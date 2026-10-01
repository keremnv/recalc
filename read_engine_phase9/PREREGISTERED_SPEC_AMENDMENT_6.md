# Phase 9 preregistration amendment 6 — abrupt diagnostic route assertion

Status: recorded after the first unscored abrupt changed-file diagnostic, before any eligible scored run.

The `exit_after_save` H0/H1 execution preserved identical package state, target exit, observer receipt and successful capture. The diagnostic's ad hoc assertion incorrectly required **both** arms to emit Phase-9 `FAST_PATH_PROVEN_REFERENCE`. Frozen H0 correctly emits `REFERENCE_RUNTIME` and has its runtime installed; only H1 should emit the new fast-path witness. Preserve the first diagnostic row as `abrupt_exit_attempt_1.jsonl` and rerun both abrupt cases with arm-specific route assertions. No treatment, population, benchmark endpoint, or decision rule changes.
