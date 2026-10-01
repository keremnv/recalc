"""Unit tests for gold-blind TEMPORAL_SPINE_V2 extraction."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from temporal_spine import ALL_FEATURES, compile_temporal_workbook, coordinates_as_periods  # noqa: E402
from workbook_grounding import parse_scope_spec, retrieve_scope  # noqa: E402


def _save(tmp_path: Path, build) -> Path:
    workbook = openpyxl.Workbook()
    build(workbook)
    path = tmp_path / "in.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_date_serial_with_format(tmp_path: Path) -> None:
    def build(wb):
        sheet = wb.active
        sheet.title = "IS"
        sheet["A1"] = "Item"
        sheet["B1"] = 45100  # ~2023-06-23 in Excel 1900
        sheet["B1"].number_format = "MMM-YY"
        sheet["A2"] = "Revenue"
        sheet["B2"] = None

    compiled = compile_temporal_workbook(_save(tmp_path, build), features=set(ALL_FEATURES))
    assert compiled["readable"]
    years = {c["period"].get("year") for c in compiled["coordinates"] if c["axis"] == "column"}
    assert 2023 in years


def test_date_serial_not_inferred_without_format(tmp_path: Path) -> None:
    def build(wb):
        sheet = wb.active
        sheet["A1"] = "qty"
        sheet["B1"] = 45100
        sheet["B1"].number_format = "0"

    compiled = compile_temporal_workbook(_save(tmp_path, build), features=set(ALL_FEATURES))
    assert not any(c["period"].get("year") == 2023 for c in compiled["coordinates"])


def test_merged_year_and_month_row(tmp_path: Path) -> None:
    def build(wb):
        sheet = wb.active
        sheet["A1"] = "Item"
        sheet["B1"] = 2025
        sheet.merge_cells("B1:E1")
        sheet["B2"] = "Jan"
        sheet["C2"] = "Feb"
        sheet["D2"] = "Mar"
        sheet["E2"] = "Apr"
        sheet["A3"] = "Receivables"

    compiled = compile_temporal_workbook(_save(tmp_path, build), features=set(ALL_FEATURES))
    cols = {c["col"]: c["period"] for c in compiled["coordinates"] if c["axis"] == "column"}
    assert cols[3].get("year") == 2025
    assert cols[3].get("month") == 2
    assert any("MERGED_HEADER_PROPAGATION" in c["encoding_class"] for c in compiled["coordinates"])
    assert any("MULTIROW_HEADER_COMPOSITION" in c["encoding_class"] for c in compiled["coordinates"])


def test_edate_chain(tmp_path: Path) -> None:
    def build(wb):
        sheet = wb.active
        sheet["B1"] = dt.datetime(2023, 8, 1)
        sheet["C1"] = "=EDATE(B1,1)"
        sheet["D1"] = "=EDATE(C1,1)"

    compiled = compile_temporal_workbook(_save(tmp_path, build), features=set(ALL_FEATURES))
    months = {
        c["col"]: (c["period"].get("year"), c["period"].get("month"))
        for c in compiled["coordinates"]
        if c["axis"] == "column"
    }
    assert months.get(2) == (2023, 8)
    assert months.get(3) == (2023, 9)
    assert months.get(4) == (2023, 10)


def test_row_axis_years(tmp_path: Path) -> None:
    def build(wb):
        sheet = wb.active
        sheet["A1"] = "Year"
        sheet["B1"] = "Revenue"
        sheet["A2"] = 2024
        sheet["A3"] = 2025
        sheet["B2"] = None
        sheet["B3"] = None

    compiled = compile_temporal_workbook(_save(tmp_path, build), features=set(ALL_FEATURES))
    rows = [c for c in compiled["coordinates"] if c["axis"] == "row" and c["period"].get("year") == 2025]
    assert rows


def test_v2_periods_feed_frozen_retrieval(tmp_path: Path) -> None:
    def build(wb):
        sheet = wb.active
        sheet.title = "Working Capital"
        sheet["A1"] = "Item"
        sheet["B1"] = 2026
        sheet["C1"] = 2027
        sheet["A2"] = "Receivables"

    compiled = compile_temporal_workbook(_save(tmp_path, build), features=set(ALL_FEATURES))
    spine = {
        "sheets": [{"id": "sheet:s00", "title": "Working Capital"}],
        "periods": coordinates_as_periods(compiled),
        "text_anchors": [],
        "occupied": [],
    }
    ob = {"scope": [{"text": "for 2026E–2030E"}]}
    hits = retrieve_scope(spine, ob)
    years = {h["period"]["year"] for h in hits if h.get("period")}
    assert 2026 in years
    assert parse_scope_spec(ob)["years"][0] == 2026
