# Phase 2 role-aware authority frontier report

Date: 2026-09-14  
Mode: zero-model, evaluator-side/static only  
Verdict: **`MULTIPLE_ROLE_DISTINCTIONS_REQUIRED`**

## Executive result

The remaining misses are not one generic grounding-quality problem. The census
finds at least four materially different frontend boundaries:

1. Task IR fields survive, but their field-to-target role is not composed
   (553 missed gold-cell observations).
2. The child obligation needs parent context, but the Task IR records only
   sequencing and not inheritance (153 observations).
3. A population or occurrence role is not represented even though labels,
   cells, and in one case dependency direction are present (41 observations).
4. The requested table body has no mechanically supported extent relation
   (345 observations).

There are also 14 observations that are clean planner choices with sufficient
candidate evidence, and 63 observations with no usable planner response. The
clean selection cases are too small to make model selection the dominant
frontend explanation.

No new semantic representation or runtime rule was installed. No live planner
A/B was launched. Scheduler execution remains frozen, `04_01` was not
continued, and FM20 was not launched.

## Census scope and method

The archived feasibility population contains 11 tasks. Ten produced usable
Task IR and 72 obligations; `Financial_Model:17_05` is the archived missing-IR
provider case. Evaluator gold is available for 27 obligations across four of
the five prioritized tasks. The fifth prioritized task, `Financial_Model:08_01`,
has no evaluator gold in this archive and is retained below as an unannotated
context diagnostic.

The annotated slice contains 1,204 obligation-level gold-cell observations:

| quantity | count |
| --- | ---: |
| archived obligations | 72 |
| annotated obligations | 27 |
| annotated obligations with missed authority | 19 |
| gold-cell observations | 1,204 |
| missed gold-cell observations | 1,169 |
| unique missed gold cell IDs | 1,139 |
| gold-cell observations with correct saved authority | 35 |
| annotated obligations with no missed gold | 8 |

The census converts gold addresses and saved expanded authorities to the
canonical cell-ID namespace, checks the current repaired compiled world, and
reprojects the archived obligations through the already-frozen repaired
temporal world. It records both complete candidate membership and saved
foreground/region evidence. A target absent from the complete candidate set is
not called a planner choice. A target present in the candidate evidence but
absent from a valid expanded plan is eligible for the model-selection class.

The complete per-cell accounting is in
[`role_aware_authority_census.csv`](../history/loose_evidence/role_aware_authority_census.csv). The
structured version, including obligation records, parent context, candidate
counts, secondary causes, unannotated diagnostics, and ranked distinctions is
in [`role_aware_authority_census.json`](../history/loose_evidence/role_aware_authority_census.json).
The reproducible static census is
[`benchmark/role_aware_authority_census.py`](benchmark/role_aware_authority_census.py).

## Earliest supported loss boundary

Primary classifications are mutually exclusive per missed gold-cell
observation. Secondary causes are independent flags and therefore do not add
to the primary total.

| earliest supported category | obligations | missed gold cells | share |
| --- | ---: | ---: | ---: |
| `TASK_IR_OMISSION` | 0 | 0 | 0.0% |
| `TASK_IR_CONTEXT_RELATION_LOSS` | 3 | 153 | 13.1% |
| `GROUNDING_FIELD_INTERFACE_LOSS` | 4 | 553 | 47.3% |
| `SPINE_FACT_MISSING` | 0 | 0 | 0.0% |
| `SPINE_FACT_PRESENT_NOT_PROJECTED` | 0 | 0 | 0.0% |
| `ROLE_RELATION_NOT_REPRESENTED` | 2 | 41 | 3.5% |
| `STRUCTURE_NOT_MECHANICALLY_DEFINED` | 2 | 345 | 29.5% |
| `EVIDENCE_PRESENT_MODEL_WRONG_SELECTION` | 2 | 14 | 1.2% |
| `PLANNER_RESPONSE_MISSING` | 6 | 63 | 5.4% |
| `EXPANSION_ERROR` | 0 | 0 | 0.0% |

