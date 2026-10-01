# Token-claim forensic review

This is a post-hoc review of the frozen [token diagnosis packet](ASTRA_TOKEN_DIAGNOSIS_PACKET.md), including its later affordance-induced verification question. It uses only the original 60 primary runs and their archived requests, tool events, transcripts, and official scores. No model call, scorer run, replication, product change, or holdout analysis was performed. The preregistered discovery verdict remains `TOKEN_EFFECT_TRAJECTORY_NOISE`.

## Verdict

**B's lower call count is observable; an affordance-induced reduction in redundant verification is not identified.** B used fewer calls than A in 10 of 14 uncensored task pairs, and fewer post-edit read/recalc operations in 7 of 9 dual-submitted pairs. The latter difference is heavily concentrated in two Template trajectories with many A-side edit/recalc loops. B did **not** consistently reach its first recorded workbook save earlier, and its submit gap after the last save had the same median as A. There is no direct evidence that the missing checks were redundant, that the model had greater confidence, or that actual helper availability rather than its extra note caused the behavior.

The strongest causal contrast in the frozen design is **the bundled B/A profile**: helper import availability *plus* an 83-token local-estimate addendum describing it. Because those changed together, no comparison isolates availability, an affordance cue, textual priming, or credible queryability. B's one helper-using run cannot explain the cohort-wide effect; the 13 uncensored B/A pairs without helper invocation still have a median B/A input-token ratio of **0.889**, but excluding the adopter is a post-treatment descriptive slice, not a randomized causal contrast.

## Evidence integrity and classification method

The preregistration, primary-run ledger, raw call ledger, and RC hashes remain unchanged. One additional accounting correction emerged during review: the global append-only `mechanism_events.jsonl` contains **1,166** tool events, including eight from the interrupted partial block. The completed primary runs' own `events.jsonl` files contain **1,158** selected tool events. The [trajectory classification](token_claim_review/trajectory_classification.jsonl) and [summary](token_claim_review/affordance_trajectory_review.json) use the latter; the raw ledger is retained. Corrected model-visible observation bytes are A **952,760**, B **986,419**, C **997,021**, D **1,003,414**. The packet's corresponding totals each include one superseded 4,851-byte observation. This small correction does not change the direction of the observation-burden finding.

Classification is deliberately conservative. A successful `wb.save(...)` shell command is a **recorded-save proxy**, not proof of the first semantic edit or of a correct final solution. An `openpyxl.load_workbook(...)` command is a workbook-open proxy, not automatically a reread of the same facts. Repeated exact `view_xlsx` targets, identical read commands, and identical visible observations establish repetition but not uselessness. A save followed by a workbook read or LibreOffice recalc establishes an **edit/check loop**, not redundant checking. Commands that combine editing, recalc, and inspection remain `other / ambiguous` where their purpose cannot be separated. “Required edit already mechanically complete” cannot be recovered from the trajectory without task-specific state snapshots; inspection after the final recorded save is reported only as a weaker proxy.

The ten requested activity labels were applied only where mechanically defensible. Initial sheet listing is navigation; first observed reads are new-evidence inspection; explicit assertions/checks before a save are pre-edit verification; subsequent workbook reads or recalc after a save are post-edit verification/reopen proxies; exact repeated views with visible formulas are repeated-range inspection. Many shell commands are ambiguous, and the classifier's absence of a category is **not** evidence that the behavior did not occur. The classifier does not infer confidence, intent, or the model's internal policy.

| Observable measure | A | B | Interpretation |
| --- | ---: | ---: | --- |
| All-arm model calls | 329 | 257 | B lower; 10/14 uncensored paired tasks have fewer B calls. |
| Recorded workbook-save commands | 39 | 23 | B has fewer edit/check iterations in aggregate. |
| LibreOffice/recalc commands | 28 | 16 | Concentrated in iterative Template work. |
| Workbook-open commands | 142 | 99 | Absolute count lower; open-per-call direction is mixed across paired dual submissions. |
| Post-edit read/recalc proxies | 72 | 34 | Includes useful validation and iterative repair. |
| Exact repeated `view_xlsx` targets | 10 | 0 | Eight A repeats are one noncompleting Financial_Model task. |
| Identical visible observations | 28 | 12 | Includes stalls/retries; not a redundancy census. |
| Model-visible observation bytes, corrected | 952,760 | 986,419 | B did not reduce total observation burden. |

On the **nine dual-submitted A/B pairs**, A has 146 model calls and B 98; post-edit read/recalc proxies are **55 vs 20**, with B lower in 7 pairs, equal in 1, and higher in 1. The two Template tasks `01_05` and `04_04` account for **27 of the 35** fewer B post-edit operations and **17 of the 19** fewer B edit/check loops. This is a local behavioral pattern, not a cross-family mechanism. The dual-submitted median first-save call is **A 7, B 8** (B earlier in 5 pairs, equal in 2, later in 2). The median number of calls from final save through submit is **2 in both arms** (B shorter in 3, equal in 5, longer in 1).

