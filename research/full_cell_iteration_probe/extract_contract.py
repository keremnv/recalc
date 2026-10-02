"""Extract the observed iteration contract from target workloads.

1. Re-derive the iteration-only-blocked representative subset by running the
   frozen classifier over staged Population A scripts.
2. AST-extract every concrete iteration form + downstream cell use.
3. Emit TARGET_WORKLOADS.json + ITERATION_CONTRACT.json.

Read-only with respect to product code; writes only probe research files.
"""
import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from recalc_agent._frozen.eligibility import classify  # noqa: E402

CENSUS_STAGE = Path(__file__).parent.parent / "execution_surface_census" / "_staging"
ITER_BLOCKERS = {"iterator shape not statically proven",
                 "CELL_OBJECT_ITERATION_BOUNDARY"}


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        return (left + "." + node.attr) if left else node.attr
    return ""


class IterCensus(ast.NodeVisitor):
    """Collect iteration forms and downstream cell-variable use."""

    def __init__(self, source):
        self.source = source
        self.ws_vars = set()
        self.wb_vars = set()
        self.iter_calls = []      # iter_rows/iter_cols call sites + args
        self.sheet_iters = []     # for x in ws
        self.cell_vars = set()    # vars proven to hold cells from iteration
        self.row_vars = set()     # vars proven to hold yielded rows
        self.cell_attr_use = {}   # attr -> count (on cell vars)
        self.row_ops = []         # len/index/unpack/materialize on row vars
        self.stored = []          # cell vars stored/captured
        self.identity_use = []    # is/type/parent/repr on cell vars
        self.merged_refs = []
        self.materialize = []     # list()/tuple() over iterators

    def resolve(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                tgt = node.targets[0]
                if not isinstance(tgt, ast.Name):
                    continue
                val = node.value
                if isinstance(val, ast.Call):
                    if _dotted(val.func).rsplit(".", 1)[-1] == "load_workbook":
                        self.wb_vars.add(tgt.id)
                elif isinstance(val, ast.Name) and val.id in self.wb_vars:
                    self.wb_vars.add(tgt.id)
                elif isinstance(val, ast.Subscript):
                    if _dotted(val.value) in self.wb_vars:
                        self.ws_vars.add(tgt.id)
            elif isinstance(node, ast.For):
                self._for_target(node)

    def _for_target(self, node):
        it = node.iter
        names = [n.id for n in ast.walk(node.target)
                 if isinstance(n, ast.Name)
                 and isinstance(getattr(n, "ctx", None), ast.Store)]
        base = ""
        call = ""
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute):
            call = it.func.attr
            base = _dotted(it.func.value)
        else:
            base = _dotted(it)
        if call in ("iter_rows", "iter_cols") and base in self.ws_vars:
            self.row_vars.update(names)
        elif base in self.ws_vars and not call:
            self.sheet_iters.append({"line": node.lineno, "targets": names})
            self.row_vars.update(names)
        elif base in self.row_vars or (not base and not call and
                                       _dotted(it) in self.row_vars):
            self.cell_vars.update(names)
        elif _dotted(it) in self.row_vars:
            self.cell_vars.update(names)

    def visit_Call(self, node):
        fn = _dotted(node.func)
        short = fn.rsplit(".", 1)[-1]
        recv = (node.func.value if isinstance(node.func, ast.Attribute)
                else None)
        if short in ("iter_rows", "iter_cols"):
            args = {}
            for k in node.keywords:
                try:
                    args[k.arg] = ast.literal_eval(k.value)
                except Exception:
                    args[k.arg] = "<dynamic>"
            self.iter_calls.append({"method": short, "line": node.lineno,
                                    "receiver_ws": recv is not None and
                                    _dotted(recv) in self.ws_vars,
                                    "kwargs": args})
        elif short in ("list", "tuple") and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Call):
                inner = _dotted(a0.func).rsplit(".", 1)[-1]
                if inner in ("iter_rows", "iter_cols"):
                    self.materialize.append({"line": node.lineno,
                                             "form": short, "of": inner})
        self.generic_visit(node)

    def visit_Attribute(self, node):
        base = _dotted(node.value).split(".", 1)[0]
        if base in self.cell_vars:
            self.cell_attr_use[node.attr] = \
                self.cell_attr_use.get(node.attr, 0) + 1
        if node.attr in ("merged_cells", "merge_cells", "unmerge_cells"):
            self.merged_refs.append({"line": getattr(node, "lineno", None)})
        self.generic_visit(node)

    def visit_Subscript(self, node):
        base = _dotted(node.value).split(".", 1)[0]
        if base in self.row_vars:
            self.row_ops.append({"op": "index", "line": node.lineno})
        self.generic_visit(node)

    def visit_Compare(self, node):
        for op in node.ops:
            if isinstance(op, (ast.Is, ast.IsNot)):
                sides = [_dotted(node.left).split(".", 1)[0]] + \
                        [_dotted(c).split(".", 1)[0] for c in node.comparators]
                if any(s in self.cell_vars for s in sides):
                    self.identity_use.append({"op": "is",
                                              "line": node.lineno})
        self.generic_visit(node)


