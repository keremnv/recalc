#!/usr/bin/env python3
"""§5 preflight: the representability ceiling of synthesize-once + translate.

Two questions, both answered without a single model call.

  survey   Over each task's full Edit-Plan-authorised set, how much of it forms
           mechanically eligible ProgramGroups at all? This sizes the population
           and answers "how often do members share one program" without any
           selection toward eligibility.

  ceiling  For each eligible group, if the *correct* program were synthesized
           once at the frozen canonical position, would deterministic
           translation reproduce the other gold member formulas? Gold is read
           here and only here, evaluator-side, after eligibility is already
           decided. It never touches runtime grouping or canonical selection.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import execution_unit_score as S
import program_group as pg

OUT = old.MECHANICAL / "program-group-probe"
TASKS = ["08_03", "08_04", "08_05", "09_05", "15_04", "17_03"]
QUARANTINED = ["07_03", "14_05"]


def addr(c):
    return f"{c[0]}!{cc.a1(c[1], c[2])}"


def gold_map(task: str) -> dict:
    return {(e["sheet"], e["row"], e["col"]): e["golden_payload"] for e in cc.population_E(task)}


def ceiling_for(task: str, group: dict, gold: dict) -> dict:
    """Could one correct program, translated, reproduce the gold members?"""
    canon = tuple(group["canonical_cell"])
    cells = [tuple(c) for c in group["member_cells"]]
    in_gold = [c for c in cells if c in gold]
    row = {"members": group["members"], "canonical_member": group["canonical_member"],
           "n_members": len(cells), "n_members_in_gold_edit_set": len(in_gold)}
    if canon not in gold:
        row["status"] = "CANONICAL_NOT_IN_GOLD_EDIT_SET"
        return row
    src = gold[canon]
    exact = fp = 0
    detail = {}
    for c in cells:
        if c not in gold:
            detail[addr(c)] = {"gold": None, "translated": None, "verdict": "NOT_A_GOLD_EDIT"}
            continue
        try:
            t = pg.translate(src, canon, c)
        except Exception as exc:
            detail[addr(c)] = {"verdict": f"TRANSLATION_FAILURE: {type(exc).__name__}"}
            continue
        e = S._same(t, gold[c])
        f = pg.formula_a1_shape(t) == pg.formula_a1_shape(gold[c])
        exact += bool(e)
        fp += bool(f)
        detail[addr(c)] = {"gold": gold[c], "translated": t, "exact": bool(e), "fingerprint": bool(f)}
    row.update({"status": "MEASURED", "exact_correct": exact, "fingerprint_correct": fp,
                "translation_ceiling_exact": round(exact / len(in_gold), 6) if in_gold else None,
                "translation_ceiling_fingerprint": round(fp / len(in_gold), 6) if in_gold else None,
                "all_members_reproduced": exact == len(in_gold) and len(in_gold) == len(cells),
                "detail": detail})
    return row


def survey(min_lines: int = pg.MIN_WITNESS_LINES, save: bool = True) -> dict:
    """Eligibility over each task's whole authorised set. No selection toward eligibility."""
    rows = []
    for task in TASKS:
        plan, spine, by_cell, cid_of = P.authorised(task)
        forms, kinds = pg.input_formulas(task), pg.input_kinds(task)
        gold = gold_map(task)
        groups, refused = pg.groups_for(sorted(by_cell), by_cell, task, forms, kinds, min_lines)
        ceilings = [ceiling_for(task, g, gold) for g in groups]
        rows.append({
            "task": task,
            "authorised_cells": len(by_cell),
            "cells_in_eligible_groups": sum(len(g["member_cells"]) for g in groups),
            "n_groups": len(groups),
            "group_sizes": sorted(len(g["member_cells"]) for g in groups),
            "refusal_reasons": dict(Counter(r["reason"] for r in refused)),
            "cells_refused": {r: sum(len(x["members"]) for x in refused if x["reason"] == r)
                              for r in {x["reason"] for x in refused}},
            "groups": groups, "ceilings": ceilings,
        })
    tot_cells = sum(r["authorised_cells"] for r in rows)
    tot_grouped = sum(r["cells_in_eligible_groups"] for r in rows)
    measured = [c for r in rows for c in r["ceilings"] if c.get("status") == "MEASURED"]
    ex = sum(c["exact_correct"] for c in measured)
    fpc = sum(c["fingerprint_correct"] for c in measured)
    den = sum(c["n_members_in_gold_edit_set"] for c in measured)
    summary = {
        "tasks": TASKS, "quarantined": QUARANTINED, "min_witness_lines": min_lines,
        "authorised_cells": tot_cells,
        "cells_in_eligible_groups": tot_grouped,
        "share_of_authorised_cells_in_a_program_group": round(tot_grouped / tot_cells, 6) if tot_cells else None,
        "groups": sum(r["n_groups"] for r in rows),
        "groups_with_a_measurable_ceiling": len(measured),
        "TRANSLATION_CEILING_EXACT": round(ex / den, 6) if den else None,
        "TRANSLATION_CEILING_FINGERPRINT": round(fpc / den, 6) if den else None,
        "groups_fully_reproduced_by_translation": sum(1 for c in measured if c["all_members_reproduced"]),
    }
    out = {"summary": summary, "tasks": rows}
    if save:
        old.write(OUT / "preflight_survey.json", out)
    return out


def evidence_sweep() -> dict:
    """The ceiling under each evidence standard, so the chosen one is defensible.

    Disclosure: the corroboration requirement was added after inspecting which
    groups the single-witness rule could not represent. That inspection used
    gold. The rule itself remains gold-blind at runtime, and both settings are
    reported so the choice is visible rather than buried.
    """
    rows = []
    for ml in (1, 2, 3):
        s = survey(ml, save=False)["summary"]
        rows.append({k: s[k] for k in ("min_witness_lines", "groups", "cells_in_eligible_groups",
                                       "share_of_authorised_cells_in_a_program_group",
                                       "groups_with_a_measurable_ceiling",
                                       "TRANSLATION_CEILING_EXACT",
                                       "TRANSLATION_CEILING_FINGERPRINT",
                                       "groups_fully_reproduced_by_translation")})
    out = {"sweep": rows}
    old.write(OUT / "evidence_sweep.json", out)
    return out


if __name__ == "__main__":
    print(json.dumps(survey()["summary"], indent=1))
