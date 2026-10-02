# Phase 13 — No-Submit Analysis

## Population A (tight budget: $0.25 / 40 calls / 900 s): 28/40 without valid submission

| Terminal class | n | Mechanism |
|---|---|---|
| TRUNCATED_INSTANCE_COST | 8 | Inspection loop burned $0.25 (1.3–1.7M tokens, 30–39 calls, 0 saves) |
| TRUNCATED_CALL_LIMIT | 4 | 40-call inspection loop (03_03, 05_04, 10_05) or XML-debug saga (17_05, output corrupt) |
| NO_SUBMIT, no output | 14 | Wall-time death: inspection loops (11), ramble traps (01_03, 15_02, 03_01-pilot), work-in-progress (18_03) |
| NO_SUBMIT, output on disk | 1 | 12_01: V1-exact workbook (ambiguous recalc class), over-verification loop, wall death |
| SUBMITTED, no output | 2 | 04_06, 08_06: degenerate 1-call submits |

## Mechanism split (primary L8 unless noted)

- **Inspection loop without action (19 runs)**: repeated full-sheet
  dumps / formula prints; zero writes; dies at cap or wall-time.
  Coverage probe: most had already inspected the gold-mod regions
  (8 runs at 1.0 on all mod sheets) — this is NOT primarily a
  discovery failure. Secondary L3 (couldn't convert observation
  into a fix plan) where coverage is full; secondary L2 where
  named sheets were never opened (12_05 Valuation; 08_0x
  Assumptions; 03_03 Valuation Bridge/Ex8/Ex9; 10_0x FY tail).
- **Scale overwhelm (10_03, 10_01, 10_04, 10_05, 10_06)**: ~2000-row
  multi-sheet footprints; 10_06 covered ~80%+ and still never wrote.
- **Ramble trap (01_03, 15_02, 03_01-pilot)**: 5–7 max-length
  generations with no tool call; wall-time consumed by ~195 s
  generations (phase-12 A1 phenomenon). 15_02 additionally never
  inspected its target sheet (L2 secondary, DIRECT).
- **Work-in-progress death (18_03)**: building + self-debugging at
  death; recoverable with more time.
- **Degenerate submit (04_06, 08_06)**: L7, not L8 — submitted with
  no inspection at all.
- **Correct-work no-submit (12_01)**: L7 PRIMARY — V1-exact workbook
  (ambiguous class; "perfect" hedged per Gate-A fix 8), chose
  verification over submit until wall death.

## The budget-regime contrast (do not pool)

- Tight regime (Pop A): 70% no valid submission.
- Loose regime (Pop B parents, $4.00/50 calls): retained archive is
  conditioned on submission, so no clean rate exists — but 183
  ordinary submissions including 41 Debugging show the same task
  families ARE completable with ~16× budget.
- Within Pop A, submitted runs used 7–15 calls and <$0.05; truncated
  runs used 30–40 calls and ~$0.20–0.26. The margin between "enough"
  and "starved" is task-dependent, not a fixed number.

## What the model spent its budget on (§20)

- Repeated full-sheet scans (same iter_rows dumps across calls).
- Repeated workbook opens (every bash call re-loads; 10–30 opens).
- Ramble generations (no new evidence, no tool call).
- Verification loops after correct state (12_01; 18_03's /tmp loop).
- Off-task drift in 2 runs (repo greps in 08_05, 16_05).
- Zero runs spent budget on formula debugging loops against scored
  cells — because none reached the write stage except 18_03/12_01.

## Conclusion

No-submit in the tight regime is an **L8 resource-allocation
failure with an L3 action-initiation gap inside it**: agents that
find the region but cannot turn observation into a first write
before the budget dies. More budget converts an unknown fraction
(the loose regime proves the category is convertible, not the run).
This is the largest single loss mass in Population A and the
strongest candidate for verdict D — but see the frontier analysis
for why "more budget" is not a research probe and why no
mechanical primitive is earned by it (Stage-B helpers already
tested the mechanizable slice and found no arm-level gain).
