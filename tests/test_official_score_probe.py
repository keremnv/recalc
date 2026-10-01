import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import matched_compiled_treatment as treatment  # noqa: E402
import official_score_probe as probe  # noqa: E402
from experiment_config import AUTHORITATIVE_EXPERIMENT_CONFIG  # noqa: E402


def test_slice_is_frozen_population_subset_and_avoids_burned_tasks():
    population = {f"{row['category']}:{row['id']}" for row in json.loads((ROOT / "benchmark/slices/control-census-sixty.json").read_text())["tasks"]}
    selected = probe.load_slice_tasks(probe.GLM_SLICE)
    assert selected == list(probe.GLM_TASKS)
    assert set(selected) <= population
    assert not set(selected) & probe.BURNED
    assert probe.load_slice_tasks(probe.SPARK_SLICE) == [probe.SPARK_TASK]
    assert probe.SPARK_TASK in selected


def test_spec_labels_spark_as_extra_and_uses_glm_high_envelope():
    payload = probe.spec()
    assert payload["claim"] == "system_benchmark_vs_published_control"
    assert payload["not_a_causal_scaffold_claim"] is True
    assert payload["glm"]["model"] == AUTHORITATIVE_EXPERIMENT_CONFIG.model
    assert payload["glm"]["reasoning"] == "high"
    assert payload["glm"]["max_model_calls_per_task"] == 40
    assert payload["glm"]["max_cost_usd_per_task"] == 2.5
    assert payload["spark_extra"]["model"] == "meta/muse-spark-1.3-contributor"
    assert payload["spark_extra"]["scaffold"] == "librecalc_sweagent_harness"
    assert payload["spark_extra"]["label"] == "extra_comparison_not_causal"
    assert payload["spark_control_kept"]["label"] == "kept_because_already_ran"
    assert payload["spark_control_kept"]["rerun"] is False
    assert payload["spark_extra"]["task"] == "Financial_Model:02_01"
    assert payload["isolation"]["one_os_process_per_task"] is True
    assert payload["exclusions"]["no_published_control_rerun"] is True
    assert Path(payload["spark_extra"]["output_root"]) != Path(payload["spark_control_kept"]["output_root"])
    assert Path(payload["glm"]["output_root"]) != Path(payload["spark_extra"]["output_root"])
    assert Path(payload["glm"]["output_root"]) != treatment.LIVE


def test_glm_envelope_does_not_go_through_historical_50_dollar4_run_live():
    previous = probe.apply_glm_envelope()
    try:
        assert treatment.ACTIVE_MAX_MODEL_CALLS == 40
        assert treatment.ACTIVE_MAX_COST_USD == pytest.approx(2.5)
        assert treatment.MAX_MODEL_CALLS == 50
        assert treatment.MAX_COST_USD == 4.0
        assert AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning == "high"
        budget = treatment.TaskBudget({"model_call_count": 40, "provider_cost_usd": 0})
        assert budget.failure() == "TASK_MODEL_CALL_LIMIT"
        cheap = treatment.TaskBudget({"model_call_count": 0, "provider_cost_usd": 2.5})
        assert cheap.failure() == "TASK_COST_LIMIT"
    finally:
        treatment.restore_runtime(previous)
    assert treatment.ACTIVE_MAX_MODEL_CALLS == previous["max_model_calls"]


def test_worker_roots_and_locks_do_not_collide():
    roots = {probe.glm_task_dir(key) for key in probe.GLM_TASKS}
    roots.add(probe.spark_task_dir())
    roots.add(probe.spark_harness_task_dir())
    assert len(roots) == 5
    locks = {probe.worker_lock_path(worker_id) for worker_id in probe.WORKER_IDS}
    assert len(locks) == 5
    logs = {probe.log_path(worker_id) for worker_id in probe.WORKER_IDS}
    assert len(logs) == 5
    assert probe.GLM_ROOT != probe.SPARK_ROOT
    assert probe.SPARK_ROOT != probe.SPARK_HARNESS_ROOT
    assert probe.load_slice_tasks(probe.SPARK_HARNESS_SLICE) == [probe.SPARK_TASK]
    assert treatment.LIVE not in roots
    assert "INTERRUPTED" not in probe.TERMINAL_STATUSES
    assert "RUNNING" not in probe.TERMINAL_STATUSES
