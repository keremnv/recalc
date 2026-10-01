# Integrated Feasibility Cost Report

This report attributes provider cost from immutable per-call ledgers. It separates semantic demand, provider failures, resource censoring, and evidenced orchestration/authority expansion. Writer, LibreOffice, and scorer operations are not provider calls and have zero model cost.

## Integrated GLM total: 1166 calls / $4.6858

Reported tokens: 27,603,535 total, 23,604,215 prompt, 3,999,320 completion, 3,829,024 reasoning.

| Stage | calls | cost | prompt tokens | completion tokens | total tokens |
|---|---:|---:|---:|---:|---:|
| edit_plan | 84 | $0.3851 | 604,678 | 680,151 | 1,284,829 |
| retrieval | 931 | $2.5642 | 11,529,452 | 2,804,561 | 14,334,013 |
| synthesis | 139 | $1.7027 | 11,457,284 | 445,610 | 11,902,894 |
| task_ir | 12 | $0.0339 | 12,801 | 68,998 | 81,799 |

## Cost by task

| Task | calls | cost | ceiling | status | provider failures | wall seconds |
|---|---:|---:|---:|---|---|---:|
| Financial_Model:01_01 | 150 | $0.5233 | $6.0 | COMPLETED | {"PROVIDER_TIMEOUT": 8} | 7623.4 |
| Financial_Model:03_01 | 150 | $0.3451 | $6.0 | COMPLETED | {"PROVIDER_TIMEOUT": 25} | 10290.5 |
| Financial_Model:04_01 | 9 | $0.0236 | $6.0 | COMPLETED | {"PROVIDER_TIMEOUT": 2} | 1993.5 |
| Financial_Model:05_01 | 62 | $0.2048 | $6.0 | COMPLETED | {"PROVIDER_TIMEOUT": 8} | 4628.3 |
| Financial_Model:06_01 | 150 | $1.5470 | $6.0 | COMPLETED | {"PROVIDER_TIMEOUT": 28} | 12909.4 |
| Financial_Model:07_01 | 150 | $0.5801 | $6.0 | NON_MODEL_FAILURE | {"PROVIDER_ERROR": 8, "PROVIDER_TIMEOUT": 8} | 36967.9 |
| Financial_Model:08_01 | 92 | $0.3310 | $0.33 | COMPLETED | {"PROVIDER_TIMEOUT": 2, "TASK_COST_LIMIT": 1} | 4872.6 |
| Financial_Model:12_05 | 53 | $0.1624 | $0.33 | COMPLETED | {"PROVIDER_TIMEOUT": 4} | 3538.8 |
| Financial_Model:13_05 | 100 | $0.2555 | $0.33 | COMPLETED | {"PROVIDER_TIMEOUT": 3} | 5070.6 |
| Financial_Model:14_05 | 139 | $0.3307 | $0.33 | COMPLETED | {"PROVIDER_TIMEOUT": 8, "TASK_COST_LIMIT": 1} | 6868.5 |
| Financial_Model:15_05 | 9 | $0.0518 | $0.33 | COMPLETED | {} | 1144.5 |
| Financial_Model:17_05 | 102 | $0.3305 | $0.33 | COMPLETED | {"PROVIDER_TIMEOUT": 5, "TASK_COST_LIMIT": 1} | 7013.9 |

## Evidenced cost concentrations and wastes

- Authority expansion is the clearest architecture-induced demand hotspot. `06_01` authorized 78,777 cells, left 78,756 unresolved at the bound, and produced six accepted edits; `05_01` and `07_01` also carried large authority/residual populations. This is not evidence that all those cells were semantically needed.
- Retrieval used the largest number of calls and synthesis used the largest individual prompts. The largest successful synthesis contexts were roughly half a million prompt tokens in `06_01`, making repeated full working-set context a directly evidenced cost driver.
- The GLM ledger contains 112 provider-failure call records: {"PROVIDER_ERROR": 8, "PROVIDER_TIMEOUT": 101, "TASK_COST_LIMIT": 3}. These are provider wastage/latency and are kept separate from explicit abstentions and invalid model responses.
- 7 integrated tasks were capped. The three remaining-task 33¢ caps crossed slightly on their final successful responses (`08_01`, `14_05`, `17_05`); the configured ceiling stopped subsequent work but cannot undo the already completed response charge.
- The 07_01 wall-clock value is inflated by interruption/resumption history and should not be interpreted as a clean per-call latency sample. The run also deviated from the original one-worker sequence when remaining capped tasks were parallelized by request.

## One-off GPT comparison (not part of integrated total)

`openai/gpt-5.6-sol`, reasoning `high`, task `06_01`: 92 calls, $0.7490, 5,556,261 tokens. It was intentionally stopped after crossing the requested 66¢ cutoff; no result was persisted, so it is a partial cost/call comparison only and must not be scored as a completed task.

## Recommendation

Freeze the current envelope before changing architecture. The highest-value cost-control experiment is a bounded authority/working-set treatment for 06_01 that measures whether the same accepted edits can be reached without the 78k-cell expansion, followed by a prospectively specified limited-domain control comparison. Do not interpret that as permission to widen or redesign authority algebra in this feasibility report.

Machine-readable detail: `integrated_feasibility_cost.json` and `integrated_feasibility_cost.csv`. Raw ledgers remain under `/home/kerem/Desktop/Personal Projects/librecalc-mcp/benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/resource_feasibility/clean_integrated/live` and `/home/kerem/Desktop/Personal Projects/librecalc-mcp/benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/resource_feasibility/clean_integrated/model_swap_gpt56_sol_high`.
