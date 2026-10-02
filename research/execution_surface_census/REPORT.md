# Execution-surface census — report

Branch: `research/execution-surface-census`. Measurement-only phase; no
product files modified (verified: `git status` shows only
`research/execution_surface_census/` plus the `_staging/` gitignore rule).
Preregistration: `PREREGISTRATION.md` (`1e48c093…`, hashed before scoring).

## 1. Executive result

**Top finding: workbook parsing is essentially the entire removable cost, and
full-cell iteration is the gate blocking 13 of 30 representative workloads
from the direct path.** Across 140 executed workloads (1,120 runs),
`load_workbook` holds ~157 s of measured operation time while ~150k cell
reads, ~5.5k value writes, and all sheet/bounds/dimension access combined
hold under 0.3 s. Of the 30 representative workloads, 8 are admitted today;
of the 22 that are not, 13 are blocked *only* by iteration and hold 64.1 of
64.5 s of reference-path parse (99%). The phase earns exactly one feasibility
probe — full-cell iteration serving on the direct path — and closes or defers
everything else, including the token-saving inspection thesis (outputs are
already sparse: median heredoc observation 479 B; coordinate-only summaries
would exceed current filtered output), cheap read forms with zero observed
demand (0 range-literals, 0 `values_only` in 309 scripts), write ownership
(mutation dispatch ~ms; save mass real but inherent serialization work with
no evidenced faster producer), dependency machinery (~zero demand), and
recalculation (real but small mass, enormous mechanism cost).

## 2. Preregistered questions and populations

Q1 (primary): where wall time goes in representative ordinary-Python/openpyxl
workloads. Q2: what inspection patterns traverse/print excess state. Q3:
which costs a small Recalc extension could plausibly remove. The preregistered
allowed answer — no high-value mechanism earned — was not taken: one probe
cleared the bar.

- **Population A (representative 30):** frozen `representative_population.json`
  identities recovered byte-identical from pre-tidy commit `554dc00`
  (30/30 script hashes verified; 30/30 workbooks present).
- **Population B (fixed 22):** frozen `eligible_population.json`, same
  verification. Contact-selected; never pooled with A for prevalence.
  A∩B overlap is 4 workloads; all aggregation keys on (population,
  workload) after a mid-phase keying bug was found and fixed (8 pairs
  recovered).
- **Population C (agent-script sample 120):** mechanical round-robin over
  59 purpose-label strata from the control audit, `(task_id, exec_id)`
  order, task cap 4 → 120 scripts, 58 distinct tasks (≥50 required).
  88 staged for execution (workbook basenames resolved to `benchmark-data/`);
  32 static-only (trajectory-created files: `fixed.xlsx`, `in.xlsx`,
  prior-step outputs). Staged-lineage note: path normalization strips
  `/mnt/…` prefixes to workdir basenames and redirects
  `/mnt/spreadsheet_output` to the workdir (RC-study style); both hashes
  recorded per workload. 42/88 executed C workloads exit 0 on all arms;
  the rest are trajectory fragments (missing prior-step files), agent bugs
  (two confirmed: XML `standalone` kwarg, column-letter arithmetic), or
  environment limits — all failing identically across arms (parity held).

## 3. Instrumentation and parity validation

- **I1 census shim** (`census_hook/`): env-gated (`RECALC_CENSUS=1`),
  wraps openpyxl entry points with count/coarse-time decorators, delegates
  identically, attributes parse-internal vs script-driven traffic via a
  load/save context stack, chains under the product bootstrap for
  HOOKPROD runs. Covers loads, sheet/cell/range/iteration/value/formula/
  bounds/merge/names/tables/save/assign families; rich-attribute *reads*
  (plain attributes, non-interceptable) covered statically by I3.
- **I2 decomposition**: external wall clock + receipt timers
  (`setup.json`, `runtime_state.json`, observer `profile_ns`,
  `capture_state.json`) + artifact-build and import/startup probes.
