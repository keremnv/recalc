# Request-Configuration Audit

This audit covers the request paths relevant to the current compiled
architecture. The only valid current experiment entry point is the integrated
`matched_compiled_treatment` path. No provider request was made by the gate.

## Authoritative path

`benchmark/experiment_config.py` is the sole authoritative source for:

- model: `z-ai/glm-5.3-flash`;
- provider: OpenRouter, with `allow_fallbacks=true` and
  `require_parameters=true`;
- reasoning effort: `high` (current evidence-delivery experiment; the
  historical resource-feasibility archive used `max`);
- temperature: `0`;
- top-p: `1`;
- max output tokens: `65536`;
- timeout: 600 seconds for Task IR/Edit Plan, 180 seconds for retrieval,
  300 seconds for synthesis (five minutes; this evidence-delivery experiment).

`benchmark/matched_compiled_treatment.py` uses this path for all four stages:

```text
Task IR       -> model_call -> request_body -> request_identity -> wire
Edit Plan     -> model_call -> request_body -> request_identity -> wire
retrieval     -> model_call -> request_body -> request_identity -> wire
synthesis     -> model_call -> request_body -> request_identity -> wire
```

The post-response path invokes `response_identity`. Every new call record
contains the declared model, wire/request model, response model, declared and
wire reasoning, and effective generation parameters. Runtime configuration may
change only observation budgets and frontend mode; attempts to override request
identity or request timeout fail.

`benchmark/fm_resource_feasibility.py` has two named helpers because it runs
the static/front-end feasibility machinery, but both
`frontend_body` and `treatment_request_body` delegate to the authoritative
constructor. Its direct `call_provider` path asserts the same wire identity and
response identity. The former treatment-body monkeypatch was removed.

## Other locations audited

| Location | Fields it can mention | Status for current experiment |
|---|---|---|
| `matched_compiled_treatment.configure_runtime` | old reasoning/top-p/timeout arguments | identity overrides rejected; budget/mode only |
| `clean_integrated_feasibility.py` | runtime profile and database path | request-body override removed; not run |
| `authority_frontier_live_probe.py` | runtime profile and request-body override | request-body override removed; not run |
| `output_role_planner_live_probe.py` | runtime profile and request-body override | request-body override removed; not run |
| `scheduler_live_validation.py` | archived runtime profile and request-body override | request-body override removed; not run |
| `matched_fm_max.py` | separate frozen gateway model/temperature/reasoning/top-p/max-output/timeout | separate historical A/B entry point; explicitly prohibited by this gate |
| `end_to_end_composition_probe.py` | direct GLM body, medium reasoning, stage-specific output caps, 300-second timeout | old 18-task probe; not current architecture/control |
| `integrated_hybrid_synthesis_probe.py` | direct retrieval/synthesis bodies and 300-second timeout | old probe; not current architecture/control |
| `relational_retrieval_probe.py` | direct retrieval body and 300-second timeout | old probe; not current architecture/control |
| `task_obligation_compile_probe.py` | offline model profiles for compiler experiments | not an integrated experiment request path |
| `run_openrouter_slice.py` and SWE-agent configs | published control model/effort/cap fields | external benchmark scaffold/control reference only; not rerun |

The last group is retained as historical or external-reference code. It is not
allowed to produce a current architecture claim. A future paid comparison must
use the authoritative integrated path and the identity artifact; it must not
select one of these legacy constructors.

## Regression

`tests/test_integrity_gate.py` and
`experiment_config.archived_mismatch_probe()` reproduce the archived defect:
the runtime label is `openai/gpt-5.6-sol` while the serialized request model is
`z-ai/glm-5.3-flash`. The request is rejected before any provider attempt.
