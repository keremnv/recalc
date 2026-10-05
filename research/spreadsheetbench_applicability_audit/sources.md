# SpreadsheetBench-2 applicability audit — primary sources

Frozen study commit: `7d0db1e5ceea511bbfe37f9a7c5796eb3773a2e4`
(branch `research/external-validity-tier1`).
Directory: `research/external_validity_tier1/`.
All sources streamed read-only via `git show <commit>:<path>`; never
modified. Local `/tmp/t1_*.jsonl` copies were scratch only.

## Machine-readable evidence (all under the frozen commit)

- `TASK_MANIFEST.json` — 12 tasks, strata (`controlled` × 6), instruction
  hashes, contamination flag.
- `WORKBOOK_MANIFEST.json` — per-task source (`SpreadsheetBench-2 (local
  ignored checkout)` vs `Tier 1 curated`), `original: true`, workbook
  SHA-256, sizes, sheets, r/w expectation.
- `RUN_LEDGER.jsonl` — 18 runs (P first-half 6 + O all 12 per A2),
  statuses, exits, scores.
- `RUNTIME_REPLAY.jsonl` — 332 rows = 166 blocks × 2 arms (base/recalc):
  exits, `wall_s`, validity, route, admission, artifact, counts
  (direct/fallback/reference loads, reads, iteration cells/rows), AST +
  dynamic features. Primary ledger for this audit.
- `ROUTING_CENSUS.jsonl` — 36 rows = per (run, arm) route/admission/
  validity/fallback aggregates; independently sums to the same
  147/10/8/None route multiset.
- `REPLAY_TRIAGE.json` — 166 total, 147 replay-consistent, runtime-usable
  rule, r18 s29 exclusion, r18 s12 error-path inclusion, 17 triaged steps.
- `MODEL_MANIFEST.json` — P/O model IDs, identical settings, caps.
- `OPERATION_CENSUS.jsonl`, `MODEL_BEHAVIOR.jsonl` — consulted for
  operation vocabulary; not needed for the final counts.
- `PREREGISTRATION.md` (+ `.sha256`) — §§0–4: design authority, harness
  freeze, models/settings, 12-task population, mechanical controlled-task
  rule, amendments A1 (DeepSeek→Mimo) + A2 (18 runs).
- `REPORT.md` — frozen verdict `EXTERNAL_VALIDITY_STRENGTHENED`; §§6–7
  (population/validity), §12 (122.8/125.3 s replay), §13 (146/10/8
  routes, 18/165 admitted, 136 read-only). Cross-checked, never edited.
- `HALFWAY_DECISION.md` — A2 reshape record (consulted).

## External reference (Tier 2 comparison only)

- `research/tier2_distribution_audit/` (branch
  `research/tier2-performance-distribution-audit`, commit `402fe7e`):
  representative-30 ledger, OFF→ON 102.26 → 21.51 s, concentration
  top-3 = 84%.

## Derived outputs (this audit)

- `research/spreadsheetbench_applicability_audit/rebuild.py`
- `research/spreadsheetbench_applicability_audit/task_population.csv`
- `research/spreadsheetbench_applicability_audit/invocation_ledger.csv`
- `research/spreadsheetbench_applicability_audit/task_summary.csv`
- `research/spreadsheetbench_applicability_audit/model_summary.csv`
- `research/spreadsheetbench_applicability_audit/summary.json`
- `research/spreadsheetbench_applicability_audit/AUDIT.md`
- `research/spreadsheetbench_applicability_audit/denominator_map.md`
- `research/spreadsheetbench_applicability_audit/sources.md` (this file)
