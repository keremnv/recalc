# Phase 13 — Resource Allocation Analysis

## Where the budget went (Population A, per run_record efficiency)

| Run class | Calls | Tokens | Cost | Wall | Writes |
|---|---|---|---|---|---|
| Submitted Template (8) | 7–15 | 33K–205K | <$0.05 | 150–910 s | yes |
| Truncated cost (8) | 30–39 | 1.3–1.7M | ~$0.25 | 80–770 s | 0 |
| Truncated call (4) | 40 | 1.3–1.6M | ~$0.20–0.24 | 135–815 s | 0 (17_05 excepted) |
| NO_SUBMIT wall (14) | 10–32 | 80K–1.2M | $0.03–0.20 | ~900–1060 s | 0 (12_01 excepted) |

## Patterns

1. **Context bloat per call**: truncated runs average ~40–45K
   tokens/call — the transcript accumulates every full-sheet dump.
   Cost death is token death: each additional scan makes the next
   call more expensive (calls 30–39 cost ~$0.01 each vs ~$0.0002
   for call 1).
2. **Repeated opens**: 10–30 workbook opens per truncated run (every
   bash inspection re-loads). No run amortized a single load.
3. **Ramble burn**: max-length generations (~195 s, ~$0.0045 each)
   consume wall-time without evidence or action (01_03, 15_02,
   03_01-pilot).
4. **Slow-tool wall death**: some NO_SUBMIT runs die with budget
   unspent (07_02: 16 calls, $0.075, 1031 s; 10_01: LO call) —
   wall-time, not tokens, is the binding constraint.
5. **Successful runs are cheap**: all Pop-A submits cost <$0.05
   with ≤15 calls. Success and failure separate early: runs that
   act by call ~5 submit; runs still scanning at call ~15 never do.

## Search-cost vs reasoning-cost (§21)

| Cluster | Dominant cost | Evidence |
|---|---|---|
| Truncated inspection loops | Search/discovery spend, reasoning-dominated failure | Targets already inspected (coverage 1.0); spend continues without action |
| Ramble traps | Reasoning-dominated (runaway generation) | No tool calls; no evidence sought |
| Submitted stale-cache | Verification-dominated | Work correct; submit-hygiene step missed |
| Formula residuals (11_03/11_04/14_03) | Reasoning-dominated | Evidence present; wrong choice |
| Debugging misdiagnosis (05_08-class) | Reasoning-dominated | Saw bug; misjudged/didn't recognize |
| 16_12 annualization | Reasoning-dominated | Units in labels; 5-call rush |

## Comparison against successful runs (§13)

- P1 exact-1 runs (29) and Pop-A V1-recovered runs show the same
  early pattern: 1–3 views, targeted dumps, write by call ~5,
  LO-verify, submit. Total: <15 calls, <$0.05.
- Failed runs differ BEFORE any divergence point in exactly one
  consistent way: they do not write by call ~10. Everything else
  (view choice, dump style) overlaps with successes.
- The missing behavior (early write attempt) is therefore
  *correlated* with success, but a causal "write earlier" probe
  would be a scaffold behavior-shaping intervention, not a
  mechanical primitive — and phase 12's sham arm already showed
  neutral nudges change behavior without improving decisions.

## Implication

The spend profile (re-scans, re-opens, bloat) looks mechanizable,
but the program already tested that slice: Stage-B inspection
helpers displaced scan loops where adopted yet produced no
arm-level gain, and agents bypass equivalent helpers. The residual
question — why inspection doesn't convert to action — is a model
capability question (planning/initiation under uncertainty), not a
tooling question. No new resource primitive is earned.
