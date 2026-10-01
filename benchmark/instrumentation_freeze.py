#!/usr/bin/env python3
"""Freeze the earned harness repairs before the composition-closure probe.

This is a precondition, not an experiment. It pins the instrument so that any
later divergence is attributable to the experiment rather than to a quiet change
in how responses are read, budgeted or written.

It also states which outcomes are NOT model-quality failures. Conflating a
truncated response, an access failure or a resource bound with a wrong answer is
exactly the class of defect this project has now hit five times.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
import task_obligation_compile as toc
import edit_plan

OUT = old.MECHANICAL / "instrumentation-freeze"

# The freeze is generational. A repair earned by an experiment is frozen as a new
# generation rather than written over the old one, so a completed run's
# provenance stays verifiable against the instrument it actually ran on.
GENERATION = 2
GENERATIONS = {1: "freeze.json", 2: "freeze.v2.json"}

# Outcomes that describe the harness or the provider, never the model's answer.
NON_MODEL_FAILURE_CLASSES = ["TRUNCATED_NO_CONTENT", "TRUNCATED_AT_BUDGET", "MODEL_ACCESS_FAILURE", "SESSION_RESOURCE_LIMIT"]

# Every model call in a frozen run must persist all of these.
REQUIRED_RESPONSE_FIELDS = ["request_body", "text", "usage", "parsed", "duplicate_object_status", "truncation_status"]

COMPONENTS = [
    "benchmark/end_to_end_composition_probe.py",
    "benchmark/task_obligation_compile.py",
    "benchmark/edit_plan.py",
    "benchmark/xlsx_cell_writer.py",
    "benchmark/report_edit_plan_replay.py",
]


def build():
    repairs = {
        "duplicate_emission_parser": {
            "where": "task_obligation_compile.extract_json_object",
            "rule": "repeated top-level objects accepted only when semantically identical; disagreeing objects stay unparseable",
            "verified": toc.extract_json_object('{"a":1}\n\n\n{"a":1}') == {"a": 1}
                        and toc.extract_json_object('{"a":1}\n{"a":2}') is None,
        },
        "output_budgets": {
            "retrieval_max_tokens": old.RETRIEVAL_MAX_TOKENS,
            "synthesis_max_tokens": old.SYNTHESIS_MAX_TOKENS,
            "verified_separate": old.SYNTHESIS_MAX_TOKENS > old.RETRIEVAL_MAX_TOKENS,
        },
        "explicit_truncation": {
            "fields": ["synthesis_truncated", "truncation_class"],
            "classes": ["TRUNCATED_NO_CONTENT", "TRUNCATED_AT_BUDGET"],
            "rule": "a response at the output budget with no parseable object is truncated, "
                    "whether the body is empty or full of deliberation",
            "verified": "truncation_class" in old.run_target.__code__.co_consts
                        or "TRUNCATED_AT_BUDGET" in (old.run_target.__code__.co_consts or ()),
        },
        "phase_specific_synthesis_prompt": {"sha256": hashlib.sha256(old.SYNTHESIS_SYSTEM.encode()).hexdigest()},
        "delta_working_set_serialization": {"sha256": hashlib.sha256(old.DELTA_RETRIEVAL_SYSTEM.encode()).hexdigest()},
        "closed_world_validator": {"contract": "V2", "namespaces": ["cell", "sheet", "row", "col", "text", "period", "tcoord", "formula_class", "wb"]},
        "writer": {"module": "xlsx_cell_writer", "gate": "zero-write round trip scores regression 1.0", "gate_pass": None},
        "per_session_resource_bound": {"declared_in": "each run's freeze.json", "explicit_record": "SESSION_RESOURCE_LIMIT"},
    }
    gate = old.MECHANICAL / "writer-neutrality-gate/gate.json"
    if gate.exists():
        g = old.load(gate)
        repairs["writer"]["gate_pass"] = bool(g.get("pass"))
        repairs["writer"]["tasks_passing"] = f"{g.get('passing')}/{g.get('tasks')}"

    frozen = {
        "purpose": "instrumentation freeze preceding the composition-closure probe",
        "model_guard": {"slug": "z-ai/glm-5.3-flash", "temperature": 0, "reasoning": "medium",
                        "no_fallback": True, "no_gpt": True},
        "repairs": repairs,
        "non_model_failure_classes": NON_MODEL_FAILURE_CLASSES,
        "required_response_fields": REQUIRED_RESPONSE_FIELDS,
        "sha256": {c: hashlib.sha256((old.ROOT / c).read_bytes()).hexdigest() for c in COMPONENTS},
    }
    unverified = [k for k, v in repairs.items() if isinstance(v, dict) and v.get("verified") is False]
    if unverified or not repairs["output_budgets"]["verified_separate"]:
        raise RuntimeError(f"instrumentation not in the declared state: {unverified}")
    frozen["generation"] = GENERATION
    old.write(OUT / GENERATIONS[GENERATION], frozen)
    return frozen


def check():
    """Fail loudly if the instrument moved after the freeze."""
    f = old.load(OUT / GENERATIONS[GENERATION])
    drift = [c for c, d in f["sha256"].items()
             if hashlib.sha256((old.ROOT / c).read_bytes()).hexdigest() != d]
    if drift:
        raise RuntimeError(f"instrumentation drifted after freeze: {drift}")
    old.guard(f["model_guard"]["slug"])
    return f


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
