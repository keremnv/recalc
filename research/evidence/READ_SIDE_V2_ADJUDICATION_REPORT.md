# Read-side v2 adjudication

Status: Phase A complete; Phase B gated off.

Verdict: `V2_MECHANICAL_COMPRESSION_NOT_GENERAL`.

This adjudication used zero new model calls. It replayed six frozen H0 control trajectories selected mechanically from the frozen control-only exposure ranking. The current v2 read surface reproduced the available workbook facts without stale responses, silent truncation, or systematic fact loss. It did not, however, clear the required efficiency gate.

## Scope and controls

The semantic boundary stayed fixed. The only model-facing factual primitives were `search`, `periods`, `inspect`, and `inspect_ranges`. No relevance inference, summarization, ranking, target selection, dependency recommendation, or formula recommendation was added.

The selection rule was fixed as: take the first six rows of `thin_architecture_checkpoint/exposure_ranking.json` restricted to the frozen `thin_architecture_checkpoint/population.json`. The selected tasks were:

| Task | Historical factual operations counted | Historical ranges | v2 helper operations | v2 factual result |
|---|---:|---:|---:|---|
| Financial_Model:08_01 | 24 | 53 | 24 | FACT_EQUIVALENT |
| Debugging:10_04 | 28 | 35 | 28 | FACT_EQUIVALENT |
| Financial_Model:08_03 | 1 | 1 | 1 | FACT_EQUIVALENT |
| Financial_Model:07_01 | 3 | 3 | 3 | FACT_EQUIVALENT |
| Debugging:10_10 | 11 | 22 | 13 | FACT_EQUIVALENT |
| Financial_Model:15_04 | 2 | 2 | 2 | FACT_EQUIVALENT |

“Historical ranges” counts explicit mechanically reconstructed range slices. “v2 helper operations” counts one compact helper operation per reconstructed historical inspection execution. Invalid rows were metadata-only or had no reconstructable factual range and were retained in the sequence archive but excluded from payload comparisons.

Two harness/runtime defects were corrected before the final replay: single-range v2 results now retain their sheet identity, and array formulas are indexed by stable formula text rather than process-specific object representations. The final replay also used a bounded 10,000-cell mechanical output budget and logged freshness on every helper call.

## Phase A results

### Factual equivalence

All six tasks were `FACT_EQUIVALENT`. The result is deliberately not six claims of byte-for-byte historical transcript equality: capped view observations and Python print loops often exposed only a visible subset or metadata, while v2 returned the same facts plus additional mechanical cell facts from the explicit historical range. Those additions are marked `ADDITIONAL_BUT_MECHANICAL` in the per-operation artifact.

There were zero v2 stale responses, zero v2 silent truncations, and zero systematic decision-relevant fact losses in the mechanically available ranges.

### Raw historical observation versus v2 payload

| Task | Historical bytes | v2 bytes | Payload reduction | Historical ops | v2 ops | Operation reduction |
|---|---:|---:|---:|---:|---:|---:|
| Financial_Model:08_01 | 90,792 | 510,881 | -462.69% | 53 | 24 | 54.72% |
| Debugging:10_04 | 37,917 | 308,170 | -712.75% | 35 | 28 | 20.00% |
| Financial_Model:08_03 | 10,292 | 491,576 | -4,676.29% | 1 | 1 | 0.00% |
| Financial_Model:07_01 | 29,241 | 164,775 | -463.51% | 3 | 3 | 0.00% |
| Debugging:10_10 | 82,554 | 407,292 | -393.36% | 22 | 13 | 40.91% |
| Financial_Model:15_04 | 20,581 | 69,664 | -238.49% | 2 | 2 | 0.00% |

Robust summaries:

- Median raw observation-byte change: **-463.10%**; range **-4,676.29% to -238.49%**.
- Median explicit inspection-operation reduction: **10.00%**; range **0% to 54.72%**.
- Tasks clearing the 25% raw-byte threshold: **0/6**.
- Tasks clearing the 25% operation threshold: **2/6**.
- Tasks clearing either threshold: **2/6**, below the required 4/6.

The raw-byte result is not a claim that compact encoding is intrinsically verbose. It reflects the actual comparison requested: current v2 emitted structured cell facts for the explicit historical ranges, while the historical controls often printed a narrower value-only subset or were already capped. Returning more mechanically authorized facts is fidelity-preserving but not an observation-byte saving.

### Compactness versus batching

