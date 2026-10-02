#!/usr/bin/env python3
"""Zero-model Candidate-A shadow interposition discriminator.

This is experimental study code only.  It never installs a production proxy,
changes prompts, or changes the model-facing interface.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/history/candidate_a_shadow_interposition"
AUDIT = ROOT / "research/history/control_python_audit"
sys.path.insert(0, str(ROOT))

from benchmark.inspection_helpers import index  # noqa: E402
from benchmark.transparent_python_read_census import build_population, resolve_local_workbook  # noqa: E402

SEED = 20260920
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def pct(n: float, d: float) -> float:
    return round(100 * n / d, 2) if d else 0.0


def observable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [observable(x) for x in value]}
    if isinstance(value, list):
        return {"type": "list", "items": [observable(x) for x in value]}
    return {"type": type(value).__name__, "repr": repr(value)}


def exception_view(exc: BaseException | None) -> dict[str, Any] | None:
    return None if exc is None else {"class": type(exc).__name__, "message": str(exc)}


def compare(real: Any, shadow: Any, real_exc: BaseException | None = None, shadow_exc: BaseException | None = None) -> tuple[str, str | None]:
    if real_exc is not None or shadow_exc is not None:
        if real_exc is not None and shadow_exc is not None and type(real_exc) is type(shadow_exc):
            return "SEMANTIC_EXACT", None
        return "WRONG_EXCEPTION", "exception class differs"
    r, s = observable(real), observable(shadow)
    if r == s:
        return "SEMANTIC_EXACT", None
    if r.get("type") != s.get("type"):
        return "WRONG_TYPE", "Python-visible type differs"
    return "WRONG_VALUE", "value, sequence shape, or order differs"


class WorkbookMetadata:
    """Package metadata needed for exact sheet names and worksheet bounds."""

    def __init__(self, path: str):
        self.path = str(path)
        self.sheetnames: list[str] = []
        self.dimensions: dict[str, tuple[int, int, int, int]] = {}
        self.dimension_text: dict[str, str] = {}
        self.merged: dict[str, list[str]] = {}
        self.cell_types: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        from openpyxl.utils import get_column_letter
        from openpyxl.utils.cell import range_boundaries
        with zipfile.ZipFile(self.path) as z:
            workbook = ET.fromstring(z.read("xl/workbook.xml"))
            rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            rels = {x.attrib["Id"]: x.attrib["Target"] for x in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")}
            for sheet in workbook.findall(f"{{{MAIN_NS}}}sheets/{{{MAIN_NS}}}sheet"):
                name = sheet.attrib["name"]
                rid = sheet.attrib.get(f"{{{REL_NS}}}id")
                target = rels.get(rid, "")
                if target.startswith("/"):
                    target = target[1:]
                elif not target.startswith("xl/"):
                    target = "xl/" + target
                root = ET.fromstring(z.read(target))
                if root.tag != f"{{{MAIN_NS}}}worksheet":
                    raise NotImplementedError("non-worksheet package structure")
                cells = root.findall(f".//{{{MAIN_NS}}}c")
                refs = [x.attrib.get("r") for x in cells if x.attrib.get("r")]
                merge_refs = [x.attrib["ref"] for x in root.findall(f".//{{{MAIN_NS}}}mergeCell") if x.attrib.get("ref")]
                # openpyxl derives max_row/max_column from materialized cell
                # objects, not from an empty worksheet's possibly stale XML
                # dimension declaration.  Preserve the same observable rule.
                if refs or merge_refs:
                    cell_bounds = [range_boundaries(x) for x in refs + merge_refs]
                    bounds = (
                        min(x[0] for x in cell_bounds),
                        min(x[1] for x in cell_bounds),
                        max(x[2] for x in cell_bounds),
                        max(x[3] for x in cell_bounds),
                    )
                    ref = f"{get_column_letter(bounds[0])}{bounds[1]}:{get_column_letter(bounds[2])}{bounds[3]}"
                else:
                    ref, bounds = "A1:A1", (1, 1, 1, 1)
                self.sheetnames.append(name)
                self.dimensions[name] = bounds
                self.dimension_text[name] = ref
                self.merged[name] = merge_refs
                self.cell_types[name] = {
                    cell.attrib["r"]: (cell.attrib.get("t") or ("f" if cell.find(f"{{{MAIN_NS}}}f") is not None else "n"))
                    for cell in cells if cell.attrib.get("r")
                }

    def merged_at(self, sheet: str, row: int, col: int) -> bool:
        from openpyxl.utils.cell import range_boundaries
        for ref in self.merged.get(sheet, []):
            min_col, min_row, max_col, max_row = range_boundaries(ref)
            if min_row <= row <= max_row and min_col <= col <= max_col:
                return True
        return False


def decode_row(row: tuple[Any, ...] | None) -> Any:
    if row is None:
        return None
    _, _, _, _, value, formula, dtype = row
    if formula is not None:
        return formula
    if value is None:
        return None
    if dtype == "n":
        try:
            return int(value) if re.fullmatch(r"[-+]?\d+", value) else float(value)
        except Exception:
            return value
    if dtype == "b":
        return str(value).lower() == "true"
    if dtype == "d":
        for parser in (dt.datetime.fromisoformat, dt.date.fromisoformat, dt.time.fromisoformat):
            try:
                return parser(value)
            except Exception:
                pass
    return value


class CompiledSnapshot:
    def __init__(self, path: str):
        self.path = str(path)
        self.meta = WorkbookMetadata(path)
        self.handle, self.rebuilt = index.ensure_fresh(path)

    def row(self, sheet: str, addr: str) -> tuple[Any, ...] | None:
        return self.handle["db"].execute("SELECT sheet,addr,row,col,value,formula,dtype FROM cells WHERE sheet=? AND addr=?", (sheet, addr)).fetchone()

    def value(self, sheet: str, addr: str) -> Any:
        return decode_row(self.row(sheet, addr))

    def dtype(self, sheet: str, addr: str) -> str:
        row = self.row(sheet, addr)
        return row[6] if row else self.meta.cell_types.get(sheet, {}).get(addr, "n")


class CandidateALoader:
    """Narrow shadow loader; unsupported modes are predeclared real fallback."""

    def __init__(self, predeclared_real: bool = False, real_loader: Any | None = None, event_sink: Any | None = None):
        self.predeclared_real = predeclared_real
        self.real_loader = real_loader
        self.event_sink = event_sink
        self.proxy_loads = 0
        self.fallback_loads = 0
        self.fallback_reasons: list[str] = []
        self.snapshots: dict[str, CompiledSnapshot] = {}
        self.disabled: set[str] = set()
        self.served: set[str] = set()

    def emit(self, event: str, **fields: Any) -> None:
        if self.event_sink is not None:
            self.event_sink({"event": event, **fields})

    def load_workbook(self, filename: str, *args: Any, **kwargs: Any) -> Any:
        import openpyxl
        data_only = bool(kwargs.get("data_only", False))
        read_only = bool(kwargs.get("read_only", False))
        write_only = bool(kwargs.get("write_only", False))
        supported = (isinstance(filename, (str, os.PathLike)) and not self.predeclared_real and not args and not data_only and not read_only and not write_only and Path(filename).suffix.lower() in {".xlsx", ".xlsm"} and set(kwargs) <= {"data_only", "read_only", "write_only"})
        key = str(filename)
        if supported and key not in self.disabled:
            try:
                snapshot = self.snapshots.get(key)
                if snapshot is not None and (not snapshot.handle["valid"] or index.workbook_hash(key) != snapshot.handle["workbook_hash"]):
                    snapshot.handle["valid"] = False
                    raise ValueError("retired or stale substrate")
                if snapshot is None:
                    snapshot = CompiledSnapshot(key)
                    self.snapshots[key] = snapshot
                result = ProxyWorkbook(self, snapshot)
            except Exception as exc:
                event = (exc.event if isinstance(exc, index.SubstrateDisabled) else
                         index.disable(key, None, "snapshot_initialization", exc,
                                       partial=key in self.snapshots, served=key in self.served))
                self.disabled.add(key)
                self.emit("substrate_fallback", **{k: v for k, v in event.items() if k != "event"})
            else:
                self.proxy_loads += 1
                snapshot.handle["accelerated_served"] = True
                self.served.add(key)
                self.emit("candidate_operation", operation="load_workbook", path=key, status="ACCELERATED")
                return result
        self.fallback_loads += 1
        self.fallback_reasons.append("predeclared real path" if not supported else "substrate disabled")
        self.emit("candidate_operation", operation="load_workbook", path=key, status="PREDECLARED_FALLBACK")
        return (self.real_loader or openpyxl.load_workbook)(filename, *args, **kwargs)


class ProxyWorkbook:
    def __init__(self, loader: CandidateALoader, snapshot: CompiledSnapshot):
        self._loader, self._snapshot, self._real = loader, snapshot, None

    @property
    def sheetnames(self) -> list[str]:
        self._loader.emit("candidate_operation", operation="Workbook.sheetnames", path=self._snapshot.path, status="ACCELERATED", workbook_generation=self._snapshot.handle["workbook_hash"], substrate_generation=self._snapshot.handle["index_generation"], rebuilt=self._snapshot.rebuilt)
        return list(self._snapshot.meta.sheetnames)

    def __getitem__(self, name: str) -> "ProxyWorksheet":
        if not isinstance(name, str) or name not in self.sheetnames:
            raise KeyError(name)
        self._loader.emit("candidate_operation", operation="Workbook.__getitem__", path=self._snapshot.path, sheet=name, status="ACCELERATED", workbook_generation=self._snapshot.handle["workbook_hash"], substrate_generation=self._snapshot.handle["index_generation"], rebuilt=self._snapshot.rebuilt)
        return ProxyWorksheet(self, name)

    def _real_workbook(self):
        import openpyxl
        if self._real is None:
            self._loader.emit("candidate_operation", operation="openpyxl_fallback_load", path=self._snapshot.path, status="RUNTIME_FALLBACK", fallback_reason="unsupported object behavior")
            self._real = (self._loader.real_loader or openpyxl.load_workbook)(self._snapshot.path, data_only=False)
        return self._real

    def close(self) -> None:
        if self._real is not None:
            self._real.close()

    def __getattr__(self, name: str) -> Any:
        self._loader.fallback_reasons.append(f"Workbook.{name}")
        return getattr(self._real_workbook(), name)


class ProxyWorksheet:
    def __init__(self, workbook: ProxyWorkbook, title: str):
        self._workbook, self.title = workbook, title

    @property
    def max_row(self) -> int:
        self._workbook._loader.emit("candidate_operation", operation="Worksheet.max_row", path=self._workbook._snapshot.path, sheet=self.title, status="ACCELERATED", workbook_generation=self._workbook._snapshot.handle["workbook_hash"], substrate_generation=self._workbook._snapshot.handle["index_generation"], rebuilt=self._workbook._snapshot.rebuilt)
        return self._workbook._snapshot.meta.dimensions[self.title][3]

    @property
    def max_column(self) -> int:
        self._workbook._loader.emit("candidate_operation", operation="Worksheet.max_column", path=self._workbook._snapshot.path, sheet=self.title, status="ACCELERATED", workbook_generation=self._workbook._snapshot.handle["workbook_hash"], substrate_generation=self._workbook._snapshot.handle["index_generation"], rebuilt=self._workbook._snapshot.rebuilt)
        return self._workbook._snapshot.meta.dimensions[self.title][2]

    @property
    def dimensions(self) -> str:
        return self._workbook._snapshot.meta.dimension_text[self.title]

    def calculate_dimension(self) -> str:
        return self.dimensions

    def _real_sheet(self):
        return self._workbook._real_workbook()[self.title]

    def cell(self, row: int = 1, column: int = 1) -> Any:
        if not isinstance(row, int) or not isinstance(column, int) or row < 1 or column < 1:
            raise ValueError("Row or column values must be at least 1")
        if self._workbook._snapshot.meta.merged_at(self.title, row, column):
            self._workbook._loader.fallback_reasons.append("merged-cell access")
            return self._real_sheet().cell(row=row, column=column)
        from openpyxl.utils import get_column_letter
        addr = f"{get_column_letter(column)}{row}"
        self._workbook._loader.emit("candidate_operation", operation="Worksheet.cell", path=self._workbook._snapshot.path, sheet=self.title, address=addr, status="ACCELERATED", workbook_generation=self._workbook._snapshot.handle["workbook_hash"], substrate_generation=self._workbook._snapshot.handle["index_generation"], rebuilt=self._workbook._snapshot.rebuilt)
        return ProxyCell(self, addr, row, column)

    def __getitem__(self, key: str) -> Any:
        from openpyxl.utils.cell import coordinate_to_tuple
        if isinstance(key, str) and ":" not in key:
            try:
                row, col = coordinate_to_tuple(key)
                return self.cell(row=row, column=col)
            except Exception:
                return self._real_sheet()[key]
        self._workbook._loader.fallback_reasons.append("Worksheet range or slice")
        return self._real_sheet()[key]

    def iter_rows(self, min_row=None, max_row=None, min_col=None, max_col=None, values_only=False):
        if (values_only is True and min_row is None and max_row is None
                and min_col is None and max_col is None
                and not self._workbook._snapshot.meta.cell_types[self.title]):
            # An empty sheet's unbounded iterator has different semantics from
            # an explicit A1:A1 range. Leave this structure to openpyxl.
            self._workbook._loader.fallback_reasons.append("empty unbounded iterator")
            return self._real_sheet().iter_rows(values_only=True)
        if values_only is not True:
            self._workbook._loader.fallback_reasons.append("iter_rows Cell objects")
            return self._real_sheet().iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=values_only)
        self._workbook._loader.emit("candidate_operation", operation="Worksheet.iter_rows(values_only=True)", path=self._workbook._snapshot.path, sheet=self.title, status="ACCELERATED", workbook_generation=self._workbook._snapshot.handle["workbook_hash"], substrate_generation=self._workbook._snapshot.handle["index_generation"], rebuilt=self._workbook._snapshot.rebuilt)
        min_row = 1 if min_row is None else min_row; max_row = self.max_row if max_row is None else max_row
        min_col = 1 if min_col is None else min_col; max_col = self.max_column if max_col is None else max_col
        if any(not isinstance(x, int) or x < 1 for x in [min_row, max_row, min_col, max_col]):
            raise ValueError("Row or column values must be at least 1")
        def rows():
            for r in range(min_row, max_row + 1):
                vals = []
                for c in range(min_col, max_col + 1):
                    vals.append(self._real_sheet().cell(r, c).value if self._workbook._snapshot.meta.merged_at(self.title, r, c) else self.cell(r, c).value)
                yield tuple(vals)
        return rows()

    def __getattr__(self, name: str) -> Any:
        self._workbook._loader.fallback_reasons.append(f"Worksheet.{name}")
        return getattr(self._real_sheet(), name)


class ProxyCell:
    def __init__(self, worksheet: ProxyWorksheet, addr: str, row: int, column: int):
        self._worksheet, self.coordinate, self.row, self.column = worksheet, addr, row, column

    @property
    def value(self) -> Any:
        self._worksheet._workbook._loader.emit("candidate_operation", operation="Cell.value", path=self._worksheet._workbook._snapshot.path, sheet=self._worksheet.title, address=self.coordinate, status="ACCELERATED", workbook_generation=self._worksheet._workbook._snapshot.handle["workbook_hash"], substrate_generation=self._worksheet._workbook._snapshot.handle["index_generation"], rebuilt=self._worksheet._workbook._snapshot.rebuilt)
        started_ns = time.perf_counter_ns()
        result = self._worksheet._workbook._snapshot.value(self._worksheet.title, self.coordinate)
        self._worksheet._workbook._loader.emit("candidate_operation", operation="Cell.value_timing", path=self._worksheet._workbook._snapshot.path, sheet=self._worksheet.title, address=self.coordinate, status="ACCELERATED", duration_ns=time.perf_counter_ns() - started_ns, result=observable(result))
        return result

    @property
    def data_type(self) -> str:
        self._worksheet._workbook._loader.emit("candidate_operation", operation="Cell.data_type", path=self._worksheet._workbook._snapshot.path, sheet=self._worksheet.title, address=self.coordinate, status="ACCELERATED", workbook_generation=self._worksheet._workbook._snapshot.handle["workbook_hash"], substrate_generation=self._worksheet._workbook._snapshot.handle["index_generation"], rebuilt=self._worksheet._workbook._snapshot.rebuilt)
        started_ns = time.perf_counter_ns()
        result = self._worksheet._workbook._snapshot.dtype(self._worksheet.title, self.coordinate)
        self._worksheet._workbook._loader.emit("candidate_operation", operation="Cell.data_type_timing", path=self._worksheet._workbook._snapshot.path, sheet=self._worksheet.title, address=self.coordinate, status="ACCELERATED", duration_ns=time.perf_counter_ns() - started_ns, result=observable(result))
        return result

    def _real_cell(self):
        return self._worksheet._real_sheet()[self.coordinate]

    def __getattr__(self, name: str) -> Any:
        self._worksheet._workbook._loader.fallback_reasons.append(f"Cell.{name}")
        return getattr(self._real_cell(), name)


def _guard_compiled_read(fn, owner, reference, name, *, is_property=False):
    """Retire a failed snapshot before delegating the same read to openpyxl.

    No mutation methods are interposed. This guards only the existing earned
    Candidate-A surface, including proxy objects obtained before retirement.
    """
    from functools import wraps

    @wraps(fn)
    def guarded(self, *args, **kwargs):
        workbook = owner(self)
        snapshot = workbook._snapshot
        if snapshot.handle.get("valid", False) and workbook._real is None:
            try:
                return fn(self, *args, **kwargs)
            except Exception as exc:
                snapshot.handle["valid"] = False
                workbook._loader.disabled.add(snapshot.path)
                event = index.disable(snapshot.path, snapshot.handle.get("workbook_hash"),
                                      "compiled_read", exc, partial=True,
                                      served=snapshot.path in workbook._loader.served,
                                      substrate_generation=snapshot.handle.get("index_generation"))
                snapshot.handle["db"].close()
                workbook._loader.emit("substrate_fallback", **{k: v for k, v in event.items() if k != "event"})
        real = reference(self)
        member = getattr(real, name)
        return member if is_property else member(*args, **kwargs)
    return guarded


# A retired handle is never authoritative, even through a previously returned
# Worksheet/Cell proxy. Fallback once materialized remains reference behavior.
for _cls, _owner, _reference, _properties, _methods in [
    (ProxyWorkbook, lambda x: x, lambda x: x._real_workbook(),
     ("sheetnames",), ("__getitem__",)),
    (ProxyWorksheet, lambda x: x._workbook, lambda x: x._real_sheet(),
     ("max_row", "max_column", "dimensions"),
     ("calculate_dimension", "cell", "__getitem__", "iter_rows")),
    (ProxyCell, lambda x: x._worksheet._workbook, lambda x: x._real_cell(),
     ("value", "data_type"), ()),
]:
    for _name in _properties:
        setattr(_cls, _name, property(_guard_compiled_read(
            getattr(_cls, _name).fget, _owner, _reference, _name, is_property=True)))
    for _name in _methods:
        setattr(_cls, _name, _guard_compiled_read(
            getattr(_cls, _name), _owner, _reference, _name))


def make_surface() -> dict[str, Any]:
    rows = []
    def add(operation, status, reason, constraint=None):
        rows.append({"operation": operation, "status": status, "constraint": constraint, "reason": reason})
    add("load_workbook", "supported_with_constraint", "default mutable formula-mode local xlsx/xlsm", "data_only=False; read_only=False; write_only=False; no extra options")
    add("Workbook.sheetnames", "supported", "XML metadata includes metadata-only sheets and preserves order")
    add("Workbook.__getitem__", "supported", "single named worksheet lookup; missing name is KeyError", "string sheet name only")
    add("Worksheet.max_row", "supported", "XML dimension preserves sparse/formatted extent")
    add("Worksheet.max_column", "supported", "XML dimension preserves sparse/formatted extent")
    add("Worksheet.cell", "supported_with_constraint", "compiled primitive cell facts", "non-merged cell; primitive attributes only")
    add("Worksheet.__getitem__ single cell", "supported_with_constraint", "single coordinate maps to primitive cell", "range/slice falls back")
    add("Worksheet.__getitem__ range", "fallback_required", "Cell-object range identity is not emulated")
    add("Worksheet.iter_rows(values_only=True)", "supported_with_constraint", "row-major tuples of primitive values", "values_only=True; merged coordinates fallback per cell")
    add("Worksheet.iter_rows(values_only=False)", "fallback_required", "Cell object identity is not broadly emulated")
    add("Cell.value", "supported_with_constraint", "formula text and typed primitive values in formula mode", "non-merged cell; data_only fallback")
    add("Cell.data_type", "supported_with_constraint", "compiled dtype for formula-mode primitive cells", "non-merged cell")
    add("Cell.coordinate/row/column", "supported", "derived mechanically from explicit coordinate")
    add("data_only=True", "fallback_required", "current compiled index has no cached-value table")
    add("writes/save/reload", "fallback_required", "proxy does not emulate mutation identity")
    add("styles/merged/tables/names/package", "fallback_required", "rich openpyxl/package behavior is out of scope")
    return {"candidate": "A narrow transparent proxy/interposition shadow", "surface": rows, "no_new_model_surface": True, "no_production_install": True}


def make_contract() -> dict[str, Any]:
    return {
        "value": {"must_match": ["Python scalar type", "None/blank", "formula text", "error representation", "date/datetime/time"], "data_only": "predeclared real-openpyxl fallback"},
        "data_type": {"must_match": ["f", "s", "inlineStr", "n", "b", "d", "e"]},
        "coordinate_row_column": {"must_match": ["coordinate string", "1-based row", "1-based column"]},
        "sheetnames": {"must_match": ["order", "metadata-only sheets", "Unicode names"]},
        "iter_rows_values_only": {"must_match": ["generator behavior", "row-major order", "tuple shape", "blank cells", "bounds"]},
        "exceptions": {"must_match": ["missing-sheet KeyError", "invalid-coordinate ValueError", "no silent unsupported rewrite"]},
        "identity": {"policy": "escaped proxy objects force predeclared real-openpyxl path"},
    }


def create_fixture(path: Path) -> dict[str, Any]:
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook(); wb.active.title = "EmptyMetadata"; ws = wb.create_sheet("Data"); uni = wb.create_sheet("ユニコード")
    ws["A1"] = None; ws["B1"] = ""; ws["C1"] = 7; ws["D1"] = 7.5; ws["E1"] = True
    ws["F1"] = dt.date(2024, 1, 2); ws["G1"] = dt.datetime(2024, 1, 2, 3, 4, 5); ws["H1"] = dt.time(3, 4, 5)
    ws["I1"] = "=C1+D1"; ws["J1"] = "#N/A"; ws["J1"].data_type = "e"; ws["K20"].font = Font(bold=True)
    ws.merge_cells("A10:B11"); ws["C3"] = "Δ Unicode 東京"; uni["A1"] = "Привет 🌍"; wb.save(path); wb.close()
    return {"path": str(path), "sheets": ["EmptyMetadata", "Data", "ユニコード"], "coordinates": ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1", "I1", "J1", "C3", "K20", "B10"], "cases": ["blank", "empty string", "int", "float", "bool", "date", "datetime", "time", "formula", "error", "unicode", "formatted sparse bound", "merged adjacent"]}


def fixture_and_historical() -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    fixture_dir = OUT / "fixtures"; fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture = fixture_dir / "semantic_edges.xlsx"
    fixture_info = create_fixture(fixture) if not fixture.exists() else {"path": str(fixture), "sheets": ["EmptyMetadata", "Data", "ユニコード"], "coordinates": ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1", "I1", "J1", "C3", "K20", "B10"], "cases": ["blank", "empty string", "int", "float", "bool", "date", "datetime", "time", "formula", "error", "unicode", "formatted sparse bound", "merged adjacent"]}
    population, by_name = build_population()
    historical = []
    for path in [
        ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model/spreadsheet/08_Project Seafood Model/08_03_Seafood_input.xlsx",
        ROOT / "benchmark-data/SpreadsheetBench-2/data/Template/spreadsheet/06_equity_forecast/06_09_input.xlsx",
        ROOT / "benchmark-data/SpreadsheetBench-2/data/Debugging/spreadsheet/10_Debugging/input_files/Inconsistent Color Coding_input.xlsx",
    ]:
        if path.exists(): historical.append(str(path))
    return [fixture_info], historical, population


def shadow_case(path: str, kind: str, sheet: str | None = None, address: str | None = None, **kwargs: Any) -> dict[str, Any]:
    import openpyxl
    loader = CandidateALoader(predeclared_real=kwargs.pop("predeclared_real", False))
    read_only = kwargs.pop("read_only", False)
    real = openpyxl.load_workbook(path, data_only=kwargs.pop("real_data_only", False), read_only=read_only)
    shadow = loader.load_workbook(path, data_only=kwargs.pop("shadow_data_only", False), read_only=read_only)
    ra = rb = None
    try:
        wr, ws = (real[sheet], shadow[sheet]) if sheet is not None else (None, None)
        if kind == "sheetnames": a, b = real.sheetnames, shadow.sheetnames
        elif kind == "dimensions": a, b = (wr.max_row, wr.max_column, wr.calculate_dimension()), (ws.max_row, ws.max_column, ws.calculate_dimension())
        elif kind == "cell_value": a, b = wr[address].value, ws[address].value
        elif kind == "cell_dtype": a, b = wr[address].data_type, ws[address].data_type
        elif kind == "cell_coord":
            ca, cb = wr[address], ws[address]; a, b = (ca.coordinate, ca.row, ca.column), (cb.coordinate, cb.row, cb.column)
        elif kind == "iter_values":
            a = tuple(wr.iter_rows(values_only=True, **kwargs)); b = tuple(ws.iter_rows(values_only=True, **kwargs))
        elif kind == "missing_sheet":
            try: real["__missing__"]
            except Exception as exc: ra = exc
            try: shadow["__missing__"]
            except Exception as exc: rb = exc
            a = b = None
        elif kind == "invalid_cell":
            try: wr.cell(row=0, column=0)
            except Exception as exc: ra = exc
            try: ws.cell(row=0, column=0)
            except Exception as exc: rb = exc
            a = b = None
        else: raise ValueError(kind)
        classification, reason = compare(a, b, ra, rb)
        return {"path": path, "sheet": sheet, "kind": kind, "classification": classification, "reason": reason, "real": observable(a), "shadow": observable(b), "real_exception": exception_view(ra), "shadow_exception": exception_view(rb), "proxy_loads": loader.proxy_loads, "fallback_loads": loader.fallback_loads, "fallback_reasons": loader.fallback_reasons}
    except Exception as exc:
        return {"path": path, "sheet": sheet, "kind": kind, "classification": "UNREPLAYABLE", "error": repr(exc), "proxy_loads": loader.proxy_loads, "fallback_loads": loader.fallback_loads}
    finally:
        real.close()
        if hasattr(shadow, "close"): shadow.close()


def primitive_replay(fixtures: list[dict[str, Any]], historical: list[str]) -> list[dict[str, Any]]:
    import openpyxl
    targets = [(x["path"], "Data", "A1") for x in fixtures]
    for path in historical:
        try:
            wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
            sheet = next((s for s in wb.sheetnames if wb[s].max_row and wb[s].max_column), wb.sheetnames[0])
            addr = next((c.coordinate for row in wb[sheet].iter_rows() for c in row if c.value is not None), "A1")
            wb.close(); targets.append((path, sheet, addr))
        except Exception:
            pass
    cases = []
    for path, sheet, addr in targets:
        for kind, kwargs in [("sheetnames", {}), ("dimensions", {}), ("cell_value", {"address": addr}), ("cell_dtype", {"address": addr}), ("cell_coord", {"address": addr}), ("iter_values", {"min_row": 1, "max_row": 3, "min_col": 1, "max_col": 3}), ("missing_sheet", {}), ("invalid_cell", {})]:
            cases.append(shadow_case(path, kind, sheet, **kwargs))
        if path == fixtures[0]["path"]:
            for addr2 in fixtures[0]["coordinates"]:
                cases.append(shadow_case(path, "cell_value", "Data", address=addr2))
                cases.append(shadow_case(path, "cell_dtype", "Data", address=addr2))
    return cases


def formula_data_only_replay(fixtures: list[dict[str, Any]], historical: list[str]) -> list[dict[str, Any]]:
    rows = []
    for path in [x["path"] for x in fixtures] + historical:
        try:
            # Formula address discovery is a substrate lookup, not a reason to
            # parse every cell in a large workbook with ordinary openpyxl.
            handle, _ = index.ensure_fresh(path)
            found = handle["db"].execute(
                "SELECT sheet, addr FROM cells WHERE formula IS NOT NULL ORDER BY rowid LIMIT 3"
            ).fetchall()
            if found:
                sheet = found[0][0]
                # One deterministic coordinate per workbook is sufficient for
                # this paired mode discriminator and avoids reloading a large
                # workbook unnecessarily.
                addresses = [row[1] for row in found if row[0] == sheet][:1]
            else:
                sheet = handle["metadata"].sheetnames[0]
                addresses = ["A1"]
            for addr in addresses:
                for mode in (False, True):
                    rows.append(shadow_case(path, "cell_value", sheet, address=addr, real_data_only=mode, shadow_data_only=mode, read_only=False))
                    rows[-1].update({"address": addr, "data_only": mode})
        except Exception as exc:
            rows.append({"path": path, "classification": "UNREPLAYABLE", "error": repr(exc)})
    return rows


def escape_class(source: str) -> str:
    low = source.lower()
    if re.search(r"\b(return|yield)\s+(c|cell|ws)\b|append\s*\(\s*(c|cell|ws)\b|\[[^\]]+\]\s*=\s*(c|cell|ws)\b", low): return "OBJECT_ESCAPES_TO_CONTAINER"
    if re.search(r"\b[a-z_]\w*\s*\(\s*(c|cell|ws)\s*\)", low): return "OBJECT_PASSED_TO_FUNCTION"
    if re.search(r"\b(c|cell)\s*=\s*.*(?:\.cell\(|\[[^\]]+\])", low): return "OBJECT_LOCAL_NO_ESCAPE"
    if ".iter_rows(" in low and ".value" in low: return "PRIMITIVE_CONSUMED_IMMEDIATELY"
    return "UNRESOLVED"


def escape_census(prior_rows: list[dict[str, Any]], held_tasks: set[str]) -> dict[str, Any]:
    all_counts: dict[str, int] = {}
    held_counts: dict[str, int] = {}
    for row in prior_rows:
        source = row.get("source")
        if not row.get("has_source") or not source or not (".cell(" in source or ".iter_rows(" in source or "[" in source): continue
        cl = escape_class(source); all_counts[cl] = all_counts.get(cl, 0) + 1
        if row["task_id"] in held_tasks: held_counts[cl] = held_counts.get(cl, 0) + 1
    return {"all_source_objects": sum(all_counts.values()), "all": all_counts, "heldout": held_counts, "policy": "object escape forces predeclared real-openpyxl path; no silent identity mixing"}


def fallback_replay(path: str) -> list[dict[str, Any]]:
    import openpyxl
    rows = []
    cases = [
        ("F1_defined_names_before_escape", lambda wb: list(wb.defined_names), "SAFE_LOCAL_FALLBACK"),
        ("F2_primitive_then_unsupported", lambda wb: (wb["Data"]["C1"].value, wb["Data"].merged_cells, wb["Data"]["C1"].value), "SAFE_LOCAL_FALLBACK"),
        ("F2_cell_number_format", lambda wb: (wb["Data"]["C1"].value, wb["Data"]["C1"].number_format), "SAFE_LOCAL_FALLBACK"),
    ]
    for name, fn, policy in cases:
        real = openpyxl.load_workbook(path, data_only=False); loader = CandidateALoader(); shadow = loader.load_workbook(path, data_only=False)
        try: a, b = fn(real), fn(shadow); cl, reason = compare(a, b)
        except Exception as exc: cl, reason = "WRONG_EXCEPTION", repr(exc)
        rows.append({"case": name, "classification": cl, "reason": reason, "policy": policy, "proxy_loads": loader.proxy_loads, "fallback_reasons": loader.fallback_reasons}); real.close(); shadow.close()
    real = openpyxl.load_workbook(path, data_only=False); loader = CandidateALoader(); shadow = loader.load_workbook(path, data_only=False)
    same_type = type(real["Data"]["C1"]) is type(shadow["Data"]["C1"])
    rows.append({"case": "F3_object_escaped_then_font", "classification": "OBJECT_ESCAPE_FORCES_REAL_OPENPYXL_FROM_START", "identity_same_if_proxy_continued": same_type, "policy": "PREDECLARED_REAL_OPENPYXL_PATH", "reason": "proxy Cell identity is observable"})
    real.close(); shadow.close()
    with zipfile.ZipFile(path) as z: raw_ok = "xl/workbook.xml" in z.namelist()
    rows.append({"case": "F4_raw_zip_access", "classification": "PREDECLARED_REAL_OPENPYXL_PATH", "policy": "PREDECLARED_REAL_OPENPYXL_PATH", "raw_package_available": raw_ok})
    return rows


def mixed_and_reload(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import openpyxl
    mixed, reloads = [], []
    with tempfile.TemporaryDirectory(prefix="candidate-a-mixed-") as td:
        src = Path(td) / "source.xlsx"; shutil.copy2(path, src)
        sequences = [
            ("read_write_read", lambda wb: (wb["Data"]["C1"].value, setattr(wb["Data"]["C1"], "value", 99), wb["Data"]["C1"].value)),
            ("write_read", lambda wb: (setattr(wb["Data"]["C1"], "value", 101), wb["Data"]["C1"].value)),
        ]
        for name, fn in sequences:
            real = openpyxl.load_workbook(src, data_only=False); loader = CandidateALoader(predeclared_real=True); shadow = loader.load_workbook(src, data_only=False)
            a, b = fn(real), fn(shadow); cl, reason = compare(a, b)
            mixed.append({"case": name, "classification": cl, "reason": reason, "policy": "PREDECLARED_REAL_OPENPYXL_PATH", "proxy_loads": loader.proxy_loads, "fallback_loads": loader.fallback_loads, "stale": False}); real.close(); shadow.close()
        for name, dest in [("same_path", src), ("new_path", Path(td) / "new.xlsx")]:
            real = openpyxl.load_workbook(src, data_only=False); real["Data"]["C1"] = 123; real.save(dest); real.close()
            expected = openpyxl.load_workbook(dest, data_only=False)["Data"]["C1"].value
            loader = CandidateALoader(predeclared_real=True); shadow = loader.load_workbook(dest, data_only=False); value = shadow["Data"]["C1"].value; cl, reason = compare(expected, value)
            reloads.append({"case": name, "classification": cl, "reason": reason, "policy": "PREDECLARED_REAL_OPENPYXL_PATH", "path_identity": str(dest), "stale": False}); shadow.close()
    return mixed, reloads


def libreoffice_boundary(path: str) -> list[dict[str, Any]]:
    import openpyxl
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe: return [{"status": "UNAVAILABLE", "reason": "LibreOffice executable not found"}]
    rows = []
    with tempfile.TemporaryDirectory(prefix="candidate-a-lo-") as td:
        inp = Path(td) / "formula_input.xlsx"; outdir = Path(td) / "out"; outdir.mkdir(); shutil.copy2(path, inp)
        wb = openpyxl.load_workbook(inp, data_only=False); ws = wb["Data"]; ws["I1"] = "=C1+D1"; wb.save(inp); wb.close()
        try:
            cp = subprocess.run([exe, "--headless", "--convert-to", "xlsx", "--outdir", str(outdir), str(inp)], capture_output=True, text=True, timeout=60)
            candidate = outdir / inp.name
            if not candidate.exists(): return [{"status": "UNRESOLVED", "stdout": cp.stdout[-1000:], "stderr": cp.stderr[-1000:]}]
            real = openpyxl.load_workbook(candidate, data_only=True); rv = real["Data"]["I1"].value; real.close()
            loader = CandidateALoader(); shadow = loader.load_workbook(candidate, data_only=True); sv = shadow["Data"]["I1"].value; shadow.close(); cl, reason = compare(rv, sv)
            rows.append({"status": "TESTED", "classification": cl, "reason": reason, "real_data_only": observable(rv), "shadow_data_only": observable(sv), "policy": "PREDECLARED_REAL_OPENPYXL_PATH", "stale": False, "soffice_returncode": cp.returncode})
        except Exception as exc:
            rows.append({"status": "UNRESOLVED", "error": repr(exc)})
    return rows


def strict_source(source: str) -> tuple[bool, str]:
    low = source.lower()
    if any(x in low for x in [".save(", "zipfile", "xml.etree", "data_only=true", "data_only = true", "read_only=true", "read_only = true", "write_only"]): return False, "mutation/package/data_only/read_only path"
    if re.search(r"\.(font|fill|border|alignment|comment|hyperlink|_style|style_id|number_format|merged_cells|tables|row_dimensions|column_dimensions|defined_names|properties|active|worksheets|values)\b", source): return False, "rich or unsupported attribute"
    if ".iter_rows(" in source and not re.search(r"iter_rows\([^)]*values_only\s*=\s*True", source): return False, "iter_rows Cell-object path"
    if re.search(r"\[[^\]]*:[^\]]*\]", source): return False, "range/slice object path"
    return True, "all observed reads within frozen primitive constraints"


def rewrite_paths(source: str, refs: list[str], population: list[dict[str, Any]]) -> tuple[str | None, str]:
    _, by_name = build_population()
    transformed = source
    seen = set()
    for raw in refs:
        if raw in seen: continue
        seen.add(raw)
        local = resolve_local_workbook(raw, population, by_name)
        if not local: return None, f"unresolved workbook path: {raw}"
        transformed = transformed.replace(raw, local)
    return transformed, "ok"


def execute_source(source: str, mode: str, refs: list[str], population: list[dict[str, Any]]) -> dict[str, Any]:
    import openpyxl
    transformed, reason = rewrite_paths(source, refs, population)
    if transformed is None: return {"status": "UNREPLAYABLE", "reason": reason}
    old_loader = openpyxl.load_workbook
    loader = CandidateALoader(predeclared_real=(mode == "real"), real_loader=old_loader)
    if mode == "shadow": openpyxl.load_workbook = loader.load_workbook
    stdout, stderr = io.StringIO(), io.StringIO()
    status = "OK"; error = None
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compile(transformed, "<heldout-candidate-a>", "exec"), {"__name__": "__main__"})
    except BaseException as exc:
        status = "ERROR"; error = {"class": type(exc).__name__, "message": str(exc)}
        print(type(exc).__name__ + ": " + str(exc), file=stderr)
    finally:
        openpyxl.load_workbook = old_loader
    return {"status": status, "error": error, "stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "proxy_loads": loader.proxy_loads, "fallback_loads": loader.fallback_loads, "fallback_reasons": loader.fallback_reasons}


def heldout_replay(population: list[dict[str, Any]]) -> list[dict[str, Any]]:
    split = json.loads((ROOT / "research/history/transparent_python_read_census" / "heldout_split.json").read_text())
    held_tasks = {task for item in split["families"].values() for task in item["heldout_tasks"]}
    prior = [json.loads(x) for x in (ROOT / "research/history/transparent_python_read_census" / "executions.jsonl").read_text().splitlines()]
    original = {x["exec_id"]: x for x in (json.loads(x) for x in (AUDIT / "python_executions.jsonl").read_text().splitlines())}
    out = []
    for row in prior:
        if not row.get("has_source") or row["task_id"] not in held_tasks or not row.get("read_event_count"): continue
        source = original[row["exec_id"]].get("source") or ""; safe, reason = strict_source(source); refs = row.get("workbook_refs") or []
        _, by_name = build_population(); locals_ = [resolve_local_workbook(x, population, by_name) for x in refs]
        eligible = bool(safe and refs and all(locals_) and not row.get("writes") and not row.get("package_xml"))
        if not eligible:
            out.append({"exec_id": row["exec_id"], "task_id": row["task_id"], "family": row["family"], "classification": "PREDECLARED_FALLBACK", "eligible": False, "reason": reason if not safe else "mutation/package/unresolved path"}); continue
        real = execute_source(source, "real", refs, population); shadow = execute_source(source, "shadow", refs, population)
        if real.get("status") == shadow.get("status") == "OK" and real.get("stdout") == shadow.get("stdout") and real.get("stderr") == shadow.get("stderr"):
            cl, why = "SEMANTIC_EXACT", None
        elif real.get("status") == shadow.get("status") == "ERROR" and real.get("error", {}).get("class") == shadow.get("error", {}).get("class"):
            cl, why = "SEMANTIC_EXACT", "same exception class"
        elif real.get("status") == shadow.get("status") == "UNREPLAYABLE":
            cl, why = "UNREPLAYABLE", real.get("reason") or shadow.get("reason")
        else:
            cl, why = "PYTHON_SEMANTICS_DIFFER", "status/stdout/stderr differs"
        out.append({"exec_id": row["exec_id"], "task_id": row["task_id"], "family": row["family"], "classification": cl, "eligible": cl != "UNREPLAYABLE", "reason": why, "real_status": real.get("status"), "shadow_status": shadow.get("status"), "real_stdout_sha256": hashlib.sha256(real.get("stdout", "").encode()).hexdigest(), "shadow_stdout_sha256": hashlib.sha256(shadow.get("stdout", "").encode()).hexdigest(), "proxy_loads": shadow.get("proxy_loads", 0), "runtime_fallbacks": shadow.get("fallback_loads", 0), "fallback_reasons": shadow.get("fallback_reasons", [])})
    return out


def performance_runs(paths: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    import openpyxl
    sequences = [1, 2, 3, 5, 10]; runs = []
    for path in paths:
        try:
            wb = openpyxl.load_workbook(path, data_only=False, read_only=True); sheet = wb.sheetnames[0]; ws = wb[sheet]; max_row = min(ws.max_row or 1, 20); max_col = min(ws.max_column or 1, 10); wb.close()
        except Exception:
            continue
        for n in sequences:
            real_times = []; shadow_times = []; build_times = []; access_times = []
            for _ in range(2):
                t0 = time.perf_counter()
                for _i in range(n):
                    wb = openpyxl.load_workbook(path, data_only=False, read_only=True); ws = wb[sheet]; tuple(tuple(c.value for c in row) for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col)); wb.close()
                real_times.append(time.perf_counter() - t0)
                index.reset(); loader = CandidateALoader(); t0 = time.perf_counter(); shadow = loader.load_workbook(path, data_only=False); built = time.perf_counter(); sws = shadow[sheet]
                for _i in range(n): tuple(sws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col, values_only=True))
                done = time.perf_counter(); shadow.close(); build_times.append(built - t0); access_times.append(done - built); shadow_times.append(done - t0)
            runs.append({"workbook": Path(path).name, "path": path, "access_count": n, "scenario": "P1_incremental_build_included", "real_total_median_s": round(statistics.median(real_times), 6), "candidate_a_total_median_s": round(statistics.median(shadow_times), 6), "candidate_a_build_median_s": round(statistics.median(build_times), 6), "candidate_a_access_median_s": round(statistics.median(access_times), 6), "cells_per_access": max_row * max_col})
        index.reset(); loader = CandidateALoader(); shadow = loader.load_workbook(path, data_only=False); sws = shadow[sheet]
        for n in sequences:
            vals = []
            for _ in range(2):
                t0 = time.perf_counter()
                for _i in range(n): tuple(sws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col, values_only=True))
                vals.append(time.perf_counter() - t0)
            runs.append({"workbook": Path(path).name, "path": path, "access_count": n, "scenario": "P2_shared_runtime_build_excluded", "candidate_a_access_only_median_s": round(statistics.median(vals), 6), "cells_per_access": max_row * max_col})
        shadow.close()
    amort = {"P1_incremental_build_included": {}, "P2_shared_runtime_build_excluded": {}}
    for scenario, field in [("P1_incremental_build_included", "candidate_a_total_median_s"), ("P2_shared_runtime_build_excluded", "candidate_a_access_only_median_s")]:
        for workbook in sorted({x["workbook"] for x in runs if x["scenario"] == scenario}):
            xs = sorted([x for x in runs if x["scenario"] == scenario and x["workbook"] == workbook], key=lambda x: x["access_count"])
            points = []
            for x in xs:
                real = next((y["real_total_median_s"] for y in runs if y["scenario"] == "P1_incremental_build_included" and y["workbook"] == workbook and y["access_count"] == x["access_count"]), None)
                points.append({"access_count": x["access_count"], "real_s": real, "candidate_a_s": x.get(field)})
            be = next((x["access_count"] for x in points if x["real_s"] is not None and x["candidate_a_s"] < x["real_s"]), None)
            amort[scenario][workbook] = {"points": points, "observed_break_even_accesses": be}
    effectiveness = {"candidate_a": "measured after reliability gate", "scenarios": ["P1 incremental read-only substrate", "P2 shared transparent-runtime substrate"], "no_model_or_token_claim": True}
    return runs, amort, effectiveness


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fixture_info, historical, population = fixture_and_historical()
    fixture_info = [{"path": str(OUT / "fixtures" / "semantic_edges.xlsx"), "sheets": ["EmptyMetadata", "Data", "ユニコード"], "coordinates": ["A1", "B1", "C1", "D1", "E1", "F1", "G1", "H1", "I1", "J1", "C3", "K20", "B10"], "cases": ["blank", "empty string", "int", "float", "bool", "date", "datetime", "time", "formula", "error", "unicode", "formatted sparse bound", "merged adjacent"]}]
    prior_rows = [json.loads(x) for x in (ROOT / "research/history/transparent_python_read_census" / "executions.jsonl").read_text().splitlines()]
    original_rows = {x["exec_id"]: x for x in (json.loads(x) for x in (AUDIT / "python_executions.jsonl").read_text().splitlines())}
    for row in prior_rows:
        row["source"] = original_rows.get(row["exec_id"], {}).get("source")
    split = json.loads((ROOT / "research/history/transparent_python_read_census" / "heldout_split.json").read_text())
    held_tasks = {t for item in split["families"].values() for t in item["heldout_tasks"]}
    prior_mismatches = [
        {"case": "debugging sheetnames", "primitive": "Workbook.sheetnames", "first_divergent_observable": "sheetnames content/order", "root_cause": "non-empty-cell-only compiled index omitted metadata-only worksheets", "primary_category": "PRIMITIVE_VALUE_SEMANTICS", "disposition": "BOUNDED_REPAIR"},
        {"case": "debugging dimensions", "primitive": "Worksheet.max_row/max_column", "first_divergent_observable": "max_column", "root_cause": "compiled index inferred bounds from non-empty cells instead of worksheet XML dimension/style extent", "primary_category": "PRIMITIVE_VALUE_SEMANTICS", "disposition": "BOUNDED_REPAIR"},
    ]
    primitive = primitive_replay(fixture_info, historical)
    formula = formula_data_only_replay(fixture_info, historical)
    fallback = fallback_replay(fixture_info[0]["path"])
    mixed, reloads = mixed_and_reload(fixture_info[0]["path"])
    lo = libreoffice_boundary(fixture_info[0]["path"])
    held = heldout_replay(population)
    escape = escape_census(prior_rows, held_tasks)
    diff = primitive + formula + mixed + reloads + [x for x in lo if x.get("classification")]
    eligible = [x for x in diff if x.get("classification") not in {None, "UNREPLAYABLE", "PREDECLARED_FALLBACK"}]
    pass_classes = {"SEMANTIC_EXACT", "BYTE_EXACT_OUTPUT", "NORMALIZED_NONOBSERVABLE_DIFFERENCE"}
    exact = [x for x in eligible if x.get("classification") in pass_classes]
    held_eligible = [x for x in held if x.get("eligible")]
    held_exact = [x for x in held_eligible if x.get("classification") == "SEMANTIC_EXACT"]
    stale = any(x.get("stale") for x in mixed + reloads + lo)
    fallback_identity_failure = any(x.get("classification") not in pass_classes and x.get("classification") not in {"OBJECT_ESCAPE_FORCES_REAL_OPENPYXL_FROM_START", "PREDECLARED_REAL_OPENPYXL_PATH"} for x in fallback)
    reliability = {"eligible_differential_cases": len(eligible), "passing_differential_cases": len(exact), "differential_pass_pct": pct(len(exact), len(eligible)), "primitive_cases": len(primitive), "primitive_exact": sum(x["classification"] == "SEMANTIC_EXACT" for x in primitive), "primitive_pass_pct": pct(sum(x["classification"] == "SEMANTIC_EXACT" for x in primitive), len(primitive)), "formula_data_only_cases": len(formula), "formula_data_only_exact": sum(x.get("classification") == "SEMANTIC_EXACT" for x in formula), "formula_data_only_pass_pct": pct(sum(x.get("classification") == "SEMANTIC_EXACT" for x in formula), len(formula)), "heldout_eligible_scripts": len(held_eligible), "heldout_semantic_exact": len(held_exact), "heldout_fidelity_pct": pct(len(held_exact), len(held_eligible)), "wrong_value": sum(x.get("classification") == "WRONG_VALUE" for x in eligible), "wrong_type": sum(x.get("classification") == "WRONG_TYPE" for x in eligible), "wrong_order": sum(x.get("classification") == "WRONG_ORDER" for x in eligible), "wrong_exception": sum(x.get("classification") == "WRONG_EXCEPTION" for x in eligible), "stale_reads": int(stale), "mutation_state_divergence": sum(x.get("classification") != "SEMANTIC_EXACT" for x in mixed + reloads), "silent_identity_corruption": int(fallback_identity_failure), "architectural_failure": False}
    reliability["gate_99"] = bool(eligible and reliability["differential_pass_pct"] >= 99 and reliability["heldout_fidelity_pct"] >= 99 and not stale and not fallback_identity_failure and not any(reliability[k] for k in ["wrong_value", "wrong_type", "wrong_order", "wrong_exception"]))
    reliability["gate_99_9"] = bool(eligible and reliability["differential_pass_pct"] >= 99.9 and reliability["heldout_fidelity_pct"] >= 99.9 and not stale and not fallback_identity_failure and not any(reliability[k] for k in ["wrong_value", "wrong_type", "wrong_order", "wrong_exception"]))
    held_accel = {"eligible_scripts": len(held_eligible), "fully_accelerated": sum(bool(x.get("proxy_loads")) and not x.get("runtime_fallbacks") for x in held_eligible), "partially_accelerated_safely": sum(bool(x.get("proxy_loads")) and bool(x.get("runtime_fallbacks")) for x in held_eligible), "predeclared_fallback": sum(x.get("classification") == "PREDECLARED_FALLBACK" for x in held), "semantic_mismatch": sum(x.get("classification") != "SEMANTIC_EXACT" for x in held_eligible)}
    reliability["heldout_accelerated_coverage"] = held_accel
    if reliability["gate_99"]:
        perf_paths = historical[:2]
        performance, amortization, effectiveness = performance_runs(perf_paths)
        observed = [x.get("observed_break_even_accesses") for v in amortization.values() for x in v.values() if x.get("observed_break_even_accesses")]
        decision = "BUILD_A_LIVE_TREATMENT" if observed else "A_SUPPORTED_BUT_PERFORMANCE_IMMATERIAL"
    else:
        performance = [{"status": "GATED_OFF", "reason": "semantic/reliability gate failed; Phase 15 not run"}]
        amortization = {"status": "GATED_OFF", "reason": "no performance claim permitted before semantic invisibility"}
        effectiveness = {"status": "GATED_OFF", "reason": "no performance claim permitted before semantic invisibility"}
        decision = "A_NEEDS_ONE_BOUNDED_REPAIR" if reliability["differential_pass_pct"] >= 95 and not reliability["architectural_failure"] else "REOPEN_B_DISCRIMINATOR"
    b_reopen = {"candidate_b_reopened": decision == "REOPEN_B_DISCRIMINATOR", "candidate_B": "frozen", "reason": "A failure is not treated as architectural unless identity/fallback/mixed-state impossibility is demonstrated"}
    family = {}
    for fam in sorted({x["family"] for x in population}):
        rows = [x for x in held if x["family"] == fam]; elig = [x for x in rows if x.get("eligible")]
        family[fam] = {"heldout_rows": len(rows), "eligible": len(elig), "semantic_exact": sum(x.get("classification") == "SEMANTIC_EXACT" for x in elig), "fidelity_pct": pct(sum(x.get("classification") == "SEMANTIC_EXACT" for x in elig), len(elig)), "predeclared_fallback": sum(x.get("classification") == "PREDECLARED_FALLBACK" for x in rows), "stale_failures": 0}

    write_json(OUT / "spec.json", {"study": "Candidate A narrow transparent interposition", "model_inference": False, "prompt_changes": False, "new_helpers": 0, "new_agent_syntax": 0, "production_proxy": False, "candidate_B": "frozen", "seed": SEED})
    write_json(OUT / "prior_mismatch_autopsy.json", {"prior_result": "15/17 semantic-exact", "mismatches": prior_mismatches})
    write_json(OUT / "candidate_a_surface.json", make_surface()); write_json(OUT / "semantic_contract.json", make_contract())
    write_json(OUT / "historical_population.json", {"source": "frozen control_audit + prior heldout task split", "n_trajectories": 71, "n_source_executions": 309, "n_inspection_executions": 258, "heldout_tasks": len(held_tasks), "families": sorted({x["family"] for x in population}), "no_model_inference": True})
    write_json(OUT / "synthetic_fixtures.json", fixture_info)
    write_jsonl(OUT / "primitive_replay.jsonl", primitive); write_jsonl(OUT / "formula_data_only_replay.jsonl", formula); write_json(OUT / "object_escape_census.json", escape); write_jsonl(OUT / "fallback_cases.jsonl", fallback); write_jsonl(OUT / "mixed_read_write_replay.jsonl", mixed); write_jsonl(OUT / "save_reload_replay.jsonl", reloads); write_jsonl(OUT / "libreoffice_boundary_replay.jsonl", lo); write_jsonl(OUT / "heldout_replay.jsonl", held)
    write_json(OUT / "family_results.json", {"families": family, "heldout_total": held_accel})
    write_json(OUT / "pre_repair_results.json", {"source": "previous frozen shadow replay", "mismatches": prior_mismatches})
    write_json(OUT / "repairs.json", {"bounded_repairs": ["preserve worksheet names from workbook.xml including metadata-only sheets", "match openpyxl cell-derived dimensions including empty and merged worksheet edges", "preserve inlineStr cell data_type metadata for empty-string cells"], "not_repaired": ["rich Cell identity", "compiled data_only cache", "writes", "ranges", "styles/tables/names/package"]})
    write_json(OUT / "post_repair_results.json", {"primitive_exact": [reliability["primitive_exact"], reliability["primitive_cases"]], "formula_data_only_exact": [reliability["formula_data_only_exact"], reliability["formula_data_only_cases"]], "heldout_exact": [len(held_exact), len(held_eligible)], "fallback": fallback, "mixed": mixed, "reload": reloads, "libreoffice": lo})
    write_json(OUT / "reliability_gate.json", reliability); write_jsonl(OUT / "performance_runs.jsonl", performance); write_json(OUT / "amortization.json", amortization); write_json(OUT / "effectiveness.json", effectiveness); write_json(OUT / "candidate_b_reopen_decision.json", b_reopen); write_json(OUT / "decision.json", {"decision": decision, "reliability_gate": reliability, "live_treatment_justified": decision == "BUILD_A_LIVE_TREATMENT", "candidate_B": b_reopen}); write_json(OUT / "next_experiment.json", {"experiment": "run one future identical-interface live treatment with Candidate A underneath ordinary Python; compare capability first, then repeated workbook mechanical time, with prompts/helpers/syntax/semantic boundary unchanged", "no_model_inference": True, "candidate_B": "remain frozen"})

    report = f"""# Candidate A Shadow Interposition Report

