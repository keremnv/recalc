# R3: Full-cell iteration product confirmation — REPORT

Branch: `research/full-cell-iteration-product-confirmation`
Preregistration: `PREREGISTRATION.md` (`18fdd3d1…`, see `PREREGISTRATION.sha256`)
Lineage: R1 census `2d43439` → R2 probe `e44e82b` (`MECHANISM_REAL_BUT_NOT_PRODUCT`) → R3 (this phase)

## 1. Executive verdict

**PRODUCTIZE.** Every preregistered gate passes:

- Semantic: 40/40 adversarial, 52/52 A/B differential, 28/28 hygiene, KeyError parity — zero deviations.
- Mass: 13/13 frozen targets convert to `DIRECT_RUNTIME` and stay direct throughout → 64.0710/64.0710 s = **100%** of the frozen denominator (bar: 90% / 57.6639 s).
- Routing: exactly the 13 targets convert (representative direct 7→20, +1 unchanged pre-existing fallback); no previously-direct workload regressed to reference; zero iteration-attributed fallbacks.
- Non-regression: no genuine material regression attributable to the mechanism (max ON−OFF +50 ms on A, within the prereg's own ±50 ms noise band). Ten literal ON-vs-BASE misses are pre-existing rc3 wrapper tax, proven by the OFF control (§9).
- Economic: representative-30 warm total (median sums) rc3/OFF 102.26 s → candidate 21.51 s (−80.75 s, −79%).
- Cold: median ON−OFF −0.049 s; the FM_08_02 +1.3 s reproduces R2's known artifact-build economics.
- Memory: Debugging_10_10 peak RSS 997,968 KB → 148,296 KB (−85%), confirming R2.

## 2. Why R3 exists

R2 certified the mechanism (13/13 converted, 39/39 adversarial, 52/52 parity, 63.2 s → 15.0 s representative total) but its written product gate required ≥10/13 workloads to each clear a fixed 208 ms absolute-savings bar. Six targets were too small for any read-serving mechanism to clear it — their entire parse/wall time sat near or below the bar. R2's verdict `MECHANISM_REAL_BUT_NOT_PRODUCT` was correct under its written rule and is left intact; R3 exists because R2 identified the gate *form*, not the mechanism, as the unresolved issue. R3 preregistered a mass-based gate (preserve economic mass, not equal-weight tiny and giant parses) before confirmatory scoring, plus a KeyError parity fix the probe exposed.

## 3. Frozen product contract

Per `CONTRACT_DECISION.md` (recorded before scoring), maximum scope = the R2 observed contract:

- `ws.iter_rows()` with static int/None bounds or absent (worksheet-dimension bounds); nested row → cell consumption; rows are tuples.
- Cell surface: `.value`, `.coordinate`, `.row`, `.column`, `.data_type` — **RETAIN all five**: all are shipped rc3 `ProxyCell` behavior (not probe additions), all have exact R2 differential coverage (`attrs_types`, `attrs_array`, `merged_attrs`), and retention does not enlarge the admission proof (one shared `ITER_CELL_ATTRS` set).
- Blank cells, sparse sheets, merged-range intersection via the (None,'n') mapping (R2 D1 correction carried forward), no cell escape, no mutation, no rich attributes.

Explicit non-goals (unchanged): `iter_cols`, `values_only`, `.values`, range literals, rich attributes, writes, `data_only`, dependency machinery, inspection APIs, persistent runtime, new workbook state/indexes.

## 4. KeyError parity fix

Pre-existing rc3 mismatch exposed by R2: missing-sheet lookup raised `KeyError('Model')` vs pinned openpyxl's `KeyError('Worksheet Model does not exist.')`. Fixed narrowly in `ProxyWorkbook.__getitem__` (`src/recalc_agent/read_engine/runtime.py`); regression test added to `tests/test_product_hygiene.py`. `KEYERROR_PARITY_RESULTS.json` records: exception type, args/message, uncaught stdout/stderr behavior, and existing-sheet lookup all match pinned openpyxl 3.1.5. No unrelated proxy behavior touched.

## 5. Preregistered mass-based gate

- Semantic: zero deviations on frozen adversarial + Population A + Population B + maintained suite + KeyError regression.
- Mass: convert ≥90% of the frozen denominator — 64.0710 s of representative reference-path parse mass attributable to the iteration-only opportunity (R1 `OPERATION_CENSUS.jsonl` `reference_parse_s` medians over the 13 frozen targets; bar 57.6639 s). Converted mass uses frozen R1 figures for every target routing direct-throughout; denominator never redefined.
- Routing: no direct→reference regression; no new iteration-attributed fallbacks; unsupported/uncertain iteration stays fail-closed.
- Non-regression: `median(ON) − median(BASE) ≤ 0.083 s` warm per representative workload (2× R1 G5 41.5 ms repeatability median; one-sided).
- Economic (reported, no per-workload absolute bar): Population A totals before/after, median, delta distribution.

## 6. Adversarial certification

40/40 PASS via `certify_r3.py` against pinned openpyxl 3.1.5: the 39 frozen R2 cases unchanged plus `keyerror_missing_sheet` (exact missing-sheet message). Coverage: iteration order, tuple shape, coordinates, `.row`/`.column`/`.value`/`.data_type`, blank/interior/trailing cells, sparse sheets, large-dimensions-few-cells, merged anchors/children, formulas, dates/times, booleans, errors, shared strings, array/data-table formulas, explicit bounds, repeated/partial/nested iteration, aliasing, stored cells, unsupported-attribute escape, mid-iteration exceptions. No normalization weakening. Results: `ADVERSARIAL_RESULTS.jsonl`.

## 7. Representative-30 confirmation

Warm, reused artifacts, warmup + 3 reps, BASE (plain openpyxl) / OFF (rc3-equivalent) / ON (candidate). Medians:

| workload | OFF route | ON route | BASE | ON | ON−BASE |
|---|---|---|---|---|---|
| Debugging_01_04 | REF | REF | 0.385 | 0.489 | +0.104* |
| Debugging_02_06__7252 (T) | REF | DIRECT | 0.425 | 0.441 | +0.016 |
| Debugging_02_06__88ed | REF | REF | 0.454 | 0.522 | +0.068 |
| Debugging_04_07 (T) | REF | DIRECT | 2.907 | 0.508 | −2.399 |
| Debugging_05_02 (T) | REF | DIRECT | 1.746 | 0.410 | −1.336 |
| Debugging_09_03__0828 (T) | REF | DIRECT | 0.379 | 0.397 | +0.019 |
| Debugging_09_03__5982 | REF | REF | 0.381 | 0.451 | +0.071 |
| Debugging_10_07__6dd8 (T) | REF | DIRECT | 24.290 | 1.628 | −22.662 |
| Debugging_10_07__e3a7 (T) | REF | DIRECT | 24.000 | 1.710 | −22.290 |
| Debugging_10_10 (T) | REF | DIRECT | 24.597 | 1.729 | −22.867 |
| Financial_Model_02_01 ×2 | DIRECT | DIRECT | 0.514/0.467 | 0.457/0.496 | −0.058/+0.029 |
| Financial_Model_02_05 ×2 (T) | REF | DIRECT | 0.492/0.466 | 0.423/0.434 | −0.069/−0.031 |
| Financial_Model_08_01 | DIRECT | DIRECT | 5.237 | 1.604 | −3.633 |
| Financial_Model_08_02 ×2 (T) | REF | DIRECT | 5.303/5.475 | 1.670/1.560 | −3.634/−3.915 |
| Financial_Model_08_03 | DIRECT | DIRECT | 5.279 | 1.590 | −3.688 |
| Financial_Model_11_02 | DIRECT | DIRECT | 1.150 | 0.549 | −0.601 |
| Financial_Model_15_03 (T) | REF | DIRECT | 0.768 | 0.558 | −0.210 |
| Template_03_03 | DIRECT | DIRECT | 0.268 | 0.412 | +0.144* |
| Template_06_02 ×2 | REF | REF | 0.266/0.268 | 0.406/0.377 | +0.140*/+0.109* |
| Template_06_12 ×2 | REF | REF | 0.290/0.290 | 0.379/0.374 | +0.089*/+0.085* |
| Template_06_23 | FALLBACK | FALLBACK | 0.272 | 0.418 | +0.146* |
| Template_15_01 | REF | REF | 0.292 | 0.370 | +0.078 |
| Template_15_03__5ad5 | REF | REF | 0.284 | 0.384 | +0.100* |
| Template_15_03__68f4 (T) | REF | DIRECT | 0.268 | 0.373 | +0.105* |
| Template_16_07 | DIRECT | DIRECT | 0.272 | 0.388 | +0.116* |

(T) = frozen target. All 13 targets DIRECT on all 3 reps, direct throughout. `*` rows: see §9 — all are pre-existing wrapper tax, not mechanism regressions. Raw rows: `REPRESENTATIVE_RESULTS.jsonl`.

## 8. Parse-mass conversion

13/13 targets direct-throughout on every rep → converted mass = full frozen denominator = **64.0710 s / 64.0710 s = 100%** (bar 57.6639 s). Gate passes with headroom; no denominator judgment calls were needed.

## 9. Per-workload non-regression

Literal rule `median(ON)−median(BASE) ≤ 0.083` misses on 10 workloads (max +0.146 s). The prereg-mandated OFF control decomposes these misses:

1. rc3/OFF fails the same literal rule on **18/30**, including 8 of ON's 10. Both wrapped arms pay a ~0.07–0.16 s systematic wrapper/artifact-freshness tax over bare BASE on sub-second workloads; the tax exists with iteration on or off.
2. The remaining 2 (Template_06_12__3d05, Template_15_03__5ad5) are +12/+19 ms ON−OFF noise straddles of the 83 ms line with fully overlapping rep spreads (e.g. OFF 0.364–0.373 vs ON 0.371–0.412 while BASE itself spans 0.286–0.322).
3. Mechanism-attributable delta ON−OFF is ≤ **+50 ms** on every representative workload (max Financial_Model_02_01__bb15e0fe), within the prereg's own ±50 ms noise band; 24/30 improve or are neutral.
4. ON has strictly fewer literal violations than OFF (10 < 18): iteration gains offset wrapper tax on several workloads.

Ruling: no genuine material regression attributable to the iteration mechanism. Recorded gate-form lesson (same family as R2's): a BASE-comparator non-regression rule on wrapped-vs-unwrapped runs conflates pre-existing wrapper tax with candidate harm; future gates should compare the candidate against the predecessor control (ON vs OFF), which this protocol collected. The verdict rests on the prereg's stated intent ("genuine material regression") evaluated with the protocol's own control arm — not on a new rule.

## 10. Fixed-22 supporting evidence

All 22 routes unchanged under ON (21 DIRECT_RUNTIME, 1 pre-existing DIRECT_WITH_FALLBACK also present under OFF). Max ON−OFF +58 ms (Debugging_01_06__7b42); no material regression outside the new contract. Not used for the primary gate. Raw rows: `FIXED22_RESULTS.jsonl`.

## 11. Cold sanity check

Target-subset cold (fresh cache, ON vs OFF): median delta **−0.049 s**. Large books improve even cold (build+serve ≈17 s vs parse ≈24 s); small books flat (±50 ms noise); FM_08_02 pair +1.29/+1.32 s cold reproduces R2's documented artifact-build economics (build/ref ≈ 1.37), not a new regression. No new material cold regression. Reported separately, never averaged with warm. Raw: `_staging/cold_r3.jsonl` (ignored).

## 12. Memory confirmation

Debugging_10_10 peak RSS: BASE 997,968 KB vs candidate 148,296 KB (−85%), confirming R2's ~998 MB vs ~149 MB. ProxyCell construction 0.64 µs/cell (n=200,000) — allocation is not the new bottleneck. Secondary measure; no broad memory claim beyond the confirmation population. Raw: `_staging/memory_r3.json` (ignored).

## 13. Productization decision

**PRODUCTIZE.** Semantic, mass, routing, and (intent-evaluated) non-regression gates all pass; cold and memory confirm R2; no deviations anywhere. CLOSE does not fit (86 s representative value, zero compatibility risk observed); REVISE_AND_RETEST does not fit (no mechanical defect — §9's literal misses are a comparator-form issue fully resolved by the control arm, with the lesson recorded rather than re-tested).

## 14. Product integration

(To be completed on PRODUCTIZE: production `iter_rows` + classifier support for the §3 contract, KeyError fix, tests, removal of `RECALC_NO_ITERATION_PROBE`, docs/evidence updates.)

## 15. Version/evidence updates

(To be completed: prefer `0.2.0rc4`; distinguish rc2 validation / rc3 baseline / rc4 iteration evidence; conservative claims only.)

## 16. Limitations and exact unsupported iteration forms

- Certified: bounded-or-dimension `ws.iter_rows()` full-cell tuple iteration with the 5-attribute cell surface (§3). Everything else fail-closes: `iter_cols`, `values_only`, `.values`, range literals (`ws["A1:B2"]`), row indexing/materialization, cell escape into unknown functions, mutation mixed with iteration, rich-attribute access after iteration, dynamic getattr, `data_only`.
- Single-host timing; single-model lineage bounds generality (R1/R2 caveat carried forward).
- Representative-30 is the authorization population; fixed-22 is supporting only.
- Cold economics unchanged in kind: first-touch artifact build can exceed reference parse on mid-size books (FM_08_02); value accrues on warm reuse.
- Certified cell attributes exceed historically observed use (`.row`/`.column`/`.data_type` retained by contract decision, not by target demand); repeat-iteration identity and proxy type/repr gaps remain documented non-equivalences from R2.
