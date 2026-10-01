# Thin Architecture Evidence Ledger (frozen pre-checkpoint)

Ledger frozen before checkpoint task selection. No reinterpretation of old
evidence; cross-experiment score comparisons are invalid where noted.

## EARNED — model-facing surface

- Ordinary Python / openpyxl / bash / view_xlsx / submit (default scaffold).
- Optional factual helpers `search(...)`, `periods(...)`, `inspect(...)`:
  earned narrow surface via Stage-B live probe (natural adoption + exact
  mechanical replacement of larger deterministic inspections).

## EARNED — invisible infrastructure

- Transparent mutation transaction (snapshot → unchanged Python → WorkbookDelta
  → mechanical validation → atomic commit of identical bytes → telemetry).
- WorkbookDelta capture/replay, mechanical validator, opaque preservation,
  generation/freshness guards, compiled workbook substrate (cells, formulas,
  text anchors, period coordinates, fingerprints, references, provenance),
  runtime fidelity telemetry.

## SUPPORTED BUT NARROW

- Transparent runtime: zero-model capture/replay feasibility passed
  (TRANSPARENT_CAPTURE_FEASIBLE, 38/38 eligible); live H0/H1 A/B MIXED with
  no systematic capability loss attributable to the runtime; Stage-A
  replication SUPPORTED (24 reps); no systematic capture/delta/validation/
  commit failure class observed.
- Helper efficiency: Stage B measured view_xlsx ≈ -51%, tokens ≈ -40%,
  cost ≈ -37% at arm aggregate — EXPLICITLY CONFOUNDED in part by
  trajectory/stall composition. The clean claim is only: adopted helper
  calls exactly replaced larger deterministic inspections.

## REJECTED / CLOSED (do not reintroduce)

Task IR, Edit Plan, scheduler, ExecutionUnits, retrieval subagent,
dependency-derived edit authority, dependency execution closure, ProgramGroups
as runtime, semantic verifier, mandatory Mutation IR, write_cells,
write_formulas (live: zero adoption, zero work removed), fill/translation/
style-copy helpers, automatic commit receipt, verify helper, automatic recalc
receipt, automatic repair. Mutation-authoring and post-mutation-verification
branches both closed on measured negative results.

## OPEN INTEGRATION DEBT (pre-checkpoint status)

- LO/soffice was assumed non-executable; all prior live scoring used
  `--no-refresh`. Prior absolute scores are NOT comparable to refreshed scores.
- Cached-value/recalc boundary witness stayed open.

## ENVIRONMENT UPDATE (predeclared before selection, 2026-09-19)

- `soffice --headless --version` → LibreOffice 26.2.5.2, rc=0.
- `open_spreadsheet.py --dir_path` refresh tested end-to-end: rc=0, cached
  values genuinely populated (e.g. `=C7*C20` → 84000000).
- Checkpoint decision per §6: LO IS executable → both arms may use soffice
  identically; scoring uses official WITH-refresh behavior for both arms.
  This retires "LO unavailable" for this sandbox but does NOT retroactively
  validate old no-refresh scores. The LO witness is now folded into normal
  refreshed checkpoint operation (declared before selection, not opportunistic).

## UNTESTED

- Full-benchmark effect size of the thin architecture (this checkpoint is 24 tasks).
- Any architecture beyond the frozen surface + infrastructure above.
