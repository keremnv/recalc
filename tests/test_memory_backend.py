from librecalc_mcp.backend.memory import MemoryCalcBackend
from librecalc_mcp.domain.models import CalcOperation


def test_program_can_create_and_write_sheet() -> None:
    backend = MemoryCalcBackend()
    result = backend.execute_program(
        [
            CalcOperation(op="create_sheet", name="Analysis"),
            CalcOperation(op="write_range", sheet="Analysis", range="A1:B2", values=[[1, 2], [3, 4]]),
            CalcOperation(op="set_formula", sheet="Analysis", range="C1", formula="=SUM(A1:B1)"),
        ]
    )

    assert result["ok"] is True
    read = backend.read_range("Analysis", "A1:B2")
    assert read["values"] == [[1, 2], [3, 4]]
    assert backend.read_range("Analysis", "C1")["formulas"] == [["=SUM(A1:B1)"]]


def test_inspection_lists_sheets() -> None:
    backend = MemoryCalcBackend()
    backend.execute_program([CalcOperation(op="create_sheet", name="Model")])
    info = backend.inspect_workbook()
    assert [sheet.name for sheet in info.sheets] == ["Sheet1", "Model"]
