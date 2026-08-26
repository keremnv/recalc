#!/usr/bin/env python3
"""Run a mixed-category slice with the frozen K2.7 cheap-compiler overlays.

Template and Financial Model use formula-patterns-v1. Debugging uses
formula-anomalies-v1 plus the read-budget instrument. Both groups use
formula-blocks-v1. Task failures do not skip the rest of the slice.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "benchmark" / "run_openrouter_slice.py"
DEFAULT_MODEL = "moonshotai/kimi-k2.7-code"
NONVISUAL = ("Template", "Financial_Model", "Debugging")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cost-limit", type=float, default=2.0)
    parser.add_argument("--call-limit", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--task",
        action="append",
        help="Run only CATEGORY:ID; repeat for multiple tasks. Defaults to the whole slice.",
    )
    return parser.parse_args()


def _load_tasks(slice_path: Path, filters: list[str] | None) -> list[dict[str, str]]:
    payload = json.loads(slice_path.read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    unknown = sorted({task["category"] for task in tasks} - set(NONVISUAL))
    if unknown:
        raise ValueError(f"frozen K2.7 runner is non-visual only; got {unknown}")
    if not filters:
        return tasks
    requested = set(filters)
    selected = [task for task in tasks if f"{task['category']}:{task['id']}" in requested]
    found = {f"{task['category']}:{task['id']}" for task in selected}
    missing = requested - found
    if missing:
        raise ValueError(f"Tasks are not in the slice: {', '.join(sorted(missing))}")
    return selected


def _group(tasks: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    compute = [
        f"{task['category']}:{task['id']}"
        for task in tasks
        if task["category"] != "Debugging"
    ]
    debugging = [
        f"{task['category']}:{task['id']}"
        for task in tasks
        if task["category"] == "Debugging"
    ]
    return compute, debugging


def _run_group(
    *,
    args: argparse.Namespace,
    observation: str,
    labels: list[str],
) -> int:
    if not labels:
        return 0
    command = [
        sys.executable,
        str(RUNNER),
        "--slice",
        str(args.slice.resolve()),
        "--run-name",
        args.run_name,
        "--model",
        args.model,
        "--observation",
        observation,
        "--execution",
        "formula-blocks-v1",
        "--read-policy",
        "progressive",
        "--cost-limit",
        str(args.cost_limit),
        "--call-limit",
        str(args.call_limit),
        "--max-requeries",
        "2",
        "--reasoning-effort",
        "low",
        "--timeout",
        str(args.timeout),
    ]
    if observation == "formula-anomalies-v1":
        command.append("--read-budget")
    if args.skip_existing:
        command.append("--skip-existing")
    for label in labels:
        command.extend(["--task", label])
    print(f"GROUP observation={observation} tasks={len(labels)}", flush=True)
    return subprocess.call(command, cwd=PROJECT_ROOT)


def main() -> int:
    args = _arguments()
    compute, debugging = _group(_load_tasks(args.slice, args.task))
    failures = 0
    failures += 1 if _run_group(args=args, observation="formula-patterns-v1", labels=compute) else 0
    failures += 1 if _run_group(args=args, observation="formula-anomalies-v1", labels=debugging) else 0
    print(f"FROZEN-SUMMARY groups_failed={failures} run={args.run_name}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
