"""The chart adapter must report what LibreOffice refused, not swallow it.

A silently dropped field makes an agent that under-specified a chart look identical
to a world that discarded what the agent did specify. Those have opposite fixes, so
the distinction has to survive into the tool result.
"""

from __future__ import annotations

from librecalc_mcp.backend.uno_charts import _apply_axis, _ApplyLog
from librecalc_mcp.domain.charts import ChartAxisSpec


class _TitleShape:
    """Accepts a title and keeps it, like a diagram that renders axis titles."""

    def __init__(self) -> None:
        self.String = ""


class _RejectingTitleShape:
    """Accepts the assignment but discards it, like several LO diagram types."""

    def __init__(self) -> None:
        self._value = ""

    @property
    def String(self) -> str:
        return self._value

    @String.setter
    def String(self, value: str) -> None:
        self._value = ""


class _Axis:
    """Scale properties live on the axis, separately from the title shape."""

    def __init__(self) -> None:
        self.AutoMin = True
        self.Min = 0.0


class _Diagram:
    def __init__(self, title_shape: object) -> None:
        self.HasXAxisTitle = False
        self.XAxisTitle = title_shape
        self.XAxis = _Axis()


def test_accepted_axis_title_is_reported_as_applied() -> None:
    log = _ApplyLog()
    diagram = _Diagram(_TitleShape())

    _apply_axis(diagram, "XAxis", ChartAxisSpec(title="Quarter"), None, log)

    assert "xaxis.title" in log.applied
    assert not log.dropped
    assert diagram.HasXAxisTitle is True


def test_missing_axis_object_is_reported_rather_than_ignored() -> None:
    log = _ApplyLog()
    diagram = _Diagram(_TitleShape())
    del diagram.XAxis

    _apply_axis(diagram, "XAxis", ChartAxisSpec(title="Quarter", min=0), None, log)

    assert "xaxis.title" in log.applied
    assert any(entry.startswith("xaxis.scale") for entry in log.dropped)


def test_silently_discarded_axis_title_is_reported_as_dropped() -> None:
    log = _ApplyLog()
    diagram = _Diagram(_RejectingTitleShape())

    _apply_axis(diagram, "XAxis", ChartAxisSpec(title="Quarter"), None, log)

    assert "xaxis.title" not in log.applied
    assert any(entry.startswith("xaxis.title") for entry in log.dropped)


def test_probe_records_the_exception_type_it_absorbed() -> None:
    log = _ApplyLog()

    with log.probe("series[0].color"):
        raise AttributeError("no such property")

    assert log.applied == []
    assert log.dropped == ["series[0].color (AttributeError)"]
