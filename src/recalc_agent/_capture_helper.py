"""Capture mechanical XLSX effects after the external observer detects change."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from recalc_agent._frozen import capture


def main() -> int:
    workdir, run_dir = map(Path, sys.argv[1:3])
    pre: dict[str, bytes] = {}
    for line in (run_dir / "pre_index.tsv").read_text().splitlines():
        name, rel = line.split("\t", 1)
        pre[rel] = (run_dir / "pre" / name).read_bytes()
    rows, _ = capture.capture_wrap_timed(workdir, pre, run_dir.name, "PRODUCT", 1)
    state = {"records": len(rows), "failures": sum(bool(x.get("runtime_failure")) for x in rows),
             "validation_passed": all(x.get("validation_passed") is True for x in rows)}
    (run_dir / "capture.json").write_text(json.dumps(rows, sort_keys=True, default=str) + "\n")
    (run_dir / "capture_state.json").write_text(json.dumps(state, sort_keys=True) + "\n")
    return 0 if state["failures"] == 0 and state["validation_passed"] else 3


if __name__ == "__main__":
    sys.exit(main())
