"""Frozen workload-level analysis of packaged RC timing and semantic replay."""
from __future__ import annotations

import collections
import hashlib
import json
import math
import pathlib
import random
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "rc_acceleration_validation"


def read(name):
    return json.loads((OUT / name).read_text())


def rows(name):
    with (OUT / name).open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def put(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def median(values):
    return statistics.median(values) if values else None


def effects(workloads, seed=20261011):
    if not workloads:
        return {"n": 0}
    ratios = [w["ratio"] for w in workloads]
    rng = random.Random(seed)
    boots_geo, boots_med = [], []
    for _ in range(10000):
        sample = [ratios[rng.randrange(len(ratios))] for _ in ratios]
        boots_geo.append(math.exp(statistics.mean(math.log(x) for x in sample)))
        boots_med.append(statistics.median(sample))
    boots_geo.sort(); boots_med.sort()
    family = {}
    for fam in sorted({w["family"] for w in workloads}):
        rs = [w["ratio"] for w in workloads if w["family"] == fam]
        family[fam] = {"n": len(rs), "median_ratio": median(rs),
                       "faster": sum(x < 0.995 for x in rs), "slower": sum(x > 1.005 for x in rs)}
    return {"n": len(ratios), "median_ratio": median(ratios),
            "median_reduction_pct": 100 * (1 - median(ratios)),
            "arithmetic_mean_ratio": statistics.mean(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in ratios)),
            "bootstrap_95pct_ci_geometric_ratio": [boots_geo[250], boots_geo[9749]],
            "bootstrap_95pct_ci_median_ratio": [boots_med[250], boots_med[9749]],
            "faster": sum(x < 0.995 for x in ratios), "tie": sum(0.995 <= x <= 1.005 for x in ratios),
            "slower": sum(x > 1.005 for x in ratios), "family": family}


def cluster_ci(workloads):
    tasks = sorted({w["task"] for w in workloads})
    groups = {t: [w for w in workloads if w["task"] == t] for t in tasks}
    rng = random.Random(20261012)
    vals = []
    for _ in range(10000):
        draw = [groups[tasks[rng.randrange(len(tasks))]] for _ in tasks]
        task_means = [statistics.mean(math.log(w["ratio"]) for w in group) for group in draw]
        vals.append(math.exp(statistics.mean(task_means)))
    vals.sort()
    return {"distinct_tasks": len(tasks), "task_cluster_bootstrap_95pct_ci_geometric_ratio": [vals[250], vals[9749]],
            "task_weighted_geometric_ratio": math.exp(statistics.mean(statistics.mean(math.log(w["ratio"]) for w in groups[t]) for t in tasks))}


