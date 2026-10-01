# What makes a harness valuable

Evidence packet for a fresh discussion. 4 September 2026. Numbers below were re-read from stored `official_scores.json` and `ledger.jsonl` on this date, not copied from the HTML page this replaces.

This is not a design doc and not a ranking of “what matters.” It is the product, the two interfaces, and the measurements that exist, with the nuances that change how those measurements read. Governance (commit gates, refusal, “constraints on what can go wrong”) is recorded only where it was already measured; it is not the question this packet is for.

**Bounded to:** SpreadsheetBench 2 non-visual subset, 297 tasks (Template 97, Financial_Model 100, Debugging 100). Single-shot, gold-scored, no human in the loop. Principal model for the harness comparison: GLM 5.3 Flash. A frontier row already exists on our interface (GPT-5.6); it has no control cell.

---

## 0. How to read this

Three claims get confused and should stay separate:

1. **Same score.** Control 6/60 exact, ours 5/60. Statistically a tie at this sample size.
2. **Same behaviour.** Only 2 of those exacts are shared. The arms are not solving the same tasks.
3. **Stable competence profiles.** A harness that is *good at different things* would repeat those differences. On the one slice where we have repeats, it does not.

(1) is true. (2) is true as a description of one draw. (3) is the interesting hypothesis, and the available test of it fails. The rest of the packet exists so that sentence can be argued with, not so it can be treated as settled.

A fourth claim sits underneath all three: **exact is a cliff.** Several “unique exacts” are the other arm at modification 0.97–0.997. Dichotomising those as capability gained or lost is the metric talking, not the workbook.

---

## 1. What the product is

LibreCalc is an **agent-native programmable Calc world**, exposed through MCP. It is not a chat product, not an embedded agent, and not a Python library with a nicer API. The host agent (Cursor, Claude Code, Codex, SWE-agent in the benchmark) owns reasoning, planning, and any general computation. This repository owns a deterministic semantic interface to a live LibreOffice Calc workbook.

The intended split, from the architecture:

```text
natural-language intent
        │
        ▼
external coding agent          ← reasoning, shell, Python, web, files
        │  typed tool calls / short programs
        ▼
librecalc-mcp                  ← this repo
        │  domain types, observation, write policy
        ▼
UNO adapter
        ▼
LibreOffice Calc               ← state, formulas, recalc, charts
```

The MCP server makes no model calls. A domain is treated as a small virtual machine `(S, O, A, T, I)`: workbook state, observations the agent can request, primitive actions, Calc/UNO transition semantics, and invariants (the file remains a valid workbook, formulas are real formulas, etc.). The LLM is the compiler from fuzzy intent into programs over that machine.

That is a different bet from “give the model bash.” A shell is Turing-complete and semantically thin: the runtime understands almost none of spreadsheet structure. A curated interface is the opposite trade — less expressiveness, more meaning per call.

### 1.1 Why Calc, and what “world” is supposed to mean

A spreadsheet is already state plus computation. Cells hold values; formulas are executable relationships; references are a graph; `calculateAll` is the transition function. The agent loop the product is built for is:

```text
inspect → focused read → write formulas as formulas → recalculate → inspect again
```

The output is supposed to be a native workbook whose formulas still work when inputs change — not a sheet of baked numbers. That is the product claim, independent of any benchmark score.

v1 is intentionally narrow. Features get added when a repeated failure shows a missing world abstraction, not because they sound useful. Visualization (24 SpreadsheetBench tasks) is out of scope until chart UNO→Excel translation is measured. Writer/Impress/Draw are later.

### 1.2 The instruction set the agent actually sees

The product MCP surface (`src/librecalc_mcp/server.py`) is small: `calc_health`, `workbook_inspect`, `range_read`, `range_write`, `program_execute`. The benchmark agent sees a SWE-agent wrapping of the same world, with names used throughout this packet:

| Tool | What it is |
|---|---|
| `calc_inspect` | Progressive observation. No target sheets → compact all-sheet manifest. Named sheets → labels, structure, formula patterns (or anomalies, on Debugging). |
| `calc_read` / `calc_read_ranges` | Addressed rectangular reads through Calc. `calc_read_ranges` batches several independent sheet/range requests in one workbook pass. |
| `calc_fill_formulas` | The compact write path. Each block is `{sheet, range, top-left formula}`; relative A1 references are translated across and down the range the way Calc autofill would, then the workbook is recalculated once and saved once. |
| `calc_program` | Mixed ordered batch: `write_range`, `set_formula`, `fill_formula`, `set_format`, `clear_range`, `create_sheet`, `insert_row`, `delete_row`, chart upsert/delete. Recalculate once, save once. |
| `calc_compare` | Deterministic semantic diff of input vs output: label/input/formula changes in full; recalculation effects as counts plus bounded representatives. |
| `submit` | SWE-agent finalise. Not a Calc primitive. |

`fill_formula` / `calc_fill_formulas` is the distinctive write primitive. It is not “write these strings into cells.” It is deterministic relative-reference translation (`src/librecalc_mcp/domain/formulas.py`), then a real Calc recalc. One block per patterned row or column replaces enumerating one-cell formulas.

`calc_compare` is the distinctive verify primitive, and it has a structural limit that matters for Debugging: it diffs output against input, so it reports the changes the agent intended and made. It cannot surface a change the agent did not know to make. That is not a bug in the tool; it is what a before/after diff is.

### 1.3 Observation is compiled, not dumped

`src/librecalc_mcp/domain/observation.py` is half the world. The agent does not receive a sheet dump. It receives a compiled view:

