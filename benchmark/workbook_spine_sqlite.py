#!/usr/bin/env python3
"""Typed SQLite materialization and read-only query interfaces for workbook spines.

This module deliberately contains only mechanically compiled workbook facts. It
does not rank candidates, infer finance roles, or expose a formula-synthesis
operation.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
SPINE_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe/spines"
TEMPORAL_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-closure-probe/coords"

SCHEMA_SQL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE workbooks (workbook_id TEXT PRIMARY KEY, source_path TEXT, readable INTEGER NOT NULL);
CREATE TABLE sheets (sheet_id TEXT PRIMARY KEY, workbook_id TEXT NOT NULL, sheet_index INTEGER NOT NULL, name TEXT NOT NULL, normalized_name TEXT, visibility TEXT, used_r1 INTEGER, used_c1 INTEGER, used_r2 INTEGER, used_c2 INTEGER);
CREATE TABLE rows (row_id TEXT PRIMARY KEY, sheet_id TEXT NOT NULL, row_idx INTEGER NOT NULL, n_text INTEGER, n_formula INTEGER, n_value INTEGER, n_blank INTEGER);
CREATE TABLE columns (col_id TEXT PRIMARY KEY, sheet_id TEXT NOT NULL, col_idx INTEGER NOT NULL, n_text INTEGER, n_formula INTEGER, n_value INTEGER, periods_json TEXT);
CREATE TABLE cells (cell_id TEXT PRIMARY KEY, sheet_id TEXT NOT NULL, row_id TEXT NOT NULL, col_id TEXT NOT NULL, row_idx INTEGER NOT NULL, col_idx INTEGER NOT NULL, address TEXT NOT NULL, kind TEXT NOT NULL, raw_value TEXT, display_value TEXT);
CREATE TABLE text_anchors (anchor_id TEXT PRIMARY KEY, cell_id TEXT NOT NULL, exact_text TEXT NOT NULL, normalized_text TEXT, row_id TEXT, col_id TEXT);
CREATE TABLE formulas (formula_id TEXT PRIMARY KEY, cell_id TEXT NOT NULL, formula_text TEXT, fingerprint_id TEXT, opaque INTEGER NOT NULL);
CREATE TABLE formula_classes (fingerprint_id TEXT PRIMARY KEY, canonical_fingerprint TEXT);
CREATE TABLE formula_class_members (fingerprint_id TEXT NOT NULL, formula_id TEXT NOT NULL, PRIMARY KEY (fingerprint_id, formula_id));
CREATE TABLE point_references (formula_id TEXT NOT NULL, referenced_cell_id TEXT NOT NULL, ref_slot INTEGER NOT NULL, row_delta INTEGER, col_delta INTEGER, row_absolute INTEGER, col_absolute INTEGER, cross_sheet INTEGER NOT NULL, PRIMARY KEY (formula_id, ref_slot, referenced_cell_id));
CREATE TABLE ranges (range_id TEXT PRIMARY KEY, sheet_id TEXT NOT NULL, r1 INTEGER NOT NULL, c1 INTEGER NOT NULL, r2 INTEGER NOT NULL, c2 INTEGER NOT NULL);
CREATE TABLE range_references (formula_id TEXT NOT NULL, range_id TEXT NOT NULL, ref_slot INTEGER NOT NULL, cross_sheet INTEGER NOT NULL, PRIMARY KEY (formula_id, ref_slot, range_id));
CREATE TABLE temporal_coordinates (temporal_id TEXT PRIMARY KEY, sheet_id TEXT NOT NULL, axis TEXT NOT NULL, axis_index INTEGER, year INTEGER, month INTEGER, quarter INTEGER, marker TEXT, derivation_kind TEXT, cell_id TEXT, row_id TEXT, col_id TEXT, period_key TEXT, header_text TEXT);
CREATE TABLE temporal_provenance (temporal_id TEXT NOT NULL, step_index INTEGER NOT NULL, source_cell_id TEXT, parent_cell_id TEXT, relation_type TEXT, PRIMARY KEY (temporal_id, step_index, source_cell_id, parent_cell_id, relation_type));
CREATE VIEW formula_locations AS SELECT f.formula_id, f.cell_id, c.sheet_id, c.row_idx, c.col_idx, f.fingerprint_id, f.opaque FROM formulas f JOIN cells c ON c.cell_id=f.cell_id;
CREATE VIEW formula_point_precedents AS SELECT p.formula_id, p.referenced_cell_id, p.ref_slot, p.row_delta, p.col_delta, p.row_absolute, p.col_absolute, p.cross_sheet FROM point_references p;
CREATE VIEW formula_range_precedents AS SELECT r.formula_id, r.range_id, r.ref_slot, r.cross_sheet, g.sheet_id, g.r1, g.c1, g.r2, g.c2 FROM range_references r JOIN ranges g ON g.range_id=r.range_id;
CREATE VIEW row_formulas AS SELECT c.row_id, f.formula_id, f.cell_id, f.fingerprint_id FROM formulas f JOIN cells c ON c.cell_id=f.cell_id;
CREATE VIEW column_formulas AS SELECT c.col_id, f.formula_id, f.cell_id, f.fingerprint_id FROM formulas f JOIN cells c ON c.cell_id=f.cell_id;
CREATE VIEW cell_temporal_context AS SELECT t.temporal_id, t.cell_id, t.sheet_id, t.axis, t.axis_index, t.year, t.month, t.quarter, t.marker, t.derivation_kind, t.period_key FROM temporal_coordinates t;
CREATE VIEW formula_with_temporal_context AS SELECT f.formula_id, f.cell_id, f.fingerprint_id, t.temporal_id, t.axis, t.axis_index, t.year, t.month, t.quarter, t.period_key FROM formulas f LEFT JOIN cell_temporal_context t ON t.cell_id=f.cell_id;
CREATE INDEX idx_cells_sheet_row_col ON cells(sheet_id, row_idx, col_idx);
CREATE INDEX idx_cells_sheet_row ON cells(sheet_id, row_idx);
CREATE INDEX idx_cells_sheet_col ON cells(sheet_id, col_idx);
CREATE INDEX idx_text_anchors_normalized ON text_anchors(normalized_text);
CREATE INDEX idx_formulas_cell ON formulas(cell_id);
CREATE INDEX idx_formulas_fingerprint ON formulas(fingerprint_id);
CREATE INDEX idx_members_fingerprint ON formula_class_members(fingerprint_id);
CREATE INDEX idx_point_formula ON point_references(formula_id);
CREATE INDEX idx_point_source ON point_references(referenced_cell_id);
CREATE INDEX idx_range_formula ON range_references(formula_id);
CREATE INDEX idx_temporal_sheet_axis ON temporal_coordinates(sheet_id, axis, axis_index);
CREATE INDEX idx_temporal_ym ON temporal_coordinates(year, month);
"""

