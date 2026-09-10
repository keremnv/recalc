"""Tests for the operand-availability audit.

The audit exists to keep one distinction honest: a wrong program written with
every operand materialized is the model's failure; a wrong program written with
an operand missing is the context's. So the tests are about the visibility
ladder and about which side of that line a group lands on.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import operand_availability_audit as oa


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE sheets (sheet_id TEXT, name TEXT);
        CREATE TABLE cells (cell_id TEXT, sheet_id TEXT, address TEXT,
                            row_idx INTEGER, col_idx INTEGER, kind TEXT, raw_value TEXT);
        CREATE TABLE formulas (formula_id TEXT, cell_id TEXT);
        CREATE TABLE point_references (formula_id TEXT, referenced_cell_id TEXT, ref_slot INTEGER);
        CREATE TABLE ranges (range_id TEXT, sheet_id TEXT, r1 INT, c1 INT, r2 INT, c2 INT);
        CREATE TABLE range_references (formula_id TEXT, range_id TEXT, ref_slot INTEGER);
        INSERT INTO sheets VALUES ('s00','Sheet1');
        INSERT INTO cells VALUES ('cell:s00:r1:c1','s00','A1',1,1,'value','1'),
                                 ('cell:s00:r2:c1','s00','A2',2,1,'value','2'),
                                 ('cell:s00:r3:c1','s00','A3',3,1,'value','3'),
                                 ('cell:s00:r4:c1','s00','A4',4,1,'formula',NULL);
        INSERT INTO formulas VALUES ('formula:f1','cell:s00:r4:c1');
        INSERT INTO point_references VALUES ('formula:f1','cell:s00:r2:c1',0);
        INSERT INTO ranges VALUES ('range:g1','s00',1,1,3,1);
        INSERT INTO range_references VALUES ('formula:f1','range:g1',1);
    """)
    return c


def test_a_materialized_cell_outranks_one_that_is_merely_referenced(con):
    level, named = oa.visible_sets(con, {"cell:s00:r1:c1", "formula:f1"})
    assert level["cell:s00:r1:c1"] == "CELL_MATERIALIZED"
    assert "cell:s00:r2:c1" in named
    assert "cell:s00:r2:c1" not in level


def test_a_formula_entity_makes_its_own_cell_visible(con):
    level, _ = oa.visible_sets(con, {"formula:f1"})
    assert level["cell:s00:r4:c1"] == "FORMULA_MATERIALIZED"


def test_a_materialized_range_names_the_cells_inside_it(con):
    _, named = oa.visible_sets(con, {"range:g1"})
    assert {"cell:s00:r1:c1", "cell:s00:r2:c1", "cell:s00:r3:c1"} <= named


def test_nothing_in_the_working_set_means_nothing_is_visible(con):
    level, named = oa.visible_sets(con, set())
    assert not level and not named


# ------------------------------------------------------------ operands

def test_a_bare_reference_is_resolved_against_the_canonical_sheet():
    ops = oa.operands("=A1+'Other'!B2", "Sheet1")
    assert [(o["sheet"], o["start"], o["kind"]) for o in ops] == [
        ("Sheet1", "A1", "POINT"), ("Other", "B2", "POINT")]


def test_a_range_operand_is_kept_apart_from_a_point_operand():
    ops = oa.operands("=SUM(A1:A9)+B1", "Sheet1")
    assert [o["kind"] for o in ops] == ["RANGE", "POINT"]
    assert ops[0]["end"] == "A9"


def test_absolute_markers_do_not_change_the_operand():
    assert oa.operands("=$C$56", "Sheet1")[0]["start"] == "C56"


def test_a_string_literal_is_not_an_operand():
    assert oa.operands('=IF(A1="B2","C3",A4)', "Sheet1") == [
        {"sheet": "Sheet1", "start": "A1", "end": None, "kind": "POINT"},
        {"sheet": "Sheet1", "start": "A4", "end": None, "kind": "POINT"}]


# --------------------------------------------------------- attribution

def _unit(**kw):
    base = {"task": "T", "canonical_member": "Sheet1!A9", "canonical_cell": ["Sheet1", 9, 1],
            "availability_class": "GENUINELY_NOVEL"}
    base.update(kw)
    return base


def _session(ids, boot=()):
    return {"working_set_ids": sorted(ids), "calls": [],
            "bootstrap": {"bootstrap_entity_ids": sorted(boot)}}


def test_every_operand_materialized_is_charged_to_program_construction(con, monkeypatch):
    monkeypatch.setattr(oa, "_conn", lambda task: con)
    r = oa.audit_unit(_unit(), _session(["cell:s00:r1:c1", "cell:s00:r3:c1"]),
                      {("Sheet1", 9, 1): "=A1+A3"})
    assert r["verdict"] == "ALL_OPERANDS_AVAILABLE"
    assert r["attribution"] == "PROGRAM_CONSTRUCTION_FAILURE"


def test_one_missing_operand_is_charged_to_context_delivery(con, monkeypatch):
    monkeypatch.setattr(oa, "_conn", lambda task: con)
    r = oa.audit_unit(_unit(), _session(["cell:s00:r1:c1"]), {("Sheet1", 9, 1): "=A1+A3"})
    assert r["verdict"] == "PARTIAL_OPERANDS_AVAILABLE"
    assert r["attribution"] == "CONTEXT_DELIVERY_FAILURE"
    assert r["weakest_operand_level"] == "ABSENT"


def test_being_named_by_a_retrieved_formula_is_not_the_same_as_being_seen(con, monkeypatch):
    monkeypatch.setattr(oa, "_conn", lambda task: con)
    r = oa.audit_unit(_unit(), _session(["cell:s00:r1:c1", "formula:f1"]),
                      {("Sheet1", 9, 1): "=A1+A2"})
    assert r["weakest_operand_level"] == "REFERENCED_ONLY"
    assert r["attribution"] == "CONTEXT_DELIVERY_FAILURE"


def test_bootstrap_provenance_is_recorded_per_operand(con, monkeypatch):
    monkeypatch.setattr(oa, "_conn", lambda task: con)
    r = oa.audit_unit(_unit(), _session(["cell:s00:r1:c1", "cell:s00:r3:c1"],
                                        boot=["cell:s00:r1:c1"]),
                      {("Sheet1", 9, 1): "=A1+A3"})
    assert [o["from_bootstrap"] for o in r["operands"]] == [True, False]


def test_a_group_outside_the_gold_edit_set_is_not_audited(con, monkeypatch):
    monkeypatch.setattr(oa, "_conn", lambda task: con)
    r = oa.audit_unit(_unit(), _session([]), {})
    assert r["status"] == "CANONICAL_NOT_IN_GOLD_EDIT_SET"
    assert "attribution" not in r
