# Candidate-A A1 Classifier Repair Report

Zero-model differential proof. No model inference, prompt change, helper, model-facing syntax, semantic-surface expansion, A2/A3 implementation, or Candidate-B reopening occurred.

## Decision

`A1_CLASSIFIER_REPAIR_EARNED`

A1 changes only the eligibility classifier: it replaces the lexical bracket-colon rejection with fail-closed AST/provenance analysis. The existing proxy, fallback, formula/data_only, write, object-escape, rich-object, and generation rules remain unchanged.

## Core result

All 34 known source-recoverable false-positive turns were no longer rejected for the bogus range/slice reason. 20 were admitted to the frozen A0 surface. Newly admitted source replay was 20/20 semantic-exact against ordinary openpyxl. True unsupported controls admitted: 0.

## Classifier contract

A1 recognizes string colons and Python sequence slices without treating them as workbook ranges. It recognizes proven workbook/worksheet single-cell subscripts, real worksheet range subscripts, worksheet cell calls, values-only iterators, Cell-object iterators, and unresolved dynamic subscripts. Unresolved provenance fails closed. AST is used only for eligibility; it does not rewrite or reinterpret the Python.

## Live six-task counterfactual

A0 observed contact: **2/6**. A1 counterfactual contact opportunity: **3/6**. Contact tasks: Financial_Model:07_01, Financial_Model:08_03, Financial_Model:08_01. FM:07_01 becomes a genuine admitted/exact opportunity; Debugging remains outside the frozen surface; FM:06_01 remains runner-censored.

| task | A0 contact | A1 opportunity | admitted executions | primitive-read units | remaining blocker |
|---|---|---|---:|---:|---|
| Financial_Model:07_01 | False | True | 9 | 40 | none |
| Financial_Model:08_03 | True | True | 0 | 0 | none |
| Financial_Model:08_01 | True | True | 11 | 52 | none |
| Financial_Model:06_01 | False | UNKNOWN_RUNNER_CENSORED | 0 | 0 | runner error |
| Debugging:01_06 | False | False | 0 | 0 | data_only/Cell-object/rich |
| Debugging:05_02 | False | False | 0 | 0 | data_only/Cell-object/rich |

## Historical 309-execution ceiling

A0 frozen fully eligible executions: **72**. A1 fully eligible executions: **86**. Newly eligible: **14**. A0 read-event opportunity: 3349; A1 estimate: 3377 (+28). The additional repeated-open figure is an open-call upper bound; exact same-generation group attribution is not implied.

| family | A0 fully eligible | A1 fully eligible | newly eligible | additional read-event estimate |
|---|---:|---:|---:|---:|
| Debugging | 16 | 17 | 1 | 10 |
| Financial_Model | 48 | 52 | 4 | 18 |
| Template | 5 | 5 | 0 | 0 |
| Visualization | 3 | 12 | 9 | 0 |

## Semantic and boundary gates

Semantic differential: 20/20 exact; wrong values 0, wrong types 0, wrong order 0, wrong exceptions 0. Boundary preservation: True. Formula/data_only regression: 8/8 unchanged. Freshness stale/wrong-generation: 0/0; identity corruption: 0.

The semantic gate is **True**. The contact gate is **True**. One bounded AST-classifier repair round was used; no production runtime or semantic surface was changed.

## Required answers

1. **A0 error:** lexical `\[[^]]*:[^]]*\]` matched string literals and Python sequence slices, not only workbook subscripts.
2. **A1 identification:** AST node type plus conservative workbook/worksheet provenance; dynamic provenance falls back.
3. **Known repairs:** 20/34.
4. **Legitimate blockers after the lexical repair:** 14 known turns remained blocked by another rule.
5. **True unsupported cases incorrectly admitted:** 0.
6. **Newly contacting executions:** 20 admitted source executions; 20 exact.
7. **Semantic exactness:** 20/20.
8. **Python scalar types:** exact in every newly admitted replay.
9. **Iteration order/shapes:** exact in every newly admitted replay; no Cell-object iterator was admitted.
10. **Exceptions:** no newly admitted exception mismatch.
11. **Formula mode:** unchanged and exact under the frozen primitive shadow.
12. **data_only:** unchanged predeclared real-openpyxl fallback.
13. **Writes:** conservatively excluded.
14. **Cell-object iteration:** conservatively excluded.
15. **Escaped objects:** conservatively excluded or unresolved/fail-closed.
16. **Stale reads:** 0.
17. **Identity corruption:** 0.
18. **FM:07_01:** yes, a genuine A1 contact opportunity.
19. **Six-task ceiling:** A0 2/6; A1 3/6.
20. **Debugging:** unchanged at zero contact opportunity under A1.
21. **Historical eligibility:** 72/309 → 86/309 fully eligible source executions.
22. **Additional primitive reads:** estimated +28.
23. **Additional repeated opens:** exact same-generation gain not reconstructable; open-call upper bound +0.
24. **Materiality:** yes as an eligibility/contact correction: it creates a third independent live task opportunity and a measurable historical opportunity; read-time benefit remains untested.
25. **Semantic surface:** unchanged.
26. **Eligibility surface:** expanded only by removing false-negative classification.
27. **A1 earned:** True.
28. **12-task checkpoint:** True justified, but not run in this task.

