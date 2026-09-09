#!/usr/bin/env python3
"""Closed-world ProgramCandidates: the programs a ProgramGroup could execute.

Phase C left one stochastic decision standing -- which single program should a
ProgramGroup run? This module builds the choice set for that decision, and it
builds it deterministically from the input workbook. Every candidate originates
in a formula the workbook already contains, translated to the group's canonical
cell by the same translation the harness already trusts. Nothing here consults
gold, ranks candidates, or truncates a set to a top-k.

Four mechanisms of increasing breadth:

    M0  the repetition-witness line(s) that established the group
    M1  every parallel line that covers the group's coordinates and is
        internally translation-consistent across them
    M2  same-sheet runs on the group's axis that overlap its span, without
        requiring full coverage
    M3  every formula anywhere in the workbook that can legally be translated
        to the canonical cell -- a ceiling, not a runtime interface

M0 through M2 are candidate *generation* rules a runtime can afford. M3 exists
to answer one question that no runtime rule can answer on its own: does the
correct program exist in this workbook at all?
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import program_group as pg

Cell = cc.Cell

MECHANISMS = ("M0", "M1", "M2", "M3")

# A run must repeat at least this many times before it is evidence of a program.
# Same constant the ProgramGroup predicate uses; not a new knob.
MIN_RUN = pg.MIN_WITNESS_MEMBERS


def addr(c: Cell) -> str:
    return f"{c[0]}!{cc.a1(c[1], c[2])}"


def _axis_key(cell: Cell, axis: str) -> tuple[int, int]:
    """(line, coordinate) for a cell under the group's axis."""
    return (cell[1], cell[2]) if axis == "ROW" else (cell[2], cell[1])


def _cell_at(sheet: str, line: int, k: int, axis: str) -> Cell:
    return (sheet, line, k) if axis == "ROW" else (sheet, k, line)


def _lines(forms: dict[Cell, str], sheet: str, axis: str) -> dict[int, dict[int, str]]:
    out: dict[int, dict[int, str]] = {}
    for cell, f in forms.items():
        if cell[0] != sheet:
            continue
        line, k = _axis_key(cell, axis)
        out.setdefault(line, {})[k] = f
    return out


def _consistent(sheet: str, line: int, coords: list[int], axis: str,
                row: dict[int, str]) -> bool:
    """Do these positions on this line all instantiate one relative program?"""
    anchor = _cell_at(sheet, line, coords[0], axis)
    src = row[coords[0]]
    for k in coords[1:]:
        c = _cell_at(sheet, line, k, axis)
        try:
            t = pg.translate(src, anchor, c)
        except Exception:
            return False
        if pg.canonical(t) != pg.canonical(row[k]):
            return False
    return True


def _runs_of(coords: list[int]) -> list[list[int]]:
    return pg._runs(sorted(coords))


def _make(source: Cell, canon: Cell, forms: dict[Cell, str], mechanism: str,
          why: str) -> dict | None:
    """One candidate, or None when the source cannot legally reach the canonical cell."""
    src = forms.get(source)
    if not src:
        return None
    try:
        t = pg.translate(src, source, canon)
    except Exception:
        return None
    if not t:
        return None
    return {"source_cell_id": addr(source),
            "source_cell": list(source),
            "source_formula": src,
            "source_fingerprint": pg.formula_a1_shape(src),
            "translated_formula_at_canonical": t,
            "fingerprint": pg.formula_a1_shape(t),
            "mechanism": mechanism,
            "why_retrieved": why}


# --------------------------------------------------------------- mechanisms

def m0(group: dict, forms: dict[Cell, str]) -> list[dict]:
    """The witness line(s) that established this group, and nothing else."""
    w = group.get("witness") or {}
    axis = group["axis"]
    canon = tuple(group["canonical_cell"])
    sheet = canon[0]
    coords = sorted(w.get("covered_coordinates") or [])
    if not coords:
        return []
    out = []
    for line in (w.get("corroborating_lines") or [w.get("line")]):
        if line is None:
            continue
        anchor = _cell_at(sheet, line, coords[0], axis)
        c = _make(anchor, canon, forms, "M0",
                  f"repetition witness on line {line} covering {coords[0]}..{coords[-1]}")
        if c:
            out.append(c)
    return out


def m1(group: dict, forms: dict[Cell, str]) -> list[dict]:
    """Every parallel line covering the group's own coordinates, consistently."""
    axis = group["axis"]
    canon = tuple(group["canonical_cell"])
    sheet = canon[0]
    members = [tuple(c) for c in group["member_cells"]]
    base = _axis_key(members[0], axis)[0]
    coords = sorted(_axis_key(m, axis)[1] for m in members)
    out = []
    for line, row in sorted(_lines(forms, sheet, axis).items()):
        if line == base:
            continue
        if not all(k in row for k in coords):
            continue
        if not _consistent(sheet, line, coords, axis, row):
            continue
        anchor = _cell_at(sheet, line, coords[0], axis)
        c = _make(anchor, canon, forms, "M1",
                  f"parallel line {line} covers every group coordinate consistently")
        if c:
            out.append(c)
    return out


