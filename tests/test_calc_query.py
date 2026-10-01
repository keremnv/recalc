from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

from calc_query import (  # noqa: E402
    MODES,
    MAX_ROWS,
    refuse_gold,
    run_query,
)


def _xlsx(tmp_path: Path) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Model"
    sheet["A1"] = "Line"
    sheet["B1"] = "FY26"
    sheet["C1"] = "FY27"
    sheet["A2"] = "Revenue"
    sheet["B2"] = "=B3"
    sheet["C2"] = "=C3"
    sheet["A3"] = "Volume"
    sheet["B3"] = 10
    sheet["C3"] = 12
    path = tmp_path / "book.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_gold_paths_are_refused(tmp_path: Path) -> None:
    gold = tmp_path / "golden_response.xlsx"
    gold.write_bytes(b"not-an-xlsx")
    assert refuse_gold(gold) == "GOLD_PATH_REFUSED"
    payload = run_query(gold, "inspect", sheet="Model", target="A1")
    assert payload["status"] == "GOLD_PATH_REFUSED"


def test_modes_are_read_only_deterministic_and_bounded(tmp_path: Path) -> None:
    path = _xlsx(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    first = run_query(path, "inspect", sheet="Model", target="B2", cache_root=tmp_path / "cache")
    second = run_query(path, "inspect", sheet="Model", target="B2", cache_root=tmp_path / "cache")
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after
    assert first == second
    assert first["edit_authority"] is False
    assert first["should_edit"] is None
    assert first["status"] == "OK"
    assert first["cells"][0]["display"] == "Model!B2"
    assert first["cells"][0]["formula"] == "=B3"
    assert "table_body" not in first
    assert "should_edit" in first

    search = run_query(path, "search", text="Revenue", cache_root=tmp_path / "cache")
    assert search["hits"]
    assert search["hits"][0]["display"] == "Model!A2"
    assert search["hits"][0]["fact_kind"] == "raw_text_anchor"

    periods = run_query(path, "periods", cache_root=tmp_path / "cache")
    assert periods["status"] == "OK"
    assert periods["edit_authority"] is False
    years = {row.get("year") for row in periods["coordinates"] if row.get("year")}
    assert 2026 in years or any("FY26" in str(row.get("header_text") or "") for row in periods["coordinates"])

    refs = run_query(path, "references", sheet="Model", target="B2", cache_root=tmp_path / "cache")
    assert refs["status"] == "OK"
    assert any(item["display"] == "Model!B3" for item in refs["precedents"])

    pattern = run_query(path, "formula_pattern", sheet="Model", target="B2", cache_root=tmp_path / "cache")
    assert pattern["status"] == "OK"
    assert "homogeneous" in pattern["note"].lower() or "not a claim" in pattern["note"].lower()

    analogues = run_query(path, "analogues", sheet="Model", target="B2", cache_root=tmp_path / "cache")
    assert analogues["status"] == "OK"
    assert any(item["display"] == "Model!C2" for item in analogues["analogues"])
    assert "not a recommended edit formula" in analogues["note"].lower()
    dumped = json.dumps(analogues)
    assert "should be edited" not in dumped.lower()
    assert len(json.dumps(first)) < 200_000
    assert set(MODES) == {"inspect", "search", "periods", "references", "formula_pattern", "analogues"}
    assert MAX_ROWS == 64


def test_missing_relation_is_explicit(tmp_path: Path) -> None:
    path = _xlsx(tmp_path)
    payload = run_query(path, "inspect", sheet="Missing", target="Z99", cache_root=tmp_path / "cache")
    assert payload["status"] == "NOT_AVAILABLE"
    assert "not" in payload["reason"].lower()
    unknown = run_query(path, "search", text="", cache_root=tmp_path / "cache")
    assert unknown["status"] == "NOT_AVAILABLE"


def test_does_not_invent_table_body_extent(tmp_path: Path) -> None:
    path = _xlsx(tmp_path)
    for mode in MODES:
        kwargs = {}
        if mode in {"inspect", "references", "formula_pattern", "analogues"}:
            kwargs = {"sheet": "Model", "target": "A1"}
        elif mode == "search":
            kwargs = {"text": "table body"}
        payload = run_query(path, mode, cache_root=tmp_path / "cache", **kwargs)
        blob = json.dumps(payload)
        assert "table_body" not in payload
        assert "implicit_table" not in blob
        assert payload.get("should_edit") is None
        assert payload.get("edit_authority") is False
