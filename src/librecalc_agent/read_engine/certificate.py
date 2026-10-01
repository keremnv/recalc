"""Positive, closed-grammar merged-child scalar certificate."""
from __future__ import annotations

import ast
from typing import Any

TERMINALS = frozenset({"value", "data_type", "coordinate", "row", "column"})
SCALAR_CALLS = frozenset({"print", "repr", "type", "range"})
RESERVED = SCALAR_CALLS | {"openpyxl"}


class NotProven(Exception):
    def __init__(self, reason: str, node: ast.AST | None = None):
        self.reason = reason
        self.line = getattr(node, "lineno", None)
        super().__init__(reason)


class Prover:
    def __init__(self) -> None:
        self.imported = False
        self.books: set[str] = set()
        self.sheets: set[str] = set()
        self.scalars: set[str] = set()
        self.lists: set[str] = set()
        self.cell_calls = 0

    def fail(self, reason: str, node: ast.AST) -> None:
        raise NotProven(reason, node)

    def ordinary_target(self, node: ast.AST) -> str:
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Store):
            self.fail("NON_NAME_BINDING", node)
        if node.id in RESERVED:
            self.fail("RESERVED_REBINDING", node)
        return node.id

    def load_call(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            return False
        fn = node.func
        if not (isinstance(fn.value, ast.Name) and fn.value.id == "openpyxl"
                and fn.attr == "load_workbook"):
            return False
        if not self.imported or len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) \
                or not isinstance(node.args[0].value, str):
            self.fail("UNPROVEN_LOAD", node)
        if any(kw.arg != "data_only" or not isinstance(kw.value, ast.Constant)
               or kw.value.value is not False for kw in node.keywords):
            self.fail("UNPROVEN_LOAD_MODE", node)
        return True

    def sheet_lookup(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name):
            return False
        if node.value.id not in self.books:
            return False
        if not isinstance(node.slice, ast.Constant) or not isinstance(node.slice.value, str):
            self.fail("DYNAMIC_SHEET_LOOKUP", node)
        return True

    def cell_call(self, node: ast.AST) -> None:
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            self.fail("CELL_CALL_SHAPE", node)
        fn = node.func
        if fn.attr != "cell" or not isinstance(fn.value, ast.Name) or fn.value.id not in self.sheets:
            self.fail("UNPROVEN_CELL_RECEIVER", node)
        if len(node.args) > 2 or any(kw.arg not in {"row", "column"} for kw in node.keywords):
            self.fail("UNPROVEN_CELL_ARGUMENTS", node)
        for arg in node.args:
            self.expr(arg)
        for kw in node.keywords:
            self.expr(kw.value)
        self.cell_calls += 1

    def expr(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and type(node.value) in (type(None), bool, int, float, str):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in self.scalars or node.id in self.lists:
                return
            self.fail("UNPROVEN_NAME_VALUE", node)
        if isinstance(node, ast.Attribute):
            if node.attr in TERMINALS and isinstance(node.value, ast.Call):
                self.cell_call(node.value)
                return
            self.fail("UNPROVEN_ATTRIBUTE_OR_OBJECT_ESCAPE", node)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in SCALAR_CALLS:
                if node.keywords or any(isinstance(a, ast.Starred) for a in node.args):
                    self.fail("UNPROVEN_CALL_ARGUMENTS", node)
                if node.func.id == "range" and not 1 <= len(node.args) <= 3:
                    self.fail("UNPROVEN_RANGE", node)
                if node.func.id in {"repr", "type"} and len(node.args) != 1:
                    self.fail("UNPROVEN_SCALAR_CALL", node)
                for arg in node.args:
                    self.expr(arg)
                return
            if (isinstance(node.func, ast.Attribute) and node.func.attr == "append"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in self.lists and len(node.args) == 1
                    and not node.keywords):
                self.expr(node.args[0])
                return
            self.fail("UNPROVEN_CALL_DISPATCH", node)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for elt in node.elts:
                self.expr(elt)
            return
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                self.fail("DICT_UNPACK", node)
            for key, value in zip(node.keys, node.values):
                self.expr(key)
                self.expr(value)
            return
        if isinstance(node, ast.ListComp):
            previous = set(self.scalars)
            try:
                for gen in node.generators:
                    if gen.is_async:
                        self.fail("ASYNC_COMPREHENSION", node)
                    self.iterator(gen.iter)
                    target = self.ordinary_target(gen.target)
                    if target in self.books or target in self.sheets or target in self.lists:
                        self.fail("PROXY_BINDER_REUSE", gen.target)
                    self.scalars.add(target)
                    for cond in gen.ifs:
                        self.expr(cond)
                self.expr(node.elt)
            finally:
                self.scalars = previous
            return
        if isinstance(node, ast.Subscript):
            self.expr(node.value)  # Workbook and worksheet names are not scalar values.
            if isinstance(node.slice, ast.Slice):
                for part in (node.slice.lower, node.slice.upper, node.slice.step):
                    if part is not None:
                        self.expr(part)
            else:
                self.expr(node.slice)
            return
        if isinstance(node, ast.Compare):
            self.expr(node.left)
            for other in node.comparators:
                self.expr(other)
            if not all(isinstance(op, (ast.Is, ast.IsNot, ast.Eq, ast.NotEq,
                                      ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for op in node.ops):
                self.fail("UNPROVEN_COMPARISON", node)
            return
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for value in node.values:
                self.expr(value)
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            self.expr(node.operand)
            return
        if isinstance(node, ast.IfExp):
            self.expr(node.test)
            self.expr(node.body)
            self.expr(node.orelse)
            return
        self.fail("UNKNOWN_EXPRESSION", node)

    def iterator(self, node: ast.AST) -> None:
        if isinstance(node, (ast.List, ast.Tuple)):
            for elt in node.elts:
                self.expr(elt)
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            self.expr(node)
            return
        self.fail("UNPROVEN_ITERATOR", node)

    def statement(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Import):
            if self.imported or len(node.names) != 1 or node.names[0].name != "openpyxl" \
                    or node.names[0].asname is not None:
                self.fail("UNPROVEN_IMPORT", node)
            self.imported = True
            return
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                self.fail("MULTIPLE_BINDING", node)
            target = self.ordinary_target(node.targets[0])
            if self.load_call(node.value):
                if target in self.sheets or target in self.scalars or target in self.lists:
                    self.fail("PROXY_BINDER_REUSE", node)
                self.books.add(target)
                return
            if self.sheet_lookup(node.value):
                if target in self.books or target in self.scalars or target in self.lists:
                    self.fail("PROXY_BINDER_REUSE", node)
                self.sheets.add(target)
                return
            if target in self.books or target in self.sheets:
                self.fail("PROXY_REBINDING", node)
            self.expr(node.value)
            if isinstance(node.value, ast.List) and not node.value.elts:
                self.lists.add(target)
            else:
                self.lists.discard(target)
                self.scalars.add(target)
            return
        if isinstance(node, ast.For):
            if node.orelse:
                self.fail("LOOP_ELSE", node)
            self.iterator(node.iter)
            target = self.ordinary_target(node.target)
            if target in self.books or target in self.sheets or target in self.lists:
                self.fail("PROXY_BINDER_REUSE", node.target)
            self.scalars.add(target)
            for item in node.body:
                self.statement(item)
            return
        if isinstance(node, ast.If):
            self.expr(node.test)
            for item in node.body + node.orelse:
                self.statement(item)
            return
        if isinstance(node, ast.Expr):
            self.expr(node.value)
            return
        if isinstance(node, ast.Pass):
            return
        self.fail("UNKNOWN_STATEMENT", node)

    def module(self, tree: ast.Module) -> None:
        for stmt in tree.body:
            self.statement(stmt)
        if not self.imported or not self.books or not self.sheets or self.cell_calls == 0:
            raise NotProven("NO_POSITIVE_CELL_PROOF")


def certify(source: str, admission: dict[str, Any]) -> dict[str, Any]:
    if admission.get("decision") != "A1_ADMIT":
        return {"certified": False, "reason": "NOT_ADMITTED", "cell_calls": 0}
    try:
        tree = ast.parse(source)
        proof = Prover()
        proof.module(tree)
    except SyntaxError:
        return {"certified": False, "reason": "PARSE_FAILED", "cell_calls": 0}
    except NotProven as exc:
        result: dict[str, Any] = {"certified": False, "reason": exc.reason,
                                  "cell_calls": proof.cell_calls if "proof" in locals() else 0}
        if exc.line is not None:
            result["line"] = exc.line
        return result
    return {"certified": True, "reason": "CLOSED_GRAMMAR_TERMINAL_CELL_PROOF",
            "cell_calls": proof.cell_calls, "terminals": sorted(TERMINALS)}
