"""Paired full-command analysis for the normalized Phase-10B ledgers."""
from __future__ import annotations

import collections
import json
import math
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20260928
MAIN_PAIRS = (("P4", "P0"), ("P1", "P0"), ("P2", "P1"),
              ("P3", "P2"), ("P4", "P3"))
SUPPLEMENT_PAIRS = (("S1", "S0"), ("S2", "S1"), ("S3", "S2"), ("S3", "S0"))
P5_PAIRS = (("P4", "PY_OLD"), ("P5", "PY_NEW"), ("P5", "P4"),
            ("PY_NEW", "PY_OLD"))


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text().splitlines() if line]


def interval(values: list[float], seed: int) -> list[float]:
    rng = random.Random(seed)
    stats = sorted(statistics.median(rng.choices(values, k=len(values)))
                   for _ in range(5000))
    return [stats[124], stats[4874]]


def dataset(name: str, pairs: tuple[tuple[str, str], ...], pop: dict) -> dict:
    rows = load(name)
    by = {(x["workload_id"], x["rep"], x["invocation"], x["arm"]):
          x["wall_ns"] / 1e6 for x in rows}
    ids = pop["ids"]
    assert len(rows) == len(ids) * 2 * 2 * len({arm for pair in pairs for arm in pair})
    result = {"rows": len(rows), "pairs": {}, "per_workload": {}}
    for b, a in pairs:
        label = f"{b}_minus_{a}"
        values, ratios = [], []
        per = {}
        for wid in ids:
            deltas = [by[(wid, rep, 2, b)] - by[(wid, rep, 2, a)]
                      for rep in (1, 2)]
            repeats = [by[(wid, rep, 2, b)] / by[(wid, rep, 2, a)]
                       for rep in (1, 2)]
            d, r = statistics.median(deltas), statistics.median(repeats)
            values.append(d); ratios.append(r)
            per[wid] = {"paired_signed_ms": d, "paired_ratio": r,
                        "repetition_signed_ms": deltas,
                        "repetition_ratios": repeats}
            result["per_workload"].setdefault(wid, {})[label] = per[wid]
        task_groups = collections.defaultdict(list)
        for row in pop["workloads"]:
            task_groups[f"{row['family']}:{row['task']}"].append(per[row["workload_id"]]["paired_signed_ms"])
        task_values = [statistics.median(group) for group in task_groups.values()]
        result["pairs"][label] = {
            "count": len(values), "median_signed_ms": statistics.median(values),
            "signed_interval_95": interval(values, SEED ^ len(label)),
            "signed_range_ms": [min(values), max(values)],
            "median_paired_ratio": statistics.median(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in ratios)),
            "ratio_interval_95": interval(ratios, SEED ^ len(label) ^ 0x55),
            "ratio_range": [min(ratios), max(ratios)],
            "faster": sum(x < 0 for x in values),
            "slower": sum(x > 0 for x in values),
            "tied": sum(x == 0 for x in values),
            "task_cluster_count": len(task_groups),
            "task_collapsed_median_signed_ms": statistics.median(task_values),
            "task_collapsed_signed_interval_95": interval(task_values, SEED ^ len(label) ^ 0xAA),
        }
    return result


