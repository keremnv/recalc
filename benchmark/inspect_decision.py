#!/usr/bin/env python3
"""Stand where the model stood at the moment it went wrong.

Given a run, a task and the address the evaluator names as the first miss, find the step whose
action touches that cell and print three things: what the model had just been shown, what it
said it was doing, and what it then did. That is the whole method -- reading the observation
that preceded a bad write is what exposed the `regions` bounding box behind the Template
overfills.

Nothing here is model-specific or task-specific, and no golden data is read; the miss address
comes from the evaluator's own message, which is already in official_scores.json.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
_MISS = re.compile(r"^(Regression|Modification) error at (.+?): answer=", re.IGNORECASE)
_A1 = re.compile(r"^([A-Za-z]+)([0-9]+)$")
# A read that happens to span the cell is not the wrong call; a write is.
_WRITE_TOOLS = ("calc_write", "calc_fill_formulas", "calc_program", "calc_upsert_chart")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--task", help="CATEGORY:ID. Default: every non-exact task in the run.")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--context", type=int, default=420, help="Characters of surrounding text.")
    parser.add_argument("--thoughts", action="store_true", help="Include the model's reasoning.")
    return parser.parse_args()


def _decode(action: str) -> str:
    """Tool arguments arrive percent-encoded; decode so addresses are greppable."""
    parts = []
    for token in action.split():
        if token.startswith(("%5B", "%7B")):
            try:
                parts.append(urllib.parse.unquote(token))
                continue
            except (ValueError, UnicodeDecodeError):
                pass
        parts.append(token)
    return " ".join(parts)


def _covers(decoded: str, sheet: str, address: str) -> bool:
    """Whether an action names the cell, or a range whose rectangle contains it."""
    if address in decoded:
        return True
    match = _A1.match(address)
    if match is None:
        return False
    column, row = match.group(1).upper(), int(match.group(2))
    column_number = 0
    for character in column:
        column_number = column_number * 26 + (ord(character) - 64)
    for start_col, start_row, end_col, end_row in re.findall(
        r"([A-Z]+)([0-9]+):([A-Z]+)([0-9]+)", decoded.upper()
    ):
        def number(label: str) -> int:
            value = 0
            for character in label:
                value = value * 26 + (ord(character) - 64)
            return value

        if (
            number(start_col) <= column_number <= number(end_col)
            and int(start_row) <= row <= int(end_row)
        ):
            return True
    return False


def examine(run_dir: Path, task: str, address: str, context: int, thoughts: bool) -> None:
    category, _, task_id = task.partition(":")
    sheet, _, cell = address.rpartition("!")
    trajectories = sorted((run_dir / f"{category}-{task_id}").glob("trajectory/*/*.traj"))
    if not trajectories:
        print(f"  no trajectory for {task}")
        return
    steps = json.loads(trajectories[-1].read_text(encoding="utf-8")).get("trajectory", [])

    print(f"--- {task}   first miss {address}")
    candidates = []
    for index, step in enumerate(steps):
        decoded = _decode((step.get("action") or "").strip())
        if not decoded or not _covers(decoded, sheet, cell):
            continue
        candidates.append((index, step, decoded))
    writes = [c for c in candidates if c[2].split()[0] in _WRITE_TOOLS]
    chosen = writes[:1] or candidates[:1]
    hit = bool(chosen)
    for index, step, decoded in chosen:
        print(f"  step {index}: {decoded[:240]}")
        if thoughts and step.get("thought"):
            print(f"    THOUGHT: {' '.join(str(step['thought']).split())[:400]}")
        prior = steps[index - 1].get("observation") if index else None
        if isinstance(prior, str):
            where = prior.find(cell)
            if where == -1 and sheet:
                where = prior.find(sheet)
            if where != -1:
                start = max(0, where - context)
                snippet = " ".join(prior[start : where + context].split())
                print(f"    SHOWN BEFORE: ...{snippet}...")
            else:
                print(
                    f"    SHOWN BEFORE: (cell absent from the prior observation, "
                    f"{len(prior)} chars)"
                )
    if not hit:
        print("  no action names or covers that cell (the write may be a fill translation)")


def main() -> int:
    args = _arguments()
    run_dir = args.runs_dir / args.run
    scores_path = run_dir / "official_scores.json"
    if not scores_path.is_file():
        print(f"no official_scores.json in {run_dir}")
        return 1
    tasks: dict[str, Any] = json.loads(scores_path.read_text(encoding="utf-8"))["tasks"]

    selected = [args.task] if args.task else sorted(tasks)
    for task in selected:
        score = tasks.get(task)
        if score is None or score.get("accuracy"):
            continue
        match = _MISS.match(score.get("error_message") or "")
        if match is None:
            continue
        examine(run_dir, task, match.group(2), args.context, args.thoughts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
