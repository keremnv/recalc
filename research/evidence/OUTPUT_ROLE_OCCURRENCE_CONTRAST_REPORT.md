# Output-role occurrence contrast

Date: 2026-09-14  
Mode: zero-model, evaluator-side/static only  
Verdict: **`OUTPUT_ROLE_RELATION_EARNED_FOR_PLANNER_PROBE`**

## Result

For `Financial_Model:05_01 O6`, one deterministic composition recovers the
five intended Dashboard output cells with no false endpoints:

```text
included member occurrence
  → existing point dependency to copied output header
  → same-column Month header
  → right-neighbor Numbers header
  → contiguous formula-bearing Month rows
  → corresponding Numbers cells
```

It uses no gold-derived rule, finance ontology, lexical alias propagation, or
dependency closure as authority. The frozen member restriction is applied
before this path: First-Tranche starts are not traversed by the accepted
relation.

This earns a planner-only A/B in a subsequent experiment. No planner call was
launched here, and the relation was not wired into runtime grounding or
authority.

## Scope and frozen inputs

The previous member result was treated as immutable input:

```text
included: G16 Second, G17 Third, F22 Second, H22 Third
excluded: G15 First, D22 First
```

Task IR fields retained for attribution are:

```text
locus:            Dashboard
subject:          Exit Multiple
subject_interval: second → third
scope:            for second and third tranches; for all deals
required_change:  update Exit Multiple for second and third tranches to 2.0x for all deals
```

Evaluator gold was loaded only after candidate derivation for measurement:
`Dashboard!G43`, `I43`, `G44`, `I44`, and `G45`.

The current repaired packet has 24 target candidates and none of the five
gold cells. Its dependency facts and formula-class facts contain the relevant
header evidence, but not the final target population. The saved O6 fragment
was a provider timeout and has no expanded authority.

## Candidate relations tested

### 1. Direct point-dependency closure — rejected

Starting directly from the four included label cells produces only five
unique downstream endpoints:

```text
F22 → F40 → F55
F22 → Distribution Sheet-Deal By Deal!C18
H22 → H40 → H55
```

`F40` and `H40` are copied header cells. `F55` and `H55` are
`Investment Exit Value` header cells. The cross-sheet `C18` endpoint is not
the requested output population. No gold target is reached. This confirms
that dependency connectivity is not itself target authority.

### 2. Adjacent value cell followed by dependency closure — rejected

Treating a label's right neighbor as its value cell is mechanically expressible
but overbroad. `G16 → H16` and `G17 → H17` lead to 584 unique downstream
endpoints across Dashboard, Workings Cost Sheet, Distribution Sheet-Deal By
Deal, and IRR Calculation. None is gold. `F22 → G22` and `H22 → I22` do not
produce downstream endpoints.

The 584 endpoint records, including every false endpoint and its path/evidence,
are in the machine-readable CSV/JSON. This candidate is rejected because it
aliases a value cell's dependency neighborhood rather than identifying the
requested output role.

### 3. Copied-header / Month-Numbers / formula-extent relation — accepted

The accepted relation is entirely input-side and deterministic:

```text
F22 --POINT_REFERENCE--> F40
    --same output-section column--> F42 [Month]
    --right-neighbor header--> G42 [Numbers]
    --formula-bearing contiguous rows F43:F45--> G43:G45

H22 --POINT_REFERENCE--> H40
    --same output-section column--> H42 [Month]
    --right-neighbor header--> I42 [Numbers]
    --formula-bearing contiguous rows H43:H44--> I43:I44
```

The path is source-to-consumer only for the copied header edge. The remaining
steps are structural relations over existing row/column text and formula
occupancy; they are not dependency edges. Formula presence, not formula-class
equality, defines the row extent. This matters because F45 is formula-bearing
but has a distinct class/fingerprint reference, while H45 is not
formula-bearing. The relation consequently includes G45 and does not invent
I45.

The accepted endpoint population is exactly:

```text
Dashboard!G43
Dashboard!G44
Dashboard!G45
Dashboard!I43
Dashboard!I44
```

## Measurements

