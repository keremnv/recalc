#!/usr/bin/env python3
"""Offline preflight for the Financial_Model formula-index pilot.

Does not launch agents. Scans all 100 FM inputs, checks CONTROL config identity,
and prints the frozen 20-task slice with reasons.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "benchmark"))

from fingerprint import formula_text, relative_fingerprint  # noqa: E402
from formula_index_pilot import ZERO_RECOVERABLE, select_pilot  # noqa: E402
from formula_index_score import is_blank, load_formulas, load_values  # noqa: E402
from render import OBSERVATION_LIMIT, render_classes  # noqa: E402
from workbook import build_index  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model"
SLICE = ROOT / "benchmark/slices/fm-index-pilot-twenty.json"
CONTROL = ROOT / "benchmark/sweagent/spreadsheet-control.yaml"
OFFICIAL = ROOT / "benchmark-data/SpreadsheetBench-2/SWE-agent/config/spreadsheet.yaml"


def _dist(xs: list[int]) -> dict:
    if not xs:
        return {}
    return {
        "n": len(xs),
        "mean": round(sum(xs) / len(xs), 1),
        "median": round(float(statistics.median(xs)), 1),
        "p90": sorted(xs)[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))],
        "max": max(xs),
        "min": min(xs),
        "frac_gt_10k": round(sum(1 for x in xs if x > OBSERVATION_LIMIT) / len(xs), 3),
    }


def control_unchanged() -> dict:
    import yaml

    ours = yaml.safe_load(CONTROL.read_text())
    official = yaml.safe_load(OFFICIAL.read_text())
    return {
        "control_sha256": hashlib.sha256(CONTROL.read_bytes()).hexdigest(),
        "instance_template_matches_official": (
            ours["agent"]["templates"]["instance_template"]
            == official["agent"]["templates"]["instance_template"]
        ),
        "system_template_matches_official": (
            ours["agent"]["templates"]["system_template"]
            == official["agent"]["templates"]["system_template"]
        ),
        "control_bundles": [item["path"] for item in ours["agent"]["tools"]["bundles"]],
        "max_observation_length": ours["agent"]["templates"]["max_observation_length"],
        "bash_enabled": ours["agent"]["tools"]["enable_bash_tool"],
    }


def main() -> int:
    dataset = json.loads((DATA / "dataset.json").read_text())
    golden_cache: dict[Path, tuple[dict, dict]] = {}
    formula_cells = opaque_cells = 0
    opaque_reasons: Counter[str] = Counter()
    opaque_books = 0
    range_chars: list[int] = []
    axis_chars: list[int] = []
    lookup_chars: list[int] = []
    rows = []

    for i, task in enumerate(dataset, 1):
        inp_path = DATA / task["spreadsheet_path"]
        gold_path = DATA / task["golden_response_path"]
        index = build_index(inp_path)
        formula_cells += index.formula_cells
        opaque_cells += index.opaque_cells
        if index.opaque_cells:
            opaque_books += 1
        opaque_reasons.update(index.opaque_reasons)
        if gold_path not in golden_cache:
            golden_cache[gold_path] = (load_formulas(gold_path), load_values(gold_path))
        gold, gval = golden_cache[gold_path]
        inp = load_formulas(inp_path)
        inv = load_values(inp_path)

        nearest: Counter[str] = Counter()
        blank = rec = 0
        first_blank = None
        keys = set(inp) | set(inv) | set(gold) | set(gval)
        for pos in keys:
            gf, inf = gold.get(pos), inp.get(pos)
            if not gf or inf == gf:
                continue
            if not is_blank(inf, inv.get(pos)):
                continue
            blank += 1
            fp = relative_fingerprint(gf, pos[1], pos[2], sheet=pos[0])
            bucket = index.nearest_bucket(pos[0], pos[1], pos[2], fp.eq_id)
            nearest[bucket] += 1
            if bucket != "unrecoverable":
                rec += 1
            if first_blank is None:
                first_blank = pos

        if index.classes:
            top_sheet = max(
                {sheet for sheet, _c, _r in index.at_cell},
                key=lambda sheet: sum(1 for s, _c, _r in index.at_cell if s == sheet),
            )
            range_records = index.classes_in_range(top_sheet, "A1:Z50")
            range_chars.append(
                len(
                    render_classes(
                        kind="range",
                        header_fields=[f"sheet={top_sheet}", "range=A1:Z50"],
                        records=range_records,
                    )
                )
            )
            sample = first_blank or (top_sheet, 1, 1)
            axis_records = index.classes_on_axis(sample[0], row=sample[2], col=sample[1])
            axis_chars.append(
                len(
                    render_classes(
                        kind="axis",
                        header_fields=[
                            f"sheet={sample[0]}",
                            f"row={sample[2]}",
                            f"col={sample[1]}",
                        ],
                        records=axis_records,
                    )
                )
            )
            first_eq = next(iter(index.classes.values()))
            lookup_chars.append(
                len(
                    render_classes(
                        kind="lookup",
                        header_fields=[f"eq_id={first_eq.eq_id}"],
                        records=[first_eq],
                    )
                )
            )

        rows.append(
            {
                "id": task["id"],
                "families": len(index.classes),
                "formulas": index.formula_cells,
                "opaque_cells": index.opaque_cells,
                "recoverable_blanks": rec,
                "blank_to_formula": blank,
                "nearest": dict(nearest),
            }
        )
        print(
            f"{i:3}/100 {task['id']} formulas={index.formula_cells} "
            f"classes={len(index.classes)} opaque={index.opaque_cells} rec={rec}",
            flush=True,
        )

    negatives, positives = select_pilot(rows)
    slice_tasks = [
        {"category": "Financial_Model", "id": item["id"], "role": "negative_control", "reason": item["reason"]}
        for item in negatives
    ] + [
        {"category": "Financial_Model", "id": item["id"], "role": "mechanism_positive", "reason": item["reason"]}
        for item in positives
    ]
    expected = json.loads(SLICE.read_text())
    expected_ids = [task["id"] for task in expected["tasks"]]
    got_ids = [task["id"] for task in slice_tasks]

    report = {
        "parser": {
            "formula_cells": formula_cells,
            "canonical_cells": formula_cells - opaque_cells,
            "opaque_cells": opaque_cells,
            "support_rate_pct": None
            if not formula_cells
            else round(100 * (formula_cells - opaque_cells) / formula_cells, 2),
            "opaque_reason_counts": dict(opaque_reasons),
            "workbooks_with_any_opaque": opaque_books,
            "workbooks": 100,
        },
        "payload_chars": {
            "range_A1_Z50_busiest_sheet": _dist(range_chars),
            "axis_row_union_col_first_blank": _dist(axis_chars),
            "lookup_first_class": _dist(lookup_chars),
            "observation_cap": OBSERVATION_LIMIT,
        },
        "control": control_unchanged(),
        "pilot_slice_matches_frozen": expected_ids == got_ids,
        "pilot_ids": got_ids,
        "pilot_tasks": slice_tasks,
    }
    out = ROOT / "benchmark/slices/fm-index-preflight.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "pilot_tasks"}, indent=2))
    print("wrote", out)
    if expected_ids != got_ids:
        print("SLICE MISMATCH", "expected", expected_ids, "got", got_ids, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
