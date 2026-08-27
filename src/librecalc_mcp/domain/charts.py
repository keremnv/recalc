from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Literal

ChartType = Literal[
    "column",
    "clustered_column",
    "stacked_column",
    "bar",
    "stacked_bar",
    "line",
    "area",
    "pie",
    "doughnut",
    "scatter",
    "bubble",
    "combo",
    "pareto",
    "waterfall",
    "gauge",
    "sunburst",
]
AxisBinding = Literal["primary", "secondary"]

# LibreOffice chart Rectangle uses 1/100 mm (HMM). SpreadsheetBench goldens mostly use
# Excel twoCellAnchor spans (~8 columns × ~15 rows); Excel's common inserted chart is ~5"×3".
EXCEL_DEFAULT_COL_WIDTH_HMM = 1700  # ~64px @ 96dpi
EXCEL_DEFAULT_ROW_HEIGHT_HMM = 530  # ~15pt
DEFAULT_CHART_COL_SPAN = 8
DEFAULT_CHART_ROW_SPAN = 15
DEFAULT_CHART_WIDTH_HMM = DEFAULT_CHART_COL_SPAN * EXCEL_DEFAULT_COL_WIDTH_HMM  # 13600
DEFAULT_CHART_HEIGHT_HMM = DEFAULT_CHART_ROW_SPAN * EXCEL_DEFAULT_ROW_HEIGHT_HMM  # 7950
# Floor so postage-stamp charts cannot be created accidentally.
MIN_CHART_WIDTH_HMM = 5000  # 5 cm
MIN_CHART_HEIGHT_HMM = 3000  # 3 cm
# Agents often send Excel-like col/row spans (e.g. width=16, height=9) instead of HMM.
_CELL_SPAN_MAX = 64


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def normalize_chart_size_hmm(
    *,
    width: Any = None,
    height: Any = None,
    col_span: Any = None,
    row_span: Any = None,
) -> tuple[int, int]:
    """Return (width_hmm, height_hmm) matching Excel/SpreadsheetBench defaults.

    Accepts:
    - omitted size → Excel-like ~8×15 cell default
    - col_span / row_span → converted with Excel default col/row sizes
    - small width+height (both ≤ 64) → treated as col/row spans (agent habit)
    - otherwise width/height as LibreOffice HMM (1/100 mm)
    """
    span_cols = _as_optional_int(col_span)
    span_rows = _as_optional_int(row_span)
    raw_w = _as_optional_int(width)
    raw_h = _as_optional_int(height)

    if span_cols is not None or span_rows is not None:
        cols = span_cols if span_cols is not None else DEFAULT_CHART_COL_SPAN
        rows = span_rows if span_rows is not None else DEFAULT_CHART_ROW_SPAN
        width_hmm = cols * EXCEL_DEFAULT_COL_WIDTH_HMM
        height_hmm = rows * EXCEL_DEFAULT_ROW_HEIGHT_HMM
    elif raw_w is None and raw_h is None:
        width_hmm = DEFAULT_CHART_WIDTH_HMM
        height_hmm = DEFAULT_CHART_HEIGHT_HMM
    elif (
        raw_w is not None
        and raw_h is not None
        and 0 < raw_w <= _CELL_SPAN_MAX
        and 0 < raw_h <= _CELL_SPAN_MAX
    ):
        width_hmm = raw_w * EXCEL_DEFAULT_COL_WIDTH_HMM
        height_hmm = raw_h * EXCEL_DEFAULT_ROW_HEIGHT_HMM
    else:
        width_hmm = raw_w if raw_w is not None else DEFAULT_CHART_WIDTH_HMM
        height_hmm = raw_h if raw_h is not None else DEFAULT_CHART_HEIGHT_HMM

    return max(width_hmm, MIN_CHART_WIDTH_HMM), max(height_hmm, MIN_CHART_HEIGHT_HMM)


@dataclass(frozen=True)
class ChartSeriesSpec:
    name: str | None
    values_range: str
    # Optional worksheet cell that supplies the live series label. This is needed
    # when a series uses a row slice whose header is not immediately above it.
    name_range: str | None = None
    chart_type: ChartType | None = None
    axis: AxisBinding = "primary"
    # Scatter/bubble X values are independent from category/data-label text.
    x_values_range: str | None = None
    bubble_size_range: str | None = None
    color: str | None = None
    # Per-point fill colors (hex), e.g. bubble/column point overrides.
    point_colors: tuple[str, ...] | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ChartSeriesSpec:
        allowed = {item.name for item in fields(cls)}
        payload = {key: raw[key] for key in raw if key in allowed}
        colors = payload.get("point_colors")
        if colors is not None:
            if not isinstance(colors, (list, tuple)):
                raise ValueError("series.point_colors must be a list of hex colors")
            payload["point_colors"] = tuple(str(item) for item in colors)
        values_range = payload.get("values_range")
        if not isinstance(values_range, str) or not values_range.strip():
            raise ValueError("series.values_range is required")
        # Optional in the type, but a required dataclass field; missing name used to
        # leak TypeError from __init__ instead of an agent-recoverable ValueError.
        payload.setdefault("name", None)
        return cls(**payload)


