# Benchmark plan

## North star

SpreadsheetBench 2.

Treat its task categories as the requirements backlog:

1. Template tasks: mechanics and correctness.
2. Financial modeling: cross-sheet reasoning and large patterned edits.
3. Debugging: dependency traversal and formula anomaly discovery.
4. Visualization: charts/pivots after the computational world is solid.

## Breadth regression

Use SpreadsheetBench / SpreadsheetBench Verified when practical to catch missing everyday spreadsheet operations.

## Later quality bar

Use BlueFin later for dynamic correctness, integration, and professional-model behavior rather than making finance expertise a v1 requirement.

## Experimental hypothesis

A thick semantic world plus one-call program execution should outperform a thin spreadsheet tool interface for identical frontier agents.

## Evaluation hygiene

- Keep golden workbooks outside the agent's filesystem and tool authority during a scored run.
- Use explicitly contaminated tasks only as development canaries, never as held-out results.
- Mount or copy only the input workbook into the agent runtime, then collect the output separately.
- Recalculate outputs with the official LibreOffice refresh script before evaluation.
- Run the official evaluator without modification and retain trajectories, outputs, and result JSON.

Maintain two scoreboards:

1. Competitive: strongest available model plus LibreCalc, maximizing full-benchmark accuracy.
2. Controlled: identical model, task set, call budget, and scaffold across thin, semantic, and semantic-plus-program interfaces.

## First isolated baseline

On 2026-08-25, Cursor with `cursor-grok-4.6-medium` completed the untouched
SpreadsheetBench 2 task `Template-02_02` inside the official benchmark container. Only the
task input, the LibreCalc source/tool bundle, and a private output directory were mounted;
golden data was not available until after scoring.

- Regression accuracy: `0.9838`
- Modification accuracy: `0.7534`
- Exact task accuracy: `0.0`
- Agent tool calls: `6`
- Model tokens: `39,720` input, `9,305` output, `129,024` cache-read

The dominant error was a financial-model sign convention: debt repayments needed to be
negative cash flows. Read-back enabled the agent to repair a row-alignment mistake, but the
tool surface gave it no semantic warning about the sign mismatch. The run also used 123
one-cell formula operations, motivating the tested `fill_formula` and `clear_range`
primitives. This task is now a development task, not a held-out task.

## Next experiment slice

1. Freeze the runner prompt and LibreCalc surface.
2. Select five untouched tasks spanning template completion, financial modeling, and debugging.
3. Run Grok 4.6 with the same isolation and retain every trajectory, output, and score.
4. Classify each miss as inspection, target selection, reasoning, execution, recalculation, or evaluation failure.
5. Add only primitives justified by repeated failures, with in-memory tests before UNO changes.
6. Re-run the frozen slice after each interface revision and record accuracy, calls, tokens, time, and recovery behavior.

The first slice is frozen in `benchmark/slices/grok-v1-five.json`. It includes two template
tasks, two cross-sheet financial-model tasks, and one structural debugging task. Template tasks
`01_01` and `02_05` are now development-only: `02_05` was officially scored and `01_01` had an
aborted over-budget trajectory. Their untouched replacements are frozen in
`benchmark/slices/grok-v2-five.json`.

The first OpenRouter credential supplied for the initial experiment returned HTTP 401 before any
model response. A replacement credential was validated on 2026-08-25 and OpenRouter is now usable
through the isolated SWE-agent harness. Credentials must remain ephemeral and outside repository
files, trajectories, and command-line arguments.

## Second isolated result and harness findings

On 2026-08-25, Cursor `composer-2.5` completed Template task `02_05` after the premium
model allowance was exhausted. This is a low-cost interface baseline, not a competitive model
result.

- Regression accuracy: `0.9586`
- Modification accuracy: `0.5000`
- Exact task accuracy: `0.0`
- Agent tool calls: `14`
- Model tokens: `39,893` input, `20,233` output, `431,200` cache-read

The run exposed two interface defects. Native Calc `fillAuto` silently no-op'd when the XLSX
source was mounted read-only, and parallel agent reads could deadlock independent UNO clients.
LibreCalc now translates relative A1 formulas deterministically and the benchmark adapter uses
an OS-level cross-process lock. Both fixes pass real-UNO and exact read-only-container probes.

The remaining scored error was model reasoning: the agent treated interest as a cash payment
ahead of principal, while the task's expected waterfall swept cash to principal and calculated
average-balance interest separately. A later `01_01` attempt was stopped after Composer ignored
the prompt-only call limit. The runner now monitors Cursor's event stream and interrupts the
container on the sixteenth total tool call, including calls across resumes.

Cursor reported that premium model usage is exhausted until 2026-09-11. Grok 4.6 sessions are
retained and resumable, but no further premium retries should run until capacity resets or the
user explicitly enables another paid route.

## First observation-format canary

On 2026-08-25, OpenRouter `google/gemini-3.7-flash` ran the contaminated development task
`Template:02_05` through SWE-agent. A first trajectory was invalidated and manually stopped after
the generic bash tool allowed out-of-interface `openpyxl` inspection. It cost `$0.017400824` and is
classified as a harness failure. The generic bash tool is now disabled structurally.

Two clean exploratory runs then held the model, task, execution primitives, response-token cap,
and call budget constant while varying only `calc_read` observations:

