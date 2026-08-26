import pytest

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


def test_sliced_series_round_trips_explicit_name_range() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "slice",
            "sheet": "Sheet1",
            "chart_type": "column",
            "category_range": "A22:A41",
            "series": [
                {"name": "Foo", "name_range": "B1", "values_range": "B22:B41"},
                {"name": "Faa", "name_range": "C1", "values_range": "C22:C41"},
            ],
        }
    )
    assert spec.series[0].name_range == "B1"
    assert spec.series[1].name_range == "C1"
    assert spec.to_dict()["series"][0]["name_range"] == "B1"


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
                    "x_values_range": "B2:B4",
                    "values_range": "C2:C4",
                    "bubble_size_range": "D2:D4",
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


def test_bubble_chart_requires_and_round_trips_all_four_semantic_ranges() -> None:
    spec = ChartSpec.from_dict(
        {
            "id": "portfolio",
            "sheet": "Strategy",
            "chart_type": "bubble",
            "category_range": "M5:M13",
            "series": [
                {
                    "name": "Portfolio",
                    "name_range": "O4",
                    "x_values_range": "N5:N13",
                    "values_range": "O5:O13",
                    "bubble_size_range": "P5:P13",
                }
            ],
        }
    )

    assert spec.series[0].x_values_range == "N5:N13"
    assert spec.series[0].name_range == "O4"
    assert spec.series[0].values_range == "O5:O13"
    assert spec.series[0].bubble_size_range == "P5:P13"
    assert spec.to_dict()["series"][0] == {
        "name": "Portfolio",
        "name_range": "O4",
        "values_range": "O5:O13",
        "chart_type": None,
        "axis": "primary",
        "x_values_range": "N5:N13",
        "bubble_size_range": "P5:P13",
        "color": None,
    }


@pytest.mark.parametrize(
    "series",
    [
        {"name": "Portfolio", "values_range": "O5:O13", "bubble_size_range": "P5:P13"},
        {"name": "Portfolio", "values_range": "O5:O13", "x_values_range": "N5:N13"},
    ],
)
def test_bubble_chart_rejects_missing_x_or_size_range(series: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="bubble series requires"):
        ChartSpec.from_dict(
            {
                "id": "portfolio",
                "sheet": "Strategy",
                "chart_type": "bubble",
                "category_range": "M5:M13",
                "series": [series],
            }
        )


def test_chart_spec_rejects_object_anchor() -> None:
    with pytest.raises(ValueError, match="chart.anchor must be an A1 cell"):
        ChartSpec.from_dict(
            {
                "id": "c1",
                "sheet": "Sheet1",
                "chart_type": "column",
                "category_range": "A2:A5",
                "series": [{"name": "Foo", "values_range": "B2:B5"}],
                "anchor": {"cell": "E1"},
            }
        )


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
