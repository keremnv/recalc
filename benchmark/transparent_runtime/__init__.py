"""H1 transparent workbook-transaction runtime.

Wraps ordinary agent Python/openpyxl mutations without changing agent code:

  canonical pre-state -> run Python unchanged -> capture effects ->
  derive WorkbookDelta -> mechanical validation -> commit -> provenance.

The model-facing surface is byte-identical to H0 (``bash``, ``view_xlsx``,
``submit``). This package adds no model info, helpers, prompts, intent/target
inference, edit expansion/reorder, auto translation, dependency closure,
semantic verifiers, compiled-read acceleration, or inspection changes.
"""

from benchmark.transparent_runtime.delta import WorkbookDelta
from benchmark.transparent_runtime.telemetry import MutationTelemetry
from benchmark.transparent_runtime.transaction import (
    MODEL_SURFACE,
    WorkbookTransaction,
    run_transaction,
)
from benchmark.transparent_runtime.validate import ValidationReport, validate_mechanical

__all__ = [
    "MODEL_SURFACE",
    "MutationTelemetry",
    "ValidationReport",
    "WorkbookDelta",
    "WorkbookTransaction",
    "run_transaction",
    "validate_mechanical",
]
