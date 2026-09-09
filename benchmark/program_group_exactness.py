"""How much of each arm's scorer credit is exact, and how much is tolerance.

The evaluator compares population S by value with a 1% relative tolerance and a
"not meaningful" equivalence class. That is the official semantics and section 8
of the report uses it unchanged. This module adds one diagnostic on top, because
a delta built out of near misses and a delta built out of exact answers are not
the same claim: for every scorer cell one arm wins and the other loses, it asks
whether the winner reproduced the gold value exactly or merely landed inside the
tolerance band.

It is a reporting refinement, never a rescoring: no cell is credited here that
the evaluator did not credit, and the official numbers are not adjusted.
"""
from __future__ import annotations

import json

import end_to_end_composition_probe as old
import execution_unit_score as S
import program_group_probe as C

TOLERANCE = 0.01


def _rel(gold, got):
    try:
        g, v = float(gold), float(got)
    except (TypeError, ValueError):
        return None
    if g == 0:
        return None
    return abs(g - v) / abs(g)


def classify(detail: dict, cells: list[str]) -> dict:
    exact, band, other = [], [], []
    for a in cells:
        x = detail.get(a) or {}
        e = _rel(x.get("gold"), x.get("got"))
        if e == 0:
            exact.append(a)
        elif e is not None and e <= TOLERANCE:
            band.append(a)
        else:
            other.append(a)
    return {"exact": exact, "within_tolerance_not_exact": band,
            "not_numeric_or_outside": other}


def run() -> dict:
    scores = json.loads((C.OUT / "phase_c_scores.json").read_text())
    units = []
    for r in scores["units"]:
        if not (r["P1_newly_correct_vs_P0"] or r["P1_lost_vs_P0"]):
            continue
        task, d = r["task"], r["seed"].replace("!", "_").replace(" ", "_")
        p = C.OUT / "variants" / task
        _, d0 = S.correct_S(task, p / f"{d}__P0" / f"{task}_output.xlsx")
        _, d1 = S.correct_S(task, p / f"{d}__P1" / f"{task}_output.xlsx")
        units.append({"task": task, "seed": r["seed"],
                      "P1_gains": classify(d1, r["P1_newly_correct_vs_P0"]),
                      "P1_losses": classify(d0, r["P1_lost_vs_P0"])})
    out = {"tolerance": TOLERANCE, "units": units,
           "status": "DIAGNOSTIC_ONLY_OFFICIAL_SCORES_UNCHANGED"}
    old.write(C.OUT / "phase_c_exactness.json", out)
    return out


if __name__ == "__main__":
    o = run()
    for u in o["units"]:
        print(json.dumps({
            "task": u["task"], "seed": u["seed"],
            "gains_exact": len(u["P1_gains"]["exact"]),
            "gains_tolerance": len(u["P1_gains"]["within_tolerance_not_exact"]),
            "losses_exact": len(u["P1_losses"]["exact"]),
            "losses_tolerance": len(u["P1_losses"]["within_tolerance_not_exact"])}), flush=True)
