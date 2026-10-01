"""Gold-blind continuation-vs-termination predicates on frozen C1 blank tails.

Task-independent occupancy, homology, headers, and formula-class structure only.
No labels, no goldens, no formula scoring. Predicates are evidence, not a
frontier classification bit.
"""
from __future__ import annotations

import calendar
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from formula_completion_certs import translate_to_target
from formula_dependency_selection import (
    CellKey,
    DependencyGraph,
    homologous_peers,
)
from formula_liveness import (
    ACTIVE,
    OccupancyGrid,
    OccupancyPeers,
    point_slots_for,
)
from formula_liveness import FORMULA as FORMULA_KINDS
from xlsx_metadata_repair import install

install()
import openpyxl  # noqa: E402

Kind = Literal["F", "O", "V", "B"]

ROW_WINDOWS = (1, 2, 4, 8)
REP_ROW = 4
CONT_K = (1, 2, 3, 5)
CONT_DEPTH = (1, 2, 4, 8)
STOP_TOL = (0, 1, 2)
REGION_WINDOWS = (2, 4, 8, 16)
REP_REGION = 8
F1_SHARES = (0.50, 0.75, 0.90)
HEADER_SCAN_ROWS = 24
HOM1_K = 2
D3_SHARE = 0.75
E4_BLANK = 0.50
F2_LAG = 4
DIST_BINS = ((1, 1, "1"), (2, 2, "2"), (3, 4, "3_4"), (5, 8, "5_8"), (9, 10**9, "gt8"))

_MONTH_NAME = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTH_ABBR = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
_QUARTER = re.compile(r"^(?:q\s*([1-4])|([1-4])\s*q)$", re.I)
_YEAR = re.compile(r"^(19|20)\d{2}$")

DEFINITIONS = {
    "golden_in_generation": False,
    "population": (
        "Frozen liveness C1: ANY_POINT blank whose row has last ACTIVE strictly "
        "left of T and a blank tail of length ≥2 containing T. Candidate list "
        "is reused from formula-liveness-probe; C1 is not redefined."
    ),
    "A": (
        "Sibling continuation in fixed row windows ±1/±2/±4/±8. "
        "A1: ≥k nearby rows (rep ±4) have last ACTIVE ≥ T.col + d. "
        "Conjunction A1 uses k≥2 and d≥2. "
        "A2 coordinated stop: ≥3 nearby rows have last ACTIVE within ±1 of the "
        "target row's last ACTIVE. "
        "A3 isolated stop: ≥2 nearby rows continue ≥4 cols past T, and A2 is false."
    ),
    "B": (
        "Header/grid continuation without business labels. Header row is the "
        "most populated value-row in the first 24 rows above T on the span "
        "from last ACTIVE through the blank tail. "
        "B1: ≥2 header cells populated strictly right of last ACTIVE, or a merge "
        "continues across that boundary. "
        "B2: header last populated column is within ±2 of last ACTIVE and B1 is false. "
        "B3: a mechanical year/quarter/month/integer run of length ≥3 continues "
        "into a populated header cell at or after T."
    ),
    "C_hom": (
        "Homologous role instances from occupancy-vector row homology, "
        "point-consumer formula-class offsets, and other rows of P's formula "
        "class. Hom1: ≥k homologues have last ACTIVE ≥ T.col (conj k≥2). "
        "Hom2: ≥2 homologues and ≥50% stop within ±1 of the target last ACTIVE. "
        "Hom3: P's formula class is instantiated at column ≥ T.col on another row."
    ),
    "D": (
        "P = last FORMULA cell on T's row with col < T.col. "
        "D1: P exists, T is the immediate next cell (T.col = P.col+1), and P's "
        "class has a same-row left neighbor. "
        "D2: P's class has a member with col > P.col. "
        "D3: among ≥2 rows that host P's class, ≥75% have the class max-col "
        "within ±1 of P.col. "
        "D4: translating P onto T is a supported relative fingerprint whose "
        "eq_id already exists elsewhere. The translated text is not persisted "
        "or scored."
    ),
    "E": (
        "Point-consumer continuation only. "
        "E1: a direct consumer class has a member with col > T.col. "
        "E2: every direct consumer class has max col within ±2 of T.col. "
        "E3: homologous consumer precedents include ≥2 ACTIVE cells. "
        "E4: ≥2 homologous precedents and blank share ≥50%."
    ),
    "F": (
        "Regional last-ACTIVE distribution in ±2/±4/±8/±16. "
        "F1: among ≥4 active rows in ±8, ≥75% terminate within ±1 of the modal "
        "last-ACTIVE column. Also reported at 50/75/90% and exact/±1/±2. "
        "F2: target last ACTIVE is ≥4 cols left of the ±8 median. "
        "F3: target last ACTIVE is within ±1 of the ±8 mode."
    ),
    "G": (
        "Blank-tail geometry. Distance = T.col - last ACTIVE. Tail length is "
        "the frozen C1 blank_tail. Bins 1 / 2 / 3–4 / 5–8 / >8 are predeclared. "
        "first_blank: distance=1. resume: an ACTIVE cell exists after the tail. "
        "to_extent: tail reaches the occupancy max_col."
    ),
    "conjunctions": {
        "Q1": "A3 and B1",
        "Q2": "A2 and F1",
        "Q3": "Hom1 k≥2",
        "Q4": "Hom2",
        "Q5": "D1 and D2",
        "Q6": "D3",
        "Q7": "≥2 of {A3, B1, Hom1, D2, E1, F2}",
        "Q8": "≥2 of {A2, B2, Hom2, D3, E2, F3}",
        "Q9": "D4",
    },
    "not_used": (
        "Goldens, task text, business-semantic header labels, official scores, "
        "agents, and formula correctness scoring are not used in features."
    ),
}


