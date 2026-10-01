# Integrated Feasibility Report

Verdict: `INTEGRATED_FEASIBILITY_RESOURCE_CENSORED`

This report is a zero-model rendering of the persisted 12-task Financial_Model feasibility run. The original sequential/one-worker plan was operator-adjusted during execution: remaining GLM tasks were continued in parallel and capped at 33¢ each, as requested. The report therefore preserves that execution fact rather than presenting it as a strict sequential replication.

## Funnel summary

The slice contains 12 tasks and 84 archived obligations. 12/12 tasks reached structurally valid Task IR; 10/12 produced schema-valid Edit Plans; 4/12 were marked complete; 10/12 had non-empty expanded authority; 10/12 reached retrieval; 10/12 reached synthesis; and 10/12 produced accepted semantic edits.

Evaluator-side authority gold is available for 4 tasks / 29 obligation rows, covering 1298 gold cells. The current authority shared 270 of those cells under the per-obligation accounting. Other tasks are reported as gold-unavailable rather than assigned synthetic precision/recall.

| Task | status | IR | plan | completeness | authority | gold | recall | precision | retrieval | synthesis | edits | calls | cost | earliest supported loss |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Financial_Model:01_01 | COMPLETED | yes | yes | PARTIAL | 67 | — | — | — | 124 | 17 | 13 | 150 | $0.5233 | NO_FRONTEND_GOLD_AVAILABLE |
| Financial_Model:03_01 | COMPLETED | yes | yes | PARTIAL | 638 | 280 | 0.914 | 0.401 | 122 | 21 | 10 | 150 | $0.3451 | EVIDENCE_PRESENT_MODEL_WRONG_SELECTION |
| Financial_Model:04_01 | COMPLETED | yes | no | NO_VALID_AUTHORITY | 0 | — | — | — | 0 | 0 | 0 | 9 | $0.0236 | PLANNER_RESPONSE_MISSING |
| Financial_Model:05_01 | COMPLETED | yes | yes | PARTIAL | 466 | 383 | 0.008 | 0.006 | 46 | 8 | 186 | 62 | $0.2048 | EVIDENCE_PRESENT_MODEL_WRONG_SELECTION |
| Financial_Model:06_01 | COMPLETED | yes | yes | PARTIAL | 78777 | — | — | — | 121 | 21 | 6 | 150 | $1.5470 | NO_FRONTEND_GOLD_AVAILABLE |
| Financial_Model:07_01 | NON_MODEL_FAILURE | yes | yes | PARTIAL | 1402 | — | — | — | 122 | 20 | 253 | 150 | $0.5801 | WRITER_FAILURE |
| Financial_Model:08_01 | COMPLETED | yes | yes | COMPLETE | 781 | — | — | — | 73 | 9 | 66 | 92 | $0.3310 | NO_FRONTEND_GOLD_AVAILABLE |
| Financial_Model:12_05 | COMPLETED | yes | yes | COMPLETE | 38 | — | — | — | 40 | 6 | 27 | 53 | $0.1624 | NO_FRONTEND_GOLD_AVAILABLE |
| Financial_Model:13_05 | COMPLETED | yes | yes | COMPLETE | 32 | 21 | 0.524 | 0.344 | 82 | 11 | 11 | 100 | $0.2555 | EVIDENCE_PRESENT_MODEL_WRONG_SELECTION |
| Financial_Model:14_05 | COMPLETED | yes | yes | COMPLETE | 86 | — | — | — | 117 | 15 | 42 | 139 | $0.3307 | NO_FRONTEND_GOLD_AVAILABLE |
| Financial_Model:15_05 | COMPLETED | yes | no | NO_VALID_AUTHORITY | 0 | 614 | 0.000 | — | 0 | 0 | 0 | 9 | $0.0518 | PLANNER_SCHEMA_OR_ENTITY_FAILURE |
| Financial_Model:17_05 | COMPLETED | yes | yes | PARTIAL | 38 | — | — | — | 84 | 11 | 14 | 102 | $0.3305 | NO_FRONTEND_GOLD_AVAILABLE |

## Static integration preflight

The activation audit was `STATIC_COMPLETE` with zero predicate violations. It recorded 2 population/member activations, 17 output-role activations, five distinct output endpoints, and five candidate additions. Output-role activation occurred only in the studied `Financial_Model:05_01` task. These relations remained planner evidence/candidate structure and did not grant authority automatically.

## Scheduling, retrieval, synthesis, and execution

Across tasks, 628 semantic writes were scheduled and 625 persisted. 1 task(s) had writer rejections. ProgramGroup canonical decisions, deterministic translations, dependency-coordinated groups, disposition statuses, residual authority, and provider failures are retained per task in the census JSON/CSV. Provider failures are not counted as model abstentions.

LibreOffice refresh and metadata-tolerant scorer execution were healthy for all 12 scored outputs; missing outputs were 0. Exact-task count was 0/12; this is a feasibility funnel measurement, not a matched control comparison.

## Attribution

The largest task-level residual is `06_01`: authority 78777, with 78756 unresolved authorized targets at the resource bound. The census distinguishes invalid plans, evidence-present planner selection errors, resource censoring, writer failures, and no-frontend-loss cases. Aggregate earliest-loss labels are `{"EVIDENCE_PRESENT_MODEL_WRONG_SELECTION": 3, "NO_FRONTEND_GOLD_AVAILABLE": 6, "PLANNER_RESPONSE_MISSING": 1, "PLANNER_SCHEMA_OR_ENTITY_FAILURE": 1, "WRITER_FAILURE": 1}`.

## Resource envelope

The integrated GLM funnel consumed 1166 calls, $4.6858, and 27,603,535 reported tokens (23,604,215 prompt, 3,999,320 completion, 3,829,024 reasoning). 7 tasks were resource-censored and 112 call records were provider failures. See the companion cost report for stage/task concentration and evidenced wastes.

## Decision gate

`INTEGRATED_FEASIBILITY_RESOURCE_CENSORED`

The current result is resource-censored: it demonstrates meaningful end-to-end work and a healthy writer/LibreOffice/scorer bridge, but the ceiling/provider failures prevent an uncensored feasibility claim. The narrow next step is to freeze this resource envelope and prospectively specify a limited-domain control comparison after the persisted ledgers are reviewed; no new frontend abstraction is justified by this run alone.

## Artifacts

- Census: `integrated_feasibility_census.json`, `integrated_feasibility_census.csv`
- Cost report: `INTEGRATED_FEASIBILITY_COST_REPORT.md`, `integrated_feasibility_cost.json`, `integrated_feasibility_cost.csv`
- Static activation: `integrated_static_activation.json`, `integrated_static_activation.csv`
- Raw GLM task ledgers: `/home/kerem/Desktop/Personal Projects/librecalc-mcp/benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/resource_feasibility/clean_integrated/live`
- Scorer output: `/home/kerem/Desktop/Personal Projects/librecalc-mcp/benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/resource_feasibility/clean_integrated/live/official_scores.json`
