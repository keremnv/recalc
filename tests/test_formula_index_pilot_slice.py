from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))

from formula_index_pilot import ZERO_RECOVERABLE, even_space, select_pilot


def test_even_space_picks_endpoints_and_midpoint() -> None:
    assert even_space(ZERO_RECOVERABLE, 3) == ["03_02", "09_05", "19_04"]


def test_select_pilot_never_uses_scores() -> None:
    rows = []
    for task_id in [f"{i:02d}_01" for i in range(1, 21)] + ZERO_RECOVERABLE:
        rows.append(
            {
                "id": task_id,
                "families": 100,
                "formulas": 1000,
                "recoverable_blanks": 0 if task_id in ZERO_RECOVERABLE else 5,
                "nearest": {
                    "same_row_nonadjacent": 2,
                    "same_column_nonadjacent": 2,
                    "cross_sheet": 1,
                },
            }
        )
    seen = {row["id"]: row for row in rows}
    negatives, positives = select_pilot(list(seen.values()))
    assert [item["id"] for item in negatives] == ["03_02", "09_05", "19_04"]
    assert len(positives) == 17
    assert {item["id"] for item in positives}.isdisjoint(set(ZERO_RECOVERABLE))
    assert all("score" not in item["reason"].lower() for item in negatives + positives)


def test_frozen_slice_has_twenty_paired_tasks() -> None:
    payload = json.loads(
        (Path(__file__).parents[1] / "benchmark/slices/fm-index-pilot-twenty.json").read_text()
    )
    ids = [task["id"] for task in payload["tasks"]]
    assert len(ids) == 20
    assert len(set(ids)) == 20
    assert all(task["category"] == "Financial_Model" for task in payload["tasks"])
    negatives = [task["id"] for task in payload["tasks"] if task["role"] == "negative_control"]
    positives = [task["id"] for task in payload["tasks"] if task["role"] == "mechanism_positive"]
    assert negatives == ["03_02", "09_05", "19_04"]
    assert len(positives) == 17
    assert payload["repeats"] == 2
    assert payload["max_tool_calls_per_task"] == 50
    assert payload["cost_limit_usd"] == 2.0


def test_launch_jobs_are_interleaved_and_deterministic() -> None:
    from formula_index_launch import ARM_RUNS, SEED, build_jobs, runner_command

    payload = json.loads(
        (Path(__file__).parents[1] / "benchmark/slices/fm-index-pilot-twenty.json").read_text()
    )
    jobs = build_jobs(payload)
    again = build_jobs(payload, seed=SEED)
    assert jobs == again
    assert len(jobs) == 80
    keys = [(job["task"], job["arm"], job["repeat"]) for job in jobs]
    assert len(set(keys)) == 80
    assert {job["arm"] for job in jobs} == {"control", "control-index"}
    assert {job["repeat"] for job in jobs} == {1, 2}
    # Not all-control-then-treatment: the first 8 jobs include both arms.
    assert {job["arm"] for job in jobs[:8]} == {"control", "control-index"}
    control = next(job for job in jobs if job["arm"] == "control")
    treatment = next(job for job in jobs if job["arm"] == "control-index")
    assert "--control" in runner_command(control)
    assert "--control-index" in runner_command(treatment)
    assert "--max-tokens" not in runner_command(control)
    assert ARM_RUNS["control"][1] in runner_command(control)

