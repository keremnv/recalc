# Fact-normalized read replay report

This was a zero-model adjudication of the frozen six-task archive. It did not run model inference, change prompts, add helpers, or change the semantic boundary. The live V1/V2 discriminator was not run.

Verdict: `FACT_NORMALIZED_READ_EFFICIENCY_NOT_GENERAL`.

The experiment separates two claims:

1. Compact positional encoding is smaller than verbose structured encoding of the same facts.
2. The compiled path can generally reproduce exactly what the historical model saw from information available at the time, and therefore save bytes against the actual historical observation.

The first is supported narrowly. The second does not clear the gate.

## Frozen population and H reconstruction

The exact six-task population from the prior replay was reused:

| Task | Eligible H observations | Direct/mechanical | Hindsight | Ambiguous |
|---|---:|---:|---:|---:|
| Financial_Model:08_01 | 17 | 12 | 5 | 0 |
| Debugging:10_04 | 6 | 2 | 4 | 0 |
| Financial_Model:08_03 | 10 | 4 | 6 | 0 |
| Financial_Model:07_01 | 8 | 3 | 4 | 1 |
| Debugging:10_10 | 19 | 7 | 12 | 0 |
| Financial_Model:15_04 | 3 | 0 | 3 | 0 |
| **Total** | **63** | **28** | **34** | **1** |

There were 169 archived factual/tool observations. Sixty-three had reconstructable visible cell facts. The remaining 106 were retained as `UNRESOLVED` or `METADATA_ONLY` and excluded from the primary fact-normalized metric.

Eligible historical classes were 24 `CAPPED_VISIBLE`, 21 `RANGE_TABLE`, 16 `VALUE_ONLY`, and 2 `FULL_VISIBLE`. Capped output contributed only its visible head/prefix or tail. Hidden cells never entered H.

The complete population and anti-hindsight rules are in [spec.json](../history/fact_normalized_read_replay/spec.json). The reconstructed visible sets are in [visible_fact_sets.jsonl](../history/fact_normalized_read_replay/visible_fact_sets.jsonl), and the pre-observation query audit is in [query_realizability.jsonl](../history/fact_normalized_read_replay/query_realizability.jsonl).

The H parser uses the archived observation text itself. In particular, formulas printed as `repr(c.value)[:N]`, standalone tuples, and row-prefixed tuple lists remain visibly truncated or value-only; they are not replaced by full source-workbook formulas.

## Fact-set equality and no-hindsight realizability

All 63 eligible H sets were reconstructed from content visible in the archived observations. The visible addresses define the historical H archive; they are not used as counterfactual query filters.

| Primary result | Count |
|---|---:|
| `EXACT_VISIBLE_FACT_MATCH` | 15 |
| `NORMALIZED_VISIBLE_FACT_MATCH` | 0 |
| `MISSING_VISIBLE_FACTS` | 8 |
| `WRONG_VISIBLE_FACTS` | 5 |
| `NOT_QUERY_REALIZABLE` | 35 |

The 15 exact matches were all directly or mechanically realizable. At the task level, three of six tasks reached at least 95% fact match on candidate-comparable facts: `Financial_Model:08_01` 98.16%, `Financial_Model:07_01` 99.89%, and `Financial_Model:15_04` 100.00%. `Debugging:10_04` was 76.41%, `Financial_Model:08_03` 36.18%, and `Debugging:10_10` 84.81%.

The 5 primary mismatch rows contained 430 mismatched visible facts in total. These are primarily the expected consequences of comparing full compiled formulas/values with historical value-only or visibly truncated prints; they are still fidelity mismatches and therefore fail the strict gate. There were no stale responses and no silent helper truncations.

The raw candidate comparison, including hindsight-ineligible queries, was 29 exact, 11 missing, and 8 wrong across 48 attempted candidates. Those hindsight-ineligible results are retained diagnostically but are not efficiency evidence.

No-hindsight realizability was 28/63 eligible observations overall: 11 direct and 17 mechanically projected. Per-task realizability rates were 70.59%, 33.33%, 40.00%, 37.50%, 36.84%, and 0%. No task cleared the required 75% threshold.

