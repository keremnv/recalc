from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark-data/SpreadsheetBench-2/evaluation"))

import evaluation as ev

from benchmark.target_classification import classify_cache_robust_targets


def _book(value) -> Workbook:
    workbook = Workbook()
    workbook.active["A1"] = value
    return workbook


def test_equivalent_formula_with_different_value_is_not_a_direct_target() -> None:
    result = classify_cache_robust_targets(
        ev,
        _book(None),
        _book(42),
        _book("=$B$1"),
        _book("=b1"),
        "Sheet",
        "A1",
    )

    assert result.modification == ()
    assert result.regression == ("A1",)
    assert result.unchanged_formula_value_differences == ("A1",)


def test_different_formula_with_different_cache_remains_a_target() -> None:
    result = classify_cache_robust_targets(
        ev,
        _book(1),
        _book(2),
        _book("=B1"),
        _book("=C1"),
        "Sheet",
        "A1",
    )

    assert result.modification == ("A1",)
    assert result.unchanged_formula_value_differences == ()


def test_different_formula_with_both_caches_absent_is_reported_indeterminate() -> None:
    result = classify_cache_robust_targets(
        ev,
        _book(None),
        _book(None),
        _book("=B1"),
        _book("=C1"),
        "Sheet",
        "A1",
    )

    assert result.modification == ()
    assert result.indeterminate_uncached_formula_differences == ("A1",)
    assert result.value_equivalent_formula_differences == ("A1",)


def test_zero_valued_golden_formula_is_reported_as_dynamic_only() -> None:
    result = classify_cache_robust_targets(
        ev,
        _book(None),
        _book(0),
        _book(None),
        _book("=B1"),
        "Sheet",
        "A1",
    )

    assert result.modification == ()
    assert result.value_equivalent_formula_differences == ("A1",)
    assert result.indeterminate_uncached_formula_differences == ()


def test_color_change_is_not_removed_as_an_unchanged_formula() -> None:
    input_raw = _book("=B1")
    answer_raw = _book("=B1")
    input_raw.active["A1"].font = Font(color="000000")
    answer_raw.active["A1"].font = Font(color="FF0000")

    result = classify_cache_robust_targets(
        ev,
        _book(None),
        _book(42),
        input_raw,
        answer_raw,
        "Sheet",
        "A1",
        with_font_color=True,
    )

    assert result.modification == ("A1",)
    assert result.unchanged_formula_value_differences == ()


def test_formula_mode_uses_the_official_raw_formula_split_unchanged() -> None:
    input_book = _book("=B1")
    answer_book = _book("=C1")

    result = classify_cache_robust_targets(
        ev,
        input_book,
        answer_book,
        input_book,
        answer_book,
        "Sheet",
        "A1",
        with_formula=True,
    )

    assert result.modification == ("A1",)
    assert result.unchanged_formula_value_differences == ()
    assert result.value_equivalent_formula_differences == ()
