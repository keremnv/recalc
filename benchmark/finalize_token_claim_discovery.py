#!/usr/bin/env python3
"""Adjudicate frozen token-claim evidence without model calls or rescoring.

This script only writes derived analysis and handoff artifacts. It refuses to
continue if the preregistration, primary outcomes, or reserved cohort changed.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/history/token_claim_discovery"
CENSORED = {"PROVIDER_CENSORED", "RUNNER_CENSORED", "WORKBOOK_INFRA_CENSORED"}


def read(name):
    return json.loads((OUT / name).read_text())


def lines(name):
    return [json.loads(s) for s in (OUT / name).read_text().splitlines() if s.strip()]


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def geo(values):
    return math.exp(st.mean(math.log(x) for x in values)) if values else None


def main():
    freeze = read("primary_freeze.json")
    for name, expected in freeze["files_sha256"].items():
        actual_name = "provider_usage_raw.jsonl" if name == "provider_usage.jsonl" else name
        actual = hashlib.sha256((OUT / actual_name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"frozen evidence changed: {name}")
    primary = lines("primary_runs.jsonl")
    if len(primary) != 60 or len({(x["task"], x["arm"]) for x in primary}) != 60:
        raise RuntimeError("incomplete or duplicate primary slots")
    reserved = set(read("future_validation_reservation.json")["tasks"])
    selected = set(read("population.json")["tasks"])
    if reserved & selected:
        raise RuntimeError("future validation reservation overlaps discovery")
    if any(r["task"] in reserved for r in primary):
        raise RuntimeError("future validation task was run")

    scores = read("official_scores.json")["rows"]
    if len(scores) != 60:
        raise RuntimeError("official score record incomplete")
    scoring_diagnostics = [x for x in scores if x["submitted"] and x["scorer_error"]]
    if any(not str(x["scorer_error"]).startswith(("Modification error at ", "Regression error at ")) for x in scoring_diagnostics):
        raise RuntimeError("submitted workbook has non-mismatch scorer error; inspect manually")
    if sum(x["valid_submission"] for x in scores) != sum(x["submitted"] for x in primary):
        raise RuntimeError("submitted workbook did not reach scorer as a valid workbook")

    raw_usage = lines("provider_usage_raw.jsonl")
    final_usage = lines("provider_usage.jsonl")
    if len(raw_usage) != 1175 or len(final_usage) != sum(x["api_calls"] for x in primary):
        raise RuntimeError("provider-call lineage differs from recorded interruption")
    by_arm = defaultdict(list)
    for u in final_usage:
        by_arm[u["arm"]].append(u)
    if any(sum(u["prompt_tokens"] for u in by_arm[a]) != sum(r["prompt_tokens"] for r in primary if r["arm"] == a) for a in "ABCD"):
        raise RuntimeError("selected provider calls do not reconcile with primary tokens")

    tasks = read("task_token_summary.json")
    fx = read("factorial_effects.json")
    behavior = read("inspection_behavior.json")
    trajectory = read("trajectory_decomposition.json")
    capability = read("capability_guard.json")
    censoring = read("censoring.json")
    tool_events = lines("mechanism_events.jsonl")
    helper_calls = [e for e in tool_events if e.get("helper_mentioned") and e.get("arm") in "BD"]
    helper_success = [e for e in helper_calls if e.get("returncode") == 0]
    if any(e["task"] != "Financial_Model:09_02" or e["arm"] != "B" for e in helper_calls):
        raise RuntimeError("helper invocation set changed; re-audit")

    paired = {}
    for label, tr, co in (("D_vs_A", "D", "A"), ("C_vs_A", "C", "A"), ("B_vs_A", "B", "A"), ("D_vs_C", "D", "C")):
        rows = [r for r in tasks if r[tr]["censoring"] not in CENSORED and r[co]["censoring"] not in CENSORED]
        paired[label] = {
            "n": len(rows),
            "geometric_call_count_ratio": geo([r[tr]["calls"] / r[co]["calls"] for r in rows]),
            "geometric_input_tokens_per_call_ratio": geo([r[tr]["mean_input_tokens_per_call"] / r[co]["mean_input_tokens_per_call"] for r in rows]),
            "geometric_total_input_ratio": geo([r[tr]["provider_input_tokens"] / r[co]["provider_input_tokens"] for r in rows]),
            "completion_discordances": [
                {"task": r["task"], "treatment": r[tr]["status"], "control": r[co]["status"]}
                for r in rows if r[tr]["valid_submission"] != r[co]["valid_submission"]
            ],
        }

    robust = [r for r in tasks if r["A"]["censoring"] not in CENSORED and r["D"]["censoring"] not in CENSORED]
    omitted = {"Template:01_05", "Template:04_04"}
    after = [r["D"]["provider_input_tokens"] / r["A"]["provider_input_tokens"] for r in robust if r["task"] not in omitted]
    effect = fx["contrasts"]
    caching = {
        a: {
            "provider_input_tokens": sum(u["prompt_tokens"] for u in by_arm[a]),
            "reported_cached_input_tokens": sum(u.get("cached_input_tokens") or 0 for u in by_arm[a]),
            "input_tokens_minus_reported_cached": sum(u["prompt_tokens"] - (u.get("cached_input_tokens") or 0) for u in by_arm[a]),
            "provider_output_tokens": sum(u["completion_tokens"] for u in by_arm[a]),
            "provider_reported_cost_usd": sum(u.get("reported_cost_usd") or 0 for u in by_arm[a]),
        }
        for a in "ABCD"
    }

    audit = {
        "phase": "POST_PRIMARY_ANALYSIS_CORRECTION",
        "primary_and_preregistration_unchanged": True,
        "official_scorer_rerun": False,
        "model_calls_added": 0,
        "score_validity_error": "An error_message may describe a scored cell mismatch. It does not by itself invalidate a submitted workbook.",
        "submitted_scored_workbooks": sum(x["valid_submission"] for x in scores),
        "submitted_with_ordinary_mismatch_diagnostics": len(scoring_diagnostics),
        "previously_misclassified_submitted_workbooks": len(scoring_diagnostics),
        "raw_provider_call_rows": len(raw_usage),
        "superseded_rows_from_interrupted_partial_block": len(raw_usage) - len(final_usage),
        "selected_provider_call_rows": len(final_usage),
        "selection_rule": "last successful record per task/arm/call, reconciled exactly to each frozen primary run",
        "raw_provider_ledger_frozen_hash_preserved": True,
        "all_archived_successful_requests_decomposed": len(lines("request_decomposition_exact.jsonl")) == len(final_usage),
        "no_replications": (OUT / "replication_runs.jsonl").stat().st_size == 0,
        "future_validation_population_untouched": True,
        "limits": [
            "The workbook evaluator supplies accuracy scores for missing workbooks too; valid submission additionally requires the frozen SUBMITTED status and an output file.",
            "View/scan classifiers are syntactic proxies, not proof of semantic usefulness.",
            "cl100k local token estimates are not the model-native/provider token count.",
        ],
    }
    write("analysis_audit.json", audit)

    mechanism = {
        "paired_trajectory_decomposition": paired,
        "D_vs_A_e2_median_ratio": effect["D_vs_A"]["E2_all_uncensored"]["median_ratio"],
        "D_vs_A_e2_geometric_ratio": effect["D_vs_A"]["E2_all_uncensored"]["geometric_mean_ratio"],
        "D_vs_A_without_two_extreme_template_tasks": {
            "omitted": sorted(omitted), "n": len(after), "median_ratio": st.median(after), "geometric_mean_ratio": geo(after)
        },
        "per_arm_caching_and_cost": caching,
        "visible_observation_bytes_by_arm": {a: behavior[a]["observation_bytes"] for a in "ABCD"},
        "broad_view_calls_by_arm": {a: behavior[a]["broad_views"] for a in "ABCD"},
        "python_stdout_bytes_by_arm": {a: behavior[a]["python_stdout_bytes"] for a in "ABCD"},
        "cumulative_prior_observation_bytes_by_arm": {a: trajectory[a]["cumulative_prior_observation_bytes"] for a in "ABCD"},
        "helper_audit": {
            "runs_with_actual_helper_calls": 1,
            "task": "Financial_Model:09_02", "arm": "B", "type": "search",
            "command_calls": len(helper_calls), "successful_command_calls": len(helper_success),
            "failed_command_calls": len(helper_calls) - len(helper_success),
            "model_visible_bytes_all_helper_commands": sum(e.get("observation_bytes_model_visible", 0) for e in helper_calls),
            "model_visible_bytes_successful_helper_commands": sum(e.get("observation_bytes_model_visible", 0) for e in helper_success),
            "command_rendering_cell_hits": 1,
            "audit_note": "Transcript shows one type/iteration probe and one loop over result-object keys before the final command printed cell hits; return code 0 alone is not useful adoption.",
            "D_arm_helper_calls": 0,
            "displacement_established": False,
            "reason": "One B run used the helper, but subsequent broad Python output and trajectory differences prevent mechanical attribution of the arm-level token contrast to displaced inspection."
        },
        "observation_burden_hypothesis_supported": False,
        "observation_burden_reason": "Broad view_xlsx calls fell, but total model-visible observation bytes and Python stdout bytes rose in D versus A; paired token reduction was driven mainly by fewer calls, with higher input tokens per call.",
        "interaction": fx["overall_effects_with_ci"]["interaction"],
        "capability": {
            "submitted": capability["submitted"], "valid": capability["valid"],
            "D_vs_A_paired_modification_mean_delta": capability["paired_score_deltas"]["D_vs_A"]["mean_modification_delta"],
            "D_vs_A_paired_regression_mean_delta": capability["paired_score_deltas"]["D_vs_A"]["mean_regression_delta"],
            "D_vs_A_submission_discordance": paired["D_vs_A"]["completion_discordances"],
            "formal_equivalence": "NOT_ESTABLISHED",
        },
    }
    write("mechanism_adjudication.json", mechanism)

    gate = {
        "D_vs_A_median_reduction_ge_10pct": True,
        "favorable_two_families": True,
        "not_one_or_two_pathological_tasks": False,
        "capability_guard_pass": False,
        "capability_guard_interpretation": "Cannot affirmatively establish preservation: D had 9 valid submissions versus A's 10, with two A-only and one D-only valid submissions, and mixed paired modification deltas. No reproducible degradation is proven either.",
        "coherent_mechanism": False,
        "component_material_descriptively": True,
        "component_material": True,
        "component_mechanism_identified": False,
        "salience_mechanism_supported": False,
        "helper_mechanism_supported": False,
        "interaction_supported": False,
        "discovered": False,
        "primary_verdict": "TOKEN_EFFECT_TRAJECTORY_NOISE",
        "verdict_scope": "The observed paired token movement is mixed and dominated by trajectory length and two Template tasks. This is not proof that every product-facing effect is zero.",
        "holdout_validation_justified": False,
        "reason": "D/A E2 median clears 10% narrowly but reverses after omitting two extreme Template tasks; its CI crosses 1, Debugging median is adverse, helper adoption is one B run and zero D runs, observation burden does not fall, and capability preservation is not established.",
    }
    write("discovery_gate.json", gate)
    write("replication_decision.json", {
        "eligible_conditions": ["one-arm provider censoring", "D/A completion discordance", "extreme >3x task ratios"],
        "replication_runs": 0,
        "reason_not_run": "The primary result is already frozen and fails the mechanism and robustness gates. Targeted repeats could diagnose pathologies but cannot rescue this preregistered discovery gate or turn this cohort into holdout validation.",
        "primary_results_unchanged": True,
    })
    write("next_action.json", {
        "single_next_action": "Independent GPT-6 Astra forensic review of the frozen packet; no live treatment or holdout calls.",
        "after_review_if_refinement_warranted": "Choose one smallest evidence-grounded model-facing integration change, assign a new RC/profile identity, use a fresh discovery cohort, and preregister again.",
        "product_rc_unchanged": True,
        "architecture_discovery": "CLOSED",
        "future_validation_population": "RESERVED_UNTOUCHED",
        "public_token_claim": "NOT_READY",
    })
    print(json.dumps({"audit": audit, "gate": gate}, sort_keys=True))


if __name__ == "__main__":
    main()
