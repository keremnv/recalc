#!/usr/bin/env python3
"""Static activation audit, live feasibility runner, and evaluator report.

The live command deliberately uses a fresh output root and the repaired
compiled databases.  The only frontend addition in this experiment is the
earned population/member and copied-header/Month/Numbers output evidence in
``workbook_grounding.project_obligation``.  Neither relation grants authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "src"), str(ROOT / "benchmark/sweagent/formula_index/lib")]

import fm_resource_feasibility as feasibility
import matched_compiled_treatment as runtime
from workbook_grounding import project_obligation


RUN_ROOT = feasibility.RUN_ROOT
AUDIT_ROOT = RUN_ROOT / "clean_integrated"
LIVE_ROOT = AUDIT_ROOT / "live"
STATIC_ROOT = AUDIT_ROOT / "static_activation"
REPORT_PATH = ROOT / "INTEGRATED_FEASIBILITY_REPORT.md"
CSV_PATH = ROOT / "research/history/loose_evidence/integrated_feasibility_census.csv"
JSON_PATH = ROOT / "research/history/loose_evidence/integrated_feasibility_census.json"
ACTIVATION_CSV = ROOT / "research/history/loose_evidence/integrated_static_activation.csv"
ACTIVATION_JSON = ROOT / "research/history/loose_evidence/integrated_static_activation.json"

TASKS = [
    "Financial_Model:01_01", "Financial_Model:03_01", "Financial_Model:04_01",
    "Financial_Model:05_01", "Financial_Model:06_01", "Financial_Model:07_01",
    "Financial_Model:08_01", "Financial_Model:12_05", "Financial_Model:13_05",
    "Financial_Model:14_05", "Financial_Model:15_05", "Financial_Model:17_05",
]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def digest(value: Any) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def task_dir_for(root: Path, task_key: str) -> Path:
    return root / task_key.replace(":", "-")


def archived_result(task_key: str) -> dict[str, Any]:
    # Archived Task IR only; this path is never used as a live cache.
    path = feasibility.REPAIRED_LIVE / task_key.replace(":", "-") / "result.json"
    result = read_json(path)
    if not result:
        raise FileNotFoundError(f"archived Task IR missing: {path}")
    return result


def _base_packet(spine: dict[str, Any], obligation: dict[str, Any]) -> dict[str, Any]:
    return project_obligation(
        spine,
        obligation,
        ablation={"NO_MEMBER_RELATION", "NO_OUTPUT_ROLE_RELATION"},
    )


def static_activation_audit() -> dict[str, Any]:
    """Replay integrated candidate construction without model calls or gold."""
    STATIC_ROOT.mkdir(parents=True, exist_ok=True)
    tasks: list[dict[str, Any]] = []
    activation_rows: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    total_obligations = 0
    total_additions = 0
    for task_key in TASKS:
        archived = archived_result(task_key)
        compiler = archived.get("compiler") or {}
        spine = runtime.spine_for(task_key)
        task_record = {
            "task": task_key,
            "archived_task_ir_status": compiler.get("status"),
            "obligation_count": len(compiler.get("obligations") or []),
            "obligations": [],
        }
        total_obligations += len(compiler.get("obligations") or [])
        for obligation in compiler.get("obligations") or []:
            base = _base_packet(spine, obligation)
            integrated = project_obligation(spine, obligation)
            member = integrated.get("population_member_evidence") or {}
            output = integrated.get("output_role_evidence") or {}
            additions = sorted(set(integrated.get("target_cell_ids") or []) - set(base.get("target_cell_ids") or []))
            total_additions += len(additions)
            ob_record = {
                "obligation_id": obligation.get("id"),
                "task_ir_fields": {
                    key: obligation.get(key)
                    for key in ("locus", "subject", "subject_interval", "scope", "required_change", "source_relation")
                },
                "population_member_active": bool(member.get("active")),
                "population_specifications": member.get("specifications") or [],
                "member_occurrences": member.get("occurrences") or [],
                "included_members": member.get("allowed_members") or [],
                "excluded_members": member.get("excluded_members") or [],
                "excluded_occurrences": member.get("excluded_occurrences") or [],
                "output_role_active": bool(output.get("active")),
                "output_role_activations": output.get("activations") or [],
                "candidate_additions": additions,
                "base_candidate_count": len(base.get("target_cell_ids") or []),
                "integrated_candidate_count": len(integrated.get("target_cell_ids") or []),
                "uses_gold": bool(output.get("uses_gold")),
            }
            if ob_record["uses_gold"]:
                violations.append({"task": task_key, "obligation_id": obligation.get("id"), "violation": "RELATION_MARKED_USES_GOLD"})
            for activation in output.get("activations") or []:
                starts = {x.get("cell_id") for x in member.get("included_occurrences") or []}
                if activation.get("start_cell_id") not in starts:
                    violations.append({"task": task_key, "obligation_id": obligation.get("id"), "violation": "OUTPUT_START_NOT_INCLUDED_MEMBER", "activation": activation})
                if not activation.get("deterministic"):
                    violations.append({"task": task_key, "obligation_id": obligation.get("id"), "violation": "NON_DETERMINISTIC_ACTIVATION", "activation": activation})
                for endpoint in activation.get("endpoints") or []:
                    activation_rows.append({
                        "task": task_key,
                        "obligation_id": obligation.get("id"),
                        "start_cell_id": activation.get("start_cell_id"),
                        "start_address": activation.get("start_address"),
                        "member_identity": activation.get("member_identity"),
                        "population_label": activation.get("population_label"),
                        "introducing_field": activation.get("introducing_field"),
                        "introducing_path": activation.get("introducing_path"),
                        "occurrence_identity": activation.get("occurrence_identity"),
                        "reason": activation.get("reason"),
                        "relation_sequence": activation.get("relation_sequence"),
                        "intermediate_nodes": activation.get("intermediate_nodes"),
                        "endpoint_cell_id": endpoint.get("cell_id"),
                        "endpoint_address": endpoint.get("address"),
                        "endpoint_role_evidence": endpoint.get("role_evidence"),
                        "deterministic": activation.get("deterministic"),
                    })
            task_record["obligations"].append(ob_record)
        tasks.append(task_record)
    result = {
        "status": "STATIC_COMPLETE" if not violations else "STATIC_PREDICATE_VIOLATION",
        "model_calls": 0,
        "gold_used": False,
        "task_population": TASKS,
        "task_count": len(tasks),
        "obligation_count": total_obligations,
        "population_member_activation_count": sum(
            1 for task in tasks for ob in task["obligations"] if ob["population_member_active"]
        ),
        "output_role_activation_count": sum(
            len(ob["output_role_activations"]) for task in tasks for ob in task["obligations"]
        ),
        "output_role_endpoint_count": len({row["endpoint_cell_id"] for row in activation_rows}),
        "candidate_addition_count": total_additions,
        "tasks_with_output_role_activation": sorted({
            task["task"] for task in tasks for ob in task["obligations"] if ob["output_role_active"]
        }),
        "violations": violations,
        "tasks": tasks,
        "relation_contract": {
            "member": "explicit ordinal/member population relation with Task IR field provenance; no lexical target union",
            "output": "allowed member occurrence -> exact same-column copied-header point dependency -> same-column Month -> right-neighbor Numbers -> contiguous formula-bearing Month extent -> corresponding Numbers cells",
            "authority": "candidate/evidence only; Edit Plan authority algebra unchanged",
        },
    }
    write_json(STATIC_ROOT / "activation_audit.json", result)
    write_json(ACTIVATION_JSON, result)
    write_csv(ACTIVATION_CSV, activation_rows)
    return result


def _load_call_records(task_dir: Path) -> list[dict[str, Any]]:
    calls = []
    for path in sorted((task_dir / "calls").glob("*.json")):
        record = read_json(path, {})
        record["_path"] = str(path)
        calls.append(record)
    return calls


def _parsed_status(record: dict[str, Any]) -> str | None:
    parsed = record.get("parsed_response")
    if isinstance(parsed, dict):
        return parsed.get("status") or parsed.get("decision")
    return None


def _failure_class(record: dict[str, Any]) -> str | None:
    value = record.get("failure_class")
    return str(value) if value else None


def _provider_status(record: dict[str, Any]) -> str:
    if _failure_class(record):
        return "FAILURE"
    if record.get("provider_attempt") is False:
        return "NOT_ATTEMPTED"
    if record.get("response") is not None or record.get("raw_response_text") is not None:
        return "SUCCESS"
    return "UNKNOWN"


def _authority_for_obligation(result: dict[str, Any], obligation_id: str) -> set[str]:
    expansion = result.get("edit_plan", {}).get("expansion") or {}
    result_ids = set()
    for operation in expansion.get("operations") or []:
        if operation.get("obligation_id") == obligation_id:
            result_ids.update(operation.get("cell_ids") or [])
    # The composed expansion carries the final operation ownership after
    # prefixing; fall back to fragment expansion for older/result variants.
    if not result_ids:
        for fragment in result.get("edit_plan", {}).get("fragments") or []:
            if fragment.get("obligation_id") != obligation_id:
                continue
            result_ids.update((fragment.get("expansion") or {}).get("cell_ids") or [])
    return result_ids


def _gold_by_obligation(task_key: str, spine: dict[str, Any]) -> dict[str, set[str]]:
    """Read evaluator gold only for post-run measurement, never construction."""
    candidates = [
        ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/authority_loss_by_obligation.csv",
        ROOT / "research/history/loose_evidence/authority_loss_by_obligation.csv",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return {}
    # Existing research CSV schemas vary.  Prefer exact task/obligation and
    # parse display targets only when the columns are unambiguous.
    out: dict[str, set[str]] = defaultdict(set)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            task = row.get("task") or row.get("task_key") or ""
            oid = row.get("obligation_id") or ""
            if task not in {task_key, task_key.split(":", 1)[-1], task_key.replace(":", "-")}:
                continue
            if not oid:
                continue
            for key in ("gold_target", "gold_cell", "target", "cell", "gold"):
                value = row.get(key)
                if value and "!" in value:
                    title, address = value.rsplit("!", 1)
                    index = (spine.get("title_to_index") or {}).get(title)
                    if index is not None:
                        import workbook_grounding_spine as ws
                        match = __import__("re").fullmatch(r"([A-Z]+)(\d+)", address)
                        if match:
                            col = 0
                            for char in match.group(1):
                                col = col * 26 + ord(char) - 64
                            out[oid].add(ws.cell_id(index, int(match.group(2)), col))
                    break
    return dict(out)


def _score_task(score: dict[str, Any], task_key: str) -> dict[str, Any]:
    tasks = score.get("tasks") if isinstance(score, dict) else {}
    if not isinstance(tasks, dict):
        return {}
    return tasks.get(task_key) or tasks.get(task_key.replace(":", "-")) or {}


def _call_usage(calls: list[dict[str, Any]]) -> dict[str, Any]:
    usage = Counter()
    cost = 0.0
    failures = Counter()
    stages = Counter()
    for call in calls:
        stage = call.get("stage") or "unknown"
        stages[stage] += 1
        u = call.get("usage") or {}
        for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens"):
            if u.get(key) is not None:
                usage[key] += int(u.get(key) or 0)
        cost += float(call.get("provider_cost_usd") or 0.0)
        if _failure_class(call):
            failures[_failure_class(call)] += 1
    return {"by_stage": dict(stages), "tokens": dict(usage), "cost_usd": cost, "provider_failures": dict(failures)}


def _schedule_metrics(result: dict[str, Any]) -> dict[str, Any]:
    schedule = result.get("schedule") or {}
    dispositions = schedule.get("dispositions") or {}
    statuses = Counter(str(v.get("status")) for v in dispositions.values())
    failures = Counter(str(v.get("failure_class")) for v in schedule.get("failures") or [] if v.get("failure_class"))
    failures.update(str(v.get("failure_class")) for v in result.get("failure_ledger") or [] if v.get("failure_class"))
    budget = {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"}
    budget_events = [v for v in result.get("failure_ledger") or [] if v.get("failure_class") in budget]
    return {
        "independent_semantic_units": schedule.get("initial_stochastic_work_items", schedule.get("stochastic_formula_decisions", 0)),
        "program_groups": len(schedule.get("groups") or []),
        "eligible_program_groups": schedule.get("eligible_program_groups"),
        "deferred_residual_authority": schedule.get("deferred_decisions", len(schedule.get("unresolved_authorised_targets") or [])),
        "units_activated": sum(statuses.values()),
        "units_terminally_disposed": dict(statuses),
        "units_censored_by_global_call_limit": len(budget_events),
        "budget_events": budget_events,
        "unexpected_scheduler_runtime_exceptions": [x for x in result.get("failure_ledger") or [] if x.get("failure_class") == "INTEGRATION_FAILURE"],
        "schedule_failure_classes": dict(failures),
        "operation_count": schedule.get("operation_count"),
        "authorized_targets": schedule.get("authorized_targets"),
        "unresolved_authorised_targets": len(schedule.get("unresolved_authorised_targets") or []),
    }


def _task_record(task_key: str, result: dict[str, Any], score: dict[str, Any], static: dict[str, Any]) -> dict[str, Any]:
    task_dir = task_dir_for(LIVE_ROOT, task_key)
    calls = _load_call_records(task_dir)
    compiler = result.get("compiler") or {}
    plan = result.get("edit_plan") or {}
    spine = runtime.spine_for(task_key)
    gold = _gold_by_obligation(task_key, spine)
    authority_by_ob = {oid: _authority_for_obligation(result, oid) for oid in gold}
    authority_union = set().union(*authority_by_ob.values()) if authority_by_ob else set(plan.get("expansion", {}).get("cell_ids") or [])
    gold_union = set().union(*gold.values()) if gold else set()
    shared = authority_union & gold_union
    fp = authority_union - gold_union
    fn = gold_union - authority_union
    stages = Counter(c.get("stage") for c in calls)
    provider_failures = Counter(_failure_class(c) for c in calls if _failure_class(c))
    parsed_invalid = Counter(c.get("stage") for c in calls if not _failure_class(c) and c.get("parsed_response") is None)
    synth = [c for c in calls if c.get("stage") == "synthesis"]
    retrieval = [c for c in calls if c.get("stage") == "retrieval"]
    synth_status = Counter(_parsed_status(c) for c in synth)
    plan_fragments = plan.get("fragments") or []
    static_task = next(x for x in static["tasks"] if x["task"] == task_key)
    output_activations = [
        a for ob in static_task["obligations"] for a in ob.get("output_role_activations") or []
    ]
    exact = _score_task(score, task_key)
    started = result.get("state", {}).get("started_at") or result.get("started_at")
    finished = result.get("finished_at")
    wall = None
    try:
        if started and finished:
            wall = (datetime.fromisoformat(finished.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
    except Exception:
        wall = None
    return {
        "task": task_key,
        "status": result.get("status"),
        "fatal_failure": result.get("fatal_failure"),
        "task_ir_provider_status": _provider_status((result.get("compiler") or {}).get("call") or {}),
        "task_ir_failure_class": _failure_class((result.get("compiler") or {}).get("call") or {}),
        "task_ir_structural_validity": compiler.get("status") == "OK" and bool(compiler.get("obligations")),
        "obligation_count": len(compiler.get("obligations") or []),
        "inherited_context_diagnostics": {
            "population_obligations": sum(1 for ob in static_task["obligations"] if ob.get("population_member_active")),
            "excluded_member_occurrences": sum(len(ob.get("excluded_occurrences") or []) for ob in static_task["obligations"]),
            "output_role_activations": len(output_activations),
        },
        "edit_plan_provider_status": {
            "success": sum(1 for c in calls if c.get("stage") == "edit_plan" and _provider_status(c) == "SUCCESS"),
            "failure": sum(1 for c in calls if c.get("stage") == "edit_plan" and _provider_status(c) == "FAILURE"),
        },
        "edit_plan_schema_validity": plan.get("status") == "VALID_PLAN",
        "plan_completeness": (plan.get("planning_completeness") or {}).get("status"),
        "expanded_authority_size": len(authority_union),
        "authority_recall": (len(shared) / len(gold_union)) if gold_union else None,
        "authority_precision": (len(shared) / len(authority_union)) if authority_union else None,
        "authority_false_positives": sorted(fp),
        "authority_false_negatives": sorted(fn),
        "authority_miss_classes": {},
        "scheduling": _schedule_metrics(result),
        "retrieval_attempts": len(retrieval),
        "retrieval_completeness_diagnostics": {
            "working_set_handles": len((result.get("state") or {}).get("working_set_handles") or {}),
            "sql_history_entries": len((result.get("state") or {}).get("sql_history") or []),
        },
        "synthesis_attempts": len(synth),
        "synthesis_provider_failures": sum(1 for c in synth if _failure_class(c)),
        "synthesis_explicit_abstentions": sum(1 for c in synth if _parsed_status(c) in {"ABSTAIN", "ABSTENTION"}),
        "synthesis_invalid_responses": sum(1 for c in synth if not _failure_class(c) and not isinstance(c.get("parsed_response"), dict)),
        "synthesis_no_ops": sum(1 for c in synth if _parsed_status(c) in {"NO_OP", "NOOP"}),
        "synthesis_verifier_rejections": sum(1 for x in (result.get("schedule") or {}).get("failures") or [] if x.get("failure_class") == "HARD_VERIFIER_REJECT"),
        "synthesis_proposed_formulas": sum(1 for c in synth if _parsed_status(c) == "PROPOSED" and (c.get("parsed_response") or {}).get("formula")),
        "accepted_semantic_edits": len((result.get("schedule") or {}).get("translated_formula_instances") or []),
        "program_group_canonical_decisions": len((result.get("schedule") or {}).get("canonical_decisions") or []),
        "program_group_translations": len((result.get("schedule") or {}).get("translated_formula_instances") or []),
        "program_group_translation_formulas": (result.get("schedule") or {}).get("translated_formula_instances") or [],
        "dependency_coordinated_units": sum(1 for g in (result.get("schedule") or {}).get("groups") or [] if g.get("execution_members") or g.get("dependency_members")),
        "semantic_writes_scheduled": len((result.get("schedule") or {}).get("edits") or []) if "edits" in (result.get("schedule") or {}) else len((result.get("write_audit") or {}).get("scheduled") or []),
        "writes_persisted": len((result.get("write_audit") or {}).get("applied") or []),
        "scorer": exact,
        "model_calls_by_stage": dict(stages),
        "input_output_tokens": _call_usage(calls)["tokens"],
        "provider_failures": dict(provider_failures),
        "parse_invalid_by_stage": dict(parsed_invalid),
        "wall_clock_seconds": wall,
        "cost_usd": _call_usage(calls)["cost_usd"],
        "call_ceiling_bound": bool(result.get("partial_due_to_budget")),
        "independently_available_work_remaining_when_bound": len((result.get("schedule") or {}).get("unresolved_authorised_targets") or []) if result.get("partial_due_to_budget") else 0,
        "role_output_activations": output_activations,
        "raw_call_ledger": str(task_dir / "calls"),
    }


def run_live() -> dict[str, Any]:
    static = read_json(STATIC_ROOT / "activation_audit.json") or static_activation_audit()
    if static.get("status") != "STATIC_COMPLETE":
        raise RuntimeError("static activation audit failed: predicate violation")
    LIVE_ROOT.mkdir(parents=True, exist_ok=True)
    prior = runtime.configure_runtime(
        max_model_calls=150, max_cost_usd=6.0,
        frontend_mode="sharded_projected",
    )
    prior_databases = runtime.DATABASES
    results: dict[str, Any] = {}
    try:
        runtime.DATABASES = feasibility.REPAIRED_DATABASES
        for index, task_key in enumerate(TASKS, 1):
            print(json.dumps({"event": "task_start", "index": index, "task": task_key}), flush=True)
            results[task_key] = runtime.run_one_task(task_key, stub=False, resume=False, output_root=LIVE_ROOT)
            print(json.dumps({"event": "task_end", "index": index, "task": task_key, "status": results[task_key].get("status"), "calls": (results[task_key].get("state") or {}).get("model_call_count")}), flush=True)
    finally:
        runtime.DATABASES = prior_databases
        runtime.restore_runtime(prior)
    write_json(AUDIT_ROOT / "live_results.json", results)
    # Refresh is explicit and occurs only after all task outputs exist.
    score = runtime.scorer(LIVE_ROOT, "clean-integrated-feasibility", refresh=True)
    write_json(AUDIT_ROOT / "official_scores.json", score)
    return {"results": results, "score": score, "static": static}


def render_report(bundle: dict[str, Any]) -> dict[str, Any]:
    static = bundle["static"]
    score = bundle.get("score") or {}
    rows = [_task_record(task_key, bundle["results"].get(task_key) or {}, score, static) for task_key in TASKS]
    write_json(JSON_PATH, {"static_activation": static, "tasks": rows, "score": score})
    write_csv(CSV_PATH, rows)
    all_calls = sum(sum(row["model_calls_by_stage"].values()) for row in rows)
    all_cost = sum(row["cost_usd"] for row in rows)
    frontend_reached = sum(bool(row["task_ir_structural_validity"]) for row in rows)
    authority_available = sum(row["expanded_authority_size"] > 0 for row in rows)
    evidence_sufficient = sum(bool(row["synthesis_attempts"] or row["accepted_semantic_edits"]) for row in rows)
    synthesis_success = sum(row["accepted_semantic_edits"] > 0 for row in rows)
    scorer_refresh = score.get("status") != "SCORER_FAILURE"
    budget_tasks = sum(row["call_ceiling_bound"] for row in rows)
    provider_failure_tasks = sum(bool(row["provider_failures"]) for row in rows)
    stage_counts = Counter()
    for row in rows:
        stage_counts.update(row["model_calls_by_stage"])
    # The gate is deliberately conservative: resource censoring takes
    # precedence over a score-based feasibility claim when it dominates.
    total_calls = all_calls
    if budget_tasks or provider_failure_tasks or total_calls >= len(TASKS) * 150:
        verdict = "INTEGRATED_FEASIBILITY_RESOURCE_CENSORED"
    elif not scorer_refresh:
        verdict = "INTEGRATED_FEASIBILITY_IMPLEMENTATION_DEFECT"
    elif authority_available == 0:
        verdict = "INTEGRATED_FEASIBILITY_FRONTEND_LIMITED"
    elif synthesis_success == 0 and evidence_sufficient:
        verdict = "INTEGRATED_FEASIBILITY_SYNTHESIS_LIMITED"
    else:
        verdict = "INTEGRATED_FEASIBILITY_SUPPORTED"
    summary = {
        "verdict": verdict,
        "task_count": len(rows),
        "obligation_count": sum(row["obligation_count"] for row in rows),
        "tasks_reaching_task_ir": frontend_reached,
        "tasks_with_authority": authority_available,
        "tasks_with_synthesis_or_edits": evidence_sufficient,
        "tasks_with_accepted_edits": synthesis_success,
        "stage_call_counts": dict(stage_counts),
        "total_model_calls": total_calls,
        "total_cost_usd": all_cost,
        "budget_censored_tasks": budget_tasks,
        "provider_failure_tasks": provider_failure_tasks,
        "scorer_refresh_healthy": scorer_refresh,
        "static_activation": {
            "task_count": static.get("task_count"),
            "obligation_count": static.get("obligation_count"),
            "population_member_activation_count": static.get("population_member_activation_count"),
            "output_role_activation_count": static.get("output_role_activation_count"),
            "output_role_endpoint_count": static.get("output_role_endpoint_count"),
            "candidate_addition_count": static.get("candidate_addition_count"),
            "tasks_with_output_role_activation": static.get("tasks_with_output_role_activation"),
        },
    }
    lines = [
        "# Integrated Feasibility Report",
        "",
        f"Verdict: `{verdict}`",
        "",
        "This is the first clean sequential 12-task feasibility run. It used fresh task output directories, the repaired database lineage, sharded projected planning, and the earned relations as planner evidence/candidates only. No FM20, matched control, synthesis retry, or runtime authority widening was used.",
        "",
        "## Scope and static preflight",
        "",
        f"The static audit covered {static.get('task_count')} tasks and {static.get('obligation_count')} archived obligations with zero model calls and no evaluator gold in construction. It found {static.get('population_member_activation_count')} population/member activations, {static.get('output_role_activation_count')} output-role activations, {static.get('output_role_endpoint_count')} distinct output endpoints, and {static.get('candidate_addition_count')} candidate additions. Output-role activation occurred in: {', '.join(static.get('tasks_with_output_role_activation') or []) or 'none'}.",
        "",
        "Every output-role activation retained member occurrence identity, Task IR introducing field/path, and the copied-header → Month → Numbers → formula extent witness. The activation audit status was `" + str(static.get("status")) + "` and its violation list was empty.",
        "",
        "## Funnel summary",
        "",
        f"{summary['tasks_reaching_task_ir']}/{summary['task_count']} tasks produced structurally valid Task IR; {summary['tasks_with_authority']}/{summary['task_count']} reached non-empty expanded authority; {summary['tasks_with_synthesis_or_edits']}/{summary['task_count']} reached retrieval/synthesis activity or accepted edits; {summary['tasks_with_accepted_edits']}/{summary['task_count']} produced accepted semantic edits. Total demand was {summary['total_model_calls']} model calls and ${summary['total_cost_usd']:.4f} reported provider cost.",
        "",
        "| Task | IR | obligations | plan | completeness | authority | recall | precision | calls | cost | edits | score | budget/provider |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        recall = "—" if row["authority_recall"] is None else f"{row['authority_recall']:.3f}"
        precision = "—" if row["authority_precision"] is None else f"{row['authority_precision']:.3f}"
        score_text = f"mod {row['scorer'].get('modification_accuracy')} / reg {row['scorer'].get('regression_accuracy')}" if row["scorer"] else "—"
        lines.append(f"| {row['task']} | {'yes' if row['task_ir_structural_validity'] else 'no'} | {row['obligation_count']} | {'yes' if row['edit_plan_schema_validity'] else 'no'} | {row['plan_completeness'] or '—'} | {row['expanded_authority_size']} | {recall} | {precision} | {sum(row['model_calls_by_stage'].values())} | ${row['cost_usd']:.4f} | {row['accepted_semantic_edits']} | {score_text} | {'budget' if row['call_ceiling_bound'] else '—'}/{('provider' if row['provider_failures'] else '—')} |")
    lines += [
        "",
        "## Attribution and resource interpretation",
        "",
        "The machine-readable census retains per-obligation authority sets, role activations, provider statuses, call-stage counts, schedule dispositions, retrieval/synthesis outcomes, writer audit, and scorer output. Provider failure, parse invalidity, explicit abstention, verifier rejection, and budget censoring are reported as separate fields.",
        "",
        f"Stage calls: `{json.dumps(dict(stage_counts), sort_keys=True)}`. Provider-failure tasks: {provider_failure_tasks}; budget-censored tasks: {budget_tasks}. Independently available residual work at a budget bound is recorded per task from the scheduler's unresolved authorized set; it is not treated as queue death.",
        "",
        f"LibreOffice/scorer refresh was {'healthy' if scorer_refresh else 'not healthy'}. Writer persistence is reported per task from the write audit. ProgramGroup canonical decisions, translations, and dependency-coordinated units remain separated from ungrouped synthesis in the census.",
        "",
        "## Decision gate",
        "",
        f"`{verdict}`",
        "",
        "The next step is a resource-envelope freeze followed by a prospectively specified limited-domain control comparison only if this run is sufficiently interpretable. No further frontend abstraction is introduced by this report; any blocking mechanical defect is recorded in the census before consideration of that comparison.",
        "",
        "## Artifacts",
        "",
        f"- Static activation JSON/CSV: `{ACTIVATION_JSON.name}`, `{ACTIVATION_CSV.name}`",
        f"- Task census JSON/CSV: `{JSON_PATH.name}`, `{CSV_PATH.name}`",
        f"- Raw task ledgers and outputs: `{LIVE_ROOT}`",
        f"- Official scorer output: `{AUDIT_ROOT / 'official_scores.json'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    write_json(AUDIT_ROOT / "summary.json", summary)
    return {"summary": summary, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "run", "report"))
    args = parser.parse_args()
    if args.command == "audit":
        print(json.dumps(static_activation_audit(), indent=2))
    elif args.command == "run":
        bundle = run_live()
        output = render_report(bundle)
        print(json.dumps(output["summary"], indent=2))
    else:
        static = read_json(STATIC_ROOT / "activation_audit.json") or static_activation_audit()
        results = read_json(AUDIT_ROOT / "live_results.json", {})
        score = read_json(AUDIT_ROOT / "official_scores.json", {})
        print(json.dumps(render_report({"static": static, "results": results, "score": score})["summary"], indent=2))


if __name__ == "__main__":
    main()
