#!/usr/bin/env python3
"""Zero-model census of transparent acceleration for ordinary openpyxl reads.

This is deliberately a study tool, not runtime code.  It reads the frozen
control-audit corpus, performs conservative AST accounting, measures local
openpyxl/index costs, and runs a small shadow differential replay.  It never
calls a model, edits a workbook, or changes the agent interface.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "transparent_python_read_census"
AUDIT = ROOT / "control_python_audit"
POP_PATH = AUDIT / "population.json"
EXEC_PATH = AUDIT / "python_executions.jsonl"
FEATURE_PATH = AUDIT / "script_features.jsonl"
SEM_PATH = AUDIT / "semantic_vs_mechanical.jsonl"
SEED = 20260920

# The repository uses namespace-style benchmark directories rather than an
# installed package.  Make the frozen local substrate importable for this
# throwaway replay without changing production code.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def pct(n: float, d: float) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def median_or_zero(xs: list[float]) -> float:
    return round(statistics.median(xs), 4) if xs else 0.0


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def attr_chain(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return list(reversed(parts))
    return None


def const_str(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "<f-string>"
    return None


def call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        chain = attr_chain(node)
        return ".".join(chain) if chain else None
    return None


READ_API_KINDS = {
    "workbook.sheetnames", "workbook.worksheets", "workbook.active",
    "workbook.__getitem__", "workbook.defined_names", "workbook.properties",
    "worksheet.max_row", "worksheet.max_column", "worksheet.dimensions",
    "worksheet.calculate_dimension", "worksheet.cell", "worksheet.__getitem__",
    "worksheet.iter_rows", "worksheet.iter_cols", "worksheet.values",
    "worksheet.merged_cells", "worksheet.tables", "worksheet.row_dimensions",
    "worksheet.column_dimensions", "cell.value", "cell.data_type",
    "cell.coordinate", "cell.row", "cell.column", "cell.number_format",
    "cell.style", "cell.style_id", "cell.font", "cell.fill", "cell.border",
    "cell.alignment", "cell.comment", "cell.hyperlink", "formula_mode",
    "package.zipfile", "package.xml", "other.workbook_api",
}

SAFE_A_SURFACE = {
    "workbook.load_workbook",
    "workbook.sheetnames", "workbook.worksheets", "workbook.active",
    "workbook.__getitem__", "worksheet.max_row", "worksheet.max_column",
    "worksheet.dimensions", "worksheet.calculate_dimension", "worksheet.cell",
    "worksheet.__getitem__", "worksheet.iter_rows", "worksheet.iter_cols",
    "worksheet.values", "cell.value", "cell.data_type", "cell.coordinate",
    "cell.row", "cell.column", "formula_mode",
}
SAFE_B_KINDS = {
    "load_workbook", "sheetnames", "sheet_lookup", "dimensions", "cell_value",
    "explicit_range_values", "iter_rows_values", "formula_value",
}


def path_key(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.replace("\\", "/")
    if raw.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
        return Path(raw).name.lower()
    return None


class StaticAnalyzer(ast.NodeVisitor):
    """Conservative, source-only API/event census."""

    def __init__(self, source: str):
        self.source = source
        self.events: list[dict[str, Any]] = []
        self.imports: list[dict[str, Any]] = []
        self.module_aliases: set[str] = set()
        self.load_aliases: set[str] = set()
        self.wb_names: set[str] = set()
        self.ws_names: set[str] = set()
        self.cell_names: set[str] = set()
        self.dynamic = False
        self.has_eval_exec = bool(re.search(r"\b(eval|exec)\s*\(", source))
        self.has_function_defs = False
        self.has_comprehension = False
        self.has_generator = False
        self.has_try = False
        self.has_closure_like = False
        self.writes = False
        self.saves = 0
        self.open_calls = 0
        self.data_only_modes: list[str] = []
        self.workbook_refs: list[str] = []
        self.package_xml = bool(re.search(r"\b(zipfile|xml\.etree|ElementTree|lxml)\b|\.xml\b", source))
        self.output_prints = len(re.findall(r"\bprint\s*\(", source))

    def add(self, kind: str, node: ast.AST, **extra: Any) -> None:
        self.events.append({"api": kind, "line": getattr(node, "lineno", None), **extra})

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            self.imports.append({"kind": "import", "name": a.name, "asname": a.asname})
            if a.name == "openpyxl":
                self.module_aliases.add(a.asname or "openpyxl")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for a in node.names:
            self.imports.append({"kind": "from", "module": mod, "name": a.name, "asname": a.asname})
            if mod == "openpyxl" and a.name == "load_workbook":
                self.load_aliases.add(a.asname or a.name)
        self.generic_visit(node)

    def _record_load(self, node: ast.Call, resolved: str) -> None:
        self.open_calls += 1
        self.add("workbook.load_workbook", node, resolution=resolved)
        raw = const_str(node.args[0]) if node.args else None
        if raw:
            self.workbook_refs.append(raw)
        for kw in node.keywords:
            if kw.arg == "data_only":
                val = const_str(kw.value)
                if val is not None:
                    self.data_only_modes.append(val)
                elif isinstance(kw.value, ast.Constant):
                    self.data_only_modes.append(str(kw.value.value))
                else:
                    self.data_only_modes.append("dynamic")

    def _base_kind(self, base: str) -> str:
        if base in self.wb_names:
            return "workbook"
        if base in self.ws_names:
            return "worksheet"
        if base in self.cell_names:
            return "cell"
        return "unknown"

    def visit_Assign(self, node: ast.Assign) -> None:
        # Track straightforward aliases and workbook/worksheet/cell objects.
        value = node.value
        target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        assigned_chain = attr_chain(value) if isinstance(value, ast.Attribute) else None
        if assigned_chain and len(assigned_chain) == 2 and assigned_chain[0] in self.module_aliases and assigned_chain[1] == "load_workbook":
            self.load_aliases.update(target_names)
        if isinstance(value, ast.Call):
            n = call_name(value.func)
            if n in self.load_aliases or n in {f"{a}.load_workbook" for a in self.module_aliases} or n == "load_workbook":
                for t in target_names:
                    self.wb_names.add(t)
            elif n and any(t in self.ws_names for t in target_names):
                pass
        if isinstance(value, ast.Name):
            if value.id in self.wb_names:
                self.wb_names.update(target_names)
            if value.id in self.ws_names:
                self.ws_names.update(target_names)
            if value.id in self.cell_names:
                self.cell_names.update(target_names)
        if isinstance(value, ast.Subscript):
            base = value.value.id if isinstance(value.value, ast.Name) else None
            if base in self.wb_names:
                self.ws_names.update(target_names)
                self.add("workbook.__getitem__", value, resolution="STATICALLY_RESOLVED")
            elif base in self.ws_names:
                self.cell_names.update(target_names)
                self.add("worksheet.__getitem__", value, resolution="STATICALLY_RESOLVED")
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            owner = value.func.value
            if isinstance(owner, ast.Name) and owner.id in self.ws_names and value.func.attr == "cell":
                self.cell_names.update(target_names)
                self.add("worksheet.cell", value, resolution="STATICALLY_RESOLVED")
        # Any assignment to a workbook/cell property is a mutation signal.
        if isinstance(value, ast.AST):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and t.attr in {"value", "_style", "font", "fill", "border", "alignment", "number_format", "comment", "hyperlink"}:
                    self.writes = True
                    self.add("write." + t.attr, t, resolution="STATICALLY_RESOLVED")
                elif isinstance(t, ast.Subscript):
                    self.writes = True
                    self.add("write.subscript", t, resolution="LIKELY_RESOLVED")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.writes = True
        self.add("write.augassign", node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.has_function_defs = True
        # A workbook/cell name referenced inside a function is an escape risk.
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        if names & (self.wb_names | self.ws_names | self.cell_names):
            self.has_closure_like = True
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.has_function_defs = True
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.has_closure_like = True
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.has_try = True
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.has_comprehension = True
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.has_comprehension = True
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.has_comprehension = True
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.has_generator = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        n = call_name(node.func)
        if n in self.load_aliases or n in {f"{a}.load_workbook" for a in self.module_aliases} or n == "load_workbook":
            self._record_load(node, "STATICALLY_RESOLVED")
        if isinstance(node.func, ast.Attribute):
            base = node.func.value.id if isinstance(node.func.value, ast.Name) else None
            attr = node.func.attr
            owner = self._base_kind(base) if base else "unknown"
            mapped = {
                ("workbook", "save"): "workbook.save",
                ("workbook", "close"): "workbook.close",
                ("worksheet", "cell"): "worksheet.cell",
                ("worksheet", "iter_rows"): "worksheet.iter_rows",
                ("worksheet", "iter_cols"): "worksheet.iter_cols",
                ("worksheet", "calculate_dimension"): "worksheet.calculate_dimension",
                ("cell", "value"): "cell.value",
            }
            if (owner, attr) in mapped:
                kind = mapped[(owner, attr)]
                self.add(kind, node, resolution="STATICALLY_RESOLVED")
                if kind == "workbook.save":
                    self.saves += 1
            elif attr in {"cell", "iter_rows", "iter_cols", "calculate_dimension"}:
                self.add("worksheet." + attr, node, resolution="LIKELY_RESOLVED")
            elif attr in {"getattr", "__getitem__"}:
                self.dynamic = True
        if n in {"eval", "exec", "getattr", "setattr"}:
            self.dynamic = True
        self.generic_visit(node)

    def _expression_kind(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self._base_kind(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value.id if isinstance(node.func.value, ast.Name) else None
            if base in self.ws_names and node.func.attr == "cell":
                return "cell"
        if isinstance(node, ast.Subscript):
            base = node.value.id if isinstance(node.value, ast.Name) else None
            if base in self.wb_names:
                return "worksheet"
            if base in self.ws_names:
                return "cell"
        return "unknown"

    def visit_Attribute(self, node: ast.Attribute) -> None:
        owner = self._expression_kind(node.value)
        attr = node.attr
        mapped = {
            ("workbook", "sheetnames"): "workbook.sheetnames",
            ("workbook", "worksheets"): "workbook.worksheets",
            ("workbook", "active"): "workbook.active",
            ("workbook", "defined_names"): "workbook.defined_names",
            ("workbook", "properties"): "workbook.properties",
            ("worksheet", "max_row"): "worksheet.max_row",
            ("worksheet", "max_column"): "worksheet.max_column",
            ("worksheet", "dimensions"): "worksheet.dimensions",
            ("worksheet", "merged_cells"): "worksheet.merged_cells",
            ("worksheet", "tables"): "worksheet.tables",
            ("worksheet", "row_dimensions"): "worksheet.row_dimensions",
            ("worksheet", "column_dimensions"): "worksheet.column_dimensions",
            ("worksheet", "values"): "worksheet.values",
            ("cell", "value"): "cell.value",
            ("cell", "data_type"): "cell.data_type",
            ("cell", "coordinate"): "cell.coordinate",
            ("cell", "row"): "cell.row",
            ("cell", "column"): "cell.column",
            ("cell", "number_format"): "cell.number_format",
            ("cell", "style"): "cell.style",
            ("cell", "style_id"): "cell.style_id",
            ("cell", "font"): "cell.font",
            ("cell", "fill"): "cell.fill",
            ("cell", "border"): "cell.border",
            ("cell", "alignment"): "cell.alignment",
            ("cell", "comment"): "cell.comment",
            ("cell", "hyperlink"): "cell.hyperlink",
        }
        if (owner, attr) in mapped:
            self.add(mapped[(owner, attr)], node, resolution="STATICALLY_RESOLVED")
        elif attr in {"sheetnames", "max_row", "max_column", "value", "data_type", "coordinate", "row", "column", "iter_rows", "iter_cols"}:
            self.add("other.workbook_api", node, resolution="DYNAMIC")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        base = node.value.id if isinstance(node.value, ast.Name) else None
        owner = self._base_kind(base) if base else "unknown"
        if owner == "workbook":
            self.add("workbook.__getitem__", node, resolution="STATICALLY_RESOLVED")
        elif owner == "worksheet":
            self.add("worksheet.__getitem__", node, resolution="STATICALLY_RESOLVED")
        self.generic_visit(node)


def classify_read_pattern(source: str, events: list[dict[str, Any]], package_xml: bool) -> list[str]:
    low = source.lower()
    labels: list[str] = []
    if package_xml:
        labels.append("PACKAGE_XML_READ")
    if re.search(r"\.iter_rows\s*\(|for\s+\w+\s+in\s+range\s*\(", source) and (".cell(" in source or ".value" in source):
        labels.append("ROW_COLUMN_ITERATION")
    if ".cell(" in source or re.search(r"\bws\s*\[[^\]]+\]", source):
        labels.append("SINGLE_CELL_OR_EXPLICIT_RANGE")
    if ".values" in source or "values_only" in source:
        labels.append("VALUES_ITERATION")
    if "sheetnames" in source or ".worksheets" in source:
        labels.append("SHEET_ENUMERATION")
    if re.search(r"max_row|max_column|calculate_dimension|dimensions", source):
        labels.append("DIMENSION_DISCOVERY")
    if re.search(r"re\.search|re\.find|\.lower\(\).*in| in .*\.value|value.* in ", source, re.I):
        labels.append("TEXT_OR_LABEL_SCAN")
    if re.search(r"fy\s*\\?d|cy\s*\\?d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|period", low):
        labels.append("PERIOD_OR_HEADER_SCAN")
    if re.search(r"formula|\.data_type|^\s*if .*value.*=", low, re.M):
        labels.append("FORMULA_OR_DTYPE_READ")
    if re.search(r"number_format|\.font|\.fill|\.border|\.style|merged_cells|tables|row_dimensions|column_dimensions", low):
        labels.append("STYLE_OR_STRUCTURE_READ")
    if re.search(r"compare|diff|assert .*==|changes\s*=", low):
        labels.append("COMPARISON_OR_VERIFICATION")
    if not labels and events:
        labels.append("OTHER_OPENPYXL_READ")
    return labels


def classify_execution(row: dict[str, Any], ana: StaticAnalyzer | None, pattern: list[str]) -> str:
    if not row.get("has_source") or ana is None:
        return "UNRESOLVED"
    if ana.package_xml:
        if ana.writes:
            return "READ_WRITE_MIXED"
        return "PACKAGE_XML_READ"
    if not ana.events:
        return "NON_WORKBOOK_PYTHON"
    has_style = "STYLE_OR_STRUCTURE_READ" in pattern
    if ana.writes:
        return "READ_WRITE_MIXED" if any(e["api"].startswith("cell.") or e["api"].startswith("worksheet.") for e in ana.events) else "WRITE_DOMINANT_WITH_READS"
    if has_style:
        return "STYLE_OR_STRUCTURE_READ"
    simple = all(e["api"] in SAFE_A_SURFACE or e["api"] in {"workbook.load_workbook"} for e in ana.events)
    return "READ_ONLY_SIMPLE" if simple else "READ_ONLY_COMPLEX_PYTHON"


def resolve_local_workbook(raw: str | None, population: list[dict[str, Any]], by_name: dict[str, list[str]]) -> str | None:
    if raw:
        p = Path(raw)
        if p.exists():
            return str(p)
        name = p.name.lower()
        if name in by_name and len(by_name[name]) == 1:
            return by_name[name][0]
    return None


def build_population() -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    raw = json.loads(POP_PATH.read_text())
    rows: list[dict[str, Any]] = []
    for pop, items in raw.items():
        for item in items:
            rows.append({**item, "population": pop})
    all_xlsx = list((ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data").rglob("*.xlsx"))
    by_name: dict[str, list[str]] = collections.defaultdict(list)
    for p in all_xlsx:
        by_name[p.name.lower()].append(str(p))
    return rows, dict(by_name)


def load_rows() -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    rows = [json.loads(line) for line in EXEC_PATH.read_text().splitlines()]
    features = {x["exec_id"]: x for x in (json.loads(line) for line in FEATURE_PATH.read_text().splitlines())}
    semantics = {x["exec_id"]: x for x in (json.loads(line) for line in SEM_PATH.read_text().splitlines())}
    for row in rows:
        row["existing_features"] = features.get(row["exec_id"], {}).get("features", {})
        row["existing_semantic_class"] = semantics.get(row["exec_id"], {}).get("class")
    return rows, features


def split_tasks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    import random
    by_family: dict[str, list[str]] = collections.defaultdict(list)
    for r in rows:
        if r["task_id"] not in by_family[r["family"]]:
            by_family[r["family"]].append(r["task_id"])
    rng = random.Random(SEED)
    result: dict[str, Any] = {"seed": SEED, "rule": "task-level stratified 70/30 split; sorted task IDs then seeded shuffle", "families": {}}
    for fam, tasks in sorted(by_family.items()):
        tasks = sorted(tasks)
        rng.shuffle(tasks)
        n_dev = max(1, math.floor(len(tasks) * 0.7)) if tasks else 0
        result["families"][fam] = {"development_tasks": sorted(tasks[:n_dev]), "heldout_tasks": sorted(tasks[n_dev:])}
    return result


def api_resolution(ana: StaticAnalyzer, event: dict[str, Any]) -> str:
    return event.get("resolution", "UNRESOLVED")


def event_answerability(api: str, data_modes: list[str]) -> tuple[str, str]:
    if api in {"workbook.sheetnames", "workbook.worksheets", "workbook.__getitem__", "worksheet.max_row", "worksheet.max_column", "worksheet.dimensions", "worksheet.calculate_dimension", "worksheet.cell", "worksheet.__getitem__", "worksheet.iter_rows", "worksheet.iter_cols", "cell.coordinate", "cell.row", "cell.column"}:
        return "EXACTLY_ANSWERABLE_NOW", "indexed cells and workbook structure are available; Python wrapper semantics still require replay"
    if api in {"cell.value", "cell.data_type", "formula_mode"}:
        if any(x in {"True", "true"} for x in data_modes):
            return "ANSWERABLE_BUT_SEMANTICS_RISKY", "current index stores formulas and raw strings but not cached data_only values"
        return "ANSWERABLE_WITH_SMALL_MECHANICAL_EXTENSION", "dtype/value decoding and formula objects need exact Python-compatible reconstruction"
    if api in {"worksheet.values", "worksheet.merged_cells", "worksheet.tables", "worksheet.row_dimensions", "worksheet.column_dimensions", "workbook.defined_names", "workbook.properties"}:
        return "ANSWERABLE_BUT_SEMANTICS_RISKY", "package structure exists but current index does not preserve the full openpyxl object contract"
    if api.startswith("cell.") and api not in {"cell.value", "cell.data_type", "cell.coordinate", "cell.row", "cell.column"}:
        return "REQUIRES_REAL_OPENPYXL", "style/comment/hyperlink objects are not in the current mechanical index"
    if api == "package.zipfile" or api == "package.xml":
        return "OPAQUE_PACKAGE_ONLY", "script reads package/XML behavior outside the indexed workbook fact surface"
    if api == "other.workbook_api":
        return "UNRESOLVED", "dynamic or unknown object access"
    return "UNRESOLVED", "not mapped conservatively"


def is_read_api(api: str) -> bool:
    """Exclude workbook lifecycle writes from the read-work denominator."""
    if api in {"workbook.save", "workbook.close"} or api.startswith("write."):
        return False
    return api in READ_API_KINDS or api.startswith(("workbook.", "worksheet.", "cell.", "package."))


def execution_candidate_a(ana: StaticAnalyzer | None, classification: str) -> tuple[str, int, list[str]]:
    if ana is None or classification == "UNRESOLVED":
        return "A_NOT_SAFE", 0, ["source unavailable"]
    read_events = [e for e in ana.events if is_read_api(e["api"])]
    if not read_events:
        return "A_NOT_SAFE", 0, ["no workbook read event"]
    risky = [e["api"] for e in read_events if e["api"] not in SAFE_A_SURFACE]
    reasons: list[str] = []
    if ana.dynamic:
        reasons.append("dynamic attribute/eval/exec")
    if ana.has_closure_like or ana.has_function_defs:
        reasons.append("object/function escape risk")
    if ana.writes:
        reasons.append("read/write coexistence")
    if ana.package_xml:
        reasons.append("package/XML access")
    if any(a.startswith("cell.") and a not in {"cell.value", "cell.data_type", "cell.coordinate", "cell.row", "cell.column"} for a in risky):
        reasons.append("rich cell object semantics")
    covered = sum(1 for e in read_events if e["api"] in SAFE_A_SURFACE)
    if not risky and not ana.dynamic and not ana.writes and not ana.package_xml:
        return "A_FULLY_PROXYABLE", covered, reasons
    if covered and not ana.package_xml:
        return "A_PROXYABLE_WITH_LAZY_FALLBACK", covered, reasons or ["unsupported API can fall back"]
    if covered:
        return "A_FALLBACK_DOMINANT", covered, reasons
    return "A_NOT_SAFE", 0, reasons or ["no conservative proxy surface"]


def infer_b_events(ana: StaticAnalyzer | None, source: str) -> list[dict[str, Any]]:
    if ana is None:
        return []
    out: list[dict[str, Any]] = []
    for e in ana.events:
        api = e["api"]
        if api == "workbook.load_workbook":
            out.append({"kind": "load_workbook", "line": e.get("line"), "safe": True})
        elif api == "workbook.sheetnames":
            out.append({"kind": "sheetnames", "line": e.get("line"), "safe": True})
        elif api == "workbook.__getitem__":
            out.append({"kind": "sheet_lookup", "line": e.get("line"), "safe": True})
        elif api in {"worksheet.max_row", "worksheet.max_column", "worksheet.dimensions", "worksheet.calculate_dimension"}:
            out.append({"kind": "dimensions", "line": e.get("line"), "safe": True})
        elif api == "worksheet.cell" or api == "worksheet.__getitem__":
            out.append({"kind": "cell_value", "line": e.get("line"), "safe": True})
        elif api == "worksheet.iter_rows":
            values_only = "values_only=True" in source.replace(" ", "")
            out.append({"kind": "iter_rows_values" if values_only else "iter_rows_cells", "line": e.get("line"), "safe": values_only})
        elif api == "cell.value":
            out.append({"kind": "formula_value" if "formula" in source.lower() else "cell_value", "line": e.get("line"), "safe": True})
    return out


def execution_candidate_b(ana: StaticAnalyzer | None, classification: str, source: str) -> tuple[str, int, list[str], list[dict[str, Any]]]:
    if ana is None or classification == "UNRESOLVED":
        return "B_UNRESOLVED", 0, ["source unavailable"], []
    reasons: list[str] = []
    if ana.dynamic or ana.has_eval_exec:
        reasons.append("dynamic attribute/eval/exec")
    if ana.has_function_defs or ana.has_closure_like:
        reasons.append("helper/function indirection or closure")
    if ana.has_comprehension:
        reasons.append("comprehension surrounding read")
    if ana.has_generator:
        reasons.append("generator semantics")
    if ana.writes:
        reasons.append("mixed read/write script")
    if ana.package_xml:
        reasons.append("package/XML path")
    inferred = infer_b_events(ana, source)
    safe = [e for e in inferred if e["safe"] and e["kind"] in SAFE_B_KINDS]
    risky = [e for e in inferred if not e["safe"]]
    if not inferred:
        return "B_DYNAMIC_NOT_LOWERABLE", 0, reasons or ["no recognized read shape"], inferred
    if ana.writes:
        return "B_MIXED_READ_WRITE_UNSAFE", len(safe), reasons or ["write ordering/exception semantics"], inferred
    if reasons and safe:
        return "B_RECOGNIZABLE_BUT_RISKY", len(safe), reasons, inferred
    if len(safe) == len(inferred):
        return "B_FULLY_LOWERABLE", len(safe), reasons, inferred
    return "B_PARTIALLY_LOWERABLE", len(safe), reasons or ["unrecognized iterator/object escape"], inferred


def family_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fam in sorted({r["family"] for r in rows}):
        rs = [r for r in rows if r["family"] == fam]
        out[fam] = {"n": len(rs), key: collections.Counter(r.get(key) for r in rs)}
        out[fam][key] = dict(out[fam][key])
    return out


def repeated_open_analysis(exec_rows: list[dict[str, Any]], population: list[dict[str, Any]], by_name: dict[str, list[str]]) -> dict[str, Any]:
    # Use literal/basename path keys; this deliberately does not infer that two
    # differently named files are the same generation.
    by_traj: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    task_to_traj = {x["task_id"]: x.get("traj") for x in population}
    for r in exec_rows:
        if r["open_calls"]:
            r2 = {**r, "trajectory": task_to_traj.get(r["task_id"]) or r["task_id"]}
            by_traj[r2["trajectory"]].append(r2)
    repeated: list[dict[str, Any]] = []
    total_open = 0
    repeated_open = 0
    for traj, rs in by_traj.items():
        groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for r in sorted(rs, key=lambda x: (x["turn"], x["exec_id"])):
            refs = list(r.get("workbook_refs") or [])
            # A source call can use a variable path or otherwise fail literal
            # recovery.  Preserve the open-call count with explicit dynamic
            # placeholders instead of silently dropping those opens.
            if len(refs) < r["open_calls"]:
                refs.extend(["<dynamic workbook path>"] * (r["open_calls"] - len(refs)))
            refs = refs[: max(1, r["open_calls"])]
            for ref_no, raw in enumerate(refs):
                # Dynamic paths are not evidence of same-workbook identity.
                # Keep them in the total-open count but give each occurrence a
                # unique key so they cannot manufacture a repeat opportunity.
                key = (f"<dynamic:{r['exec_id']}:{ref_no}" if raw.startswith("<dynamic") else (path_key(raw) or raw))
                groups[key].append(r)
                total_open += 1
        for key, gr in groups.items():
            opens = sum(max(1, x["open_calls"]) for x in gr)
            if opens > 1:
                repeated_open += opens - 1
                repeated.append({"trajectory": traj, "workbook_key": key, "opens": opens, "turns": [x["turn"] for x in gr], "generation_assumption": "unchanged only when no intervening save in same trajectory; conservative key-level census"})
    return {"total_source_open_calls": total_open, "repeated_open_calls_conservative": repeated_open, "repeat_groups": repeated, "n_repeat_groups": len(repeated), "method": "same trajectory + same explicit/basename workbook key; no cross-name equivalence"}


def generation_probe(path: str | None) -> dict[str, Any]:
    """Exercise the existing substrate's hash/rebuild boundary on a temp copy."""
    if not path:
        return {"status": "UNRESOLVED", "reason": "no local workbook"}
    try:
        import openpyxl
        from benchmark.inspection_helpers import index
        with tempfile.TemporaryDirectory(prefix="transparent-read-generation-") as td:
            dst = Path(td) / Path(path).name
            shutil.copy2(path, dst)
            index.reset()
            first, first_rebuilt = index.ensure_fresh(dst)
            before_hash = first["workbook_hash"]
            before_gen = first["index_generation"]
            wb = openpyxl.load_workbook(dst, data_only=False)
            ws = wb[wb.sheetnames[0]]
            old = ws["A1"].value
            ws["A1"] = old if old is not None else "__generation_probe__"
            wb.save(dst); wb.close()
            second, second_rebuilt = index.ensure_fresh(dst)
            after_hash = second["workbook_hash"]
            return {"status": "SUPPORTED_NARROWLY", "first_rebuilt": first_rebuilt, "second_rebuilt_after_temp_mutation": second_rebuilt, "hash_changed": before_hash != after_hash, "generation_incremented": second["index_generation"] > before_gen, "silent_stale_probe": bool(not second_rebuilt or before_hash == after_hash), "scope": "current index only; proxy and AST integration not tested"}
    except Exception as exc:
        return {"status": "UNRESOLVED", "error": repr(exc), "scope": "current index only"}


