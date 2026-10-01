#!/usr/bin/env python3
"""Phase A mechanics for the composition-closure probe. No model calls.

Three populations are kept apart on purpose, because conflating them is itself
one of the defects this probe exists to measure:

  E  content edit set      cells whose content differs input -> gold in a way an
                           agent would have to actuate (formula text, literal
                           value, blank/nonblank), edit types kept separate
  F  formula-text edit set the subset of E whose formula text differs
  S  scorer modification   cells the official evaluator treats as modification
                           cells inside answer_position, compared by value

Dependency graphs are built over (sheet, row, col) so the input-side and
gold-side graphs are directly comparable. G_input is the only graph a runtime
could actually consult; G_gold and G_union are evaluator-side diagnosis.
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
import openpyxl

EVAL_DIR = old.ROOT / "benchmark-data/SpreadsheetBench-2/evaluation"
sys.path.insert(0, str(EVAL_DIR))
DATA = old.ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model"

# A range wider than this is recorded as an edge but not expanded cell by cell;
# expanding it would dominate reachability without changing which *edit* cells
# are ancestors in any case we have seen. Flagged in the ledger when it matters.
MAX_RANGE_CELLS = 40000

Cell = tuple[str, int, int]  # (sheet title, row, col), 1-based


def a1(row: int, col: int) -> str:
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return f"{s}{row}"


def col_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + ord(ch) - 64
    return n


@lru_cache(maxsize=None)
def dataset() -> dict[str, dict]:
    return {r["id"]: r for r in json.loads((DATA / "dataset.json").read_text())}


@lru_cache(maxsize=None)
def workbook_paths(task: str) -> tuple[Path, Path]:
    """(input, golden) for a task. Golden files are shared across a project."""
    hits = list((DATA / "spreadsheet").rglob(f"{task}_*input*.xlsx"))
    if not hits:
        raise FileNotFoundError(f"no input workbook for {task}")
    inp = hits[0]
    gold = next(iter(sorted(inp.parent.glob("*golden*.xlsx"))), None)
    if gold is None:
        raise FileNotFoundError(f"no golden workbook beside {inp}")
    return inp, gold


# ---------------------------------------------------------------- populations

def population_E(task: str) -> list[dict]:
    """Content edits, semantic only, with the edit type preserved."""
    out = []
    for c in old.delta_map()[task]["changes"]:
        if not old.is_semantic_change(c):
            continue
        kind = c["change_kind"]
        out.append({"sheet": c["sheet"], "row": c["row"], "col": c["col"],
                    "address": c["address"], "change_kind": kind,
                    "input_kind": c.get("input_kind"), "golden_kind": c.get("golden_kind"),
                    "golden_payload": c.get("golden_payload"), "input_payload": c.get("input_payload"),
                    "edit_type": ("FORMULA_TEXT" if c.get("golden_kind") == "formula" and c.get("input_kind") == "formula"
                                  else "BLANK_TO_FORMULA" if c.get("input_kind") == "blank" and c.get("golden_kind") == "formula"
                                  else "VALUE_TO_FORMULA" if c.get("golden_kind") == "formula"
                                  else "LITERAL_VALUE")})
    return out


def population_F(E: list[dict]) -> list[dict]:
    return [e for e in E if e["golden_kind"] == "formula"]


def population_S(task: str) -> tuple[set[Cell], set[Cell], dict]:
    """Evaluator modification and regression cells, from its own classifier."""
    from evaluation import classify_cells_by_modification, parse_answer_position
    inp, gold = workbook_paths(task)
    wi = openpyxl.load_workbook(inp, data_only=True)
    wg = openpyxl.load_workbook(gold, data_only=True)
    wif = openpyxl.load_workbook(inp, data_only=False)
    wgf = openpyxl.load_workbook(gold, data_only=False)
    mod: set[Cell] = set()
    reg: set[Cell] = set()
    ranges = []
    for scr in parse_answer_position(dataset()[task]["answer_position"]):
        sheet, rng = (scr.split("!", 1) if "!" in scr else (wg.sheetnames[0], scr))
        sheet = sheet.strip("'").strip()
        rng = rng.strip("'").strip()
        ranges.append(f"{sheet}!{rng}")
        try:
            r_cells, m_cells = classify_cells_by_modification(
                wi, wg, sheet, rng, False, False, wb_input_formula=wif, wb_answer_formula=wgf)
        except Exception:
            continue
        for coll, dest in ((r_cells, reg), (m_cells, mod)):
            for addr in coll:
                m = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", str(addr))
                if m:
                    dest.add((sheet, int(m.group(2)), col_index(m.group(1))))
    for wb in (wi, wg, wif, wgf):
        wb.close()
    return mod, reg, {"answer_position_ranges": ranges}


# ------------------------------------------------------------------- graphs

def _expand(sheet: str, r1: int, c1: int, r2: int, c2: int, ledger: list) -> set[Cell]:
    n = (r2 - r1 + 1) * (c2 - c1 + 1)
    if n > MAX_RANGE_CELLS:
        ledger.append({"reason": "RANGE_TOO_LARGE", "sheet": sheet, "cells": n})
        return set()
    return {(sheet, r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)}


def graph_input(task: str) -> tuple[dict[Cell, set[Cell]], list]:
    """Precedent map from the frozen relational spine: cell -> cells it reads."""
    db = sqlite3.connect(old.relational.db_path(task))
    db.row_factory = sqlite3.Row
    sheet_name = {r["sheet_id"]: r["name"] for r in db.execute("SELECT sheet_id,name FROM sheets")}
    cell_rc = {r["cell_id"]: (sheet_name[r["sheet_id"]], r["row_idx"], r["col_idx"])
               for r in db.execute("SELECT cell_id,sheet_id,row_idx,col_idx FROM cells")}
    formula_cell = {r["formula_id"]: r["cell_id"] for r in db.execute("SELECT formula_id,cell_id FROM formulas")}
    ledger: list = []
    pre: dict[Cell, set[Cell]] = defaultdict(set)
    for r in db.execute("SELECT formula_id,referenced_cell_id FROM point_references"):
        u, v = formula_cell.get(r["formula_id"]), r["referenced_cell_id"]
        if u in cell_rc and v in cell_rc:
            pre[cell_rc[u]].add(cell_rc[v])
    rng = {r["range_id"]: (sheet_name[r["sheet_id"]], r["r1"], r["c1"], r["r2"], r["c2"])
           for r in db.execute("SELECT range_id,sheet_id,r1,c1,r2,c2 FROM ranges")}
    for r in db.execute("SELECT formula_id,range_id FROM range_references"):
        u = formula_cell.get(r["formula_id"])
        spec = rng.get(r["range_id"])
        if u in cell_rc and spec:
            pre[cell_rc[u]] |= _expand(*spec, ledger)
    db.close()
    return dict(pre), ledger


def graph_gold(task: str) -> tuple[dict[Cell, set[Cell]], list]:
    """Precedent map parsed from the golden workbook. Evaluator-side only."""
    from integrated_hybrid_synthesis_probe import eval_tools as et
    _, gold = workbook_paths(task)
    wb = openpyxl.load_workbook(gold, data_only=False)
    ledger: list = []
    pre: dict[Cell, set[Cell]] = defaultdict(set)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if not isinstance(v, str) or not v.startswith("="):
                    continue
                try:
                    refs = et._ref_records(v, ws.title, cell.row, cell.column)
                except Exception:
                    ledger.append({"reason": "UNSUPPORTED_FORMULA_REFERENCE", "sheet": ws.title, "address": cell.coordinate})
                    continue
                here = (ws.title, cell.row, cell.column)
                for ref in refs.get("points", []) + refs.get("ranges", []):
                    m1 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", ref.get("start") or "")
                    if not m1:
                        continue
                    r1, c1 = int(m1.group(2)), col_index(m1.group(1))
                    if ref.get("is_range"):
                        m2 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", ref.get("end") or ref["start"])
                        if not m2:
                            continue
                        r2, c2 = int(m2.group(2)), col_index(m2.group(1))
                        pre[here] |= _expand(ref["sheet"], min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2), ledger)
                    else:
                        pre[here].add((ref["sheet"], r1, c1))
    wb.close()
    return dict(pre), ledger


OFFSET_RE = re.compile(r"OFFSET\s*\(", re.I)


def _split_args(text: str, start: int) -> tuple[list[str], int]:
    """Split the argument list of a call whose '(' is at `start`."""
    args, depth, cur, i, quote = [], 0, [], start, None
    while i < len(text):
        ch = text[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch == "(":
            depth += 1
            if depth > 1:
                cur.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(cur).strip())
                return args, i
            cur.append(ch)
        elif ch == "," and depth == 1:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    return args, i


def offset_edges(task: str, values: dict[Cell, object]) -> tuple[dict[Cell, set[Cell]], list]:
    """Edges for the region an OFFSET call actually sweeps.

    Static reference extraction records only OFFSET's anchor and the cells its
    numeric arguments come from, not the block it returns. That break is why the
    08_03 dependency chain looked absent from the input graph. Argument values
    are read from the input workbook's own cached values, so this stays
    input-side and runtime-available.
    """
    import sqlite3
    db = sqlite3.connect(old.relational.db_path(task))
    db.row_factory = sqlite3.Row
    sheet_name = {r["sheet_id"]: r["name"] for r in db.execute("SELECT sheet_id,name FROM sheets")}
    cell_rc = {r["cell_id"]: (sheet_name[r["sheet_id"]], r["row_idx"], r["col_idx"])
               for r in db.execute("SELECT cell_id,sheet_id,row_idx,col_idx FROM cells")}
    edges: dict[Cell, set[Cell]] = defaultdict(set)
    ledger: list = []
    from integrated_hybrid_synthesis_probe import eval_tools as et
    for r in db.execute("SELECT cell_id,formula_text FROM formulas WHERE UPPER(formula_text) LIKE '%OFFSET%'"):
        here = cell_rc.get(r["cell_id"])
        text = r["formula_text"] or ""
        if not here:
            continue
        for m in OFFSET_RE.finditer(text):
            args, _ = _split_args(text, m.end() - 1)
            if len(args) < 1:
                continue
            try:
                refs = et._ref_records("=" + args[0], here[0], here[1], here[2])
            except Exception:
                ledger.append({"reason": "UNSUPPORTED_FORMULA_REFERENCE", "cell": here, "arg": args[0][:40]})
                continue
            pts = refs.get("points", []) + refs.get("ranges", [])
            if not pts:
                continue
            a = pts[0]
            m1 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", a.get("start") or "")
            if not m1:
                continue
            ar, ac = int(m1.group(2)), col_index(m1.group(1))

            def numeric(expr: str, default: int | None) -> int | None:
                expr = expr.strip()
                if not expr:
                    return default
                if re.fullmatch(r"-?\d+", expr):
                    return int(expr)
                try:
                    rr = et._ref_records("=" + expr, here[0], here[1], here[2])
                except Exception:
                    return None
                pp = rr.get("points", [])
                if len(pp) != 1:
                    return None
                mm = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", pp[0].get("start") or "")
                if not mm:
                    return None
                val = values.get((pp[0]["sheet"], int(mm.group(2)), col_index(mm.group(1))))
                return int(val) if isinstance(val, (int, float)) else None

            dr = numeric(args[1] if len(args) > 1 else "", 0)
            dc = numeric(args[2] if len(args) > 2 else "", 0)
            h = numeric(args[3] if len(args) > 3 else "", 1)
            w = numeric(args[4] if len(args) > 4 else "", 1)
            if None in (dr, dc, h, w) or h < 1 or w < 1:
                ledger.append({"reason": "DYNAMIC_OFFSET_UNRESOLVED", "cell": here, "args": [x[:20] for x in args]})
                continue
            r1, c1 = ar + dr, ac + dc
            edges[here] |= _expand(a["sheet"], r1, c1, r1 + h - 1, c1 + w - 1, ledger)
    db.close()
    return dict(edges), ledger


def input_cached_values(task: str) -> dict[Cell, object]:
    inp, _ = workbook_paths(task)
    wb = openpyxl.load_workbook(inp, data_only=True)
    out: dict[Cell, object] = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    out[(ws.title, c.row, c.column)] = c.value
    wb.close()
    return out


def graph_input_plus_offset(task: str) -> tuple[dict[Cell, set[Cell]], list]:
    base, led = graph_input(task)
    extra, led2 = offset_edges(task, input_cached_values(task))
    merged = {k: set(v) for k, v in base.items()}
    for k, v in extra.items():
        merged.setdefault(k, set()).update(v)
    return merged, led + led2


def ancestors_within(t: Cell, pre: dict[Cell, set[Cell]], keep: set[Cell], node_cap: int = 400000) -> set[Cell]:
    """Cells in `keep` reachable backwards from t. Excludes t itself."""
    seen: set[Cell] = set()
    q = deque([t])
    hit: set[Cell] = set()
    while q:
        if len(seen) > node_cap:
            break
        cur = q.popleft()
        for p in pre.get(cur, ()):  # precedents
            if p in seen:
                continue
            seen.add(p)
            if p in keep:
                hit.add(p)
            q.append(p)
    hit.discard(t)
    return hit


def successors(pre: dict[Cell, set[Cell]]) -> dict[Cell, set[Cell]]:
    """Reverse the precedent map once. Rebuilding it per target dominates."""
    succ: dict[Cell, set[Cell]] = defaultdict(set)
    for u, ps in pre.items():
        for p in ps:
            succ[p].add(u)
    return succ


def descendants_within(t: Cell, pre_or_succ: dict[Cell, set[Cell]], keep: set[Cell], is_succ: bool = False) -> set[Cell]:
    """Cells in `keep` that read t, directly or transitively."""
    succ = pre_or_succ if is_succ else successors(pre_or_succ)
    seen: set[Cell] = set()
    q = deque([t])
    hit: set[Cell] = set()
    while q:
        cur = q.popleft()
        for s in succ.get(cur, ()):
            if s in seen:
                continue
            seen.add(s)
            if s in keep:
                hit.add(s)
            q.append(s)
    hit.discard(t)
    return hit
