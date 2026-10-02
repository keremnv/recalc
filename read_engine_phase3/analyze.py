"""Paired full-boundary analysis; preserves primary and secondary views."""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SEED = 20261011


def rows(filename: str) -> list[dict]:
    return [json.loads(s) for s in (HERE / filename).read_text().splitlines() if s]


def med(values):
    return statistics.median(values) if values else None


def effects(pairs: list[tuple[float, float]], seed=SEED) -> dict:
    ratios = [a / b for a, b in pairs if a > 0 and b > 0]
    if not ratios:
        return {"n": 0}
    rng = random.Random(seed)
    boot_med = sorted(statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(2000))
    boot_geo = sorted(math.exp(statistics.mean(math.log(x) for x in rng.choices(ratios, k=len(ratios)))) for _ in range(2000))
    return {"n": len(ratios), "median_ratio": med(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in ratios)),
            "median_bootstrap_95pct": [boot_med[49], boot_med[1949]],
            "geometric_bootstrap_95pct": [boot_geo[49], boot_geo[1949]],
            "min_ratio": min(ratios), "max_ratio": max(ratios),
            "faster": sum(x < 1 for x in ratios), "slower": sum(x > 1 for x in ratios),
            "tied": sum(x == 1 for x in ratios), "ratios": ratios}


def old_artifact_bytes(wid: str) -> int | None:
    base = ROOT / "research/history/rc_acceleration_validation/runs" / f"{wid}__TREATMENT__score_1/cache/librecalc-agent/runs"
    paths = list(base.glob("*/index/*.sqlite"))
    return sum(p.stat().st_size for p in paths) if paths else None