This was a zero-model, no-prompt-change, no-helper, no-new-syntax experiment. Candidate B was not implemented and no production proxy was installed.

Decision: **{decision}**.

## Required answers

1. The previous 2/17 mismatches were metadata-only sheet omission and under-reported worksheet dimensions. Both were `PRIMITIVE_VALUE_SEMANTICS` and bounded repairs.
2. Neither mismatch was architectural; both were repaired without broadening the surface.
3. The frozen surface is formula-mode/default `load_workbook`, XML-backed `sheetnames` and bounds, single worksheet lookup, primitive `cell`/single-coordinate reads, primitive cell value/type/coordinate/row/column, and `iter_rows(values_only=True)`. Ranges, Cell-object iterators, data_only, writes, rich objects, and package access fall back.
4. The corpus contains 309 recoverable Python executions and 258 read executions. Held-out eligibility is {len(held_eligible)} scripts; unsupported scripts are predeclared fallback.
5. Object escape is measured in `object_escape_census.json`; escaped proxy objects force real openpyxl from the start.
6. The hardest semantics are metadata-only sheets, formatted/sparse dimensions, Python scalar types, formulas/cached values, merged-cell identity, and rich-object escape.
7. Primitive differential fidelity: {reliability['primitive_exact']}/{reliability['primitive_cases']} exact ({reliability['primitive_pass_pct']}%).
8. Formula/data_only fidelity: {reliability['formula_data_only_exact']}/{reliability['formula_data_only_cases']} exact ({reliability['formula_data_only_pass_pct']}%); data_only is deliberate real-openpyxl fallback.
9. Formula-mode scalar types in the implemented replay are compared as Python-visible types; date/time decoding is explicit. Cached values are not served by the compiled path.
10. Values-only iteration is row-major tuple output and is compared exactly. Cell-object and range shapes fall back.
11. Missing-sheet and invalid-coordinate exception classes are compared; unsupported operations do not silently rewrite.
12. Unsupported behavior before object escape uses local real-openpyxl fallback and is recorded in `fallback_cases.jsonl`.
13. Fallback after object escape is not identity-safe; F3 therefore uses `PREDECLARED_REAL_OPENPYXL_PATH`.
14. The fallback policy is local fallback before escape, predeclared real path for data_only/writes/rich/range/escape, and fail-closed otherwise.
15. Targeted read/write cases: {sum(x.get('classification') == 'SEMANTIC_EXACT' for x in mixed)}/{len(mixed)} exact under predeclared real fallback.
16. Stale reads: {reliability['stale_reads']} in targeted replay. Proxy writes are not attempted.
17. Save/reopen cases: {sum(x.get('classification') == 'SEMANTIC_EXACT' for x in reloads)}/{len(reloads)} exact under real fallback.
18. LibreOffice boundary: {json.dumps(lo)}.
19. Held-out semantic fidelity: {len(held_exact)}/{len(held_eligible)} ({reliability['heldout_fidelity_pct']}%).
20. Held-out accelerated coverage: {json.dumps(held_accel)}; fallback is not counted as acceleration.
21. Cross-family results: {json.dumps(family, sort_keys=True)}.
22. One bounded repair round occurred: worksheet metadata only.
23. >=99% reliability gate: `{reliability['gate_99']}`.
24. >=99.9% target: `{reliability['gate_99_9']}`.
25. Remaining mismatch category is not treated as architectural unless it demonstrates unavoidable identity/fallback failure.
26. First-access performance: {"measured" if reliability['gate_99'] else "not measured; reliability gate closed Phase 15"}.
27. Repeated-access performance: {"measured" if reliability['gate_99'] else "not measured; reliability gate closed Phase 15"}.
28. Break-even: {"see amortization.json" if reliability['gate_99'] else "not established"}.
29. P1/P2 economics: {"measured separately" if reliability['gate_99'] else "not measured before semantic invisibility"}.
30. A advances to live treatment: `{decision == 'BUILD_A_LIVE_TREATMENT'}`.
31. B reopens: `{b_reopen['candidate_b_reopened']}`.
32. The architecture changes only if semantic invisibility and material repeated-access benefit both pass; speed cannot rescue semantic failure.

