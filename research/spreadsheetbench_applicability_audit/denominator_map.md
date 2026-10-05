# SpreadsheetBench-2 applicability — denominator map

Study term for the subset: **"controlled"** stratum (6 tasks,
SpreadsheetBench-2 provenance, original workbooks).

## Full study

```text
12 tasks (6 controlled + 6 curated)
└─ 18 trajectories (P×6 + O×12; A1/A2 amended, all scored)
   └─ 166 canonical block records (x2 arms = 332 RUNTIME_REPLAY rows)
      ├─ 1 unreplayable (r18 step 29: shell for-loop, triage-excluded from timing)
      └─ 165 replayable
         ├─ 1 skipped/non-executed (r18 step 47 block 1: 0 bytes, exit -1, wall 0.0)
         └─ 164 executed Python invocations
            ├─ 146 reference (REFERENCE_FAST_PATH)
            ├─ 10 fully direct (DIRECT_RUNTIME, each 1 served load)
            └─ 8 admitted-but-fell-back (DIRECT_WITH_FALLBACK, each 0 served loads)
```

Timing denominator: 165 rows/arm (122.82 / 125.27 s).
Prevalence denominator: 164 executed (admitted 18, useful 10).
Read-only AST: 136/165 replayable (report figure; includes the empty
record) = 135/164 executed.

## SpreadsheetBench-2-derived (controlled) subset

```text
6 tasks (Debugging 07_01/08_06, Template 07_01/03_02, FM 11_05/07_01)
└─ 9 trajectories (P×3 + O×6)
   └─ 138 canonical block records
      ├─ 1 unreplayable (r18 s29, in FM:07_01)
      └─ 137 replayable
         ├─ 1 skipped (r18 s47 b1, in FM:07_01)
         └─ 136 executed Python invocations
            ├─ 119 reference
            ├─ 10 fully direct (all study-wide useful service is here)
            └─ 7 admitted-but-fell-back (0 served loads each)
```

Timing denominator: 137 rows/arm (112.754 / 114.410 s).
Prevalence denominator: 136 executed (admitted 17, useful 10).
Static load sites (AST): 110. Direct reads: 13,989. Iteration cells:
9,302. Task exposure: 4/6. Trajectory exposure: 4/9.

## Term map (historical → audit)

| historical | audit |
|---|---|
| controlled (stratum) | SpreadsheetBench-2-derived subset |
| block (replay record) | canonical block record |
| runtime-usable block | replayable block |
| executed block | executed Python invocation |
| admitted (`admitted: true`) | admitted (classifier passed; ≠ served) |
| `DIRECT_RUNTIME` | fully direct (⟺ useful service here) |
| `DIRECT_WITH_FALLBACK` | admitted-but-fell-back (0 loads served) |
| `direct_served_loads` | directly served workbook loads |
| curated (strata read/mutation/mixed) | excluded from this subset |

## Rules for future writing

- Prevalence (routes, admission, service): executed denominators
  (164 full / 136 subset). Never 165/137.
- Replay timing: replayable denominators (165 full / 137 subset).
- Never present admission (17/136) as applicability; fallbacks served
  zero loads (7/7 in-subset, 8/8 study-wide).
- Task/trajectory exposure as counts (4/6, 4/9), not percentages.
- Operation counts (reads/cells) are depth context, never prevalence.
