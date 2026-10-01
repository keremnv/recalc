#!/usr/bin/env python3
"""Phase B: does the C1 closure survive when seeded by the model's own proposal?

Architectural claim under test:

    Edit Plans establish edit authority.
    Proposal-seeded input-side dependency closure establishes execution
    coordination.

An ExecutionUnit therefore never widens authority. Its candidate members are the
intersection of the C1 closure with the cells the generated Edit Plan already
authorises, so a cell that is merely a precedent is not editable.

The two arms share the seed session byte for byte: B1 runs the identical seed
call and only adds sessions for the unit's other authorised members. The arms
differ in exactly one thing, whether coordinated members were solved too.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import edit_plan_replication as rep
import instrumentation_freeze as instr

OUT = old.MECHANICAL / "execution-unit-probe"
PLANS = rep.OUT / "phase_b"
CLOSURE = ccf.OUT

# Predeclared. 07_03 and 14_05 are excluded because their gold edit sets fail
# apparatus validation, so no causal claim can rest on them.
QUARANTINED = ["07_03", "14_05"]
LIMITS = {"model": "z-ai/glm-5.3-flash", "temperature": 0, "reasoning": "medium", "retries": 0,
          "max_sql_calls": old.MAX_SQL_CALLS, "per_session_input_cap": 400_000,
          "total_input_cap": 3_000_000, "units_min": 8, "units_max": 12,
          "synthesis_mode": "PER_CELL_SYNTHESIS",
          "closure_rule": "C1 input-side OFFSET-aware, seeded by the model's proposed formula",
          "authority_rule": "members must already be authorised by the generated Edit Plan"}


def cell_of(spine, cid):
    a = old.target_address(spine, cid)
    return (a["sheet"], a["row"], a["col"]), a


def parse_addr(s: str) -> cc.Cell:
    sheet, ref = s.rsplit("!", 1)
    m = re.fullmatch(r"([A-Za-z]{1,3})([0-9]+)", ref)
    return (sheet, int(m.group(2)), cc.col_index(m.group(1)))


def authorised(task: str):
    """Cells the generated Edit Plan authorises, with the operation that did so."""
    d = old.load(PLANS / f"{task}.json")
    spine = old._load_spine(task)
    by_cell, cid_of = {}, {}
    for op in (d.get("expansion") or {}).get("operations", []):
        for cid in op["cell_ids"]:
            try:
                c, _ = cell_of(spine, cid)
            except Exception:
                continue
            by_cell.setdefault(c, {"operation_id": op["operation_id"], "obligation_id": op["obligation_id"],
                                   "operation_kind": op.get("operation_kind")})
            cid_of[c] = cid
    return d, spine, by_cell, cid_of


def select():
    report = old.load(CLOSURE / "phase_a_report.json")
    units = []
    for t in report["targets"]:
        if t["task"] in QUARANTINED:
            continue
        d, spine, by_cell, cid_of = authorised(t["task"])
        seed = parse_addr(t["address"])
        if seed not in by_cell:
            continue  # the plan never authorised this cell; it cannot be a unit
        units.append({"task": t["task"], "seed": t["address"], "seed_cell": list(seed),
                      "seed_cell_id": cid_of[seed], **by_cell[seed],
                      "phase_a_regime": t["regime"], "phase_a_n_U": t["n_U"],
                      "phase_a_isolated_gain": t["isolated_gain"],
                      "phase_a_closure_gain": t["closure_gain"], "cone": t["cone"]})
    order = {"COMPOSITION_DEPENDENT_EDIT": 0, "UNRESOLVED": 1, "INDEPENDENT_EDIT": 2}
    units.sort(key=lambda u: (order.get(u["phase_a_regime"], 3), u["task"], u["seed"]))
    chosen, per_task = [], defaultdict(int)
    for u in units:
        if len(chosen) >= LIMITS["units_max"]:
            break
        if per_task[u["task"]] >= 3:
            continue
        chosen.append(u)
        per_task[u["task"]] += 1
    payload = {"limits": LIMITS, "quarantined": QUARANTINED, "units": chosen,
               "regimes": {k: sum(1 for u in chosen if u["phase_a_regime"] == k)
                           for k in ("COMPOSITION_DEPENDENT_EDIT", "UNRESOLVED", "INDEPENDENT_EDIT")},
               "sha256": hashlib.sha256(json.dumps(chosen, sort_keys=True).encode()).hexdigest()}
    old.write(OUT / "units.json", payload)
    print(json.dumps({"n": len(chosen), "regimes": payload["regimes"]}, indent=1))
    for u in chosen:
        print(f"  {u['task']} {u['seed']:32} {u['phase_a_regime']:28} U={u['phase_a_n_U']} cone={u['cone']}")


def freeze():
    if (OUT / "freeze.json").exists():
        raise RuntimeError("already frozen")
    instr.check()
    units = old.load(OUT / "units.json")
    paths = [Path(__file__), Path(old.__file__), Path(cc.__file__), Path(ccf.__file__)]
    old.write(OUT / "freeze.json", {
        "limits": LIMITS, "units_sha256": units["sha256"], "instrumentation": instr.check()["sha256"],
        "sha256": {str(p.relative_to(old.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "arms": {"B0": "seed target solved and actuated alone",
                 "B1": "identical seed session, plus sessions for the unit's other authorised members"},
        "shared_seed_session": True,
        "closure_seeded_from": "the model's parsed proposal, never gold",
    })
    print("frozen")


def proposal_precedents(formula: str, seed: cc.Cell) -> set[cc.Cell]:
    """Direct precedents of the model's own proposed formula. Never gold."""
    from integrated_hybrid_synthesis_probe import eval_tools as et
    out: set[cc.Cell] = set()
    led: list = []
    try:
        refs = et._ref_records(formula, seed[0], seed[1], seed[2])
    except Exception:
        return out
    for ref in refs.get("points", []) + refs.get("ranges", []):
        m1 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", ref.get("start") or "")
        if not m1:
            continue
        r1, c1 = int(m1.group(2)), cc.col_index(m1.group(1))
        if ref.get("is_range"):
            m2 = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([0-9]+)", ref.get("end") or ref["start"])
            if not m2:
                continue
            r2, c2 = int(m2.group(2)), cc.col_index(m2.group(1))
            out |= cc._expand(ref["sheet"], min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2), led)
        else:
            out.add((ref["sheet"], r1, c1))
    return out


