from __future__ import annotations

import os
from dataclasses import asdict
from functools import lru_cache
from typing import Any

from mcp.server import MCPServer

from librecalc_mcp.backend.uno import UnoCalcBackend
from librecalc_mcp.domain.models import CalcOperation

mcp = MCPServer("librecalc-mcp")


@lru_cache(maxsize=1)
def backend() -> UnoCalcBackend:
    return UnoCalcBackend(
        host=os.environ.get("LIBRECALC_HOST", "localhost"),
        port=int(os.environ.get("LIBRECALC_PORT", "2021")),
    )


@mcp.tool()
def calc_health() -> dict[str, object]:
    """Check whether the LibreOffice Calc runtime is reachable over UNO."""
    return backend().health()


@mcp.tool()
def workbook_inspect(path: str | None = None) -> dict[str, Any]:
    """Inspect a Calc workbook: title, URL, sheets, and each sheet's used range."""
    return asdict(backend().inspect_workbook(path))


@mcp.tool()
def range_read(sheet: str, cell_range: str, path: str | None = None) -> dict[str, Any]:
    """Read values and formulas from an A1-style Calc range, e.g. Sheet1 + A1:D20."""
    return backend().read_range(sheet, cell_range, path)


@mcp.tool()
def range_write(
    sheet: str,
    cell_range: str,
    values: list[list[str | int | float | bool | None]],
    path: str | None = None,
    output_path: str | None = None,
) -> dict[str, object]:
    """Write a rectangular value matrix, recalculate, and persist the workbook.

    When path is provided, the source is updated in place unless output_path names a copy.
    Without path, the active Calc document is used and is saved only when output_path is provided.
    """
    return backend().write_range(sheet, cell_range, values, path, output_path)


@mcp.tool()
def program_execute(
    operations: list[dict[str, Any]],
    path: str | None = None,
    output_path: str | None = None,
) -> dict[str, object]:
    """Execute many deterministic Calc operations in one call.

    v0 operation forms:
    - {"op":"create_sheet", "name":"Analysis", "index":2}
    - {"op":"write_range", "sheet":"Analysis", "range":"A1:B2", "values":[[...],[...]]}
    - {"op":"set_formula", "sheet":"Analysis", "range":"C2", "formula":"=SUM(A2:B2)"}
    - {"op":"fill_formula", "sheet":"Analysis", "range":"C2:G2", "formula":"=SUM(A2:B2)"}
    - {"op":"clear_range", "sheet":"Analysis", "range":"C2:G2"}
    - {"op":"insert_row", "sheet":"Analysis", "index":5, "count":1}
    - {"op":"delete_row", "sheet":"Analysis", "index":8, "count":1}
    - {"op":"upsert_chart", "chart":{...ChartSpec fields...}}
    - {"op":"delete_chart", "name":"chart_id"}

    insert_row / delete_row use 1-based row numbers (index is the first affected row; count defaults
    to 1). insert_row inserts before that row. This is geometry, not a task-specific restore.

    This is intentionally not arbitrary Python execution. It is the seed of the generated-program layer.

    When path is provided, the source is updated in place unless output_path names a copy.
    Without path, the active Calc document is used and is saved only when output_path is provided.
    """
    program = [CalcOperation.from_dict(operation) for operation in operations]
    return backend().execute_program(program, path, output_path)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
