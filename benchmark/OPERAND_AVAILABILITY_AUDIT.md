# Operand-availability audit

A follow-up to the canonical-choice probe, answering one question the Phase D
report deliberately left open: when a group's program was wrong, had the model
actually been shown the cells that program needs?

Phase D does not exonerate retrieval — 15 of 16 sessions spent all eight
permitted queries — so "could not construct the program" and "was never shown
the operands" stayed confounded. This audit separates them.

## Method

No model calls, nothing unfrozen. For each of the 16 Phase B groups, take the
gold canonical formula, extract its operands lexically (the same reference
extraction the workbook compiler uses), and grade each one against the *stored*
synthesis working set of the session both arms shared:

| Level | Meaning |
| --- | --- |
| `CELL_MATERIALIZED` | `cell:<id>` in the working set: kind, raw value and display value all in `WORKING_SET_EVIDENCE` |
| `FORMULA_MATERIALIZED` | a formula entity for that cell is in the working set: address and formula text visible |
| `REFERENCED_ONLY` | named as the referent of a materialized formula, or inside a materialized range. The model sees that the cell exists and is used, not what is in it |
| `ABSENT` | not in the working set in any form |
| `NOT_IN_WORKBOOK` | no such cell in the compiled spine |

An operand is *available* only when materialized. A group whose every operand
was available and whose program was still wrong is charged to
`PROGRAM_CONSTRUCTION_FAILURE`; anything weaker is charged to
`CONTEXT_DELIVERY_FAILURE`, whatever else is also true of it.

The gold formula is read, so this is evaluator-side only. It is a measurement,
not a mechanism, and nothing here is available at runtime.

## Reproduce

```bash
python benchmark/operand_availability_audit.py
```

Writes `.../canonical-choice-probe/operand_availability.json`.

## Result

Reference completeness is high but not uniform: 28 of 34 gold operands were
materialized, and 12 of 16 groups had every operand in hand.

| Availability class | groups | all operands | partial | none |
| --- | ---: | ---: | ---: | ---: |
| RECOVERABLE_EXACT | 7 | 7 | 0 | 0 |
| RECOVERABLE_SHAPE_ONLY | 3 | 1 | 1 | 1 |
| GENUINELY_NOVEL | 6 | 3 | 2 | 1 |

All five groups either arm got right had every operand materialized, so the
audit has no false-negative among the successes.

Of the eleven wrong groups, six are construction failures and five are delivery
failures:

| Group | class | verdict | charge |
| --- | --- | --- | --- |
| 08_04 `Working Capital!C68` | novel | all operands | construction |
| 08_04 `Working Capital!D68` | novel | all operands | construction |
| 08_05 `Working Capital!C66` | novel | all operands | construction |
| 08_03 `Working Capital!J50` | shape-only | all operands | construction |
| 15_04 `Consol_annual!N50` | exact | all operands | construction |
| 15_04 `Consol_quarterly!E30` | exact | all operands | construction |
| 08_03 `Ratio Analysis!C19` | novel | `Balance Sheet!C9` absent | delivery |
| 08_05 `Ratio Analysis!C19` | novel | both operands absent | delivery |
| 15_04 `Consol_annual!N168` | novel | `Consol_annual!N49` referenced only | delivery |
| 08_03 `Balance Sheet!I7` | shape-only | sole operand absent | delivery |
| 08_04 `Balance Sheet!C34` | shape-only | `Balance Sheet!C20` absent | delivery |

Both failures that ended Phase C — 08_04 `C68` and 08_05 `C66` — are
construction failures with every operand materialized, and materialized from the
deterministic bootstrap rather than from retrieval at all. `NOVEL_SYNTHESIS_DOMINANT`
survives the audit on its two central cases.

Every delivery failure is cross-sheet or cross-region, and no session hit the
input cap or declared retrieval finished. All five spent all eight turns and
still came up short — but so did the successes, so the budget is not by itself
the explanation.

What does separate them is how many turns survived. Counting turns lost to
`QUERY_TIMEOUT`, `RESULT_TOO_LARGE`, `SQL_ERROR` and malformed actions:

| Group | groups | turns | lost | share |
| --- | ---: | ---: | ---: | ---: |
| correct | 5 | 40 | 6 | 15% |
| construction failure | 6 | 48 | 12 | 25% |
| delivery failure | 5 | 40 | 12 | 30% |

Suggestive, not decisive: the construction failures lost nearly as many turns
and still had every operand. 08_03 `Balance Sheet!I7` is the clearest single
case — one malformed action, two timeouts, and on its last turn it was still
resolving the sheet id for `Capex and Debt Assumptions ` when its only operand
lived at `U138` on that sheet.

## Invariants

1. No model calls. The audit reads stored sessions and the compiled spine only.
2. Gold is read, so the taxonomy is evaluator-side and never runtime-visible.
3. Operand extraction is the compiler's own; named and structured references are
   omitted here exactly as they are there.
4. Availability is judged against the working set as stored, not as re-derived.
5. Entity ids carry their kind prefix; the working-set id *is* the primary key.
