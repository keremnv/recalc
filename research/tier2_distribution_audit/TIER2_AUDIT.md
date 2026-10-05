# Tier 2 read-heavy population — distribution audit

Research-only evidence reconstruction. No new benchmark runs, no product
changes, no documentation changes, no historical verdict modified.

- Branch: `research/tier2-performance-distribution-audit`
- Builder: `research/tier2_distribution_audit/build_ledger.py` (deterministic)
- Ledger: `tier2_workloads.json` / `tier2_workloads.csv`
- Summary: `tier2_summary.json`
- Denominator map: `denominator_map.md`
- Sources: `sources.md`

## 1. Population definition (task section 2)

**Name (historical):** Population A, "representative 30".

**Selection rule (frozen, preregistered):** seeded within-family sample of up
to 10 usable control read scripts, max two per task, no eligibility
requirement. Label `CONTROL_OBSERVED_TREATMENT_BLIND`, seed `20261011`.

**Source file:** pre-tidy `rc_acceleration_validation/representative_population.json`
at commit `554dc00`, re-verified byte-identical (30/30 script SHA-256,
30/30 workbooks present) by the R1 census. Design hash preregistered in
`preregistered_spec.json` (`design_hashes.representative_population.json`).

**Corpus identity:** 10 Template + 10 Financial_Model + 10 Debugging
workloads. Scripts are ordinary-Python/openpyxl agent trajectory executions
recovered from `research/history/control_python_audit/python_executions.jsonl`
(GLM/Spark model family lineage); workbooks are SpreadsheetBench-2 files
under `benchmark-data/`. "Usable" = control preflight exit 0 with recorded
stdout hash (`control_preflight.usable`, per `workload_manifest.json`).

**Exclusions:** none after freeze. All 30 units executed in all three R3
arms (BASE/OFF/ON), 3 warm reps each, all exits 0.

**"Representative" scope:** representative *within the historical study
design* — a seeded, treatment-blind, within-family sample of usable
control read scripts with no eligibility filter. It is **not** established
as representative of spreadsheet agents generally: single benchmark
family (SpreadsheetBench-2), single model lineage (GLM/Spark), read-only
scripts, single host. In the original rc validation spec the
representative-30 role was explicitly "supporting descriptive view only";
R1/R2/R3 promoted Population A to the primary population.

**Full 30-workload list:** `tier2_workloads.csv` (column `workload_id`).

## 2. The 30-vs-13 relationship (task section 3)

The 13 targets are a strict subset of the 30, selected mechanically in R1
by classifier-blocker shape:

- **Target rule** (`TARGET_WORKLOADS.json`): Population A workloads whose
  classifier blockers are a subset of {iterator shape not statically
  proven, `CELL_OBJECT_ITERATION_BOUNDARY`} — i.e. blocked *only* by
  iteration. These 13 held 64.1/64.5 s of reference-path parse (99%).
- **The other 17:** 8 `ADMITTED_PREEXISTING` (already direct under rc3/OFF:
  7 `DIRECT_RUNTIME` + 1 pre-existing `DIRECT_WITH_FALLBACK`) and 9
  `BLOCKED_OTHER` (blocked on non-iteration grounds: rich objects, static
  uncertainty, worksheets/active-sheet boundaries).

```
30 = 13 TARGETS + 8 ADMITTED_PREEXISTING + 9 BLOCKED_OTHER
13 = iteration-only-blocked subset of the 30 (target rule above)
aggregate timing denominator = all 30 (every unit contributes)
direct-route denominator = 13 targets (13/13 DIRECT_RUNTIME throughout)
```

**Can 13/13 sit beside the 30-workload aggregate?** Yes, but only with the
subset relation stated: the aggregate measures whole-population warm
runtime (all 30, including 17 workloads the mechanism was never expected
to move); 13/13 measures mechanism conversion on the iteration-blocked
subset. Presenting "13/13 direct" next to "79% lower" without noting the
13 ⊂ 30 relation invites the false reading that all 30 workloads went
direct. See `denominator_map.md`.

## 3. Ledger and historical reproduction (task sections 4-5)

**Historical reducer (preserved exactly):** per-workload median of 3 warm
reps, summed across all 30 workloads.

**Historical pair:** OFF → ON, where OFF is the rc3-equivalent
predecessor control (iteration disabled via `RECALC_NO_ITERATION_PROBE`)
and ON is the iteration candidate. This is explicit in the R3 report
("rc3/OFF 102.26 s → candidate 21.51 s") and `PRODUCT_GATE.json`
(`off_total_median_sum_s`, `on_total_median_sum_s`).

**Critical comparator note:** the public `102.26 → 21.51` aggregate is
**predecessor-product → candidate**, not bare-openpyxl → Recalc:

| comparator sum (median sums) | value |
|---|---|
| Σ BASE medians (bare openpyxl) | 107.4838 s |
| Σ OFF medians (rc3-equivalent) | **102.2582 s → 102.26** |
| Σ ON medians (candidate) | **21.5080 s → 21.51** |
| saved OFF→ON | **80.7502 s → 80.75** |
| ON/OFF ratio | 0.2103 |
| relative reduction | **78.97% → 79.0%** |
| saved BASE→ON (for reference) | 85.9758 s (matches `saved_vs_base_s: -85.98`) |

Reconstruction reproduces every historical rounded figure. No correction
needed; the historical outcome stands unchanged.

**R2 lineage cross-check:** R2's "63.2 s → 15.0 s" recomputes as BASE
63.2169 → ON 15.0041 (OFF was 61.1333) — i.e. the R2 headline used the
BASE comparator while the R3 headline uses the OFF comparator, on
different hosts (R3 BASE Σ is 107.48; R2 documented ~2× machine variance
on giants). Both are internally consistent; they must not be mixed into a
single series without stating the comparator and host change.

## 4. Post-hoc descriptives (task section 6)

Post-hoc descriptive summaries of the frozen historical population. They
do not modify the preregistered outcome. Pair: ON vs OFF (exact
faster/slower, no equality band; no exact ties occurred).

| statistic | value |
|---|---|
| workloads faster (ON < OFF) | 23/30 |
| workloads equal | 0 |
| workloads slower (ON > OFF) | 7/30 (all ≤ 49.7 ms; all non-targets) |
| median ON/OFF ratio | 0.9125 |
| arithmetic mean ratio | 0.7566 |
| geometric mean ratio | 0.5965 |
| 25th / 75th percentile ratio | 0.5497 / 0.9997 |
| min ratio | 0.0673 (`Debugging_10_07__6dd8f6d3a4dd`) |
| max ratio | 1.1113 (`Financial_Model_02_01__bb15e0fe3832`) |
| median absolute saved | 0.0358 s |
| total absolute saved | 80.7502 s |
| largest saving | 22.8672 s (`Debugging_10_10__c7eca76e6646`) |
| largest regression | −0.0497 s (`Financial_Model_02_01__bb15e0fe3832`) |

The median workload improves only 8.75% (ratio 0.91) and saves 36 ms,
while the aggregate falls 79.0%: the aggregate is driven by a heavy tail,
not by a typical-workload effect.

## 5. Concentration audit (task section 7)

Workloads sorted by absolute seconds saved (OFF→ON):

| group | share of total positive savings |
|---|---|
| top 1 (`Debugging_10_10`, 22.87 s) | 28.3% |
| top 3 (the three Debugging giants, ~22.6–22.9 s each) | **84.2%** |
| top 5 (+ FM:08_02 pair, ~3.8–3.9 s each) | 93.7% |
| top 10 | 99.4% |
| remaining 20 workloads | 0.6% |

Runtime concentration: the top 3 workloads hold 71.6% of aggregate OFF
runtime (top 5: 82.2%), but only 23.6% of aggregate ON runtime — the
mechanism specifically collapses the giant parses.

**Assessment: dominated by a few expensive workloads.** The ≈79%
aggregate reduction is real and parity-clean, but 5 of 30 workloads
supply 94% of the seconds saved. An aggregate-only public summary would
be technically correct and practically misleading about what a
non-giant workload experiences.

## 6. Effect size vs workload size (task section 8)

Descriptive within this fixed population only; no causality, no
superpopulation inference.

| correlation (OFF runtime vs …) | Pearson | Spearman |
|---|---|---|
| absolute seconds saved | 0.9986 | 0.7758 |
| ON/OFF ratio | −0.7618 | −0.7780 |

Absolute benefit is essentially proportional to workload size
(Pearson 0.999): larger/slower BASE workloads receive nearly all of the
absolute benefit. Larger workloads also get better relative ratios
(negative correlation with ON/OFF ratio).

## 7. Mechanism consistency (task section 9)

- Routes OFF → ON: 22 REF / 7 DIRECT / 1 FALLBACK → 9 REF / 20 DIRECT /
  1 FALLBACK. Exactly the 13 targets converted; every route unanimous
  across all 3 reps; all exits 0.
- All 13 targets `DIRECT_RUNTIME` throughout with 0 iteration-attributed
  fallbacks; the 1 fallback is pre-existing under OFF (byte-identical
  counts).
- All 9 `BLOCKED_OTHER` stayed reference (no artifact: `artifact_status`
  empty, expected); all 8 `ADMITTED_PREEXISTING` kept their rc3 routes.