@dataclass
class ExtentCache:
    last_active: dict[int, int | None]
    last_formula: dict[int, int | None]
    min_row: int
    max_row: int
    max_col: int


def build_extent(grid: OccupancyGrid) -> ExtentCache:
    last_active = {}
    last_formula = {}
    for row in range(grid.min_row, grid.max_row + 1):
        last_a = last_f = None
        for col in range(grid.min_col, grid.max_col + 1):
            kind = grid.kind(col, row)
            if kind in ACTIVE:
                last_a = col
            if kind in FORMULA_KINDS:
                last_f = col
        last_active[row] = last_a
        last_formula[row] = last_f
    return ExtentCache(
        last_active=last_active,
        last_formula=last_formula,
        min_row=grid.min_row,
        max_row=grid.max_row,
        max_col=grid.max_col,
    )


def _nearby(row: int, radius: int, min_row: int, max_row: int) -> list[int]:
    return [
        other
        for other in range(row - radius, row + radius + 1)
        if other != row and min_row <= other <= max_row
    ]


def _bin_name(value: int) -> str:
    for lo, hi, name in DIST_BINS:
        if lo <= value <= hi:
            return name
    return "gt8"


def family_a(
    extent: ExtentCache, col: int, row: int, last_t: int | None
) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    for radius in ROW_WINDOWS:
        rows = _nearby(row, radius, extent.min_row, extent.max_row)
        continue_d = {depth: 0 for depth in CONT_DEPTH}
        continue_f = 0
        stop = {tol: 0 for tol in STOP_TOL}
        n_active = 0
        depths: list[int] = []
        for other in rows:
            last_a = extent.last_active.get(other)
            last_f = extent.last_formula.get(other)
            if last_a is None:
                continue
            n_active += 1
            if last_a > col:
                gap = last_a - col
                depths.append(gap)
                for depth in CONT_DEPTH:
                    if gap >= depth:
                        continue_d[depth] += 1
            if last_f is not None and last_f > col:
                continue_f += 1
            if last_t is not None:
                for tol in STOP_TOL:
                    if abs(last_a - last_t) <= tol:
                        stop[tol] += 1
        windows[str(radius)] = {
            "n_nearby_active": n_active,
            "continue_k": {str(depth): continue_d[depth] for depth in CONT_DEPTH},
            "continue_formula": continue_f,
            "stop_k": {str(tol): stop[tol] for tol in STOP_TOL},
            "max_continue_depth": max(depths) if depths else 0,
        }
    rep = windows[str(REP_ROW)]
    a1_grid = {
        f"k{k}_d{depth}": rep["continue_k"][str(depth)] >= k
        for k in CONT_K
        for depth in CONT_DEPTH
    }
    a2_grid = {f"k{k}_t{tol}": rep["stop_k"][str(tol)] >= k for k in CONT_K for tol in STOP_TOL}
    a1 = a1_grid["k2_d2"]
    a2 = a2_grid["k3_t1"]
    a3 = (rep["continue_k"]["4"] >= 2) and not a2
    return {
        "A1": a1,
        "A2": a2,
        "A3": a3,
        "A1_grid": a1_grid,
        "A2_grid": a2_grid,
        "windows": windows,
        "n_continue_k2_d2": rep["continue_k"]["2"],
        "n_stop_t1": rep["stop_k"]["1"],
        "max_continue_depth": rep["max_continue_depth"],
    }


