# Phase-12 promotion recommendations

## Promotion standard (§43) — applied per candidate

| # | criterion | ERR | UNIF-D3 | REF-D3 | CHG |
|---|---|---|---|---|---|
| 1 | deterministic/CONDITIONAL truth | CONDITIONAL (LO-recalc trust) | EXACT | EXACT | EXACT |
| 2 | meaningful exposure | 59 pairs, 4 positive | 59 outputs, 28 positive | 81/18 positive | 49 footprints |
| 3 | incomplete natural reach | 4/4 ≤R3 | 28/28 uncompared | all ≤R2 | 15/49 unreviewed |
| 4 | decision relevance | submit veto | revisit trigger | cascade diagnosis | revisit trigger |
| 5 | discrimination beyond warning | REDUCES ×1 + severity veto | REDUCES ×1 (3-cell) | REDUCES ×2 | DIRECTLY ×4 |
| 6 | tractable compute | 1 recalc, seconds | sub-second | seconds | sub-second |
| 7 | no authority leap | presence-only | break-only | delta-only | footprint-only |
| 8 | low-coupling surface | post-run analysis of frozen artifacts | same | same | same |

All four clear all eight bars. Promoted as ONE bundled treatment (they
corroborate: DCF!X9 sits at the intersection of three), not four separate
surfaces.

## Recommended Phase-12 treatment

**Post-edit verification evidence block**, computed offline from frozen
input/output artifacts at submit time (or on explicit verify request):

```text
POST-EDIT VERIFICATION (mechanical, gold-blind):
- new formula errors: 23 (#VALUE!), e.g. EPS_Accretion!B15...
- uniformity breaks introduced: 3, e.g. DCF!X9 (was uniform in LBO...)
- references that became blank: 18, e.g. ...
- change footprint: 27 formula cells changed/added
- one-hop context: X9 fed by ...; feeds ...
```

Framed as EVIDENCE with a veto-shaped question ("submit anyway?"), never
repair instructions. Control arm: identical task without the block. Primary
endpoint: submit-with-new-errors rate + scored-miss overlap with flagged
sets. Secondary: revisit rate, tokens/time cost of the check.

## Delivery surface (lowest coupling)

`analyze <run-dir>`-style post-run analysis over frozen artifacts (Phase-10C-A
extension point, first choice). No read-engine coupling, no live runtime
internals, no bootstrap changes. The block is a pure function of
(input.xlsx, output.xlsx) + recalc.

## Explicitly NOT promoted

- FAM-REL-FAMILY (infrastructure, not surface), TEMP-PERIOD-MAP (no
  demonstrated discriminator; bundle-only), ROLE-EQUIV-SET (zero leverage
  shown), DEP-DIRECT-REFS standalone (accessory only), CTRL-* (controls).
- Nothing semantic, nothing authoritative, nothing token-motivated.

## Sample-size caveat

Positive-case counts are small (4 error runs, 28 post-edit breaks, 18 blank
deltas). Phase 12 must pre-register decision thresholds and a larger run
budget; this census establishes the frontier's EXISTENCE (missed + exact +
linked), not its population rate. Do not cite 7% as a prevalence claim —
cite it as 4/59 observed with recalc-verified ground truth.
