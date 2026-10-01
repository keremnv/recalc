#!/usr/bin/env python3
"""Offline diagnostic of operational dependence structure on ORACLE_WHERE failures.

Phases:
  extract  — gold-blind substrate on the frozen 12 (no goldens)
  evaluate — model vs golden wiring using goldens as labels only
  all      — extract then evaluate

No agents, OpenRouter, workbook writes, official scorer, classifiers, LLMs,
or semantic PRODUCES/PARAMETERIZES predicates.
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
from formula_dependency_selection_probe import _input_path, _load_slice, _task_list  # noqa: E402
from formula_operational import (  # noqa: E402
    DEFINITIONS,
    LEFT_RIGHT_WINDOWS,
    OperationalView,
    aggregate_templates,
    ancestor_of_peers,
    build_view,
    candidate_orientation_match,
    collect_peers,
    cycle_if_added,
    descendant_of_peers,
    direct_dependents,
    edge_signature,
    orientation,
    parse_use_def_slots,
    reduction_of,
    reduction_relations,
    source_profile,
    template_match,
)
from formula_schema_probe import (  # noqa: E402
    GLM_OUT,
    ORACLE_CLASSES,
    SLICE_36,
    align_refs,
    parse_refs,
)
from xlsx_metadata_repair import install  # noqa: E402

install()

OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-operational-probe"
)
SCHEMA_EVAL = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-schema-probe/evaluation.json"
)

PRIMARY_CLASSES = {
    "WRONG_SOURCE_OR_HOMOLOGUE",
    "WRONG_AGGREGATION_LEVEL",
    "DATAFLOW_DIRECTION",
}
SECONDARY_CLASSES = {"TASK_TEXT_OR_TEXTBOOK_TEMPLATE", "INSUFFICIENT_OBSERVATION"}
EXCLUDE_CLASSES = {"CORRECT", "ALGEBRAIC_EQUIVALENT", "EMPTY_GENERATION"}
_TRIVIAL_LITS = {0, 1}


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
    from ranges import parse_a1_cell

    col, row = parse_a1_cell(addr)
    return task_id, sheet, col, row


def _src_id(ref: dict[str, Any] | None) -> str | None:
    if not ref:
        return None
    text = f"{ref['sheet']}!{ref['start']}"
    if ref.get("end"):
        text += f":{ref['end']}"
    return text


def _ref_key(ref: dict[str, Any]) -> tuple[str, int, int]:
    return (ref["sheet"], ref["c1"], ref["r1"])


def classify_object(model_formula: str | None, gold_formula: str | None, aligned: dict[str, Any]) -> str:
    m_parsed = parse_use_def_slots(model_formula, "S", 1, 1)
    g_parsed = parse_use_def_slots(gold_formula, "S", 1, 1)
    m_red = reduction_of(model_formula, m_parsed)
    g_red = reduction_of(gold_formula, g_parsed)
    m_range = any(slot["is_range"] for slot in m_parsed["slots"])
    g_range = any(slot["is_range"] for slot in g_parsed["slots"])
    reduction_mismatch = (
        m_red["is_reduction"] or g_red["is_reduction"] or m_range or g_range
    ) and (
        m_red["operator"] != g_red["operator"]
        or m_red["operand_count"] != g_red["operand_count"]
        or m_red["point_vs_range"] != g_red["point_vs_range"]
        or m_range != g_range
    )
    if reduction_mismatch:
        return "REDUCTION_CHOICE"
    leftover_gold_only = [
        slot for slot in aligned["differing"] if slot["gold_ref"] and not slot["model_ref"]
    ]
    leftover_both = [
        slot for slot in aligned["differing"] if slot["gold_ref"] and slot["model_ref"]
    ]
    m_extra = {lit for lit in m_parsed["literals"] if lit not in _TRIVIAL_LITS}
    g_extra = {lit for lit in g_parsed["literals"] if lit not in _TRIVIAL_LITS}
    if leftover_gold_only and not leftover_both and (m_extra - g_extra):
        return "LITERAL_REFERENCE_CHOICE"
    if leftover_gold_only and not leftover_both and g_parsed["slots"] and m_extra:
        return "LITERAL_REFERENCE_CHOICE"
    return "EDGE_CHOICE"


def _template_clear(agg: dict[str, Any]) -> bool:
    if not agg.get("n"):
        return False
    if agg.get("peer_conflict"):
        return False
    return agg["n_strict"] >= 2 or (
        agg["n_vector_and_sheet"] >= 1 and agg["n_vector_and_sheet"] == agg["n"]
    )


def discriminate_edge(gold_ev: dict[str, Any], model_ev: dict[str, Any]) -> str:
    if gold_ev.get("missing") and model_ev.get("missing"):
        return "OPERATIONAL_MISSING"
    gold_strong: list[str] = []
    model_strong: list[str] = []
    if model_ev["cycle"]["C3_cycle_if_added"] and not gold_ev["cycle"]["C3_cycle_if_added"]:
        gold_strong.append("cycle")
    if gold_ev["cycle"]["C3_cycle_if_added"] and not model_ev["cycle"]["C3_cycle_if_added"]:
        model_strong.append("cycle")
    gt = _template_clear(gold_ev["template"])
    mt = _template_clear(model_ev["template"])
    if gt and not mt:
        gold_strong.append("template")
    if mt and not gt:
        model_strong.append("template")
    if gold_ev.get("matches_target_side") and model_ev.get("matches_opposite_side"):
        gold_strong.append("orientation")
    if model_ev.get("matches_target_side") and gold_ev.get("matches_opposite_side"):
        model_strong.append("orientation")
    if gold_strong and not model_strong:
        return "CLEAR_OPERATIONAL_GOLD"
    if model_strong and not gold_strong:
        return "MODEL_FAVORED"
    if gold_strong and model_strong:
        return "MIXED"
    if gold_ev.get("missing") or model_ev.get("missing"):
        return "OPERATIONAL_MISSING"
    return "TIE"


def discriminate_reduction(
    gold_rel: dict[str, Any],
    model_rel: dict[str, Any],
    n_peers: int,
) -> str:
    if n_peers <= 0:
        return "REDUCTION_STRUCTURE_MISSING"
    gold_strong: list[str] = []
    model_strong: list[str] = []
    if gold_rel.get("peer_conflict") or model_rel.get("peer_conflict"):
        return "MIXED_REDUCTION"
    for name in (
        "R4_peer_reduction_shape_match",
        "R1_reduces_contiguous_range",
        "R2_reduces_sibling_aggregates",
        "R5_range_boundary_match",
        "R6_reduction_level_match",
    ):
        if gold_rel.get(name) and not model_rel.get(name):
            gold_strong.append(name)
        if model_rel.get(name) and not gold_rel.get(name):
            model_strong.append(name)
    if gold_strong and not model_strong:
        return "CLEAR_REDUCTION_GOLD"
    if model_strong and not gold_strong:
        return "MODEL_REDUCTION_FAVORED"
    if gold_strong and model_strong:
        return "MIXED_REDUCTION"
    return "TIE_REDUCTION"


def _target_side(p1: dict[str, Any], orient: dict[str, Any]) -> str | None:
    change = any(orient[f"w{w}"]["O3_change"] for w in LEFT_RIGHT_WINDOWS)
    if not change:
        return None
    left = p1.get("left")
    right = p1.get("right")
    if left and (not right or left["distance"] <= right["distance"]):
        return "left"
    if right:
        return "right"
    return None


def _compact_peer(peer: dict[str, Any]) -> dict[str, Any]:
    slots = (peer.get("parsed") or {}).get("slots") or []
    return {
        "provenance": peer.get("provenance"),
        "address": peer.get("address"),
        "formula": peer.get("formula"),
        "eq_id": peer.get("eq_id"),
        "distance": peer.get("distance"),
        "via_consumer": peer.get("via_consumer"),
        "reduction": peer.get("reduction"),
        "n_slots": len(slots),
        "slots": [
            {
                "sheet": slot["sheet"],
                "start": slot["start"],
                "end": slot.get("end"),
                "is_range": slot["is_range"],
                "dcol": slot["dcol"],
                "drow": slot["drow"],
                "enclosing": slot["enclosing"],
                "abs_mask": slot["abs_mask"],
            }
            for slot in slots
        ],
    }


def cmd_extract(views: dict[str, OperationalView] | None = None) -> tuple[dict[str, Any], dict[str, OperationalView]]:
    slice_doc = _load_slice()
    score = json.loads((GLM_OUT / "score.json").read_text())
    by_id = {task["id"]: task for task in _task_list()}
    oracle_ids = [row["cell_id"] for row in score["oracle_where"]["cells"]]
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    built: dict[str, OperationalView] = {} if views is None else views
    payload: dict[str, Any] = {
        "extracted_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "direction_convention": "DATA_DEPENDENCE(S, C) = S → C (precedent → dependent)",
        "definitions": DEFINITIONS,
        "oracle_classes_frozen": ORACLE_CLASSES,
        "windows": list(LEFT_RIGHT_WINDOWS),
        "reused": [
            "fm-target-selection-probe-12",
            "build_graph / formula fingerprints / formula_a1_references",
            "formula-dependency-glm-probe 18 ORACLE_WHERE targets",
            "prior ORACLE autopsy class labels (frozen)",
        ],
        "runtime_s": {},
        "tasks": {},
        "oracle_cells": {},
        "coverage": {
            "n_oracle": len(oracle_ids),
            "n_with_p1": 0,
            "n_with_p2": 0,
            "n_with_p3": 0,
            "n_with_any_peer": 0,
            "n_with_dependents": 0,
            "n_orientation_change": 0,
            "n_parser_fail_peers": 0,
        },
    }
    for item in slice_doc["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        source = _input_path(task)
        print(f"EXTRACT {task_id}", flush=True)
        t0 = time.perf_counter()
        if task_id not in built:
            built[task_id] = build_view(build_graph(source))
        view = built[task_id]
        graph_s = time.perf_counter() - t0
        cov = dict(view.graph.coverage)
        payload["tasks"][task_id] = {
            "family": item["family"],
            "graph": cov,
            "n_formula_rows": len(view.by_row),
        }
        payload["runtime_s"][task_id] = round(graph_s, 3)
        for cell_id in oracle_ids:
            if not cell_id.startswith(task_id + ":"):
                continue
            _tid, sheet, col, row = _parse_cell_id(cell_id)
            peers = collect_peers(view, sheet, col, row)
            orient = orientation(view, sheet, col, row)
            deps = direct_dependents(view, (sheet, col, row))
            parser_fail = any(
                not (peer.get("parsed") or {}).get("parser_ok", True)
                for peer in peers["formula_peers"]
            )
            rec = {
                "cell_id": cell_id,
                "class": ORACLE_CLASSES.get(cell_id),
                "n_direct_dependents": len(deps),
                "dependent_sample": [
                    f"{k[0]}!{a1_address(k[1], k[2])}" for k in deps[:8]
                ],
                "peers": {
                    "n_p1": peers["n_p1"],
                    "n_p2": peers["n_p2"],
                    "n_p3": peers["n_p3"],
                    "n_formula_peers": peers["n_formula_peers"],
                    "P1_left": None if not peers["P1"]["left"] else _compact_peer(peers["P1"]["left"]),
                    "P1_right": None
                    if not peers["P1"]["right"]
                    else _compact_peer(peers["P1"]["right"]),
                    "P2_sample": [_compact_peer(p) for p in peers["P2"][:6]],
                    "P3_sample": [_compact_peer(p) for p in peers["P3"][:6]],
                },
                "orientation": orient,
                "parser_fail_peers": parser_fail,
            }
            payload["oracle_cells"][cell_id] = rec
            c = payload["coverage"]
            c["n_with_p1"] += int(peers["n_p1"] > 0)
            c["n_with_p2"] += int(peers["n_p2"] > 0)
            c["n_with_p3"] += int(peers["n_p3"] > 0)
            c["n_with_any_peer"] += int(peers["n_formula_peers"] > 0)
            c["n_with_dependents"] += int(len(deps) > 0)
            c["n_orientation_change"] += int(
                any(orient[f"w{w}"]["O3_change"] for w in LEFT_RIGHT_WINDOWS)
            )
            c["n_parser_fail_peers"] += int(parser_fail)
        print(f"  supported={cov.get('supported')} runtime={graph_s:.1f}s", flush=True)

    payload["runtime_s"]["all"] = round(time.perf_counter() - started, 3)
    dest = OUT / "operational_extract.json"
    dest.write_text(json.dumps(payload) + "\n")
    (OUT / "extract.md").write_text(_render_extract(payload) + "\n")
    print(f"EXTRACT {dest} runtime={payload['runtime_s']['all']}s", flush=True)
    return payload, built


def _literal_facts(formula: str | None, parsed: dict[str, Any], peers: list[dict[str, Any]]) -> dict[str, Any]:
    abs_refs = [
        (slot["sheet"], slot["start"], slot["abs_mask"])
        for slot in parsed["slots"]
        if "$" in (slot.get("abs_mask") or "")
    ]
    peer_lits = []
    peer_abs = []
    peer_has_ref = False
    peer_has_lit = False
    for peer in peers:
        red = peer.get("reduction") or {}
        if red.get("has_literal"):
            peer_has_lit = True
            peer_lits.extend(red.get("literals") or [])
        pslots = (peer.get("parsed") or {}).get("slots") or []
        if pslots:
            peer_has_ref = True
        for slot in pslots:
            if "$" in (slot.get("abs_mask") or ""):
                peer_abs.append((slot["sheet"], slot["start"], slot["abs_mask"]))
    return {
        "V1_peers_use_literal": peer_has_lit,
        "V2_peers_use_reference": peer_has_ref,
        "V3_peers_use_same_absolute_reference": bool(abs_refs) and any(
            item[:2] == abs_refs[0][:2] for item in peer_abs
        ),
        "formula_literals": parsed.get("literals") or [],
        "has_nontrivial_literal": any(lit not in _TRIVIAL_LITS for lit in (parsed.get("literals") or [])),
        "abs_refs": [f"{s}!{a}/{m}" for s, a, m in abs_refs],
        "peer_abs_n": len(peer_abs),
        "skeleton": parsed.get("shape"),
    }


def _edge_bundle(
    view: OperationalView,
    target: tuple[str, int, int],
    ref: dict[str, Any] | None,
    slot_from_formula: dict[str, Any] | None,
    peers_pack: dict[str, Any],
    orient: dict[str, Any],
) -> dict[str, Any]:
    if ref is None:
        return {
            "missing": True,
            "cycle": {
                "C1_direct_downstream_conflict": False,
                "C2_transitive_downstream_conflict": False,
                "C3_cycle_if_added": False,
                "shortest_T_to_S": None,
            },
            "template": {
                "n": 0,
                "n_strict": 0,
                "n_vector_and_sheet": 0,
                "peer_conflict": False,
            },
            "matches_target_side": False,
            "matches_opposite_side": False,
            "signature": None,
            "profile": None,
            "C4": False,
            "C5": False,
            "orient_match": None,
        }
    source = _ref_key(ref)
    cycle = cycle_if_added(view, source, target)
    matches = [
        template_match(peer, slot_from_formula, source, target, view)
        for peer in peers_pack["formula_peers"]
    ]
    agg = aggregate_templates(matches)
    omatch = candidate_orientation_match(orient, source[0], target[0])
    side = _target_side(peers_pack["P1"], orient)
    matches_target = False
    matches_opposite = False
    if side == "left":
        matches_target = any(omatch[f"w{w}"]["O4_matches_left"] for w in LEFT_RIGHT_WINDOWS)
        matches_opposite = any(omatch[f"w{w}"]["O5_matches_right"] for w in LEFT_RIGHT_WINDOWS)
    elif side == "right":
        matches_target = any(omatch[f"w{w}"]["O5_matches_right"] for w in LEFT_RIGHT_WINDOWS)
        matches_opposite = any(omatch[f"w{w}"]["O4_matches_left"] for w in LEFT_RIGHT_WINDOWS)
    peer_keys = [peer["key"] for peer in peers_pack["formula_peers"]]
    profile = source_profile(view, source, peers_pack["formula_peers"])
    sig = edge_signature(view, source, target, slot_from_formula)
    return {
        "missing": False,
        "source": _src_id(ref),
        "cycle": cycle,
        "template": agg,
        "template_rows": matches[:6],
        "matches_target_side": matches_target,
        "matches_opposite_side": matches_opposite,
        "target_side": side,
        "orient_match": omatch,
        "signature": sig,
        "profile": profile,
        "C4_source_is_upstream": ancestor_of_peers(view, source, peer_keys),
        "C5_source_is_downstream": descendant_of_peers(view, source, peer_keys, target),
    }


def _slot_for_ref(parsed: dict[str, Any], ref: dict[str, Any] | None) -> dict[str, Any] | None:
    if ref is None:
        return None
    for slot in parsed["slots"]:
        if (
            slot["sheet"] == ref["sheet"]
            and slot["c1"] == ref["c1"]
            and slot["r1"] == ref["r1"]
            and bool(slot["is_range"]) == bool(ref["is_range"])
        ):
            return slot
    return parsed["slots"][ref.get("i", 0)] if parsed["slots"] else None


def cmd_evaluate(extract: dict[str, Any], views: dict[str, OperationalView] | None = None) -> dict[str, Any]:
    glm_slice = json.loads(SLICE_36.read_text())
    gold_by = {
        cell["cell_id"]: cell.get("eval_golden_formula")
        for cell in glm_slice["cells"]
        if cell.get("eval_role") == "TRUE_TARGET"
    }
    score = json.loads((GLM_OUT / "score.json").read_text())
    pred_by = {row["cell_id"]: row.get("predicted") for row in score["oracle_where"]["cells"]}
    schema_pairs = []
    if SCHEMA_EVAL.exists():
        schema_pairs = json.loads(SCHEMA_EVAL.read_text()).get("pairs") or []
    schema_index = {
        (p["target"], p.get("model_source"), p.get("golden_source")): p["category"]
        for p in schema_pairs
    }
    by_id = {task["id"]: task for task in _task_list()}
    needed = sorted({cell_id.split(":", 1)[0] for cell_id in extract["oracle_cells"]})
    built: dict[str, OperationalView] = dict(views or {})
    started = time.perf_counter()
    for task_id in needed:
        if task_id in built:
            continue
        print(f"EVAL-LOAD {task_id}", flush=True)
        built[task_id] = build_view(build_graph(_input_path(by_id[task_id])))

    edges: list[dict[str, Any]] = []
    reductions: list[dict[str, Any]] = []
    literals: list[dict[str, Any]] = []
    scaling: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    n1: list[dict[str, Any]] = []
    n2: list[dict[str, Any]] = []
    n3: list[dict[str, Any]] = []

    for cell_id, rec in extract["oracle_cells"].items():
        klass = rec["class"]
        task_id, sheet, col, row = _parse_cell_id(cell_id)
        view = built[task_id]
        target = (sheet, col, row)
        pred = pred_by.get(cell_id)
        gold_formula = gold_by.get(cell_id)
        model_refs = parse_refs(pred, sheet)
        gold_refs = parse_refs(gold_formula, sheet)
        aligned = align_refs(model_refs, gold_refs)
        m_parsed = parse_use_def_slots(pred, sheet, col, row)
        g_parsed = parse_use_def_slots(gold_formula, sheet, col, row)
        peers_pack = collect_peers(view, sheet, col, row)
        orient = orientation(view, sheet, col, row)

        if klass in EXCLUDE_CLASSES:
            excluded.append(
                {
                    "cell_id": cell_id,
                    "class": klass,
                    "reason": "class_excluded",
                    "predicted": pred,
                    "golden": gold_formula,
                }
            )
            for shared in aligned["shared"]:
                n1.append(_n1_row(cell_id, shared, view, target, peers_pack, orient, m_parsed))
            continue
        if aligned["same_span_set"]:
            excluded.append(
                {
                    "cell_id": cell_id,
                    "class": klass,
                    "reason": "same_precedent_spans",
                    "predicted": pred,
                    "golden": gold_formula,
                }
            )
            scaling.append(_scaling_row(cell_id, klass, pred, gold_formula, m_parsed, g_parsed, peers_pack))
            for shared in aligned["shared"]:
                n1.append(_n1_row(cell_id, shared, view, target, peers_pack, orient, m_parsed))
            continue

        obj = classify_object(pred, gold_formula, aligned)
        population = "primary" if klass in PRIMARY_CLASSES else "secondary"
        peer_reds = [
            peer.get("reduction") or {}
            for peer in peers_pack["formula_peers"]
            if peer.get("reduction")
        ]

        if obj == "REDUCTION_CHOICE":
            m_red = reduction_of(pred, m_parsed)
            g_red = reduction_of(gold_formula, g_parsed)
            m_rel = reduction_relations(m_red, peer_reds, view, m_parsed["slots"])
            g_rel = reduction_relations(g_red, peer_reds, view, g_parsed["slots"])
            cat = discriminate_reduction(g_rel, m_rel, peers_pack["n_formula_peers"])
            schema_cats = [
                p["category"]
                for p in schema_pairs
                if p["target"] == cell_id
            ]
            reductions.append(
                {
                    "object": "REDUCTION_CHOICE",
                    "population": population,
                    "target": cell_id,
                    "class": klass,
                    "model_formula": pred,
                    "golden_formula": gold_formula,
                    "model_reduction": m_red,
                    "golden_reduction": g_red,
                    "model_relations": m_rel,
                    "golden_relations": g_rel,
                    "n_peers": peers_pack["n_formula_peers"],
                    "peer_formulas": [p.get("formula") for p in peers_pack["formula_peers"][:6]],
                    "category": cat,
                    "schema_categories": schema_cats,
                    "explanation": _explain_reduction(cat, g_red, m_red, g_rel, m_rel),
                }
            )
            continue

        if obj == "LITERAL_REFERENCE_CHOICE":
            m_lit = _literal_facts(pred, m_parsed, peers_pack["formula_peers"])
            g_lit = _literal_facts(gold_formula, g_parsed, peers_pack["formula_peers"])
            v4_gold = (not g_lit["has_nontrivial_literal"] and g_lit["V2_peers_use_reference"]) or g_lit[
                "V3_peers_use_same_absolute_reference"
            ]
            v4_model = m_lit["has_nontrivial_literal"] and m_lit["V1_peers_use_literal"]
            literals.append(
                {
                    "object": "LITERAL_REFERENCE_CHOICE",
                    "population": population,
                    "target": cell_id,
                    "class": klass,
                    "model_formula": pred,
                    "golden_formula": gold_formula,
                    "model_facts": m_lit,
                    "golden_facts": g_lit,
                    "V4_gold_matches_peer_ref_role": v4_gold,
                    "V4_model_matches_peer_literal_role": v4_model,
                    "schema_categories": [
                        p["category"] for p in schema_pairs if p["target"] == cell_id
                    ],
                }
            )
            continue

        for shared in aligned["shared"]:
            n1.append(_n1_row(cell_id, shared, view, target, peers_pack, orient, m_parsed))

        both = [
            slot for slot in aligned["differing"] if slot["model_ref"] and slot["gold_ref"]
        ]
        if not both:
            continue
        for slot in both:
            mref = slot["model_ref"]
            gref = slot["gold_ref"]
            m_slot = _slot_for_ref(m_parsed, mref)
            g_slot = _slot_for_ref(g_parsed, gref)
            gold_ev = _edge_bundle(view, target, gref, g_slot, peers_pack, orient)
            model_ev = _edge_bundle(view, target, mref, m_slot, peers_pack, orient)
            cat = discriminate_edge(gold_ev, model_ev)
            schema_cat = schema_index.get((cell_id, _src_id(mref), _src_id(gref)))
            row_out = {
                "object": "EDGE_CHOICE",
                "population": population,
                "target": cell_id,
                "class": klass,
                "model_formula": pred,
                "golden_formula": gold_formula,
                "slot_alignment": slot["alignment"],
                "model_source": _src_id(mref),
                "golden_source": _src_id(gref),
                "gold": _summarize_edge(gold_ev),
                "model": _summarize_edge(model_ev),
                "category": cat,
                "schema_category": schema_cat,
                "explanation": _explain_edge(cat, gold_ev, model_ev),
                "peer_conflict": gold_ev["template"]["peer_conflict"]
                or model_ev["template"]["peer_conflict"],
            }
            edges.append(row_out)
            if row_out["peer_conflict"]:
                n3.append({"cell_id": cell_id, "model": _src_id(mref), "gold": _src_id(gref)})
            distractor = _distractor(view, gref, target)
            if distractor is not None:
                dref = {
                    "sheet": distractor[0],
                    "c1": distractor[1],
                    "r1": distractor[2],
                    "start": a1_address(distractor[1], distractor[2]),
                    "end": None,
                    "is_range": False,
                }
                d_slot = {
                    **(g_slot or {}),
                    "sheet": distractor[0],
                    "c1": distractor[1],
                    "r1": distractor[2],
                    "dcol": distractor[1] - col,
                    "drow": distractor[2] - row,
                    "is_range": False,
                }
                d_ev = _edge_bundle(view, target, dref, d_slot, peers_pack, orient)
                n2.append(
                    {
                        "cell_id": cell_id,
                        "gold": _src_id(gref),
                        "distractor": _src_id(dref),
                        "category": discriminate_edge(gold_ev, d_ev),
                    }
                )

    primary_edges = [e for e in edges if e["population"] == "primary"]
    primary_red = [r for r in reductions if r["population"] == "primary"]
    edge_counts = Counter(e["category"] for e in primary_edges)
    red_counts = Counter(r["category"] for r in primary_red)
    explained = set()
    for e in primary_edges:
        if e["category"] == "CLEAR_OPERATIONAL_GOLD":
            explained.add(e["target"])
    for r in primary_red:
        if r["category"] == "CLEAR_REDUCTION_GOLD":
            explained.add(r["target"])
    cross = Counter()
    for e in primary_edges:
        cross[f"{e.get('schema_category')}|{e['category']}"] += 1
    for r in primary_red:
        sch = r["schema_categories"][0] if r["schema_categories"] else None
        cross[f"{sch}|{r['category']}"] += 1

    vocab = _vocab_verdict(primary_edges, primary_red, extract)
    gate = _interpret(edge_counts, red_counts, primary_edges, primary_red, explained)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": True,
        "golden_used_in_extraction": False,
        "runtime_s": round(time.perf_counter() - started, 3),
        "extract_runtime_s": extract["runtime_s"],
        "n_primary_edge": len(primary_edges),
        "n_primary_reduction": len(primary_red),
        "edge_counts": dict(edge_counts),
        "reduction_counts": dict(red_counts),
        "clear_operational_gold_rate": _rate(edge_counts["CLEAR_OPERATIONAL_GOLD"], len(primary_edges)),
        "clear_reduction_gold_rate": _rate(red_counts["CLEAR_REDUCTION_GOLD"], len(primary_red)),
        "n_oracle_targets_clearly_explained": len(explained),
        "explained_targets": sorted(explained),
        "schema_x_operational": dict(cross),
        "edges": edges,
        "reductions": reductions,
        "literals": literals,
        "scaling": scaling,
        "excluded": excluded,
        "n1_shared": n1,
        "n2_distractors": n2,
        "n3_peer_ambiguity": n3,
        "vocabulary": vocab,
        "interpretation": gate,
        "extract_coverage": extract["coverage"],
    }
    dest = OUT / "evaluation.json"
    dest.write_text(json.dumps(report) + "\n")
    (OUT / "evaluation.md").write_text(_render_eval(report, extract) + "\n")
    print(
        f"EVAL {dest} edges={len(primary_edges)} reductions={len(primary_red)} "
        f"gate={gate['gate']}",
        flush=True,
    )
    return report


def _summarize_edge(ev: dict[str, Any]) -> dict[str, Any]:
    cyc = ev["cycle"]
    tmpl = ev["template"]
    return {
        "source": ev.get("source"),
        "cycle_if_added": cyc.get("C3_cycle_if_added"),
        "C1": cyc.get("C1_direct_downstream_conflict"),
        "C2": cyc.get("C2_transitive_downstream_conflict"),
        "path": cyc.get("shortest_T_to_S"),
        "template_strict": tmpl.get("n_strict"),
        "template_vector_sheet": tmpl.get("n_vector_and_sheet"),
        "template_n": tmpl.get("n"),
        "peer_conflict": tmpl.get("peer_conflict"),
        "matches_target_side": ev.get("matches_target_side"),
        "matches_opposite_side": ev.get("matches_opposite_side"),
        "C4": ev.get("C4_source_is_upstream"),
        "C5": ev.get("C5_source_is_downstream"),
        "profile": None
        if not ev.get("profile")
        else {
            "kind": ev["profile"]["kind"],
            "n_dep": ev["profile"]["n_direct_dependents"],
            "n_prec": ev["profile"]["n_direct_precedents"],
            "peer_use": ev["profile"]["peer_use_count"],
            "group": ev["profile"]["in_formula_group"],
        },
        "signature": None
        if not ev.get("signature")
        else {
            "same_sheet": ev["signature"]["same_sheet"],
            "dcol": ev["signature"]["dcol"],
            "drow": ev["signature"]["drow"],
            "source_sheet": ev["signature"]["source_sheet"],
            "enclosing": ev["signature"]["enclosing"],
            "source_kind": ev["signature"]["source_kind"],
        },
    }


def _explain_edge(cat: str, gold_ev: dict[str, Any], model_ev: dict[str, Any]) -> str:
    bits = [cat]
    bits.append(
        f"cycle G={gold_ev['cycle']['C3_cycle_if_added']} M={model_ev['cycle']['C3_cycle_if_added']}"
    )
    if model_ev["cycle"].get("shortest_T_to_S"):
        bits.append(f"pathM={model_ev['cycle']['shortest_T_to_S']}")
    gt = gold_ev["template"]
    mt = model_ev["template"]
    bits.append(
        f"template G strict={gt['n_strict']}/vec={gt['n_vector_and_sheet']} "
        f"M strict={mt['n_strict']}/vec={mt['n_vector_and_sheet']}"
    )
    bits.append(
        f"orient G target={gold_ev.get('matches_target_side')} opp={gold_ev.get('matches_opposite_side')} "
        f"M target={model_ev.get('matches_target_side')} opp={model_ev.get('matches_opposite_side')}"
    )
    return "; ".join(bits)


def _explain_reduction(cat, g_red, m_red, g_rel, m_rel) -> str:
    return (
        f"{cat}; gold {g_red.get('operator')} n={g_red.get('operand_count')} "
        f"contig={g_red.get('contiguous')} vs model {m_red.get('operator')} "
        f"n={m_red.get('operand_count')} contig={m_red.get('contiguous')}; "
        f"R4 G={g_rel.get('R4_peer_reduction_shape_match')} M={m_rel.get('R4_peer_reduction_shape_match')} "
        f"R1 G={g_rel.get('R1_reduces_contiguous_range')} M={m_rel.get('R1_reduces_contiguous_range')} "
        f"R2 G={g_rel.get('R2_reduces_sibling_aggregates')} M={m_rel.get('R2_reduces_sibling_aggregates')}"
    )


def _n1_row(cell_id, shared, view, target, peers_pack, orient, parsed) -> dict[str, Any]:
    ref = shared["ref"]
    slot = _slot_for_ref(parsed, ref)
    ev = _edge_bundle(view, target, ref, slot, peers_pack, orient)
    return {
        "cell_id": cell_id,
        "source": _src_id(ref),
        "cycle_if_added": ev["cycle"]["C3_cycle_if_added"],
        "template_clear": _template_clear(ev["template"]),
        "C5": ev.get("C5_source_is_downstream"),
    }


def _scaling_row(cell_id, klass, pred, gold, m_parsed, g_parsed, peers_pack) -> dict[str, Any]:
    peer_shapes = [
        (peer.get("parsed") or {}).get("shape") for peer in peers_pack["formula_peers"]
    ]
    peer_shapes = [s for s in peer_shapes if s]
    m_shape = m_parsed.get("shape")
    g_shape = g_parsed.get("shape")
    return {
        "target": cell_id,
        "class": klass,
        "model_formula": pred,
        "golden_formula": gold,
        "model_skeleton": m_shape,
        "golden_skeleton": g_shape,
        "peer_skeletons": peer_shapes[:8],
        "gold_matches_peer_skeleton": g_shape in peer_shapes if g_shape else False,
        "model_matches_peer_skeleton": m_shape in peer_shapes if m_shape else False,
        "model_has_const_scale": bool(m_parsed.get("literals"))
        and any(lit not in _TRIVIAL_LITS for lit in m_parsed.get("literals") or []),
        "gold_has_const_scale": bool(g_parsed.get("literals"))
        and any(lit not in _TRIVIAL_LITS for lit in g_parsed.get("literals") or []),
    }


def _distractor(view: OperationalView, gold_ref: dict[str, Any], target: tuple[str, int, int]):
    gsheet, gc, gr = gold_ref["sheet"], gold_ref["c1"], gold_ref["r1"]
    for offset in range(1, 9):
        for other in (gr - offset, gr + offset):
            if other < 1:
                continue
            key = (gsheet, gc, other)
            if key == (target[0], gc, other) and gsheet == target[0]:
                continue
            if key in view.graph.formulas or view.graph.kind(key) == "V":
                return key
    return None


def _vocab_verdict(edges, reductions, extract) -> dict[str, str]:
    n_cycle = sum(1 for e in edges if e["model"]["cycle_if_added"] != e["gold"]["cycle_if_added"])
    n_tmpl = sum(
        1
        for e in edges
        if e["gold"]["template_vector_sheet"] != e["model"]["template_vector_sheet"]
    )
    n_orient = sum(
        1
        for e in edges
        if e["gold"]["matches_target_side"] != e["model"]["matches_target_side"]
    )
    n_red = sum(1 for r in reductions if r["category"] == "CLEAR_REDUCTION_GOLD")
    n_peer = extract["coverage"]["n_with_any_peer"]
    return {
        "DATA_DEPENDENCE": "useful",
        "USE_DEF_SLOT": "useful" if n_tmpl else "weak",
        "TRANSITIVE_DEPENDENCE": "useful" if n_cycle else "weak",
        "DEPENDENCE_CYCLE_IF_ADDED": "useful" if n_cycle else "weak",
        "DEPENDENCE_TEMPLATE": "useful" if n_tmpl else "weak",
        "DEPENDENCE_ORIENTATION": "useful" if n_orient else "unobservable",
        "DIRECTION_CHANGE_POINT": "useful"
        if extract["coverage"]["n_orientation_change"]
        else "unobservable",
        "REDUCTION": "useful" if n_red else "weak",
        "FORMULA_GROUP": "weak",
        "REFERENCE_VECTOR": "useful" if n_tmpl else "weak",
        "peer_recovery": "useful" if n_peer else "unobservable",
    }


def _interpret(edge_counts, red_counts, edges, reductions, explained) -> dict[str, Any]:
    n_e = len(edges)
    n_r = len(reductions)
    clear_e = edge_counts["CLEAR_OPERATIONAL_GOLD"]
    clear_r = red_counts["CLEAR_REDUCTION_GOLD"]
    mixed = edge_counts["MIXED"] + red_counts["MIXED_REDUCTION"]
    missing = (
        edge_counts["TIE"]
        + edge_counts["OPERATIONAL_MISSING"]
        + red_counts["TIE_REDUCTION"]
        + red_counts["REDUCTION_STRUCTURE_MISSING"]
    )
    model_fav = edge_counts["MODEL_FAVORED"] + red_counts["MODEL_REDUCTION_FAVORED"]
    schema_tie_to_clear = 0
    for e in edges:
        if e.get("schema_category") in {"TIE", "SCHEMA_MISSING", "MODEL_FAVORED"} and e[
            "category"
        ] == "CLEAR_OPERATIONAL_GOLD":
            schema_tie_to_clear += 1
    for r in reductions:
        if r["category"] == "CLEAR_REDUCTION_GOLD" and any(
            c in {"TIE", "SCHEMA_MISSING", "MODEL_FAVORED"} for c in r.get("schema_categories") or []
        ):
            schema_tie_to_clear += 1
    classes_clear = {e["class"] for e in edges if e["category"] == "CLEAR_OPERATIONAL_GOLD"} | {
        r["class"] for r in reductions if r["category"] == "CLEAR_REDUCTION_GOLD"
    }
    if n_e and clear_e >= max(2, n_e // 3) and model_fav <= 1 and len(classes_clear) >= 2:
        gate = "STRONG POSITIVE"
        conclusion = (
            "Operational dependence roles contain decision-relevant information not "
            "captured by raw topology or descriptive schema."
        )
        nxt = "broader operational-relational census; not semantic relation names"
    elif (clear_e + clear_r + mixed) >= 1 and missing < (n_e + n_r or 1):
        gate = "PARTIAL / HETEROGENEOUS"
        conclusion = (
            "Operational semantics are represented by several typed mechanical "
            "relations, not one universal edge role."
        )
        nxt = "typed follow-up on the relations that actually split; do not add PRODUCES"
    else:
        gate = "WEAK"
        conclusion = (
            "Mechanical dataflow-role structure does not explain the known ORACLE "
            "precedent failures beyond isolated cases."
        )
        nxt = "stop; do not rescue with semantic labels"
    return {
        "gate": gate,
        "conclusion": conclusion,
        "next": nxt,
        "schema_tie_to_operational_clear": schema_tie_to_clear,
        "classes_with_clear": sorted(classes_clear),
        "explained_targets": sorted(explained),
        "model_favored": model_fav,
    }


def _render_extract(payload: dict[str, Any]) -> str:
    c = payload["coverage"]
    lines = [
        "# Operational substrate (gold-blind)",
        "",
        f"Runtime {payload['runtime_s']['all']}s. Direction: {payload['direction_convention']}",
        "",
        f"ORACLE cells {c['n_oracle']}: P1 {c['n_with_p1']}, P2 {c['n_with_p2']}, "
        f"P3 {c['n_with_p3']}, any peer {c['n_with_any_peer']}, dependents "
        f"{c['n_with_dependents']}, orientation-change {c['n_orientation_change']}.",
        "",
        "## Workbook graph coverage",
        "",
        "| task | supported | point edges | range edges | classes | runtime s |",
        "|------|----------:|------------:|------------:|--------:|----------:|",
    ]
    for tid, task in payload["tasks"].items():
        g = task["graph"]
        lines.append(
            f"| {tid} | {g.get('supported')} | {g.get('point_edges')} | {g.get('range_edges')} "
            f"| {g.get('equivalence_classes')} | {payload['runtime_s'].get(tid)} |"
        )
    lines += ["", "## ORACLE peers", ""]
    for cell_id, rec in payload["oracle_cells"].items():
        p = rec["peers"]
        o3 = any(rec["orientation"][f"w{w}"]["O3_change"] for w in LEFT_RIGHT_WINDOWS)
        lines.append(
            f"- `{cell_id}` [{rec['class']}] P1={p['n_p1']} P2={p['n_p2']} P3={p['n_p3']} "
            f"deps={rec['n_direct_dependents']} O3={o3} "
            f"L={None if not p['P1_left'] else p['P1_left']['formula']} "
            f"R={None if not p['P1_right'] else p['P1_right']['formula']}"
        )
    return "\n".join(lines)


def _render_eval(report: dict[str, Any], extract: dict[str, Any]) -> str:
    lines = [
        "# Operational dependence discrimination",
        "",
        f"Primary EDGE_CHOICE n={report['n_primary_edge']} counts={report['edge_counts']}",
        f"Primary REDUCTION_CHOICE n={report['n_primary_reduction']} counts={report['reduction_counts']}",
        f"CLEAR_OPERATIONAL_GOLD rate={_pct(report['clear_operational_gold_rate'])}",
        f"CLEAR_REDUCTION_GOLD rate={_pct(report['clear_reduction_gold_rate'])}",
        f"Targets with a clear operational explanation: {report['n_oracle_targets_clearly_explained']}",
        "",
        f"**{report['interpretation']['gate']}**",
        "",
        report["interpretation"]["conclusion"],
        "",
        "## EDGE_CHOICE",
        "",
    ]
    for e in report["edges"]:
        lines.append(
            f"- `{e['target']}` [{e['class']}/{e['population']}] {e['category']} "
            f"schema={e.get('schema_category')} M={e['model_source']} G={e['golden_source']} | {e['explanation']}"
        )
    lines += ["", "## REDUCTION_CHOICE", ""]
    for r in report["reductions"]:
        lines.append(
            f"- `{r['target']}` [{r['class']}] {r['category']} | {r['explanation']}"
        )
    lines += ["", "## LITERAL / SCALING", ""]
    for item in report["literals"]:
        lines.append(
            f"- LITERAL `{item['target']}` gold_ref_role={item['V4_gold_matches_peer_ref_role']} "
            f"model_lit_role={item['V4_model_matches_peer_literal_role']} "
            f"M={item['model_facts']['skeleton']} G={item['golden_facts']['skeleton']}"
        )
    for item in report["scaling"]:
        lines.append(
            f"- SCALING `{item['target']}` gold_peer={item['gold_matches_peer_skeleton']} "
            f"model_peer={item['model_matches_peer_skeleton']} "
            f"M={item['model_skeleton']} G={item['golden_skeleton']}"
        )
    lines += ["", "## Schema × operational", "", str(report["schema_x_operational"])]
    lines += ["", "## Vocabulary", ""]
    for name, verdict in report["vocabulary"].items():
        lines.append(f"- {name}: {verdict}")
    lines += ["", "## Negative controls", ""]
    lines.append(f"N1 shared slots: {len(report['n1_shared'])}")
    n1_cycle = sum(1 for x in report["n1_shared"] if x["cycle_if_added"])
    lines.append(f"N1 with cycle_if_added (should be rare): {n1_cycle}")
    lines.append("N2 distractors: " + str(Counter(x["category"] for x in report["n2_distractors"])))
    lines.append(f"N3 peer-ambiguous pairs: {len(report['n3_peer_ambiguity'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("extract", "evaluate", "all"), nargs="?", default="all")
    args = parser.parse_args()
    extract = None
    views = None
    if args.phase in ("extract", "all"):
        extract, views = cmd_extract()
    if args.phase in ("evaluate", "all"):
        if extract is None:
            extract = json.loads((OUT / "operational_extract.json").read_text())
        cmd_evaluate(extract, views)


if __name__ == "__main__":
    main()
