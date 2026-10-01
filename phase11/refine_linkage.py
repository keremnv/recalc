#!/usr/bin/env python3
"""Precision-guard linkage/discrimination recompute.

Overlap between a finding set and eval miss cells only counts when the
finding set is small enough to be actionable (<=50 cells). Huge sets
(all precedents, all formulas) fall back to GENERIC/UNRELATED.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase11"))
from mine import miss_cells  # noqa: E402

CAP = 50


def main() -> None:
    p = ROOT / "phase11" / "DERIVATION_REACHABILITY_MATRIX.jsonl"
    rows = [json.loads(l) for l in open(p)]
    for r in rows:
        cells = set(r.get("finding_cells") or [])
        # finding_cells truncated at 50 in matrix; use count for size
        n = r.get("finding_count", 0)
        misses = miss_cells(r.get("eval_error"))
        exact = r.get("official_exact")
        reached = r.get("reachability") or 0
        disc = "NO_DISCRIMINATION"
        if n:
            if misses and cells and (cells & misses) and n <= CAP:
                disc = "UNIQUE_DISCRIMINATOR" if cells == misses else "REDUCES_CANDIDATE_SET"
            else:
                disc = "GENERIC_WARNING_ONLY"
        r["discrimination"] = disc
        if exact == 1:
            r["failure_linkage"] = "UNRELATED"
        elif exact in (0, 0.0):
            if misses and cells and (cells & misses) and n <= CAP and reached < 4:
                r["failure_linkage"] = "DIRECTLY_LINKED"
            elif n and reached < 4 and r["candidate"] in (
                    "ERR-NEW-ERROR-DELTA", "UNIF-FAMILY-BREAK",
                    "REF-BLANK-DELTA", "CHG-STRUCT-DIFF",
                    "TEMP-PERIOD-MAP", "ROLE-EQUIV-SET"):
                # finding exists, agent missed it, run failed: plausibly linked
                r["failure_linkage"] = "PLAUSIBLY_LINKED"
            elif r["candidate"] in ("DEP-DIRECT-REFS", "FAM-REL-FAMILY",
                                    "CTRL-FORMULA-LIST"):
                # sets too broad to link without overlap evidence
                r["failure_linkage"] = "UNRELATED" if not (misses & cells) else r["failure_linkage"]
                if r["failure_linkage"] == "DIRECTLY_LINKED" and n > CAP:
                    r["failure_linkage"] = "UNRELATED"
            else:
                r["failure_linkage"] = "UNRELATED"
        else:
            r["failure_linkage"] = "UNKNOWN"
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    print("refined", len(rows))


if __name__ == "__main__":
    main()
