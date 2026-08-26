"""write_range must honour Calc's cell-entry rule for strings beginning with '='.

Storing such a string as literal text produces a cell whose `formulas` field reads
back looking correct while its calculated value is the text itself, so the loss is
invisible to read-back verification and only shows up in value-mode scoring.
"""

from __future__ import annotations

import os

import pytest

from librecalc_mcp.backend.memory import MemoryCalcBackend
from librecalc_mcp.domain.formulas import is_escaped_text, is_formula_text, unescape_text


def test_domain_rule_matches_calc_cell_entry() -> None:
    assert is_formula_text("=A1+B1")
    assert not is_formula_text("A1+B1")
    assert not is_formula_text(5)
    assert not is_formula_text(None)
    # An escaped literal is text, not a formula.
    assert not is_formula_text("'=A1+B1")
    assert is_escaped_text("'=A1+B1")
    assert unescape_text("'=A1+B1") == "=A1+B1"
    assert unescape_text("plain") == "plain"


def test_memory_write_range_records_a_formula_not_text() -> None:
    backend = MemoryCalcBackend()
    result = backend.write_range("Sheet1", "C1", [["=A1+B1"]])

    assert result["formulas_written"] == 1
    assert backend.read_range("Sheet1", "C1")["formulas"] == [["=A1+B1"]]


def test_memory_write_range_normalizes_argument_separators() -> None:
    backend = MemoryCalcBackend()
    backend.write_range("Sheet1", "C1", [["=IF(A1>0,A1,0)"]])

    assert backend.read_range("Sheet1", "C1")["formulas"] == [["=IF(A1>0;A1;0)"]]


def test_memory_write_range_unescapes_literal_text() -> None:
    backend = MemoryCalcBackend()
    result = backend.write_range("Sheet1", "C1", [["'=A1+B1"]])

    assert result["formulas_written"] == 0
    assert backend.read_range("Sheet1", "C1")["values"] == [["=A1+B1"]]


def test_memory_write_range_leaves_plain_values_alone() -> None:
    backend = MemoryCalcBackend()
    result = backend.write_range("Sheet1", "A1:B1", [[2, "Revenue"]])

    assert result["formulas_written"] == 0
    assert backend.read_range("Sheet1", "A1:B1")["values"] == [[2, "Revenue"]]


@pytest.mark.uno
@pytest.mark.skipif(os.environ.get("LIBRECALC_RUN_UNO") != "1", reason="requires LibreOffice")
def test_uno_write_range_formula_calculates(tmp_path) -> None:
    from openpyxl import Workbook

    from librecalc_mcp.backend.uno import UnoCalcBackend

    source = tmp_path / "seed.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"], sheet["B1"] = 2, 3
    workbook.save(source)

    output = tmp_path / "out.xlsx"
    backend = UnoCalcBackend()
    # Single cell, and a multi-cell matrix mixing a value with a formula.
    backend.write_range("Sheet1", "C1", [["=A1+B1"]], str(source), str(output))
    backend.write_range("Sheet1", "E1:F1", [[10, "=A1*2"]], str(output), str(output))

    read = backend.read_range("Sheet1", "C1:F1", str(output))
    assert read["values"][0][0] == 5.0, "C1 stored as text instead of a formula"
    assert read["values"][0][2] == 10
    assert read["values"][0][3] == 4.0, "E1:F1 matrix dropped its formula"
