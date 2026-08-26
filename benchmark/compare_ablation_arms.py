#!/usr/bin/env python3
"""Tabulate interface ablation arms from their run ledgers.

A -> B isolates observation richness; B -> C isolates one-call program execution.
Reports the resource the arms actually share -- a dollar cap -- alongside the
round trips and tokens each interface needed to reach its result.

Usage:
    uv run python benchmark/compare_ablation_arms.py RUN_DIR [RUN_DIR ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ARM_BY_CONFIG = {
    ("grid-v1", "thin", "cell-writes-v1"): "A  thin",
    ("formula-patterns-v1", "progressive", "cell-writes-v1"): "B  semantic",
    ("formula-patterns-v1", "progressive", "formula-blocks-v1"): "C  semantic+program",
    ("formula-patterns-v1", "progressive", "semantic-program-v1"): "C  semantic+program",
}


def _rows(run_dir: Path) -> list[dict]:
    ledger = run_dir / "ledger.jsonl"
    if not ledger.is_file():
        return []
    merged: dict[str, dict] = {}
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        # Scoring appends a second row per task; later rows win.
        merged.setdefault(record["task"], {}).update(record)
    return list(merged.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="+", type=Path)
    args = parser.parse_args()

    header = (
        f"{'arm':22} {'task':26} {'exact':>6} {'reg':>7} {'mod':>7} "
        f"{'$':>9} {'calls':>6} {'tools':>6} {'prompt tok':>11} {'sec':>7}"
    )
    print(header)
    print("-" * len(header))
    totals: dict[str, dict[str, float]] = {}
    for run_dir in args.run_dirs:
        for row in _rows(run_dir):
            arm = ARM_BY_CONFIG.get(
                (
                    row.get("observation_variant"),
                    row.get("read_policy"),
                    row.get("execution_variant"),
                ),
                "?",
            )
            exact = row.get("exact_success")
            print(
                f"{arm:22} {row.get('task', ''):26} "
                f"{('yes' if exact else 'no' if exact is not None else '-'):>6} "
                f"{_fmt(row.get('regression_accuracy')):>7} "
                f"{_fmt(row.get('modification_accuracy')):>7} "
                f"{row.get('charged_cost_usd', 0):>9.4f} "
                f"{row.get('model_calls', 0):>6} {row.get('tool_calls', 0):>6} "
                f"{row.get('prompt_tokens', 0):>11,} "
                f"{row.get('elapsed_seconds', 0):>7.0f}"
            )
            bucket = totals.setdefault(arm, {"usd": 0.0, "calls": 0, "exact": 0, "n": 0})
            bucket["usd"] += row.get("charged_cost_usd", 0) or 0
            bucket["calls"] += row.get("model_calls", 0) or 0
            bucket["exact"] += 1 if exact else 0
            bucket["n"] += 1

    print()
    print(f"{'arm':22} {'exact':>8} {'total $':>10} {'total calls':>12}")
    print("-" * 54)
    for arm in sorted(totals):
        bucket = totals[arm]
        print(
            f"{arm:22} {int(bucket['exact'])}/{int(bucket['n']):<6} "
            f"{bucket['usd']:>10.4f} {int(bucket['calls']):>12}"
        )
    return 0


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
