#!/usr/bin/env python3
"""Offline diagnostic of unfinished continuation vs legitimate termination on C1.

Phases:
  freeze   — frozen C1 candidates + A–G predicates (no goldens)
  evaluate — golden labels, Q1–Q9, monotonicity, autopsy coverage
  all      — freeze then evaluate

Reuses fm-target-selection-probe-12, the liveness C1 list, and the reverse-A1
graph. No agents, workbook writes, official scorer, formula reconstruction,
or learned scores.
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

from fingerprint import a1_address  # noqa: E402
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
from formula_frontier import (  # noqa: E402
    ATOMIC,
    CONJUNCTIONS,
    CORE_ATOMIC,
    DEFINITIONS,
    build_extent,
    features_for_cell,
    load_schema_layers,
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
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-frontier-probe"
)

AUTOPSY_CELLS = (
    {"cell_id": "15_04:Work Sheet!AP124", "class": "lattice unused slot"},
    {"cell_id": "15_04:Work Sheet!AP140", "class": "lattice unused slot"},
    {"cell_id": "07_05:Construction Schedule!CQ57", "class": "schedule live-window end"},
    {"cell_id": "15_04:Consol_annual!T139", "class": "spacer row"},
    {"cell_id": "17_03:Financials!K38", "class": "regime handoff"},
    {"cell_id": "17_03:Financials!L38", "class": "regime handoff"},
)

DIRECTION = {
    "A1": "increase",
    "A2": "decrease",
    "A3": "increase",
    "B1": "increase",
    "B2": "decrease",
    "B3": "increase",
    "Hom1": "increase",
    "Hom2": "decrease",
    "Hom3": "increase",
    "D1": "increase",
    "D2": "increase",
    "D3": "decrease",
    "D4": "increase",
    "E1": "increase",
    "E2": "decrease",
    "E3": "measure",
    "E4": "decrease",
    "F1": "decrease",
    "F2": "increase",
    "F3": "decrease",
    "G_first_blank": "increase",
    "G_resume": "measure",
    "G_to_extent": "measure",
    "Q1": "increase",
    "Q2": "decrease",
    "Q3": "increase",
    "Q4": "decrease",
    "Q5": "increase",
    "Q6": "decrease",
    "Q7": "increase",
    "Q8": "decrease",
    "Q9": "increase",
}

CONT_EVIDENCE = ("Q1", "Q3", "Q5", "Q7", "Q9", "A1", "A3", "B1", "Hom1", "D2", "D4", "E1", "F2")
TERM_EVIDENCE = ("Q2", "Q4", "Q6", "Q8", "A2", "B2", "Hom2", "D3", "E2", "F1", "F3")


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
    precision_by_task = {
        tid: _rate(stats["true_by_task"][tid], n_bin)
        for tid, n_bin in stats["binary_by_task"].items()
    }
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
            "precision_by_task": precision_by_task,
        },
    }


def _cell_id(task_id: str, sheet: str, col: int, row: int) -> str:
    return f"{task_id}:{sheet}!{a1_address(col, row)}"


def _load_liveness_freeze() -> dict[str, Any]:
    return json.loads((LIVE_OUT / "candidate_freeze.json").read_text())


def cmd_freeze() -> dict[str, Any]:
    slice_doc = _load_slice()
    live = _load_liveness_freeze()
    by_id = {task["id"]: task for task in _task_list()}
    OUT.mkdir(parents=True, exist_ok=True)
    freeze: dict[str, Any] = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "slice": SLICE_NAME,
        "population": "liveness_C1",
        "definitions": DEFINITIONS,
        "conjunctions_predeclared": DEFINITIONS["conjunctions"],
        "reused": [
            "fm-target-selection-probe-12 workbook IDs",
            "formula-liveness-probe C1 candidate list, last_active_col, blank_tail",
            "build_graph occupancy and formula classes (same reverse-A1 graph)",
            "homologous_peers and occupancy-vector homology",
            "point_range_decomposition baselines (evaluation only)",
        ],
        "newly_computed": [
            "sibling last-ACTIVE / last-FORMULA continuation (A)",
            "header/merge/period-sequence schema facts (B)",
            "homologous extent Hom1–Hom3",
            "predecessor family D1–D4 (D4 eq_id existence only)",
            "point-consumer continuation E1–E4",
            "regional termination F1–F3",
            "blank-tail geometry G",
            "predeclared Q1–Q9",
        ],
        "runtime_s": {},
        "tasks": {},
        "n_c1": 0,
        "c1_flag_mismatch": 0,
    }
    t0 = time.perf_counter()
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        source = _input_path(task)
        live_cells = [
            feat for feat in live["tasks"][task_id]["cells"] if feat["flags"].get("C1")
        ]
        print(f"GRAPH {task_id} C1={len(live_cells)}", flush=True)
        started = time.perf_counter()
        graph = build_graph(source)
        graph_s = time.perf_counter() - started
        schema_started = time.perf_counter()
        schema = load_schema_layers(source)
        schema_s = time.perf_counter() - schema_started
        wanted = {(c["sheet"], c["col"], c["row"]) for c in live_cells}
        occ_started = time.perf_counter()
        occ = build_occupancy_peers(graph.occupancy, wanted)
        occ_s = time.perf_counter() - occ_started
        extents = {
            title: build_extent(grid)
            for title, grid in graph.occupancy.items()
            if any(key[0] == title for key in wanted)
        }
        feat_started = time.perf_counter()
        class_cache: dict[str, Any] = {}
        cells = []
        for live_feat in live_cells:
            key = (live_feat["sheet"], live_feat["col"], live_feat["row"])
            if key[0] not in graph.occupancy:
                freeze["c1_flag_mismatch"] += 1
                continue
            feat = features_for_cell(
                graph,
                key,
                occ,
                extents[key[0]],
                schema.get(key[0]),
                class_cache,
                live_feat.get("C") or {},
            )
            feat["cell_id"] = _cell_id(task_id, key[0], key[1], key[2])
            feat["n_point"] = live_feat.get("n_point")
            feat["n_point_eq"] = live_feat.get("n_point_eq")
            cells.append(feat)
        feat_s = time.perf_counter() - feat_started
        elapsed = time.perf_counter() - started
        freeze["runtime_s"][task_id] = {
            "graph": round(graph_s, 3),
            "schema": round(schema_s, 3),
            "occupancy_peers": round(occ_s, 3),
            "features": round(feat_s, 3),
            "total": round(elapsed, 3),
        }
        freeze["tasks"][task_id] = {
            "family": item["family"],
            "stratum": item["stratum"],
            "n_c1": len(cells),
            "cells": cells,
        }
        freeze["n_c1"] += len(cells)
        print(
            f"  C1={len(cells)} graph={graph_s:.1f}s schema={schema_s:.1f}s "
            f"peers={occ_s:.1f}s feat={feat_s:.1f}s",
            flush=True,
        )
        del graph, occ, schema, extents, cells
    freeze["runtime_s"]["all"] = round(time.perf_counter() - t0, 3)
    dest = OUT / "candidate_freeze.json"
    dest.write_text(json.dumps(freeze) + "\n")
    print(f"FREEZE {dest} n={freeze['n_c1']} runtime={freeze['runtime_s']['all']}s", flush=True)
    return freeze


def _load_freeze() -> dict[str, Any]:
    return json.loads((OUT / "candidate_freeze.json").read_text())


def _load_baselines() -> dict[str, Any]:
    return json.loads((DEP_OUT / "point_range_decomposition.json").read_text())


def _load_liveness_eval() -> dict[str, Any]:
    return json.loads((LIVE_OUT / "evaluation.json").read_text())


def _selector_names() -> tuple[str, ...]:
    return ("C1",) + ATOMIC + CONJUNCTIONS


def cmd_evaluate() -> dict[str, Any]:
    slice_doc = _load_slice()
    freeze = _load_freeze()
    baselines = _load_baselines()
    live_eval = _load_liveness_eval()
    by_id = {task["id"]: task for task in _task_list()}
    n_tasks = len(slice_doc["tasks"])
    started = time.perf_counter()
    groups = {name: _empty_stats() for name in _selector_names()}
    n_targets = 0
    n_true_pop = 0
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
            if label == "A":
                n_true_pop += 1
            rec = {
                "cell_id": feat["cell_id"],
                "task_id": task_id,
                "label": label,
                "eval_role": (
                    "TRUE_TARGET"
                    if label == "A"
                    else "INTENTIONAL_BLANK"
                    if label == "B"
                    else "GOLDEN_VALUE"
                ),
                "flags": feat["flags"],
                "A": feat["A"],
                "B": feat["B"],
                "Hom": feat["Hom"],
                "D": feat["D"],
                "E": feat["E"],
                "F": feat["F"],
                "G": feat["G"],
                "last_active_col": feat.get("last_active_col"),
                "votes": feat["votes"],
            }
            labeled.append(rec)
            _add(groups["C1"], task_id, label)
            for name in ATOMIC + CONJUNCTIONS:
                if feat["flags"].get(name):
                    _add(groups[name], task_id, label)
        print(
            f"  C1={freeze['tasks'][task_id]['n_c1']} "
            f"A={groups['C1']['true_by_task'][task_id]}",
            flush=True,
        )
        del input_cells, golden_cells

    packed = {name: _pack(stats, n_true_pop, n_targets, n_tasks) for name, stats in groups.items()}
    base = packed["C1"]["target_precision"]
    monotonic = _monotonic(packed, labeled, base)
    autopsy = _autopsy_coverage(freeze, labeled)
    examples = _examples(labeled)
    distributions = _distributions(labeled)
    interpretation = _interpret(packed, monotonic, autopsy)
    stored_c1 = live_eval["atomic"]["C1"]
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
        "n_c1": freeze["n_c1"],
        "n_c1_labeled": len(labeled),
        "n_true_targets_in_c1": n_true_pop,
        "n_targets_all_golden_formula_blanks": n_targets,
        "golden_blank_to_formula_targets": golden_targets_by_task,
        "stored_baselines": {
            "C1": {
                "selected": stored_c1["selected"],
                "binary_selected": stored_c1["binary_selected"],
                "A_golden_formula": stored_c1["A_golden_formula"],
                "B_intended_blank": stored_c1["B_intended_blank"],
                "C_golden_value": stored_c1["C_golden_value"],
                "target_precision": stored_c1["target_precision"],
            },
            "ANY_POINT": {
                "selected": stored_any["selected"],
                "target_precision": stored_any["target_precision"],
            },
            "POINT_ONLY": {"target_precision": stored_point["target_precision"]},
            "ANY_POINT + >=2 consumer classes": {
                "selected": stored_eq2["selected"],
                "target_precision": stored_eq2["target_precision"],
            },
        },
        "c1_count_match": freeze["n_c1"] == stored_c1["selected"],
        "definitions": DEFINITIONS,
        "atomic": {name: packed[name] for name in ATOMIC},
        "conjunctions": {name: packed[name] for name in CONJUNCTIONS},
        "C1": packed["C1"],
        "monotonic": monotonic,
        "distributions": distributions,
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


def _monotonic(packed: dict[str, Any], labeled: list[dict[str, Any]], base: float | None) -> dict[str, Any]:
    names = [name for name in CORE_ATOMIC + CONJUNCTIONS if name in DIRECTION or name in packed]
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
        task_rates = []
        for task_id, bucket in by_task[name].items():
            on_bin = bucket["A"] + bucket["B"]
            off_bin = bucket["offA"] + bucket["offB"]
            on_p = _rate(bucket["A"], on_bin)
            off_p = _rate(bucket["offA"], off_bin)
            if on_bin < 8 or off_bin < 8 or on_p is None or off_p is None:
                continue
            higher = on_p > off_p + 0.02
            lower = on_p < off_p - 0.02
            direction = "increase" if higher else "decrease" if lower else "flat"
            task_rates.append(
                {
                    "task": task_id,
                    "on_precision": on_p,
                    "off_precision": off_p,
                    "on_n": on_bin,
                    "off_n": off_bin,
                    "direction": direction,
                }
            )
            if expected == "increase" and lower:
                inconsistent.append(task_id)
            elif expected == "decrease" and higher:
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
            "workbook_conditional": task_rates,
        }
    strength = {}
    for prefix, keys in (
        ("A1_continue_k_d2", [f"A1_k{k}_d2" for k in (1, 2, 3, 5)]),
        ("A1_continue_k2_depth", [f"A1_k2_d{d}" for d in (1, 2, 4, 8)]),
        ("F1_share_t1", [f"F1_p{p}_t1" for p in (50, 75, 90)]),
        ("Hom1_k", [f"Hom1_k{k}" for k in (1, 2, 3, 5)]),
    ):
        strength[prefix] = [
            {
                "name": name,
                "precision": packed[name]["target_precision"],
                "n": packed[name]["binary_selected"],
                "recall": packed[name]["recall_in_c1"],
            }
            for name in keys
            if name in packed
        ]
    out["_strength"] = strength
    return out


def _distributions(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    def collect(getter):
        buckets = {"TRUE_TARGET": [], "INTENTIONAL_BLANK": []}
        for rec in labeled:
            if rec["eval_role"] not in buckets:
                continue
            val = getter(rec)
            if val is not None:
                buckets[rec["eval_role"]].append(val)
        out = {}
        for role, vals in buckets.items():
            if not vals:
                out[role] = {"n": 0}
                continue
            ordered = sorted(vals)
            n = len(ordered)
            out[role] = {
                "n": n,
                "mean": round(sum(ordered) / n, 4),
                "p25": ordered[n // 4],
                "median": ordered[n // 2],
                "p75": ordered[(3 * n) // 4],
            }
        return out

    def counts(getter):
        out = {"TRUE_TARGET": Counter(), "INTENTIONAL_BLANK": Counter()}
        for rec in labeled:
            if rec["eval_role"] not in out:
                continue
            out[rec["eval_role"]][str(getter(rec))] += 1
        return {role: dict(counter) for role, counter in out.items()}

    return {
        "distance": collect(lambda r: r["G"]["distance"]),
        "tail": collect(lambda r: r["G"]["tail"]),
        "max_sibling_continue_depth": collect(lambda r: r["A"]["max_continue_depth"]),
        "hom_continue": collect(lambda r: r["Hom"]["n_hom_continue"]),
        "region_median_minus_row_last": collect(
            lambda r: None
            if r["F"]["region_median"] is None or r.get("last_active_col") is None
            else r["F"]["region_median"] - r["last_active_col"]
        ),
        "dist_bin": counts(lambda r: r["G"]["dist_bin"]),
        "tail_bin": counts(lambda r: r["G"]["tail_bin"]),
    }


def _autopsy_coverage(freeze: dict[str, Any], labeled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {rec["cell_id"]: rec for rec in labeled}
    freeze_ids = {feat["cell_id"] for task in freeze["tasks"].values() for feat in task["cells"]}
    out = []
    for spec in AUTOPSY_CELLS:
        rec = by_id.get(spec["cell_id"])
        flags = rec["flags"] if rec else None
        out.append(
            {
                **spec,
                "in_c1": spec["cell_id"] in freeze_ids,
                "eval_role": rec["eval_role"] if rec else None,
                "continuation": [name for name in CONT_EVIDENCE if flags and flags.get(name)],
                "termination": [name for name in TERM_EVIDENCE if flags and flags.get(name)],
                "votes": rec["votes"] if rec else None,
                "G": rec["G"] if rec else None,
            }
        )
    return out


def _examples(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    def pack(rec: dict[str, Any] | None) -> dict[str, Any] | None:
        if rec is None:
            return None
        return {
            "cell_id": rec["cell_id"],
            "eval_role": rec["eval_role"],
            "votes": rec["votes"],
            "continuation": [name for name in CONT_EVIDENCE if rec["flags"].get(name)],
            "termination": [name for name in TERM_EVIDENCE if rec["flags"].get(name)],
            "G": rec["G"],
            "A": rec["A"],
            "Hom": rec["Hom"],
            "D": rec["D"],
        }

    unfinished = [r for r in labeled if r["label"] == "A" and r["votes"]["cont"] >= 2]
    terminated = [r for r in labeled if r["label"] == "B" and r["votes"]["term"] >= 2]
    fp = [r for r in labeled if r["label"] == "B" and r["votes"]["cont"] >= 3]
    fn = [r for r in labeled if r["label"] == "A" and r["votes"]["term"] >= 3]
    unfinished.sort(key=lambda r: r["votes"]["cont"], reverse=True)
    terminated.sort(key=lambda r: r["votes"]["term"], reverse=True)
    fp.sort(key=lambda r: r["votes"]["cont"], reverse=True)
    fn.sort(key=lambda r: r["votes"]["term"], reverse=True)
    return {
        "unfinished_continuation": pack(unfinished[0] if unfinished else None),
        "legitimate_termination": pack(terminated[0] if terminated else None),
        "false_positive_despite_continuation": pack(fp[0] if fp else None),
        "false_negative_despite_termination": pack(fn[0] if fn else None),
    }


def _interpret(packed: dict[str, Any], monotonic: dict[str, Any], autopsy: list[dict[str, Any]]) -> dict[str, Any]:
    base = packed["C1"]["target_precision"] or 0.0
    material = []
    for name in CONJUNCTIONS:
        prec = packed[name]["target_precision"]
        n = packed[name]["binary_selected"]
        books = packed[name]["task_coverage"]["workbooks_with_ge1_true"]
        expected = DIRECTION[name]
        if prec is None or n < 30:
            continue
        if expected == "increase" and prec >= base + 0.05 and books >= 3:
            material.append({"name": name, "precision": prec, "n": n, "books": books, "side": "continuation"})
        if expected == "decrease" and prec <= base - 0.05 and books >= 3:
            material.append({"name": name, "precision": prec, "n": n, "books": books, "side": "termination"})
    directional = []
    broken = []
    for name, rec in monotonic.items():
        if name.startswith("_") or rec.get("expected") == "measure":
            continue
        if rec["on_selected_binary"] < 30:
            continue
        if rec["pooled_matches_expected"] and len(rec["inconsistent_workbooks"]) <= 2:
            directional.append(name)
        elif not rec["pooled_matches_expected"] or len(rec["inconsistent_workbooks"]) >= 3:
            broken.append(name)
    in_c1 = [item for item in autopsy if item["in_c1"]]
    explained = [item["cell_id"] for item in in_c1 if item["continuation"] or item["termination"]]
    if (
        material
        and len(directional) >= 6
        and len(broken) <= 4
        and any(row["side"] == "continuation" for row in material)
        and any(row["side"] == "termination" for row in material)
    ):
        gate = "strong_support"
        conclusion = (
            "Continuation frontier vs legitimate termination is a mechanically "
            "recoverable higher-level structural distinction."
        )
    elif directional or material:
        gate = "partial_heterogeneous_support"
        conclusion = (
            "Frontier semantics are represented by several typed structural "
            "relations rather than one universal continuation predicate."
        )
    else:
        gate = "weak_support"
        conclusion = (
            "The blank-tail ambiguity cannot be resolved from this class of "
            "mechanical frontier structure alone."
        )
    return {
        "gate": gate,
        "conclusion": conclusion,
        "material_selectors": material,
        "directional_predicates": directional,
        "broken_or_heterogeneous": broken,
        "autopsy_in_c1": [item["cell_id"] for item in in_c1],
        "autopsy_with_frontier_facts": explained,
    }


def _row(name: str, stats: dict[str, Any]) -> str:
    cov = stats["task_coverage"]
    return (
        f"| {name} | {stats['binary_selected']} | {stats['A_golden_formula']} | "
        f"{stats['B_intended_blank']} | {stats['C_golden_value']} | "
        f"{_pct(stats['target_precision'])} | {_pct(stats['recall_in_c1'])} | "
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
        "# Blank-tail continuation vs termination diagnostic",
        "",
        f"**{report['label']}**",
        f"**{report['not']}**",
        "",
        "Goldens were not used in feature construction. Population is frozen liveness C1.",
        "",
        f"C1 n={report['n_c1']}. Freeze runtime {report['freeze_runtime_s']['all']}s. "
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
        "## Baselines",
        "",
        f"- C1 {report['stored_baselines']['C1']['target_precision']} "
        f"(binary n={report['stored_baselines']['C1']['binary_selected']}, "
        f"A={report['stored_baselines']['C1']['A_golden_formula']})",
        f"- ANY_POINT {report['stored_baselines']['ANY_POINT']['target_precision']}",
        f"- POINT_ONLY {report['stored_baselines']['POINT_ONLY']['target_precision']}",
        f"- ANY_POINT + ≥2 classes {report['stored_baselines']['ANY_POINT + >=2 consumer classes']['target_precision']}",
        f"- C1 count match vs stored: {report['c1_count_match']}",
        "",
        "## Atomic predicates",
        "",
        "| predicate | selected | A | B | C | precision | recall | ≥1 true | ≥5 true |",
        "|-----------|----------|---|---|---|-----------|--------|---------|---------|",
        _row("C1", report["C1"]),
    ]
    for name in CORE_ATOMIC:
        lines.append(_row(name, report["atomic"][name]))
    lines += [
        "",
        "## Q1–Q9",
        "",
        "| selector | selected | A | B | C | precision | recall | ≥1 true | ≥5 true |",
        "|----------|----------|---|---|---|-----------|--------|---------|---------|",
    ]
    for name in CONJUNCTIONS:
        lines.append(_row(name, report["conjunctions"][name]))
    lines += ["", "## Per-workbook Q1 / Q2 / Q7 / Q8 / Q9", ""]
    for name in ("Q1", "Q2", "Q7", "Q8", "Q9"):
        lines += [f"### {name}", ""] + _book_table(report["conjunctions"][name]) + [""]
    lines += [
        "",
        "## Monotonic / directional",
        "",
        "| predicate | expected | on precision | Δ vs C1 | pooled match | inconsistent books |",
        "|-----------|----------|--------------|---------|--------------|--------------------|",
    ]
    for name, rec in report["monotonic"].items():
        if name.startswith("_"):
            continue
        lines.append(
            f"| {name} | {rec['expected']} | {_pct(rec['on_precision'])} | "
            f"{rec['delta_vs_c1']} | {rec['pooled_matches_expected']} | "
            f"{', '.join(rec['inconsistent_workbooks']) or '—'} |"
        )
    lines += ["", "## Strength ladders", ""]
    for prefix, rows in report["monotonic"].get("_strength", {}).items():
        lines.append(f"### {prefix}")
        lines.append("| name | n | precision | recall |")
        lines.append("|------|---|-----------|--------|")
        for row in rows:
            lines.append(f"| {row['name']} | {row['n']} | {_pct(row['precision'])} | {_pct(row['recall'])} |")
        lines.append("")
    lines += ["", "## Frontier-position distributions", ""]
    dist = report["distributions"]
    for key in ("distance", "tail", "max_sibling_continue_depth", "hom_continue"):
        lines.append(f"### {key}")
        for role, stats in dist[key].items():
            lines.append(f"- {role}: {stats}")
        lines.append("")
    lines += ["## Autopsy-class coverage", ""]
    for item in report["autopsy"]:
        lines.append(
            f"- `{item['cell_id']}` ({item['class']}): in_c1={item['in_c1']} "
            f"role={item['eval_role']} cont={item['continuation']} term={item['termination']}"
        )
    lines += ["", "## Examples", ""]
    for key, rec in report["examples"].items():
        if rec is None:
            lines.append(f"- {key}: none")
            continue
        lines.append(
            f"- {key}: `{rec['cell_id']}` {rec['eval_role']} votes={rec['votes']} "
            f"cont={rec['continuation']} term={rec['termination']}"
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