def _consistent_segments(sheet: str, line: int, run: list[int], axis: str,
                         row: dict[int, str]) -> list[list[int]]:
    """Maximal stretches of one program inside a contiguous run of formulas.

    A line often carries two programs side by side. Requiring the whole run to
    be consistent throws such a line away entirely, including the part that is
    perfectly regular, so the run is cut at each break instead -- the same thing
    the ProgramGroup witness does when it keeps only its witnessed run.
    """
    segs, seg = [], [run[0]]
    for k in run[1:]:
        anchor = _cell_at(sheet, line, seg[0], axis)
        cell = _cell_at(sheet, line, k, axis)
        try:
            t = pg.translate(row[seg[0]], anchor, cell)
            ok = pg.canonical(t) == pg.canonical(row[k])
        except Exception:
            ok = False
        if ok:
            seg.append(k)
        else:
            segs.append(seg)
            seg = [k]
    segs.append(seg)
    return segs


def m2(group: dict, forms: dict[Cell, str]) -> list[dict]:
    """Same-sheet runs on the group's axis: the group's own line, and overlapping lines.

    Broader than M1 in three ways, each of them structural. The run need not
    cover every group coordinate; a line carrying two programs contributes the
    regular part rather than nothing; and the group's *own* line is included,
    because a row that already holds the program at other columns is the most
    homologous evidence there is. On that line the overlap test is dropped --
    the group occupies the span, so every existing formula on it necessarily
    sits outside.

    Still purely structural. No business meaning is attached to any row or
    column, and gold is not consulted.
    """
    axis = group["axis"]
    canon = tuple(group["canonical_cell"])
    sheet = canon[0]
    members = [tuple(c) for c in group["member_cells"]]
    base = _axis_key(members[0], axis)[0]
    coords = sorted(_axis_key(m, axis)[1] for m in members)
    lo, hi = coords[0], coords[-1]
    out = []
    for line, row in sorted(_lines(forms, sheet, axis).items()):
        on_base = line == base
        for run in _runs_of(list(row)):
            if not on_base and (run[-1] < lo or run[0] > hi):
                continue
            for seg in _consistent_segments(sheet, line, run, axis, row):
                if len(seg) < MIN_RUN:
                    continue
                if not on_base and (seg[-1] < lo or seg[0] > hi):
                    continue
                anchor = _cell_at(sheet, line, seg[0], axis)
                why = (f"the group's own line repeats one program across "
                       f"{seg[0]}..{seg[-1]}" if on_base else
                       f"line {line} repeats one program across {seg[0]}..{seg[-1]}, "
                       f"overlapping the group span {lo}..{hi}")
                c = _make(anchor, canon, forms, "M2", why)
                if c:
                    out.append(c)
    return out


def m3(group: dict, forms: dict[Cell, str]) -> list[dict]:
    """Ceiling: every workbook formula that can legally reach the canonical cell.

    Deliberately far too broad to put in a model's context. Its only job is to
    say whether the correct program exists in this workbook at all, so that a
    runtime mechanism's miss can be told apart from genuine novelty.
    """
    canon = tuple(group["canonical_cell"])
    out = []
    for source in sorted(forms):
        c = _make(source, canon, forms, "M3", f"workbook formula at {addr(source)}")
        if c:
            out.append(c)
    return out


GENERATORS = {"M0": m0, "M1": m1, "M2": m2, "M3": m3}


# ------------------------------------------------------------ candidate sets

def dedupe(cands: list[dict]) -> list[dict]:
    """Collapse identical translated formulas, keeping every provenance.

    Ordering is frozen and mechanical: by translated formula text. Candidate ids
    are assigned from that order, so the same group always produces the same
    ids, and no ordering signal leaks about which candidate is better.
    """
    by_text: dict[str, dict] = {}
    for c in cands:
        key = pg.canonical(c["translated_formula_at_canonical"]) or ""
        hit = by_text.get(key)
        if hit is None:
            hit = {"translated_formula_at_canonical": c["translated_formula_at_canonical"],
                   "fingerprint": c["fingerprint"],
                   "mechanisms": [], "provenance": []}
            by_text[key] = hit
        if c["mechanism"] not in hit["mechanisms"]:
            hit["mechanisms"].append(c["mechanism"])
        hit["provenance"].append({"source_cell_id": c["source_cell_id"],
                                  "source_formula": c["source_formula"],
                                  "source_fingerprint": c["source_fingerprint"],
                                  "mechanism": c["mechanism"],
                                  "why_retrieved": c["why_retrieved"]})
    out = []
    for i, key in enumerate(sorted(by_text), start=1):
        c = by_text[key]
        c["candidate_id"] = f"K{i:03d}"
        c["source_cell_id"] = c["provenance"][0]["source_cell_id"]
        c["source_formula_id"] = c["provenance"][0]["source_formula"]
        c["source_fingerprint"] = c["provenance"][0]["source_fingerprint"]
        c["source_relation"] = c["provenance"][0]["why_retrieved"]
        c["n_sources"] = len(c["provenance"])
        out.append(c)
    return out


def candidates(group: dict, forms: dict[Cell, str],
               mechanisms=("M0", "M1", "M2")) -> list[dict]:
    """The frozen candidate set for one group under the named mechanisms."""
    raw = []
    for m in mechanisms:
        raw.extend(GENERATORS[m](group, forms))
    return dedupe(raw)
