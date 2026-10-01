"""Unit tests for task-obligation shape discovery primitives."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))

from task_obligation_shape import (  # noqa: E402
    SPLIT_SEED,
    cluster_changes,
    explicit_preservation_spans,
    family_of,
    golden_delta,
    is_semantic_change,
    make_family_split,
    weak_clauses,
)


def test_family_split_is_deterministic_and_disjoint() -> None:
    a = make_family_split(SPLIT_SEED)
    b = make_family_split(SPLIT_SEED)
    assert a["discovery_families"] == b["discovery_families"]
    assert a["validation_families"] == b["validation_families"]
    assert a["held_out_families"] == b["held_out_families"]
    disco = set(a["discovery_families"])
    val = set(a["validation_families"])
    held = set(a["held_out_families"])
    assert len(disco) == 10 and len(val) == 5 and len(held) == 5
    assert not (disco & val) and not (disco & held) and not (val & held)
    assert disco | val | held == {f"{i:02d}" for i in range(1, 21)}
    assert family_of("09_05") == "09"


def test_weak_clauses_preserve_exact_spans() -> None:
    text = (
        "Complete the financial model based on the provided assumptions. "
        "Ensure the existing structure, layout, and formatting of the model are preserved throughout the process.\n"
        "Complete the revenue forecast for 2025 through 2029 using the growth assumptions."
    )
    clauses = weak_clauses(text)
    assert clauses
    for clause in clauses:
        span = clause["exact_source_span"]
        assert text[span["start"] : span["end"]] == span["text"]
        if clause["predicate_span"]:
            pred = clause["predicate_span"]
            assert text[pred["start"] : pred["end"]] == pred["text"]
    assert explicit_preservation_spans(text)
    forecast = [c for c in clauses if "revenue forecast" in c["exact_source_span"]["text"]]
    assert forecast
    assert any("2025 through 2029" in (m.get("text") or "") for c in forecast for m in c["modifier_spans"]) or any(
        "2025 through 2029" in (a.get("text") or "") for c in forecast for a in c["argument_spans"] + c["modifier_spans"]
    )


def test_golden_delta_ignores_identical_formulas(tmp_path: Path) -> None:
    def save(name: str, fill) -> Path:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Assumptions"
        fill(sheet)
        path = tmp_path / name
        workbook.save(path)
        workbook.close()
        return path

    def fill_in(sheet) -> None:
        sheet["K7"] = "=A1"

    def fill_gold(sheet) -> None:
        sheet["K6"] = "=J6*(1+K27)"
        sheet["K7"] = "=A1"

    delta = golden_delta("04_05", save("in.xlsx", fill_in), save("gold.xlsx", fill_gold))
    kinds = {row["address"]: row["change_kind"] for row in delta["changes"]}
    assert kinds["K6"] == "blank→formula"
    assert "K7" not in kinds


def test_float_noise_is_not_semantic() -> None:
    assert not is_semantic_change(
        {
            "input_payload": "23.170585269835776",
            "golden_payload": "23.1705852698358",
            "change_kind": "value→value_changed",
        }
    )
    assert not is_semantic_change(
        {"input_payload": "#N/A", "golden_payload": "=#N/A", "change_kind": "value→formula"}
    )
    assert is_semantic_change(
        {"input_payload": None, "golden_payload": "=A1", "change_kind": "blank→formula"}
    )


def test_clusters_group_horizontal_runs() -> None:
    changes = [
        {
            "sheet": "IS",
            "col": col,
            "row": 10,
            "address": f"col{col}",
            "change_kind": "blank→formula",
            "golden_formula_fingerprint": "abc",
            "refs_added": ["IS!A1"],
        }
        for col in (5, 6, 7)
    ]
    clusters = cluster_changes(changes)
    assert clusters["n_horizontal_runs"] == 1
    assert clusters["contiguous_horizontal"][0] == [0, 1, 2]
