# Tier 1 External-Validity Replication — Final Report

Branch: `research/external-validity-tier1`.
Frozen product control: `recalc-agent 0.2.0`, `master`/`v0.2.0` at
`f2db7ee97faa87331a2fb4e96b23f40cfa25d3e0` (verified, never modified).
Preregistration: `research/external_validity_tier1/PREREGISTRATION.md`,
SHA-256 `918bb53554a222c87d65ab54400d1b77788dad2600edc8d6b06bef0c5e891192`
(after amendments A1+A2; hash committed before scored runs).

## 1. Executive result

**Overall Tier 1 verdict: `EXTERNAL_VALIDITY_STRENGTHENED`.**
**Thesis classification: `STRENGTHENED`.**

18 primary model-in-loop runs (6 Category P + 12 Category O, per amended
design) plus deterministic replay of all 166 replayable python blocks under
released `v0.2.0` (×2 arms, 332 rows). No preregistered material reversal
occurred. Per-claim results: A `STRENGTHENED`, B `STRENGTHENED`,
C `HOLDS_WITH_LIMITATION`, D `STRENGTHENED`, E `HOLDS_WITH_LIMITATION`,
F `STRENGTHENED`. No closure earns `REOPEN_FOR_CONFIRMATION`; no Tier 2 is
earned; no product mechanism was implemented; `master` and `v0.2.0` are
untouched.

The two limitations are caveats, not reversals: (C) the O family emits
~10–20× more observation bytes than P with no measurable harm; (E) raw
natural-behavior direct coverage is modest (11% of blocks) with `data_only`
as the largest adjacent demand, still closed on cache-semantics risk.

## 2. Why Tier 1 exists

Recalc 0.2.0's architecture (ordinary-Python surface, closed helper/IR
family, narrow direct-read contract, external observer) was derived largely
from a GLM-family / SpreadsheetBench-derived regime. Tier 1 is a small
falsification screen asking whether those conclusions survive a changed
model family and task/workbook distribution — not a benchmark campaign and
not a leaderboard. Design authority:
`research/release_and_validity/TIER1_REPLICATION_DESIGN.md` (planning
branch `research/release-validity-planning` `3a26ce1`).

## 3. Frozen 0.2.0 baseline

- Product `recalc-agent 0.2.0`; `git rev-parse master v0.2.0` both
  `f2db7ee97faa87331a2fb4e96b23f40cfa25d3e0` (tag object `747488b`).
- `recalc-agent --version` → `0.2.0`; `doctor` smoke green at study setup.
- All Layer R replay runs released `v0.2.0` via `recalc_agent.runner.run`
  (paired BASE vs RECALC, same window, pristine inputs).
- No product file was modified on this branch (research-only branch).

## 4. Preregistration

`PREREGISTRATION.md` (+ `.sha256`, committed separately before scored runs)
froze: baseline, models, 12-task manifest, settings (temp 0.0, top_p 1.0,
tool auto, reasoning unset, 50-call / $2.00 / 3600 s caps), prompts, retry
and provider-invalid policy (upstream errors only; 3 attempts; exclusion
only on 3× invalid), measurements, reopen rules (adoption AND benefit;
concentrated family + material cost + credible boundary), halfway rules,
decision rules, and exclusions. Amendment A1 swapped DeepSeek → Mimo
(5/6 DeepSeek cells provider-invalid under rate limits; completed DeepSeek
cell excluded); amendment A2 reshaped to 18 runs (P frozen at first-half
6 cells, O runs all 12) for cost discipline. Both amendments hashed and
committed before further scored runs. No threshold changed after results.

## 5. Models and environments

| Category | Model | Cells | Served snapshot (audited) | Provider |
|---|---|---|---|---|
| P (frontier proprietary) | `anthropic/claude-sonnet-4.5` | 6 | `anthropic/claude-4.5-sonnet-20250929` | Amazon Bedrock |
| O (strong open-weight) | `xiaomi/mimo-v2.6-pro` | 12 | `xiaomi/mimo-v2.6-pro-20260921` | DeepInfra (7 runs) / Xiaomi (5 runs) |

Served-model audit (`SERVED_MODEL_AUDIT.jsonl`, re-ran in-session):
18/18 runs `VALID`, 325/325 generations match requested family (snapshot
ids equated per preregistered token-set rule; raw ids recorded), 0 query
errors, 0 substitutions. Model families are genuinely distinct (Anthropic
vs Xiaomi open-weight). Settings identical across categories. Primary
environment: Linux (container image `spreadsheetbench-v2:latest` for
model runs; host conda Python 3.13.12 / openpyxl 3.1.5 for replay;
container Python 3.11.10 / openpyxl 3.1.5; LO 26.x host vs 7.0.4.2
container — see §7 for the measured consequences).

