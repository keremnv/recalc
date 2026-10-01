"""Paired Phase-9 analysis over frozen full-command ledgers."""
from __future__ import annotations

import json
import math
import random
import statistics as stats
from collections import Counter, defaultdict
from pathlib import Path

from read_engine_phase9 import benchmark as b9

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text().splitlines()]


def med(xs: list[float]) -> float:
    return stats.median(xs)


def summarize(ratios: dict[str, list[float]],
              signed: dict[str, list[float]] | None = None) -> dict:
    per = {wid: med(v) for wid, v in ratios.items()}
    xs = list(per.values())
    if not xs:
        return {"count": 0}
    rng = random.Random(20261002)
    draws = sorted(med([rng.choice(xs) for _ in xs]) for _ in range(2000))
    result = {"count": len(xs), "median_ratio": med(xs),
              "geometric_mean_ratio": math.exp(sum(math.log(v) for v in xs) / len(xs)),
              "bootstrap_median_interval_95": [draws[49], draws[1949]],
              "faster": sum(v < 1 for v in xs), "slower": sum(v > 1 for v in xs),
              "tied": sum(v == 1 for v in xs), "range": [min(xs), max(xs)],
              "per_workload_ratio": per}
    if signed is not None:
        vals = {wid: med(v) for wid, v in signed.items()}
        result["median_signed_excess_ms"] = med(list(vals.values()))
        result["per_workload_excess_ms"] = vals
    return result


def paired(data: list[dict], *, phase: str, invocation: int,
           numerator: str, denominator: str, selected: set[str]) -> tuple[dict, dict]:
    groups = defaultdict(dict)
    for row in data:
        if (row["phase"] == phase and row["invocation"] == invocation
                and row["workload_id"] in selected):
            groups[(row["workload_id"], row["rep"])][row["arm"]] = row
    ratios, signed = defaultdict(list), defaultdict(list)
    for (wid, rep), arms in groups.items():
        if numerator not in arms or denominator not in arms:
            raise RuntimeError(f"Unpaired {wid} repetition {rep}")
        a, b = arms[numerator]["wall_ns"], arms[denominator]["wall_ns"]
        ratios[wid].append(a / b)
        signed[wid].append((a - b) / 1e6)
    return ratios, signed


def session_paired(data: list[dict], n: int, *,
                   numerator: str, denominator: str,
                   selected: set[str]) -> tuple[dict, dict]:
    ratios, signed = defaultdict(list), defaultdict(list)
    for row in data:
        if row["N"] != n or row["workload_id"] not in selected:
            continue
        wid = row["workload_id"]
        a, b = row[numerator + "_ns"], row[denominator + "_ns"]
        ratios[wid].append(a / b)
        signed[wid].append((a - b) / 1e6)
    return ratios, signed


def cluster(summary: dict, task_by_id: dict[str, str]) -> dict:
    grouped = defaultdict(list)
    for wid, ratio in summary.get("per_workload_ratio", {}).items():
        grouped[task_by_id[wid]].append(ratio)
    xs = [med(v) for v in grouped.values()]
    if not xs:
        return {"task_count": 0}
    rng = random.Random(20261003)
    draws = sorted(med([rng.choice(xs) for _ in xs]) for _ in range(2000))
    return {"task_count": len(xs), "equal_task_median_ratio": med(xs),
            "task_bootstrap_median_interval_95": [draws[49], draws[1949]]}


def component_profile(data: list[dict], ids: set[str]) -> dict:
    vals = defaultdict(lambda: defaultdict(list))
    for row in data:
        if (row["phase"] != "scored" or row["invocation"] != 2
                or row["workload_id"] not in ids or row["arm"] == "PY"):
            continue
        arm, wid = row["arm"], row["workload_id"]
        bootstrap = ((row.get("parent_profile") or {}).get("script_bootstrap") or {})
        child = row.get("child_profile") or {}
        observer = ((row.get("parent_profile") or {}).get("observer") or {})
        for key in ("pre_runtime", "config_admission", "runtime_import_install",
                    "bootstrap_total"):
            if key in bootstrap:
                vals[(arm, key)][wid].append(bootstrap[key] / 1e6)
        for key in ("post_bootstrap_to_exit_ns",):
            if key in child:
                vals[(arm, key)][wid].append(child[key] / 1e6)
        for key in ("pre_snapshot", "post_snapshot_compare",
                    "changed_helper_or_empty_receipt", "observer_to_receipt"):
            if key in observer:
                vals[(arm, "observer_" + key)][wid].append(observer[key] / 1e6)
    return {arm + "_" + key + "_median_ms":
            med([med(samples) for samples in by_wid.values()])
            for (arm, key), by_wid in vals.items()}