def analyze(workload_id, source):
    tree = ast.parse(source)
    c = IterCensus(source)
    c.resolve(tree)
    c.visit(tree)
    return {
        "workload": workload_id,
        "ws_vars": sorted(c.ws_vars),
        "iter_calls": c.iter_calls,
        "sheet_iters": c.sheet_iters,
        "cell_vars": sorted(c.cell_vars),
        "row_vars": sorted(c.row_vars),
        "cell_attr_use": dict(sorted(c.cell_attr_use.items())),
        "row_ops": c.row_ops,
        "materialize": c.materialize,
        "identity_use": c.identity_use,
        "merged_refs": c.merged_refs,
    }


def main():
    man = json.loads((HERE.parent / "execution_surface_census"
                      / "WORKLOAD_MANIFEST.json").read_text())
    staged = CENSUS_STAGE / "staged" / "clean" / "A"
    targets, admitted, other = [], [], []
    for w in man["populations"]["A"]["workloads"]:
        wid = w["workload_id"]
        src = (staged / wid / "workload.py").read_text()
        res = classify(src)
        if res.get("decision") == "A1_ADMIT":
            admitted.append(wid)
            continue
        reasons = {b if isinstance(b, str) else b.get("reason", "?")
                   for b in (res.get("blockers") or [])}
        if reasons <= ITER_BLOCKERS:
            targets.append(wid)
        else:
            other.append({"workload": wid, "blockers": sorted(reasons)})
    print("admitted:", len(admitted), "targets:", len(targets),
          "other-blocked:", len(other))
    for o in other:
        print("  other:", o["workload"], o["blockers"])

    contract = [analyze(wid, (staged / wid / "workload.py").read_text())
                for wid in sorted(targets)]
    (HERE / "TARGET_WORKLOADS.json").write_text(json.dumps(
        {"n": len(targets), "workloads": sorted(targets),
         "rule": "Population A, classifier blockers subset of "
                 "{iterator shape not statically proven, "
                 "CELL_OBJECT_ITERATION_BOUNDARY}",
         "other_blocked": other, "admitted": sorted(admitted)},
        indent=1) + "\n")
    (HERE / "ITERATION_CONTRACT.json").write_text(
        json.dumps(contract, indent=1) + "\n")
    # Aggregate summary to stdout.
    agg_calls, agg_attrs = {}, {}
    for c in contract:
        for ic in c["iter_calls"]:
            k = (ic["method"], tuple(sorted(ic["kwargs"])))
            agg_calls[k] = agg_calls.get(k, 0) + 1
        for a, n in c["cell_attr_use"].items():
            agg_attrs[a] = agg_attrs.get(a, 0) + n
    print("iter call shapes:", agg_calls)
    print("cell attrs:", agg_attrs)
    print("sheet iters:", sum(len(c["sheet_iters"]) for c in contract),
          "materialize:", sum(len(c["materialize"]) for c in contract),
          "row_ops:", sum(len(c["row_ops"]) for c in contract),
          "identity:", sum(len(c["identity_use"]) for c in contract),
          "merged:", sum(len(c["merged_refs"]) for c in contract))


if __name__ == "__main__":
    main()
