#!/usr/bin/env python3
"""Offline diagnostic of hierarchical block extent vs role extent on frozen C1.

Phases:
  freeze   — exact C1 list + A–G / H1–H10 (no goldens)
  evaluate — labels, extent_delta, block controls, golden stripe characterization
  all      — freeze then evaluate

Reuses formula-frontier-probe C1. No agents, workbook writes, official scorer,
formula reconstruction, or learned scores.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address, formula_text  # noqa: E402
from formula_dependency_selection import build_graph  # noqa: E402
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
from formula_frontier import build_extent, load_schema_layers  # noqa: E402
from formula_hierarchy import (  # noqa: E402
    ATOMIC,
    CONJUNCTIONS,
    CORE_ATOMIC,
    DEFINITIONS,
    DELTA_BINS,
    SIZE_BINS,
    features_for_cell,
)
from formula_liveness import build_occupancy_peers  # noqa: E402
from formula_target_selection import SLICE_LABEL, SLICE_NAME, SLICE_NOT  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()

DEP_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-dependency-selection-probe"
)
LIVE_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-liveness-probe"
)
FRONT_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-frontier-probe"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-hierarchy-probe"
)

KNOWN_CASES = (
    {"cell_id": "15_04:Consol_annual!T139", "note": "intentional spacer / isolated role"},
    {"cell_id": "17_03:Financials!K38", "note": "regime handoff; not expected in C1"},
    {"cell_id": "17_03:Financials!L38", "note": "regime handoff; not expected in C1"},
    {"cell_id": "14_05:DCF_Income Approach!D10", "note": "true target"},
    {"cell_id": "03_01:Income Statement!V7", "note": "true synchronized-stop example"},
    {"cell_id": "15_04:IS_BS_CF!AC48", "note": "intentional blank despite continuation"},
)

DIRECTION = {
    "A1": "increase",
    "A2": "increase",
    "A3": "decrease",
    "A4": "measure",
    "B1": "increase",
    "B2": "decrease",
    "B3": "increase",
    "Role1": "increase",
    "Role2": "decrease",
    "Role2_d4": "decrease",
    "Role2_d8": "decrease",
    "Role3": "measure",
    "D1": "increase",
    "D2": "decrease",
    "D3": "increase",
    "E1": "increase",
    "E2": "decrease",
    "E3": "increase",
    "E4": "decrease",
    "F1": "increase",
    "F2": "decrease",
    "F3": "measure",
    "G1": "increase",
    "G2": "measure",
    "G3": "increase",
    "H1": "increase",
    "H2": "increase",
    "H3": "increase",
    "H4": "increase",
    "H5": "increase",
    "H6": "decrease",
    "H7": "decrease",
    "H8": "decrease",
    "H9": "increase",
    "H10": "decrease",
}


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
    return {
        "selected": stats["selected"],
        "binary_selected": binary,
        "A_golden_formula": true_n,
        "B_intended_blank": stats["B"],
        "C_golden_value": stats["C"],
        "target_precision": _rate(true_n, binary),
        "recall_in_c1": _rate(true_n, n_true_pop),
        "recall_vs_all_golden_formula_blanks": _rate(true_n, n_targets),
        "false_positive_burden": stats["B"],
        "task_coverage": {
            "workbooks_with_ge1_true": len(covered),
            "workbooks_with_ge5_true": len(covered5),
            "n_workbooks": n_tasks,
            "true_by_task": stats["true_by_task"],
            "selected_by_task": stats["selected_by_task"],
            "binary_by_task": stats["binary_by_task"],
            "precision_by_task": {
                tid: _rate(stats["true_by_task"][tid], n_bin)
                for tid, n_bin in stats["binary_by_task"].items()
            },
        },
    }


def _cell_id(task_id: str, sheet: str, col: int, row: int) -> str:
    return f"{task_id}:{sheet}!{a1_address(col, row)}"


def cmd_freeze() -> dict[str, Any]:
    slice_doc = _load_slice()
    front = json.loads((FRONT_OUT / "candidate_freeze.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    OUT.mkdir(parents=True, exist_ok=True)
    freeze: dict[str, Any] = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "slice": SLICE_NAME,
        "population": "frontier_C1",
        "definitions": DEFINITIONS,
        "conjunctions_predeclared": DEFINITIONS["conjunctions"],
        "reused": [
            "fm-target-selection-probe-12 workbook IDs",
            "formula-frontier-probe exact C1 candidate list, last_active_col, last_formula_col",
            "build_graph occupancy, formula classes, point_rev",
            "occupancy-vector homology and homologous_peers",
            "header/merge schema loader from formula_frontier",
        ],
        "newly_computed": [
            "local qualifying row groups ±2/±4/±8/±16",
            "modal block frontier M and A1–A4",
            "schema continuation beyond M (B)",
            "role vs block extent_delta (Role1–Role3)",
            "formula-block coherence D1–D3",
            "homologous block/role extent E1–E4",
            "post-frontier stripe F1–F3",
            "block-level point demand G1–G3",
            "H1–H10",
        ],
        "runtime_s": {},
        "tasks": {},
        "n_c1": 0,
    }
    t0 = time.perf_counter()
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        source = _input_path(task)
        front_cells = front["tasks"][task_id]["cells"]
        print(f"GRAPH {task_id} C1={len(front_cells)}", flush=True)
        started = time.perf_counter()
        graph = build_graph(source)
        graph_s = time.perf_counter() - started
        schema_started = time.perf_counter()
        schema = load_schema_layers(source) if front_cells else {}
        schema_s = time.perf_counter() - schema_started
        wanted = {(c["sheet"], c["col"], c["row"]) for c in front_cells}
        occ = build_occupancy_peers(graph.occupancy, wanted) if wanted else None
        extents = {
            title: build_extent(grid)
            for title, grid in graph.occupancy.items()
            if any(key[0] == title for key in wanted)
        }
        feat_started = time.perf_counter()
        class_cache: dict[str, Any] = {}
        cells = []
        for src in front_cells:
            key = (src["sheet"], src["col"], src["row"])
            feat = features_for_cell(
                graph,
                key,
                occ,
                extents[key[0]],
                schema.get(key[0]),
                class_cache,
                {
                    "last_active_col": src.get("last_active_col"),
                    "last_formula_col": src.get("last_formula_col"),
                },
            )
            feat["cell_id"] = _cell_id(task_id, key[0], key[1], key[2])
            cells.append(feat)
        feat_s = time.perf_counter() - feat_started
        elapsed = time.perf_counter() - started
        freeze["runtime_s"][task_id] = {
            "graph": round(graph_s, 3),
            "schema": round(schema_s, 3),
            "features": round(feat_s, 3),
            "total": round(elapsed, 3),
        }
        freeze["tasks"][task_id] = {
            "family": item["family"],
            "n_c1": len(cells),
            "cells": cells,
        }
        freeze["n_c1"] += len(cells)
        print(
            f"  C1={len(cells)} graph={graph_s:.1f}s schema={schema_s:.1f}s feat={feat_s:.1f}s",
            flush=True,
        )
        del graph, occ, schema, extents, cells
    freeze["runtime_s"]["all"] = round(time.perf_counter() - t0, 3)
    dest = OUT / "candidate_freeze.json"
    dest.write_text(json.dumps(freeze) + "\n")
    print(f"FREEZE {dest} n={freeze['n_c1']} runtime={freeze['runtime_s']['all']}s", flush=True)
    return freeze


def cmd_evaluate() -> dict[str, Any]:
    slice_doc = _load_slice()
    freeze = json.loads((OUT / "candidate_freeze.json").read_text())
    baselines = json.loads((DEP_OUT / "point_range_decomposition.json").read_text())
    live_eval = json.loads((LIVE_OUT / "evaluation.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    n_tasks = len(slice_doc["tasks"])
    started = time.perf_counter()
    names = ("C1",) + ATOMIC + CONJUNCTIONS
    groups = {name: _empty_stats() for name in names}
    n_targets = 0
    n_true_pop = 0
    labeled: list[dict[str, Any]] = []
    golden_stripe_blocks: list[dict[str, Any]] = []

    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        print(f"EVAL {task_id}", flush=True)
        golden_cells = _cell_map(_golden_path(task))
        input_cells = _cell_map(_input_path(task))
        targets = _blank_formula_targets(input_cells, golden_cells)
        n_targets += len(targets)
        for stats in groups.values():
            _ensure_task(stats, task_id)
        block_acc: dict[tuple[str, int | None], dict[str, Any]] = {}
        for feat in freeze["tasks"][task_id]["cells"]:
            key = (feat["sheet"], feat["col"], feat["row"])
            label = _label(golden_cells.get(key))
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
                "M": feat["M"],
                "delta": feat["delta"],
                "delta_bin": feat["delta_bin"],
                "size_bin": feat["size_bin"],
                "n_block": feat["n_block"],
                "qual_rows": feat["qual_rows"],
                "Role": feat["Role"],
                "A": feat["A"],
                "D": feat["D"],
                "E": feat["E"],
                "F": feat["F"],
                "G": feat["G"],
            }
            labeled.append(rec)
            _add(groups["C1"], task_id, label)
            for name in ATOMIC + CONJUNCTIONS:
                if feat["flags"].get(name):
                    _add(groups[name], task_id, label)
            bkey = (feat["sheet"], feat["M"])
            acc = block_acc.setdefault(
                bkey,
                {"rows": set(), "A": 0, "B": 0, "C": 0, "n_block": feat["n_block"], "qual": set()},
            )
            acc[label] += 1
            acc["rows"].add(feat["row"])
            acc["qual"].update(feat["qual_rows"])
        for (sheet, m), acc in block_acc.items():
            if m is None:
                continue
            n_rows_edited = 0
            n_formula_cells = 0
            max_col = m
            for row in acc["qual"]:
                row_hit = False
                for col in range(m + 1, m + 9):
                    if formula_text(golden_cells.get((sheet, col, row))):
                        n_formula_cells += 1
                        row_hit = True
                        max_col = max(max_col, col)
                if row_hit:
                    n_rows_edited += 1
            n_qual = max(len(acc["qual"]), 1)
            if n_rows_edited == 0:
                pattern = "no_continuation"
            elif n_rows_edited == 1:
                pattern = "single_role_edit"
            elif n_rows_edited / n_qual >= 0.75:
                pattern = "multi_row_continuation_stripe"
            else:
                pattern = "mixed_pattern"
            golden_stripe_blocks.append(
                {
                    "task_id": task_id,
                    "sheet": sheet,
                    "M": m,
                    "n_c1": acc["A"] + acc["B"] + acc["C"],
                    "A": acc["A"],
                    "B": acc["B"],
                    "n_qual_rows": len(acc["qual"]),
                    "n_rows_edited": n_rows_edited,
                    "n_formula_cells": n_formula_cells,
                    "columns_extended": max(0, max_col - m),
                    "pattern": pattern,
                    "within_block_precision": _rate(acc["A"], acc["A"] + acc["B"]),
                }
            )
        print(f"  C1={freeze['tasks'][task_id]['n_c1']} A={groups['C1']['true_by_task'][task_id]}", flush=True)
        del golden_cells, input_cells

    packed = {name: _pack(stats, n_true_pop, n_targets, n_tasks) for name, stats in groups.items()}
    base = packed["C1"]["target_precision"]
    monotonic = _monotonic(packed, labeled, base)
    delta_table = _delta_table(labeled)
    size_table = _size_table(labeled)
    block_conc = _block_concentration(golden_stripe_blocks)
    stripe = _stripe_summary(golden_stripe_blocks)
    autopsy = _known_cases(freeze, labeled)
    examples = _examples(labeled)
    interpretation = _interpret(packed, monotonic, delta_table, stripe, autopsy)
    stored_c1 = live_eval["atomic"]["C1"]
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
        "n_c1": freeze["n_c1"],
        "n_true_targets_in_c1": n_true_pop,
        "stored_baselines": {
            "C1": {
                "binary_selected": stored_c1["binary_selected"],
                "A_golden_formula": stored_c1["A_golden_formula"],
                "B_intended_blank": stored_c1["B_intended_blank"],
                "target_precision": stored_c1["target_precision"],
            },
            "ANY_POINT": {
                "target_precision": baselines["partitions"]["ANY_POINT"]["target_precision"]
            },
            "POINT_ONLY": {
                "target_precision": baselines["partitions"]["POINT_ONLY"]["target_precision"]
            },
            "ANY_POINT + >=2 consumer classes": {
                "target_precision": baselines["point_consumer_classes"][">=2"]["target_precision"]
            },
        },
        "c1_count_match": freeze["n_c1"] == stored_c1["selected"],
        "definitions": DEFINITIONS,
        "atomic": {name: packed[name] for name in ATOMIC},
        "conjunctions": {name: packed[name] for name in CONJUNCTIONS},
        "C1": packed["C1"],
        "extent_delta": delta_table,
        "block_size": size_table,
        "monotonic": monotonic,
        "golden_stripes": stripe,
        "block_concentration": block_conc,
        "known_cases": autopsy,
        "examples": examples,
        "interpretation": interpretation,
    }
    dest = OUT / "evaluation.json"
    dest.write_text(json.dumps(report) + "\n")
    md = OUT / "evaluation.md"
    md.write_text(_render(report) + "\n")
    print(f"EVAL {dest}", flush=True)
    print(f"interpretation={interpretation['gate']}", flush=True)
    return report


def _monotonic(packed: dict[str, Any], labeled: list[dict[str, Any]], base: float | None) -> dict[str, Any]:
    names = list(CORE_ATOMIC + CONJUNCTIONS)
    by_task: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"A": 0, "B": 0, "offA": 0, "offB": 0})
    )
    for rec in labeled:
        if rec["label"] not in ("A", "B"):
            continue
        for name in names:
            bucket = by_task[name][rec["task_id"]]
            if rec["flags"].get(name):
                bucket[rec["label"]] += 1
            else:
                bucket["off" + rec["label"]] += 1
    out: dict[str, Any] = {}
    for name in names:
        on = packed[name]
        expected = DIRECTION.get(name, "measure")
        on_rate = on["target_precision"]
        delta = None if on_rate is None or base is None else round(on_rate - base, 4)
        inconsistent = []
        for task_id, bucket in by_task[name].items():
            on_bin = bucket["A"] + bucket["B"]
            off_bin = bucket["offA"] + bucket["offB"]
            on_p = _rate(bucket["A"], on_bin)
            off_p = _rate(bucket["offA"], off_bin)
            if on_bin < 8 or off_bin < 8 or on_p is None or off_p is None:
                continue
            if expected == "increase" and on_p < off_p - 0.02:
                inconsistent.append(task_id)
            elif expected == "decrease" and on_p > off_p + 0.02:
                inconsistent.append(task_id)
        observed = "measure"
        if expected in ("increase", "decrease") and delta is not None:
            if abs(delta) < 0.02:
                observed = "flat"
            elif delta > 0:
                observed = "increase"
            else:
                observed = "decrease"
        out[name] = {
            "expected": expected,
            "on_precision": on_rate,
            "on_selected_binary": on["binary_selected"],
            "delta_vs_c1": delta,
            "pooled_matches_expected": expected == "measure" or observed == expected,
            "observed_pooled": observed,
            "inconsistent_workbooks": inconsistent,
        }
    out["_strength"] = {
        "A1_share_t1": [
            {
                "name": name,
                "n": packed[name]["binary_selected"],
                "precision": packed[name]["target_precision"],
                "recall": packed[name]["recall_in_c1"],
            }
            for name in ("A1_p50_t1", "A1_p75_t1", "A1_p90_t1")
        ],
        "D1_k": [
            {
                "name": name,
                "n": packed[name]["binary_selected"],
                "precision": packed[name]["target_precision"],
                "recall": packed[name]["recall_in_c1"],
            }
            for name in ("D1_k2", "D1_k3", "D1_k5")
        ],
        "F1_share": [
            {
                "name": name,
                "n": packed[name]["binary_selected"],
                "precision": packed[name]["target_precision"],
                "recall": packed[name]["recall_in_c1"],
            }
            for name in ("F1_p50", "F1_p75", "F1_p90")
        ],
        "G1_k": [
            {
                "name": name,
                "n": packed[name]["binary_selected"],
                "precision": packed[name]["target_precision"],
                "recall": packed[name]["recall_in_c1"],
            }
            for name in ("G1_k2", "G1_k3", "G1_k5")
        ],
        "role_shortfall": [
            {
                "name": name,
                "n": packed[name]["binary_selected"],
                "precision": packed[name]["target_precision"],
                "recall": packed[name]["recall_in_c1"],
            }
            for name in ("Role2", "Role2_d4", "Role2_d8")
        ],
    }
    return out


def _bin_pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    a = sum(1 for r in rows if r["label"] == "A")
    b = sum(1 for r in rows if r["label"] == "B")
    books = sorted({r["task_id"] for r in rows if r["label"] == "A"})
    return {
        "selected": a + b,
        "A": a,
        "B": b,
        "precision": _rate(a, a + b),
        "n_books_with_true": len(books),
    }


def _delta_table(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    by_bin: dict[str, list] = defaultdict(list)
    aligned, shorter, longer = [], [], []
    deltas = {"TRUE_TARGET": [], "INTENTIONAL_BLANK": []}
    for rec in labeled:
        if rec["label"] not in ("A", "B"):
            continue
        if rec["delta_bin"]:
            by_bin[rec["delta_bin"]].append(rec)
        if rec["flags"].get("Role1"):
            aligned.append(rec)
        if rec["flags"].get("Role2"):
            shorter.append(rec)
        if rec["flags"].get("Role3"):
            longer.append(rec)
        if rec["delta"] is not None:
            deltas[rec["eval_role"]].append(rec["delta"])
    def summ(vals):
        if not vals:
            return {"n": 0}
        ordered = sorted(vals)
        n = len(ordered)
        return {
            "n": n,
            "mean": round(sum(ordered) / n, 4),
            "p25": ordered[n // 4],
            "median": ordered[n // 2],
            "p75": ordered[(3 * n) // 4],
        }
    return {
        "bins": {name: _bin_pack(by_bin.get(name, [])) for name, _lo, _hi in DELTA_BINS},
        "role_aligned": _bin_pack(aligned),
        "role_shorter": _bin_pack(shorter),
        "role_longer": _bin_pack(longer),
        "delta_summary": {role: summ(vals) for role, vals in deltas.items()},
    }


def _size_table(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    by_bin: dict[str, list] = defaultdict(list)
    h1_by: dict[str, list] = defaultdict(list)
    h6_by: dict[str, list] = defaultdict(list)
    for rec in labeled:
        if rec["label"] not in ("A", "B"):
            continue
        by_bin[rec["size_bin"]].append(rec)
        if rec["flags"].get("H1"):
            h1_by[rec["size_bin"]].append(rec)
        if rec["flags"].get("H6"):
            h6_by[rec["size_bin"]].append(rec)
    size_names = ("lt2",) + tuple(name for name, _lo, _hi in SIZE_BINS)
    return {
        "all": {name: _bin_pack(by_bin.get(name, [])) for name in size_names},
        "H1": {name: _bin_pack(h1_by.get(name, [])) for name in size_names},
        "H6": {name: _bin_pack(h6_by.get(name, [])) for name in size_names},
    }


def _stripe_summary(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = Counter(b["pattern"] for b in blocks)
    with_edits = [b for b in blocks if b["n_rows_edited"] >= 1]
    return {
        "n_distinct_frontiers": len(blocks),
        "n_with_golden_edit": len(with_edits),
        "pattern_counts": dict(patterns),
        "rows_edited": {
            "mean": round(sum(b["n_rows_edited"] for b in blocks) / len(blocks), 4) if blocks else None,
            "median": sorted(b["n_rows_edited"] for b in blocks)[len(blocks) // 2] if blocks else None,
        },
        "columns_extended_when_edited": {
            "median": sorted(b["columns_extended"] for b in with_edits)[len(with_edits) // 2]
            if with_edits
            else None
        },
    }


def _block_concentration(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    rates = [b["within_block_precision"] for b in blocks if b["A"] + b["B"] >= 5 and b["within_block_precision"] is not None]
    nearly = [b for b in blocks if (b["within_block_precision"] or 0) >= 0.9 and b["A"] + b["B"] >= 5]
    true_near = sum(b["A"] for b in nearly)
    true_all = sum(b["A"] for b in blocks)
    return {
        "n_blocks_ge5": len(rates),
        "median_within_block_precision": sorted(rates)[len(rates) // 2] if rates else None,
        "mean_within_block_precision": round(sum(rates) / len(rates), 4) if rates else None,
        "n_nearly_all_golden": len(nearly),
        "share_of_true_from_nearly_all_golden": _rate(true_near, true_all),
        "true_in_nearly_all_golden": true_near,
        "true_all_blocks": true_all,
    }


def _known_cases(freeze: dict[str, Any], labeled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {rec["cell_id"]: rec for rec in labeled}
    freeze_ids = {feat["cell_id"] for task in freeze["tasks"].values() for feat in task["cells"]}
    out = []
    for spec in KNOWN_CASES:
        rec = by_id.get(spec["cell_id"])
        out.append(
            {
                **spec,
                "in_c1": spec["cell_id"] in freeze_ids,
                "eval_role": rec["eval_role"] if rec else None,
                "M": rec["M"] if rec else None,
                "delta": rec["delta"] if rec else None,
                "Role": rec["Role"] if rec else None,
                "H": {name: rec["flags"].get(name) for name in CONJUNCTIONS} if rec else None,
                "A1": rec["flags"].get("A1") if rec else None,
                "F1": rec["flags"].get("F1") if rec else None,
                "F2": rec["flags"].get("F2") if rec else None,
            }
        )
    return out


def _examples(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    def pack(rec):
        if rec is None:
            return None
        return {
            "cell_id": rec["cell_id"],
            "eval_role": rec["eval_role"],
            "M": rec["M"],
            "delta": rec["delta"],
            "n_block": rec["n_block"],
            "Role": rec["Role"],
            "H": [name for name in CONJUNCTIONS if rec["flags"].get(name)],
        }

    frontier_true = [r for r in labeled if r["label"] == "A" and r["flags"].get("H1")]
    role_blank = [r for r in labeled if r["label"] == "B" and r["flags"].get("H6")]
    fp = [r for r in labeled if r["label"] == "B" and r["flags"].get("H1") and r["flags"].get("H4")]
    fn = [r for r in labeled if r["label"] == "A" and r["flags"].get("H6") and r["flags"].get("H7")]
    frontier_true.sort(key=lambda r: (r["n_block"], -(r["delta"] or 0)), reverse=True)
    role_blank.sort(key=lambda r: abs(r["delta"] or 0), reverse=True)
    return {
        "true_at_block_frontier": pack(frontier_true[0] if frontier_true else None),
        "intentional_role_early_stop": pack(role_blank[0] if role_blank else None),
        "false_positive_block_frontier": pack(fp[0] if fp else None),
        "false_negative_role_absence": pack(fn[0] if fn else None),
    }


def _interpret(packed, monotonic, delta_table, stripe, autopsy) -> dict[str, Any]:
    base = packed["C1"]["target_precision"] or 0.0
    aligned = delta_table["role_aligned"]["precision"]
    shorter = delta_table["role_shorter"]["precision"]
    h1 = packed["H1"]["target_precision"]
    h6 = packed["H6"]["target_precision"]
    h1_books = packed["H1"]["task_coverage"]["workbooks_with_ge1_true"]
    h6_books = packed["H6"]["task_coverage"]["workbooks_with_ge1_true"]
    stripe_ok = (stripe["pattern_counts"].get("multi_row_continuation_stripe") or 0) >= 3
    aligned_up = aligned is not None and aligned >= base + 0.05
    shorter_down = shorter is not None and shorter <= base - 0.05
    if aligned_up and shorter_down and h1_books >= 3 and h6_books >= 3 and stripe_ok:
        gate = "strong_support"
        conclusion = (
            "Hierarchical block extent and role extent are mechanically recoverable "
            "relations relevant to missing-computation detection."
        )
    elif aligned_up or shorter_down or (h1 is not None and abs((h1 or 0) - base) >= 0.05):
        gate = "partial_heterogeneous_support"
        conclusion = (
            "Block extent / role extent is one useful family of typed structural "
            "relations, but not a universal spreadsheet abstraction."
        )
    else:
        gate = "weak_support"
        conclusion = (
            "The apparent synchronized-frontier signal does not support a genuine "
            "block-vs-role representation."
        )
    return {
        "gate": gate,
        "conclusion": conclusion,
        "aligned_precision": aligned,
        "shorter_precision": shorter,
        "H1_precision": h1,
        "H6_precision": h6,
        "stripe_patterns": stripe["pattern_counts"],
    }


def _row(name: str, stats: dict[str, Any]) -> str:
    cov = stats["task_coverage"]
    return (
        f"| {name} | {stats['binary_selected']} | {stats['A_golden_formula']} | "
        f"{stats['B_intended_blank']} | {_pct(stats['target_precision'])} | "
        f"{_pct(stats['recall_in_c1'])} | {cov['workbooks_with_ge1_true']} | "
        f"{cov['workbooks_with_ge5_true']} |"
    )


def _book_table(stats: dict[str, Any]) -> list[str]:
    lines = ["| task | selected | true | precision |", "|------|----------|------|-----------|"]
    for tid, n in stats["task_coverage"]["binary_by_task"].items():
        a = stats["task_coverage"]["true_by_task"][tid]
        lines.append(f"| {tid} | {n} | {a} | {_pct(_rate(a, n))} |")
    return lines


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Hierarchical block extent vs role extent",
        "",
        f"**{report['label']}**",
        f"**{report['not']}**",
        "",
        f"C1 n={report['n_c1']}. Freeze {report['freeze_runtime_s']['all']}s. Eval {report['runtime_s']}s.",
        "",
        f"C1 baseline {report['stored_baselines']['C1']['target_precision']} "
        f"(A={report['stored_baselines']['C1']['A_golden_formula']}, "
        f"binary n={report['stored_baselines']['C1']['binary_selected']}). "
        f"Count match: {report['c1_count_match']}",
        "",
        "## Atomic",
        "",
        "| predicate | selected | A | B | precision | recall | ≥1 true | ≥5 true |",
        "|-----------|----------|---|---|-----------|--------|---------|---------|",
        _row("C1", report["C1"]),
    ]
    for name in CORE_ATOMIC:
        lines.append(_row(name, report["atomic"][name]))
    lines += [
        "",
        "## H1–H10",
        "",
        "| selector | selected | A | B | precision | recall | ≥1 true | ≥5 true |",
        "|----------|----------|---|---|-----------|--------|---------|---------|",
    ]
    for name in CONJUNCTIONS:
        lines.append(_row(name, report["conjunctions"][name]))
    lines += ["", "## extent_delta bins", ""]
    lines.append("| bin | selected | A | B | precision |")
    lines.append("|-----|----------|---|---|-----------|")
    for name, stats in report["extent_delta"]["bins"].items():
        lines.append(
            f"| {name} | {stats['selected']} | {stats['A']} | {stats['B']} | {_pct(stats['precision'])} |"
        )
    ra, rs, rl = (
        report["extent_delta"]["role_aligned"],
        report["extent_delta"]["role_shorter"],
        report["extent_delta"]["role_longer"],
    )
    lines += [
        "",
        f"Role aligned |Δ|≤1: n={ra['selected']} precision={_pct(ra['precision'])}",
        f"Role shorter Δ≤-2: n={rs['selected']} precision={_pct(rs['precision'])}",
        f"Role longer Δ≥+2: n={rl['selected']} precision={_pct(rl['precision'])}",
        "",
        "## Block-size control",
        "",
    ]
    for split in ("all", "H1", "H6"):
        lines.append(f"### {split}")
        lines.append("| size | selected | A | precision |")
        lines.append("|------|----------|---|-----------|")
        for name, stats in report["block_size"][split].items():
            lines.append(
                f"| {name} | {stats['selected']} | {stats['A']} | {_pct(stats['precision'])} |"
            )
        lines.append("")
    lines += ["## Per-workbook H1 / H6 / Role1 / Role2", ""]
    for name, blob in (
        ("H1", report["conjunctions"]["H1"]),
        ("H6", report["conjunctions"]["H6"]),
        ("Role1", report["atomic"]["Role1"]),
        ("Role2", report["atomic"]["Role2"]),
    ):
        lines += [f"### {name}", ""] + _book_table(blob) + [""]
    lines += [
        "## Golden stripe characterization",
        "",
        str(report["golden_stripes"]),
        "",
        "## Block concentration",
        "",
        str(report["block_concentration"]),
        "",
        "## Known cases",
        "",
    ]
    for item in report["known_cases"]:
        lines.append(
            f"- `{item['cell_id']}` in_c1={item['in_c1']} role={item['eval_role']} "
            f"M={item['M']} delta={item['delta']} Role={item['Role']} H={item['H']}"
        )
    lines += ["", "## Examples", ""]
    for key, rec in report["examples"].items():
        lines.append(f"- {key}: {rec}")
    interp = report["interpretation"]
    lines += ["", "## Conclusion", "", f"**{interp['gate']}**", "", interp["conclusion"]]
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
