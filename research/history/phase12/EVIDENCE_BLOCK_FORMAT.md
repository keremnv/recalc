# Evidence block format v1 (frozen)

Factual, non-prescriptive. Shown once at the submit boundary when the
verifier is positive.

```text
Post-edit verification (mechanical check of the current workbook)

Changed cells: {n} across {sheets} sheet(s).

New formula errors ({count}):
- {Sheet!Cell}: {error}
[... up to 10, then "and {k} more (grouped: ...)"]

New formula-pattern breaks ({count}):
- {Sheet!Cell} differs from the previously consistent {row|column} pattern.
[... up to 10]

Newly blank referenced cells ({count}):
- {formula} now references blank {cell}
[... up to 10]

(Only non-empty sections appear. "Changed cells" always appears.)

This report is mechanical evidence about the current workbook state.
Review it before deciding whether to submit or revise.
```

## Rules

- Sections with zero items are omitted (except Changed cells).
- Samples capped at 10 per section; totals + grouping always shown
  (by error type, by sheet).
- Dependency context appears only as `fed by X` / `feeds into Y` one-liners
  attached to a listed ERR/UNIF/REF cell, max 3 refs each.
- No prescriptive language anywhere (never "fix", "wrong", "should",
  "must", "correct target").
- Severity is factual only: counts, sheets, types, overlap with changed
  footprint. No "critical"/"warning" labels.
- Full machine-readable detail is preserved in the run ledger, not in
  context.
