"""Model-facing shim for Stage-B inspection helpers (dropped in C1 workdirs).

Optional: the agent may ignore this file and use ordinary Python/openpyxl.
Usage:
    import lx_helpers
    lx_helpers.periods("input.xlsx")
    lx_helpers.search("input.xlsx", "revenue")
    lx_helpers.inspect("input.xlsx", "Sheet1", "A1:Z50")
    lx_helpers.inspect_ranges("input.xlsx", [
        {"sheet": "Sheet1", "range": "A1:C10"},
        {"sheet": "Sheet2", "range": "B4:F8"},
    ])
"""
import os
import sys

_ROOT = os.environ.get("LX_REPO_ROOT", "/home/kerem/Desktop/Personal Projects/librecalc-mcp")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmark.inspection_helpers.api import inspect, inspect_ranges, periods, search  # noqa: E402

__all__ = ["periods", "search", "inspect", "inspect_ranges"]
