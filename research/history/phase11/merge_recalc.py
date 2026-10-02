#!/usr/bin/env python3
"""Merge RECALC_ERROR_DELTA findings into ERR matrix rows.

Recomputes finding_cells, failure_linkage, and discrimination for
ERR-NEW-ERROR-DELTA rows from LibreOffice-recalculated deltas (the matrix
proper carries cached-value deltas, which are empty for openpyxl-written
outputs). All other rows untouched.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/history/phase11"))
from mine import discrimination, failure_linkage, miss_cells  # noqa: E402


def main() -> None:
    recalc = {r["rep"]: r for r in
              (json.loads(l) for l in open(ROOT / "research/history/phase11" / "RECALC_ERROR_DELTA.jsonl"))}
    rows = [json.loads(l) for l in open(ROOT / "research/history/phase11" / "DERIVATION_REACHABILITY_MATRIX.jsonl")]
    n = 0
    for r in rows:
        if r["candidate"] != "ERR-NEW-ERROR-DELTA":
            continue
        d = recalc.get(r["rep"])
        if not d or not d["ok"]:
            r["recalc_ok"] = False
            continue
        r["recalc_ok"] = True
        cells = set(d["new"])
        r["finding_count"] = len(cells)
        r["finding_cells"] = sorted(cells)[:50]
        score = {"official_exact": r.get("official_exact"),
                 "eval_error": r.get("eval_error")}
        r["failure_linkage"] = failure_linkage("ERR-NEW-ERROR-DELTA", cells, score, r["reachability"])
        r["discrimination"] = discrimination(cells, score)
        n += 1
    with open(ROOT / "research/history/phase11" / "DERIVATION_REACHABILITY_MATRIX.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    print(f"merged recalc into {n} ERR rows")


if __name__ == "__main__":
    main()