The excluded events were not rejected because of stale data. Historical scans frequently exposed a subset that was not mechanically specified by the pre-observation request, or printed a truncated/value-only representation that a compiled factual query cannot know in advance. Offline recovery of such a subset would be hindsight.

## Three-way representation sizes

For every matched realizable H, the replay compared:

- A: actual historical visible observation bytes;
- B: verbose structured per-cell dictionaries for exactly H;
- C: compact positional rows for exactly H.

### Compact encoding versus normalized H

Only three tasks had matched realizable observations:

| Task | Matched observations | Median reduction vs normalized H | Range |
|---|---:|---:|---:|
| Financial_Model:08_01 | 9 | 57.82% | 21.85%–62.82% |
| Financial_Model:07_01 | 3 | 55.25% | 53.44%–57.31% |
| Debugging:10_10 | 3 | 58.21% | 58.19%–61.81% |
| Debugging:10_04 | 0 | not measurable | — |
| Financial_Model:08_03 | 0 | not measurable | — |
| Financial_Model:15_04 | 0 | not measurable | — |

The event-level median was 57.82%; the median of the three task medians was 57.82%. Compact encoding therefore still clears 25% against a normalized representation of the same H, but that is a representation result, not an end-to-end result.

The direct verbose-structured-to-compact reduction was smaller: 30.85% event-level median, with task medians of 30.85%, 28.69%, and 34.18%. The prior 49.6% witness was a valid mechanical witness but exceptional relative to this exact-H verbose baseline and not representative of actual historical raw payloads.

### Compact encoding versus actual historical observations

Against the bytes actually visible to the historical model:

| Task | Matched observations | Median reduction vs actual historical raw observation | Range |
|---|---:|---:|---:|
| Financial_Model:08_01 | 9 | **−59.24%** | −79.54%–17.40% |
| Financial_Model:07_01 | 3 | **−108.98%** | −112.12%–−87.20% |
| Debugging:10_10 | 3 | **−66.44%** | −75.69%–−29.87% |
| Debugging:10_04 | 0 | not measurable | — |
| Financial_Model:08_03 | 0 | not measurable | — |
| Financial_Model:15_04 | 0 | not measurable | — |

The raw payload gate therefore passed 0/6 tasks. This is not a contradiction with normalized compactness: historical Python/value-only output often omitted the addresses, field labels, and full formula text needed to define canonical H. Compact structured output can be much smaller than verbose structured H while still being larger than a terse historical print.

Across the 15 matched realizable observations, historical raw bytes were 66,366, normalized H bytes were 244,282, and compact exact-H bytes were 103,370. The raw-minus-normalized difference was −177,916 bytes. There was no positive tool-formatting-overhead saving: raw historical output was already smaller than the canonical factual representation.

## Projection and over-fetch

Projection did not eliminate over-fetch universally. Across matched realizable rows:

- 150 extra compiled facts were returned, concentrated in `Financial_Model:08_01`.
- The positive compiled-full-minus-projected byte upper-bound total was 8,794 bytes; signed wrapper/framing differences made the total full-minus-projected value −2,458 bytes.
- Direct explicit ranges were generally clean; mechanically filtered ranges could still expose a larger range than H.
- Missing and wrong fact rows were not silent freshness truncations: helper responses reported no truncation, and the mismatch arose from query/representation mismatch.

## Batching and true interaction cycles

The replay found 169 actual historical model/tool cycles: one tool execution followed by one model-visible observation. They comprised 158 Python executions and 11 `view_xlsx` executions. The archive contained 116 explicit/internal range slices.

The prior replay’s “historical operations” metric counted range-level slices in its counterfactual operation comparison. In particular, the 53→24 and 22→13 headline reductions were range-level counts, not model/tool-cycle counts. One sequence (`Financial_Model:08_01`) contained 53 internal ranges inside 26 tool executions. Thus all 116 range slices must not be interpreted as 116 extra interaction cycles.

The corrected cycle ceiling is:

| Quantity | Result |
|---|---:|
| Actual historical model/tool cycles | 169 |
| Minimum compiled calls at one call per historical execution | 169 |
| Cycles saved by consolidating ranges inside an existing execution | 0 |
| Exact repeated-query reuse opportunities | 20 |

