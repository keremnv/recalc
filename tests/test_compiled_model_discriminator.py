import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import matched_compiled_treatment as treatment  # noqa: E402
import official_score_probe as probe  # noqa: E402
from experiment_config import (  # noqa: E402
    AUTHORITATIVE_EXPERIMENT_CONFIG,
    SPARK_COMPILED_EXPERIMENT_CONFIG,
    activate_experiment_config,
    active_experiment_config,
    restore_experiment_config,
)


def test_spark_compiled_config_matches_glm_except_model():
    glm = AUTHORITATIVE_EXPERIMENT_CONFIG
    spark = SPARK_COMPILED_EXPERIMENT_CONFIG
    assert spark.model == "meta/muse-spark-1.3-contributor"
    assert spark.model != glm.model
    assert spark.reasoning == glm.reasoning == "high"
    assert spark.temperature == glm.temperature
    assert spark.top_p == glm.top_p
    assert spark.max_output_tokens == glm.max_output_tokens
    assert spark.provider_options == glm.provider_options
    assert spark.timeouts == glm.timeouts


def test_bind_compiled_identity_changes_wire_then_restores():
    glm_body = treatment.request_body("s", "u")
    assert glm_body["model"] == "z-ai/glm-5.3-flash"
    previous = treatment.bind_compiled_identity(SPARK_COMPILED_EXPERIMENT_CONFIG)
    try:
        assert active_experiment_config().model == "meta/muse-spark-1.3-contributor"
        spark_body = treatment.request_body("s", "u")
        assert spark_body["model"] == "meta/muse-spark-1.3-contributor"
        assert spark_body["reasoning"] == {"effort": "high"}
        assert spark_body["temperature"] == glm_body["temperature"]
        assert spark_body["top_p"] == glm_body["top_p"]
        assert spark_body["max_tokens"] == glm_body["max_tokens"]
        assert spark_body["provider"] == glm_body["provider"]
        treatment.check_model(treatment.MODEL, treatment.REASONING, treatment.TEMPERATURE)
    finally:
        treatment.restore_compiled_identity(previous)
    restored = treatment.request_body("s", "u")
    assert restored["model"] == "z-ai/glm-5.3-flash"
    assert active_experiment_config() is AUTHORITATIVE_EXPERIMENT_CONFIG or active_experiment_config().model == AUTHORITATIVE_EXPERIMENT_CONFIG.model


def test_spark_compiled_root_does_not_collide_with_glm_or_harness():
    assert probe.SPARK_COMPILED_ROOT != probe.GLM_ROOT
    assert probe.SPARK_COMPILED_ROOT != probe.SPARK_ROOT
    assert probe.SPARK_COMPILED_ROOT != probe.SPARK_HARNESS_ROOT
    assert probe.SPARK_COMPILED_ROOT != treatment.LIVE


def test_discriminator_verdict_edit_plan_clearance_is_model_sensitivity():
    rows = [
        {
            "task": "Template:01_02",
            "glm": {"earliest": "TASK_MODEL_CALL_LIMIT", "unresolved_authorised_targets": 181},
            "spark": {"earliest": "TASK_MODEL_CALL_LIMIT", "unresolved_authorised_targets": 181, "identity_ok": True, "terminal_stage": "resource", "edit_plan_status": "VALID_PLAN"},
            "spark_official": {"accuracy": 0.0},
        },
        {
            "task": "Financial_Model:02_01",
            "glm": {"earliest": "edit_plan"},
            "spark": {"earliest": None, "identity_ok": True, "terminal_stage": "completed", "edit_plan_status": "VALID_PLAN"},
        },
        {
            "task": "Debugging:01_01",
            "glm": {"earliest": "UNSUPPORTED_EDIT_KIND"},
            "spark": {"earliest": "UNSUPPORTED_EDIT_KIND", "identity_ok": True, "terminal_stage": "actuation"},
        },
    ]
    assert probe.discriminator_verdict(rows) == "MIXED_MODEL_ARCHITECTURE_LIMITS"


def test_discriminator_verdict_shared_failures():
    rows = [
        {
            "task": "Template:01_02",
            "glm": {"earliest": "TASK_MODEL_CALL_LIMIT", "unresolved_authorised_targets": 181},
            "spark": {"earliest": "TASK_MODEL_CALL_LIMIT", "unresolved_authorised_targets": 181, "identity_ok": True, "terminal_stage": "resource"},
            "spark_official": {"accuracy": 0.0},
        },
        {
            "task": "Financial_Model:02_01",
            "glm": {"earliest": "edit_plan"},
            "spark": {"earliest": "edit_plan", "identity_ok": True, "terminal_stage": "edit_plan", "edit_plan_status": "PARSE_FAILURE"},
        },
        {
            "task": "Debugging:01_01",
            "glm": {"earliest": "UNSUPPORTED_EDIT_KIND"},
            "spark": {"earliest": "UNSUPPORTED_EDIT_KIND", "identity_ok": True, "terminal_stage": "actuation"},
        },
    ]
    assert probe.discriminator_verdict(rows) == "ARCHITECTURE_LIMIT_SHARED_ACROSS_MODELS"


def test_glm_loss_boundary_snapshot_from_completed_probe():
    template = probe.compiled_task_snapshot(probe.GLM_ROOT, "Template:01_02")
    fm = probe.compiled_task_snapshot(probe.GLM_ROOT, "Financial_Model:02_01")
    debugging = probe.compiled_task_snapshot(probe.GLM_ROOT, "Debugging:01_01")
    assert template["earliest"] == "TASK_MODEL_CALL_LIMIT"
    assert template["unresolved_authorised_targets"] == 181
    assert fm["edit_plan_status"] == "PARSE_FAILURE"
    assert fm["earliest"] == "edit_plan"
    assert debugging["earliest"] == "UNSUPPORTED_EDIT_KIND"
    assert template["identity_ok"] is True
    assert fm["model"] == "z-ai/glm-5.3-flash"
