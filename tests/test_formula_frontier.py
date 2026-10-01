"""Unit tests for gold-blind blank-tail continuation vs termination predicates."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import formula_frontier_probe  # noqa: E402
from formula_dependency_selection import build_graph  # noqa: E402
from formula_frontier import (  # noqa: E402
    CONJUNCTIONS,
    DEFINITIONS,
    SchemaLayer,
    build_extent,
    conjunctions,
    family_a,
    family_b,
    family_d,
    family_g,
    features_for_cell,
)
from formula_liveness import build_occupancy_peers  # noqa: E402
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
    source = inspect.getsource(sys.modules["formula_frontier"])
    assert "_golden_path" not in source
    assert "_label(" not in source
    assert "golden_response" not in source
    freeze_src = inspect.getsource(formula_frontier_probe.cmd_freeze)
    assert "_golden_path" not in freeze_src
    assert "_label" not in freeze_src
    assert "golden" not in inspect.signature(features_for_cell).parameters


def test_a3_isolated_stop_and_a2_coordinated_stop() -> None:
    cells = {}
    for col in range(1, 4):
        cells[(col, 5)] = "F"
    for col in range(1, 12):
        cells[(col, 4)] = "F"
        cells[(col, 6)] = "F"
    extent = build_extent(occupancy_from_cells("M", cells))
    a = family_a(extent, 5, 5, last_t=3)
    assert a["A1"] is True
    assert a["A3"] is True
    assert a["A2"] is False

    for col in range(1, 4):
        cells[(col, 3)] = "F"
        cells[(col, 4)] = "F"
        cells[(col, 6)] = "F"
        cells[(col, 7)] = "F"
    for col in range(4, 12):
        cells.pop((col, 4), None)
        cells.pop((col, 6), None)
    extent = build_extent(occupancy_from_cells("M", cells))
    a = family_a(extent, 5, 5, last_t=3)
    assert a["A2"] is True
    assert a["A3"] is False


def test_b1_schema_continues_and_b3_period_sequence() -> None:
    schema = SchemaLayer(
        headers={1: {1: 2020, 2: 2021, 3: 2022, 4: 2023, 5: 2024}},
        merges=[],
        widths={},
    )
    b = family_b(schema, col=4, row=10, last_t=3, tail=4, max_col=8)
    assert b["B1"] is True
    assert b["B3"] is True
    assert b["B2"] is False
    stop = SchemaLayer(headers={1: {1: 2020, 2: 2021, 3: 2022}}, merges=[], widths={})
    b2 = family_b(stop, col=5, row=10, last_t=3, tail=4, max_col=8)
    assert b2["B1"] is False
    assert b2["B2"] is True
    assert b2["B3"] is False


def test_g_distance_bins_are_predeclared() -> None:
    g = family_g(col=5, last_t=4, tail=6, max_col=12, resume=False)
    assert g["G_first_blank"] is True
    assert g["G_dist_1"] is True
    assert g["G_tail_5_8"] is True
    assert g["distance"] == 1


def test_d1_d4_horizontal_family_frontier(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A2"] = 1
        sheet["B2"] = "=A2"
        sheet["C2"] = "=B2"
        sheet["A5"] = 1
        sheet["B5"] = "=A5"
        sheet["C5"] = "=B5"
        sheet["D5"] = "=C5"
        sheet["Z20"] = 1
        sheet["D3"] = "=D2"

    graph = build_graph(_save(tmp_path, fill))
    key = ("M", 4, 2)
    p_key = ("M", 3, 2)
    d = family_d(graph, key, p_key)
    assert d["D1"] is True
    assert d["D2"] is True
    assert d["translation_supported"] is True
    assert d["D4"] is True
    assert "formula" not in d


def test_q_conjunctions_are_unweighted() -> None:
    flags = {
        name: False
        for name in (
            "A3",
            "B1",
            "A2",
            "F1",
            "Hom1",
            "Hom2",
            "D1",
            "D2",
            "D3",
            "D4",
            "E1",
            "E2",
            "B2",
            "F2",
            "F3",
        )
    }
    flags.update({"A3": True, "B1": True, "Hom1": True})
    out = conjunctions(flags)
    assert out["Q1"] is True
    assert out["Q3"] is True
    assert out["Q7"] is True
    assert out["cont_votes"] == 3
    flags2 = dict(flags)
    flags2.update({"A3": False, "B1": False, "Hom1": False, "A2": True, "F1": True, "F3": True})
    out2 = conjunctions(flags2)
    assert out2["Q2"] is True
    assert out2["Q8"] is True


def test_features_for_cell_shape(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["A1"] = 2020
        sheet["B1"] = 2021
        sheet["C1"] = 2022
        sheet["D1"] = 2023
        sheet["A2"] = 1
        sheet["B2"] = "=A2"
        sheet["C2"] = "=B2"
        sheet["A3"] = 1
        sheet["B3"] = "=A3"
        sheet["C3"] = "=B3"
        sheet["D3"] = "=C3"
        sheet["E3"] = "=D3"
        sheet["D4"] = "=D2"
        sheet["Z10"] = 1

    graph = build_graph(_save(tmp_path, fill))
    key = ("M", 4, 2)
    occ = build_occupancy_peers(graph.occupancy, {key})
    extent = build_extent(graph.occupancy["M"])
    feat = features_for_cell(
        graph,
        key,
        occ,
        extent,
        None,
        {},
        {"last_active_col": 3, "blank_tail": 4},
    )
    assert set(CONJUNCTIONS) <= set(feat["flags"])
    for name in ("A1", "A2", "A3", "B1", "Hom1", "D1", "D4", "Q1", "Q9"):
        assert name in feat["flags"]
    assert feat["G"]["distance"] == 1
    assert "formula" not in feat["D"]
