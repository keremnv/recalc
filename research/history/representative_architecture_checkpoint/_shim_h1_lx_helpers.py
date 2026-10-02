"""Model-facing shim: search/periods/inspect (substrate backend, H1).

Optional: the agent may ignore this file and use ordinary Python/openpyxl.
"""
import json as _json
import os as _os
import sys as _sys
import time as _time

_ROOT = _os.environ.get("LX_REPO_ROOT", "/home/kerem/Desktop/Personal Projects/librecalc-mcp")
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from benchmark.inspection_helpers import api as _api

_ROLES = {"periods": "HELPER_PERIODS", "search": "HELPER_SEARCH",
          "inspect": "HELPER_INSPECT", "inspect_ranges": "HELPER_INSPECT"}


def _wrap(name):
    fn = getattr(_api, name)

    def call(*args, **kwargs):
        t0 = _time.perf_counter_ns()
        try:
            return fn(*args, **kwargs)
        finally:
            tel = _os.environ.get("REP_HELPER_TELEMETRY")
            if tel:
                try:
                    with open(tel, "a", encoding="utf-8") as fh:
                        fh.write(_json.dumps(
                            {"event": "helper_backend", "helper": name,
                             "consumer_role": _ROLES[name],
                             "backend": "substrate",
                             "duration_ns": _time.perf_counter_ns() - t0,
                             "python_pid": _os.getpid()}) + "\n")
                except OSError:
                    pass

    call.__name__ = name
    return call


periods = _wrap("periods")
search = _wrap("search")
inspect = _wrap("inspect")
inspect_ranges = _wrap("inspect_ranges")

__all__ = ["inspect", "inspect_ranges", "periods", "search"]
