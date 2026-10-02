#!/usr/bin/env python3
"""Mechanical analysis of the frozen 48-slot affordance discovery experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import shutil
import statistics as stats
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.review_token_affordance import analyze_run  # noqa: E402

OUT = ROOT / "research/history/token_affordance_discovery"
ARMS = "ABCD"
FAMILIES = ("Template", "Financial_Model", "Debugging")
CENSORED = {"PROVIDER_CENSORED", "RUNNER_CENSORED", "WORKBOOK_INFRA_CENSORED"}
SEED = 20261007


def load(name):
    return json.loads((OUT / name).read_text())


def rows(name):
    return [json.loads(x) for x in (OUT / name).read_text().splitlines() if x.strip()]


def put(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def write_rows(name, values):
    with (OUT / name).open("w") as stream:
        for x in values:
            stream.write(json.dumps(x, sort_keys=True, default=str) + "\n")


def summary(values):
    values = [float(x) for x in values if x is not None and x > 0]
    if not values:
        return {"n": 0, "median_ratio": None, "mean_ratio": None,
                "geometric_mean_ratio": None, "bootstrap_95pct_ci_geometric_ratio": None,
                "treatment_lower": 0, "treatment_higher": 0, "equal": 0}
    logs = [math.log(x) for x in values]
    rng = random.Random(SEED)
    boot = sorted(math.exp(stats.mean(rng.choice(logs) for _ in logs)) for _ in range(10000))
    return {"n": len(values), "median_ratio": stats.median(values), "mean_ratio": stats.mean(values),
            "geometric_mean_ratio": math.exp(stats.mean(logs)),
            "bootstrap_95pct_ci_geometric_ratio": [boot[249], boot[9749]],
            "treatment_lower": sum(x < 1 for x in values),
            "treatment_higher": sum(x > 1 for x in values), "equal": sum(x == 1 for x in values)}


def score_all(primary):
    staged = OUT / "score_staging"
    per_arm = {}
    for arm in ARMS:
        root = staged / arm
        root.mkdir(parents=True, exist_ok=True)
        for rec in primary:
            if rec["arm"] != arm:
                continue
            family, task_id = rec["task"].split(":", 1)
            dst = root / f"{family}-{task_id}"
            dst.mkdir(exist_ok=True)
            src = ROOT / rec["run_dir"] / "output.xlsx"
            if src.is_file():
                shutil.copy2(src, dst / "output.xlsx")
        cmd = [sys.executable, str(ROOT / "benchmark/score_openrouter_run.py"), str(root),
               "--model-name", f"token_affordance_discovery_{arm}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        (root / "scorer_stdout.txt").write_text(proc.stdout + proc.stderr)
        if proc.returncode or not (root / "official_scores.json").exists():
            raise RuntimeError(f"official scoring failed for {arm}: {(proc.stdout + proc.stderr)[-1000:]}")
        per_arm[arm] = json.loads((root / "official_scores.json").read_text())
    return per_arm


def categorize_run(rec, scored):
    if rec["status"] in CENSORED:
        return rec["status"]
    event_path = ROOT / rec["run_dir"] / "events.jsonl"
    events = [json.loads(x) for x in event_path.read_text().splitlines() if x.strip()]
    # A recovered timeout is harmless for a submitted slot. For an unfinished
    # slot below the call cap, logged provider failures consumed part of the
    # fixed deadline, so model-only noncompletion cannot be identified.
    if rec["status"] == "MODEL_NONCOMPLETION" and rec["api_calls"] < 40 and any(
        event.get("event") == "provider_error" for event in events
    ):
        return "PROVIDER_CENSORED"
    if rec["status"] == "MODEL_NONCOMPLETION":
        return "MODEL_NONCOMPLETION"
    if rec["status"] == "SUBMITTED":
        return "VALID_SUBMISSION" if scored["valid_submission"] else "INVALID_SUBMISSION"
    return "OTHER"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-scores", action="store_true", help="Never call LibreOffice/scorer; use archived official scores")
    args = parser.parse_args()
    spec = load("preregistered_spec.json")
    if hashlib.sha256((OUT / "preregistered_spec.json").read_bytes()).hexdigest() != load("spec_hash.json")["sha256"]:
        raise RuntimeError("preregistration changed")
    for name, digest in spec["hashes"].items():
        if hashlib.sha256((OUT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"frozen design artifact changed: {name}")
    primary = rows("primary_runs.jsonl")
    population = load("population.json")["tasks"]
    if len(primary) != 48 or len({(x["task"], x["arm"]) for x in primary}) != 48:
        raise RuntimeError("all 48 unique primary slots must finish before analysis")
    if set(x["task"] for x in primary) != set(population):
        raise RuntimeError("primary task set changed")
    if hashlib.sha256((ROOT / "research/history/token_claim_discovery/future_validation_reservation.json").read_bytes()).hexdigest() != spec["reserved_holdout_sha256"]:
        raise RuntimeError("reserved holdout manifest changed")

    scores = load("official_scores.json")["arms"] if args.reuse_scores else score_all(primary)
    scored_rows = []
    for rec in primary:
        official = scores[rec["arm"]]["tasks"].get(rec["task"], {})
        error = str(official.get("error_message") or "")
        scored_workbook = bool(official and
                               isinstance(official.get("modification_accuracy"), (int, float)) and
                               isinstance(official.get("regression_accuracy"), (int, float)) and
                               (not error or error.startswith(("Modification error at ", "Regression error at "))))
        scored_rows.append({
            "task": rec["task"], "arm": rec["arm"], "submitted": rec["submitted"],
            "output_exists": rec["output_exists"],
            "valid_submission": bool(rec["submitted"] and rec["output_exists"] and scored_workbook),
            "workbook_scored": bool(rec["output_exists"] and scored_workbook),
            "exact": official.get("accuracy"),
            "modification": official.get("modification_accuracy"),
            "regression": official.get("regression_accuracy"),
            "scorer_diagnostic": official.get("error_message"),
        })
    put("official_scores.json", {"official_runtime": "unmodified official evaluator after LibreOffice refresh",
                                 "arms": scores, "rows": scored_rows})
    score_by = {(x["task"], x["arm"]): x for x in scored_rows}
    categories = []
    for rec in primary:
        score = score_by[(rec["task"], rec["arm"])]
        categories.append({"task": rec["task"], "arm": rec["arm"], "status": rec["status"],
                           "category": categorize_run(rec, score)})
    put("censoring.json", {"rows": categories,
                           "by_arm": {a: dict(Counter(x["category"] for x in categories if x["arm"] == a)) for a in ARMS}})
    category_by = {(x["task"], x["arm"]): x["category"] for x in categories}

    raw_usage = rows("provider_usage.jsonl")
    selected = {}
    for usage in raw_usage:
        selected[(usage["task"], usage["arm"], usage["call"])] = usage
    usage_rows = list(selected.values())
    if len(usage_rows) != sum(x["api_calls"] for x in primary):
        raise RuntimeError("selected provider calls do not reconcile with primary runs")
    for rec in primary:
        matches = [x for x in usage_rows if (x["task"], x["arm"]) == (rec["task"], rec["arm"])]
        if len(matches) != rec["api_calls"] or sum(x["prompt_tokens"] for x in matches) != rec["prompt_tokens"]:
            raise RuntimeError(f"provider usage mismatch for {rec['task']} {rec['arm']}")
    write_rows("provider_usage_selected.jsonl", usage_rows)
    uses = defaultdict(list)
    for u in usage_rows:
        uses[(u["task"], u["arm"])].append(u)

    trajectory_summaries = []
    classified = []
    event_by = defaultdict(list)
    for rec in primary:
        trajectory, labels = analyze_run(rec)
        trajectory_summaries.append(trajectory)
        labels_by_call = {x["call"]: x for x in labels}
        for raw in rows_from_run(rec):
            if not raw.get("tool"):
                continue
            enriched = {**raw, "phase": "PRIMARY", "classification": labels_by_call[raw["call"]]["category"],
                        "classification_flags": labels_by_call[raw["call"]]["flags"]}
            classified.append(enriched)
            event_by[(rec["task"], rec["arm"])].append(enriched)
    write_rows("trajectory_events.jsonl", classified)
    trajectory_by = {(x["task"], x["arm"]): x for x in trajectory_summaries}

    import_re = re.compile(r"\b(?:import\s+lx_helpers|from\s+lx_helpers\s+import)\b")
    helper_summary = []
    for rec in primary:
        ev = event_by[(rec["task"], rec["arm"])]
        attempts = [e for e in ev if e.get("tool") == "bash" and import_re.search(str((e.get("arguments") or {}).get("command") or ""))]
        calls = []
        for e in ev:
            if e.get("tool") != "bash":
                continue
            cmd = str((e.get("arguments") or {}).get("command") or "")
            aliases = {"lx_helpers"}
            aliases.update(re.findall(r"\bimport\s+lx_helpers\s+as\s+([A-Za-z_]\w*)", cmd))
            qualified = re.compile(r"\b(?:" + "|".join(re.escape(a) for a in sorted(aliases)) + r")\.(search|periods|inspect)\s*\(")
            found = qualified.findall(cmd)
            imported_names = re.findall(r"\bfrom\s+lx_helpers\s+import\s+([^\n;]+)", cmd)
            for names in imported_names:
                for name in ("search", "periods", "inspect"):
                    if re.search(r"\b" + name + r"\b", names):
                        found.extend(re.findall(r"(?<![.\w])(" + name + r")\s*\(", cmd))
            if found:
                calls.append({"call": e["call"], "types": found, "returncode": e.get("returncode"),
                              "visible_output_bytes_proxy": e.get("observation_bytes_model_visible", 0)})
        helper_summary.append({"task": rec["task"], "arm": rec["arm"],
                               "import_attempts": len(attempts),
                               "import_command_failures": sum(e.get("returncode") not in (0, None) for e in attempts),
                               "helper_command_calls": calls,
                               "helper_function_call_syntax": dict(Counter(t for call in calls for t in call["types"])),
                               "helper_output_bytes_proxy": sum(x["visible_output_bytes_proxy"] for x in calls),
                               "displacement_mechanically_proven": False})
    put("helper_adoption.json", {"rows": helper_summary,
                                 "by_arm": {a: {"runs_with_import_attempt": sum(x["import_attempts"] > 0 for x in helper_summary if x["arm"] == a),
                                                "runs_with_helper_call_syntax": sum(bool(x["helper_command_calls"]) for x in helper_summary if x["arm"] == a),
                                                "helper_command_calls": sum(len(x["helper_command_calls"]) for x in helper_summary if x["arm"] == a)} for a in ARMS},
                                 "limit": "Syntax and command exit status are proxies; transcript audit is required for successful import, useful helper output, and displacement."})

    task_rows = []
    for task in population:
        row = {"task": task, "family": task.split(":")[0]}
        for arm in ARMS:
            rec = next(x for x in primary if x["task"] == task and x["arm"] == arm)
            u = uses[(task, arm)]
            traj = trajectory_by[(task, arm)]
            es = event_by[(task, arm)]
            score = score_by[(task, arm)]
            reported_costs = [x.get("reported_cost_usd") for x in u]
            row[arm] = {
                "provider_input_tokens": rec["prompt_tokens"], "provider_output_tokens": rec["completion_tokens"],
                "cached_input_tokens": sum(x.get("cached_input_tokens") or 0 for x in u),
                "uncached_input_tokens": sum(x["prompt_tokens"] - (x.get("cached_input_tokens") or 0) for x in u),
                "provider_reported_cost_usd": sum(reported_costs) if all(x is not None for x in reported_costs) else None,
                "estimated_cost_usd": rec["cost_usd_estimate"],
                "billed_tokens_if_distinct": [((x.get("raw_usage") or {}).get("billed_tokens")) for x in u],
                "calls": rec["api_calls"], "status": rec["status"], "censoring": category_by[(task, arm)],
                "elapsed_s": rec["elapsed_s"],
                "noncompletion_boundary_proxy": ("CALL_CAP" if rec["api_calls"] >= 40 else
                                                 "ESTIMATED_COST_CAP" if rec["cost_usd_estimate"] >= 0.25 else
                                                 "TASK_DEADLINE" if rec["elapsed_s"] >= 895 else
                                                 "OTHER") if rec["status"] == "MODEL_NONCOMPLETION" else None,
                "submitted": rec["submitted"], "valid_submission": score["valid_submission"],
                "modification": score["modification"], "regression": score["regression"], "exact": score["exact"],
                "first_workbook_open_call": min([e["call"] for e in es if e.get("tool") == "view_xlsx" or e["classification_flags"]["workbook_open_command"]], default=None),
                "first_save_call": traj["first_save_command_call"], "last_save_call": traj["last_save_command_call"],
                "save_commands": len(traj["save_command_calls"]),
                "workbook_open_commands": traj["flags"].get("workbook_open_command", 0),
                "recalc_commands": traj["flags"].get("recalc_command", 0),
                "post_edit_read_recalc": traj["flags"].get("post_edit_read_or_recalc_proxy", 0),
                "post_edit_recalc": sum(bool(e["classification_flags"].get("after_first_save_proxy") and e["classification_flags"].get("recalc_command")) for e in es),
                "post_edit_workbook_reads": sum(bool(e["classification_flags"].get("after_first_save_proxy") and (e["classification_flags"].get("read_command") or e.get("tool") == "view_xlsx")) for e in es),
                "edit_check_loops": traj["edit_check_loop_proxy_count"],
                "final_save_to_submit_calls": traj["submit_calls_after_last_save"],
                "repeat_view_targets": traj["flags"].get("exact_repeat_view_target", 0),
                "repeat_read_commands": traj["flags"].get("exact_repeat_read_command", 0),
                "repeat_visible_observations": traj["flags"].get("repeated_identical_visible_observation", 0),
                "formula_dump_calls": sum(bool(re.search(r"formula|data_type\s*==\s*['\"]f['\"]", str((e.get("arguments") or {}).get("command") or ""), re.I)) for e in es if e.get("tool") == "bash"),
                "whole_workbook_scan_proxy": sum(bool(e.get("whole_workbook_scan")) for e in es),
                "targeted_range_proxy": sum(bool(e.get("targeted_range")) for e in es),
                "python_inspection_calls": sum(bool(e.get("python_inspection")) for e in es),
                "python_stdout_visible_bytes": sum(e.get("observation_bytes_model_visible", 0) for e in es if e.get("tool") == "bash" and e.get("python_inspection")),
                "view_visible_bytes": sum(e.get("observation_bytes_model_visible", 0) for e in es if e.get("tool") == "view_xlsx"),
                "broad_view_calls": sum(bool(e.get("broad_view")) for e in es if e.get("tool") == "view_xlsx"),
                "total_tool_observation_visible_bytes": sum(e.get("observation_bytes_model_visible", 0) for e in es),
                "helper_import_attempts": next(x["import_attempts"] for x in helper_summary if x["task"] == task and x["arm"] == arm),
                "helper_command_calls": next(len(x["helper_command_calls"]) for x in helper_summary if x["task"] == task and x["arm"] == arm),
                "helper_api_introspection_proxy": sum(bool(re.search(r"\b(?:dir\s*\(\s*lx_helpers|(?:getsource|__doc__)\b)", str((e.get("arguments") or {}).get("command") or ""))) for e in es if e.get("tool") == "bash" and "lx_helpers" in str((e.get("arguments") or {}).get("command") or "")),
                "served_models": sorted(set(str(x.get("served_model")) for x in u)),
                "served_providers": dict(Counter(str(x.get("served_provider")) for x in u)),
                "first_request_provider_input_tokens": min(u, key=lambda x: x["call"])["prompt_tokens"] if u else None,
            }
        task_rows.append(row)
    put("token_summary.json", task_rows)

    contrast_defs = (("B_vs_A", "B", "A"), ("C_vs_B", "C", "B"),
                     ("D_vs_C", "D", "C"), ("C_vs_A", "C", "A"), ("D_vs_A", "D", "A"))
    contrasts = {}
    families = {}
    sensitivity = {}
    for label, tr, co in contrast_defs:
        pair_rows = []
        for row in task_rows:
            t, c = row[tr], row[co]
            if t["censoring"] in CENSORED or c["censoring"] in CENSORED:
                continue
            if not t["provider_input_tokens"] or not c["provider_input_tokens"] or not t["calls"] or not c["calls"]:
                continue
            pair_rows.append({"task": row["task"], "family": row["family"],
                              "input_ratio": t["provider_input_tokens"] / c["provider_input_tokens"],
                              "call_ratio": t["calls"] / c["calls"], "call_difference": t["calls"] - c["calls"],
                              "input_per_call_ratio": (t["provider_input_tokens"] / t["calls"]) / (c["provider_input_tokens"] / c["calls"]),
                              "cached_ratio": t["cached_input_tokens"] / c["cached_input_tokens"] if c["cached_input_tokens"] else None,
                              "uncached_ratio": t["uncached_input_tokens"] / c["uncached_input_tokens"] if c["uncached_input_tokens"] else None,
                              "cost_ratio": t["provider_reported_cost_usd"] / c["provider_reported_cost_usd"] if t["provider_reported_cost_usd"] is not None and c["provider_reported_cost_usd"] else None,
                              "dual_valid": t["valid_submission"] and c["valid_submission"],
                              "treatment_submitted": t["valid_submission"], "control_submitted": c["valid_submission"],
                              "modification_delta": t["modification"] - c["modification"] if t["valid_submission"] and c["valid_submission"] else None,
                              "regression_delta": t["regression"] - c["regression"] if t["valid_submission"] and c["valid_submission"] else None,
                              "first_save_call_difference": t["first_save_call"] - c["first_save_call"] if t["first_save_call"] is not None and c["first_save_call"] is not None else None,
                              "save_count_difference": t["save_commands"] - c["save_commands"],
                              "post_edit_read_recalc_difference": t["post_edit_read_recalc"] - c["post_edit_read_recalc"],
                              "final_save_to_submit_difference": t["final_save_to_submit_calls"] - c["final_save_to_submit_calls"] if t["final_save_to_submit_calls"] is not None and c["final_save_to_submit_calls"] is not None else None})
        dual = [x for x in pair_rows if x["dual_valid"]]
        contrasts[label] = {
            "E2_all_uncensored": {key: summary([x[key] for x in pair_rows]) for key in ("input_ratio", "call_ratio", "input_per_call_ratio", "cached_ratio", "uncached_ratio", "cost_ratio")},
            "E1_dual_valid": {key: summary([x[key] for x in dual]) for key in ("input_ratio", "call_ratio")},
            "pairs": pair_rows,
            "dual_valid_n": len(dual),
            "completion_discordance": [x for x in pair_rows if x["treatment_submitted"] != x["control_submitted"]],
            "mean_dual_valid_modification_delta": stats.mean(x["modification_delta"] for x in dual) if dual else None,
            "mean_dual_valid_regression_delta": stats.mean(x["regression_delta"] for x in dual) if dual else None,
        }
        families[label] = {family: {"input": summary([x["input_ratio"] for x in pair_rows if x["family"] == family]),
                                    "calls": summary([x["call_ratio"] for x in pair_rows if x["family"] == family])}
                           for family in FAMILIES}
        sensitivity[label] = {
            "full": summary([x["input_ratio"] for x in pair_rows]),
            "leave_one_task_out": {x["task"]: summary([y["input_ratio"] for y in pair_rows if y["task"] != x["task"]]) for x in pair_rows},
            "leave_one_family_out": {family: summary([x["input_ratio"] for x in pair_rows if x["family"] != family]) for family in FAMILIES},
            "largest_favorable": min(pair_rows, key=lambda x: x["input_ratio"]) if pair_rows else None,
            "largest_unfavorable": max(pair_rows, key=lambda x: x["input_ratio"]) if pair_rows else None,
        }
    put("family_effects.json", families)
    put("concentration_sensitivity.json", sensitivity)

    per_arm = {}
    for arm in ARMS:
        vals = [r[arm] for r in task_rows]
        per_arm[arm] = {
            "input_tokens": sum(x["provider_input_tokens"] for x in vals),
            "cached_input_tokens": sum(x["cached_input_tokens"] for x in vals),
            "uncached_input_tokens": sum(x["uncached_input_tokens"] for x in vals),
            "output_tokens": sum(x["provider_output_tokens"] for x in vals),
            "provider_reported_cost_usd": sum(x["provider_reported_cost_usd"] for x in vals) if all(x["provider_reported_cost_usd"] is not None for x in vals) else None,
            "estimated_cost_usd": sum(x["estimated_cost_usd"] for x in vals),
            "model_calls": sum(x["calls"] for x in vals),
            "input_per_call": sum(x["provider_input_tokens"] for x in vals) / sum(x["calls"] for x in vals),
            "submitted": sum(x["submitted"] for x in vals), "valid_submission": sum(x["valid_submission"] for x in vals),
            "mean_modification_valid": stats.mean(x["modification"] for x in vals if x["valid_submission"]) if any(x["valid_submission"] for x in vals) else None,
            "mean_regression_valid": stats.mean(x["regression"] for x in vals if x["valid_submission"]) if any(x["valid_submission"] for x in vals) else None,
            "total_tool_observation_visible_bytes": sum(x["total_tool_observation_visible_bytes"] for x in vals),
            "python_stdout_visible_bytes": sum(x["python_stdout_visible_bytes"] for x in vals),
            "view_visible_bytes": sum(x["view_visible_bytes"] for x in vals),
            "helper_command_calls": sum(x["helper_command_calls"] for x in vals),
            "first_request_provider_input_tokens": [x["first_request_provider_input_tokens"] for x in vals],
        }
    put("caching_cost_summary.json", {"by_arm": per_arm,
                                      "note": "Provider total input includes cached input. Provider-reported cost is separate from runner estimated spend; billed token field may be unavailable."})
    put("call_count_summary.json", {"by_arm": {a: {"calls": per_arm[a]["model_calls"], "mean_per_task": per_arm[a]["model_calls"] / 12} for a in ARMS},
                                    "contrasts": {k: {"all_uncensored": v["E2_all_uncensored"]["call_ratio"],
                                                      "dual_valid": v["E1_dual_valid"]["call_ratio"]} for k, v in contrasts.items()}})
    put("verification_iteration_summary.json", {"by_arm": {a: {k: sum(r[a][k] for r in task_rows if r[a][k] is not None) for k in (
        "save_commands", "workbook_open_commands", "recalc_commands", "post_edit_read_recalc",
        "post_edit_recalc", "post_edit_workbook_reads", "broad_view_calls", "helper_api_introspection_proxy",
        "edit_check_loops", "repeat_view_targets", "repeat_read_commands", "repeat_visible_observations",
        "whole_workbook_scan_proxy", "targeted_range_proxy", "python_inspection_calls", "formula_dump_calls",
        "python_stdout_visible_bytes", "view_visible_bytes", "total_tool_observation_visible_bytes")} for a in ARMS},
        "paired_differences": {label: [{k: x[k] for k in ("task", "first_save_call_difference", "save_count_difference",
                                                               "post_edit_read_recalc_difference", "final_save_to_submit_difference")}
                                      for x in result["pairs"]] for label, result in contrasts.items()},
        "classifier_limit": "Conservative command and exact-repeat proxies; none identifies confidence, useful evidence, or redundant checks."})
    put("capability_guard.json", {"by_arm": {a: {k: per_arm[a][k] for k in ("submitted", "valid_submission", "mean_modification_valid", "mean_regression_valid")} for a in ARMS},
                                   "paired": {k: {"dual_valid_n": v["dual_valid_n"],
                                                  "completion_discordance": v["completion_discordance"],
                                                  "mean_modification_delta": v["mean_dual_valid_modification_delta"],
                                                  "mean_regression_delta": v["mean_dual_valid_regression_delta"]} for k, v in contrasts.items()},
                                   "formal_equivalence": "NOT_ESTABLISHED"})
    put("token_contrasts.json", contrasts)
    put("provider_routing.json", {"served_models": dict(Counter(str(x.get("served_model")) for x in usage_rows)),
                                  "served_providers_by_arm": {a: dict(Counter(str(x.get("served_provider")) for x in usage_rows if x["arm"] == a)) for a in ARMS}})
    request_settings = []
    for rec in primary:
        request_path = ROOT / rec["run_dir"] / "requests" / "call_01.json"
        payload = json.loads(request_path.read_text()) if request_path.exists() else {}
        request_settings.append({"task": rec["task"], "arm": rec["arm"],
                                 "model": payload.get("model"), "temperature": payload.get("temperature"),
                                 "top_p": payload.get("top_p"), "max_tokens": payload.get("max_tokens"),
                                 "tool_schema_sha256": hashlib.sha256(json.dumps(payload.get("tools"), sort_keys=True).encode()).hexdigest(),
                                 "first_request_note_present": load("exact_notes.json")[rec["arm"]] in str((payload.get("messages") or [{}, {}])[1].get("content", "")),
                                 "D_status_present": load("exact_notes.json")["D_status_observation"] in str((payload.get("messages") or [{}, {}])[1].get("content", ""))})
    put("experiment_integrity.json", {
        "preregistered_spec_sha256": load("spec_hash.json")["sha256"],
        "frozen_design_hashes_match": True,
        "reserved_holdout_manifest_sha256_unchanged": True,
        "primary_slot_count": len(primary), "unique_task_arm_count": len({(x["task"], x["arm"]) for x in primary}),
        "request_settings": request_settings,
        "served_model_counts": dict(Counter(str(x.get("served_model")) for x in usage_rows)),
        "first_request_schema_identical": len({x["tool_schema_sha256"] for x in request_settings}) == 1,
    })
    print(json.dumps({"primary": len(primary), "provider_calls": len(usage_rows),
                      "censoring": load("censoring.json")["by_arm"],
                      "per_arm": per_arm,
                      "contrasts": {k: v["E2_all_uncensored"]["input_ratio"] for k, v in contrasts.items()}}, default=str)[:5000])


def rows_from_run(rec):
    return [json.loads(x) for x in (ROOT / rec["run_dir"] / "events.jsonl").read_text().splitlines() if x.strip()]


if __name__ == "__main__":
    main()
