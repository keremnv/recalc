"""Frozen formula-provenance walker for temporal-spine misses.

Gold-blind. Walks backward from header cells through a tiny set of
supported formula edges. Does not write coordinates, change retrieval,
or synthesize formulas.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from fingerprint import a1_address, column_number, formula_text
from formula_schema import parse_period, period_key
from librecalc_mcp.domain.formulas import formula_a1_references
from temporal_spine import (
    HEADER_COL_CAP,
    HEADER_ROW_CAP,
    _fy_loose,
    _merge_map,
    snapshot_cell,
)
from xlsx_metadata_repair import install

install()
from openpyxl.styles.numbers import is_date_format  # noqa: E402
from openpyxl.utils.datetime import from_excel  # noqa: E402

MAX_DEPTH = 6
MAX_VISITED_CLOSURE = 256
SCHEMA = "TEMPORAL_PROVENANCE_PREFLIGHT_V1"
SCHEMA_DEPTH = "TEMPORAL_PROVENANCE_DEPTH_V1"

PRIMARY_RESULTS = (
    "REACHABLE_TEMPORAL_SEED",
    "OPAQUE_PATH",
    "NO_TEMPORAL_SEED",
    "NO_HEADER_CANDIDATE",
    "CYCLE",
    "DEPTH_LIMIT",
)
PATH_TYPES = (
    "DIRECT_CROSS_SHEET",
    "SAME_SHEET_TRANSFORM",
    "CROSS_SHEET_THEN_TRANSFORM",
    "TRANSFORM_THEN_CROSS_SHEET",
    "MULTIHOP_REFERENCE",
    "OTHER_SUPPORTED_COMPOSITION",
)
SEED_TYPES = (
    "EXISTING_COORDINATE",
    "DATETIME_SEED",
    "FY_SEED",
    "MONTH_YEAR_SEED",
    "QUARTER_SEED",
    "YEAR_SEED",
)

_OPAQUE_FN = re.compile(
    r"\b(?:INDIRECT|OFFSET|INDEX|MATCH|XLOOKUP|VLOOKUP|HLOOKUP|LOOKUP|"
    r"IF|IFS|SWITCH|CHOOSE|TEXTJOIN|CONCATENATE|CONCAT|TEXT|DATEVALUE|"
    r"YEAR|MONTH|DAY|WEEKDAY|NETWORKDAYS|WORKDAY|SUM|AVERAGE|SUMPRODUCT|"
    r"MIN|MAX|IFERROR|IFNA|AGGREGATE|INDEX)\s*\(",
    re.I,
)
_DIRECT = re.compile(
    r"^(?:(?:'([^']+)'|([A-Za-z0-9_. ]+))!)?(\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)$"
)
_E2 = re.compile(
    r"^\s*(?:_xlfn\.)?(EDATE|EOMONTH)\(\s*"
    r"(?:(?:'([^']+)'|([A-Za-z0-9_. ]+))!)?"
    r"(\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)\s*,\s*(-?\d+)\s*\)\s*$",
    re.I,
)
_DATE_LIT = re.compile(
    r"^\s*(?:_xlfn\.)?DATE\(\s*(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})\s*\)\s*$",
    re.I,
)
_E3 = re.compile(
    r"^(?:(?:'([^']+)'|([A-Za-z0-9_. ]+))!)?(\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)"
    r"\s*([+-])\s*(\d+)$"
)
_A1 = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$")
_FY_HINT = re.compile(r"\b(?:fy|fye|cy)\b", re.I)
_QUARTER_HINT = re.compile(r"\bq\s*[1-4]\b", re.I)
_YEAR_HINT = re.compile(r"\b(?:19|20)\d{2}\b")
_MONTH_HINT = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b",
    re.I,
)


def strip_formula_body(formula: str) -> str:
    text = formula.strip()
    if text.startswith("="):
        text = text[1:]
    text = text.strip()
    while text.startswith("+"):
        text = text[1:].strip()
    return text


def _parse_a1(addr: str) -> tuple[int, int] | None:
    match = _A1.match(addr.replace("$", ""))
    if not match:
        return None
    return column_number(match.group(1)), int(match.group(2))


def _ref_payload(sheet_q: str | None, sheet_u: str | None, addr: str) -> dict[str, Any] | None:
    parsed = _parse_a1(addr)
    if not parsed:
        return None
    col, row = parsed
    sheet = sheet_q if sheet_q is not None else sheet_u
    return {
        "sheet": sheet,
        "col": col,
        "row": row,
        "address": a1_address(col, row),
    }


def classify_formula(formula: str) -> dict[str, Any]:
    """Classify a formula as E1 / E2 / E3 / LITERAL_DATE / OPAQUE."""
    raw = formula if isinstance(formula, str) else str(formula)
    body = strip_formula_body(raw)
    if not body:
        return {"kind": "OPAQUE", "reason": "empty"}
    if "&" in body:
        return {"kind": "OPAQUE", "reason": "concat"}
    if _OPAQUE_FN.search(body):
        return {"kind": "OPAQUE", "reason": "unsupported_function"}

    match = _DATE_LIT.match(body)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 1990 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return {
                "kind": "LITERAL_DATE",
                "year": year,
                "month": month,
                "day": day,
                "refs": [],
            }
        return {"kind": "OPAQUE", "reason": "date_out_of_range"}

    match = _E2.match(body)
    if match:
        ref = _ref_payload(match.group(2), match.group(3), match.group(4))
        if ref:
            return {
                "kind": "E2",
                "transform": match.group(1).upper(),
                "offset": int(match.group(5)),
                "refs": [ref],
            }

    match = _E3.match(body)
    if match:
        ref = _ref_payload(match.group(1), match.group(2), match.group(3))
        if ref:
            sign = 1 if match.group(4) == "+" else -1
            return {
                "kind": "E3",
                "transform": "SAFE_DATE_OFFSET",
                "offset": sign * int(match.group(5)),
                "refs": [ref],
            }

    match = _DIRECT.match(body)
    if match:
        ref = _ref_payload(match.group(1), match.group(2), match.group(3))
        if ref:
            refs = formula_a1_references("=" + body)
            if len(refs) == 1 and refs[0][2] is None:
                return {"kind": "E1", "transform": None, "offset": None, "refs": [ref]}

    refs = formula_a1_references("=" + body)
    if not refs:
        return {"kind": "OPAQUE", "reason": "named_range_or_literal"}
    if any(end is not None for _sheet, _start, end in refs) or len(refs) > 1:
        return {"kind": "OPAQUE", "reason": "multi_cell_or_range"}
    return {"kind": "OPAQUE", "reason": "arbitrary_formula"}


def _temporal_text_kind(text: str) -> str | None:
    compact = text.strip()
    if not compact:
        return None
    fy = _fy_loose(compact)
    if fy and _FY_HINT.search(compact):
        return "FY_SEED"
    parsed = parse_period(compact)
    if not parsed:
        fy = _fy_loose(compact)
        if fy:
            return "FY_SEED"
        return None
    if "quarter" in parsed and "year" in parsed:
        return "QUARTER_SEED"
    if "month" in parsed and "year" in parsed:
        return "MONTH_YEAR_SEED"
    if "quarter" in parsed:
        return "QUARTER_SEED"
    if parsed.get("year") and _FY_HINT.search(compact):
        return "FY_SEED"
    if parsed.get("year"):
        return "YEAR_SEED"
    if parsed.get("month") and _MONTH_HINT.search(compact):
        return None
    return None


def classify_seed(
    snap: dict[str, Any],
    *,
    sheet_title: str,
    coord_index: dict[tuple[str, int, int], dict[str, Any]] | None = None,
    epoch: Any = None,
) -> dict[str, Any] | None:
    """Return a seed record if this cell is already a recoverable temporal seed."""
    title_key = sheet_title
    exact = (coord_index or {}).get((title_key, int(snap["col"]), int(snap["row"])))
    if exact is None:
        exact = (coord_index or {}).get((title_key.strip(), int(snap["col"]), int(snap["row"])))
    if exact is not None:
        return {
            "seed_type": "EXISTING_COORDINATE",
            "period": exact.get("period"),
            "coord_id": exact.get("id"),
            "cell": f"{sheet_title}!{snap['address']}",
        }

    formula = snap.get("formula")
    if formula:
        edge = classify_formula(formula)
        if edge["kind"] == "LITERAL_DATE":
            return {
                "seed_type": "DATETIME_SEED",
                "period": {"year": edge["year"], "month": edge["month"]},
                "cell": f"{sheet_title}!{snap['address']}",
            }
        return None

    if snap.get("kind") == "datetime" and snap.get("dt"):
        return {
            "seed_type": "DATETIME_SEED",
            "period": {"year": snap["dt"]["year"], "month": snap["dt"]["month"]},
            "cell": f"{sheet_title}!{snap['address']}",
        }

    if snap.get("kind") == "number" and snap.get("is_date_format"):
        raw = snap.get("raw")
        if isinstance(raw, (int, float)) and 1 <= float(raw) <= 80000:
            try:
                parsed = from_excel(float(raw), epoch=epoch) if epoch is not None else from_excel(float(raw))
            except Exception:
                parsed = None
            if parsed is not None and hasattr(parsed, "year"):
                return {
                    "seed_type": "DATETIME_SEED",
                    "period": {"year": int(parsed.year), "month": int(parsed.month)},
                    "cell": f"{sheet_title}!{snap['address']}",
                }

    if snap.get("kind") == "text" and isinstance(snap.get("raw"), str):
        kind = _temporal_text_kind(snap["raw"])
        if kind:
            parsed = parse_period(snap["raw"]) or _fy_loose(snap["raw"]) or {}
            return {
                "seed_type": kind,
                "period": parsed,
                "cell": f"{sheet_title}!{snap['address']}",
            }

    if snap.get("kind") == "number":
        parsed = parse_period(snap.get("raw"))
        if parsed and "year" in parsed and "month" not in parsed and "quarter" not in parsed:
            return {
                "seed_type": "YEAR_SEED",
                "period": parsed,
                "cell": f"{sheet_title}!{snap['address']}",
            }
    return None


def is_header_candidate(snap: dict[str, Any], *, header_band: bool) -> bool:
    if snap.get("is_date_format") or snap.get("formula") or snap.get("kind") == "datetime":
        return True
    raw = snap.get("raw")
    if isinstance(raw, str) and (
        _temporal_text_kind(raw)
        or _FY_HINT.search(raw)
        or _QUARTER_HINT.search(raw)
        or (_MONTH_HINT.search(raw) and _YEAR_HINT.search(raw))
    ):
        return True
    if snap.get("kind") == "number" and parse_period(raw):
        return True
    return bool(header_band and snap.get("kind") in {"datetime", "text", "number"} and raw not in (None, ""))


def resolve_sheet(workbook: Any, name: str | None, current_title: str) -> Any | None:
    if not name:
        title = current_title
    else:
        title = name.replace("''", "'")
    for sheet in workbook.worksheets:
        if sheet.title == title:
            return sheet
    stripped = title.strip()
    for sheet in workbook.worksheets:
        if sheet.title.strip() == stripped:
            return sheet
    lowered = stripped.casefold()
    hits = [sheet for sheet in workbook.worksheets if sheet.title.strip().casefold() == lowered]
    if len(hits) == 1:
        return hits[0]
    return None


def _snap_at(sheet: Any, col: int, row: int, merge_origin: dict[tuple[int, int], tuple[int, int]]) -> dict[str, Any]:
    origin = merge_origin.get((col, row), (col, row))
    cell = sheet.cell(row=origin[1], column=origin[0])
    snap = snapshot_cell(cell, merge_origin=merge_origin)
    snap["col"] = col
    snap["row"] = row
    snap["address"] = a1_address(col, row)
    return snap


def header_candidates(
    sheet: Any,
    *,
    axis: str,
    col: int,
    row: int | None = None,
    merge_origin: dict[tuple[int, int], tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    """Bounded mechanical header region on the missing axis. No gold formulas."""
    if merge_origin is None:
        merge_origin, _spans = _merge_map(sheet)
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    if axis == "row":
        scan_row = int(row or 1)
        for cand_col in range(1, HEADER_COL_CAP + 1):
            snap = _snap_at(sheet, cand_col, scan_row, merge_origin)
            band = cand_col <= 8
            if is_header_candidate(snap, header_band=band) and (cand_col, scan_row) not in seen:
                seen.add((cand_col, scan_row))
                out.append(snap)
        return out
    for cand_row in range(1, HEADER_ROW_CAP + 1):
        snap = _snap_at(sheet, col, cand_row, merge_origin)
        band = cand_row <= 12
        if is_header_candidate(snap, header_band=band) and (col, cand_row) not in seen:
            seen.add((col, cand_row))
            out.append(snap)
    return out


def path_type_of(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "OTHER_SUPPORTED_COMPOSITION"
    kinds = [step["kind"] for step in steps]
    cross = [bool(step.get("cross_sheet")) for step in steps]
    has_cross = any(cross)
    has_transform = any(kind in {"E2", "E3"} for kind in kinds)
    only_refs = all(kind == "E1" for kind in kinds)
    if only_refs and len(steps) == 1 and has_cross:
        return "DIRECT_CROSS_SHEET"
    if only_refs and len(steps) >= 2:
        return "MULTIHOP_REFERENCE"
    if has_transform and not has_cross:
        return "SAME_SHEET_TRANSFORM"
    if has_transform and has_cross:
        first_cross = next(i for i, flag in enumerate(cross) if flag)
        first_transform = next(i for i, kind in enumerate(kinds) if kind in {"E2", "E3"})
        if first_cross < first_transform:
            return "CROSS_SHEET_THEN_TRANSFORM"
        if first_transform < first_cross:
            return "TRANSFORM_THEN_CROSS_SHEET"
        return "OTHER_SUPPORTED_COMPOSITION"
    return "OTHER_SUPPORTED_COMPOSITION"


def _e3_seed_ok(seed: dict[str, Any], used_e3: bool) -> bool:
    if not used_e3:
        return True
    if seed["seed_type"] in {"DATETIME_SEED", "MONTH_YEAR_SEED"}:
        return True
    if seed["seed_type"] == "EXISTING_COORDINATE":
        period = seed.get("period") or {}
        return "month" in period or "year" in period
    return False


def _path_record(seed: dict[str, Any], steps: list[dict[str, Any]], start_sheet: Any, start_col: int, start_row: int) -> dict[str, Any]:
    return {
        "seed": seed,
        "steps": list(steps),
        "depth": len(steps),
        "path_type": path_type_of(steps),
        "same_sheet_hops": sum(1 for step in steps if not step.get("cross_sheet")),
        "cross_sheet_hops": sum(1 for step in steps if step.get("cross_sheet")),
        "transform_edges": sum(1 for step in steps if step["kind"] in {"E2", "E3"}),
        "reference_edges": sum(1 for step in steps if step["kind"] == "E1"),
        "e1_edges": sum(1 for step in steps if step["kind"] == "E1"),
        "e2_edges": sum(1 for step in steps if step["kind"] == "E2"),
        "e3_edges": sum(1 for step in steps if step["kind"] == "E3"),
        "start": f"{start_sheet.title}!{a1_address(start_col, start_row)}",
        "end": seed["cell"],
        "visited_n": len(steps) + 1,
        "n_edges": len(steps),
    }


def walk_from(
    workbook: Any,
    *,
    start_sheet: Any,
    start_col: int,
    start_row: int,
    coord_index: dict[tuple[str, int, int], dict[str, Any]],
    merge_maps: dict[str, dict[tuple[int, int], tuple[int, int]]],
    epoch: Any = None,
    max_depth: int = MAX_DEPTH,
    max_visited: int | None = None,
) -> dict[str, Any]:
    """Walk backward from one header cell. Returns best outcome for that start."""
    successes: list[dict[str, Any]] = []
    stops: list[str] = []
    decision_depth = 0
    visited_peak = 0
    n_edges = 0

    def rec(
        sheet: Any,
        col: int,
        row: int,
        depth: int,
        visited: tuple[tuple[str, int, int], ...],
        steps: list[dict[str, Any]],
        used_e3: bool,
    ) -> None:
        nonlocal decision_depth, visited_peak, n_edges
        key = (sheet.title, col, row)
        if key in visited:
            stops.append("CYCLE")
            decision_depth = max(decision_depth, depth)
            return
        if max_visited is not None and len(visited) >= max_visited:
            stops.append("SAFE_CLOSURE_LIMIT")
            decision_depth = max(decision_depth, depth)
            return
        if depth > max_depth:
            stops.append("DEPTH_LIMIT")
            decision_depth = max(decision_depth, depth)
            return
        visited_peak = max(visited_peak, len(visited) + 1)
        merge_origin = merge_maps.setdefault(sheet.title, _merge_map(sheet)[0])
        snap = _snap_at(sheet, col, row, merge_origin)
        seed = classify_seed(snap, sheet_title=sheet.title, coord_index=coord_index, epoch=epoch)
        if seed is not None:
            if not _e3_seed_ok(seed, used_e3):
                stops.append("NO_TEMPORAL_SEED")
                decision_depth = max(decision_depth, depth)
                return
            successes.append(_path_record(seed, steps, start_sheet, start_col, start_row))
            decision_depth = max(decision_depth, len(steps))
            return
        formula = snap.get("formula")
        if not formula:
            stops.append("NO_TEMPORAL_SEED")
            decision_depth = max(decision_depth, depth)
            return
        if depth == max_depth:
            stops.append("DEPTH_LIMIT")
            decision_depth = max(decision_depth, depth)
            return
        edge = classify_formula(formula)
        if edge["kind"] == "OPAQUE":
            stops.append("OPAQUE_PATH")
            decision_depth = max(decision_depth, depth)
            return
        if edge["kind"] == "LITERAL_DATE":
            seed = {
                "seed_type": "DATETIME_SEED",
                "period": {"year": edge["year"], "month": edge["month"]},
                "cell": f"{sheet.title}!{snap['address']}",
            }
            successes.append(_path_record(seed, steps, start_sheet, start_col, start_row))
            decision_depth = max(decision_depth, len(steps))
            return
        ref = edge["refs"][0]
        target_sheet = resolve_sheet(workbook, ref["sheet"], sheet.title)
        if target_sheet is None:
            stops.append("OPAQUE_PATH")
            decision_depth = max(decision_depth, depth)
            return
        step = {
            "kind": edge["kind"],
            "transform": edge.get("transform"),
            "offset": edge.get("offset"),
            "from": f"{sheet.title}!{a1_address(col, row)}",
            "to": f"{target_sheet.title}!{a1_address(ref['col'], ref['row'])}",
            "cross_sheet": target_sheet.title != sheet.title,
            "formula": formula[:240],
        }
        n_edges += 1
        rec(
            target_sheet,
            ref["col"],
            ref["row"],
            depth + 1,
            visited + (key,),
            steps + [step],
            used_e3 or edge["kind"] == "E3",
        )

    rec(start_sheet, start_col, start_row, 0, tuple(), [], False)
    extra = {
        "decision_depth": decision_depth,
        "visited_n": visited_peak,
        "n_edges": n_edges,
        "stops": stops,
    }
    if successes:
        successes.sort(key=lambda item: (item["depth"], PATH_TYPES.index(item["path_type"]) if item["path_type"] in PATH_TYPES else 99))
        return {"status": "REACHABLE_TEMPORAL_SEED", "paths": successes, **extra}
    if "OPAQUE_PATH" in stops:
        primary = "OPAQUE_PATH"
    elif "CYCLE" in stops:
        primary = "CYCLE"
    elif "SAFE_CLOSURE_LIMIT" in stops:
        primary = "SAFE_CLOSURE_LIMIT"
    elif "DEPTH_LIMIT" in stops:
        primary = "DEPTH_LIMIT"
    else:
        primary = "NO_TEMPORAL_SEED"
    return {"status": primary, "paths": [], **extra}


def project_walk(walk: dict[str, Any], *, max_depth: int) -> dict[str, Any]:
    """Replay a closure walk as if max_depth had been the hop cap."""
    reachable = [path for path in walk.get("paths") or [] if int(path.get("depth") or 0) <= max_depth]
    if reachable:
        copied = dict(walk)
        copied["status"] = "REACHABLE_TEMPORAL_SEED"
        copied["paths"] = reachable
        return copied
    decision = int(walk.get("decision_depth") or 0)
    if decision > max_depth:
        return {
            "status": "DEPTH_LIMIT",
            "paths": [],
            "stops": ["DEPTH_LIMIT"],
            "decision_depth": max_depth,
            "visited_n": walk.get("visited_n"),
            "n_edges": walk.get("n_edges"),
        }
    status = walk.get("status")
    if status == "SAFE_CLOSURE_LIMIT":
        return {
            "status": "DEPTH_LIMIT",
            "paths": [],
            "stops": ["DEPTH_LIMIT"],
            "decision_depth": max_depth,
            "visited_n": walk.get("visited_n"),
            "n_edges": walk.get("n_edges"),
        }
    return walk


def combine_start_walks(start_snaps: list[dict[str, Any]], walks: list[dict[str, Any]]) -> dict[str, Any]:
    """Same primary-selection rule as the original preflight."""
    all_paths: list[dict[str, Any]] = []
    stops: list[str] = []
    plausible_stops: list[str] = []
    supported_attempt = False
    visited_total = 0
    edges_total = 0
    for snap, result in zip(start_snaps, walks, strict=True):
        all_paths.extend(result.get("paths") or [])
        stops.extend(result.get("stops") or [])
        visited_total += int(result.get("visited_n") or 0)
        edges_total += int(result.get("n_edges") or 0)
        formula = snap.get("formula") or ""
        edge = classify_formula(formula) if formula else None
        if edge and edge["kind"] in {"E1", "E2", "E3", "LITERAL_DATE"}:
            supported_attempt = True
        plausible = bool(
            snap.get("is_date_format")
            or snap.get("kind") == "datetime"
            or (edge and edge["kind"] in {"E1", "E2", "E3", "LITERAL_DATE", "OPAQUE"})
        )
        if plausible:
            plausible_stops.append(result["status"])
    cost = {"visited_total": visited_total, "n_edges_total": edges_total}
    if all_paths:
        all_paths.sort(
            key=lambda item: (
                item["depth"],
                PATH_TYPES.index(item["path_type"]) if item["path_type"] in PATH_TYPES else 99,
            )
        )
        best = all_paths[0]
        return {
            "primary": "REACHABLE_TEMPORAL_SEED",
            "path_type": best["path_type"],
            "seed_type": best["seed"]["seed_type"],
            "n_header_candidates": len(start_snaps),
            "paths": all_paths,
            "best": best,
            "header_candidates": [f"{s.get('sheet_title', '')}!{s['address']}".lstrip("!") for s in start_snaps],
            "stops": stops,
            "depth": best["depth"],
            "same_sheet_hops": best["same_sheet_hops"],
            "cross_sheet_hops": best["cross_sheet_hops"],
            "transform_edges": best["transform_edges"],
            "reference_edges": best["reference_edges"],
            **cost,
        }
    ranked = plausible_stops or stops
    if supported_attempt and "DEPTH_LIMIT" in ranked:
        primary = "DEPTH_LIMIT"
    elif supported_attempt and "SAFE_CLOSURE_LIMIT" in ranked:
        primary = "SAFE_CLOSURE_LIMIT"
    elif "OPAQUE_PATH" in ranked:
        primary = "OPAQUE_PATH"
    elif "CYCLE" in ranked:
        primary = "CYCLE"
    elif "SAFE_CLOSURE_LIMIT" in ranked:
        primary = "SAFE_CLOSURE_LIMIT"
    elif "DEPTH_LIMIT" in ranked:
        primary = "DEPTH_LIMIT"
    else:
        primary = "NO_TEMPORAL_SEED"
    return {
        "primary": primary,
        "path_type": None,
        "seed_type": None,
        "n_header_candidates": len(start_snaps),
        "paths": [],
        "header_candidates": [s.get("address") for s in start_snaps],
        "stops": stops,
        "depth": None,
        "same_sheet_hops": 0,
        "cross_sheet_hops": 0,
        "transform_edges": 0,
        "reference_edges": 0,
        **cost,
    }


def compact_path(path: dict[str, Any]) -> list[str]:
    """Collapse repetitive same-sheet E2 runs; keep boundary hops explicit."""
    steps = path.get("steps") or []
    lines: list[str] = []
    index = 0
    while index < len(steps):
        step = steps[index]
        run = [step]
        cursor = index + 1
        if step["kind"] == "E2" and not step.get("cross_sheet"):
            transform = step.get("transform")
            while (
                cursor < len(steps)
                and steps[cursor]["kind"] == "E2"
                and not steps[cursor].get("cross_sheet")
                and steps[cursor].get("transform") == transform
            ):
                run.append(steps[cursor])
                cursor += 1
        if len(run) >= 3:
            xf = run[0].get("transform") or "E2"
            lines.append(
                f"{run[0]['from']} → ... → {run[-1]['to']}  [{len(run)} {xf} hops]"
            )
            index = cursor
            continue
        for item in run:
            mark = " (cross-sheet)" if item.get("cross_sheet") else ""
            extra = f" {item['transform']}" if item.get("transform") else ""
            lines.append(f"{item['from']} → {item['to']}  [{item['kind']}{extra}{mark}]")
        index = cursor if run else index + 1
    seed = path.get("seed") or {}
    lines.append(f"seed {seed.get('seed_type')} at {path.get('end')} period={seed.get('period')}")
    return lines


def terminal_failure_class(primary: str, *, n_edges: int) -> str | None:
    if primary == "REACHABLE_TEMPORAL_SEED":
        return None
    if primary == "OPAQUE_PATH":
        return "OPAQUE_BOUNDARY"
    if primary == "CYCLE":
        return "CYCLE"
    if primary == "SAFE_CLOSURE_LIMIT":
        return "CLOSURE_LIMIT"
    if primary in {"NO_TEMPORAL_SEED", "NO_HEADER_CANDIDATE"}:
        if n_edges > 0:
            return "NO_SEED_AFTER_SUPPORTED_CHAIN"
        return "TERMINAL_NONTEMPORAL"
    if primary == "DEPTH_LIMIT":
        return "CLOSURE_LIMIT"
    return primary


def index_coordinates(coordinates: list[dict[str, Any]]) -> dict[tuple[str, int, int], dict[str, Any]]:
    out: dict[tuple[str, int, int], dict[str, Any]] = {}
    for coord in coordinates:
        title = coord.get("sheet_title") or ""
        col = int(coord["col"])
        row = int(coord["row"])
        rec = coord
        out[(title, col, row)] = rec
        stripped = title.strip()
        if stripped != title:
            out[(stripped, col, row)] = rec
    return out


def classify_coordinate(
    workbook: Any,
    *,
    sheet: Any,
    axis: str,
    col: int,
    row: int | None,
    coord_index: dict[tuple[str, int, int], dict[str, Any]],
    merge_maps: dict[str, dict[tuple[int, int], tuple[int, int]]],
    epoch: Any = None,
    max_depth: int = MAX_DEPTH,
    extra_starts: list[tuple[int, int]] | None = None,
    max_visited: int | None = None,
) -> dict[str, Any]:
    merge_origin = merge_maps.setdefault(sheet.title, _merge_map(sheet)[0])
    starts = header_candidates(sheet, axis=axis, col=col, row=row, merge_origin=merge_origin)
    if extra_starts:
        seen = {(s["col"], s["row"]) for s in starts}
        for extra_col, extra_row in extra_starts:
            if (extra_col, extra_row) in seen:
                continue
            starts.append(_snap_at(sheet, extra_col, extra_row, merge_origin))
            seen.add((extra_col, extra_row))
    if not starts:
        return {
            "primary": "NO_HEADER_CANDIDATE",
            "path_type": None,
            "seed_type": None,
            "n_header_candidates": 0,
            "paths": [],
            "header_candidates": [],
            "stops": ["NO_HEADER_CANDIDATE"],
            "depth": None,
            "same_sheet_hops": 0,
            "cross_sheet_hops": 0,
            "transform_edges": 0,
            "reference_edges": 0,
        }
    walks = []
    for snap in starts:
        walks.append(
            walk_from(
                workbook,
                start_sheet=sheet,
                start_col=int(snap["col"]),
                start_row=int(snap["row"]),
                coord_index=coord_index,
                merge_maps=merge_maps,
                epoch=epoch,
                max_depth=max_depth,
                max_visited=max_visited,
            )
        )
    combined = combine_start_walks(starts, walks)
    combined["header_candidates"] = [f"{sheet.title}!{s['address']}" for s in starts]
    return combined


def add_months(period: dict[str, Any], months: int) -> dict[str, Any] | None:
    if "year" not in period or "month" not in period:
        return None
    month0 = int(period["month"]) + int(months) - 1
    year = int(period["year"]) + month0 // 12
    month = month0 % 12 + 1
    out = {"year": year, "month": month}
    if "day" in period:
        import calendar as _cal

        out["day"] = min(int(period["day"]), _cal.monthrange(year, month)[1])
    return out


def add_days(period: dict[str, Any], days: int) -> dict[str, Any] | None:
    if "year" not in period or "month" not in period:
        return None
    import datetime as _dt

    day = int(period.get("day") or 1)
    try:
        stamp = _dt.date(int(period["year"]), int(period["month"]), day) + _dt.timedelta(days=int(days))
    except ValueError:
        return None
    return {"year": stamp.year, "month": stamp.month, "day": stamp.day}


def derive_period_from_path(seed: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Apply E1–E3 transforms from seed forward along the reversed backward path."""
    period = dict(seed.get("period") or {})
    if not any(k in period for k in ("year", "month", "quarter")):
        return None
    for step in reversed(steps):
        kind = step.get("kind")
        if kind == "E1":
            continue
        if kind == "E2":
            period = add_months(period, int(step.get("offset") or 0))
            if period is None:
                return None
            continue
        if kind == "E3":
            period = add_days(period, int(step.get("offset") or 0))
            if period is None:
                return None
            continue
        return None
    return {k: period[k] for k in ("year", "month", "quarter", "day") if k in period}