| Observation | Output | Charged cost | Prompt tokens | Completion tokens | Reasoning tokens | Executed tools |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `grid-v1` | none | `$0.015337800` | `20,959` | `4,348` | `3,950` | `7` |
| `sparse-addressed-v1` | none | `$0.017388375` | `16,819` | `5,910` | `5,690` | `4` |

Sparse addressed observations removed blank cells, attached an A1 address to each returned cell,
and omitted duplicate constant/formula representations. They reduced prompt tokens by about 20%,
but did not improve task completion and increased total cost because the model spent more output
tokens reasoning and hit the 1,024-token response ceiling more often. Both agents fixated on the
template's offset between year headers and populated time-series columns and repeatedly inspected
overlapping ranges without attempting a write.

This single paired canary does not select an observation model. It shows that coordinate encoding
alone is insufficient and motivates testing a genuinely structure-first overview. The response
token cap is also a material interaction variable and must be held fixed or explicitly varied in
future comparisons. Total charged OpenRouter usage for the invalid harness run and both clean
canaries was `$0.050126999`.

## Observation and model canaries after the sparse/grid pair

Further development-only runs on `Template:02_05` separated four concerns that the initial pair
had conflated: structural overview, semantic completeness, native tool transport, and model
reasoning policy.

| Model | Observation | Provider-billed cost | Result |
| --- | --- | ---: | --- |
| Gemini 3.7 Flash | `structure-first-v1` | `$0.005643000` | Resolved the header/data offset, then exhausted its response on reasoning before a write. |
| Kimi K2.7 Code | `structure-first-v1` | `$0.017460530` | Exhausted 4,096 output tokens debating task semantics; no write. |
| Kimi K2.5 | `semantic-snapshot-v1` | `$0.005343300` | Produced a program, exposing a native function-schema transport defect. |
| Kimi K2.5 | `semantic-snapshot-v1` | `$0.013692070` | Executed and verified a workbook; scored 145/145 regression and 19/40 modification cells, not exact. |
| Kimi K3 | `semantic-snapshot-v2` | `$0.037273440` | Used 2,038 reasoning tokens across two calls and made no edit. |
| Kimi K2.5 | `semantic-snapshot-v2` | `$0.008736060` | Sixth response contained an exact-scoring program, but the call-limit check prevented execution. Recovered output scored 145/145 and 40/40; diagnostic-only. |
| Kimi K2.5 | `semantic-snapshot-v2`, overview-only | `$0.005681840` | Inspected once and attempted a write on call two, but enumerated one-cell formulas until the 2,048-token response cap; no output. |

The transport defect is fixed: array-valued tool arguments remain arrays in the native function
schema and are serialized as URL-encoded JSON for the shell boundary. The contract was tested
through SWE-agent's actual function parser and against real LibreOffice execution/recalculation.

`semantic-snapshot-v1` adds address-keyed inputs plus live formulas and calculated values to the
structure-first overview. Its K2.5 output proved that this was enough for efficient execution but
not semantic correctness: the agent omitted the `D6:F6` beginning-cash carry-forward, so one miss
cascaded through the debt waterfall. `semantic-snapshot-v2` therefore makes likely structural
gaps first-class while labeling them as heuristics rather than requirements.

K3 saw those gaps, including `D6:F6`, but still spent its entire response resolving the cash-sweep
and interest-ordering ambiguity. A more expensive model did not compensate for an unconstrained
reasoning loop. This is evidence against selecting models by headline capability alone and in
favor of treating reasoning policy and response budget as controlled experimental variables.

The K2.5 v2 canary then isolated the observation change: with reasoning disabled, the model
explicitly added the missing cash and debt beginning-balance carry-forwards and produced an
officially exact workbook when its already-paid action was replayed. This is not a competitive
success because SWE-agent checked the six-call ceiling before executing the sixth action. It is
nevertheless strong diagnostic evidence that meaningful gaps in the overview fixed the prior
semantic failure.

That run also ignored the instruction not to reread complete sections and spent four calls on
information already present in the snapshot. The next observation ablation should therefore hold
the snapshot fixed and compare `progressive` access (focused reads remain available) with an
`overview-only` tool set. This tests whether optional detail helps hard cases enough to justify the
extra tool-selection burden and cost.

## Current observation philosophy

The observation interface should be a deterministic, progressively disclosed semantic snapshot:

1. Begin with exact structure, labels, regions, constants, formulas, and calculated values.
2. Preserve meaningful absence; do not let sparse serialization erase template gaps.
3. Keep facts and heuristics in separate, explicitly named fields.
4. Use focused addressed reads only when the overview leaves a real ambiguity.
5. Verify by regenerating the same snapshot after recalculation and comparing intended versus
   actual changes, rather than merely reading a few cells selected by the agent.

This does not yet select `semantic-snapshot-v2` as the final observation model. It selects the
properties to preserve while we ablate representation and verification. The next high-leverage
work is an overview-only/progressive disclosure comparison, deterministic post-execution
validation/semantic diff, and then a small controlled comparison of model reasoning modes. More
paid retries on the same canary are lower value until that loop is implemented.

## Offline harness checkpoint

The next harness layer was implemented without model calls:

- `progressive` and `overview-only` are explicit read policies recorded per run. Overview-only
  removes `calc_read` from the native function schema rather than relying on prompt compliance.
- `calc_compare` builds the same semantic snapshot for input and output and emits
  `semantic-diff-v1`. Exact label, constant-input, formula-expression, and calculated-value changes
  are separated from heuristic candidate-gap changes.
