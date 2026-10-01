"""Paired analysis of the frozen Phase-8 representative and changed-file runs."""
from __future__ import annotations

import json
import math
import random
import statistics as stats
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P8 = ROOT / "read_engine_phase8"


def load(name: str) -> list[dict]:
    return [json.loads(x) for x in (P8 / name).read_text().splitlines()]


def median(x: list[float]) -> float:
    return stats.median(x)


def summarize(values: dict[str, list[float]], *, signed: dict[str, list[float]] | None = None) -> dict:
    paired = {wid: median(rows) for wid, rows in values.items()}
    xs = list(paired.values())
    if not xs:
        return {"count": 0}
    rng = random.Random(20260928)
    draws = sorted(median([rng.choice(xs) for _ in xs]) for _ in range(2000))
    result = {"count": len(xs), "median_ratio": median(xs),
              "geometric_mean_ratio": math.exp(sum(math.log(v) for v in xs) / len(xs)),
              "bootstrap_median_interval_95": [draws[49], draws[1949]],
              "faster": sum(x < 1 for x in xs), "slower": sum(x > 1 for x in xs),
              "tied": sum(x == 1 for x in xs), "range": [min(xs), max(xs)],
              "per_workload_ratio": paired}
    if signed:
        per_signed = {wid: median(rows) for wid, rows in signed.items()}
        result["median_signed_excess_ms"] = median(list(per_signed.values()))
        result["per_workload_excess_ms"] = per_signed
    return result


def pairs(rows: list[dict], *, phase: str, invocation: int,
          arm: str = "H1", ids: set[str] | None = None) -> tuple[dict, dict]:
    groups = defaultdict(dict)
    for row in rows:
        if row["phase"] != phase or row["invocation"] != invocation:
            continue
        if ids is not None and row["workload_id"] not in ids:
            continue
        groups[(row["workload_id"], row["rep"])][row["arm"]] = row
    ratios = defaultdict(list)
    signed = defaultdict(list)
    for (wid, _rep), arms in groups.items():
        if not {"PY", arm} <= set(arms):
            raise RuntimeError(f"Unpaired result: {wid} {arm}")
        py, treatment = arms["PY"]["wall_ns"], arms[arm]["wall_ns"]
        ratios[wid].append(treatment / py)
        signed[wid].append((treatment - py) / 1e6)
    return ratios, signed


def session(rows: list[dict], n: int, *, ids: set[str] | None = None,
            arm: str = "H1") -> tuple[dict, dict]:
    ratios = defaultdict(list)
    signed = defaultdict(list)
    for row in rows:
        if row["N"] != n or ids is not None and row["workload_id"] not in ids:
            continue
        wid = row["workload_id"]
        ratios[wid].append(row[f"{arm}_ns"] / row["PY_ns"])
        signed[wid].append((row[f"{arm}_ns"] - row["PY_ns"]) / 1e6)
    return ratios, signed


def task_cluster(summary: dict, tasks: dict[str, str]) -> dict:
    by_task = defaultdict(list)
    for wid, ratio in summary.get("per_workload_ratio", {}).items():
        by_task[tasks[wid]].append(ratio)
    xs = [median(v) for v in by_task.values()]
    if not xs:
        return {"task_count": 0}
    rng = random.Random(20260929)
    draws = sorted(median([rng.choice(xs) for _ in xs]) for _ in range(2000))
    return {"task_count": len(xs), "equal_task_median_ratio": median(xs),
            "task_bootstrap_median_interval_95": [draws[49], draws[1949]]}


