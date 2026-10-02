# R4: Post-rc4 residual cost census — REPORT

Branch: `research/post-rc4-residual-census` (from rc4 `fed04b5`)
Preregistration: `PREREGISTRATION.md` (`8b21a4f1…`), committed before scoring (`558321a`).
Baseline: all headline comparisons are plain Python/openpyxl vs rc4 product.

## 1. Executive result

rc4 removed the parse frontier almost entirely: residual representative
reference-parse mass is **0.23 s** across Population A (was 64.5 s in R1),
diffuse across blocker families with no item above noise. The remaining
PROD-warm total is 12.95 s (median sums; BASE 58.47 s), dominated by:

- artifact decode **4.97 s (38%)**, concentrated in 7 large-book workloads
  (~0.65–0.73 s each, ~70% of those workloads' walls) — the single
  strongest and only `EARNED_FOR_FEASIBILITY_PROBE` item;
- inherent program execution ~6.1 s (child interpreter, openpyxl import,
  user loops, serving — BASE non-parse ≈ 6.8 s corroborates);
- parent CLI startup ~1.59 s (~53 ms/invocation, mostly a second Python
  interpreter + `recalc_agent` import);
- residual reference parse 0.23 s (2%).

Verdicts: 1 EARNED (artifact decode acceleration), 3 OBSERVE_MORE
(persistence residency/worker, build laziness), 7 CLOSED_FOR_NOW,
1 ALREADY_PRODUCTIZED (transparency). No new read shape, write,
recalc, `data_only`, or inspection mechanism is earned.

## 2. rc4 baseline and why remeasurement was necessary

R1 measured a pre-iteration product (7 direct / 22 reference). rc4
converted the 13 iteration-only workloads (R3: 100% of frozen parse
mass, 102.26 s → 21.51 s on the R3 machine). R1 opportunity rankings
are stale by construction; R4 re-measures routing, buckets, blockers,
and demand from scratch on rc4. R3 timing is used as cross-check only.

Machine-variance note: absolute giant-book seconds on this window run
~1.3–2× faster than R1/R3 windows (e.g. D_10 BASE ≈ 13 s vs R3 ≈ 24 s;
same-13 parse ≈ 48 s vs frozen 64.07 s). All R4 arms ran interleaved on
one machine, so relative/mass conclusions hold; cross-phase absolute
comparisons carry this caveat.

## 3. Populations and preregistration

A (30, authorizing), B (22, supporting), C (120, supporting) frozen-reused
from R1 manifest `ab71c8d4…`. All 52 A/B staged dirs re-verified by
script+workbook SHA — zero mismatches, zero irreproducible workloads.
Protocol: BASE×3, HOOK×2, PROD-WARM (warmup+3, persistent cache),
PROD-COLD×1; medians; 300 s timeout, none hit. EARNED rule per prereg
§6 (concentrated mass × grounded avoidable fraction − tax − risk,
materially above noise; contact-selected evidence cannot authorize).

## 4. Instrumentation/parity

520/520 runs collected, all exit-0. HOOK/BASE parity 104/104
(exit + address-normalized stdout + workbook state). Hook overhead
median 44 ms; +0.5–2.6 s on 11 large-book HOOK runs (per-cell wrapping
perturbation; parity held; HOOK walls never used for headlines — BASE
is the timing reference). No workload changed admission under
instrumentation. One harness bug found and fixed before analysis:
warmup tag matched the warm filter; ledgers regenerated.

## 5. New representative routing

A: **20 DIRECT_RUNTIME + 1 DIRECT_WITH_FALLBACK + 9 REFERENCE** (rc3:
7 + 1 + 22). B: 22/22 direct (21 + 1 pre-existing fallback). Static
scan agrees (A: 21 admitted / 9 reference; B: 22/22). All direct
artifacts show BUILT→REUSED→REUSED→REUSED. The fallback (T_06_23) is
the known pre-existing rc3 escape, unchanged. C static re-scan: 6/120
admitted; blockers dominated by writes/mixed (270/70), uncertainty
(221), escape (100) — same family ranking as R1.

## 6. Full-command residual cost decomposition

A median sums, PROD-warm 12.95 s (BASE 58.47 s; cold 55.80 s):

| bucket | s | share | removable? |
|---|---|---|---|
| artifact decode | 4.97 | 38% | candidate (EARNED probe) |
| inherent program exec (interp/import/loops/serving) | ~6.1 | 47% | no (common with BASE) |
| parent CLI startup | ~1.59 | 12% | partially (diffuse micro-work) |
| residual reference parse | 0.23 | 2% | no (diffuse, sub-noise) |
| source hash / observer-parent | ~0.06 | <1% | no |
| unattributed | ~0 | — | decomposition closes vs BASE |

Medians: BASE 0.273 s → PROD 0.270 s per workload (median workload is
small; mass lives in the large-book tail). Full rows:
`COST_DECOMPOSITION.jsonl`; routing: `ROUTING_CENSUS.jsonl`.

## 7. Remaining reference-parse mass

0.2315 s over 10 workloads (9 reference + 1 fallback). Largest single
workload 82 ms (below the 83 ms noise reference); largest family
(dynamic_uncertain) 0.10 s; families overlap and are diffuse
(rich 0.084, uncertain 0.100, active/worksheets 0.065,
iteration-mixed 0.062). No concentrated, agent-shaped compatibility
boundary remains. See `REFERENCE_PARSE_MASS.json`.

## 8. Fixed per-invocation tax

Empty script: BASE 38 ms vs PROD 151 ms → 113 ms tax, split (measured)
into parent CLI ~92 ms (second interpreter + `recalc_agent` import,
43.6 ms cumulative; CLI does NOT import openpyxl), observer-parent
~1 ms (fork/launch/snapshots), child-side ~21 ms (bootstrap, admission,
config, receipt). On real small workloads the wrapped-vs-bare tax is
+17…+87 ms (≈ +50 ms typical; parent CLI 43–66 ms). Admission proper:
0.6 ms/script — negligible. Bare `python -c pass`: 40 ms; openpyxl
import: 87 ms (child-side, common with BASE). Total tax mass ≈ 1.6 s.
Only the parent-CLI slice is Recalc-removable in principle, and it is
diffuse micro-work: CLOSED_FOR_NOW. See `FIXED_TAX_ANALYSIS.json`.

## 9. Persistence economics

- Decoded-state residency / mmap: prize = up to 4.97 s decode, but
  only across same-workbook invocations (unmeasured reuse) minus
  IPC/validity tax; prize shrinks if the decode probe succeeds first.
- Persistent worker: removes ~1.6 s parent CLI + part of child startup
  per invocation, but naive in-process workers violate the
  external-death-observation constraint — fork-server is the only viable
  shape, with high integration cost for ~12% mass.
- No-persistence remains the default. All persistence: OBSERVE_MORE
  with a specific reopen condition (same-workbook multi-invocation
  reuse measurement + IPC cost evidence).

## 10. Artifact lifecycle economics

Decode scales with book size (8.3 MB → 0.68 s; 2.15 MB → 0.66 s;
≤0.68 MB → ≤0.09 s; ≤0.11 MB → ~1 ms). Build (cold−warm) also scales
(8.3 MB → ~9.2 s < parse ~13 s; 2.15 MB → ~3.1 s ≈ parse; small →
negligible) but is first-touch-only. Reuse is reliable (BUILT→REUSED).
Decode acceleration is EARNED (§19); build laziness is OBSERVE_MORE
(per-sheet touch demand unmeasured, zero warm value). See
`ARTIFACT_LIFECYCLE_ANALYSIS.json`.

## 11. Remaining read-surface opportunities

A demand: loads 30, workbook-iteration 28 (0.0001 s total — negligible
dispatch), value/sheet/cell access 24–26, data_type 16, iter_rows 15,
bounds/getitem 6, dimensions/active 2. Zero A/B demand for `iter_cols`,
`.values`, `values_only`, range literals, `data_only` — unchanged by
rc4 routing. All CLOSED_FOR_NOW.

## 12. `data_only`

Zero A/B demand; 23–25 C references (supporting only). rc4 changes
nothing; the Phase 12/12R cache-semantics warning stands. Demoted
OBSERVE_MORE → CLOSED_FOR_NOW on confirmed-zero representative demand
with unchanged-high semantic risk.

## 13. Write/save economics

Zero saves in A/B (HOOK census). C is mutation-heavy by construction
but supporting-only, and its cost is agent authoring, not Recalc
serving. R1 stands: dispatch ~ms, serialization inherent with no
evidenced faster producer. CLOSED_FOR_NOW. See
`WRITE_RECALC_ANALYSIS.json`.

## 14. Recalculation economics

Zero soffice/LibreOffice in A/B scripts; 90 references in the
C-universe executions (supporting context, not costed). Still too rare
on representative evidence, and owning calculation remains out of
scope. CLOSED_FOR_NOW.

## 15. Execution transparency

Receipts expose route, admission decision, fallback reasons, artifact
state (BUILT/REUSED), iteration counts (`direct_iteration_cells/rows`),
served/reference load counts, ns timings, and the full observer
profile — iteration serving included, with no new opaque behavior in
rc4. ALREADY_PRODUCTIZED; no agent-facing API (no demand).

## 16. Memory

D_10_10 peak RSS: BASE 997,632 KB → PROD 148,520 KB (third independent
confirmation of ~998 MB → ~148 MB). Small workloads: ~47 MB both arms
(PROD +0.5–1.3 MB: decode/proxy overhead, negligible). Repeatable
secondary benefit, isolated to openpyxl cell materialization; no
dedicated memory work earned. See `MEMORY_CENSUS.json`.

## 17. Residual opportunity table

`RESIDUAL_OPPORTUNITY_TABLE.json`: 1 EARNED (decode acceleration),
3 OBSERVE_MORE (residency/mmap, persistent worker, build laziness),
7 CLOSED_FOR_NOW (next read shape, iter_cols family, `data_only`,
writes, recalc, parent-CLI micro-work, inspection APIs),
1 ALREADY_PRODUCTIZED (transparency).

## 18. What rc4 closes

The reference-parse frontier as a product concern (64.5 s → 0.23 s,
−99.6%); the iteration thesis end-to-end; any near-term read-shape
expansion (demand + mass both ~zero); write/recalc ownership on
representative evidence (zero demand); the token/inspection thesis
again (no new data). The remaining 12.95 s is 47% inherent program
execution, 38% decode, 12% parent CLI, 2% reference parse.

## 19. Recommended next feasibility probe, if any

**Artifact decode acceleration** (single EARNED item). Suggested probe:
(a) decode breakdown gate first (decompress vs structure-parse vs
object-build on the 7 frozen large-book workloads); (b) candidate
codec and/or lazy per-sheet decode serving byte-identical state;
(c) gate on byte-identical served state + measured warm speedup with
zero parity deviations (adversarial + A/B style); old decoder retained
as fallback. Explicit non-goals: persistence, API changes, semantic
expansion, build redesign.

## 20. Reopen conditions / limitations

- Single host/window; giant-book absolutes vary ~2× across windows —
  relative conclusions hold, cross-phase absolutes caveated.
- Residency/worker reopen on: same-workbook multi-invocation reuse
  rates + IPC cost measurement.
- Build-laziness reopen on: per-sheet touch census showing
  single-sheet dominance on large books.
- Read-shape/`data_only`/write/recalc reopen on: new representative
  demand ≥2× noise with concentrated mass (R1 rule carried forward).
- C stays supporting-only; B stays contact-selected.
- Stopping here per the stop rule: no mechanism implemented.