def _token(value: object) -> tuple[str, int] | None:
    if value is None:
        return None
    if hasattr(value, "year") and hasattr(value, "month"):
        return ("year", int(value.year))
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        number = int(value)
        if 1990 <= number <= 2100:
            return ("year", number)
        return ("int", number)
    text = str(value).strip().lower()
    if not text:
        return None
    if text in _MONTH_NAME:
        return ("month", _MONTH_NAME[text])
    if text in _MONTH_ABBR:
        return ("month", _MONTH_ABBR[text])
    match = _QUARTER.match(text)
    if match:
        digit = match.group(1) or match.group(2)
        return ("quarter", int(digit))
    if _YEAR.match(text):
        return ("year", int(text))
    if text.isdigit():
        number = int(text)
        if 1990 <= number <= 2100:
            return ("year", number)
        return ("int", number)
    return None


def _sequence_continues(tokens: dict[int, tuple[str, int]], last_t: int, col: int) -> bool:
    cols = sorted(tokens)
    best = None
    for i, start in enumerate(cols):
        kind = tokens[start][0]
        run = [start]
        step = None
        for nxt in cols[i + 1 :]:
            if nxt != run[-1] + 1:
                break
            other = tokens[nxt]
            if other[0] != kind:
                break
            delta = other[1] - tokens[run[-1]][1]
            if step is None:
                if delta == 0:
                    break
                step = delta
            elif delta != step:
                break
            run.append(nxt)
        if len(run) >= 3 and (best is None or len(run) > len(best)):
            best = run
    if best is None or best[-1] < last_t:
        return False
    return any(c >= col for c in tokens)


@dataclass
class SchemaLayer:
    headers: dict[int, dict[int, object]]
    merges: list[tuple[int, int, int, int]]
    widths: dict[int, float | None]


def load_schema_layers(path: Path) -> dict[str, SchemaLayer]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    out: dict[str, SchemaLayer] = {}
    try:
        for sheet in workbook.worksheets:
            headers: dict[int, dict[int, object]] = defaultdict(dict)
            for row in range(1, HEADER_SCAN_ROWS + 1):
                for item in sheet[row]:
                    value = item.value
                    if value is None:
                        continue
                    if isinstance(value, str) and (value.startswith("=") or not value.strip()):
                        continue
                    headers[int(item.row)][int(item.column)] = value
            merges = [
                (rng.min_col, rng.min_row, rng.max_col, rng.max_row)
                for rng in sheet.merged_cells.ranges
            ]
            widths = {}
            for _letter, dim in sheet.column_dimensions.items():
                if dim.min is None:
                    continue
                for col in range(int(dim.min), int(dim.max or dim.min) + 1):
                    widths[col] = dim.width
            out[sheet.title] = SchemaLayer(dict(headers), merges, widths)
    finally:
        workbook.close()
    return out


