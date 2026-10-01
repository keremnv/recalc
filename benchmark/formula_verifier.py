"""Gold-blind formula candidate verifier.

verify_formula(input workbook facts, target, candidate) → PASS / REJECT / ABSTAIN
per frozen checker. Never sees golden formulas. Absence of a violation is not
automatically PASS: if a checker is inapplicable it ABSTAINS.

DATA_DEPENDENCE(S, C) = S → C (precedent → dependent).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from formula_operational import (
    CellKey,
    OperationalView,
    _cell_id,
    collect_peers,
    cycle_if_added,
    parse_use_def_slots,
    reduction_of,
    reduction_relations,
)
from librecalc_mcp.domain.formulas import formula_a1_shape
from xlsx_metadata_repair import install

install()
import openpyxl  # noqa: E402

K_THRESHOLDS = (3, 5)
HARD_IDS = ("A1", "A2", "A3", "A4", "A5")
_TRIVIAL_LITS = {0, 1}
_SHEET_PREFIX = re.compile(r"\$?'(?:[^']|'')+'!|\$?[A-Za-z_][A-Za-z0-9_]*!")
_HASH_REF = re.compile(r"#REF!", re.I)

DEFINITIONS = {
    "golden_in_generation": False,
    "REJECT": "A frozen checker establishes a violation of its property.",
    "PASS": "The checker is applicable and the candidate satisfies the property.",
    "ABSTAIN": "Insufficient mechanically recoverable evidence. Not a pass.",
    "HARD": "A1–A5 graph/reference constraints, subject to circular-workbook caveat.",
    "EMPIRICAL_EXACT": (
        "B/C/D exact unanimous peer contracts. Not logical invariants. "
        "Primary support is unanimous k>=3 and k>=5 independently; no majority."
    ),
    "A_STRICT": (
        "Reject a new cycle only if the input graph is acyclic or the candidate "
        "creates a new SCC not already present."
    ),
    "A_LENIENT": "If the input already has circularity, reject only self/direct 2-cycles.",
    "D2_sum_vs_plus": (
        "SUM(range) vs explicit + of the same contiguous cells is not a rejection. "
        "ABSTAIN for that syntactic pair."
    ),
    "not_used": (
        "Goldens, LLMs, learned scores, semantic ontology, and automatic repair "
        "are not used at verification time."
    ),
}


def operator_skeleton(formula: str | None) -> str | None:
    if not formula:
        return None
    shaped = formula_a1_shape(formula)
    return _SHEET_PREFIX.sub("", shaped)


def candidate_kind(formula: str | None) -> str:
    if not formula:
        return "EMPTY"
    parsed = parse_use_def_slots(formula, "S", 1, 1)
    red = reduction_of(formula, parsed)
    if red["is_reduction"]:
        return "REDUCTION_CANDIDATE"
    lits = [lit for lit in parsed["literals"] if lit not in _TRIVIAL_LITS]
    if lits and parsed["slots"]:
        return "LITERAL_REFERENCE_CANDIDATE"
    skel = operator_skeleton(formula) or ""
    if parsed["slots"] and ("/" in skel or re.search(r"(?i)\bIF\s*\(", formula)):
        return "OPERATOR_SKELETON_CANDIDATE"
    if parsed["slots"]:
        return "EDGE_CANDIDATE"
    return "OTHER_SUPPORTED_FORMULA"


def _result(
    checker_id: str,
    family: str,
    checker_type: str,
    verdict: str,
    *,
    support_count: int = 0,
    support_addresses: list[str] | None = None,
    reason: str = "",
    provenance: dict[str, Any] | None = None,
    k: int | None = None,
) -> dict[str, Any]:
    applicable = verdict != "ABSTAIN"
    cid = checker_id if k is None else f"{checker_id}_k{k}"
    return {
        "checker_id": cid,
        "checker_family": family,
        "checker_type": checker_type,
        "k": k,
        "applicable": applicable,
        "verdict": verdict,
        "support_count": support_count,
        "support_addresses": support_addresses or [],
        "reason": reason,
        "provenance": provenance or {},
    }


def circular_workbook_meta(path: Path) -> dict[str, Any]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=True)
    try:
        calc = getattr(workbook, "calculation", None)
        iterate = getattr(calc, "iterate", None) if calc is not None else None
        iterate_count = getattr(calc, "iterateCount", None) if calc is not None else None
        iterate_delta = getattr(calc, "iterateDelta", None) if calc is not None else None
        calc_mode = getattr(calc, "calcMode", None) if calc is not None else None
        return {
            "iterate": bool(iterate) if iterate is not None else None,
            "iterateCount": iterate_count,
            "iterateDelta": iterate_delta,
            "calcMode": calc_mode,
        }
    finally:
        workbook.close()


def scc_stats(view: OperationalView) -> dict[str, Any]:
    graph = view.dependents
    nodes: set[CellKey] = set(view.graph.formulas)
    nodes.update(graph)
    for dests in graph.values():
        nodes.update(dests)
    index = 0
    stack: list[CellKey] = []
    onstack: set[CellKey] = set()
    indices: dict[CellKey, int] = {}
    lowlink: dict[CellKey, int] = {}
    comps: list[list[CellKey]] = []
    # Iterative Tarjan: frame = (node, neighbor_iter, started)
    for start in nodes:
        if start in indices:
            continue
        frame_stack: list[tuple[CellKey, Any, bool]] = [(start, iter(graph.get(start, ())), False)]
        while frame_stack:
            node, niter, started = frame_stack[-1]
            if not started:
                indices[node] = index
                lowlink[node] = index
                index += 1
                stack.append(node)
                onstack.add(node)
                frame_stack[-1] = (node, niter, True)
            try:
                nxt = next(niter)
            except StopIteration:
                frame_stack.pop()
                if lowlink[node] == indices[node]:
                    comp = []
                    while True:
                        w = stack.pop()
                        onstack.remove(w)
                        comp.append(w)
                        if w == node:
                            break
                    comps.append(comp)
                if frame_stack:
                    parent, _piter, _ps = frame_stack[-1]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
                continue
            if nxt not in nodes:
                continue
            if nxt not in indices:
                frame_stack.append((nxt, iter(graph.get(nxt, ())), False))
            elif nxt in onstack:
                lowlink[node] = min(lowlink[node], indices[nxt])
    nontrivial = [comp for comp in comps if len(comp) >= 2]
    self_loops = [node for node in nodes if node in graph.get(node, ())]
    return {
        "n_nodes": len(nodes),
        "n_scc": len(comps),
        "n_nontrivial_scc": len(nontrivial) + len(self_loops),
        "acyclic": len(nontrivial) == 0 and not self_loops,
        "nontrivial_sample": [[_cell_id(k) for k in comp[:6]] for comp in nontrivial[:5]],
        "self_loop_n": len(self_loops),
    }


def _sources(parsed: dict[str, Any], target: CellKey) -> list[CellKey]:
    out = []
    seen: set[CellKey] = set()
    for slot in parsed["slots"]:
        key = (slot["sheet"], slot["c1"], slot["r1"])
        if key not in seen:
            seen.add(key)
            out.append(key)
        if slot["is_range"]:
            key2 = (slot["sheet"], slot["c2"], slot["r2"])
            if key2 not in seen:
                seen.add(key2)
                out.append(key2)
    return out


def _slot_contains_target(slot: dict[str, Any], target: CellKey) -> bool:
    sheet, col, row = target
    return (
        slot["sheet"] == sheet
        and slot["c1"] <= col <= slot["c2"]
        and slot["r1"] <= row <= slot["r2"]
    )


def check_family_a(
    view: OperationalView,
    target: CellKey,
    parsed: dict[str, Any],
    sccs: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    sources = _sources(parsed, target)
    self_hit = any(_slot_contains_target(slot, target) for slot in parsed["slots"])
    rows.append(
        _result(
            "A1",
            "A",
            "HARD",
            "REJECT" if self_hit else ("PASS" if parsed["slots"] else "ABSTAIN"),
            support_count=int(self_hit),
            support_addresses=[_cell_id(target)] if self_hit else [],
            reason="SELF_REFERENCE_IF_ADDED" if self_hit else "no_self_reference",
        )
    )
    cycles = []
    for source in sources:
        if source == target:
            continue
        cycles.append((source, cycle_if_added(view, source, target)))
    direct = [(_cell_id(s), c) for s, c in cycles if c["C1_direct_downstream_conflict"]]
    trans = [(_cell_id(s), c) for s, c in cycles if c["C2_transitive_downstream_conflict"]]
    any_cycle = [(_cell_id(s), c) for s, c in cycles if c["C3_cycle_if_added"]]
    acyclic = bool(sccs.get("acyclic"))
    if not sources:
        a2 = a3 = a4 = "ABSTAIN"
        reason2 = reason3 = reason4 = "no_sources"
    else:
        if direct:
            a2 = "REJECT"
            reason2 = "DIRECT_CYCLE_IF_ADDED"
        else:
            a2 = "PASS"
            reason2 = "no_direct_cycle"
        if trans:
            a3 = "REJECT"
            reason3 = "TRANSITIVE_CYCLE_IF_ADDED"
        else:
            a3 = "PASS"
            reason3 = "no_transitive_cycle"
        if any_cycle:
            a4 = "REJECT"
            reason4 = "SCC_EXPANSION_IF_ADDED"
        else:
            a4 = "PASS"
            reason4 = "no_new_scc"
        if not acyclic:
            if a3 == "REJECT" and not direct:
                a3 = "ABSTAIN"
                reason3 = "existing_circularity_lenient"
            if a4 == "REJECT" and not direct:
                a4 = "ABSTAIN"
                reason4 = "existing_circularity_lenient"
    rows.append(
        _result(
            "A2",
            "A",
            "HARD",
            a2,
            support_count=len(direct),
            support_addresses=[addr for addr, _c in direct],
            reason=reason2,
            provenance={
                "policy_primary": "A_STRICT" if acyclic else "A_LENIENT_CONTEXT",
                "input_acyclic": acyclic,
                "paths": [c["shortest_T_to_S"] for _s, c in cycles if c["C3_cycle_if_added"]],
            },
        )
    )
    rows.append(
        _result(
            "A3",
            "A",
            "HARD",
            a3,
            support_count=len(trans),
            support_addresses=[addr for addr, _c in trans],
            reason=reason3,
            provenance={"input_acyclic": acyclic},
        )
    )
    rows.append(
        _result(
            "A4",
            "A",
            "HARD",
            a4,
            support_count=len(any_cycle),
            support_addresses=[addr for addr, _c in any_cycle],
            reason=reason4,
            provenance={
                "input_acyclic": acyclic,
                "n_nontrivial_scc": sccs.get("n_nontrivial_scc"),
            },
        )
    )
    invalid = []
    known = set(view.graph.occupancy)
    if parsed.get("opaque") and not parsed["slots"]:
        rows.append(
            _result(
                "A5",
                "A",
                "HARD",
                "ABSTAIN",
                reason="unsupported_opaque_formula",
                provenance={"opaque_reason": parsed.get("opaque_reason")},
            )
        )
        return rows
    for slot in parsed["slots"]:
        if slot["sheet"] not in known:
            invalid.append(f"unknown_sheet:{slot['sheet']}!{slot['start']}")
        if slot["c1"] < 1 or slot["r1"] < 1:
            invalid.append(f"invalid_address:{slot['start']}")
    if not parsed.get("parser_ok", True):
        invalid.append("parser_failure")
    raw = parsed.get("shape") or ""
    if _HASH_REF.search(raw):
        invalid.append("#REF!")
    rows.append(
        _result(
            "A5",
            "A",
            "HARD",
            "REJECT" if invalid else "PASS",
            support_count=len(invalid),
            support_addresses=invalid,
            reason="INVALID_REFERENCE" if invalid else "refs_ok",
        )
    )
    return rows


def _peer_features(peer: dict[str, Any]) -> list[dict[str, Any]]:
    slots = (peer.get("parsed") or {}).get("slots") or []
    out = []
    for slot in slots:
        abs_mask = slot.get("abs_mask") or ""
        out.append(
            {
                "vector": (slot["dcol"], slot["drow"]),
                "sheet": "SAME_SHEET" if not slot["cross_sheet"] else slot["sheet"],
                "kind": "range" if slot["is_range"] else "point",
                "abs_mask": abs_mask,
                "abs_key": (
                    (slot["sheet"], slot["start"], abs_mask)
                    if "$" in abs_mask
                    else None
                ),
                "enclosing": slot.get("enclosing") or {},
                "range_off": (
                    slot["drow"],
                    slot["drow"] + (slot["r2"] - slot["r1"]),
                    slot["dcol"],
                    slot["dcol"] + (slot["c2"] - slot["c1"]),
                ),
                "source": (slot["sheet"], slot["c1"], slot["r1"]),
            }
        )
    return out


def _unanimous(values: list[Any]) -> Any | None:
    if not values:
        return None
    first = values[0]
    if all(item == first for item in values[1:]):
        return first
    return None


def _cand_features(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    fake_peer = {"parsed": parsed}
    return _peer_features(fake_peer)


def check_family_b(
    view: OperationalView,
    target: CellKey,
    parsed: dict[str, Any],
    peers: list[dict[str, Any]],
    k: int,
) -> list[dict[str, Any]]:
    addrs = [p["address"] for p in peers]
    n = len(peers)
    if n < k:
        return [
            _result(
                cid,
                "B",
                "EMPIRICAL_EXACT",
                "ABSTAIN",
                support_count=n,
                support_addresses=addrs,
                reason="insufficient_peers",
                k=k,
            )
            for cid in ("B1", "B2", "B3", "B4", "B5")
        ]
    peer_feats = [_peer_features(p) for p in peers]
    cand = _cand_features(parsed)
    # B1: unanimous absolute key among peers (any slot); candidate must include it.
    peer_abs = []
    for feats in peer_feats:
        keys = tuple(sorted(f["abs_key"] for f in feats if f["abs_key"]))
        peer_abs.append(keys)
    contract_abs = _unanimous(peer_abs)
    if not contract_abs or contract_abs == ():
        b1 = _result(
            "B1",
            "B",
            "EMPIRICAL_EXACT",
            "ABSTAIN",
            support_count=n,
            support_addresses=addrs,
            reason="no_unanimous_absolute_ref",
            k=k,
        )
    else:
        cand_abs = {f["abs_key"] for f in cand if f["abs_key"]}
        ok = set(contract_abs) <= cand_abs
        b1 = _result(
            "B1",
            "B",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="ABSOLUTE_REFERENCE_CONTRACT" if not ok else "matches_abs_contract",
            provenance={"contract": [list(x) for x in contract_abs], "candidate": [list(x) for x in cand_abs if x]},
            k=k,
        )
    def slot_prop(name: str) -> list[Any]:
        vals = []
        for feats in peer_feats:
            vals.append(tuple(f[name] for f in feats))
        return vals

    def compare_tuple(cid: str, prop: str, reason: str) -> dict[str, Any]:
        contract = _unanimous(slot_prop(prop))
        if contract is None:
            return _result(
                cid,
                "B",
                "EMPIRICAL_EXACT",
                "ABSTAIN",
                support_count=n,
                support_addresses=addrs,
                reason="peers_not_unanimous",
                k=k,
            )
        cand_t = tuple(f[prop] for f in cand)
        if len(cand_t) != len(contract):
            return _result(
                cid,
                "B",
                "EMPIRICAL_EXACT",
                "ABSTAIN",
                support_count=n,
                support_addresses=addrs,
                reason="slot_count_mismatch",
                provenance={"peer_n": len(contract), "cand_n": len(cand_t)},
                k=k,
            )
        ok = cand_t == contract
        return _result(
            cid,
            "B",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason=reason if not ok else f"matches_{cid}",
            provenance={"contract": list(contract), "candidate": list(cand_t)},
            k=k,
        )

    b2 = compare_tuple("B2", "vector", "REFERENCE_VECTOR_CONTRACT")
    b3 = compare_tuple("B3", "sheet", "SOURCE_SHEET_CONTRACT")
    b4 = compare_tuple("B4", "kind", "POINT_RANGE_KIND_CONTRACT")
    kinds = []
    for feats in peer_feats:
        ks = []
        for f in feats:
            src = f["source"]
            ks.append(view.kind(src))
        kinds.append(tuple(ks))
    contract_k = _unanimous(kinds)
    if contract_k is None:
        b5 = _result(
            "B5",
            "B",
            "EMPIRICAL_EXACT",
            "ABSTAIN",
            support_count=n,
            support_addresses=addrs,
            reason="peers_not_unanimous",
            k=k,
        )
    else:
        cand_k = tuple(view.kind(f["source"]) for f in cand)
        if len(cand_k) != len(contract_k):
            b5 = _result(
                "B5",
                "B",
                "EMPIRICAL_EXACT",
                "ABSTAIN",
                support_count=n,
                support_addresses=addrs,
                reason="slot_count_mismatch",
                k=k,
            )
        else:
            ok = cand_k == contract_k
            b5 = _result(
                "B5",
                "B",
                "EMPIRICAL_EXACT",
                "PASS" if ok else "REJECT",
                support_count=n,
                support_addresses=addrs,
                reason="FORMULA_CLASS_SOURCE_CONTRACT" if not ok else "matches_source_kind",
                k=k,
            )
    return [b1, b2, b3, b4, b5]


def check_family_c(
    parsed: dict[str, Any],
    formula: str | None,
    peers: list[dict[str, Any]],
    k: int,
) -> list[dict[str, Any]]:
    addrs = [p["address"] for p in peers]
    n = len(peers)
    if n < k:
        return [
            _result(cid, "C", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="insufficient_peers", k=k)
            for cid in ("C1", "C2", "C3")
        ]
    skels = [operator_skeleton(p.get("formula")) for p in peers]
    contract = _unanimous(skels)
    cand_skel = operator_skeleton(formula)
    if contract is None:
        c1 = _result("C1", "C", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peers_not_unanimous", k=k)
    else:
        ok = cand_skel == contract
        c1 = _result(
            "C1",
            "C",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="OPERATOR_SKELETON_CONTRACT" if not ok else "matches_skeleton",
            provenance={"contract": contract, "candidate": cand_skel},
            k=k,
        )
    # C2: slot-specific literal vs reference. Align by slot index when counts match.
    # Identify peer slots that are references; if candidate has a nontrivial literal
    # where peers have a reference at the same skeleton <REF> index, REJECT.
    peer_feats = [_peer_features(p) for p in peers]
    n_slots = [len(f) for f in peer_feats]
    slot_n = _unanimous(n_slots)
    cand = _cand_features(parsed)
    cand_lits = [lit for lit in parsed.get("literals") or [] if lit not in _TRIVIAL_LITS]
    if slot_n is None:
        c2 = _result("C2", "C", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peer_slot_count_not_unanimous", k=k)
    elif len(cand) == slot_n:
        # same ref count: PASS if no substitution. Inverse: peers have lits in skeleton
        peer_lits = []
        for p in peers:
            red = p.get("reduction") or {}
            peer_lits.append(tuple(x for x in (red.get("literals") or []) if x not in _TRIVIAL_LITS))
        lit_contract = _unanimous(peer_lits)
        cand_nt = tuple(cand_lits)
        if lit_contract is None:
            c2 = _result("C2", "C", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peer_literals_not_unanimous", k=k)
        elif cand_nt != lit_contract:
            # only reject if one side has a ref-like extra and the other a literal
            c2 = _result(
                "C2",
                "C",
                "EMPIRICAL_EXACT",
                "REJECT",
                support_count=n,
                support_addresses=addrs,
                reason="LITERAL_VS_REFERENCE_CONTRACT",
                provenance={"peer_lits": list(lit_contract), "candidate_lits": list(cand_nt)},
                k=k,
            )
        else:
            c2 = _result("C2", "C", "EMPIRICAL_EXACT", "PASS", support_count=n, support_addresses=addrs, reason="literal_pattern_matches", k=k)
    elif len(cand) < slot_n and cand_lits:
        # fewer refs + extra literal: likely literal substituted for a ref
        c2 = _result(
            "C2",
            "C",
            "EMPIRICAL_EXACT",
            "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="LITERAL_VS_REFERENCE_CONTRACT",
            provenance={"peer_slots": slot_n, "cand_slots": len(cand), "cand_lits": cand_lits},
            k=k,
        )
    elif len(cand) > slot_n and not cand_lits:
        c2 = _result(
            "C2",
            "C",
            "EMPIRICAL_EXACT",
            "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="LITERAL_VS_REFERENCE_CONTRACT",
            provenance={"direction": "literal_to_reference"},
            k=k,
        )
    else:
        c2 = _result("C2", "C", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="cannot_align_literal_slot", k=k)
    peer_abs = []
    for feats in peer_feats:
        keys = tuple(sorted(f["abs_key"] for f in feats if f["abs_key"]))
        peer_abs.append(keys)
    abs_contract = _unanimous(peer_abs)
    if not abs_contract or abs_contract == ():
        c3 = _result("C3", "C", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="no_unanimous_abs_slot", k=k)
    else:
        cand_abs = tuple(sorted(f["abs_key"] for f in cand if f["abs_key"]))
        ok = cand_abs == abs_contract
        c3 = _result(
            "C3",
            "C",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="ABSOLUTE_REFERENCE_SLOT_CONTRACT" if not ok else "matches_abs_slot",
            provenance={"contract": [list(x) for x in abs_contract]},
            k=k,
        )
    return [c1, c2, c3]


def check_family_d(
    view: OperationalView,
    parsed: dict[str, Any],
    formula: str | None,
    peers: list[dict[str, Any]],
    k: int,
) -> list[dict[str, Any]]:
    addrs = [p["address"] for p in peers]
    n = len(peers)
    red_peers = [p for p in peers if (p.get("reduction") or {}).get("is_reduction")]
    if len(red_peers) < k:
        return [
            _result(cid, "D", "EMPIRICAL_EXACT", "ABSTAIN", support_count=len(red_peers), support_addresses=[p["address"] for p in red_peers], reason="insufficient_reduction_peers", k=k)
            for cid in ("D1", "D2", "D3", "D4")
        ]
    use = red_peers[: ]  # all reduction peers; still require n>=k of them
    if len(use) < k:
        use = red_peers
    addrs = [p["address"] for p in use]
    n = len(use)
    cand_red = reduction_of(formula, parsed)
    peer_reds = [p.get("reduction") or {} for p in use]
    extents = []
    bounds = []
    for p in use:
        feats = _peer_features(p)
        range_feats = [f for f in feats if f["kind"] == "range"]
        if len(range_feats) == 1:
            extents.append(range_feats[0]["range_off"])
            bounds.append((range_feats[0]["range_off"][0], range_feats[0]["range_off"][1]))
        else:
            red = p.get("reduction") or {}
            extents.append(("points", red.get("row_span"), red.get("col_span"), red.get("operand_count")))
            bounds.append(("points", red.get("row_span")))
    ext_c = _unanimous(extents)
    cand_feats = _cand_features(parsed)
    cand_range = [f for f in cand_feats if f["kind"] == "range"]
    if cand_range:
        cand_ext = cand_range[0]["range_off"]
        cand_bound = (cand_ext[0], cand_ext[1])
    else:
        cand_ext = ("points", cand_red.get("row_span"), cand_red.get("col_span"), cand_red.get("operand_count"))
        cand_bound = ("points", cand_red.get("row_span"))
    if ext_c is None:
        d1 = _result("D1", "D", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peers_not_unanimous", k=k)
    else:
        ok = cand_ext == ext_c
        d1 = _result(
            "D1",
            "D",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="REDUCTION_RANGE_EXTENT_CONTRACT" if not ok else "matches_extent",
            provenance={"contract": list(ext_c) if isinstance(ext_c, tuple) else ext_c, "candidate": cand_ext},
            k=k,
        )
    ops = [r.get("operator") for r in peer_reds]
    op_c = _unanimous(ops)
    cand_op = cand_red.get("operator")
    if op_c is None:
        d2 = _result("D2", "D", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peers_not_unanimous", k=k)
    elif {op_c, cand_op} <= {"SUM", "explicit_+"} and op_c != cand_op:
        d2 = _result(
            "D2",
            "D",
            "EMPIRICAL_EXACT",
            "ABSTAIN",
            support_count=n,
            support_addresses=addrs,
            reason="sum_vs_explicit_plus_equivalent_syntax",
            provenance={"peer_op": op_c, "candidate_op": cand_op},
            k=k,
        )
    elif cand_op == op_c:
        d2 = _result("D2", "D", "EMPIRICAL_EXACT", "PASS", support_count=n, support_addresses=addrs, reason="matches_reduction_op", k=k)
    else:
        d2 = _result(
            "D2",
            "D",
            "EMPIRICAL_EXACT",
            "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="REDUCTION_OPERATOR_CONTRACT",
            provenance={"peer_op": op_c, "candidate_op": cand_op},
            k=k,
        )
    nest = []
    for p in use:
        rel = reduction_relations(p.get("reduction") or {}, [], view, (p.get("parsed") or {}).get("slots") or [])
        nest.append((rel.get("R3_reduces_leaf_like"), rel.get("R2_reduces_sibling_aggregates")))
    nest_c = _unanimous(nest)
    cand_rel = reduction_relations(cand_red, peer_reds, view, parsed["slots"])
    cand_nest = (cand_rel.get("R3_reduces_leaf_like"), cand_rel.get("R2_reduces_sibling_aggregates"))
    if nest_c is None:
        d3 = _result("D3", "D", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peers_not_unanimous", k=k)
    else:
        ok = cand_nest == nest_c
        d3 = _result(
            "D3",
            "D",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="REDUCTION_NESTING_CONTRACT" if not ok else "matches_nesting",
            k=k,
        )
    bound_c = _unanimous(bounds)
    if bound_c is None:
        d4 = _result("D4", "D", "EMPIRICAL_EXACT", "ABSTAIN", support_count=n, support_addresses=addrs, reason="peers_not_unanimous", k=k)
    else:
        ok = cand_bound == bound_c
        d4 = _result(
            "D4",
            "D",
            "EMPIRICAL_EXACT",
            "PASS" if ok else "REJECT",
            support_count=n,
            support_addresses=addrs,
            reason="REDUCTION_BOUNDARY_CONTRACT" if not ok else "matches_boundary",
            provenance={"contract": bound_c, "candidate": cand_bound},
            k=k,
        )
    return [d1, d2, d3, d4]


def apply_policy(results: list[dict[str, Any]], name: str) -> dict[str, Any]:
    if name == "H":
        chosen = [r for r in results if r["checker_id"] in HARD_IDS]
    elif name == "HE3":
        chosen = [
            r
            for r in results
            if r["checker_id"] in HARD_IDS or (r.get("k") == 3 and r["checker_type"] == "EMPIRICAL_EXACT")
        ]
    elif name == "HE5":
        chosen = [
            r
            for r in results
            if r["checker_id"] in HARD_IDS or (r.get("k") == 5 and r["checker_type"] == "EMPIRICAL_EXACT")
        ]
    else:
        raise ValueError(name)
    rejects = [r for r in chosen if r["verdict"] == "REJECT"]
    passes = [r for r in chosen if r["verdict"] == "PASS"]
    if rejects:
        verdict = "REJECT"
    elif passes:
        verdict = "PASS"
    else:
        verdict = "ABSTAIN"
    return {
        "policy": name,
        "verdict": verdict,
        "reject_ids": [r["checker_id"] for r in rejects],
        "pass_ids": [r["checker_id"] for r in passes],
    }


def verify_formula(
    view: OperationalView,
    target: CellKey,
    candidate_formula: str | None,
    *,
    sccs: dict[str, Any] | None = None,
    peers_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gold-blind. Returns atomic checker rows and policy verdicts."""
    if not candidate_formula or not isinstance(candidate_formula, str):
        return {
            "results": [],
            "policies": [
                {"policy": p, "verdict": "ABSTAIN", "reject_ids": [], "pass_ids": []}
                for p in ("H", "HE3", "HE5")
            ],
            "kind": "EMPTY",
            "parsed": {"slots": [], "parser_ok": True},
        }
    sheet, col, row = target
    parsed = parse_use_def_slots(candidate_formula, sheet, col, row)
    sccs = sccs or scc_stats(view)
    peers_pack = peers_pack or collect_peers(view, sheet, col, row)
    peers = peers_pack["formula_peers"]
    results = []
    results.extend(check_family_a(view, target, parsed, sccs))
    for k in K_THRESHOLDS:
        results.extend(check_family_b(view, target, parsed, peers, k))
        results.extend(check_family_c(parsed, candidate_formula, peers, k))
        results.extend(check_family_d(view, parsed, candidate_formula, peers, k))
    policies = [apply_policy(results, name) for name in ("H", "HE3", "HE5")]
    return {
        "results": results,
        "policies": policies,
        "kind": candidate_kind(candidate_formula),
        "parsed": {
            "n_slots": len(parsed["slots"]),
            "opaque": parsed.get("opaque"),
            "shape": parsed.get("shape"),
            "skeleton": operator_skeleton(candidate_formula),
            "literals": parsed.get("literals"),
        },
        "n_peers": peers_pack["n_formula_peers"],
        "peer_addresses": [p["address"] for p in peers[:12]],
    }
