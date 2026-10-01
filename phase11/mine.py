#!/usr/bin/env python3
"""Phase-11 corpus miner.

Indexes rep dirs (transcript + run_record + workbooks + scores), parses
transcripts into tool calls, computes deterministic workbook derivations
offline with openpyxl/zipfile only, codes conservative reachability per
candidate, and emits DERIVATION_REACHABILITY_MATRIX.jsonl plus aggregates.

Gold/evaluator data (capability_scores eval_error) is used ONLY to classify
outcomes/failure relevance — never to generate candidate facts.
"""
from __future__ import annotations

import glob
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "phase11"

SOURCES = {
    "representative": "representative_architecture_checkpoint/reps/*",
    "batch": "batch_write_helper_ab/reps/*",
    "inspection": "inspection_efficiency_ab/reps/*",
    "live": "live_transparent_runtime_ab/runs/*/*",
    "token": "token_affordance_discovery/runs/primary/*",
}

SCORE_FILES = [
    "representative_architecture_checkpoint/capability_scores.json",
    "batch_write_helper_ab/capability_scores.json",
    "inspection_efficiency_ab/capability_scores.json",
    "live_transparent_runtime_ab/paired_scores.json",
    "token_affordance_discovery/completion_table.json",
]

ERROR_VALUES = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!",
                "#VALUE!", "#GETTING_DATA", "#SPILL!", "#CALC!", "#FIELD!"}


# ---------------------------------------------------------------- indexing

def task_key(rep: Path, rec: dict) -> str | None:
    """Canonical <Family>_<a>_<b> task key from record or dirname."""
    tid = rec.get("task_id") or ""
    m = re.match(r"([A-Za-z]+)[:_](\d+)[_:](\d+)", tid)
    if m:
        return f"{m.group(1)}_{m.group(2)}_{m.group(3)}"
    m = re.match(r"([A-Za-z]+)_(\d+)_(\d+)", rep.name)
    if m:
        return f"{m.group(1)}_{m.group(2)}_{m.group(3)}"
    m = re.search(r"(\d+)_([A-Za-z]+)_(\d+)_(\d+)_", rep.name)
    if m:
        return f"{m.group(2)}_{m.group(3)}_{m.group(4)}"
    return None


def find_workbooks(rep: Path, source: str, rec: dict):
    """Locate (input, output, output_shared) workbooks for a rep dir.

    Priority: rep-local files, then rep/work/, then the experiment's
    work/<task>/ tree. Shared work-tree outputs (one per task, multiple
    runs) are flagged output_shared=True.
    """
    key = task_key(rep, rec)
    exp = {"representative": "representative_architecture_checkpoint",
           "batch": "batch_write_helper_ab",
           "inspection": "inspection_efficiency_ab",
           "live": "live_transparent_runtime_ab",
           "token": "token_affordance_discovery"}[source]
    inp, out, shared = None, False, False
    if (rep / "input.xlsx").is_file():
        inp = rep / "input.xlsx"
    elif (rep / "work" / "input.xlsx").is_file():
        inp = rep / "work" / "input.xlsx"
    if (rep / "output.xlsx").is_file():
        out = rep / "output.xlsx"
    elif (rep / "work" / "output.xlsx").is_file():
        out = rep / "work" / "output.xlsx"
    if key and (inp is None or out is None):
        wd = ROOT / exp / "work" / key
        if inp is None and (wd / "input.xlsx").is_file():
            inp = wd / "input.xlsx"
        if out is None and (wd / "output.xlsx").is_file():
            out = wd / "output.xlsx"
            shared = True
    return inp, out, shared


def load_scores() -> dict:
    """Map (task_id, arm) -> score record (run_id match where available)."""
    out: dict = {}
    for rel in SCORE_FILES:
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            data = json.load(open(p))
        except Exception:
            continue
        rows = data if isinstance(data, list) else data.get("rows", data.get("scores", []))
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            tid = r.get("task_id")
            arm = r.get("arm")
            if tid:
                out[(tid, arm, r.get("run_id"))] = r
                out.setdefault((tid, arm, None), r)
    return out


def index_reps() -> list[dict]:
    reps = []
    for source, pat in SOURCES.items():
        for rep in sorted(glob.glob(str(ROOT / pat))):
            rep = Path(rep)
            if not rep.is_dir():
                continue
            t_full = rep / "transcript_full.jsonl"
            t_short = rep / "transcript.jsonl"
            transcript = t_full if t_full.is_file() else (t_short if t_short.is_file() else None)
            if transcript is None:
                continue
            rec = {}
            if (rep / "run_record.json").is_file():
                try:
                    rec = json.load(open(rep / "run_record.json"))
                except Exception:
                    rec = {}
            inp, outp, shared = find_workbooks(rep, source, rec)
            reps.append({"source": source, "rep": str(rep.relative_to(ROOT)),
                         "transcript": str(transcript.relative_to(ROOT)),
                         "full": transcript.name == "transcript_full.jsonl",
                         "record": rec, "input": str(inp) if inp else None,
                         "output": str(outp) if outp else None,
                         "output_shared": shared})
    return reps


