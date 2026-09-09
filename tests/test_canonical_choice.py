"""Tests for closed-world ProgramCandidate generation and canonical choice.

The properties that matter are the ones that keep the choice honest: every
candidate comes from a real workbook formula, the list leaks nothing about which
one is right, and a selection is executed verbatim rather than paraphrased.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import canonical_choice as cch
import program_candidate as pc

S = "Sheet1"


def _forms(spec):
    return {(S, r, c): f for (r, c), f in spec.items()}


def _group(members, canonical, axis="ROW", witness=None):
    return {"axis": axis, "member_cells": [list(m) for m in members],
            "members": [f"{m[0]}!{m[1]}:{m[2]}" for m in members],
            "canonical_cell": list(canonical),
            "canonical_member": f"{canonical[0]}!{canonical[1]}:{canonical[2]}",
            "witness": witness or {}}


# ------------------------------------------------------------- generation

def test_a_candidate_always_comes_from_a_real_workbook_formula():
    forms = _forms({(5, 3): "=A5+B5", (5, 4): "=B5+C5"})
    g = _group([(S, 6, 3), (S, 6, 4)], (S, 6, 3))
    out = pc.m2(g, forms)
    assert out
    for c in out:
        assert tuple(c["source_cell"]) in forms
        assert c["source_formula"] == forms[tuple(c["source_cell"])]


def test_the_group_s_own_line_is_a_candidate_source():
    """A row already holding the program at other columns is the best evidence."""
    forms = _forms({(6, 1): "=A1*2", (6, 2): "=B1*2"})
    g = _group([(S, 6, 5), (S, 6, 6)], (S, 6, 5))
    out = pc.m2(g, forms)
    assert [c["translated_formula_at_canonical"] for c in out] == ["=E1*2"]


def test_a_line_holding_two_programs_contributes_its_regular_part():
    forms = _forms({(4, 1): "=A1+1", (4, 2): "=B1+1", (4, 3): "=ZZ9", (4, 4): "=D1+1"})
    g = _group([(S, 5, 1), (S, 5, 2)], (S, 5, 1))
    texts = {c["translated_formula_at_canonical"] for c in pc.m2(g, forms)}
    assert "=A2+1" in texts


def test_m1_requires_the_line_to_cover_every_group_coordinate():
    forms = _forms({(4, 1): "=A1+1", (4, 2): "=B1+1"})
    covered = _group([(S, 5, 1), (S, 5, 2)], (S, 5, 1))
    uncovered = _group([(S, 5, 1), (S, 5, 2), (S, 5, 3)], (S, 5, 1))
    assert pc.m1(covered, forms)
    assert pc.m1(uncovered, forms) == []


def test_a_source_that_cannot_legally_translate_is_not_a_candidate():
    forms = _forms({(5, 1): "=A2", (5, 2): "=B2"})
    g = _group([(S, 1, 1), (S, 1, 2)], (S, 1, 1))
    assert pc.m2(g, forms) == []


# ---------------------------------------------------------------- dedupe

def test_identical_translated_formulas_collapse_and_keep_provenance():
    # Two different lines carrying the same relative program: one candidate, two sources.
    forms = _forms({(4, 1): "=A1+1", (4, 2): "=B1+1", (3, 1): "=A0+1", (3, 2): "=B0+1"})
    g = _group([(S, 5, 1), (S, 5, 2)], (S, 5, 1))
    out = pc.candidates(g, forms)
    texts = [c["translated_formula_at_canonical"] for c in out]
    assert len(texts) == len(set(texts))
    assert all(c["n_sources"] == len(c["provenance"]) for c in out)


def test_candidate_ids_are_stable_and_ordered_by_formula_text():
    forms = _forms({(4, 1): "=A1+1", (4, 2): "=B1+1", (2, 1): "=A1*9", (2, 2): "=B1*9"})
    g = _group([(S, 5, 1), (S, 5, 2)], (S, 5, 1))
    first = pc.candidates(g, forms)
    again = pc.candidates(g, forms)
    assert [c["candidate_id"] for c in first] == [c["candidate_id"] for c in again]
    assert [c["candidate_id"] for c in first] == sorted(c["candidate_id"] for c in first)


def test_the_model_is_shown_no_correctness_and_no_ranking():
    forms = _forms({(4, 1): "=A1+1", (4, 2): "=B1+1"})
    g = _group([(S, 5, 1), (S, 5, 2)], (S, 5, 1))
    block = cch.candidate_block(pc.candidates(g, forms))
    allowed = {"candidate_id", "formula_at_target", "relative_program",
               "source_cell", "why_retrieved", "other_sources"}
    for entry in block:
        assert set(entry) == allowed


# ------------------------------------------------------------ closed world

def test_a_selection_is_executed_verbatim_not_paraphrased():
    cands = [{"candidate_id": "K001", "translated_formula_at_canonical": "=A1+B1"}]
    out = cch.classify({"decision": "SELECT", "candidate_id": "K001",
                        "formula": "=SOMETHING_ELSE()"}, cands)
    assert out == ("SELECTED_EXISTING", "K001", "=A1+B1")


def test_an_invented_candidate_id_is_refused_rather_than_guessed():
    cands = [{"candidate_id": "K001", "translated_formula_at_canonical": "=A1"}]
    assert cch.classify({"decision": "SELECT", "candidate_id": "K404"}, cands)[0] \
        == "INVALID_CANDIDATE_ID"


def test_compose_new_and_abstain_are_distinct_outcomes():
    assert cch.classify({"decision": "COMPOSE_NEW", "formula": "=B2*2"}, [])[0] == "COMPOSED_NEW"
    assert cch.classify({"decision": "ABSTAIN"}, [])[0] == "ABSTAIN"


def test_compose_new_without_a_formula_is_not_an_answer():
    assert cch.classify({"decision": "COMPOSE_NEW", "formula": ""}, [])[0] == "INVALID_OUTPUT"


# ------------------------------------------------- instrumentation repairs

def test_a_decision_wrapped_in_an_envelope_is_not_charged_to_the_model():
    """Defect 10: {"answer": "{...}"} was read as though the envelope were the answer."""
    cands = [{"candidate_id": "K001", "translated_formula_at_canonical": "=A1"}]
    parsed = {"answer": '{"decision":"SELECT","candidate_id":"K001"}'}
    assert cch.classify(parsed, cands) == ("SELECTED_EXISTING", "K001", "=A1")


def test_the_unwrap_cannot_invent_structure():
    assert cch.unwrap({"answer": "not json"}) == {"answer": "not json"}
    assert cch.unwrap({"a": 1, "b": 2}) == {"a": 1, "b": 2}
    assert cch.unwrap({"decision": "ABSTAIN"}) == {"decision": "ABSTAIN"}
    assert cch.unwrap({"answer": '["a","b"]'}) == {"answer": '["a","b"]'}


def test_the_previous_protocol_s_schema_is_named_not_promoted():
    """Defect 11: a formula with no declared decision is a real answer, but not this one."""
    out = cch.classify({"target_id": "x", "status": "PROPOSED", "formula": "=J46+J48"}, [])
    assert out == ("WRONG_RESPONSE_SCHEMA", None, "=J46+J48")


# --------------------------------------------------------- run invariants

def _probe():
    import canonical_choice_select as sel
    return sel


def test_every_selected_formula_is_a_candidate_formula_verbatim():
    sel = _probe()
    import end_to_end_composition_probe as old
    path = sel.OUT / "formula_scores.json"
    if not path.exists():
        pytest.skip("probe has not run yet")
    units = {(u["task"], u["canonical_member"]): u
             for u in old.load(sel.OUT / "units.json")["units"]}
    for r in old.load(path)["units"]:
        if r["A1_outcome"] != "SELECTED_EXISTING":
            continue
        cands = {c["candidate_id"]: c for c in units[(r["task"], r["canonical_member"])]["candidates"]}
        assert r["A1_candidate_id"] in cands
        assert r["A1_formula"] == cands[r["A1_candidate_id"]]["translated_formula_at_canonical"]


def test_each_arm_writes_its_canonical_formula_at_the_canonical_cell():
    """Whatever was chosen, translation must put it back where it was chosen for."""
    sel = _probe()
    import composition_closure as cc
    import end_to_end_composition_probe as old
    path = sel.OUT / "units"
    if not path.exists():
        pytest.skip("probe has not run yet")
    for p in sorted(path.glob("*.json")):
        rec = old.load(p)
        if rec.get("status") != "RUN":
            continue
        canon = tuple(rec["unit"]["canonical_cell"])
        addr = f"{canon[0]}!{cc.a1(canon[1], canon[2])}"
        for arm in ("A0", "A1"):
            formula = rec[arm]["canonical_formula"]
            if formula is None:
                assert rec[arm]["formulas"] == {}, p.name
            else:
                assert rec[arm]["formulas"][addr] == formula, (p.name, arm)


def test_members_outside_the_group_are_never_written():
    sel = _probe()
    import composition_closure as cc
    import end_to_end_composition_probe as old
    path = sel.OUT / "units"
    if not path.exists():
        pytest.skip("probe has not run yet")
    for p in sorted(path.glob("*.json")):
        rec = old.load(p)
        if rec.get("status") != "RUN":
            continue
        allowed = {f"{c[0]}!{cc.a1(c[1], c[2])}" for c in rec["unit"]["member_cells"]}
        for arm in ("A0", "A1"):
            assert set(rec[arm]["formulas"]) <= allowed, (p.name, arm)
