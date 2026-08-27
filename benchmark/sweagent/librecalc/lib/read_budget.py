"""Post-inspect read budget: a measuring instrument, not a world primitive.

Caps a Debugging run at one successful read batch after calc_inspect so that a
model which spirals on inspection is forced to commit. It exists to isolate
confirm-then-write behaviour in an experiment, and deliberately does not live in
the product: nothing outside a benchmark run should have its reads rationed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def read_budget_enabled() -> bool:
    return os.environ.get("LIBRECALC_READ_BUDGET_ENABLED") == "1"


def read_budget_path() -> Path | None:
    raw = os.environ.get("LIBRECALC_READ_BUDGET_PATH")
    if not raw:
        return None
    return Path(raw)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"remaining": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")


def reset_read_budget() -> None:
    if not read_budget_enabled():
        return
    path = read_budget_path()
    if path is None:
        return
    _save_state(path, {"remaining": 1})


def begin_inspection() -> str | None:
    """Start one inspect/read pass, respecting an optional run-scoped pass limit."""

    if not read_budget_enabled():
        return None
    path = read_budget_path()
    if path is None:
        return None
    state = _load_state(path)
    used = int(state.get("inspections", 0))
    raw_limit = os.environ.get("LIBRECALC_INSPECTION_LIMIT")
    limit = int(raw_limit) if raw_limit else 0
    if limit and used >= limit:
        return (
            f"Inspection budget exhausted after {limit} pass(es). "
            "Write or submit; do not begin another inspection loop."
        )
    _save_state(path, {"remaining": 1, "inspections": used + 1})
    return None


def read_budget_error() -> str | None:
    if not read_budget_enabled():
        return None
    path = read_budget_path()
    if path is None:
        return None
    remaining = int(_load_state(path).get("remaining", 0))
    if remaining <= 0:
        return (
            "Read budget exhausted after inspect. Use calc_fill_formulas or calc_program "
            "to write; further calc_read / calc_read_ranges calls are blocked for this run."
        )
    return None


def consume_read_budget(*, successful: bool) -> None:
    if not read_budget_enabled() or not successful:
        return
    path = read_budget_path()
    if path is None:
        return
    state = _load_state(path)
    state["remaining"] = max(0, int(state.get("remaining", 0)) - 1)
    _save_state(path, state)
