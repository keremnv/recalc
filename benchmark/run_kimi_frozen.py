#!/usr/bin/env python3
"""Run a mixed-category slice with the frozen K2.7 cheap-compiler overlays.

Template and Financial Model use formula-patterns-v1. Debugging defaults to
formula-anomalies-v1 plus the read-budget instrument. Both groups default to
formula-blocks-v1. The isolated format arm switches Debugging to
format-conventions-v1 and semantic-program-v1. Task failures do not skip the
rest of the slice.
After both groups finish, this scores the run in-process (LibreOffice refresh plus
unmodified evaluation.py) so logs, workbooks, and official JSON come from one command.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "benchmark" / "run_openrouter_slice.py"
SCORER = PROJECT_ROOT / "benchmark" / "score_openrouter_run.py"
DEFAULT_MODEL = "moonshotai/kimi-k2.7-code"
DEFAULT_RUNS = (
    PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "benchmark-runs" / "openrouter"
)
NONVISUAL = ("Template", "Financial_Model", "Debugging")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cost-limit", type=float, default=2.0)
    parser.add_argument("--call-limit", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh", "max"),
        default="low",
        help="Forwarded to the OpenRouter runner. K2.7 stays low; Sol's measured write path used medium.",
    )
    parser.add_argument(
        "--provider-only",
        action="append",
        help=(
            "Restrict OpenRouter to this provider slug; repeat to allow more than one. "
            "Diagnostic control only; disables provider fallbacks."
        ),
    )
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Expose bash/view_xlsx alongside all LibreCalc tools for the optional-ISA arm.",
    )
    parser.add_argument(
        "--unbounded-reads",
        action="store_true",
        help="Remove the read ceiling and post-inspect read budget in both category groups.",
    )
    parser.add_argument(
        "--compute-execution",
        choices=("formula-blocks-v1", "semantic-program-v1"),
        default="formula-blocks-v1",
        help="Template/Financial Model execution surface; default preserves the frozen 297 arm.",
    )
    parser.add_argument(
        "--debug-execution",
        choices=("formula-blocks-v1", "semantic-program-v1"),
        default="formula-blocks-v1",
        help="Explicit Debugging ablation; semantic-program exposes structural and format ops.",
    )
    parser.add_argument(
        "--debug-observation",
        choices=("formula-anomalies-v1", "format-conventions-v1"),
        default="formula-anomalies-v1",
        help=(
            "Explicit Debugging ablation. format-conventions-v1 is a gold-blind font-color "
            "census and requires --debug-execution semantic-program-v1."
        ),
    )
    parser.add_argument(
        "--debug-repair-passes",
        type=int,
        choices=(1, 2),
        default=1,
        help="Explicit Debugging ablation allowing one bounded output re-inspection.",
    )
    parser.add_argument(
        "--preserve-populated",
        action="store_true",
        help=(
            "Forward --preserve-populated to Template/Financial Model only. "
            "Never applied to Debugging."
        ),
    )
    parser.add_argument(
        "--commit-gate",
        action="store_true",
        help=(
            "Two-phase submit carrying the checks that cleared the offline gate. "
            "Forwarded to Debugging only; never the 297 default."
        ),
    )
    parser.add_argument(
        "--compute-read-budget",
        action="store_true",
        help=(
            "Forward --compute-read-budget to Template/Financial Model only. "
            "Write-commit experiment; never the 297 default."
        ),
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Skip the in-run official eval pack. Default is to score after inference.",
    )
    parser.add_argument(
        "--task",
        action="append",
        help="Run only CATEGORY:ID; repeat for multiple tasks. Defaults to the whole slice.",
    )
    return parser.parse_args()


def _safe_name(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_." else "-" for character in value
    )
    return cleaned.strip("-.")


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
        f"{task['category']}:{task['id']}" for task in tasks if task["category"] != "Debugging"
    ]
    debugging = [
        f"{task['category']}:{task['id']}" for task in tasks if task["category"] == "Debugging"
    ]
    return compute, debugging


def _run_group(
    *,
    args: argparse.Namespace,
    observation: str,
    labels: list[str],
    debugging: bool,
) -> int:
    if not labels:
        return 0
    if args.hybrid:
        execution = "semantic-program-v1"
    elif debugging:
        execution = args.debug_execution
    else:
        execution = args.compute_execution
    repair_passes = args.debug_repair_passes if debugging else 1
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
        execution,
        "--read-policy",
        "progressive",
        "--cost-limit",
        str(args.cost_limit),
        "--call-limit",
        str(args.call_limit),
        "--max-requeries",
        "2",
        "--reasoning-effort",
        args.reasoning_effort,
        "--timeout",
        str(args.timeout),
        "--repair-passes",
        str(repair_passes),
    ]
    if debugging:
        if not args.unbounded_reads:
            command.append("--read-budget")
        # The three checks that cleared the offline gate were all measured on Debugging
        # output, and broken_check_cell is worthless outside repair tasks.
        if args.commit_gate:
            command.append("--commit-gate")
    else:
        if args.preserve_populated:
            command.append("--preserve-populated")
        if args.compute_read_budget:
            command.append("--compute-read-budget")
    if args.hybrid:
        command.append("--hybrid")
    if args.unbounded_reads:
        command.append("--unbounded-reads")
    if args.skip_existing:
        command.append("--skip-existing")
    for provider in args.provider_only or []:
        command.extend(["--provider-only", provider])
    command.append("--no-score")
    for label in labels:
        command.extend(["--task", label])
    print(f"GROUP observation={observation} tasks={len(labels)}", flush=True)
    return subprocess.call(command, cwd=PROJECT_ROOT)


def _score_run(run_name: str) -> int:
    run_root = DEFAULT_RUNS / _safe_name(run_name)
    command = [
        sys.executable,
        str(SCORER),
        str(run_root),
        "--write-ledger",
    ]
    print(f"SCORE {run_root}", flush=True)
    return subprocess.call(command, cwd=PROJECT_ROOT)


def main() -> int:
    args = _arguments()
    if (
        args.debug_observation == "format-conventions-v1"
        and args.debug_execution != "semantic-program-v1"
    ):
        raise ValueError("format-conventions-v1 requires --debug-execution semantic-program-v1")
    compute, debugging = _group(_load_tasks(args.slice, args.task))
    failures = 0
    failures += (
        1
        if _run_group(
            args=args,
            observation="formula-patterns-v1",
            labels=compute,
            debugging=False,
        )
        else 0
    )
    failures += (
        1
        if _run_group(
            args=args,
            observation=args.debug_observation,
            labels=debugging,
            debugging=True,
        )
        else 0
    )
    score_status = 0 if args.no_score else _score_run(args.run_name)
    print(
        f"FROZEN-SUMMARY groups_failed={failures} score_failed={score_status} run={args.run_name}",
        flush=True,
    )
    return 1 if failures or score_status else 0


if __name__ == "__main__":
    raise SystemExit(main())