- **I3 static miner** (`analyze_inspection.py`): AST + provenance tracking
  (workbook/worksheet/cell variables, A1-classifier style) over all 309
  universe scripts + A/B; validated against read-only ground truth
  (zero false mutation loops in A/B after two detector fixes).

Gates (prereg §5): **G1** 40/40 product tests pass. **G2** 280/280 pairs
agree on exit code, address-normalized stdout, and
volatile-metadata-normalized workbook state (normalization covers object
`repr` addresses and `docProps` timestamps; raw bytes compared first, then
normalized — both reported). **G3** zero admission/route/fallback deltas
between PROD and HOOKPROD. **G4** median overhead 8.2% of workload wall
(31 ms absolute median; fixed ~0.24 s hook-import cost on tiny scripts;
per-op wrapper ~sub-µs; per-op timing retained with the caveat recorded).
**G5** zero nondeterminism beyond the two normalized classes; BASE rep0/rep1
spread median 41.5 ms (6.7% relative) sets the authorization bar at
5× ≈ 208 ms lower-80% expected value per representative workload.

## 4. Operation census

Per-population operation time (median-of-reps sums; full rows in
`OPERATION_CENSUS.jsonl`):

- **A:** 30 loads = 72.8 s; 57k `.cell()` + 78k value-gets + 18k
  data_type-gets ≈ 0.06 s; iteration 29 calls ≈ 0.001 s (call setup only;
  consumption runs as user Python). Reopens 0, saves 0.
- **B:** 22 loads = 21.7 s; everything else ≈ 0.04 s. Admission 44/44 runs.
- **C:** 81 loads = 62.2 s; 33 workloads save ≈ 31 s total (median 9 ms,
  bimodal: ms on tiny books, 1–6 s on large); mutation dispatch ≈ 0.1 s
  total (1,106 subscript assigns + 4,422 value sets); 1 reopen.
  Admission 2 workloads (writes/iteration/rich dominate C by construction).

Classification into A–F: class A (Recalc-owned when admitted) covers the
sub-µs reads; the mass sits in reference parses behind class-B
iteration (13 A-workloads), class-C writes (C saves), and class-F
fixed costs. No observed operation required class D (dependency/calc)
or class E (rich fidelity) for more than ~ms.

## 5. Full-command cost decomposition

Cold-cache by construction (fresh cache dir per run; warm reuse was measured
in prior phases and is not re-litigated here):

- **A:** base wall median 0.43 s (sum 83.4 s); prod median 0.50 s
  (sum 83.4 s); prod tax median +89 ms. Admitted workloads win on warm
  reuse; reference workloads pay the wrapper tax.
- **B:** base median 0.71 s (sum 28.4 s); prod sum 35.3 s (cold builds
  included); tax median +118 ms.
- **C:** base median 0.28 s (sum 94.1 s); prod sum 107.5 s; tax +112 ms.
- Buckets: interpreter startup 30 ms; openpyxl import 186 ms (importtime);
  observer envelope median 0.80 ms (max 25.7 ms); source hashing ≤0.4 ms;
  warm artifact decode medians 15.6 ms (A) / 52.1 ms (B, larger books);
  reference fallback parses 0.3 s total (B); capture helper sub-ms when
  nothing changed. Artifact **build** (cold): ~3 ms tiny books → ~9 s
  8.3 MB books; on admitted A/B workloads build costs 1.37× the reference
  parse it replaces (41.1 s vs 30.0 s) — cold never wins; all product
  value is warm reuse.
- `unattributed` residual: user-Python loop consumption (iteration bodies),
  bootstrap/classifier milliseconds on reference paths, and artifact build
  inside cold PROD walls are reported as explicit buckets where measured;
  the remainder (loop bodies over materialized cells) is the only large
  unattributed mass and is bounded by base−parse per workload.

## 6. Reference/fallback cost

Routes over 280 PROD runs: 216 reference fast path, 60 direct,
4 direct-with-fallback (`proxy_operation_escape`, one C workload).
Non-admission blockers (direct classifier probe on staged scripts):