DDL_CONTEXT = SCHEMA_SQL


def canonical_cell_id(value: str | None) -> str | None:
    """Normalize legacy ``cell:sheet:s03`` aliases to the spine's cell:s03 form."""
    if not value:
        return None
    m = re.fullmatch(r"cell:(?:sheet:)?s(\d+):r(\d+):c(\d+)", value)
    return None if not m else f"cell:s{int(m.group(1)):02d}:r{int(m.group(2))}:c{int(m.group(3))}"


def canonical_sheet_id(value: str | None) -> str | None:
    if not value:
        return None
    m = re.fullmatch(r"(?:sheet:)?s(\d+)", value)
    return None if not m else f"sheet:s{int(m.group(1)):02d}"


def canonical_row_id(value: str | None) -> str | None:
    if not value:
        return None
    m = re.fullmatch(r"row:(?:sheet:)?s(\d+):r(\d+)", value)
    return None if not m else f"row:s{int(m.group(1)):02d}:r{int(m.group(2))}"


def canonical_col_id(value: str | None) -> str | None:
    if not value:
        return None
    m = re.fullmatch(r"col:(?:sheet:)?s(\d+):c(\d+)", value)
    return None if not m else f"col:s{int(m.group(1)):02d}:c{int(m.group(2))}"


def canonical_formula_id(value: str | None) -> str | None:
    if not value:
        return None
    m = re.fullmatch(r"formula:(?:sheet:)?s(\d+):r(\d+):c(\d+)", value)
    return None if not m else f"formula:s{int(m.group(1)):02d}:r{int(m.group(2))}:c{int(m.group(3))}"


