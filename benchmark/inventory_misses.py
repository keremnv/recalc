#!/usr/bin/env python3
"""What was the first reported error in each non-exact attempt?

The official evaluator retains only the first error message for a task. This script reads
every official_scores.json under benchmark-runs/ and sorts that first-error signature by
what the reported cell held in the *input* workbook:

  absence: hole never filled      blank in input, agent wrote nothing
  absence: hole found, wrong      blank in input, agent wrote the wrong thing
  downstream cascade              input/output retain the same formula; cause is upstream
  existing formula/literal        the reported cell itself was over-edited
  structural                      the evaluator never got as far as a cell

The split is useful for triage, but it is not a census of wrong cells and cannot support a
claim about what percentage of all cell-level misses belongs to each class. Absence
detection can address only a "never filled" first error; it cannot repair a wrong value.

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

import evaluation as ev
import openpyxl
from experiment_validity import invalid_reason
from xlsx_metadata_repair import install

install()

RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs"
DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
ERROR = re.compile(
    r"(Regression|Modification) error at (.+?)!([A-Z]{1,3}\d{1,7}): "
    r"answer=(.*?), output=(.*)$",
    re.DOTALL,
)

# Root cause established, not merely localised. Keep this honest: a reproducible symptom
# is not a diagnosis.
DIAGNOSED = {
    ("Template:01_03", "ZeroCouponBond!C12"): (
        "accounting sign/concept choice, not missing context: the model explicitly treated "
        "cash tax minus book tax as positive deferred tax and reused the DTA-change formula; "
        "the golden records deferred tax expense as negative OID amortization times the tax rate"
    ),
    ("Financial_Model:09_04", "Valuation!G59"): (
        "blank target the model never nominates; characterised against official ground "
        "truth -- selection needs the instruction, so the world cannot resolve it alone"
    ),
    ("Financial_Model:01_02", "Working Capital Schedule!M3"): (
        "implicit target-selection miss: the golden extends an unmentioned forecast date with "
        "=EOMONTH(L3,12), while the instruction names Debt Schedule, WACC, DCF Valuation, and "
        "Income Statement work; the model scoped inspection to those named dependencies and "
        "never selected Working Capital Schedule"
    ),
    ("Debugging:04_02", "Income Statement!J20"): (
        "wrote the precedent's value as a literal (=(-0.595*...)) where the golden keeps "
        "the reference (=(-J52*J19)); numerically equal today, wrong on recalculation"
    ),
    ("Template:02_05", "DebtWaterfall!E35"): (
        "GLM chose to accumulate excess cash after debt reached zero, despite the instruction "
        "requiring ending cash to equal the operating cash requirement exactly; successful "
        "runs link row 35 to row 7. Context, execution, and post-write reads were available"
    ),
    ("Template:02_05", "DebtWaterfall!B5"): (
        "thin-interface ablation wrote one 31x4 matrix at B5:E35 even though the model data "
        "columns are C:F, overwriting row labels and shifting every formula; this is the "
        "expected destructive target-selection failure of the thin calc_write arm"
    ),
}


def _dataset(category: str, cache: dict) -> dict:
    if category not in cache:
        tasks = json.loads((DATA / category / "dataset.json").read_text())
        cache[category] = {task["id"]: task for task in tasks}
    return cache[category]


def _workbook(path: Path, cache: dict) -> openpyxl.Workbook:
    key = str(path.resolve())
    if key not in cache:
        cache[key] = openpyxl.load_workbook(path, data_only=False)
    return cache[key]


def _cell(path: Path, sheet: str, address: str, cache: dict):
    workbook = _workbook(path, cache)
    match = next(
        (workbook[n] for n in workbook.sheetnames if n.strip().lower() == sheet.strip().lower()),
        None,
    )
    return None if match is None else match[address]


def _input_path(key: str, dataset_cache: dict) -> Path:
    category, task_id = key.split(":")
    task = _dataset(category, dataset_cache)[task_id]
    return DATA / category / task["spreadsheet_path"]


def classify(
    key: str,
    message: str,
    run_root: Path,
    dataset_cache: dict,
    workbook_cache: dict,
) -> tuple[str, str]:
    match = ERROR.match(message.strip())
    if match is None:
        return "structural", ""
    error_kind, sheet, cell, _answer, output = match.groups()
    signature = f"{sheet}!{cell}"
    input_cell = _cell(_input_path(key, dataset_cache), sheet, cell, workbook_cache)
    if input_cell is None:
        return "structural: input sheet missing", signature
    input_value = input_cell.value
    if input_value is None:
        if error_kind == "Regression":
            return "direct over-edit of evaluator-equivalent blank", signature
        blank_kind = "never filled" if output.strip() == "None" else "found, value wrong"
        return f"absence: hole {blank_kind}", signature

    category, task_id = key.split(":")
    output_path = run_root / f"{category}-{task_id}" / "output.xlsx"
    if not output_path.exists():
        return "structural: output workbook missing", signature
    output_cell = _cell(output_path, sheet, cell, workbook_cache)
    if output_cell is None:
        return "structural: output sheet missing", signature

    input_formula = getattr(input_value, "text", input_value)
    if isinstance(input_formula, str) and input_formula.startswith("="):
        if ev.compare_cell_formula(input_cell, output_cell):
            return "downstream cascade at unchanged formula", signature
        return "direct over-edit of existing formula", signature
    return "direct over-edit of existing literal", signature


def main() -> int:
    dataset_cache: dict = {}
    workbook_cache: dict = {}
    attempts: list[tuple[str, str, str]] = []
    exact = 0
    for path in sorted(RUNS.glob("*/*/official_scores.json")) + sorted(
        RUNS.glob("*/official_scores.json")
    ):
        scores = json.loads(path.read_text())
        run_name = str(scores.get("run_name") or path.parent.name)
        for key, task in scores.get("tasks", {}).items():
            if invalid_reason(run_name, key):
                continue
            if task.get("accuracy") == 1.0:
                exact += 1
                continue
            bucket, signature = classify(
                key,
                task.get("error_message", ""),
                path.parent,
                dataset_cache,
                workbook_cache,
            )
            attempts.append((bucket, key, signature))

    total = len(attempts)
    print(f"{exact + total} scored attempts: {exact} exact, {total} non-exact\n")
    distinct = sorted({(b, k, s) for b, k, s in attempts})
    for scope, rows in (
        ("by non-exact attempt's first error", attempts),
        ("by distinct first-error signature", distinct),
    ):
        counts = Counter(bucket for bucket, _, _ in rows)
        print(f"=== {scope} (n={len(rows)}) ===")
        for bucket, n in counts.most_common():
            print(f"{n:4}  {n / len(rows):5.0%}  {bucket}")
        print()

    known = [row for row in distinct if (row[1], row[2]) in DIAGNOSED]
    print(
        "=== root cause established: "
        f"{len(known)}/{len(distinct)} distinct first-error signatures ==="
    )
    for _bucket, key, signature in known:
        print(f"  {key} {signature}\n      {DIAGNOSED[(key, signature)]}")
    print(f"\n=== first error localised but undiagnosed: {len(distinct) - len(known)} ===")
    for bucket, key, signature in distinct:
        if (key, signature) not in DIAGNOSED:
            print(f"  {key:24} {signature:28} {bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