- The recovered exact `02_05` workbook produced a deterministic diff of 72 formulas added, zero
  labels or constant inputs changed, 19 candidate gaps resolved, zero new gaps, and three remaining
  header/note false positives clearly marked as non-failures.
- The runner stages a temporary overlay of SWE-agent 1.1.0 with the call-limit check moved before
  the next query. The last allowed paid response can therefore execute, while an additional paid
  request is prevented. The official benchmark checkout remains untouched.

The overview-only canary confirmed the intended tool-selection effect: K2.5 moved from four
redundant reads plus a sixth-call program to one inspect followed immediately by a program. That
reduced provider cost to `$0.005681840`, but the model expanded more than 70 one-cell
`set_formula` operations and its native argument was truncated at 2,048 completion tokens. The
partial program also subtracted operating cash requirements twice during repayment, a separate
reasoning error that must not be encoded as debt-waterfall knowledge inside LibreCalc.

The execution failure justifies a compact orthogonal primitive. `calc_fill_formulas` now accepts
formula blocks containing a sheet, range, and one top-left formula. It translates relative A1
references over each range using the already-tested `fill_formula` semantics, recalculates once,
and saves once. It passed both an in-memory backend test and a real-UNO range-translation probe.

`formula-blocks-v1` now keeps `calc_fill_formulas` as the only write tool while retaining inspect
and semantic compare. Malformed blocks are rejected before workbook execution. An offline replay
through SWE-agent's native function parser preserved array structure, spaces, ranges, and formulas;
the two-block probe encoded to a 293-character shell action. No further paid retry is warranted in
this implementation pass. The next canary can directly test the full inspect → compact fill →
semantic diff → submit loop.

## First exact isolated OpenRouter result

The resulting 2026-08-25 canary completed that full loop on development task `Template:02_05`.
Kimi K2.5 used exactly four model/tool turns: inspect, compact formula fill, semantic compare, and
submit. The fill call expressed 72 translated formulas as 19 patterned range blocks. The semantic
diff reported zero label or constant-input changes, all 19 real candidate gaps resolved, no new
gaps, and only the three known header/note false positives remaining.

After the official LibreOffice refresh, the unmodified SpreadsheetBench 2 evaluator reported:

- exact task success: `true` (`185/185` evaluated cells),
- regression preservation: `145/145`,
- required modifications: `40/40`,
- provider-billed cost: `$0.005702530`,
- model calls / executed tools: `4 / 4`,
- tokens: `10,646` prompt, `1,551` completion, `0` reasoning,
- elapsed time: `43.51s`.

This is the first competitively eligible exact result through the isolated OpenRouter harness. It
validates the end-to-end mechanics and the local hypothesis that a semantically complete overview
plus a compact orthogonal range primitive can turn a long cell-edit trace into a short, inspectable
program. It is not evidence of broad benchmark performance: `02_05` is now a contaminated
development task, and its solution is unusually well matched to formula-block execution.

Do not spend more money repeating `02_05`. The next paid evidence should come from one untouched
task in `grok-v2-five.json`, starting with `Template:01_02`, using the same K2.5 configuration as a
frozen transfer test. Classify any miss before changing the interface. In particular, do not
declare overview-only universally superior until tasks with genuine local ambiguity have tested
whether focused reads earn their extra cost. Formula blocks should remain the narrow write surface
for formula-completion tasks; other task families may justify different orthogonal primitives.

## First transfer and model-threshold probes

The frozen K2.5 configuration did not transfer exactly to untouched `Template:01_02`, a materially
harder OID bond-accounting task. It produced a workbook and repaired its first-period opening
balances on the fifth and final response, but the official evaluator reported only `235/280` cells:
`221/228` regression and `14/52` modification. The run cost `$0.008297370`.

Failure classification found both runtime and model defects. LibreOffice's UNO `Formula` property
accepted comma-separated `RATE` but silently changed comma-separated `IF` formulas into invalid
four-argument expressions during XLSX export. Formula function-argument separators are now
normalized deterministically outside quoted strings and array constants. The fix passes pure,
memory-backend, and real-UNO tests. Replaying the already-paid final action through the fixed
runtime improved the diagnostic score to `244/280`, with `226/228` regression and `18/52`
modification, but remained far from exact. The remaining misses were model reasoning: reversed
GAAP liability accretion and deferred-tax-asset signs, an incorrect tax-balance carry-forward, and
omitted retained-earnings opening balances. The original run is therefore ineligible as a clean
competitive result, while still proving that formula blocks transfer mechanically.

A later clean Grok 4.6 medium run through `formula-patterns-v1` and `formula-blocks-v1` improved
`Template:01_02` to `274/280` (`226/228` regression, `48/52` modification) for `$0.140878`.
Its six misses were a single maturity-year accounting-choice cluster, not an interface miss.

On untouched `Template:02_04`, the same configuration produced a workbook for `$0.086942` and
scored `118/130` (`93/93` regression, `25/37` modification). All 12 misses were exactly the same
4× interest-rate convention: Q1–Q4 columns led the model to divide the displayed rates by four,
while the golden applied them directly each quarter. Record this as task-convention ambiguity;
do not encode either convention in LibreCalc.

