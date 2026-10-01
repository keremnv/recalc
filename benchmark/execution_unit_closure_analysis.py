#!/usr/bin/env python3
"""Where each unit's closure imprecision actually comes from.

The proposal-seeded closure is computed twice: once restricted to the cells the
generated Edit Plan authorises, which is what the B1 arm executed, and once
restricted to the gold content edit set E, which is what an oracle Edit Plan
would have authorised. The difference isolates Edit Plan over-authorisation from
any imprecision in the closure rule itself.

Also records whether a unit's members sit inside the seed's own Edit Plan
operation or span several, which is what decides whether an ExecutionUnit is a
regrouping of one operation or a genuinely cross-operation object.
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


def addr(c):
    return f"{c[0]}!{cc.a1(c[1], c[2])}"


def witnesses() -> dict:
    a = old.load(ccf.OUT / "phase_a_report.json")
    return {(w["task"], w["target"]): w for w in a.get("witness_rule_table", [])}


def run() -> dict:
    wit = witnesses()
    rows = []
    cache = {}
    for p in sorted((P.OUT / "units").glob("*.json")):
        rec = old.load(p)
        u = rec["unit"]
        task = u["task"]
        if task not in cache:
            plan, spine, by_cell, cid_of = P.authorised(task)
            g, _ = cc.graph_input_plus_offset(task)
            E = {(e["sheet"], e["row"], e["col"]) for e in cc.population_E(task)}
            cache[task] = (by_cell, g, E)
        by_cell, g, E = cache[task]
        seed = tuple(u["seed_cell"])
        f = rec.get("seed_formula")
        row = {"task": task, "seed": u["seed"], "regime": u["phase_a_regime"],
               "seed_formula": f, "authorised_cells": len(by_cell), "E": len(E)}
        if not f:
            row["status"] = "NO_PROPOSAL"
            rows.append(row)
            continue
        pr = P.proposal_precedents(f, seed)

        def closure(keep):
            cl = set()
            for c in pr:
                cl |= cc.ancestors_within(c, g, keep)
            cl |= (pr & keep)
            cl.discard(seed)
            return cl

        c_auth, c_gold = closure(set(by_cell)), closure(E)
        w = wit.get((task, u["seed"]))
        w_cells = {P.parse_addr(x) for x in (w or {}).get("witness", [])}
        row.update({
            "status": "OK",
            "precedents_of_proposal": sorted(addr(c) for c in pr),
            "closure_within_edit_plan": sorted(addr(c) for c in c_auth),
            "closure_within_gold_edit_set": sorted(addr(c) for c in c_gold),
            "n_closure_edit_plan": len(c_auth), "n_closure_gold": len(c_gold),
            "members_authorised_but_not_in_gold_edit_set": sorted(addr(c) for c in c_auth - E),
            "closure_precision_vs_gold_edit_set":
                round(len(c_auth & E) / len(c_auth), 6) if c_auth else None,
            "phase_a_minimal_witness": sorted(addr(c) for c in w_cells) or None,
            "witness_recovered_by_executed_closure": (w_cells <= c_auth) if w_cells else None,
            "witness_recovered_by_gold_restricted_closure": (w_cells <= c_gold) if w_cells else None,
            "seed_operation_id": by_cell.get(seed, {}).get("operation_id"),
            "member_operation_ids": sorted({by_cell[c]["operation_id"] for c in c_auth if c in by_cell}),
        })
        row["closure_spans_multiple_operations"] = len(
            set(row["member_operation_ids"]) | {row["seed_operation_id"]}) > 1
        rows.append(row)
    ok = [r for r in rows if r.get("status") == "OK"]
    summary = {
        "units": len(rows),
        "units_with_a_proposal": len(ok),
        "units_whose_witness_is_recovered": sum(1 for r in ok if r["witness_recovered_by_executed_closure"]),
        "units_with_a_witness": sum(1 for r in ok if r["phase_a_minimal_witness"]),
        "closure_members_total": sum(r["n_closure_edit_plan"] for r in ok),
        "closure_members_inside_gold_edit_set": sum(
            r["n_closure_edit_plan"] - len(r["members_authorised_but_not_in_gold_edit_set"]) for r in ok),
        "closure_members_authorised_but_not_gold": sum(
            len(r["members_authorised_but_not_in_gold_edit_set"]) for r in ok),
        "units_spanning_multiple_operations": sum(1 for r in ok if r["closure_spans_multiple_operations"]),
    }
    out = {"summary": summary, "rows": rows}
    old.write(P.OUT / "closure_analysis.json", out)
    return out


if __name__ == "__main__":
    print(json.dumps(run()["summary"], indent=1))
