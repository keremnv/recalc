#!/usr/bin/env python3
"""Phase B: A0 free-form canonical synthesis against A1 candidate-first choice.

The arms share everything except one turn. Both use the same ProgramGroup, the
same canonical member, the same grounded goal and -- this is the part that makes
the comparison exact -- the same retrieval session. A1 does not re-query: it
rebuilds A0's own synthesis input from the stored working set and adds the
frozen ProgramCandidate list. So the 8-query retrieval policy is not merely
unchanged, it is literally the same eight queries.

After the choice, both arms translate across the group with the Phase C
implementation, unmodified. Choose once, propagate mechanically.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import canonical_choice as cch
import canonical_choice_select as sel
import end_to_end_composition_probe as old
import execution_unit_probe as P
import instrumentation_freeze as instr
import program_group as pg
import program_group_probe as PC

OUT = sel.OUT
LIMITS = sel.LIMITS
NON_MODEL = set(instr.NON_MODEL_FAILURE_CLASSES)

SESSION_DIRS = [OUT / "sessions", PC.OUT / "sessions", P.OUT / "sessions"]


def spent() -> int:
    """Input tokens this probe charges. Sessions inherited from earlier probes
    were paid for under the same frozen conditions and are reported separately."""
    total = 0
    for p in (OUT / "sessions").glob("*.json"):
        s = old.load(p)
        total += s.get("retrieval_input_tokens", 0) + s.get("synthesis_input_tokens", 0)
    for p in (OUT / "choices").glob("*.json"):
        total += old.load(p).get("choice_input_tokens", 0)
    return total


def a0_session(task, cell, cid, obligation_id, plan, spine, key):
    """A0's canonical synthesis, reused from any earlier probe that already ran it."""
    name = f"{task}__{cid.replace(':', '_')}.json"
    for d in SESSION_DIRS[1:]:
        prior = d / name
        if prior.exists():
            s = old.load(prior)
            s["reused_from"] = prior.parent.parent.name
            return s
    path = OUT / "sessions" / name
    if path.exists():
        return old.load(path)
    ob = next(o for o in plan["compiler"]["obligations"] if o["id"] == obligation_id)
    target = old.target_address(spine, cid)
    info = old.input_cell_info(task, target["sheet"], target["address"])
    target.update({"target_id": cid, "current_input_content": info["raw_value"],
                   "current_input_kind": info["kind"]})
    t0 = time.perf_counter()
    s = old.run_target(task, plan["compiler"]["raw_task"], ob, target,
                       plan["grounding"]["packets"][obligation_id], spine, key,
                       synthesis_system=old.SYNTHESIS_SYSTEM,
                       retrieval_system=old.DELTA_RETRIEVAL_SYSTEM,
                       delta_state=True,
                       session_input_cap=LIMITS["per_session_input_cap"])
    s["wall_seconds"] = time.perf_counter() - t0
    s["cell"] = list(cell)
    s["cell_id"] = cid
    s["reused_from"] = None
    old.write(path, s)
    return s


def run():
    f = old.load(OUT / "freeze.json")
    me = str(Path(__file__).resolve().relative_to(old.ROOT))
    drift = {}
    for name, digest in f["sha256"].items():
        now = hashlib.sha256((old.ROOT / name).read_bytes()).hexdigest()
        if now != digest:
            if name != me:
                raise RuntimeError(f"frozen component changed: {name}")
            drift[name] = now
    instr.check()
    old.guard(LIMITS["model"])
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    units = old.load(OUT / "units.json")["units"]
    old.write(OUT / "run_manifest.json",
              {"frozen_sha256": f["sha256"], "runner_drift": drift,
               "instrumentation_generation": f.get("instrumentation_generation")})

    ctx = {}
    for u in units:
        if u["task"] not in ctx:
            plan, spine, by_cell, cid_of = P.authorised(u["task"])
            ctx[u["task"]] = (plan, spine, by_cell, cid_of)

    results = []
    for u in units:
        name = f"{u['task']}__{u['canonical_member'].replace('!', '_').replace(' ', '_')}.json"
        out_path = OUT / "units" / name
        if out_path.exists():
            results.append(old.load(out_path))
            continue
        plan, spine, by_cell, cid_of = ctx[u["task"]]
        canon = tuple(u["canonical_cell"])
        raw_task = plan["compiler"]["raw_task"]

        if spent() >= LIMITS["total_input_cap"]:
            rec = {"unit": u, "status": "RESOURCE_CENSORED_NOT_RUN"}
            old.write(out_path, rec)
            results.append(rec)
            continue

        s = a0_session(u["task"], canon, u["canonical_cell_id"], u["obligation_id"],
                       plan, spine, key)
        a0_outcome = PC.outcome_of(s)
        a0_formula = P.proposed_formula(s)

        cpath = OUT / "choices" / name
        if cpath.exists():
            choice = old.load(cpath)
        else:
            choice = cch.choose(u["task"], s, raw_task, u["candidates"], key)
            old.write(cpath, choice)

        group = {"axis": u["axis"], "members": u["members"],
                 "member_cells": u["member_cells"], "canonical_cell": u["canonical_cell"],
                 "canonical_member": u["canonical_member"]}
        arms = {}
        for arm, formula in (("A0", a0_formula), ("A1", choice["formula"])):
            if formula:
                applied = pg.apply_program(formula, group)
                arms[arm] = {"canonical_formula": formula,
                             "formulas": applied["formulas"],
                             "translation_failures": applied["failures"]}
            else:
                arms[arm] = {"canonical_formula": None, "formulas": {},
                             "translation_failures": {}}

        rec = {"unit": u, "status": "RUN",
               "A0_outcome": a0_outcome, "A0_session_reused_from": s.get("reused_from"),
               "A0": arms["A0"],
               "A1_outcome": choice["outcome"], "A1_candidate_id": choice["candidate_id"],
               "A1_failure_class": choice.get("failure_class"),
               "A1": arms["A1"],
               "n_candidates": u["n_candidates"],
               "input_tokens_after": spent()}
        old.write(out_path, rec)
        results.append(rec)
        print(json.dumps({"task": u["task"], "canonical": u["canonical_member"],
                          "class": u["availability_class"],
                          "candidates": u["n_candidates"],
                          "A0": a0_outcome, "A0_formula": a0_formula,
                          "A1": choice["outcome"], "A1_candidate": choice["candidate_id"],
                          "A1_formula": choice["formula"],
                          "spent": spent()}), flush=True)

    old.write(OUT / "arms.json", {"units": results, "limits": LIMITS,
                                  "new_input_tokens": spent()})
    return results


if __name__ == "__main__":
    run()
