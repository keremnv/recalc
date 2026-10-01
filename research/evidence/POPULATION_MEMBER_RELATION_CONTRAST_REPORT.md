# Population/member relation contrast

Date: 2026-09-14  
Mode: zero-model, evaluator-side/static only  
Verdict: **`MEMBER_IDENTITY_EARNED_ROLE_UNRESOLVED`**

## Result

An explicit population/member relation is mechanically supported for the two
tranche contrasts, but it is not sufficient as a target-authority relation.
It recovers the `05_01 O7` member population and rejects `First Tranche` for
`05_01 O6` without lexical union. It preserves repeated occurrences as
separate cell/run identities. `O6` still lacks a mechanically safe relation
from the selected members to the intended output-value columns, and `01_01
O5` retains a line-item-role ambiguity after the wrong sheet is removed.

No runtime grounding, planner, authority, scheduler, synthesis, or workbook
operation was run or changed. The experiment analyzed exactly three archived
obligations. `O6` and `O7` have evaluator gold; the `O5` control has no
archived evaluator gold.

## Candidate representation

The evaluator-side relation is:

```text
R(span, occurrence) iff
  span provenance is retained as the introducing Task IR scope span
  AND normalized population label matches
  AND, for an explicit member set, occurrence member identity is allowed
      and is not in the observed excluded-member set
  AND occurrence identity is retained as cell ID plus repeated-run context
```

The tranche parser derives `First`, `Second`, and `Third` from the leading
ordinal in an existing text anchor. For `all three tranches`, the allowed set
is `{First, Second, Third}`. For `second and third tranches`, the allowed set
is `{Second, Third}` and the observed `First` member is explicitly excluded.
This is a set relation, not a universal `tranche` lexical match.

For the O7 measurement only, a separate deterministic role check selects a
vertical three-member run whose same-column anchor two rows above matches the
Task IR subject `total funds raised` after simple singular/plural
normalization. The existing row-4 period axis then expands the selected rows
across O:DI. This is an evaluator-side contrast, not a generic role-aware
grounding rule.

Gold is used only for measurement. It is not used to derive the relation or
choose a candidate.

## Measurements

“Before” is the current repaired archived packet's target-candidate count;
it is not new authority. “Member survivors” are workbook occurrences after
population/member restriction. “Role survivors” are cell occurrences only
where a deterministic role relation was demonstrated.

| case | before target candidates | lexical shadow hits | member survivors | role survivors | member recall | included-member precision | excluded-member FPs | occurrence precision | gold target-block recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `05_01 O7` all three | 1,037 | 14 | 12 | 3 | 12/12 = 100% | 12/12 = 100% | 0 | 3/3 = 100% | 297/297 = 100% |
| `05_01 O6` second and third | 24 | 2 | 4 | 0* | 4/4 = 100% | 4/4 = 100% | 0 | N/A* | N/A* |
| `01_01 O5` Foundation Course | 1,060 | 11 | 5† | 0 | N/A† | N/A† | N/A† | N/A† | N/A† |

\* `O6` occurrence identities are preserved, but output-role selection is
intentionally not inferred. The evaluator gold is
`Dashboard!G43,I43,G44,I44,G45`; scoring the empty unresolved target set as
an end-to-end candidate would be 0 recall, but target-block recall is marked
N/A because that would conflate this experiment with output-role grounding.

† `O5` is not a member-set case. Five lexical population occurrences remain
on the exact `Cost Drivers` locus sheet, but the relation does not claim they
are the requested line-item targets.

The complete occurrence-level measurements, provenance, context, packet
membership, candidate status, and evidence are in
[`population_member_relation_contrast.csv`](population_member_relation_contrast.csv)
and
[`population_member_relation_contrast.json`](population_member_relation_contrast.json).
The rerunnable static evaluator is
[`benchmark/population_member_relation_contrast.py`](benchmark/population_member_relation_contrast.py).

## Case contrasts

### `Financial_Model:05_01 O7`

Task IR contributes the scope span `for all three tranches` and the subject
`total funds raised`. The spine contains four distinct vertical member runs:

```text
Portfolio Building MoM       B11:B13
Portfolio Building Cumulative B17:B19
Ticket Size per Portfolio    B23:B25
Total Fund Raised            B29:B31
```

The relation first keeps all 12 member occurrences, rather than collapsing
them by label. The subject/parent-run check then keeps only `B29:B31`, whose
parent anchor is `B27 Total Fund Raised`. Crossing those three rows with the
existing O:DI axis yields exactly:

```text
Workings Cost Sheet!O29:DI31   297 cells
```

The relation therefore recovers every gold cell and removes the 11 lexical
shadow false positives. The 1,037-cell existing target candidate set had no
gold intersection; the 297-cell evaluator candidate has all 297.

### `Financial_Model:05_01 O6`

Task IR contributes the scope span `for second and third tranches` and also a
separate `subject_interval` from `second` to `third`. The derived allowed set
is `{Second, Third}` and the excluded set is `{First}`.

The six observed Dashboard tranche occurrences remain separate by run:

```text
Ticket Size block:       G15 First, G16 Second, G17 Third
Investment Starts block: D22 First, F22 Second, H22 Third
```

The relation survives `G16`, `G17`, `F22`, and `H22`; it rejects `G15` and
`D22`. Thus the member restriction itself passes with 100% member recall,
100% included-member precision, and zero excluded-member false positives.

