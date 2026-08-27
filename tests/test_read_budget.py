from __future__ import annotations

import json
from pathlib import Path

import pytest
from read_budget import (
    begin_inspection,
    consume_read_budget,
    read_budget_error,
    reset_read_budget,
)


@pytest.fixture(autouse=True)
def _clear_read_budget_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state_path = tmp_path / "read_budget.json"
    monkeypatch.setenv("LIBRECALC_READ_BUDGET_ENABLED", "1")
    monkeypatch.setenv("LIBRECALC_READ_BUDGET_PATH", str(state_path))
    return state_path


def test_read_budget_allows_one_batch_after_inspect() -> None:
    reset_read_budget()
    assert read_budget_error() is None
    consume_read_budget(successful=True)
    assert read_budget_error() is not None


def test_read_budget_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIBRECALC_READ_BUDGET_ENABLED", raising=False)
    reset_read_budget()
    consume_read_budget(successful=True)
    assert read_budget_error() is None


def test_read_budget_reset_on_inspect_clears_exhaustion() -> None:
    reset_read_budget()
    consume_read_budget(successful=True)
    assert read_budget_error() is not None
    reset_read_budget()
    assert read_budget_error() is None


def test_read_budget_state_file_tracks_remaining(_clear_read_budget_env: Path) -> None:
    state_path = _clear_read_budget_env
    reset_read_budget()
    consume_read_budget(successful=True)
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["remaining"] == 0


def test_inspection_budget_allows_exact_configured_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIBRECALC_INSPECTION_LIMIT", "2")

    assert begin_inspection() is None
    consume_read_budget(successful=True)
    assert begin_inspection() is None
    assert begin_inspection() == (
        "Inspection budget exhausted after 2 pass(es). "
        "Write or submit; do not begin another inspection loop."
    )
