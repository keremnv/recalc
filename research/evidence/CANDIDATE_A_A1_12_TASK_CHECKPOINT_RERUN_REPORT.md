# Candidate-A A1 12-Task Checkpoint Rerun Report

This is a new run of the exact frozen checkpoint after transport hardening. The earlier censored attempt at `candidate_a_a1_checkpoint/` was preserved and not overwritten. No prompts, model-facing interface, Candidate-A semantic surface, A1 classifier, A2, A3, or Candidate B changed.

Verdict: **A1_LIVE_END_TO_END_SUPPORTED**

## Transport and provenance

The runner now enforces socket/read < request < retry budget < model-call < task deadline: 15s < 90s < 270s < 300s < 900s. The deliberately stalled/chunked-response suite passed 4/4, including retry-after-read-timeout and subprocess timeout behavior. The rerun used the byte-identical population and run order from the failed attempt; see `rerun_manifest.json`.

All 24 primary slots were attempted. There were 6 provider-censored slots and 2 shared runner/workbook-error slots. These are retained as censored evidence, not agent outcomes. The common XML namespace error occurred in both arms for `Financial_Model:06_01`.

## Main result

- Population: 12 tasks, family composition {'Financial_Model': 6, 'Debugging': 4, 'Template': 2}.
- H1 contact: 7/12 independent tasks, 7 runs, 135,937 canonical accelerated events.
- Contact tasks: Debugging:05_02, Debugging:10_10, Financial_Model:08_01, Financial_Model:08_03, Financial_Model:10_01, Financial_Model:15_04, Template:13_08.
- Exact trace replay: 51/51 semantic-exact, 0 mismatches.
- Exact-trace speed: median 44.46% reduction, median 1.423s saved, 50/51 traces positive (98.0%).
- Positive independent tasks: 7/7.
- Reliability: 0 freshness anomalies and 0 replay mismatches.
- Runtime recommendation: **RETAIN_A_IN_RUNTIME**, narrowly and conditionally.

## Required interpretation

The contact gate passed at 7/12, and the exact-trace mechanical gate passed. The result supports a useful invisible deterministic fast path on the contacted, exposure-enriched workload. It does not establish benchmark-wide prevalence, cross-family generality beyond the observed FM/Debugging/Template contact, model-call reduction, token savings, cost savings, or general openpyxl replacement.

The non-Financial-Model contact families were Debugging and Template. This is evidence of cross-family contact, not a generalization estimate. Several live arm/task outcomes were provider-censored, so task-level capability comparisons remain limited. Comparable completed pairs did not show reproducible contact-attributed degradation; exact traces were all exact.

## Required answers

1. **Selected tasks/rule:** the exact frozen 12-task ranking and within-task arm order are in `population_ranking.json`, `population.json`, and `run_order.json`; no reselection occurred.
2. **Family composition:** {'Financial_Model': 6, 'Debugging': 4, 'Template': 2}.
3. **H1 contact:** 7/12 tasks; 7 runs.
4. **Accelerated operations:** 135,937 canonical events.
5. **Real parses avoided:** live H0/H1 parse counts are in `task_timing.json`; exact replay performs 3 real parses versus 0 Candidate-A parses per trace, for 153 replay parses avoided.
6. **H0 counterfactual eligibility:** `h0_shadow_eligibility.jsonl` records the A1-eligible load opportunities without routing H0 through A.
7. **Non-contact:** stochastic Python shape, conservative fallback boundaries, provider censoring, and the shared XML setup error explain missing task-level evidence; no treatment behavior was exposed to the model.
8. **Stale/fidelity:** zero stale/wrong-generation events and 0 exact-trace mismatches.
9. **Capability:** official H0/H1 evaluation is in `capability.json`; no reproducible contact-attributed H1 degradation is established, but censored slots are not treated as capability outcomes.
10. **Direct timing:** per-load/read timing is archived; exact trace is the causal timing estimate.
11. **Model behavior:** calls/tokens/cost are archived in `model_behavior.json` and are treated as trajectory-neutrality checks, not benefits.

## Final synthesis

### WHAT A1 CONTACTED LIVE

Debugging:05_02, Debugging:10_10, Financial_Model:08_01, Financial_Model:08_03, Financial_Model:10_01, Financial_Model:15_04, Template:13_08; 7 independent tasks spanning Financial_Model, Debugging, and Template.

### WHY NON-CONTACT STILL OCCURRED

