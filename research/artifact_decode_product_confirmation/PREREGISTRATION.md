# R6 D1 confirmation — preregistration

Written and hashed BEFORE confirmatory scoring. Baseline: rc4 `fed04b5`.
Candidate: D1 per `CONTRACT.md` (R5 `be806c3` delta, D1 only).

## 1. Semantic gate (all must pass)

- 52/52 canonical workbook-state equality, pristine rc4 decoder vs
  merged D1, on frozen A/B artifacts (identity-independent comparison).
- 40/40 adversarial certification (R3/R5 suite) vs pinned openpyxl,
  same routing/exit/normalized-streams/state/exceptions; no weakened
  normalization.
- 52/52 full-command A/B behavioral parity (exit, normalized stdout,
  workbook state, route, fallback, artifact status).
- Maintained product tests green; full suite with no new failures
  (4 documented pre-existing failures excepted).

## 2. Corruption gate

All 12 R5 cases reject identically on rc4 control and D1 (truncated
header/payload, wrong checksum/source-hash/decoder/format versions,
corrupt stream/structure, dup coordinates, impossible kind/value/
coordinate, NaN/non-finite numerics). No silent serve.

## 3. Economic gate (Population A, warm reused artifacts, paired)

- Decode-mass reduction ≥25% relative AND ≥1.0 s absolute.
- Full-command improvement materially tracks decode (no disappearance).
- Non-regression: no workload worse than +0.083 s candidate-vs-rc4
  control (R3 rule; never vs bare BASE). Noise floor: R1 G5 41.5 ms
  repeatability; R5 order-bias evidence (±50–120 ms small-workload
  straddles).
- R5 absolutes (5.272→2.036 s decode, 15.244→11.848 s wall) are
  historical reference only; the gate uses this window's paired gains.

## 4. Order-bias rule (predefined, §12)

- Arms alternate by workload index: even → rc4 block first, odd →
  D1 block first. Each arm: warmup + 3 reps, medians.
- Any >83 ms flag is re-run once with opposite arm order. A flag
  counts as genuine ONLY if it persists under reversal. Flags on
  workloads whose path never invokes artifact decode are diagnosed
  as noise/harness contamination first.
- No selective re-running outside this rule.

## 5. Compatibility gate

Artifact bytes unchanged; format unchanged; rc4-built artifacts
REUSED under D1 with correct semantics; D1-built artifacts
byte-identical to rc4-built; no migration; no cache clear required
by D1; no new dependency; no admission/routing/API change.

## 6. Build/cold gate

Encode path unchanged by construction; cold walls show no systematic
D1 regression (apparent large cold deltas investigated as
noise/order variance first; tripwire: >50% cold regression on any A
workload without such explanation fails the gate).

## 7. Verdict

PRODUCTIZE iff all gates pass. CLOSE on failed reproduction or
unacceptable risk. REVISE_AND_RETEST only for a narrow mechanical
defect with an obvious correction. No new criteria after data.

## 8. Post-PRODUCTIZE version note (recorded before scoring)

`RUNTIME_VERSION` (package `__version__`) participates in
`artifact_key` and sidecar validation, so an rc4→rc5 bump
mechanically invalidates rc4 artifacts (one-time rebuild) even though
D1 is byte-compatible. This is existing key policy, not a D1
requirement; if PRODUCTIZE, document the rebuild rather than
redesigning identity in this phase.