def family_b(
    schema: SchemaLayer | None,
    col: int,
    row: int,
    last_t: int,
    tail: int,
    max_col: int,
) -> dict[str, Any]:
    span_lo = max(1, last_t - 4)
    span_hi = min(max_col, max(col + 4, last_t + max(tail, 1) + 2))
    header_row = None
    header_n = -1
    header_cells: dict[int, object] = {}
    if schema is not None:
        for hrow, cells in schema.headers.items():
            if hrow >= row:
                continue
            n = sum(1 for c in cells if span_lo <= c <= span_hi)
            if n > header_n:
                header_n = n
                header_row = hrow
                header_cells = cells
    right_populated = [c for c in header_cells if last_t < c <= span_hi]
    header_last = max(header_cells) if header_cells else None
    merge_continues = False
    if schema is not None:
        for c1, r1, c2, r2 in schema.merges:
            if r1 <= (header_row or 1) <= r2 and c1 <= last_t <= c2 and c2 > last_t:
                merge_continues = True
                break
    tokens = {}
    for c, value in header_cells.items():
        tok = _token(value)
        if tok is not None:
            tokens[c] = tok
    b1 = len(right_populated) >= 2 or merge_continues
    b2 = (
        header_last is not None
        and abs(header_last - last_t) <= 2
        and len(right_populated) == 0
        and not merge_continues
    )
    b3 = _sequence_continues(tokens, last_t, col) if tokens else False
    return {
        "B1": b1,
        "B2": b2,
        "B3": b3,
        "header_row": header_row,
        "header_right_n": len(right_populated),
        "header_last_col": header_last,
        "merge_continues": merge_continues,
        "n_tokens": len(tokens),
    }


def _homologue_rows(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    p_key: CellKey | None,
    class_cache: dict,
) -> set[int]:
    sheet, _col, row = key
    rows: set[int] = set()
    for peer_row, _kind in occ.row_peers.get(key, []):
        if peer_row != row:
            rows.add(peer_row)
    for eq_id, slot_index, formula_key in point_slots_for(graph, key):
        for peer in homologous_peers(graph, key, eq_id, slot_index, formula_key, class_cache):
            if peer[0] == sheet and peer[2] != row:
                rows.add(peer[2])
    if p_key is not None:
        node = graph.formulas.get(p_key)
        if node is not None:
            for member in graph.by_eq.get(node.eq_id, []):
                if member[0] == sheet and member[2] != row:
                    rows.add(member[2])
    return rows


def family_hom(
    graph: DependencyGraph,
    key: CellKey,
    extent: ExtentCache,
    occ: OccupancyPeers,
    last_t: int | None,
    p_key: CellKey | None,
    class_cache: dict,
) -> dict[str, Any]:
    _sheet, col, row = key
    rows = _homologue_rows(graph, key, occ, p_key, class_cache)
    n_continue = 0
    n_stop = 0
    n_with_last = 0
    depths: list[int] = []
    for other in rows:
        last_a = extent.last_active.get(other)
        if last_a is None:
            continue
        n_with_last += 1
        if last_a >= col:
            n_continue += 1
            depths.append(last_a - col)
        if last_t is not None and abs(last_a - last_t) <= 1:
            n_stop += 1
    hom1 = n_continue >= HOM1_K
    hom2 = n_with_last >= 2 and (n_stop / n_with_last) >= 0.5 and n_stop >= 2
    hom3 = False
    peer_later = 0
    if p_key is not None:
        node = graph.formulas.get(p_key)
        if node is not None:
            for member in graph.by_eq.get(node.eq_id, []):
                if member[2] != row and member[1] >= col:
                    hom3 = True
                    peer_later += 1
    return {
        "Hom1": hom1,
        "Hom2": hom2,
        "Hom3": hom3,
        "Hom1_grid": {f"k{k}": n_continue >= k for k in CONT_K},
        "n_hom_rows": len(rows),
        "n_hom_continue": n_continue,
        "n_hom_stop": n_stop,
        "n_class_later_rows": peer_later,
        "max_hom_depth": max(depths) if depths else 0,
    }


def _predecessor(
    graph: DependencyGraph, sheet: str, row: int, col: int, last_f: int | None
) -> CellKey | None:
    if last_f is None or last_f >= col:
        return None
    key = (sheet, last_f, row)
    if key in graph.formulas:
        return key
    return None