The next clean transfer, `Financial_Model:01_03`, produced a workbook with Grok 4.6 medium in 11
calls for `$0.538236`. Official value scoring was `2586/2843` (`2413/2425` regression,
`173/418` modification), but direct-formula analysis is more diagnostic: 35 of 40 requested
formulas match exactly. Five Capex formulas selected the wrong revenue source, and the model missed
an unstated 2025A Receivables prerequisite that feeds forecast Receivable Days. That upstream blank
caused a large value cascade. Existing `semantic-snapshot-v2` does not rank this edge gap.

This run also crossed an observation-cost threshold: formula-pattern inspect was 163,278 bytes and
semantic compare was 198,664 bytes because it included 1,797 downstream recalculation changes.
SWE-agent truncated compare at 100,000 characters, and total prompt usage reached 549,294 tokens.
Pause before the next paid task. Evaluate optional sheet-scoped inspection and bounded downstream
diff representatives, while retaining complete direct edits and error changes. Prototype any
dependency-gap signal offline and measure precision before adding it to the observation surface.

That observation experiment subsequently passed an apples-to-apples development rerun. Inspection
is now progressive: a 4,814-byte all-sheet manifest precedes detailed inspection of exact selected
sheet names. The four `01_03` target sheets produced 14,908 bytes rather than 163,278 bytes.
Semantic compare filters tight numerical no-ops, keeps complete direct edits and error transitions,
and bounds unchanged-formula recalculation evidence while retaining complete per-sheet counts and
affected ranges. The prior output's compare fell from 198,664 to 12,423 bytes and was no longer
truncated. Grok 4.6 medium completed the rerun in 10 calls for `$0.199046`, using 178,294 prompt
tokens rather than 549,294. Its resulting workbook has zero cell-content differences from the old
`$0.538236` output. Observation cost and truncation are therefore patched without a capability
regression; the upstream Receivables and Capex-source reasoning misses remain a separate problem.

Two controlled probes then held the exact-scoring `02_05` task and interface fixed:

| Model | Reasoning policy | Cost | Result |
| --- | --- | ---: | --- |
| Kimi K2.5 | none | `$0.005702530` | Exact `185/185`; inspect, fill, compare, submit in four calls. |
| Gemini 3.7 Flash | lowest supported (`low`) | `$0.004699500` | Inspected once, then used 1,968 reasoning tokens and hit the response cap without a write. |
| Gemini 2.5 Flash Lite | requested `none` | `$0.000856500` | Provider still used 1,962 reasoning tokens; model shortened the supplied input path, and the pre-fix runtime terminated on the nonexistent file. Invalid controlled run. |

The Flash Lite failure motivated fail-fast path validation before any UNO connection, so a wrong
agent target now returns a recoverable error instead of terminating the tool process. Total
reconciled OpenRouter experiment spend after these probes is `$0.163513139`.

This does not locate a scalar intelligence threshold. It does establish a behavioral boundary for
this bounded loop: K2.5 converts the semantic snapshot into an executable program with no hidden
reasoning, while both tested Gemini policies spend nearly the full response budget deliberating.
Model capability, mandated reasoning policy, tool-call reliability, and willingness to commit are
separate experimental variables. A weaker model can only be judged on a task where the stronger
anchor succeeds under the same clean runtime.

Formula calculation errors are now explicit in range reads, semantic snapshots, and semantic
diffs; `#VALUE!`, `#DIV/0!`, and related Calc results are no longer serialized as ambiguous null
values. The contract passes memory and real-UNO tests. Before another paid ladder, assemble a small
development difficulty set rather than drawing conclusions from one task. For each task, establish
an exact upper anchor first; only then descend through cheaper models. Untouched tasks remain
reserved for frozen transfer/competitive measurements, not repeated threshold tuning.

## Cost accounting rule

Provider-observed billing is the primary metric. The OpenRouter key-usage delta and per-generation
records are reconciled as `charged_cost_usd`; reasoning tokens are counted separately because they
are billed as completion tokens. SWE-agent's estimate uses worst-case catalog prices and is kept
as `budget_enforcement_cost_usd`, not reported as an actual charge. Cost per exact success is the
primary efficiency result; workbook creation and partial cell accuracy remain diagnostic metrics.

## Official public trajectory audit

The official `trajectory_example.zip` artifact was audited and its 15 non-visual Claude Opus 4.6
actions were replayed through the official image and evaluator. The public subset scored 7/15 exact:
4/5 Template, 3/5 Financial Model, and 0/5 Debugging. It used 290 API calls and reports $53.631540
of SWE-agent instance cost. The most informative shape is 99.23% mean Financial Model modification
accuracy despite two exact failures, versus only 30.89% mean Debugging modification accuracy.

The live official leaderboard currently places arito (45.46%) and WPS AI (42.27%) above the paper's
Claude Opus 4.6 SWE-agent result (34.89%); it does not list Opus 5. Full task-level results are not
public, but the example archive provides 160 complete trajectories across eight models and twenty
tasks.

The audit also found successful golden-workbook reads in five public model-task trajectories,
including three Opus trajectories. Therefore neither the public subset nor the published Opus row
should be assumed gold-blind. Our one-input/read-only isolation remains stricter and is required for
all competitive claims. The public non-visual examples are frozen as contaminated development suite
`benchmark/slices/public-example-nonvisual-v1.json`; detailed scores and evidence are in
`docs/public-trajectory-audit.md`.

