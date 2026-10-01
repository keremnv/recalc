"""Mechanical A1 range compression. Geometry only; no ranking."""
from __future__ import annotations

from collections import defaultdict

from fingerprint import a1_address, column_letter, column_number


def parse_a1_cell(address: str) -> tuple[int, int]:
    address = address.strip().upper().replace("$", "")
    index = 0
    while index < len(address) and address[index].isalpha():
        index += 1
    if index == 0 or index == len(address):
        raise ValueError(f"Invalid A1 address: {address}")
    return column_number(address[:index]), int(address[index:])


def parse_a1_range(spec: str) -> tuple[int, int, int, int]:
    spec = spec.strip().replace("$", "")
    if "!" in spec:
        spec = spec.split("!", 1)[1]
    if ":" not in spec:
        col, row = parse_a1_cell(spec)
        return col, row, col, row
    start, end = spec.split(":", 1)
    c1, r1 = parse_a1_cell(start)
    c2, r2 = parse_a1_cell(end)
    return min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2)


def compress_cells(cells: set[tuple[int, int]]) -> list[str]:
    if not cells:
        return []
    by_row: dict[int, list[int]] = defaultdict(list)
    for col, row in cells:
        by_row[row].append(col)

    def intervals(cols: list[int]) -> tuple[tuple[int, int], ...]:
        ordered = sorted(set(cols))
        out: list[tuple[int, int]] = []
        start = prev = ordered[0]
        for col in ordered[1:]:
            if col == prev + 1:
                prev = col
            else:
                out.append((start, prev))
                start = prev = col
        out.append((start, prev))
        return tuple(out)

    row_iv = {row: intervals(cols) for row, cols in by_row.items()}
    rows = sorted(row_iv)
    ranges: list[str] = []
    index = 0
    while index < len(rows):
        r0 = rows[index]
        iv = row_iv[r0]
        r1 = r0
        follow = index + 1
        while follow < len(rows) and rows[follow] == r1 + 1 and row_iv[rows[follow]] == iv:
            r1 = rows[follow]
            follow += 1
        for c1, c2 in iv:
            start = a1_address(c1, r0)
            end = a1_address(c2, r1)
            ranges.append(start if start == end else f"{start}:{end}")
        index = follow
    return ranges


def format_member_ranges(by_sheet: dict[str, set[tuple[int, int]]]) -> str:
    parts = []
    for sheet in sorted(by_sheet):
        specs = compress_cells(by_sheet[sheet])
        if not specs:
            continue
        parts.append(f"{sheet}!{','.join(specs)}")
    return "; ".join(parts)


def column_letter_public(number: int) -> str:
    return column_letter(number)