- **Structure / occupancy.** Used regions, labels, where populated runs stop (`column_extents` / `row_extents`).
- **Formula patterns.** Horizontal autofill runs of length ≥ 4, with the top-left formula and covered/unrepresented counts. Short or irregular formulas stay behind focused reads.
- **Formula anomalies (Debugging).** Numeric constants that look like they should be formulas, short gaps, error-token shortlists, deleted-row geometry. Explicitly heuristic. The prompt tells the model to confirm once, then write.
- **Boundary continuations.** One-cell date-run extensions of an existing formula, listed as candidates, not requirements.

Deterministic facts (labels, formulas, values, occupied regions) live in different fields from heuristic affordances (candidate gaps, translation shortlists). Heuristics are labelled as heuristics. Shipping a heuristic as a silent requirement is a known failure mode (the `fm-01-02-m3` note “Not requirements” vs an evaluator that wanted the extra date cell).

The frozen 297 configuration uses `formula-patterns-v1` + `formula-blocks-v1` on Template and Financial_Model, and `formula-anomalies-v1` + formula-blocks on Debugging. Progressive reads, with a **run-scoped read budget**: after inspect, at most one successful read batch; further reads return a structured write-now error. The read budget is a measuring instrument in `benchmark/`, not a product primitive. `enable_bash_tool: false` on our config. The prompt forbids Python/openpyxl/LibreOffice CLI edits because those bypass the interface being evaluated.

### 1.4 What the engine actually does that openpyxl does not

Writes go through UNO into a live Calc document, which recalculates, then saves. openpyxl can read and write the xlsx zip; it cannot evaluate formulas. A bash+openpyxl agent that writes `=SUM(A1:A10)` stores a formula whose cached value is whatever was already in the file (often empty). A LibreCalc agent that writes the same formula gets Calc’s computed value in the saved cache.

That engine difference is the one thing in the product that is not constructible from bash+Python without also invoking LibreOffice. The control prompt does mention LibreOffice as available. Whether the control arm actually uses it for recalc, rather than writing formulas with stale caches, has not been counted from trajectories in this packet.

### 1.5 What this is *not*

It is not a general spreadsheet copilot UI. It is not pandas. It is not a planner. The host already has those. The design rule on record: *the host owns arbitrary computation; this project owns computation that has persistent meaning inside the spreadsheet world.*

Hybrid (bash plus our tools in one agent) was built (`benchmark/sweagent/spreadsheet-hybrid.yaml`) and dropped. The comparison this packet is about is the official baseline versus the curated ISA, not a union of both.

---

## 2. The two interfaces under test

Both arms run inside the official SpreadsheetBench container, through SWE-agent 1.1.0, one tool call per turn, OpenRouter, the same isolated input/output paths, goldens off-limits until scoring.

### 2.1 Control — the harness the benchmark ships with

Config: `benchmark/sweagent/spreadsheet-control.yaml`. Copied from the official agent section; only the Docker deployment block is ours.

- Tools: `bash`, `view_xlsx`, `submit`.
- Environment the prompt names: pandas, openpyxl, numpy, LibreOffice.
- Recommended workflow: `view_xlsx` inspect → write a Python script → `python3` → verify → `submit`.
- Native budgets in the config: 50 calls. On the 60-task census run the dollar cap was $4. On the 15-task control runs it was $2.
- Observation: whatever `view_xlsx` dumps (list sheets, or content with optional row range), plus anything the model prints from Python.

This arm is Turing-complete. Anything our interface can do, a competent model can in principle reconstruct with bash and Python, given enough steps — except live recalc, which it can also reconstruct if it actually shells out to LibreOffice.

### 2.2 Ours — the curated ISA

Config: `benchmark/sweagent/spreadsheet.yaml` plus the librecalc tool bundle. Frozen 297 run (`glm-5.3-flash-nonvisual-297-1`):

- Model `z-ai/glm-5.3-flash`, reasoning `low`.
- 24 calls, $2, `token_limit_policy: remaining-budget` (the YAML file still contains a `max_tokens: 2048` default; the runner overrode it; the ledger records `max_tokens_per_call: None`).
- `formula-patterns-v1` on 197 Template/FM tasks, `formula-anomalies-v1` on 100 Debugging tasks.
- `formula-blocks-v1` execution both categories. `calc_program` is in the schema on Debugging because the frozen runner forwards the commit-gate overlay there; Template/FM writes go through `calc_fill_formulas`.
- Read budget on. Bash off.

The 15-task “ours” arm `glm-5.3-flash-librecalc-fifteen-1` was the same model at **12 calls**, `formula-patterns-v1` on all 15 including Debugging (so Debugging in that arm is not the frozen config). Do not mix that arm’s Debugging rows into a frozen-config comparison.

### 2.3 Budgets are not matched

| | calls | $ | tokens | read budget |
|---|---:|---:|---|---|
| Control 60 | 50 | 4 | remaining-budget | off |
| Ours 297 | 24 | 2 | remaining-budget | on |
| GPT-5.6 297 (ours) | **12** | 2 | remaining-budget | on |
| Control 15 | 50 | 2 | remaining-budget | on |
| Ours 15 | 12 | 2 | remaining-budget | on |

A later cut restricting the 60-slice to tasks where **both** arms used ≤24 model calls leaves 53 tasks. Exact is still 6 vs 5. Mean modification is still 0.7058 control vs 0.6346 ours. The headline gap is not an artifact of the six control tasks that ran long (those six: `Financial_Model:06_01` 25, `07_01` 26, `08_01` 33, `Debugging:06_02` 50, `08_09` 26, `10_05` 28).

The control sample was drawn after our 297 results were known: per category, task ids sorted, 20 taken at even spacing, 15 public-example tasks excluded. Fair for arm comparison. Not an independent estimate of our own accuracy.

---

## 3. How a run is scored

This section is load-bearing for whether the benchmark can reward the product.

