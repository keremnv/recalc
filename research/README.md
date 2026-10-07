# Research archive

Recalc's research archive preserves the experiments, preregistrations,
negative results, productization studies, external-validity work, and
evidence audits that led to the current 0.2.0 product and documentation.
Historical records are preserved as written; some contain terminology or
claims superseded by later evidence. Use the current public documents
for product claims, and this archive for provenance.

- Quantitative public source of truth: [PERFORMANCE.md](../PERFORMANCE.md)
- Semantic/operational source of truth:
  [EVIDENCE_AND_LIMITATIONS.md](../docs/EVIDENCE_AND_LIMITATIONS.md)
- Visual provenance: [asset taxonomy](../docs/assets/README.md)

Everything under `research/` is the record of how the product boundary
was reached — not user documentation, and not a specification of
current behavior.

## Study map

| Study (role) | Question | Frozen verdict | Why read it now |
| --- | --- | --- | --- |
| [Surface census](execution_surface_census/REPORT.md) (discovery) | Where is the earned read cost? | No formal verdict; per-candidate `EARNED` / `CLOSED_FOR_NOW` / `ALREADY_PRODUCTIZED` | Census behind the iteration mechanism; closed-candidate reopen conditions |
| [R2 iteration probe](full_cell_iteration_probe/REPORT.md) (discovery) | Is full-cell iteration real and product-ready? | `MECHANISM_REAL_BUT_NOT_PRODUCT` | Mechanism probe only; preregistered product gate failed |
| [R3 product confirmation](full_cell_iteration_product_confirmation/REPORT.md) (confirmation) | Does the mechanism hold under a product gate? | `PRODUCTIZE` | Separate study/gate/population from R2; historical OFF→ON evidence |
| [D1 decode confirmation](artifact_decode_product_confirmation/REPORT.md) (optimization) | Does the decode optimization hold with parity? | `PRODUCTIZE` | Component-level decode evidence, not a task result |
| [Tier 1 external validity](external_validity_tier1/REPORT.md) (external validity) | Does the mechanism survive ordinary trajectories? | `EXTERNAL_VALIDITY_STRENGTHENED` | Task-replay and routing evidence; controlled + curated; no population speedup |
| [Tier 2 distribution audit](tier2_distribution_audit/TIER2_AUDIT.md) (distribution audit) | What distribution sits behind the R3 aggregate? | `TIER2_AGGREGATE_NEEDS_`<br>`DISTRIBUTION_CONTEXT` | Heavy-tail context for the aggregate; basis of Figure D |
| [SB2 applicability audit](spreadsheetbench_applicability_audit/AUDIT.md) (applicability audit) | How often did useful direct service occur? | `SPREADSHEETBENCH_APPLICABILITY_`<br>`CLAIM_USABLE_WITH_MULTIPLE_DENOMINATORS` | Service incidence and denominator discipline; not a benchmark win |
| [Benefit evidence ledger](benefit_evidence_ledger/README.md) (claim synthesis) | Which public claims does evidence support? | No formal verdict | Machine-readable task/substep/block/boundary synthesis with claim restrictions |
| [0.2.0 release verification](releases/0.2.0/RELEASE_VERIFICATION.md) (release verification) | Is the 0.2.0 release gated and green? | No formal verdict | Release gates and suite results |
| [Evidence corpus](evidence/FINAL_ARCHITECTURE_FREEZE.md) (historical) | — | No single verdict | 66 frozen checkpoint/A/B/audit/probe reports |
| [History archive](history/phase13/PROGRAM_SYNTHESIS.md) (historical) | — | No single verdict | Per-family provenance incl. phase ledgers |
| [Pre-public archive](archive/PROJECT_CONTEXT.md) (historical) | — | No formal verdict | Pre-public planning context |

## R2 vs R3

R2 (`full_cell_iteration_probe/`) was a mechanism probe whose
preregistered product gate failed:
`MECHANISM_REAL_BUT_NOT_PRODUCT`. R3
(`full_cell_iteration_product_confirmation/`) was a separate
product-confirmation study with a different gate and population:
`PRODUCTIZE`. Do not rewrite R2 as a success because R3 later
productized the mechanism.

