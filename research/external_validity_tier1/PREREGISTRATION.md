# Tier 1 external-validity replication — preregistration

Frozen before any scored model-in-the-loop run. No threshold, population,
prompt, cap, or decision-rule change is permitted after scoring begins.
Any deviation is reported as a protocol deviation, not a silent edit.

## 0. Lineage and authority

Controlling design (read before execution; design wins on any conflict with
working notes):

- branch `research/release-validity-planning`, commit `3a26ce1`:
  `research/release_and_validity/EXTERNAL_VALIDITY_PLAN.md`,
  `TIER1_REPLICATION_DESIGN.md`, `REOPEN_CRITERIA.md`, `LONGITUDINAL_PLAN.md`.

Study scale: 2 model categories x 12 tasks = 24 primary model-in-loop runs,
plus a deterministic replay/runtime layer that does not count toward the 24.

## 1. Frozen product control (Layer R baseline)

- product: `recalc-agent`, version `0.2.0`
- `master` = `f2db7ee97faa87331a2fb4e96b23f40cfa25d3e0`
- tag `v0.2.0` is an annotated tag whose commit target is `f2db7ee...`
  (tag object `747488b2e1da1ea87b3c63e7938e65030d3c1af3`).
- Replay installs the released 0.2.0 from the frozen tree and asserts
  `recalc-agent --version == 0.2.0` before scoring replay. rc5 is lineage
  only, never the Tier 1 control.
- No product code is modified on this branch. A genuine 0.2.0 correctness
  bug, if found, is isolated and reported separately; affected scoring stops.

## 2. Research harness freeze

Harness commit on this branch: `ceca61b226ca4864b8887560f8e83ea5ef5d0225`
("Tier 1 external-validity: harness, curated tasks, helper delivery, overlay").

Frozen file hashes (sha256):

| file | sha256 |
|---|---|
| `benchmark/sweagent/spreadsheet-control.yaml` (control prompt ancestor) | `c3cc1b506956bc73a9560716e739bfb2fb19d96477df540f3837d17c3cd53c3d` |
| `research/external_validity_tier1/spreadsheet-control-tier1.yaml` | `6247c74aa57ff0448f273cd7b2f8b09df9fd940209976ad51d82f80aab4f32d1` |
| `research/external_validity_tier1/helper_bundle/lx_helpers.py` | `f9c5cc270f93bdd1be529deab4c0d5f84b26cc9365050162729fae5b0094a179` |
| `research/external_validity_tier1/generate_curated.py` | `3b49a8244529d877255c6a61ba84348625f5cf3782d5f1489910a2416b3e7306` |
| `research/external_validity_tier1/evaluate_curated.py` | `e872c13b1785f60a3b86f10ae5555648356daa3c8d2f513efdf5ac20841124e5` |
| `_overlay/slices/tier1_slice.json` | `066d323e2f390e68e491950df5af06dad30fbb7d7176e41e76664efdda5e97de` |
| `_overlay/.../data/Curated_Tier1/dataset.json` | `49397b5d104d488f83395bfdaedab710d42f2923d218e34582731fcc3e5b5b2e` |
| SpreadsheetBench `data/Debugging/dataset.json` (ignored checkout) | `fb3441c0255a50f9e5e885c9c8dc952b109ba5673f712c181e5d7da7b1c682cc` |
| SpreadsheetBench `data/Template/dataset.json` (ignored checkout) | `e3d2942e1fab23ae0c90ad199d0cb43660027965593de810ff50f9ea67397e61` |
| SpreadsheetBench `data/Financial_Model/dataset.json` (ignored checkout) | `4edf2a8dd20384ef9d0fd1719d83ecbdb209b111ddfa9365c4ea0613b80ddf78` |

Agent container image: locally built `spreadsheetbench-v2:latest`,
image Id `sha256:b63a6cc2b95c97ee9f9da96ec1dcd80a0c06ed6825e497bc51471a56ffe69139`
(build recipe preserved as `Dockerfile.tier1.image`).

