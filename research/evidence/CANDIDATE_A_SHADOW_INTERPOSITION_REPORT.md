# Candidate A Shadow Interposition Report

This was a zero-model, no-prompt-change, no-helper, no-new-syntax experiment. Candidate B was not implemented and no production proxy was installed.

Decision: **BUILD_A_LIVE_TREATMENT**.

## Required answers

1. The previous 2/17 mismatches were metadata-only sheet omission and under-reported worksheet dimensions. Both were `PRIMITIVE_VALUE_SEMANTICS` and bounded repairs.
2. Neither mismatch was architectural; both were repaired without broadening the surface.
3. The frozen surface is formula-mode/default `load_workbook`, XML-backed `sheetnames` and bounds, single worksheet lookup, primitive `cell`/single-coordinate reads, primitive cell value/type/coordinate/row/column, and `iter_rows(values_only=True)`. Ranges, Cell-object iterators, data_only, writes, rich objects, and package access fall back.
4. The corpus contains 309 recoverable Python executions and 258 read executions. The frozen census identified 72 fully Candidate-A-proxyable executions across 18 tasks; this strict whole-script replay had 3 eligible held-out executions, with unsupported scripts predeclared fallback.
5. The object census classified 56/301 source-level read-object cases as immediate/local non-escape; 245/301 were escaped, passed onward, or unresolved. Escaped proxy objects force real openpyxl from the start.
6. The hardest semantics are metadata-only sheets, formatted/sparse dimensions, Python scalar types, formulas/cached values, merged-cell identity, and rich-object escape.
7. Primitive differential fidelity: 58/58 exact (100.0%).
8. Formula/data_only fidelity: 8/8 exact (100.0%). The 4 default formula-mode cases used the proxy; the 4 `data_only=True` cases used deliberate real-openpyxl fallback. No compiled cached-value acceleration is claimed.
9. Formula-mode scalar types in the implemented replay are compared as Python-visible types; date/time decoding is explicit. Cached values are not served by the compiled path.
10. Values-only iteration is row-major tuple output and is compared exactly. Cell-object and range shapes fall back.
11. Missing-sheet and invalid-coordinate exception classes are compared; unsupported operations do not silently rewrite.
12. Unsupported behavior before object escape uses local real-openpyxl fallback and is recorded in `fallback_cases.jsonl`.
13. Fallback after object escape is not identity-safe; F3 therefore uses `PREDECLARED_REAL_OPENPYXL_PATH`.
14. The fallback policy is local fallback before escape, predeclared real path for data_only/writes/rich/range/escape, and fail-closed otherwise.
15. Targeted read/write cases: 2/2 exact under predeclared real fallback.
16. Stale reads: 0 in targeted replay. Proxy writes are not attempted.
17. Save/reopen cases: 2/2 exact under real fallback.
18. LibreOffice boundary: [{"status": "TESTED", "classification": "SEMANTIC_EXACT", "reason": null, "real_data_only": {"type": "float", "value": 14.5}, "shadow_data_only": {"type": "float", "value": 14.5}, "policy": "PREDECLARED_REAL_OPENPYXL_PATH", "stale": false, "soffice_returncode": 0}].
19. Held-out semantic fidelity: 3/3 eligible executions (100.0%); 105 other held-out executions were conservatively predeclared fallback.
20. Held-out accelerated coverage: {"eligible_scripts": 3, "fully_accelerated": 1, "partially_accelerated_safely": 2, "predeclared_fallback": 105, "semantic_mismatch": 0}; fallback is not counted as acceleration.
21. Cross-family results: Financial_Model had 3 eligible/3 exact; Template, Debugging, and Visualization had no eligible accelerated whole-script cases in this strict replay and therefore fell back. This supports safety, not broad cross-family acceleration generalisation.
22. One bounded repair round occurred: worksheet metadata only.
23. >=99% reliability gate: `True`.
24. >=99.9% target: `True`.
25. There were no remaining differential mismatches; the only repaired issues were bounded metadata/type/dimension details. No architectural identity or fallback failure was observed.
26. First-access performance: P1 (build included) was 4.694s vs 0.041s on the large FM workbook and 0.0125s vs 0.0039s on Template; P2 (shared substrate) was 0.0085s vs 0.041s and 0.0016s vs 0.0039s respectively. These are medians of two local repetitions for a 200-cell sequence.
27. Repeated-access performance: P1 never broke even through 10 accesses on FM and broke even at 3 on Template; P2 was faster from access 1 on both, reaching about 80% lower cumulative walltime on FM and 55% lower on Template at 10 accesses.
28. Break-even: P1 Template at 3 accesses; P1 FM not observed by 10; P2 at 1 access on both. Full points are in `amortization.json`.
29. P1/P2 economics were measured separately. Process startup and model/network time were excluded; the local timing decomposes build and access for Candidate A versus repeated openpyxl load/read time.
30. A advances to live treatment: `True`.
31. B reopens: `False`.
32. The architecture may advance only as a narrow live treatment: semantic invisibility and shared-substrate repeated-access benefit passed, but broad fallback-dominant coverage and data-only/writes remain outside the claim.

