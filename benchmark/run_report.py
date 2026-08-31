#!/usr/bin/env python3
"""One tidy row per task, joining everything a run already produces.

A run leaves four separate artifacts -- ledger.jsonl, official_scores.json, the trajectory, and
the workbook -- and every question about it has so far needed a bespoke script. This joins them
once and derives the two things that were always recomputed by hand: the tool-call shape of the
trajectory, and a failure mode.

Metrics are fixed here rather than chosen after the fact:

* ``exact``  official accuracy, for leaderboard comparability.
* ``usable`` regression >= 0.99 AND modification >= 0.99. A deliverable a person would accept
  after deleting a stray cell. Template 05_01 is modification 1.0000 with one extra cell and
  scores exact 0; 14 Financial Model tasks in the Sol 297 sit at reg 1.0 / mod >= 0.99 and
  contribute nothing. Report it beside exact, never instead of it.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
USABLE_THRESHOLD = 0.99

_MISS = re.compile(r"^(Regression|Modification) error at (.+?): answer=", re.IGNORECASE)
_WRITE_TOOLS = ("calc_write", "calc_fill_formulas", "calc_program", "calc_upsert_chart")
_TRANSPORT_400 = ("must not be empty", "Tool choice must be auto", "maximum context length")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="+", help="Run name(s) under the runs directory.")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--csv", type=Path, help="Write the per-task rows here.")
    parser.add_argument("--jsonl", type=Path, help="Write the per-task rows here.")
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Diff the first two runs task by task instead of summarising each.",
    )
    return parser.parse_args()


def _ledger_rows(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Last row wins: the scoring pass re-appends each task."""
    rows: dict[str, dict[str, Any]] = {}
    ledger = run_dir / "ledger.jsonl"
    if not ledger.is_file():
        return rows
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("task"):
            rows[record["task"]] = record
    return rows


