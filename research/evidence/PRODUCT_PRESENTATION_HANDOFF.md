# Product and presentation handoff

The architecture is frozen. This is a registry for future engineering and communication; no installer, packaging, UI, website or marketing was built here. See [FINAL_ARCHITECTURE_FREEZE.md](FINAL_ARCHITECTURE_FREEZE.md).

The intended experience remains: install → configure an ordinary coding agent/model → point it at workbook tasks → use ordinary Python/openpyxl. Invisible deterministic runtime activates only where safe; unsupported cases use ordinary behavior. There is no new spreadsheet-specific interaction model. The optional helper contract is unchanged and uses reference openpyxl.

Future minimum installability requirements:

- single documented installation path.
- dependency/bootstrap check.
- LibreOffice availability check where recalc/validation is required.
- clear enable/disable configuration for invisible runtime.
- safe default behavior.
- fail-closed operation when optional substrate is unavailable.
- minimal example task.
- diagnostic command/status output.
- versioned compatibility statement.

`BASIC_INSTALLABILITY_AND_PACKAGING` is a `PRODUCTIZATION_TASK`, `NOT_RESEARCH_MECHANISM`. `EVIDENCE_PRESENTATION_AND_CLAIMS` is a `COMMUNICATION_TASK`, `NOT_RESEARCH_MECHANISM`. Both are authorized future work after the freeze; neither reopens architecture. Package the chosen maintained harness, establish compatibility, and make enable/disable and diagnostics clear. Decide optional helper-surface product value separately.

Presentation claims registry:

| CLAIM | STATUS | STRONGEST EVIDENCE | SCOPE | WHAT WE MUST NOT SAY |
|---|---|---|---|---|
| Ordinary Python remains the model-facing working interface | EARNED | [OLD_HARNESS_COMPONENT_TRANSFER_AUDIT.md](OLD_HARNESS_COMPONENT_TRANSFER_AUDIT.md); [THIN_ARCHITECTURE_SYSTEM_CHECKPOINT_REPORT.md](THIN_ARCHITECTURE_SYSTEM_CHECKPOINT_REPORT.md) | Tested coding-agent scaffold | Python is universally optimal |
| A structured semantic waist was not required by the tested coding agent | SUPPORTED | [ARCHITECTURE_EVIDENCE_FREEZE.md](ARCHITECTURE_EVIDENCE_FREEZE.md); [OLD_HARNESS_COMPONENT_TRANSFER_AUDIT.md](OLD_HARNESS_COMPONENT_TRANSFER_AUDIT.md) | Tested agent and transfer studies | All spreadsheet agents should reject structured interfaces |
| Transparent conservative read acceleration is exact on its earned surface | EARNED | [candidate_a_a1_checkpoint_rerun_01/exact_trace_fidelity.json](../history/candidate_a_a1_checkpoint_rerun_01/exact_trace_fidelity.json); [final_architecture_freeze/fail_closed_tests.json](../history/final_architecture_freeze/fail_closed_tests.json) | 51/51 historical traces and focused primitive regressions; unsupported structures fall back | General openpyxl replacement or all inputs proven exact |
| Conditional read acceleration can pay materially on large-workbook tails | SUPPORTED | [CANDIDATE_A_A1_12_TASK_CHECKPOINT_RERUN_REPORT.md](CANDIDATE_A_A1_12_TASK_CHECKPOINT_RERUN_REPORT.md); [representative_architecture_checkpoint/economics.json](../history/representative_architecture_checkpoint/economics.json) | Conditional read traces and representative unit-cost estimates; tail-heavy economics | Universally faster, total-task speedup, or compiled substrate always pays |
| Mutation capture provides cheap deterministic assurance | EARNED | [TRANSPARENT_CAPTURE_REPLAY_REPORT.md](TRANSPARENT_CAPTURE_REPLAY_REPORT.md); [THIN_ARCHITECTURE_SYSTEM_CHECKPOINT_REPORT.md](THIN_ARCHITECTURE_SYSTEM_CHECKPOINT_REPORT.md); [representative_architecture_checkpoint/economics.json](../history/representative_architecture_checkpoint/economics.json) | Fidelity/validation/generation checks; .34s for 16 checkpoint mutations | Capture prevents corruption in practice or is capability-required |
| Context repetition is not a material bottleneck in the measured corpus | SUPPORTED | [TRACK_C_TERMINAL_PROJECTION_AUDIT.md](TRACK_C_TERMINAL_PROJECTION_AUDIT.md) | 71 trajectories/70 tasks; C0/C1 ~1.65%, C2 ~1.68% | Context repetition never matters for other agents/corpora |
| Large first-seen context does not imply a mechanically removable projection | SUPPORTED | [TRACK_C_TERMINAL_PROJECTION_AUDIT.md](TRACK_C_TERMINAL_PROJECTION_AUDIT.md) | Large P2 oracle mass; 9 no-hindsight selectors failed gate | Unlinked context is useless or compressible without decision loss |
| Unsupported optimized paths fall back rather than replacing semantics | SUPPORTED | [final_architecture_freeze/corrective_replay.json](../history/final_architecture_freeze/corrective_replay.json); [final_architecture_freeze/fail_closed_tests.json](../history/final_architecture_freeze/fail_closed_tests.json) | Hardened optional index/load boundary; reference may itself reject invalid input | Malformed workbooks are repaired or guaranteed to succeed |
| Cumulative practical-stack capability preservation is supported | SUPPORTED | [final_architecture_freeze/cumulative_capability_evidence.json](../history/final_architecture_freeze/cumulative_capability_evidence.json) | Independent tested causal scopes, corrected parser veto; checkpoint neutrality only narrow | Better benchmark scores, formal capability equivalence, or all completion gaps disproven |

Do not claim better benchmark scores, universal speed, universal Python optimality, formal capability equivalence, an always-profitable substrate, observed corruption prevention, or applicability to every spreadsheet agent. Do not turn nonsignificance into equivalence or the corrective replay into a new model result.

Research synthesis for a future technical narrative: **Preserve semantic freedom in the coding agent; move only proven mechanical work underneath its existing interface.** This is a scoped experimental conclusion, not marketing copy. Present the negative results, censored outcomes, tail dependence, and retention-versus-rebuild distinction with the positive fidelity and assurance evidence. The product should expose less architecture than the research required to discover it.
