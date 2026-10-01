# SpreadsheetBench 2 public trajectory audit

Audit date: 2026-08-25.

## What is public

The official dataset repository publishes `trajectory_example.zip`, a 158 MB archive with full
SWE-agent trajectories, trace/debug logs, predictions, and configs. It contains five examples from
each of the four categories for each of the eight paper models: 160 model-task trajectories in all.
It is not the complete result set, so it cannot reveal every task passed or failed in the reported
full-benchmark scores.

The 15 non-visual tasks are frozen as the contaminated development slice
`benchmark/slices/public-example-nonvisual-v1.json`. They must never be reported as held-out or
competitive results.

Sources:

- Project and live leaderboard: <https://spreadsheetbench.github.io/>
- Official code: <https://github.com/RUCKBReasoning/SpreadsheetBench-2>
- Dataset and trajectory archive: <https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2>
- Paper: <https://arxiv.org/abs/2606.29955>

## Current leaderboard correction

The live official V2 leaderboard does not list Claude Opus 5. As of the audit date, the top three
entries are arito at 45.46%, WPS AI at 42.27%, and Claude Opus 4.6 with SWE-agent at 34.89%.
The paper result is the Opus 4.6 row. Opus 5 appears on other agent leaderboards, which likely
caused the name confusion.

## Replayed Opus 4.6 examples

The published non-visual Opus actions were replayed sequentially in the official local Docker image,
with networking disabled, and the resulting workbooks were recalculated and scored by the unmodified
official evaluator. This reproduces the actions already present in the public traces; it is not a new
model run. `Cost` is SWE-agent's trace-reported instance cost, not independently reconciled provider
billing.

| Category | Task | Exact | Regression | Modification | Calls | Cost | Golden accessed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Template | `01_01` | 1 | 1.0000 | 1.0000 | 11 | $3.174125 | no |
| Template | `02_02` | 1 | 1.0000 | 1.0000 | 11 | $1.195300 | yes |
| Template | `02_04` | 1 | 1.0000 | 1.0000 | 10 | $0.779805 | no |
| Template | `06_01` | 0 | 1.0000 | 0.8500 | 11 | $0.916765 | no |
| Template | `16_08` | 1 | 1.0000 | 1.0000 | 11 | $0.546620 | yes |
| Financial Model | `09_01` | 1 | 1.0000 | 1.0000 | 27 | $6.250340 | no |
| Financial Model | `09_02` | 1 | 1.0000 | 1.0000 | 21 | $4.040390 | no |
| Financial Model | `09_03` | 1 | 1.0000 | 1.0000 | 19 | $3.446900 | no |
| Financial Model | `09_04` | 0 | 1.0000 | 0.9981 | 30 | $8.403125 | no |
| Financial Model | `09_05` | 0 | 1.0000 | 0.9635 | 17 | $2.666250 | no |
| Debugging | `04_06` | 0 | 1.0000 | 0.8424 | 18 | $2.461645 | yes |
| Debugging | `05_03` | 0 | 1.0000 | 0.0000 | 23 | $2.985140 | no |
| Debugging | `07_01` | 0 | 0.9969 | 0.0000 | 24 | $4.594535 | no |
| Debugging | `08_03` | 0 | 1.0000 | 0.0000 | 31 | $6.679200 | no |
| Debugging | `10_02` | 0 | 1.0000 | 0.7021 | 26 | $5.491400 | no |

| Category | Exact | Mean regression | Mean modification | Calls | Trace cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Template | 4/5 | 1.0000 | 0.9700 | 54 | $6.612615 |
| Financial Model | 3/5 | 1.0000 | 0.9923 | 114 | $24.807005 |
| Debugging | 0/5 | 0.9994 | 0.3089 | 122 | $22.211920 |
| Overall | 7/15 | 0.9998 | 0.7571 | 290 | $53.631540 |

This five-task-per-category subset is not representative of the full benchmark and its 46.67% exact
rate must not be compared directly to leaderboard scores. It is useful because it exposes matched
frontier behavior at task level.

### `Template:06_01` is a defective-golden case

A clean, gold-blind Opus 5 run through LibreCalc reproduced the Opus 4.6 result exactly: 34/40
modification cells (85%) and 308/308 regression cells. It used six model/tool calls, cost $0.383785,
and completed in 89.16 seconds. The miss is not a model or interface failure.

The golden workbook contains the correct first-period formulas at `IncomeStmt!D18:D19`, but its
translated cells `E18:G18` and `E19:G19` are literally `=#REF!`. Both Opus versions generated valid
relative formulas across all four periods, producing the intended gross-profit values and margins.
The official evaluator therefore penalizes six semantically correct formulas for not reproducing the
golden workbook's broken references.

Keep this task as a regression fixture for evaluator/golden-quality detection, not as an intelligence
threshold or tool-design task. LibreCalc should surface such discrepancies; it should not learn to
manufacture spreadsheet errors merely to imitate a defective golden file.

### Clean `Template:01_01` threshold probe

The public Opus 4.6 example solved `01_01` exactly in 11 calls at a trace-reported cost of $3.174125,
without golden-workbook access. Fresh gold-blind OpenRouter probes through LibreCalc found two
earlier boundaries before producing a scored workbook:

