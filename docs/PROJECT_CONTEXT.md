# LibreCalc MCP — Project Context and Continuation Guide

> **Purpose:** This is the canonical context document for continuing the project in a new chat, coding-agent session, or after a long break. Read this before proposing architecture changes.
>
> The project is intentionally narrow in v1. The larger ideas matter because they explain *why* the architecture is shaped this way, but they are not permission to expand scope prematurely.

---

## 0. Current handoff — 2026-08-25 (Codex)

This section is the operator brief. Read `AGENTS.md` next. Sections below this are background;
if they conflict with §0, §0 wins.

**Mismatch census (2026-08-26).** The evaluator's first-error inventory cannot support a
percentage claim about all wrong cells. `benchmark/mismatch_census.py` now replays official
cell comparisons over every scored range, then classifies each mismatch on the audited
direct/downstream axis. Across 24 valid stored OpenRouter attempts (6 official exact; the
contaminated `glm-5.3-v4-five-high-1` / `Template:01_04` copy excluded): **345** mismatch
occurrences, **0/24** score-replay disagreements.

Causal mix of those 345 cells:

| class | n | share |
|---|---:|---:|
| downstream cascade at unchanged formula | 117 | 33.9% |
| direct blank target: wrong edit | 94 | 27.2% |
| regression cell over-edited | 79 | 22.9% |
| direct blank target: unchanged | 20 | 5.8% |
| direct populated target: unchanged | 19 | 5.5% |
| dynamic-only regression cell over-edited | 16 | 4.6% |

Never-filled blanks are a real class and include the known `Valuation!G59` miss on all three
`09_04` ablation outputs plus `Working Capital Schedule!M3` on v5 `01_02`. They are **not**
the bulk of stored misses. Absence detection can address only the 5.8% never-filled slice;
wrong writes on blank targets are ~5× larger. Do not treat the 70.6% “direct FM targets are
blank” gold-side figure as the miss mix.

**Blank-candidate ranking is rejected as an automatic observation (2026-08-26).**
`benchmark/characterize_blank_ranking.py` scored gold-blind shortlists against cache-robust
direct blank targets on all 100 Financial Model tasks (11,771 blank targets). No arm clears
the shipping bar (much smaller pool without destroying recall):

| arm | pool | precision | recall | tasks with a hit |
|---|---:|---:|---:|---:|
| named-block-label | 2,160 | 2.4% | 0.4% | 26/100 |
| block-peer+label | 6,148 | 0.9% | 0.5% | 28/100 |
| named-rank-top-20 | 2,000 | 32.0% | 5.4% | 83/100 |
| referenced+peer | 72,077 | 9.4% | 57.9% | 99/100 |
| named-any-peer | 419,715 | 2.1% | 74.9% | 100/100 |

`Valuation!G59` survives named-block-label on `09_04` and is **dropped** by both top-20 rankers.
`Working Capital Schedule!G4` is only in named-any-peer / referenced, never in the labelled
block-hole list. Ranking raises precision by concentrating on easy clustered blanks; it does
not surface the one-cell misses. Do not ship a labelled absence shortlist. Keep the carry-chain
bridge bounded. Next experiment is a same-model A/B with vs without that shipped bridge:
`LIBRECALC_BLANK_BRIDGES=0` / `--no-blank-bridges`, slice `benchmark/slices/bridge-ab-two.json`
(`01_03` where G4 is rank-1, `09_04` where bridges fire but G59 is not among them). GLM 5.3.

**Bridge A/B result (GLM 5.3, one seed, 2026-08-26).** Both arms wrote workbooks. Official scores:

| arm | 01_03 | 09_04 | cost |
|---|---|---|---:|
| on (`…-high-2`) | reg 1.0 / mod **0.5909** | reg 1.0 / mod 0.9981, first miss `Valuation!G59` | $0.323 |
| off (`…-high-2`) | reg 1.0 / mod **0.1579** | reg 1.0 / mod 0.9981, first miss `Valuation!G59` | $0.132 |

`Working Capital Schedule!G4` and `Valuation!G59` stayed blank on **both** arms. The 09_04
near-miss is identical with or without the signal. The 01_03 modification gap is other work,
not G4, and is one seed — do not treat it as proof the bridge helps. Keep the shipped bridge
bounded and on; do not expand absence detectors off this A/B.

**Debugging read-budget A/B result (GLM 5.3, one seed, 2026-08-26).** Slice
`debug-read-ab-two.json` (`06_01` Double Counting, `09_06` Incorrect Cross Sheet References).
Success was workbook produced. **0/4 workbooks.**

| arm | 06_01 | 09_06 | cost |
|---|---|---|---:|
| on (`…-high-1`) | no workbook, 6 calls; gate fired after one successful read | no workbook, 10 calls; gate fired | $0.248 |
| off (`…-high-1`) | no workbook, 12/12 calls, inspect then 11 reads | no workbook, 6 calls | $0.265 |

The write-now error did fire on both on-arm tasks. The compiler then format/blocklist-errored and
autosubmitted instead of calling `calc_fill_formulas`. Off-arm `06_01` is the inspect-forever
control (call cap, still no write). Do not raise `--call-limit` or `--max-tokens`. Do not mint a
write tool. Keep the read budget a measuring instrument, default on for `formula-anomalies-v1`;
it does not convert GLM confirm-then-write misses into workbooks. Do not rerun `08_03` or this
slice. Do not change default observation off this A/B.

**Leave `Debugging:08_03`.** Bounded reads, inspect-error representatives, and capped neighboring
context are in the world and work. The inspect-dense canary still produced no workbook: K2.7
immediately returned to whole-region dumps, shrank one rejected range at a time for all eleven
post-inspect calls, and never called `insert_row` / `calc_program`. Do not rerun `08_03` on another
nearby overlay. Do not raise `--call-limit` or `--max-tokens` as the fix. Do not mint a
restore-UFCF / restore-row tool.

**Held-out threshold established on `Template:01_02`.** K2.7 produced no workbook for `$0.059763`:
after one useful read it spent two full 8192-token responses reasoning without a tool call. The
same frozen formula-pattern / formula-block interface with Grok 4.6 medium produced a workbook in
11 calls for `$0.140878`. Official scoring was `274/280`: regression `226/228`, modification
`48/52`. All six misses are one maturity-year accounting-choice cluster (cash tax / DTA reversal
plus an invented debt-extinguishment loss), not an inspection or execution miss. `01_02` is now
development data. Do not tune the world to those cells.

**Spark 1.2 Contributor passed the `01_02` write gate at ~26× lower $ than Grok.** Same frozen
interface, `tool_choice=auto` (Meta rejects `required` on both Spark slugs). `$0.005452`, 12
calls, 11 tools, workbook produced. Official value-mode after refresh: `260/280`, regression
`220/228` (`0.9649`), modification `40/52` (`0.7692`), not exact. First miss `OID_Bond!C24` is
inside the existing development accounting-choice cluster. Do not rerun `01_02` to chase it.
Contributor prompts may be used to train Meta models. Standard Spark hit the same `tool_choice`
reject (`$0.000014`) before this patch.

**`Template:02_04` produced a clean workbook but exposed an evaluation-convention ambiguity.**
Grok 4.6 medium completed it in 10 calls for `$0.086942`; official score `118/130`, regression
`93/93`, modification `25/37`. Spark 1.2 Contributor transferred the same frozen interface in 8
calls for `$0.002478` (submitted, not autosubmit) and scored **the same** `118/130` / `93/93` /
`25/37`. First miss `DebtWaterfall!B13` is `210.8` vs `52.7` (exactly 4×). The only 12 misses are
the four quarterly senior-interest cells, four mezzanine-interest cells, and their four totals.
The sheet labels columns Q1–Q4 and inputs only as `Interest Rate`; both compilers divided 6.2% /
9.5% by four as annual rates, while the golden applies them directly every quarter. Treat as
ambiguous task convention, not a world/ISA miss or a Spark-vs-Grok gap. Do not encode either
rate convention. Do not rerun `02_04`.

**`Financial_Model:01_03` exposed an observation-cost problem; the bounded redesign is now
validated.**
Grok 4.6 medium produced a workbook in 11 calls for `$0.538236`. Official score was `2586/2843`:
regression `2413/2425`, modification `173/418`. That value-mode headline is cascade-amplified:
35 of the 40 directly requested formulas match the golden exactly. The five Capex formulas use
`Consolidated P&L` revenue where the golden uses a `Revenue Drivers` total. A second miss is an
unstated prerequisite: the golden also restores 2025A Receivables at `Working Capital Schedule!G4`;
without it, the otherwise exact H4:L4 formulas inherit zero Receivable Days and cascade widely.
The model saw G4 blank and G6/H6 at zero in focused reads but did not infer the upstream restore.
Neither `formula-patterns-v1` nor a local `semantic-snapshot-v2` inspection ranks this edge gap.

The run also measured an observation-cost problem rather than a call-limit problem. Initial
formula-pattern inspect was 163,278 bytes across 25 sheets. `calc_compare` emitted 198,664 bytes,
including all 1,797 downstream recalculation changes, and SWE-agent truncated it to its 100,000
character view. Total prompt usage reached 549,294 tokens. Before `Financial_Model:02_02`, decide
how to bound/select observations; do not merely buy a larger context or remove verification.

The 2026-08-25 development rerun settled that choice. `calc_inspect` now returns a 4,814-byte
all-sheet manifest first and accepts exact sheet names for detailed structure/formula patterns.
On `01_03`, the four requested sheets produced 14,908 bytes instead of the former 163,278-byte
whole-workbook detail. Semantic compare now filters tight numeric no-ops, preserves complete direct
label/input/formula and formula-error changes, and reports complete per-sheet downstream counts and
affected ranges with at most eight spatial representatives per sheet / 80 globally. The same output
that formerly yielded 198,664 bytes and 1,797 raw downstream inequalities now yields 12,423 bytes,
402 meaningful downstream changes, and 69 representatives; it is not truncated.

