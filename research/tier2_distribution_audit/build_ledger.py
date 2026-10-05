#!/usr/bin/env python3
"""Tier 2 distribution audit: reconstruct the frozen R3 representative-30
ledger from primary evidence and compute post-hoc descriptive statistics.

Reads (frozen, never modified):
  research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl
  research/full_cell_iteration_probe/TARGET_WORKLOADS.json
  research/full_cell_iteration_product_confirmation/_staging/parity_r3.jsonl

Writes (derived):
  research/tier2_distribution_audit/tier2_workloads.json
  research/tier2_distribution_audit/tier2_workloads.csv
  research/tier2_distribution_audit/tier2_summary.json

Historical reducer (preserved exactly): per-workload median of 3 warm reps,
then sum across the 30 workloads. Historical comparison: OFF (rc3-equivalent
predecessor control) -> ON (iteration candidate). BASE (bare openpyxl) is
carried as a secondary comparator only.
"""

import csv
import json
import math
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
R3 = REPO / "research/full_cell_iteration_product_confirmation"
OUT = REPO / "research/tier2_distribution_audit"


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def first_mode(values):
    """Most common value; ties broken by first occurrence (deterministic)."""
    counts = {}
    for v in values:
        key = json.dumps(v, sort_keys=True)
        counts[key] = counts.get(key, 0) + 1
    best = max(counts.values())
    for v in values:
        if counts[json.dumps(v, sort_keys=True)] == best:
            return v
    raise AssertionError("unreachable")