- **A (8/30 admitted):** iterator-shape 15 workloads,
  cell-object-iteration 14, rich 5–8, uncertainty 4, active/worksheets 3.
  The 13 iteration-*only*-blocked workloads hold 64.1/64.5 s of
  reference-path parse.
- **B (22/22 admitted):** by construction (A1-selected).
- **C (5/120 admitted overall; 2 executed):** writes 69, uncertainty 61,
  mixed 44, escape 29, data_only 23, rich 23, iteration 19.

Fallback-after-contact is rare (4/280 runs); the cost is non-admission,
not fallback. Reference parses on the 3 × 8.3 MB Debugging books (~53 s)
dominate the all-population parse mass — all three are iteration-only
blocked.

## 7. Write/recalc decomposition

- **Writes:** 0 in A/B by construction. Executed C: 33 workloads save
  (~31 s, bimodal as above); mutation dispatch ≈ 0.1 s; capture +
  validation sub-second (all `validation_passed`, 0 failures).
  Dominant write-side cost is serialization of large books, not authoring
  (authoring is ms-scale dispatch; the semantic authoring cost is model
  time, out of scope). Reopen-after-save: 7 static instances.
- **Recalculation:** 3/309 heredocs + 63 shell actions invoke LO/soffice
  (66 calls, ~48 tasks), archived waits median 1.7 s, sum 185 s. Both
  LO-invoking C-sample scripts are failing fragments, so no LO wait was
  re-measured live; the archived mass stands as the bound (~2–5 s per
  recalc-using trajectory). Post-recalc inspection is the documented
  recalc-then-read pattern (prior phases); this census adds that no
  Python-side dependency vocabulary accompanies it (0 executions).

## 8. Inspection-loop census

`INSPECTION_LOOP_CENSUS.jsonl` (324 scripts: 52 A/B + 272 C-universe
non-viz with source). Static families: SEARCH 226+21 (C+A/B),
MUTATION_LOOP 181 (C only), BROAD_INSPECTION 47+16, NESTED_SCAN 47+16,
FORMULA_INSPECTION 29+25, PRINT_LOOP 37+4, TEXT_OP 51, SAVE 105,
READBACK_DATA_ONLY 53, MULTI_LOAD 34, POSSIBLE_COMPARE 32, STYLE_RICH 45+4,
MERGE 4, REOPEN_AFTER_SAVE 7, RECALC_EXTERNAL 3, PACKAGE_SURGERY 0 in
sample (1 universe-adjacent XML case observed dynamically in C_109).
Purposes (conservative, code-shape only): text/header search, region
dumps with conditional prints, formula-region scans, workbook diffs,
readback verification. `unknown` scope retained where bounds are not
statically derivable (most C loops).

## 9. Repeated-inspection analysis

34 C-universe tasks contain scan scripts; 17 have ≥2 (151 scripts,
0.9 MB archived observations). Heaviest repeaters: FM:08_01 (23 scripts,
64 KB), Debugging:10_04 (23, 32 KB), FM:08_03 (17, 168 KB). Repetition
is real but each instance is small (median heredoc obs 479 B); the
repeat mass is ~1 MB across the whole corpus. Crucially, repetition
spans separate trajectory steps (separate processes): removing it
requires cross-step state *and* agent adoption of the querying form —
the combination prior phases tested (helpers FM-only 4/24, batch 0/13).
Same-region re-scan is inferred conservatively (same sheet literal +
same family); exact region-overlap proof would need stdout text, which
the archives do not retain.

## 10. Candidate inspection primitives

`INSPECTION_PRIMITIVE_MAPPING.json` (mechanical mapping from §8):

