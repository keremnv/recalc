"""Closed-world mechanical WORKBOOK_GROUNDING_SPINE.

Compile an input workbook into a deterministic universe of entity IDs.
No finance ontology, no goldens, no LLM. Blank cells inside a sheet's
occupancy bounding box are addressable even when not serialized as payloads.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from fingerprint import a1_address, column_number, formula_text, relative_fingerprint
from formula_schema import as_text, normalize_text, parse_period, period_key
from formula_target_selection import occupancy_from_grid, select_s1
from formula_completion_certs import SheetGrid, load_grids
from librecalc_mcp.domain.formulas import formula_a1_references
from xlsx_metadata_repair import install

install()
import openpyxl  # noqa: E402

_PUNCT = re.compile(r"[^\w\s]+", re.UNICODE)
_WS = re.compile(r"\s+")
_ERROR = re.compile(r"^#(N/?A|VALUE!|REF!|DIV/0!|NAME\?|NULL!|NUM!|GETTING_DATA)", re.I)

RETRIEVAL_RULES = {
    "sheet": (
        "exact title; normalize_text; compact (whitespace/punct stripped); "
        "title initials (all tokens, and prefixes length>=2); token Jaccard>=0.40; "
        "all query tokens subset of title tokens"
    ),
    "subject": (
        "exact; normalize; compact; substring if query length>=4; "
        "token Jaccard>=0.40; query tokens subset of anchor tokens"
    ),
    "scope": "parse explicit period tokens; match every compatible period header",
    "source": "same conservative text-anchor procedure as subject",
    "top_k": False,
    "learned_ranker": False,
    "gold_filter": False,
    "finance_synonyms": False,
}

JACCARD_MIN = 0.40


def compact_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "", normalize_text(text))


def title_initials(text: str | None) -> list[str]:
    toks = [t for t in normalize_text(text or "").split() if t]
    if len(toks) < 2:
        return []
    full = "".join(t[0] for t in toks if t)
    out = []
    if len(full) >= 2:
        out.append(full)
        for n in range(2, len(full)):
            out.append(full[:n])
    return out


def tokens_of(text: str | None) -> set[str]:
    return {t for t in normalize_text(text or "").split() if t}


def sheet_id(index: int) -> str:
    return f"sheet:s{index:02d}"


def cell_id(index: int, row: int, col: int) -> str:
    return f"cell:s{index:02d}:r{row}:c{col}"


def row_id(index: int, row: int) -> str:
    return f"row:s{index:02d}:r{row}"


def col_id(index: int, col: int) -> str:
    return f"col:s{index:02d}:c{col}"


def text_id(index: int, row: int, col: int) -> str:
    return f"text:s{index:02d}:r{row}:c{col}"


def formula_id(index: int, row: int, col: int) -> str:
    return f"formula:s{index:02d}:r{row}:c{col}"


def class_id(eq: str) -> str:
    return f"formula_class:{eq}"


def period_id(index: int, row: int, col: int) -> str:
    return f"period:s{index:02d}:r{row}:c{col}"


def region_id(kind: str, n: int) -> str:
    return f"region:{kind}:{n}"


def workbook_id(task_id: str) -> str:
    return f"wb:{task_id}"


def _kind(value: object) -> str:
    if value is None:
        return "blank"
    if isinstance(value, str) and not value.strip():
        return "blank"
    text = formula_text(value)
    if text:
        if _ERROR.match(text.lstrip("=")):
            return "error"
        return "formula"
    if isinstance(value, str) and _ERROR.match(value.strip()):
        return "error"
    if isinstance(value, bool):
        return "numeric"
    if isinstance(value, (int, float)):
        return "numeric"
    if as_text(value):
        return "text"
    return "numeric"


def _payload(value: object, kind: str) -> str | int | float | bool | None:
    if kind == "formula" or kind == "error":
        return formula_text(value) or (str(value) if value is not None else None)
    if kind == "text":
        return as_text(value)
    if kind == "numeric":
        return value if isinstance(value, (int, float, bool)) else None
    return None


def compile_spine(path: Path, *, workbook_key: str) -> dict[str, Any]:
    """Compile a closed entity universe from an INPUT workbook."""
    unsupported: list[str] = []
    try:
        workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    except Exception as exc:
        return {
            "workbook_id": workbook_id(workbook_key),
            "path": str(path),
            "readable": False,
            "unsupported": [type(exc).__name__],
            "error": str(exc)[:300],
            "sheets": [],
            "ids": [],
        }
    try:
        return _compile_open(workbook, path, workbook_key, unsupported)
    finally:
        workbook.close()


def _compile_open(
    workbook: Any,
    path: Path,
    workbook_key: str,
    unsupported: list[str],
) -> dict[str, Any]:
    wb_id = workbook_id(workbook_key)
    sheets: list[dict[str, Any]] = []
    title_to_index: dict[str, int] = {}
    occupied: dict[tuple[int, int, int], dict[str, Any]] = {}
    text_anchors: list[dict[str, Any]] = []
    periods: list[dict[str, Any]] = []
    formulas: list[dict[str, Any]] = []
    point_deps: list[dict[str, Any]] = []
    range_deps: list[dict[str, Any]] = []
    merges: list[dict[str, Any]] = []
    hidden_rows: list[str] = []
    hidden_cols: list[str] = []
    named_ranges: list[dict[str, Any]] = []
    class_members: dict[str, list[str]] = defaultdict(list)
    row_meta: dict[tuple[int, int], dict[str, Any]] = {}
    col_meta: dict[tuple[int, int], dict[str, Any]] = {}

    defined = getattr(workbook, "defined_names", None)
    if defined is not None:
        try:
            for name in defined:
                dest = None
                try:
                    dest = defined[name].attr_text if hasattr(defined[name], "attr_text") else str(defined[name])
                except Exception:
                    dest = str(name)
                named_ranges.append({"name": getattr(name, "name", str(name)), "attr": str(dest)[:200]})
        except Exception:
            unsupported.append("named_ranges_unreadable")

    for s_i, sheet in enumerate(workbook.worksheets):
        sid = sheet_id(s_i)
        title_to_index[sheet.title] = s_i
        visible = getattr(sheet, "sheet_state", "visible") or "visible"
        min_col = min_row = None
        max_col = max_row = None
        n_written = 0
        merge_origin: dict[tuple[int, int], tuple[int, int]] = {}
        merge_spans: list[tuple[int, int, int, int]] = []
        for rng in sheet.merged_cells.ranges:
            span = (int(rng.min_col), int(rng.min_row), int(rng.max_col), int(rng.max_row))
            merge_spans.append(span)
            merges.append(
                {
                    "id": f"merge:s{s_i:02d}:{span[0]}:{span[1]}:{span[2]}:{span[3]}",
                    "sheet_id": sid,
                    "span": span,
                }
            )
            for col in range(span[0], span[2] + 1):
                for row in range(span[1], span[3] + 1):
                    merge_origin[(col, row)] = (span[0], span[1])
        for cell in sheet._cells.values():
            col, row = int(cell.column), int(cell.row)
            min_col = col if min_col is None else min(min_col, col)
            max_col = col if max_col is None else max(max_col, col)
            min_row = row if min_row is None else min(min_row, row)
            max_row = row if max_row is None else max(max_row, row)
            n_written += 1
            kind = _kind(cell.value)
            rec = {
                "id": cell_id(s_i, row, col),
                "sheet_id": sid,
                "col": col,
                "row": row,
                "address": a1_address(col, row),
                "kind": kind,
            }
            payload = _payload(cell.value, kind)
            if payload is not None:
                rec["payload"] = payload[:500] if isinstance(payload, str) else payload
            occupied[(s_i, row, col)] = rec
            rm = row_meta.setdefault(
                (s_i, row),
                {"id": row_id(s_i, row), "sheet_id": sid, "row": row, "n_text": 0, "n_formula": 0, "n_value": 0, "n_blank": 0, "anchors": []},
            )
            cm = col_meta.setdefault(
                (s_i, col),
                {"id": col_id(s_i, col), "sheet_id": sid, "col": col, "n_text": 0, "n_formula": 0, "n_value": 0, "anchors": [], "periods": []},
            )
            if kind == "text":
                rm["n_text"] += 1
                cm["n_text"] += 1
            elif kind == "formula":
                rm["n_formula"] += 1
                cm["n_formula"] += 1
            elif kind == "blank":
                rm["n_blank"] += 1
            else:
                rm["n_value"] += 1
                cm["n_value"] = cm.get("n_value", 0) + 1
            if kind == "text" and payload:
                origin = merge_origin.get((col, row), (col, row))
                tid = text_id(s_i, origin[1], origin[0])
                anchor = {
                    "id": tid,
                    "cell_id": cell_id(s_i, origin[1], origin[0]),
                    "sheet_id": sid,
                    "row_id": row_id(s_i, origin[1]),
                    "col_id": col_id(s_i, origin[0]),
                    "row": origin[1],
                    "col": origin[0],
                    "address": a1_address(origin[0], origin[1]),
                    "text": payload,
                    "text_norm": normalize_text(payload),
                    "text_compact": compact_text(payload),
                    "merged": (col, row) in merge_origin,
                }
                text_anchors.append(anchor)
                rm["anchors"].append(tid)
                cm["anchors"].append(tid)
            period = parse_period(cell.value) if kind != "formula" else None
            if period:
                pid = period_id(s_i, row, col)
                periods.append(
                    {
                        "id": pid,
                        "cell_id": rec["id"],
                        "sheet_id": sid,
                        "row_id": row_id(s_i, row),
                        "col_id": col_id(s_i, col),
                        "row": row,
                        "col": col,
                        "address": rec["address"],
                        "period": period,
                        "period_key": period_key(period),
                        "header_text": payload if kind == "text" else (str(cell.value) if cell.value is not None else None),
                    }
                )
                cm["periods"].append(pid)
            if kind == "formula" and payload:
                fp = relative_fingerprint(payload, col, row, sheet=sheet.title)
                fid = formula_id(s_i, row, col)
                cid = class_id(fp.eq_id)
                formulas.append(
                    {
                        "id": fid,
                        "cell_id": rec["id"],
                        "sheet_id": sid,
                        "row_id": row_id(s_i, row),
                        "col_id": col_id(s_i, col),
                        "formula": payload[:400],
                        "fingerprint": fp.text[:200],
                        "class_id": cid,
                        "opaque": fp.opaque,
                    }
                )
                if not fp.opaque:
                    class_members[cid].append(fid)
                known = set(title_to_index) | {sheet.title}
                for ref_sheet, start, end in formula_a1_references(payload):
                    host = ref_sheet or sheet.title
                    # sheet index may not be known yet if forward-ref; record title
                    dep = {
                        "consumer_id": rec["id"],
                        "consumer_formula_id": fid,
                        "source_sheet_title": host,
                        "start": start,
                        "end": end,
                        "cross_sheet": host != sheet.title,
                    }
                    if end:
                        range_deps.append({**dep, "type": "RANGE_REFERENCE"})
                    else:
                        point_deps.append({**dep, "type": "POINT_REFERENCE"})
        for row, dim in (sheet.row_dimensions or {}).items():
            if getattr(dim, "hidden", False):
                hidden_rows.append(row_id(s_i, int(row)))
        for col, dim in (sheet.column_dimensions or {}).items():
            if getattr(dim, "hidden", False):
                try:
                    from fingerprint import column_number

                    hidden_cols.append(col_id(s_i, column_number(str(col))))
                except Exception:
                    unsupported.append("hidden_col_parse")
        sheets.append(
            {
                "id": sid,
                "index": s_i,
                "title": sheet.title,
                "title_norm": normalize_text(sheet.title),
                "title_compact": compact_text(sheet.title),
                "initials": title_initials(sheet.title),
                "visibility": visible,
                "bounds": {
                    "min_col": min_col or 1,
                    "max_col": max_col or 1,
                    "min_row": min_row or 1,
                    "max_row": max_row or 1,
                },
                "n_written": n_written,
            }
        )

    # Resolve dependency source cell ids now that all titles are known.
    def _resolve_addr(title: str, addr: str) -> str | None:
        s_i = title_to_index.get(title)
        if s_i is None:
            return None
        from fingerprint import column_number as _cn

        m = re.match(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)", addr)
        if not m:
            return None
        col = _cn(m.group(1))
        row = int(m.group(2))
        return cell_id(s_i, row, col)

    for dep in point_deps:
        dep["source_id"] = _resolve_addr(dep["source_sheet_title"], dep["start"])
        dep["same_sheet"] = not dep["cross_sheet"]
    for dep in range_deps:
        dep["source_start_id"] = _resolve_addr(dep["source_sheet_title"], dep["start"])
        dep["source_end_id"] = _resolve_addr(dep["source_sheet_title"], dep["end"] or dep["start"])
        dep["same_sheet"] = not dep["cross_sheet"]

    # Neighbors for text anchors (same row left/right).
    by_row: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for anchor in text_anchors:
        by_row[(anchor["row"], anchor["sheet_id"])].append(anchor)
    for group in by_row.values():
        group.sort(key=lambda a: a["col"])
        for i, anchor in enumerate(group):
            left = group[i - 1]["text"] if i else None
            right = group[i + 1]["text"] if i + 1 < len(group) else None
            anchor["neighbor_left"] = left
            anchor["neighbor_right"] = right

    # Formula-equivalence runs as regions.
    regions: list[dict[str, Any]] = []
    n_region = 0
    by_class_row: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for form in formulas:
        if form["opaque"]:
            continue
        m = re.match(r"cell:s(\d+):r(\d+):c(\d+)", form["cell_id"])
        if not m:
            continue
        by_class_row[(form["class_id"], form["sheet_id"])].append(
            {"row": int(m.group(2)), "col": int(m.group(3)), "id": form["id"]}
        )
    for (cid, sid), members in by_class_row.items():
        by_r: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in members:
            by_r[item["row"]].append(item)
        for row, items in by_r.items():
            items.sort(key=lambda x: x["col"])
            run = [items[0]]
            for item in items[1:]:
                if item["col"] == run[-1]["col"] + 1:
                    run.append(item)
                else:
                    if len(run) >= 2:
                        n_region += 1
                        regions.append(
                            {
                                "id": region_id("eq_run", n_region),
                                "kind": "formula_equivalence_run",
                                "sheet_id": sid,
                                "class_id": cid,
                                "row": row,
                                "cols": [x["col"] for x in run],
                                "member_ids": [x["id"] for x in run],
                            }
                        )
                    run = [item]
            if len(run) >= 2:
                n_region += 1
                regions.append(
                    {
                        "id": region_id("eq_run", n_region),
                        "kind": "formula_equivalence_run",
                        "sheet_id": sid,
                        "class_id": cid,
                        "row": row,
                        "cols": [x["col"] for x in run],
                        "member_ids": [x["id"] for x in run],
                    }
                )

    # S1 holes via occupancy grids (second lightweight pass over already-open data).
    # Reconstruct SheetGrid-like occupancy from occupied map.
    s1_cells: list[str] = []
    from formula_target_selection import OccupancyGrid

    for s_i, sheet_rec in enumerate(sheets):
        cells_k = {}
        for (si, row, col), rec in occupied.items():
            if si != s_i:
                continue
            kind = rec["kind"]
            if kind == "formula":
                # opaque vs supported: look up formula list
                cells_k[(col, row)] = "F"
            elif kind == "blank":
                continue
            else:
                cells_k[(col, row)] = "V"
        for form in formulas:
            m = re.match(r"cell:s(\d+):r(\d+):c(\d+)", form["cell_id"])
            if not m or int(m.group(1)) != s_i:
                continue
            cells_k[(int(m.group(3)), int(m.group(2)))] = "O" if form["opaque"] else "F"
        if not cells_k:
            continue
        b = sheet_rec["bounds"]
        grid = OccupancyGrid(
            title=sheet_rec["title"],
            min_col=b["min_col"],
            max_col=b["max_col"],
            min_row=b["min_row"],
            max_row=b["max_row"],
            cells=cells_k,
        )
        for hit in select_s1(grid):
            s1_cells.append(cell_id(s_i, hit.row, hit.col))

    id_index = set()
    id_index.add(wb_id)
    for rec in sheets:
        id_index.add(rec["id"])
    for rec in occupied.values():
        id_index.add(rec["id"])
    for rec in text_anchors:
        id_index.add(rec["id"])
    for rec in periods:
        id_index.add(rec["id"])
    for rec in formulas:
        id_index.add(rec["id"])
        id_index.add(rec["class_id"])
    for rec in row_meta.values():
        id_index.add(rec["id"])
    for rec in col_meta.values():
        id_index.add(rec["id"])
    for rec in regions:
        id_index.add(rec["id"])
    for rec in merges:
        id_index.add(rec["id"])
    id_index.update(s1_cells)
    id_index.update(hidden_rows)
    id_index.update(hidden_cols)

    classes = [
        {"id": cid, "n": len(members), "sample_ids": members[:8]}
        for cid, members in sorted(class_members.items(), key=lambda kv: -len(kv[1]))
    ]

    payload_rows = [
        {"id": rec.get("id"), "kind": rec.get("kind"), "payload": rec.get("payload")}
        for rec in sorted(occupied.values(), key=lambda item: item["id"])
    ]
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    payload_sha256 = hashlib.sha256(
        json.dumps(payload_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "workbook_id": wb_id,
        "path": str(path),
        "readable": True,
        "unsupported": unsupported,
        "n_named_ranges": len(named_ranges),
        "named_ranges": named_ranges[:50],
        "sheets": sheets,
        "title_to_index": title_to_index,
        "occupied": list(occupied.values()),
        "text_anchors": text_anchors,
        "periods": periods,
        "formulas": formulas,
        "formula_classes": classes,
        "class_members": {k: v for k, v in class_members.items()},
        "point_deps": point_deps,
        "range_deps": range_deps,
        "rows": list(row_meta.values()),
        "cols": list(col_meta.values()),
        "regions": regions,
        "merges": merges,
        "hidden_rows": hidden_rows,
        "hidden_cols": hidden_cols,
        "s1_cell_ids": s1_cells,
        "id_index": sorted(id_index),
        "stats": {
            "n_sheets": len(sheets),
            "n_occupied": len(occupied),
            "n_text_anchors": len(text_anchors),
            "n_periods": len(periods),
            "n_formulas": len(formulas),
            "n_formula_classes": len(classes),
            "n_point_deps": len(point_deps),
            "n_range_deps": len(range_deps),
            "n_rows": len(row_meta),
            "n_cols": len(col_meta),
            "n_regions": len(regions),
            "n_s1": len(s1_cells),
            "n_ids": len(id_index),
        },
        "lineage": {
            "source_sha256": source_sha256,
            "payload_sha256": payload_sha256,
            "payload_contract": "occupied.id/kind/payload sorted by id",
        },
    }


def cell_in_bounds(spine: dict[str, Any], sheet_index: int, row: int, col: int) -> bool:
    if sheet_index < 0 or sheet_index >= len(spine.get("sheets") or []):
        return False
    b = spine["sheets"][sheet_index]["bounds"]
    return b["min_col"] <= col <= b["max_col"] and b["min_row"] <= row <= b["max_row"]


def parse_cell_id(eid: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", eid)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def rebuild_id_set(spine: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    if spine.get("workbook_id"):
        ids.add(spine["workbook_id"])
    for rec in spine.get("sheets") or []:
        ids.add(rec["id"])
    for rec in spine.get("occupied") or []:
        ids.add(rec["id"])
    for rec in spine.get("text_anchors") or []:
        ids.add(rec["id"])
        ids.add(rec.get("cell_id") or "")
        ids.add(rec.get("row_id") or "")
        ids.add(rec.get("col_id") or "")
    for rec in spine.get("periods") or []:
        ids.add(rec["id"])
    for rec in spine.get("formulas") or []:
        ids.add(rec["id"])
        ids.add(rec.get("class_id") or "")
    for rec in spine.get("rows") or []:
        ids.add(rec["id"])
    for rec in spine.get("cols") or []:
        ids.add(rec["id"])
    for rec in spine.get("regions") or []:
        ids.add(rec["id"])
    ids.update(spine.get("s1_cell_ids") or [])
    ids.discard("")
    spine["_id_set"] = ids
    return ids


def id_in_spine(spine: dict[str, Any], eid: str) -> bool:
    if not eid:
        return False
    index = spine.get("_id_set")
    if index is None:
        index = rebuild_id_set(spine)
    if eid in index:
        return True
    parsed = parse_cell_id(eid)
    if parsed:
        s_i, row, col = parsed
        return cell_in_bounds(spine, s_i, row, col)
    return False


def sheet_cell_id(spine: dict[str, Any], title: str, row: int, col: int) -> str | None:
    s_i = (spine.get("title_to_index") or {}).get(title)
    if s_i is None:
        return None
    eid = cell_id(s_i, row, col)
    if id_in_spine(spine, eid):
        return eid
    return None
