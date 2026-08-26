"""Compiled observation models: what an agent sees when it looks at a workbook.

PROJECT_CONTEXT.md section 9.1 -- observation is a compiled interface, not a dump. It
is the read half of the world, and the evidence says it controls the action threshold
more than model choice does: bounding these payloads on Financial_Model:01_03 cut
prompt tokens 68% and cost 63% while leaving the produced workbook byte-identical.

Everything here is deterministic and backend-independent: it consumes CalcBackend
results, never UNO. Deterministic workbook facts (labels, formulas, values, occupied
regions) are kept in separate fields from heuristic affordances (candidate gaps,
translation shortlists, dependency bridges), which are always marked as heuristics and
must never silently become task requirements.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from itertools import pairwise
from typing import Any

from librecalc_mcp.domain.formulas import (
    formula_a1_references,
    formula_a1_shape,
    translate_a1_formula,
)
from librecalc_mcp.domain.grid import (
    A1_RANGE,
    a1_cell_count,
    a1_sort_key,
    cell_kind,
    column_label,
    column_number,
    is_formula,
    matrix_value,
    spans,
    spreadsheet_error_kind,
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

def _formula_anomaly_sheet(
    *,
    sheet: str,
    used_range: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Find compact formula-consistency signals without declaring cells incorrect."""

    match = A1_RANGE.fullmatch(used_range.upper())
    if match is None:
        raise ValueError(f"used range must be an A1 range: {used_range}")
    start_column, start_row, end_column, end_row = match.groups()
    end_column = end_column or start_column
    end_row = end_row or start_row
    start_column_number = column_number(start_column)
    row_count = int(end_row) - int(start_row) + 1
    column_count = column_number(end_column) - start_column_number + 1
    values = result.get("values", [])
    formulas = result.get("formulas", [])
    errors = result.get("errors", [])

    def address(row: int, column: int) -> str:
        return f"{column_label(start_column_number + column)}{int(start_row) + row}"

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
                value = matrix_value(values, source_row, source_column)
                formula = matrix_value(formulas, source_row, source_column)
                if is_formula(formula) or value is None or value == "":
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
            formula = matrix_value(formulas, row, column)
            value = matrix_value(values, row, column)
            if is_formula(formula):
                formula_cells += 1
                error_kind = spreadsheet_error_kind(
                    formula, matrix_value(errors, row, column)
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
                    source_formula = matrix_value(formulas, source_row, source_column)
                    if not is_formula(source_formula):
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
            formula = matrix_value(formulas, row, column)
            if is_formula(formula):
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
                    matrix_value(values, row, column)
                    for column in range(left_column + 1, right_column)
                ]
                gap_formulas = [
                    matrix_value(formulas, row, column)
                    for column in range(left_column + 1, right_column)
                ]
                if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in gap_values):
                    continue
                if any(is_formula(formula) for formula in gap_formulas):
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
        address_match = A1_RANGE.fullmatch(candidate["address"])
        if address_match is None:
            continue
        column, row, _, _ = address_match.groups()
        grouped_candidates[
            (candidate["sheet"], int(row), formula_a1_shape(candidate["inferred_formula"]))
        ].append((column_number(column), candidate))
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
        cells.sort(key=lambda cell: a1_sort_key(cell["address"]))
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
        key=lambda cell: (-cell["repeat_count"], cell["sheet"], a1_sort_key(cell["address"]))
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
        key=lambda cell: (-cell["repeat_count"], cell["sheet"], a1_sort_key(cell["address"])),
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

