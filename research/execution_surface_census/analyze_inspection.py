"""I3 — static inspection-loop census over archived sources.

AST + conservative pattern detectors. Never executes. For traversal-size
estimates it reads workbook dimensions only (values never enter verdicts).
Output: INSPECTION_LOOP_CENSUS.jsonl rows per (script, pattern instance).
"""
import ast
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]

# Sheets of detectors; each returns list of dicts with conservative fields.
PRINT_CALLS = {"print"}
TEXT_OPS = {"find", "lower", "upper", "strip", "startswith", "endswith",
            "match", "search", "fullmatch"}
LOOP_BOUND_RE = re.compile(r"range\(\s*(\d+)?\s*,?\s*(\d+)?")


def _src(seg, node):
    try:
        return ast.get_source_segment(seg, node) or ""
    except Exception:
        return ""


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        return (left + "." + node.attr) if left else node.attr
    return ""


class Census(ast.NodeVisitor):
    def __init__(self, source, dims):
        self.source = source
        self.dims = dims  # {sheet: (max_row, max_col)} or {}
        self.rows = []
        self.stack = []
        self.loads = []  # load_workbook call nodes
        self.saves = []
        self.prints = []
        self.loops = []
        self.wb_vars = set()
        self.ws_vars = set()
        self.cell_vars = set()

    def resolve_provenance(self, tree):
        # Workbook/worksheet/cell variable provenance (A1-classifier style).
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if not isinstance(tgt, ast.Name):
                    continue
                name, val = tgt.id, node.value
                if isinstance(val, ast.Call):
                    fn = _dotted(val.func)
                    if fn.rsplit(".", 1)[-1] == "load_workbook":
                        self.wb_vars.add(name)
                    elif fn.rsplit(".", 1)[-1] == "cell":
                        recv = (val.func.value if isinstance(val.func, ast.Attribute)
                                else None)
                        if recv is not None and _dotted(recv) in self.ws_vars:
                            self.cell_vars.add(name)
                elif isinstance(val, ast.Name):
                    for s, t in ((self.wb_vars, self.wb_vars),
                                 (self.ws_vars, self.ws_vars),
                                 (self.cell_vars, self.cell_vars)):
                        if val.id in s:
                            t.add(name)
                elif isinstance(val, ast.Subscript):
                    base = _dotted(val.value)
                    if base in self.wb_vars:
                        self.ws_vars.add(name)
                    elif base in self.ws_vars:
                        self.cell_vars.add(name)
            elif isinstance(node, ast.For):
                # for ws in wb / wb.worksheets ; for row in ws.iter_rows()...
                it = _src(self.source, node.iter)
                base = _dotted(node.iter.func.value) if (
                    isinstance(node.iter, ast.Call) and
                    isinstance(node.iter.func, ast.Attribute)) else _dotted(node.iter)
                tgt = node.target
                names = [n.id for n in ast.walk(tgt)
                         if isinstance(n, ast.Name) and
                         isinstance(getattr(n, "ctx", None), ast.Store)]
                if base in self.wb_vars:
                    self.ws_vars.update(names)
                elif base in self.ws_vars:
                    self.cell_vars.update(names)

    def _is_wb_object(self, node):
        return _dotted(node).split(".", 1)[0] in (
            self.wb_vars | self.ws_vars | self.cell_vars)

    def emit(self, family, detail, node, scope=None, traversed=None,
             printed="unknown"):
        self.rows.append({
            "family": family, "detail": detail,
            "line": getattr(node, "lineno", None),
            "scope": scope or "unknown",
            "traversed_cells_est": traversed,
            "printed": printed,
            "evidence": _src(self.source, node)[:400],
        })

    def visit_Call(self, node):
        fn = node.func
        name = ""
        if isinstance(fn, ast.Attribute):
            name = fn.attr
        elif isinstance(fn, ast.Name):
            name = fn.id
        if name == "load_workbook":
            self.loads.append(node)
            args = [_src(self.source, a)[:80] for a in node.args]
            kws = {k.arg: _src(self.source, k.value)[:40] for k in node.keywords}
            self.emit("LOAD", {"args": args, "kwargs": kws}, node)
        elif name == "save":
            self.saves.append(node)
            self.emit("SAVE", {}, node)
        elif name == "print":
            self.prints.append(node)
        elif name in ("iter_rows", "iter_cols", "iterrows"):
            self._inspect_iteration(node, name)
        elif name in ("Popen", "run", "call", "check_output", "check_call",
                      "system", "popen"):
            s = _src(self.source, node).lower()
            if "soffice" in s or "libreoffice" in s:
                self.emit("RECALC_EXTERNAL", {"call": name}, node)
        elif name in TEXT_OPS and self._in_loop():
            self.emit("SEARCH_TEXT_OP", {"op": name}, node,
                      printed="conditional")
        self.generic_visit(node)

    def visit_For(self, node):
        self.loops.append(node)
        self._inspect_loop(node)
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def visit_While(self, node):
        self.loops.append(node)
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def _in_loop(self):
        return bool(self.stack)

    def _loop_iter_shape(self, node):
        it = node.iter
        s = _src(self.source, it)
        if isinstance(it, ast.Call):
            f = it.func
            n = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            return ("call", n, s[:120])
        return ("other", "", s[:120])

    def _inspect_iteration(self, node, name):
        in_loop = self._in_loop()
        body_print = "unknown"
        self.emit("BROAD_INSPECTION" if not in_loop else "NESTED_SCAN",
                  {"iter": name, "nested": in_loop,
                   "args": _src(self.source, node)[:160]}, node,
                  printed=body_print)

    def _inspect_loop(self, node):
        kind, name, shape = self._loop_iter_shape(node)
        body = "\n".join(_src(self.source, b) for b in node.body)
        has_print = "print(" in body
        has_text_test = any(op in body for op in
                            (" in ", ".find(", ".lower()", "==", "!=",
                             "startswith", "regex", "re.search", "re.match"))
        has_formula_test = ("'='" in body or '"="' in body or "data_type" in body
                            or "startswith('=')" in body or ".value" in body)
        has_assign = False
        for b in ast.walk(node):
            if isinstance(b, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                tgts = b.targets if isinstance(b, ast.Assign) else [b.target]
                for t in tgts:
                    # Workbook writes only: stores into proven workbook
                    # objects. Plain names/dicts/lists are local accumulation.
                    if isinstance(t, ast.Subscript):
                        if self._is_wb_object(t.value):
                            has_assign = True
                    elif (isinstance(t, ast.Attribute) and t.attr == "value"):
                        if self._is_wb_object(t.value):
                            has_assign = True
            elif isinstance(b, ast.Call):
                f = b.func
                n = f.attr if isinstance(f, ast.Attribute) else ""
                recv = f.value if isinstance(f, ast.Attribute) else None
                if n in ("append", "delete_rows", "delete_cols",
                         "merge_cells", "unmerge_cells", "create_sheet",
                         "add_data_validation", "add_table", "freeze_panes"):
                    if recv is not None and self._is_wb_object(recv):
                        has_assign = True
        # range() loop bounds
        rng = LOOP_BOUND_RE.search(shape)
        bound = None
        if rng:
            try:
                lo = int(rng.group(1) or 0)
                hi = int(rng.group(2) or lo)
                bound = max(0, hi - lo)
            except ValueError:
                bound = None
        if name in ("iter_rows", "iter_cols") or "iter_rows" in shape:
            fam = "BROAD_INSPECTION"
        elif has_text_test and not has_assign:
            fam = "SEARCH"
        elif has_formula_test and not has_assign and has_print:
            fam = "FORMULA_INSPECTION"
        elif has_assign:
            fam = "MUTATION_LOOP"
        elif has_print:
            fam = "PRINT_LOOP"
        else:
            fam = "ACCUMULATION_LOOP"
        self.emit(fam, {"iter_shape": shape, "range_bound": bound,
                        "has_print": has_print, "nested": self._in_loop()},
                  node, printed="yes" if has_print else "no")


def workbook_dims(path):
    """Dimensions only (no values). Returns {sheet: (max_row, max_col)}."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        out = {}
        for ws in wb.worksheets:
            try:
                out[ws.title] = (ws.max_row or 0, ws.max_column or 0)
            except Exception:
                out[ws.title] = (0, 0)
        wb.close()
        return out
    except Exception:
        return {}


def analyze_script(source, dims):
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [{"family": "UNPARSEABLE", "detail": {"error": str(e)[:120]},
                 "line": None, "scope": "unknown",
                 "traversed_cells_est": None, "printed": "unknown",
                 "evidence": ""}]
    c = Census(source, dims)
    c.resolve_provenance(tree)
    c.visit(tree)
    # Cross-cutting conservative detectors on full text.
    s = source
    if re.search(r"data_only\s*=\s*True", s):
        c.emit("READBACK_DATA_ONLY", {}, tree)
    if len(c.loads) >= 2:
        c.emit("MULTI_LOAD", {"n_loads": len(c.loads)}, tree,
               scope="reopen_or_compare")
    if c.loads and c.saves:
        # save position vs last load: reopen-after-save heuristic
        last_load_line = max(getattr(n, "lineno", 0) for n in c.loads)
        first_save_line = min(getattr(n, "lineno", 0) for n in c.saves)
        if last_load_line > first_save_line:
            c.emit("REOPEN_AFTER_SAVE", {}, tree)
    if len(c.loads) >= 2 and "for" in s:
        c.emit("POSSIBLE_WORKBOOK_COMPARE", {"n_loads": len(c.loads)}, tree)
    if re.search(r"\.font|\.fill|\.border|\.alignment|number_format|\.style",
                 s):
        c.emit("STYLE_RICH_REF", {}, tree)
    if re.search(r"merged_cells|merge_cells|unmerge", s):
        c.emit("MERGE_REF", {}, tree)
    if re.search(r"defined_names|create_named_range|\.tables\[|\.tables\.add",
                 s):
        c.emit("NAMES_TABLES_REF", {}, tree)
    if re.search(r"ws\[.*:.*\]|iter_rows\(.*\)|iter_cols\(.*\)", s):
        pass  # ranges/iters already covered by AST detectors
    if re.search(r"open\(['\"]", s) and "zipfile" in s:
        c.emit("PACKAGE_XML_SURGERY", {}, tree)
    return c.rows


def main():
    man = json.loads((HERE / "WORKLOAD_MANIFEST.json").read_text())
    rc_stage = HERE / "_staging" / "rc_acceleration_validation"
    rc_man = json.loads((rc_stage / "workload_manifest.json").read_text())
    cands = {c["workload_id"]: c for c in rc_man["all_candidates"]}
    execs = {}
    with open(ROOT / "research" / "history" / "control_python_audit"
              / "python_executions.jsonl") as f:
        for line in f:
            r = json.loads(line)
            execs[r["exec_id"]] = r
    out = HERE / "_staging" / "inspection_raw.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out, "w") as f:
        # A/B scripts
        for pop in ("A", "B"):
            for w in man["populations"][pop]["workloads"]:
                wid = w["workload_id"]
                src = (rc_stage / "workloads" / (wid + ".py")).read_text()
                dims = workbook_dims(cands[wid]["workbook_path"])
                rows = analyze_script(src, dims)
                for r in rows:
                    r.update({"population": pop, "id": wid,
                              "task": w["task"], "family_fam": w["family"]})
                    f.write(json.dumps(r, sort_keys=True) + "\n")
                    n += 1
        # C scripts (all 309 in universe for the static census, flagged)
        selected = {w["exec_id"] for w in man["populations"]["C"]["workloads"]}
        for eid, r in sorted(execs.items()):
            if not r.get("source"):
                continue
            if r["population"] == "P-C_viz":
                continue
            rows = analyze_script(r["source"], {})
            for row in rows:
                row.update({"population": "Cuniverse", "id": "C_%d" % eid,
                            "task": r["task_id"], "family_fam": r["family"],
                            "in_sample": eid in selected})
                f.write(json.dumps(row, sort_keys=True) + "\n")
                n += 1
    print("inspection rows:", n)


if __name__ == "__main__":
    main()
