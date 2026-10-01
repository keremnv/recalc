# Candidate-A A1 12-Task Checkpoint Report

## Verdict: `PROVIDER_OR_RUNNER_CENSORED`

The frozen live runner completed one H0 run, began its matched H1 run, then stalled in a chunked provider response and was interrupted. Twenty-two primary runs were never started. No Candidate-A speed, capability, or reliability conclusion is drawn from this partial live record.

## Required answers

1. **Selected tasks:** Financial_Model:07_01, Financial_Model:08_03, Financial_Model:08_01, Financial_Model:15_04, Debugging:10_10, Financial_Model:06_01, Debugging:01_06, Debugging:10_04, Debugging:05_02, Template:13_08, Template:03_03, Financial_Model:10_01.
2. **Frozen ranking rule:** top 12 by A1-eligible historical executions, same-generation repeated-open count, A1-safe primitive reads, historical deterministic read/open time, then stable task ID; no score, gold, outcome, or balancing.
3. **Family composition:** {'Financial_Model': 6, 'Debugging': 4, 'Template': 2}; selected before inference.
4. **H1 contact:** 0 valid completed H1 tasks; the H1 task in progress was censored.
5. **Contact executions:** 0 valid completed H1 contact executions.
6. **Accelerated operations:** 0 valid completed H1 accelerated operations.
7. **Parses avoided:** not estimable; no valid H1 contact trace completed.
8. **H0 counterfactual eligibility:** 10 eligible load opportunities in the one completed H0 run.
9. **High-exposure non-contact:** not adjudicable from one completed H0 and one censored H1; the partial H1 events were all fallback events.
10. **Non-FM contact:** none observed in valid completed runs.
11. **Stale/wrong-generation reads:** no stale/wrong-generation event observed in completed H0/shared-substrate telemetry; H1 reliability is not established.
12. **Semantic/fallback mismatch:** none observed in completed artifacts; no valid H1 comparison.
13. **Exact-trace replay:** 0 traces; untested.
14. **Capability:** untested for H1; no reproducible capability comparison.
15. **Real per-load time:** completed H0 recorded load timings; no valid H1 comparison.
16. **Candidate-A per-load time:** no accelerated H1 load completed.
17. **Candidate-A per-read time:** no accelerated H1 read completed.
18. **Fallback materialization:** partial H1 events recorded eight predeclared fallback loads; not a completed-run estimate.
19. **Exact-trace timing:** no valid traces.
20. **Positive trace fraction:** not estimable.
21. **Median exact-trace reduction:** not estimable.
22. **Median absolute saving:** not estimable.
23. **Effect by task:** none estimable.
24. **Total Python walltime:** one completed H0 run recorded 13.232343385112472 s; no H1 comparison.
25. **Total tool walltime:** one completed H0 run recorded 17.497114800964482 s; no H1 comparison.
26. **Total task walltime:** one completed H0 run recorded 1130.0136512210593 s; no H1 comparison.
27. **Model/network share:** completed H0 network wait was 1111.2365770339966 s; no paired system fraction.
28. **Calls/tokens/cost:** no treatment-neutrality conclusion from one H0 only.
29. **Causally removable deterministic time:** not established.
30. **Benchmark relevance:** not established; the checkpoint is censored before valid live contact evidence.
31. **Runtime retention:** not decidable from this checkpoint; prior narrow shadow evidence is not replaced.
32. **A2:** not justified by this censored run.
33. **Candidate B:** remains frozen.
34. **Final architectural claim:** only that the requested decision experiment could not obtain sufficient valid paired live evidence under the frozen provider/runner path.

## Censoring record

Completed primary runs: 1/24. Partial H1 run: primary_02_Financial_Model_07_01_H1; runtime events: 16, loads: 8, accelerated operations: 0. Unstarted primary runs: 22. The interruption occurred while `urllib` was reading a chunked HTTPS response.

## Evidence ledger

