from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from benchmark.catalog_gate import (
    NOISE,
    REFUTED_LEVER,
    SHARED,
    SURVIVES,
    UNJUDGED,
    _blank_is_decidable,
    cell_verdict,
    judge_case,
    load_arms,
    min_misses,
    parse_answer,
    split_address,
    values_agree,
)
from benchmark.pattern_catalog import CATALOG, load_cases

ARMS = {
    "control": ["ctrl-1", "ctrl-2"],
    "ours": ["ours-1", "ours-2", "ours-3"],
    "levers": {"information": "refuted", "constraint": "untested"},
}


def _write_run(
    runs_dir: Path, name: str, task: str, cells: dict[str, Any] | None, mod: float = 0.99
) -> None:
    """A stored run with one scored task and, unless `cells` is None, one output workbook."""

    run_dir = runs_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "official_scores.json").write_text(
        json.dumps(
            {
                "tasks": {
                    task: {
                        "modification_accuracy": mod,
                        "regression_accuracy": 1.0,
                        "accuracy": 0.0,
                        "error_message": "",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    if cells is None:
        return
    category, _, task_id = task.partition(":")
    out = run_dir / "submission" / "outputs" / category
    out.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Model"
    for address, value in cells.items():
        sheet[address] = value
    workbook.save(out / f"{task_id}_output.xlsx")


def _case(**claims: Any) -> dict[str, Any]:
    return {
        "id": "x-1",
        "run": "ours-1",
        "task": "Template:01_01",
        "first_miss": {
            "kind": "modification",
            "address": "Model!B2",
            "error_message": "Modification error at Model!B2: answer=42, output=7",
        },
        "claims": claims,
    }


def test_parse_answer_reads_both_error_kinds_and_declines_the_rest() -> None:
    assert parse_answer("Modification error at Model!B2: answer=42, output=7") == "42"
    assert parse_answer("Regression error at Ex 1 - LBO!AC20: answer=0, output=-130.6") == "0"
    assert parse_answer("output file not exist") is None
    assert parse_answer("") is None


def test_parse_answer_keeps_a_formula_answer_that_contains_output() -> None:
    message = 'Regression error at S!C36: answer==A1&", output=x", output==A1'
    assert parse_answer(message) == '=A1&", output=x"'


def test_split_address_keeps_spaces_and_dashes_in_the_sheet_name() -> None:
    assert split_address("Ex 1 - LBO!C11") == ("Ex 1 - LBO", "C11")
    assert split_address("Valuation Band!m4") == ("Valuation Band", "M4")


def test_values_agree_on_float_noise_and_on_text() -> None:
    assert values_agree("0.273318647267128", 0.2733186472671281)
    assert not values_agree("0.2733", 0.2951)
    assert values_agree("Total", "total ")
    assert not values_agree("42", None)


def test_min_misses_is_the_smallest_consistent_miss_count() -> None:
    assert min_misses(1.0) == 0
    assert min_misses(0.8723) == 6  # 41/47
    assert min_misses(0.9995) == 1
    assert min_misses(None) is None


def test_min_misses_is_a_lower_bound_so_a_far_task_stays_far() -> None:
    # 0.3572 cannot be reached by any small denominator with few misses.
    assert min_misses(0.3572) >= 9


def test_min_misses_understates_rather_than_overstates() -> None:
    """It is a bound, not a count: 0.5 is one miss in two as readily as fifty in a hundred.

    The gate only ever rejects on this number, so a weak bound costs coverage and never
    manufactures a `far` verdict.
    """

    assert min_misses(0.5) == 1


def test_blank_output_is_a_miss_unless_the_answer_is_itself_zero() -> None:
    assert _blank_is_decidable("42")
    assert _blank_is_decidable("Total")
    assert not _blank_is_decidable("0")
    assert not _blank_is_decidable("")


def test_cell_verdict_reports_a_missing_output_rather_than_a_miss(tmp_path: Path) -> None:
    _write_run(tmp_path, "ours-1", "Template:01_01", None)
    assert cell_verdict(tmp_path / "ours-1", "Template:01_01", "Model!B2", "42") == "no-output"


def test_cell_verdict_calls_a_blank_cell_wrong_only_when_the_sheet_has_caches(
    tmp_path: Path,
) -> None:
    _write_run(tmp_path, "ours-1", "Template:01_01", {"A1": 5})
    assert cell_verdict(tmp_path / "ours-1", "Template:01_01", "Model!B2", "42") == "wrong"
    _write_run(tmp_path, "ours-2", "Template:01_01", {})
    assert cell_verdict(tmp_path / "ours-2", "Template:01_01", "Model!B2", "42") == "no-cache"


def test_our_own_repeats_winning_the_cell_makes_it_noise_before_any_arm_delta(
    tmp_path: Path,
) -> None:
    task = "Template:01_01"
    _write_run(tmp_path, "ours-1", task, {"B2": 7})
    _write_run(tmp_path, "ours-2", task, {"B2": 42})
    _write_run(tmp_path, "ours-3", task, {"B2": 7})
    _write_run(tmp_path, "ctrl-1", task, {"B2": 42})
    _write_run(tmp_path, "ctrl-2", task, {"B2": 42})

    row = judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3)

    assert row["verdict"] == NOISE
    assert row["arm_delta"] == "self-unstable"
    assert row["self"]["right"] == 1


def test_a_cell_both_arms_always_miss_is_shared(tmp_path: Path) -> None:
    task = "Template:01_01"
    for name in ("ours-1", "ours-2", "ours-3", "ctrl-1", "ctrl-2"):
        _write_run(tmp_path, name, task, {"B2": 7})

    row = judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3)

    assert row["verdict"] == SHARED
    assert row["arm_delta"] == "shared"


def test_no_control_coverage_is_unjudged_not_a_finding(tmp_path: Path) -> None:
    task = "Template:01_01"
    for name in ("ours-1", "ours-2", "ours-3"):
        _write_run(tmp_path, name, task, {"B2": 7})

    row = judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3)

    assert row["verdict"] == UNJUDGED
    assert row["arm_delta"] == "no-control"


def test_one_deciding_control_run_is_not_enough(tmp_path: Path) -> None:
    task = "Template:01_01"
    for name in ("ours-1", "ours-2", "ours-3"):
        _write_run(tmp_path, name, task, {"B2": 7})
    _write_run(tmp_path, "ctrl-1", task, {"B2": 42})
    _write_run(tmp_path, "ctrl-2", task, None)

    assert judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3)["verdict"] == UNJUDGED
    assert (
        judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3, min_decided=1)["verdict"]
        == SURVIVES
    )


