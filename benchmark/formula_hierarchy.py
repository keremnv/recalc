"""Gold-blind hierarchical block extent vs role extent on frozen C1 tails.

Mechanical local row groups only. No semantic block/role labels, no goldens,
no formula reconstruction. Predicates are evidence, not a live/inactive bit.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from formula_dependency_selection import CellKey, DependencyGraph, homologous_peers
from formula_frontier import (
    ExtentCache,
    SchemaLayer,
    _sequence_continues,
    _token,
)
from formula_liveness import ACTIVE, OccupancyGrid, OccupancyPeers, point_slots_for
from formula_liveness import FORMULA as FORMULA_KINDS

ROW_WINDOWS = (2, 4, 8, 16)
REP_WINDOW = 8
LEFT_SPAN = 8
MIN_LEFT = 3
MIN_BLOCK = 4
SHARES = (0.50, 0.75, 0.90)
TOLS = (0, 1, 2)
LAGS = (2, 4, 8)
K_SET = (2, 3, 5)
SCHEMA_HORIZON = 8
DENSE_LEFT = 0.50
SPARSE_RIGHT = 0.10
DELTA_BINS = (
    ("le_m8", None, -8),
    ("m7_m4", -7, -4),
    ("m3_m2", -3, -2),
    ("m1_p1", -1, 1),
    ("p2_p3", 2, 3),
    ("p4_p7", 4, 7),
    ("ge_p8", 8, None),
)
SIZE_BINS = (("2_3", 2, 3), ("4_7", 4, 7), ("8_15", 8, 15), ("ge16", 16, None))

DEFINITIONS = {
    "golden_in_generation": False,
    "population": (
        "Exact frozen C1 list from formula-frontier-probe. C1 is not redefined: "
        "ANY_POINT blank whose row last ACTIVE is strictly left of T and T lies "
        "in a blank tail of length ≥2."
    ),
    "block": (
        "Local row group in a fixed window ±2/±4/±8/±16 around T. A row qualifies "
        "if it has ≥3 ACTIVE cells in [T.col-8, T.col-1] (active qualifier) or "
        "≥3 FORMULA cells on that span (formula qualifier). Representative "
        "conjunctions use the ±8 active-qualified group. A block exists only if "
        "≥4 qualifying rows. Mode M is the most common last-ACTIVE column "
        "among those rows; ties take the mode nearest the target last ACTIVE, "
        "then the smaller column."
    ),
    "A": (
        "A1: ≥s of qualifying rows have last ACTIVE within tol of modal M, "
        "s∈{50,75,90}%, tol∈{0,1,2}. Conjunction A1 is 75% within ±1. "
        "A2: |role_end - M| ≤ tol. A3: role_end ≤ M - lag, lag∈{2,4,8}. "
        "A4: role_end ≥ M + lag."
    ),
    "B": (
        "Schema continuation beyond M. B1: ≥k distinct columns in (M+1..M+8) "
        "have a header value, a merge, or ≥2 occupied sheet cells. Conjunction "
        "k≥2. B2: zero such columns. B3: year/quarter/month/integer run of "
        "length ≥3 continues into a populated header cell at or after M+1."
    ),
    "Role": (
        "extent_delta = role_end - M. Role1 aligned: |delta|≤1. "
        "Role2 shorter: delta≤-2, also ≤-4 and ≤-8. Role3 longer: delta≥+2."
    ),
    "D": (
        "D1: ≥k distinct supported formula classes have their last formula on a "
        "qualifying row within ±1 of M. D2: target last-formula class stops at "
        "or before M while ≥2 other formula-qualified rows have last FORMULA "
        "> M+2. D3: ≥k rows with ≥50% FORMULA in the previous 8 columns and "
        "≤10% FORMULA in the next 8; conjunction k≥4."
    ),
    "E": (
        "Homology from occupancy row peers and other host rows of the target "
        "row's last supported formula class. E1: a homologue last ACTIVE ≥ M+d, "
        "d∈{1,2,4,8}, conjunction d≥2. E2: ≥2 homologues and ≥50% stop within "
        "±1 of M. E3: a homologue is ACTIVE at T.col or has last ACTIVE > M. "
        "E4: ≥2 homologues and ≥75% have last ACTIVE ≤ role_end+1."
    ),
    "F": (
        "F1: ≥s of qualifying rows are entirely blank on columns M+1..M+4. "
        "Conjunction 75%. F2: T.col is blank on the target row but <50% of "
        "qualifying rows are blank there. F3: blank share at T.col in [50%, 75)."
    ),
    "G": (
        "G1: ≥k qualifying rows have an explicit point-reference at T.col. "
        "G2: among qualifying rows, only T is point-referenced at T.col. "
        "G3: a point consumer of a stripe blank (qualifying row × [M+1,M+4]) "
        "sits at a column > M."
    ),
    "conjunctions": {
        "H1": "A1 75%±1 and A2 ±1",
        "H2": "H1 and B1",
        "H3": "H1 and D1 k≥2",
        "H4": "H1 and F1 75%",
        "H5": "H1 and G1 k≥2",
        "H6": "Role2 delta≤-4",
        "H7": "H6 and ≥2 qualifying rows last ACTIVE > role_end",
        "H8": "H6 and E4",
        "H9": "H1 and E1",
        "H10": "H1 and E2",
    },
    "not_used": (
        "Goldens, task text, business block/role names, official scores, agents, "
        "and formula correctness scoring are not used in features."
    ),
}


def _mode(values: list[int], prefer: int | None) -> int | None:
    if not values:
        return None
    counts = Counter(values)
    best = counts.most_common()
    top = best[0][1]
    tied = [col for col, n in best if n == top]
    if prefer is not None:
        tied.sort(key=lambda col: (abs(col - prefer), col))
    else:
        tied.sort()
    return tied[0]


def _delta_bin(delta: int | None) -> str | None:
    if delta is None:
        return None
    for name, lo, hi in DELTA_BINS:
        if lo is None and hi is not None and delta <= hi:
            return name
        if hi is None and lo is not None and delta >= lo:
            return name
        if lo is not None and hi is not None and lo <= delta <= hi:
            return name
    return None


def _size_bin(n: int) -> str:
    if n < 2:
        return "lt2"
    for name, lo, hi in SIZE_BINS:
        if hi is None and n >= lo:
            return name
        if hi is not None and lo <= n <= hi:
            return name
    return "lt2"


def left_counts(grid: OccupancyGrid, col: int, row: int) -> tuple[int, int]:
    n_active = n_formula = 0
    for c in range(max(1, col - LEFT_SPAN), col):
        kind = grid.kind(c, row)
        if kind in ACTIVE:
            n_active += 1
        if kind in FORMULA_KINDS:
            n_formula += 1
    return n_active, n_formula


def qualifying_rows(
    grid: OccupancyGrid,
    col: int,
    row: int,
    radius: int,
    *,
    formula: bool,
) -> list[int]:
    out = []
    lo = max(grid.min_row, row - radius)
    hi = min(grid.max_row, row + radius)
    for other in range(lo, hi + 1):
        n_active, n_formula = left_counts(grid, col, other)
        if formula:
            if n_formula >= MIN_LEFT:
                out.append(other)
        elif n_active >= MIN_LEFT:
            out.append(other)
    return out


def _right_formula_frac(grid: OccupancyGrid, col: int, row: int) -> float:
    kinds = [grid.kind(c, row) for c in range(col + 1, min(grid.max_col, col + LEFT_SPAN) + 1)]
    if not kinds:
        return 0.0
    return sum(1 for kind in kinds if kind in FORMULA_KINDS) / len(kinds)


def family_a(
    grid: OccupancyGrid,
    extent: ExtentCache,
    col: int,
    row: int,
    last_t: int | None,
) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    for radius in ROW_WINDOWS:
        qrows = qualifying_rows(grid, col, row, radius, formula=False)
        lasts_i = [v for r in qrows if (v := extent.last_active.get(r)) is not None]
        m = _mode(lasts_i, last_t)
        n = len(lasts_i)
        grid_a1 = {}
        for share in SHARES:
            for tol in TOLS:
                if m is None or n < MIN_BLOCK:
                    grid_a1[f"p{int(share * 100)}_t{tol}"] = False
                else:
                    hit = sum(1 for val in lasts_i if abs(val - m) <= tol)
                    grid_a1[f"p{int(share * 100)}_t{tol}"] = (hit / n) >= share
        a2 = {
            f"t{tol}": bool(m is not None and last_t is not None and abs(last_t - m) <= tol)
            for tol in TOLS
        }
        a3 = {
            f"d{lag}": bool(m is not None and last_t is not None and last_t <= m - lag)
            for lag in LAGS
        }
        a4 = {
            f"d{lag}": bool(m is not None and last_t is not None and last_t >= m + lag)
            for lag in LAGS
        }
        n_beyond_role = 0
        if last_t is not None:
            n_beyond_role = sum(1 for val in lasts_i if val > last_t)
        windows[str(radius)] = {
            "n": n,
            "M": m,
            "rows": qrows,
            "A1": grid_a1,
            "A2": a2,
            "A3": a3,
            "A4": a4,
            "n_beyond_role": n_beyond_role,
        }
    rep = windows[str(REP_WINDOW)]
    delta = None
    if last_t is not None and rep["M"] is not None:
        delta = last_t - rep["M"]
    return {
        "windows": windows,
        "n": rep["n"],
        "M": rep["M"],
        "delta": delta,
        "delta_bin": _delta_bin(delta),
        "size_bin": _size_bin(rep["n"]),
        "rows": rep["rows"],
        "A1": bool(rep["A1"]["p75_t1"]),
        "A2": bool(rep["A2"]["t1"]),
        "A3": bool(rep["A3"]["d2"]),
        "A4": bool(rep["A4"]["d2"]),
        "A1_grid": rep["A1"],
        "A2_grid": rep["A2"],
        "A3_grid": rep["A3"],
        "A4_grid": rep["A4"],
        "n_beyond_role": rep["n_beyond_role"],
        "Role1": delta is not None and abs(delta) <= 1,
        "Role2": delta is not None and delta <= -2,
        "Role2_d4": delta is not None and delta <= -4,
        "Role2_d8": delta is not None and delta <= -8,
        "Role3": delta is not None and delta >= 2,
    }


def family_b(
    schema: SchemaLayer | None,
    grid: OccupancyGrid,
    col: int,
    row: int,
    m: int | None,
) -> dict[str, Any]:
    if m is None:
        return {
            "B1": False,
            "B2": False,
            "B3": False,
            "B1_grid": {f"k{k}": False for k in (1, 2, 4, 8)},
            "n_schema_cols": 0,
            "merge_continues": False,
        }
    hi = min(grid.max_col, m + SCHEMA_HORIZON)
    header_cells: dict[int, object] = {}
    if schema is not None:
        best_n = -1
        for hrow, cells in schema.headers.items():
            if hrow >= row:
                continue
            n = sum(1 for c in cells if m - 4 <= c <= hi)
            if n > best_n:
                best_n = n
                header_cells = cells
    instantiated: set[int] = set()
    for c in range(m + 1, hi + 1):
        if c in header_cells:
            instantiated.add(c)
            continue
        occupied = sum(
            1
            for r in range(max(grid.min_row, row - 16), min(grid.max_row, row + 16) + 1)
            if grid.kind(c, r) in ACTIVE
        )
        if occupied >= 2:
            instantiated.add(c)
    merge_continues = False
    if schema is not None:
        for c1, _r1, c2, _r2 in schema.merges:
            if c1 <= m <= c2 and c2 > m:
                merge_continues = True
                instantiated.update(range(m + 1, min(c2, hi) + 1))
    n_cols = len(instantiated)
    b1_grid = {f"k{k}": n_cols >= k or (k == 1 and merge_continues) for k in (1, 2, 4, 8)}
    tokens = {}
    for c, value in header_cells.items():
        tok = _token(value)
        if tok is not None:
            tokens[c] = tok
    b3 = _sequence_continues(tokens, m, m + 1) if tokens else False
    return {
        "B1": b1_grid["k2"] or merge_continues,
        "B2": n_cols == 0 and not merge_continues,
        "B3": b3,
        "B1_grid": b1_grid,
        "n_schema_cols": n_cols,
        "merge_continues": merge_continues,
    }


def family_d(
    graph: DependencyGraph,
    grid: OccupancyGrid,
    extent: ExtentCache,
    sheet: str,
    col: int,
    row: int,
    m: int | None,
    last_f: int | None,
) -> dict[str, Any]:
    qrows = qualifying_rows(grid, col, row, REP_WINDOW, formula=True)
    classes_at_m: set[str] = set()
    n_continue = 0
    n_dense = 0
    target_eq = None
    if last_f is not None:
        node = graph.formulas.get((sheet, last_f, row))
        if node is not None:
            target_eq = node.eq_id
    for other in qrows:
        lf = extent.last_formula.get(other)
        if lf is None:
            continue
        if m is not None and lf > m + 2:
            n_continue += 1
        node = graph.formulas.get((sheet, lf, other))
        if node is not None and m is not None and abs(lf - m) <= 1:
            classes_at_m.add(node.eq_id)
        n_left_f = left_counts(grid, col, other)[1]
        left_span = min(LEFT_SPAN, max(col - 1, 1))
        left_frac = n_left_f / left_span if left_span else 0.0
        right_frac = _right_formula_frac(grid, m if m is not None else col, other)
        if left_frac >= DENSE_LEFT and right_frac <= SPARSE_RIGHT:
            n_dense += 1
    d1_grid = {f"k{k}": len(classes_at_m) >= k for k in K_SET}
    d2 = bool(
        target_eq is not None
        and m is not None
        and last_f is not None
        and last_f <= m
        and n_continue >= 2
    )
    d3_grid = {f"k{k}": n_dense >= k for k in (2, 3, 4, 5)}
    return {
        "D1": d1_grid["k2"],
        "D2": d2,
        "D3": d3_grid["k4"],
        "D1_grid": d1_grid,
        "D3_grid": d3_grid,
        "n_classes_at_M": len(classes_at_m),
        "n_formula_continue": n_continue,
        "n_dense": n_dense,
        "n_formula_rows": len(qrows),
    }


def _homologue_rows(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    last_f: int | None,
    class_cache: dict,
) -> set[int]:
    sheet, _col, row = key
    rows: set[int] = set()
    for peer_row, _kind in occ.row_peers.get(key, []):
        if peer_row != row:
            rows.add(peer_row)
    if last_f is not None:
        node = graph.formulas.get((sheet, last_f, row))
        if node is not None:
            for member in graph.by_eq.get(node.eq_id, []):
                if member[0] == sheet and member[2] != row:
                    rows.add(member[2])
    for eq_id, slot_index, formula_key in point_slots_for(graph, key):
        for peer in homologous_peers(graph, key, eq_id, slot_index, formula_key, class_cache):
            if peer[0] == sheet and peer[2] != row:
                rows.add(peer[2])
    return rows


def family_e(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    extent: ExtentCache,
    last_t: int | None,
    last_f: int | None,
    m: int | None,
    class_cache: dict,
) -> dict[str, Any]:
    sheet, col, _row = key
    rows = _homologue_rows(graph, key, occ, last_f, class_cache)
    lasts = []
    n_active_at_t = 0
    n_short = 0
    for other in rows:
        last_a = extent.last_active.get(other)
        if last_a is None:
            continue
        lasts.append(last_a)
        if graph.occupancy[sheet].kind(col, other) in ACTIVE or (m is not None and last_a > m):
            n_active_at_t += 1
        if last_t is not None and last_a <= last_t + 1:
            n_short += 1
    n = len(lasts)
    e1_grid = {
        f"d{d}": bool(m is not None and any(val >= m + d for val in lasts)) for d in (1, 2, 4, 8)
    }
    e2 = n >= 2 and m is not None and (sum(1 for val in lasts if abs(val - m) <= 1) / n) >= 0.5
    e3 = n_active_at_t >= 1
    e4 = n >= 2 and (n_short / n) >= 0.75
    return {
        "E1": e1_grid["d2"],
        "E2": e2,
        "E3": e3,
        "E4": e4,
        "E1_grid": e1_grid,
        "n_hom": n,
        "n_hom_active_beyond": n_active_at_t,
        "n_hom_short": n_short,
    }


def family_f(
    grid: OccupancyGrid,
    qrows: list[int],
    col: int,
    row: int,
    m: int | None,
) -> dict[str, Any]:
    empty = {f"p{int(s * 100)}": False for s in SHARES}
    if m is None or not qrows:
        return {
            "F1": False,
            "F2": False,
            "F3": False,
            "F1_grid": empty,
            "blank_share_w4": None,
            "blank_share_tcol": None,
            "n_stripe_rows": 0,
        }

    def row_blank(other: int, lo: int, hi: int) -> bool:
        return all(grid.kind(c, other) == "B" for c in range(lo, hi + 1))

    w4_hi = m + 4
    n = len(qrows)
    blank_w4 = sum(1 for r in qrows if row_blank(r, m + 1, w4_hi)) / n
    blank_t = sum(1 for r in qrows if grid.kind(col, r) == "B") / n
    f1_grid = {f"p{int(s * 100)}": blank_w4 >= s for s in SHARES}
    target_blank = grid.kind(col, row) == "B"
    return {
        "F1": f1_grid["p75"],
        "F2": target_blank and blank_t < 0.5,
        "F3": 0.5 <= blank_t < 0.75,
        "F1_grid": f1_grid,
        "blank_share_w4": round(blank_w4, 4),
        "blank_share_tcol": round(blank_t, 4),
        "n_stripe_rows": n,
    }


def family_g(
    graph: DependencyGraph,
    sheet: str,
    col: int,
    row: int,
    qrows: list[int],
    m: int | None,
) -> dict[str, Any]:
    demanded = [other for other in qrows if graph.point_rev.get((sheet, col, other))]
    g1_grid = {f"k{k}": len(demanded) >= k for k in K_SET}
    g2 = demanded == [row] or (len(demanded) == 1 and demanded[0] == row)
    g3 = False
    if m is not None:
        hi = m + 4
        for other in qrows:
            for c in range(m + 1, hi + 1):
                for formula_key, _slot in graph.point_rev.get((sheet, c, other)) or []:
                    if formula_key[1] > m:
                        g3 = True
                        break
                if g3:
                    break
            if g3:
                break
    return {
        "G1": g1_grid["k2"],
        "G2": bool(g2 and not g1_grid["k2"]),
        "G3": g3,
        "G1_grid": g1_grid,
        "n_demand_rows": len(demanded),
    }


def conjunctions(flags: dict[str, bool]) -> dict[str, bool]:
    h1 = bool(flags.get("A1") and flags.get("A2"))
    h6 = bool(flags.get("Role2_d4"))
    return {
        "H1": h1,
        "H2": h1 and bool(flags.get("B1")),
        "H3": h1 and bool(flags.get("D1")),
        "H4": h1 and bool(flags.get("F1")),
        "H5": h1 and bool(flags.get("G1")),
        "H6": h6,
        "H7": h6 and bool(flags.get("block_continues")),
        "H8": h6 and bool(flags.get("E4")),
        "H9": h1 and bool(flags.get("E1")),
        "H10": h1 and bool(flags.get("E2")),
    }


def features_for_cell(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    extent: ExtentCache,
    schema: SchemaLayer | None,
    class_cache: dict,
    frozen: dict[str, Any],
) -> dict[str, Any]:
    sheet, col, row = key
    grid = graph.occupancy[sheet]
    last_t = frozen.get("last_active_col")
    if last_t is None:
        last_t = extent.last_active.get(row)
    last_f = frozen.get("last_formula_col")
    if last_f is None:
        last_f = extent.last_formula.get(row)
    a = family_a(grid, extent, col, row, last_t)
    b = family_b(schema, grid, col, row, a["M"])
    d = family_d(graph, grid, extent, sheet, col, row, a["M"], last_f)
    e = family_e(graph, key, occ, extent, last_t, last_f, a["M"], class_cache)
    f = family_f(grid, a["rows"], col, row, a["M"])
    g = family_g(graph, sheet, col, row, a["rows"], a["M"])
    flags = {
        "A1": a["A1"],
        "A2": a["A2"],
        "A3": a["A3"],
        "A4": a["A4"],
        "B1": b["B1"],
        "B2": b["B2"],
        "B3": b["B3"],
        "Role1": a["Role1"],
        "Role2": a["Role2"],
        "Role2_d4": a["Role2_d4"],
        "Role2_d8": a["Role2_d8"],
        "Role3": a["Role3"],
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
        "G1": g["G1"],
        "G2": g["G2"],
        "G3": g["G3"],
        "block_continues": a["n_beyond_role"] >= 2,
    }
    for name, val in a["A1_grid"].items():
        flags[f"A1_{name}"] = bool(val)
    for name, val in a["A2_grid"].items():
        flags[f"A2_{name}"] = bool(val)
    for name, val in a["A3_grid"].items():
        flags[f"A3_{name}"] = bool(val)
    for name, val in a["A4_grid"].items():
        flags[f"A4_{name}"] = bool(val)
    for name, val in b["B1_grid"].items():
        flags[f"B1_{name}"] = bool(val)
    for name, val in d["D1_grid"].items():
        flags[f"D1_{name}"] = bool(val)
    for name, val in d["D3_grid"].items():
        flags[f"D3_{name}"] = bool(val)
    for name, val in e["E1_grid"].items():
        flags[f"E1_{name}"] = bool(val)
    for name, val in f["F1_grid"].items():
        flags[f"F1_{name}"] = bool(val)
    for name, val in g["G1_grid"].items():
        flags[f"G1_{name}"] = bool(val)
    for name, val in conjunctions(flags).items():
        flags[name] = bool(val)
    return {
        "sheet": sheet,
        "col": col,
        "row": row,
        "last_active_col": last_t,
        "last_formula_col": last_f,
        "M": a["M"],
        "delta": a["delta"],
        "delta_bin": a["delta_bin"],
        "size_bin": a["size_bin"],
        "n_block": a["n"],
        "qual_rows": a["rows"][:40],
        "flags": flags,
        "A": {k: a[k] for k in ("A1", "A2", "A3", "A4", "n", "M", "delta", "n_beyond_role")},
        "B": {k: b[k] for k in ("B1", "B2", "B3", "n_schema_cols")},
        "Role": {k: a[k] for k in ("Role1", "Role2", "Role2_d4", "Role2_d8", "Role3")},
        "D": {k: d[k] for k in ("D1", "D2", "D3", "n_classes_at_M", "n_dense")},
        "E": {k: e[k] for k in ("E1", "E2", "E3", "E4", "n_hom")},
        "F": {k: f[k] for k in ("F1", "F2", "F3", "blank_share_w4", "blank_share_tcol")},
        "G": {k: g[k] for k in ("G1", "G2", "G3", "n_demand_rows")},
    }


A1_VARIANTS = tuple(f"A1_p{int(s * 100)}_t{t}" for s in SHARES for t in TOLS)
ROLE_FLAGS = ("Role1", "Role2", "Role2_d4", "Role2_d8", "Role3")
CORE_ATOMIC = (
    "A1",
    "A2",
    "A3",
    "A4",
    "B1",
    "B2",
    "B3",
) + ROLE_FLAGS + (
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
    "G1",
    "G2",
    "G3",
)
ATOMIC = CORE_ATOMIC + A1_VARIANTS + (
    "B1_k1",
    "B1_k2",
    "B1_k4",
    "B1_k8",
    "D1_k2",
    "D1_k3",
    "D1_k5",
    "D3_k2",
    "D3_k3",
    "D3_k4",
    "D3_k5",
    "E1_d1",
    "E1_d2",
    "E1_d4",
    "E1_d8",
    "F1_p50",
    "F1_p75",
    "F1_p90",
    "G1_k2",
    "G1_k3",
    "G1_k5",
    "A2_t0",
    "A2_t1",
    "A2_t2",
    "A3_d2",
    "A3_d4",
    "A3_d8",
    "A4_d2",
    "A4_d4",
    "A4_d8",
)
CONJUNCTIONS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10")
