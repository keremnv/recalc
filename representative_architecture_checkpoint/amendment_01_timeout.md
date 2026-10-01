# Methods amendment 01 — request deadline 90s → 240s (2026-09-22)

## Observation (before any 240s outcome exists)
- 280s curl of a deep-history request (Debugging:10_07 H1, 84K prompt
  tokens): HTTP 200, valid tool call, 126s wall. Slow-finite (Class S),
  killed 3x by the 90s absolute request deadline → slot censored.
- 280s curl of an early-history request (Template:01_06 H0): HTTP 200,
  1034 whitespace bytes, never completes. Non-terminating (Class W).
- 12 completed slots show 1–2 tolerated 90s timeouts: the 90s value is
  binding on this workload (deep histories need >90s), not just on
 -provider-outage. It was tuned for a faster regime (~5s/call).

## Change (arm-symmetric, predeclared)
- `base.CHAT_TIMEOUT = 240` set by `benchmark/representative_checkpoint.py`
  at import (process-local; no change to `ab_local_runner.py`, no change
  to any other harness).
- Applies to all subsequent attempts in BOTH arms. Nothing else changes:
  model, prompts, schemas, budgets (40 calls, $0.25/instance, 900s run),
  3-strike transport rule, H0/H1 invisible flags all frozen.

## Wave structure
- Wave A (90s deadline): main 4-worker run + parallel/serial retries up to
  2026-09-22 ~05:30 UTC. All completed SUBMITTED/NO_SUBMIT/TRUNCATED slots
  stand as measured. All Wave-A PROVIDER_CENSORED slots except
  Template:01_06 (both arms, Class-W proven: 0/8 attempts + whitespace
  trickle proof) and Financial_Model:06_01 H1 (deterministic substrate
  XML crash, stands as RUNNER_ERROR) are re-released for Wave B.
- Wave B (240s deadline): serial chain over re-released slots only.
- Reporting: censoring tabulated per wave; pooled arm comparison unchanged
  (deadline identical across arms within every wave).

## Falsification guard
- If Wave-B deaths replay as non-terminating at 240s+, they are Class W
  and stand as provider-unrunnable. No further deadline changes: 240s is
  final for this checkpoint.