def formula_anomaly_format_requests(sheets: list[dict[str, Any]]) -> list[tuple[str, str]]:
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
    match = A1_RANGE.fullmatch(used_range.upper())
    if match is None:
        raise ValueError(f"used range must be an A1 range: {used_range}")
    start_column, start_row, end_column, end_row = match.groups()
    end_column = end_column or start_column
    end_row = end_row or start_row
    start_column_number = column_number(start_column)
    column_count = column_number(end_column) - start_column_number + 1
    row_count = int(end_row) - int(start_row) + 1
    values = result.get("values", [])
    formulas = result.get("formulas", [])
    errors = result.get("errors", [])
    row_labels = [str(int(start_row) + offset) for offset in range(row_count)]
    column_labels = [column_label(start_column_number + offset) for offset in range(column_count)]

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
            kind = cell_kind(value, formula)
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

    row_signatures = [spans(row) for row in kinds]
    column_signatures = [
        spans([kinds[row][column] for row in range(row_count)])
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

    sheet_cells: dict[str, dict[str, tuple[Any, Any]]] = {}
    formula_cells: dict[tuple[str, str], str] = {}
    for sheet, used_range, result in sheets:
        match = A1_RANGE.fullmatch(used_range.upper())
        if match is None:
            continue
        start_column, start_row, end_column, end_row = match.groups()
        end_column = end_column or start_column
        end_row = end_row or start_row
        start_column_number = column_number(start_column)
        row_count = int(end_row) - int(start_row) + 1
        column_count = column_number(end_column) - start_column_number + 1
        values = result.get("values", [])
        formulas = result.get("formulas", [])
        cells: dict[str, tuple[Any, Any]] = {}
        for row in range(row_count):
            for column in range(column_count):
                address = (
                    f"{column_label(start_column_number + column)}"
                    f"{int(start_row) + row}"
                )
                value = matrix_value(values, row, column)
                formula = matrix_value(formulas, row, column)
                cells[address] = (value, formula)
                if is_formula(formula):
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
                if value in (None, "") and not is_formula(precedent_formula):
                    blank_dependents[precedent].add(dependent)
                continue
            try:
                cell_count = a1_cell_count(f"{start}:{end}")
            except ValueError:
                continue
            if cell_count > _DEPENDENCY_RANGE_MAX_CELLS:
                continue
            range_match = A1_RANGE.fullmatch(f"{start}:{end}")
            if range_match is None:
                continue
            start_column, start_row, end_column, end_row = range_match.groups()
            assert end_column is not None and end_row is not None
            for row in range(int(start_row), int(end_row) + 1):
                for column in range(
                    column_number(start_column), column_number(end_column) + 1
                ):
                    reverse_dependencies[(source_sheet, f"{column_label(column)}{row}")].add(
                        dependent
                    )

    def carry_chain(dependent: tuple[str, str], step: int) -> list[tuple[str, str]]:
        match = A1_RANGE.fullmatch(dependent[1])
        if match is None:
            return [dependent]
        column, row, _, _ = match.groups()
        column_index = column_number(column)
        chain = [dependent]
        current = dependent
        while column_index + step > 0:
            column_index += step
            candidate = (dependent[0], f"{column_label(column_index)}{row}")
            if current not in direct_dependencies.get(candidate, set()):
                break
            chain.append(candidate)
            current = candidate
        return chain

    def row_label(sheet: str, address: str, relation: str) -> dict[str, Any] | None:
        match = A1_RANGE.fullmatch(address)
        if match is None:
            return None
        column, row, _, _ = match.groups()
        column_index = column_number(column)
        for source_column in range(column_index - 1, max(0, column_index - 8), -1):
            source_address = f"{column_label(source_column)}{row}"
            value, formula = sheet_cells[sheet].get(source_address, (None, None))
            if isinstance(value, str) and value and not is_formula(formula):
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
            a1_sort_key(candidate["address"]),
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

def workbook_observation(
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
        format_requests = formula_anomaly_format_requests(anomaly_sheets)
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

def format_read_observation(
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

    match = A1_RANGE.fullmatch(cell_range.upper())
    if match is None:
        raise ValueError(f"sparse-addressed-v1 requires an A1 cell or range: {cell_range}")
    start_column, start_row, _, _ = match.groups()
    start_column_number = column_number(start_column)
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
                "address": f"{column_label(start_column_number + column_offset)}{int(start_row) + row_offset}",
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
