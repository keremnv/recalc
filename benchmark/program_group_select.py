#!/usr/bin/env python3
"""Frozen, evaluator-blind selection of ExecutionUnits for the translation probe.

Phase B's units were seeded for the closure experiment and only one turned out
to hold a multi-member ProgramGroup, so candidates are predicted here.

The prediction never uses gold and never uses a model. For a candidate seed we
build a *proxy* formula by translating the nearest existing input-workbook
homologue into the seed's position, run the frozen C1 closure on that proxy, and
keep seeds whose predicted closure holds an eligible ProgramGroup.

At execution time the proxy is discarded: the closure that runs is seeded by the
model's own proposal, exactly as Phase B froze it. A unit whose real closure
holds no group is reported, not dropped, because the rate at which members share
a program is one of the questions being asked.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import instrumentation_freeze as instr
import program_group as pg
import program_group_preflight as pf

OUT = pf.OUT
MAX_PER_TASK = 3
UNITS_MAX = 12

# The units §6 names, reused from Phase B with their sessions intact.
PRIORITY = [("08_03", "Income Statement!C69"), ("08_03", "Working Capital!M50"),
            ("08_04", "Income Statement!R69"), ("08_04", "DCF Valuation!J20"),
            ("08_05", "Balance Sheet!C9"), ("08_05", "Balance Sheet!P20"),
            ("17_03", "Ratio_Analysis!K12")]
HOMOLOGUE_WINDOW = pg.WITNESS_WINDOW

LIMITS = {"model": "z-ai/glm-5.3-flash", "temperature": 0, "reasoning": "medium", "retries": 0,
          "max_sql_calls": old.MAX_SQL_CALLS, "per_session_input_cap": 400_000,
          "total_input_cap": 4_000_000, "units_min": 8, "units_max": 12,
          "arms": {"P0": "PER_CELL_SYNTHESIS", "P1": "SYNTHESIZE_ONCE_TRANSLATE"},
          "closure_rule": "C1 input-side OFFSET-aware, seeded by the model's proposed formula",
          "authority_rule": "members must already be authorised by the generated Edit Plan",
          "group_rule": "repetition witness in the input workbook at the group's own coordinates",
          "min_witness_lines": pg.MIN_WITNESS_LINES,
          "selection": "proxy formula translated from the nearest input homologue; never gold, never a model"}


def addr(c):
    return f"{c[0]}!{cc.a1(c[1], c[2])}"


def nearest_homologue(cell: cc.Cell, forms: dict) -> tuple[cc.Cell, str] | None:
    """The closest existing input formula sharing this cell's row or column position."""
    sheet, r, c = cell
    for dist in range(1, HOMOLOGUE_WINDOW + 1):
        for cand in ((sheet, r - dist, c), (sheet, r + dist, c),
                     (sheet, r, c - dist), (sheet, r, c + dist)):
            if cand[1] >= 1 and cand[2] >= 1 and cand in forms:
                return cand, forms[cand]
    return None


def predicted_closure(task: str, seed: cc.Cell, proxy: str, graph, auth: set) -> set:
    precs = P.proposal_precedents(proxy, seed)
    out = set()
    for p in precs:
        out |= cc.ancestors_within(p, graph, auth)
    out |= (precs & auth)
    out.discard(seed)
    return out