R3's historical primary comparator is OFF predecessor → ON iteration
candidate, not BASE → released Recalc 0.2.0. Current interpretation
belongs in [PERFORMANCE.md](../PERFORMANCE.md).

## Closures and negative results

Closed work stays visible; closures are findings, not TODOs.

- Derivation elision: the mechanism ledger records no earned elision,
  `CLOSED`
  ([RESEARCH_MECHANISM_LEDGER.md](history/phase13/RESEARCH_MECHANISM_LEDGER.md)).
- The execution-surface census closed 7 candidates `CLOSED_FOR_NOW`
  with explicit reopen conditions; see its
  [REPORT.md](execution_surface_census/REPORT.md).
- D1 decode work productized a component-level optimization
  (`PRODUCTIZE` gate); it is not task evidence.

## Program status

Per the frozen final architecture freeze
([FINAL_ARCHITECTURE_FREEZE.md](evidence/FINAL_ARCHITECTURE_FREEZE.md)):

> Mechanism discovery is closed; the next phase is engineering and
> communication.

Study status `MECHANISM_DISCOVERY: CLOSED`. No new semantic failure
from corrective replay and no economic finding licenses invention;
remaining work is engineering and communication. This is a pause under
current evidence and regime, not a claim that no future optimization
is possible.

## If you want to verify a current public claim

- Task-replay performance: [PERFORMANCE.md](../PERFORMANCE.md) →
  [benefit_evidence_ledger/](benefit_evidence_ledger/) → underlying
  Tier 1 replay evidence
  ([REPORT.md](external_validity_tier1/REPORT.md)).
- R3 historical mechanism effect: [PERFORMANCE.md](../PERFORMANCE.md) →
  [tier2_distribution_audit/](tier2_distribution_audit/) → frozen R3
  primary evidence
  ([REPORT.md](full_cell_iteration_product_confirmation/REPORT.md)).
- Controlled applicability: [PERFORMANCE.md](../PERFORMANCE.md) →
  [spreadsheetbench_applicability_audit/](spreadsheetbench_applicability_audit/).
- Semantic contract:
  [EVIDENCE_AND_LIMITATIONS.md](../docs/EVIDENCE_AND_LIMITATIONS.md)
  → relevant frozen product tests and research reports.
- Visual figures: [asset taxonomy](../docs/assets/README.md) →
  sanctioned generator and evidence bundle.

## Historical archive guidance

Historical research and presentation artifacts live in `history/` (and
`archive/` for pre-public planning). Wording there may be superseded;
current product claims must not be taken from historical files. Files
remain preserved for provenance — including the
[product presentation drafts](history/product_presentation/) and the
phase ledgers:

- [PROGRAM_SYNTHESIS.md](history/phase13/PROGRAM_SYNTHESIS.md) —
  causal map of the program.
- [ARCHITECTURE_DECISION_LEDGER.md](history/phase13/ARCHITECTURE_DECISION_LEDGER.md) —
  adopted and rejected choices with reopen conditions.
- [RESEARCH_MECHANISM_LEDGER.md](history/phase13/RESEARCH_MECHANISM_LEDGER.md) —
  one row per explored mechanism family.
- [PHASE13_LOSS_BOUNDARY_CENSUS_REPORT.md](reports/PHASE13_LOSS_BOUNDARY_CENSUS_REPORT.md) —
  final residual-failure census.

## Repository layout

- `research/history/` — one directory per experiment family, plus
  `loose_evidence/` for small preserved outputs.
- `research/reports/` — major human-readable phase/product reports.
- `research/evidence/` — frozen evidence reports behind major claims.
- Top-level code directories (`benchmark/`, `read_engine_phase*/`, and
  a few others) — research-support code kept at the repository root
  because the research test suite and probe scripts import it as
  top-level Python packages.

Prose inside frozen reports may cite pre-reorganization root paths;
`research/history/` maps old paths to new ones.

## Raw evidence

Large raw evidence (run telemetry, staged workbooks, caches,
transcripts) lives outside Git. See [EVIDENCE_ARCHIVE.md](EVIDENCE_ARCHIVE.md)
for the preservation model and `evidence-manifest.json` for the
machine-readable index. Working experiment data never committed stays
in a private directory outside the repository; see
`private-data-manifest.json`.
