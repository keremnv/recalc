from __future__ import annotations

from typing import Protocol

from .models import CalcOperation, Matrix, WorkbookInfo


class CalcBackend(Protocol):
    def health(self) -> dict[str, object]: ...

    def inspect_workbook(self, path: str | None = None) -> WorkbookInfo: ...

    def read_range(self, sheet: str, cell_range: str, path: str | None = None) -> dict[str, Matrix]: ...

    def write_range(
        self,
        sheet: str,
        cell_range: str,
        values: Matrix,
        path: str | None = None,
    ) -> dict[str, object]: ...

    def execute_program(
        self,
        operations: list[CalcOperation],
        path: str | None = None,
    ) -> dict[str, object]: ...
