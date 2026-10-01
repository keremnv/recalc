# Phase 12R — independent Gate-A design review

Review disposition: **revise the attribution and denominator rules before freeze; the bounded replay design is otherwise suitable.** This is a design review, not a prediction of recovery prevalence or a reconsideration of Phase-12 D — DEMOTE.

Scope: read `PREREGISTERED_REPLAY_SPEC.md`, `STRONG_REVIEW_PREREG_RAW.md`, `PHASE12_POST_EDIT_VERIFICATION_AB_REPORT.md`, and the local official `benchmark-data/SpreadsheetBench-2/evaluation/evaluation.py`. No trajectories, recalculations, scoring runs, or workbook modifications were performed. Only this review document was written. The requested reviewer model was `gpt-6-astra`; this document does not independently attest backend identity or a measured strength ranking.

## 1. What the proposed experiment can identify

The paired comparison identifies the effect of one specified LibreOffice load/calculate/save pipeline on one frozen evaluator, conditional on the retained artifacts. It does not isolate calculation from serialization, establish Excel-equivalent semantics, or measure agent reasoning improvement.

The cache witness is a useful, distinct intervention: replace V0's typed formula-cache payloads with V1's and hold the rest of V0 fixed. If its assessed-cell outcomes reproduce V1's, it establishes that those cache replacements suffice to reproduce the observed scoring change. It does **not** establish that LibreOffice produced those caches using unchanged semantics. For example, LibreOffice could alter a defined name or iteration setting, calculate under that change, and leave behind caches which still score successfully when transplanted into the original package. A witness can reproduce the resulting numbers without reproducing their provenance.

Even a comprehensive stored-state comparison cannot prove that two calculation engines interpret all supported formulas identically. Therefore define `CACHE_ONLY_SCORE_RECOVERY` operationally as a **cache-mediated recovery under the frozen official scorer and stated semantic checks**. Do not promote that label into proof of correct original workbook semantics, a correct numeric answer at every affected cell, or engine neutrality. Record semantic-check results separately from witness success. A package difference census alone is not a semantic equality test.

## 2. Alternative explanations that could be falsely called cache-only

**Same formula text, changed calculation inputs or settings.** Required equality checks should cover typed nonformula values, sheet identities/order, formula positions/text/attributes and array ranges, defined names, tables and structured references, workbook date system, merged ranges, external-data/link state, iteration settings, precision settings, and calculation-relevant extensions. Compare resolved strings, not shared-string indexes. Resolve styles sufficiently to establish that number/date interpretation and any scored colors are unchanged. Unknown changed parts or unsupported constructs fail attribution conservatively. A frozen allowlist can accept strictly representational changes; it must not accept all metadata or styles wholesale.

**Different scorer branches.** The local evaluator's `cell_level_compare_with_classification` compares formulas whenever either the golden or output cached value is one of its recognized Excel error strings. This branch bypasses ordinary value comparison and, even in color mode, the font-color check. Thus a newly introduced cached `#NAME?` can turn a wrong or missing numerical answer into a match when the formula matches the golden formula. This is a valid cache-mediated *score* effect, but is not numerical repair. Conversely, replacing an error with a numerical value can exit a previously favorable formula fallback and reduce the score. The trigger checks the string value against the evaluator's fixed error set, not merely the XML error type.

The fallback comparator also strips dollar signs, uppercases the entire formula string, and removes a leading `=+`. Uppercasing includes quoted literals. Consequently, its agreement is weaker than the proposed semantic-equivalence rule. Never import the evaluator's formula normalization into semantic identity. Report whether changed assessed cells enter, leave, or remain in fallback, and whether the error is in the golden or output. Golden-triggered fallback persists even after output errors are removed. The classification of modification versus regression also uses error-triggered fallback, but remains fixed across variants when the input and golden are fixed.

