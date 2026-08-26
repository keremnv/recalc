#!/usr/bin/env python3
"""Is a blank target *demanded* by the sheet, or merely shaped like its neighbours?

characterize_absence_surface.py classifies each blank modification target by the shape
of its neighbourhood (row/col/block/isolated). That is a similarity signal, and it hits a
precision wall in the 3-8% band because most holes in a spreadsheet are deliberate.

The shipped detector (_blank_dependency_bridges) works on a different axis: it nominates a
blank cell because a live formula *references* it. That is a demand signal -- a referenced
blank is broken by construction, not merely unusual. This measures that axis directly:

  referenced    some formula elsewhere in the workbook names this cell (or a range over it)
  unreferenced  nothing points at it

For a referenced blank, the candidate pool is bounded by how many blanks the workbook
actually asks for, not by how many cells look lonely. That bound is the number reported
here as "demand pool", and it is the ceiling on the shipped detector's precision.

Ground truth is the official evaluator's classify_cells_by_modification, restricted to each
task's answer_position. No model calls.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark-data/SpreadsheetBench-2/evaluation"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))

import evaluation as ev
import openpyxl
from xlsx_metadata_repair import install as _install_repair

_install_repair()

from librecalc_mcp.domain.formulas import formula_a1_references
from librecalc_mcp.domain.grid import column_label, column_number

# A range wide enough to be a whole-column sweep tells us nothing about any one cell in it.
RANGE_MAX_CELLS = 4096
CELL = re.compile(r"^\$?([A-Z]{1,3})\$?([0-9]{1,7})$")


def _cells_in(start: str, end: str | None) -> list[str] | None:
    a, b = CELL.match(start.upper()), CELL.match((end or start).upper())
    if not a or not b:
        return None
    c0, r0 = column_number(a.group(1)), int(a.group(2))
    c1, r1 = column_number(b.group(1)), int(b.group(2))
    c0, c1 = min(c0, c1), max(c0, c1)
    r0, r1 = min(r0, r1), max(r0, r1)
    if (c1 - c0 + 1) * (r1 - r0 + 1) > RANGE_MAX_CELLS:
        return None
    return [f"{column_label(c)}{r}" for c in range(c0, c1 + 1) for r in range(r0, r1 + 1)]


def _demanded(workbook) -> set[tuple[str, str]]:
    """Every (sheet, address) named by some formula in the workbook."""
    demanded: set[tuple[str, str]] = set()
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value
                if not isinstance(value, str) or not value.startswith("="):
                    continue
                for ref_sheet, start, end in formula_a1_references(value):
                    addresses = _cells_in(start, end)
                    if addresses is None:
                        continue
                    for address in addresses:
                        demanded.add((ref_sheet or sheet.title, address))
    return demanded


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def analyse(task: dict, data_dir: Path) -> Counter:
    inp = data_dir / task["spreadsheet_path"]
    gold = data_dir / task["golden_response_path"]
    with_color = "Color" in task["spreadsheet_path"]
    with_formula = "Embedded" in task["spreadsheet_path"]

    wb_i = openpyxl.load_workbook(inp, data_only=not with_formula)
    wb_a = openpyxl.load_workbook(gold, data_only=not with_formula)
    wb_if = openpyxl.load_workbook(inp, data_only=False) if not with_formula else None
    wb_af = openpyxl.load_workbook(gold, data_only=False) if not with_formula else None
    formulas = openpyxl.load_workbook(inp, data_only=False)

    demanded = _demanded(formulas)
    counts: Counter = Counter()

    # The candidate pool the shipped detector draws from: blanks something already asks for.
    for sheet_name, address in demanded:
        ws = ev._find_sheet(formulas, sheet_name)
        if ws is None:
            continue
        try:
            if _is_blank(ws[address].value):
                counts["demand pool"] += 1
        except (ValueError, KeyError):
            continue

    for chunk in ev.parse_answer_position(task["answer_position"]):
        sheet_name, _, rng = chunk.rpartition("!")
        sheet_name = sheet_name.strip().strip("'")
        _reg, mod = ev.classify_cells_by_modification(
            wb_i, wb_a, sheet_name, rng, with_color, with_formula, wb_if, wb_af
        )
        if not mod:
            continue
        ws_i = ev._find_sheet(wb_i, sheet_name)
        ws_raw = ev._find_sheet(formulas, sheet_name)
        if ws_i is None or ws_raw is None:
            continue
        resolved = ws_i.title
        for cell in mod:
            counts["targets"] += 1
            # A cell is present if it holds anything at all -- a literal, or a formula that
            # was never calculated. Many of these workbooks ship with no cached results, so
            # testing the data_only workbook alone reports live formulas as absent and
            # inflates the blank count by an order of magnitude.
            if ws_i[cell].value is not None or ws_raw[cell].value is not None:
                counts["populated"] += 1
                continue
            counts["blank"] += 1
            key = "referenced" if (resolved, cell) in demanded else "unreferenced"
            counts[key] += 1
    return counts


def main() -> int:
    category = sys.argv[1] if len(sys.argv) > 1 else "Financial_Model"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    data_dir = ROOT / "benchmark-data/SpreadsheetBench-2/data" / category
    tasks = json.loads((data_dir / "dataset.json").read_text())
    if limit:
        tasks = tasks[:limit]
    per_task: list[Counter] = []
    for task in tasks:
        try:
            counts = analyse(task, data_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"{task['id']:8} ERROR {type(exc).__name__}: {str(exc)[:50]}", file=sys.stderr)
            continue
        per_task.append(counts)
        if counts["blank"]:
            hit = counts["referenced"] / max(1, counts["demand pool"])
            print(
                f"{task['id']:8} blank={counts['blank']:6} referenced={counts['referenced']:5} "
                f"unreferenced={counts['unreferenced']:6} pool={counts['demand pool']:6} "
                f"precision={hit:6.1%}"
            )
    _report(f"{category}: all {len(per_task)} tasks measured", per_task)
    partial = [c for c in per_task if c["blank"] < c["targets"]]
    if partial and len(partial) != len(per_task):
        _report(f"{category}: {len(partial)} partially populated tasks", partial)
    return 0


def _report(title: str, per_task: list[Counter]) -> None:
    total: Counter = Counter()
    for counts in per_task:
        total.update(counts)
    b = total["blank"]
    print(f"\n=== {title} ===")
    print(f"blank modification targets  {b:8,}")
    for key in ("referenced", "unreferenced"):
        print(f"  {key:24} {total[key]:8,}  ({total[key] / max(1, b):.1%} of blanks)")
    print(f"demand pool (blanks named by a formula)  {total['demand pool']:8,}")
    print(
        f"  pooled precision if the whole pool were nominated: "
        f"{total['referenced'] / max(1, total['demand pool']):.1%}"
    )
    recalls = [c["referenced"] / c["blank"] for c in per_task if c["blank"]]
    precs = [c["referenced"] / c["demand pool"] for c in per_task if c["demand pool"]]
    if recalls:
        print(f"  per-task recall of blanks   median {statistics.median(recalls):7.1%}")
    if precs:
        print(f"  per-task precision of pool  median {statistics.median(precs):7.1%}")
    reach = sum(1 for c in per_task if c["referenced"])
    print(f"  tasks where the demand signal reaches >=1 real target: {reach}/{len(per_task)}")


if __name__ == "__main__":
    raise SystemExit(main())
