"""Frozen implementation; packaging extraction only. See extraction_manifest.json."""
from __future__ import annotations
import ast
import re
from typing import Any

def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def const_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def is_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def base_name(node: ast.AST) -> str:
    return dotted(node).split(".", 1)[0]


class A1Analyzer:
    """Small fail-closed source classifier; it never rewrites or executes code."""

    RICH = {"font", "fill", "border", "alignment", "comment", "hyperlink", "number_format", "style", "tables", "merged_cells", "defined_names", "_charts", "_images", "_cells", "_parent"}

    def __init__(self, source: str | None):
        self.source = source or ""
        self.categories: list[dict[str, Any]] = []
        self.blockers: list[dict[str, Any]] = []
        self.workbooks: set[str] = set()
        self.worksheets: set[str] = set()
        self.cells: set[str] = set()
        self.cell_functions: set[str] = set()
        self.openpyxl_loaded = "openpyxl" in self.source
        self.tree: ast.AST | None = None
        self.parse_error: str | None = None
        try:
            self.tree = ast.parse(self.source)
        except SyntaxError as exc:
            self.parse_error = str(exc)

    def add_category(self, category: str, node: ast.AST, detail: str = "") -> None:
        self.categories.append({"category": category, "line": getattr(node, "lineno", None), "detail": detail})

    def add_blocker(self, reason: str, node: ast.AST | None = None, detail: str = "") -> None:
        self.blockers.append({"reason": reason, "line": getattr(node, "lineno", None), "detail": detail})

    def _proven_object(self, node: ast.AST, kind: str | None = None) -> bool:
        name = dotted(node)
        if kind == "workbook":
            return name in self.workbooks
        if kind == "worksheet":
            return name in self.worksheets
        if kind == "cell":
            return name in self.cells
        return name in self.workbooks | self.worksheets | self.cells

    def _resolve_assign(self, target: ast.AST, value: ast.AST) -> None:
        if not isinstance(target, ast.Name):
            return
        name = target.id
        if isinstance(value, ast.Call):
            fn = dotted(value.func)
            if fn.rsplit(".", 1)[-1] == "load_workbook":
                self.workbooks.add(name)
            elif fn.rsplit(".", 1)[-1] == "cell" and self._proven_object(value.func.value if isinstance(value.func, ast.Attribute) else ast.Name(id="", ctx=ast.Load()), "worksheet"):
                self.cell_functions.add(name)
        elif isinstance(value, ast.Name):
            if value.id in self.workbooks:
                self.workbooks.add(name)
            if value.id in self.worksheets:
                self.worksheets.add(name)
            if value.id in self.cells:
                self.cells.add(name)
            if value.id in self.cell_functions:
                self.cell_functions.add(name)
        elif isinstance(value, ast.Attribute):
            if value.attr == "cell" and self._proven_object(value.value, "worksheet"):
                self.cell_functions.add(name)
        elif isinstance(value, ast.Subscript):
            base = value.value
            if self._proven_object(base, "workbook") and isinstance(value.slice, ast.Constant) and isinstance(value.slice.value, str):
                self.worksheets.add(name)
            elif self._proven_object(base, "worksheet") and isinstance(value.slice, ast.Constant) and isinstance(value.slice.value, str) and ":" not in value.slice.value:
                self.cells.add(name)

    def _walk_statements(self, body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    self._resolve_assign(target, stmt.value)
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                self._resolve_assign(stmt.target, stmt.value)
            elif isinstance(stmt, (ast.For, ast.While, ast.If, ast.With, ast.Try)):
                bodies: list[list[ast.stmt]] = []
                if hasattr(stmt, "body"): bodies.append(stmt.body)
                if hasattr(stmt, "orelse"): bodies.append(stmt.orelse)
                if isinstance(stmt, ast.Try):
                    bodies.extend(h.body for h in stmt.handlers)
                    bodies.append(stmt.finalbody)
                for b in bodies:
                    self._walk_statements(b)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Definitions are intentionally conservative and do not enter
                # the admitted set; callers may observe object identity.
                self.add_blocker("OBJECT_ESCAPE_BOUNDARY", stmt, "function definition")

    def _load_mode_blockers(self) -> None:
        assert self.tree is not None
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call) or dotted(node.func).rsplit(".", 1)[-1] != "load_workbook":
                continue
            for kw in node.keywords:
                if kw.arg == "data_only" and is_true(kw.value): self.add_blocker("DATA_ONLY_BOUNDARY", node)
                elif kw.arg in {"read_only", "write_only"} and is_true(kw.value): self.add_blocker("LOAD_OPTION_BOUNDARY", node, kw.arg)
                elif kw.arg not in {"data_only", "read_only", "write_only"}:
                    self.add_blocker("LOAD_OPTION_BOUNDARY", node, kw.arg)
            # The first positional argument is the required workbook
            # filename.  A0's lexical rule was not allowed to reinterpret it
            # as an unsupported load option.  Only additional positional
            # arguments are outside the frozen loader contract.
            if len(node.args) > 1:
                self.add_blocker("LOAD_OPTION_BOUNDARY", node, "additional positional load option")

    def analyze(self) -> dict[str, Any]:
        if not self.source or not self.openpyxl_loaded:
            return {"decision": "PREDECLARED_REAL_OPENPYXL", "reason": "source unavailable or no openpyxl", "categories": [], "blockers": [{"reason": "STATIC_ANALYSIS_UNCERTAINTY"}], "parse_ok": False}
        if self.tree is None:
            return {"decision": "PREDECLARED_REAL_OPENPYXL", "reason": "syntax parse failed", "categories": [], "blockers": [{"reason": "STATIC_ANALYSIS_UNCERTAINTY", "detail": self.parse_error}], "parse_ok": False}
        self._walk_statements(self.tree.body)
        self._load_mode_blockers()
        lexical = self.a0_lexical_matches()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and ":" in node.value:
                self.add_category("STRING_LITERAL_WITH_COLON", node, node.value[:120])
            if isinstance(node, ast.Subscript):
                base = node.value
                if self._proven_object(base, "worksheet"):
                    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                        if ":" in node.slice.value:
                            self.add_category("WORKBOOK_RANGE_SUBSCRIPT", node, dotted(base))
                            self.add_blocker("RANGE_OBJECT_BOUNDARY", node, "explicit worksheet range")
                        else:
                            self.add_category("WORKBOOK_SINGLE_CELL_SUBSCRIPT", node, dotted(base))
                    elif isinstance(node.slice, ast.Slice):
                        self.add_category("WORKBOOK_RANGE_SUBSCRIPT", node, dotted(base))
                        self.add_blocker("RANGE_OBJECT_BOUNDARY", node, "worksheet slice")
                    else:
                        self.add_category("UNKNOWN_DYNAMIC_SUBSCRIPT", node, dotted(base))
                        self.add_blocker("STATIC_ANALYSIS_UNCERTAINTY", node, "dynamic worksheet subscript")
                elif self._proven_object(base, "workbook"):
                    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                        self.add_category("WORKBOOK_SINGLE_CELL_SUBSCRIPT", node, "workbook sheet lookup")
                    else:
                        self.add_category("UNKNOWN_DYNAMIC_SUBSCRIPT", node, "dynamic workbook lookup")
                        self.add_blocker("STATIC_ANALYSIS_UNCERTAINTY", node, "dynamic workbook subscript")
                elif isinstance(node.slice, ast.Slice):
                    self.add_category("PYTHON_SEQUENCE_SLICE", node, dotted(base))
                elif isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and ":" in node.slice.value:
                    self.add_category("STRING_LITERAL_WITH_COLON", node, "mapping/string key")
            if isinstance(node, ast.Call):
                fn = dotted(node.func)
                leaf = fn.rsplit(".", 1)[-1]
                receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
                if leaf == "cell" and ((receiver is not None and self._proven_object(receiver, "worksheet")) or fn in self.cell_functions or (isinstance(node.func, ast.Name) and node.func.id in self.cell_functions)):
                    self.add_category("WORKSHEET_CELL_CALL", node, fn)
                if leaf == "iter_rows" and receiver is not None and self._proven_object(receiver, "worksheet"):
                    values_only = next((kw.value for kw in node.keywords if kw.arg == "values_only"), None)
                    if is_true(values_only):
                        self.add_category("ITER_ROWS_VALUES_ONLY", node, fn)
                    else:
                        self.add_category("CELL_OBJECT_ITERATION", node, fn)
                        self.add_blocker("CELL_OBJECT_ITERATION_BOUNDARY", node)
                if leaf == "iter_cols":
                    self.add_category("CELL_OBJECT_ITERATION", node, fn)
                    self.add_blocker("CELL_OBJECT_ITERATION_BOUNDARY", node)
                if leaf in {"dir", "getattr", "eval", "exec"} and any(self._proven_object(arg) for arg in node.args):
                    self.add_blocker("STATIC_ANALYSIS_UNCERTAINTY", node, "dynamic object inspection")
                if any(self._proven_object(arg) for arg in node.args):
                    self.add_blocker("OBJECT_ESCAPE_BOUNDARY", node, "workbook-shaped object passed to function")
            if isinstance(node, ast.Attribute):
                if node.attr in {"worksheets", "active"} and self._proven_object(node.value, "workbook"):
                    self.add_blocker("WORKBOOK_WORKSHEETS_BOUNDARY" if node.attr == "worksheets" else "RICH_OBJECT_BOUNDARY", node)
                if node.attr == "sheet_state" and self._proven_object(node.value, "worksheet"):
                    self.add_blocker("WORKSHEET_SHEET_STATE_BOUNDARY", node)
                if node.attr in self.RICH and self._proven_object(node.value):
                    self.add_blocker("RICH_OBJECT_BOUNDARY", node, node.attr)
            if isinstance(node, ast.Call) and dotted(node.func).rsplit(".", 1)[-1] == "save":
                self.add_blocker("WRITE_BOUNDARY", node)
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = []
                if isinstance(node, ast.Assign): targets = node.targets
                else: targets = [node.target]
                for target in targets:
                    if isinstance(target, (ast.Attribute, ast.Subscript)) and self._proven_object(target.value if isinstance(target, ast.Subscript) else target.value):
                        self.add_blocker("READ_WRITE_MIXED_BOUNDARY", node)
            if isinstance(node, ast.Return) and node.value is not None and self._proven_object(node.value):
                self.add_blocker("OBJECT_ESCAPE_BOUNDARY", node)
        # Preserve every non-range A0 lexical rejection.  Only the lexical
        # range/slice rejection is replaced by the AST proof above.
        for item in lexical:
            if item["reason"] != "range/slice object path":
                self.add_blocker(item["reason"], None, "A0 lexical boundary preserved")
        # Deduplicate and choose stable precedence.
        unique = []
        seen = set()
        for b in self.blockers:
            key = (b.get("reason"), b.get("line"), b.get("detail"))
            if key not in seen:
                unique.append(b); seen.add(key)
        self.blockers = unique
        if self.blockers:
            return {"decision": "PREDECLARED_REAL_OPENPYXL", "reason": self.blockers[0]["reason"], "categories": self.categories, "blockers": self.blockers, "parse_ok": True, "lexical_matches": lexical, "proven_workbooks": sorted(self.workbooks), "proven_worksheets": sorted(self.worksheets), "proven_cells": sorted(self.cells), "proven_cell_functions": sorted(self.cell_functions)}
        return {"decision": "A1_ADMIT", "reason": "AST proves no unsupported workbook range/object behavior and all A0 rules pass", "categories": self.categories, "blockers": [], "parse_ok": True, "lexical_matches": lexical, "proven_workbooks": sorted(self.workbooks), "proven_worksheets": sorted(self.worksheets), "proven_cells": sorted(self.cells), "proven_cell_functions": sorted(self.cell_functions)}

    def a0_lexical_matches(self) -> list[dict[str, Any]]:
        low = self.source.lower()
        matches = []
        needles = [
            (".save(", "mutation/save"), ("data_only=true", "data_only"), ("data_only = true", "data_only"),
            ("read_only=true", "read_only"), ("read_only = true", "read_only"), ("write_only", "write_only"),
            ("zipfile", "package access"), (".font", "rich object"), (".fill", "rich object"),
            (".border", "rich object"), (".alignment", "rich object"), (".comment", "rich object"),
            (".hyperlink", "rich object"), (".number_format", "rich object"), (".style", "rich object"),
            (".merged_cells", "merged/rich object"), (".tables", "rich object"), (".defined_names", "rich object"),
            (".worksheets", "unsupported worksheet collection"), (".active", "unsupported active worksheet"),
            (".iter_rows(", "iterator shape not statically proven"), (".iter_cols(", "unsupported iterator"),
            (".values", "unsupported worksheet values iterator"), (".value =", "cell mutation"), (".value=", "cell mutation"),
            ("eval(", "dynamic execution"), ("exec(", "dynamic execution"), ("def ", "function/object escape risk"),
            ("lambda", "closure/object escape risk"),
        ]
        for needle, reason in needles:
            if needle in low:
                matches.append({"match": needle, "reason": reason})
        if re.search(r"\[[^\]]*:[^\]]*\]", self.source):
            matches.append({"match": "bracket-colon lexical regex", "reason": "range/slice object path"})
        if re.search(r"(?:wb|ws|cell|c)\s*\[[^\]]+\]\s*=", self.source):
            matches.append({"match": "workbook/cell assignment regex", "reason": "workbook/cell mutation"})
        return matches


def classify(source: str | None) -> dict[str, Any]:
    a = A1Analyzer(source)
    return a.analyze()
