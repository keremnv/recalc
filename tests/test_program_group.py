"""Tests for ProgramGroup formation and deterministic translation.

The central rule under test is that region membership never implies one
program: a group exists only when the input workbook itself demonstrates the
repetition, at the group's own coordinates, on more than one line.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import program_group as pg


S = "Sheet1"


def _forms(spec):
    return {(S, r, c): f for (r, c), f in spec.items()}


# ------------------------------------------------------------- translation

def test_relative_references_move_with_the_cell():
    assert pg.translate("=A1+B2", (S, 1, 1), (S, 1, 2)) == "=B1+C2"


def test_absolute_references_do_not_move():
    assert pg.translate("=$A$1+B2", (S, 1, 1), (S, 2, 3)) == "=$A$1+D3"


def test_mixed_references_move_only_on_the_relative_axis():
    assert pg.translate("=A$1+$B2", (S, 5, 1), (S, 6, 2)) == "=B$1+$B3"


def test_ranges_translate_at_both_endpoints():
    assert pg.translate("=SUM(A1:A5)", (S, 1, 1), (S, 1, 2)) == "=SUM(B1:B5)"


def test_sheet_qualified_references_keep_their_sheet():
    out = pg.translate("='Other Sheet'!A1", (S, 1, 1), (S, 1, 2))
    assert out == "='Other Sheet'!B1"


def test_string_literals_are_never_rewritten():
    assert pg.translate('=IF(A1="B2","B2",A1)', (S, 1, 1), (S, 1, 2)) == '=IF(B1="B2","B2",B1)'


def test_translation_that_would_leave_the_grid_is_a_failure_not_a_guess():
    """Moving a reference above row 1 must be refused, never silently clamped."""
    out = pg.apply_program("=A2", {"canonical_cell": [S, 5, 1],
                                   "member_cells": [[S, 5, 1], [S, 1, 1]]})
    assert "TRANSLATION_FAILURE" in out["failures"][f"{S}!A1"]
    assert f"{S}!A1" not in out["formulas"]


# ------------------------------------------------------------- eligibility

def _by_cell(cells, op="op1"):
    return {c: {"operation_id": op} for c in cells}


def test_a_row_with_no_repetition_anywhere_forms_no_group():
    members = [(S, 10, 3), (S, 10, 4)]
    forms = _forms({})
    kinds = {c: "blank" for c in members}
    groups, refused = pg.groups_for(members, _by_cell(members), "t", forms, kinds)
    assert groups == []
    assert any(r["reason"] == "NO_REPETITION_WITNESS_IN_INPUT_WORKBOOK" for r in refused)


def test_two_corroborating_lines_establish_a_group():
    members = [(S, 10, 3), (S, 10, 4)]
    forms = _forms({(11, 3): "=A11", (11, 4): "=B11", (12, 3): "=A12+1", (12, 4): "=B12+1"})
    kinds = {c: "blank" for c in members}
    groups, _ = pg.groups_for(members, _by_cell(members), "t", forms, kinds)
    assert len(groups) == 1
    assert groups[0]["members"] == ["Sheet1!C10", "Sheet1!D10"]
    assert groups[0]["witness"]["n_corroborating_lines"] >= 2


def test_the_evidence_standard_is_a_declared_knob_not_an_accident():
    """One witness line is the frozen default; corroboration is available and measured."""
    members = [(S, 10, 3), (S, 10, 4)]
    forms = _forms({(11, 3): "=A11", (11, 4): "=B11"})
    kinds = {c: "blank" for c in members}
    assert pg.MIN_WITNESS_LINES == 1
    assert pg.groups_for(members, _by_cell(members), "t", forms, kinds)[0]
    assert pg.groups_for(members, _by_cell(members), "t", forms, kinds, min_lines=2)[0] == []


def test_a_line_that_does_not_repeat_cannot_vouch_for_the_group():
    """Two formulas that are not translations of each other are not a program."""
    members = [(S, 10, 3), (S, 10, 4)]
    forms = _forms({(11, 3): "=A11", (11, 4): "=ZZ99", (12, 3): "=A12", (12, 4): "=QQ1"})
    kinds = {c: "blank" for c in members}
    assert pg.groups_for(members, _by_cell(members), "t", forms, kinds)[0] == []


def test_the_group_shrinks_to_the_coordinates_the_witness_actually_covers():
    """A witness over C:D says nothing about E, so E stays out."""
    members = [(S, 10, 3), (S, 10, 4), (S, 10, 5)]
    forms = _forms({(11, 3): "=A11", (11, 4): "=B11", (12, 3): "=A12", (12, 4): "=B12"})
    kinds = {c: "blank" for c in members}
    groups, refused = pg.groups_for(members, _by_cell(members), "t", forms, kinds)
    assert groups[0]["members"] == ["Sheet1!C10", "Sheet1!D10"]
    assert any(r["reason"] == "OUTSIDE_WITNESSED_RUN" and "Sheet1!E10" in r["members"]
               for r in refused)


def test_members_in_different_edit_plan_operations_are_not_one_group():
    members = [(S, 10, 3), (S, 10, 4)]
    forms = _forms({(11, 3): "=A11", (11, 4): "=B11", (12, 3): "=A12", (12, 4): "=B12"})
    kinds = {c: "blank" for c in members}
    by_cell = {members[0]: {"operation_id": "op1"}, members[1]: {"operation_id": "op2"}}
    assert pg.groups_for(members, by_cell, "t", forms, kinds)[0] == []


def test_members_on_different_sheets_are_never_collinear():
    members = [(S, 10, 3), ("Other", 10, 4)]
    assert pg.axis_of(members) is None


def test_a_single_member_is_never_a_program_group():
    members = [(S, 10, 3)]
    forms = _forms({(11, 3): "=A11", (12, 3): "=A12"})
    assert pg.groups_for(members, _by_cell(members), "t", forms, {members[0]: "blank"})[0] == []


# ------------------------------------------------------------- canonical

def test_canonical_prefers_a_member_that_already_has_a_formula():
    members = [(S, 10, 3), (S, 10, 4)]
    forms = _forms({(10, 4): "=B10"})
    assert pg.canonical_member(members, "ROW", forms) == (S, 10, 4)


def test_canonical_otherwise_is_the_leftmost_member_deterministically():
    members = [(S, 10, 4), (S, 10, 3)]
    assert pg.canonical_member(members, "ROW", {}) == (S, 10, 3)


# ------------------------------------------------------------- application

def test_one_program_is_instantiated_across_the_group_without_a_model():
    group = {"canonical_cell": [S, 44, 10],
             "member_cells": [[S, 44, 10], [S, 44, 11], [S, 44, 12]]}
    out = pg.apply_program("=+J35+J26+J15+J6", group)
    assert out["formulas"]["Sheet1!J44"] == "=+J35+J26+J15+J6"
    assert out["formulas"]["Sheet1!K44"] == "=+K35+K26+K15+K6"
    assert out["formulas"]["Sheet1!L44"] == "=+L35+L26+L15+L6"
    assert out["failures"] == {}


# ------------------------------- arm construction invariants

def _probe():
    import program_group_probe as C
    return C


def test_p1_never_issues_a_model_call_p0_does_not():
    """The canonical session is one of P0's own sessions, byte for byte."""
    C = _probe()
    path = C.OUT / "units"
    if not path.exists():
        pytest.skip("probe has not run yet")
    for p in sorted(path.glob("*.json")):
        rec = C.old.load(p)
        assert rec["P1_model_calls"] <= rec["P0_model_calls"], p.name


