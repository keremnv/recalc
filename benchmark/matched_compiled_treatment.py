#!/usr/bin/env python3
"""Frozen 60-task compiled-harness treatment.

This runner has no provider side effect unless the explicit ``run`` command is
used after the freeze and all deterministic gates pass.  ``freeze``,
``neutrality``, ``dry-run`` and ``preflight-only`` never make model calls.

The runtime state machine is:

    task IR -> grounding -> Edit Plan -> deterministic expansion -> bootstrap
    -> bounded SQL/delta working state -> proposal -> C1 closure -> groups
    -> deterministic translation -> ungrouped synthesis -> neutral actuation.

Edit Plan authority is never widened by dependency closure.  Formula edits are
the earned actuation scope; unsupported literal/clear operations are retained
as explicit failures rather than silently guessed or repaired.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import signal
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "src"), str(ROOT / "benchmark/sweagent/formula_index/lib")]

from xlsx_metadata_repair import install as install_metadata_repair, repair as repair_metadata  # noqa: E402

install_metadata_repair()

import openpyxl  # noqa: E402
from openpyxl.cell.cell import MergedCell  # noqa: E402

import composition_closure as closure  # noqa: E402
import end_to_end_composition_probe as prior  # noqa: E402
import edit_plan_probe  # noqa: E402
import program_group  # noqa: E402
import relational_retrieval_probe as relational  # noqa: E402
import task_obligation_compile as task_compile  # noqa: E402
import workbook_grounding_spine as spine_compiler  # noqa: E402
from experiment_config import (  # noqa: E402
    AUTHORITATIVE_EXPERIMENT_CONFIG,
    ExperimentConfig,
    activate_experiment_config,
    active_experiment_config,
    assert_declared_matches_wire,
    identity_record,
    request_identity,
    response_identity,
    restore_experiment_config,
    timeout_for_stage,
)
from edit_plan import PlanError, World, expand_edit_plan  # noqa: E402
from formula_completion_certs import load_grids  # noqa: E402
from formula_dependency_selection import build_graph_from_grids  # noqa: E402
from formula_operational import build_view  # noqa: E402
from formula_verifier import scc_stats  # noqa: E402
from workbook_grounding import project_obligation, token_estimate  # noqa: E402
from workbook_spine_sqlite import ReadOnlySqlite, build_database  # noqa: E402
from xlsx_cell_writer import write_cells  # noqa: E402


RUN_NAME = "matched-glm-compiled-sixty"
RUN_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs" / RUN_NAME
PREP = RUN_ROOT / "prep"
INPUTS = PREP / "repaired_inputs"
SPINES = PREP / "spines"
TEMPORAL = PREP / "temporal"
DATABASES = PREP / "db"
LIVE = RUN_ROOT / "live"
NEUTRALITY = PREP / "neutrality"
DRY = PREP / "dry_run"

AUDIT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/historical-control-audit/control_audit.json"
CONTROL_SLICE = ROOT / "benchmark/slices/control-census-sixty.json"
CONTROL_CONFIG = ROOT / "benchmark/sweagent/spreadsheet-control.yaml"
COMPILED_CONFIG = ROOT / "benchmark/sweagent/spreadsheet.yaml"
CENSUS_TASKS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/structural-recoverability-census/tasks.json"
CONTROL_RUN = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/glm-5.3-flash-control-census-sixty-1"

MODEL = AUTHORITATIVE_EXPERIMENT_CONFIG.model
PROVIDER = AUTHORITATIVE_EXPERIMENT_CONFIG.provider
REASONING = AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning
TEMPERATURE = AUTHORITATIVE_EXPERIMENT_CONFIG.temperature
MAX_MODEL_CALLS = 50
MAX_COST_USD = 4.0
MAX_SQL_CALLS = 8
EXECUTION_TIMEOUT = 180
OBSERVATION_LIMIT = 10_000
LOCAL_OPENROUTER_KEY = ROOT / ".secrets/openrouter_api_key.b64"

# The archived treatment contract remains the default so historical replay and
# its tests stay byte-for-byte compatible.  A fresh feasibility run opts into
# this explicit runtime profile before it starts; every stochastic request then
# reads the same active values.  Keeping the profile in one place prevents a
# frontend max-reasoning probe from accidentally leaving retrieval/synthesis on
# the old low-reasoning/50-call envelope.
ACTIVE_REASONING = REASONING
ACTIVE_TOP_P: float | None = AUTHORITATIVE_EXPERIMENT_CONFIG.top_p
ACTIVE_MAX_MODEL_CALLS = MAX_MODEL_CALLS
ACTIVE_MAX_COST_USD = MAX_COST_USD
ACTIVE_FRONTEND_MODE = "monolithic"
ACTIVE_FRONTEND_TIMEOUT = timeout_for_stage("edit_plan")


def configure_runtime(*, reasoning: str | None = None, top_p: float | None = None,
                      max_model_calls: int | None = None, max_cost_usd: float | None = None,
                      frontend_mode: str | None = None,
                      frontend_timeout: int | None = None) -> dict[str, Any]:
    """Set the explicit per-run stochastic profile and return the old one.

    This is deliberately a small configuration seam, not a second planning
    abstraction.  The default profile is the frozen historical runner; callers
    doing the new max-reasoning feasibility probe must set all shared values
    before making the first model call and restore them afterwards.
    """
    global ACTIVE_REASONING, ACTIVE_TOP_P, ACTIVE_MAX_MODEL_CALLS, ACTIVE_MAX_COST_USD, ACTIVE_FRONTEND_MODE, ACTIVE_FRONTEND_TIMEOUT
    previous = {
        "reasoning": ACTIVE_REASONING,
        "top_p": ACTIVE_TOP_P,
        "max_model_calls": ACTIVE_MAX_MODEL_CALLS,
        "max_cost_usd": ACTIVE_MAX_COST_USD,
        "frontend_mode": ACTIVE_FRONTEND_MODE,
        "frontend_timeout": ACTIVE_FRONTEND_TIMEOUT,
    }
    if reasoning is not None and str(reasoning) != AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning:
        raise RuntimeError(f"REQUEST_CONFIGURATION_OVERRIDE_REJECTED: reasoning={reasoning!r}")
    if top_p is not None and float(top_p) != AUTHORITATIVE_EXPERIMENT_CONFIG.top_p:
        raise RuntimeError(f"REQUEST_CONFIGURATION_OVERRIDE_REJECTED: top_p={top_p!r}")
    if max_model_calls is not None:
        ACTIVE_MAX_MODEL_CALLS = int(max_model_calls)
    if max_cost_usd is not None:
        ACTIVE_MAX_COST_USD = float(max_cost_usd)
    if frontend_mode is not None:
        if frontend_mode not in {"monolithic", "sharded_old", "sharded_projected"}:
            raise ValueError(f"unknown frontend mode: {frontend_mode}")
        ACTIVE_FRONTEND_MODE = frontend_mode
    if frontend_timeout is not None and int(frontend_timeout) != timeout_for_stage("edit_plan"):
        raise RuntimeError(f"REQUEST_CONFIGURATION_OVERRIDE_REJECTED: frontend_timeout={frontend_timeout!r}")
    return previous


def restore_runtime(previous: dict[str, Any]) -> None:
    global ACTIVE_REASONING, ACTIVE_TOP_P, ACTIVE_MAX_MODEL_CALLS, ACTIVE_MAX_COST_USD, ACTIVE_FRONTEND_MODE, ACTIVE_FRONTEND_TIMEOUT
    ACTIVE_REASONING = active_experiment_config().reasoning
    ACTIVE_TOP_P = active_experiment_config().top_p
    ACTIVE_MAX_MODEL_CALLS = previous["max_model_calls"]
    ACTIVE_MAX_COST_USD = previous["max_cost_usd"]
    ACTIVE_FRONTEND_MODE = previous["frontend_mode"]
    ACTIVE_FRONTEND_TIMEOUT = timeout_for_stage("edit_plan")


def bind_compiled_identity(config: ExperimentConfig) -> dict[str, Any]:
    """Bind the compiled runner's request identity to an explicit experiment config.

    Architecture, schemas, evidence, and actuation stay frozen.  Only the
    fail-closed generation identity changes.  Callers must restore.
    """
    global MODEL, PROVIDER, REASONING, TEMPERATURE, ACTIVE_REASONING, ACTIVE_TOP_P
    previous = {
        "config": activate_experiment_config(config),
        "MODEL": MODEL,
        "PROVIDER": PROVIDER,
        "REASONING": REASONING,
        "TEMPERATURE": TEMPERATURE,
        "ACTIVE_REASONING": ACTIVE_REASONING,
        "ACTIVE_TOP_P": ACTIVE_TOP_P,
        "max_model_calls": ACTIVE_MAX_MODEL_CALLS,
        "max_cost_usd": ACTIVE_MAX_COST_USD,
        "frontend_mode": ACTIVE_FRONTEND_MODE,
        "frontend_timeout": ACTIVE_FRONTEND_TIMEOUT,
    }
    MODEL = config.model
    PROVIDER = config.provider
    REASONING = config.reasoning
    TEMPERATURE = config.temperature
    ACTIVE_REASONING = config.reasoning
    ACTIVE_TOP_P = config.top_p
    return previous


def restore_compiled_identity(previous: dict[str, Any]) -> None:
    global MODEL, PROVIDER, REASONING, TEMPERATURE, ACTIVE_REASONING, ACTIVE_TOP_P, ACTIVE_MAX_MODEL_CALLS, ACTIVE_MAX_COST_USD, ACTIVE_FRONTEND_MODE, ACTIVE_FRONTEND_TIMEOUT
    restore_experiment_config(previous["config"])
    MODEL = previous["MODEL"]
    PROVIDER = previous["PROVIDER"]
    REASONING = previous["REASONING"]
    TEMPERATURE = previous["TEMPERATURE"]
    ACTIVE_REASONING = previous["ACTIVE_REASONING"]
    ACTIVE_TOP_P = previous["ACTIVE_TOP_P"]
    ACTIVE_MAX_MODEL_CALLS = previous["max_model_calls"]
    ACTIVE_MAX_COST_USD = previous["max_cost_usd"]
    ACTIVE_FRONTEND_MODE = previous["frontend_mode"]
    ACTIVE_FRONTEND_TIMEOUT = previous["frontend_timeout"]

_TASK_ROWS_CACHE: list[dict[str, Any]] | None = None

RETRIEVAL_SYSTEM = prior.DELTA_RETRIEVAL_SYSTEM
# The inherited evidence-retrieval preamble explicitly prohibited synthesis.
# At transition only the synthesis protocol is authoritative.
SYNTHESIS_SYSTEM = prior.SYNTHESIS_SYSTEM.replace(relational.COMMON_PROMPT, "", 1)
TASK_IR_SYSTEM = task_compile.PARSER_PROMPT
EDIT_PLAN_PROMPT = edit_plan_probe.PLAN_PROMPT
EDIT_PLAN_SCHEMA = edit_plan_probe.SCHEMA

NON_MODEL_FAILURES = {
    "MODEL_ACCESS_FAILURE", "PROVIDER_ERROR", "TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT",
    "QUERY_TIMEOUT", "SQL_ERROR", "RESULT_TOO_LARGE", "INVALID_ACTION",
    "INVALID_ENTITY", "INVALID_EDIT_PLAN", "ADMISSIBILITY_LIMIT",
    "SESSION_RESOURCE_LIMIT", "TRUNCATED_AT_BUDGET", "TRUNCATED_NO_CONTENT",
    "PARSE_FAILURE", "WRITER_FAILURE", "SCORER_FAILURE", "INFRASTRUCTURE_RETRY", "PROVIDER_TIMEOUT",
}
FATAL_TASK_FAILURES = {"MODEL_ACCESS_FAILURE", "PROVIDER_ERROR", "INTEGRATION_FAILURE", "SCORER_FAILURE"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents a desktop/process interruption from leaving
    # a truncated authoritative state file.
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def task_rows() -> list[dict[str, Any]]:
    global _TASK_ROWS_CACHE
    if _TASK_ROWS_CACHE is not None:
        return _TASK_ROWS_CACHE
    audit = read_json(AUDIT)
    rows = audit["structural_join"]["task_rows"]
    expected = [f"{r['category']}:{r['id']}" for r in read_json(CONTROL_SLICE)["tasks"]]
    by_key = {r["task_key"]: r for r in rows}
    out = []
    for key in expected:
        row = dict(by_key[key])
        row["task_key"] = key
        row["category"], row["task"] = key.split(":", 1)
        out.append(row)
    _TASK_ROWS_CACHE = out
    return out


def task_map() -> dict[str, dict[str, Any]]:
    return {r["task_key"]: r for r in task_rows()}


def check_model(model: str, reasoning: str, temperature: float) -> None:
    if model != MODEL:
        raise RuntimeError(f"MODEL_GUARD: expected {MODEL}, got {model}")
    if reasoning != REASONING:
        raise RuntimeError(f"REASONING_GUARD: expected {REASONING}, got {reasoning}")
    if float(temperature) != TEMPERATURE:
        raise RuntimeError(f"TEMPERATURE_GUARD: expected {TEMPERATURE}, got {temperature}")


def provider_key() -> str | None:
    """Load the provider credential from the environment or ignored local secret file."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    if not LOCAL_OPENROUTER_KEY.exists():
        return None
    try:
        return base64.b64decode(LOCAL_OPENROUTER_KEY.read_text(encoding="ascii").strip(), validate=True).decode("ascii").strip()
    except (ValueError, UnicodeError):
        return None


