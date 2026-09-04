"""Score formula-index pilot trajectories for proximal fingerprint writes.

Goldens are used offline only. The arm-comparable proximal metric is whether the
submitted formula at a golden-changed target has the golden fingerprint.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "benchmark"))

from fingerprint import formula_text, relative_fingerprint  # noqa: E402
from workbook import WorkbookIndex, build_index  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

from experiment_metrics import trajectory_metrics  # noqa: E402

RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
_EQ = re.compile(r"\beq ([0-9a-f]{10})\b")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control_run")
    parser.add_argument("treatment_run")
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def load_formulas(path: Path) -> dict[tuple[str, int, int], str]:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
    out: dict[tuple[str, int, int], str] = {}
    try:
        for sheet in wb.worksheets:
            for cell in sheet._cells.values():
                text = formula_text(cell.value)
                if text:
                    out[(sheet.title, int(cell.column), int(cell.row))] = text
    finally:
        wb.close()
    return out


def load_values(path: Path) -> dict[tuple[str, int, int], object]:
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
    out: dict[tuple[str, int, int], object] = {}
    try:
        for sheet in wb.worksheets:
            for cell in sheet._cells.values():
                if formula_text(cell.value):
                    continue
                out[(sheet.title, int(cell.column), int(cell.row))] = cell.value
    finally:
        wb.close()
    return out


def is_blank(formula: str | None, value: object) -> bool:
    if formula:
        return False
    return value is None or value == ""


def occupancy_targets(
    index: WorkbookIndex,
    inp: dict[tuple[str, int, int], str],
    inv: dict[tuple[str, int, int], object],
    gold: dict[tuple[str, int, int], str],
    gval: dict[tuple[str, int, int], object],
) -> list[dict[str, Any]]:
    keys = set(inp) | set(inv) | set(gold) | set(gval)
    targets = []
    for pos in keys:
        gf = gold.get(pos)
        inf = inp.get(pos)
        if not gf or inf == gf:
            continue
        sheet, col, row = pos
        fp = relative_fingerprint(gf, col, row, sheet=sheet)
        bucket = index.nearest_bucket(sheet, col, row, fp.eq_id)
        row_ids = index.by_row.get((sheet, row), set())
        unique_row = fp.eq_id in row_ids and len(row_ids) == 1
        targets.append(
            {
                "sheet": sheet,
                "col": col,
                "row": row,
                "blank_fill": is_blank(inf, inv.get(pos)),
                "golden_fp": fp.text,
                "golden_eq_id": fp.eq_id,
                "golden_opaque": fp.opaque,
                "stratum": bucket,
                "unique_row": unique_row,
            }
        )
    return targets


def parse_trajectory(path: Path) -> dict[str, Any]:
    empty = {
        "invoked": False,
        "queries": [],
        "eq_ids": [],
        "model_calls": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "cost": None,
    }
    if not path.is_file():
        return empty
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = trajectory_metrics(path)
    queries = []
    eq_ids: list[str] = []
    for step in data.get("trajectory", []):
        action = str(step.get("action") or "")
        observation = str(step.get("observation") or "")
        blob = action + "\n" + observation
        if "formula_index" not in blob:
            continue
        if re.search(r"formula_index\s+range\b", blob):
            queries.append("range")
        elif re.search(r"formula_index\s+axis\b", blob):
            queries.append("axis")
        elif re.search(r"formula_index\s+lookup\b", blob):
            queries.append("lookup")
        else:
            queries.append("formula_index")
        eq_ids.extend(_EQ.findall(blob))
    return {
        "invoked": bool(queries),
        "queries": queries,
        "eq_ids": sorted(set(eq_ids)),
        "model_calls": metrics.get("model_calls"),
        "prompt_tokens": metrics.get("harness_prompt_tokens"),
        "completion_tokens": metrics.get("harness_completion_tokens"),
        "cost": metrics.get("harness_estimated_cost_usd"),
    }


def score_targets(
    targets: list[dict[str, Any]],
    submitted: dict[tuple[str, int, int], str] | None,
    trajectory: dict[str, Any],
    *,
    task: str,
) -> list[dict[str, Any]]:
    rows = []
    for target in targets:
        pos = (target["sheet"], target["col"], target["row"])
        submitted_formula = None if submitted is None else submitted.get(pos)
        submitted_fp = None
        match = False
        if submitted_formula:
            fp = relative_fingerprint(
                submitted_formula, pos[1], pos[2], sheet=pos[0]
            )
            submitted_fp = fp.text
            match = submitted_fp == target["golden_fp"]
        rows.append(
            {
                **target,
                "task": task,
                "submitted_fp": submitted_fp,
                "fingerprint_match": match,
                "index_invoked": trajectory.get("invoked", False),
                "retrieved_class": target["golden_eq_id"] in trajectory.get("eq_ids", []),
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_stratum[row["stratum"]].append(row)
        if row.get("unique_row"):
            by_stratum["unique_row"].append(row)

    def pack(items: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(items)
        hits = sum(1 for item in items if item["fingerprint_match"])
        tasks = {item["task"] for item in items if item.get("task")}
        task_hits = {
            item["task"] for item in items if item.get("task") and item["fingerprint_match"]
        }
        return {
            "cells": n,
            "fingerprint_match_cells": hits,
            "fingerprint_match_cell_pct": None if n == 0 else round(100 * hits / n, 2),
            "tasks": len(tasks),
            "tasks_any_match": len(task_hits),
            "task_pct": None if not tasks else round(100 * len(task_hits) / len(tasks), 2),
        }

    return {name: pack(items) for name, items in sorted(by_stratum.items())}


def _find_trajectory(task_root: Path) -> Path | None:
    matches = list(task_root.rglob("*.traj")) + list(task_root.rglob("*trajectory*.json"))
    return matches[0] if matches else None


def score_run(run_root: Path, tasks: list[dict[str, str]]) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    mediation: list[dict[str, Any]] = []
    for task in tasks:
        category, task_id = task["category"], task["id"]
        task_key = f"{category}:{task_id}"
        dataset = json.loads((DATA / category / "dataset.json").read_text())
        record = next(item for item in dataset if item["id"] == task_id)
        inp_path = DATA / category / record["spreadsheet_path"]
        gold_path = DATA / category / record["golden_response_path"]
        index = build_index(inp_path)
        inp = load_formulas(inp_path)
        inv = load_values(inp_path)
        gold = load_formulas(gold_path)
        gval = load_values(gold_path)
        targets = occupancy_targets(index, inp, inv, gold, gval)
        task_root = run_root / f"{category}-{task_id}"
        output = task_root / "output.xlsx"
        submitted = load_formulas(output) if output.is_file() else None
        traj_path = _find_trajectory(task_root)
        trajectory = parse_trajectory(traj_path) if traj_path else {
            "invoked": False,
            "queries": [],
            "eq_ids": [],
            "model_calls": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "cost": None,
        }
        rows = score_targets(targets, submitted, trajectory, task=task_key)
        all_rows.extend(rows)
        mediation.append(
            {
                "task": task_key,
                "index_invoked": trajectory["invoked"],
                "queries": trajectory["queries"],
                "retrieved_any_golden_class": any(row["retrieved_class"] for row in rows),
                "fingerprint_match_cells": sum(row["fingerprint_match"] for row in rows),
                "targets": len(rows),
            }
        )
    return {
        "by_stratum": summarize(all_rows),
        "mediation": mediation,
        "cells": all_rows,
    }


def main() -> int:
    args = _arguments()
    slice_tasks = json.loads(
        (ROOT / "benchmark/slices/fm-index-pilot-twenty.json").read_text()
    )["tasks"]
    control = score_run(args.runs_dir / args.control_run, slice_tasks)
    treatment = score_run(args.runs_dir / args.treatment_run, slice_tasks)
    report = {
        "proximal_metric": "correct golden fingerprint written at target",
        "control": {"by_stratum": control["by_stratum"], "mediation": control["mediation"]},
        "treatment": {
            "by_stratum": treatment["by_stratum"],
            "mediation": treatment["mediation"],
        },
    }
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
