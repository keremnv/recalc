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

1. `phase13/PROGRAM_SYNTHESIS.md` — the causal map: which loss boundaries
   moved, which mechanisms earned product status, and why.
2. `phase13/ARCHITECTURE_DECISION_LEDGER.md` — adopted and rejected
   choices with evidence, scope, and reopen conditions.
3. `phase13/RESEARCH_MECHANISM_LEDGER.md` — one row per explored
   mechanism family: hypothesis, evidence, verdict.
4. `PHASE13_LOSS_BOUNDARY_CENSUS_REPORT.md` — the final residual-failure
   census and what it implies.
5. `research/evidence/` — 66 frozen evidence reports behind the major
   claims (checkpoints, A/Bs, audits, probes).

## Phase map

| Question | Where | Verdict |
|---|---|---|
| Can narrow reads be served cheaper? | read_engine_phase*, candidate_a_*, representative_architecture_checkpoint | Yes — exact narrow surface productized |
| Do richer agent surfaces help? | batch_write_helper_ab, compiled_context_sidecar_ab, Track C, program/scheduler probes | Tested; did not earn required status |
| Is dependency/semantic structure decision-bearing? | phase11/* | Real facts, not decision-bearing standalone |
| Does post-edit verification transfer? | phase12/*, phase12r/* | Behaviorally potent but benign; recalc prompting, not diagnosis |
| What remains after all mechanisms? | phase13/* | Reasoning-limited residue with evidence in context |

## Raw evidence

Large raw evidence (run telemetry, staged workbooks, caches, transcripts)
lives outside Git. See `EVIDENCE_ARCHIVE.md` for the preservation model
and `evidence-manifest.json` for the machine-readable index.
