from __future__ import annotations

from openpyxl import Workbook

from benchmark.blank_ranking import (
    BlankCandidate,
    adjacent_label,
    enumerate_blank_candidates,
    instruction_sheet_names,
    shortlist,
)


def test_instruction_sheet_names_match_longest_workbook_titles() -> None:
    names = instruction_sheet_names(
        "In the Valuation sheet, calculate WACC. In the Working Capital Schedule sheet, "
        "calculate Receivables.",
        ["Valuation", "WACC", "Working Capital Schedule", "IS"],
    )
    assert names == {"Valuation", "WACC", "Working Capital Schedule"}


def test_instruction_sheet_names_skip_tiny_colliding_titles() -> None:
    names = instruction_sheet_names("In the Valuation sheet, calculate WACC.", ["IS", "Valuation"])
    assert names == {"Valuation"}


def test_adjacent_label_reads_the_cell_above() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Valuation"
    sheet["G58"] = "WACC"
    assert adjacent_label(sheet, 7, 59) == "WACC"


def test_named_block_label_keeps_g59_shape_and_drops_isolated_blanks() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Valuation"
    sheet["G58"] = "WACC"
    sheet["H59"] = "=E48"
    sheet["G60"] = "=E49"
    sheet["A1"] = None  # isolated blank
    sheet["B2"] = None
    candidates = enumerate_blank_candidates(
        workbook,
        instruction="In the Valuation sheet, calculate WACC.",
        demanded=set(),
    )
    g59 = next(item for item in candidates if item.address == "G59")
    assert g59.block_peer is True
    assert g59.label == "WACC"
    assert g59.named_sheet is True
    kept = {(item.sheet, item.address) for item in shortlist(candidates, "named-block-label")}
    assert ("Valuation", "G59") in kept
    assert ("Valuation", "A1") not in kept


def test_rank_score_prefers_labelled_block_peers() -> None:
    strong = BlankCandidate(
        "Valuation", "G59", True, True, referenced=False, label="WACC", named_sheet=True
    )
    weak = BlankCandidate(
        "Valuation", "A1", False, False, referenced=False, label=None, named_sheet=True
    )
    assert strong.score() > weak.score()
    ranked = shortlist([weak, strong], "named-rank-top-20")
    assert ranked[0].address == "G59"
