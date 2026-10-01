# Phase 13 — Research Debt

Ranked by how much each item blocks important causal questions.

## 1. No chain-of-thought in phase-12 transcripts (blocks L2/L3/L4 separation)

Phase-12 CONTROL assistant messages carry tool calls with null text.
Whether a truncated run "had a hypothesis" is unobservable; L2 vs L3
vs L4 secondaries for 26 no-submit runs rest on action sequences +
coverage probes, not stated reasoning. Swe-agent .traj files do carry
thoughts and are the better source for intent-level questions.

## 2. No intermediate workbook snapshots (blocks best-state analysis)

Only final outputs are retained. Best-intermediate-state analysis
(§35) is therefore indirect: transcript claims of /tmp artifacts
(which are not retained) plus the 12_01-class existence proof. A
future harness should snapshot output.xlsx on every save.

## 3. First-error-only historical scores (blocks residual attribution)

Official scores retain one error string. Phase 13 re-derived full
per-cell mismatches deterministically (probe_fullerr), but that
re-derivation runs under the current parser, not the historical one
(FM:06_01-class parse drift proves the gap).

## 4. Unavailable historical evaluator/parser versions (blocks exact replay)

Phase 12R already recorded this: historical evaluator source versions
are unavailable; strictness drift (lxml/openpyxl) changes outcomes on
fixed bytes. 41 P1 rows are INCOMPATIBLE/UNSUPPORTED and bound every
global claim.

## 5. No-submit runs leave no workbook (blocks recoverability grading)

28/40 Pop-A runs have no output. Whether more budget would have
converted them is inferred from category-level contrasts (swe-agent
$4 regime submits Debugging), not per-run evidence.

## 6. Single-model dependence (blocks generality)

Both census populations are GLM-5.3(-flash). Ramble-trap frequency,
inspection-loop length, and submit hygiene are plausibly
model-version-specific (phase 12 already flagged reasoning runaway
as version-sensitive). No cross-model prevalence exists for the
loss boundaries.

## 7. Unsupported recalc classes (blocks recalc-fair universality)

Volatile functions (TODAY), external links, UDF/macros, and
scorer-XML failures leave 41 P1 rows + 2 phase-12 outputs outside
any recalc-fair comparison. The unresolved bound (0–41 rows) is
structural, not a sample-size problem.

## 8. Missing model-visible context records (blocks cost-of-discovery claims)

What the model literally saw (truncated observations, MAX_OBS cuts)
is reconstructible from transcripts but was not logged as
first-class observation artifacts with byte counts in the archived
runs. Token-decomposition claims inherit this gap.

## 9. No-submit siblings of P1 tasks unattributed (blocks ordinary submit-rate)

The 378 NOT_SUBMITTED exclusions are P2-stratum research dirs, not
P1-parent runs, so no clean "ordinary submit rate under the $4
regime" exists. The ordinary no-submit rate is regime-specific to
Population A.

## 10. Treatment-arm transcripts unused for prevalence (by design)

TREATMENT/SHAM trajectories exist and contain recalc behavior, but
using them for ordinary prevalence would contaminate the population.
They serve only as matched comparisons.