## Evidence ledger

| item | status |
|---|---|
| A0_CLASSIFIER | `EARNED` |
| A1_AST_ELIGIBILITY | `SUPPORTED_NARROWLY` |
| A1_FALSE_POSITIVE_REPAIR | `EARNED` |
| A1_SEMANTIC_EQUIVALENCE | `EARNED` |
| A1_BOUNDARY_PRESERVATION | `EARNED` |
| A1_FRESHNESS_SAFETY | `EARNED` |
| A1_CONTACT_GAIN | `EARNED` |
| A1_HISTORICAL_GENERALISATION | `SUPPORTED_NARROWLY` |
| CANDIDATE_A_SEMANTIC_SURFACE | `SUPPORTED_NARROWLY` |
| CANDIDATE_A_ELIGIBILITY_SURFACE | `EARNED` |
| LARGER_LIVE_CHECKPOINT_JUSTIFICATION | `EARNED` |
| CANDIDATE_B_REOPENING | `CLOSED` |

## Final synthesis

### WHAT A0 WAS GETTING WRONG
It treated any bracketed colon pattern as a workbook range/slice, so output labels and Python list/sequence slices forced real openpyxl even when all workbook access was inside the frozen primitive formula-mode surface.

### THE A1 AST CONTRACT
Use AST node types and conservative symbol provenance. Admit only proven primitive formula-mode access; preserve fallback for real ranges, dynamic subscripts, Cell objects, modes, writes, rich objects, and escapes.

### KNOWN FALSE-POSITIVE REPAIR
20/34 known turns repaired; 14 hit legitimate remaining blockers; 0 were true range shapes.

### NEWLY ADMITTED EXECUTIONS
20; 20 semantic-exact.

### SEMANTIC DIFFERENTIAL RESULT
Exact values, Python-visible types, ordering/shapes, stdout/stderr, exit status, and exception behavior for the newly admitted replay.

### BOUNDARY REGRESSION RESULT
Passed: negative controls stayed predeclared fallback; no semantic surface expansion.

### FORMULA / DATA_ONLY RESULT
Formula-mode primitive behavior remained exact; data_only remained real-openpyxl fallback.

### FRESHNESS / GENERATION RESULT
No stale or wrong-generation reads; all accelerated loads matched the copied input snapshot and substrate generation.

### LIVE SIX-TASK CONTACT CEILING
A0 2/6 → A1 3/6; FM:07_01 is newly admitted; Debugging remains unchanged; FM:06_01 is censored.

### HISTORICAL CONTACT CEILING
A0 72 → A1 86 fully eligible source executions; additional read-event opportunity is estimated, not a speed claim.

### CROSS-FAMILY CONTACT EFFECT
FM gains the demonstrated contact; Debugging does not. Template/Visualization historical classification is reported, but live cross-family benefit remains untested.

### HOW MUCH USEFUL WORK A1 RECOVERS
It recovers +28 estimated historical read-event opportunity and a +0 open-call upper bound, plus the FM:07_01 live opportunity. Exact read-time savings remain untested.

### WHETHER THE SEMANTIC SURFACE CHANGED
No.

### WHETHER ONLY ELIGIBILITY CHANGED
Yes. A1 is an eligibility-classifier correction; AST does not lower or rewrite execution.

### WHETHER A1 IS EARNED
Yes: `A1_CLASSIFIER_REPAIR_EARNED`.

### WHETHER THE 12-TASK LIVE CHECKPOINT IS NOW JUSTIFIED
Yes, conditionally by this gate; it is the next experiment and was not run here.

### SINGLE NEXT EXPERIMENT
Run the larger identical-interface Candidate-A checkpoint with A1 frozen, direct per-load/read timing, and exact trace replay. Keep Candidate B frozen.

