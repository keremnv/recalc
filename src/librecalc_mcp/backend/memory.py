from __future__ import annotations

import re
from copy import deepcopy

from librecalc_mcp.domain.charts import ChartSpec, chart_compile_note
from librecalc_mcp.domain.formulas import (
    is_escaped_text,
    is_formula_text,
    normalize_formula_argument_separators,
    unescape_text,
)
from librecalc_mcp.domain.models import (
    CalcOperation,
    CellFormat,
    Matrix,
    SheetInfo,
    WorkbookInfo,
)

_RANGE_KEY = re.compile(
    r"^(?P<c1>\$?[A-Za-z]{1,3})(?P<r1>[1-9][0-9]*)"
    r"(?::(?P<c2>\$?[A-Za-z]{1,3})(?P<r2>[1-9][0-9]*))?$"
)


def _column_number(label: str) -> int:
    number = 0
    for character in label.lstrip("$").upper():
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def _column_label(number: int) -> str:
    label = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def _range_cells(cell_range: str) -> list[str]:
    match = _RANGE_KEY.fullmatch(cell_range)
    if match is None:
        raise ValueError(f"invalid A1 range: {cell_range}")
    start_column = _column_number(match.group("c1"))
    end_column = _column_number(match.group("c2") or match.group("c1"))
    start_row = int(match.group("r1"))
    end_row = int(match.group("r2") or match.group("r1"))
    return [
        f"{_column_label(column)}{row}"
        for row in range(start_row, end_row + 1)
        for column in range(start_column, end_column + 1)
    ]


def _shift_range_key(key: str, *, start_row: int, count: int, deleting: bool) -> str | None:
    match = _RANGE_KEY.fullmatch(key)
    if match is None:
        return key
    first = int(match.group("r1"))
    last = int(match.group("r2") or match.group("r1"))
    last_deleted = start_row + count - 1
    if deleting:
        if last < start_row:
            return key
        if first > last_deleted:
            first -= count
            last -= count
        elif start_row <= first and last <= last_deleted:
            return None
        else:
            return None
    else:
        if last < start_row:
            return key
        if first >= start_row:
            first += count
            last += count
        else:
            last += count
    start_label = f"{match.group('c1')}{first}"
    if match.group("c2") is None:
        return start_label
    return f"{start_label}:{match.group('c2')}{last}"


def _shift_sheet_maps(
    maps: list[dict[str, object]], *, start_row: int, count: int, deleting: bool
) -> None:
    for mapping in maps:
        shifted: dict[str, object] = {}
        for key, value in mapping.items():
            new_key = _shift_range_key(key, start_row=start_row, count=count, deleting=deleting)
            if new_key is not None:
                shifted[new_key] = value
        mapping.clear()
        mapping.update(shifted)


