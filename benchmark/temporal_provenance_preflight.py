#!/usr/bin/env python3
"""Offline preflight: can missing V2 temporal coordinates reach a seed?

Does not modify V2, retrieval, workbooks, or TASK_OBLIGATION_SHAPE_V1.
Does not run GPT/GLM. Goldens identify missing coordinates only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from temporal_spine import _merge_map, snapshot_cell  # noqa: E402
from temporal_provenance import (  # noqa: E402
    MAX_DEPTH,
    SCHEMA,
    classify_coordinate,
    classify_formula,
    classify_seed,
    index_coordinates,
    walk_from,
)
from workbook_grounding_probe import DATA, DATASET, _tasks  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

SPINE_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-spine-probe"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-provenance-preflight"
KNOWN = [
    {
        "id": "WC_J4",
        "task": "08_01",
        "sheet": "Working Capital",
        "address": "J4",
        "col": 10,
        "row": 4,
    },
    {
        "id": "BS_C5",
        "task": "08_01",
        "sheet": "Balance Sheet",
        "address": "C5",
        "col": 3,
        "row": 5,
    },
    {
        "id": "IS_P5",
        "task": "08_01",
        "sheet": "Income Statement",
        "address": "P5",
        "col": 16,
        "row": 5,
    },
]


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def _percentile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * q
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return round(ordered[low] * (1 - frac) + ordered[high] * frac, 4)


def _load_missing() -> list[dict[str, Any]]:
    rows = json.loads((SPINE_OUT / "coverage_rows.json").read_text())["rows"]
    return [
        row
        for row in rows
        if row.get("split") == "held_out"
        and row.get("status") == "WORKBOOK_TIME_MISSING"
        and row.get("class") != "TASK_SCOPE_UNPARSED"
    ]


def _unique_coords(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], dict[str, Any]] = {}
    for cell in cells:
        key = (cell["task"], cell["sheet_id"], int(cell["col"]))
        rec = grouped.get(key)
        if rec is None:
            grouped[key] = {
                "task": cell["task"],
                "family": cell["family"],
                "sheet": cell["sheet"],
                "sheet_id": cell["sheet_id"],
                "col": int(cell["col"]),
                "col_id": cell["col_id"],
                "axis": "column",
                "n_cells": 1,
                "sample_rows": [int(cell["row"])],
            }
        else:
            rec["n_cells"] += 1
            if len(rec["sample_rows"]) < 4:
                rec["sample_rows"].append(int(cell["row"]))
    return sorted(grouped.values(), key=lambda item: (item["task"], item["sheet_id"], item["col"]))


def _path_by_task() -> dict[str, Path]:
    return {task["id"]: DATA / "Financial_Model" / task["spreadsheet_path"] for task in _tasks()}


def _load_coords(task: str) -> list[dict[str, Any]]:
    path = SPINE_OUT / "coords" / f"{task}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("coordinates") or []


def _compact_path(path: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": path.get("start"),
        "end": path.get("end"),
        "depth": path.get("depth"),
        "path_type": path.get("path_type"),
        "seed_type": (path.get("seed") or {}).get("seed_type"),
        "seed_period": (path.get("seed") or {}).get("period"),
        "same_sheet_hops": path.get("same_sheet_hops"),
        "cross_sheet_hops": path.get("cross_sheet_hops"),
        "transform_edges": path.get("transform_edges"),
        "reference_edges": path.get("reference_edges"),
        "steps": [
            {
                "kind": step["kind"],
                "transform": step.get("transform"),
                "offset": step.get("offset"),
                "from": step["from"],
                "to": step["to"],
                "cross_sheet": step.get("cross_sheet"),
                "formula": step.get("formula"),
            }
            for step in path.get("steps") or []
        ],
    }


def _sheet_by_title(workbook: Any, title: str) -> Any | None:
    for sheet in workbook.worksheets:
        if sheet.title == title:
            return sheet
    stripped = title.strip()
    for sheet in workbook.worksheets:
        if sheet.title.strip() == stripped:
            return sheet
    return None


def inspect_known(workbook: Any, coord_index: dict[tuple[str, int, int], dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    sheet = _sheet_by_title(workbook, case["sheet"])
    if sheet is None:
        return {**case, "error": "sheet_not_found"}
    merge_maps: dict[str, dict[tuple[int, int], tuple[int, int]]] = {}
    merge_origin = merge_maps.setdefault(sheet.title, _merge_map(sheet)[0])
    cell = sheet.cell(row=case["row"], column=case["col"])
    snap = snapshot_cell(cell, merge_origin=merge_origin)
    seed = classify_seed(snap, sheet_title=sheet.title, coord_index=coord_index)
    edge = classify_formula(snap["formula"]) if snap.get("formula") else None
    walked = walk_from(
        workbook,
        start_sheet=sheet,
        start_col=case["col"],
        start_row=case["row"],
        coord_index=coord_index,
        merge_maps=merge_maps,
        epoch=getattr(workbook, "epoch", None),
    )
    return {
        **case,
        "sheet_title": sheet.title,
        "formula": snap.get("formula"),
        "kind": snap.get("kind"),
        "raw": snap.get("raw"),
        "number_format": snap.get("number_format"),
        "local_seed": seed,
        "first_edge": edge,
        "walk_status": walked["status"],
        "paths": [_compact_path(path) for path in walked["paths"][:5]],
        "stops": walked["stops"][:12],
    }


def cmd_run(*, limit: int | None = None) -> dict[str, Any]:
    coverage = json.loads((SPINE_OUT / "coverage.json").read_text())
    held = coverage["by_split"]["held_out"]
    denom = int(held["n"])
    existing_hits = int(held["status"]["HIT"])
    cells = _load_missing()
    coords = _unique_coords(cells)
    if limit is not None:
        coords = coords[:limit]
    path_by_task = _path_by_task()
    open_cache: dict[str, Any] = {}
    coord_cache: dict[str, dict[tuple[str, int, int], dict[str, Any]]] = {}
    merge_cache: dict[str, dict[str, dict[tuple[int, int], tuple[int, int]]]] = {}
    results: list[dict[str, Any]] = []

    def workbook_for(task: str) -> Any | None:
        if task in open_cache:
            return open_cache[task]
        path = path_by_task[task]
        try:
            workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
        except Exception as exc:
            open_cache[task] = None
            coord_cache[task] = {}
            print(f"UNREADABLE {task} {type(exc).__name__}: {exc}", flush=True)
            return None
        open_cache[task] = workbook
        coord_cache[task] = index_coordinates(_load_coords(task))
        merge_cache[task] = {}
        return workbook

    try:
        for i, coord in enumerate(coords, start=1):
            task = coord["task"]
            workbook = workbook_for(task)
            if workbook is None:
                rec = {
                    **coord,
                    "primary": "NO_HEADER_CANDIDATE",
                    "path_type": None,
                    "seed_type": None,
                    "error": "unreadable",
                    "n_header_candidates": 0,
                    "depth": None,
                    "paths": [],
                }
                results.append(rec)
                continue
            sheet = _sheet_by_title(workbook, coord["sheet"])
            if sheet is None:
                rec = {
                    **coord,
                    "primary": "NO_HEADER_CANDIDATE",
                    "path_type": None,
                    "seed_type": None,
                    "error": "sheet_not_found",
                    "n_header_candidates": 0,
                    "depth": None,
                    "paths": [],
                }
                results.append(rec)
                continue
            classified = classify_coordinate(
                workbook,
                sheet=sheet,
                axis="column",
                col=coord["col"],
                row=None,
                coord_index=coord_cache[task],
                merge_maps=merge_cache[task],
                epoch=getattr(workbook, "epoch", None),
            )
            rec = {
                **coord,
                "primary": classified["primary"],
                "path_type": classified["path_type"],
                "seed_type": classified["seed_type"],
                "n_header_candidates": classified["n_header_candidates"],
                "header_candidates": classified["header_candidates"][:12],
                "depth": classified["depth"],
                "same_sheet_hops": classified["same_sheet_hops"],
                "cross_sheet_hops": classified["cross_sheet_hops"],
                "transform_edges": classified["transform_edges"],
                "reference_edges": classified["reference_edges"],
                "n_paths": len(classified["paths"]),
                "best": _compact_path(classified["paths"][0]) if classified["paths"] else None,
            }
            results.append(rec)
            if i % 50 == 0 or i == len(coords):
                print(f"PROGRESS {i}/{len(coords)} {task} {coord['sheet']} c{coord['col']} {rec['primary']}", flush=True)

        known = []
        for case in KNOWN:
            workbook = workbook_for(case["task"])
            if workbook is None:
                known.append({**case, "error": "unreadable"})
                continue
            known.append(inspect_known(workbook, coord_cache[case["task"]], case))
    finally:
        for workbook in open_cache.values():
            if workbook is not None:
                workbook.close()

    by_primary = Counter(row["primary"] for row in results)
    reachable = [row for row in results if row["primary"] == "REACHABLE_TEMPORAL_SEED"]
    n_unique = len(results)
    n_cells = sum(row["n_cells"] for row in results)
    n_reachable_unique = len(reachable)
    n_reachable_cells = sum(row["n_cells"] for row in reachable)
    unique_rate = n_reachable_unique / n_unique if n_unique else 0.0
    cell_rate = n_reachable_cells / n_cells if n_cells else 0.0
    depths = [int(row["depth"]) for row in reachable if row.get("depth") is not None]
    by_path = Counter(row["path_type"] for row in reachable)
    by_seed = Counter(row["seed_type"] for row in reachable)
    by_depth = Counter(row["depth"] for row in reachable)
    by_cross = Counter(row["cross_sheet_hops"] for row in reachable)
    family_reachable = Counter(row["family"] for row in reachable)
    family_missing = Counter(row["family"] for row in results)
    family_reachable_cells = Counter()
    for row in reachable:
        family_reachable_cells[row["family"]] += row["n_cells"]
    largest_family = family_reachable.most_common(1)[0][0] if family_reachable else None
    largest_share = (
        family_reachable[largest_family] / n_reachable_unique if n_reachable_unique and largest_family else 0.0
    )
    families_ge10 = sorted(fam for fam, n in family_reachable.items() if n >= 10)
    cross_sheet_specific = sum(
        1
        for row in reachable
        if row["path_type"] in {"DIRECT_CROSS_SHEET", "CROSS_SHEET_THEN_TRANSFORM", "TRANSFORM_THEN_CROSS_SHEET", "MULTIHOP_REFERENCE"}
        and int(row.get("cross_sheet_hops") or 0) >= 1
    )
    direct_cross = sum(1 for row in reachable if row["path_type"] == "DIRECT_CROSS_SHEET")
    counterfactual_cells = existing_hits + n_reachable_cells
    counterfactual = counterfactual_cells / denom if denom else 0.0
    opaque = by_primary.get("OPAQUE_PATH", 0)
    opaque_cells = sum(row["n_cells"] for row in results if row["primary"] == "OPAQUE_PATH")
    depth_limit_unique = by_primary.get("DEPTH_LIMIT", 0)
    depth_limit_cells = sum(row["n_cells"] for row in results if row["primary"] == "DEPTH_LIMIT")

    families_span = len({row["family"] for row in reachable})
    short = sum(1 for row in reachable if (row.get("depth") or 99) <= 2)
    short_share = short / n_reachable_unique if n_reachable_unique else 0.0
    near_gate = counterfactual >= 0.90
    high_rate = unique_rate >= 0.50
    if high_rate and near_gate and families_span >= 3 and short_share >= 0.6:
        gate = "STRONG_POSITIVE"
        conclusion = (
            "Temporal identity is present but displaced through workbook provenance. "
            "Implement provenance-based temporal propagation."
        )
    elif unique_rate >= 0.15 or (n_reachable_cells / denom if denom else 0) >= 0.10:
        gate = "PARTIAL"
        conclusion = (
            "A meaningful fraction of missing coordinates can reach a temporal seed, "
            "but coverage would remain below the 0.95 gate or the opportunity is concentrated."
        )
    else:
        gate = "WEAK"
        conclusion = (
            "Cross-sheet provenance is not the main missing representation. "
            "Stop this rescue path and inspect the remaining miss classes instead."
        )

    summary = {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "max_depth": MAX_DEPTH,
        "population": {
            "missing_gold_cells": n_cells,
            "unique_missing_coordinates": n_unique,
            "held_out_scope_evaluable_denominator": denom,
            "existing_v2_hits": existing_hits,
            "excluded": "TASK_SCOPE_UNPARSED",
        },
        "primary": dict(by_primary),
        "reachable_seed_rate_unique": round(unique_rate, 4),
        "reachable_seed_rate_cell_weighted": round(cell_rate, 4),
        "n_reachable_unique": n_reachable_unique,
        "n_reachable_cells": n_reachable_cells,
        "path_type": dict(by_path),
        "seed_type": dict(by_seed),
        "depth": {
            "counts": {str(k): v for k, v in sorted(by_depth.items())},
            "median": _percentile(depths, 0.5),
            "p90": _percentile(depths, 0.9),
            "max": max(depths) if depths else None,
            "n_depth_zero": by_depth.get(0, 0),
        },
        "cross_sheet_hops": {str(k): v for k, v in sorted(by_cross.items())},
        "cross_sheet_specific_unique": cross_sheet_specific,
        "direct_cross_sheet_unique": direct_cross,
        "opaque_unique": opaque,
        "opaque_cells": opaque_cells,
        "opaque_unique_rate": round(opaque / n_unique, 4) if n_unique else 0.0,
        "depth_limit_unique": depth_limit_unique,
        "depth_limit_cells": depth_limit_cells,
        "family_missing_unique": dict(family_missing),
        "family_reachable_unique": dict(family_reachable),
        "family_reachable_cells": dict(family_reachable_cells),
        "largest_reachable_family": largest_family,
        "largest_family_share_of_reachable": round(largest_share, 4),
        "families_with_ge10_reachable": families_ge10,
        "n_families_with_reachable": families_span,
        "COUNTERFACTUAL_TEMPORAL_COVERAGE": round(counterfactual, 4),
        "counterfactual_hits": counterfactual_cells,
        "previous_held_out_coverage": held.get("GOLD_TEMPORAL_COORDINATE_COVERAGE"),
        "gate": gate,
        "conclusion": conclusion,
    }
    _write("summary.json", summary)
    _write(
        "coordinates.json",
        {
            "n": len(results),
            "rows": [
                {k: v for k, v in row.items() if k not in {"header_candidates"} or True}
                for row in results
            ],
        },
    )
    _write("known_examples.json", {"cases": known})
    family_rows = []
    for fam in sorted(family_missing):
        family_rows.append(
            {
                "family": fam,
                "missing_unique": family_missing[fam],
                "reachable_unique": family_reachable[fam],
                "reachable_cells": family_reachable_cells[fam],
                "rate": round(family_reachable[fam] / family_missing[fam], 4) if family_missing[fam] else 0.0,
            }
        )
    _write("family.json", {"rows": family_rows})
    report = _write_report(summary, known, family_rows)
    print(
        f"GATE {gate} unique_rate={unique_rate:.4f} cell_rate={cell_rate:.4f} "
        f"counterfactual={counterfactual:.4f} report={report}",
        flush=True,
    )
    return summary


def _write_report(summary: dict[str, Any], known: list[dict[str, Any]], family_rows: list[dict[str, Any]]) -> Path:
    lines = [
        "# Temporal provenance preflight",
        "",
        "Offline elimination test. V2 coordinates were not modified. No retrieval change, no resolver, no GPT/GLM.",
        "",
        f"- schema: `{summary['schema']}`",
        f"- max depth: {summary['max_depth']}",
        f"- missing gold cells: {summary['population']['missing_gold_cells']}",
        f"- unique missing coordinates: {summary['population']['unique_missing_coordinates']}",
        f"- held-out denominator: {summary['population']['held_out_scope_evaluable_denominator']}",
        f"- existing V2 hits: {summary['population']['existing_v2_hits']}",
        "",
        "## Primary counts (unique missing coordinates)",
        "",
        f"`{summary['primary']}`",
        "",
        "## Headline metrics",
        "",
        f"- reachable seed rate (unique): **{summary['reachable_seed_rate_unique']}**",
        f"- reachable seed rate (cell-weighted): **{summary['reachable_seed_rate_cell_weighted']}**",
        f"- COUNTERFACTUAL_TEMPORAL_COVERAGE: **{summary['COUNTERFACTUAL_TEMPORAL_COVERAGE']}** "
        f"(previous {summary['previous_held_out_coverage']})",
        f"- opaque unique rate: {summary['opaque_unique_rate']}",
        f"- depth-limit unique / cells: {summary['depth_limit_unique']} / {summary['depth_limit_cells']}",
        "",
        "## Reachable breakdown",
        "",
        f"- path type: `{summary['path_type']}`",
        f"- seed type: `{summary['seed_type']}`",
        f"- depth counts: `{summary['depth']['counts']}`",
        f"- median / p90 / max depth: {summary['depth']['median']} / {summary['depth']['p90']} / {summary['depth']['max']}",
        f"- cross-sheet hop counts: `{summary['cross_sheet_hops']}`",
        f"- direct cross-sheet unique: {summary['direct_cross_sheet_unique']}",
        f"- any-cross-sheet reachable unique: {summary['cross_sheet_specific_unique']}",
        "",
        "## Family concentration",
        "",
        f"- largest reachable family: {summary['largest_reachable_family']} "
        f"({summary['largest_family_share_of_reachable']})",
        f"- families with ≥10 reachable misses: {summary['families_with_ge10_reachable']}",
        "",
    ]
    for row in family_rows:
        lines.append(
            f"- family {row['family']}: missing unique {row['missing_unique']}, "
            f"reachable unique {row['reachable_unique']} ({row['rate']}), "
            f"reachable cells {row['reachable_cells']}"
        )
    lines += ["", "## Known examples", ""]
    for case in known:
        lines.append(f"### {case.get('id')} `{case.get('task')} {case.get('sheet')}!{case.get('address')}`")
        lines.append("")
        lines.append(f"- formula: `{case.get('formula')}`")
        lines.append(f"- first edge: `{case.get('first_edge')}`")
        lines.append(f"- local seed: `{case.get('local_seed')}`")
        lines.append(f"- walk status: **{case.get('walk_status')}**")
        paths = case.get("paths") or []
        if paths:
            lines.append(f"- best path type {paths[0].get('path_type')} depth {paths[0].get('depth')} seed {paths[0].get('seed_type')}")
            for step in paths[0].get("steps") or []:
                lines.append(
                    f"  - {step.get('kind')} {step.get('from')} → {step.get('to')} "
                    f"{'(cross-sheet) ' if step.get('cross_sheet') else ''}`{step.get('formula')}`"
                )
        else:
            lines.append(f"- stop reasons: `{case.get('stops')}`")
        lines.append("")
    lines += [
        "## Gate",
        "",
        f"**{summary['gate']}**",
        "",
        summary["conclusion"],
        "",
        "## Direct answers",
        "",
        f"1. Unique reachable-seed fraction: {summary['reachable_seed_rate_unique']}; "
        f"cell-weighted {summary['reachable_seed_rate_cell_weighted']}.",
        f"2. Direct cross-sheet unique: {summary['direct_cross_sheet_unique']}; "
        f"any cross-sheet reachable unique: {summary['cross_sheet_specific_unique']}.",
        f"3. Depth median/p90/max: {summary['depth']['median']} / {summary['depth']['p90']} / {summary['depth']['max']}; "
        f"depth-limit unique {summary['depth_limit_unique']}.",
        f"4. Needed relations among reachable: `{summary['path_type']}`.",
        f"5. Largest family {summary['largest_reachable_family']} share "
        f"{summary['largest_family_share_of_reachable']}; families ≥10: {summary['families_with_ge10_reachable']}.",
        f"6. Counterfactual held-out temporal coverage: {summary['COUNTERFACTUAL_TEMPORAL_COVERAGE']}.",
        f"7. Opaque unique rate: {summary['opaque_unique_rate']} ({summary['opaque_unique']} coords, {summary['opaque_cells']} cells).",
        f"8. Provenance propagation justified? Gate={summary['gate']}.",
        "",
        "Final: missing workbook temporal coordinates are classified by whether a short typed formula-provenance path already reaches a seed. This run does not propagate those paths into V2.",
        "",
    ]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["run"])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.cmd == "run":
        cmd_run(limit=args.limit)


if __name__ == "__main__":
    main()
