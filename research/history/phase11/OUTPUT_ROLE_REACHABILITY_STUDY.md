# Output-role reachability study (C5 → ROLE-EQUIV-SET, D2, CONDITIONAL)

Mechanical definition (gold-blind): columns/blocks whose translated formula
signatures repeat (≥2 bands, ≥2 distinct fingerprints per band). Pure
structural analogy — no role names, no ontology.

## Prevalence

78/146 readable inputs (53%) contain repeated output columns. Pervasive in
Debugging/FM layouts (repeated forecast/segment blocks).

## Natural reachability (n=78)

R1=1, R2=76, R4=1. Agents essentially NEVER compare repeated blocks
structurally (reach rate 1%). The single R4 is genuine
("S9 should sum both segments like the other forecast columns" + fix) —
an eyeball analogy, not computed. Modal behavior: view each block
separately, fix locally.

## Failure linkage / discrimination

- Linkage: PLAUSIBLY_LINKED 45/78 by the mechanical rule (failed + missed
  + finding exists) — but this overstates: with 53% prevalence and ~0%
  reach, almost every failure is "consistent with" the miss. Discrimination
  is GENERIC throughout; no case shows the role set picking the correct
  target over alternatives.
- The honest reading: ROLE is a context-broadening fact, not a
  discriminator. It answers "what else looks like this" — useful when the
  agent fixes one block and forgets its twin. Zero observed twin-fix
  failures were isolated in this census (miss cells are singletons in
  eval_error), so the mechanism is unproven here.

## Interpretation

MISSED BUT NON-DISCRIMINATIVE. The reach gap is real and extreme (1%),
the fact is cheap and mechanical — but no decision leverage was
demonstrated: no failure was shown to turn on the missing analogy, and the
finding sets (column lists) do not localize misses. Historical planner
effects remain the only motivation, and they were narrow. Do not promote.
Revisit only if a future corpus yields twin-block failures with the
analogy as the unique discriminator. No role ontology.
