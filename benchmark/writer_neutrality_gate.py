#!/usr/bin/env python3
"""Blocking gate: a zero-write round trip must score regression = 1.0.

Runs the writer with no edits over the frozen population, then scores the results
with the normal benchmark path. Until this passes, no benchmark delta measured
through the writer is interpretable, so the replication must not spend model
calls. Nothing here calls a model.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
from xlsx_cell_writer import write_cells

OUT = old.MECHANICAL / "writer-neutrality-gate"


def main() -> int:
    tasks = [r["task"] for r in old.load(old.OUT / "end_to_end_population.json")["rows"]]
    run_root = OUT / "scoring"
    for task in tasks:
        result = write_cells(old.synth_tools._input_path(task), run_root / f"Financial_Model-{task}" / "output.xlsx", [])
        assert result["byte_identical_to_source"], task
    print(f"NULL_WRITE workbooks={len(tasks)} all byte-identical to source", flush=True)
    subprocess.run([sys.executable, str(old.ROOT / "benchmark/score_openrouter_run.py"), str(run_root),
                    "--model-name", "writer-neutrality-gate", "--metadata-tolerant"],
                   cwd=old.ROOT / "benchmark-data/SpreadsheetBench-2/evaluation", check=False)
    scores = old.load(run_root / "official_scores.json")
    rows = [{"task": k.split(":", 1)[1], "regression_accuracy": v.get("regression_accuracy"),
             "modification_accuracy": v.get("modification_accuracy"), "error_message": v.get("error_message")}
            for k, v in sorted(scores["tasks"].items())]
    failures = [r for r in rows if r["regression_accuracy"] != 1.0]
    payload = {"gate": "ZERO_WRITE_REGRESSION_EQUALS_ONE", "tasks": len(rows),
               "passing": len(rows) - len(failures), "failures": failures, "rows": rows,
               "pass": not failures}
    old.write(OUT / "gate.json", payload)
    print(json.dumps({k: payload[k] for k in ("gate", "tasks", "passing", "pass")}, indent=2))
    for f in failures:
        print(f"  FAIL {f['task']} regression={f['regression_accuracy']} {str(f['error_message'])[:90]}")
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