1. The agent writes an xlsx to the output path, or it doesn’t.
2. `benchmark/score_openrouter_run.py` stages outputs and runs the official `evaluation/open_spreadsheet.py`.
3. That script opens every submitted workbook in LibreOffice, sets `doc.IsIterationEnabled`, calls **`doc.calculateAll()`**, and saves it back as xlsx. Stale or missing cached values are recomputed.
4. Unmodified `evaluation/evaluation.py` compares the refreshed output to the golden.

Exact is all-or-nothing per task. The evaluator also publishes **regression accuracy** (cells the golden leaves alone) and **modification accuracy** (cells the golden changes). The result JSON retains only the first error per task (`error_message` with `answer=`). That line is an evaluator leak; the pattern catalog is allowed to use it; it is not a golden dump.

**Implication, inferred from this pipeline, not yet A/B tested:** an agent that writes correct formulas with empty caches still scores as if it had recalculated, because step 3 does the recalc. The control arm is handed the engine advantage at scoring time. If that reading is right, SpreadsheetBench 2 as currently scored cannot reward the thing the product is built on — live Calc evaluation during the loop — except insofar as the agent *uses* those calculated values as observations mid-trajectory. Mid-loop observation of calculated errors/values is still ours. End-of-task correctness of formula results is not.

A census that reads the raw container output rather than the refreshed copy disagrees with official scores (historical figure: 59/121). After the census was pointed at the file the evaluator scores, agreement is 275/275 on the 297 rows that have a workbook, and 55/55 on both arms of the usable 60-slice. Anything computed against the raw file before 3 September is void.

Five Financial_Model `06_*` goldens surface as openpyxl `ParseError` / unbound `dc` prefix on `docProps/core.xml`. That is official evaluator behaviour, not a model miss. On the 60-slice, `Financial_Model:06_01` is 0.0/0.0 for control (namespace prefix), ours (no workbook), and GPT (unbound prefix). It contributes a shared zero and should not be read as anyone’s capability.

---

## 4. The finding: 6 and 5, only 2 shared

Identical 60 tasks, GLM 5.3 Flash, one draw each.

| | exact | rate | mean mod | mean reg | median calls | $ |
|---|---:|---:|---:|---:|---:|---:|
| Control (bash + openpyxl) | 6/60 | 10.0% | 0.6691 | 0.9706 | 13 | 0.51 |
| Ours (297 run, same 60) | 5/60 | 8.3% | 0.5758 | 0.9125 | 9 | — |
| GPT-5.6 on ours, same 60 | 13/60 | 21.7% | 0.7151 | 0.9810 | 6 | — |

Shared exacts, two tasks:

- `Template:06_21` — all three exact.
- `Template:08_03` — both GLM arms exact; GPT misses (sign flip at `IncomeProjection!C27`, mod 0.9286, reg 1.0).

Control only (4):

| Task | Control | Ours mod/reg | GPT |
|---|---|---|---|
| `Financial_Model:11_01` | exact | 0.9975 / 1.0 | exact |
| `Template:06_17` | exact | 0.9677 / (miss) | exact |
| `Template:13_08` | exact | 0.6667 | exact |
| `Template:15_01` | exact | 0.4286 | exact |

Ours only (3):

| Task | Ours | Control mod/reg | GPT |
|---|---|---|---|
| `Financial_Model:02_01` | exact | 0.9938 | exact |
| `Financial_Model:20_05` | exact | 0.9755 | exact |
| `Template:10_01` | exact | mod 1.0, **reg 0.9844** | same miss as control: regression at `EPS_Accretion!D39` |

Union of GLM exacts on this slice: 9 tasks. GPT recovers 5 of control’s 6 and 3 of ours’ 5, and adds 6 more that neither GLM arm hit (`Financial_Model:05_01`, `12_05`, `Template:02_05`, `05_02`, `06_12`, `07_01`). The only GLM exact GPT misses among the 9 is `Template:08_03` (both GLM) plus `Template:10_01` (ours only).

Read this table twice.

**First read (the interesting one):** the arms are not interchangeable. Control’s Template exacts `13_08` and `15_01` are not near-misses on our side (0.67 and 0.43). Our `Template:10_01` is a clean exact against a *shared* failure mode on control and on GPT-on-ours: modification perfect, one regression cell at D39. That is “we gain a task, we lose tasks,” not “same score so same thing.”

**Second read (the metric one):** `Financial_Model:11_01` (ours 0.9975) and `02_01` (control 0.9938) and `20_05` (control 0.9755) and `Template:06_17` (ours 0.9677) are one-or-few-cell differences promoted to opposite exact outcomes. On those four, “capability profile” is the exact cliff.

Both reads are in the data. Collapsing to either alone is the mistake.

Full 60-task grid is in §8.

---

## 5. Does the gain/lose pattern survive a repeat?

The test: if a harness has a competence profile, two runs of the *same* harness agree more than two runs of different harnesses.

The 60-slice has no control repeat. The test uses the 15-task slice, which does.

Eight GLM runs, same 15 tasks. Only three of the 15 are ever solved by anything. The other twelve are `.` in every column.

| Task | ctrl-1 | ctrl-2 | ours-lc | ours-str | C1 | C2 | C3 | D | 297 |
|---|---|---|---|---|---|---|---|---|---|
| `Template:06_18` | exact | exact | exact | exact | . | exact | exact | exact | exact |
| `Financial_Model:13_02` | exact | . | . | exact | . | exact | . | exact | . |
| `Financial_Model:20_05` | exact | . | exact | . | . | . | exact | . | exact |
| 12 others | . | . | . | . | . | . | . | . | . |
| **exact count** | **3** | **1** | **2** | **2** | **0** | **2** | **2** | **2** | **2** |

`C1`/`C2`/`C3` are three runs of one identical configuration (`glm-ladder-C-unbounded-*`). They scored 0, 2, and 2. C2’s extra exact is `13_02`; C3’s extra exact is `20_05`. Same config, the two Financial_Model hits anti-correlate.

