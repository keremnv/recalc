#!/usr/bin/env python3
"""Two diagnostics that split the old "synthesis failure" bucket in half.

The operand audit showed that the eleven wrong canonicals of Phase D are not one
failure. Six had every gold operand materialized in the synthesis working set;
five did not. So there are two earliest losses, and each gets its own probe:

  N   -- N0..N3 factorial over the four *clean* construction failures, where all
         four cells rest on identical delivered evidence. Mechanism validation,
         not a rate estimate: the point is to see whether program shape or
         reference binding is the missing choice, and to confirm that N3 (both
         supplied) succeeds. If N3 fails the protocol is broken and nothing else
         in the factorial means anything.

  E   -- oracle evidence completion over the five delivery failures. The stored
         synthesis payload is rebuilt byte for byte and the missing gold operand
         cells are added to the working set with their ordinary materialized
         evidence, exactly as retrieval would have delivered them. Nothing else
         changes: no skeleton, no reference list, no hint of how they combine.

Both arms read gold, so both are oracle interventions. E is *not* a retrieval
improvement and must not be described as one -- it says what a perfect retriever
would have bought, which is the precondition for deciding whether a gold-blind
retrieval mechanism is worth designing at all.

The two RECOVERABLE_EXACT abstentions are deliberately in neither population.
Correct program present, operands present, model declines: that is a commitment
phenomenon, and folding it into "construction" would assume the answer.

Everything below the synthesis turn is frozen. No retrieval runs, no candidate
list is shown, the system prompt is `end_to_end_composition_probe.SYNTHESIS_SYSTEM`
unchanged, and the only edit to the user payload is the named oracle block.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical_choice_probe as probe
import canonical_choice_select as sel
import composition_closure as cc
import end_to_end_composition_probe as old
import execution_unit_probe as P
import execution_unit_score as S
import instrumentation_freeze as instr
import operand_availability_audit as oa
import program_group_preflight as pf
import relational_retrieval_probe as relational
import workbook_grounding as wg

OUT = old.MECHANICAL / "synthesis-decomposition"
ARMS = ("N0", "N1", "N2", "N3")

LIMITS = {
    "model": old.MODEL,
    "temperature": old.TEMPERATURE,
    "reasoning": old.REASONING,
    "retries": 0,
    "max_sql_calls": 0,
    "synthesis_max_tokens": old.SYNTHESIS_MAX_TOKENS,
    "total_input_cap": 2_000_000,
    "retrieval": "none; every payload is rebuilt from a stored working set",
    "oracle": "gold formula is read to build the oracle blocks and the completed evidence",
}

FROZEN = ["benchmark/end_to_end_composition_probe.py",
          "benchmark/operand_availability_audit.py",
          "benchmark/execution_unit_probe.py",
          "benchmark/execution_unit_score.py",
          "benchmark/composition_closure.py"]

SHAPE_NOTE = ("The operator and function skeleton of the correct program, with every "
              "cell or range reference replaced by a numbered hole. Each hole takes "
              "exactly one reference; the same reference may fill more than one hole. "
              "Fill every hole from the workbook evidence and return the completed formula.")
REFS_NOTE = ("The exact set of workbook references the correct program uses, sorted by "
             "address. The program uses each of these at least once and uses nothing "
             "else. How they combine -- the operators, functions and any literals -- is "
             "not given. Return the formula.")


# ------------------------------------------------------------------ payload

def rebuild(task: str, session: dict, raw_task: str, extra_ids: set[str] = frozenset(),
            oracle: dict | None = None) -> tuple[str, dict]:
    """Reconstruct the stored synthesis payload, optionally extended.

    This mirrors `end_to_end_composition_probe.run_target`'s transition dict
    exactly -- same keys, same order, same separators -- so that with no extras
    and no oracle the serialized bytes are the ones that turn actually sent.
    The N0 arm exists to check that claim against the provider's own measured
    prompt_tokens rather than to assert it.
    """
    working = set(session["working_set_ids"]) | set(extra_ids)
    evidence = old.materialize_working_set(task, working)
    transition = {"SYNTHESIS_TRANSITION": old.SYNTHESIS_TRANSITION,
                  "RAW_TASK": raw_task,
                  "TARGET": session["target"],
                  "OBLIGATION": session["obligation"],
                  "WORKING_SET_COUNTS": dict(Counter(x.split(":", 1)[0] for x in working)),
                  "WORKING_SET_ENTITY_IDS": sorted(working),
                  "WORKING_SET_EVIDENCE": evidence}
    if oracle:
        transition.update(oracle)
    return json.dumps(transition, ensure_ascii=False, separators=(",", ":")), transition


# ------------------------------------------------------------------ oracles

_REF = re.compile(r"(?:(?:'[^']*'|[A-Za-z_][A-Za-z0-9_. ]*)!)?\$?[A-Z]{1,3}\$?[0-9]{1,7}"
                  r"(?::\$?[A-Z]{1,3}\$?[0-9]{1,7})?")


def skeleton(formula: str) -> tuple[str, int]:
    """Gold with every reference replaced by <REF n>, left to right.

    Numbering the holes reveals how many references the program takes, which is
    part of the shape and is meant to be revealed. It does not reveal which
    holes share a reference: two holes may legitimately be filled alike.
    """
    n = 0
    out, last = [], 0
    for m in _REF.finditer(formula):
        if m.end() < len(formula) and formula[m.end()] == "(":
            continue
        n += 1
        out.append(formula[last:m.start()])
        out.append(f"<REF{n}>")
        last = m.end()
    out.append(formula[last:])
    return "".join(out), n


def reference_set(formula: str, home_sheet: str) -> list[str]:
    """Distinct gold references, sorted, so slot order leaks nothing."""
    seen = set()
    for op in oa.operands(formula, home_sheet):
        addr = f"{op['start']}:{op['end']}" if op["end"] else op["start"]
        seen.add(f"{op['sheet']}!{addr}")
    return sorted(seen)


def oracle_for(arm: str, formula: str, home_sheet: str) -> dict:
    if arm == "N0":
        return {}
    shape, n = skeleton(formula)
    refs = reference_set(formula, home_sheet)
    block = {}
    if arm in ("N1", "N3"):
        block["ORACLE_PROGRAM_SHAPE"] = {"note": SHAPE_NOTE, "skeleton": shape, "n_holes": n}
    if arm in ("N2", "N3"):
        block["ORACLE_REFERENCE_SET"] = {"note": REFS_NOTE, "references": refs}
    return block


# ------------------------------------------------------------- population

def audit_rows() -> list[dict]:
    return [r for r in old.load(sel.OUT / "operand_availability.json")["units"]
            if r.get("status") == "AUDITED"]


def populations() -> tuple[list[dict], list[dict]]:
    """N: clean construction failures. E: delivery failures. Neither holds the
    two RECOVERABLE_EXACT abstentions -- N excludes them by class, and they have
    no missing operand for E to complete."""
    rows = audit_rows()
    novel_or_shape = ("GENUINELY_NOVEL", "RECOVERABLE_SHAPE_ONLY")
    n = [r for r in rows if not r["correct"] and r["availability_class"] in novel_or_shape
         and r["attribution"] == "PROGRAM_CONSTRUCTION_FAILURE"]
    e = [r for r in rows if not r["correct"] and r["attribution"] == "CONTEXT_DELIVERY_FAILURE"]
    return n, e


def program_key(row: dict) -> str:
    """Independent-program identity, so two columns of one program are not two
    results. `08_04 C68` and `D68` are the same program under translation."""
    import program_group as pg
    return f'{row["task"]}::{pg.formula_a1_shape(row["gold_canonical_formula"])}'


# --------------------------------------------------------------- execution

def session_for(unit: dict):
    name = f"{unit['task']}__{unit['canonical_cell_id'].replace(':', '_')}.json"
    return next(d / name for d in probe.SESSION_DIRS if (d / name).exists())


def units_by_key() -> dict:
    return {(u["task"], u["canonical_member"]): u
            for u in old.load(sel.OUT / "units.json")["units"]}


def spent() -> int:
    total = 0
    for p in (OUT / "calls").glob("*.json"):
        total += old.load(p).get("input_tokens", 0)
    return total


def missing_operand_ids(row: dict, task: str) -> list[str]:
    """Cell ids of the operands the session never materialized."""
    con = oa._conn(task)
    try:
        sheets = oa._sheet_ids(con)
        cells = oa._cell_index(con)
        out = []
        for op in row["operands"]:
            if op["level"] in oa.AVAILABLE:
                continue
            sid = sheets.get(op["reference"].split("!", 1)[0])
            if sid is None:
                continue
            if op["kind"] == "POINT":
                c = cells.get((sid, op["reference"].split("!", 1)[1]))
                if c:
                    out.append(c["cell_id"])
            else:
                a1, a2 = op["reference"].split("!", 1)[1].split(":")
                a, b = cells.get((sid, a1)), cells.get((sid, a2))
                if a and b:
                    out += [r["cell_id"] for r in con.execute(
                        "SELECT cell_id FROM cells WHERE sheet_id=? AND row_idx BETWEEN ? AND ? "
                        "AND col_idx BETWEEN ? AND ?",
                        (sid, min(a["row_idx"], b["row_idx"]), max(a["row_idx"], b["row_idx"]),
                         min(a["col_idx"], b["col_idx"]), max(a["col_idx"], b["col_idx"])))]
        return sorted(set(out))
    finally:
        con.close()


def call(name: str, task: str, session: dict, raw_task: str, gold: str, key: str,
         extra_ids: set[str] = frozenset(), oracle: dict | None = None) -> dict:
    path = OUT / "calls" / f"{name}.json"
    if path.exists():
        return old.load(path)
    user, transition = rebuild(task, session, raw_task, extra_ids, oracle)
    t0 = time.perf_counter()
    resp = old.call_glm(key, old.SYNTHESIS_SYSTEM, user, "librecalc-synthesis-decomposition",
                        old.SYNTHESIS_MAX_TOKENS)
    parsed = old.extract_json_object(resp.get("text", "")) if resp.get("http_ok") else None
    usage = resp.get("usage") or {}
    at_budget = usage.get("completion_tokens") == old.SYNTHESIS_MAX_TOKENS
    truncated = bool(resp.get("http_ok") and at_budget and parsed is None)
    fake = {"synthesis": {"parsed": parsed}, "cell_id": session["target"]["cell_id"]}
    formula = P.proposed_formula(fake)
    rec = {"name": name, "task": task,
           "payload_sha256": hashlib.sha256(user.encode()).hexdigest(),
           "payload_chars": len(user),
           "payload_token_estimate": wg.token_estimate(user),
           "oracle_keys": sorted(oracle or {}),
           "n_extra_entity_ids": len(extra_ids),
           "request": {"model": old.MODEL, "temperature": old.TEMPERATURE,
                       "reasoning": old.REASONING, "max_tokens": old.SYNTHESIS_MAX_TOKENS,
                       "system_sha256": hashlib.sha256(old.SYNTHESIS_SYSTEM.encode()).hexdigest()},
           "response": resp, "parsed": parsed, "formula": formula,
           "status": (parsed or {}).get("status"),
           "truncation_class": ("TRUNCATED_NO_CONTENT" if truncated and not (resp.get("text") or "")
                                else "TRUNCATED_AT_BUDGET" if truncated else None),
           "failure_class": None if resp.get("http_ok") else "MODEL_ACCESS_FAILURE",
           "input_tokens": int(usage.get("prompt_tokens") or 0),
           "output_tokens": int(usage.get("completion_tokens") or 0),
           "exact": S._same(formula, gold),
           "gold": gold,
           "wall_seconds": round(time.perf_counter() - t0, 3)}
    old.write(path, rec)
    old.write(OUT / "payloads" / f"{name}.json", transition)
    return rec


def run(arms=ARMS, do_e=True):
    instr.check()
    old.guard(LIMITS["model"])
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    old.write(OUT / "run_manifest.json",
              {"limits": LIMITS,
               "instrumentation_generation": instr.GENERATION,
               "frozen_sha256": {n: hashlib.sha256((old.ROOT / n).read_bytes()).hexdigest()
                                 for n in FROZEN},
               "synthesis_system_sha256": hashlib.sha256(old.SYNTHESIS_SYSTEM.encode()).hexdigest()})

    N, E = populations()
    units = units_by_key()
    plans, results = {}, {"N": [], "E": []}

    def ctx(task):
        if task not in plans:
            plans[task] = P.authorised(task)[0]["compiler"]["raw_task"]
        return plans[task]

    for row in N:
        u = units[(row["task"], row["canonical_member"])]
        s = old.load(session_for(u))
        gold = row["gold_canonical_formula"]
        home = u["canonical_cell"][0]
        for arm in arms:
            if spent() >= LIMITS["total_input_cap"]:
                print(json.dumps({"stop": "TOTAL_INPUT_CAP", "spent": spent()}), flush=True)
                break
            tag = f'{arm}__{row["task"]}__{u["canonical_cell_id"].replace(":", "_")}'
            rec = call(tag, row["task"], s, ctx(row["task"]), gold, key,
                       oracle=oracle_for(arm, gold, home))
            rec.update({"arm": arm, "canonical_member": row["canonical_member"],
                        "availability_class": row["availability_class"],
                        "program_key": program_key(row),
                        "stored_synthesis_input_tokens": s.get("synthesis_input_tokens")})
            results["N"].append(rec)
            print(json.dumps({k: rec[k] for k in
                              ("arm", "task", "canonical_member", "status", "formula",
                               "exact", "input_tokens")}), flush=True)

    if do_e:
        for row in E:
            u = units[(row["task"], row["canonical_member"])]
            s = old.load(session_for(u))
            gold = row["gold_canonical_formula"]
            extra = set(missing_operand_ids(row, row["task"]))
            if spent() >= LIMITS["total_input_cap"]:
                print(json.dumps({"stop": "TOTAL_INPUT_CAP", "spent": spent()}), flush=True)
                break
            tag = f'E1__{row["task"]}__{u["canonical_cell_id"].replace(":", "_")}'
            rec = call(tag, row["task"], s, ctx(row["task"]), gold, key, extra_ids=extra)
            rec.update({"arm": "E1", "canonical_member": row["canonical_member"],
                        "availability_class": row["availability_class"],
                        "program_key": program_key(row),
                        "completed_operand_ids": sorted(extra),
                        "E0_formula": row["A0_formula"],
                        "E0_exact": row["A0_canonical_exact"],
                        "stored_synthesis_input_tokens": s.get("synthesis_input_tokens")})
            results["E"].append(rec)
            print(json.dumps({k: rec[k] for k in
                              ("arm", "task", "canonical_member", "status", "formula",
                               "exact", "E0_formula", "input_tokens")}), flush=True)

    old.write(OUT / "results.json",
              {"limits": LIMITS, "population_N": [r["canonical_member"] for r in N],
               "population_E": [r["canonical_member"] for r in E],
               "input_tokens": spent(), **results})
    return results


if __name__ == "__main__":
    run()
