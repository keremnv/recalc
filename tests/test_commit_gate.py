"""The commit gate: one pass, fail-open, and it must never see openpyxl representations."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from librecalc_mcp.domain import commit_checks


def _gate_module():
    path = Path(__file__).parents[1] / "benchmark/sweagent/librecalc/lib/commit_gate.py"
    spec = importlib.util.spec_from_file_location("librecalc_commit_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["librecalc_commit_gate"] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class _Sheet:
    name: str
    used_range: str | None


class _Workbook:
    def __init__(self, sheets):
        self.sheets = sheets


class _FakeBackend:
    """Both workbooks are read through one engine, which is the point of the design."""

    def __init__(self, by_path):
        self._by_path = by_path

    def inspect_workbook(self, path=None):
        return _Workbook([_Sheet("S", "A1:C3")])

    def read_ranges(self, ranges, path=None, include_errors=True):
        return [self._by_path[path] for _ in ranges]


def _result(values, formulas, errors):
    return {"values": values, "formulas": formulas, "errors": errors}


def test_gate_reports_a_new_error_then_lets_the_next_submit_through(tmp_path, monkeypatch) -> None:
    gate = _gate_module()
    state = tmp_path / "gate.json"
    monkeypatch.setenv("LIBRECALC_COMMIT_GATE_ENABLED", "1")
    monkeypatch.setenv("LIBRECALC_COMMIT_GATE_PATH", str(state))
    monkeypatch.setattr(gate, "discover_paths", lambda: ("in.xlsx", "out.xlsx"))

    backend = _FakeBackend(
        {
            "in.xlsx": _result([[1, None, None]], [["=A1", "", ""]], [[None, None, None]]),
            "out.xlsx": _result(
                [["#VALUE!", None, None]], [["=A1+\"x\"", "", ""]], [["#VALUE!", None, None]]
            ),
        }
    )

    report = gate.evaluate(backend, commit_checks)

    assert report["ok"] is False
    assert report["checks"]["new_formula_error"]["count"] == 1
    assert gate.already_reported() is False
    gate.mark_reported()
    assert gate.already_reported() is True


def test_gate_passes_when_there_is_nothing_to_say(tmp_path, monkeypatch) -> None:
    gate = _gate_module()
    monkeypatch.setenv("LIBRECALC_COMMIT_GATE_ENABLED", "1")
    monkeypatch.setenv("LIBRECALC_COMMIT_GATE_PATH", str(tmp_path / "gate.json"))
    monkeypatch.setattr(gate, "discover_paths", lambda: ("in.xlsx", "out.xlsx"))
    clean = _result([[1, None, None]], [["=A1", "", ""]], [[None, None, None]])

    assert gate.evaluate(_FakeBackend({"in.xlsx": clean, "out.xlsx": clean}), commit_checks)["ok"]


def test_gate_passes_when_no_workbook_was_produced(monkeypatch) -> None:
    """Blocking a submission that has no output helps nobody -- it just loses the trajectory."""
    gate = _gate_module()
    monkeypatch.setenv("LIBRECALC_COMMIT_GATE_ENABLED", "1")
    monkeypatch.setattr(gate, "discover_paths", lambda: ("in.xlsx", None))

    result = gate.evaluate(_FakeBackend({}), commit_checks)

    assert result["ok"] is True
    assert "no output" in result["reason"]


def test_gate_is_off_unless_explicitly_enabled(monkeypatch) -> None:
    gate = _gate_module()
    monkeypatch.delenv("LIBRECALC_COMMIT_GATE_ENABLED", raising=False)
    assert gate.commit_gate_enabled() is False
    monkeypatch.setenv("LIBRECALC_COMMIT_GATE_ENABLED", "1")
    assert gate.commit_gate_enabled() is True