# ------------------------------------------------------- transcript parsing

def parse_transcript(path: Path) -> list[dict]:
    """Ordered tool calls: [{idx, tool, args, command, observation}]."""
    rows = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    calls: list[dict] = []
    pending: dict | None = None
    idx = 0
    for r in rows:
        if r.get("role") == "assistant" and r.get("tool_calls"):
            for tc in r["tool_calls"]:
                fn = (tc.get("function") or {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {"_raw": fn.get("arguments")}
                pending = {"idx": idx, "tool": fn.get("name"),
                           "args": args, "command": args.get("command", ""),
                           "observation": ""}
                idx += 1
        elif r.get("role") == "user" and pending is not None:
            pending["observation"] = r.get("content") or ""
            calls.append(pending)
            pending = None
    if pending is not None:
        calls.append(pending)
    return calls


PY_HINTS = ("python", "openpyxl", ".py", "import ")


def agent_python(calls: list[dict]) -> list[tuple[int, str]]:
    """Extract (call_idx, python_code) from bash commands."""
    out = []
    for c in calls:
        if c["tool"] != "bash":
            continue
        cmd = c.get("command") or ""
        if not any(h in cmd for h in PY_HINTS):
            continue
        code = cmd
        # heredoc bodies
        for m in re.finditer(r"<<\s*'?(\w+)'?\n(.*?)(\n\1\b)", cmd, re.S):
            code += "\n" + m.group(2)
        out.append((c["idx"], code))
    return out


def mutation_calls(calls: list[dict]) -> list[dict]:
    """Calls that write workbooks: .save(, convert+overwrite, mutation scripts."""
    muts = []
    for c in calls:
        if c["tool"] != "bash":
            continue
        cmd = c.get("command") or ""
        if (".save(" in cmd or "wb.save" in cmd or "workbook.save" in cmd
                or ("convert-to" in cmd and ".xls" in cmd)):
            muts.append(c)
    return muts


def view_calls(calls: list[dict]) -> list[dict]:
    return [c for c in calls if c["tool"] == "view_xlsx"]


# ---------------------------------------------------- workbook derivations

def _tokenizer():
    from openpyxl.formula.tokenizer import Tokenizer
    return Tokenizer


COORD_RE = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)([0-9]+)$")


def _col_to_idx(col: str) -> int:
    n = 0
    for ch in col.upper():
        n = n * 26 + ord(ch) - 64
    return n


def rel_fingerprint(formula: str, row: int, col: int) -> str | None:
    """Normalize formula to relative-offset pattern; None if unparseable."""
    try:
        Tokenizer = _tokenizer()
        toks = Tokenizer(formula).items
    except Exception:
        return None
    parts = []
    for t in toks:
        v = t.value
        if t.type == "OPERAND" and t.subtype in ("RANGE",):
            span = v.split(":")
            norm = []
            for s in span:
                s = s.split("!")[-1]
                m = COORD_RE.match(s)
                if not m:
                    norm.append("R?")
                    continue
                c = _col_to_idx(m.group(2)) - col
                r = int(m.group(4)) - row
                norm.append(f"{'A' if m.group(1) else 'r'}{r:+d}"
                            f"{'A' if m.group(3) else 'c'}{c:+d}")
            parts.append("RANGE(" + ":".join(norm) + ")")
        elif t.type == "OPERAND" and t.subtype == "LOGICAL":
            parts.append("L" + v)
        elif t.type in ("FUNC", "OP", "PAREN", "SEP", "WHITESPACE"):
            parts.append(v if t.type != "WHITESPACE" else " ")
        elif t.type == "OPERAND":
            parts.append("N" if t.subtype == "NUMBER" else "T")
        else:
            parts.append(v)
    return "".join(parts)


def direct_precedents(formula: str) -> list[str]:
    """Owning-cell A1 refs (sheet-qualified where present)."""
    try:
        Tokenizer = _tokenizer()
        toks = Tokenizer(formula).items
    except Exception:
        return []
    refs = []
    for t in toks:
        if t.type == "OPERAND" and t.subtype == "RANGE":
            refs.append(t.value)
    return refs


def load_book(path: str | None, data_only: bool):
    if not path:
        return None
    import openpyxl
    try:
        return openpyxl.load_workbook(path, data_only=data_only,
                                      read_only=True)
    except Exception:
        return None


def derive_workbook(path: str | None) -> dict:
    """Deterministic fact inventory of one workbook state."""
    from openpyxl.utils import get_column_letter
    d: dict = {"ok": False, "formulas": {}, "values": {}, "dtypes": {},
               "families": {}, "merged": {}, "errors": set(),
               "precedents": {}, "dims": {}}
    if not path:
        return d
    wb_f = load_book(path, False)
    wb_v = load_book(path, True)
    if wb_f is None:
        return d
    try:
        for ws in wb_f.worksheets:
            title = ws.title
            merged = getattr(ws, "merged_cells", None)
            if merged is None:
                merged = getattr(ws, "merged_cell_ranges", []) or []
                d["merged"][title] = [str(r) for r in merged]
            else:
                d["merged"][title] = [str(r) for r in merged.ranges]
            d["dims"][title] = (ws.max_row, ws.max_column)
            for r_idx, row in enumerate(ws.iter_rows(), start=1):
                for c_idx, cell in enumerate(row, start=1):
                    coord = f"{title}!{get_column_letter(c_idx)}{r_idx}"
                    v = cell.value
                    if isinstance(v, str) and v.startswith("="):
                        fp = rel_fingerprint(v, cell.row, cell.column)
                        d["formulas"][coord] = {"text": v, "fp": fp,
                                                "row": cell.row,
                                                "col": cell.column}
                        d["precedents"][coord] = direct_precedents(v)
            fams: dict = {}
            for coord, f in d["formulas"].items():
                if f["fp"]:
                    fams.setdefault(f["fp"], []).append(coord)
            d["families"] = fams
    finally:
        wb_f.close()
    if wb_v is not None:
        try:
            for ws in wb_v.worksheets:
                for r_idx, row in enumerate(ws.iter_rows(), start=1):
                    for c_idx, cell in enumerate(row, start=1):
                        coord = f"{ws.title}!{get_column_letter(c_idx)}{r_idx}"
                        d["values"][coord] = cell.value
                        d["dtypes"][coord] = cell.data_type
                        if (isinstance(cell.value, str)
                                and cell.value in ERROR_VALUES):
                            d["errors"].add(coord)
        finally:
            wb_v.close()
    d["ok"] = True
    return d


def family_singletons(facts: dict) -> list[str]:
    """Formula cells whose fingerprint is unique workbook-wide."""
    return [m for m, cells in facts["families"].items() if len(cells) == 1
            for m in cells]


def adjacent_family_breaks(facts: dict) -> list[dict]:
    """Singletons with a same-row/col neighbor in a family of >=3."""
    fams = facts["families"]
    big = {m for m, cells in fams.items() if len(cells) >= 3
            for m in cells}
    by_sheet_row: dict = {}
    by_sheet_col: dict = {}
    for coord, f in facts["formulas"].items():
        sheet = coord.split("!")[0]
        by_sheet_row.setdefault((sheet, f["row"]), []).append(coord)
        by_sheet_col.setdefault((sheet, f["col"]), []).append(coord)
    breaks = []
    for s in family_singletons(facts):
        f = facts["formulas"][s]
        sheet = s.split("!")[0]
        neighbors = [c for c in by_sheet_row.get((sheet, f["row"]), [])
                     if c != s]
        neighbors += [c for c in by_sheet_col.get((sheet, f["col"]), [])
                      if c != s]
        if any(n in big for n in neighbors):
            breaks.append({"cell": s, "neighbors": len(neighbors)})
    return breaks


def error_delta(pre: dict, post: dict) -> dict:
    new = sorted((post["errors"] - pre["errors"]))
    gone = sorted((pre["errors"] - post["errors"]))
    return {"new": new, "gone": gone,
            "types": Counter(str(post["values"].get(c)) for c in new)}


def blank_refs(facts: dict) -> dict[str, list[str]]:
    """formula coord -> referenced coords that are currently blank."""
    out: dict = {}
    for coord, refs in facts["precedents"].items():
        blanks = []
        for r in refs:
            for cell in expand_ref(r, coord):
                if facts["values"].get(cell) in (None, ""):
                    blanks.append(cell)
        if blanks:
            out[coord] = sorted(set(blanks))
    return out


def expand_ref(ref: str, context: str) -> list[str]:
    """Expand A1 refs/ranges to sheet-qualified coords (bounded)."""
    sheet = context.split("!")[0]
    if "!" in ref:
        sheet, ref = ref.rsplit("!", 1)
        sheet = sheet.strip("'")
    cells = []
    if ":" in ref:
        a, b = ref.split(":")
        try:
            from openpyxl.utils import coordinate_to_tuple
            r1, c1 = coordinate_to_tuple(a)
            r2, c2 = coordinate_to_tuple(b)
            if (r2 - r1 + 1) * (c2 - c1 + 1) > 20000:
                return []
            from openpyxl.utils import get_column_letter
            for r in range(min(r1, r2), max(r1, r2) + 1):
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    cells.append(f"{sheet}!{get_column_letter(c)}{r}")
        except Exception:
            return []
    else:
        m = COORD_RE.match(ref.replace("$", ""))
        if m:
            cells.append(f"{sheet}!{m.group(2).upper()}{m.group(4)}")
    return cells


FY_RE = re.compile(r"\b(FY\s?\d{2,4}|CY\s?\d{2,4}|Q[1-4]\b|20\d{2}|19\d{2})\b",
                   re.I)
MONTH_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b",
                      re.I)