def _periods_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in ("year", "month", "quarter"):
        if key in left and key in right and left[key] != right[key]:
            return False
    return True


def _merge_periods(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    out = dict(left)
    for key, value in right.items():
        out.setdefault(key, value)
    return out


def _closure_start(col: int, row: int, formula: str | None) -> bool:
    if not formula:
        return False
    edge = classify_formula(formula)
    if edge["kind"] not in {"E1", "E2", "E3", "LITERAL_DATE"}:
        return False
    if row <= HEADER_ROW_CAP or col <= HEADER_COL_CAP:
        return True
    return edge["kind"] in {"E2", "E3", "LITERAL_DATE"}


def close_temporal_workbook(
    workbook: Any,
    coordinates: list[dict[str, Any]],
    *,
    features: set[str],
    epoch: Any = None,
    max_visited: int = MAX_VISITED_CLOSURE,
) -> dict[str, Any]:
    """Gold-blind E1–E3 closure. Adds PROPAGATED_TEMPORAL_COORDINATE facts."""
    local = list(coordinates)
    for coord in local:
        coord.setdefault("derivation_status", "LOCAL_TEMPORAL_COORDINATE")
    coord_index = index_coordinates(local)
    local_col = {(c["sheet_id"], c["col"]) for c in local if c.get("axis") == "column"}
    local_row = {(c["sheet_id"], c["row"]) for c in local if c.get("axis") == "row"}
    title_index = {sheet.title: i for i, sheet in enumerate(workbook.worksheets)}
    merge_maps: dict[str, dict[tuple[int, int], tuple[int, int]]] = {}
    derivations: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    n_opaque = n_cycle = n_limit = n_nontemporal = 0
    n_starts = 0
    visited_total = 0
    edges_total = 0

    for sheet in workbook.worksheets:
        merge_origin = merge_maps.setdefault(sheet.title, _merge_map(sheet)[0])
        starts: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for cell in sheet._cells.values():
            col, row = int(cell.column), int(cell.row)
            formula = formula_text(cell.value)
            if not _closure_start(col, row, formula):
                continue
            if (col, row) in seen:
                continue
            seen.add((col, row))
            starts.append((col, row))
        for col, row in starts:
            n_starts += 1
            walked = walk_from(
                workbook,
                start_sheet=sheet,
                start_col=col,
                start_row=row,
                coord_index=coord_index,
                merge_maps=merge_maps,
                epoch=epoch,
                max_depth=10**9,
                max_visited=max_visited,
            )
            visited_total += int(walked.get("visited_n") or 0)
            edges_total += int(walked.get("n_edges") or 0)
            status = walked["status"]
            if status == "OPAQUE_PATH":
                n_opaque += 1
                continue
            if status == "CYCLE":
                n_cycle += 1
                continue
            if status == "SAFE_CLOSURE_LIMIT":
                n_limit += 1
                continue
            if status != "REACHABLE_TEMPORAL_SEED" or not walked.get("paths"):
                n_nontemporal += 1
                continue
            best = walked["paths"][0]
            if int(best.get("depth") or 0) == 0:
                continue
            derived = derive_period_from_path(best["seed"], best.get("steps") or [])
            if not derived:
                n_nontemporal += 1
                continue
            rec = {
                "start": best.get("start"),
                "end": best.get("end"),
                "period": derived,
                "seed": best.get("seed"),
                "depth": best.get("depth"),
                "path_type": best.get("path_type"),
                "same_sheet_hops": best.get("same_sheet_hops"),
                "cross_sheet_hops": best.get("cross_sheet_hops"),
                "e1_edges": best.get("e1_edges"),
                "e2_edges": best.get("e2_edges"),
                "e3_edges": best.get("e3_edges"),
                "compact": compact_path(best),
                "row": row,
                "col": col,
            }
            derivations[(sheet.title, "column", col)].append(rec)
            if "ROW_AXIS_SUPPORT" in features and col <= HEADER_COL_CAP:
                derivations[(sheet.title, "row", row)].append(rec)

    conflicts: list[dict[str, Any]] = []
    propagated: list[dict[str, Any]] = []
    depths: list[int] = []
    e1 = e2 = e3 = 0
    cross_counts: Counter = Counter()

    def emit(axis: str, sheet: Any, index: int, chosen: dict[str, Any], period: dict[str, Any]) -> None:
        nonlocal e1, e2, e3
        sheet_index = title_index[sheet.title]
        sid = f"sheet:s{sheet_index:02d}"
        row = int(chosen["row"] if axis == "row" else chosen.get("row") or 1)
        col = int(chosen["col"] if axis == "column" else chosen.get("col") or 1)
        if axis == "column":
            row = int(chosen["row"])
            col = index
        else:
            row = index
            col = int(chosen["col"])
        coord_id = f"tcoord:s{sheet_index:02d}:{axis[0]}:{index}:p"
        period_only = {k: period[k] for k in ("year", "month", "quarter") if k in period}
        propagated.append(
            {
                "id": coord_id,
                "axis": axis,
                "sheet_id": sid,
                "sheet_title": sheet.title,
                "row": row,
                "col": col,
                "row_id": f"row:s{sheet_index:02d}:r{row}",
                "col_id": f"col:s{sheet_index:02d}:c{col}",
                "cell_id": f"cell:s{sheet_index:02d}:r{row}:c{col}",
                "address": a1_address(col, row),
                "components": period,
                "period": period_only,
                "period_key": period_key(period_only),
                "encoding_class": ["FORMULA_DERIVED_DATE"],
                "evidence_cells": [a1_address(col, row)],
                "inherited_from": [chosen.get("end")],
                "propagation_rule": ["provenance_closure_e1_e3"],
                "header_text": chosen.get("start"),
                "provenance": [
                    {
                        "cell": chosen.get("start"),
                        "kind": "PROVENANCE_CLOSURE",
                        "source": chosen.get("path_type"),
                        "seed": chosen.get("end"),
                        "seed_type": (chosen.get("seed") or {}).get("seed_type"),
                        "path_length": chosen.get("depth"),
                        "cross_sheet_hops": chosen.get("cross_sheet_hops"),
                        "compact": chosen.get("compact"),
                    }
                ],
                "derivation_status": "PROPAGATED_TEMPORAL_COORDINATE",
                "seed_cell": chosen.get("end"),
                "seed_id": (chosen.get("seed") or {}).get("coord_id"),
                "path_length": chosen.get("depth"),
                "cross_sheet_hops": chosen.get("cross_sheet_hops"),
                "edge_types": {
                    "E1": chosen.get("e1_edges") or 0,
                    "E2": chosen.get("e2_edges") or 0,
                    "E3": chosen.get("e3_edges") or 0,
                },
            }
        )
        depths.append(int(chosen.get("depth") or 0))
        e1 += int(chosen.get("e1_edges") or 0)
        e2 += int(chosen.get("e2_edges") or 0)
        e3 += int(chosen.get("e3_edges") or 0)
        cross_counts[int(chosen.get("cross_sheet_hops") or 0)] += 1

    sheets_by_title = {sheet.title: sheet for sheet in workbook.worksheets}
    for (title, axis, index), recs in derivations.items():
        sheet = sheets_by_title.get(title)
        if sheet is None:
            continue
        sheet_index = title_index[title]
        sid = f"sheet:s{sheet_index:02d}"
        if axis == "column" and (sid, index) in local_col:
            continue
        if axis == "row" and (sid, index) in local_row:
            continue
        period = dict(recs[0]["period"])
        conflict = False
        for rec in recs[1:]:
            if not _periods_compatible(period, rec["period"]):
                conflict = True
                break
            period = _merge_periods(period, rec["period"])
        if conflict:
            conflicts.append(
                {
                    "sheet_title": title,
                    "axis": axis,
                    "index": index,
                    "candidates": [
                        {"period": r["period"], "start": r["start"], "end": r["end"], "depth": r["depth"]}
                        for r in recs
                    ],
                }
            )
            continue
        recs.sort(key=lambda item: int(item.get("depth") or 0))
        emit(axis, sheet, index, recs[0], period)

    def _pct(values: list[int], q: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        rank = (len(ordered) - 1) * q
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        frac = rank - low
        return round(ordered[low] * (1 - frac) + ordered[high] * frac, 4)

    stats = {
        "n_local": len(local),
        "n_starts": n_starts,
        "n_propagated": len(propagated),
        "n_conflicts": len(conflicts),
        "n_opaque": n_opaque,
        "n_cycle": n_cycle,
        "n_closure_limit": n_limit,
        "n_nontemporal": n_nontemporal,
        "visited_total": visited_total,
        "n_edges_total": edges_total,
        "depth": {
            "median": _pct(depths, 0.5),
            "p90": _pct(depths, 0.9),
            "max": max(depths) if depths else None,
            "n": len(depths),
        },
        "cross_sheet_hops": {str(k): v for k, v in sorted(cross_counts.items())},
        "edges": {"E1": e1, "E2": e2, "E3": e3},
        "golden_used": False,
    }
    return {
        "coordinates": local + propagated,
        "conflicts": conflicts,
        "stats": stats,
    }
