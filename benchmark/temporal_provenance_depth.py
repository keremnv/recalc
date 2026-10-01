#!/usr/bin/env python3
"""Depth-sensitivity probe on previous DEPTH_LIMIT temporal-provenance misses.

Same E1–E3 walker. Only max depth / visited-cell cap change. No V2 writes,
no retrieval change, no new formula semantics, no GPT/GLM.
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

from temporal_provenance import (  # noqa: E402
    MAX_VISITED_CLOSURE,
    SCHEMA_DEPTH,
    combine_start_walks,
    compact_path,
    header_candidates,
    index_coordinates,
    project_walk,
    terminal_failure_class,
    walk_from,
)
from temporal_spine import _merge_map  # noqa: E402
from workbook_grounding_probe import DATA, _tasks  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

PREFLIGHT_OUT = (
    ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-provenance-preflight"
)
SPINE_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-spine-probe"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-provenance-depth"
SWEEP = [6, 8, 12, 16, 24, 32]
OPTIONAL = [48, 64]
KNOWN = {
    "task": "08_01",
    "sheet": "Income Statement",
    "col": 16,
    "row": 5,
    "address": "P5",
}


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
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


def _sheet_by_title(workbook: Any, title: str) -> Any | None:
    for sheet in workbook.worksheets:
        if sheet.title == title:
            return sheet
    stripped = title.strip()
    for sheet in workbook.worksheets:
        if sheet.title.strip() == stripped:
            return sheet
    return None


def _path_composition(path: dict[str, Any] | None) -> str | None:
    if not path:
        return None
    e1 = int(path.get("e1_edges") or path.get("reference_edges") or 0)
    e2 = int(path.get("e2_edges") or 0)
    e3 = int(path.get("e3_edges") or 0)
    if path.get("transform_edges") and not e2 and not e3:
        # reconstructed from older path records
        if path.get("path_type") == "SAME_SHEET_TRANSFORM":
            e2 = int(path.get("transform_edges") or 0)
        else:
            e2 = int(path.get("transform_edges") or 0)
    if e1 and e2 and not e3:
        return "E1+E2"
    if e1 and e3 and not e2:
        return "E1+E3"
    if e2 and not e1 and not e3:
        return "E2-only"
    if e1 and not e2 and not e3:
        return "E1-only"
    if e1 and e2 and e3:
        return "E1+E2+E3"
    if e3 and not e1:
        return "E3-only"
    return "OTHER"


def _slim_path(path: dict[str, Any] | None) -> dict[str, Any] | None:
    if not path:
        return None
    steps = path.get("steps") or []
    return {
        "start": path.get("start"),
        "end": path.get("end"),
        "depth": path.get("depth"),
        "path_type": path.get("path_type"),
        "seed_type": (path.get("seed") or {}).get("seed_type"),
        "seed_period": (path.get("seed") or {}).get("period"),
        "same_sheet_hops": path.get("same_sheet_hops"),
        "cross_sheet_hops": path.get("cross_sheet_hops"),
        "e1_edges": path.get("e1_edges"),
        "e2_edges": path.get("e2_edges"),
        "e3_edges": path.get("e3_edges"),
        "composition": _path_composition(path),
        "n_steps": len(steps),
        "compact": compact_path(path),
        "boundary_steps": [
            {
                "kind": step["kind"],
                "transform": step.get("transform"),
                "from": step["from"],
                "to": step["to"],
                "cross_sheet": step.get("cross_sheet"),
                "formula": step.get("formula"),
            }
            for step in steps
            if step.get("cross_sheet") or step["kind"] != "E2"
        ][:12],
    }


def _family_share(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    counts = Counter(row["family"] for row in rows)
    largest = counts.most_common(1)[0] if counts else (None, 0)
    return {
        "n": n,
        "by_family": dict(counts),
        "largest_family": largest[0],
        "largest_family_share": round(largest[1] / n, 4) if n else 0.0,
        "families_with_ge10": sorted(fam for fam, k in counts.items() if k >= 10),
    }


def cmd_run(*, limit: int | None = None) -> dict[str, Any]:
    prev_summary = json.loads((PREFLIGHT_OUT / "summary.json").read_text())
    prev_rows = json.loads((PREFLIGHT_OUT / "coordinates.json").read_text())["rows"]
    depth_limit_rows = [row for row in prev_rows if row["primary"] == "DEPTH_LIMIT"]
    prev_reachable = [row for row in prev_rows if row["primary"] == "REACHABLE_TEMPORAL_SEED"]
    if limit is not None:
        depth_limit_rows = depth_limit_rows[:limit]
    if len(depth_limit_rows) != 615 and limit is None:
        print(f"WARN expected 615 DEPTH_LIMIT, got {len(depth_limit_rows)}", flush=True)

    denom = int(prev_summary["population"]["held_out_scope_evaluable_denominator"])
    existing_hits = int(prev_summary["population"]["existing_v2_hits"])
    prev_reachable_cells = int(prev_summary["n_reachable_cells"])
    path_by_task = {task["id"]: DATA / "Financial_Model" / task["spreadsheet_path"] for task in _tasks()}
    workbooks: dict[str, Any] = {}
    coord_cache: dict[str, dict[tuple[str, int, int], dict[str, Any]]] = {}
    merge_cache: dict[str, dict[str, dict[tuple[int, int], tuple[int, int]]]] = {}

    def workbook_for(task: str) -> Any | None:
        if task in workbooks:
            return workbooks[task]
        try:
            workbook = openpyxl.load_workbook(path_by_task[task], data_only=False, read_only=False)
        except Exception as exc:
            print(f"UNREADABLE {task} {type(exc).__name__}: {exc}", flush=True)
            workbooks[task] = None
            return None
        workbooks[task] = workbook
        coords_path = SPINE_OUT / "coords" / f"{task}.json"
        coords = json.loads(coords_path.read_text()).get("coordinates") or [] if coords_path.exists() else []
        coord_cache[task] = index_coordinates(coords)
        merge_cache[task] = {}
        return workbook

    results: list[dict[str, Any]] = []
    try:
        for i, coord in enumerate(depth_limit_rows, start=1):
            task = coord["task"]
            workbook = workbook_for(task)
            if workbook is None:
                results.append({**coord, "closure_primary": "NO_HEADER_CANDIDATE", "error": "unreadable"})
                continue
            sheet = _sheet_by_title(workbook, coord["sheet"])
            if sheet is None:
                results.append({**coord, "closure_primary": "NO_HEADER_CANDIDATE", "error": "sheet_not_found"})
                continue
            merge_maps = merge_cache[task]
            merge_origin = merge_maps.setdefault(sheet.title, _merge_map(sheet)[0])
            starts = header_candidates(
                sheet, axis="column", col=int(coord["col"]), row=None, merge_origin=merge_origin
            )
            walks = [
                walk_from(
                    workbook,
                    start_sheet=sheet,
                    start_col=int(snap["col"]),
                    start_row=int(snap["row"]),
                    coord_index=coord_cache[task],
                    merge_maps=merge_maps,
                    epoch=getattr(workbook, "epoch", None),
                    max_depth=10**9,
                    max_visited=MAX_VISITED_CLOSURE,
                )
                for snap in starts
            ]
            closure = combine_start_walks(starts, walks)
            by_depth: dict[str, str] = {}
            for depth in SWEEP + OPTIONAL:
                projected = [project_walk(walk, max_depth=depth) for walk in walks]
                combined = combine_start_walks(starts, projected)
                by_depth[str(depth)] = combined["primary"]
            best = closure.get("best")
            rec = {
                "task": coord["task"],
                "family": coord["family"],
                "sheet": coord["sheet"],
                "sheet_id": coord["sheet_id"],
                "col": coord["col"],
                "n_cells": coord["n_cells"],
                "n_header_candidates": len(starts),
                "d6_primary": by_depth["6"],
                "closure_primary": closure["primary"],
                "success_depth": closure.get("depth"),
                "seed_type": closure.get("seed_type"),
                "path_type": closure.get("path_type"),
                "composition": _path_composition(best) if best else None,
                "same_sheet_hops": closure.get("same_sheet_hops"),
                "cross_sheet_hops": closure.get("cross_sheet_hops"),
                "visited_total": closure.get("visited_total"),
                "n_edges_total": closure.get("n_edges_total"),
                "terminal_class": terminal_failure_class(
                    closure["primary"], n_edges=int(closure.get("n_edges_total") or 0)
                ),
                "by_depth": by_depth,
                "best": _slim_path(best),
            }
            results.append(rec)
            if i % 40 == 0 or i == len(depth_limit_rows):
                print(
                    f"PROGRESS {i}/{len(depth_limit_rows)} {task} {coord['sheet']} c{coord['col']} "
                    f"d6={rec['d6_primary']} closure={rec['closure_primary']} depth={rec['success_depth']}",
                    flush=True,
                )
    finally:
        for workbook in workbooks.values():
            if workbook is not None:
                workbook.close()

    return _score_and_write(
        results,
        prev_summary=prev_summary,
        prev_reachable=prev_reachable,
        denom=denom,
        existing_hits=existing_hits,
        prev_reachable_cells=prev_reachable_cells,
    )


def _score_and_write(
    results: list[dict[str, Any]],
    *,
    prev_summary: dict[str, Any],
    prev_reachable: list[dict[str, Any]],
    denom: int,
    existing_hits: int,
    prev_reachable_cells: int,
) -> dict[str, Any]:
    n_pop = len(results)
    n_cells = sum(int(row.get("n_cells") or 0) for row in results)
    d6_not_limit = sum(1 for row in results if row.get("d6_primary") != "DEPTH_LIMIT")
    if d6_not_limit:
        print(f"WARN d=6 reconstruction drifted for {d6_not_limit} coords", flush=True)

    reachable_24 = sum(1 for row in results if row.get("by_depth", {}).get("24") == "REACHABLE_TEMPORAL_SEED")
    reachable_32 = sum(1 for row in results if row.get("by_depth", {}).get("32") == "REACHABLE_TEMPORAL_SEED")
    extend = (reachable_32 - reachable_24) / n_pop >= 0.01 if n_pop else False
    depths_reported = list(SWEEP) + (OPTIONAL if extend else [])

    curve = []
    prev_reach = 0
    prev_cov = (existing_hits + prev_reachable_cells) / denom
    for depth in depths_reported + ["closure"]:
        if depth == "closure":
            reachable_rows = [row for row in results if row["closure_primary"] == "REACHABLE_TEMPORAL_SEED"]
            primary_counts = Counter(row["closure_primary"] for row in results)
        else:
            reachable_rows = [
                row for row in results if row.get("by_depth", {}).get(str(depth)) == "REACHABLE_TEMPORAL_SEED"
            ]
            primary_counts = Counter(row.get("by_depth", {}).get(str(depth), "DEPTH_LIMIT") for row in results)
        n_reach = len(reachable_rows)
        n_reach_cells = sum(int(row["n_cells"]) for row in reachable_rows)
        counterfactual = (existing_hits + prev_reachable_cells + n_reach_cells) / denom if denom else 0.0
        incremental_unique = n_reach - prev_reach
        incremental_cov = counterfactual - prev_cov
        curve.append(
            {
                "depth": depth,
                "reachable": n_reach,
                "incremental": incremental_unique,
                "still_depth_limited": primary_counts.get("DEPTH_LIMIT", 0)
                + (primary_counts.get("SAFE_CLOSURE_LIMIT", 0) if depth == "closure" else 0),
                "primary": dict(primary_counts),
                "reachable_cells": n_reach_cells,
                "reachability_of_depth_limit_pop": round(n_reach / n_pop, 4) if n_pop else 0.0,
                "COUNTERFACTUAL_TEMPORAL_COVERAGE": round(counterfactual, 4),
                "incremental_coverage": round(incremental_cov, 4),
                "by_family": dict(Counter(row["family"] for row in reachable_rows)),
            }
        )
        prev_reach = n_reach
        prev_cov = counterfactual

    newly = [row for row in results if row["closure_primary"] == "REACHABLE_TEMPORAL_SEED"]
    depths = [int(row["success_depth"]) for row in newly if row.get("success_depth") is not None]
    compositions = Counter(row.get("composition") for row in newly)
    seed_types = Counter(row.get("seed_type") for row in newly)
    path_types = Counter(row.get("path_type") for row in newly)
    failures = [row for row in results if row["closure_primary"] != "REACHABLE_TEMPORAL_SEED"]
    terminal = Counter(row.get("terminal_class") for row in failures)
    visited = [int(row.get("visited_total") or 0) for row in results]
    edges = [int(row.get("n_edges_total") or 0) for row in results]

    def overall_successes(depth_key: str | None) -> list[dict[str, Any]]:
        extra = []
        if depth_key is None:
            extra = newly
        else:
            extra = [row for row in results if row.get("by_depth", {}).get(depth_key) == "REACHABLE_TEMPORAL_SEED"]
        return prev_reachable + extra

    family_at = {
        "depth_6": _family_share(overall_successes("6")),
        "depth_16": _family_share(overall_successes("16")),
        "closure": _family_share(overall_successes(None)),
        "new_from_depth_limit_closure": _family_share(newly),
    }

    closure_cov = curve[-1]["COUNTERFACTUAL_TEMPORAL_COVERAGE"]
    n_families_new = len({row["family"] for row in newly})
    e123_only = sum(
        1 for row in newly if row.get("composition") in {"E1-only", "E1+E2", "E1+E3", "E2-only", "E1+E2+E3"}
    )
    median_visited = _percentile(visited, 0.5)
    p95_visited = _percentile(visited, 0.95)
    cheap = (max(visited) if visited else 0) <= MAX_VISITED_CLOSURE and (p95_visited or 0) <= MAX_VISITED_CLOSURE
    new_share = family_at["new_from_depth_limit_closure"]["largest_family_share"]
    families_ge10_new = family_at["new_from_depth_limit_closure"]["families_with_ge10"]
    if (
        closure_cov >= 0.85
        and len(families_ge10_new) >= 2
        and n_families_new >= 3
        and e123_only >= 0.9 * max(len(newly), 1)
        and cheap
    ):
        gate = "STRONG_POSITIVE"
        conclusion = (
            "Temporal identity is predominantly encoded as transitive provenance. "
            "Implement provenance closure / propagated TEMPORAL_COORDINATE."
        )
    elif closure_cov >= 0.55 or (newly and new_share >= 0.75):
        gate = "PARTIAL"
        conclusion = (
            "Recovery is meaningful but final counterfactual coverage remains below the grounding gate, "
            "or gains remain highly family concentrated."
        )
    else:
        gate = "WEAK"
        conclusion = (
            "Long provenance chains are not the missing general temporal representation. "
            "Stop the temporal-spine rescue path."
        )

    # saturation depth: first d where incremental unique < 1% of population
    sat = "closure"
    for item in curve:
        if item["depth"] == 6:
            continue
        if item["depth"] == "closure":
            sat = "closure"
            break
        if item["incremental"] / n_pop < 0.01:
            sat = item["depth"]
            break

    samples = _pick_samples(results)
    summary = {
        "schema": SCHEMA_DEPTH,
        "generated_at": datetime.now(UTC).isoformat(),
        "max_visited_closure": MAX_VISITED_CLOSURE,
        "population_n": n_pop,
        "population_cells": n_cells,
        "d6_reconstruction_drift": d6_not_limit,
        "extended_to_48_64": extend,
        "curve": curve,
        "success_depth": {
            "n": len(depths),
            "median": _percentile(depths, 0.5),
            "p75": _percentile(depths, 0.75),
            "p90": _percentile(depths, 0.9),
            "p95": _percentile(depths, 0.95),
            "max": max(depths) if depths else None,
            "counts": {str(k): v for k, v in sorted(Counter(depths).items())},
        },
        "composition": dict(compositions),
        "seed_type": dict(seed_types),
        "path_type": dict(path_types),
        "terminal_failures": dict(terminal),
        "n_unresolved_closure": len(failures),
        "cost": {
            "median_visited_cells": median_visited,
            "p95_visited_cells": p95_visited,
            "max_visited_cells": max(visited) if visited else None,
            "median_edges": _percentile(edges, 0.5),
            "p95_edges": _percentile(edges, 0.95),
            "total_edges": sum(edges),
            "median_success_depth": _percentile(depths, 0.5),
            "p95_success_depth": _percentile(depths, 0.95),
            "cheap_enough": cheap,
        },
        "family": family_at,
        "saturation_depth": sat,
        "previous_d6_counterfactual": prev_summary.get("COUNTERFACTUAL_TEMPORAL_COVERAGE"),
        "gate": gate,
        "conclusion": conclusion,
    }
    _write("summary.json", summary)
    _write("coordinates.json", {"n": len(results), "rows": results})
    _write("samples.json", samples)
    report = _write_report(summary, samples, prev_summary)
    print(
        f"GATE {gate} closure_reach={curve[-1]['reachability_of_depth_limit_pop']} "
        f"closure_cov={curve[-1]['COUNTERFACTUAL_TEMPORAL_COVERAGE']} sat={sat} report={report}",
        flush=True,
    )
    return summary


def _pick_samples(results: list[dict[str, Any]]) -> dict[str, Any]:
    newly = sorted(
        [row for row in results if row["closure_primary"] == "REACHABLE_TEMPORAL_SEED" and row.get("success_depth") is not None],
        key=lambda row: (int(row["success_depth"]), row["task"], row["col"]),
    )
    failures = [row for row in results if row["closure_primary"] != "REACHABLE_TEMPORAL_SEED"]
    p5 = next(
        (
            row
            for row in results
            if row["task"] == KNOWN["task"] and row["sheet"] == KNOWN["sheet"] and int(row["col"]) == KNOWN["col"]
        ),
        None,
    )
    n = len(newly)
    median = newly[n // 2 : n // 2 + 5] if n else []
    return {
        "known_is_p5": p5,
        "shortest_new": newly[:5],
        "median_new": median,
        "longest_new": list(reversed(newly[-5:])),
        "terminal_failures": failures[:5],
    }


def _sample_block(title: str, rows: list[dict[str, Any]] | dict[str, Any] | None) -> list[str]:
    lines = [f"### {title}", ""]
    items: list[dict[str, Any]]
    if rows is None:
        return lines + ["(none)", ""]
    if isinstance(rows, dict):
        items = [rows]
    else:
        items = rows
    for row in items:
        loc = f"{row.get('task')} {row.get('sheet')}!c{row.get('col')}"
        lines.append(f"- **{loc}** family={row.get('family')} cells={row.get('n_cells')} closure={row.get('closure_primary')} depth={row.get('success_depth')} {row.get('terminal_class') or row.get('seed_type')}")
        best = row.get("best") or {}
        for line in best.get("compact") or []:
            lines.append(f"  - {line}")
        if not best.get("compact"):
            lines.append("  - (no compact path)")
        lines.append("")
    return lines


def _write_report(summary: dict[str, Any], samples: dict[str, Any], prev: dict[str, Any]) -> Path:
    lines = [
        "# Temporal provenance depth-sensitivity",
        "",
        "Same E1–E3 walker as the previous preflight. Only max depth / visited-cell cap changed. V2 was not modified.",
        "",
        f"- population: {summary['population_n']} unique DEPTH_LIMIT coordinates ({summary['population_cells']} cells)",
        f"- previous ≤6 reachable unique/cells: {prev.get('n_reachable_unique')}/{prev.get('n_reachable_cells')}",
        f"- previous counterfactual: {summary['previous_d6_counterfactual']}",
        f"- closure visited-cell cap: {summary['max_visited_closure']}",
        f"- extended 48/64: {summary['extended_to_48_64']}",
        f"- d=6 reconstruction drift: {summary['d6_reconstruction_drift']}",
        "",
        "## Cumulative reachability",
        "",
        "| depth | reachable | incremental | still limited | pop rate | counterfactual coverage | Δ cov |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary["curve"]:
        lines.append(
            f"| {item['depth']} | {item['reachable']} | {item['incremental']} | "
            f"{item['still_depth_limited']} | {item['reachability_of_depth_limit_pop']} | "
            f"{item['COUNTERFACTUAL_TEMPORAL_COVERAGE']} | {item['incremental_coverage']} |"
        )
    sd = summary["success_depth"]
    lines += [
        "",
        "## Success depth (newly reachable from DEPTH_LIMIT)",
        "",
        f"- n={sd['n']} median={sd['median']} p75={sd['p75']} p90={sd['p90']} p95={sd['p95']} max={sd['max']}",
        f"- composition: `{summary['composition']}`",
        f"- seed type: `{summary['seed_type']}`",
        f"- path type: `{summary['path_type']}`",
        "",
        "## Terminal failures under SAFE_CLOSURE",
        "",
        f"`{summary['terminal_failures']}` unresolved={summary['n_unresolved_closure']}",
        "",
        "## Family concentration",
        "",
        f"- overall successes at d=6: `{summary['family']['depth_6']}`",
        f"- overall successes at d=16: `{summary['family']['depth_16']}`",
        f"- overall successes at closure: `{summary['family']['closure']}`",
        f"- new from DEPTH_LIMIT at closure: `{summary['family']['new_from_depth_limit_closure']}`",
        "",
        "## Cost",
        "",
        f"`{summary['cost']}`",
        "",
        "## Gate",
        "",
        f"**{summary['gate']}**  saturation≈{summary['saturation_depth']}",
        "",
        summary["conclusion"],
        "",
        "## Chain samples",
        "",
    ]
    lines += _sample_block("08_01 Income Statement!P5", samples.get("known_is_p5"))
    lines += _sample_block("5 shortest newly resolved", samples.get("shortest_new"))
    lines += _sample_block("5 median-depth newly resolved", samples.get("median_new"))
    lines += _sample_block("5 longest successful", samples.get("longest_new"))
    lines += _sample_block("5 terminal failures", samples.get("terminal_failures"))
    cov = {item["depth"]: item["COUNTERFACTUAL_TEMPORAL_COVERAGE"] for item in summary["curve"]}
    lines += [
        "## Direct answers",
        "",
        f"1. Closure reachability of the 615: {summary['curve'][-1]['reachability_of_depth_limit_pop']} "
        f"({summary['curve'][-1]['reachable']}/{summary['population_n']}).",
        f"2. Saturation depth ≈ {summary['saturation_depth']}.",
        f"3. Counterfactual coverage under safe closure: {cov.get('closure')}.",
        f"4. Composition of new successes: `{summary['composition']}`.",
        f"5. New DEPTH_LIMIT recoveries by family: `{summary['family']['new_from_depth_limit_closure']}`.",
        f"6. Remaining terminal classes: `{summary['terminal_failures']}`.",
        f"7. Cost cheap_enough={summary['cost']['cheap_enough']} median/p95 visited={summary['cost']['median_visited_cells']}/{summary['cost']['p95_visited_cells']}.",
        f"8. Gate={summary['gate']}.",
        "",
    ]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["run", "score"])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.cmd == "run":
        cmd_run(limit=args.limit)
    elif args.cmd == "score":
        prev_summary = json.loads((PREFLIGHT_OUT / "summary.json").read_text())
        prev_rows = json.loads((PREFLIGHT_OUT / "coordinates.json").read_text())["rows"]
        results = json.loads((OUT / "coordinates.json").read_text())["rows"]
        _score_and_write(
            results,
            prev_summary=prev_summary,
            prev_reachable=[row for row in prev_rows if row["primary"] == "REACHABLE_TEMPORAL_SEED"],
            denom=int(prev_summary["population"]["held_out_scope_evaluable_denominator"]),
            existing_hits=int(prev_summary["population"]["existing_v2_hits"]),
            prev_reachable_cells=int(prev_summary["n_reachable_cells"]),
        )


if __name__ == "__main__":
    main()