- Parity: 30/30 Population A differential `true` (`parity_r3.jsonl`).
- The 7 slower workloads are all non-targets (5 pre-existing
  direct/fallback, 2 reference-blocked) with deltas −1.0 to −49.7 ms —
  inside the preregistered ±50 ms noise band, i.e. measurement noise on
  workloads the mechanism does not touch, not mechanism regressions.
- Weak/no speedup workloads correspond exactly to telemetry: no direct
  iteration cells served (non-targets) and/or small BASE runtime with the
  fixed wrapper tax dominating (small targets, e.g. `Template_15_03__68f4`
  saves 27 ms).

## 8. Measurement noise vs workload variation (task section 10)

Run-to-run variation (3 warm reps per arm): median coefficient of
variation 2.5% BASE, 2.6% OFF, 5.1% ON; worst-case 10.7% BASE / 9.3% OFF /
11.3% ON (small sub-second workloads where ±ms noise dominates). This is
an order of magnitude below the workload-level effect range (ratios
0.067–1.111): cross-workload variation is the signal (real differences
among workload shapes — giant parses vs small reference scripts), not
noise. No confidence intervals for spreadsheet agents generally are
constructed; the population is fixed and non-random.

No inferential retrofit was performed (task section 11): no significance
tests, no p-values, no "expected real-world speedup" label on the median
or geometric mean. The frozen 30 are not a random sample from a formal
superpopulation of agent workloads.

## 9. Is the aggregate still the best primary summary? (task section 12)

**YES_WITH_DISTRIBUTION_CONTEXT.** The aggregate (Σ medians OFF→ON) is
the preregistered whole-population economic form, matches the mass-based
gate philosophy R3 was created to serve, and captures the decision-relevant
quantity (total warm seconds removed). It should remain primary. But the
concentration result (top 3 = 84%) makes aggregate-only presentation
misleading about the per-workload experience: the median workload saves
36 ms, not 79%. The aggregate must be accompanied by distribution context.

## 10. Minimum supporting statistics (task section 13)

For a future `PERFORMANCE.md`, the minimum set that adds information the
aggregate does not contain:

1. **23/30 workloads faster** (exact ON<OFF; the 7 slower are all ≤50 ms,
   inside the preregistered noise band, on workloads the mechanism does
   not touch). Adds: breadth of effect. The aggregate alone cannot tell
   30 small wins from 3 giant ones.
2. **Median per-workload ratio 0.91 (IQR 0.55–1.00).** Adds: the typical
   workload experience, which the aggregate completely hides.
3. **Top 3 workloads contribute 84% of total seconds saved.** Adds: the
   concentration fact that reconciles (1) and (2) with the 79% aggregate.

Each is computable from `tier2_workloads.csv`. No further statistics are
needed for an honest public summary; a sorted-ratio or scatter plot may
replace (2)+(3) visually (see §11).

## 11. Visualization candidates (task section 14)

- **A. BASE-vs-Recalc scatter (log–log): GOOD.** Would expose the
  size-dependent effect honestly: giants far below the diagonal, the tail
  clustered near it. Directly visualizes the Pearson-0.999 finding.
- **B. Sorted paired/dumbbell plot: GOOD.** Would make absolute savings
  (and their concentration in the top 5) immediately visible. Best
  companion to the aggregate number.
- **C. Sorted runtime-ratio plot: GOOD.** Would make relative consistency
  visible: 12 workloads at ≤0.80, a middle band near 0.9–1.0, 7 at ≥1.0.
  Best companion to the median-ratio statistic.
- **D. Aggregate card only: MISLEADING.** With top-3 = 84% and median
  saved = 36 ms, a lone "102.26 → 21.51 (−79%)" card invites the false
  inference of a typical-workload effect. Inadequate without (B) or (C).

No production chart was built in this phase. Any two of A/B/C suffice;
D must not stand alone.

## 12. Vignette cross-check (task section 15)

`Financial_Model_08_02__4ca3ae46295d` **is** a member of Population A
(role: TARGET).

| measure (R3 frozen row) | value | rank in 30 |
|---|---|---|
| BASE median | 5.3035 s | 5th largest |
| OFF→ON saved | 3.7874 s | 5th |
| OFF→ON reduction | 69.40% | 7th |
| ON/OFF ratio | 0.3060 | 7th |

Three distinct measurements of this workload must not be conflated:

| measurement | BASE | ON/RECALC | reduction |
|---|---|---|---|
| R2 frozen (probe host) | 3.05 s | 1.04 s | ~66% |
| R3 frozen (confirmation host) | 5.3035 s | 1.6696 s | 69.40% (OFF→ON) |
| Vignette 0.2.0 reproduction | 3.6866 s | 0.7320 s | 80.14% (BASE→RECALC) |

