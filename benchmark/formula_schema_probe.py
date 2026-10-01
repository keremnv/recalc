#!/usr/bin/env python3
"""Offline diagnostic of conservative S0/S1 label/schema relations.

Phases:
  extract  — gold-blind S0/S1 census on frozen 12 (no goldens)
  evaluate — ORACLE_WHERE precedent discrimination (goldens as labels only)
  all      — extract, Phase A gate, then evaluate if the gate passes

No agents, OpenRouter, workbook writes, official scorer, classifiers, or S2.
"""
from __future__ import annotations

import argparse
import hashlib
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
from formula_dependency_selection import blank_edge_types, build_graph  # noqa: E402
from formula_dependency_selection_probe import _input_path, _load_slice, _task_list  # noqa: E402
from formula_schema import (  # noqa: E402
    DEFINITIONS,
    JACCARD_THRESHOLDS,
    WorkbookSchema,
    build_workbook_schema,
    compact_schema,
    exact_label_counterparts,
    lexical_relation,
    schema_for_cell,
)
from librecalc_mcp.domain.formulas import formula_a1_references  # noqa: E402
from ranges import parse_a1_cell  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

GLM_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-dependency-glm-probe"
)
SLICE_36 = ROOT / "benchmark/slices/fm-dependency-glm-probe-36.json"
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-schema-probe"
)

# Frozen from the GLM ORACLE_WHERE autopsy. Not revised using schema results.
ORACLE_CLASSES = {
    "20_04:Revenue Driver!I19": "CORRECT",
    "13_03:CF!K30": "CORRECT",
    "13_03:CF!L30": "CORRECT",
    "04_05:Assumptions!K6": "WRONG_SOURCE_OR_HOMOLOGUE",
    "14_05:DCF_Income Approach!D10": "WRONG_SOURCE_OR_HOMOLOGUE",
    "20_04:Balance Sheet Schedules!H41": "WRONG_SOURCE_OR_HOMOLOGUE",
    "08_01:Working Capital!J46": "WRONG_AGGREGATION_LEVEL",
    "14_05:Revenue!J31": "WRONG_AGGREGATION_LEVEL",
    "09_05:Assumptions!K163": "DATAFLOW_DIRECTION",
    "09_05:Assumptions!L163": "DATAFLOW_DIRECTION",
    "08_01:Income Statement!AF66": "TASK_TEXT_OR_TEXTBOOK_TEMPLATE",
    "08_01:Income Statement!AG66": "TASK_TEXT_OR_TEXTBOOK_TEMPLATE",
    "17_03:Assumptions!K104": "TASK_TEXT_OR_TEXTBOOK_TEMPLATE",
    "15_04:Consol_annual!Y39": "INSUFFICIENT_OBSERVATION",
    "15_04:Consol_annual!Y40": "INSUFFICIENT_OBSERVATION",
    "13_03:DCF!C12": "ALGEBRAIC_EQUIVALENT",
    "09_05:Ratio_Analysis !F31": "EMPTY_GENERATION",
    "17_03:Assumptions!L104": "EMPTY_GENERATION",
}

PRIMARY_EXCLUDE = {"CORRECT", "ALGEBRAIC_EQUIVALENT", "EMPTY_GENERATION"}


