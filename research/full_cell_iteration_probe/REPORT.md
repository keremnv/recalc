# Full-cell iteration probe — report

Branch: `research/full-cell-iteration-probe` (from census tip `2d43439`).
Preregistration: `PREREGISTRATION.md` (`59287dd5…`, hashed before scoring).
One disclosed deviation: `DEVIATIONS.md` D1 (merged-contact premise).

## 1. Executive verdict

**MECHANISM_REAL_BUT_NOT_PRODUCT.** The mechanism works: 13/13
iteration-only representative workloads convert to and stay direct
throughout, with zero semantic deviations across 39 adversarial cases and
52/52 A/B differential runs, and representative-30 warm time falls
63.2 s → 15.0 s (4.21×). But the preregistered gate's count form
(≥10/13 workloads each clearing a fixed 208 ms bar) fails at 7/13:
the 6 misses all have total walls ≤0.52 s, so no read-serving mechanism
can clear a 208 ms bar on them — the bar exceeds their entire parse plus
the fixed ~90–120 ms wrapper tax. The failure is gate miscalibration for
the small-parse tail (second premise error, analyzed as D2 below), not
mechanism failure. No automatic productization follows; §15 states the
corrected gate under which a product decision could be revisited.

## 2. Exact observed iteration contract

`ITERATION_CONTRACT.json` (mechanical extraction) + corrected merge
inventory (D1). All 13 targets share one shape:

```python
for row in ws.iter_rows(min_row=R, max_row=R[, min_col, max_col]):
    for c in row:
        if c.value is not None:
            print(c.coordinate, repr(c.value)[:N])
```

14 call sites: 13 with static int bounds, 1 bare `iter_rows()` (dimension
bounds); 1 comprehension variant (`[(c.coordinate, c.value) ...]`, attributes
only, no cell stores). Cell use: `.value` (26 sites), `.coordinate` (13);
no `.data_type`/`.row`/`.column` in targets (certified as readable anyway);
no stores, aliases, escape, identity use (the 13 `is` flags are all
`c.value is not None`), rich access, or writes. 12/13 target books contain
merges; 9 rectangles avoid them, 4 intersect (served post-D1). Zero
`iter_cols`, sheet iteration, materialization, row indexing, `values_only`,
ranges in targets. The implementation contract is exactly this — nothing
more.

## 3. Preregistered gates

Primary (kept from census): ≥10/13 targets convert and stay direct; each
clears 208 ms lower-80% warm gain; zero parity deviations on certification
populations. Result: 13/13 convert and stay direct; 7/13 clear 208 ms;
zero deviations (39/39 adversarial + 52/52 A/B). Gate fails on the count
form. As-preregistered outcome (pre-D1, merged fallback): 4/13 — reported
for the record; the corrected scoring (post-D1) is 7/13. Secondary
measures all collected (§8–§13).

## 4. Implementation shape

`src/recalc_agent/read_engine/runtime.py`: `ProxyWorksheet.iter_rows`
delegates to `_serve_iter_rows` (~70 lines). It binds through openpyxl's
exact signature (arity/keyword errors reproduce via genuine fallback);
fails closed on `values_only`, non-int bounds, and bare-bounds-with-empty-
sparse-state (truly-empty vs style-only vs merges-only is indistinguishable
without new state — reference decides in ms); mirrors `or`-defaults exactly
(falsy → default, incl. 0); validates `min ≥ 1` lazily inside the generator
with openpyxl's identical `ValueError` message; serves merged ranges via
the pre-certified merged-child → `(None, 'n')` mapping (D1); yields tuples
of the existing `ProxyCell` (value/data_type/coordinate/row/column served,
all else escapes per-cell to genuine). No new persisted state, tables,
indexes, APIs, or processes. `RECALC_NO_ITERATION_PROBE=1` disables both
serving and classifier certification (rc3-behavior control). Receipts now
persist the bounded `events` list (additive key) so exact fallback reasons
are inspectable.

## 5. Classifier/admission changes

`src/recalc_agent/_frozen/eligibility.py`: for-target tracking over
`ws.iter_rows(...)` (statements + comprehensions) and row-var loops;
per-site kwargs proof (kwargs-only, known keys, int/None bounds,
`values_only` absent/False/None, direct `for…in` consumption); whole-tree
consumption proof (row vars only as for-target/iter; iteration-derived
cells only via `.value/.coordinate/.row/.column/.data_type` loads or
for-target binding; every other occurrence blocks); A0
"iterator shape not statically proven" superseded only when ≥1 site
certifies and no iteration boundary remains (bare lexical matches with no
certified site, e.g. in strings/eval payloads, keep the blocker).
`iter_cols`, sheet iteration, materialization, row ops, stores, escape,
identity, rich access, and writes all keep whole-script reference.
Result: A 8→21 admitted (+13 targets, zero regressions), B 22→22, C-sample
+1 (`C_415`, textbook contract member, reviewed). Probe-off reproduces
rc3 decisions exactly.

