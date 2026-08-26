# Benchmark harness

`run_cursor_slice.py` and `run_openrouter_slice.py` execute frozen SpreadsheetBench 2 slices in
the official isolated container. OpenRouter runs use the vendored SWE-agent environment and keep
the API key on the host; it is not placed in commands, repository files, trajectories, or the task
container.

The current controlled dimensions are:

- observation: `grid-v1`, `sparse-addressed-v1`, `structure-first-v1`,
  `formula-patterns-v1`, `formula-anomalies-v1`, `semantic-snapshot-v1`, or
  `semantic-snapshot-v2`;
- read policy: `progressive` or `overview-only`;
- execution: `semantic-program-v1` or formula-only `formula-blocks-v1`;
- model, reasoning effort, per-task dollar limit, model-call limit, and response-token limit.

OpenRouter runs perform a live model preflight before spending money. The selected model must
exist and support native tools plus `max_tokens`; its current catalog prices and reasoning
capabilities are recorded in the ledger. The harness receives worst-case catalog pricing for
budget enforcement. `--max-tokens` is optional and is intended for controlled ablations. Without
it, the harness recalculates the largest response allowance that fits the remaining dollar and
context budgets before each request. For a model whose live catalog completion price is zero, the
runner omits `max_tokens` entirely and leaves response sizing to the provider/context policy.

The runner records a separate per-tool `--execution-timeout` (180 seconds by default). Large
workbook semantic comparisons can legitimately exceed SWE-agent's original 60-second command
limit; the overall task timeout remains independently bounded by `--timeout`.

`--call-limit` is a paid-response ceiling. The runner stages a temporary SWE-agent package overlay
that checks the ceiling before another query, allowing an action from the last paid response to
execute without permitting an extra charge. `--max-requeries` defaults to `2`: SWE-agent counts the
initial attempt, so this permits one bounded repair response after a malformed/no-tool result. Both
attempts still count against the call and dollar limits. The official SpreadsheetBench/SWE-agent
checkout is not modified.

Because every turn in this harness must execute exactly one tool, OpenRouter requests set
`tool_choice` to `required`. Models that advertise `parallel_tool_calls` also receive
`parallel_tool_calls: false`; independent focused reads should use `calc_read_ranges` instead.

The dollar limit is also guarded before each request. The runner reserves a 50% margin over the
locally counted prompt tokens at worst-case catalog prices, then gives the response the remaining
safe allowance. An explicitly configured `--max-tokens` cap replaces that automatic allowance.
Either policy prevents the provider charge from overshooting the advertised task cap.

`calc_compare` regenerates semantic snapshots for the isolated input and output, then reports exact
label/input/formula changes and calculated-value changes. Candidate gaps are reported in a
separate heuristic section. Under `overview-only`, `calc_read` is removed from the native tool
schema; under `progressive`, it remains available for focused ambiguity resolution.
Semantic snapshots retain up to 240 characters per label/note so short explanatory notes are not
silently reduced to misleading fragments.

`calc_fill_formulas` is the compact formula-only execution path. Each block supplies a sheet,
range, and top-left formula; LibreCalc deterministically translates relative references across and
down the range, executes all blocks, recalculates once, and saves once. This avoids verbose
one-cell formula programs while retaining inspectable spreadsheet semantics.

`calc_read_ranges` is the matching compact inspection path: it accepts several independent
sheet/range requests, opens the workbook once, and returns each result with explicit addresses.
Use it instead of parallel native tool calls when a task needs multiple focused regions. The
96-cell neighborhood limit is checked per item: an oversize item returns its own structured error
without discarding valid sibling reads.

`formula-patterns-v1` is the compact middle observation between structure-only and full semantic
snapshots. It retains the structure view and adds only exact horizontal autofill runs spanning at
least four cells, with the top-left formula/value and explicit covered/unrepresented counts. Short
or irregular formulas remain available through progressive focused reads.