def canonical_range_id(sheet_id: str, r1: int, c1: int, r2: int, c2: int) -> str:
    sid = canonical_sheet_id(sheet_id) or sheet_id
    return f"range:{sid.removeprefix('sheet:')}:r{min(r1,r2)}:c{min(c1,c2)}:r{max(r1,r2)}:c{max(c1,c2)}"


def _json_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _a1(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    m = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?(\d+)", value)
    if not m:
        return None
    n = 0
    for char in m.group(1).upper():
        n = n * 26 + ord(char) - 64
    return n, int(m.group(2))


def _address(col: int, row: int) -> str:
    out = ""
    n = col
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return f"{out}{row}"


def _sheet_id_from_title(spine: dict[str, Any], title: str) -> str | None:
    index = (spine.get("title_to_index") or {}).get(title)
    return None if index is None else f"sheet:s{int(index):02d}"


def _cell_from_title_address(spine: dict[str, Any], title: str, address: str) -> str | None:
    sid = _sheet_id_from_title(spine, title)
    pos = _a1(address)
    return None if not sid or not pos else f"cell:{sid.removeprefix('sheet:')}:r{pos[1]}:c{pos[0]}"


def _insert_spine(conn: sqlite3.Connection, spine: dict[str, Any], temporal: dict[str, Any] | None) -> dict[str, int]:
    wb_id = spine["workbook_id"]
    conn.execute("INSERT INTO workbooks VALUES (?, ?, ?)", (wb_id, spine.get("path"), int(bool(spine.get("readable")))))
    conn.executemany("INSERT INTO sheets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        (s["id"], wb_id, s["index"], s["title"], s.get("title_norm"), s.get("visibility"), s.get("bounds", {}).get("min_row"), s.get("bounds", {}).get("min_col"), s.get("bounds", {}).get("max_row"), s.get("bounds", {}).get("max_col")) for s in spine.get("sheets", [])
    ])
    for r in spine.get("rows") or []:
        conn.execute("INSERT OR IGNORE INTO rows VALUES (?, ?, ?, ?, ?, ?, ?)", (canonical_row_id(r["id"]), canonical_sheet_id(r["sheet_id"]), r["row"], r.get("n_text"), r.get("n_formula"), r.get("n_value"), r.get("n_blank")))
    for c in spine.get("cols") or []:
        conn.execute("INSERT OR IGNORE INTO columns VALUES (?, ?, ?, ?, ?, ?, ?)", (canonical_col_id(c["id"]), canonical_sheet_id(c["sheet_id"]), c["col"], c.get("n_text"), c.get("n_formula"), c.get("n_value"), _json_value(c.get("periods"))))
    cells: dict[str, tuple[Any, ...]] = {}
    for c in spine.get("occupied") or []:
        cid = canonical_cell_id(c.get("id"))
        if not cid:
            continue
        sid = canonical_sheet_id(c.get("sheet_id"))
        row, col = int(c["row"]), int(c["col"])
        cells[cid] = (cid, sid, f"row:{sid.removeprefix('sheet:')}:r{row}", f"col:{sid.removeprefix('sheet:')}:c{col}", row, col, c.get("address") or _address(col, row), c.get("kind") or "blank", _json_value(c.get("payload")), _json_value(c.get("payload")))
    # Ensure every explicit point endpoint is queryable even when the source
    # workbook did not instantiate a blank cell object.
    for dep in spine.get("point_deps") or []:
        cid = canonical_cell_id(dep.get("source_id"))
        if cid and cid not in cells:
            m = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", cid)
            if m:
                sid, row, col = f"sheet:s{int(m.group(1)):02d}", int(m.group(2)), int(m.group(3))
                cells[cid] = (cid, sid, f"row:s{int(m.group(1)):02d}:r{row}", f"col:s{int(m.group(1)):02d}:c{col}", row, col, _address(col, row), "blank", None, None)
    conn.executemany("INSERT INTO cells VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", cells.values())
    conn.executemany("INSERT INTO text_anchors VALUES (?, ?, ?, ?, ?, ?)", [
        (a["id"], canonical_cell_id(a["cell_id"]), a.get("text"), a.get("text_norm"), canonical_row_id(a.get("row_id")), canonical_col_id(a.get("col_id"))) for a in spine.get("text_anchors") or []
    ])
    for f in spine.get("formulas") or []:
        fid = canonical_formula_id(f["id"])
        fp = f.get("class_id")
        conn.execute("INSERT INTO formulas VALUES (?, ?, ?, ?, ?)", (fid, canonical_cell_id(f.get("cell_id")), f.get("formula"), fp, int(bool(f.get("opaque")))))
        if fp and not f.get("opaque"):
            conn.execute("INSERT OR IGNORE INTO formula_classes VALUES (?, ?)", (fp, f.get("fingerprint")))
            conn.execute("INSERT OR IGNORE INTO formula_class_members VALUES (?, ?)", (fp, fid))
    # Preserve exact parsed reference slots and absolute/relative masks where
    # the existing operational parser supports them.
    from formula_operational import parse_use_def_slots
    formulas_by_id = {canonical_formula_id(f["id"]): f for f in spine.get("formulas") or []}
    for fid, f in formulas_by_id.items():
        if not f.get("formula") or f.get("opaque"):
            continue
        origin = canonical_cell_id(f.get("cell_id"))
        if not origin:
            continue
        m = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", origin)
        if not m:
            continue
        origin_sid, origin_row, origin_col = int(m.group(1)), int(m.group(2)), int(m.group(3))
        title = next((s["title"] for s in spine.get("sheets") or [] if s["index"] == origin_sid), "")
        parsed = parse_use_def_slots(f["formula"], title, origin_col, origin_row)
        for slot in parsed.get("slots") or []:
            host_sid = _sheet_id_from_title(spine, slot.get("sheet") or title)
            if not host_sid:
                continue
            if slot.get("is_range"):
                rid = canonical_range_id(host_sid, slot["r1"], slot["c1"], slot["r2"], slot["c2"])
                conn.execute("INSERT OR IGNORE INTO ranges VALUES (?, ?, ?, ?, ?, ?)", (rid, host_sid, slot["r1"], slot["c1"], slot["r2"], slot["c2"]))
                conn.execute("INSERT OR IGNORE INTO range_references VALUES (?, ?, ?, ?)", (fid, rid, slot["index"], int(bool(slot.get("cross_sheet")))))
            else:
                ref = f"cell:{host_sid.removeprefix('sheet:')}:r{slot['r1']}:c{slot['c1']}"
                mask = slot.get("abs_mask") or "CR"
                conn.execute("INSERT OR IGNORE INTO point_references VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (fid, ref, slot["index"], slot.get("drow"), slot.get("dcol"), int(len(mask) > 1 and mask[1] == "$"), int(bool(mask) and mask[0] == "$"), int(bool(slot.get("cross_sheet")))))
    # The frozen spine dependency ledger remains authoritative for explicit
    # references when the bounded formula text/parser cannot expose a slot.
    existing_points = set(conn.execute("SELECT formula_id, referenced_cell_id FROM point_references"))
    existing_ranges = set(conn.execute("SELECT formula_id, range_id FROM range_references"))
    for dep in spine.get("point_deps") or []:
        fid = canonical_formula_id(dep.get("consumer_formula_id"))
        ref = canonical_cell_id(dep.get("source_id"))
        if not fid or not ref or (fid, ref) in existing_points:
            continue
        slot = conn.execute("SELECT COALESCE(MAX(ref_slot), -1) + 1 FROM point_references WHERE formula_id=?", (fid,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO point_references VALUES (?, ?, ?, NULL, NULL, NULL, NULL, ?)", (fid, ref, slot, int(bool(dep.get("cross_sheet")))))
        existing_points.add((fid, ref))
    for dep in spine.get("range_deps") or []:
        fid = canonical_formula_id(dep.get("consumer_formula_id"))
        start = canonical_cell_id(dep.get("source_start_id"))
        end = canonical_cell_id(dep.get("source_end_id"))
        if not fid or not start or not end:
            continue
        sm = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", start)
        em = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", end)
        if not sm or not em or sm.group(1) != em.group(1):
            continue
        rid = canonical_range_id(f"sheet:s{int(sm.group(1)):02d}", int(sm.group(2)), int(sm.group(3)), int(em.group(2)), int(em.group(3)))
        conn.execute("INSERT OR IGNORE INTO ranges VALUES (?, ?, ?, ?, ?, ?)", (rid, f"sheet:s{int(sm.group(1)):02d}", min(int(sm.group(2)), int(em.group(2))), min(int(sm.group(3)), int(em.group(3))), max(int(sm.group(2)), int(em.group(2))), max(int(sm.group(3)), int(em.group(3)))))
        if (fid, rid) in existing_ranges:
            continue
        slot = conn.execute("SELECT COALESCE(MAX(ref_slot), -1) + 1 FROM range_references WHERE formula_id=?", (fid,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO range_references VALUES (?, ?, ?, ?)", (fid, rid, slot, int(bool(dep.get("cross_sheet")))))
        existing_ranges.add((fid, rid))
    # Temporal coordinates and closure provenance are materialized, not
    # rediscovered by model queries.
    for t in (temporal or {}).get("coordinates") or []:
        period = t.get("period") or {}
        components = t.get("components") or {}
        conn.execute("INSERT OR REPLACE INTO temporal_coordinates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (t.get("id"), canonical_sheet_id(t.get("sheet_id")), t.get("axis"), t.get("col") if t.get("axis") == "column" else t.get("row"), components.get("year", period.get("year")), components.get("month", period.get("month")), components.get("quarter", period.get("quarter")), components.get("marker"), t.get("derivation_status"), canonical_cell_id(t.get("cell_id")), canonical_row_id(t.get("row_id")), canonical_col_id(t.get("col_id")), t.get("period_key"), t.get("header_text")))
        provenance = t.get("provenance") or []
        for i, p in enumerate(provenance):
            parent = p.get("seed") or p.get("cell")
            source = t.get("cell_id")
            parent_id = _cell_from_title_address(spine, parent.split("!", 1)[0], parent.split("!", 1)[1]) if isinstance(parent, str) and "!" in parent else canonical_cell_id(parent)
            relation = (p.get("compact") or [None])[0] if isinstance(p.get("compact"), list) else p.get("source") or "temporal_provenance"
            conn.execute("INSERT OR IGNORE INTO temporal_provenance VALUES (?, ?, ?, ?, ?)", (t.get("id"), i, canonical_cell_id(source), parent_id, relation))
    counts = {}
    for table in ("sheets", "rows", "columns", "cells", "text_anchors", "formulas", "formula_classes", "formula_class_members", "point_references", "ranges", "range_references", "temporal_coordinates", "temporal_provenance"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    lineage = spine.get("lineage") or {}
    conn.executemany("INSERT INTO metadata VALUES (?, ?)", [
        ("schema_version", "workbook_spine_sqlite_v1"),
        ("id_normalization", "canonical cell:sNN / sheet:sNN IDs"),
        ("counts", json.dumps(counts, sort_keys=True)),
        ("source_sha256", str(lineage.get("source_sha256") or "")),
        ("payload_sha256", str(lineage.get("payload_sha256") or "")),
    ])
    return counts


def build_database(spine_path: Path, temporal_path: Path, destination: Path) -> dict[str, Any]:
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    temporal = json.loads(temporal_path.read_text(encoding="utf-8")) if temporal_path.exists() else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    conn = sqlite3.connect(destination)
    try:
        conn.executescript(SCHEMA_SQL)
        counts = _insert_spine(conn, spine, temporal)
        conn.commit()
        return {"workbook_id": spine.get("workbook_id"), "path": str(destination), "counts": counts, "spine_stats": spine.get("stats", {}), "temporal": {k: temporal.get(k) for k in ("n_coordinates", "n_local_coordinates", "n_propagated_coordinates")} if temporal else None}
    finally:
        conn.close()


class ReadOnlySqlite:
    """Read-only SQL with deny-by-authorizer and no silent result truncation."""

    DENIED = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_TEMP_TABLE, sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_CREATE_TEMP_TRIGGER, sqlite3.SQLITE_CREATE_TEMP_INDEX, sqlite3.SQLITE_PRAGMA}

    def __init__(self, path: Path, *, max_rows: int = 5000, max_bytes: int = 8_000_000, timeout_s: float = 10.0, max_progress_ops: int = 2_000_000):
        self.path = path
        self.max_rows = max_rows
        self.max_bytes = max_bytes
        self.timeout_s = timeout_s
        self.max_progress_ops = max_progress_ops

    def execute(self, sql: str) -> dict[str, Any]:
        started = time.perf_counter()
        normalized = re.sub(r"^\s*(?:--[^\n]*\n|/\*.*?\*/\s*)*", "", sql or "", flags=re.S)
        first = (normalized.strip().split(None, 1) or [""])[0].upper()
        if first not in {"SELECT", "WITH"}:
            return {"status": "SQL_REJECTED", "error": "Only SELECT or WITH statements are permitted", "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        ops = 0
        def progress() -> int:
            nonlocal ops
            ops += 1000
            return int(ops > self.max_progress_ops or time.perf_counter() - started > self.timeout_s)
        def authorizer(action: int, _arg1: str | None, _arg2: str | None, _db: str | None, _source: str | None) -> int:
            return sqlite3.SQLITE_DENY if action in self.DENIED else sqlite3.SQLITE_OK
        conn.set_authorizer(authorizer)
        conn.set_progress_handler(progress, 1000)
        try:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description or []]
            rows = []
            encoded_bytes = 0
            while True:
                batch = cur.fetchmany(256)
                if not batch:
                    break
                for item in batch:
                    record = {key: item[key] for key in columns}
                    encoded_bytes += len(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                    if len(rows) + 1 > self.max_rows or encoded_bytes > self.max_bytes:
                        return {"status": "RESULT_TOO_LARGE", "columns": columns, "row_count": None, "configured_row_limit": self.max_rows, "configured_byte_limit": self.max_bytes, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
                    rows.append(record)
            return {"status": "OK", "columns": columns, "rows": rows, "row_count": len(rows), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2), "bytes": encoded_bytes}
        except (sqlite3.OperationalError, sqlite3.ProgrammingError) as exc:
            message = str(exc)
            status = "QUERY_TIMEOUT" if "interrupted" in message.lower() else "SQL_ERROR"
            return {"status": status, "error": message[:500], "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
        finally:
            conn.close()


class TypedWorkbookApi:
    """Small mechanical API compiled to deterministic SQL over the same DB."""

    def __init__(self, executor: ReadOnlySqlite):
        self.executor = executor

    def _run(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any]:
        # Parameters are safely literalized for the read-only query path. The
        # API itself never exposes arbitrary SQL to the caller.
        conn = sqlite3.connect(f"file:{self.executor.path}?mode=ro", uri=True)
        try:
            rendered = sql
            for value in params:
                escaped = "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"
                rendered = rendered.replace("?", escaped, 1)
            return self.executor.execute(rendered)
        finally:
            conn.close()

    def get_entities(self, ids: list[str]) -> dict[str, Any]:
        ids = [canonical_cell_id(x) or canonical_formula_id(x) or canonical_sheet_id(x) or x for x in ids]
        if not ids:
            return {"status": "OK", "columns": [], "rows": [], "row_count": 0, "elapsed_ms": 0}
        quoted = ",".join("'" + x.replace("'", "''") + "'" for x in ids)
        sql = f"SELECT 'cell' AS entity_type, cell_id AS entity_id, sheet_id, row_idx, col_idx, kind, raw_value FROM cells WHERE cell_id IN ({quoted}) UNION ALL SELECT 'formula', formula_id, NULL, NULL, NULL, 'formula', formula_text FROM formulas WHERE formula_id IN ({quoted}) UNION ALL SELECT 'sheet', sheet_id, sheet_id, NULL, NULL, 'sheet', name FROM sheets WHERE sheet_id IN ({quoted})"
        return self.executor.execute(sql)

    def text_matches(self, text: str, sheet_ids: list[str] | None = None) -> dict[str, Any]:
        clause = "" if not sheet_ids else " AND sheet_id IN (" + ",".join("'" + canonical_sheet_id(x).replace("'", "''") + "'" for x in sheet_ids if canonical_sheet_id(x)) + ")"
        escaped = text.replace("'", "''")
        return self.executor.execute(f"SELECT anchor_id, cell_id, exact_text, normalized_text FROM text_anchors WHERE normalized_text LIKE '%' || lower('{escaped}') || '%' {clause} ORDER BY anchor_id")

    def formulas_in_row(self, row_id: str) -> dict[str, Any]:
        rid = canonical_row_id(row_id) or row_id
        return self.executor.execute("SELECT formula_id, cell_id, fingerprint_id FROM row_formulas WHERE row_id='" + rid.replace("'", "''") + "' ORDER BY cell_id")

    def formulas_in_column(self, col_id: str) -> dict[str, Any]:
        cid = canonical_col_id(col_id) or col_id
        return self.executor.execute("SELECT formula_id, cell_id, fingerprint_id FROM column_formulas WHERE col_id='" + cid.replace("'", "''") + "' ORDER BY cell_id")

    def references_of(self, formula_ids: list[str]) -> dict[str, Any]:
        ids = [canonical_formula_id(x) or x for x in formula_ids]
        quoted = ",".join("'" + x.replace("'", "''") + "'" for x in ids)
        return self.executor.execute(f"SELECT formula_id, referenced_cell_id AS entity_id, ref_slot, 'POINT' AS reference_type, cross_sheet FROM point_references WHERE formula_id IN ({quoted}) UNION ALL SELECT formula_id, range_id, ref_slot, 'RANGE', cross_sheet FROM range_references WHERE formula_id IN ({quoted}) ORDER BY formula_id, ref_slot")

    def dependents_of(self, entity_ids: list[str]) -> dict[str, Any]:
        ids = [canonical_cell_id(x) or x for x in entity_ids]
        quoted = ",".join("'" + x.replace("'", "''") + "'" for x in ids)
        return self.executor.execute(f"SELECT formula_id, referenced_cell_id AS entity_id, ref_slot, 'POINT' AS reference_type FROM point_references WHERE referenced_cell_id IN ({quoted}) UNION ALL SELECT rr.formula_id, rr.range_id, rr.ref_slot, 'RANGE' FROM range_references rr WHERE rr.range_id IN ({quoted}) ORDER BY formula_id")

    def formula_class_members(self, fingerprint_id: str) -> dict[str, Any]:
        fp = fingerprint_id.replace("'", "''")
        return self.executor.execute(f"SELECT m.fingerprint_id, m.formula_id, f.cell_id FROM formula_class_members m JOIN formulas f ON f.formula_id=m.formula_id WHERE m.fingerprint_id='{fp}' ORDER BY f.cell_id")

    def temporal_at(self, sheet_id: str, axis: str, axis_index: int) -> dict[str, Any]:
        sid = canonical_sheet_id(sheet_id) or sheet_id
        return self.executor.execute(f"SELECT temporal_id, cell_id, year, month, quarter, marker, derivation_kind, period_key FROM temporal_coordinates WHERE sheet_id='{sid}' AND axis='{axis.replace(chr(39), chr(39)*2)}' AND axis_index={int(axis_index)} ORDER BY temporal_id")

    def entities_at_period(self, year: int | None = None, month: int | None = None) -> dict[str, Any]:
        clause = []
        if year is not None: clause.append(f"year={int(year)}")
        if month is not None: clause.append(f"month={int(month)}")
        return self.executor.execute("SELECT temporal_id, cell_id, sheet_id, axis, axis_index, year, month, quarter, period_key FROM temporal_coordinates WHERE " + (" AND ".join(clause) if clause else "1=1"))

    def translate_formula(self, formula_id: str, target_cell_id: str) -> dict[str, Any]:
        # Mechanical relation only: translate relative A1 references. This is
        # not a semantic query and does not select whether a source formula is
        # an appropriate homologue.
        fid = canonical_formula_id(formula_id) or formula_id
        tid = canonical_cell_id(target_cell_id) or target_cell_id
        source = self.executor.execute("SELECT f.formula_id, f.cell_id, f.formula_text, f.fingerprint_id FROM formulas f WHERE f.formula_id='" + fid.replace("'", "''") + "'")
        if source.get("status") != "OK" or not source.get("rows"):
            return source
        row = source["rows"][0]
        origin = canonical_cell_id(row.get("cell_id"))
        target = canonical_cell_id(tid)
        origin_match = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", origin or "")
        target_match = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", target or "")
        if not origin_match or not target_match or not row.get("formula_text"):
            return {"status": "API_ERROR", "error": "Formula or canonical source/target cell is not translatable"}
        from librecalc_mcp.domain.formulas import translate_a1_formula
        translated = translate_a1_formula(
            row["formula_text"],
            column_offset=int(target_match.group(3)) - int(origin_match.group(3)),
            row_offset=int(target_match.group(2)) - int(origin_match.group(2)),
        )
        return {"status": "OK", "columns": ["formula_id", "cell_id", "formula_text", "fingerprint_id", "target_cell_id", "translated_formula"], "rows": [{**row, "target_cell_id": target, "translated_formula": translated}], "row_count": 1, "elapsed_ms": source.get("elapsed_ms", 0)}


def database_id_inventory(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        out: set[str] = set()
        for table, column in (("workbooks", "workbook_id"), ("cells", "cell_id"), ("formulas", "formula_id"), ("sheets", "sheet_id"), ("rows", "row_id"), ("columns", "col_id"), ("text_anchors", "anchor_id"), ("formula_classes", "fingerprint_id"), ("ranges", "range_id"), ("temporal_coordinates", "temporal_id")):
            out.update(row[0] for row in conn.execute(f"SELECT {column} FROM {table}"))
        return out
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("spine")
    parser.add_argument("temporal")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(json.dumps(build_database(Path(args.spine), Path(args.temporal), Path(args.destination)), indent=2))
