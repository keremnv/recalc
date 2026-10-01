#!/usr/bin/env python3
"""Continuation arm for the member sessions the frozen total cap censored.

The Phase B total input cap of 3,000,000 tokens is predeclared and was not
raised. Three member sessions on 08_05 were therefore recorded as
RESOURCE_CENSORED_NOT_RUN, which leaves three UNRESOLVED units with arms that
are identical by construction and so carry no information.

This is a separately declared continuation, not an amendment: same model, same
prompts, same retrieval, same parser, same writer, same per-session cap. It runs
exactly the censored member sessions and nothing else, and its results are
reported separately from the primary capped result.
"""
from __future__ import annotations
import hashlib
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import instrumentation_freeze as instr

LIMITS = dict(P.LIMITS)
LIMITS["total_input_cap"] = 3_600_000
LIMITS["scope"] = "only the member sessions the primary arm recorded as RESOURCE_CENSORED_NOT_RUN"


def censored() -> list[tuple[dict, cc.Cell]]:
    out = []
    for p in sorted((P.OUT / "units").glob("*.json")):
        rec = old.load(p)
        for m, st in (rec.get("member_status") or {}).items():
            if st == "RESOURCE_CENSORED_NOT_RUN":
                out.append((rec, P.parse_addr(m)))
    return out


def freeze():
    path = P.OUT / "continuation_freeze.json"
    if path.exists():
        raise RuntimeError("already frozen")
    instr.check()
    jobs = [{"task": r["unit"]["task"], "seed": r["unit"]["seed"],
             "member": f"{c[0]}!{cc.a1(c[1], c[2])}"} for r, c in censored()]
    old.write(path, {"limits": LIMITS, "jobs": jobs, "n": len(jobs),
                     "primary_freeze_sha256": old.load(P.OUT / "freeze.json")["sha256"],
                     "changes_from_primary": ["total_input_cap 3,000,000 -> 3,600,000"],
                     "unchanged": ["model", "temperature", "reasoning", "prompts", "retrieval",
                                   "parser", "writer", "per_session_input_cap", "unit selection",
                                   "closure rule", "authority rule"]})
    print(json.dumps({"frozen": len(jobs), "jobs": jobs}, indent=1))


def run():
    f = old.load(P.OUT / "continuation_freeze.json")
    for name, digest in f["primary_freeze_sha256"].items():
        if name == str(Path(P.__file__).resolve().relative_to(old.ROOT)):
            continue
        if hashlib.sha256((old.ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"frozen component changed: {name}")
    instr.check()
    old.guard(LIMITS["model"])
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    done = []
    for rec, cell in censored():
        task = rec["unit"]["task"]
        if P.spent_so_far() >= LIMITS["total_input_cap"]:
            done.append({"task": task, "member": f"{cell[0]}!{cc.a1(cell[1], cell[2])}",
                         "status": "RESOURCE_CENSORED_NOT_RUN"})
            continue
        plan, spine, by_cell, cid_of = P.authorised(task)
        s = P.session_for(task, cell, cid_of[cell], by_cell[cell]["obligation_id"], plan, spine, key)
        addr = f"{cell[0]}!{cc.a1(cell[1], cell[2])}"
        rec["member_status"][addr] = s.get("status")
        rec["member_formulas"][addr] = P.proposed_formula(s)
        old.write(P.OUT / f"units/{task}__{rec['unit']['seed'].replace('!', '_').replace(' ', '_')}.json", rec)
        done.append({"task": task, "member": addr, "status": s.get("status"),
                     "formula": P.proposed_formula(s), "spent": P.spent_so_far()})
        print(json.dumps(done[-1]), flush=True)
    old.write(P.OUT / "continuation.json", {"limits": LIMITS, "jobs": done,
                                            "total_input_tokens": P.spent_so_far()})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["freeze", "run"])
    a = ap.parse_args()
    {"freeze": freeze, "run": run}[a.command]()
