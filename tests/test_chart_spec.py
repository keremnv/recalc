from librecalc_mcp.domain.charts import (
    DEFAULT_CHART_HEIGHT_HMM,
    DEFAULT_CHART_WIDTH_HMM,
    EXCEL_DEFAULT_COL_WIDTH_HMM,
    EXCEL_DEFAULT_ROW_HEIGHT_HMM,
    ChartSpec,
    normalize_chart_size_hmm,
)


def test_chart_spec_accepts_x_y_axis_aliases() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "burndown",
            "sheet": "Count",
            "chart_type": "line",
            "category_range": "Data!A6:A46",
            "series": [
                {"name": "Goal", "values_range": "Data!D6:D46", "color": "#0000FF"},
                {"name": "Count", "values_range": "Data!G6:G46", "color": "#808080"},
            ],
            "title": "Invoice Count Burndown August 2023",
            "x_axis": {"number_format": "dd/mm/yyyy", "label_rotation": 45},
            "y_axis": {"min": 0, "max": 800},
        }
    )
    assert spec.category_axis is not None
    assert spec.category_axis.number_format == "dd/mm/yyyy"
    assert spec.category_axis.label_rotation == 45
    assert spec.value_axis is not None
    assert spec.value_axis.min == 0
    assert spec.value_axis.max == 800
    assert spec.series[0].color == "#0000FF"


def test_chart_series_ignores_unknown_keys() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "c1",
            "sheet": "Sheet1",
            "chart_type": "column",
            "category_range": "A1:A2",
            "series": [{"name": "S", "values_range": "B1:B2", "extra": "ignored"}],
        }
    )
    assert spec.series[0].name == "S"


def test_chart_series_accepts_point_colors() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "bub",
            "sheet": "Sheet1",
            "chart_type": "bubble",
            "category_range": "A2:A4",
            "series": [
                {
                    "name": "P",
                    "values_range": "B2:B4",
                    "point_colors": ["#00FF00", "#FF0000", "#0000FF"],
                }
            ],
            "data_labels": True,
        }
    )
    assert spec.data_labels is True
    assert spec.series[0].point_colors == ("#00FF00", "#FF0000", "#0000FF")
    assert spec.to_dict()["series"][0]["point_colors"] == [
        "#00FF00",
        "#FF0000",
        "#0000FF",
    ]


def test_chart_size_defaults_match_excel_cell_span() -> None:
    assert normalize_chart_size_hmm() == (
        DEFAULT_CHART_WIDTH_HMM,
        DEFAULT_CHART_HEIGHT_HMM,
    )
    width, height = normalize_chart_size_hmm(width=16, height=9)
    assert width == 16 * EXCEL_DEFAULT_COL_WIDTH_HMM
    assert height == 9 * EXCEL_DEFAULT_ROW_HEIGHT_HMM


def test_chart_spec_treats_small_width_height_as_excel_spans() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "c1",
            "sheet": "Sheet1",
            "chart_type": "column",
            "category_range": "A1:A2",
            "series": [{"name": "S", "values_range": "B1:B2"}],
            "width": 16,
            "height": 9,
        }
    )
    assert spec.width == 16 * EXCEL_DEFAULT_COL_WIDTH_HMM
    assert spec.height == 9 * EXCEL_DEFAULT_ROW_HEIGHT_HMM


def test_chart_spec_accepts_explicit_col_row_span() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "c1",
            "sheet": "Sheet1",
            "chart_type": "line",
            "category_range": "A1:A2",
            "series": [{"name": "S", "values_range": "B1:B2"}],
            "col_span": 8,
            "row_span": 15,
        }
    )
    assert spec.width == DEFAULT_CHART_WIDTH_HMM
    assert spec.height == DEFAULT_CHART_HEIGHT_HMM


def test_chart_spec_preserves_large_hmm_sizes() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "c1",
            "sheet": "Sheet1",
            "chart_type": "pie",
            "category_range": "A1:A2",
            "series": [{"name": "S", "values_range": "B1:B2"}],
            "width": 12000,
            "height": 8000,
        }
    )
    assert spec.width == 12000
    assert spec.height == 8000
