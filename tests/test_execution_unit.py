"""Tests for Phase B: proposal-seeded closure, the loss taxonomy, and the
value-only rescoring that separates workbook correctness from scorer credit."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import composition_closure as cc
import execution_unit_probe as P
import execution_unit_score as S


def _row(**kw):
    base = {
        "seed_failure_class": None, "seed_status": "PROPOSAL_RETURNED",
        "seed_parsed_status": "PROPOSED", "seed_formula_text_correct": True,
        "closure_status": "CLOSURE_FOUND", "n_members": 1, "n_members_with_proposal": 1,
        "member_text_correct": {"S!A1": True}, "phase_a": {"n_U": 1},
        "delta_modification": 0.0, "delta_modification_value_only": 0.0,
        "delta_regression": 0.0, "delta_regression_value_only": 0.0, "overreach": None,
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- closure

def test_closure_is_seeded_by_the_proposed_formula_not_by_gold():
    """A closure must be derivable from what the model actually wrote."""
    seed = ("Sheet1", 10, 3)
    precs = P.proposal_precedents("=B10+Sheet2!A1", seed)
    assert ("Sheet1", 10, 2) in precs
    assert ("Sheet2", 1, 1) in precs


def test_a_range_in_the_proposal_expands_to_its_cells():
    seed = ("Sheet1", 5, 1)
    precs = P.proposal_precedents("=SUM(C1:C3)", seed)
    assert {("Sheet1", 1, 3), ("Sheet1", 2, 3), ("Sheet1", 3, 3)} <= precs


def test_an_unparseable_proposal_yields_no_precedents_rather_than_raising():
    """A malformed proposal must degrade to an empty closure, not crash the arm."""
    assert P.proposal_precedents("=((((", ("S", 1, 1)) == set()


def test_closure_never_leaves_the_authorised_set():
    """Authority comes from the Edit Plan. Closure may only group, never widen."""
    g = {("S", 3, 1): {("S", 2, 1)}, ("S", 2, 1): {("S", 1, 1)}}
    auth = {("S", 2, 1)}
    assert cc.ancestors_within(("S", 3, 1), g, auth) <= auth


# ---------------------------------------------------------------- taxonomy

def test_a_wrong_seed_proposal_is_a_synthesis_failure_not_a_closure_failure():
    assert S.taxonomy(_row(seed_formula_text_correct=False)) == "F5A_FORMULA_SYNTHESIS_FAILURE"


def test_a_correct_formula_with_an_unsolved_member_is_closure_incomplete():
    r = _row(n_members=2, n_members_with_proposal=1)
    assert S.taxonomy(r) == "F5B_COMPOSITION_CLOSURE_INCOMPLETE"


def test_an_empty_closure_where_phase_a_found_ancestors_is_closure_incomplete():
    r = _row(closure_status="CLOSURE_EMPTY", n_members=0, n_members_with_proposal=0,
             member_text_correct={}, phase_a={"n_U": 3})
    assert S.taxonomy(r) == "F5B_COMPOSITION_CLOSURE_INCOMPLETE"


def test_damage_that_buys_nothing_is_overreach():
    r = _row(overreach={"delta_regression": -0.2, "outweighed_by_gain": False})
    assert S.taxonomy(r) == "F5C_CLOSURE_OVERREACH"


def test_damage_outweighed_by_a_real_gain_is_not_called_overreach():
    """Coordination that wins scorer cells while nudging regression is working."""
    r = _row(delta_modification=0.3, delta_modification_value_only=0.3,
             delta_regression=-0.000005,
             overreach={"delta_regression": -0.000005, "outweighed_by_gain": True})
    assert S.taxonomy(r) == "GAIN_WITH_REGRESSION_COST"


def test_a_unit_that_gained_despite_an_incomplete_closure_says_so():
    r = _row(n_members=2, n_members_with_proposal=1,
             delta_modification=0.02, delta_modification_value_only=0.02)
    assert S.taxonomy(r) == "F5B_COMPOSITION_CLOSURE_INCOMPLETE_BUT_GAINED"


def test_overreach_is_only_recorded_when_something_was_damaged():
    assert S.overreach(_row(), []) is None
    assert S.overreach(_row(delta_regression=-0.1), [])["outweighed_by_gain"] is False


def test_a_truncated_response_is_never_a_model_quality_failure():
    r = _row(seed_failure_class="TRUNCATED_NO_CONTENT")
    assert S.taxonomy(r) == "NON_MODEL_TRUNCATED_NO_CONTENT"


def test_a_resource_limit_is_never_a_model_quality_failure():
    r = _row(seed_failure_class="SESSION_RESOURCE_LIMIT")
    assert S.taxonomy(r) == "NON_MODEL_SESSION_RESOURCE_LIMIT"


def test_gain_requires_the_value_only_metric_to_move():
    """Official credit that moved only through the error fallback is labelled."""
    r = _row(delta_modification=0.3, delta_modification_value_only=0.0)
    assert S.taxonomy(r) == "GAIN_OFFICIAL_ONLY_NOT_BY_VALUE"
    assert S.taxonomy(_row(delta_modification=0.1,
                           delta_modification_value_only=0.1)) == "GAIN"


# ---------------------------------------------------------------- scoring

def test_value_comparison_uses_the_evaluators_own_one_percent_tolerance():
    """Judging by any other rule reports a different population than the scorer."""
    assert S._value_equal(1.0, 1.0 + 1e-12)
    assert S._value_equal(1.0, 1.005)          # inside the evaluator's 1%
    assert not S._value_equal(1.0, 1.5)


def test_not_meaningful_placeholders_are_equivalent_to_each_other():
    assert S._value_equal("#DIV/0!", "N/M")
    assert not S._value_equal("#DIV/0!", 2.39)


def test_an_error_string_is_not_equal_to_a_number():
    assert not S._value_equal(2.39, "#VALUE!")


def test_provenance_names_the_edited_cell_itself():
    g = {}
    assert S.provenance("t", ("S", 1, 1), {("S", 1, 1)}, g) == "DIRECTLY_EDITED_CELL"


def test_provenance_follows_the_input_side_graph_upstream():
    g = {("S", 3, 1): {("S", 2, 1)}, ("S", 2, 1): {("S", 1, 1)}}
    assert S.provenance("t", ("S", 2, 1), {("S", 1, 1)}, g) == "RECALCULATED_DEPENDENT_DIRECT"
    assert S.provenance("t", ("S", 3, 1), {("S", 1, 1)}, g) == "RECALCULATED_DEPENDENT_TRANSITIVE"
    assert S.provenance("t", ("S", 3, 1), {("S", 9, 9)}, g) == "UNEXPLAINED_BY_INPUT_SIDE_GRAPH"


def test_quarantined_tasks_stay_out_of_the_phase_b_population():
    assert set(P.QUARANTINED) == {"07_03", "14_05"}
    units = P.old.load(P.OUT / "units.json")["units"]
    assert not [u for u in units if u["task"] in P.QUARANTINED]


def test_every_selected_seed_is_authorised_by_its_edit_plan():
    units = P.old.load(P.OUT / "units.json")["units"]
    assert units
    for u in units:
        _, _, by_cell, _ = P.authorised(u["task"])
        assert tuple(u["seed_cell"]) in by_cell


# ------------------------------- defect 9: budget exhaustion with content

def _stub(monkeypatch, old, text, completion_tokens):
    def fake_call_glm(key, system, content, tag, max_tokens):
        if tag.endswith("retrieval"):
            return {"http_ok": True, "text": '{"action":"final","status":"ENOUGH_EVIDENCE"}', "usage": {}}
        return {"http_ok": True, "text": text, "usage": {"completion_tokens": completion_tokens}}

    monkeypatch.setattr(old, "call_glm", fake_call_glm)
    monkeypatch.setattr(old, "compile_bootstrap", lambda *a: {"bootstrap_entity_ids": []})
    monkeypatch.setattr(old, "materialize_working_set", lambda task, working: {})
    monkeypatch.setattr(old, "ReadOnlySqlite", lambda *a, **k: object())
    return old.run_target("t", "raw", {"id": "O1"},
                          {"cell_id": "cell:s01:r1:c1", "sheet": "S", "address": "A1"}, {}, {}, "k")


def test_deliberation_that_exhausts_the_budget_is_truncation_not_a_wrong_answer(monkeypatch):
    """The response spent every output token reasoning and never emitted JSON."""
    old = P.old
    r = _stub(monkeypatch, old, "thinking out loud " * 500, old.SYNTHESIS_MAX_TOKENS)
    assert r["synthesis_truncated"] is True
    assert r["truncation_class"] == "TRUNCATED_AT_BUDGET"
    assert r["failure_class"] == "TRUNCATED_AT_BUDGET"


def test_an_empty_body_at_the_budget_keeps_its_own_class(monkeypatch):
    old = P.old
    r = _stub(monkeypatch, old, "", old.SYNTHESIS_MAX_TOKENS)
    assert r["truncation_class"] == "TRUNCATED_NO_CONTENT"


def test_a_parsed_answer_at_the_budget_is_not_truncated(monkeypatch):
    """Hitting the budget is only truncation when nothing parseable came out."""
    old = P.old
    r = _stub(monkeypatch, old, '{"status":"ABSTAIN"}', old.SYNTHESIS_MAX_TOKENS)
    assert r["synthesis_truncated"] is False
    assert r["truncation_class"] is None


def test_unparseable_below_the_budget_is_still_a_parse_failure(monkeypatch):
    old = P.old
    r = _stub(monkeypatch, old, "no json here", 42)
    assert r["synthesis_truncated"] is False
    assert r["failure_class"] is None


def test_budget_exhaustion_is_declared_a_non_model_failure():
    import instrumentation_freeze as instr
    assert "TRUNCATED_AT_BUDGET" in instr.NON_MODEL_FAILURE_CLASSES


# ------------------------------- invariants over the executed run

def test_no_executed_unit_ever_edited_a_cell_the_edit_plan_had_not_authorised():
    """The safety rule of the spec, checked against what actually ran."""
    for path in sorted((P.OUT / "units").glob("*.json")):
        rec = P.old.load(path)
        _, _, by_cell, _ = P.authorised(rec["unit"]["task"])
        for cell in rec["member_cells"]:
            assert tuple(cell) in by_cell, f"{path.name} edited an unauthorised cell {cell}"


def test_both_arms_share_the_same_seed_formula():
    """B1 must reuse B0's seed session, so the arms differ in one thing only."""
    scores = P.old.load(P.OUT / "phase_b_scores.json")["units"]
    for r in scores:
        rec = P.old.load(P.OUT / f"units/{r['task']}__"
                                 f"{r['seed'].replace('!', '_').replace(' ', '_')}.json")
        assert rec.get("seed_formula") == r["seed_formula"]


def test_a_censored_session_is_recorded_not_dropped():
    """A resource bound must leave a trace, never silently shrink the arm."""
    seen = set()
    for path in sorted((P.OUT / "units").glob("*.json")):
        rec = P.old.load(path)
        for member, status in (rec.get("member_status") or {}).items():
            seen.add(status)
            assert status is not None
    assert seen <= {"PROPOSAL_RETURNED", "MODEL_ACCESS_FAILURE", "INTEGRATION_FAILURE",
                    "RESOURCE_CENSORED_NOT_RUN"}


def test_every_stored_session_retained_its_raw_body_and_usage():
    """Retaining raw responses is a standing reproducibility requirement."""
    for path in sorted((P.OUT / "sessions").glob("*.json")):
        d = P.old.load(path)
        resp = (d.get("synthesis") or {}).get("response") or {}
        assert resp.get("text") is not None, path.name
        assert resp.get("usage"), path.name
