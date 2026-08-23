from __future__ import annotations

from copy import deepcopy

from librecalc_mcp.domain.models import CalcOperation, Matrix, SheetInfo, WorkbookInfo


class MemoryCalcBackend:
    """Tiny backend for MCP/domain tests. Not a spreadsheet engine."""

    def __init__(self) -> None:
        self.sheets: dict[str, dict[str, Matrix]] = {"Sheet1": {}}
        self.formulas: dict[str, dict[str, str]] = {"Sheet1": {}}

    def health(self) -> dict[str, object]:
        return {"ok": True, "backend": "memory"}

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
        return {"values": values, "formulas": formulas}

    def write_range(
        self,
        sheet: str,
        cell_range: str,
        values: Matrix,
        path: str | None = None,
    ) -> dict[str, object]:
        self.sheets.setdefault(sheet, {})[cell_range] = deepcopy(values)
        return {"ok": True, "sheet": sheet, "range": cell_range, "rows": len(values)}

    def execute_program(
        self,
        operations: list[CalcOperation],
        path: str | None = None,
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for operation in operations:
            if operation.op == "create_sheet":
                assert operation.name
                self.sheets.setdefault(operation.name, {})
                self.formulas.setdefault(operation.name, {})
                results.append({"op": operation.op, "ok": True, "name": operation.name})
            elif operation.op == "write_range":
                assert operation.sheet and operation.range and operation.values is not None
                results.append(
                    {"op": operation.op, **self.write_range(operation.sheet, operation.range, operation.values)}
                )
            elif operation.op == "set_formula":
                assert operation.sheet and operation.range and operation.formula is not None
                self.formulas.setdefault(operation.sheet, {})[operation.range] = operation.formula
                results.append({"op": operation.op, "ok": True})
            else:
                raise ValueError(f"Unsupported operation: {operation.op}")
        return {"ok": True, "operations": results}