**Aggregate agreement conceals disagreement.** Two variants can have identical exact/modification/regression outputs while matching different assessed cells. Returned ratios are rounded and regression ratios at least 0.998 are promoted to 1.0, so agreement can also conceal different correct-cell counts. The official `accuracy` is calculated from those returned ratios, not directly from the all-cells-match boolean. A task with an empty modification or regression partition has additional zero-denominator behavior. Preserve these definitions in the primary score and disclose them; do not silently substitute an intuitive exact-match score.

**Representation or parsing changes.** Rewriting styles can change the Python value type of a numeric cache, and rewriting sheet names can change the scorer's tolerant sheet lookup. Copying only `<v>` is insufficient for strings, errors, and Booleans; copying V1 shared-string indexes into V0 can produce the wrong strings. Cached string payloads need valid formula-cache representation without replacing the shared-string table. Shared/array formulas and spill outputs require an explicit supported policy. A spill value with no `<f>` must not be treated as a safely writable formula cache merely because its anchor is a formula.

Finally, call changed pre-existing caches “changed by the specified recalculation,” not automatically “stale.” A changed value may reflect a different engine interpretation. Missing-cache materialization and replacement of a present cache should be reported separately.

## 3. V0/V1 confounds and invalid comparisons

1. **Historical artifact mismatch.** Exact-copy V0 and the P1 fallback to unverified run-local outputs are incompatible if both are called original submitted bytes. Split byte-verified historical submissions from candidate-artifact normalized replay. A historical score match, especially after aggregation/rounding, does not verify the bytes. Unverified candidates may provide current-pipeline evidence but cannot establish correction of a historical submission.
2. **Historical evaluator drift.** Keep the historical score, current V0 score, and current V1 score as three separate fields. Historical numerical reproduction is necessary for some historical claims but is not evidence of evaluator identity. Byte-verified/current-score effects remain interpretable when the old evaluator is unavailable, with the historical attribution limit explicit.
3. **Asymmetric staging.** Freeze input/golden hashes, complete task metadata, answer positions, dataset-name mode flags, dependencies, arguments, and output naming. Stage variants separately; never let a stale output file masquerade as successful V1 generation. Record loading/saving completion and validate generated artifacts. Do not refresh input or golden during this replay.
4. **Failure-dependent eligibility.** “Reproducible current official evaluator” must not permit removal of difficult rows after scores or failures are observed. Determine provenance/task eligibility before replay; retain later evaluation/recalculation failures and unsupported cases as outcomes in the eligible denominator. Distinguish workbook read failure from an ordinary incorrect answer: the scorer converts some exceptions into zeros. A nonempty error message alone is insufficient because ordinary cell mismatches also produce one. Zero assessed cells require explicit handling.
5. **Uncontrolled calculation state.** Fixed locale/profile is useful but does not establish determinism for links, UDFs, external data, iterative/circular calculations, or unrecognized functions. Freeze unsupported detection and the conservative unknown-feature policy before outcomes. Scan parsed formulas and relevant package metadata, not substrings that also match quoted text. Unsupported is neither a successful no-effect result nor evidence of stability.
6. **Retention and repeated exposure.** This is prevalence among retained eligible artifacts, not among all historical attempts. Inventory missing/censored outputs. “Any affected run per task” depends on how many runs survive for that task; task clustering does not remove that dependence. Report retained run counts per task and keep the task-level endpoint descriptive, with its fixed aggregation rule.

## 4. The rule most vulnerable to hindsight

The phrase “no ... change plausibly explaining gains” leaves the decisive attribution judgment to the analyst after observing the gain. Replace it before freeze with a required-equality checklist, a narrow representational allowlist, and `UNDETERMINED` for unexplained changes. Apply identical rules to gains, regressions, and ties. Freeze the formula tokenizer/normalization rules and keep raw-formula equality separate from allowed semantic equivalence. Specify whether allowed function-case/shared-formula equivalence is sufficient to attempt a witness; “formula-identical” currently has more than one possible meaning.