def test_an_induced_cell_on_a_far_task_does_not_survive(tmp_path: Path) -> None:
    task = "Template:01_01"
    for name in ("ours-1", "ours-2", "ours-3"):
        _write_run(tmp_path, name, task, {"B2": 7}, mod=0.4722)
    for name in ("ctrl-1", "ctrl-2"):
        _write_run(tmp_path, name, task, {"B2": 42}, mod=0.4722)

    row = judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3)

    assert row["arm_delta"] == "induced"
    assert row["verdict"] == "far"


def test_a_refuted_lever_blocks_an_otherwise_reachable_case(tmp_path: Path) -> None:
    task = "Template:01_01"
    for name in ("ours-1", "ours-2", "ours-3"):
        _write_run(tmp_path, name, task, {"B2": 7})
    for name in ("ctrl-1", "ctrl-2"):
        _write_run(tmp_path, name, task, {"B2": 42})

    assert judge_case(_case(lever="information"), ARMS, tmp_path, near=3)["verdict"] == (
        REFUTED_LEVER
    )
    assert judge_case(_case(lever="constraint"), ARMS, tmp_path, near=3)["verdict"] == SURVIVES


def test_arms_yaml_names_runs_and_priors_the_gate_understands() -> None:
    arms = load_arms(CATALOG / "arms.yaml")

    assert arms["control"] and arms["ours"]
    assert not set(arms["control"]) & set(arms["ours"])
    assert arms["levers"]["information"] == "refuted"


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_every_case_carries_a_parseable_first_miss(case: dict[str, Any]) -> None:
    """The gate is only as good as the leak it reads. A case it cannot parse is invisible."""

    message = case["first_miss"].get("error_message") or ""
    assert parse_answer(message) is not None, case["id"]
    sheet, cell = split_address(case["first_miss"]["address"])
    assert sheet and cell


def test_briefing_and_method_point_at_the_gate() -> None:
    """A briefing that does not name the gate sends the next agent back to v1."""

    briefing = (CATALOG / "BRIEFING.md").read_text(encoding="utf-8")
    method = (CATALOG / "METHOD.md").read_text(encoding="utf-8")

    assert "catalog_gate.py" in briefing
    assert "catalog_gate.py" in method
    for lever in ("information", "constraint", "substitution", "selection"):
        assert lever in method


def test_every_case_carries_a_lever_the_gate_recognises() -> None:
    """An unset lever is not a neutral default: it silently exempts a case from step 4."""

    levers = set(load_arms(CATALOG / "arms.yaml")["levers"])
    for case in load_cases():
        claims = case["claims"]
        assert claims.get("lever") in levers, case["id"]
        assert claims.get("mechanism"), case["id"]


def test_surface_mechanisms_cover_every_established_pattern() -> None:
    """The collapse has to be total, or a pattern quietly has no mechanism to design against."""

    import yaml

    surface = yaml.safe_load((CATALOG / "surface.yaml").read_text(encoding="utf-8"))
    grouped = {
        pattern_id
        for mechanism in surface["mechanisms"].values()
        for pattern_id in mechanism["patterns"]
    }
    for pattern in surface["patterns"]:
        assert pattern["id"] in grouped, pattern["id"]

    cases = {case["id"] for case in load_cases()}
    for name, mechanism in surface["mechanisms"].items():
        assert set(mechanism["cases"]) <= cases, name
