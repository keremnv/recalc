import os
from pathlib import Path

import pytest

from librecalc_mcp.backend.uno import UnoCalcBackend
from librecalc_mcp.domain.models import CalcOperation

pytestmark = [
    pytest.mark.uno,
    pytest.mark.skipif(
        os.environ.get("LIBRECALC_RUN_UNO") != "1",
        reason="set LIBRECALC_RUN_UNO=1 and start LibreOffice to run UNO integration tests",
    ),
]


def test_program_persists_output_copy_without_changing_source(tmp_path) -> None:
    backend = UnoCalcBackend()
    assert backend.health()["ok"] is True

    fixture_path = Path(__file__).parent / "fixtures" / "smoke.csv"
    workbook = backend.inspect_workbook(str(fixture_path))
    sheet = workbook.sheets[0].name
    source_path = tmp_path / "source.xlsx"
    output_path = tmp_path / "output.xlsx"

    backend.write_range(
        sheet,
        "A1:B3",
        [["Revenue", "Cost"], [100, 60], [80, 30]],
        path=str(fixture_path),
        output_path=str(source_path),
    )
    result = backend.execute_program(
        [
            CalcOperation(
                op="fill_formula",
                sheet=sheet,
                range="C2:E3",
                formula="=A2-B2",
            )
        ],
        path=str(source_path),
        output_path=str(output_path),
    )

    assert result["saved_to"] == str(output_path)
    assert output_path.is_file()
    assert backend.read_range(sheet, "A1:E3", str(output_path))["values"] == [
        ["Revenue", "Cost", "", "", ""],
        [100.0, 60.0, 40.0, 20.0, 20.0],
        [80.0, 30.0, 50.0, -20.0, 70.0],
    ]
    assert backend.read_range(sheet, "C2", str(source_path))["values"] == [[""]]

    in_place = backend.execute_program(
        [CalcOperation(op="set_formula", sheet=sheet, range="C2", formula="=A2-B2")],
        path=str(source_path),
    )
    assert in_place["saved_to"] == str(source_path)
    assert backend.read_range(sheet, "C2", str(source_path))["values"] == [[40.0]]

    backend.execute_program(
        [CalcOperation(op="clear_range", sheet=sheet, range="E2:E3")],
        path=str(output_path),
    )
    assert backend.read_range(sheet, "E2:E3", str(output_path))["values"] == [[""], [""]]


def test_excel_style_function_arguments_round_trip_through_uno(tmp_path) -> None:
    backend = UnoCalcBackend()
    assert backend.health()["ok"] is True
    fixture_path = Path(__file__).parent / "fixtures" / "smoke.csv"
    sheet = backend.inspect_workbook(str(fixture_path)).sheets[0].name
    source_path = tmp_path / "conditional-source.xlsx"
    output_path = tmp_path / "conditional-output.xlsx"

    backend.write_range(
        sheet,
        "A1:A2",
        [["Period"], ["Year 4"]],
        path=str(fixture_path),
        output_path=str(source_path),
    )
    backend.execute_program(
        [
            CalcOperation(
                op="set_formula",
                sheet=sheet,
                range="B2",
                formula='=IF(A2="Year 4",18000,0)',
            )
        ],
        path=str(source_path),
        output_path=str(output_path),
    )

    result = backend.read_range(sheet, "B2", str(output_path))
    assert result["values"] == [[18000.0]]
    assert result["formulas"] == [['=IF(A2="Year 4";18000;0)']]


def test_formula_errors_are_exposed_by_uno(tmp_path) -> None:
    backend = UnoCalcBackend()
    assert backend.health()["ok"] is True
    fixture_path = Path(__file__).parent / "fixtures" / "smoke.csv"
    sheet = backend.inspect_workbook(str(fixture_path)).sheets[0].name
    output_path = tmp_path / "error-output.xlsx"

    backend.execute_program(
        [CalcOperation(op="set_formula", sheet=sheet, range="C2", formula="=1/0")],
        path=str(fixture_path),
        output_path=str(output_path),
    )

    result = backend.read_range(sheet, "C2", str(output_path))
    assert result["formulas"] == [["=1/0"]]
    assert result["errors"] == [["#DIV/0!"]]


def test_program_insert_row_shifts_values_on_uno(tmp_path) -> None:
    backend = UnoCalcBackend()
    assert backend.health()["ok"] is True
    fixture_path = Path(__file__).parent / "fixtures" / "smoke.csv"
    sheet = backend.inspect_workbook(str(fixture_path)).sheets[0].name
    source_path = tmp_path / "insert-source.xlsx"
    output_path = tmp_path / "insert-output.xlsx"

    backend.write_range(
        sheet,
        "A1:A2",
        [["keep"], ["below"]],
        path=str(fixture_path),
        output_path=str(source_path),
    )
    backend.execute_program(
        [
            CalcOperation(op="insert_row", sheet=sheet, index=2),
            CalcOperation(op="set_formula", sheet=sheet, range="A2", formula='="inserted"'),
        ],
        path=str(source_path),
        output_path=str(output_path),
    )

    values = backend.read_range(sheet, "A1:A3", str(output_path))["values"]
    assert values[0] == ["keep"]
    assert values[1] == ["inserted"]
    assert values[2] == ["below"]


def test_single_cell_write_range_persists(tmp_path) -> None:
    backend = UnoCalcBackend()
    assert backend.health()["ok"] is True
    fixture_path = Path(__file__).parent / "fixtures" / "smoke.csv"
    sheet = backend.inspect_workbook(str(fixture_path)).sheets[0].name
    output_path = tmp_path / "single-cell-output.xlsx"

    result = backend.write_range(
        sheet,
        "C3",
        [[3]],
        path=str(fixture_path),
        output_path=str(output_path),
    )

    assert result["ok"] is True
    assert backend.read_range(sheet, "C3", str(output_path))["values"] == [[3.0]]
