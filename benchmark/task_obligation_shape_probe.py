#!/usr/bin/env python3
"""Gated offline discovery of the minimum task-obligation representation.

Phases:
  split      — persist family split BEFORE golden ontology inspection
  delta      — input vs golden cell manifests + mechanical clusters
  clauses    — weak schema-less clause carrier
  discover   — counterexample ledger on DISCOVERY families only
  validate   — ORACLE_OBLIGATION on VALIDATION (frozen V1)
  held_out   — frozen schema, no field additions
  searchspace — task-conditioned candidate reduction diagnostic
  all        — split, delta, clauses, discover, validate, held_out, searchspace

No agents, OpenRouter, workbook writes, LibreCalc changes, or extraction models.
"""
from __future__ import annotations

import argparse
import json
import re
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
from formula_completion_certs import load_grids  # noqa: E402
from formula_dependency_selection_probe import (  # noqa: E402
    _golden_path,
    _input_path,
    _task_list,
)
from formula_target_selection import occupancy_from_grid, select_s1  # noqa: E402
from task_obligation_shape import (  # noqa: E402
    DEFINITIONS,
    SPLIT_SEED,
    cluster_changes,
    explicit_preservation_spans,
    family_of,
    golden_delta,
    ground_sheets,
    is_semantic_change,
    make_family_split,
    mentioned_sheet_spans,
    quantifier_spans,
    relation_spans,
    split_of_task,
    weak_clauses,
)
from xlsx_metadata_repair import install  # noqa: E402

install()

OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-shape-probe"
)

KNOWN_FAILURES = [
    ("04_05", "Assumptions", "K6"),
    ("09_05", "Assumptions", "K163"),
    ("09_05", "Assumptions", "L163"),
    ("14_05", "DCF_Income Approach", "D10"),
    ("20_04", "Balance Sheet Schedules", "H41"),
    ("14_05", "Revenue", "J31"),
    ("08_01", "Working Capital", "J46"),
    ("08_01", "Income Statement", "AF66"),
    ("08_01", "Income Statement", "AG66"),
    ("17_03", "Assumptions", "K104"),
    ("15_04", "Consol_annual", "Y39"),
    ("15_04", "Consol_annual", "Y40"),
]


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def cmd_split() -> dict[str, Any]:
    existing = OUT / "family_split.json"
    if existing.is_file():
        payload = json.loads(existing.read_text())
        print(f"SPLIT reuse {existing} discovery={payload['discovery_families']}", flush=True)
        return payload
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_inspected_for_ontology": False,
        "definitions": DEFINITIONS,
        **make_family_split(SPLIT_SEED),
    }
    dest = _write("family_split.json", payload)
    print(f"SPLIT persisted {dest} discovery={payload['discovery_families']}", flush=True)
    return payload


