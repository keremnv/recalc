import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import frontend_projection as projection  # noqa: E402
import matched_compiled_treatment as treatment  # noqa: E402


def test_projection_keeps_remainder_handle_and_does_not_delete_world_candidates():
    obligation = {"id": "O1", "locus": "Revenue", "required_change": "formula"}
    packet = {
        "locus": [{"id": f"l{i}", "text": "Revenue", "rules": [rule]} for i, rule in enumerate(("exact_norm", "compact", "substring", "jaccard", "token_prefix"))],
        "subject": [], "scope": [], "source": [], "target_cell_ids": [f"cell:s00:r{i}:c1" for i in range(30)],
        "formula_class_facts": [], "dependency_facts": [], "counts": {"locus": 5, "targets": 30},
        "fields": {"locus": "Revenue"},
    }
    projected = projection.project_packet(obligation, packet, foreground_limit=2, target_foreground_limit=3, region_limit=2)
    assert projected["locus"]["candidate_count"] == 5
    assert projected["locus"]["omitted_count"] == 3
    assert projected["locus"]["remainder_handle"] == "grounding:O1:locus:tail"
    assert projected["targets"]["candidate_count"] == 30
    assert projected["targets"]["remainder_handle"] == "grounding:O1:targets:tail"
    assert len(projected["targets"]["region_summaries"]) <= 2


def test_runtime_profile_is_explicit_and_restorable():
    old = treatment.configure_runtime(reasoning="high", top_p=1, max_model_calls=150, max_cost_usd=6, frontend_mode="sharded_projected")
    try:
        assert treatment.ACTIVE_REASONING == "high"
        assert treatment.ACTIVE_TOP_P == 1.0
        assert treatment.ACTIVE_MAX_MODEL_CALLS == 150
        assert treatment.ACTIVE_MAX_COST_USD == 6.0
        assert treatment.ACTIVE_FRONTEND_MODE == "sharded_projected"
        body = treatment.request_body("system", "user")
        assert body["reasoning"] == {"effort": "high"}
        assert body["top_p"] == 1.0
    finally:
        treatment.restore_runtime(old)
    assert treatment.ACTIVE_REASONING == treatment.REASONING
    assert treatment.ACTIVE_MAX_MODEL_CALLS == treatment.MAX_MODEL_CALLS


def test_retrieval_guard_uses_active_call_ceiling(monkeypatch, tmp_path):
    """The 150-call feasibility profile must not inherit the old 50-call guard."""
    old = treatment.configure_runtime(max_model_calls=150, max_cost_usd=6)
    calls = []

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

    def fake_call(task_dir, task_key, stage, system, user, state, **kwargs):
        calls.append(stage)
        state["model_call_count"] = int(state.get("model_call_count", 0)) + 1
        if stage == "retrieval":
            return {"stage": stage, "parsed_response": {"action": "final"}, "failure_class": None}
        return {"stage": stage, "parsed_response": {"status": "ABSTAIN"}, "failure_class": None}

    monkeypatch.setattr(treatment.relational, "ReadOnlySqlite", FakeExecutor)
    monkeypatch.setattr(treatment, "call_or_stub", fake_call)
    monkeypatch.setattr(treatment, "materialize", lambda *args, **kwargs: {})
    monkeypatch.setattr(treatment.prior, "compile_bootstrap", lambda *args, **kwargs: {"bootstrap_entity_ids": []})
    monkeypatch.setattr(treatment, "spine_for", lambda task_key: {})
    monkeypatch.setattr(treatment, "db_for", lambda task_key: tmp_path / "empty.sqlite")

    state = {"model_call_count": 49, "provider_cost_usd": 0.0}
    result = treatment.retrieval_synthesis(
        "Financial_Model:01_01",
        {"instruction": "x"},
        {"id": "O1"},
        {"cell_id": "cell:s00:r1:c1", "sheet": "Sheet1", "address": "A1"},
        {}, state, tmp_path, stub=False,
    )
    treatment.restore_runtime(old)
    assert calls == ["retrieval", "synthesis"]
    assert result["status"] == "ABSTAIN"  # an explicit model abstention, not provider failure
    assert state["model_call_count"] == 51