Pairwise shared exacts on these 15:

- ctrl-1 ∩ ctrl-2 = **1** (`Template:06_18`)
- ctrl-1 ∩ ours-lc = **2**
- ctrl-1 ∩ ours-str = **2**
- ctrl-1 ∩ C2 = **2**
- ctrl-1 ∩ C3 = **2**
- ctrl-1 ∩ D = **2**
- ctrl-1 ∩ 297 = **2**
- C1 ∩ anyone = **0**
- ours-lc ∩ ours-str = **1** (only `06_18`)

On this slice, the control arm shares more exacts with our interface than with its own repeat. Arm identity does not predict which of the three solvable tasks fires.

A second variance measurement, one task, five repeats, identical config: `variance-c-02_05-glm-1..5` on `Template:02_05`.

| Repeat | exact | mod | reg |
|---|---|---:|---:|
| 1 | no | 0.85 | 1.0 |
| 2 | no | 0.85 | 1.0 |
| 3 | yes | 1.0 | 1.0 |
| 4 | no | 0.85 | 1.0 |
| 5 | yes | 1.0 | 1.0 |

2 exact, 3 miss. The miss is stable at mod 0.85 / reg 1.0 — so even the *partial* failure is a repeatable cliff on this task, and exact still flips.

**What this does and does not say about the 60-slice.** It says you cannot treat a single-draw exact *set* at a ~10% base rate as a competence profile, on the evidence of the 15. It does **not** say the 60-slice’s `Template:15_01` (ours 0.43 vs control exact) is noise; that gap is large, and we have no 60-slice repeat. The honest position is: the 2-shared pattern is real as a description of one draw; the 15-task test is why you should not build a theory of “our interface is for X, bash is for Y” from it without repeats or a metric with more dynamic range.

---

## 6. Category trade, which exact hides

On the same 60 tasks, mean modification by category:

| Category | Control mod / reg / exact | Ours mod / reg / exact | GPT-on-ours mod / reg / exact |
|---|---|---|---|
| Template (20) | **0.7345** / 0.9850 / 5 | 0.6087 / 0.9408 / 3 | 0.8950 / 0.9953 / 8 |
| Financial_Model (20) | 0.6742 / 0.9480 / 1 | **0.7225** / 0.9477 / 2 | 0.7492 / 0.9488 / 5 |
| Debugging (20) | **0.5986** / **0.9787** / 0 | 0.3962 / 0.8490 / 0 | 0.5012 / 0.9989 / 0 |
| All 60 | 0.6691 / 0.9706 / 6 | 0.5758 / 0.9125 / 5 | 0.7151 / 0.9810 / 13 |

Overall “control slightly ahead on exact, ahead on mod” is a mixture:

- **Template:** control better on exact and mod. This is where the 4-vs-3 exact split lives, and where two of control’s unique exacts are large gaps (`13_08`, `15_01`).
- **Financial_Model:** ours better on exact and mod. The two ours-unique exacts are control near-misses (0.9938, 0.9755).
- **Debugging:** nobody exact. Control is substantially better on both modification and regression. Ours *damages* more (reg 0.849 vs 0.979) and completes less of the repair (mod 0.396 vs 0.599). GPT-on-ours restores regression (0.999) and sits between them on modification (0.501).

If “we gain capability and lose capability” is going to mean something that isn’t the exact cliff, this is the more durable version: **our interface is not uniformly better or worse; it trades Template/Debugging modification for a small Financial_Model edge, at this model, on this slice.** That still wants a repeat. It does not require treating 6 vs 5 as a profile.

---

## 7. Model, on the same interface

Holding the harness at ours:

| | GLM 5.3 Flash 297 | GPT-5.6 297 |
|---|---|---|
| Exact | 24/297 = 8.08% | 59/297 = 19.87% |
| Template | 6/97 (6.19%) | 26/97 (26.8%) |
| Financial_Model | 18/100 (18.00%) | 33/100 (33.0%) |
| Debugging | 0/100 | 0/100 |
| Mean mod / reg | 0.5668 / 0.9205 | 0.8019·FM, 0.8480·T, 0.4006·D / 0.9490·FM, 0.9940·T, 0.9962·D |
| Median calls | 8 | 6 |
| Call cap | 24 | **12** |
| $ | 4.61 | 28.04 |
| Status | 277 completed, 20 failed | 297/297 completed |
| Missing outputs | 19 | 0 |

Nesting of exact sets: 19 of GLM’s 24 sit inside GPT’s 59. GLM-only five, with GPT’s score on the same task:

| Task | GPT mod / reg | GPT first miss |
|---|---|---|
| `Financial_Model:09_01` | 0.9772 / 1.0 | `Ratio_Analysis!F12` |
| `Financial_Model:20_02` | 0.9965 / 1.0 | `Balance Sheet Schedules!C32` |
| `Template:06_02` | 0.7692 / 1.0 | `WC_Forecast!D29` blank |
| `Template:08_03` | 0.9286 / 1.0 | sign at `IncomeProjection!C27` |
| `Template:10_01` | 1.0 / 0.9844 | regression `EPS_Accretion!D39` |

Three of five GLM-only exacts are GPT near-misses (mod ≥ 0.977). `Template:06_02` and `08_03` are real GPT misses. Capability mostly produces supersets. It does not always.

On the 60-slice, swapping model (5 → 13 exact) moves more than swapping harness at GLM (6 → 5), and more than the union of both GLM harnesses (9). That is a measured comparison with the harness held fixed. It is not a reason to ignore the 2-shared table; it is the size of the other lever.

GPT-5.6 has **no control arm**. The missing cell is GPT + bash. Nobody has it. The 19.9% is also a floor in one respect (12-call cap vs GLM’s 24) and a different reasoning setting (medium vs low). Do not quote it as a matched model comparison against the control 10%.

