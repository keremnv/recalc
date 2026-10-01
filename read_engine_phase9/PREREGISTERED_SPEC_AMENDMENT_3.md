# Phase 9 preregistration amendment 3 — frozen H0 arm correction

Status: recorded after two unscored gate attempts stopped at the first direct-contact workload, before any scored run.

The Phase-9 runner passed its arm name `H0` directly to `read_engine_phase8a.validation_runner.command`. In that frozen runner, `H0` denotes the older Phase-6 observer without the hardened Phase-8A merged-cell certificate; `H1` denotes the frozen Phase-8A candidate. Phase 9 specified its own `H0` as the latter. The second gate attempt exposed this mismatch when H0's certificate was absent. The affected cold row had exact observable output, but it was the wrong causal control.

Correct the Phase-9 wrapper to pass `H1` to the Phase-8A runner for both Phase-9 `H0` and Phase-9 `H1`. For Phase-9 `H0`, leave the frozen Phase-8A overlay in place. For Phase-9 `H1`, temporarily substitute only the Phase-9 overlay. Pass `PY` through unchanged. This restores the originally preregistered arms; it changes no treatment code, population, timing endpoint, order, repetitions, or decision rule.

Preserve the failed gate rows as `gate_attempt_2_*`, repin the corrected runner, and rerun the complete correctness gate before scoring. The Phase-8A code and evidence remain frozen.