def analyze() -> dict:
    rows = load("representative_timings.jsonl")
    correct = load("representative_correctness.jsonl")
    changed = load("changed_file_timings.jsonl")
    changed_correct = load("changed_file_correctness.jsonl")
    sessions = load("session_timings.jsonl")
    if sum(r["phase"] == "scored" for r in rows) != 30 * 3 * 5 * 3:
        raise RuntimeError("Incomplete representative scored rows")
    if sum(r["phase"] == "scored" for r in changed) != 5 * 3 * 3:
        raise RuntimeError("Incomplete changed-file scored rows")
    if not all(r["valid"] for r in correct + changed_correct):
        raise RuntimeError("Correctness failure in scored or gate rows")
    gate = [r for r in correct if r["phase"] == "gate" and r["invocation"] == 1]
    classes = {r["workload_id"]: r["H1_class"] for r in gate}
    if len(classes) != 30:
        raise RuntimeError("Incomplete class map")
    ids = {"ALL_30": set(classes)}
    for category in ("DIRECT_CONTACT", "REFERENCE_ONLY", "FALLBACK_AFTER_CONTACT", "OTHER"):
        ids[category] = {wid for wid, value in classes.items() if value == category}
    pop = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    tasks = {r["workload_id"]: r["task"] for r in pop["workloads"]}
    result = {"status": "COMPLETE", "representative_count": 30,
              "changed_file_count": 5, "class_counts": dict(Counter(classes.values())),
              "class_by_workload": classes, "representative": {}, "changed_file": {},
              "correctness": {"representative_rows": len(correct),
                              "representative_valid": sum(r["valid"] for r in correct),
                              "changed_rows": len(changed_correct),
                              "changed_valid": sum(r["valid"] for r in changed_correct),
                              "representative_volatile_rows": sum(
                                  any(c["classification"] == "VOLATILE_ONLY_DIFFERENCE"
                                      for c in r["checks"].values()) for r in correct),
                              "changed_volatile_core_rows": sum(bool(r["volatile_package_parts"])
                                                                for r in changed_correct)}}
    for name, selected in ids.items():
        view = {}
        for inv, endpoint in ((1, "COLD"), (2, "SECOND_OR_REUSE")):
            ratio, signed = pairs(rows, phase="scored", invocation=inv, ids=selected)
            s = summarize(ratio, signed=signed)
            s["task_cluster"] = task_cluster(s, tasks)
            view[endpoint] = s
            if name == "ALL_30":
                h0ratio, h0signed = pairs(rows, phase="scored", invocation=inv,
                                          ids=selected, arm="H0")
                view[endpoint + "_H0_PY"] = summarize(h0ratio, signed=h0signed)
        view["SESSION"] = {}
        for n in (1, 2, 3, 5):
            ratio, signed = session(sessions, n, ids=selected)
            s = summarize(ratio, signed=signed)
            s["task_cluster"] = task_cluster(s, tasks)
            view["SESSION"][str(n)] = s
        result["representative"][name] = view
    for name in sorted({r["workload_id"] for r in changed if r["phase"] == "scored"}):
        ratio, signed = pairs(changed, phase="scored", invocation=1, ids={name})
        view = summarize(ratio, signed=signed)
        treatment = [r for r in changed if r["phase"] == "scored" and r["workload_id"] == name
                     and r["arm"] == "H1"]
        components = defaultdict(list)
        for row in treatment:
            observer = (row.get("parent_profile") or {}).get("observer") or {}
            for key, ns in observer.items():
                components["observer_" + key + "_ms"].append(ns / 1e6)
            cp = row.get("capture_profile") or {}
            if "capture_total_ns" in cp:
                components["capture_total_ms"].append(cp["capture_total_ns"] / 1e6)
                helper_envelope = observer.get("changed_helper_or_empty_receipt")
                if helper_envelope is not None:
                    components["helper_envelope_minus_capture_ms"].append(
                        (helper_envelope - cp["capture_total_ns"]) / 1e6)
            for key, seconds in (cp.get("sections_s") or {}).items():
                components["capture_" + key + "_ms"].append(seconds * 1e3)
        view["H1_component_median_ms"] = {k: median(v) for k, v in components.items()}
        result["changed_file"][name] = view
    return result


def main() -> None:
    analysis = analyze()
    (P8 / "analysis.json").write_text(json.dumps(analysis, sort_keys=True, indent=2) + "\n")
    profile = {"status": "COMPLETE", "changed_file_component_medians_ms": {
        name: row["H1_component_median_ms"] for name, row in analysis["changed_file"].items()},
        "note": "Coarse nested wall timers; medians are not additive. Helper envelope residual includes pre-byte persistence, helper process startup/import, teardown and observer work, not a pure startup timer."}
    (P8 / "profile.json").write_text(json.dumps(profile, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"class_counts": analysis["class_counts"],
                      "all30_cold": analysis["representative"]["ALL_30"]["COLD"]["median_ratio"],
                      "all30_second": analysis["representative"]["ALL_30"]["SECOND_OR_REUSE"]["median_ratio"],
                      "reference_only_second": analysis["representative"]["REFERENCE_ONLY"]["SECOND_OR_REUSE"]["median_ratio"]},
                     indent=2))


if __name__ == "__main__":
    main()
