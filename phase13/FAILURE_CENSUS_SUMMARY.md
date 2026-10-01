# Phase 13 — Failure Census Summary

## Population A (40 phase-12 CONTROL; full trajectory classification)

Terminal: 12 submitted w/ output, 2 submitted w/o output, 8 cost-cap,
4 call-cap, 14 wall-time no-submit. Exact: 0/40.

| Primary | n | Runs |
|---|---|---|
| L8 resource allocation | 26 | all truncated + wall-time no-submit w/o output |
| L0 evaluator/benchmark state | 7 | 6 stale-cache submits + 16_02 (PLAUSIBLE) |
| L7 verification/stopping | 3 | 04_06, 08_06 (degenerate), 12_01 (correct-work no-submit) |
| L5 formula choice | 3 | 11_03, 11_04, 14_03 |
| L6 execution mechanics | 1 | 17_05 chart XML |

Secondaries: L2 ×16 (never opened target sheets/regions), L3 ×7
(saw-but-never-acted), L7 ×6 (wrong-artifact verification), L0 ×2,
L8 ×2, L9 ×1 (TODAY volatility), none ×6.
Confidence: DIRECT 12, STRONGLY_SUPPORTED 25, PLAUSIBLE 3.

Submitted-work loss (12 outputs): 6 fully recalc-recoverable
(hygiene, closed), 1 partly (11_03), 1 mostly-residual (11_04),
1 single-slip (14_03), 1 unscorable/volatility (16_02), 1
correct-but-unsubmitted (12_01), 1 corrupt (17_05).

No-submit loss (28 runs): 19 inspection loops, 5 scale-overwhelm
(10_0x, overlapping), 3 ramble traps, 1 work-in-progress, 2
degenerate submits. Coverage probe: 8/26 had full mod-region
coverage (L3 secondary); 16 had named-sheet gaps (L2 secondary).

## Population B (183 P1 archived controls; score census + 18-traj sample)

Exact: 29/183. Failures: 154 (Template 31, FM 82, Debugging 41 —
Debugging has ZERO exact-1). Summed mod loss 41.4766, reg loss 2.122.

Recalc-fair: 142 ALREADY_RECALC_FAIR (no material effect, scores
reproduce); 41 INCOMPATIBLE/UNSUPPORTED (unresolved bounds).

First-error taxonomy: MOD:valued 75, REG:valued 64, MOD:output=None
13, scorer-XML 1, NONE 30 (exact-1 + rounding).

Per-cell full-error rollup (probe_fullerr, official code paths,
validated 3/3 on patched runs): 2053 assessed roots after
cascade factoring (sign-flip 1308 symptoms → 117 roots).
Root-cause split: 1049 formula-differs (L5), 780 formula-same
(cascade/upstream; cache-fresh per recalc classes), 200 value-only.
Footprints: recall median 0.966, precision median ~1.0 — failures
are content, not placement.

Sampled mechanisms (19 trajectories, DIRECT forensics):
unpassable-as-scored empty MOD set (05_08 — scored bytes were
recalced; run-dir None caches a red herring), wrong-bug-theory
wholesale miss (07_03, recall 0.014), systematic scale error
(16_12 ×12), retained hardcodes (01_02), malformed input (FM
06_01), offset self-correction in successes (09_03, FM 11_01),
thorough near-misses (18_02, 11_02, 08_03 — upstream/cascade
residuals).

## Cross-population loss partition (score-bearing mass)

- EXPLAINED BY KNOWN MECHANISM: submit-hygiene stale cache (Pop A
  V1-recovered + 05_08 edited cells), malformed input (06_01),
  evaluator artifacts where proven (B31 pre-existing, TODAY B4),
  degenerate submits. (Exact mass TBD after fullerr.)
- LIKELY EXPLAINED: small-residual reasoning slips with in-context
  evidence (sign/scale/row classes).
- UNEXPLAINED: residuals whose mechanism fullerr + trajectories
  cannot fix (target: explicit list per run, defaulting to
  UNALLOCATED rather than forced).

## Category heterogeneity (preview)

- Template: tight-regime failures are hygiene (recoverable) or
  single-slip reasoning; loose-regime near-misses dominate.
- Financial_Model: tight-regime no-submit (assumption-discovery
  gaps + loops); loose-regime largest mod-loss pool (18.654).
- Debugging: zero exact-1 in either population's ordinary runs;
  misdiagnosis + partial fixes + formula-text artifacts; the only
  category with no demonstrated ordinary success.