@dataclass(frozen=True)
class ChartAxisSpec:
    title: str | None = None
    min: float | None = None
    max: float | None = None
    number_format: str | None = None
    label_rotation: float | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ChartAxisSpec | None:
        if not raw:
            return None
        if not isinstance(raw, dict):
            # ValueError, not TypeError: the benchmark wrappers turn ValueError into a
            # structured agent-recoverable observation. See calc_tool._require_neighborhood_range.
            raise ValueError("axis spec must be an object")  # noqa: TRY004
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: raw[key] for key in raw if key in allowed})

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "min": self.min,
            "max": self.max,
            "number_format": self.number_format,
            "label_rotation": self.label_rotation,
        }


@dataclass(frozen=True)
class ChartSpec:
    id: str
    sheet: str
    chart_type: ChartType
    category_range: str
    series: tuple[ChartSeriesSpec, ...]
    title: str | None = None
    legend: bool = True
    anchor: str = "A1"
    width: int = DEFAULT_CHART_WIDTH_HMM
    height: int = DEFAULT_CHART_HEIGHT_HMM
    primary_axis_title: str | None = None
    secondary_axis_title: str | None = None
    data_labels: bool = False
    category_axis: ChartAxisSpec | None = None
    value_axis: ChartAxisSpec | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ChartSpec:
        series_raw = raw.get("series") or []
        if not isinstance(series_raw, list) or not series_raw:
            raise ValueError("chart.series must be a non-empty list")
        series = tuple(ChartSeriesSpec.from_dict(item) for item in series_raw)
        if raw.get("chart_type") == "bubble":
            for index, item in enumerate(series):
                if item.x_values_range is None or item.bubble_size_range is None:
                    raise ValueError(
                        "bubble series requires x_values_range, values_range (Y), "
                        f"and bubble_size_range (series {index})"
                    )
        # Agents often send x_axis / y_axis; accept those aliases.
        category_axis = ChartAxisSpec.from_dict(raw.get("category_axis") or raw.get("x_axis"))
        value_axis = ChartAxisSpec.from_dict(raw.get("value_axis") or raw.get("y_axis"))
        width_hmm, height_hmm = normalize_chart_size_hmm(
            width=raw.get("width"),
            height=raw.get("height"),
            col_span=raw.get("col_span"),
            row_span=raw.get("row_span"),
        )
        anchor_raw = raw.get("anchor", "A1")
        if not isinstance(anchor_raw, str):
            # Benchmark wrappers convert ValueError into a structured, agent-recoverable
            # observation. A TypeError would leak out as a harness failure instead.
            raise ValueError("chart.anchor must be an A1 cell such as E1")  # noqa: TRY004
        return cls(
            id=str(raw["id"]),
            sheet=str(raw["sheet"]),
            chart_type=raw["chart_type"],
            category_range=str(raw["category_range"]),
            series=series,
            title=raw.get("title"),
            legend=bool(raw.get("legend", True)),
            anchor=anchor_raw,
            width=width_hmm,
            height=height_hmm,
            primary_axis_title=raw.get("primary_axis_title")
            or (category_axis.title if category_axis else None),
            secondary_axis_title=raw.get("secondary_axis_title"),
            data_labels=bool(raw.get("data_labels", False)),
            category_axis=category_axis,
            value_axis=value_axis,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "sheet": self.sheet,
            "chart_type": self.chart_type,
            "category_range": self.category_range,
            "series": [
                {
                    "name": item.name,
                    "name_range": item.name_range,
                    "values_range": item.values_range,
                    "chart_type": item.chart_type,
                    "axis": item.axis,
                    "x_values_range": item.x_values_range,
                    "bubble_size_range": item.bubble_size_range,
                    "color": item.color,
                    **(
                        {"point_colors": list(item.point_colors)}
                        if item.point_colors is not None
                        else {}
                    ),
                }
                for item in self.series
            ],
            "title": self.title,
            "legend": self.legend,
            "anchor": self.anchor,
            "width": self.width,
            "height": self.height,
            "primary_axis_title": self.primary_axis_title,
            "secondary_axis_title": self.secondary_axis_title,
            "data_labels": self.data_labels,
        }
        if self.category_axis is not None:
            payload["category_axis"] = self.category_axis.to_dict()
        if self.value_axis is not None:
            payload["value_axis"] = self.value_axis.to_dict()
        return payload


NATIVE_UNO_CHART_TYPES: frozenset[ChartType] = frozenset(
    {
        "column",
        "clustered_column",
        "stacked_column",
        "bar",
        "stacked_bar",
        "line",
        "area",
        "pie",
        "doughnut",
        "scatter",
        "bubble",
    }
)


def chart_compile_note(chart_type: ChartType) -> str | None:
    if chart_type in NATIVE_UNO_CHART_TYPES:
        return None
    if chart_type in {"combo", "pareto"}:
        return "approximated"
    if chart_type in {"waterfall", "gauge"}:
        return "scaffold"
    if chart_type == "sunburst":
        return "unsupported"
    return "unsupported"
