# Phase 13 — Formula Failure Analysis

Failure-mode split for runs that wrote formulas (§32). Per-cell
mass figures come from probe_fullerr (Population B) and V0/V1
pairs (Population A).

## Population A (12 outputs + forensics)

| Mode | Runs | Detail |
|---|---|---|
| Correct formulas, stale submit | 06_05, 06_09, 06_16, 06_25, 10_02, 11_01 | V1 recovers to 1.0/0.96+; L0/L7, not formula errors |
| Wrong source cells | 11_04 (rows 24 vs 26), 11_03 (D19 empty) | L5; 11_04 systematic across 5 columns |
| Wrong operator/sign | 14_03 (C48 missing negation), 11_04 (C33) | L5 single slips |
| Reference omitted | 11_04 (D26:H26 blank), 11_03 (C19, C35/D35) | L5/L4 |
| Value instead of formula | 0 observed | — |
| Correct formula, wrong coordinate | 0 observed (offsets self-corrected in successes) | — |
| Correct formula, evaluator/cache issue | 06_05-class (stale), 16_02 B4 (TODAY volatility) | L0/L9 |

## Population B (full-error rollup complete)

All-cell enumeration over 154 fails (official comparison code):
2053 assessed roots. Class mix (roots): MOD NUMERIC_VALUE 1274,
MOD MISSING 493 (86 partial-block, 205 untouched-block), REG
NUMERIC 346, COLOR_ONLY 264, REG OVERFILL 170, MOD SIGN_FLIP 117,
FORMULA_TEXT 79 (38 non-VALUE-mode audited: 5 proven-equivalent
L0 cells, rest genuine L5), TYPE_OTHER ~100, STRING ~19.

Mod-loss allocation (sums exactly, no double count): L5 30.25
(73%), L4 3.32 (8%), L0 2.0 (5%), UNALLOCATED 5.90 (14%,
unverifiable-cache shares in UNSCORABLE rows).

Sampled-trajectory forensics:

- 16_12 (mod 0.0): systematic missing ×12 annualization — wrong
  operator/scale across a whole block (L5, reasoning-dominated).
- 05_08 (mod 0.0): assessed MOD set EMPTY (formula-only gold
  fixes invisible under data_only scoring) — exact unpassable as
  scored (L0). The agent actually fixed L12/L14 exactly as gold
  (trajectory-verified); C22 miss is moot. Run-dir None caches are
  a red herring (scored submission copy was recalced).
- 01_02 (mod 0.94): residual includes formula-text-identical
  mismatches (D8:D8 vs D8 — L0 evaluator normalization).
- 04_01 (mod 0.99), 08_03 (mod 0.9955), 11_02 (mod 0.9765):
  small-residual near-misses (fullerr details pending).
- 06_01 FM (mod/reg 0.0): malformed benchmark input (dc prefix) —
  not a formula failure at all (L0).
- Successes (09_03, 11_01 FM): offset self-correction during
  verification; formula content right.

## Reasoning vs mechanics (§22 lens)

Every formula-content residual in the sampled set had the deciding
evidence in context (labels with units, visible buggy formulas,
same-row patterns). None required a fact the agent lacked tooling
to obtain — 07_03 dumped the entire workbook then fixed the wrong
bugs; 16_12 read the units and dropped the factor anyway. The
formula-generation failure is **model reasoning**
(operator choice, sign convention, scale factor, bug recognition),
not mechanical formula-writing ability: agents write complex
INDEX/MATCH/NPV formulas fluently and debug their own script bugs
(18_02, 18_03 FM).

## Conclusion

No formula-generation primitive is earned. The residuals are
semantic (which operator, which scale, which cell is buggy) and
the program's formula-shaped hypotheses (family, fingerprint,
error feedback as product) are closed/frozen. Sign/scale slips at
0.98+ mod are below any probe's discriminating power.
