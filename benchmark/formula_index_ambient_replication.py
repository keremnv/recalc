"""Freeze the 20_05 / 11_02 ambient-replication target subsets.

Offline input/golden analysis plus the prior diagnostic treatment's first
content window. Does not consult new trajectories. Does not change the
intervention.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "benchmark"))

from ambient import build_ambient_payload, visible_class_records  # noqa: E402
from fingerprint import a1_address
from formula_index_ambient_preflight import control_unchanged
from formula_index_ambient_score import parse_ambient_trajectory
from formula_index_score import _find_trajectory, load_formulas, load_values, occupancy_targets
from workbook import build_index  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
PRIOR_TREATMENT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
    / "glm-5.3-flash-fm-ambient-treatment-1"
)
MANIFEST = ROOT / "benchmark/slices/fm-ambient-replication-targets.json"
SLICE = ROOT / "benchmark/slices/fm-ambient-replication-two.json"

# First content windows from the diagnostic treatment trajectories. These
# define the frozen exposed subsets; they are not updated after new runs.
DIAGNOSTIC_FIRST_CONTENT = {
    "20_05": {
        "sheet": "Cost Drivers",
        "start_row": None,
        "end_row": None,
        "action": (
            "view_xlsx '/mnt/spreadsheet_data/spreadsheet/20_Project Fintech/"
            "20_05_Fintech_input.xlsx' content 'Cost Drivers'"
        ),
    },
    "11_02": {
        "sheet": "CF",
        "start_row": None,
        "end_row": None,
        "action": (
            "view_xlsx '/mnt/spreadsheet_data/spreadsheet/11_Project Switchgear/"
            "11_02_Switchgear_input.xlsx' content CF"
        ),
    },
}

EXPECTED_EXPOSED = {"20_05": 42, "11_02": 5}

INTERVENTION_PATHS = [
    ROOT / "benchmark/sweagent/spreadsheet-control.yaml",
    ROOT / "benchmark/sweagent/spreadsheet-control-ambient.yaml",
    ROOT / "benchmark/sweagent/view_xlsx_ambient/bin/view_xlsx",
    ROOT / "benchmark/sweagent/view_xlsx_ambient/config.yaml",
    ROOT / "benchmark/sweagent/formula_index/lib/ambient.py",
    ROOT / "benchmark/sweagent/formula_index/lib/fingerprint.py",
    ROOT / "benchmark/sweagent/formula_index/lib/workbook.py",
    ROOT / "benchmark/sweagent/formula_index/lib/ranges.py",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def intervention_integrity() -> dict[str, Any]:
    files = {str(path.relative_to(ROOT)): sha256_file(path) for path in INTERVENTION_PATHS}
    control = control_unchanged()
    wrapper = (ROOT / "benchmark/sweagent/view_xlsx_ambient/bin/view_xlsx").read_text()
    ambient = (ROOT / "benchmark/sweagent/formula_index/lib/ambient.py").read_text()
    treatment_yaml = (ROOT / "benchmark/sweagent/spreadsheet-control-ambient.yaml").read_text()
    return {
        "files": files,
        "control": control,
        "wrapper_appends_first_content_only": "_already_emitted" in wrapper,
        "treatment_prompt_has_no_structural_index": "STRUCTURAL INDEX" not in treatment_yaml,
        "no_formula_index_in_treatment": control["formula_index_absent_from_treatment_prompt"],
        "no_ranking_in_ambient": "likely" not in ambient.lower() and "golden" not in ambient.lower(),
        "observation_cap": 10_000,
    }


def _task_paths(task_id: str) -> tuple[Path, Path]:
    dataset = json.loads((DATA / "Financial_Model" / "dataset.json").read_text())
    record = next(item for item in dataset if item["id"] == task_id)
    return (
        DATA / "Financial_Model" / record["spreadsheet_path"],
        DATA / "Financial_Model" / record["golden_response_path"],
    )


def freeze_task(task_id: str) -> dict[str, Any]:
    spec = DIAGNOSTIC_FIRST_CONTENT[task_id]
    inp_path, gold_path = _task_paths(task_id)
    index = build_index(inp_path)
    inp = load_formulas(inp_path)
    inv = load_values(inp_path)
    gold = load_formulas(gold_path)
    gval = load_values(gold_path)
    occupancy = occupancy_targets(index, inp, inv, gold, gval)
    payload = build_ambient_payload(
        inp_path,
        sheet=spec["sheet"],
        start_row=spec["start_row"],
        end_row=spec["end_row"],
        index=index,
        formulas=inp,
        limit=10_000,
    )
    payload_eq = set(payload["eq_ids"])
    window = payload["window"]
    payload_fps = {
        record.fingerprint
        for record, _source, _formula in visible_class_records(
            index,
            inp,
            sheet=window["sheet"],
            c1=window["c1"],
            r1=window["r1"],
            c2=window["c2"],
            r2=window["r2"],
        )
    }

    traj_path = _find_trajectory(PRIOR_TREATMENT / f"Financial_Model-{task_id}")
    prior = parse_ambient_trajectory(traj_path)
    prior_eq = set(prior.get("eq_ids") or [])

    targets: list[dict[str, Any]] = []
    for row in occupancy:
        if not row["blank_fill"]:
            continue
        eq_in_payload = row["golden_eq_id"] in payload_eq
        fp_in_payload = row["golden_fp"] in payload_fps
        exposed = eq_in_payload or fp_in_payload
        if task_id == "20_05":
            in_fixed = exposed and row["stratum"] == "same_column_nonadjacent"
        else:
            # Diagnostic mediation counted 5 exposed blank fills on 11_02. Those
            # cells are adjacent BS!I7:M7 homologues, not the Working Capital
            # same-column family (which the CF first inspection did not intersect).
            in_fixed = exposed
        targets.append(
            {
                "sheet": row["sheet"],
                "address": f"{row['sheet']}!{a1_address(row['col'], row['row'])}",
                "col": row["col"],
                "row": row["row"],
                "golden_fingerprint": row["golden_fp"],
                "golden_eq_id": row["golden_eq_id"],
                "recoverable": row["stratum"] != "unrecoverable",
                "stratum": row["stratum"],
                "golden_eq_id_in_payload": eq_in_payload,
                "same_fingerprint_in_payload": fp_in_payload,
                "class_exposed": exposed,
                "in_fixed_exposed_subset": in_fixed,
            }
        )

    exposed = [row for row in targets if row["in_fixed_exposed_subset"]]
    recoverable_unexposed = [
        row for row in targets if row["recoverable"] and not row["in_fixed_exposed_subset"]
    ]
    unrecoverable = [row for row in targets if not row["recoverable"]]
    return {
        "id": task_id,
        "diagnostic_first_content": spec,
        "payload_window": payload["window"],
        "payload_classes": payload["classes"],
        "payload_chars": len(payload["text"]),
        "payload_truncated": "truncated=true" in payload["text"].split("\n", 1)[0],
        "prior_treatment_first_content": prior.get("first_content_action"),
        "prior_treatment_ambient_emitted": prior.get("ambient_emitted"),
        "prior_observation_eq_ids": sorted(prior_eq),
        "counts": {
            "blank_fill": len(targets),
            "fixed_exposed": len(exposed),
            "fixed_exposed_same_column": sum(
                1 for row in exposed if row["stratum"] == "same_column_nonadjacent"
            ),
            "recoverable_unexposed": len(recoverable_unexposed),
            "unrecoverable": len(unrecoverable),
            "recoverable": sum(1 for row in targets if row["recoverable"]),
        },
        "fixed_exposed_strata": dict(Counter(row["stratum"] for row in exposed)),
        "fixed_exposed_eq_ids": sorted({row["golden_eq_id"] for row in exposed}),
        "fixed_exposed_addresses": sorted(row["address"] for row in exposed),
        "targets": targets,
    }


def freeze_manifest() -> dict[str, Any]:
    tasks = {task_id: freeze_task(task_id) for task_id in ("20_05", "11_02")}
    for task_id, expected in EXPECTED_EXPOSED.items():
        got = tasks[task_id]["counts"]["fixed_exposed"]
        if got != expected:
            raise ValueError(
                f"{task_id} frozen exposed subset is {got}, expected {expected} "
                "from the diagnostic; do not launch"
            )
        first = tasks[task_id]["prior_treatment_first_content"]
        documented = DIAGNOSTIC_FIRST_CONTENT[task_id]["action"]
        if first and first != documented:
            raise ValueError(
                f"{task_id} prior first content {first!r} != documented {documented!r}"
            )
    return {
        "name": "fm-ambient-replication-two",
        "purpose": (
            "Replication of the forced-exposure diagnostic on 20_05 (candidate "
            "positive) and 11_02 (candidate null). Exposed subsets are frozen from "
            "the diagnostic treatment first-content windows. Not a LibreCalc experiment."
        ),
        "intervention": intervention_integrity(),
        "tasks": tasks,
    }


def write_slice() -> dict[str, Any]:
    payload = {
        "name": "fm-ambient-replication-two",
        "purpose": (
            "n=5 replication of forced-exposure on Financial_Model 20_05 and 11_02. "
            "Primary unit is one full task run. Exposed-target subsets are frozen in "
            "fm-ambient-replication-targets.json."
        ),
        "model": "z-ai/glm-5.3-flash",
        "sampling": (
            "The two informative cases from fm-ambient-six. Not resampled. "
            "Never historical scores."
        ),
        "arms": {
            "control": "--control, official config, 50 calls, $2, reasoning low, remaining-budget, no read budget",
            "control-ambient": "--control-ambient, identical prompt/budgets; first view_xlsx content appends unranked formula-equivalence metadata",
        },
        "repeats": 5,
        "max_tool_calls_per_task": 50,
        "cost_limit_usd": 2.0,
        "reasoning_effort": "low",
        "token_limit_policy": "remaining-budget",
        "tasks": [
            {
                "category": "Financial_Model",
                "id": "20_05",
                "role": "replication_positive_candidate",
                "stratum": "same_column_nonadjacent",
                "reason": "diagnostic candidate positive; freeze 42 same-column exposed blank→formula targets",
            },
            {
                "category": "Financial_Model",
                "id": "11_02",
                "role": "replication_null_candidate",
                "stratum": "same_column_nonadjacent",
                "reason": "diagnostic candidate null; freeze the 5 blank fills whose class was actually in the CF first-content payload (adjacent BS!I7:M7, not the unexposed Working Capital same-column family)",
            },
        ],
    }
    SLICE.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main() -> int:
    slice_data = write_slice()
    manifest = freeze_manifest()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"WROTE {SLICE}", flush=True)
    print(f"WROTE {MANIFEST}", flush=True)
    integrity = manifest["intervention"]
    print(
        f"INTEGRITY prompt_match={integrity['control']['treatment_prompt_matches_control']} "
        f"no_formula_index={integrity['no_formula_index_in_treatment']} "
        f"first_content_only={integrity['wrapper_appends_first_content_only']}",
        flush=True,
    )
    for task_id, task in manifest["tasks"].items():
        print(
            f"{task_id} exposed={task['counts']['fixed_exposed']} "
            f"exposed_strata={task['fixed_exposed_strata']} "
            f"recoverable_unexposed={task['counts']['recoverable_unexposed']} "
            f"unrecoverable={task['counts']['unrecoverable']} "
            f"blank_fill={task['counts']['blank_fill']} "
            f"payload_chars={task['payload_chars']} truncated={task['payload_truncated']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
