# Integration autopsy — failed matched 60-task treatment

Classification: **MULTIPLE_INTEGRATION_FAILURES**, dominated by frontend target loss and budget fragmentation. No new model calls were used. The artifacts do not support a claim that the earned mechanisms are harmful, nor a low-reasoning causal attribution.

## Primary findings

| Category | Gold content edits | Output edits | Output ∩ gold | Outside gold | Gold-write recall | Write precision |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 36584 | 97 | 62 | 35 | 0.17% | 63.92% |
| Template | 1129 | 12 | 11 | 1 | 0.97% | 91.67% |
| Financial_Model | 8716 | 60 | 35 | 25 | 0.40% | 58.33% |
| Debugging | 26739 | 25 | 16 | 9 | 0.06% | 64.00% |

The zero-edit-floor test finds **49/60 effectively inert** tasks using the predeclared |modification gain| ≤ 0.001 threshold. Per-cell official and value-only outcomes, including cells newly correct over floor, are retained in `scorer_cells/` and `zero_edit_floor_scores.json`.

There were 41 parseable proposals at true gold formula targets, 20 exact formula matches. 40 were written as proposed; the remainder were explicitly hard-rejected. The seven scheduler-dropped proposals were all non-gold targets. Thus proposal-to-writer loss is a real defect, but does not explain the missing useful writes in this run.

## Earliest supported loss

| Category | Task spec | Edit Plan authority | Scheduling | Operational |
|---|---:|---:|---:|---:|
| ALL | 9 | 33 | 17 | 1 |
| Template | 9 | 4 | 7 | 0 |
| Financial_Model | 0 | 12 | 7 | 1 |
| Debugging | 0 | 17 | 3 | 0 |

Earliest supported mechanical loss wins. Structured Task IR is empty on nine tasks. Invalid/empty authority or gold-content recall below 50% precedes scheduling. The other valid plans leave gold formula targets without sessions. No unsupported semantic judgments were used to separate F1 grounding from F2 authority: independent clause-level semantic annotations are absent from this run. The raw instruction survives in full, but that does not prove its structured requirements, subject or scope survive.

## Calls and budget fragmentation

The state totals sum to 1,936; the immutable call-file census has **1,937 provider attempts** plus 74 budget-block pseudo-call records. Financial_Model:04_01 contains both `002_edit_plan.json` (provider rejection) and `002_task_ir.json` (resumed parse), followed by `003_edit_plan.json`. This exactly explains the one-call undercount. Timeouts are attempts, not successful completions; their provider usage/cost is unavailable. Archived invalid earlier runs are excluded from this 60-task population.

| Stage | Attempts |
|---|---:|
| Task IR | 63 |
| Edit Plan | 54 |
| retrieval/query selection | 1622 |
| ungrouped-cell synthesis | 187 |
| canonical synthesis | 11 |
| Stochastic grounding | 0 |
| Dedicated closure-member synthesis | 0 |
| Other | 0 |

1,622/1,937 attempts (83.7%) were retrieval. Of 234 persisted target sessions, 176 used all eight retrieval turns. The normal active task reached the cap after about six sessions; 38 tasks reached 50 counted calls. The final retrieval episode could consume the remaining budget and prevent synthesis. No writes occurred until the terminal writer batch, so calls before the first useful gold write equal all task attempts when such a write exists; otherwise that metric is undefined.

The retrieval continuation passed `delta=None` even after 622 calls added entities, advertising an empty NEW_SINCE_LAST_TURN. Only the latest SQL result was shown on the next request. The synthesis prompt inherited a retrieval preamble explicitly saying not to synthesize. Both are protocol/composition defects. Their semantic effect cannot be measured by pretending stored responses would have changed under a corrected prompt.

## Authority and Financial_Model distribution

