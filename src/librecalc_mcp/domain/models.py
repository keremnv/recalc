from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

Scalar: TypeAlias = str | int | float | bool | None
Matrix: TypeAlias = list[list[Scalar]]


@dataclass(frozen=True)
class SheetInfo:
    name: str
    used_range: str | None = None


@dataclass(frozen=True)
class WorkbookInfo:
    title: str | None
    url: str | None
    sheets: list[SheetInfo]


OperationKind = Literal["write_range", "set_formula", "create_sheet"]


@dataclass(frozen=True)
class CalcOperation:
    op: OperationKind
    sheet: str | None = None
    range: str | None = None
    values: Matrix | None = None
    formula: str | None = None
    name: str | None = None
    index: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CalcOperation":
        return cls(
            op=raw["op"],
            sheet=raw.get("sheet"),
            range=raw.get("range"),
            values=raw.get("values"),
            formula=raw.get("formula"),
            name=raw.get("name"),
            index=raw.get("index"),
        )
