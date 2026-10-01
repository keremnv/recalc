# Phase 13 — Best-Intermediate-State Analysis

Offline failure analysis only. No oracle is proposed for any live agent.

## Data limitation

No intermediate workbook snapshots are retained (research debt #2).
/tmp recalc copies described in transcripts were never preserved.
Best-state claims below rest on: retained final outputs, V0/V1
score pairs, and transcript-described (unretained) artifacts.

## Proven best-state gaps

| Run | Best state | Final submitted state | Gap cause |
|---|---|---|---|
| FM:12_01 CONTROL | output.xlsx on disk, V1 exact 1.0 | no-submit, exact 0 | Chose verification over submit until wall death (L7) |
| 06_05/06_09/06_16-class (3) | /tmp LO-recalc copy, values correct (unretained) | stale output.xlsx, exact 0 | Submitted the wrong file (L0/L7) |
| 06_25/10_02/11_01/11_03-class | /tmp copies correct-or-near (unretained) | stale output.xlsx | Same wrong-artifact pattern |

## Monotonicity

- Submitted runs: inspect → write → verify → submit; monotonically
  improving on every retained artifact. No improve-then-regress case.
- 12_01: monotonically improving until wall death; never submitted.
- 18_03: improving at death (self-fix in final action).
- No trajectory shows a retained better state followed by a
  retained worse state. Overwork-as-damage (§36) is unobserved.

## Conclusion

Best-state losses exist but are all **submission-boundary**
losses (never-submit / wrong-file-submit), not overwork damage.
They are addressed by the earned scaffold fix
(recalc-before-submit + submit-the-verified-file), not by any
checkpoint/oracle mechanism. No gold-blind condition is needed
because no regression-from-best is observed.
