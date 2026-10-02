# Research program

This directory indexes the research program behind recalc: the experiments
that determined what the product's substrate should and should not contain.

The current product is documented in `README.md`, `COMPATIBILITY.md`,
`CHANGELOG.md`, and `docs/EVIDENCE_AND_LIMITATIONS.md`. Everything under
`research/` and in the historical phase directories is the record of how
that product boundary was reached — not user documentation, and not a
specification of current behavior.

## Entry points

Start here, in this order:

1. `research/history/phase13/PROGRAM_SYNTHESIS.md` — the causal map: which loss boundaries
   moved, which mechanisms earned product status, and why.
2. `research/history/phase13/ARCHITECTURE_DECISION_LEDGER.md` — adopted and rejected
   choices with evidence, scope, and reopen conditions.
3. `research/history/phase13/RESEARCH_MECHANISM_LEDGER.md` — one row per explored
   mechanism family: hypothesis, evidence, verdict.
4. `research/reports/PHASE13_LOSS_BOUNDARY_CENSUS_REPORT.md` — the final residual-failure
   census and what it implies.
5. `research/evidence/` — 66 frozen evidence reports behind the major
   claims (checkpoints, A/Bs, audits, probes).

## Phase map

| Question | Where | Verdict |
|---|---|---|
| Can narrow reads be served cheaper? | read_engine_phase* (top level), history/candidate_a_*, history/representative_architecture_checkpoint | Yes — exact narrow surface productized |
| Do richer agent surfaces help? | history/batch_write_helper_ab, compiled_context_sidecar_ab (top level), Track C, program/scheduler probes | Tested; did not earn required status |
| Is dependency/semantic structure decision-bearing? | research/history/phase11/* | Real facts, not decision-bearing standalone |
| Does post-edit verification transfer? | research/history/phase12/*, research/history/phase12r/* | Behaviorally potent but benign; recalc prompting, not diagnosis |
| What remains after all mechanisms? | research/history/phase13/* | Reasoning-limited residue with evidence in context |

## Repository layout

Historical research lives in three places:

- `research/history/` — one directory per experiment family, plus
  `loose_evidence/` for small root-level CSV/JSON outputs preserved as-is.
- `research/reports/` — the major human-readable phase/product reports.
- Top-level code directories (`benchmark/`, `read_engine_phase*/`, and a
  few others) — research-support code that stays at the repository root
  because the research test suite and probe scripts import it as
  top-level Python packages; moving it would churn frozen imports for
  no scientific benefit.

Prose inside frozen reports may still cite pre-reorganization root paths
(e.g. `phase13/...`); machine-checked links were updated, and the
`research/history/` prefix maps old paths to new ones.

## Raw evidence

Large raw evidence (run telemetry, staged workbooks, caches, transcripts)
lives outside Git. See `EVIDENCE_ARCHIVE.md` for the preservation model
and `evidence-manifest.json` for the machine-readable index.

Working experiment data that was never committed (benchmark checkout,
run caches, large raw JSONLs) and bulk data files removed from Git stay
in a private directory outside the repository; see `EVIDENCE_ARCHIVE.md`
and `private-data-manifest.json`.
