from __future__ import annotations

import os
from typing import Any

from librecalc_mcp.domain.models import CalcOperation, Matrix, SheetInfo, WorkbookInfo


class UnoUnavailable(RuntimeError):
    pass


class UnoCalcBackend:
    def __init__(self, host: str = "localhost", port: int = 2021) -> None:
        self.host = host
        self.port = port
        self._ctx: Any | None = None
        self._desktop: Any | None = None

    def _uno(self):
        try:
            import uno  # type: ignore
        except ImportError as exc:
            raise UnoUnavailable(
                "Python cannot import 'uno'. Use a Python environment with LibreOffice UNO bindings."
            ) from exc
        return uno

    def _connect(self) -> None:
        if self._desktop is not None:
            return
        uno = self._uno()
        local_ctx = uno.getComponentContext()
        resolver = local_ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_ctx
        )
        url = (
            f"uno:socket,host={self.host},port={self.port};"
            "urp;StarOffice.ComponentContext"
        )
        self._ctx = resolver.resolve(url)
        self._desktop = self._ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self._ctx
        )

    def health(self) -> dict[str, object]:
        try:
            self._connect()
            return {"ok": True, "backend": "uno", "host": self.host, "port": self.port}
        except Exception as exc:  # connectivity surface; report instead of crashing health
            return {
                "ok": False,
                "backend": "uno",
                "host": self.host,
                "port": self.port,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _document(self, path: str | None = None):
        self._connect()
        assert self._desktop is not None
        if path:
            uno = self._uno()
            file_url = uno.systemPathToFileUrl(os.path.abspath(os.path.expanduser(path)))
            doc = self._desktop.loadComponentFromURL(file_url, "_blank", 0, ())
        else:
            doc = self._desktop.getCurrentComponent()
        if doc is None or not doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
            raise RuntimeError("No active Calc spreadsheet document. Open one or provide path=...")
        return doc

    @staticmethod
    def _used_range(sheet: Any) -> str | None:
        cursor = sheet.createCursor()
        cursor.gotoEndOfUsedArea(True)
        address = cursor.RangeAddress
        # UNO columns/rows are zero-based; implement small A1 converter locally.
        def col_name(n: int) -> str:
            n += 1
            out = ""
            while n:
                n, rem = divmod(n - 1, 26)
                out = chr(65 + rem) + out
            return out

        return f"A1:{col_name(address.EndColumn)}{address.EndRow + 1}"

    def inspect_workbook(self, path: str | None = None) -> WorkbookInfo:
        doc = self._document(path)
        sheets = doc.Sheets
        info: list[SheetInfo] = []
        for name in sheets.ElementNames:
            sheet = sheets.getByName(name)
            info.append(SheetInfo(name=name, used_range=self._used_range(sheet)))
        title = getattr(doc, "Title", None) or None
        url = getattr(doc, "URL", None) or None
        return WorkbookInfo(title=title, url=url, sheets=info)

    def read_range(self, sheet: str, cell_range: str, path: str | None = None) -> dict[str, Matrix]:
        doc = self._document(path)
        target = doc.Sheets.getByName(sheet).getCellRangeByName(cell_range)
        values = [list(row) for row in target.getDataArray()]
        try:
            formulas = [list(row) for row in target.getFormulaArray()]
        except Exception:
            formulas = []
        return {"values": values, "formulas": formulas}

    def write_range(
        self,
        sheet: str,
        cell_range: str,
        values: Matrix,
        path: str | None = None,
    ) -> dict[str, object]:
        doc = self._document(path)
        target = doc.Sheets.getByName(sheet).getCellRangeByName(cell_range)
        target.setDataArray(tuple(tuple(row) for row in values))
        doc.calculateAll()
        return {"ok": True, "sheet": sheet, "range": cell_range, "rows": len(values)}

    def execute_program(
        self,
        operations: list[CalcOperation],
        path: str | None = None,
    ) -> dict[str, object]:
        doc = self._document(path)
        results: list[dict[str, object]] = []
        for operation in operations:
            if operation.op == "create_sheet":
                if not operation.name:
                    raise ValueError("create_sheet requires name")
                index = operation.index if operation.index is not None else doc.Sheets.Count
                doc.Sheets.insertNewByName(operation.name, index)
                results.append({"op": operation.op, "ok": True, "name": operation.name})
                continue

            if not operation.sheet or not operation.range:
                raise ValueError(f"{operation.op} requires sheet and range")
            target = doc.Sheets.getByName(operation.sheet).getCellRangeByName(operation.range)

            if operation.op == "write_range":
                if operation.values is None:
                    raise ValueError("write_range requires values")
                target.setDataArray(tuple(tuple(row) for row in operation.values))
            elif operation.op == "set_formula":
                if operation.formula is None:
                    raise ValueError("set_formula requires formula")
                # v0 deliberately restricts this op to a single-cell range.
                target.getCellByPosition(0, 0).Formula = operation.formula
            else:
                raise ValueError(f"Unsupported operation: {operation.op}")
            results.append({"op": operation.op, "ok": True})

        doc.calculateAll()
        return {"ok": True, "operations": results}