| Model/configuration | Result | Calls | Charged cost |
| --- | --- | ---: | ---: |
| Kimi K2.5, progressive | Three parallel reads violated the one-tool contract; no output | 2 | $0.002156940 |
| Kimi K2.5, overview-only, 4K | Exhausted 4,096 visible analysis tokens; no action | 2 | $0.010627630 |
| Kimi K2.5, overview-only, 8K | Exhausted 8,192 visible analysis tokens; no action | 2 | $0.019608570 |
| Opus 5, progressive, high reasoning | Exhausted the reasoning budget; no action | 2 | $0.134715000 |
| Opus 5, progressive, high reasoning, one repair | Exhausted two reasoning windows; no action | 4 | $0.291160000 |
| Opus 5, progressive, low reasoning, one repair | Workbook; 380/381 regression and 72/87 modification | 5 | $0.344300000 |

The completed Opus 5 workbook missed exactness because of one coherent accounting choice. It carried
the tax-basis loan at face value rather than issue price, causing 15 target-cell errors in the tax
loan, year-six cash tax, and DTA reversal schedules. The unreversed `H22` DTA was the sole regression
error. This is a reasoning/inspection miss, not an execution-encoding failure: one compact formula
call wrote all intended ranges, recalculation succeeded, and the semantic comparison completed.

The exact public Opus 4.6 trajectory did more than inspect and write. It dumped the full sheet,
inspected formatting through `openpyxl`, attempted two generated Python programs, and finished with
explicit numerical assertions: total discount amortization equals `$2,850`, year-six DTA equals
zero, deferred taxes sum to zero, the GAAP loan reaches face value, and the tax balance-sheet identity
holds. The fresh Opus 5 trace verbally expected the DTA to reverse but never tested that invariant.
This is evidence for an agent-specified deterministic assertion/check surface, not for embedding
bond-accounting logic in LibreCalc. Require repetition on another ladder task before adding it.

The trace also exposed two harness/observation defects. SWE-agent had been configured with no actual
format-repair response; the runner now permits one bounded repair by default. The semantic snapshot
truncated the decisive `J11` note after 120 characters, omitting “via reversal of DTAs”; the general
label budget is now 240 characters with regression coverage. Do not rerun this paid probe merely to
tune the task. Test the observation change on the next ladder task and reserve `01_01` as a recorded
threshold case.

## Golden-workbook access

Five of the 160 public model-task trajectories explicitly read a golden workbook, and the recorded
actions succeeded:

- Claude Opus 4.6: `Debugging:04_06`, `Template:02_02`, `Template:16_08`.
- GPT-5.2: `Template:02_02`.
- DeepSeek V3.2: `Template:02_04`.

For example, the Opus `Debugging:04_06` trajectory compares the input against the golden workbook,
identifies cell-level differences, and ends with a script reporting that all cells match the golden
file. The two golden-assisted Template tasks scored exact in the replay; the golden-assisted Debugging
task still failed.

This does not prove how often golden access occurred outside the public sample, but it means the
published Opus result cannot be assumed to be gold-blind. The current repository documentation says
new runs mount only the selected input workbook, suggesting the harness has since been tightened.
LibreCalc competitive runs must continue using the stricter isolation rule: the agent receives one
read-only input workbook and a private writable output directory, with golden files withheld until
evaluation.

## What the failures imply for LibreCalc

The public traces reinforce three distinct engineering targets:

1. **Residual-error elimination.** Opus loses `Financial_Model:09_04` at 99.81% modification
   accuracy. Exact-match scoring makes deterministic semantic diff and completeness checks more
   valuable than another broad implementation pass.
2. **Grounded target selection.** Debugging is the fracture point. The interface needs formula-error,
   pattern-anomaly, dependency, and style-semantic evidence tied to exact candidate cells; a general
   workbook dump merely transfers localization work back to the model.
3. **Bounded mutation scope.** Debugging traces often preserve almost the whole workbook while fixing
   none of the required cells, or alter a wrong cell. Candidate-based edits plus pre-commit semantic
   diffs should make unsupported changes conspicuous.

The sole public `09_04` error is an omitted `Valuation!G59` formula (`=E48`), the WACC anchor at the
top-left of a sensitivity table. The current row-label candidate-gap heuristic does not flag it
because the `WACC` header is in `G58`, one row above the blank, while the neighboring growth-rate
series occupies `H59:L59`. A stricter offline table-corner signal (text above and above-right,
populated cells right and below) did nominate `G59`, but across all 15 public non-visual inputs it
produced 23 candidates for one true modified-cell hit: 4.35% precision and 0.14% recall. Reject it
as an automatic target selector. Future work should rank anomalies using several contextual signals
and expose the evidence, not turn this single sensitivity-table shape into a rule.

The next development ladder should start with three public, non-golden-access tasks:

1. `Template:01_01` — a clean exact Opus bond-accounting schedule with real sign and carry-forward
   reasoning.
2. `Financial_Model:09_04` — a near-perfect frontier miss that tests residual detection.
3. `Debugging:10_02` — unit-mismatch debugging where Opus reached 70.21% modification accuracy.

Establish a clean exact upper-model anchor on each task before descending to cheaper models. The
offline formula-anchor observation study did not clear the precision bar, so run `09_04` with the
existing interface rather than contaminating the comparison. Add a primitive only after a repeated
trace demonstrates that the missing information or action cannot be expressed cleanly by the
existing semantic snapshot and program operations.

The clean run itself supplied that repeated evidence for a different primitive. A structural
overview localized every requested region, but Opus repeatedly tried to read two independent ranges
in parallel; strict one-tool transport converted each attempt into a paid repair. The resulting run
spent `$1.151565` with no mutation and is invalid as a capability result. `calc_read_ranges` was added
as the general amortized inspection counterpart to range-based writes. This is not a sensitivity-
table special case: it accepts arbitrary explicit sheet/range requests and opens the workbook once.
