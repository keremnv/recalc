#!/usr/bin/env python3
"""Post-hoc measurement pass: run the FROZEN verifier (v1.0.0, unmodified)
on every run's FINAL output.xlsx and (when present) pre_intervention.xlsx.

Measurement only -- no model contact, no intervention. Produces the
verifier-output ledger. Deterministic.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "research/history/phase12"))

from verification_block import verify  # noqa: E402

RUNS = PROJECT_ROOT / "research/history/phase12" / "runs"
LEDGERS = PROJECT_ROOT / "research/history/phase12" / "ledgers"
REPORTS = LEDGERS / "verifier_final_reports"


def parse(dirname: str):
    for arm in ("CONTROL", "TREATMENT", "SHAM"):
        if dirname.endswith("_" + arm):
            stem = dirname[: -len(arm) - 1]
            for cat in ("Template", "Debugging", "Financial_Model"):
                if stem.startswith(cat + "_"):
                    return cat, stem[len(cat) + 1:], arm
    raise RuntimeError(f"unparseable: {dirname}")


def main() -> None:
    pops = sys.argv[1:] or ["popA", "popB", "pilot", "pilot_ext"]
    LEDGERS.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(LEDGERS / "verifier_output.jsonl", "w") as fp:
        for pop in pops:
            for d in sorted((RUNS / pop).glob("*")):
                if not d.is_dir():
                    continue
                cat, tid, arm = parse(d.name)
                task = f"{cat}:{tid}"
                rec_p = d / "run_record.json"
                rec = json.loads(rec_p.read_text()) if rec_p.exists() else {}
                sheet_in = d / "input.xlsx"
                for label, fname in (("final", "output.xlsx"),
                                     ("pre", "pre_intervention.xlsx")):
                    cand = d / fname
                    if not cand.exists() or not sheet_in.exists():
                        continue
                    t0 = time.monotonic()
                    try:
                        rep = verify(sheet_in, cand)
                    except Exception as exc:  # never expected; record it
                        rep = {"positive": None, "status": "MEASURE_ERROR",
                               "reason": f"{type(exc).__name__}: {exc}"}
                    wall = time.monotonic() - t0
                    sig = rep.get("signals", {}) if isinstance(rep, dict) else {}
                    row = {
                        "pop": pop, "task_id": task, "arm": arm,
                        "which": label, "run_status": rec.get("status"),
                        "positive": rep.get("positive"),
                        "status": rep.get("status"),
                        "families": rep.get("positive_families"),
                        "n_err": (sig.get("ERR") or {}).get("count"),
                        "n_unif": (sig.get("UNIF") or {}).get("count"),
                        "n_ref": (sig.get("REF") or {}).get("count"),
                        "chg_cells": (sig.get("CHG") or {}).get("changed_cells"),
                        "verifier_wall_s": round(wall, 3),
                    }
                    fp.write(json.dumps(row) + "\n")
                    rp = REPORTS / pop / d.name
                    rp.mkdir(parents=True, exist_ok=True)
                    (rp / f"{label}.json").write_text(
                        json.dumps(rep, indent=1, default=str))
                    n += 1
    print(f"wrote {n} verifier-output rows")


if __name__ == "__main__":
    main()
