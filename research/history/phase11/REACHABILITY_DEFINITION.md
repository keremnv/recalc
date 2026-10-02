# Reachability definition — Phase 11

## Natural reachability

A candidate fact counts as naturally reached only if the agent obtains an
equivalent fact **before the relevant decision**, evidenced by:

- Python code in the transcript computing it (bash `python -c`, heredoc,
  or executed `.py` whose content is in-transcript or in the rep dir);
- tool output explicitly containing it AND a subsequent agent message or
  action depending on it;
- a model-visible observation the agent requested, followed by use;
- a script conditional branching on it;
- explicit model reasoning from the equivalent relationship after obtaining
  supporting data (conservative: vague "pattern" talk without the
  supporting query does not count).

Do NOT count: accidental presence in an unused giant dump; post-decision
computation; evaluator/gold knowledge; inferred "probably noticed".

## R-levels (per candidate × decision event)

- R0 — required world state did not yet exist (e.g. post-recalc error
  before any edit).
- R1 — computable from available state; agent never sought equivalent
  evidence.
- R2 — raw supporting evidence inspected (cells/state seen) but the
  derived relation not computed.
- R3 — relation partially derived, decisive fact missing.
- R4 — equivalent fact independently obtained (semantic equivalence per
  §25; formatting may differ).
- R5 — obtained AND demonstrably influenced the next relevant action.

## Decision-bearing events (coded moments)

`CHOOSE_TARGETS`, `CHOOSE_SOURCE_PERIOD`, `COPY_FORMULA`,
`DECLARE_COMPLETE` (repair-complete claim), `SUBMIT`, `REVISIT_REGION`
(post-change return to a region), `VERIFY_AFTER_EDIT` (explicit post-mutation
check). Each matrix row binds candidate × event × run.

## Failure linkage (gold used only to classify)

- DIRECTLY_LINKED: the error is the fact's negation (e.g. submitted workbook
  contains the new #REF! the agent never checked).
- PLAUSIBLY_LINKED: error consistent with the miss; other explanations open.
- UNRELATED / UNKNOWN.

Linkage is observational, never causal.

## Counterfactual discrimination (offline, gold-blind generation)

- UNIQUE_DISCRIMINATOR: fact alone picks the correct action.
- REDUCES_CANDIDATE_SET: fact narrows options materially.
- GENERIC_WARNING_ONLY / NO_DISCRIMINATION.

## Mechanical certainty

EXACT (deterministic from available state) / CONDITIONAL (exact given a
stated, checkable condition) / HEURISTIC / SEMANTIC. Only EXACT/CONDITIONAL
advance.

## Trivial-Python baseline bins

`1-3 LINES`, `4-10 LINES`, `11-30 LINES`, `>30 LINES`,
`MULTI-STAGE / RECALC REQUIRED`, `PACKAGE/XML SPECIALIZED`.
Discovery cost coded separately from implementation cost.