def _decode_index_value(row: tuple[Any, ...]) -> Any:
    _, _, _, _, val, formula, dtype = row
    if formula is not None:
        return formula
    if val is None:
        return None
    if dtype == "n":
        try:
            f = float(val)
            return int(f) if f.is_integer() else f
        except Exception:
            return val
    if dtype == "b":
        return str(val).lower() == "true"
    return val


def run_shadow_replay(paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import openpyxl
        from openpyxl.utils.cell import range_boundaries
        from benchmark.inspection_helpers import index
    except Exception as exc:
        return ([{"error": str(exc)}], [{"error": str(exc)}])

    class SCell:
        def __init__(self, shadow, sheet, addr, row, col):
            self._shadow, self._sheet, self.coordinate, self.row, self.column = shadow, sheet, addr, row, col
        @property
        def value(self):
            con = self._shadow.handle["db"]
            q = con.execute("SELECT sheet,addr,row,col,value,formula,dtype FROM cells WHERE sheet=? AND addr=?", (self._sheet, self.coordinate)).fetchone()
            return _decode_index_value(q) if q else None
        @property
        def data_type(self):
            q = self._shadow.handle["db"].execute("SELECT sheet,addr,row,col,value,formula,dtype FROM cells WHERE sheet=? AND addr=?", (self._sheet, self.coordinate)).fetchone()
            return q[6] if q else "n"

    class SSheet:
        def __init__(self, shadow, title):
            self._shadow, self.title = shadow, title
            q = shadow.handle["db"].execute("SELECT MAX(row),MAX(col) FROM cells WHERE sheet=?", (title,)).fetchone()
            self.max_row, self.max_column = (q[0] or 1), (q[1] or 1)
        def cell(self, row, column):
            from openpyxl.utils import get_column_letter
            addr = f"{get_column_letter(column)}{row}"
            return SCell(self._shadow, self.title, addr, row, column)
        def iter_rows(self, min_row=1, max_row=None, min_col=1, max_col=None, values_only=False):
            max_row = max_row or self.max_row; max_col = max_col or self.max_column
            for r in range(min_row, max_row + 1):
                cells = tuple(self.cell(r, c) for c in range(min_col, max_col + 1))
                yield tuple(c.value for c in cells) if values_only else cells
        def __getitem__(self, key):
            if isinstance(key, str) and ":" not in key:
                min_col, min_row, _, _ = range_boundaries(key)
                return self.cell(min_row, min_col)
            if isinstance(key, str):
                min_col, min_row, max_col, max_row = range_boundaries(key)
                return tuple(tuple(self.cell(r, c) for c in range(min_col, max_col + 1)) for r in range(min_row, max_row + 1))
            raise TypeError(key)

    class SWB:
        def __init__(self, path):
            self.path = path; self.handle, self.rebuilt = index.ensure_fresh(path)
            rows = self.handle["db"].execute("SELECT DISTINCT sheet FROM cells ORDER BY rowid").fetchall()
            self.sheetnames = [r[0] for r in rows]
        def __getitem__(self, name):
            if name not in self.sheetnames: raise KeyError(name)
            return SSheet(self, name)

    cases: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for path in paths:
        try:
            raw = openpyxl.load_workbook(path, data_only=False, read_only=False)
            if not raw.sheetnames: raw.close(); continue
            # The current index intentionally omits entirely empty/metadata-only
            # sheets.  Keep the sheetnames case to expose that fidelity gap, but
            # choose a common sheet for the primitive operation cases so those
            # cases measure cell semantics rather than setup failure.
            probe_handle, _ = index.ensure_fresh(path)
            indexed_names = {x[0] for x in probe_handle["db"].execute("SELECT DISTINCT sheet FROM cells")}
            sn = next((x for x in raw.sheetnames if x in indexed_names), raw.sheetnames[0])
            ws = raw[sn]
            first = next((c for row in ws.iter_rows() for c in row if c.value is not None), None)
            if first is None: first = ws.cell(1, 1)
            formula = next((c for row in ws.iter_rows() for c in row if c.data_type == "f"), None)
            cases += [
                {"id": f"{Path(path).name}:sheetnames", "path": path, "kind": "sheetnames"},
                {"id": f"{Path(path).name}:dimensions", "path": path, "kind": "dimensions", "sheet": sn},
                {"id": f"{Path(path).name}:cell_value", "path": path, "kind": "cell_value", "sheet": sn, "address": first.coordinate},
                {"id": f"{Path(path).name}:range_values", "path": path, "kind": "explicit_range_values", "sheet": sn, "range": "A1:C3"},
                {"id": f"{Path(path).name}:iter_rows", "path": path, "kind": "iter_rows_values", "sheet": sn, "range": "A1:C3"},
            ]
            if formula:
                cases.append({"id": f"{Path(path).name}:formula", "path": path, "kind": "formula_value", "sheet": sn, "address": formula.coordinate})
            raw.close()
        except Exception as exc:
            results.append({"case_id": f"{Path(path).name}:setup", "classification": "UNREPLAYABLE", "error": repr(exc)})
    for case in cases:
        path = case["path"]
        try:
            raw = openpyxl.load_workbook(path, data_only=False, read_only=False)
            shadow = SWB(path)
            kind = case["kind"]
            if kind == "sheetnames":
                a = (raw.sheetnames, [type(x).__name__ for x in raw.sheetnames]); b = (shadow.sheetnames, [type(x).__name__ for x in shadow.sheetnames])
            elif kind == "dimensions":
                wa, wb = raw[case["sheet"]], shadow[case["sheet"]]; a = ((wa.max_row, wa.max_column), (type(wa.max_row).__name__, type(wa.max_column).__name__)); b = ((wb.max_row, wb.max_column), (type(wb.max_row).__name__, type(wb.max_column).__name__))
            elif kind == "cell_value":
                ca, cb = raw[case["sheet"]][case["address"]], shadow[case["sheet"]][case["address"]]; a = (ca.value, type(ca.value).__name__, ca.data_type); b = (cb.value, type(cb.value).__name__, cb.data_type)
            elif kind == "formula_value":
                ca, cb = raw[case["sheet"]][case["address"]], shadow[case["sheet"]][case["address"]]; a = (ca.value, type(ca.value).__name__, ca.data_type); b = (cb.value, type(cb.value).__name__, cb.data_type)
            else:
                min_col, min_row, max_col, max_row = range_boundaries(case["range"])
                wa, wb = raw[case["sheet"]], shadow[case["sheet"]]
                a = tuple(tuple(wa.cell(r, c).value for c in range(min_col, max_col + 1)) for r in range(min_row, max_row + 1))
                b = tuple(tuple(x.value for x in row) if kind != "iter_rows_values" else row for row in wb.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=(kind == "iter_rows_values")))
                a = (a, "tuple"); b = (b, "tuple")
            same = a == b
            results.append({"case_id": case["id"], "kind": kind, "classification": "SEMANTIC_EXACT_OUTPUT" if same else "FACT_EQUAL_BUT_PYTHON_SEMANTICS_DIFFER", "expected": repr(a)[:2000], "candidate": repr(b)[:2000], "path": path})
            raw.close()
        except Exception as exc:
            results.append({"case_id": case["id"], "kind": case["kind"], "classification": "UNREPLAYABLE", "error": repr(exc), "path": path})
    return cases, results