def test_every_group_member_is_an_authorised_closure_member():
    """ProgramGroup.members must stay inside the ExecutionUnit's authorised set."""
    C = _probe()
    path = C.OUT / "units"
    if not path.exists():
        pytest.skip("probe has not run yet")
    for p in sorted(path.glob("*.json")):
        rec = C.old.load(p)
        members = set(rec["members"])
        for g in rec["program_groups"]:
            assert set(g["members"]) <= members, p.name


def test_the_two_arms_share_the_seed_formula_exactly():
    C = _probe()
    path = C.OUT / "units"
    if not path.exists():
        pytest.skip("probe has not run yet")
    for p in sorted(path.glob("*.json")):
        rec = C.old.load(p)
        for a in rec["members_not_in_any_group"]:
            assert rec["P1_formulas"].get(a) == rec["P0_formulas"].get(a), p.name


def test_a_translation_failure_is_never_replaced_by_independent_synthesis():
    """§11: no silent fallback inside a group in the primary P1 arm."""
    C = _probe()
    path = C.OUT / "units"
    if not path.exists():
        pytest.skip("probe has not run yet")
    for p in sorted(path.glob("*.json")):
        rec = C.old.load(p)
        for g in rec["program_groups"]:
            for member, _ in (g.get("translation_failures") or {}).items():
                assert rec["P1_formulas"].get(member) is None, p.name


