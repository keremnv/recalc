from __future__ import annotations

from typing import Protocol

from .models import CalcOperation, CellFormat, Matrix, WorkbookInfo


class CalcBackend(Protocol):
    def health(self) -> dict[str, object]: ...

    def inspect_workbook(self, path: str | None = None) -> WorkbookInfo: ...

    def inspect_charts(self, path: str | None = None) -> list[dict[str, object]]: ...

    def read_range(
        self, sheet: str, cell_range: str, path: str | None = None
    ) -> dict[str, Matrix]: ...

    def read_ranges(
        self,
        ranges: list[tuple[str, str]],
        path: str | None = None,
        *,
        include_errors: bool = True,
    ) -> list[dict[str, Matrix]]: ...

    def read_formats(
        self,
        cells: list[tuple[str, str]],
        path: str | None = None,
    ) -> list[CellFormat]: ...

    def write_range(
        self,
        sheet: str,
        cell_range: str,
        values: Matrix,
        path: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, object]: ...

    def execute_program(
        self,
        operations: list[CalcOperation],
        path: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, object]: ...
