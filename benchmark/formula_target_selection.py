"""Gold-blind formula-occupancy target-selection probe.

Selectors mark blanks that occupy a computation position. They do not propose
formulas. Golden workbooks are not consulted during selection or freeze.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"

import sys

sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address  # noqa: E402
from formula_completion_certs import SheetGrid, load_grids  # noqa: E402

Kind = Literal["F", "O", "V", "B"]
CellKey = tuple[str, int, int]

SLICE_LABEL = "DIAGNOSTIC STRUCTURAL-DIVERSITY SAMPLE"
SLICE_NOT = "NOT POPULATION ESTIMATE"
SLICE_NAME = "fm-target-selection-probe-12"
SLICE_N = 12
STRATUM_SIZE = 3
MIN_COMPONENT = 8
DENSITY_THRESHOLDS = (0.70, 0.80, 0.90)
S3_INTERSECTION_THRESHOLD = 0.80
S6_KS = (2, 3, 4)
S4_MIN_SUPPORT = 2
FEATURE_KEYS = (
    "formula_cells",
    "sheets",
    "n_lr",
    "n_ud",
    "n_k2",
    "n_k2_conflicts",
    "horiz_share",
    "formulas_per_sheet",
    "log_file_size",
    "lr_share",
    "conflict_rate",
)

SELECTOR_DEFINITIONS = {
    "occupancy": (
        "F = supported formula (relative fingerprint not opaque). "
        "O = opaque/unsupported formula. V = non-formula populated value/text. "
        "B = blank (None or whitespace-only). No labels, styles, or semantics."
    ),
    "S1": (
        "1D formula-span interior hole. On a row or column, consider consecutive "
        "non-blank occupants. If two consecutive occupants are both formulas "
        "(F or O) and at least one blank lies strictly between them, every such "
        "blank is selected. Values terminate a span. Sheet used-bounds terminate "
        "a span. Formula equivalence is not required. A cell may qualify on one "
        "or both axes; S1 is the union."
    ),
    "S2": (
        "Bidirectional occupancy hole: the blank satisfies S1 on both the row "
        "axis and the column axis."
    ),
    "S3": (
        "Dense formula-region hole. Formula cells are F∪O. A region is a "
        "4-connected component of formula cells with size ≥ 8. Density is "
        "|component| / |axis-aligned bounding-box cells|. A blank is selected "
        "if it lies strictly inside that bounding box (not on the box edge) and "
        "density ≥ T. T is predeclared at 70%, 80%, and 90%. The 80% threshold "
        "is the frozen representative for S7 intersections. Thresholds are not "
        "tuned against goldens."
    ),
    "S4": (
        "Repeated-row occupancy disagreement. Restrict to columns that contain "
        "at least one formula. Each row becomes a vector in {F,V,B} (O maps to "
        "F). All-blank vectors are dropped. A blank at vector index i is "
        "selected if at least 2 other rows have the identical vector except F "
        "at index i. Support count is the number of those homologous F-rows. "
        "No formula correctness, labels, or goldens."
    ),
    "S5": "Column analogue of S4, using rows that contain at least one formula.",
    "S6": (
        "Repeated-pattern singleton hole. Same homology as S4/S5. Select when "
        "the filled pattern occurs ≥ k times and exactly one row/column has the "
        "blank variant at that relative position. Reported at k≥2, k≥3, k≥4. "
        "Union of row-wise and column-wise singleton holes. No ranking."
    ),
    "S7": (
        "Intersections of independent families. Pairwise: S1∩S4, S1∩S5, "
        "S3_80∩S4, S3_80∩S5, S4∩S5. any2 / any3 count membership among "
        "{S1, S3_80, S4, S5}. S2 and S6 are reported standalone; they are not "
        "extra independent families."
    ),
    "not_used": (
        "Formula-translation agreement, golden locations, official scores, "
        "agent outcomes, styles, labels, and task semantics are not selectors."
    ),
}


@dataclass
class OccupancyGrid:
    title: str
    min_col: int
    max_col: int
    min_row: int
    max_row: int
    cells: dict[tuple[int, int], Kind]

    def kind(self, col: int, row: int) -> Kind:
        return self.cells.get((col, row), "B")


@dataclass
class Hit:
    sheet: str
    col: int
    row: int
    address: str
    meta: dict[str, Any] = field(default_factory=dict)

    def key(self) -> CellKey:
        return (self.sheet, self.col, self.row)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "sheet": self.sheet,
            "col": self.col,
            "row": self.row,
            "address": self.address,
        }
        payload.update(self.meta)
        return payload


def _is_formula(kind: Kind) -> bool:
    return kind in ("F", "O")


def _sig(kind: Kind) -> str:
    if _is_formula(kind):
        return "F"
    return kind


def _hit(sheet: str, col: int, row: int, **meta: Any) -> Hit:
    return Hit(sheet=sheet, col=col, row=row, address=a1_address(col, row), meta=meta)


def occupancy_from_grid(grid: SheetGrid) -> OccupancyGrid:
    cells: dict[tuple[int, int], Kind] = {}
    for (col, row), occupied_kind in grid.occupied.items():
        if occupied_kind == "formula" or (col, row) in grid.formulas:
            fp = grid.source_fp.get((col, row))
            cells[(col, row)] = "O" if fp is not None and fp.opaque else "F"
        else:
            cells[(col, row)] = "V"
    return OccupancyGrid(
        title=grid.title,
        min_col=grid.min_col,
        max_col=grid.max_col,
        min_row=grid.min_row,
        max_row=grid.max_row,
        cells=cells,
    )


def occupancy_from_cells(
    title: str,
    cells: dict[tuple[int, int], Kind],
) -> OccupancyGrid:
    if not cells:
        return OccupancyGrid(title, 1, 1, 1, 1, {})
    cols = [col for col, _ in cells]
    rows = [row for _, row in cells]
    return OccupancyGrid(title, min(cols), max(cols), min(rows), max(rows), dict(cells))


def occupancy_stats(grids: Iterable[OccupancyGrid]) -> dict[str, int]:
    counts = {"F": 0, "O": 0, "V": 0, "B": 0, "sheets": 0}
    for grid in grids:
        counts["sheets"] += 1
        occupied = 0
        for kind in grid.cells.values():
            counts[kind] += 1
            occupied += 1
        area = (grid.max_col - grid.min_col + 1) * (grid.max_row - grid.min_row + 1)
        counts["B"] += max(area - occupied, 0)
    return counts


def _group_occupied(grid: OccupancyGrid) -> tuple[dict[int, list[tuple[int, Kind]]], dict[int, list[tuple[int, Kind]]]]:
    by_row: dict[int, list[tuple[int, Kind]]] = defaultdict(list)
    by_col: dict[int, list[tuple[int, Kind]]] = defaultdict(list)
    for (col, row), kind in grid.cells.items():
        by_row[row].append((col, kind))
        by_col[col].append((row, kind))
    for row in by_row:
        by_row[row].sort()
    for col in by_col:
        by_col[col].sort()
    return by_row, by_col


def select_s1(grid: OccupancyGrid) -> list[Hit]:
    by_row, by_col = _group_occupied(grid)
    found: dict[tuple[int, int], dict[str, Any]] = {}

    def add(col: int, row: int, axis: str, left: int, right: int) -> None:
        item = found.setdefault((col, row), {"axes": [], "horizontal": None, "vertical": None})
        if axis not in item["axes"]:
            item["axes"].append(axis)
        item[axis] = {
            "distance_to_supports": [left, right],
            "span_length": left + right + 1,
        }

    for row, items in by_row.items():
        for index in range(len(items) - 1):
            col1, kind1 = items[index]
            col2, kind2 = items[index + 1]
            if not (_is_formula(kind1) and _is_formula(kind2)):
                continue
            if col2 <= col1 + 1:
                continue
            for col in range(col1 + 1, col2):
                add(col, row, "horizontal", col - col1, col2 - col)
    for col, items in by_col.items():
        for index in range(len(items) - 1):
            row1, kind1 = items[index]
            row2, kind2 = items[index + 1]
            if not (_is_formula(kind1) and _is_formula(kind2)):
                continue
            if row2 <= row1 + 1:
                continue
            for row in range(row1 + 1, row2):
                add(col, row, "vertical", row - row1, row2 - row)
    hits = []
    for (col, row), meta in sorted(found.items()):
        hits.append(
            _hit(
                grid.title,
                col,
                row,
                axes=sorted(meta["axes"]),
                horizontal=meta["horizontal"],
                vertical=meta["vertical"],
            )
        )
    return hits


def select_s2(s1_hits: Iterable[Hit]) -> list[Hit]:
    hits = []
    for hit in s1_hits:
        axes = hit.meta.get("axes") or []
        if "horizontal" in axes and "vertical" in axes:
            hits.append(
                _hit(
                    hit.sheet,
                    hit.col,
                    hit.row,
                    axes=["horizontal", "vertical"],
                    horizontal=hit.meta.get("horizontal"),
                    vertical=hit.meta.get("vertical"),
                )
            )
    return hits


def _components(formula_cells: set[tuple[int, int]]) -> Iterator[list[tuple[int, int]]]:
    seen: set[tuple[int, int]] = set()
    for start in formula_cells:
        if start in seen:
            continue
        stack = [start]
        component: list[tuple[int, int]] = []
        while stack:
            cell = stack.pop()
            if cell in seen:
                continue
            seen.add(cell)
            component.append(cell)
            col, row = cell
            for neighbor in ((col + 1, row), (col - 1, row), (col, row + 1), (col, row - 1)):
                if neighbor in formula_cells and neighbor not in seen:
                    stack.append(neighbor)
        yield component


def select_s3(grid: OccupancyGrid, threshold: float) -> list[Hit]:
    formula_cells = {(col, row) for (col, row), kind in grid.cells.items() if _is_formula(kind)}
    selected: dict[tuple[int, int], dict[str, Any]] = {}
    for component in _components(formula_cells):
        if len(component) < MIN_COMPONENT:
            continue
        cols = [col for col, _ in component]
        rows = [row for _, row in component]
        min_col, max_col = min(cols), max(cols)
        min_row, max_row = min(rows), max(rows)
        width = max_col - min_col + 1
        height = max_row - min_row + 1
        if width < 3 or height < 3:
            continue
        area = width * height
        density = len(component) / area
        if density < threshold:
            continue
        for row in range(min_row + 1, max_row):
            for col in range(min_col + 1, max_col):
                if grid.kind(col, row) != "B":
                    continue
                current = selected.get((col, row))
                if current is None or density > current["density"]:
                    selected[(col, row)] = {
                        "density": round(density, 4),
                        "component_size": len(component),
                        "bbox": [min_col, min_row, max_col, max_row],
                        "threshold": threshold,
                    }
    return [
        _hit(grid.title, col, row, **meta)
        for (col, row), meta in sorted(selected.items())
    ]


def _repeated_axis(
    grid: OccupancyGrid,
    *,
    along_rows: bool,
    min_support: int,
    singleton: bool,
    k: int,
) -> list[Hit]:
    formula_axis: set[int] = set()
    other_axis: set[int] = set()
    for (col, row), kind in grid.cells.items():
        if not _is_formula(kind):
            continue
        if along_rows:
            formula_axis.add(col)
            other_axis.add(row)
        else:
            formula_axis.add(row)
            other_axis.add(col)
    if not formula_axis:
        return []
    axis_ids = sorted(formula_axis)
    vectors: dict[int, tuple[str, ...]] = {}
    for line in sorted(other_axis):
        tokens = []
        for axis_id in axis_ids:
            col, row = (axis_id, line) if along_rows else (line, axis_id)
            tokens.append(_sig(grid.kind(col, row)))
        if all(token == "B" for token in tokens):
            continue
        vectors[line] = tuple(tokens)
    by_vector: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for line, vector in vectors.items():
        by_vector[vector].append(line)
    hits: dict[tuple[int, int], Hit] = {}
    for line, vector in vectors.items():
        for index, token in enumerate(vector):
            if token != "B":
                continue
            filled = vector[:index] + ("F",) + vector[index + 1 :]
            supporters = by_vector.get(filled, [])
            if len(supporters) < min_support:
                continue
            if singleton:
                if len(supporters) < k:
                    continue
                if len(by_vector.get(vector, [])) != 1:
                    continue
            axis_id = axis_ids[index]
            col, row = (axis_id, line) if along_rows else (line, axis_id)
            key = (col, row)
            meta = {
                "axis": "row" if along_rows else "column",
                "support": len(supporters),
                "pattern_length": len(axis_ids),
            }
            if singleton:
                meta["k"] = k
            if key not in hits or len(supporters) > hits[key].meta.get("support", 0):
                hits[key] = _hit(grid.title, col, row, **meta)
    return [hits[key] for key in sorted(hits)]


def select_s4(grid: OccupancyGrid) -> list[Hit]:
    return _repeated_axis(
        grid, along_rows=True, min_support=S4_MIN_SUPPORT, singleton=False, k=0
    )


def select_s5(grid: OccupancyGrid) -> list[Hit]:
    return _repeated_axis(
        grid, along_rows=False, min_support=S4_MIN_SUPPORT, singleton=False, k=0
    )


def select_s6(grid: OccupancyGrid, k: int) -> list[Hit]:
    found: dict[tuple[int, int], Hit] = {}
    for hit in _repeated_axis(
        grid, along_rows=True, min_support=k, singleton=True, k=k
    ) + _repeated_axis(
        grid, along_rows=False, min_support=k, singleton=True, k=k
    ):
        key = (hit.col, hit.row)
        previous = found.get(key)
        if previous is None or hit.meta.get("support", 0) > previous.meta.get("support", 0):
            found[key] = hit
    return [found[key] for key in sorted(found)]


def select_on_grids(grids: list[OccupancyGrid]) -> dict[str, list[Hit]]:
    s1: list[Hit] = []
    s3: dict[float, list[Hit]] = {threshold: [] for threshold in DENSITY_THRESHOLDS}
    s4: list[Hit] = []
    s5: list[Hit] = []
    s6: dict[int, list[Hit]] = {k: [] for k in S6_KS}
    for grid in grids:
        row_s1 = select_s1(grid)
        s1.extend(row_s1)
        for threshold in DENSITY_THRESHOLDS:
            s3[threshold].extend(select_s3(grid, threshold))
        s4.extend(select_s4(grid))
        s5.extend(select_s5(grid))
        for k in S6_KS:
            s6[k].extend(select_s6(grid, k))
    out: dict[str, list[Hit]] = {
        "S1": s1,
        "S2": select_s2(s1),
        "S4": s4,
        "S5": s5,
    }
    for threshold in DENSITY_THRESHOLDS:
        out[f"S3_{int(threshold * 100)}"] = s3[threshold]
    for k in S6_KS:
        out[f"S6_{k}"] = s6[k]
    return out


def _keys(hits: Iterable[Hit]) -> set[CellKey]:
    return {hit.key() for hit in hits}


def intersections(selected: dict[str, list[Hit]]) -> dict[str, list[CellKey]]:
    s1 = _keys(selected["S1"])
    s3 = _keys(selected["S3_80"])
    s4 = _keys(selected["S4"])
    s5 = _keys(selected["S5"])
    families = {"S1": s1, "S3_80": s3, "S4": s4, "S5": s5}
    any2: set[CellKey] = set()
    any3: set[CellKey] = set()
    universe = s1 | s3 | s4 | s5
    for key in universe:
        n = sum(key in family for family in families.values())
        if n >= 2:
            any2.add(key)
        if n >= 3:
            any3.add(key)
    return {
        "S1∩S4": sorted(s1 & s4),
        "S1∩S5": sorted(s1 & s5),
        "S3_80∩S4": sorted(s3 & s4),
        "S3_80∩S5": sorted(s3 & s5),
        "S4∩S5": sorted(s4 & s5),
        "any2": sorted(any2),
        "any3": sorted(any3),
    }


def hits_to_json(hits: list[Hit]) -> list[dict[str, Any]]:
    return [hit.as_dict() for hit in hits]


def key_to_json(key: CellKey) -> dict[str, Any]:
    sheet, col, row = key
    return {"sheet": sheet, "col": col, "row": row, "address": a1_address(col, row)}


def project_family(task_id: str, spreadsheet_path: str) -> str:
    parts = Path(spreadsheet_path).parts
    if len(parts) >= 2:
        return parts[1]
    return task_id.split("_")[0]


def extract_certificate_features(payload: dict[str, Any]) -> dict[str, Any]:
    certs = payload.get("certificates") or {}
    lr = certs.get("LR") or []
    ud = certs.get("UD") or []
    k2 = certs.get("K2") or []
    k2_h = 0
    k2_v = 0
    for item in k2:
        axes = item.get("axes") or []
        if axes == ["horizontal"]:
            k2_h += 1
        elif axes == ["vertical"]:
            k2_v += 1
    n_k2_conflicts = sum(
        1 for item in payload.get("conflicts") or [] if item.get("rule") == "K2"
    )
    n_lr = len(lr)
    n_ud = len(ud)
    n_k2 = len(k2)
    formula_cells = int(payload.get("formula_cells") or 0)
    sheets = int(payload.get("sheets") or 0)
    return {
        "error": payload.get("error"),
        "formula_cells": formula_cells,
        "sheets": sheets,
        "n_lr": n_lr,
        "n_ud": n_ud,
        "n_k2": n_k2,
        "n_k2_conflicts": n_k2_conflicts,
        "k2_horizontal": k2_h,
        "k2_vertical": k2_v,
        "horiz_share": k2_h / n_k2 if n_k2 else 0.0,
        "formulas_per_sheet": formula_cells / sheets if sheets else 0.0,
        "lr_share": n_lr / (n_lr + n_ud) if (n_lr + n_ud) else 0.0,
        "conflict_rate": (
            n_k2_conflicts / (n_k2 + n_k2_conflicts) if (n_k2 + n_k2_conflicts) else 0.0
        ),
        "volume": math.log1p(n_k2),
    }


def attach_file_size(features: dict[str, Any], path: Path) -> dict[str, Any]:
    size = path.stat().st_size if path.is_file() else 0
    features = dict(features)
    features["file_size"] = size
    features["log_file_size"] = math.log1p(size)
    return features


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    mean = statistics.fmean(values)
    if len(values) == 1:
        return mean, 1.0
    std = statistics.pstdev(values)
    return mean, std if std > 0 else 1.0


def standardize(rows: list[dict[str, Any]], keys: tuple[str, ...] = FEATURE_KEYS) -> None:
    stats = {key: _mean_std([float(row[key]) for row in rows]) for key in keys}
    for row in rows:
        z = [(float(row[key]) - stats[key][0]) / stats[key][1] for key in keys]
        row["z"] = z
        row["l2"] = math.sqrt(sum(value * value for value in z))
        row["feature_means"] = {key: stats[key][0] for key in keys}
        row["feature_stds"] = {key: stats[key][1] for key in keys}


def _distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left["z"], right["z"])))


def _tertile_bounds(values: list[float]) -> tuple[float, float]:
    ordered = sorted(values)
    if not ordered:
        return 0.0, 0.0
    def pct(p: float) -> float:
        rank = (p / 100.0) * (len(ordered) - 1)
        low = math.floor(rank)
        high = math.ceil(rank)
        if low == high:
            return float(ordered[low])
        return float(ordered[low] * (high - rank) + ordered[high] * (rank - low))
    return pct(100.0 / 3.0), pct(200.0 / 3.0)


def farthest_point(
    pool: list[dict[str, Any]],
    n: int,
    anchors: list[dict[str, Any]],
    used_families: set[str],
) -> list[dict[str, Any]]:
    remaining = [row for row in pool if row["family"] not in used_families]
    remaining.sort(key=lambda row: row["id"])
    chosen: list[dict[str, Any]] = []
    while len(chosen) < n and remaining:
        refs = anchors + chosen
        if not refs:
            pick = min(remaining, key=lambda row: (-row["l2"], row["id"]))
        else:
            pick = min(
                remaining,
                key=lambda row: (
                    -min(_distance(row, ref) for ref in refs),
                    row["id"],
                ),
            )
        chosen.append(pick)
        remaining = [row for row in remaining if row["family"] != pick["family"]]
    return chosen


def select_probe_slice(rows: list[dict[str, Any]], n: int = SLICE_N) -> list[dict[str, Any]]:
    eligible = [row for row in rows if not row.get("error")]
    if not eligible:
        return []
    standardize(eligible)
    q1, q2 = _tertile_bounds([row["volume"] for row in eligible])
    dense = [row for row in eligible if row["volume"] >= q2]
    sparse = [row for row in eligible if row["volume"] <= q1]
    medium = [row for row in eligible if q1 < row["volume"] < q2]
    # Include boundary ties: if q1==q2, put equals into dense except zeros to sparse.
    if q1 == q2:
        dense = [row for row in eligible if row["volume"] >= q1]
        medium = []
        sparse = [row for row in eligible if row["volume"] < q1]
    used: set[str] = set()
    selected: list[dict[str, Any]] = []

    def take(pool: list[dict[str, Any]], count: int, stratum: str) -> None:
        picks = farthest_point(pool, count, selected, used)
        for pick in picks:
            item = dict(pick)
            item["stratum"] = stratum
            used.add(item["family"])
            selected.append(item)

    take(dense, STRATUM_SIZE, "dense_high_candidate")
    take(medium, STRATUM_SIZE, "medium")
    take(sparse, STRATUM_SIZE, "sparse_low_candidate")
    remaining = [row for row in eligible if row["family"] not in used]
    take(remaining, STRATUM_SIZE, "unusual_extreme")
    missing = n - len(selected)
    if missing > 0:
        leftover = [row for row in eligible if row["family"] not in used]
        take(leftover, missing, "diversity_fill")
    return selected[:n]


def inclusion_reason(row: dict[str, Any]) -> str:
    stratum = row.get("stratum")
    return (
        f"{stratum}; family={row['family']}; volume=log1p(K2)={row['volume']:.3f}; "
        f"K2={row['n_k2']}; LR={row['n_lr']}; UD={row['n_ud']}; "
        f"formulas={row['formula_cells']}; sheets={row['sheets']}; "
        f"K2_conflicts={row['n_k2_conflicts']}; horiz_share={row['horiz_share']:.3f}; "
        f"z-L2={row['l2']:.3f}"
    )
