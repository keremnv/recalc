"""Unit tests for gold-blind slot liveness / regime predicates."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

from formula_dependency_selection import blank_edge_types, build_graph  # noqa: E402
import formula_liveness_probe  # noqa: E402
from formula_liveness import (  # noqa: E402
    ATOMIC,
    CONJUNCTIONS,
    DEFINITIONS,
    build_occupancy_peers,
    conjunctions,
    family_a,
    family_b,
    family_c,
    family_e,
    family_f,
    features_for_cell,
    point_slots_for,
    sheet_scan,
)
from formula_target_selection import occupancy_from_cells  # noqa: E402


def _save(tmp_path: Path, fill) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "M"
    fill(sheet, workbook)
    path = tmp_path / "in.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_definitions_are_gold_blind() -> None:
    assert DEFINITIONS["golden_in_generation"] is False
    signature = inspect.signature(features_for_cell)
    assert "golden" not in signature.parameters
    source = inspect.getsource(sys.modules["formula_liveness"])
    assert "_golden_path" not in source
    assert "_label(" not in source
    assert "golden_response" not in source
    freeze_src = inspect.getsource(formula_liveness_probe.cmd_freeze)
    assert "_golden_path" not in freeze_src
    assert "_label" not in freeze_src
    assert "_cell_map" not in freeze_src


def test_a1_isolated_active_row_hole() -> None:
    grid = occupancy_from_cells(
        "M",
        {
            (1, 1): "F",
            (2, 1): "V",
            (4, 1): "V",
            (5, 1): "F",
        },
    )
    a = family_a(grid, 3, 1)
    assert a["A1_h"] is True
    assert a["A1"] is True
    assert a["A2_h"] is False
    flags = conjunctions({**{name: False for name in (
        "A1", "A2", "B1", "B2", "B3", "C1", "C2", "C3", "D1", "D2", "D3",
        "E1", "E2", "E3", "E4", "F1", "F2", "F3",
    )}, "A1": True, "A2": False, "C2": False, "E1": False})
    assert flags["L1"] is True


def test_a2_persistent_blank_row_segment() -> None:
    cells = {(col, 2): "F" for col in range(1, 6)}
    grid = occupancy_from_cells("M", cells)
    a = family_a(grid, 3, 1)
    assert a["A2_h"] is True
    assert a["A1_h"] is False


def test_a3_vertical_isolated_hole() -> None:
    grid = occupancy_from_cells(
        "M",
        {
            (1, 1): "F",
            (1, 2): "V",
            (1, 4): "V",
            (1, 5): "F",
        },
    )
    a = family_a(grid, 1, 3)
    assert a["A1_v"] is True
    assert a["A3"] is True
    assert a["A1_h"] is False


def test_b3_role_handoff_candidate() -> None:
    cells = {}
    for col in range(1, 4):
        cells[(col, 2)] = "V"
        cells[(col, 3)] = "V"
    for col in range(4, 7):
        cells[(col, 3)] = "F"
    grid = occupancy_from_cells("M", cells)
    b = family_b(grid, 4, 2)
    assert b["B3"] is True
    assert b["handoff_rows"]
    assert b["B1"] is True


def test_c1_beyond_live_extent() -> None:
    grid = occupancy_from_cells(
        "M",
        {
            (1, 1): "V",
            (2, 1): "F",
            (9, 2): "F",
        },
    )
    c = family_c(grid, 5, 1)
    assert c["C1"] is True
    assert c["C2"] is False
    assert c["last_active_col"] == 2


def test_c2_inside_live_extent() -> None:
    grid = occupancy_from_cells(
        "M",
        {
            (1, 1): "V",
            (2, 1): "F",
            (8, 1): "F",
            (9, 1): "V",
        },
    )
    c = family_c(grid, 5, 1)
    assert c["C2"] is True
    assert c["C1"] is False


def test_sheet_scan_matches_direct_family_b() -> None:
    cells = {}
    for col in range(1, 4):
        cells[(col, 2)] = "V"
        cells[(col, 3)] = "V"
    for col in range(4, 7):
        cells[(col, 3)] = "F"
    grid = occupancy_from_cells("M", cells)
    scan = sheet_scan(grid, rows={2})
    assert family_b(grid, 4, 2, scan) == family_b(grid, 4, 2, None)


def test_e3_unique_inactive_slot_among_active_peers(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A2"] = 10
        sheet["A4"] = 20
        sheet["B2"] = "=A2"
        sheet["B3"] = "=A3"
        sheet["B4"] = "=A4"

    graph = build_graph(_save(tmp_path, fill))
    key = ("M", 1, 3)
    types = blank_edge_types(graph)
    assert types[key]["n_point"] >= 1
    occ = build_occupancy_peers(graph.occupancy, {key})
    slots = point_slots_for(graph, key)
    e = family_e(graph, key, occ, {}, slots)
    assert e["n_active"] >= 2
    assert e["n_blank"] == 0
    assert e["E3"] is True
    assert e["E1"] is True
    assert e["E2"] is False


def test_f2_consumer_tolerates_blank_role(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["B2"] = "=A2"
        sheet["B3"] = "=A3"
        sheet["B4"] = "=A4"

    graph = build_graph(_save(tmp_path, fill))
    key = ("M", 1, 3)
    occ = build_occupancy_peers(graph.occupancy, {key})
    slots = point_slots_for(graph, key)
    f = family_f(graph, key, {}, slots)
    assert f["n_peers"] >= 2
    assert f["F2"] is True
    assert f["F1"] is False
    e = family_e(graph, key, occ, {}, slots)
    assert e["E2"] is True


def test_f3_copied_consumer_continuation(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A5"] = "=A1"
        sheet["B5"] = "=B1"
        sheet["C5"] = "=C1"

    graph = build_graph(_save(tmp_path, fill))
    key = ("M", 1, 1)
    f = family_f(graph, key, {}, point_slots_for(graph, key))
    assert f["consumer_columns"] >= 3
    assert f["F3"] is True
    assert f["F2"] is True


def test_features_for_cell_freeze_shape(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = 1
        sheet["C1"] = 2
        sheet["A2"] = "=B1"
        sheet["C2"] = "=B1"

    graph = build_graph(_save(tmp_path, fill))
    key = ("M", 2, 1)
    edge = blank_edge_types(graph)[key]
    occ = build_occupancy_peers(graph.occupancy, {key})
    feat = features_for_cell(graph, key, occ, {}, edge)
    assert set(CONJUNCTIONS) <= set(feat["flags"])
    for name in ATOMIC:
        assert name in feat["flags"]
    assert feat["n_point"] >= 1
    assert feat["flags"]["A1"] in (True, False)
    assert feat["flags"]["L1"] == bool(feat["flags"]["A1"] and not feat["flags"]["A2"])