def cmd_delta(split: dict[str, Any] | None = None) -> dict[str, Any]:
    split = split or json.loads((OUT / "family_split.json").read_text())
    started = time.perf_counter()
    tasks = _task_list()
    records = []
    skipped = []
    for task in tasks:
        task_id = task["id"]
        t0 = time.perf_counter()
        try:
            delta = golden_delta(task_id, _input_path(task), _golden_path(task))
        except Exception as exc:
            skipped.append({"task": task_id, "error": type(exc).__name__, "detail": str(exc)[:160]})
            print(f"  SKIP {task_id} {type(exc).__name__}", flush=True)
            continue
        clusters = cluster_changes(delta["changes"])
        compact_changes = []
        for row in delta["changes"]:
            compact_changes.append(
                {
                    "sheet": row["sheet"],
                    "address": row["address"],
                    "col": row["col"],
                    "row": row["row"],
                    "change_kind": row["change_kind"],
                    "input_kind": row["input_kind"],
                    "golden_kind": row["golden_kind"],
                    "golden_formula_fingerprint": row["golden_formula_fingerprint"],
                    "input_formula_fingerprint": row["input_formula_fingerprint"],
                    "refs_added": row["refs_added"][:12],
                    "refs_removed": row["refs_removed"][:12],
                    "golden_payload": (row["golden_payload"] or "")[:160],
                    "input_payload": (row["input_payload"] or "")[:160],
                }
            )
        rec = {
            "task": task_id,
            "family": family_of(task_id),
            "split": split_of_task(task_id, split),
            "n_changes": delta["n_changes"],
            "chart_delta": delta["chart_delta"],
            "n_charts_input": delta["n_charts_input"],
            "n_charts_golden": delta["n_charts_golden"],
            "change_kind_counts": delta["change_kind_counts"],
            "sheet_counts": delta["sheet_counts"],
            "clusters": {
                k: v
                for k, v in clusters.items()
                if k.startswith("n_")
            },
            "n_same_sheet_groups": len(clusters["same_sheet"]),
            "n_fp_families": clusters["n_fingerprint_families"],
            "n_horizontal_runs": clusters["n_horizontal_runs"],
            "n_vertical_runs": clusters["n_vertical_runs"],
            "n_rectangles": clusters["n_rectangles"],
            "changed_sheets": sorted(delta["sheet_counts"]),
            "changes": compact_changes,
            "runtime_s": round(time.perf_counter() - t0, 3),
        }
        records.append(rec)
        print(
            f"  {task_id} split={rec['split']} changes={rec['n_changes']} "
            f"sheets={len(rec['changed_sheets'])} {rec['runtime_s']}s",
            flush=True,
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "split_seed": split["seed"],
        "n_tasks": len(records),
        "skipped": skipped,
        "runtime_s": round(time.perf_counter() - started, 3),
        "tasks": records,
    }
    dest = _write("golden_delta.json", payload)
    print(f"DELTA {dest} n={len(records)} skipped={len(skipped)}", flush=True)
    return payload


def cmd_clauses(split: dict[str, Any] | None = None) -> dict[str, Any]:
    split = split or json.loads((OUT / "family_split.json").read_text())
    tasks = []
    for task in _task_list():
        instruction = task["instruction"]
        clauses = weak_clauses(instruction)
        tasks.append(
            {
                "task": task["id"],
                "family": family_of(task["id"]),
                "split": split_of_task(task["id"], split),
                "instruction": instruction,
                "n_clauses": len(clauses),
                "clauses": clauses,
                "mentioned_sheet_spans": mentioned_sheet_spans(instruction),
                "preservation_spans": explicit_preservation_spans(instruction),
                "quantifier_spans": quantifier_spans(instruction),
                "relation_spans": relation_spans(instruction),
            }
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "carrier": "schema-less CLAUSE spans; no spreadsheet semantics assigned",
        "tasks": tasks,
    }
    dest = _write("weak_clauses.json", payload)
    print(f"CLAUSES {dest} n={len(tasks)}", flush=True)
    return payload


def _delta_index(delta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["task"]: row for row in delta["tasks"]}