| Task | Gold edits | Authority | Gold recall | Formula recall | Precision | Plan status |
|---|---:|---:|---:|---:|---:|---|
| Financial_Model:01_01 | 82 | 105 | 46.34% | 46.34% | 36.19% | VALID_PLAN |
| Financial_Model:02_01 | 42 | 30 | 71.43% | 90.91% | 100.00% | VALID_PLAN |
| Financial_Model:03_01 | 280 | 260 | 14.29% | 14.61% | 15.38% | VALID_PLAN |
| Financial_Model:04_01 | 487 | 0 | 0.00% | 0.00% | N/A | SESSION_RESOURCE_LIMIT |
| Financial_Model:05_01 | 383 | 523 | 8.62% | 9.73% | 6.31% | VALID_PLAN |
| Financial_Model:06_01 | 83 | 3008 | 90.36% | 92.11% | 2.49% | VALID_PLAN |
| Financial_Model:07_01 | 894 | 4354 | 12.42% | 23.03% | 2.55% | VALID_PLAN |
| Financial_Model:08_01 | 807 | 756 | 72.12% | 94.17% | 76.98% | VALID_PLAN |
| Financial_Model:10_01 | 421 | 44 | 9.03% | 11.15% | 86.36% | VALID_PLAN |
| Financial_Model:11_01 | 40 | 42 | 67.50% | 67.50% | 64.29% | VALID_PLAN |
| Financial_Model:11_05 | 93 | 119 | 75.27% | 75.27% | 58.82% | VALID_PLAN |
| Financial_Model:12_05 | 59 | 0 | 0.00% | 0.00% | N/A | INVALID_ENTITY |
| Financial_Model:13_05 | 21 | 35 | 52.38% | 71.43% | 31.43% | VALID_PLAN |
| Financial_Model:14_05 | 3939 | 125 | 1.93% | 73.79% | 60.80% | VALID_PLAN |
| Financial_Model:15_05 | 614 | 585 | 60.42% | 60.42% | 63.42% | VALID_PLAN |
| Financial_Model:16_05 | 95 | 33 | 21.05% | 21.05% | 60.61% | VALID_PLAN |
| Financial_Model:17_05 | 72 | 64 | 19.44% | 35.90% | 21.88% | VALID_PLAN |
| Financial_Model:18_05 | 42 | 0 | 0.00% | 0.00% | N/A | INVALID_ENTITY |
| Financial_Model:19_05 | 65 | 0 | 0.00% | 0.00% | N/A | INVALID_ENTITY |
| Financial_Model:20_05 | 197 | 0 | 0.00% | 0.00% | N/A | INVALID_ENTITY |

Every frozen temporal JSON was an empty placeholder. The database therefore had no temporal coordinates even when the Edit Plan used TEMPORAL_INTERVAL and period IDs. This is a supported integration defect: the earned temporal compiler was not called. Restoring it uses input-only facts and does not change temporal inference rules. Plans that remain too narrow or broad after that repair are not repaired with benchmark-derived selection rules.

## Conditional synthesis and mechanism cash-out

There are 54 sessions selected at true gold formula targets. Under the mechanical direct-reference coverage definition, 35 have complete coverage; this does not prove semantic sufficiency. Exact formula and relative fingerprint results are cross-tabulated by existing/novel and retrieval coverage in `conditional_synthesis.csv`. False selected targets are excluded.

Runtime formed 17 ProgramGroups across the run, but just one in Financial_Model: Assumption sheet E44:F44 on 06_01. Both were false targets, and no grouped Financial_Model gold cells were cashed out. Evaluator-side missed eligible groups: {'member not scheduled': 83, 'target not authorised': 313, 'scheduler skipped group': 1}. Those causes are ordered observations, not proof that every authorized group would pass the runtime operation partition/witness contract.

There are 120 C1 execution records. All recorded execution members are inside authority: True. There are 52 recorded member occurrences which the old scheduler marks assigned in the current operation without a session or write. Safety containment held, but membership was incorrectly treated as completion. Group formation could also translate a seed into an unrelated prerequisite group and omit the seed's own write.

## Measurement limits and reproducibility

`funnel.json` contains all requested G/T/P/S/E/W/R stages per task and category. Cell stages report entering/surviving counts, intersection survival, gold recall and precision. Groups/programs/tasks have different units; null metrics denote non-comparable units or missing semantic-retention annotations, never guessed zeroes. Group and ungrouped branches merge at actuation, so the funnel has explicit predecessors rather than a misleading single nesting chain.

Semantic writes compare formula/literal content in the delivered output.xlsx against its effective input; recalculation-cache drift is not a write. Gold content differences ignore empty strings/whitespace as blanks, include all workbook cells, and use no score-derived tolerance. 06_01 is metadata repaired and included (83 content edits, 76 formula edits); the old structural census could not classify it. Financial_Model:04_01 has 487 semantic content edits under this rule versus the old census's 4,978; formula edits agree at 421. These definitions and denominator differences must not be conflated.

The zero-edit floor uses the exact staged original input copies and official LibreOffice refresh. Scoring invokes the official cell-classification and comparison functions, including Debugging Color/Embedded modes, formula-error fallback, four-decimal rounding and regression snapping. A compact read-only cell adapter prevents large workbook evaluations from retaining multiple full openpyxl object graphs; it changes no comparator. Official treatment scores are checked against the frozen scores before accepting this path.

Reproduce with `python benchmark/integration_autopsy.py analyze`, `score-details`, then `python benchmark/integration_report.py`. Gold/evaluator code is confined to the offline audit and report. The runtime scheduler imports no autopsy or gold data. Phase B remains blocked until the separate repair gates pass.
