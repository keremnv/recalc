#!/usr/bin/env python3
"""Diagnostic probe of dependency/dataflow target selection.

Phases:
  freeze   — graph + D1–D6 on the frozen 12 (no goldens)
  evaluate — visibility, precision, impact, recovery
  all      — freeze then evaluate

Reuses fm-target-selection-probe-12. No agents, writes, or official scorer.
"""
from __future__ import annotations

import argparse
import json
import statistics
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

from fingerprint import a1_address, formula_text, relative_fingerprint  # noqa: E402
from formula_dependency_selection import (  # noqa: E402
    DEFINITIONS,
    all_selector_names,
    build_graph,
    downstream_impact,
    key_json,
    select_all,
)
from formula_target_selection import SLICE_LABEL, SLICE_NAME, SLICE_NOT  # noqa: E402
from workbook import build_index  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
OCC_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-target-selection-probe"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-dependency-selection-probe"
)
SLICE_PATH = ROOT / "benchmark/slices" / f"{SLICE_NAME}.json"
CATEGORY = "Financial_Model"
NAMES = all_selector_names()


def _rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num / den, 4)


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{100.0 * rate:.2f}%"


def _quantile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return float(ordered[low] * (1 - frac) + ordered[high] * frac)


def _summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p25": None, "p75": None, "p90": None}
    return {
        "n": len(values),
        "median": _quantile(values, 50),
        "p25": _quantile(values, 25),
        "p75": _quantile(values, 75),
        "p90": _quantile(values, 90),
        "mean": round(statistics.fmean(values), 4),
        "max": max(values),
    }


def _task_list() -> list[dict[str, str]]:
    return json.loads((DATA / CATEGORY / "dataset.json").read_text())


def _load_slice() -> dict[str, Any]:
    return json.loads(SLICE_PATH.read_text())


def _input_path(task: dict[str, str]) -> Path:
    return DATA / CATEGORY / task["spreadsheet_path"]


def _golden_path(task: dict[str, str]) -> Path:
    return DATA / CATEGORY / task["golden_response_path"]


