"""Model-facing inspection helpers: periods / search / inspect.

Mechanical only. Every call logs workbook/index/query generations and fails
closed on stale or unreadable input. No ranking, recommendations, semantic
claims, or inferred targets are returned.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from benchmark.inspection_helpers.index import ensure_fresh, next_query_id

CAP = 200
CELL_CAP = 2_000
CELL_FIELDS = ("address", "row", "col", "value", "formula", "dtype")


def _log(call: dict) -> None:
    log = os.environ.get("AB_FRESHNESS_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(call) + "\n")


def _gen(path: str) -> tuple[dict, int, bool]:
    h, rebuilt = ensure_fresh(path)
    return h, next_query_id(), rebuilt


def _page(limit: int | None, offset: int, default: int) -> tuple[int, int]:
    if limit is None:
        limit = default
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    return limit, offset


def _compact(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the same cell facts in a lower-overhead positional form."""
    return {
        "fields": list(CELL_FIELDS),
        "cells": [[cell[field] for field in CELL_FIELDS] for cell in cells],
    }


def _inspect_cells(
    h: dict,
    sheet: str,
    cell_range: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], bool]:
    from openpyxl.utils import range_boundaries

    minc, minr, maxc, maxr = range_boundaries(cell_range)
    cur = h["db"].execute(
        "SELECT addr, row, col, value, formula, dtype FROM cells "
        "WHERE sheet = ? AND row BETWEEN ? AND ? AND col BETWEEN ? AND ? "
        "ORDER BY row, col LIMIT ? OFFSET ?",
        (sheet, minr, maxr, minc, maxc, limit + 1, offset),
    )
    rows = [
        {"address": a, "row": r, "col": c, "value": v, "formula": f, "dtype": d}
        for a, r, c, v, f, d in cur.fetchall()
    ]
    return rows[:limit], len(rows) > limit


def _styles(workbook: str, sheet: str, cell_range: str) -> dict[str, dict[str, str | None]]:
    from openpyxl.reader.excel import load_workbook
    from openpyxl.utils import range_boundaries

    minc, minr, maxc, maxr = range_boundaries(cell_range)
    wb = load_workbook(workbook, data_only=False, read_only=False)
    try:
        ws = wb[sheet]
        return {
            cell.coordinate: {
                "number_format": cell.number_format,
                "font": str(cell.font.color.rgb)
                if cell.font.color and cell.font.color.type == "rgb"
                else None,
                "fill": str(cell.fill.fgColor.rgb)
                if cell.fill.fgColor and cell.fill.fgColor.type == "rgb"
                and cell.fill.fgColor.rgb not in (None, "00000000")
                else None,
            }
            for row in ws.iter_rows(min_row=minr, max_row=maxr, min_col=minc, max_col=maxc)
            for cell in row
        }
    finally:
        wb.close()


def periods(
    workbook: str,
    sheet: str | None = None,
    *,
    limit: int = CAP,
    offset: int = 0,
) -> dict:
    """Mechanically recovered period/header coordinates. No task relevance."""
    h, qid, rebuilt = _gen(workbook)
    limit, offset = _page(limit, offset, CAP)
    cur = h["db"].execute(
        "SELECT label, sheet, addr, row, col FROM temporal "
        + ("WHERE sheet = ? " if sheet else "")
        + "ORDER BY sheet, row, col LIMIT ? OFFSET ?",
        (*((sheet,) if sheet else ()), limit + 1, offset),
    )
    raw = cur.fetchall()
    truncated = len(raw) > limit
    rows = [{"label": l, "sheet": s, "address": a, "row": r, "col": c}
            for l, s, a, r, c in raw[:limit]]
    _log({"helper": "periods", "workbook": str(Path(workbook).name),
          "sheet": sheet, "workbook_generation": h["workbook_hash"][:12],
          "index_generation": h["index_generation"], "query_generation": qid,
          "rebuilt": rebuilt, "n_results": len(rows), "truncated": truncated,
          "offset": offset, "limit": limit})
    return {"results": rows, "truncated": truncated,
            "next_offset": offset + limit if truncated else None,
            "index_generation": h["index_generation"]}


def search(
    workbook: str,
    pattern: str,
    regex: bool = False,
    sheet: str | None = None,
    *,
    limit: int = CAP,
    offset: int = 0,
) -> dict:
    """Exact workbook occurrences of text/pattern, in sheet/row/col order."""
    import re as _re

    h, qid, rebuilt = _gen(workbook)
    limit, offset = _page(limit, offset, CAP)
    if not regex:
        cur = h["db"].execute(
            "SELECT a.sheet, a.addr, c.value, c.formula FROM anchors a "
            "JOIN cells c ON c.sheet=a.sheet AND c.addr=a.addr "
            "WHERE a.term = ?" + (" AND a.sheet = ?" if sheet else "")
            + " ORDER BY c.sheet, c.row, c.col LIMIT ? OFFSET ?",
            [pattern.lower(), *([sheet] if sheet else []), limit + 1, offset],
        )
        raw = cur.fetchall()
    else:
        rx = _re.compile(pattern)
        cur = h["db"].execute(
            "SELECT sheet, addr, value, formula FROM cells"
            + (" WHERE sheet = ?" if sheet else "")
            + " ORDER BY sheet, row, col",
            ((sheet,) if sheet else ()),
        )
        matches = []
        for row in cur:
            if (row[2] and rx.search(row[2])) or (row[3] and rx.search(row[3])):
                matches.append(row)
                if len(matches) >= offset + limit + 1:
                    break
        raw = matches[offset:offset + limit + 1]
    out = [{"sheet": s, "address": a, "value": v, "formula": f}
           for s, a, v, f in raw[:limit]]
    truncated = len(raw) > limit
    _log({"helper": "search", "workbook": str(Path(workbook).name),
          "pattern": pattern[:80], "regex": regex, "sheet": sheet,
          "workbook_generation": h["workbook_hash"][:12],
          "index_generation": h["index_generation"], "query_generation": qid,
          "rebuilt": rebuilt, "n_results": len(out), "truncated": truncated,
          "offset": offset, "limit": limit})
    return {"results": out, "truncated": truncated,
            "next_offset": offset + limit if truncated else None,
            "index_generation": h["index_generation"]}


