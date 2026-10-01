#!/usr/bin/env python3
"""Apply the METHOD v2 gate to the pattern catalog. Gold-blind, no new inference runs.

A pattern earns a design change only when it survives four questions, asked in this
order because each one is cheaper to answer than the next is to act on:

1. **Self-stability.** Do *our own* repeat runs get that cell right sometimes? The
   measured n=4 swing on this model is exact <-> 0.9854 on one task, so a cell we
   win on repeat is variance, not a pattern.
2. **Arm delta.** Does the control arm get that cell right? A cell both arms miss is
   a property of the model or the task. Only `induced` (control right, we wrong) and
   `recovered` (we right, control wrong) carry information about the interface.
3. **Distance to exact.** How many misses does the case's task still carry? Fixing a
   first miss on a task with thirty of them converts nothing.
4. **Lever.** Which family would the fix belong to? `information` has been measured
   four times and has never converted an exact on this model.

Everything here reads the evaluator's own first-miss line (`answer=` is an evaluator
leak, already allowed by METHOD.md) plus arm output workbooks at that one address.
No golden is opened, and `min_mod_misses` is recovered from the published accuracy
scalar rather than from any answer-position dump.

    python benchmark/catalog_gate.py
    python benchmark/catalog_gate.py --json /tmp/gate.json --near 3
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

from paired_autopsy import RUNS_DIR
from pattern_catalog import CATALOG, load_cases, load_surface

ARMS = CATALOG / "arms.yaml"
_MISS_LINE = re.compile(
    r"^(Modification|Regression) error at (?P<address>.+?): (?P<body>answer=.*)$"
)
_REL_TOL = 1e-6
_ABS_TOL = 1e-9

# Verdicts, worst-first. The first one that applies wins.
NOISE = "noise"
SHARED = "shared"
UNJUDGED = "unjudged"
FAR = "far"
REFUTED_LEVER = "refuted-lever"
SURVIVES = "survives"


def load_arms(path: Path = ARMS) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def split_address(address: str) -> tuple[str, str]:
    """`Ex 1 - LBO!C11` -> (`Ex 1 - LBO`, `C11`). Sheet names may contain anything."""

    sheet, _, cell = address.rpartition("!")
    return sheet, cell.upper()


def parse_answer(error_message: str) -> str | None:
    """The golden value the evaluator printed for the first miss. `None` if absent."""

    match = _MISS_LINE.match((error_message or "").strip())
    if match is None:
        return None
    body = match.group("body")
    answer, sep, _output = body.rpartition(", output=")
    if not sep:
        return None
    return answer[len("answer=") :]


def values_agree(answer: str, cached: Any) -> bool:
    if cached is None:
        return False
    try:
        return math.isclose(float(answer), float(cached), rel_tol=_REL_TOL, abs_tol=_ABS_TOL)
    except (TypeError, ValueError):
        pass
    return str(answer).strip().casefold() == str(cached).strip().casefold()


def min_misses(accuracy: float | None, max_denominator: int = 4000) -> int | None:
    """Smallest miss count consistent with a 4dp accuracy scalar.

    The evaluator publishes `matched / total` rounded to four places. The true total is
    unknown, but every consistent fraction is a multiple of the smallest one, so the
    smallest denominator gives a **lower bound** on the misses. That is exactly the
    right shape for a distance filter: a lower bound above the threshold is decisive,
    and a lower bound of one leaves the case in play.

    The bound is weak where the smallest consistent denominator is small -- 0.5 reads as
    one miss in two whether or not it was fifty in a hundred. Since the gate only ever
    *rejects* on this number, a weak bound costs coverage and never invents a `far`.
    """

    if accuracy is None:
        return None
    for denominator in range(1, max_denominator + 1):
        numerator = round(accuracy * denominator)
        if 0 <= numerator <= denominator and round(numerator / denominator, 4) == round(
            accuracy, 4
        ):
            return denominator - numerator
    return None


def _scores(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "official_scores.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["tasks"]


def _output_path(run_dir: Path, task: str) -> Path:
    category, _, task_id = task.partition(":")
    return run_dir / "submission" / "outputs" / category / f"{task_id}_output.xlsx"


def _blank_is_decidable(answer: str) -> bool:
    """A blank output cell is a miss unless the wanted answer is itself blank or zero."""

    text = str(answer).strip()
    if text == "":
        return False
    try:
        return float(text) != 0.0
    except ValueError:
        return True


def cell_verdict(run_dir: Path, task: str, address: str, answer: str) -> str:
    """One arm's fate at one cell.

    `right` / `wrong` are decided. `no-output`, `no-sheet`, `no-cache` and `blank-vs-zero`
    are not, and are excluded from every count. `no-cache` matters: a workbook saved
    without cached values reads as all-`None`, and calling that a miss everywhere would
    manufacture agreement out of an artifact, so the whole sheet is checked first.
    """

    path = _output_path(run_dir, task)
    if not path.is_file():
        return "no-output"
    sheet, cell = split_address(address)
    try:
        workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:  # noqa: BLE001 -- a workbook we cannot open decides nothing
        return "no-output"
    try:
        if sheet not in workbook.sheetnames:
            return "no-sheet"
        worksheet = workbook[sheet]
        cached = worksheet[cell].value
        if cached is None:
            has_any_cache = any(
                value is not None for row in worksheet.iter_rows(values_only=True) for value in row
            )
            if not has_any_cache:
                return "no-cache"
            return "wrong" if _blank_is_decidable(answer) else "blank-vs-zero"
    except Exception:  # noqa: BLE001 -- a cell we cannot reach decides nothing
        return "no-sheet"
    finally:
        workbook.close()
    return "right" if values_agree(answer, cached) else "wrong"


def _tally(runs: list[str], runs_dir: Path, task: str, address: str, answer: str) -> dict[str, Any]:
    per_run: dict[str, str] = {}
    for name in runs:
        run_dir = runs_dir / name
        scores = _scores(run_dir)
        if scores is None or task not in scores:
            continue
        per_run[name] = cell_verdict(run_dir, task, address, answer)
    decided = [v for v in per_run.values() if v in ("right", "wrong")]
    return {
        "per_run": per_run,
        "covered": len(per_run),
        "decided": len(decided),
        "right": sum(1 for v in decided if v == "right"),
    }


def judge_case(
    case: dict[str, Any], arms: dict[str, Any], runs_dir: Path, near: int, min_decided: int = 2
) -> dict[str, Any]:
    task = case["task"]
    first_miss = case.get("first_miss") or {}
    address = first_miss.get("address")
    answer = parse_answer(first_miss.get("error_message") or "")
    claims = case.get("claims") or {}
    own_run = case["run"]

    row: dict[str, Any] = {
        "case": case["id"],
        "task": task,
        "address": address,
        "run": own_run,
        "patterns": claims.get("patterns") or [],
        "lever": claims.get("lever", "unset"),
        "mechanism": claims.get("mechanism", "unset"),
    }

    scores = _scores(runs_dir / own_run) or {}
    score = scores.get(task) or {}
    mod_misses = min_misses(score.get("modification_accuracy"))
    reg_misses = min_misses(score.get("regression_accuracy"))
    total = None if mod_misses is None or reg_misses is None else mod_misses + reg_misses
    row["distance"] = {
        "mod": score.get("modification_accuracy"),
        "reg": score.get("regression_accuracy"),
        "min_mod_misses": mod_misses,
        "min_reg_misses": reg_misses,
        "min_total_misses": total,
    }

    if answer is None:
        row["arm_delta"] = "no-leak"
        row["verdict"] = UNJUDGED
        row["why"] = "first-miss line carries no answer= value"
        return row

    peers = [name for name in arms.get("ours") or [] if name != own_run]
    row["self"] = _tally(peers, runs_dir, task, address, answer)
    row["control"] = _tally(arms.get("control") or [], runs_dir, task, address, answer)

    if row["self"]["decided"] >= min_decided and row["self"]["right"]:
        row["arm_delta"] = "self-unstable"
        row["verdict"] = NOISE
        row["why"] = (
            f"our own arm got {address} right in "
            f"{row['self']['right']}/{row['self']['decided']} other runs"
        )
        return row

    if row["control"]["decided"] < min_decided:
        row["arm_delta"] = "no-control"
        row["verdict"] = UNJUDGED
        row["why"] = f"control decided on {row['control']['decided']} run(s), need {min_decided}"
        return row

    if row["control"]["right"] == 0:
        row["arm_delta"] = "shared"
        row["verdict"] = SHARED
        row["why"] = f"control missed {address} in all {row['control']['decided']} runs too"
        return row

    row["arm_delta"] = "induced"
    if total is not None and total > near:
        row["verdict"] = FAR
        row["why"] = f"task still carries at least {total} misses (threshold {near})"
        return row
    if arms.get("levers", {}).get(row["lever"]) == "refuted":
        row["verdict"] = REFUTED_LEVER
        row["why"] = f"lever `{row['lever']}` has been measured and never converted"
        return row
    row["verdict"] = SURVIVES
    row["why"] = (
        f"control got {address} right in {row['control']['right']}/"
        f"{row['control']['decided']} runs and the task is within {near} misses"
    )
    return row


def roll_up(rows: list[dict[str, Any]], surface: dict[str, Any]) -> list[dict[str, Any]]:
    by_case = {row["case"]: row for row in rows}
    out = []
    for pattern in surface.get("patterns") or []:
        verdicts = [
            by_case[cid]["verdict"]
            for cid in pattern.get("establishing_cases") or []
            if cid in by_case
        ]
        out.append(
            {
                "id": pattern["id"],
                "status": pattern.get("status"),
                "design": pattern.get("design"),
                "cases": len(verdicts),
                "verdicts": verdicts,
                "survives": SURVIVES in verdicts,
            }
        )
    return out


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--arms", type=Path, default=ARMS)
    parser.add_argument(
        "--near",
        type=int,
        default=3,
        help="max misses remaining for a case to count as reachable (default 3)",
    )
    parser.add_argument(
        "--min-decided",
        type=int,
        default=2,
        help="runs an arm must decide before its agreement counts (default 2)",
    )
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    arms = load_arms(args.arms)
    surface = load_surface()
    rows = [
        judge_case(case, arms, args.runs_dir, args.near, args.min_decided) for case in load_cases()
    ]

    width = max(len(row["case"]) for row in rows)
    print(f"{'case':{width}}  {'arm_delta':13} {'dist':>5}  {'lever':13} {'verdict':13} why")
    for row in sorted(rows, key=lambda r: (r["verdict"] != SURVIVES, r["case"])):
        distance = row["distance"]["min_total_misses"]
        print(
            f"{row['case']:{width}}  {row.get('arm_delta', '-'):13} "
            f"{('-' if distance is None else distance):>5}  "
            f"{row['lever']:13} {row['verdict']:13} {row['why']}"
        )

    print()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    print("cases: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    print()
    patterns = roll_up(rows, surface)
    print(f"{'pattern':26} {'status':12} {'design':6} verdicts")
    for pattern in patterns:
        mark = "*" if pattern["survives"] else " "
        print(
            f"{mark}{pattern['id']:25} {pattern['status']!s:12} "
            f"{pattern['design']!s:6} {', '.join(pattern['verdicts']) or '(no cases)'}"
        )
    survivors = [p["id"] for p in patterns if p["survives"]]
    print()
    print(
        f"patterns surviving the gate: {len(survivors)}/{len(patterns)}"
        + (" -- " + ", ".join(survivors) if survivors else "")
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "near": args.near,
                    "min_decided": args.min_decided,
                    "cases": rows,
                    "patterns": patterns,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
