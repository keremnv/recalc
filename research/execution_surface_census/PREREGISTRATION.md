# Execution-surface census — preregistration

Version 1. Frozen before final scoring runs. This phase is measurement-only:
no new spreadsheet capabilities, no API, no daemon, no mutation engine, no
recalculation engine, no expanded direct-runtime contract.

## 1. Questions

- Q1 (primary): where does wall-clock time go in representative
  ordinary-Python/openpyxl spreadsheet workloads?
- Q2 (secondary): what workbook inspection patterns cause agents to traverse
  or print far more workbook state than they need?
- Q3 (tertiary): which observed costs could plausibly be removed by a small
  Recalc extension without general openpyxl reimplementation?

Allowed terminal answer: no high-value new mechanism is currently earned.

## 2. Lineage constraints (binding)

From `phase13/PROGRAM_SYNTHESIS.md`, `phase13/ARCHITECTURE_DECISION_LEDGER.md`,
`phase13/RESEARCH_MECHANISM_LEDGER.md`, `READ_ACCELERATION_RECONCILIATION.md`,
`docs/EVIDENCE_AND_LIMITATIONS.md`, read-engine phases 1–9, and
`research/history/control_python_audit` review:

- Ordinary Python/openpyxl stays the default agent surface; no agent-facing
  IR/planner/helper/DSL work without new evidence.
- Agent-abstraction failures do not imply hidden-runtime uselessness; classify
  separately.
- Full-command economics, never microbenchmarks alone; representative evidence
  separate from contact-selected evidence.
- Genuine openpyxl is the oracle and fallback; parity-gated.

## 3. Populations (frozen identities)

- **Population A (representative 30):** workload IDs from the pre-tidy
  `rc_acceleration_validation/representative_population.json`
  (commit 554dc00), scripts re-verified by SHA-256, workbooks from
  `benchmark-data/` per `workload_manifest.json`. Representative evidence.
- **Population B (fixed 22):** IDs from pre-tidy `eligible_population.json`,
  same verification. Contact-selected; reported separately, never pooled
  with A for prevalence claims.
- **Population C (ordinary agent-script sample):** universe = the 309
  `python_heredoc` executions with recovered source in
  `research/history/control_python_audit/python_executions.jsonl`
  (68 tasks), P-C viz excluded (kept separate in the source audit).
  Mechanical selection rule (no outcome inspection):
  1. Strata = purpose-label groups from `purpose_classification.jsonl`
     (mechanical v1 labels), ordered alphabetically by label set.
  2. Within each stratum order by `(task_id, exec_id)`.
  3. Round-robin across strata; skip scripts from tasks already at 4
     selections; stop at 120 scripts or exhaustion.
  4. Assert ≥50 distinct tasks, else widen cap to 6 and repeat once.
  Workbook staging: map each script's workbook basename to
  `benchmark-data/` by exact basename match; unresolvable scripts stay in
  the static inspection-loop census only (recorded, not executed).
  Trajectory fragments may fail at runtime (missing prior state); failures
  are recorded with exit/stdout, never retried or repaired.

Every population entry records workload/script/task IDs, script SHA-256,
workbook SHA-256, and staging paths in `WORKLOAD_MANIFEST.json`.

## 4. Instrumentation (measurement-only)

Two independent, non-semantic instruments:

- **I1 — operation census shim:** a `sitecustomize`-style import hook active
  only under an explicit env key, wrapping `openpyxl.load_workbook` and
  counting/timing operation families (loads, sheet/cell/range/iteration/
  value/formula/style/merge/names/save/assign ops). Counts are exact;
  timings are coarse (perf_counter around wrapped calls). No behavior change:
  every wrapped call delegates with identical arguments and returns the
  identical object.
- **I2 — full-command decomposition:** external wall clock plus existing
  receipt/run-dir timers (observer, bootstrap, artifact, capture) plus
  coarse Python-side phase timers. Buckets per task §5/§8; an explicit
  `unattributed` bucket holds the residual. No product-code changes; the
  product runs unmodified (I1 lives in this research dir).

