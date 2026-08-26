#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import fcntl
import json
import math
import os
import re
import sys
import urllib.parse
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import pairwise
from typing import Any

_A1_RANGE = re.compile(r"^([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?$")
_SPREADSHEET_ERROR_TOKEN = re.compile(
    r"#(?:DIV/0!|N/A|NAME\?|NULL!|NUM!|REF!|VALUE!)|Err:\d+",
    re.IGNORECASE,
)
_STRUCTURE_LABEL_LIMIT = 200
_STRUCTURE_LABEL_LENGTH = 240
_FORMULA_PATTERN_MIN_LENGTH = 4
_ANOMALY_NEIGHBOR_DISTANCE = 4
_ANOMALY_GLOBAL_PREFORMAT_LIMIT = 100
_ANOMALY_PER_SHEET_PREFORMAT_LIMIT = 10
_ANOMALY_GLOBAL_LIMIT = 20
_ANOMALY_PER_SHEET_LIMIT = 5
_ANOMALY_SMALL_SHEET_NUMERIC_LIMIT = 100
_ANOMALY_SATURATION_THRESHOLD = 0.9
_ANOMALY_SEQUENCE_LIMIT = 50
_ANOMALY_ERROR_GLOBAL_LIMIT = 20
_ANOMALY_ERROR_PER_SHEET_LIMIT = 5
_ANOMALY_ERROR_CONTEXT_CELL_LIMIT = 4
_READ_NEIGHBORHOOD_MAX_CELLS = 96
_DOWNSTREAM_VALUE_GLOBAL_LIMIT = 80
_DOWNSTREAM_VALUE_PER_SHEET_LIMIT = 8
_DIFF_ABSOLUTE_TOLERANCE = 1e-12
_DIFF_RELATIVE_TOLERANCE = 1e-9
_DEPENDENCY_BRIDGE_GLOBAL_LIMIT = 12
_DEPENDENCY_BRIDGE_MIN_CARRY = 2
_DEPENDENCY_RANGE_MAX_CELLS = 500
_FORMULA_ERROR_LITERALS = {
    "=#DIV/0!",
    "=#N/A",
    "=#NAME?",
    "=#NULL!",
    "=#NUM!",
    "=#REF!",
    "=#VALUE!",
}


