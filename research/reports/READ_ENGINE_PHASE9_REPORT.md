# Read Engine Phase 9 — reference-only transparency and pay-for-play activation

Status: completed offline experiment; **no public product integration or claim change**. The complete scored run used the frozen Phase-8 representative 30 and five changed-file fixtures. It is a same-run, full-command PY/H0/H1 comparison, not a claim that LibreCalc accelerates every task. Raw evidence and the paired analysis are in [`read_engine_phase9/`](../../read_engine_phase9).

## PHASE 8A EVIDENCE CARRIED FORWARD

Phase 8A repaired the merged-cell certificate's false positive with a restricted positive grammar. Its 69 adversarial cases, 15 mutations, fixed-22 regression, representative correctness, and changed-file correctness passed. On the fixed 22 contact-selected scripts, Phase 7 warm H1/PY was 0.513 with 18/22 faster; cold was 1.194. None of those frozen results was rerun or reinterpreted here. Phase 8A found 22/30 representative scripts reference-only and measured a +22.0 ms reference-only second-command excess. Phase 9 addresses that non-contact tax only.

The original Phase-9 preregistration SHA-256 is `68c786a73d3ea510ec1216247725dfb3e3ac10ad92d3cd171e3b1da49a03563a`. Six [numbered amendments](../../read_engine_phase9/PREREGISTERED_SPEC_AMENDMENT_1.md) after it recorded fixture, gate, staging, and assurance-order corrections **before the eligible scored run**. Failed gate attempts and the interrupted partial score are archived under distinct `attempt` names and excluded from analysis. The treatment, frozen identities, endpoints, repetitions, and decision thresholds were unchanged. The final process, 30-script, five-write, and abrupt-exit gates passed before the complete scored run.

## REFERENCE ONLY LOSS BOUNDARY

All 22 reference-only programs were rejected by the unchanged whole-script classifier before artifact discovery: 14 for cell-object iteration, four for static analysis uncertainty, three for rich-object access, and one for worksheet-collection access. Frozen H0 nevertheless imported artifact/certificate/runtime modules, initialized real openpyxl, and installed a reference-delegating patch. It then performed no direct serving. The [pre-treatment review](../../read_engine_phase9/REFERENCE_ONLY_ARCHITECTURE_REVIEW.md) records each workload and its actual rejection reason.

The native observer's pre/post read-only work was sub-millisecond in the diagnostic profile. The main unnecessary category was direct-runtime activation after an authoritative negative admission decision. Import timing alone was not a valid estimate of recoverable full-command time because these scripts still import real openpyxl themselves.

## INDEPENDENT PAY FOR PLAY ARCHITECTURE REVIEW

The [architecture decision](../../read_engine_phase9/ARCHITECTURE_DECISION.md) compared early definite-reference bypass, a first-contact loader, deferred import interposition, negative-admission caching, and observer-side classification. The existing classifier already supplies the earliest authoritative negative decision for this population. First-contact hooks would change import/module behavior, while cache or observer classification would add a trust boundary. The lowest-surface test was therefore to stop direct-runtime activation after classifier rejection, preserving the existing direct path for admitted scripts.

## SELECTED FAST PATH

H0 is the **frozen Phase-8A candidate**: thin native observer, real Python script process, guarded sitecustomize, hardened merged-cell certificate, safe persistent artifact, direct runtime and reference fallback. H1 changes only the rejected-source bootstrap branch. It keeps script identity guard, config and unchanged classifier, writes a truthful route receipt, leaves `openpyxl.load_workbook` unpatched, and lets the byte-identical script use ordinary reference openpyxl. It skips parent-artifact/certificate/direct-runtime imports and installation. An admitted script follows the frozen Phase-8A direct path.

H1's `FAST_PATH_PROVEN_REFERENCE` witness means a classifier rejection and no installed direct runtime. It is **not** a claim that the script made zero reference workbook loads: those calls are no longer intercepted or counted on that branch.

## ROUTING AUTHORITY

