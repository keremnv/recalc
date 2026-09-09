#!/usr/bin/env python3
"""The A1 arm: choose one canonical program from a closed-world candidate set.

Phase C removed the harness's repeated asking. What is left is a single
stochastic decision per ProgramGroup, and this module changes only that
decision's interface. Retrieval is not re-run: the arm reuses the stored
working set of the very session A0 used, so the two arms differ in exactly one
turn -- the synthesis call -- and in exactly one way: A1 is shown the
deterministic ProgramCandidate set and may answer by reference.

The model may select a candidate, compose a genuinely new formula, or abstain.
It may not invent a candidate id, and a selected candidate is used verbatim --
the harness substitutes the stored translated formula and ignores any text the
model writes alongside it. That is what makes SELECT a closed-world act rather
than a suggestion.

Nothing about correctness, gold, ranking or a recommendation is exposed.
Candidates are serialized in their frozen id order, which is derived from
formula text, so the ordering carries no signal about which one is better.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
import relational_retrieval_probe as relational

CHOICE_SYSTEM = relational.sql_strong_context("", {}) + """

ARCHITECTURE V1.3 CANONICAL PROGRAM CHOICE:
Retrieval is over. No further query will be executed. The accumulated working
set below is the complete evidence available for this target.

You are choosing ONE program for this cell. The workbook already contains
formulas; every PROGRAM_CANDIDATE below is one of them, rewritten by the
harness so that it reads correctly at this exact target cell. Existing patterns
are evidence, not correctness guarantees.

Choose exactly one of:

  SELECT       one candidate implements the requested computation. Return its
               candidate_id. The harness uses that candidate's formula exactly
               as printed; you cannot edit it.
  COMPOSE_NEW  no candidate implements the requested computation, so a new
               formula is required. Return it.
  ABSTAIN      the evidence does not determine the answer.

Do not invent a candidate_id. Do not invent workbook cells, sheets, labels or
relationships.

Return exactly one JSON object and nothing else:
{"target_id":"cell:...","decision":"SELECT"|"COMPOSE_NEW"|"ABSTAIN",
 "candidate_id":"K012"|null,"formula":"=..."|null}
"""

OUTCOMES = ("SELECTED_EXISTING", "COMPOSED_NEW", "ABSTAIN",
            "INVALID_CANDIDATE_ID", "WRONG_RESPONSE_SCHEMA", "INVALID_OUTPUT")


def unwrap(parsed):
    """Undo a single-key envelope holding the real object as a JSON string.

    Instrumentation defect 10: the model sometimes answers correctly but wraps
    the object, as {"answer": "{...}"}. Reading the envelope as the answer turns
    a well-formed decision into a parse failure and charges it to the model.
    The unwrap is deliberately narrow -- one key, a string value, and that
    string must itself parse to an object -- so it cannot invent structure that
    the response did not contain.
    """
    if not isinstance(parsed, dict) or "decision" in parsed:
        return parsed
    if len(parsed) != 1:
        return parsed
    (value,) = parsed.values()
    if not isinstance(value, str):
        return parsed
    try:
        inner = json.loads(value)
    except Exception:
        return parsed
    return inner if isinstance(inner, dict) else parsed


def candidate_block(candidates: list[dict]) -> list[dict]:
    """What the model sees. No correctness, no rank, no recommendation."""
    return [{"candidate_id": c["candidate_id"],
             "formula_at_target": c["translated_formula_at_canonical"],
             "relative_program": c["fingerprint"],
             "source_cell": c["source_cell_id"],
             "why_retrieved": c["source_relation"],
             "other_sources": max(0, c["n_sources"] - 1)}
            for c in candidates]


def payload(task: str, session: dict, raw_task: str, candidates: list[dict]) -> dict:
    """Rebuild A0's synthesis input, then add the candidate set and nothing else."""
    task_target = session["target"]
    working = sorted(session["working_set_ids"])
    from collections import Counter
    return {"SYNTHESIS_TRANSITION": old.SYNTHESIS_TRANSITION,
            "RAW_TASK": raw_task,
            "TARGET": task_target,
            "OBLIGATION": session["obligation"],
            "WORKING_SET_COUNTS": dict(Counter(x.split(":", 1)[0] for x in working)),
            "WORKING_SET_ENTITY_IDS": working,
            "WORKING_SET_EVIDENCE": old.materialize_working_set(task, set(working)),
            "PROGRAM_CANDIDATES": candidate_block(candidates)}


def classify(parsed: dict | None, candidates: list[dict]) -> tuple[str, str | None, str | None]:
    """(outcome, candidate_id, formula) under closed-world discipline."""
    parsed = unwrap(parsed)
    if not isinstance(parsed, dict):
        return "INVALID_OUTPUT", None, None
    ids = {c["candidate_id"]: c for c in candidates}
    decision = str(parsed.get("decision") or "").upper()
    cid = parsed.get("candidate_id")
    if decision == "SELECT":
        if cid not in ids:
            return "INVALID_CANDIDATE_ID", cid, None
        return "SELECTED_EXISTING", cid, ids[cid]["translated_formula_at_canonical"]
    if decision == "COMPOSE_NEW":
        f = parsed.get("formula")
        if not isinstance(f, str) or not f.strip():
            return "INVALID_OUTPUT", None, None
        return "COMPOSED_NEW", None, f.strip()
    if decision == "ABSTAIN":
        return "ABSTAIN", None, None
    # The A0 schema, returned to the A1 protocol: a formula with no declared
    # decision. It is a real answer, but not one this arm asked for, so it is
    # named rather than silently promoted to COMPOSE_NEW.
    if "status" in parsed or (parsed.get("formula") and not decision):
        return "WRONG_RESPONSE_SCHEMA", None, (parsed.get("formula") or None)
    return "INVALID_OUTPUT", None, None


def choose(task: str, session: dict, raw_task: str, candidates: list[dict], key: str) -> dict:
    """One synthesis turn on A0's own working set, with the candidate set added."""
    body = json.dumps(payload(task, session, raw_task, candidates),
                      ensure_ascii=False, separators=(",", ":"))
    response = old.call_glm(key, CHOICE_SYSTEM, body,
                            "librecalc-canonical-choice", old.SYNTHESIS_MAX_TOKENS)
    parsed = old.extract_json_object(response.get("text", "")) if response.get("http_ok") else None
    usage = response.get("usage") or {}
    at_budget = usage.get("completion_tokens") == old.SYNTHESIS_MAX_TOKENS
    truncated = bool(response.get("http_ok") and at_budget and parsed is None)
    truncation_class = ("TRUNCATED_NO_CONTENT" if truncated and not (response.get("text") or "")
                        else "TRUNCATED_AT_BUDGET" if truncated else None)
    if not response.get("http_ok"):
        outcome, cid, formula, failure = "INVALID_OUTPUT", None, None, "MODEL_ACCESS_FAILURE"
    elif truncation_class:
        outcome, cid, formula, failure = "INVALID_OUTPUT", None, None, truncation_class
    else:
        outcome, cid, formula = classify(parsed, candidates)
        failure = None
    return {"outcome": outcome, "candidate_id": cid, "formula": formula,
            "failure_class": failure, "truncation_class": truncation_class,
            "n_candidates": len(candidates),
            "candidate_ids": [c["candidate_id"] for c in candidates],
            "response": response, "parsed": parsed,
            "choice_input_tokens": int(usage.get("prompt_tokens") or 0),
            "choice_output_tokens": int(usage.get("completion_tokens") or 0)}