def temporal_headers(facts: dict, path: str | None) -> dict:
    """Mechanically unambiguous period headers: date-typed cells in the first
    8 rows + FY/Q/year/month string matches. Returns col->labels per sheet."""
    out: dict = {"sheets": {}, "has_period_structure": False}
    if not path:
        return out
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:
        return out
    try:
        for ws in wb.worksheets:
            cols: dict = {}
            for row in ws.iter_rows(min_row=1, max_row=8):
                for cell in row:
                    label = None
                    v = cell.value
                    if cell.data_type == "d" and v is not None:
                        label = f"date:{v}"
                    elif isinstance(v, str):
                        if FY_RE.search(v) or MONTH_RE.search(v):
                            label = f"text:{v.strip()[:40]}"
                    if label:
                        cols.setdefault(cell.column, []).append(label)
            if len(cols) >= 3:
                out["sheets"][ws.title] = cols
    finally:
        wb.close()
    out["has_period_structure"] = bool(out["sheets"])
    return out


def repeated_output_columns(facts: dict) -> list[dict]:
    """Columns/blocks sharing translated formula families (>=2 bands)."""
    by_col: dict = {}
    for coord, f in facts["formulas"].items():
        if not f["fp"]:
            continue
        sheet = coord.split("!")[0]
        by_col.setdefault((sheet, f["col"]), []).append(f["fp"])
    sig_to_cols: dict = {}
    for (sheet, col), fps in by_col.items():
        sig = hashlib.sha256(("|".join(sorted(set(fps)))).encode()).hexdigest()[:16]
        if len(set(fps)) >= 2:
            sig_to_cols.setdefault((sheet, sig), []).append(col)
    return [{"sheet": s, "cols": sorted(c)}
            for (s, _), c in sig_to_cols.items() if len(c) >= 2]


