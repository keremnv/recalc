# Experiment Integrity Gate

Result: `EXPERIMENT_INTEGRITY_VERIFIED`

The gate is offline and recorded zero provider attempts. It treats
`RESOURCE_DEMAND_AUTOPSY_REPORT.md` as authoritative.

The full request-construction inventory, including retired direct probes, is in
`REQUEST_CONFIGURATION_AUDIT.md`.

## Request identity

The authoritative request configuration is
`benchmark/experiment_config.py::AUTHORITATIVE_EXPERIMENT_CONFIG`. It owns the
model, provider, reasoning effort, temperature, top-p, output cap, provider
pinning policy, and stage timeouts.

| Stage | Constructor | Wire assertion | Timeout |
|---|---|---|---:|
| Task IR | `matched_compiled_treatment.request_body` | `experiment_config.request_identity` | 600 s |
| Edit Plan | same | same | 600 s |
| Retrieval | same | same | 180 s |
| Synthesis | same | same | 180 s |

`matched_compiled_treatment.model_call` persists `declared_model`,
`request_model`, `response_model`, `declared_reasoning`,
`request_reasoning`, and effective generation parameters before the call. The
wire assertion runs before `urlopen`; a response model mismatch raises and is
retained as an identity failure by the feasibility ledger. Runtime configuration
can still change observation budgets and frontend mode, but request-identity
overrides are rejected.

`fm_resource_feasibility.frontend_body` and
`fm_resource_feasibility.treatment_request_body` now delegate to that same
constructor. Its direct `call_provider` path performs the same pre-wire and
post-response checks. The old resource runner no longer monkeypatches a
stage-specific request body.

The regression in `experiment_config.archived_mismatch_probe()` reproduces the
archived state: declared `openai/gpt-5.6-sol`, serialized request
`z-ai/glm-5.3-flash`. The probe is rejected before a provider attempt.

Historical direct probes retain their own archived constructors for replay
only; they are not valid entry points for the current experiment and are not
used by the gate or the next comparison.

## Fresh fidelity preflight

`benchmark/integrity_gate.py` creates a fresh isolated lineage from the exact
06_01 effective source workbook. It verifies source values through the fresh
compiled spine, SQLite, grounding projection, bootstrap evidence, archived
retrieval working-set IDs, and final synthesis packet. It includes positive
numeric, zero, text, formula, blank, and percentage-formatted numeric facts,
including the archived witnesses `DCF!C47`, `C48`, and `C51`. Negative numeric
and boolean values are unavailable in this source and are recorded explicitly.

The archived null witness values are classified at the earliest demonstrated
boundary as `stale database/cache lineage`: the archived spine omitted numeric
payloads and both archived databases stored null `raw_value`/`display_value`.
Fresh compilation and materialization preserve all available witness values.

## Evidence baseline and comparison freeze

`RESOURCE_EVIDENCE_ACCESS_BASELINE.md` documents all 16 frozen O3 target
manifests, shared record IDs, target deltas, retrieval history/state, and final
synthesis-visible records. C49 reconstructs content-equivalently from the
preserved content-addressed pool, manifest, and entity delta. This is a
lossless storage baseline only; it makes no stateless-model or token-saving
claim.

The old LibreCalc harness is not the current control. The external reference is
the published SpreadsheetBench 2 standard agent scaffold and official
evaluation. System benchmark claims and causal matched-backbone scaffold claims
are recorded separately. No FM20, model swap, matched control, or new frontend
IR was run.
