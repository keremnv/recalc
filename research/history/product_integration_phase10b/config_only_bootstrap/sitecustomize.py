"""Supplemental attribution: guarded startup plus production config only."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _start(context_path: Path) -> None:
    time.perf_counter_ns()
    lines = context_path.read_text().splitlines()
    if len(lines) != 4:
        raise ValueError("invalid observer context")
    script = Path(lines[0]).resolve()
    if Path(sys.argv[0]).resolve() != script:
        return
    from librecalc_agent.config import Config, load as load_config
    effective = os.environ.get("LIBRECALC_EFFECTIVE_CONFIG")
    if effective:
        config, issues = Config(**json.loads(effective)), []
    else:
        config, issues = load_config(os.environ.get("LIBRECALC_CONFIG"),
                                    os.environ.get("LIBRECALC_NO_RUNTIME") == "1")
    _ = config.reads, issues


_context = os.environ.get("LIBRECALC_RUN_CONTEXT")
if _context:
    try:
        _start(Path(_context))
    except Exception:
        pass