The original token decomposition also points to trajectory length: in 14 uncensored B/A pairs the geometric call-count ratio is **0.754**, versus **0.937** for provider input tokens per call. In aggregate B made 257 calls versus A's 329, while aggregate input per call was **27,676** in B versus **24,190** in A. The B/A median total-input ratio is **0.848**. This is an arm-level resource observation, not proof of the verification mediator.

## Answers to the affordance-induced verification questions

| Question | Forensic answer |
| --- | --- |
| 1. Fewer verification/reinspection cycles? | **Fewer recorded edit/check and post-edit read/recalc cycles in absolute count**, especially in dual-submitted pairs. Their necessity is unknown. The largest difference is concentrated in two Template tasks. |
| 2. First mutation earlier? | **Not systematically.** The first successful save proxy has dual-submitted medians A 7 and B 8; five B runs are earlier, two tie, two are later. Actual first cell mutation may precede the save and is not logged separately. |
| 3. Submit sooner after final mutation? | **No material general difference.** Final-save-to-submit median is two calls in both arms. The final recorded save is a proxy, not a semantic completion certificate. |
| 4. Fewer reopens/rereads after facts observed? | B has fewer absolute workbook-open commands (99 vs 142), but A/B open-per-call direction is mixed on dual submissions (4 lower, 1 tie, 4 higher for B). The trace cannot tell whether two different commands retrieved the same relevant fact. |
| 5. Repeated reads of the same cells/ranges/facts lower? | Strict exact-repeat evidence is sparse: among dual submissions, A has one repeated view target and three identical read commands; B has zero. Across all runs A's repeats are mostly a noncompleting Financial_Model loop. This cannot establish a systematic reduction in repeated **facts**. |
| 6. Less redundant checking or trajectory divergence? | **Trajectory divergence is the safer explanation.** B has fewer calls and shorter edit/recalc sequences, but many A-side iterations are candidate repairs or necessary recalculation, not provably redundant. Some fewer B checks coincide with lower workbook score. |
| 7. Correct-enough earlier without quality loss? | **Not established.** `Template:04_04` is one suggestive case: A 26 calls/15 saves, B 8 calls/4 saves, equal modification score. `Template:01_05` moves from A 19 calls/9 saves to B 10/3, but B's modification score is **0.320 lower**. Across nine dual-valid pairs the mean B−A modification delta is +0.018 with large opposing task effects; formal equivalence is absent. |
| 8. Actual helper user different? | The sole helper-using B run, `Financial_Model:09_02`, has A 20 calls versus B 16; first save A 15/B 14; final-save-to-submit A 5/B 2; both score exactly. Yet both have **10** workbook-open commands, and B continues broad Python inspection after its helper calls. This one case does not identify displacement. |
| 9. Zero-helper B runs differ? | **Descriptively yes on call count:** among 13 uncensored A/B pairs without B helper invocation, B has fewer calls in 9, equal in 2, more in 2; median B/A input ratio is 0.889. First save and submit gap still do not show a systematic earlier-commitment pattern. This is a post-treatment subgroup. |
| 10. Best label? | **`NOT IDENTIFIABLE`** for the proposed *affordance-induced redundant-verification* mechanism. `HELPER EXECUTION` is ruled out as the cohort-wide explanation. `GENERAL TRAJECTORY VARIANCE` remains a compatible descriptive alternative; localized shorter edit/check loops are observed, not proven to be caused by affordance. |

## Case-level checks and supporting contrasts

`Template:04_04` is the strongest local “shorter iteration” case: first save occurs at call 3 in both arms; A then repeatedly edits and recalculates through call 25, while B's last save is call 7. Both submit one call after their last save, with the same modification score. The difference is **after first save**, not an earlier first commitment. `Template:01_05` has the same first-save call (5), but A makes six more save commands and finishes with a higher modification score. These two cases account for most of the edit/check-loop difference, and they point in different quality directions.

`Financial_Model:15_03` supplies eight of A's ten repeated exact view targets; **neither arm submitted**. It is evidence of a repetitive A trajectory, not evidence that B safely omitted redundant verification. In `Debugging:04_07`, A hit the call cap without submitting while B submitted; the large call reduction is completion divergence. The helper-using `Financial_Model:09_02` is qualitatively different from B's nonuser cohort, but is one treated case with no matched helper-free replay.

C/D supports caution. D/C has a median input-token ratio of **0.949** across 13 uncensored pairs and a median call-count ratio of **0.909** (D lower in 7, higher in 5, tied in 1). Neither D nor C invoked a helper, but D's post-edit read/recalc proxy total is **28**, the same as C's. The helper-description effect is therefore not consistently expressed as fewer post-edit checks under salience. The factorial interaction estimate is wide and crosses no effect.

