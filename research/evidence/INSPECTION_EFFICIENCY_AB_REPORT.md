# Stage B: Inspection Efficiency — Report

Question: can deterministic compiled workbook reads replace repeated
Python/view-based inspection work while preserving capability and semantic
freedom? C0 = transparent runtime + ordinary tools; C1 = C0 + optional
`lx_helpers` (periods/search/inspect) with a minimal usage note. Python fully
available in both; nothing mandatory; no tools removed.

**Verdict: INSPECTION_HELPERS_EFFICIENCY_EARNED** (per-helper below; inspect
carries a breadth caveat).

## Capability gate: PASS

r1 (9 tasks): 5 discordant cells (3 against C1, 2 for C1). Per policy all 5
repeated once. Every r1 split reversed or converged in r2:

- FM:01_01: r1 C0-output/C1-stall → r2 both stall (40 calls each).
- FM:13_05: r1 C0-stall/C1-output → r2 both complete (C0 mod .65, C1 .03,
  C1 r2 made 0 helper calls — pure variance).
- Template:01_02: r1 C0-strong/C1-stall → r2 both complete (C1 mod .69).
- Template:06_12: r1 C0-stall/C1-output → r2 identical (mod 0, reg 1.0).
- Template:01_07: r1 C0-output/C1-stall → r2 both stall (6 calls each).

No systematic C1 loss; no helper-attributable damage (all deltas classify
UNRELATED_MODEL_VARIANCE; the one C1-adopting completed run matches its
twin). FM:02_01 identical both rounds.

## Adoption (natural, unforced)

33 logged helper calls in 3 of 14 C1 runs, all Financial_Model:

- FM:13_05 C1 r1: 6 iterative `search` refinements (Borrowing → Rate
  variants) driving inspection; completed while C0 twin stalled.
- FM:01_01 C1 r1+r2: `periods` + 12 `inspect` range-prints as the primary
  inspection loop, replacing openpyxl print-loops one-for-one.
- Template r2 C1: imported but bypassed (0 executions).
- Debugging C1: never imported.

## Work removed

Per-arm totals (14 runs each): C1 −51% view_xlsx calls (56 vs 115), −40%
tokens, −37% cost vs C0; walltime tied. Helper calls add python execs
(+48%) but displace longer view observations. Evidence-equivalence: all
adopted calls classify EXACT_REPLACEMENT (same address/value/formula facts,
less mechanical work). Aggregate gap partly reflects stall mix; trajectory
evidence supports attribution on adopting runs.

## Freshness

Every call logged workbook/index/query generations; rebuild-on-mismatch
verified in tests; zero stale serves; zero model-visible helper errors.

## Failure inventory

One DELTA_CONSTRUCTION telemetry bug found live: created packages with
explicit zip directory entries failed replay (empty-image deletion sentinel
collision). Telemetry-only — committed bytes always equaled Python-produced
(persisted=true), zero score effect. Fixed with explicit deleted flag, 8/8
runtime tests pass including a new regression test, all 15 Stage-B outputs
re-verified part-exact.

## Helper verdicts

- `search`: EARNED (iterative refinement, exact text-scan replacement).
- `periods`: EARNED (exact header-scan replacement, 2 runs).
- `inspect`: EARNED with breadth caveat (12-call exact replacement loop in
  1 run; re-confirm breadth in the next probe).