def structural_diff(pre: dict, post: dict) -> dict:
    pf = set(pre["formulas"])
    qf = set(post["formulas"])
    pv = {c for c, v in pre["values"].items() if v not in (None, "")}
    qv = {c for c, v in post["values"].items() if v not in (None, "")}
    return {"formulas_added": sorted(qf - pf)[:200],
            "formulas_removed": sorted(pf - qf)[:200],
            "formulas_changed": sorted(
                c for c in pf & qf
                if pre["formulas"][c]["text"] != post["formulas"][c]["text"])[:200],
            "cells_emptied": sorted((pv - qv))[:200],
            "cells_filled": sorted((qv - pv))[:200]}


# ------------------------------------------------------ reachability rules
# Conservative pattern rules over (agent_code, observations). Each returns
# (R-level 1-5 or None if unexposed, evidence string). R0 handled by caller.

def _code(calls):
    return "\n".join(c for _, c in agent_python(calls))


def _obs(calls):
    return "\n".join(c.get("observation") or "" for c in calls)


def _has(code, *pats):
    return any(re.search(p, code, re.I | re.S) for p in pats)


def rule_formula_list(calls, facts, **kw):
    code, obs = _code(calls), _obs(calls)
    if not facts.get("formulas"):
        return None, "no formulas in workbook"
    if _has(code, r"data_type\s*==\s*['\"]f['\"]", r"\.value\b.*startswith\(['\"]=",
             r"print\([^)]*\.value", r"for\s+\w+\s+in\s+.*iter_rows",
             r"Translator", r"formula"):
        return 4, "agent code enumerates formulas"
    if _has(obs, r"="):
        return 2, "formulas visible in tool output"
    return 1, "formulas never inspected"


def rule_merged(calls, facts, **kw):
    code, obs = _code(calls), _obs(calls)
    if not any(facts.get("merged", {}).values()):
        return None, "no merged ranges"
    if _has(code, r"merged_cells|merged_ranges|unmerge|merge_cells"):
        return 4, "agent code touches merged ranges"
    if _has(obs, r"merg", "MERGED"):
        return 2, "merged visible in output"
    return 1, "merged never inspected"


