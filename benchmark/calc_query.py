#!/usr/bin/env python3
"""Read-only calc_query over the existing compiled workbook world.

Deterministic structural facts only. No Task IR, edit authority, gold, or
synthesis. Used by the C1 sidecar arm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path[:0] = [
    str(ROOT / "benchmark"),
    str(ROOT / "src"),
    str(ROOT / "benchmark/sweagent/formula_index/lib"),
]

from workbook_grounding_spine import compile_spine  # noqa: E402
from workbook_spine_sqlite import build_database, ReadOnlySqlite  # noqa: E402
from temporal_spine import compile_temporal_workbook  # noqa: E402

MODES = ("inspect", "search", "periods", "references", "formula_pattern", "analogues")
MAX_ROWS = 64
MAX_NEAR = 8
A1 = re.compile(r"^\$?([A-Za-z]{1,3})\$?(\d+)(?::\$?([A-Za-z]{1,3})\$?(\d+))?$")
GOLD_MARKERS = ("golden", "goldens", "/gold/", "_gold.", "evaluator")


def col_letter(col: int) -> str:
    out = ""
    n = int(col)
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def a1(row: int, col: int) -> str:
    return f"{col_letter(col)}{row}"


def parse_a1(text: str) -> tuple[int, int, int, int] | None:
    match = A1.fullmatch((text or "").replace(" ", ""))
    if not match:
        return None
    def num(letters: str) -> int:
        n = 0
        for ch in letters.upper():
            n = n * 26 + ord(ch) - 64
        return n
    c1, r1 = num(match.group(1)), int(match.group(2))
    if match.group(3):
        c2, r2 = num(match.group(3)), int(match.group(4))
        return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)
    return r1, c1, r1, c1


def refuse_gold(path: Path) -> str | None:
    lowered = str(path).replace("\\", "/").lower()
    if any(marker in lowered for marker in GOLD_MARKERS):
        return "GOLD_PATH_REFUSED"
    return None


def _sql(db: Path, query: str) -> dict[str, Any]:
    stripped = query.rstrip().rstrip(";")
    if " limit " not in stripped.lower():
        stripped = f"{stripped} LIMIT {MAX_ROWS}"
    return ReadOnlySqlite(db, max_rows=MAX_ROWS, max_bytes=80_000).execute(stripped)


def _esc(value: Any) -> str:
    return str(value).replace("'", "''")


def compile_world(xlsx: Path, destination: Path) -> dict[str, Any]:
    refused = refuse_gold(xlsx)
    if refused:
        raise RuntimeError(refused)
    destination.mkdir(parents=True, exist_ok=True)
    spine = compile_spine(xlsx, workbook_key=xlsx.stem)
    temporal = compile_temporal_workbook(xlsx, closure=True)
    spine_path = destination / "spine.json"
    temporal_path = destination / "temporal.json"
    db_path = destination / "workbook.sqlite"
    spine_path.write_text(json.dumps(spine, ensure_ascii=False), encoding="utf-8")
    temporal_path.write_text(json.dumps(temporal, ensure_ascii=False), encoding="utf-8")
    if temporal.get("golden_used"):
        raise RuntimeError("GOLD_USED")
    stats = build_database(spine_path, temporal_path, db_path)
    return {"db": str(db_path), "stats": stats, "golden_used": False}


def cached_world(xlsx: Path, cache_root: Path | None = None) -> Path:
    refused = refuse_gold(xlsx)
    if refused:
        raise RuntimeError(refused)
    digest = hashlib.sha256(xlsx.read_bytes()).hexdigest()[:24]
    if cache_root is None:
        env_root = os.environ.get("CALC_QUERY_CACHE_ROOT")
        cache_root = Path(env_root) if env_root else Path(tempfile.gettempdir()) / "calc_query_cache"
    dest = cache_root / digest
    db = dest / "workbook.sqlite"
    if not db.is_file():
        compile_world(xlsx, dest)
    return db


def _sheet_id(db: Path, sheet: str) -> str | None:
    rows = _sql(db, f"SELECT sheet_id, name FROM sheets WHERE name='{_esc(sheet)}'").get("rows") or []
    if rows:
        return rows[0]["sheet_id"]
    return None


def _cell_display(row: dict[str, Any]) -> str:
    sheet = row.get("sheet_name") or row.get("name")
    address = row.get("address")
    if not address and row.get("row_idx") is not None and row.get("col_idx") is not None:
        address = a1(int(row["row_idx"]), int(row["col_idx"]))
    if sheet and address:
        return f"{sheet}!{address}"
    return row.get("cell_id") or ""


def _nearby(db: Path, sheet_id: str, row: int, col: int) -> list[dict[str, Any]]:
    result = _sql(
        db,
        "SELECT c.cell_id, s.name AS sheet_name, c.address, c.kind, c.raw_value, c.row_idx, c.col_idx "
        "FROM cells c JOIN sheets s ON s.sheet_id=c.sheet_id "
        f"WHERE c.sheet_id='{_esc(sheet_id)}' AND c.row_idx BETWEEN {max(1, row-2)} AND {row+2} "
        f"AND c.col_idx BETWEEN {max(1, col-2)} AND {col+2} "
        "AND c.kind='text' ORDER BY c.row_idx, c.col_idx",
    )
    rows = []
    for item in (result.get("rows") or [])[:MAX_NEAR]:
        rows.append({"display": _cell_display(item), "kind": "raw_text", "text": item.get("raw_value"), "cell_id": item.get("cell_id")})
    return rows


def inspect(db: Path, *, sheet: str, target: str) -> dict[str, Any]:
    parsed = parse_a1(target)
    sid = _sheet_id(db, sheet)
    if parsed is None or sid is None:
        return {"mode": "inspect", "status": "NOT_AVAILABLE", "reason": "Sheet or A1 target is not a compiled coordinate", "sheet": sheet, "target": target}
    r1, c1, r2, c2 = parsed
    result = _sql(
        db,
        "SELECT c.cell_id, s.name AS sheet_name, c.address, c.row_idx, c.col_idx, c.kind, c.raw_value, c.display_value, "
        "f.formula_text, f.fingerprint_id, f.opaque "
        "FROM cells c JOIN sheets s ON s.sheet_id=c.sheet_id "
        f"LEFT JOIN formulas f ON f.cell_id=c.cell_id WHERE c.sheet_id='{_esc(sid)}' "
        f"AND c.row_idx BETWEEN {r1} AND {r2} AND c.col_idx BETWEEN {c1} AND {c2} "
        "ORDER BY c.row_idx, c.col_idx",
    )
    cells = []
    for item in result.get("rows") or []:
        cells.append(
            {
                "display": _cell_display(item),
                "cell_id": item.get("cell_id"),
                "kind_raw": item.get("kind"),
                "raw_value": item.get("raw_value"),
                "display_value": item.get("display_value"),
                "formula": item.get("formula_text"),
                "formula_fingerprint_id": item.get("fingerprint_id"),
                "formula_opaque": bool(item.get("opaque")),
                "nearby_labels": _nearby(db, sid, int(item["row_idx"]), int(item["col_idx"])),
            }
        )
    return {"mode": "inspect", "status": result.get("status") or "OK", "fact_kind": "compiled_cell", "truncated": len(cells) >= MAX_ROWS, "cells": cells}


def search(db: Path, *, text: str, sheet: str | None = None) -> dict[str, Any]:
    clause = ""
    if sheet:
        sid = _sheet_id(db, sheet)
        if not sid:
            return {"mode": "search", "status": "NOT_AVAILABLE", "reason": "Sheet is not compiled", "text": text}
        clause = f" AND c.sheet_id='{_esc(sid)}'"
    result = _sql(
        db,
        "SELECT a.anchor_id, a.cell_id, a.exact_text, s.name AS sheet_name, c.address, c.row_idx, c.col_idx, c.sheet_id "
        "FROM text_anchors a JOIN cells c ON c.cell_id=a.cell_id JOIN sheets s ON s.sheet_id=c.sheet_id "
        f"WHERE a.normalized_text LIKE '%' || lower('{_esc(text)}') || '%' {clause} ORDER BY a.anchor_id",
    )
    hits = []
    for item in result.get("rows") or []:
        hits.append(
            {
                "display": _cell_display(item),
                "cell_id": item.get("cell_id"),
                "exact_text": item.get("exact_text"),
                "fact_kind": "raw_text_anchor",
                "nearby_labels": _nearby(db, item["sheet_id"], int(item["row_idx"]), int(item["col_idx"])),
            }
        )
    return {"mode": "search", "status": result.get("status") or "OK", "text": text, "truncated": len(hits) >= MAX_ROWS, "hits": hits}


def periods(db: Path, *, sheet: str | None = None) -> dict[str, Any]:
    clause = ""
    if sheet:
        sid = _sheet_id(db, sheet)
        if not sid:
            return {"mode": "periods", "status": "NOT_AVAILABLE", "reason": "Sheet is not compiled", "sheet": sheet}
        clause = f" WHERE t.sheet_id='{_esc(sid)}'"
    result = _sql(
        db,
        "SELECT t.temporal_id, t.sheet_id, s.name AS sheet_name, t.axis, t.axis_index, t.year, t.month, t.quarter, "
        "t.marker, t.derivation_kind, t.period_key, t.header_text, t.cell_id, c.address, c.row_idx, c.col_idx "
        "FROM temporal_coordinates t JOIN sheets s ON s.sheet_id=t.sheet_id "
        "LEFT JOIN cells c ON c.cell_id=t.cell_id "
        f"{clause} ORDER BY s.sheet_index, t.axis, t.axis_index, t.year, t.month",
    )
    rows = []
    for item in result.get("rows") or []:
        rows.append(
            {
                "display": _cell_display(item) if item.get("address") else f"{item.get('sheet_name')} {item.get('axis')}={item.get('axis_index')}",
                "temporal_id": item.get("temporal_id"),
                "year": item.get("year"),
                "month": item.get("month"),
                "quarter": item.get("quarter"),
                "period_key": item.get("period_key"),
                "header_text": item.get("header_text"),
                "derivation_kind": item.get("derivation_kind"),
                "axis": item.get("axis"),
                "axis_index": item.get("axis_index"),
                "fact_kind": "compiled_temporal_coordinate",
            }
        )
    provenance = _sql(
        db,
        "SELECT temporal_id, step_index, source_cell_id, parent_cell_id, relation_type FROM temporal_provenance ORDER BY temporal_id, step_index",
    )
    sheets = _sql(
        db,
        "SELECT s.name AS sheet_name, COUNT(*) AS n_coordinates FROM temporal_coordinates t "
        "JOIN sheets s ON s.sheet_id=t.sheet_id GROUP BY s.name ORDER BY s.sheet_index",
    )
    status = result.get("status") or "OK"
    truncated = status == "RESULT_TOO_LARGE" or len(rows) >= MAX_ROWS
    if status == "RESULT_TOO_LARGE" and not rows:
        status = "OK"
        truncated = True
    return {
        "mode": "periods",
        "status": status if status != "RESULT_TOO_LARGE" else "OK",
        "truncated": truncated,
        "coordinates": rows,
        "sheet_counts": sheets.get("rows") or [],
        "provenance": (provenance.get("rows") or [])[:MAX_ROWS],
        "note": "These are mechanically compiled period mappings, not edit targets. Results are bounded; pass --sheet to inspect one worksheet.",
        "fact_kind": "compiled_temporal_coordinate",
    }


def references(db: Path, *, sheet: str, target: str) -> dict[str, Any]:
    parsed = parse_a1(target)
    sid = _sheet_id(db, sheet)
    if parsed is None or sid is None or parsed[0] != parsed[2] or parsed[1] != parsed[3]:
        return {"mode": "references", "status": "NOT_AVAILABLE", "reason": "references requires one compiled A1 cell", "sheet": sheet, "target": target}
    row, col = parsed[0], parsed[1]
    cell = _sql(
        db,
        "SELECT c.cell_id, s.name AS sheet_name, c.address, f.formula_id, f.formula_text "
        f"FROM cells c JOIN sheets s ON s.sheet_id=c.sheet_id LEFT JOIN formulas f ON f.cell_id=c.cell_id "
        f"WHERE c.sheet_id='{_esc(sid)}' AND c.row_idx={row} AND c.col_idx={col}",
    )
    if not (cell.get("rows") or []):
        return {"mode": "references", "status": "NOT_AVAILABLE", "reason": "Cell is not occupied in the compiled world", "display": f"{sheet}!{target}"}
    rec = cell["rows"][0]
    cid = rec["cell_id"]
    fid = rec.get("formula_id")
    precedents = []
    if fid:
        points = _sql(
            db,
            "SELECT p.ref_slot, p.referenced_cell_id, p.row_delta, p.col_delta, p.row_absolute, p.col_absolute, p.cross_sheet, "
            "s.name AS sheet_name, c.address FROM point_references p "
            "JOIN cells c ON c.cell_id=p.referenced_cell_id JOIN sheets s ON s.sheet_id=c.sheet_id "
            f"WHERE p.formula_id='{_esc(fid)}' ORDER BY p.ref_slot",
        )
        for item in points.get("rows") or []:
            precedents.append({"kind": "point", "display": _cell_display(item), "cell_id": item.get("referenced_cell_id"), "cross_sheet": bool(item.get("cross_sheet")), "fact_kind": "parsed_reference"})
        ranges = _sql(
            db,
            "SELECT r.ref_slot, r.range_id, r.cross_sheet, g.r1, g.c1, g.r2, g.c2, s.name AS sheet_name "
            "FROM range_references r JOIN ranges g ON g.range_id=r.range_id JOIN sheets s ON s.sheet_id=g.sheet_id "
            f"WHERE r.formula_id='{_esc(fid)}' ORDER BY r.ref_slot",
        )
        for item in ranges.get("rows") or []:
            precedents.append(
                {
                    "kind": "range",
                    "display": f"{item['sheet_name']}!{a1(item['r1'], item['c1'])}:{a1(item['r2'], item['c2'])}",
                    "range_id": item.get("range_id"),
                    "cross_sheet": bool(item.get("cross_sheet")),
                    "fact_kind": "parsed_reference",
                }
            )
    dependents = _sql(
        db,
        "SELECT s.name AS sheet_name, c.address, c.cell_id, p.ref_slot FROM point_references p "
        "JOIN formulas f ON f.formula_id=p.formula_id JOIN cells c ON c.cell_id=f.cell_id JOIN sheets s ON s.sheet_id=c.sheet_id "
        f"WHERE p.referenced_cell_id='{_esc(cid)}' ORDER BY c.row_idx, c.col_idx",
    )
    dep = [{"display": _cell_display(item), "cell_id": item.get("cell_id"), "fact_kind": "parsed_dependent"} for item in dependents.get("rows") or []]
    return {
        "mode": "references",
        "status": "OK",
        "display": _cell_display(rec),
        "formula": rec.get("formula_text"),
        "precedents": precedents,
        "dependents": dep,
        "truncated": len(precedents) >= MAX_ROWS or len(dep) >= MAX_ROWS,
        "note": "Parsed formula references only. Absence is not evidence that a relation does not exist in Excel.",
    }


def formula_pattern(db: Path, *, sheet: str, target: str) -> dict[str, Any]:
    parsed = parse_a1(target)
    sid = _sheet_id(db, sheet)
    if parsed is None or sid is None:
        return {"mode": "formula_pattern", "status": "NOT_AVAILABLE", "reason": "Sheet or A1 target is not compiled"}
    row, col = parsed[0], parsed[1]
    recs = _sql(
        db,
        "SELECT c.cell_id, s.name AS sheet_name, c.address, f.formula_text, f.fingerprint_id, f.opaque, fc.canonical_fingerprint "
        "FROM cells c JOIN sheets s ON s.sheet_id=c.sheet_id LEFT JOIN formulas f ON f.cell_id=c.cell_id "
        "LEFT JOIN formula_classes fc ON fc.fingerprint_id=f.fingerprint_id "
        f"WHERE c.sheet_id='{_esc(sid)}' AND c.row_idx={row} AND c.col_idx={col}",
    ).get("rows") or []
    if not recs or not recs[0].get("formula_text"):
        return {"mode": "formula_pattern", "status": "NOT_AVAILABLE", "reason": "No compiled formula at this cell", "display": f"{sheet}!{target}"}
    rec = recs[0]
    if rec.get("opaque") or not rec.get("fingerprint_id"):
        return {"mode": "formula_pattern", "status": "OPAQUE", "display": _cell_display(rec), "formula": rec.get("formula_text"), "reason": "Formula could not be safely canonicalized"}
    members = _sql(
        db,
        "SELECT s.name AS sheet_name, c.address, c.cell_id, f.formula_text FROM formula_class_members m "
        "JOIN formulas f ON f.formula_id=m.formula_id JOIN cells c ON c.cell_id=f.cell_id JOIN sheets s ON s.sheet_id=c.sheet_id "
        f"WHERE m.fingerprint_id='{_esc(rec['fingerprint_id'])}' ORDER BY s.sheet_index, c.row_idx, c.col_idx",
    )
    return {
        "mode": "formula_pattern",
        "status": "OK",
        "display": _cell_display(rec),
        "formula": rec.get("formula_text"),
        "fingerprint_id": rec.get("fingerprint_id"),
        "canonical_fingerprint": rec.get("canonical_fingerprint"),
        "member_count_returned": len(members.get("rows") or []),
        "members": [{"display": _cell_display(item), "formula": item.get("formula_text"), "cell_id": item.get("cell_id")} for item in (members.get("rows") or [])],
        "truncated": len(members.get("rows") or []) >= MAX_ROWS,
        "note": "Membership is mechanical relative-formula equivalence, not a claim that an adjacent rectangle is homogeneous.",
    }


def analogues(db: Path, *, sheet: str, target: str) -> dict[str, Any]:
    pattern = formula_pattern(db, sheet=sheet, target=target)
    if pattern.get("status") != "OK":
        return {**pattern, "mode": "analogues"}
    return {
        "mode": "analogues",
        "status": "OK",
        "source": pattern["display"],
        "evidence": "same compiled relative-formula fingerprint_id",
        "fingerprint_id": pattern["fingerprint_id"],
        "canonical_fingerprint": pattern.get("canonical_fingerprint"),
        "analogues": [m for m in pattern["members"] if m["display"] != pattern["display"]],
        "truncated": pattern.get("truncated"),
        "note": "Analogues are other members of the same compiled formula class. This is not a recommended edit formula.",
    }


HANDLERS = {
    "inspect": inspect,
    "search": search,
    "periods": periods,
    "references": references,
    "formula_pattern": formula_pattern,
    "analogues": analogues,
}


def run_query(xlsx: Path, mode: str, *, sheet: str | None = None, target: str | None = None, text: str | None = None, cache_root: Path | None = None) -> dict[str, Any]:
    if mode not in MODES:
        return {"status": "NOT_AVAILABLE", "reason": f"Unknown mode {mode!r}. Available: {', '.join(MODES)}"}
    refused = refuse_gold(xlsx)
    if refused:
        return {"status": refused, "reason": "Evaluator gold paths are not queryable"}
    if not xlsx.is_file():
        return {"status": "NOT_AVAILABLE", "reason": f"Workbook not found: {xlsx}"}
    db = cached_world(xlsx, cache_root)
    kwargs: dict[str, Any] = {}
    if mode in {"inspect", "references", "formula_pattern", "analogues"}:
        if not sheet or not target:
            return {"status": "NOT_AVAILABLE", "reason": f"{mode} requires sheet and A1 target"}
        kwargs = {"sheet": sheet, "target": target}
    elif mode == "search":
        if not text:
            return {"status": "NOT_AVAILABLE", "reason": "search requires text"}
        kwargs = {"text": text, "sheet": sheet}
    elif mode == "periods":
        kwargs = {"sheet": sheet}
    payload = HANDLERS[mode](db, **kwargs)
    payload["workbook"] = str(xlsx)
    payload["edit_authority"] = False
    payload["should_edit"] = None
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only compiled workbook query")
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("xlsx")
    parser.add_argument("--sheet")
    parser.add_argument("--target", help="A1 cell or range")
    parser.add_argument("--text")
    args = parser.parse_args(argv)
    payload = run_query(Path(args.xlsx), args.mode, sheet=args.sheet, target=args.target, text=args.text)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"OK", "OPAQUE", None} or payload.get("cells") or payload.get("hits") or payload.get("coordinates") else 0


if __name__ == "__main__":
    raise SystemExit(main())