def main() -> None:
    pop = json.loads((HERE / "population.json").read_text())
    main = dataset("raw_timings.jsonl", MAIN_PAIRS, pop)
    supplement = dataset("supplement_raw_timings.jsonl", SUPPLEMENT_PAIRS, pop)
    p5 = dataset("p5_raw_timings.jsonl", P5_PAIRS, pop)
    main_correctness = load("correctness.jsonl")
    supplement_correctness = load("supplement_correctness.jsonl")
    p5_correctness = load("p5_correctness.jsonl")
    assert len(main_correctness) == len(supplement_correctness) == 88
    assert len(p5_correctness) == 88
    assert all(x["valid"] for x in main_correctness + supplement_correctness + p5_correctness)
    control = {(x["workload_id"], x["rep"]): x["wall_ns"] / 1e6
               for x in load("raw_timings.jsonl")
               if x["arm"] == "P0" and x["invocation"] == 2}
    short = [wid for wid in pop["ids"] if statistics.median(
        control[(wid, rep)] for rep in (1, 2)) < 500]
    diagnostics = {}
    for name, data in (("main", main), ("supplement", supplement)):
        diagnostics[name] = {pair: {
            "median_signed_ms": statistics.median(data["per_workload"][wid][pair]["paired_signed_ms"]
                                                    for wid in short),
            "faster": sum(data["per_workload"][wid][pair]["paired_signed_ms"] < 0
                          for wid in short),
            "slower": sum(data["per_workload"][wid][pair]["paired_signed_ms"] > 0
                          for wid in short),
        } for pair in data["pairs"]}
    p5_raw = load("p5_raw_timings.jsonl")
    p5_walls = {(x["workload_id"], x["rep"], x["arm"]): x["wall_ns"] / 1e6
                for x in p5_raw if x["invocation"] == 2}
    main_spread = {}
    p5_spread = {}
    adjusted = []
    for wid in pop["ids"]:
        main_pair = [control[(wid, rep)] for rep in (1, 2)]
        p5_pair = [p5_walls[(wid, rep, "PY_OLD")] for rep in (1, 2)]
        main_spread[wid] = abs(main_pair[0] - main_pair[1]) / min(main_pair)
        p5_spread[wid] = abs(p5_pair[0] - p5_pair[1]) / min(p5_pair)
        adjusted.append(statistics.median(
            (p5_walls[(wid, rep, "P5")] - p5_walls[(wid, rep, "PY_NEW")])
            - (p5_walls[(wid, rep, "P4")] - p5_walls[(wid, rep, "PY_OLD")])
            for rep in (1, 2)))
    unstable_main = {wid: val for wid, val in main_spread.items() if val > .25}
    unstable_p5 = {wid: val for wid, val in p5_spread.items() if val > .25}
    reliability_passed = len(unstable_main) <= 3 and len(unstable_p5) <= 3
    result = {"population_count": 22, "main": main, "supplement": supplement,
              "p5": p5,
              "main_correctness_valid": len(main_correctness),
              "supplement_correctness_valid": len(supplement_correctness),
              "p5_correctness_valid": len(p5_correctness),
              "affinity_cpu": 1,
              "reliability": {"passed": reliability_passed,
                              "main_control_over_25_percent": unstable_main,
                              "p5_control_over_25_percent": unstable_p5},
              "p5_adjusted_difference_in_differences": {
                  "median_signed_ms": statistics.median(adjusted),
                  "signed_interval_95": interval(adjusted, SEED ^ 0xB5),
                  "faster": sum(x < 0 for x in adjusted),
                  "slower": sum(x > 0 for x in adjusted)},
              "diagnostic_short_control_under_500ms": {"count": len(short),
                                                          "ids": short,
                                                          "effects": diagnostics},
              "budget_ms": 10,
              "budget_met_on_replication": reliability_passed and main["pairs"]["P4_minus_P0"]["median_signed_ms"] <= 10,
              "tax_replicated": reliability_passed and main["pairs"]["P4_minus_P0"]["median_signed_ms"] > 10,
              "p5_budget_met": reliability_passed and p5["pairs"]["P5_minus_PY_NEW"]["median_signed_ms"] <= 10,
              "p5_effect_median_ms": p5["pairs"]["P5_minus_P4"]["median_signed_ms"],
              "p5_reason": "Bounded lexical-negative shortcut covers 20/22 reference-only scripts; pinned same-run effect is reported separately from the unchanged PROD budget replication."}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"tax_ms": result["main"]["pairs"]["P4_minus_P0"]["median_signed_ms"],
                      "budget_met_on_replication": result["budget_met_on_replication"],
                      "p5_budget_met": result["p5_budget_met"],
                      "reliability_passed": reliability_passed}))


if __name__ == "__main__":
    main()