def rule_family(calls, facts, **kw):
    code, obs = _code(calls), _obs(calls)
    big = [cells for cells in facts.get("families", {}).values()
           if len(cells) >= 3]
    if not big:
        return None, "no repeated family"
    if _has(code, r"Translator", r"set\(\s*\w*formula",
             r"Counter\(.*formula|formula.*Counter",
             r"\.value\s*(==|!=)\s*\S{0,40}\.value",
             r"formula.*(==|!=)| (==|!=).*formula",
             r"sorted\(\s*set\(|unique.*formula|formula.*unique",
             r"groupby|defaultdict\(.*formula", r"re\.\w+\(.*formula"):
        return 4, "agent code compares/groups formulas"
    if len(re.findall(r"print\([^)]*\.value", code)) >= 2:
        return 3, "multiple formulas printed, no comparison"
    if _has(obs, r"="):
        return 2, "formulas visible"
    return 1, "family structure never inspected"


def rule_uniformity(calls, facts, breaks, **kw):
    code, obs = _code(calls), _obs(calls)
    if not breaks:
        return None, "no adjacent family break"
    cells = {b["cell"].split("!")[-1] for b in breaks}
    if _has(code, r"!=\s*\w*formula|formula.*!=|different.*formula|"
             r"outlier|inconsist|breaks?\s+(the\s+)?pattern|"
             r"not\s+match|doesn.t\s+match"):
        return 4, "agent code/message flags deviant formula"
    if any(c in code for c in cells) and _has(code, r"print"):
        return 3, "outlier cell read without comparison"
    if _has(obs, r"="):
        return 2, "formulas visible"
    return 1, "break never inspected"


def rule_error_delta(calls, facts_pre, facts_post, delta, muts, **kw):
    code = _code(calls)
    if not facts_post.get("ok"):
        return 0, "no post-state (R0)"
    post_read = _has(code, r"data_only\s*=\s*True", r"soffice|libreoffice",
                      r"#REF|#VALUE|#DIV|#NAME|#N/A|#NUM|is-error|"
                      r"startswith\(['\"]#")
    if delta["new"]:
        cells = {c.split("!")[-1] for c in delta["new"]}
        if post_read and any(c in code for c in cells):
            return 4, "agent re-read output and touched new-error cells"
        if post_read:
            return 3, "agent re-read output values, error cells not named"
        return 1, "new errors present, output never re-read"
    # No delta: did the agent verify anyway?
    if post_read:
        return 4, "agent verified output values (no errors to find)"
    if muts and _has(code, r"load_workbook\(['\"]o"):
        return 3, "output reopened without value check"
    if muts:
        return 2, "mutation made; output values not re-read"
    return 1, "no mutation, no check"


def rule_temporal(calls, facts, temporal, **kw):
    code, obs = _code(calls), _obs(calls)
    if not temporal.get("has_period_structure"):
        return None, "no period structure"
    if _has(code, r"strptime|dateutil|datetime|FY|quarter|period|"
             r"19\d\d|20\d\d|month|Jan|Feb|Q[1-4]"):
        # Must be tied to header parsing, not incidental
        if _has(code, r"row\s*==?\s*1\b|\.rows\[0\]|header|min_row"):
            return 4, "agent code parses period headers"
        return 3, "date/period tokens in code without header tie"
    if FY_RE.search(obs) or MONTH_RE.search(obs):
        return 2, "period headers visible in output"
    return 1, "period headers never inspected"


def rule_role(calls, facts, roles, **kw):
    code, obs = _code(calls), _obs(calls)
    if not roles:
        return None, "no repeated output columns"
    if _has(code, r"analog|correspond|same\s+(struct|pattern|"
             r"layout|formula|block)|like\s+the\s+(other|rest|neighbor)|"
             r"same\s+as\s+(the\s+)?(other|neighbor|adjacent|rest)|"
             r"repeat.*(struct|pattern|block|col)|"
             r"across\s+\w+\s+(block|col|sheet).*same|"
             r"for\s+\w+\s+in\s+\w*(block|sheet)s\b.{0,200}(compar|match|same)"):
        return 4, "agent code/message compares repeated blocks"
    if _has(obs, r"Sheet"):
        return 2, "multiple sheets/blocks visible"
    return 1, "repeated structure never compared"


def rule_dependency(calls, facts, **kw):
    code, obs = _code(calls), _obs(calls)
    if not facts.get("formulas"):
        return None, "no formulas"
    if _has(code, r"Tokenizer|tokenize|precedent|dependent|"
             r"re\.findall.*A-Z.*0-9|coordinate_from_string|"
             r"Translator"):
        return 4, "agent code extracts references"
    if _has(code, r"\.value\b") and len(re.findall(r"\[[\"'][A-Z]+[0-9]+[\"']\]|"
             r"cell\(row=", code)) >= 3:
        return 3, "manual multi-cell trace"
    if _has(obs, r"="):
        return 2, "formulas visible"
    return 1, "dependencies never traced"


