"""Model-facing shim for the batch-write A/B (dropped in C1 workdirs as lx_helpers.py).

C1 = earned C0 surface (periods/search/inspect) + optional write_cells/write_formulas.
Optional: the agent may ignore this file and use ordinary Python/openpyxl.
Usage:
    import lx_helpers
    lx_helpers.write_cells({"Sheet1!B4": 10}, workbook="output.xlsx")
    lx_helpers.write_formulas({"DCF!G20": "=G17*G19"}, workbook="output.xlsx")
"""
import os
import sys

_ROOT = os.environ.get("LX_REPO_ROOT", "/home/kerem/Desktop/Personal Projects/librecalc-mcp")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmark.inspection_helpers.api import inspect, inspect_ranges, periods, search  # noqa: E402
from benchmark.mutation_helpers.batch import write_cells, write_formulas  # noqa: E402

__all__ = ["periods", "search", "inspect", "inspect_ranges", "write_cells", "write_formulas"]