def session_for(task, cell, cid, obligation_id, plan, spine, key):
    """One frozen synthesis session for one authorised cell."""
    path = OUT / f"sessions/{task}__{cid.replace(':', '_')}.json"
    if path.exists():
        return old.load(path)
    ob = next(o for o in plan["compiler"]["obligations"] if o["id"] == obligation_id)
    target = old.target_address(spine, cid)
    info = old.input_cell_info(task, target["sheet"], target["address"])
    target.update({"target_id": cid, "current_input_content": info["raw_value"], "current_input_kind": info["kind"]})
    t0 = time.perf_counter()
    try:
        s = old.run_target(task, plan["compiler"]["raw_task"], ob, target,
                           plan["grounding"]["packets"][obligation_id], spine, key,
                           synthesis_system=old.SYNTHESIS_SYSTEM,
                           retrieval_system=old.DELTA_RETRIEVAL_SYSTEM,
                           delta_state=True, session_input_cap=LIMITS["per_session_input_cap"])
    except Exception as exc:
        s = {"status": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}", "target": target}
    s["wall_seconds"] = time.perf_counter() - t0
    s["cell"] = list(cell)
    s["cell_id"] = cid
    # Retention is a standing requirement: raw body, usage, parser result and
    # truncation status must all survive for every call.
    resp = (s.get("synthesis") or {}).get("response") or {}
    s["audit"] = {"raw_text_len": len(resp.get("text") or ""), "usage": resp.get("usage"),
                  "parsed": (s.get("synthesis") or {}).get("parsed"),
                  "truncated": s.get("synthesis_truncated"),
                  "failure_class": s.get("failure_class")}
    old.write(path, s)
    return s


def proposed_formula(session) -> str | None:
    p = (session.get("synthesis") or {}).get("parsed") or {}
    f = p.get("formula") if p.get("status") == "PROPOSED" else None
    if isinstance(f, str) and f.startswith("=") and p.get("target_id") == session.get("cell_id"):
        return f
    return None


def spent_so_far() -> int:
    if not (OUT / "sessions").exists():
        return 0
    tot = 0
    for p in (OUT / "sessions").glob("*.json"):
        d = old.load(p)
        tot += d.get("retrieval_input_tokens", 0) + d.get("synthesis_input_tokens", 0)
    return tot


