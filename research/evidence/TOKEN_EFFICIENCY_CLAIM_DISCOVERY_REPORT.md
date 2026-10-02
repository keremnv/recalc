# Token-efficiency claim discovery

This is a preregistered 2×2 **claim-discovery** experiment on a mechanism-enriched cohort. Architecture discovery remains closed; this is not a public claim-validation result. A later independent 48-slot affordance study also failed its frozen discovery gate. This report preserves the original 2×2 verdict; the new deliverable index is retrospective and did not add model calls or change preregistered inference.

Frozen specification: `9acaec8ccdb6a51161eeee6488059b043d0a92893a0ba0a5b907fd7c67f5e0d4`. Product RC: `0.2.0rc1`, source/config `1aba3117…`, wheel `532e493f…`. Primary slots recorded: **60/60**. Replication slots: **0**.

## Design and integrity

| Arm | Strategy note | Helpers |
| --- | --- | --- |
| A | Neutral | Off |
| B | Neutral | On |
| C | Targeted-inspection salience | Off |
| D | Targeted-inspection salience | On |

Invisible runtime: Candidate A off; compiled substrate off; capture off; ordinary openpyxl in every arm. Helpers, when visible, are the frozen `lx_helpers` Python functions from the RC wheel using reference openpyxl. The provider tool schemas remain bash/view_xlsx/submit in all arms; H changes Python helper availability and its exact addendum. This preserves the frozen product interface.

The strategy notes are 38 and 38 tokens under the recorded local `cl100k_base` estimate (difference 0); no model-native tokenizer count is claimed.

**Neutral note**

```text
## Working note
Use the available spreadsheet tools as appropriate for the task. Check the workbook and produce the requested output. Continue until you can submit the result. Record the final output path.
```

**Salience note**

```text
## Working note
Prefer targeted inspection of needed cells or ranges using ordinary Python/openpyxl. Avoid dumping entire workbooks or sheets unless broad inspection is required. Gather evidence incrementally.
```

**Helpers-on addendum**

```text
## Optional factual helpers
You may import `lx_helpers` in Python. Available signatures: `search(workbook, pattern, regex=False, sheet=None)`, `periods(workbook, sheet=None)`, `inspect(workbook, sheet, cell_range, with_styles=False)`. These read the workbook with ordinary openpyxl. They are optional; ordinary Python/openpyxl and view_xlsx remain available.
```

Population label: `MECHANISM_ENRICHED_NOT_REPRESENTATIVE`. Selection used frozen H0 completion and broad-observation headroom only. All other tasks, including the independent seed-20261001 30-task reservation, were left unrun.

## Historical lower-token observations

These are experiment/cohort records, not 55 independent registry rows. They vary in token measure and are not pooled.