A clean, gold-blind Opus 5 anchor attempt on `Template:06_01` reproduced the public Opus 4.6 score:
308/308 regression cells, 34/40 modification cells, and no exact success. The six misses are a
benchmark defect, not an agent failure: the golden workbook contains `=#REF!` in `IncomeStmt!E18:G18`
and `E19:G19`, while both agents generated correctly translated gross-profit and margin formulas.
The Opus 5 run used six calls, cost $0.383785, and completed in 89.16 seconds. Retain `06_01` as an
evaluator/golden-quality fixture, not a model-threshold task, and do not add behavior that reproduces
known-broken formulas.

The revised three-task difficulty ladder is `Template:01_01`, `Financial_Model:09_04`, and
`Debugging:10_02`. They are public development tasks whose Opus example trajectories did not read
golden files. `01_01` already has a clean exact public Opus anchor; establish clean exact upper-model
anchors for the other two before cheaper-model descent.

## `Template:01_01` threshold result

Fresh gold-blind runs separated protocol, deliberation, and domain-reasoning failures. Kimi K2.5
failed before mutation: progressive inspection led to parallel tool calls, while overview-only runs
used the full 4,096- and 8,192-token response budgets without acting. Their charged costs were
`$0.002156940`, `$0.010627630`, and `$0.019608570` respectively.

Opus 5 with high reasoning likewise exhausted a 4,096-token reasoning window; after the runner was
fixed to allow one bounded format repair, it exhausted two such windows. Those probes cost
`$0.134715000` and `$0.291160000`. Low reasoning plus one repair produced a workbook in five calls
for `$0.344300000`. The official evaluator scored it 380/381 regression cells and 72/87 modification
cells, not exact.

All 16 wrong cells arise from the same choice: carrying the tax-basis loan at `$25,000` face value
instead of the `$22,150` issue price and consequently failing to reverse the year-six DTA. The write,
recalculation, comparison, and submission path worked. Treat this as a target/domain-reasoning miss
with an inspection contribution: the 120-character semantic-label cap hid the end of the note that
explicitly mentions DTA reversal. The cap is now 240 characters, and SWE-agent gets one bounded
repair response by default. No further paid tuning on `01_01` is warranted before testing transfer.

The exact public Opus 4.6 trajectory used explicit post-write invariants that the fresh run omitted:
discount amortization totals `$2,850`, the DTA and cumulative deferred tax both end at zero, the GAAP
loan accretes to face value, and the tax balance sheet balances. This points toward deterministic,
agent-specified assertions as a possible verification primitive. It does not justify a domain-aware
bond checker; wait for a repeated need on another task.

Offline inspection of the public `Financial_Model:09_04` near-miss found exactly one error:
`Valuation!G59` remained blank instead of linking WACC with `=E48`. The semantic header is in `G58`
and the neighboring sensitivity values are in `H59:L59`, so the current same-row label-gap heuristic
cannot nominate it. A strict table-corner candidate signal found `G59`, but its full 15-task offline
score was only 1 true hit from 23 candidates (4.35% precision, 0.14% recall over 699 known blank
targets). This is too noisy and narrow for `semantic-snapshot-v2`; keep it as rejected evidence and
run the clean upper anchor with the current observation model. A future candidate ranker should
combine multiple contextual signals and report why each cell was nominated.

The first clean upper-anchor attempt then found a scale defect before model reasoning: the 2.58 MB
workbook made `semantic-snapshot-v2` reopen the file once per sheet and query errors cell by cell.
Inspection timed out at 60 seconds after one Opus 5 call (`$0.012135`, invalid). Batched backend
reads and formula-only error checks reduced a compact `structure-first-v1` inspection from 126.3 to
4.0 seconds. Full semantic v2 fell to 42.9 seconds but still emitted 5.77 MB, far beyond the 100 KB
harness observation window; structure-first emitted 49.8 KB and remained intact.

A structure-first retry showed that this overview was sufficient to localize PAT, the balance-sheet
check, Equity Turnover, WACC, and the sensitivity table. It nevertheless failed before mutation
because Opus repeatedly emitted two independent focused reads in parallel. Format-repair responses
drove eight calls to `$1.151565` and no workbook, making the run invalid as a capability score. This
trace justified `calc_read_ranges`: several addressed sheet/range requests now share one workbook
open and one native tool result. A real-UNO smoke test returned the three requested task regions in
1.79 seconds and 11.4 KB. The runner also reserves a conservatively priced full response before
each request so a nominal dollar cap cannot be crossed by the next provider call.

Do not spend further on Opus during interface development. Validate the batch-read loop with Kimi
K2.5/K2.7 or another cheap tool-capable model; use expensive upper anchors only after the cheap run
proves that transport, observation size, comparison timeout, and hard cost enforcement all work.

The cheap validation completed that tooling check. Kimi K2.7 Code used `calc_read_ranges` correctly
and identified PAT, the balance-sheet check, Equity Turnover, WACC, and the sensitivity table. At
low reasoning it spent `$0.079998630` across six responses; at minimal reasoning it spent
`$0.076508670` across seven. Both runs made four valid inspection calls, then repeatedly reached
`finish_reason=length` while debating the sensitivity calculation. Neither wrote a workbook.
Offline classification found its four ordinary formula plans correct or algebraically equivalent;
it missed the separate sensitivity-table anchor at `Valuation!G59` and never executed its direct
DCF-table plan.

