# Transparent Python Read Acceleration Census

## Scope and decision

This was a zero-model, no-prompt-change, no-helper experiment over the frozen `control_python_audit` corpus. It did not modify the agent interface or production runtime. The current decision is **NEED_ONE_MORE_MECHANICAL_DISCRIMINATOR**. This is a feasibility decision for a throwaway shadow path, not permission to run a live model A/B.

The corpus contains 71 trajectories (70 task IDs), 1210 archived executions, and 309 readable Python bodies. The primary control population is P-B_sixty_control plus P-A_matched_c0; Visualization is retained as a separate family. The task-level held-out split is deterministic (seed 20260920) and is recorded in `heldout_split.json`.

Units are kept separate: 1210 archived action executions, 1210 unique archived trajectory-turn/model-tool records, 309 readable Python executions, and 258 source executions containing workbook reads. A loop with many cell accesses remains one Python execution and one trajectory turn, not many model/tool cycles.

## Answers to the required questions

1. **Actual read APIs.** The static census found 3917 workbook-read API events in 258 source executions. The most frequent categories are [["workbook.__getitem__", 872], ["worksheet.__getitem__", 845], ["cell.value", 592], ["worksheet.cell", 566], ["other.workbook_api", 465], ["workbook.load_workbook", 298], ["worksheet.iter_rows", 48], ["cell.number_format", 40], ["cell.coordinate", 29], ["worksheet.max_column", 25], ["worksheet.max_row", 25], ["workbook.sheetnames", 24]].
2. **Frequency leaders.** Frequency is dominated by `cell.value`/cell access, row/column loops, workbook open, sheet enumeration, dimensions, and explicit/range iteration. The exact event table is `api_events.jsonl`.
3. **Deterministic walltime leaders.** Local replay measures open-plus-full-scan; historical scripts also show 298 source `load_workbook` calls and 150 loop-heavy inspection executions. The timing sample is in `walltime_measurements.jsonl`.
4. **Repeated opens.** The conservative same-trajectory/same-basename census finds 234 repeated open calls in 61 repeat groups out of 298 source open calls. It does not equate differently named files.
5. **Repeated parsing.** The measured ceiling is 9.1471 seconds on the selected local sample under that conservative repeat fraction; this excludes model/network time.
6. **Arbitrary Python around reads.** 41 source executions are complex read-only Python and 125 mix reads and writes; this is why “API fact coverage” is not the same as whole-script safe replacement.
7. **Current substrate exact answerability.** Counts by answerability are {"UNRESOLVED": 767, "EXACTLY_ANSWERABLE_NOW": 2453, "ANSWERABLE_WITH_SMALL_MECHANICAL_EXTENSION": 293, "ANSWERABLE_BUT_SEMANTICS_RISKY": 312, "REQUIRES_REAL_OPENPYXL": 92}. Primitive structure is available; exact openpyxl scalar/data_only/rich-object semantics are not all preserved by the current index.
8. **Small extensions.** `cell.value`, dtype decoding, cached data-only values, and compatible iterator/object wrappers are small mechanically bounded extensions, but they are not free semantic equivalence.
9. **Fundamental real-openpyxl/package cases.** Style/rich objects and raw zip/XML behavior remain `REQUIRES_REAL_OPENPYXL` or `OPAQUE_PACKAGE_ONLY`; counts are in `substrate_answerability.jsonl`.
10. **A 50/75/90% surface.** The A thresholds are [{"add_api": "worksheet.__getitem__", "execution_coverage_pct": 99.22, "read_event_coverage_pct": 66.56, "surface": ["workbook.load_workbook", "workbook.__getitem__", "cell.value", "worksheet.__getitem__"], "surface_size": 4, "target_event_coverage_pct": 50}, {"add_api": "worksheet.cell", "execution_coverage_pct": 100.0, "read_event_coverage_pct": 81.01, "surface": ["workbook.load_workbook", "workbook.__getitem__", "cell.value", "worksheet.__getitem__", "worksheet.cell"], "surface_size": 5, "target_event_coverage_pct": 75}, {"add_api": "other.workbook_api", "execution_coverage_pct": 100.0, "read_event_coverage_pct": 92.88, "surface": ["workbook.load_workbook", "workbook.__getitem__", "cell.value", "worksheet.__getitem__", "worksheet.cell", "other.workbook_api"], "surface_size": 6, "target_event_coverage_pct": 90}]; the smallest API categories are selected by observed event coverage, while full proxyability is reported separately to avoid hiding fallback.
11. **A fallback.** A has 181 proxyable-with-fallback executions and 5 fallback-dominant executions. Safe object-preserving lazy fallback is **not proven**.
12. **A fallback semantic preservation.** Not established: escaped proxy objects, mixed reads/writes, exceptions, and data_only/formula mode can make per-object swapping observably different.
13. **B lowerability.** B recognizes 3257 conservative read events; execution classes are {"B_PARTIALLY_LOWERABLE": 13, "B_FULLY_LOWERABLE": 46, "B_RECOGNIZABLE_BUT_RISKY": 76, "B_MIXED_READ_WRITE_UNSAFE": 123}.
14. **B failure modes.** The leading blockers are dynamic/indirect aliases, functions/closures, comprehensions/generators, object escape, mixed read/write ordering, and proof of Python scalar/iterator/exception semantics.
15. **Held-out performance.** Development is {"A_any_proxy_reads_pct": 100.0, "A_fully_proxyable_pct": 31.33, "B_any_lowerable_reads_pct": 100.0, "B_fully_lowerable_pct": 20.0, "inspection_source_execs": 150, "read_events": 2280} and held-out is {"A_any_proxy_reads_pct": 100.0, "A_fully_proxyable_pct": 23.15, "B_any_lowerable_reads_pct": 100.0, "B_fully_lowerable_pct": 14.81, "inspection_source_execs": 108, "read_events": 1637}; no candidate surface was changed after the split. Family results are in `family_coverage.json`.
16. **Cross-family.** The family table keeps Financial_Model, Template, Debugging, and Visualization separate: {"Debugging": {"A_any_proxy_reads": 77, "A_fully_proxyable": 16, "B_any_lowerable_reads": 77, "B_fully_lowerable": 12, "inspection_source_execs": 77, "read_events": 789}, "Financial_Model": {"A_any_proxy_reads": 123, "A_fully_proxyable": 48, "B_any_lowerable_reads": 123, "B_fully_lowerable": 28, "inspection_source_execs": 123, "read_events": 2082}, "Template": {"A_any_proxy_reads": 52, "A_fully_proxyable": 5, "B_any_lowerable_reads": 52, "B_fully_lowerable": 5, "inspection_source_execs": 52, "read_events": 938}, "Visualization": {"A_any_proxy_reads": 6, "A_fully_proxyable": 3, "B_any_lowerable_reads": 6, "B_fully_lowerable": 1, "inspection_source_execs": 6, "read_events": 108}}. Coverage is not credited as benchmark-general merely because Financial_Model is large.
17. **Workbook-specific dependence.** No candidate rule uses sheet names, row labels, or benchmark schemas. Literal workbook paths are only used to resolve local timing/replay inputs.
18. **Read/write mixing.** 129 executions contain writes, including 125 mixed executions and 4 write-dominant executions; stress evidence includes 9 save/reload chains and 5 scripts with try blocks around writes.
19. **Mutation integration.** A proxy is easier to place around ordinary reads but harder to preserve identity when writes escape; B can rewrite reads only if mutation invalidation is proven at every write path. Neither has a proven silent-safe path.
20. **Stale state.** Both need generation/path/mode keys and fail-closed invalidation. A temporary-file mutation probe for the existing index is recorded in `generation_analysis.json`; it does not prove transparent proxy/B integration, which remains a design obligation.
21. **Hardest semantics.** `data_only` cached values, formulas versus values, dates/numbers/bools/errors, blank materialization, iterator ordering, exceptions, rich cell objects, and object identity.
22. **Differential fidelity.** The throwaway shadow replay produced 15/17 semantic-exact cases; all results and any mismatches are in `shadow_replay_results.jsonl`. This is a narrow substrate shadow, not a full proxy.
23. **A walltime ceiling.** On the local timing sample, A's event-weighted open+scan ceiling is 9.9597 seconds; this is a ceiling, not a live saving.
24. **B walltime ceiling.** The corresponding conservative B ceiling is 9.6861 seconds.
25. **Build/update cost.** Median index build is 2.7615 seconds for the 5 timed workbooks with at least 100k iterated cells (all-sample median 0.0055s); update/freshness cost is a rebuild on hash mismatch in the current substrate.
26. **Amortization.** The crude measured break-even is about 1.65 repeated full open+scan equivalents, before accounting for memory and incremental updates. Shared existing substrate cost must not be charged twice.
27. **Proxy viability.** Viable enough for a shadow accelerator if the target is narrow primitive reads and fallback is treated as correctness-critical; not yet viable as transparent production interposition.
28. **AST lowering viability.** Viable only as a narrow, opt-in shadow for explicit read-only shapes; corpus dynamics and mixed writes prevent a broad transparent lowering claim.
29. **Hybrid justification.** No measurable complementary prize was demonstrated that warrants combining two unproven boundaries. C is not selected as a compromise.
30. **Live A/B.** Not justified. This is a zero-model census and does not establish safe proxy fallback, broad semantic replay, or production economics.

