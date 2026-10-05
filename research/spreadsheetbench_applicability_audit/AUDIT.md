# SpreadsheetBench-2 applicability audit

Research-only post-hoc descriptive subset summaries of the frozen Tier 1
external-validity study. No new experiments, replays, or model calls. No
historical verdict modified (`EXTERNAL_VALIDITY_STRENGTHENED` stands).

- Branch: `research/spreadsheetbench-applicability-audit`
- Frozen study commit: `7d0db1e5ceea511bbfe37f9a7c5796eb3773a2e4`
- Builder: `research/spreadsheetbench_applicability_audit/rebuild.py`
  (deterministic; streams frozen sources via `git show` from the pinned
  commit)
- Derived: `task_population.csv`, `invocation_ledger.csv`,
  `task_summary.csv`, `model_summary.csv`, `summary.json`
- `denominator_map.md`, `sources.md` (this directory)

## 1. Study population (task sections 1-2)

The frozen study ran 18 model-in-loop trajectories over 12 tasks
(preregistration + amendments A1/A2, all hashed before scoring):

- **Controlled stratum (6):** `Debugging:07_01`, `Debugging:08_06`,
  `Template:07_01`, `Template:03_02`, `Financial_Model:11_05`,
  `Financial_Model:07_01` — mechanical selection (per-family lowest
  `sha256(task_id)`, no hindsight), SpreadsheetBench-2 provenance,
  **original workbooks** (`original: true` in `WORKBOOK_MANIFEST.json`).
  The study's term is "controlled"; this audit's "SpreadsheetBench-2-
  derived subset" means exactly this stratum. "Derived" = selected from
  and run against SpreadsheetBench-2, not adapted: task IDs, instructions,
  and workbooks are the benchmark's own.
- **Curated stratum (6):** `Curated_Tier1:T1_R1/R2/W1/W2/M1/M2` (2 read /
  2 mutation / 2 mixed), authored pre-model with frozen evaluators.
  Excluded from this audit's subset.

Trajectories: Category P (`anthropic/claude-sonnet-4.5`) ran the first 6
tasks; Category O (`xiaomi/mimo-v2.6-pro`) ran all 12. All 18 runs are
scored; exclusions (5 DeepSeek provider-invalid + 1 completed DeepSeek
cell per A1, 2 unscored smokes) never enter the ledgers. The
SpreadsheetBench-2-derived subset holds **6 tasks / 9 trajectories**
(P×3 + O×6). Full per-task population (IDs, strata, trajectories,
inclusion): `task_population.csv`.

## 2. Denominator map (task section 3)

Full study (mechanical counts from `RUNTIME_REPLAY.jsonl` + triage):

```text
166 canonical block records (x2 arms = 332 replay rows)
└─ 165 replayable (minus r18 step 29: triage-excluded, unreplayable shell loop)
   ├─ 1 skipped/non-executed (r18 step 47 block 1: 0 bytes, exit -1, wall 0.0, null route both arms)
   └─ 164 executed Python invocations
      ├─ 146 reference (REFERENCE_FAST_PATH)
      ├─ 10 fully direct (DIRECT_RUNTIME)
      └─ 8 admitted-but-fell-back (DIRECT_WITH_FALLBACK)
```

SpreadsheetBench-2-derived (controlled) subset:

```text
138 canonical block records
└─ 137 replayable (r18 s29 is in FM:07_01, hence in-subset)
   ├─ 1 skipped (r18 s47 b1, likewise in-subset)
   └─ 136 executed Python invocations
      ├─ 119 reference
      ├─ 10 fully direct
      └─ 7 admitted-but-fell-back
```

All 10 usefully-served invocations in the entire study fall inside this
subset; the curated stratum's single admission (r11, fallback) served
zero direct loads. See `denominator_map.md`.

## 3. The 164 vs 165 resolution (task section 4)

- **166** = canonical block records (both arms present for every one).
- **165** = replayable records: minus r18 step 29 block 0
  (`Financial_Model:07_01`, O trajectory), excluded by `REPLAY_TRIAGE.json`
  because a shell for-loop's control flow unrolled in-container and is not
  replayable as a linear block sequence. This is the aggregate-timing
  denominator (both arms summed over these 165).
- **164** = executed Python invocations: minus r18 step 47 block 1, an
  empty record (0 bytes, exit −1, 0.0 s, null route/admission/counts in
  both arms; its sibling block 0 executed and failed identically in both
  arms). This is the correct denominator for route, admission, and
  direct-service prevalence.

Historical note: the frozen report's "18/165 admitted" and "136
read-only" both use the 165 denominator, i.e. they include the
never-executed empty record (null admission; trivially read-only AST).
Over executed invocations the figures are 18/164 admitted and 135
read-only. Future writing must use 164 for prevalence and 165 only for
replay-timing aggregates.