def rule_blank_ref(calls, facts_pre, facts_post, **kw):
    code = _code(calls)
    br = blank_refs(facts_pre)
    if not br:
        return None, "no blank-referenced formulas"
    if _has(code, r"is\s+None|==\s*None|blank|empty|not\s+\w+\.value"):
        return 4, "agent code checks blankness"
    if _has(code, r"\.value\b"):
        return 2, "values read without blankness check"
    return 1, "blank references never inspected"


def rule_struct_diff(calls, facts_pre, facts_post, diff, muts, **kw):
    code = _code(calls)
    if not facts_post.get("ok"):
        return 0, "no post-state (R0)"
    if not (diff.get("formulas_added") or diff.get("formulas_changed")
            or diff.get("cells_emptied")):
        return None, "no structural change"
    if _has(code, r"input\.xlsx.*output\.xlsx|output\.xlsx.*input\.xlsx|"
             r"diff|compar|before.*after|old.*new"):
        return 4, "agent code diffs input vs output"
    if muts and _has(code, r"load_workbook\(['\"]o"):
        return 3, "output re-read after mutation"
    if muts:
        return 2, "mutation made; no systematic re-read"
    return 1, "change never reviewed"


# R5 use-detection: narrow heuristics per candidate over call order
def rule_used(candidate: str, calls, evidence_cells: set[str]) -> bool:
    """True only with explicit use-after-obtaining evidence."""
    joined = [(c["idx"], (c.get("command") or "") + "\n" + (c.get("observation") or ""))
              for c in calls]
    if candidate == "ERR-NEW-ERROR-DELTA":
        for i, text in joined:
            if any(c in text for c in evidence_cells) and re.search(
                    r"#REF|#VALUE|#DIV|error", text, re.I):
                for j, later in joined:
                    if j > i and (".save(" in later or "submit" in later.lower()):
                        return True
        return False
    if candidate == "FAM-REL-FAMILY":
        for i, text in joined:
            if re.search(r"Translator|set\(.*formula|same.*formula", text, re.I):
                for j, later in joined:
                    if j > i and re.search(r"\.value\s*=\s*['\"]=", later):
                        return True
        return False
    return False


# ------------------------------------------------------------- decision events

def decision_events(calls: list[dict]) -> dict:
    muts = mutation_calls(calls)
    submits = [c for c in calls if c["tool"] == "submit"]
    first_mut = muts[0]["idx"] if muts else None
    last_mut = muts[-1]["idx"] if muts else None
    verify = [c for c in calls
              if last_mut is not None and c["idx"] > last_mut
              and c["tool"] == "bash"
              and ("output" in (c.get("command") or "")
                   or "data_only" in (c.get("command") or ""))]
    copy_f = [c for c in calls
              if re.search(r"\.value\s*=\s*['\"]=", c.get("command") or "")]
    return {"CHOOSE_TARGETS": first_mut, "COPY_FORMULA": copy_f[0]["idx"] if copy_f else None,
            "VERIFY_AFTER_EDIT": verify[0]["idx"] if verify else None,
            "SUBMIT": submits[0]["idx"] if submits else None,
            "DECLARE_COMPLETE": submits[0]["idx"] if submits else None,
            "REVISIT_REGION": None, "CHOOSE_SOURCE_PERIOD": first_mut}

CANDIDATE_EVENT = {
    "CTRL-FORMULA-LIST": "CHOOSE_TARGETS", "CTRL-MERGED-MAP": "CHOOSE_TARGETS",
    "FAM-REL-FAMILY": "COPY_FORMULA", "UNIF-FAMILY-BREAK": "CHOOSE_TARGETS",
    "ERR-NEW-ERROR-DELTA": "SUBMIT", "TEMP-PERIOD-MAP": "CHOOSE_SOURCE_PERIOD",
    "ROLE-EQUIV-SET": "CHOOSE_TARGETS", "DEP-DIRECT-REFS": "CHOOSE_TARGETS",
    "REF-BLANK-DELTA": "VERIFY_AFTER_EDIT", "CHG-STRUCT-DIFF": "VERIFY_AFTER_EDIT",
}


# ------------------------------------------------------- failure linkage

MISS_CELL_RE = re.compile(r"(?:at\s+)([A-Za-z0-9 _\-',&()]+?![A-Z]{1,3}[0-9]+)")


def miss_cells(eval_error: str | None) -> set[str]:
    if not eval_error:
        return set()
    return set(MISS_CELL_RE.findall(eval_error))


