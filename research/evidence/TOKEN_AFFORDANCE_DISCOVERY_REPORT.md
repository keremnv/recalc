# Fresh factual-lookup affordance discovery

**Verdict: `TOKEN_PRODUCT_EFFECT_NOT_ROBUST`.** All 48 preregistered primary slots were attempted. Neither shippable profile C nor D met the discovery gate, and B did not reproduce the prior systematic reduction in model calls. No helper query executed. The reserved 30-task token-validation cohort remains unrun and unchanged. Architecture discovery and `PRODUCT_HYGIENE_RC` 0.2.0rc1 remain frozen.

This is a discovery result, not a proof that truthful lookup cues can never help. The current data do **not** identify a reliable causal token mechanism or justify representative token-claim validation. Provider routing and sparse completion materially limit interpretation. The next claim-specific work should address the independent read-acceleration lead, not tune another token profile against these tasks.

## Integrity and design

The [preregistered specification](../history/token_affordance_discovery/preregistered_spec.json) was hashed before inference (`6fada992333be6832fe89271f631ded4ac5d11f6c6499ac62181fc64738819c7`). The [primary freeze](../history/token_affordance_discovery/primary_freeze.json) hashes the original ledger, usage and event files, design artifacts, and all 2,850 run files. The 48 slots are unique, and 1,306 successful provider calls reconcile exactly with the run totals. All calls requested and were served `z-ai/glm-5.3-flash`; temperature was 0, `top_p` 1, and the bash/view/submit schemas were identical. The provider-routing *policy* was identical, but actual serving alternated between OpenInference and Wafer. [Request-level integrity](../history/token_affordance_discovery/experiment_integrity.json) and [provider routing](../history/token_affordance_discovery/provider_routing_analysis.json) preserve those facts.

The deterministic seed `20261007` selected four tasks per family using only historical control-side completion, interaction and token/call headroom. It excluded both the earlier 15 discovery tasks and the reserved 30 validation tasks. This `AFFORDANCE_DISCOVERY_FRESH_NONREPRESENTATIVE` cohort contains Template `01_07`, `15_01`, `06_12`, `15_03`; Financial_Model `01_01`, `04_03`, `03_03`, `02_01`; and Debugging `02_01`, `02_06`, `10_10`, `01_08`. The last two Debugging tasks had usable historical control interaction but no historical submission; the [selection manifest](../history/token_affordance_discovery/selection_manifest.json) exposes that limitation. The frozen task order used one concurrent four-arm block per task with rotated arm positions.

The four arm profiles were:

| Arm | Model-visible state | `lx_helpers` importable | Preflight |
| --- | --- | --- | --- |
| A | No lookup cue | No | None |
| B | Lookup might be available; verify before use | No | None |
| C | `lx_helpers` and three function names announced | Yes | None |
| D | Same as C | Yes | Actual import/function check reported before the first decision |

B's exact note was:

> Optional factual lookup capabilities may be available in some environments. If you choose to rely on one, verify that it is available before use. Ordinary Python/openpyxl remains fully available.

C/D's exact note was:

> Optional factual helpers are available through lx_helpers. Available functions: search(...), periods(...), inspect(...). You may import them if useful. Ordinary Python/openpyxl remains fully available.

Both had the same heading and were 42 local `cl100k_base` tokens. Provider first-request input differed from A by exactly 42 tokens for B and C on all 12 tasks. D used the C note plus a real, fact-free availability observation; its first requests were 63 provider tokens above A, or 21 above C. [Exact notes](../history/token_affordance_discovery/exact_notes.json) and [arm profiles](../history/token_affordance_discovery/arm_profiles.json) are frozen. A/B could not import the helper; C/D used the unchanged RC helper module with the reference-openpyxl backend. The invisible runtime, Candidate A, substrate serving and capture were disabled in every arm. Ordinary Python/openpyxl and the scorer were the same.

An identification limit was present in the frozen design: **C versus B bundles actual importability with a more specific truthful note** naming `lx_helpers` and its functions. It cannot isolate importability alone. D versus C more cleanly isolates the fact-free confirmation, including its fixed context overhead. No stronger model or Astra arm was used.

## Resource and capability results

Ratios below are treatment/control for **uncensored task pairs**. Values below 1 use fewer resources. The bootstrap intervals resample tasks, not calls; none establishes a public claim. The original runner labels and the corrected censoring analysis are both archived. The correction excludes two unfinished below-cap runs with logged provider timeouts; see [analysis correction log](../history/token_affordance_discovery/analysis_correction_log.json).