Published leaderboard context, not our runs: arito 45.46%, WPS AI 42.27%, Opus 4.6 + SWE-agent 34.89% overall, with Debugging at 12% for that Opus number. Our Debugging 0/100 is *our* gap relative to that published figure, not a benchmark-wide wall. See §10 for why that still does not make Debugging a harness comparison.

---

## 8. Scoreboards

### 8.1 Principal runs

| Run | Arm | n | exact | miss out | median calls | $ |
|---|---|---:|---:|---:|---:|---:|
| `glm-5.3-flash-nonvisual-297-1` | ours, frozen | 297 | 24 | 19 | 8 | 4.61 |
| `gpt-5.6-sol-nonvisual-all-medium-1` | ours, frozen | 297 | 59 | 0 | 6 | 28.04 |
| `glm-5.3-flash-control-census-sixty-1` | control | 60 | 6 | 0 | 13 | 0.51 |
| `glm-5.3-flash-control-fifteen-1` | control | 15 | 3 | 0 | 12 | 0.09 |
| `glm-5.3-flash-control-fifteen-2` | control | 15 | 1 | 2 | 8.5 | 0.10 |
| `glm-5.3-flash-librecalc-fifteen-1` | ours, 12-call | 15 | 2 | 2 | 8 | 0.08 |
| `glm-5.3-flash-strict-fifteen-unbounded-1` | ours | 15 | 2 | 0 | 7 | 0.14 |
| `glm-ladder-C-unbounded-1` | ours | 15 | 0 | 0 | 7 | 0.09 |
| `glm-ladder-C-unbounded-2` | ours | 15 | 2 | 0 | 8 | 0.10 |
| `glm-ladder-C-unbounded-3` | ours | 15 | 2 | 2 | 7 | 0.08 |
| `glm-ladder-D-raw-1` | ours | 15 | 2 | 1 | 13 | 0.14 |
| `glm-5.3-flash-catalog-control-eight-1` | control | 8 | 1 | 0 | 11 | 0.03 |
| `glm-5.3-flash-catalog-control-eight-2` | control | 8 | 0 | 0 | 11 | 0.08 |
| `glm-5.3-flash-catalog-ours-eight-1` | ours, frozen | 8 | 0 | 0 | 9 | 0.04 |
| `glm-5.3-flash-catalog-ours-eight-2` | ours, frozen | 8 | 0 | 0 | 9.5 | 0.03 |

72 stored runs have `official_scores.json`. Across every one of them: Template 310 attempts / 51 exact (16.45%); Financial_Model 295 / 61 (20.68%); Debugging **327 / 0 (0%)**. 66 distinct tasks have ever been exact; 0 of them are Debugging. Financial_Model 36, Template 30.

### 8.2 GLM 297 exact list (24)

`Financial_Model:` 02_01, 02_05, 03_05, 09_01, 09_02, 11_03, 11_04, 12_03, 12_04, 13_03, 16_01, 16_03, 17_02, 17_03, 19_03, 20_01, 20_02, 20_05.

`Template:` 06_02, 06_05, 06_18, 06_21, 08_03, 10_01.

### 8.3 Control 60 exact list (6)

`Financial_Model:11_01`, `Template:06_17`, `06_21`, `08_03`, `13_08`, `15_01`.

### 8.4 Per-task 60-slice (exact / modification)

`EXACT` means accuracy 1.0. Modification is the published scalar. Debugging omitted from this table because it is 20× miss × miss × miss; those rows are in the extract if needed.

**Template (20)**

| Task | Ctrl | Ours | GPT | c_mod | o_mod | g_mod |
|---|---|---|---|---:|---:|---:|
| 01_02 | miss | miss | miss | 0.9808 | 0.4038 | 0.2115 |
| 01_07 | miss | miss | miss | 0.9053 | 0.7789 | 0.7895 |
| 02_05 | miss | miss | EXACT | 0.6000 | 0.3500 | 1.0000 |
| 03_03 | miss | miss | miss | 0.1489 | 0.8723 | 0.8936 |
| 05_02 | miss | miss | EXACT | 1.0000 | 0.1591 | 1.0000 |
| 06_06 | miss | miss | miss | 0.9180 | 0.8033 | 0.9836 |
| 06_12 | miss | miss | EXACT | 0.6667 | 0.7333 | 1.0000 |
| 06_17 | EXACT | miss | EXACT | 1.0000 | 0.9677 | 1.0000 |
| 06_21 | EXACT | EXACT | EXACT | 1.0000 | 1.0000 | 1.0000 |
| 07_01 | miss | miss | EXACT | 0.6667 | 0.6667 | 1.0000 |
| 08_03 | EXACT | EXACT | miss | 1.0000 | 1.0000 | 0.9286 |
| 10_01 | miss | EXACT | miss | 1.0000 | 1.0000 | 1.0000 |
| 11_03 | miss | miss | miss | 0.6176 | 0.1765 | 0.9412 |
| 13_03 | miss | miss | miss | 0.1084 | 0.8554 | 0.8554 |
| 13_08 | EXACT | miss | EXACT | 1.0000 | 0.6667 | 1.0000 |
| 14_05 | miss | miss | miss | 0.6154 | 0.0615 | 0.6154 |
| 15_01 | EXACT | miss | EXACT | 1.0000 | 0.4286 | 1.0000 |
| 16_01 | miss | miss | miss | 0.7429 | 0.7714 | 0.9429 |
| 16_06 | miss | miss | miss | 0.7200 | 0.0000 | 0.7600 |
| 16_12 | miss | miss | miss | 0.0000 | 0.4792 | 0.9792 |

