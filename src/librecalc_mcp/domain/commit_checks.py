"""Commit-time checks: what the world reports back when the agent tries to finalise.

These are the world-initiated half of the loop. `calc_compare` answers "what did I change?",
which is self-confirming: it reports the edits the agent intended and made, so it can never
surface an edit the agent did not know to make. The checks here answer the questions the
agent did not ask, computed from the input, the output, and the agent's own declared write
targets.

Gold-blind by construction. Nothing here reads a golden workbook; every finding is derivable
from the two workbooks the agent already has plus the arguments it already sent.

A check only works when it references something the agent did not author. The world's own
independent computations qualify (the continuation enumerator, deleted-row geometry, the
input-to-output error delta). The agent's declared write targets do not -- see
`unrequested_writes`.

Pure functions over cell maps. No backend, no UNO, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .formulas import formula_a1_references, formula_a1_shape
from .grid import (
    A1_RANGE,
    SPREADSHEET_ERROR_TOKEN,
    column_label,
    column_number,
    is_formula,
    matrix_value,
    spreadsheet_error_kind,
)

# A cell map is {(sheet, address): (value, formula)}. `formula` is None for literals.
CellMap = dict[tuple[str, str], tuple[Any, Any]]


@dataclass(frozen=True)
class CommitFinding:
    """One fact about the diff that the agent has not accounted for."""

    check: str
    sheet: str
    address: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "sheet": self.sheet,
            "address": self.address,
            "detail": self.detail,
        }


def cell_map_from_reads(reads: list[tuple[str, str, dict[str, Any]]]) -> CellMap:
    """Build a cell map from backend range reads.

    `reads` is (sheet, cell_range, result) where result carries the "values", "formulas" and
    "errors" matrices the backend returns. Both workbooks in a commit check are read this way,
    through the same engine, so no representation difference between an Excel-authored file and
    a saved one can register as a change -- the trap that dominates offline replay.
    """
    cells: CellMap = {}
    for sheet, cell_range, result in reads:
        match = A1_RANGE.fullmatch(cell_range.strip().upper())
        if match is None:
            continue
        first_column = column_number(match.group(1))
        first_row = int(match.group(2))
        values = result.get("values") or []
        formulas = result.get("formulas") or []
        errors = result.get("errors") or []
        for row_index, row in enumerate(values):
            for column_index, value in enumerate(row):
                formula = matrix_value(formulas, row_index, column_index)
                error = matrix_value(errors, row_index, column_index)
                if error:
                    value = str(error)
                if formula in ("", None) and (
                    value is None or (isinstance(value, str) and not value.strip())
                ):
                    continue
                address = f"{column_label(first_column + column_index)}{first_row + row_index}"
                cells[(sheet, address)] = (value, formula or None)
    return cells


def expand_range(sheet: str, cell_range: str) -> set[tuple[str, str]]:
    """Expand an A1 range into its individual (sheet, address) cells."""
    match = A1_RANGE.fullmatch(cell_range.strip().upper())
    if match is None:
        raise ValueError(f"invalid A1 range: {cell_range}")
    start_column, start_row, end_column, end_row = match.groups()
    first_column = column_number(start_column)
    last_column = column_number(end_column or start_column)
    first_row = int(start_row)
    last_row = int(end_row or start_row)
    if last_column < first_column or last_row < first_row:
        raise ValueError(f"A1 range is inverted: {cell_range}")
    return {
        (sheet, f"{column_label(column)}{row}")
        for column in range(first_column, last_column + 1)
        for row in range(first_row, last_row + 1)
    }


def declared_targets(requests: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """The union of cells the agent itself named as write targets.

    Accepts the request dicts already sent to `calc_write` / `calc_fill_formulas` /
    `calc_program`, so the agent carries no extra burden: its intent is whatever it asked for.
    Unparseable entries are skipped rather than raising -- a malformed request is the agent's
    problem to see in that call's own error, not a reason to fail the commit report.
    """
    targets: set[tuple[str, str]] = set()
    for request in requests:
        if not isinstance(request, dict):
            continue
        sheet = request.get("sheet")
        cell_range = request.get("range") or request.get("cell")
        if not isinstance(sheet, str) or not isinstance(cell_range, str):
            continue
        try:
            targets |= expand_range(sheet, cell_range)
        except ValueError:
            continue
    return targets


def _content(cell: tuple[Any, Any] | None) -> tuple[Any, Any]:
    if cell is None:
        return (None, None)
    return cell


def _is_blank(cell: tuple[Any, Any] | None) -> bool:
    value, formula = _content(cell)
    if formula not in (None, ""):
        return False
    return value is None or (isinstance(value, str) and not value.strip())


def error_kind(cell: tuple[Any, Any] | None) -> str | None:
    """The spreadsheet error a cell currently shows, if any.

    A cached value carries the error an evaluated formula produced (`#REF!`); the formula text
    carries a reference that is already broken. Both count, and neither is the backend `error`
    field that `spreadsheet_error_kind` expects as its second argument.
    """
    value, formula = _content(cell)
    if isinstance(value, str):
        match = SPREADSHEET_ERROR_TOKEN.search(value)
        if match is not None:
            return match.group(0)
    return spreadsheet_error_kind(formula, None)


def changed_cells(before: CellMap, after: CellMap) -> set[tuple[str, str]]:
    """Cells whose stored content differs, comparing formulas where a formula exists."""
    changed: set[tuple[str, str]] = set()
    for key in set(before) | set(after):
        before_value, before_formula = _content(before.get(key))
        after_value, after_formula = _content(after.get(key))
        if before_formula is not None or after_formula is not None:
            if before_formula != after_formula:
                changed.add(key)
            continue
        if before_value != after_value:
            changed.add(key)
    return changed


def unrequested_writes(
    before: CellMap,
    after: CellMap,
    declared: set[tuple[str, str]],
) -> list[CommitFinding]:
    """Cells the agent changed without naming them as a target.

    MEASURED AND REJECTED as the answer to the Template overfill class (2026-08-31). Replayed
    against the three documented Sol overfills -- `05_01` C23/C29, `06_24` G11:G17, `06_08`
    `WorkingCapital_Forecast!B17` -- it returns **zero findings**, because the agent *declared*
    every one of them. The overfill class is not "wrote where it did not say it would"; it is
    "said it would write, and should not have". Declared intent is authored by the same faulty
    reasoning that produced the error, so checking against it is the self-confirming trap that
    `calc_compare` already falls into, moved one step later.

    Retained as a diagnostic for genuinely undeclared mutation (a program op with wider effect
    than its stated range). Do not ship it as the overfill guard.
    """
    findings: list[CommitFinding] = []
    for sheet, address in sorted(changed_cells(before, after) - declared):
        was_blank = _is_blank(before.get((sheet, address)))
        _, formula = _content(after.get((sheet, address)))
        wrote = "formula" if is_formula(formula) else "value"
        origin = "input blank" if was_blank else "populated input cell"
        findings.append(
            CommitFinding(
                check="unrequested_write",
                sheet=sheet,
                address=address,
                detail=f"wrote a {wrote} into a {origin} you did not name as a target",
            )
        )
    return findings


def new_formula_errors(before: CellMap, after: CellMap) -> list[CommitFinding]:
    """Error cells present in the output that were not present in the input.

    Catches an edit that broke the workbook it was repairing -- the self-wipe class, where a
    later step re-applied a structural op from the input path and destroyed earlier work.
    """
    findings: list[CommitFinding] = []
    for key in sorted(set(after)):
        after_error = error_kind(after.get(key))
        if after_error is None:
            continue
        if error_kind(before.get(key)) is not None:
            continue
        sheet, address = key
        findings.append(
            CommitFinding(
                check="new_formula_error",
                sheet=sheet,
                address=address,
                detail=f"output has {after_error} here; the input did not",
            )
        )
    return findings


def unextended_continuations(
    after: CellMap,
    continuations: list[dict[str, Any]],
) -> list[CommitFinding]:
    """Detected right-edge continuations still blank in the output.

    `continuations` is the gold-blind enumerator's own output, so this check adds no new
    heuristic -- it only asks whether the agent acted on what the world already detected.
    """
    findings: list[CommitFinding] = []
    for candidate in continuations:
        sheet = candidate.get("sheet")
        address = candidate.get("address")
        if not isinstance(sheet, str) or not isinstance(address, str):
            continue
        if not _is_blank(after.get((sheet, address))):
            continue
        inferred = candidate.get("formula") or "a continuation of the run to its left"
        findings.append(
            CommitFinding(
                check="unextended_continuation",
                sheet=sheet,
                address=address,
                detail=f"still blank; the run to its left continues as {inferred}",
            )
        )
    return findings


def unrestored_structure(
    after: CellMap,
    geometry: list[dict[str, Any]],
) -> list[CommitFinding]:
    """Deleted-row remnants the agent never restored.

    `geometry` is the existing `deleted_row_geometry` payload. A remnant is unrestored when
    the reported row still holds pure-#REF! formulas in the output.
    """
    findings: list[CommitFinding] = []
    for signal in geometry:
        sheet = signal.get("sheet")
        row_index = signal.get("insert_row_index")
        if not isinstance(sheet, str) or not isinstance(row_index, int):
            continue
        still_broken = [
            address
            for (candidate_sheet, address), (value, formula) in after.items()
            if candidate_sheet == sheet and error_kind((value, formula)) is not None
        ]
        if not still_broken:
            continue
        findings.append(
            CommitFinding(
                check="unrestored_structure",
                sheet=sheet,
                address=f"row {row_index}",
                detail=(
                    f"inspect reported a deleted-row remnant here and {len(still_broken)} "
                    f"error cell(s) remain; insert_row was never applied"
                ),
            )
        )
    return findings


def _is_passing_check(value: Any) -> bool:
    """Whether a value reads as a satisfied tie-out.

    Financial models carry author-built checks that rest at zero or TRUE: balance identities,
    sources-minus-uses, sum-versus-total rows. The convention is the author's, not ours.
    """
    if value is True:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return abs(value) < 1e-6
    if isinstance(value, str):
        return value.strip().upper() in {"OK", "TRUE", "BALANCED"}
    return False


def _looks_like_tie_out(formula: Any) -> bool:
    """Whether a formula is shaped like an author-built identity rather than an empty cell.

    A tie-out asserts that two things agree, so it subtracts or compares. Without this the
    check collapses to "was zero", which in a forecast model matches every unused period cell:
    measured at 0.3% precision across 40 Template/Financial Model outputs.
    """
    if not isinstance(formula, str):
        return False
    body = formula.lstrip("=").upper()
    if not body:
        return False
    return "-" in body or "<>" in body or body.startswith(("ABS(", "IF(", "ROUND("))


def broken_check_cells(before: CellMap, after: CellMap) -> list[CommitFinding]:
    """Author-built tie-outs that passed in the input and fail in the output.

    SCOPED TO REPAIR TASKS (2026-08-31). Rejected on completion tasks and re-admitted on repair:

    - Template / Financial Model: **0.2%** precision over 40 outputs. In a workbook being filled
      in, most near-zero cells mean "not computed yet" and a correct answer turns them non-zero,
      so the check flags right answers. Narrowing to identity-shaped formulas cut volume 4x while
      precision fell 0.3% -> 0.2%, removing signal and noise together.
    - Debugging, frontier output (Sol): **0 findings**.
    - Debugging, cheap output (K2.7, 17 outputs): **145 findings at 100%**.

    So it is worthless where the task is to complete a workbook, silent where the model repairs
    one competently, and exact where a weak model damages one. Ship it for Debugging only.
    """
    findings: list[CommitFinding] = []
    for key, (before_value, before_formula) in sorted(before.items()):
        if before_formula is None:
            continue
        after_cell = after.get(key)
        if after_cell is None:
            continue
        after_value, after_formula = after_cell
        if after_formula != before_formula:
            continue
        if not _looks_like_tie_out(before_formula):
            continue
        if not _is_passing_check(before_value):
            continue
        if _is_passing_check(after_value):
            continue
        sheet, address = key
        findings.append(
            CommitFinding(
                check="broken_check_cell",
                sheet=sheet,
                address=address,
                detail=(
                    f"this cell's own formula was satisfied before your edit "
                    f"({before_value!r}) and now reads {after_value!r}"
                ),
            )
        )
    return findings


def referential_integrity(before: CellMap, after: CellMap) -> list[CommitFinding]:
    """Formulas that now reference a cell which used to hold something and no longer does.

    This is the cascade mechanism itself, caught at its source rather than at the thousands of
    cells downstream of it. Independent of intent: the reference is read out of the formula the
    output actually contains, and whether its target is empty is a fact about the two workbooks.
    Only single-cell references are followed, so a formula over a wide range cannot flood.

    MEASURED AND REJECTED (2026-08-31): **0 findings** on both Sol and K2.7 Debugging output. The
    cascade in this dataset does not run through emptied cells; it runs through a formula that
    still sums an now-empty block and therefore evaluates to zero (`=+SUM(D35:D40)` -> 0, so
    `=+D51/D41` -> #DIV/0!). Widening the check to "referenced cell now evaluates to zero" would
    match every legitimate zero, which is what killed `broken_check_cells` on completion tasks.
    The downstream error is already caught by `new_formula_errors`. Do not revive this.
    """
    findings: list[CommitFinding] = []
    for (sheet, address), (_, formula) in sorted(after.items()):
        if not is_formula(formula):
            continue
        for reference_sheet, start, end in formula_a1_references(formula):
            if end is not None:
                continue
            target_sheet = reference_sheet or sheet
            target = (target_sheet, start.replace("$", ""))
            if not _is_blank(after.get(target)) or _is_blank(before.get(target)):
                continue
            findings.append(
                CommitFinding(
                    check="referential_integrity",
                    sheet=sheet,
                    address=address,
                    detail=(
                        f"references {target_sheet}!{target[1]}, which held a value in the "
                        f"input and is empty in your output"
                    ),
                )
            )
    return findings


def _row_runs(cells: CellMap) -> dict[tuple[str, int], list[tuple[int, str]]]:
    """Group formula cells by sheet and row, as (column number, shape) sorted left to right."""
    rows: dict[tuple[str, int], list[tuple[int, str]]] = {}
    for (sheet, address), (_, formula) in cells.items():
        if not is_formula(formula):
            continue
        match = A1_RANGE.fullmatch(address.upper())
        if match is None:
            continue
        column, row = match.group(1), int(match.group(2))
        try:
            shape = formula_a1_shape(formula)
        except (ValueError, IndexError):
            continue
        rows.setdefault((sheet, row), []).append((column_number(column), shape))
    for entries in rows.values():
        entries.sort()
    return rows


def uniformity_breaks(
    before: CellMap,
    after: CellMap,
    minimum_run: int = 3,
) -> list[CommitFinding]:
    """Cells that broke a uniform horizontal formula run the input already had.

    A row of a financial model is normally one formula translated across periods. Where the input
    carried such a run and the output no longer does, the agent has singled out one period. The
    run is evidence the author created, not something the agent declared, and the shape
    comparison is translation-aware so a correct fill does not register.
    """
    findings: list[CommitFinding] = []
    after_rows = _row_runs(after)
    for (sheet, row), entries in sorted(_row_runs(before).items()):
        after_shapes = dict(after_rows.get((sheet, row), []))
        index = 0
        while index < len(entries):
            shape = entries[index][1]
            end = index
            while (
                end + 1 < len(entries)
                and entries[end + 1][1] == shape
                and entries[end + 1][0] == entries[end][0] + 1
            ):
                end += 1
            if end - index + 1 >= minimum_run:
                for column, _ in entries[index : end + 1]:
                    after_shape = after_shapes.get(column)
                    if after_shape is None or after_shape == shape:
                        continue
                    findings.append(
                        CommitFinding(
                            check="uniformity_break",
                            sheet=sheet,
                            address=f"{column_label(column)}{row}",
                            detail=(
                                f"the input carried one formula across "
                                f"{end - index + 1} columns of this row; your output differs "
                                f"here alone"
                            ),
                        )
                    )
            index = end + 1
    return findings


def _input_regions(before: CellMap) -> dict[str, list[tuple[int, int, set[int]]]]:
    """Row-contiguous blocks per sheet as (first row, last row, populated columns).

    Same blocks the structure observation calls `regions`, rebuilt from the input cell map so
    the check does not depend on what the agent was shown.
    """
    populated: dict[str, dict[int, set[int]]] = {}
    for (sheet, address), cell in before.items():
        if _is_blank(cell):
            continue
        match = A1_RANGE.fullmatch(address.upper())
        if match is None:
            continue
        rows = populated.setdefault(sheet, {})
        rows.setdefault(int(match.group(2)), set()).add(column_number(match.group(1)))
    regions: dict[str, list[tuple[int, int, set[int]]]] = {}
    for sheet, rows in populated.items():
        blocks: list[tuple[int, int, set[int]]] = []
        start: int | None = None
        previous: int | None = None
        for row in sorted(rows):
            if start is None:
                start = row
            elif previous is not None and row != previous + 1:
                columns = set().union(*(rows[r] for r in range(start, previous + 1)))
                blocks.append((start, previous, columns))
                start = row
            previous = row
        if start is not None and previous is not None:
            columns = set().union(*(rows[r] for r in range(start, previous + 1)))
            blocks.append((start, previous, columns))
        regions[sheet] = blocks
    return regions


def region_width_extensions(before: CellMap, after: CellMap) -> list[CommitFinding]:
    """Blanks filled in a column no row of their own block populates.

    MEASURED AND REJECTED (2026-08-31). Built for the 17 Template run-extension failures no
    inspect-time extent can name -- `06_24` fills `G11` under a header reaching `G` while every
    data block stops at `F`. Replayed across 148 stored Template outputs it returns **4586
    findings at 5.6% precision**, firing on 132 of 148 tasks: about 31 a task. Filling a blank in
    a column the block never populated is what a Template completion *is*, and the golden wants
    the cell filled 94% of the time.

    No narrowing survives either. Restricting to columns past the block's right edge keeps the
    legitimate new-period writes; requiring no header above the column suppresses `06_24`, whose
    `G7` is labelled `Total` and is precisely what invited the write. The same geometry is
    correct in the common case and wrong in these 17, and nothing in the input separates them --
    so this class is not detectable from inside the world, and no gate check should claim it is.

    Kept, unwired, so the idea is not reinvented. Do not add it to `commit_gate.evaluate`.
    """
    findings: list[CommitFinding] = []
    regions = _input_regions(before)
    for sheet, address in sorted(changed_cells(before, after)):
        if not _is_blank(before.get((sheet, address))):
            continue
        if _is_blank(after.get((sheet, address))):
            continue
        match = A1_RANGE.fullmatch(address.upper())
        if match is None:
            continue
        column, row = column_number(match.group(1)), int(match.group(2))
        for first_row, last_row, columns in regions.get(sheet, []):
            if not first_row <= row <= last_row:
                continue
            if column in columns:
                break
            span = f"{column_label(min(columns))}:{column_label(max(columns))}"
            findings.append(
                CommitFinding(
                    check="region_width_extension",
                    sheet=sheet,
                    address=address,
                    detail=(
                        f"filled a blank in column {column_label(column)}; the block at rows "
                        f"{first_row}-{last_row} populates only {span}"
                    ),
                )
            )
            break
    return findings


def report(findings: list[CommitFinding]) -> dict[str, Any]:
    """Group findings for the commit-time response."""
    grouped: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        grouped.setdefault(finding.check, []).append(finding.as_dict())
    return {
        "schema": "commit-checks-v1",
        "finding_count": len(findings),
        "checks": grouped,
    }
