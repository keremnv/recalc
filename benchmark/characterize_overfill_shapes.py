#!/usr/bin/env python3
"""Classify every regression-first failure by the shape of the cell that was wrongly written.

Four hand-read cases suggested four different mechanisms rather than one, so this counts them.
The classification uses only the input workbook and the address the evaluator names as the first
miss; goldens are not opened. The point is to learn which mechanism dominates *before* designing
an observation for it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

import characterize_commit_checks as cc

from librecalc_mcp.domain.grid import column_number

DATA_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/data"
RUNS_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
_MISS = re.compile(r"^(Regression|Modification) error at (.+?): answer=", re.IGNORECASE)
_A1 = re.compile(r"^([A-Za-z]+)([0-9]+)$")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def classify(cells: dict, sheet: str, address: str) -> tuple[str, dict[str, Any]]:
    """Name the shape of a wrongly written cell from the input workbook alone."""
    match = _A1.match(address)
    if match is None:
        return "unparseable_address", {}
    column, row = match.group(1).upper(), int(match.group(2))

    if (sheet, f"{column}{row}") in cells:
        return "populated_overwrite", {}

    column_rows = sorted(
        int(_A1.match(addr).group(2))
        for (s, addr) in cells
        if s == sheet and _A1.match(addr) and _A1.match(addr).group(1) == column
    )
    row_columns = sorted(
        column_number(_A1.match(addr).group(1))
        for (s, addr) in cells
        if s == sheet and _A1.match(addr) and int(_A1.match(addr).group(2)) == row
    )
    facts = {
        "column_populated_rows": len(column_rows),
        "row_populated_columns": len(row_columns),
    }
    if not column_rows:
        return "column_never_populated", facts
    if not row_columns:
        return "row_never_populated", facts
    if row > column_rows[-1]:
        return "column_extended_below", facts
    if row < column_rows[0]:
        return "column_extended_above", facts
    if column_number(column) > row_columns[-1]:
        return "row_extended_right", facts
    if column_number(column) < row_columns[0]:
        return "row_extended_left", facts
    return "interior_hole", facts


def main() -> int:
    args = _arguments()
    run_dir = args.runs_dir / args.run
    tasks = json.loads((run_dir / "official_scores.json").read_text(encoding="utf-8"))["tasks"]
    datasets = {
        directory.name: {t["id"]: t for t in json.loads((directory / "dataset.json").read_text())}
        for directory in sorted(DATA_DIR.iterdir())
        if (directory / "dataset.json").is_file()
    }

    tally: Counter = Counter()
    detail: list[dict[str, Any]] = []
    analysed = 0
    for task, score in sorted(tasks.items()):
        if score.get("accuracy"):
            continue
        match = _MISS.match(score.get("error_message") or "")
        if match is None or match.group(1).lower() != "regression":
            continue
        if args.limit and analysed >= args.limit:
            break
        category, _, task_id = task.partition(":")
        entry = datasets.get(category, {}).get(task_id)
        if entry is None:
            continue
        sheet, _, cell = match.group(2).rpartition("!")
        try:
            cells = cc._cell_map(DATA_DIR / category / entry["spreadsheet_path"])
        except Exception:  # noqa: BLE001 - a stored input may be unreadable
            tally["unreadable"] += 1
            continue
        shape, facts = classify(cells, sheet, cell)
        analysed += 1
        tally[shape] += 1
        detail.append(
            {
                "task": task,
                "address": match.group(2),
                "shape": shape,
                "modification": score.get("modification_accuracy"),
                **facts,
            }
        )

    print(f"regression-first tasks classified: {analysed}")
    for shape, count in tally.most_common():
        share = f"{100 * count / analysed:.1f}%" if analysed else "n/a"
        print(f"  {count:>4}  {share:>6}  {shape}")
    near = [d for d in detail if (d.get("modification") or 0) >= 0.99]
    if near:
        print(f"\n  of the {len(near)} that are one overfill from exact:")
        for entry in sorted(near, key=lambda d: d["shape"]):
            print(f"    {entry['shape']:<24} {entry['task']:<22} {entry['address']}")
    if args.json:
        args.json.write_text(json.dumps(detail, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
