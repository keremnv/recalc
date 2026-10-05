# Benefit ledger — primary sources

All primaries read-only. Later audits used only for cross-checks.

## R1/R2/R3 (master checkout)

- `research/execution_surface_census/WORKLOAD_MANIFEST.json` — Pop A
  workload/workbook bytes (branch `research/execution-surface-census`
  `2d43439`).
- `research/full_cell_iteration_probe/PERFORMANCE_RESULTS.jsonl` — R2
  per-workload arms (branch `research/full-cell-iteration-probe`
  `e44e82b`); R2 FM:08_02 window + R2 population row.
- `research/full_cell_iteration_probe/REPORT.md` §§8–9 — R2 63.2→15.0 s,
  7/13 gate form, machine-variance note.
- `research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl`
  — R3 30 workload rows (branch
  `research/full-cell-iteration-product-confirmation` `fed04b5`).
- `research/full_cell_iteration_product_confirmation/_staging/parity_r3.jsonl`
  — 52/52 differential parity.
- `research/full_cell_iteration_product_confirmation/PRODUCT_GATE.json` —
  historical 102.26/21.51 figures, routing counts.
- `research/full_cell_iteration_product_confirmation/REPORT.md` §§1,7,9,11
  — OFF→ON comparator, per-workload table, cold check (−0.049 s median).
- `research/full_cell_iteration_product_confirmation/PREREGISTRATION.md` —
  mass gate, non-regression rule.

## Vignette (master checkout)

- `docs/evidence/readme_vignette/timing.json` — 0.2.0 reproduction
  3.6866→0.7320 s, parity standard, R3 cross-check (commit `89f3dfd`).
- `docs/evidence/readme_vignette/scenario.json` — provenance bundle.

## Tier 1 (frozen commit `7d0db1e`, via `git show`)

- `research/external_validity_tier1/RUNTIME_REPLAY.jsonl` — 332 rows;
  trajectories, task sums, blocks, populations.
- `research/external_validity_tier1/REPLAY_TRIAGE.json` — 166 total,
  r18 s29 exclusion rule.
- `research/external_validity_tier1/TASK_MANIFEST.json`,
  `WORKBOOK_MANIFEST.json`, `RUN_LEDGER.jsonl`, `ROUTING_CENSUS.jsonl`,
  `PREREGISTRATION.md`, `REPORT.md` — strata, workbooks, runs, routes,
  design, frozen `EXTERNAL_VALIDITY_STRENGTHENED` verdict.

## Prior-audit cross-checks (via `git show`, values asserted equal)

- `research/tier2-performance-distribution-audit` (`402fe7e`):
  `research/tier2_distribution_audit/tier2_summary.json` — OFF/ON sums
  match to 1e-6.
- `research/spreadsheetbench-applicability-audit` (`0fc0187`):
  `research/spreadsheetbench_applicability_audit/summary.json` —
  controlled replay sums match to 1e-6.

## Derived outputs (this ledger)

- `research/benefit_evidence_ledger/build_ledger.py`
- `research/benefit_evidence_ledger/benefit_ledger.csv`
- `research/benefit_evidence_ledger/benefit_ledger.json`
- `research/benefit_evidence_ledger/summary.json`
- `research/benefit_evidence_ledger/README.md`
- `research/benefit_evidence_ledger/positive_cases.md`
- `research/benefit_evidence_ledger/boundary_cases.md`
- `research/benefit_evidence_ledger/claim_support_matrix.md`
- `research/benefit_evidence_ledger/sources.md` (this file)
