"""Paired Phase-5 architecture analysis of fixed 22 full-command rows."""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from read_engine_phase5.benchmark import HERE, ROOT, verify

SEED = 20261105


def median(values):
    return statistics.median(values)


def effects(pairs: list[tuple[float, float]], seed: int = SEED) -> dict:
    ratios = [a / b for a, b in pairs]
    rng = random.Random(seed)
    boot = sorted(median(rng.choices(ratios, k=len(ratios))) for _ in range(2000))
    return {"n": len(ratios), "median_ratio": median(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in ratios)),
            "bootstrap_median_95pct": [boot[49], boot[1949]],
            "range": [min(ratios), max(ratios)],
            "faster": sum(x < 1 for x in ratios), "slower": sum(x > 1 for x in ratios),
            "tied": sum(x == 1 for x in ratios)}


def rows(name: str) -> list[dict]:
    return [json.loads(s) for s in (HERE / name).read_text().splitlines() if s]


def analyze() -> tuple[dict, dict]:
    pop = verify()
    raw = [x for x in rows("raw_timings.jsonl") if x["phase"] == "scored"]
    correctness = [x for x in rows("raw_correctness.jsonl") if x.get("kind") == "script_triplet" and x["phase"] == "scored"]
    sessions = rows("session_timings.jsonl")
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    lookup = {(x["workload_id"], x["rep"], x["invocation"], x["arm"]): x for x in raw}
    if len(raw) != 22 * 3 * 5 * 3 or len(correctness) != 22 * 3 * 5 or len(sessions) != 22 * 3 * 4:
        raise RuntimeError("Incomplete scored ledgers")
    if not all(x["valid"] for x in correctness):
        raise RuntimeError("Scored semantic/reuse failure")
    per = {}
    for wid in pop["primary_ids"]:
        record = by_id[wid]
        obs = {"task": record["task"], "family": record["family"],
               "old_rc_ratio": record["old_rc_median_ratio"],
               "phase4_archived_warm_ratio": json.loads((ROOT / "read_engine_phase4/analysis.json").read_text())["per_workload"][wid]["warm"]["H1_PY"]}
        for regime, positions in (("cold", (1,)), ("warm", (2, 3, 4, 5))):
            arm_times = {}
            for arm in ("PY", "H0", "H1"):
                arm_times[arm] = median([median([lookup[(wid, rep, j, arm)]["wall_ns"] for j in positions])
                                         for rep in range(1, 4)])
            obs[regime] = {**{f"{a}_ns": t for a, t in arm_times.items()},
                           "H1_H0": arm_times["H1"] / arm_times["H0"],
                           "H1_PY": arm_times["H1"] / arm_times["PY"],
                           "H0_PY": arm_times["H0"] / arm_times["PY"]}
        rr0 = [lookup[(wid, rep, j, "H0")] for rep in range(1, 4) for j in range(2, 6)]
        rr1 = [lookup[(wid, rep, j, "H1")] for rep in range(1, 4) for j in range(2, 6)]
        def artifact(x):
            return next(iter(x["summary"]["artifacts"].values()))
        obs["artifact_bytes"] = median(artifact(x)["phases"]["artifact_bytes"] for x in rr1)
        obs["H0_parent_validation_ms"] = median(artifact(x)["phases"]["artifact_discovery_validation_ns"] for x in rr0) / 1e6
        obs["H1_parent_validation_ms"] = median(artifact(x)["phases"]["artifact_discovery_validation_ns"] for x in rr1) / 1e6
        obs["H1_semantic_load_confirmed"] = all(x["child_profile"]["times"]["artifact_load_ns"] > 0 for x in rr1)
        obs["H0_fallback_reasons"] = dict(Counter(y for x in rr0 for y in x["summary"]["reference_reasons"]))
        obs["H1_fallback_reasons"] = dict(Counter(y for x in rr1 for y in x["summary"]["reference_reasons"]))
        obs["H0_warm_statuses"] = dict(Counter(artifact(x)["status"] for x in rr0))
        obs["H1_warm_statuses"] = dict(Counter(artifact(x)["status"] for x in rr1))
        obs["warm_signed_excess_ms"] = (obs["warm"]["H1_ns"] - obs["warm"]["PY_ns"]) / 1e6
        obs["warm_optimization_saved_ms"] = (obs["warm"]["H0_ns"] - obs["warm"]["H1_ns"]) / 1e6
        per[wid] = obs

    aggregates = {}
    for regime in ("cold", "warm"):
        aggregates[regime] = {}
        for num, den in (("H1", "H0"), ("H1", "PY"), ("H0", "PY")):
            aggregates[regime][f"{num}_{den}"] = effects([
                (per[wid][regime][f"{num}_ns"], per[wid][regime][f"{den}_ns"])
                for wid in pop["primary_ids"]])
    sess_lookup = {(x["workload_id"], x["rep"], x["N"]): x for x in sessions}
    aggregates["session"] = {}
    for N in (1, 2, 3, 5):
        times = {wid: {arm: median(sess_lookup[(wid, rep, N)][f"{arm}_ns"] for rep in range(1, 4))
                       for arm in ("PY", "H0", "H1")} for wid in pop["primary_ids"]}
        aggregates["session"][str(N)] = {
            f"{num}_{den}": effects([(times[wid][num], times[wid][den]) for wid in pop["primary_ids"]])
            for num, den in (("H1", "H0"), ("H1", "PY"), ("H0", "PY"))}

    # Task clusters are sensitivity analysis, not a new decision population.
    task_ratios = defaultdict(list)
    for wid in pop["primary_ids"]:
        task_ratios[per[wid]["task"]].append(per[wid]["warm"]["H1_PY"])
    task_values = [math.exp(statistics.mean(math.log(x) for x in values)) for values in task_ratios.values()]
    warm = aggregates["warm"]["H1_PY"]
    warm_supported = (warm["median_ratio"] < 1 and warm["faster"] > 11 and warm["bootstrap_median_95pct"][1] < 1)
    cold = aggregates["cold"]["H1_PY"]
    cold_supported = cold["median_ratio"] < 1 and cold["faster"] > 11 and cold["bootstrap_median_95pct"][1] < 1
    analysis = {"population": {"scripts": 22, "tasks": len(task_values), "scored_invocations": len(raw),
                               "correctness_rows": len(correctness)},
                "per_workload": per, "aggregate": aggregates,
                "warm_task_cluster": effects([(x, 1) for x in task_values]),
                "warm_signed_excess_ms": {"median": median([x["warm_signed_excess_ms"] for x in per.values()]),
                                          "range": [min(x["warm_signed_excess_ms"] for x in per.values()),
                                                    max(x["warm_signed_excess_ms"] for x in per.values())]},
                "crossed_break_even": [wid for wid, x in per.items() if x["warm"]["H0_PY"] >= 1 and x["warm"]["H1_PY"] < 1],
                "decisions": {"WARM_PRODUCT_SHAPED_SPEED": "SUPPORTED" if warm_supported else "NOT SUPPORTED",
                              "COLD_PRODUCT_SHAPED_SPEED": "SUPPORTED" if cold_supported else "NOT SUPPORTED"},
                "limits": ["OS cache uncontrolled", "22 scripts represent 14 tasks", "offline product-shaped harness, not public RC"]}
    profile = {"warm_components_ms": {}, "cold_components_ms": {}}
    for regime, positions, key in (("warm", (2, 3, 4, 5), "warm_components_ms"), ("cold", (1,), "cold_components_ms")):
        for arm in ("H0", "H1"):
            local = defaultdict(list)
            for wid in pop["primary_ids"]:
                rows_for_workload = [lookup[(wid, rep, j, arm)] for rep in range(1, 4) for j in positions]
                per_comp = defaultdict(list)
                for row in rows_for_workload:
                    p = row["parent_profile"]
                    c = row["child_profile"]
                    a = next(iter(row["summary"]["artifacts"].values()))
                    for name in ("parent_total_ns", "pre_capture_ns", "post_capture_delta_validation_ns"):
                        per_comp[name].append(p[name] / 1e6)
                    if arm == "H0":
                        per_comp["child_wall_ns"].append(p["child_wall_ns"] / 1e6)
                    else:
                        per_comp["script_wall_ns"].append(p["script_wall_ns"] / 1e6)
                        per_comp["runtime_install_ns"].append(p["runtime_install_ns"] / 1e6)
                    per_comp["external_parent_residual_ns"].append((row["wall_ns"] - p["parent_total_ns"]) / 1e6)
                    for name in ("artifact_discovery_validation_ns", "sidecar_header_ns", "artifact_read_ns", "artifact_hash_ns", "builder_import_ns", "direct_decode_ns", "serialization_ns", "publication_ns"):
                        if isinstance(a["phases"].get(name), (int, float)):
                            per_comp[name].append(a["phases"][name] / 1e6)
                    for name in ("module_import_to_run_ns", "rc_import_ns"):
                        if name in p:
                            per_comp[name].append(p[name] / 1e6)
                    per_comp["runtime_bootstrap_ns"].append(c["bootstrap_ns"] / 1e6)
                    per_comp["runtime_artifact_load_ns"].append(c["times"]["artifact_load_ns"] / 1e6)
                    per_comp["runtime_reference_parse_ns"].append(c["times"]["reference_parse_ns"] / 1e6)
                for name, values in per_comp.items():
                    local[name].append(median(values))
            profile[key][arm] = {name.replace("_ns", "_ms"): {"median": median(v), "range": [min(v), max(v)]}
                                 for name, v in local.items()}
    return analysis, profile


def main() -> None:
    analysis, profile = analyze()
    (HERE / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    (HERE / "profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