def family_d(
    graph: DependencyGraph, key: CellKey, p_key: CellKey | None
) -> dict[str, Any]:
    sheet, col, row = key
    d1 = d2 = d3 = d4 = False
    family_n = 0
    n_later = 0
    n_rows = 0
    n_align = 0
    translation_ok = False
    successor_exists = False
    if p_key is not None:
        node = graph.formulas[p_key]
        members = graph.by_eq.get(node.eq_id, [])
        family_n = len(members)
        same_row = {m[1] for m in members if m[0] == sheet and m[2] == row}
        left_neighbor = (p_key[1] - 1) in same_row
        d1 = col == p_key[1] + 1 and left_neighbor
        n_later = sum(1 for m in members if m[1] > p_key[1])
        d2 = n_later >= 1
        by_row: dict[tuple[str, int], int] = {}
        for member in members:
            pair = (member[0], member[2])
            by_row[pair] = max(by_row.get(pair, 0), member[1])
        n_rows = len(by_row)
        if n_rows >= 2:
            n_align = sum(1 for max_c in by_row.values() if abs(max_c - p_key[1]) <= 1)
            d3 = (n_align / n_rows) >= D3_SHARE
        translated = translate_to_target(
            node.formula,
            src_sheet=sheet,
            src_col=p_key[1],
            src_row=row,
            tgt_sheet=sheet,
            tgt_col=col,
            tgt_row=row,
        )
        if translated is not None:
            translation_ok = True
            others = [m for m in graph.by_eq.get(translated["eq_id"], []) if m != p_key]
            successor_exists = bool(others)
            d4 = successor_exists
    return {
        "D1": d1,
        "D2": d2,
        "D3": d3,
        "D4": d4,
        "family_n": family_n,
        "n_later": n_later,
        "n_family_rows": n_rows,
        "n_family_align": n_align,
        "translation_supported": translation_ok,
        "successor_eq_exists": successor_exists,
        "p_col": None if p_key is None else p_key[1],
    }


def family_e(graph: DependencyGraph, key: CellKey, class_cache: dict) -> dict[str, Any]:
    _sheet, col, _row = key
    slots = point_slots_for(graph, key)
    consumer_eqs = {eq_id for eq_id, _slot, _fk in slots}
    n_consumers = len(graph.point_rev.get(key) or [])
    e1 = False
    class_stop = []
    max_consumer_col = None
    for eq_id in consumer_eqs:
        members = graph.by_eq.get(eq_id) or []
        cols = [m[1] for m in members]
        if not cols:
            class_stop.append(False)
            continue
        hi = max(cols)
        max_consumer_col = hi if max_consumer_col is None else max(max_consumer_col, hi)
        if hi > col:
            e1 = True
        class_stop.append(hi <= col + 2)
    e2 = bool(consumer_eqs) and all(class_stop)
    kinds: list[Kind] = []
    seen: set[CellKey] = set()
    for eq_id, slot_index, formula_key in slots:
        for peer in homologous_peers(graph, key, eq_id, slot_index, formula_key, class_cache):
            if peer in seen:
                continue
            seen.add(peer)
            kinds.append(graph.kind(peer))
    n_peers = len(kinds)
    n_active = sum(1 for kind in kinds if kind in ACTIVE)
    n_blank = sum(1 for kind in kinds if kind == "B")
    e3 = n_active >= 2
    e4 = n_peers >= 2 and (n_blank / n_peers) >= E4_BLANK
    return {
        "E1": e1,
        "E2": e2,
        "E3": e3,
        "E4": e4,
        "n_point_consumers": n_consumers,
        "n_consumer_eq": len(consumer_eqs),
        "max_consumer_col": max_consumer_col,
        "n_hom_peers": n_peers,
        "n_hom_active": n_active,
        "n_hom_blank": n_blank,
    }