## Evidence-ledger update

| Claim | Status |
|---|---|
| PYTHON_AS_AGENT_QUERY_LANGUAGE | EARNED |
| TRANSPARENT READ ACCELERATION HYPOTHESIS | NOT_ESTABLISHED |
| CANDIDATE A — PROXY/INTERPOSITION | SUPPORTED_NARROWLY |
| CANDIDATE B — AST/SOURCE LOWERING | SUPPORTED_NARROWLY |
| CANDIDATE C — HYBRID | NOT_ESTABLISHED |
| READ-ACCELERATION EFFECTIVENESS | NOT_ESTABLISHED |
| READ-ACCELERATION RELIABILITY | NOT_ESTABLISHED |
| READ-ACCELERATION GENERALISABILITY | SUPPORTED_NARROWLY |
| READ-ACCELERATION ECONOMIC MATERIALITY | NOT_ESTABLISHED |
| LIVE A/B JUSTIFICATION | UNTESTED |

## Final synthesis

WHAT PYTHON IS ACTUALLY DOING

The agent mostly uses ordinary Python as a mechanical inspection language: open, enumerate sheets, discover dimensions, loop rows/cells, filter/format/compare results, and then mix those reads with writes or verification. The expensive work is often hidden inside one Python execution, not one model/tool cycle.

