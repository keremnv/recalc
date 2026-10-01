"""Deterministic six-task forced-exposure diagnostic slice."""
from __future__ import annotations

from formula_index_pilot import ZERO_RECOVERABLE, even_space

AVOID = {"08_03"}
FROZEN_NEGATIVES = ["03_02", "09_05", "19_04"]
FROZEN_SAME_ROW = ["01_01", "11_04", "20_05"]
FROZEN_SAME_COL = ["11_02"]
FROZEN_CROSS = ["11_01", "20_01"]


def select_ambient_six(task_rows: list[dict]) -> list[dict]:
    """Pick 6 Financial_Model IDs from the frozen 20-task strata.

    Never consults historical scores. Skips 08_03 (opaque/dynamic-ref prevalence).
    """
    by_id = {row["id"]: row for row in task_rows}
    selected: list[dict] = []
    taken: set[str] = set()

    def add(task_id: str, role: str, reason: str) -> None:
        if task_id in taken or task_id not in by_id:
            return
        nearest = by_id[task_id].get("nearest") or {}
        selected.append(
            {
                "category": "Financial_Model",
                "id": task_id,
                "role": role,
                "reason": reason,
                "opaque_cells": by_id[task_id].get("opaque", 0),
                "formulas": by_id[task_id].get("formulas", 0),
                "nearest": dict(nearest),
            }
        )
        taken.add(task_id)

    negatives = [task_id for task_id in FROZEN_NEGATIVES if task_id in by_id]
    for task_id in even_space(negatives, 1):
        add(
            task_id,
            "negative_control",
            "zero-recoverable negative control; even-space of the frozen Gate-2 zeros",
        )

    row_ids = [task_id for task_id in FROZEN_SAME_ROW if task_id not in AVOID]
    for task_id in even_space(row_ids, 2):
        add(
            task_id,
            "same_row_nonadjacent",
            "recoverable same-row non-adjacent; even-space of the frozen same-row stratum",
        )

    col_tagged = [task_id for task_id in FROZEN_SAME_COL if task_id not in AVOID]
    for task_id in col_tagged:
        add(
            task_id,
            "same_column_nonadjacent",
            "recoverable same-column non-adjacent; the frozen same-column tagged task",
        )
    remaining_col = sorted(
        row["id"]
        for row in task_rows
        if row["id"] not in taken
        and row["id"] not in AVOID
        and row["id"] not in ZERO_RECOVERABLE
        and (row.get("nearest") or {}).get("same_column_nonadjacent", 0) > 0
    )
    for task_id in even_space(remaining_col, 2 - sum(1 for item in selected if item["role"] == "same_column_nonadjacent")):
        add(
            task_id,
            "same_column_nonadjacent",
            "recoverable same-column non-adjacent; even-space of remaining frozen tasks with that nearest class",
        )

    cross_ids = [task_id for task_id in FROZEN_CROSS if task_id not in AVOID]
    for task_id in even_space(cross_ids, 1):
        add(
            task_id,
            "cross_sheet",
            "recoverable cross-sheet; even-space of the frozen cross-sheet stratum",
        )

    return selected
