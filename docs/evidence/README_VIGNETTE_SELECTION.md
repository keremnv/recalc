# README vignette candidate selection

Mechanical analysis before choosing the performance vignette. Ranking order
(per task §5): 1. correctness/semantic parity, 2. public provenance,
3. understandable scenario, 4. absolute time saved, 5. percentage, 6. visible
sheet effect.

## Candidates

| # | Task/workload | Provenance | Publishable? | Prompt clarity | Workbook visual | Read op | Route | BASE | RECALC | Saved | % | Parity | Visible effect? | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | FM:08_02 scan, `Financial_Model_08_02__4ca3ae46295d` (R3 pop A) | SpreadsheetBench-2 (public: site/arXiv/HF), agent scan step | Yes + attribution | High: "Complete the financial model… in blue" (Project Seafood Model) | High: 13-sheet model, Assumptions tab | iter_rows 120×40, 4800 cells | DIRECT 3/3, REUSED | 5.3035 s med | 1.6696 s med (rc4; reproduce on 0.2.0) | 3.6339 s | −68.5% | 52/52 differential + stdout parity | Read-only step: scanned region, no writes | **SELECTED** |
| C2 | FM:08_02 scan, `__625ec1db4acb` (Capex tab) | Same | Yes | High (Capex-link subtask) | High | iter_rows 200×40 | DIRECT 3/3 | 5.475 med | 1.560 med | 3.915 s | −71.5% | Same | Read-only | Runner-up; Line-01 tab matches instruction verbatim, cleaner story |
| C3 | Debugging_10_10 (R3) | Same benchmark, Debugging family | Yes | Medium: error-hunt scan of 'Model' | Medium: dense dump | iter_rows 200 rows | DIRECT 3/3 | 24.597 | 1.729 | 22.867 s | −93% | Same | Read-only | Rejected at rank 3 (scenario clarity) despite larger absolute |
| C4 | Debugging_04_07 (R3) | Same | Yes | Medium | Medium | iter_rows | DIRECT 3/3 | 2.907 | 0.508 | 2.399 s | −82.6% | Same | Read-only | Rejected: smaller savings + less clear scenario than C1 |
| C5 | Tier-1 r06 slice (5 direct + 1 save) | Tier-1 replay (public-transcript? local) | Partial (prompts in benchmark; transcripts local) | Medium | Low (small books) | Small direct reads | DIRECT (5 inv) | ~0.3–0.6 s/inv deltas | — | ~2.2 s traj total, noisy | mixed | Replay parity | Save exists, small | Rejected: sub-second steps (§12) + BASE hook-contaminated, not same-window A/B |
| C6 | Tier-1 r01 slice (3 direct + 1 save) | Same | Partial | Medium | Low | Small direct reads | DIRECT (3 inv) | deltas +0.16..+0.76 s | — | <1 s | mixed | Replay parity | Save exists, small | Rejected: same as C5 |
| C7 | C_674 (FM:03_01 agent read+write) | Control-audit agent script (real code) | Unclear (transcript-derived) | High (banking ratios) | High (2 MB model) | 13.1 s parse + 350 writes + save | REFERENCE (admission rejects mutation) | — | — | 0 | 0% | n/a | Would write, but no benefit | Rejected: no direct participation (admission A0 boundary) |
| C8 | Changed-file fixtures (×5) | Project-authored | Yes | High | Low (tiny) | n/a (write-only) | n/a | full-cmd ~1.6× overhead | — | negative | +60% | Exact cell parity | Exact changed cells | Rejected: no speedup (assurance cost) |
| C9 | Curated T1_R1 trajectory | Project-authored (in git) | Yes | High | Medium | Small reads | all REFERENCE | — | — | 0 | 0% | Golden parity | Writes exist | Rejected: no direct participation |

## Decision

C1 wins mechanically: parity ✓ (rank 1), public provenance ✓ (rank 2, tie C1–C4),
understandable scenario (rank 3: named business model + instruction naming the
scanned tab verbatim; beats C3/C4), absolute 3.63 s (rank 4; C3 larger but already
eliminated at rank 3 per the ordered ranking — not by percentage).

## Honest limitations of the selection (carried into README)

- The frozen step is read-only: no changed cells exist. The vignette shows the
  scanned region (cells served directly, values identical) and states plainly that
  this step performs no writes. No write row, no fabricated effect.
- Timing is reproduced on 0.2.0 (faithful R3 protocol: warm cache, warmup + 3 reps,
  same window, fresh workdirs) because R3's ON arm ran the rc4 candidate; R3 frozen
  medians are retained as cross-check. No product behavior affecting this workload
  changed except the parity-held rc5 decode improvement.
- Tier-1 (mixed-workflow) aggregate shows no Recalc speedup; README carries that
  limitation explicitly (§18).
