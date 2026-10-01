"""Gold-blind slot liveness / regime predicates on point-referenced blanks.

Task-independent occupancy and homology only. No labels, no goldens, no
formula reconstruction. Predicates are evidence, not a single liveness bit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from formula_dependency_selection import (
    CellKey,
    DependencyGraph,
    homologous_peers,
)
from formula_target_selection import OccupancyGrid

Kind = Literal["F", "O", "V", "B"]
TypeTok = Literal["F", "V", "B"]

ACTIVE = frozenset({"F", "O", "V"})
FORMULA = frozenset({"F", "O"})
WINDOWS = (2, 4, 8)
REP_WINDOW = 4
DOMINANT_K = 3
BOUNDARY_TOL = 1
NEARBY_ROWS = 2
COORD_ROW_RADIUS = 4
BLANK_RUN_MIN = 3
D_SPAN = 8
E_K = (2, 3, 5)
E_SHARES = (1.0, 0.90, 0.75)
F_ACTIVE_SHARE = 0.75
F_BLANK_SHARE = 0.50
L6_SHARE = 0.75
L6_K = 2
L7_BLANK_SHARE = 0.75

DEFINITIONS = {
    "golden_in_generation": False,
    "population": (
        "ANY_POINT: input blank with ≥1 explicit supported point-reference. "
        "RANGE_ONLY excluded. Same reverse-A1 graph as the dependency probe."
    ),
    "types": (
        "Occupancy F = supported formula, O = opaque formula, V = populated "
        "value/text, B = blank. Formula vs value are never collapsed except "
        "where a predicate explicitly uses ACTIVE={F,O,V} or FORMULA={F,O}."
    ),
    "A": (
        "Row/column persistence in fixed windows ±2/±4/±8 and in the full "
        "contiguous run from T to the next ACTIVE cell or sheet bbox. "
        "A1 isolated hole: ACTIVE exists on both sides of T within ±4. "
        "A2 persistent blank segment: contiguous blank run length ≥3 containing "
        "T, and a neighboring line (±1) is ≥50% ACTIVE on that run's span."
    ),
    "B": (
        "TYPE REGIME TRANSITION. Tokenize F∪O as F. Dominant type of a 3-cell "
        "window is its unique mode (ties are no-claim). A boundary column c is "
        "where dominant(c-3:c-1) ≠ dominant(c:c+2). B1: T is at or after the "
        "nearest left boundary (T.col ≥ c) within 8 columns, and the post-side "
        "dominant is B. B2: ≥3 rows in T.row±2 have a boundary in T.col±1. "
        "B3 role-handoff: T's row is populated→B at a boundary in T.col±1, and "
        "a nearby row has post-side dominant F at that boundary±1."
    ),
    "C": (
        "Live-window extent from occupancy, not sheet used-range. "
        "C1: the row has a last ACTIVE column strictly left of T, and T sits "
        "in a blank tail of length ≥2. C2: ≥2 ACTIVE cells in [col-8,col-1] "
        "and ≥2 in [col+1,col+8]. C3: among rows in ±4 with any ACTIVE cell, "
        "≥3 and ≥50% have last ACTIVE column in [T.col-2, T.col]."
    ),
    "D": (
        "Blank identity on ±8 column span. D1: T's row ≥75% B and a neighbor "
        "row ±1 is ≥50% ACTIVE. D2: T's row ≥50% ACTIVE and ≤2 blanks in the "
        "span. D3: occupancy-vector homology (S4/S5-style) has ≥2 peers and "
        "peer blank share ≥75% at T's position."
    ),
    "E": (
        "Repeated-block slot occupancy. Peers are the union of occupancy "
        "row/column homology and formula-class homologous precedents of "
        "point-consumer slots. E1: ≥k peers ACTIVE, reported at k∈{2,3,5} "
        "and ACTIVE share ∈{100%,90%,75%}. Conjunction E1 uses k≥2 and "
        "share≥75%. E2: ≥2 peers and blank share ≥75%. E3: ≥2 ACTIVE peers "
        "and 0 other blank peers. E4: ≥2 other blank peers."
    ),
    "F": (
        "Point-consumer continuation. Homologous precedents through the same "
        "consumer eq_id+slot. F1: ≥2 peers, ACTIVE share ≥75%. F2: ≥2 peers, "
        "blank share ≥50%. F3: consumer class occupies ≥3 distinct columns "
        "and homologous-precedent blank share ≥50%."
    ),
    "conjunctions": {
        "L1": "A1_h4 or A1_v4, and not (A2_h or A2_v)",
        "L2": "B1 or B2",
        "L3": "B3",
        "L4": "C2",
        "L5": "C1 or C3",
        "L6": "E1 k≥2 share≥75%",
        "L7": "E2 or E4",
        "L8": "L6 and C2",
        "L9": "F2 or F3",
    },
    "not_used": (
        "Goldens, task text, styles, labels, official scores, agents, and "
        "formula synthesis are not used in feature construction."
    ),
}


def _tok(kind: Kind) -> TypeTok:
    if kind in FORMULA:
        return "F"
    if kind == "V":
        return "V"
    return "B"


def _dominant(tokens: list[TypeTok]) -> TypeTok | None:
    if not tokens:
        return None
    counts = Counter(tokens)
    ranked = counts.most_common()
    if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
        return ranked[0][0]
    return None


def _frac(kinds: list[Kind], pred) -> float:
    if not kinds:
        return 0.0
    return sum(1 for kind in kinds if pred(kind)) / len(kinds)


def _longest_run(kinds: list[Kind], pred) -> int:
    best = cur = 0
    for kind in kinds:
        if pred(kind):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _axis_window(
    grid: OccupancyGrid, col: int, row: int, radius: int, *, horizontal: bool
) -> list[Kind]:
    kinds: list[Kind] = []
    if horizontal:
        lo, hi = max(1, col - radius), col + radius
        hi = min(hi, grid.max_col)
        for c in range(lo, hi + 1):
            kinds.append(grid.kind(c, row))
    else:
        lo, hi = max(1, row - radius), row + radius
        hi = min(hi, grid.max_row)
        for r in range(lo, hi + 1):
            kinds.append(grid.kind(col, r))
    return kinds


def _run_from_t(
    grid: OccupancyGrid, col: int, row: int, *, horizontal: bool, left: bool
) -> tuple[int, Kind | None]:
    length = 1
    last_active: Kind | None = None
    if horizontal:
        step = -1 if left else 1
        pos = col + step
        bound = 1 if left else grid.max_col
        while (pos >= bound if left else pos <= bound):
            kind = grid.kind(pos, row)
            if kind in ACTIVE:
                last_active = kind
                break
            length += 1
            pos += step
    else:
        step = -1 if left else 1
        pos = row + step
        bound = 1 if left else grid.max_row
        while (pos >= bound if left else pos <= bound):
            kind = grid.kind(col, pos)
            if kind in ACTIVE:
                last_active = kind
                break
            length += 1
            pos += step
    return length, last_active


def persistence(
    grid: OccupancyGrid, col: int, row: int, radius: int, *, horizontal: bool
) -> dict[str, Any]:
    if horizontal:
        left_kinds = [grid.kind(c, row) for c in range(max(1, col - radius), col)]
        right_kinds = [
            grid.kind(c, row) for c in range(col + 1, min(grid.max_col, col + radius) + 1)
        ]
    else:
        left_kinds = [grid.kind(col, r) for r in range(max(1, row - radius), row)]
        right_kinds = [
            grid.kind(col, r) for r in range(row + 1, min(grid.max_row, row + radius) + 1)
        ]
    kinds = left_kinds + [grid.kind(col, row)] + right_kinds
    left_run, left_active = _run_from_t(grid, col, row, horizontal=horizontal, left=True)
    right_run, right_active = _run_from_t(
        grid, col, row, horizontal=horizontal, left=False
    )
    blank_run = left_run + right_run - 1
    isolated = any(k in ACTIVE for k in left_kinds) and any(k in ACTIVE for k in right_kinds)
    neighbor_active = False
    if horizontal:
        span_lo, span_hi = col - left_run + 1, col + right_run - 1
        for n_row in (row - 1, row + 1):
            if n_row < 1 or n_row > grid.max_row:
                continue
            span = [
                grid.kind(c, n_row)
                for c in range(max(1, span_lo), min(grid.max_col, span_hi) + 1)
            ]
            if span and _frac(span, lambda k: k in ACTIVE) >= 0.5:
                neighbor_active = True
                break
    else:
        span_lo, span_hi = row - left_run + 1, row + right_run - 1
        for n_col in (col - 1, col + 1):
            if n_col < 1 or n_col > grid.max_col:
                continue
            span = [
                grid.kind(n_col, r)
                for r in range(max(1, span_lo), min(grid.max_row, span_hi) + 1)
            ]
            if span and _frac(span, lambda k: k in ACTIVE) >= 0.5:
                neighbor_active = True
                break
    return {
        "n": len(kinds),
        "frac_F": round(_frac(kinds, lambda k: k == "F"), 4),
        "frac_O": round(_frac(kinds, lambda k: k == "O"), 4),
        "frac_V": round(_frac(kinds, lambda k: k == "V"), 4),
        "frac_B": round(_frac(kinds, lambda k: k == "B"), 4),
        "frac_formula": round(_frac(kinds, lambda k: k in FORMULA), 4),
        "longest_formula_run": _longest_run(kinds, lambda k: k in FORMULA),
        "longest_blank_run": _longest_run(kinds, lambda k: k == "B"),
        "isolated_hole": isolated,
        "blank_run": blank_run,
        "persistent_blank_segment": blank_run >= BLANK_RUN_MIN and neighbor_active,
        "left_support": left_active,
        "right_support": right_active,
    }


def row_boundaries(grid: OccupancyGrid, row: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    min_c, max_c = grid.min_col, grid.max_col
    if max_c - min_c + 1 < 2 * DOMINANT_K:
        return out
    for c in range(min_c + DOMINANT_K, max_c - DOMINANT_K + 2):
        left = [_tok(grid.kind(x, row)) for x in range(c - DOMINANT_K, c)]
        right = [_tok(grid.kind(x, row)) for x in range(c, min(c + DOMINANT_K, max_c + 1))]
        if len(right) < 2:
            continue
        dl, dr = _dominant(left), _dominant(right)
        if dl and dr and dl != dr:
            out.append({"col": c, "left": dl, "right": dr})
    return out


def last_active_col(grid: OccupancyGrid, row: int) -> int | None:
    last = None
    for col in range(grid.min_col, grid.max_col + 1):
        if grid.kind(col, row) in ACTIVE:
            last = col
    return last


def first_active_col(grid: OccupancyGrid, row: int) -> int | None:
    for col in range(grid.min_col, grid.max_col + 1):
        if grid.kind(col, row) in ACTIVE:
            return col
    return None


def sheet_scan(
    grid: OccupancyGrid, rows: Iterable[int] | None = None, pad: int = COORD_ROW_RADIUS
) -> dict[str, Any]:
    if rows is None:
        needed = list(range(grid.min_row, grid.max_row + 1))
    else:
        needed_set: set[int] = set()
        for row in rows:
            lo = max(grid.min_row, row - pad)
            hi = min(grid.max_row, row + pad)
            needed_set.update(range(lo, hi + 1))
        needed = sorted(needed_set)
    boundaries = {row: row_boundaries(grid, row) for row in needed}
    lasts = {row: last_active_col(grid, row) for row in needed}
    firsts = {row: first_active_col(grid, row) for row in needed}
    return {"boundaries": boundaries, "last": lasts, "first": firsts}


@dataclass
class OccupancyPeers:
    row_peers: dict[tuple[str, int, int], list[tuple[int, Kind]]] = field(default_factory=dict)
    col_peers: dict[tuple[str, int, int], list[tuple[int, Kind]]] = field(default_factory=dict)


def build_occupancy_peers(
    grids: dict[str, OccupancyGrid], wanted: set[CellKey] | None = None
) -> OccupancyPeers:
    """S4/S5-style homology: same occupancy vector except T's axis position."""
    peers = OccupancyPeers()
    wanted_sheets = {key[0] for key in wanted} if wanted is not None else None
    for title, grid in grids.items():
        if wanted_sheets is not None and title not in wanted_sheets:
            continue
        formula_cols = sorted(
            {col for (col, _row), kind in grid.cells.items() if kind in FORMULA}
        )
        formula_rows = sorted(
            {row for (_col, row), kind in grid.cells.items() if kind in FORMULA}
        )
        if formula_cols:
            row_ids = sorted({row for (_col, row) in grid.cells} | set(formula_rows))
            vectors: dict[int, tuple[str, ...]] = {}
            for row in row_ids:
                vec = tuple(_sig(grid.kind(col, row)) for col in formula_cols)
                if all(tok == "B" for tok in vec):
                    continue
                vectors[row] = vec
            col_index = {col: i for i, col in enumerate(formula_cols)}
            groups: dict[tuple[int, tuple[str, ...]], list[int]] = defaultdict(list)
            for row, vec in vectors.items():
                for i in range(len(vec)):
                    mask = vec[:i] + vec[i + 1 :]
                    groups[(i, mask)].append(row)
            for row, vec in vectors.items():
                for col, i in col_index.items():
                    key = (title, col, row)
                    if wanted is not None and key not in wanted:
                        continue
                    mask = vec[:i] + vec[i + 1 :]
                    others = [
                        (peer_row, grid.kind(col, peer_row))
                        for peer_row in groups.get((i, mask), [])
                        if peer_row != row
                    ]
                    if others:
                        peers.row_peers[key] = others
        if formula_rows:
            col_ids = sorted({col for (col, _row) in grid.cells} | set(formula_cols))
            vectors = {}
            for col in col_ids:
                vec = tuple(_sig(grid.kind(col, row)) for row in formula_rows)
                if all(tok == "B" for tok in vec):
                    continue
                vectors[col] = vec
            row_index = {row: i for i, row in enumerate(formula_rows)}
            groups = defaultdict(list)
            for col, vec in vectors.items():
                for i in range(len(vec)):
                    mask = vec[:i] + vec[i + 1 :]
                    groups[(i, mask)].append(col)
            for col, vec in vectors.items():
                for row, i in row_index.items():
                    key = (title, col, row)
                    if wanted is not None and key not in wanted:
                        continue
                    mask = vec[:i] + vec[i + 1 :]
                    others = [
                        (peer_col, grid.kind(peer_col, row))
                        for peer_col in groups.get((i, mask), [])
                        if peer_col != col
                    ]
                    if others:
                        peers.col_peers[key] = others
    return peers


