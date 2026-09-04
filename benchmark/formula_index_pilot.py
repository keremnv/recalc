"""Deterministic Financial_Model formula-index pilot slice construction."""
from __future__ import annotations

from typing import Iterable

ZERO_RECOVERABLE = [
    "03_02",
    "03_05",
    "05_02",
    "06_03",
    "09_04",
    "09_05",
    "16_03",
    "17_03",
    "17_04",
    "17_05",
    "19_04",
]


def even_space(items: Iterable[str], k: int) -> list[str]:
    items = list(items)
    if k <= 0:
        return []
    if k >= len(items):
        return items
    if k == 1:
        return [items[0]]
    return [items[round(i * (len(items) - 1) / (k - 1))] for i in range(k)]


def select_pilot(task_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (negative_controls, mechanism_positive) with reasons.

    ``task_rows`` items need: id, families, formulas, recoverable_blanks, nearest.
    Selection never consults historical scores.
    """
    by_id = {row["id"]: row for row in task_rows}
    zero = [task_id for task_id in ZERO_RECOVERABLE if task_id in by_id]
    negatives = [
        {
            "id": task_id,
            "reason": (
                "zero-recoverable negative control; even-space of the 11 "
                "Financial_Model tasks with no input homologue for a golden blank fill"
            ),
        }
        for task_id in even_space(zero, 3)
    ]

    positive_ids = sorted(
        row["id"] for row in task_rows if row.get("recoverable_blanks", 0) > 0
    )
    small = sorted(positive_ids, key=lambda i: (by_id[i]["families"], i))[:10]
    large = sorted(positive_ids, key=lambda i: (-by_id[i]["formulas"], i))[:10]
    row = sorted(
        i for i in positive_ids if by_id[i]["nearest"].get("same_row_nonadjacent", 0) > 0
    )
    col = sorted(
        i
        for i in positive_ids
        if by_id[i]["nearest"].get("same_column_nonadjacent", 0) > 0
    )
    cross = sorted(
        i for i in positive_ids if by_id[i]["nearest"].get("cross_sheet", 0) > 0
    )

    selected: list[str] = []
    reasons: dict[str, str] = {}

    def add(ids: list[str], reason: str) -> None:
        for task_id in ids:
            if task_id not in reasons:
                selected.append(task_id)
                reasons[task_id] = reason

    add(even_space(small, 2), "small-workbook even-space of 10 fewest-family mechanism-positive tasks")
    add(even_space(large, 2), "large-workbook even-space of 10 most-formula mechanism-positive tasks")
    add(
        even_space(row, 3),
        "same-row non-adjacent even-space of mechanism-positive tasks with that nearest class",
    )
    add(
        even_space(col, 3),
        "same-column non-adjacent even-space of mechanism-positive tasks with that nearest class",
    )
    add(
        even_space(cross, 3),
        "cross-sheet even-space of mechanism-positive tasks with that nearest class",
    )
    if len(selected) < 17:
        rest = [task_id for task_id in positive_ids if task_id not in selected]
        add(
            even_space(rest, 17 - len(selected)),
            "fill even-space of remaining mechanism-positive tasks to 17",
        )

    positives = [{"id": task_id, "reason": reasons[task_id]} for task_id in selected[:17]]
    return negatives, positives
