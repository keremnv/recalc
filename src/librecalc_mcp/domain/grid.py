"""A1 addressing and cell-kind primitives shared by the observation and diff models.

Pure functions over values and formulas. No backend, no UNO, no I/O.
"""

from __future__ import annotations

import re
from typing import Any

A1_RANGE = re.compile(r"^([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?$")

SPREADSHEET_ERROR_TOKEN = re.compile(
    r"#(?:DIV/0!|N/A|NAME\?|NULL!|NUM!|REF!|VALUE!)|Err:\d+",
    re.IGNORECASE,
)


def a1_cell_count(cell_range: str) -> int:
    match = A1_RANGE.fullmatch(cell_range.upper())
    if match is None:
        raise ValueError(f"invalid A1 range: {cell_range}")
    start_column, start_row, end_column, end_row = match.groups()
    end_column = end_column or start_column
    end_row = end_row or start_row
    rows = int(end_row) - int(start_row) + 1
    columns = column_number(end_column) - column_number(start_column) + 1
    if rows < 1 or columns < 1:
        raise ValueError(f"A1 range is inverted: {cell_range}")
    return rows * columns


def validate_matrix_shape(cell_range: str, matrix: list[list[Any]]) -> None:
    """Require a rectangular matrix that exactly covers an A1 range."""
    match = A1_RANGE.fullmatch(cell_range.upper())
    if match is None:
        raise ValueError(f"invalid A1 range: {cell_range}")
    start_column, start_row, end_column, end_row = match.groups()
    expected_rows = int(end_row or start_row) - int(start_row) + 1
    expected_columns = column_number(end_column or start_column) - column_number(start_column) + 1
    if expected_rows < 1 or expected_columns < 1:
        raise ValueError(f"A1 range is inverted: {cell_range}")
    row_widths = [len(row) for row in matrix]
    if len(matrix) != expected_rows or any(width != expected_columns for width in row_widths):
        received = f"{len(matrix)} row(s) with widths {row_widths}"
        raise ValueError(
            f"range {cell_range.upper()} requires a {expected_rows}x{expected_columns} "
            f"values matrix; received {received}"
        )


def spreadsheet_error_kind(formula: Any, error: Any) -> str | None:
    if error:
        return str(error)
    if not isinstance(formula, str):
        return None
    match = SPREADSHEET_ERROR_TOKEN.search(formula)
    if match is None:
        return None
    token = match.group(0)
    return token.upper() if token.startswith("#") else token


def a1_sort_key(address: str) -> tuple[int, int]:
    match = A1_RANGE.fullmatch(address.upper())
    if match is None:
        return (10**9, 10**9)
    column, row, _, _ = match.groups()
    return (int(row), column_number(column))


def column_number(label: str) -> int:
    value = 0
    for character in label:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def column_label(number: int) -> str:
    characters = []
    while number:
        number, remainder = divmod(number - 1, 26)
        characters.append(chr(ord("A") + remainder))
    return "".join(reversed(characters))


def cell_kind(value: Any, formula: Any) -> str:
    if isinstance(formula, str) and formula.startswith("="):
        return "formula"
    if value is None or value == "":
        return "blank"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "text"


def spans(kinds: list[str]) -> tuple[tuple[int, int, str], ...]:
    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    active_kind: str | None = None
    for index, kind in enumerate([*kinds, "blank"]):
        if kind == active_kind and kind != "blank":
            continue
        if start is not None and active_kind is not None:
            spans.append((start, index - 1, active_kind))
        if kind == "blank":
            start = None
            active_kind = None
        else:
            start = index
            active_kind = kind
    return tuple(spans)


def matrix_value(matrix: list[list[Any]], row: int, column: int) -> Any:
    if row < 0 or column < 0 or row >= len(matrix) or column >= len(matrix[row]):
        return None
    return matrix[row][column]


def is_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("=")