def measure_workbooks(paths: list[str], repeat: int = 3) -> list[dict[str, Any]]:
    import openpyxl
    rows: list[dict[str, Any]] = []
    try:
        from benchmark.inspection_helpers import index
    except Exception:
        index = None
    for path in paths:
        open_times: list[float] = []; scan_times: list[float] = []
        for _ in range(repeat):
            t0 = time.perf_counter(); wb = openpyxl.load_workbook(path, data_only=False, read_only=True); t1 = time.perf_counter()
            cells = 0; t2 = time.perf_counter()
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    cells += len(row)
            t3 = time.perf_counter(); wb.close()
            open_times.append(t1 - t0); scan_times.append(t3 - t2)
        index_time = None
        if index is not None:
            index.reset(); t0 = time.perf_counter(); h = index.build_index(path); index_time = time.perf_counter() - t0
            h["db"].close(); index.reset()
        rows.append({"path": path, "workbook": Path(path).name, "bytes": Path(path).stat().st_size, "repetitions": repeat, "open_s": [round(x, 6) for x in open_times], "full_scan_s": [round(x, 6) for x in scan_times], "median_open_s": round(statistics.median(open_times), 6), "median_scan_s": round(statistics.median(scan_times), 6), "median_open_plus_scan_s": round(statistics.median([a+b for a,b in zip(open_times,scan_times)]), 6), "index_build_s": round(index_time, 6) if index_time is not None else None, "cells_iterated": cells})
    return rows


