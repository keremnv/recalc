# Formula family study (C1 → FAM-REL-FAMILY, D2, EXACT)

## Prevalence (mechanical, gold-blind)

- 146/179 runs have a readable input workbook; 87 contain formulas.
- 85/87 formula workbooks (98%) contain at least one relative family ≥3.
- Families are large: Debugging workbooks carry hundreds–thousands of
  family members (e.g. 1837 in Debugging_04_07, 453 in Debugging_03_06).
- Structural regularity is near-universal on this population. This
  reproduces the historical regularity finding on ordinary-agent tasks
  without any family-as-authority claim.

## Natural reachability (n=85 exposed runs)

| R | count | meaning |
|---|---|---|
| R2 | 42 | formulas seen, no comparison |
| R3 | 36 | multiple formulas printed/eyeballed, no computed comparison |
| R4 | 7 | code compares/groups formulas (Translator, set/Counter, ==/!=) |
| R5 | 0 | — |

Reach rate R4+: 7/85 (8%). The modal behavior is R3: agents print formula
columns and eyeball repetition ("follow the same pattern") without computing
membership. All 7 R4 cases are Debugging runs — family comparison appears
only where the task is explicitly about broken formulas.

## Failure linkage / discrimination

- Failure linkage: no DIRECTLY_LINKED after the precision guard (finding
  sets span hundreds of cells; overlap with a miss cell is uninformative).
- Discrimination: GENERIC_WARNING_ONLY throughout. Family membership alone
  does not discriminate misses — expected: the family is the background,
  the break is the signal (see uniformity study).
- Trivial-Python baseline: 11–30 lines (tokenize + relativize + group).
  Discovery cost is the scan (which rows/columns matter), not the code.

## Interpretation

FAM-REL-FAMILY as a standalone surfaced fact is MISSED BUT
NON-DISCRIMINATIVE: real, cheap, rarely computed — but membership lists do
not bear on decisions. Its value is as infrastructure for UNIF-FAMILY-BREAK
(post-edit variant), which is where the decision leverage lives. Do not
promote the family list itself; keep the machinery as the uniformity
detector's substrate. No automatic repair claim is made or implied.
