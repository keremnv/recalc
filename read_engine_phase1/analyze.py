"""Reproducible summaries of the frozen Phase-1 raw ledgers."""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(name):
    return [json.loads(line) for line in (HERE / name).open() if line.strip()]


def ratio_summary(pairs):
    # Each pair is (identity, comparator ns, treatment ns).
    ratios = [t / c for _, c, t in pairs if c > 0 and t > 0]
    if not ratios:
        return {"pairs": 0}
    logs = [math.log(x) for x in ratios]
    rng = random.Random(20260925)
    boot = []
    if len(logs) > 1:
        for _ in range(2000):
            boot.append(math.exp(statistics.mean(rng.choice(logs) for _ in logs)))
        boot.sort()
    return {"pairs": len(ratios), "median_ratio": statistics.median(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(logs)),
            "min_ratio": min(ratios), "max_ratio": max(ratios),
            "faster": sum(x < 1 for x in ratios), "slower": sum(x > 1 for x in ratios),
            "tied": sum(x == 1 for x in ratios),
            "geometric_mean_95pct_bootstrap_ci": [boot[49], boot[1949]] if boot else None}


def paired_group(raw, phase, key, measure, repetition=None, n=None, repeated_only=False):
    selected = [r for r in raw if r["phase"] == phase and r.get("status", "ok") == "ok"
                and (repetition is None or r.get("repetition") == repetition)
                and (not repeated_only or r.get("repetition", 0) > 0)
                and (n is None or r.get("n") == n)]
    grouped = defaultdict(list)
    for r in selected:
        grouped[(r[key], r["variant"])].append(r[measure])
    med = {k: statistics.median(v) for k, v in grouped.items()}
    identities = sorted({k[0] for k in med})
    variants = ("R0", "R1", "R2", "R3")
    out = {"identity_count": len(identities), "variant_median_seconds": {},
           "versus_R0": {}, "versus_R1": {}, "versus_R2": {}}
    for variant in variants:
        values = [med[(ident, variant)] / 1e9 for ident in identities if (ident, variant) in med]
        out["variant_median_seconds"][variant] = statistics.median(values) if values else None
    for baseline, slot in (("R0", "versus_R0"), ("R1", "versus_R1"), ("R2", "versus_R2")):
        for variant in variants:
            if variant == baseline:
                continue
            pairs = [(ident, med[(ident, baseline)], med[(ident, variant)]) for ident in identities
                     if (ident, baseline) in med and (ident, variant) in med]
            out[slot][variant] = ratio_summary(pairs)
    return out


def main():
    correctness = rows("raw_correctness.jsonl")
    timing = rows("raw_timings.jsonl")
    c = Counter(x["kind"] for x in correctness)
    out = {"correctness_counts": dict(c),
           "exact_trace_by_variant": {v: sum(x["exact"] for x in correctness if x["kind"] == "trace" and x["variant"] == v)
                                      for v in ("R0", "R1", "R2", "R3")},
           "exact_workbook_by_variant": {v: sum(x["exact"] for x in correctness if x["kind"] == "workbook_summary" and x["variant"] == v)
                                         for v in ("R2", "R3")},
           "nonempty_checked_by_variant": {v: sum(x["checked_nonempty_cells"] for x in correctness if x["kind"] == "workbook_summary" and x["variant"] == v)
                                           for v in ("R2", "R3")},
           "mismatch_categories": dict(Counter(x["category"] for x in correctness if x["kind"] == "mismatch")),
           "oracle_failures": [x for x in correctness if x["kind"] == "oracle_failure"],
           "timing_counts": dict(Counter("/".join((x["phase"], x["variant"], x.get("status", "ok"))) for x in timing))}
    if any(x["phase"] == "construction" for x in timing):
        out["construction_first"] = paired_group(timing, "construction", "workbook_sha256", "total_ns", repetition=0)
        out["construction_repeated"] = paired_group(timing, "construction", "workbook_sha256", "total_ns", repeated_only=True)
        artifacts = {}
        for variant in ("R1", "R2", "R3"):
            sample = [x for x in timing if x["phase"] == "construction" and x["variant"] == variant
                      and x.get("status") == "ok" and x["repetition"] == 0]
            key = "approx_memory_bytes" if variant == "R2" else "artifact_bytes"
            vals = [x[key] for x in sample if x[key] is not None]
            ratios = [x["artifact_source_ratio"] for x in sample if x.get("artifact_source_ratio") is not None]
            artifacts[variant] = {"n": len(vals), "median_bytes": statistics.median(vals) if vals else None,
                                  "min_bytes": min(vals) if vals else None, "max_bytes": max(vals) if vals else None,
                                  "median_artifact_source_ratio": statistics.median(ratios) if ratios else None,
                                  "cross_process_readonly_attach": Counter(str(x.get("cross_process_readonly_attach")) for x in sample)}
        out["representations"] = artifacts
    if any(x["phase"] == "index_ready" for x in timing):
        out["index_ready_total"] = paired_group(timing, "index_ready", "trace_id", "total_ns")
        out["index_ready_acquisition"] = paired_group(timing, "index_ready", "trace_id", "acquisition_ns")
        out["index_ready_operations"] = paired_group(timing, "index_ready", "trace_id", "operations_ns")
    if any(x["phase"] == "reuse" for x in timing):
        out["reuse"] = {str(n): paired_group(timing, "reuse", "trace_id", "total_ns", n=n)
                        for n in (1, 2, 3, 5, 10)}
        by = {(x["trace_id"], x["variant"], x["n"]): x["total_ns"] for x in timing if x["phase"] == "reuse"}
        traces = sorted({x["trace_id"] for x in timing if x["phase"] == "reuse"})
        out["first_observed_break_even"] = {}
        for variant in ("R1", "R2", "R3"):
            answers = []
            for trace in traces:
                observed = next((n for n in (1, 2, 3, 5, 10)
                                 if (trace, variant, n) in by and (trace, "R0", n) in by
                                 and by[(trace, variant, n)] <= by[(trace, "R0", n)]), None)
                answers.append(observed)
            out["first_observed_break_even"][variant] = dict(Counter(str(x) for x in answers))
    (HERE / "analysis.json").write_text(json.dumps(out, indent=2, sort_keys=True, default=dict) + "\n")
    print(json.dumps({k: out[k] for k in ("correctness_counts", "exact_trace_by_variant", "oracle_failures", "timing_counts")}, indent=2, default=str))


if __name__ == "__main__":
    main()