The broad-baseline rule also needs one interpretation now. Specify P1 as the primary population, whether 10% applies separately to each family or overall, and how many distinct affected tasks each implicated family must contain. Do not switch to P1+P2 when P1 is small. Define mixed cases explicitly: a material gain plus a material loss is not an unqualified recovery numerator. A material gain plus a subthreshold loss should retain a visible mixed-sign flag even if the primary materiality rule counts it. Freeze Gate-B strata, denominators and timing; sparse strata and failure-heavy strata must remain visible.

Report the confirmed recovery fraction over all eligible rows, the conditional comparable-case fraction, and an unresolved-case bound. Otherwise a low confirmed fraction can be mistaken for evidence that failures and unsupported workbooks have no effect. These bounds concern unresolved retained cases, not the unobserved population of historical attempts.

## 5. A simpler discriminating replay

Retain only the paired V0/V1 experiment and one conditional cache witness. No trajectory, repair arm, or new verifier is needed.

1. Freeze manifest/provenance, semantics checks, scorer contract, failure rules and denominators. Score exact V0 copies with the current unmodified `process_single_item`.
2. Produce V1 once using the fixed pipeline. Score it under the same staging contract; retain every signed delta and status.
3. For materially changed pairs satisfying the frozen formula/semantic checks, create W by replacing only supported typed formula-cache payloads in V0. Apply this symmetrically to gains and losses.
4. Require W and V1 to agree on the assessed cell universe, modification/regression membership, per-cell match outcomes, and scorer branch selection, as well as the three official score fields. Alternatively, establish equality of every scorer-consumed typed value, formula, and relevant color at every assessed cell, which is a sufficient stronger condition. Use the official helper logic or a read-only observation check without modifying the official evaluator or redefining its scores. If the existing output cannot establish cell agreement, aggregate agreement alone remains a weaker sufficiency result.
5. Verify that W differs from V0 only in the declared cache payloads/types. Nonworksheet ZIP members must retain identical uncompressed payloads; compare worksheet XML outside allowed cache edits. A no-op transplant should preserve all scorer observations. Validate handling of numeric, string, empty, Boolean, error and supported shared/array cases on disposable plumbing fixtures, not by editing historical originals.

If semantics checks fail, W can at most demonstrate cache sufficiency for scoring; it cannot elevate the pair to the strongest attribution class. If witness observations disagree, retain the recalculation-associated result rather than resolving the disagreement by post-hoc allowances. No additional exploratory arm is needed to make that distinction.

## 6. Freeze requirements and interpretation limits

The essential pre-freeze changes are: separate verified historical bytes from candidate outputs; operationalize semantic checks and cache representation; require assessed-cell witness agreement; freeze primary and Gate-B denominators; and explicitly account for error fallback and evaluator failures. These are design corrections, not permission to tune materiality after pilot outcomes.

Keep the Phase-12 behavioral finding and D — DEMOTE as the starting record, but do not treat “mechanistically nailed” or “recalc-fair staging erases most benefit” as premises that this replay must confirm. Any correction should name the recovered runs and the exact affected claim. Successful score normalization on retained artifacts does not establish how agents would behave under a newly announced recalculating harness. It also does not separately demonstrate benefit from recalculation at both submission and evaluation: once evaluation recalculates, an additional submission refresh needs its own rationale.

Likewise, no detected recovery does not establish that historical baselines were unaffected when provenance, unsupported cases, failures, or retained-task coverage leave the relevant claim untested. Report those claims as unknown at the appropriate scope. This review recommends no product change and predicts no preferred replay outcome.

## Repository-agent disposition before freeze

Accepted: exact submission provenance for P1, separate normalized candidates,
operational semantics equality, full assessed-cell witness equivalence, scorer
error-fallback disclosure, strict historical returned-score reproduction, fixed
P1 baseline thresholds and Gate-B denominators, explicit unresolved cases, no-op
and typed-cache tests, and independent tooling/evaluation policy reasoning.
Iteration-enabled inputs are replayed with preserved settings but excluded from
strong attribution. More exploratory arms are unnecessary under the bounded
V0/V1+witness design. All changes occurred before final protocol hashing; pilot
changes concern mechanics/failure policy only, not materiality thresholds.