`Template:10_01` is the cleanest ours-only exact: both other columns have modification 1.0 and fail exact on the same regression cell. `Template:15_01` is the cleanest control-only hole on our side (0.43). `Template:05_02` is the reverse shape: control already has modification 1.0 and still misses (a regression cell), ours collapses to 0.16, GPT is the only exact.

**Financial_Model (20)**

| Task | Ctrl | Ours | GPT | c_mod | o_mod | g_mod |
|---|---|---|---|---:|---:|---:|
| 01_01 | miss | miss | miss | 0.3353 | 0.3353 | 0.4132 |
| 02_01 | miss | EXACT | EXACT | 0.9938 | 1.0000 | 1.0000 |
| 03_01 | miss | miss | miss | 0.9524 | 0.9559 | 0.9912 |
| 04_01 | miss | miss | miss | 0.8102 | 0.6300 | 0.8748 |
| 05_01 | miss | miss | EXACT | 0.7310 | 0.9853 | 1.0000 |
| 06_01 | miss | miss | miss | 0.0000 | 0.0000 | 0.0000 |
| 07_01 | miss | miss | miss | 0.1454 | 0.2289 | 0.3417 |
| 08_01 | miss | miss | miss | 0.6195 | 0.6389 | 0.9282 |
| 10_01 | miss | miss | miss | 0.5062 | 0.9221 | 0.9451 |
| 11_01 | EXACT | miss | EXACT | 1.0000 | 0.9975 | 1.0000 |
| 11_05 | miss | miss | miss | 0.9973 | 0.9806 | 0.9862 |
| 12_05 | miss | miss | EXACT | 0.8496 | 0.9115 | 1.0000 |
| 13_05 | miss | miss | miss | 0.6472 | 0.6472 | 0.6472 |
| 14_05 | miss | miss | miss | 0.7811 | 0.6636 | 0.7526 |
| 15_05 | miss | miss | miss | 0.2357 | 0.2398 | 0.1821 |
| 16_05 | miss | miss | miss | 0.9715 | 0.9505 | 0.9887 |
| 17_05 | miss | miss | miss | 0.8734 | 0.8734 | 0.8734 |
| 18_05 | miss | miss | miss | 0.9936 | 0.6497 | 0.9936 |
| 19_05 | miss | miss | miss | 0.0661 | 0.8391 | 0.0661 |
| 20_05 | miss | EXACT | EXACT | 0.9755 | 1.0000 | 1.0000 |

`06_01` is the evaluator/`docProps` zero, all arms. `11_05` / `16_05` / `18_05` are high-mod misses that exact will never distinguish without repeats.

**Debugging (20), all miss.** Modification still moves:

Control mean 0.5986 vs ours 0.3962 vs GPT 0.5012. Individual rows where ours is 0.0 and control is not: `02_06` 0.1739 vs 0, `04_01` 0.9899 vs 0, `05_02` 0.4545 vs 0, `06_02` 0.2857 vs 0, `08_04` 0.7812 vs 0. Ours ahead on `10_10` (0.6706 vs control 0.3411). The Debugging modification gap is not one outlier.

---

## 9. Causal census — what the mismatched cells are

Replay of the evaluator’s cell comparisons plus a causal classification, on the **refreshed** workbooks. 60-slice, 55 usable tasks (skipped: `Debugging:04_01`, `05_08`, `10_05`, `Financial_Model:06_01`, `Template:16_06` — no workbook or no causal payload). Census-to-evaluator agreement 55/55 both arms. Full 297 census: 275/297 `score_matches_stored` (the 22 non-matches are the no-workbook/failed rows).

**All 55, mismatched cell counts**

| Causal class | Control cells | Ours cells | Ctrl tasks | Ours tasks |
|---|---:|---:|---:|---:|
| downstream cascade at unchanged formula | 4986 | 5128 | 26 | 25 |
| regression cell over-edited | 7180 | 2676 | 30 | 27 |
| direct populated target: unchanged | 931 | 1001 | 20 | 19 |
| direct blank target: wrong edit | 888 | 743 | 24 | 29 |
| direct blank target: unchanged | 767 | 822 | 24 | 20 |
| direct populated target: wrong edit | 154 | 188 | 7 | 7 |
| dynamic-only regression over-edit | 43 | 58 | 8 | 9 |
| downstream cell over-edited | 14 | 1 | 2 | 1 |
| **total mismatched cells** | **14963** | **10617** | | |

The four “direct-target” classes sum to **2740 control vs 2754 ours**. That near-equality is real and easy to over-read. It says the arms miss a similar *number of direct targets*. It does not say they miss the same way, and it hides the rest of the table.

Cell-weighted vs task-weighted matters. Control’s extra ~4,300 mismatched cells are almost entirely `regression cell over-edited`, and almost entirely in Debugging:

**Debugging (17 usable)**

| Class | Control | Ours |
|---|---:|---:|
| regression cell over-edited | 5611 (75.6%) | 186 (6.7%) |
| downstream cascade | 663 | 1280 |
| direct populated target: unchanged | 903 (17/17 tasks) | 975 (**17/17 tasks**) |
| total mismatched cells | 7421 | 2781 |

Both arms leave the planted populated cell(s) untouched in **every** Debugging task in this sample. That is the population form of the `agent_scan` candidate (see §10). Control then over-edits thousands of regression cells on a subset of those tasks — enough to dominate *cell counts* while task-mean regression on the 20 Debugging tasks is still *better* for control (0.979 vs 0.849). A few huge over-edit workbooks inflate the cell total; the per-task mean does not.

**Template (19 usable):** ours does more `direct blank target: wrong edit` (261 vs 164, 13 tasks vs 9). That is the overfill / wrote-the-wrong-blank class, and it is the one Template signal that looks interface-induced rather than shared. Control leaves more blanks unchanged (104 vs 70).

**Financial_Model (19 usable):** dominated by cascade (4323 vs 3848). Regression over-edit is *higher* on ours (2466 vs 1509). Direct-target numbers are similar.