The zero `SPINE_FACT_MISSING` count is important: every one of the 1,169
missed gold targets is a cell inside the current compiled workbook world. That
does not mean every target role is encoded. The table-body cases demonstrate
the difference between compiled cells/formula runs and a compiled body
relation.

The eight annotated obligations with no missed gold are recorded as
`NO_FRONTEND_LOSS` in the per-cell CSV rather than being included in the
missed-cell primary table.

## Obligation and population accounting

This table is the compact obligation-level view of every missed annotated
population. The CSV contains one row for every gold-cell observation, including
the relevant Task IR fields, inherited context, workbook facts, packet
membership, saved authority, and the same category evidence.

| task / obligation | missed gold population | primary | secondary | supported evidence |
| --- | --- | --- | --- | --- |
| `05_01 O1` | IRR Calculation D14:D15,D25:D26 (4) | `PLANNER_RESPONSE_MISSING` | — | IRR sheet and row anchors exist; fragment timed out before selection. |
| `05_01 O2` | IS - Mgmt Co. DK total cells (36) | `ROLE_RELATION_NOT_REPRESENTED` | `GROUNDING_FIELD_INTERFACE_LOSS` | DK7 is the compiled `Total` anchor and DK cells exist, but no total-column role relation enters target composition. |
| `05_01 O6` | Dashboard G43/I43, G44/I44, G45 (5) | `PLANNER_RESPONSE_MISSING` | — | Timeout; no selection to attribute. |
| `05_01 O7` | Workings Cost Sheet O29:DI31 (297) | `GROUNDING_FIELD_INTERFACE_LOSS` | `ROLE_RELATION_NOT_REPRESENTED` | IR scope says all three tranches; B29:B31 labels exist; subject-only composition selects Total Fund Raised row 27. |
| `15_05 O1` | Formats first-table body (193) | `STRUCTURE_NOT_MECHANICALLY_DEFINED` | `ROLE_RELATION_NOT_REPRESENTED` | Headings/cells/runs exist, but no explicit table object or heading-to-body extent relation exists. |
| `15_05 O2` | Formats E25:M25 (9) | `EVIDENCE_PRESENT_MODEL_WRONG_SELECTION` | — | E24:M25 and D25 Net Margin are in candidate/region evidence; valid plan selects P:X and AA:AI. |
| `15_05 O3` | IS_BS_CF ratio section (132) | `TASK_IR_CONTEXT_RELATION_LOSS` | `PLANNER_RESPONSE_MISSING` | Full/raw parent Formats context exists; child has sequencing but no locus/table inheritance; saved response failed to parse. |
| `15_05 O4` | Formats AY:BA rows 50,52,54,56,59,61,63 (21) | `GROUNDING_FIELD_INTERFACE_LOSS` | `ROLE_RELATION_NOT_REPRESENTED`, `PLANNER_RESPONSE_MISSING` | Below-table/metric list survives IR and output formulas exist; generic logical-functions subject yields no target role. |
| `15_05 O5` | Formats AY:AZ on the seven output rows (14) | `TASK_IR_CONTEXT_RELATION_LOSS` | grounding/role/response | Period and output-property fields survive, but parent O4 metric and below-table context is not inherited. |
| `15_05 O6` | Formats BA on the seven output rows (7) | `TASK_IR_CONTEXT_RELATION_LOSS` | grounding/role | Same parent-context loss; valid plan guesses AX38:AX44 instead of BA50/52/54/56/59/61/63. |
| `15_05 O7` | Report Tables Particulars body (152) | `STRUCTURE_NOT_MECHANICALLY_DEFINED` | `ROLE_RELATION_NOT_REPRESENTED` | Particulars heading/body labels exist, but body extent is not a compiled relation; plan selects heading row only. |
| `15_05 O8` | Report Tables C30:I32 and G34:I36 (30) | `PLANNER_RESPONSE_MISSING` | — | Timeout; section labels and anchors exist but there is no returned selection. |
| `03_01 O1` | Balance Sheet O5:P13 (18) | `PLANNER_RESPONSE_MISSING` | — | IR locus, Asset subject and CAGR intervals exist; fragment was truncated. |
| `03_01 O4` | Income Statement R5:AA31 growth block (230) | `GROUNDING_FIELD_INTERFACE_LOSS` | `ROLE_RELATION_NOT_REPRESENTED` | `required_change` says year-on-year growth and R2 is `Growth (%)`, but generic all-line-items subject is used with no output-column relation. |
| `03_01 O5` | CF I39:M39 (5) | `GROUNDING_FIELD_INTERFACE_LOSS` | `ROLE_RELATION_NOT_REPRESENTED` | CF B39 and target cells exist; locus resolution chooses the wrong sheet/row relation and plan guesses row 33. |
| `03_01 O6` | Valuation D6:H6 (5) | `EVIDENCE_PRESENT_MODEL_WRONG_SELECTION` | — | D6:H6 Tier 1 assumption and D8:H8 output are candidate-visible; valid plan authorizes only D8:H8. |
| `13_05 O1` | Input Sheet I20:M20 (5) | `PLANNER_RESPONSE_MISSING` | — | The frozen temporal projection repair puts all FY26:FY30 targets in current candidates; saved fragment timed out. |
| `13_05 O3` | Input Sheet I58:M58 (5) | `ROLE_RELATION_NOT_REPRESENTED` | `GROUNDING_FIELD_INTERFACE_LOSS` | B58 is `=B25`; B58→B25 survives full and projected packets, but source-vs-target occurrence role is absent. |
| `13_05 O4` | Debt Schedule K13 (1) | `PLANNER_RESPONSE_MISSING` | — | Provider returned finish error/content null; target is current-candidate-visible. |