def select() -> dict:
    existing = []
    for p in sorted((P.OUT / "units").glob("*.json")):
        rec = old.load(p)
        existing.append(rec)
    chosen, considered = [], []
    for task in pf.TASKS:
        plan, spine, by_cell, cid_of = P.authorised(task)
        forms, kinds = pg.input_formulas(task), pg.input_kinds(task)
        graph, _ = cc.graph_input_plus_offset(task)
        auth = set(by_cell)
        picked = 0
        seen_groups: set[str] = set()
        for cell in sorted(auth):
            if picked >= MAX_PER_TASK:
                break
            hom = nearest_homologue(cell, forms)
            if hom is None:
                continue
            src, f = hom
            try:
                proxy = pg.translate(f, src, cell)
            except Exception:
                continue
            closure = predicted_closure(task, cell, proxy, graph, auth)
            if not closure:
                continue
            groups, _ = pg.groups_for(sorted(closure), by_cell, task, forms, kinds)
            best = max((len(g["member_cells"]) for g in groups), default=0)
            considered.append({"task": task, "seed": addr(cell), "predicted_members": len(closure),
                               "predicted_groups": len(groups), "largest_group": best})
            if best < 2:
                continue
            # One seed per distinct coordinated group. Adjacent seeds in a row
            # otherwise reach overlapping slices of the same swept run, which
            # would inflate the population without adding evidence.
            reached = {m for g in groups if len(g["member_cells"]) >= 2 for m in g["members"]}
            if reached & seen_groups:
                continue
            seen_groups |= reached
            chosen.append({
                "task": task, "seed": addr(cell), "seed_cell": list(cell),
                "seed_cell_id": cid_of[cell],
                "operation_id": by_cell[cell]["operation_id"],
                "obligation_id": by_cell[cell]["obligation_id"],
                "operation_kind": by_cell[cell].get("operation_kind"),
                "origin": "PREDICTED",
                "proxy_formula": proxy, "proxy_source": addr(src),
                "predicted_members": len(closure),
                "predicted_groups": [g["members"] for g in groups],
            })
            picked += 1
    # Phase B units come first and are never displaced: they were frozen earlier
    # and their sessions are reused byte for byte.
    prior = []
    for rec in existing:
        u = rec["unit"]
        if u["task"] in pf.QUARANTINED or (u["task"], u["seed"]) not in PRIORITY:
            continue
        prior.append({"task": u["task"], "seed": u["seed"], "seed_cell": u["seed_cell"],
                      "seed_cell_id": u["seed_cell_id"], "operation_id": u["operation_id"],
                      "obligation_id": u["obligation_id"],
                      "operation_kind": u.get("operation_kind"),
                      "origin": "PHASE_B", "phase_a_regime": u["phase_a_regime"]})
    have = {(x["task"], x["seed"]) for x in prior}
    add = [x for x in chosen if (x["task"], x["seed"]) not in have]
    units = prior + add[: max(0, UNITS_MAX - len(prior))]
    payload = {"limits": LIMITS, "quarantined": pf.QUARANTINED,
               "n_prior": len(prior), "n_predicted": len(units) - len(prior),
               "units": units, "considered": considered}
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload["units"], sort_keys=True).encode()).hexdigest()
    old.write(OUT / "units.json", payload)
    return payload


def freeze():
    path = OUT / "freeze.json"
    if path.exists():
        raise RuntimeError("already frozen")
    f = instr.check()
    units = old.load(OUT / "units.json")
    paths = [Path(__file__), Path(pg.__file__), Path(P.__file__), Path(old.__file__),
             Path(cc.__file__)]
    old.write(path, {
        "limits": LIMITS, "units_sha256": units["sha256"],
        "instrumentation_generation": f.get("generation"),
        "instrumentation_sha256": f["sha256"],
        "non_model_failure_classes": f["non_model_failure_classes"],
        "sha256": {str(p.resolve().relative_to(old.ROOT)):
                   hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "arms": {"P0": "every authorised member gets its own retrieval/synthesis session",
                 "P1": "one canonical synthesis per ProgramGroup, then deterministic "
                       "translation; members in no group fall to the identical P0 session, "
                       "which is recorded, never silent"},
        "shared_sessions": "the seed session and every P0 member session are reused byte for byte",
        "group_rule_frozen_before_any_model_call": True,
    })
    print(json.dumps({"frozen_units": len(units["units"]),
                      "prior": units["n_prior"], "predicted": units["n_predicted"]}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["select", "freeze"])
    a = ap.parse_args()
    if a.command == "select":
        d = select()
        print(json.dumps({"units": len(d["units"]), "prior": d["n_prior"],
                          "predicted": d["n_predicted"]}, indent=1))
        for u in d["units"]:
            g = u.get("predicted_groups")
            print(f"  {u['task']} {u['seed']:30s} {u['origin']:9s} "
                  f"{'groups=' + str([len(x) for x in g]) if g else ''}")
    else:
        freeze()