| Contrast | Pairs / dual-valid | Median input ratio | Geometric input ratio [95% bootstrap CI] | Lower-input tasks | Geometric call ratio | Median uncached ratio | Median reported-cost ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B/A — cue | 9 / 2 | 0.912 | 0.809 [0.350, 1.630] | 5/9 | 0.884 | 1.005 | 0.908 |
| C/B — announced availability | 9 / 3 | 0.971 | 1.018 [0.560, 1.863] | 6/9 | 1.033 | 0.977 | 1.005 |
| D/C — confirmed queryability | 10 / 2 | 1.104 | 1.164 [0.841, 1.630] | 2/10 | 1.039 | 0.966 | 1.059 |
| C/A — shippable announcement | 10 / 2 | 0.969 | 0.854 [0.651, 1.057] | 6/10 | 0.922 | 1.021 | 1.000 |
| D/A — shippable confirmation | 10 / 2 | 1.072 | 0.993 [0.731, 1.229] | 2/10 | 0.958 | 1.026 | 1.086 |

The paired model-call **median was 1.0 for every contrast**. In B/A, B made fewer calls on only 2 of 9 corrected uncensored pairs, the same number on 5, and more on 2. This does not replicate the earlier 10/14 lower-call pattern. B/A's two dual-valid pairs have a geometric **input ratio of 1.848**, because B was faster on Financial_Model `03_03` but much slower on Template `15_03`. C/A's two dual-valid pairs had a geometric ratio of 0.746, but two tasks cannot establish a general or family-spanning effect. D/A's two dual-valid pairs were approximately even (1.000).

| Arm | Provider input | Cached input | Uncached input | Output | Calls | Input/call | Provider-reported cost | Valid submissions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 10,683,925 | 9,740,619 | 943,306 | 53,502 | 367 | 29,112 | $0.3640 | 2/12 |
| B | 9,248,394 | 8,459,538 | 788,856 | 42,138 | 301 | 30,726 | $0.3111 | 3/12 |
| C | 10,003,587 | 9,140,592 | 862,995 | 43,894 | 321 | 31,164 | $0.3344 | 3/12 |
| D | 10,503,280 | 9,684,950 | 818,330 | 47,169 | 317 | 33,133 | $0.3472 | 2/12 |

These whole-arm totals are descriptive and include censored and noncompleted attempts; B had three provider-censored slots versus A's one. Around 91–92% of reported input was cached. Lower total input was **not proportional** to uncached input or provider-reported dollars: for example C/A's paired median input ratio was 0.969, while its median uncached ratio was 1.021 and median cost ratio approximately 1.000. The runner's estimated-cost caps also diverged sharply from provider-reported charges when cache hits were high. Financial_Model `01_01` A stopped at the preregistered **estimated** $0.25 slot cap although the provider reported about $0.05. Four arms on that task and four on Financial_Model `04_03` reached estimated-cost limits; these are noncompletion outcomes, not savings.

The official LibreOffice/evaluator path accepted every submitted workbook as valid. Submission counts were A 2, B 3, C 3, D 2. No submission scored exact. Mean modification among the *different* submitted sets was A 0.591, B 0.395, C 0.707, D 0.679; regression was near 1.0. Those unpaired means are not comparative capability estimates. In the two dual-valid B/A tasks, B improved modification on Financial_Model `03_03` (0.471 versus 0.373) but worsened it on Template `15_03` (0.429 versus 0.810). On Template `15_01`, B/C submitted while A/D did not; B's submitted modification was 0.286, C's 0.762. A/D had partial output workbooks, but their lack of submission remains noncompletion. This sparse, discordant record does not clear a capability-preservation guard for a token claim and is not formal equivalence evidence.

Descriptive provider input per valid submission was A 5.34 million, B 3.08 million, C 3.33 million, D 5.25 million. It divides all 12 attempts per arm by only 2–3 valid submissions, whose scores differ, so it cannot support a commercial token-to-success claim. [Official scores](../history/token_affordance_discovery/official_scores.json), [capability guard](../history/token_affordance_discovery/capability_guard.json), and [token-to-success](../history/token_affordance_discovery/token_to_success.json) contain task-level values.

## Observable trajectory and identification