def _occupancy_keys(task_id: str) -> tuple[set[tuple[str, int, int]], set[tuple[str, int, int]]]:
    freeze = json.loads((OCC_OUT / "selector_freeze.json").read_text())
    payload = freeze["tasks"][task_id]
    def keys(name: str) -> set[tuple[str, int, int]]:
        return {(c["sheet"], c["col"], c["row"]) for c in payload["selectors"][name]}
    return keys("S1"), keys("S5")


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
        return {"fingerprint_in_input": False, "opaque_golden": True, "bucket": None, "eq_id": None}
    record = index.lookup(fp.eq_id)
    if record is None or record.n <= 0:
        return {
            "fingerprint_in_input": False,
            "opaque_golden": False,
            "bucket": "absent",
            "eq_id": fp.eq_id,
        }
    return {
        "fingerprint_in_input": True,
        "opaque_golden": False,
        "bucket": index.nearest_bucket(sheet, col, row, fp.eq_id),
        "eq_id": fp.eq_id,
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


def cmd_freeze() -> dict[str, Any]:
    slice_doc = _load_slice()
    by_id = {task["id"]: task for task in _task_list()}
    OUT.mkdir(parents=True, exist_ok=True)
    print("LOAD occupancy S1/S5", flush=True)
    occ_freeze = json.loads((OCC_OUT / "selector_freeze.json").read_text())
    freeze: dict[str, Any] = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "slice": SLICE_NAME,
        "definitions": DEFINITIONS,
        "runtime_s": {},
        "tasks": {},
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
        s1 = {
            (c["sheet"], c["col"], c["row"])
            for c in occ_freeze["tasks"][task_id]["selectors"]["S1"]
        }
        s5 = {
            (c["sheet"], c["col"], c["row"])
            for c in occ_freeze["tasks"][task_id]["selectors"]["S5"]
        }
        selected, blanks, evidence = select_all(graph, s1, s5)
        impact = {}
        for key, meta in blanks.items():
            feat = downstream_impact(graph, key, meta["dependents"])
            feat["distinct_families"] = len(meta["eq_ids"])
            feat["cross_sheet_direct"] = bool(meta["cross_sheet"])
            impact[f"{key[0]}!{a1_address(key[1], key[2])}"] = feat
        d5_meta = {}
        for key in selected["D5_2"]:
            recs = [rec for rec in evidence[key] if rec.get("same_formula_eq") and rec["share"] >= 1.0]
            recs.sort(key=lambda rec: rec["n_formula"], reverse=True)
            if recs:
                d5_meta[f"{key[0]}!{a1_address(key[1], key[2])}"] = {
                    "peer_eq_id": recs[0]["peer_eq_id"],
                    "n_peers": recs[0]["n_peers"],
                    "consumer_eq_id": recs[0]["eq_id"],
                }
        elapsed = time.perf_counter() - started
        freeze["runtime_s"][task_id] = {"graph": round(graph_s, 3), "total": round(elapsed, 3)}
        freeze["tasks"][task_id] = {
            "family": item["family"],
            "stratum": item["stratum"],
            "coverage": graph.coverage,
            "counts": {name: len(selected[name]) for name in NAMES},
            "selectors": {
                name: [key_json(key) for key in sorted(selected[name])] for name in NAMES
            },
            "d1_impact": impact,
            "d5_meta": d5_meta,
        }
        print(
            f"  formulas={graph.coverage['formula_cells']} "
            f"supported={graph.coverage['supported']} "
            f"D1_1={len(selected['D1_1'])} D5_2={len(selected['D5_2'])} "
            f"{elapsed:.1f}s",
            flush=True,
        )
        del graph, selected, blanks, evidence
    freeze["runtime_s"]["all"] = round(time.perf_counter() - t0, 3)
    dest = OUT / "selector_freeze.json"
    dest.write_text(json.dumps(freeze) + "\n")
    print(f"FREEZE {dest} runtime={freeze['runtime_s']['all']}s", flush=True)
    return freeze


def _load_occupancy_eval() -> dict[str, Any]:
    return json.loads((OCC_OUT / "evaluation.json").read_text())


def cmd_evaluate() -> dict[str, Any]:
    slice_doc = _load_slice()
    freeze = json.loads((OUT / "selector_freeze.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    occ_eval = _load_occupancy_eval()
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
        for name in NAMES
    }
    visibility = {
        "true_targets": 0,
        "intentional_blanks": 0,
        "true": Counter(),
        "intentional": Counter(),
        "true_by_task": {},
        "intentional_by_task": {},
    }
    vis_keys = (
        "d1_1",
        "d1_2",
        "d1_3",
        "d1_5",
        "d2_2",
        "d2_3",
        "cross_sheet_direct",
        "any_downstream",
    )
    impact_true: dict[str, list[float]] = defaultdict(list)
    impact_blank: dict[str, list[float]] = defaultdict(list)
    recovery = {
        name: {
            "true": 0,
            "recoverable": 0,
            "opaque": 0,
            "absent": 0,
            "buckets": Counter(),
            "d5_role_matches_golden": 0,
            "d5_role_compared": 0,
        }
        for name in NAMES
    }
    examples = {
        "true_dependency_role_hole": None,
        "intentional_blank_many_dependents": None,
        "strong_consensus_true": None,
        "strong_consensus_false": None,
    }
    golden_targets_by_task: dict[str, int] = {}
    t0 = time.perf_counter()
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        print(f"EVAL {task_id}", flush=True)
        input_cells = _cell_map(_input_path(task))
        golden_cells = _cell_map(_golden_path(task))
        index = build_index(_input_path(task))
        targets = set(_blank_formula_targets(input_cells, golden_cells))
        golden_targets_by_task[task_id] = len(targets)
        payload = freeze["tasks"][task_id]
        d1 = {
            (c["sheet"], c["col"], c["row"]): payload["d1_impact"][
                f"{c['sheet']}!{c['address']}"
            ]
            for c in payload["selectors"]["D1_1"]
        }
        d1_2 = {(c["sheet"], c["col"], c["row"]) for c in payload["selectors"]["D1_2"]}
        d1_3 = {(c["sheet"], c["col"], c["row"]) for c in payload["selectors"]["D1_3"]}
        d1_5 = {(c["sheet"], c["col"], c["row"]) for c in payload["selectors"]["D1_5"]}
        d2_2 = {(c["sheet"], c["col"], c["row"]) for c in payload["selectors"]["D2_2"]}
        d2_3 = {(c["sheet"], c["col"], c["row"]) for c in payload["selectors"]["D2_3"]}

        def vis_flags(key: tuple[str, int, int]) -> dict[str, bool]:
            feat = d1.get(key)
            return {
                "d1_1": key in d1,
                "d1_2": key in d1_2,
                "d1_3": key in d1_3,
                "d1_5": key in d1_5,
                "d2_2": key in d2_2,
                "d2_3": key in d2_3,
                "cross_sheet_direct": bool(feat and feat.get("cross_sheet_direct")),
                "any_downstream": bool(feat and feat.get("downstream_formulas", 0) >= 1),
            }

        task_true = {flag: 0 for flag in vis_keys}
        for key in targets:
            visibility["true_targets"] += 1
            flags = vis_flags(key)
            for flag, hit in flags.items():
                if hit:
                    visibility["true"][flag] += 1
                    task_true[flag] += 1
            feat = d1.get(key)
            if feat:
                impact_true["direct_dependents"].append(feat["direct_dependents"])
                impact_true["distinct_families"].append(feat["distinct_families"])
                impact_true["downstream_formulas"].append(feat["downstream_formulas"])
                impact_true["downstream_sheets"].append(feat["downstream_sheets"])
                impact_true["max_depth"].append(feat["max_depth"])
        visibility["true_by_task"][task_id] = {"n": len(targets), **task_true}

        intentional = 0
        task_int = {flag: 0 for flag in vis_keys}
        seen_int = set()
        for key, value in input_cells.items():
            if not _blank(value):
                continue
            if key in targets:
                continue
            if _label(golden_cells.get(key)) != "B":
                continue
            intentional += 1
            seen_int.add(key)
            flags = vis_flags(key)
            for flag, hit in flags.items():
                if hit:
                    visibility["intentional"][flag] += 1
                    task_int[flag] += 1
            feat = d1.get(key)
            if feat:
                impact_blank["direct_dependents"].append(feat["direct_dependents"])
                impact_blank["distinct_families"].append(feat["distinct_families"])
                impact_blank["downstream_formulas"].append(feat["downstream_formulas"])
                impact_blank["downstream_sheets"].append(feat["downstream_sheets"])
                impact_blank["max_depth"].append(feat["max_depth"])
        for key, feat in d1.items():
            if key in targets or key in seen_int:
                continue
            if _label(golden_cells.get(key)) != "B":
                continue
            intentional += 1
            flags = vis_flags(key)
            for flag, hit in flags.items():
                if hit:
                    visibility["intentional"][flag] += 1
                    task_int[flag] += 1
            impact_blank["direct_dependents"].append(feat["direct_dependents"])
            impact_blank["distinct_families"].append(feat["distinct_families"])
            impact_blank["downstream_formulas"].append(feat["downstream_formulas"])
            impact_blank["downstream_sheets"].append(feat["downstream_sheets"])
            impact_blank["max_depth"].append(feat["max_depth"])
        visibility["intentional_blanks"] += intentional
        visibility["intentional_by_task"][task_id] = {"n": intentional, **task_int}

        labeled: dict[str, dict[tuple[str, int, int], str]] = {}
        for name in NAMES:
            labels = {}
            for cell in payload["selectors"][name]:
                key = (cell["sheet"], cell["col"], cell["row"])
                label = _label(golden_cells.get(key))
                labels[key] = label
                per_selector[name][label] += 1
                per_selector[name]["selected"] += 1
            labeled[name] = labels
            true_n = sum(1 for lab in labels.values() if lab == "A")
            per_selector[name]["true_by_task"][task_id] = true_n
            per_selector[name]["selected_by_task"][task_id] = len(labels)
            recovery[name]["true"] += true_n
            for key, lab in labels.items():
                if lab != "A":
                    continue
                sheet, col, row = key
                golden_formula = formula_text(golden_cells.get(key))
                if not golden_formula:
                    continue
                info = _recovery(index, sheet, col, row, golden_formula)
                if info["opaque_golden"]:
                    recovery[name]["opaque"] += 1
                elif info["fingerprint_in_input"]:
                    recovery[name]["recoverable"] += 1
                    recovery[name]["buckets"][info["bucket"]] += 1
                else:
                    recovery[name]["absent"] += 1
                if name.startswith("D5_"):
                    meta = payload["d5_meta"].get(f"{sheet}!{a1_address(col, row)}")
                    if meta and info.get("eq_id"):
                        recovery[name]["d5_role_compared"] += 1
                        if meta.get("peer_eq_id") == info["eq_id"]:
                            recovery[name]["d5_role_matches_golden"] += 1

        if examples["true_dependency_role_hole"] is None:
            for key, lab in labeled["D5_2"].items():
                if lab == "A":
                    examples["true_dependency_role_hole"] = {
                        "task": task_id,
                        "cell": f"{key[0]}!{a1_address(key[1], key[2])}",
                        "selector": "D5_2",
                        **payload["d5_meta"].get(f"{key[0]}!{a1_address(key[1], key[2])}", {}),
                    }
                    break
        if examples["intentional_blank_many_dependents"] is None:
            ranked = sorted(
                (
                    (feat["direct_dependents"], key)
                    for key, feat in d1.items()
                    if _label(golden_cells.get(key)) == "B"
                ),
                reverse=True,
            )
            if ranked:
                _n, key = ranked[0]
                examples["intentional_blank_many_dependents"] = {
                    "task": task_id,
                    "cell": f"{key[0]}!{a1_address(key[1], key[2])}",
                    "direct_dependents": d1[key]["direct_dependents"],
                    "distinct_families": d1[key]["distinct_families"],
                }
        if examples["strong_consensus_true"] is None:
            for key, lab in labeled["D3_k5_s100"].items():
                if lab == "A":
                    examples["strong_consensus_true"] = {
                        "task": task_id,
                        "cell": f"{key[0]}!{a1_address(key[1], key[2])}",
                        "selector": "D3_k5_s100",
                    }
                    break
            if examples["strong_consensus_true"] is None:
                for key, lab in labeled["D3_k2_s100"].items():
                    if lab == "A":
                        examples["strong_consensus_true"] = {
                            "task": task_id,
                            "cell": f"{key[0]}!{a1_address(key[1], key[2])}",
                            "selector": "D3_k2_s100",
                        }
                        break
        if examples["strong_consensus_false"] is None:
            for key, lab in labeled["D3_k5_s100"].items():
                if lab == "B":
                    examples["strong_consensus_false"] = {
                        "task": task_id,
                        "cell": f"{key[0]}!{a1_address(key[1], key[2])}",
                        "selector": "D3_k5_s100",
                    }
                    break
            if examples["strong_consensus_false"] is None:
                for key, lab in labeled["D3_k2_s100"].items():
                    if lab == "B":
                        examples["strong_consensus_false"] = {
                            "task": task_id,
                            "cell": f"{key[0]}!{a1_address(key[1], key[2])}",
                            "selector": "D3_k2_s100",
                        }
                        break
        print(
            f"  targets={len(targets)} D1_1={payload['counts']['D1_1']} "
            f"D5_2={payload['counts']['D5_2']}",
            flush=True,
        )

    n_tasks = len(slice_doc["tasks"])
    target_total = sum(golden_targets_by_task.values())
    selectors_out = {}
    for name in NAMES:
        stats = per_selector[name]
        selected_n = stats["selected"]
        true_n = stats["A"]
        covered = [n for n in stats["true_by_task"].values() if n >= 1]
        covered5 = [n for n in stats["true_by_task"].values() if n >= 5]
        selectors_out[name] = {
            "selected": selected_n,
            "A_golden_formula": true_n,
            "B_intended_blank": stats["B"],
            "C_golden_value": stats["C"],
            "D_eval_issue": stats["D"],
            "target_precision": _rate(true_n, selected_n),
            "target_recall": _rate(true_n, target_total),
            "task_coverage": {
                "workbooks_with_ge1_true": len(covered),
                "workbooks_with_ge5_true": len(covered5),
                "median_true_per_covered": statistics.median(covered) if covered else None,
                "n_workbooks": n_tasks,
                "true_by_task": stats["true_by_task"],
                "selected_by_task": stats["selected_by_task"],
            },
            "false_positive_burden": {
                "intended_blanks": stats["B"],
                "intended_blanks_pct": _rate(stats["B"], selected_n),
                "value_targets": stats["C"],
                "value_targets_pct": _rate(stats["C"], selected_n),
            },
        }
    vis_true = {
        flag: {
            "count": visibility["true"][flag],
            "rate": _rate(visibility["true"][flag], visibility["true_targets"]),
            "tasks_with_ge1": sum(
                1 for row in visibility["true_by_task"].values() if row[flag] >= 1
            ),
        }
        for flag in vis_keys
    }
    vis_int = {
        flag: {
            "count": visibility["intentional"][flag],
            "rate": _rate(visibility["intentional"][flag], visibility["intentional_blanks"]),
            "tasks_with_ge1": sum(
                1 for row in visibility["intentional_by_task"].values() if row[flag] >= 1
            ),
        }
        for flag in vis_keys
    }
    recovery_out = {}
    for name, rec in recovery.items():
        recovery_out[name] = {
            "true_targets": rec["true"],
            "recoverable": rec["recoverable"],
            "opaque": rec["opaque"],
            "absent": rec["absent"],
            "rate": _rate(rec["recoverable"], rec["true"]),
            "buckets": dict(rec["buckets"]),
            "d5_role_compared": rec["d5_role_compared"],
            "d5_role_matches_golden": rec["d5_role_matches_golden"],
            "d5_role_match_rate": _rate(rec["d5_role_matches_golden"], rec["d5_role_compared"]),
        }
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "slice": SLICE_NAME,
        "runtime_s": round(time.perf_counter() - t0, 3),
        "freeze_runtime_s": freeze.get("runtime_s"),
        "golden_blank_to_formula_targets": golden_targets_by_task,
        "coverage": {tid: freeze["tasks"][tid]["coverage"] for tid in freeze["tasks"]},
        "visibility": {
            "true_targets": visibility["true_targets"],
            "intentional_blanks": visibility["intentional_blanks"],
            "true": vis_true,
            "intentional": vis_int,
            "true_by_task": visibility["true_by_task"],
            "intentional_by_task": visibility["intentional_by_task"],
        },
        "impact": {
            "true_targets_visible": {k: _summarize(v) for k, v in impact_true.items()},
            "intentional_blanks_visible": {k: _summarize(v) for k, v in impact_blank.items()},
        },
        "selectors": selectors_out,
        "occupancy_baselines": {
            "S1": occ_eval["selectors"]["S1"]["target_precision"],
            "S5": occ_eval["selectors"]["S5"]["target_precision"],
        },
        "recovery": recovery_out,
        "examples": examples,
    }
    (OUT / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "report.md").write_text(_render_report(slice_doc, freeze, report) + "\n")
    print(f"EVAL {OUT / 'evaluation.json'}", flush=True)
    print(f"REPORT {OUT / 'report.md'}", flush=True)
    return report


def _coverage_table(freeze: dict[str, Any]) -> list[str]:
    lines = [
        "| task | formulas | opaque | supported | with edges | point | range | cross-sheet | classes |",
        "|------|----------|--------|-----------|------------|-------|-------|-------------|---------|",
    ]
    for task_id, payload in freeze["tasks"].items():
        c = payload["coverage"]
        lines.append(
            f"| {task_id} | {c['formula_cells']} | {c['opaque']} | {c['supported']} | "
            f"{c['supported_with_edges']} | {c['point_edges']} | {c['range_edges']} | "
            f"{c['cross_sheet_edges']} | {c['equivalence_classes']} |"
        )
    return lines


def _conclusion(report: dict[str, Any]) -> str:
    interesting = []
    for name, stats in report["selectors"].items():
        if name.endswith("∩S1") or name.endswith("∩S5"):
            continue
        precision = stats["target_precision"]
        true_n = stats["A_golden_formula"]
        covered = stats["task_coverage"]["workbooks_with_ge1_true"]
        if precision is None:
            continue
        if precision >= 0.10 and true_n >= 10 and covered >= 3:
            interesting.append((precision, true_n, covered, name))
    d5 = report["selectors"]["D5_2"]
    d1 = report["selectors"]["D1_1"]
    s1 = report["occupancy_baselines"]["S1"]
    s5 = report["occupancy_baselines"]["S5"]
    if interesting:
        best = max(interesting)
        return (
            f"Promising: {best[3]} reached {best[0]:.1%} precision with {best[1]} true "
            f"targets across {best[2]} workbooks, above occupancy S1 ({_pct(s1)}) / S5 ({_pct(s5)}). "
            "Still a 12-task diagnostic sample."
        )
    d5p = d5["target_precision"] or 0
    d1p = d1["target_precision"] or 0
    if d5p < 0.03 and d1p < 0.03:
        return (
            "Structurally unpromising. Explicit dependency/dataflow topology does not "
            "provide enough information for formula-target selection on this diagnostic sample."
        )
    return (
        "Ambiguous: dependency structure is visible on some true targets and some "
        f"selectors exceed occupancy S1 ({_pct(s1)}), but precision, coverage, or "
        "workbook concentration do not show a large general WHERE signal. "
        f"Frontier D5_2={_pct(d5['target_precision'])} ({d5['A_golden_formula']}/{d5['selected']}), "
        f"D1_1={_pct(d1['target_precision'])}."
    )


def _render_report(slice_doc: dict[str, Any], freeze: dict[str, Any], report: dict[str, Any]) -> str:
    vis = report["visibility"]
    lines = [
        "# Dependency/dataflow target-selection probe",
        "",
        f"**{SLICE_LABEL}**",
        f"**{SLICE_NOT}**",
        "",
        "No agents. No OpenRouter. No workbook writes. No official scorer.",
        "",
        "## 1–2. Graph semantics, reuse, runtime",
        "",
        freeze["definitions"]["graph"],
        "",
        freeze["definitions"]["slot"],
        "",
        f"Freeze runtime: {freeze['runtime_s']['all']}s. Evaluate runtime: {report['runtime_s']}s.",
        "",
        "Reused: frozen 12 IDs; occupancy S1/S5 outputs for secondary intersections; "
        "occupancy evaluation S1/S5 precision; `load_grids` / fingerprints / `formula_a1_references`; "
        "golden blank→formula definition from the occupancy probe.",
        "",
        "Newly computed: reverse-reference graph, slot homology, D1–D6, downstream impact, "
        "visibility, golden labels for dependency selectors, D5 role-vs-golden comparison.",
        "",
        *_coverage_table(freeze),
        "",
        "## 3. Dependency visibility of golden targets vs intentional blanks",
        "",
        f"True blank→formula targets: {vis['true_targets']}. "
        f"Intentional blanks (input blank, golden blank): {vis['intentional_blanks']}.",
        "",
        "| visibility | true count | true rate | true tasks≥1 | intentional count | intentional rate |",
        "|------------|------------|-----------|--------------|-------------------|------------------|",
    ]
    for flag in vis["true"]:
        t = vis["true"][flag]
        i = vis["intentional"][flag]
        lines.append(
            f"| {flag} | {t['count']} | {_pct(t['rate'])} | {t['tasks_with_ge1']} | "
            f"{i['count']} | {_pct(i['rate'])} |"
        )
    lines += [
        "",
        "## 4–8. Selector precision / recall",
        "",
        f"Occupancy baselines on the same 12: S1 precision={_pct(report['occupancy_baselines']['S1'])}, "
        f"S5 precision={_pct(report['occupancy_baselines']['S5'])}.",
        "",
        "| selector | selected | A | B | C | precision | recall | ≥1 true | ≥5 true | median true/covered | blank FP% |",
        "|----------|----------|---|---|---|---------|--------|---------|---------|---------------------|-----------|",
    ]
    for name, stats in report["selectors"].items():
        cov = stats["task_coverage"]
        lines.append(
            f"| {name} | {stats['selected']} | {stats['A_golden_formula']} | "
            f"{stats['B_intended_blank']} | {stats['C_golden_value']} | "
            f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
            f"{cov['workbooks_with_ge1_true']} | {cov['workbooks_with_ge5_true']} | "
            f"{cov['median_true_per_covered']} | {_pct(stats['false_positive_burden']['intended_blanks_pct'])} |"
        )
    lines += ["", "## 9. Downstream impact (D1-visible cells only)", ""]
    for group in ("true_targets_visible", "intentional_blanks_visible"):
        lines.append(f"### {group}")
        lines.append("| feature | n | median | p25 | p75 | p90 | mean | max |")
        lines.append("|---------|---|--------|-----|-----|-----|------|-----|")
        for feat, summary in report["impact"][group].items():
            lines.append(
                f"| {feat} | {summary['n']} | {summary['median']} | {summary['p25']} | "
                f"{summary['p75']} | {summary['p90']} | {summary['mean']} | {summary['max']} |"
            )
        lines.append("")
    lines += [
        "## 10–12. Per-workbook concentration, occupancy comparison, recovery",
        "",
        "True-by-task for key selectors is in evaluation.json `selectors.*.task_coverage.true_by_task`.",
        "",
        "| selector | recoverable | rate | buckets | D5 role=golden |",
        "|----------|-------------|------|---------|----------------|",
    ]
    for name in ("D1_1", "D3_k2_s100", "D4_2", "D5_2", "D6_2", "D5_2∩S5"):
        rec = report["recovery"].get(name)
        if not rec:
            continue
        lines.append(
            f"| {name} | {rec['recoverable']}/{rec['true_targets']} | {_pct(rec['rate'])} | "
            f"{rec['buckets']} | {rec['d5_role_matches_golden']}/{rec['d5_role_compared']} "
            f"({_pct(rec['d5_role_match_rate'])}) |"
        )
    examples = report["examples"]
    lines += [
        "",
        "## 13. Examples",
        "",
        f"- True dependency-role hole: {examples['true_dependency_role_hole']}",
        f"- Intentional blank with many dependents: {examples['intentional_blank_many_dependents']}",
        f"- Strong homologous consensus TP: {examples['strong_consensus_true']}",
        f"- Strong homologous consensus FP: {examples['strong_consensus_false']}",
        "",
        "## 14. Conclusion",
        "",
        _conclusion(report),
        "",
        "Do not treat this as a population estimate. Do not expand to all 100 without review.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "evaluate", "all"))
    args = parser.parse_args()
    if args.phase in ("freeze", "all"):
        cmd_freeze()
    if args.phase in ("evaluate", "all"):
        cmd_evaluate()


if __name__ == "__main__":
    main()