def failure_linkage(candidate: str, finding_cells: set[str], score: dict,
                    reached: int) -> str:
    if not score or score.get("official_exact") not in (0, 0.0):
        if score and score.get("official_exact") == 1:
            return "UNRELATED"
        return "UNKNOWN"
    err = score.get("eval_error") or ""
    misses = miss_cells(err)
    if candidate == "ERR-NEW-ERROR-DELTA" and finding_cells and reached < 4:
        if misses & finding_cells:
            return "DIRECTLY_LINKED"
        if re.search(r"#\w+!|error", err, re.I):
            return "PLAUSIBLY_LINKED"
        return "UNRELATED"
    if finding_cells and misses and (finding_cells & misses) and reached < 4:
        return "DIRECTLY_LINKED"
    if finding_cells and reached < 4:
        return "PLAUSIBLY_LINKED"
    return "UNRELATED"


def discrimination(finding_cells: set[str], score: dict) -> str:
    misses = miss_cells((score or {}).get("eval_error"))
    if not finding_cells:
        return "NO_DISCRIMINATION"
    if misses and finding_cells == misses:
        return "UNIQUE_DISCRIMINATOR"
    if misses and (finding_cells & misses):
        return "REDUCES_CANDIDATE_SET"
    if finding_cells:
        return "GENERIC_WARNING_ONLY"
    return "NO_DISCRIMINATION"


# ------------------------------------------------------------------- main

CANDIDATES = ["CTRL-FORMULA-LIST", "CTRL-MERGED-MAP", "FAM-REL-FAMILY",
              "UNIF-FAMILY-BREAK", "ERR-NEW-ERROR-DELTA", "TEMP-PERIOD-MAP",
              "ROLE-EQUIV-SET", "DEP-DIRECT-REFS", "REF-BLANK-DELTA",
              "CHG-STRUCT-DIFF"]

REGISTRY_D = {"CTRL-FORMULA-LIST": "D1", "CTRL-MERGED-MAP": "D1",
              "FAM-REL-FAMILY": "D2", "UNIF-FAMILY-BREAK": "D2",
              "ERR-NEW-ERROR-DELTA": "D3", "TEMP-PERIOD-MAP": "D2",
              "ROLE-EQUIV-SET": "D2", "DEP-DIRECT-REFS": "D1",
              "REF-BLANK-DELTA": "D2", "CHG-STRUCT-DIFF": "D3"}


def code_run(rep: dict, scores: dict) -> list[dict]:
    calls = parse_transcript(ROOT / rep["transcript"])
    rec = rep["record"]
    task_id = rec.get("task_id") or rep["rep"]
    arm = rec.get("arm")
    run_id = None
    m = re.search(r"(primary_\d+|[A-Z]+_r\d+)$", Path(rep["rep"]).name)
    if m:
        run_id = m.group(1)
    score = scores.get((task_id, arm, run_id)) or scores.get((task_id, arm, None)) or {}
    pre = derive_workbook(rep["input"])
    post = derive_workbook(rep["output"])
    muts = mutation_calls(calls)
    events = decision_events(calls)
    breaks = adjacent_family_breaks(pre) if pre["ok"] else []
    delta = error_delta(pre, post) if pre["ok"] and post["ok"] else {"new": [], "gone": []}
    temporal = temporal_headers(pre, rep["input"])
    roles = repeated_output_columns(pre) if pre["ok"] else []
    diff = structural_diff(pre, post) if pre["ok"] and post["ok"] else {}
    br_pre = blank_refs(pre) if pre["ok"] else {}
    br_post = blank_refs(post) if post["ok"] else {}
    # post-edit blank delta: refs that BECAME blank
    br_delta = set()
    for coord, cells in br_post.items():
        before = set(br_pre.get(coord, []))
        br_delta.update(set(cells) - before)

    findings: dict[str, set[str]] = {
        "CTRL-FORMULA-LIST": set(pre["formulas"]),
        "CTRL-MERGED-MAP": {f"{s}:{r}" for s, rs in pre["merged"].items() for r in rs},
        "FAM-REL-FAMILY": {c for cells in pre["families"].values() if len(cells) >= 3 for c in cells},
        "UNIF-FAMILY-BREAK": {b["cell"] for b in breaks},
        "ERR-NEW-ERROR-DELTA": set(delta["new"]),
        "TEMP-PERIOD-MAP": {f"{s}:{c}" for s, cols in temporal["sheets"].items() for c in cols},
        "ROLE-EQUIV-SET": {f"{r['sheet']}:{c}" for r in roles for c in r["cols"]},
        "DEP-DIRECT-REFS": set(pre["precedents"]),
        "REF-BLANK-DELTA": br_delta,
        "CHG-STRUCT-DIFF": set((diff.get("formulas_added") or []) + (diff.get("formulas_changed") or []) + (diff.get("cells_emptied") or [])),
    }
    rules = {
        "CTRL-FORMULA-LIST": rule_formula_list(calls, pre),
        "CTRL-MERGED-MAP": rule_merged(calls, pre),
        "FAM-REL-FAMILY": rule_family(calls, pre),
        "UNIF-FAMILY-BREAK": rule_uniformity(calls, pre, breaks),
        "ERR-NEW-ERROR-DELTA": rule_error_delta(calls, pre, post, delta, muts),
        "TEMP-PERIOD-MAP": rule_temporal(calls, pre, temporal),
        "ROLE-EQUIV-SET": rule_role(calls, pre, roles),
        "DEP-DIRECT-REFS": rule_dependency(calls, pre),
        "REF-BLANK-DELTA": rule_blank_ref(calls, pre, post),
        "CHG-STRUCT-DIFF": rule_struct_diff(calls, pre, post, diff, muts),
    }
    rows = []
    for cand in CANDIDATES:
        level, evidence = rules[cand]
        if level is None:
            continue  # unexposed
        if level == 4 and rule_used(cand, calls, {c.split("!")[-1] for c in findings[cand]}):
            level = 5
        event = CANDIDATE_EVENT[cand]
        rows.append({
            "task": task_id, "rep": rep["rep"], "source": rep["source"],
            "arm": arm, "family": rec.get("family"),
            "model": rec.get("model"), "status": rec.get("status"),
            "event": event, "event_call": events.get(event),
            "candidate": cand, "d_level": REGISTRY_D[cand],
            "reachability": level, "reach_evidence": evidence,
            "finding_count": len(findings[cand]),
            "finding_cells": sorted(findings[cand])[:50],
            "n_calls": len(calls), "n_python": len(agent_python(calls)),
            "official_exact": score.get("official_exact"),
            "eval_error": (score.get("eval_error") or "")[:300],
            "failure_linkage": failure_linkage(cand, findings[cand], score, level or 0),
            "discrimination": discrimination(findings[cand], score),
            "has_input": pre["ok"], "has_output": post["ok"],
            "output_shared": rep.get("output_shared", False),
        })
    return rows


