import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import matched_compiled_treatment as runner  # noqa: E402


def test_frozen_population_and_model_guard():
    rows = runner.task_rows()
    assert len(rows) == 60
    assert {category: sum(row["category"] == category for row in rows) for category in ("Template", "Financial_Model", "Debugging")} == {
        "Template": 20,
        "Financial_Model": 20,
        "Debugging": 20,
    }
    assert "Financial_Model:06_01" in {row["task_key"] for row in rows}
    runner.check_model(runner.MODEL, runner.REASONING, runner.TEMPERATURE)
    with pytest.raises(RuntimeError, match="MODEL_GUARD"):
        runner.check_model("other-model", runner.REASONING, runner.TEMPERATURE)
    with pytest.raises(RuntimeError, match="REASONING_GUARD"):
        runner.check_model(runner.MODEL, "medium", runner.TEMPERATURE)


def test_central_budget_and_request_fidelity_contract():
    state = {"model_call_count": 49, "provider_cost_usd": 3.99}
    assert runner.TaskBudget(state).failure() is None
    assert runner.TaskBudget({"model_call_count": 50, "provider_cost_usd": 0}).failure() == "TASK_MODEL_CALL_LIMIT"
    assert runner.TaskBudget({"model_call_count": 0, "provider_cost_usd": 4}).failure() == "TASK_COST_LIMIT"
    body = runner.request_body("system", "user")
    assert body["model"] == runner.MODEL
    assert body["temperature"] == 0.0
    assert body["reasoning"] == {"effort": "high"}
    assert body["top_p"] == 1.0
    assert body["max_tokens"] == 65536
    assert body["provider"] == {"allow_fallbacks": True, "require_parameters": True}
    assert body["messages"][-1] == {"role": "user", "content": "user"}


def test_resume_reuses_persisted_call_without_new_model_call(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    body = runner.request_body("s", "u")
    identity = runner.identity_record(body, {"choices": []}, stage="task_ir")
    persisted = {
        "task_id": "Template:01_02",
        "stage": "task_ir",
        "call_index_within_task": 1,
        "failure_class": None,
        "raw_response_body": {"choices": []},
        "request_body": body,
        "request_sha256": runner.digest(body),
        **identity,
    }
    (task_dir / "calls").mkdir()
    (task_dir / "calls" / "001_task_ir.json").write_text(json.dumps(persisted), encoding="utf-8")
    state = {"model_call_count": 0, "provider_cost_usd": 0.0, "_resume_mode": True}
    call = runner.call_or_stub(task_dir, "Template:01_02", "task_ir", "s", "u", state, stub=False)
    assert call == persisted
    # Reusing a response makes zero *new* calls, but the persisted provider
    # attempt must still be included in the task's cumulative budget.
    assert state["model_call_count"] == 1
    assert not (task_dir / "calls" / "002_task_ir.json").exists()


def test_production_runner_has_no_rejected_stochastic_interfaces():
    source = (ROOT / "benchmark/matched_compiled_treatment.py").read_text(encoding="utf-8")
    assert "from program_candidate" not in source
    assert "def select_program_candidate" not in source
    assert "def sketch_stage" not in source
    assert "def operand_binding_stage" not in source


def test_repaired_fm_task_is_runnable_and_census_unclassifiable_when_environment_exists():
    environment = runner.PREP / "environment.json"
    if not environment.exists():
        pytest.skip("offline freeze has not been generated")
    records = {row["task_key"]: row for row in json.loads(environment.read_text(encoding="utf-8"))["records"]}
    row = records["Financial_Model:06_01"]
    assert row["status"] == "TREATMENT_RUNNABLE_CENSUS_UNCLASSIFIABLE"
    assert row["metadata_only_repair"] is True
    assert Path(row["effective_path"]).exists()
    assert row["spine"]["readable"] is True


def test_freeze_profile_matches_expected_structural_slice():
    profile = runner.structural_profile()
    assert profile["formula_cells"] == 5818
    assert profile["independent_programs"] == 1387
    assert profile["exact_recoverable_cells"] == 1416
    assert profile["programgroup_uniform_cells"] == 3549
    assert profile["programgroup_after_decisions"] == 2452
