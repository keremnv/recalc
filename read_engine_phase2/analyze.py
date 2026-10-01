"""Paired analysis of frozen Phase-2 raw rows; no workload selection."""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = 1_000_000
HORIZONS = (1, 2, 3, 5, 10)


def rows(name: str) -> list[dict]:
    return [json.loads(s) for s in (HERE / name).read_text().splitlines() if s]


def metric(pairs: list[tuple[float, float]], seed: int = 20260926) -> dict:
    ratios = [a / b for a, b in pairs if a > 0 and b > 0]
    if not ratios:
        return {"n": 0}
    rng = random.Random(seed)
    samples = [statistics.median(rng.choices(ratios, k=len(ratios))) for _ in range(2000)]
    samples.sort()
    return {"n": len(ratios), "median_ratio": statistics.median(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in ratios)),
            "bootstrap_median_95pct": [samples[49], samples[1949]],
            "min_ratio": min(ratios), "max_ratio": max(ratios),
            "faster": sum(x < 1 for x in ratios), "slower": sum(x > 1 for x in ratios),
            "tied": sum(x == 1 for x in ratios),
            "paired_ratios": ratios}


def med(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def analyze() -> dict:
    raw = rows("raw_timings.jsonl")
    sessions = rows("session_timings.jsonl")
    builds = {(r["workbook_sha256"], r["variant"]): r for r in raw if r["kind"] == "build"}
    inv = {(r["trace_id"], r["variant"], r["invocation"]): r for r in raw if r["kind"] == "invocation"}
    sess = {(r["trace_id"], r["variant"], r["N"]): r for r in sessions}
    workbooks = sorted({k[0] for k in builds})
    traces = sorted({k[0] for k in inv})
    if len(workbooks) != 39 or len(traces) != 51 or len(inv) != 2040 or len(sess) != 1020:
        raise ValueError(f"Incomplete raw data: {len(workbooks)} books, {len(traces)} traces, {len(inv)} invocations, {len(sess)} sessions")
    output = {"identities": {"workbooks": len(workbooks), "traces": len(traces),
                              "snapshots": len({inv[(t, 'P0', 0)]['snapshot_sha256'] for t in traces}),
                              "invocations": len(inv)}, "build": {}, "warm_engine": {},
              "warm_process": {}, "session": {}, "break_even": {}, "profiles": {},
              "artifact_size": [], "snapshot_session": {}}
    for numerator, denominator in (("P1", "P0"), ("P2", "P1"), ("P3", "P1"), ("P3", "P2")):
        pairs = [(builds[(w, numerator)]["child"]["phases"]["build_ns"],
                  builds[(w, denominator)]["child"]["phases"]["build_ns"]) for w in workbooks
                 if builds[(w, numerator)]["child"]["phases"]["build_ns"] is not None
                 and builds[(w, denominator)]["child"]["phases"]["build_ns"] is not None]
        output["build"][f"{numerator}/{denominator}"] = metric(pairs)
    for kind in ("warm_engine", "warm_process"):
        for numerator, denominator in (("P2", "P0"), ("P3", "P0"), ("P3", "P2")):
            pairs = []
            for t in traces:
                def per(variant):
                    rr = [inv[(t, variant, n)] for n in range(1, 10)]
                    return med([r["child"]["engine_ns"] if kind == "warm_engine" else r["process_ns"] for r in rr])
                pairs.append((per(numerator), per(denominator)))
            output[kind][f"{numerator}/{denominator}"] = metric(pairs)
    for N in HORIZONS:
        output["session"][str(N)] = {}
        for variant in ("P1", "P2", "P3"):
            pairs = [(sess[(t, variant, N)]["session_ns"], sess[(t, "P0", N)]["session_ns"]) for t in traces]
            output["session"][str(N)][f"{variant}/P0"] = metric(pairs)
    for variant in ("P1", "P2", "P3"):
        first = {}
        for t in traces:
            first[t] = next((N for N in HORIZONS if sess[(t, variant, N)]["session_ns"] < sess[(t, "P0", N)]["session_ns"]), None)
        output["break_even"][variant] = {"counts": dict(Counter(str(n) if n is not None else "not_by_10" for n in first.values())),
                                          "first_by_trace": first}
    for variant in ("P2", "P3"):
        for w in workbooks:
            b = builds[(w, variant)]
            output["artifact_size"].append({"workbook_sha256": w, "variant": variant,
                                             "artifact_bytes": b["child"]["phases"]["artifact_bytes"],
                                             "source_bytes": b["source_bytes"],
                                             "ratio": b["child"]["phases"]["artifact_bytes"] / b["source_bytes"]})
    for variant in ("P0", "P1", "P2", "P3"):
        rr = [inv[(t, variant, n)] for t in traces for n in range(1, 10)]
        phase_names = ("source_hash_ns", "manifest_discovery_ns", "artifact_hash_ns",
                       "format_validation_ns", "attach_ns", "build_ns", "acquire_ns")
        profile = {name: med([r["child"]["phases"].get(name, 0) / NS for r in rr]) for name in phase_names}
        profile.update({"trace_ms": med([r["child"]["trace_profile"]["trace_ns"] / NS for r in rr]),
                        "engine_ms": med([r["child"]["engine_ns"] / NS for r in rr]),
                        "process_ms": med([r["process_ns"] / NS for r in rr]),
                        "startup_residual_ms": med([(r["process_ns"] - r["child"]["engine_ns"]) / NS for r in rr]),
                        "rss_kib": med([r["child"]["rss_kib"] for r in rr])})
        output["profiles"][variant] = profile
    for N in HORIZONS:
        output["snapshot_session"][str(N)] = {}
        by_snapshot = defaultdict(list)
        for t in traces:
            by_snapshot[inv[(t, "P0", 0)]["snapshot_sha256"]].append(t)
        for variant in ("P2", "P3"):
            output["snapshot_session"][str(N)][variant] = {
                snap: metric([(sess[(t, variant, N)]["session_ns"], sess[(t, "P0", N)]["session_ns"]) for t in ts])
                for snap, ts in by_snapshot.items()}
    return output


if __name__ == "__main__":
    result = analyze()
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("wrote analysis.json")
