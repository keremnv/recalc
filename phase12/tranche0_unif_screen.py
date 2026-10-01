#!/usr/bin/env python3
"""Tranche 0b: UNIF precision-gate screen (§38).

Runs the frozen verifier over all 59 Phase-11 matched pairs offline and
reports UNIF positive rate, surviving-set sizes, and benign structure,
 WITHOUT gold. Decision rule (preregistered here): UNIF stays in the live
bundle iff surviving-break runs are a minority (<50%) with small sets
(median <=5); else UNIF is dropped pre-live and the bundle proceeds as
ERR/REF/CHG.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase12"))
sys.path.insert(0, str(ROOT / "phase11"))

from mine import index_reps  # noqa: E402
from verification_block import verify  # noqa: E402


def main() -> None:
    reps = [r for r in index_reps() if r["input"] and r["output"]]
    print(f"pairs: {len(reps)}")
    rows = []
    for i, r in enumerate(reps):
        rep = verify(r["input"], r["output"])
        u = rep["signals"].get("UNIF", {}).get("count", -1) if rep["status"] == "OK" else -1
        rows.append({"rep": r["rep"], "status": rep["status"],
                     "unif": u, "families": rep["positive_families"]})
        if (i + 1) % 15 == 0:
            print(f"  {i + 1}/{len(reps)}")
    ok = [r for r in rows if r["status"] == "OK"]
    pos = [r for r in ok if r["unif"] > 0]
    sizes = sorted(r["unif"] for r in pos)
    med = sizes[len(sizes) // 2] if sizes else 0
    print(f"ok: {len(ok)}, UNIF-positive runs: {len(pos)} "
          f"({len(pos) / max(len(ok), 1):.0%}), median set: {med}")
    print(f"max set: {max(sizes) if sizes else 0}")
    for r in pos:
        print(f"  {r['unif']:3d} {r['rep'].split('/')[-1]}")
    with open(ROOT / "phase12" / "TRANCHE0_UNIF_SCREEN.json", "w") as f:
        json.dump(rows, f, indent=1)
    keep = (len(pos) / max(len(ok), 1)) < 0.50 and med <= 5
    print("GATE:", "KEEP UNIF" if keep else "DROP UNIF pre-live")


if __name__ == "__main__":
    main()