`formula-anomalies-v1` is a debugging-oriented attention view. It ranks numeric constants only
when two or more nearby formulas independently translate to the same inferred formula, and reports
short numeric gaps bracketed by a repeated formula shape. It reads compact formatting fingerprints
for shortlisted cells, deprioritizes conventional blue inputs, unfilled historical constants,
unbracketed trailing assumption blocks, literal error formulas, and sheets where the signal is
saturated. Every item remains an explicitly heuristic candidate that should be confirmed once with a small
neighborhood read before a write; the view never auto-edits a workbook. Progressive
`formula-anomalies-v1` runs also rewrite the prompt so the model gets at most one confirmation
pass, then `calc_fill_formulas`, instead of expanding into whole-sheet reads.

Calc command wrappers keep the persistent agent shell alive when an operation is rejected. The
underlying tool emits a structured JSON error, while the wrapper normalizes its process status so
SWE-ReX can return that error as the next observation and the model can repair its arguments.

`formula-anomalies-v1` runs enable a run-scoped read budget by default: after `calc_inspect`, at most
one successful `calc_read` / `calc_read_ranges` batch; further reads return a structured write-now
error. Disable with `--no-read-budget` / `LIBRECALC_READ_BUDGET_ENABLED=0`. Measuring instrument, not
a product primitive. State file: `/mnt/spreadsheet_output/.librecalc_read_budget.json`.

## Kimi K2.7 Code lane (frozen cheap compiler)

OpenRouter `moonshotai/kimi-k2.7-code`. Frozen overlays: `formula-patterns-v1` +
`formula-blocks-v1` for Template/FM; `formula-anomalies-v1` + blocks for Debugging.
Held-out slice: [`benchmark/slices/kimi-v1-five.json`](slices/kimi-v1-five.json).
Confirmation: [`kimi-v2-fifteen.json`](slices/kimi-v2-fifteen.json). Full non-visual:
[`kimi-nonvisual-all.json`](slices/kimi-nonvisual-all.json) (297 tasks). Mixed-category
slices must go through [`benchmark/run_kimi_frozen.py`](run_kimi_frozen.py) so Debugging
gets `formula-anomalies-v1`. Use `--skip-existing` to resume. GLM 5.3 is retired from this lane.

Publish **non-visual subset only** (~297 Template+FM+Debugging tasks). Visualization (24 tasks) stays
out of scope until chart UNO→Excel translation is measured. Do not quote a full-bench exact rate
from development or burned slices.

Supply the credential through `.env` at the repo root (see `.env.example`) or export it
ephemerally for the run:

```bash
# .env is loaded automatically by run_openrouter_slice.py
benchmark/run_openrouter_slice.py \
  --slice benchmark/slices/grok-v2-five.json \
  --run-name example-grid-v1 \
  --observation semantic-snapshot-v2 \
  --read-policy overview-only \
  --execution formula-blocks-v1
```

Official-score completed runs:

```bash
uv run python benchmark/score_openrouter_run.py \
  benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/REPLACE-RUN-NAME
```

Results are written below the ignored `benchmark-data/SpreadsheetBench-2/benchmark-runs/` tree.
Each run has an append-only `ledger.jsonl`. The primary cost field is actual OpenRouter charged
usage, reconciled from the key-usage delta and per-generation usage records. A separate
`budget_enforcement_cost_usd` may be higher because it includes SWE-agent's conservative
worst-case estimate. Prompt, completion, and reasoning tokens are recorded separately. Summarize
a ledger with:

```bash
benchmark/summarize_experiment.py path/to/ledger.jsonl
```

`cost_per_success_usd` remains null until official evaluation populates `exact_success`; producing
a workbook is not treated as benchmark success.

`slices/public-example-nonvisual-v1.json` is a separate, explicitly contaminated development suite
matching the official public trajectory examples. It is useful for task-level comparison against
published frontier traces, but it must never be used for a held-out claim. See
`docs/public-trajectory-audit.md` for the replayed Opus 4.6 scores and benchmark-isolation caveat.