The two clean selection obligations account for all 14 primary
`EVIDENCE_PRESENT_MODEL_WRONG_SELECTION` cells. The 05_01 O2 totals miss is
not counted there: its DK cells are not in the complete target candidate set,
even though the DK7 `Total` label is present. That is exactly the
output-column/row-role boundary this phase is intended to separate.

## Tranche population: identity is not membership, and membership is not role

`05_01 O7` is the positive population case:

```text
subject: total funds raised
scope:   for all three tranches; from Apr-25 to Jun-33
gold:    Workings Cost Sheet O29:DI31
```

The Task IR preserves the phrase `all three tranches`. The spine has repeated
labels at B11:B13, B17:B19, B23:B25, and B29:B31, including the desired
First/Second/Third Tranche rows under Total Fund Raised. A scope-only lexical
shadow finds all three desired row labels, but also finds 11 other label
occurrences and an unrelated `Transfer from` match: 14 shadow hits total.
The normal subject-driven target set instead contains the Total Fund Raised
row 27 and none of the 297 gold cells.

`05_01 O6` supplies the restriction contrast:

```text
subject_interval: second → third
scope:           for second and third tranches; for all deals
```

The exact scope shadow returns two `First Tranche` labels. There is no usable
planner response for this obligation, so the shadow is not promoted into an
authority claim. It does establish the overreach test: “second and third” is
not the same as “all labels matching tranche”, and an ordinal restriction needs
all of:

| distinction | evidence required |
| --- | --- |
| mention identity | which task span introduced the phrase |
| population membership | which workbook entities belong to the named set |
| ordinal/member identity | First, Second, Third, or an explicit member interval |
| inclusion | members that must be targeted |
| exclusion/restriction | members that must not be targeted |
| target role | the correct repeated occurrence/block, not merely a matching label |

The evidence supports a set-membership/inclusion distinction as a candidate
for a focused static contrast. It does not support a generic scope-to-target
union rule: that would include the wrong repeated tranche blocks and, for O6,
First Tranche.

## Inherited context: available, unlinked, and unused are separate

The full raw task is retained in all 72 saved fragments. However, 20
obligations have `then_after` edges whose referenced obligation IDs are absent
from the shard's `GENERATED_TASK_IR`. This is a structural warning, not proof
that all 20 edges are semantic losses.

The annotated evidence supports three context-relation losses:

- `15_05 O3`: the raw task and preceding O1/O2 context establish the Formats
  / Consolidated Financials setting, but the child locus is only “the balance
  sheet of the Consolidated Financials table”. Its `then_after: [O2]` records
  order, not inheritance of the parent locus/table context.
