"""Paired descriptive analysis of the preregistered Phase-10 ledgers."""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEED = 20260928


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text().splitlines() if line]


def interval(values: list[float]) -> list[float]:
    if not values:
        return []
    rng = random.Random(SEED + len(values))
    draws = [statistics.median(rng.choices(values, k=len(values))) for _ in range(5000)]
    draws.sort()
    return [draws[124], draws[4874]]


def describe(items: list[tuple[str, float, float]]) -> dict:
    by_id: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for wid, numerator, denominator in items:
        if numerator <= 0 or denominator <= 0:
            raise ValueError("nonpositive wall in paired timing")
        by_id[wid].append((numerator / denominator, (numerator - denominator) / 1e6))
    ratios = {wid: statistics.median(x[0] for x in vals) for wid, vals in by_id.items()}
    signed = {wid: statistics.median(x[1] for x in vals) for wid, vals in by_id.items()}
    values = list(ratios.values())
    return {"count": len(values), "median_ratio": statistics.median(values),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in values)),
            "bootstrap_median_interval_95": interval(values),
            "range": [min(values), max(values)],
            "faster": sum(x < 1 for x in values), "slower": sum(x > 1 for x in values),
            "tied": sum(x == 1 for x in values),
            "median_signed_excess_ms": statistics.median(signed.values()),
            "per_workload_ratio": ratios, "per_workload_signed_excess_ms": signed}


def main() -> None:
    timing = rows("raw_timings.jsonl")
    correctness = rows("correctness.jsonl")
    sessions = rows("session_timings.jsonl")
    population = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    by_id = {x["workload_id"]: x for x in population["workloads"]}
    assert len(correctness) == len({(x["population"], x["workload_id"], x["rep"], x["invocation"])
                                    for x in timing})
    assert all(x["valid"] for x in correctness)
    keyed = {(x["population"], x["workload_id"], x["rep"], x["invocation"], x["arm"]): x
             for x in timing}
    assert len(keyed) == len(timing)
    route = {}
    for wid in population["secondary_ids"]:
        candidates = [x["route"] for x in timing if x["population"] == "representative30"
                      and x["workload_id"] == wid and x["arm"] == "PROD"]
        assert len(set(candidates)) == 1, (wid, candidates)
        route[wid] = candidates[0]
    groups = {
        "all30": population["secondary_ids"],
        "reference_only": [wid for wid in population["secondary_ids"]
                           if route[wid] == "REFERENCE_ONLY"],
        "direct_contact": [wid for wid in population["secondary_ids"]
                           if route[wid] == "DIRECT_CONTACT"],
        "fallback_after_contact": [wid for wid in population["secondary_ids"]
                                   if route[wid] == "FALLBACK_AFTER_CONTACT"],
        "fixed22": population["primary_ids"],
    }
    result = {"status": "ALL_SCORED_CORRECTNESS_GATES_PASS",
              "correctness_rows": len(correctness), "timing_rows": len(timing),
              "session_rows": len(sessions), "route_by_workload": route,
              "route_counts": {name: len(ids) for name, ids in groups.items()},
              "populations": {}, "sessions": {}, "changed_file": {},
              "per_task_sensitivity": {}}
    for name, ids in groups.items():
        label = "fixed22" if name == "fixed22" else "representative30"
        subset = set(ids)
        result["populations"][name] = {}
        for endpoint, invocation in (("cold", 1), ("second", 2)):
            result["populations"][name][endpoint] = {}
            for numerator, denominator in (("PROD", "PY"), ("PROD", "EXP"), ("EXP", "PY")):
                matched = []
                for key, row in keyed.items():
                    pop, wid, rep, inv, arm = key
                    if pop != label or wid not in subset or inv != invocation or arm != numerator:
                        continue
                    other = keyed[(pop, wid, rep, inv, denominator)]
                    matched.append((wid, row["wall_ns"], other["wall_ns"]))
                result["populations"][name][endpoint][f"{numerator}_{denominator}"] = describe(matched)
        if name == "all30":
            task_groups = defaultdict(list)
            for wid in ids:
                task_groups[by_id[wid]["task"]].append(wid)
            for task, task_ids in task_groups.items():
                vals = [result["populations"][name]["second"]["PROD_PY"]
                        ["per_workload_ratio"][wid] for wid in task_ids]
                result["per_task_sensitivity"][task] = statistics.median(vals)
    changed_ids = sorted({x["workload_id"] for x in timing if x["population"] == "changed5"})
    for numerator, denominator in (("PROD", "PY"), ("PROD", "EXP")):
        matched = [(wid,
                    keyed[("changed5", wid, 1, 1, numerator)]["wall_ns"],
                    keyed[("changed5", wid, 1, 1, denominator)]["wall_ns"])
                   for wid in changed_ids]
        result["changed_file"][f"{numerator}_{denominator}"] = describe(matched)
    for n in (1, 2, 3, 5):
        chosen = [x for x in sessions if x["n"] == n]
        assert len(chosen) == 30
        result["sessions"][str(n)] = {}
        for name, ids in groups.items():
            if name == "fixed22":
                continue
            subset = set(ids)
            result["sessions"][str(n)][name] = {}
            for numerator, denominator in (("PROD", "PY"), ("PROD", "EXP")):
                matched = [(x["workload_id"], x["sum_ns"][numerator],
                            x["sum_ns"][denominator]) for x in chosen
                           if x["workload_id"] in subset]
                result["sessions"][str(n)][name][f"{numerator}_{denominator}"] = describe(matched)
    (HERE / "analysis.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    brief = {"rows": (len(timing), len(correctness), len(sessions)),
             "routes": result["route_counts"],
             "reference_second": result["populations"]["reference_only"]["second"]["PROD_PY"],
             "direct_second": result["populations"]["direct_contact"]["second"]["PROD_PY"],
             "all_second": result["populations"]["all30"]["second"]["PROD_PY"]}
    for key in ("reference_second", "direct_second", "all_second"):
        brief[key] = {k: v for k, v in brief[key].items() if not k.startswith("per_workload")}
    print(json.dumps(brief, indent=2))


if __name__ == "__main__":
    main()
