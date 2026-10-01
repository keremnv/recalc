#!/usr/bin/env python3
"""Offline diagnostic of slot liveness / regime on frozen ANY_POINT blanks.

Phases:
  freeze   — ANY_POINT candidates + A–F predicates (no goldens)
  evaluate — golden labels, L1–L9, monotonicity, autopsy coverage
  all      — freeze then evaluate

Reuses fm-target-selection-probe-12 and the point-range graph. No agents,
workbook writes, official scorer, formula reconstruction, or learned scores.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address  # noqa: E402
from formula_dependency_selection import blank_edge_types, build_graph  # noqa: E402
from formula_dependency_selection_probe import (  # noqa: E402
    _blank_formula_targets,
    _cell_map,
    _golden_path,
    _input_path,
    _label,
    _load_slice,
    _pct,
    _rate,
    _task_list,
)
from formula_liveness import (  # noqa: E402
    ATOMIC,
    CONJUNCTIONS,
    DEFINITIONS,
    build_occupancy_peers,
    features_for_cell,
    sheet_scan,
)
from formula_target_selection import SLICE_LABEL, SLICE_NAME, SLICE_NOT  # noqa: E402
from ranges import parse_a1_cell  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()

DEP_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-dependency-selection-probe"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-liveness-probe"
)

# Secondary evaluation only. Predicates were not defined from these cells.
AUTOPSY_CELLS = (
    {
        "cell_id": "15_04:Work Sheet!AP124",
        "class": "lattice unused slot",
    },
    {
        "cell_id": "15_04:Work Sheet!AP140",
        "class": "lattice unused slot",
    },
    {
        "cell_id": "07_05:Construction Schedule!CQ57",
        "class": "schedule live-window end",
    },
    {
        "cell_id": "15_04:Consol_annual!T139",
        "class": "spacer row",
    },
    {
        "cell_id": "17_03:Financials!K38",
        "class": "regime handoff",
    },
    {
        "cell_id": "17_03:Financials!L38",
        "class": "regime handoff",
    },
)

# Predeclared directional hypotheses. E3 is measured, not assumed.
DIRECTION = {
    "A1": "increase",
    "A1_h": "increase",
    "A1_v": "increase",
    "A2": "decrease",
    "A2_h": "decrease",
    "A2_v": "decrease",
    "B1": "decrease",
    "B2": "decrease",
    "B3": "decrease",
    "C1": "decrease",
    "C2": "increase",
    "C3": "decrease",
    "D1": "decrease",
    "D2": "increase",
    "D3": "decrease",
    "E1": "increase",
    "E2": "decrease",
    "E3": "measure",
    "E4": "decrease",
    "F1": "increase",
    "F2": "decrease",
    "F3": "decrease",
    "L1": "increase",
    "L2": "decrease",
    "L3": "decrease",
    "L4": "increase",
    "L5": "decrease",
    "L6": "increase",
    "L7": "decrease",
    "L8": "increase",
    "L9": "decrease",
}

ACTIVITY_EVIDENCE = ("L1", "L4", "L6", "L8", "A1", "C2", "E1", "D2", "F1")
INACTIVITY_EVIDENCE = ("L2", "L3", "L5", "L7", "L9", "A2", "C1", "C3", "D1", "E2", "E4", "F2", "F3")


def _empty_stats() -> dict[str, Any]:
    return {
        "A": 0,
        "B": 0,
        "C": 0,
        "selected": 0,
        "binary": 0,
        "true_by_task": {},
        "selected_by_task": {},
        "binary_by_task": {},
    }


def _ensure_task(stats: dict[str, Any], task_id: str) -> None:
    stats["true_by_task"].setdefault(task_id, 0)
    stats["selected_by_task"].setdefault(task_id, 0)
    stats["binary_by_task"].setdefault(task_id, 0)


def _add(stats: dict[str, Any], task_id: str, label: str) -> None:
    stats[label] += 1
    stats["selected"] += 1
    if label in ("A", "B"):
        stats["binary"] += 1
        stats["binary_by_task"][task_id] = stats["binary_by_task"].get(task_id, 0) + 1
    stats["true_by_task"][task_id] = stats["true_by_task"].get(task_id, 0) + int(label == "A")
    stats["selected_by_task"][task_id] = stats["selected_by_task"].get(task_id, 0) + 1


def _pack(stats: dict[str, Any], n_true_pop: int, n_targets: int, n_tasks: int) -> dict[str, Any]:
    true_n = stats["A"]
    binary = stats["binary"]
    covered = [n for n in stats["true_by_task"].values() if n >= 1]
    covered5 = [n for n in stats["true_by_task"].values() if n >= 5]
    precision_by_task = {}
    for tid, n_bin in stats["binary_by_task"].items():
        precision_by_task[tid] = _rate(stats["true_by_task"][tid], n_bin)
    return {
        "selected": stats["selected"],
        "binary_selected": binary,
        "A_golden_formula": true_n,
        "B_intended_blank": stats["B"],
        "C_golden_value": stats["C"],
        "target_precision": _rate(true_n, binary),
        "recall_in_any_point": _rate(true_n, n_true_pop),
        "recall_vs_all_golden_formula_blanks": _rate(true_n, n_targets),
        "false_positive_burden": stats["B"],
        "task_coverage": {
            "workbooks_with_ge1_true": len(covered),
            "workbooks_with_ge5_true": len(covered5),
            "n_workbooks": n_tasks,
            "true_by_task": stats["true_by_task"],
            "selected_by_task": stats["selected_by_task"],
            "binary_by_task": stats["binary_by_task"],
            "precision_by_task": precision_by_task,
        },
    }


def _cell_id(task_id: str, sheet: str, col: int, row: int) -> str:
    return f"{task_id}:{sheet}!{a1_address(col, row)}"


def _parse_cell_id(cell_id: str) -> tuple[str, str, int, int]:
    task_id, rest = cell_id.split(":", 1)
    sheet, address = rest.split("!", 1)
    col, row = parse_a1_cell(address)
    return task_id, sheet, col, row


def cmd_freeze() -> dict[str, Any]:
    slice_doc = _load_slice()
    by_id = {task["id"]: task for task in _task_list()}
    OUT.mkdir(parents=True, exist_ok=True)
    freeze: dict[str, Any] = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "slice": SLICE_NAME,
        "population": "ANY_POINT",
        "definitions": DEFINITIONS,
        "conjunctions_predeclared": DEFINITIONS["conjunctions"],
        "reused": [
            "fm-target-selection-probe-12 workbook IDs",
            "build_graph / blank_edge_types (same reverse-A1 graph as point_range_decomposition)",
            "occupancy F/O/V/B from DependencyGraph.occupancy",
            "homologous_peers formula-class slot offsets",
            "workbook used bounds via occupancy grids",
        ],
        "newly_computed": [
            "ANY_POINT candidate list for this probe",
            "occupancy-vector homology peers (D3/E)",
            "row type-regime boundaries and live-extent scans",
            "liveness predicates A–F and L1–L9",
        ],
        "runtime_s": {},
        "tasks": {},
        "n_any_point": 0,
    }
    t0 = time.perf_counter()
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        source = _input_path(task)
        print(f"GRAPH {task_id}", flush=True)
        started = time.perf_counter()
        graph = build_graph(source)
        graph_s = time.perf_counter() - started
        types = blank_edge_types(graph)
        any_point = {key: info for key, info in types.items() if info["n_point"] >= 1}
        wanted = set(any_point)
        occ_started = time.perf_counter()
        occ = build_occupancy_peers(graph.occupancy, wanted)
        occ_s = time.perf_counter() - occ_started
        by_sheet: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
        for key in any_point:
            by_sheet[key[0]].append(key)
        scans = {
            sheet: sheet_scan(graph.occupancy[sheet], rows={key[2] for key in keys})
            for sheet, keys in by_sheet.items()
            if sheet in graph.occupancy
        }
        feat_started = time.perf_counter()
        class_cache: dict[str, Any] = {}
        cells = []
        for key in sorted(any_point):
            edge = any_point[key]
            feat = features_for_cell(
                graph,
                key,
                occ,
                class_cache,
                edge,
                scans.get(key[0]),
            )
            feat["cell_id"] = _cell_id(task_id, key[0], key[1], key[2])
            cells.append(feat)
        feat_s = time.perf_counter() - feat_started
        elapsed = time.perf_counter() - started
        freeze["runtime_s"][task_id] = {
            "graph": round(graph_s, 3),
            "occupancy_peers": round(occ_s, 3),
            "features": round(feat_s, 3),
            "total": round(elapsed, 3),
        }
        freeze["tasks"][task_id] = {
            "family": item["family"],
            "stratum": item["stratum"],
            "coverage": graph.coverage,
            "n_any_point": len(cells),
            "cells": cells,
        }
        freeze["n_any_point"] += len(cells)
        print(
            f"  ANY_POINT={len(cells)} formulas={graph.coverage['formula_cells']} "
            f"graph={graph_s:.1f}s peers={occ_s:.1f}s feat={feat_s:.1f}s",
            flush=True,
        )
        del graph, types, occ, scans, cells, any_point
    freeze["runtime_s"]["all"] = round(time.perf_counter() - t0, 3)
    dest = OUT / "candidate_freeze.json"
    dest.write_text(json.dumps(freeze) + "\n")
    print(f"FREEZE {dest} n={freeze['n_any_point']} runtime={freeze['runtime_s']['all']}s", flush=True)
    return freeze


def _load_freeze() -> dict[str, Any]:
    return json.loads((OUT / "candidate_freeze.json").read_text())


def _load_baselines() -> dict[str, Any]:
    path = DEP_OUT / "point_range_decomposition.json"
    return json.loads(path.read_text())


def _selector_names() -> tuple[str, ...]:
    return ("ANY_POINT",) + ATOMIC + CONJUNCTIONS


def cmd_evaluate() -> dict[str, Any]:
    slice_doc = _load_slice()
    freeze = _load_freeze()
    baselines = _load_baselines()
    by_id = {task["id"]: task for task in _task_list()}
    n_tasks = len(slice_doc["tasks"])
    started = time.perf_counter()
    groups = {name: _empty_stats() for name in _selector_names()}
    n_targets = 0
    n_true_pop = 0
    other_labels = 0
    labeled: list[dict[str, Any]] = []
    golden_targets_by_task: dict[str, int] = {}

    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        print(f"EVAL {task_id}", flush=True)
        input_cells = _cell_map(_input_path(task))
        golden_cells = _cell_map(_golden_path(task))
        targets = _blank_formula_targets(input_cells, golden_cells)
        golden_targets_by_task[task_id] = len(targets)
        n_targets += len(targets)
        for stats in groups.values():
            _ensure_task(stats, task_id)
        for feat in freeze["tasks"][task_id]["cells"]:
            key = (feat["sheet"], feat["col"], feat["row"])
            label = _label(golden_cells.get(key))
            if label not in ("A", "B", "C"):
                other_labels += 1
                continue
            if label == "A":
                n_true_pop += 1
            rec = {
                "cell_id": feat["cell_id"],
                "task_id": task_id,
                "sheet": feat["sheet"],
                "col": feat["col"],
                "row": feat["row"],
                "label": label,
                "eval_role": (
                    "TRUE_TARGET"
                    if label == "A"
                    else "INTENTIONAL_BLANK"
                    if label == "B"
                    else "GOLDEN_VALUE"
                ),
                "flags": feat["flags"],
                "n_point": feat["n_point"],
                "n_point_eq": feat["n_point_eq"],
                "partition": feat["partition"],
                "A": feat["A"],
                "B": feat["B"],
                "C": feat["C"],
                "D": feat["D"],
                "E": feat["E"],
                "F": feat["F"],
            }
            labeled.append(rec)
            _add(groups["ANY_POINT"], task_id, label)
            for name in ATOMIC + CONJUNCTIONS:
                if feat["flags"].get(name):
                    _add(groups[name], task_id, label)
        print(
            f"  n={freeze['tasks'][task_id]['n_any_point']} "
            f"A={groups['ANY_POINT']['true_by_task'][task_id]} "
            f"sel={groups['ANY_POINT']['selected_by_task'][task_id]}",
            flush=True,
        )
        del input_cells, golden_cells

    packed = {
        name: _pack(stats, n_true_pop, n_targets, n_tasks) for name, stats in groups.items()
    }
    base_any = packed["ANY_POINT"]["target_precision"]
    monotonic = _monotonic(packed, freeze, labeled, base_any)
    autopsy = _autopsy_coverage(freeze, labeled)
    examples = _examples(labeled)
    interpretation = _interpret(packed, monotonic, autopsy, baselines)
    stored_any = baselines["partitions"]["ANY_POINT"]
    stored_point = baselines["partitions"]["POINT_ONLY"]
    stored_eq2 = baselines["point_consumer_classes"][">=2"]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": True,
        "golden_used_in_features": False,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "runtime_s": round(time.perf_counter() - started, 3),
        "freeze_runtime_s": freeze["runtime_s"],
        "reused": freeze["reused"],
        "newly_computed": freeze["newly_computed"],
        "n_any_point": freeze["n_any_point"],
        "n_any_point_labeled": len(labeled),
        "n_true_targets_in_any_point": n_true_pop,
        "n_other_golden_labels": other_labels,
        "n_targets_all_golden_formula_blanks": n_targets,
        "golden_blank_to_formula_targets": golden_targets_by_task,
        "stored_baselines": {
            "ANY_POINT": {
                "selected": stored_any["selected"],
                "A_golden_formula": stored_any["A_golden_formula"],
                "B_intended_blank": stored_any["B_intended_blank"],
                "C_golden_value": stored_any["C_golden_value"],
                "target_precision": stored_any["target_precision"],
                "target_recall": stored_any["target_recall"],
            },
            "POINT_ONLY": {
                "selected": stored_point["selected"],
                "target_precision": stored_point["target_precision"],
            },
            "ANY_POINT + >=2 consumer classes": {
                "selected": stored_eq2["selected"],
                "target_precision": stored_eq2["target_precision"],
            },
        },
        "any_point_count_match": freeze["n_any_point"] == stored_any["selected"],
        "definitions": DEFINITIONS,
        "atomic": {name: packed[name] for name in ATOMIC},
        "conjunctions": {name: packed[name] for name in CONJUNCTIONS},
        "ANY_POINT": packed["ANY_POINT"],
        "monotonic": monotonic,
        "autopsy": autopsy,
        "examples": examples,
        "interpretation": interpretation,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "evaluation.json"
    dest.write_text(json.dumps(report) + "\n")
    md = OUT / "evaluation.md"
    md.write_text(_render(report) + "\n")
    print(f"EVAL {dest}", flush=True)
    print(f"WROTE {md}", flush=True)
    print(f"interpretation={interpretation['gate']}", flush=True)
    return report


def _monotonic(
    packed: dict[str, Any],
    freeze: dict[str, Any],
    labeled: list[dict[str, Any]],
    base_any: float | None,
) -> dict[str, Any]:
    by_task_flag: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"A": 0, "B": 0, "offA": 0, "offB": 0})
    )
    names = [name for name in ATOMIC + CONJUNCTIONS if not name.startswith("E1_k")]
    for rec in labeled:
        if rec["label"] not in ("A", "B"):
            continue
        task_id = rec["task_id"]
        for name in names:
            bucket = by_task_flag[name][task_id]
            if rec["flags"].get(name):
                bucket[rec["label"]] += 1
            else:
                bucket["off" + rec["label"]] += 1
    out: dict[str, Any] = {}
    for name in names:
        on = packed[name]
        expected = DIRECTION.get(name, "measure")
        on_rate = on["target_precision"]
        delta = None if on_rate is None or base_any is None else round(on_rate - base_any, 4)
        task_rates = []
        inconsistent = []
        for task_id, bucket in by_task_flag[name].items():
            on_bin = bucket["A"] + bucket["B"]
            off_bin = bucket["offA"] + bucket["offB"]
            on_p = _rate(bucket["A"], on_bin)
            off_p = _rate(bucket["offA"], off_bin)
            if on_bin < 8 or off_bin < 8 or on_p is None or off_p is None:
                continue
            higher = on_p > off_p + 0.02
            lower = on_p < off_p - 0.02
            task_rates.append(
                {
                    "task": task_id,
                    "on_precision": on_p,
                    "off_precision": off_p,
                    "on_n": on_bin,
                    "off_n": off_bin,
                    "direction": "increase" if higher else "decrease" if lower else "flat",
                }
            )
            if expected == "increase" and lower:
                inconsistent.append(task_id)
            elif expected == "decrease" and higher:
                inconsistent.append(task_id)
        observed = "measure"
        if expected in ("increase", "decrease") and delta is not None:
            if expected == "increase":
                observed = "increase" if delta >= 0.02 else "decrease" if delta <= -0.02 else "flat"
            else:
                observed = "decrease" if delta <= -0.02 else "increase" if delta >= 0.02 else "flat"
        out[name] = {
            "expected": expected,
            "on_precision": on_rate,
            "on_selected_binary": on["binary_selected"],
            "delta_vs_any_point": delta,
            "pooled_matches_expected": expected == "measure" or observed == expected,
            "observed_pooled": observed,
            "inconsistent_workbooks": inconsistent,
            "workbook_conditional": task_rates,
        }
    return out


def _autopsy_coverage(freeze: dict[str, Any], labeled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {rec["cell_id"]: rec for rec in labeled}
    freeze_ids = {
        feat["cell_id"]
        for task in freeze["tasks"].values()
        for feat in task["cells"]
    }
    out = []
    for spec in AUTOPSY_CELLS:
        rec = by_id.get(spec["cell_id"])
        present = spec["cell_id"] in freeze_ids
        flags = rec["flags"] if rec else None
        fired = []
        if flags:
            fired = [name for name in ATOMIC + CONJUNCTIONS if flags.get(name)]
        out.append(
            {
                **spec,
                "in_any_point": present,
                "eval_role": rec["eval_role"] if rec else None,
                "fired": fired,
                "activity_evidence": [name for name in ACTIVITY_EVIDENCE if flags and flags.get(name)],
                "inactivity_evidence": [
                    name for name in INACTIVITY_EVIDENCE if flags and flags.get(name)
                ],
            }
        )
    return out


def _examples(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    def score_activity(rec: dict[str, Any]) -> int:
        return sum(1 for name in ACTIVITY_EVIDENCE if rec["flags"].get(name))

    def score_inactivity(rec: dict[str, Any]) -> int:
        return sum(1 for name in INACTIVITY_EVIDENCE if rec["flags"].get(name))

    def pack(rec: dict[str, Any] | None) -> dict[str, Any] | None:
        if rec is None:
            return None
        return {
            "cell_id": rec["cell_id"],
            "eval_role": rec["eval_role"],
            "activity_score": score_activity(rec),
            "inactivity_score": score_inactivity(rec),
            "fired": [name for name in ATOMIC + CONJUNCTIONS if rec["flags"].get(name)],
            "C": rec["C"],
            "E": {
                k: rec["E"][k]
                for k in ("E1", "E2", "E3", "E4", "n_peers", "n_active", "n_blank", "active_share")
            },
            "F": {
                k: rec["F"][k]
                for k in ("F1", "F2", "F3", "n_peers", "blank_share", "consumer_columns")
            },
        }

    true_active = [
        rec for rec in labeled if rec["label"] == "A" and score_activity(rec) >= 2
    ]
    int_inactive = [
        rec for rec in labeled if rec["label"] == "B" and score_inactivity(rec) >= 2
    ]
    fp_active = [
        rec for rec in labeled if rec["label"] == "B" and score_activity(rec) >= 3
    ]
    fn_inactive = [
        rec for rec in labeled if rec["label"] == "A" and score_inactivity(rec) >= 3
    ]
    true_active.sort(key=score_activity, reverse=True)
    int_inactive.sort(key=score_inactivity, reverse=True)
    fp_active.sort(key=score_activity, reverse=True)
    fn_inactive.sort(key=score_inactivity, reverse=True)
    return {
        "active_true_target": pack(true_active[0] if true_active else None),
        "inactive_intentional_blank": pack(int_inactive[0] if int_inactive else None),
        "false_positive_despite_activity": pack(fp_active[0] if fp_active else None),
        "false_negative_despite_inactivity": pack(fn_inactive[0] if fn_inactive else None),
    }


def _interpret(
    packed: dict[str, Any],
    monotonic: dict[str, Any],
    autopsy: list[dict[str, Any]],
    baselines: dict[str, Any],
) -> dict[str, Any]:
    base = packed["ANY_POINT"]["target_precision"] or 0.0
    eq2 = baselines["point_consumer_classes"][">=2"]["target_precision"]
    material = []
    for name in CONJUNCTIONS:
        prec = packed[name]["target_precision"]
        n = packed[name]["binary_selected"]
        books = packed[name]["task_coverage"]["workbooks_with_ge1_true"]
        if prec is None or n < 30:
            continue
        if prec >= base + 0.05 and books >= 3:
            material.append({"name": name, "precision": prec, "n": n, "books": books})
    directional = []
    broken = []
    for name, rec in monotonic.items():
        if rec["expected"] == "measure":
            continue
        if rec["on_selected_binary"] < 30:
            continue
        if rec["pooled_matches_expected"] and len(rec["inconsistent_workbooks"]) <= 2:
            directional.append(name)
        elif not rec["pooled_matches_expected"] or len(rec["inconsistent_workbooks"]) >= 3:
            broken.append(name)
    autopsy_explained = []
    autopsy_miss = []
    classes_seen = set()
    for item in autopsy:
        inactive = item["inactivity_evidence"]
        if inactive:
            autopsy_explained.append(item["cell_id"])
            classes_seen.add(item["class"])
        else:
            autopsy_miss.append(item["cell_id"])
    if (
        material
        and len(directional) >= 6
        and len(broken) <= 3
        and len(classes_seen) >= 3
        and any((row["precision"] or 0) >= (eq2 or 0) for row in material)
    ):
        gate = "strong_support"
        conclusion = (
            "Role liveness / regime is a useful higher-level relation that "
            "should be represented explicitly."
        )
    elif directional or material or len(classes_seen) >= 2:
        gate = "partial_heterogeneous_support"
        conclusion = (
            "Liveness is useful as a family of typed relations, not a single latent variable."
        )
    else:
        gate = "weak_support"
        conclusion = "Slot liveness/regime is not the missing abstraction."
    return {
        "gate": gate,
        "conclusion": conclusion,
        "material_selectors": material,
        "directional_predicates": directional,
        "broken_or_heterogeneous": broken,
        "autopsy_with_inactivity_evidence": autopsy_explained,
        "autopsy_without_inactivity_evidence": autopsy_miss,
        "autopsy_classes_with_inactivity_evidence": sorted(classes_seen),
    }


def _row(name: str, stats: dict[str, Any]) -> str:
    cov = stats["task_coverage"]
    return (
        f"| {name} | {stats['binary_selected']} | {stats['A_golden_formula']} | "
        f"{stats['B_intended_blank']} | {stats['C_golden_value']} | "
        f"{_pct(stats['target_precision'])} | {_pct(stats['recall_in_any_point'])} | "
        f"{cov['workbooks_with_ge1_true']} | {cov['workbooks_with_ge5_true']} |"
    )


def _book_table(stats: dict[str, Any]) -> list[str]:
    lines = [
        "| task | selected | true | precision |",
        "|------|----------|------|-----------|",
    ]
    for tid, n in stats["task_coverage"]["binary_by_task"].items():
        a = stats["task_coverage"]["true_by_task"][tid]
        lines.append(f"| {tid} | {n} | {a} | {_pct(_rate(a, n))} |")
    return lines


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Slot liveness / regime diagnostic",
        "",
        f"**{report['label']}**",
        f"**{report['not']}**",
        "",
        "Goldens were not used in feature construction.",
        "",
        f"ANY_POINT n={report['n_any_point']}. Freeze runtime {report['freeze_runtime_s']['all']}s. "
        f"Evaluate runtime {report['runtime_s']}s.",
        "",
        "## Reused vs newly computed",
        "",
        "Reused:",
        *[f"- {item}" for item in report["reused"]],
        "",
        "Newly computed:",
        *[f"- {item}" for item in report["newly_computed"]],
        "",
        "## Stored baselines on the same frozen 12",
        "",
        f"- ANY_POINT {report['stored_baselines']['ANY_POINT']['target_precision']} "
        f"(n={report['stored_baselines']['ANY_POINT']['selected']})",
        f"- POINT_ONLY {report['stored_baselines']['POINT_ONLY']['target_precision']}",
        f"- ANY_POINT + ≥2 consumer classes "
        f"{report['stored_baselines']['ANY_POINT + >=2 consumer classes']['target_precision']}",
        f"- Count match vs stored ANY_POINT: {report['any_point_count_match']}",
        "",
        "## Atomic predicates",
        "",
        "| predicate | selected | A | B | C | precision | recall | ≥1 true | ≥5 true |",
        "|-----------|----------|---|---|---|-----------|--------|---------|---------|",
        _row("ANY_POINT", report["ANY_POINT"]),
    ]
    for name in ATOMIC:
        lines.append(_row(name, report["atomic"][name]))
    lines += [
        "",
        "## L1–L9 conjunctions",
        "",
        "| selector | selected | A | B | C | precision | recall | ≥1 true | ≥5 true |",
        "|----------|----------|---|---|---|-----------|--------|---------|---------|",
    ]
    for name in CONJUNCTIONS:
        lines.append(_row(name, report["conjunctions"][name]))
    lines += [
        "",
        "## Per-workbook L1 / L4 / L5 / L8 / L9",
        "",
    ]
    for name in ("L1", "L4", "L5", "L8", "L9"):
        lines += [f"### {name}", ""] + _book_table(report["conjunctions"][name]) + [""]
    lines += ["## Monotonic / directional", ""]
    lines += [
        "| predicate | expected | on precision | Δ vs ANY_POINT | pooled match | inconsistent books |",
        "|-----------|----------|--------------|----------------|--------------|--------------------|",
    ]
    for name, rec in report["monotonic"].items():
        lines.append(
            f"| {name} | {rec['expected']} | {_pct(rec['on_precision'])} | "
            f"{rec['delta_vs_any_point']} | {rec['pooled_matches_expected']} | "
            f"{', '.join(rec['inconsistent_workbooks']) or '—'} |"
        )
    lines += ["", "## Autopsy-class coverage", ""]
    for item in report["autopsy"]:
        lines.append(
            f"- `{item['cell_id']}` ({item['class']}): in_any_point={item['in_any_point']} "
            f"role={item['eval_role']} inactivity={item['inactivity_evidence']} "
            f"activity={item['activity_evidence']}"
        )
    lines += ["", "## Examples", ""]
    for key, rec in report["examples"].items():
        if rec is None:
            lines.append(f"- {key}: none")
            continue
        lines.append(
            f"- {key}: `{rec['cell_id']}` {rec['eval_role']} "
            f"activity={rec['activity_score']} inactivity={rec['inactivity_score']} "
            f"fired={rec['fired']}"
        )
    interp = report["interpretation"]
    lines += [
        "",
        "## Conclusion",
        "",
        f"**{interp['gate']}**",
        "",
        interp["conclusion"],
        "",
        f"Material selectors: {interp['material_selectors']}",
        f"Directional: {interp['directional_predicates']}",
        f"Broken/heterogeneous: {interp['broken_or_heterogeneous']}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "evaluate", "all"), default="all", nargs="?")
    args = parser.parse_args()
    if args.phase in ("freeze", "all"):
        cmd_freeze()
    if args.phase in ("evaluate", "all"):
        cmd_evaluate()


if __name__ == "__main__":
    main()
