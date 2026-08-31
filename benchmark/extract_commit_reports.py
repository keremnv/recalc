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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
_PAYLOAD = re.compile(r'\{"ok":false,"schema":"commit-checks-v1".*?\}(?=\s*$|\n)', re.DOTALL)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--run", action="append", help="Restrict to these run names.")
    parser.add_argument("--json", type=Path, help="Write the recovered reports here.")
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
    if args.json:
        args.json.write_text(json.dumps(recovered, indent=2))
        print(f"detail written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