class MemoryCalcBackend:
    """Tiny backend for MCP/domain tests. Not a spreadsheet engine."""

    def __init__(self) -> None:
        self.sheets: dict[str, dict[str, Matrix]] = {"Sheet1": {}}
        self.formulas: dict[str, dict[str, str]] = {"Sheet1": {}}
        self.formats: dict[str, dict[str, CellFormat]] = {"Sheet1": {}}
        self.charts: dict[str, ChartSpec] = {}

    def health(self) -> dict[str, object]:
        return {"ok": True, "backend": "memory"}

    def inspect_charts(self, path: str | None = None) -> list[dict[str, object]]:
        del path
        return [
            {
                **spec.to_dict(),
                "compile_note": chart_compile_note(spec.chart_type),
            }
            for spec in self.charts.values()
        ]

    def inspect_workbook(self, path: str | None = None) -> WorkbookInfo:
        return WorkbookInfo(
            title="memory",
            url=None,
            sheets=[SheetInfo(name=name) for name in self.sheets],
        )

    def read_range(self, sheet: str, cell_range: str, path: str | None = None) -> dict[str, Matrix]:
        values = deepcopy(self.sheets[sheet].get(cell_range, []))
        formula = self.formulas[sheet].get(cell_range)
        formulas: Matrix = [[formula]] if formula is not None else []
        return {"values": values, "formulas": formulas, "errors": []}

    def read_ranges(
        self,
        ranges: list[tuple[str, str]],
        path: str | None = None,
        *,
        include_errors: bool = True,
    ) -> list[dict[str, Matrix]]:
        del include_errors
        return [self.read_range(sheet, cell_range, path) for sheet, cell_range in ranges]

    def read_formats(
        self,
        cells: list[tuple[str, str]],
        path: str | None = None,
    ) -> list[CellFormat]:
        del path
        return [deepcopy(self.formats.get(sheet, {}).get(address, {})) for sheet, address in cells]

    def write_range(
        self,
        sheet: str,
        cell_range: str,
        values: Matrix,
        path: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, object]:
        stored = deepcopy(values)
        formulas_written = 0
        for row in stored:
            for column, value in enumerate(row):
                if is_formula_text(value):
                    formulas_written += 1
                elif is_escaped_text(value):
                    row[column] = unescape_text(str(value))
        if formulas_written and len(stored) == 1 and len(stored[0]) == 1:
            # Toy single-cell model: record the formula so read_range reports it the
            # way the UNO backend does rather than as literal text.
            self.formulas.setdefault(sheet, {})[cell_range] = normalize_formula_argument_separators(
                str(stored[0][0])
            )
        self.sheets.setdefault(sheet, {})[cell_range] = stored
        return {
            "ok": True,
            "sheet": sheet,
            "range": cell_range,
            "rows": len(values),
            "formulas_written": formulas_written,
            "saved_to": output_path or path,
        }

    def execute_program(
        self,
        operations: list[CalcOperation],
        path: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for operation in operations:
            if operation.op == "create_sheet":
                assert operation.name
                self.sheets.setdefault(operation.name, {})
                self.formulas.setdefault(operation.name, {})
                self.formats.setdefault(operation.name, {})
                results.append({"op": operation.op, "ok": True, "name": operation.name})
            elif operation.op == "write_range":
                assert operation.sheet and operation.range and operation.values is not None
                results.append(
                    {
                        "op": operation.op,
                        **self.write_range(operation.sheet, operation.range, operation.values),
                    }
                )
            elif operation.op in {"set_formula", "fill_formula"}:
                assert operation.sheet and operation.range and operation.formula is not None
                self.formulas.setdefault(operation.sheet, {})[operation.range] = (
                    normalize_formula_argument_separators(operation.formula)
                )
                results.append({"op": operation.op, "ok": True})
            elif operation.op == "set_format":
                if not operation.sheet or not operation.range or operation.cell_format is None:
                    raise ValueError("set_format requires sheet, range, and format")
                cells = _range_cells(operation.range)
                sheet_formats = self.formats.setdefault(operation.sheet, {})
                for address in cells:
                    sheet_formats.setdefault(address, {}).update(deepcopy(operation.cell_format))
                results.append(
                    {
                        "op": operation.op,
                        "ok": True,
                        "sheet": operation.sheet,
                        "range": operation.range,
                        "cells_formatted": len(cells),
                    }
                )
            elif operation.op == "clear_range":
                assert operation.sheet and operation.range
                self.sheets.setdefault(operation.sheet, {}).pop(operation.range, None)
                self.formulas.setdefault(operation.sheet, {}).pop(operation.range, None)
                results.append({"op": operation.op, "ok": True})
            elif operation.op in {"insert_row", "delete_row"}:
                if not operation.sheet or operation.index is None:
                    raise ValueError(f"{operation.op} requires sheet and 1-based index")
                count = 1 if operation.count is None else operation.count
                if operation.index < 1 or count < 1:
                    raise ValueError(f"{operation.op} requires index >= 1 and count >= 1")
                sheet = operation.sheet
                self.sheets.setdefault(sheet, {})
                self.formulas.setdefault(sheet, {})
                self.formats.setdefault(sheet, {})
                _shift_sheet_maps(
                    [self.sheets[sheet], self.formulas[sheet], self.formats[sheet]],
                    start_row=operation.index,
                    count=count,
                    deleting=operation.op == "delete_row",
                )
                results.append(
                    {
                        "op": operation.op,
                        "ok": True,
                        "sheet": sheet,
                        "index": operation.index,
                        "count": count,
                    }
                )
            elif operation.op == "upsert_chart":
                if operation.chart is None:
                    raise ValueError("upsert_chart requires chart")
                spec = ChartSpec.from_dict(operation.chart)
                note = chart_compile_note(spec.chart_type)
                self.charts[spec.id] = spec
                results.append(
                    {
                        "op": operation.op,
                        "ok": note != "unsupported",
                        "chart_id": spec.id,
                        "compile_note": note,
                    }
                )
            elif operation.op == "delete_chart":
                if not operation.name:
                    raise ValueError("delete_chart requires name (chart id)")
                existed = operation.name in self.charts
                self.charts.pop(operation.name, None)
                results.append({"op": operation.op, "ok": True, "deleted": existed})
            else:
                raise ValueError(f"Unsupported operation: {operation.op}")
        return {"ok": True, "operations": results, "saved_to": output_path or path}
