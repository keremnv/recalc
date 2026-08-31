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

from .grid import (
    A1_RANGE,
    SPREADSHEET_ERROR_TOKEN,
    column_label,
    column_number,
    is_formula,
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

    MEASURED AND REJECTED (2026-08-31). The reference is sound -- the workbook's own redundancy
    is not authored by the agent -- but it cannot be isolated without the golden. In a template
    or forecast workbook most near-zero cells mean "not computed yet", and filling the model
    *correctly* turns them non-zero, so the check flags right answers: 0.2% precision over 40
    Template/Financial Model outputs. Narrowing to identity-shaped formulas cut volume 4x and
    precision did not move (0.3% -> 0.2%), i.e. it removed signal and noise together. On
    Debugging, where the workbook is already complete, the narrowed form finds **nothing**.

    Retained as the record of a rejected idea. Do not ship it.
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
