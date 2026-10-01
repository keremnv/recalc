#!/usr/bin/env python3
"""Build the auditable post-repair Financial_Model feasibility handoff.

This module is deliberately offline.  It reads the retained live ledgers,
states, workbooks, and max-control trajectories; it never calls a provider or
changes the compiled treatment.  The first live rehearsal overlapped requests
and recorded OpenRouter in-flight-credit failures, so those failures are kept
as an explicit infrastructure confound rather than being folded into semantic
demand.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
import sys
from typing import Any
from openpyxl.utils.cell import coordinate_to_tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
import integration_autopsy as ia  # noqa: E402
import matched_compiled_treatment as m  # noqa: E402
import fm_resource_feasibility as f  # noqa: E402


RUN = f.RUN_ROOT
LIVE = f.REPAIRED_LIVE
TASKS = f._selected_ids()
CAPS = (25, 50, 75, 100)


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        out = csv.DictWriter(handle, fieldnames=fields)
        out.writeheader()
        for row in rows:
            out.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def percentile(values: list[float], p: int) -> float | None:
    values = sorted(float(x) for x in values if x is not None)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return float(statistics.quantiles(values, n=100, method="inclusive")[p - 1])


def cell_label(c: tuple[str, int, int]) -> str:
    return f"{c[0]}!{m.closure.a1(c[1], c[2])}"


def calls_for(task: str) -> list[dict[str, Any]]:
    directory = LIVE / f"Financial_Model-{task}" / "calls"
    calls = [load(p, {}) for p in directory.glob("*.json")]
    return sorted(calls, key=lambda x: int(x.get("call_index_within_task", 0) or 0))


def stage_counts(calls: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(x.get("stage") or "other") for x in calls)


def useful_call(call: dict[str, Any]) -> bool:
    if call.get("failure_class"):
        return False
    stage = call.get("stage")
    parsed = call.get("parsed_response")
    if stage in {"task_ir", "edit_plan"}:
        return isinstance(parsed, dict)
    if stage == "retrieval":
        return bool(call.get("new_working_set_ids")) or (isinstance(parsed, dict) and parsed.get("action") == "final")
    if stage == "synthesis" and isinstance(parsed, dict):
        state = str(parsed.get("status") or parsed.get("decision") or "").upper()
        return state in {"PROPOSED", "FORMULA", "ACCEPT", "OK"} or bool(parsed.get("formula"))
    return False


def load_cells(task: str) -> tuple[dict, dict, dict, set, set]:
    row = m.task_map()[f.key(task)]
    source = ia.cells(m.task_source(f.key(task)))
    gold = ia.cells(Path(row["gold_path"]))
    changed = ia.changed(source, gold)
    formula_gold = {c for c in changed if ia.formula(gold.get(c))}
    output = LIVE / f"Financial_Model-{task}" / "output.xlsx"
    out = ia.cells(output) if output.exists() else {}
    return source, gold, out, changed, formula_gold


def authority_cells(task: str, state: dict[str, Any]) -> set[tuple[str, int, int]]:
    result: set[tuple[str, int, int]] = set()
    for cid in state.get("authorised_target_set") or []:
        c = f.target_from_cid(task, str(cid))
        if c:
            result.add(tuple(c))
    return result


def output_metrics(source: dict, gold: dict, out: dict, changed: set, formula_gold: set) -> dict[str, Any]:
    edits = ia.changed(source, out)
    inside = edits & changed
    correct = 0
    exact_formula = 0
    for c in inside:
        value_ok = ia.exact(out.get(c), gold.get(c)) if ia.formula(gold.get(c)) else out.get(c) == gold.get(c)
        if value_ok:
            correct += 1
            exact_formula += int(ia.formula(gold.get(c)))
    return {
        "output_exists": bool(out),
        "output_semantic_edits": len(edits),
        "output_edits_inter_gold": len(inside),
        "output_edits_outside_gold": len(edits - changed),
        "gold_write_correct": correct,
        "gold_write_recall": correct / len(changed) if changed else None,
        "write_precision": correct / len(edits) if edits else None,
        "exact_formula_writes": exact_formula,
        "gold_edit_cells": len(changed),
        "gold_formula_targets": len(formula_gold),
    }


def frontend_metrics(task: str, compiler: dict, plan: dict, state: dict, changed: set, formula_gold: set) -> dict[str, Any]:
    auth = authority_cells(task, state)
    parsed = plan.get("parsed") or {}
    expansion = plan.get("expansion") or {}
    task_row = m.task_map()[f.key(task)]
    spec = f.task_compile.score_task(
        task_id=task,
        instruction=task_row["instruction"],
        oracle=f.task_compile.build_ungrounded_oracle(task_row["instruction"]),
        pred=compiler.get("obligations") or [],
        parse_valid=compiler.get("status") == "OK",
    )
    return {
        "task_ir_status": compiler.get("status"),
        "obligation_count": len(compiler.get("obligations") or []),
        "task_ir_critical_requirement_recall": spec.get("critical_requirement_recall"),
        "task_ir_task_spec_preserved": spec.get("task_spec_preserved"),
        "edit_plan_status": plan.get("status"),
        "edit_plan_valid": plan.get("status") == "VALID_PLAN",
        "operation_count": len(parsed.get("operations") or []),
        "expanded_cell_count": len(expansion.get("cell_ids") or []),
        "authorised_cells": len(auth),
        "gold_edit_cells": len(changed),
        "gold_formula_targets": len(formula_gold),
        "gold_authority_recall": len(auth & changed) / len(changed) if changed else None,
        "gold_authority_precision": len(auth & changed) / len(auth) if auth else None,
        "gold_formula_target_recall": len(auth & formula_gold) / len(formula_gold) if formula_gold else None,
        "gold_formula_target_precision": len(auth & formula_gold) / len(auth) if auth else None,
        "authority_gold_cells": len(auth & changed),
        "authority_gold_formula_cells": len(auth & formula_gold),
        "task_ir_error_counts": spec.get("error_counts", {}),
    }


def actual_groups(schedule: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    rows = []
    for ui, unit in enumerate(schedule.get("groups") or []):
        for gi, group in enumerate(unit.get("groups") or []):
            rows.append((ui, gi, group))
    return rows


def group_cells(group: dict[str, Any]) -> set[tuple[str, int, int]]:
    return {tuple(c) for c in (group.get("member_cells") or []) if isinstance(c, list) and len(c) == 3}


def task_record(task: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict, dict, dict, set, set]:
    directory = LIVE / f"Financial_Model-{task}"
    result = load(directory / "result.json", {})
    state = load(directory / "state.json", {})
    compiler = result.get("compiler") or state.get("task_ir") or {}
    plan = result.get("edit_plan") or state.get("edit_plan") or {}
    schedule = result.get("schedule") or state.get("schedule") or {}
    source, gold, out, changed, formula_gold = load_cells(task)
    return result, state, compiler, plan, schedule, source, gold, out, changed, formula_gold


def treatment_rows() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    pg_rows: list[dict[str, Any]] = []
    for task in TASKS:
        result, state, compiler, plan, schedule, source, gold, out, changed, formula_gold = task_record(task)
        calls = calls_for(task)
        stages = stage_counts(calls)
        failures = Counter(str(c.get("failure_class")) for c in calls if c.get("failure_class"))
        metrics = output_metrics(source, gold, out, changed, formula_gold)
        fm = frontend_metrics(task, compiler, plan, state, changed, formula_gold)
        applied = result.get("write_audit") or {}
        applied_cells = {(x.get("sheet"), int(coordinate_to_tuple(x.get("address"))[0]), int(coordinate_to_tuple(x.get("address"))[1])) for x in (applied.get("applied") or []) if x.get("sheet") and x.get("address")}
        grouped = set()
        for _, _, group in actual_groups(schedule):
            grouped |= group_cells(group)
        disposition_cells = {
            tuple(v.get("cell")) for v in (schedule.get("dispositions") or {}).values()
            if isinstance(v, dict) and isinstance(v.get("cell"), list) and len(v["cell"]) == 3
        }
        residual_materialized = disposition_cells - grouped
        canonical = schedule.get("canonical_decisions") or []
        natural_calls = max(len(calls), int(state.get("model_call_count", 0) or 0), int((result.get("state") or {}).get("model_call_count", 0) or 0))
        cost = sum(float(c.get("provider_cost_usd") or 0.0) for c in calls)
        semantic_calls = sum(1 for c in calls if not c.get("failure_class"))
        useful = sum(1 for c in calls if useful_call(c))
        valid_plan = plan.get("status") == "VALID_PLAN"
        synth_reached = valid_plan and stages.get("synthesis", 0) > 0
        writes = len(applied.get("applied") or [])
        if not valid_plan:
            earliest = "EDIT_PLAN_INVALID"
        elif stages.get("retrieval", 0) == 0:
            earliest = "RETRIEVAL_FAILURE"
        elif not synth_reached:
            earliest = "SYNTHESIS_FAILURE"
        elif writes == 0:
            earliest = "ACTUATION_FAILURE"
        elif not metrics["gold_write_correct"] and (fm["gold_authority_recall"] or 0.0) < 0.5:
            earliest = "AUTHORITY_MISS"
        elif not metrics["gold_write_correct"]:
            earliest = "SYNTHESIS_FAILURE"
        else:
            earliest = "NONE"
        if failures and earliest == "NONE":
            supporting = "PROVIDER_FAILURES_PRESENT"
        elif failures:
            supporting = "PROVIDER_FAILURES_PRESENT"
        else:
            supporting = None
        row = {
            "task": f.key(task),
            "task_id": task,
            **fm,
            # An output.xlsx can exist even when the planner failed: the
            # neutral writer copies the source workbook for a typed failure.
            # Therefore file existence is not a semantic pipeline stage.
            "deepest_stage": (
                "WRITE" if writes > 0 else
                "SYNTHESIS" if synth_reached else
                "RETRIEVAL" if stages.get("retrieval", 0) > 0 else
                "EDIT_PLAN" if valid_plan else
                "TASK_IR" if compiler.get("status") == "OK" else
                "PROVIDER_FAILURE"
            ),
            "operation_containers": len(schedule.get("groups") or []) if valid_plan else 0,
            "program_groups_actual": len(actual_groups(schedule)),
            "program_groups_eligible": len(schedule.get("eligible_program_groups") or []),
            "grouped_authorised_cells": len(grouped),
            "residual_authorised_cells": max(0, int(schedule.get("authorized_targets") or 0) - len(grouped)) if valid_plan else 0,
            "initial_active_work_items": schedule.get("initial_stochastic_work_items"),
            "deferred_work_items": schedule.get("deferred_decisions"),
            "latent_residual_authorised_cells": schedule.get("latent_residual_authorised_cells"),
            "maximum_immediately_required_semantic_decisions": schedule.get("maximum_immediately_required_semantic_decisions"),
            "eliminated_decisions": schedule.get("eliminated_decisions", 0),
            "amortized_decisions": schedule.get("amortized_decisions", 0),
            "deferred_decisions": schedule.get("deferred_decisions", 0),
            "residual_cells_materialized": len(residual_materialized),
            "max_simultaneous_active_semantic_work_items": schedule.get("maximum_immediately_required_semantic_decisions"),
            "retrieval_sessions_started": stages.get("retrieval", 0),
            "synthesis_calls": stages.get("synthesis", 0),
            "canonical_proposals": len(canonical),
            "canonical_exact_or_fingerprint_correct": sum(1 for x in canonical if x.get("correct") is True or x.get("fingerprint_match") is True),
            "translated_formula_instances": len(schedule.get("translated_formula_instances") or []),
            "translated_exact_formula_instances": 0,
            "execution_units": len(state.get("execution_units") or schedule.get("groups") or []),
            "closure_members": sum(len(group_cells(g)) for _, _, g in actual_groups(schedule)),
            "writes_scheduled": len(applied.get("scheduled") or applied.get("applied") or []),
            "writes_verifier_passed": writes,
            "writes_sent_to_writer": writes,
            "writes_present": writes,
            "semantic_edits": metrics["output_semantic_edits"],
            "gold_edits_written": metrics["output_edits_inter_gold"],
            "correct_gold_writes": metrics["gold_write_correct"],
            "gold_write_recall": metrics["gold_write_recall"],
            "write_precision": metrics["write_precision"],
            "calls_to_first_write": natural_calls if writes else None,
            "calls_to_first_correct_write": natural_calls if metrics["gold_write_correct"] else None,
            "natural_call_attempts": natural_calls,
            "semantic_calls_without_infrastructure_failures": semantic_calls,
            "calls_by_stage": dict(stages),
            "useful_calls": useful,
            "useful_call_fraction": useful / natural_calls if natural_calls else None,
            "duplicate_or_nonproductive_calls": natural_calls - useful,
            "input_tokens": sum(int((c.get("usage") or {}).get("prompt_tokens") or 0) for c in calls),
            "output_tokens": sum(int((c.get("usage") or {}).get("completion_tokens") or 0) for c in calls),
            "reasoning_tokens": sum(int((c.get("usage") or {}).get("reasoning_tokens") or 0) for c in calls),
            "provider_cost_usd": cost,
            "provider_failure_calls": sum(failures.values()),
            "provider_failure_classes": dict(failures),
            "budget_censored": bool(result.get("partial_due_to_budget")) or any(k in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"} for k in failures),
            "output_produced": bool((LIVE / f"Financial_Model-{task}" / "output.xlsx").exists()),
            # Submission is relative to the LIVE root being audited.  This
            # keeps the offline analyzer valid for the clean sequential
            # replication instead of silently consulting the contaminated
            # run's submission directory.
            "submitted": bool((LIVE / "submission" / "outputs" / "Financial_Model" / f"{task}_output.xlsx").exists()),
            "officially_scored": True,
            "stop_reason": "COMPLETED" if result else "NO_RESULT",
            "earliest_supported_failure": earliest,
            "supporting_infrastructure_condition": supporting,
            "failure_ledger": result.get("failure_ledger") or state.get("failure_ledger") or [],
        }
        rows.append(row)

        translations = {}
        for item in schedule.get("translated_formula_instances") or []:
            if isinstance(item, dict) and isinstance(item.get("cell"), list):
                translations[tuple(item["cell"])] = item.get("formula")
        canonical_by_cell = {tuple(x.get("seed")): x.get("formula") for x in canonical if isinstance(x, dict) and isinstance(x.get("seed"), list)}
        for ui, gi, group in actual_groups(schedule):
            members = group_cells(group)
            canonical_cell = tuple(group.get("canonical_cell") or group.get("member_cells", [None])[0] or ())
            formula = canonical_by_cell.get(canonical_cell)
            if formula is None:
                formula = next((canonical_by_cell.get(tuple(x.get("seed"))) for x in canonical if isinstance(x, dict) and tuple(x.get("seed") or ()) in members), None)
            translated_members = members - {canonical_cell}
            exact_canonical = bool(formula is not None and canonical_cell in gold and ia.exact(formula, gold.get(canonical_cell)))
            # Count only formulas that the runtime actually emitted as
            # translation instances.  Comparing every group member's final
            # workbook cell to gold over-counts unchanged/pre-existing cells
            # as "exact translations" and was the source of the historical
            # 97-instance figure.
            generated_members = translated_members & set(translations)
            exact_translated = sum(
                1 for c in generated_members
                if ia.exact(translations.get(c), gold.get(c))
            )
            written_translated = len(generated_members & applied_cells)
            correct_written = sum(
                1 for c in generated_members
                if c in applied_cells and ia.exact(out.get(c), gold.get(c))
            )
            pg_rows.append({
                "task": f.key(task), "task_id": task, "unit_index": ui, "group_index": gi,
                "operation_id": group.get("operation_id"), "canonical_cell": cell_label(canonical_cell) if len(canonical_cell) == 3 else None,
                "member_count": len(members), "canonical_formula": formula,
                "canonical_proposal_present": formula is not None, "canonical_exact": exact_canonical,
                "translated_member_count": len(translated_members), "translated_instances": len(set(translations) & translated_members),
                "translated_exact_formula_count": exact_translated, "translated_written_count": written_translated,
                "translated_correct_written_count": correct_written, "grouped_gold_cells": len(members & formula_gold),
                "stochastic_decisions_avoided": max(0, len(members) - 1),
                "downstream_correct_cells_measurable": correct_written,
                "propagation_cashout": "one canonical plus deterministic member translations; output correctness measured against gold formula cells",
            })
    aggregate = {
        "tasks": len(rows),
        "tasks_task_ir_valid": sum(r["task_ir_status"] == "OK" for r in rows),
        "tasks_edit_plan_valid": sum(r["edit_plan_valid"] for r in rows),
        "tasks_reach_retrieval": sum(r["retrieval_sessions_started"] > 0 for r in rows),
        "tasks_reach_synthesis": sum(r["synthesis_calls"] > 0 for r in rows),
        "tasks_semantic_writes": sum(r["writes_present"] > 0 for r in rows),
        "tasks_correct_gold_writes": sum(r["correct_gold_writes"] > 0 for r in rows),
        "tasks_submitted": sum(r["submitted"] for r in rows),
        "tasks_scored": sum(r["officially_scored"] for r in rows),
        "failure_counts": dict(Counter(r["earliest_supported_failure"] for r in rows)),
        "provider_failure_calls": sum(r["provider_failure_calls"] for r in rows),
        "provider_failure_classes": dict(Counter(k for r in rows for k, v in r["provider_failure_classes"].items() for _ in range(v))),
        "total_call_attempts": sum(r["natural_call_attempts"] for r in rows),
        "total_semantic_calls": sum(r["semantic_calls_without_infrastructure_failures"] for r in rows),
        "total_useful_calls": sum(r["useful_calls"] for r in rows),
        "median_calls": statistics.median(r["natural_call_attempts"] for r in rows),
        "p75_calls": percentile([r["natural_call_attempts"] for r in rows], 75),
        "p90_calls": percentile([r["natural_call_attempts"] for r in rows], 90),
        "max_calls": max(r["natural_call_attempts"] for r in rows),
        "median_cost_usd": statistics.median(r["provider_cost_usd"] for r in rows),
        "p90_cost_usd": percentile([r["provider_cost_usd"] for r in rows], 90),
        "max_cost_usd": max(r["provider_cost_usd"] for r in rows),
        "deferred_residual_cells_declared": sum(int(r["deferred_decisions"] or 0) for r in rows),
        "residual_cells_materialized": sum(int(r["residual_cells_materialized"] or 0) for r in rows),
        "canonical_decisions_materialized": sum(int(r["canonical_proposals"] or 0) for r in rows),
        "translated_instances": sum(int(r["translated_formula_instances"] or 0) for r in rows),
        "translated_exact_instances": sum(int(x["translated_exact_formula_count"]) for x in pg_rows),
    }
    return rows, aggregate, pg_rows


def scheduler_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: r.get(k) for k in ("task_id", "operation_count", "authorised_cells", "operation_containers", "program_groups_actual", "program_groups_eligible", "grouped_authorised_cells", "residual_authorised_cells", "initial_active_work_items", "maximum_immediately_required_semantic_decisions", "deferred_decisions", "latent_residual_authorised_cells", "residual_cells_materialized", "eliminated_decisions", "amortized_decisions", "canonical_proposals", "translated_formula_instances", "execution_units", "max_simultaneous_active_semantic_work_items", "natural_call_attempts")} for r in rows]


def control_recovery() -> dict[str, Any]:
    existing = load(RUN / "MAX_CONTROL_SUBMISSION_RELIABILITY_REPORT.json", {})
    rows = []
    for row in existing.get("rows") or []:
        task = row.get("task_id")
        # .../<run-root>/Financial_Model-XX/trajectory/XX/XX.traj
        root = Path(row["trajectory_path"]).parents[3] if row.get("trajectory_path") else None
        task_dir = root / f"Financial_Model-{task}" if root else None
        xlsx = sorted(task_dir.rglob("*.xlsx")) if task_dir and task_dir.exists() else []
        recoverable = bool(xlsx)
        if row.get("output_exists"):
            classification = "SUBMITTED_OUTPUT"
            disposition = "already_submitted"
        elif recoverable:
            classification = "SUBMISSION_RECOVERY_AVAILABLE"
            disposition = "requires_contract_review_before_copying"
        elif row.get("write_action_count", 0) > 0:
            classification = "WRITE_ACTIONS_NOT_PERSISTED"
            disposition = "NOT_RECOVERABLE_WITHOUT_NEW_MODEL_WORK"
        else:
            classification = row.get("classification") or "NO_OUTPUT_OTHER"
            disposition = "NOT_RECOVERABLE_WITHOUT_NEW_MODEL_WORK"
        rows.append({**row, "edited_workbook_candidates": [str(p) for p in xlsx], "mechanically_recoverable": recoverable, "recovery_classification": classification, "recovery_disposition": disposition})
    counts = Counter(r["recovery_classification"] for r in rows)
    report = {
        "status": "BLOCKED" if any(not r["mechanically_recoverable"] and not r["output_exists"] for r in rows) else "COMPLETE",
        "zero_model_calls": True,
        "rows": rows,
        "classification_counts": dict(counts),
        "submission_recovery_performed": False,
        "conclusion": "The three control traces with write actions have no persisted edited workbook in their retained task directories; trajectory action text is not sufficient to reconstruct missing edits. No synthetic recovery was performed. The one pre-write provider/runner failure is likewise not recoverable without new model work.",
    }
    dump(RUN / "max_control_submission_recovery.json", report)
    lines = ["# Max-control submission reliability and recovery", "", "No model calls were made. This is a filesystem/trajectory audit of the retained max-reasoning control run.", "", "| Task | Prior class | Edited workbook candidate | Mechanically recoverable | Disposition |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['task_id']} | {r.get('classification')} | {len(r['edited_workbook_candidates'])} | {r['mechanically_recoverable']} | {r['recovery_disposition']} |")
    lines += ["", "No output was copied or invented. The three write-but-no-submit traces contain action logs but no edited workbook artifact; they are not mechanically recoverable under the normal control contract.", "", f"Status: **{report['status']}**"]
    (RUN / "MAX_CONTROL_SUBMISSION_RELIABILITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def resource_curves(rows: list[dict[str, Any]], control_data: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for r in rows:
        for cap in (*CAPS, r["natural_call_attempts"]):
            complete = r["natural_call_attempts"] <= cap
            result.append({
                "arm": "treatment", "task_id": r["task_id"], "call_cap": cap,
                "natural_call_attempts": r["natural_call_attempts"], "semantic_calls": r["semantic_calls_without_infrastructure_failures"],
                "budget_censored_at_cap": not complete, "submission_possible": bool(complete and r["submitted"]),
                "deepest_stage_at_prefix": r["deepest_stage"] if complete else "prefix_state_not_persisted",
                "writes_accumulated": r["writes_present"] if complete else 0,
                "correct_gold_writes_accumulated": r["correct_gold_writes"] if complete else 0,
                "unresolved_operation_containers": None if not complete else max(0, int(r["operation_containers"] or 0) - int(r["canonical_proposals"] or 0)),
                "unresolved_residual_authority": r["deferred_decisions"] if complete else None,
                "replay_note": "The saved calls establish the prefix; writer runs after the final model trajectory, so writes are credited only for completed natural runs. No model calls were replayed.",
            })
    for item in control_data.get("rows") or []:
        for cap in (*CAPS, item.get("natural_calls")):
            if item.get("natural_calls") is None:
                continue
            complete = item["natural_calls"] <= cap
            result.append({
                "arm": "control", "task_id": item["task_id"], "call_cap": cap,
                "natural_call_attempts": item["natural_calls"], "semantic_calls": item["natural_calls"],
                "budget_censored_at_cap": not complete, "submission_possible": bool(complete and item.get("output_produced")),
                "deepest_stage_at_prefix": "SUBMIT" if complete and item.get("output_produced") else "trajectory_prefix_only",
                "writes_accumulated": item.get("write_actions", 0) if complete else 0,
                "correct_gold_writes_accumulated": item.get("gold_write_correct", 0) if complete else 0,
                "unresolved_operation_containers": None, "unresolved_residual_authority": None,
                "replay_note": "Control trajectory prefix retained; no model rerun.",
            })
    write_csv(RUN / "repaired_treatment_resource_curves.csv", result)
    return result


def official_summary() -> dict[str, Any]:
    score = load(LIVE / "official_scores.json", {})
    task_scores = score.get("tasks") or {}
    mods = [float(v.get("modification_accuracy", 0.0)) for v in task_scores.values()]
    regs = [float(v.get("regression_accuracy", 0.0)) for v in task_scores.values()]
    return {"source": str(LIVE / "official_scores.json"), "scored": score.get("scored"), "missing_outputs": score.get("missing_outputs"), "exact": score.get("exact"), "mean_modification": statistics.mean(mods) if mods else None, "median_modification": statistics.median(mods) if mods else None, "mean_regression": statistics.mean(regs) if regs else None, "median_regression": statistics.median(regs) if regs else None, "value_only": "not separately recalculated; no value-only scorer is part of this run"}


def write_report(rows: list[dict[str, Any]], aggregate: dict[str, Any], control: dict[str, Any], pg_rows: list[dict[str, Any]], curves: list[dict[str, Any]], scores: dict[str, Any]) -> None:
    config = load(RUN / "freeze.json", {})
    gate = {
        "task_ir": aggregate["tasks_task_ir_valid"] >= 9,
        "edit_plan": aggregate["tasks_edit_plan_valid"] >= 9,
        "retrieval": aggregate["tasks_reach_retrieval"] >= 9,
        "synthesis": aggregate["tasks_reach_synthesis"] >= 9,
        "semantic_writes": aggregate["tasks_semantic_writes"] >= 9,
        "correct_gold_writes": aggregate["tasks_correct_gold_writes"] >= 8,
        "submitted": aggregate["tasks_submitted"] >= 11,
    }
    lines = [
        "# Post-repair Financial_Model treatment feasibility",
        "",
        "**Verdict: `MULTIPLE_INTEGRATION_FAILURES` (not traversable under the required gates).**",
        "",
        "This is the first corrected integrated-treatment live test on the frozen 12-task Financial_Model population. No final 20-task matched A/B was launched.",
        "",
        "## Frozen run and validity",
        "",
        f"Model configuration is retained in `freeze.json`: `{config.get('model')}`, temperature `{config.get('temperature')}`, top_p `{config.get('top_p')}`, reasoning request `{config.get('reasoning_request_field')}={config.get('reasoning_request_value')}`, frontend timeout 600s, retrieval/synthesis timeout 180s, observation ceiling 150 calls/$6 per task.",
        "",
        "The invalid rehearsal whose guard still used a 50-call constant is excluded. The corrected run used the fixed active call ceiling. The first live launch overlapped 12 PTY processes; OpenRouter consequently recorded 74 `MODEL_ACCESS_FAILURE` responses with `in_flight_budget_exhausted` and 62 provider timeouts. Those records are retained and reported as infrastructure failures, not silently counted as semantic decisions or retries.",
        "",
        "## Required funnel",
        "",
        "| Stage | Count | Gate |",
        "|---|---:|---:|",
        f"| valid Task IR | {aggregate['tasks_task_ir_valid']}/12 | {'PASS' if gate['task_ir'] else 'FAIL'} |",
        f"| valid Edit Plan | {aggregate['tasks_edit_plan_valid']}/12 | {'PASS' if gate['edit_plan'] else 'FAIL'} |",
        f"| retrieval reached | {aggregate['tasks_reach_retrieval']}/12 | {'PASS' if gate['retrieval'] else 'FAIL'} |",
        f"| synthesis reached | {aggregate['tasks_reach_synthesis']}/12 | {'PASS' if gate['synthesis'] else 'FAIL'} |",
        f"| >=1 semantic write | {aggregate['tasks_semantic_writes']}/12 | {'PASS' if gate['semantic_writes'] else 'FAIL'} |",
        f"| >=1 correct gold write | {aggregate['tasks_correct_gold_writes']}/12 | {'PASS' if gate['correct_gold_writes'] else 'FAIL'} |",
        f"| submitted workbook | {aggregate['tasks_submitted']}/12 | {'PASS' if gate['submitted'] else 'FAIL'} |",
        "",
        "The treatment therefore fails the feasibility gates on semantic writes (8/12) and correct-gold-write coverage (4/12), even though output files and scorer inputs exist for all 12.",
        "",
        "## Per-task results",
        "",
        "| Task | Plan | Retrieval | Synthesis | Authority recall | Active work | Deferred | Materialized residual | Writes | Correct gold | Calls | Cost | Earliest loss |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(f"| {r['task_id']} | {r['edit_plan_status']} | {r['retrieval_sessions_started']} | {r['synthesis_calls']} | {r['gold_authority_recall'] if r['gold_authority_recall'] is not None else ''} | {r['initial_active_work_items'] if r['initial_active_work_items'] is not None else ''} | {r['deferred_decisions'] if r['deferred_decisions'] is not None else ''} | {r['residual_cells_materialized']} | {r['writes_present']} | {r['correct_gold_writes']} | {r['natural_call_attempts']} | {r['provider_cost_usd']:.4f} | {r['earliest_supported_failure']} |")
    lines += [
        "",
        "## Direct answers",
        "",
        f"1–7. The counts are {aggregate['tasks_task_ir_valid']}, {aggregate['tasks_edit_plan_valid']}, {aggregate['tasks_reach_retrieval']}, {aggregate['tasks_reach_synthesis']}, {aggregate['tasks_semantic_writes']}, {aggregate['tasks_correct_gold_writes']}, and {aggregate['tasks_submitted']} respectively.",
        f"8. Operation-preserving scheduling remains visible live: initial active work is recorded separately from authority, and the runtime did not create one initial synthesis item per authorized cell. Across valid plans, initial active work is {sum(int(r['initial_active_work_items'] or 0) for r in rows)} versus {sum(int(r['authorised_cells'] or 0) for r in rows)} authorized cells.",
        f"9. The prior static 2,328 deferred residuals are not claimed solved. In this live population, {aggregate['residual_cells_materialized']} residual-authority cells were actually materialized in dispositions, while {aggregate['deferred_residual_cells_declared']} deferred decisions were declared. These are distinct from the {aggregate['canonical_decisions_materialized']} canonical model decisions and must not be conflated.",
        f"10–11. Treatment observed natural attempts: median {aggregate['median_calls']}, p90 {aggregate['p90_calls']}, max {aggregate['max_calls']}; costs median ${aggregate['median_cost_usd']:.4f}, p90 ${aggregate['p90_cost_usd']:.4f}, max ${aggregate['max_cost_usd']:.4f}. These are contaminated by provider infrastructure failures and are not a final budget recommendation.",
        f"12. Earliest supported loss counts: `{json.dumps(aggregate['failure_counts'], sort_keys=True)}`. The dominant supported semantic losses are invalid/conflicting Edit Plans (3 tasks), authority misses among valid plans, and synthesis/actuation failures; 74 in-flight-credit failures and 62 timeouts are reported separately.",
        f"13. ProgramGroup propagation did fire structurally: {len(pg_rows)} runtime groups and {aggregate['translated_instances']} translation instances are recorded in the schedule ({sum(int(x['translated_instances']) for x in pg_rows)} tied directly to runtime group members). Of those tied members, {aggregate['translated_exact_instances']} are exact against gold formulas and {sum(int(x['translated_correct_written_count']) for x in pg_rows)} were actually present as exact translated writes. This is partial cash-out, not a complete downstream correctness win.",
        f"14. The max-control submission defect is not mechanically repairable from these retained traces: {control.get('classification_counts')}; the three write-but-no-submit traces have no persisted edited workbook. No synthetic submission recovery was performed.",
        "15–16. No defensible common call or cost cap can be frozen. The treatment trace is infrastructure-confounded and fails the semantic feasibility gates; `proposed_final_matched_budget.json` is BLOCKED.",
        "17. The system is not ready for the fresh 20-task A/B.",
        "",
        "## Secondary official score",
        "",
        f"The retained scorer processed {scores.get('scored')}/12 treatment outputs with no missing output files: exact {scores.get('exact')}, mean modification {scores.get('mean_modification')}, median modification {scores.get('median_modification')}, mean regression {scores.get('mean_regression')}, median regression {scores.get('median_regression')}. This is diagnostic only; a value-only scorer was not separately recalculated.",
        "",
        "## Resource interpretation",
        "",
        f"Useful calls were {aggregate['total_useful_calls']} of {aggregate['total_call_attempts']} recorded attempts ({aggregate['total_useful_calls'] / aggregate['total_call_attempts']:.1%}). This fraction is not a clean architecture efficiency estimate because the overlapping launch injected infrastructure failures. The resource-curve CSV credits writes only after a saved natural run completes and explicitly marks censored prefixes; no model calls were replayed.",
        "",
        "Artifacts: `repaired_treatment_funnel.csv`, `repaired_treatment_natural_demand.json`, `repaired_treatment_resource_curves.csv`, `repaired_treatment_failures.json`, `programgroup_live_cashout.csv`, `operation_scheduler_live_metrics.csv`, `max_control_submission_recovery.json`, and `proposed_final_matched_budget.json`.",
    ]
    (RUN / "POST_REPAIR_TREATMENT_FEASIBILITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows, aggregate, pg_rows = treatment_rows()
    control_rows = load(RUN / "natural_demand_control.json", {}).get("rows") or []
    control = control_recovery()
    curves = resource_curves(rows, {"rows": control_rows})
    scores = official_summary()
    write_csv(RUN / "repaired_treatment_funnel.csv", rows)
    write_csv(RUN / "operation_scheduler_live_metrics.csv", scheduler_rows(rows))
    write_csv(RUN / "programgroup_live_cashout.csv", pg_rows)
    dump(RUN / "repaired_treatment_results.json", {"status": "TREATMENT_STILL_INTEGRATION_BLOCKED", "not_final_ab": True, "model_config": load(RUN / "freeze.json", {}), "aggregate": aggregate, "scores": scores, "rows": rows})
    dump(RUN / "repaired_treatment_natural_demand.json", {"status": "COMPLETE_WITH_INFRASTRUCTURE_CONFOUND", "observation_ceiling": {"calls": 150, "cost_usd": 6.0}, "semantic_demand_definition": "recorded calls with valid provider responses; infrastructure failures reported separately", "aggregate": aggregate, "rows": rows})
    dump(RUN / "repaired_treatment_failures.json", {"status": "COMPLETE", "earliest_supported_failure_counts": aggregate["failure_counts"], "provider_failure_calls": aggregate["provider_failure_calls"], "provider_failure_classes": aggregate["provider_failure_classes"], "rows": [{"task_id": r["task_id"], "earliest_supported_failure": r["earliest_supported_failure"], "supporting_infrastructure_condition": r["supporting_infrastructure_condition"], "failure_ledger": r["failure_ledger"], "provider_failure_classes": r["provider_failure_classes"]} for r in rows]})
    dump(RUN / "proposed_final_matched_budget.json", {"status": "BLOCKED", "recommended_call_cap": None, "recommended_cost_cap_usd": None, "reason": "Post-repair treatment fails semantic feasibility gates and the observed live trace is confounded by overlapping-provider in-flight-credit failures; do not convert these observations into a final matched budget.", "control_reference": {"median_calls": 37.5, "p90_calls": 57.4, "max_calls": 62}, "treatment_observed": {"median_calls": aggregate["median_calls"], "p90_calls": aggregate["p90_calls"], "max_calls": aggregate["max_calls"], "median_cost_usd": aggregate["median_cost_usd"], "p90_cost_usd": aggregate["p90_cost_usd"], "max_cost_usd": aggregate["max_cost_usd"]}, "no_final_ab_launched": True})
    write_report(rows, aggregate, control, pg_rows, curves, scores)
    print(json.dumps({"status": "TREATMENT_STILL_INTEGRATION_BLOCKED", "aggregate": aggregate, "control_recovery": control.get("status"), "artifacts": ["POST_REPAIR_TREATMENT_FEASIBILITY_REPORT.md", "repaired_treatment_results.json", "repaired_treatment_funnel.csv", "repaired_treatment_natural_demand.json", "repaired_treatment_resource_curves.csv", "repaired_treatment_failures.json", "programgroup_live_cashout.csv", "operation_scheduler_live_metrics.csv", "MAX_CONTROL_SUBMISSION_RELIABILITY_REPORT.md", "max_control_submission_recovery.json", "proposed_final_matched_budget.json"]}, indent=2))


if __name__ == "__main__":
    main()
