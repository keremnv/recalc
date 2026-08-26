from librecalc_mcp.backend.memory import MemoryCalcBackend
from librecalc_mcp.domain.models import CalcOperation


def test_memory_upsert_and_inspect_chart_roundtrip() -> None:
    backend = MemoryCalcBackend()
    spec = {
        "id": "sales_chart",
        "sheet": "Sheet1",
        "chart_type": "line",
        "category_range": "A2:A5",
        "series": [{"name": "Revenue", "values_range": "B2:B5"}],
        "title": "Revenue Trend",
    }
    result = backend.execute_program(
        [CalcOperation.from_dict({"op": "upsert_chart", "chart": spec})]
    )
    assert result["ok"] is True
    assert result["operations"][0]["ok"] is True
    charts = backend.inspect_charts()
    assert len(charts) == 1
    assert charts[0]["id"] == "sales_chart"
    assert charts[0]["title"] == "Revenue Trend"
    assert charts[0]["compile_note"] is None


def test_memory_sunburst_marks_unsupported() -> None:
    backend = MemoryCalcBackend()
    result = backend.execute_program(
        [
            CalcOperation.from_dict(
                {
                    "op": "upsert_chart",
                    "chart": {
                        "id": "sun",
                        "sheet": "Sheet1",
                        "chart_type": "sunburst",
                        "category_range": "A1:A3",
                        "series": [{"name": "X", "values_range": "B1:B3"}],
                    },
                }
            )
        ]
    )
    assert result["operations"][0]["compile_note"] == "unsupported"
    assert result["operations"][0]["ok"] is False


def test_memory_delete_chart() -> None:
    backend = MemoryCalcBackend()
    chart = {
        "id": "c1",
        "sheet": "Sheet1",
        "chart_type": "pie",
        "category_range": "A1:A2",
        "series": [{"name": "S", "values_range": "B1:B2"}],
    }
    backend.execute_program([CalcOperation.from_dict({"op": "upsert_chart", "chart": chart})])
    backend.execute_program([CalcOperation.from_dict({"op": "delete_chart", "name": "c1"})])
    assert backend.inspect_charts() == []


def test_memory_backend_round_trips_bubble_x_y_size_and_label_ranges() -> None:
    backend = MemoryCalcBackend()
    chart = {
        "id": "portfolio",
        "sheet": "Sheet1",
        "chart_type": "bubble",
        "category_range": "A2:A5",
        "series": [
            {
                "name": "Products",
                "x_values_range": "B2:B5",
                "values_range": "C2:C5",
                "bubble_size_range": "D2:D5",
            }
        ],
    }

    backend.execute_program([CalcOperation.from_dict({"op": "upsert_chart", "chart": chart})])

    inspected = backend.inspect_charts()
    assert inspected[0]["category_range"] == "A2:A5"
    assert inspected[0]["series"][0]["x_values_range"] == "B2:B5"
    assert inspected[0]["series"][0]["values_range"] == "C2:C5"
    assert inspected[0]["series"][0]["bubble_size_range"] == "D2:D5"