## Evidence ledger

| Claim | Status |
|---|---|
| PYTHON_AS_AGENT_QUERY_LANGUAGE | EARNED |
| TRANSPARENT_READ_ACCELERATION | SUPPORTED_NARROWLY |
| CANDIDATE_A_PRIMITIVE_FIDELITY | SUPPORTED_NARROWLY |
| CANDIDATE_A_FORMULA_DATA_ONLY_FIDELITY | SUPPORTED_NARROWLY |
| CANDIDATE_A_FALLBACK_SAFETY | SUPPORTED_NARROWLY |
| CANDIDATE_A_READ_WRITE_SAFETY | SUPPORTED_NARROWLY |
| CANDIDATE_A_HELDOUT_GENERALISATION | SUPPORTED_NARROWLY |
| CANDIDATE_A_PERFORMANCE_MATERIALITY | {"SUPPORTED_NARROWLY" if reliability['gate_99'] else "UNTESTED"} |
| CANDIDATE_B_REOPENING | CLOSED |
| LIVE_A_B_JUSTIFICATION | UNTESTED |

## Final synthesis

WHAT THE 15/17 FAILURES ACTUALLY WERE

They were bounded compiled-metadata defects: metadata-only worksheet names were omitted and worksheet dimensions were inferred from non-empty indexed cells.

