# Candidate A Live Treatment Report

This was the first narrow live causal treatment. Prompts, tools, model, scaffold, and syntax were identical; H1 changed only the Python subprocess interposition flag. Candidate B was not implemented.

Verdict: **LIVE_A_CONTACT_INSUFFICIENT**.

## Required answers

1. Selected tasks: Financial_Model:07_01, Financial_Model:08_03, Financial_Model:08_01, Financial_Model:06_01, Debugging:01_06, Debugging:05_02. The frozen rule retained no-reason A_FULLY_PROXYABLE primitive-read executions with repeated-open evidence, then sorted by safe read events, repeated-open surplus, safe executions, and task ID; the complete ranking is in `population_ranking.json`.
2. Family composition: {'Financial_Model': 4, 'Debugging': 2}. This is exposure-enriched, not family-balanced or representative.
3. H1 contact occurred on 2/6 runs: ['Financial_Model:08_01', 'Financial_Model:08_03'].
4. Accelerated primitive operations: 4073. Workbook loads themselves are not counted as contact.
5. Conservative fallback events: 94. Reasons are retained in `fallback_events.jsonl`; predeclared unsafe Python sources were forced to real openpyxl.
6. Fallback reasons: {'forced real path': 76, 'Worksheet.sheet_state': 13, 'unsupported object behavior': 2, 'unsupported load mode/options': 2, 'Workbook.worksheets': 1}.
7. Real openpyxl parses avoided: 47 across matched pairs.
8. Same-generation repeated-open acceleration: 47 parse/open events avoided in this n=1 sample; common substrate refreshes are reported separately.
9. Stale/wrong-generation reads: 0/0.
10. Semantic/fallback mismatch: 0 unexplained; identity corruption 0.
11. Capability: see `capability.json` and `capability_gate.json`; no reproducible H1 capability loss was observed.
12. No capability discordance was treated as causal without replication; the primary capability rows are preserved.
13. Pre-contact trajectory variance is recorded in `pre_contact_variance.jsonl`; no treatment-specific observation exists before H1 contact by construction.
14. Direct workbook-read/open timing was not separately instrumented. The matched deterministic tool-walltime proxy is: [{"h0_deterministic_tool_walltime_s": 101.04234723304398, "h1_deterministic_tool_walltime_s": 49.55389438022394, "reduction_pct": 50.9573008375064, "task_id": "Financial_Model:08_03"}, {"h0_deterministic_tool_walltime_s": 108.34393121174071, "h1_deterministic_tool_walltime_s": 71.72962468315382, "reduction_pct": 33.79451540947886, "task_id": "Financial_Model:08_01"}].
15. Median deterministic tool-walltime proxy reduction: 50.9573008375064%; positive tasks 2. This is not a direct read/open-time causal estimate.
16. Total Python walltime, 17. total tool walltime, and 18. total task walltime are in `task_timing.json`; n=1 timing is noisy.
19. Model/network latency is separately recorded in each run’s `efficiency.model_network_wait_s`; it is not included in mechanical read-time comparisons.
20. Calls/tokens/cost were intended to remain treatment-neutral; recorded aggregate behavior is in `model_behavior.json`. No token or cost saving is claimed.
21. Shared-substrate benefit is tested by common parent-maintained substrate plus H1 persistent reads; direct workbook-load timing was not isolated from Python/tool execution in this live runner.
22. Non-FM acceleration: [].
23. Unproven: benchmark-wide prevalence, cross-family generality, token/cost savings, model reasoning effects, and broad openpyxl replacement.
24. Broader checkpoint: not justified; any next checkpoint must preserve the identical interface.
25. Candidate B remains frozen.

## Targeted replication

The required matched replication of Financial_Model:08_03 ran H1 first. H1 contacted Candidate A (7211 accelerated operations); H0 contacted Candidate A: False. Output produced was H0=False and H1=False; the primary output/no-output discordance was therefore not reproduced. The replication does not add an independent task to the contact gate. Its deterministic tool walltime was H0=83.95s versus H1=86.31s; this was not a positive timing replication.

## Evidence ledger

| BROADER_CHECKPOINT_JUSTIFICATION | NOT_ESTABLISHED |
| CANDIDATE_A_CROSS_FAMILY_GENERALISATION | NOT_ESTABLISHED |
| CANDIDATE_A_LIVE_CAPABILITY_NEUTRALITY | SUPPORTED_NARROWLY |
| CANDIDATE_A_LIVE_CONTACT | SUPPORTED_NARROWLY |
| CANDIDATE_A_LIVE_MECHANICAL_EFFECTIVENESS | NOT_ESTABLISHED |
| CANDIDATE_A_LIVE_RELIABILITY | SUPPORTED_NARROWLY |
| CANDIDATE_A_LIVE_SYSTEM_MATERIALITY | NOT_ESTABLISHED |
| CANDIDATE_A_TOKEN_COST_EFFECT | NOT_ESTABLISHED |
| CANDIDATE_B_REOPENING | CLOSED |
| PYTHON_AS_AGENT_QUERY_LANGUAGE | EARNED |
| TRANSPARENT_READ_ACCELERATION | SUPPORTED_NARROWLY |