| Experiment | Control | Treatment | Measure | Attribution defect |
| --- | ---: | ---: | --- | --- |
| Inspection efficiency Stage B (aggregate) | 6,319,843 | 3,760,254 | total provider tokens | Optional helper+note changed visible evidence and backend. Later thin checkpoint attributed aggregate view shift largely |
| Thin architecture checkpoint (ALL) | 18,097,832 | 16,258,754 | total provider tokens | Representative non-adopters show lower tokens; exposure cohort has higher tokens. No aggregate helper/runtime attributio |
| Thin architecture checkpoint (A-representative) | 7,722,979 | 5,345,845 | total provider tokens | Representative non-adopters show lower tokens; exposure cohort has higher tokens. No aggregate helper/runtime attributio |
| Thin architecture checkpoint (B-exposure) | 10,374,853 | 10,912,909 | total provider tokens | Representative non-adopters show lower tokens; exposure cohort has higher tokens. No aggregate helper/runtime attributio |
| Batch-write helpers (aggregate) | 4,104,791 | 4,058,278 | total provider tokens | Zero helper invocations in all 13 treatment runs. Lower total is descriptive; rejected branch remains closed. |
| Default-harness deterministic execution (aggregate) | 15,731,994 | 14,047,346 | provider prompt tokens | Executor invoked zero times; lower treatment tokens cannot be attributed to execution. |
| Compact evidence encoding, complete pairs (aggregate) | 5,842,363 | 4,998,231 | provider prompt tokens | Explicit representation intervention makes prompt reduction plausible on completed pairs; rejected mechanism, unretained |
| Historical Phase C translation subset (aggregate) | 4,170,000 | 2,030,000 | input tokens (rounded summary) | Session consolidation under old edit-plan architecture; default-agent transfer not established; preserve without integra |
| Historical bounded inspection/compare, Financial_Model:01_03 (aggregate) | 549,294 | 178,294 | provider prompt tokens | 2026-08-25 Grok rerun changed visible inspection/compare payloads; reported equal workbook cell content. Historical MCP  |
| candidate_a_live (aggregate) | 6,569,169 | 5,367,656 | total provider tokens | Available-token run totals only; missing usage not imputed as zero. Trajectory lengths, output production and censoring  |
| candidate_a_a1_checkpoint_rerun_01 (aggregate) | 8,637,149 | 3,497,071 | total provider tokens | Available-token run totals only; missing usage not imputed as zero. Trajectory lengths, output production and censoring  |
| live_transparent_runtime_ab (aggregate) | 2,128,686 | 2,163,980 | total provider tokens | Available-token run totals only; missing usage not imputed as zero. Trajectory lengths, output production and censoring  |
| targeted_runtime_replication (aggregate) | 2,866,299 | 3,072,131 | total provider tokens | Available-token run totals only; missing usage not imputed as zero. Trajectory lengths, output production and censoring  |
| representative_architecture_checkpoint (aggregate) | 12,321,973 | 16,860,574 | total provider tokens | Available-token run totals only; missing usage not imputed as zero. Trajectory lengths, output production and censoring  |
| representative_architecture_checkpoint_replication (aggregate) | 1,782,516 | 860,988 | total provider tokens | Available-token run totals only; missing usage not imputed as zero. Trajectory lengths, output production and censoring  |

## Primary provider-input-token contrasts

Task-level paired ratios are the unit. Censored pairs are excluded from E2 paired contrasts; model noncompletion stays in E2 as an outcome and cannot be interpreted as a saving.

| Contrast | E2 pairs | Median ratio | Median reduction | Geometric mean ratio | Bootstrap 95% CI | Favorable direction | E1 dual-valid pairs |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| D / A | 14 | 0.888 | 11.164% | 0.854 | [0.5631591639611041, 1.2119890703056515] | 8 | 8 |
| C / A | 13 | 0.972 | 2.760% | 0.925 | [0.5165075340540984, 1.8229465046496538] | 7 | 8 |
| B / A | 14 | 0.848 | 15.176% | 0.706 | [0.50162020386776, 0.9388129922794695] | 9 | 9 |
| D / C | 13 | 0.949 | 5.069% | 0.914 | [0.5353727344503874, 1.4900096108089163] | 8 | 6 |
| D / B | 14 | 0.993 | 0.668% | 1.210 | [0.9543354535258894, 1.5867433360713012] | 7 | 9 |

## Mechanism and capability

| Arm | Calls | Input per call | Cumulative prior-observation bytes | Visible observation bytes | Broad views | Python calls | Helper mentions | Valid submissions | Tokens per valid submission |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 329 | 24,189.951 | 15,308,310 | 957,611 | 39 | 172 | 0 | 10 | 795,849.400 |
| B | 257 | 27,676.144 | 13,078,795 | 991,270 | 30 | 113 | 4 | 12 | 592,730.750 |
| C | 306 | 27,256.399 | 15,454,287 | 1,001,872 | 24 | 195 | 0 | 8 | 1,042,557.250 |
| D | 275 | 27,407.847 | 13,845,424 | 1,008,265 | 12 | 192 | 0 | 9 | 837,462.000 |

Censoring by arm: `{"A": {"MODEL_NONCOMPLETION": 4, "PROVIDER_CENSORED": 1, "VALID_SUBMISSION": 10}, "B": {"MODEL_NONCOMPLETION": 3, "VALID_SUBMISSION": 12}, "C": {"MODEL_NONCOMPLETION": 5, "PROVIDER_CENSORED": 2, "VALID_SUBMISSION": 8}, "D": {"MODEL_NONCOMPLETION": 5, "PROVIDER_CENSORED": 1, "VALID_SUBMISSION": 9}}`.