def inspect(
    workbook: str,
    sheet: str,
    cell_range: str,
    with_styles: bool = False,
    *,
    limit: int = CELL_CAP,
    offset: int = 0,
    compact: bool = False,
) -> dict:
    """Deterministic state for an explicitly requested sheet/range.

    The result reports truncation and supports paging; older callers keep the
    original verbose result shape unless ``compact=True`` is requested.
    """
    h, qid, rebuilt = _gen(workbook)
    limit, offset = _page(limit, offset, CELL_CAP)
    cells, truncated = _inspect_cells(h, sheet, cell_range, limit=limit, offset=offset)
    styles = _styles(workbook, sheet, cell_range) if with_styles else None
    _log({"helper": "inspect", "workbook": str(Path(workbook).name),
          "sheet": sheet, "range": cell_range, "with_styles": with_styles,
          "workbook_generation": h["workbook_hash"][:12],
          "index_generation": h["index_generation"], "query_generation": qid,
          "rebuilt": rebuilt, "n_results": len(cells), "truncated": truncated,
          "offset": offset, "limit": limit})
    return {"results": _compact(cells) if compact else cells,
            "styles": styles, "truncated": truncated,
            "next_offset": offset + limit if truncated else None,
            "index_generation": h["index_generation"]}


def inspect_ranges(
    workbook: str,
    ranges: list[dict[str, str] | tuple[str, str]],
    *,
    with_styles: bool = False,
    max_cells: int = CELL_CAP,
) -> dict:
    """Read several explicit ranges with one freshness lookup and one log event.

    Results are compact positional cell facts. ``max_cells`` is a total output
    budget, so this helper cannot accidentally return a huge multi-range dump.
    It never infers sheets, ranges, or task relevance.
    """
    if not isinstance(ranges, list) or not ranges:
        raise ValueError("ranges must be a non-empty list")
    max_cells, _ = _page(max_cells, 0, CELL_CAP)
    h, qid, rebuilt = _gen(workbook)
    out: list[dict[str, Any]] = []
    remaining = max_cells
    for request in ranges:
        if isinstance(request, dict):
            sheet = request.get("sheet")
            cell_range = request.get("range")
        elif isinstance(request, (tuple, list)) and len(request) == 2:
            sheet, cell_range = request
        else:
            raise ValueError("each range must be {'sheet': ..., 'range': ...}")
        if not isinstance(sheet, str) or not isinstance(cell_range, str):
            raise TypeError("each range requires string sheet and range")
        if remaining <= 0:
            out.append({"sheet": sheet, "range": cell_range,
                        **_compact([]), "truncated": True, "next_offset": 0})
            continue
        cells, truncated = _inspect_cells(
            h, sheet, cell_range, limit=remaining, offset=0
        )
        item: dict[str, Any] = {
            "sheet": sheet,
            "range": cell_range,
            **_compact(cells),
            "truncated": truncated,
            "next_offset": len(cells) if truncated else None,
        }
        if with_styles:
            item["styles"] = _styles(workbook, sheet, cell_range)
        out.append(item)
        remaining -= len(cells)
    _log({"helper": "inspect_ranges", "workbook": str(Path(workbook).name),
          "ranges": [{"sheet": r["sheet"], "range": r["range"]} for r in out],
          "with_styles": with_styles, "workbook_generation": h["workbook_hash"][:12],
          "index_generation": h["index_generation"], "query_generation": qid,
          "rebuilt": rebuilt, "n_ranges": len(out),
          "n_results": sum(len(r["cells"]) for r in out), "max_cells": max_cells})
    return {"results": out, "index_generation": h["index_generation"],
            "max_cells": max_cells}


# Historical substrate API: retained for evidence reproduction only. Active
# lx_helpers uses reference_api. Even direct historical callers fail closed.
def _reference_on_disabled(fn):
    from functools import wraps
    from benchmark.inspection_helpers.index import SubstrateDisabled

    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except SubstrateDisabled:
            from benchmark.inspection_helpers import reference_api
            return getattr(reference_api, fn.__name__)(*args, **kwargs)
    return call


periods = _reference_on_disabled(periods)
search = _reference_on_disabled(search)
inspect = _reference_on_disabled(inspect)
inspect_ranges = _reference_on_disabled(inspect_ranges)
