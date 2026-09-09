#!/usr/bin/env python3
"""Score the canonical-choice arms: formula level first, workbook level second.

Everything up to `score_formulas` is cheap and needs no LibreOffice, because the
primary question -- when the correct program is in the candidate set, is it
chosen? -- is answered at the level of the canonical formula. The workbook pass
then ties that choice back to the Phase C execution funnel: translate, write,
recalculate, score.

A1's outcomes are read from the re-parsed record where one exists, and the
as-run outcome is carried alongside it so the repair never disappears.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical_choice_select as sel
import composition_closure as cc
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import execution_unit_score as S
import program_group as pg
import program_group_preflight as pf
import program_group_score as PGS

OUT = sel.OUT
WORK = OUT / "variants"

AMBIGUITY_BUCKETS = [("1", 1, 1), ("2-5", 2, 5), ("6-20", 6, 20), (">20", 21, 10 ** 9)]


def build(task: str, name: str, edits: list[dict]):
    """Write one variant workbook into *this* probe's tree.

    Deliberately not reusing the Phase C builder: that module's output root is a
    module-level constant pointing at the Phase C run directory, so calling it
    from here silently wrote this probe's variants into the previous probe's
    tree and left them unrecalculated. Owning the path here keeps each probe's
    artifacts its own.
    """
    dest_dir = WORK / task / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{task}_output.xlsx"
    inp, _ = cc.workbook_paths(task)
    from xlsx_cell_writer import write_cells
    audit = write_cells(inp, dest, edits)
    old.write(dest_dir / "audit.json", {"variant": name, "edits": edits, "audit": audit})
    return dest


def bucket(n: int) -> str:
    for label, lo, hi in AMBIGUITY_BUCKETS:
        if lo <= n <= hi:
            return label
    return ">20"


def _reparsed() -> dict:
    p = OUT / "choices_reparsed.json"
    if not p.exists():
        return {}
    return {(r["task"], r["canonical_member"]): r for r in old.load(p)["rows"]}


def failure_class(row: dict) -> str | None:
    """§18, for whichever arm result is wrong. Availability decides the branch."""
    if row["A1_canonical_exact"]:
        return None
    cls, outcome = row["availability_class"], row["A1_outcome"]
    exact_present = row["exact_candidate_present"]
    if outcome in ("INVALID_OUTPUT", "WRONG_RESPONSE_SCHEMA", "INVALID_CANDIDATE_ID"):
        return outcome
    if outcome == "ABSTAIN":
        # §18 names two abstain cases. A third is needed to keep them honest:
        # abstaining when only the gold *shape* was available is neither
        # "with the correct candidate" nor "nothing existed".
        if exact_present:
            return "ABSTAIN_WITH_CORRECT_CANDIDATE"
        if row["n_fingerprint_candidates"]:
            return "ABSTAIN_WITH_SHAPE_ONLY_CANDIDATE"
        if cls == "GENUINELY_NOVEL":
            return "ABSTAIN_NOVEL"
        # Nothing usable was in the set the model saw, even though the correct
        # program or its shape exists somewhere in the workbook. That is a
        # candidate-recovery miss, not an abstention on a novel program.
        return "ABSTAIN_NO_USABLE_CANDIDATE"
    if outcome == "SELECTED_EXISTING":
        if exact_present:
            return "WRONG_CANDIDATE_SELECTED"
        if cls == "RECOVERABLE_SHAPE_ONLY":
            return "RECOVERY_BINDING_ERROR"
        return "FALSE_RECOVERY"
    if outcome == "COMPOSED_NEW":
        if exact_present:
            return "NEW_WHEN_RECOVERABLE"
        return "NOVEL_SYNTHESIS_WRONG"
    return "CANDIDATE_NOT_AVAILABLE"


def score_formulas() -> dict:
    units = {(u["task"], u["canonical_member"]): u
             for u in old.load(OUT / "units.json")["units"]}
    rep = _reparsed()
    golds = {}
    rows = []
    for p in sorted((OUT / "units").glob("*.json")):
        rec = old.load(p)
        u = rec["unit"]
        task, canon_addr = u["task"], u["canonical_member"]
        gold = golds.setdefault(task, pf.gold_map(task))
        canon = tuple(u["canonical_cell"])
        gold_formula = gold.get(canon)
        r = rep.get((task, canon_addr)) or {}
        a1_outcome = r.get("reparsed_outcome", rec["A1_outcome"])
        a1_formula = r.get("reparsed_formula", rec["A1"]["canonical_formula"])
        a0_formula = rec["A0"]["canonical_formula"]
        cands = units[(task, canon_addr)]["candidates"]
        exact_ids = [c["candidate_id"] for c in cands
                     if gold_formula and S._same(c["translated_formula_at_canonical"], gold_formula)]
        shape = pg.formula_a1_shape(gold_formula) if gold_formula else None
        fp_ids = [c["candidate_id"] for c in cands if shape and c["fingerprint"] == shape]
        distinct = len({c["fingerprint"] for c in cands})

        def members(formula):
            if not formula:
                return {}
            return pg.apply_program(formula, {"member_cells": u["member_cells"],
                                              "canonical_cell": u["canonical_cell"]})["formulas"]

        row = {"task": task, "canonical_member": canon_addr,
               "availability_class": u["availability_class"],
               "n_members": u["n_members"], "n_candidates": u["n_candidates"],
               "ambiguity_bucket": bucket(u["n_candidates"]),
               "n_exact_candidates": len(exact_ids), "exact_candidate_ids": exact_ids,
               "exact_candidate_present": bool(exact_ids),
               "n_fingerprint_candidates": len(fp_ids),
               "n_structurally_distinct_candidates": distinct,
               "gold_canonical_formula": gold_formula,
               "A0_outcome": rec["A0_outcome"], "A0_formula": a0_formula,
               "A0_canonical_exact": S._same(a0_formula, gold_formula),
               "A1_outcome_as_run": rec["A1_outcome"], "A1_outcome": a1_outcome,
               "A1_candidate_id": r.get("reparsed_candidate_id", rec["A1_candidate_id"]),
               "A1_formula": a1_formula,
               "A1_canonical_exact": S._same(a1_formula, gold_formula),
               "A0_session_reused_from": rec["A0_session_reused_from"]}
        for arm, formula in (("A0", a0_formula), ("A1", a1_formula)):
            written = members(formula)
            in_gold = [c for c in u["member_cells"] if tuple(c) in gold]
            ok = sum(1 for c in in_gold
                     if S._same(written.get(f"{c[0]}!{cc.a1(c[1], c[2])}"), gold[tuple(c)]))
            row[f"{arm}_members_required"] = len(in_gold)
            row[f"{arm}_members_exact"] = ok
            row[f"{arm}_all_members_exact"] = bool(in_gold) and ok == len(in_gold)
            row[f"{arm}_formulas"] = written
        row["A1_failure_class"] = failure_class(row)
        # §25: what selecting the gold candidate would have produced, no model call.
        if exact_ids:
            oracle = next(c for c in cands if c["candidate_id"] == exact_ids[0])
            wr = members(oracle["translated_formula_at_canonical"])
            in_gold = [c for c in u["member_cells"] if tuple(c) in gold]
            row["oracle_members_exact"] = sum(
                1 for c in in_gold
                if S._same(wr.get(f"{c[0]}!{cc.a1(c[1], c[2])}"), gold[tuple(c)]))
            row["oracle_all_members_exact"] = bool(in_gold) and row["oracle_members_exact"] == len(in_gold)
            row["oracle_formulas"] = wr
        else:
            row["oracle_members_exact"] = None
            row["oracle_all_members_exact"] = None
            row["oracle_formulas"] = {}
        rows.append(row)
    out = {"units": rows,
           "canonical_correctness": _by_class(rows),
           "ambiguity": _by_ambiguity(rows),
           "failure_taxonomy": dict(Counter(r["A1_failure_class"] for r in rows
                                            if r["A1_failure_class"]))}
    old.write(OUT / "formula_scores.json", out)
    return out


def _by_class(rows) -> dict:
    out = {}
    for cls in sorted({r["availability_class"] for r in rows}):
        xs = [r for r in rows if r["availability_class"] == cls]
        out[cls] = {"groups": len(xs),
                    "A0_canonical_exact": sum(1 for r in xs if r["A0_canonical_exact"]),
                    "A1_canonical_exact": sum(1 for r in xs if r["A1_canonical_exact"]),
                    "A0_all_members_exact": sum(1 for r in xs if r["A0_all_members_exact"]),
                    "A1_all_members_exact": sum(1 for r in xs if r["A1_all_members_exact"]),
                    "A1_outcomes": dict(Counter(r["A1_outcome"] for r in xs))}
    return out


def _by_ambiguity(rows) -> dict:
    out = {}
    for label, _, _ in AMBIGUITY_BUCKETS:
        xs = [r for r in rows if r["ambiguity_bucket"] == label]
        present = [r for r in xs if r["exact_candidate_present"]]
        out[label] = {"groups": len(xs), "groups_with_an_exact_candidate": len(present),
                      "A1_selected_it": sum(1 for r in present if r["A1_canonical_exact"]),
                      "A0_composed_it": sum(1 for r in present if r["A0_canonical_exact"])}
    return out


def score_workbooks() -> dict:
    """Translate, write, recalculate, score. Ties choice back to the funnel."""
    scores = old.load(OUT / "formula_scores.json")["units"]
    by_task = {}
    for r in scores:
        by_task.setdefault(r["task"], []).append(r)
    results = []
    for task, rows in sorted(by_task.items()):
        variants, tags = {}, {}
        variants["BASE"] = []
        for r in rows:
            tag = r["canonical_member"].replace("!", "_").replace(" ", "_")
            tags[r["canonical_member"]] = tag
            for arm in ("A0", "A1"):
                if r[f"{arm}_formulas"]:
                    variants[f"{tag}__{arm}"] = PGS.edits_from(task, r[f"{arm}_formulas"])
        paths = {n: build(task, n, e) for n, e in variants.items()}
        ccf.recalculate(WORK / task)
        scored = {n: ccf.score(task, p) for n, p in paths.items()}
        strict = {n: S.strict_score(task, p) for n, p in paths.items()}
        cells = {n: S.correct_S(task, p) for n, p in paths.items()}
        base_ok = cells["BASE"][0]
        for r in rows:
            tag = tags[r["canonical_member"]]
            out = {"task": task, "canonical_member": r["canonical_member"],
                   "availability_class": r["availability_class"],
                   "BASE": scored["BASE"], "BASE_S_correct": len(base_ok)}
            for arm in ("A0", "A1"):
                key = f"{tag}__{arm}"
                out[arm] = scored.get(key)
                out[f"{arm}_strict"] = strict.get(key)
                ok = cells.get(key, (set(), {}))[0]
                out[f"{arm}_S_correct"] = len(ok) if key in cells else None
                out[f"{arm}_gained_vs_base"] = sorted(
                    f"{c[0]}!{cc.a1(c[1], c[2])}" for c in ok - base_ok) if key in cells else []
                out[f"{arm}_lost_vs_base"] = sorted(
                    f"{c[0]}!{cc.a1(c[1], c[2])}" for c in base_ok - ok) if key in cells else []
            out["delta_modification_A1_vs_A0"] = S._delta(out["A1"], out["A0"], "modification_accuracy")
            out["delta_regression_A1_vs_A0"] = S._delta(out["A1"], out["A0"], "regression_accuracy")
            out["delta_modification_value_only_A1_vs_A0"] = S._dstrict(
                out.get("A1_strict"), out.get("A0_strict"), "modification")
            results.append(out)
    out = {"units": results}
    old.write(OUT / "workbook_scores.json", out)
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "formulas"
    if which == "workbooks":
        o = score_workbooks()
        for r in o["units"]:
            print(json.dumps({k: r[k] for k in ("task", "canonical_member",
                                                "A0_S_correct", "A1_S_correct",
                                                "delta_modification_A1_vs_A0")}), flush=True)
    else:
        o = score_formulas()
        print(json.dumps(o["canonical_correctness"], indent=1))
        print(json.dumps(o["ambiguity"], indent=1))
        print(json.dumps(o["failure_taxonomy"], indent=1))