Actually served model/provider routing: `{"note": "Default OpenRouter routing policy is common to arms; actually served provider may vary stochastically and is reported, not treated as a factorial arm.", "provider_wait_s_by_arm": {"A": 4879.05176768429, "B": 4048.0609026205457, "C": 5016.566482827002, "D": 6191.6057239495785}, "served_models": {"z-ai/glm-5.3-flash": 1167}, "served_providers_by_arm": {"A": {"DeepInfra": 1, "InferenceNet": 2, "Morph": 7, "OpenInference": 65, "Phala": 13, "Wafer": 241}, "B": {"DeepInfra": 2, "InferenceNet": 9, "Morph": 1, "OpenInference": 52, "Phala": 14, "Wafer": 179}, "C": {"InferenceNet": 13, "Morph": 1, "OpenInference": 64, "Phala": 26, "Wafer": 202}, "D": {"DeepInfra": 1, "InferenceNet": 14, "Morph": 6, "OpenInference": 68, "Phala": 13, "Wafer": 173}}}`.

Capability: submitted `{'A': 10, 'B': 12, 'C': 8, 'D': 9}`; valid `{'A': 10, 'B': 12, 'C': 8, 'D': 9}`; mean modification on valid outputs `{'A': 0.70118, 'B': 0.68875, 'C': 0.6910375, 'D': 0.8361888888888889}`; mean regression `{'A': 0.97923, 'B': 0.9798, 'C': 0.98825, 'D': 0.994}`. Formal equivalence: **NOT ESTABLISHED**.

Factorial mean log effects (secondary): `{"H_at_S0": -0.33638204215777523, "H_at_S1": -0.08950386213824019, "S_at_H0": -0.07754438391070291, "S_at_H1": 0.16933379610883215, "interaction": 0.24687818001953504}`. Helper adoption: `{"A": {"helper_mention_calls": 0, "invocation_syntax_by_type": {}, "runs_with_helper_mention": 0, "runs_with_invocation_syntax": 0}, "B": {"helper_mention_calls": 4, "invocation_syntax_by_type": {"search": 6}, "runs_with_helper_mention": 1, "runs_with_invocation_syntax": 1}, "C": {"helper_mention_calls": 0, "invocation_syntax_by_type": {}, "runs_with_helper_mention": 0, "runs_with_invocation_syntax": 0}, "D": {"helper_mention_calls": 0, "invocation_syntax_by_type": {}, "runs_with_helper_mention": 0, "runs_with_invocation_syntax": 0}}`. Helper mentions alone do not prove backend invocation or mechanical displacement.

## Task-level ratios

| Task | A input | B input | C input | D input | D/A | A status | D status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Template:16_07 | 68,819 | 55,568 | 56,086 | 55,831 | 0.811 | SUBMITTED | SUBMITTED |
| Template:06_02 | 36,509 | 25,312 | 827,565 | 86,100 | 2.358 | SUBMITTED | SUBMITTED |
| Template:16_08 | 4,812 | 16,261 | 8,052 | 16,692 | 3.469 | PROVIDER_CENSORED | MODEL_NONCOMPLETION |
| Template:01_05 | 150,528 | 54,527 | 151,637 | 43,978 | 0.292 | SUBMITTED | SUBMITTED |
| Template:04_04 | 191,814 | 26,604 | 19,391 | 24,153 | 0.126 | SUBMITTED | SUBMITTED |
| Financial_Model:02_04 | 98,268 | 104,378 | 76,684 | 202,754 | 2.063 | SUBMITTED | SUBMITTED |
| Financial_Model:18_05 | 151,902 | 135,044 | 114,856 | 103,132 | 0.679 | SUBMITTED | SUBMITTED |
| Financial_Model:02_05 | 88,722 | 104,004 | 103,066 | 97,842 | 1.103 | SUBMITTED | SUBMITTED |
| Financial_Model:15_03 | 1,682,032 | 1,682,757 | 1,635,616 | 1,214,042 | 0.722 | MODEL_NONCOMPLETION | MODEL_NONCOMPLETION |
| Financial_Model:09_02 | 356,349 | 216,098 | 190,956 | 344,038 | 0.965 | SUBMITTED | SUBMITTED |
| Debugging:04_07 | 1,229,271 | 667,037 | 1,595,231 | 902,434 | 0.734 | MODEL_NONCOMPLETION | SUBMITTED |
| Debugging:07_05 | 675,750 | 295,103 | 217,940 | 949,105 | 1.405 | SUBMITTED | MODEL_NONCOMPLETION |
| Debugging:09_03 | 1,422,888 | 1,345,963 | 1,605,088 | 1,124,509 | 0.790 | MODEL_NONCOMPLETION | MODEL_NONCOMPLETION |
| Debugging:06_10 | 646,091 | 921,654 | 325,521 | 908,078 | 1.405 | SUBMITTED | MODEL_NONCOMPLETION |
| Debugging:01_04 | 1,154,739 | 1,462,459 | 1,412,769 | 1,464,470 | 1.268 | MODEL_NONCOMPLETION | MODEL_NONCOMPLETION |

