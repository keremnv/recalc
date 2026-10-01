#!/usr/bin/env python3
"""Offline preflight for the forced-exposure ambient-index diagnostic.

Persists the frozen 6-task slice, verifies CONTROL identity, and reports whether
each task's golden blank-fill classes would appear in (a) a default first-sheet
content window and (b) the first content inspection from the prior control
trajectory. Does not launch agents. Does not use historical scores to select.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "benchmark"))

from ambient import (  # noqa: E402
    build_ambient_payload,
    parse_view_xlsx_action,
)
from formula_index_ambient import AVOID  # noqa: E402
from formula_index_score import load_formulas, load_values, occupancy_targets  # noqa: E402
from workbook import build_index  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model"
SLICE = ROOT / "benchmark/slices/fm-ambient-six.json"
CONTROL = ROOT / "benchmark/sweagent/spreadsheet-control.yaml"
AMBIENT = ROOT / "benchmark/sweagent/spreadsheet-control-ambient.yaml"
OFFICIAL = ROOT / "benchmark-data/SpreadsheetBench-2/SWE-agent/config/spreadsheet.yaml"
PRIOR_CONTROL = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
    / "glm-5.3-flash-fm-index-control-1"
)
REPORT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
    / "fm-ambient-six"
    / "preflight.json"
)


def control_unchanged() -> dict:
    import yaml

    ours = yaml.safe_load(CONTROL.read_text())
    treatment = yaml.safe_load(AMBIENT.read_text())
    official = yaml.safe_load(OFFICIAL.read_text())
    return {
        "control_sha256": hashlib.sha256(CONTROL.read_bytes()).hexdigest(),
        "instance_template_matches_official": (
            ours["agent"]["templates"]["instance_template"]
            == official["agent"]["templates"]["instance_template"]
        ),
        "treatment_prompt_matches_control": (
            treatment["agent"]["templates"]["instance_template"]
            == ours["agent"]["templates"]["instance_template"]
        ),
        "treatment_system_matches_control": (
            treatment["agent"]["templates"]["system_template"]
            == ours["agent"]["templates"]["system_template"]
        ),
        "control_bundles": [item["path"] for item in ours["agent"]["tools"]["bundles"]],
        "treatment_bundles": [
            item["path"] for item in treatment["agent"]["tools"]["bundles"]
        ],
        "max_observation_length": ours["agent"]["templates"]["max_observation_length"],
        "bash_enabled": ours["agent"]["tools"]["enable_bash_tool"],
        "formula_index_absent_from_treatment_prompt": (
            "formula_index" not in treatment["agent"]["templates"]["instance_template"]
        ),
    }


def _find_trajectory(task_id: str) -> Path | None:
    task_root = PRIOR_CONTROL / f"Financial_Model-{task_id}"
    matches = list(task_root.rglob("*.traj"))
    return matches[0] if matches else None


def first_content_from_traj(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for step in data.get("trajectory", []):
        parsed = parse_view_xlsx_action(str(step.get("action") or ""))
        if parsed is not None and parsed.mode == "content":
            return {
                "action": step.get("action"),
                "sheet": parsed.sheet,
                "start_row": parsed.start_row,
                "end_row": parsed.end_row,
            }
    return None


def _coverage(payload: dict, golden_eq_ids: set[str]) -> dict:
    exposed = [eq_id for eq_id in golden_eq_ids if eq_id in payload["eq_ids"]]
    return {
        "classes_in_payload": payload["classes"],
        "opaque_classes": payload.get("opaque_classes", 0),
        "payload_chars": len(payload["text"]),
        "truncated": "truncated=true" in payload["text"].split("\n", 1)[0],
        "window": payload["window"],
        "golden_eq_ids": sorted(golden_eq_ids),
        "golden_eq_ids_exposed": exposed,
        "correct_class_exposed": bool(exposed),
    }


def describe_task(task_id: str, dataset: dict) -> dict:
    rec = dataset[task_id]
    inp_path = DATA / rec["spreadsheet_path"]
    gold_path = DATA / rec["golden_response_path"]
    index = build_index(inp_path)
    inp = load_formulas(inp_path)
    inv = load_values(inp_path)
    gold = load_formulas(gold_path)
    gval = load_values(gold_path)
    targets = occupancy_targets(index, inp, inv, gold, gval)
    blanks = [row for row in targets if row["blank_fill"]]
    nearest = Counter(row["stratum"] for row in blanks)
    golden_eq_ids = {row["golden_eq_id"] for row in blanks}
    recoverable_eq = {
        row["golden_eq_id"] for row in blanks if row["stratum"] != "unrecoverable"
    }
    default_payload = build_ambient_payload(
        inp_path, index=index, formulas=inp, limit=10_000
    )
    prior = first_content_from_traj(_find_trajectory(task_id))
    prior_payload = None
    if prior is not None:
        prior_payload = build_ambient_payload(
            inp_path,
            sheet=prior["sheet"],
            start_row=prior["start_row"],
            end_row=prior["end_row"],
            index=index,
            formulas=inp,
            limit=10_000,
        )
    return {
        "id": task_id,
        "formulas": index.formula_cells,
        "opaque_cells": index.opaque_cells,
        "opaque_frac": (
            0.0
            if not index.formula_cells
            else round(index.opaque_cells / index.formula_cells, 4)
        ),
        "blank_fills": len(blanks),
        "nearest": dict(nearest),
        "default_first_sheet": _coverage(default_payload, golden_eq_ids),
        "default_recoverable_class_exposed": bool(
            set(default_payload["eq_ids"]) & recoverable_eq
        ),
        "prior_control_first_content": prior,
        "prior_control_would_expose_correct_class": (
            None
            if prior_payload is None
            else _coverage(prior_payload, golden_eq_ids)["correct_class_exposed"]
        ),
        "prior_control_would_expose_recoverable_class": (
            None
            if prior_payload is None
            else bool(set(prior_payload["eq_ids"]) & recoverable_eq)
        ),
        "prior_control_payload": None if prior_payload is None else _coverage(prior_payload, golden_eq_ids),
        "recoverable_eq_ids": sorted(recoverable_eq),
    }


def main() -> int:
    slice_data = json.loads(SLICE.read_text())
    dataset = {item["id"]: item for item in json.loads((DATA / "dataset.json").read_text())}
    picked_ids = [task["id"] for task in slice_data["tasks"]]
    if any(task_id in AVOID for task_id in picked_ids):
        raise SystemExit("frozen slice included an avoided task")
    if picked_ids != ["03_02", "01_01", "20_05", "11_02", "02_05", "11_01"]:
        raise SystemExit(f"frozen slice IDs drifted: {picked_ids}")

    print("VERIFY payloads for frozen 6", flush=True)
    tasks = []
    for item in slice_data["tasks"]:
        print(f"  payload {item['id']}", flush=True)
        detail = describe_task(item["id"], dataset)
        tasks.append({**item, **detail})

    report = {
        "slice": str(SLICE.relative_to(ROOT)),
        "avoid": sorted(AVOID),
        "control": control_unchanged(),
        "selection": [
            {
                "id": item["id"],
                "role": item["role"],
                "reason": item["reason"],
            }
            for item in slice_data["tasks"]
        ],
        "tasks": tasks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"WROTE {REPORT}", flush=True)
    print("FROZEN", " ".join(picked_ids), flush=True)
    for task in tasks:
        prior = task["prior_control_would_expose_correct_class"]
        print(
            f"{task['id']} role={task['role']} opaque_frac={task['opaque_frac']} "
            f"nearest={task['nearest']} default_exposed="
            f"{task['default_first_sheet']['correct_class_exposed']} "
            f"prior_control_exposed={prior} "
            f"prior_recoverable_exposed={task['prior_control_would_expose_recoverable_class']} "
            f"payload_chars={task['default_first_sheet']['payload_chars']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