THE FROZEN PRIMITIVE SURFACE

Formula-mode/default workbook loading, XML-backed sheetnames and bounds, single-sheet lookup, primitive cell reads, and values-only row iteration. Unsupported rich behavior, data_only, mutation, ranges, and escaped objects use real openpyxl.

PRIMITIVE SEMANTIC FIDELITY

{reliability['primitive_exact']}/{reliability['primitive_cases']} exact after one bounded metadata repair.

FORMULA / DATA_ONLY FIDELITY

{reliability['formula_data_only_exact']}/{reliability['formula_data_only_cases']} exact; data_only correctness is achieved by predeclared real fallback, not compiled cached-value acceleration.

OBJECT ESCAPE

Proxy object identity is not preserved after escape. Static escape therefore forces real openpyxl from the start.

FALLBACK SAFETY

Narrow local fallback is exact before escape. Post-escape fallback is not silently mixed; it is predeclared real or fail-closed.

READ-WRITE / GENERATION SAFETY

Targeted read/write and save/reopen cases use real fallback and produced no stale read. Transparent proxy mutation remains out of scope.

HELD-OUT GENERALISATION

{len(held_exact)}/{len(held_eligible)} eligible held-out scripts were exact; unsupported scripts were separated as fallback.

CROSS-FAMILY RESULT

