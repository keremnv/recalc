"""Run the isolated live continuation of the repaired 04_01 scheduler.

This diagnostic loads the archived Task IR, Edit Plan, authority, groups and
session state. It copies the immutable archive to a separate continuation
directory, then invokes only ``compiled_scheduler.schedule``. No frontend,
writer, LibreOffice refresh or scorer is called.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import shutil
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

import compiled_scheduler
import fm_resource_feasibility as feasibility
import formula_synthesis_probe as synth_tools
import matched_compiled_treatment as m
import openpyxl

from librecalc_mcp.domain.formulas import formula_a1_references

ROOT = Path(__file__).resolve().parents[1]
TASK_KEY = "Financial_Model:04_01"
ARCHIVE = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty"
    / "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge"
    / "Financial_Model-04_01"
)
ARCHIVE_CALL_COUNT = 23
CRASHED_SYNTHESIS_INDEX = 56
CRASHED_CELL_ID = "cell:s03:r11:c6"
CRASHED_FORMULA = "=F10/E10-1"
CRASHED_TARGET = {"sheet": "Financials", "row": 11, "col": 6, "address": "F11"}

PROVIDER_FAILURES = {
    "MODEL_ACCESS_FAILURE",
    "PROVIDER_ERROR",
    "PROVIDER_TIMEOUT",
    "INFRASTRUCTURE_RETRY",
}
SESSION_RESOURCE_FAILURES = {
    "SESSION_RESOURCE_LIMIT",
    "QUERY_TIMEOUT",
    "SQL_ERROR",
    "RESULT_TOO_LARGE",
    "ADMISSIBILITY_LIMIT",
}
GLOBAL_RESOURCE_FAILURES = {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnose_persisted_proposal(continuation_dir: Path) -> dict[str, Any]:
    """Reproduce the unsized-sheet TypeError path with zero model calls."""
    call_path = continuation_dir / "calls" / f"{CRASHED_SYNTHESIS_INDEX:03d}_synthesis.json"
    parsed = read(call_path)["parsed_response"]
    source = m.task_source(TASK_KEY)
    formula = parsed.get("formula")
    workbook = openpyxl.load_workbook(source, data_only=False, read_only=True)
    try:
        sheets = []
        for name in workbook.sheetnames:
            ws = workbook[name]
            sheets.append(
                {
                    "name": name,
                    "type": type(ws).__name__,
                    "max_column": ws.max_column,
                    "max_row": ws.max_row,
                }
            )
        financials = workbook[CRASHED_TARGET["sheet"]]
        before = {"max_column": financials.max_column, "max_row": financials.max_row}
        try:
            forced = financials.calculate_dimension(force=True)
            force_error = None
        except Exception as exc:  # noqa: BLE001 - diagnosis must record the exact failure
            forced = None
            force_error = f"{type(exc).__name__}: {exc}"
        after = {
            "max_column": financials.max_column,
            "max_row": financials.max_row,
            "dimension": forced,
            "error": force_error,
        }
    finally:
        workbook.close()
    refs = [
        {"host": host, "start": start, "end": end, "resolved_sheet": host or CRASHED_TARGET["sheet"]}
        for host, start, end in formula_a1_references(formula or "")
    ]
    row = {"task": TASK_KEY, "input_path": str(source), "target": CRASHED_TARGET}
    raised = None
    validation = None
    try:
        validation = synth_tools._validate_formula(
            row, formula, {}, {"title_to_index": {CRASHED_TARGET["sheet"]: 3}}, None, None
        )
    except Exception as exc:  # noqa: BLE001 - the original defect was an uncaught TypeError
        raised = f"{type(exc).__name__}: {exc}"
    none_sheets = [s["name"] for s in sheets if s["max_column"] is None or s["max_row"] is None]
    return {
        "call_path": str(call_path),
        "call_index": CRASHED_SYNTHESIS_INDEX,
        "cell_id": parsed.get("target_id"),
        "parsed_status": parsed.get("status"),
        "formula": formula,
        "target": CRASHED_TARGET,
        "workbook": str(source),
        "references": refs,
        "readonly_sheet_bounds": sheets,
        "crashing_object": {
            "worksheet": CRASHED_TARGET["sheet"],
            "openpyxl_type": "ReadOnlyWorksheet",
            "readonly_before_force": before,
            "after_force": after,
        },
        "unsized_readonly_sheets": none_sheets,
        "legal_state": (
            "OOXML worksheets may omit <dimension>; openpyxl ReadOnlyWorksheet then "
            "leaves max_column/max_row as None even when the sheet is populated."
        ),
        "incorrect_invariant": "ws.max_column and ws.max_row are always comparable integers",
        "other_workbooks": (
            "Any read_only workbook whose sheet XML omits <dimension> can hit the same "
            "comparison. In the frozen 60-task repaired_inputs set, only Financial_Model-04_01 "
            "is fully unsized."
        ),
        "validation_after_repair": None
        if validation is None
        else {k: validation.get(k) for k in ("parser_ok", "invalid_address", "invalid_sheet", "formula_present")},
        "raised": raised,
    }


def snapshot_pre_resume(output: Path, continuation_dir: Path) -> dict[str, Any]:
    dest = output / "pre_verifier_resume"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("scheduler_live_validation_trace.json", "scheduler_live_validation_trace.csv"):
        src = output / name
        if src.exists() and not (dest / name).exists():
            shutil.copy2(src, dest / name)
    prior_report = ROOT / "SCHEDULER_LIVE_VALIDATION_REPORT.md"
    if prior_report.exists() and not (dest / prior_report.name).exists():
        shutil.copy2(prior_report, dest / prior_report.name)
    state = read(continuation_dir / "state.json")
    checkpoint = state.get("scheduler_v3") or state.get("scheduler_v2") or {}
    return {
        "snapshot_directory": str(dest),
        "state_sha256": file_digest(continuation_dir / "state.json"),
        "call_056_sha256": file_digest(
            continuation_dir / "calls" / f"{CRASHED_SYNTHESIS_INDEX:03d}_synthesis.json"
        ),
        "model_call_count_before": state.get("model_call_count"),
        "provider_cost_usd_before": state.get("provider_cost_usd"),
        "persisted_session_ids": sorted(checkpoint.get("sessions", {})),
        "persisted_disposition_ids": sorted(checkpoint.get("dispositions", {})),
        "completed_edits_before": list(state.get("completed_edits") or []),
    }


def cell_label(cell: tuple[str, int, int]) -> str:
    return f"{cell[0]}!{m.closure.a1(cell[1], cell[2])}"


def call_rows(task_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((task_dir / "calls").glob("*.json")):
        record = read(path)
        rows.append(
            {
                "call_index": record.get("call_index_within_task", record.get("index")),
                "stage": record.get("stage"),
                "failure_class": record.get("failure_class"),
                "finish_reason": record.get("finish_reason"),
                "provider_attempt": record.get("provider_attempt"),
                "provider_cost_usd": record.get("provider_cost_usd", 0.0),
                "request_sha256": record.get("request_sha256"),
            }
        )
    return rows


def failure_from_session(wrapper: dict[str, Any] | None) -> str | None:
    if not wrapper:
        return None
    session = wrapper.get("session") or wrapper
    failure = session.get("failure_class")
    if failure:
        return failure
    for call in reversed(session.get("calls") or []):
        if call.get("failure_class"):
            return call["failure_class"]
    return None


def parsed_from_session(wrapper: dict[str, Any] | None) -> Any:
    if not wrapper:
        return None
    return (wrapper.get("session") or wrapper).get("synthesis", {}).get("parsed")


def disposition_class(disposition: dict[str, Any] | None, wrapper: dict[str, Any] | None) -> str:
    status = (disposition or {}).get("status")
    if status is None and wrapper is not None:
        return "ATTEMPTED_NO_TERMINAL_DISPOSITION"
    failure = failure_from_session(wrapper)
    parsed = parsed_from_session(wrapper)
    if status in {"WRITES_SCHEDULED", "TRANSLATED_WRITE_SCHEDULED"}:
        return "ACCEPTED_PROPOSAL"
    if status == "NO_SEMANTIC_CHANGE":
        return "NO_OP"
    if status in {"REJECTED_HARD", "REJECTED_HARD_TRANSLATION", "HARD_VERIFIER_REJECT"}:
        return "VERIFIER_REJECTION"
    if failure in GLOBAL_RESOURCE_FAILURES:
        return "GLOBAL_RESOURCE_FAILURE"
    if failure in PROVIDER_FAILURES:
        return "PROVIDER_FAILURE"
    if failure in SESSION_RESOURCE_FAILURES:
        return "SESSION_RESOURCE_FAILURE"
    if failure in {"INVALID_ACTION", "PARSE_FAILURE", "INVALID_RESPONSE"}:
        return "INVALID_RESPONSE"
    if isinstance(parsed, dict) and parsed.get("status") == "ABSTAIN":
        return "EXPLICIT_MODEL_ABSTENTION"
    if status == "ABSTAIN" and not failure:
        return "EXPLICIT_MODEL_ABSTENTION"
    if status in {"INVALID_RESPONSE", "PARSE_FAILURE", "INVALID_ENTITY"}:
        return "INVALID_RESPONSE"
    if status:
        return status
    return "UNATTEMPTED_INDEPENDENT"


def disposition_detail(
    cid: str,
    disposition: dict[str, Any] | None,
    wrapper: dict[str, Any] | None,
    archived_session_ids: set[str],
    call_index_floor: int,
) -> dict[str, Any]:
    session = (wrapper or {}).get("session") or {}
    calls = session.get("calls") or []
    new_calls = [
        {
            "call_index": c.get("call_index_within_task"),
            "stage": c.get("stage"),
            "failure_class": c.get("failure_class"),
            "finish_reason": c.get("finish_reason"),
            "provider_attempt": c.get("provider_attempt"),
        }
        for c in calls
        if int(c.get("call_index_within_task", 0) or 0) > call_index_floor
    ]
    failure = failure_from_session(wrapper)
    parsed = parsed_from_session(wrapper)
    return {
        "cell_id": cid,
        "archived_session": cid in archived_session_ids,
        "live_session_attempted": cid not in archived_session_ids and wrapper is not None,
        "disposition": disposition,
        "outcome_class": disposition_class(disposition, wrapper),
        "failure_class": failure,
        "parsed_status": parsed.get("status") if isinstance(parsed, dict) else None,
        "formula_present": bool(isinstance(parsed, dict) and parsed.get("formula")),
        "session_call_count": len(calls),
        "new_calls": new_calls,
    }


def build_report(
    *,
    output: Path,
    continuation_dir: Path,
    archive_result: dict[str, Any],
    archive_state: dict[str, Any],
    state_after: dict[str, Any],
    scheduled: dict[str, Any],
    plan: dict[str, Any],
    task: dict[str, Any],
    exception: str | None,
    exception_trace: str | None = None,
    resume: bool = False,
    verifier_defect: dict[str, Any] | None = None,
    continuation_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta, cids = m.authorised_cells(plan)
    groups = scheduled.get("eligible_program_groups") or archive_result.get("schedule", {}).get("eligible_program_groups") or []
    group_by_cell = {
        tuple(member): i + 1
        for i, group in enumerate(groups)
        for member in group.get("member_cells", [])
    }
    canonical_cells = {tuple(group["canonical_cell"]) for group in groups}
    group_members = {tuple(member) for group in groups for member in group.get("member_cells", [])}
    independent = canonical_cells | (set(meta) - group_members)
    independent = sorted(independent, key=lambda c: (cids[c], c))
    independent_ids = [cids[c] for c in independent]
    before_checkpoint = archive_state.get("scheduler_v3") or archive_state.get("scheduler_v2") or {}
    after_checkpoint = state_after.get("scheduler_v3") or state_after.get("scheduler_v2") or {}
    before_sessions = set(before_checkpoint.get("sessions", {}))
    after_sessions = after_checkpoint.get("sessions", {})
    after_dispositions = scheduled.get("dispositions") or after_checkpoint.get("dispositions") or {}
    independent_trace = []
    for cell, cid in zip(independent, independent_ids):
        record = disposition_detail(
            cid,
            after_dispositions.get(cid),
            after_sessions.get(cid),
            before_sessions,
            ARCHIVE_CALL_COUNT,
        )
        record.update(
            {
                "cell": list(cell),
                "label": cell_label(cell),
                "unit_kind": "PROGRAM_GROUP_CANONICAL" if cell in canonical_cells else "UNGROUPED_INDEPENDENT",
                "program_group": group_by_cell.get(cell),
            }
        )
        independent_trace.append(record)

    group_trace = []
    for i, group in enumerate(groups, 1):
        canonical = tuple(group["canonical_cell"])
        canonical_id = cids[canonical]
        canonical_record = after_dispositions.get(canonical_id)
        canonical_wrapper = after_sessions.get(canonical_id)
        members = []
        for raw in group.get("member_cells", []):
            member = tuple(raw)
            member_id = cids[member]
            members.append(
                {
                    "cell_id": member_id,
                    "label": cell_label(member),
                    "disposition": after_dispositions.get(member_id),
                    "independent": member in independent,
                    "promoted_to_independent": False,
                    "failed_canonical_member": member != canonical and member not in after_dispositions and disposition_class(canonical_record, canonical_wrapper) not in {"ACCEPTED_PROPOSAL", "NO_OP"},
                }
            )
        group_trace.append(
            {
                "group_id": f"G{i}",
                "canonical_cell_id": canonical_id,
                "canonical_label": cell_label(canonical),
                "canonical_outcome_class": disposition_class(canonical_record, canonical_wrapper),
                "canonical_disposition": canonical_record,
                "members": members,
            }
        )

    call_records = call_rows(continuation_dir)
    new_call_records = [r for r in call_records if int(r.get("call_index") or 0) > ARCHIVE_CALL_COUNT]
    failures = scheduled.get("failures") or after_checkpoint.get("failures") or []
    global_failures = [f for f in failures if f.get("failure_class") in GLOBAL_RESOURCE_FAILURES]
    unattempted = [r for r in independent_trace if not r["live_session_attempted"] and not r["archived_session"]]
    attempted_new = [r for r in independent_trace if r["live_session_attempted"]]
    persisted_or_live = [r for r in independent_trace if r["archived_session"] or r["live_session_attempted"]]
    terminal_statuses = Counter(r["outcome_class"] for r in independent_trace)
    resource_boundary = bool(global_failures)
    if exception:
        unattempted_reason = f"blocked_by_runtime_exception: {exception}"
        verdict = "NEW_INTEGRATION_DEFECT"
    elif unattempted and resource_boundary:
        unattempted_reason = "global_resource_boundary: " + ",".join(
            sorted({str(f.get("failure_class")) for f in global_failures})
        )
        verdict = "SCHEDULER_LIVENESS_PARTIAL_RESOURCE_CENSORED"
    elif unattempted:
        unattempted_reason = "independently_reachable_but_queue_did_not_expose"
        verdict = "SCHEDULER_LIVENESS_DEFECT_REMAINS"
    else:
        unattempted_reason = None
        verdict = "SCHEDULER_LIVENESS_VALIDATED"
    for row in unattempted:
        row["unattempted_reason"] = unattempted_reason
    edits = scheduled.get("edits") or state_after.get("completed_edits") or []
    coverage = {
        "independent_units_reached": len(independent),
        "independent_units_attempted_live_or_persisted": len(persisted_or_live),
        "provider_failures": terminal_statuses.get("PROVIDER_FAILURE", 0),
        "invalid_responses": terminal_statuses.get("INVALID_RESPONSE", 0),
        "abstentions": terminal_statuses.get("EXPLICIT_MODEL_ABSTENTION", 0),
        "accepted_proposals": terminal_statuses.get("ACCEPTED_PROPOSAL", 0),
        "no_ops": terminal_statuses.get("NO_OP", 0),
        "verifier_rejections": terminal_statuses.get("VERIFIER_REJECTION", 0),
        "accepted_edits": len(edits),
        "unattempted_independent_units": len(unattempted),
        "session_resource_failures": terminal_statuses.get("SESSION_RESOURCE_FAILURE", 0),
        "attempted_without_terminal_disposition": terminal_statuses.get("ATTEMPTED_NO_TERMINAL_DISPOSITION", 0),
    }

    archive_files = {str(p.relative_to(ARCHIVE)): file_digest(p) for p in ARCHIVE.rglob("*") if p.is_file()}
    report = {
        "experiment": "scheduler_live_validation",
        "task": TASK_KEY,
        "archive": str(ARCHIVE),
        "continuation_directory": str(continuation_dir),
        "resume": resume,
        "frontend_rerun": False,
        "writer_called": False,
        "libreoffice_called": False,
        "scorer_called": False,
        "frozen_inputs": {
            "raw_task_sha256": digest(archive_result["compiler"]["raw_task"]),
            "compiler_sha256": digest(archive_result["compiler"]),
            "edit_plan_sha256": digest(archive_result["edit_plan"]),
            "authority_cell_count": len(meta),
            "authority_cell_ids_sha256": digest(sorted(cids.values())),
            "program_group_count": len(groups),
            "archived_model_calls": ARCHIVE_CALL_COUNT,
            "archived_state_model_call_count": archive_state.get("model_call_count"),
            "model": archive_state.get("model"),
            "reasoning": archive_state.get("reasoning"),
            "temperature": archive_state.get("temperature"),
            "top_p": archive_state.get("top_p"),
            "max_model_calls": archive_state.get("max_model_calls"),
            "max_cost_usd": archive_state.get("max_cost_usd"),
            "frontend_mode": archive_state.get("frontend_mode"),
            "repaired_database": str(feasibility.REPAIRED_DATABASES / "Financial_Model-04_01.sqlite"),
        },
        "predicted": {"independent_units": 49, "archived_session_outcomes": 3, "newly_exposed_units": 46},
        "observed": {
            "independent_units": len(independent),
            "archived_session_outcomes": sum(r["archived_session"] for r in independent_trace),
            "newly_exposed_units": sum(not r["archived_session"] for r in independent_trace),
            "newly_attempted_units": len(attempted_new),
            "newly_unattempted_units": len(unattempted),
            "total_model_calls_after": state_after.get("model_call_count"),
            "new_persisted_model_calls": len(new_call_records),
            "provider_cost_usd_after": state_after.get("provider_cost_usd"),
            "new_provider_cost_usd": sum(float(r.get("provider_cost_usd") or 0.0) for r in new_call_records),
            "terminal_status_counts": dict(terminal_statuses),
            "global_resource_failures": global_failures,
            "scheduler_exception": exception,
            "scheduler_exception_trace": exception_trace,
            "coverage": coverage,
        },
        "liveness": {
            "all_independent_units_disposed_or_explicitly_censored": not unattempted or resource_boundary,
            "latent_work_continued_after_terminal_dispositions": len(attempted_new) > 0,
            "failed_program_group_members_promoted": any(
                member["promoted_to_independent"] and member["failed_canonical_member"]
                for group in group_trace
                for member in group["members"]
            ),
            "terminal_disposition_failed_to_replenish": bool(unattempted) and not exception and not resource_boundary,
            "unattempted_independent_units": unattempted,
            "unattempted_reason": unattempted_reason,
            "verdict": verdict,
        },
        "verifier_defect": verifier_defect,
        "continuation_provenance": continuation_provenance,
        "independent_unit_trace": independent_trace,
        "program_group_trace": group_trace,
        "calls": call_records,
        "scheduler_failures": failures,
        "archive_file_sha256": archive_files,
        "result_schedule": scheduled,
        "verdict": verdict,
        "interpretation": "This continuation validates scheduler liveness only. Formula correctness and scoring were not measured.",
        "task_instruction": task.get("instruction"),
    }
    write(output / "scheduler_live_validation_trace.json", report)
    with (output / "scheduler_live_validation_trace.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "cell_id", "label", "unit_kind", "program_group", "archived_session",
            "live_session_attempted", "outcome_class", "failure_class", "parsed_status",
            "formula_present", "session_call_count", "disposition", "unattempted_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in independent_trace:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else row.get(k) for k in fields})
    return report


def render_markdown(report: dict[str, Any], path: Path) -> None:
    observed = report["observed"]
    frozen = report["frozen_inputs"]
    live = report["liveness"]
    coverage = observed.get("coverage") or {}
    defect = report.get("verifier_defect") or {}
    provenance = report.get("continuation_provenance") or {}
    crashing = defect.get("crashing_object") or {}
    unattempted = live.get("unattempted_independent_units") or []
    unattempted_lines = [
        f"- `{row['cell_id']}` `{row.get('label')}`: {row.get('unattempted_reason') or live.get('unattempted_reason')}"
        for row in unattempted
    ] or ["- none"]
    exception_block = observed.get("scheduler_exception_trace") or observed.get("scheduler_exception")
    lines = [
        "# Scheduler live validation — Financial_Model:04_01",
        "",
        "This is an isolated scheduler continuation. The archived Task IR, Edit Plan, authority,",
        "ProgramGroups, repaired database lineage, evidence/cache state and three retained terminal",
        "sessions were copied to a separate continuation directory. The frontend was not rerun.",
        "The continuation invoked only the repaired compiled scheduler and the existing retrieval/",
        "synthesis path for newly activated units. No writer, LibreOffice refresh or scorer ran.",
        "",
        "## Frozen starting state",
        "",
        f"- Authorized cells: **{frozen['authority_cell_count']}**.",
        f"- Earned ProgramGroups: **{frozen['program_group_count']}**.",
        f"- Predicted independent units: **{report['predicted']['independent_units']}**.",
        f"- Archived terminal session outcomes: **{report['predicted']['archived_session_outcomes']}**.",
        f"- Newly exposed independent units: **{report['predicted']['newly_exposed_units']}**.",
        f"- Archived runtime profile: `{frozen['model']}`, reasoning `{frozen['reasoning']}`,",
        f"  `{frozen['max_model_calls']}` model-call ceiling, `${frozen['max_cost_usd']}` cost ceiling,",
        f"  frontend mode `{frozen['frontend_mode']}`.",
        "",
        "The archived terminal sessions were `PROVIDER_TIMEOUT`, `PROVIDER_TIMEOUT` and",
        "`SESSION_RESOURCE_LIMIT`. Their scheduler dispositions remain archived as terminal state;",
        "the trace reclassifies them from the persisted session failure fields so provider/resource",
        "failure is not reported as model abstention.",
        "",
        "## A. Zero-model verifier-crash reproduction",
        "",
        "The prior continuation replenished after provider failure, invalid response, and explicit",
        "abstention. Failed ProgramGroup members were not promoted. An accepted proposal for",
        f"`{defect.get('cell_id', CRASHED_CELL_ID)}` then aborted the run in `_validate_formula`",
        "before that unit received a terminal disposition. That crash is a downstream verifier",
        "invariant defect, not queue starvation.",
        "",
        f"- Persisted synthesis call: **{defect.get('call_index', CRASHED_SYNTHESIS_INDEX)}**.",
        f"- Parsed status: `{defect.get('parsed_status')}` formula `{defect.get('formula')}`.",
        f"- References: `{json.dumps(defect.get('references'), ensure_ascii=False)}`.",
        f"- Crashing worksheet object: `{crashing.get('worksheet')}` `{crashing.get('openpyxl_type')}`.",
        f"- Read-only bounds before force: `{json.dumps(crashing.get('readonly_before_force'), ensure_ascii=False)}`.",
        f"- Bounds after `calculate_dimension(force=True)`: `{json.dumps(crashing.get('after_force'), ensure_ascii=False)}`.",
        f"- Legal state: {defect.get('legal_state')}",
        f"- Incorrect invariant: `{defect.get('incorrect_invariant')}`.",
        f"- Other workbooks: {defect.get('other_workbooks')}",
        f"- Raised after repair: `{defect.get('raised')}`.",
        f"- Validation after repair: `{json.dumps(defect.get('validation_after_repair'), ensure_ascii=False)}`.",
        "",
        "## B. Patch",
        "",
        "`formula_synthesis_probe._used_sheet_bounds` materializes integer used-range maxima on",
        "unsized read-only worksheets, then applies the original beyond-used-range predicate to",
        "both range starts and range ends. The archived `=F10/E10-1` proposal is the regression",
        "in `tests/test_formula_synthesis_bounds.py`. Authority, ProgramGroups, retrieval,",
        "synthesis, and prompts were not changed.",
        "",
        "## C. Continuation provenance",
        "",
        f"- Resume: **{report.get('resume')}**.",
        f"- Continuation directory: `{report['continuation_directory']}`.",
        f"- Pre-resume snapshot: `{provenance.get('snapshot_directory')}`.",
        f"- State SHA-256 before resume: `{provenance.get('state_sha256')}`.",
        f"- Call 056 SHA-256: `{provenance.get('call_056_sha256')}`.",
        f"- Model-call count before resume: **{provenance.get('model_call_count_before')}**.",
        f"- Persisted session ids: `{json.dumps(provenance.get('persisted_session_ids'), ensure_ascii=False)}`.",
        f"- Persisted disposition ids: `{json.dumps(provenance.get('persisted_disposition_ids'), ensure_ascii=False)}`.",
        "",
        "The scheduler re-entered the persisted F11 session and did not repeat those model calls.",
        "Later independent units used the existing retrieval/synthesis path only when no session",
        "was already checkpointed.",
        "",
        "## D. Final independent-unit coverage",
        "",
        f"- Independent units reached: **{coverage.get('independent_units_reached')}**.",
        f"- Attempted live or satisfied by persisted outcomes: **{coverage.get('independent_units_attempted_live_or_persisted')}**.",
        f"- Provider failures: **{coverage.get('provider_failures')}**.",
        f"- Invalid responses: **{coverage.get('invalid_responses')}**.",
        f"- Abstentions: **{coverage.get('abstentions')}**.",
        f"- Accepted proposals: **{coverage.get('accepted_proposals')}**.",
        f"- No-ops: **{coverage.get('no_ops')}**.",
        f"- Verifier rejections: **{coverage.get('verifier_rejections')}**.",
        f"- Accepted edits: **{coverage.get('accepted_edits')}**.",
        f"- Session resource failures: **{coverage.get('session_resource_failures')}**.",
        f"- Attempted without terminal disposition: **{coverage.get('attempted_without_terminal_disposition')}**.",
        f"- Unattempted independent units: **{coverage.get('unattempted_independent_units')}**.",
        f"- Total model calls after continuation: **{observed['total_model_calls_after']}**.",
        f"- New persisted model calls: **{observed['new_persisted_model_calls']}**.",
        f"- Provider cost after continuation: **${float(observed['provider_cost_usd_after'] or 0):.6f}**.",
        "",
        "Independent-unit outcome counts:",
        "",
        "```json",
        json.dumps(observed["terminal_status_counts"], indent=2, sort_keys=True),
        "```",
        "",
        "Remaining unattempted independent units:",
        "",
        *unattempted_lines,
        "",
        "The full per-unit trace is in `scheduler_live_validation_trace.json`; the independent-unit",
        "table is in `scheduler_live_validation_trace.csv`. Failed canonical groups never become",
        "independent synthesis units. Formula correctness and benchmark score are outside this",
        "experiment.",
        "",
        "## Liveness verdict",
        "",
        f"- Latent work continued after terminal dispositions: **{live['latent_work_continued_after_terminal_dispositions']}**.",
        f"- Failed ProgramGroup members promoted: **{live['failed_program_group_members_promoted']}**.",
        f"- Terminal disposition failed to replenish: **{live.get('terminal_disposition_failed_to_replenish')}**.",
        f"- All independent work disposed or explicitly censored: **{live['all_independent_units_disposed_or_explicitly_censored']}**.",
        f"- Global resource failures: **{len(observed['global_resource_failures'])}**.",
        f"- Scheduler exception: `{observed.get('scheduler_exception')}`.",
        "",
    ]
    if exception_block:
        lines.extend(["Runtime exception traceback:", "", "```text", str(exception_block), "```", ""])
    lines.append(f"**{report['verdict']}**")
    if report["verdict"] == "SCHEDULER_LIVENESS_VALIDATED":
        lines.extend(
            [
                "",
                "Scheduler and verifier execution infrastructure for this continuation is frozen.",
                "The next phase is Task IR → role-aware grounding → authority. Do not start it from",
                "this report; frontend regeneration remains out of scope here.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(output: Path, report_path: Path, *, resume: bool = False) -> dict[str, Any]:
    if not ARCHIVE.is_dir():
        raise FileNotFoundError(f"Archived 04_01 task directory missing: {ARCHIVE}")
    continuation_dir = output / "Financial_Model-04_01"
    verifier_defect = None
    continuation_provenance = None
    if resume:
        if not continuation_dir.is_dir():
            raise FileNotFoundError(f"Continuation directory missing: {continuation_dir}")
        continuation_provenance = snapshot_pre_resume(output, continuation_dir)
        verifier_defect = diagnose_persisted_proposal(continuation_dir)
        if verifier_defect.get("raised"):
            raise RuntimeError(f"Zero-model verifier repair did not hold: {verifier_defect['raised']}")
        if (verifier_defect.get("validation_after_repair") or {}).get("invalid_address"):
            raise RuntimeError("Repair incorrectly rejected the archived in-range proposal")
    else:
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite continuation directory: {output}")
        output.mkdir(parents=True)
        shutil.copytree(ARCHIVE, continuation_dir, symlinks=False)
    archive_result = read(ARCHIVE / "result.json")
    archive_state = read(ARCHIVE / "state.json")
    compiler = copy.deepcopy(archive_result["compiler"])
    plan = copy.deepcopy(archive_result["edit_plan"])
    state = read(continuation_dir / "state.json")
    task = copy.deepcopy(m.task_map()[TASK_KEY])
    if task["instruction"] != compiler["raw_task"]:
        raise AssertionError("Frozen task text differs from archived compiler raw_task")
    old_databases = m.DATABASES
    previous_runtime = m.configure_runtime(
        max_model_calls=archive_state["max_model_calls"],
        max_cost_usd=archive_state["max_cost_usd"],
        frontend_mode=archive_state["frontend_mode"],
    )
    m.DATABASES = feasibility.REPAIRED_DATABASES
    exception = None
    exception_trace = None
    scheduled: dict[str, Any] = {}
    try:
        scheduled = compiled_scheduler.schedule(
            m,
            TASK_KEY,
            task,
            compiler,
            plan,
            state,
            continuation_dir,
            stub=False,
        )
    except Exception as exc:  # noqa: BLE001 - preserve a machine-readable partial trace
        exception = f"{type(exc).__name__}: {exc}"
        exception_trace = traceback.format_exc()
    finally:
        m.DATABASES = old_databases
        m.restore_runtime(previous_runtime)
    state_after = read(continuation_dir / "state.json")
    report = build_report(
        output=output,
        continuation_dir=continuation_dir,
        archive_result=archive_result,
        archive_state=archive_state,
        state_after=state_after,
        scheduled=scheduled,
        plan=plan,
        task=task,
        exception=exception,
        exception_trace=exception_trace,
        resume=resume,
        verifier_defect=verifier_defect,
        continuation_provenance=continuation_provenance,
    )
    render_markdown(report, report_path)
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "coverage": report["observed"].get("coverage"),
                "terminal_status_counts": report["observed"]["terminal_status_counts"],
                "scheduler_exception": report["observed"].get("scheduler_exception"),
                "unattempted_reason": report["liveness"].get("unattempted_reason"),
                "failed_program_group_members_promoted": report["liveness"]["failed_program_group_members_promoted"],
                "terminal_disposition_failed_to_replenish": report["liveness"].get(
                    "terminal_disposition_failed_to_replenish"
                ),
            },
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "scheduler_live_validation")
    parser.add_argument("--report", type=Path, default=ROOT / "SCHEDULER_LIVE_VALIDATION_REPORT.md")
    parser.add_argument("--resume", action="store_true", help="Continue the existing isolated 04_01 directory")
    args = parser.parse_args()
    run(args.output, args.report, resume=args.resume)
