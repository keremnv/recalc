# Edit Plan V1

Describe the intended edit set using workbook coordinates and structural identities.
The harness expands it; do not enumerate large cell lists. All bounds are inclusive,
one-based. Sheet IDs use the supplied canonical identity, not a sheet name.
Use only workbook identities in the supplied context. Physical presence is not
evidence that a cell needs editing. Blank cells are not automatically erroneous.
Raw task text remains authoritative evidence alongside the generated obligations.

An operation has operation_id (unique), obligation_id (supplied generated ID),
operation_kind, target_set, and optional occupancy_filter, explicit_exceptions,
source_relation, sequencing. The accompanying JSON Schema is the exact grammar.
Return only {"operations":[...]} with no explanatory prose.

Operation kinds: SET_FORMULA assigns a formula; REPLACE_FORMULA denotes formula
replacement; FILL_FORMULA expresses a shared relative program across a region;
CLEAR_CELL clears content. Do not use FILL_FORMULA for heterogeneous formulas
merely because their targets form a rectangle. Kinds do not silently add occupancy
filters. Filters must be explicit. Literal value setting is outside this language.

Target sets:

- CELL(cell_id): a single coordinate, for genuinely isolated edits.
- SHEET(sheet_id): compiled inclusive used rectangle, including implicit blanks.
- RECTANGLE(sheet_id,r1,c1,r2,c2): inclusive coordinate rectangle.
- ROW_INTERVAL(sheet_id,row_start,row_end,col_start?,col_end?): omitted columns use
  compiled sheet bounds. COLUMN_INTERVAL similarly uses optional row bounds.
- TEMPORAL_INTERVAL(sheet_id,axis,start_coordinate,end_coordinate,row_constraint?):
  endpoints are existing temporal IDs on the same sheet/axis. Select materialized
  temporal coordinates whose ordered year/month (or quarter start month) lies
  inclusively between endpoints; do not fill intervening unlabelled axes. Axis is
  row or column; optional row_constraint is {r1,r2}. Endpoints need a year.
- FORMULA_CLASS_MEMBERS(fingerprint_id,sheet_id?): input formula cells in that class.
  Mechanical structure does not establish task relevance or business equivalence.
- UNION and INTERSECT have a nonempty sets array. DIFFERENCE has exactly two sets,
  left minus right. Empty intersections and empty valid selections are possible.

All coordinates must exist in the compiled world: stored cells or implicit blanks
inside compiled sheet bounds. The runtime never creates a new sheet or identity
universe. Filters inspect the frozen input occupancy after set evaluation:
BLANK_ONLY, NONBLANK_ONLY, FORMULA_ONLY, NONFORMULA_ONLY. No inferred business roles.

Exceptions: explicit_exceptions={include:[cell IDs],exclude:[cell IDs]}, maximum
16 combined per operation. Apply filter, then includes, then excludes. They are
for irregular edges, not a replacement for set expressions. Do not evade this
with a long series of singleton operations.

Sequencing={after:[operation IDs]} is an acyclic dependency order; absent it,
array order is used. Selection/filtering always observes frozen input. It does
not mean reevaluate occupancy after earlier writes. source_relation={entity_ids:[]}
may cite known cells, sheets, formula classes or temporal coordinates as evidence;
it does not retrieve or select additional targets.

Generic examples (illustrative identities only; substitute supplied IDs):

1. Two rows, columns 4–12, currently blank cells:
{"operations":[{"operation_id":"op1","obligation_id":"O1","operation_kind":"SET_FORMULA","target_set":{"kind":"RECTANGLE","sheet_id":"sheet:s00","r1":6,"r2":7,"c1":4,"c2":12},"occupancy_filter":"BLANK_ONLY"}]}

2. Replace existing formulas in one column interval:
{"operations":[{"operation_id":"op1","obligation_id":"O1","operation_kind":"REPLACE_FORMULA","target_set":{"kind":"COLUMN_INTERVAL","sheet_id":"sheet:s00","col_start":4,"col_end":4,"row_start":6,"row_end":20},"occupancy_filter":"FORMULA_ONLY"}]}

3. Two separate regions can be one operation with target_set
{"kind":"UNION","sets":[{"kind":"RECTANGLE","sheet_id":"sheet:s00","r1":3,"r2":3,"c1":4,"c2":8},{"kind":"RECTANGLE","sheet_id":"sheet:s00","r1":9,"r2":9,"c1":4,"c2":8}]}.

Grounding candidate rectangles below are lossless compression of existing
grounding output, not constraints that prohibit other task-supported coordinates.
Use raw instructions and supplied sheet/row/column identities to specify the
complete intended regions. Do not change every plausible source candidate.