## 6. Task/workbook selection

12 frozen tasks (`TASK_MANIFEST.json`, `WORKBOOK_MANIFEST.json`):
- **Controlled (6)**, mechanical rule (per-category lowest `sha256(task_id)`,
  no hindsight): Debugging 07_01/08_06, Template 07_01/03_02,
  Financial_Model 11_05/07_01 (SpreadsheetBench-2 provenance).
- **Curated (6)**, authored pre-model, 2 read / 2 mutation / 2 mixed:
  T1_R1/R2/W1/W2/M1/M2 (`curated/`, `specs.json`, frozen evaluators +
  golden files; input-as-output negative controls pass).
Stratified coverage: point reads, iteration, search, computed edits,
fallback behavior, saves, recalculation, merges, styles. No private
spreadsheets. Workbook hashes/sizes/sheets/formulas/merges recorded per
task. Comparisons P-vs-O use the 6 matched tasks (A2); claim bars use
own denominators per preregistration.

## 7. Study validity / exclusions

- Primary runs: 18/18 analyzable. Provider-invalid in primary: **0**.
  Superseded (excluded by A1, recorded): 5 DeepSeek provider-invalid +
  1 completed DeepSeek cell. Unscored smokes: 2 (1 P `exit_cost`, 1 O
  timeout). No hidden retries; every attempt is ledgered.
- Run exits: 8 `submitted` (7 exact + r16 + r24 non-exact), 6
  `exit_cost` (3 P cost-caps, r14/r18 50-call caps), 1 `exit_format`
  (r04), 3 wall-timeout kills r02/r06/r10 (rc 124, massive token
  throughput throughout — observed, not provider-invalid).
- Replay validity: 147/166 blocks replay-consistent (140 `VALID` +
  6 `VALID-both-failed` + 1 `VALID-unchecked-truncated`). The 19
  remaining blocks (17 steps) are individually triaged in
  `REPLAY_TRIAGE.json`, all verified environment/nondeterminism-only
  (LO wording/values/serialization, ls owner/date/perms, SIGPIPE
  timing, ASLR addresses, set ordering) except one documented
  harness limitation (r18 s29 shell for-loop, excluded from runtime
  aggregates) and one error-path-consistent SyntaxError step (r18 s12,
  included). Python-version gap (3.13 vs 3.11) attributes zero blocks;
  openpyxl is 3.1.5 on both sides.
- Correctness: existing evaluators reused; curated evaluators frozen
  pre-scoring. One frozen-evaluator strictness found (r24 dynamic flags
  vs static golden — recorded as evaluation ambiguity, NOT rescored).

## 8. Overall task outcomes

Exact success: **7/18** (P 3/6: R1/W1/M1; O 4/12: R1/M1/R2/W2).
Controlled stratum: 0/9 exact (P partials reg 0.99–1.0, mod up to 0.985;
O r16 reg 0.964/mod 0.955, rest no-output). Curated stratum: 7/9 exact
(r10 no-output on timeout-after-save; r24 15/30 evaluator-ambiguity).
This is task-outcome context, not a finding: Tier 1 tests architectural
conclusions, not scores, and the models are experimental axes (§17
reports behavior without ranking).

## 9. Claim A — ordinary Python surface: `STRENGTHENED`

Both new families naturally express spreadsheet work through ordinary
Python/openpyxl with heavy compositional machinery and zero demand for a
Recalc-specific abstraction:

- 191 KB of replayed agent python over 166 blocks: openpyxl throughout,
  plus pandas (`read_excel`, verification frames), `re`, `zipfile`,
  `subprocess` (LibreOffice orchestration), `shutil`, `pathlib`.
- IR-awkward operations (corpus totals, `OPERATION_CENSUS.jsonl`):
  284 search loops, 60 computed-coordinate uses, 60 cross-sheet
  patterns, 45 dimension loops, 7 try/except probes, 17 formula writes
  with computed strings, 351 cell writes, 20 saves.
- Every run composes multi-step pipelines (inspect → compute in Python
  → write → re-read/verify; unzip → grep → targeted python →
  LO-recalc → data_only re-read). r03's 600-line equity-method
  recomputation and r18's XML-surgery + LO verification pipeline are
  representative, not exceptional.