| measure | result |
| --- | ---: |
| included-member occurrence path coverage | 2/4 = 50% |
| included-member endpoint recall | 5/5 = 100% |
| target-cell recall | 5/5 = 100% |
| target precision | 5/5 = 100% |
| accepted false endpoints | 0 |
| intermediate/non-target false endpoints in direct closure | 5 |
| adjacent-value closure false endpoints | 584 |
| excluded-member leakage in accepted relation | 0 |
| counterfactual First-Tranche endpoints if restriction were removed | 10 |
| repeated-occurrence confusion | 0 |
| accepted endpoints already in current planner candidates | 0/5 |
| one deterministic relation covers all gold outputs | yes |

The 2/4 path coverage is intentional occurrence discrimination: `G16` and
`G17` are same-member labels in the Ticket Size block and have no copied
output-header path. They are not silently aliased to the row-22 output
occurrence. The two path-bearing included occurrences, `F22` and `H22`, cover
all five required endpoints.

## Restriction and negative checks

Applying the same structural relation counterfactually to excluded `D22 First
Tranche` would produce `E43:E52` through `D40 → D42 [Month] → E42 [Numbers]`
and the contiguous `D43:D52` formula extent. Those ten endpoints are recorded
as blocked counterfactuals, not accepted candidates. The frozen inclusion gate
therefore prevents First-Tranche leakage.

`G16` and `G17` have no `row-22 → row-40` copy edge, so the accepted relation
does not merge the Ticket Size occurrence with the output occurrence. The
direct-dependency candidate does expose the non-target copied headers and
downstream `Investment Exit Value` headers, demonstrating why an unfiltered
dependency path is insufficient.

The accepted relation has no false endpoints. All false endpoint records from
the rejected candidates and all counterfactual excluded endpoints are present
in the machine-readable contrast table.

## Compiled-world evidence

| evidence | finding |
| --- | --- |
| point dependencies | `D22→D40`, `F22→F40`, `H22→H40`; the copied-header relation already exists |
| reverse dependencies | each accepted gold cell is a source to later Dashboard cells (`G43→G57`, `I43→I57`, etc.), not a consumer of the member label |
| formula fingerprints | D/F/H header copies share `=C[0]R[-18]`; Month formulas are present in F43:F45 and H43:H44 |
| row/column labels | row 42 mechanically contains paired `Month` / `Numbers` headers |
| stable identities | cell IDs and source/consumer direction are retained throughout |
| compiled regions | no existing compiled region covers the accepted target cells |
| occupancy/formulas | gold targets are blank in the spine and have no formulas; adjacent Month cells provide the deterministic extent |
| raw workbook formatting | gold cells carry `0.00"x"` number formats, corroborating role but not used by the relation |
| planner packet | member/header evidence is partially present; none of the five final targets is in current target candidates |

The target cells are therefore not absent from the workbook address space, but
their final target role is not an explicit compiled relation. The accepted
composition must be newly derived from relations that are individually latent:
copied-header dependency, repeated header pairing, formula-bearing row extent,
and stable coordinates.

The relation does not use lexical equality to alias labels. It uses the frozen
member identity only to choose the allowed starts, dependency direction to
connect row-22 headers to row-40 headers, and generic workbook structure to
select the value columns and rows.

## Planner decision and next experiment

The static contrast satisfies the causal-isolation requirement:

```text
member identity: frozen
restriction:     frozen
output relation: the only changed distinction
```

It therefore earns, but does not launch, a planner-only O6 A/B. The treatment
packet should add only the five accepted target endpoints and their path
evidence to the frozen member-grounded packet; the control should remain the
archived packet. The A/B must measure authority-bounded selection and retain
the First-Tranche exclusion check.

No deterministic implementation defect was found. No runtime patch is
proposed. The smallest next experiment is that isolated planner-only O6 A/B;
runtime integration remains deferred until that causal test is complete.

## Artifacts

- [`output_role_occurrence_contrast.csv`](../history/loose_evidence/output_role_occurrence_contrast.csv)
- [`output_role_occurrence_contrast.json`](../history/loose_evidence/output_role_occurrence_contrast.json)
- [`benchmark/output_role_occurrence_contrast.py`](benchmark/output_role_occurrence_contrast.py)

All artifacts were produced with zero model calls, zero workbook writes, a
frozen scheduler, and no FM20 execution.
