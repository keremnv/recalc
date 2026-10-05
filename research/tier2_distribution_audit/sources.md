# Tier 2 audit — primary sources

All paths relative to repo root. Commits are the identities available in
this clone at audit time.

## Frozen timing evidence (read, never modified)

- `research/full_cell_iteration_product_confirmation/REPRESENTATIVE_RESULTS.jsonl`
  — 30 rows, BASE/OFF/ON arms × 3 warm reps. Source of the ledger.
- `research/full_cell_iteration_product_confirmation/PRODUCT_GATE.json`
  — historical rounded figures (`off_total_median_sum_s: 102.26`,
  `on_total_median_sum_s: 21.51`, `saved_vs_off_s: -80.75`,
  `saved_vs_base_s: -85.98`).
- `research/full_cell_iteration_product_confirmation/_staging/parity_r3.jsonl`
  — 52/52 differential parity (30 A + 22 B), all `true`.
- `research/full_cell_iteration_probe/PERFORMANCE_RESULTS.jsonl`
  — R2 lineage cross-check (48 rows; 30 with A membership; BASE 63.2169 →
  ON 15.0041).

## Population and target definitions

- `554dc00:rc_acceleration_validation/representative_population.json`
  — frozen 30 IDs; rule "Seeded within-family sample of up to 10 usable
  control read scripts, max two per task; no eligibility requirement.",
  seed 20261011, label `CONTROL_OBSERVED_TREATMENT_BLIND`.
- `554dc00:rc_acceleration_validation/preregistered_spec.json`
  — design hashes, `selected_representative_ids`, `representative_role:
  "supporting descriptive view only"`.
- `554dc00:rc_acceleration_validation/workload_manifest.json`
  — `all_candidates` with `control_preflight.usable`, script/workbook
  SHA-256, SpreadsheetBench-2 workbook paths.
- `research/execution_surface_census/WORKLOAD_MANIFEST.json`
  — R1 re-verification (30/30 scripts, 30/30 workbooks).
- `research/execution_surface_census/PREREGISTRATION.md`
  (§3 populations) and `REPORT.md` (§2).
- `research/full_cell_iteration_probe/TARGET_WORKLOADS.json`
  — 13/8/9 partition with the target rule.
- `research/full_cell_iteration_probe/REPORT.md` (§§8–9) and
  `research/full_cell_iteration_product_confirmation/REPORT.md` (§§1, 7, 9)
  plus its `PREREGISTRATION.md` (§§2–3 gates).

## Branch tips consulted

- `research/full-cell-iteration-probe`: `e44e82b`
- `research/full-cell-iteration-product-confirmation`: `fed04b5`
- `research/execution-surface-census`: `2d43439`
- `research/external-validity-tier1`: `7d0db1e` (Tier 3 comparison:
  `REPORT.md` §§1, 12–13 — replay BASE 122.8 vs RECALC 125.3 s,
  146/10/8 routes over 165 usable blocks)

## Vignette evidence (cross-check only, not merged into the ledger)

- `docs/evidence/readme_vignette/scenario.json`
- `docs/evidence/readme_vignette/timing.json`
  (`Financial_Model_08_02__4ca3ae46295d`, 0.2.0 reproduction 3.6866 →
  0.7320 s, with `frozen_crosscheck_R3` medians 5.3035 / 1.6696)

## Public claim wordings (read-only reference)

- `README.md` (aggregate paragraph), `docs/EVIDENCE_AND_LIMITATIONS.md`,
  `CHANGELOG.md` — all carry `102.26 s → 21.51 s` without an arm label;
  the audit establishes the arms as OFF (rc3) → ON (candidate).

## Derived outputs (this audit)

- `research/tier2_distribution_audit/build_ledger.py`
- `research/tier2_distribution_audit/tier2_workloads.json`
- `research/tier2_distribution_audit/tier2_workloads.csv`
- `research/tier2_distribution_audit/tier2_summary.json`
- `research/tier2_distribution_audit/TIER2_AUDIT.md`
- `research/tier2_distribution_audit/denominator_map.md`
- `research/tier2_distribution_audit/sources.md` (this file)
