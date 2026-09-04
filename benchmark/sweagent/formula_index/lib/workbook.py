"""Build and query an unranked formula-equivalence index."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from fingerprint import formula_text, relative_fingerprint
from ranges import format_member_ranges, parse_a1_range

try:
    from xlsx_metadata_repair import install as _install_repair
except ImportError:  # pragma: no cover
    def _install_repair() -> None:
        return None

_install_repair()
import openpyxl  # noqa: E402

_REPAIR_INSTALLED = False


def _ensure_repair() -> None:
    global _REPAIR_INSTALLED
    if _REPAIR_INSTALLED:
        return
    _install_repair()
    _REPAIR_INSTALLED = True


@dataclass
class EquivalenceClass:
    eq_id: str
    fingerprint: str
    opaque: bool
    reason: str | None
    n: int
    exemplar_sheet: str
    exemplar_col: int
    exemplar_row: int
    exemplar_formula: str
    members: dict[str, set[tuple[int, int]]] = field(default_factory=lambda: defaultdict(set))

    @property
    def sheets(self) -> int:
        return len(self.members)

    def member_text(self) -> str:
        return format_member_ranges(self.members)


@dataclass
class WorkbookIndex:
    path: Path
    classes: dict[str, EquivalenceClass]
    at_cell: dict[tuple[str, int, int], str]
    by_row: dict[tuple[str, int], set[str]]
    by_col: dict[tuple[str, int], set[str]]
    formula_cells: int
    opaque_cells: int
    opaque_reasons: dict[str, int]

    def classes_in_range(self, sheet: str, spec: str) -> list[EquivalenceClass]:
        c1, r1, c2, r2 = parse_a1_range(spec)
        ids: list[str] = []
        seen: set[str] = set()
        for row in range(r1, r2 + 1):
            for col in range(c1, c2 + 1):
                eq_id = self.at_cell.get((sheet, col, row))
                if eq_id and eq_id not in seen:
                    seen.add(eq_id)
                    ids.append(eq_id)
        return [self.classes[eq_id] for eq_id in ids]

    def classes_on_axis(
        self, sheet: str, *, row: int | None = None, col: int | None = None
    ) -> list[EquivalenceClass]:
        ids: set[str] = set()
        if row is not None:
            ids |= self.by_row.get((sheet, row), set())
        if col is not None:
            ids |= self.by_col.get((sheet, col), set())
        return [self.classes[eq_id] for eq_id in sorted(ids)]

    def lookup(self, eq_id: str) -> EquivalenceClass | None:
        return self.classes.get(eq_id)

    def nearest_bucket(self, sheet: str, col: int, row: int, eq_id: str) -> str:
        record = self.classes.get(eq_id)
        if record is None:
            return "unrecoverable"
        same = record.members.get(sheet, set())
        other_sheets = [name for name in record.members if name != sheet and record.members[name]]
        has_elsewhere = (len(same) - (1 if (col, row) in same else 0)) > 0 or bool(other_sheets)
        if not has_elsewhere:
            return "unrecoverable"
        adjacent = (
            (col + 1, row) in same
            or (col - 1, row) in same
            or (col, row + 1) in same
            or (col, row - 1) in same
        )
        same_row = any(ocol != col for ocol, orow in same if orow == row)
        same_col = any(orow != row for ocol, orow in same if ocol == col)
        on_sheet = any((c, r) != (col, row) for c, r in same)
        if adjacent:
            return "adjacent"
        if same_row:
            return "same_row_nonadjacent"
        if same_col:
            return "same_column_nonadjacent"
        if on_sheet:
            return "distant_same_sheet"
        return "cross_sheet"


def build_index(path: Path | str) -> WorkbookIndex:
    _ensure_repair()
    path = Path(path)
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    classes: dict[str, EquivalenceClass] = {}
    at_cell: dict[tuple[str, int, int], str] = {}
    by_row: dict[tuple[str, int], set[str]] = defaultdict(set)
    by_col: dict[tuple[str, int], set[str]] = defaultdict(set)
    formula_cells = 0
    opaque_cells = 0
    opaque_reasons: dict[str, int] = defaultdict(int)
    try:
        for sheet in workbook.worksheets:
            for cell in sheet._cells.values():
                text = formula_text(cell.value)
                if text is None:
                    continue
                col, row = int(cell.column), int(cell.row)
                formula_cells += 1
                fp = relative_fingerprint(text, col, row, sheet=sheet.title)
                if fp.opaque:
                    opaque_cells += 1
                    opaque_reasons[fp.reason or "unparsed"] += 1
                record = classes.get(fp.eq_id)
                if record is None:
                    record = EquivalenceClass(
                        eq_id=fp.eq_id,
                        fingerprint=fp.text,
                        opaque=fp.opaque,
                        reason=fp.reason,
                        n=0,
                        exemplar_sheet=sheet.title,
                        exemplar_col=col,
                        exemplar_row=row,
                        exemplar_formula=text,
                    )
                    classes[fp.eq_id] = record
                record.n += 1
                record.members[sheet.title].add((col, row))
                at_cell[(sheet.title, col, row)] = fp.eq_id
                by_row[(sheet.title, row)].add(fp.eq_id)
                by_col[(sheet.title, col)].add(fp.eq_id)
    finally:
        workbook.close()
    return WorkbookIndex(
        path=path,
        classes=classes,
        at_cell=at_cell,
        by_row=dict(by_row),
        by_col=dict(by_col),
        formula_cells=formula_cells,
        opaque_cells=opaque_cells,
        opaque_reasons=dict(opaque_reasons),
    )


def stable_eq_id(fingerprint_text: str) -> str:
    return hashlib.sha1(fingerprint_text.encode("utf-8")).hexdigest()[:10]
