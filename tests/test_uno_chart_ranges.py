from librecalc_mcp.backend.uno_charts import _chart_type_from_diagram, _split_range_reference


def test_split_range_reference_supports_sheet_qualified_ranges() -> None:
    assert _split_range_reference("Data!A6:A46", "Count") == ("Data", "A6:A46")
    assert _split_range_reference("Data.A6:A46", "Count") == ("Data", "A6:A46")
    assert _split_range_reference("A6:A46", "Count") == ("Count", "A6:A46")


class _Diagram:
    def __init__(self, name: str, vertical: bool = True) -> None:
        self.ImplementationName = name
        self.Vertical = vertical


def test_chart_type_from_diagram_mapping() -> None:
    assert _chart_type_from_diagram(_Diagram("com.sun.star.comp.chart.LineDiagram")) == "line"
    assert _chart_type_from_diagram(_Diagram("com.sun.star.comp.chart.BarDiagram", True)) == "column"
    assert _chart_type_from_diagram(_Diagram("com.sun.star.comp.chart.BarDiagram", False)) == "bar"
    assert _chart_type_from_diagram(_Diagram("com.sun.star.comp.chart.DonutDiagram")) == "doughnut"
