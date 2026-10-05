#!/usr/bin/env python3
"""Benefit evidence ledger: consolidate frozen Recalc benefit evidence into
one canonical machine-readable record with explicit benefit statuses.

Frozen primaries (read-only):
  research/full_cell_iteration_probe/PERFORMANCE_RESULTS.jsonl      (R2, master checkout)
  research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl (R3)
  research/full_cell_iteration_product_confirmation/_staging/parity_r3.jsonl
  research/execution_surface_census/WORKLOAD_MANIFEST.json          (R1 manifest)
  docs/evidence/readme_vignette/timing.json                        (0.2.0 vignette)
  <T1_COMMIT>:research/external_validity_tier1/{TASK,WORKBOOK}_MANIFEST,
    RUN_LEDGER, RUNTIME_REPLAY, REPLAY_TRIAGE                        (Tier 1, via git show)

Cross-checks (prior audits, read-only via git show):
  research/tier2-performance-distribution-audit: tier2_summary.json
  research/spreadsheetbench-applicability-audit: summary.json

Writes: benefit_ledger.{csv,json}, summary.json under
research/benefit_evidence_ledger/.

Benefit-status taxonomy (row-local; never transferred across units).
Whole-task non-benefit is always recorded via the more specific
DIRECT_SERVICE_NO_WHOLE_TASK_BENEFIT or NO_USEFUL_DIRECT_SERVICE:
  WHOLE_TASK_BENEFIT                 complete measured trajectory/task replay faster
  SUBSTEP_BENEFIT                    defined substep faster; no whole-task result
  SUBSTEP_NO_BENEFIT                 measured substep not faster
  DIRECT_BLOCK_BENEFIT               served block faster (block unit only)
  DIRECT_SERVICE_NO_WHOLE_TASK_BENEFIT service occurred but task did not improve
  NO_USEFUL_DIRECT_SERVICE           executed; zero served loads/reads
  CONDITIONAL_MECHANISM_EFFECT       population aggregate showing mechanism value
  NO_POPULATION_BENEFIT              population aggregate showing no benefit
  NOT_EVALUATED                      no valid paired evidence at that unit
"""

import csv
import json
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research/benefit_evidence_ledger"
T1 = "7d0db1e5ceea511bbfe37f9a7c5796eb3773a2e4"
T1D = "research/external_validity_tier1"
T2_BRANCH = "research/tier2-performance-distribution-audit"
SB2_BRANCH = "research/spreadsheetbench-applicability-audit"

EXCLUDED = ("tier1-r18-O-mimo-Financial_Model-07_01", 29, 0)
EMPTY = ("tier1-r18-O-mimo-Financial_Model-07_01", 47, 1)


def gshow(rev, path):
    p = subprocess.run(["git", "show", f"{rev}:{path}"],
                       cwd=REPO, capture_output=True, text=True, check=True)
    return p.stdout


def jload(path):
    return json.loads((REPO / path).read_text())


def jlload(path):
    return [json.loads(l) for l in (REPO / path).read_text().splitlines() if l.strip()]


COLS = ["study_id", "study_commit", "benchmark", "benchmark_task_id", "task_family",
        "task_id", "workload_id", "trajectory_id", "model_family", "unit_type",
        "measurement_scope", "benefit_status", "comparator", "recalc_variant",
        "warm_or_cold", "artifact_state", "route", "direct_served_loads",
        "direct_reads", "iteration_cells", "base_runtime_s", "recalc_runtime_s",
        "absolute_delta_s", "relative_delta", "repetitions", "reducer",
        "semantic_parity_status", "whole_task_result_available",
        "substep_result_available", "workbook_bytes", "sheet_count",
        "read_only_or_mutating", "direct_base_share", "notes",
        "primary_evidence_path", "primary_evidence_key"]


def row(**kw):
    r = {c: None for c in COLS}
    r.update(kw)
    unknown = set(kw) - set(COLS)
    assert not unknown, unknown
    return r