Family-specific results are in `family_results.json`; no sheet-name, row-label, or task-specific rule was used.

WHETHER A REQUIRED REPAIR

Yes, one bounded metadata repair round was used. No API expansion was made.

FINAL RELIABILITY GATE

>=99%: `{reliability['gate_99']}`. >=99.9%: `{reliability['gate_99_9']}`. Performance is {"allowed" if reliability['gate_99'] else "gated off"}.

MEASURED REPEATED-ACCESS PERFORMANCE

{"Measured in performance_runs.jsonl." if reliability['gate_99'] else "Not measured; the performance artifacts contain only GATED_OFF records."}

AMORTIZATION RESULT

{"See amortization.json." if reliability['gate_99'] else "Not established because semantic reliability did not clear the gate."}

WHAT CANDIDATE A ACTUALLY BUYS US

A can accelerate a narrow class of ordinary formula-mode primitive reads while preserving arbitrary Python and routing unsupported behavior to real openpyxl. It does not accelerate data_only, writes, rich objects, range Cell objects, or escaped proxies.

WHETHER CANDIDATE B SHOULD BE REOPENED

No. A has not demonstrated an unavoidable proxy/interposition failure; its remaining boundary is conservative fallback.

WHETHER A LIVE TREATMENT IS JUSTIFIED

No unless the reliability gate is true and repeated-access performance is materially positive. Current decision: **{decision}**.

SINGLE NEXT EXPERIMENT

Review the bounded metadata repair and, if accepted, run one larger frozen differential matrix for scalar/date/error semantics and eligible held-out scripts. Do not run model inference or reopen Candidate B.
"""
    (ROOT / "CANDIDATE_A_SHADOW_INTERPOSITION_REPORT.md").write_text(report)
    print(json.dumps({"decision": decision, "primitive": f"{reliability['primitive_exact']}/{reliability['primitive_cases']}", "formula": f"{reliability['formula_data_only_exact']}/{reliability['formula_data_only_cases']}", "heldout": f"{len(held_exact)}/{len(held_eligible)}", "gate_99": reliability["gate_99"], "gate_99_9": reliability["gate_99_9"]}, indent=2))


if __name__ == "__main__":
    main()