def _sig(kind: Kind) -> str:
    return "F" if kind in FORMULA else kind


def _peer_stats(peer_kinds: list[Kind]) -> dict[str, Any]:
    n = len(peer_kinds)
    n_active = sum(1 for kind in peer_kinds if kind in ACTIVE)
    n_blank = sum(1 for kind in peer_kinds if kind == "B")
    n_formula = sum(1 for kind in peer_kinds if kind in FORMULA)
    n_value = sum(1 for kind in peer_kinds if kind == "V")
    return {
        "n_peers": n,
        "n_active": n_active,
        "n_blank": n_blank,
        "n_formula": n_formula,
        "n_value": n_value,
        "active_share": round(n_active / n, 4) if n else None,
        "blank_share": round(n_blank / n, 4) if n else None,
    }


def _row_bounds(
    grid: OccupancyGrid, row: int, scan: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if scan is not None and row in scan["boundaries"]:
        return scan["boundaries"][row]
    return row_boundaries(grid, row)


def _scan_last(grid: OccupancyGrid, row: int, scan: dict[str, Any] | None) -> int | None:
    if scan is not None and row in scan["last"]:
        return scan["last"][row]
    return last_active_col(grid, row)


def _scan_first(grid: OccupancyGrid, row: int, scan: dict[str, Any] | None) -> int | None:
    if scan is not None and row in scan["first"]:
        return scan["first"][row]
    return first_active_col(grid, row)


def family_a(grid: OccupancyGrid, col: int, row: int) -> dict[str, Any]:
    out: dict[str, Any] = {"h": {}, "v": {}}
    for radius in WINDOWS:
        out["h"][str(radius)] = persistence(grid, col, row, radius, horizontal=True)
        out["v"][str(radius)] = persistence(grid, col, row, radius, horizontal=False)
    h4 = out["h"][str(REP_WINDOW)]
    v4 = out["v"][str(REP_WINDOW)]
    out["A1_h"] = bool(h4["isolated_hole"])
    out["A1_v"] = bool(v4["isolated_hole"])
    out["A2_h"] = bool(h4["persistent_blank_segment"])
    out["A2_v"] = bool(v4["persistent_blank_segment"])
    out["A1"] = out["A1_h"] or out["A1_v"]
    out["A2"] = out["A2_h"] or out["A2_v"]
    out["A3"] = out["A1_v"] or out["A2_v"]
    return out


def family_b(
    grid: OccupancyGrid, col: int, row: int, scan: dict[str, Any] | None = None
) -> dict[str, Any]:
    bounds = _row_bounds(grid, row, scan)
    nearest = None
    for item in bounds:
        if item["col"] <= col + BOUNDARY_TOL:
            nearest = item
    b1 = False
    if nearest is not None and col >= nearest["col"] - BOUNDARY_TOL and nearest["right"] == "B":
        if col - nearest["col"] <= 8:
            b1 = True
    nearby_hit = 0
    nearby_rows = []
    for n_row in range(row - NEARBY_ROWS, row + NEARBY_ROWS + 1):
        if n_row < 1 or n_row > grid.max_row:
            continue
        for item in _row_bounds(grid, n_row, scan):
            if abs(item["col"] - col) <= BOUNDARY_TOL:
                nearby_hit += 1
                nearby_rows.append({"row": n_row, **item})
                break
    b2 = nearby_hit >= 3
    b3 = False
    b3_support: list[dict[str, Any]] = []
    t_bounds = [
        item
        for item in bounds
        if abs(item["col"] - col) <= BOUNDARY_TOL
        and item["left"] in {"V", "F"}
        and item["right"] == "B"
    ]
    if t_bounds:
        c0 = t_bounds[0]["col"]
        for n_row in range(row - NEARBY_ROWS, row + NEARBY_ROWS + 1):
            if n_row == row or n_row < 1 or n_row > grid.max_row:
                continue
            for item in _row_bounds(grid, n_row, scan):
                if abs(item["col"] - c0) <= BOUNDARY_TOL and item["right"] == "F":
                    b3 = True
                    b3_support.append({"row": n_row, **item})
    return {
        "B1": b1,
        "B2": b2,
        "B3": b3,
        "nearest_boundary": nearest,
        "coordinated_rows": nearby_rows[:8],
        "handoff_rows": b3_support[:8],
    }


def family_c(
    grid: OccupancyGrid, col: int, row: int, scan: dict[str, Any] | None = None
) -> dict[str, Any]:
    last = _scan_last(grid, row, scan)
    first = _scan_first(grid, row, scan)
    left = [grid.kind(c, row) for c in range(max(1, col - D_SPAN), col)]
    right = [grid.kind(c, row) for c in range(col + 1, min(grid.max_col, col + D_SPAN) + 1)]
    n_left = sum(1 for kind in left if kind in ACTIVE)
    n_right = sum(1 for kind in right if kind in ACTIVE)
    c2 = n_left >= 2 and n_right >= 2
    c1 = False
    tail = 0
    if last is not None and col > last:
        for c in range(last + 1, grid.max_col + 1):
            if grid.kind(c, row) in ACTIVE:
                break
            tail += 1
        c1 = tail >= 2
    active_rows = []
    for n_row in range(max(1, row - COORD_ROW_RADIUS), min(grid.max_row, row + COORD_ROW_RADIUS) + 1):
        end = _scan_last(grid, n_row, scan)
        if end is None:
            continue
        active_rows.append((n_row, end))
    aligned = [(n_row, end) for n_row, end in active_rows if col - 2 <= end <= col]
    c3 = len(active_rows) >= 3 and len(aligned) >= 3 and len(aligned) / len(active_rows) >= 0.5
    return {
        "C1": c1,
        "C2": c2,
        "C3": c3,
        "last_active_col": last,
        "first_active_col": first,
        "n_active_left8": n_left,
        "n_active_right8": n_right,
        "blank_tail": tail,
        "aligned_row_ends": len(aligned),
        "active_rows_nearby": len(active_rows),
    }


def family_d(
    grid: OccupancyGrid, col: int, row: int, occ: OccupancyPeers, key: CellKey
) -> dict[str, Any]:
    lo, hi = max(1, col - D_SPAN), min(grid.max_col, col + D_SPAN)
    span = [grid.kind(c, row) for c in range(lo, hi + 1)]
    blank_frac = _frac(span, lambda k: k == "B")
    active_frac = _frac(span, lambda k: k in ACTIVE)
    n_blank = sum(1 for kind in span if kind == "B")
    neighbor_active = False
    for n_row in (row - 1, row + 1):
        if n_row < 1 or n_row > grid.max_row:
            continue
        nspan = [grid.kind(c, n_row) for c in range(lo, hi + 1)]
        if _frac(nspan, lambda k: k in ACTIVE) >= 0.5:
            neighbor_active = True
    occ_peers = occ.row_peers.get(key, []) + occ.col_peers.get(key, [])
    occ_kinds = [kind for _peer, kind in occ_peers]
    stats = _peer_stats(occ_kinds)
    d3 = stats["n_peers"] >= 2 and (stats["blank_share"] or 0) >= 0.75
    return {
        "D1": blank_frac >= 0.75 and neighbor_active,
        "D2": active_frac >= 0.5 and n_blank <= 2,
        "D3": d3,
        "span_blank_frac": round(blank_frac, 4),
        "span_active_frac": round(active_frac, 4),
        "span_n_blank": n_blank,
        "occupancy_peers": stats,
    }


def family_e(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    class_cache: dict,
    point_slots: list[tuple[str, int, CellKey]],
) -> dict[str, Any]:
    kinds: list[Kind] = []
    seen: set[CellKey] = set()
    for peer_row, kind in occ.row_peers.get(key, []):
        pkey = (key[0], key[1], peer_row)
        if pkey not in seen:
            seen.add(pkey)
            kinds.append(kind)
    for peer_col, kind in occ.col_peers.get(key, []):
        pkey = (key[0], peer_col, key[2])
        if pkey not in seen:
            seen.add(pkey)
            kinds.append(kind)
    for eq_id, slot_index, formula_key in point_slots:
        for peer in homologous_peers(graph, key, eq_id, slot_index, formula_key, class_cache):
            if peer in seen:
                continue
            seen.add(peer)
            kinds.append(graph.kind(peer))
    stats = _peer_stats(kinds)
    e1 = {}
    for k in E_K:
        for share in E_SHARES:
            name = f"k{k}_s{int(share * 100)}"
            e1[name] = stats["n_active"] >= k and (stats["active_share"] or 0) >= share
    e1_conj = stats["n_active"] >= L6_K and (stats["active_share"] or 0) >= L6_SHARE
    e2 = stats["n_peers"] >= 2 and (stats["blank_share"] or 0) >= L7_BLANK_SHARE
    e3 = stats["n_active"] >= 2 and stats["n_blank"] == 0
    e4 = stats["n_blank"] >= 2
    return {
        "E1": e1_conj,
        "E1_grid": e1,
        "E2": e2,
        "E3": e3,
        "E4": e4,
        **stats,
    }


def family_f(
    graph: DependencyGraph,
    key: CellKey,
    class_cache: dict,
    point_slots: list[tuple[str, int, CellKey]],
) -> dict[str, Any]:
    kinds: list[Kind] = []
    consumer_cols: set[int] = set()
    seen: set[CellKey] = set()
    for eq_id, slot_index, formula_key in point_slots:
        consumer_cols.add(formula_key[1])
        node_class = graph.by_eq.get(eq_id) or []
        for member in node_class:
            consumer_cols.add(member[1])
        for peer in homologous_peers(graph, key, eq_id, slot_index, formula_key, class_cache):
            if peer in seen:
                continue
            seen.add(peer)
            kinds.append(graph.kind(peer))
    stats = _peer_stats(kinds)
    f1 = stats["n_peers"] >= 2 and (stats["active_share"] or 0) >= F_ACTIVE_SHARE
    f2 = stats["n_peers"] >= 2 and (stats["blank_share"] or 0) >= F_BLANK_SHARE
    f3 = len(consumer_cols) >= 3 and stats["n_peers"] >= 2 and (stats["blank_share"] or 0) >= F_BLANK_SHARE
    return {
        "F1": f1,
        "F2": f2,
        "F3": f3,
        "consumer_columns": len(consumer_cols),
        **stats,
    }


def point_slots_for(graph: DependencyGraph, key: CellKey) -> list[tuple[str, int, CellKey]]:
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int, CellKey]] = []
    for formula_key, slot_index in graph.point_rev.get(key) or []:
        node = graph.formulas[formula_key]
        pair = (node.eq_id, slot_index)
        if pair in seen:
            continue
        seen.add(pair)
        out.append((node.eq_id, slot_index, formula_key))
    return out


