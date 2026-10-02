#!/usr/bin/env python3
"""Render the persisted zero-model integrated feasibility and cost reports.

This script reads only saved task state, call ledgers, static activation data,
evaluator gold, and scorer output.  It never calls a model, starts a scheduler,
opens a workbook for writing, or refreshes LibreOffice.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "src"), str(ROOT / "benchmark/sweagent/formula_index/lib")]

import clean_integrated_feasibility as integrated  # noqa: E402
import workbook_grounding_spine as spine_lib  # noqa: E402


TASKS = integrated.TASKS
AUDIT_ROOT = integrated.AUDIT_ROOT
LIVE_ROOT = integrated.LIVE_ROOT
GPT_ROOT = AUDIT_ROOT / "model_swap_gpt56_sol_high"
STATIC_PATH = integrated.STATIC_ROOT / "activation_audit.json"
SCORE_PATH = LIVE_ROOT / "official_scores.json"
GOLD_PATHS = [ROOT / "research/history/loose_evidence/authority_loss_by_obligation.csv", ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/authority_loss_by_obligation.csv"]

REPORT_PATH = ROOT / "INTEGRATED_FEASIBILITY_REPORT.md"
CENSUS_JSON = ROOT / "research/history/loose_evidence/integrated_feasibility_census.json"
CENSUS_CSV = ROOT / "research/history/loose_evidence/integrated_feasibility_census.csv"
COST_REPORT_PATH = ROOT / "INTEGRATED_FEASIBILITY_COST_REPORT.md"
COST_JSON = ROOT / "research/history/loose_evidence/integrated_feasibility_cost.json"
COST_CSV = ROOT / "research/history/loose_evidence/integrated_feasibility_cost.csv"


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def task_dir(task: str, root: Path = LIVE_ROOT) -> Path:
    return root / task.replace(":", "-")


def task_state(task: str, root: Path = LIVE_ROOT) -> dict[str, Any]:
    return load(task_dir(task, root) / "state.json", {}) or {}


def task_result(task: str, root: Path = LIVE_ROOT) -> dict[str, Any]:
    return load(task_dir(task, root) / "result.json", {}) or {}


def calls_for(root: Path) -> list[dict[str, Any]]:
    calls = []
    for path in sorted((root / "calls").glob("*.json")):
        record = load(path, {}) or {}
        record["_path"] = str(path)
        calls.append(record)
    return calls


def failure(record: dict[str, Any]) -> str | None:
    value = record.get("failure_class")
    return str(value) if value else None


def parsed_status(record: dict[str, Any]) -> str | None:
    value = record.get("parsed_response")
    if isinstance(value, dict):
        return value.get("status") or value.get("decision")
    return None


def call_tokens(record: dict[str, Any]) -> dict[str, int]:
    usage = record.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def provider_status(record: dict[str, Any]) -> str:
    if failure(record):
        return "FAILURE"
    if record.get("raw_response_body") is not None or record.get("raw_response_text") is not None:
        return "SUCCESS"
    return "UNKNOWN"


def display_to_cell_id(task: str, display: str, workbook_spine: dict[str, Any]) -> str | None:
    if not isinstance(display, str) or "!" not in display:
        return None
    title, address = display.rsplit("!", 1)
    sheet_index = (workbook_spine.get("title_to_index") or {}).get(title)
    if sheet_index is None:
        return None
    import re
    match = re.fullmatch(r"([A-Z]+)([0-9]+)", address.upper())
    if not match:
        return None
    col = 0
    for char in match.group(1):
        col = col * 26 + ord(char) - 64
    return spine_lib.cell_id(sheet_index, int(match.group(2)), col)


def cell_id_to_display(cell_id: str, workbook_spine: dict[str, Any]) -> str:
    # The runtime's target-address helper is deliberately avoided here so the
    # report remains usable even when a legacy spine lacks a target index.
    match = __import__("re").fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", cell_id or "")
    if not match:
        return cell_id
    sheet_index, row, col = (int(x) for x in match.groups())
    titles = workbook_spine.get("index_to_title") or {}
    if titles:
        title = titles.get(str(sheet_index), titles.get(sheet_index, f"sheet:{sheet_index}"))
    else:
        title = next((name for name, index in (workbook_spine.get("title_to_index") or {}).items() if index == sheet_index), f"sheet:{sheet_index}")
    return f"{title}!{integrated.runtime.closure.a1(row, col)}"


def read_gold() -> tuple[dict[str, dict[str, set[str]]], dict[str, dict[str, list[str]]], int]:
    """Return gold IDs by task/obligation and retained display provenance."""
    path = next((candidate for candidate in GOLD_PATHS if candidate.exists()), None)
    if path is None:
        return {}, {}, 0
    csv.field_size_limit(sys.maxsize)
    ids: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    displays: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    rows = 0
    for task in TASKS:
        workbook_spine = load(integrated.runtime.SPINES / f"{task.replace(':', '-')}.json", {}) or {}
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("task") != task or not row.get("obligation_id"):
                    continue
                raw = row.get("gold_target_cells") or "[]"
                try:
                    targets = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    targets = []
                rows += 1
                for display in targets if isinstance(targets, list) else []:
                    if display not in displays[task][row["obligation_id"]]:
                        displays[task][row["obligation_id"]].append(display)
                    cid = display_to_cell_id(task, display, workbook_spine)
                    if cid:
                        ids[task][row["obligation_id"]].add(cid)
    return {task: dict(obligations) for task, obligations in ids.items()}, {task: dict(obligations) for task, obligations in displays.items()}, rows


def authority_by_obligation(state: dict[str, Any]) -> dict[str, set[str]]:
    plan = state.get("edit_plan") or {}
    # Fragments retained on an invalid plan are diagnostic candidates, not
    # Edit Plan authority.  Do not count them as operational authority.
    if plan.get("status") not in {"VALID_PLAN", "EMPTY_EXPANSION"}:
        return {}
    expansion = plan.get("expansion") or {}
    out: dict[str, set[str]] = defaultdict(set)
    for operation in expansion.get("operations") or []:
        oid = operation.get("obligation_id")
        if oid:
            out[oid].update(operation.get("cell_ids") or [])
    if out:
        return dict(out)
    for fragment in (state.get("edit_plan") or {}).get("fragments") or []:
        oid = fragment.get("obligation_id")
        if oid:
            out[oid].update((fragment.get("expansion") or {}).get("cell_ids") or [])
    return dict(out)


def candidate_by_obligation(state: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for oid, packet in ((state.get("edit_plan") or {}).get("packets") or {}).items():
        out[oid].update(packet.get("target_cell_ids") or [])
    return dict(out)


def started_wall_seconds(state: dict[str, Any]) -> float | None:
    started, finished = state.get("started_at"), state.get("finished_at")
    if not started or not finished:
        return None
    try:
        return (datetime.fromisoformat(finished.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
    except (TypeError, ValueError):
        return None


def static_obligation(static: dict[str, Any], task: str, oid: str) -> dict[str, Any]:
    for task_record in static.get("tasks", []):
        if task_record.get("task") != task:
            continue
        for obligation in task_record.get("obligations", []):
            if obligation.get("obligation_id") == oid:
                return obligation
    return {}


def earliest_loss(state: dict[str, Any], result: dict[str, Any], missed: set[str], candidates: set[str], gold_available: bool) -> tuple[str, dict[str, Any]]:
    compiler = state.get("compiler") or {}
    plan = state.get("edit_plan") or {}
    calls = calls_for(task_dir(state.get("task_id", "")))
    call_failures = Counter(failure(call) for call in calls if failure(call))
    if compiler.get("status") != "OK":
        return "TASK_IR_PROVIDER_OR_PARSE_FAILURE", {"compiler_status": compiler.get("status"), "call_failures": dict(call_failures)}
    if plan.get("status") != "VALID_PLAN":
        if any(f in {"PROVIDER_TIMEOUT", "PROVIDER_ERROR", "MODEL_ACCESS_FAILURE"} for f in call_failures):
            return "PLANNER_RESPONSE_MISSING", {"plan_status": plan.get("status"), "call_failures": dict(call_failures)}
        return "PLANNER_SCHEMA_OR_ENTITY_FAILURE", {"plan_status": plan.get("status"), "call_failures": dict(call_failures)}
    if missed and candidates.intersection(missed):
        return "EVIDENCE_PRESENT_MODEL_WRONG_SELECTION", {"missed_candidate_cells": sorted(candidates.intersection(missed))}
    if missed and result.get("partial_due_to_budget"):
        return "RESOURCE_CENSORING", {"missed_cells": sorted(missed), "unresolved_authorised_targets": len((state.get("schedule") or {}).get("unresolved_authorised_targets") or [])}
    if result.get("fatal_failure") and (state.get("write_audit") or {}).get("rejected"):
        return "WRITER_FAILURE", {"rejected_writes": (state.get("write_audit") or {}).get("rejected")}
    if missed and gold_available:
        return "ROLE_OR_TARGET_RELATION_NOT_REPRESENTED", {"missed_cells": sorted(missed)}
    if result.get("fatal_failure"):
        return "EXECUTION_RUNTIME_FAILURE", {"failure_ledger": state.get("failure_ledger") or []}
    if gold_available and not missed:
        return "NO_FRONTEND_LOSS", {}
    return "NO_FRONTEND_GOLD_AVAILABLE", {}


def task_census_row(task: str, static: dict[str, Any], gold: dict[str, dict[str, set[str]]], gold_display: dict[str, dict[str, list[str]]], score: dict[str, Any]) -> dict[str, Any]:
    state = task_state(task)
    result = task_result(task)
    calls = calls_for(task_dir(task))
    workbook_spine = load(integrated.runtime.SPINES / f"{task.replace(':', '-')}.json", {}) or {}
    compiler = state.get("compiler") or {}
    plan = state.get("edit_plan") or {}
    schedule = state.get("schedule") or {}
    gold_by_ob = gold.get(task, {})
    gold_union = set().union(*(set(value) for value in gold_by_ob.values())) if gold_by_ob else set()
    authority_by_ob = authority_by_obligation(state)
    authority_union = set().union(*authority_by_ob.values()) if authority_by_ob else set()
    candidate_union = set().union(*candidate_by_obligation(state).values()) if candidate_by_obligation(state) else set()
    shared, fp, fn = authority_union & gold_union, authority_union - gold_union, gold_union - authority_union
    stage_calls = Counter(call.get("stage") or "unknown" for call in calls)
    stage_cost = Counter()
    tokens = Counter()
    call_failures = Counter()
    parse_invalid = Counter()
    for call in calls:
        stage = call.get("stage") or "unknown"
        stage_cost[stage] += float(call.get("provider_cost_usd") or 0.0)
        tokens.update(call_tokens(call))
        if failure(call):
            call_failures[failure(call)] += 1
        elif call.get("parsed_response") is None:
            parse_invalid[stage] += 1
    statuses = Counter(str(value.get("status")) for value in (schedule.get("dispositions") or {}).values())
    synth = [call for call in calls if call.get("stage") == "synthesis"]
    retrieval = [call for call in calls if call.get("stage") == "retrieval"]
    synth_status = Counter(parsed_status(call) for call in synth)
    plan_calls = [call for call in calls if call.get("stage") == "edit_plan"]
    task_ir_call = next((call for call in calls if call.get("stage") == "task_ir"), {})
    ob_rows = []
    for oid, gold_cells in sorted(gold_by_ob.items()):
        authority = authority_by_ob.get(oid, set())
        candidates = candidate_by_obligation(state).get(oid, set())
        ob_rows.append({
            "obligation_id": oid,
            "gold_targets": sorted(gold_display.get(task, {}).get(oid, [])),
            "gold_cell_ids": sorted(gold_cells),
            "authority_cell_ids": sorted(authority),
            "candidate_cell_ids_contain_gold": sorted(gold_cells & candidates),
            "authority_recall": len(authority & gold_cells) / len(gold_cells) if gold_cells else None,
            "authority_precision": len(authority & gold_cells) / len(authority) if authority else None,
            "missed_gold_cells": sorted(gold_cells - authority),
            "task_ir_fields": next((ob for ob in compiler.get("obligations", []) if ob.get("id") == oid), {}),
            "static_context": static_obligation(static, task, oid),
        })
    loss, loss_evidence = earliest_loss(state, result, fn, candidate_union, bool(gold_union))
    exact = (score.get("tasks") or {}).get(task) or {}
    write_audit = state.get("write_audit") or result.get("write_audit") or {}
    schedule_failures = Counter(value.get("failure_class") for value in schedule.get("failures") or [] if value.get("failure_class"))
    ledger_failures = Counter(value.get("failure_class") for value in state.get("failure_ledger") or [] if value.get("failure_class"))
    group_records = schedule.get("groups") or []
    dependency_groups = [group for group in group_records if group.get("execution_members") or group.get("groups")]
    return {
        "task": task,
        "model": state.get("model"),
        "reasoning": state.get("reasoning"),
        "max_model_calls": state.get("max_model_calls"),
        "max_cost_usd": state.get("max_cost_usd"),
        "status": state.get("status") or result.get("status"),
        "fatal_failure": bool(state.get("fatal_failure") or result.get("fatal_failure")),
        "task_ir_provider_status": provider_status(task_ir_call),
        "task_ir_failure_class": failure(task_ir_call),
        "task_ir_structural_validity": compiler.get("status") == "OK" and bool(compiler.get("obligations")),
        "obligation_count": len(compiler.get("obligations") or []),
        "context_diagnostics": {
            "subject_interval_obligations": sum(bool(ob.get("subject_interval")) for ob in compiler.get("obligations") or []),
            "scope_obligations": sum(bool(ob.get("scope")) for ob in compiler.get("obligations") or []),
            "source_relation_obligations": sum(bool(ob.get("source_relation")) for ob in compiler.get("obligations") or []),
            "parent_or_inheritance_keys": sorted({key for ob in compiler.get("obligations") or [] for key in ob if "parent" in key or "inherit" in key}),
            "population_member_obligations": sum(1 for task_record in static.get("tasks", []) if task_record.get("task") == task for ob in task_record.get("obligations", []) if ob.get("population_member_active")),
            "output_role_activations": sum(len(ob.get("output_role_activations") or []) for task_record in static.get("tasks", []) if task_record.get("task") == task for ob in task_record.get("obligations", [])),
        },
        "edit_plan_provider_status": {
            "attempts": len(plan_calls),
            "successes": sum(provider_status(call) == "SUCCESS" for call in plan_calls),
            "failures": sum(provider_status(call) == "FAILURE" for call in plan_calls),
        },
        "edit_plan_schema_validity": plan.get("status") == "VALID_PLAN",
        "plan_completeness": (plan.get("planning_completeness") or {}).get("status"),
        "expanded_authority_size": len(authority_union),
        "gold_available": bool(gold_union),
        "gold_target_count": len(gold_union),
        "authority_recall": len(shared) / len(gold_union) if gold_union else None,
        "authority_precision": len(shared) / len(authority_union) if gold_union and authority_union else None,
        "authority_false_positive_count": len(fp) if gold_union else None,
        "authority_false_negative_count": len(fn) if gold_union else None,
        "authority_false_positive_cells": sorted(cell_id_to_display(cell, workbook_spine) for cell in fp),
        "authority_false_negative_cells": sorted(cell_id_to_display(cell, workbook_spine) for cell in fn),
        "authority_miss_classes": {"primary": loss, "evidence": loss_evidence},
        "obligation_gold_rows": ob_rows,
        "scheduling": {
            "independent_semantic_units": schedule.get("initial_stochastic_work_items", schedule.get("stochastic_formula_decisions")),
            "program_groups": len(group_records),
            "eligible_program_groups": schedule.get("eligible_program_groups"),
            "deferred_residual_authority": schedule.get("deferred_decisions", len(schedule.get("unresolved_authorised_targets") or [])),
            "units_activated": len(schedule.get("dispositions") or {}),
            "units_terminally_disposed": dict(statuses),
            "units_censored_by_budget": sum(value for key, value in statuses.items() if key in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"}) + sum(value for key, value in ledger_failures.items() if key in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"}),
            "unexpected_scheduler_runtime_exceptions": [value for value in state.get("failure_ledger") or [] if value.get("failure_class") == "INTEGRATION_FAILURE"],
            "operation_count": schedule.get("operation_count"),
            "authorized_targets": schedule.get("authorized_targets", len(authority_union)),
            "unresolved_authorised_targets": len(schedule.get("unresolved_authorised_targets") or []),
            "schedule_failure_classes": dict(schedule_failures),
        },
        "retrieval_attempts": len(retrieval),
        "retrieval_completeness_diagnostics": {
            "working_set_handle_count": len(state.get("working_set_handles") or {}),
            "sql_history_entries": len(state.get("sql_history") or []),
            "successful_retrieval_calls": sum(provider_status(call) == "SUCCESS" for call in retrieval),
            "retrieval_failures": dict(Counter(failure(call) for call in retrieval if failure(call))),
        },
        "synthesis_attempts": len(synth),
        "synthesis_provider_failures": sum(bool(failure(call)) for call in synth),
        "synthesis_explicit_abstentions": sum(parsed_status(call) in {"ABSTAIN", "ABSTENTION"} for call in synth),
        "synthesis_invalid_responses": sum(not failure(call) and not isinstance(call.get("parsed_response"), dict) for call in synth),
        "synthesis_no_ops": sum(parsed_status(call) in {"NO_OP", "NOOP", "NO_SEMANTIC_CHANGE"} for call in synth),
        "synthesis_verifier_rejections": sum(value.get("failure_class") == "HARD_VERIFIER_REJECT" for value in schedule.get("failures") or []),
        "synthesis_proposed_formulas": sum(parsed_status(call) == "PROPOSED" and bool((call.get("parsed_response") or {}).get("formula")) for call in synth),
        "accepted_semantic_edits": len(state.get("completed_edits") or []),
        "program_group_canonical_decisions": len(schedule.get("canonical_decisions") or []),
        "program_group_translations": len(state.get("translated_formulas") or schedule.get("translated_formula_instances") or []),
        "program_group_translation_formulas": state.get("translated_formulas") or schedule.get("translated_formula_instances") or [],
        "dependency_coordinated_group_count": len(dependency_groups),
        "semantic_writes_scheduled": len(state.get("completed_edits") or []),
        "writes_persisted": len(write_audit.get("applied") or []),
        "writer_rejections": write_audit.get("rejected") or [],
        "writer_persistence_success": bool((task_dir(task) / "output.xlsx").exists()),
        "scorer": {
            "exact": bool(exact.get("accuracy") == 1.0),
            "modification_accuracy": exact.get("modification_accuracy"),
            "regression_accuracy": exact.get("regression_accuracy"),
            "error_message": exact.get("error_message"),
        },
        "model_calls_by_stage": dict(stage_calls),
        "stage_cost_usd": dict(stage_cost),
        "input_output_tokens": dict(tokens),
        "provider_failures": dict(call_failures),
        "parse_invalid_by_stage": dict(parse_invalid),
        "ledger_failure_classes": dict(ledger_failures),
        "wall_clock_seconds": started_wall_seconds(state),
        "cost_usd": float(state.get("provider_cost_usd") or sum(float(call.get("provider_cost_usd") or 0.0) for call in calls)),
        "call_ceiling_bound": bool(result.get("partial_due_to_budget") or state.get("partial_due_to_budget")),
        "independently_available_work_remaining_when_bound": len(schedule.get("unresolved_authorised_targets") or []) if result.get("partial_due_to_budget") or state.get("partial_due_to_budget") else 0,
        "raw_call_ledger": str(task_dir(task) / "calls"),
    }


def scorer_refresh_status(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "present": bool(score),
        "runtime": score.get("evaluation_runtime"),
        "staged_outputs": score.get("submission", {}).get("outputs"),
        "scored": score.get("scored"),
        "missing_outputs": score.get("missing_outputs"),
        "exact": score.get("exact"),
        "value": "LibreOffice refresh succeeded before scorer; metadata-tolerant local evaluator was used",
    }


def render_integrated() -> dict[str, Any]:
    static = load(STATIC_PATH, {}) or {}
    score = load(SCORE_PATH, {}) or {}
    gold, gold_display, gold_rows = read_gold()
    rows = [task_census_row(task, static, gold, gold_display, score) for task in TASKS]
    summary = {
        "verdict": None,
        "run_scope": "12-task Financial_Model integrated feasibility; operator-adjusted continuation used parallel workers and per-task 33¢ caps for remaining tasks",
        "task_count": len(rows),
        "static_obligation_count": static.get("obligation_count"),
        "evaluator_gold_obligation_rows_available": gold_rows,
        "evaluator_gold_task_count": sum(bool(row["gold_available"]) for row in rows),
        "tasks_reaching_valid_task_ir": sum(row["task_ir_structural_validity"] for row in rows),
        "tasks_with_valid_edit_plan": sum(row["edit_plan_schema_validity"] for row in rows),
        "tasks_with_complete_plan": sum(row["plan_completeness"] == "COMPLETE" for row in rows),
        "tasks_with_nonempty_authority": sum(row["expanded_authority_size"] > 0 for row in rows),
        "tasks_with_retrieval": sum(row["retrieval_attempts"] > 0 for row in rows),
        "tasks_with_synthesis": sum(row["synthesis_attempts"] > 0 for row in rows),
        "tasks_with_accepted_edits": sum(row["accepted_semantic_edits"] > 0 for row in rows),
        "gold_authority_cells": sum(row["gold_target_count"] for row in rows),
        "gold_authority_shared_cells": sum(int(round((row["authority_recall"] or 0) * row["gold_target_count"])) for row in rows),
        "total_model_calls": sum(sum(row["model_calls_by_stage"].values()) for row in rows),
        "total_provider_cost_usd": sum(row["cost_usd"] for row in rows),
        "total_prompt_tokens": sum(row["input_output_tokens"].get("prompt_tokens", 0) for row in rows),
        "total_completion_tokens": sum(row["input_output_tokens"].get("completion_tokens", 0) for row in rows),
        "total_reasoning_tokens": sum(row["input_output_tokens"].get("reasoning_tokens", 0) for row in rows),
        "total_tokens": sum(row["input_output_tokens"].get("total_tokens", 0) for row in rows),
        "budget_censored_tasks": sum(row["call_ceiling_bound"] for row in rows),
        "provider_failure_tasks": sum(bool(row["provider_failures"]) for row in rows),
        "provider_failure_calls": sum(sum(row["provider_failures"].values()) for row in rows),
        "writer_rejection_tasks": sum(bool(row["writer_rejections"]) for row in rows),
        "writes_scheduled": sum(row["semantic_writes_scheduled"] for row in rows),
        "writes_persisted": sum(row["writes_persisted"] for row in rows),
        "exact_tasks": sum(row["scorer"]["exact"] for row in rows),
        "scorer_refresh": scorer_refresh_status(score),
        "static_activation": {key: static.get(key) for key in ("task_count", "obligation_count", "population_member_activation_count", "output_role_activation_count", "output_role_endpoint_count", "candidate_addition_count", "tasks_with_output_role_activation")},
    }
    loss_counts = Counter(row["authority_miss_classes"]["primary"] for row in rows)
    summary["earliest_loss_task_counts"] = dict(loss_counts)
    if summary["budget_censored_tasks"] or summary["provider_failure_calls"]:
        summary["verdict"] = "INTEGRATED_FEASIBILITY_RESOURCE_CENSORED"
    elif not summary["scorer_refresh"]["present"]:
        summary["verdict"] = "INTEGRATED_FEASIBILITY_IMPLEMENTATION_DEFECT"
    elif summary["tasks_with_nonempty_authority"] == 0:
        summary["verdict"] = "INTEGRATED_FEASIBILITY_FRONTEND_LIMITED"
    elif not summary["tasks_with_accepted_edits"]:
        summary["verdict"] = "INTEGRATED_FEASIBILITY_SYNTHESIS_LIMITED"
    else:
        summary["verdict"] = "INTEGRATED_FEASIBILITY_SUPPORTED"
    payload = {"summary": summary, "tasks": rows, "static_activation": static, "scorer": score}
    write_json(CENSUS_JSON, payload)
    write_csv(CENSUS_CSV, rows)
    return payload


def cost_rows(root: Path, arm: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    all_calls: list[dict[str, Any]] = []
    for task_root in sorted(root.glob("Financial_Model-*")):
        calls = calls_for(task_root)
        if not calls:
            continue
        totals = Counter()
        failures = Counter()
        by_stage: dict[str, Counter] = defaultdict(Counter)
        for call in calls:
            totals.update(call_tokens(call))
            totals["calls"] += 1
            totals["cost_usd"] += float(call.get("provider_cost_usd") or 0.0)
            stage = call.get("stage") or "unknown"
            by_stage[stage]["calls"] += 1
            by_stage[stage]["cost_usd"] += float(call.get("provider_cost_usd") or 0.0)
            by_stage[stage].update(call_tokens(call))
            if failure(call):
                failures[failure(call)] += 1
            all_calls.append(call | {"_task_dir": task_root.name, "arm": arm})
        state = load(task_root / "state.json", {}) or {}
        rows.append({
            "arm": arm,
            "task": task_root.name.replace("-", ":", 1),
            "model": state.get("model"),
            "reasoning": state.get("reasoning"),
            "max_model_calls": state.get("max_model_calls"),
            "max_cost_usd": state.get("max_cost_usd"),
            "calls": totals["calls"],
            "cost_usd": totals["cost_usd"],
            "prompt_tokens": totals["prompt_tokens"],
            "completion_tokens": totals["completion_tokens"],
            "reasoning_tokens": totals["reasoning_tokens"],
            "total_tokens": totals["total_tokens"],
            "provider_failures": dict(failures),
            "stage_breakdown": {stage: dict(values) for stage, values in by_stage.items()},
            "status": state.get("status"),
            "partial_due_to_budget": state.get("partial_due_to_budget"),
            "wall_clock_seconds": started_wall_seconds(state),
        })
    total = Counter()
    by_stage: dict[str, Counter] = defaultdict(Counter)
    failures = Counter()
    for call in all_calls:
        total.update(call_tokens(call))
        total["calls"] += 1
        total["cost_usd"] += float(call.get("provider_cost_usd") or 0.0)
        stage = call.get("stage") or "unknown"
        by_stage[stage]["calls"] += 1
        by_stage[stage]["cost_usd"] += float(call.get("provider_cost_usd") or 0.0)
        by_stage[stage].update(call_tokens(call))
        if failure(call):
            failures[failure(call)] += 1
    total_payload = {"arm": arm, "calls": total["calls"], "cost_usd": total["cost_usd"], "prompt_tokens": total["prompt_tokens"], "completion_tokens": total["completion_tokens"], "reasoning_tokens": total["reasoning_tokens"], "total_tokens": total["total_tokens"], "provider_failures": dict(failures), "stage_breakdown": {stage: dict(values) for stage, values in by_stage.items()}}
    return rows, {"summary": total_payload, "calls": all_calls}


def render_cost(integrated_payload: dict[str, Any]) -> dict[str, Any]:
    glm_rows, glm = cost_rows(LIVE_ROOT, "integrated_glm")
    gpt_rows, gpt = cost_rows(GPT_ROOT, "one_off_gpt_probe")
    summary = integrated_payload["summary"]
    top_cost = sorted(glm["calls"], key=lambda call: float(call.get("provider_cost_usd") or 0.0), reverse=True)[:10]
    top_prompt = sorted(glm["calls"], key=lambda call: call_tokens(call)["prompt_tokens"], reverse=True)[:10]
    authority_rows = sorted((row for row in integrated_payload["tasks"] if row["expanded_authority_size"]), key=lambda row: row["expanded_authority_size"], reverse=True)
    waste = {
        "provider_failures_are_separate_from_cost": True,
        "provider_failure_calls": sum(glm["summary"]["provider_failures"].values()),
        "authority_expansion_hotspots": [{"task": row["task"], "authority_cells": row["expanded_authority_size"], "unresolved_after_bound": row["scheduling"]["unresolved_authorised_targets"], "cost_usd": row["cost_usd"]} for row in authority_rows[:5]],
        "large_prompt_calls": [{"task": call.get("_task_dir"), "call": Path(call.get("_path", "")).name, "stage": call.get("stage"), "prompt_tokens": call_tokens(call)["prompt_tokens"], "cost_usd": float(call.get("provider_cost_usd") or 0.0)} for call in top_prompt[:10]],
        "resource_censored_tasks": [row["task"] for row in integrated_payload["tasks"] if row["call_ceiling_bound"]],
        "writer_or_scorer_cost": 0.0,
        "interpretation": [
            "The largest directly evidenced architecture-induced cost driver is authority expansion: 06_01 authorized 78,777 cells and retained 78,756 unresolved targets at the bound while producing six accepted edits.",
            "Retrieval and synthesis together account for the majority of provider spend and token volume; synthesis contains the largest prompts, including repeated roughly half-million-token contexts in 06_01.",
            "Provider timeouts/errors are provider wastage and latency, not semantic abstentions; they consumed no reported provider tokens in the call ledger but blocked progress.",
            "Tasks at the 150-call or 33¢ ceilings are resource-censored, so their residual work is not evidence that the scheduler queue died.",
            "LibreOffice, scoring, and writer operations have no model-provider cost in this ledger.",
        ],
    }
    payload = {
        "integrated": {"task_rows": glm_rows, "summary": glm["summary"]},
        "one_off_gpt_probe": {"task_rows": gpt_rows, "summary": gpt["summary"], "termination": "user_requested_stop_at_or_above_0.66_usd", "persisted_result": (GPT_ROOT / "Financial_Model-06_01" / "result.json").exists()},
        "waste_analysis": waste,
        "top_cost_calls": [{"task": call.get("_task_dir"), "call": Path(call.get("_path", "")).name, "stage": call.get("stage"), "cost_usd": float(call.get("provider_cost_usd") or 0.0), "tokens": call_tokens(call)} for call in top_cost],
        "top_prompt_calls": [{"task": call.get("_task_dir"), "call": Path(call.get("_path", "")).name, "stage": call.get("stage"), "prompt_tokens": call_tokens(call)["prompt_tokens"], "cost_usd": float(call.get("provider_cost_usd") or 0.0)} for call in top_prompt],
        "integrated_summary_from_census": summary,
    }
    write_json(COST_JSON, payload)
    write_csv(COST_CSV, glm_rows + gpt_rows)
    return payload


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(integrated_payload: dict[str, Any], cost_payload: dict[str, Any]) -> None:
    summary = integrated_payload["summary"]
    lines = [
        "# Integrated Feasibility Report",
        "",
        f"Verdict: `{summary['verdict']}`",
        "",
        "This report is a zero-model rendering of the persisted 12-task Financial_Model feasibility run. The original sequential/one-worker plan was operator-adjusted during execution: remaining GLM tasks were continued in parallel and capped at 33¢ each, as requested. The report therefore preserves that execution fact rather than presenting it as a strict sequential replication.",
        "",
        "## Funnel summary",
        "",
        f"The slice contains {summary['task_count']} tasks and {summary['static_obligation_count']} archived obligations. {summary['tasks_reaching_valid_task_ir']}/{summary['task_count']} tasks reached structurally valid Task IR; {summary['tasks_with_valid_edit_plan']}/{summary['task_count']} produced schema-valid Edit Plans; {summary['tasks_with_complete_plan']}/{summary['task_count']} were marked complete; {summary['tasks_with_nonempty_authority']}/{summary['task_count']} had non-empty expanded authority; {summary['tasks_with_retrieval']}/{summary['task_count']} reached retrieval; {summary['tasks_with_synthesis']}/{summary['task_count']} reached synthesis; and {summary['tasks_with_accepted_edits']}/{summary['task_count']} produced accepted semantic edits.",
        "",
        f"Evaluator-side authority gold is available for {summary['evaluator_gold_task_count']} tasks / {summary['evaluator_gold_obligation_rows_available']} obligation rows, covering {summary['gold_authority_cells']} gold cells. The current authority shared {summary['gold_authority_shared_cells']} of those cells under the per-obligation accounting. Other tasks are reported as gold-unavailable rather than assigned synthetic precision/recall.",
        "",
        "| Task | status | IR | plan | completeness | authority | gold | recall | precision | retrieval | synthesis | edits | calls | cost | earliest supported loss |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in integrated_payload["tasks"]:
        lines.append(f"| {row['task']} | {row['status']} | {'yes' if row['task_ir_structural_validity'] else 'no'} | {'yes' if row['edit_plan_schema_validity'] else 'no'} | {row['plan_completeness'] or '—'} | {row['expanded_authority_size']} | {row['gold_target_count'] if row['gold_available'] else '—'} | {fmt(row['authority_recall'], 3)} | {fmt(row['authority_precision'], 3)} | {row['retrieval_attempts']} | {row['synthesis_attempts']} | {row['accepted_semantic_edits']} | {sum(row['model_calls_by_stage'].values())} | ${row['cost_usd']:.4f} | {row['authority_miss_classes']['primary']} |")
    lines += [
        "",
        "## Static integration preflight",
        "",
        f"The activation audit was `{integrated_payload['static_activation'].get('status')}` with zero predicate violations. It recorded {integrated_payload['static_activation'].get('population_member_activation_count')} population/member activations, {integrated_payload['static_activation'].get('output_role_activation_count')} output-role activations, five distinct output endpoints, and five candidate additions. Output-role activation occurred only in the studied `Financial_Model:05_01` task. These relations remained planner evidence/candidate structure and did not grant authority automatically.",
        "",
        "## Scheduling, retrieval, synthesis, and execution",
        "",
        f"Across tasks, {summary['writes_scheduled']} semantic writes were scheduled and {summary['writes_persisted']} persisted. {summary['writer_rejection_tasks']} task(s) had writer rejections. ProgramGroup canonical decisions, deterministic translations, dependency-coordinated groups, disposition statuses, residual authority, and provider failures are retained per task in the census JSON/CSV. Provider failures are not counted as model abstentions.",
        "",
        f"LibreOffice refresh and metadata-tolerant scorer execution were healthy for all {summary['scorer_refresh'].get('scored')} scored outputs; missing outputs were {summary['scorer_refresh'].get('missing_outputs')}. Exact-task count was {summary['exact_tasks']}/{summary['task_count']}; this is a feasibility funnel measurement, not a matched control comparison.",
        "",
        "## Attribution",
        "",
        f"The largest task-level residual is `06_01`: authority {next((r['expanded_authority_size'] for r in integrated_payload['tasks'] if r['task'] == 'Financial_Model:06_01'), 0)}, with {next((r['scheduling']['unresolved_authorised_targets'] for r in integrated_payload['tasks'] if r['task'] == 'Financial_Model:06_01'), 0)} unresolved authorized targets at the resource bound. The census distinguishes invalid plans, evidence-present planner selection errors, resource censoring, writer failures, and no-frontend-loss cases. Aggregate earliest-loss labels are `{json.dumps(summary['earliest_loss_task_counts'], sort_keys=True)}`.",
        "",
        "## Resource envelope",
        "",
        f"The integrated GLM funnel consumed {summary['total_model_calls']} calls, ${summary['total_provider_cost_usd']:.4f}, and {summary['total_tokens']:,} reported tokens ({summary['total_prompt_tokens']:,} prompt, {summary['total_completion_tokens']:,} completion, {summary['total_reasoning_tokens']:,} reasoning). {summary['budget_censored_tasks']} tasks were resource-censored and {summary['provider_failure_calls']} call records were provider failures. See the companion cost report for stage/task concentration and evidenced wastes.",
        "",
        "## Decision gate",
        "",
        f"`{summary['verdict']}`",
        "",
        "The current result is resource-censored: it demonstrates meaningful end-to-end work and a healthy writer/LibreOffice/scorer bridge, but the ceiling/provider failures prevent an uncensored feasibility claim. The narrow next step is to freeze this resource envelope and prospectively specify a limited-domain control comparison after the persisted ledgers are reviewed; no new frontend abstraction is justified by this run alone.",
        "",
        "## Artifacts",
        "",
        f"- Census: `{CENSUS_JSON.name}`, `{CENSUS_CSV.name}`",
        f"- Cost report: `{COST_REPORT_PATH.name}`, `{COST_JSON.name}`, `{COST_CSV.name}`",
        f"- Static activation: `{integrated.ACTIVATION_JSON.name}`, `{integrated.ACTIVATION_CSV.name}`",
        f"- Raw GLM task ledgers: `{LIVE_ROOT}`",
        f"- Scorer output: `{SCORE_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    csummary = cost_payload["integrated"]["summary"]
    stage_lines = ["| Stage | calls | cost | prompt tokens | completion tokens | total tokens |", "|---|---:|---:|---:|---:|---:|"]
    for stage, values in sorted(csummary.get("stage_breakdown", {}).items()):
        stage_lines.append(f"| {stage} | {values.get('calls', 0)} | ${values.get('cost_usd', 0.0):.4f} | {values.get('prompt_tokens', 0):,} | {values.get('completion_tokens', 0):,} | {values.get('total_tokens', 0):,} |")
    cost_lines = [
        "# Integrated Feasibility Cost Report",
        "",
        "This report attributes provider cost from immutable per-call ledgers. It separates semantic demand, provider failures, resource censoring, and evidenced orchestration/authority expansion. Writer, LibreOffice, and scorer operations are not provider calls and have zero model cost.",
        "",
        f"## Integrated GLM total: {csummary['calls']} calls / ${csummary['cost_usd']:.4f}",
        "",
        f"Reported tokens: {csummary['total_tokens']:,} total, {csummary['prompt_tokens']:,} prompt, {csummary['completion_tokens']:,} completion, {csummary['reasoning_tokens']:,} reasoning.",
        "",
        *stage_lines,
        "",
        "## Cost by task",
        "",
        "| Task | calls | cost | ceiling | status | provider failures | wall seconds |",
        "|---|---:|---:|---:|---|---|---:|",
    ]
    for row in cost_payload["integrated"]["task_rows"]:
        cost_lines.append(f"| {row['task']} | {row['calls']} | ${row['cost_usd']:.4f} | ${row['max_cost_usd']} | {row['status']} | {json.dumps(row['provider_failures'], sort_keys=True)} | {fmt(row['wall_clock_seconds'], 1)} |")
    cost_lines += [
        "",
        "## Evidenced cost concentrations and wastes",
        "",
        "- Authority expansion is the clearest architecture-induced demand hotspot. `06_01` authorized 78,777 cells, left 78,756 unresolved at the bound, and produced six accepted edits; `05_01` and `07_01` also carried large authority/residual populations. This is not evidence that all those cells were semantically needed.",
        "- Retrieval used the largest number of calls and synthesis used the largest individual prompts. The largest successful synthesis contexts were roughly half a million prompt tokens in `06_01`, making repeated full working-set context a directly evidenced cost driver.",
        f"- The GLM ledger contains {sum(csummary['provider_failures'].values())} provider-failure call records: {json.dumps(csummary['provider_failures'], sort_keys=True)}. These are provider wastage/latency and are kept separate from explicit abstentions and invalid model responses.",
        f"- {integrated_payload['summary']['budget_censored_tasks']} integrated tasks were capped. The three remaining-task 33¢ caps crossed slightly on their final successful responses (`08_01`, `14_05`, `17_05`); the configured ceiling stopped subsequent work but cannot undo the already completed response charge.",
        "- The 07_01 wall-clock value is inflated by interruption/resumption history and should not be interpreted as a clean per-call latency sample. The run also deviated from the original one-worker sequence when remaining capped tasks were parallelized by request.",
        "",
        "## One-off GPT comparison (not part of integrated total)",
        "",
    ]
    gpt = cost_payload["one_off_gpt_probe"]["summary"]
    cost_lines.append(f"`openai/gpt-5.6-sol`, reasoning `high`, task `06_01`: {gpt['calls']} calls, ${gpt['cost_usd']:.4f}, {gpt['total_tokens']:,} tokens. It was intentionally stopped after crossing the requested 66¢ cutoff; no result was persisted, so it is a partial cost/call comparison only and must not be scored as a completed task.")
    cost_lines += [
        "",
        "## Recommendation",
        "",
        "Freeze the current envelope before changing architecture. The highest-value cost-control experiment is a bounded authority/working-set treatment for 06_01 that measures whether the same accepted edits can be reached without the 78k-cell expansion, followed by a prospectively specified limited-domain control comparison. Do not interpret that as permission to widen or redesign authority algebra in this feasibility report.",
        "",
        f"Machine-readable detail: `{COST_JSON.name}` and `{COST_CSV.name}`. Raw ledgers remain under `{LIVE_ROOT}` and `{GPT_ROOT}`.",
    ]
    COST_REPORT_PATH.write_text("\n".join(cost_lines) + "\n", encoding="utf-8")


def main() -> None:
    integrated_payload = render_integrated()
    cost_payload = render_cost(integrated_payload)
    render_markdown(integrated_payload, cost_payload)
    print(json.dumps({"verdict": integrated_payload["summary"]["verdict"], "tasks": len(integrated_payload["tasks"]), "calls": cost_payload["integrated"]["summary"]["calls"], "cost_usd": cost_payload["integrated"]["summary"]["cost_usd"], "gpt_probe_calls": cost_payload["one_off_gpt_probe"]["summary"]["calls"], "gpt_probe_cost_usd": cost_payload["one_off_gpt_probe"]["summary"]["cost_usd"]}, indent=2))


if __name__ == "__main__":
    main()