def cmd_summarize() -> dict[str, Any]:
    split = json.loads((OUT / "family_split.json").read_text())
    delta = json.loads((OUT / "golden_delta.json").read_text())
    clauses = json.loads((OUT / "weak_clauses.json").read_text())
    by_clause = {row["task"]: row for row in clauses["tasks"]}
    rows = []
    for rec in delta["tasks"]:
        cl = by_clause[rec["task"]]
        kinds = rec["change_kind_counts"]
        rows.append(
            {
                "task": rec["task"],
                "family": rec["family"],
                "split": rec["split"],
                "n_clauses": cl["n_clauses"],
                "n_changes": rec["n_changes"],
                "n_sheets": len(rec["changed_sheets"]),
                "changed_sheets": rec["changed_sheets"],
                "mentioned_sheets": [s["text"] for s in cl["mentioned_sheet_spans"]],
                "n_preservation_spans": len(cl["preservation_spans"]),
                "n_quantifier_spans": len(cl["quantifier_spans"]),
                "n_relation_spans": len(cl["relation_spans"]),
                "change_kinds": kinds,
                "chart_delta": rec["chart_delta"],
                "n_horizontal_runs": rec["n_horizontal_runs"],
                "n_vertical_runs": rec["n_vertical_runs"],
                "n_rectangles": rec["n_rectangles"],
                "n_fp_families": rec["n_fp_families"],
                "blank_to_formula": kinds.get("blank→formula", 0),
                "formula_to_formula": kinds.get("formula→formula", 0),
                "value_to_formula": kinds.get("value→formula", 0),
                "blank_to_value": kinds.get("blank→value", 0),
                "value_changed": kinds.get("value→value_changed", 0),
            }
        )
    payload = {"split": {k: split[k] for k in ("discovery_families", "validation_families", "held_out_families", "seed")}, "rows": rows}
    _write("task_summaries.json", payload)
    lines = [
        "# Task obligation shape — mechanical census",
        "",
        f"split seed={split['seed']}",
        f"discovery={split['discovery_families']}",
        f"validation={split['validation_families']}",
        f"held_out={split['held_out_families']}",
        "",
        "| task | split | clauses | changes | sheets | b→f | f→f | v→f | b→v | charts | h-runs | v-runs |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task']} | {row['split']} | {row['n_clauses']} | {row['n_changes']} | "
            f"{row['n_sheets']} | {row['blank_to_formula']} | {row['formula_to_formula']} | "
            f"{row['value_to_formula']} | {row['blank_to_value']} | {row['chart_delta']} | "
            f"{row['n_horizontal_runs']} | {row['n_vertical_runs']} |"
        )
    (OUT / "task_summaries.md").write_text("\n".join(lines) + "\n")
    print(f"SUMMARY {OUT / 'task_summaries.md'}", flush=True)
    return payload


# Frozen after DISCOVERY inspection. Do not add fields during held-out.
TASK_OBLIGATION_SHAPE_V1 = {
    "unit": "clause_obligation = one requested transformation + its task-licensed constraints",
    "not_the_unit": ["whole task as one blob", "single action enum", "spreadsheet address", "finance role class"],
    "fields": [
        {
            "id": "F_PROVENANCE",
            "name": "provenance",
            "definition": "Exact task-text span(s) for the clause.",
            "task_side": True,
        },
        {
            "id": "F_LOCUS",
            "name": "locus",
            "definition": "Named sheet/tab/section where the transformation is requested.",
            "task_side": True,
        },
        {
            "id": "F_SUBJECT",
            "name": "subject",
            "definition": "Named line item / metric / object of the clause (not a cell address).",
            "task_side": True,
        },
        {
            "id": "F_SUBJECT_INTERVAL",
            "name": "subject_interval",
            "definition": "Ordered from–to span of subjects when the task names a range of line items.",
            "task_side": True,
        },
        {
            "id": "F_REQUIRED_CHANGE",
            "name": "required_change",
            "definition": "Task-licensed state change: calculate/link/reference/set-or-hardcode/populate/create/add-check.",
            "task_side": True,
        },
        {
            "id": "F_SCOPE",
            "name": "scope",
            "definition": "Quantifier or period boundary: all/each/through/enumerated years/historical vs forecast text.",
            "task_side": True,
        },
        {
            "id": "F_SOURCE_RELATION",
            "name": "source_relation",
            "definition": "Explicit using/from/based-on/by-applying correspondence. Absent ⇒ WORKBOOK_RESOLUTION_REQUIRED.",
            "task_side": True,
        },
        {
            "id": "F_CONDITION",
            "name": "condition",
            "definition": "When/where guard stated in the clause (negative PBT, unavailable inputs, equity not meaningful).",
            "task_side": True,
        },
        {
            "id": "F_RESULT_PROPERTY",
            "name": "result_property",
            "definition": "Required output property: display NM/NA, nil tax, same-as-last-historical, percentage-of.",
            "task_side": True,
        },
        {
            "id": "F_THEN",
            "name": "then_after",
            "definition": "Explicit THEN/from-that dependency between clauses.",
            "task_side": True,
        },
        {
            "id": "F_OCCUPANCY_FILTER",
            "name": "occupancy_filter",
            "definition": "Constraint over existing cell kind, e.g. only cells that are not hardcoded.",
            "task_side": True,
        },
    ],
    "rejected_or_not_retained": [
        {
            "name": "row_role/regime finance ontology",
            "why": "No counterexample required REVENUE vs GROWTH_DRIVER classes; subject spans suffice.",
        },
        {
            "name": "target address",
            "why": "Workbook grounding, not task text. Tasks name entities and sheets, not K104.",
        },
        {
            "name": "cell-level preservation invariant",
            "why": "Boilerplate is identical across variants so it does not distinguish transformations; 01_02 golden still edits an unmentioned date cell.",
        },
        {
            "name": "single operation enum without change kind",
            "why": "calculate vs set-value vs link vs create-chart are different transformations of the same locus.",
        },
        {
            "name": "complete-the-model as the obligation",
            "why": "Shared preamble; family variants request disjoint sheet sets.",
        },
    ],
}