- PYTHON_AS_AGENT_QUERY_LANGUAGE: EARNED
- CANDIDATE_A_A1_LIVE_RELIABILITY: NOT_ESTABLISHED
- CANDIDATE_A_A1_LIVE_CAPABILITY_NEUTRALITY: NOT_ESTABLISHED
- CANDIDATE_A_A1_LIVE_CONTACT: NOT_ESTABLISHED
- CANDIDATE_A_A1_EXACT_TRACE_FIDELITY: UNTESTED
- CANDIDATE_A_A1_MECHANICAL_EFFECTIVENESS: UNTESTED
- CANDIDATE_A_A1_SYSTEM_MATERIALITY: NOT_ESTABLISHED
- CANDIDATE_A_A1_CROSS_FAMILY_GENERALISATION: UNTESTED
- CANDIDATE_A_TOKEN_COST_EFFECT: NOT_ESTABLISHED
- CANDIDATE_A_RUNTIME_RETENTION: NOT_ESTABLISHED
- A2_RESEARCH_JUSTIFICATION: NOT_ESTABLISHED
- CANDIDATE_B_REOPENING: CLOSED
- BROADER_BENCHMARK_JUSTIFICATION: NOT_ESTABLISHED

WHAT A1 CONTACTED LIVE

No valid completed H1 run contacted Candidate A. The partial H1 run generated only predeclared real-openpyxl fallback load events before provider censoring.

WHY NON-CONTACT STILL OCCURRED

The checkpoint did not reach enough completed H1 trajectories to distinguish contact prevalence; no inference is made.

CAPABILITY RESULT

Not established because the H1 trajectory and official paired evaluation did not complete.

RELIABILITY RESULT

Not established for live A1; no valid H1 contact trace existed. Completed H0 freshness telemetry showed no stale generation.

DIRECT LOAD / READ TIMING

Only completed H0 and partial fallback telemetry exist; no H1 accelerated timing comparison.

EXACT-TRACE CAUSAL EFFECT

Untested: zero valid H1 contact traces.

PARSES AVOIDED

Not established.

PYTHON / TOOL-TIME EFFECT

Not comparable.

TOTAL TASK-TIME EFFECT

Not comparable.

MODEL / NETWORK DOMINANCE

The stalled chunked response is a provider/runner censoring event, not a treatment effect.

TOKEN / COST EFFECT

Not established.

CROSS-FAMILY CONTACT

Untested.

HISTORICAL-VS-LIVE EXPOSURE

Not adjudicable from the censored checkpoint; population ranking remains frozen.

WHETHER CONTACT IS SUFFICIENT

No: valid contact evidence is insufficient, not evidence of low contact.

WHETHER CONDITIONAL SPEEDUP IS MATERIAL

Untested in this live checkpoint.

WHETHER A1 IS A BENCHMARK-LEVEL MECHANISM

Not established.

WHETHER A1 IS STILL WORTH RETAINING AS A NARROW FAST PATH

Not decided by this censored experiment; prior shadow evidence remains the relevant retention evidence.

WHETHER A2 DESERVES A SEPARATE MECHANICAL PROBE

No new justification from this run.

WHETHER CANDIDATE B REMAINS FROZEN

Yes.

FINAL EVIDENCE LEDGER

PYTHON_AS_AGENT_QUERY_LANGUAGE: EARNED
CANDIDATE_A_A1_LIVE_RELIABILITY: NOT_ESTABLISHED
CANDIDATE_A_A1_LIVE_CAPABILITY_NEUTRALITY: NOT_ESTABLISHED
CANDIDATE_A_A1_LIVE_CONTACT: NOT_ESTABLISHED
CANDIDATE_A_A1_EXACT_TRACE_FIDELITY: UNTESTED
CANDIDATE_A_A1_MECHANICAL_EFFECTIVENESS: UNTESTED
CANDIDATE_A_A1_SYSTEM_MATERIALITY: NOT_ESTABLISHED
CANDIDATE_A_A1_CROSS_FAMILY_GENERALISATION: UNTESTED
CANDIDATE_A_TOKEN_COST_EFFECT: NOT_ESTABLISHED
CANDIDATE_A_RUNTIME_RETENTION: NOT_ESTABLISHED
A2_RESEARCH_JUSTIFICATION: NOT_ESTABLISHED
CANDIDATE_B_REOPENING: CLOSED
BROADER_BENCHMARK_JUSTIFICATION: NOT_ESTABLISHED

SINGLE NEXT EXPERIMENT

Resolve the provider/runner chunked-response censoring, then rerun this exact frozen 12-task checkpoint without changing prompts, arms, Candidate-A surface, A1 classifier, or Candidate B status.
