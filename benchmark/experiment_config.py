"""Single source of truth for stochastic experiment request identity.

This module is deliberately small.  It owns only the fields that can change
the provider/model identity or generation envelope.  Runtime scheduling
budgets and frontend layout are not request configuration and cannot override
these values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExperimentConfig:
    model: str
    provider: str
    reasoning: str
    temperature: float
    top_p: float
    max_output_tokens: int
    provider_options: dict[str, Any]
    timeouts: dict[str, int]

    def request_fields(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "reasoning": {"effort": self.reasoning},
            "provider": dict(self.provider_options),
            "max_tokens": self.max_output_tokens,
        }

    def metadata(self) -> dict[str, Any]:
        fields = self.request_fields()
        return {
            "declared_model": self.model,
            "declared_reasoning": self.reasoning,
            "declared_provider": self.provider,
            "declared_temperature": self.temperature,
            "declared_top_p": self.top_p,
            "declared_max_output_tokens": self.max_output_tokens,
            "declared_provider_options": dict(self.provider_options),
            "declared_timeouts": dict(self.timeouts),
            "declared_generation_parameters": fields,
        }


# This is the only request configuration for live compiled-architecture
# experiments.  The historical resource-feasibility archive used reasoning=max
# on the wire; the current evidence-delivery experiment freezes reasoning=high.
# Future paid work must not select a different value by monkeypatching a
# stage-specific body.
AUTHORITATIVE_EXPERIMENT_CONFIG = ExperimentConfig(
    model="z-ai/glm-5.3-flash",
    provider="openrouter",
    reasoning="high",
    temperature=0.0,
    top_p=1.0,
    max_output_tokens=65536,
    provider_options={"allow_fallbacks": True, "require_parameters": True},
    timeouts={"task_ir": 600, "edit_plan": 600, "retrieval": 180, "synthesis": 300},
)

# Same compiled request envelope as AUTHORITATIVE_EXPERIMENT_CONFIG except the
# model.  Used only by the frozen three-task compiled model discriminator.
# Architecture, schemas, evidence, and budgets stay GLM's; Spark's API accepts
# reasoning=high, temperature, top_p, and max_tokens.
SPARK_COMPILED_EXPERIMENT_CONFIG = ExperimentConfig(
    model="meta/muse-spark-1.3-contributor",
    provider=AUTHORITATIVE_EXPERIMENT_CONFIG.provider,
    reasoning=AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning,
    temperature=AUTHORITATIVE_EXPERIMENT_CONFIG.temperature,
    top_p=AUTHORITATIVE_EXPERIMENT_CONFIG.top_p,
    max_output_tokens=AUTHORITATIVE_EXPERIMENT_CONFIG.max_output_tokens,
    provider_options=dict(AUTHORITATIVE_EXPERIMENT_CONFIG.provider_options),
    timeouts=dict(AUTHORITATIVE_EXPERIMENT_CONFIG.timeouts),
)

_ACTIVE_EXPERIMENT_CONFIG = AUTHORITATIVE_EXPERIMENT_CONFIG


def active_experiment_config() -> ExperimentConfig:
    return _ACTIVE_EXPERIMENT_CONFIG


def activate_experiment_config(config: ExperimentConfig) -> ExperimentConfig:
    global _ACTIVE_EXPERIMENT_CONFIG
    previous = _ACTIVE_EXPERIMENT_CONFIG
    _ACTIVE_EXPERIMENT_CONFIG = config
    return previous


def restore_experiment_config(previous: ExperimentConfig) -> None:
    global _ACTIVE_EXPERIMENT_CONFIG
    _ACTIVE_EXPERIMENT_CONFIG = previous


def timeout_for_stage(stage: str) -> int:
    try:
        return active_experiment_config().timeouts[stage]
    except KeyError as exc:
        raise RuntimeError(f"REQUEST_TIMEOUT_NOT_CONFIGURED: {stage}") from exc


def _request_identity(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_model": body.get("model"),
        "request_reasoning": ((body.get("reasoning") or {}).get("effort") if isinstance(body.get("reasoning"), dict) else body.get("reasoning")),
        "effective_generation_parameters": {
            key: body.get(key)
            for key in ("temperature", "top_p", "max_tokens", "provider", "reasoning")
        },
    }


def request_identity(body: dict[str, Any], *, stage: str) -> dict[str, Any]:
    """Assert exact wire identity before a provider request is sent."""
    active = active_experiment_config()
    expected = active.request_fields()
    mismatches = {}
    for key, value in expected.items():
        if body.get(key) != value:
            mismatches[key] = {"expected": value, "actual": body.get(key)}
    if "stream" in body and body.get("stream"):
        mismatches["stream"] = {"expected": False, "actual": body.get("stream")}
    if mismatches:
        raise RuntimeError(f"REQUEST_CONFIGURATION_MISMATCH[{stage}]: {mismatches}")
    return {**active.metadata(), **_request_identity(body)}


def assert_declared_matches_wire(declared_model: str, declared_reasoning: str, body: dict[str, Any], *, stage: str) -> None:
    """Reject runtime labels that disagree with the serialized request."""
    request_identity(body, stage=stage)
    wire_reasoning = (body.get("reasoning") or {}).get("effort") if isinstance(body.get("reasoning"), dict) else body.get("reasoning")
    if declared_model != body.get("model"):
        raise RuntimeError(f"DECLARED_WIRE_MODEL_MISMATCH[{stage}]: declared={declared_model!r} wire={body.get('model')!r}")
    if declared_reasoning != wire_reasoning:
        raise RuntimeError(f"DECLARED_WIRE_REASONING_MISMATCH[{stage}]: declared={declared_reasoning!r} wire={wire_reasoning!r}")


def response_identity(payload: dict[str, Any] | None, *, stage: str) -> dict[str, Any]:
    """Retain provider identity and reject a reported model mismatch."""
    reported = payload.get("model") if isinstance(payload, dict) else None
    expected = active_experiment_config().model
    if reported is not None and reported != expected:
        raise RuntimeError(
            f"RESPONSE_MODEL_MISMATCH[{stage}]: expected {expected}, got {reported}"
        )
    return {"response_model": reported}


def identity_record(body: dict[str, Any], payload: dict[str, Any] | None, *, stage: str) -> dict[str, Any]:
    """Return the persisted identity fields after validating both sides."""
    return {**request_identity(body, stage=stage), **response_identity(payload, stage=stage)}


def archived_mismatch_probe() -> dict[str, Any]:
    """Reproduce the archived label/wire defect without making a request."""
    bad = AUTHORITATIVE_EXPERIMENT_CONFIG.request_fields()
    bad["model"] = "z-ai/glm-5.3-flash"
    declared = "openai/gpt-5.6-sol"
    try:
        # The exact archived failure: the runtime label said GPT while the
        # serialized request body carried GLM.
        if declared == bad["model"]:
            raise AssertionError("probe setup failed")
        assert_declared_matches_wire(declared, AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning, bad, stage="archived_mismatch_regression")
    except RuntimeError:
        return {
            "declared_model": declared,
            "request_model": bad["model"],
            "rejected": True,
            "provider_attempt": False,
        }
    raise AssertionError("archived GPT-label/GLM-wire mismatch was not rejected")
