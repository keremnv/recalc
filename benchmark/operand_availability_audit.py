#!/usr/bin/env python3
"""Were the gold program's operands actually in front of the model?

Phase D reports that novel synthesis is where the architecture fails, and it
deliberately does not exonerate retrieval: 15 of 16 sessions spent all eight
permitted queries, so "the model could not construct the program" and "the model
was never shown the cells the program needs" are still confounded.

This audit separates them, deterministically and with no model calls. For every
Phase B group it takes the gold canonical formula, extracts its operands, and
asks what the synthesis turn could see of each one. Nothing here is a runtime
mechanism: the gold formula is read, so this is evaluator-side only.

Visibility levels, strongest first:

  CELL_MATERIALIZED    cell:<id> is in the working set, so WORKING_SET_EVIDENCE
                       carries its kind, raw value and display value.
  FORMULA_MATERIALIZED a formula entity for that cell is in the working set, so
                       its address and formula text are visible even though the
                       cell row itself was never materialized.
  REFERENCED_ONLY      the cell is named as the referent of some materialized
                       formula, or lies inside a materialized range rectangle.
                       The model can see that the cell exists and is used; it
                       cannot see what is in it.
  ABSENT               not in the working set in any form.
  NOT_IN_WORKBOOK      no such cell in the compiled spine (blank, off-sheet).

An operand counts as available when it is materialized (either kind). Everything
weaker is charged to retrieval, not to synthesis.
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical_choice_select as sel
import canonical_choice_probe as probe
import composition_closure as cc
import end_to_end_composition_probe as old
import program_group_preflight as pf
import relational_retrieval_probe as relational

from librecalc_mcp.domain.formulas import formula_a1_references

OUT = sel.OUT
AVAILABLE = ("CELL_MATERIALIZED", "FORMULA_MATERIALIZED")
LEVEL_ORDER = ("SHEET_NOT_FOUND", "NOT_IN_WORKBOOK", "ABSENT", "REFERENCED_ONLY",
               "FORMULA_MATERIALIZED", "CELL_MATERIALIZED")


def _conn(task: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{relational.db_path(task)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _sheet_ids(con) -> dict[str, str]:
    return {r["name"]: r["sheet_id"] for r in con.execute("SELECT sheet_id,name FROM sheets")}


def _cell_index(con) -> dict[tuple[str, str], sqlite3.Row]:
    return {(r["sheet_id"], r["address"]): r
            for r in con.execute("SELECT cell_id,sheet_id,address,row_idx,col_idx,kind,raw_value FROM cells")}


def visible_sets(con, working: set[str]) -> tuple[dict[str, str], set[str]]:
    """Per-cell materialization level, and the cells merely named by it."""
    level: dict[str, str] = {}
    for x in working:
        if x.startswith("cell:"):
            level[x] = "CELL_MATERIALIZED"
    fids = sorted(x for x in working if x.startswith("formula:"))
    named: set[str] = set()
    if fids:
        q = ",".join("?" * len(fids))
        for r in con.execute(f"SELECT formula_id,cell_id FROM formulas WHERE formula_id IN ({q})", fids):
            level.setdefault(r["cell_id"], "FORMULA_MATERIALIZED")
        for r in con.execute(f"SELECT referenced_cell_id FROM point_references WHERE formula_id IN ({q})", fids):
            named.add(r["referenced_cell_id"])
        rects = list(con.execute(
            f"SELECT r.sheet_id,r.r1,r.c1,r.r2,r.c2 FROM range_references rr "
            f"JOIN ranges r ON r.range_id=rr.range_id WHERE rr.formula_id IN ({q})", fids))
    else:
        rects = []
    # Every id in the spine carries its own kind prefix, range_id included, so
    # the working-set id is the primary key -- stripping it matches nothing.
    rids = sorted(x for x in working if x.startswith("range:"))
    if rids:
        q = ",".join("?" * len(rids))
        rects += list(con.execute(f"SELECT sheet_id,r1,c1,r2,c2 FROM ranges WHERE range_id IN ({q})", rids))
    for rect in rects:
        for r in con.execute(
                "SELECT cell_id FROM cells WHERE sheet_id=? AND row_idx BETWEEN ? AND ? AND col_idx BETWEEN ? AND ?",
                (rect["sheet_id"], rect["r1"], rect["r2"], rect["c1"], rect["c2"])):
            named.add(r["cell_id"])
    return level, named


def operands(formula: str, home_sheet: str) -> list[dict]:
    """Gold operands, points and ranges kept apart. Lexical, like the spine's own
    reference extraction -- named ranges and structured references are omitted
    there too, so this stays consistent with what the workbook compiler saw."""
    out = []
    for sheet, start, end in formula_a1_references(formula):
        out.append({"sheet": sheet or home_sheet, "start": start, "end": end,
                    "kind": "RANGE" if end else "POINT"})
    return out


def audit_unit(unit: dict, session: dict, gold: dict) -> dict:
    task = unit["task"]
    canon = tuple(unit["canonical_cell"])
    formula = gold.get(canon)
    row = {"task": task, "canonical_member": unit["canonical_member"],
           "availability_class": unit["availability_class"],
           "gold_canonical_formula": formula}
    if not formula:
        row["status"] = "CANONICAL_NOT_IN_GOLD_EDIT_SET"
        return row
    con = _conn(task)
    try:
        working = set(session["working_set_ids"])
        boot = set((session.get("bootstrap") or {}).get("bootstrap_entity_ids") or [])
        level, named = visible_sets(con, working)
        sheets = _sheet_ids(con)
        cells = _cell_index(con)
        rows = []
        for op in operands(formula, canon[0]):
            sid = sheets.get(op["sheet"])
            addr = f"{op['start']}:{op['end']}" if op["end"] else op["start"]
            rec = {"reference": (f"{op['sheet']}!{addr}"), "kind": op["kind"],
                   "sheet_resolved": sid is not None}
            targets = []
            if sid is None:
                rec["level"] = "SHEET_NOT_FOUND"
            elif op["kind"] == "POINT":
                c = cells.get((sid, op["start"]))
                targets = [c["cell_id"]] if c else []
                rec["level"] = ("NOT_IN_WORKBOOK" if not c else
                                level.get(c["cell_id"]) or
                                ("REFERENCED_ONLY" if c["cell_id"] in named else "ABSENT"))
            else:
                a, b = cells.get((sid, op["start"])), cells.get((sid, op["end"]))
                if not a or not b:
                    rec["level"] = "NOT_IN_WORKBOOK"
                else:
                    inside = [r["cell_id"] for r in con.execute(
                        "SELECT cell_id FROM cells WHERE sheet_id=? AND row_idx BETWEEN ? AND ? "
                        "AND col_idx BETWEEN ? AND ?",
                        (sid, min(a["row_idx"], b["row_idx"]), max(a["row_idx"], b["row_idx"]),
                         min(a["col_idx"], b["col_idx"]), max(a["col_idx"], b["col_idx"])))]
                    targets = inside
                    seen = sum(1 for x in inside if level.get(x) in AVAILABLE)
                    rec["cells_in_range"] = len(inside)
                    rec["cells_materialized"] = seen
                    rec["level"] = ("CELL_MATERIALIZED" if inside and seen == len(inside) else
                                    "REFERENCED_ONLY" if seen or any(x in named for x in inside) else
                                    "ABSENT")
            rec["from_bootstrap"] = any(x in boot for x in targets)
            rows.append(rec)
        levels = [r["level"] for r in rows]
        row.update({
            "status": "AUDITED",
            "n_operands": len(rows),
            "n_available": sum(1 for l in levels if l in AVAILABLE),
            "n_referenced_only": levels.count("REFERENCED_ONLY"),
            "n_absent": levels.count("ABSENT"),
            "n_not_in_workbook": levels.count("NOT_IN_WORKBOOK") + levels.count("SHEET_NOT_FOUND"),
            "operands": rows,
            "working_set_size": len(working),
            "retrieval_turns": len(session.get("calls", [])),
            "sql_calls": len([c for c in session.get("calls", []) if c.get("sql")]),
            # A turn spent on a malformed action or a timed-out query is a turn
            # the session did not get to use for retrieval.
            "retrieval_turn_status": dict(sorted(Counter(
                (c.get("result") or {}).get("status") or c.get("failure_class")
                or ("FINAL" if c.get("final") else "NO_RESULT")
                for c in session.get("calls", [])).items())),
            # A session that declared itself finished with an operand still
            # missing stopped asking; one that hit the wall ran out of asks.
            "retrieval_declared_final": any(c.get("final") for c in session.get("calls", [])),
            "session_resource_limited": bool(session.get("session_resource_limited")),
            "verdict": ("ALL_OPERANDS_AVAILABLE" if rows and all(l in AVAILABLE for l in levels)
                        else "NO_OPERANDS_AVAILABLE" if not any(l in AVAILABLE for l in levels)
                        else "PARTIAL_OPERANDS_AVAILABLE"),
        })
        # The split this audit exists for. A wrong program written with every
        # operand on the table is the model's; a wrong program written without
        # one is the context's, whatever else is also true of it.
        row["attribution"] = ("PROGRAM_CONSTRUCTION_FAILURE"
                              if all(l in AVAILABLE for l in levels)
                              else "CONTEXT_DELIVERY_FAILURE")
        row["weakest_operand_level"] = min(
            levels, key=lambda l: LEVEL_ORDER.index(l) if l in LEVEL_ORDER else 0)
        return row
    finally:
        con.close()


def run() -> dict:
    units = old.load(OUT / "units.json")["units"]
    scores = {(r["task"], r["canonical_member"]): r
              for r in old.load(OUT / "formula_scores.json")["units"]}
    gold: dict[str, dict] = {}
    rows = []
    for u in units:
        gold.setdefault(u["task"], pf.gold_map(u["task"]))
        name = f"{u['task']}__{u['canonical_cell_id'].replace(':', '_')}.json"
        path = next((d / name for d in probe.SESSION_DIRS if (d / name).exists()), None)
        if path is None:
            rows.append({"task": u["task"], "canonical_member": u["canonical_member"],
                         "status": "SESSION_NOT_FOUND"})
            continue
        r = audit_unit(u, old.load(path), gold[u["task"]])
        s = scores[(u["task"], u["canonical_member"])]
        r["session"] = path.parent.parent.name
        r["correct"] = bool(s["A0_canonical_exact"] or s["A1_canonical_exact"])
        r["A0_canonical_exact"] = s["A0_canonical_exact"]
        r["A1_canonical_exact"] = s["A1_canonical_exact"]
        r["A0_formula"] = s["A0_formula"]
        r["A1_formula"] = s["A1_formula"]
        r["A1_outcome"] = s["A1_outcome"]
        rows.append(r)
    audited = [r for r in rows if r.get("status") == "AUDITED"]
    by = {}
    for cls in sorted({r["availability_class"] for r in audited}):
        g = [r for r in audited if r["availability_class"] == cls]
        by[cls] = {"groups": len(g),
                   "all_operands_available": sum(1 for r in g if r["verdict"] == "ALL_OPERANDS_AVAILABLE"),
                   "partial": sum(1 for r in g if r["verdict"] == "PARTIAL_OPERANDS_AVAILABLE"),
                   "none": sum(1 for r in g if r["verdict"] == "NO_OPERANDS_AVAILABLE")}
    failures = [r for r in audited if not r["correct"]
                and r["availability_class"] in ("GENUINELY_NOVEL", "RECOVERABLE_SHAPE_ONLY")]
    def _split(rs):
        return {"n": len(rs),
                "PROGRAM_CONSTRUCTION_FAILURE": [
                    f'{r["task"]} {r["canonical_member"]}' for r in rs
                    if r["attribution"] == "PROGRAM_CONSTRUCTION_FAILURE"],
                "CONTEXT_DELIVERY_FAILURE": [
                    f'{r["task"]} {r["canonical_member"]} ({r["weakest_operand_level"]})' for r in rs
                    if r["attribution"] == "CONTEXT_DELIVERY_FAILURE"]}
    wrong = [r for r in audited if not r["correct"]]
    out = {"units": rows, "by_availability_class": by,
           "operands_total": sum(r["n_operands"] for r in audited),
           "operands_available": sum(r["n_available"] for r in audited),
           "nine_failures": {
               "groups": len(failures),
               "all_operands_available": sum(1 for r in failures if r["verdict"] == "ALL_OPERANDS_AVAILABLE"),
               "partial": sum(1 for r in failures if r["verdict"] == "PARTIAL_OPERANDS_AVAILABLE"),
               "none": sum(1 for r in failures if r["verdict"] == "NO_OPERANDS_AVAILABLE"),
               "operands": sum(r["n_operands"] for r in failures),
               "available": sum(r["n_available"] for r in failures),
               "referenced_only": sum(r["n_referenced_only"] for r in failures),
               "absent": sum(r["n_absent"] for r in failures)},
           "attribution": {
               "all_wrong_groups": _split(wrong),
               "novel": _split([r for r in failures if r["availability_class"] == "GENUINELY_NOVEL"]),
               "shape_only": _split([r for r in failures
                                     if r["availability_class"] == "RECOVERABLE_SHAPE_ONLY"]),
               "recoverable_exact_wrong": _split(
                   [r for r in wrong if r["availability_class"] == "RECOVERABLE_EXACT"]),
           },
           "correct_groups": {
               "groups": sum(1 for r in audited if r["correct"]),
               "all_operands_available": sum(1 for r in audited if r["correct"]
                                             and r["verdict"] == "ALL_OPERANDS_AVAILABLE")}}
    old.write(OUT / "operand_availability.json", out)
    return out


if __name__ == "__main__":
    import json
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "units"}, indent=2))
