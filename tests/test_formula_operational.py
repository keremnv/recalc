"""Unit tests for gold-blind operational dependence structure."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))

import formula_operational_probe  # noqa: E402
from formula_dependency_selection import build_graph  # noqa: E402
from formula_operational import (  # noqa: E402
    DEFINITIONS,
    aggregate_templates,
    build_view,
    collect_peers,
    cycle_if_added,
    parse_use_def_slots,
    reduction_of,
    template_match,
)
from formula_operational_probe import classify_object, discriminate_edge  # noqa: E402
from formula_schema_probe import align_refs, parse_refs  # noqa: E402


def _save(tmp_path: Path, fill) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Assumptions"
    fill(sheet, workbook)
    path = tmp_path / "in.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_definitions_and_extract_are_gold_blind() -> None:
    assert DEFINITIONS["golden_in_generation"] is False
    source = inspect.getsource(sys.modules["formula_operational"])
    assert "_golden_path" not in source
    assert "eval_golden_formula" not in source
    freeze_src = inspect.getsource(formula_operational_probe.cmd_extract)
    assert "_golden_path" not in freeze_src
    assert "eval_golden_formula" not in freeze_src


def test_use_def_slots_keep_order_and_operators() -> None:
    parsed = parse_use_def_slots("=J6*(1+K12)", "Assumptions", 11, 6)
    assert len(parsed["slots"]) == 2
    assert parsed["slots"][0]["start"] == "J6"
    assert parsed["slots"][1]["start"] == "K12"
    assert parsed["slots"][0]["enclosing"]["op"] == "*"
    assert parsed["slots"][1]["enclosing"]["op"] == "+"
    assert parsed["slots"][0]["dcol"] == -1
    assert parsed["slots"][0]["drow"] == 0
    assert parsed["slots"][1]["dcol"] == 0
    assert parsed["slots"][1]["drow"] == 6
    assert parsed["literals"] == [1]


def test_enclosing_sum_range_and_abs_mask() -> None:
    parsed = parse_use_def_slots("=SUM($C$8,AF64)*0.3", "IS", 32, 66)
    assert parsed["slots"][0]["is_range"] is False
    assert parsed["slots"][0]["abs_mask"] == "$$"
    assert parsed["slots"][0]["enclosing"]["func"] == "SUM"
    assert parsed["slots"][1]["abs_mask"] == "CR"
    assert 0.3 in parsed["literals"]


def test_reduction_sum_vs_explicit_plus() -> None:
    gold = reduction_of("=SUM(J44:J45)", parse_use_def_slots("=SUM(J44:J45)", "WC", 10, 46))
    model = reduction_of("=+J37+J28+J17+J8", parse_use_def_slots("=+J37+J28+J17+J8", "WC", 10, 46))
    assert gold["operator"] == "SUM"
    assert gold["contiguous"] is True
    assert gold["is_reduction"] is True
    assert model["operator"] == "explicit_+"
    assert model["contiguous"] is False
    assert model["operand_count"] == 4


def test_cycle_if_added_is_precedent_to_dependent(tmp_path: Path) -> None:
    def fill(sheet, wb) -> None:
        other = wb.create_sheet("Financials")
        sheet["K163"] = None
        other["K82"] = "=Assumptions!K163"
        sheet["J163"] = "=Financials!J82"
        other["J82"] = 10
        sheet["K164"] = 0.05
        sheet["K18"] = 100

    graph = build_graph(_save(tmp_path, fill))
    view = build_view(graph)
    target = ("Assumptions", 11, 163)
    wrong = ("Financials", 11, 82)
    gold = ("Assumptions", 11, 164)
    wrong_cycle = cycle_if_added(view, wrong, target)
    gold_cycle = cycle_if_added(view, gold, target)
    assert wrong_cycle["C1_direct_downstream_conflict"] is True
    assert wrong_cycle["C3_cycle_if_added"] is True
    assert wrong_cycle["shortest_T_to_S"] == ["Assumptions!K163", "Financials!K82"]
    assert gold_cycle["C3_cycle_if_added"] is False


def test_peer_template_matches_translated_vector(tmp_path: Path) -> None:
    def fill(sheet, _wb) -> None:
        sheet["J6"] = "=I6*(1+J27)"
        sheet["K6"] = None
        sheet["L6"] = "=K6*(1+L27)"
        sheet["J27"] = 0.1
        sheet["K12"] = 0.2
        sheet["K27"] = 0.3
        sheet["L27"] = 0.1

    graph = build_graph(_save(tmp_path, fill))
    view = build_view(graph)
    peers = collect_peers(view, "Assumptions", 11, 6)
    assert peers["n_p1"] == 2
    gold_slot = parse_use_def_slots("=J6*(1+K27)", "Assumptions", 11, 6)["slots"][1]
    model_slot = parse_use_def_slots("=J6*(1+K12)", "Assumptions", 11, 6)["slots"][1]
    target = ("Assumptions", 11, 6)
    gold_matches = [
        template_match(peer, gold_slot, ("Assumptions", 11, 27), target, view)
        for peer in peers["formula_peers"]
        if peer["provenance"] == "P1"
    ]
    model_matches = [
        template_match(peer, model_slot, ("Assumptions", 11, 12), target, view)
        for peer in peers["formula_peers"]
        if peer["provenance"] == "P1"
    ]
    gold_agg = aggregate_templates(gold_matches)
    model_agg = aggregate_templates(model_matches)
    assert gold_agg["n_vector_and_sheet"] >= 1
    assert gold_agg["n_T5"] >= 1
    assert model_agg["n_T5"] == 0


def test_object_types_and_no_gold_break() -> None:
    aligned_red = align_refs(
        parse_refs("=+J37+J28+J17+J8", "WC"),
        parse_refs("=+SUM(J44:J45)", "WC"),
    )
    assert classify_object("=+J37+J28+J17+J8", "=+SUM(J44:J45)", aligned_red) == "REDUCTION_CHOICE"
    aligned_edge = align_refs(parse_refs("=J6*(1+K12)", "A"), parse_refs("=J6*(1+K27)", "A"))
    assert classify_object("=J6*(1+K12)", "=J6*(1+K27)", aligned_edge) == "EDGE_CHOICE"
    aligned_lit = align_refs(
        parse_refs("=IF(AF64>0,AF64*0.3,0)", "IS"),
        parse_refs("=IF(AF64>0,AF64*'Assumptions - Company Level'!$C$8,0)", "IS"),
    )
    assert (
        classify_object(
            "=IF(AF64>0,AF64*0.3,0)",
            "=IF(AF64>0,AF64*'Assumptions - Company Level'!$C$8,0)",
            aligned_lit,
        )
        == "LITERAL_REFERENCE_CHOICE"
    )
    tied = discriminate_edge(
        {
            "cycle": {"C3_cycle_if_added": False},
            "template": {
                "n": 0,
                "n_strict": 0,
                "n_vector_and_sheet": 0,
                "peer_conflict": False,
            },
            "orient_strong": False,
            "missing": False,
        },
        {
            "cycle": {"C3_cycle_if_added": False},
            "template": {
                "n": 0,
                "n_strict": 0,
                "n_vector_and_sheet": 0,
                "peer_conflict": False,
            },
            "orient_strong": False,
            "missing": False,
        },
    )
    assert tied == "TIE"
    cycle_gold = discriminate_edge(
        {
            "cycle": {"C3_cycle_if_added": False},
            "template": {
                "n": 0,
                "n_strict": 0,
                "n_vector_and_sheet": 0,
                "peer_conflict": False,
            },
            "orient_strong": False,
            "missing": False,
        },
        {
            "cycle": {"C3_cycle_if_added": True},
            "template": {
                "n": 0,
                "n_strict": 0,
                "n_vector_and_sheet": 0,
                "peer_conflict": False,
            },
            "orient_strong": False,
            "missing": False,
        },
    )
    assert cycle_gold == "CLEAR_OPERATIONAL_GOLD"
