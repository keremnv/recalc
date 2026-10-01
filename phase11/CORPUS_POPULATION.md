# Corpus population — Phase 11

## ORDINARY PYTHON POPULATION (primary census base)

SWE-agent-style runs: model drives `bash` (incl. `python`/`python3`),
`view_xlsx`, `submit` against a task workdir. No MCP semantic tools, no
required IR, no planner authority. All runs below carry at least a
model-visible transcript (`transcript.jsonl` or `transcript_full.jsonl`), a
`run_record.json`, and input/output workbooks.

| Source | Runs | Arms | Model | Families |
|---|---|---|---|---|
| `representative_architecture_checkpoint/reps` | 59 | H0/H1 | z-ai/glm-5.3-flash | Template/Debugging/Financial_Model |
| `token_affordance_discovery/runs/primary` | 48 | A/B/C/D | GLM-family | Template/Debugging/Financial_Model |
| `inspection_efficiency_ab/reps` | 28 | C0/C1 | GLM-family | Template/Debugging/Financial_Model |
| `batch_write_helper_ab/reps` | 26 | C0/C1 | z-ai/glm-5.3-flash | Template/Debugging/Financial_Model |
| `live_transparent_runtime_ab/runs` | 18 | H0/H1 | GLM-family | Financial_Model (+others) |
| **Total primary** | **179** | | | |

Treatment arms (H1/C1/B–D variants) offered optional helpers/shims; prior
`helper_usage` analyses show agents usually bypassed them
(`available_but_bypassed: true`, zero helper calls typical), so treatment
runs remain ordinary-Python behavior for reachability purposes. Where a run
demonstrably used a helper for the coded fact, that event is excluded from
the *natural* reachability denominator and noted.

Outcome data: `capability_scores.json` per experiment
(`official_exact`, `official_modification`, `official_regression`,
`eval_error`, `usable_workbook`, `task_completed`, run status). Gold/evaluator
data is used ONLY to classify outcomes and failure relevance — never to
generate candidate facts (§38).

Status mix (114 run_records surveyed): SUBMITTED 43, NO_SUBMIT 43,
TRUNCATED_CALL_LIMIT 12, PROVIDER_CENSORED 13, other 3. Non-completed runs
contribute inspection/reachability evidence (R0–R3) but no submit-decision
events.

## OLD STRUCTURED HARNESS (historical context only)

`benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/*semantic*`,
`*commit-*`, `*viz*`, MCP-era runs using `calc_*` semantic tools: ~1000+
`.traj` files. Used ONLY for historical examples and counterevidence (§30);
never for prevalence. The old harness changes the discovery surface
(tool-provided structure), so mixing it into reachability rates would be
invalid.

## Workbook snapshots

Every primary run has `input.xlsx` (pre-action) and usually `output.xlsx`
(post-action) in its workdir or rep dir. Deterministic derivations run
offline against these with openpyxl + zipfile only. Recalculated values use
stored cached values in the artifacts (LibreOffice recalc is NOT rerun in
Phase 11 except where a stored recalc artifact already exists; otherwise the
candidate is coded R0/`UNOBSERVABLE_FROM_ARCHIVE` for the recalc-dependent
part).

## Exclusions

- `reps_preserved_infra*` / retry sets: infrastructure duplicates, excluded
  from denominators (noted where inspected).
- Censored/truncated runs: included for inspection evidence, excluded from
  submit-decision denominators.
- Runs whose transcript is missing observations (request-only logs): coded
  `UNOBSERVABLE_FROM_ARCHIVE` for observation-dependent candidates.