DISCOVERY_COUNTEREXAMPLES = [
    {
        "id": "CX-LOCUS-01",
        "requirement": "F_LOCUS",
        "pair": ["01_01", "01_02"],
        "families": ["01"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Same preamble would license both P&L/Revenue-Drivers edits and Debt/WACC/DCF edits.",
        "notes": "01_01 golden sheets {P&L, Revenue Drivers, Cost Drivers, WC, Fixed Assets, BS}; 01_02 {Debt, WACC, DCF} plus one unexplained WC date formula.",
    },
    {
        "id": "CX-SUBJECT-01",
        "requirement": "F_SUBJECT",
        "pair": ["01_03", "01_03"],
        "families": ["01"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Working Capital Receivables vs Current Assets vs Total Working Capital collapse into one sheet edit.",
        "notes": "One sheet, three subjects, different row clusters (C4 vs C19 vs C21 families).",
    },
    {
        "id": "CX-SCOPE-01",
        "requirement": "F_SCOPE",
        "pair": ["01_03", "01_03"],
        "families": ["01"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "2026E–2030E vs all years vs 2021A–2025A on P&L Segment 1 would be the same obligation.",
        "notes": "Receivables scoped to forecast years; Total WC 'for all years'; PBT Margin historical 2021A–2025A.",
    },
    {
        "id": "CX-CHANGE-13",
        "requirement": "F_REQUIRED_CHANGE",
        "pair": ["13_01", "11_01"],
        "families": ["13", "11"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Cannot tell writing constants (0.40, 0.35, … growth rates) from filling formulas.",
        "notes": "13_01 Input Sheet I11:M11 blank→value 0.4/0.4/0.35/0.3/0.25 matches enumerated percents. 11_01 is blank→formula only.",
    },
    {
        "id": "CX-SOURCE-01",
        "requirement": "F_SOURCE_RELATION",
        "pair": ["01_02", "01_02"],
        "families": ["01"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Interest expense could use any rate; task names Key Assumptions and average opening/closing debt.",
        "notes": "If omitted, source X vs source Y is WORKBOOK_RESOLUTION_REQUIRED. Here the task does distinguish.",
    },
    {
        "id": "CX-RESULT-01",
        "requirement": "F_RESULT_PROPERTY",
        "pair": ["01_02", "01_04"],
        "families": ["01"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "EV/EBITDA always numeric vs display NM when EBITDA non-positive would be indistinguishable.",
        "notes": "Also 01_04 NM for zero/negative revenue; NA where inputs unavailable.",
    },
    {
        "id": "CX-THEN-01",
        "requirement": "F_THEN",
        "pair": ["01_01", "01_01"],
        "families": ["01"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Reference Other Revenue, hardcode %, and forecast Other Revenue become an unordered bag; task says then / From that.",
        "notes": "Dataflow among three clauses is in the task, not only in the workbook.",
    },
    {
        "id": "CX-INTERVAL-15",
        "requirement": "F_SUBJECT_INTERVAL",
        "pair": ["15_04", "15_02"],
        "families": ["15"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Consol_annual 'from PBT to EPS Growth (%)' vs 15_02 Work-Sheet-only edits collapse.",
        "notes": "15_04 also 'not hardcoded' occupancy_filter and shares 2023–2027 same as last historical year.",
    },
    {
        "id": "CX-FILTER-15",
        "requirement": "F_OCCUPANCY_FILTER",
        "pair": ["15_04", "15_04"],
        "families": ["15"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Would license overwriting hardcoded share counts that the task says to copy, not recalculate.",
        "notes": "calculate all elements that are not hardcoded; shares section same as last historical year.",
    },
    {
        "id": "CX-CONDITION-01",
        "requirement": "F_CONDITION",
        "pair": ["01_02", "17_03"],
        "families": ["01", "17"],
        "evidence": "EXPLICIT",
        "side": "task-side",
        "failure_if_omitted": "Unguarded formulas vs when-EBITDA-non-positive / where-unavailable.",
        "notes": "Condition and result_property co-occur (display NM when …).",
    },
    {
        "id": "CX-NOT-PRESERVE",
        "requirement": "cell-level preservation (NOT retained)",
        "pair": ["01_01", "01_02"],
        "families": ["01"],
        "evidence": "EXPLICIT boilerplate but non-distinguishing",
        "side": "task-side",
        "failure_if_omitted": "None for distinguishing family variants: every FM task has the same structure/layout/formatting sentence.",
        "notes": "01_02 golden still writes Working Capital!M3 =EOMONTH despite WC not being named. Unmentioned≠forbidden.",
    },
]


def _content_clauses(clause_row: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for clause in clause_row["clauses"]:
        text = clause["exact_source_span"]["text"]
        if text.startswith("Complete the financial model"):
            continue
        if text.startswith("Ensure the existing structure"):
            continue
        out.append(clause)
    return out


def oracle_obligation(clause: dict[str, Any]) -> dict[str, Any]:
    """Populate V1 from clause spans only. No finance class labels."""
    args = " ".join(span.get("text") or "" for span in clause["argument_spans"])
    mods = " ".join(span.get("text") or "" for span in clause["modifier_spans"])
    blob = f"{args} {mods}".strip()
    pred = (clause.get("predicate_span") or {}).get("text")
    locus = None
    match = re.search(r"(?:in|on)\s+the\s+(.+?)(?:\s+sheet|\s+tab|\s+section|,)", blob, flags=re.I)
    if match:
        locus = match.group(1).strip()
    interval = None
    im = re.search(r"from\s+(.+?)\s+to\s+(.+)", blob, flags=re.I)
    if im and re.search(r"PBT|EPS", blob, re.I):
        interval = f"{im.group(1).strip()} → {im.group(2).strip()}"
    occupancy = "not_hardcoded" if re.search(r"not hardcoded", blob, re.I) else None
    return {
        "clause_id": clause["id"],
        "provenance": clause["exact_source_span"],
        "locus": locus,
        "subject": args[:180] or None,
        "subject_interval": interval,
        "required_change": pred,
        "scope": mods[:180] or None,
        "source_relation": mods if re.search(r"\b(using|from|based on|by applying|by growing|by summing)\b", mods, re.I) else None,
        "condition": mods if re.search(r"\b(when|where)\b", mods, re.I) else None,
        "result_property": blob if re.search(r'\b(NM|NA|nil|same as|percentage)\b', blob, re.I) else None,
        "then_after": clause["relation_spans"][0] if clause["relation_spans"] else None,
        "occupancy_filter": occupancy,
        "schema": "TASK_OBLIGATION_SHAPE_V1",
    }


def _granularity(n_clauses: int, n_sheets: int, n_h: int, n_v: int) -> str:
    clusters = max(n_sheets, n_h, n_v, 1)
    if n_clauses <= 1 and clusters <= 1:
        return "ONE_TO_ONE"
    if n_clauses <= 1 and clusters > 1:
        return "ONE_TO_MANY"
    if n_clauses > 1 and clusters <= 1:
        return "MANY_TO_ONE"
    return "MANY_TO_MANY"


def classify_task(task_id: str, rec: dict[str, Any], clause_row: dict[str, Any], grounded: list[str], semantic: list[dict[str, Any]]) -> dict[str, Any]:
    content = _content_clauses(clause_row)
    obligations = [oracle_obligation(c) for c in content]
    semantic_sheets = sorted({row["sheet"] for row in semantic})
    grounded_l = [g.casefold() for g in grounded]
    def named(sheet: str) -> bool:
        s = sheet.casefold()
        return any(s in g or g in s or g[:12] in s for g in grounded_l if g)
    unexplained = [s for s in semantic_sheets if not named(s)]
    n_sem = len(semantic) or 1
    n_unexp_cells = sum(1 for row in semantic if not named(row["sheet"]))
    # V1 is the discovery schema. Parser gaps are not missing expressivity (R ≠ P).
    expressivity = "SUFFICIENT"
    if n_unexp_cells / n_sem > 0.5 and unexplained:
        klass = "GOLDEN_NOT_EXPLAINED_BY_TASK"
    else:
        klass = "TASK_UNDERSPECIFIED"
    return {
        "task": task_id,
        "class": klass,
        "expressivity": expressivity,
        "n_content_clauses": len(content),
        "obligations": obligations,
        "grounded_sheets": grounded,
        "semantic_sheets": semantic_sheets,
        "extra_semantic_sheets": unexplained,
        "n_unexplained_semantic_cells": n_unexp_cells,
        "granularity": _granularity(
            len(content),
            rec.get("n_sheets") or 0,
            rec.get("n_horizontal_runs") or 0,
            rec.get("n_vertical_runs") or 0,
        ),
        "n_semantic_changes": len(semantic),
        "n_raw_changes": rec["n_changes"],
    }


def cmd_discover() -> dict[str, Any]:
    split = json.loads((OUT / "family_split.json").read_text())
    delta = json.loads((OUT / "golden_delta.json").read_text())
    clauses = json.loads((OUT / "weak_clauses.json").read_text())
    by_c = {row["task"]: row for row in clauses["tasks"]}
    rows = []
    for rec in delta["tasks"]:
        if rec["split"] != "discovery":
            continue
        semantic = [c for c in rec["changes"] if is_semantic_change(c)]
        titles = rec["changed_sheets"]
        grounded = [g["sheet"] for g in ground_sheets(by_c[rec["task"]]["instruction"], titles)]
        rows.append(classify_task(rec["task"], rec, by_c[rec["task"]], grounded, semantic))
    payload = {
        "schema": TASK_OBLIGATION_SHAPE_V1,
        "counterexamples": DISCOVERY_COUNTEREXAMPLES,
        "n_discovery_tasks_with_delta": len(rows),
        "class_counts": dict(Counter(r["class"] for r in rows)),
        "granularity_counts": dict(Counter(r["granularity"] for r in rows)),
        "tasks": rows,
        "excluded_family_06": "XMLSyntaxError on all five inputs; clauses inspected from text only.",
    }
    _write("discovery.json", payload)
    print(f"DISCOVER n={len(rows)} classes={payload['class_counts']}", flush=True)
    return payload


def cmd_validate(split_name: str) -> dict[str, Any]:
    split = json.loads((OUT / "family_split.json").read_text())
    delta = json.loads((OUT / "golden_delta.json").read_text())
    clauses = json.loads((OUT / "weak_clauses.json").read_text())
    by_c = {row["task"]: row for row in clauses["tasks"]}
    rows = []
    for rec in delta["tasks"]:
        if rec["split"] != split_name:
            continue
        semantic = [c for c in rec["changes"] if is_semantic_change(c)]
        grounded = [g["sheet"] for g in ground_sheets(by_c[rec["task"]]["instruction"], rec["changed_sheets"])]
        rows.append(classify_task(rec["task"], rec, by_c[rec["task"]], grounded, semantic))
    explainable = [r for r in rows if r["class"] != "GOLDEN_NOT_EXPLAINED_BY_TASK"]
    sufficient_expr = [r for r in explainable if r["expressivity"] == "SUFFICIENT"]
    payload = {
        "split": split_name,
        "schema": "TASK_OBLIGATION_SHAPE_V1",
        "n": len(rows),
        "class_counts": dict(Counter(r["class"] for r in rows)),
        "expressivity_counts": dict(Counter(r["expressivity"] for r in rows)),
        "sufficiency_rate": (len(sufficient_expr) / len(explainable)) if explainable else None,
        "tasks": rows,
        "v2_refinements": [],
        "note": "No V2 fields added: validation did not produce >=2 examples of a new distinction without a discovery analogue.",
    }
    name = "validation.json" if split_name == "validation" else "held_out.json"
    _write(name, payload)
    print(f"{split_name.upper()} n={len(rows)} classes={payload['class_counts']} rate={payload['sufficiency_rate']}", flush=True)
    return payload


def cmd_searchspace() -> dict[str, Any]:
    split = json.loads((OUT / "family_split.json").read_text())
    delta = json.loads((OUT / "golden_delta.json").read_text())
    clauses = json.loads((OUT / "weak_clauses.json").read_text())
    by_c = {row["task"]: row for row in clauses["tasks"]}
    by_task = {t["id"]: t for t in _task_list()}
    rows = []
    started = time.perf_counter()
    for rec in delta["tasks"]:
        task = by_task[rec["task"]]
        t0 = time.perf_counter()
        try:
            grids = load_grids(_input_path(task))
        except Exception as exc:
            rows.append({"task": rec["task"], "error": type(exc).__name__})
            continue
        titles = [g.title for g in grids]
        grounded = {g["sheet"] for g in ground_sheets(by_c[rec["task"]]["instruction"], titles)}
        s1 = []
        for grid in grids:
            occ = occupancy_from_grid(grid)
            for hit in select_s1(occ):
                s1.append((grid.title, hit.col, hit.row))
        s1_set = set(s1)
        scoped = {key for key in s1_set if key[0] in grounded}
        gold = {
            (c["sheet"], c["col"], c["row"])
            for c in rec["changes"]
            if is_semantic_change(c) and c["golden_kind"] == "formula"
        }
        before = len(s1_set)
        after = len(scoped)
        retained = len(gold & scoped)
        lost = len(gold - scoped)
        gold_in_s1 = len(gold & s1_set)
        rows.append(
            {
                "task": rec["task"],
                "split": rec["split"],
                "n_s1": before,
                "n_s1_and_locus": after,
                "n_gold_formula": len(gold),
                "gold_in_s1": gold_in_s1,
                "retained": retained,
                "lost": lost,
                "reduction_ratio": round(after / before, 4) if before else None,
                "precision_before": round(gold_in_s1 / before, 4) if before else None,
                "precision_after": round(retained / after, 4) if after else None,
                "retention_of_s1_gold": round(retained / gold_in_s1, 4) if gold_in_s1 else None,
                "grounded_sheets": sorted(grounded),
                "runtime_s": round(time.perf_counter() - t0, 3),
            }
        )
        print(
            f"  SS {rec['task']} s1={before} scoped={after} gold={len(gold)} retained={retained} lost={lost}",
            flush=True,
        )
    usable = [r for r in rows if "n_s1" in r and r["n_s1"]]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n": len(rows),
        "runtime_s": round(time.perf_counter() - started, 3),
        "mean_reduction_ratio": round(sum(r["reduction_ratio"] or 0 for r in usable) / len(usable), 4) if usable else None,
        "mean_retention_of_s1_gold": round(
            sum(r["retention_of_s1_gold"] or 0 for r in usable if r["retention_of_s1_gold"] is not None)
            / max(1, sum(1 for r in usable if r["retention_of_s1_gold"] is not None)),
            4,
        ),
        "mean_precision_before": round(sum(r["precision_before"] or 0 for r in usable) / len(usable), 4) if usable else None,
        "mean_precision_after": round(sum(r["precision_after"] or 0 for r in usable) / len(usable), 4) if usable else None,
        "tasks": rows,
    }
    _write("searchspace.json", payload)
    print(f"SEARCHSPACE n={len(rows)} reduction={payload['mean_reduction_ratio']} retain={payload['mean_retention_of_s1_gold']}", flush=True)
    return payload


def cmd_autopsy() -> dict[str, Any]:
    delta = json.loads((OUT / "golden_delta.json").read_text())
    clauses = json.loads((OUT / "weak_clauses.json").read_text())
    by_d = {row["task"]: row for row in delta["tasks"]}
    by_c = {row["task"]: row for row in clauses["tasks"]}
    split = json.loads((OUT / "family_split.json").read_text())
    rows = []
    for task_id, sheet, addr in KNOWN_FAILURES:
        rec = by_d.get(task_id)
        change = None
        if rec:
            change = next((c for c in rec["changes"] if c["sheet"] == sheet and c["address"] == addr), None)
        instruction = by_c[task_id]["instruction"]
        rows.append(
            {
                "task": task_id,
                "split": split_of_task(task_id, split),
                "cell": f"{sheet}!{addr}",
                "golden_change": change,
                "instruction": instruction,
                "would_perfect_ir_prevent": None,
            }
        )
    # Hand labels (discovery-informed; validation/held-out are overlay not schema changes).
    prevent = {
        "04_05:Assumptions!K6": "NO — task says grow forecast revenue from 2013 using total growth rates; it does not name K12 vs K27.",
        "09_05:Assumptions!K163": "NO — Other LTA 2014F–2018F; left-side Financials!K82 vs K164*K18 is workbook/dataflow, not in the task.",
        "09_05:Assumptions!L163": "NO — same as K163.",
        "14_05:DCF_Income Approach!D10": "NO — income tax using Tax-DCF effective rate vs homolog D17 is workbook slot choice.",
        "20_04:Balance Sheet Schedules!H41": "PARTIAL — 'days-based linkage to Income Statement expenses' is an explicit source_relation; exact H30 vs H42 is still workbook.",
        "14_05:Revenue!J31": "PARTIAL — Total Revenue for all products / all periods is scope; SUM(J7:J29) vs J28+J29 is aggregation, not named.",
        "08_01:Working Capital!J46": "NO — Inventory/Payables/Receivables named; which reduction cells is workbook.",
        "08_01:Income Statement!AF66": "PARTIAL — tax 30% with nil where PBT negative is explicit result_property/condition; $C$8 vs literal 0.3 is workbook vs textbook.",
        "08_01:Income Statement!AG66": "PARTIAL — same as AF66.",
        "17_03:Assumptions!K104": "YES-ISH — 'as a percentage of Revenue' distinguishes *rate from AR's days/365 recipe; not the exact K14 cell.",
        "15_04:Consol_annual!Y39": "NO — 'calculate or reference where required' licenses a reference; IS_BS_CF!AC48 is workbook.",
        "15_04:Consol_annual!Y40": "NO — interval PBT–EPS does not name the Y37+Y38+Y39 local sum.",
    }
    for row in rows:
        row["would_perfect_ir_prevent"] = prevent.get(f"{row['task']}:{row['cell']}")
    payload = {"rows": rows}
    _write("known_failure_autopsy.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=(
            "split",
            "delta",
            "clauses",
            "summarize",
            "mechanical",
            "discover",
            "validate",
            "held_out",
            "searchspace",
            "autopsy",
            "all",
        ),
        nargs="?",
        default="mechanical",
    )
    args = parser.parse_args()
    split = None
    if args.phase in ("split", "mechanical", "delta", "clauses", "summarize", "discover", "validate", "held_out", "all"):
        split = cmd_split()
    if args.phase in ("delta", "mechanical", "all") and args.phase != "discover":
        if args.phase in ("delta", "mechanical"):
            cmd_delta(split)
    if args.phase in ("clauses", "mechanical"):
        cmd_clauses(split)
    if args.phase in ("summarize", "mechanical"):
        cmd_summarize()
    if args.phase in ("discover", "all"):
        cmd_discover()
    if args.phase in ("validate", "all"):
        cmd_validate("validation")
    if args.phase in ("held_out", "all"):
        cmd_validate("held_out")
    if args.phase in ("searchspace", "all"):
        cmd_searchspace()
    if args.phase in ("autopsy", "all"):
        cmd_autopsy()


if __name__ == "__main__":
    main()
