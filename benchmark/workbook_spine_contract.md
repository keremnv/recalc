# Workbook spine relational contract

This database is an immutable, read-only compiled representation of one
workbook. Entity IDs use the existing spine identity namespace: `cell:s03:r41:c8`,
`sheet:s03`, `row:s03:r41`, `col:s03:c8`, `formula:s03:r41:c8`, and canonical
`range:s03:r1:c1:r2:c2` IDs. A `cell:sheet:s03:...` spelling is an alias that
must normalize to `cell:s03:...`; it is not a second identity.

## Relation meanings

`workbooks`, `sheets`, `rows`, `columns`, and `cells` describe workbook
structure. `cells` contains the materialized workbook cells plus explicit
reference endpoints needed for lookup. A physical cell's existence does not
imply task relevance. Cell kinds are `blank`, `text`, `numeric`, `formula`, or
other source-preserved kinds.

`text_anchors` stores exact and normalized workbook text. Text equality or
similarity does not establish semantic identity.

`formulas` attaches source formula text to its formula cell. Formula text may be
opaque or bounded by the frozen compiler's existing source representation.
`formula_classes` and `formula_class_members` store location-relative
mechanical formula identity. The same fingerprint means normalized structural
equivalence; it does not mean business-semantic equivalence or authorization to
copy a formula.

`point_references` contains explicit single-cell references parsed from formula
slots. Absolute/relative flags and row/column deltas describe the parsed slot.
`range_references` contains explicit rectangular range references through a
canonical `ranges` row. Point references and range membership are deliberately
separate facts.

`temporal_coordinates` contains direct and propagated time identity from the
frozen E1-E3 deterministic closure. `derivation_kind` distinguishes local and
propagated coordinates. `temporal_provenance` records the already-compiled
provenance path; querying it is not a request to rediscover a long formula
chain.

The convenience views are transparent joins over these base relations. They do
not rank candidates or add semantic facts.

## Operational warnings

- A dependency does not imply a missing formula.
- A repeated workbook pattern is not an output invariant.
- Multiple workbook entities may remain valid candidates.
- Do not invent workbook objects absent from the database.
- Formula classes are evidence, not authorization.
- Preserve ambiguity when the database does not distinguish alternatives.
- A range reference is not interchangeable with an arbitrary list of points.
- Cross-sheet identity must be established by stored IDs and relations, not by
  label similarity alone.
- Resolver preferences, if supplied by a caller, are advisory and never delete
  database candidates.

## Query discipline

Use IDs returned by one query as inputs to later queries. Narrow results by
sheet, row, column, formula class, temporal coordinate, or explicit joins. A
large result is not silently truncated: the executor returns `RESULT_TOO_LARGE`
and the query must be refined or explicitly limited by the caller.
