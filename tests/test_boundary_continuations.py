from __future__ import annotations

from datetime import date

from openpyxl import Workbook

from benchmark.boundary_continuations import enumerate_boundary_continuations, select_arm


def _workbooks() -> tuple[Workbook, Workbook]:
    raw = Workbook()
    raw.active.title = "Schedule"
    values = Workbook()
    values.active.title = "Schedule"
    return raw, values


def test_date_formula_run_nominates_styled_right_boundary() -> None:
    raw, values = _workbooks()
    raw_sheet, value_sheet = raw.active, values.active
    for address, formula, value in (
        ("J3", "=EOMONTH(I3,12)", date(2028, 3, 31)),
        ("K3", "=EOMONTH(J3,12)", date(2029, 3, 31)),
        ("L3", "=EOMONTH(K3,12)", date(2030, 3, 31)),
    ):
        raw_sheet[address] = formula
        raw_sheet[address].number_format = "yyyy-mm-dd"
        value_sheet[address] = value
    raw_sheet["M3"].number_format = "yyyy-mm-dd"

    candidates = enumerate_boundary_continuations(raw, values, instruction="Build forecast")

    assert len(candidates) == 1
    candidate = candidates[0]
    assert (candidate.sheet, candidate.address) == ("Schedule", "M3")
    assert candidate.inferred_formula == "=EOMONTH(L3,12)"
    assert candidate.run_length == 3
    assert candidate.style_match is True
    assert candidate.date_like is True
    assert select_arm(candidates, "date+style") == candidates


def test_internal_gap_is_not_a_right_boundary_candidate() -> None:
    raw, values = _workbooks()
    sheet = raw.active
    sheet["B2"], sheet["C2"], sheet["D2"] = "=A1", "=B1", None
    sheet["E2"] = "=D1"

    assert enumerate_boundary_continuations(raw, values, instruction="Schedule") == []


def test_nontranslated_trailing_formulas_do_not_form_a_run() -> None:
    raw, values = _workbooks()
    sheet = raw.active
    sheet["B2"], sheet["C2"], sheet["D2"] = "=A1", "=SUM(A1)", "=C1"
    sheet["E2"].number_format = "0.0"

    assert enumerate_boundary_continuations(raw, values, instruction="Schedule") == []