def main():
    rep_rows = load_jsonl(R3 / "REPRESENTATIVE_RESULTS.jsonl")
    assert len(rep_rows) == 30, f"expected 30 representative rows, got {len(rep_rows)}"
    targets_doc = json.loads((REPO / "research/full_cell_iteration_probe/TARGET_WORKLOADS.json").read_text())
    targets = set(targets_doc["workloads"])
    admitted = set(targets_doc["admitted"])
    blocked_other = {e["workload"] for e in targets_doc["other_blocked"]}
    assert len(targets) == 13 and len(admitted) == 8 and len(blocked_other) == 9
    parity_rows = load_jsonl(R3 / "_staging/parity_r3.jsonl")
    parity_a = {r["workload"]: r["parity"] for r in parity_rows if r["population"] == "A"}
    assert len(parity_a) == 30 and all(parity_a.values()), "R3 Population A parity must be 30/30 true"

    ledger = []
    for r in rep_rows:
        wid = r["workload"]
        arms = r["arms"]
        base_reps = list(arms["BASE"]["wall_s"])
        off_reps = list(arms["OFF"]["wall_s"])
        on_reps = list(arms["ON"]["wall_s"])
        assert len(base_reps) == len(off_reps) == len(on_reps) == 3, wid
        base_med = statistics.median(base_reps)
        off_med = statistics.median(off_reps)
        on_med = statistics.median(on_reps)
        off_routes = list(arms["OFF"]["routes"])
        on_routes = list(arms["ON"]["routes"])
        on_counts = list(arms["ON"]["counts"])
        on_art = list(arms["ON"]["artifact_status"])
        off_exits = list(arms["OFF"]["exits"])
        on_exits = list(arms["ON"]["exits"])
        if wid in targets:
            role = "TARGET"
        elif wid in admitted:
            role = "ADMITTED_PREEXISTING"
        elif wid in blocked_other:
            role = "BLOCKED_OTHER"
        else:
            raise AssertionError(f"workload outside 13/8/9 partition: {wid}")
        ledger.append(
            {
                "workload_id": wid,
                "population_role": role,
                "target_status": wid in targets,
                "base_rep_values": base_reps,
                "off_rep_values": off_reps,
                "on_rep_values": on_reps,
                "base_median": base_med,
                "off_median": off_med,
                "on_median": on_med,
                "reducer_definition": "median of 3 warm reps (historical R3 reducer)",
                "saved_s_off_on": off_med - on_med,
                "saved_s_base_on": base_med - on_med,
                "ratio_on_off": on_med / off_med,
                "ratio_on_base": on_med / base_med,
                "reduction_off_on": 1.0 - on_med / off_med,
                "route_off": first_mode(off_routes),
                "route_off_unanimous_3reps": len(set(off_routes)) == 1,
                "route_on": first_mode(on_routes),
                "route_on_unanimous_3reps": len(set(on_routes)) == 1,
                "direct_served_loads_on": [c.get("direct_served_loads", 0) for c in on_counts],
                "direct_served_reads_on": [c.get("direct_served_reads", 0) for c in on_counts],
                "direct_iteration_cells_on": [c.get("direct_iteration_cells", 0) for c in on_counts],
                "fallback_loads_on": [c.get("fallback_loads", 0) for c in on_counts],
                "reference_loads_on": [c.get("reference_loads", 0) for c in on_counts],
                "artifact_status_on": on_art,
                "exits_off": off_exits,
                "exits_on": on_exits,
                "base_exit": r.get("base_exit"),
                "parity_population_A": parity_a[wid],
                "included_in_historical_aggregate": True,
                "source_evidence": "research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl",
            }
        )
    ledger.sort(key=lambda e: e["workload_id"])

    # ---- historical primary reproduction (OFF -> ON, median sums) ----
    sum_base = sum(e["base_median"] for e in ledger)
    sum_off = sum(e["off_median"] for e in ledger)
    sum_on = sum(e["on_median"] for e in ledger)
    saved = sum_off - sum_on
    ratio = sum_on / sum_off
    reduction = 1.0 - ratio

    # ---- post-hoc descriptive statistics (frozen population) ----
    ratios = [e["ratio_on_off"] for e in ledger]
    saveds = [e["saved_s_off_on"] for e in ledger]
    faster = sum(1 for e in ledger if e["on_median"] < e["off_median"])
    equal = sum(1 for e in ledger if e["on_median"] == e["off_median"])
    slower = sum(1 for e in ledger if e["on_median"] > e["off_median"])
    qs = statistics.quantiles(sorted(ratios), n=4, method="exclusive")
    by_saved = sorted(ledger, key=lambda e: e["saved_s_off_on"], reverse=True)
    positive_total = sum(s for s in saveds if s > 0)
    conc = {}
    for k in (1, 3, 5, 10):
        conc[f"top{k}_share_of_positive_savings"] = sum(e["saved_s_off_on"] for e in by_saved[:k]) / positive_total
    conc["remaining_share"] = 1.0 - conc["top10_share_of_positive_savings"]
    by_off = sorted(ledger, key=lambda e: e["off_median"], reverse=True)
    off_total = sum_off
    on_total = sum_on
    conc["top3_off_runtime_share"] = sum(e["off_median"] for e in by_off[:3]) / off_total
    conc["top5_off_runtime_share"] = sum(e["off_median"] for e in by_off[:5]) / off_total
    # ON-runtime concentration on the same largest-OFF workloads
    conc["top3_off_workloads_on_runtime_share"] = sum(e["on_median"] for e in by_off[:3]) / on_total

    offs = [e["off_median"] for e in ledger]
    pearson_saved = statistics.correlation(offs, saveds)
    pearson_ratio = statistics.correlation(offs, ratios)

    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        rk = [0.0] * len(xs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk

    spearman_saved = statistics.correlation(ranks(offs), ranks(saveds))
    spearman_ratio = statistics.correlation(ranks(offs), ranks(ratios))

    # within-workload variability (run-to-run, per arm)
    var = {}
    for arm_key, label in (("base_rep_values", "BASE"), ("off_rep_values", "OFF"), ("on_rep_values", "ON")):
        cvs = []
        for e in ledger:
            reps = e[arm_key]
            mean = statistics.fmean(reps)
            sd = statistics.pstdev(reps)
            cvs.append(sd / mean if mean else 0.0)
        var[label] = {
            "median_cv_3reps": statistics.median(cvs),
            "max_cv_3reps": max(cvs),
            "max_cv_workload": max(ledger, key=lambda e, c=cvs, L=ledger: c[L.index(e)])["workload_id"],
        }

    fm = next(e for e in ledger if e["workload_id"] == "Financial_Model_08_02__4ca3ae46295d")
    rank_base = 1 + sum(1 for e in ledger if e["base_median"] > fm["base_median"])
    rank_saved = 1 + sum(1 for e in ledger if e["saved_s_off_on"] > fm["saved_s_off_on"])
    rank_reduction = 1 + sum(1 for e in ledger if e["reduction_off_on"] > fm["reduction_off_on"])

    summary = {
        "n_workloads": 30,
        "historical_reducer": "sum of per-workload medians of 3 warm reps",
        "historical_pair": "OFF (rc3-equivalent predecessor control) -> ON (iteration candidate)",
        "recomputed_base_sum_medians": sum_base,
        "recomputed_off_sum_medians": sum_off,
        "recomputed_on_sum_medians": sum_on,
        "absolute_saved_off_on": saved,
        "ratio_on_off": ratio,
        "relative_reduction_off_on": reduction,
        "historical_rounded": {"off": 102.26, "on": 21.51, "saved": 80.75, "reduction_pct": 79.0},
        "posthoc_descriptive": {
            "faster_on_lt_off": faster,
            "equal": equal,
            "slower_on_gt_off": slower,
            "median_ratio_on_off": statistics.median(ratios),
            "mean_ratio_on_off": statistics.fmean(ratios),
            "geomean_ratio_on_off": math.exp(statistics.fmean(math.log(x) for x in ratios)),
            "q1_ratio": qs[0],
            "q3_ratio": qs[2],
            "min_ratio": min(ratios),
            "min_ratio_workload": min(ledger, key=lambda e: e["ratio_on_off"])["workload_id"],
            "max_ratio": max(ratios),
            "max_ratio_workload": max(ledger, key=lambda e: e["ratio_on_off"])["workload_id"],
            "median_saved_s": statistics.median(saveds),
            "total_saved_s": saved,
            "largest_saving_s": max(saveds),
            "largest_saving_workload": max(ledger, key=lambda e: e["saved_s_off_on"])["workload_id"],
            "largest_regression_s": min(saveds),
            "largest_regression_workload": min(ledger, key=lambda e: e["saved_s_off_on"])["workload_id"],
            "concentration": conc,
            "pearson_off_runtime_vs_saved": pearson_saved,
            "pearson_off_runtime_vs_ratio": pearson_ratio,
            "spearman_off_runtime_vs_saved": spearman_saved,
            "spearman_off_runtime_vs_ratio": spearman_ratio,
            "within_workload_variability": var,
        },
        "fm08_02_4ca3": {
            "member": True,
            "population_role": fm["population_role"],
            "rank_by_base_median_desc": rank_base,
            "rank_by_saved_desc": rank_saved,
            "rank_by_reduction_desc": rank_reduction,
            "base_median": fm["base_median"],
            "off_median": fm["off_median"],
            "on_median": fm["on_median"],
            "saved_s_off_on": fm["saved_s_off_on"],
            "ratio_on_off": fm["ratio_on_off"],
            "reduction_off_on": fm["reduction_off_on"],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tier2_workloads.json").write_text(json.dumps(ledger, indent=1) + "\n")
    csv_cols = [
        "workload_id", "population_role", "target_status", "base_rep_values", "off_rep_values",
        "on_rep_values", "base_median", "off_median", "on_median", "reducer_definition",
        "saved_s_off_on", "saved_s_base_on", "ratio_on_off", "ratio_on_base", "reduction_off_on",
        "route_off", "route_off_unanimous_3reps", "route_on", "route_on_unanimous_3reps",
        "direct_served_loads_on", "direct_served_reads_on", "direct_iteration_cells_on",
        "fallback_loads_on", "reference_loads_on", "artifact_status_on", "exits_off", "exits_on",
        "base_exit", "parity_population_A", "included_in_historical_aggregate", "source_evidence",
    ]
    with open(OUT / "tier2_workloads.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols)
        w.writeheader()
        for e in ledger:
            row = {}
            for c in csv_cols:
                v = e[c]
                row[c] = json.dumps(v) if isinstance(v, (list, dict)) else v
            w.writerow(row)
    (OUT / "tier2_summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    # ---- console verification ----
    print(f"n={len(ledger)} roles=" + str({k: sum(1 for e in ledger if e['population_role'] == k) for k in ('TARGET', 'ADMITTED_PREEXISTING', 'BLOCKED_OTHER')}))
    print(f"BASE sum={sum_base:.4f} OFF sum={sum_off:.4f} ON sum={sum_on:.4f}")
    print(f"saved={saved:.4f} ratio={ratio:.4f} reduction={reduction * 100:.2f}%")
    print(f"faster={faster} equal={equal} slower={slower}")
    print(f"median_ratio={statistics.median(ratios):.4f} geomean={summary['posthoc_descriptive']['geomean_ratio_on_off']:.4f}")
    print("wrote", OUT / "tier2_workloads.json", OUT / "tier2_workloads.csv", OUT / "tier2_summary.json")


if __name__ == "__main__":
    sys.exit(main())
