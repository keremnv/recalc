#!/usr/bin/env python3
"""Does the region_occupancy extent actually name the stop each overfill crossed?

The field reports two things per region: how far down each column is populated, and how far
right each row is populated. A miss is reachable when either names it -- the column's extent
ends above the miss row, or the miss row's own extent ends left of the miss column. It is
unreachable when the miss row spans the whole block and the miss column lies outside it, which
is the geometry the field is structurally blind to. This separates the two using the input
workbook and the evaluator's miss address only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

import characterize_commit_checks as cc
from characterize_overfill_shapes import _A1, DATA_DIR

from librecalc_mcp.domain.grid import column_number

_REACHABLE_SHAPES = {"column_extended_below", "column_extended_above", "row_extended_right"}


def _rows(cells: dict, sheet: str) -> dict[int, set[int]]:
    """Populated column numbers per row, for one sheet of the input workbook."""
    rows: dict[int, set[int]] = {}
    for other, address in cells:
        if other != sheet:
            continue
        match = _A1.match(address)
        if match is None:
            continue
        rows.setdefault(int(match.group(2)), set()).add(column_number(match.group(1)))
    return rows


def _regions(by_row: dict[int, set[int]]) -> list[tuple[int, int, set[int]]]:
    """Row-contiguous blocks as (first row, last row, populated columns), like inspect."""
    regions: list[tuple[int, int, set[int]]] = []
    start: int | None = None
    previous: int | None = None
    for row in sorted(by_row):
        if start is None:
            start = row
        elif previous is not None and row != previous + 1:
            regions.append((start, previous, set().union(*(by_row[r] for r in range(start, previous + 1)))))
            start = row
        previous = row
    if start is not None and previous is not None:
        regions.append((start, previous, set().union(*(by_row[r] for r in range(start, previous + 1)))))
    return regions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("detail", type=Path, help="JSON written by characterize_overfill_shapes.py")
    parser.add_argument("--category", default="Template")
    args = parser.parse_args()

    detail = json.loads(args.detail.read_text(encoding="utf-8"))
    datasets = {
        directory.name: {t["id"]: t for t in json.loads((directory / "dataset.json").read_text())}
        for directory in sorted(DATA_DIR.iterdir())
        if (directory / "dataset.json").is_file()
    }

    tally: Counter = Counter()
    unreachable: list[str] = []
    for entry in detail:
        category, _, task_id = entry["task"].partition(":")
        if category != args.category or entry["shape"] not in _REACHABLE_SHAPES:
            continue
        dataset_entry = datasets.get(category, {}).get(task_id)
        if dataset_entry is None:
            continue
        sheet, _, address = entry["address"].rpartition("!")
        match = _A1.match(address)
        if match is None:
            continue
        column, row = column_number(match.group(1)), int(match.group(2))
        cells = cc._cell_map(DATA_DIR / category / dataset_entry["spreadsheet_path"])
        by_row = _rows(cells, sheet)
        containing = [r for r in _regions(by_row) if r[0] <= row <= r[1]]
        if not containing:
            # The miss sits in a blank row between blocks. No region contains it, so neither
            # half of the field can address the cell itself.
            tally["outside_every_region"] += 1
            unreachable.append(f"{entry['task']} {entry['address']} ({entry['shape']}, no block)")
            continue
        first_row, last_row, columns = containing[0]
        column_rows = [r for r in range(first_row, last_row + 1) if column in by_row.get(r, set())]
        if column_rows and row > column_rows[-1]:
            tally["named_by_column_extent"] += 1
            continue
        row_columns = by_row.get(row, set())
        if row_columns and max(row_columns) < column and max(row_columns) < max(columns):
            tally["named_by_row_extent"] += 1
            continue
        tally["unreachable"] += 1
        unreachable.append(f"{entry['task']} {entry['address']} ({entry['shape']})")

    total = sum(tally.values())
    print(f"{args.category} run-extension misses examined: {total}")
    for name, count in tally.most_common():
        share = f"{100 * count / total:.1f}%" if total else "n/a"
        print(f"  {count:>4}  {share:>6}  {name}")
    if unreachable:
        print("\n  no extent names these; they need a commit-time check:")
        for line in unreachable:
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