The routing rule is the frozen whole-script classifier's `A1_ADMIT` decision, applied to current source bytes and config. A decision other than `A1_ADMIT` already forced H0 to reference openpyxl; H1 merely avoids constructing an unused interception layer. Historical route labels, workload IDs, task families, workbook sizes and measured runtimes do not enter H1. Uncertain source remains on reference execution. Admission and the merged-cell certificate are unchanged for admitted scripts.

## FAST PATH COVERAGE

The same-run outcome classification was 22 `REFERENCE_ONLY`, seven `DIRECT_CONTACT`, and one `FALLBACK_AFTER_CONTACT`. The general classifier rule proved the fast path for **22/22** reference-only scripts; zero were `REFERENCE_ONLY_BUT_UNCERTAIN`. The other eight entered `DIRECT_RUNTIME` and kept their existing contact/fallback routes. The five fixed write fixtures also took the rejected-source fast path; the external observer and changed-file helper remained active.

## PROCESS AND ASSURANCE SEMANTICS

All 22 focused process/module fixtures passed their accepted H0/PY comparison, including genuine `__main__`, argv/path, imports, output, exit, atexit, inherited FD, signals and abrupt termination. Two fixtures retained pre-existing PY-versus-observer module/path visibility differences; H1 introduced no new product-contract violation. On the proven-reference fixture, `openpyxl.load_workbook` and workbook objects were genuine reference objects. A separate initially misrouted identity fixture exposed the **inherited admitted direct-path** patched-function identity difference; it is not a fast-path exactness claim and remains a known narrow-interface limit.

The observer still starts before the real script interpreter, observes XLSX state before and after, survives target death, runs the capture helper on mutation, and records raw termination status. H1 does not use `runpy`, remove capture, or bypass the observer.

## REPRESENTATIVE CORRECTNESS

All 30 exact frozen script/workbook identities were verified. The unscored cold/second gate and all 450 scored representative invocation comparisons passed: **510/510 valid correctness rows**. Output differences were exact or the frozen comparator's volatile-only package difference; 68 rows contained a permitted volatile-only classification. Direct contact, certificate, fallback reason, and `BUILT → REUSED` artifact witnesses remained stable. Every scored H1 fast-path row had the classifier-negative/no-runtime witness. The five changed-file gates and scored rows also passed, giving **20/20 valid changed-file correctness rows**. There was no population substitution or post-result threshold adjustment.

## REFERENCE ONLY CAUSAL EFFECT

The primary endpoint is full-command H1/H0 on the 22 proven-reference second invocations, paired by workload and repetition. Median ratio was **0.985** (geometric mean 0.975; workload-bootstrap median interval **[0.961, 0.996]**), with **15 faster / 7 slower** and median signed saving **5.04 ms** (ratio range 0.901–1.073). This meets the preregistered causal rule, including its 5 ms margin, but only narrowly on that absolute margin. Equal-task median was 0.982 across 14 tasks; its task-bootstrap interval [0.944, 1.011] is wider and includes one. Cold H1/H0 on the same 22 was 0.980, with 17/5 faster/slower and −4.13 ms median signed difference.

These are same-run causal comparisons of the branch change. Comparing H1's signed excess to Phase-8A's archived +22 ms would overstate the effect because command timings drifted: same-run H0/PY reference-only second-command excess was +12.73 ms.

## REFERENCE ONLY TRANSPARENCY

Against direct PY, all 22 reference-only scripts had second-command H1/PY median **1.055** (geometric mean 1.053; interval **[1.024, 1.079]**), median excess **+8.73 ms**, 3 faster / 19 slower, range 0.986–1.134. Cold median was **1.054**, excess **+8.53 ms**, 3/19 faster/slower. These meet the **preregistered practical margins** of at most +10 ms second and +15 ms cold, respectively. They do not establish zero overhead or statistical equivalence to PY. The read-only assurance wrapper, guarded startup and classifier still have a measurable tax.

## DIRECT CONTACT NEGATIVE CONTROL

The seven direct-contact scripts preserved H0's path. Valid-reuse H1/H0 median was **1.000** (four faster / three slower; interval [0.998, 1.031]); no systematic direct-path improvement is credited to Phase 9. Their H1/PY valid-reuse median was **0.594**, with five faster and two slower, median signed saving −70.4 ms. The seven-workload interval [0.316, 1.085] is wide: this is a diagnostic contact view, not the all-30 product verdict. Cold H1/PY median for this subset was 1.147.

