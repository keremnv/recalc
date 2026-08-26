import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from librecalc_mcp.domain.models import CalcOperation


def _calc_tool_module():
    path = Path(__file__).parents[1] / "benchmark/sweagent/librecalc/lib/calc_tool.py"
    spec = importlib.util.spec_from_file_location("benchmark_calc_tool", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calc_tool_read_budget_blocks_second_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calc_tool = _calc_tool_module()
    monkeypatch.setenv("LIBRECALC_READ_BUDGET_ENABLED", "1")
    monkeypatch.setenv("LIBRECALC_READ_BUDGET_PATH", str(tmp_path / "budget.json"))
    calc_tool._read_budget().reset_read_budget()
    calc_tool._read_budget().consume_read_budget(successful=True)
    assert calc_tool._read_budget().read_budget_error() is not None


@pytest.mark.skipif(os.environ.get("LIBRECALC_RUN_UNO") != "1", reason="requires LibreOffice UNO")
def test_uno_chart_xlsx_roundtrip_openpyxl_count() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    from librecalc_mcp.backend.uno import UnoCalcBackend

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "chart_source.xlsx"
        backend = UnoCalcBackend()
        backend.execute_program(
            [
                CalcOperation(
                    op="write_range",
                    sheet="Sheet1",
                    range="A1:B4",
                    values=[
                        ["Month", "Sales"],
                        ["Jan", 10],
                        ["Feb", 20],
                        ["Mar", 30],
                    ],
                ),
                CalcOperation.from_dict(
                    {
                        "op": "upsert_chart",
                        "chart": {
                            "id": "SalesLine",
                            "sheet": "Sheet1",
                            "chart_type": "line",
                            "category_range": "A2:A4",
                            "series": [{"name": "Sales", "values_range": "B2:B4"}],
                            "title": "Sales",
                            "anchor": "D2",
                        },
                    }
                ),
            ],
            path=None,
            output_path=str(source),
        )
        profile = tempfile.mkdtemp()
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                f"-env:UserInstallation=file://{profile}",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(root),
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        workbook = openpyxl.load_workbook(source)
        chart_count = sum(len(getattr(sheet, "_charts", []) or []) for sheet in workbook.worksheets)
        assert chart_count >= 1


@pytest.mark.skipif(os.environ.get("LIBRECALC_RUN_UNO") != "1", reason="requires LibreOffice UNO")
def test_uno_chart_axis_titles_data_labels_and_point_colors() -> None:
    from librecalc_mcp.backend.uno import UnoCalcBackend

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "in.xlsx"
        output = root / "styled.xlsx"
        # Minimal xlsx seed so UNO has a path to open.
        try:
            from openpyxl import Workbook

            wb = Workbook()
            wb.active.title = "Sheet1"
            wb.save(source)
        except Exception:
            pytest.skip("openpyxl required to seed workbook")

        backend = UnoCalcBackend()
        backend.execute_program(
            [
                CalcOperation(
                    op="write_range",
                    sheet="Sheet1",
                    range="A1:B5",
                    values=[
                        ["Cat", "Val"],
                        ["A", 10],
                        ["B", 20],
                        ["C", 30],
                        ["D", 40],
                    ],
                ),
                CalcOperation.from_dict(
                    {
                        "op": "upsert_chart",
                        "chart": {
                            "id": "Styled",
                            "sheet": "Sheet1",
                            "chart_type": "column",
                            "category_range": "A2:A5",
                            "series": [
                                {
                                    "name": "Val",
                                    "values_range": "B2:B5",
                                    "color": "#3366FF",
                                    "point_colors": ["#00AA00", "#FF0000", "#0000FF", "#FFAA00"],
                                }
                            ],
                            "title": "Styled Columns",
                            "legend": False,
                            "data_labels": True,
                            "x_axis": {"title": "Category"},
                            "y_axis": {"title": "Value"},
                            "anchor": "D2",
                            "width": 10,
                            "height": 12,
                        },
                    }
                ),
            ],
            path=str(source),
            output_path=str(output),
        )

        backend._connect()
        uno = backend._uno()
        doc = backend._desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(str(output.resolve())), "_blank", 0, ()
        )
        try:
            chart_doc = (
                doc.Sheets.getByName("Sheet1").getCharts().getByIndex(0).getEmbeddedObject()
            )
            diagram = chart_doc.getDiagram()
            assert getattr(diagram, "HasXAxisTitle", False) is True
            assert diagram.XAxisTitle.String == "Category"
            assert getattr(diagram, "HasYAxisTitle", False) is True
            assert diagram.YAxisTitle.String == "Value"
            assert diagram.getDataRowProperties(0).DataCaption == 4  # TEXT

            series = (
                chart_doc.getFirstDiagram()
                .getCoordinateSystems()[0]
                .getChartTypes()[0]
                .getDataSeries()[0]
            )
            assert series.getDataPointByIndex(0).FillColor == 0x00AA00
            assert series.getDataPointByIndex(1).FillColor == 0xFF0000
            assert series.getDataPointByIndex(0).Label.ShowCategoryName is True
        finally:
            doc.close(True)