The apparent B/A verification reduction is concentrated. Raw post-edit read/recalc proxies were A 62 and B 12, but A's total includes 32 on Template `06_12`, whose B run was provider-censored. Of the remaining prominent difference, Template `15_01` had A 25 post-edit proxies and 14 save commands versus B 0 and one; A did not submit and B's submitted edit scored 0.286. On the dual-valid Template `15_03`, the direction reversed: B had 10 post-edit proxies and three saves versus A one and one, submitted 13 calls later, and scored worse. On the dual-valid Financial Model `03_03`, B first saved at call 8 versus A call 12 and submitted three calls sooner, but had **more** post-edit proxies (2 versus 1). There is no systematic earlier first save or shorter final-save-to-submit interval on comparable tasks. Exact repeated read-command totals (A 34, B 10, C 10, D 22) and repeated-view targets (46, 34, 47, 37) are likewise dominated by unequal trajectories and noncompletion; they do not prove redundant checking was removed.

Total visible tool-observation bytes were very similar: A 1.171 million, B 1.162 million, C 1.181 million, D 1.185 million. Per model call they were **higher** in B/C/D (about 3,860/3,680/3,739 bytes) than A (3,191). Provider input per call was also higher in every treatment arm. Broad-view counts were A 62, B 57, C 72, D 53; B's Python stdout was larger than A's (508 KB versus 435 KB), and its whole-workbook-scan proxy was higher (86 versus 44). The hypothesized chain “credible lookup → fewer checks/fat observations → lower per-call input” is not mechanically supported by this cohort. The counts are syntactic proxies, not judgments about whether a check was necessary.

There were **zero actual `search`, `periods`, or `inspect` calls** in every arm and no helper displacement. One D run (Debugging `01_08`) imported the helper twice to inspect its API/source; it never queried workbook facts. B made no failed import attempt. Any profile difference here would be an affordance/cue/trajectory effect, not helper execution. The observed results do not establish such an affordance effect. [Trajectory events](../history/token_affordance_discovery/trajectory_events.jsonl), [verification summary](../history/token_affordance_discovery/verification_iteration_summary.json), and [helper adoption](../history/token_affordance_discovery/helper_adoption.json) retain the audit trail.

The strongest alternative explanation is **trajectory and provider variation**. On influential Template `15_01`, all arms began on OpenInference, but from call 2 B/C were served mainly by Wafer and submitted, while A/D stayed mainly on OpenInference and did not. Ten of 12 tasks had some unequal provider mix across arms despite a shared routing policy. We do not postselect provider-matched tasks to manufacture an effect. Original runner labels had provider-censored counts A 1, B 2, C 1, D 2. A documented taxonomy correction classified two additional unfinished below-cap runs with logged provider timeouts as censored, yielding A 1, B 3, C 2, D 2. In the original analysis C/A's extreme low-token Template `06_12` C run gave a geometric ratio 0.670; after correctly censoring its timeout-contaminated eight-call trajectory, C/A became 0.854 with median 0.969. Both versions remain archived.

Concentration also rejects a robust cue story. Corrected B/A geometric input ratio was 0.809, but **1.150 when Template `15_01` is left out**. B/A's largest unfavorable task, Template `15_03`, had a 5.686 input ratio and a lower modification score. C/A remains under 1 under leave-one-task-out, but its full median reduction is only 3.1%, call-count median is unchanged, and its favorable family summaries include noncompleted tasks. D/A is unfavorable in 8 of 10 uncensored pairs. [Family effects](../history/token_affordance_discovery/family_effects.json) and [concentration sensitivity](../history/token_affordance_discovery/concentration_sensitivity.json) show every task.

## Independent assessment

My reading is that this experiment decisively **fails to license a token product claim**, while it does not estimate a precise zero effect. The strongest apparent B saving comes from a task where A kept iterating, B submitted a weaker edit, and the served providers differed. The other cleanly dual-submitted Template task points the opposite way. C's aggregate geometric saving survives some leave-one-out checks, yet misses the predeclared median threshold and lacks the proposed call/observation mechanism. D's fact-free confirmation adds no reproducible value and is usually costlier than C. The estimated-cost cap and intermittent provider failures further reduce the number of comparable trajectories. No helper executed, so “helpers save tokens” is especially unsupported. These are reasons to stop token-mechanism chasing under the stated final-discriminator rule, not reasons to reopen architecture research.

