# Performance validation policy (future work — no new benchmark run here)

Context: Phase-10 measured +18.85 ms reference-only median (unpinned);
Phase-10B's CPU-pinned rerun of the unchanged product measured +6.39 ms
[5.63, 9.71] with an independent +6.47 ms bridge. Same code, same host,
different run protocol → different result. Identical controls drifted sharply
across unpinned batches. Policy must therefore treat timing as host/run
identity, not as a portable constant.

## Recommended policy

### Controls and pairing
- Reference-only overhead MUST always use same-run plain-Python (PY) controls:
  identical script/workbook identities, same repetition protocol (first/second
  invocation), balanced arm order within the run. Cross-batch PY reuse is
  forbidden (drift demonstrated).
- Effects are paired per workload (PROD−PY per script), then medianed.
  Task-cluster collapsing is a reported sensitivity view, not the primary gate.

### CPU / host identity
- CPU affinity: REQUIRED for budget-gating runs (singleton core, inherited by
  children, applied outside the command timer — the Phase-10B method). Do NOT
  claim pinning is universally required for all timing; it is required when a
  millisecond budget verdict is drawn.
- Record: CPU model, selected core id + class (P/E on hybrid), max frequency,
  governor (and whether fixed), core count, kernel, OS/glibc, CPython +
  openpyxl + lxml versions, filesystem. Phase-10B recorded all but fixed
  neither governor nor exclusivity — say so explicitly.
- Frequency/governor state MUST be recorded; fixing them is optional but any
  fixed state must be reported (a fixed-governor result does not describe
  stock laptops).

### Repetitions and reliability gates
- Minimum: 2 full repetitions of the whole protocol (Phase-10/10B standard).
- Keep the preregistered drift gate: at most 3 controls with >25% spread
  between second-invocation repetitions invalidates nothing by itself, but
  MORE than 3 fails the batch (batch discarded, not averaged). Calibrate the
  threshold per population size; 3/22 worked for the fixed set.
- Any budget verdict requires the gate to pass IN THE SAME BATCH.

### Reporting units
- Report milliseconds AND ratios, always paired: median signed difference
  with workload-bootstrap 95% interval, median paired ratio, faster/slower
  counts, and the range. Neither alone describes the distribution (cf. all-30:
  median 1.044 vs geometric mean 0.903).
- Never report a bare ratio without the absolute baseline scale (a 1.6× on
  100 ms is not a 1.6× on 10 s of script work).

### Cross-host rules
- Functional support and performance characterization are SEPARATE claims with
  separate evidence. A host can be supported (correctness + assurance pass)
  without characterized timings.
- What may be compared across hosts: route/artifact/fallback behavior,
  pass/fail gates, qualitative shape (e.g. "warm reuse faster than cold on
  both hosts"), order-of-magnitude costs.
- What must NEVER be averaged across hosts: millisecond medians, ratios, or
  intervals. Each host gets its own row; no pooled "average overhead".
- `LINUX PERFORMANCE CHARACTERIZED` (a future milestone, not v1) requires at
  minimum: 3+ host classes (e.g. desktop P-core-pinned, laptop stock-governor,
  CI/container shared-core), fixed populations + protocol per host, per-host
  rows published, and an explicit statement of which hosts were NOT tested.
  `VALIDATED ON THIS HOST` remains the honest v1-adjacent wording.

### Regression vs variation
- A release regression is: same host + same protocol + same population, median
  moves outside the prior batch's 95% interval AND the drift gate passes in
  both batches. Either condition alone is noise.
- Expected machine variation is: anything across hosts, governors, background
  load, or unpinned vs pinned runs. Do not file perf bugs across those
  boundaries; do file them for same-batch PY-control drift (indicates an
  unhealthy batch, not a product change).

### Budgets
- Keep budgets as engineering tripwires on fixed populations, not marketing
  thresholds. The +10 ms reference-only budget stands (met on replication);
  no data justifies raising it (observer envelope measured +0.83 ms).
- Any future budget change requires a written justification recorded BEFORE
  the scored rerun, as Phase-10B's preregistration amendments did.
