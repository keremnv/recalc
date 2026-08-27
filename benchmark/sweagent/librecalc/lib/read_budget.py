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
    _save_state(
        path,
        {
            "remaining": 1,
            "inspections": used + 1,
            "write_now": bool(state.get("write_now")),
        },
    )
    return None


def read_budget_error() -> str | None:
    if not read_budget_enabled():
        return None
    path = read_budget_path()
    if path is None:
        return None
    state = _load_state(path)
    remaining = int(state.get("remaining", 0))
    write_now = bool(state.get("write_now"))
    if remaining <= 0 or write_now:
        return (
            "Read budget exhausted after inspect. Use calc_fill_formulas or calc_program "
            "to write from inspect; further calc_read / calc_read_ranges calls are blocked "
            "for this run. Do not retry dumps or bash."
        )
    return None


def consume_read_budget(*, successful: bool = True) -> None:
    """Spend the post-inspect confirmation slot only when a neighborhood read succeeds.

    Oversized dumps used to consume the slot and then format-exit (Debugging 05_03
    low-4). A failed dump now keeps remaining=1 but sets write_now so the next read
    is blocked and the model must write from inspect.
    """

    if not read_budget_enabled():
        return
    path = read_budget_path()
    if path is None:
        return
    state = _load_state(path)
    if successful:
        state["remaining"] = max(0, int(state.get("remaining", 0)) - 1)
        state["write_now"] = False
    else:
        state["write_now"] = True
    _save_state(path, state)
