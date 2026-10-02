"""Materialize a navigable, post-run index of the frozen token claim study.

This script does not rerun, re-score, or change the preregistered experiment.
Its outputs are explicitly retrospective aliases or summaries of archived data.
"""

from __future__ import annotations

import collections
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/history/token_claim_discovery"


def read(name: str):
    return json.loads((OUT / name).read_text())


def put(name: str, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def copy_alias(target: str, source: str):
    shutil.copyfile(OUT / source, OUT / target)


def historical_detail():
    records = []
    checkpoint_scores = {
        (s["task_id"], s["arm"]): s
        for s in json.loads((ROOT / "research/history/representative_architecture_checkpoint/capability_scores.json").read_text())
    }
    for path in sorted((ROOT / "research/history/representative_architecture_checkpoint/reps").glob("*/run_record.json")):
        r = json.loads(path.read_text())
        e = r.get("efficiency") or {}
        score = checkpoint_scores.get((r.get("task_id"), r.get("arm")), {})
        records.append({
            "study": "representative_architecture_checkpoint", "task": r.get("task_id"),
            "family": r.get("family"), "arm": r.get("arm"), "requested_model": r.get("model"),
            "served_provider": None, "completion_state": r.get("status"), "censoring": r.get("censoring"),
            "provider_input_tokens": e.get("prompt_tokens"), "provider_output_tokens": e.get("completion_tokens"),
            "cached_input_tokens": None, "reasoning_tokens": None, "billed_tokens": None,
            "cost_usd": e.get("cost_usd"), "model_calls": e.get("api_calls"),
            "python_calls": e.get("python_execs"), "helper_calls": e.get("helper_calls"),
            "helper_exposure": "fixed_across_H0_H1", "treatment_contact": r.get("first_contact_turn"),
            "official_score": {"exact": score.get("official_exact"), "modification": score.get("official_modification"),
                               "regression": score.get("official_regression")},
            "source": str(path.relative_to(ROOT)),
        })
    for study in ("token_claim_discovery", "token_affordance_discovery"):
        study_dir = ROOT / study
        scores = {(s["task"], s["arm"]): s for s in json.loads((study_dir / "official_scores.json").read_text())["rows"]}
        usage = collections.defaultdict(list)
        for u in rows(study_dir / "provider_usage.jsonl"):
            usage[(u["task"], u["arm"])].append(u)
        events = collections.defaultdict(list)
        event_path = study_dir / ("inspection_events.jsonl" if study == "token_claim_discovery" else "trajectory_events.jsonl")
        for ev in rows(event_path):
            if ev.get("task") and ev.get("arm"):
                events[(ev["task"], ev["arm"])].append(ev)
        for r in rows(study_dir / "primary_runs.jsonl"):
            key = (r["task"], r["arm"])
            calls = usage[key]
            evs = events[key]
            score = scores.get(key, {})
            records.append({
                "study": study, "task": r["task"], "family": r["family"], "arm": r["arm"],
                "requested_model": "z-ai/glm-5.3-flash", "served_models": sorted({u.get("served_model") for u in calls}),
                "served_providers": dict(collections.Counter(u.get("served_provider") for u in calls)),
                "completion_state": r["status"], "censoring": r["censoring"],
                "provider_input_tokens": r["prompt_tokens"], "provider_output_tokens": r["completion_tokens"],
                "cached_input_tokens": sum(u.get("cached_input_tokens") or 0 for u in calls),
                "reasoning_tokens": sum(u.get("reasoning_tokens") or 0 for u in calls),
                "billed_tokens": None,
                "provider_reported_cost_usd": sum(u.get("reported_cost_usd") or 0 for u in calls),
                "runner_estimated_cost_usd": r.get("cost_usd_estimate"), "model_calls": r["api_calls"],
                "visible_observation_bytes": sum(e.get("observation_bytes_model_visible") or 0 for e in evs),
                "view_xlsx_calls": sum(e.get("tool") == "view_xlsx" for e in evs),
                "broad_view_calls": sum(bool(e.get("broad_view")) for e in evs),
                "bash_calls": sum(e.get("tool") == "bash" for e in evs),
                "helper_exposure": r.get("helper_exposed"),
                "helper_adoption": bool(study == "token_claim_discovery" and key == ("Financial_Model:09_02", "B")),
                "official_score": {"exact": score.get("exact"), "modification": score.get("modification"),
                                   "regression": score.get("regression")},
                "valid_submission": score.get("valid_submission"),
                "source": f"{study}/primary_runs.jsonl",
            })
    summary = read("historical_token_summary.json")
    summary["task_arm_records"] = records
    summary["task_arm_record_count"] = len(records)
    summary["task_arm_note"] = (
        "Task records include two later discovery studies for independent retrospective audit; "
        "they were not available to select the original 2026-09-22 cohort. Missing fields remain null. "
        "Overlapping cohorts and study phases must not be pooled as independent evidence."
    )
    put("historical_token_summary.json", summary)


def main():
    original_spec = read("spec_hash.json")["sha256"]
    if digest(OUT / "preregistered_spec.json") != original_spec:
        raise RuntimeError("frozen preregistration changed")
    historical_detail()
    aliases = {
        "population_candidates.json": "selection_manifest.json",
        "population_selection.json": "selection_manifest.json",
        "representative_reserve.json": "future_validation_reservation.json",
        "arm_definitions.json": "arm_configs.json",
        "prompt_notes.json": "exact_notes.json",
        "run_records.jsonl": "primary_runs.jsonl",
        "inspection_telemetry.jsonl": "inspection_events.jsonl",
        "scores.json": "official_scores.json",
        "mechanism_analysis.json": "mechanism_adjudication.json",
        "decision.json": "discovery_gate.json",
    }
    for target, source in aliases.items():
        copy_alias(target, source)
    variance = read("variance_estimates.json")
    sd = variance["task_log_ratio_sd"]
    variance["power_note"] = (
        "Retrospective calculation using an earlier, different-mechanism paired log-ratio SD; "
        "the original 15-task preregistration was directional discovery, not powered confirmation."
    )
    variance["approximate_paired_tasks_for_80pct_power_two_sided_alpha_0_05"] = {
        f"{int(effect * 100)}pct_reduction": round(((1.96 + 0.84) * sd / abs(__import__('math').log(1 - effect))) ** 2)
        for effect in (0.10, 0.20, 0.30)
    }
    variance["approximate_95pct_log_effect_half_width_at_n_15"] = 1.96 * sd / (15 ** 0.5)
    put("historical_variance_analysis.json", variance)
    tasks = read("task_token_summary.json")
    for task in tasks:
        effects = {}
        for numerator, denominator in (("B", "A"), ("C", "A"), ("D", "A"), ("D", "B"), ("D", "C")):
            high, low = task[numerator], task[denominator]
            p, q = high["provider_input_tokens"], low["provider_input_tokens"]
            effects[f"{numerator}_vs_{denominator}"] = {
                "paired_input_ratio": p / q if p and q else None,
                "paired_percent_change": 100 * (p / q - 1) if p and q else None,
                "both_valid": bool(high["valid_submission"] and low["valid_submission"]),
                "both_uncensored": high["censoring"] != "PROVIDER_CENSORED" and low["censoring"] != "PROVIDER_CENSORED",
            }
        task["paired_effects"] = effects
    put("task_level_token_effects.json", tasks)
    put("family_level_token_effects.json", read("factorial_effects.json")["family_effects_with_ci"])
    put("provider_config.json", {
        "original_config": read("arm_configs.json"),
        "actual_routing": read("provider_routing.json"),
        "provider_tool_schemas": read("helper_schemas.json")["provider_tool_schemas_all_arms"],
        "reasoning_level": None,
        "reasoning_level_note": "No explicit reasoning setting in archived request configuration; served response reasoning tokens are preserved per call.",
        "base_scaffold_source": "benchmark/sweagent/spreadsheet-control.yaml via benchmark/ab_local_runner.py load_templates()",
        "provenance": "retrospective index of frozen arm configs, schemas, and per-call routing",
    })
    task_lookup = {(t["task"], arm): t[arm] for t in tasks for arm in "ABCD"}
    completion_rows = []
    for r in read("censoring.json")["rows"]:
        t = task_lookup.get((r["task"], r["arm"]), {})
        completion_rows.append({**r, "valid_submission": t.get("valid_submission"),
                                "modification": t.get("modification"), "regression": t.get("regression")})
    put("completion_table.json", {"rows": completion_rows, "by_arm": read("censoring.json")["by_arm"]})
    put("paired_scores.json", read("capability_guard.json")["paired_score_deltas"])
    helper_events = []
    for e in rows(OUT / "inspection_events.jsonl"):
        if "lx_helpers" in json.dumps(e.get("arguments", {})):
            helper_events.append(e)
    with (OUT / "helper_telemetry.jsonl").open("w") as stream:
        for e in helper_events:
            stream.write(json.dumps(e, sort_keys=True) + "\n")
    put("helper_telemetry_summary.json", {
        "archived_helper_events": len(helper_events),
        "adoption_audit": read("mechanism_adjudication.json")["helper_audit"],
        "caution": "Text matching is an event index; adoption and displacement follow the transcript audit.",
    })
    reserve = read("representative_reserve.json")
    held = set(sum(reserve["tasks"].values(), []))
    prior_h1 = set()
    for path in (ROOT / "research/history/representative_architecture_checkpoint/reps").glob("*/run_record.json"):
        r = json.loads(path.read_text())
        if r.get("arm") == "H1":
            prior_h1.add(r.get("task_id"))
    put("reserve_integrity_audit.json", {
        "new_token_claim_treatment_on_reserve": False,
        "later_affordance_treatment_on_reserve": False,
        "historical_prior_H1_overlap": sorted(held & prior_h1),
        "interpretation": "No treatment was run on the reserve after its creation. Two tasks already had earlier, different-architecture H1 runs; a future representative claim-validation design must assess this prior exposure.",
    })
    manifest = {
        "status": "POST_RUN_INDEX_OF_FROZEN_NEGATIVE_DISCOVERY",
        "frozen_spec_sha256": original_spec,
        "primary_freeze_sha256": digest(OUT / "primary_freeze.json"),
        "entries": {},
    }
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "final_result_hash_manifest.json":
            manifest["entries"][path.name] = digest(path)
    manifest["root_reports"] = {
        name: digest(ROOT / name)
        for name in ("research/reports/TOKEN_EFFICIENCY_CLAIM_DISCOVERY_REPORT.md", "research/reports/CLAIM_BACKLOG.md")
    }
    put("final_result_hash_manifest.json", manifest)


if __name__ == "__main__":
    main()
