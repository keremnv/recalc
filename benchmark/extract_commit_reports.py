#!/usr/bin/env python3
"""Recover the gate's live findings from stored trajectories.

The report is emitted as a tool observation, so the trajectory is the durable record -- the
output mount it is also written to is a temporary directory the harness discards. These are the
only *live* findings: the offline replay in characterize_commit_checks.py reads openpyxl caches
while the gate reads through UNO with recalculation, and the two disagree (Debugging 07_01: 94
broken_check_cell findings offline, none live). Score precision from these, not from replay.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

RUNS_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
DATA_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/data"
_PAYLOAD = re.compile(r'\{"ok":false,"schema":"commit-checks-v1".*?\}(?=\s*$|\n)', re.DOTALL)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--run", action="append", help="Restrict to these run names.")
    parser.add_argument("--json", type=Path, help="Write the recovered reports here.")
    parser.add_argument(
        "--score",
        action="store_true",
        help=(
            "Judge each recovered representative against the golden. Precision here is over "
            "the representatives the model actually saw, not over every finding the gate "
            "counted -- the report caps them at 8 a sheet and 80 overall."
        ),
    )
    return parser.parse_args()


def _reports_in(trajectory: Path) -> list[dict[str, Any]]:
    """Pull every commit-checks payload out of one trajectory's observations."""
    document = json.loads(trajectory.read_text(encoding="utf-8"))
    reports: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in document.get("trajectory", []):
        observation = step.get("observation")
        if not isinstance(observation, str) or "commit-checks-v1" not in observation:
            continue
        for match in _PAYLOAD.finditer(observation):
            raw = match.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            try:
                reports.append(json.loads(raw))
            except ValueError:
                continue
    return reports


def _score_live(recovered: list[dict[str, Any]]) -> Counter:
    """Judge the representatives the model was shown, using the offline verdict rule."""
    import characterize_commit_checks as cc

    datasets = cc._datasets()
    tally: Counter = Counter()
    for entry in recovered:
        category, _, task_id = entry["task"].partition("-")
        task = datasets.get((category, task_id))
        if task is None:
            tally["unmatched_task"] += 1
            continue
        try:
            before = cc._cell_map(DATA_DIR / category / task["spreadsheet_path"])
            golden = cc._cell_map(DATA_DIR / category / task["golden_response_path"])
        except Exception:  # noqa: BLE001 - a stored artifact may be unreadable
            tally["unreadable"] += 1
            continue
        for finding in entry["representatives"]:
            check = finding.get("check", "")
            verdict = cc.score_finding(
                check,
                finding.get("sheet", ""),
                finding.get("address", ""),
                finding.get("detail", ""),
                before,
                golden,
            )
            tally[f"{check}:{verdict}"] += 1
            tally[check] += 1
    return tally


def main() -> int:
    args = _arguments()
    run_dirs = sorted(d for d in args.runs_dir.iterdir() if d.is_dir())
    if args.run:
        wanted = set(args.run)
        run_dirs = [d for d in run_dirs if d.name in wanted]

    recovered: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        for task_dir in sorted(d for d in run_dir.iterdir() if d.is_dir()):
            for trajectory in sorted(task_dir.glob("trajectory/*/*.traj")):
                reports = _reports_in(trajectory)
                if not reports:
                    continue
                for report in reports:
                    checks = report.get("checks") or {}
                    recovered.append(
                        {
                            "run": run_dir.name,
                            "task": task_dir.name,
                            "finding_count": report.get("finding_count"),
                            "counts": {
                                name: entry.get("count") for name, entry in checks.items()
                            },
                            # Reports predating the bounded-representative change carry a
                            # flat "findings" list instead.
                            "representatives": [
                                finding
                                for entry in checks.values()
                                for finding in (
                                    entry.get("representatives") or entry.get("findings") or []
                                )
                            ],
                        }
                    )

    for entry in recovered:
        print(
            f"{entry['run']}  {entry['task']}  findings={entry['finding_count']}  "
            f"{entry['counts']}  representatives={len(entry['representatives'])}"
        )
    if not recovered:
        print("no commit-check reports found in the selected runs")
    if args.score and recovered:
        tally = _score_live(recovered)
        checks = sorted({name for name in tally if ":" not in name})
        print("\nlive precision over the representatives the model saw:")
        for check in checks:
            true_positive = tally[f"{check}:true_positive"]
            false_positive = tally[f"{check}:false_positive"]
            scored = true_positive + false_positive
            precision = f"{true_positive / scored:.1%}" if scored else "n/a"
            print(
                f"  {check}: {tally[check]} representatives, precision {precision} "
                f"(tp {true_positive} / fp {false_positive} / "
                f"unscorable {tally[f'{check}:unscorable']})"
            )
        for problem in ("unmatched_task", "unreadable"):
            if tally[problem]:
                print(f"  {problem}: {tally[problem]}")
    if args.json:
        args.json.write_text(json.dumps(recovered, indent=2))
        print(f"detail written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