- `find_text` (L0): 257 instances, 168 scripts, 38 tasks, 1.15 MB obs.
- `sparse_range_values` (L1): 126 instances, 60 scripts, 23 tasks, 0.67 MB.
- `formula_regions` (L1): 54 instances, 49 scripts, 25 tasks, 0.12 MB.
- `diff_workbooks` (L2): 32 instances, 32 scripts, 15 tasks, 89 KB.
- `reference_search` (L2): 8 instances, 6 scripts, 4 tasks, 5 KB.
- `changed_cells` (L2): 7 instances, 7 scripts, 7 tasks, 2 KB.
- `inspect_neighborhood` (L1): 1 instance (bounded-print detector is
  narrow; local-context printing is usually inline in larger loops).

All are mechanically exact over read state; none requires new substrate
state except `reference_search` (formula-text index) and the two-state
L2 forms. No L3 (diagnostic interpretation) candidate has any evidence.

## 11. Progressive-disclosure economics

**The token-saving thesis is not earned; the measurement points the other
way.** For the 15 A/B workloads with unbounded iteration: traversed
dimension-cells exceed printed bytes by 10–7,000× (e.g. 2.6M dim-cells →
4.7–91 KB stdout; 10M → 1.4 KB). Agents already filter at print time
(non-None, match-gated). A coordinate-only summary of traversed regions
would *exceed* current output (26 MB coords vs ≤91 KB actual on the
largest case). Archived heredoc observations confirm small outputs
(median 479 B, p90 8.9 KB, max 71 KB); the multi-MB dumps in the corpus
are shell `cat`s, outside any workbook-query surface. Mechanical proxies
used: chars/bytes/cells; no tokenizer claim is made (no transcripts).
Conclusion: broad traversal wastes *compute* (parse + loop), not context.
Any future primitive must be justified by traversal time — which §5 shows
is ms-scale once parsed — not by tokens.

## 12. Direct-read expansion opportunities

Ranked by representative avoidable mass:

1. **Full-cell iteration** (`iter_rows`/`iter_cols`/worksheet iteration
   yielding cells): 13/30 A-workloads, 64.1 s parse, median 1.36 s/
   workload avoidable warm. State required: none new (artifact holds
   values/types; iteration is a serving protocol). Parity burden:
   per-expansion certification in the Phase-8A style (cell identity,
   `coordinate`, empty-cell semantics, merged children). Classifier work:
   static iterator-shape proofs to convert the 15+14 iteration blockers.
   Maximum plausible benefit: warm 13/30 workloads from ~1.4 s median
   parse to ~50 ms decode.
2. **Rich/workbook-surface expansion** (active, worksheets, merged,
   styles-adjacent): 9/30 A-workloads holding 0.4 s. Below bar.
3. **Range access / `values_only` / `.values`**: zero demand
   (0/309 range-literal, 0 `values_only`, 1 `.values`). Do not build.
4. **`data_only` serving**: zero A/B demand; 23 C-sample references.
   Requires cached-value storage + staleness semantics (the Ph12/12R
   saga warns this is a semantic project, not a serving tweak).
   Below bar on representative evidence.

Not implemented in this phase, per the stop rule.

## 13. Persistent-runtime opportunity

Fixed per-invocation mass: startup 30 ms + import 186 ms + warm
validate/decode ~15–52 ms ≈ ~250 ms against workload medians 0.28–0.71 s.
Theoretically removable under a persistent worker (A), shared/mmap state
(B), decoded-state residency (C), or fork server (D) — all unbuilt, all
unmeasured for integration tax. Against the bar: net ≈ 150–200 ms after
a plausible 50–100 ms integration/assurance residual vs the 208 ms bar —
borderline, with the tax entirely unmeasured. Decisive constraint from
lineage: Phase 5 falsified in-process observation (abrupt death), so any
persistent design must preserve external death detection; the current
observer (0.80 ms envelope) already delivers that cheaply. No persistence
form is earned; option E (no additional persistence) remains the default.
State loading is small but not negligible (~10–35% of small-workload
walls); on heavy workloads it is <5%.

## 14. Dependency/recalculation opportunity