## Responses to the original twelve review questions

1. **Identified mechanism?** No. Randomized paired contrasts can estimate bundled arm effects in this enriched cohort; mediator claims are post-hoc and confounded by trajectory and completion.
2. **Strongest causal contrast?** B/A for the bundled helper-description-plus-availability profile. Its input and call-count reductions are stronger than C/A or D/C, but helper execution is not the cause established by that contrast.
3. **Completion/censoring/calls?** Provider-censored pairs were excluded from paired E2. B submits more often than A (12 vs 10 overall), so B's lower tokens are not simply premature failure. Fewer calls explain much of B/A, while D/A is completion-fragile and concentrated.
4. **Salience as product effect or prompt artifact?** A reproducible shipped note could be a legitimate product effect. Here C/A median input reduction is only 2.8%, with a wide interval and no reduced observation burden; support is absent.
5. **Helper displacement?** Not mechanically established. One B run invoked `search`; only its final helper command clearly printed cell hits, and broad Python inspection continued.
6. **Factorial decomposition?** Log contrasts are computable, but the H factor bundles text and importability, the interaction is imprecise, and no stable causal mediator is isolated.
7. **Gate calibration?** Appropriate to reject a public claim here, but the phrases “material component,” “pathological concentration,” and “capability guard” need numeric definitions in a fresh preregistration. A passing discovery gate alone would still require holdout validation.
8. **Earliest loss boundary?** For the original token mechanism, broad views did not translate into lower visible observation bytes or per-call input. For the new affordance hypothesis, treatment construction never separated a textual cue from actual availability; first-save timing and submit-gap evidence then fail to support a general earlier-commitment account.
9. **Smallest justified product refinement?** None from this record. Do not ship a stronger helper prompt, change helper behavior, or tune against the reserved cohort based on this review.
10. **What must remain unchanged?** The RC, reference-openpyxl helper backend, Candidate A eligibility, capture/freshness semantics, model-facing architecture, and untouched validation reservation. No architecture branch reopens.
11. **Fresh discriminating experiment?** See the next section. It is a *new claim-discovery design*, not a rerun or public validation.
12. **Representative holdout now?** No. The primary D/A gate failed, and the affordance mediator remains unidentifiable.

## Smallest fresh test if the affordance lead is pursued

Freeze a **new integration-profile identity**, use fresh non-holdout tasks, keep the ordinary coding model and invisible runtime identical, and preregister call count, first save, edit/check loops, post-final-save gap, repeated exact reads, valid submissions, and official scores. A compact design needs to separate the text from actual availability:

| Profile | Model-visible cue | Helper importable? | Purpose |
| --- | --- | --- | --- |
| Control | None | No | Baseline. |
| Generic lookup | Precise factual lookup through ordinary Python is available | No helper | Tests generic inspection wording. |
| Helper cue only | Conditional description of a possible helper | No | Tests textual cue without actual access; any failed attempted call counts against it. |
| Silent availability | None | Yes | Tests whether availability matters without announced affordance; effect before discovery should be absent. |
| Announced availability | Same helper cue | Yes | Tests cue plus real access. |
| Demonstrated queryability | Same cue plus a neutral successful import/status observation | Yes | Tests credible ability to query, distinct from an unverified claim. |

Keep wording, placement, and token length matched as closely as possible; log failed helper attempts, actual helper calls, and workbook quality. The “cue only” wording must be truthful (for example, that a helper *may* be available and should be checked before use), or any explicit sham must be marked as diagnostic and failures retained. A silent installed module cannot change the agent's behavior until the agent discovers it; that is a useful falsification condition. Analyze all six profiles on fresh paired tasks rather than selecting B nonadopters after treatment. No representative holdout should be opened until a stable mechanism and capability guard pass on a fresh discovery cohort.

## My opinion

There is a real-looking **shorter iterative editing pattern in some B trajectories**, and it is more interesting than the near-absent helper execution. But the record does not tell us that the model “felt able to check later” or that the omitted checks were redundant. The strongest B cases are ordinary task-specific path changes: one preserved quality, another lost substantial modification accuracy. The affordance story is a plausible next *hypothesis*, not an earned product mechanism. I would preserve the current negative/mixed verdict, perform the fresh separation experiment only if token efficiency remains a priority, and keep the representative holdout sealed.

## Summary of findings

B made fewer model calls and fewer post-edit read/recalc operations, including in runs with no helper invocation. First-save and final-save-to-submit timing do not show a general earlier-commitment effect. Most of the observable reduction in edit/check loops comes from two Template tasks, with mixed quality. Actual helper execution cannot explain the cohort effect, and the frozen design cannot separate affordance from textual priming or stochastic trajectory differences. **Affordance-induced reduced redundant verification is not identified; holdout validation is not justified.**
