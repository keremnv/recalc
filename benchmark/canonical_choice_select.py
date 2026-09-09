#!/usr/bin/env python3
"""Freeze the runtime candidate mechanism and the Phase B population.

Two decisions are made here, both before any model call, and both recorded so
they can be argued with.

The runtime mechanism is chosen on the aggregate preflight, as §9 directs, not
on whether it rescues a particular group. M0+M1+M2 captures 7 of the 10 groups
whose correct program is reachable at all -- 70% of the M3 ceiling's exact
recall -- for 31 candidates on average against M3's 471. M3 stays where it
belongs: a measurement of what exists, not an interface.

The population is stratified by an evaluator-side availability class, which §11
requires and which means the resulting accuracies are diagnostic contrasts, not
a benchmark rate. Every RECOVERABLE_EXACT group is taken, because "when the
correct program is in the set, is it chosen?" is the question the probe exists
to answer and there are only seven of them.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import instrumentation_freeze as instr
import program_candidate as pcand
import program_candidate_preflight as A
import program_group as pg
import program_group_probe as PC

OUT = A.OUT
RUNTIME_MECHANISM = ("M0", "M1", "M2")
RUNTIME_LABEL = "M0+M1+M2"

GROUPS_MIN, GROUPS_MAX = 12, 18

# How many of each availability class to execute. All RECOVERABLE_EXACT, because
# that is the primary question and the whole supply is seven. Enough
# GENUINELY_NOVEL to see whether synthesis behaves differently when no candidate
# can help, and a smaller SHAPE_ONLY stratum for the binding case.
QUOTA = {"RECOVERABLE_EXACT": 7, "GENUINELY_NOVEL": 6, "RECOVERABLE_SHAPE_ONLY": 3}

MANDATORY = A.MANDATORY

LIMITS = {
    "model": old.MODEL,
    "temperature": 0,
    "reasoning": "medium",
    "retries": 0,
    "max_sql_calls": old.MAX_SQL_CALLS,
    "per_session_input_cap": 400_000,
    "total_input_cap": 4_000_000,
    "arms": {"A0": "CANONICAL_SYNTHESIS", "A1": "CANDIDATE_FIRST_CHOICE"},
    "runtime_candidate_mechanism": RUNTIME_LABEL,
    "candidate_rule": "every candidate is an input-workbook formula translated to the canonical cell",
    "selection_rule": "closed world: SELECT a candidate id, COMPOSE_NEW, or ABSTAIN",
    "retrieval": "frozen; A1 reuses A0's stored working set and re-runs only the synthesis turn",
}

FROZEN = ["benchmark/program_candidate.py",
          "benchmark/program_candidate_preflight.py",
          "benchmark/canonical_choice.py",
          "benchmark/program_group.py",
          "benchmark/execution_unit_probe.py",
          "benchmark/end_to_end_composition_probe.py",
          "benchmark/composition_closure.py"]


def _phase_c_groups() -> dict:
    """Groups Phase C actually executed, keyed by task and canonical member."""
    out = {}
    for p in sorted((PC.OUT / "units").glob("*.json")):
        rec = json.loads(p.read_text())
        for g in rec["program_groups"]:
            out[(rec["unit"]["task"], g["canonical_member"])] = g
    return out


def select() -> dict:
    pre = json.loads((OUT / "candidate_preflight.json").read_text())
    if pre["runtime_mechanism"] != RUNTIME_LABEL:
        raise RuntimeError(f"preflight was scored for {pre['runtime_mechanism']!r}")
    rows = {(r["task"], r["canonical_member"]): r for r in pre["rows"]}
    phase_c = _phase_c_groups()
    survey = {}
    for e in A.population():
        survey.setdefault((e["task"], e["group"]["canonical_member"]), e["group"])

    ordered = sorted(rows, key=lambda k: (k[0], k[1]))
    mandatory = [k for k in MANDATORY if k in rows]
    taken, per_class = [], {}
    for key in mandatory + [k for k in ordered if k not in mandatory]:
        cls = rows[key]["availability_class"]
        if cls not in QUOTA:
            continue
        if key not in mandatory and per_class.get(cls, 0) >= QUOTA[cls]:
            continue
        per_class[cls] = per_class.get(cls, 0) + 1
        taken.append(key)
    if not GROUPS_MIN <= len(taken) <= GROUPS_MAX:
        raise RuntimeError(f"population of {len(taken)} outside [{GROUPS_MIN}, {GROUPS_MAX}]")

    ctx, units = {}, []
    for task, canon_addr in taken:
        if task not in ctx:
            plan, spine, by_cell, cid_of = P.authorised(task)
            ctx[task] = (plan, spine, by_cell, cid_of, pg.input_formulas(task))
        plan, spine, by_cell, cid_of, forms = ctx[task]
        row = rows[(task, canon_addr)]
        # Execute the group Phase C executed where one exists, so the end-to-end
        # numbers tie back to that funnel instead of to a much wider authorised
        # row the earlier probe never actuated.
        group = phase_c.get((task, canon_addr)) or survey[(task, canon_addr)]
        source = "PHASE_C" if (task, canon_addr) in phase_c else "SURVEY"
        canon = tuple(group["canonical_cell"])
        cands = pcand.candidates(group, forms, RUNTIME_MECHANISM)
        units.append({
            "task": task,
            "canonical_member": canon_addr,
            "canonical_cell": list(canon),
            "canonical_cell_id": cid_of.get(canon),
            "obligation_id": (by_cell.get(canon) or {}).get("obligation_id"),
            "operation_id": (by_cell.get(canon) or {}).get("operation_id"),
            "axis": group["axis"],
            "members": group["members"],
            "member_cells": group["member_cells"],
            "n_members": len(group["member_cells"]),
            "execution_group_source": source,
            "availability_class": row["availability_class"],
            "n_candidates": len(cands),
            "candidate_ids": [c["candidate_id"] for c in cands],
            "candidates": cands,
        })
    out = {"runtime_mechanism": RUNTIME_LABEL, "limits": LIMITS,
           "quota": QUOTA, "mandatory": [list(m) for m in MANDATORY],
           "n_units": len(units),
           "by_availability_class": {c: sum(1 for u in units if u["availability_class"] == c)
                                     for c in QUOTA},
           "units": units}
    old.write(OUT / "units.json", out)
    return out


def freeze() -> dict:
    digests = {}
    for name in FROZEN:
        digests[name] = hashlib.sha256((old.ROOT / name).read_bytes()).hexdigest()
    out = {"sha256": digests, "limits": LIMITS,
           "instrumentation_generation": instr.GENERATION,
           "runtime_candidate_mechanism": RUNTIME_LABEL}
    old.write(OUT / "freeze.json", out)
    return out


if __name__ == "__main__":
    s = select()
    freeze()
    print(json.dumps({k: s[k] for k in ("runtime_mechanism", "n_units",
                                        "by_availability_class")}, indent=1))
    for u in s["units"]:
        print(json.dumps({"task": u["task"], "canonical": u["canonical_member"],
                          "class": u["availability_class"], "members": u["n_members"],
                          "source": u["execution_group_source"],
                          "candidates": u["n_candidates"]}))
