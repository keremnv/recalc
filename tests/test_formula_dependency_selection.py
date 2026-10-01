"""Unit tests for conservative dependency target selectors."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

from formula_completion_certs import load_grids  # noqa: E402
from formula_dependency_selection import (  # noqa: E402
    build_graph,
    d3_name,
    homologous_peers,
    referenced_blanks,
    select_all,
    select_d1,
    select_d3,
    select_d4,
    select_d5,
    select_d6,
    slot_evidence,
)


def _save(tmp_path: Path, fill) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "M"
    fill(sheet, workbook)
    path = tmp_path / "in.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_indirect_and_named_range_create_no_edges(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = '=INDIRECT("B1")'
        sheet["A2"] = "=Revenue"
        sheet["B1"] = None
        sheet["C1"] = 1

    graph = build_graph(_save(tmp_path, fill))
    assert graph.coverage["opaque"] == 2
    assert graph.coverage["supported_with_edges"] == 0
    assert referenced_blanks(graph) == {}


def test_explicit_a1_creates_reverse_edge(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = "=B1"
        sheet["C1"] = "=B1+B2"

    graph = build_graph(_save(tmp_path, fill))
    blanks = referenced_blanks(graph)
    assert ("M", 2, 1) in blanks
    assert len(blanks[("M", 2, 1)]["dependents"]) == 2
    assert ("M", 2, 2) in blanks
    assert len(blanks[("M", 2, 2)]["dependents"]) == 1
    assert graph.coverage["dropped_unknown_or_unparsed"] == 0


def test_unknown_sheet_is_dropped(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = "=Missing!B1"
        sheet["A2"] = "=B2"

    graph = build_graph(_save(tmp_path, fill))
    blanks = referenced_blanks(graph)
    assert ("M", 2, 2) in blanks
    assert graph.coverage["dropped_unknown_or_unparsed"] >= 1
    assert ("Missing", 2, 1) not in blanks


def test_d1_thresholds_and_d2_families(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = "=C1"
        sheet["A2"] = "=C1"
        sheet["B1"] = "=C1+1"

    graph = build_graph(_save(tmp_path, fill))
    blanks = referenced_blanks(graph)
    assert select_d1(blanks, 1) == {("M", 3, 1)}
    assert select_d1(blanks, 3) == {("M", 3, 1)}
    assert select_d1(blanks, 5) == set()
    selected, _, _ = select_all(graph)
    assert ("M", 3, 1) in selected["D2_2"]
    assert ("M", 3, 1) in selected["D2_1"]


def test_homologous_formula_role_d3_d4_d5(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["C2"] = "=A2"
        sheet["C4"] = "=A4"
        sheet["D2"] = "=C2"
        sheet["D3"] = "=C3"
        sheet["D4"] = "=C4"

    graph = build_graph(_save(tmp_path, fill))
    blanks = referenced_blanks(graph)
    evidence = slot_evidence(graph, blanks)
    assert ("M", 3, 3) in blanks
    recs = evidence[("M", 3, 3)]
    assert recs
    best = max(recs, key=lambda rec: rec["n_peers"])
    assert best["n_peers"] == 2
    assert best["n_formula"] == 2
    assert best["share"] == 1.0
    assert best["same_formula_eq"] is True
    assert ("M", 3, 3) in select_d3(evidence, 2, 1.0)
    assert ("M", 3, 3) in select_d4(evidence, 2)
    assert ("M", 3, 3) in select_d5(evidence, 2)
    assert ("M", 3, 3) not in select_d3(evidence, 5, 1.0)


def test_value_peers_are_not_formula_consensus(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["C2"] = 10
        sheet["C4"] = 10
        sheet["D2"] = "=C2"
        sheet["D3"] = "=C3"
        sheet["D4"] = "=C4"

    graph = build_graph(_save(tmp_path, fill))
    evidence = slot_evidence(graph, referenced_blanks(graph))
    assert ("M", 3, 3) not in select_d3(evidence, 2, 0.75)
    assert ("M", 3, 3) not in select_d5(evidence, 2)


def test_two_blank_peers_block_singleton(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["C2"] = "=A2"
        sheet["D2"] = "=C2"
        sheet["D3"] = "=C3"
        sheet["D4"] = "=C4"

    graph = build_graph(_save(tmp_path, fill))
    evidence = slot_evidence(graph, referenced_blanks(graph))
    assert ("M", 3, 3) not in select_d4(evidence, 2)
    assert ("M", 3, 4) not in select_d4(evidence, 2)


def test_d6_two_consumer_classes(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["C2"] = "=A2"
        sheet["C4"] = "=A4"
        sheet["D2"] = "=C2"
        sheet["D3"] = "=C3"
        sheet["D4"] = "=C4"
        sheet["E2"] = "=C2*2"
        sheet["E3"] = "=C3*2"
        sheet["E4"] = "=C4*2"

    graph = build_graph(_save(tmp_path, fill))
    evidence = slot_evidence(graph, referenced_blanks(graph))
    assert ("M", 3, 3) in select_d6(evidence, 2, d5=False)
    assert ("M", 3, 3) in select_d6(evidence, 2, d5=True)
    assert ("M", 3, 3) not in select_d6(evidence, 3, d5=False)


def test_range_offset_homology(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = 1
        sheet["A2"] = 1
        sheet["A3"] = 1
        sheet["C1"] = 1
        sheet["C3"] = 1
        sheet["B4"] = "=SUM(A1:A3)"
        sheet["D4"] = "=SUM(C1:C3)"

    graph = build_graph(_save(tmp_path, fill))
    blanks = referenced_blanks(graph)
    assert ("M", 3, 2) in blanks
    node = graph.formulas[("M", 4, 4)]
    peers = homologous_peers(graph, ("M", 3, 2), node.eq_id, 0, ("M", 4, 4))
    assert peers == [("M", 1, 2)]


def test_selector_grid_is_predeclared(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = "=B1"

    selected, _, _ = select_all(build_graph(_save(tmp_path, fill)))
    assert d3_name(2, 1.0) in selected
    assert d3_name(5, 0.75) in selected
    assert "D5_2" in selected
    assert "D6_D5_3" in selected
    assert "D1_1∩S1" in selected


def test_point_vs_range_partition_is_mutually_exclusive(tmp_path: Path) -> None:
    from formula_dependency_selection import blank_edge_types

    def fill(sheet, _wb) -> None:
        sheet["A1"] = "=B1"
        sheet["A2"] = "=SUM(C1:C4)"
        sheet["A3"] = "=D1+SUM(D1:D3)"
        sheet["C4"] = 0
        sheet["D3"] = 0

    types = blank_edge_types(build_graph(_save(tmp_path, fill)))
    assert types[("M", 2, 1)]["partition"] == "POINT_ONLY"
    assert types[("M", 3, 2)]["partition"] == "RANGE_ONLY"
    assert types[("M", 4, 1)]["partition"] == "POINT_AND_RANGE"
    assert types[("M", 4, 2)]["partition"] == "RANGE_ONLY"
    assert types[("M", 2, 1)]["n_point"] == 1
    assert types[("M", 3, 2)]["n_range"] == 1
    assert types[("M", 4, 1)]["n_point"] == 1
    assert types[("M", 4, 1)]["n_range"] == 1
    assert types[("M", 3, 2)]["min_range_area"] == 4