- `15_05 O5` and `O6`: the child obligations retain their periods and output
  properties, while the parent O4 contains the metric list and “below the
  consolidated Quarterly Result Table” locus. Those fields are not copied or
  relationally linked into the children.
- `08_01 O3` is retained as an unannotated diagnostic: O2 says
  `for Aug-23 to Dec-28`, O3 says `for the same timeframe`, and the child scope
  projection remains empty. The `then_after` edge is sequencing only. It is
  excluded from all gold-cell counts because no evaluator gold is archived.

These are `TASK_IR_CONTEXT_RELATION_LOSS`, not `TASK_IR_OMISSION`: the useful
context exists in the full task or parent obligation. A future relation must be
explicit and scoped; propagating every parent locus or scope to every child
would overreach.

## Output roles are not temporal roles

Temporal coordinates are present in the relevant cases and are not the missing
distinction.

- `03_01 O4` has R2 `Growth (%)` and formula cells in R5:AA31. The Task IR has
  `required_change: calculate year-on-year growth`. The grounder consumes the
  generic `all line items` subject but does not relate that required change to
  the Growth output columns.
- `05_01 O2` has DK7 `Total` and DK target cells, while the monthly temporal
  span is O:DI. The missing relation is “total column for each component”, not
  a year coordinate.
- `15_05 O4` has AV2 `Quarterly Result Table (Consolidated )`, output formulas
  and the AY/AZ/BA columns. O5/O6 retain the periods 3QFY23, 2QFY24, and
  3QFY24E. What is missing is the relation from the metric list/parent output
  role to the seven separated output rows, not temporal identity.

The census therefore does not propose broadening the temporal interval or
calling output labels “subjects”. It records a field-to-output-role loss and,
where the workbook itself does not encode the relation, a separate role
relation loss.

## Linked occurrences: dependency survives, requested role does not

For `13_05 O3`, the relevant workbook facts are:

```text
Input Sheet B25: text-side Rate per Square Feet occurrence
Input Sheet B58: formula =B25, cost-side linked occurrence
Input Sheet I58:M58: blank target cells
B58 → B25: point dependency survives compilation and packet projection
```

The subject text is the same semantic label family. The current target packet
selects the revenue-side B25 row and the valid plan changes J25:M25. It does
not select the cost-side I58:M58 gold region. Adding another dependency edge
would not address this miss: the edge already exists in the full and projected
packets. The missing distinction is occurrence identity plus source-vs-target
role/context. One counterexample is enough to keep this candidate visible, but
not enough to justify a live A/B or automatic alias propagation.

## Table bodies: no supported mechanical detector exists

The 15_05 input workbook has no OOXML table parts / explicit Excel Table
objects. The spine provides merged headings, text anchors, cell occupancy,
formula-equivalence runs, and ordinary row/column facts. Those facts do not
deterministically distinguish:

```text
heading | body | totals | adjacent unrelated cells
```

Consequently, `15_05 O1` (193 first-table body cells) and `O7` (152
Particulars body cells) are classified as
`STRUCTURE_NOT_MECHANICALLY_DEFINED`, not as a discarded known table fact.
The heading-to-body relation must not be invented from adjacency or formula
runs in this phase.

## Existing distinctions versus composition loss

| distinction | exists in Task IR | exists in compiled world | reaches target role correctly | conclusion |
| --- | --- | --- | --- | --- |
| temporal identity | yes, where stated | yes after frozen same-world repair | demonstrated planner value in the prior frozen probe | leave frozen |
| tranche population text | yes (`all three`, `second and third`) | repeated ordinal anchors/cells | no population/block relation | candidate static contrast |
| inclusion/exclusion | lexical phrase only | member labels exist | no explicit member-set object | candidate, no generic rule |
| parent context | often in raw/full/parent obligation | workbook loci/labels exist | no child inheritance relation | candidate static contrast |
| growth/total/output role | required change or subject wording exists | output labels/formulas/cells exist | no deterministic field-to-output relation | candidate, separate from time |
| occurrence/source-target role | not explicit as a role field | B58→B25 edge exists | edge survives; role selection does not | single-case candidate |
| table body | task names table/body concept | headings/cells/runs exist | no supported body extent | not currently defined |