The 20 repeated-query rows are a deterministic reuse ceiling, not observed savings. The current read surface does not automatically make the model skip those later turns. The replay exercised 48 helper calls: 41 `inspect` and 7 `inspect_ranges`.

## Mechanical gate

| Gate component | Result | Required |
|---|---:|---:|
| Tasks with >=95% comparable fact preservation | 3/6 | >=4/6 |
| Tasks with >=75% eligible observations directly/mechanically realizable | 0/6 | >=4/6 |
| Tasks with >=25% median reduction vs actual historical visible bytes | 0/6 | >=4/6 |
| Stale responses | 0 | 0 |
| Silent helper truncations | 0 | 0 |
| Primary wrong-fact rows | 5 | 0 systematic fidelity failure |

The gate fails `FACT_PRESERVATION`, `QUERY_REALIZABILITY`, `PAYLOAD_MATERIALITY`, and the strict fidelity component. Phase B was not justified and no model inference was run. The machine-readable result is in [gate.json](../history/fact_normalized_read_replay/gate.json).

## Required adjudication answers

1. **Eligible observations:** 63 of 169 archived inspection observations.
2. **Reconstructed exact visible fact sets:** 63/63 eligible H sets were reconstructed from observation text.
3. **Compiled exact/safely normalized reproduction:** 15 exact primary matches, 0 normalized-only matches; three tasks cleared 95% comparable fact fidelity.
4. **Hindsight filtering:** 34 eligible observations required hindsight; one was ambiguous.
5. **Direct/mechanical query realizability:** 28/63 eligible observations: 11 direct and 17 mechanically projected.
6. **>=25% normalized compactness:** yes, on all three tasks with matched data; task-median median 57.82% versus normalized H.
7. **Per-task payload reduction versus actual historical observations:** −59.24%, not measurable, not measurable, −108.98%, −66.44%, and not measurable in frozen task order.
8. **Reduction versus normalized factual representations:** 57.82%, not measurable, not measurable, 55.25%, 58.21%, and not measurable.
9. **Tool-formatting overhead:** not a positive saving source; matched raw-minus-normalized bytes were −177,916 pooled.
10. **Residual over-fetch:** yes, 150 extra facts and an 8,794-byte positive upper-bound total in matched rows.
11. **Actual model/tool cycles:** 169, not 116 ranges.
12. **Mechanically consolidatable cycles:** zero within-execution cycle savings; 20 exact repeated-query reuse opportunities as a ceiling.
13. **Previous range/cycle error:** internal range slices were treated as operation-level units; the prior headline reductions in two tasks were not model-turn reductions.
14. **Payload-saving ceiling:** versus actual historical raw observations, −37,004 bytes avoided pooled (−55.76% pooled; −66.44% median of task medians). Versus normalized H, 57.68% pooled reduction and 57.82% median of task medians.
15. **Round-trip ceiling:** 169 historical cycles to 169 one-call-per-execution compiled cycles; 0 proven cycle savings, with 20 deterministic repeat-reuse opportunities.
16. **Current limiting component:** query realizability and projection/selectivity, plus historical representation fidelity; not compact encoding.
17. **Repaired gate:** fails fact preservation, query realizability, raw payload materiality, and strict fidelity.
18. **Old broad “no efficiency gain” conclusion:** still unresolved, not falsified and not supported as a universal null. The new result rejects using the prior raw aggregate as evidence against compactness, but does not establish live savings.
19. **Live V1/V2 discriminator:** not justified; `LIVE_V1_V2_JUSTIFIED = false`.
20. **Evidence ledger:** corrected below and in [corrected_evidence_ledger.json](../history/fact_normalized_read_replay/corrected_evidence_ledger.json).

## Corrected evidence ledger