- The O-family XML-surgery workflows (r02/r04/r14/r16/r18: `unzip`,
  `grep -o` element patterns, regex cell surgery, `sed -i` on build
  scripts) route *around* openpyxl with plain Python/regex rather than
  demanding richer APIs — a compositional escape valve, the opposite of
  an abstraction demand.
- Spontaneous demand for a richer Recalc-specific abstraction: 0/18.

## 10. Claim B — helper closures: `STRENGTHENED`

Stratified by helper condition (D1), per `HALFWAY_DECISION.md`:

- Working stratum (12 O runs, container-verified all 6 helpers
  importable/callable): **0 imports, 0 calls** — despite 3
  write-eligible runs (r06/r10/r22) and universal search/inspection
  demand (agents hand-rolled every search with loops/regex/grep).
- Broken stratum (6 P runs): 2 spontaneous `search` calls (r01 s04, r05
  s02, both genuine search tasks — latent interest), both failed on D1
  (`ModuleNotFoundError: No module named 'benchmark'` at
  `lx_helpers.py:17`, verified in trajectories); 0 successes; both
  models continued in ordinary openpyxl without retry or workaround.
- Write-family helpers: 0 calls given 6 eligible runs (agents hand-roll
  all 351 cell writes + 17 formula writes, including exact outputs).
- Plan artifacts: 0 genuine in 18 runs (1 miner flag on r16 adjudicated
  FALSE POSITIVE: markdown bullets inside financial-analysis prose, no
  plan/todo wording anywhere — `HELPER_ADOPTION.json`).
- Reopen rule (adoption AND benefit): both prongs absent in the only
  stratum where benefit is measurable. Closure holds.

## 11. Claim C — observation/output sparsity: `HOLDS_WITH_LIMITATION`

The filter-before-emit structure holds in both families, with an
O-verbosity caveat (`OUTPUT_CENSUS.jsonl`):

- Median largest single observation: 5.4 KB. Python-observation totals:
  P median 3.3 KB / max 8.5 KB; O median 8.7 KB / max 154 KB (r18).
- Largest singles overall are *harness* `view_xlsx` serializations
  (65 KB r18 s02, 58.6 KB r07/r08) — requested by agents but serialized
  by the tool; r07/r08 then succeeded exactly. Largest *agent-python*
  singles: 32.5 KB (r18 s11), 27.1 KB (r06 s07) — all O, top-8 all O.
- Heavy O runs still filter: r18 traverses full sheets into *files*
  then greps/prints slices (11.6K emitted addresses of ~100K+
  traversed cells); r06 full-sheet iteration piped to `head -60`; r14
  full dumps sliced with `sed`/`grep`. Broad traversal feeds files and
  pipes, not context dumps.
- No run failed from context pressure: failures are call/time/cost/
  format; zero context-limit errors. r18's 5.7M prompt tokens
  accumulated over 50 calls (call-count cap, not context cap); P hit
  cost caps with the *smallest* outputs (inverse of the harm pattern).
- **Limitation**: O absolute verbosity is ~10–20× P with no measurable
  harm at these scales — a model-family caveat on the universality of
  "sparse". The reopen signal (systematic large emission AND measurable
  suffering) is not met: the suffering prong is absent.

## 12. Claim D — sub-surface mechanical cost: `STRENGTHENED`

Replayed cost stays in implementation mechanics below ordinary Python
(165 runtime-usable blocks, `RUNTIME_REPLAY.jsonl` + `REPLAY_TRIAGE.json`):

- Paired wall: BASE 122.8 s vs RECALC 125.3 s (Tier 1 is not a speedup
  claim; same-window controls only). Recalc-owned phases total ~3.6 s
  (reference parse 3.2 s + artifact load 0.3 s + hashing); the remainder
  is ordinary-Python execution: openpyxl loads/iteration, user search/
  compute logic, and LO subprocess waits.
- Admitted path served real volume: 13,989 direct reads + 9,302
  iteration cells + 349 iteration rows on 10 direct loads.
- No block's cost traces to a missing agent-facing operation.
  Non-admission blockers are designed-out categories (mixed read/write,
  dynamic uncertainty, escape, `data_only`, rich objects).
- Per preregistration this is structural generalization, not numerical
  identity with R7 percentages.

## 13. Claim E — direct-contract coverage: `HOLDS_WITH_LIMITATION`

