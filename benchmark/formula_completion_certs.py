"""Gold-blind mechanically certified formula completion.

Uses existing A1 translation and conservative relative fingerprints. Golden
workbooks are never opened here. Style, labels, ranking, and business
semantics are not consulted.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "benchmark/sweagent/formula_index/lib"

import sys

sys.path.insert(0, str(LIB))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address, formula_text, relative_fingerprint  # noqa: E402
from librecalc_mcp.domain.formulas import translate_a1_formula  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

RULES = ("LR", "UD", "CROSS", "K2", "K3", "K4")
K_THRESHOLDS = (2, 3, 4)
DEFINITIONS = {
    "eligible_source": (
        "Same-sheet formula whose relative fingerprint is not opaque and whose "
        "translation to the target stays supported (non-opaque) and in-bounds."
    ),
    "blank": "None or whitespace-only. Values and formulas are occupied.",
    "LR": (
        "Nearest occupied cell to the left and to the right on the same row. "
        "Skip empty cells only. The first occupied cell on each side must be "
        "an eligible source. Both translations to T must produce the same "
        "canonical fingerprint. Distance is |Δcol|. Do not skip a value or an "
        "ineligible formula to reach a further formula."
    ),
    "UD": (
        "Same as LR on the column axis: nearest occupied cell above and below. "
        "Distance is |Δrow|."
    ),
    "CROSS": (
        "An LR certificate and a UD certificate exist at T and imply the exact "
        "same canonical target formula."
    ),
    "K_peer": (
        "Axis peer = every eligible formula on the same row or same column as T "
        "(same sheet). Blanks and values between peers and T are allowed. "
        "Translate each peer independently. Emit Kk when exactly one translated "
        "fingerprint is supported by ≥k peers. If two or more fingerprints each "
        "have ≥k peers, record a conflict and emit no Kk certificate. "
        "Serialized K records keep counts, unique source eq_ids, distance bounds, "
        "and a 4-source sample; the rule itself still uses every independent peer."
    ),
    "agreement": (
        "Canonical relative fingerprint at T, not raw text. Opaque translations "
        "cannot certify."
    ),
    "same_sheet_only": True,
    "golden_in_generation": False,
}


@dataclass(frozen=True)
class Source:
    sheet: str
    col: int
    row: int
    address: str
    formula: str
    fingerprint: str
    eq_id: str
    distance: int
    axis: str


@dataclass
class Certificate:
    rule: str
    sheet: str
    col: int
    row: int
    address: str
    candidate: str
    candidate_fingerprint: str
    candidate_eq_id: str
    agreeing_sources: int
    sources: list[Source]
    same_equivalence_class: bool
    axes: list[str]
    same_sheet: bool
    opaque_involvement: str
    adjacent: bool
    max_distance: int
    min_distance: int

    def as_json(self) -> dict[str, Any]:
        keep_full = self.rule in {"LR", "UD", "CROSS"} or len(self.sources) <= 6
        sources: list[dict[str, Any]] = []
        sample_n = len(self.sources) if keep_full else min(4, len(self.sources))
        for source in self.sources[:sample_n]:
            item = {
                "sheet": source.sheet,
                "address": source.address,
                "col": source.col,
                "row": source.row,
                "eq_id": source.eq_id,
                "distance": source.distance,
                "axis": source.axis,
            }
            if keep_full:
                item["formula"] = source.formula
                item["fingerprint"] = source.fingerprint
            sources.append(item)
        return {
            "rule": self.rule,
            "sheet": self.sheet,
            "col": self.col,
            "row": self.row,
            "address": self.address,
            "target": f"{self.sheet}!{self.address}",
            "candidate": self.candidate,
            "candidate_fingerprint": self.candidate_fingerprint,
            "candidate_eq_id": self.candidate_eq_id,
            "agreeing_sources": self.agreeing_sources,
            "sources": sources,
            "source_eq_ids": sorted({source.eq_id for source in self.sources}),
            "same_equivalence_class": self.same_equivalence_class,
            "axes": self.axes,
            "same_sheet": self.same_sheet,
            "opaque_involvement": self.opaque_involvement,
            "adjacent": self.adjacent,
            "max_distance": self.max_distance,
            "min_distance": self.min_distance,
        }


@dataclass
class Conflict:
    rule: str
    sheet: str
    col: int
    row: int
    address: str
    fingerprints: list[str]
    source_counts: list[int]


@dataclass
class SheetGrid:
    title: str
    min_col: int
    max_col: int
    min_row: int
    max_row: int
    formulas: dict[tuple[int, int], str]
    occupied: dict[tuple[int, int], str]
    by_row: dict[int, list[tuple[int, str]]]
    by_col: dict[int, list[tuple[int, str]]]
    source_fp: dict[tuple[int, int], Any]

    def kind(self, col: int, row: int) -> str:
        if (col, row) in self.formulas:
            return "formula"
        if (col, row) in self.occupied:
            return "value"
        return "blank"

    def in_bounds(self, col: int, row: int) -> bool:
        return self.min_col <= col <= self.max_col and self.min_row <= row <= self.max_row


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def load_grids(path: Path) -> list[SheetGrid]:
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    grids: list[SheetGrid] = []
    try:
        for sheet in workbook.worksheets:
            formulas: dict[tuple[int, int], str] = {}
            occupied: dict[tuple[int, int], str] = {}
            min_col = min_row = None
            max_col = max_row = None
            for cell in sheet._cells.values():
                col, row = int(cell.column), int(cell.row)
                min_col = col if min_col is None else min(min_col, col)
                max_col = col if max_col is None else max(max_col, col)
                min_row = row if min_row is None else min(min_row, row)
                max_row = row if max_row is None else max(max_row, row)
                text = formula_text(cell.value)
                if text:
                    formulas[(col, row)] = text
                    occupied[(col, row)] = "formula"
                elif not _is_blank(cell.value):
                    occupied[(col, row)] = "value"
            if min_col is None:
                continue
            by_row: dict[int, list[tuple[int, str]]] = defaultdict(list)
            by_col: dict[int, list[tuple[int, str]]] = defaultdict(list)
            source_fp: dict[tuple[int, int], Any] = {}
            for (col, row), text in formulas.items():
                by_row[row].append((col, text))
                by_col[col].append((row, text))
                source_fp[(col, row)] = relative_fingerprint(text, col, row, sheet=sheet.title)
            grids.append(
                SheetGrid(
                    title=sheet.title,
                    min_col=min_col,
                    max_col=max_col,
                    min_row=min_row,
                    max_row=max_row,
                    formulas=formulas,
                    occupied=occupied,
                    by_row=dict(by_row),
                    by_col=dict(by_col),
                    source_fp=source_fp,
                )
            )
    finally:
        workbook.close()
    return grids


def translate_to_target(
    formula: str,
    *,
    src_sheet: str,
    src_col: int,
    src_row: int,
    tgt_sheet: str,
    tgt_col: int,
    tgt_row: int,
    source_fp: Any | None = None,
) -> dict[str, str] | None:
    if src_sheet != tgt_sheet:
        return None
    if source_fp is None:
        source_fp = relative_fingerprint(formula, src_col, src_row, sheet=src_sheet)
    if source_fp.opaque:
        return None
    try:
        translated = translate_a1_formula(
            formula,
            column_offset=tgt_col - src_col,
            row_offset=tgt_row - src_row,
        )
    except ValueError:
        return None
    target_fp = relative_fingerprint(translated, tgt_col, tgt_row, sheet=tgt_sheet)
    if target_fp.opaque:
        return None
    return {
        "formula": translated,
        "fingerprint": target_fp.text,
        "eq_id": target_fp.eq_id,
        "source_fingerprint": source_fp.text,
        "source_eq_id": source_fp.eq_id,
    }


def _walk(
    grid: SheetGrid,
    col: int,
    row: int,
    dcol: int,
    drow: int,
) -> tuple[tuple[int, int], str, int] | None:
    distance = 0
    cursor_col, cursor_row = col, row
    while True:
        cursor_col += dcol
        cursor_row += drow
        distance += 1
        if not grid.in_bounds(cursor_col, cursor_row):
            return None
        kind = grid.kind(cursor_col, cursor_row)
        if kind == "blank":
            continue
        if kind == "value":
            return None
        return (cursor_col, cursor_row), grid.formulas[(cursor_col, cursor_row)], distance


def _source_from_translation(
    *,
    sheet: str,
    col: int,
    row: int,
    formula: str,
    translated: dict[str, str],
    distance: int,
    axis: str,
) -> Source:
    return Source(
        sheet=sheet,
        col=col,
        row=row,
        address=a1_address(col, row),
        formula=formula,
        fingerprint=translated["source_fingerprint"],
        eq_id=translated["source_eq_id"],
        distance=distance,
        axis=axis,
    )


def _certificate(
    rule: str,
    sheet: str,
    col: int,
    row: int,
    translated: dict[str, str],
    sources: list[Source],
) -> Certificate:
    eq_ids = {source.eq_id for source in sources}
    distances = [source.distance for source in sources]
    axes = sorted({source.axis for source in sources})
    return Certificate(
        rule=rule,
        sheet=sheet,
        col=col,
        row=row,
        address=a1_address(col, row),
        candidate=translated["formula"],
        candidate_fingerprint=translated["fingerprint"],
        candidate_eq_id=translated["eq_id"],
        agreeing_sources=len(sources),
        sources=sources,
        same_equivalence_class=len(eq_ids) == 1,
        axes=axes,
        same_sheet=True,
        opaque_involvement="none",
        adjacent=all(distance == 1 for distance in distances),
        max_distance=max(distances),
        min_distance=min(distances),
    )


def _pair_certificate(
    rule: str,
    grid: SheetGrid,
    col: int,
    row: int,
    first: tuple[tuple[int, int], str, int],
    second: tuple[tuple[int, int], str, int],
    axis: str,
) -> Certificate | None:
    (c1, r1), f1, d1 = first
    (c2, r2), f2, d2 = second
    t1 = translate_to_target(
        f1,
        src_sheet=grid.title,
        src_col=c1,
        src_row=r1,
        tgt_sheet=grid.title,
        tgt_col=col,
        tgt_row=row,
        source_fp=grid.source_fp.get((c1, r1)),
    )
    t2 = translate_to_target(
        f2,
        src_sheet=grid.title,
        src_col=c2,
        src_row=r2,
        tgt_sheet=grid.title,
        tgt_col=col,
        tgt_row=row,
        source_fp=grid.source_fp.get((c2, r2)),
    )
    if t1 is None or t2 is None:
        return None
    if t1["fingerprint"] != t2["fingerprint"]:
        return None
    sources = [
        _source_from_translation(
            sheet=grid.title, col=c1, row=r1, formula=f1, translated=t1, distance=d1, axis=axis
        ),
        _source_from_translation(
            sheet=grid.title, col=c2, row=r2, formula=f2, translated=t2, distance=d2, axis=axis
        ),
    ]
    return _certificate(rule, grid.title, col, row, t1, sources)


def lr_certificate(grid: SheetGrid, col: int, row: int) -> Certificate | None:
    left = _walk(grid, col, row, -1, 0)
    right = _walk(grid, col, row, 1, 0)
    if left is None or right is None:
        return None
    return _pair_certificate("LR", grid, col, row, left, right, "horizontal")


def ud_certificate(grid: SheetGrid, col: int, row: int) -> Certificate | None:
    up = _walk(grid, col, row, 0, -1)
    down = _walk(grid, col, row, 0, 1)
    if up is None or down is None:
        return None
    return _pair_certificate("UD", grid, col, row, up, down, "vertical")


def _axis_peers(grid: SheetGrid, col: int, row: int) -> Iterator[tuple[int, int, str, int, str]]:
    for src_col, formula in grid.by_row.get(row, []):
        if src_col != col:
            yield src_col, row, formula, abs(src_col - col), "horizontal"
    for src_row, formula in grid.by_col.get(col, []):
        if src_row != row:
            yield col, src_row, formula, abs(src_row - row), "vertical"


def k_agreements(
    grid: SheetGrid, col: int, row: int
) -> tuple[dict[int, Certificate], list[Conflict]]:
    grouped: dict[str, list[tuple[dict[str, str], Source]]] = defaultdict(list)
    for src_col, src_row, formula, distance, axis in _axis_peers(grid, col, row):
        translated = translate_to_target(
            formula,
            src_sheet=grid.title,
            src_col=src_col,
            src_row=src_row,
            tgt_sheet=grid.title,
            tgt_col=col,
            tgt_row=row,
            source_fp=grid.source_fp.get((src_col, src_row)),
        )
        if translated is None:
            continue
        source = _source_from_translation(
            sheet=grid.title,
            col=src_col,
            row=src_row,
            formula=formula,
            translated=translated,
            distance=distance,
            axis=axis,
        )
        grouped[translated["fingerprint"]].append((translated, source))
    certificates: dict[int, Certificate] = {}
    conflicts: list[Conflict] = []
    for k in K_THRESHOLDS:
        winners = [
            (fingerprint, members)
            for fingerprint, members in grouped.items()
            if len(members) >= k
        ]
        if len(winners) > 1:
            conflicts.append(
                Conflict(
                    rule=f"K{k}",
                    sheet=grid.title,
                    col=col,
                    row=row,
                    address=a1_address(col, row),
                    fingerprints=[item[0] for item in winners],
                    source_counts=[len(item[1]) for item in winners],
                )
            )
            continue
        if len(winners) != 1:
            continue
        _fingerprint, members = winners[0]
        translated, _source = members[0]
        certificates[k] = _certificate(
            f"K{k}",
            grid.title,
            col,
            row,
            translated,
            [item[1] for item in members],
        )
    return certificates, conflicts


def candidate_blanks(grid: SheetGrid) -> set[tuple[int, int]]:
    blanks: set[tuple[int, int]] = set()
    by_row: dict[int, list[int]] = defaultdict(list)
    by_col: dict[int, list[int]] = defaultdict(list)
    for col, row in grid.formulas:
        by_row[row].append(col)
        by_col[col].append(row)
    for row, cols in by_row.items():
        for col in range(min(cols), max(cols) + 1):
            if grid.kind(col, row) == "blank":
                blanks.add((col, row))
    for col, rows in by_col.items():
        for row in range(min(rows), max(rows) + 1):
            if grid.kind(col, row) == "blank":
                blanks.add((col, row))
    return blanks


def certificates_for_grid(grid: SheetGrid) -> dict[str, Any]:
    by_rule: dict[str, list[Certificate]] = {rule: [] for rule in RULES}
    conflicts: list[Conflict] = []
    lr_ud_disagree: list[dict[str, Any]] = []
    for col, row in sorted(candidate_blanks(grid)):
        lr = lr_certificate(grid, col, row)
        ud = ud_certificate(grid, col, row)
        if lr is not None:
            by_rule["LR"].append(lr)
        if ud is not None:
            by_rule["UD"].append(ud)
        if lr is not None and ud is not None:
            if lr.candidate_fingerprint == ud.candidate_fingerprint:
                sources = list(lr.sources) + list(ud.sources)
                by_rule["CROSS"].append(
                    _certificate("CROSS", grid.title, col, row, {
                        "formula": lr.candidate,
                        "fingerprint": lr.candidate_fingerprint,
                        "eq_id": lr.candidate_eq_id,
                    }, sources)
                )
            else:
                lr_ud_disagree.append(
                    {
                        "sheet": grid.title,
                        "address": a1_address(col, row),
                        "lr": lr.candidate,
                        "ud": ud.candidate,
                    }
                )
        k_certs, k_conflicts = k_agreements(grid, col, row)
        for k, cert in k_certs.items():
            by_rule[f"K{k}"].append(cert)
        conflicts.extend(k_conflicts)
    return {
        "certificates": {rule: [item.as_json() for item in by_rule[rule]] for rule in RULES},
        "conflicts": [
            {
                "rule": item.rule,
                "sheet": item.sheet,
                "col": item.col,
                "row": item.row,
                "address": item.address,
                "n_groups": len(item.fingerprints),
                "source_counts": item.source_counts,
            }
            for item in conflicts
        ],
        "lr_ud_disagree": lr_ud_disagree,
    }


def apply_certificates(source: Path, destination: Path, certificates: list[dict[str, Any]]) -> dict[str, int]:
    """Copy the input workbook and write certified formulas into currently blank cells."""
    import shutil

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    empty = {
        "written": 0,
        "skipped_occupied": 0,
        "skipped_missing_sheet": 0,
        "skipped_merged": 0,
    }
    if not certificates:
        return empty
    workbook = openpyxl.load_workbook(destination, data_only=False, read_only=False)
    written = 0
    skipped_occupied = 0
    skipped_missing_sheet = 0
    skipped_merged = 0
    try:
        for cert in certificates:
            title = cert["sheet"]
            if title not in workbook.sheetnames:
                skipped_missing_sheet += 1
                continue
            cell = workbook[title].cell(cert["row"], cert["col"])
            if isinstance(cell, openpyxl.cell.cell.MergedCell):
                skipped_merged += 1
                continue
            if formula_text(cell.value) or not _is_blank(cell.value):
                skipped_occupied += 1
                continue
            cell.value = cert["candidate"]
            written += 1
        workbook.save(destination)
    finally:
        workbook.close()
    return {
        "written": written,
        "skipped_occupied": skipped_occupied,
        "skipped_missing_sheet": skipped_missing_sheet,
        "skipped_merged": skipped_merged,
    }


def certificates_for_workbook(path: Path) -> dict[str, Any]:
    grids = load_grids(path)
    merged: dict[str, Any] = {
        "path": str(path),
        "certificates": {rule: [] for rule in RULES},
        "conflicts": [],
        "lr_ud_disagree": [],
        "sheets": len(grids),
        "formula_cells": 0,
    }
    for grid in grids:
        merged["formula_cells"] += len(grid.formulas)
        payload = certificates_for_grid(grid)
        for rule in RULES:
            merged["certificates"][rule].extend(payload["certificates"][rule])
        merged["conflicts"].extend(payload["conflicts"])
        merged["lr_ud_disagree"].extend(payload["lr_ud_disagree"])
    return merged