AGENT_PATTERNS = {
    "set_comparison": r"set\(.*\)\s*[-&^|]\s*set\(|symmetric_difference",
    "counter_grouping": r"Counter\(|defaultdict\(|groupby",
    "formula_regex": r"re\.(compile|findall|search|match)\(",
    "date_parsing": r"strptime|dateutil|datetime\.|fromisoformat",
    "dep_extraction": r"Tokenizer|precedent|Translator|coordinate_",
    "before_after": r"input\.xlsx.*output|output.*input\.xlsx|diff|shutil",
    "projection": r"iter_rows|iter_cols|ws\.rows|ws\.columns",
    "zip_inspection": r"zipfile|ZipFile",
    "recalc": r"soffice|libreoffice|data_only",
    "scan_loop": r"for\s+\w+\s+in\s+.*:\s*\n.*for\s+\w+\s+in",
    "print_dump": r"print\(",
    "save_mutation": r"\.save\(",
}


def mine_agent_patterns(reps: list[dict]) -> Counter:
    counts: Counter = Counter()
    for rep in reps:
        calls = parse_transcript(ROOT / rep["transcript"])
        code = _code(calls)
        for name, pat in AGENT_PATTERNS.items():
            if re.search(pat, code, re.I | re.S):
                counts[name] += 1
    return counts


def main() -> None:
    OUT.mkdir(exist_ok=True)
    reps = index_reps()
    print(f"indexed reps: {len(reps)}", file=sys.stderr)
    with_input = sum(1 for r in reps if r["input"])
    with_output = sum(1 for r in reps if r["output"])
    print(f"with input: {with_input}, with output: {with_output}", file=sys.stderr)
    scores = load_scores()
    rows: list[dict] = []
    ok = 0
    for i, rep in enumerate(reps):
        try:
            rows.extend(code_run(rep, scores))
            ok += 1
        except Exception as exc:  # never let one rep kill the census
            print(f"SKIP {rep['rep']}: {type(exc).__name__}: {exc}", file=sys.stderr)
        if (i + 1) % 25 == 0:
            print(f"  coded {i + 1}/{len(reps)}", file=sys.stderr)
    with open(OUT / "DERIVATION_REACHABILITY_MATRIX.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    print(f"coded reps: {ok}, matrix rows: {len(rows)}", file=sys.stderr)
    pats = mine_agent_patterns(reps)
    print("agent patterns:", dict(pats), file=sys.stderr)
    with open(OUT / "AGENT_PATTERN_COUNTS.json", "w") as f:
        json.dump({"runs": len(reps), "patterns": dict(pats)}, f, indent=1)


if __name__ == "__main__":
    main()