- Routes (usable blocks): 146 `REFERENCE_FAST_PATH`, 10
  `DIRECT_RUNTIME`, 8 `DIRECT_WITH_FALLBACK` (fail-closed working as
  designed), 1 skipped. **18/165 admitted (11%; 13% of the 136
  read-only blocks)**, 8/18 runs touched, admitted wall 9.6 s.
- Single-blocker-family wall audit (reopen screen): static-uncertainty
  18.9 s/51 blocks (no static boundary possible — dynamic Python);
  `data_only` 14.5 s/11 blocks (boundary not credible: stale-cache
  ambiguity per the Phase-12 lineage — performance alone insufficient);
  write-ish 8.8 s/11 blocks (needs a mutation engine — out of scope);
  rich/worksheets ~1 s each. Uncertified iterator shapes NEVER appear
  alone (always co-blocked) → no read-expansion family earns reopen.
- Zero admission errors observed; unsupported forms fail closed.
- **Limitation**: raw natural-behavior coverage is modest — most natural
  agent code is mixed read/write + dynamic *by construction*, which the
  read-only contract targets away from by design. `data_only` is the
  largest adjacent demand and stays closed on semantic risk, not lack
  of demand. Decline-alone does not reopen per preregistration.

## 14. Claim F — failure boundary: `STRENGTHENED`

11 non-exact runs forensically classified (`FAILURE_BOUNDARY.jsonl`):

- **Reasoning/action with deciding evidence verified in context (5)**:
  r01 (all 7 M75 precedents observed; wrong formula), r03 (full sheet
  viewed 4×; wrong cash computation rewritten unchanged 4×), r05
  (near-miss with structural inputs observed; submitted on None-valued
  verification without obtainable recalc), r16 (voluntary submit; C14
  commission error with C14 observed), r04 (`exit_format` disengagement
  with evidence available and budget remaining).
- **Missing mechanical evidence: 0** — the key falsifier never appeared
  across 2 new model families.
- **Budget terminations without signal (5)**: r02/r06 (3600 s timeouts
  mid-investigation, 1.4M/2.1M token throughput); r10 (timeout *after
  saving output*, latency-driven, unsubmitted); r18 (50-call cap while
  on-track verifying correct values); r14 proximate cap (with
  misdirected-investigation underlying); r01/r03/r05 proximate cost-caps
  (with reasoning errors visible in partials).
- **Evaluation ambiguity (1)**: r24 wrote spec-compliant *dynamic* flags
  (`=IF(B<0,"NEGATIVE","OK")`, exactly the spec sentence; all 15 endings
  compute to golden values) but the frozen evaluator demands static
  golden strings. Recorded, not rescored per preregistration.
- The reasoning-residue interpretation survives: failures are
  model action/choice or budgets, never missing mechanical evidence.

## 15. New write/recalc/read-shape demand

Surveillance (`MODEL_BEHAVIOR.jsonl` + operation census; nothing
implemented):

- Saves: 20 across 18 runs; all fast openpyxl serializations, small
  wall share. No concentrated certifiable write family.
- External recalculation: 7/18 runs invoke LO (`soffice`/`libreoffice`
  binaries, D4-refined detection) successfully as agent-chosen
  orchestration — including r01-P. Waits are tolerated, never a failure
  cause. No demand for Recalc-owned calculation expressed or implied.
- `data_only`: 36 blocker instances; 11 single-family blocks / 14.5 s —
  largest adjacent demand, closed on cache-semantics risk (§13).
- `iter_cols`: 0 uses. `.values`/`values_only`/range literals: no
  material demand. Rich attributes: present as blockers, diffuse.
- Merges/dimensions/names/tables: read routinely inside reference
  execution; no API demand.

## 16. Replay/runtime results

- 166 blocks × 2 arms = 332 `RUNTIME_REPLAY.jsonl` rows (BASE plain
  `python3` vs RECALC `v0.2.0` via `recalc_agent.runner.run`), pristine
  inputs, remapped mounts, fresh-shell cwd model, block-level validity
  against recorded stdout.
- Validity: 140 `VALID` + 6 `VALID-both-failed` + 1
  `VALID-unchecked-truncated` = **147/166 (88.6%) replay-consistent**;
  19 MISMATCH blocks individually triaged and verified env-only
  (`REPLAY_TRIAGE.json`), plus 1 documented harness limitation
  (shell for-loop) and 1 error-path-consistent SyntaxError step.
