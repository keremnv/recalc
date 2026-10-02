# Preregistration deviation D1: merged-range contact in targets

Status: disclosed before scoring; correction applied and re-certified.

## What was encoded incorrectly

`PREREGISTRATION.md` §2 states "no merged-range contact in any target book"
and excludes merged serving from the contract ("merged contact fails closed
to genuine openpyxl; the probe does not serve merged ranges").

That premise came from a broken probe: the merged inventory opened books
with `read_only=True`, where `ReadOnlyWorksheet` has no `merged_cells`
attribute, so `getattr(ws, 'merged_cells', None)` returned `None` for every
sheet and every book was recorded as merge-free. A corrected inventory with
full `openpyxl.load_workbook` shows merges in 12 of 13 target books
(all except `Template_15_03__68f4733f2576`).

## Measured impact (pre-correction scoring)

9 target workloads' iteration rectangles avoid merges (served direct);
4 intersect (`Debugging_10_07__e3a79d24091a`,
`Debugging_10_10__c7eca76e6646`, `Financial_Model_02_05__c75ecb00f745`,
`Financial_Model_08_02__625ec1db4acb`) and failed closed to
`DIRECT_WITH_FALLBACK` with reason `merged_intersection`, exactly as the
(incorrect-premise) contract specified. Parity held in all cases; the
runtime did the right thing given its instructions.

## Correction (narrow, fail-closed philosophy preserved)

Merged ranges are served in iteration instead of forcing fallback:

- `MemoryBook.cell` already maps merged non-anchor coords to `(None, 'n')`
  — exactly the observable `MergedCell` state for `.value`, `.data_type`,
  `.coordinate`, `.row`, `.column`.
- The observed/certified contract uses only `.value`/`.coordinate`
  (classifier permits `.row`/`.column`/`.data_type` reads); no type
  checks, writes, or rich access can reach a served merged child, so a
  proxy cell is indistinguishable from `MergedCell` within the contract.
- Any post-iteration rich access still escapes per-cell to genuine
  openpyxl (existing `ProxyCell.__getattr__`).

Changes: removed the `merged_intersection` fallback branch in
`_serve_iter_rows` (one branch); adversarial merged cases re-pointed from
fallback-expected to direct-expected with identical-output assertions;
added a `merged_attrs` case printing every cell (including children) to
differentially verify `MergedCell`-equivalence. Full certification and
warm scoring re-run after the correction.

## Why this is a correction, not scope creep

The probe question is whether *historically observed* iteration forms can
be served. Merged intersection is one of the observed forms (4/13); the
exclusion rested on a false measurement, not on evidence. No new state,
API, or semantic claim is added: the serving path reuses the already
certified merged-child mapping. The as-preregistered outcome (4/13 gate
clearances incl. 4 merged fallbacks) is reported alongside the corrected
outcome in `REPORT.md`.
