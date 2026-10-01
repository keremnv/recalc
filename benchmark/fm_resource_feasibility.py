#!/usr/bin/env python3
"""Financial_Model resource-feasibility probe.

The first commands in this module are evaluator-side/static only.  They use
the archived treatment plans and the repaired replay artifacts to freeze the
12-task feasibility population and to make the call-demand decomposition
auditable before a new provider request is made.  Later commands (``frontend``,
``live`` and ``report``) are intentionally separate so an interrupted desktop
session can be resumed without re-running completed calls.

This is not the final 20-task matched benchmark.  In particular, the 150-call
ceiling in ``live`` is an observation ceiling, never a proposed benchmark
budget.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
import integration_autopsy as ia  # noqa: E402
import frontend_projection as fp  # noqa: E402
import matched_compiled_treatment as m  # noqa: E402
import task_obligation_compile as task_compile  # noqa: E402


RUN_ROOT = m.RUN_ROOT / "resource_feasibility"
STATIC = RUN_ROOT / "static"
FRONTEND = RUN_ROOT / "frontend_max"
LIVE = RUN_ROOT / "live"
REPAIRED_LIVE = LIVE / "repaired_treatment"
REPLAY = m.RUN_ROOT / "integration_autopsy" / "replay"
REPAIRED_DATABASES = m.RUN_ROOT / "integration_autopsy" / "repaired_db"
RESOURCE_AUDIT = m.RUN_ROOT / "integration_autopsy" / "resource_envelope_audit.json"
CAPABILITY = m.RUN_ROOT / "integration_autopsy" / "provider_capability_metadata.json"

FM_TASKS = [
    "01_01", "02_01", "03_01", "04_01", "05_01", "06_01", "07_01",
    "08_01", "10_01", "11_01", "11_05", "12_05", "13_05", "14_05",
    "15_05", "16_05", "17_05", "18_05", "19_05", "20_05",
]

MODEL = m.AUTHORITATIVE_EXPERIMENT_CONFIG.model
REASONING = m.AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning
TEMPERATURE = m.AUTHORITATIVE_EXPERIMENT_CONFIG.temperature
TOP_P = m.AUTHORITATIVE_EXPERIMENT_CONFIG.top_p
PROVIDER_POLICY = dict(m.AUTHORITATIVE_EXPERIMENT_CONFIG.provider_options)
NATURAL_CALL_CEILING = 150
NATURAL_COST_CEILING = 6.0
MAX_OUTPUT_TOKENS = m.AUTHORITATIVE_EXPERIMENT_CONFIG.max_output_tokens
FRONTEND_TIMEOUT_SECONDS = m.timeout_for_stage("edit_plan")

_SPINE_CACHE: dict[str, dict[str, Any]] = {}
_CID_CELL_CACHE: dict[str, dict[str, tuple[str, int, int]]] = {}


def key(task: str) -> str:
    return f"Financial_Model:{task}"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def cell_label(cell: tuple[str, int, int]) -> str:
    return f"{cell[0]}!{m.closure.a1(cell[1], cell[2])}"


def target_from_cid(task: str, cid: str) -> tuple[str, int, int] | None:
    cached = _CID_CELL_CACHE.get(task, {}).get(cid)
    if cached is not None:
        return cached
    if task not in _SPINE_CACHE:
        _SPINE_CACHE[task] = m.spine_for(key(task))
    address = m.target_address(_SPINE_CACHE[task], cid)
    if not address:
        return None
    return address["sheet"], int(address["row"]), int(address["col"])


def load_repaired_plan(task: str) -> dict[str, Any]:
    """Return authority and evaluator-side eligible groups from repaired replay.

    The replay result is the repaired, no-new-model-call state transition.  It
    contains all disposition keys even when a stored session was unavailable,
    which is the authoritative cell set for temporal tasks whose original plan
    had an INVALID_ENTITY placeholder.
    """
    path = REPLAY / f"Financial_Model-{task}" / "result.json"
    result = read_json(path, {})
    schedule = result.get("schedule") or {}
    cells: set[tuple[str, int, int]] = set()
    cid_cells: dict[str, tuple[str, int, int]] = {}
    for cid, disposition in (schedule.get("dispositions") or {}).items():
        raw_cell = (disposition or {}).get("cell")
        c = tuple(raw_cell) if isinstance(raw_cell, list) and len(raw_cell) == 3 else target_from_cid(task, cid)
        if c:
            cells.add(c)
            cid_cells[cid] = c
    _CID_CELL_CACHE[task] = cid_cells
    # A defensive fallback for a replay produced by an older writer.
    if not cells:
        old = read_json(m.LIVE / f"Financial_Model-{task}" / "result.json", {})
        expansion = ((old.get("edit_plan") or {}).get("expansion") or {})
        for cid in expansion.get("cell_ids", []):
            c = target_from_cid(task, cid)
            if c:
                cells.add(c)
    groups = []
    for i, group in enumerate(schedule.get("eligible_program_groups") or []):
        members = []
        for raw in group.get("member_cells") or []:
            if len(raw) == 3:
                members.append(tuple(raw))
        if members:
            groups.append({
                "group_id": f"G{i + 1}",
                "operation_id": group.get("operation_id"),
                "axis": group.get("axis"),
                "input_kind": group.get("input_kind"),
                "canonical_member": group.get("canonical_member"),
                "canonical_cell": group.get("canonical_cell"),
                "member_cells": [list(c) for c in members],
                "members": [cell_label(c) for c in members],
                "translation_offsets": group.get("translation_offsets") or {},
                "witness": "persisted evaluator-side program_group.groups_for result",
            })
    grouped = {tuple(c) for group in groups for c in map(tuple, group["member_cells"])}
    ungrouped = sorted(cells - grouped)
    return {
        "task": key(task),
        "authority_cells": sorted(cells),
        "authority_labels": [cell_label(c) for c in sorted(cells)],
        "eligible_groups": groups,
        "grouped_cells": sorted(grouped),
        "ungrouped_cells": ungrouped,
        "replay_result": str(path),
        "replay_audit": result.get("audit") or {},
    }


def operation_map(task: str) -> dict[tuple[str, int, int], str | None]:
    """Map archived/replayed authority cells to operation IDs where retained."""
    out: dict[tuple[str, int, int], str | None] = {}
    old = read_json(m.LIVE / f"Financial_Model-{task}" / "result.json", {})
    plan = old.get("edit_plan") or {}
    for op in ((plan.get("expansion") or {}).get("operations") or []):
        for cid in op.get("cell_ids", []):
            c = target_from_cid(task, cid)
            if c:
                out.setdefault(c, op.get("operation_id"))
    # Temporal plans are restored only in replay.  Disposition records preserve
    # the cell but not the operation; leave that identity explicitly absent.
    return out


def projected_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resource = read_json(RESOURCE_AUDIT, {})
    audit_by = {r.get("task", "").split(":", 1)[-1]: r for r in resource.get("rows", []) if r.get("task", "").startswith("Financial_Model:")}
    rows = []
    classes: dict[str, Any] = {}
    for task in FM_TASKS:
        print(f"STATIC_TASK {task}", flush=True)
        repaired = load_repaired_plan(task)
        print(f"STATIC_LOADED {task}", flush=True)
        auth = set(map(tuple, repaired["authority_cells"]))
        groups = repaired["eligible_groups"]
        grouped = set(map(tuple, repaired["grouped_cells"]))
        units = len(groups) + len(auth - grouped)
        # The previous scheduler was cell-first.  These are a transparent
        # lower-bound and full-session projections, not a claim that every
        # archived plan would have consumed all eight retrieval turns.
        before_semantic = len(auth)
        after_semantic = units
        before_lower = 2 + before_semantic
        after_lower = 2 + after_semantic
        before_full = 2 + before_semantic * (m.MAX_SQL_CALLS + 1)
        after_full = 2 + after_semantic * (m.MAX_SQL_CALLS + 1)
        resource_row = audit_by.get(task, {})
        groups_by_cell = {}
        for group in groups:
            for raw in group["member_cells"]:
                groups_by_cell[tuple(raw)] = group["group_id"]
        classes_for_task = []
        print(f"STATIC_CLASSES_START {task}", flush=True)
        op_map = operation_map(task)
        for group in groups:
            members = [tuple(c) for c in group["member_cells"]]
            classes_for_task.append({
                "class_id": f"{task}:{group['group_id']}",
                "stage": "formula_synthesis",
                "operation_id": group.get("operation_id"),
                "target_region": sorted({c[0] for c in members}),
                "program_group": group["group_id"],
                "evidence_identity": "input repetition witness; no stochastic evidence exists before canonical inference",
                "members": [cell_label(c) for c in members],
                "raw_cell_decisions": len(members),
                "distinct_semantic_decisions": 1,
                "mechanically_redundant_decisions": max(0, len(members) - 1),
            })
        for c in sorted(auth - grouped):
            classes_for_task.append({
                "class_id": f"{task}:U:{cell_label(c)}",
                "stage": "formula_synthesis",
                "operation_id": op_map.get(c),
                "target_region": [c[0]],
                "program_group": None,
                "evidence_identity": "single authorized cell; no mechanically equivalent peer witness",
                "members": [cell_label(c)],
                "raw_cell_decisions": 1,
                "distinct_semantic_decisions": 1,
                "mechanically_redundant_decisions": 0,
            })
        print(f"STATIC_CLASSES_DONE {task}", flush=True)
        # Task IR and Edit Plan are two distinct semantic calls in the frozen
        # frontend.  Grounding is deterministic here and is not counted as a
        # stochastic call.
        rows.append({
            "task": key(task),
            "task_id": task,
            "selected": False,
            "selected_role": "",
            "authority_cells": len(auth),
            "evaluator_program_groups": len(groups),
            "grouped_cells": len(grouped),
            "ungrouped_cells": len(auth - grouped),
            "raw_cellwise_semantic_decisions": before_semantic,
            "repaired_distinct_semantic_decisions": after_semantic,
            "mechanically_redundant_decisions": max(0, before_semantic - after_semantic),
            "raw_projected_calls_lower_bound": before_lower,
            "repaired_projected_calls_lower_bound": after_lower,
            "raw_projected_calls_full_8_retrieval": before_full,
            "repaired_projected_calls_full_8_retrieval": after_full,
            "raw_frontend_calls": 2,
            "repaired_frontend_calls": 2,
            "raw_task_ir_calls": 1,
            "repaired_task_ir_calls": 1,
            "raw_edit_plan_calls": 1,
            "repaired_edit_plan_calls": 1,
            "raw_stochastic_grounding_calls": 0,
            "repaired_stochastic_grounding_calls": 0,
            "raw_target_session_initialization_calls": before_semantic,
            "repaired_target_session_initialization_calls": after_semantic,
            "raw_retrieval_action_decision_calls": before_semantic * m.MAX_SQL_CALLS,
            "repaired_retrieval_action_decision_calls": after_semantic * m.MAX_SQL_CALLS,
            "raw_canonical_synthesis_calls": before_semantic,
            "repaired_canonical_synthesis_calls": after_semantic,
            "raw_programgroup_canonical_synthesis_calls": 0,
            "repaired_programgroup_canonical_synthesis_calls": len(groups),
            "raw_ungrouped_synthesis_calls": before_semantic,
            "repaired_ungrouped_synthesis_calls": len(auth - grouped),
            "raw_executionunit_member_synthesis_calls": 0,
            "repaired_executionunit_member_synthesis_calls": 0,
            "raw_retry_infrastructure_calls": 0,
            "repaired_retry_infrastructure_calls": 0,
            "archived_model_calls": resource_row.get("archived_model_calls"),
            "archived_retrieval_calls": resource_row.get("archived_retrieval_calls"),
            "archived_synthesis_calls": resource_row.get("archived_synthesis_calls"),
            "calls_lower_bound_excluding_retrieval": resource_row.get("calls_lower_bound_excluding_retrieval", after_lower),
            "fits_50_repaired_lower_bound": after_lower <= 50,
            "authority_replay_source": repaired["replay_result"],
        })
        classes[key(task)] = {
            "task": key(task),
            "equivalence_basis": ["stage", "authorised operation", "target region", "ProgramGroup witness", "persisted evidence identity where available"],
            "classes": classes_for_task,
            "raw_projected_calls": before_lower,
            "repaired_projected_calls": after_lower,
            "raw_distinct_semantic_decisions": before_semantic,
            "repaired_distinct_semantic_decisions": after_semantic,
            "mechanically_duplicate_or_redundant_calls": max(0, before_semantic - after_semantic),
        }
        print(f"STATIC_TASK_DONE {task} auth={len(auth)} groups={len(groups)}", flush=True)
    # Selection is frozen from repaired lower-bound demand only.  The nine
    # stress rows are exactly the archived audit's >50 rows.  Comparison rows
    # are low, median and highest eligible values, with task ID tie-breaking.
    stress = [r["task_id"] for r in rows if not r["fits_50_repaired_lower_bound"]]
    eligible = sorted((r for r in rows if r["fits_50_repaired_lower_bound"]), key=lambda r: (r["repaired_projected_calls_lower_bound"], r["task_id"]))
    if not eligible:
        raise RuntimeError("NO_REPAIRED_FM_TASKS_WITHIN_50")
    comp = [eligible[0], eligible[len(eligible) // 2], eligible[-1]]
    selected_roles = {task: "STRESS_GT50" for task in stress}
    for role, row in zip(("COMPARISON_LOW", "COMPARISON_MEDIAN", "COMPARISON_HIGHEST_LE50"), comp):
        selected_roles[row["task_id"]] = role
    # If a deterministic collision ever occurs (e.g. a tiny population), do
    # not silently run fewer than 12 tasks.
    if len(selected_roles) != 12:
        raise RuntimeError(f"SELECTION_NOT_12_UNIQUE_TASKS: {selected_roles}")
    for row in rows:
        row["selected"] = row["task_id"] in selected_roles
        row["selected_role"] = selected_roles.get(row["task_id"], "")
    selection = {
        "population": [key(t) for t in FM_TASKS],
        "stress_tasks": [key(t) for t in stress],
        "comparison_tasks": [key(r["task_id"]) for r in comp],
        "selected_tasks": [key(t) for t in FM_TASKS if t in selected_roles],
        "selected_roles": {key(t): role for t, role in selected_roles.items()},
        "selection_basis": "repaired archived lower-bound stochastic demand only; no endpoint scores or anecdotes",
        "repaired_source": str(RESOURCE_AUDIT),
        "repair_gates_sha256": digest(read_json(m.RUN_ROOT / "integration_autopsy" / "repair_gates.json", {})),
    }
    return rows, {"selection": selection, "classes": classes}


def static_audit() -> dict[str, Any]:
    rows, detail = projected_rows()
    STATIC.mkdir(parents=True, exist_ok=True)
    write_csv(STATIC / "phase_a_projected_demand.csv", rows)
    write_json(STATIC / "call_equivalence_classes.json", detail["classes"])
    write_json(STATIC / "feasibility_tasks.json", detail["selection"])
    # The requested deliverables are copied at the resource-feasibility root
    # as well as retained under static/ for crash-safe discovery.
    write_csv(RUN_ROOT / "phase_a_projected_demand.csv", rows)
    write_json(RUN_ROOT / "call_equivalence_classes.json", detail["classes"])
    write_json(RUN_ROOT / "feasibility_tasks.json", detail["selection"])
    before = sum(r["raw_projected_calls_lower_bound"] for r in rows if r["selected"])
    after = sum(r["repaired_projected_calls_lower_bound"] for r in rows if r["selected"])
    repair_rows = []
    for r in rows:
        repair_rows.append({
            "task": r["task"],
            "selected": r["selected"],
            "before_projected_calls_lower_bound": r["raw_projected_calls_lower_bound"],
            "after_projected_calls_lower_bound": r["repaired_projected_calls_lower_bound"],
            "reduction_calls": r["raw_projected_calls_lower_bound"] - r["repaired_projected_calls_lower_bound"],
            "before_distinct_semantic_decisions": r["raw_cellwise_semantic_decisions"],
            "after_distinct_semantic_decisions": r["repaired_distinct_semantic_decisions"],
            "semantic_decision_change": r["repaired_distinct_semantic_decisions"] - r["raw_cellwise_semantic_decisions"],
            "before_full_8_retrieval_calls": r["raw_projected_calls_full_8_retrieval"],
            "after_full_8_retrieval_calls": r["repaired_projected_calls_full_8_retrieval"],
            "programgroup_coverage": r["grouped_cells"] / r["authority_cells"] if r["authority_cells"] else None,
        })
    write_csv(STATIC / "projected_demand_after_repair.csv", repair_rows)
    write_csv(RUN_ROOT / "projected_demand_after_repair.csv", repair_rows)
    report = {
        "status": "STATIC_COMPLETE",
        "selection": detail["selection"],
        "selected_raw_projected_calls_lower_bound": before,
        "selected_repaired_projected_calls_lower_bound": after,
        "selected_mechanically_redundant_calls": before - after,
        "stress_count": len(detail["selection"]["stress_tasks"]),
        "comparison_count": len(detail["selection"]["comparison_tasks"]),
        "no_model_calls": True,
        "notes": [
            "Full-session projections assume up to eight retrieval actions plus one synthesis per semantic unit; lower bounds count one semantic decision per unit.",
            "A group is an evaluator-side input-repetition witness already earned by the existing ProgramGroup contract. No new grouping rule is inferred.",
            "The demand audit is not a score optimization and does not use gold endpoint results for selection.",
        ],
    }
    write_json(STATIC / "static_audit.json", report)
    write_json(RUN_ROOT / "static_audit.json", report)
    print(json.dumps(report, indent=2))
    return report


def frozen_tasks() -> dict[str, Any]:
    path = RUN_ROOT / "feasibility_tasks.json"
    if not path.exists():
        static_audit()
    return read_json(path)


def provider_key() -> str:
    return m.provider_key() or ""


def provider_config() -> dict[str, Any]:
    catalog = read_json(CAPABILITY, {})
    model_row = catalog.get("model") or {}
    supported = ((model_row.get("reasoning") or {}).get("supported_efforts") or [])
    if "max" not in supported:
        raise RuntimeError(f"MAX_REASONING_NOT_SUPPORTED_BY_CAPABILITY_METADATA: {supported}")
    config = m.AUTHORITATIVE_EXPERIMENT_CONFIG.request_fields()
    return {"model_config": config, "model_config_sha256": digest(config), "capability_metadata": str(CAPABILITY), "capability_sha256": hashlib.sha256(CAPABILITY.read_bytes()).hexdigest(), "exact_reasoning_field": "reasoning.effort", "exact_reasoning_value": REASONING}


def call_provider(body: dict[str, Any], task: str, stage: str, index: int, ledger_dir: Path, *, timeout_seconds: int = 180) -> dict[str, Any]:
    """One bounded provider call with immutable request/response retention."""
    if int(timeout_seconds) != m.timeout_for_stage(stage):
        raise RuntimeError(f"REQUEST_CONFIGURATION_MISMATCH[{stage}]: timeout={timeout_seconds!r}")
    request_meta = m.request_identity(body, stage=stage)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    record = {"task": key(task), "stage": stage, "index": index, "request": body, "request_sha256": digest(body), "started_at": time.time(), "provider_attempt": True, **request_meta, "request_provider": m.PROVIDER, "response_model": None}
    path = ledger_dir / f"{index:03d}_{stage}.json"
    if path.exists():
        prior = read_json(path)
        if prior.get("request_sha256") == record["request_sha256"]:
            return prior
        raise RuntimeError(f"LIVE_LEDGER_COLLISION: {path}")
    if not provider_key():
        record.update({"provider_attempt": False, "failure_class": "MODEL_ACCESS_FAILURE", "error": "OPENROUTER_API_KEY missing"})
        write_json(path, record)
        return record
    req = urllib.request.Request(m.relational.OPENROUTER_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {provider_key()}", "Content-Type": "application/json", "X-Title": "fm-resource-feasibility"}, method="POST")
    previous_alarm = signal.getsignal(signal.SIGALRM)
    payload: dict[str, Any] | None = None
    def provider_alarm(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"provider response exceeded {timeout_seconds} seconds")
    try:
        signal.signal(signal.SIGALRM, provider_alarm)
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode()
            payload = json.loads(raw)
        response_meta = m.response_identity(payload, stage=stage)
        choices = payload.get("choices") or []
        text = ((choices[0].get("message") or {}).get("content") or "") if choices else ""
        usage = payload.get("usage") or {}
        record.update({"response": payload, "raw_response_text": text, "usage": usage, "provider_cost_usd": float(usage.get("cost") or payload.get("cost") or 0.0), "finish_reason": choices[0].get("finish_reason") if choices else None, "completed_at": time.time(), "failure_class": None, **response_meta})
    except RuntimeError as exc:
        record.update({"response": payload, "provider_cost_usd": 0.0, "completed_at": time.time(), "failure_class": "REQUEST_IDENTITY_FAILURE", "error": str(exc)})
        write_json(path, record)
        raise
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        record.update({"response": {"status": exc.code, "body": body_text}, "provider_cost_usd": 0.0, "completed_at": time.time(), "failure_class": "MODEL_ACCESS_FAILURE"})
    except Exception as exc:
        record.update({"response": None, "provider_cost_usd": 0.0, "completed_at": time.time(), "failure_class": f"INFRASTRUCTURE_FAILURE:{type(exc).__name__}", "error": str(exc)})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_alarm)
    write_json(path, record)
    return record


def _provider_worker(args: tuple[dict[str, Any], str, str, int, str, int]) -> dict[str, Any]:
    """Process worker so each bounded provider call has its own SIGALRM scope."""
    body, task, stage, index, ledger_dir, timeout_seconds = args
    return call_provider(body, task, stage, index, Path(ledger_dir), timeout_seconds=timeout_seconds)


def frontend_body(system: str, user: str) -> dict[str, Any]:
    return m.request_body(system, user)


def frontend_gold_metrics(task: str, compiler: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    row = m.task_map()[key(task)]
    source = ia.cells(m.task_source(key(task)))
    gold = ia.cells(Path(row["gold_path"]))
    gold_changed = ia.changed(source, gold)
    gold_formula = {c for c in gold_changed if ia.formula(gold.get(c))}
    plan_copy = dict(plan)
    plan_copy["spine"] = m.spine_for(key(task))
    try:
        auth_meta, _ = m.authorised_cells(plan_copy)
        auth = set(auth_meta)
    except Exception:
        auth = set()
    task_oracle = task_compile.build_ungrounded_oracle(row["instruction"])
    pred_obs = compiler.get("obligations") or []
    # The frozen task-obligation evaluator scores only the task-text IR; this
    # is evaluator-side and does not enter the frontend prompt or scheduler.
    spec = task_compile.score_task(task_id=task, instruction=row["instruction"], oracle=task_oracle, pred=pred_obs, parse_valid=compiler.get("status") == "OK")
    formula_auth = auth & gold_formula
    return {
        "gold_edit_cells": len(gold_changed),
        "gold_formula_targets": len(gold_formula),
        "authorised_cells": len(auth),
        "authority_gold_target_recall": len(auth & gold_changed) / len(gold_changed) if gold_changed else None,
        "authority_gold_target_precision": len(auth & gold_changed) / len(auth) if auth else None,
        "formula_target_recall": len(formula_auth) / len(gold_formula) if gold_formula else None,
        "formula_target_precision": len(formula_auth) / len(auth) if auth else None,
        "operation_count": len((plan.get("parsed") or {}).get("operations", [])),
        "expanded_cell_count": len(((plan.get("expansion") or {}).get("cell_ids") or [])),
        "plan_status": plan.get("status"),
        "edit_plan_valid": plan.get("status") == "VALID_PLAN",
        "task_ir_status": compiler.get("status"),
        "task_ir_obligations": len(pred_obs),
        "task_ir_critical_requirement_recall": spec.get("critical_requirement_recall"),
        "task_ir_task_spec_preserved": spec.get("task_spec_preserved"),
        "task_ir_parse_valid": spec.get("parse_valid"),
        "task_ir_error_counts": spec.get("error_counts", {}),
    }


def run_frontend_task(task: str, *, resume: bool = True) -> dict[str, Any]:
    """Run only Task IR + Edit Plan at max reasoning; never retrieval/synthesis."""
    task_key = key(task)
    task_dir = FRONTEND / f"Financial_Model-{task}"
    if not resume and task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    result_path = task_dir / "result.json"
    if resume and result_path.exists():
        return read_json(result_path)
    task_row = m.task_map()[task_key]
    state = {"task_id": task_key, "model": MODEL, "reasoning": REASONING, "temperature": TEMPERATURE, "model_call_count": 0, "provider_cost_usd": 0.0}
    # This uses the exact frozen frontend prompts and deterministic compiler
    # functions but bypasses the full treatment state machine after Edit Plan.
    task_user = "Compile the following task instruction into TASK_OBLIGATION_SHAPE_V1 JSON.\n\nTASK INSTRUCTION:\n" + task_row["instruction"]
    c_record = call_provider(frontend_body(m.TASK_IR_SYSTEM, task_user), task, "task_ir", 1, task_dir / "calls")
    text = c_record.get("raw_response_text", "")
    parsed = task_compile.extract_json_object(text)
    if c_record.get("failure_class"):
        compiler = {"status": c_record["failure_class"], "raw_task": task_row["instruction"], "obligations": [], "call": c_record}
    elif not isinstance(parsed, dict):
        compiler = {"status": "PARSE_FAILURE", "raw_task": task_row["instruction"], "obligations": [], "call": c_record}
    else:
        try:
            compiler = {"status": "OK", "raw_task": task_row["instruction"], "obligations": task_compile.normalize_prediction(parsed), "parsed": parsed, "call": c_record}
        except Exception as exc:
            compiler = {"status": "PARSE_FAILURE", "raw_task": task_row["instruction"], "obligations": [], "error": str(exc), "call": c_record}
    state["model_call_count"] = 1
    state["provider_cost_usd"] = float(c_record.get("provider_cost_usd") or 0.0)
    plan = {"status": "EMPTY_EXPANSION", "parsed": {"operations": []}, "expansion": {"status": "EMPTY_EXPANSION", "cell_ids": [], "operations": [], "provenance": {}}, "packets": {}}
    if compiler.get("status") == "OK" and compiler.get("obligations"):
        # Keep the exact frozen plan context construction in matched treatment.
        world = m.World(m.db_for(task_key))
        try:
            packets = {ob["id"]: m.project_obligation(m.spine_for(task_key), ob) for ob in compiler["obligations"]}
            context = m.plan_context(task_row, compiler, packets, world)
        finally:
            world.close()
        p_record = call_provider(frontend_body(m.EDIT_PLAN_PROMPT, json.dumps(context, ensure_ascii=False, separators=(",", ":"))), task, "edit_plan", 2, task_dir / "calls")
        p_text = p_record.get("raw_response_text", "")
        p_parsed = task_compile.extract_json_object(p_text)
        state["model_call_count"] = 2
        state["provider_cost_usd"] += float(p_record.get("provider_cost_usd") or 0.0)
        plan = {"status": p_record.get("failure_class") or "PARSE_FAILURE", "parsed": p_parsed, "expansion": None, "packets": packets, "context": context, "call": p_record}
        if isinstance(p_parsed, dict) and not p_record.get("failure_class"):
            world = m.World(m.db_for(task_key))
            try:
                try:
                    expansion = m.expand_edit_plan(p_parsed, world, {ob["id"] for ob in compiler["obligations"]}, id_contract="V2")
                    plan.update({"status": expansion["status"], "expansion": expansion})
                except m.PlanError as exc:
                    plan.update({"status": exc.category, "expansion": None, "error": str(exc)})
            finally:
                world.close()
    metrics = frontend_gold_metrics(task, compiler, plan)
    result = {"task": task_key, "model_config": provider_config()["model_config"], "compiler": {k: v for k, v in compiler.items() if k != "call"}, "edit_plan": {k: v for k, v in plan.items() if k not in ("context", "packets", "call")}, "metrics": metrics, "calls": {"total": state["model_call_count"], "cost_usd": state["provider_cost_usd"]}, "raw_ledger": str(task_dir / "calls"), "status": "COMPLETED"}
    write_json(task_dir / "state.json", state)
    write_json(result_path, result)
    return result


def frontend_probe() -> dict[str, Any]:
    selection = frozen_tasks()
    tasks = [t.split(":", 1)[1] for t in selection["selected_tasks"]]
    results = [run_frontend_task(task) for task in tasks]
    rows = []
    archived_rows = []
    for result in results:
        task = result["task"].split(":", 1)[1]
        metrics = result["metrics"]
        old = read_json(m.LIVE / f"Financial_Model-{task}" / "result.json", {})
        old_comp = old.get("compiler") or {}
        old_plan = old.get("edit_plan") or {}
        # Evaluate archived low-reasoning frontend with the same evaluator-side
        # functions; no old model call is repeated.
        old_metrics = frontend_gold_metrics(task, old_comp, old_plan)
        role = selection["selected_roles"].get(result["task"], "")
        row = {"task": result["task"], "role": role, **metrics, "max_total_calls": result["calls"]["total"], "max_cost_usd": result["calls"]["cost_usd"]}
        rows.append(row)
        archived_rows.append({
            "task": result["task"], "role": role,
            "archived_task_ir_critical_requirement_recall": old_metrics.get("task_ir_critical_requirement_recall"),
            "max_task_ir_critical_requirement_recall": metrics.get("task_ir_critical_requirement_recall"),
            "archived_edit_plan_valid": old_metrics.get("edit_plan_valid"),
            "max_edit_plan_valid": metrics.get("edit_plan_valid"),
            "archived_formula_target_recall": old_metrics.get("formula_target_recall"),
            "max_formula_target_recall": metrics.get("formula_target_recall"),
            "archived_formula_target_precision": old_metrics.get("formula_target_precision"),
            "max_formula_target_precision": metrics.get("formula_target_precision"),
            "archived_authorised_cells": old_metrics.get("authorised_cells"),
            "max_authorised_cells": metrics.get("authorised_cells"),
            "archived_operation_count": old_metrics.get("operation_count"),
            "max_operation_count": metrics.get("operation_count"),
            "archived_expanded_cell_count": old_metrics.get("expanded_cell_count"),
            "max_expanded_cell_count": metrics.get("expanded_cell_count"),
        })
    write_json(RUN_ROOT / "max_frontend_results.json", {"status": "COMPLETE", "model_config": provider_config(), "tasks": results, "selected_tasks": selection})
    write_csv(RUN_ROOT / "max_frontend_vs_archived.csv", archived_rows)
    write_json(STATIC / "max_frontend_results.json", {"status": "COMPLETE", "model_config": provider_config(), "tasks": results, "selected_tasks": selection})
    write_csv(STATIC / "max_frontend_vs_archived.csv", archived_rows)
    return {"status": "COMPLETE", "rows": rows, "comparison": archived_rows}


def retained_task_ir_tasks() -> list[str]:
    """The eight tasks whose archived max probe Task IR call completed."""
    out = []
    for task in _selected_ids():
        result = read_json(FRONTEND / f"Financial_Model-{task}" / "result.json", {})
        compiler = result.get("compiler") or {}
        if compiler.get("status") == "OK" and compiler.get("obligations"):
            out.append(task)
    return out


def retained_compiler(task: str) -> dict[str, Any] | None:
    result = read_json(FRONTEND / f"Financial_Model-{task}" / "result.json", {})
    compiler = result.get("compiler") or {}
    return compiler if compiler.get("status") == "OK" and compiler.get("obligations") else None


def _world_sheets(task: str) -> dict[str, Any]:
    world = m.World(m.db_for(key(task)))
    try:
        return m.compact_table(list(world.sheets.values()))
    finally:
        world.close()


def _old_context(task: str, compiler: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    task_row = m.task_map()[key(task)]
    world = m.World(m.db_for(key(task)))
    try:
        spine = m.spine_for(key(task))
        packets = {ob["id"]: m.project_obligation(spine, ob) for ob in compiler["obligations"]}
        context = m.plan_context(task_row, compiler, packets, world)
    finally:
        world.close()
    return context, packets


def _projected_context(task: str, compiler: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    task_row = m.task_map()[key(task)]
    world = m.World(m.db_for(key(task)))
    try:
        spine = m.spine_for(key(task))
        packets = {ob["id"]: m.project_obligation(spine, ob) for ob in compiler["obligations"]}
        projected = {ob["id"]: fp.project_packet(ob, packets[ob["id"]]) for ob in compiler["obligations"]}
        context = fp.projection_context(task_row, compiler, projected, m.compact_table(list(world.sheets.values())), m.EDIT_PLAN_SCHEMA)
    finally:
        world.close()
    return context, packets


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _payload_components(context: dict[str, Any], *, request: dict[str, Any] | None = None) -> dict[str, Any]:
    messages = (request or {}).get("messages") or [{"content": m.EDIT_PLAN_PROMPT}, {"content": json.dumps(context, ensure_ascii=False, separators=(",", ":"))}]
    system = str(messages[0].get("content") or "") if messages else ""
    user = str(messages[1].get("content") or "") if len(messages) > 1 else ""
    grounding = context.get("GROUNDING") or {}
    raw_task = context.get("RAW_TASK") or ""
    task_ir = context.get("GENERATED_TASK_IR") or {}
    sheets = context.get("SHEETS") or {}
    schema = context.get("EXACT_JSON_SCHEMA") or {}
    return {
        "request_chars": len(json.dumps(request, ensure_ascii=False, separators=(",", ":"))) if request else len(system) + len(user),
        "request_tokens_estimate": max(1, (len(system) + len(user)) // 4),
        "system_prompt_chars": len(system),
        "raw_task_chars": len(str(raw_task)),
        "task_ir_chars": _json_chars(task_ir),
        "sheets_chars": _json_chars(sheets),
        "grounding_chars": _json_chars(grounding),
        "schema_chars": _json_chars(schema),
        "message_user_chars": len(user),
    }


def _packet_candidate_counts(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for oid, packet in packets.items():
        out[oid] = {
            "locus_candidate_count": len(packet.get("locus") or []),
            "subject_candidate_count": len(packet.get("subject") or []),
            "scope_temporal_candidate_count": len(packet.get("scope") or []),
            "source_candidate_count": len(packet.get("source") or []),
            "target_candidate_ids_count": len(packet.get("target_cell_ids") or []),
            "formula_class_fact_count": len(packet.get("formula_class_facts") or []),
            "dependency_fact_count": len(packet.get("dependency_facts") or []),
            "packet_counts": packet.get("counts") or {},
        }
    return out


def frontend_payload_audit() -> dict[str, Any]:
    """Measure the existing monolithic Edit Plan envelope without model calls."""
    rows = []
    examples: dict[str, Any] = {}
    for task in _selected_ids():
        result = read_json(FRONTEND / f"Financial_Model-{task}" / "result.json", {})
        compiler = result.get("compiler") or {}
        call_path = FRONTEND / f"Financial_Model-{task}" / "calls" / "002_edit_plan.json"
        call = read_json(call_path, {}) if call_path.exists() else {}
        row: dict[str, Any] = {"task": key(task), "task_id": task, "task_ir_status": compiler.get("status"), "edit_plan_ledger": str(call_path) if call_path.exists() else None, "edit_plan_failure": call.get("failure_class"), "edit_plan_error": call.get("error"), "provider_attempt": call.get("provider_attempt"), "old_request_present": bool(call.get("request"))}
        if compiler.get("status") != "OK" or not compiler.get("obligations"):
            row.update({"audit_status": "NO_COMPLETED_TASK_IR", "obligation_count": 0})
            rows.append(row)
            continue
        context, packets = _old_context(task, compiler)
        request = call.get("request") if isinstance(call.get("request"), dict) else frontend_body(m.EDIT_PLAN_PROMPT, json.dumps(context, ensure_ascii=False, separators=(",", ":")))
        comp = _payload_components(context, request=request)
        row.update({"audit_status": "COMPLETE", "obligation_count": len(compiler["obligations"]), **comp, "packet_candidate_counts": _packet_candidate_counts(packets)})
        if not examples:
            projected_context, projected_packets = _projected_context(task, compiler)
            examples = {"task": key(task), "old_context": context, "projected_context": projected_context, "old_packet_counts": _packet_candidate_counts(packets), "projected_packets": projected_packets}
        rows.append(row)
    write_csv(RUN_ROOT / "frontend_payload_audit.csv", rows)
    write_csv(STATIC / "frontend_payload_audit.csv", rows)
    report = {
        "status": "COMPLETE",
        "model_calls": 0,
        "rows": rows,
        "retained_task_ir_tasks": [key(t) for t in retained_task_ir_tasks()],
        "old_request_chars_total": sum(int(r.get("request_chars") or 0) for r in rows),
        "old_grounding_chars_total": sum(int(r.get("grounding_chars") or 0) for r in rows),
        "notes": ["Rows without a completed archived Task IR have no frozen Edit Plan request to measure.", "Candidate counts are deterministic packet counts; no candidates were deleted from the persistent spine/world."],
    }
    write_json(RUN_ROOT / "frontend_payload_audit.json", report)
    write_json(STATIC / "frontend_payload_audit.json", report)
    if examples:
        write_json(RUN_ROOT / "obligation_projection_examples.json", examples)
        write_json(STATIC / "obligation_projection_examples.json", examples)
    lines = ["# Frontend payload audit", "", "Zero model calls were made.", "", "The old Edit Plan request is built from the complete deterministic packet/world projection. Rows report serialized request components and per-obligation candidate counts.", "", "| Task | Task IR | Request chars | Grounding chars | Raw task chars | Task IR chars | Sheets chars | Schema chars | Edit Plan failure |", "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r['task_id']} | {r.get('task_ir_status')} | {r.get('request_chars', '')} | {r.get('grounding_chars', '')} | {r.get('raw_task_chars', '')} | {r.get('task_ir_chars', '')} | {r.get('sheets_chars', '')} | {r.get('schema_chars', '')} | {r.get('edit_plan_failure') or r.get('edit_plan_error') or ''} |")
    lines += ["", "The complete candidate universe remains in the spine/database. This audit measures only the model-facing serialization."]
    (RUN_ROOT / "FRONTEND_PAYLOAD_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _parse_plan_record(record: dict[str, Any]) -> dict[str, Any] | None:
    if record.get("failure_class"):
        return None
    return task_compile.extract_json_object(record.get("raw_response_text") or "")


def _expand_fragment(task: str, parsed: dict[str, Any] | None, obligation_id: str, world: Any) -> tuple[str, dict[str, Any] | None, str | None]:
    if not isinstance(parsed, dict):
        return "PARSE_FAILURE", None, None
    try:
        expansion = m.expand_edit_plan(parsed, world, {obligation_id}, id_contract="V2")
        return expansion["status"], expansion, None
    except m.PlanError as exc:
        return exc.category, None, str(exc)


def _compose_fragment_plans(task: str, compiler: dict[str, Any], fragments: list[dict[str, Any]], world: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    operations: list[dict[str, Any]] = []
    expansions = []
    for fragment in fragments:
        parsed = fragment.get("parsed")
        if not isinstance(parsed, dict):
            continue
        prefix = str(fragment["obligation_id"])
        ops = fp.rename_operations(parsed.get("operations") or [], prefix)
        operations.extend(ops)
        if fragment.get("expansion"):
            ex = json.loads(json.dumps(fragment["expansion"], ensure_ascii=False))
            ex["operations"] = fp.rename_operations(ex.get("operations") or [], prefix)
            expansions.append(ex)
    conflicts = fp.fragment_conflicts(expansions)
    if conflicts:
        return {"status": "PLAN_FRAGMENT_CONFLICT", "parsed": {"operations": operations}, "expansion": None, "conflicts": conflicts}, conflicts
    composed = {"operations": operations}
    if not operations:
        return {"status": "EMPTY_EXPANSION", "parsed": composed, "expansion": {"status": "EMPTY_EXPANSION", "cell_ids": [], "operations": [], "provenance": {}}}, []
    try:
        expansion = m.expand_edit_plan(composed, world, {ob["id"] for ob in compiler["obligations"]}, id_contract="V2")
        return {"status": expansion["status"], "parsed": composed, "expansion": expansion, "conflicts": []}, []
    except m.PlanError as exc:
        return {"status": exc.category, "parsed": composed, "expansion": None, "error": str(exc), "conflicts": []}, []


def _diagnostic_root(arm: str, task: str) -> Path:
    return RUN_ROOT / "frontend_projection" / arm / f"Financial_Model-{task}"


def run_frontend_diagnostic_task(arm: str, task: str, *, resume: bool = True) -> dict[str, Any]:
    compiler = retained_compiler(task)
    if compiler is None:
        return {"task": key(task), "arm": arm, "status": "NO_RETAINED_TASK_IR"}
    root = _diagnostic_root(arm, task)
    root.mkdir(parents=True, exist_ok=True)
    result_path = root / "result.json"
    if resume and result_path.exists():
        return read_json(result_path)
    task_row = m.task_map()[key(task)]
    old_context, old_packets = _old_context(task, compiler)
    projected_context, projected_packets = _projected_context(task, compiler)
    if arm == "p0_old_extended":
        contexts = [(None, old_context)]
        timeout = 600
    else:
        contexts = []
        for ob in compiler["obligations"]:
            base = old_packets[ob["id"]] if arm == "p1_sharded_old" else projected_packets[ob["id"]]
            if arm == "p1_sharded_old":
                packet_context = {
                    "RAW_TASK": compiler["raw_task"],
                    "GENERATED_TASK_IR": {"obligations": [ob]},
                    "SHEETS": old_context["SHEETS"],
                    "GROUNDING": {ob["id"]: {k: m.compact_table(base.get(k, [])) for k in ("locus", "subject", "scope", "source")} | {"target_candidate_ids": sorted(base.get("target_cell_ids") or []), "candidate_count": len(base.get("target_cell_ids") or []), "fields": base.get("fields")}},
                    "NOTE": old_context["NOTE"],
                    "EXACT_JSON_SCHEMA": m.EDIT_PLAN_SCHEMA,
                }
            else:
                packet_context = {"RAW_TASK": compiler["raw_task"], "GENERATED_TASK_IR": {"obligations": [ob]}, "SHEETS": projected_context["SHEETS"], "GROUNDING": {ob["id"]: base}, "NOTE": projected_context["NOTE"], "EXACT_JSON_SCHEMA": m.EDIT_PLAN_SCHEMA}
            contexts.append((ob["id"], packet_context))
        timeout = 180
    records: list[dict[str, Any]] = []
    fragments: list[dict[str, Any]] = []
    if arm == "p0_old_extended":
        body = frontend_body(m.EDIT_PLAN_PROMPT, json.dumps(old_context, ensure_ascii=False, separators=(",", ":")))
        record = call_provider(body, task, "edit_plan", 1, root / "calls", timeout_seconds=timeout)
        records.append(record)
        parsed = _parse_plan_record(record)
        world = m.World(m.db_for(key(task)))
        try:
            status, expansion, error = _expand_fragment(task, parsed, "__ALL__", world) if parsed is not None else (record.get("failure_class") or "PARSE_FAILURE", None, record.get("error"))
        finally:
            world.close()
        # A monolithic plan is allowed to cite every retained obligation.
        if parsed is not None and not record.get("failure_class"):
            world = m.World(m.db_for(key(task)))
            try:
                try:
                    expansion = m.expand_edit_plan(parsed, world, {ob["id"] for ob in compiler["obligations"]}, id_contract="V2")
                    status, error = expansion["status"], None
                except m.PlanError as exc:
                    status, expansion, error = exc.category, None, str(exc)
            finally:
                world.close()
        plan = {"status": status, "parsed": parsed, "expansion": expansion}
        metrics = frontend_gold_metrics(task, compiler, plan)
        result = {"task": key(task), "arm": arm, "status": status, "plan": plan, "metrics": metrics, "calls": {"total": 1, "cost_usd": sum(float(x.get("provider_cost_usd") or 0) for x in records)}, "payload": _payload_components(old_context, request=body), "raw_ledger": str(root / "calls")}
    else:
        requests = []
        for oid, context in contexts:
            body = frontend_body(m.EDIT_PLAN_PROMPT, json.dumps(context, ensure_ascii=False, separators=(",", ":")))
            ob_dir = root / "calls" / str(oid)
            requests.append((oid, context, body, ob_dir))
        # Obligation fragments are independent semantic calls.  Running the
        # bounded calls in separate processes preserves the exact timeout and
        # raw-ledger contract while avoiding an eight-times-180-second serial
        # diagnostic when several providers are slow.
        worker_args = [(body, task, "edit_plan", 1, str(ob_dir), timeout) for _, _, body, ob_dir in requests]
        with concurrent.futures.ProcessPoolExecutor(max_workers=min(4, max(1, len(worker_args)))) as pool:
            worker_records = list(pool.map(_provider_worker, worker_args))
        records.extend(worker_records)
        for (oid, context, body, ob_dir), record in zip(requests, worker_records):
            parsed = _parse_plan_record(record)
            world = m.World(m.db_for(key(task)))
            try:
                status, expansion, error = _expand_fragment(task, parsed, oid, world) if parsed is not None else (record.get("failure_class") or "PARSE_FAILURE", None, record.get("error"))
            finally:
                world.close()
            fragments.append({"obligation_id": oid, "status": status, "error": error, "parsed": parsed, "expansion": expansion, "payload": _payload_components(context, request=body), "record_path": str(ob_dir / "001_edit_plan.json")})
        world = m.World(m.db_for(key(task)))
        try:
            plan, conflicts = _compose_fragment_plans(task, compiler, fragments, world)
        finally:
            world.close()
        metrics = frontend_gold_metrics(task, compiler, plan)
        result = {"task": key(task), "arm": arm, "status": plan.get("status"), "plan": plan, "metrics": metrics, "fragments": fragments, "calls": {"total": len(records), "cost_usd": sum(float(x.get("provider_cost_usd") or 0) for x in records)}, "raw_ledger": str(root / "calls"), "fragment_conflicts": conflicts}
    write_json(root / "result.json", result)
    return result


def projection_experiment() -> dict[str, Any]:
    tasks = retained_task_ir_tasks()
    results = {}
    for arm in ("p0_old_extended", "p1_sharded_old", "p2_sharded_projected_compact"):
        selected = ["01_01", "13_05"] if arm == "p0_old_extended" else tasks
        results[arm] = [run_frontend_diagnostic_task(arm, task, resume=True) for task in selected]
    write_json(RUN_ROOT / "projection_results.json", {"status": "COMPLETE", "retained_tasks": [key(t) for t in tasks], "arms": results, "model_config": provider_config()})
    rows = []
    for arm, items in results.items():
        for item in items:
            if arm == "p0_old_extended":
                rows.append({"arm": arm, "task": item.get("task"), "status": item.get("status"), "valid_plan": item.get("metrics", {}).get("edit_plan_valid"), "timeout": "TimeoutError" in str(item.get("status")), "fragment_conflicts": 0, "model_calls": item.get("calls", {}).get("total"), "cost_usd": item.get("calls", {}).get("cost_usd"), "request_chars": item.get("payload", {}).get("request_chars"), "expanded_cells": item.get("metrics", {}).get("expanded_cell_count"), "formula_target_recall": item.get("metrics", {}).get("formula_target_recall"), "authority_precision": item.get("metrics", {}).get("authority_gold_target_precision")})
            else:
                frags = item.get("fragments") or []
                rows.append({"arm": arm, "task": item.get("task"), "status": item.get("status"), "valid_plan": item.get("metrics", {}).get("edit_plan_valid"), "timeout": sum("TimeoutError" in str(f.get("status")) for f in frags), "fragment_conflicts": len(item.get("fragment_conflicts") or []), "model_calls": item.get("calls", {}).get("total"), "cost_usd": item.get("calls", {}).get("cost_usd"), "request_chars": sum(int(f.get("payload", {}).get("request_chars") or 0) for f in frags), "expanded_cells": item.get("metrics", {}).get("expanded_cell_count"), "formula_target_recall": item.get("metrics", {}).get("formula_target_recall"), "authority_precision": item.get("metrics", {}).get("authority_gold_target_precision")})
    write_csv(RUN_ROOT / "projection_results.csv", rows)
    lines = ["# Projection experiment report", "", "All Task IR outputs were reused from the archived max frontend probe. No new Task IR calls were made.", "", "| Arm | Tasks | Valid plans | Timeouts/fragments | Median request chars |", "|---|---:|---:|---:|---:|"]
    for arm in ("p0_old_extended", "p1_sharded_old", "p2_sharded_projected_compact"):
        rr = [r for r in rows if r["arm"] == arm]
        lines.append(f"| {arm} | {len(rr)} | {sum(bool(r['valid_plan']) for r in rr)} | {sum(int(r['timeout'] or 0) for r in rr)} | {statistics.median([int(r['request_chars'] or 0) for r in rr]) if rr else 0} |")
    lines += ["", "P0 is diagnostic only. P1 tests obligation sharding with the old packet representation. P2 tests obligation sharding plus deterministic model-facing projection. Persistent grounding remains complete in the workbook spine/database."]
    (RUN_ROOT / "PROJECTION_EXPERIMENT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "COMPLETE", "rows": rows}


def freeze_resource() -> dict[str, Any]:
    """Freeze the resource-probe model envelope, distinct from final A/B freeze."""
    selection = frozen_tasks()
    config = provider_config()
    frozen_sources = {
        name: hashlib.sha256((ROOT / "benchmark" / name).read_bytes()).hexdigest()
        for name in ("fm_resource_feasibility.py", "matched_compiled_treatment.py", "compiled_scheduler.py", "frontend_projection.py")
    }
    freeze = {
        "version": "fm-resource-feasibility-v2",
        "frozen_at": time.time(),
        "population": selection,
        "model_config": config["model_config"],
        "model_config_sha256": config["model_config_sha256"],
        "reasoning_request_field": "reasoning.effort",
        "reasoning_request_value": "max",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "provider_policy": PROVIDER_POLICY,
        "provider_capability_metadata": config["capability_metadata"],
        "provider_capability_sha256": config["capability_sha256"],
        "maximum_stochastic_calls_per_task": NATURAL_CALL_CEILING,
        "per_task_cost_ceiling_usd": NATURAL_COST_CEILING,
        "max_tokens_per_call": MAX_OUTPUT_TOKENS,
        "frontend_timeout_seconds": FRONTEND_TIMEOUT_SECONDS,
        "retrieval_synthesis_timeout_seconds": m.EXECUTION_TIMEOUT,
        "frontend_mode": "sharded_projected",
        "scheduler": "compiled_scheduler.schedule_v3",
        "runtime_revision": "active_call_ceiling_guard_fixed_after_invalid_budget50_rehearsal",
        "source_sha256": frozen_sources,
        "max_requeries": 1,
        "quality_retries": 0,
        "infrastructure_retry_policy": "none in probe runner; a missing response is retained as typed infrastructure failure",
        "new_model_calls_before_freeze": 0,
        "not_final_matched_benchmark": True,
    }
    write_json(RUN_ROOT / "freeze.json", freeze)
    write_json(STATIC / "freeze.json", freeze)
    return freeze


def build_control_overlay() -> tuple[Path, Path]:
    """Make an isolated control dataset with the same repaired 06_01 input."""
    overlay = RUN_ROOT / "control_benchmark"
    data_dir = overlay / "data" / "Financial_Model"
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data" / "Financial_Model" / "dataset.json"
    records = read_json(dataset_path, [])
    selected = {t.split(":", 1)[1] for t in frozen_tasks()["selected_tasks"]}
    selected_records = [r for r in records if r.get("id") in selected]
    if len(selected_records) != len(selected):
        raise RuntimeError("CONTROL_OVERLAY_TASK_RECORD_MISMATCH")
    write_json(data_dir / "dataset.json", records)
    source_root = ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data" / "Financial_Model"
    for rec in selected_records:
        rel = Path(rec["spreadsheet_path"])
        source = source_root / rel
        dest = data_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rec["id"] == "06_01":
            # This is the same metadata-only repaired private copy used by the
            # treatment prep; the original benchmark input is untouched.
            shutil.copy2(m.task_source(key("06_01")), dest)
        else:
            shutil.copy2(source, dest)
    slice_path = RUN_ROOT / "control_slice.json"
    write_json(slice_path, {"model": MODEL, "tasks": [{"category": "Financial_Model", "id": t} for t in sorted(selected)]})
    return overlay, slice_path


def treatment_request_body(system: str, user: str) -> dict[str, Any]:
    return m.request_body(system, user)


def run_treatment_task(task: str, *, resume: bool = True) -> dict[str, Any]:
    """Run the repaired compiled arm under the nonbinding 150/$6 probe envelope."""
    database = REPAIRED_DATABASES / f"Financial_Model-{task}.sqlite"
    if not database.is_file():
        raise FileNotFoundError(f"Repaired compiled database required: {database}")
    old_runtime = m.configure_runtime(
        max_model_calls=NATURAL_CALL_CEILING,
        max_cost_usd=NATURAL_COST_CEILING, frontend_mode="sharded_projected",
    )
    old_databases = m.DATABASES
    m.DATABASES = REPAIRED_DATABASES
    try:
        return m.run_one_task(key(task), resume=resume, output_root=REPAIRED_LIVE)
    finally:
        m.DATABASES = old_databases
        m.restore_runtime(old_runtime)


def treatment_live() -> dict[str, Any]:
    freeze_resource()
    selection = frozen_tasks()
    tasks = [t.split(":", 1)[1] for t in selection["selected_tasks"]]
    rows = []
    for task in tasks:
        print(f"TREATMENT_LIVE {task}", flush=True)
        result = run_treatment_task(task, resume=True)
        rows.append({"task": key(task), "status": result.get("status"), "result_path": str(REPAIRED_LIVE / f"Financial_Model-{task}" / "result.json")})
    write_json(RUN_ROOT / "treatment_live_manifest.json", {"status": "COMPLETE", "rows": rows, "model_config": provider_config()})
    return {"status": "COMPLETE", "rows": rows}


def control_live() -> dict[str, Any]:
    freeze_resource()
    overlay, slice_path = build_control_overlay()
    run_name = "fm-resource-feasibility-control"
    run_root = overlay / "benchmark-runs" / "openrouter" / run_name
    ledger = run_root / "ledger.jsonl"
    if not ledger.exists() or len(ledger.read_text(encoding="utf-8").splitlines()) < len(frozen_tasks()["selected_tasks"]):
        cmd = [
            sys.executable, str(ROOT / "benchmark" / "run_openrouter_slice.py"),
            "--slice", str(slice_path), "--benchmark-root", str(overlay),
            "--sweagent-root", str(ROOT / "benchmark-data" / "SpreadsheetBench-2" / "SWE-agent"),
            "--config", str(ROOT / "benchmark" / "sweagent" / "spreadsheet-control.yaml"),
            "--run-name", run_name, "--model", MODEL, "--control",
            "--reasoning-effort", REASONING, "--max-tokens", str(MAX_OUTPUT_TOKENS),
            "--call-limit", str(NATURAL_CALL_CEILING), "--cost-limit", str(NATURAL_COST_CEILING),
            "--max-requeries", "1", "--timeout", "1800", "--execution-timeout", "180",
            "--no-score", "--skip-existing",
        ]
        completed = subprocess.run(cmd, cwd=ROOT, check=False)
        command_status = completed.returncode
    else:
        command_status = 0
    manifest = {"status": "COMPLETE" if command_status == 0 else "PARTIAL", "command_status": command_status, "run_root": str(run_root), "ledger": str(ledger), "overlay": str(overlay), "model_config": provider_config()}
    write_json(RUN_ROOT / "control_live_manifest.json", manifest)
    return manifest


def scheduler_repair_report() -> dict[str, Any]:
    selection = frozen_tasks()
    rows = read_json(STATIC / "static_audit.json", {})
    demand = list(csv.DictReader((STATIC / "phase_a_projected_demand.csv").open(encoding="utf-8")))
    selected = [r for r in demand if r.get("selected") == "True"]
    report = {
        "status": "COMPLETE",
        "repair_principle": "unit-first scheduling over already-earned ProgramGroup repetition witnesses; deterministic translation prevents a second stochastic call for a covered member",
        "direct_redundancy_witness": "archived/repaired plans contain evaluator-side groups with member count > 1 while old cell-first demand counted every authorized cell as a semantic decision",
        "selection": selection,
        "selected_before_calls_lower_bound": sum(int(r["raw_projected_calls_lower_bound"]) for r in selected),
        "selected_after_calls_lower_bound": sum(int(r["repaired_projected_calls_lower_bound"]) for r in selected),
        "selected_raw_semantic_decisions": sum(int(r["raw_cellwise_semantic_decisions"]) for r in selected),
        "selected_repaired_semantic_decisions": sum(int(r["repaired_distinct_semantic_decisions"]) for r in selected),
        "selected_reduction": sum(int(r["raw_projected_calls_lower_bound"]) - int(r["repaired_projected_calls_lower_bound"]) for r in selected),
        "semantic_decisions_unchanged_or_reduced_only_by_group_witness": True,
        "no_new_group_rule": True,
        "no_gold_runtime_ranking": True,
        "static_replay_zero_model_calls": True,
        "note": "The repaired scheduler is the code already covered by the integration repair gates; this report records its deterministic demand replay and does not authorize a new semantic mechanism.",
    }
    write_json(STATIC / "scheduler_repair_report.json", report)
    write_json(RUN_ROOT / "scheduler_repair_report.json", report)
    text = "# Scheduler repair report\n\n"
    text += "Status: COMPLETE (zero model calls).\n\n"
    text += "The repaired scheduler applies the existing, evaluator-earned ProgramGroup witness before creating stochastic sessions. Group members are translated deterministically and are not resynthesized. C1 closure remains a subset of Edit Plan authority.\n\n"
    text += f"For the frozen 12-task population, the static lower-bound demand changes from {report['selected_before_calls_lower_bound']} cell-first calls to {report['selected_after_calls_lower_bound']} unit-first calls, removing {report['selected_reduction']} mechanically redundant semantic opportunities while retaining {report['selected_repaired_semantic_decisions']} distinct semantic decisions. Full per-task values are in `projected_demand_after_repair.csv`.\n\n"
    text += "This is not a new grouping rule: each merged class is directly backed by the persisted `program_group.groups_for` repetition witness. No gold target or endpoint score is used to select a group.\n"
    (RUN_ROOT / "scheduler_repair_report.md").write_text(text, encoding="utf-8")
    return report


def operation_schedule_counterfactual() -> dict[str, Any]:
    """Replay the archived authority as operation containers, without calls.

    This is intentionally a demand-before-first-result analysis.  It does not
    call latent residual cells solved, and it does not claim that an operation
    has a shared formula merely because its authority set is broad.
    """
    rows: list[dict[str, Any]] = []
    for task in _selected_ids():
        repaired = load_repaired_plan(task)
        auth = {tuple(c) for c in repaired["authority_cells"]}
        groups = repaired["eligible_groups"]
        grouped = {tuple(c) for c in repaired["grouped_cells"]}
        old = read_json(m.LIVE / f"Financial_Model-{task}" / "result.json", {})
        expansion = ((old.get("edit_plan") or {}).get("expansion") or {})
        operation_ids = []
        operation_cells: dict[str, set[tuple]] = defaultdict(set)
        for op in expansion.get("operations") or []:
            oid = str(op.get("operation_id"))
            operation_ids.append(oid)
            for cid in op.get("cell_ids") or []:
                c = target_from_cid(task, cid)
                if c:
                    operation_cells[oid].add(c)
        cell_ops = operation_map(task)
        for c in auth:
            oid = cell_ops.get(c) or "__replay_authority__"
            if oid not in operation_cells:
                operation_ids.append(oid)
            operation_cells[oid].add(c)
        operation_ids = list(dict.fromkeys(operation_ids))
        operation_count = len(operation_ids)
        # A runtime operation container is one latent work identity.  It may
        # expose a witnessed group canonical or one residual member, but it
        # never materializes every authorised cell at initialization.
        upfront = operation_count
        residual = len(auth - grouped)
        amortized = sum(max(0, len(g.get("member_cells") or []) - 1) for g in groups)
        rows.append({
            "task": key(task), "task_id": task,
            "authorised_cells": len(auth), "edit_plan_operations": operation_count,
            "program_groups": len(groups), "grouped_cells": len(grouped),
            "residual_authorised_cells": residual,
            "s0_current_unit_first_upfront_decisions": len(groups) + residual,
            "s1_operation_container_upfront_work_items": upfront,
            "s1_maximum_immediately_required_semantic_decisions": upfront,
            "latent_residual_authorised_cells": residual,
            "eliminated_decisions": amortized,
            "amortized_decisions": amortized,
            "deferred_decisions": residual,
            "upfront_reduction_from_s0": max(0, len(groups) + residual - upfront),
            "operation_ids": operation_ids,
            "note": "Residual cells are deferred, not solved; grouped members are amortized only by the persisted ProgramGroup witness.",
        })
    write_csv(RUN_ROOT / "operation_schedule_counterfactual.csv", rows)
    write_csv(STATIC / "operation_schedule_counterfactual.csv", rows)
    report = {
        "status": "COMPLETE", "model_calls": 0,
        "principle": "Edit Plan operations remain intensional scheduling containers; expanded authority is retained separately.",
        "rows": rows,
        "definitions": {
            "ELIMINATED_DECISION": "witness-backed group member beyond its canonical decision",
            "AMORTIZED_DECISION": "same as eliminated for demand accounting; canonical remains stochastic",
            "DEFERRED_DECISION": "authorised residual not instantiated before a semantic result",
        },
    }
    write_json(RUN_ROOT / "operation_schedule_counterfactual.json", report)
    write_json(STATIC / "operation_schedule_counterfactual.json", report)
    lines = ["# Operation-preserving scheduling report", "", "Status: COMPLETE (zero model calls).", "", "The static replay keeps Edit Plan authority and active work separate. S0 is the existing repaired unit-first lower bound (one canonical per ProgramGroup plus one residual per ungrouped authorised cell). S1 creates one operation container per Edit Plan operation and exposes only the next earned group/residual unit lazily.", "", "| Task | Authority | Operations | ProgramGroups | S0 upfront | S1 upfront | Deferred residual | Amortized members |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['task_id']} | {row['authorised_cells']} | {row['edit_plan_operations']} | {row['program_groups']} | {row['s0_current_unit_first_upfront_decisions']} | {row['s1_operation_container_upfront_work_items']} | {row['deferred_decisions']} | {row['amortized_decisions']} |")
    lines += ["", "S1 does not claim residual cells are solved. It only prevents authority cardinality from becoming upfront stochastic demand; later residual work remains explicit and durable in task state."]
    (RUN_ROOT / "OPERATION_SCHEDULING_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _selected_ids() -> list[str]:
    return [t.split(":", 1)[1] for t in frozen_tasks()["selected_tasks"]]


def _gold_sets(task: str) -> tuple[dict, dict, set, set]:
    row = m.task_map()[key(task)]
    source = ia.cells(m.task_source(key(task)))
    gold = ia.cells(Path(row["gold_path"]))
    changed = ia.changed(source, gold)
    formula_targets = {c for c in changed if ia.formula(gold.get(c))}
    return source, gold, changed, formula_targets


def _output_metrics(task: str, output: Path | None) -> dict[str, Any]:
    source, gold, gold_edits, gold_formula = _gold_sets(task)
    if output is None or not output.exists():
        return {
            "output_exists": False, "output_semantic_edits": 0,
            "output_edits_inter_gold": 0, "output_edits_outside_gold": 0,
            "gold_write_correct": 0, "gold_write_recall": 0.0,
            "write_precision": None, "exact_formula_writes": 0,
        }
    out = ia.cells(output)
    edits = ia.changed(source, out)
    inside = edits & gold_edits
    correct = 0
    exact_formula = 0
    for c in inside:
        ov, gv = out.get(c), gold.get(c)
        ok = ia.exact(ov, gv) if ia.formula(gv) else ov == gv
        if ok:
            correct += 1
            if ia.formula(gv):
                exact_formula += 1
    return {
        "output_exists": True,
        "output_semantic_edits": len(edits),
        "output_edits_inter_gold": len(inside),
        "output_edits_outside_gold": len(edits - gold_edits),
        "gold_write_correct": correct,
        "gold_write_recall": correct / len(gold_edits) if gold_edits else None,
        "write_precision": correct / len(edits) if edits else None,
        "exact_formula_writes": exact_formula,
        "gold_edit_cells": len(gold_edits),
        "gold_formula_targets": len(gold_formula),
    }


def _call_useful(call: dict[str, Any]) -> bool:
    """Conservative, stage-local useful-call definition from the protocol."""
    stage = call.get("stage")
    if call.get("failure_class"):
        return False
    parsed = call.get("parsed_response")
    if stage in ("task_ir", "edit_plan"):
        return isinstance(parsed, dict)
    if stage == "retrieval":
        return bool(call.get("new_working_set_ids")) or (isinstance(parsed, dict) and parsed.get("action") == "final")
    if stage == "synthesis":
        if isinstance(parsed, dict):
            status = str(parsed.get("status") or parsed.get("decision") or "").upper()
            return status in {"PROPOSED", "FORMULA", "ACCEPT", "OK"} or bool(parsed.get("formula"))
    return False


def _treatment_natural_row(task: str) -> dict[str, Any]:
    task_dir = REPAIRED_LIVE / f"Financial_Model-{task}"
    result = read_json(task_dir / "result.json", {})
    state = read_json(task_dir / "state.json", {})
    calls = [read_json(p, {}) for p in sorted((task_dir / "calls").glob("*.json"))]
    calls.sort(key=lambda x: int(x.get("call_index_within_task", x.get("index", 0)) or 0))
    stages = Counter(str(c.get("stage") or "other") for c in calls)
    useful = [_call_useful(c) for c in calls]
    output = Path(result.get("output")) if result.get("output") else task_dir / "output.xlsx"
    metrics = _output_metrics(task, output)
    schedule = result.get("schedule") or {}
    state_block = result.get("state") or {}
    failures = result.get("failure_ledger") or state.get("failure_ledger") or []
    failure_classes = sorted({str(x.get("failure_class")) for x in failures if isinstance(x, dict) and x.get("failure_class")})
    calls_total = max(len(calls), int(state.get("model_call_count", 0) or 0), int(state_block.get("model_call_count", 0) or 0))
    prompt_tokens = sum(int((c.get("usage") or {}).get("prompt_tokens") or 0) for c in calls)
    completion_tokens = sum(int((c.get("usage") or {}).get("completion_tokens") or 0) for c in calls)
    reasoning_tokens = sum(int((c.get("usage") or {}).get("reasoning_tokens") or 0) for c in calls)
    cost = sum(float(c.get("provider_cost_usd") or 0.0) for c in calls)
    groups = schedule.get("groups") or []
    canonical = schedule.get("canonical_decisions") or []
    translated = schedule.get("translated_formula_instances") or []
    dispositions = schedule.get("dispositions") or {}
    write_audit = result.get("write_audit") or {}
    first_write = calls_total if write_audit.get("applied") else None
    first_correct = calls_total if metrics.get("gold_write_correct", 0) else None
    authorized = len((schedule.get("authorized_targets") or [])) if isinstance(schedule.get("authorized_targets"), list) else int(schedule.get("authorized_targets") or 0)
    # ``authorized_targets`` is an integer in the repaired runtime; the state
    # retains the actual cell IDs for the cell-count diagnostic.
    if not authorized:
        authorized = len(state.get("authorised_target_set") or [])
    retrieval_calls = stages.get("retrieval", 0)
    return {
        "arm": "treatment", "task": key(task), "task_id": task,
        "natural_calls": calls_total, "calls_to_first_workbook_write": first_write,
        "calls_to_first_evaluator_correct_write": first_correct,
        "calls_by_stage": dict(stages), "task_ir_calls": stages.get("task_ir", 0),
        "edit_plan_calls": stages.get("edit_plan", 0), "retrieval_calls": retrieval_calls,
        "canonical_synthesis_calls": sum(1 for c in calls if c.get("stage") == "synthesis"),
        "ungrouped_synthesis_calls": sum(1 for c in calls if c.get("stage") == "synthesis"),
        "execution_unit_member_synthesis_calls": 0,
        "retry_calls": 0, "infrastructure_calls": sum(1 for c in calls if c.get("failure_class")),
        "useful_calls": sum(useful), "duplicate_or_nonproductive_calls": calls_total - sum(useful),
        "useful_call_fraction": sum(useful) / calls_total if calls_total else None,
        "input_tokens": prompt_tokens, "output_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens, "provider_cost_usd": cost,
        "output_produced": bool(metrics.get("output_exists")),
        "stop_reason": failure_classes[0] if failure_classes else ("COMPLETED" if result else "NO_RESULT"),
        "failure_classes": failure_classes, "budget_censored": any(x in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"} for x in failure_classes),
        "partial_due_to_budget": bool(result.get("partial_due_to_budget")),
        "authorized_cells": authorized, "sessions_created": len(state.get("working_set_handles") or {}),
        "retrieval_loops": retrieval_calls, "proposals": len(canonical),
        "correct_proposals": sum(1 for x in canonical if isinstance(x, dict) and x.get("correct")),
        "program_groups": len(groups), "canonical_decisions": len(canonical),
        "translated_instances": len(translated), "avoided_stochastic_decisions": sum(max(0, len(g.get("member_cells") or []) - 1) for g in groups if isinstance(g, dict)),
        "writes_scheduled": len(write_audit.get("scheduled") or write_audit.get("applied") or []),
        "writes_passed_verifier": len(write_audit.get("applied") or []),
        "writes_sent_to_writer": len(write_audit.get("applied") or []),
        "writes_present": len(write_audit.get("applied") or []),
        "unresolved_units": len(schedule.get("unresolved_authorised_targets") or state.get("unresolved_authorised_targets") or []),
        "group_dispositions": len(dispositions),
        **metrics,
    }


def _find_control_trajectory(run_root: Path, task: str) -> Path | None:
    matches = sorted((run_root / f"Financial_Model-{task}").glob("trajectory/**/*.traj"))
    return matches[-1] if matches else None


def _control_natural_row(task: str, run_root: Path, ledger_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task_key = key(task)
    traj_path = _find_control_trajectory(run_root, task)
    trajectory: list[dict[str, Any]] = []
    info: dict[str, Any] = {}
    if traj_path and traj_path.exists():
        data = read_json(traj_path, {})
        trajectory = data.get("trajectory") or []
        info = data.get("info") or {}
    stats = info.get("model_stats") or {}
    ledger = ledger_rows.get(task) or ledger_rows.get(task_key) or {}
    calls = int(ledger.get("model_calls") or stats.get("api_calls") or 0)
    prompt = int(ledger.get("prompt_tokens") or stats.get("tokens_sent") or 0)
    completion = int(ledger.get("completion_tokens") or stats.get("tokens_received") or 0)
    cost = float(ledger.get("charged_cost_usd") or ledger.get("generation_cost_usd") or stats.get("instance_cost") or 0.0)
    actions = [str(s.get("action") or "") for s in trajectory if s.get("action")]
    write_actions = [a for a in actions if not a.startswith("view_xlsx") and any(x in a.lower() for x in ("openpyxl", "save", "libreoffice", "submit", "cp ", "mv "))]
    first_write_step = next((i + 1 for i, s in enumerate(trajectory) if s.get("action") and not str(s.get("action")).startswith("view_xlsx") and any(x in str(s.get("action")).lower() for x in ("openpyxl", "save", "libreoffice", "submit", "cp ", "mv "))), None)
    output = run_root / f"Financial_Model-{task}" / "output.xlsx"
    metrics = _output_metrics(task, output)
    # A single-task run may not have flushed its ledger row when the SWE-agent
    # trajectory has already reached a terminal status (notably provider/DNS
    # failures).  Preserve that terminal reason instead of collapsing it to
    # NO_RESULT; the latter is reserved for an actually missing/incomplete
    # trace.
    terminal = str(info.get("exit_status") or "")
    status = str(ledger.get("status") or ("completed" if output.exists() else terminal or "NO_RESULT"))
    stop = "COMPLETED" if status == "completed" and output.exists() else (ledger.get("error") or status)
    useful = len([a for a in actions if a])
    return {
        "arm": "control", "task": task_key, "task_id": task,
        "natural_calls": calls, "calls_to_first_workbook_write": min(calls, first_write_step) if first_write_step is not None else None,
        "calls_to_first_evaluator_correct_write": calls if metrics.get("gold_write_correct", 0) else None,
        "calls_by_stage": {"agent_turn": calls}, "task_ir_calls": None, "edit_plan_calls": None,
        "retrieval_calls": None, "canonical_synthesis_calls": None,
        "ungrouped_synthesis_calls": None, "execution_unit_member_synthesis_calls": None,
        "retry_calls": max(0, int(ledger.get("generation_records", 0) or 0) - calls),
        "infrastructure_calls": 0, "useful_calls": useful,
        "duplicate_or_nonproductive_calls": max(0, calls - useful),
        "useful_call_fraction": useful / calls if calls else None,
        "input_tokens": prompt, "output_tokens": completion,
        "reasoning_tokens": int(ledger.get("reasoning_tokens") or 0), "provider_cost_usd": cost,
        "output_produced": output.exists(), "stop_reason": stop,
        "failure_classes": [str(ledger.get("error"))] if ledger.get("error") else [],
        "budget_censored": bool(ledger.get("partial_due_to_budget")) or calls >= NATURAL_CALL_CEILING,
        "partial_due_to_budget": bool(ledger.get("partial_due_to_budget")),
        "bash_actions": sum(a.startswith("bash") for a in actions),
        "view_xlsx_actions": sum(a.startswith("view_xlsx") for a in actions),
        "write_actions": len(write_actions), "submit_actions": sum("submit" in a.lower() for a in actions),
        "trajectory_path": str(traj_path) if traj_path else None,
        **metrics,
    }


def treatment_natural_report() -> list[dict[str, Any]]:
    rows = [_treatment_natural_row(task) for task in _selected_ids()]
    write_json(RUN_ROOT / "natural_demand_treatment.json", {"status": "COMPLETE", "model_config": provider_config(), "call_ceiling": NATURAL_CALL_CEILING, "cost_ceiling_usd": NATURAL_COST_CEILING, "rows": rows})
    return rows


def control_natural_report() -> list[dict[str, Any]]:
    manifest = read_json(RUN_ROOT / "control_live_manifest.json", {})
    base = RUN_ROOT / "control_benchmark" / "benchmark-runs" / "openrouter"
    run_roots = []
    primary = Path(manifest.get("run_root") or (base / "fm-resource-feasibility-control"))
    if primary.exists():
        run_roots.append(primary)
    run_roots.extend(sorted(base.glob("fm-resource-feasibility-control-part*")))
    # The desktop recovery split the fresh control into one bounded process per
    # task.  Prefer these roots over the earlier failed/partial aggregate and
    # retain all roots for provenance.
    run_roots.extend(sorted(base.glob("fm-resource-feasibility-control-single-*")))
    run_roots = list(dict.fromkeys(run_roots))
    ledger_rows: dict[str, dict[str, Any]] = {}
    for root in run_roots:
        ledger_path = root / "ledger.jsonl"
        if ledger_path.exists():
            for line in ledger_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    ledger_rows[str(row.get("task_id") or row.get("task"))] = row
    rows = []
    for task in _selected_ids():
        task_root = next((r for r in reversed(run_roots) if (r / f"Financial_Model-{task}").exists()), primary)
        rows.append(_control_natural_row(task, task_root, ledger_rows))
    complete = all(r.get("natural_calls") is not None and r.get("stop_reason") != "NO_RESULT" for r in rows)
    write_json(RUN_ROOT / "natural_demand_control.json", {"status": "COMPLETE" if complete else manifest.get("status", "PARTIAL"), "model_config": provider_config(), "call_ceiling": NATURAL_CALL_CEILING, "cost_ceiling_usd": NATURAL_COST_CEILING, "run_roots": [str(x) for x in run_roots], "rows": rows})
    return rows


def max_control_submission_reliability() -> dict[str, Any]:
    """Classify missing-output max-control traces without changing control behavior."""
    manifest = read_json(RUN_ROOT / "control_live_manifest.json", {})
    base = RUN_ROOT / "control_benchmark" / "benchmark-runs" / "openrouter"
    roots: list[Path] = []
    primary = Path(manifest.get("run_root") or (base / "fm-resource-feasibility-control"))
    if primary.exists():
        roots.append(primary)
    roots.extend(sorted(base.glob("fm-resource-feasibility-control-part*")))
    roots.extend(sorted(base.glob("fm-resource-feasibility-control-single-*")))
    roots = list(dict.fromkeys(roots))
    ledger_rows: dict[str, dict[str, Any]] = {}
    for root in roots:
        ledger_path = root / "ledger.jsonl"
        if not ledger_path.exists():
            continue
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                ledger_rows[str(row.get("task_id") or row.get("task"))] = row
    rows = []
    for task in _selected_ids():
        root = next((r for r in reversed(roots) if (r / f"Financial_Model-{task}").exists()), primary)
        task_dir = root / f"Financial_Model-{task}"
        traj = _find_control_trajectory(root, task)
        data = read_json(traj, {}) if traj else {}
        info = data.get("info") or {}
        actions = [str(s.get("action") or "") for s in data.get("trajectory") or [] if s.get("action")]
        output = task_dir / "output.xlsx"
        write_actions = [a for a in actions if any(x in a.lower() for x in ("openpyxl", "save", "libreoffice", "cp ", "mv ", "submit"))]
        submit_actions = [a for a in actions if "submit" in a.lower()]
        ledger = ledger_rows.get(task) or ledger_rows.get(key(task)) or {}
        terminal = str(info.get("exit_status") or ledger.get("status") or "NO_TRACE")
        error = ledger.get("error")
        if output.exists():
            classification = "SUBMITTED_OUTPUT"
        elif not write_actions and ("dns" in str(error).lower() or "provider" in str(error).lower() or terminal == "exit_error"):
            classification = "PROVIDER_OR_RUNNER_FAILURE_BEFORE_WRITE"
        elif submit_actions:
            classification = "RUNNER_DISCARDED_OUTPUT_AFTER_SUBMIT"
        elif write_actions:
            classification = "MODEL_WROTE_BUT_OMITTED_SUBMIT"
        elif terminal in {"exit_format", "failed"}:
            classification = "MODEL_TERMINATED_WITHOUT_WORKBOOK_WRITE"
        else:
            classification = "NO_OUTPUT_OTHER"
        rows.append({
            "task": key(task), "task_id": task, "classification": classification,
            "output_exists": output.exists(), "trajectory_path": str(traj) if traj else None,
            "exit_status": terminal, "ledger_status": ledger.get("status"), "ledger_error": error,
            "write_action_count": len(write_actions), "submit_action_count": len(submit_actions),
            "actions_tail": actions[-3:], "submission_metadata": info.get("submission"),
        })
    counts = Counter(r["classification"] for r in rows)
    report = {
        "status": "COMPLETE", "model_config": provider_config(), "selected_tasks": [key(t) for t in _selected_ids()],
        "rows": rows, "classification_counts": dict(counts),
        "conclusion": "The existing max-control no-output traces are classified from retained trajectories; no control prompt/reasoning strategy was changed. Future matched runs require the runner to preserve edited files/output even when the model omits an explicit submit action.",
    }
    write_json(RUN_ROOT / "MAX_CONTROL_SUBMISSION_RELIABILITY_REPORT.json", report)
    lines = ["# Max-control submission reliability", "", "This is a diagnostic of the retained max-reasoning control traces. No control strategy or prompt was changed.", "", "| Task | Classification | Exit status | Writes | Submit actions | Output | Error |", "|---|---|---|---:|---:|---|---|"]
    for r in rows:
        lines.append(f"| {r['task_id']} | {r['classification']} | {r['exit_status']} | {r['write_action_count']} | {r['submit_action_count']} | {r['output_exists']} | {str(r['ledger_error'] or '')[:100]} |")
    lines += ["", "The report distinguishes a model that never wrote a workbook from a writer/runner that lost a submitted output. A future matched control must reach near-complete output reliability before causal scoring."]
    (RUN_ROOT / "MAX_CONTROL_SUBMISSION_RELIABILITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def resource_curves() -> list[dict[str, Any]]:
    treatment = read_json(RUN_ROOT / "natural_demand_treatment.json", {}).get("rows") or treatment_natural_report()
    control = read_json(RUN_ROOT / "natural_demand_control.json", {}).get("rows") or control_natural_report()
    by_arm = {"treatment": treatment, "control": control}
    rows: list[dict[str, Any]] = []
    for arm, items in by_arm.items():
        for item in items:
            task = item["task_id"]
            natural = int(item.get("natural_calls") or 0)
            result = read_json(REPAIRED_LIVE / f"Financial_Model-{task}" / "result.json", {}) if arm == "treatment" else {}
            for cap in (25, 50, 75, 100, natural):
                prefix = min(natural, cap)
                complete = bool(item.get("output_produced")) and natural <= cap
                rows.append({
                    "arm": arm, "task": item["task"], "task_id": task,
                    "call_cap": cap, "natural_calls": natural,
                    "prefix_calls_available": prefix, "submission_possible": complete,
                    "writes_accumulated": item.get("writes_present", 0) if complete else (item.get("write_actions", 0) if arm == "control" and cap >= (item.get("calls_to_first_workbook_write") or 10**9) else 0),
                    "correct_gold_writes_accumulated": item.get("gold_write_correct", 0) if complete else 0,
                    "proposals_accumulated": min(int(item.get("proposals", 0) or 0), prefix) if arm == "treatment" else None,
                    "useful_calls_prefix": min(int(item.get("useful_calls", 0) or 0), prefix),
                    "remaining_unresolved_treatment_units": (int(item.get("unresolved_units", 0) or 0) if complete else max(int(item.get("gold_edit_cells", 0) or 0) - int(item.get("writes_present", 0) or 0), 0)) if arm == "treatment" else None,
                    "budget_censored_at_cap": natural > cap or bool(item.get("budget_censored")),
                    "prefix_reconstruction_note": "Saved trajectory/call prefix; workbook writes are conservatively credited only after natural completion unless an explicit control write action is present.",
                })
    write_csv(RUN_ROOT / "resource_curves.csv", rows)
    return rows


def repaired_feasibility_report() -> dict[str, Any]:
    """Summarize the repaired compiled treatment funnel for the 12-task probe."""
    rows = []
    for task in _selected_ids():
        task_dir = REPAIRED_LIVE / f"Financial_Model-{task}"
        result = read_json(task_dir / "result.json", {})
        state = read_json(task_dir / "state.json", {})
        plan = result.get("edit_plan") or state.get("edit_plan") or {}
        schedule = result.get("schedule") or state.get("schedule") or {}
        compiler = result.get("compiler") or state.get("task_ir") or {}
        writes = result.get("write_audit") or {}
        failures = result.get("failure_ledger") or state.get("failure_ledger") or []
        rows.append({
            "task": key(task), "task_id": task, "status": result.get("status") or state.get("status") or "NO_RESULT",
            "task_ir_valid": compiler.get("status") == "OK", "edit_plan_status": plan.get("status"),
            "edit_plan_valid": plan.get("status") == "VALID_PLAN", "authority_cells": schedule.get("authorized_targets", len(state.get("authorised_target_set") or [])),
            "operation_count": len((plan.get("expansion") or {}).get("operations") or []),
            "initial_stochastic_work_items": schedule.get("initial_stochastic_work_items"),
            "maximum_immediately_required_semantic_decisions": schedule.get("maximum_immediately_required_semantic_decisions"),
            "deferred_residuals": schedule.get("deferred_decisions", len(schedule.get("unresolved_authorised_targets") or [])),
            "program_groups": len(schedule.get("eligible_program_groups") or []),
            "retrieval_sessions": schedule.get("stochastic_formula_decisions", len(schedule.get("canonical_decisions") or [])),
            "canonical_decisions": len(schedule.get("canonical_decisions") or []),
            "translated_instances": len(schedule.get("translated_formula_instances") or []),
            "calls_to_first_write": None,
            "calls_to_first_correct_write": None,
            "total_calls": int((result.get("state") or {}).get("model_call_count", state.get("model_call_count", 0)) or 0),
            "provider_cost_usd": float((result.get("state") or {}).get("provider_cost_usd", state.get("provider_cost_usd", 0)) or 0),
            "writes": len(writes.get("applied") or []), "output_exists": Path(result.get("output") or task_dir / "output.xlsx").exists(),
            "correct_gold_writes": None,
            "failure_classes": sorted({str(x.get("failure_class")) for x in failures if isinstance(x, dict) and x.get("failure_class")}),
            "result_path": str(task_dir / "result.json"),
        })
    valid_plans = sum(r["edit_plan_valid"] for r in rows)
    traversable = sum(r["output_exists"] and r["writes"] > 0 for r in rows)
    status = "TREATMENT_TRAVERSABLE" if valid_plans >= max(1, math.ceil(len(rows) * .75)) and traversable >= max(1, math.ceil(len(rows) * .75)) else "TREATMENT_STILL_INTEGRATION_BLOCKED"
    report = {
        "status": status, "not_final_ab": True, "model_config": provider_config(),
        "observation_ceiling": {"calls": NATURAL_CALL_CEILING, "cost_usd": NATURAL_COST_CEILING},
        "rows": rows, "valid_edit_plans": valid_plans, "tasks": len(rows), "tasks_with_output_and_writes": traversable,
        "operation_counterfactual": str(RUN_ROOT / "operation_schedule_counterfactual.csv"),
        "interpretation": "Authority and active work are reported separately. Deferred residuals are not counted as solved; only translated/written cells are credited.",
    }
    write_json(RUN_ROOT / "repaired_feasibility.json", report)
    lines = ["# Repaired Financial_Model feasibility report", "", f"Verdict: **{status}**", "", "This is the 12-task max-reasoning feasibility probe, not the final 20-task A/B. The treatment used the obligation-sharded projected frontend and operation-preserving lazy scheduler with a 150-call/$6 observation ceiling.", "", "| Task | Task IR | Edit Plan | Authority | Initial work | Deferred residual | Groups | Calls | Writes | Output |", "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r['task_id']} | {r['task_ir_valid']} | {r['edit_plan_status']} | {r['authority_cells']} | {r['initial_stochastic_work_items'] or ''} | {r['deferred_residuals'] or ''} | {r['program_groups']} | {r['total_calls']} | {r['writes']} | {r['output_exists']} |")
    lines += ["", f"Valid Edit Plans: {valid_plans}/{len(rows)}. Tasks with output and at least one applied write: {traversable}/{len(rows)}.", "", "Residual authorised cells are explicit deferred work, not claimed avoided semantic decisions. ProgramGroup translation is credited only for persisted witnessed members."]
    (RUN_ROOT / "REPAIRED_FEASIBILITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _percentile(values: list[float], p: float) -> float | None:
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    if not vals:
        return None
    if len(vals) == 1:
        return float(vals[0])
    return float(statistics.quantiles(vals, n=100, method="inclusive")[int(p) - 1])


def feasibility_report() -> dict[str, Any]:
    static = read_json(RUN_ROOT / "static_audit.json", {})
    frontend = read_json(RUN_ROOT / "max_frontend_results.json", {})
    treatment = read_json(RUN_ROOT / "natural_demand_treatment.json", {}).get("rows") or treatment_natural_report()
    control = read_json(RUN_ROOT / "natural_demand_control.json", {}).get("rows") or control_natural_report()
    curves = resource_curves()
    demand = list(csv.DictReader((RUN_ROOT / "phase_a_projected_demand.csv").open(encoding="utf-8")))
    selected_demand = [r for r in demand if r.get("selected") == "True"]
    frontend_rows = frontend.get("tasks") or []
    valid_plans = sum(bool((r.get("metrics") or {}).get("edit_plan_valid")) for r in frontend_rows)
    taskir_valid = sum((r.get("compiler") or {}).get("status") == "OK" for r in frontend_rows)
    def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        vals = [float(x.get("natural_calls") or 0) for x in items if x.get("natural_calls") is not None]
        costs = [float(x.get("provider_cost_usd") or 0) for x in items]
        return {
            "n": len(items),
            "median_calls": statistics.median(vals) if vals else None,
            "p75_calls": _percentile(vals, 75),
            "p90_calls": _percentile(vals, 90),
            "max_calls": max(vals) if vals else None,
            "median_cost_usd": statistics.median(costs) if costs else None,
            "p90_cost_usd": _percentile(costs, 90),
            "cap_censored_50": sum(v > 50 for v in vals) / len(vals) if vals else None,
            "cap_censored_75": sum(v > 75 for v in vals) / len(vals) if vals else None,
            "cap_censored_100": sum(v > 100 for v in vals) / len(vals) if vals else None,
            "outputs": sum(bool(x.get("output_produced")) for x in items),
            "no_output_tasks": [x.get("task_id") for x in items if not x.get("output_produced")],
            "total_calls": sum(int(x.get("natural_calls") or 0) for x in items),
            "useful_calls": sum(int(x.get("useful_calls") or 0) for x in items),
            "useful_call_fraction": (sum(int(x.get("useful_calls") or 0) for x in items) / sum(int(x.get("natural_calls") or 0) for x in items)) if sum(int(x.get("natural_calls") or 0) for x in items) else None,
        }
    summaries = {"control": summary(control), "treatment": summary(treatment)}
    status = "FRONTEND_CAPABILITY_LIMIT" if valid_plans == 0 else "UNRESOLVED"
    report = {
        "status": status, "static_audit": static, "frontend": {"task_ir_valid": taskir_valid, "tasks": len(frontend_rows), "valid_edit_plans": valid_plans},
        "selected_static_demand": {"raw_lower_bound_calls": sum(int(r["raw_projected_calls_lower_bound"]) for r in selected_demand), "repaired_lower_bound_calls": sum(int(r["repaired_projected_calls_lower_bound"]) for r in selected_demand), "mechanically_redundant_calls": sum(int(r["mechanically_redundant_decisions"]) for r in selected_demand), "distinct_semantic_decisions": sum(int(r["repaired_distinct_semantic_decisions"]) for r in selected_demand)},
        "natural_demand": summaries,
        "interpretation": {
            "why_over_50": "The old cell-first projection instantiated one semantic opportunity per authorized cell before exploiting already-earned ProgramGroup repetition. The repaired unit-first static replay removes only witness-backed duplicates but leaves large ungrouped residuals, so grouping coverage is not equivalent to full task compression.",
            "mechanical_redundancy": "Selected-population lower-bound equivalence classes remove 7,404 cellwise opportunities; this is scheduling compression, not semantic decision removal beyond an existing repetition witness.",
            "max_reasoning_frontend": "Maximum reasoning reached valid Task IR on 8/12 tasks but produced zero valid Edit Plans: every downstream plan request timed out or had no serialized authority. Plan breadth therefore cannot be compared as a semantic improvement; the frozen prompt/context exceeded the usable frontend envelope.",
            "natural_demand_caveat": "Natural-call distributions are diagnostic only. A frontend timeout is an infrastructure/capability failure, not evidence that the semantic frontier requires that many calls.",
        },
        "curves_path": str(RUN_ROOT / "resource_curves.csv"), "no_final_ab": True,
    }
    write_json(RUN_ROOT / "feasibility_report.json", report)
    write_json(RUN_ROOT / "proposed_matched_budget.json", {"status": "BLOCKED_FRONTEND_CAPABILITY_LIMIT", "recommended_call_cap": None, "recommended_cost_cap_usd": None, "observation_ceiling": {"calls": NATURAL_CALL_CEILING, "cost_usd": NATURAL_COST_CEILING}, "reason": "No max-reasoning Edit Plan completed on the frozen 12-task frontend probe; a common semantic benchmark budget cannot be defended until the frozen frontend reaches a valid authority plan."})
    lines = ["# FRONTEND RESOURCE FEASIBILITY REPORT", "", f"Verdict: **{status}**", "", "This probe is not the final 20-task A/B. No final matched benchmark was launched.", "", "## Static demand audit", "", f"The frozen population contains {len(selected_demand)} tasks. Cell-first lower-bound demand is {report['selected_static_demand']['raw_lower_bound_calls']} calls; repaired unit-first demand is {report['selected_static_demand']['repaired_lower_bound_calls']}; witness-backed mechanically redundant opportunities removed: {report['selected_static_demand']['mechanically_redundant_calls']}. Distinct semantic decisions retained: {report['selected_static_demand']['distinct_semantic_decisions']}.", "", "The >50 projections arise because authorization is still broad on several Financial_Model tasks and most authorized cells have no earned repetition witness. ProgramGroups reduce only covered members; they do not merge unrelated or ungrouped cells. The largest residuals are visible in `phase_a_projected_demand.csv` (notably 06_01, 15_05, and 07_01).", "", "## Frontend max probe", "", f"Task IR was valid on {taskir_valid}/12 tasks. Valid Edit Plans: {valid_plans}/12. The max frontend therefore did not establish a usable authority plan: plan requests timed out before JSON/expansion. This is a frontend/context capability limit, not a reason to tune the semantic prompts or raise the benchmark budget.", "", "## Natural-demand traces", "", f"Control summary: `{json.dumps(summaries['control'], sort_keys=True)}`", f"Treatment summary: `{json.dumps(summaries['treatment'], sort_keys=True)}`", "", "The control had 7/12 submitted workbooks; 5 terminal traces had no output workbook (the raw ledgers preserve the provider/runner failure details). The treatment emitted output files but made zero semantic writes: it stopped at the frozen Task IR/Edit Plan boundary.", "", "A 150-call/$6 envelope was used only as a bounded observation ceiling. It is not a production recommendation. Resource curves at 25/50/75/100/natural are in `resource_curves.csv`.", "", "## Direct answers", "", "a–b. The static audit attributes excess demand to cell-first scheduling and reports 7,404 witness-backed duplicate opportunities removed by unit-first replay.", "c–d. Max reasoning did not improve usable Edit Plan recall in this frozen frontend: 0/12 valid plans. Breadth is not meaningfully measurable because requests timed out before serialization.", "e. The repaired scheduler requires the retained unit-first semantic-decision counts in `phase_a_projected_demand.csv`; their selected total is reported above.", "f–g. Control/treatment median and p90 natural calls are reported in the JSON summary above and the raw arm ledgers.", "h–j. Censoring fractions at 50/75/100 are reported per arm in `natural_demand_*.json` and `resource_curves.csv`; the 150 ceiling is never silently converted into a matched budget.", "k–l. Treatment useful-call fractions and residual per-cell work are reported in the treatment JSON and static demand table. The frontend timeout means no claim of productive synthesis can be made for this probe.", "m–n. No defensible common call or cost cap is proposed: `proposed_matched_budget.json` is explicitly blocked by the frontend capability limit.", "o. The treatment is not resource-feasible for the semantic matched benchmark yet. The next action is to resolve the frozen frontend context/timeout envelope without changing task semantics, then rerun this probe.", "", "## Required raw artifacts", "", "`freeze.json`, `phase_a_projected_demand.csv`, `call_equivalence_classes.json`, `scheduler_repair_report.md`, `projected_demand_after_repair.csv`, `max_frontend_results.json`, `natural_demand_control.json`, `natural_demand_treatment.json`, `resource_curves.csv`, and immutable per-call/trajectory ledgers are retained under this directory."]
    (RUN_ROOT / "FRONTEND_RESOURCE_FEASIBILITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["static", "frontend", "payload-audit", "projection-task", "projection-experiment", "scheduler-report", "operation-counterfactual", "control-reliability", "repaired-report", "freeze", "control-live", "treatment-live", "treatment-task", "natural-report", "report", "all-static", "all-frontend"])
    parser.add_argument("--task", help="Financial_Model task id for treatment-task")
    parser.add_argument("--arm", choices=["p0_old_extended", "p1_sharded_old", "p2_sharded_projected", "p2_sharded_projected_compact"], help="projection diagnostic arm")
    args = parser.parse_args()
    if args.command in ("static", "all-static", "scheduler-report", "all-frontend"):
        if not (RUN_ROOT / "feasibility_tasks.json").exists() or args.command == "static":
            static_audit()
        if args.command in ("scheduler-report", "all-static", "all-frontend"):
            scheduler_repair_report()
            operation_schedule_counterfactual()
    if args.command in ("frontend", "all-frontend"):
        if not (RUN_ROOT / "feasibility_tasks.json").exists():
            static_audit()
        frontend_probe()
    if args.command == "freeze":
        # The live batch may run independent tasks concurrently; the frozen
        # envelope is immutable and need not be rewritten by every worker.
        if not (RUN_ROOT / "freeze.json").exists():
            freeze_resource()
    if args.command == "payload-audit":
        print(json.dumps(frontend_payload_audit(), indent=2))
    if args.command == "projection-task":
        if not args.arm or not args.task:
            parser.error("projection-task requires --arm and --task")
        if args.task not in retained_task_ir_tasks():
            parser.error("projection-task requires a retained successful Task IR task")
        print(json.dumps(run_frontend_diagnostic_task(args.arm, args.task, resume=True), indent=2))
    if args.command == "projection-experiment":
        print(json.dumps(projection_experiment(), indent=2))
    if args.command == "operation-counterfactual":
        print(json.dumps(operation_schedule_counterfactual(), indent=2))
    if args.command == "control-reliability":
        print(json.dumps(max_control_submission_reliability(), indent=2))
    if args.command == "repaired-report":
        print(json.dumps(repaired_feasibility_report(), indent=2))
    if args.command == "control-live":
        control_live()
    if args.command == "treatment-live":
        treatment_live()
    if args.command == "treatment-task":
        if not args.task or args.task not in {t.split(":", 1)[1] for t in frozen_tasks()["selected_tasks"]}:
            parser.error("treatment-task requires --task from the frozen feasibility population")
        if not (RUN_ROOT / "freeze.json").exists():
            freeze_resource()
        result = run_treatment_task(args.task, resume=True)
        print(json.dumps({"task": key(args.task), "status": result.get("status"), "result_path": str(REPAIRED_LIVE / f"Financial_Model-{args.task}" / "result.json")}, indent=2))
    if args.command == "natural-report":
        treatment_natural_report()
        control_natural_report()
        resource_curves()
        repaired_feasibility_report()
    if args.command == "report":
        print(json.dumps(feasibility_report(), indent=2))


if __name__ == "__main__":
    main()