---

## 10. Debugging is a floor, not a harness comparison

327 attempts, every model, every harness, every config in the archive. Zero exacts.

Debugging is 100/297 of the benchmark. Including it in an exact-rate comparison adds a third of the mass at a ceiling of zero. The 8.08% and 19.87% would be 24/197 = 12.2% and 59/197 = 29.9% on Template+FM alone.

The deepest analysis in the repo was spent here: `formula-anomalies-v1`, the commit gate, `new_formula_error` at 91.8% precision (Sol) / 99.0% (K2.7), `uniformity_break`, the 17/17 “agent never touches the broken cell,” the `d-*` case series, `agent_scan`. Those measurements are real. They describe a category nothing in this archive has ever solved. They are not evidence that bash is better at Debugging *on exact*, because bash is also 0. They *are* evidence that bash gets further on modification (0.60 vs 0.40 on the 20) and damages less on task-mean regression (0.98 vs 0.85), while still not finding the planted cell (17/17 unchanged populated targets, both arms).

`agent_scan` as a candidate mechanism, not a lever: case `d-02-05-d7`. Control gets `WACC!D7` right in 2/2 catalog-control runs. Our arm’s read windows land next to D7 in 3/3 trajectories and never include it. The hypothesized mechanism is that bash+openpyxl lets the model load the workbook and scan every formula; our inspect/read interface never presents D7. One case. `arms.yaml` marks it `candidate`, not a family to build a tool from. The 17/17 census result is the population rhyme; it is still a floor (both miss the cell), plus a modification gap (control repairs more of the surrounding work anyway).

Published Opus Debugging at 12% means the category is not inherently at zero. Something about *these* agents, *these* interfaces, or *this* frozen Debugging policy (one confirmation read, formula-blocks, 5-call typical trajectory) is. Untangling those is a different experiment than “does the ISA beat bash on exact.”

---

## 11. Reliability is a model property

A previous page called our 15.5% never-submitted rate the cost of the interface. The GPT run on the same tools retracts that.

Trajectory heuristic (`"name": "submit"` actually issued, not merely present in the schema):

| Run | Submit called | Never submitted | `exit_format` in traj | Ledger failed / no workbook |
|---|---:|---:|---:|---:|
| GLM + ours (297) | 253 | 44 (14.8%) | 15 | 20 failed; 18 “no output workbook”; 2 timeouts; 19 missing_outputs |
| GPT + ours (297) | 294 | 3 (1.0%) | 0 | 0 failed; 0 missing; 5 evaluator `unbound prefix` (the `06_*` ParseError rows) |
| GLM + control (60) | 60 | 0 | 0 | 0 |

The 15 `exit_format` failures and the malformed-call deaths are GLM not emitting well-formed function calls. GPT drives the same `calc_inspect` / `calc_read_ranges` / `calc_fill_formulas` surface at a 1% skip rate. Control on GLM never fails to submit, at n=60.

Never-submit on GLM is concentrated in Debugging (26 of 44). That is the category whose frozen prompt pushes write-after-one-read, and the category where `exit_format` is 12 of 15.

GPT’s three never-submit tasks: `Debugging:07_03`, `Financial_Model:05_05`, `Financial_Model:15_03`. It still produced workbooks (ledger completed 297/297); SWE-agent autosubmit at the call cap can land a file without a `submit` tool call.

---

## 12. Efficiency, the axis that is not swamped

Median model calls, GLM, 60-slice: control 13, ours 9. On the 297: ours 8, GPT-on-ours 6. Mean calls 14.47 vs 10.08 vs 6.37.

Our arm reaches a statistically tied exact rate, and a worse overall modification rate, in roughly 60–70% of the turns. Nobody has treated cost-to-outcome as the headline. Unlike exact-set identity, call counts are not sitting on a 10% base-rate coin flip.

Caveats: budgets were not matched (50 vs 24 vs 12). Observation tokens per call are not equal (`view_xlsx` dumps vs compiled inspect). Dollar cost on the 60-slice is $0.51 for 60 control tasks vs $4.61 for 297 ours — not a paired cost comparison. Pair it before claiming cheaper.

---

## 13. What the pattern catalog already closed

Not the subject of this packet, but it is why “just look at first-misses and add a tool” is not an open road.

`python benchmark/catalog_gate.py` over 12 autopsied cases, n=2 per arm: **0 of 14 patterns survive.** Verdicts: 6 `shared` (control misses the same cell), 4 `noise` (our own repeats get the cell right), 1 `far` (too many other misses for the first miss to matter), 1 `refuted-lever` (`d-02-05-d7`, real arm delta, no live lever in the four families).

The four lever families were `information`, `constraint`, `substitution`, `selection`. `information` has a measured prior of zero exact conversions (commit-gate findings at 100% and 96.1% precision on the 297, converted nothing). A first-miss the control also misses is a model/task property. A cell we get right on repeat is variance.

That catalog is a closed collection. It does not answer “what makes a harness valuable.” It answers “these twelve first-miss stories are not a redesign backlog.”

---

## 14. Corrections to prior documents

1. **Never-submitted is not an interface tax.** Retracted in §11. GPT on the same tools submits.
2. **`max_tokens: 2048` vs uncapped is not what the principal runs did.** Both GLM 297 and the control 60 used `remaining-budget`. The YAML default is 2048; the ledger says `None`.
3. **“Bash appears in both configs” is not how you identify the GPT run.** Our YAML sets `enable_bash_tool: false`. The word `bash` appears in our trajectories because the prompt says not to emit it. The GPT 297 run is on `calc_inspect` / `calc_read_ranges` / `calc_fill_formulas`. Confirmed in every one of its 297 trajectories.
4. **Census must read the LibreOffice-refreshed copy.** Pre-3-September cell-level conclusions are void.
5. **n=15 exact is not a result.** On the record in `METHOD.md`. The 15-task grid in §5 is a variance instrument, not a scoreboard.
6. **275/275 means 275 scorable rows**, not 275/297. The 22 others have no workbook to replay.
7. **Direct-target 2740 vs 2754 is not “the arms fail the same.”** It is one slice of the census. Regression over-edit and Template wrong-blanks go the other way.