## Discovery adjudication

Primary verdict: **TOKEN_EFFECT_TRAJECTORY_NOISE**. Gate details: `{"D_vs_A_median_reduction_ge_10pct": true, "capability_guard_interpretation": "Cannot affirmatively establish preservation: D had 9 valid submissions versus A's 10, with two A-only and one D-only valid submissions, and mixed paired modification deltas. No reproducible degradation is proven either.", "capability_guard_pass": false, "coherent_mechanism": false, "component_material": true, "component_material_descriptively": true, "component_mechanism_identified": false, "discovered": false, "favorable_two_families": true, "helper_mechanism_supported": false, "holdout_validation_justified": false, "interaction_supported": false, "not_one_or_two_pathological_tasks": false, "primary_verdict": "TOKEN_EFFECT_TRAJECTORY_NOISE", "reason": "D/A E2 median clears 10% narrowly but reverses after omitting two extreme Template tasks; its CI crosses 1, Debugging median is adverse, helper adoption is one B run and zero D runs, observation burden does not fall, and capability preservation is not established.", "salience_mechanism_supported": false, "verdict_scope": "The observed paired token movement is mixed and dominated by trajectory length and two Template tasks. This is not proof that every product-facing effect is zero."}`.

The result is frozen regardless of direction. No representative holdout was run; any product refinement requires independent forensic diagnosis, a new RC/profile identity, a fresh discovery cohort, and a new preregistration.

The strongest current external token claim remains none. Earlier lower-token totals are descriptive; a prompt effect here, if supported, would be an effect of the product-facing inspection strategy, not of the invisible runtime.

## Analysis audit and integrity

The preregistration and 60 primary outcomes remain frozen. The official scorer was not rerun for this correction. 30 submitted workbooks were initially marked invalid because the evaluator's `error_message` also reports ordinary cell mismatches. All **39 submitted workbooks** reached the scorer as valid workbooks; this does not mean their edits were correct. E1, E3, censoring, and capability summaries were recomputed from the archived official scores.

The append-only provider ledger has 1175 successful call rows, including 8 from an interrupted, incomplete block. The 1167 final call rows reconcile exactly to the frozen primary task totals. The raw ledger and primary hashes are preserved. An earlier historical-summary omission was corrected after preregistration without changing selection or the live design. See `analysis_audit.json`, `primary_freeze.json`, and `historical_normalization_correction.json`.

The helper factor exposed the existing Python module and an 83-token local-estimate addendum; the provider tool schemas did **not** change. Thus H identifies that *combined availability-and-description profile*, not an isolated tool-schema effect. The S notes were matched at 38 local cl100k tokens each; this is not model-native token matching.

## What the primary effect actually shows

D/A has an E2 median ratio of **0.888** (11.2% lower) in 14 uncensored pairs, but the geometric-ratio bootstrap interval is **0.563–1.212**, crossing no effect. Only 8/14 pairs favor D. Removing two extreme Template pairs (`Template:01_05`, `Template:04_04`) changes the median to **1.034** and geometric ratio to **1.096** across the other 12 pairs. Template favors D; Financial_Model is near even; Debugging favors A. The preregistered robustness gate therefore fails.

B/A is lower in this sample (median ratio **0.848**, 9/14 favorable; secondary geometric-ratio interval **0.502–0.939**), but helper execution occurred in only one B run and no D run. It cannot be described as helper-driven token saving. C/A is near neutral (median **0.972**) and D/C is modest (median **0.949**), both with wide intervals. The factorial interaction has a mean multiplicative ratio near **1.28** with a wide interval crossing no interaction.

## Trajectory and observation mechanism

D used **275 calls** versus A's **329**; aggregate input per call increased from **24,190** to **27,408** provider tokens. Across 14 uncensored D/A pairs, the geometric call-count ratio is **0.821** and per-call input ratio is **1.041**. Lower total input is principally fewer calls, not lighter calls. The paired path and per-arm cache/cost accounting are in `mechanism_adjudication.json`.