Dependency demand is ~zero (8 `reference_search` instances/4 tasks; no
dependency vocabulary executed anywhere). Dirty propagation has no
observed consumer. Recalculation has real but bounded mass (66 calls,
185 s archived, ~2–5 s per using-trajectory) against a very-high-cost,
very-high-risk mechanism (engine + LO/Excel parity + oracle problem).
A dependency/recalc feasibility phase is not earned by this census;
reopen only if mutation workflows with recalc waits dominate a future
product workload mix (reopen condition recorded in the opportunity table
and §19).

## 15. Execution-transparency opportunity

Inventory of already-known facts: route, admission decision, artifact
status (BUILT/REUSED), fallback reasons, served-load/read counts,
per-phase timings (artifact load, reference parse, source hash, observer
envelope), changed workbooks + package deltas, validation/replay results,
target-vs-assurance separation. Classification: internal instrumentation
(sufficient as-is for development); developer-facing (receipts exist;
surfacing is product work, no research needed); agent-facing mechanical
query (no evidenced demand — agents never query execution metadata in
309 scripts; prior indifference results apply). No probe justified;
core verdict ALREADY_PRODUCTIZED.

## 16. Economic opportunity table

`ECONOMIC_OPPORTUNITY_TABLE.json`: 11 candidates × (workloads affected,
frequency, avoidable mass, context reduction, complexity, risk, fallback,
confidence, value-vs-bar, verdict). Bar: 208 ms lower-80% expected value
per representative workload (5× the 41.5 ms G5 repeatability spread).
Summary: 1 EARNED (full-cell iteration), 2 OBSERVE_MORE (data_only,
persistence), 7 CLOSED_FOR_NOW, 1 ALREADY_PRODUCTIZED (transparency).

## 17. What the phase rules out

- Token-saving inspection primitives (outputs already sparse; §11).
- Cheap read forms as expansion targets (zero demand; §12).
- Write-ownership-by-analogy (no hidden mutation mass; save mass is
  inherent serialization; §7) — note this complements, not repeats,
  the 0/13 exposure result.
- Dependency/calc machinery on demand grounds (§14).
- Recalculation engine on cost/benefit grounds (§14).
- Persistent runtime as a presumed win (borderline mass, unmeasured tax,
  lineage constraint; §13).
- Rich-surface expansion on mass grounds (0.4 s over 9 workloads; §12).
- The "broad dump" mental model of agent inspection (§11).

## 18. Recommended next feasibility probe

**Full-cell iteration serving on the direct path** (the single EARNED
item). Narrow probe, not implementation: (a) extend the proxy contract
with `iter_rows`/`iter_cols`/worksheet iteration yielding proxy cells
for the shapes observed in the 13 blocked workloads; (b) add classifier
iterator-shape proofs converting those blockers; (c) certify with a
Phase-8A-style adversarial + differential (openpyxl) gate on the
representative corpus; (d) re-run Populations A/B warm and report
per-workload full-command deltas with the 208 ms bar. Success criterion
(preregister in the probe): ≥10/13 iteration-blocked workloads convert
to direct with warm full-command gains clearing the bar and zero parity
deviations. Explicit non-goals: ranges, `values_only`, rich attributes,
writes, `data_only`.

## 19. Reopen conditions / limitations

- Closed candidates reopen on: new representative evidence of ≥2× the
  mass measured here, or a new agent class with systematically different
  surface usage (architecture-ledger condition).
- Limitations: single-host timing (this machine; host recorded in
  `_staging/environment.json`); cold-cache scoring (warm reuse taken from
  prior phases); C fragments fail at 46% (partial census + full static
  coverage mitigate); stdout *text* unavailable for archived runs
  (bytes only), bounding disclosure analysis to mechanical proxies;
  per-op timings carry ~2× micro-overhead on sub-µs ops (counts exact);
  iteration-body consumption time is unattributed user Python (bounded,
  not split); single-model lineage (GLM/Spark family) bounds generality;
  LO waits are archived, not re-measured.
- All raw telemetry (1,120 run rows, staged workdirs, caches) stays in
  gitignored `_staging/`; committed ledgers are the compact JSON/JSONL
  files plus this report. Total committed addition is small (<1 MB).
