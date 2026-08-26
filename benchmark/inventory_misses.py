#!/usr/bin/env python3
"""What did we actually get wrong, and do we know why?

Reads every official_scores.json under benchmark-runs/ and sorts each scored miss into a
failure class by looking at what the failing cell held in the *input* workbook:

  absence: hole never filled      blank in input, agent wrote nothing
  absence: hole found, wrong      blank in input, agent wrote the wrong thing
  existing formula: wrong value   input held a formula, agent changed it wrongly
  existing literal: wrong value   input held a literal
  structural                      the evaluator never got as far as a cell

The split matters for what to build. Absence detection can only ever address the first
class. The second class already found the cell and computed it wrong, so a better detector
does nothing for it.

DIAGNOSED lists signatures whose root cause has actually been established, as opposed to
merely localised to a cell. Everything else is a symptom with an address.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "benchmark-data/SpreadsheetBench-2/evaluation"))

import openpyxl
from xlsx_metadata_repair import install

install()

RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs"
DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
ERROR = re.compile(
    r"(?:Regression|Modification) error at (.+?)!([A-Z]{1,3}\d{1,7}): answer=(.*?), output=(.*)$",
    re.DOTALL,
)

# Root cause established, not merely localised. Keep this honest: a reproducible symptom
# is not a diagnosis.
DIAGNOSED = {
    ("Financial_Model:09_04", "Valuation!G59"): (
        "blank target the model never nominates; characterised against official ground "
        "truth -- selection needs the instruction, so the world cannot resolve it alone"
    ),
    ("Debugging:04_02", "Income Statement!J20"): (
        "wrote the precedent's value as a literal (=(-0.595*...)) where the golden keeps "
        "the reference (=(-J52*J19)); numerically equal today, wrong on recalculation"
    ),
    ("Template:01_04", ""): "required worksheet OID_Bond was never created",
}


def _dataset(category: str, cache: dict) -> dict:
    if category not in cache:
        tasks = json.loads((DATA / category / "dataset.json").read_text())
        cache[category] = {task["id"]: task for task in tasks}
    return cache[category]


def _input_state(key: str, sheet: str, cell: str, cache: dict) -> str:
    category, task_id = key.split(":")
    task = _dataset(category, cache)[task_id]
    workbook = openpyxl.load_workbook(DATA / category / task["spreadsheet_path"], data_only=False)
    match = next(
        (workbook[n] for n in workbook.sheetnames if n.strip().lower() == sheet.strip().lower()),
        None,
    )
    if match is None:
        return "no-sheet"
    value = match[cell].value
    if value is None:
        return "BLANK"
    return "formula" if isinstance(value, str) and value.startswith("=") else "literal"


def classify(key: str, message: str, cache: dict) -> tuple[str, str]:
    match = ERROR.match(message.strip())
    if match is None:
        return "structural", ""
    sheet, cell, _answer, output = match.groups()
    signature = f"{sheet}!{cell}"
    state = _input_state(key, sheet, cell, cache)
    if state == "BLANK":
        blank_kind = "never filled" if output.strip() == "None" else "found, value wrong"
        return f"absence: hole {blank_kind}", signature
    return f"existing {state}: value wrong", signature


def main() -> int:
    cache: dict = {}
    attempts: list[tuple[str, str, str]] = []
    exact = 0
    for path in sorted(RUNS.glob("*/*/official_scores.json")) + sorted(
        RUNS.glob("*/official_scores.json")
    ):
        scores = json.loads(path.read_text())
        for key, task in scores.get("tasks", {}).items():
            if task.get("accuracy") == 1.0:
                exact += 1
                continue
            bucket, signature = classify(key, task.get("error_message", ""), cache)
            attempts.append((bucket, key, signature))

    total = len(attempts)
    print(f"{exact + total} scored attempts: {exact} exact, {total} misses\n")
    distinct = sorted({(b, k, s) for b, k, s in attempts})
    for scope, rows in (("by attempt", attempts), ("by distinct signature", distinct)):
        counts = Counter(bucket for bucket, _, _ in rows)
        print(f"=== {scope} (n={len(rows)}) ===")
        for bucket, n in counts.most_common():
            print(f"{n:4}  {n / len(rows):5.0%}  {bucket}")
        print()

    known = [row for row in distinct if (row[1], row[2]) in DIAGNOSED]
    print(f"=== root cause established: {len(known)}/{len(distinct)} distinct signatures ===")
    for _bucket, key, signature in known:
        print(f"  {key} {signature}\n      {DIAGNOSED[(key, signature)]}")
    print(f"\n=== localised but undiagnosed: {len(distinct) - len(known)} ===")
    for bucket, key, signature in distinct:
        if (key, signature) not in DIAGNOSED:
            print(f"  {key:24} {signature:28} {bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
