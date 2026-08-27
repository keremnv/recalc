"""Optional write guards. Measuring instruments, not product defaults."""

from __future__ import annotations

import os


def preserve_populated() -> bool:
    """Skip writes onto cells that already hold a value or formula.

    Enabled only when LIBRECALC_PRESERVE_POPULATED=1. Template/FM target-safety
    arm; Debugging measurements must not set this.
    """

    return os.environ.get("LIBRECALC_PRESERVE_POPULATED") == "1"
