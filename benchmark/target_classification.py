"""Cache-robust target classification for offline benchmark analysis.

SpreadsheetBench 2 classifies value-mode modification cells by comparing cached
values in the distributed input and golden workbooks. An unchanged formula can
therefore be classified as a modification because an upstream golden edit changes
its result, or because one distributed cache is stale or absent. In either case,
the formula cell itself needs no direct edit.

This module does not replace or patch official scoring. It separates unchanged-
formula value differences from *offline direct-edit* target sets. It does not
claim those differences are cache artifacts: proving that requires recalculating
the untouched input. Cases where both caches are absent and raw formulas differ
are reported as indeterminate instead of being guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TargetClassification:
    """Official split plus cache diagnostics for one scored range."""

    regression: tuple[str, ...]
    modification: tuple[str, ...]
    unchanged_formula_value_differences: tuple[str, ...]
    value_equivalent_formula_differences: tuple[str, ...]
    indeterminate_uncached_formula_differences: tuple[str, ...]


def _formula_value(value: Any) -> str | None:
    text = getattr(value, "text", value)
    if isinstance(text, str) and text.startswith("="):
        return text
    return None


def classify_cache_robust_targets(
    evaluator,
    wb_input_values,
    wb_answer_values,
    wb_input_raw,
    wb_answer_raw,
    sheet_name: str,
    cell_range: str,
    *,
    with_font_color: bool = False,
    with_formula: bool = False,
) -> TargetClassification:
    """Return an offline split separating direct edits from unchanged formulas.

    ``evaluator`` is the vendored SpreadsheetBench 2 evaluation module.  Keeping
    it explicit makes this helper usable without importing or modifying vendored
    benchmark code.
    """

    official_regression, official_modification = evaluator.classify_cells_by_modification(
        wb_input_values,
        wb_answer_values,
        sheet_name,
        cell_range,
        with_font_color,
        with_formula,
        wb_input_raw,
        wb_answer_raw,
    )
    if with_formula:
        return TargetClassification(
            tuple(official_regression),
            tuple(official_modification),
            (),
            (),
            (),
        )

    input_values = evaluator._find_sheet(wb_input_values, sheet_name)
    answer_values = evaluator._find_sheet(wb_answer_values, sheet_name)
    input_raw = evaluator._find_sheet(wb_input_raw, sheet_name)
    answer_raw = evaluator._find_sheet(wb_answer_raw, sheet_name)
    if None in (input_values, answer_values, input_raw, answer_raw):
        return TargetClassification(
            tuple(official_regression),
            tuple(official_modification),
            (),
            (),
            (),
        )

    unchanged_formula_values: list[str] = []
    modification: list[str] = []
    for address in official_modification:
        input_formula = _formula_value(input_raw[address].value)
        answer_formula = _formula_value(answer_raw[address].value)
        formulas_match = (
            input_formula is not None
            and answer_formula is not None
            and evaluator.compare_cell_formula(input_raw[address], answer_raw[address])
        )
        colors_match = not with_font_color or evaluator.compare_font_color(
            input_raw[address].font, answer_raw[address].font
        )
        if formulas_match and colors_match:
            unchanged_formula_values.append(address)
        else:
            modification.append(address)

    value_equivalent_formula_differences: list[str] = []
    indeterminate: list[str] = []
    for address in official_regression:
        input_formula = _formula_value(input_raw[address].value)
        answer_formula = _formula_value(answer_raw[address].value)
        if input_formula is None and answer_formula is None:
            continue
        formulas_match = evaluator.compare_cell_formula(input_raw[address], answer_raw[address])
        if not formulas_match:
            value_equivalent_formula_differences.append(address)
            both_caches_absent = (
                input_values[address].value is None and answer_values[address].value is None
            )
            if both_caches_absent:
                indeterminate.append(address)

    regression = [*official_regression, *unchanged_formula_values]
    return TargetClassification(
        tuple(regression),
        tuple(modification),
        tuple(unchanged_formula_values),
        tuple(value_equivalent_formula_differences),
        tuple(indeterminate),
    )


__all__ = ["TargetClassification", "classify_cache_robust_targets"]