The gold-blind Grok 4.6 medium rerun completed in 10 calls for `$0.199046`, with 178,294 provider
prompt tokens versus 549,294 (68% lower). Its workbook has **zero cell-content differences** from
the previous `$0.538236` output, so capability was preserved exactly while cost fell 63%. This does
not fix the separate reasoning miss: the historical Receivables prerequisite and Capex source choice
remain. Do not rerun `01_03` to re-prove the observation bound.

**Blank-dependency-bridge signal (2026-08-25, unfinished Codex work completed offline).**
Generic “blank cells referenced by formulas” is unusable (333 candidates on `01_03`). Requiring
that a dependent formula start a horizontal carry-forward of **at least two steps** is sparse and
hits the known edge:

| Workbook | Bridges | Notes |
|---|---:|---|
| `Financial_Model:01_03` (requested sheets) | 1 | Rank 1 is `Working Capital Schedule!G4` → `G6:L6` (carry 5), labels Receivable / Receivable Days. 925 bytes before the one-step filter; G4 remains after it. |
| `Template:01_02`, `02_04` | 0 | |
| `Financial_Model:02_02` (all 9 sheets) | 0 | Untouched canary will **not** exercise this signal. |
| `Financial_Model:09_04` | 3 after min-carry=2 | Blank forecast-year cells on `Financials` feeding a cash-line chain (`K46` etc.). Heuristic, not a Pepsi restore rule. |
| `Debugging:10_02` | 0 | |

It is already attached to scoped `formula-patterns-v1` inspect (`blank_dependency_bridges`). Do not
encode G4/Receivables. A same-model A/B with vs without the bridge is the next measurement; it is
an interface comparison, not a G4 hunt. Do not expand absence detectors after the ranking rejection.

**Measurement audit (2026-08-26) — supersedes every 44% / 48.7% / 10.4% / 4.1%
absence claim.** The official value-mode modification population mixes cells requiring a direct
edit with unchanged formulas whose values differ after upstream golden edits (and potentially
with stale/missing distributed caches). Equivalent raw formulas prove only that the formula cell
needs no direct edit; they do **not** prove a cache artifact or a free scoring point. Official
scoring remains unchanged. Offline characterization now reports three populations separately:

