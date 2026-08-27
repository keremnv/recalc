"""Benchmark wrapper around the domain enumerator.

Adds instruction-named sheets for the offline census. The inspect payload lives in
librecalc_mcp.domain.boundary_continuations and does not see the instruction.
"""

from __future__ import annotations

from typing import Any

from benchmark.blank_ranking import instruction_sheet_names
from librecalc_mcp.domain.boundary_continuations import (
    ARMS,
    BoundaryContinuation,
    payload_from_xlsx,
    select_arm,
)
from librecalc_mcp.domain.boundary_continuations import (
    enumerate_boundary_continuations as _enumerate,
)

__all__ = [
    "ARMS",
    "BoundaryContinuation",
    "enumerate_boundary_continuations",
    "payload_from_xlsx",
    "select_arm",
]


def enumerate_boundary_continuations(
    raw_workbook: Any,
    value_workbook: Any,
    *,
    instruction: str,
    minimum_run: int = 3,
) -> list[BoundaryContinuation]:
    named = instruction_sheet_names(
        instruction, [sheet.title for sheet in raw_workbook.worksheets]
    )
    return _enumerate(
        raw_workbook,
        value_workbook,
        named_sheets=named,
        minimum_run=minimum_run,
    )
