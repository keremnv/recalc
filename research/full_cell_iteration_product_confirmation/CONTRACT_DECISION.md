# R3 product contract decision (recorded before confirmatory scoring)

## Question (§2)

Should `.row`, `.column`, and `.data_type` remain in the certified
iteration-derived cell contract, although the 13 historical targets only
use `.value` + `.coordinate`?

## Decision: RETAIN all five

`{.value, .coordinate, .row, .column, .data_type}` stays the certified
iteration cell surface. Rationale against the default rule's three
conditions:

1. **Already part of the existing ProxyCell contract.** All five are
   shipped rc3 `ProxyCell` behavior, not probe additions: `.value` /
   `.data_type` are served from read state for point reads;
   `.coordinate` is precomputed at construction; `.row` / `.column` are
   stored construction coordinates. The probe reuses the identical
   object for yielded cells; no new attribute path was created.
2. **Exact differential coverage.** R2 adversarial cases `attrs_types`,
   `attrs_array`, and `merged_attrs` print all five attributes for every
   yielded cell — including blank cells, merged children, formulas,
   dates, booleans, errors, and array/data-table formulas — and all
   passed byte-identical against pinned openpyxl 3.1.5.
3. **No admission-proof enlargement.** The classifier permits the five
   through one shared set membership (`ITER_CELL_ATTRS`) in a single
   Name-walk. Tightening to two attributes would not simplify the proof;
   it would add a second set plus new blockers for shapes already proven
   identical — a larger diff with no risk reduction.

Compatibility risk of retention is nil beyond the existing ProxyCell
surface: `.row`/`.column`/`.coordinate` are pure functions of iteration
position, and `.data_type` reuses the point-read mapping (sparse miss →
`(None, 'n')`, matching empty cells).

## Frozen product contract (maximum scope)

- `ws.iter_rows()` with static int/None bounds or absent (dimension
  bounds); nested row → cell consumption; rows are tuples.
- Per-cell reads: `.value`, `.coordinate`, `.row`, `.column`,
  `.data_type`.
- `value is not None` filtering; blank cells yielded with `None`.
- Merged-range intersection served (children read `None`/`'n'`).
- No cell/row stores, aliases, escape, identity use, rich access,
  writes, `values_only`, `iter_cols`, sheet iteration, row
  indexing/materialization, positional/dynamic bounds, or `data_only`.

Anything outside this contract keeps the whole-script reference path.
No broadening beyond this set occurs in R3.