def _pct(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{100 * rate:.1f}%"


def _rate(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(n / d, 4)


def _parse_cell_id(cell_id: str) -> tuple[str, str, int, int]:
    task_id, rest = cell_id.split(":", 1)
    sheet, addr = rest.split("!", 1)
    col, row = parse_a1_cell(addr)
    return task_id, sheet, col, row


def parse_refs(formula: str | None, default_sheet: str) -> list[dict[str, Any]]:
    if not formula:
        return []
    out = []
    for sheet, start, end in formula_a1_references(formula):
        c1, r1 = parse_a1_cell(start)
        if end:
            c2, r2 = parse_a1_cell(end)
        else:
            c2, r2 = c1, r1
        host = sheet or default_sheet
        out.append(
            {
                "sheet": host,
                "start": start,
                "end": end,
                "c1": c1,
                "r1": r1,
                "c2": c2,
                "r2": r2,
                "is_range": end is not None and (c1, r1) != (c2, r2),
                "anchor": (host, c1, r1),
                "span": (host, c1, r1, c2, r2),
            }
        )
    return out


def align_refs(
    model_refs: list[dict[str, Any]], gold_refs: list[dict[str, Any]]
) -> dict[str, Any]:
    used_m: set[int] = set()
    used_g: set[int] = set()
    shared = []
    for i, model in enumerate(model_refs):
        for j, gold in enumerate(gold_refs):
            if j in used_g:
                continue
            if model["span"] == gold["span"]:
                shared.append({"model_i": i, "gold_i": j, "ref": model})
                used_m.add(i)
                used_g.add(j)
                break
    leftover_m = [i for i in range(len(model_refs)) if i not in used_m]
    leftover_g = [j for j in range(len(gold_refs)) if j not in used_g]
    differing = []
    n = max(len(leftover_m), len(leftover_g))
    for k in range(n):
        mi = leftover_m[k] if k < len(leftover_m) else None
        gj = leftover_g[k] if k < len(leftover_g) else None
        differing.append(
            {
                "model_i": mi,
                "gold_i": gj,
                "model_ref": None if mi is None else model_refs[mi],
                "gold_ref": None if gj is None else gold_refs[gj],
                "alignment": (
                    "lexical_remainder_order"
                    if mi is not None and gj is not None
                    else "unpaired"
                ),
            }
        )
    model_set = {ref["span"] for ref in model_refs}
    gold_set = {ref["span"] for ref in gold_refs}
    return {
        "shared": shared,
        "differing": differing,
        "same_span_set": model_set == gold_set and bool(model_set),
        "model_n": len(model_refs),
        "gold_n": len(gold_refs),
    }


def coverage_bucket() -> dict[str, int]:
    return {
        "n": 0,
        "immediate": 0,
        "stack": 0,
        "header": 0,
        "period": 0,
        "same_label": 0,
        "cross_sheet_label": 0,
        "label_period": 0,
    }


def _add_cov(bucket: dict[str, int], schema: dict[str, Any], book: WorkbookSchema) -> None:
    bucket["n"] += 1
    if schema.get("has_immediate"):
        bucket["immediate"] += 1
    if schema.get("has_stack"):
        bucket["stack"] += 1
    if schema.get("has_header"):
        bucket["header"] += 1
    if schema.get("has_period"):
        bucket["period"] += 1
    peers = exact_label_counterparts(book, schema.get("label_norm"))
    if len(peers) >= 2:
        bucket["same_label"] += 1
    sheets = {sheet for sheet, _row in peers}
    if len(sheets) >= 2:
        bucket["cross_sheet_label"] += 1
    if schema.get("label_norm") and schema.get("period_key"):
        n_lp = 0
        for sheet, row in peers:
            if sheet == schema["sheet"] and row == schema["row"]:
                continue
            periods = book.period_cols.get(sheet, {})
            if periods.get(schema["col"]) == schema["period_key"] or any(
                key == schema["period_key"] for key in periods.values()
            ):
                n_lp += 1
        if n_lp:
            bucket["label_period"] += 1


def _pack_cov(bucket: dict[str, int]) -> dict[str, Any]:
    n = bucket["n"]
    return {
        **bucket,
        "pct_immediate": _rate(bucket["immediate"], n),
        "pct_stack": _rate(bucket["stack"], n),
        "pct_header": _rate(bucket["header"], n),
        "pct_period": _rate(bucket["period"], n),
        "pct_same_label": _rate(bucket["same_label"], n),
        "pct_cross_sheet_label": _rate(bucket["cross_sheet_label"], n),
        "pct_label_period": _rate(bucket["label_period"], n),
    }


def cmd_extract() -> dict[str, Any]:
    slice_doc = _load_slice()
    score = json.loads((GLM_OUT / "score.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    oracle_ids = [row["cell_id"] for row in score["oracle_where"]["cells"]]
    pred_by = {row["cell_id"]: row.get("predicted") for row in score["oracle_where"]["cells"]}
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "extracted_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "definitions": DEFINITIONS,
        "oracle_classes_frozen": ORACLE_CLASSES,
        "reused": [
            "fm-target-selection-probe-12",
            "build_graph / blank_edge_types ANY_POINT",
            "formula-dependency-glm-probe 18 ORACLE_WHERE targets and model formulas",
            "prior ORACLE autopsy class labels (frozen)",
        ],
        "newly_computed": [
            "S0 row labels, stacks, headers, periods",
            "S1 normalization/Jaccard (not used for census counts)",
            "R1–R5 correspondence indexes",
        ],
        "runtime_s": {},
        "tasks": {},
        "formula_cov": {},
        "any_point_cov": {},
        "oracle_cov": {},
        "oracle_pred_ref_cov": {},
        "oracle_cells": {},
        "integrity_sample": [],
    }
    formula_all = coverage_bucket()
    any_all = coverage_bucket()
    oracle_all = coverage_bucket()
    pred_ref_all = coverage_bucket()
    sample_pool: list[dict[str, Any]] = []

    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        source = _input_path(task)
        print(f"EXTRACT {task_id}", flush=True)
        t0 = time.perf_counter()
        book = build_workbook_schema(source)
        schema_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        graph = build_graph(source)
        graph_s = time.perf_counter() - t1
        f_cov = coverage_bucket()
        a_cov = coverage_bucket()
        formula_keys = [
            (title, col, row)
            for title, grid in graph.occupancy.items()
            for (col, row), kind in grid.cells.items()
            if kind in ("F", "O")
        ]
        for sheet, col, row in formula_keys:
            index = book.sheets.get(sheet)
            if index is None:
                continue
            schema = schema_for_cell(index, col, row)
            _add_cov(f_cov, schema, book)
            _add_cov(formula_all, schema, book)
            digest = hashlib.sha1(f"{task_id}:{sheet}!{a1_address(col, row)}".encode()).hexdigest()
            if int(digest[:8], 16) % 41 == 0:
                sample_pool.append(
                    {
                        "cell_id": f"{task_id}:{sheet}!{a1_address(col, row)}",
                        "schema": compact_schema(schema),
                        "candidates": schema.get("label_candidates", [])[:3],
                    }
                )
        edges = blank_edge_types(graph)
        n_any = 0
        for key, meta in edges.items():
            if not meta["point_formulas"]:
                continue
            n_any += 1
            sheet, col, row = key
            index = book.sheets.get(sheet)
            if index is None:
                continue
            schema = schema_for_cell(index, col, row)
            _add_cov(a_cov, schema, book)
            _add_cov(any_all, schema, book)
        oracle_here = []
        for cell_id in oracle_ids:
            if not cell_id.startswith(task_id + ":"):
                continue
            _tid, sheet, col, row = _parse_cell_id(cell_id)
            index = book.sheets.get(sheet)
            schema = None if index is None else schema_for_cell(index, col, row)
            if schema is not None:
                _add_cov(oracle_all, schema, book)
            pred_refs = []
            for ref in parse_refs(pred_by.get(cell_id), sheet):
                src_index = book.sheets.get(ref["sheet"])
                src_schema = (
                    None if src_index is None else schema_for_cell(src_index, ref["c1"], ref["r1"])
                )
                if src_schema is not None:
                    _add_cov(pred_ref_all, src_schema, book)
                pred_refs.append(
                    {"ref": ref, "schema": None if src_schema is None else compact_schema(src_schema)}
                )
            rec = {
                "cell_id": cell_id,
                "class": ORACLE_CLASSES.get(cell_id),
                "predicted": pred_by.get(cell_id),
                "target": None if schema is None else compact_schema(schema),
                "target_full_immediate": None if schema is None else schema.get("immediate"),
                "target_stack": None if schema is None else [compact_schema({**schema, "address": item["address"], "sheet": item["sheet"], "label_raw": item["raw"], "label_norm": item["norm"], "has_immediate": True, "has_stack": False, "has_header": False, "has_period": False, "period_key": None}) for item in schema.get("stack") or []],
                "pred_refs": pred_refs,
            }
            payload["oracle_cells"][cell_id] = rec
            oracle_here.append(cell_id)
        payload["tasks"][task_id] = {
            "family": item["family"],
            "n_formula": f_cov["n"],
            "n_any_point": n_any,
            "n_oracle": len(oracle_here),
            "formula": _pack_cov(f_cov),
            "any_point": _pack_cov(a_cov),
            "n_label_norms": len(book.label_rows),
            "n_cross_sheet_labels": sum(
                1
                for peers in book.label_rows.values()
                if len({sheet for sheet, _row in peers}) >= 2
            ),
        }
        payload["runtime_s"][task_id] = {
            "schema_index": round(schema_s, 3),
            "graph": round(graph_s, 3),
            "total": round(time.perf_counter() - t0, 3),
        }
        print(
            f"  F={f_cov['n']} any={n_any} immF={_pct(_rate(f_cov['immediate'], f_cov['n']))} "
            f"schema={schema_s:.1f}s graph={graph_s:.1f}s",
            flush=True,
        )
        del graph, book

    sample_pool.sort(key=lambda item: item["cell_id"])
    payload["integrity_sample"] = sample_pool[:24]
    payload["formula_cov"] = _pack_cov(formula_all)
    payload["any_point_cov"] = _pack_cov(any_all)
    payload["oracle_cov"] = _pack_cov(oracle_all)
    payload["oracle_pred_ref_cov"] = _pack_cov(pred_ref_all)
    n_oracle = oracle_all["n"]
    n_labeled = sum(
        1
        for rec in payload["oracle_cells"].values()
        if rec["target"] and (rec["target"]["has_immediate"] or rec["target"]["has_stack"])
    )
    payload["phase_a_gate"] = {
        "oracle_with_label_or_stack": n_labeled,
        "oracle_n": n_oracle,
        "share": _rate(n_labeled, n_oracle),
        "pass_threshold": 0.70,
        "passed": (n_labeled / n_oracle) >= 0.70 if n_oracle else False,
        "note": (
            "Second clause (schema on both gold and model sources) is checked "
            "in evaluate without changing extractors."
        ),
    }
    payload["runtime_s"]["all"] = round(time.perf_counter() - started, 3)
    dest = OUT / "schema_extract.json"
    dest.write_text(json.dumps(payload) + "\n")
    (OUT / "phase_a.md").write_text(_render_phase_a(payload) + "\n")
    print(
        f"EXTRACT {dest} gate={payload['phase_a_gate']['passed']} "
        f"oracle_labels={n_labeled}/{n_oracle} runtime={payload['runtime_s']['all']}s",
        flush=True,
    )
    return payload


def _facts_for(
    target: dict[str, Any] | None,
    source: dict[str, Any] | None,
    book: WorkbookSchema,
    graph,
    target_key: tuple[str, int, int],
    source_ref: dict[str, Any] | None,
    peer_source: dict[str, Any] | None,
) -> dict[str, Any]:
    tlab = None if not target else target.get("label_norm")
    slab = None if not source else source.get("label_norm")
    tper = None if not target else target.get("period_key")
    sper = None if not source else source.get("period_key")
    tpar = set((target or {}).get("parents") or [])
    spar = set((source or {}).get("parents") or [])
    lex = lexical_relation(
        None if not target else target.get("label_raw"),
        None if not source else source.get("label_raw"),
    )
    peers = exact_label_counterparts(book, slab)
    same_sheet_repeat = sum(1 for sheet, _row in peers if target and sheet == target["sheet"]) >= 2
    cross = len({sheet for sheet, _row in peers}) >= 2
    cycle = False
    if source_ref is not None:
        src_key = (source_ref["sheet"], source_ref["c1"], source_ref["r1"])
        for formula_key, _slot in graph.point_rev.get(target_key) or []:
            if formula_key == src_key:
                cycle = True
        node = graph.formulas.get(src_key)
        if node is not None:
            for sheet, start, end in formula_a1_references(node.formula):
                host = sheet or src_key[0]
                c1, r1 = parse_a1_cell(start)
                if (host, c1, r1) == target_key:
                    cycle = True
                if end:
                    c2, r2 = parse_a1_cell(end)
                    if host == target_key[0] and min(c1, c2) <= target_key[1] <= max(c1, c2) and min(r1, r2) <= target_key[2] <= max(r1, r2):
                        cycle = True
    w1 = False
    if peer_source and source and peer_source.get("label_norm") and peer_source.get("label_norm") == slab:
        w1 = True
    w3 = bool(
        peer_source
        and source
        and peer_source.get("sheet") == source.get("sheet")
        and peer_source.get("label_norm") == slab
        and slab
    )
    w5 = bool(
        peer_source
        and source
        and peer_source.get("label_norm")
        and slab
        and peer_source.get("label_norm") != slab
    )
    return {
        "P1": bool(tlab and slab and tlab == slab),
        "P2": bool(tpar & spar),
        "P3": bool(tper and sper and tper == sper),
        "P4": bool(tper and sper and tper == sper),
        "P5": same_sheet_repeat,
        "P6": cross,
        "P7": bool(slab and sper and len(peers) >= 2),
        "P9": cross,
        "L1": lex,
        "W1": w1,
        "W3": w3,
        "W5": w5,
        "cycle": cycle,
        "source_label": None if not source else source.get("label_raw"),
        "source_period": sper,
        "n_label_peers": len(peers),
    }


def _s0_favor(gold_f: dict[str, Any], model_f: dict[str, Any]) -> str:
    conservative = ("P1", "P3", "W1", "W3")
    gold_hits = [name for name in conservative if gold_f.get(name) and not model_f.get(name)]
    model_hits = [name for name in conservative if model_f.get(name) and not gold_f.get(name)]
    gold_cycle_ok = (not gold_f.get("cycle")) and model_f.get("cycle")
    model_cycle_ok = (not model_f.get("cycle")) and gold_f.get("cycle")
    if gold_cycle_ok:
        gold_hits.append("cycle_avoided")
    if model_cycle_ok:
        model_hits.append("cycle_avoided")
    if gold_hits and not model_hits:
        return "CLEAR_S0_GOLD"
    if model_hits and not gold_hits:
        return "MODEL_FAVORED"
    if gold_hits and model_hits:
        return "MIXED"
    g_j = (gold_f.get("L1") or {}).get("jaccard")
    m_j = (model_f.get("L1") or {}).get("jaccard")
    g_ex = (gold_f.get("L1") or {}).get("exact_norm")
    m_ex = (model_f.get("L1") or {}).get("exact_norm")
    if (g_ex and not m_ex) or (
        g_j is not None and m_j is not None and g_j >= m_j + 0.20 and g_j >= 0.60
    ):
        return "CLEAR_S1_GOLD"
    if (m_ex and not g_ex) or (
        g_j is not None and m_j is not None and m_j >= g_j + 0.20 and m_j >= 0.60
    ):
        return "MODEL_FAVORED"
    missing = not gold_f.get("source_label") and not model_f.get("source_label")
    if missing:
        return "SCHEMA_MISSING"
    return "TIE"


def _left_right_direction(graph, sheet: str, col: int, row: int) -> dict[str, Any]:
    left = []
    right = []
    index_keys = [
        key
        for key in graph.formulas
        if key[0] == sheet and key[2] == row
    ]
    for key in index_keys:
        node = graph.formulas[key]
        refs = formula_a1_references(node.formula)
        cross = [ref for ref in refs if ref[0] and ref[0] != sheet]
        if not cross:
            continue
        dest = cross[0][0]
        if key[1] < col:
            left.append(dest)
        elif key[1] > col:
            right.append(dest)
    return {
        "LEFT_REGIME_DIRECTION": left[-1] if left else None,
        "RIGHT_REGIME_DIRECTION": right[0] if right else None,
        "DIRECTION_CHANGE_AT_COLUMN": bool(left and right and left[-1] != right[0]),
    }


def cmd_evaluate() -> dict[str, Any]:
    extract = json.loads((OUT / "schema_extract.json").read_text())
    if not extract["phase_a_gate"]["passed"]:
        print("HARD STOP: Phase A gate failed; not evaluating precedent pairs.", flush=True)
        return extract
    slice_doc = _load_slice()
    glm_slice = json.loads(SLICE_36.read_text())
    gold_by = {
        cell["cell_id"]: cell.get("eval_golden_formula")
        for cell in glm_slice["cells"]
        if cell.get("eval_role") == "TRUE_TARGET"
    }
    by_id = {task["id"]: task for task in _task_list()}

    started = time.perf_counter()
    pairs: list[dict[str, Any]] = []
    n1_shared: list[dict[str, Any]] = []
    n2: list[dict[str, Any]] = []
    n3: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    needed_tasks = sorted({cell_id.split(":", 1)[0] for cell_id in extract["oracle_cells"]})
    books: dict[str, tuple[WorkbookSchema, Any]] = {}
    for task_id in needed_tasks:
        task = by_id[task_id]
        source = _input_path(task)
        print(f"EVAL-LOAD {task_id}", flush=True)
        books[task_id] = (build_workbook_schema(source), build_graph(source))

    for cell_id, rec in extract["oracle_cells"].items():
        klass = rec["class"]
        task_id, sheet, col, row = _parse_cell_id(cell_id)
        book, graph = books[task_id]
        gold_formula = gold_by.get(cell_id)
        pred = rec.get("predicted")
        model_refs = parse_refs(pred, sheet)
        gold_refs = parse_refs(gold_formula, sheet)
        aligned = align_refs(model_refs, gold_refs)
        tschema = book.cell(sheet, col, row)
        tcomp = None if tschema is None else compact_schema(tschema)
        direction = _left_right_direction(graph, sheet, col, row)
        peer_source = None
        left_node = None
        for c in range(col - 1, max(1, col - 8) - 1, -1):
            if (sheet, c, row) in graph.formulas:
                left_node = graph.formulas[(sheet, c, row)]
                break
        if left_node is not None:
            left_refs = parse_refs(left_node.formula, sheet)
            if left_refs:
                peer_source = compact_schema(
                    schema_for_cell(book.sheets[left_refs[0]["sheet"]], left_refs[0]["c1"], left_refs[0]["r1"])
                    if left_refs[0]["sheet"] in book.sheets
                    else {"sheet": left_refs[0]["sheet"], "address": left_refs[0]["start"], "label_raw": None, "label_norm": None, "parents": [], "has_immediate": False, "has_stack": False, "has_header": False, "has_period": False, "period_key": None}
                )

        if klass in PRIMARY_EXCLUDE or aligned["same_span_set"]:
            excluded.append(
                {
                    "cell_id": cell_id,
                    "class": klass,
                    "reason": "class_excluded" if klass in PRIMARY_EXCLUDE else "same_precedent_spans",
                    "predicted": pred,
                    "golden": gold_formula,
                }
            )
            for shared in aligned["shared"]:
                n1_shared.append({"cell_id": cell_id, "ref": shared["ref"]["span"]})
            continue

        target_key = (sheet, col, row)
        for slot in aligned["differing"]:
            mref = slot["model_ref"]
            gref = slot["gold_ref"]
            mschema = None
            gschema = None
            if mref and mref["sheet"] in book.sheets:
                mschema = compact_schema(schema_for_cell(book.sheets[mref["sheet"]], mref["c1"], mref["r1"]))
            if gref and gref["sheet"] in book.sheets:
                gschema = compact_schema(schema_for_cell(book.sheets[gref["sheet"]], gref["c1"], gref["r1"]))
            gold_f = _facts_for(tcomp, gschema, book, graph, target_key, gref, peer_source)
            model_f = _facts_for(tcomp, mschema, book, graph, target_key, mref, peer_source)
            if not gschema and not mschema:
                cat = "SCHEMA_MISSING"
            else:
                cat = _s0_favor(gold_f, model_f)
            explanation = _explain(cat, gold_f, model_f, direction)
            pair = {
                "target": cell_id,
                "class": klass,
                "model_formula": pred,
                "golden_formula": gold_formula,
                "alignment": slot["alignment"],
                "model_source": None if not mref else f"{mref['sheet']}!{mref['start']}" + ("" if not mref["end"] else f":{mref['end']}"),
                "golden_source": None if not gref else f"{gref['sheet']}!{gref['start']}" + ("" if not gref["end"] else f":{gref['end']}"),
                "target_label": None if not tcomp else tcomp.get("label_raw"),
                "target_header": None if not tcomp else tcomp.get("header_raw"),
                "target_period": None if not tcomp else tcomp.get("period_key"),
                "model_source_label": None if not mschema else mschema.get("label_raw"),
                "golden_source_label": None if not gschema else gschema.get("label_raw"),
                "model_source_header": None if not mschema else mschema.get("header_raw"),
                "golden_source_header": None if not gschema else gschema.get("header_raw"),
                "S0_gold": {k: gold_f[k] for k in ("P1", "P2", "P3", "P5", "P6", "W1", "W3", "W5", "cycle")},
                "S0_model": {k: model_f[k] for k in ("P1", "P2", "P3", "P5", "P6", "W1", "W3", "W5", "cycle")},
                "S1_gold": gold_f["L1"],
                "S1_model": model_f["L1"],
                "direction": direction,
                "category": cat,
                "explanation": explanation,
            }
            pairs.append(pair)
            if gref and gref["sheet"] in book.sheets:
                distractor = _distractor(book, graph, gref, sheet, col, row)
                if distractor is not None:
                    dschema = compact_schema(schema_for_cell(book.sheets[distractor[0]], distractor[1], distractor[2]))
                    d_f = _facts_for(tcomp, dschema, book, graph, target_key, None, peer_source)
                    n2.append(
                        {
                            "cell_id": cell_id,
                            "gold": gschema.get("label_raw") if gschema else None,
                            "distractor": dschema.get("label_raw"),
                            "category": _s0_favor(gold_f, d_f),
                        }
                    )
            if gschema and gschema.get("label_norm"):
                peers = exact_label_counterparts(book, gschema["label_norm"])
                if len(peers) >= 2:
                    n3.append(
                        {
                            "cell_id": cell_id,
                            "label": gschema["label_raw"],
                            "n_peers": len(peers),
                            "sheets": sorted({s for s, _r in peers}),
                        }
                    )

    counts = Counter(pair["category"] for pair in pairs)
    n_el = len(pairs)
    distinguishable = counts["CLEAR_S0_GOLD"] + counts["CLEAR_S1_GOLD"]
    by_class: dict[str, Counter] = defaultdict(Counter)
    for pair in pairs:
        by_class[pair["class"]][pair["category"]] += 1
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": True,
        "golden_used_in_extraction": False,
        "runtime_s": round(time.perf_counter() - started, 3),
        "extract_runtime_s": extract["runtime_s"],
        "phase_a_gate": extract["phase_a_gate"],
        "n_eligible_slots": n_el,
        "counts": dict(counts),
        "schema_distinguishable_rate": _rate(distinguishable, n_el),
        "s0_alone_rate": _rate(counts["CLEAR_S0_GOLD"], n_el),
        "by_class": {klass: dict(vals) for klass, vals in by_class.items()},
        "pairs": pairs,
        "excluded": excluded,
        "n1_shared_slots": len(n1_shared),
        "n2_distractors": n2,
        "n3_label_ambiguity": n3,
        "interpretation": _interpret(counts, n_el, extract),
    }
    dest = OUT / "evaluation.json"
    dest.write_text(json.dumps(report) + "\n")
    (OUT / "evaluation.md").write_text(_render_eval(report, extract) + "\n")
    print(f"EVAL {dest} n_slots={n_el} gate={report['interpretation']['gate']}", flush=True)
    return report


def _distractor(book, graph, gold_ref, sheet, col, row):
    gsheet, gc, gr = gold_ref["sheet"], gold_ref["c1"], gold_ref["r1"]
    for offset in range(1, 9):
        for other in (gr - offset, gr + offset):
            if other < 1:
                continue
            key = (gsheet, gc, other)
            if key in graph.formulas or (
                gsheet in book.sheets and book.sheets[gsheet].values.get((gc, other)) not in (None, "")
            ):
                if other != gr:
                    return (gsheet, gc, other)
    return None


def _explain(cat, gold_f, model_f, direction) -> str:
    bits = [cat]
    if gold_f.get("P1") != model_f.get("P1"):
        bits.append(f"P1 gold={gold_f.get('P1')} model={model_f.get('P1')}")
    if gold_f.get("cycle") or model_f.get("cycle"):
        bits.append(f"cycle gold={gold_f.get('cycle')} model={model_f.get('cycle')}")
    if direction.get("DIRECTION_CHANGE_AT_COLUMN"):
        bits.append(
            f"dir L={direction.get('LEFT_REGIME_DIRECTION')} R={direction.get('RIGHT_REGIME_DIRECTION')}"
        )
    gj = (gold_f.get("L1") or {}).get("jaccard")
    mj = (model_f.get("L1") or {}).get("jaccard")
    bits.append(f"jaccard gold={gj} model={mj}")
    return "; ".join(bits)


def _interpret(counts: Counter, n_el: int, extract: dict[str, Any]) -> dict[str, Any]:
    dist = counts["CLEAR_S0_GOLD"] + counts["CLEAR_S1_GOLD"]
    share = _rate(dist, n_el) or 0.0
    model_fav = counts["MODEL_FAVORED"]
    missing = counts["TIE"] + counts["SCHEMA_MISSING"]
    if n_el and share >= 0.5 and model_fav <= max(1, n_el // 5):
        gate = "strong_positive"
        conclusion = (
            "Label/schema relations contain information missing from formula/"
            "dataflow topology and directly explain known precedent-selection failures."
        )
        nxt = "broad schema census"
    elif n_el and (dist >= 2 or counts["MIXED"] >= 1) and missing < n_el:
        gate = "partial_heterogeneous"
        conclusion = (
            "Schema is a useful family of typed relations, but not one universal "
            "correspondence layer."
        )
        nxt = "targeted follow-up on classes schema actually splits; not a general S2 ontology"
    else:
        gate = "weak"
        conclusion = (
            "Conservative label/schema structure does not explain the known "
            "precedent-selection failures."
        )
        nxt = "stop; do not proceed to a large semantic IR"
    return {
        "gate": gate,
        "conclusion": conclusion,
        "next": nxt,
        "extraction_vs_information": (
            "SCHEMA_MISSING counts extraction failure; TIE/MODEL_FAVORED with "
            "recovered labels is representation insufficiency; CLEAR_* is "
            "positive information."
        ),
        "phase_a_passed": extract["phase_a_gate"]["passed"],
    }


def _render_phase_a(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase A — mechanical schema extraction",
        "",
        f"Runtime {payload['runtime_s']['all']}s. Goldens not used.",
        "",
        "## Coverage",
        "",
        "| population | n | immediate | stack | header | period | same-label | cross-sheet | label+period |",
        "|------------|--:|----------:|------:|-------:|-------:|-----------:|------------:|-------------:|",
    ]
    for name, key in (
        ("formula-bearing", "formula_cov"),
        ("ANY_POINT", "any_point_cov"),
        ("ORACLE targets", "oracle_cov"),
        ("ORACLE model refs", "oracle_pred_ref_cov"),
    ):
        c = payload[key]
        lines.append(
            f"| {name} | {c['n']} | {_pct(c['pct_immediate'])} | {_pct(c['pct_stack'])} | "
            f"{_pct(c['pct_header'])} | {_pct(c['pct_period'])} | {_pct(c['pct_same_label'])} | "
            f"{_pct(c['pct_cross_sheet_label'])} | {_pct(c['pct_label_period'])} |"
        )
    lines += ["", "## Per workbook (formula-bearing)", ""]
    lines.append("| task | n | immediate | stack | header | period | cross-sheet labels |")
    lines.append("|------|--:|----------:|------:|-------:|-------:|-------------------:|")
    for tid, task in payload["tasks"].items():
        f = task["formula"]
        lines.append(
            f"| {tid} | {f['n']} | {_pct(f['pct_immediate'])} | {_pct(f['pct_stack'])} | "
            f"{_pct(f['pct_header'])} | {_pct(f['pct_period'])} | {task['n_cross_sheet_labels']} |"
        )
    gate = payload["phase_a_gate"]
    lines += [
        "",
        "## Gate",
        "",
        f"ORACLE targets with immediate label or stack: {gate['oracle_with_label_or_stack']}/{gate['oracle_n']} "
        f"({_pct(gate['share'])}). passed={gate['passed']}",
        "",
        "## Integrity sample",
        "",
    ]
    for item in payload["integrity_sample"]:
        s = item["schema"]
        lines.append(
            f"- `{item['cell_id']}` label={s.get('label_raw')!r} header={s.get('header_raw')!r} "
            f"period={s.get('period_key')} parents={s.get('parents')}"
        )
    return "\n".join(lines)


def _render_eval(report: dict[str, Any], extract: dict[str, Any]) -> str:
    lines = [
        "# Phase B — ORACLE precedent discrimination",
        "",
        f"Eligible differing-precedent slots: {report['n_eligible_slots']}",
        f"Distinguishable (S0+S1): {_pct(report['schema_distinguishable_rate'])}",
        f"S0 alone: {_pct(report['s0_alone_rate'])}",
        "",
        str(report["counts"]),
        "",
        "## Pairs",
        "",
    ]
    for pair in report["pairs"]:
        lines.append(
            f"- `{pair['target']}` [{pair['class']}] {pair['category']}: "
            f"model `{pair['model_source']}` vs gold `{pair['golden_source']}` "
            f"| T={pair['target_label']!r} M={pair['model_source_label']!r} G={pair['golden_source_label']!r} "
            f"| {pair['explanation']}"
        )
    lines += ["", "## Conclusion", "", f"**{report['interpretation']['gate']}**", "", report["interpretation"]["conclusion"]]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("extract", "evaluate", "all"), nargs="?", default="all")
    args = parser.parse_args()
    extract = None
    if args.phase in ("extract", "all"):
        extract = cmd_extract()
    if args.phase in ("evaluate", "all"):
        if extract is None:
            extract = json.loads((OUT / "schema_extract.json").read_text())
        if not extract["phase_a_gate"]["passed"] and args.phase == "all":
            print("HARD STOP after Phase A.", flush=True)
            return
        cmd_evaluate()


if __name__ == "__main__":
    main()
