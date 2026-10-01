"""Only activated by the Phase-3 parent for the exact child script."""
import json
import os
import time

_started = time.perf_counter_ns()
_context = os.environ.get("READ_ENGINE_PHASE3_CONTEXT")
if _context:
    try:
        from read_engine_phase3.runtime import install
        install(json.loads(_context), _started)
    except Exception as exc:
        # A failed optional bootstrap leaves normal openpyxl available; parent
        # sees missing runtime evidence and fails the semantic/timing gate.
        try:
            context = json.loads(_context)
            with open(context["events"], "a", encoding="utf-8") as out:
                out.write(json.dumps({"event": "bootstrap_failure", "exception_class": type(exc).__name__,
                                      "message": str(exc)[:300]}) + "\n")
        except Exception:
            pass