For the same v2 facts, replacing the verbose dictionary representation with the compact positional representation produced:

- Median reduction: **60.81%**.
- Per-task range: **57.18% to 63.36%**.
- All six tasks cleared 25% on this isolated verbose-to-compact comparison.

That is the narrow mechanical compression effect. It is real and stronger in this replay than the earlier 49.6% witness, so the earlier witness was not an exceptional encoding artifact. It was nevertheless not representative of raw historical control observations or end-to-end behavior.

The explicit batched representation covered multiple ranges in one helper result for three tasks. Serialized payload change versus the sum of independent v2 range results was small and negative: per-task measured batching changes were **-0.48%**, **-3.80%**, and **-0.64%**. Batching reduced the number of range-level inspection operations in two tasks, but did not materially reduce serialized bytes because the facts and per-range framing remained present.

Therefore:

- Compactness is the positive mechanism witness.
- Batching is an operation-count opportunity in some historical sequences.
- Neither combination cleared the Phase A generality gate against the actual frozen control observations.

## Required adjudication answers

1. **Was the prior 49.6% witness representative or exceptional?** It was representative of the verbose-to-compact encoding mechanism, not of raw historical observation replacement. The six-task same-facts verbose-to-compact median was 60.81%.

2. **On how many of six tasks can v2 reproduce the same decision-relevant facts?** Six of six at the mechanically available factual-range level, classified `FACT_EQUIVALENT`; additional returned facts remained mechanical and no systematic loss was observed.

3. **Per-task payload reduction?** -462.69%, -712.75%, -4,676.29%, -463.51%, -393.36%, and -238.49%, respectively, in the table above. These are increases in raw serialized payload, not savings.

4. **Per-task inspection-operation reduction?** 54.72%, 20.00%, 0%, 0%, 40.91%, and 0%, respectively.

5. **How much comes from compact encoding versus batching?** Compact encoding reduced the same-v2-fact verbose representation by 57.18–63.36% per task. Batching changed serialized bytes by -3.80% to -0.48% where measurable; its larger effect was reducing explicit range operations in two tasks.

6. **Did Phase A clear the mechanical gate?** No. Six of six preserved facts, but only two of six cleared either required 25% efficiency threshold.

7. **If live-tested, do agents naturally use `inspect_ranges`?** Not tested. Phase B was gated off.

8. **Does v2 displace repeated Python/view inspection?** Mechanically, it can consolidate some explicit range slices; the replay measured this as 53→24 and 22→13 range-level operations in two tasks. Natural model displacement was not tested.

9. **Does it displace model/tool cycles, or only tool implementation bytes?** Not established. Phase A has no model behavior and no causal call-cycle measurement.

10. **Does capability remain preserved?** The factual read replay preserved the available facts. The frozen checkpoint still supports capability preservation. No live v2 capability comparison was run.

11. **What happens to direct observation bytes?** Against the raw frozen historical observations, they increase in all six task replays. Against the same facts encoded as verbose v2 dictionaries, compactness reduces them by a median 60.81%.

12. **What happens to subsequent context burden?** Not observed live. The history multiplier is therefore unmeasured in this adjudication.

13. **What happens to total calls/tokens/cost?** No new live totals exist. Phase A provides no valid end-to-end calls, tokens, or cost estimate.

14. **Can those changes be causally aligned with actual v2 use?** No. There was no Phase B trajectory.

15. **Does helper salience remain controlled between V1 and V2?** Not tested. The identical-documentation V1/V2 discriminator was not reached.

16. **Did provider/runtime censor any pairs?** No Phase-B pairs were run. A separate preliminary live probe was provider-censored and is explicitly excluded from outcomes.

17. **Did freshness/fidelity remain perfect?** In Phase A, yes: zero stale responses, zero v2 silent truncations, and no systematic factual loss. Live freshness was not tested.

18. **Is the checkpoint’s broad “no efficiency gain” conclusion still defensible?** Not as a causal null. The checkpoint was right that its aggregate A/B result was confounded. This adjudication shows a real narrow compactness mechanism, but it also shows that this v2 representation is not a general raw-observation efficiency win on the frozen six-task population.

19. **What should the evidence ledger now say?** The corrected state is given below. In particular, v1 end-to-end efficiency remains confounded, v2 behavioral and end-to-end effects are untested, and v2 mechanical compression is supported only narrowly.

20. **Is a later default-v2 system A/B justified?** No. The specified precondition—strong Phase A gate plus live behavioral substitution plus preserved capability—was not met.

