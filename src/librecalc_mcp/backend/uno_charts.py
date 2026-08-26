from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from librecalc_mcp.domain.charts import (
    MIN_CHART_HEIGHT_HMM,
    MIN_CHART_WIDTH_HMM,
    NATIVE_UNO_CHART_TYPES,
    ChartAxisSpec,
    ChartSpec,
    ChartType,
    chart_compile_note,
)


class _ApplyLog:
    """Records which ChartSpec fields actually reached LibreOffice.

    UNO property support varies by diagram type and by version, so applying a chart
    field is a probe rather than a guarantee. Swallowing those failures silently makes
    an agent that under-specified a chart indistinguishable from a world that dropped
    what the agent did specify -- the two have opposite fixes. Every probe is recorded.
    """

    def __init__(self) -> None:
        self.applied: list[str] = []
        self.dropped: list[str] = []

    def record(self, feature: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.applied.append(feature)
        else:
            self.dropped.append(f"{feature} ({detail})" if detail else feature)

    @contextmanager
    def probe(self, feature: str, *, record_success: bool = True) -> Iterator[None]:
        try:
            yield
        except Exception as exc:
            self.record(feature, False, type(exc).__name__)
        else:
            if record_success:
                self.record(feature, True)


def _column_index(label: str) -> int:
    value = 0
    for character in label.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _anchor_position(anchor: str) -> tuple[int, int]:
    letters = ""
    digits = ""
    for character in anchor:
        if character.isalpha():
            letters += character
        elif character.isdigit():
            digits += character
    if not letters or not digits:
        raise ValueError(f"invalid chart anchor: {anchor}")
    return _column_index(letters), int(digits) - 1


def _diagram_service_name(chart_type: ChartType) -> str:
    mapping = {
        "column": "com.sun.star.chart.BarDiagram",
        "clustered_column": "com.sun.star.chart.BarDiagram",
        "stacked_column": "com.sun.star.chart.BarDiagram",
        "bar": "com.sun.star.chart.BarDiagram",
        "stacked_bar": "com.sun.star.chart.BarDiagram",
        "line": "com.sun.star.chart.LineDiagram",
        "area": "com.sun.star.chart.AreaDiagram",
        "pie": "com.sun.star.chart.PieDiagram",
        "doughnut": "com.sun.star.chart.DonutDiagram",
        "scatter": "com.sun.star.chart.XYDiagram",
        "bubble": "com.sun.star.chart.BubbleDiagram",
    }
    try:
        return mapping[chart_type]
    except KeyError as exc:
        raise ValueError(f"unsupported UNO chart type: {chart_type}") from exc


def _chart_type_from_diagram(diagram: Any) -> str:
    if diagram is None:
        return "unknown"
    service = ""
    for attr in ("getImplementationName", "ImplementationName"):
        try:
            value = getattr(diagram, attr)
            service = str(value() if callable(value) else value)
            if service:
                break
        except Exception:
            continue
    lowered = service.lower()
    if "donut" in lowered:
        return "doughnut"
    if "pie" in lowered:
        return "pie"
    if "line" in lowered:
        return "line"
    if "area" in lowered:
        return "area"
    if "bubble" in lowered:
        return "bubble"
    if "xy" in lowered or "scatter" in lowered:
        return "scatter"
    if "bar" in lowered:
        vertical = getattr(diagram, "Vertical", True)
        try:
            is_vertical = bool(vertical)
        except Exception:
            is_vertical = True
        return "column" if is_vertical else "bar"
    return "unknown"


def _chart_type_from_document(chart_doc: Any, diagram: Any) -> str:
    """Read a chart type through Chart2, falling back to legacy Chart1 properties."""

    try:
        coordinate_systems = chart_doc.getFirstDiagram().getCoordinateSystems()
        chart_types = coordinate_systems[0].getChartTypes() if coordinate_systems else ()
        type_name = str(chart_types[0].getChartType()).lower() if chart_types else ""
    except Exception:
        type_name = ""
    if "bubble" in type_name:
        return "bubble"
    if "scatter" in type_name:
        return "scatter"
    if "line" in type_name:
        return "line"
    if "area" in type_name:
        return "area"
    if "pie" in type_name:
        return "pie"
    if "column" in type_name or "bar" in type_name:
        stacked = bool(getattr(diagram, "Stacked", False))
        vertical = bool(getattr(diagram, "Vertical", True))
        if vertical:
            return "stacked_column" if stacked else "column"
        return "stacked_bar" if stacked else "bar"
    return _chart_type_from_diagram(diagram)


def _split_range_reference(range_ref: str, default_sheet: str) -> tuple[str, str]:
    if "!" in range_ref:
        sheet_name, cell_range = range_ref.split("!", 1)
        return sheet_name.strip("'"), cell_range
    if "." in range_ref:
        sheet_name, cell_range = range_ref.split(".", 1)
        if sheet_name and cell_range[:1].isalpha():
            return sheet_name.strip("'"), cell_range
    return default_sheet, range_ref


def _range_address(doc: Any, range_ref: str, *, default_sheet: str) -> Any:
    return _range_object(doc, range_ref, default_sheet=default_sheet).getRangeAddress()


def _range_object(doc: Any, range_ref: str, *, default_sheet: str) -> Any:
    sheet_name, cell_range = _split_range_reference(range_ref, default_sheet)
    sheet = doc.Sheets.getByName(sheet_name)
    return sheet.getCellRangeByName(cell_range)


def _range_representation(doc: Any, range_ref: str, *, default_sheet: str) -> str:
    return str(_range_object(doc, range_ref, default_sheet=default_sheet).AbsoluteName)


def _shape_for_chart_name(sheet: Any, chart_name: str) -> Any | None:
    page = sheet.getDrawPage()
    for index in range(page.Count):
        shape = page.getByIndex(index)
        try:
            if str(shape.PersistName) == str(chart_name):
                return shape
        except Exception:
            continue
    return None


def chart_collection_name_for_id(sheet: Any, requested_id: str) -> str | None:
    """Resolve a stable ChartSpec id after XLSX renames the embedded object."""

    charts = sheet.getCharts()
    if requested_id in charts.getElementNames():
        return requested_id
    for chart_name in charts.getElementNames():
        shape = _shape_for_chart_name(sheet, chart_name)
        if shape is not None and str(getattr(shape, "Name", "")) == requested_id:
            return str(chart_name)
    return None


def _set_requested_chart_id(sheet: Any, chart_name: str, requested_id: str) -> bool:
    shape = _shape_for_chart_name(sheet, chart_name)
    if shape is None:
        return False
    shape.Name = requested_id
    return str(shape.Name) == requested_id


def _read_title(chart: Any, chart_doc: Any) -> str | None:
    for owner in (chart_doc, chart):
        if owner is None:
            continue
        try:
            if getattr(owner, "HasMainTitle", False):
                title = getattr(owner, "Title", None)
                if title is not None and getattr(title, "String", None):
                    return str(title.String)
        except Exception:
            pass
        try:
            title = getattr(owner, "Title", None)
            if title is not None and getattr(title, "String", None):
                return str(title.String)
        except Exception:
            pass
    return None


def _parse_rgb(color: str | None) -> int | None:
    if not color:
        return None
    text = color.strip().lstrip("#")
    if len(text) == 6:
        return int(text, 16)
    if len(text) == 8:
        # 8 hex digits are ARGB; drop the alpha pair (not an 0x prefix).
        return int(text[2:], 16)  # noqa: FURB166
    return None


def _apply_diagram_type(chart_doc: Any, chart_type: ChartType, log: _ApplyLog) -> None:
    service = _diagram_service_name(chart_type)
    diagram = chart_doc.createInstance(service)
    if chart_type in {"column", "clustered_column", "stacked_column"}:
        with log.probe("orientation.column"):
            diagram.Vertical = True
    if chart_type in {"bar", "stacked_bar"}:
        with log.probe("orientation.bar"):
            diagram.Vertical = False
    if chart_type in {"stacked_column", "stacked_bar"}:
        with log.probe("stacked"):
            diagram.Stacked = True
    chart_doc.setDiagram(diagram)


def _apply_axis(
    diagram: Any,
    axis_name: str,
    axis: ChartAxisSpec | None,
    fallback_title: str | None,
    log: _ApplyLog,
    *,
    chart_doc: Any | None = None,
) -> None:
    if axis is None and not fallback_title:
        return

    title = (axis.title if axis else None) or fallback_title
    # LibreOffice Chart1: enable axis title shapes, then set String.
    # (Axis.DisplayTitle / Axis.Title are unreliable across diagram types.)
    has_attr = f"Has{axis_name}Title"
    title_attr = f"{axis_name}Title"
    if title:
        feature = f"{axis_name.lower()}.title"
        applied = False
        with log.probe(feature, record_success=False):
            if hasattr(diagram, has_attr):
                setattr(diagram, has_attr, True)
            title_shape = getattr(diagram, title_attr, None)
            if title_shape is not None and hasattr(title_shape, "String"):
                title_shape.String = str(title)
                # Read back: setting String is accepted on shapes that never render.
                applied = str(getattr(title_shape, "String", "")) == str(title)
        if not applied:
            with log.probe(f"{feature}.displaytitle", record_success=False):
                uno_axis = getattr(diagram, axis_name)
                if hasattr(uno_axis, "DisplayTitle"):
                    uno_axis.DisplayTitle = True
                axis_title = getattr(uno_axis, "Title", None) or getattr(
                    uno_axis, "AxisTitle", None
                )
                if axis_title is not None and hasattr(axis_title, "String"):
                    axis_title.String = str(title)
                    applied = str(getattr(axis_title, "String", "")) == str(title)
        log.record(feature, applied, "" if applied else "not accepted by diagram")

    if axis is None:
        return
    try:
        uno_axis = getattr(diagram, axis_name)
    except Exception as exc:
        log.record(f"{axis_name.lower()}.scale", False, type(exc).__name__)
        return
    if axis.min is not None:
        with log.probe(f"{axis_name.lower()}.min"):
            uno_axis.AutoMin = False
            uno_axis.Min = float(axis.min)
    if axis.max is not None:
        with log.probe(f"{axis_name.lower()}.max"):
            uno_axis.AutoMax = False
            uno_axis.Max = float(axis.max)
    if axis.label_rotation is not None:
        with log.probe(f"{axis_name.lower()}.label_rotation"):
            uno_axis.TextRotation = int(axis.label_rotation) * 100
    if axis.number_format is not None:
        feature = f"{axis_name.lower()}.number_format"
        with log.probe(feature, record_success=False):
            if chart_doc is None:
                raise ValueError("chart document unavailable")
            formats = chart_doc.getNumberFormats()
            current_key = int(getattr(uno_axis, "NumberFormat", 0))
            try:
                locale = formats.getByKey(current_key).Locale
            except Exception:
                locale = formats.getByKey(0).Locale
            format_key = formats.queryKey(str(axis.number_format), locale, True)
            if format_key == -1:
                format_key = formats.addNew(str(axis.number_format), locale)
            if hasattr(uno_axis, "LinkNumberFormatToSource"):
                uno_axis.LinkNumberFormatToSource = False
            uno_axis.NumberFormat = format_key
            applied = formats.getByKey(int(uno_axis.NumberFormat)).FormatString
            log.record(feature, str(applied).upper() == str(axis.number_format).upper())


def _set_series_data_labels(data_row: Any, index: int, *, enabled: bool, log: _ApplyLog) -> None:
    if not enabled:
        return
    with log.probe(f"series[{index}].data_labels.caption"):
        # ChartDataCaption flags: VALUE=1, PERCENT=2, TEXT=4 (category name).
        data_row.DataCaption = 4  # TEXT / category
    with log.probe(f"series[{index}].data_labels.category", record_success=False):
        label = getattr(data_row, "Label", None)
        if label is not None and hasattr(label, "ShowCategoryName"):
            label.ShowCategoryName = True
            if hasattr(data_row, "Label"):
                data_row.Label = label
            log.record(f"series[{index}].data_labels.category", True)


def _chart2_type(chart_doc: Any) -> Any:
    coordinate_systems = chart_doc.getFirstDiagram().getCoordinateSystems()
    if not coordinate_systems:
        raise ValueError("chart has no coordinate system")
    chart_types = coordinate_systems[0].getChartTypes()
    if not chart_types:
        raise ValueError("chart has no chart type")
    return chart_types[0]


def _new_labeled_sequence(
    chart_doc: Any,
    context: Any,
    range_representation: str,
    role: str,
) -> Any:
    provider = chart_doc.getDataProvider()
    values = provider.createDataSequenceByRangeRepresentation(range_representation)
    values.Role = role
    labeled = context.getServiceManager().createInstanceWithContext(
        "com.sun.star.chart2.data.LabeledDataSequence", context
    )
    labeled.setValues(values)
    return labeled


def _header_label_range(
    doc: Any,
    range_ref: str,
    *,
    default_sheet: str,
    expected_name: str | None,
) -> str | None:
    if not expected_name:
        return None
    target = _range_object(doc, range_ref, default_sheet=default_sheet)
    address = target.RangeAddress
    if address.StartColumn != address.EndColumn or address.StartRow <= 0:
        return None
    sheet = doc.Sheets.getByIndex(address.Sheet)
    header = sheet.getCellByPosition(address.StartColumn, address.StartRow - 1)
    if str(header.String).strip().casefold() != expected_name.strip().casefold():
        return None
    return str(header.AbsoluteName)


def _bind_xy_series(
    chart_doc: Any,
    spec: ChartSpec,
    *,
    doc: Any,
    context: Any,
    log: _ApplyLog,
) -> None:
    if spec.chart_type not in {"scatter", "bubble"}:
        return
    try:
        chart_type = _chart2_type(chart_doc)
        existing = list(chart_type.getDataSeries())
        bound = []
        for index, series_spec in enumerate(spec.series):
            if index < len(existing):
                data_series = existing[index]
            else:
                data_series = context.getServiceManager().createInstanceWithContext(
                    "com.sun.star.chart2.DataSeries", context
                )
            x_range = series_spec.x_values_range or spec.category_range
            role_ranges = [
                ("values-x", x_range),
                ("values-y", series_spec.values_range),
            ]
            if spec.chart_type == "bubble":
                role_ranges.append(("values-size", str(series_spec.bubble_size_range)))
            sequences = []
            for role, range_ref in role_ranges:
                sequence = _new_labeled_sequence(
                    chart_doc,
                    context,
                    _range_representation(doc, range_ref, default_sheet=spec.sheet),
                    role,
                )
                sequences.append(sequence)
                log.record(f"series[{index}].{role}", True)

            label_role = str(chart_type.getRoleOfSequenceForSeriesLabel())
            label_target = next(
                (pair for pair in sequences if str(pair.getValues().Role) == label_role),
                sequences[-1],
            )
            label_range = _header_label_range(
                doc,
                series_spec.values_range,
                default_sheet=spec.sheet,
                expected_name=series_spec.name,
            )
            if label_range is not None:
                label_target.setLabel(
                    chart_doc.getDataProvider().createDataSequenceByRangeRepresentation(label_range)
                )
                log.record(f"series[{index}].name", True)
            elif series_spec.name:
                log.record(
                    f"series[{index}].name",
                    False,
                    "literal series names require a matching header cell",
                )
            data_series.setData(tuple(sequences))
            bound.append(data_series)
        chart_type.setDataSeries(tuple(bound))
    except Exception as exc:
        log.record("xy_series_binding", False, type(exc).__name__)


def _apply_non_xy_series_names(
    chart_doc: Any,
    spec: ChartSpec,
    *,
    doc: Any,
    log: _ApplyLog,
) -> None:
    if spec.chart_type in {"scatter", "bubble"}:
        return
    try:
        chart_type = _chart2_type(chart_doc)
        label_role = str(chart_type.getRoleOfSequenceForSeriesLabel())
        for index, (data_series, series_spec) in enumerate(
            zip(chart_type.getDataSeries(), spec.series, strict=False)
        ):
            if not series_spec.name:
                continue
            label_range = _header_label_range(
                doc,
                series_spec.values_range,
                default_sheet=spec.sheet,
                expected_name=series_spec.name,
            )
            target = next(
                (
                    item
                    for item in data_series.getDataSequences()
                    if str(item.getValues().Role) == label_role
                ),
                None,
            )
            if label_range is not None and target is not None:
                target.setLabel(
                    chart_doc.getDataProvider().createDataSequenceByRangeRepresentation(label_range)
                )
                log.record(f"series[{index}].name", True)
            else:
                log.record(
                    f"series[{index}].name",
                    False,
                    "literal series names require a matching header cell",
                )
    except Exception as exc:
        log.record("series.names", False, type(exc).__name__)


def _apply_custom_point_label(
    point: Any,
    label_cell: Any,
    *,
    context: Any,
) -> None:
    field = context.getServiceManager().createInstanceWithContext(
        "com.sun.star.chart2.DataPointCustomLabelField", context
    )
    uno_module = __import__("uno")
    field.setFieldType(uno_module.Enum("com.sun.star.chart2.DataPointCustomLabelFieldType", "TEXT"))
    field.setString(str(label_cell.String))
    point.CustomLabelFields = (field,)
    # LibreOffice 7.0 has no ShowCustomLabel member. There, ShowCategoryName makes
    # CustomLabelFields render; newer releases expose the explicit custom-label flag.
    try:
        label = point.Label
        if hasattr(label, "ShowCustomLabel"):
            label.ShowCategoryName = False
            label.ShowCustomLabel = True
        else:
            label.ShowCategoryName = True
        point.Label = label
    except AttributeError:
        pass
    # DataLabelPlacement.RIGHT. Keep the numeric UNO constant local to avoid importing
    # generated LibreOffice Python modules outside a live UNO runtime.
    try:
        point.LabelPlacement = 8
    except AttributeError:
        pass


def _apply_point_styles_chart2(
    chart_doc: Any,
    spec: ChartSpec,
    log: _ApplyLog,
    *,
    doc: Any,
    context: Any,
) -> None:
    """Per-point FillColor / category labels via Chart2 when available."""
    wants_points = any(series.point_colors for series in spec.series)
    try:
        if not chart_doc.supportsService("com.sun.star.chart2.ChartDocument"):
            if wants_points:
                log.record("point_colors.chart2", False, "no chart2 service")
            return
        diagram2 = chart_doc.getFirstDiagram()
        coordinate_systems = diagram2.getCoordinateSystems()
        if not coordinate_systems:
            return
        chart_types = coordinate_systems[0].getChartTypes()
        if not chart_types:
            return
        data_series_list = chart_types[0].getDataSeries()
    except Exception as exc:
        if wants_points:
            log.record("point_colors.chart2", False, type(exc).__name__)
        return

    for series_index, series in enumerate(spec.series):
        if series_index >= len(data_series_list):
            break
        data_series = data_series_list[series_index]
        custom_labels = spec.data_labels and spec.chart_type in {"scatter", "bubble"}
        label_range = None
        if custom_labels:
            label_range = _range_object(doc, spec.category_range, default_sheet=spec.sheet)
            # LibreOffice 7.0 persists per-point CustomLabelFields but exposes label
            # visibility only at series level. Newer releases also accept the per-point
            # hint in _apply_custom_point_label.
            with log.probe(f"series[{series_index}].data_labels.visibility"):
                label = data_series.Label
                if hasattr(label, "ShowCustomLabel"):
                    label.ShowCategoryName = False
                    label.ShowCustomLabel = True
                else:
                    label.ShowCategoryName = True
                data_series.Label = label
        if spec.data_labels and not custom_labels:
            with log.probe(f"series[{series_index}].data_labels.chart2"):
                label = data_series.Label
                label.ShowCategoryName = True
                data_series.Label = label
        colors = series.point_colors or ()
        for point_index, color in enumerate(colors):
            feature = f"series[{series_index}].point_colors[{point_index}]"
            rgb = _parse_rgb(color)
            if rgb is None:
                log.record(feature, False, f"unparsable color {color!r}")
                continue
            with log.probe(feature, record_success=False):
                point = data_series.getDataPointByIndex(point_index)
                if point is None:
                    log.record(feature, False, "no such data point")
                    continue
                point.FillColor = rgb
                if hasattr(point, "Color"):
                    with log.probe(f"{feature}.line", record_success=False):
                        point.Color = rgb
                log.record(feature, True)
        if spec.data_labels:
            # Ensure labels visible even when only some points are recolored.
            label_count = 0
            labels_applied = 0
            if label_range is not None:
                address = label_range.RangeAddress
                label_count = (address.EndColumn - address.StartColumn + 1) * (
                    address.EndRow - address.StartRow + 1
                )
            for point_index in range(len(colors) or label_count or 32):
                try:
                    point = data_series.getDataPointByIndex(point_index)
                    if point is None:
                        break
                    if label_range is not None:
                        width = (
                            label_range.RangeAddress.EndColumn
                            - label_range.RangeAddress.StartColumn
                            + 1
                        )
                        label_cell = label_range.getCellByPosition(
                            point_index % width, point_index // width
                        )
                        _apply_custom_point_label(point, label_cell, context=context)
                        labels_applied += 1
                    else:
                        label = point.Label
                        label.ShowCategoryName = True
                        point.Label = label
                except Exception as exc:
                    log.record(
                        f"series[{series_index}].data_labels[{point_index}]",
                        False,
                        type(exc).__name__,
                    )
            if custom_labels:
                complete = label_count > 0 and labels_applied == label_count
                log.record(
                    f"series[{series_index}].data_labels.custom_text",
                    complete,
                    "" if complete else f"applied {labels_applied}/{label_count}",
                )


def _apply_point_styles_chart1(diagram: Any, spec: ChartSpec, log: _ApplyLog) -> None:
    """Fallback: old Chart1 getDataPointProperties(category, series)."""
    for series_index, series in enumerate(spec.series):
        colors = series.point_colors or ()
        for point_index, color in enumerate(colors):
            rgb = _parse_rgb(color)
            if rgb is None:
                continue
            with log.probe(
                f"series[{series_index}].point_colors[{point_index}].chart1",
                record_success=False,
            ):
                point = diagram.getDataPointProperties(point_index, series_index)
                point.FillColor = rgb


def _apply_series_styles(
    diagram: Any,
    spec: ChartSpec,
    log: _ApplyLog,
    *,
    chart_doc: Any | None = None,
    doc: Any | None = None,
    context: Any | None = None,
) -> None:
    for index, series in enumerate(spec.series):
        try:
            data_row = diagram.getDataRowProperties(index)
        except Exception as exc:
            log.record(f"series[{index}]", False, type(exc).__name__)
            continue
        rgb = _parse_rgb(series.color)
        if rgb is not None:
            applied_attrs = []
            for attr in ("FillColor", "Color", "LineColor"):
                try:
                    setattr(data_row, attr, rgb)
                except Exception:
                    continue
                applied_attrs.append(attr)
            log.record(
                f"series[{index}].color",
                bool(applied_attrs),
                "" if applied_attrs else "no color property accepted",
            )
        _set_series_data_labels(
            data_row,
            index,
            enabled=spec.data_labels and spec.chart_type not in {"scatter", "bubble"},
            log=log,
        )

    _apply_point_styles_chart1(diagram, spec, log)
    if chart_doc is not None and doc is not None and context is not None:
        _apply_point_styles_chart2(
            chart_doc,
            spec,
            log,
            doc=doc,
            context=context,
        )


def _sequence_range(sequence: Any) -> str | None:
    try:
        return str(sequence.getSourceRangeRepresentation())
    except Exception:
        return None


def _series_name(labeled_sequences: tuple[Any, ...]) -> str | None:
    for sequence in labeled_sequences:
        try:
            label = sequence.getLabel()
            data = label.getData() if label is not None else ()
            if data and str(data[0]):
                return str(data[0])
        except Exception:
            continue
    return None


def _color_hex(value: Any) -> str | None:
    try:
        return f"#{int(value) & 0xFFFFFF:06X}"
    except (TypeError, ValueError):
        return None


def _series_point_colors(series: Any, point_count: int) -> list[str | None] | None:
    """Read rendered colors for attributed points without claiming implicit defaults."""

    try:
        attributed = {int(index) for index in series.AttributedDataPoints}
    except Exception:
        return None
    if not attributed:
        return None
    colors: list[str | None] = []
    for index in range(point_count):
        if index not in attributed:
            colors.append(None)
            continue
        try:
            point = series.getDataPointByIndex(index)
            colors.append(_color_hex(point.FillColor))
        except Exception:
            colors.append(None)
    return colors if any(color is not None for color in colors) else None


def _inspect_series(chart_doc: Any) -> list[dict[str, object]]:
    try:
        chart_type = _chart2_type(chart_doc)
        data_series = chart_type.getDataSeries()
    except Exception:
        return []
    result: list[dict[str, object]] = []
    for series in data_series:
        labeled_sequences = tuple(series.getDataSequences())
        roles: dict[str, str] = {}
        point_count = 0
        for sequence in labeled_sequences:
            try:
                values = sequence.getValues()
                range_representation = _sequence_range(values)
                if range_representation:
                    roles[str(values.Role)] = range_representation
                if str(values.Role) == "values-y":
                    point_count = len(values.getData())
            except Exception:
                continue
        payload: dict[str, object] = {
            "name": _series_name(labeled_sequences),
            "values_range": roles.get("values-y"),
        }
        if "values-x" in roles:
            payload["x_values_range"] = roles["values-x"]
        if "values-size" in roles:
            payload["bubble_size_range"] = roles["values-size"]
        point_colors = _series_point_colors(series, point_count)
        if point_colors is not None:
            payload["point_colors"] = point_colors
        result.append(payload)
    return result


def _axis_category_range(chart_doc: Any) -> str | None:
    try:
        coordinate_system = chart_doc.getFirstDiagram().getCoordinateSystems()[0]
        categories = coordinate_system.getAxisByDimension(0, 0).ScaleData.Categories
        return _sequence_range(categories.getValues()) if categories is not None else None
    except Exception:
        return None


def _collapse_custom_label_ranges(chart_doc: Any) -> str | None:
    """Recover the contiguous category/data-label range used by XY point labels."""

    try:
        series = _chart2_type(chart_doc).getDataSeries()[0]
        cells = []
        for index in range(10_000):
            point = series.getDataPointByIndex(index)
            if point is None:
                break
            fields = tuple(getattr(point, "CustomLabelFields", ()) or ())
            ranges = [str(field.getCellRange()) for field in fields if field.getDataLabelsRange()]
            if not ranges:
                break
            cells.append(ranges[0])
        if not cells:
            return None
        if len(cells) == 1:
            return cells[0]
        first_sheet, first_cell = cells[0].rsplit(".", 1)
        last_sheet, last_cell = cells[-1].rsplit(".", 1)
        if first_sheet != last_sheet:
            return None
        return f"{first_sheet}.{first_cell}:{last_cell}"
    except Exception:
        return None


def _custom_point_labels(chart_doc: Any) -> list[str]:
    try:
        series = _chart2_type(chart_doc).getDataSeries()[0]
        labels = []
        for index in range(10_000):
            point = series.getDataPointByIndex(index)
            if point is None:
                break
            fields = tuple(getattr(point, "CustomLabelFields", ()) or ())
            if not fields:
                break
            labels.append("".join(str(field.getString()) for field in fields))
        return labels
    except Exception:
        return []


def _inspect_axis(diagram: Any, axis_name: str, chart_doc: Any) -> dict[str, object] | None:
    try:
        axis = getattr(diagram, axis_name)
    except Exception:
        return None
    payload: dict[str, object] = {}
    title = getattr(diagram, f"{axis_name}Title", None)
    if title is not None and str(getattr(title, "String", "")):
        payload["title"] = str(title.String)
    if getattr(axis, "AutoMin", True) is False:
        payload["min"] = float(axis.Min)
    if getattr(axis, "AutoMax", True) is False:
        payload["max"] = float(axis.Max)
    rotation = getattr(axis, "TextRotation", 0)
    if rotation:
        payload["label_rotation"] = float(rotation) / 100
    try:
        key = int(axis.NumberFormat)
        payload["number_format"] = str(chart_doc.getNumberFormats().getByKey(key).FormatString)
    except Exception:
        pass
    return payload or None


def _requested_chart_id(sheet: Any, chart_name: str) -> str:
    shape = _shape_for_chart_name(sheet, chart_name)
    requested = str(getattr(shape, "Name", "")) if shape is not None else ""
    return requested or str(chart_name)


def _chart_has_data_labels(chart_doc: Any) -> bool:
    def visible(label: Any) -> bool:
        return any(
            bool(getattr(label, name, False))
            for name in (
                "ShowCategoryName",
                "ShowCustomLabel",
                "ShowSeriesName",
                "ShowNumber",
                "ShowNumberInPercent",
            )
        )

    try:
        for series in _chart2_type(chart_doc).getDataSeries():
            if visible(series.Label):
                return True
            point = series.getDataPointByIndex(0)
            if point is not None and visible(point.Label):
                return True
        return False
    except Exception:
        return False


def _initial_chart_ranges(doc: Any, spec: ChartSpec) -> tuple[Any, ...]:
    if spec.chart_type in {"scatter", "bubble"}:
        ranges = []
        for series in spec.series:
            ranges.append(
                _range_address(
                    doc,
                    series.x_values_range or spec.category_range,
                    default_sheet=spec.sheet,
                )
            )
            ranges.append(_range_address(doc, series.values_range, default_sheet=spec.sheet))
            if spec.chart_type == "bubble" and series.bubble_size_range is not None:
                ranges.append(
                    _range_address(doc, series.bubble_size_range, default_sheet=spec.sheet)
                )
        return tuple(ranges)
    category = _range_address(doc, spec.category_range, default_sheet=spec.sheet)
    values = tuple(
        _range_address(doc, item.values_range, default_sheet=spec.sheet) for item in spec.series
    )
    return (category, *values)


def inspect_charts_from_document(doc: Any) -> list[dict[str, object]]:
    charts: list[dict[str, object]] = []
    sheets = doc.Sheets
    for name in sheets.ElementNames:
        sheet = sheets.getByName(name)
        chart_collection = sheet.getCharts()
        for chart_name in chart_collection.getElementNames():
            chart = chart_collection.getByName(chart_name)
            chart_doc = None
            try:
                chart_doc = chart.getEmbeddedObject()
            except Exception:
                chart_doc = None
            diagram = None
            try:
                if chart_doc is not None:
                    diagram = chart_doc.getDiagram()
            except Exception:
                diagram = None
            chart_type = _chart_type_from_document(chart_doc, diagram)
            category_range = (
                _collapse_custom_label_ranges(chart_doc)
                if chart_type in {"scatter", "bubble"}
                else _axis_category_range(chart_doc)
            )
            charts.append(
                {
                    "id": _requested_chart_id(sheet, str(chart_name)),
                    "storage_id": str(chart_name),
                    "sheet": str(name),
                    "title": _read_title(chart, chart_doc),
                    "chart_type": chart_type,
                    "has_legend": bool(
                        getattr(chart_doc, "HasLegend", getattr(chart, "HasLegend", None))
                    ),
                    "category_range": category_range,
                    "category_labels": _custom_point_labels(chart_doc),
                    "series": _inspect_series(chart_doc),
                    "data_labels": _chart_has_data_labels(chart_doc),
                    "x_axis": _inspect_axis(diagram, "XAxis", chart_doc),
                    "y_axis": _inspect_axis(diagram, "YAxis", chart_doc),
                    "compile_note": chart_compile_note(chart_type),
                }
            )
    return charts


def upsert_chart_on_sheet(
    sheet: Any,
    spec: ChartSpec,
    *,
    doc: Any,
    uno_module: Any,
    context: Any,
) -> dict[str, object]:
    note = chart_compile_note(spec.chart_type)
    if note == "unsupported":
        return {"ok": False, "chart_id": spec.id, "compile_note": note}
    if spec.chart_type not in NATIVE_UNO_CHART_TYPES:
        return {"ok": False, "chart_id": spec.id, "compile_note": note or "unsupported"}

    charts = sheet.getCharts()
    existing_names = list(charts.getElementNames())
    existing_id = chart_collection_name_for_id(sheet, spec.id)
    if existing_id is not None:
        charts.removeByName(existing_id)
        existing_names = list(charts.getElementNames())

    col, row = _anchor_position(spec.anchor)
    rect = uno_module.createUnoStruct("com.sun.star.awt.Rectangle")
    rect.X = col * 2000
    rect.Y = row * 600
    # ChartSpec sizes are HMM; keep Excel-like floors even if a caller bypasses from_dict.
    rect.Width = max(spec.width, MIN_CHART_WIDTH_HMM)
    rect.Height = max(spec.height, MIN_CHART_HEIGHT_HMM)

    cell_range_addresses = _initial_chart_ranges(doc, spec)

    charts.addNewByName(
        spec.id,
        rect,
        cell_range_addresses,
        False,
        True,
    )
    created_names = list(charts.getElementNames())
    created_id = (
        spec.id
        if spec.id in created_names
        else next(
            (name for name in created_names if name not in existing_names),
            created_names[-1] if created_names else spec.id,
        )
    )
    log = _ApplyLog()
    log.record("id", _set_requested_chart_id(sheet, created_id, spec.id), "shape unavailable")

    chart = charts.getByName(created_id)
    chart_doc = chart.getEmbeddedObject() if hasattr(chart, "getEmbeddedObject") else chart
    with log.probe("chart_type"):
        _apply_diagram_type(chart_doc, spec.chart_type, log)
    _bind_xy_series(chart_doc, spec, doc=doc, context=context, log=log)
    _apply_non_xy_series_names(chart_doc, spec, doc=doc, log=log)

    if spec.title:
        with log.probe("title", record_success=False):
            if hasattr(chart_doc, "HasMainTitle"):
                chart_doc.HasMainTitle = True
            title = getattr(chart_doc, "Title", None)
            if title is not None and hasattr(title, "String"):
                title.String = spec.title
            log.record("title", str(getattr(title, "String", "")) == str(spec.title))
    with log.probe("legend"):
        if hasattr(chart_doc, "HasLegend"):
            chart_doc.HasLegend = spec.legend
        elif hasattr(chart, "HasLegend"):
            chart.HasLegend = spec.legend

    try:
        diagram = chart_doc.getDiagram()
    except Exception as exc:
        log.record("diagram", False, type(exc).__name__)
        diagram = None
    if diagram is not None:
        _apply_axis(
            diagram,
            "XAxis",
            spec.category_axis,
            spec.primary_axis_title,
            log,
            chart_doc=chart_doc,
        )
        _apply_axis(
            diagram,
            "YAxis",
            spec.value_axis,
            None,
            log,
            chart_doc=chart_doc,
        )
        if spec.secondary_axis_title:
            applied = False
            with log.probe("secondary_axis.title", record_success=False):
                if hasattr(diagram, "HasSecondaryYAxis"):
                    diagram.HasSecondaryYAxis = True
                if hasattr(diagram, "HasSecondaryYAxisTitle"):
                    diagram.HasSecondaryYAxisTitle = True
                title_shape = getattr(diagram, "SecondYAxisTitle", None)
                if title_shape is not None and hasattr(title_shape, "String"):
                    title_shape.String = str(spec.secondary_axis_title)
                    applied = True
            log.record("secondary_axis.title", applied)
            if not applied:
                _apply_axis(
                    diagram,
                    "YAxis",
                    ChartAxisSpec(title=spec.secondary_axis_title),
                    spec.secondary_axis_title,
                    log,
                    chart_doc=chart_doc,
                )
        _apply_series_styles(
            diagram,
            spec,
            log,
            chart_doc=chart_doc,
            doc=doc,
            context=context,
        )

    return {
        "ok": True,
        "chart_id": spec.id,
        "requested_id": spec.id,
        "storage_id": created_id,
        "compile_note": note,
        "applied": log.applied,
        "dropped": log.dropped,
    }


def export_charts_to_png(
    doc: Any,
    *,
    output_dir: str,
    file_prefix: str,
    uno_module: Any,
    context: Any,
) -> list[str]:
    """Export each Calc chart shape via native GraphicExportFilter to PNG.

    LibreOffice supports this natively: setSourceDocument(draw_shape) + MediaType image/png.
    """
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    service_manager = context.getServiceManager()
    exporter = service_manager.createInstanceWithContext(
        "com.sun.star.drawing.GraphicExportFilter",
        context,
    )

    sheets = doc.Sheets
    chart_index = 0
    for sheet_name in sheets.ElementNames:
        sheet = sheets.getByName(sheet_name)
        draw_page = sheet.getDrawPage()
        for shape_index in range(draw_page.getCount()):
            shape = draw_page.getByIndex(shape_index)
            # Charts appear as OLE2Shape / chart shapes on the draw page.
            shape_type = ""
            try:
                shape_type = str(shape.ShapeType)
            except Exception:
                pass
            is_chart = "Chart" in shape_type or "OLE2Shape" in shape_type
            if not is_chart:
                try:
                    # Fallback: shapes that expose an embedded chart document.
                    embedded = shape.getEmbeddedObject()
                    if embedded is None or not embedded.supportsService(
                        "com.sun.star.chart.ChartDocument"
                    ):
                        continue
                    is_chart = True
                except Exception:
                    continue
            if not is_chart:
                continue

            chart_index += 1
            target = out / f"{file_prefix}_chart_{chart_index}.png"
            url = uno_module.systemPathToFileUrl(str(target.resolve()))
            props = (
                uno_module.createUnoStruct("com.sun.star.beans.PropertyValue"),
                uno_module.createUnoStruct("com.sun.star.beans.PropertyValue"),
            )
            props[0].Name = "URL"
            props[0].Value = url
            props[1].Name = "MediaType"
            props[1].Value = "image/png"
            exporter.setSourceDocument(shape)
            if not exporter.filter(props):
                raise RuntimeError(f"GraphicExportFilter failed for chart {chart_index}")
            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError(f"PNG not written for chart {chart_index}: {target}")
            exported.append(str(target))

    return exported