Tier 1 config = control config + exactly one frozen historical helper note
(`NOTE_C1` verbatim from `benchmark/ab_batch.py` at harness commit, plus a
one-line Tier 1 header). Verified file-level identical otherwise. Both model
categories see the identical prompt. Arm name: `control-tier1`.

Helper delivery: harness `--tier1-helper-bundle` stages the frozen bundle
read-only at `/root/tier1_helpers` with `PYTHONPATH=/root/tier1_helpers`,
asserting the expected sha256 (fail-closed). Verified: mount + import of all
six helpers inside the built image; control-without-flag path unchanged.

## 3. Models and run settings

Full record: `MODEL_MANIFEST.json` (this commit). Summary:

- Category P (frontier proprietary): `anthropic/claude-sonnet-4.5`
  (catalog ctx 1000000, tools supported).
- Category O (strong open-weight): `deepseek/deepseek-v3.2`
  (catalog ctx 163840, tools supported).
- Families (Anthropic / DeepSeek) are both outside the GLM/Spark lineage
  and distinct from each other. No sibling substitution is permitted.

Identical settings for both categories:

```text
temperature 0.0, top_p 1.0, tool_choice auto (one tool per turn enforced)
reasoning_effort unset (both in default non-thinking configuration)
--call-limit 50 --cost-limit 2.00 --timeout 3600 --execution-timeout 180
--max-requeries 2, --max-tokens unset (remaining-budget policy)
--control --tier1-helper-bundle <frozen> --tier1-helper-sha256 <frozen>
--benchmark-root <tier1 overlay> --config <tier1 config> --no-score
provider policy: OpenRouter default (allow_fallbacks=true,
  require_parameters=true); no provider pin because provider slugs are not
  exposed by the catalog API at freeze time.
```