## Final synthesis

WHAT THE LIVE TREATMENT ACTUALLY CONTACTED

H1 contacted 2 primary tasks and 4073 primary primitive operations; the targeted replication additionally contacted 1 already-counted task (7211 operations): ['Financial_Model:08_01', 'Financial_Model:08_03']. The population was {'Financial_Model': 4, 'Debugging': 2}; contact is the relevant denominator, not the six-task population alone.

CAPABILITY RESULT

No reproducible H1 capability degradation was established. The primary output/no-output discordance was not reproduced in the required targeted replication; official exact/modification/regression/output/submission rows are preserved.

RELIABILITY RESULT

Across primary and targeted-replication runs, no stale reads, wrong-generation reads, identity corruption, or unexplained semantic substitutions were recorded: {'candidate_a_caused_exceptions': 0, 'contact_tasks': 2, 'fallback_identity_corruption': 0, 'freshness_events': 272, 'note': 'No runtime event reported stale/wrong-generation/identity failure; official capability and output checks are in capability.json.', 'pass': True, 'primary_freshness_events': 229, 'silent_semantic_substitutions': 0, 'stale_reads': 0, 'targeted_replication_fallback_identity_corruption': 0, 'targeted_replication_freshness_events': 43, 'targeted_replication_stale_reads': 0, 'targeted_replication_wrong_generation_reads': 0, 'wrong_generation_reads': 0}.

REPEATED-OPEN / PARSE EFFECT

Matched parse avoidance is 47 events. Common substrate build/refresh cost was run in both arms and kept separate.

MECHANICAL READ-TIME EFFECT

Direct workbook read/open time was not isolated. The deterministic tool-walltime proxy fell by 50.96% and 33.79% on the two primary contact comparisons, but the required replication was H0=83.95s versus H1=86.31s; the live timing evidence is therefore mixed and not a clean read-time causal estimate.

PYTHON / TOOL-TIME EFFECT

On the two primary contact pairs, Python walltime fell from 82.82s to 26.65s and from 98.54s to 52.50s; total task walltime nevertheless rose from 870.01s to 934.51s and from 906.17s to 942.13s because model/network wait dominated. The replication Python walltime was H0=73.96s versus H1=79.97s. Full timings are in `task_timing.json`.

TOTAL TASK-TIME EFFECT

Total task time did not improve on the primary contact pairs: H1 was +7.4% and +4.0%; the replication was +2.9%. Model/network latency accounted for roughly 88–94% of those contacted task totals.

MODEL CALL / TOKEN / COST EFFECT

Primary aggregate behavior was H0=167 calls/6.69M tokens/$0.628 versus H1=133 calls/5.50M tokens/$0.523, but this is trajectory variance, not a treatment claim; the model surface was identical and token/cost benefit is not established.

PRE-CONTACT VARIANCE

Pre-contact records are in `pre_contact_variance.jsonl`; any model trajectory variance before first contact is not attributed to Candidate A.

CROSS-FAMILY CONTACT

The selected population contains two Debugging tasks, but neither received H1 acceleration; no cross-family live contact was obtained.

THE PRECISE NARROWNESS OF THE RESULT

Semantic: frozen formula-mode primitive surface only. Contact: conservative fallback dominates many scripts. Family: exposure-enriched FM-heavy sample. Economic: shared compiled substrate assumed common; read-only index construction is not charged as an H1-only benefit.

WHAT CANDIDATE A NOW EARNS

Candidate A earns two live FM contact witnesses with clean observed reliability and lower deterministic tool-walltime proxies, but the required independent-task contact gate did not pass and direct read/open timing was not isolated.

WHAT IT STILL DOES NOT EARN

It does not earn benchmark-wide speedup, cross-family generality, token/cost savings, better reasoning, or general openpyxl replacement.

WHETHER CANDIDATE B REMAINS FROZEN

Yes. Candidate B was not implemented or tested.

WHETHER A BROADER CHECKPOINT IS JUSTIFIED

No; the frozen contact/effectiveness gates did not clear.

SINGLE NEXT EXPERIMENT

Run one larger identical-interface Candidate-A checkpoint with direct per-load/read timing and an exposure-enriched population; keep conservative fallback and the model surface unchanged.
