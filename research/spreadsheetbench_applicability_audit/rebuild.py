#!/usr/bin/env python3
"""SpreadsheetBench-2 applicability audit: reconstruct the controlled-stratum
(SpreadsheetBench-2 provenance) subset of the frozen Tier 1
external-validity study from primary evidence.

Frozen sources are streamed from the pinned Tier 1 commit and never
modified. All derived files point back to them.

Reads (frozen, via git show):
  <T1>:research/external_validity_tier1/TASK_MANIFEST.json
  <T1>:research/external_validity_tier1/WORKBOOK_MANIFEST.json
  <T1>:research/external_validity_tier1/RUN_LEDGER.jsonl
  <T1>:research/external_validity_tier1/RUNTIME_REPLAY.jsonl
  <T1>:research/external_validity_tier1/ROUTING_CENSUS.jsonl
  <T1>:research/external_validity_tier1/REPLAY_TRIAGE.json
  <T1>:research/external_validity_tier1/MODEL_MANIFEST.json

Writes (derived):
  research/spreadsheetbench_applicability_audit/task_population.csv
  research/spreadsheetbench_applicability_audit/invocation_ledger.csv
  research/spreadsheetbench_applicability_audit/task_summary.csv
  research/spreadsheetbench_applicability_audit/model_summary.csv
  research/spreadsheetbench_applicability_audit/summary.json

Definitions (mechanical, from the frozen artifacts):
  canonical block record: one (run, step, block) replay unit (166 total).
  replayable: canonical minus r18 step 29 (triage-excluded, unreplayable
    shell for-loop) = 165.
  executed Python invocation: replayable minus r18 step 47 block 1 (empty
    record: 0 bytes, exit -1, wall 0.0, null route in both arms) = 164.
  useful direct service: recalc arm direct_served_loads >= 1.
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

T1_COMMIT = "7d0db1e5ceea511bbfe37f9a7c5796eb3773a2e4"
T1_DIR = "research/external_validity_tier1"
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "research/spreadsheetbench_applicability_audit"

EXCLUDED_UNREPLAYABLE = ("tier1-r18-O-mimo-Financial_Model-07_01", 29, 0)
EMPTY_RECORD = ("tier1-r18-O-mimo-Financial_Model-07_01", 47, 1)


def gshow(name):
    p = subprocess.run(
        ["git", "show", f"{T1_COMMIT}:{T1_DIR}/{name}"],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    return p.stdout


def load_jsonl(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main():
    task_manifest = json.loads(gshow("TASK_MANIFEST.json"))
    workbook_manifest = {t["task"]: t for t in json.loads(gshow("WORKBOOK_MANIFEST.json"))}
    runs = load_jsonl(gshow("RUN_LEDGER.jsonl"))
    replay = load_jsonl(gshow("RUNTIME_REPLAY.jsonl"))
    routing = load_jsonl(gshow("ROUTING_CENSUS.jsonl"))
    triage = json.loads(gshow("REPLAY_TRIAGE.json"))
    assert triage["total_blocks"] == 166

    stratum = {t["task"]: t["stratum"] for t in task_manifest}
    assert set(stratum.values()) == {"controlled", "read", "mutation", "mixed"}
    controlled_tasks = sorted(t for t, s in stratum.items() if s == "controlled")
    assert len(controlled_tasks) == 6, controlled_tasks
    # Study term "controlled" == SpreadsheetBench-2 provenance, original workbooks.
    for t in controlled_tasks:
        assert workbook_manifest[t]["source"].startswith("SpreadsheetBench-2"), t
        assert workbook_manifest[t]["original"] is True, t

    # ---- block-level join across arms ----
    by_key = {}
    for r in replay:
        key = (r["run_name"], r["step"], r["block"])
        by_key.setdefault(key, {})[r["arm"]] = r
    assert len(by_key) == 166, len(by_key)
    for key, arms in by_key.items():
        assert set(arms) == {"base", "recalc"}, key

    def is_empty(key):
        b, rc = by_key[key]["base"], by_key[key]["recalc"]
        return (
            b["bytes"] == 0 and rc["bytes"] == 0
            and b["exit"] == -1 and rc["exit"] == -1
            and b["wall_s"] == 0.0 and rc["wall_s"] == 0.0
            and b["route"] is None and rc["route"] is None
        )

    assert is_empty(EMPTY_RECORD)
    assert sum(1 for k in by_key if is_empty(k)) == 1, "exactly one empty record expected"
    assert EXCLUDED_UNREPLAYABLE in by_key

    ledger = []
    for key in sorted(by_key):
        b, rc = by_key[key]["base"], by_key[key]["recalc"]
        assert b["task"] == rc["task"] and b["model"] == rc["model"]
        assert b["ast"] == rc["ast"], key  # same block source
        counts = rc.get("counts") or {}
        ledger.append(
            {
                "run_name": key[0],
                "task": b["task"],
                "stratum": stratum[b["task"]],
                "controlled": stratum[b["task"]] == "controlled",
                "model": b["model"],
                "step": key[1],
                "block": key[2],
                "replayable": key != EXCLUDED_UNREPLAYABLE,
                "executed": key != EXCLUDED_UNREPLAYABLE and not is_empty(key),
                "base_exit": b["exit"],
                "recalc_exit": rc["exit"],
                "base_wall_s": b["wall_s"],
                "recalc_wall_s": rc["wall_s"],
                "validity": b["validity"],
                "route": rc.get("route"),
                "admitted": rc.get("admitted"),
                "admission_reason": rc.get("admission_reason"),
                "artifact": rc.get("artifact"),
                "direct_served_loads": rc.get("direct_served_loads"),
                "direct_served_reads": counts.get("direct_served_reads"),
                "direct_iteration_cells": counts.get("direct_iteration_cells"),
                "direct_iteration_rows": counts.get("direct_iteration_rows"),
                "fallback_loads": counts.get("fallback_loads"),
                "reference_loads": counts.get("reference_loads"),
                "fallback_reasons": rc.get("fallback_reasons"),
                "ast_load_workbook": b["ast"]["load_workbook"],
                "ast_save": b["ast"]["save"],
                "ast_cell_write": b["ast"]["cell_write"],
                "ast_formula_write": b["ast"]["formula_write"],
                "read_only_ast": (b["ast"]["cell_write"] == 0 and b["ast"]["formula_write"] == 0 and b["ast"]["save"] == 0),
            }
        )

    for e in ledger:
        dsl = e["direct_served_loads"]
        e["useful_direct_service"] = (dsl is not None and dsl >= 1)

    # ---- full-population validation against the frozen report ----
    n_canon = len(ledger)
    n_replay = sum(1 for e in ledger if e["replayable"])
    n_exec = sum(1 for e in ledger if e["executed"])
    assert (n_canon, n_replay, n_exec) == (166, 165, 164)
    exec_rows = [e for e in ledger if e["executed"]]
    from collections import Counter
    assert Counter(e["route"] for e in exec_rows) == {
        "REFERENCE_FAST_PATH": 146, "DIRECT_RUNTIME": 10, "DIRECT_WITH_FALLBACK": 8,
    }
    assert sum(1 for e in exec_rows if e["admitted"]) == 18
    assert all(
        (e["direct_served_loads"] or 0) == 0
        for e in exec_rows if e["route"] == "DIRECT_WITH_FALLBACK"
    ), "every fallback block must serve zero direct loads"
    assert all(
        e["direct_served_loads"] == 1
        for e in exec_rows if e["route"] == "DIRECT_RUNTIME"
    )
    assert sum(1 for e in exec_rows if e["useful_direct_service"]) == 10
    # Historical replay aggregates (report section 12): BASE 122.8 / RECALC 125.3.
    agg_base = sum(e["base_wall_s"] for e in ledger if e["replayable"])
    agg_recalc = sum(e["recalc_wall_s"] for e in ledger if e["replayable"])
    assert abs(agg_base - 122.8) < 0.05, agg_base
    assert abs(agg_recalc - 125.3) < 0.05, agg_recalc
    # "136 read-only blocks" cross-check (report section 13): the historical
    # figure counts over the 165 replayable records (it includes the empty
    # r18s47b1 record, whose null AST is trivially read-only). Over the 164
    # executed invocations the count is 135.
    replay_rows = [e for e in ledger if e["replayable"]]
    n_readonly_replayable = sum(1 for e in replay_rows if e["read_only_ast"])
    assert n_readonly_replayable == 136, n_readonly_replayable
    n_readonly = sum(1 for e in exec_rows if e["read_only_ast"])
    assert n_readonly == 135, n_readonly

    # ---- controlled (SpreadsheetBench-2) subset ----
    sub = [e for e in ledger if e["controlled"]]
    sub_exec = [e for e in sub if e["executed"]]
    sub_replay = [e for e in sub if e["replayable"]]
    sub_runs = sorted({e["run_name"] for e in sub})
    assert len(sub_runs) == 9, sub_runs
    for r in runs:
        if r["run_name"] in sub_runs:
            assert r["task"] in controlled_tasks

    def rates(rows):
        n = len(rows)
        d = {
            "n": n,
            "admitted": sum(1 for e in rows if e["admitted"]),
            "fully_direct": sum(1 for e in rows if e["route"] == "DIRECT_RUNTIME"),
            "fallback": sum(1 for e in rows if e["route"] == "DIRECT_WITH_FALLBACK"),
            "reference": sum(1 for e in rows if e["route"] == "REFERENCE_FAST_PATH"),
            "useful": sum(1 for e in rows if e["useful_direct_service"]),
        }
        return d

    full_rates = rates(exec_rows)
    sub_rates = rates(sub_exec)
    sub_loads_direct = sum(e["direct_served_loads"] or 0 for e in sub_exec)
    sub_load_sites = sum(e["ast_load_workbook"] for e in sub_exec)
    sub_reads = sum(e["direct_served_reads"] or 0 for e in sub_exec)
    sub_cells = sum(e["direct_iteration_cells"] or 0 for e in sub_exec)
    sub_rows = sum(e["direct_iteration_rows"] or 0 for e in sub_exec)
    sub_base = sum(e["base_wall_s"] for e in sub_replay)
    sub_recalc = sum(e["recalc_wall_s"] for e in sub_replay)

    tasks_exposed = sum(
        1 for t in controlled_tasks
        if any(e["useful_direct_service"] for e in sub_exec if e["task"] == t)
    )
    runs_exposed = sum(
        1 for r in sub_runs
        if any(e["useful_direct_service"] for e in sub_exec if e["run_name"] == r)
    )

    # ---- per-task and per-model tables ----
    task_rows = []
    for t in controlled_tasks:
        te = [e for e in sub_exec if e["task"] == t]
        tr = [e for e in sub_replay if e["task"] == t]
        r = rates(te)
        task_rows.append(
            {
                "task": t,
                "task_family": t.split(":")[0],
                "source": workbook_manifest[t]["source"],
                "original_workbook": workbook_manifest[t]["original"],
                "n_trajectories": len({e["run_name"] for e in te}),
                "executed_invocations": r["n"],
                "fully_direct": r["fully_direct"],
                "useful_direct": r["useful"],
                "fallback": r["fallback"],
                "reference": r["reference"],
                "admitted": r["admitted"],
                "ast_load_sites": sum(e["ast_load_workbook"] for e in te),
                "direct_served_loads": sum(e["direct_served_loads"] or 0 for e in te),
                "direct_reads": sum(e["direct_served_reads"] or 0 for e in te),
                "iteration_cells": sum(e["direct_iteration_cells"] or 0 for e in te),
                "base_replay_s": sum(e["base_wall_s"] for e in tr),
                "recalc_replay_s": sum(e["recalc_wall_s"] for e in tr),
            }
        )
        task_rows[-1]["replay_diff_s"] = task_rows[-1]["recalc_replay_s"] - task_rows[-1]["base_replay_s"]

    model_rows = []
    for m in sorted({e["model"] for e in sub}):
        me = [e for e in sub_exec if e["model"] == m]
        r = rates(me)
        model_rows.append(
            {
                "model": m,
                "n_trajectories": len({e["run_name"] for e in me}),
                "executed_invocations": r["n"],
                "fully_direct": r["fully_direct"],
                "useful_direct": r["useful"],
                "fallback": r["fallback"],
                "reference": r["reference"],
                "admitted": r["admitted"],
                "direct_served_loads": sum(e["direct_served_loads"] or 0 for e in me),
                "direct_reads": sum(e["direct_served_reads"] or 0 for e in me),
                "iteration_cells": sum(e["direct_iteration_cells"] or 0 for e in me),
            }
        )

    # ---- task population table ----
    pop_rows = []
    for t in task_manifest:
        pop_rows.append(
            {
                "task": t["task"],
                "task_family": t["task"].split(":")[0],
                "stratum": t["stratum"],
                "controlled_spreadsheetbench2": t["stratum"] == "controlled",
                "source": workbook_manifest[t["task"]]["source"],
                "original_workbook": workbook_manifest[t["task"]]["original"],
                "instruction_sha256": t["instruction_sha256"],
                "contaminated_public_example": t["contaminated_public_example"],
                "trajectories": sorted({e["run_name"] for e in ledger if e["task"] == t["task"]}),
                "inclusion_status": "INCLUDED",
                "exclusion_reason": None,
            }
        )

    summary = {
        "frozen_commit": T1_COMMIT,
        "full_population": {
            "tasks": 12,
            "trajectories": len(runs),
            "canonical_blocks": n_canon,
            "replayable_blocks": n_replay,
            "executed_invocations": n_exec,
            "excluded_unreplayable": ["%s step %d block %d" % EXCLUDED_UNREPLAYABLE],
            "empty_record": ["%s step %d block %d" % EMPTY_RECORD],
            "routes_executed": full_rates,
            "replay_base_s": agg_base,
            "replay_recalc_s": agg_recalc,
            "read_only_ast_executed": n_readonly,
            "read_only_ast_replayable": n_readonly_replayable,
        },
        "controlled_subset": {
            "definition": "stratum == 'controlled' (study term): 6 tasks with SpreadsheetBench-2 provenance, original workbooks",
            "tasks": controlled_tasks,
            "n_tasks": 6,
            "trajectories": sub_runs,
            "n_trajectories": 9,
            "canonical_blocks": len(sub),
            "replayable_blocks": len(sub_replay),
            "executed_invocations": len(sub_exec),
            "routes_executed": sub_rates,
            "metric_A_fully_direct_rate": sub_rates["fully_direct"] / sub_rates["n"],
            "metric_B_useful_service_rate": sub_rates["useful"] / sub_rates["n"],
            "metric_C_admission_rate": sub_rates["admitted"] / sub_rates["n"],
            "metric_D_load_service_rate": sub_loads_direct / sub_load_sites,
            "metric_D_loads_direct": sub_loads_direct,
            "metric_D_load_sites_ast": sub_load_sites,
            "metric_E_task_exposure": tasks_exposed / 6,
            "metric_E_tasks_exposed": tasks_exposed,
            "metric_F_trajectory_exposure": runs_exposed / 9,
            "metric_F_runs_exposed": runs_exposed,
            "direct_reads": sub_reads,
            "iteration_cells": sub_cells,
            "iteration_rows": sub_rows,
            "replay_base_s": sub_base,
            "replay_recalc_s": sub_recalc,
            "replay_diff_s": sub_recalc - sub_base,
            "replay_ratio": sub_recalc / sub_base,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)

    def write_csv(name, rows, cols):
        with open(OUT / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for e in rows:
                w.writerow({c: (json.dumps(e[c]) if isinstance(e[c], (list, dict)) else e[c]) for c in cols})

    write_csv("task_population.csv", pop_rows, list(pop_rows[0].keys()))
    write_csv("invocation_ledger.csv", ledger, list(ledger[0].keys()) + ["useful_direct_service"])
    write_csv("task_summary.csv", task_rows, list(task_rows[0].keys()))
    write_csv("model_summary.csv", model_rows, list(model_rows[0].keys()))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    s = summary["controlled_subset"]
    print(f"full: canon={n_canon} replay={n_replay} exec={n_exec} base={agg_base:.2f} recalc={agg_recalc:.2f} readonly={n_readonly}")
    print(f"subset: tasks=6 runs=9 canon={len(sub)} replay={len(sub_replay)} exec={len(sub_exec)}")
    print(f"subset routes: {sub_rates}")
    print(f"A={s['metric_A_fully_direct_rate']:.4f} B={s['metric_B_useful_service_rate']:.4f} C={s['metric_C_admission_rate']:.4f} "
          f"D={s['metric_D_load_service_rate']:.4f} ({sub_loads_direct}/{sub_load_sites}) E={s['metric_E_task_exposure']:.4f} F={s['metric_F_trajectory_exposure']:.4f}")
    print(f"subset replay: base={sub_base:.3f} recalc={sub_recalc:.3f} diff={s['replay_diff_s']:+.3f} ratio={s['replay_ratio']:.4f}")
    print(f"reads={sub_reads} cells={sub_cells} rows={sub_rows}")
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
