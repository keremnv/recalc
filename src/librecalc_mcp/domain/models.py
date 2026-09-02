from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

Scalar: TypeAlias = str | int | float | bool | None
Matrix: TypeAlias = list[list[Scalar]]
CellFormat: TypeAlias = dict[str, str | int | float | bool | None]


@dataclass(frozen=True)
class SheetInfo:
    name: str
    used_range: str | None = None


@dataclass(frozen=True)
class WorkbookInfo:
    title: str | None
    url: str | None
    sheets: list[SheetInfo]


OperationKind = Literal[
    "write_range",
    "set_formula",
    "fill_formula",
    "set_format",
    "clear_range",
    "create_sheet",
    "insert_row",
    "delete_row",
    "upsert_chart",
    "delete_chart",
]


@dataclass(frozen=True)
class CalcOperation:
    op: OperationKind
    sheet: str | None = None
    range: str | None = None
    values: Matrix | None = None
    formula: str | None = None
    cell_format: CellFormat | None = None
    name: str | None = None
    index: int | None = None
    count: int | None = None
    chart: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CalcOperation:
        cell_range = raw.get("range")
        alias = raw.get("cell_range")
        if cell_range is None:
            cell_range = alias
        elif alias is not None and alias != cell_range:
            raise ValueError("operation has conflicting range and cell_range")
        return cls(
            op=raw["op"],
            sheet=raw.get("sheet"),
            range=cell_range,
            values=raw.get("values"),
            formula=raw.get("formula"),
            cell_format=raw.get("format"),
            name=raw.get("name"),
            index=raw.get("index"),
            count=raw.get("count"),
            chart=raw.get("chart"),
        )