| Claim | Status |
|---|---|
| CAPABILITY PRESERVATION | `SUPPORTED` |
| TRANSPARENT RUNTIME | `SUPPORTED` |
| V1 READ-SIDE MECHANISM | `EARNED` |
| V1 END-TO-END EFFICIENCY | `CONFOUNDED` |
| COMPACT ENCODING | `SUPPORTED_NARROWLY` |
| FACT-NORMALIZED PROJECTION | `NOT_ESTABLISHED` |
| QUERY REALIZABILITY | `NOT_ESTABLISHED` |
| ROUND-TRIP CONSOLIDATION | `SUPPORTED_NARROWLY` |
| V2 BEHAVIORAL SUBSTITUTION | `UNTESTED` |
| V2 END-TO-END EFFICIENCY | `UNTESTED` |
| FULL-BENCHMARK JUSTIFICATION | `NOT_ESTABLISHED` |

The full evidence package is in [fact_normalized_read_replay/](../history/fact_normalized_read_replay): population, historical observations, visible H sets, query inputs, realizability, fact equivalence, representation sizes, task results, cycle analysis, consolidation opportunities, ceilings, gate, ledger, freshness log, and next-experiment decision.

## Final synthesis

### WHAT THE PREVIOUS REPLAY GOT RIGHT

It correctly showed capability preservation, transparent runtime integrity, and that the v1 aggregate efficiency result was confounded. It also correctly exposed verbose/capped observations and the need for a compact/batched read mechanism.

### WHAT IT COMPARED INCORRECTLY

It compared historical visible subsets with larger mechanically authorized v2 supersets, and its operation metric counted internal range slices rather than model/tool cycles. Those comparisons cannot establish model-visible byte savings or model-turn savings.

### FACT-SET NORMALIZED RESULT

Sixty-three eligible H sets were reconstructed from observation text. Fifteen admissible compiled candidates matched exactly; 8 were missing, 5 had visible-fact mismatches, and 35 had no admissible query.

### QUERY-REALIZABILITY RESULT

Only 28/63 eligible observations were directly or mechanically query-realizable. Thirty-four required hindsight and one was ambiguous. The 75% per-task gate was cleared by 0/6 tasks.

### COMPACTNESS RESULT

Compact positional encoding reduced the same normalized H by a 57.82% median across task medians and reduced exact-H verbose structured encoding by a 30.85% event-level median. The 49.6% witness was not representative of actual historical raw payloads.

### PROJECTION / OVERFETCH RESULT

Projection helped but did not universally remove over-fetch: matched rows still included 150 extra facts and 8,794 positive-upper-bound bytes. Observation-faithful parsing also exposed 5 visible-fact mismatch rows.

### TRUE MODEL-TOOL CYCLE OPPORTUNITY

The archive contains 169 actual model/tool cycles and 116 internal range slices. Batching ranges within an existing execution saves no model/tool cycle. There are 20 exact repeated-query reuse opportunities as a ceiling only.

### PAYLOAD-SAVING CEILING

Against actual historical observations, the ceiling was negative: −55.76% pooled across matched rows and −66.44% median of task medians. Against normalized factual H, it was 57.68% pooled and 57.82% by task-median median.

### ROUND-TRIP-SAVING CEILING

No cycle reduction was demonstrated. The mechanical ceiling is 20 repeat-query reuse opportunities, not an observed or automatically realized saving.

### CORRECTED EVIDENCE LEDGER

`SUPPORTED` capability and transparent runtime; `EARNED` v1 read mechanism; `CONFOUNDED` v1 end-to-end efficiency; `SUPPORTED_NARROWLY` compact encoding and round-trip consolidation; `NOT_ESTABLISHED` fact-normalized projection, query realizability, and full-benchmark justification; `UNTESTED` v2 behavioral substitution and v2 end-to-end efficiency.

### WHETHER THE LIVE V1/V2 TEST IS NOW JUSTIFIED

No. The repaired gate fails fact preservation, query realizability, and actual-historical payload materiality. The live discriminator remains a possible future test only after the query-realizability bottleneck is resolved without changing the semantic boundary; no new helper is justified by this replay.

### SINGLE NEXT EXPERIMENT

None in this task. Do not run live V1/V2 yet. If the branch is reopened, run only the already frozen identical-documentation V1/V2 discriminator after a new pre-specified query-realizability audit clears this gate.
