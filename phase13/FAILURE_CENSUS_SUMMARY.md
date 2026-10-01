# Phase 13 — Failure Census Summary

## Population A (40 phase-12 CONTROL; full trajectory classification)

Terminal: 12 submitted w/ output, 2 submitted w/o output, 8 cost-cap,
4 call-cap, 14 wall-time no-submit. Exact: 0/40.

| Primary | n | Runs |
|---|---|---|
| Primary | n | Runs |
|---|---|---|
| L8 resource allocation | 26 | all truncated + wall-time no-submit w/o output |
| L5 formula choice | 5 | 11_03, 11_04, 14_03, 10_02, 11_01 |
| L0 evaluator/benchmark state | 5 | 06_05, 06_25, 06_09, 06_16 + 16_02 (PLAUSIBLE) |
| L7 verification/stopping | 3 | 04_06, 08_06 (degenerate), 12_01 (V1-exact, ambiguous class) |
| L6 execution mechanics | 1 | 17_05 chart XML |

(Gate-A fix 4: 10_02/11_01 L0/L7 → L5/L0 — V1 still fails, so
formulas-first per taxonomy precedence; 06_25 stays L0 under the
benchmark-state carve-out. Fix 8: 12_01 "perfect work" hedged to
V1-exact-ambiguous.)

Secondaries: L2 ×16 (never opened target sheets/regions), L3 ×7
(saw-but-never-acted), L7 ×4 (wrong-artifact verification), L0 ×4,
L8 ×2, L9 ×1 (TODAY volatility), none ×6.
Confidence: DIRECT 10, STRONGLY_SUPPORTED 27, PLAUSIBLE 3.

Submitted-work loss (12 outputs): 3 fully recalc-recovered to
exact (06_05, 06_09, 06_16) + 1 near (06_25, benchmark-state
residual) — hygiene-primary, closed; 4 partials with agent
residuals (10_02, 11_01, 11_03, 11_04) — L5-primary; 1
single-slip (14_03); 1 unscorable/volatility (16_02); 1
V1-exact-but-unsubmitted (12_01, ambiguous class); 1 corrupt
(17_05).

No-submit loss (28 runs): 19 inspection loops, 5 scale-overwhelm
(10_0x, overlapping), 3 ramble traps, 1 work-in-progress, 2
degenerate submits. Coverage probe: 8/26 had full mod-region
coverage (L3 secondary); 16 had named-sheet gaps (L2 secondary).

## Population B (183 P1 archived controls; score census + 19-traj sample)

Exact: 29/183. Failures: 154 (Template 31, FM 82, Debugging 41 —
Debugging has ZERO exact-1). Summed mod loss 41.4766, reg loss 2.122.

Recalc-fair: 142 resolved (141 NO_MATERIAL_EFFECT + 1 measured
RECALC_REGRESSION) + 41 INCOMPATIBLE/UNSUPPORTED (unresolved
bounds). (Gate-A fix 3: triple reported explicitly.)
Census primaries (v2, mass-dominant score-only rule): L5 ×124
(71 tasks), L4 ×16, UNKNOWN ×10 (6 tasks, all UNSCORABLE-same),
L0 ×2, L6 ×2 (color-tooling). Confidence: DIRECT 3,
STRONGLY_SUPPORTED 138, PLAUSIBLE 13.
Mod-loss partition (kind-pure, exact-sum): L5 28.13 (68%), L4
5.26 (13%), L0 2.34 (6%), L6 0.05, UNALLOCATED 5.69 (14%).
REG-loss partition: L0 1.00 (FM06_01), L5 0.60, L6 0.52 (color
tooling), UNALLOCATED 0.001.

First-error taxonomy: MOD:valued 75, REG:valued 64, MOD:output=None
13, scorer-XML 1, NONE 30 (exact-1 + rounding).

Per-cell full-error rollup (probe_fullerr, official code paths,
UNCAPPED full sets after Gate-A fix 1; 71/71 exact self-checks
derived==official; df44beb5-class rounding inversions verified
spurious by direct official-function rerun): 109,034 mismatches →
77,340 roots after cascade factoring. Root classes: REG COLOR_ONLY
69,473; MOD NUMERIC_VALUE 4,626; MOD MISSING 1,369 (330
partial-block, 1,043 untouched); REG NUMERIC 711; MOD SIGN_FLIP
368; REG OVERFILL 203; MOD STRING 159; MOD OVERFILL 97;
FORMULA_TEXT 125 (audited: 7 proven-equivalent L0 cells over 5
runs — RRI, SUMPRODUCT, sheet-prefix, C36×2 — never sole cause;
19_05 D6/E6 error-valued, no recovery implied); TYPE_OTHER ~100.
Root causes: 3,465 formula-differs, 23,294 formula-same, 50,397
value-only (color-dominated). Precedent closure (Q4): 336
upstream-proven (24 edited / 312 untouched), 3,164
precedent-matched; shape split (Q4b): OFFSET/array 86, named-range
947, positional 0, plain 2,270; exact-precedent sample 22/30 at
agent-scale magnitudes (sub-tolerance cascade, I29-archetype);
time-volatile same-roots: ZERO (exhaustive).
Footprints: recall median 0.966, precision median ~1.0 — failures
are content, not placement. Color preservation (official
comparator): 30,787 missed fixes (L5) vs 38,742 pipeline-destroyed
on value-untouched cells (L6) across 3 color runs.

Sampled mechanisms (19 trajectories, DIRECT forensics):
unpassable-as-scored empty MOD set (05_08 — scored bytes were
recalced; run-dir None caches a red herring), wrong-bug-theory
wholesale miss (07_03, recall 0.014), systematic scale error
(16_12 ×12), retained hardcodes (01_02), malformed input (FM
06_01), offset self-correction in successes (09_03, FM 11_01),
thorough near-misses (18_02, 11_02, 08_03 — upstream/cascade
residuals).

## Cross-population loss partition (score-bearing mass)

- EXPLAINED BY KNOWN MECHANISM: submit-hygiene stale cache (Pop A:
  3 exact-flips + 1 near + 4 partial V1 gains; closed → scaffold
  fix), malformed input (FM06_01: 1.0 mod + 1.0 reg), unpassable
  empty MOD set (05_08: 1.0 mod), evaluator artifacts where proven
  (B31 pre-existing, TODAY B4, 7 formula-equivalent cells),
  color-tooling destruction (L6: 0.05 mod + 0.52 reg), degenerate
  submits. Mod: L0 2.34 + L6 0.05 (+ hygiene part of L5/L0 Pop-A).
- LIKELY EXPLAINED (model reasoning, in-context evidence): L5
  28.13 (differs 3,465 roots + localized upstream + omissions) +
  L4 5.26 (untouched-target misses, 07_03 wholesale).
- UNEXPLAINED (explicit per-run UNALLOCATED, never forced): 5.69
  mod (UNSCORABLE same-formula shares where cache-vs-cascade is
  undecidable) + 0.001 reg + 10 UNKNOWN-primary runs (6 tasks).

## Category heterogeneity (preview)

- Template: tight-regime failures are hygiene (recoverable) or
  single-slip reasoning; loose-regime near-misses dominate.
- Financial_Model: tight-regime no-submit (assumption-discovery
  gaps + loops); loose-regime largest mod-loss pool (18.654).
- Debugging: zero exact-1 in either population's ordinary runs;
  misdiagnosis + partial fixes + formula-text artifacts; the only
  category with no demonstrated ordinary success.