def main():
    ledger = []

    # ---------------- R3: 30 frozen workloads + population ----------------
    r3 = jlload("research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl")
    assert len(r3) == 30
    parity = {p["workload"]: p["parity"] for p in
              jlload("research/full_cell_iteration_product_confirmation/_staging/parity_r3.jsonl")
              if p["population"] == "A"}
    assert len(parity) == 30 and all(parity.values())
    wmanifest = jload("research/execution_surface_census/WORKLOAD_MANIFEST.json")
    wbytes = {w["workload_id"]: w["workbook_bytes"] for w in wmanifest["populations"]["A"]["workloads"]}
    sum_base = sum_off = sum_on = 0.0
    for e in r3:
        wid = e["workload"]
        fam = wid.split("_")[0] + ("_" + wid.split("_")[1] if "_" in wid else "")
        fam = {"Debugging": "Debugging", "Financial": "Financial_Model", "Template": "Template"}[wid.split("_")[0]]
        b = statistics.median(e["arms"]["BASE"]["wall_s"])
        o = statistics.median(e["arms"]["OFF"]["wall_s"])
        n = statistics.median(e["arms"]["ON"]["wall_s"])
        sum_base += b
        sum_off += o
        sum_on += n
        on_routes = e["arms"]["ON"]["routes"]
        assert len(set(on_routes)) == 1
        loads = [c.get("direct_served_loads", 0) for c in e["arms"]["ON"]["counts"]]
        reads = [c.get("direct_served_reads", 0) for c in e["arms"]["ON"]["counts"]]
        cells = [c.get("direct_iteration_cells", 0) for c in e["arms"]["ON"]["counts"]]
        served = max(loads) > 0
        faster = n < o
        status = ("SUBSTEP_BENEFIT" if faster else "SUBSTEP_NO_BENEFIT") if served else "NO_USEFUL_DIRECT_SERVICE"
        task_bits = wid.rsplit("__", 1)[0]
        ledger.append(row(
            study_id="R3-full-cell-iteration-product-confirmation",
            study_commit="fed04b5", benchmark="SpreadsheetBench-2",
            benchmark_task_id=task_bits, task_family=fam, workload_id=wid,
            unit_type="frozen workload",
            measurement_scope="single agent-script execution (complete script; substep of its source trajectory)",
            benefit_status=status, comparator="OFF (rc3-equivalent predecessor)", recalc_variant="ON (rc4 iteration candidate)",
            warm_or_cold="warm", artifact_state="REUSED (direct rows)",
            route=on_routes[0], direct_served_loads=max(loads),
            direct_reads=max(reads), iteration_cells=max(cells),
            base_runtime_s=o, recalc_runtime_s=n, absolute_delta_s=n - o,
            relative_delta=n / o - 1, repetitions=3, reducer="median-of-3",
            semantic_parity_status="R3 A/B differential PASS (parity_r3.jsonl)",
            whole_task_result_available=False, substep_result_available=True,
            workbook_bytes=wbytes.get(wid), read_only_or_mutating="read-only (population construction: 0 saves)",
            notes="BASE (bare openpyxl) median %.4f s carried for reference; historical pair is OFF->ON" % b,
            primary_evidence_path="research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl",
            primary_evidence_key=wid))
    ledger.append(row(
        study_id="R3-full-cell-iteration-product-confirmation", study_commit="fed04b5",
        benchmark="SpreadsheetBench-2 (Pop A representative-30)",
        unit_type="study population",
        measurement_scope="population aggregate: sum of per-workload medians, all 30 (13 targets + 8 pre-existing + 9 blocked)",
        benefit_status="CONDITIONAL_MECHANISM_EFFECT",
        comparator="OFF (rc3-equivalent)", recalc_variant="ON (rc4 candidate)",
        warm_or_cold="warm", base_runtime_s=sum_off, recalc_runtime_s=sum_on,
        absolute_delta_s=sum_on - sum_off, relative_delta=sum_on / sum_off - 1,
        repetitions=3, reducer="sum-of-medians",
        semantic_parity_status="40/40 adversarial + 52/52 A/B differential",
        whole_task_result_available=False, substep_result_available=True,
        notes="102.26 -> 21.51 s (-79.0%); 23/30 faster; median ratio 0.91; top-3 = 84% of savings. Mechanism effect, not typical-workload or task claim.",
        primary_evidence_path="research/full_cell_iteration_product_confirmation/PRODUCT_GATE.json",
        primary_evidence_key="economic"))

    # ---------------- R2: population + FM:08_02 window ----------------
    r2 = jlload("research/full_cell_iteration_probe/PERFORMANCE_RESULTS.jsonl")
    r2a = [x for x in r2 if "A" in x["populations"]]
    assert len(r2a) == 30
    r2base = sum(statistics.median(x["arms"]["BASE"]["wall_s"]) for x in r2a)
    r2on = sum(statistics.median(x["arms"]["ON"]["wall_s"]) for x in r2a)
    ledger.append(row(
        study_id="R2-full-cell-iteration-probe", study_commit="e44e82b",
        benchmark="SpreadsheetBench-2 (Pop A representative-30)",
        unit_type="study population",
        measurement_scope="population aggregate: sum of per-workload medians, BASE->ON (probe host)",
        benefit_status="CONDITIONAL_MECHANISM_EFFECT",
        comparator="BASE (bare openpyxl)", recalc_variant="ON (research probe)",
        warm_or_cold="warm", base_runtime_s=r2base, recalc_runtime_s=r2on,
        absolute_delta_s=r2on - r2base, relative_delta=r2on / r2base - 1,
        repetitions=3, reducer="sum-of-medians",
        semantic_parity_status="39/39 adversarial + 52/52 A/B differential",
        whole_task_result_available=False, substep_result_available=True,
        notes="63.22 -> 15.00 s (4.21x) on probe host; verdict MECHANISM_REAL_BUT_NOT_PRODUCT (count-gate form). Do not splice with R3 (different host/comparator).",
        primary_evidence_path="research/full_cell_iteration_probe/PERFORMANCE_RESULTS.jsonl",
        primary_evidence_key="populations=A aggregate"))
    fm2 = next(x for x in r2a if x["workload"] == "Financial_Model_08_02__4ca3ae46295d")
    b2 = statistics.median(fm2["arms"]["BASE"]["wall_s"])
    n2 = statistics.median(fm2["arms"]["ON"]["wall_s"])
    c2 = fm2["arms"]["ON"]["counts"][0]
    ledger.append(row(
        study_id="R2-full-cell-iteration-probe", study_commit="e44e82b",
        benchmark="SpreadsheetBench-2", benchmark_task_id="Financial_Model:08_02",
        task_family="Financial_Model", workload_id="Financial_Model_08_02__4ca3ae46295d",
        unit_type="frozen workload",
        measurement_scope="single agent-script execution: read-only Assumptions-sheet inspection step (R2 window)",
        benefit_status="SUBSTEP_BENEFIT", comparator="BASE (bare openpyxl)",
        recalc_variant="ON (research probe)", warm_or_cold="warm",
        artifact_state="REUSED", route="DIRECT_RUNTIME",
        direct_served_loads=c2["direct_served_loads"], direct_reads=c2["direct_served_reads"],
        iteration_cells=c2["direct_iteration_cells"],
        base_runtime_s=b2, recalc_runtime_s=n2, absolute_delta_s=n2 - b2,
        relative_delta=n2 / b2 - 1, repetitions=3, reducer="median-of-3",
        semantic_parity_status="R2 A/B differential PASS",
        whole_task_result_available=False, substep_result_available=True,
        notes="Window 1 of 3 for this workload (R2 probe host).",
        primary_evidence_path="research/full_cell_iteration_probe/PERFORMANCE_RESULTS.jsonl",
        primary_evidence_key="Financial_Model_08_02__4ca3ae46295d"))

    # ---------------- Vignette: 0.2.0 reproduction window ----------------
    vt = jload("docs/evidence/readme_vignette/timing.json")
    assert vt["workload"] == "Financial_Model_08_02__4ca3ae46295d"
    ledger.append(row(
        study_id="vignette-0.2.0-reproduction", study_commit="89f3dfd",
        benchmark="SpreadsheetBench-2", benchmark_task_id="Financial_Model:08_02",
        task_family="Financial_Model", workload_id=vt["workload"],
        unit_type="inspection substep",
        measurement_scope="one real read-only inspection step from the FM:08_02 agent trajectory (NOT the whole task)",
        benefit_status="SUBSTEP_BENEFIT", comparator="BASE (bare python/openpyxl)",
        recalc_variant="released recalc-agent 0.2.0", warm_or_cold="warm",
        artifact_state="REUSED x3", route="DIRECT_RUNTIME (3/3)",
        direct_served_loads=1, direct_reads=8351, iteration_cells=4800,
        base_runtime_s=vt["base_median_s"], recalc_runtime_s=vt["recalc_median_s"],
        absolute_delta_s=vt["recalc_median_s"] - vt["base_median_s"],
        relative_delta=vt["ratio"] - 1, repetitions=3, reducer="median-of-3",
        semantic_parity_status=vt["parity_standard"][:220],
        whole_task_result_available=False, substep_result_available=True,
        workbook_bytes=wbytes.get("Financial_Model_08_02__4ca3ae46295d"),
        read_only_or_mutating="read-only (workbook bytes unchanged)",
        notes="3.6866 -> 0.7320 s (-80.14%). Window 3 of 3 (R3 frozen row is window 2, in the R3 workload rows). Must never become a whole-task claim.",
        primary_evidence_path="docs/evidence/readme_vignette/timing.json",
        primary_evidence_key="base_median_s/recalc_median_s"))

    # ---------------- Tier 1: trajectories, tasks, blocks, populations ----------------
    t1_tasks = json.loads(gshow(T1, f"{T1D}/TASK_MANIFEST.json"))
    t1_wb = {t["task"]: t for t in json.loads(gshow(T1, f"{T1D}/WORKBOOK_MANIFEST.json"))}
    t1_runs = [json.loads(l) for l in gshow(T1, f"{T1D}/RUNTIME_REPLAY.jsonl").splitlines()]
    stratum = {t["task"]: t["stratum"] for t in t1_tasks}
    by_key = {}
    for r in t1_runs:
        by_key.setdefault((r["run_name"], r["step"], r["block"]), {})[r["arm"]] = r
    assert len(by_key) == 166

    def lbl(run):
        return "P (anthropic/claude-sonnet-4.5)" if "-P-" in run else "O (xiaomi/mimo-v2.6-pro)"

    run_names = sorted({k[0] for k in by_key})
    assert len(run_names) == 18
    traj_rows = {}
    for run in run_names:
        keys = sorted(k for k in by_key if k[0] == run)
        task = by_key[keys[0]]["base"]["task"]
        timed = [k for k in keys if k != EXCLUDED]
        ex = [k for k in timed if k != EMPTY]
        tb = sum(by_key[k]["base"]["wall_s"] for k in timed)
        tr = sum(by_key[k]["recalc"]["wall_s"] for k in timed)
        d = sum(1 for k in ex if by_key[k]["recalc"].get("route") == "DIRECT_RUNTIME")
        fb = sum(1 for k in ex if by_key[k]["recalc"].get("route") == "DIRECT_WITH_FALLBACK")
        loads = sum((by_key[k]["recalc"].get("direct_served_loads") or 0) for k in ex)
        reads = sum(((by_key[k]["recalc"].get("counts") or {}).get("direct_served_reads") or 0) for k in ex)
        cells = sum(((by_key[k]["recalc"].get("counts") or {}).get("direct_iteration_cells") or 0) for k in ex)
        writes = sum(by_key[k]["base"]["ast"]["cell_write"] + by_key[k]["base"]["ast"]["formula_write"] + by_key[k]["base"]["ast"]["save"] for k in ex)
        val = Counter(by_key[k]["base"]["validity"] for k in timed)
        served = loads >= 1
        faster = tr < tb
        status = ("WHOLE_TASK_BENEFIT" if faster else "DIRECT_SERVICE_NO_WHOLE_TASK_BENEFIT") if served else "NO_USEFUL_DIRECT_SERVICE"
        if not served and faster:
            status = "NO_USEFUL_DIRECT_SERVICE"  # no service: delta unattributable
        db = sum(by_key[k]["base"]["wall_s"] for k in ex if by_key[k]["recalc"].get("route") == "DIRECT_RUNTIME")
        traj_rows[run] = dict(task=task, n=len(ex), d=d, fb=fb, loads=loads, reads=reads,
                              cells=cells, tb=tb, tr=tr, status=status,
                              share=(db / tb) if served else None)
        ledger.append(row(
            study_id="Tier1-external-validity", study_commit=T1,
            benchmark="SpreadsheetBench-2" if stratum[task] == "controlled" else "Tier 1 curated",
            benchmark_task_id=task, task_family=task.split(":")[0], task_id=task,
            trajectory_id=run, model_family=lbl(run), unit_type="trajectory",
            measurement_scope="whole trajectory replay: paired per-block replay summed (%d executed invocations)" % len(ex),
            benefit_status=status, comparator="BASE (bare python/openpyxl, same window)",
            recalc_variant="released recalc-agent 0.2.0", warm_or_cold="warm (replay cache)",
            direct_served_loads=loads, direct_reads=reads, iteration_cells=cells,
            base_runtime_s=tb, recalc_runtime_s=tr, absolute_delta_s=tr - tb,
            relative_delta=tr / tb - 1, repetitions=1, reducer="single paired replay, summed",
            semantic_parity_status="validity mix: " + ", ".join(f"{v}={c}" for v, c in sorted(val.items())),
            whole_task_result_available=True, substep_result_available=True,
            workbook_bytes=t1_wb[task]["size_bytes"], sheet_count=t1_wb[task]["sheet_count"],
            read_only_or_mutating="mutating" if writes else "read-only",
            direct_base_share=(db / tb) if served else None,
            notes="%d direct / %d fallback / %d reference; stratum=%s" % (d, fb, len(ex) - d - fb, stratum[task]),
            primary_evidence_path=f"{T1D}/RUNTIME_REPLAY.jsonl@{T1[:7]}",
            primary_evidence_key=run))

    for t in sorted(stratum):
        runs_t = [rn for rn in run_names if traj_rows[rn]["task"] == t]
        tb = sum(traj_rows[rn]["tb"] for rn in runs_t)
        tr = sum(traj_rows[rn]["tr"] for rn in runs_t)
        loads = sum(traj_rows[rn]["loads"] for rn in runs_t)
        served = loads >= 1
        faster = tr < tb
        status = ("WHOLE_TASK_BENEFIT" if faster else "DIRECT_SERVICE_NO_WHOLE_TASK_BENEFIT") if served else "NO_USEFUL_DIRECT_SERVICE"
        ledger.append(row(
            study_id="Tier1-external-validity", study_commit=T1,
            benchmark="SpreadsheetBench-2" if stratum[t] == "controlled" else "Tier 1 curated",
            benchmark_task_id=t, task_family=t.split(":")[0], task_id=t,
            model_family="P+O" if len(runs_t) > 1 else lbl(runs_t[0]),
            unit_type="task (multi-trajectory sum)",
            measurement_scope="DESCRIPTIVE task sum across %d trajector%s (not a single execution)" % (len(runs_t), "y" if len(runs_t) == 1 else "ies"),
            benefit_status=status, comparator="BASE (same-window replay)",
            recalc_variant="released recalc-agent 0.2.0", warm_or_cold="warm (replay cache)",
            direct_served_loads=loads,
            direct_reads=sum(traj_rows[rn]["reads"] for rn in runs_t),
            iteration_cells=sum(traj_rows[rn]["cells"] for rn in runs_t),
            base_runtime_s=tb, recalc_runtime_s=tr, absolute_delta_s=tr - tb,
            relative_delta=tr / tb - 1, repetitions=1, reducer="sum of trajectory replay sums",
            whole_task_result_available=True, substep_result_available=True,
            workbook_bytes=t1_wb[t]["size_bytes"], sheet_count=t1_wb[t]["sheet_count"],
            notes="trajectories: " + ", ".join(runs_t),
            primary_evidence_path=f"{T1D}/RUNTIME_REPLAY.jsonl@{T1[:7]}",
            primary_evidence_key="task=" + t))

    n_direct_blocks = 0
    for key in sorted(by_key):
        rc = by_key[key]["recalc"]
        if rc.get("route") != "DIRECT_RUNTIME":
            continue
        n_direct_blocks += 1
        b = by_key[key]["base"]
        c = rc.get("counts") or {}
        assert rc["wall_s"] < b["wall_s"], key
        ledger.append(row(
            study_id="Tier1-external-validity", study_commit=T1,
            benchmark="SpreadsheetBench-2" if stratum[b["task"]] == "controlled" else "Tier 1 curated",
            benchmark_task_id=b["task"], task_family=b["task"].split(":")[0],
            task_id=b["task"], trajectory_id=key[0], model_family=lbl(key[0]),
            unit_type="python invocation (replay block)",
            measurement_scope="single replay block, paired (step %d block %d)" % (key[1], key[2]),
            benefit_status="DIRECT_BLOCK_BENEFIT", comparator="BASE (same window)",
            recalc_variant="released recalc-agent 0.2.0", warm_or_cold="warm",
            artifact_state=json.dumps(rc.get("artifact")), route="DIRECT_RUNTIME",
            direct_served_loads=rc.get("direct_served_loads"),
            direct_reads=c.get("direct_served_reads"), iteration_cells=c.get("direct_iteration_cells"),
            base_runtime_s=b["wall_s"], recalc_runtime_s=rc["wall_s"],
            absolute_delta_s=rc["wall_s"] - b["wall_s"],
            relative_delta=rc["wall_s"] / b["wall_s"] - 1, repetitions=1, reducer="single paired replay",
            semantic_parity_status="validity=" + b["validity"],
            whole_task_result_available=True, substep_result_available=True,
            notes="1 of 10 directly served blocks study-wide",
            primary_evidence_path=f"{T1D}/RUNTIME_REPLAY.jsonl@{T1[:7]}",
            primary_evidence_key="%s s%d b%d" % (key[0], key[1], key[2])))
    assert n_direct_blocks == 10

    def pop_row(name, keys, status, scope_note):
        tb = sum(by_key[k]["base"]["wall_s"] for k in keys)
        tr = sum(by_key[k]["recalc"]["wall_s"] for k in keys)
        return row(study_id="Tier1-external-validity", study_commit=T1,
                   benchmark=name, unit_type="study population",
                   measurement_scope="population replay aggregate over %d rows/arm (%s)" % (len(keys), scope_note),
                   benefit_status=status, comparator="BASE (same-window replay)",
                   recalc_variant="released recalc-agent 0.2.0", warm_or_cold="warm",
                   base_runtime_s=tb, recalc_runtime_s=tr, absolute_delta_s=tr - tb,
                   relative_delta=tr / tb - 1, repetitions=1, reducer="sum over replayable rows",
                   whole_task_result_available=True, substep_result_available=True,
                   notes="Both arms present for every included row.",
                   primary_evidence_path=f"{T1D}/RUNTIME_REPLAY.jsonl@{T1[:7]}+REPLAY_TRIAGE.json",
                   primary_evidence_key=name)

    all_replay = [k for k in by_key if k != EXCLUDED]
    ctl_replay = [k for k in all_replay if stratum[by_key[k]["base"]["task"]] == "controlled"]
    cur_replay = [k for k in all_replay if k not in ctl_replay]
    ledger.append(pop_row("Tier 1 full (12 tasks)", all_replay, "NO_POPULATION_BENEFIT", "165 rows"))
    ledger.append(pop_row("Tier 1 SB2 controlled (6 tasks)", ctl_replay, "NO_POPULATION_BENEFIT", "137 rows"))
    ledger.append(pop_row("Tier 1 curated (6 tasks)", cur_replay, "NO_POPULATION_BENEFIT", "28 rows"))

    # ---------------- cross-checks against prior audits ----------------
    t2 = json.loads(gshow(T2_BRANCH, "research/tier2_distribution_audit/tier2_summary.json"))
    assert abs(t2["recomputed_off_sum_medians"] - sum_off) < 1e-6
    assert abs(t2["recomputed_on_sum_medians"] - sum_on) < 1e-6
    sb2 = json.loads(gshow(SB2_BRANCH, "research/spreadsheetbench_applicability_audit/summary.json"))
    cs = sb2["controlled_subset"]
    assert cs["executed_invocations"] == sum(1 for k in ctl_replay if k != EMPTY)
    assert abs(cs["replay_base_s"] - sum(by_key[k]["base"]["wall_s"] for k in ctl_replay)) < 1e-6
    assert abs(cs["replay_recalc_s"] - sum(by_key[k]["recalc"]["wall_s"] for k in ctl_replay)) < 1e-6

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "benefit_ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for e in ledger:
            w.writerow({c: ("" if e[c] is None else e[c]) for c in COLS})
    (OUT / "benefit_ledger.json").write_text(json.dumps(ledger, indent=1) + "\n")

    by_status = Counter(e["benefit_status"] for e in ledger)
    pos_traj = [e["trajectory_id"] for e in ledger
                if e["unit_type"] == "trajectory" and e["benefit_status"] == "WHOLE_TASK_BENEFIT"]
    summary = {
        "n_rows": len(ledger),
        "by_status": dict(sorted(by_status.items())),
        "whole_task_positive_trajectories": pos_traj,
        "whole_task_positive_tasks": sorted({e["task_id"] for e in ledger
                                             if e["unit_type"] == "task (multi-trajectory sum)"
                                             and e["benefit_status"] == "WHOLE_TASK_BENEFIT"}),
        "counterexample_trajectories": [e["trajectory_id"] for e in ledger
                                        if e["unit_type"] == "trajectory"
                                        and e["benefit_status"] == "DIRECT_SERVICE_NO_WHOLE_TASK_BENEFIT"],
        "direct_blocks": n_direct_blocks,
        "crosschecks": "tier2_summary OFF/ON sums match to 1e-6; sb2 controlled replay sums match to 1e-6",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"rows={len(ledger)}")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