def run():
    f = old.load(OUT / "freeze.json")
    me = str(Path(__file__).resolve().relative_to(old.ROOT))
    drift = {}
    for name, digest in f["sha256"].items():
        now = hashlib.sha256((old.ROOT / name).read_bytes()).hexdigest()
        if now == digest:
            continue
        # Reporting code may be added to this module after the freeze; that is
        # recorded, never silent. Any other component changing invalidates the arm.
        if name != me:
            raise RuntimeError(f"frozen component changed: {name}")
        drift[name] = now
    old.write(OUT / "run_manifest.json", {"frozen_sha256": f["sha256"], "runner_drift": drift})
    instr.check()
    old.guard(LIMITS["model"])
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    units = old.load(OUT / "units.json")["units"]

    def unit_path(u):
        return OUT / f"units/{u['task']}__{u['seed'].replace('!', '_').replace(' ', '_')}.json"

    # Pass 1 solves every seed before any member, so that if the declared total
    # cap censors, it censors coordination (B1) and never the B0 baseline.
    ctx, seeds = {}, {}
    for u in units:
        if u["task"] not in ctx:
            ctx[u["task"]] = P = authorised(u["task"])
            ctx[u["task"]] = (P[0], P[1], P[2], P[3], cc.graph_input_plus_offset(u["task"])[0])
        plan, spine, by_cell, cid_of, g_off = ctx[u["task"]]
        if spent_so_far() >= LIMITS["total_input_cap"]:
            seeds[u["seed"]] = {"status": "RESOURCE_CENSORED_NOT_RUN"}
            continue
        seeds[u["seed"]] = session_for(u["task"], tuple(u["seed_cell"]), u["seed_cell_id"],
                                       u["obligation_id"], plan, spine, key)
        print(json.dumps({"pass": "seed", "task": u["task"], "seed": u["seed"],
                          "status": seeds[u["seed"]].get("status"),
                          "formula": proposed_formula(seeds[u["seed"]]),
                          "spent": spent_so_far()}), flush=True)

    results = []
    for u in units:
        out_path = unit_path(u)
        plan, spine, by_cell, cid_of, g_off = ctx[u["task"]]
        seed = tuple(u["seed_cell"])
        seed_session = seeds[u["seed"]]
        formula = proposed_formula(seed_session)
        auth = set(by_cell)
        members, closure_status = [], "NO_PROPOSAL"
        if formula:
            precs = proposal_precedents(formula, seed)
            closure = set()
            for pcell in precs:
                closure |= cc.ancestors_within(pcell, g_off, auth)
            closure |= (precs & auth)
            closure.discard(seed)
            members = sorted(closure)
            closure_status = "CLOSURE_EMPTY" if not members else "CLOSURE_FOUND"
        member_sessions = []
        for m in members:
            if spent_so_far() >= LIMITS["total_input_cap"]:
                member_sessions.append({"cell": list(m), "status": "RESOURCE_CENSORED_NOT_RUN"})
                continue
            member_sessions.append(session_for(u["task"], m, cid_of[m], by_cell[m]["obligation_id"],
                                               plan, spine, key))
        rec = {"unit": u, "seed_cell_id": u["seed_cell_id"],
               "seed_formula": formula, "seed_status": seed_session.get("status"),
               "seed_failure_class": seed_session.get("failure_class"),
               "seed_parsed_status": ((seed_session.get("synthesis") or {}).get("parsed") or {}).get("status"),
               "closure_status": closure_status,
               "members": [f"{m[0]}!{cc.a1(m[1], m[2])}" for m in members],
               "member_cells": [list(m) for m in members],
               "member_status": {f"{m[0]}!{cc.a1(m[1], m[2])}": s.get("status")
                                 for m, s in zip(members, member_sessions)},
               "member_formulas": {f"{m[0]}!{cc.a1(m[1], m[2])}": proposed_formula(s)
                                   for m, s in zip(members, member_sessions)},
               "input_tokens_after": spent_so_far()}
        old.write(out_path, rec)
        results.append(rec)
        print(json.dumps({"pass": "unit", "task": u["task"], "seed": u["seed"],
                          "regime": u["phase_a_regime"], "proposal": bool(formula),
                          "closure": closure_status, "n_members": len(members),
                          "spent": spent_so_far()}), flush=True)
    old.write(OUT / "arms.json", {"limits": LIMITS, "n_units": len(results), "units": results,
                                  "total_input_tokens": spent_so_far()})
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["select", "freeze", "run"])
    a = ap.parse_args()
    {"select": select, "freeze": freeze, "run": run}[a.command]()