Broad `view_xlsx` calls fell from **39 (A)** to **12 (D)**, but model-visible observation bytes rose from **957,611** to **1,008,265**, and Python stdout rose from **284,513** to **685,468** bytes. C likewise had fewer broad views but greater observation and Python-output burden than A. Cumulative prior-observation bytes summed across requests fell in D only because there were fewer requests; mean prior-observation bytes per D call was higher. The hypothesized `fewer fat workbook observations → smaller per-call input` path was **not observed**. The syntactic inspection classifiers do not establish semantic usefulness.

One B run (`Financial_Model:09_02`) made four `lx_helpers.search` command calls: one failed and three returned exit status 0. Transcript review shows only the final command clearly printed cell hits; an earlier successful command iterated the result object's keys. The initial alias-blind classifier missed these calls. No D run invoked a helper. That B run also continued with broad Python output, so actual displacement of larger inspection work is not mechanically established. Helper availability may have changed the model's plan or trajectory without invocation, but this study cannot isolate that from the note itself.

## Completion, scores, and commercial burden

Valid submissions were **A 10, B 12, C 8, D 9**. D/A has two A-only and one D-only valid submission; C's `Template:06_02` even produced an exact workbook but never submitted it after consuming 827,565 input tokens. Model noncompletion is an outcome, not censoring. On eight dual-valid D/A pairs the median input ratio is 0.888, with a wide interval; modification deltas are mixed, including two lower-scoring low-token Template outputs. No formal capability equivalence or capability-preserving token claim follows.

E3 provider input tokens per valid submission: **A 795,849; B 592,731; C 1,042,557; D 837,462**. This discovery-only ratio uses all attempted-slot input and is not a prospective cost estimate. D had fewer total reported input tokens than A but **more uncached input tokens** (856,031 vs 788,581), more output tokens (165,158 vs 130,269), and higher provider-reported cost in these calls ($0.295 vs $0.281). No cost-saving claim is supported.

No targeted replication was run. Eligible pathologies and the decision are recorded in `replication_decision.json`: The primary result is already frozen and fails the mechanism and robustness gates. Targeted repeats could diagnose pathologies but cannot rescue this preregistered discovery gate or turn this cohort into holdout validation.

## My findings and opinion

The most diagnostic result is the mismatch between the visible behavior shift and the proposed token path. The salience wording changed *which interface* carried inspection—fewer `view_xlsx` calls, more Python output—but did not reduce bytes shown to the model or input per call. That is a useful product-design finding, but it is not the advertised token mechanism.

The B/A reduction deserves forensic attention because it appeared without broad helper adoption and with better completion counts. I would treat it as a possible effect of the helper *description or availability* on trajectory planning, not as evidence that the helper implementation saved tokens. It may also be stochastic: two Template tasks strongly influence the paired result, and the cohort was selected for headroom. The current four-arm design cannot distinguish these explanations.

My verdict is deliberately conservative: `TOKEN_EFFECT_TRAJECTORY_NOISE` means the combined D/A product-surface effect is not stable or mechanistically identified here; it does **not** prove that a future, narrower integration cannot save tokens. The capability guard did not affirmatively pass, but the small discordances and mixed scores do not establish a reproducible treatment degradation either. The first loss boundary is the absence of a lower per-call observation burden, followed by concentration in two Template trajectories.

## Next action

Independent GPT-6 Astra forensic review of the frozen packet; no live treatment or holdout calls. The 30 reserved validation tasks remain untouched. A later refinement, if justified, needs a new integration-profile identity, fresh discovery tasks, and a new preregistration; do not tune this RC against the reserved holdout.

## Summary of findings

The combined product-facing profile produced an 11.2% lower median provider-input count in the uncensored discovery pairs, but that result is concentrated in two Template tasks, lacks a stable cross-family effect, and has no affirmative capability guard. Salience reduced broad views without reducing observation bytes or per-call input. Helper use occurred in one B run and none in D, so helper execution is not the identified cause. The primary verdict is `TOKEN_EFFECT_TRAJECTORY_NOISE`; no token or cost claim is ready. Independent Astra review of the frozen packet is the next step, with the representative holdout still untouched.

## Final synthesis

### HISTORICAL EVIDENCE

