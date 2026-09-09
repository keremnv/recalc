#!/usr/bin/env python3
"""ProgramGroup formation: which ExecutionUnit members share one program.

The spec's hard rule is that region membership never implies one program. A
rectangle, a row, an Edit Plan operation or an ExecutionUnit may hold many
programs, so this module never infers homogeneity from adjacency alone.

Instead it requires a **repetition witness**: a parallel line of the input
workbook that already carries existing formulas at the group's own coordinates,
and whose formulas are mutually reproducible by translation. That is direct
evidence, in this workbook, that one relative program is repeated across exactly
those positions. Gold is never consulted.

A group therefore has to survive five checks:

    1. at least two members
    2. same sheet, collinear along one axis
    3. one Edit Plan operation (generated information, not gold)
    4. uniform input cell kind, so translation never overwrites mixed content
    5. a repetition witness on the nearest qualifying parallel line

Check 5 is the one that does the work. It is also what keeps an over-authorised
Edit Plan from being laundered into a program claim: coordinates the workbook
shows no repetition at simply do not form a group.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import composition_closure as cc
import end_to_end_composition_probe as old
import openpyxl
from librecalc_mcp.domain.formulas import translate_a1_formula, formula_a1_shape

Cell = cc.Cell

# Frozen search window for a repetition witness, in lines either side of the
# group's own line. Small on purpose: a witness far away is weak evidence.
WITNESS_WINDOW = 8
MIN_WITNESS_MEMBERS = 2

# How many distinct parallel lines must independently demonstrate the repetition.
# Held at the smallest justified test. A corroboration requirement was measured
# (see evidence_sweep.json) and rejected: it raises the exact ceiling by only
# 0.904 -> 0.919 while cutting coverage from 43.6% to 36.7% of authorised cells,
# and it does not address the failure that motivated it, which is a homologue
# repeating at a non-unit stride. Keeping the knob out is more honest than
# keeping a knob that was motivated by gold and does not fix its motivation.
MIN_WITNESS_LINES = 1


def canonical(formula: str | None) -> str | None:
    return old.synth_tools._canonical_formula(formula)


def input_formulas(task: str) -> dict[Cell, str]:
    """Every formula the input workbook already contains. No gold."""
    inp, _ = cc.workbook_paths(task)
    wb = openpyxl.load_workbook(inp, data_only=False)
    out: dict[Cell, str] = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    out[(ws.title, c.row, c.column)] = c.value
    wb.close()
    return out


def input_kinds(task: str) -> dict[Cell, str]:
    inp, _ = cc.workbook_paths(task)
    wb = openpyxl.load_workbook(inp, data_only=False)
    out: dict[Cell, str] = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                out[(ws.title, c.row, c.column)] = (
                    "formula" if isinstance(v, str) and v.startswith("=")
                    else "blank" if v is None
                    else "value")
    wb.close()
    return out


def translate(formula: str, src: Cell, dst: Cell) -> str:
    """Calc autofill semantics, as already trusted by the harness."""
    return translate_a1_formula(formula, column_offset=dst[2] - src[2], row_offset=dst[1] - src[1])


def axis_of(members: list[Cell]) -> str | None:
    """ROW when the members share a row and vary by column, COL for the reverse."""
    if len({m[0] for m in members}) != 1:
        return None
    rows, cols = {m[1] for m in members}, {m[2] for m in members}
    if len(rows) == 1 and len(cols) == len(members) > 1:
        return "ROW"
    if len(cols) == 1 and len(rows) == len(members) > 1:
        return "COL"
    return None


def _runs(coords: list[int]) -> list[list[int]]:
    """Maximal contiguous runs within a sorted coordinate list."""
    out: list[list[int]] = []
    for k in coords:
        if out and k == out[-1][-1] + 1:
            out[-1].append(k)
        else:
            out.append([k])
    return out


def witness_line(task: str, members: list[Cell], axis: str,
                 forms: dict[Cell, str], min_lines: int = MIN_WITNESS_LINES) -> dict | None:
    """The nearest parallel line that demonstrably repeats one program.

    The witness must cover the group's *own* coordinates, and only the
    coordinates it actually covers become a group. A line that repeats a program
    across J..N says nothing about C..I, so C..I stay out. That is what stops an
    over-authorised Edit Plan from being laundered into a program claim, and it
    is decided from the input workbook alone.

    Deterministic: nearest line first, then the longest witnessed run, ties
    resolved toward the lower coordinate.
    """
    sheet = members[0][0]
    base = members[0][1] if axis == "ROW" else members[0][2]
    coords = sorted(m[2] if axis == "ROW" else m[1] for m in members)

    def at(line: int, k: int) -> Cell:
        return (sheet, line, k) if axis == "ROW" else (sheet, k, line)

    found: list[dict] = []
    for dist in range(1, WITNESS_WINDOW + 1):
        for line in (base - dist, base + dist):
            if line < 1:
                continue
            present = [k for k in coords if at(line, k) in forms]
            best_here = None
            for run in _runs(present):
                if len(run) < MIN_WITNESS_MEMBERS:
                    continue
                cells = [at(line, k) for k in run]
                anchor = cells[0]
                if not all(canonical(translate(forms[anchor], anchor, c)) == canonical(forms[c])
                           for c in cells[1:]):
                    continue
                cand = {"offset": line - base, "axis": axis, "line": line,
                        "covered_coordinates": run,
                        "cells": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in cells],
                        "anchor": f"{anchor[0]}!{cc.a1(anchor[1], anchor[2])}",
                        "anchor_formula": forms[anchor],
                        "shape": formula_a1_shape(forms[anchor])}
                if best_here is None or len(run) > len(best_here["covered_coordinates"]):
                    best_here = cand
            if best_here is not None:
                found.append(best_here)
    if len(found) < min_lines:
        return None
    # Corroborating lines must agree on which coordinates repeat, otherwise the
    # region is not uniformly one program and the group is refused.
    primary = found[0]
    agree = [w for w in found if set(w["covered_coordinates"]) == set(primary["covered_coordinates"])]
    if len(agree) < min_lines:
        return None
    primary = dict(primary)
    primary["corroborating_lines"] = [w["line"] for w in agree]
    primary["n_corroborating_lines"] = len(agree)
    return primary


def canonical_member(members: list[Cell], axis: str, forms: dict[Cell, str]) -> Cell:
    """Frozen, evaluator-blind: an existing formula homologue first, else leftmost/topmost.

    Never chosen by which cell a model happened to get right before.
    """
    have = sorted(m for m in members if m in forms)
    if have:
        return have[0]
    return sorted(members)[0]


def groups_for(members: list[Cell], by_cell: dict, task: str,
               forms: dict[Cell, str] | None = None,
               kinds: dict[Cell, str] | None = None,
               min_lines: int = MIN_WITNESS_LINES) -> tuple[list[dict], list[dict]]:
    """Partition authorised members into eligible ProgramGroups plus a refusal ledger.

    Members are first bucketed by (sheet, Edit Plan operation, line, input kind),
    which is necessary but never sufficient; each bucket then has to produce a
    repetition witness before it becomes a group.
    """
    forms = input_formulas(task) if forms is None else forms
    kinds = input_kinds(task) if kinds is None else kinds
    buckets: dict[tuple, list[Cell]] = {}
    for m in members:
        op = (by_cell.get(m) or {}).get("operation_id")
        kind = kinds.get(m, "blank")
        buckets.setdefault((m[0], op, "ROW", m[1], kind), []).append(m)
        buckets.setdefault((m[0], op, "COL", m[2], kind), []).append(m)
    groups, refused, claimed = [], [], set()
    for key in sorted(buckets, key=lambda k: (-len(buckets[k]), str(k))):
        sheet, op, axis, line, kind = key
        cand = sorted(c for c in buckets[key] if c not in claimed)
        if len(cand) < 2:
            if len(buckets[key]) >= 2:
                refused.append({"members": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in buckets[key]],
                                "reason": "MEMBERS_ALREADY_IN_ANOTHER_GROUP"})
            continue
        if axis_of(cand) != axis:
            continue
        w = witness_line(task, cand, axis, forms, min_lines)
        if w is None:
            refused.append({"members": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in cand],
                            "axis": axis, "operation_id": op, "input_kind": kind,
                            "reason": "NO_REPETITION_WITNESS_IN_INPUT_WORKBOOK"})
            continue
        covered = set(w["covered_coordinates"])
        witnessed = [c for c in cand if (c[2] if axis == "ROW" else c[1]) in covered]
        outside = [c for c in cand if c not in witnessed]
        if len(witnessed) < 2:
            refused.append({"members": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in cand],
                            "axis": axis, "operation_id": op,
                            "reason": "WITNESS_COVERS_FEWER_THAN_TWO_MEMBERS"})
            continue
        if outside:
            refused.append({"members": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in outside],
                            "axis": axis, "operation_id": op,
                            "reason": "OUTSIDE_WITNESSED_RUN"})
        cand = witnessed
        canon = canonical_member(cand, axis, forms)
        groups.append({
            "members": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in cand],
            "member_cells": [list(c) for c in cand],
            "axis": axis, "operation_id": op, "input_kind": kind,
            "canonical_member": f"{canon[0]}!{cc.a1(canon[1], canon[2])}",
            "canonical_cell": list(canon),
            "canonical_has_input_formula": canon in forms,
            "translation_offsets": {f"{c[0]}!{cc.a1(c[1], c[2])}":
                                    [c[1] - canon[1], c[2] - canon[2]] for c in cand},
            "witness": w,
            "eligibility_status": "TRANSLATION_ELIGIBLE",
        })
        claimed |= set(cand)
    ungrouped = [m for m in members if m not in claimed]
    return groups, refused + [{"members": [f"{c[0]}!{cc.a1(c[1], c[2])}" for c in ungrouped],
                               "reason": "NOT_IN_ANY_PROGRAM_GROUP"}] if ungrouped else refused


def apply_program(canonical_formula: str, group: dict) -> dict:
    """Translate one canonical formula across a group. No model, no repair."""
    canon = tuple(group["canonical_cell"])
    out, failures = {}, {}
    for cell in group["member_cells"]:
        c = tuple(cell)
        addr = f"{c[0]}!{cc.a1(c[1], c[2])}"
        if c == canon:
            out[addr] = canonical_formula
            continue
        try:
            out[addr] = translate(canonical_formula, canon, c)
        except Exception as exc:
            failures[addr] = f"TRANSLATION_FAILURE: {type(exc).__name__}: {exc}"
    return {"formulas": out, "failures": failures}
