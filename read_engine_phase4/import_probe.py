"""Diagnostic-only fresh-interpreter import probes; not a workload endpoint."""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
from pathlib import Path

from read_engine_phase4.benchmark import HERE, VENV, verify


def main() -> None:
    verify()
    if (HERE / "import_diagnostics.json").exists():
        raise RuntimeError("Import diagnostics already exist")
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "READ_ENGINE_PHASE3_CONTEXT"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cases = {
        "bare_python": [str(VENV), "-c", "pass"],
        "h0_parent_imports": [str(VENV), str(HERE.parent / "read_engine_phase3/harness.py"), "--help"],
        "h1_warm_parent_imports": [str(VENV), str(HERE / "harness.py"), "--help"],
        "h1_cold_builder_stack": [str(VENV), "-c", "from read_engine_phase4 import parent_artifact; from read_engine_phase3 import safe_artifact"],
        "h1_warm_module_presence": [str(VENV), "-c", "import sys; from read_engine_phase4 import parent_artifact; print({x:(x in sys.modules) for x in ('prototype','lxml','openpyxl')})"],
    }
    rows = {}
    for name, argv in cases.items():
        times = []
        last_stdout = ""
        for _ in range(15):
            t = time.perf_counter_ns()
            proc = subprocess.run(argv, env=env, capture_output=True, text=True)
            times.append((time.perf_counter_ns() - t) / 1e6)
            if proc.returncode:
                raise RuntimeError(f"Import probe {name} failed: {proc.stderr[-500:]}")
            last_stdout = proc.stdout.strip()
        rows[name] = {"median_ms": statistics.median(times), "range_ms": [min(times), max(times)],
                      "observations_ms": times, "stdout_last": last_stdout if name == "h1_warm_module_presence" else None}
    (HERE / "import_diagnostics.json").write_text(json.dumps({"diagnostic_only": True,
        "fresh_process_each_observation": True, "os_cache": "uncontrolled", "cases": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
