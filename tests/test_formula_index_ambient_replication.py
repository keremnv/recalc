from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))


def test_replication_slice_is_the_two_diagnostic_cases() -> None:
    payload = json.loads(
        (ROOT / "benchmark/slices/fm-ambient-replication-two.json").read_text()
    )
    assert [task["id"] for task in payload["tasks"]] == ["20_05", "11_02"]
    assert payload["repeats"] == 5
    assert payload["model"] == "z-ai/glm-5.3-flash"
    assert payload["max_tool_calls_per_task"] == 50
    assert payload["cost_limit_usd"] == 2.0


def test_frozen_exposed_subsets_match_the_diagnostic() -> None:
    manifest = json.loads(
        (ROOT / "benchmark/slices/fm-ambient-replication-targets.json").read_text()
    )
    twenty = manifest["tasks"]["20_05"]
    eleven = manifest["tasks"]["11_02"]
    assert twenty["counts"]["fixed_exposed"] == 42
    assert twenty["fixed_exposed_strata"] == {"same_column_nonadjacent": 42}
    assert eleven["counts"]["fixed_exposed"] == 5
    assert eleven["fixed_exposed_strata"] == {"adjacent": 5}
    assert eleven["fixed_exposed_addresses"] == [
        "BS!I7",
        "BS!J7",
        "BS!K7",
        "BS!L7",
        "BS!M7",
    ]
    assert twenty["diagnostic_first_content"]["sheet"] == "Cost Drivers"
    assert eleven["diagnostic_first_content"]["sheet"] == "CF"
    assert twenty["counts"]["recoverable_unexposed"] == 42
    assert twenty["counts"]["unrecoverable"] == 88
    assert eleven["counts"]["unrecoverable"] == 30


def test_replication_intervention_is_the_forced_exposure_arm() -> None:
    import yaml

    control = yaml.safe_load(
        (ROOT / "benchmark/sweagent/spreadsheet-control.yaml").read_text()
    )
    treatment = yaml.safe_load(
        (ROOT / "benchmark/sweagent/spreadsheet-control-ambient.yaml").read_text()
    )
    integrity = json.loads(
        (ROOT / "benchmark/slices/fm-ambient-replication-targets.json").read_text()
    )["intervention"]
    assert integrity["control"]["treatment_prompt_matches_control"] is True
    assert integrity["no_formula_index_in_treatment"] is True
    assert integrity["wrapper_appends_first_content_only"] is True
    assert integrity["treatment_prompt_has_no_structural_index"] is True
    assert (
        control["agent"]["templates"]["instance_template"]
        == treatment["agent"]["templates"]["instance_template"]
    )


def test_replication_jobs_are_twenty_interleaved_and_deterministic() -> None:
    from formula_index_ambient_replication_launch import (
        SEED,
        build_jobs,
        runner_command,
    )

    payload = json.loads(
        (ROOT / "benchmark/slices/fm-ambient-replication-two.json").read_text()
    )
    jobs = build_jobs(payload)
    assert jobs == build_jobs(payload, seed=SEED)
    assert len(jobs) == 20
    keys = [(job["task"], job["arm"], job["repeat"]) for job in jobs]
    assert len(set(keys)) == 20
    assert {job["arm"] for job in jobs} == {"control", "control-ambient"}
    assert {job["repeat"] for job in jobs} == {1, 2, 3, 4, 5}
    assert {job["arm"] for job in jobs[:6]} == {"control", "control-ambient"}
    assert {job["task"] for job in jobs[:6]} == {
        "Financial_Model:20_05",
        "Financial_Model:11_02",
    }
    control = next(job for job in jobs if job["arm"] == "control")
    treatment = next(job for job in jobs if job["arm"] == "control-ambient")
    assert "--control" in runner_command(control)
    assert "--control-ambient" in runner_command(treatment)
    assert "--max-tokens" not in runner_command(control)
    assert "fm-ambient-replication-two.json" in " ".join(runner_command(control))


def test_quarantine_missing_directory_does_not_raise(tmp_path) -> None:
    from formula_index_ambient_replication_launch import _quarantine

    missing = tmp_path / "Financial_Model-20_05"
    dest = _quarantine(missing)
    assert dest.name == "Financial_Model-20_05.infra-fail-1"
    assert not missing.exists()
    assert not dest.exists()


def test_finished_orders_skip_done_and_fail_but_not_started(tmp_path) -> None:
    from formula_index_ambient_replication_launch import _finished_orders

    log = tmp_path / "launch.log"
    log.write_text(
        "JOB-DONE 15 Financial_Model:11_02 control-ambient\n"
        "JOB-FAIL 16 rc=1 Financial_Model:20_05 control\n"
        "JOB 17/20 control r5 Financial_Model:20_05 "
        "run=glm-5.3-flash-fm-ambient-repl-control-5 started=2026-09-05T11:31:01Z\n"
    )
    assert _finished_orders(log) == {15, 16}