Appropriate denominators: route/admission/direct-service prevalence →
164 (full) / 136 (subset); aggregate replay timing → 165 (full) / 137
(subset; the empty record contributes 0.0 s either way).

## 4. Admitted vs actually directly served (task section 5)

Per-invocation reconstruction (`invocation_ledger.csv`): route,
admission, `direct_served_loads`, fallback/reference counts, direct
reads, iteration cells/rows, artifact, exits.

- **All 8 `DIRECT_WITH_FALLBACK` blocks (7 in-subset) served zero direct
  loads and zero direct reads** (`direct_served_loads: 0`,
  `fallback_loads: 1`, `reference_loads: 1`, reason
  `missing_stale_corrupt_artifact` on every one). Admission did not
  produce acceleration for any of them.
- **All 10 `DIRECT_RUNTIME` blocks served exactly 1 direct load each**,
  0 fallback loads. Fully direct ⟺ usefully served in this study.
- Hence: admitted = 18 full / 17 subset; usefully served = 10 full /
  10 subset. The admission-to-service gap is 8/8 fallback blocks.

## 5. Candidate applicability metrics (task sections 6-7)

Subset denominators: 136 executed invocations, 110 static
`load_workbook` call sites (AST; dynamic reference-path loads are not
instrumented — the D denominator is static sites, not executions), 6
tasks, 9 trajectories.

| metric | value | assessment |
|---|---|---|
| A. fully direct invocation rate | 10/136 = **7.4%** | `PRIMARY_CANDIDATE` — interpretable unit, mechanically correct (every DIRECT block served a load), product-relevant, inflation-resistant |
| B. useful-service invocation rate | 10/136 = **7.4%** | `PRIMARY_CANDIDATE` — numerically identical to A here (all fallbacks served zero); state the equivalence rather than reporting both |
| C. admission rate | 17/136 = 12.5% | `TECHNICAL_ONLY` — answers a classifier-coverage question, not applicability; 7/17 admitted served nothing. Never present as applicability |
| D. load direct-service rate | 10/110 static sites = 9.1% | `SECONDARY_CONTEXT` — depth, not breadth; static-site denominator caveat required |
| E. task exposure | 4/6 tasks (counts, not %) | `SECONDARY_CONTEXT` — pairs with A to show spread; n=6 too small for a percentage headline |
| F. trajectory exposure | 4/9 runs (counts, not %) | `SECONDARY_CONTEXT` — same spread role at run level |

## 6. Applicability by task (task section 8)

| task | traj | exec | direct/useful | fallback | ref | loads | reads | cells |
|---|---|---|---|---|---|---|---|---|
| Debugging:07_01 | 2 | 20 | 3 | 4 | 13 | 3 | 63 | 0 |
| Debugging:08_06 | 1 | 26 | 1 | 0 | 25 | 1 | 4,607 | 3,480 |
| Financial_Model:11_05 | 2 | 28 | 5 | 1 | 22 | 5 | 9,271 | 5,822 |
| Financial_Model:07_01 | 1 | 42 | 1 | 0 | 41 | 1 | 48 | 0 |
| Template:07_01 | 2 | 12 | 0 | 1 | 11 | 0 | 0 | 0 |
| Template:03_02 | 1 | 8 | 0 | 1 | 7 | 0 | 0 | 0 |

Useful service spans 4/6 tasks (both Debugging, both Financial_Model;
neither Template) — spread, not single-task-concentrated — but invocation
volume concentrates: FM:11_05 holds 5/10 served invocations and 66% of
direct reads. (`task_summary.csv`.)

## 7. Applicability by model family (task section 9)

Subset only; descriptive, no tests:

| model | traj | exec | direct/useful | fallback | ref | reads | cells |
|---|---|---|---|---|---|---|---|
| P claude-sonnet-4.5 | 3 | 26 | 3 | 6 | 17 | 63 | 0 |
| O mimo-v2.6-pro | 6 | 110 | 7 | 1 | 102 | 13,926 | 9,302 |

The pattern differs descriptively: O trajectories contain 4× the
invocations and 100% of the iteration-cell volume; P's 3 served blocks
are small point-read scripts, and 6 of P's 9 admissions fell back
(stale-artifact). No model-population inference is drawn.
(`model_summary.csv`.)

## 8. Subset replay timing (task section 10)

Historical reducer preserved exactly (Σ `wall_s` per arm over replayable
rows; both arms present for every included row). Full-study check
reproduces the report: BASE 122.82 / RECALC 125.27 s.

Subset (137 replayable rows):