## 6. Adversarial certification

`ADVERSARIAL_CASES.json`: 39 cases — empty/sparse/big-dim/blanks/style-only/
merges-only sheets; merged anchor/child/outside/bare + `merged_attrs`
(MergedCell-equivalence incl. children); formulas, dates, booleans, errors,
shared strings, array/data-table formulas; explicit/out-of-dimension/zero/
reversed/negative/single-cell bounds; repeat/partial/nested iteration;
12 block-shapes (values_only, iter_cols, dynamic bounds, rich-after, store,
identity, escape-call, materialize, mixed-write, row-index, getattr,
alias, len(row)); abrupt mid-iteration exception. Result: 39/39 pass
(25 direct, 14 reference), exit/stdout/state identical to pinned openpyxl
3.1.5 throughout. Known non-equivalences (documented, classifier-blocked
where observable): repeat iteration yields fresh proxy objects (openpyxl
returns cached identical cells); proxy `type`/`repr` differ (pre-existing
proxy gap class).

## 7. Differential parity

`PARITY_RESULTS.jsonl`: 52/52 A/B workloads pass (exit,
address-normalized stdout, volatile-normalized state). Adversarial 39/39
(§6). Product suite: 40/40 hygiene/process tests; full suite 881 passed
with only the 4 pre-existing baseline failures (verified identical via
stash). One out-of-population note: newly admitted C-sample script `C_415`
(a fragment whose staged book lacks sheet "Model") exposes a *pre-existing*
rc3 gap — `ProxyWorkbook.__getitem__` raises `KeyError('Model')` where
openpyxl raises `KeyError('Worksheet Model does not exist.')` — confirmed
present on the probe-off rc3 path. Not introduced by this probe and out of
scope to change frozen behavior, but broader admission widens exposure to
such frozen point-read gaps: a productization must-fix (one line).

## 8. Representative performance

Population A warm (REUSED artifacts, 3 reps + warmup): sum 63.2 s → 15.0 s
(4.21×). Target-subset detail (§9). Non-target A workloads: unchanged
routing except the 13 conversions; OFF-vs-ON ≈ 1.0 on unaffected scripts
(B ON/OFF = 1.014 overall). Median per-workload gain on converted
workloads: 0.10 s (mean pulled by 11–13 s giants); distribution is
bimodal by book size, as predicted by parse-bound economics.

## 9. Target-subset performance

| workload (median s) | base | on | gain | lo80 | cells |
|---|---|---|---|---|---|
| 10_07_6dd8 | 12.75 | 0.88 | 11.87 | 11.77 | 820 |
| 10_10_c7ec | 15.04 | 1.49 | 13.55 | 12.83 | 10400 |
| 10_07_e3a7 | 12.92 | 1.42 | 11.50 | 11.37 | 500 |
| 08_02_625e | 3.74 | 0.99 | 2.75 | 2.57 | 8000 |
| 08_02_4ca3 | 3.05 | 1.04 | 2.01 | 2.03 | 4800 |
| 04_07_62a7 | 1.58 | 0.25 | 1.33 | 1.32 | 320 |
| 05_02_f274 | 1.02 | 0.24 | 0.78 | 0.71 | 1430 |
| 15_03_6409 | 0.52 | 0.42 | 0.10 | 0.09 | 8145 |
| 02_05_9000 | 0.33 | 0.27 | 0.06 | 0.04 | 1331 |
| 02_06_7252 | 0.30 | 0.27 | 0.04 | 0.02 | 800 |
| 02_05_c75e | 0.29 | 0.28 | 0.02 | −0.01 | 1804 |
| 09_03_0828 | 0.26 | 0.26 | −0.00 | −0.04 | 1175 |
| 15_03_68f4 | 0.22 | 0.26 | −0.04 | −0.05 | 1140 |

7/13 clear 208 ms (top 7). All 13 stay DIRECT_RUNTIME throughout (zero
fallbacks post-D1). Target mass: ~47 s → ~7 s warm.

## 10. Fixed/contact-selected supporting evidence

Population B warm: sum 23.6 s → 10.5 s (2.26×), of which essentially all
is rc3's pre-existing direct serving (B was 22/22 admitted before the
probe); ON/OFF = 1.014 proves the probe neither helps nor harms
contact-selected scripts outside its contract. No success claim rests
on B.