The earlier temporal, percentage-unit, and hash-order repairs remain held fixed.
The current census found no new dropped compiled relation, corrupted stable ID,
or deterministic expansion defect. In particular, it found no basis to widen
authority after expansion and no basis to add dependency structure for 13_05
O3.

## Earned-distinction ranking

“Field provenance to target role” is an umbrella description, not a proposed
single abstraction. The evidence says it should be split into the following
experiments:

| rank | candidate distinction | empirical support | deterministic coverage measure | overreach test | status |
| ---: | --- | --- | --- | --- | --- |
| 1 | population/member restriction | 05_01 O7: 297 cells; O6 supplies “second and third” contrast and First-Tranche shadow false hits | desired-member recall, target-block recall, excluded-member false positives | O7’s 14 lexical hits; O6’s First-Tranche hits; repeated tranche blocks | earned attention; not a runtime representation |
| 2 | output-column/row-role relation | 03_01 O4: 230; 05_01 O2: 36; 15_05 O4–O6: 42 | candidate∩gold and role-specific region precision/recall | growth block vs C63:P100; DK total vs O:DI monthly; AY/AZ/BA vs unrelated rows | earned attention; must remain distinct from population |
| 3 | explicit parent-context inheritance | 15_05 O3–O6: 174 annotated cells plus 08_01 O3 diagnostic | child field/context preservation and target recovery by explicit parent edge | do not propagate context across unrelated siblings | earned attention; no generic copy rule |
| 4 | occurrence/source-vs-target role | 13_05 O3: 5 cells with dependency already present | B25-versus-B58 candidate/authority precision and direction preservation | do not alias every formula-linked occurrence | single case; not earned for live A/B |
| 5 | table-body extent | 345 cells, but no supported source relation | not measurable before a structure contract exists | heading/totals/adjacent-block false authority | explicitly not earned |
| 6 | planner-only choice | 14 cells in two valid plans | candidate evidence → expanded authority precision/recall | do not label absent candidates as model error | already isolated; not the current frontier |

No candidate has genuinely earned a planner-only live A/B in this phase. The
population and output-role candidates have enough evidence for an evaluator-
side static contrast, but not for a live test that would conflate multiple
roles or broaden authority.

## Deterministic defect and repair status

No new deterministic defect was demonstrated in Phase 2, so no Phase 2 runtime
patch was made.

The zero-model replay rechecked the already-frozen repairs:

- shared temporal-world projection into planning and expansion;
- typed percentage parsing that prevents `10%` from becoming calendar year
  2010;
- stable ordering before the bounded dependency-evidence limit.

The replay reproduced all 72 archived target sets, found the existing
15_05 O2 hash-order membership instability already repaired, and kept source
hashes unchanged. The saved authorities of the nine previously valid archived
plans remained exactly unchanged. These repairs are integration/fidelity
invariants, not new role abstractions.

## Smallest next experiment

Run one more zero-model evaluator-side contrast for only the
population/member distinction:

1. `05_01 O7`: all three tranche members, correct Total Fund Raised block;
2. `05_01 O6`: second and third members, explicit First exclusion;
3. `01_01 O5`: Foundation Course lexical negative control across revenue and
   expense occurrences.

Annotate only mention span, normalized member identity, inclusion/exclusion,
repeated block role, and target cell population. Measure member recall,
block-role precision, excluded-member false positives, and whether the
relation is present in complete candidates versus only shadow lexical hits.
Do not union the shadow hits into authority. If and only if that contrast
passes, isolate a planner-only A/B for the one population relation while
holding output roles, context inheritance, temporal identity, expansion, and
scheduler execution fixed.

## High-level verdict

**`MULTIPLE_ROLE_DISTINCTIONS_REQUIRED`**

The evidence does not support a single generic scope-to-target rule. Population
membership, output role, parent-context inheritance, and occurrence role are
different relations with different deterministic coverage and overreach tests;
table-body semantics are not mechanically defined in the current workbook
world. Temporal identity remains useful and frozen. The next action is the
small static population contrast above, not a live planner A/B.