```text
Σ BASE   = 112.754 s
Σ RECALC = 114.410 s
diff     = +1.656 s (RECALC slower)
ratio    = 1.0147 (+1.5%)
```

Not a speedup. Subset aggregation is methodologically the same
operation as the full aggregate (task-filtered rows, same reducer, same
triage rule — the excluded r18 s29 is in-subset and excluded here too),
so it is valid as a descriptive subset summary. The subset dominates the
full aggregate (curated contributes only ~10 s per arm).

## 9. Prevalence vs cost mass (task section 11)

- **Breadth:** 4/6 tasks, 4/9 trajectories, 10/136 invocations (7.4%).
- **Depth:** 10 directly served loads, 13,989 direct reads, 9,302
  iteration cells, 349 iteration rows — 100% of the study's direct
  volume sits in this subset.
- Operation counts must never denominate workload statements: 13,989
  reads occurred inside just 10 invocations.

## 10. Service-vs-benefit alignment (task section 14)

Mixed at task level, clean at block level:

| task | served inv | BASE | RECALC | diff |
|---|---|---|---|---|
| Debugging:07_01 | 3 | 23.886 | 21.980 | −1.906 |
| Financial_Model:11_05 | 5 | 32.923 | 32.049 | −0.874 |
| Debugging:08_06 | 1 | 12.254 | 13.176 | +0.922 |
| Financial_Model:07_01 | 1 | 39.132 | 41.958 | +2.826 |

The 10 served blocks themselves save 6.779 s paired (10.226 → 3.447 s —
every served block is individually faster under RECALC), but the other
126 reference blocks plus wrapper/LO noise dominate task totals, so 2 of
4 served tasks still regress. Useful direct service aligns with
block-level benefit but does not survive to task-level benefit in this
subset. No causality claimed.

## 11. Provenance (task section 15)

Study term: **"controlled"** stratum. All 6 tasks: SpreadsheetBench-2
`dataset.json` IDs, instructions and workbooks used as-is
(`original: true`), mechanical sha256-rank selection, no hindsight.
`Debugging:07_01` carries the frozen `contaminated_public_example: true`
flag (retained per preregistration; Tier 1 is not a score study).

| task | workbook sha (12) | bytes | sheets | r/w expectation |
|---|---|---|---|---|
| Debugging:07_01 | 0ab0be5d7146 | 415,162 | 9 | mixed |
| Debugging:08_06 | 379497ec0a37 | 281,967 | 13 | mixed |
| Template:07_01 | 9bb442b8e133 | 7,322 | 1 | mutation |
| Template:03_02 | 6eb9ea3e1d37 | 7,197 | 1 | mutation |
| Financial_Model:11_05 | 8473c534954f | 593,396 | 18 | mutation |
| Financial_Model:07_01 | e918281d3d70 | 590,007 | 8 | mutation |

Future writing must say "SpreadsheetBench-2 tasks in the controlled
stratum" (they are the benchmark's tasks, not adaptations), never "typical
agent workflows".

## 12. Public claim formulation (task sections 12-13, 19)

**`USABLE_WITH_TWO_LEVEL_DENOMINATORS`.** Invocation-level alone (10/136)
hides the 4-task spread; task-level alone (4/6) hides the 7.4%
invocation rarity. Both levels are needed; neither suffices.

Proposed canonical descriptive claim:

> In the frozen SpreadsheetBench-2 controlled-stratum subset of the
> external-validity study (6 tasks, 9 trajectories), 10 of 136 executed
> Python invocations (7.4%) were fully directly served by Recalc, spread
> across 4 of the 6 tasks. Seven further admitted invocations fell back
> before serving any direct load. Aggregate paired replay runtime for the
> subset was 112.8 s BASE vs 114.4 s RECALC (no speedup).

Minimum public evidence set (each answers a distinct question):

1. **10/136 fully direct (7.4%)** — how often did Recalc actually do
   accelerated work per invocation?
2. **4/6 tasks exposed** — was that spread across tasks or isolated?
3. **Fallbacks served zero loads (7/7)** — why admission (17/136) is not
   the applicability number.
4. **112.8 vs 114.4 s subset replay** — what happened to runtime overall?

No inferential retrofit (task section 18): exact counts only, no
p-values, no CIs, no superpopulation extrapolation.

## 13. Tier 2 vs applicability-subset comparison (task section 16)

