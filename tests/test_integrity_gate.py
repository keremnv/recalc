import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

from experiment_config import (  # noqa: E402
    AUTHORITATIVE_EXPERIMENT_CONFIG,
    archived_mismatch_probe,
    request_identity,
    response_identity,
)
import matched_compiled_treatment as treatment  # noqa: E402


def test_archived_gpt_label_glm_wire_mismatch_is_rejected_without_provider_attempt():
    result = archived_mismatch_probe()
    assert result == {
        "declared_model": "openai/gpt-5.6-sol",
        "request_model": "z-ai/glm-5.3-flash",
        "rejected": True,
        "provider_attempt": False,
    }


def test_request_identity_contains_all_fail_closed_fields():
    body = {**AUTHORITATIVE_EXPERIMENT_CONFIG.request_fields(), "messages": []}
    identity = request_identity(body, stage="regression")
    assert identity["declared_model"] == identity["request_model"] == AUTHORITATIVE_EXPERIMENT_CONFIG.model
    assert identity["declared_reasoning"] == identity["request_reasoning"] == AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning
    assert identity["effective_generation_parameters"]["max_tokens"] == 65536
    assert identity["declared_provider"] == "openrouter"


def test_wire_model_mismatch_fails_before_network():
    body = {**AUTHORITATIVE_EXPERIMENT_CONFIG.request_fields(), "model": "openai/gpt-5.6-sol", "messages": []}
    with pytest.raises(RuntimeError, match="REQUEST_CONFIGURATION_MISMATCH"):
        request_identity(body, stage="regression")


def test_provider_reported_model_mismatch_fails_loudly():
    with pytest.raises(RuntimeError, match="RESPONSE_MODEL_MISMATCH"):
        response_identity({"model": "z-ai/glm-5.3-flash-wrong"}, stage="regression")


def test_stub_call_persists_declared_request_and_response_identity(tmp_path):
    state = {"model_call_count": 0, "provider_cost_usd": 0.0}
    call = treatment.model_call("Template:01_01", "task_ir", "s", "u", state, stub=True)
    assert call["declared_model"] == call["request_model"] == call["response_model"] == treatment.MODEL
    assert call["declared_reasoning"] == call["request_reasoning"] == treatment.REASONING
    assert call["effective_generation_parameters"]["top_p"] == 1.0
