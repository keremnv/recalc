#!/usr/bin/env python3
"""Diagnostic probe of mechanical formula-target selection.

Phases:
  select   — input-side features + freeze 12 IDs (no goldens)
  freeze   — occupancy + selectors on the 12 (no goldens)
  evaluate — compare frozen targets to goldens; no writes, no scorer, no LLM
  all      — select, then freeze, then evaluate

This is a diagnostic structural-diversity sample, not a population estimate.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import formula_text, relative_fingerprint  # noqa: E402
from formula_completion_certs import load_grids  # noqa: E402
from formula_target_selection import (  # noqa: E402
    SELECTOR_DEFINITIONS,
    SLICE_LABEL,
    SLICE_NAME,
    SLICE_NOT,
    attach_file_size,
    extract_certificate_features,
    hits_to_json,
    inclusion_reason,
    intersections,
    key_to_json,
    occupancy_from_grid,
    occupancy_stats,
    project_family,
    select_on_grids,
    select_probe_slice,
)
from workbook import build_index  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
CERTS = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-completion/certificates"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-target-selection-probe"
)
SLICE_PATH = ROOT / "benchmark/slices" / f"{SLICE_NAME}.json"
CATEGORY = "Financial_Model"
SELECTOR_ORDER = (
    "S1",
    "S2",
    "S3_70",
    "S3_80",
    "S3_90",
    "S4",
    "S5",
    "S6_2",
    "S6_3",
    "S6_4",
)
INTERSECTION_ORDER = (
    "S1∩S4",
    "S1∩S5",
    "S3_80∩S4",
    "S3_80∩S5",
    "S4∩S5",
    "any2",
    "any3",
)


def _rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num / den, 4)


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    return statistics.median(values)


def _task_list() -> list[dict[str, str]]:
    return json.loads((DATA / CATEGORY / "dataset.json").read_text())


def _cert_path(task_id: str) -> Path:
    return CERTS / CATEGORY / f"{task_id}.json"


def _input_path(task: dict[str, str]) -> Path:
    return DATA / CATEGORY / task["spreadsheet_path"]


def _golden_path(task: dict[str, str]) -> Path:
    return DATA / CATEGORY / task["golden_response_path"]


def _load_features() -> list[dict[str, Any]]:
    cache = OUT / "input_features.json"
    if cache.is_file():
        return json.loads(cache.read_text())["tasks"]
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = _task_list()
    rows = []
    reused = {
        "certificate_json": True,
        "formula_cells": True,
        "sheets": True,
        "lr_ud_k2_counts": True,
        "k2_conflict_counts": True,
        "k2_axis_counts": True,
        "input_file_size": True,
        "project_family_from_path": True,
        "golden": False,
        "occupancy_grids": False,
        "equivalence_classes": False,
        "used_cell_blank_counts": False,
    }
    for index, task in enumerate(tasks, 1):
        task_id = task["id"]
        cert_file = _cert_path(task_id)
        print(f"FEATURES {index}/{len(tasks)} {task_id}", flush=True)
        if not cert_file.is_file():
            row = {
                "id": task_id,
                "family": project_family(task_id, task["spreadsheet_path"]),
                "error": "missing_certificate_json",
                "spreadsheet_path": task["spreadsheet_path"],
            }
            rows.append(row)
            continue
        payload = json.loads(cert_file.read_text())
        features = extract_certificate_features(payload)
        del payload
        features = attach_file_size(features, _input_path(task))
        features["id"] = task_id
        features["category"] = CATEGORY
        features["family"] = project_family(task_id, task["spreadsheet_path"])
        features["spreadsheet_path"] = task["spreadsheet_path"]
        features["golden_response_path"] = task["golden_response_path"]
        rows.append(features)
    cache.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "golden_used": False,
                "reused": reused,
                "newly_computed": {
                    "k2_axis_counts_from_existing_certs": True,
                    "input_file_size": True,
                    "standardized_feature_vector": True,
                },
                "tasks": rows,
            },
            indent=2,
        )
        + "\n"
    )
    return rows


def _strip_row(row: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "category": CATEGORY,
        "id": row["id"],
        "family": row["family"],
        "stratum": row["stratum"],
        "reason": inclusion_reason(row),
        "formula_cells": row["formula_cells"],
        "sheets": row["sheets"],
        "n_lr": row["n_lr"],
        "n_ud": row["n_ud"],
        "n_k2": row["n_k2"],
        "n_k2_conflicts": row["n_k2_conflicts"],
        "k2_horizontal": row.get("k2_horizontal"),
        "k2_vertical": row.get("k2_vertical"),
        "horiz_share": round(row["horiz_share"], 4),
        "formulas_per_sheet": round(row["formulas_per_sheet"], 4),
        "file_size": row.get("file_size"),
        "conflict_rate": round(row["conflict_rate"], 4),
        "lr_share": round(row["lr_share"], 4),
        "volume": round(row["volume"], 4),
        "l2": round(row["l2"], 4),
        "spreadsheet_path": row["spreadsheet_path"],
    }
    return keep


def cmd_select() -> dict[str, Any]:
    rows = _load_features()
    selected = select_probe_slice(rows)
    slice_doc = {
        "name": SLICE_NAME,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "purpose": (
            "Diagnostic probe of occupancy-topology target selection. "
            "Not a population estimate. Not fresh generalization evidence."
        ),
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "selection": {
            "eligible": sum(1 for row in rows if not row.get("error")),
            "excluded_unreadable": [
                row["id"] for row in rows if row.get("error")
            ],
            "features": [
                "formula_cells",
                "sheets",
                "n_lr",
                "n_ud",
                "n_k2",
                "n_k2_conflicts",
                "horiz_share",
                "formulas_per_sheet",
                "log_file_size",
                "lr_share",
                "conflict_rate",
            ],
            "standardize": "population z-score on eligible Financial_Model tasks",
            "volume": "log1p(n_k2); tertiles define dense / medium / sparse",
            "family_rule": "at most one task per input spreadsheet project family",
            "within_stratum": (
                "farthest-point in z-space; seed is max z-L2, tie-break min task id; "
                "thereafter max min-distance to already selected, tie-break min id"
            ),
            "unusual": (
                "after 3 dense + 3 medium + 3 sparse, pick 3 remaining by "
                "farthest-point from the 9 already chosen"
            ),
            "reused": [
                "formula-completion certificate JSON (counts and K2 axes only)",
                "input workbook file size",
                "dataset spreadsheet_path family folder",
            ],
            "not_used": [
                "golden target locations",
                "certificate correctness vs golden",
                "official modification/regression scores",
                "agent success/failure",
                "prior exacts",
                "equivalence-class sizes (not in cert JSON; not computed for selection)",
            ],
        },
        "tasks": [_strip_row(row) for row in selected],
    }
    SLICE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SLICE_PATH.write_text(json.dumps(slice_doc, indent=2) + "\n")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "slice.json").write_text(json.dumps(slice_doc, indent=2) + "\n")
    print(f"SLICE {SLICE_PATH}", flush=True)
    for task in slice_doc["tasks"]:
        print(f"  {task['id']} {task['stratum']} {task['family']}", flush=True)
    return slice_doc


def _load_slice() -> dict[str, Any]:
    if not SLICE_PATH.is_file():
        raise SystemExit(f"missing slice {SLICE_PATH}; run select first")
    return json.loads(SLICE_PATH.read_text())


def cmd_freeze() -> dict[str, Any]:
    slice_doc = _load_slice()
    if slice_doc.get("golden_used"):
        raise SystemExit("slice is marked golden_used; refuse to freeze")
    by_id = {task["id"]: task for task in _task_list()}
    freeze: dict[str, Any] = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "definitions": SELECTOR_DEFINITIONS,
        "slice": SLICE_NAME,
        "tasks": {},
    }
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        source = _input_path(task)
        print(f"OCCUPANCY {task_id}", flush=True)
        grids = [occupancy_from_grid(grid) for grid in load_grids(source)]
        selected = select_on_grids(grids)
        inter = intersections(selected)
        freeze["tasks"][task_id] = {
            "family": item["family"],
            "stratum": item["stratum"],
            "occupancy": occupancy_stats(grids),
            "selectors": {
                name: hits_to_json(selected[name]) for name in SELECTOR_ORDER
            },
            "intersections": {
                name: [key_to_json(key) for key in inter[name]]
                for name in INTERSECTION_ORDER
            },
            "counts": {
                **{name: len(selected[name]) for name in SELECTOR_ORDER},
                **{name: len(inter[name]) for name in INTERSECTION_ORDER},
            },
        }
        print(f"  counts {freeze['tasks'][task_id]['counts']}", flush=True)
    dest = OUT / "selector_freeze.json"
    dest.write_text(json.dumps(freeze) + "\n")
    print(f"FREEZE {dest}", flush=True)
    return freeze


def _cell_map(path: Path) -> dict[tuple[str, int, int], object]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    out: dict[tuple[str, int, int], object] = {}
    try:
        for sheet in workbook.worksheets:
            for cell in sheet._cells.values():
                out[(sheet.title, int(cell.column), int(cell.row))] = cell.value
    finally:
        workbook.close()
    return out


def _blank(value: object) -> bool:
    if formula_text(value):
        return False
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _label(golden_value: object | None) -> str:
    if formula_text(golden_value):
        return "A"
    if _blank(golden_value):
        return "B"
    return "C"


def _recovery(index, sheet: str, col: int, row: int, golden_formula: str) -> dict[str, Any]:
    fp = relative_fingerprint(golden_formula, col, row, sheet=sheet)
    if fp.opaque:
        return {
            "fingerprint_in_input": False,
            "opaque_golden": True,
            "bucket": None,
        }
    record = index.lookup(fp.eq_id)
    if record is None or record.n <= 0:
        return {
            "fingerprint_in_input": False,
            "opaque_golden": False,
            "bucket": "absent",
        }
    return {
        "fingerprint_in_input": True,
        "opaque_golden": False,
        "bucket": index.nearest_bucket(sheet, col, row, fp.eq_id),
        "class_n": record.n,
    }


def _blank_formula_targets(
    input_cells: dict[tuple[str, int, int], object],
    golden_cells: dict[tuple[str, int, int], object],
) -> list[tuple[str, int, int]]:
    keys = set(input_cells) | set(golden_cells)
    out = []
    for key in keys:
        if not _blank(input_cells.get(key)):
            continue
        if formula_text(golden_cells.get(key)):
            out.append(key)
    return out


def _items_for_selector(task_payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    if name in task_payload["selectors"]:
        return task_payload["selectors"][name]
    return task_payload["intersections"][name]


def cmd_evaluate() -> dict[str, Any]:
    slice_doc = _load_slice()
    freeze_path = OUT / "selector_freeze.json"
    freeze = json.loads(freeze_path.read_text())
    if freeze.get("golden_used"):
        raise SystemExit("freeze already evaluated")
    by_id = {task["id"]: task for task in _task_list()}
    names = list(SELECTOR_ORDER) + list(INTERSECTION_ORDER)
    per_selector: dict[str, dict[str, Any]] = {
        name: {
            "A": 0,
            "B": 0,
            "C": 0,
            "D": 0,
            "selected": 0,
            "true_by_task": {},
            "selected_by_task": {},
        }
        for name in names
    }
    recovery = {
        "true_targets": 0,
        "fingerprint_in_input": 0,
        "opaque_golden": 0,
        "absent": 0,
        "buckets": Counter(),
        "by_selector": {
            name: {"true": 0, "recoverable": 0, "buckets": Counter()}
            for name in names
        },
    }
    golden_targets_by_task: dict[str, int] = {}
    examples = {
        "clear_true_target": None,
        "intentional_blank_false_positive": None,
        "repeated_pattern_success": None,
        "repeated_pattern_failure": None,
    }
    task_errors: dict[str, str] = {}
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        print(f"EVAL {task_id}", flush=True)
        try:
            input_cells = _cell_map(_input_path(task))
            golden_cells = _cell_map(_golden_path(task))
            index = build_index(_input_path(task))
        except Exception as exc:  # noqa: BLE001
            task_errors[task_id] = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR {task_errors[task_id]}", flush=True)
            for name in names:
                per_selector[name]["D"] += freeze["tasks"][task_id]["counts"][name]
                per_selector[name]["selected"] += freeze["tasks"][task_id]["counts"][name]
            continue
        targets = _blank_formula_targets(input_cells, golden_cells)
        target_set = set(targets)
        golden_targets_by_task[task_id] = len(targets)
        payload = freeze["tasks"][task_id]
        labeled: dict[str, dict[tuple[str, int, int], str]] = {}
        for name in names:
            labels = {}
            for cell in _items_for_selector(payload, name):
                key = (cell["sheet"], cell["col"], cell["row"])
                label = _label(golden_cells.get(key))
                labels[key] = label
                per_selector[name][label] += 1
                per_selector[name]["selected"] += 1
            labeled[name] = labels
            true_n = sum(1 for label in labels.values() if label == "A")
            per_selector[name]["true_by_task"][task_id] = true_n
            per_selector[name]["selected_by_task"][task_id] = len(labels)
            recovery["by_selector"][name]["true"] += true_n
        for key, label in labeled["S1"].items():
            if label != "A":
                continue
            sheet, col, row = key
            golden_formula = formula_text(golden_cells.get(key))
            if not golden_formula:
                continue
            info = _recovery(index, sheet, col, row, golden_formula)
            recovery["true_targets"] += 1
            if info["opaque_golden"]:
                recovery["opaque_golden"] += 1
            elif info["fingerprint_in_input"]:
                recovery["fingerprint_in_input"] += 1
                recovery["buckets"][info["bucket"]] += 1
            else:
                recovery["absent"] += 1
        for name in names:
            for key, label in labeled[name].items():
                if label != "A":
                    continue
                sheet, col, row = key
                golden_formula = formula_text(golden_cells.get(key))
                if not golden_formula:
                    continue
                info = _recovery(index, sheet, col, row, golden_formula)
                if info["fingerprint_in_input"]:
                    recovery["by_selector"][name]["recoverable"] += 1
                    recovery["by_selector"][name]["buckets"][info["bucket"]] += 1
        if examples["clear_true_target"] is None:
            for cell in payload["selectors"]["S1"]:
                key = (cell["sheet"], cell["col"], cell["row"])
                if labeled["S1"].get(key) == "A":
                    examples["clear_true_target"] = {
                        "task": task_id,
                        "cell": f"{cell['sheet']}!{cell['address']}",
                        "selector": "S1",
                        "axes": cell.get("axes"),
                    }
                    break
        if examples["intentional_blank_false_positive"] is None:
            for cell in payload["selectors"]["S1"]:
                key = (cell["sheet"], cell["col"], cell["row"])
                if labeled["S1"].get(key) == "B":
                    examples["intentional_blank_false_positive"] = {
                        "task": task_id,
                        "cell": f"{cell['sheet']}!{cell['address']}",
                        "selector": "S1",
                        "axes": cell.get("axes"),
                    }
                    break
        if examples["repeated_pattern_success"] is None:
            for cell in payload["selectors"]["S4"]:
                key = (cell["sheet"], cell["col"], cell["row"])
                if labeled["S4"].get(key) == "A":
                    examples["repeated_pattern_success"] = {
                        "task": task_id,
                        "cell": f"{cell['sheet']}!{cell['address']}",
                        "selector": "S4",
                        "support": cell.get("support"),
                    }
                    break
        if examples["repeated_pattern_failure"] is None:
            for cell in payload["selectors"]["S4"]:
                key = (cell["sheet"], cell["col"], cell["row"])
                if labeled["S4"].get(key) == "B":
                    examples["repeated_pattern_failure"] = {
                        "task": task_id,
                        "cell": f"{cell['sheet']}!{cell['address']}",
                        "selector": "S4",
                        "support": cell.get("support"),
                    }
                    break
        print(
            f"  golden_blank_to_formula={len(targets)} "
            f"S1={payload['counts']['S1']} S4={payload['counts']['S4']}",
            flush=True,
        )

    report: dict[str, Any] = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "slice": SLICE_NAME,
        "task_errors": task_errors,
        "golden_blank_to_formula_targets": golden_targets_by_task,
        "selectors": {},
        "recovery_on_s1_true_targets": {
            "note": (
                "S1 true targets only, for a single occupancy-hole denominator. "
                "Per-selector recoverable counts are also reported."
            ),
            "true_targets": recovery["true_targets"],
            "fingerprint_in_input": recovery["fingerprint_in_input"],
            "opaque_golden": recovery["opaque_golden"],
            "absent": recovery["absent"],
            "rate": _rate(recovery["fingerprint_in_input"], recovery["true_targets"]),
            "buckets": dict(recovery["buckets"]),
        },
        "recovery_by_selector": {},
        "examples": examples,
        "prior_action_precision_reference": {
            "formula_agreement_completion": "approximately 0.1–0.35% on full Financial_Model",
            "this_probe_primary_metric": "target precision = A / selected",
        },
    }
    n_tasks = len(slice_doc["tasks"])
    for name in names:
        stats = per_selector[name]
        selected_n = stats["selected"]
        true_n = stats["A"]
        target_total = sum(golden_targets_by_task.values())
        true_by_task = stats["true_by_task"]
        covered = [n for n in true_by_task.values() if n >= 1]
        covered5 = [n for n in true_by_task.values() if n >= 5]
        recall_hits = 0
        # recall uses unique selected true targets vs all golden targets; already unique per selector
        recall_hits = true_n
        report["selectors"][name] = {
            "selected": selected_n,
            "A_golden_formula": true_n,
            "B_intended_blank": stats["B"],
            "C_golden_value": stats["C"],
            "D_eval_issue": stats["D"],
            "target_precision": _rate(true_n, selected_n),
            "target_recall": _rate(recall_hits, target_total),
            "task_coverage": {
                "workbooks_with_ge1_true": len(covered),
                "workbooks_with_ge5_true": len(covered5),
                "median_true_per_covered": _median(covered),
                "n_workbooks": n_tasks,
                "true_by_task": true_by_task,
                "selected_by_task": stats["selected_by_task"],
            },
            "false_positive_burden": {
                "intended_blanks": stats["B"],
                "intended_blanks_pct": _rate(stats["B"], selected_n),
                "value_targets": stats["C"],
                "value_targets_pct": _rate(stats["C"], selected_n),
            },
        }
        rec = recovery["by_selector"][name]
        report["recovery_by_selector"][name] = {
            "true_targets": rec["true"],
            "fingerprint_in_input": rec["recoverable"],
            "rate": _rate(rec["recoverable"], rec["true"]),
            "buckets": dict(rec["buckets"]),
        }
    dest = OUT / "evaluation.json"
    dest.write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "report.md").write_text(_render_report(slice_doc, freeze, report) + "\n")
    print(f"EVAL {dest}", flush=True)
    print(f"REPORT {OUT / 'report.md'}", flush=True)
    return report


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{100.0 * rate:.2f}%"


def _render_report(
    slice_doc: dict[str, Any],
    freeze: dict[str, Any],
    report: dict[str, Any],
) -> str:
    lines = [
        "# Formula-occupancy target-selection probe",
        "",
        f"**{SLICE_LABEL}**",
        f"**{SLICE_NOT}**",
        "",
        "No agents. No OpenRouter. No formula writes. No official scorer.",
        "",
        "## 1. Reused artifacts vs newly computed",
        "",
        "Reused from the formula-completion experiment:",
        "",
        "- per-task certificate JSON: `formula_cells`, `sheets`, LR/UD/K2 lists (counts only), K2 conflicts, K2 axes",
        "- input workbook paths and file sizes",
        "- project family from `spreadsheet_path`",
        "- `load_grids` occupancy (formulas / values / used bounds) and relative fingerprints for F vs O",
        "- existing `relative_fingerprint` / `WorkbookIndex` for the post-freeze recovery diagnostic",
        "",
        "Newly computed, and only on the frozen 12 after IDs were persisted:",
        "",
        "- F/O/V/B occupancy maps",
        "- S1–S7 selector outputs",
        "- golden A/B/C/D labels",
        "- conditional fingerprint recoverability on true targets",
        "",
        "Not computed for selection: equivalence-class sizes, used-cell/blank totals, golden locations, scores.",
        "",
        "## 2. Slice selection procedure",
        "",
        "Eligible = Financial_Model tasks whose certificate JSON has no generation error "
        f"({slice_doc['selection']['eligible']} of 100). Unreadable (not opened for occupancy): "
        + ", ".join(slice_doc["selection"]["excluded_unreadable"])
        + ".",
        "",
        "Feature vector (input-side only): " + ", ".join(slice_doc["selection"]["features"]) + ".",
        "",
        slice_doc["selection"]["standardize"] + ". Volume = " + slice_doc["selection"]["volume"] + ".",
        "",
        slice_doc["selection"]["family_rule"] + ".",
        "",
        "Strata: 3 dense / 3 medium / 3 sparse by K2-volume tertiles, then 3 unusual by farthest-point from the 9.",
        "",
        slice_doc["selection"]["within_stratum"] + ".",
        "",
        "## 3. Frozen 12 IDs",
        "",
        "| ID | stratum | family | K2 | formulas | sheets | reason |",
        "|----|---------|--------|----|----------|--------|--------|",
    ]
    for task in slice_doc["tasks"]:
        lines.append(
            f"| {task['id']} | {task['stratum']} | {task['family']} | {task['n_k2']} | "
            f"{task['formula_cells']} | {task['sheets']} | {task['reason']} |"
        )
    lines += [
        "",
        "## 4. Selector definitions",
        "",
    ]
    for key, text in freeze["definitions"].items():
        lines += [f"**{key}.** {text}", ""]
    lines += [
        "## 5. Candidate counts by selector and workbook",
        "",
        "| task | " + " | ".join(SELECTOR_ORDER + INTERSECTION_ORDER) + " |",
        "|------|" + "|".join(["---"] * (len(SELECTOR_ORDER) + len(INTERSECTION_ORDER))) + "|",
    ]
    for task in slice_doc["tasks"]:
        counts = freeze["tasks"][task["id"]]["counts"]
        cells = " | ".join(str(counts[name]) for name in list(SELECTOR_ORDER) + list(INTERSECTION_ORDER))
        lines.append(f"| {task['id']} | {cells} |")
    lines += [
        "",
        "## 6–9. Precision, recall, intersections, coverage, false positives",
        "",
        "| selector | selected | A | B | C | D | precision | recall | ≥1 true | ≥5 true | median true/covered | blank FP% | value FP% |",
        "|----------|----------|---|---|---|---|-----------|--------|---------|---------|---------------------|-----------|-----------|",
    ]
    for name, stats in report["selectors"].items():
        cov = stats["task_coverage"]
        fp = stats["false_positive_burden"]
        lines.append(
            f"| {name} | {stats['selected']} | {stats['A_golden_formula']} | "
            f"{stats['B_intended_blank']} | {stats['C_golden_value']} | {stats['D_eval_issue']} | "
            f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
            f"{cov['workbooks_with_ge1_true']} | {cov['workbooks_with_ge5_true']} | "
            f"{cov['median_true_per_covered']} | {_pct(fp['intended_blanks_pct'])} | "
            f"{_pct(fp['value_targets_pct'])} |"
        )
    rec = report["recovery_on_s1_true_targets"]
    lines += [
        "",
        "## 10. Conditional formula recoverability (true targets only)",
        "",
        "This is not a selector. Question: once the blank is a true golden formula target, "
        "is that golden fingerprint already present in the input workbook?",
        "",
        f"S1 true targets: {rec['true_targets']}. Fingerprint in input: {rec['fingerprint_in_input']} "
        f"({_pct(rec['rate'])}). Opaque golden: {rec['opaque_golden']}. Absent: {rec['absent']}. "
        f"Buckets: {rec['buckets']}.",
        "",
        "| selector | true | recoverable | rate | buckets |",
        "|----------|------|-------------|------|---------|",
    ]
    for name, item in report["recovery_by_selector"].items():
        lines.append(
            f"| {name} | {item['true_targets']} | {item['fingerprint_in_input']} | "
            f"{_pct(item['rate'])} | {item['buckets']} |"
        )
    examples = report["examples"]
    lines += [
        "",
        "## 11. Examples",
        "",
        f"- Clear true target: {examples['clear_true_target']}",
        f"- Intentional blank falsely selected: {examples['intentional_blank_false_positive']}",
        f"- Repeated-pattern success: {examples['repeated_pattern_success']}",
        f"- Repeated-pattern failure: {examples['repeated_pattern_failure']}",
        "",
        "## 12. Conclusion",
        "",
        _conclusion(report),
        "",
        "Do not treat this as a population estimate. Do not expand to all 100 without review.",
    ]
    return "\n".join(lines)


def _conclusion(report: dict[str, Any]) -> str:
    interesting = []
    for name, stats in report["selectors"].items():
        precision = stats["target_precision"]
        true_n = stats["A_golden_formula"]
        covered = stats["task_coverage"]["workbooks_with_ge1_true"]
        if precision is None:
            continue
        if precision >= 0.10 and true_n >= 10 and covered >= 2:
            interesting.append((precision, true_n, covered, name))
    interesting.sort(reverse=True)
    if not interesting:
        low = True
        for stats in report["selectors"].values():
            precision = stats["target_precision"]
            if precision is not None and precision >= 0.03 and stats["A_golden_formula"] >= 5:
                low = False
                break
        if low:
            return (
                "Structurally unpromising on this diagnostic sample: occupancy-topology "
                "selectors stay near the previous ~0.1–0.35% action-precision regime, or "
                "they only look precise by collapsing to a handful of cells. "
                "Pure formula-occupancy topology does not provide a useful target-selection "
                "predicate on this diagnostic sample."
            )
        return (
            "Ambiguous: some selectors rise above noise but do not show an "
            "order-of-magnitude precision change with nontrivial true-target count "
            "and multi-workbook coverage. Larger validation is not yet justified."
        )
    best = interesting[0]
    return (
        f"Promising enough for larger validation: {best[3]} reached target precision "
        f"{best[0]:.1%} with {best[1]} true targets across {best[2]} workbooks. "
        "This is still a 12-task diagnostic sample, not a population estimate."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("select", "freeze", "evaluate", "all"))
    args = parser.parse_args()
    if args.phase in ("select", "all"):
        cmd_select()
    if args.phase in ("freeze", "all"):
        cmd_freeze()
    if args.phase in ("evaluate", "all"):
        cmd_evaluate()


if __name__ == "__main__":
    main()