The relation does not select target cells. The spine does contain existing
dependency facts `F22 → F40` and `H22 → H40`, and the packet contains some
member/header evidence, but no safe output-role relation was added to map
those member occurrences to the `Numbers` value columns and intended deal
rows. That is a separate role distinction, not a reason to widen the member
set.

### `Financial_Model:01_01 O5` lexical control

The scope span is `for each Foundation Course line item`; this is a population
label, not an ordinal member set. The lexical shadow returns 11 occurrences
across two semantic sheets. An exact Task IR locus-to-sheet relation removes
the six `Revenue Drivers` occurrences and retains five `Cost Drivers`
occurrences. The five retained labels are still headings or totals rather
than a mechanically selected line-item target population. They remain
separate by cell identity, so lexical equality does not merge the revenue and
cost blocks, but the target role is unresolved.

## Every lexical false-positive occurrence

The following are all shadow hits not selected by the demonstrated role
relation, or not role-selectable where the experiment deliberately stops:

| case | occurrence | reason |
| --- | --- | --- |
| `05_01 O7` | `Distribution Sheet-Deal By Deal!C30 Third Tranche` | wrong locus / repeated semantic block |
| `05_01 O7` | `Workings Cost Sheet!B11:B13` First/Second/Third | Portfolio Building MoM block |
| `05_01 O7` | `Workings Cost Sheet!B17:B19` First/Second/Third | Portfolio Building Cumulative block |
| `05_01 O7` | `Workings Cost Sheet!B23:B25` First/Second/Third | Ticket Size per Portfolio block |
| `05_01 O7` | `PreOp Cost!F1 Transfer from` | unrelated lexical shadow and wrong locus |
| `05_01 O6` | `Dashboard!G15 First Tranche (Under construction in Tier 2 cities)` | explicitly excluded member |
| `05_01 O6` | `Dashboard!D22 First Tranche` | explicitly excluded member |
| `01_01 O5` | `Revenue Drivers!B6` | wrong semantic block/locus |
| `01_01 O5` | `Revenue Drivers!B17` | wrong semantic block/locus |
| `01_01 O5` | `Revenue Drivers!B29` | wrong semantic block/locus |
| `01_01 O5` | `Revenue Drivers!B41` | wrong semantic block/locus |
| `01_01 O5` | `Revenue Drivers!B43` | wrong semantic block/locus |
| `01_01 O5` | `Revenue Drivers!B141` | wrong semantic block/locus |
| `01_01 O5` | `Cost Drivers!B6` | retained by population/locus, but heading role unresolved |
| `01_01 O5` | `Cost Drivers!B23` | retained by population/locus, but total role unresolved |
| `01_01 O5` | `Cost Drivers!B41` | retained by population/locus, but total role unresolved |
| `01_01 O5` | `Cost Drivers!B59` | retained by population/locus, but total role unresolved |
| `01_01 O5` | `Cost Drivers!B61` | retained by population/locus, but total role unresolved |

The O7 shadow false-positive count is 11; O6 is 2; O5 has six wrong-locus
hits plus five retained-but-role-unresolved occurrences. No lexical shadow
was unioned into a target candidate.

## Existing distinctions versus derived distinctions

| distinction | already present | lost or absent |
| --- | --- | --- |
| mention provenance | exact Task IR `scope` spans exist | no structured provenance-aware population relation reaches grounding |
| tranche member labels | all relevant text anchors exist in the spine | Task IR does not expose an allowed/excluded member set |
| O6 interval | `subject_interval second → third` exists | interval is not composed with scope into inclusion/exclusion semantics |
| repeated tranche runs | deterministic same-row/same-column runs exist | no relation binds the run to the requested subject role in the packet |
| O7 target axis | row-4 O:DI formula/value axis exists | member-row/subject-parent relation is not projected into the packet |
| O6 occurrence dependency | `F22 → F40` and `H22 → H40` exist | output value-column/row role is not mechanically selected here |
| O5 sheet distinction | `Revenue Drivers` and `Cost Drivers` titles exist | “Foundation Course line item” versus heading/total is not a target relation |

The required facts are not missing from the compiled workbook for these
contrasts. The proposed restriction and occurrence relation is genuinely
derived from existing Task IR text and spine facts; the explicit
allowed/excluded set is not an existing structured Task IR field. No
deterministic integration defect or invariant violation was found, so no
runtime repair was made.

## Candidate ranking and live-probe decision

1. **Explicit member identity plus inclusion/exclusion** — strongest support.
   It passes O7 and O6, with 12/12 and 4/4 member recall and zero excluded
   members surviving. It is measurable and does not broaden lexical matches.
2. **Occurrence identity preservation** — supported as a representation
   invariant in all three cases; cell/run identities remain distinct, but
   preservation alone does not choose the requested role.
3. **Subject-to-parent ordinal-run role** — demonstrated for O7 only, with
   3/3 repeated-block precision and 297/297 gold target-block recall. It is
   not generalized to O6 or O5 in this experiment.
4. **Locus-to-population-sheet restriction** — rejects all six O5
   cross-sheet lexical shadows, but leaves five same-sheet heading/total
   occurrences and therefore does not earn line-item authority.

No distinction warrants a planner-only live A/B yet. The member restriction
would be tested together with an unresolved target role, so a planner result
would not isolate the proposed distinction. The smallest next experiment is a
separate static output-role/occurrence-role contrast for O6; it is outside
this experiment and was not launched.

This result is therefore **`MEMBER_IDENTITY_EARNED_ROLE_UNRESOLVED`**, not a
generic role-aware grounding proposal and not an authority-widening result.
