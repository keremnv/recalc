"""Tests for the N0-N3 factorial and the oracle evidence-completion arm.

What has to hold: the rebuilt payload is the stored one when nothing is added,
each oracle block reveals exactly its own factor and no more, and the two
populations stay disjoint from the abstentions they would otherwise absorb.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import synthesis_decomposition as sd


# --------------------------------------------------------------- skeleton

def test_every_reference_becomes_a_numbered_hole():
    assert sd.skeleton("=C62*C63+C64*C65") == ("=<REF1>*<REF2>+<REF3>*<REF4>", 4)


def test_literals_survive_the_skeleton_because_they_are_structure():
    assert sd.skeleton("=C66*C67/12")[0] == "=<REF1>*<REF2>/12"


def test_a_function_name_is_not_mistaken_for_a_reference():
    shape, n = sd.skeleton("=OFFSET($I16,0,C$4-1,1,1)")
    assert shape == "=OFFSET(<REF1>,0,<REF2>-1,1,1)" and n == 2


def test_a_cross_sheet_reference_is_a_single_hole():
    assert sd.skeleton("='Balance Sheet'!C18/'Balance Sheet'!C9") == ("=<REF1>/<REF2>", 2)


def test_repeated_references_get_their_own_holes():
    assert sd.skeleton("=A1+A1")[1] == 2


# -------------------------------------------------------------- reference set

def test_the_reference_set_is_sorted_so_slot_order_leaks_nothing():
    assert sd.reference_set("=C67*C66/12", "WC") == ["WC!C66", "WC!C67"]


def test_the_reference_set_is_distinct():
    assert sd.reference_set("=A1+A1", "S") == ["S!A1"]


def test_a_bare_reference_takes_the_canonical_sheet():
    assert sd.reference_set("=A1+'Other'!B2", "Home") == ["Home!A1", "Other!B2"]


# -------------------------------------------------------------- oracle blocks

@pytest.mark.parametrize("arm,keys", [
    ("N0", []),
    ("N1", ["ORACLE_PROGRAM_SHAPE"]),
    ("N2", ["ORACLE_REFERENCE_SET"]),
    ("N3", ["ORACLE_PROGRAM_SHAPE", "ORACLE_REFERENCE_SET"]),
])
def test_each_arm_reveals_exactly_its_own_factor(arm, keys):
    assert sorted(sd.oracle_for(arm, "=C66*C67/12", "WC")) == sorted(keys)


def test_the_shape_arm_never_names_a_cell():
    block = sd.oracle_for("N1", "=C66*C67/12", "WC")["ORACLE_PROGRAM_SHAPE"]
    assert "C66" not in block["skeleton"] and "C67" not in block["skeleton"]


def test_the_reference_arm_never_shows_an_operator():
    block = sd.oracle_for("N2", "=C66*C67/12", "WC")["ORACLE_REFERENCE_SET"]
    assert block["references"] == ["WC!C66", "WC!C67"]
    assert "12" not in "".join(block["references"])


# ------------------------------------------------------------------ payload

def _session():
    return {"working_set_ids": ["cell:s00:r1:c1"], "target": {"cell_id": "cell:s00:r9:c1"},
            "obligation": {"id": "ob1"}}


def test_a_rebuild_with_nothing_added_is_the_stored_payload(monkeypatch):
    monkeypatch.setattr(sd.old, "materialize_working_set", lambda t, w: {"ids": sorted(w)})
    a, _ = sd.rebuild("T", _session(), "raw")
    b, _ = sd.rebuild("T", _session(), "raw")
    assert a == b
    assert "ORACLE" not in a


def test_completed_evidence_adds_the_operand_and_nothing_else(monkeypatch):
    monkeypatch.setattr(sd.old, "materialize_working_set", lambda t, w: {"ids": sorted(w)})
    _, base = sd.rebuild("T", _session(), "raw")
    _, done = sd.rebuild("T", _session(), "raw", extra_ids={"cell:s00:r2:c1"})
    assert set(done) == set(base)
    assert done["WORKING_SET_ENTITY_IDS"] == ["cell:s00:r1:c1", "cell:s00:r2:c1"]
    for k in ("SYNTHESIS_TRANSITION", "RAW_TASK", "TARGET", "OBLIGATION"):
        assert done[k] == base[k]


def test_an_oracle_block_is_the_only_other_difference(monkeypatch):
    monkeypatch.setattr(sd.old, "materialize_working_set", lambda t, w: {"ids": sorted(w)})
    _, base = sd.rebuild("T", _session(), "raw")
    _, n3 = sd.rebuild("T", _session(), "raw", oracle=sd.oracle_for("N3", "=A1+A2", "S"))
    assert set(n3) - set(base) == {"ORACLE_PROGRAM_SHAPE", "ORACLE_REFERENCE_SET"}
    assert all(n3[k] == base[k] for k in base)


# --------------------------------------------------------------- populations

def _row(member, cls, attribution, correct=False, gold="=A1+A2", task="T"):
    return {"status": "AUDITED", "task": task, "canonical_member": member,
            "availability_class": cls, "attribution": attribution, "correct": correct,
            "gold_canonical_formula": gold}


def test_the_two_populations_split_wrong_groups_by_earliest_loss(monkeypatch):
    rows = [_row("a", "GENUINELY_NOVEL", "PROGRAM_CONSTRUCTION_FAILURE"),
            _row("b", "RECOVERABLE_SHAPE_ONLY", "CONTEXT_DELIVERY_FAILURE"),
            _row("c", "GENUINELY_NOVEL", "PROGRAM_CONSTRUCTION_FAILURE", correct=True)]
    monkeypatch.setattr(sd, "audit_rows", lambda: rows)
    n, e = sd.populations()
    assert [r["canonical_member"] for r in n] == ["a"]
    assert [r["canonical_member"] for r in e] == ["b"]


def test_the_recoverable_exact_abstentions_are_in_neither_population(monkeypatch):
    rows = [_row("abstained", "RECOVERABLE_EXACT", "PROGRAM_CONSTRUCTION_FAILURE")]
    monkeypatch.setattr(sd, "audit_rows", lambda: rows)
    n, e = sd.populations()
    assert n == [] and e == []


def test_one_program_on_two_columns_is_one_program(monkeypatch):
    a = _row("Sheet!C68", "GENUINELY_NOVEL", "PROGRAM_CONSTRUCTION_FAILURE", gold="=C66*C67/12")
    b = _row("Sheet!D68", "GENUINELY_NOVEL", "PROGRAM_CONSTRUCTION_FAILURE", gold="=D66*D67/12")
    assert sd.program_key(a) == sd.program_key(b)


def test_the_same_shape_in_a_different_task_is_a_different_program():
    a = _row("S!A1", "GENUINELY_NOVEL", "PROGRAM_CONSTRUCTION_FAILURE", task="08_04")
    b = _row("S!A1", "GENUINELY_NOVEL", "PROGRAM_CONSTRUCTION_FAILURE", task="08_05")
    assert sd.program_key(a) != sd.program_key(b)