1. direct value targets (the cell itself differs),
2. unchanged-formula downstream value differences,
3. value-equivalent but dynamically different formulas (important after input changes even when
   today's value-mode score treats them as regression).

Across all 100 Financial Model tasks the official modification population contains 268,035
unchanged-formula value differences and 16,679 cache-robust direct value targets. There are also
3,020 value-equivalent formula differences that matter dynamically but not to today's value score;
zero have both caches absent, so none are indeterminate under this definition. Of the direct value
targets, 11,771 are blank in the input (70.6%) and 4,908 are populated. Fifty-two tasks have only blank
direct targets; this does not mean their whole answer ranges are blank. In the 48 mixed tasks,
5,324/10,232 direct targets are blank (52.0%). Their blank topology is column-peer 80.4%,
block-peer 14.1%, row-peer 4.8%, isolated 0.7%. So absence matters and column topology dominates
mixed tasks, but neither fact identifies which blank cells the instruction wants.

The broad reference-demand baseline reaches 7,042/11,771 blank direct targets (59.8%) from a pool
of 77,088 referenced blanks: pooled target share 9.1%, per-task median 17.5%. In the 48 mixed tasks
it reaches 77.7% of blank direct targets, with 6.9% pooled / 19.2% median target share. A referenced
blank is evidence, not a defect by construction: optional blanks and empty-as-zero formulas are
common. This broad pool is a superset of the shipped carry-chain bridge observation, not that
observation's candidate pool or a ceiling on its precision.

The shipped carry-chain bridge itself is a niche signal, not a general detector. With all sheets
selected (candidate generation gold-blind, then scored offline against goldens), the 100 FM tasks
produce 787 candidates; 429 survive
the per-workbook cap of 12, and 50 visible candidates are direct blank targets: 11.7% pooled
precision, 0.4% blank-target recall, with a visible hit on 17/100 tasks. It is excellent on a few
workbooks (`01_03` remains a one-candidate/one-hit example) and silent or distracting elsewhere.
Keep it bounded and explicitly heuristic; do not expand it as the absence solution. Whether it
belongs in the default formula-pattern observation remains an agent-level ablation question because
offline gold can measure candidate quality but cannot measure distraction cost.

The miss inventory is also narrower than its original name implied. The evaluator stores only the
first error for each non-exact task, so `benchmark/inventory_misses.py` inventories first-error
signatures, not all wrong cells. It cannot support a percentage claim about all cell-level misses.
The full-cell census is `benchmark/mismatch_census.py` (see §0). Known-invalid harness attempts are
listed in `benchmark/experiment_validity.py` and excluded from both aggregates.
`Template:02_05!E35` is diagnosed: GLM explicitly chose to accumulate surplus cash after debt was
repaid, contrary to the instruction's “exactly” requirement; successful runs link ending cash to
the operating cash requirement. Context, execution, and verification were available, so this is a
compiler reasoning miss, not a world/ISA miss.

**Financial Model `06_01..06_05` evaluator compatibility.** Their inputs alone have malformed
`docProps/core.xml` (`dc:` is reused out of scope); every golden is valid and LibreOffice opens all
files. The local metadata-tolerant evaluator wrapper repairs only that metadata member in a temp
copy and labels results `metadata-tolerant-local-v1`. It does not modify grids or benchmark data,
but such results are local-compatible scores, not the distributed evaluator runtime byte-for-byte.

**`Financial_Model:02_02` is a gold-blind exact.** Grok 4.6 medium, bounded `formula-patterns-v1` +
`formula-blocks-v1`, 8 calls, `$0.166338`. Official evaluator: exact `1.0` (regression clamped from
`3025/3026` = `0.9997` ≥ `0.998`; modification `1126/1126`). The single regression miss is
`IS, BS, CF!F95` (`0` vs `0.0100000000002183`). Tools: inspect ×2, `calc_read_ranges` ×3, one
`calc_fill_formulas`, compare, submit. This task had zero blank-dependency-bridge candidates; the
win is transfer of the bounded world, not the G4 heuristic.

**`Debugging:01_03` is development: the UNO write hole is closed; the score is not exact.** The
first Grok canary (`…-medium-1`, `$0.341`) wrote but the container dropped every single-cell
`setDataArray`. Root cause, docker-reproduced (host UNO does **not** catch this):
`getCellRangeByName("C9")` returns `ScCellObj`; container LO rejects `setDataArray` on it
(`cellsuno.cxx:5014`); `contextlib.throw` then attaches a traceback to the UNO object and pyuno
masks the real error as `Couldn't convert <traceback object>`. `write_range` now uses
`getCellRangeByPosition`, 1×1 cells use `Value`/`String`, and `_document` is class-based.

The post-fix canary (`…-medium-2`, `$0.388422`, 12 calls) produced a workbook. All program ops
returned `ok: true`. Tools: inspect, nine `calc_read_ranges` (many 96-cell bounces), one
`calc_program` (CHOOSE / sheet-name repairs plus `C9=3`), compare, autosubmit at the call cap.
No `insert_row`. Official value-mode after LibreOffice refresh: `7150/8668`, regression
`6413/6655` (`0.9636`), modification `737/2013` (`0.3661`), not exact. First error is a
**regression** at `Ex 1 - LBO!C9` (`1` vs `3`): input and golden both keep `1`; the instruction
stated the scenario selector is `3`. Do not encode CHOOSE, selector=`1`, or selector=`3`. Do not
rerun `01_03`.

### Mission in one line

Thick, deterministic, programmable Calc world for **external** coding agents. No LLM in the
server. Domain behind `CalcBackend`; UNO only in `backend/uno.py`. Benchmark-first.

**High entropy of intent, low entropy of primitives.** The LLM is a compiler into programs over
a bounded ISA. Matching SWE-agent's `bash` + `view_xlsx` score would mean we failed to densify
the world, not that we lacked "flexibility." A junk drawer of per-miss tools is also not a
philosophy. Experiment overlays (`formula-blocks-v1`, anomaly prompts) are **measuring
instruments, not the product**.

### Public Debugging slice (contaminated development — not held-out)

| Task | Family | Last useful result |
|---|---|---|
| `10_02` Embedded Hardcodes | formula rewrite | formula-mode mod `41/47` (`0.8723`); nine hardcode repairs match |
| `07_01` Double Counting | formula logic | value-mode mod `85/86` (`0.9884`) |
| `04_06` Cross-sheet refs | formula retarget | **no workbook**, `$0.331`; inspect-spiral; fill *can* express this |
| `05_03` Errors | deleted-row `#REF!` | **no workbook**, `$0.178`; fill cannot insert |
| `08_03` Errors | deleted-row `#REF!` | **no workbook** three times; see causal stack below |

Official eval: `with_formula=True` only when the golden path contains `Embedded`; else value-mode.
Public Opus on `07_01` / `05_03` / `08_03` was `0.0000` modification (gold-blind). Public Opus on
`04_06` read a golden — not a comparator. Public slice:
`benchmark/slices/public-example-nonvisual-v1.json`. Competitive slice:
`benchmark/slices/grok-v2-five.json` (all five now development except `Financial_Model:02_02`
official-exact; `Debugging:01_03` post-fix workbook is not exact).

### World surface now

Domain ops: `write_range`, `set_formula`, `fill_formula`, `clear_range`, `create_sheet`,
`insert_row`, `delete_row`. Insert is before a 1-based `index`; optional `count` defaults to 1.
Memory backend shifts stored keys (toy; not full Calc ref-rewrite). UNO uses `Rows.insertByIndex`
/ `removeByIndex`.

SWE-agent tools: `calc_inspect`, `calc_read`, `calc_read_ranges`, `calc_compare`, `calc_write`,
`calc_fill_formulas`, `calc_program`, `submit`. Bash is off.

World invariants just added (kind-repeating, not `08_03` patches):

1. **Neighborhood reads are bounded** at 96 cells (`_READ_NEIGHBORHOOD_MAX_CELLS` in
   `benchmark/sweagent/librecalc/lib/calc_tool.py`). Oversize `calc_read` requests return a
   structured error. `calc_read_ranges` validates the same bound per item: valid siblings are
   returned and each oversize item gets its own `{"ok":false,"error":...}` instead of rejecting
   the whole batch. Inspect may still read used ranges internally.
2. **`formula-anomalies-v1` inspect includes `formula_errors`**: compact representatives
   collapsed by sheet / error kind / formula shape (`repeat_count`), same heuristic status as
   the translation shortlist. Each selected representative now includes at most four nearby
   literal cells: nearest row labels/values and column headers/values, with addresses, relation,
   and distance. This is deterministic context, not repair inference. Enable `include_errors` on
   that inspect path.
3. **Exact-path isolation is explicit in the agent scaffold.** Two Grok tasks each wasted three
   calls inspecting a directory, a guessed sibling input, and/or a not-yet-created output. The
   frozen system prompt now says only the supplied Input and Output paths exist. This changes no
   server operation and does not expose another file.

Frozen fill overlay still strips `calc_write` / `calc_program`. Errors-family probes use
**unfrozen** `semantic-program-v1`.

### `08_03` causal stack (do not collapse these)

1. **Missing geometry** (frozen fill-only): compiler diagnosed deleted total-revenue / `#REF!`
   and could not insert a row. `insert_row` was added. Not a `restore_UFCF_row` heuristic.
2. **Primitive unused** (`…-semantic-program-auto-low-1`, `$0.109`): `insert_row` available,
   never called. Anomalies selected three hardcode-shaped cells. Model dumped whole sheets,
   then `finish_reason=length` (8192 output cap) → format error → autosubmit.
3. **Invariants held, compiler tiled** (`…-bounded-inspect-auto-low-1`, `$0.036813`, 12 calls,
   58s): inspect listed **569** errors (`Err:509` 400, `#REF!` 169) as 20 shape representatives
   (top: `Operating Model + DCF!E9` `Err:509` ×125, shape `=<REF>/<REF>`). Six of eleven
   `calc_read_ranges` bounced (`A1:L41` = 492 cells, then 144, 162, …). Model tiled
   `Comps + WACC` (**0 errors**) down toward 96 cells, burned the call cap, **zero writes**.
4. **Dense error context did not rescue K2.7** (`…-error-context-auto-low-1`, `$0.023320`,
   12 calls, 110s): inspect attached useful labels/headers to all 20 representatives (`Revenue`,
   `Gross Profit`, `SG&A`, `Cloud`, years, etc.). The next call still requested four broad regions.
   Every later call was `calc_read_ranges`; the model repeatedly shrank whichever item triggered
   the next 96-cell rejection. It made **zero successful writes** and never called `calc_program`.

Trajectory:
`benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/kimi-k2.7-code-debugging-08_03-bounded-inspect-auto-low-1/`

Inspect-dense trajectory:
`benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/kimi-k2.7-code-debugging-08_03-error-context-auto-low-1/`

Same overlay will shrink-and-retry. Remaining miss is compiler discipline / inspect not dense
enough to make tiling unnecessary — not a missing op.

### Cheap-lane frozen config

`moonshotai/kimi-k2.7-code`, `formula-anomalies-v1`, progressive, `$2` cap, 12 calls, low
reasoning, `--max-requeries 2`, `--timeout 1200`, no `--max-tokens` (runner caps missing
output limits at 8192). Use `--execution formula-blocks-v1` for formula-only; 
`semantic-program-v1` when geometry may compose.

Do not use Opus for interface development. Ox Alpha is a free low-capability probe, not the
fallback. OpenRouter key is ephemeral: operator supplies `OPENROUTER_API_KEY`, never write it
into docs, trajectories, or commands that get committed. Unset after the run.

```bash
read -rsp 'OpenRouter key: ' OPENROUTER_API_KEY
export OPENROUTER_API_KEY
uv run python benchmark/run_openrouter_slice.py \
  --slice benchmark/slices/public-example-nonvisual-v1.json \
  --run-name REPLACE-ME \
  --model moonshotai/kimi-k2.7-code \
  --observation formula-anomalies-v1 \
  --execution semantic-program-v1 \
  --read-policy progressive \
  --cost-limit 2.00 \
  --call-limit 12 \
  --max-requeries 2 \
  --reasoning-effort low \
  --timeout 1200 \
  --task Debugging:08_03
unset OPENROUTER_API_KEY
```

Docker + the SpreadsheetBench 2 image are required. Local UNO on `localhost:2021` is for
dev/tests (`LIBRECALC_RUN_UNO=1`), not the isolated agent. Goldens are never mounted.

### Repository state and safety

- The worktree is intentionally dirty. Preserve it; do not reset or discard unrelated changes.
- Keep spreadsheet semantics behind `CalcBackend`. New ops: memory-backend test first.
- Local verification at this handoff: `117 passed, 8 skipped`; `ruff check .` passes.
- Do not encode `(-) OpEx`, nine hardcode cells, UFCF, Contract Revenue, or other
  task-specific restores. Do not expose goldens to the agent.

### What is built and has demonstrated usefulness

- `CalcBackend` isolates domain semantics from UNO. Memory and UNO backends support workbook
  inspection, batched range reads, values/formulas/errors, compact selected-cell format reads,
  writes, deterministic formula fill, clear, recalculation, geometry (insert/delete row), and
  one-save program execution.
- Isolated SpreadsheetBench 2 runner: one input workbook read-only, private output directory.
- Native tool calls one at a time. Invalid tools return structured JSON without killing SWE-ReX.
- Observation variants: structure-only, formula patterns, semantic snapshots/diffs,
  `formula-anomalies-v1` (translation consensus + sequence gaps + formula-error representatives).

### Best benchmark evidence so far

| Task / model | Cost | Official result | Interpretation |
| --- | ---: | --- | --- |
| `Template:02_05`, Kimi K2.5, semantic v2 | `$0.00570253` | Exact `185/185` | Isolated loop works end to end. |
| `Template:02_05`, Ox Alpha | `$0` | regression `1.0`, modification `0.375`, not exact | Free probe; not the active lane. |
| `Financial_Model:09_04`, Kimi K2.7 Code, formula patterns | `$0.068615` | regression `1.0`, modification `0.9981`, not exact | One-cell miss (`Valuation!G59` should link WACC). |
| `Debugging:10_02`, Kimi K2.7 Code, refined anomaly view | `$0.054597` | regression `1.0`, modification `41/47` (`0.8723`), not exact | All nine hardcode→formula repairs match. Six misses are P&L `(-)` label prefixes. Public Opus `0.7021`. |
| `Debugging:05_03`, Kimi K2.7 Code, frozen fill | `$0.177607` | No workbook | Errors family. Five reads, format-error exit. Fill cannot insert rows. Public Opus `0.0000`. |
| `Debugging:07_01`, Kimi K2.7 Code, frozen fill | `$0.196742` | regression `9970/10004` (`0.9966`), modification `85/86` (`0.9884`) | Formula ISA transfers beyond hardcodes. Public Opus `0.0000`. |
| `Debugging:04_06`, Kimi K2.7 Code, frozen fill | `$0.331478` | No workbook | Cross-sheet refs. All reads, format-error exit. Fill *can* retarget. Public Opus `0.8424` read a golden. |
| `Debugging:08_03`, Kimi K2.7 Code, frozen fill | `$0.144598` | No workbook | Diagnosed missing row / `#REF!`; no fill. Public Opus `0.0000`. |
| `Debugging:08_03`, Kimi K2.7 Code, unfrozen program | `$0.108810` | No workbook | `insert_row` available, unused. Dump → length → autosubmit. |
| `Debugging:08_03`, Kimi K2.7 Code, bounded reads + inspect errors | `$0.036813` | No workbook | Invariants held. Compiler tiled a zero-error sheet and never wrote. |
| `Debugging:08_03`, Kimi K2.7 Code, inspect error context | `$0.023320` | No workbook | Useful labels/years were present; compiler still used all remaining calls shrinking rejected dumps. |
| `Template:01_02`, Kimi K2.7 Code, formula patterns | `$0.059763` | No workbook | Understood much of the OID problem, then used two full responses reasoning without emitting a tool call. |
| `Template:01_02`, Grok 4.6 medium, formula patterns | `$0.140878` | `274/280`; regression `226/228`, modification `48/52` | Clean held-out threshold. Compact fill executed correctly; six maturity-year misses are accounting reasoning. |
| `Template:02_04`, Grok 4.6 medium, formula patterns | `$0.086942` | `118/130`; regression `93/93`, modification `25/37` | Workbook produced. Twelve interest/total cells differ only by quarterly-rate convention (exactly 4×). |
| `Financial_Model:01_03`, Grok 4.6 medium, formula patterns | `$0.538236` | `2586/2843`; regression `2413/2425`, modification `173/418` | 35/40 requested formulas exact; five wrong Capex source refs plus an unstated historical Receivables prerequisite cascade. Inspect/compare were 163 KB/199 KB. |
| `Financial_Model:02_02`, Grok 4.6 medium, bounded formula patterns | `$0.166338` | **Exact** `1.0`; regression `3025/3026` clamped, modification `1126/1126` | First untouched `grok-v2-five` exact. 8 calls. One 1¢ regression float at `IS, BS, CF!F95`. |

Do not use Opus during interface development. Prior Opus probes were expensive and exposed harness
or golden-data issues rather than justifying the spend. K2.7 remains the cheap threshold probe;
Grok 4.6 is the current competitive lane after crossing the execution threshold on `01_02`. Ox
Alpha remains a free low-capability probe, not the current fallback.

Held-out trajectories:

```text
benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/kimi-k2.7-code-heldout-template-01_02-formula-patterns-auto-low-1/
benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/grok-4.6-heldout-template-01_02-formula-patterns-auto-medium-1/
benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/grok-4.6-heldout-template-02_04-formula-patterns-auto-medium-1/
benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/grok-4.6-heldout-financial-model-01_03-formula-patterns-auto-medium-1/
benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/grok-4.6-heldout-financial-model-02_02-formula-patterns-auto-medium-1/
```

### Debugging:10_02 — exact current state

The task input is:

```text
benchmark-data/SpreadsheetBench-2/data/Debugging/spreadsheet/10_Debugging/input_files/Embedded Hardcodes_input.xlsx
```

Offline golden characterization is allowed for this contaminated public development task, but the
golden must never be exposed to the model. There are nine genuine hardcode-to-formula repairs:

```text
Model!I53, I131, I135, I172, J175, K175, I291
P&L Summary!G19
BBC -- Backcountry + SAIL!F3
```

Thirty-three other apparent hardcode/formula differences are strings such as `#REF!` normalized to
literal `=#REF!` formulas in the golden. They are not evidence that the agent should reconstruct
unrelated broken sheets.

The first anomaly canary showed that full recall alone was dangerous. After that run, the observation
was refined deterministically:

- exact translated-formula consensus provides inferred formulas and source addresses;
- short repeated-formula-shape gaps surface the two SOFR cells without inventing their formulas;
- `formula_a1_shape` preserves quoted sheet names, strings, and function names;
- selected-cell formatting fingerprints distinguish conventional blue inputs from formula-colored
  cells without scanning every cell individually;
- unfilled black historical constants, unbracketed trailing assumption blocks, literal error
  formulas, and signal-saturated sheets are deprioritized;
- `4-Wall Analysis` is explicitly reported as saturated instead of flooding the shortlist;
- every signal is labelled heuristic and requires a focused confirmation/read before writing.

The final real-UNO measurement is the key handoff fact:

```text
payload:                  21,243 bytes
translation candidates:  19,544 total, 7 selected
sequence gaps:            6 total, 4 selected
format-deprioritized:     96 pre-ranked candidates
edge-block-deprioritized: 4 candidates
saturated sheets omitted: 4-Wall Analysis
offline task coverage:    9/9 true repairs
offline selected precision: 9/9 unique selected cells are true repairs
```

The seven translation selections are exactly `Model!I53`, `I131`, `I135`, `I172`, `I291`,
`P&L Summary!G19`, and `BBC -- Backcountry + SAIL!F3`. The four sequence selections are
`Model!I131`, `J175`, `K175`, and `P&L Summary!G19`; the overlap is intentional corroboration.

All nine hardcode-to-formula repairs now match the golden in the `…-auto-low-4` workbook. The only
official misses are six P&L label prefixes. Freeze this variant. Do not add a `(-) OpEx` heuristic.

The `Debugging:05_03` transfer used the frozen K2.7 configuration and produced no workbook
(`$0.177607`, five reads, format-error exit). That task is deleted-row / `#REF!` repair, not
embedded hardcodes; formula-block execution cannot insert rows. Do not widen the ISA from this
single miss. Public Opus also scored `0.0000` modification on this example.

The `Debugging:07_01` transfer (Double Counting) produced a workbook in 10 calls for `$0.196742`.
Official value-mode scoring (`with_formula=False`; only Embedded uses formula-mode): regression
`9970/10004` (`0.9966`), modification `85/86` (`0.9884`), not exact. Public Opus modification on
this example was `0.0000`. Treat as successful transfer of the frozen formula ISA to a
non-structural logic family. Do not chase the residual cells with task-specific heuristics.

The `Debugging:04_06` transfer (Incorrect Cross Sheet References) produced no workbook
(`$0.331478`, 11 calls / 7 tools, all reads, format-error exit). Formula-blocks can express
retargeted formulas; the miss is confirm-then-write discipline, not a new primitive. Public Opus
on this example read a golden — do not use that score as a gold-blind baseline.

### Next action, in order

1. **Do not rerun `02_02`, FM `01_03` (observation bound), `08_03`, or Debugging `01_03`.**
   `Financial_Model:02_02` is the only official-exact on `grok-v2-five.json`. The slice is exhausted
   as held-out.
**Grok-v3 Template so far (not exact).** Frozen formula-patterns / formula-blocks, medium.
`Template:03_01` `$0.142158`, `290/312`, first miss regression `M&A_Consolidation!C14`.
`Template:05_01` `$0.097202`, `396/400`, official exact `0.0`, first miss regression
`DeferredTax!C23` (`None` vs `100`). Do not encode cell heuristics.
`Financial_Model:03_01` `$0.436328`, `92039/92052`, official exact `0.0`, regression
`91485/91485` (clamped `1.0`), modification `554/567` (`0.9771`). First miss
`Balance Sheet!O9` (`NA` vs `#DIV/0!`). Do not encode that cell.
`Financial_Model:05_01` `$0.482988`, `52985/53004`, official exact `0.0`, regression
`51015/51030` (clamped `1.0`), modification `1970/1974` (`0.998`). First miss
regression `Dashboard!G46` (`None` vs `2`). Do not encode that cell.
`Debugging:02_01` **no workbook**, `$0.455650`, 12/12 calls, inspect/read neighborhood
bounces, autosubmit at the call cap. Confirm-then-write miss, not a missing primitive. Do
not raise `--call-limit` or the 96-cell read cap. Do not rerun `02_01`.
`grok-v3-five.json` is exhausted as held-out: `0/5` official exact (four close computational
misses, one Debugging no-write). Do not quote a full-benchmark exact rate.

**DeepSeek V4 Flash 0731 failed the Template write-gate.** `Template:05_01`, frozen
formula-patterns / formula-blocks, reasoning `high`, `$0.002725`, 5 model calls / 3 tools
(inspect, inspect, read), then SWE-agent **repeated format/blocklist errors** and autosubmit.
No workbook. Not a missing primitive. Do not rerun Flash on `05_01`.

**GLM 5.3 first canary never reached the model.** `z-ai/glm-5.3` on `Template:05_01`
rejected `tool_choice=required` (`Tool choice must be auto`, `$0`, 0 calls, ~16 min retry
then autosubmit). Same harness class as Muse Spark. `_tool_choice` now maps `glm-5.3` to
`auto`; retry as `…-high-2`. Do not treat the `$0` run as a compiler miss.

**GLM 5.3 passed the Template write-gate.** `…-high-2`, `$0.046294`, submitted. Official
value-mode `398/400`, regression `341/343` (`0.9942`), modification `57/57` (`1.0`), not
exact. First miss is the same regression over-edit as Grok (`DeferredTax!C23`, empty vs
`100`). Grok on this task was `396/400` / `$0.097`. Do not encode C23. Do not rerun `05_01`.

**GLM 5.3 FM write-gate passed.** `Financial_Model:05_01`, `$0.140717`, submitted.
Official `52986/53004`, regression clamped `1.0`, modification `1972/1974` (`0.999`).
First miss same regression over-edit as Grok (`Dashboard!G46`). Cheap lane transfers to FM.
Do not rerun `05_01`. OpenRouter `z-ai/glm-5.3`, `tool_choice=auto`
(Spark/GLM reject `required`), `formula-patterns-v1` + `formula-blocks-v1`, progressive,
`--reasoning-effort high`, `$2` / 12 calls. Park Grok and Cursor CLI for competitive runs.
Do not mix harness numbers.

**Debugging read-budget instrument (formula-anomalies-v1 only).** After `calc_inspect`,
at most one successful `calc_read` / `calc_read_ranges` batch; further reads return a
structured “write now” error. State: `/mnt/spreadsheet_output/.librecalc_read_budget.json`.
Not a product primitive; do not raise the 96-cell cap or call limit.

**Chart ISA v0 landed (UNO-first).** Domain `ChartSpec` + program ops `upsert_chart` /
`delete_chart`; memory round-trip tests; UNO native line/column/pie/scatter/bubble path in
[`uno_charts.py`](src/librecalc_mcp/backend/uno_charts.py). `sunburst` / `waterfall` /
`gauge` return honest `compile_note` (`unsupported` / `scaffold`). Translation-loss fixture:
[`tests/test_chart_translation.py`](tests/test_chart_translation.py) (UNO skip unless
`LIBRECALC_RUN_UNO=1`). Visualization agent runs remain blocked until inspect+upsert are
exercised; official VLM eval is Windows Excel COM.

**GLM 5.3 Debugging probe (03_01).** `formula-anomalies-v1` + read budget + blocks,
`$0.005388`, **no workbook** (inspect-only; autosubmit). Same confirm-then-write class as
Grok `02_01`. Filename-space alias symlinks now staged for Debugging inputs. Stop further
Debugging budget on GLM unless measuring a fresh held-out; zeros stay a publish caveat.

**GLM 5.3 held-out v4 (`glm-v4-five`, exhausted).** Five tasks, five workbooks, `$0.359`
charged (one failed Debugging retry excluded from completion claim). Official exact **2/5**
after scoring: `Financial_Model:01_04` and `Financial_Model:02_04` exact; `Template:02_03`
close (`reg 0.95`, `mod 0.53`); `Debugging:04_01` close (`reg 1.0`, `mod 0.97`);
`Template:01_04` **scored 0/0** — post-mortem: harness copied `Financial_Model:01_04`
output into `Template:01_04` because `_find_output` matched task id only across categories
(**fixed** — now category-scoped). Do not rerun v4 for publish; treat Template:01_04 score
as invalid/contaminated.

**GLM 5.3 held-out v5 (`glm-v5-five`, exhausted).** Five tasks, five workbooks, `$0.213`.
Official exact **0/5**; all **`reg 1.0`**. Modification peaks: `Financial_Model:01_02`
(`0.996`), `Template:01_03` (`0.93`); Debugging `04_02` missed primary chart target
(`mod 0.0`, fixed only `Line Item Metrics!M29`). Lane story unchanged: cheap completion,
FM strongest exact lane, Debugging weakest.

**Harness fixes (Aug 2026).** `.env` auto-load for `OPENROUTER_API_KEY`; append-to-existing
run directories; Debugging filename underscore aliases; category-scoped output discovery;
[`benchmark/score_openrouter_run.py`](../benchmark/score_openrouter_run.py) for official
evaluator passes.

**Visualization lane started.** Chart tools exposed to agents: `calc_inspect_charts`,
`calc_upsert_chart` (wraps domain `upsert_chart`); config
[`benchmark/sweagent/spreadsheet-viz.yaml`](../benchmark/sweagent/spreadsheet-viz.yaml);
dev canary [`benchmark/slices/viz-dev-line-one.json`](../benchmark/slices/viz-dev-line-one.json)
(`Visualization:Task 1411527`, native line chart). Native LO PNG export + OpenRouter
`glm-4.6v` checklist scoring bridge landed. Viz ladder `glm-5.3-viz-ladder-five-high-1`:
**4/5** workbook completions / **1** format-error fail; VLM **0/4** @0.7. Postage-stamp
PNGs were agent `width`/`height` as Excel **col×row spans** (e.g. 16×9) misread as HMM —
`ChartSpec` now matches Excel/SpreadsheetBench defaults (~8×15 cells), treats small
ints as spans, floors at 5×3 cm. Axis titles now use `HasX/YAxisTitle` + title shapes
(not the unreliable Axis.DisplayTitle path); `data_labels` shows category names;
`series.point_colors` sets per-point FillColor via Chart2. Remaining hard gaps are
LO-vs-Excel (combo, multi-level category axes), not harness wiring.

**Publish:** report **non-visual subset only** (~297 Template+FM+Debugging); **10 held-out
GLM tasks** (v4+v5) as cost/completion sample — **2/10 official exact**, ~**$0.57** total,
~**$0.06/task** avg. Do not quote full-bench exact %. Visualization still out of official
publish until translation matrix + agent canary complete.

**Next:** optional `viz-dev-line-one` agent run; classify v5 modification misses; no further
GLM non-visual held-out slices until publish note lands. Do not encode task-specific golden
shortcuts.

### High-value paths

```text
AGENTS.md
docs/PROJECT_CONTEXT.md          §0 is this brief; wins on conflict
docs/benchmark-plan.md
docs/public-trajectory-audit.md
benchmark/README.md
benchmark/run_openrouter_slice.py
benchmark/sweagent/librecalc/lib/calc_tool.py
benchmark/sweagent/librecalc/config.yaml
src/librecalc_mcp/domain/models.py
src/librecalc_mcp/domain/formulas.py
src/librecalc_mcp/backend/memory.py
src/librecalc_mcp/backend/uno.py
tests/test_benchmark_observations.py
tests/test_openrouter_runner.py
tests/test_memory_backend.py
benchmark/slices/public-example-nonvisual-v1.json   contaminated
benchmark/slices/grok-v2-five.json                  exhausted held-out / development
benchmark/slices/grok-v3-five.json                  exhausted held-out
benchmark/slices/glm-v4-five.json                 exhausted held-out
benchmark/slices/glm-v5-five.json                 exhausted held-out
benchmark/slices/viz-dev-line-one.json            visualization dev canary

benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/
  grok-4.6-heldout-financial-model-02_02-formula-patterns-auto-medium-1/
  grok-4.6-heldout-debugging-01_03-formula-anomalies-program-medium-1/
  grok-4.6-heldout-debugging-01_03-formula-anomalies-program-medium-2/
  kimi-k2.7-code-debugging-08_03-bounded-inspect-auto-low-1/
  kimi-k2.7-code-debugging-08_03-semantic-program-auto-low-1/
  kimi-k2.7-code-debugging-10_02-formula-anomalies-auto-low-4/
```

---

## 1. One-sentence project thesis

Build a **thick, deterministic, programmable LibreOffice Calc world for external coding agents**, exposed through MCP, so capable agents can inspect, reason over, program, modify, and eventually validate/version real spreadsheets without needing to understand UNO or manipulate the UI.

The project is **not** a chatbot for LibreOffice.

---

## 2. The larger paradigm this project is exploring

The broader research idea is **just-in-time / ephemeral software**:

> Instead of pre-building a permanent application for every possible user workflow, expose a bounded programmable world and let an LLM synthesize a temporary task-specific program over that world when needed.

The generated code is not necessarily the durable artifact. It may exist only long enough to perform a task. The persistent result may be a spreadsheet, report, dataset, graph, changed state, or other native artifact.

A useful stack is:

```text
Human intent
    ↓
External agent / LLM compiler
    ↓
Domain program / IR
    ↓
Semantic primitive set / capability algebra
    ↓
Domain runtime
    ↓
Persistent world state / artifact
```

In this project:

```text
Human intent
    ↓
Codex / Claude Code / Cursor / other agent
    ↓
Temporary Calc program / MCP calls
    ↓
LibreCalc semantic capability layer
    ↓
UNO
    ↓
LibreOffice Calc workbook
```

The project therefore explores a more general question:

> **What is the right instruction set for an autonomous agent operating inside a spreadsheet world?**

---

## 3. Core mental model: the domain is a computer

Treat a domain as a virtual machine.

A useful abstract world model is:

```text
W = (S, O, A, T, I)
```

where:

- `S` = state of the world,
- `O` = observations available to the agent,
- `A` = primitive actions,
- `T` = transition semantics,
- `I` = invariants / constraints.

A language or grammar `G` determines which programs can be composed from the available primitives.

For Calc:

```text
State
  workbook, sheets, ranges, values, formulas, names, charts, styles...

Observations
  workbook structure, cell contents, formulas, dependencies, errors...

Actions
  read, write, create, delete, rename, formulate, recalculate, chart...

Transitions
  Calc/UNO semantics

Invariants
  workbook remains valid, formulas resolve, protected constraints hold...
```

The LLM is best thought of as a **compiler from fuzzy user intent into programs over this world**.

This is not the same as “give the model a shell.”

A shell is extremely expressive but semantically thin. A good agent world should have a compact primitive set with high semantic density.

---

## 4. The central primitive-design problem

The world must avoid both extremes.

### Too thin

```text
click(x, y)
type(text)
get_cell(A1)
set_cell(A1, value)
```

These are expressive only through huge amounts of agent work. The runtime understands almost none of the domain semantics.

### Too high-level

```text
make_quarterly_sales_report()
build_financial_model()
fix_forecast()
```

These encode anticipated workflows directly. This recreates conventional application development and destroys the combinatorial advantage of program synthesis.

### Desired region

We want:

- enough semantics that operations correspond to meaningful spreadsheet concepts,
- enough orthogonality that novel tasks emerge through composition,
- enough structure to inspect, validate, bound, and eventually govern programs.

A rough objective is:

```text
maximum expressive closure
minimum primitive surface
subject to safety + learnability + verifiability
```

This primitive-basis question is one of the core intellectual problems in the project.

---

## 5. Why Calc is first

LibreOffice consists of Writer, Calc, Impress, Draw, Base, and Math.

The longer-term office-suite idea is interesting, but **Calc is the first target deliberately**.

Why Calc:

1. **It is both state and computation.**
   - Cells hold data.
   - Formulas encode executable relationships.
   - Dependencies form a graph.
   - Changes propagate through recalculation.

2. **It is structurally inspectable.**
   The agent can reason about ranges, formulas, dependencies, names, sheets, tables, and charts without requiring subjective semantic interpretation for every operation.

3. **It supports a powerful read/write loop.**

```text
inspect → traverse → compute → modify → recalculate → inspect again
```

4. **There are strong external benchmarks.**
   We can avoid spending months learning spreadsheet workflows manually.

5. **Spreadsheet work is already a form of end-user programming.**
   The agent is not merely creating documents; it can construct persistent executable models.

Conceptually, a spreadsheet already resembles a graph:

```text
cells       = nodes
references  = edges
formulas    = transformations
```

This is one reason the project parallels the separate graph-agent project: both benefit from low-level traversal tools plus a higher-level programmable traversal/execution interface.

---

## 6. Important architectural decision: the MCP server is not the agent

The system should **not** embed another LLM, planner, web-search system, or chat product.

The external host agent may already have:

```text
Python
shell
web search
filesystem
pandas
NumPy
DuckDB
other MCP servers
its own planning/reasoning
```

Our server should expose a deterministic domain world.

Target architecture:

```text
Claude Code / Codex / Cursor / future coding agent
                  │
                  │ reasoning, planning, arbitrary host tools
                  ▼
            LibreCalc MCP
                  │
                  │ deterministic spreadsheet semantics
                  ▼
           Calc domain layer
                  │
                  ▼
                UNO
                  │
                  ▼
        LibreOffice Calc
```

The project should improve automatically as external models improve.

We own **the world**, not the intelligence.

---

## 7. Generic computation vs domain-native computation

Do **not** turn the MCP server into a replacement for pandas, NumPy, DuckDB, or arbitrary Python.

Rule:

> **The host agent owns generic computation. Our world owns computation whose meaning should persist inside the spreadsheet.**

Example:

### Fine to do outside Calc

```text
scrape data
run an ML model
parse a PDF
perform an arbitrary NumPy calculation
execute a simulation
```

### Should be representable inside our world when it forms part of the workbook

```text
import dataset
create/reshape table
create formulas
establish named ranges
create pivots
create charts
construct derived tables
recalculate
trace dependencies
validate model
```

A crucial future concept is **derived data**.

If an agent uses pandas externally and simply dumps the final numbers into Calc, the workbook loses the computational relationship between input and output.

The stronger representation preserves something like:

```text
raw data
   ↓
transformation program
   ↓
derived table
   ↓
metric / chart / model
```

The exact representation should be earned through benchmark failures rather than designed speculatively in v0.

---

## 8. Low-level tools AND program execution

This is a deliberate dual-interface design.

Agents need low-level tools for discovery, inspection, debugging, and local manipulation.

But forcing complex tasks through hundreds of individual MCP calls defeats the purpose of code synthesis.

Therefore the project should support both:

### Inspection / low-level tools

Examples:

```text
workbook.inspect
range.read
formula.inspect
chart.inspect
```

### Program execution

Conceptually:

```text
office.execute(program)
```

The external coding agent authors a temporary program that composes domain primitives, and the runtime executes it in one or a small number of calls.

Current v0 intentionally uses a deterministic operation list rather than arbitrary Python supplied by the model.

Example conceptual program:

```python
[
    {"op": "create_sheet", "name": "Analysis"},
    {
        "op": "write_range",
        "sheet": "Analysis",
        "range": "A1:B2",
        "values": [["Revenue", "Cost"], [100, 60]],
    },
    {
        "op": "set_formula",
        "sheet": "Analysis",
        "range": "C2",
        "formula": "=A2-B2",
    },
]
```

The long-term question is what the ideal agent-native Calc language should be:

- operation list,
- restricted Python-like DSL,
- declarative IR,
- custom typed language,
- or something else.

Do not decide this prematurely.

---

## 9. Read side and write side are equally important

The goal is not a spreadsheet query system.

A complete world needs both:

```text
                 CALC WORLD

        READ                    WRITE

inspect workbook           create sheet
inspect table              create table
read range                 write range
inspect formula            create formula
trace dependencies         modify formula
inspect chart              create chart
find errors                restructure model
       │                        │
       └──────────┬─────────────┘
                  │
              PROGRAMS
```

This mirrors the graph-agent architecture:

```text
traverse graph
    ↓
reason / compute
    ↓
write graph
```

For Calc:

```text
inspect workbook
    ↓
reason / compute
    ↓
modify workbook
    ↓
recalculate
```

The write/post side is essential because the persistent output is often a **living workbook**, not merely an answer returned to the user.

### 9.1 Observation is a compiled interface, not a dump

The observation model drives the agent's feedback loop and should be treated as a first-class
design surface. A useful observation should be:

- compact enough that repeated inspect/act/verify loops are affordable,
- address-stable so every fact maps back to an exact workbook location,
- semantically complete enough to expose labels, constant inputs, formulas, calculated values,
  regions, and meaningful absences,
- deterministic and backend-independent,
- layered so an agent can start broad and request focused detail without losing context.

Keep deterministic workbook facts separate from heuristic affordances. For example, labels,
formulas, values, and occupied regions are facts; a likely missing formula cell is an inference.
Heuristics may guide attention, but must be explicitly marked and must never silently become task
requirements.

The intended loop is:

```text
semantic snapshot
    ↓
focused inspection when necessary
    ↓
bounded program execution
    ↓
recalculation
    ↓
same semantic snapshot + semantic diff / validation
```

Absence is data in a template-completion task. Blank cells inside a time-series row can be more
important than populated cells, so sparse encodings must preserve meaningful gaps rather than
making them implicit.

---

## 10. Why the persistent artifact matters

A good task outcome is not:

```text
agent → Python → final prose answer
```

It is often:

```text
agent
  ↓
analysis
  ↓
structured native workbook
  ↓
human can inspect / modify assumptions / reuse later
```

The workbook should remain executable after the agent session ends.

A particularly important quality bar is:

> **Does the workbook still work when its inputs change?**

That separates:

- an AI-generated spreadsheet-shaped artifact,
- from software constructed *inside* a spreadsheet.

---

## 11. Version control / transactions are important, but not v0 scope

Autonomous writes make spreadsheet history and rollback much more important.

The project will eventually need a semantic history system rather than relying only on binary file copies.

Target execution model:

```text
snapshot
   ↓
execute program
   ↓
recalculate
   ↓
validate
   ↓
semantic diff
   ↓
commit OR rollback
```

A future semantic diff might report:

```text
+ Sheet: FY27 Scenario
~ Revenue!G17
    =SUM(G4:G16)
    →
    =SUM(G4:G15)

~ NamedRange: TaxRate
    0.21 → 0.23

+ Chart: MarginSensitivity
+ 84 formulas
- 1 broken external reference

Dependency impact:
Revenue!G17
   ├── EBITDA!D11
   ├── Dashboard!B4
   └── Chart: Operating Margin
```

Conceptually Git-like ideas map well:

```text
snapshot  → workbook version
diff      → semantic spreadsheet change
branch    → alternative scenario
commit    → approved agent modification
rollback  → restore
merge     → reconcile parallel edits
blame     → origin/history of formula or change
```

However:

> **Do not build a full spreadsheet VCS before the benchmark forces us to.**

For early work, only keep the architecture compatible with eventual snapshots/diffs/transactions.

---

## 12. Benchmark-first philosophy

The user explicitly wants to avoid unnecessary spreadsheet-domain research and scope creep.

This is a project rule:

> **Use existing benchmarks as the v1 requirements discovery process.**

A benchmark is not a perfect ranking of business value, but good benchmarks have already spent significant effort identifying realistic tasks, curating workbooks, defining correctness, and observing agent failure modes.

Instead of inventing 100 spreadsheet primitives from intuition:

1. run a benchmark task,
2. observe failure,
3. classify failure,
4. ask whether the model failed or the world/interface was too thin,
5. add the smallest semantic capability that addresses the failure,
6. rerun.

The benchmark becomes an **abstraction-discovery mechanism**.

A useful scope-control question for every feature is:

> **Does this help solve a benchmark task or remove a clearly measured interface bottleneck?**

If not, put it in `future.md` / backlog rather than implementing it.

The intentional exception is **program execution**, because it is part of the core research hypothesis even if a benchmark does not explicitly demand that interface design.

---

## 13. Benchmark hierarchy

### 13.1 SpreadsheetBench 2 — v1 north star

Treat SpreadsheetBench 2 as the main product/research requirements document for v1.

It covers four useful classes of realistic tasks:

1. **Financial Modeling**
2. **Debugging**
3. **Template completion**
4. **Visualization**

The tasks involve large, multi-sheet workbooks and many coordinated edits, which makes them suitable for testing whether a thick semantic interface is better than cell-by-cell manipulation.

Known important failure modes from the benchmark include:

- insufficient spreadsheet inspection,
- incorrect target-cell selection,
- global inconsistency even when many local edits are correct,
- very poor debugging performance.

Those failures map directly to the hypothesized value of:

```text
structured inspection
dependency awareness
programmatic execution
validation
semantic targeting
```

### 13.2 SpreadsheetBench / SpreadsheetBench Verified — breadth/regression

Use these for broader everyday spreadsheet operations and regression checking.

They are useful for testing whether the world is missing common spreadsheet capabilities.

Do not make them the sole quality target because exact output/value correctness does not fully capture workbook design or dynamic behavior.

### 13.3 BlueFin — later living-model quality bar

BlueFin is more finance-specialized and should not dictate v1.

Use it later to push toward:

- formula correctness,
- model integration,
- perturbation/dynamic correctness,
- professional quality,
- persistent models that react correctly when inputs change.

The project should not require the developer to become a finance expert before the underlying agent interface is proven.

---

## 14. Benchmark-driven roadmap

### v0 — establish the execution loop

Already scaffolded:

- MCP server skeleton,
- backend abstraction,
- in-memory backend,
- UNO adapter skeleton,
- workbook inspection,
- range read,
- range write,
- deterministic multi-operation execution.

Immediate goals:

1. connect to a real local Calc instance through UNO,
2. open a real workbook,
3. inspect it through MCP,
4. make a small modification through program execution,
5. run **one SpreadsheetBench 2 task end-to-end**.

Do not expand scope before this works.

### v1 — benchmark-driven world design

Add capabilities only when benchmark failures justify them.

Likely candidates, not commitments:

```text
formula-aware writes
used-region inspection
formula-region inspection
named ranges
sheet create/delete/rename
style and number-format inspection
dependency traversal
formula-pattern comparison
workbook recalculation
error scanning
charts/pivots
large rectangular writes
```

### v1.5 — interface ablation

This is potentially the strongest research contribution.

Compare the same external agent/model with:

1. thin / low-level tools,
2. semantic spreadsheet tools,
3. semantic tools + program execution.

Measure:

```text
task accuracy
modification score
tool calls
model turns
input/output tokens
execution time
program executions
failures/retries
rollback count (later)
```

Core hypothesis:

> **A thick semantic world plus temporary program execution is a better interface for spreadsheet agents than a thin tool surface.**

That is more intellectually interesting than “another LibreOffice MCP.”

### v2 — living models

Only after benchmark competence:

- transactions,
- snapshots,
- semantic diffs,
- rollback,
- perturbation validation,
- provenance/lineage,
- recurring workbook maintenance.

### Later

- Writer,
- Impress,
- Draw,
- cross-document artifact graph,
- workspace-wide propagation,
- multi-agent editing,
- richer governance/scope systems.

---

## 15. User stories that justify the domain

The strongest framing is not “who wants AI in spreadsheets?”

It is:

> **Which workflows live in spreadsheets because they are structured enough to compute, but too bespoke or fast-changing to justify custom software?**

Those are natural just-in-time-programming use cases.

Examples:

### Monthly workbook maintenance

```text
Take last month's workbook and this month's raw exports.
Update the workbook while preserving its methodology.
Incorporate new categories correctly.
Do not silently change calculation definitions.
```

The agent may need to:

```text
inspect workbook
understand data/model structure
inspect new files
synthesize update program
execute modifications
recalculate
validate
show semantic diff
```

This may be more commercially interesting than greenfield workbook generation.

### Spreadsheet debugging

```text
This 20-sheet forecast is wrong. Find out why and repair it.
```

A good agent world enables generated diagnostic programs that traverse formula dependencies, compare neighboring formula patterns, and locate anomalies.

### Build a living workbook from raw data

```text
Turn these raw exports into an inspectable model with source data,
transformations, metrics, formulas, and charts.
```

The result should remain modifiable and dynamically correct.

### Reconciliation

```text
Reconcile these ledger, billing, and bank exports.
Explain every unmatched item and preserve the reconciliation model.
```

### Scenario/model modification

```text
Add an acquisition/downside/new-pricing scenario to this existing model
without breaking its current cases.
```

These are not necessarily v1 implementation targets; benchmark tasks should decide immediate work.

---

## 16. The most promising commercial distinction: maintain, not just create

Creating a new workbook from scratch is useful but increasingly commoditized.

A harder and potentially more valuable task is:

> **Understand an unfamiliar existing workbook, modify it correctly, preserve its invariants, and leave an auditable change history.**

Real workbooks are messy, old, partially documented, and economically important.

The agent needs:

```text
INSPECT
   ↓
UNDERSTAND
   ↓
MODIFY
   ↓
VERIFY
```

That is where a thick domain world may outperform generic code generation.

---

## 17. What current benchmarks do NOT fully cover

These are deliberate future opportunities, not excuses to expand v1.

### Version control / transactions

Benchmarks generally evaluate final output, not whether the user can inspect, approve, reject, or roll back an agent's semantic changes.

### Provenance

They usually do not ask:

```text
why does this cell exist?
which program created it?
which input produced it?
which run changed it?
```

### Longitudinal maintenance

Most tasks look like:

```text
input workbook + instruction → output workbook
```

They do not strongly test repeated month-over-month maintenance.

### Semantic invariants

Examples:

```text
Assets = Liabilities + Equity
forecast starts after historical period
calculation ranges contain no hard-coded constants
approved source tabs are the only upstream data
```

### Multiple valid implementations

Golden-file evaluation may penalize a structurally different but semantically valid solution.

Longer term, specification/postcondition-based verification may be more appropriate.

### Cross-document propagation

Spreadsheet benchmarks stop at the workbook boundary.

They do not test:

```text
Calc metric changes
    ↓
Writer claim becomes stale
    ↓
Impress chart/slide becomes stale
```

This is part of the larger office-artifact vision, intentionally deferred.

---

## 18. Longer-term LibreOffice office-world vision

LibreOffice's modules can eventually be treated as different semantic sub-worlds:

```text
Writer   → narrative / document world
Calc     → computational / data world
Impress  → presentation / argument world
Draw     → spatial / diagram world
Base     → relational information world
Math     → notation capability
```

UNO provides the low-level shared programmable substrate.

The interesting layer would sit above UNO and expose **agent-native semantics**, not simply mirror the raw object model.

A future stack might be:

```text
LLM-generated program
        ↓
knowledge-work / office IR
        ↓
office-semantic primitives
        ↓
UNO
        ↓
LibreOffice
```

The longer-term office use case that emerged in discussion was essentially a **build system for knowledge work**.

Instead of unrelated files:

```text
raw_data.csv
forecast.ods
quarterly_report.odt
architecture_diagram.odg
board_deck.odp
```

we could eventually maintain an artifact graph:

```text
source
  ↓
transformation
  ↓
metric
  ├──→ chart
  ├──→ Writer claim
  └──→ Impress slide
```

Then changing a source can identify stale downstream artifacts.

This is powerful but **explicitly outside the current Calc-first scope**.

---

## 19. Why LibreOffice is useful even if Microsoft owns the commercial office world

Microsoft has a major strategic advantage because it owns a rich, permissioned office world: Excel, Word, PowerPoint, Outlook, Teams, SharePoint, OneDrive, Graph APIs, enterprise identity, etc.

But LibreOffice is a strong experimental substrate because:

- it is open source,
- UNO exposes a substantial programmable object model,
- external programs can control it,
- the project can build an abstraction above UNO without forking LibreOffice,
- we can explore agent-native office languages independently of any proprietary model or UI.

The project should therefore be thought of as:

> **an agent-native spreadsheet runtime / world**, with LibreOffice Calc as the first backend.

Not:

> “AI for LibreOffice.”

If the abstraction is good, other backends could theoretically exist later.

---

## 20. Research lineage / projects worth knowing

These are related to the broader paradigm. They are context, not implementation requirements.

### Code as agent action

- **CodeAct** — executable code as an agent action representation; relevant to why temporary programs can outperform long sequences of individual tool calls.
- **ViperGPT** — visual reasoning through LLM-generated programs over a bounded API.
- **Code as Policies** — robot policies generated as code over perception/control primitives.

### Generated skills/tools

- **Voyager** — Minecraft agent generating executable skills and storing successful ones for reuse.
- **LLMs as Tool Makers (LATM)** — LLM-generated utilities/tool creation.
- **CRAFT** — generation, validation, abstraction, and reuse of tools.

These motivate a later question:

> When should a temporary synthesized program become a persistent reusable skill?

### Ephemeral / demand-generated applications

- **Apeiron / Amorphware** — recent work around demand-specific synthesized applications.
- **Ephemeral software** — emerging terminology for software synthesized for temporary intent rather than maintained as a permanent application.

### Data / analysis

- **Microsoft Data Formulator** — especially relevant: agentic/generated data transformations plus visualizations and reproducibility.

### Agent-specific languages / safe code execution

- **Quasar** and other restricted-code/DSL approaches — relevant to the eventual question of whether arbitrary Python is the correct execution language for generated programs.

The project does **not** need to reproduce these systems. They provide conceptual precedent.

---

## 21. The broader “world” heuristic

For future domains, the strongest opportunities seem to have:

1. **Bounded primitives** — a compact basis can be enumerated/typed.
2. **High compositionality** — combinations unlock far more tasks than primitives individually.
3. **Long-tail intent** — many useful requests are too bespoke to justify permanent features.
4. **Observable execution** — the runtime reports machine-readable outcomes.
5. **Verifiability** — results/postconditions can often be checked.
6. **Constrainable damage** — the world can make unsafe behavior unrepresentable or explicitly governed.

A useful informal heuristic is:

```text
Opportunity(World)
    ∝
Intent Diversity × Compositionality × Verifiability
----------------------------------------------------
Primitive Complexity × Side-effect Risk
```

The best phrasing discovered in discussion was:

> **High entropy of intent, low entropy of primitives.**

Spreadsheets and graphs both score well under this framing.

---

## 22. Scope compilation — broader future idea

In more open-ended environments such as web acquisition/scraping, a major problem is not merely execution but **bounding the world the agent is allowed to construct and operate in**.

A useful future decomposition is:

```text
fuzzy intent
    ↓
scope compiler
    ↓
information boundary
computation boundary
authority boundary
resource boundary
    ↓
program synthesis
    ↓
execution
```

Types of scope:

- **information scope** — sources, entities, freshness, domains, geography,
- **computational scope** — allowed transforms/inference,
- **authority scope** — what external state may be changed,
- **resource scope** — requests, time, tokens, cost.

This is highly relevant to the broader research direction and to the separate graph-governance project, but **not part of LibreCalc v1**.

---

## 23. Current repository architecture

Current structure:

```text
librecalc-mcp/
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
├── docs/
│   ├── PROJECT_CONTEXT.md
│   ├── architecture.md
│   ├── benchmark-plan.md
│   └── roadmap.md
├── pyproject.toml
├── scripts/
│   ├── install_into_personal_projects.sh
│   ├── smoke_uno.py
│   └── start_libreoffice.sh
├── src/librecalc_mcp/
│   ├── server.py
│   ├── domain/
│   │   ├── backend.py
│   │   └── models.py
│   └── backend/
│       ├── memory.py
│       └── uno.py
└── tests/
    └── test_memory_backend.py
```

Architectural rule:

> Domain semantics must remain independent of UNO details.

Code should depend on the `CalcBackend` abstraction. Only the UNO adapter should know LibreOffice-specific API details.

Why:

- test without LibreOffice,
- keep semantics stable if UNO is awkward,
- possibly compare backends later,
- make the agent world the real product/research artifact.

---

## 24. Current v0 tool surface

The initial executable surface is intentionally tiny:

```text
calc_health
workbook_inspect
range_read
range_write
program_execute
```

Do not treat this list as the final language.

It exists to establish the loop.

`program_execute` is the first experiment in amortizing tool/model round trips through deterministic programmatic composition.

No arbitrary model-supplied Python execution in v0.

---

## 25. Exact next steps when resuming

**Superseded by §0.** Historical resume notes below; do not follow them over the current handoff.

### Completed foundation

Local UNO inspection, reading, deterministic multi-operation editing, recalculation, save-as,
formula translation, and real-workbook tests are working. The isolated SpreadsheetBench 2 harness
keeps golden workbooks outside agent authority, refreshes results with LibreOffice, and records
official scores, trajectories, calls, tokens, time, and provider cost.

On development task `Template:02_05`, Kimi K2.5 completed an exact-scoring workbook in four turns
for `$0.005702530` using `semantic-snapshot-v2`, overview-only reads, semantic diff verification,
and compact formula blocks. This proves the loop; it does not establish general benchmark quality.
See `docs/benchmark-plan.md` for the complete experiment record.

### Step 1 — freeze the successful configuration

Treat the exact canary as a fixed transfer configuration. Do not tune on `02_05` again and do not
promote task-specific debt-waterfall semantics into LibreCalc.

### Step 2 — use the completed transfer result

The frozen K2.5 configuration produced a non-exact `235/280` result on `Template:01_02`. A
LibreOffice formula-separator defect accounted for nine cells; the already-paid action replayed
through the fixed runtime scored `244/280`, leaving substantive accounting-sign and carry-forward
reasoning errors. Treat `01_02` as development-only from this point onward.

### Step 3 — classify before changing

Use the official evaluator and trajectory to classify any miss as observation, target selection,
reasoning, execution encoding, recalculation, verification, or harness failure. Distinguish exact
facts from heuristic candidate gaps.

### Step 4 — let repeated failures choose the next primitive

Do not brainstorm broad APIs first.

Examples:

```text
can't find relevant region
→ improve workbook structural inspection

can't understand formula relationships
→ add formula/dependency inspection

requires hundreds of writes
→ improve program language / bulk operations

writes wrong locations
→ improve semantic target representation

breaks workbook on edit
→ add validation / transaction mechanism
```

Then rerun.

### Step 5 — expand evidence carefully

Proceed one task at a time only after the error-observation improvement is tested offline. Formula
blocks remain a narrow primitive for patterned formulas; financial-model and debugging tasks may
justify dependency inspection or other orthogonal operations. Compare overview-only and
progressive reads only where a task contains genuine unresolved local ambiguity.

Calculated formula errors are now explicit in range reads, semantic observations, and semantic
diffs, with memory and real-UNO coverage. The next step is to create a small development difficulty
set, establish a clean exact upper anchor per task, and descend through cheaper models only where
that anchor succeeds. K2.5 is exact on development task `02_05`; Gemini 3.7 Flash exhausted its
reasoning budget without writing, and the Flash Lite probe was invalidated after a wrong input path
exposed a now-fixed runtime crash.

The first clean difficulty probe, `Template:01_01`, found the current threshold. Kimi K2.5 failed
before mutation through either parallel-tool output or unbounded visible deliberation. Opus 5 with
low reasoning and one repair completed in five calls for `$0.344300000`, but scored 380/381 regression
and 72/87 modification cells. Its 16 misses all followed from carrying the tax loan at face value
instead of issue price and failing to reverse the DTA in year six. The execution surface worked; the
miss was domain/target reasoning with an inspection contribution. The runner now permits one bounded
format repair, and semantic snapshots retain 240-character notes so the DTA-reversal phrase is no
longer truncated. A strict table-corner signal for the known `Financial_Model:09_04` residual found
only 1 true modified-cell hit from 23 candidates across the 15-task public non-visual slice (4.35%
precision, 0.14% recall). Reject it as an automatic selector. Continue with an unchanged-interface
upper-anchor run on `09_04`; do not tune further on `01_01` yet.

That `09_04` attempt exposed observation scale and transport failures. The 2.58 MB input caused the
old semantic inspection to reopen the workbook eight times and time out after one `$0.012135` Opus
call. `CalcBackend.read_ranges` now batches independent reads; UNO error checks touch formula cells
only. Structure-first inspection dropped from 126.3 seconds to 4.0 seconds and produced 49.8 KB;
semantic v2 is now 42.9 seconds but still 5.77 MB and is unsuitable as the initial observation under
the 100 KB harness limit. Structure-first correctly localized all requested task areas, but Opus
repeatedly emitted parallel focused reads and spent `$1.151565` across eight calls without creating
a workbook. The trace is invalid as a model score.

`calc_read_ranges` now exposes several explicit sheet/range reads as one deterministic tool call and
one workbook open. Its real-UNO smoke test read the three relevant Pepsi regions in 1.79 seconds and
11.4 KB. The runner records a 180-second per-command timeout for large comparisons and performs a
conservative pre-request budget check. Do not use Opus again during tooling development; resume with
a cheap tool-capable model after these fixes.

Cheap validation separated transport from model policy. Kimi K2.7 Code correctly used the batch
reader, localized every requested region, and inferred the ordinary target formulas, but exhausted
its output on deliberation at both low and minimal reasoning (`$0.079998630` and `$0.076508670`) and
never wrote. Kimi K2.5 with reasoning disabled made eight valid tool calls for `$0.044540800`, but
used all seven turns after inspection on increasingly broad reads and never wrote. The batch tool,
single-tool provider boundary, timeout, and cost ledger are therefore useful and working; the
remaining failure is action selection plus an observation that is either too thin
(`structure-first-v1`) or too large (`semantic-snapshot-v2`). The runner no longer imposes a small
fixed response cap by default. It derives the largest safe allowance from the remaining hard dollar
and context budgets before each request, while retaining an explicit fixed cap for ablations.

A controlled Gemini 3.7 Flash `Template:02_05` rerun confirmed that the new policy is active: its
second response used 4,201 completion tokens, exceeded the old 2,048 ceiling, and attempted a write.
The model still produced two empty formula-block objects, so the `$0.008901750` run failed before
mutation. That malformed call revealed that nonzero Calc wrapper exits killed SWE-ReX's persistent
shell even after `calc_tool.py` emitted a structured JSON validation error. Benchmark wrappers now
normalize their process status and preserve the JSON error as an agent observation, allowing bounded
repair instead of turning an ordinary invalid action into a dead runtime.

---

## 26. Questions intentionally left open

These are important but unresolved by design.

### What should the generated language be?

Possible answers:

- deterministic JSON-like operations,
- restricted Python subset,
- custom DSL,
- typed AST/IR,
- declarative transformations.

Do not choose before observing benchmark tasks.

### How thick should primitives be?

Need empirical iteration. Avoid 1:1 UNO mirroring and avoid workflow-specific mega-tools.

### Which computations belong inside the workbook?

Use the rule: persistent spreadsheet meaning should be representable in the world; generic temporary computation can remain with the host agent.

### How should semantic diff/versioning work?

Deferred until write competence exists.

### When should a temporary agent program become reusable infrastructure?

Potential later research question, not v1.

### How should cross-document provenance work?

Deferred until Calc is strong.

---

## 27. Things we explicitly do NOT want to build right now

Do not add these unless the project scope is deliberately revised:

- custom LLM/fine-tuning,
- built-in chat UI,
- built-in web search,
- autonomous planning inside the server,
- generic pandas/NumPy replacement,
- Writer support,
- Impress support,
- Draw support,
- Base support,
- a full office-suite knowledge graph,
- generalized enterprise workflow automation,
- a web-scraping agent,
- full Git-for-spreadsheets implementation,
- bespoke finance intelligence,
- arbitrary Python execution because it is convenient,
- features that cannot be connected to benchmark performance or a measured architectural need.

---

## 28. The research claim we may eventually be able to test

A clean future experiment is:

```text
Same model
Same benchmark
Same workbook tasks

Interface A: thin low-level spreadsheet tools
Interface B: semantic spreadsheet tools
Interface C: semantic tools + temporary program execution
```

Then compare:

```text
accuracy
modification score
model turns
tool calls
tokens
latency
error rate
recovery ability
```

If Interface C materially improves performance/efficiency, the project provides evidence for the larger paradigm:

> **Agent capability depends not only on model quality, but on the semantic richness and compositional structure of the world it is given.**

That is the deeper reason to build this.

---

## 29. Short context prompt for a new agent/chat

If resuming somewhere that cannot read this full file initially, paste this:

> We are building `librecalc-mcp`, a benchmark-first, Calc-only MCP server that exposes LibreOffice Calc as a thick deterministic programmable world to external coding agents such as Codex/Claude Code. The MCP is not itself an agent: no LLM, web search, chat UI, or planner. UNO is only the backend; our project owns an agent-native semantic spreadsheet layer. We want both low-level inspection tools and one-call temporary program execution, because complex spreadsheet tasks should be synthesized as programs rather than hundreds of tool calls. We are optimizing v1 against SpreadsheetBench 2, using benchmark failures to discover the minimum useful primitive set. SpreadsheetBench/Verified are breadth regression suites; BlueFin is later for dynamic/living-model quality. Generic computation stays with the host agent; transformations that form persistent spreadsheet meaning should be representable in our world. Read `docs/PROJECT_CONTEXT.md`, `AGENTS.md`, `docs/roadmap.md`, and `docs/benchmark-plan.md` before making changes. The isolated harness, semantic snapshot/diff including formula errors, compact formula blocks, exact development canary, first transfer classification, and public Opus trajectory audit are complete. The official public examples are contaminated development data and include successful golden-workbook access, so competitive runs retain stricter one-input isolation. `Template:06_01` is also a confirmed defective-golden case: both Opus 4.6 and a clean Opus 5 run were penalized for generating correct formulas instead of six golden `=#REF!` cells. The immediate development ladder is `Template:01_01`, `Financial_Model:09_04`, and `Debugging:10_02`.

---

## 30. Relevant references / names to search

These were useful during the design discussion:

### Spreadsheet benchmarks

- SpreadsheetBench 2
- SpreadsheetBench / SpreadsheetBench Verified
- BlueFin

### LibreOffice

- LibreOffice UNO API / SDK
- LibreOffice Calc

### Agent/program synthesis context

- CodeAct
- ViperGPT
- Code as Policies
- Voyager
- LLMs as Tool Makers (LATM)
- CRAFT
- Apeiron / Amorphware
- Ephemeral Software
- Microsoft Data Formulator
- Quasar / restricted agent code execution

### Broader research/search terminology

- ephemeral software
- runtime program synthesis
- code-as-action / CodeAct
- end-user programming
- agent DSLs
- tool creation
- domain-specific languages for agents
- generative UI
- situated / situational software
- program synthesis from natural language

---

# Final principle

When unsure what to build next, return to this:

> **We are not trying to make Calc easier to chat with. We are trying to make Calc a good computer for an agent to program.**

And when scope expands:

> **First pass the benchmark. Then earn the abstraction.**
