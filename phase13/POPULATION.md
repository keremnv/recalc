# Phase 13 — Population

## Primary populations (ordinary Python/openpyxl only)

### Population A — phase-12 CONTROL (trajectory census)

- 40 runs: popA 24 + popB 12 + pilot 3 + pilot_ext 1, arm CONTROL.
- Model: z-ai/glm-5.3-flash, temp 0.0. Harness: phase-12 custom loop
  (bash / view_xlsx / submit), CALL_LIMIT 40, RUN_TIMEOUT 900 s,
  INSTANCE_COST_LIMIT $0.25, MAX_OBS 10000.
- Every run has: run_record.json (efficiency + behavior counts),
  trajectory.jsonl (tool sequence), transcript_full.jsonl (full
  transcript), input.xlsx, output if produced, official scores in
  phase12/ledgers/scorer_outcome.jsonl.
- Outcome: 40/40 exact 0. 12 SUBMITTED with output, 2 SUBMITTED
  without output, 8 TRUNCATED_INSTANCE_COST, 4 TRUNCATED_CALL_LIMIT,
  14 NO_SUBMIT (wall-time deaths).
- Recalc-fair status: NEEDS_NORMALIZED_RECALC for the 14 runs with
  output on disk (normalized V1 in phase12r/PHASE12_REPLICATION.jsonl,
  12 scorable); no-output runs are not score-bearing.
- Role: full trajectory classification (all 40), first-divergence
  analysis, no-submit census, resource-allocation analysis,
  inspection-coverage probe, best-intermediate-state analysis.

### Population B — P1 archived ordinary controls (score census + sampled trajectories)

- 183 submitted runs / 98 tasks from phase12r POPULATION_MANIFEST
  stratum P1: glm-5.3-flash ordinary-control runs under the swe-agent
  harness (call limit 50, cost limit $4.00 — a looser budget regime
  than Population A) plus a small number of spark-sidecar c0 and
  fill-c0 runs.
- Every run has: archived output.xlsx, official score tuple,
  input/gold identity. Most have .traj trajectories + ledger rows.
- Outcome: 29 exact 1, 154 exact 0. Summed modification loss 41.4766,
  regression loss 2.122 over the 154 failures.
- Recalc-fair status: ALREADY_RECALC_FAIR for 142 resolved pairs
  (RECALC_NO_MATERIAL_EFFECT, scores reproduce); INCOMPATIBLE /
  UNSUPPORTED for 41 rows (scorer/XML/LO-envelope failures — carried
  as unresolved bounds, never as zero effect).
- Role: score-mass census (all 183), full-error per-cell probe
  (§17–18), stratified trajectory sample (18 runs) for mechanism
  classification, matched success comparison (29 exact-1 runs).

## What is NOT in prevalence

- P2 (byte-unverified research candidates) and P3 (structured-harness
  history): mechanistic context only, never pooled into ordinary
  prevalence.
- TREATMENT/SHAM arms: used only as matched comparisons (§13), never
  as population.
- Excluded rows (444): 378 NOT_SUBMITTED are P2-stratum research
  rep-dirs (mixed harnesses, mostly non-ordinary) — not an ordinary
  no-submit rate. The ordinary no-submit rate comes from Population
  A (28/40 without valid submission) and from P1-parent ledger
  analysis where attributable.

## Budget-regime note (read before comparing A and B)

Population A ($0.25 / 40 calls / 900 s) and Population B ($4.00 /
50 calls, swe-agent) operate under different budgets. No-submit is
the dominant terminal state in A (70%) and rare in B's retained
archive (conditioned on submission). Completion-behavior findings
are therefore stated per-regime; the census does not pool them
into one "agent submit rate".

## Provenance

- Population A: phase12/runs/*/*_CONTROL + phase12/ledgers/*.
- Population B: phase12r/POPULATION_MANIFEST.json (stratum P1) +
  benchmark-data/.../benchmark-runs/openrouter/* + phase12r
  SCORE_REPLAY / REPLAY_PROGRESS / CACHE_STATE / FORMULA_IDENTITY.
- No new model calls. No reruns. Deterministic probes only
  (probe_inspect_coverage.py, probe_fullerr.py).
