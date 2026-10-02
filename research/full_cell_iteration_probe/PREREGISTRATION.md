# Full-cell iteration probe — preregistration

Version 1. Frozen before scoring. Narrow feasibility experiment acting on
`research/execution-surface-census` (commit `2d43439`), which earned exactly
one probe: full-cell iteration serving on the direct-read path.

## 1. Question

Can Recalc transparently serve the historically observed full-cell iteration
forms from existing workbook read state, convert most iteration-only
representative workloads to the direct path, and preserve openpyxl-observable
behavior closely enough to clear the established full-command economic and
parity gates?

## 2. Frozen observed contract (`ITERATION_CONTRACT.json`)

Derived mechanically from the 13 target workloads (see `extract_contract.py`).
The minimum contract — nothing more:

- `ws.iter_rows()` with static int `min_row/max_row/min_col/max_col` or
  absent (absent side falls back to sheet dimension bounds);
- nested `for row ...: for c in row:` consumption; rows are tuples;
- per-cell use limited to `.value` and `.coordinate`;
- `value is not None` filtering (blank cells yielded with `None`);
- no cell/row stores, aliases, escape, identity use, or rich access;
- no merged-range contact in any target book (merged contact fails closed
  to genuine openpyxl; the probe does not serve merged ranges);
- no `iter_cols`, sheet iteration, materialization, row indexing,
  `.row`/`.column`/`.data_type` use in targets (certified only insofar as
  the implementation serves them identically; not required for the gate).

Anything outside this contract keeps the whole-script reference path.

## 3. Populations (frozen)

- **Authorization: Population A** (30 representative workloads, census
  identities). Headline claims use A only.
- **Target subset:** the 13 iteration-only-blocked A workloads in
  `TARGET_WORKLOADS.json` (rule: classifier blockers ⊆ {iterator shape
  not statically proven, CELL_OBJECT_ITERATION_BOUNDARY}).
- **Supporting: Population B** (22 fixed/contact-selected). Never the
  basis of a success claim.

## 4. Primary success gate (kept from the census report)

1. At least **10 of the 13** target workloads convert from reference to
   direct execution **and stay direct throughout** (no runtime fallback).
2. Each converted workload shows a **warm full-command gain exceeding the
   208 ms authorization bar** (lower-80% interval per workload, bar basis:
   5× the 41.5 ms G5 repeatability spread from the census phase).
3. **Zero semantic parity deviations** on all certification populations
   (adversarial suite + A/B differential runs): exit code, stdout bytes
   (address-normalized per census convention), and workbook state
   (volatile-metadata-normalized) identical to pinned openpyxl 3.1.5.

Warm = artifact already built and content-fresh (REUSED path); each workload
measured with reps (≥3) after one warmup build. If any part of the gate was
encoded incorrectly, stop and explain before scoring — do not silently
change the rule.

## 5. Secondary measures

Median/distribution of full-command gains; artifact decode cost; iteration
serving cost split (traversal vs proxy allocation); cells yielded;
per-cell overhead; fallback/materialization rate with reasons; classifier
admit rate on A/B plus false-positive/false-negative review (every newly
admitted script manually reviewed for contract membership); memory delta
(RSS peak, PROD vs BASE); cold-check deltas (see §7).

## 6. Implementation bounds (non-goals stay closed)

Allowed: proxy row/cell iteration over existing read state
(bounds + sparse coord→(value, data_type) + merged info for fail-closed);
minimal classifier extension distinguishing certified/unsupported/uncertain
iteration (fail-closed philosophy mandatory); runtime fallback with recorded
reasons; measurement instrumentation.

Forbidden (R1 CLOSED/OBSERVE_MORE): dependency graphs, fingerprints, new
persisted tables/indexes (unless iteration is proven economically impossible
without — requires a stop-and-explain note), mutation state, persistent
workers, inspection APIs, `find_text`/regions/diff/dependency queries,
`values_only`, `.values`, range literals, `data_only`, rich styles,
serialization or formula-engine work.

## 7. Measurement protocol

- Comparator arms per workload: plain Python/openpyxl (BASE), rc3 product
  behavior (PROBE-OFF control = this branch with the probe disabled via env
  key, proving the probe is the only delta), probe behavior (PROBE-ON).
- Warm scoring (authorization): prebuilt artifact, ≥3 timed reps + warmup.
- Cold check (limited, reported separately, never averaged with warm):
  fresh cache per run, target subset only; success = no material
  worsening vs rc3 cold (median delta within ±2× repeatability spread).
- Proxy economics: cells yielded, allocation vs traversal split,
  RSS-peak delta. If proxy construction erases >50% of avoided parse on
  any converted workload, the probe reports MECHANISM_REAL_BUT_NOT_PRODUCT
  at best (threshold preregistered here, not post hoc).
- Adversarial suite (`ADVERSARIAL_CASES.json`): empty/sparse sheets, large
  dims with few cells, interior/trailing blanks, merged anchors/children
  (must fall back, never mis-serve), formulas, dates, booleans, errors,
  shared strings, array/data-table formulas, explicit bounds incl.
  out-of-dimension bounds, repeated/partial/nested iteration, aliasing,
  stored cells, post-iteration rich access (must fall back), abrupt
  exceptions mid-iteration. Differential vs pinned openpyxl; meaningful
  differences are failures, never normalized away.

## 8. Verdict classes (exactly one)

- PRODUCTIZE: gate clears fully, zero deviations, mechanism stays narrow.
- MECHANISM_REAL_BUT_NOT_PRODUCT: serving works but economics/coverage/
  integration risk fail the product gate.
- REVISE_AND_RETEST: a specific mechanical defect invalidates the test
  with a preregistered-style corrective path.
- CLOSE: semantics/economics fail with no narrow correction justified.

No automatic productization follows any verdict. This phase stops at the
verdict.

## 9. Environment and provenance

Same host family as census; versions recorded at scoring. Product baseline:
rc3 `src/recalc_agent` at `2d43439`; probe changes live on this branch only.
Raw telemetry in gitignored `_staging/`; compact ledgers committed.
