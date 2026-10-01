# Phase 13 — Stopping and Regression Analysis

## Completion-detection failures (§33)

| Run | Mode | Evidence |
|---|---|---|
| 04_06, 08_06 CONTROL | Stop too early (degenerate) | Submit at call 1, zero inspection, no output |
| 12_01 CONTROL | Never submit despite valid workbook | Exact-correct output on disk; kept verifying until wall death |
| 17_05 CONTROL | Never submit (couldn't finish) | Call cap consumed by XML debugging; output corrupt |
| 18_03 CONTROL | Never submit (work in progress) | Building + fixing at wall death; work in /tmp only |

No run in either population shows "keep editing after correct
state and overwrite correct work" with a retained workbook proving
the regression — the overwrite-regression class (§34) has zero
DIRECT cases. 05_08 (Pop B) reverted its own L15 rewrite, but the
revert restored the gold formula (correct behavior, not damage).

## Best-intermediate-state analysis (§35)

No intermediate snapshots are retained (research debt #2), so this
is indirect:

- **12_01**: best state (final output.xlsx) scores V1 exact 1.0;
  submitted score 0.0 via no-submit. Best-vs-final gap = 1.0 exact.
  The ONLY proven best-state loss in the corpus.
- **18_03**: /tmp artifacts unretained; trajectory shows a
  self-found bug fix in the last action — best state unknown, final
  unsubmitted.
- **06_05-class**: intermediate /tmp recalc copies were
  score-correct; submitted originals were stale. Best-state gap =
  full recovery (V1 − V0), caused by submitting the wrong file.
- **Monotonicity**: submitted runs improve monotonically (inspect →
  write → verify → submit). No trajectory shows improve-then-regress
  on retained artifacts.

## Overwrite regressions (§34, §36)

Verdict: **not observed as a loss class**. Zero runs demonstrably
reached a better scored state and later degraded it on a retained
artifact. The stopping problem in this corpus is one-directional:
under-stopping is rare and degenerate (empty submits); the mass is
in never-submitting (L8) and wrong-artifact submitting (L0/L7).

A future stopping probe (checkpoint/oracle-adjacent) is therefore
NOT warranted: there is no regression mass for it to recover, and
12_01-class events (n=1 proven) are too rare to carry a mechanism.
The earned stopping fix is scaffold-level recalc-before-submit
(phase-12 D-demote follow-on), which addresses the 06_05-class
wrong-artifact submits without any gold-blind checkpoint.
