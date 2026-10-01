"""Gold-blind dependency/dataflow target-selection probe.

Reverse-reference graph over supported explicit A1 formulas. Opaque, named,
dynamic, and unparsable references create no edges. Golden workbooks are not
consulted during graph construction or selector freeze.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"

import sys

sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address  # noqa: E402
from formula_completion_certs import load_grids  # noqa: E402
from formula_target_selection import OccupancyGrid, occupancy_from_grid  # noqa: E402
from librecalc_mcp.domain.formulas import formula_a1_references  # noqa: E402
from ranges import parse_a1_cell  # noqa: E402

Kind = Literal["F", "O", "V", "B"]
CellKey = tuple[str, int, int]

D1_KS = (1, 2, 3, 5)
D2_KS = (1, 2, 3)
D3_KS = (2, 3, 5)
D3_SHARES = (1.0, 0.90, 0.75)
D4_KS = (2, 3, 5)
D5_KS = (2, 3, 5)
D6_KS = (2, 3)
BFS_VISIT_CAP = 250_000

DEFINITIONS = {
    "graph": (
        "Reverse-reference index over supported (non-opaque) formulas only. "
        "An edge exists from referenced cell/range to the formula cell that "
        "explicitly names it in A1. INDIRECT/OFFSET, named ranges, structured "
        "refs, 3D refs, externals, and unparsable forms create no edges. "
        "Unknown sheet names drop the edge. False-negative edges are preferred "
        "to guessed dependencies. Ranges are stored as rectangles; membership "
        "is exact containment. Candidate blanks are clipped to each sheet's "
        "used occupancy bbox."
    ),
    "slot": (
        "Canonical reference slot = 0-based index of an explicit A1 ref in a "
        "supported formula. Members of one equivalence class are required to "
        "have the same slot count. Homologous precedent of T through slot R is "
        "the cell at T's offset inside every other member's resolved R range."
    ),
    "formula_bearing": (
        "Occupancy F (supported formula). Opaque formulas (O) are recorded but "
        "do not count as formula-role consensus."
    ),
    "D1": "Blank referenced by ≥k supported formulas. k in {1,2,3,5}.",
    "D2": "Blank referenced by formulas from ≥k distinct equivalence classes. k in {1,2,3}.",
    "D3": (
        "Formula-role consensus. Some consumer class F references T through "
        "slot R; ≥k other members provide homologous R-slot cells; the share "
        "of those cells with occupancy F is ≥ s. Grid: k in {2,3,5} × s in "
        "{100%, 90%, 75%}. Reported in full; not tuned."
    ),
    "D4": (
        "Dependency-role singleton hole. ≥k homologous peers; every peer is F; "
        "T is the only blank in {T} ∪ peers."
    ),
    "D5": (
        "Same-formula-role consensus. D3 100% at the same k, and all "
        "formula-bearing peers share one equivalence class."
    ),
    "D6": (
        "Independent consumer corroboration. ≥k distinct consumer classes each "
        "provide D3 100% k≥2 (D6) or D5 k≥2 (D6_D5)."
    ),
    "not_used": (
        "Goldens, labels, styles, task semantics, occupancy selectors as "
        "primary rules, ranking, and classifiers are not used to define "
        "dependency objects."
    ),
}


@dataclass(frozen=True)
class SlotGeom:
    index: int
    sheet: str
    min_col: int
    min_row: int
    max_col: int
    max_row: int
    cross_sheet: bool


@dataclass
class FormulaNode:
    key: CellKey
    formula: str
    eq_id: str
    fingerprint: str
    slots: list[SlotGeom]


@dataclass
class DependencyGraph:
    occupancy: dict[str, OccupancyGrid]
    formulas: dict[CellKey, FormulaNode]
    by_eq: dict[str, list[CellKey]]
    point_rev: dict[CellKey, list[tuple[CellKey, int]]]
    rects: list[tuple[CellKey, SlotGeom]]
    formula_fwd: dict[CellKey, set[CellKey]]
    coverage: dict[str, int] = field(default_factory=dict)

    def kind(self, key: CellKey) -> Kind:
        sheet, col, row = key
        grid = self.occupancy.get(sheet)
        if grid is None:
            return "B"
        return grid.kind(col, row)


def _parse_address(text: str) -> tuple[int, int] | None:
    try:
        return parse_a1_cell(text)
    except ValueError:
        return None


def _slot_geoms(
    formula: str,
    origin_sheet: str,
    known_sheets: set[str],
) -> tuple[list[SlotGeom], int]:
    dropped = 0
    slots: list[SlotGeom] = []
    for index, (ref_sheet, start, end) in enumerate(formula_a1_references(formula)):
        sheet = ref_sheet or origin_sheet
        if sheet not in known_sheets:
            dropped += 1
            continue
        first = _parse_address(start)
        last = _parse_address(end) if end else first
        if first is None or last is None:
            dropped += 1
            continue
        c1, r1 = first
        c2, r2 = last
        slots.append(
            SlotGeom(
                index=index,
                sheet=sheet,
                min_col=min(c1, c2),
                min_row=min(r1, r2),
                max_col=max(c1, c2),
                max_row=max(r1, r2),
                cross_sheet=sheet != origin_sheet,
            )
        )
    return slots, dropped


def _contains(slot: SlotGeom, sheet: str, col: int, row: int) -> bool:
    return (
        slot.sheet == sheet
        and slot.min_col <= col <= slot.max_col
        and slot.min_row <= row <= slot.max_row
    )


def _offset(slot: SlotGeom, col: int, row: int) -> tuple[int, int]:
    return col - slot.min_col, row - slot.min_row


def _apply_offset(slot: SlotGeom, dc: int, dr: int) -> CellKey | None:
    col = slot.min_col + dc
    row = slot.min_row + dr
    if col < 1 or row < 1:
        return None
    if col > slot.max_col or row > slot.max_row:
        return None
    return (slot.sheet, col, row)


def build_graph_from_grids(grids) -> DependencyGraph:
    occupancy = {grid.title: occupancy_from_grid(grid) for grid in grids}
    known_sheets = set(occupancy)
    formulas: dict[CellKey, FormulaNode] = {}
    by_eq: dict[str, list[CellKey]] = defaultdict(list)
    point_rev: dict[CellKey, list[tuple[CellKey, int]]] = defaultdict(list)
    rects: list[tuple[CellKey, SlotGeom]] = []
    formula_cells = 0
    opaque = 0
    supported = 0
    with_edges = 0
    point_edges = 0
    range_edges = 0
    cross_edges = 0
    dropped_unknown = 0
    for grid in grids:
        for (col, row), text in grid.formulas.items():
            formula_cells += 1
            fp = grid.source_fp[(col, row)]
            if fp.opaque:
                opaque += 1
                continue
            supported += 1
            key = (grid.title, col, row)
            slots, dropped = _slot_geoms(text, grid.title, known_sheets)
            dropped_unknown += dropped
            node = FormulaNode(
                key=key,
                formula=text,
                eq_id=fp.eq_id,
                fingerprint=fp.text,
                slots=slots,
            )
            formulas[key] = node
            by_eq[fp.eq_id].append(key)
            if not slots:
                continue
            with_edges += 1
            for slot in slots:
                if slot.cross_sheet:
                    cross_edges += 1
                area = (slot.max_col - slot.min_col + 1) * (slot.max_row - slot.min_row + 1)
                if area == 1:
                    target = (slot.sheet, slot.min_col, slot.min_row)
                    point_rev[target].append((key, slot.index))
                    point_edges += 1
                else:
                    rects.append((key, slot))
                    range_edges += 1
    coverage = {
        "formula_cells": formula_cells,
        "opaque": opaque,
        "supported": supported,
        "supported_with_edges": with_edges,
        "supported_without_edges": supported - with_edges,
        "point_edges": point_edges,
        "range_edges": range_edges,
        "cross_sheet_edges": cross_edges,
        "dropped_unknown_or_unparsed": dropped_unknown,
        "equivalence_classes": len(by_eq),
    }
    formula_fwd: dict[CellKey, set[CellKey]] = defaultdict(set)
    for target, dependents in point_rev.items():
        if target in formulas:
            for dep, _slot in dependents:
                formula_fwd[target].add(dep)
    for dep, slot in rects:
        grid = occupancy.get(slot.sheet)
        if grid is None:
            continue
        for (col, row), kind in grid.cells.items():
            if kind not in ("F", "O"):
                continue
            if not _contains(slot, slot.sheet, col, row):
                continue
            src = (slot.sheet, col, row)
            if src in formulas:
                formula_fwd[src].add(dep)
    return DependencyGraph(
        occupancy=occupancy,
        formulas=formulas,
        by_eq=dict(by_eq),
        point_rev=dict(point_rev),
        rects=rects,
        formula_fwd={key: set(vals) for key, vals in formula_fwd.items()},
        coverage=coverage,
    )


def build_graph(path: Path) -> DependencyGraph:
    return build_graph_from_grids(load_grids(path))


def _bbox_clip(grid: OccupancyGrid, slot: SlotGeom) -> tuple[int, int, int, int] | None:
    c1 = max(slot.min_col, grid.min_col)
    c2 = min(slot.max_col, grid.max_col)
    r1 = max(slot.min_row, grid.min_row)
    r2 = min(slot.max_row, grid.max_row)
    if c1 > c2 or r1 > r2:
        return None
    return c1, r1, c2, r2


def _add_dep(
    bucket: dict[CellKey, dict[str, Any]],
    key: CellKey,
    formula: CellKey,
    slot_index: int,
    eq_id: str,
    cross_sheet: bool,
) -> None:
    item = bucket.setdefault(
        key,
        {
            "dependents": set(),
            "eq_ids": set(),
            "slots": set(),
            "cross_sheet": False,
        },
    )
    item["dependents"].add(formula)
    item["eq_ids"].add(eq_id)
    item["slots"].add((eq_id, slot_index, formula))
    if cross_sheet:
        item["cross_sheet"] = True


def referenced_blanks(graph: DependencyGraph) -> dict[CellKey, dict[str, Any]]:
    out: dict[CellKey, dict[str, Any]] = {}
    for key, deps in graph.point_rev.items():
        sheet, col, row = key
        if col < 1 or row < 1:
            continue
        if graph.kind(key) != "B":
            continue
        if sheet not in graph.occupancy:
            continue
        for formula_key, slot_index in deps:
            node = graph.formulas[formula_key]
            _add_dep(
                out,
                key,
                formula_key,
                slot_index,
                node.eq_id,
                formula_key[0] != key[0],
            )
    for formula_key, slot in graph.rects:
        grid = graph.occupancy.get(slot.sheet)
        if grid is None:
            continue
        clipped = _bbox_clip(grid, slot)
        if clipped is None:
            continue
        c1, r1, c2, r2 = clipped
        node = graph.formulas[formula_key]
        for col in range(c1, c2 + 1):
            for row in range(r1, r2 + 1):
                key = (slot.sheet, col, row)
                if graph.kind(key) != "B":
                    continue
                _add_dep(out, key, formula_key, slot.index, node.eq_id, slot.cross_sheet)
    return out


RANGE_AREA_BINS = (
    ("1-4", 1, 4),
    ("5-25", 5, 25),
    ("26-100", 26, 100),
    ("101-1000", 101, 1000),
    (">1000", 1001, None),
)


def range_area_bin(area: int) -> str:
    for name, lo, hi in RANGE_AREA_BINS:
        if hi is None:
            if area >= lo:
                return name
        elif lo <= area <= hi:
            return name
    return ">1000"


def slot_area(slot: SlotGeom) -> int:
    return (slot.max_col - slot.min_col + 1) * (slot.max_row - slot.min_row + 1)


def blank_edge_types(graph: DependencyGraph) -> dict[CellKey, dict[str, Any]]:
    """Tag D1-visible blanks by point vs range edges. Does not change D1."""
    out: dict[CellKey, dict[str, Any]] = {}

    def bucket(key: CellKey) -> dict[str, Any]:
        return out.setdefault(
            key,
            {
                "point_formulas": set(),
                "range_formulas": set(),
                "point_eq_ids": set(),
                "range_eq_ids": set(),
                "point_same_sheet": False,
                "point_cross_sheet": False,
                "range_areas": [],
            },
        )

    for key, deps in graph.point_rev.items():
        sheet, col, row = key
        if col < 1 or row < 1:
            continue
        if graph.kind(key) != "B":
            continue
        if sheet not in graph.occupancy:
            continue
        item = bucket(key)
        for formula_key, _slot_index in deps:
            node = graph.formulas[formula_key]
            item["point_formulas"].add(formula_key)
            item["point_eq_ids"].add(node.eq_id)
            if formula_key[0] == sheet:
                item["point_same_sheet"] = True
            else:
                item["point_cross_sheet"] = True
    for formula_key, slot in graph.rects:
        grid = graph.occupancy.get(slot.sheet)
        if grid is None:
            continue
        clipped = _bbox_clip(grid, slot)
        if clipped is None:
            continue
        c1, r1, c2, r2 = clipped
        node = graph.formulas[formula_key]
        area = slot_area(slot)
        for col in range(c1, c2 + 1):
            for row in range(r1, r2 + 1):
                key = (slot.sheet, col, row)
                if graph.kind(key) != "B":
                    continue
                item = bucket(key)
                if formula_key not in item["range_formulas"]:
                    item["range_formulas"].add(formula_key)
                    item["range_eq_ids"].add(node.eq_id)
                    item["range_areas"].append(area)
    for key, item in out.items():
        has_point = bool(item["point_formulas"])
        has_range = bool(item["range_formulas"])
        if has_point and has_range:
            item["partition"] = "POINT_AND_RANGE"
        elif has_point:
            item["partition"] = "POINT_ONLY"
        else:
            item["partition"] = "RANGE_ONLY"
        item["n_point"] = len(item["point_formulas"])
        item["n_range"] = len(item["range_formulas"])
        item["n_point_eq"] = len(item["point_eq_ids"])
        item["n_range_eq"] = len(item["range_eq_ids"])
        item["min_range_area"] = min(item["range_areas"]) if item["range_areas"] else None
        item["max_range_area"] = max(item["range_areas"]) if item["range_areas"] else None
    return out


def _class_slot_geoms(
    graph: DependencyGraph,
    eq_id: str,
    cache: dict[str, dict[int, list[tuple[CellKey, SlotGeom]]] | None] | None = None,
) -> dict[int, list[tuple[CellKey, SlotGeom]]] | None:
    if cache is not None and eq_id in cache:
        return cache[eq_id]
    members = graph.by_eq.get(eq_id) or []
    packed: dict[int, list[tuple[CellKey, SlotGeom]]] | None
    if len(members) < 2:
        packed = None
    else:
        counts = {len(graph.formulas[key].slots) for key in members}
        if len(counts) != 1:
            packed = None
        else:
            by_slot: dict[int, list[tuple[CellKey, SlotGeom]]] = defaultdict(list)
            for key in members:
                node = graph.formulas[key]
                seen: set[int] = set()
                for slot in node.slots:
                    if slot.index in seen:
                        continue
                    seen.add(slot.index)
                    by_slot[slot.index].append((key, slot))
            packed = dict(by_slot)
    if cache is not None:
        cache[eq_id] = packed
    return packed


def homologous_peers(
    graph: DependencyGraph,
    target: CellKey,
    eq_id: str,
    slot_index: int,
    source_formula: CellKey,
    cache: dict[str, dict[int, list[tuple[CellKey, SlotGeom]]] | None] | None = None,
) -> list[CellKey]:
    packed = _class_slot_geoms(graph, eq_id, cache)
    if packed is None or slot_index not in packed:
        return []
    source_slot = None
    for key, slot in packed[slot_index]:
        if key == source_formula:
            source_slot = slot
            break
    if source_slot is None or not _contains(source_slot, *target):
        return []
    dc, dr = _offset(source_slot, target[1], target[2])
    peers: list[CellKey] = []
    seen: set[CellKey] = set()
    for key, slot in packed[slot_index]:
        if key == source_formula:
            continue
        cell = _apply_offset(slot, dc, dr)
        if cell is None or cell == target or cell in seen:
            continue
        seen.add(cell)
        peers.append(cell)
    return peers


def _role_record(graph: DependencyGraph, peers: list[CellKey]) -> dict[str, Any]:
    kinds = {"F": 0, "O": 0, "V": 0, "B": 0}
    formula_eqs: list[str] = []
    for peer in peers:
        kind = graph.kind(peer)
        kinds[kind] += 1
        if kind == "F":
            node = graph.formulas.get(peer)
            if node is not None:
                formula_eqs.append(node.eq_id)
    n = len(peers)
    n_f = kinds["F"]
    share = n_f / n if n else 0.0
    same_eq = len(set(formula_eqs)) == 1 if formula_eqs else False
    return {
        "n_peers": n,
        "n_formula": n_f,
        "share": share,
        "kinds": kinds,
        "same_formula_eq": same_eq,
        "peer_eq_id": formula_eqs[0] if same_eq and formula_eqs else None,
        "peer_eq_ids": sorted(set(formula_eqs)),
    }


def slot_evidence(
    graph: DependencyGraph, blanks: dict[CellKey, dict[str, Any]]
) -> dict[CellKey, list[dict[str, Any]]]:
    evidence: dict[CellKey, list[dict[str, Any]]] = {}
    class_cache: dict[str, dict[int, list[tuple[CellKey, SlotGeom]]] | None] = {}
    for key, meta in blanks.items():
        seen_pairs: set[tuple[str, int]] = set()
        records = []
        for eq_id, slot_index, formula_key in meta["slots"]:
            pair = (eq_id, slot_index)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            peers = homologous_peers(
                graph, key, eq_id, slot_index, formula_key, class_cache
            )
            rec = _role_record(graph, peers)
            rec["eq_id"] = eq_id
            rec["slot_index"] = slot_index
            records.append(rec)
        evidence[key] = records
    return evidence


def select_d1(blanks: dict[CellKey, dict[str, Any]], k: int) -> set[CellKey]:
    return {key for key, meta in blanks.items() if len(meta["dependents"]) >= k}


def select_d2(blanks: dict[CellKey, dict[str, Any]], k: int) -> set[CellKey]:
    return {key for key, meta in blanks.items() if len(meta["eq_ids"]) >= k}


def select_d3(
    evidence: dict[CellKey, list[dict[str, Any]]],
    k: int,
    share: float,
) -> set[CellKey]:
    selected = set()
    for key, records in evidence.items():
        for rec in records:
            if rec["n_peers"] >= k and rec["share"] + 1e-12 >= share:
                selected.add(key)
                break
    return selected


def select_d4(evidence: dict[CellKey, list[dict[str, Any]]], k: int) -> set[CellKey]:
    selected = set()
    for key, records in evidence.items():
        for rec in records:
            if rec["n_peers"] >= k and rec["n_formula"] == rec["n_peers"] and rec["kinds"]["B"] == 0:
                selected.add(key)
                break
    return selected


def select_d5(evidence: dict[CellKey, list[dict[str, Any]]], k: int) -> set[CellKey]:
    selected = set()
    for key, records in evidence.items():
        for rec in records:
            if (
                rec["n_peers"] >= k
                and rec["share"] + 1e-12 >= 1.0
                and rec["n_formula"] >= k
                and rec["same_formula_eq"]
            ):
                selected.add(key)
                break
    return selected


def select_d6(
    evidence: dict[CellKey, list[dict[str, Any]]],
    k: int,
    *,
    d5: bool,
) -> set[CellKey]:
    selected = set()
    for key, records in evidence.items():
        classes = set()
        for rec in records:
            ok = rec["n_peers"] >= 2 and rec["share"] + 1e-12 >= 1.0
            if d5:
                ok = ok and rec["n_formula"] >= 2 and rec["same_formula_eq"]
            if ok:
                classes.add(rec["eq_id"])
        if len(classes) >= k:
            selected.add(key)
    return selected


def downstream_impact(
    graph: DependencyGraph, start: CellKey, dependents: set[CellKey]
) -> dict[str, Any]:
    visited: set[CellKey] = set()
    queue: deque[tuple[CellKey, int]] = deque()
    for dep in dependents:
        queue.append((dep, 1))
    max_depth = 0
    sheets: set[str] = set()
    while queue and len(visited) < BFS_VISIT_CAP:
        node, depth = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        max_depth = max(max_depth, depth)
        sheets.add(node[0])
        for nxt in graph.formula_fwd.get(node, ()):
            if nxt not in visited:
                queue.append((nxt, depth + 1))
    return {
        "direct_dependents": len(dependents),
        "downstream_formulas": len(visited),
        "downstream_sheets": len(sheets),
        "max_depth": max_depth,
        "cross_sheet_downstream": any(sheet != start[0] for sheet in sheets),
        "bfs_capped": len(visited) >= BFS_VISIT_CAP and bool(queue),
    }


def d3_name(k: int, share: float) -> str:
    return f"D3_k{k}_s{int(round(share * 100))}"


def all_selector_names() -> list[str]:
    names = [f"D1_{k}" for k in D1_KS]
    names += [f"D2_{k}" for k in D2_KS]
    names += [d3_name(k, share) for k in D3_KS for share in D3_SHARES]
    names += [f"D4_{k}" for k in D4_KS]
    names += [f"D5_{k}" for k in D5_KS]
    names += [f"D6_{k}" for k in D6_KS]
    names += [f"D6_D5_{k}" for k in D6_KS]
    names += [
        "D1_1∩S1",
        "D3_k2_s100∩S1",
        "D5_2∩S1",
        "D3_k2_s100∩S5",
        "D5_2∩S5",
    ]
    return names


def select_all(
    graph: DependencyGraph,
    occupancy_s1: set[CellKey] | None = None,
    occupancy_s5: set[CellKey] | None = None,
) -> tuple[dict[str, set[CellKey]], dict[CellKey, dict[str, Any]], dict[CellKey, list[dict[str, Any]]]]:
    blanks = referenced_blanks(graph)
    evidence = slot_evidence(graph, blanks)
    selected: dict[str, set[CellKey]] = {}
    for k in D1_KS:
        selected[f"D1_{k}"] = select_d1(blanks, k)
    for k in D2_KS:
        selected[f"D2_{k}"] = select_d2(blanks, k)
    for k in D3_KS:
        for share in D3_SHARES:
            selected[d3_name(k, share)] = select_d3(evidence, k, share)
    for k in D4_KS:
        selected[f"D4_{k}"] = select_d4(evidence, k)
    for k in D5_KS:
        selected[f"D5_{k}"] = select_d5(evidence, k)
    for k in D6_KS:
        selected[f"D6_{k}"] = select_d6(evidence, k, d5=False)
        selected[f"D6_D5_{k}"] = select_d6(evidence, k, d5=True)
    s1 = occupancy_s1 or set()
    s5 = occupancy_s5 or set()
    selected["D1_1∩S1"] = selected["D1_1"] & s1
    selected["D3_k2_s100∩S1"] = selected["D3_k2_s100"] & s1
    selected["D5_2∩S1"] = selected["D5_2"] & s1
    selected["D3_k2_s100∩S5"] = selected["D3_k2_s100"] & s5
    selected["D5_2∩S5"] = selected["D5_2"] & s5
    return selected, blanks, evidence


def key_json(key: CellKey, **meta: Any) -> dict[str, Any]:
    sheet, col, row = key
    payload = {"sheet": sheet, "col": col, "row": row, "address": a1_address(col, row)}
    payload.update(meta)
    return payload