---

## 15. Open questions that are about harness value

Not a to-do list. Not governance.

**Q1. Does scoring erase the engine advantage?**
`open_spreadsheet.py` calls `calculateAll` on every submission. If control writes formulas and never evaluates them, the scorer still does. The remaining place the engine can matter is *mid-loop*: seeing `#REF!`, seeing a calculated total, deciding the next write from a live value. That is checkable from control trajectories (did they shell out to LibreOffice before submit?) and from an ablation that scores without the refresh. If the refresh is doing the work, this benchmark is the wrong exam for the product’s actual claim.

**Q2. Is the 2-shared table a profile, or a draw?**
The 15-task test says exact-set identity at 10% is mostly noise. The 60-task table still contains two large, directed gaps (`Template:15_01`, `Template:13_08` against us; `Template:10_01` for us, replicated as the same D39 regression on control *and* GPT). Repeating the 60 is the direct test. A cheaper proxy is repeating only those four tasks, n≥4 per arm, and seeing whether the large gaps hold. That is still a harness question, not a model question.

**Q3. Should comparison move to modification, or to Template+FM, or both?**
Exact at 10% with a zero-ceiling third cannot distinguish harnesses. Modification on the 60 already shows a category trade. Template+FM exact would be 6/40 vs 5/40 vs 13/40 — still noisy, but no longer diluted by 20 structural zeros.

**Q4. Is efficiency the claim?**
Fewer turns to a tied exact rate is the one harness difference that is not sitting on the exact cliff. It needs a matched budget and a tokens-per-task number, not just median calls.

**Q5. What would “valuable” mean if the baseline is Turing-complete?**
Anything we offer, bash can in principle reconstruct. Then a harness is valuable only if it changes *which* tasks get solved, or the cost of solving them, or the mid-loop observations the model cannot cheaply reconstruct (compiled structure, live error values, deterministic fill). Adding to the exact *count* by one or two, at this base rate, is indistinguishable from a different draw. Changing the set, stably, is the claim. This packet has a changed set on one draw, and a failed stability test on a smaller draw. That is the discussion.

What this packet deliberately does not open: adding tools from autopsies, commit-time refusal, two-phase submit, “the world should constrain what can go wrong,” rerunning 297, running a frontier control cell. Those are available; they are not required to have the conversation.

---

## Appendix A — Frozen GLM 297 category scores

From `glm-5.3-flash-nonvisual-297-1` `official_scores.json`:

| Category | exact | mean reg | mean mod | median mod |
|---|---:|---:|---:|---:|
| Template | 6/97 (6.19%) | 0.9680 | 0.6201 | 0.6667 |
| Financial_Model | 18/100 (18.00%) | 0.9181 | 0.7247 | 0.9206 |
| Debugging | 0/100 | 0.8769 | 0.3572 | 0.1222 |
| Overall | 24/297 (8.08%) | 0.9205 | 0.5668 | — |

GPT-5.6, same interface:

| Category | exact | mean mod | median mod | mean reg |
|---|---:|---:|---:|---:|
| Template | 26/97 | 0.8480 | 0.9649 | 0.9940 |
| Financial_Model | 33/100 | 0.8019 | 0.9849 | 0.9490 |
| Debugging | 0/100 | 0.4006 | 0.2713 | 0.9962 |

---

## Appendix B — Where the files are

- Runs: `benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter/<run>/official_scores.json` and `ledger.jsonl`
- Control 60 slice: `benchmark/slices/control-census-sixty.json`
- Control 15 slice: `benchmark/slices/control-arm-fifteen.json`
- Control config: `benchmark/sweagent/spreadsheet-control.yaml`
- Ours config: `benchmark/sweagent/spreadsheet.yaml`, tools in `benchmark/sweagent/librecalc/`
- Scoring: `benchmark/score_openrouter_run.py` → `evaluation/open_spreadsheet.py` (`calculateAll`) → `evaluation/evaluation.py`
- Census: `benchmark/mismatch_census.py`; paired dumps under the originating chat’s scratchpad `census297.jsonl`, `census_control60.jsonl`
- Catalog: `benchmark/pattern-catalog/` (`BRIEFING.md`, `METHOD.md`, `arms.yaml`, `catalog_gate.py`)
- Observation / fill / compare: `src/librecalc_mcp/domain/observation.py`, `formulas.py`, `diff.py`
- Product boundary: `README.md`, `docs/architecture.md`, `docs/PROJECT_CONTEXT.md` §3–6 (mental model; §0 is an operator log and will disagree with itself across dates)

---

## Appendix C — Known limits of this packet

- One draw per task on the 60. The variance test used a different, smaller slice.
- Control 60 dollar cap $4 vs ours $2; call cap 50 vs 24. Matched-call cut at 53 tasks does not flip exact or the mod gap.
- GPT 12-call vs GLM 24-call on the same interface; GPT reasoning medium vs GLM low.
- Trajectory “submit called” is a string heuristic. Schema mentions of `submit`/`bash`/`calc_*` are not call counts. Tool-presence-in-traj is not tool-use-count.
- `glm-ladder-D-raw-2` has no `official_scores.json`.
- Hybrid arm is dropped and not in these tables.
- Visualization tasks are out of scope.
- This packet does not re-derive the twelve catalog cases. If a discussion needs them, start from `benchmark/pattern-catalog/BRIEFING.md`, not from memory of chat.
