#!/usr/bin/env python3
"""How much of the required work is *absent* state, and how much of it is reachable?

Section 9.1 says absence is data. This measures the surface: across a whole category,
what fraction of the cells an agent must modify are blank in the input, and of those,
how many could be nominated by a signal that generalises from populated peers.

Classification of each blank target:
  row-peer     a cell in the same row within 8 columns holds a formula
  col-peer     a cell in the same column within 8 rows holds a formula
  block-peer   both of the above
  isolated     neither -- no peer-based signal can reach it (the Valuation!G59 class)

Ground truth is the official evaluator's own classify_cells_by_modification, restricted
to each task's answer_position. No model calls.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark-data/SpreadsheetBench-2/evaluation"))

import evaluation as ev
import openpyxl

PEER_DISTANCE = 8


def _norm(v):
    return getattr(v, "text", None) or v


def _is_formula(v) -> bool:
    return isinstance(v, str) and v.startswith("=")


def _split(addr: str) -> tuple[int, int]:
    letters = "".join(c for c in addr if c.isalpha())
    digits = "".join(c for c in addr if c.isdigit())
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n, int(digits)


def _col(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


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

    counts: Counter = Counter()
    for chunk in ev.parse_answer_position(task["answer_position"]):
        sheet_name, _, rng = chunk.rpartition("!")
        sheet_name = sheet_name.strip().strip("'")
        _reg, mod = ev.classify_cells_by_modification(
            wb_i, wb_a, sheet_name, rng, with_color, with_formula, wb_if, wb_af
        )
        if not mod:
            continue
        ws_i = ev._find_sheet(wb_i, sheet_name)
        ws_f = ev._find_sheet(formulas, sheet_name)
        if ws_i is None or ws_f is None:
            continue
        for cell in mod:
            counts["targets"] += 1
            if ws_i[cell].value is not None:
                counts["populated"] += 1
                continue
            counts["blank"] += 1
            c, r = _split(cell)
            row_peer = any(
                _is_formula(_norm(ws_f[f"{_col(cc)}{r}"].value))
                for cc in range(max(1, c - PEER_DISTANCE), c + PEER_DISTANCE + 1)
                if cc != c
            )
            col_peer = any(
                _is_formula(_norm(ws_f[f"{_col(c)}{rr}"].value))
                for rr in range(max(1, r - PEER_DISTANCE), r + PEER_DISTANCE + 1)
                if rr != r
            )
            if row_peer and col_peer:
                counts["block-peer"] += 1
            elif row_peer:
                counts["row-peer"] += 1
            elif col_peer:
                counts["col-peer"] += 1
            else:
                counts["isolated"] += 1
    return counts


def main() -> int:
    category = sys.argv[1] if len(sys.argv) > 1 else "Financial_Model"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    data_dir = ROOT / "benchmark-data/SpreadsheetBench-2/data" / category
    tasks = json.loads((data_dir / "dataset.json").read_text())
    if limit:
        tasks = tasks[:limit]
    total: Counter = Counter()
    for task in tasks:
        try:
            counts = analyse(task, data_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"{task['id']:8} ERROR {type(exc).__name__}: {str(exc)[:50]}", file=sys.stderr)
            continue
        total.update(counts)
        if counts["blank"]:
            print(
                f"{task['id']:8} targets={counts['targets']:6} blank={counts['blank']:6} "
                f"block={counts['block-peer']:5} row={counts['row-peer']:4} "
                f"col={counts['col-peer']:4} isolated={counts['isolated']:4}"
            )
    t, b = total["targets"], total["blank"]
    print(f"\n=== {category}: {len(tasks)} tasks ===")
    print(f"modification targets        {t:8,}")
    print(f"  already populated         {total['populated']:8,}  ({total['populated']/max(1,t):.1%})")
    print(f"  BLANK in input            {b:8,}  ({b/max(1,t):.1%})")
    for key in ("block-peer", "row-peer", "col-peer", "isolated"):
        print(f"    {key:22} {total[key]:8,}  ({total[key]/max(1,b):.1%} of blanks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