Kimi K2.5 with reasoning disabled showed the complementary boundary. It made eight valid native
tool calls for `$0.044540800`, but all seven post-inspection calls were progressively broader
`calc_read_ranges` requests. Its 1,158 completion tokens were far below the configured 4,096-token
cap; the failure was over-inspection and the call ceiling, not response truncation. Together these
runs confirm that native tool schemas, required single-tool transport, batching, observation size,
timeouts, and accounting work. They do not establish a model success on `09_04`.

Small fixed response caps were confounding the K2.7 result, so they are no longer the runner
default. With no explicit `--max-tokens`, each request receives the largest allowance that fits the
remaining hard dollar and context budgets after a conservative prompt reserve. Explicit caps remain
available for controlled response-budget ablations. The next observation experiment should compare
progressive structure-first inspection with a compact formula-pattern overview: the former is now
proven fast but semantically thin for weaker models, while the current full semantic snapshot is
too large for this workbook.

A controlled Gemini 3.7 Flash rerun on development canary `Template:02_05` validated the automatic
allowance. Holding the model, semantic-v2 overview-only observation, formula-block execution, low
reasoning, call limit, and `$0.02` task cap fixed, Gemini consumed 4,201 tokens in its second
response—more than twice the former 2,048-token ceiling—and reached a write call. It then supplied
two empty formula-block objects. The run cost `$0.008901750` and produced no workbook. This confirms
that the fixed cap had been mechanically binding, but removing it did not cross the model's action-
construction threshold.

The malformed call exposed a separate feedback-loop defect: a nonzero Calc wrapper status caused
SWE-ReX's persistent shell to exit after the tool had emitted a useful structured validation error.
All benchmark wrappers now preserve that JSON error observation while normalizing the wrapper status,
so a later model response can repair invalid arguments. This is harness recovery behavior, not a
spreadsheet primitive or an embedded planner.

## Compact formula observations and first debugging attention model

`formula-patterns-v1` compressed `Financial_Model:09_04` to exact horizontal translated formula
runs. With Kimi K2.7 Code, low reasoning, progressive reads, dynamic response allowance, and a
`$0.10` ceiling, it produced a workbook in four model calls for `$0.068615`. The official evaluator
reported regression `1.0` and modification `0.9981`; the only miss was the previously known
`Valuation!G59` WACC anchor. This is the strongest evidence so far that observation quality, not
just raw model intelligence, controls the action threshold.

The next ladder task, `Debugging:10_02`, has 99 populated sheets. Formula patterns emitted 739 KB,
so a task-specific attention *mechanism* was required, not a task-specific fix. The initial
`formula-anomalies-v1` combined translated-formula consensus with short formula-shape gaps. It
contained all nine genuine hardcode repairs in 39 KB, but its shortlist also contained intentional
forecast assumptions and literal `=#REF!` artifacts. K2.7 correctly named the nine repairs, then
overgeneralized and spent four reads investigating false candidates; it stopped at `$0.061632`
without producing a workbook.

That failure justified a precision refinement. The backend now supports compact selected-cell
format fingerprints, with an in-memory test before the UNO implementation. The observation uses
those fingerprints plus structural evidence to deprioritize conventional blue inputs, unfilled
historical constants, unbracketed trailing assumption blocks, literal error formulas, and sheets
where nearly every numeric constant is nominated. On the real workbook the final view is 21,243
bytes, omits saturated `4-Wall Analysis`, and selects exactly the nine known repairs (seven inferred
translation candidates plus two additional SOFR sequence gaps) with no false selected cell in this
contaminated development task. Unit tests, the full suite (`52 passed, 3 skipped`), and Ruff are
clean. The first refined paid run (`…-auto-low-2`) still produced no workbook: six progressive
reads, `$0.082875`, then the `$0.10` remaining-budget gate. Raising the cap to `$2` without a
model output ceiling requested ~588k `max_tokens` and OpenRouter rejected it. After capping
automatic output at 8,192 tokens and prompting at most one shortlist confirmation, K2.7 wrote
in five calls for `$0.054597`. Official formula-mode scoring: regression `1.0`, modification
`41/47` (`0.8723`). Every genuine hardcode-to-formula repair matches the golden. The six
misses are `P&L Summary!B48:B50` and `E48:E50` (`OpEx` vs `(-) OpEx`, same for Occupancy and
Administrative). Thirty-three other scored modification cells are `#REF!` strings that Calc
saved as `=#REF!`, matching the golden without agent intent. Do not encode the `(-)` label
prefix. Frozen fill-only transfers: `05_03` and `08_03` produced no workbook (repeated deleted-row
`#REF!` diagnosis); `07_01` scored modification `85/86`; `04_06` inspect-spiraled with no write.
Geometry is now in the algebra (`insert_row` / `delete_row` behind `CalcBackend`). That is not a
task heuristic. Flexibility stays in programs; overlays stay measurement instruments. Next probe:
`08_03` with unfrozen `calc_program`.

## Kimi K2.7 Code cheap compiler lane (frozen)

OpenRouter `moonshotai/kimi-k2.7-code` is the default cheap compiler for non-visual work.
GLM 5.3 is retired from this lane. Visualization still uses the same OpenRouter account for
VLM scoring via `z-ai/glm-4.6v`. Park Grok for a later competitive threshold; do not mix
harness numbers.

| Setting | Value |
|---|---|
| Template / FM observation | `formula-patterns-v1` |
| Debugging observation | `formula-anomalies-v1` (+ read-budget instrument) |
| Execution | `formula-blocks-v1` |
| Read policy | `progressive` |
| Reasoning | `--reasoning-effort low` |
| Budget | `$2` / 12 calls / `--timeout 1200` |

