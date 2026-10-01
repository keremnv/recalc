# Phase 9 preregistration amendment 2 — gate comparator correction

Status: recorded after the first unscored representative gate stopped, before any scored run.

The first gate passed both invocations of `Template_15_03__5ad5663409d0` and stopped at the cold invocation of `Template_16_07__9662584ede5e`. All three output comparisons for that invocation were `EXACT`; the direct-contact classes, artifact `BUILT` witnesses, and reference-fallback reasons agreed. The gate's `direct_stable` check was false because `read_engine_phase8a.validation_runner.command` stores the H0 certificate in `result["certificate"]`, while the Phase-9 wrapper additionally stores the H1 certificate in `result["merged_certificate"]`. The Phase-9 gate compared `H0["merged_certificate"]` (absent) to `H1["merged_certificate"]`.

Correct only this experimental comparator to compare `H0["certificate"]` with `H1["merged_certificate"]`. This does not change either treatment, the frozen population, the semantic rule, timing, repetitions, ordering, endpoints, or decisions. Preserve the failed gate rows as `gate_attempt_1_*` and rerun the entire correctness gate before any scored timing. The implementation identity manifest is rehashed before that rerun.