## Evidence ledger

| Claim | Status |
|---|---|
| PYTHON_AS_AGENT_QUERY_LANGUAGE | EARNED |
| TRANSPARENT_READ_ACCELERATION | SUPPORTED_NARROWLY |
| CANDIDATE_A_PRIMITIVE_FIDELITY | SUPPORTED_NARROWLY |
| CANDIDATE_A_FORMULA_DATA_ONLY_FIDELITY | SUPPORTED_NARROWLY |
| CANDIDATE_A_FALLBACK_SAFETY | SUPPORTED_NARROWLY |
| CANDIDATE_A_READ_WRITE_SAFETY | SUPPORTED_NARROWLY |
| CANDIDATE_A_HELDOUT_GENERALISATION | SUPPORTED_NARROWLY |
| CANDIDATE_A_PERFORMANCE_MATERIALITY | SUPPORTED_NARROWLY |
| CANDIDATE_B_REOPENING | CLOSED |
| LIVE_A_B_JUSTIFICATION | UNTESTED |

## Final synthesis

WHAT THE 15/17 FAILURES ACTUALLY WERE

They were bounded compiled-metadata defects: metadata-only worksheet names were omitted and worksheet dimensions were inferred from non-empty indexed cells.

THE FROZEN PRIMITIVE SURFACE

Formula-mode/default workbook loading, XML-backed sheetnames and bounds, single-sheet lookup, primitive cell reads, and values-only row iteration. Unsupported rich behavior, data_only, mutation, ranges, and escaped objects use real openpyxl.

PRIMITIVE SEMANTIC FIDELITY

58/58 exact after one bounded metadata repair.

FORMULA / DATA_ONLY FIDELITY

8/8 exact: 4/4 default formula-mode proxy cases and 4/4 `data_only` real-openpyxl fallback cases. Data-only correctness is not compiled cached-value acceleration.

OBJECT ESCAPE

Proxy object identity is not preserved after escape. Static escape therefore forces real openpyxl from the start.

FALLBACK SAFETY

Narrow local fallback is exact before escape. Post-escape fallback is not silently mixed; it is predeclared real or fail-closed.

READ-WRITE / GENERATION SAFETY

Targeted read/write and save/reopen cases use real fallback and produced no stale read. Transparent proxy mutation remains out of scope.

HELD-OUT GENERALISATION

3/3 eligible held-out executions were exact; 105 unsupported held-out executions were separated as fallback. Eligible coverage was confined to Financial_Model in this strict replay, so cross-family acceleration remains narrow.

CROSS-FAMILY RESULT

Family-specific results are in `family_results.json`; no sheet-name, row-label, or task-specific rule was used.

WHETHER A REQUIRED REPAIR

Yes, one bounded metadata repair round was used. No API expansion was made.

FINAL RELIABILITY GATE

>=99%: `True`. >=99.9%: `True`. Performance is allowed.

MEASURED REPEATED-ACCESS PERFORMANCE

Measured in `performance_runs.jsonl`: P1 build-included and P2 shared-substrate scenarios are separate. P1 had no FM break-even through 10 accesses and Template broke even at 3; P2 broke even at 1 on both workbooks.

AMORTIZATION RESULT

The shared-runtime scenario is materially positive on both representative workbooks; the incremental-build scenario is positive only after repeated access and only on the smaller Template workbook.

WHAT CANDIDATE A ACTUALLY BUYS US

A can accelerate a narrow class of ordinary formula-mode primitive reads while preserving arbitrary Python and routing unsupported behavior to real openpyxl. With an already-maintained compiled substrate, it materially reduces repeated deterministic read time; it does not accelerate data_only, writes, rich objects, range Cell objects, or escaped proxies.

WHETHER CANDIDATE B SHOULD BE REOPENED

No. A has not demonstrated an unavoidable proxy/interposition failure; its remaining boundary is conservative fallback.

WHETHER A LIVE TREATMENT IS JUSTIFIED

Yes, narrowly: **BUILD_A_LIVE_TREATMENT**. This authorizes a future identical-interface real-vs-shadow treatment only; it does not establish model-level or benchmark-level benefit.

SINGLE NEXT EXPERIMENT

Run one future identical-interface live treatment with Candidate A enabled underneath ordinary Python, keeping prompts, helpers, syntax, and semantic boundary unchanged. Compare capability first, then actual repeated workbook mechanical time; keep Candidate B frozen.