def analyze() -> dict:
    pop = json.loads((HERE / "population.json").read_text())
    raw = rows("raw_timings.jsonl")
    correct = rows("raw_correctness.jsonl")
    session = rows("session_timings.jsonl")
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    scored = [x for x in raw if x["phase"] == "scored"]
    paired = {(x["view"], x["workload_id"], x["rep"], x["invocation"], x["arm"]): x for x in scored}
    sess = {(x["view"], x["workload_id"], x["rep"], x["N"]): x for x in session}
    output = {"identities": {}, "primary": {}, "secondary": {}, "per_workload": {},
              "component_profile": {}, "fallback": {}, "old_vs_new_setup": {},
              "decisions": {}, "limits": {"trace_independence": "22 scripts from 14 primary tasks; 30 scripts from 21 secondary tasks",
                                        "cache": "OS page cache uncontrolled", "product": "offline product-shaped harness, not RC"}}
    for view, ids, reps, last in (("PRIMARY", pop["primary_ids"], 3, 5),
                                  ("SECONDARY", pop["secondary_ids"], 2, 2)):
        for wid in ids:
            for rep in range(1, reps + 1):
                for j in range(1, last + 1):
                    for arm in ("CONTROL", "TREATMENT"):
                        if (view, wid, rep, j, arm) not in paired:
                            raise ValueError(f"Missing scored invocation {view} {wid} {rep} {j} {arm}")
                for N in ((1, 2, 3, 5) if view == "PRIMARY" else (1, 2)):
                    if (view, wid, rep, N) not in sess:
                        raise ValueError(f"Missing session row {view} {wid} {rep} {N}")
        view_effects = {}
        per = {}
        for wid in ids:
            record = by_id[wid]
            obs = {}
            for regime, positions in (("cold", (1,)), ("warm", tuple(range(2, last + 1)))):
                arm_medians = {}
                for arm in ("CONTROL", "TREATMENT"):
                    arm_medians[arm] = med([med([paired[(view, wid, rep, j, arm)]["wall_ns"]
                                                     for j in positions]) for rep in range(1, reps + 1)])
                obs[regime] = {"control_ns": arm_medians["CONTROL"],
                               "treatment_ns": arm_medians["TREATMENT"],
                               "ratio": arm_medians["TREATMENT"] / arm_medians["CONTROL"]}
            obs["session"] = {}
            for N in ((1, 2, 3, 5) if view == "PRIMARY" else (1, 2)):
                c = med([sess[(view, wid, rep, N)]["control_ns"] for rep in range(1, reps + 1)])
                t = med([sess[(view, wid, rep, N)]["treatment_ns"] for rep in range(1, reps + 1)])
                obs["session"][str(N)] = {"control_ns": c, "treatment_ns": t, "ratio": t / c}
            treated = [paired[(view, wid, rep, j, "TREATMENT")] for rep in range(1, reps + 1) for j in range(1, last + 1)]
            comparisons = [x for x in correct if x.get("kind") == "script_pair" and x.get("view") == view
                           and x.get("phase") == "scored" and x.get("workload_id") == wid]
            if len(comparisons) != reps * last:
                raise ValueError(f"Incomplete semantic rows {view} {wid}")
            cold_artifacts = [x["summary"]["artifacts"] for x in treated if x["invocation"] == 1 and x["summary"]]
            warm_artifacts = [x["summary"]["artifacts"] for x in treated if x["invocation"] > 1 and x["summary"]]
            obs.update({"task": record["task"], "family": record["family"],
                        "old_rc_ratio": record["old_rc_median_ratio"],
                        "old_semantic_status": record["old_semantic_status"],
                        "new_semantic_counts": dict(Counter(x["classification"] for x in comparisons)),
                        "admitted_count": sum(bool(x["summary"] and x["summary"]["admitted"]) for x in treated),
                        "contact_count": sum(bool(x["summary"] and x["summary"]["direct_served_loads"]) for x in treated),
                        "cold_artifact_statuses": [sorted({a["status"] for a in entry.values()}) for entry in cold_artifacts],
                        "warm_artifact_statuses": [sorted({a["status"] for a in entry.values()}) for entry in warm_artifacts],
                        "reference_fallback_count": sum(x["summary"]["reference_loads"] or 0 for x in treated if x["summary"]),
                        "reference_fallback_reasons": dict(Counter(reason for x in treated if x["summary"] for reason in x["summary"]["reference_reasons"])),
                        "artifact_bytes": med([a["phases"]["artifact_bytes"] for entry in cold_artifacts for a in entry.values() if a.get("phases") and a["phases"].get("artifact_bytes")]),
                        "old_artifact_bytes": old_artifact_bytes(wid),
                        "old_rc_index_setup_median_s": record["old_rc_index_setup_median_s"]})
            per[wid] = obs
            output["per_workload"][f"{view}:{wid}"] = obs
        for regime in ("cold", "warm"):
            view_effects[regime] = effects([(per[wid][regime]["treatment_ns"], per[wid][regime]["control_ns"]) for wid in ids])
        view_effects["session"] = {}
        for N in ((1, 2, 3, 5) if view == "PRIMARY" else (1, 2)):
            view_effects["session"][str(N)] = effects([(per[wid]["session"][str(N)]["treatment_ns"],
                                                         per[wid]["session"][str(N)]["control_ns"]) for wid in ids])
        # Cluster sensitivity: one equal-weight ratio per distinct task.
        task_ratios = defaultdict(list)
        for wid in ids:
            task_ratios[per[wid]["task"]].append(per[wid]["warm"]["ratio"])
        task_values = [math.exp(statistics.mean(math.log(v) for v in z)) for z in task_ratios.values()]
        view_effects["warm_task_cluster"] = effects([(v, 1) for v in task_values])
        view_effects["distinct_tasks"] = len(task_ratios)
        view_effects["semantic_counts"] = dict(Counter(x["classification"] for x in correct
                                                      if x.get("kind") == "script_pair" and x.get("view") == view and x.get("phase") == "scored"))
        view_effects["admitted_workloads"] = sum(any(per[wid]["admitted_count"] for _ in [0]) for wid in ids)
        view_effects["contacted_workloads"] = sum(per[wid]["contact_count"] > 0 for wid in ids)
        view_effects["built_workloads"] = sum(any("BUILT" in statuses for statuses in per[wid]["cold_artifact_statuses"]) for wid in ids)
        view_effects["reused_workloads"] = sum(any("REUSED" in statuses for statuses in per[wid]["warm_artifact_statuses"]) for wid in ids)
        view_effects["fallback_workloads"] = sum(per[wid]["reference_fallback_count"] > 0 for wid in ids)
        output["primary" if view == "PRIMARY" else "secondary"] = view_effects
    # Coarse, per-workload medians so repeated invocations of one task do not dominate components.
    for regime, predicate in (("cold", lambda x: x["invocation"] == 1),
                              ("warm", lambda x: x["invocation"] > 1)):
        components = defaultdict(lambda: defaultdict(list))
        for wid in pop["primary_ids"]:
            rr = [x for x in scored if x["view"] == "PRIMARY" and x["workload_id"] == wid
                  and x["arm"] == "TREATMENT" and predicate(x)]
            local = defaultdict(list)
            for r in rr:
                p, child = r["parent_profile"] or {}, r["child_profile"] or {}
                for key in ("config_preflight_run_dir_ns", "admission_ns", "discovery_ns", "pre_capture_ns",
                            "child_wall_ns", "post_capture_delta_validation_ns", "diagnostic_read_ns",
                            "diagnostic_write_ns", "parent_total_ns"):
                    if isinstance(p.get(key), (int, float)):
                        local[key].append(p[key] / 1e6)
                for key, value in p.get("capture_sections_s", {}).items():
                    if isinstance(value, (int, float)):
                        local[f"capture_{key}_ms"].append(value * 1000)
                for entry in (r["summary"] or {}).get("artifacts", {}).values():
                    for key in ("source_hash_ns", "ensure_ns"):
                        if isinstance(entry.get(key), (int, float)):
                            local[key].append(entry[key] / 1e6)
                    for key in ("artifact_discovery_validation_ns", "direct_decode_ns",
                                "serialization_ns", "publication_ns"):
                        if isinstance(entry.get("phases", {}).get(key), (int, float)):
                            local[key].append(entry["phases"][key] / 1e6)
                for key in ("bootstrap_ns", "post_bootstrap_to_exit_ns"):
                    if isinstance(child.get(key), (int, float)):
                        local[key].append(child[key] / 1e6)
                for key in ("artifact_load_ns", "reference_parse_ns", "child_source_hash_ns"):
                    if isinstance(child.get("times", {}).get(key), (int, float)):
                        local[key].append(child["times"][key] / 1e6)
                if p and child:
                    local["child_startup_residual_ns"].append((p["child_wall_ns"] - child["bootstrap_ns"] - child["post_bootstrap_to_exit_ns"]) / 1e6)
            for key, vals in local.items():
                components[key]["workload_medians"].append(med(vals))
        output["component_profile"][regime] = {key.replace("_ns", "_ms"): {"workload_median_ms": med(v["workload_medians"]),
                                                                            "workloads": len(v["workload_medians"])}
                                                for key, v in components.items()}
    primary_scored = [x for x in scored if x["view"] == "PRIMARY" and x["arm"] == "TREATMENT"]
    output["fallback"] = {"primary_reason_counts": dict(Counter(reason for x in primary_scored if x["summary"]
                                                                   for reason in x["summary"]["reference_reasons"])),
                          "cold_built_plus_reference_parse": sum(x["invocation"] == 1 and x["summary"] and
                                                                  any(a["status"] == "BUILT" for a in x["summary"]["artifacts"].values())
                                                                  and (x["summary"]["reference_loads"] or 0) > 0 for x in primary_scored),
                          "warm_reused_plus_reference_parse": sum(x["invocation"] > 1 and x["summary"] and
                                                                   any(a["status"] == "REUSED" for a in x["summary"]["artifacts"].values())
                                                                   and (x["summary"]["reference_loads"] or 0) > 0 for x in primary_scored),
                          "primary_scored_invocations": len(primary_scored)}
    output["old_vs_new_setup"] = {wid: {"old_index_setup_s": output["per_workload"][f"PRIMARY:{wid}"]["old_rc_index_setup_median_s"],
                                           "old_artifact_bytes": output["per_workload"][f"PRIMARY:{wid}"]["old_artifact_bytes"],
                                           "new_artifact_bytes": output["per_workload"][f"PRIMARY:{wid}"]["artifact_bytes"]}
                                  for wid in pop["primary_ids"]}
    exact_primary = output["primary"]["semantic_counts"].get("EXACT", 0) == 330
    def favorable(x):
        return x["median_ratio"] < 1 and x["faster"] > 11 and x["median_bootstrap_95pct"][1] < 1
    cold = favorable(output["primary"]["cold"]) if exact_primary else False
    warm = favorable(output["primary"]["warm"]) if exact_primary and output["primary"]["reused_workloads"] == 22 else False
    session_good = any(favorable(output["primary"]["session"][str(N)]) for N in (2, 3, 5)) if exact_primary else False
    output["decisions"] = {"READ_ENGINE_SEMANTICS": "SUPPORTED" if exact_primary else "NOT SUPPORTED",
                           "COLD_PRODUCT_SHAPED_SPEED": "SUPPORTED" if cold else "NOT SUPPORTED",
                           "WARM_PRODUCT_SHAPED_SPEED": "SUPPORTED" if warm else "NOT SUPPORTED",
                           "INTEGRATION_CANDIDATE": "EARNED" if exact_primary and (cold or warm or session_good) else "NOT EARNED"}
    output["identities"] = {"primary_scripts": len(pop["primary_ids"]), "secondary_scripts": len(pop["secondary_ids"]),
                            "primary_tasks": output["primary"]["distinct_tasks"],
                            "secondary_tasks": output["secondary"]["distinct_tasks"],
                            "scored_invocations": len(scored), "semantic_rows": len(correct),
                            "session_rows": len(session)}
    return output


if __name__ == "__main__":
    result = analyze()
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("wrote analysis.json")
