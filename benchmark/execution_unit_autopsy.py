#!/usr/bin/env python3
"""Mandatory matched-pair autopsy for 07_03 (§23).

07_03 is quarantined from the Phase B population because its gold edit set fails
apparatus validation, so no causal claim rests on it. The autopsy is still owed,
and it is entirely mechanical: the proposal is the one already recovered from a
stored response by the duplicate-emission parser repair, so this makes no model
call.

Two counterfactuals are run over the recovered proposal:

    ISOLATED        D8 alone, with the model's own formula
    CLOSURE_GOLD    D8 with the model's formula, plus the closure members set to
                    gold content, which is an evaluator intervention and answers
                    only "was coordination necessary", never "could the model do it"
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import execution_unit_probe as P
import execution_unit_score as S

TASK = "07_03"
PROPOSAL = "=Inputs!C11"
SEED_ID = "cell:s06:r8:c4"


def run() -> dict:
    plan, spine, by_cell, cid_of = P.authorised(TASK)
    seed, _ = P.cell_of(spine, SEED_ID)
    g_off = cc.graph_input_plus_offset(TASK)[0]
    auth = set(by_cell)
    precs = P.proposal_precedents(PROPOSAL, seed)
    closure = set()
    for p in precs:
        closure |= cc.ancestors_within(p, g_off, auth)
    closure |= (precs & auth)
    closure.discard(seed)
    members = sorted(closure)

    name_iso, name_cls = "autopsy_07_03__ISOLATED", "autopsy_07_03__CLOSURE_GOLD"
    edits_iso = [{"sheet": seed[0], "address": cc.a1(seed[1], seed[2]), "formula": PROPOSAL}]
    edits_cls = list(edits_iso)
    gold_missing = []
    for m in members:
        g = S.gold_formula(TASK, m)
        if g is None:
            gold_missing.append(f"{m[0]}!{cc.a1(m[1], m[2])}")
            continue
        edits_cls.append({"sheet": m[0], "address": cc.a1(m[1], m[2]), "formula": g})
    paths = {name_iso: S.build(TASK, name_iso, edits_iso),
             name_cls: S.build(TASK, name_cls, edits_cls)}
    ccf.recalculate(S.WORK / TASK)
    scores = {n: ccf.score(TASK, p) for n, p in paths.items()}
    strict = {n: S.strict_score(TASK, p) for n, p in paths.items()}
    ok_iso, _ = S.correct_S(TASK, paths[name_iso])
    ok_cls, _ = S.correct_S(TASK, paths[name_cls])
    mod, reg, meta = cc.population_S(TASK)
    out = {
        "task": TASK, "quarantined": TASK in P.QUARANTINED,
        "seed": f"{seed[0]}!{cc.a1(seed[1], seed[2])}", "proposal": PROPOSAL,
        "proposal_source": "recovered from a stored response by the duplicate-emission repair",
        "seed_authorised_by_edit_plan": seed in auth,
        "gold_formula_at_seed": S.gold_formula(TASK, seed),
        "proposal_matches_gold_text": S._same(PROPOSAL, S.gold_formula(TASK, seed)),
        "closure_size": len(members),
        "closure_members": [f"{m[0]}!{cc.a1(m[1], m[2])}" for m in members],
        "closure_members_without_gold_content": gold_missing,
        "population": {"E": len(cc.population_E(TASK)),
                       "F": len(cc.population_F(cc.population_E(TASK))),
                       "S_modification": len(mod), "S_regression": len(reg),
                       "answer_position": meta["answer_position_ranges"]},
        "scores": scores, "scores_value_only": strict,
        "S_correct_isolated": len(ok_iso), "S_correct_closure_gold": len(ok_cls),
        "isolated_sufficient": scores[name_iso]["modification_accuracy"] == scores[name_cls]["modification_accuracy"],
        "closure_adds": round((scores[name_cls]["modification_accuracy"] or 0)
                              - (scores[name_iso]["modification_accuracy"] or 0), 6),
        "why_the_score_reaches_0_75": {
            "official_modification_accuracy": scores[name_iso]["modification_accuracy"],
            "value_only_modification_accuracy": strict[name_iso]["modification"]["value_only_accuracy"],
            "cells_taking_error_fallback": strict[name_iso]["modification"]["took_error_fallback"],
            "correct_only_via_error_fallback": strict[name_iso]["modification"]["correct_only_via_error_fallback"],
            "reading": "the proposal resolved to a label, propagated #VALUE!, and every "
                       "error cell was then compared by unchanged formula text instead of value"},
    }
    old.write(P.OUT / "autopsy_07_03.json", out)
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
