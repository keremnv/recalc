# Phase 9 preregistration amendment 4 — restore cold gate staging

Status: recorded after the third unscored gate attempt, before any scored run.

With the correct frozen Phase-8A H0 arm and certificate comparison, `Template_16_07__9662584ede5e` passed all output, class, certificate, and fallback checks. Its cold artifact witness was `REUSED`, whereas the frozen protocol requires `BUILT`. The earlier failed gate attempts had created artifacts under the same `runs/gate` staging paths. This is contaminated benchmark staging, not a treatment semantic difference.

Preserve the third failed gate rows and move the entire `runs/gate` staging tree to `runs/gate_attempt_3`. Rerun the complete gate against a newly absent `runs/gate` tree, restoring the originally specified cold and second-invocation artifact states. No population, treatment, benchmark code, timing endpoint, order, or decision rule changes.