The most that can be said externally is that this product retains ordinary Python/openpyxl and has a conservative optional runtime with reference fallback, supported within the frozen evidence scopes. This experiment supplies **no** public reduced-token, reduced-cost, or capability-equivalence claim. Read acceleration, fail-closed behavior, mutation assurance, and the ordinary interface have separate evidence and remain unaffected.

## Required answers

1. **Fresh population:** the 12 tasks listed above, four per family, seed `20261007`.
2. **Holdout:** untouched; its reservation hash still matches the preregistration.
3. **Profiles frozen:** yes, with exact notes, arm configs and run order hashed before inference.
4. **Note matching:** B/C/D shared placement and heading; B/C notes were each 42 local tokens and added exactly 42 provider tokens on first requests. D added a 21-provider-token confirmation over C.
5. **Runtime:** identical and disabled in all arms; helpers were reference-openpyxl only when importable.
6. **B/A:** median input ratio 0.912, geometric 0.809, 5/9 lower, call median 1.0; not robust.
7. **C/B:** median 0.971, geometric 1.018; no availability increment established.
8. **D/C:** median 1.104, geometric 1.164; confirmation did not help.
9. **C/A:** median 0.969, geometric 0.854; below the required 10% median reduction.
10. **D/A:** median 1.072, geometric 0.993; no useful reduction.
11. **Fewest model calls:** B by whole-arm descriptive total (301); paired call medians were equal in every contrast.
12. **Fewest total input tokens:** B (9.248 million), descriptively.
13. **Fewest uncached input tokens:** B (788,856), descriptively; paired B/A uncached median was 1.005.
14. **Lowest provider-reported cost:** B ($0.3111), descriptively.
15. **Input versus dollars:** not proportional; caching and output use differ, and reported charges diverged from the runner's uncached-blind estimate.
16. **First save:** no systematic earlier treatment timing on dual-valid pairs; B was four calls earlier on one Financial Model and equal on the dual-valid Template.
17. **Save/edit iterations:** B had fewer in one noncompleted A Template trajectory but more on a dual-valid Template; no general reduction.
18. **Post-edit checking:** aggregate B lower, concentrated in noncomparable or provider-confounded tasks; dual-valid directions conflict.
19. **Final save to submit:** no consistent treatment advantage; B was one call sooner on Financial Model `03_03` and one later on Template `15_03`.
20. **Repeated exact reads:** raw B lower, but not a robust paired or quality-preserving effect.
21. **Observation bytes:** essentially flat in total; higher per call in treatment arms.
22. **Helper attempts:** only one D run imported twice for API inspection; B made no failed attempt.
23. **Helper use:** zero factual helper calls.
24. **Execution explanation:** impossible; no helper execution occurred.
25. **Without helper use:** all observed differences occurred without factual helper execution, but none identified a robust affordance mechanism.
26. **Cue-only replication:** no; B had fewer calls in only 2/9 corrected uncensored pairs, with five ties.
27. **Availability increment:** not established; C/B is near 1, and wording specificity is bundled with importability.
28. **Demonstrated queryability increment:** not established; D/C generally worsened input use.
29. **Capability:** no formal equivalence; B had one material dual-valid modification loss, and completion was sparse/discordant.
30. **Premature termination:** several apparent savings came from deadline/cost-cap noncompletion or provider-contaminated runs and are not credited.
31. **At least two families:** descriptive geometric directions sometimes span two families, but not with adequate valid-workbook evidence; no capability-preserving family-general effect is established.
32. **Concentration:** B/A reverses when Template `15_01` is omitted; C/A's median misses threshold; D/A is mostly unfavorable.
33. **Best causal explanation:** not identifiable beyond model trajectory and provider-routing variance; no coherent lookup-induced verification mechanism was observed.
34. **`AFFORDANCE_EFFECT_DISCOVERED`:** failed for C and D.
35. **`CUE_EFFECT_SUPPORTED`:** failed.
36. **`AVAILABILITY_ADDS_VALUE`:** failed.
37. **`DEMONSTRATED_QUERYABILITY_ADDS_VALUE`:** failed.
38. **Token discovery:** stop under the predeclared final-discriminator rule; preserve results as descriptive evidence.
39. **Representative holdout:** not justified; do not open or run it.
40. **Frozen profile:** none for a token claim; product RC and architecture remain unchanged.
41. **Other claims:** conservative read acceleration, fail-closed fallback, mutation assurance, ordinary Python interface, and narrow cumulative capability evidence are unaffected.
42. **Single next action:** preregister independent RC-level conservative read-acceleration claim validation.

