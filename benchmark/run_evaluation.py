"""Run the vendored SpreadsheetBench-2 evaluator with metadata repair installed.

The evaluator is invoked as a subprocess (score_openrouter_run.py:76), so an in-process
patch of openpyxl cannot reach it. This wrapper installs the repair, then runs
evaluation.py as __main__ with argv forwarded, leaving the vendored file untouched.

Without it, Financial_Model 06_01..06_05 raise ParseError before any cell is compared and
the category cannot be scored. See xlsx_metadata_repair for what is malformed and why.
The evaluator code and grids are unchanged, but this is a metadata-tolerant local runtime,
not an execution of the benchmark's distributed evaluator environment byte-for-byte.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "benchmark-data/SpreadsheetBench-2/evaluation/evaluation.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(EVALUATION.parent))

from xlsx_metadata_repair import install

if __name__ == "__main__":
    install()
    sys.argv = [str(EVALUATION), *sys.argv[1:]]
    runpy.run_path(str(EVALUATION), run_name="__main__")