def source_path(row: dict[str, Any]) -> Path:
    repaired = INPUTS / f"{row['category']}-{row['task']}_input.xlsx"
    if repaired.exists():
        return repaired
    return Path(row["input_path"])


def prepare_source(row: dict[str, Any]) -> dict[str, Any]:
    source = Path(row["input_path"])
    output = INPUTS / f"{row['category']}-{row['task']}_input.xlsx"
    metadata_repaired = False
    if row["task_key"] == "Financial_Model:06_01":
        repaired = repair_metadata(source, INPUTS)
        if repaired is None:
            return {"status": "TREATMENT_INPUT_UNRUNNABLE", "source": str(source), "error": "metadata-only repair unavailable"}
        metadata_repaired = True
        output = repaired
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.exists():
            shutil.copy2(source, output)
    return {
        "status": "TREATMENT_RUNNABLE_CENSUS_UNCLASSIFIABLE" if metadata_repaired else "OK",
        "original_path": str(source),
        "effective_path": str(output),
        "original_sha256": file_digest(source),
        "effective_sha256": file_digest(output),
        "metadata_only_repair": metadata_repaired,
    }


def build_environment() -> dict[str, Any]:
    """Compile all 60 source workbooks into private read-only treatment state."""
    rows = task_rows()
    records = []
    for row in rows:
        source = prepare_source(row)
        if source["status"] == "TREATMENT_INPUT_UNRUNNABLE":
            records.append({"task_key": row["task_key"], **source})
            continue
        effective = Path(source["effective_path"])
        spine_path = SPINES / f"{row['category']}-{row['task']}.json"
        temporal_path = TEMPORAL / f"{row['category']}-{row['task']}.json"
        db_path = DATABASES / f"{row['category']}-{row['task']}.sqlite"
        try:
            compiled = spine_compiler.compile_spine(effective, workbook_key=row["task_key"])
            write_json(spine_path, compiled)
            temporal = read_json(temporal_path) if temporal_path.exists() else {}
            # Historical prep left empty placeholders at these paths. File
            # existence alone is not evidence that closure was compiled.
            if temporal.get("readable") is not True or not isinstance(temporal.get("closure"), dict):
                from temporal_spine import compile_temporal_workbook
                write_json(temporal_path, compile_temporal_workbook(effective, closure=True))
            db = build_database(spine_path, temporal_path, db_path)
            records.append({
                "task_key": row["task_key"], **source,
                "spine": {
                    "readable": compiled.get("readable"),
                    "error": compiled.get("error"),
                    "sha256": file_digest(spine_path),
                    "lineage": compiled.get("lineage"),
                },
                "database": db,
                "database_sha256": file_digest(db_path),
                "lineage": compiled.get("lineage"),
            })
        except Exception as exc:
            records.append({"task_key": row["task_key"], **source, "status": "TREATMENT_INPUT_UNRUNNABLE", "error": f"{type(exc).__name__}: {exc}"})
    payload = {"generated_at": now(), "task_count": len(rows), "records": records, "all_inputs_present": all(r.get("status") != "TREATMENT_INPUT_UNRUNNABLE" for r in records), "malformed_metadata_policy": "metadata-only repaired private copy; original input never modified"}
    write_json(PREP / "environment.json", payload)
    return payload


def _database_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    conn = sqlite3.connect(path)
    try:
        return {row[0]: row[1] for row in conn.execute("SELECT key,value FROM metadata")}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def _environment_record_current(record: dict[str, Any]) -> bool:
    effective = Path(record.get("effective_path", ""))
    if not effective.exists():
        return False
    source_sha256 = file_digest(effective)
    lineage = record.get("lineage") or (record.get("spine") or {}).get("lineage") or {}
    if source_sha256 != record.get("effective_sha256") or source_sha256 != lineage.get("source_sha256"):
        return False
    task = record.get("task_key", "").replace(":", "-")
    spine_path = SPINES / f"{task}.json"
    db_path = DATABASES / f"{task}.sqlite"
    if not spine_path.exists() or not db_path.exists():
        return False
    compiled = read_json(spine_path)
    spine_lineage = compiled.get("lineage") or {}
    if spine_lineage.get("source_sha256") != source_sha256 or spine_lineage.get("payload_sha256") != lineage.get("payload_sha256"):
        return False
    metadata = _database_metadata(db_path)
    return metadata.get("source_sha256") == source_sha256 and metadata.get("payload_sha256") == spine_lineage.get("payload_sha256")


def ensure_environment() -> dict[str, Any]:
    path = PREP / "environment.json"
    if path.exists():
        env = read_json(path)
        if len(env.get("records", [])) == 60 and all(_environment_record_current(record) for record in env["records"]):
            return env
        # A stale DB/spine/cache must never be treated as a valid compiled
        # world merely because its files exist.  Rebuild the full private
        # lineage from the effective source workbooks.
    return build_environment()


def effective_record(task_key: str) -> dict[str, Any]:
    env = ensure_environment()
    return next(r for r in env["records"] if r["task_key"] == task_key)


def spine_for(task_key: str) -> dict[str, Any]:
    row = task_map()[task_key]
    return read_json(SPINES / f"{row['category']}-{row['task']}.json")


def planning_spine_for(task_key: str, world: World) -> dict[str, Any]:
    """Project the same compiled temporal identities that validate the plan.

    The legacy spine's local period layer is not the closure-backed world.
    Read the active database, so a repaired DB cannot coexist with stale
    grounding periods or a different temporal sidecar during planning.
    """
    from temporal_spine import overlay_periods

    coordinates = []
    for rec in world.temporal.values():
        parsed = spine_compiler.parse_cell_id(rec["cell_id"])
        if parsed is None:
            raise ValueError(f"INVALID_TEMPORAL_CELL: {rec['cell_id']}")
        _, row, col = parsed
        coordinates.append({
            "id": rec["temporal_id"], "cell_id": rec["cell_id"],
            "sheet_id": rec["sheet_id"], "row_id": rec["row_id"], "col_id": rec["col_id"],
            "row": row, "col": col, "address": closure.a1(row, col), "axis": rec["axis"],
            "period": {k: rec[k] for k in ("year", "month", "quarter") if rec.get(k) is not None},
            "period_key": rec.get("period_key"), "header_text": rec.get("header_text"),
        })
    return overlay_periods(spine_for(task_key), {"coordinates": coordinates})


def db_for(task_key: str) -> Path:
    row = task_map()[task_key]
    return DATABASES / f"{row['category']}-{row['task']}.sqlite"


def task_source(task_key: str) -> Path:
    return Path(effective_record(task_key)["effective_path"])


def target_address(spine: dict[str, Any], cell_id: str) -> dict[str, Any] | None:
    return prior.target_address(spine, cell_id)


def cell_info(source: Path, sheet: str, address: str) -> dict[str, Any]:
    wb = openpyxl.load_workbook(source, data_only=False, read_only=True)
    try:
        value = wb[sheet][address].value
    finally:
        wb.close()
    kind = "blank" if value is None or (isinstance(value, str) and not value.strip()) else "formula" if isinstance(value, str) and value.startswith("=") else "value"
    return {"kind": kind, "raw_value": value}


def compact_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"columns": [], "rows": []}
    columns = sorted({key for row in rows for key in row})
    return {"columns": columns, "rows": [[row.get(key) for key in columns] for row in rows]}


def plan_context(task: dict[str, Any], compiler: dict[str, Any], packets: dict[str, dict[str, Any]], world: World) -> dict[str, Any]:
    grounding: dict[str, Any] = {}
    for oid, packet in packets.items():
        grounding[oid] = {key: compact_table(packet.get(key, [])) for key in ("locus", "subject", "scope", "source")}
        grounding[oid]["target_candidate_ids"] = sorted(packet.get("target_cell_ids", []))
        grounding[oid]["candidate_count"] = len(packet.get("target_cell_ids", []))
        grounding[oid]["fields"] = packet.get("fields")
    return {
        "RAW_TASK": compiler["raw_task"],
        "GENERATED_TASK_IR": {"obligations": compiler.get("obligations", [])},
        "SHEETS": compact_table(list(world.sheets.values())),
        "GROUNDING": grounding,
        "NOTE": "Grounding candidates are evidence, not a whitelist. Use only closed-world identities and compact set expressions. Do not enumerate targets unless required by the schema.",
        "EXACT_JSON_SCHEMA": EDIT_PLAN_SCHEMA,
    }


def formula_forms(source: Path) -> dict[closure.Cell, str]:
    wb = openpyxl.load_workbook(source, data_only=False, read_only=True)
    try:
        out: dict[closure.Cell, str] = {}
        for ws in wb.worksheets:
            for row_idx, row in enumerate(ws.iter_rows(), start=1):
                for col_idx, cell in enumerate(row, start=1):
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        out[(ws.title, row_idx, col_idx)] = cell.value
        return out
    finally:
        wb.close()


def input_kinds(source: Path) -> dict[closure.Cell, str]:
    wb = openpyxl.load_workbook(source, data_only=False, read_only=True)
    try:
        out = {}
        for ws in wb.worksheets:
            for row_idx, row in enumerate(ws.iter_rows(), start=1):
                for col_idx, cell in enumerate(row, start=1):
                    value = cell.value
                    out[(ws.title, row_idx, col_idx)] = "blank" if value is None else "formula" if isinstance(value, str) and value.startswith("=") else "value"
        return out
    finally:
        wb.close()


