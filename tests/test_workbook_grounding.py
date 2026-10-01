"""Unit tests for closed-world workbook grounding spine and retrieval."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from workbook_grounding import (  # noqa: E402
    lexical_hit,
    project_obligation,
    retrieve_locus,
    validate_resolution,
)
from workbook_grounding_spine import (  # noqa: E402
    RETRIEVAL_RULES,
    compact_text,
    compile_spine,
    id_in_spine,
    title_initials,
)


def _wb(tmp_path: Path) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Balance Sheet Schedules"
    sheet["A1"] = "Line item"
    sheet["B1"] = "2026E"
    sheet["C1"] = "2027E"
    sheet["A2"] = "Accounts Receivable"
    sheet["B2"] = None
    sheet["C2"] = None
    sheet["A3"] = "Total WC"
    sheet["B3"] = "=B2"
    other = workbook.create_sheet("P&L – Segment 1")
    other["A1"] = "PBT Margin"
    other["B1"] = "2021A"
    path = tmp_path / "in.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_compact_alias_is_mechanical_not_golden() -> None:
    assert compact_text("Balancesheet Schedules") == compact_text("Balance Sheet Schedules")
    assert compact_text("P&L – Segment 1") == compact_text("P&L - Segment 1")
    initials = title_initials("Cash Flow Statement")
    assert "cfs" in initials or "cf" in initials
    assert RETRIEVAL_RULES["gold_filter"] is False
    assert RETRIEVAL_RULES["top_k"] is False
    assert RETRIEVAL_RULES["finance_synonyms"] is False


def test_spine_assigns_stable_ids_and_used_range_blanks(tmp_path: Path) -> None:
    spine = compile_spine(_wb(tmp_path), workbook_key="t1")
    assert spine["readable"]
    titles = {s["title"]: s["id"] for s in spine["sheets"]}
    assert "Balance Sheet Schedules" in titles
    assert any(a["text"] == "Accounts Receivable" for a in spine["text_anchors"])
    assert any(p.get("period") and p["period"].get("year") == 2026 for p in spine["periods"])
    bss = titles["Balance Sheet Schedules"]
    s_i = int(bss.rsplit("s", 1)[1])
    blank = f"cell:s{s_i:02d}:r2:c2"
    assert id_in_spine(spine, blank)
    assert not id_in_spine(spine, "sheet:Tax Assumptions")
    assert not id_in_spine(spine, "cell:s99:r1:c1")


def test_locus_retrieval_uses_compact_and_dash_normalization(tmp_path: Path) -> None:
    spine = compile_spine(_wb(tmp_path), workbook_key="t1")
    ob = {
        "id": "O1",
        "locus": {"text": "In the Balancesheet Schedules sheet"},
        "subject": {"text": "Accounts Receivable"},
        "scope": [{"text": "for 2026E–2030E"}],
        "source_relation": None,
        "occupancy_filter": None,
        "subject_interval": None,
        "required_change": {"text": "calculate"},
    }
    hits = retrieve_locus(spine, ob)
    assert any("Balance Sheet" in h["title"] for h in hits)
    packet = project_obligation(spine, ob)
    assert packet["locus"]
    assert any(h["text"] == "Accounts Receivable" for h in packet["subject"])
    assert packet["scope"]
    assert packet["target_cell_ids"]


def test_resolver_cannot_invent_entities(tmp_path: Path) -> None:
    spine = compile_spine(_wb(tmp_path), workbook_key="t1")
    ob = {
        "id": "O1",
        "locus": {"text": "Balance Sheet Schedules"},
        "subject": {"text": "Accounts Receivable"},
        "scope": [{"text": "for 2026E"}],
        "source_relation": None,
        "occupancy_filter": None,
        "subject_interval": None,
        "required_change": {"text": "calculate"},
    }
    packet = project_obligation(spine, ob)
    fake = {
        "locus": {"status": "RESOLVED", "candidate_ids": ["sheet:Tax Assumptions"]},
        "subject": {"status": "UNRESOLVED", "candidate_ids": []},
        "subject_interval": {"status": "UNRESOLVED", "candidate_ids": []},
        "scope": {"status": "UNRESOLVED", "candidate_ids": []},
        "source_relation_arguments": {"status": "UNRESOLVED", "candidate_ids": []},
        "target_region": {"status": "RESOLVED", "candidate_ids": ["cell:s00:r2:c2"]},
    }
    checked = validate_resolution(fake, packet)
    assert "sheet:Tax Assumptions" in checked["invalid"]
    assert checked["fields"]["locus"]["status"] == "UNRESOLVED"


def test_lexical_hit_is_permissive_without_synonyms() -> None:
    assert lexical_hit("Receivables", "Accounts Receivable")
    assert lexical_hit("Working Capital Schedule", "Working Capital Schedule sheet")
    assert lexical_hit("revenue", "sales") is None


def test_scope_spec_parses_month_year_and_rejects_anaphora() -> None:
    from workbook_grounding import parse_scope_spec

    interval = parse_scope_spec({"scope": [{"text": "for Aug-23 to Dec-28"}]})
    assert 2023 in interval["years"] and 2028 in interval["years"]
    anaphora = parse_scope_spec({"scope": [{"text": "for the same timeframe"}]})
    assert not anaphora["years"] and not anaphora["all"] and not anaphora["months"]
    quant = parse_scope_spec({"scope": [{"text": "for all years"}]})
    assert quant["all"] is True