# ------------------------------------------------- post-run diagnostics

def _mod(name):
    import importlib
    return importlib.import_module(name)


def test_exactness_separates_exact_matches_from_tolerance_credit():
    """A near miss inside the evaluator's 1% band is not an exact answer."""
    ex = _mod("program_group_exactness")
    detail = {"A": {"gold": 100.0, "got": 100.0},
              "B": {"gold": 100.0, "got": 100.5},
              "C": {"gold": 100.0, "got": 130.0},
              "D": {"gold": "text", "got": "text"}}
    out = ex.classify(detail, ["A", "B", "C", "D"])
    assert out["exact"] == ["A"]
    assert out["within_tolerance_not_exact"] == ["B"]
    assert set(out["not_numeric_or_outside"]) == {"C", "D"}


def test_exactness_never_credits_a_cell_outside_the_band():
    ex = _mod("program_group_exactness")
    out = ex.classify({"A": {"gold": 1.0, "got": 1.02}}, ["A"])
    assert out["exact"] == [] and out["within_tolerance_not_exact"] == []


def test_posthoc_substitutes_only_when_the_canonical_produced_nothing():
    """The post-hoc rule leaves a group alone when its canonical answered."""
    ph = _mod("program_group_posthoc")
    rec = {"program_groups": [{"members": ["Sheet1!A1", "Sheet1!B1"],
                               "canonical_member": "Sheet1!A1"}],
           "P0_formulas": {"Sheet1!A1": "=A2", "Sheet1!B1": "=ZZ9"},
           "P0_outcomes": {"Sheet1!A1": "PROPOSED", "Sheet1!B1": "PROPOSED"}}
    out = ph.recovered(rec)
    assert out["formulas"] == {}
    assert out["notes"] == [{"group": "Sheet1!A1", "substituted": False}]


def test_posthoc_translates_from_the_first_member_that_answered():
    ph = _mod("program_group_posthoc")
    rec = {"program_groups": [{"members": ["Sheet1!A1", "Sheet1!B1", "Sheet1!C1"],
                               "canonical_member": "Sheet1!A1"}],
           "P0_formulas": {"Sheet1!A1": None, "Sheet1!B1": "=B2", "Sheet1!C1": "=ZZ9"},
           "P0_outcomes": {"Sheet1!A1": "ABSTAIN", "Sheet1!B1": "PROPOSED",
                           "Sheet1!C1": "PROPOSED"}}
    out = ph.recovered(rec)
    assert out["formulas"] == {"Sheet1!A1": "=A2", "Sheet1!B1": "=B2", "Sheet1!C1": "=C2"}
    note = out["notes"][0]
    assert note["substituted"] and note["substitute_canonical"] == "Sheet1!B1"


def test_posthoc_reports_when_no_member_answered_at_all():
    ph = _mod("program_group_posthoc")
    rec = {"program_groups": [{"members": ["Sheet1!A1", "Sheet1!B1"],
                               "canonical_member": "Sheet1!A1"}],
           "P0_formulas": {"Sheet1!A1": None, "Sheet1!B1": None},
           "P0_outcomes": {"Sheet1!A1": "ABSTAIN", "Sheet1!B1": "ABSTAIN"}}
    out = ph.recovered(rec)
    assert out["formulas"] == {}
    assert out["notes"][0]["reason"] == "NO_MEMBER_PROPOSED_ANYTHING"


def test_p1_sessions_are_always_a_subset_of_p0_sessions():
    """The cost claim rests on P1 never issuing a call P0 did not."""
    C = _probe()
    cost = C.OUT / "phase_c_cost.json"
    if not cost.exists():
        pytest.skip("cost has not been computed yet")
    d = C.old.load(cost)
    for u in d["units"]:
        assert u["P1_sessions"] <= u["P0_sessions"], u["seed"]
        for f in ("retrieval_input_tokens", "synthesis_input_tokens"):
            assert u["P1"][f] <= u["P0"][f], (u["seed"], f)