Loose-cap rationale (per design: "loose regime (swe-agent-like) to avoid
budget-death confounding"): 50 calls matches the control arm's native budget;
$2.00/task binds only runaway trajectories (prior ordinary runs cost
~$0.04-0.51); 3600 s/task absorbs frontier latency at 50 calls. Caps bind
rarely by construction; any cap-terminated run is scored as observed (see §7),
never silently retried as provider-invalid.

Served-model audit: every generation id in each run's debug log is re-queried
via the OpenRouter generation API; the served `model` must equal the requested
model id on every generation. Any mismatch invalidates the run
(provider-invalid; retried per §7). Provider routing across endpoints serving
the same model id is permitted and recorded, not a substitution.

## 4. Task population (12 frozen)

Full record: `TASK_MANIFEST.json`, `WORKBOOK_MANIFEST.json` (this commit).

Controlled (mechanical rule from design: within each category, all
`dataset.json` ids ranked by `sha256(task_id)` hex ascending, lowest 2 taken;
no exclusions, no hindsight):

- `Debugging:07_01`, `Debugging:08_06`
- `Template:07_01`, `Template:03_02`
- `Financial_Model:11_05`, `Financial_Model:07_01`

Transparency note: `Debugging:07_01` is a member of the known contaminated
public-example set (`benchmark/slices/public-example-nonvisual-v1.json`). It
is retained because the selection rule is mechanical and Tier 1 is not a
benchmark-score study; contamination affects score validity, not
architectural-behavior observation. No absolute score from this study is
quoted as benchmark performance. The flag is recorded per task in
`TASK_MANIFEST.json`.

Curated (authored before model selection; strata fixed in the frozen
generator; instructions frozen in `curated/specs.json`):

- read: `Curated_Tier1:T1_R1`, `Curated_Tier1:T1_R2`
- mutation: `Curated_Tier1:T1_W1`, `Curated_Tier1:T1_W2`
- mixed: `Curated_Tier1:T1_M1`, `Curated_Tier1:T1_M2`

Fixed run order (interleaved; halves stratified). Task sequence:

```text
Debugging:07_01, Template:07_01, Financial_Model:11_05,
T1_R1, T1_W1, T1_M1, Debugging:08_06, Template:03_02,
Financial_Model:07_01, T1_R2, T1_W2, T1_M2
```

Each task runs Category P then Category O before the next task begins
(P,O,P,O,...). Runs 1-12 (first 6 tasks x both models) form the halfway
point: 3 controlled + 3 curated per model.

## 5. Smoke policy (unscored)

At most 2 unscored smoke runs on `Debugging:01_01` (not in the manifest) to
validate harness/container/network function. Smoke runs are never scored,
never enter ledgers except a one-line SMOKE note, and may not be used to
tune prompts, caps, or thresholds. If smoke fails for harness reasons, the
harness is fixed and this preregistration is re-hashed only if a frozen
value changed (any change is a protocol amendment, reported as such).

## 6. Correctness evaluation (frozen)

- Controlled tasks: the benchmark's official evaluation pack, run post-hoc
  on run outputs (in-run scoring disabled via `--no-score` for uniformity).
- Curated tasks: frozen `evaluate_curated.py` (sha above), whose golden
  self-check (6/6) and input-as-output negative control were verified
  before this preregistration.
- No evaluator is weakened to match historical results. `exact_success`
  and task score are recorded per run; scores are descriptive, never a
  model ranking.

## 7. Retry, invalid-run, and exclusion policy

Provider-invalid (retried, same cell, max 2 retries / 3 attempts):

- served-model mismatch on any generation;
- OpenRouter API outage / 5xx / rate-limit death with zero agent progress;
- docker/container or harness crash before agent completion;
- smoke-proven host fault (disk full, OOM of the harness itself).

Scored as observed (never retried as invalid):

- call/cost/time cap termination (behavioral outcome under loose caps);
- agent submit with wrong result; agent failure to submit;
- task-success variance of any kind.

Exclusion: a cell is excluded only if all 3 attempts are provider-invalid.
Target is 24 scored runs; every retry and exclusion is recorded in
`RUN_LEDGER.jsonl` with attempt numbers. Only the final valid attempt per
cell is analyzed.

## 8. Layer M (model-in-loop) measurements

Mining code is written after this preregistration and must implement exactly
these definitions. Raw trajectories/transcripts stay in ignored space; only
compact ledgers are committed.

Per run (`MODEL_BEHAVIOR.jsonl`):

- `submit_reached`, `task_success` (evaluator), `tool_calls`,
  `prompt_tokens`, `completion_tokens`, `cost_usd` (ledger + generation API).
- Surface use: AST counts over extracted python code of `load_workbook`,
  `iter_rows`/`iter_cols`, `ws[...]`, `.cell(`, `.value` reads, cell/formula
  writes, `save(`, plus non-openpyxl libs used. Ordinary-Python share =
  fraction of workbook-affecting operations issued as plain Python/openpyxl
  vs helper calls.
- Dynamic composition: counts of loops over sheet dimensions, computed
  coordinates/indices, cross-sheet computed references, ad-hoc search/filter
  loops, exception-driven probing. Plus a manual two-pass read of each of
  the 24 scripts recording operations awkward under the historical small IR
  (dynamic search, computed targets, conditional multi-sheet edits).
- Helper adoption (`HELPER_ADOPTION.json`): per helper family
  (inspect/search/periods; write_cells/write_formulas): eligible tasks
  (read family: every task; write family: tasks whose solution performs >=2
  cell/formula writes as judged from the trajectory), invocations
  (`import lx_helpers` + call), successes, outcome/resource association.
  The prompt announces availability only; any call counts as adoption
  (nothing is forced).
- Edit-plan behavior: spontaneous plan artifact present/absent (markdown
  plan block, stepwise comments, todo list) + outcome association.
  Observational only; no prompt requirement (a forced plan cannot measure
  natural adoption).
- Output census (`OUTPUT_CENSUS.jsonl`): per run, total stdout bytes of
  python/inspection tool outputs, cells traversed (conservative static
  bound: explicit cell accesses + iterator bounds), cells reflected in
  output, emission ratio, largest single observation in bytes.

## 9. Layer R (deterministic replay) measurements

For each run, the ordered workbook-affecting python command sequence is
extracted verbatim from the trajectory (file scripts and `python -c` /
heredoc executions; `ls`/`cat`/view/submit wrappers excluded). Replay:

- pristine task inputs; container path remap to local paths (recorded);
- paired same-window comparison: plain `python3` (BASE) vs released
  `recalc-agent 0.2.0` (RECALC) via the existing observer/receipt path;
- per command: exit code, stdout/stderr hash, output-workbook hash,
  Recalc route (DIRECT_RUNTIME / DIRECT_WITH_FALLBACK /
  REFERENCE_FAST_PATH), blocker family if non-direct, artifact
  build-vs-reuse, decode seconds, reference-parse seconds, full-command
  seconds.

Replay-eligibility: a command sequence is replay-valid iff it re-executes
deterministically from pristine inputs under BASE (same exit/output hashes
as the recorded trajectory modulo paths). `soffice`/LibreOffice commands
are replayed only if LibreOffice is present in the replay environment;
otherwise the sequence is marked `UNREPLAYED_EXTERNAL_TOOL` with reason.
Non-deterministic or host-dependent sequences are marked with reason, never
force-fitted. Claim D/E denominators are the replay-valid subset, reported
honestly with the exclusion ledger.

Second Linux environment: all replay-valid sequences are additionally
replayed inside a `python:3.11` container with 0.2.0 installed from the
frozen tree. Parity (exit/output hashes) must hold; timings are compared
qualitatively (gross pathology detection, not identity).

Primary host (recorded): Linux 7.0.0-34-generic x86_64, ext4,
Python 3.13.12, openpyxl 3.1.5, lxml 6.1.3.

## 10. Claim-specific decision rules

No model leaderboard is produced under any outcome. "Adoption AND benefit"
is required for every helper/abstraction reopening (per REOPEN_CRITERIA.md).

Claim A (ordinary Python surface): STRENGTHENED unless reopen evidence:
systematic openpyxl-mechanics failure (>=3 scripts failing purely on
mechanics, e.g. cannot express the operation) AND IR-awkwardness audit
showing a majority of scripts awkward under the historical small IR.
Descriptive reporting otherwise (surface share, dynamic composition rate).

Claim B (helper closures):

- Mutation/batch helpers (historical 0/13): REOPEN_FOR_CONFIRMATION iff
  natural adoption on >=3 eligible tasks AND paired outcome/resource
  benefit (adopting runs succeed where matched non-adopting runs fail, or
  measured cost/time reduction on the same task). Else STRENGTHENED
  (negligible adoption or no benefit); adoption-without-benefit holds the
  closure per the SQL-sidecar precedent.
- Inspection helpers (historical no arm-level gain): same adoption+benefit
  form (>=3 eligible tasks + benefit). Tier 1 has no no-note arm, so
  benefit is within-study association; a powered note-vs-no-note A/B is
  the Tier 2 confirmation, never a Tier 1 product claim.
- Edit plans (historical no authority/variance): REOPEN iff spontaneous
  plans appear on >=4/24 runs with clear paired benefit. Else STRENGTHENED.

Claim C (output sparsity): REOPEN (inspection-query thesis to Tier 2) iff a
model family shows dense dumping as a trait: family median emitted
observation bytes per task > 8 KB (order-of-magnitude reversal of the 479 B
historical median) AND emitted/traversed cell ratio > 25% on >=4 tasks of
one family. One verbose run is never sufficient. Else STRENGTHENED.

Claim D (sub-surface mechanical cost): structural judgment, no numeric
identity required. STRENGTHENED if replay-valid cost remains concentrated
in implementation mechanics (parse/decode/state/user-program execution)
with no missing agent-facing API implicated in >=3 scripts. REOPEN only on
concrete repeated need for a previously closed abstraction with benefit
evidence (same adoption+benefit discipline).

Claim E (direct-contract coverage): report route shares by all/controlled/
new/model-category. A coverage decline alone reopens nothing. Read-expansion
reopens (to Tier 2 measurement, never optimization) iff one unsupported
operation family concentrates >=1.0 s absolute reference-parse mass on the
new mix AND a credible narrow certification boundary is identified.

Claim F (failure boundary): each failed run forensically classified into
exactly one of: missing-evidence, runtime/mechanical, agent
reasoning/action, evaluation-ambiguity, budget/termination, UNRESOLVED.
Ambiguous cases are UNRESOLVED, never forced. Descriptive only; supports
the reasoning-residue interpretation only where deciding evidence was
demonstrably in model-visible context and the model chose otherwise.

Surveillance (demand census, no action): saves, reopens, mutation,
external recalculation, `data_only`, `iter_cols`, `.values`,
`values_only`, range literals, rich attributes, active/workbook
iteration, other blockers. Reopen forms: `data_only` iff >=3/12 tasks'
scripts use it AND a Tier 2 cache-semantics review passes; dependency
surface iff >=3 failures trace to one missing exact relation that
discriminates action; broader reads per Claim E.

Per-claim verdicts: STRENGTHENED / HOLDS_WITH_LIMITATION /
REOPEN_FOR_CONFIRMATION / NOT_TESTED_CLEANLY. No Tier 1 result becomes
PRODUCTIZE.

## 11. Halfway stopping check (after run 12)

`HALFWAY_DECISION.md` is written before run 13. Permitted outcomes:

- CONTINUE (default): finish Tier 1. Boring results are not a stop reason.
- EARLY_DIVERGENCE: only if >=2 claims already meet their full §10 reopen
  evidence bars on the halfway subset. Evidence is preserved; no mechanism
  work starts.
- INFRASTRUCTURE_INVALID: only if >=4/12 runs are provider-invalid after
  retries, or a harness defect makes cells non-comparable. Fix
  infrastructure only; no prompt/cap/threshold tuning on outcomes.

No prompt, cap, threshold, or population change is permitted at halfway
under any outcome.

## 12. Final study verdict

Exactly one of: EXTERNAL_VALIDITY_STRENGTHENED /
EXTERNAL_VALIDITY_MIXED / TIER2_CONFIRMATION_EARNED / STUDY_INVALID, per
the task §30 meanings. Individual claims keep their §10 verdicts. A
REOPEN_FOR_CONFIRMATION specifies: exact prior closure, new evidence, why
old evidence no longer suffices, affected population, estimated
mass/benefit, uncertainty, and the minimum Tier 2 confirmation. Tier 2 is
never started from this phase.

Thesis classification (STRENGTHENED / QUALIFIED / CHALLENGED /
NOT_INFORMATIVE) for "Preserve compositionality and semantic freedom at
the agent-facing surface; move mechanically exact complexity beneath it"
is driven by the §10 ledger, not by prior belief.

## 13. Cost and footprint accounting

Recorded: 24 primary runs + <=2 smoke runs; retries; provider-invalid
runs; tokens and API cost per run (ledger + generation API); replay
count; storage footprint. Hard ceiling: (24 + 2) x $2.00 = $52.00 model
spend. Trajectory/run bulk stays in ignored space (<100 MB discipline);
only compact ledgers are committed. Agent-code preservation avoids
provider secrets and private chain-of-thought; derived ledgers preferred.

## 14. Amendments

Any change to this document after hashing requires a dated amendment
section appended here, a re-hash, and a report of what (if anything) was
already observed at amendment time. Unexplained edits invalidate the
study (STUDY_INVALID).

### Amendment A1 (2026-10-03, user-directed Category O model change)

Change: Category O model `deepseek/deepseek-v3.2` is replaced by
`xiaomi/mimo-v2.6-pro` (catalog ctx 1050000, tools supported,
$0.000000435/$0.00000087 per token, endpoints DeepInfra/Novita/GMICloud/
Xiaomi). Category P (`anthropic/claude-sonnet-4.5`) is unchanged. All run
settings (§3) are unchanged for both categories. `MODEL_MANIFEST.json` is
updated to match; this document is re-hashed.

Observed at amendment time (12 DeepSeek-era attempt-1 runs + 1 smoke run):

- 6 Category P cells completed with outputs (exact scores/mechanics under
  analysis; no claim verdicts drawn).
- 1 DeepSeek cell completed (Debugging:07_01, partial credit).
- 5 DeepSeek cells provider-invalid (upstream 429/504 rate limits and a
  LiteLLM↔Friendli `thinking_blocks` 422; terminating event
  provider-caused in all cases; 1-9 calls each).
- Served-model audit instrument correction: OpenRouter reports
  fully-qualified snapshot ids (not separate catalog models); audit
  equates same-author/same-token-set ids and records raw served ids
  verbatim. Verified no sibling substitution in any run.

Disposition (frozen by this amendment):

- All DeepSeek-era cells are EXCLUDED from primary analysis and reported
  as superseded data. The completed DeepSeek cell is not a Category O
  observation.
- All 12 Category O cells are (re-)run with `xiaomi/mimo-v2.6-pro`.
  Mimo run names take the form `tier1-r{NN}-O-mimo-{task}` (retries append
  `-b`, `-c`); primary-analysis miners filter on ledger `model` identity,
  never on run-name patterns.
- Category P cells stand as run (6 done, 6 to run).
- Resumed run order: Mimo O cells for first-half tasks first (cells
  02/04/06/08/10/12), then the halfway decision, then second-half tasks
  in P,O order (cells 13-24).
- Halfway point redefined: 6 P first-half cells + 6 Mimo O first-half
  cells. Halfway rules (§11) are otherwise unchanged.
- Retry/exclusion policy (§7) applies to Mimo cells unchanged (max 2
  retries per cell).
- Cost ceiling unchanged ($52.00). DeepSeek-era spend (charged $1.555,
  of which $0.72 is the documented r04 key-attribution artifact;
  generation-API $0.180) stays in cost accounting as superseded spend.

Rationale: user-directed model change; the DeepSeek provider path showed
heavy upstream rate limiting (5/6 cells provider-invalid), and the user
selected the Xiaomi open-weight replacement. The Category O role
(strong open-weight, distinct from Anthropic and GLM families) is
preserved. No claim threshold, task, prompt, cap, or decision rule is
altered by this amendment.

### Amendment A2 (2026-10-03, user-directed study reshape: P frozen at 6)

Change: no further Category P (Claude) runs. The 6 completed P first-half
cells stand as the full Category P evidence. Category O (Mimo) runs all
12 tasks. Primary study scale is therefore 6 P + 12 O = 18 runs (plus
replay layer), not 24. Amendment A1's DeepSeek dispositions are unchanged.

Observed at amendment time: same 12 DeepSeek-era attempt-1 runs as A1
(6 P completed, 1 DeepSeek completed + 5 provider-invalid, all DeepSeek
cells superseded). No claim verdicts drawn. No Mimo run had completed
(one Mimo smoke run in flight, unscored).

Disposition (frozen by this amendment):

- Category P evidence = the 6 first-half cells only
  (Debugging:07_01, Template:07_01, Financial_Model:11_05, T1_R1, T1_W1,
  T1_M1). No P cells on second-half tasks. This is a cost decision, not
  an outcome-driven selection: the 6 tasks are the preregistered first
  half, fixed before any result was seen.
- Category O evidence = 12 Mimo cells (all tasks). Resumed order: Mimo
  first-half cells first (02/04/06/08/10/12), then the halfway decision,
  then Mimo second-half cells (14/16/18/20/22/24).
- Model-family COMPARISONS (P vs O behavior differences) use only the 6
  matched first-half tasks. Within-model claims use each model's own
  denominator (P: 6 cells; O: 12 cells).
- Claim threshold restatement for unequal denominators (same bars,
  own-denominator counting): Claim B reopen iff adoption on >=3 eligible
  tasks WITHIN that model's cells + paired benefit; Claim C family-trait
  bar (>=4 tasks of one family + median > 8 KB) unchanged and still
  satisfiable for P (4/6) and O (4/12); Claim E/F/D surveillance
  denominators reported per model and pooled over replay-valid scripts.
- Halfway point unchanged from A1 (6 P + 6 Mimo O first-half cells);
  halfway rules (§11) unchanged.
- Retry/exclusion policy (§7) unchanged. Cost ceiling unchanged ($52.00);
  expected remaining spend is Mimo-only (<$1).