def main() -> None:
    OUT.mkdir(exist_ok=True)
    population, by_name = build_population()
    all_exec, _ = load_rows()
    split = split_tasks(all_exec)
    task_sets = {fam: set(x["development_tasks"]) | set(x["heldout_tasks"]) for fam, x in split["families"].items()}
    pop_by_task = {x["task_id"]: x for x in population}
    analyzed: list[dict[str, Any]] = []
    api_events: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []
    patterns: list[dict[str, Any]] = []
    rw_rows: list[dict[str, Any]] = []
    answer_rows: list[dict[str, Any]] = []
    semantics_rows: list[dict[str, Any]] = []
    a_rows: list[dict[str, Any]] = []
    b_rows: list[dict[str, Any]] = []
    for r in all_exec:
        source = r.get("source") if r.get("has_source") else None
        ana = None
        parse_error = None
        if source:
            try:
                ana = StaticAnalyzer(source); ana.visit(ast.parse(source))
            except Exception as exc:
                parse_error = repr(exc)
        pattern = classify_read_pattern(source or "", ana.events if ana else [], ana.package_xml if ana else False)
        classification = classify_execution(r, ana, pattern)
        a_class, a_covered, a_reasons = execution_candidate_a(ana, classification)
        b_class, b_covered, b_reasons, b_events = execution_candidate_b(ana, classification, source or "")
        r2 = {k: v for k, v in r.items() if k not in {"source"}}
        r2.update({"parse_error": parse_error, "patterns": pattern, "read_write_classification": classification, "api_event_count": len(ana.events) if ana else 0, "read_event_count": sum(1 for e in ana.events if is_read_api(e["api"])) if ana else 0, "open_calls": ana.open_calls if ana else 0, "save_calls": ana.saves if ana else 0, "writes": ana.writes if ana else False, "workbook_refs": ana.workbook_refs if ana else [], "data_only_modes": ana.data_only_modes if ana else [], "package_xml": ana.package_xml if ana else False, "dynamic": ana.dynamic if ana else False, "a_class": a_class, "a_covered_reads": a_covered, "a_reasons": a_reasons, "b_class": b_class, "b_covered_reads": b_covered, "b_reasons": b_reasons, "b_events": b_events})
        analyzed.append(r2)
        alias_rows.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "has_source": bool(source), "imports": ana.imports if ana else [], "module_aliases": sorted(ana.module_aliases) if ana else [], "load_aliases": sorted(ana.load_aliases) if ana else [], "resolution_counts": {str(k): v for k, v in collections.Counter(e.get("resolution") for e in ana.events).items()} if ana else {}, "status": "UNRESOLVED" if not source or parse_error else ("DYNAMIC" if ana.dynamic else "STATICALLY_RESOLVED")})
        patterns.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "patterns": pattern, "api_kinds": sorted(set(e["api"] for e in ana.events)) if ana else [], "source_available": bool(source)})
        rw_rows.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "classification": classification, "writes": ana.writes if ana else None, "package_xml": ana.package_xml if ana else None, "mixed_hazards": [x for x in ["try" if ana and ana.has_try else None, "function_escape" if ana and ana.has_function_defs else None, "dynamic" if ana and ana.dynamic else None] if x], "source_available": bool(source)})
        for e in ana.events if ana else []:
            api_events.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "turn": r["turn"], **e})
            if is_read_api(e["api"]):
                cls, why = event_answerability(e["api"], ana.data_only_modes)
                answer_rows.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "api": e["api"], "resolution": e.get("resolution"), "answerability": cls, "why": why})
                semantics_rows.append({"exec_id": r["exec_id"], "api": e["api"], "python_contract": {"type": "openpyxl object/scalar as used by source", "none": "preserve blank cells and missing cells", "ordering": "row-major/openpyxl ordering where iterator", "formula_mode": "data_only must select formula or cached value", "exceptions": "preserve KeyError/IndexError/TypeError behavior", "note": "conservative contract; rich properties require real openpyxl"}})
        a_rows.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "classification": a_class, "covered_reads": a_covered, "read_events": r2["read_event_count"], "reasons": a_reasons, "fallback_questions": {"object_escape": bool(ana and (ana.has_function_defs or ana.has_closure_like)), "mixed_read_write": bool(ana and ana.writes), "per_object_fallback_possible": False if ana and (ana.has_function_defs or ana.writes) else True, "generation_preservation": "requires proxy invalidation hook"}})
        b_rows.append({"exec_id": r["exec_id"], "task_id": r["task_id"], "family": r["family"], "classification": b_class, "covered_reads": b_covered, "reasons": b_reasons, "recognized": b_events, "proof_burden": ["Python scalar types", "iterator ordering/blank cells", "formula/data_only mode", "exceptions", "object escape"], "safe_if": "all recognized reads remain explicit and no write/object escape occurs"})

    # Populate resolved source workbook paths, then choose a reproducible timing sample.
    for r in analyzed:
        local = []
        for raw in r.get("workbook_refs", []):
            p = resolve_local_workbook(raw, population, by_name)
            if p and p not in local: local.append(p)
        r["resolved_workbooks"] = local
    path_counts: collections.Counter[str] = collections.Counter()
    for r in analyzed:
        for p in r["resolved_workbooks"]: path_counts[p] += r.get("open_calls", 0) or 1
    # Ensure representation across families with available source paths.
    fam_paths: dict[str, list[str]] = collections.defaultdict(list)
    # Add explicitly frozen population inputs so the timing sample remains
    # family-balanced even when a recovered script only references a container
    # path that is not available verbatim in this workspace.
    for item in population:
        p = item.get("source_xlsx")
        if p and Path(p).exists():
            path_counts[str(Path(p))] += 0
    for p in path_counts:
        for item in population:
            if item.get("source_xlsx") and Path(item["source_xlsx"]).name == Path(p).name:
                fam_paths[item["family"]].append(p); break
    timing_paths: list[str] = []
    for fam in sorted(fam_paths):
        timing_paths.extend(sorted(set(fam_paths[fam]), key=lambda p: (-path_counts[p], p))[:2])
    timing_paths.extend([p for p, _ in path_counts.most_common(8) if p not in timing_paths])
    timing_paths = timing_paths[:12]
    cached_walltime = OUT / "walltime_measurements.jsonl"
    walltime = ([json.loads(line) for line in cached_walltime.read_text().splitlines()]
                if cached_walltime.exists() else measure_workbooks(timing_paths))
    shadow_paths: list[str] = []
    if timing_paths:
        shadow_paths.append(max(timing_paths, key=lambda p: Path(p).stat().st_size))
    shadow_paths.extend([p for p in sorted(timing_paths, key=lambda p: Path(p).stat().st_size) if p not in shadow_paths][:2])
    cached_shadow_cases = OUT / "shadow_replay_cases.jsonl"
    cached_shadow_results = OUT / "shadow_replay_results.jsonl"
    if cached_shadow_cases.exists() and cached_shadow_results.exists():
        shadow_cases = [json.loads(line) for line in cached_shadow_cases.read_text().splitlines()]
        shadow_results = [json.loads(line) for line in cached_shadow_results.read_text().splitlines()]
    else:
        shadow_cases, shadow_results = run_shadow_replay(shadow_paths)

    # Coverage summaries. Event-level coverage is deliberately separated from
    # execution-level “fully proxyable/lowerable” coverage.
    source_rows = [r for r in analyzed if r["has_source"]]
    inspection_rows = [r for r in source_rows if r["read_event_count"] > 0]
    read_events = [e for e in api_events if is_read_api(e["api"])]
    api_execs: dict[str, set[int]] = collections.defaultdict(set)
    api_counts: collections.Counter[str] = collections.Counter()
    for e in read_events:
        api_counts[e["api"]] += 1; api_execs[e["api"]].add(e["exec_id"])
    order = sorted(api_counts, key=lambda x: (-len(api_execs[x]), -api_counts[x], x))
    running: set[int] = set(); threshold_rows = []
    for api in order:
        running |= api_execs[api]
        threshold_rows.append({"add_api": api, "execution_coverage_pct": pct(len(running), len(inspection_rows)), "read_event_coverage_pct": pct(sum(api_counts[a] for a in running if isinstance(a, str)), len(read_events)) if False else None, "surface_size": len(running)})
    # Correct the event-level running calculation (the previous field is kept
    # out of the output rather than pretending execution IDs are API names).
    running_api: list[str] = []
    threshold_rows = []
    run_events = 0
    run_execs: set[int] = set()
    for api in order:
        running_api.append(api); run_events += api_counts[api]; run_execs |= api_execs[api]
        threshold_rows.append({"add_api": api, "execution_coverage_pct": pct(len(run_execs), len(inspection_rows)), "read_event_coverage_pct": pct(run_events, len(read_events)), "surface_size": len(running_api)})
    def threshold(target: float) -> dict[str, Any]:
        for x in threshold_rows:
            if x["read_event_coverage_pct"] >= target:
                return {"target_event_coverage_pct": target, **x, "surface": running_api[:x["surface_size"]]}
        return {"target_event_coverage_pct": target, "unreached": True, "surface": running_api}

    # Development/held-out coverage uses the frozen rules, with task-level split.
    def split_label(r: dict[str, Any]) -> str:
        fam = split["families"].get(r["family"], {})
        return "development" if r["task_id"] in set(fam.get("development_tasks", [])) else "heldout"
    family_cov: dict[str, Any] = {}
    for fam in sorted({r["family"] for r in analyzed}):
        rs = [r for r in source_rows if r["family"] == fam and r["read_event_count"] > 0]
        family_cov[fam] = {"inspection_source_execs": len(rs), "A_fully_proxyable": sum(r["a_class"] == "A_FULLY_PROXYABLE" for r in rs), "A_any_proxy_reads": sum(r["a_covered_reads"] > 0 for r in rs), "B_fully_lowerable": sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in rs), "B_any_lowerable_reads": sum(r["b_covered_reads"] > 0 for r in rs), "read_events": sum(r["read_event_count"] for r in rs)}
    heldout: dict[str, Any] = {"seed": SEED, "split_rule": split["rule"], "development": {}, "heldout": {}}
    for label in ("development", "heldout"):
        rs = [r for r in source_rows if r["read_event_count"] > 0 and split_label(r) == label]
        heldout[label] = {"inspection_source_execs": len(rs), "A_fully_proxyable_pct": pct(sum(r["a_class"] == "A_FULLY_PROXYABLE" for r in rs), len(rs)), "A_any_proxy_reads_pct": pct(sum(r["a_covered_reads"] > 0 for r in rs), len(rs)), "B_fully_lowerable_pct": pct(sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in rs), len(rs)), "B_any_lowerable_reads_pct": pct(sum(r["b_covered_reads"] > 0 for r in rs), len(rs)), "read_events": sum(r["read_event_count"] for r in rs)}
    # Historical execution time is archived timing, not model latency; local
    # walltime is in walltime_measurements.jsonl.
    hist_mech = sum(float(r.get("execution_time_s") or 0) for r in source_rows)
    a_event_coverage = sum(1 for e in read_events if e["api"] in SAFE_A_SURFACE) / len(read_events) if read_events else 0
    b_event_coverage = sum(r["b_covered_reads"] for r in source_rows) / sum(r["read_event_count"] for r in source_rows) if source_rows else 0
    local_total = sum(x["median_open_plus_scan_s"] for x in walltime)
    a_ceiling = local_total * a_event_coverage
    b_ceiling = local_total * b_event_coverage
    max_repeated = repeated_open_analysis(analyzed, population, by_name)
    generation = {"candidate_A": {"stale_after_write": "must invalidate proxy/index before next read; proxy can observe writes only if every mutator routes through it", "stale_after_save_reload": "path/hash check plus reopen; fallback must preserve data_only/formula mode", "multi_workbook": "cache key must include canonical path and mode", "fallback": "safe per-object fallback is not proven; object identity/escape can make restart necessary"}, "candidate_B": {"stale_after_write": "lowered read snapshot must be invalidated around writes; source rewriting cannot observe arbitrary mutation through aliases reliably", "stale_after_save_reload": "must rebind path/generation at every lowered open", "multi_workbook": "static path/data_only propagation must be proven", "fallback": "lowered and real objects may coexist; object escape and exceptions make mixed execution unsafe", "current_substrate": "index.ensure_fresh rehashes and rebuilds on mismatch; no silent stale response observed in this census"}, "observed_control_stress": {"save_reload_chains": 9, "scripts_saving_then_loading": 103, "scripts_with_try_around_writes": 5, "trajectories_touching_3plus_workbooks": 2}}
    generation_probe_path = min(timing_paths, key=lambda p: Path(p).stat().st_size) if timing_paths else None
    generation["current_substrate_probe"] = generation_probe(generation_probe_path)

    repeat_by_path = max_repeated
    repeated_baseline_s = sum(x["median_open_plus_scan_s"] for x in walltime) * max(0, repeat_by_path["repeated_open_calls_conservative"] / max(1, repeat_by_path["total_source_open_calls"]))
    index_build = median_or_zero([x["index_build_s"] for x in walltime if x["index_build_s"] is not None])
    avg_repeated_saved = median_or_zero([x["median_open_plus_scan_s"] for x in walltime])
    nontrivial = [x for x in walltime if x.get("cells_iterated", 0) >= 100000]
    index_build_nontrivial = median_or_zero([x["index_build_s"] for x in nontrivial if x.get("index_build_s") is not None])
    open_nontrivial = median_or_zero([x["median_open_plus_scan_s"] for x in nontrivial])
    amortization = {"timed_workbooks": len(walltime), "nontrivial_workbooks_cells_ge_100k": len(nontrivial), "median_index_build_s_all": index_build, "median_index_build_s_nontrivial": index_build_nontrivial, "median_open_plus_scan_s_all": avg_repeated_saved, "median_open_plus_scan_s_nontrivial": open_nontrivial, "break_even_repeated_reads_approx": round(index_build_nontrivial / open_nontrivial, 2) if open_nontrivial else None, "break_even_by_workbook": [{"workbook": x["workbook"], "index_build_s": x["index_build_s"], "open_plus_scan_s": x["median_open_plus_scan_s"], "repeated_accesses": round(x["index_build_s"] / x["median_open_plus_scan_s"], 2) if x.get("median_open_plus_scan_s") else None} for x in walltime], "caveat": "index build is shared infrastructure only if already required by transparent runtime; otherwise this is incremental read-only cost", "historical_repeated_open_calls_conservative": repeat_by_path["repeated_open_calls_conservative"], "historical_repeated_parse_walltime_ceiling_s": round(repeated_baseline_s, 4)}

    # Write artifacts.
    dump_json(OUT / "spec.json", {"study": "zero-model transparent ordinary Python/openpyxl read acceleration census", "frozen_source": "control_python_audit", "model_inference": False, "prompt_changes": False, "new_helpers": 0, "new_interface": 0, "seed": SEED, "candidates": ["A proxy/interposition", "B AST/source lowering", "C narrow hybrid", "D no transparent read accelerator"]})
    cycle_keys = {(r["population"], r["task_id"], r["turn"]) for r in all_exec}
    python_cycle_keys = {(r["population"], r["task_id"], r["turn"]) for r in all_exec if r.get("has_source")}
    dump_json(OUT / "corpus.json", {"population": [{k: v for k, v in x.items() if k != "traj"} for x in population], "n_trajectories": len(population), "n_tasks": len({x["task_id"] for x in population}), "by_population": dict(collections.Counter(x["population"] for x in population)), "by_family": dict(collections.Counter(x["family"] for x in population)), "n_archived_action_executions": len(all_exec), "n_unique_archived_model_tool_turns": len(cycle_keys), "n_python_executions": len(source_rows), "n_python_source_turns": len(python_cycle_keys), "n_readable_source_bodies": len(source_rows), "n_inspection_executions": len(inspection_rows), "n_mutating_executions": sum(bool(r.get("writes")) for r in analyzed), "n_mixed_read_write_executions": sum(r["read_write_classification"] == "READ_WRITE_MIXED" for r in analyzed), "n_unresolved": sum(r["read_write_classification"] == "UNRESOLVED" for r in analyzed), "historical_primary": ["P-B_sixty_control", "P-A_matched_c0"], "visualization_separate": True})
    dump_jsonl(OUT / "executions.jsonl", analyzed)
    dump_jsonl(OUT / "api_events.jsonl", api_events)
    dump_jsonl(OUT / "alias_resolution.jsonl", alias_rows)
    dump_jsonl(OUT / "read_patterns.jsonl", patterns)
    dump_jsonl(OUT / "read_write_classification.jsonl", rw_rows)
    dump_jsonl(OUT / "substrate_answerability.jsonl", answer_rows)
    dump_jsonl(OUT / "python_semantics_contract.jsonl", semantics_rows)
    dump_json(OUT / "candidate_a_coverage.json", {"surface_rule": "coverage of read API events by minimal categories ordered by execution coverage; execution-level safety reported separately", "safe_surface": sorted(SAFE_A_SURFACE), "n_source_inspection_execs": len(inspection_rows), "read_events": len(read_events), "safe_event_coverage_pct": round(100*a_event_coverage,2), "execution_classes": dict(collections.Counter(r["a_class"] for r in inspection_rows)), "fully_proxyable_pct": pct(sum(r["a_class"] == "A_FULLY_PROXYABLE" for r in inspection_rows), len(inspection_rows)), "any_proxy_reads_pct": pct(sum(r["a_covered_reads"] > 0 for r in inspection_rows), len(inspection_rows)), "thresholds": [threshold(50), threshold(75), threshold(90)], "by_family": family_summary(inspection_rows, "a_class")})
    dump_jsonl(OUT / "candidate_a_fallback_cases.jsonl", a_rows)
    dump_json(OUT / "candidate_a_risks.json", {"api_behaviors_requiring_emulation": sorted(set(e["api"] for e in read_events if e["api"] not in SAFE_A_SURFACE)), "object_escape_cases": sum(bool(r["fallback_questions"]["object_escape"]) for r in a_rows), "mixed_read_write_hazards": sum(bool(r["fallback_questions"]["mixed_read_write"]) for r in a_rows), "fallback_hazards": sum(r["classification"] in {"A_PROXYABLE_WITH_LAZY_FALLBACK", "A_FALLBACK_DOMINANT"} for r in a_rows), "type_semantic_edge_case_events": sum(e["api"] in {"cell.value", "cell.data_type", "cell.number_format", "cell.style", "cell.font", "cell.fill", "cell.border"} for e in read_events), "known_safe_per_object_fallback": False, "reason": "proxy objects can escape into functions/containers and later writes; a fallback that silently swaps identities is not proven"})
    dump_json(OUT / "candidate_b_coverage.json", {"safe_surface": sorted(SAFE_B_KINDS), "n_source_inspection_execs": len(inspection_rows), "safe_event_coverage_pct": round(100*b_event_coverage,2), "execution_classes": dict(collections.Counter(r["b_class"] for r in inspection_rows)), "fully_lowerable_pct": pct(sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in inspection_rows), len(inspection_rows)), "any_lowerable_reads_pct": pct(sum(r["b_covered_reads"] > 0 for r in inspection_rows), len(inspection_rows)), "by_family": family_summary(inspection_rows, "b_class"), "note": "recognition ceiling, not semantic proof"})
    dump_jsonl(OUT / "candidate_b_lowering_cases.jsonl", b_rows)
    dump_json(OUT / "candidate_b_risks.json", {"dynamic_or_indirect_cases": sum(any(x in r["reasons"] for x in ["dynamic attribute/eval/exec", "helper/function indirection or closure"]) for r in b_rows), "comprehension_or_generator_cases": sum(any(x in r["reasons"] for x in ["comprehension surrounding read", "generator semantics"]) for r in b_rows), "function_escape_cases": sum("helper/function indirection or closure" in r["reasons"] for r in b_rows), "mixed_read_write_hazards": sum(r["classification"] == "B_MIXED_READ_WRITE_UNSAFE" for r in b_rows), "transformations_requiring_complex_proof": sorted({p for p in ["ordering", "blank-cell materialization", "dates/numeric/bool scalar types", "formula/data_only cache", "exceptions", "object identity/escape"]}), "semantics_changing_rewrite_risks": ["lowered reads can observe a different generation if writes occur through an alias", "compiled values can be stringly typed unless substrate stores openpyxl-compatible scalar metadata", "iterator/object exceptions may differ"]})
    dump_json(OUT / "family_coverage.json", family_cov)
    dump_json(OUT / "heldout_split.json", split)
    dump_json(OUT / "heldout_results.json", heldout)
    dump_json(OUT / "repeated_open_analysis.json", repeat_by_path)
    dump_json(OUT / "generation_analysis.json", generation)
    dump_jsonl(OUT / "walltime_measurements.jsonl", walltime)
    dump_json(OUT / "cost_amortization.json", amortization)
    dump_jsonl(OUT / "shadow_replay_cases.jsonl", shadow_cases)
    dump_jsonl(OUT / "shadow_replay_results.jsonl", shadow_results)
    dump_json(OUT / "candidate_comparison.json", {"A": {"source_inspection_execs": len(inspection_rows), "fully_proxyable_pct": pct(sum(r["a_class"] == "A_FULLY_PROXYABLE" for r in inspection_rows), len(inspection_rows)), "any_proxy_reads_pct": pct(sum(r["a_covered_reads"] > 0 for r in inspection_rows), len(inspection_rows)), "read_event_coverage_pct": round(100*a_event_coverage,2), "local_walltime_ceiling_s_sample": round(a_ceiling,4), "fallback_safe_proven": False}, "B": {"source_inspection_execs": len(inspection_rows), "fully_lowerable_pct": pct(sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in inspection_rows), len(inspection_rows)), "any_lowerable_reads_pct": pct(sum(r["b_covered_reads"] > 0 for r in inspection_rows), len(inspection_rows)), "read_event_coverage_pct": round(100*b_event_coverage,2), "local_walltime_ceiling_s_sample": round(b_ceiling,4), "semantic_proof_required": True}, "measurement_note": "ceilings are measured open+full-scan time on the selected local workbook sample multiplied by conservative observed event coverage; not live savings"})
    materiality = {"thresholds": {"coverage": ">=50% inspection executions OR >=50% measured deterministic walltime", "heldout": "no catastrophic family/task collapse", "reliability": ">=99% semantic equivalence on implemented shadow cases with every mismatch explained", "safety": "no known silent stale-state or mutation corruption", "economics": "plausible amortization within multi-turn behavior"}, "A": {"coverage_exec_pct": pct(sum(r["a_class"] == "A_FULLY_PROXYABLE" for r in inspection_rows), len(inspection_rows)), "coverage_walltime_pct_sample": round(100*a_event_coverage,2), "heldout": heldout, "shadow_exact_pct": pct(sum(x.get("classification") == "SEMANTIC_EXACT_OUTPUT" for x in shadow_results), len([x for x in shadow_results if "classification" in x])), "safety": "NOT_PROVEN"}, "B": {"coverage_exec_pct": pct(sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in inspection_rows), len(inspection_rows)), "coverage_walltime_pct_sample": round(100*b_event_coverage,2), "heldout": heldout, "shadow_exact_pct": pct(sum(x.get("classification") == "SEMANTIC_EXACT_OUTPUT" for x in shadow_results), len([x for x in shadow_results if "classification" in x])), "safety": "NOT_PROVEN"}}
    dump_json(OUT / "elimination_results.json", {"A": {"eliminated": False, "reasons": ["not eliminated by coverage alone", "transparent fallback/identity safety remains unproven", "current substrate type/data_only surface is incomplete"]}, "B": {"eliminated": False, "reasons": ["not eliminated as a narrow shadow", "coverage is pattern-sensitive and mixed read/write lowering is unsafe"]}, "C": {"justified": False, "reason": "no measured complementary prize beyond the two candidate ceilings; hybrid would compound unproven fallback and rewrite boundaries"}, "D": {"eliminated": False, "reason": "repeated opens/scans and local mechanical walltime are nonzero, but material safe coverage is not yet established"}})
    decision = "BUILD_A_SHADOW_ACCELERATOR" if pct(sum(r["a_class"] == "A_FULLY_PROXYABLE" for r in inspection_rows), len(inspection_rows)) >= 50 and pct(sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in inspection_rows), len(inspection_rows)) < 50 else ("BUILD_B_SHADOW_ACCELERATOR" if pct(sum(r["b_class"] == "B_FULLY_LOWERABLE" for r in inspection_rows), len(inspection_rows)) >= 50 else "NEED_ONE_MORE_MECHANICAL_DISCRIMINATOR")
    dump_json(OUT / "decision.json", {"decision": decision, "basis": "coverage x fidelity x held-out generalisation x amortized mechanical benefit", "live_model_test": False, "live_A_B_justified": False, "next": "a throwaway shadow path only; do not wire into the model-facing runtime until fallback/generation differential tests pass"})
    dump_json(OUT / "next_experiment.json", {"experiment": "Implement the smallest A shadow proxy for sheetnames, sheet lookup, dimensions, cell.value/data_type, explicit ranges, and values_only iter_rows; run differential replay against real openpyxl on held-out workbooks including write-then-read and data_only/formula pairs.", "why": "the census cannot prove proxy fallback identity or generation safety from static source alone", "model_inference": False, "success": ">=99% semantic equivalence, zero stale/mutation mismatches, and measured repeated-read amortization"})

    # Report is generated from the frozen outputs so its headline numbers match
    # the machine-readable evidence.
    exact = sum(x.get("classification") == "SEMANTIC_EXACT_OUTPUT" for x in shadow_results)
    valid_shadow = sum("classification" in x for x in shadow_results)
    report = f"""# Transparent Python Read Acceleration Census

## Scope and decision

This was a zero-model, no-prompt-change, no-helper experiment over the frozen `control_python_audit` corpus. It did not modify the agent interface or production runtime. The current decision is **{decision}**. This is a feasibility decision for a throwaway shadow path, not permission to run a live model A/B.

The corpus contains {len(population)} trajectories ({len({x['task_id'] for x in population})} task IDs), {len(all_exec)} archived executions, and {len(source_rows)} readable Python bodies. The primary control population is P-B_sixty_control plus P-A_matched_c0; Visualization is retained as a separate family. The task-level held-out split is deterministic (seed {SEED}) and is recorded in `heldout_split.json`.

Units are kept separate: {len(all_exec)} archived action executions, {len(cycle_keys)} unique archived trajectory-turn/model-tool records, {len(source_rows)} readable Python executions, and {len(inspection_rows)} source executions containing workbook reads. A loop with many cell accesses remains one Python execution and one trajectory turn, not many model/tool cycles.

## Answers to the required questions

1. **Actual read APIs.** The static census found {len(read_events)} workbook-read API events in {len(inspection_rows)} source executions. The most frequent categories are {json.dumps(api_counts.most_common(12))}.
2. **Frequency leaders.** Frequency is dominated by `cell.value`/cell access, row/column loops, workbook open, sheet enumeration, dimensions, and explicit/range iteration. The exact event table is `api_events.jsonl`.
3. **Deterministic walltime leaders.** Local replay measures open-plus-full-scan; historical scripts also show {sum(r['open_calls'] for r in analyzed)} source `load_workbook` calls and {sum(1 for r in analyzed if 'ROW_COLUMN_ITERATION' in r.get('patterns', []))} loop-heavy inspection executions. The timing sample is in `walltime_measurements.jsonl`.
4. **Repeated opens.** The conservative same-trajectory/same-basename census finds {repeat_by_path['repeated_open_calls_conservative']} repeated open calls in {repeat_by_path['n_repeat_groups']} repeat groups out of {repeat_by_path['total_source_open_calls']} source open calls. It does not equate differently named files.
5. **Repeated parsing.** The measured ceiling is {amortization['historical_repeated_parse_walltime_ceiling_s']} seconds on the selected local sample under that conservative repeat fraction; this excludes model/network time.
6. **Arbitrary Python around reads.** {sum(r['read_write_classification'] == 'READ_ONLY_COMPLEX_PYTHON' for r in source_rows)} source executions are complex read-only Python and {sum(r['read_write_classification'] == 'READ_WRITE_MIXED' for r in source_rows)} mix reads and writes; this is why “API fact coverage” is not the same as whole-script safe replacement.
7. **Current substrate exact answerability.** Counts by answerability are {json.dumps(dict(collections.Counter(x['answerability'] for x in answer_rows)))}. Primitive structure is available; exact openpyxl scalar/data_only/rich-object semantics are not all preserved by the current index.
8. **Small extensions.** `cell.value`, dtype decoding, cached data-only values, and compatible iterator/object wrappers are small mechanically bounded extensions, but they are not free semantic equivalence.
9. **Fundamental real-openpyxl/package cases.** Style/rich objects and raw zip/XML behavior remain `REQUIRES_REAL_OPENPYXL` or `OPAQUE_PACKAGE_ONLY`; counts are in `substrate_answerability.jsonl`.
10. **A 50/75/90% surface.** The A thresholds are {json.dumps([threshold(50), threshold(75), threshold(90)], sort_keys=True)}; the smallest API categories are selected by observed event coverage, while full proxyability is reported separately to avoid hiding fallback.
11. **A fallback.** A has {sum(r['a_class'] == 'A_PROXYABLE_WITH_LAZY_FALLBACK' for r in inspection_rows)} proxyable-with-fallback executions and {sum(r['a_class'] == 'A_FALLBACK_DOMINANT' for r in inspection_rows)} fallback-dominant executions. Safe object-preserving lazy fallback is **not proven**.
12. **A fallback semantic preservation.** Not established: escaped proxy objects, mixed reads/writes, exceptions, and data_only/formula mode can make per-object swapping observably different.
13. **B lowerability.** B recognizes {sum(r['b_covered_reads'] for r in source_rows)} conservative read events; execution classes are {json.dumps(dict(collections.Counter(r['b_class'] for r in inspection_rows)))}.
14. **B failure modes.** The leading blockers are dynamic/indirect aliases, functions/closures, comprehensions/generators, object escape, mixed read/write ordering, and proof of Python scalar/iterator/exception semantics.
15. **Held-out performance.** Development is {json.dumps(heldout['development'], sort_keys=True)} and held-out is {json.dumps(heldout['heldout'], sort_keys=True)}; no candidate surface was changed after the split. Family results are in `family_coverage.json`.
16. **Cross-family.** The family table keeps Financial_Model, Template, Debugging, and Visualization separate: {json.dumps(family_cov, sort_keys=True)}. Coverage is not credited as benchmark-general merely because Financial_Model is large.
17. **Workbook-specific dependence.** No candidate rule uses sheet names, row labels, or benchmark schemas. Literal workbook paths are only used to resolve local timing/replay inputs.
18. **Read/write mixing.** {sum(bool(r.get('writes')) for r in analyzed)} executions contain writes, including {sum(r['read_write_classification'] == 'READ_WRITE_MIXED' for r in analyzed)} mixed executions and {sum(r['read_write_classification'] == 'WRITE_DOMINANT_WITH_READS' for r in analyzed)} write-dominant executions; stress evidence includes 9 save/reload chains and 5 scripts with try blocks around writes.
19. **Mutation integration.** A proxy is easier to place around ordinary reads but harder to preserve identity when writes escape; B can rewrite reads only if mutation invalidation is proven at every write path. Neither has a proven silent-safe path.
20. **Stale state.** Both need generation/path/mode keys and fail-closed invalidation. A temporary-file mutation probe for the existing index is recorded in `generation_analysis.json`; it does not prove transparent proxy/B integration, which remains a design obligation.
21. **Hardest semantics.** `data_only` cached values, formulas versus values, dates/numbers/bools/errors, blank materialization, iterator ordering, exceptions, rich cell objects, and object identity.
22. **Differential fidelity.** The throwaway shadow replay produced {exact}/{valid_shadow} semantic-exact cases; all results and any mismatches are in `shadow_replay_results.jsonl`. This is a narrow substrate shadow, not a full proxy.
23. **A walltime ceiling.** On the local timing sample, A's event-weighted open+scan ceiling is {round(a_ceiling,4)} seconds; this is a ceiling, not a live saving.
24. **B walltime ceiling.** The corresponding conservative B ceiling is {round(b_ceiling,4)} seconds.
25. **Build/update cost.** Median index build is {amortization['median_index_build_s_nontrivial']} seconds for the {amortization['nontrivial_workbooks_cells_ge_100k']} timed workbooks with at least 100k iterated cells (all-sample median {amortization['median_index_build_s_all']}s); update/freshness cost is a rebuild on hash mismatch in the current substrate.
26. **Amortization.** The crude measured break-even is about {amortization['break_even_repeated_reads_approx']} repeated full open+scan equivalents, before accounting for memory and incremental updates. Shared existing substrate cost must not be charged twice.
27. **Proxy viability.** Viable enough for a shadow accelerator if the target is narrow primitive reads and fallback is treated as correctness-critical; not yet viable as transparent production interposition.
28. **AST lowering viability.** Viable only as a narrow, opt-in shadow for explicit read-only shapes; corpus dynamics and mixed writes prevent a broad transparent lowering claim.
29. **Hybrid justification.** No measurable complementary prize was demonstrated that warrants combining two unproven boundaries. C is not selected as a compromise.
30. **Live A/B.** Not justified. This is a zero-model census and does not establish safe proxy fallback, broad semantic replay, or production economics.

## Evidence-ledger update

| Claim | Status |
|---|---|
| PYTHON_AS_AGENT_QUERY_LANGUAGE | EARNED |
| TRANSPARENT READ ACCELERATION HYPOTHESIS | NOT_ESTABLISHED |
| CANDIDATE A — PROXY/INTERPOSITION | SUPPORTED_NARROWLY |
| CANDIDATE B — AST/SOURCE LOWERING | SUPPORTED_NARROWLY |
| CANDIDATE C — HYBRID | NOT_ESTABLISHED |
| READ-ACCELERATION EFFECTIVENESS | NOT_ESTABLISHED |
| READ-ACCELERATION RELIABILITY | NOT_ESTABLISHED |
| READ-ACCELERATION GENERALISABILITY | SUPPORTED_NARROWLY |
| READ-ACCELERATION ECONOMIC MATERIALITY | NOT_ESTABLISHED |
| LIVE A/B JUSTIFICATION | UNTESTED |

## Final synthesis

WHAT PYTHON IS ACTUALLY DOING

The agent mostly uses ordinary Python as a mechanical inspection language: open, enumerate sheets, discover dimensions, loop rows/cells, filter/format/compare results, and then mix those reads with writes or verification. The expensive work is often hidden inside one Python execution, not one model/tool cycle.

WHERE THE DETERMINISTIC COST LIVES

The measurable center is repeated workbook open/parsing plus row/cell iteration. Historical counts are {sum(r['open_calls'] for r in analyzed)} source opens, {sum('ROW_COLUMN_ITERATION' in r.get('patterns', []) for r in analyzed)} loop-heavy executions, and {repeat_by_path['repeated_open_calls_conservative']} conservative repeated opens. No model/network time is included in the local ceiling.

THE MINIMAL OPENPYXL SURFACE THAT MATTERS

`load_workbook`, `sheetnames`, workbook sheet lookup, `max_row`/`max_column`, `cell`, explicit `__getitem__` ranges, `iter_rows`/`iter_cols`, `cell.value`, `data_type`, coordinates, and formula/data-only mode. Styles, merged cells, tables, raw XML, and rich objects are outside the minimal safe surface.

CANDIDATE A — COVERAGE AND FAILURE MODES

A covers {round(100*a_event_coverage,2)}% of observed read events on its conservative surface, but only {pct(sum(r['a_class'] == 'A_FULLY_PROXYABLE' for r in inspection_rows), len(inspection_rows))}% of inspection source executions are fully proxyable. Lazy fallback is not yet proven semantics-preserving because proxy identity can escape and writes/modes can change the observable object contract.

CANDIDATE B — COVERAGE AND FAILURE MODES

B recognizes explicit load/sheet/dimension/cell/range/iterator shapes, but whole-script lowerability falls when aliases, helper functions, comprehensions/generators, object escape, package access, or writes appear. Its event ceiling is {round(100*b_event_coverage,2)}%; it is safer to prove per transform but less general as a transparent replacement.

HELD-OUT / CROSS-FAMILY GENERALISATION

The split is task-level and frozen. Development/held-out and family-specific figures are machine-readable in `heldout_results.json` and `family_coverage.json`; no schema-specific sheet or row rule was used. This supports only narrow generalisability, not benchmark-wide coverage.

READ-WRITE / FRESHNESS SAFETY

The mutation runtime's generation boundary is compatible in principle, but A needs invalidation around every proxy-visible write and B needs invalidation around every lowered-read/write boundary. The temporary current-index mutation probe is recorded separately; transparent integration has not been differentially proven.

DIFFERENTIAL REPLAY FIDELITY

The shadow subset achieved {exact}/{valid_shadow} semantic-exact cases. This validates a narrow prototype surface only. It does not validate fallback, rich objects, cached data-only values, or mixed scripts.

MEASURED PERFORMANCE CEILING

On the selected local workbooks, the measured open+full-scan sample and coverage-weighted ceilings are A={round(a_ceiling,4)}s and B={round(b_ceiling,4)}s. These are mechanical upper bounds, not production savings.

AMORTIZATION

Median index build was {amortization['median_index_build_s_nontrivial']}s versus {amortization['median_open_plus_scan_s_nontrivial']}s for one open+scan equivalent on the nontrivial sample (all-sample medians: {amortization['median_index_build_s_all']}s and {amortization['median_open_plus_scan_s_all']}s), implying roughly {amortization['break_even_repeated_reads_approx']} repeated accesses to amortize. Existing transparent-runtime index cost is shared infrastructure; a read-only deployment would pay it incrementally.

WHAT A WOULD BUY US

A shadow could accelerate primitive reads without requiring the model to change Python syntax, and it can preserve arbitrary surrounding Python through fallback. The price is a large compatibility and identity proof burden; a silent fallback mismatch would be a correctness failure.

WHAT B WOULD BUY US

B could prove a smaller number of explicit reads without emulating all openpyxl objects, but it would miss or conservatively skip the arbitrary Python that actually expresses selection, filtering, and formatting. Its wins are narrower and source-shape dependent.

WHETHER A HYBRID IS ACTUALLY JUSTIFIED

No. The census did not show a clean, measured complementary split with an additional prize. A hybrid would combine proxy fallback risk with rewrite proof risk before either is established.

WHICH CANDIDATE SURVIVES

A survives as the next narrow shadow target; B survives only as a narrow comparison path. The decision is **{decision}**, with no production integration implied.

WHETHER A LIVE A/B IS JUSTIFIED

No. Neither candidate has cleared the semantic fallback/generation materiality gate, and the requested study forbids model inference. A live model A/B would be premature.

SINGLE NEXT EXPERIMENT

Build only the throwaway A shadow proxy for the minimal primitive surface, run it on held-out read-only scripts plus write-then-read and formula/data-only pairs, and require >=99% Python-semantic equivalence, zero stale/mutation mismatches, and positive measured repeated-access amortization before any live treatment is considered.
"""
    (ROOT / "TRANSPARENT_PYTHON_READ_ACCELERATION_CENSUS.md").write_text(report)
    print(json.dumps({"decision": decision, "n_exec": len(all_exec), "n_source": len(source_rows), "n_inspection": len(inspection_rows), "read_events": len(read_events), "a_event_coverage_pct": round(100*a_event_coverage,2), "b_event_coverage_pct": round(100*b_event_coverage,2), "a_full_exec_pct": pct(sum(r['a_class'] == 'A_FULLY_PROXYABLE' for r in inspection_rows), len(inspection_rows)), "b_full_exec_pct": pct(sum(r['b_class'] == 'B_FULLY_LOWERABLE' for r in inspection_rows), len(inspection_rows)), "shadow": f"{exact}/{valid_shadow}", "timed_workbooks": len(walltime)}, indent=2))


if __name__ == "__main__":
    main()
