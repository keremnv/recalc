"""Gold-blind blank-candidate signals for offline ranking experiments.

Candidate generation and scoring use only the input workbook and the task instruction.
Golden data is applied later by the characterisation CLI, never here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from librecalc_mcp.domain.formulas import formula_a1_references
from librecalc_mcp.domain.grid import column_label, column_number

PEER_DISTANCE = 8
RANGE_MAX_CELLS = 4096
CELL = re.compile(r"^\$?([A-Z]{1,3})\$?([0-9]{1,7})$")
_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-"})


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _is_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("=")


def _is_label(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith("=")


def _cells_in(start: str, end: str | None) -> list[str] | None:
    first, last = CELL.match(start.upper()), CELL.match((end or start).upper())
    if not first or not last:
        return None
    column_0, row_0 = column_number(first.group(1)), int(first.group(2))
    column_1, row_1 = column_number(last.group(1)), int(last.group(2))
    column_0, column_1 = min(column_0, column_1), max(column_0, column_1)
    row_0, row_1 = min(row_0, row_1), max(row_0, row_1)
    if (column_1 - column_0 + 1) * (row_1 - row_0 + 1) > RANGE_MAX_CELLS:
        return None
    return [
        f"{column_label(column)}{row}"
        for column in range(column_0, column_1 + 1)
        for row in range(row_0, row_1 + 1)
    ]


def demanded_addresses(workbook: Any) -> set[tuple[str, str]]:
    """Every bounded (sheet, address) named by some formula in the workbook."""

    demanded: set[tuple[str, str]] = set()
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value
                if not _is_formula(value):
                    continue
                for ref_sheet, start, end in formula_a1_references(value):
                    addresses = _cells_in(start, end)
                    if addresses is None:
                        continue
                    for address in addresses:
                        demanded.add((ref_sheet or sheet.title, address))
    return demanded


def instruction_sheet_names(instruction: str, sheet_names: list[str]) -> set[str]:
    """Sheets whose names appear in the instruction, longest match first.

    This is a gold-blind scope, not a target selector. Tiny names (<3 chars) are
    skipped because they collide with ordinary English.
    """

    text = instruction.translate(_DASHES).lower()
    matched: set[str] = set()
    for name in sorted(sheet_names, key=len, reverse=True):
        needle = name.translate(_DASHES).lower()
        if len(needle) < 3:
            continue
        if needle in text:
            matched.add(name)
    return matched


def adjacent_label(sheet: Any, column: int, row: int) -> str | None:
    """Nearest header-like string: above, left, or above-left."""

    for offset_column, offset_row in ((0, -1), (-1, 0), (-1, -1)):
        neighbour_column = column + offset_column
        neighbour_row = row + offset_row
        if neighbour_column < 1 or neighbour_row < 1:
            continue
        value = sheet.cell(neighbour_row, neighbour_column).value
        if _is_label(value):
            return str(value).strip()
    return None


@dataclass(frozen=True)
class BlankCandidate:
    sheet: str
    address: str
    row_peer: bool
    col_peer: bool
    referenced: bool
    label: str | None
    named_sheet: bool

    @property
    def block_peer(self) -> bool:
        return self.row_peer and self.col_peer

    @property
    def any_peer(self) -> bool:
        return self.row_peer or self.col_peer

    def score(self) -> int:
        """Additive rank: peers, demand, label, instruction sheet. Not a selector."""

        points = 0
        if self.block_peer:
            points += 4
        elif self.any_peer:
            points += 2
        if self.referenced:
            points += 3
        if self.label:
            points += 2
        if self.named_sheet:
            points += 2
        return points


def _peer_flags(
    formulas_by_row: dict[int, set[int]],
    formulas_by_column: dict[int, set[int]],
    column: int,
    row: int,
) -> tuple[bool, bool]:
    row_peer = any(
        other != column and abs(other - column) <= PEER_DISTANCE
        for other in formulas_by_row.get(row, ())
    )
    col_peer = any(
        other != row and abs(other - row) <= PEER_DISTANCE
        for other in formulas_by_column.get(column, ())
    )
    return row_peer, col_peer


def enumerate_blank_candidates(
    workbook: Any,
    *,
    instruction: str,
    demanded: set[tuple[str, str]] | None = None,
) -> list[BlankCandidate]:
    """Every blank used-range cell, with gold-blind flags."""

    demanded = demanded if demanded is not None else demanded_addresses(workbook)
    named = instruction_sheet_names(instruction, [sheet.title for sheet in workbook.worksheets])
    candidates: list[BlankCandidate] = []
    for sheet in workbook.worksheets:
        used = sheet.calculate_dimension()
        if not used:
            continue
        formulas_by_row: dict[int, set[int]] = {}
        formulas_by_column: dict[int, set[int]] = {}
        blanks: list[tuple[int, int]] = []
        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value
                if _is_formula(value):
                    formulas_by_row.setdefault(cell.row, set()).add(cell.column)
                    formulas_by_column.setdefault(cell.column, set()).add(cell.row)
                elif _is_blank(value):
                    blanks.append((cell.column, cell.row))
        named_sheet = sheet.title in named
        for column, row in blanks:
            row_peer, col_peer = _peer_flags(formulas_by_row, formulas_by_column, column, row)
            address = f"{column_label(column)}{row}"
            candidates.append(
                BlankCandidate(
                    sheet=sheet.title,
                    address=address,
                    row_peer=row_peer,
                    col_peer=col_peer,
                    referenced=(sheet.title, address) in demanded,
                    label=adjacent_label(sheet, column, row),
                    named_sheet=named_sheet,
                )
            )
    return candidates


def shortlist(candidates: list[BlankCandidate], arm: str) -> list[BlankCandidate]:
    """Named arms used by the characterisation CLI. None of these is shipped."""

    if arm == "block-peer":
        return [item for item in candidates if item.block_peer]
    if arm == "block-peer+label":
        return [item for item in candidates if item.block_peer and item.label]
    if arm == "named-sheet":
        return [item for item in candidates if item.named_sheet]
    if arm == "named-block-label":
        return [
            item for item in candidates if item.named_sheet and item.block_peer and item.label
        ]
    if arm == "named-any-peer":
        return [item for item in candidates if item.named_sheet and item.any_peer]
    if arm == "referenced":
        return [item for item in candidates if item.referenced]
    if arm == "referenced+peer":
        return [item for item in candidates if item.referenced and item.any_peer]
    if arm == "rank-top-20":
        return sorted(candidates, key=lambda item: (-item.score(), item.sheet, item.address))[:20]
    if arm == "named-rank-top-20":
        scoped = [item for item in candidates if item.named_sheet]
        return sorted(scoped, key=lambda item: (-item.score(), item.sheet, item.address))[:20]
    raise ValueError(f"unknown ranking arm: {arm}")


ARMS = (
    "block-peer",
    "block-peer+label",
    "named-sheet",
    "named-block-label",
    "named-any-peer",
    "referenced",
    "referenced+peer",
    "rank-top-20",
    "named-rank-top-20",
)