def features_for_cell(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    class_cache: dict,
    edge: dict[str, Any],
    scan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sheet, col, row = key
    grid = graph.occupancy[sheet]
    slots = point_slots_for(graph, key)
    a = family_a(grid, col, row)
    b = family_b(grid, col, row, scan)
    c = family_c(grid, col, row, scan)
    d = family_d(grid, col, row, occ, key)
    e = family_e(graph, key, occ, class_cache, slots)
    f = family_f(graph, key, class_cache, slots)
    flags = {
        "A1": a["A1"],
        "A1_h": a["A1_h"],
        "A1_v": a["A1_v"],
        "A2": a["A2"],
        "A2_h": a["A2_h"],
        "A2_v": a["A2_v"],
        "B1": b["B1"],
        "B2": b["B2"],
        "B3": b["B3"],
        "C1": c["C1"],
        "C2": c["C2"],
        "C3": c["C3"],
        "D1": d["D1"],
        "D2": d["D2"],
        "D3": d["D3"],
        "E1": e["E1"],
        "E2": e["E2"],
        "E3": e["E3"],
        "E4": e["E4"],
        "F1": f["F1"],
        "F2": f["F2"],
        "F3": f["F3"],
    }
    for name, val in e["E1_grid"].items():
        flags[f"E1_{name}"] = bool(val)
    flags.update(conjunctions(flags))
    return {
        "sheet": sheet,
        "col": col,
        "row": row,
        "n_point": edge["n_point"],
        "n_point_eq": edge["n_point_eq"],
        "partition": edge["partition"],
        "flags": flags,
        "A": {k: a[k] for k in ("A1", "A1_h", "A1_v", "A2", "A2_h", "A2_v")},
        "A_windows": {
            "h": {radius: a["h"][str(radius)] for radius in WINDOWS},
            "v": {radius: a["v"][str(radius)] for radius in WINDOWS},
        },
        "B": {
            k: b[k]
            for k in ("B1", "B2", "B3", "nearest_boundary", "coordinated_rows", "handoff_rows")
        },
        "C": {
            k: c[k]
            for k in (
                "C1",
                "C2",
                "C3",
                "last_active_col",
                "n_active_left8",
                "n_active_right8",
                "blank_tail",
                "aligned_row_ends",
                "active_rows_nearby",
            )
        },
        "D": {k: d[k] for k in ("D1", "D2", "D3", "span_blank_frac", "span_active_frac", "span_n_blank")},
        "E": {
            k: e[k]
            for k in (
                "E1",
                "E2",
                "E3",
                "E4",
                "n_peers",
                "n_active",
                "n_blank",
                "active_share",
                "blank_share",
                "E1_grid",
            )
        },
        "F": {
            k: f[k]
            for k in (
                "F1",
                "F2",
                "F3",
                "n_peers",
                "n_active",
                "n_blank",
                "active_share",
                "blank_share",
                "consumer_columns",
            )
        },
    }


def conjunctions(flags: dict[str, bool]) -> dict[str, bool]:
    l1 = bool(flags["A1"] and not flags["A2"])
    l2 = bool(flags["B1"] or flags["B2"])
    l3 = bool(flags["B3"])
    l4 = bool(flags["C2"])
    l5 = bool(flags["C1"] or flags["C3"])
    l6 = bool(flags["E1"])
    l7 = bool(flags["E2"] or flags["E4"])
    l8 = bool(l6 and flags["C2"])
    l9 = bool(flags["F2"] or flags["F3"])
    return {
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "L4": l4,
        "L5": l5,
        "L6": l6,
        "L7": l7,
        "L8": l8,
        "L9": l9,
    }


E1_VARIANTS = tuple(
    f"E1_k{k}_s{int(share * 100)}" for k in E_K for share in E_SHARES
)
ATOMIC = (
    "A1",
    "A1_h",
    "A1_v",
    "A2",
    "A2_h",
    "A2_v",
    "B1",
    "B2",
    "B3",
    "C1",
    "C2",
    "C3",
    "D1",
    "D2",
    "D3",
    "E1",
    "E2",
    "E3",
    "E4",
    "F1",
    "F2",
    "F3",
) + E1_VARIANTS
CONJUNCTIONS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9")