def family_f(extent: ExtentCache, row: int, last_t: int | None) -> dict[str, Any]:
    windows: dict[str, Any] = {}
    for radius in REGION_WINDOWS:
        lasts = []
        for other in range(max(extent.min_row, row - radius), min(extent.max_row, row + radius) + 1):
            last_a = extent.last_active.get(other)
            if last_a is not None:
                lasts.append(last_a)
        n = len(lasts)
        grid = {}
        mode = None
        median = None
        if n:
            counts = Counter(lasts)
            mode = counts.most_common(1)[0][0]
            ordered = sorted(lasts)
            median = ordered[n // 2]
            for share in F1_SHARES:
                for tol in STOP_TOL:
                    hit = sum(1 for val in lasts if abs(val - mode) <= tol)
                    grid[f"p{int(share * 100)}_t{tol}"] = n >= 4 and (hit / n) >= share
        windows[str(radius)] = {
            "n_active_rows": n,
            "mode": mode,
            "median": median,
            "grid": grid,
        }
    rep = windows[str(REP_REGION)]
    f1 = bool(rep["grid"].get("p75_t1"))
    median = rep["median"]
    f2 = bool(last_t is not None and median is not None and median - last_t >= F2_LAG)
    f3 = bool(last_t is not None and rep["mode"] is not None and abs(last_t - rep["mode"]) <= 1)
    return {
        "F1": f1,
        "F2": f2,
        "F3": f3,
        "F1_grid": rep["grid"],
        "region_n": rep["n_active_rows"],
        "region_mode": rep["mode"],
        "region_median": median,
        "windows": {
            str(radius): {
                "n": windows[str(radius)]["n_active_rows"],
                "mode": windows[str(radius)]["mode"],
                "median": windows[str(radius)]["median"],
            }
            for radius in REGION_WINDOWS
        },
    }


def family_g(
    col: int, last_t: int | None, tail: int, max_col: int, resume: bool
) -> dict[str, Any]:
    distance = None if last_t is None else col - last_t
    dist_name = _bin_name(distance) if distance is not None and distance > 0 else None
    tail_name = _bin_name(max(tail, 1))
    flags = {}
    for _lo, _hi, name in DIST_BINS:
        flags[f"G_dist_{name}"] = dist_name == name
        flags[f"G_tail_{name}"] = tail_name == name
    flags["G_first_blank"] = distance == 1
    flags["G_resume"] = resume
    flags["G_to_extent"] = bool(last_t is not None and last_t + tail >= max_col)
    return {
        **flags,
        "distance": distance,
        "tail": tail,
        "dist_bin": dist_name,
        "tail_bin": tail_name,
    }


def conjunctions(flags: dict[str, bool]) -> dict[str, Any]:
    cont = sum(bool(flags.get(name)) for name in ("A3", "B1", "Hom1", "D2", "E1", "F2"))
    term = sum(bool(flags.get(name)) for name in ("A2", "B2", "Hom2", "D3", "E2", "F3"))
    return {
        "Q1": bool(flags["A3"] and flags["B1"]),
        "Q2": bool(flags["A2"] and flags["F1"]),
        "Q3": bool(flags["Hom1"]),
        "Q4": bool(flags["Hom2"]),
        "Q5": bool(flags["D1"] and flags["D2"]),
        "Q6": bool(flags["D3"]),
        "Q7": cont >= 2,
        "Q8": term >= 2,
        "Q9": bool(flags["D4"]),
        "cont_votes": cont,
        "term_votes": term,
    }


def features_for_cell(
    graph: DependencyGraph,
    key: CellKey,
    occ: OccupancyPeers,
    extent: ExtentCache,
    schema: SchemaLayer | None,
    class_cache: dict,
    frozen_c: dict[str, Any],
) -> dict[str, Any]:
    sheet, col, row = key
    last_t = frozen_c.get("last_active_col")
    if last_t is None:
        last_t = extent.last_active.get(row)
    tail = int(frozen_c.get("blank_tail") or 0)
    last_f = extent.last_formula.get(row)
    p_key = _predecessor(graph, sheet, row, col, last_f)
    resume = False
    if last_t is not None:
        grid = graph.occupancy[sheet]
        for c in range(last_t + tail + 1, extent.max_col + 1):
            if grid.kind(c, row) in ACTIVE:
                resume = True
                break
    a = family_a(extent, col, row, last_t)
    b = family_b(schema, col, row, last_t or col, tail, extent.max_col)
    hom = family_hom(graph, key, extent, occ, last_t, p_key, class_cache)
    d = family_d(graph, key, p_key)
    e = family_e(graph, key, class_cache)
    f = family_f(extent, row, last_t)
    g = family_g(col, last_t, tail, extent.max_col, resume)
    flags = {
        "A1": a["A1"],
        "A2": a["A2"],
        "A3": a["A3"],
        "B1": b["B1"],
        "B2": b["B2"],
        "B3": b["B3"],
        "Hom1": hom["Hom1"],
        "Hom2": hom["Hom2"],
        "Hom3": hom["Hom3"],
        "D1": d["D1"],
        "D2": d["D2"],
        "D3": d["D3"],
        "D4": d["D4"],
        "E1": e["E1"],
        "E2": e["E2"],
        "E3": e["E3"],
        "E4": e["E4"],
        "F1": f["F1"],
        "F2": f["F2"],
        "F3": f["F3"],
    }
    for name, val in a["A1_grid"].items():
        flags[f"A1_{name}"] = bool(val)
    for name, val in a["A2_grid"].items():
        flags[f"A2_{name}"] = bool(val)
    for name, val in hom["Hom1_grid"].items():
        flags[f"Hom1_{name}"] = bool(val)
    for name, val in f["F1_grid"].items():
        flags[f"F1_{name}"] = bool(val)
    for name in (
        "G_dist_1",
        "G_dist_2",
        "G_dist_3_4",
        "G_dist_5_8",
        "G_dist_gt8",
        "G_tail_1",
        "G_tail_2",
        "G_tail_3_4",
        "G_tail_5_8",
        "G_tail_gt8",
        "G_first_blank",
        "G_resume",
        "G_to_extent",
    ):
        flags[name] = bool(g[name])
    conj = conjunctions(flags)
    for name, val in conj.items():
        if str(name).startswith("Q"):
            flags[name] = bool(val)
    return {
        "sheet": sheet,
        "col": col,
        "row": row,
        "last_active_col": last_t,
        "last_formula_col": last_f,
        "blank_tail": tail,
        "flags": flags,
        "A": {
            k: a[k]
            for k in ("A1", "A2", "A3", "n_continue_k2_d2", "n_stop_t1", "max_continue_depth")
        },
        "B": {
            k: b[k]
            for k in (
                "B1",
                "B2",
                "B3",
                "header_row",
                "header_right_n",
                "header_last_col",
                "merge_continues",
            )
        },
        "Hom": {
            k: hom[k]
            for k in (
                "Hom1",
                "Hom2",
                "Hom3",
                "n_hom_rows",
                "n_hom_continue",
                "n_hom_stop",
                "max_hom_depth",
            )
        },
        "D": {
            k: d[k]
            for k in (
                "D1",
                "D2",
                "D3",
                "D4",
                "family_n",
                "n_later",
                "translation_supported",
                "successor_eq_exists",
                "p_col",
            )
        },
        "E": {
            k: e[k]
            for k in (
                "E1",
                "E2",
                "E3",
                "E4",
                "n_point_consumers",
                "n_consumer_eq",
                "max_consumer_col",
            )
        },
        "F": {k: f[k] for k in ("F1", "F2", "F3", "region_n", "region_mode", "region_median")},
        "G": {
            k: g[k]
            for k in ("distance", "tail", "dist_bin", "tail_bin", "G_first_blank", "G_resume", "G_to_extent")
        },
        "votes": {"cont": conj["cont_votes"], "term": conj["term_votes"]},
    }


A1_VARIANTS = tuple(f"A1_k{k}_d{d}" for k in CONT_K for d in CONT_DEPTH)
A2_VARIANTS = tuple(f"A2_k{k}_t{t}" for k in CONT_K for t in STOP_TOL)
HOM1_VARIANTS = tuple(f"Hom1_k{k}" for k in CONT_K)
F1_VARIANTS = tuple(f"F1_p{int(s * 100)}_t{t}" for s in F1_SHARES for t in STOP_TOL)
G_FLAGS = (
    "G_dist_1",
    "G_dist_2",
    "G_dist_3_4",
    "G_dist_5_8",
    "G_dist_gt8",
    "G_tail_1",
    "G_tail_2",
    "G_tail_3_4",
    "G_tail_5_8",
    "G_tail_gt8",
    "G_first_blank",
    "G_resume",
    "G_to_extent",
)
CORE_ATOMIC = (
    "A1",
    "A2",
    "A3",
    "B1",
    "B2",
    "B3",
    "Hom1",
    "Hom2",
    "Hom3",
    "D1",
    "D2",
    "D3",
    "D4",
    "E1",
    "E2",
    "E3",
    "E4",
    "F1",
    "F2",
    "F3",
) + G_FLAGS
ATOMIC = CORE_ATOMIC + A1_VARIANTS + A2_VARIANTS + HOM1_VARIANTS + F1_VARIANTS
CONJUNCTIONS = ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9")