## Final synthesis

### EXPERIMENT INTEGRITY

48/48 slots; frozen design and RC verified; primary raw evidence hashed. The served model was constant, but actual providers varied.

### FRESH DISCOVERY POPULATION

Twelve nonrepresentative, control-headroom-selected fresh tasks; no overlap with prior discovery or reserved holdout.

### A — CONTROL

No cue and no importable helper.

### B — CUE ONLY

Truthful possibility cue; helper unavailable; no import attempt or actual call.

### C — ANNOUNCED AVAILABILITY

Truthful named helper announcement and importability; zero factual helper calls.

### D — DEMONSTRATED QUERYABILITY

C plus fact-free successful preflight status; zero factual helper calls and one API-introspection run.

### B VS A

Median input ratio 0.912, geometric 0.809, 5/9 lower; call median 1.0 and leave-one-out reversal. Cue effect unsupported.

### C VS B

Median input ratio 0.971, geometric 1.018. Actual availability adds no demonstrated value; note specificity is bundled.

### D VS C

Median input ratio 1.104, geometric 1.164. Confirmation did not improve token use.

### C VS A

Median input ratio 0.969, geometric 0.854. The required 10% median reduction did not occur.

### D VS A

Median input ratio 1.072, geometric 0.993; 8/10 pairs used more input tokens.

### MODEL-CALL EFFECT

Whole-arm B used 301 calls versus A 367, but paired medians were tied and only 2/9 corrected B/A pairs had fewer B calls.

### TOTAL INPUT-TOKEN EFFECT

Whole-arm B total was lower, but paired and completion-aware evidence does not support a causal product claim.

### UNCACHED TOKEN EFFECT

Caching exceeded 91% in every arm; B/A paired median uncached ratio was 1.005 despite a lower total-input median.

### DOLLAR-COST EFFECT

B had the lowest descriptive provider-reported total ($0.3111), but no capability-preserving causal cost reduction was established.

### TRAJECTORY EFFECT

The earlier systematic B/A call-count pattern did not replicate; individual tasks diverged strongly.

### FIRST-SAVE EFFECT

No consistent earlier first save on comparable submitted tasks.

### EDIT / SAVE ITERATIONS

Large B/A reductions on one noncompleted, provider-confounded Template task reversed on a dual-valid Template task.

### POST-EDIT CHECKING

Raw A 62 versus B 12 proxies is concentrated in noncomparable tasks; it does not identify reduced redundant verification.

### FINAL-SAVE TO SUBMIT

No consistent treatment shortening on dual-valid pairs.

### HELPER ADOPTION

One D task inspected helper APIs; no factual helper was invoked in any arm.

### HELPER EXECUTION CONTRIBUTION

Zero; mechanical displacement cannot occur without execution.

### CAPABILITY GUARD

Only 2–3 valid submissions per arm, no exact successes, one large B/A dual-valid modification loss, and provider-confounded completion discordance. No equivalence claim.

### FAMILY GENERALITY

No robust quality-preserving effect across at least two families; Debugging had no valid submissions.

### OUTLIER / CONCENTRATION ROBUSTNESS

B/A geometric ratio becomes 1.150 without Template `15_01`; no favorable aggregate is robust enough for a claim.

### BEST CAUSAL EXPLANATION

No token mechanism identified. Provider assignment, truncation at frozen budgets, and trajectory variance are strong competing explanations.

### DISCOVERY GATE

`AFFORDANCE_EFFECT_DISCOVERED`, cue support, availability increment, and demonstrated-queryability increment all failed.

### TOKEN CLAIM STATUS

`TOKEN_PRODUCT_EFFECT_NOT_ROBUST`; token observations remain descriptive only.

### ACCELERATION CLAIM STATUS

Unchanged: conservative optional read acceleration has separate narrow evidence and needs its own RC-level claim test.

### OTHER CLAIMS UNAFFECTED

Fail-closed fallback, mutation assurance, ordinary Python/openpyxl interface and scoped capability evidence retain their prior statuses.

### WHETHER HOLDOUT VALIDATION IS JUSTIFIED

No. The reserved 30 tasks remain sealed.

### TOKEN-DISCOVERY STOP RULE

Triggered. Do not tune and rerun another token mechanism profile against discovery or holdout tasks.

### SINGLE NEXT ACTION

Preregister an independent RC-level conservative read-acceleration claim-validation test.