The model emitted unsupported or conservative-fallback Python in some tasks, and several provider calls were censored. A1 did not change the model surface.

### CAPABILITY RESULT

No reproducible contact-attributed capability loss; the run contains censored and non-submitting outcomes, so this is narrow capability neutrality rather than a benchmark capability result.

### RELIABILITY RESULT

Exact-trace fidelity was 51/51; no stale, wrong-generation, identity, or semantic substitution was observed.

### DIRECT LOAD / READ TIMING

H1 contact runs recorded substrate-hit acquisition and primitive timing. Exact-trace replay gives the clean backend comparison.

### EXACT-TRACE CAUSAL EFFECT

Median 44.46% read-trace reduction and 1.423s median saved; 50/51 traces improved.

### PARSES AVOIDED

Each exact trace used three R0 real-openpyxl parses and zero R1 parses: 153 replay parses avoided. Live parse counts remain task-specific and include fallback behavior.

### PYTHON / TOOL-TIME EFFECT

Secondary live timing is noisy and provider-dominated; it is not the causal estimator. `task_timing.json` contains the arm/task decomposition.

### TOTAL TASK-TIME EFFECT

Not claimed from stochastic cross-arm walltime.

### MODEL / NETWORK DOMINANCE

The live H1 task-time sum was 5690.7s, of which 2629.2s was model/network wait (46.2%).

### TOKEN / COST EFFECT

No token or cost benefit is claimed.

### CROSS-FAMILY CONTACT

Contact occurred in Financial_Model, Debugging, and Template; this is narrow observed transfer, not family-general prevalence.

### HISTORICAL-VS-LIVE EXPOSURE

Per-task comparison is in `historical_live_exposure.jsonl`; selected historical exposure did not guarantee matching live Python.

### WHETHER CONTACT IS SUFFICIENT

Yes for the exposure-enriched checkpoint: 7/12 exceeds the required 4/12. It is not sufficient for a representative benchmark claim.

### WHETHER CONDITIONAL SPEEDUP IS MATERIAL

Yes on exact traces: median 44.46% reduction, above the 25% gate.

### WHETHER A1 IS A BENCHMARK-LEVEL MECHANISM

No. It is a supported conditional mechanism on the contacted exposure-enriched workload, not a benchmark-wide prevalence result.

### WHETHER A1 IS STILL WORTH RETAINING AS A NARROW FAST PATH

**RETAIN_A_IN_RUNTIME** because reliability is clean, the substrate is shared, fallback is conservative, and exact-trace speedup is material.

### WHETHER A2 DESERVES A SEPARATE MECHANICAL PROBE

**A2_RESEARCH_NOT_JUSTIFIED**. The current result does not require opening another interposition branch.

### WHETHER CANDIDATE B REMAINS FROZEN

Yes. No A1 failure implicated proxy semantics, and no B work was performed.

### FINAL EVIDENCE LEDGER

- PYTHON_AS_AGENT_QUERY_LANGUAGE: EARNED
- CANDIDATE_A_A1_LIVE_RELIABILITY: SUPPORTED_NARROWLY
- CANDIDATE_A_A1_LIVE_CAPABILITY_NEUTRALITY: SUPPORTED_NARROWLY
- CANDIDATE_A_A1_LIVE_CONTACT: EARNED
- CANDIDATE_A_A1_EXACT_TRACE_FIDELITY: EARNED
- CANDIDATE_A_A1_MECHANICAL_EFFECTIVENESS: EARNED
- CANDIDATE_A_A1_SYSTEM_MATERIALITY: SUPPORTED_NARROWLY
- CANDIDATE_A_A1_CROSS_FAMILY_GENERALISATION: SUPPORTED_NARROWLY
- CANDIDATE_A_TOKEN_COST_EFFECT: NOT_ESTABLISHED
- CANDIDATE_A_RUNTIME_RETENTION: SUPPORTED_NARROWLY
- A2_RESEARCH_JUSTIFICATION: A2_RESEARCH_NOT_JUSTIFIED
- CANDIDATE_B_REOPENING: CLOSED
- BROADER_BENCHMARK_JUSTIFICATION: NOT_ESTABLISHED

### SINGLE NEXT EXPERIMENT

No immediate architecture expansion. If benchmark-wide prevalence is required, run a separately budgeted representative identical-interface checkpoint with this transport-tested runner; otherwise retain the narrow A1 fast path and stop treating it as a benchmark efficiency claim.
