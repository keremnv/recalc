from librecalc_mcp.backend.memory import MemoryCalcBackend
from librecalc_mcp.domain.models import CalcOperation


def test_program_can_create_and_write_sheet() -> None:
    backend = MemoryCalcBackend()
    result = backend.execute_program(
        [
            CalcOperation(op="create_sheet", name="Analysis"),
            CalcOperation(
                op="write_range", sheet="Analysis", range="A1:B2", values=[[1, 2], [3, 4]]
            ),
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


def test_reads_multiple_ranges_in_request_order() -> None:
    backend = MemoryCalcBackend()
    backend.write_range("Sheet1", "A1:B1", [[1, 2]])
    backend.execute_program([CalcOperation(op="create_sheet", name="Analysis")])
    backend.write_range("Analysis", "C3", [[9]])

    reads = backend.read_ranges(
        [("Analysis", "C3"), ("Sheet1", "A1:B1")],
        include_errors=False,
    )

    assert [read["values"] for read in reads] == [[[9]], [[1, 2]]]


def test_reads_cell_format_fingerprints_in_request_order() -> None:
    backend = MemoryCalcBackend()
    backend.formats["Sheet1"]["B2"] = {
        "font_color": "#0000FF",
        "background_color": "#FFFFFF",
        "background_transparent": False,
        "font_weight": 100.0,
    }

    assert backend.read_formats([("Sheet1", "B2"), ("Sheet1", "C3")]) == [
        {
            "font_color": "#0000FF",
            "background_color": "#FFFFFF",
            "background_transparent": False,
            "font_weight": 100.0,
        },
        {},
    ]


def test_write_reports_explicit_output_path() -> None:
    backend = MemoryCalcBackend()

    result = backend.write_range(
        "Sheet1",
        "A1:B1",
        [[1, 2]],
        path="input.xlsx",
        output_path="output.xlsx",
    )

    assert result["saved_to"] == "output.xlsx"
    assert backend.read_range("Sheet1", "A1:B1")["values"] == [[1, 2]]


def test_program_defaults_to_in_place_save_when_source_path_is_given() -> None:
    backend = MemoryCalcBackend()

    result = backend.execute_program(
        [CalcOperation(op="set_formula", sheet="Sheet1", range="C1", formula="=SUM(A1:B1)")],
        path="model.xlsx",
    )

    assert result["saved_to"] == "model.xlsx"


def test_program_can_fill_a_formula_range() -> None:
    backend = MemoryCalcBackend()

    result = backend.execute_program(
        [
            CalcOperation(
                op="fill_formula",
                sheet="Sheet1",
                range="B2:F2",
                formula="=B3*B4",
            )
        ]
    )

    assert result["ok"] is True
    assert backend.read_range("Sheet1", "B2:F2")["formulas"] == [["=B3*B4"]]


def test_program_normalizes_function_argument_separators() -> None:
    backend = MemoryCalcBackend()

    backend.execute_program(
        [
            CalcOperation(
                op="fill_formula",
                sheet="Sheet1",
                range="C31:F31",
                formula='=IF(C5="Year 4",18000,0)',
            )
        ]
    )

    assert backend.read_range("Sheet1", "C31:F31")["formulas"] == [
        ['=IF(C5="Year 4";18000;0)']
    ]


def test_program_can_clear_a_range_without_removing_the_sheet() -> None:
    backend = MemoryCalcBackend()
    backend.execute_program(
        [CalcOperation(op="set_formula", sheet="Sheet1", range="B2", formula="=1+1")]
    )

    result = backend.execute_program(
        [CalcOperation(op="clear_range", sheet="Sheet1", range="B2")]
    )

    assert result["ok"] is True
    assert backend.read_range("Sheet1", "B2")["formulas"] == []


def test_program_insert_row_shifts_later_stored_ranges() -> None:
    backend = MemoryCalcBackend()
    backend.write_range("Sheet1", "A1", [["keep"]])
    backend.write_range("Sheet1", "A2", [["below"]])
    backend.formulas["Sheet1"]["B2"] = "=A2"

    result = backend.execute_program(
        [CalcOperation(op="insert_row", sheet="Sheet1", index=2)]
    )

    assert result["ok"] is True
    assert result["operations"][0]["count"] == 1
    assert backend.read_range("Sheet1", "A1")["values"] == [["keep"]]
    assert backend.read_range("Sheet1", "A2")["values"] == []
    assert backend.read_range("Sheet1", "A3")["values"] == [["below"]]
    assert backend.read_range("Sheet1", "B3")["formulas"] == [["=A2"]]


def test_program_delete_row_drops_and_shifts_stored_ranges() -> None:
    backend = MemoryCalcBackend()
    backend.write_range("Sheet1", "A1", [["keep"]])
    backend.write_range("Sheet1", "A2", [["gone"]])
    backend.write_range("Sheet1", "A3", [["below"]])

    result = backend.execute_program(
        [CalcOperation(op="delete_row", sheet="Sheet1", index=2, count=1)]
    )

    assert result["ok"] is True
    assert backend.read_range("Sheet1", "A1")["values"] == [["keep"]]
    assert backend.read_range("Sheet1", "A2")["values"] == [["below"]]
    assert backend.read_range("Sheet1", "A3")["values"] == []