- Replay-harness bugs found and fixed during triage (research tooling
  only, never product): `\ `-escaped `cd` targets, `-c` double-quote
  unescaping, `/dev/null` remapping, remap corruption of XML regexes /
  formulas / `/0` checks (prefix-only remap for python contexts),
  mid-chain `cd` tracking, output-redirect and `2>&1 |` modeling,
  catom-aware shell remap. 29 parse unit tests
  (`test_replay_parse.py`) guard the fixes.
- No `0.2.0` product bug found: every divergence attributed to
  environment (LO/owner/date/perms/Python-minor) or harness modeling,
  each verified case-by-case. Second-environment replay was not run
  (single-Linux limitation, §24); openpyxl pinned identical (3.1.5).

## 17. Model-family differences

Behavioral differences (no ranking — models are experimental axes):

- P imported helpers 2× (broken stratum, failed on D1); O never
  imported/called (0/12 working stratum).
- O emits ~10–20× more observation bytes (154 KB vs 8.5 KB max python
  total) and uses heavier tooling (XML-grep in r02/r04/r14/r16/r18,
  LO-recalc in 6/12 O vs 1/6 P).
- O shows intermittent empty tool calls (r02/r04/r06/r10/r14/r18 —
  generation quirk; fatal only in r04's `exit_format`); P shows none.
- O failures skew budget/format (6 failed-as-observed); P failures are
  cost-capped partials with high regression scores. Success counts are
  reported without leaderboard framing per preregistration.
- Core architecture-relevant behavior is IDENTICAL: ordinary-Python
  composition, zero abstraction demand, filter-before-emit, mechanical
  cost, reasoning/budget failures.

## 18. Controlled vs new-task differences

The stratum gap dominates task outcomes in both families (a regime
effect, not a model effect):

- Controlled (SpreadsheetBench debugging/modeling): 0/9 exact. P
  partials are strong (reg 0.99–1.0; mod 0.10/0.70/0.99); O r16 partial
  (reg 0.964/mod 0.955), rest no-output (budgets/format).
- Curated (authored read/mutation/mixed): 7/9 exact (P 3/3; O 4/6 with
  r10 timeout-after-save and r24 evaluator-ambiguity).
- Behavior is consistent across strata (ordinary Python, no helper
  uptake, filter-before-emit in both); difficulty differs, not
  architecture-relevant conduct. Direct admission touches both strata
  (8 runs span controlled + curated).

## 19. Halfway decision

`HALFWAY_DECISION.md` (committed at `49bba75`): **CONTINUE** after the
first 12 cells. Findings: D1 helper-staging defect (fixed; Claim B
stratified), no decisive reversal, no infrastructure invalidity.
DeepSeek rate-limit invalidity later triggered A1 (documented there).

## 20. Closure/reopen ledger

`REOPEN_LEDGER.json`: 11 closures assessed — 8 `STRENGTHENED`
(ordinary-Python surface, inspection/mutation helpers, plans,
sub-surface cost, read-scope, write ownership, recalculation
ownership, reasoning residue), 3 `HOLDS_WITH_LIMITATION` (sparsity,
direct coverage, `data_only`), 0 `REOPEN_FOR_CONFIRMATION`,
0 `NOT_TESTED_CLEANLY`. No Tier 2 confirmations earned.

## 21. Overall Tier 1 verdict

**`EXTERNAL_VALIDITY_STRENGTHENED`.** No preregistered material
reversal: no agent-surface reversal (0 abstraction demand), no context
reversal (no output-size harm), no coverage reversal (no concentrated
certifiable family), no mutation/recalc reversal (surveillance only),
no runtime reversal (contract + fail-closed behave as designed), no
failure-boundary reversal (0 missing-evidence failures). The C and E
items are recorded limitations with explicit evidence, below the
"important dependency" bar for `MIXED`: neither changes any
architectural conclusion.

## 22. Minimum Tier 2 design, if earned

None earned — this section is N/A by design. Had any closure earned
`REOPEN_FOR_CONFIRMATION`, the minimum Tier 2 would have been a
targeted confirmation on the reopened mechanism only (preregistered
adoption+benefit or demand+economic gates, new task sample, frozen
product control). No such study is authorized.

## 23. Implications for the Recalc thesis

> Preserve compositionality and semantic freedom at the agent-facing
> surface; move mechanically exact complexity beneath it.

**Classification: `STRENGTHENED`.** Two new model families — one
frontier proprietary, one open-weight — both program spreadsheets as
free ordinary-Python compositions (including escaping *around*
openpyxl into regex/zipfile/XML when it suits them), ignore offered
helpers even when working, absorb all cost in mechanical execution,
and fail on reasoning/budgets rather than missing machinery. The
evidence drove the classification in the thesis's favor on every
claim; nothing in Tier 1 qualifies, challenges, or leaves it
uninformative. The study was designed to be capable of all four
outcomes.

## 24. Limitations

- Only 2 added model categories; only 12 tasks; no real-user
  longitudinal evidence; Linux-only (second-environment replay not
  run); curated-task selection effects (see §18 stratum gap).
- P cells ran under the broken-helper stratum (D1): P's latent helper
  interest (2 calls) is unmeasurable for benefit; the working-stratum
  evidence is O-only (0/12).
- Replay is single-harness (one remap/cwd model, however verified:
  88.6% exact-output reproduction); pure-shell steps execute but are
  not output-compared; shell for-loops unmodeled (1 step).
- Budgets shape O failures (time/call caps) and P partials (cost
  caps); long-horizon convergence beyond caps is untested.
- Evaluators frozen: r24's dynamic-flag solution scores 15/30 under a
  static-golden comparison (recorded as ambiguity, correctly
  unscored-up).
- Model APIs/configurations drift over time; served snapshots recorded
  (`SERVED_MODEL_AUDIT.jsonl`) for provenance.

## 25. Recommended next program step

No mechanism work is earned. The recommended next step is the already-
planned longitudinal program (`LONGITUDINAL_PLAN.md`) — repeated-use /
persistence evidence — which Tier 1 explicitly does not substitute
(incidental repeated loads observed, e.g. save→reopen→verify cycles in
most runs, are not persistence evidence). If a future screen revisits
read coverage, `data_only` (11 blocks / 14.5 s) is the named adjacent
demand, gated on solving the stale-cache trust problem first — a
semantics project, not a performance project.

## Appendix A — Cost accounting

Model-in-loop spend (charged USD from run ledgers): P $3.48
(976K prompt + 36K completion tokens over 6 runs); O $5.76
(13.2M prompt + 915K completion tokens over 12 runs);
**total $9.25**. Retries: DeepSeek-era attempts superseded per A1
(all recorded); primary-cell retries: 0. Provider-invalid in primary:
0. Replay count: 332 block-rows + harness overhead (negligible).
Storage: compact JSONL ledgers committed (~1 MB total); raw provider
trajectories stay in ignored `_overlay/` + external run archives;
`/tmp/t1replay` scratch ignored. No spend beyond the preregistered
18-cell scale (plus 2 unscored smokes).

## Appendix B — Artifact index

All under `research/external_validity_tier1/` on branch
`research/external-validity-tier1`: `PREREGISTRATION.md` (+`.sha256`,
`918bb535…`), `MODEL_MANIFEST.json`, `TASK_MANIFEST.json`,
`WORKBOOK_MANIFEST.json`, `RUN_LEDGER.jsonl` (18, score-enriched),
`MODEL_BEHAVIOR.jsonl`, `OUTPUT_CENSUS.jsonl`, `CORRECTNESS_ROWS.jsonl`,
`HELPER_ADOPTION.json`, `SERVED_MODEL_AUDIT.jsonl` (18/18 VALID, 325
gens), `RUNTIME_REPLAY.jsonl` (332), `ROUTING_CENSUS.jsonl` (36),
`OPERATION_CENSUS.jsonl` (18), `REPLAY_TRIAGE.json`,
`FAILURE_BOUNDARY.jsonl` (11 + header), `CLAIM_RESULTS.json`,
`REOPEN_LEDGER.json`, `HALFWAY_DECISION.md`, `REPORT.md` (this file);
harness: `mine_layerm.py` (D2/D3/D4 corrected), `score_runs.py`,
`audit_served.py`, `replay_layer.py`, `test_replay_parse.py` (29
tests green), `generate_curated.py`, `evaluate_curated.py`,
`helper_bundle/`, `Dockerfile.tier1.image`, `spreadsheet-control-tier1.yaml`.

## Appendix C — Confirmations

- No product mechanism was implemented (research branch only).
- `master` (`f2db7ee9…`) and tag `v0.2.0` remain untouched (verified
  §3; no merge performed, none requested).
- No Tier 2 or persistence study was started (§22 N/A; §25 points at
  the pre-planned longitudinal program as future work only).