## FALLBACK AFTER CONTACT

The single `Template_06_23__fc41ad37c48b` fallback-after-contact script retained its contact, reference escape, certificate and artifact behavior. H1/H0 second-command ratio was 1.020; H1/PY was **1.161** and +14.3 ms. It was not fast-pathed or optimized. Its N=5 H1/PY session ratio was 1.203.

## ALL 30 COLD RESULT

On all 30, H1/PY cold median was **1.055** (geometric mean 1.073; workload-bootstrap interval **[1.041, 1.097]**), median signed excess +9.0 ms, **6 faster / 24 slower**, range 0.811–1.568. H1/H0 cold median was 0.983, with 20/10 faster/slower and −3.2 ms signed difference. Cold product-wide acceleration remains unsupported. Equal-task H1/PY cold median was 1.057 across 21 tasks.

## ALL 30 SECOND INVOCATION OR VALID REUSE RESULT

The endpoint combines **second invocation** for 22 reference-only scripts and **valid artifact reuse** for the eight contact/fallback scripts; it is not one universal warm label. All-30 H1/PY median was **1.054** (geometric mean 0.908; interval **[1.012, 1.077]**), median signed excess +8.3 ms, **8 faster / 22 slower**, range 0.310–1.161. H1/H0 median was 0.991 (19/11 faster/slower). Equal-task H1/PY median was 1.051, with task-bootstrap interval [1.006, 1.085]. The low geometric mean reflects large contact wins, while the median and count show the majority of this representative view receives no speedup.

## ALL 30 SESSION RESULT

Observed full-command sums start with no artifact; N is the number of fresh invocations. Ratios below are H1/PY. The bootstrap intervals resample workload identities, not a broad market population.

| N | All-30 median (geometric mean) | 95% median interval | Faster / slower | Median signed excess | Reference-only median | Direct-contact median |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.055 (1.073) | [1.041, 1.097] | 6 / 24 | +9.0 ms | 1.054 | 1.147 |
| 2 | 1.051 (1.012) | [1.019, 1.072] | 8 / 22 | +16.0 ms | 1.053 | 0.903 |
| 3 | 1.046 (0.984) | [1.017, 1.078] | 7 / 23 | +26.0 ms | 1.057 | 0.717 |
| 5 | 1.057 (0.959) | [1.020, 1.075] | 8 / 22 | +44.1 ms | 1.059 | 0.659 |

The direct-contact N=2/3/5 medians favor reuse, but the all-30 medians remain above one because 22 scripts accumulate the small reference-only wrapper cost. All-30 session acceleration is unsupported.

## CHANGED FILE CORRECTNESS

The same five frozen fixtures covered existing-cell value, formula, 20-cell, structural new-sheet, and output-workbook saves. Each H1 result matched PY/H0 final package state under the frozen volatile `docProps/core.xml` rule, produced the expected one-file effect record, and had successful helper validation/replay and observer receipt. The five volatile-core differences were classified, not ignored. The fast path never disabled effect observation.

## CHANGED FILE ECONOMICS

All five remain slower than PY because the assurance-preserving changed-file path runs the capture helper. Per-fixture median H1/PY ratios were **1.501–1.537**, with signed excess **+47.7 to +51.3 ms**. H1/H0 ratios were **0.932–0.986**, a modest improvement from skipping direct-runtime activation; this is not write acceleration. Across 15 scored H1 commands, the observer's changed-helper envelope median was approximately **42.6 ms** while measured internal capture work was **5.3 ms**. The full-command median was approximately 144.5 ms for H1 versus 95.1 ms for PY. These nested medians are diagnostic, not additive causal terms; same-run H1/H0 and H1/PY are the effect measures. The helper remains an understood but unresolved assurance cost.

## ABRUPT EXIT ASSURANCE

The two [changed-workbook abrupt diagnostics](../../read_engine_phase9/abrupt_exit.jsonl) passed **before the eligible score**. After `os._exit(7)` and SIGTERM, both H0 and H1 observers survived, detected one changed XLSX, completed the capture helper and validation, wrote receipts, and preserved exit 7 or signal 15 status. H0 followed its frozen reference-runtime route; H1 took the proven-reference fast path. Final workbook packages were equivalent. These are bounded Linux/POSIX witnesses, not a cross-platform assurance proof.

