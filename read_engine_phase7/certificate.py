"""Conservative terminal-cell-observation proof for the Phase-7 experiment."""
from __future__ import annotations

import ast
from typing import Any

TERMINALS = frozenset({"value", "data_type", "coordinate", "row", "column"})


def certify(source: str, admission: dict[str, Any]) -> dict[str, Any]:
    if admission.get("decision") != "A1_ADMIT":
        return {"certified": False, "reason": "NOT_ADMITTED", "cell_calls": 0}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"certified": False, "reason": "PARSE_FAILED", "cell_calls": 0}
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    sheets = set(admission.get("proven_worksheets", []))
    calls = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in sheets:
            return {"certified": False, "reason": "WORKSHEET_SUBSCRIPT", "cell_calls": calls,
                    "line": getattr(node, "lineno", None)}
        if not isinstance(node, ast.Attribute) or node.attr != "cell":
            continue
        parent = parents.get(node)
        terminal = parents.get(parent) if parent is not None else None
        if (not isinstance(parent, ast.Call) or parent.func is not node
                or not isinstance(terminal, ast.Attribute) or terminal.value is not parent
                or not isinstance(terminal.ctx, ast.Load) or terminal.attr not in TERMINALS):
            return {"certified": False, "reason": "CELL_OBJECT_NOT_TERMINAL_SCALAR",
                    "cell_calls": calls, "line": getattr(node, "lineno", None)}
        calls += 1
    return {"certified": True, "reason": "ALL_CELL_CALLS_TERMINAL_SCALAR", "cell_calls": calls,
            "terminals": sorted(TERMINALS)}
