import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
import matched_fm_max as b


def frozen():
    return {"model_config": {"model": "z-ai/glm-5.3-flash", "temperature": 0.0, "top_p": 1.0, "reasoning": {"effort": "max"}, "provider": {"allow_fallbacks": True, "require_parameters": True}}, "maximum_stochastic_calls_per_task": 2, "per_task_monetary_cap_usd": 4, "max_tokens_per_call": 1000, "provider_prices_per_token": {"prompt": .000001, "completion": .000002}}


def test_phase_b_refuses_to_start_without_phase_a_gates(tmp_path, monkeypatch):
    monkeypatch.setattr(b.a, "OUT", tmp_path)
    with pytest.raises(RuntimeError, match="PHASE_A_GATES_NOT_COMPLETE"):
        b.require_gates()


def test_phase_b_refuses_unresolved_resource_envelope(tmp_path, monkeypatch):
    monkeypatch.setattr(b.a, "OUT", tmp_path)
    b.m.write_json(tmp_path / "repair_gates.json", {"status": "PASS", "repaired_source_sha256": {}})
    b.m.write_json(tmp_path / "resource_envelope_audit.json", {"status": "UNRESOLVED_RESOURCE_ENVELOPE"})
    with pytest.raises(RuntimeError, match="RESOURCE_ENVELOPE_NOT_FROZEN"):
        b.require_gates()


def test_gateway_rejects_reasoning_mismatch_before_network(tmp_path, monkeypatch):
    gateway = b.Gateway(tmp_path, frozen(), "not-a-real-key")
    monkeypatch.setattr(b.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network call"))
    body = copy.deepcopy(frozen()["model_config"])
    body["reasoning"] = {"effort": "high"}
    with pytest.raises(RuntimeError, match="MODEL_CONFIGURATION_MISMATCH: reasoning"):
        gateway.forward(body)
    assert list(tmp_path.glob("*.json")) == []


def test_gateway_applies_identical_config_retains_raw_and_enforces_calls(tmp_path, monkeypatch):
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return b'{"choices":[{"message":{"content":"answer","reasoning":"raw reasoning"}}],"usage":{"cost":0.01}}'
    def open_request(request, **kwargs):
        requests.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr(b.urllib.request, "urlopen", open_request)
    gateway = b.Gateway(tmp_path, frozen(), "not-a-real-key")
    for tool_mode in (False, True):
        body = copy.deepcopy(frozen()["model_config"])
        body["messages"] = [{"role": "user", "content": "infrastructure test"}]
        if tool_mode: body["tools"] = []
        gateway.forward(body)
    fields = frozen()["model_config"]
    assert {k: requests[0][k] for k in fields} == {k: requests[1][k] for k in fields}
    assert all(r["max_tokens"] == 1000 for r in requests)
    assert "raw reasoning" in json.loads((tmp_path / "001.json").read_text())["raw_response_text"]
    with pytest.raises(RuntimeError, match="TASK_MODEL_CALL_LIMIT"):
        gateway.forward(copy.deepcopy(frozen()["model_config"]))
    assert len(requests) == 2