WHERE THE DETERMINISTIC COST LIVES

The measurable center is repeated workbook open/parsing plus row/cell iteration. Historical counts are 298 source opens, 150 loop-heavy executions, and 234 conservative repeated opens. No model/network time is included in the local ceiling.

THE MINIMAL OPENPYXL SURFACE THAT MATTERS

`load_workbook`, `sheetnames`, workbook sheet lookup, `max_row`/`max_column`, `cell`, explicit `__getitem__` ranges, `iter_rows`/`iter_cols`, `cell.value`, `data_type`, coordinates, and formula/data-only mode. Styles, merged cells, tables, raw XML, and rich objects are outside the minimal safe surface.

CANDIDATE A — COVERAGE AND FAILURE MODES

A covers 85.5% of observed read events on its conservative surface, but only 27.91% of inspection source executions are fully proxyable. Lazy fallback is not yet proven semantics-preserving because proxy identity can escape and writes/modes can change the observable object contract.

CANDIDATE B — COVERAGE AND FAILURE MODES

B recognizes explicit load/sheet/dimension/cell/range/iterator shapes, but whole-script lowerability falls when aliases, helper functions, comprehensions/generators, object escape, package access, or writes appear. Its event ceiling is 83.15%; it is safer to prove per transform but less general as a transparent replacement.

HELD-OUT / CROSS-FAMILY GENERALISATION

The split is task-level and frozen. Development/held-out and family-specific figures are machine-readable in `heldout_results.json` and `family_coverage.json`; no schema-specific sheet or row rule was used. This supports only narrow generalisability, not benchmark-wide coverage.

READ-WRITE / FRESHNESS SAFETY

The mutation runtime's generation boundary is compatible in principle, but A needs invalidation around every proxy-visible write and B needs invalidation around every lowered-read/write boundary. The temporary current-index mutation probe is recorded separately; transparent integration has not been differentially proven.

DIFFERENTIAL REPLAY FIDELITY

The shadow subset achieved 15/17 semantic-exact cases. This validates a narrow prototype surface only. It does not validate fallback, rich objects, cached data-only values, or mixed scripts.

MEASURED PERFORMANCE CEILING

On the selected local workbooks, the measured open+full-scan sample and coverage-weighted ceilings are A=9.9597s and B=9.6861s. These are mechanical upper bounds, not production savings.

AMORTIZATION

Median index build was 2.7615s versus 1.673s for one open+scan equivalent on the nontrivial sample (all-sample medians: 0.0055s and 0.0039s), implying roughly 1.65 repeated accesses to amortize. Existing transparent-runtime index cost is shared infrastructure; a read-only deployment would pay it incrementally.

WHAT A WOULD BUY US

A shadow could accelerate primitive reads without requiring the model to change Python syntax, and it can preserve arbitrary surrounding Python through fallback. The price is a large compatibility and identity proof burden; a silent fallback mismatch would be a correctness failure.

WHAT B WOULD BUY US

B could prove a smaller number of explicit reads without emulating all openpyxl objects, but it would miss or conservatively skip the arbitrary Python that actually expresses selection, filtering, and formatting. Its wins are narrower and source-shape dependent.

WHETHER A HYBRID IS ACTUALLY JUSTIFIED

No. The census did not show a clean, measured complementary split with an additional prize. A hybrid would combine proxy fallback risk with rewrite proof risk before either is established.

WHICH CANDIDATE SURVIVES

A survives as the next narrow shadow target; B survives only as a narrow comparison path. The decision is **NEED_ONE_MORE_MECHANICAL_DISCRIMINATOR**, with no production integration implied.

WHETHER A LIVE A/B IS JUSTIFIED

No. Neither candidate has cleared the semantic fallback/generation materiality gate, and the requested study forbids model inference. A live model A/B would be premature.

SINGLE NEXT EXPERIMENT

Build only the throwaway A shadow proxy for the minimal primitive surface, run it on held-out read-only scripts plus write-then-read and formula/data-only pairs, and require >=99% Python-semantic equivalence, zero stale/mutation mismatches, and positive measured repeated-access amortization before any live treatment is considered.
