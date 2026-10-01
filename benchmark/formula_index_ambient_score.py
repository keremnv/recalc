"""Score the forced-exposure ambient-index diagnostic.

Primary proximal outcome: submitted fingerprint == golden fingerprint on
blank→formula targets. Goldens are used offline only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "benchmark"))

from ambient import parse_view_xlsx_action  # noqa: E402
from fingerprint import relative_fingerprint  # noqa: E402
from formula_index_score import (  # noqa: E402
    _find_trajectory,
    load_formulas,
    load_values,
    occupancy_targets,
    summarize,
)
from workbook import build_index  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()

from experiment_metrics import trajectory_metrics  # noqa: E402

RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
SLICE = ROOT / "benchmark/slices/fm-ambient-six.json"
_EQ = re.compile(r"\beq ([0-9a-f]{10})\b")
_FORMULA_LINE = re.compile(r"^  formula: (=.+)$", re.M)
_SOURCE_LINE = re.compile(r"^  visible_source: (\S+)$", re.M)
PRIMARY_STRATA = (
    "same_row_nonadjacent",
    "same_column_nonadjacent",
    "cross_sheet",
    "unrecoverable",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control_run")
    parser.add_argument("treatment_run")
    parser.add_argument("--runs-dir", type=Path, default=RUNS)
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def parse_ambient_trajectory(path: Path | None) -> dict[str, Any]:
    empty = {
        "content_inspections": 0,
        "ambient_emitted": False,
        "eq_ids": [],
        "formulas": [],
        "sources": [],
        "used_homologue": False,
        "model_calls": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "cost": None,
        "first_content_action": None,
    }
    if path is None or not path.is_file():
        return empty
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = trajectory_metrics(path)
    eq_ids: list[str] = []
    formulas: list[str] = []
    sources: list[str] = []
    content_inspections = 0
    first_content = None
    ambient_emitted = False
    later_actions: list[str] = []
    seen_index = False
    for step in data.get("trajectory", []):
        action = str(step.get("action") or "")
        observation = str(step.get("observation") or "")
        parsed = parse_view_xlsx_action(action)
        if parsed is not None and parsed.mode == "content":
            content_inspections += 1
            if first_content is None:
                first_content = action
        if "STRUCTURAL INDEX" in observation:
            ambient_emitted = True
            seen_index = True
            eq_ids.extend(_EQ.findall(observation))
            formulas.extend(_FORMULA_LINE.findall(observation))
            sources.extend(_SOURCE_LINE.findall(observation))
        elif seen_index:
            later_actions.append(action)
    used = False
    blob = "\n".join(later_actions)
    for formula in formulas:
        if formula and formula in blob:
            used = True
            break
    if not used:
        for source in sources:
            cell = source.split("!", 1)[-1]
            if source in blob or (cell and cell in blob):
                used = True
                break
    return {
        "content_inspections": content_inspections,
        "ambient_emitted": ambient_emitted,
        "eq_ids": sorted(set(eq_ids)),
        "formulas": formulas,
        "sources": sources,
        "used_homologue": used,
        "model_calls": metrics.get("model_calls"),
        "prompt_tokens": metrics.get("harness_prompt_tokens"),
        "completion_tokens": metrics.get("harness_completion_tokens"),
        "cost": metrics.get("harness_estimated_cost_usd"),
        "first_content_action": first_content,
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
        if not target["blank_fill"]:
            continue
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
        exposed = target["golden_eq_id"] in trajectory.get("eq_ids", [])
        rows.append(
            {
                **target,
                "task": task,
                "submitted_fp": submitted_fp,
                "fingerprint_match": match,
                "class_exposed": exposed,
                "wrote_after_exposure": bool(exposed and match),
            }
        )
    return rows


def _official_task_scores(run_root: Path) -> dict[str, dict[str, Any]]:
    path = run_root / "official_scores.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("tasks") or {}


def score_run(run_root: Path, tasks: list[dict[str, str]]) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    mediation: list[dict[str, Any]] = []
    costs: list[dict[str, Any]] = []
    official = _official_task_scores(run_root)
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
        trajectory = parse_ambient_trajectory(_find_trajectory(task_root))
        rows = score_targets(targets, submitted, trajectory, task=task_key)
        all_rows.extend(rows)
        exposed_rows = [row for row in rows if row["class_exposed"]]
        mediation.append(
            {
                "task": task_key,
                "role": task.get("role"),
                "ambient_emitted": trajectory["ambient_emitted"],
                "content_inspections": trajectory["content_inspections"],
                "first_content_action": trajectory["first_content_action"],
                "correct_class_exposed": any(row["class_exposed"] for row in rows),
                "wrote_exposed_fingerprint": any(row["wrote_after_exposure"] for row in rows),
                "used_homologue": trajectory["used_homologue"],
                "exposed_targets": len(exposed_rows),
                "fingerprint_match_cells": sum(row["fingerprint_match"] for row in rows),
                "blank_fill_targets": len(rows),
            }
        )
        official_row = official.get(task_key) or {}
        costs.append(
            {
                "task": task_key,
                "model_calls": trajectory["model_calls"],
                "prompt_tokens": trajectory["prompt_tokens"],
                "completion_tokens": trajectory["completion_tokens"],
                "cost": trajectory["cost"],
                "modification_accuracy": official_row.get("modification_accuracy"),
                "regression_accuracy": official_row.get("regression_accuracy"),
                "exact": official_row.get("accuracy") == 1.0 if official_row else None,
            }
        )
    packed = summarize(all_rows)
    empty = {
        "cells": 0,
        "fingerprint_match_cells": 0,
        "fingerprint_match_cell_pct": None,
        "tasks": 0,
        "tasks_any_match": 0,
        "task_pct": None,
    }
    primary = {name: packed.get(name, empty) for name in PRIMARY_STRATA}
    return {
        "by_stratum": packed,
        "primary_blank_fill": primary,
        "mediation": mediation,
        "distal": costs,
        "cells": all_rows,
    }


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if isinstance(value, (int, float))]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def paired_report(control: dict[str, Any], treatment: dict[str, Any], tasks: list[dict]) -> dict[str, Any]:
    by_task = []
    control_med = {row["task"]: row for row in control["mediation"]}
    treatment_med = {row["task"]: row for row in treatment["mediation"]}
    control_distal = {row["task"]: row for row in control["distal"]}
    treatment_distal = {row["task"]: row for row in treatment["distal"]}
    for task in tasks:
        key = f"{task['category']}:{task['id']}"
        by_task.append(
            {
                "task": key,
                "role": task.get("role"),
                "control": {
                    **control_med.get(key, {}),
                    **{k: v for k, v in control_distal.get(key, {}).items() if k != "task"},
                },
                "treatment": {
                    **treatment_med.get(key, {}),
                    **{k: v for k, v in treatment_distal.get(key, {}).items() if k != "task"},
                },
            }
        )
    return {
        "proximal_metric": (
            "submitted formula fingerprint == golden formula fingerprint "
            "on recoverable blank→formula targets"
        ),
        "primary_blank_fill": {
            "control": control["primary_blank_fill"],
            "treatment": treatment["primary_blank_fill"],
        },
        "mediation": treatment["mediation"],
        "paired": by_task,
        "distal": {
            "control": {
                "modification_accuracy_mean": _mean(
                    [row["modification_accuracy"] for row in control["distal"]]
                ),
                "regression_accuracy_mean": _mean(
                    [row["regression_accuracy"] for row in control["distal"]]
                ),
                "exact": sum(1 for row in control["distal"] if row.get("exact")),
                "model_calls": sum(row.get("model_calls") or 0 for row in control["distal"]),
                "prompt_tokens": sum(row.get("prompt_tokens") or 0 for row in control["distal"]),
                "completion_tokens": sum(
                    row.get("completion_tokens") or 0 for row in control["distal"]
                ),
                "cost": round(sum(row.get("cost") or 0 for row in control["distal"]), 6),
            },
            "treatment": {
                "modification_accuracy_mean": _mean(
                    [row["modification_accuracy"] for row in treatment["distal"]]
                ),
                "regression_accuracy_mean": _mean(
                    [row["regression_accuracy"] for row in treatment["distal"]]
                ),
                "exact": sum(1 for row in treatment["distal"] if row.get("exact")),
                "model_calls": sum(row.get("model_calls") or 0 for row in treatment["distal"]),
                "prompt_tokens": sum(row.get("prompt_tokens") or 0 for row in treatment["distal"]),
                "completion_tokens": sum(
                    row.get("completion_tokens") or 0 for row in treatment["distal"]
                ),
                "cost": round(sum(row.get("cost") or 0 for row in treatment["distal"]), 6),
            },
        },
    }


def main() -> int:
    args = _arguments()
    slice_tasks = json.loads(SLICE.read_text())["tasks"]
    control = score_run(args.runs_dir / args.control_run, slice_tasks)
    treatment = score_run(args.runs_dir / args.treatment_run, slice_tasks)
    report = paired_report(control, treatment, slice_tasks)
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
