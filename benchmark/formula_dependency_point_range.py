#!/usr/bin/env python3
"""Post-hoc point vs range decomposition of frozen D1/D2.

Does not change selector definitions. Rebuilds the reverse-reference graph on
the frozen 12 only because edge type was not persisted per D1 cell. Goldens are
reopened only to reuse the same A/B/C labels.
"""
from __future__ import annotations

import json
import statistics
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

from formula_dependency_selection import RANGE_AREA_BINS, blank_edge_types, build_graph, range_area_bin  # noqa: E402
from formula_dependency_selection_probe import (  # noqa: E402
    OUT,
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

SLICE_LABEL = "DIAGNOSTIC STRUCTURAL-DIVERSITY SAMPLE"
SLICE_NOT = "NOT POPULATION ESTIMATE"
PARTITIONS = ("POINT_ONLY", "RANGE_ONLY", "POINT_AND_RANGE", "ANY_POINT", "ANY_RANGE")
POINT_KS = (1, 2, 3, 5)
CLASS_KS = (1, 2, 3)


def _empty_stats() -> dict[str, Any]:
    return {"A": 0, "B": 0, "C": 0, "selected": 0, "true_by_task": {}, "selected_by_task": {}}


def _pack(stats: dict[str, Any], n_targets: int, n_tasks: int) -> dict[str, Any]:
    selected = stats["selected"]
    true_n = stats["A"]
    covered = [n for n in stats["true_by_task"].values() if n >= 1]
    covered5 = [n for n in stats["true_by_task"].values() if n >= 5]
    return {
        "selected": selected,
        "A_golden_formula": true_n,
        "B_intended_blank": stats["B"],
        "C_golden_value": stats["C"],
        "target_precision": _rate(true_n, selected),
        "target_recall": _rate(true_n, n_targets),
        "task_coverage": {
            "workbooks_with_ge1_true": len(covered),
            "workbooks_with_ge5_true": len(covered5),
            "median_true_per_covered": statistics.median(covered) if covered else None,
            "n_workbooks": n_tasks,
            "true_by_task": stats["true_by_task"],
            "selected_by_task": stats["selected_by_task"],
            "precision_by_task": {
                tid: _rate(stats["true_by_task"][tid], stats["selected_by_task"][tid])
                for tid in stats["selected_by_task"]
            },
        },
    }


def _add(stats: dict[str, Any], task_id: str, label: str) -> None:
    stats[label] += 1
    stats["selected"] += 1
    stats["true_by_task"][task_id] = stats["true_by_task"].get(task_id, 0) + int(label == "A")
    stats["selected_by_task"][task_id] = stats["selected_by_task"].get(task_id, 0) + 1


def _ensure_task(stats: dict[str, Any], task_id: str) -> None:
    stats["true_by_task"].setdefault(task_id, 0)
    stats["selected_by_task"].setdefault(task_id, 0)


def main() -> None:
    slice_doc = _load_slice()
    freeze = json.loads((OUT / "selector_freeze.json").read_text())
    eval_doc = json.loads((OUT / "evaluation.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    n_tasks = len(slice_doc["tasks"])
    started = time.perf_counter()

    groups = {
        "POINT_ONLY": _empty_stats(),
        "RANGE_ONLY": _empty_stats(),
        "POINT_AND_RANGE": _empty_stats(),
        "ANY_POINT": _empty_stats(),
        "ANY_RANGE": _empty_stats(),
        **{f"POINT_k{k}": _empty_stats() for k in POINT_KS},
        **{f"POINT_eq{k}": _empty_stats() for k in CLASS_KS},
        "POINT_same_sheet_only": _empty_stats(),
        "POINT_cross_sheet_only": _empty_stats(),
        "POINT_both_sheets": _empty_stats(),
        **{f"RANGE_ONLY_minarea_{name}": _empty_stats() for name, _lo, _hi in RANGE_AREA_BINS},
        **{f"RANGE_ONLY_nrange_{label}": _empty_stats() for label in ("1", "2", "3-5", "ge6")},
        **{f"RANGE_ONLY_eq{k}": _empty_stats() for k in CLASS_KS},
    }
    mismatch = {"missing_from_graph": 0, "extra_in_graph": 0}
    range_area_values: list[int] = []
    range_count_values: list[int] = []
    n_targets = 0
    golden_targets_by_task: dict[str, int] = {}

    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        print(f"DECOMP {task_id}", flush=True)
        graph = build_graph(_input_path(task))
        types = blank_edge_types(graph)
        d1 = {
            (c["sheet"], c["col"], c["row"])
            for c in freeze["tasks"][task_id]["selectors"]["D1_1"]
        }
        extra = set(types) - d1
        missing = d1 - set(types)
        mismatch["extra_in_graph"] += len(extra)
        mismatch["missing_from_graph"] += len(missing)
        if missing:
            print(f"  missing_from_graph={len(missing)} extra={len(extra)}", flush=True)
        input_cells = _cell_map(_input_path(task))
        golden_cells = _cell_map(_golden_path(task))
        targets = _blank_formula_targets(input_cells, golden_cells)
        golden_targets_by_task[task_id] = len(targets)
        n_targets += len(targets)
        for name, stats in groups.items():
            _ensure_task(stats, task_id)
        for key in sorted(d1):
            info = types.get(key)
            if info is None:
                continue
            label = _label(golden_cells.get(key))
            part = info["partition"]
            _add(groups[part], task_id, label)
            if part in ("POINT_ONLY", "POINT_AND_RANGE"):
                _add(groups["ANY_POINT"], task_id, label)
                n_point = info["n_point"]
                n_eq = info["n_point_eq"]
                for k in POINT_KS:
                    if n_point >= k:
                        _add(groups[f"POINT_k{k}"], task_id, label)
                for k in CLASS_KS:
                    if n_eq >= k:
                        _add(groups[f"POINT_eq{k}"], task_id, label)
                same = info["point_same_sheet"]
                cross = info["point_cross_sheet"]
                if same and cross:
                    _add(groups["POINT_both_sheets"], task_id, label)
                elif cross:
                    _add(groups["POINT_cross_sheet_only"], task_id, label)
                else:
                    _add(groups["POINT_same_sheet_only"], task_id, label)
            if part in ("RANGE_ONLY", "POINT_AND_RANGE"):
                _add(groups["ANY_RANGE"], task_id, label)
            if part == "RANGE_ONLY":
                min_area = info["min_range_area"] or 0
                _add(groups[f"RANGE_ONLY_minarea_{range_area_bin(min_area)}"], task_id, label)
                n_range = info["n_range"]
                range_count_values.append(n_range)
                range_area_values.extend(info["range_areas"])
                if n_range == 1:
                    _add(groups["RANGE_ONLY_nrange_1"], task_id, label)
                elif n_range == 2:
                    _add(groups["RANGE_ONLY_nrange_2"], task_id, label)
                elif n_range <= 5:
                    _add(groups["RANGE_ONLY_nrange_3-5"], task_id, label)
                else:
                    _add(groups["RANGE_ONLY_nrange_ge6"], task_id, label)
                for k in CLASS_KS:
                    if info["n_range_eq"] >= k:
                        _add(groups[f"RANGE_ONLY_eq{k}"], task_id, label)
        print(
            f"  D1={len(d1)} POINT_ONLY={groups['POINT_ONLY']['selected_by_task'][task_id]} "
            f"RANGE_ONLY={groups['RANGE_ONLY']['selected_by_task'][task_id]} "
            f"BOTH={groups['POINT_AND_RANGE']['selected_by_task'][task_id]}",
            flush=True,
        )
        del graph, types, input_cells, golden_cells

    packed = {name: _pack(stats, n_targets, n_tasks) for name, stats in groups.items()}
    d1 = eval_doc["selectors"]["D1_1"]
    d2 = eval_doc["selectors"]["D2_2"]
    comparison = {
        "Occupancy S1": {
            "target_precision": eval_doc["occupancy_baselines"]["S1"],
            "note": "frozen occupancy probe on the same 12",
        },
        "Dependency D1_1": {
            "target_precision": d1["target_precision"],
            "A_golden_formula": d1["A_golden_formula"],
            "selected": d1["selected"],
            "target_recall": d1["target_recall"],
            "workbooks_with_ge1_true": d1["task_coverage"]["workbooks_with_ge1_true"],
        },
        "Dependency D2_2": {
            "target_precision": d2["target_precision"],
            "A_golden_formula": d2["A_golden_formula"],
            "selected": d2["selected"],
            "target_recall": d2["target_recall"],
            "workbooks_with_ge1_true": d2["task_coverage"]["workbooks_with_ge1_true"],
        },
        "ANY_POINT": packed["ANY_POINT"],
        "POINT_ONLY": packed["POINT_ONLY"],
        "RANGE_ONLY": packed["RANGE_ONLY"],
        "POINT_AND_RANGE": packed["POINT_AND_RANGE"],
        "ANY_POINT + >=2 consumer classes": packed["POINT_eq2"],
    }

    def _dist(values: list[int]) -> dict[str, Any]:
        if not values:
            return {"n": 0}
        ordered = sorted(values)
        return {
            "n": len(values),
            "median": statistics.median(ordered),
            "p25": ordered[int(0.25 * (len(ordered) - 1))],
            "p75": ordered[int(0.75 * (len(ordered) - 1))],
            "p90": ordered[int(0.90 * (len(ordered) - 1))],
            "max": max(ordered),
        }

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "note": (
            "Post-hoc decomposition of frozen D1_1. Selector definitions unchanged. "
            "Graphs rebuilt on the frozen 12 because point/range was not stored per cell."
        ),
        "runtime_s": round(time.perf_counter() - started, 3),
        "d1_graph_mismatch": mismatch,
        "golden_blank_to_formula_targets": golden_targets_by_task,
        "n_targets": n_targets,
        "partitions": {name: packed[name] for name in PARTITIONS},
        "point_multiplicity": {f">={k}": packed[f"POINT_k{k}"] for k in POINT_KS},
        "point_consumer_classes": {f">={k}": packed[f"POINT_eq{k}"] for k in CLASS_KS},
        "point_sheet": {
            "same_sheet_only": packed["POINT_same_sheet_only"],
            "cross_sheet_only": packed["POINT_cross_sheet_only"],
            "both": packed["POINT_both_sheets"],
        },
        "range_only": {
            "min_area_bins": {
                name: packed[f"RANGE_ONLY_minarea_{name}"] for name, _lo, _hi in RANGE_AREA_BINS
            },
            "containing_range_count": {
                label: packed[f"RANGE_ONLY_nrange_{label}"]
                for label in ("1", "2", "3-5", "ge6")
            },
            "consumer_classes": {f">={k}": packed[f"RANGE_ONLY_eq{k}"] for k in CLASS_KS},
            "range_area_distribution": _dist(range_area_values),
            "n_containing_ranges_distribution": _dist(range_count_values),
        },
        "comparison": comparison,
    }
    dest = OUT / "point_range_decomposition.json"
    dest.write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "point_range_decomposition.md").write_text(_render(report) + "\n")
    print(f"WROTE {dest}", flush=True)
    print(f"WROTE {OUT / 'point_range_decomposition.md'}", flush=True)


def _row(name: str, stats: dict[str, Any]) -> str:
    cov = stats["task_coverage"]
    return (
        f"| {name} | {stats['selected']} | {stats['A_golden_formula']} | "
        f"{stats['B_intended_blank']} | {stats['C_golden_value']} | "
        f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
        f"{cov['workbooks_with_ge1_true']} | {cov['workbooks_with_ge5_true']} |"
    )


def _book_table(stats: dict[str, Any]) -> list[str]:
    lines = [
        "| task | selected | true | precision |",
        "|------|----------|------|-----------|",
    ]
    for tid, n in stats["task_coverage"]["selected_by_task"].items():
        a = stats["task_coverage"]["true_by_task"][tid]
        lines.append(f"| {tid} | {n} | {a} | {_pct(_rate(a, n))} |")
    return lines


def _render(report: dict[str, Any]) -> str:
    p = report["partitions"]
    lines = [
        "# Point vs range decomposition of frozen D1",
        "",
        f"**{SLICE_LABEL}**",
        f"**{SLICE_NOT}**",
        "",
        report["note"],
        "",
        f"Runtime {report['runtime_s']}s. Graph vs freeze D1 mismatch: {report['d1_graph_mismatch']}.",
        "",
        "## Partitions",
        "",
        "| slice | selected | A | B | C | precision | recall | ≥1 true | ≥5 true |",
        "|-------|----------|---|---|---|-----------|--------|---------|---------|",
        _row("POINT_ONLY", p["POINT_ONLY"]),
        _row("RANGE_ONLY", p["RANGE_ONLY"]),
        _row("POINT_AND_RANGE", p["POINT_AND_RANGE"]),
        _row("ANY_POINT", p["ANY_POINT"]),
        _row("ANY_RANGE", p["ANY_RANGE"]),
        "",
        "## Point multiplicity (ANY_POINT)",
        "",
        "| k | selected | A | precision | recall | ≥1 true | ≥5 true |",
        "|---|----------|---|-----------|--------|---------|---------|",
    ]
    for k, stats in report["point_multiplicity"].items():
        cov = stats["task_coverage"]
        lines.append(
            f"| {k} | {stats['selected']} | {stats['A_golden_formula']} | "
            f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
            f"{cov['workbooks_with_ge1_true']} | {cov['workbooks_with_ge5_true']} |"
        )
    lines += [
        "",
        "## Point consumer classes (ANY_POINT)",
        "",
        "| k | selected | A | precision | recall | ≥1 true | ≥5 true |",
        "|---|----------|---|-----------|--------|---------|---------|",
    ]
    for k, stats in report["point_consumer_classes"].items():
        cov = stats["task_coverage"]
        lines.append(
            f"| {k} | {stats['selected']} | {stats['A_golden_formula']} | "
            f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
            f"{cov['workbooks_with_ge1_true']} | {cov['workbooks_with_ge5_true']} |"
        )
    lines += [
        "",
        "## Cross-sheet point references (ANY_POINT)",
        "",
        "| slice | selected | A | precision | recall | ≥1 true |",
        "|-------|----------|---|-----------|--------|---------|",
    ]
    for name, stats in report["point_sheet"].items():
        cov = stats["task_coverage"]
        lines.append(
            f"| {name} | {stats['selected']} | {stats['A_golden_formula']} | "
            f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
            f"{cov['workbooks_with_ge1_true']} |"
        )
    lines += [
        "",
        "## RANGE_ONLY min covering-area bins",
        "",
        "| bin | selected | A | precision | recall | ≥1 true |",
        "|-----|----------|---|-----------|--------|---------|",
    ]
    for name, stats in report["range_only"]["min_area_bins"].items():
        cov = stats["task_coverage"]
        lines.append(
            f"| {name} | {stats['selected']} | {stats['A_golden_formula']} | "
            f"{_pct(stats['target_precision'])} | {_pct(stats['target_recall'])} | "
            f"{cov['workbooks_with_ge1_true']} |"
        )
    lines += [
        "",
        f"Containing-range area distribution: {report['range_only']['range_area_distribution']}",
        f"n containing ranges: {report['range_only']['n_containing_ranges_distribution']}",
        "",
        "## Comparison",
        "",
        "| slice | selected | A | precision | recall | ≥1 true |",
        "|-------|----------|---|-----------|--------|---------|",
        f"| Occupancy S1 | — | — | {_pct(report['comparison']['Occupancy S1']['target_precision'])} | — | — |",
        f"| Dependency D1_1 | {report['comparison']['Dependency D1_1']['selected']} | "
        f"{report['comparison']['Dependency D1_1']['A_golden_formula']} | "
        f"{_pct(report['comparison']['Dependency D1_1']['target_precision'])} | "
        f"{_pct(report['comparison']['Dependency D1_1']['target_recall'])} | "
        f"{report['comparison']['Dependency D1_1']['workbooks_with_ge1_true']} |",
        f"| Dependency D2_2 | {report['comparison']['Dependency D2_2']['selected']} | "
        f"{report['comparison']['Dependency D2_2']['A_golden_formula']} | "
        f"{_pct(report['comparison']['Dependency D2_2']['target_precision'])} | "
        f"{_pct(report['comparison']['Dependency D2_2']['target_recall'])} | "
        f"{report['comparison']['Dependency D2_2']['workbooks_with_ge1_true']} |",
        _row("ANY_POINT", p["ANY_POINT"]).replace("ANY_POINT", "ANY_POINT"),
        _row("POINT_ONLY", p["POINT_ONLY"]),
        _row("RANGE_ONLY", p["RANGE_ONLY"]),
        _row("POINT_AND_RANGE", p["POINT_AND_RANGE"]),
        _row("ANY_POINT + ≥2 classes", report["point_consumer_classes"][">=2"]),
        "",
        "## Per-workbook ANY_POINT",
        "",
        *_book_table(p["ANY_POINT"]),
        "",
        "## Per-workbook POINT_ONLY",
        "",
        *_book_table(p["POINT_ONLY"]),
        "",
        "## Per-workbook RANGE_ONLY",
        "",
        *_book_table(p["RANGE_ONLY"]),
        "",
        "## Per-workbook ANY_POINT + ≥2 classes",
        "",
        *_book_table(report["point_consumer_classes"][">=2"]),
        "",
        "## Per-workbook RANGE_ONLY 14_05 context is in the RANGE_ONLY table above",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
