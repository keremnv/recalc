"""Post-hoc, clearly-labelled diagnostic: what if the canonical member abstains?

Phase C pre-registered a deterministic, evaluator-blind canonical rule (§10) and
forbade the primary arm from falling back to independent synthesis when the
program is unavailable (§11). One group in the executed population hit exactly
that case: the canonical member's own session ABSTAINed, so P1 wrote nothing at
all for twelve members while P0 wrote eleven.

That is a real property of the arm as specified and it stays in the primary
result. This module asks a *separate* question, after the fact: is the collapse
a property of translation, or only of which member the rule happened to pick?

It answers it without a single new model call, using only sessions P0 already
paid for, and without gold: abstention is a runtime outcome, not an evaluator
signal. The rule it substitutes is still deterministic and still gold-blind --
the first member in the same canonical order whose session actually proposed a
formula. It is reported as post-hoc and never as the pre-registered arm.
"""
from __future__ import annotations

import json

import end_to_end_composition_probe as old
import program_group as pg
import program_group_probe as C
import program_group_preflight as pf
import program_group_score as S
import composition_closure as cc
import execution_unit_probe as P
parse_addr = P.parse_addr


def recovered(rec: dict) -> dict:
    """P1' formulas for one unit under the substitute canonical rule."""
    out, notes = {}, []
    for g in rec["program_groups"]:
        members = g["members"]
        canon = g["canonical_member"]
        if rec["P0_formulas"].get(canon):
            notes.append({"group": canon, "substituted": False})
            continue
        alt = next((m for m in members if rec["P0_formulas"].get(m)), None)
        if alt is None:
            notes.append({"group": canon, "substituted": False,
                          "reason": "NO_MEMBER_PROPOSED_ANYTHING"})
            continue
        src = rec["P0_formulas"][alt]
        wrote = {}
        for m in members:
            try:
                wrote[m] = pg.translate(src, parse_addr(alt), parse_addr(m))
            except Exception as e:
                notes.append({"group": canon, "member": m,
                              "TRANSLATION_FAILURE": type(e).__name__})
        out.update(wrote)
        notes.append({"group": canon, "substituted": True,
                      "original_canonical": canon,
                      "original_canonical_outcome": rec["P0_outcomes"].get(canon),
                      "substitute_canonical": alt,
                      "substitute_formula": src,
                      "members_written": len(wrote)})
    return {"formulas": out, "notes": notes}


def run() -> dict:
    units = []
    for p in sorted((C.OUT / "units").glob("*.json")):
        rec = json.loads(p.read_text())
        if not rec["program_groups"]:
            continue
        task = rec["unit"]["task"]
        gold = pf.gold_map(task)
        r = recovered(rec)
        rows = []
        for m in rec["members_in_a_group"]:
            cell = parse_addr(m)
            g = gold.get(cell)
            p1 = rec["P1_formulas"].get(m)
            px = r["formulas"].get(m, p1)
            rows.append({"member": m, "in_gold_edit_set": g is not None,
                         "gold_formula": g,
                         "P0_formula": rec["P0_formulas"].get(m),
                         "P1_formula": p1,
                         "P1prime_formula": px,
                         "P0_exact": S.S._same(rec["P0_formulas"].get(m), g),
                         "P1_exact": S.S._same(p1, g),
                         "P1prime_exact": S.S._same(px, g)})
        # Evaluator-side only, computed after the run: was the ceiling reachable?
        # If gold itself is translation-consistent across the group, then one
        # correct canonical synthesis would have produced every member. This
        # never touched runtime eligibility or member generation.
        ceiling = []
        for g in rec["program_groups"]:
            canon = g["canonical_member"]
            src = gold.get(parse_addr(canon))
            ok, checked = True, 0
            if not src:
                ok = None
            else:
                for m in g["members"]:
                    tgt = gold.get(parse_addr(m))
                    if tgt is None:
                        continue
                    checked += 1
                    try:
                        t = pg.translate(src, parse_addr(canon), parse_addr(m))
                    except Exception:
                        ok = False
                        break
                    if pg.canonical(t) != pg.canonical(tgt):
                        ok = False
                        break
            ceiling.append({"group": canon, "gold_translation_consistent": ok,
                            "members_checked": checked})
        units.append({"task": task, "seed": rec["unit"]["seed"],
                      "notes": r["notes"], "ceiling": ceiling, "members": rows})
    out = {"units": units, "model_calls_added": 0, "gold_used": False,
           "status": "POST_HOC_DIAGNOSTIC_NOT_THE_PREREGISTERED_ARM"}
    old.write(C.OUT / "phase_c_posthoc.json", out)
    return out


if __name__ == "__main__":
    o = run()
    for u in o["units"]:
        req = [m for m in u["members"] if m["in_gold_edit_set"]]
        print(json.dumps({
            "task": u["task"], "seed": u["seed"], "required": len(req),
            "P0": sum(1 for m in req if m["P0_exact"]),
            "P1": sum(1 for m in req if m["P1_exact"]),
            "P1prime": sum(1 for m in req if m["P1prime_exact"]),
            "substituted": [n for n in u["notes"] if n.get("substituted")],
            "gold_translation_consistent": [c["gold_translation_consistent"] for c in u["ceiling"]]}), flush=True)