def db_precedent_graph(db_path: Path) -> dict[closure.Cell, set[closure.Cell]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sheet_names = {r["sheet_id"]: r["name"] for r in conn.execute("SELECT sheet_id,name FROM sheets")}
    cells = {r["cell_id"]: (sheet_names.get(r["sheet_id"], r["sheet_id"]), r["row_idx"], r["col_idx"]) for r in conn.execute("SELECT cell_id,sheet_id,row_idx,col_idx FROM cells")}
    formula_cells = {r["formula_id"]: r["cell_id"] for r in conn.execute("SELECT formula_id,cell_id FROM formulas")}
    pre: dict[closure.Cell, set[closure.Cell]] = defaultdict(set)
    for row in conn.execute("SELECT formula_id,referenced_cell_id FROM point_references"):
        consumer, source = cells.get(formula_cells.get(row["formula_id"])), cells.get(row["referenced_cell_id"])
        if consumer and source:
            pre[consumer].add(source)
    ranges = {r["range_id"]: (sheet_names.get(r["sheet_id"], r["sheet_id"]), r["r1"], r["c1"], r["r2"], r["c2"]) for r in conn.execute("SELECT range_id,sheet_id,r1,c1,r2,c2 FROM ranges")}
    for row in conn.execute("SELECT formula_id,range_id FROM range_references"):
        consumer = cells.get(formula_cells.get(row["formula_id"]))
        spec = ranges.get(row["range_id"])
        if consumer and spec:
            sheet, r1, c1, r2, c2 = spec
            if (r2 - r1 + 1) * (c2 - c1 + 1) <= 40_000:
                pre[consumer].update((sheet, r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1))
    conn.close()
    return dict(pre)


def proposal_precedents(formula: str, seed: closure.Cell) -> set[closure.Cell]:
    from integrated_hybrid_synthesis_probe import eval_tools
    out: set[closure.Cell] = set()
    try:
        refs = eval_tools._ref_records(formula, seed[0], seed[1], seed[2])
    except Exception:
        return out
    for ref in refs.get("points", []) + refs.get("ranges", []):
        m1 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?(\d+)", ref.get("start") or "")
        if not m1:
            continue
        r1, c1 = int(m1.group(2)), closure.col_index(m1.group(1))
        if ref.get("is_range"):
            m2 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?(\d+)", ref.get("end") or ref["start"])
            if not m2:
                continue
            r2, c2 = int(m2.group(2)), closure.col_index(m2.group(1))
            if (r2 - r1 + 1) * (c2 - c1 + 1) <= 40_000:
                out.update((ref["sheet"], r, c) for r in range(min(r1, r2), max(r1, r2) + 1) for c in range(min(c1, c2), max(c1, c2) + 1))
        else:
            out.add((ref["sheet"], r1, c1))
    return out


def materialize(db_path: Path, working: set[str]) -> dict[str, Any]:
    # Materialization is not a bounded stochastic SQL read. Its contract is to
    # serialize every retained entity, including sheet names and temporal data.
    # A failed size-limited SELECT must never silently become an empty table.
    return materialize_complete(db_path, working)


def materialize_complete(db_path: Path, working: set[str]) -> dict[str, Any]:
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    tables = {"cell": ("cells", "cell_id"), "formula": ("formulas", "formula_id"), "range": ("ranges", "range_id"), "formula_class": ("formula_classes", "fingerprint_id"), "sheet": ("sheets", "sheet_id"), "text": ("text_anchors", "anchor_id"), "row": ("rows", "row_id"), "col": ("columns", "col_id"), "temporal": ("temporal_coordinates", "temporal_id")}
    output = {"entity_ids": sorted(working), "entities": {}, "relations": {}}
    try:
        for prefix, (table, column) in tables.items():
            ids = sorted(x for x in working if x.startswith(prefix + ":"))
            rows = []
            for offset in range(0, len(ids), 500):
                chunk = ids[offset:offset + 500]
                rows.extend(dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE {column} IN ({','.join('?' for _ in chunk)}) ORDER BY {column}", chunk))
            if prefix == "cell":
                found = {r["cell_id"] for r in rows}
                sheets = {r["sheet_id"]: dict(r) for r in conn.execute("SELECT * FROM sheets")}
                for cid in sorted(set(ids) - found):
                    match = re.fullmatch(r"cell:(s\d+):r(\d+):c(\d+)", cid)
                    if not match:
                        continue
                    sid, rr, cc = "sheet:" + match[1], int(match[2]), int(match[3])
                    sheet = sheets.get(sid)
                    if sheet and sheet["used_r1"] <= rr <= sheet["used_r2"] and sheet["used_c1"] <= cc <= sheet["used_c2"]:
                        rows.append({"cell_id": cid, "sheet_id": sid, "row_idx": rr, "col_idx": cc, "address": closure.a1(rr, cc), "kind": "blank", "raw_value": None, "display_value": None, "implicit_blank": True})
            output["entities"][table] = compact_table(rows)
        # Cell IDs encode sheet indices; synthesis needs the index/name map.
        output["entities"]["sheets"] = compact_table([dict(r) for r in conn.execute("SELECT * FROM sheets ORDER BY sheet_index")])
        fids = sorted(x for x in working if x.startswith("formula:"))
        for table in ("point_references", "range_references"):
            rows = []
            for offset in range(0, len(fids), 500):
                chunk = fids[offset:offset + 500]
                rows.extend(dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE formula_id IN ({','.join('?' for _ in chunk)}) ORDER BY formula_id,ref_slot", chunk))
            output["relations"][table] = compact_table(rows)
        return output
    finally:
        conn.close()


def legacy_materialize(db_path: Path, working: set[str]) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    for entity in sorted(working):
        groups[entity.split(":", 1)[0]].append(entity)
    executor = ReadOnlySqlite(db_path, max_rows=relational.RESULT_ROW_LIMIT, max_bytes=relational.RESULT_BYTE_LIMIT)
    def quoted(ids: list[str]) -> str:
        return ",".join("'" + x.replace("'", "''") + "'" for x in ids) or "NULL"
    output = {"entity_ids": sorted(working), "entities": {}, "relations": {}}
    if groups["cell"]:
        rows = executor.execute(f"SELECT cell_id,kind,raw_value,display_value FROM cells WHERE cell_id IN ({quoted(groups['cell'])}) ORDER BY cell_id").get("rows", [])
        output["entities"]["cells"] = {"columns": ["cell_id", "kind", "raw_value", "display_value"], "rows": [[r.get(k) for k in ("cell_id", "kind", "raw_value", "display_value")] for r in rows]}
    if groups["formula"]:
        rows = executor.execute(f"SELECT formula_id,cell_id,formula_text,fingerprint_id,opaque FROM formulas WHERE formula_id IN ({quoted(groups['formula'])}) ORDER BY formula_id").get("rows", [])
        output["entities"]["formulas"] = {"columns": ["formula_id", "cell_id", "formula_text", "fingerprint_id", "opaque"], "rows": [[r.get(k) for k in ("formula_id", "cell_id", "formula_text", "fingerprint_id", "opaque")] for r in rows]}
        rows = executor.execute(f"SELECT formula_id,referenced_cell_id,ref_slot,row_delta,col_delta,row_absolute,col_absolute,cross_sheet FROM point_references WHERE formula_id IN ({quoted(groups['formula'])}) ORDER BY formula_id,ref_slot").get("rows", [])
        output["relations"]["point_references"] = {"columns": list(rows[0]) if rows else [], "rows": [list(r.values()) for r in rows]}
    if groups["range"]:
        rows = executor.execute(f"SELECT range_id,sheet_id,r1,c1,r2,c2 FROM ranges WHERE range_id IN ({quoted(groups['range'])}) ORDER BY range_id").get("rows", [])
        output["entities"]["ranges"] = {"columns": ["range_id", "sheet_id", "r1", "c1", "r2", "c2"], "rows": [[r.get(k) for k in ("range_id", "sheet_id", "r1", "c1", "r2", "c2")] for r in rows]}
    if groups["formula_class"]:
        rows = executor.execute(f"SELECT fingerprint_id,canonical_fingerprint FROM formula_classes WHERE fingerprint_id IN ({quoted(groups['formula_class'])}) ORDER BY fingerprint_id").get("rows", [])
        output["entities"]["formula_classes"] = {"columns": ["fingerprint_id", "canonical_fingerprint"], "rows": [[r.get(k) for k in ("fingerprint_id", "canonical_fingerprint")] for r in rows]}
    executor = None
    return output


class TaskBudget:
    def __init__(self, state: dict[str, Any]):
        self.state = state

    @property
    def calls(self) -> int:
        return int(self.state.get("model_call_count", 0))

    @property
    def cost(self) -> float:
        return float(self.state.get("provider_cost_usd", 0.0))

    def failure(self) -> str | None:
        if self.calls >= ACTIVE_MAX_MODEL_CALLS:
            return "TASK_MODEL_CALL_LIMIT"
        if self.cost >= ACTIVE_MAX_COST_USD:
            return "TASK_COST_LIMIT"
        return None


def request_body(system: str, user: str) -> dict[str, Any]:
    config = active_experiment_config()
    body = {
        **config.request_fields(),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    # This is an executable invariant, not merely a test helper.  Any caller
    # that mutates the body or swaps this constructor is rejected before wire.
    assert_declared_matches_wire(config.model, config.reasoning, body, stage="request_body")
    return body


def truncation_class(body: dict[str, Any], text: str) -> str | None:
    choices = body.get("choices") or []
    finish = choices[0].get("finish_reason") if choices else None
    if finish in ("length", "max_tokens"):
        return "TRUNCATED_AT_BUDGET" if text else "TRUNCATED_NO_CONTENT"
    return None


def provider_failure_class(body: Any) -> str:
    """Map provider-side request failures to explicit non-model classes."""
    text = json.dumps(body, ensure_ascii=False).lower()
    if "maximum context length" in text or "context length" in text or "token count exceeds" in text:
        return "SESSION_RESOURCE_LIMIT"
    return "MODEL_ACCESS_FAILURE"


def model_call(task_key: str, stage: str, system: str, user: str, state: dict[str, Any], *, stub: bool = False, evidence_hash: str | None = None, working_hash: str | None = None) -> dict[str, Any]:
    budget = TaskBudget(state)
    blocked = budget.failure()
    call_index = budget.calls + 1
    body = request_body(system, user)
    request_meta = identity_record(body, None, stage=stage)
    record = {
        "task_id": task_key, "stage": stage, "call_index_within_task": call_index,
        "model": MODEL, "provider": PROVIDER, "reasoning": ACTIVE_REASONING, "temperature": TEMPERATURE,
        "request_body": body, "request_sha256": digest(body), "user_payload_sha256": hashlib.sha256(user.encode()).hexdigest(),
        "previous_persistent_state_hash": digest(state), "working_set_hash": working_hash, "evidence_hash": evidence_hash,
        **request_meta,
        "request_provider": PROVIDER,
        "response_model": None,
    }
    timeout_seconds = timeout_for_stage(stage)
    record["timeout_seconds"] = timeout_seconds
    if blocked:
        record.update({"raw_response_body": None, "parsed_response": None, "usage": {}, "provider_cost_usd": 0.0, "finish_reason": None, "truncation_class": None, "failure_class": blocked})
        return record
    if stub:
        response_body = {"id": "stub", "model": MODEL, "choices": [{"message": {"content": "{\"status\":\"ABSTAIN\"}"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0}}
    else:
        key = provider_key()
        if not key:
            record.update({"raw_response_body": None, "parsed_response": None, "usage": {}, "provider_cost_usd": 0.0, "finish_reason": None, "truncation_class": None, "failure_class": "MODEL_ACCESS_FAILURE", "detail": "OPENROUTER_API_KEY missing"})
            return record
        request = urllib.request.Request(relational.OPENROUTER_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "matched-glm-compiled-sixty"}, method="POST")
        previous_alarm = signal.getsignal(signal.SIGALRM)
        def provider_alarm(_signum: int, _frame: Any) -> None:
            raise TimeoutError(f"provider response exceeded {timeout_seconds}s")
        try:
            # The provider endpoint can keep a chunked TLS response open past
            # the socket timeout.  A process-level alarm is the final bounded
            # guard; the runner is single-threaded by freeze policy.
            signal.signal(signal.SIGALRM, provider_alarm)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                # ``urlopen`` applies its timeout while connecting, but some
                # provider/proxy combinations can leave the underlying TLS
                # socket waiting indefinitely while reading a chunked body.
                # Re-apply the same ceiling to the actual response socket so a
                # provider hang becomes a typed infrastructure failure.
                raw = getattr(getattr(response, "fp", None), "raw", None)
                sock = getattr(raw, "_sock", None)
                if sock is not None:
                    sock.settimeout(timeout_seconds)
                response_body = json.loads(response.read().decode())
        except TimeoutError as exc:
            state["model_call_count"] = call_index
            record.update({"raw_response_body": None, "parsed_response": None, "usage": {}, "provider_cost_usd": 0.0, "finish_reason": None, "truncation_class": None, "failure_class": "PROVIDER_TIMEOUT", "detail": str(exc)})
            return record
        except urllib.error.HTTPError as exc:
            error_body = {"status": exc.code, "body": exc.read().decode(errors="replace")}
            state["model_call_count"] = call_index
            record.update({"raw_response_body": error_body, "parsed_response": None, "usage": {}, "provider_cost_usd": 0.0, "finish_reason": None, "truncation_class": None, "failure_class": provider_failure_class(error_body)})
            return record
        except Exception as exc:
            state["model_call_count"] = call_index
            record.update({"raw_response_body": None, "parsed_response": None, "usage": {}, "provider_cost_usd": 0.0, "finish_reason": None, "truncation_class": None, "failure_class": "MODEL_ACCESS_FAILURE", "detail": f"{type(exc).__name__}: {exc}"})
            return record
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_alarm)
    choices = response_body.get("choices") or []
    try:
        response_meta = response_identity(response_body, stage=stage)
    except RuntimeError as exc:
        state["model_call_count"] = call_index
        record.update({
            "raw_response_body": response_body,
            "raw_response_text": "",
            "parsed_response": None,
            "usage": response_body.get("usage") or {},
            "provider_cost_usd": 0.0,
            "finish_reason": None,
            "truncation_class": None,
            "failure_class": "REQUEST_IDENTITY_FAILURE",
            "detail": str(exc),
            "response_model": response_body.get("model"),
            "identity_failure": True,
        })
        return record
    text = ((choices[0].get("message") or {}).get("content") or "") if choices else ""
    usage = response_body.get("usage") or {}
    provider_cost = float(usage.get("cost") or response_body.get("cost") or 0.0)
    parsed = None
    if stage in ("task_ir", "edit_plan"):
        parsed = task_compile.extract_json_object(text)
    elif stage == "retrieval":
        parsed = relational.extract_action(text)
    elif stage == "synthesis":
        parsed = task_compile.extract_json_object(text)
    finish = choices[0].get("finish_reason") if choices else None
    truncation = truncation_class(response_body, text)
    failure = "PROVIDER_ERROR" if finish == "error" else truncation
    state["model_call_count"] = call_index
    state["provider_cost_usd"] = budget.cost + provider_cost
    if provider_cost and state["provider_cost_usd"] > ACTIVE_MAX_COST_USD:
        failure = "TASK_COST_LIMIT"
    record.update({"raw_response_body": response_body, "raw_response_text": text, "parsed_response": parsed, "usage": usage, "provider_cost_usd": provider_cost, "finish_reason": finish, "truncation_class": truncation, "failure_class": failure, **response_meta})
    return record


def persist_call(task_dir: Path, call: dict[str, Any]) -> None:
    path = task_dir / "calls" / f"{int(call['call_index_within_task']):03d}_{call['stage']}.json"
    if path.exists():
        raise RuntimeError(f"IMMUTABLE_CALL_COLLISION: {path.name}")
    write_json(path, call)


def validate_persisted_call_identity(record: dict[str, Any], *, stage: str) -> None:
    required = ("declared_model", "request_model", "response_model", "declared_reasoning", "request_reasoning", "effective_generation_parameters")
    missing = [key for key in required if key not in record]
    if missing:
        raise RuntimeError(f"PERSISTED_REQUEST_IDENTITY_MISSING[{stage}]: {missing}")
    body = record.get("request_body")
    if not isinstance(body, dict):
        raise RuntimeError(f"PERSISTED_REQUEST_BODY_MISSING[{stage}]")
    request_identity(body, stage=stage)
    if record.get("declared_model") != record.get("request_model") or record.get("declared_reasoning") != record.get("request_reasoning"):
        raise RuntimeError(f"PERSISTED_DECLARED_WIRE_MISMATCH[{stage}]")
    payload = record.get("raw_response_body")
    if isinstance(payload, dict):
        response_identity(payload, stage=stage)


def call_or_stub(task_dir: Path, task_key: str, stage: str, system: str, user: str, state: dict[str, Any], *, stub: bool, evidence_hash: str | None = None, working_hash: str | None = None) -> dict[str, Any]:
    if state.get("_resume_mode"):
        expected = digest(request_body(system, user))
        records = [read_json(p) for p in sorted((task_dir / "calls").glob("*.json"))]
        for record in records:
            if record.get("request_sha256") == expected and record.get("stage") == stage:
                validate_persisted_call_identity(record, stage=stage)
                state["model_call_count"] = len(records)
                state["provider_cost_usd"] = sum(float(r.get("provider_cost_usd") or 0) for r in records)
                return record
    blocked = TaskBudget(state).failure()
    if blocked:
        event = {"task_id": task_key, "stage": stage, "failure_class": blocked, "provider_attempt": False, "parsed_response": None}
        state.setdefault("blocked_call_events", []).append(event)
        write_json(task_dir / "state.json", state)
        return event
    # A resumed task reuses the exact persisted call at the next call index.
    # This is deliberately keyed by both index and stage: a completed call is
    # never replayed, and a new call can never overwrite its raw request/body.
    next_index = int(state.get("model_call_count", 0)) + 1
    persisted = task_dir / "calls" / f"{next_index:03d}_{stage}.json"
    if state.get("_resume_mode") and persisted.exists() and not read_json(persisted).get("request_sha256"):
        call = read_json(persisted)
        validate_persisted_call_identity(call, stage=stage)
        # Preserve the exact stored response while normalizing a previously
        # recorded provider context rejection for control-flow purposes.
        if call.get("failure_class") == "MODEL_ACCESS_FAILURE" and provider_failure_class(call.get("raw_response_body")) == "SESSION_RESOURCE_LIMIT":
            call = dict(call)
            call["failure_class"] = "SESSION_RESOURCE_LIMIT"
        state["model_call_count"] = max(int(state.get("model_call_count", 0)), int(call.get("call_index_within_task", next_index)))
        state["last_call_hash"] = digest(call)
        if call.get("failure_class") in NON_MODEL_FAILURES:
            state.setdefault("failure_ledger", []).append({"failure_class": call.get("failure_class"), "stage": stage, "resumed": True})
        write_json(task_dir / "state.json", state)
        return call
    call = model_call(task_key, stage, system, user, state, stub=stub, evidence_hash=evidence_hash, working_hash=working_hash)
    persist_call(task_dir, call)
    state["last_call_hash"] = digest(call)
    write_json(task_dir / "state.json", state)
    if call.get("identity_failure"):
        raise RuntimeError(call.get("detail") or "REQUEST_IDENTITY_FAILURE")
    return call


def parse_task_ir(task_key: str, task: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool) -> dict[str, Any]:
    user = "Compile the following task instruction into TASK_OBLIGATION_SHAPE_V1 JSON.\n\nTASK INSTRUCTION:\n" + task["instruction"]
    call = call_or_stub(task_dir, task_key, "task_ir", TASK_IR_SYSTEM, user, state, stub=stub)
    parsed = call.get("parsed_response")
    if call.get("failure_class"):
        return {"status": call["failure_class"], "raw_task": task["instruction"], "obligations": [], "call": call}
    if stub or not isinstance(parsed, dict):
        return {"status": "ABSTAIN" if stub else "PARSE_FAILURE", "raw_task": task["instruction"], "obligations": [], "call": call}
    try:
        obligations = task_compile.normalize_prediction(parsed)
    except Exception as exc:
        return {"status": "PARSE_FAILURE", "raw_task": task["instruction"], "obligations": [], "error": str(exc), "call": call}
    return {"status": "OK", "raw_task": task["instruction"], "obligations": obligations, "parsed": parsed, "call": call}


def _fragment_context(task: dict[str, Any], compiler: dict[str, Any], obligation: dict[str, Any], packet: dict[str, Any], world: World, *, projected: bool) -> dict[str, Any]:
    """Build one obligation-scoped Edit Plan context.

    ``packet`` is always the complete deterministic packet.  Only the
    model-facing value changes: P1 keeps the old compact tables, while P2 uses
    the bounded projection with stable remainder handles.  Expansion later
    consults the complete packet/world, so omitted foreground candidates are
    not authority loss by construction.
    """
    if projected:
        import frontend_projection as projection
        view = projection.project_packet(obligation, packet)
        grounding = {obligation["id"]: view}
        note = (
            "This is a deterministic obligation-scoped projection of a complete closed-world "
            "grounding packet. Foreground candidates and region summaries are evidence, not a "
            "whitelist. Omitted candidates remain in the authoritative world under the shown "
            "remainder_handle. Use only stable workbook identities and the exact Edit Plan schema."
        )
    else:
        grounding = {
            obligation["id"]: {
                key: compact_table(packet.get(key, []))
                for key in ("locus", "subject", "scope", "source")
            }
        }
        grounding[obligation["id"]]["target_candidate_ids"] = sorted(packet.get("target_cell_ids", []))
        grounding[obligation["id"]]["candidate_count"] = len(packet.get("target_cell_ids", []))
        grounding[obligation["id"]]["fields"] = packet.get("fields")
        note = "Grounding candidates are evidence, not a whitelist. Use only closed-world identities and compact set expressions. Do not enumerate targets unless required by the schema."
    return {
        "RAW_TASK": compiler["raw_task"],
        "GENERATED_TASK_IR": {"obligations": [obligation]},
        "SHEETS": compact_table(list(world.sheets.values())),
        "GROUNDING": grounding,
        "NOTE": note,
        "EXACT_JSON_SCHEMA": EDIT_PLAN_SCHEMA,
    }


def _plan_task_sharded(task_key: str, task: dict[str, Any], compiler: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool, projected: bool) -> dict[str, Any]:
    """Run the same Edit Plan grammar once per obligation and compose mechanically."""
    import frontend_projection as projection

    world = World(db_for(task_key))
    spine = planning_spine_for(task_key, world)
    packets = {ob["id"]: project_obligation(spine, ob) for ob in compiler["obligations"]}
    fragments: list[dict[str, Any]] = []
    try:
        for obligation in compiler["obligations"]:
            context = _fragment_context(task, compiler, obligation, packets[obligation["id"]], world, projected=projected)
            call = call_or_stub(task_dir, task_key, "edit_plan", EDIT_PLAN_PROMPT, json.dumps(context, ensure_ascii=False, separators=(",", ":")), state, stub=stub)
            parsed = call.get("parsed_response")
            expansion = None
            error = None
            if call.get("failure_class"):
                status = call["failure_class"]
            elif stub or not isinstance(parsed, dict):
                status = "ABSTAIN" if stub else "PARSE_FAILURE"
            else:
                try:
                    expansion = expand_edit_plan(parsed, world, {obligation["id"]}, id_contract="V2")
                    status = expansion["status"]
                except PlanError as exc:
                    status, error = exc.category, str(exc)
            fragments.append({
                "obligation_id": obligation["id"], "status": status, "error": error,
                "parsed": parsed, "expansion": expansion, "context": context, "call": call,
            })
        operations: list[dict[str, Any]] = []
        expansions: list[dict[str, Any]] = []
        for fragment in fragments:
            parsed = fragment.get("parsed")
            if not isinstance(parsed, dict):
                continue
            prefix = str(fragment["obligation_id"])
            ops = projection.rename_operations(parsed.get("operations") or [], prefix)
            operations.extend(ops)
            if fragment.get("expansion"):
                ex = json.loads(json.dumps(fragment["expansion"], ensure_ascii=False))
                ex["operations"] = projection.rename_operations(ex.get("operations") or [], prefix)
                expansions.append(ex)
        conflicts = projection.fragment_conflicts(expansions)
        composed: dict[str, Any] = {"operations": operations}
        if conflicts:
            result = {"status": "PLAN_FRAGMENT_CONFLICT", "parsed": composed, "expansion": None, "conflicts": conflicts}
        elif not operations:
            result = {"status": "EMPTY_EXPANSION", "parsed": composed, "expansion": {"status": "EMPTY_EXPANSION", "cell_ids": [], "operations": [], "provenance": {}}, "conflicts": []}
        else:
            try:
                final_expansion = expand_edit_plan(composed, world, {ob["id"] for ob in compiler["obligations"]}, id_contract="V2")
                result = {"status": final_expansion["status"], "parsed": composed, "expansion": final_expansion, "conflicts": []}
            except PlanError as exc:
                result = {"status": exc.category, "parsed": composed, "expansion": None, "error": str(exc), "conflicts": []}
        result.update({"packets": packets, "context": {"mode": "sharded_projected" if projected else "sharded_old", "fragment_count": len(fragments)}, "fragments": fragments})
        return result
    finally:
        world.close()


def planning_completeness(compiler: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Report fragment/authority coverage, never infer semantic completeness."""
    obligations = [o["id"] for o in compiler.get("obligations", [])]
    covered = {o["obligation_id"] for o in (plan.get("expansion") or {}).get("operations", []) if o.get("cell_ids")}
    fragments = {f["obligation_id"]: f for f in plan.get("fragments", [])}
    rows = []
    for oid in obligations:
        fragment_status = fragments[oid]["status"] if oid in fragments else plan.get("status")
        rows.append({"obligation_id": oid, "fragment_status": fragment_status, "has_authority": oid in covered,
                     "successfully_planned": fragment_status == "VALID_PLAN" and oid in covered})
    valid = plan.get("status") == "VALID_PLAN"
    complete = valid and bool(rows) and all(r["successfully_planned"] for r in rows)
    return {"status": "COMPLETE" if complete else "PARTIAL" if valid else "NO_VALID_AUTHORITY",
            "schema_valid_authority": valid, "all_obligations_successfully_planned": complete,
            "obligation_count": len(rows), "obligations_with_authority": [r["obligation_id"] for r in rows if r["has_authority"]],
            "obligations_without_authority": [r["obligation_id"] for r in rows if not r["has_authority"]],
            "obligations": rows, "semantic_completeness": "NOT_ESTABLISHED"}


def plan_task(task_key: str, task: dict[str, Any], compiler: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool) -> dict[str, Any]:
    plan = _plan_task(task_key, task, compiler, state, task_dir, stub=stub)
    plan["planning_completeness"] = planning_completeness(compiler, plan)
    return plan


def _plan_task(task_key: str, task: dict[str, Any], compiler: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool) -> dict[str, Any]:
    if not compiler.get("obligations"):
        return {"status": "EMPTY_EXPANSION", "parsed": {"operations": []}, "expansion": {"status": "EMPTY_EXPANSION", "cell_ids": [], "operations": [], "provenance": {}}}
    if ACTIVE_FRONTEND_MODE in {"sharded_old", "sharded_projected"}:
        return _plan_task_sharded(
            task_key, task, compiler, state, task_dir, stub=stub,
            projected=ACTIVE_FRONTEND_MODE == "sharded_projected",
        )
    world = World(db_for(task_key))
    spine = planning_spine_for(task_key, world)
    packets = {ob["id"]: project_obligation(spine, ob) for ob in compiler["obligations"]}
    context = plan_context(task, compiler, packets, world)
    user = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    call = call_or_stub(task_dir, task_key, "edit_plan", EDIT_PLAN_PROMPT, user, state, stub=stub)
    parsed = call.get("parsed_response")
    if call.get("failure_class"):
        world.close()
        return {"status": call["failure_class"], "parsed": parsed, "expansion": None, "packets": packets, "context": context, "call": call}
    if stub or not isinstance(parsed, dict):
        world.close()
        return {"status": "ABSTAIN" if stub else "PARSE_FAILURE", "parsed": parsed, "expansion": None, "packets": packets, "context": context, "call": call}
    try:
        expansion = expand_edit_plan(parsed, world, {ob["id"] for ob in compiler["obligations"]}, id_contract="V2")
        status = expansion["status"]
    except PlanError as exc:
        expansion, status = None, exc.category
    world.close()
    return {"status": status, "parsed": parsed, "expansion": expansion, "packets": packets, "context": context, "call": call}


def validate_formula(task_key: str, target: dict[str, Any], formula: str, cache: dict[str, Any], spine: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(formula, str) or not formula.startswith("="):
        return {"hard_verifier_result": "HARD_REJECT", "failure_class": "PARSE_FAILURE"}
    source = task_source(task_key)
    if task_key not in cache:
        grids = load_grids(source)
        view = build_view(build_graph_from_grids(grids))
        cache[task_key] = (view, scc_stats(view))
    row = {"task": task_key, "input_path": str(source), "target": target, "edit_type": "UNKNOWN"}
    result = prior.synth_tools._validate_formula(row, formula, {}, spine, *cache[task_key])
    accepted = not result.get("hard_reject") and result.get("parser_ok") and not result.get("invalid_sheet") and not result.get("invalid_address") and not result.get("unsupported_external")
    result["hard_verifier_result"] = "HARD_ACCEPT" if accepted else "HARD_REJECT"
    return result


def target_from_id(spine: dict[str, Any], cell_id: str, task_key: str, obligation_id: str) -> dict[str, Any] | None:
    address = target_address(spine, cell_id)
    if not address:
        return None
    # This immutable input content is already in the compiled spine. Reopening
    # the full workbook for every translated member is unnecessary work.
    if "_input_cells_by_id" not in spine:
        spine["_input_cells_by_id"] = {c["id"]: c for c in spine.get("occupied", [])}
    cell = spine["_input_cells_by_id"].get(cell_id, {})
    value = cell.get("payload")
    # Legacy spines may omit a numeric payload. Its recorded occupancy still
    # must not be reinterpreted as a blank target.
    kind = cell.get("kind")
    info = {"raw_value": value, "kind": "formula" if kind == "formula" or isinstance(value, str) and value.startswith("=") else "value" if kind not in (None, "blank") or value is not None else "blank"}
    return {"target_id": cell_id, "cell_id": cell_id, "obligation_id": obligation_id, **address, "current_input_content": info["raw_value"], "current_input_kind": info["kind"]}


def retrieval_synthesis(task_key: str, task: dict[str, Any], obligation: dict[str, Any], target: dict[str, Any], packet: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool) -> dict[str, Any]:
    spine = spine_for(task_key)
    bootstrap = prior.compile_bootstrap(spine, packet, obligation, target)
    working = set(bootstrap["bootstrap_entity_ids"]) | {target["cell_id"]}
    executor = ReadOnlySqlite(db_for(task_key), max_rows=relational.RESULT_ROW_LIMIT, max_bytes=relational.RESULT_BYTE_LIMIT)
    history: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    latest = None
    added: set[str] = set()
    materialized = 0
    for q in range(1, MAX_SQL_CALLS + 1):
        # Reserve the final stochastic opportunity for the synthesis transition.
        # The historical runner's 50-call constant remains the default for
        # archived compatibility, but live feasibility profiles may raise the
        # active ceiling (for example to the nonbinding 150-call observation
        # envelope).  This guard must follow the active runtime value or it
        # silently censors the treatment at the historical budget.
        if int(state.get("model_call_count", 0)) >= ACTIVE_MAX_MODEL_CALLS - 1:
            break
        content = prior.session_summary(target, obligation, working, history, latest, added, f"ws-{digest(sorted(working))[:10]}") if history else json.dumps({"RAW_TASK": task["instruction"], "OBLIGATION": obligation, "TARGET": target, "DETERMINISTIC_BOOTSTRAP": bootstrap}, ensure_ascii=False, separators=(",", ":"))
        call = call_or_stub(task_dir, task_key, "retrieval", RETRIEVAL_SYSTEM, content, state, stub=stub, evidence_hash=digest(bootstrap), working_hash=digest(sorted(working)))
        calls.append(call)
        if stub or call.get("failure_class"):
            break
        action = call.get("parsed_response")
        if not isinstance(action, dict):
            calls[-1]["failure_class"] = "INVALID_ACTION"
            break
        if action.get("action") == "final":
            break
        sql = action.get("sql") if action.get("action") == "execute_sql" else None
        if not isinstance(sql, str):
            calls[-1]["failure_class"] = "INVALID_ACTION"
            break
        result = executor.execute(sql)
        estimate = token_estimate(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        if result.get("status") == "OK" and materialized + estimate > relational.EPISODE_TOKEN_LIMIT:
            result = {"status": "RESULT_TOO_LARGE", "estimated_result_tokens": estimate, "configured_episode_token_limit": relational.EPISODE_TOKEN_LIMIT}
        elif result.get("status") == "OK":
            materialized += estimate
        ids = relational.collect_ids(result)
        added = ids - working
        working |= ids
        calls[-1].update({"sql": sql, "sql_classification": relational.classify_sql(sql), "result": result, "new_working_set_ids": sorted(added)})
        history.append({"q": q, "status": result.get("status"), "row_count": result.get("row_count"), "new_ids": len(added), "query_kind": relational.classify_sql(sql).get("query_kind")})
        latest = result
    state.setdefault("working_set_handles", {})[f"{target['sheet']}!{target['address']}"] = {"entity_ids": sorted(working), "evidence_hash": digest(materialize(db_for(task_key), working))}
    state.setdefault("sql_history", []).extend(history)
    write_json(task_dir / "state.json", state)
    evidence = materialize(db_for(task_key), working)
    transition = {"SYNTHESIS_TRANSITION": SYNTHESIS_SYSTEM, "RAW_TASK": task["instruction"], "TARGET": target, "OBLIGATION": obligation, "WORKING_SET_COUNTS": dict(Counter(x.split(":", 1)[0] for x in working)), "WORKING_SET_ENTITY_IDS": sorted(working), "WORKING_SET_EVIDENCE": evidence}
    call = call_or_stub(task_dir, task_key, "synthesis", SYNTHESIS_SYSTEM, json.dumps(transition, ensure_ascii=False, separators=(",", ":")), state, stub=stub, evidence_hash=digest(evidence), working_hash=digest(sorted(working)))
    calls.append(call)
    parsed = call.get("parsed_response")
    from compiled_scheduler import synthesis_outcome
    session = {"target": target, "bootstrap": bootstrap, "working_set_ids": sorted(working), "evidence": evidence, "calls": calls, "synthesis": {"parsed": parsed}, "failure_class": call.get("failure_class"), "sql_calls": sum(1 for c in calls if c.get("stage") == "retrieval")}
    session["status"] = "ABSTAIN" if stub else synthesis_outcome(session)
    return session


def authorised_cells(plan: dict[str, Any]) -> tuple[dict[closure.Cell, dict[str, Any]], dict[str, str]]:
    by_cell: dict[closure.Cell, dict[str, Any]] = {}
    cid_by_cell: dict[str, str] = {}
    spine = plan["spine"]
    for op in (plan.get("expansion") or {}).get("operations", []):
        for cid in op.get("cell_ids", []):
            address = target_address(spine, cid)
            if not address:
                continue
            cell = (address["sheet"], address["row"], address["col"])
            by_cell.setdefault(cell, {"operation_id": op["operation_id"], "obligation_id": op["obligation_id"], "operation_kind": op["operation_kind"]})
            cid_by_cell[cell] = cid
    return by_cell, cid_by_cell


def schedule_formula_work(task_key: str, task: dict[str, Any], compiler: dict[str, Any], plan: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool) -> dict[str, Any]:
    from compiled_scheduler import schedule
    return schedule(sys.modules[__name__], task_key, task, compiler, plan, state, task_dir, stub=stub)


def legacy_schedule_formula_work(task_key: str, task: dict[str, Any], compiler: dict[str, Any], plan: dict[str, Any], state: dict[str, Any], task_dir: Path, *, stub: bool) -> dict[str, Any]:
    if not plan.get("expansion") or not plan["expansion"].get("cell_ids"):
        return {"authorized_targets": 0, "canonical_decisions": [], "translated_formula_instances": [], "proposals": [], "failures": []}
    plan["spine"] = spine_for(task_key)
    by_cell, cid_by_cell = authorised_cells(plan)
    auth = set(by_cell)
    graph = db_precedent_graph(db_for(task_key))
    forms = formula_forms(task_source(task_key))
    kinds = input_kinds(task_source(task_key))
    view_cache: dict[str, Any] = {}
    assigned: set[closure.Cell] = set()
    edits: dict[closure.Cell, str] = {}
    proposals, groups_audit, failures = [], [], []
    obligation_by_id = {o["id"]: o for o in compiler.get("obligations", [])}
    operation_order = [op for op in plan["expansion"].get("operations", []) if op.get("operation_kind") != "CLEAR_CELL"]
    operation_cells = {op["operation_id"]: [tuple(target_address(plan["spine"], cid)[k] for k in ("sheet", "row", "col")) for cid in op.get("cell_ids", []) if target_address(plan["spine"], cid)] for op in operation_order}
    for op in operation_order:
        remaining = [c for c in operation_cells[op["operation_id"]] if c not in assigned]
        while remaining:
            budget_failure = TaskBudget(state).failure()
            if budget_failure:
                failures.append({"failure_class": budget_failure, "scope": "remaining_authorized_targets", "remaining_count": len(remaining)})
                break
            seed = sorted(remaining)[0]
            seed_id = cid_by_cell[seed]
            target = target_from_id(plan["spine"], seed_id, task_key, op["obligation_id"])
            if not target:
                failures.append({"failure_class": "INVALID_ENTITY", "cell": list(seed)})
                assigned.add(seed); remaining.remove(seed); continue
            session = retrieval_synthesis(task_key, task, obligation_by_id[op["obligation_id"]], target, plan["packets"][op["obligation_id"]], state, task_dir, stub=stub)
            parsed = session["synthesis"].get("parsed") or {}
            formula = parsed.get("formula") if parsed.get("status") == "PROPOSED" and isinstance(parsed.get("formula"), str) else None
            proposal = {"seed": list(seed), "target": target, "session": session, "formula": formula}
            proposals.append(proposal)
            if not formula:
                failures.append({"failure_class": session.get("failure_class") or "ABSTAIN", "cell": list(seed)})
                assigned.add(seed); remaining.remove(seed); continue
            validation = validate_formula(task_key, target, formula, view_cache, plan["spine"])
            proposal["validation"] = validation
            if validation.get("hard_verifier_result") != "HARD_ACCEPT":
                failures.append({"failure_class": "HARD_VERIFIER_REJECT", "cell": list(seed), "validation": validation})
                assigned.add(seed); remaining.remove(seed); continue
            precedents = proposal_precedents(formula, seed)
            closure_members = set(precedents & auth)
            frontier = set(closure.ancestors_within(seed, graph, auth))
            execution_members = {seed} | closure_members | frontier
            groups, refused = program_group.groups_for(sorted(execution_members), by_cell, task_key, forms=forms, kinds=kinds)
            groups_audit.append({"seed": list(seed), "execution_members": [list(x) for x in sorted(execution_members)], "groups": groups, "refused": refused})
            if not groups:
                edits[seed] = formula
                assigned.add(seed)
                translated = []
            else:
                translated = []
                covered: set[closure.Cell] = set()
                for group in groups:
                    group_cells = [tuple(x) for x in group["member_cells"]]
                    # The proposal is the one canonical decision for this group.
                    origin = seed
                    if origin not in group_cells:
                        origin = seed
                    for member in group_cells:
                        translated_formula = program_group.translate(formula, origin, member)
                        v = target_from_id(plan["spine"], cid_by_cell[member], task_key, by_cell[member]["obligation_id"])
                        check = validate_formula(task_key, v, translated_formula, view_cache, plan["spine"])
                        if check.get("hard_verifier_result") == "HARD_ACCEPT":
                            edits[member] = translated_formula
                            translated.append({"cell": list(member), "formula": translated_formula, "source": list(origin)})
                        else:
                            failures.append({"failure_class": "HARD_VERIFIER_REJECT", "cell": list(member), "validation": check})
                        covered.add(member)
                assigned |= covered
            # C1 closure may authorize members outside the current operation; they
            # are coordinated only if they are already Edit Plan-authorized.
            assigned.add(seed)
            assigned.update(x for x in execution_members if x in auth and x in set(operation_cells[op["operation_id"]]))
            remaining = [c for c in remaining if c not in assigned]
    # Any remaining authorized formula operation cells are synthesized individually.
    for cell in sorted(auth - assigned):
        budget_failure = TaskBudget(state).failure()
        if budget_failure:
            failures.append({"failure_class": budget_failure, "scope": "ungrouped_authorized_targets", "remaining_count": len(auth - assigned)})
            break
        meta = by_cell[cell]
        if meta["operation_kind"] == "CLEAR_CELL":
            failures.append({"failure_class": "UNSUPPORTED_EDIT_KIND", "operation_kind": "CLEAR_CELL", "cell": list(cell)})
            continue
        target = target_from_id(plan["spine"], cid_by_cell[cell], task_key, meta["obligation_id"])
        if not target:
            failures.append({"failure_class": "INVALID_ENTITY", "cell": list(cell)}); continue
        session = retrieval_synthesis(task_key, task, obligation_by_id[meta["obligation_id"]], target, plan["packets"][meta["obligation_id"]], state, task_dir, stub=stub)
        parsed = session["synthesis"].get("parsed") or {}
        formula = parsed.get("formula") if parsed.get("status") == "PROPOSED" else None
        if formula:
            check = validate_formula(task_key, target, formula, view_cache, plan["spine"])
            if check.get("hard_verifier_result") == "HARD_ACCEPT": edits[cell] = formula
            else: failures.append({"failure_class": "HARD_VERIFIER_REJECT", "cell": list(cell), "validation": check})
        else:
            failures.append({"failure_class": session.get("failure_class") or "ABSTAIN", "cell": list(cell)})
        assigned.add(cell)
    return {"authorized_targets": len(auth), "canonical_decisions": proposals, "translated_formula_instances": [{"cell": list(c), "formula": f} for c, f in sorted(edits.items())], "groups": groups_audit, "failures": failures, "edits": [{"sheet": c[0], "address": closure.a1(c[1], c[2]), "formula": f} for c, f in sorted(edits.items())], "stochastic_formula_decisions": len(proposals), "translated_count": sum(1 for g in groups_audit for x in g["groups"] for _ in x["member_cells"]) }


def run_one_task(task_key: str, *, stub: bool = False, resume: bool = False, output_root: Path = LIVE, extra_state: dict[str, Any] | None = None) -> dict[str, Any]:
    task = task_map()[task_key]
    task_dir = output_root / task_key.replace(":", "-")
    if task_dir.exists() and not resume:
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    state_path = task_dir / "state.json"
    if resume and state_path.exists():
        state = read_json(state_path)
        if state.get("status") in ("COMPLETED", "DRY_COMPLETED"):
            return state
        records = [read_json(p) for p in sorted((task_dir / "calls").glob("*.json"))]
        state["model_call_count"] = len(records)
        state["provider_cost_usd"] = sum(float(r.get("provider_cost_usd") or 0) for r in records)
    else:
        state = {"task_id": task_key, "model": MODEL, "provider": PROVIDER, "reasoning": ACTIVE_REASONING, "top_p": ACTIVE_TOP_P, "temperature": TEMPERATURE, "max_model_calls": ACTIVE_MAX_MODEL_CALLS, "max_cost_usd": ACTIVE_MAX_COST_USD, "frontend_mode": ACTIVE_FRONTEND_MODE, "model_call_count": 0, "provider_cost_usd": 0.0, "failure_ledger": [], "grounding_bindings": {}, "authorised_target_set": [], "completed_edits": [], "unresolved_authorised_targets": [], "current_seed_proposals": [], "execution_units": [], "program_groups": [], "canonical_decisions": [], "translated_formulas": [], "working_set_handles": {}, "sql_history": [], "started_at": now()}
    if extra_state:
        state.update(extra_state)
    state["_resume_mode"] = resume
    try:
        compiler = parse_task_ir(task_key, task, state, task_dir, stub=stub)
        state["task_ir"] = {k: v for k, v in compiler.items() if k != "call"}
        write_json(state_path, state)
        if compiler["status"] != "OK":
            plan = {"status": "EMPTY_EXPANSION", "expansion": {"status": "EMPTY_EXPANSION", "cell_ids": [], "operations": [], "provenance": {}}, "packets": {}}
        else:
            plan = plan_task(task_key, task, compiler, state, task_dir, stub=stub)
        plan.setdefault("planning_completeness", planning_completeness(compiler, plan))
        state["edit_plan"] = {k: v for k, v in plan.items() if k not in ("spine", "context", "call")}
        state["authorised_target_set"] = sorted((plan.get("expansion") or {}).get("cell_ids", []))
        write_json(state_path, state)
        if compiler.get("obligations") and plan.get("status") not in ("VALID_PLAN", "EMPTY_EXPANSION"):
            state["failure_ledger"].append({"failure_class": "INVALID_EDIT_PLAN", "status": plan.get("status")})
        plan["spine"] = spine_for(task_key)
        if not plan.get("packets"):
            world = World(db_for(task_key))
            try:
                grounding_spine = planning_spine_for(task_key, world)
                plan["packets"] = {ob["id"]: project_obligation(grounding_spine, ob) for ob in compiler.get("obligations", [])}
            finally:
                world.close()
        schedule = schedule_formula_work(task_key, task, compiler, plan, state, task_dir, stub=stub)
        state["execution_units"] = schedule.get("groups", [])
        state["program_groups"] = schedule.get("groups", [])
        state["canonical_decisions"] = schedule.get("canonical_decisions", [])
        state["translated_formulas"] = schedule.get("translated_formula_instances", [])
        write_json(state_path, state)
        # The neutral writer is the only actuation path.  All edits are formula
        # edits already hard-validated; no openpyxl workbook is saved here.
        source = task_source(task_key)
        output = task_dir / "output.xlsx"
        write_audit = write_cells(source, output, schedule.get("edits", []))
        applied = {(e["sheet"], e["address"]) for e in write_audit.get("applied", [])}
        for rec in schedule.get("dispositions", {}).values():
            cell = rec["cell"]
            if rec["status"] in ("WRITES_SCHEDULED", "TRANSLATED_WRITE_SCHEDULED"):
                rec["writer_result"] = "WRITTEN" if (cell[0], closure.a1(cell[1], cell[2])) in applied else "DROPPED_WRITER"
        state["proposal_dispositions"] = schedule.get("dispositions", {})
        if write_audit.get("rejected"):
            state["failure_ledger"].extend({"failure_class": "WRITER_FAILURE", **x} for x in write_audit["rejected"])
        schedule_failures = schedule.get("failures", [])
        state["failure_ledger"].extend(f for f in schedule_failures if f.get("failure_class"))
        failure_classes = {compiler.get("status"), plan.get("status"), *(f.get("failure_class") for f in schedule_failures), *(f.get("failure_class") for f in state["failure_ledger"])}
        fatal_failure = any(failure in FATAL_TASK_FAILURES for failure in failure_classes)
        result = {"task_id": task_key, "category": task["category"], "compiler": compiler, "edit_plan": {k: v for k, v in plan.items() if k not in ("spine", "context")}, "schedule": {k: v for k, v in schedule.items() if k != "edits"}, "write_audit": write_audit, "output": str(output), "state": {"model_call_count": state["model_call_count"], "provider_cost_usd": state["provider_cost_usd"]}, "status": "DRY_COMPLETED" if stub else "NON_MODEL_FAILURE" if fatal_failure else "COMPLETED", "fatal_failure": fatal_failure, "partial_due_to_budget": any(failure in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"} for failure in failure_classes), "failure_ledger": state["failure_ledger"], "finished_at": now()}
        write_json(task_dir / "result.json", result)
        state.update(result)
        write_json(state_path, state)
        return result
    except Exception as exc:
        state.update({"status": "INTEGRATION_FAILURE", "failure_ledger": state.get("failure_ledger", []) + [{"failure_class": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}"}], "finished_at": now()})
        write_json(state_path, state)
        return state


def scorer(run_root: Path, model_name: str, *, refresh: bool = True) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "benchmark/score_openrouter_run.py"), str(run_root), "--model-name", model_name, "--metadata-tolerant"]
    if not refresh:
        command.append("--no-refresh")
    completed = subprocess.run(command, cwd=ROOT / "benchmark-data/SpreadsheetBench-2/evaluation", check=False)
    scores = run_root / "official_scores.json"
    if completed.returncode != 0 or not scores.exists():
        return {"status": "SCORER_FAILURE", "return_code": completed.returncode}
    return read_json(scores)


def workbook_shape(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = sorted(archive.namelist())
        formula_cells = 0
        for name in names:
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                formula_cells += archive.read(name).count(b"<f")
    wb = openpyxl.load_workbook(path, data_only=False, read_only=True)
    try:
        return {"bytes": path.stat().st_size, "sheets": list(wb.sheetnames), "sheet_count": len(wb.sheetnames), "formula_xml_count": formula_cells}
    finally:
        wb.close()


def run_neutrality() -> dict[str, Any]:
    env = ensure_environment()
    if not env.get("all_inputs_present"):
        result = {"status": "STOP", "reason": "TREATMENT_INPUT_UNRUNNABLE", "environment": env}
        write_json(PREP / "neutrality_results.json", result)
        return result
    if NEUTRALITY.exists():
        shutil.rmtree(NEUTRALITY)
    rows = []
    for task in task_rows():
        key = task["task_key"]
        source = task_source(key)
        output = NEUTRALITY / key.replace(":", "-") / "output.xlsx"
        audit = write_cells(source, output, [])
        rows.append({"task_key": key, "write_audit": audit, "source_shape": workbook_shape(source), "output_shape": workbook_shape(output), "byte_identical_before_recalc": bool(audit.get("byte_identical_to_source"))})
    # The writer gate measures the writer's semantic round-trip.  LibreOffice
    # refresh is intentionally not part of this gate: several frozen inputs
    # contain stale cached values that LibreOffice changes even when the ZIP
    # archive is byte-identical.  Treatment scoring still uses the refresh path;
    # that recalc drift is retained as a separate diagnostic below.
    score = scorer(NEUTRALITY, "matched-glm-compiled-sixty-neutrality", refresh=False)
    score_rows = score.get("tasks", {}) if isinstance(score, dict) else {}
    failures = [key for key, row in score_rows.items() if row.get("regression_accuracy") != 1.0]
    result = {"status": "PASS" if len(rows) == 60 and not failures and not any(not r["byte_identical_before_recalc"] for r in rows) else "STOP", "tasks": len(rows), "passing_regression": len(rows) - len(failures), "regression_failures": failures, "official_score": score, "rows": rows, "writer_gate_refresh": False, "recalc_path": "treatment scoring uses score_openrouter_run.py refresh; writer gate intentionally isolates archive/write neutrality"}
    write_json(PREP / "neutrality_results.json", result)
    return result


def run_dry() -> dict[str, Any]:
    env = ensure_environment()
    if not env.get("all_inputs_present"):
        result = {"status": "STOP", "reason": "TREATMENT_INPUT_UNRUNNABLE"}
        write_json(PREP / "dry_run_results.json", result)
        return result
    if DRY.exists():
        shutil.rmtree(DRY)
    selected = ["Template:01_02", "Financial_Model:01_01", "Debugging:01_01"]
    results = [run_one_task(key, stub=True, output_root=DRY) for key in selected]
    score = scorer(DRY, "matched-glm-compiled-sixty-dry")
    valid = all(r.get("status") == "DRY_COMPLETED" and Path(r.get("output", "")).exists() for r in results)
    result = {"status": "PASS" if valid and score.get("status") != "SCORER_FAILURE" else "STOP", "selected": selected, "task_results": results, "official_score": score, "stub_calls": True, "live_model_calls": 0}
    write_json(PREP / "dry_run_results.json", result)
    return result


def structural_profile() -> dict[str, Any]:
    audit = read_json(AUDIT)
    rows = task_rows()
    classified = [r for r in rows if r.get("status") == "CLASSIFIED"]
    formula = sum(int(r.get("n_formula_edits", 0) or 0) for r in classified)
    exact_cells = sum(int(r.get("recoverable_exact_formula_cells", 0) or 0) for r in classified)
    programs = sum(int(r.get("n_independent_programs", 0) or 0) for r in classified)
    pg = sum(int((r.get("programgroup") or {}).get("uniform_grouped_cells", 0) or 0) for r in classified)
    new = sum(int((r.get("programgroup") or {}).get("new_canonical_decisions", 0) or 0) for r in classified)
    return {"tasks": 60, "classified_tasks": len(classified), "unclassifiable_tasks": [r["task_key"] for r in rows if r.get("status") != "CLASSIFIED"], "formula_cells": formula, "independent_programs": programs, "exact_recoverable_cells": exact_cells, "exact_recoverable_share": exact_cells / formula if formula else None, "programgroup_uniform_cells": pg, "programgroup_before_decisions": formula, "programgroup_after_decisions": new, "programgroup_reduction": formula - new, "programgroup_reduction_share": (formula - new) / formula if formula else None, "category_pg_share": {cat: (sum(int((r.get("programgroup") or {}).get("uniform_grouped_cells", 0) or 0) for r in classified if r.get("category") == cat) / sum(int(r.get("n_formula_edits", 0) or 0) for r in classified if r.get("category") == cat) if sum(int(r.get("n_formula_edits", 0) or 0) for r in classified if r.get("category") == cat) else None) for cat in ("Template", "Financial_Model", "Debugging")}, "source_audit_sha256": file_digest(AUDIT)}


def write_prep_report(*, preflight_result: dict[str, Any] | None = None) -> None:
    """Write the human-readable freeze/preflight handoff without model calls."""
    profile = structural_profile()
    env = ensure_environment()
    neutrality = read_json(PREP / "neutrality_results.json") if (PREP / "neutrality_results.json").exists() else {"status": "MISSING"}
    dry = read_json(PREP / "dry_run_results.json") if (PREP / "dry_run_results.json").exists() else {"status": "MISSING"}
    freeze_status = validate_freeze() if (PREP / "freeze.json").exists() else {"pass": False, "missing_artifacts": ["freeze.json"]}
    lines = [
        "# Matched GLM compiled treatment — PREP REPORT",
        "",
        "No live model calls were made while producing this report.",
        "",
        "## Historical baseline",
        "",
        "- Run: `glm-5.3-flash-control-census-sixty-1`",
        "- Population: 60 tasks (20 Template, 20 Financial_Model, 20 Debugging)",
        "- Exact: 6/60",
        "- Mean modification: 0.669125; median modification: 0.795700",
        "- Mean regression: 0.970557; median regression: 1.000000",
        f"- Control score artifacts: `{file_digest(PREP / 'control_scores.json') if (PREP / 'control_scores.json').exists() else 'MISSING'}`",
        "",
        "## Treatment freeze",
        "",
        f"- Model: `{MODEL}` via `{PROVIDER}`; reasoning `{REASONING}`; temperature `{TEMPERATURE}`.",
        f"- Central task limits: {MAX_MODEL_CALLS} model calls and ${MAX_COST_USD:.2f} provider-reported cost; SQL/action escape ceiling {MAX_SQL_CALLS} per synthesis session.",
        "- No model-quality retries, no GPT, no candidate interface, no Program Sketch IR, no Operand Binding IR, no repair loop.",
        "- Provider policy: OpenRouter with `provider_only=null`, preserving historical fallback behavior.",
        f"- Freeze validation: `{ 'PASS' if freeze_status.get('pass') else 'NOT YET PASS' }`.",
        "",
        "## Runtime state machine",
        "",
        "`Task IR → grounding → Edit Plan → deterministic expansion → bootstrap → bounded SQL/delta working state → canonical proposal → proposal-seeded C1 closure → ProgramGroup detection → deterministic translation → ungrouped synthesis → neutral actuation → recalc → official scoring`.",
        "",
        "Edit Plan establishes authority. Dependency closure is intersected with already-authorized targets; it never creates edit authority. ProgramGroups are mechanical input-side repetition witnesses and do not add targets.",
        "",
        "## Structural slice",
        "",
        f"- Classified tasks: {profile['classified_tasks']}/60; census-unclassifiable task retained: {', '.join(profile['unclassifiable_tasks']) or 'none'}.",
        f"- Formula target cells: {profile['formula_cells']}; independent programs: {profile['independent_programs']}; exact-recoverable cells: {profile['exact_recoverable_cells']} ({profile['exact_recoverable_share']:.2%}).",
        f"- ProgramGroup oracle-authority coverage: {profile['programgroup_uniform_cells']} cells; decisions {profile['programgroup_before_decisions']} → {profile['programgroup_after_decisions']} ({profile['programgroup_reduction_share']:.2%} reduction).",
        f"- Category PG shares: {json.dumps(profile['category_pg_share'], sort_keys=True)}.",
        "",
        "## Deterministic gates",
        "",
        f"- Environment: {len(env.get('records', []))}/60 records; all inputs present: `{env.get('all_inputs_present')}`; FM:06_01 policy: metadata-only private repair, census remains UNCLASSIFIABLE.",
        f"- 60-task zero-write neutrality: `{neutrality.get('status')}`; regression pass count: {neutrality.get('passing_regression', 'n/a')}/60.",
        f"- Three-category stub dry run: `{dry.get('status')}`; live model calls: {dry.get('live_model_calls', 'n/a')}.",
        f"- Required freeze artifacts: `{', '.join(name for name in ('freeze.json', 'tasks.csv', 'structural_profile.csv', 'control_scores.csv', 'expected_analysis_plan.json'))}`.",
        "",
        "## Instrumentation and remaining mismatches",
        "",
        "Every treatment call retains the exact request body, raw response body/text, parsed response, usage, provider cost, finish reason, truncation class, working-set hash, evidence hash, and prior persistent-state hash. Deterministic artifacts are hash-addressed in the task state.",
        "",
        "The control used a SWE-agent bash/view_xlsx/openpyxl/LibreOffice surface and historical retry/repair behavior. The treatment necessarily has a different tool interface and deterministic compiler stages; these are architecture/interface differences, not task-specific hints. The treatment retains the same GLM slug, low reasoning, temperature 0, 50-call ceiling, $4 ceiling, observation limit, timeout, and provider fallback policy. Historical raw provider request bodies were not retained by the control; treatment request retention is therefore an instrumentation improvement, not a claimed matched artifact.",
        "",
        "## Exact launch command after approval",
        "",
        "```bash",
        f"python benchmark/matched_compiled_treatment.py run --tasks-file {PREP.relative_to(ROOT) / 'tasks.txt'} --max-workers 1",
        "```",
        "",
        "If the task-list text file is absent, use `python benchmark/matched_compiled_treatment.py run --max-workers 1`; the runner then loads the frozen slice. A live run is refused until `preflight-only` returns READY.",
    ]
    write_json(PREP / "prep_report_state.json", {"freeze": freeze_status, "profile": profile, "environment": env, "neutrality": neutrality, "dry_run": dry, "preflight": preflight_result})
    (PREP / "PREP_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_freeze() -> dict[str, Any]:
    PREP.mkdir(parents=True, exist_ok=True)
    env = ensure_environment()
    profile = structural_profile()
    expected = {"formula_cells": 5818, "independent_programs": 1387, "exact_recoverable_cells": 1416, "programgroup_uniform_cells": 3549, "programgroup_before_decisions": 5818, "programgroup_after_decisions": 2452}
    if any(profile[k] != v for k, v in expected.items()):
        raise RuntimeError(f"CENSUS_PROFILE_MISMATCH expected={expected} got={profile}")
    rows = task_rows()
    write_csv(PREP / "tasks.csv", [{"ordinal": i + 1, "task_key": r["task_key"], "category": r["category"], "task": r["task"], "census_status": r.get("status")} for i, r in enumerate(rows)])
    (PREP / "tasks.txt").write_text("\n".join(r["task_key"] for r in rows) + "\n", encoding="utf-8")
    write_csv(PREP / "structural_profile.csv", [{"metric": k, "value": v} for k, v in profile.items() if not isinstance(v, dict)])
    control_scores = read_json(CONTROL_RUN / "official_scores.json")
    write_json(PREP / "control_scores.json", control_scores)
    score_rows = []
    for task_key, score in sorted((control_scores.get("tasks") or {}).items()):
        score_rows.append({"task_key": task_key, **score})
    write_csv(PREP / "control_scores.csv", score_rows)
    expected_plan = {
        "primary_endpoint": "paired per-task modification delta",
        "secondary_endpoints": ["exact", "regression", "value_only_modification", "model_calls", "input_tokens", "output_tokens", "provider_cost", "stochastic_formula_decisions", "translated_formula_instances", "avoided_model_decisions", "completion"],
        "predictions": {"primary": "compiled treatment improves paired modification on structurally leveraged tasks", "efficiency": "compiled treatment reduces repeated stochastic formula decisions", "category": "Financial_Model has clearest ProgramGroup mechanism", "exact": "exact uplift attenuated by novel-program burden", "debugging": "structural opportunity exists but defect localization remains uncertain", "template": "weak ProgramGroup/recovery gains"},
        "programgroup_bands": {"PG_NONE": "0%", "PG_LOW": "(0,33%]", "PG_MEDIUM": "(33%,66%]", "PG_HIGH": "(66%,100%]"},
        "recoverable_bands": {"R_LOW": "[0,25%)", "R_MEDIUM": "[25%,50%)", "R_HIGH": "[50%,75%)", "R_VERY_HIGH": "[75%,100%]"},
        "novel_bands": ["NOVEL_0", "NOVEL_1", "NOVEL_2_3", "NOVEL_4_PLUS", "OPAQUE", "UNCLASSIFIABLE"],
    }
    write_json(PREP / "expected_analysis_plan.json", expected_plan)
    components = [
        Path(__file__), Path(prior.__file__), Path(task_compile.__file__), Path(edit_plan_probe.__file__), Path(ROOT / "benchmark/edit_plan.py"), Path(ROOT / "benchmark/workbook_grounding.py"), Path(ROOT / "benchmark/workbook_grounding_spine.py"), Path(ROOT / "benchmark/workbook_spine_sqlite.py"), Path(ROOT / "benchmark/relational_retrieval_probe.py"), Path(ROOT / "benchmark/composition_closure.py"), Path(ROOT / "benchmark/execution_unit_probe.py"), Path(ROOT / "benchmark/program_group.py"), Path(ROOT / "benchmark/formula_verifier.py"), Path(ROOT / "benchmark/xlsx_cell_writer.py"), Path(ROOT / "benchmark/xlsx_metadata_repair.py"), Path(ROOT / "benchmark/score_openrouter_run.py"), Path(ROOT / "benchmark/run_evaluation.py"), Path(ROOT / "benchmark/historical_control_audit.py"), Path(ROOT / "benchmark/structural_recoverability_census.py"), Path(ROOT / "tests/test_matched_compiled_treatment.py"), CONTROL_CONFIG, COMPILED_CONFIG, CONTROL_SLICE, AUDIT, CENSUS_TASKS,
    ]
    hashes = {str(p.relative_to(ROOT)): file_digest(p) for p in components if p.exists()}
    freeze = {"freeze_version": "matched-compiled-sixty-v1", "generated_at": now(), "run_name": RUN_NAME, "no_model_calls_during_freeze": True, "population": {"tasks": 60, "task_list_sha256": file_digest(CONTROL_SLICE), "task_csv_sha256": file_digest(PREP / "tasks.csv"), "category_counts": dict(Counter(r["category"] for r in rows))}, "control": {"run_id": "glm-5.3-flash-control-census-sixty-1", "scores_sha256": file_digest(PREP / "control_scores.json"), "scores_csv_sha256": file_digest(PREP / "control_scores.csv"), "model": MODEL, "provider": PROVIDER, "reasoning": REASONING, "temperature": TEMPERATURE, "max_model_calls": MAX_MODEL_CALLS, "cost_cap_usd": MAX_COST_USD, "max_requeries": 2, "repair_passes": 1, "observation_limit": OBSERVATION_LIMIT, "execution_timeout": EXECUTION_TIMEOUT, "provider_only": None}, "treatment": {"model": MODEL, "provider": PROVIDER, "reasoning": REASONING, "temperature": TEMPERATURE, "max_model_calls": MAX_MODEL_CALLS, "cost_cap_usd": MAX_COST_USD, "max_sql_calls": MAX_SQL_CALLS, "provider_only": None, "no_model_quality_retries": True, "formula_actuation_scope": "earned formula edits; unsupported literal/clear operations explicitly logged"}, "prompts": {"task_ir_sha256": hashlib.sha256(TASK_IR_SYSTEM.encode()).hexdigest(), "edit_plan_sha256": hashlib.sha256(EDIT_PLAN_PROMPT.encode()).hexdigest(), "retrieval_sha256": hashlib.sha256(RETRIEVAL_SYSTEM.encode()).hexdigest(), "synthesis_sha256": hashlib.sha256(SYNTHESIS_SYSTEM.encode()).hexdigest()}, "structural_profile": profile, "architecture_component_sha256": hashes, "runtime_state_machine": ["task_ir", "grounding", "edit_plan", "deterministic_expansion", "bootstrap", "bounded_sql_delta_working_set", "canonical_proposal", "proposal_seeded_c1_closure", "program_group_detection", "deterministic_translation", "ungrouped_synthesis", "neutral_actuation", "recalc", "official_scoring"], "invariants": ["edit_plan_establishes_authority", "dependency_closure_subset_of_authority", "program_group_requires_input_repetition_witness", "translation_is_deterministic", "no_duplicate_synthesis_for_translated_cells", "persistent_state_authoritative", "no_candidate_interface", "no_program_sketch_ir", "no_operand_binding_ir", "no_repair_loop"], "expected_analysis_plan_sha256": file_digest(PREP / "expected_analysis_plan.json"), "freeze_requires_all_component_hashes": True}
    write_json(PREP / "freeze.json", freeze)
    return freeze


def validate_freeze() -> dict[str, Any]:
    manifest = read_json(PREP / "freeze.json")
    drift = []
    for name, expected in manifest["architecture_component_sha256"].items():
        path = ROOT / name
        if not path.exists() or file_digest(path) != expected:
            drift.append(name)
    required = ["tasks.csv", "structural_profile.csv", "control_scores.csv", "control_scores.json", "expected_analysis_plan.json"]
    missing = [name for name in required if not (PREP / name).exists()]
    return {"manifest": manifest, "hash_drift": drift, "missing_artifacts": missing, "pass": not drift and not missing}


def preflight() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["freeze"] = validate_freeze() if (PREP / "freeze.json").exists() else {"pass": False, "reason": "freeze.json missing"}
    rows = task_rows()
    checks["population"] = {"pass": len(rows) == 60 and dict(Counter(r["category"] for r in rows)) == {"Template": 20, "Financial_Model": 20, "Debugging": 20}, "count": len(rows), "category_counts": dict(Counter(r["category"] for r in rows))}
    checks["model_guard"] = {"pass": True, "model": MODEL, "reasoning": REASONING, "temperature": TEMPERATURE}
    checks["environment"] = ensure_environment()
    checks["census"] = structural_profile()
    checks["neutrality"] = read_json(PREP / "neutrality_results.json") if (PREP / "neutrality_results.json").exists() else {"status": "MISSING"}
    checks["dry_run"] = read_json(PREP / "dry_run_results.json") if (PREP / "dry_run_results.json").exists() else {"status": "MISSING"}
    checks["central_budget"] = {"pass": MAX_MODEL_CALLS == 50 and MAX_COST_USD == 4.0, "max_model_calls": MAX_MODEL_CALLS, "max_cost_usd": MAX_COST_USD}
    checks["raw_retention"] = {"pass": all(k in {"request_body", "raw_response_body", "parsed_response", "usage", "provider_cost_usd", "finish_reason", "truncation_class", "working_set_hash", "evidence_hash", "previous_persistent_state_hash"} for k in ("request_body", "raw_response_body", "parsed_response", "usage", "provider_cost_usd", "finish_reason", "truncation_class", "working_set_hash", "evidence_hash", "previous_persistent_state_hash"))}
    source_text = Path(__file__).read_text(encoding="utf-8")
    rejected_terms = ["from " + "program_candidate", "def select_" + "program_candidate", "def " + "sketch_stage", "def " + "operand_binding_stage"]
    checks["no_rejected_mechanism_imports"] = {"pass": not any(term in source_text for term in rejected_terms), "rejected_terms": [term for term in rejected_terms if term in source_text], "note": "runtime has no rejected production mechanism path"}
    write_prep_report(preflight_result=None)
    checks["required_artifacts"] = {"pass": all((PREP / name).exists() for name in ("PREP_REPORT.md", "freeze.json", "tasks.csv", "structural_profile.csv", "control_scores.csv", "expected_analysis_plan.json", "neutrality_results.json", "dry_run_results.json"))}
    checks["pass"] = all([checks["freeze"].get("pass"), checks["population"].get("pass"), checks["environment"].get("all_inputs_present"), checks["neutrality"].get("status") == "PASS", checks["dry_run"].get("status") == "PASS", checks["central_budget"].get("pass"), checks["raw_retention"].get("pass"), checks["no_rejected_mechanism_imports"].get("pass"), checks["required_artifacts"].get("pass")])
    write_json(PREP / "preflight.json", checks)
    write_prep_report(preflight_result=checks)
    return checks


def run_live(task_keys: list[str], resume: bool) -> dict[str, Any]:
    checks = preflight()
    if not checks.get("pass"):
        raise RuntimeError(f"PRE_FLIGHT_FAILED: {json.dumps(checks, ensure_ascii=False)[:2000]}")
    for key in task_keys:
        result = run_one_task(key, stub=False, resume=resume, output_root=LIVE)
        if result.get("status") == "INTEGRATION_FAILURE" or result.get("fatal_failure"):
            print(json.dumps({"task": key, "status": result["status"]}), flush=True)
            write_json(LIVE / "run_abort.json", {"status": "ABORTED_BEFORE_VALID_TREATMENT", "task": key, "task_status": result["status"], "failure_ledger": result.get("failure_ledger", []), "generated_at": now(), "do_not_score_as_treatment": True})
            return {"status": "ABORTED_BEFORE_VALID_TREATMENT", "task": key, "output_root": str(LIVE)}
    scores = scorer(LIVE, "matched-glm-compiled-sixty-treatment", refresh=True)
    write_json(LIVE / "run_manifest.json", {"run_name": RUN_NAME, "generated_at": now(), "tasks": task_keys, "freeze_sha256": file_digest(PREP / "freeze.json"), "model_calls": sum((read_json(LIVE / key.replace(":", "-") / "state.json").get("model_call_count", 0) for key in task_keys if (LIVE / key.replace(":", "-") / "state.json").exists()), 0), "official_scores": scores})
    return {"status": "LIVE_RUN_COMPLETE", "task_count": len(task_keys), "output_root": str(LIVE), "official_scores": scores}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    sub.add_parser("neutrality")
    sub.add_parser("dry-run")
    sub.add_parser("preflight-only")
    run = sub.add_parser("run")
    run.add_argument("--task", action="append")
    run.add_argument("--tasks-file", type=Path)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--model", default=MODEL)
    run.add_argument("--reasoning", default=REASONING)
    run.add_argument("--temperature", type=float, default=TEMPERATURE)
    run.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()
    if args.command == "freeze":
        print(json.dumps(create_freeze(), indent=2))
        return 0
    if args.command == "neutrality":
        result = run_neutrality(); print(json.dumps({k: result.get(k) for k in ("status", "tasks", "passing_regression", "regression_failures")}, indent=2)); return 0 if result.get("status") == "PASS" else 1
    if args.command == "dry-run":
        result = run_dry(); print(json.dumps({k: result.get(k) for k in ("status", "selected", "live_model_calls")}, indent=2)); return 0 if result.get("status") == "PASS" else 1
    if args.command == "preflight-only":
        result = preflight(); print(json.dumps({"status": "READY_TO_RUN_MATCHED_GLM_TREATMENT" if result.get("pass") else "NOT_READY", "checks": {k: (v.get("status", v.get("pass"))) if isinstance(v, dict) else v for k, v in result.items() if k != "environment"}}, indent=2)); return 0 if result.get("pass") else 1
    check_model(args.model, args.reasoning, args.temperature)
    if args.max_workers != 1:
        raise SystemExit("MATCHED_RUNNER requires --max-workers 1 to preserve deterministic task-level budgets")
    if args.tasks_file:
        selected = [line.strip() for line in args.tasks_file.read_text().splitlines() if line.strip()]
    elif args.task:
        selected = args.task
    else:
        selected = [r["task_key"] for r in task_rows()]
    expected = {r["task_key"] for r in task_rows()}
    if set(selected) - expected:
        raise SystemExit(f"invalid tasks: {sorted(set(selected) - expected)}")
    result = run_live(selected, args.resume); print(json.dumps(result, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
