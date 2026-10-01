"""Run frozen mechanical capture only after the external observer sees change."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from librecalc_agent._frozen import capture


def main() -> int:
    workdir, run_dir = map(Path, sys.argv[1:3])
    pre: dict[str, bytes] = {}
    for line in (run_dir / "pre_index.tsv").read_text().splitlines():
        name, rel = line.split("\t", 1)
        pre[rel] = (run_dir / "pre" / name).read_bytes()
    t = time.perf_counter_ns()
    rows, sections = capture.capture_wrap_timed(workdir, pre, run_dir.name, "PHASE6", 1)
    profile = {"capture_total_ns": time.perf_counter_ns() - t, "sections_s": sections,
               "records": len(rows), "failures": sum(bool(x.get("runtime_failure")) for x in rows)}
    (run_dir / "capture.json").write_text(json.dumps(rows, sort_keys=True, default=str) + "\n")
    (run_dir / "capture_profile.json").write_text(json.dumps(profile, sort_keys=True, default=str) + "\n")
    return 0 if profile["failures"] == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
