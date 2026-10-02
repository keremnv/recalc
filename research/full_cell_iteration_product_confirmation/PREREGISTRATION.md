# Full-cell iteration product confirmation — preregistration

Version 1. Frozen before confirmatory scoring. This R3 phase tests whether
the already-certified R2 iteration mechanism satisfies a corrected
mass-based product gate. No mechanism development occurs here.

Lineage (frozen, not rewritten):

```text
R1: iteration opportunity earned (research/execution-surface-census)
R2: mechanism works, original product gate fails (MECHANISM_REAL_BUT_NOT_PRODUCT)
R3: new mass-based product criterion preregistered before confirmation (this phase)
```

## 1. Scope freeze

Product contract: `CONTRACT_DECISION.md` (bounded/bare `iter_rows`, nested
consumption, `.value/.coordinate/.row/.column/.data_type` reads, merged
ranges served, everything else reference-routed). Allowed runtime changes
vs `e44e82b`: the R2 iteration mechanism as-is, the `KeyError` parity fix,
and strictly necessary production cleanup. All R1 CLOSED/OBSERVE_MORE
items stay closed.

## 2. Frozen mass denominator

Representative reference-path parse mass attributable to the iteration-only
opportunity, from R1 `OPERATION_CENSUS.jsonl` `reference_parse_s` medians
over the 13 frozen targets (same parse-cost accounting as R1/R2):

**Denominator: 64.0710 s** (per-workload medians summed; cross-checks the
R2 report's 64.1/64.5 s figure; full table in `REPORT.md`).

Converted mass uses these frozen R1 per-workload figures (not re-measured
values) for every target that routes `DIRECT_RUNTIME` and stays direct
throughout in confirmation scoring. The denominator is not redefined after
seeing results.

## 3. Gates

### Semantic gate (all must hold)

- Zero deviations on the frozen 39-case adversarial suite + the new
  missing-sheet `KeyError` case (40 total), vs pinned openpyxl 3.1.5,
  with R2 normalization (address + volatile-metadata only; exception
  type/message compared where applicable).
- Zero deviations on Population A (30) differential runs.
- Zero deviations on Population B (22) differential runs.
- Maintained product suite passes (modulo the 4 documented pre-existing
  baseline failures, re-verified identical).
- Missing-sheet `KeyError` regression test passes.

Any genuine semantic deviation attributable to the iteration mechanism
fails productization.

### Coverage/mass gate

Converted mass ≥ 90% of the frozen denominator (≥ 57.6639 s). Report both
the percentage and absolute seconds.

### Routing gate

- No previously direct representative workload becomes reference-only.
- No new iteration-attributed runtime fallbacks on supported workloads.
- Unsupported/uncertain iteration forms remain fail-closed (adversarial
  block-shapes re-verified reference-routed).

### Performance non-regression gate

For every representative workload: `median(ON) − median(BASE) ≤ 0.083 s`
warm. Basis: 2× the 41.5 ms R1 G5 repeatability median (same 2× rule R2
used for its cold check); one-sided (improvements uncapped). Large gains
elsewhere do not compensate a genuine material regression. Machine
variance is handled by paired reps (≥3 + warmup) on REUSED artifacts.

### Whole-population economic gate (reported, not a veto beyond mass)

Population A warm totals before/after, median, per-workload delta
distribution. No per-workload universal absolute-savings threshold —
that form is exactly what R2 showed to be miscalibrated.

## 4. Protocol

- Same frozen A/B identities; same R2 harness code paths (reused, not
  rewritten); warm REUSED artifacts; BASE/OFF/ON arms; cold check and
  memory confirmation as secondary measures with R2 methods.
- KeyError verification: exception type/args/message, uncaught
  stdout/stderr behavior, existing-sheet lookup unaffected (dedicated
  regression test + adversarial case).
- Product-quality review of R2 code before scoring (§6 of the task);
  `RECALC_NO_ITERATION_PROBE` retained through scoring for the OFF
  control, removed only after a positive decision.

## 5. Verdict classes (exactly one)

- PRODUCTIZE: every gate above passes.
- CLOSE: corrected gate fails on value or compatibility risk.
- REVISE_AND_RETEST: only a specific new mechanical defect invalidating
  confirmation with a narrow corrective path.

No new decision rule after observing data. Conditional integration (rc4)
follows only on PRODUCTIZE, per the task's §§12–14 bounds.
