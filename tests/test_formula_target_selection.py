"""Unit tests for occupancy-topology target selectors and slice selection."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

from formula_target_selection import (  # noqa: E402
    FEATURE_KEYS,
    occupancy_from_cells,
    occupancy_from_grid,
    select_on_grids,
    select_probe_slice,
    select_s1,
    select_s2,
    select_s3,
    select_s4,
    select_s5,
    select_s6,
)
from formula_completion_certs import load_grids  # noqa: E402


def _keys(hits) -> set[tuple[int, int]]:
    return {(hit.col, hit.row) for hit in hits}


def test_s1_interior_hole_horizontal_not_value_terminated() -> None:
    grid = occupancy_from_cells(
        "M",
        {
            (1, 1): "F",
            (3, 1): "F",
            (5, 1): "F",
            (1, 2): "F",
            (2, 2): "V",
            (3, 2): "F",
        },
    )
    hits = select_s1(grid)
    assert (2, 1) in _keys(hits)
    assert (4, 1) in _keys(hits)
    assert (2, 2) not in _keys(hits)
    horizontal = next(hit for hit in hits if (hit.col, hit.row) == (2, 1))
    assert horizontal.meta["axes"] == ["horizontal"]
    assert horizontal.meta["horizontal"]["distance_to_supports"] == [1, 1]
    assert horizontal.meta["horizontal"]["span_length"] == 3


def test_s1_opaque_formula_is_support() -> None:
    grid = occupancy_from_cells("M", {(1, 5): "O", (3, 5): "F"})
    assert (2, 5) in _keys(select_s1(grid))


def test_s2_requires_both_axes() -> None:
    grid = occupancy_from_cells(
        "M",
        {
            (2, 1): "F",
            (1, 2): "F",
            (3, 2): "F",
            (2, 3): "F",
            (5, 5): "F",
            (7, 5): "F",
        },
    )
    s1 = select_s1(grid)
    s2 = select_s2(s1)
    assert _keys(s1) == {(2, 2), (6, 5)}
    assert _keys(s2) == {(2, 2)}


def test_s3_density_thresholds_are_predeclared() -> None:
    cells = {(col, row): "F" for col in range(1, 4) for row in range(1, 4)}
    cells.pop((2, 2))
    grid = occupancy_from_cells("M", cells)
    assert (2, 2) in _keys(select_s3(grid, 0.70))
    assert (2, 2) in _keys(select_s3(grid, 0.80))
    assert (2, 2) not in _keys(select_s3(grid, 0.90))


def test_s3_sparse_bbox_is_not_a_region() -> None:
    grid = occupancy_from_cells(
        "M",
        {(1, 1): "F", (8, 1): "F", (1, 8): "F", (8, 8): "F", (4, 1): "F",
         (1, 4): "F", (8, 4): "F", (4, 8): "F"},
    )
    assert select_s3(grid, 0.70) == []


def test_s4_repeated_row_blank_with_two_supports() -> None:
    cells = {}
    for row, pattern in enumerate(
        ["FFFFF", "FFFBF", "FFFFF", "FFFFF"],
        start=1,
    ):
        for col, token in enumerate(pattern, start=1):
            if token == "F":
                cells[(col, row)] = "F"
    grid = occupancy_from_cells("M", cells)
    hits = select_s4(grid)
    assert _keys(hits) == {(4, 2)}
    assert hits[0].meta["support"] == 3


def test_s4_does_not_match_across_value_disagreement() -> None:
    cells = {
        (1, 1): "F",
        (2, 1): "F",
        (3, 1): "F",
        (1, 2): "F",
        (2, 2): "V",
        (3, 2): "F",
        (1, 3): "F",
        (3, 3): "F",
    }
    grid = occupancy_from_cells("M", cells)
    assert select_s4(grid) == []


def test_s5_repeated_column_analogue() -> None:
    cells = {}
    for col, pattern in enumerate(["FFFF", "FFBF", "FFFF"], start=1):
        for row, token in enumerate(pattern, start=1):
            if token == "F":
                cells[(col, row)] = "F"
    grid = occupancy_from_cells("M", cells)
    assert _keys(select_s5(grid)) == {(2, 3)}


def test_s6_singleton_and_k_thresholds() -> None:
    cells = {}
    for row, pattern in enumerate(["FFF", "FFF", "FBF", "FFF"], start=1):
        for col, token in enumerate(pattern, start=1):
            if token == "F":
                cells[(col, row)] = "F"
    grid = occupancy_from_cells("M", cells)
    assert _keys(select_s6(grid, 2)) == {(2, 3)}
    assert _keys(select_s6(grid, 3)) == {(2, 3)}
    assert _keys(select_s6(grid, 4)) == set()


def test_s6_rejects_two_identical_holes() -> None:
    cells = {}
    for row, pattern in enumerate(["FFFFF", "FFFBF", "FFFBF", "FFFFF"], start=1):
        for col, token in enumerate(pattern, start=1):
            if token == "F":
                cells[(col, row)] = "F"
    grid = occupancy_from_cells("M", cells)
    assert _keys(select_s4(grid)) == {(4, 2), (4, 3)}
    assert select_s6(grid, 2) == []


def test_select_on_grids_names() -> None:
    grid = occupancy_from_cells("M", {(1, 1): "F", (3, 1): "F"})
    selected = select_on_grids([grid])
    assert set(selected) == {
        "S1",
        "S2",
        "S3_70",
        "S3_80",
        "S3_90",
        "S4",
        "S5",
        "S6_2",
        "S6_3",
        "S6_4",
    }
    assert _keys(selected["S1"]) == {(2, 1)}


def test_occupancy_from_real_grid_distinguishes_opaque(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "M"
    sheet["A1"] = "=B1"
    sheet["C1"] = '=INDIRECT("C2")'
    sheet["A2"] = 9
    path = tmp_path / "in.xlsx"
    workbook.save(path)
    workbook.close()
    occ = occupancy_from_grid(load_grids(path)[0])
    assert occ.kind(1, 1) == "F"
    assert occ.kind(3, 1) == "O"
    assert occ.kind(1, 2) == "V"
    assert occ.kind(2, 1) == "B"


def _fake_row(task_id: str, family: str, k2: int, **extra: float) -> dict:
    row = {
        "id": task_id,
        "family": family,
        "error": None,
        "formula_cells": extra.get("formula_cells", k2),
        "sheets": extra.get("sheets", 10),
        "n_lr": extra.get("n_lr", k2 // 10),
        "n_ud": extra.get("n_ud", k2 // 5),
        "n_k2": k2,
        "n_k2_conflicts": extra.get("n_k2_conflicts", k2 // 2),
        "horiz_share": extra.get("horiz_share", 0.5),
        "formulas_per_sheet": extra.get("formula_cells", k2) / extra.get("sheets", 10),
        "log_file_size": extra.get("log_file_size", 10.0),
        "lr_share": extra.get("lr_share", 0.3),
        "conflict_rate": extra.get("conflict_rate", 0.4),
        "volume": __import__("math").log1p(k2),
        "file_size": 1000,
    }
    for key in FEATURE_KEYS:
        assert key in row
    return row


def test_slice_selection_is_deterministic_and_family_diverse() -> None:
    rows = []
    for family in range(1, 21):
        for variant, k2 in enumerate((10, 1000, 50000), start=1):
            sheets = 3 + family
            rows.append(
                _fake_row(
                    f"{family:02d}_{variant:02d}",
                    f"{family:02d}_Project",
                    k2 + family,
                    sheets=sheets,
                    horiz_share=(family % 5) / 5,
                    n_k2_conflicts=family * 100,
                    log_file_size=8 + family / 4,
                )
            )
    first = select_probe_slice(rows)
    second = select_probe_slice(rows)
    assert [row["id"] for row in first] == [row["id"] for row in second]
    assert len(first) == 12
    assert len({row["family"] for row in first}) == 12
    counts = {}
    for row in first:
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
    assert counts["dense_high_candidate"] == 3
    assert counts["medium"] == 3
    assert counts["sparse_low_candidate"] == 3
    assert counts["unusual_extreme"] == 3


def test_unreadable_workbooks_are_excluded_from_the_slice() -> None:
    rows = [
        _fake_row("06_01", "06_Project", 0),
        _fake_row("01_01", "01_Project", 10),
        _fake_row("02_01", "02_Project", 20),
        _fake_row("03_01", "03_Project", 30),
        _fake_row("04_01", "04_Project", 40),
        _fake_row("05_01", "05_Project", 50),
        _fake_row("07_01", "07_Project", 60),
        _fake_row("08_01", "08_Project", 70),
        _fake_row("09_01", "09_Project", 80),
        _fake_row("10_01", "10_Project", 90),
        _fake_row("11_01", "11_Project", 100),
        _fake_row("12_01", "12_Project", 110),
        _fake_row("13_01", "13_Project", 120),
    ]
    rows[0]["error"] = "XMLSyntaxError"
    selected = select_probe_slice(rows)
    assert all(row["id"] != "06_01" for row in selected)
    assert len(selected) == 12
