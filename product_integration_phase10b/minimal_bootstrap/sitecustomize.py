"""Phase-10B diagnostic P2 guard. Never installs LibreCalc or changes script APIs."""
import os
import sys

_context = os.environ.get("LIBRECALC_RUN_CONTEXT")
if _context:
    try:
        with open(_context, encoding="utf-8") as _stream:
            _script = _stream.readline().strip()
        if _script and os.path.realpath(sys.argv[0]) == os.path.realpath(_script):
            pass  # The minimal target identity check completed.
    except OSError:
        pass