Next held-out: [`kimi-v1-five.json`](../benchmark/slices/kimi-v1-five.json). GLM slices
[`glm-v4-five.json`](../benchmark/slices/glm-v4-five.json) and
[`glm-v5-five.json`](../benchmark/slices/glm-v5-five.json) are exhausted **GLM** history.

### GLM 5.3 history (retired lane)

Write-gates passed on burned v3 tasks: `Template:05_01` (submitted, not exact) and
`Financial_Model:05_01` (workbook produced; regression clamped `1.0`, modification `0.999`).
Held-out slices [`glm-v4-five.json`](../benchmark/slices/glm-v4-five.json) and
[`glm-v5-five.json`](../benchmark/slices/glm-v5-five.json) are **exhausted**.

### Held-out results (v4 + v5, 10 tasks)

| Run | Tasks | Workbooks | Charged | Official exact |
|---|---:|---:|---:|---:|
| `glm-5.3-v4-five-high-1` | 5 | 5 | `$0.359` | 2/5 |
| `glm-5.3-v5-five-high-1` | 5 | 5 | `$0.213` | 0/5 |
| **Combined** | 10 | 10 | **~$0.57** | **2/10** |

**v4 exact:** `Financial_Model:01_04`, `Financial_Model:02_04`. **v4 caveats:** `Template:01_04`
official score invalidated by a harness output-discovery bug (category-id collision with
`Financial_Model:01_04`) — fixed in `run_openrouter_slice._find_output`. **v5 pattern:** all
`reg 1.0`; modification misses only; Debugging `04_02` missed chart target (`mod 0.0`).

Score a run locally:

```bash
uv pip install openpyxl tqdm
uv run python benchmark/score_openrouter_run.py \
  benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/glm-5.3-v5-five-high-1
```

Optional `--write-ledger` appends rows with `exact_success`.

### Visualization lane (started)

Chart domain ops (`upsert_chart`, `delete_chart`) were already in the algebra; agent-facing
wrappers landed:

- `calc_inspect_charts` / `calc_upsert_chart`
- [`spreadsheet-viz.yaml`](../benchmark/sweagent/spreadsheet-viz.yaml)
- Dev canary `viz-dev-line-one`; ladder [`viz-ladder-five.json`](../benchmark/slices/viz-ladder-five.json)