| | R3 / Tier 2 read-heavy | SB2 applicability subset |
|---|---|---|
| study | full-cell iteration product confirmation | Tier 1 external-validity replication, controlled stratum |
| population definition | Pop A representative-30: seeded within-family sample of usable control read scripts (SpreadsheetBench-2 / GLM lineage) | 6 controlled tasks × P/O trajectories: mechanical sha256-rank task pick; model-generated Python replayed block-wise |
| purpose | conditional mechanism effect: value when the contract applies | observed applicability: how often the contract applies in mixed model-generated workflows |
| unit | frozen workload, warm, 3 reps | executed Python invocation (replay block) |
| primary denominator | 30 workloads (timing), 13 targets (conversion) | 136 executed invocations (prevalence), 137 rows (timing) |
| performance statistic | Σ medians OFF→ON: 102.26 → 21.51 s (−79.0%; concentrated: top 3 = 84%) | subset replay Σ: 112.8 → 114.4 s (+1.5%; no speedup) |
| applicability statistic | 13/13 targets direct; 23/30 faster | 10/136 fully direct (7.4%), 4/6 tasks exposed |
| legitimate interpretation | certified reads gain a lot *when the contract applies* | the contract applies rarely *in natural mixed workflows* |

The populations were selected differently (seeded read-script sample vs
model-generated mixed trajectories) and must never be pooled. Neither is
established as representative of all spreadsheet agents. Together they
are the selective-accelerator story: deep mechanism effect, narrow
natural applicability.

## 14. Visualization candidates (task section 20, no production graphics)

- **A. invocation route stacked bar** (10 served / 7 fell-back-zero-service
  / 119 reference over 136): `GOOD_PRIMARY` — provided the fallback
  segment is labeled "admitted but served zero loads", not "partially
  accelerated".
- **B. task-by-task applicability matrix** (6 tasks × route incidence):
  `GOOD_SECONDARY` — shows the Template-zero vs FM/Debugging-spread
  pattern the headline hides.
- **C. task + invocation exposure pair** ("4 of 6 tasks; 10 of 136
  invocations"): `GOOD_PRIMARY` — the two-level denominator in visual
  form; count-based, no fragile percentages at task level.
- **D. operation-count figure** (13,989 reads / 9,302 cells):
  `MISLEADING` as prevalence (all inside 10 invocations — visually
  inflates breadth); acceptable only as explicitly labeled depth
  context, never beside a percentage headline.

## 15. Consistency review (task section 21)

- 164/165: resolved mechanically (§3); empty record and excluded step
  identified by bytes/exit/wall/route properties, asserted unique.
- Skipped block counted correctly: excluded from all prevalence (164/136),
  contributes 0.0 s to timing either way.
- Admission ≠ service: separated throughout (17 vs 10); fallback rows
  individually verified at zero direct loads/reads.
- No double-counting: invocation-level primary; load-level D kept
  separate with a static-site denominator caveat.
- Original-vs-derived: controlled workbooks are `original: true`
  SpreadsheetBench-2 artifacts; "derived" describes selection/use, and
  the audit preserves the study's "controlled" term.
- Curated contamination: verified absent — the subset is stratum-filtered
  from the manifest, and the only curated admission served zero loads.
- DeepSeek/smokes: absent from ledgers per A1/A2; RUN_LEDGER holds
  exactly the 18 amended runs (P first-half 6 + O all 12).
- Arm mismatch: asserted base+recalc present per block key with identical
  AST; both arms exist for every timing row.
- Repeated tasks across trajectories: E counts distinct tasks (4/6),
  F counts runs (4/9) — never conflated.
- Replay-block vs model-run units: the 166 blocks are the replay
  segmentation of model-run Python (shell-only/tool steps excluded per
  triage `not_tested`); the audit's unit is always the executed replay
  block, stated as "executed Python invocation".
- Route names: single-study vocabulary (`REFERENCE_FAST_PATH` /
  `DIRECT_RUNTIME` / `DIRECT_WITH_FALLBACK`), verified against
  `ROUTING_CENSUS.jsonl` per-run aggregates (36 rows sum to the same
  166-block route multiset).

**Residual ambiguities:** none material. One methodological note: metric
D's denominator (110 static `load_workbook` sites) counts call sites,
not dynamic executions — loops and conditional calls are undercounted,
dead code overcounted. It is fit for labeled secondary depth context,
not for a headline rate.

## 16. Audit verdict

**`SPREADSHEETBENCH_APPLICABILITY_CLAIM_USABLE_WITH_MULTIPLE_DENOMINATORS`**

Within the frozen SpreadsheetBench-2-derived external-validity
population, Recalc performed useful direct service on 10 of 136 executed
Python invocations (7.4%), spread across 4 of 6 tasks and 4 of 9
trajectories; aggregate subset replay runtime was 112.8 s BASE vs
114.4 s RECALC (no speedup). The claim requires the two-level
(task + invocation) denominator plus the fallback-zero-service note. No
historical verdict was modified.
