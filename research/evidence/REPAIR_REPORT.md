# Integration repair report

Repair gate status: **PASS**. Phase A made zero new model calls.

## Supported repairs

- Separate authorized, attempted and completed targets. C1 dependency membership schedules work; it cannot mark an unsolved member complete.
- Always retain a verified seed write. Apply deterministic translation only within that seed's witnessed group. Form groups across authorized operation peers using the existing witness algorithm, and do not synthesize translated members again.
- Persist sessions, per-target dispositions, unresolved targets and writer outcomes. Preserve raw request/response records, reconcile resume budgets from the ledger, distinguish budget-block events from attempts, and atomically replace state files.
- Restore the existing temporal compiler instead of supplying empty coordinate placeholders. Replay converts four formerly invalid Financial_Model Edit Plans to valid plans without changing a model response.
- Forward the actual working-set delta, remove the conflicting retrieval prohibition from the synthesis transition, reserve the final call for synthesis, and materialize retained entities plus the sheet-name map and implicit blank targets without silently losing rows.
- Read target content from the already compiled input payload rather than reopening a workbook for each deterministic translation.

No financial ontology, candidate selector, semantic verifier, Program Sketch/Operand Binding IR, gold-derived ranking, or formula-repair rule was added. Gold is confined to evaluator-side analysis. The existing writer and formula verifier are reused.

## Deterministic replay

| Population | Old semantic writes | Replay semantic writes | Old gold writes | Replay gold writes |
|---|---:|---:|---:|---:|
| ALL | 97 | 121 | 62 | 77 |
| Financial_Model | 60 | 90 | 35 | 50 |

Mean replay modification delta versus the old treatment: +0.001368. This is a deterministic composition effect, not model improvement. Per-task old/replay recall, scores and value-only results are in `deterministic_replay_scores.json`.

Replay reuses every available archived session; a missing canonical response remains explicitly missing. More permissive authority cannot invent responses for formerly blocked tasks. Repaired prompts and delta presentation cannot change already-paid answers, so their model effects await the fresh matched run.

## Gates

| Gate | Pass |
|---|---|
| writer_neutrality | True |
| no_proposal_silently_dropped | True |
| call_count_accounting_exact | True |
| programgroup_no_resynthesis | True |
| closure_authority | True |
| deterministic_replay_complete | True |
| task_state_survives_resume | True |
| all_returned_raw_model_outputs_retained | True |
| all_fixes_covered_by_tests | True |

The repair test run has 122 passing tests, plus four fresh matched-gateway tests. Tests cover resume, crash-safe state, call accounting, hard rejects, closure authority, group no-resynthesis, seed preservation, temporal materialization, blank evidence, raw-output retention, shared model configuration, and writer compatibility. The unchanged writer passes a byte-for-byte zero-write neutrality check on all 60 effective input copies.

The replay gate exposed four shared-formula-master rejections. Each proposal was identical to the input formula. The scheduler now records NO_SEMANTIC_CHANGE and continues group/closure coordination without sending that redundant write to the writer. The archived replay was reconciled through this exact deterministic no-op branch and rescored where the output archive changed.

The memory-safe evaluator adapter retains the official scorer functions. All 60 reconstructed treatment modification scores match their frozen official scores. The desktop interruption revealed high memory consumption from simultaneously loaded workbook object graphs; compact streaming value/formula views avoid that overhead without changing scoring semantics.

The source freeze is recorded in `repair_gates.json`; `repair.diff` contains the runtime repair against a preserved pre-edit source snapshot plus new scheduler/test files. Existing unrelated worktree changes were preserved. No repository-wide commit was made because the workspace already contained extensive user-owned uncommitted research.

Phase B is a new paired Financial_Model experiment. Historical low-reasoning scores are descriptive only. Its entry point refuses inference unless these gates pass and source hashes still match. Maximum supported reasoning must be established from provider capability evidence and frozen identically for both arms before any benchmark call.

## Outstanding Phase B resource condition

9/20 repaired archived plans exceed 50 model calls even at the optimistic bound of one decision per witnessed group or ungrouped authorized target plus two frontend calls, excluding all retrieval. Examples: 01_01 requires at least 84 calls; 06_01 at least 1,300. This does not predict the new model's plans, but it prevents claiming Phase A established a comfortable 50-call envelope.

The user explicitly requires a ceiling that avoids the previous censoring problem and forbids raising it merely to hide scheduler inefficiency. The remaining broad/fragmented authority cannot be narrowed using gold or a new selector under the authorized repair policy. Phase B is therefore held at resource preflight. No model capability inference or benchmark inference has been made. Free provider catalog metadata declares supported_efforts=[max, high, low], in descending order. The model-only configuration is frozen identically for both arms in model_configuration_freeze.json: model=z-ai/glm-5.3-flash, temperature=0, reasoning.effort=max, top_p=1, provider={allow_fallbacks:true, require_parameters:true}. No effort mapping is used. The full experiment/resource freeze is still pending. A separate frontend/resource feasibility probe or an explicitly opportunity-limited comparison would require a changed experimental decision.

The full 20-task lower-bound distribution is retained in `resource_envelope_audit.json`. This is an outstanding experimental condition, distinct from the nine deterministic integration repair gates.
