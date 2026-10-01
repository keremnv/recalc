#!/usr/bin/env python3
"""Gold-blind first-miss census of a stored LibreCalc run.

Reads official_scores.json and trajectories only. Does not open goldens.
Autopsy v2: inspect names include boundary_continuations; a failed oversize
read does not count as attending the cell.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

from paired_autopsy import (
    RUNS_DIR,
    _first_miss,
    _input_kind,
    _load_steps,
    _nuance,
    _split_address,
    autopsy_trajectory,
)

FORMULA_EQ = re.compile(r"answer==(.*), output==(.*)$")
NUM = re.compile(r"answer=(.*), output=(.*)$")
ERR_TOKENS = {"#NAME?", "#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NULL!", "#NUM!"}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--json", type=Path, required=True)
    return parser.parse_args()


def _parse_num(text: str) -> float | str | None:
    text = text.strip()
    if text in {"None", "none", ""}:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def value_shape(message: str) -> str:
    """Classify the evaluator leak in error_message. Not a golden."""

    if not message:
        return "no_message"
    match = FORMULA_EQ.search(message)
    if match:
        return "formula_text"
    match = NUM.search(message)
    if match is None:
        return "other"
    answer, output = match.group(1).strip(), match.group(2).strip()
    if answer in ERR_TOKENS or output in ERR_TOKENS:
        return "error_token"
    answer_n, output_n = _parse_num(answer), _parse_num(output)
    if output_n is None and isinstance(answer_n, float):
        return "output_none"
    if answer_n is None and isinstance(output_n, float):
        return "answer_none"
    if isinstance(answer_n, float) and isinstance(output_n, float):
        if answer_n == 0 and output_n != 0:
            return "answer0_output_nz"
        if output_n == 0 and answer_n != 0:
            return "answer_nz_output0"
        if (
            answer_n != 0
            and output_n != 0
            and math.isclose(abs(answer_n), abs(output_n), rel_tol=1e-6, abs_tol=1e-6)
            and (answer_n > 0) != (output_n > 0)
        ):
            return "sign_flip"
        if math.isclose(answer_n, output_n, rel_tol=1e-4, abs_tol=1e-4):
            return "near_equal_value"
        return "magnitude"
    return "other"


def census_run(run_dir: Path) -> dict[str, Any]:
    scores = json.loads((run_dir / "official_scores.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for task, score in (scores.get("tasks") or {}).items():
        category, _, task_id = task.partition(":")
        kind, address = _first_miss(score)
        row: dict[str, Any] = {
            "task": task,
            "category": category,
            "id": task_id,
            "exact": bool(score.get("accuracy")),
            "mod": score.get("modification_accuracy"),
            "reg": score.get("regression_accuracy"),
            "miss_kind": kind,
            "address": address,
            "error_message": score.get("error_message") or "",
            "value_shape": value_shape(score.get("error_message") or ""),
        }
        if address is None:
            row.update(
                {
                    "bucket": "exact" if row["exact"] else "no_first_miss",
                    "input_kind": "n/a",
                    "named": False,
                    "named_sources": [],
                    "read": False,
                    "read_attempted": False,
                    "written": False,
                    "drowned": False,
                    "named_rank": None,
                    "selected_count": 0,
                    "error_cell_count": 0,
                    "nuance": "exact" if row["exact"] else "no_first_miss",
                }
            )
        else:
            steps = _load_steps(run_dir, task)
            view = autopsy_trajectory(steps, address)
            sheet, cell = _split_address(address)
            input_kind = _input_kind(category, task_id, sheet, cell)
            row.update(
                {
                    "bucket": view["bucket"],
                    "input_kind": input_kind,
                    "named": view["named"],
                    "named_sources": view.get("named_sources") or [],
                    "read": view["read"],
                    "read_attempted": view.get("read_attempted") or False,
                    "written": view["written"],
                    "drowned": view["drowned"],
                    "named_rank": view["named_rank"],
                    "selected_count": view["selected_count"],
                    "error_cell_count": view["error_cell_count"],
                    "nuance": _nuance(view, input_kind),
                }
            )
        rows.append(row)
    return {
        "run": run_dir.name,
        "autopsy": "v2-boundary-and-successful-read",
        "scored": len(rows),
        "exact": sum(1 for row in rows if row["exact"]),
        "buckets": dict(Counter(row["bucket"] for row in rows)),
        "nuance": dict(Counter(row["nuance"] for row in rows)),
        "value_shape": dict(Counter(row["value_shape"] for row in rows)),
        "tasks": rows,
    }


def main() -> int:
    args = _arguments()
    payload = census_run(args.runs_dir / args.run)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"wrote {args.json} n={payload['scored']} exact={payload['exact']}")
    print("buckets:", payload["buckets"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