**Native LibreOffice PNG export works** via `com.sun.star.drawing.GraphicExportFilter`
(`MediaType=image/png`) on draw-page chart shapes — not a Windows-only path. Script:
[`benchmark/export_charts_png.py`](../benchmark/export_charts_png.py) (needs UNO on
`localhost:2021`). Score PNGs with OpenRouter [`z-ai/glm-4.6v`](https://openrouter.ai/z-ai/glm-4.6v)
via [`benchmark/score_visualization_openrouter.py`](../benchmark/score_visualization_openrouter.py).
Excel COM remains the official-fidelity alternative; LO PNGs are the Linux development bridge
(expect some visual translation loss vs Excel).

```bash
uv run python benchmark/run_openrouter_slice.py \
  --slice benchmark/slices/viz-dev-line-one.json \
  --run-name glm-5.3-viz-dev-line-one-high-1 \
  --config benchmark/sweagent/spreadsheet-viz.yaml \
  --model z-ai/glm-5.3 \
  --observation grid-v1 \
  --execution semantic-program-v1 \
  --read-policy progressive \
  --cost-limit 2.00 --call-limit 12 --max-requeries 2 \
  --reasoning-effort high --timeout 1200
```

**Harness note:** `.env` at repo root supplies `OPENROUTER_API_KEY` (gitignored). GLM requires
`tool_choice=auto`; enforced in `benchmark/run_openrouter_slice.py`.


## Interface ablation — first result (canary)

The comparison PROJECT_CONTEXT section 28 calls the reason to build this had never been run.
One task, three arms, identical model (`z-ai/glm-5.3`, high reasoning), identical `$0.50` cap and
40-call ceiling. `Template:02_05` is burned development data; that is deliberate and does not
invalidate the experiment, because contamination is symmetric across arms. Arm C reproduced the
known K2.5 anchor on this task, so the harness is validated.

| arm | observation / write surface | exact | reg | mod | charged | calls | prompt tok | sec |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A thin | `grid-v1`, `calc_write` only, no batched reads, no compare | no | 0.6414 | 0.0000 | `$0.0771` | 8 | 32,564 | 352 |
| B semantic | `formula-patterns-v1` + `calc_read_ranges` + `calc_compare`, `calc_write` only | no | 1.0000 | 0.8500 | `$0.0630` | 14 | 83,539 | 621 |
| C semantic+program | same observation, `calc_fill_formulas` | **yes** | 1.0000 | 1.0000 | **`$0.0306`** | 7 | 28,111 | 144 |

Monotone in exactness, cost, and time. The two deltas do different work:

**A to B — the read side prevents damage.** Arm A issued one dense `calc_write` over `B5:E35`, a
31x4 rectangle. A rectangular write forces the agent to restate cells it does not intend to change,
so a single row offset put `450` into the label `Cash Available for Debt Repayment`; regression fell
to 0.6414, meaning the run was net-negative on cells that were already correct. Arm B targeted five
precise blocks in columns C:F and never touched the label column. That targeting happened at step 5,
before its first `calc_compare`, so it is attributable to the observation and not to verification.
Verification then did separate work: compare at step 10 triggered a re-read and a repair write.
Arm A read its own output back twice and still submitted the damage, because it had no semantic
diff to tell it a label had changed.

**B to C — program execution buys efficiency and completeness.** Same observation, same targets.
The thin write surface cost five writes plus a repair; `calc_fill_formulas` expressed the same edit
in one call. Calls 14 to 7, cost 2.1x, wall time 4.3x, and the residual 15% of modification cells
closed.

The cost mechanism is generation, not round trips. Arm A used *fewer* calls than B and *smaller*
observations than C (7,605 vs 10,613 chars of total observation), but 13,810 completion tokens
against C's 3,211, because the write action had to enumerate 124 cells. Completion tokens bill at
roughly 3x prompt tokens. This predicts the gap widens with task size; `ablation-three` tests that
on `Financial_Model:09_04`.

This aligns with the published failure taxonomy for Opus 4.6 on this benchmark (arXiv 2606.29955):
insufficient inspection ~35% and wrong target selection ~28% — the A-to-B delta — plus turn limit
exceeded ~15%, the B-to-C delta.

Caveat: one task, one model, one seed. Do not quote these as benchmark performance. Extend with
`ablation-three` before drawing a general conclusion.

## Rejected: dependency root-error ranking

Prototyped and characterised offline, then rejected as an automatic selector — the same
outcome, and the same protocol, as the `Financial_Model:09_04` table-corner signal.

The idea: `observation.py` already builds a full bidirectional dependency graph
(`direct_dependencies` / `reverse_dependencies`) to compute blank-dependency bridges, then
discards it. Calculated errors propagate along that graph, so an error cell is either a
*root* (no erroring precedent) or *inherited*. Ranking roots by blast radius should beat
ranking error cells by repeated formula shape, which is what `formula-anomalies-v1` ships.

Characterised over all 100 Debugging tasks with
[`benchmark/characterize_dependency_signal.py`](../benchmark/characterize_dependency_signal.py).
Ground truth is the official evaluator's own `classify_cells_by_modification` restricted to
each task's `answer_position`, not a reimplementation — two earlier hand-rolled definitions
were both wrong (openpyxl `ArrayFormula` compares by identity, so every array cell looked
modified: 30,868 false positives on `10_02` against a true set of 47; and diffing outside the
scored ranges gave 11,966). Validated by reproducing the documented 47-cell modification set
for `Debugging:10_02`.

| | root ranking | shipped shape ranking |
|---|---:|---:|
| mean precision@20 | 0.321 | 0.314 |
| mean delta | **+0.007** | |
| better / tied / worse | 6 / 31 / 9 | |
| signal silent | 54 of 100 tasks | |

More tasks are made worse than better. Conditional slices are positive but thin: Errors class
only `+0.075` (n=10), tasks where over half the errors are inherited `+0.067` (n=21). It does
win clearly on a few — `08_03` `0.95` vs `0.70`, `05_03` `0.65` vs `0.30`, `06_03` `0.85` vs
`0.55` — but a mean gain of `+0.007` across the category does not justify a new ranked signal.

**Do not ship root-error ranking.** Keep the finding, keep the tool, and keep the graph: the
rejection is of one heuristic over the dependency structure, not of the structure itself.

## Rejected: blank-candidate ranking / labelled block-hole shortlists

Characterised offline over all 100 Financial Model tasks with
[`benchmark/characterize_blank_ranking.py`](../benchmark/characterize_blank_ranking.py).
Candidate generation is gold-blind (input workbook + instruction). Ground truth is cache-robust
direct blank modification targets from the official evaluator.

The hope was a small labelled list (block-hole + adjacent label, scoped to instruction-named
sheets) that keeps `Valuation!G59` while staying cheap. That arm's pool is small (2,160
candidates, ~22/task) and does keep G59 on `09_04`, but category recall is **0.4%** at **2.4%**
precision (a hit on 26/100 tasks). Additive top-20 ranking reaches 32% precision only by
selecting easy clustered blanks; it **drops G59 and G4**. Broad demand still sits on the
precision wall (~9% target share, 60% recall).

There is still no single absence signal. Completeness and a small pool do not co-exist in the
world. Do not ship a labelled absence shortlist. Keep `blank_dependency_bridges` bounded and
measure its distraction cost with a same-model A/B before changing the default observation.

The remaining read-side question is narrower: the shipped carry-chain bridge already nominates
`Working Capital Schedule!G4` and is silent on `Valuation!G59`. Ranking and labelled block-hole
lists cannot close that gap without a payload of mostly noise. Keep the bridge bounded; decide
whether it stays in the default observation with a same-model A/B, not by adding more absence
detectors.

## Integrity gate and comparison freeze

The resource autopsy is authoritative. The current readiness result is recorded
by the offline `benchmark/integrity_gate.py` artifact. The old LibreCalc harness
is not the control for current-architecture claims. The external reference is
the published SpreadsheetBench 2 standard agent scaffold and official evaluator.

Report separately:

- system benchmark claim: compiled architecture official score versus the
  published standard-scaffold score;
- causal scaffold claim: matched backbone/settings comparison only, never an
  inference from another model's public result.

Do not rerun the published control to recreate a published number. No FM20,
model swap, matched control, or new frontend IR is allowed before the next
resource-envelope/compact-evidence phase.