Static instrument **I3** (inspection-loop mining) parses archived sources
with `ast` plus conservative regex for print/scan shapes; it never executes.

## 5. Parity and perturbation gates (must pass before scoring counts)

- G1: maintained product tests pass (`pytest tests/test_product_hygiene.py
  tests/test_product_process_semantics.py`).
- G2: on Populations A+B, instrumented vs uninstrumented runs agree on exit
  code, stdout bytes, stderr bytes (modulo timing lines), and staged
  workbook bytes. Mismatch = stop, fix or report contamination.
- G3: I1 must not change admission or fallback: `admitted`, route, fallback
  reasons, and `direct_served_loads` identical with/without I1.
- G4: overhead quantified: report median (I1−baseline) per workload; per-op
  timing proceeds only if median overhead < 20% of workload wall, else fall
  back to counts + coarse buckets and say so.
- G5: determinism: two identical uninstrumented runs must agree on exit/
  stdout/workbook bytes (else the workload is nondeterministic and timing
  is reported with that caveat, not pooled silently).

## 6. Economic model (per operation family)

```text
expected whole-workload value =
    observed frequency
  × avoidable reference/mechanical cost
  × realistically servable coverage
  − Recalc serving cost
  − state construction/validation cost
  − fallback/compatibility tax
```

- `observed frequency`: representative (Pop A + executable Pop C) counts.
- `avoidable cost`: measured reference time for that family (Pop B informs
  magnitude only, never prevalence).
- `coverage`: fraction of observed instances servable under a stated narrow
  contract (from the census, not assumed).
- Costs/taxes: measured (artifact build/load, wrapper) or bounded by the
  closest measured analogue, labeled as bounds.
- Verdict bands: INTERESTING_MICRO (family-visible, full-command < noise),
  MEASURABLE_MINOR (full-command visible but below authorization), EARNED
  (authorized below). Noise floor = per-workload repeatability spread from
  G5 runs.

Authorization criterion for a future feasibility probe (no round numbers):
a candidate is EARNED iff its lower-80% interval expected value exceeds
5× the representative per-workload repeatability spread (the factor 5
covers unmeasured integration tax: this phase measures serving-side cost
only, and prior phases show integration roughly quintuples narrow
mechanism cost — cf. RC setup/control fraction 0.644 and wrapper residuals
in the Phase-4 audit). Otherwise OBSERVE_MORE or CLOSED_FOR_NOW per §19.

## 7. Classification rules

- Operation classes A–F per task §7, assigned from census evidence:
  A = served by rc3 today (admitted + no fallback on that op);
  B = read-only, no rich fidelity needed, oracle = openpyxl differential;
  C = needs write/state ownership; D = needs deps/calc; E = rich fidelity;
  F = non-spreadsheet cost.
- Inspection patterns per task §9 families; purpose inferred conservatively
  (code shape only; "unknown" allowed and counted).
- Primitive semantic risk L0–L3 per task §10; L3 needs extraordinary
  evidence (unanimous multi-task demand + exactness proof sketch).
- Progressive disclosure (§11): report chars/bytes/lines/cells as labeled
  mechanical proxies; no token claim without tokenizer evidence.

## 8. Reopen conditions and stop rule

- This phase ends with a measurement verdict; no implementation follows
  automatically.
- A CLOSED_FOR_NOW candidate reopens only on: new representative evidence
  of ≥2× the measured mass used here, or a new agent class with
  systematically different surface usage (per the architecture ledger).
- If instrumentation fails G2/G3, publish the failure and the static-census
  results only.

## 9. Environment and provenance

- Host recorded at scoring time (kernel, CPU, CPython, openpyxl/lxml).
- Product under test: this branch's `src/recalc_agent` (= rc3 baseline;
  no product files modified in this phase — verified by `git status`).
- Raw telemetry stays in `_staging/` (gitignored); only compact JSONL/JSON
  ledgers plus this preregistration are committed.
