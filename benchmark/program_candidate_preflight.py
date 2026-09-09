#!/usr/bin/env python3
"""Phase A: is the correct canonical program already in the workbook?

No model calls. For every mechanically eligible ProgramGroup, build the
deterministic candidate sets M0..M3 and ask, evaluator-side and only after the
sets exist, whether any of them translates to the gold canonical formula.

The distinction this is built to draw:

    PROGRAM RECOVERY   the correct program already exists in the workbook and
                       has to be found, selected and bound
    PROGRAM SYNTHESIS  no existing program translates to it, and the model has
                       to construct something genuinely new

Gold is read here to score candidate availability. It never generates a
candidate, never orders one, and never reaches a runtime rule.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import execution_unit_score as S
import program_candidate as pcand
import program_group as pg
import program_group_preflight as pf
import program_group_probe as PC

OUT = old.MECHANICAL / "canonical-choice-probe"
TASKS = pf.TASKS
QUARANTINED = pf.QUARANTINED

# The three groups §11 makes mandatory; they are the Phase C execution record.
MANDATORY = [("08_03", "Working Capital!J44"),
             ("08_04", "Working Capital!C68"),
             ("08_05", "Working Capital!C66")]

CUMULATIVE = [("M0", ("M0",)),
              ("M0+M1", ("M0", "M1")),
              ("M0+M1+M2", ("M0", "M1", "M2")),
              ("M3", ("M3",))]


def population() -> list[dict]:
    """Every eligible group in the six tasks, plus the groups Phase C executed.

    The survey set is complete -- no selection toward what Phase C got right.
    The Phase C groups are added because §11 requires them and because their
    canonical members are the ones whose failures this probe has to explain;
    where a Phase C group has the same task and canonical as a survey group,
    only one copy is kept.
    """
    survey = json.loads((PC.OUT / "preflight_survey.json").read_text())
    out, seen = [], set()
    for t in survey["tasks"]:
        for g in t["groups"]:
            key = (t["task"], g["canonical_member"])
            seen.add(key)
            out.append({"task": t["task"], "origin": "SURVEY", "group": g})
    for p in sorted((PC.OUT / "units").glob("*.json")):
        rec = json.loads(p.read_text())
        task = rec["unit"]["task"]
        for g in rec["program_groups"]:
            key = (task, g["canonical_member"])
            if key in seen:
                continue
            seen.add(key)
            out.append({"task": task, "origin": "PHASE_C", "group": g})
    return out


def _hit(cands: list[dict], gold: str | None) -> dict:
    if not gold:
        return {"gold_exact": None, "gold_fingerprint": None,
                "n_exact": 0, "n_fingerprint": 0}
    shape = pg.formula_a1_shape(gold)
    ex = [c for c in cands if S._same(c["translated_formula_at_canonical"], gold)]
    fp = [c for c in cands if c["fingerprint"] == shape]
    return {"gold_exact": bool(ex), "gold_fingerprint": bool(fp),
            "n_exact": len(ex), "n_fingerprint": len(fp),
            "exact_candidate_ids": [c["candidate_id"] for c in ex]}


def row_for(task: str, entry: dict, forms, gold: dict) -> dict:
    g = entry["group"]
    canon = tuple(g["canonical_cell"])
    gold_formula = gold.get(canon)
    row = {"task": task, "origin": entry["origin"],
           "canonical_member": g["canonical_member"],
           "axis": g["axis"], "n_members": len(g["member_cells"]),
           "members": g["members"][:1] + (["..."] if len(g["members"]) > 2 else []) + g["members"][-1:],
           "canonical_in_gold_edit_set": gold_formula is not None,
           "gold_canonical_formula": gold_formula,
           "gold_fingerprint": pg.formula_a1_shape(gold_formula) if gold_formula else None,
           "mechanisms": {}}
    # Separates "the program exists but cannot legally translate here" from "the
    # program does not exist in this workbook at all". M3 answers the first;
    # only this answers the second.
    if gold_formula:
        shape = pg.formula_a1_shape(gold_formula)
        row["fingerprint_occurrences_anywhere"] = sum(
            1 for f in forms.values() if pg.formula_a1_shape(f) == shape)
        row["exact_occurrences_anywhere"] = sum(
            1 for f in forms.values() if S._same(f, gold_formula))
    per = {m: pcand.dedupe(pcand.GENERATORS[m](g, forms)) for m in pcand.MECHANISMS}
    for label, ms in CUMULATIVE:
        cands = pcand.dedupe([c for m in ms for c in pcand.GENERATORS[m](g, forms)]) \
            if len(ms) > 1 else per[ms[0]]
        row["mechanisms"][label] = {"n_candidates": len(cands), **_hit(cands, gold_formula)}
    row["raw_counts"] = {m: len(per[m]) for m in pcand.MECHANISMS}
    return row


def classify(row: dict, runtime: str) -> str:
    """Availability class for one group under the chosen runtime mechanism."""
    if not row["canonical_in_gold_edit_set"]:
        return "OPAQUE_CANONICAL_NOT_IN_GOLD_EDIT_SET"
    rt, ceiling = row["mechanisms"][runtime], row["mechanisms"]["M3"]
    if rt["gold_exact"]:
        return "RECOVERABLE_EXACT"
    if ceiling["gold_exact"]:
        return "EXISTING_ELSEWHERE_NOT_RETRIEVED"
    if rt["gold_fingerprint"] or ceiling["gold_fingerprint"]:
        return "RECOVERABLE_SHAPE_ONLY"
    if row.get("fingerprint_occurrences_anywhere"):
        return "EXISTING_ELSEWHERE_NOT_TRANSLATABLE"
    return "GENUINELY_NOVEL"


def _stats(xs: list[int]) -> dict:
    if not xs:
        return {"mean": None, "median": None, "p95": None, "max": None}
    ordered = sorted(xs)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {"mean": round(statistics.fmean(ordered), 2), "median": statistics.median(ordered),
            "p95": ordered[idx], "max": ordered[-1]}


def run(runtime: str = "M0+M1+M2") -> dict:
    pop = population()
    by_task: dict[str, list] = {}
    for e in pop:
        by_task.setdefault(e["task"], []).append(e)
    rows = []
    for task in TASKS:
        if task not in by_task:
            continue
        forms = pg.input_formulas(task)
        gold = pf.gold_map(task)
        for e in by_task[task]:
            rows.append(row_for(task, e, forms, gold))
    scorable = [r for r in rows if r["canonical_in_gold_edit_set"]]
    curves = []
    for label, _ in CUMULATIVE:
        n = len(scorable)
        curves.append({
            "mechanism": label,
            "groups_scored": n,
            "exact_candidate_recall": round(
                sum(1 for r in scorable if r["mechanisms"][label]["gold_exact"]) / n, 6) if n else None,
            "fingerprint_candidate_recall": round(
                sum(1 for r in scorable if r["mechanisms"][label]["gold_fingerprint"]) / n, 6) if n else None,
            **{f"candidates_{k}": v for k, v in
               _stats([r["mechanisms"][label]["n_candidates"] for r in rows]).items()},
        })
    for r in rows:
        r["availability_class"] = classify(r, runtime)
    out = {"runtime_mechanism": runtime,
           "tasks": TASKS, "quarantined": QUARANTINED,
           "groups": len(rows), "groups_scored": len(scorable),
           "recall_curve": curves,
           "availability": dict(Counter(r["availability_class"] for r in rows)),
           "availability_scored": dict(Counter(r["availability_class"] for r in scorable)),
           "rows": rows}
    old.write(OUT / "candidate_preflight.json", out)
    return out


def autopsy(task: str, canonical: str) -> dict:
    """Was the correct program mechanically available for one named canonical?"""
    pop = [e for e in population() if e["task"] == task
           and e["group"]["canonical_member"] == canonical]
    if not pop:
        return {"task": task, "canonical_member": canonical, "status": "GROUP_NOT_FOUND"}
    forms, gold = pg.input_formulas(task), pf.gold_map(task)
    entry = pop[0]
    g = entry["group"]
    row = row_for(task, entry, forms, gold)
    gold_formula = row["gold_canonical_formula"]
    detail = {}
    for m in pcand.MECHANISMS:
        cands = pcand.dedupe(pcand.GENERATORS[m](g, forms))
        hit = _hit(cands, gold_formula)
        sample = [{"candidate_id": c["candidate_id"],
                   "formula": c["translated_formula_at_canonical"],
                   "source": c["source_cell_id"]} for c in cands[:12]]
        detail[m] = {"n_candidates": len(cands), **hit, "first_candidates": sample,
                     "exact_sources": [p["source_cell_id"] for c in cands
                                       if S._same(c["translated_formula_at_canonical"], gold_formula)
                                       for p in c["provenance"]][:12]}
    return {"task": task, "canonical_member": canonical, "origin": entry["origin"],
            "n_members": len(g["member_cells"]),
            "gold_canonical_formula": gold_formula,
            "gold_fingerprint": row["gold_fingerprint"],
            "by_mechanism": detail,
            "availability_class": classify(row, "M0+M1+M2")}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "run"
    if which == "autopsy":
        res = [autopsy(t, c) for t, c in MANDATORY]
        old.write(OUT / "availability_autopsy.json", {"autopsies": res})
        for r in res:
            print(json.dumps({k: r[k] for k in ("task", "canonical_member", "origin",
                                                "gold_canonical_formula", "availability_class")}))
            for m, d in r["by_mechanism"].items():
                print("   ", m, "n=", d["n_candidates"], "exact=", d["gold_exact"],
                      "fingerprint=", d["gold_fingerprint"])
    else:
        o = run()
        print(json.dumps({k: o[k] for k in ("runtime_mechanism", "groups", "groups_scored",
                                            "availability", "availability_scored")}, indent=1))
        print(json.dumps(o["recall_curve"], indent=1))