def _load_backend_types() -> tuple[type[Any], type[Any]]:
    source_root = os.environ.get("LIBRECALC_SOURCE_ROOT", "/opt/librecalc/src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    from librecalc_mcp.backend.uno import UnoCalcBackend
    from librecalc_mcp.domain.models import CalcOperation

    return UnoCalcBackend, CalcOperation


def _read_budget():
    source_root = os.environ.get("LIBRECALC_SOURCE_ROOT", "/opt/librecalc/src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from librecalc_mcp.domain import read_budget

    return read_budget


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _parse_json(raw: str, expected_type: type[Any], label: str) -> Any:
    raw = urllib.parse.unquote(raw)
    raw = urllib.parse.unquote(raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, expected_type):
        raise TypeError(f"{label} must decode to {expected_type.__name__}")
    return value


def _parse_range_requests(raw: str) -> list[tuple[str, str]]:
    requests = _parse_json(raw, list, "ranges_json")
    parsed: list[tuple[str, str]] = []
    for index, request in enumerate(requests):
        if not isinstance(request, dict) or set(request) != {"sheet", "range"}:
            raise ValueError(f"ranges_json item {index} requires only sheet and range")
        sheet = request["sheet"]
        cell_range = request["range"]
        if not isinstance(sheet, str) or not isinstance(cell_range, str):
            raise TypeError(f"ranges_json item {index} fields must be strings")
        if _A1_RANGE.fullmatch(cell_range.upper()) is None:
            raise ValueError(f"ranges_json item {index} has invalid A1 range: {cell_range}")
        parsed.append((sheet, cell_range))
    if not parsed:
        raise ValueError("ranges_json must contain at least one range")
    return parsed


def _parse_sheet_names(raw: str) -> list[str]:
    values = _parse_json(raw, list, "target_sheets_json")
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("target_sheets_json must contain only non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError("target_sheets_json must not contain duplicates")
    return values


def _range_requests(raw: str) -> list[tuple[str, str]]:
    parsed = _parse_range_requests(raw)
    for index, (_, cell_range) in enumerate(parsed):
        _require_neighborhood_range(cell_range, label=f"ranges_json item {index}")
    return parsed


def _formula_blocks(raw_blocks: str, operation_type: type[Any]) -> list[Any]:
    blocks = _parse_json(raw_blocks, list, "formula_blocks_json")
    operations = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise TypeError(f"formula_blocks_json item {index} must be an object")
        required = {"sheet", "range", "formula"}
        if set(block) != required or not all(isinstance(block[key], str) for key in required):
            raise ValueError(
                f"formula_blocks_json item {index} requires only string fields "
                "sheet, range, and formula"
            )
        operations.append(operation_type(op="fill_formula", **block))
    return operations


def _a1_cell_count(cell_range: str) -> int:
    match = _A1_RANGE.fullmatch(cell_range.upper())
    if match is None:
        raise ValueError(f"invalid A1 range: {cell_range}")
    start_column, start_row, end_column, end_row = match.groups()
    end_column = end_column or start_column
    end_row = end_row or start_row
    rows = int(end_row) - int(start_row) + 1
    columns = _column_number(end_column) - _column_number(start_column) + 1
    if rows < 1 or columns < 1:
        raise ValueError(f"A1 range is inverted: {cell_range}")
    return rows * columns


def _require_neighborhood_range(cell_range: str, *, label: str) -> None:
    count = _a1_cell_count(cell_range)
    if count > _READ_NEIGHBORHOOD_MAX_CELLS:
        raise ValueError(
            f"{label} {cell_range} covers {count} cells; neighborhood reads are limited to "
            f"{_READ_NEIGHBORHOOD_MAX_CELLS} cells (a few rows or columns around a candidate). "
            "Narrow the range; do not dump a used range or whole sheet."
        )


def _spreadsheet_error_kind(formula: Any, error: Any) -> str | None:
    if error:
        return str(error)
    if not isinstance(formula, str):
        return None
    match = _SPREADSHEET_ERROR_TOKEN.search(formula)
    if match is None:
        return None
    token = match.group(0)
    return token.upper() if token.startswith("#") else token


def _a1_sort_key(address: str) -> tuple[int, int]:
    match = _A1_RANGE.fullmatch(address.upper())
    if match is None:
        return (10**9, 10**9)
    column, row, _, _ = match.groups()
    return (int(row), _column_number(column))


def _column_number(label: str) -> int:
    value = 0
    for character in label:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _column_label(number: int) -> str:
    characters = []
    while number:
        number, remainder = divmod(number - 1, 26)
        characters.append(chr(ord("A") + remainder))
    return "".join(reversed(characters))


def _cell_kind(value: Any, formula: Any) -> str:
    if isinstance(formula, str) and formula.startswith("="):
        return "formula"
    if value is None or value == "":
        return "blank"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "text"


def _spans(kinds: list[str]) -> tuple[tuple[int, int, str], ...]:
    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    active_kind: str | None = None
    for index, kind in enumerate([*kinds, "blank"]):
        if kind == active_kind and kind != "blank":
            continue
        if start is not None and active_kind is not None:
            spans.append((start, index - 1, active_kind))
        if kind == "blank":
            start = None
            active_kind = None
        else:
            start = index
            active_kind = kind
    return tuple(spans)


def _axis_bands(
    signatures: list[tuple[tuple[int, int, str], ...]],
    *,
    outer_labels: list[str],
    inner_labels: list[str],
) -> dict[str, list[str]]:
    bands: dict[str, list[str]] = {}
    band_start = 0
    for index in range(1, len(signatures) + 1):
        if index < len(signatures) and signatures[index] == signatures[band_start]:
            continue
        signature = signatures[band_start]
        if signature:
            outer_end = index - 1
            outer_range = outer_labels[band_start]
            if outer_end != band_start:
                outer_range += f":{outer_labels[outer_end]}"
            formatted_spans = []
            for inner_start, inner_end, kind in signature:
                inner_range = inner_labels[inner_start]
                if inner_end != inner_start:
                    inner_range += f":{inner_labels[inner_end]}"
                formatted_spans.append(f"{inner_range}={kind}")
            bands[outer_range] = formatted_spans
        band_start = index
    return bands


def _candidate_table_gaps(
    *,
    kinds: list[list[str]],
    labels: dict[str, str],
    row_labels: list[str],
    column_labels: list[str],
) -> dict[str, Any] | None:
    data_columns = [
        column
        for column in range(len(column_labels))
        if any(row[column] in {"number", "formula", "boolean"} for row in kinds)
    ]
    if not data_columns:
        return None
    data_start, data_end = min(data_columns), max(data_columns)
    text_counts = [sum(row[column] == "text" for row in kinds) for column in range(len(column_labels))]
    label_column = max(range(len(column_labels)), key=lambda column: text_counts[column])
    if text_counts[label_column] == 0 or label_column >= data_start:
        return None

    region_starts: set[int] = set()
    previous_populated = False
    for row_offset, row in enumerate(kinds):
        populated = any(kind != "blank" for kind in row)
        if populated and not previous_populated:
            region_starts.add(row_offset)
        previous_populated = populated

    gaps: dict[str, str] = {}
    for row_offset, row in enumerate(kinds):
        label_address = f"{column_labels[label_column]}{row_labels[row_offset]}"
        if label_address not in labels or sum(kind == "text" for kind in row) != 1:
            continue
        populated_data = any(row[column] != "blank" for column in range(data_start, data_end + 1))
        if row_offset in region_starts and not populated_data:
            continue
        gap_start: int | None = None
        for column in range(data_start, data_end + 2):
            blank = column <= data_end and row[column] == "blank"
            if blank and gap_start is None:
                gap_start = column
            if not blank and gap_start is not None:
                gap_end = column - 1
                cell_range = f"{column_labels[gap_start]}{row_labels[row_offset]}"
                if gap_end != gap_start:
                    cell_range += f":{column_labels[gap_end]}{row_labels[row_offset]}"
                gaps[cell_range] = labels[label_address]
                gap_start = None

    data_range = column_labels[data_start]
    if data_end != data_start:
        data_range += f":{column_labels[data_end]}"
    return {
        "label_column": column_labels[label_column],
        "data_columns": data_range,
        "candidate_gaps": gaps,
        "note": "Heuristic structural gaps, not task requirements.",
    }


def _horizontal_formula_patterns(
    *,
    formulas: list[list[Any]],
    values: list[list[Any]],
    row_labels: list[str],
    column_labels: list[str],
) -> dict[str, Any]:
    """Compress deterministic horizontal autofill runs without inventing formulas."""
    from librecalc_mcp.domain.formulas import translate_a1_formula

    patterns: list[dict[str, Any]] = []
    covered_cells = 0
    formula_cells = 0
    for row_offset, row_label in enumerate(row_labels):
        row_formulas = formulas[row_offset] if row_offset < len(formulas) else []
        row_values = values[row_offset] if row_offset < len(values) else []
        formula_cells += sum(
            isinstance(formula, str) and formula.startswith("=") for formula in row_formulas
        )
        column_offset = 0
        while column_offset < len(column_labels):
            formula = row_formulas[column_offset] if column_offset < len(row_formulas) else None
            if not isinstance(formula, str) or not formula.startswith("="):
                column_offset += 1
                continue
            pattern_start = column_offset
            column_offset += 1
            while column_offset < len(column_labels):
                candidate = (
                    row_formulas[column_offset] if column_offset < len(row_formulas) else None
                )
                try:
                    expected = translate_a1_formula(
                        formula,
                        column_offset=column_offset - pattern_start,
                        row_offset=0,
                    )
                except ValueError:
                    break
                if candidate != expected:
                    break
                column_offset += 1
            pattern_length = column_offset - pattern_start
            if pattern_length < _FORMULA_PATTERN_MIN_LENGTH:
                continue
            start_address = f"{column_labels[pattern_start]}{row_label}"
            end_address = f"{column_labels[column_offset - 1]}{row_label}"
            pattern: dict[str, Any] = {
                "range": f"{start_address}:{end_address}",
                "top_left_formula": formula,
            }
            if pattern_start < len(row_values):
                pattern["top_left_value"] = row_values[pattern_start]
            patterns.append(pattern)
            covered_cells += pattern_length
    return {
        "horizontal_fill_patterns": patterns,
        "formula_cells_covered": covered_cells,
        "formula_cells_unrepresented": formula_cells - covered_cells,
        "note": (
            "Exact horizontal translated runs of at least four cells; shorter/non-fill formulas "
            "remain available by focused read."
        ),
    }


def _matrix_value(matrix: list[list[Any]], row: int, column: int) -> Any:
    if row < 0 or column < 0 or row >= len(matrix) or column >= len(matrix[row]):
        return None
    return matrix[row][column]


def _is_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("=")


def _formula_anomaly_sheet(
    *,
    sheet: str,
    used_range: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Find compact formula-consistency signals without declaring cells incorrect."""
    from librecalc_mcp.domain.formulas import formula_a1_shape, translate_a1_formula

    match = _A1_RANGE.fullmatch(used_range.upper())
    if match is None:
        raise ValueError(f"used range must be an A1 range: {used_range}")
    start_column, start_row, end_column, end_row = match.groups()
    end_column = end_column or start_column
    end_row = end_row or start_row
    start_column_number = _column_number(start_column)
    row_count = int(end_row) - int(start_row) + 1
    column_count = _column_number(end_column) - start_column_number + 1
    values = result.get("values", [])
    formulas = result.get("formulas", [])
    errors = result.get("errors", [])

    def address(row: int, column: int) -> str:
        return f"{_column_label(start_column_number + column)}{int(start_row) + row}"

    def error_context(row: int, column: int) -> list[dict[str, Any]]:
        """Return a few nearby literals that help name an error without prescribing a fix."""
        context: list[dict[str, Any]] = []
        directions = (
            (0, -1, "row_left", True),
            (0, 1, "row_right", True),
            (-1, 0, "column_above", False),
            (1, 0, "column_below", False),
        )
        for row_step, column_step, relation, prefer_text in directions:
            nearest_literal: dict[str, Any] | None = None
            axis_length = row_count if row_step else column_count
            for distance in range(1, axis_length):
                source_row = row + row_step * distance
                source_column = column + column_step * distance
                value = _matrix_value(values, source_row, source_column)
                formula = _matrix_value(formulas, source_row, source_column)
                if _is_formula(formula) or value is None or value == "":
                    continue
                candidate = {
                    "address": address(source_row, source_column),
                    "value": value,
                    "relation": relation,
                    "distance": distance,
                }
                if nearest_literal is None:
                    nearest_literal = candidate
                if not prefer_text or isinstance(value, str):
                    nearest_literal = candidate
                    break
            if nearest_literal is not None:
                context.append(nearest_literal)
        return context[:_ANOMALY_ERROR_CONTEXT_CELL_LIMIT]

    formula_cells = 0
    numeric_constants = 0
    formula_errors: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    directions = (
        (0, -1, "left"),
        (0, 1, "right"),
        (-1, 0, "above"),
        (1, 0, "below"),
    )
    for row in range(row_count):
        for column in range(column_count):
            formula = _matrix_value(formulas, row, column)
            value = _matrix_value(values, row, column)
            if _is_formula(formula):
                formula_cells += 1
                error_kind = _spreadsheet_error_kind(
                    formula, _matrix_value(errors, row, column)
                )
                if error_kind is not None:
                    formula_errors.append(
                        {
                            "sheet": sheet,
                            "address": address(row, column),
                            "formula": formula,
                            "error": error_kind,
                            "shape": formula_a1_shape(formula),
                            "context": error_context(row, column),
                        }
                    )
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            numeric_constants += 1
            inferred: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row_step, column_step, direction in directions:
                for distance in range(1, _ANOMALY_NEIGHBOR_DISTANCE + 1):
                    source_row = row + row_step * distance
                    source_column = column + column_step * distance
                    source_formula = _matrix_value(formulas, source_row, source_column)
                    if not _is_formula(source_formula):
                        continue
                    try:
                        expected = translate_a1_formula(
                            source_formula,
                            column_offset=column - source_column,
                            row_offset=row - source_row,
                        )
                    except ValueError:
                        continue
                    inferred[expected].append(
                        {
                            "address": address(source_row, source_column),
                            "direction": direction,
                            "distance": distance,
                        }
                    )
            if not inferred:
                continue
            inferred_formula, sources = min(
                inferred.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
            if len(sources) < 2:
                continue
            if inferred_formula.strip().upper() in _FORMULA_ERROR_LITERALS:
                continue
            candidates.append(
                {
                    "sheet": sheet,
                    "address": address(row, column),
                    "current_value": value,
                    "inferred_formula": inferred_formula,
                    "agreement_count": len(sources),
                    "direction_count": len({source["direction"] for source in sources}),
                    "immediate_count": sum(source["distance"] == 1 for source in sources),
                    "evidence_sources": sources,
                }
            )

    sequence_gaps_by_address: dict[str, dict[str, Any]] = {}
    for row in range(row_count):
        by_shape: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for column in range(column_count):
            formula = _matrix_value(formulas, row, column)
            if _is_formula(formula):
                by_shape[formula_a1_shape(formula)].append((column, formula))
        for shape, shaped_formulas in by_shape.items():
            if len(shaped_formulas) < 3:
                continue
            shaped_formulas.sort()
            for index, ((left_column, left_formula), (right_column, right_formula)) in enumerate(
                pairwise(shaped_formulas)
            ):
                gap_length = right_column - left_column - 1
                if not 1 <= gap_length <= 3:
                    continue
                gap_values = [
                    _matrix_value(values, row, column)
                    for column in range(left_column + 1, right_column)
                ]
                gap_formulas = [
                    _matrix_value(formulas, row, column)
                    for column in range(left_column + 1, right_column)
                ]
                if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in gap_values):
                    continue
                if any(_is_formula(formula) for formula in gap_formulas):
                    continue
                has_local_continuation = (
                    index > 0 and left_column - shaped_formulas[index - 1][0] <= 4
                ) or (
                    index + 2 < len(shaped_formulas)
                    and shaped_formulas[index + 2][0] - right_column <= 4
                )
                if not has_local_continuation:
                    continue
                nearby_sources = [
                    address(row, column)
                    for column, _ in shaped_formulas
                    if left_column - 4 <= column <= right_column + 4
                ]
                for column, current_value in zip(
                    range(left_column + 1, right_column), gap_values, strict=True
                ):
                    candidate_address = address(row, column)
                    candidate = {
                        "sheet": sheet,
                        "address": candidate_address,
                        "current_value": current_value,
                        "formula_shape": shape,
                        "before": {
                            "address": address(row, left_column),
                            "formula": left_formula,
                        },
                        "after": {
                            "address": address(row, right_column),
                            "formula": right_formula,
                        },
                        "nearby_same_shape_sources": nearby_sources,
                    }
                    previous = sequence_gaps_by_address.get(candidate_address)
                    if previous is None or len(nearby_sources) > len(
                        previous["nearby_same_shape_sources"]
                    ):
                        sequence_gaps_by_address[candidate_address] = candidate

    candidates.sort(
        key=lambda candidate: (
            -candidate["agreement_count"],
            -candidate["direction_count"],
            -candidate["immediate_count"],
            candidate["address"],
        )
    )
    sequence_gaps = sorted(
        sequence_gaps_by_address.values(), key=lambda candidate: candidate["address"]
    )
    return {
        "name": sheet,
        "used_range": used_range.upper(),
        "formula_cells": formula_cells,
        "numeric_constants": numeric_constants,
        "formula_error_count": len(formula_errors),
        "translation_candidate_count": len(candidates),
        "sequence_gap_count": len(sequence_gaps),
        "_translation_candidates": candidates,
        "_sequence_gaps": sequence_gaps,
        "_formula_errors": formula_errors,
    }


def _formula_anomaly_workbook_observation(
    *,
    title: str,
    url: str | None,
    sheets: list[dict[str, Any]],
    formats: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from librecalc_mcp.domain.formulas import formula_a1_shape

    formats = formats or {}
    saturated_sheets = {
        sheet["name"]
        for sheet in sheets
        if sheet["numeric_constants"]
        and sheet["translation_candidate_count"] / sheet["numeric_constants"]
        >= _ANOMALY_SATURATION_THRESHOLD
    }
    all_candidates = [
        candidate for sheet in sheets for candidate in sheet["_translation_candidates"]
    ]
    all_candidates.sort(
        key=lambda candidate: (
            -candidate["agreement_count"],
            -candidate["direction_count"],
            -candidate["immediate_count"],
            candidate["sheet"],
            candidate["address"],
        )
    )
    preformatted_candidates: dict[tuple[str, str], dict[str, Any]] = {}

    def with_format(candidate: dict[str, Any]) -> dict[str, Any]:
        key = (candidate["sheet"], candidate["address"])
        if key not in preformatted_candidates:
            formatted = dict(candidate)
            if key in formats:
                formatted["format"] = formats[key]
            preformatted_candidates[key] = formatted
        return preformatted_candidates[key]

    ranked_candidates = [
        candidate for candidate in all_candidates if candidate["sheet"] not in saturated_sheets
    ]
    for candidate in ranked_candidates[:_ANOMALY_GLOBAL_PREFORMAT_LIMIT]:
        with_format(candidate)
    for sheet in sheets:
        if sheet["numeric_constants"] > _ANOMALY_SMALL_SHEET_NUMERIC_LIMIT:
            continue
        for candidate in sheet["_translation_candidates"][:_ANOMALY_PER_SHEET_PREFORMAT_LIMIT]:
            with_format(candidate)

    def is_conventional_formula_format(candidate: dict[str, Any]) -> bool:
        cell_format = candidate.get("format", {})
        font_color = cell_format.get("font_color")
        if font_color == "#0000FF":
            return False
        return not (
            font_color == "#000000"
            and cell_format.get("background_transparent") is True
        )

    grouped_candidates: dict[tuple[str, int, str], list[tuple[int, dict[str, Any]]]] = (
        defaultdict(list)
    )
    for candidate in all_candidates:
        address_match = _A1_RANGE.fullmatch(candidate["address"])
        if address_match is None:
            continue
        column, row, _, _ = address_match.groups()
        grouped_candidates[
            (candidate["sheet"], int(row), formula_a1_shape(candidate["inferred_formula"]))
        ].append((_column_number(column), candidate))
    edge_block_candidates: set[tuple[str, str]] = set()
    for positioned_candidates in grouped_candidates.values():
        positioned_candidates.sort(key=lambda item: item[0])
        run: list[tuple[int, dict[str, Any]]] = []
        for positioned_candidate in positioned_candidates:
            if run and positioned_candidate[0] != run[-1][0] + 1:
                if len(run) >= 2:
                    edge_block_candidates.update(
                        (candidate["sheet"], candidate["address"])
                        for _, candidate in run
                        if not {"left", "right"}
                        <= {source["direction"] for source in candidate["evidence_sources"]}
                    )
                run = []
            run.append(positioned_candidate)
        if len(run) >= 2:
            edge_block_candidates.update(
                (candidate["sheet"], candidate["address"])
                for _, candidate in run
                if not {"left", "right"}
                <= {source["direction"] for source in candidate["evidence_sources"]}
            )

    eligible_candidates = [
        candidate
        for candidate in preformatted_candidates.values()
        if is_conventional_formula_format(candidate)
        and (candidate["sheet"], candidate["address"]) not in edge_block_candidates
    ]
    eligible_candidates.sort(
        key=lambda candidate: (
            -candidate["agreement_count"],
            -candidate["direction_count"],
            -candidate["immediate_count"],
            candidate["sheet"],
            candidate["address"],
        )
    )
    selected: dict[tuple[str, str], dict[str, Any]] = {}

    def select(candidate: dict[str, Any], reason: str) -> None:
        key = (candidate["sheet"], candidate["address"])
        if key not in selected:
            selected[key] = {**candidate, "selected_by": []}
        selected[key]["selected_by"].append(reason)

    for candidate in eligible_candidates[:_ANOMALY_GLOBAL_LIMIT]:
        select(candidate, f"global-top-{_ANOMALY_GLOBAL_LIMIT}")
    for sheet in sheets:
        if sheet["numeric_constants"] > _ANOMALY_SMALL_SHEET_NUMERIC_LIMIT:
            continue
        sheet_candidates = [
            candidate
            for candidate in eligible_candidates
            if candidate["sheet"] == sheet["name"]
        ]
        for candidate in sheet_candidates[:_ANOMALY_PER_SHEET_LIMIT]:
            select(candidate, f"sheet-top-{_ANOMALY_PER_SHEET_LIMIT}")

    sequence_gaps = [gap for sheet in sheets for gap in sheet["_sequence_gaps"]]
    sequence_gaps.sort(key=lambda gap: (gap["sheet"], gap["address"]))
    formatted_sequence_gaps = []
    for gap in sequence_gaps:
        formatted_gap = dict(gap)
        gap_key = (gap["sheet"], gap["address"])
        if gap_key in formats:
            formatted_gap["format"] = formats[gap_key]
        formatted_sequence_gaps.append(formatted_gap)
    eligible_sequence_gaps = [
        gap for gap in formatted_sequence_gaps if is_conventional_formula_format(gap)
    ]
    sheet_summaries = [
        {key: value for key, value in sheet.items() if not key.startswith("_")} for sheet in sheets
    ]
    return {
        "title": title,
        "url": url,
        "observation": "formula-anomalies-v1",
        "sheets": sheet_summaries,
        "translation_consensus": {
            "candidate_count": len(all_candidates),
            "selected_count": len(selected),
            "saturated_sheets_omitted": sorted(saturated_sheets),
            "format_candidates_deprioritized": len(preformatted_candidates)
            - sum(
                is_conventional_formula_format(candidate)
                for candidate in preformatted_candidates.values()
            ),
            "edge_block_candidates_deprioritized": sum(
                (candidate["sheet"], candidate["address"]) in edge_block_candidates
                and is_conventional_formula_format(candidate)
                for candidate in preformatted_candidates.values()
            ),
            "selected_candidates": list(selected.values()),
            "note": (
                "Numeric constants for which at least two nearby formulas translate to the same "
                "formula. Ranked signals, not validation failures; confirm with focused reads. "
                "Blue-font cells and unfilled black-font cells are deprioritized because they "
                "commonly denote intentional inputs or historical constants in financial models. "
                "Contiguous constants at an unbracketed edge of a formula pattern are also "
                "deprioritized as likely assumption blocks."
            ),
        },
        "short_sequence_gaps": {
            "candidate_count": len(sequence_gaps),
            "format_candidates_deprioritized": len(formatted_sequence_gaps)
            - len(eligible_sequence_gaps),
            "selected_candidates": eligible_sequence_gaps[:_ANOMALY_SEQUENCE_LIMIT],
            "note": (
                "One-to-three numeric constants bracketed horizontally by formulas of the same "
                "shape with a nearby continuation. Signals only; infer exact formulas from context."
            ),
        },
        "formula_errors": _formula_error_representatives(sheets),
    }


def _formula_error_representatives(sheets: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact error attention: one representative per sheet/error/shape, not every cascade."""
    all_errors = [cell for sheet in sheets for cell in sheet.get("_formula_errors", [])]
    by_error: dict[str, int] = defaultdict(int)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for cell in all_errors:
        by_error[cell["error"]] += 1
        grouped[(cell["sheet"], cell["error"], cell["shape"])].append(cell)

    representatives: list[dict[str, Any]] = []
    for (sheet, error, shape), cells in grouped.items():
        cells.sort(key=lambda cell: _a1_sort_key(cell["address"]))
        first = cells[0]
        representatives.append(
            {
                "sheet": sheet,
                "address": first["address"],
                "formula": first["formula"],
                "error": error,
                "shape": shape,
                "repeat_count": len(cells),
                "context": first.get("context", []),
            }
        )
    representatives.sort(
        key=lambda cell: (-cell["repeat_count"], cell["sheet"], _a1_sort_key(cell["address"]))
    )

    selected: dict[tuple[str, str], dict[str, Any]] = {}

    def select(candidate: dict[str, Any]) -> None:
        key = (candidate["sheet"], candidate["address"])
        if key not in selected:
            selected[key] = candidate

    for candidate in representatives[:_ANOMALY_ERROR_GLOBAL_LIMIT]:
        select(candidate)
    for sheet in sheets:
        sheet_candidates = [
            candidate for candidate in representatives if candidate["sheet"] == sheet["name"]
        ]
        for candidate in sheet_candidates[:_ANOMALY_ERROR_PER_SHEET_LIMIT]:
            select(candidate)

    selected_cells = sorted(
        selected.values(),
        key=lambda cell: (-cell["repeat_count"], cell["sheet"], _a1_sort_key(cell["address"])),
    )
    return {
        "cell_count": len(all_errors),
        "selected_count": len(selected_cells),
        "by_error": dict(sorted(by_error.items())),
        "selected_cells": selected_cells,
        "note": (
            "Calculated or formula-token errors, collapsed to one representative per sheet, "
            "error kind, and formula shape. Ranked attention, not auto-edits; confirm the "
            "damaged neighborhood with a small read before writing. Cascading dependents may "
            "share a shape after a missing row or retargeted reference."
        ),
    }


def _formula_anomaly_format_requests(sheets: list[dict[str, Any]]) -> list[tuple[str, str]]:
    saturated_sheets = {
        sheet["name"]
        for sheet in sheets
        if sheet["numeric_constants"]
        and sheet["translation_candidate_count"] / sheet["numeric_constants"]
        >= _ANOMALY_SATURATION_THRESHOLD
    }
    all_candidates = [
        candidate
        for sheet in sheets
        if sheet["name"] not in saturated_sheets
        for candidate in sheet["_translation_candidates"]
    ]
    all_candidates.sort(
        key=lambda candidate: (
            -candidate["agreement_count"],
            -candidate["direction_count"],
            -candidate["immediate_count"],
            candidate["sheet"],
            candidate["address"],
        )
    )
    requests: dict[tuple[str, str], None] = {}
    for candidate in all_candidates[:_ANOMALY_GLOBAL_PREFORMAT_LIMIT]:
        requests[(candidate["sheet"], candidate["address"])] = None
    for sheet in sheets:
        if sheet["numeric_constants"] <= _ANOMALY_SMALL_SHEET_NUMERIC_LIMIT:
            for candidate in sheet["_translation_candidates"][
                :_ANOMALY_PER_SHEET_PREFORMAT_LIMIT
            ]:
                requests[(candidate["sheet"], candidate["address"])] = None
        for gap in sheet["_sequence_gaps"][:_ANOMALY_SEQUENCE_LIMIT]:
            requests[(gap["sheet"], gap["address"])] = None
    return list(requests)


def _structure_sheet_observation(
    *,
    sheet: str,
    used_range: str,
    result: dict[str, Any],
    include_cell_details: bool = False,
    include_candidate_gaps: bool = False,
    include_formula_patterns: bool = False,
    label_limit: int | None = _STRUCTURE_LABEL_LIMIT,
) -> dict[str, Any]:
    match = _A1_RANGE.fullmatch(used_range.upper())
    if match is None:
        raise ValueError(f"used range must be an A1 range: {used_range}")
    start_column, start_row, end_column, end_row = match.groups()
    end_column = end_column or start_column
    end_row = end_row or start_row
    start_column_number = _column_number(start_column)
    column_count = _column_number(end_column) - start_column_number + 1
    row_count = int(end_row) - int(start_row) + 1
    values = result.get("values", [])
    formulas = result.get("formulas", [])
    errors = result.get("errors", [])
    row_labels = [str(int(start_row) + offset) for offset in range(row_count)]
    column_labels = [_column_label(start_column_number + offset) for offset in range(column_count)]

    kinds: list[list[str]] = []
    labels: dict[str, str] = {}
    inputs: dict[str, Any] = {}
    live_formulas: dict[str, dict[str, Any]] = {}
    nonempty_cells = 0
    formula_cells = 0
    formula_error_cells = 0
    for row_offset in range(row_count):
        row_kinds = []
        for column_offset in range(column_count):
            value = (
                values[row_offset][column_offset]
                if row_offset < len(values) and column_offset < len(values[row_offset])
                else None
            )
            formula = (
                formulas[row_offset][column_offset]
                if row_offset < len(formulas) and column_offset < len(formulas[row_offset])
                else None
            )
            error = (
                errors[row_offset][column_offset]
                if row_offset < len(errors) and column_offset < len(errors[row_offset])
                else None
            )
            kind = _cell_kind(value, formula)
            row_kinds.append(kind)
            if kind != "blank":
                nonempty_cells += 1
            if kind == "formula":
                formula_cells += 1
                if error:
                    formula_error_cells += 1
            address = f"{column_labels[column_offset]}{row_labels[row_offset]}"
            if kind == "text" and (label_limit is None or len(labels) < label_limit):
                text = str(value)
                if len(text) > _STRUCTURE_LABEL_LENGTH:
                    text = text[: _STRUCTURE_LABEL_LENGTH - 1] + "…"
                labels[address] = text
            elif kind in {"number", "boolean"}:
                inputs[address] = value
            elif kind == "formula":
                live_formulas[address] = {"expression": formula, "value": value}
                if error:
                    live_formulas[address]["error"] = error
        kinds.append(row_kinds)

    row_signatures = [_spans(row) for row in kinds]
    column_signatures = [
        _spans([kinds[row][column] for row in range(row_count)])
        for column in range(column_count)
    ]

    regions = []
    region_start: int | None = None
    for row_offset in range(row_count + 1):
        populated = row_offset < row_count and bool(row_signatures[row_offset])
        if populated and region_start is None:
            region_start = row_offset
        if not populated and region_start is not None:
            region_end = row_offset - 1
            occupied_columns = [
                column
                for row in range(region_start, region_end + 1)
                for column, kind in enumerate(kinds[row])
                if kind != "blank"
            ]
            regions.append(
                f"{column_labels[min(occupied_columns)]}{row_labels[region_start]}:"
                f"{column_labels[max(occupied_columns)]}{row_labels[region_end]}"
            )
            region_start = None

    total_labels = sum(kind == "text" for row in kinds for kind in row)
    observation = {
        "name": sheet,
        "used_range": used_range.upper(),
        "dimensions": {"rows": row_count, "columns": column_count},
        "nonempty_cells": nonempty_cells,
        "formula_cells": formula_cells,
        "formula_error_cells": formula_error_cells,
        "regions": regions,
        "labels": labels,
        "labels_omitted": total_labels - len(labels),
        "row_bands": _axis_bands(
            row_signatures,
            outer_labels=row_labels,
            inner_labels=column_labels,
        ),
        "column_bands": _axis_bands(
            column_signatures,
            outer_labels=column_labels,
            inner_labels=row_labels,
        ),
    }
    if include_cell_details:
        observation["inputs"] = inputs
        observation["formulas"] = live_formulas
        observation["formula_errors"] = {
            address: details["error"]
            for address, details in live_formulas.items()
            if details.get("error")
        }
    if include_candidate_gaps:
        candidate_table = _candidate_table_gaps(
            kinds=kinds,
            labels=labels,
            row_labels=row_labels,
            column_labels=column_labels,
        )
        if candidate_table is not None:
            observation["inferred_table"] = candidate_table
    if include_formula_patterns:
        observation["formula_patterns"] = _horizontal_formula_patterns(
            formulas=formulas,
            values=values,
            row_labels=row_labels,
            column_labels=column_labels,
        )
    return observation


def _sheet_manifest(
    *,
    sheet: str,
    used_range: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    observation = _structure_sheet_observation(
        sheet=sheet,
        used_range=used_range,
        result=result,
        label_limit=0,
    )
    return {
        key: observation[key]
        for key in (
            "name",
            "used_range",
            "dimensions",
            "nonempty_cells",
            "formula_cells",
            "formula_error_cells",
        )
    } | {"detail": "manifest-only"}


def _blank_dependency_bridges(
    sheets: list[tuple[str, str, dict[str, Any]]],
    *,
    selected_sheets: set[str],
) -> dict[str, Any]:
    """Rank blank precedents that bridge into horizontal carry-forward chains."""
    from librecalc_mcp.domain.formulas import formula_a1_references

    sheet_cells: dict[str, dict[str, tuple[Any, Any]]] = {}
    formula_cells: dict[tuple[str, str], str] = {}
    for sheet, used_range, result in sheets:
        match = _A1_RANGE.fullmatch(used_range.upper())
        if match is None:
            continue
        start_column, start_row, end_column, end_row = match.groups()
        end_column = end_column or start_column
        end_row = end_row or start_row
        start_column_number = _column_number(start_column)
        row_count = int(end_row) - int(start_row) + 1
        column_count = _column_number(end_column) - start_column_number + 1
        values = result.get("values", [])
        formulas = result.get("formulas", [])
        cells: dict[str, tuple[Any, Any]] = {}
        for row in range(row_count):
            for column in range(column_count):
                address = (
                    f"{_column_label(start_column_number + column)}"
                    f"{int(start_row) + row}"
                )
                value = _matrix_value(values, row, column)
                formula = _matrix_value(formulas, row, column)
                cells[address] = (value, formula)
                if _is_formula(formula):
                    formula_cells[(sheet, address)] = formula
        sheet_cells[sheet] = cells

    reverse_dependencies: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    direct_dependencies: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    blank_dependents: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for dependent, formula in formula_cells.items():
        for reference_sheet, start, end in formula_a1_references(formula):
            source_sheet = reference_sheet or dependent[0]
            if source_sheet not in sheet_cells:
                continue
            if end is None:
                precedent = (source_sheet, start)
                reverse_dependencies[precedent].add(dependent)
                direct_dependencies[dependent].add(precedent)
                value, precedent_formula = sheet_cells[source_sheet].get(start, (None, None))
                if value in (None, "") and not _is_formula(precedent_formula):
                    blank_dependents[precedent].add(dependent)
                continue
            try:
                cell_count = _a1_cell_count(f"{start}:{end}")
            except ValueError:
                continue
            if cell_count > _DEPENDENCY_RANGE_MAX_CELLS:
                continue
            range_match = _A1_RANGE.fullmatch(f"{start}:{end}")
            if range_match is None:
                continue
            start_column, start_row, end_column, end_row = range_match.groups()
            assert end_column is not None and end_row is not None
            for row in range(int(start_row), int(end_row) + 1):
                for column in range(
                    _column_number(start_column), _column_number(end_column) + 1
                ):
                    reverse_dependencies[(source_sheet, f"{_column_label(column)}{row}")].add(
                        dependent
                    )

    def carry_chain(dependent: tuple[str, str], step: int) -> list[tuple[str, str]]:
        match = _A1_RANGE.fullmatch(dependent[1])
        if match is None:
            return [dependent]
        column, row, _, _ = match.groups()
        column_number = _column_number(column)
        chain = [dependent]
        current = dependent
        while column_number + step > 0:
            column_number += step
            candidate = (dependent[0], f"{_column_label(column_number)}{row}")
            if current not in direct_dependencies.get(candidate, set()):
                break
            chain.append(candidate)
            current = candidate
        return chain

    def row_label(sheet: str, address: str, relation: str) -> dict[str, Any] | None:
        match = _A1_RANGE.fullmatch(address)
        if match is None:
            return None
        column, row, _, _ = match.groups()
        column_number = _column_number(column)
        for source_column in range(column_number - 1, max(0, column_number - 8), -1):
            source_address = f"{_column_label(source_column)}{row}"
            value, formula = sheet_cells[sheet].get(source_address, (None, None))
            if isinstance(value, str) and value and not _is_formula(formula):
                return {
                    "address": source_address,
                    "value": value,
                    "relation": relation,
                }
        return None

    candidates = []
    for precedent, dependents in blank_dependents.items():
        if precedent[0] not in selected_sheets:
            continue
        best_chain: list[tuple[str, str]] = []
        best_dependent: tuple[str, str] | None = None
        for dependent in sorted(dependents):
            right_chain = carry_chain(dependent, 1)
            left_chain = carry_chain(dependent, -1)
            chain = right_chain if len(right_chain) >= len(left_chain) else list(reversed(left_chain))
            if len(chain) > len(best_chain):
                best_chain = chain
                best_dependent = dependent
        carry_length = len(best_chain) - 1
        if carry_length < _DEPENDENCY_BRIDGE_MIN_CARRY or best_dependent is None:
            continue

        downstream: set[tuple[str, str]] = set()
        pending = list(reverse_dependencies.get(precedent, set()))
        while pending:
            dependent = pending.pop()
            if dependent in downstream:
                continue
            downstream.add(dependent)
            pending.extend(reverse_dependencies.get(dependent, set()))

        context = [
            value
            for value in (
                row_label(precedent[0], precedent[1], "blank_row_label"),
                row_label(best_dependent[0], best_dependent[1], "dependent_row_label"),
            )
            if value is not None
        ]
        chain_start = best_chain[0][1]
        chain_end = best_chain[-1][1]
        candidates.append(
            {
                "sheet": precedent[0],
                "address": precedent[1],
                "dependent": {
                    "sheet": best_dependent[0],
                    "address": best_dependent[1],
                    "formula": formula_cells[best_dependent],
                },
                "carry_forward_range": (
                    chain_start if chain_start == chain_end else f"{chain_start}:{chain_end}"
                ),
                "carry_forward_length": carry_length,
                "downstream_formula_count": len(downstream),
                "context": context,
            }
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate["carry_forward_length"],
            -candidate["downstream_formula_count"],
            candidate["sheet"],
            _a1_sort_key(candidate["address"]),
        )
    )
    selected = candidates[:_DEPENDENCY_BRIDGE_GLOBAL_LIMIT]
    return {
        "candidate_count": len(candidates),
        "selected_candidates": selected,
        "omitted": len(candidates) - len(selected),
        "note": (
            "Heuristic blank precedents whose dependent formula begins a horizontal "
            "carry-forward chain of at least two steps. Useful for missing historical bases "
            "or bridge inputs; not validation failures or auto-edits. Confirm with a focused read."
        ),
    }


def _workbook_observation(
    backend: Any,
    path: str,
    variant: str,
    *,
    detailed_sheets: set[str] | None = None,
) -> dict[str, Any]:
    workbook = backend.inspect_workbook(path=path)
    if variant not in {
        "structure-first-v1",
        "formula-patterns-v1",
        "formula-anomalies-v1",
        "semantic-snapshot-v1",
        "semantic-snapshot-v2",
    }:
        return dataclasses.asdict(workbook)
    populated_sheets = [sheet for sheet in workbook.sheets if sheet.used_range]
    range_results = backend.read_ranges(
        [(sheet.name, sheet.used_range) for sheet in populated_sheets],
        path=path,
        include_errors=variant.startswith("semantic-snapshot-")
        or variant == "formula-anomalies-v1",
    )
    results_by_sheet = {
        sheet.name: result for sheet, result in zip(populated_sheets, range_results, strict=True)
    }
    if variant == "formula-anomalies-v1":
        anomaly_sheets = [
            _formula_anomaly_sheet(
                sheet=sheet.name,
                used_range=sheet.used_range,
                result=results_by_sheet[sheet.name],
            )
            for sheet in populated_sheets
        ]
        format_requests = _formula_anomaly_format_requests(anomaly_sheets)
        format_values = backend.read_formats(format_requests, path=path)
        return _formula_anomaly_workbook_observation(
            title=workbook.title,
            url=workbook.url,
            sheets=anomaly_sheets,
            formats=dict(zip(format_requests, format_values, strict=True)),
        )
    known_sheets = {sheet.name for sheet in workbook.sheets}
    selected_sheets = known_sheets if detailed_sheets is None else detailed_sheets & known_sheets
    sheet_observations = []
    for sheet in workbook.sheets:
        if not sheet.used_range:
            sheet_observations.append(
                {
                    "name": sheet.name,
                    "used_range": None,
                    "detail": (
                        "selected" if sheet.name in selected_sheets else "manifest-only"
                    ),
                }
            )
        elif sheet.name not in selected_sheets:
            sheet_observations.append(
                _sheet_manifest(
                    sheet=sheet.name,
                    used_range=sheet.used_range,
                    result=results_by_sheet[sheet.name],
                )
            )
        else:
            sheet_observations.append(
                _structure_sheet_observation(
                    sheet=sheet.name,
                    used_range=sheet.used_range,
                    result=results_by_sheet[sheet.name],
                    include_cell_details=variant.startswith("semantic-snapshot-"),
                    include_candidate_gaps=variant == "semantic-snapshot-v2",
                    include_formula_patterns=variant == "formula-patterns-v1",
                    label_limit=(
                        None
                        if variant.startswith("semantic-snapshot-")
                        else _STRUCTURE_LABEL_LIMIT
                    ),
                )
            )
    observation = {
        "title": workbook.title,
        "url": workbook.url,
        "observation": variant,
        "sheets": sheet_observations,
    }
    if hasattr(backend, "inspect_charts"):
        charts = backend.inspect_charts(path=path)
        if charts:
            observation["charts"] = [
                {
                    "id": chart.get("id"),
                    "sheet": chart.get("sheet"),
                    "title": chart.get("title"),
                    "chart_type": chart.get("chart_type"),
                }
                for chart in charts
            ]
    if variant == "formula-patterns-v1" and selected_sheets:
        observation["blank_dependency_bridges"] = _blank_dependency_bridges(
            [
                (sheet.name, sheet.used_range, results_by_sheet[sheet.name])
                for sheet in populated_sheets
            ],
            selected_sheets=selected_sheets,
        )
    if detailed_sheets is not None:
        observation["detail_scope"] = {
            "requested": sorted(detailed_sheets),
            "returned": sorted(selected_sheets),
            "unknown": sorted(detailed_sheets - known_sheets),
            "note": (
                "All sheets are listed in the manifest. Labels, structural bands, and formula "
                "patterns are returned only for requested sheets; use exact manifest names."
            ),
        }
    return observation


def _mapping_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_keys = set(before)
    after_keys = set(after)
    return {
        "added": {key: after[key] for key in sorted(after_keys - before_keys)},
        "removed": {key: before[key] for key in sorted(before_keys - after_keys)},
        "changed": {
            key: {"before": before[key], "after": after[key]}
            for key in sorted(before_keys & after_keys)
            if before[key] != after[key]
        },
    }


def _values_equivalent(before: Any, after: Any) -> bool:
    if (
        isinstance(before, (int, float))
        and not isinstance(before, bool)
        and isinstance(after, (int, float))
        and not isinstance(after, bool)
    ):
        return math.isclose(
            before,
            after,
            rel_tol=_DIFF_RELATIVE_TOLERANCE,
            abs_tol=_DIFF_ABSOLUTE_TOLERANCE,
        )
    return before == after


def _address_bounding_range(addresses: list[str]) -> str | None:
    parsed = []
    for address in addresses:
        match = _A1_RANGE.fullmatch(address.upper())
        if match is None:
            continue
        column, row, _, _ = match.groups()
        parsed.append((_column_number(column), int(row)))
    if not parsed:
        return None
    min_column = min(column for column, _ in parsed)
    max_column = max(column for column, _ in parsed)
    min_row = min(row for _, row in parsed)
    max_row = max(row for _, row in parsed)
    start = f"{_column_label(min_column)}{min_row}"
    end = f"{_column_label(max_column)}{max_row}"
    return start if start == end else f"{start}:{end}"


def _evenly_spaced_keys(values: dict[str, Any], limit: int) -> list[str]:
    keys = sorted(values, key=_a1_sort_key)
    if len(keys) <= limit:
        return keys
    if limit == 1:
        return keys[:1]
    indexes = [index * (len(keys) - 1) // (limit - 1) for index in range(limit)]
    return [keys[index] for index in indexes]


def _downstream_value_summary(
    changes_by_sheet: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sampled_by_sheet = {
        sheet: _evenly_spaced_keys(changes, _DOWNSTREAM_VALUE_PER_SHEET_LIMIT)
        for sheet, changes in sorted(changes_by_sheet.items())
    }
    selected: list[dict[str, Any]] = []
    for offset in range(_DOWNSTREAM_VALUE_PER_SHEET_LIMIT):
        for sheet, addresses in sampled_by_sheet.items():
            if len(selected) >= _DOWNSTREAM_VALUE_GLOBAL_LIMIT:
                break
            if offset < len(addresses):
                address = addresses[offset]
                selected.append(
                    {
                        "sheet": sheet,
                        "address": address,
                        **changes_by_sheet[sheet][address],
                    }
                )
    total = sum(len(changes) for changes in changes_by_sheet.values())
    return {
        "count": total,
        "by_sheet": {
            sheet: {
                "count": len(changes),
                "affected_range": _address_bounding_range(list(changes)),
            }
            for sheet, changes in sorted(changes_by_sheet.items())
        },
        "representatives": selected,
        "representatives_returned": len(selected),
        "omitted": total - len(selected),
        "note": (
            "Values whose formulas were unchanged, after tight numeric-equivalence filtering. "
            "Counts and affected ranges are complete; representatives are bounded and spatially "
            "sampled. Direct formula/input edits and formula-error transitions remain complete."
        ),
    }


def _candidate_gaps(sheet: dict[str, Any]) -> dict[str, str]:
    return dict(sheet.get("inferred_table", {}).get("candidate_gaps", {}))


def _semantic_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare two semantic snapshots without depending on a Calc backend."""
    before_sheets = {sheet["name"]: sheet for sheet in before.get("sheets", [])}
    after_sheets = {sheet["name"]: sheet for sheet in after.get("sheets", [])}
    common_sheets = sorted(set(before_sheets) & set(after_sheets))
    summary = {
        "sheets_added": len(set(after_sheets) - set(before_sheets)),
        "sheets_removed": len(set(before_sheets) - set(after_sheets)),
        "labels_changed": 0,
        "inputs_added": 0,
        "inputs_removed": 0,
        "inputs_changed": 0,
        "formulas_added": 0,
        "formulas_removed": 0,
        "formulas_changed": 0,
        "formula_values_changed": 0,
        "formula_errors_added": 0,
        "formula_errors_removed": 0,
        "formula_errors_changed": 0,
        "candidate_gaps_resolved": 0,
        "candidate_gaps_new": 0,
        "candidate_gaps_remaining": 0,
    }
    sheet_changes: dict[str, Any] = {}
    downstream_values_by_sheet: dict[str, dict[str, Any]] = {}
    for name in common_sheets:
        before_sheet = before_sheets[name]
        after_sheet = after_sheets[name]
        label_delta = _mapping_delta(before_sheet.get("labels", {}), after_sheet.get("labels", {}))
        input_delta = _mapping_delta(before_sheet.get("inputs", {}), after_sheet.get("inputs", {}))

        before_formulas = before_sheet.get("formulas", {})
        after_formulas = after_sheet.get("formulas", {})
        before_expressions = {
            address: details.get("expression") for address, details in before_formulas.items()
        }
        after_expressions = {
            address: details.get("expression") for address, details in after_formulas.items()
        }
        formula_delta = _mapping_delta(before_expressions, after_expressions)
        formula_error_delta = _mapping_delta(
            before_sheet.get("formula_errors", {}),
            after_sheet.get("formula_errors", {}),
        )
        formula_values_changed = {
            address: {
                "expression": after_formulas[address].get("expression"),
                "before": before_formulas[address].get("value"),
                "after": after_formulas[address].get("value"),
            }
            for address in sorted(set(before_formulas) & set(after_formulas))
            if before_formulas[address].get("expression")
            == after_formulas[address].get("expression")
            and not _values_equivalent(
                before_formulas[address].get("value"),
                after_formulas[address].get("value"),
            )
        }
        if formula_values_changed:
            downstream_values_by_sheet[name] = formula_values_changed

        before_gaps = _candidate_gaps(before_sheet)
        after_gaps = _candidate_gaps(after_sheet)
        resolved_gaps = {key: before_gaps[key] for key in sorted(set(before_gaps) - set(after_gaps))}
        new_gaps = {key: after_gaps[key] for key in sorted(set(after_gaps) - set(before_gaps))}
        remaining_gaps = {
            key: after_gaps[key] for key in sorted(set(before_gaps) & set(after_gaps))
        }

        summary["labels_changed"] += sum(len(values) for values in label_delta.values())
        summary["inputs_added"] += len(input_delta["added"])
        summary["inputs_removed"] += len(input_delta["removed"])
        summary["inputs_changed"] += len(input_delta["changed"])
        summary["formulas_added"] += len(formula_delta["added"])
        summary["formulas_removed"] += len(formula_delta["removed"])
        summary["formulas_changed"] += len(formula_delta["changed"])
        summary["formula_values_changed"] += len(formula_values_changed)
        summary["formula_errors_added"] += len(formula_error_delta["added"])
        summary["formula_errors_removed"] += len(formula_error_delta["removed"])
        summary["formula_errors_changed"] += len(formula_error_delta["changed"])
        summary["candidate_gaps_resolved"] += len(resolved_gaps)
        summary["candidate_gaps_new"] += len(new_gaps)
        summary["candidate_gaps_remaining"] += len(remaining_gaps)

        used_range = {
            "before": before_sheet.get("used_range"),
            "after": after_sheet.get("used_range"),
        }
        has_changes = any(
            (
                used_range["before"] != used_range["after"],
                *(bool(values) for values in label_delta.values()),
                *(bool(values) for values in input_delta.values()),
                *(bool(values) for values in formula_delta.values()),
                bool(formula_values_changed),
                *(bool(values) for values in formula_error_delta.values()),
                bool(resolved_gaps),
                bool(new_gaps),
            )
        )
        if has_changes:
            change: dict[str, Any] = {}
            if used_range["before"] != used_range["after"]:
                change["used_range"] = used_range
            if any(label_delta.values()):
                change["labels"] = label_delta
            if any(input_delta.values()):
                change["inputs"] = input_delta
            if any(formula_delta.values()):
                change["formulas"] = formula_delta
            if any(formula_error_delta.values()):
                change["formula_errors"] = formula_error_delta
            if resolved_gaps or new_gaps:
                change["candidate_gaps"] = {
                    "resolved": resolved_gaps,
                    "new": new_gaps,
                    "note": "Heuristic structural gaps, not validation failures.",
                }
            if change:
                sheet_changes[name] = change

    return {
        "observation": "semantic-diff-v1",
        "before": before.get("title"),
        "after": after.get("title"),
        "sheets_added": sorted(set(after_sheets) - set(before_sheets)),
        "sheets_removed": sorted(set(before_sheets) - set(after_sheets)),
        "summary": summary,
        "downstream_formula_values": _downstream_value_summary(downstream_values_by_sheet),
        "sheet_changes": sheet_changes,
    }


def _format_read_observation(
    result: dict[str, Any],
    *,
    sheet: str,
    cell_range: str,
    variant: str,
) -> dict[str, Any]:
    if variant == "grid-v1":
        return result
    if variant not in {
        "sparse-addressed-v1",
        "structure-first-v1",
        "formula-patterns-v1",
        "formula-anomalies-v1",
        "semantic-snapshot-v1",
        "semantic-snapshot-v2",
    }:
        raise ValueError(f"Unsupported observation variant: {variant}")

    match = _A1_RANGE.fullmatch(cell_range.upper())
    if match is None:
        raise ValueError(f"sparse-addressed-v1 requires an A1 cell or range: {cell_range}")
    start_column, start_row, _, _ = match.groups()
    start_column_number = _column_number(start_column)
    cells = []
    values = result["values"]
    formulas = result["formulas"]
    errors = result.get("errors", [])
    for row_offset, row in enumerate(values):
        for column_offset, value in enumerate(row):
            formula = (
                formulas[row_offset][column_offset]
                if row_offset < len(formulas) and column_offset < len(formulas[row_offset])
                else None
            )
            if value in ("", None) and not str(formula).startswith("="):
                continue
            cell: dict[str, Any] = {
                "address": f"{_column_label(start_column_number + column_offset)}{int(start_row) + row_offset}",
                "value": value,
            }
            if str(formula).startswith("="):
                cell["formula"] = formula
            if row_offset < len(errors) and column_offset < len(errors[row_offset]):
                error = errors[row_offset][column_offset]
                if error:
                    cell["error"] = error
            cells.append(cell)
    return {"sheet": sheet, "range": cell_range.upper(), "cells": cells}


@contextmanager
def _exclusive_runtime() -> Iterator[None]:
    """Serialize independent agent processes against Calc's single UNO runtime."""
    lock_path = os.environ.get("LIBRECALC_LOCK_PATH", "/tmp/librecalc-benchmark.lock")
    with open(lock_path, "w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def main(argv: list[str]) -> int:
    if not argv:
        raise ValueError("missing command")

    backend_type, operation_type = _load_backend_types()
    backend = backend_type()
    command, *args = argv

    if command == "health":
        result = backend.health()
        _emit(result)
        return 0 if result.get("ok") else 1

    if command == "inspect" and len(args) in {1, 2}:
        path = args[0]
        detailed_sheets = set(_parse_sheet_names(args[1])) if len(args) == 2 else set()
        variant = os.environ.get("LIBRECALC_OBSERVATION_VARIANT", "grid-v1")
        _read_budget().reset_read_budget()
        _emit(
            _workbook_observation(
                backend,
                path,
                variant,
                detailed_sheets=detailed_sheets,
            )
        )
        return 0

    if command == "compare" and len(args) == 2:
        before_path, after_path = args
        before = _workbook_observation(backend, before_path, "semantic-snapshot-v2")
        after = _workbook_observation(backend, after_path, "semantic-snapshot-v2")
        _emit(_semantic_diff(before, after))
        return 0

    if command == "read" and len(args) == 3:
        path, sheet, cell_range = args
        if _read_budget().read_budget_error() is not None:
            _emit({"ok": False, "error": _read_budget().read_budget_error()})
            return 1
        if _A1_RANGE.fullmatch(cell_range.upper()) is None:
            raise ValueError(f"invalid A1 range: {cell_range}")
        _require_neighborhood_range(cell_range, label="calc_read range")
        result = backend.read_range(sheet=sheet, cell_range=cell_range, path=path)
        variant = os.environ.get("LIBRECALC_OBSERVATION_VARIANT", "grid-v1")
        _read_budget().consume_read_budget(successful=True)
        _emit(
            _format_read_observation(
                result,
                sheet=sheet,
                cell_range=cell_range,
                variant=variant,
            )
        )
        return 0

    if command == "read-ranges" and len(args) == 2:
        path, raw_requests = args
        if (budget_error := _read_budget().read_budget_error()) is not None:
            _emit({"ok": False, "error": budget_error})
            return 1
        requests = _parse_range_requests(raw_requests)
        valid_requests: list[tuple[str, str]] = []
        valid_indexes: list[int] = []
        formatted: list[dict[str, Any] | None] = [None] * len(requests)
        for index, (sheet, cell_range) in enumerate(requests):
            try:
                _require_neighborhood_range(cell_range, label=f"ranges_json item {index}")
            except ValueError as exc:
                formatted[index] = {
                    "ok": False,
                    "sheet": sheet,
                    "range": cell_range.upper(),
                    "error": f"ValueError: {exc}",
                }
            else:
                valid_requests.append((sheet, cell_range))
                valid_indexes.append(index)

        results = backend.read_ranges(valid_requests, path=path) if valid_requests else []
        variant = os.environ.get("LIBRECALC_OBSERVATION_VARIANT", "grid-v1")
        for index, (request, result) in zip(valid_indexes, zip(valid_requests, results, strict=True)):
            sheet, cell_range = request
            observation = _format_read_observation(
                result,
                sheet=sheet,
                cell_range=cell_range,
                variant=variant,
            )
            if variant == "grid-v1":
                observation = {"sheet": sheet, "range": cell_range.upper(), **observation}
            formatted[index] = observation
        assert all(item is not None for item in formatted)
        _read_budget().consume_read_budget(successful=bool(valid_requests))
        _emit({"ranges": formatted})
        return 0

    if command == "write" and len(args) == 5:
        path, output_path, sheet, cell_range, raw_values = args
        values = _parse_json(raw_values, list, "values_json")
        _emit(
            backend.write_range(
                sheet=sheet,
                cell_range=cell_range,
                values=values,
                path=path,
                output_path=output_path,
            )
        )
        return 0

    if command == "fill-formulas" and len(args) == 3:
        path, output_path, raw_blocks = args
        operations = _formula_blocks(raw_blocks, operation_type)
        _emit(backend.execute_program(operations, path=path, output_path=output_path))
        return 0

    if command == "program" and len(args) == 3:
        path, output_path, raw_operations = args
        operation_dicts = _parse_json(raw_operations, list, "operations_json")
        operations = []
        for index, operation in enumerate(operation_dicts):
            if not isinstance(operation, dict):
                raise TypeError(f"operations_json item {index} must be an object")
            operations.append(operation_type.from_dict(operation))
        _emit(backend.execute_program(operations, path=path, output_path=output_path))
        return 0

    if command == "inspect-charts" and len(args) == 1:
        path = args[0]
        if not hasattr(backend, "inspect_charts"):
            _emit({"ok": False, "error": "backend does not support chart inspection"})
            return 1
        charts = backend.inspect_charts(path=path)
        _emit({"ok": True, "path": path, "count": len(charts), "charts": charts})
        return 0

    if command == "upsert-chart" and len(args) == 3:
        path, output_path, raw_chart = args
        chart = _parse_json(raw_chart, dict, "chart_json")
        operations = [operation_type.from_dict({"op": "upsert_chart", "chart": chart})]
        _emit(backend.execute_program(operations, path=path, output_path=output_path))
        return 0

    raise ValueError(f"invalid arguments for {command!r}")


if __name__ == "__main__":
    try:
        with _exclusive_runtime():
            raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        raise SystemExit(1) from exc