def _scores(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / "official_scores.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("tasks", {})
    except ValueError:
        return {}


def _trajectory_shape(task_dir: Path) -> dict[str, Any]:
    """Tool-call shape and the behavioural flags that distinguish failure modes."""
    trajectories = sorted(task_dir.glob("trajectory/*/*.traj"))
    if not trajectories:
        return {}
    try:
        steps = json.loads(trajectories[-1].read_text(encoding="utf-8")).get("trajectory", [])
    except (OSError, ValueError):
        return {}

    tools: list[str] = []
    empty = 0
    findings = 0
    for step in steps:
        action = (step.get("action") or "").strip()
        tools.append(action.split()[0] if action else "(empty)")
        if not action:
            empty += 1
        observation = step.get("observation")
        if isinstance(observation, str) and "commit-checks-v1" in observation:
            findings += 1
    joined = " ".join(tools)
    return {
        "steps": len(steps),
        "tool_sequence": ",".join(tools),
        "empty_completions": empty,
        "wrote": any(tool in joined for tool in _WRITE_TOOLS),
        "submitted": "submit" in tools,
        "commit_report_seen": findings,
        "transport_400": any(
            marker in (step.get("observation") or "")
            for step in steps
            for marker in _TRANSPORT_400
            if isinstance(step.get("observation"), str)
        ),
    }


def _failure_mode(row: dict[str, Any]) -> str:
    if row.get("exact"):
        return "exact"
    if not row.get("has_workbook"):
        if row.get("transport_400"):
            return "no_workbook_transport"
        if row.get("return_code") == 124:
            return "no_workbook_timeout"
        if not row.get("wrote"):
            if row.get("empty_completions"):
                return "no_workbook_format_exit"
            if row.get("model_calls") and row.get("model_calls") >= (row.get("call_limit") or 0):
                return "no_workbook_call_cap"
            return "no_workbook_no_write"
        return "no_workbook_after_write"
    kind = row.get("first_miss_kind")
    if kind == "regression":
        return "wrote_regression_first"
    if kind == "modification":
        return "wrote_modification_first"
    return "wrote_unclassified"


def collect(run_dir: Path) -> list[dict[str, Any]]:
    ledger = _ledger_rows(run_dir)
    scores = _scores(run_dir)
    rows: list[dict[str, Any]] = []
    for task, record in sorted(ledger.items()):
        category = record.get("category") or task.split(":")[0]
        task_id = record.get("task_id") or task.split(":")[-1]
        task_dir = run_dir / f"{category}-{task_id}"
        score = scores.get(task, {})
        message = score.get("error_message") or ""
        match = _MISS.match(message)
        regression = score.get("regression_accuracy")
        modification = score.get("modification_accuracy")
        row: dict[str, Any] = {
            "run": run_dir.name,
            "task": task,
            "category": category,
            "model": record.get("model"),
            "status": record.get("status"),
            "error": record.get("error"),
            "return_code": record.get("return_code"),
            "model_calls": record.get("model_calls"),
            "call_limit": record.get("call_limit"),
            "cost_usd": record.get("charged_cost_usd"),
            "elapsed_seconds": record.get("elapsed_seconds"),
            "reasoning_tokens": record.get("reasoning_tokens"),
            "observation_variant": record.get("observation_variant"),
            "execution_variant": record.get("execution_variant"),
            "has_workbook": (task_dir / "output.xlsx").is_file(),
            "exact": bool(score.get("accuracy")),
            "regression": regression,
            "modification": modification,
            "usable": bool(
                regression is not None
                and modification is not None
                and regression >= USABLE_THRESHOLD
                and modification >= USABLE_THRESHOLD
            ),
            "first_miss_kind": match.group(1).lower() if match else None,
            "first_miss_address": match.group(2) if match else None,
        }
        row.update(_trajectory_shape(task_dir))
        row["failure_mode"] = _failure_mode(row)
        rows.append(row)
    return rows


def _summarise(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    print(f"=== {run_dir.name}  ({len(rows)} tasks)")
    exact = sum(1 for row in rows if row["exact"])
    usable = sum(1 for row in rows if row["usable"])
    workbooks = sum(1 for row in rows if row["has_workbook"])
    cost = sum(row["cost_usd"] or 0 for row in rows)
    print(
        f"  exact {exact}/{len(rows)}   usable(>= {USABLE_THRESHOLD}) {usable}/{len(rows)}   "
        f"workbooks {workbooks}/{len(rows)}   ${cost:.4f}"
    )
    by_category: dict[str, Counter] = {}
    for row in rows:
        by_category.setdefault(row["category"], Counter())[row["failure_mode"]] += 1
    for category, counter in sorted(by_category.items()):
        modes = "  ".join(f"{mode}={count}" for mode, count in counter.most_common())
        print(f"  {category}: {modes}")
    shapes = Counter(row.get("tool_sequence") or "(none)" for row in rows)
    print("  most common trajectory shapes:")
    for shape, count in shapes.most_common(3):
        print(f"    {count:>3}x  {shape[:110]}")


def _compare(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]) -> None:
    by_task_a = {row["task"]: row for row in rows_a}
    by_task_b = {row["task"]: row for row in rows_b}
    name_a = rows_a[0]["run"] if rows_a else "A"
    name_b = rows_b[0]["run"] if rows_b else "B"
    print(f"=== {name_a}  ->  {name_b}")
    for task in sorted(set(by_task_a) | set(by_task_b)):
        a = by_task_a.get(task, {})
        b = by_task_b.get(task, {})
        def fmt(row: dict[str, Any]) -> str:
            if not row:
                return "absent"
            if not row.get("has_workbook"):
                return f"no workbook ({row.get('failure_mode')})"
            return (
                f"reg={row.get('regression'):.4f} mod={row.get('modification'):.4f} "
                f"[{row.get('failure_mode')}]"
            )
        changed = (
            a.get("regression") != b.get("regression")
            or a.get("modification") != b.get("modification")
            or a.get("has_workbook") != b.get("has_workbook")
        )
        print(f"  {'*' if changed else ' '} {task:<24} {fmt(a):<44} -> {fmt(b)}")


def main() -> int:
    args = _arguments()
    all_rows: list[dict[str, Any]] = []
    per_run: list[tuple[Path, list[dict[str, Any]]]] = []
    for name in args.run:
        run_dir = args.runs_dir / name
        if not run_dir.is_dir():
            print(f"no such run: {name}", file=sys.stderr)
            return 1
        rows = collect(run_dir)
        per_run.append((run_dir, rows))
        all_rows.extend(rows)

    if args.compare and len(per_run) >= 2:
        _compare(per_run[0][1], per_run[1][1])
    else:
        for run_dir, rows in per_run:
            _summarise(run_dir, rows)
            print()

    if args.jsonl:
        args.jsonl.write_text("\n".join(json.dumps(row) for row in all_rows) + "\n")
        print(f"rows written to {args.jsonl}")
    if args.csv and all_rows:
        with args.csv.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"rows written to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