## 11. Cold check

Target-subset cold (fresh cache/run, ON vs OFF): median delta −0.019 s —
no material worsening (within ±2× the 41.5 ms repeatability spread, per
prereg). Per-workload: large books improve even cold (build+serve ≈
11–12 s vs parse+loop ≈ 14–15 s where build < parse); small books flat
(±50 ms noise); FM_08_02 pair slower cold (+0.9–1.2 s) where artifact
build exceeds reference parse — the known build/ref≈1.37 ratio, not a
probe regression. Cold and warm reported separately, never averaged.

## 12. Fallback/materialization behavior

Post-D1 A/B warm: 37 DIRECT_RUNTIME, 9 REFERENCE_FAST_PATH (whole-script,
non-target shapes), 2 DIRECT_WITH_FALLBACK — both pre-existing rc3
escapes also present under OFF (verified), unrelated to iteration. Zero
iteration-attributed fallbacks on A/B. Adversarial fallback paths
(values_only/dynamic-bounds/sparse-empty/signature-mismatch) verified
triggering with recorded reasons and identical behavior. `C_415`
(C-sample): DIRECT_RUNTIME, stdout identical except the pre-existing
KeyError-message gap on its missing-sheet error path (§7).

## 13. Proxy/allocation economics

ProxyCell construction: 0.48 µs/cell (200k loop) — 10k cells ≈ 5 ms
against seconds of avoided parse; the preregistered >50%-erasure
tripwire is nowhere near tripping. Per-cell wall favors ON on 11/13
targets (2 tiny ones within noise). RSS peak on the 8.3 MB book: base
998 MB vs probe 149 MB (6.7× less — ephemeral proxies vs openpyxl's
`_cells` cache). Memory impact is strictly positive. No object-model
redesign indicated; simple ephemeral proxies suffice.

## 14. Limitations

- Gate-form limitation (D2): the fixed 208 ms × 10/13 count form cannot
  be cleared by small-parse workloads (6 targets have total walls ≤0.52 s
  and parses below bar+tax). A mass-based gate (e.g. fraction of
  representative parse mass converted with per-workload non-regression)
  would have cleared overwhelmingly; adopting it post hoc would be
  redefining success, so the verdict follows the written gate.
- D1 premise error (merges unmeasured by a broken probe) corrected with
  full re-certification; frozen contract files left untouched, correction
  in `DEVIATIONS.md`.
- Single-host timing with observed machine variance (BASE walls varied
  ~2× between runs on giants); paired reps + intervals used throughout,
  and gains exceed variance by orders of magnitude where mass exists.
- Certified attribute set exceeds observed use (`.row`/`.column`/
  `.data_type` permitted though unobserved in targets) — served
  identically and adversarially covered, but strictly the contract could
  be tightened to value/coordinate.
- Repeat-iteration identity and proxy type/repr gaps (documented §6).
- Pre-existing KeyError-message gap (§7) widens in exposure with broader
  admission; must-fix before any productization.
- Single-model lineage bounds generality, as in all prior phases.

## 15. Productization verdict

**MECHANISM_REAL_BUT_NOT_PRODUCT.** The preregistered count gate fails
(7/13 ≥ 10/13), so PRODUCTIZE is unavailable despite 13/13 direct
conversion, zero deviations, 4.21× representative speedup, and strictly
positive memory impact. The failure localizes to gate miscalibration
(D2: fixed bar vs small-parse tail), not to serving defects — but the
verdict follows the written rule. CLOSE is rejected (semantics pass;
economics pass decisively where mass exists). REVISE_AND_RETEST is
rejected (no mechanical defect; the small-workload wash is the fixed
wrapper tax, i.e. the separately-closed persistence question). For any
future product decision, the corrected gate should be mass-based, e.g.:
≥90% of representative reference-path parse mass converted to direct
with zero deviations and no per-workload warm regression beyond noise —
a gate this probe's evidence would clear (64.5 s → ~7 s on targets,
no regressions beyond ±50 ms noise on small books).

## 16. Reopen conditions

- This probe's CLOSED items (if any future reader treats the verdict as
  CLOSE): reopen on ≥2× newly measured mass or a new agent class per the
  architecture ledger.
- The small-parse tail reopens only via the persistence question
  (R1 OBSERVE_MORE): fixed-tax removal, not serving, is its lever.
- Merged serving beyond the certified attribute contract (type checks,
  writes, rich access on merged children) needs its own probe; current
  certification covers reads only.
- Any productization must first fix the KeyError-message gap and
  re-run the 39-case adversarial suite plus A/B parity on the release
  candidate.