Earlier lower totals were heterogeneous and confounded. The [historical note](../history/token_claim_discovery/historical_research_note.md) and [task-arm reconstruction](../history/token_claim_discovery/historical_token_summary.json) preserve available token splits, calls, observations, completion, and provenance.

### PREREGISTERED DESIGN

The 15-task, five-per-family, 2×2 profile study was frozen at SHA-256 `9acaec8ccdb6a51161eeee6488059b043d0a92893a0ba0a5b907fd7c67f5e0d4`. Its paired log-ratio variance estimate was 1.027 from a different prior intervention; the study was directional discovery, not powered 10% confirmation. S notes were 38 local tokens each; H added about 83 provider first-request tokens and bundled helper description with availability.

### LIVE EXPERIMENT INTEGRITY

All 60 slots ran; 1,167 selected successful provider calls reconcile to primary totals. Four provider-censored slots remain censored, and model noncompletion remains an outcome. Reference openpyxl execution, scorer, and provider tool schemas were common. Served providers varied despite common routing. The later study's frozen stop rule now closes this token-profile line.

### TOKEN EFFECT

D/A E2: 14 uncensored pairs, median ratio 0.888, arithmetic mean 1.052, geometric mean 0.854, 95% task-bootstrap geometric interval 0.563–1.212, 8 favorable and 6 unfavorable. The [task table](../history/token_claim_discovery/task_level_token_effects.json) and [family contrasts](../history/token_claim_discovery/family_level_token_effects.json) provide all ratios.

### COMPLETION-AWARE EFFECT

D/A E1 has eight dual-valid pairs, median 0.888, mean 1.050, geometric mean 0.754, interval 0.388–1.359. A had 10 valid submissions and D 9; two were A-only, one D-only. E3 tokens per valid submission were A 795,849 and D 837,462. No score-qualified threshold was preregistered.

### SALIENCE EFFECT

C/A E2 median input ratio 0.972 with interval 0.517–1.823; D/B median 0.993. Neither provides a stable salience saving.

### HELPER EFFECT

B/A E2 median ratio 0.848; D/C 0.949. Only one B run made factual helper calls; D made none. The H effect is a description-plus-availability profile, not identified helper-execution savings.

### INTERACTION

The mean log interaction was 0.247, multiplicative ratio 1.280, with bootstrap log interval −0.312 to 0.829. It is imprecise and does not identify synergy.

### INSPECTION BEHAVIOR

Broad views fell from 39 in A to 12 in D, while visible observation bytes rose from 957,611 to 1,008,265 and Python stdout rose from 284,513 to 685,468 bytes.

### HISTORY GROWTH

D used 275 calls versus A's 329; input per call rose from 24,190 to 27,408. On uncensored pairs, geometric call ratio 0.821 and per-call input ratio 1.041 explain the total ratio 0.854. Smaller accumulated observation history per request was not observed.

### CAPABILITY GUARD

Formal equivalence was not established. Completion discordance and mixed score deltas prevent an affirmative preservation claim. D's uncached input and provider-reported cost exceeded A's despite lower total input.

### CAUSAL MECHANISM

The predicted chain from fewer large views to smaller observations and lower per-call input failed. The earliest observed divergence is inspection-tool choice; later token movement mainly follows task-specific call-count divergence. No component earns causal credit for a reproducible token reduction.

### CONTRADICTORY EVIDENCE

Removing two extreme Template tasks changes D/A median ratio to 1.034. Debugging trends adverse; salience increases total visible bytes; helper adoption is near zero. A later fresh affordance study failed to reproduce a robust shippable profile and executed no factual helpers. Two reserve tasks had older, different-architecture H1 traces before reservation, a future validation-integrity caveat.

### PRIMARY VERDICT

`TOKEN_EFFECT_TRAJECTORY_NOISE` for the frozen 2×2. The later independent study concluded `TOKEN_PRODUCT_EFFECT_NOT_ROBUST` and stopped this profile line.

### REPRESENTATIVE VALIDATION DECISION

`IS_REPRESENTATIVE_CLAIM_VALIDATION_JUSTIFIED: NO`. The 30-task reserve received no new treatment in these studies. No integration component qualifies for claim validation.

### SINGLE NEXT ACTION

Preserve the negative studies and keep the representative reserve closed. No wording, helper, or runtime refinement is justified by this record.