## WHERE THE 22 MS WENT

In this same-run environment, reference-only H0/PY second-command excess was **+12.73 ms**, not the archived Phase-8A +22.0 ms. H1/PY excess was **+8.73 ms**; direct paired H1/H0 saving was **5.04 ms**. The control and host/runtime state changed between studies, so the archived excess cannot be subtracted from the new excess as a causal estimate.

Coarse second-invocation component medians show the ownership movement: H0 bootstrap total **62.7 ms**, including **50.8 ms** runtime import/install; H1 bootstrap **10.3 ms**, with zero runtime import/install on proven-reference scripts. But post-bootstrap-to-exit median rises from **72.2 ms** to **128.5 ms** because real openpyxl is imported when the unchanged script executes instead of during H0 startup. Observer work remains. These nested medians do not sum to the observed net saving; they explain why removing a large bootstrap span yields only about 5 ms at the full boundary. Artifact machinery was not used by either rejected route, and it did not cause the measured reference-only excess.

## PAY FOR PLAY RUNTIME DECISION

The measured ownership rule favors **thin observer always active, direct acceleration activated only after a positive admission decision**. The 22 classifier-rejected scripts did not need the direct runtime, and skipping it preserved exact reference behavior and assurance while reducing full-command cost. The seven direct-contact wins and one fallback path stayed intact. This is pay-for-play activation by the existing semantic authority, not an economic selector and not a broad speed claim.

## REFERENCE ONLY FAST PATH VERDICT

**`EARNED`** under the preregistered rule: exact outputs, unchanged external assurance, 22/22 safe coverage, H1/H0 second median below one, median signed saving 5.04 ms, and majority faster (15/22). **`PRACTICALLY TRANSPARENT UNDER PREREGISTERED BUDGET`**: +8.73 ms second and +8.53 ms cold, both within the fixed +10/+15 ms margins. Residual overhead is real; 19/22 remain slower than PY on both endpoints, and the task-cluster causal interval includes one. The budget is an engineering criterion, not equivalence testing.

## INTEGRATION READINESS VERDICT

**A. `READY FOR PRODUCT INTEGRATION IMPLEMENTATION`.** The Phase-8A semantic blocker remains closed; Phase-9 route, representative, changed-file, process and abrupt-exit correctness gates pass; the direct-contact path is preserved; reference-only execution meets the fixed practical transparency budget. This earns reengineering the architecture into product modules, **not** copying the research harness, changing the RC, shipping a release, or making public speed claims. All-30 medians and changed-file commands remain slower than PY; the narrow warm contact benefit must be presented with its population boundary.

Production engineering still must define proxy identity policy, observer and helper failure semantics, safe artifact/resource bounds, cache permissions and concurrency, platform-specific observer packaging, and durable compact diagnostics. The changed-file helper's startup envelope is a separate future performance target, not part of Phase 9.

## AGENT INDEPENDENT PRODUCT ARCHITECTURE OPINION

I would make **acceleration conditional**, keeping the external observer and real script interpreter but activating direct-runtime imports/interposition only when the unchanged admission proof allows direct work. The simple negative branch was safer than an import hook and earned a modest full-command saving. The remaining +8–9 ms non-contact cost is small enough under the preregistered budget to begin product integration, provided nobody calls it zero overhead or universal speedup.

The most valuable next engineering task is a production implementation plan and semantic hardening of the observer/bootstrap trust and failure boundary. I would not copy the experimental overlay, native observer, or research telemetry directly. If the verdict were framed as **release readiness** or **broad product speed support**, I would disagree with it: neither has been earned.

## NEXT STEP

Begin a separate product-integration implementation phase with an explicit migration plan, correctness gates and platform/cache/error policy. Keep the current RC, public presentation and claim registry frozen until that integration is independently validated. Changed-file helper cost, cold construction and the single workbook-iteration fallback remain distinct follow-up questions; no Phase-9 optimization was stacked onto them.
