from __future__ import annotations

import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "benchmark/sweagent/formula_index/lib"
sys.path.insert(0, str(LIB))

from fingerprint import Fingerprint, relative_fingerprint  # noqa: E402


def fp(formula: str, col: int = 7, row: int = 10, sheet: str = "Sheet1") -> Fingerprint:
    return relative_fingerprint(formula, col, row, sheet=sheet)


def test_translated_copies_share_a_fingerprint() -> None:
    left = fp("=F10-F15", col=6, row=10)
    right = fp("=G10-G15", col=7, row=10)
    assert left.opaque is False
    assert left.text == right.text
    assert left.eq_id == right.eq_id
    assert left.text == "=C[0]R[0]-C[0]R[5]"


def test_raw_strings_that_differ_geometrically_do_not_collapse() -> None:
    plus_row = fp("=A1+B1", col=1, row=1)
    plus_col = fp("=A1+A2", col=1, row=1)
    assert plus_row.text != plus_col.text
    assert plus_row.eq_id != plus_col.eq_id


def test_range_is_distinct_from_scalar_pair() -> None:
    spanned = fp("=A1:B1", col=1, row=1)
    added = fp("=A1+B1", col=1, row=1)
    assert spanned.text != added.text
    assert ":" in spanned.text
    assert "+" in added.text


def test_absolute_dollars_are_preserved() -> None:
    result = fp("=$A$1+B2", col=2, row=2)
    assert "$A$1" in result.text
    assert "C[0]R[0]" in result.text


def test_sheet_qualification_is_preserved() -> None:
    result = fp("='P&L'!A1", col=2, row=2)
    assert "'P&L'!" in result.text
    assert "C[-1]R[-1]" in result.text


def test_log10_is_not_an_a1_reference() -> None:
    result = fp("=LOG10(A1)", col=1, row=1)
    assert result.opaque is False
    assert "LOG10" in result.text
    assert "C[0]R[0]" in result.text


def test_indirect_is_opaque_and_does_not_merge_with_a1() -> None:
    dynamic = fp('=INDIRECT("A1")', col=1, row=1)
    static = fp("=A1", col=1, row=1)
    assert dynamic.opaque is True
    assert dynamic.reason == "dynamic_ref"
    assert dynamic.text.startswith("OPAQUE:")
    assert static.opaque is False
    assert dynamic.eq_id != static.eq_id


def test_offset_is_opaque() -> None:
    result = fp("=OFFSET(A1,1,0)", col=1, row=1)
    assert result.opaque is True
    assert result.reason == "dynamic_ref"


def test_opaque_formulas_are_location_singletons() -> None:
    first = fp("=INDIRECT(B1)", col=1, row=1, sheet="Model")
    second = fp("=INDIRECT(B1)", col=5, row=9, sheet="Model")
    same_cell = fp("=INDIRECT(B1)", col=1, row=1, sheet="Model")
    other_sheet = fp("=INDIRECT(B1)", col=1, row=1, sheet="Other")
    other = fp("=INDIRECT(C1)", col=1, row=1, sheet="Model")
    assert first.opaque is True
    assert first.eq_id != second.eq_id
    assert first.eq_id == same_cell.eq_id
    assert first.eq_id != other_sheet.eq_id
    assert first.eq_id != other.eq_id
    assert first.text.startswith("OPAQUE:")
    assert second.text.startswith("OPAQUE:")


def test_named_range_is_opaque() -> None:
    named = fp("=Revenue", col=3, row=4)
    a1 = fp("=A1", col=3, row=4)
    assert named.opaque is True
    assert named.reason == "named_range"
    assert named.eq_id != a1.eq_id


def test_structured_reference_is_opaque() -> None:
    result = fp("=SUM(Table1[Amount])", col=1, row=1)
    assert result.opaque is True
    assert result.reason == "structured_ref"


def test_three_d_reference_is_opaque() -> None:
    result = fp("=SUM(Sheet1:Sheet3!A1)", col=1, row=1)
    assert result.opaque is True
    assert result.reason == "three_d"


def test_r1c1_is_opaque() -> None:
    result = fp("=R1C1", col=1, row=1)
    assert result.opaque is True
    assert result.reason == "r1c1"


def test_opaque_never_collides_with_canonical_prefix() -> None:
    canonical = fp("=A1+B1", col=1, row=1)
    opaque = fp("=INDIRECT(A1)", col=1, row=1)
    assert not canonical.text.startswith("OPAQUE:")
    assert opaque.text.startswith("OPAQUE:")
    assert canonical.eq_id != opaque.eq_id