def analyze() -> tuple[dict, dict]:
    b9.verify()
    timing = rows("raw_timings.jsonl")
    correct = rows("raw_correctness.jsonl")
    session_rows = rows("session_timings.jsonl")
    changed = rows("changed_file_timings.jsonl")
    changed_correct = rows("changed_file_correctness.jsonl")
    process = rows("process_semantics.jsonl")
    if sum(r["phase"] == "scored" for r in timing) != 1350:
        raise RuntimeError("Incomplete representative scored rows")
    if sum(r["phase"] == "scored" for r in changed) != 45:
        raise RuntimeError("Incomplete changed-file scored rows")
    if len(session_rows) != 360:
        raise RuntimeError("Incomplete observed sessions")
    if not all(r["valid"] for r in correct + changed_correct):
        raise RuntimeError("Semantic failure")
    if not all(r["passed"] for r in process):
        raise RuntimeError("Process/assurance failure")
    gate = [r for r in correct if r["phase"] == "gate" and r["invocation"] == 1]
    classes = {r["workload_id"]: r["H0_class"] for r in gate}
    routes = {r["workload_id"]: r["H1_route"] for r in gate}
    if len(classes) != 30:
        raise RuntimeError("Incomplete representative class map")
    selections = {"ALL_30": set(classes)}
    for name in ("REFERENCE_ONLY", "DIRECT_CONTACT", "FALLBACK_AFTER_CONTACT"):
        selections[name] = {wid for wid, value in classes.items() if value == name}
    selections["FAST_PATH_PROVEN_REFERENCE"] = {
        wid for wid in selections["REFERENCE_ONLY"]
        if routes[wid] == "FAST_PATH_PROVEN_REFERENCE"}
    selections["REFERENCE_ONLY_BUT_UNCERTAIN"] = (
        selections["REFERENCE_ONLY"] - selections["FAST_PATH_PROVEN_REFERENCE"])
    pop = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    tasks = {r["workload_id"]: r["task"] for r in pop["workloads"]}
    result = {"status": "COMPLETE", "class_counts": dict(Counter(classes.values())),
              "route_counts": dict(Counter(routes.values())),
              "class_by_workload": classes, "route_by_workload": routes,
              "correctness": {
                  "representative_rows": len(correct),
                  "representative_valid": sum(r["valid"] for r in correct),
                  "changed_rows": len(changed_correct),
                  "changed_valid": sum(r["valid"] for r in changed_correct),
                  "process_rows": len(process),
                  "process_valid": sum(r["passed"] for r in process),
                  "representative_volatile": sum(
                      any(c["classification"] == "VOLATILE_ONLY_DIFFERENCE"
                          for c in r["checks"].values()) for r in correct),
                  "changed_volatile_core": sum(
                      bool(r["volatile_package_parts"]) for r in changed_correct)},
              "representative": {}, "changed_file": {}}
    for name, selected in selections.items():
        view = {}
        for invocation, endpoint in ((1, "COLD"), (2, "SECOND_OR_REUSE")):
            view[endpoint] = {}
            for pair, numerator, denominator in (
                ("H1_PY", "H1", "PY"), ("H1_H0", "H1", "H0"),
                ("H0_PY", "H0", "PY")):
                ratio, signed = paired(
                    timing, phase="scored", invocation=invocation,
                    numerator=numerator, denominator=denominator, selected=selected)
                summary = summarize(ratio, signed)
                summary["task_cluster"] = cluster(summary, tasks)
                view[endpoint][pair] = summary
        view["SESSION"] = {}
        for n in (1, 2, 3, 5):
            view["SESSION"][str(n)] = {}
            for pair, numerator, denominator in (
                ("H1_PY", "H1", "PY"), ("H1_H0", "H1", "H0")):
                ratio, signed = session_paired(
                    session_rows, n, numerator=numerator,
                    denominator=denominator, selected=selected)
                summary = summarize(ratio, signed)
                summary["task_cluster"] = cluster(summary, tasks)
                view["SESSION"][str(n)][pair] = summary
        result["representative"][name] = view
    for name in sorted({r["workload_id"] for r in changed if r["phase"] == "scored"}):
        view = {}
        for pair, numerator, denominator in (
            ("H1_PY", "H1", "PY"), ("H1_H0", "H1", "H0")):
            ratio, signed = paired(changed, phase="scored", invocation=1,
                                   numerator=numerator, denominator=denominator,
                                   selected={name})
            view[pair] = summarize(ratio, signed)
        result["changed_file"][name] = view
    budget_cold = result["representative"]["REFERENCE_ONLY"]["COLD"]["H1_PY"][
        "median_signed_excess_ms"] <= 15
    budget_second = result["representative"]["REFERENCE_ONLY"]["SECOND_OR_REUSE"][
        "H1_PY"]["median_signed_excess_ms"] <= 10
    causal = result["representative"]["FAST_PATH_PROVEN_REFERENCE"][
        "SECOND_OR_REUSE"]["H1_H0"]
    result["decisions"] = {
        "cold_budget_met": budget_cold,
        "second_budget_met": budget_second,
        "transparency_budget_met": budget_cold and budget_second,
        "fast_path_causal_rule_met": (
            causal["count"] > 0 and causal.get("median_ratio", 1) < 1
            and causal["median_signed_excess_ms"] <= -5
            and causal["faster"] > causal["slower"])}
    profile = {"status": "COMPLETE",
               "reference_only_component_medians_ms": component_profile(
                   timing, selections["REFERENCE_ONLY"]),
               "note": "Coarse nested medians are not additive; external H1/H0 is causal authority."}
    return result, profile


def main() -> None:
    analysis, profile = analyze()
    (HERE / "analysis.json").write_text(json.dumps(analysis, sort_keys=True, indent=2) + "\n")
    (HERE / "profile.json").write_text(json.dumps(profile, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"classes": analysis["class_counts"],
                      "routes": analysis["route_counts"],
                      "decisions": analysis["decisions"]}, indent=2))


if __name__ == "__main__":
    main()
