"""Mechanical workbook index backing Stage-B inspection helpers.

Tables (SQLite, hidden from the model): cells, text anchors, temporal coords.
No semantics: no ranking, no relevance, no target claims, no roles.
Freshness: every query rehashes the workbook file; on mismatch the index
rebuilds before answering. Fail closed: never serve a stale generation.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from pathlib import Path

PERIOD_RES = [
    re.compile(r"FY\s?(\d{2,4})", re.IGNORECASE),
    re.compile(r"CY\s?(\d{2,4})", re.IGNORECASE),
    re.compile(r"\bQ([1-4])\b"),
    re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", re.IGNORECASE),
    re.compile(r"\b(19|20)\d{2}\b"),
]

_state: dict[str, dict] = {}
_query_counter = 0
_failures: dict[str, dict] = {}
_generations: dict[str, int] = {}
_snapshot_handles: dict[str, list[dict]] = {}
failure_events: list[dict] = []


class SubstrateDisabled(RuntimeError):
    """Internal control signal; consumers must select ordinary openpyxl."""

    def __init__(self, event: dict):
        self.event = event
        super().__init__(event["fallback_reason"])


def disable(path, generation, stage, exc, *, partial=False, served=False, substrate_generation=None):
    p = str(path)
    old = _state.pop(p, None)
    if old is not None:
        old["valid"] = False
    handles = _snapshot_handles.pop(p, [])
    served = served or bool(old and old.get("accelerated_served")) or any(h.get("accelerated_served") for h in handles)
    for handle in handles:
        handle["valid"] = False
    event = {
        "event": "substrate_fallback",
        "status": "ACCELERATION_DISABLED_FOR_RELEVANT_SCOPE",
        "path": p, "workbook_generation": generation,
        "index_generation": substrate_generation if substrate_generation is not None else _generations.get(p, 0), "stage": stage,
        "exception_class": type(exc).__name__,
        "fallback_reason": "optional substrate failed; ordinary openpyxl required",
        "partially_initialized": partial,
        "accelerated_operation_already_served": served,
    }
    _failures[p] = event
    failure_events.append(event)
    logging.getLogger(__name__).warning("substrate_fallback %s", event)
    if old is not None:
        close_resource(old["db"], p, generation)
    for handle in handles:
        close_resource(handle["db"], p, generation)
    return event


def close_resource(resource, path, generation):
    try:
        resource.close()
    except Exception as exc:
        event = {"event": "substrate_cleanup_failure", "path": str(path),
                 "workbook_generation": generation, "stage": "partial_build_cleanup",
                 "exception_class": type(exc).__name__,
                 "status": "ACCELERATION_DISABLED_FOR_RELEVANT_SCOPE",
                 "fallback_reason": "cleanup failed; discarded handle remains non-authoritative",
                 "partially_initialized": True, "accelerated_operation_already_served": False}
        failure_events.append(event)
        logging.getLogger(__name__).warning("substrate_cleanup_failure %s", event)



def workbook_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE TABLE cells(sheet TEXT, addr TEXT, row INT, col INT, "
                    "value TEXT, formula TEXT, dtype TEXT)")
        con.execute("CREATE TABLE anchors(term TEXT, sheet TEXT, addr TEXT)")
        con.execute("CREATE TABLE temporal(label TEXT, sheet TEXT, addr TEXT, "
                    "row INT, col INT)")
        con.execute("CREATE INDEX ia ON anchors(term)")
        con.execute("CREATE INDEX ic ON cells(sheet, row, col)")
    except Exception as exc:
        exc.substrate_partially_initialized = True
        close_resource(con, "<database under construction>", None)
        raise
    return con


def build_index(path: str | Path) -> dict:
    """(Re)build the index for a workbook file. Returns index handle."""
    import openpyxl
    p = str(path)
    wb = con = None
    served_before = bool(_state.get(p, {}).get("accelerated_served"))
    generation = None
    stage = "freshness_initialization"
    try:
        generation = workbook_hash(p)
        failed = _failures.get(p)
        if failed and failed["workbook_generation"] in (None, generation):
            raise SubstrateDisabled(failed)
        _failures.pop(p, None)
        # Retire every local snapshot before constructing a new generation.
        for handle in _snapshot_handles.pop(p, []):
            served_before = served_before or bool(handle.get("accelerated_served"))
            handle["valid"] = False
            close_resource(handle["db"], p, generation)
        old = _state.pop(p, None)
        if old is not None:
            old["valid"] = False
            old["db"].close()
        stage = "workbook_index_parse"
        wb = openpyxl.load_workbook(p, data_only=False, read_only=True)
        stage = "compiled_database_construction"
        con = _open_db()
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    v, f = c.value, None
                    if c.data_type == "f":
                        if isinstance(c.value, str):
                            f = c.value
                        elif hasattr(c.value, "text"):
                            # openpyxl represents array formulas as objects;
                            # use their stable formula text rather than the
                            # process-specific object repr.
                            f = c.value.text
                        else:
                            f = str(c.value)
                        v = None
                    if v is None and f is None:
                        continue
                    con.execute("INSERT INTO cells VALUES (?,?,?,?,?,?,?)",
                                (ws.title, c.coordinate, c.row, c.column,
                                 None if v is None else str(v), f, c.data_type))
                    for text in (str(v) if v is not None else None, f):
                        if not text:
                            continue
                        for tok in re.findall(r"[A-Za-z0-9%\$]+", text.lower()):
                            con.execute("INSERT INTO anchors VALUES (?,?,?)",
                                        (tok, ws.title, c.coordinate))
                    if isinstance(v, str):
                        for rx in PERIOD_RES:
                            for m in rx.finditer(v):
                                con.execute("INSERT INTO temporal VALUES (?,?,?,?,?)",
                                            (m.group(0), ws.title, c.coordinate, c.row, c.column))
        # Completion marker is committed with the rows, never before them.
        con.execute("CREATE TABLE substrate_identity(workbook_hash TEXT, index_generation INT)")
        con.execute("INSERT INTO substrate_identity VALUES (?, ?)",
                    (generation, _generations.get(p, 0) + 1))
        con.commit()
        stage = "freshness_verification"
        if workbook_hash(p) != generation:
            raise RuntimeError("workbook changed during index construction")
        wb.close()
        wb = None
    except SubstrateDisabled:
        raise
    except Exception as exc:
        event = disable(p, generation, stage, exc, partial=con is not None or getattr(exc, "substrate_partially_initialized", False), served=served_before)
        raise SubstrateDisabled(event) from exc
    finally:
        if wb is not None:
            close_resource(wb, p, generation)
        if con is not None and p in _failures:
            close_resource(con, p, generation)
    _failures.pop(p, None)
    _generations[p] = _generations.get(p, 0) + 1
    handle = {"db": con, "workbook_hash": generation,
              "index_generation": _generations[p], "valid": True}
    _state[p] = handle
    return handle


def ensure_fresh(path: str | Path) -> tuple[dict, bool]:
    """Return (handle, rebuilt). Rebuilds when the file hash moved."""
    p = str(path)
    try:
        cur = workbook_hash(p)
    except Exception as exc:
        raise SubstrateDisabled(disable(p, None, "freshness_initialization", exc)) from exc
    failed = _failures.get(p)
    if failed and failed["workbook_generation"] in (None, cur):
        raise SubstrateDisabled(failed)
    h = _state.get(p)
    if h is None or h["workbook_hash"] != cur:
        return build_index(p), True
    return h, False


def next_query_id() -> int:
    global _query_counter
    _query_counter += 1
    return _query_counter


def reset() -> None:
    for p, handles in _snapshot_handles.items():
        for handle in handles:
            handle["valid"] = False
            close_resource(handle["db"], p, handle.get("workbook_hash"))
    _snapshot_handles.clear()
    for handle in _state.values():
        handle["valid"] = False
        handle["db"].close()
    _state.clear()
    _failures.clear()
    _generations.clear()
    failure_events.clear()