def main():
    spec = read("preregistered_spec.json")
    if hashlib.sha256((OUT / "preregistered_spec.json").read_bytes()).hexdigest() != read("spec_hash.json")["sha256"]:
        raise RuntimeError("Preregistration changed")
    manifest = {r["workload_id"]: r for r in read("workload_manifest.json")["all_candidates"]}
    raw = list(rows("raw_timings.jsonl"))
    # The shipped product writes per-workbook ensure/backup timings into its
    # index manifest before returning an in-memory aggregate. The runner's
    # raw row therefore has null aggregate fields; derive them from the
    # archived manifest without modifying the invocation or primary endpoint.
    for r in raw:
        if r["arm"] != "TREATMENT":
            continue
        paths = list((ROOT / r["run_dir"] / "cache/librecalc-agent/runs").glob("*/index/manifest.json"))
        if len(paths) != 1:
            continue
        index_manifest = json.loads(paths[0].read_text())
        refreshes = index_manifest.get("refreshes", [])
        r["index_ensure_s"] = sum(x.get("ensure_s") or 0 for x in refreshes)
        r["index_backup_s"] = sum(x.get("backup_s") or 0 for x in refreshes)
        r["index_setup_s"] = r["index_ensure_s"] + r["index_backup_s"]
        r["index_rebuilt"] = sum(bool(x.get("rebuilt")) for x in refreshes)
        r["index_failures"] = len(index_manifest.get("failures", []))
    by = collections.defaultdict(list)
    for r in raw:
        by[(r["workload_id"], r["arm"])].append(r)
    chosen = sorted(set(spec["selected_eligible_ids"] + spec["selected_representative_ids"]))
    if set(k[0] for k in by) != set(chosen):
        raise RuntimeError("Missing selected workloads")
    workload_rows, semantic, contact, decomposition = [], [], [], []
    for ident in chosen:
        source = manifest[ident]
        control = sorted((r for r in by[(ident, "CONTROL")] if not r["warmup"]), key=lambda r: r["repetition"])
        treatment = sorted((r for r in by[(ident, "TREATMENT")] if not r["warmup"]), key=lambda r: r["repetition"])
        if len(control) != 3 or len(treatment) != 3:
            raise RuntimeError(f"Incomplete scored timings: {ident}")
        valid = all(r["exit_code"] == 0 and not r["timed_out"] and r["workbook_unchanged"] for r in control + treatment)
        output_pairs = [{"repetition": c["repetition"], "match": c["stdout_sha256"] == t["stdout_sha256"] and c["exit_code"] == t["exit_code"],
                         "control_stdout_sha256": c["stdout_sha256"], "treatment_stdout_sha256": t["stdout_sha256"]}
                        for c, t in zip(control, treatment)]
        sem = {"workload_id": ident, "task": source["task"], "valid_processes": valid,
               "all_scored_pairs_exact": valid and all(p["match"] for p in output_pairs),
               "output_pairs": output_pairs,
               "control_self_consistent": len({c["stdout_sha256"] for c in control}) == 1,
               "treatment_self_consistent": len({t["stdout_sha256"] for t in treatment}) == 1}
        semantic.append(sem)
        med_c, med_t = median([r["wall_ns"] / 1e9 for r in control]), median([r["wall_ns"] / 1e9 for r in treatment])
        row = {"workload_id": ident, "task": source["task"], "family": source["family"],
               "workbook_bytes": source["workbook_bytes"], "static_read_events": source["static_read_events"],
               "control_median_s": med_c, "treatment_median_s": med_t,
               "ratio": med_t / med_c, "reduction_pct": 100 * (1 - med_t / med_c),
               "eligible": ident in spec["selected_eligible_ids"],
               "representative": ident in spec["selected_representative_ids"],
               "semantic_exact": sem["all_scored_pairs_exact"],
               "control_raw_s": [r["wall_ns"] / 1e9 for r in control],
               "treatment_raw_s": [r["wall_ns"] / 1e9 for r in treatment]}
        workload_rows.append(row)
        contact.append({"workload_id": ident, "task": source["task"], "read_gate": sorted({r["read_gate"] for r in treatment if r["read_gate"]}),
                        "accelerated_loads_per_rep": [r["accelerated_loads"] for r in treatment],
                        "accelerated_events_per_rep": [r["accelerated_events"] for r in treatment],
                        "fallback_events_per_rep": [r["fallback_events"] for r in treatment],
                        "index_creations_per_rep": [r["index_rebuilt"] for r in treatment],
                        "index_failures_per_rep": [r["index_failures"] for r in treatment],
                        "contact": any(r["accelerated_events"] > 0 for r in treatment)})
        decomposition.append({"workload_id": ident, "control_total_median_s": med_c,
                              "treatment_total_median_s": med_t,
                              "treatment_index_setup_median_s": median([r["index_setup_s"] for r in treatment if r["index_setup_s"] is not None]),
                              "treatment_index_ensure_median_s": median([r["index_ensure_s"] for r in treatment if r["index_ensure_s"] is not None]),
                              "treatment_index_backup_median_s": median([r["index_backup_s"] for r in treatment if r["index_backup_s"] is not None]),
                              "treatment_accelerated_operation_median_s": median([r["accelerated_operation_ns"] / 1e9 for r in treatment]),
                              "treatment_fallback_operation_median_s": median([r["fallback_operation_ns"] / 1e9 for r in treatment]),
                              "unattributed_treatment_median_s": med_t - (median([r["index_setup_s"] for r in treatment if r["index_setup_s"] is not None]) or 0),
                              "note": "Unattributed residual includes startup, child work, capture, diagnostics and teardown; instrumented operation sums are nested and not additive."})
    put("workload_timings.json", workload_rows)
    put("semantic_replay_results.json", {"workloads": semantic, "exact_count": sum(x["all_scored_pairs_exact"] for x in semantic),
                                        "mismatch_count": sum(not x["all_scored_pairs_exact"] for x in semantic)})
    put("acceleration_contact.json", {"workloads": contact,
        "workload_contact_count": sum(x["contact"] for x in contact),
        "workload_contact_fraction": sum(x["contact"] for x in contact) / len(contact),
        "representative_contact_count": sum(x["contact"] and x["workload_id"] in spec["selected_representative_ids"] for x in contact),
        "eligible_contact_count": sum(x["contact"] and x["workload_id"] in spec["selected_eligible_ids"] for x in contact),
        "accelerated_events_scored_total": sum(sum(x["accelerated_events_per_rep"]) for x in contact),
        "accelerated_loads_scored_total": sum(sum(x["accelerated_loads_per_rep"]) for x in contact),
        "index_creations_scored_total": sum(sum(v or 0 for v in x["index_creations_per_rep"]) for x in contact),
        "index_failures_scored_total": sum(sum(v or 0 for v in x["index_failures_per_rep"]) for x in contact),
        "actual_cell_read_event_count": None,
        "observability_limit": "Packaged runtime records accelerated load_workbook contact, not every proxied cell or range read. Static read references are preserved per workload but are not dynamic event counts."})
    put("timing_decomposition.json", decomposition)
    # Keep every frozen workload in descriptive timing tables even on a mismatch.
    # The semantic guard then blocks a speed claim; it never drops a bad result.
    rep = [w for w in workload_rows if w["representative"]]
    elig = [w for w in workload_rows if w["eligible"]]
    rep_result = effects(rep)
    elig_result = effects(elig)
    rep_result["cluster_sensitivity"] = cluster_ci(rep) if rep else None
    elig_result["cluster_sensitivity"] = cluster_ci(elig) if elig else None
    rep_result["selected_n"] = len(spec["selected_representative_ids"])
    elig_result["selected_n"] = len(spec["selected_eligible_ids"])
    rep_result["contact_fraction"] = sum(w["representative"] and next(c["contact"] for c in contact if c["workload_id"] == w["workload_id"]) for w in workload_rows) / rep_result["selected_n"]
    put("representative_results.json", rep_result)
    put("eligible_results.json", elig_result)
    tail = [w for w in elig if w["workbook_bytes"] >= 1_000_000 and w["static_read_events"] >= 10]
    tail_result = effects(tail)
    setup = {d["workload_id"]: d["treatment_index_setup_median_s"] for d in decomposition}
    put("break_even_analysis.json", {"eligible_tail_predeclared": tail_result,
        "setup_vs_control": [{"workload_id": w["workload_id"], "workbook_bytes": w["workbook_bytes"],
            "static_read_events": w["static_read_events"], "control_s": w["control_median_s"],
            "setup_s": setup[w["workload_id"]], "setup_fraction_of_control": (setup[w["workload_id"]] or 0) / w["control_median_s"],
            "net_saving_s": w["control_median_s"] - w["treatment_median_s"]} for w in elig],
        "interpretation": "Actual gross read savings are not separately identifiable from the unchanged script; external net wall time includes all setup and overhead."})
    exact = (len(elig) == len(spec["selected_eligible_ids"])
             and len(rep) == len(spec["selected_representative_ids"])
             and all(w["semantic_exact"] for w in workload_rows))
    material = exact and elig_result["median_ratio"] <= 0.90 and elig_result["faster"] > elig_result["n"] / 2 and elig_result["bootstrap_95pct_ci_geometric_ratio"][1] < 1
    sorted_wins = sorted(elig, key=lambda w: w["reduction_pct"], reverse=True)
    leave_two = effects(sorted_wins[2:]) if len(sorted_wins) > 2 else {"median_ratio": None}
    material = material and leave_two["median_ratio"] < 1
    tail_support = exact and tail_result["n"] >= 3 and tail_result["median_ratio"] <= 0.90 and tail_result["faster"] > tail_result["n"] / 2 and tail_result["bootstrap_95pct_ci_geometric_ratio"][1] < 1
    contacted = any(c["contact"] for c in contact if c["workload_id"] in spec["selected_eligible_ids"])
    if not exact:
        verdict = "EXPERIMENT_INCONCLUSIVE"
    elif material:
        verdict = "RC_ACCELERATION_CLAIM_SUPPORTED"
    elif tail_support:
        verdict = "RC_ACCELERATION_SUPPORTED_NARROWLY"
    elif contacted and elig_result["median_ratio"] > 0.90:
        verdict = "RC_FASTPATH_ONLY_PRODUCT_SPEED_NOT_SUPPORTED"
    else:
        verdict = "NO_MATERIAL_RC_ACCELERATION"
    put("decision.json", {"primary_verdict": verdict, "semantic_exact": exact,
        "eligible_materiality_gate": material, "tail_support_gate": tail_support,
        "eligible_contact": contacted, "leave_two_largest_wins_out_median_ratio": leave_two["median_ratio"],
        "research_stop": True, "further_research_experiment_justified": False})
    print(json.dumps({"verdict": verdict, "eligible": elig_result, "representative": rep_result,
                      "semantic_exact_workloads": sum(x["all_scored_pairs_exact"] for x in semantic)}, indent=2))


if __name__ == "__main__":
    main()