## Evidence ledger

| Evidence item | State |
|---|---|
| CAPABILITY PRESERVATION | SUPPORTED |
| TRANSPARENT RUNTIME | SUPPORTED |
| V1 READ-SIDE MECHANISM | EARNED |
| V1 END-TO-END EFFICIENCY | CONFOUNDED |
| V2 MECHANICAL COMPRESSION | SUPPORTED_NARROWLY |
| V2 BEHAVIORAL SUBSTITUTION | UNTESTED |
| V2 END-TO-END EFFICIENCY | UNTESTED |
| TEMPLATE / DEBUGGING GENERALIZATION | NOT_ESTABLISHED |
| MUTATION-SIDE OPTIMIZATION | CLOSED |
| POST-MUTATION VERIFICATION | CLOSED |
| FULL-BENCHMARK JUSTIFICATION | NOT_ESTABLISHED |

## Final synthesis

### WHAT THE CHECKPOINT GOT RIGHT

It correctly established capability preservation and transparent runtime integrity, and it correctly identified that its aggregate efficiency differences were confounded by helper-note salience, trajectory variance, observation caps, and lack of batching.

### WHAT THE CHECKPOINT COULD NOT ESTABLISH

It could not establish that compiled factual reads cannot save work. The current replay demonstrates a substantial representation-level compression mechanism, separate from live behavior.

### WHAT WAS WRONG WITH V1

V1 exposed verbose per-cell dictionaries, had no multi-range batch surface, and allowed large observations to collide with common caps. Its end-to-end efficiency result was therefore not a clean test of compact/batched factual reads.

### PHASE-A MECHANICAL RESULT

Factual preservation was positive on 6/6 tasks, but the mechanical efficiency gate failed: 0/6 raw-byte wins, 2/6 operation wins, and 2/6 clearing either threshold. Verdict: `V2_MECHANICAL_COMPRESSION_NOT_GENERAL`.

### PHASE-B BEHAVIORAL RESULT

Not run. The gate correctly stopped the live discriminator; no behavioral adoption or causal efficiency claim is available.

### CAPABILITY RESULT

No Phase-B capability regression exists because no live Phase-B run exists. Phase A had no stale, truncation, or systematic factual-loss failure, and the frozen capability result remains supported.

### DIRECT CONTEXT SAVING

The direct saving is real only for the controlled verbose-to-compact comparison: median 60.81%. Against the actual frozen historical observations, direct serialized payload increased.

### CALL-COUNT EFFECT

Batching reduced range-level inspection operations materially in two tasks, but not broadly enough for the gate. No model-turn displacement was measured.

### END-TO-END TOKEN / COST EFFECT

Unmeasured in this adjudication. The provider-censored preliminary probe is not evidence for either arm.

### CORRECTED EVIDENCE LEDGER

CAPABILITY PRESERVATION — `SUPPORTED`  
TRANSPARENT RUNTIME — `SUPPORTED`  
V1 READ-SIDE MECHANISM — `EARNED`  
V1 END-TO-END EFFICIENCY — `CONFOUNDED`  
V2 MECHANICAL COMPRESSION — `SUPPORTED_NARROWLY`  
V2 BEHAVIORAL SUBSTITUTION — `UNTESTED`  
V2 END-TO-END EFFICIENCY — `UNTESTED`  
TEMPLATE / DEBUGGING GENERALIZATION — `NOT_ESTABLISHED`  
MUTATION-SIDE OPTIMIZATION — `CLOSED`  
POST-MUTATION VERIFICATION — `CLOSED`  
FULL-BENCHMARK JUSTIFICATION — `NOT_ESTABLISHED`

### WHETHER READ-SIDE EFFICIENCY REMAINS OPEN

The old broad null remains unjustified because v1 was confounded and v2 has a real narrow compression mechanism. However, this specific v2 branch failed its mechanical generality gate, so it should not advance to live inference or be treated as an established efficiency lever.

### WHETHER A DEFAULT-v2 SYSTEM TEST IS JUSTIFIED

No. Phase A did not clear, and Phase B therefore supplied neither natural adoption nor capability-preserving end-to-end evidence.

### SINGLE NEXT EXPERIMENT

If the branch is reopened, run one repaired mechanical replay that equalizes the visible-fact set and bounded observation budget before any model call; only if that replay clears the same 4/6 gate should the identical-documentation V1/V2 live discriminator be attempted.
