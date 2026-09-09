#!/usr/bin/env python3
"""Phase C: does one canonical synthesis plus deterministic translation beat
independent per-member synthesis inside a ProgramGroup?

The two arms are matched by construction rather than by care:

    P0  every authorised closure member gets its own retrieval/synthesis session
    P1  one canonical session per ProgramGroup, translated across the group;
        members in no eligible group reuse the identical P0 session

P1's canonical session *is* P0's session for that cell, byte for byte, so the
arms cannot differ in prompt, evidence, seed formula or workbook starting state.
The only treatment is what happens to a group's non-canonical members: solved
independently, or instantiated from the canonical program.

That also makes the cost claim exact. P1 issues no model call that P0 does not
already issue; it issues strictly fewer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import instrumentation_freeze as instr
import program_group as pg
import program_group_preflight as pf
import program_group_select as sel

OUT = pf.OUT
LIMITS = sel.LIMITS
NON_MODEL = set(instr.NON_MODEL_FAILURE_CLASSES)


def addr(c):
    return f"{c[0]}!{cc.a1(c[1], c[2])}"


def spent() -> int:
    """Input tokens this probe charges, which excludes reused Phase B sessions.

    A reused session costs nothing now; it was paid for under the same frozen
    conditions in Phase B. Counting it again would censor this probe against a
    bill it never incurs. Both figures are reported separately.
    """
    return _tokens_in(OUT / "sessions")


def _tokens_in(directory: Path) -> int:
    if not directory.exists():
        return 0
    total = 0
    for p in directory.glob("*.json"):
        s = old.load(p)
        total += s.get("retrieval_input_tokens", 0) + s.get("synthesis_input_tokens", 0)
    return total


def session_for(task, cell, cid, obligation_id, plan, spine, key):
    """One synthesis session for one authorised cell, reused wherever it exists.

    Phase B's sessions are looked up first so a matched arm never re-asks a
    question that has already been asked under the identical frozen conditions.
    """
    name = f"{task}__{cid.replace(':', '_')}.json"
    prior = P.OUT / "sessions" / name
    if prior.exists():
        s = old.load(prior)
        s["reused_from"] = "phase_b"
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
    try:
        s = old.run_target(task, plan["compiler"]["raw_task"], ob, target,
                           plan["grounding"]["packets"][obligation_id], spine, key,
                           synthesis_system=old.SYNTHESIS_SYSTEM,
                           retrieval_system=old.DELTA_RETRIEVAL_SYSTEM,
                           delta_state=True, session_input_cap=LIMITS["per_session_input_cap"])
    except Exception as exc:
        s = {"status": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}",
             "target": target}
    s["wall_seconds"] = time.perf_counter() - t0
    s["cell"] = list(cell)
    s["cell_id"] = cid
    resp = (s.get("synthesis") or {}).get("response") or {}
    s["audit"] = {"raw_text_len": len(resp.get("text") or ""), "usage": resp.get("usage"),
                  "parsed": (s.get("synthesis") or {}).get("parsed"),
                  "truncated": s.get("synthesis_truncated"),
                  "truncation_class": s.get("truncation_class"),
                  "failure_class": s.get("failure_class")}
    s["reused_from"] = None
    old.write(path, s)
    return s


def outcome_of(session) -> str:
    """Why a session produced no formula, keeping non-model causes separate."""
    fc = session.get("failure_class")
    if fc in NON_MODEL:
        return fc
    parsed = (session.get("synthesis") or {}).get("parsed")
    if parsed is None:
        return "UNPARSEABLE"
    return parsed.get("status") or "UNKNOWN"


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
    old.write(OUT / "run_manifest.json", {"frozen_sha256": f["sha256"], "runner_drift": drift,
                                          "instrumentation_generation": f.get("instrumentation_generation")})

    ctx = {}
    for u in units:
        t = u["task"]
        if t not in ctx:
            plan, spine, by_cell, cid_of = P.authorised(t)
            ctx[t] = (plan, spine, by_cell, cid_of,
                      cc.graph_input_plus_offset(t)[0],
                      pg.input_formulas(t), pg.input_kinds(t))

    # Pass 1: seeds. A resource bound must never censor the baseline.
    seeds = {}
    for u in units:
        plan, spine, by_cell, cid_of, graph, forms, kinds = ctx[u["task"]]
        if spent() >= LIMITS["total_input_cap"]:
            seeds[u["seed"]] = {"status": "RESOURCE_CENSORED_NOT_RUN"}
            continue
        s = session_for(u["task"], tuple(u["seed_cell"]), u["seed_cell_id"],
                        u["obligation_id"], plan, spine, key)
        seeds[u["seed"]] = s
        print(json.dumps({"pass": "seed", "task": u["task"], "seed": u["seed"],
                          "reused": s.get("reused_from"), "outcome": outcome_of(s),
                          "formula": P.proposed_formula(s), "spent": spent()}), flush=True)

    results = []
    for u in units:
        out_path = OUT / f"units/{u['task']}__{u['seed'].replace('!', '_').replace(' ', '_')}.json"
        if out_path.exists():
            results.append(old.load(out_path))
            continue
        plan, spine, by_cell, cid_of, graph, forms, kinds = ctx[u["task"]]
        seed = tuple(u["seed_cell"])
        seed_session = seeds[u["seed"]]
        formula = P.proposed_formula(seed_session)
        auth = set(by_cell)
        members, closure_status = [], "NO_PROPOSAL"
        if formula:
            precs = P.proposal_precedents(formula, seed)
            closure = set()
            for c in precs:
                closure |= cc.ancestors_within(c, graph, auth)
            closure |= (precs & auth)
            closure.discard(seed)
            members = sorted(closure)
            closure_status = "CLOSURE_EMPTY" if not members else "CLOSURE_FOUND"
        groups, refused = pg.groups_for(members, by_cell, u["task"], forms, kinds) if members else ([], [])

        # P0: every member independently. P1 shares these sessions.
        p0 = {}
        for m in members:
            if spent() >= LIMITS["total_input_cap"]:
                p0[addr(m)] = {"status": "RESOURCE_CENSORED_NOT_RUN"}
                continue
            p0[addr(m)] = session_for(u["task"], m, cid_of[m], by_cell[m]["obligation_id"],
                                      plan, spine, key)
        p0_formulas = {a: P.proposed_formula(s) if s.get("status") != "RESOURCE_CENSORED_NOT_RUN" else None
                       for a, s in p0.items()}
        p0_outcomes = {a: (s.get("status") if s.get("status") == "RESOURCE_CENSORED_NOT_RUN"
                           else outcome_of(s)) for a, s in p0.items()}

        # P1: one canonical session per group, then translation. Members in no
        # group reuse the identical P0 session, recorded rather than silent.
        p1_formulas, group_records = {}, []
        grouped = set()
        for g in groups:
            canon = tuple(g["canonical_cell"])
            grouped |= {tuple(c) for c in g["member_cells"]}
            canon_session = p0.get(addr(canon))
            canon_formula = p0_formulas.get(addr(canon))
            rec = {**g, "canonical_formula": canon_formula,
                   "canonical_outcome": p0_outcomes.get(addr(canon)),
                   "model_calls": 1, "members_covered": len(g["member_cells"])}
            if not canon_formula:
                rec["status"] = "CANONICAL_SYNTHESIS_UNAVAILABLE"
                rec["translated"] = {}
                rec["translation_failures"] = {}
            else:
                applied = pg.apply_program(canon_formula, g)
                rec["status"] = "TRANSLATED" if not applied["failures"] else "TRANSLATION_FAILURE"
                rec["translated"] = applied["formulas"]
                rec["translation_failures"] = applied["failures"]
                p1_formulas.update(applied["formulas"])
            group_records.append(rec)
        for m in members:
            if m not in grouped:
                p1_formulas[addr(m)] = p0_formulas.get(addr(m))

        rec = {
            "unit": u, "seed_formula": formula,
            "seed_outcome": outcome_of(seed_session) if formula is None else "PROPOSED",
            "seed_reused_from": seed_session.get("reused_from"),
            "closure_status": closure_status,
            "members": [addr(m) for m in members], "member_cells": [list(m) for m in members],
            "program_groups": group_records, "group_refusals": refused,
            "members_in_a_group": sorted(addr(m) for m in grouped),
            "members_not_in_any_group": sorted(addr(m) for m in members if m not in grouped),
            "P0_formulas": p0_formulas, "P0_outcomes": p0_outcomes,
            "P1_formulas": p1_formulas,
            "P0_model_calls": len(members), "P1_model_calls": len(group_records)
                              + len([m for m in members if m not in grouped]),
            "input_tokens_after": spent(),
        }
        old.write(out_path, rec)
        results.append(rec)
        print(json.dumps({"pass": "unit", "task": u["task"], "seed": u["seed"],
                          "members": len(members), "groups": len(group_records),
                          "grouped_members": len(grouped),
                          "P0_calls": rec["P0_model_calls"], "P1_calls": rec["P1_model_calls"],
                          "spent": spent()}), flush=True)
    reused = sorted({(r["unit"]["task"], a) for r in results
                     for a in list(r["P0_formulas"]) + [r["unit"]["seed"]]})
    old.write(OUT / "arms.json", {"limits": LIMITS, "n_units": len(results),
                                  "units": results,
                                  "new_input_tokens": spent(),
                                  "phase_b_sessions_reused_tokens": _tokens_in(P.OUT / "sessions"),
                                  "distinct_cells_executed": len(reused)})
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run"])
    ap.parse_args()
    run()
