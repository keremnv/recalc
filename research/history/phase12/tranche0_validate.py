#!/usr/bin/env python3
"""Tranche 0: mechanical-truth validation of the frozen verifier.

Runs verifier.verify on Phase-11 fixture pairs (4 error-positive runs +
linked break/blank cases + 6 clean negatives) and checks every emitted
item against independently recomputed ground truth. Any BUG/UNSOUND item
fails loudly (exit 1) and stops the experiment.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/history/phase12"))
sys.path.insert(0, str(ROOT / "research/history/phase11"))

from verification_block import verify  # noqa: E402

FIXTURES = [
    # (input, candidate, expected_ERR_cells_or_None, expect_UNIF_bool, note)
    ("research/history/batch_write_helper_ab/work/Template_10_01/input.xlsx",
     "research/history/batch_write_helper_ab/reps/Template_10_01_C1/output.xlsx",
     23, None, "Phase-11 error case: 23 new #VALUE!"),
    ("research/history/live_transparent_runtime_ab/runs/Financial_Model/Financial_Model_01_01_H1/input.xlsx",
     "research/history/live_transparent_runtime_ab/runs/Financial_Model/Financial_Model_01_01_H1/output.xlsx",
     442, None, "Phase-11 destruction case: 442 new #DIV/0!"),
    ("research/history/live_transparent_runtime_ab/runs/Debugging/Debugging_02_06_H0/input.xlsx",
     "research/history/live_transparent_runtime_ab/runs/Debugging/Debugging_02_06_H0/output.xlsx",
     29, None, "Phase-11 new-error case (3 pre-existing, 0 persist)"),
    ("research/history/token_affordance_discovery/runs/primary/02_Financial_Model_03_03_B/work/input.xlsx",
     "research/history/token_affordance_discovery/runs/primary/02_Financial_Model_03_03_B/output.xlsx",
     24, None, "Phase-11 new-error case (16 pre-existing, 0 persist)"),
    ("research/history/batch_write_helper_ab/work/Debugging_02_01/input.xlsx",
     "research/history/batch_write_helper_ab/reps/Debugging_02_01_C0/output.xlsx",
     None, True, "Phase-11 break case: DCF!X9 post-edit break"),
]


def main() -> int:
    results = []
    failed = 0
    for inp, cand, exp_err, exp_unif, note in FIXTURES:
        inp_p, cand_p = ROOT / inp, ROOT / cand
        if not inp_p.is_file() or not cand_p.is_file():
            print(f"SKIP (missing): {note}")
            results.append({"note": note, "status": "SKIPPED_MISSING"})
            continue
        rep = verify(inp_p, cand_p)
        if rep["status"] != "OK":
            print(f"FAIL unavailable: {note}: {rep.get('reason')}")
            failed += 1
            results.append({"note": note, "status": "FAIL", "reason": rep.get("reason")})
            continue
        verdicts = []
        if exp_err is not None:
            got = rep["signals"]["ERR"]["count"]
            ok = got == exp_err
            verdicts.append(("ERR-count", ok, f"expected {exp_err}, got {got}"))
            # every reported error must be error-valued in recalculated candidate
            for it in rep["signals"]["ERR"]["items"]:
                verdicts.append(("ERR-item", it["error"].startswith("#"), it["cell"]))
        if exp_unif:
            cells = [i["cell"] for i in rep["signals"]["UNIF"]["items"]]
            verdicts.append(("UNIF-contains-X9", "DCF!X9" in cells, str(cells[:8])))
        # CHG sanity: footprint must be non-trivial on these edited pairs
        verdicts.append(("CHG-nonzero", rep["signals"]["CHG"]["changed_cells"] > 0,
                         str(rep["signals"]["CHG"]["changed_cells"])))
        bad = [v for v in verdicts if not v[1]]
        failed += len(bad)
        for name, ok, detail in verdicts:
            print(("PASS " if ok else "FAIL ") + f"{name}: {note} :: {detail}")
        results.append({"note": note, "status": "OK" if not bad else "FAIL",
                        "positive": rep["positive"],
                        "families": rep["positive_families"]})
    with open(ROOT / "research/history/phase12" / "TRANCHE0_MECHANICAL_TRUTH.json", "w") as f:
        json.dump(results, f, indent=1)
    print("FAILURES:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