The vignette's 80.14% comes from the later 0.2.0 reproduction window, not
from the R3 timing row (different host, different absolute scale — R2
documented ~2× machine variance). The vignette evidence bundle records
the R3 medians as a cross-check; both show a large win on the same
workload.

**Typicality:** the vignette workload is a strong-but-not-extreme
beneficiary — top-quintile by savings (5th) and reduction (7th), an order
of magnitude below the top-3 giants (~22.7 s each) and two orders above
the population median (36 ms saved). It is a reasonable illustration of
"expensive certified read accelerated" provided the population context
(§10) accompanies any population-level claim. It must never be presented
as the typical workload outcome.

## 13. Tier 2 vs Tier 3 (task section 16)

("Tier 3" here is the repo's Tier 1 external-validity replication,
branch `research/external-validity-tier1`; the task's hierarchy labels it
Tier 3, the mixed external-validity population.)

| | Tier 2 read-heavy | Tier 3 mixed external-validity |
|---|---|---|
| study | R3 full-cell iteration product confirmation | Tier 1 external-validity replication |
| purpose | confirm the iteration mechanism's value on read-heavy workloads | falsification screen: do 0.2.0 conclusions survive new model families/distributions |
| unit | frozen workload (script + workbook), warm, 3 reps | model-in-loop runs (18) + replayable python blocks (165 usable) |
| population | Pop A representative-30 (seeded within-family sample; SpreadsheetBench-2 / GLM lineage) | 12 tasks × 2 model families (Claude-Sonnet-4.5, Mimo-v2.6-Pro) |
| primary statistic | Σ per-workload medians, OFF→ON | claim-by-claim replication verdicts; paired replay wall is structural, explicitly not a speedup claim |
| result | 102.26 → 21.51 s (−79.0%); 13/13 targets direct | `EXTERNAL_VALIDITY_STRENGTHENED`; replay BASE 122.8 vs RECALC 125.3 s; 18/165 blocks admitted (11%) |
| legitimate generalization | conditional mechanism effect on expensive certified reads in this regime | broader applicability: selective accelerator; most natural mixed/dynamic code correctly stays reference |

Tier 2 measures the conditional mechanism effect (how much certified
reads gain *when the contract applies*); Tier 3 measures broader
applicability (how often the contract applies *in natural mixed
workflows*). Denominators and purposes differ; neither result invalidates
the other. Together they are the selective-accelerator story.

## 14. Consistency review (task section 19)

Skeptical re-checks performed, all passing:

- **Denominators:** 30/30 rows present, unique workload IDs, every unit in
  all 3 arms × 3 reps, all exits 0, all 30 in the aggregate.
- **Duplicates:** none (ID set size 30; cross-checked against the frozen
  `representative_population.json` ID set — identical).
- **Exclusions:** none post-freeze; no row dropped or imputed.
- **Timing window:** all warm; ON direct rows show `REUSED` artifacts;
  the 9 reference rows show no artifact (expected — reference path builds
  none).
- **Median vs mean:** medians used throughout, matching the historical
  reducer; means computed only as labeled post-hoc descriptives.
- **Release vs prototype:** R3 ON = rc4 candidate mechanism (frozen
  evidence); vignette = released-0.2.0 reproduction (distinguished in
  §12, not merged into the ledger).
- **Route labels:** from the R3 `REPRESENTATIVE_RESULTS.jsonl` rows
  (correct experiment), unanimous across reps, matching
  `PRODUCT_GATE.json` routing counts (20/9/1).
- **Target vs population:** 13 ⊂ 30 via the frozen `TARGET_WORKLOADS.json`
  partition (13/8/9), verified to cover all 30 representatives.
- **Vignette vs R3 timing:** kept as three separate measurements (§12).
- **Rounding:** full-precision recomputation (102.2582 / 21.5080 /
  80.7502 / 78.97%) rounds exactly to every historical figure.

**Residual ambiguities:** none material. Two presentation facts future
writers must preserve: (a) the headline comparator is OFF (rc3), not
bare BASE (107.48 s); (b) the R2 headline used BASE while R3 used OFF —
same-direction, different-comparator numbers that must not be spliced
into one series.

## 15. Audit verdict

**`TIER2_AGGREGATE_NEEDS_DISTRIBUTION_CONTEXT`**

The historical aggregate is exactly reproduced, parity-clean, and the
right primary summary — but its benefit is heavily concentrated
(top 3 = 84%, median workload saves 36 ms). Public presentation must pair
it with the §10 minimum set (23/30 faster; median ratio 0.91, IQR
0.55–1.00; top-3 share 84%). No historical verdict was modified.
