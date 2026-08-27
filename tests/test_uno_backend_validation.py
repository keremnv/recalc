from pathlib import Path

import pytest

from librecalc_mcp.backend.uno import UnoCalcBackend, _pythonize_uno_error, a1_range_address


def test_missing_workbook_fails_before_uno_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = UnoCalcBackend()
    monkeypatch.setattr(
        backend,
        "_connect",
        lambda: pytest.fail("UNO connection attempted for a missing workbook"),
    )
    missing_path = tmp_path / "missing.xlsx"

    with pytest.raises(FileNotFoundError, match="Spreadsheet path does not exist"):
        backend.inspect_workbook(str(missing_path))


def test_a1_range_address_includes_single_cells() -> None:
    assert a1_range_address("C9") == (2, 8, 2, 8)
    assert a1_range_address("A1:B2") == (0, 0, 1, 1)
    assert a1_range_address("aa10:ab12") == (26, 9, 27, 11)


def test_a1_range_address_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="invalid A1 range"):
        a1_range_address("9C")
    with pytest.raises(ValueError, match="inverted A1 range"):
        a1_range_address("B2:A1")


def test_pythonize_uno_error_wraps_foreign_exceptions() -> None:
    class FakeUnoError(Exception):
        pass

    FakeUnoError.__module__ = "uno"
    converted = _pythonize_uno_error(FakeUnoError("Couldn't convert traceback"))
    assert isinstance(converted, RuntimeError)
    assert str(converted) == "FakeUnoError: Couldn't convert traceback"


def test_pythonize_uno_error_keeps_builtin_exceptions() -> None:
    exc = ValueError("write_range requires values")
    assert _pythonize_uno_error(exc) is exc


def test_cell_is_populated_accepts_int_and_enum_cell_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from enum import Enum

    from librecalc_mcp.backend.uno import _apply_values, _cell_is_populated

    class CellType(Enum):
        EMPTY = 0
        VALUE = 1
        FORMULA = 3

    class Cell:
        def __init__(self, cell_type: object) -> None:
            self.Type = cell_type
            self.Formula = ""
            self.Value = 0.0
            self.String = ""

        def clearContents(self, _flags: int) -> None:
            return None

    assert _cell_is_populated(Cell(0)) is False
    assert _cell_is_populated(Cell(CellType.EMPTY)) is False
    assert _cell_is_populated(Cell(1)) is True
    assert _cell_is_populated(Cell(CellType.VALUE)) is True
    assert _cell_is_populated(Cell(CellType.FORMULA)) is True

    occupied = Cell(CellType.VALUE)
    blank = Cell(CellType.EMPTY)

    class Sheet:
        def getCellByPosition(self, column: int, row: int) -> Cell:
            return occupied if (column, row) == (0, 0) else blank

    monkeypatch.setenv("LIBRECALC_PRESERVE_POPULATED", "1")
    skipped = _apply_values(Sheet(), "A1:B1", [["overwrite", "new"]])

    assert skipped == 1
    assert occupied.String == ""
    assert blank.String == "new"

