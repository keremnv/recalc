# Phase 12: Live Post-Edit Verification Evidence A/B — Report

*Model: z-ai/glm-5.3-flash, temp 0.0. 92 live runs (60 primary+sham, 24
enriched, 8 pilot). Verifier v1.0.0 frozen. Prereg
`87550d26…` (amendments A1, A2, both pre-inferential).*

## 1. Question and program context

Phase 11 established an existence frontier: cheap deterministic derivations
(ERR-NEW-ERROR-DELTA, UNIF-FAMILY-BREAK post-edit, REF-BLANK-DELTA,
CHG-STRUCT-DIFF) that agents miss but that bear on decisions. Phase 12 tests
the single bundled treatment live: does compact mechanical evidence delivered
at the submit boundary improve outcomes enough to justify the interruption?
The phase is capable of killing the program, and the kill/success rules below
were preregistered to force the verdict.

## 2. Experimental design

Task-level paired A/B (CONTROL vs TREATMENT) plus a SHAM diagnostic arm.
Each run: plain agent loop (bash/view_xlsx/submit) to submit or budget end.
TREATMENT adds exactly one submit-boundary step: freeze candidate, recalc,
run frozen verifier; if positive, inject evidence block and open one bounded
repair window; accept final submit. SHAM adds the same boundary with a neutral
message and identical window regardless of verifier state. No live hook, no
repair authority, no intent attribution — evidence only.

## 3. Populations and sampling

Fresh tasks (Phase-11 frontier excluded). Pilot: Template:03_01,
Debugging:09_09, Financial_Model:14_01 × {C,T} (non-inferential). PopA
(representative, primary): 24 tasks × {C,T} = 48 runs. Sham: 12 Pop-A tasks
× {SHAM}. PopB (enriched, separate inference): 12 dense tasks × {C,T} = 24.
Extended pilot (amendment A2): seed-1212 draw, 6 tasks, early-stop after 2
runs; permanently excluded from Tranches 2/3.

## 4. Model and scaffold (identical across arms)

z-ai/glm-5.3-flash via OpenRouter, temperature 0.0, top_p 1.0, max_tokens
8192, tools bash/view_xlsx/submit (tool_choice required, no parallel calls),
byte-identical templates from benchmark/sweagent/spreadsheet-control.yaml,
CALL_LIMIT 40, RUN_TIMEOUT 900s, INSTANCE_COST_LIMIT $0.25, MAX_OBS 10000.
Per-call absolute deadline 300s (amendment A1; inherited 90s censored
legitimate ~195s max-length generations — a client-side timeout, not a model
refusal). Runner: `phase12/run_ab.py`.

## 5. Arms

CONTROL: plain loop to submit/budget end. TREATMENT: loop + boundary
intervention (§2) + at most one repair window. SHAM: boundary + neutral
message ("Post-edit check complete… Review it before deciding whether to
submit or revise.") + identical window. Zero-signal and VERIFIER_UNAVAILABLE
submit normally with recorded outcome.

## 6. Verifier 1.0.0 (frozen) and evidence block format

Bundle: ERR (recalc error delta) + UNIF (post-edit family breaks, rewrite
filter v1) + REF (became-blank refs) + CHG (structural-diff rollup, CHG-alone
rule ≥150 cells or ≥5 sheets) + one-hop dep accessory. Sample caps 10.
Block format v1: changed-cell count, per-family findings, "mechanical
evidence… Review it before deciding whether to submit or revise." Hashes in
`phase12/VERIFIER_VERSION.json`. No verifier changes during live tranches.

## 7. Repair window protocol

At most one window per run: ≤8 model calls, ≤$0.10 additional, ≤300s wall,
same tools. Exhaustion with a candidate on disk auto-submits it
(SUBMITTED_AFTER_REPAIR_WINDOW). No second verify, no loop.

## 8. Behavioral coding guide (frozen §9)

First response after block: ACKNOWLEDGE_ONLY, INSPECT_SIGNAL, TRACE_CAUSE,
REPAIR_DIRECTLY, RECALC_VERIFY, DISMISS_WITH_REASON, IGNORE_AND_SUBMIT,
CONFUSED/MALADAPTIVE. Coded from transcripts (§23).

## 9. Endpoints

Primary: official_exact (unmodified benchmark evaluator) paired difference
TREATMENT−CONTROL on PopA completed pairs + harmful-submit rate (fraction
submitted with verifier-positive damage remaining). Secondary: revisit rate,
repair success (signal removed, score Δ, new damage), nuisance per finding,
regressions, cost split, prevalence per family (PopA), conjunctions, sham
comparison.

## 10. Kill rules

K1 uptake <25% reaching INSPECTED+; K2 zero harmful-submit reduction AND
paired Δ ≤ 0; K3 >50% findings TRUE-BUT-BENIGN; K4 ≥2 attributable
correct→incorrect reversals; K5 <5% positive rate with zero rescues; K6 sham
matches treatment on revisit (±10pp) AND harmful-submit (no separation).

## 11. Success rules (ALL required for product candidacy)

Positives on fresh tasks; uptake ≥50%; fewer harmful finals (T<C paired);
≤1 unattributed reversal; directional exact gain (Δ>0); nuisance ≤50%
benign; sham below treatment on uptake or separation; cost <2× control.

## 12. Censoring rules

Statuses preserved (PROVIDER_ERROR, TRUNCATED_*, NO_SUBMIT,
VERIFIER_UNAVAILABLE, RECALC_FAILED, INVALID_WORKBOOK). Censored runs
excluded from paired denominators, listed with stage. No silent replacement.

## 13. Preregistration and amendments

Spec hashed before live tranches. A1 (pilot): per-call deadline 90→300s;
NO_TOOL_CALL trajectory logging (max-length rambles complete and are
handled by the nudge path). A2 (pilot 0/6): extended-pilot decision rule +
finish_reason on all tool events. Both pre-inferential, hashes chained in
§12 of the spec. No amendments after Tranche 2 started.

## 14. Tranche 0: mechanical truth

Frozen verifier validated on 59 Phase-11 pairs: FAILURES 0 after
expectation corrections; UNIF screen KEEP (13/59 positive, 22%, median set
4). Boundary-vs-post-hoc determinism re-confirmed live: all 10
pre-intervention post-hoc reruns match the live boundary reports exactly.

## 15. Tranche 1: pilot (0/6) and extended pilot (early stop)

Pilot proper: 0/6 submitted (Template:03_01 ramble-trapped both arms;
Debugging:09_09 genuinely working but time-starved; FM mixed) vs 6/10 C0
baseline (p≈0.004). Intervention never fired. Per A2, extended pilot on
fresh tasks: 2/2 submitted, first live intervention (REF-positive →
recalc → submit unchanged). Early stop met (≥2 submits + ≥1 firing).
Conclusion: pilot tasks were hard, not scaffold broken; Tranche 2 proceeds
as preregistered. Pilot excluded from all inference.

## 16. Tranche 2: primary execution narrative

60/60 runs (48 primary + 12 sham), sequential per-task pairs, 18:43–04:39
UTC. CONTROL: 8 submitted / 9 no-submit / 2 call-limit / 5 cost-cap.
TREATMENT: 9 / 7 / 6 / 2. SHAM: 2 / 6 / 2 / 1 + 1 provider-error. 7
completed C/T pairs (6 Template + Debugging:04_06); 14 tasks with neither
arm submitting. 10 interventions (8 positive T + 2 sham windows). One
status seen in the wild: SUBMITTED_AFTER_REPAIR_WINDOW (window exhausted,
candidate auto-submitted). No VERIFIER_UNAVAILABLE, no recalc failures.

## 17. Tranche 3: enriched execution narrative

24/24 PopB runs (+1 infra rerun: first FM:17_05 CONTROL attempt died to
transient DNS in fetch_prices before any model call; discarded, single
fresh rerun recorded). CONTROL 3 submitted, TREATMENT 2 (incl. one
after-window), heavy truncation otherwise. Both T submits REF-positive.
All three Template pairs replicate the PopA pattern (§22). Separate
inference; consistent with primary.

## 18. Endpoint results: paired exact and harmful-submit

7 completed PopA pairs: exact Δ sum +1 (06_05: 0→1; six ties 0–0),
mean 0.143, bootstrap 95% [0.0, 0.43]. Harmful-submit (submitted +
verifier-positive final; no-output submits counted harmful): CONTROL 7/8
(87.5%), TREATMENT 2/9 (22%), SHAM 1/2 (50%). Paired harmful comparison:
4 pairs C-harmful/T-clean, 1 both-harmful (06_25 residual UNIF), 2
neither. Large reduction — but §22 recharacterizes what "harmful" measured.

## 19. Secondary results: mod/regression, uptake, cost

Modification-accuracy gains on 5/6 Template pairs (T−C: +1.0, +0.95,
+0.67, +0.53, +1.0; 14_03: −0.09). Regression blemishes in 2 T finals
(10_02 E8, 11_04 C24) both verified pre-existing in pre-intervention
candidates — zero treatment-attributable damage. Uptake: 6/6 positive-T
windows reached RECALC_VERIFY; sham 2/2 engaged (1 recalc, 1 inspect).
Cost: mean T $0.112 vs C $0.119 (truncation-dominated both arms); verifier
<1.3s per firing; repair windows $0.003–0.017. Prevalence (PopA submits):
REF 6/8 T-boundaries, UNIF 1, ERR 0, CHG-alone 0.

## 20. Kill-rule evaluation

K1: 6/6 engaged — NOT FIRED. K2: harmful reduced (87.5%→22%) AND Δ>0 —
NOT FIRED. K3: 7/7 popA findings TRUE-BUT-BENIGN — FIRED. K4: 0
attributed reversals — NOT FIRED. K5: 67% positive rate on submits + 1
rescue — NOT FIRED. K6: revisit tied (100%/100%) but harmful-submit
separated (50% vs 22%) with large outcome separation — NOT FIRED (low
sham power noted, n=2 submits). Exactly one kill rule fires: nuisance.

## 21. Success-rule evaluation

7/8 pass: positives ✓, uptake ✓, fewer harmful ✓, ≤1 reversal ✓,
directional exact gain ✓, sham separation ✓, cost ✓. Nuisance ✗ (100%
benign > 50% cap). Product candidacy NOT earned — fails on exactly the
rule that tests the program's central claim (diagnostic value).

## 22. Mechanism decomposition (the cache finding)

Post-hoc sensitivity analyses (labeled; pre-intervention scoring and
recalc-then-score in `sensitivity_scores.jsonl`): (a) All 6 Template
PRE_T candidates score mod 0.000 — identical to CONTROL; the repair
window did everything. (b) Recalculating CONTROL outputs post-hoc
reproduces the treatment effect: RC_C mod 0.36–1.0, including exact 1.0
on 06_05/06_09/06_16/16_02. (c) Formula-identity proof (06_05): CONTROL
and TREATMENT formulas byte-identical; cached values None vs filled.
Causal chain: openpyxl writes formulas without cached values → evaluator
reads data_only (no LO refresh) → stale cache scores 0 → REF evidence
(describing the stale cache as "blank" refs) prompts a repair-window
recalc → cache filled → score. The intervention is a behaviorally potent
(8/8 recalc response), sham-separated recalc prompter — not a reference
diagnostic. Genuine formula-fix content in repairs: ~zero (one formula
rewrite, 10_02, no attributable gain; 11_04's RC_C gap reflects
trajectory differences, not repair fixes).

## 23. Behavioral coding results

PopA T windows: 6× RECALC_VERIFY first response (5 soffice recalc, 1 XML
cache injection). PopA sham: 2× INSPECT_SIGNAL first (1 submit-unchanged,
1 self-discovered cache injection after reading cached None). PopB: 1×
RECALC_VERIFY, 1× INSPECT_SIGNAL→8-call injection saga ending in window
exhaustion + auto-submit (validating the §7 path). Zero DISMISS,
IGNORE_AND_SUBMIT, or CONFUSED codes. Models treat the block as a
verification work order: recalc + readback, then submit. Full codes in
`phase12/ledgers/behavioral.jsonl`.

## 24. Nuisance adjudication

Finding-level, with gold/scores (post-hoc only): all 7 popA findings
(6 REF blocks + 1 UNIF item) TRUE-BUT-BENIGN — mechanically true
(cached None / real pattern deviation), benign as defects (formulas
correct-or-adequate; RC analysis proves it). The FALSE-reading (cells
aren't "blank," they hold formulas) would strengthen K3, not weaken it.
PopB: 2 REF + 9 UNIF items identically adjudicated (separate). The 9
UNIF items are final-only: suppressed at boundary on identical formulas,
surfacing post-injection via the rewrite filter's value-sensitive
`cells_filled` term — a verifier self-contradiction across recalc states
(deterministic, but semantically unstable).

## 25. Sham analysis (K6)

Sham revisit 2/2 matches treatment 6/6; sham harmful 1/2 vs treatment
1/6(2/9 incl. no-output) separates, and mod outcomes separate decisively
(sham≈control both pairs: 0.0/0.0, 0.982/0.982). But 14_03-SHAM proves
the neutral message sometimes suffices (spontaneous recalc → mod 0.982),
and n=2 submits cannot quantify the content effect. K6 not fired; the
content-specificity claim is directionally supported, weakly powered.

## 26. Censoring inventory

66 censored runs + 1 infra crash note (`censoring.jsonl`): NO_SUBMIT 37,
TRUNCATED_CALL_LIMIT 12, TRUNCATED_INSTANCE_COST 15, PROVIDER_ERROR 2
(1 sham popA, 1 treatment popB — both after live retries, distinct from
the A1 pilot timeouts). Arm-symmetric (C/T censor profiles comparable
within families); Debugging/FM dominate. Censoring is the price of
temp-0.0 long-horizon tasks, not treatment harm. 04_06/08_06 CONTROL
submitted without outputs (unmeasurable verifier state, counted
harmful, exact 0).

## 27. Threats to validity and limitations

(1) 7 pairs: exact endpoint underpowered (CI touches 0). (2) Template-only
signal; ERR/CHG families never meaningfully exercised live. (3) Sham n=2.
(4) Evaluator reads stale caches without refresh — the endpoint measures
submit hygiene as much as task competence; a recalc-fair harness would
erase most observed Δ (shown, not assumed). (5) Single model, single
provider; reasoning-runaway behavior (A1) may be version-specific.
(6) UNIF cache-sensitivity (§24) undermines positive/negative stability.
(7) Post-hoc sensitivity analyses are explanatory, not confirmatory —
but they test a mechanism the prereg data already implied (PRE_T = 0).

## 28. Verdict

Scale (reconstructed — the brief's A–G letter key did not survive in
artifacts; defined here explicitly): A integrate as designed; B integrate
with bounded fixes; C integrate narrowed to the proven channel; D demote
to scaffold fix (real effect, not a product); E park as inconclusive;
F close (no effect); G close with prejudice (harm/misdirection).
Placement: **D — DEMOTE**. K3 fired and success rule 6 failed, ruling
out A–C: the bundle is not earned as a diagnostic layer. But the effect
is real, sham-separated, and mechanistically nailed — ruling out F–G,
and E underclaims a decisively characterized result. Ship nothing;
instead: (i) recalc-before-submit in the harness, (ii) recalc-fair
staging in the evaluator pipeline, (iii) keep the behavioral lesson
(models verify on concrete mechanical reports) for future scaffold work.

## 29. Follow-on work (narrow, allowed)

(i) Harness recalc + rescore cleanup (scaffold, not product). (ii) If the
program ever revives: recalc-fair endpoint from day one; Template-only
claims dropped; UNIF value-sensitivity fixed or disclosed; sham powered
to ≥8 submits; Debugging/FM submit-rate pilot first. (iii) No ERR-vs-UNIF
ablation, no optimizer, no product command — out of scope per brief.

## 30. Provenance: artifacts, hashes, reproduction

Runs: `phase12/runs/{popA,popB,pilot,pilot_ext}/` (92 records).
Ledgers (10): `phase12/ledgers/` — raw_run, exposure, behavioral,
scorer_outcome, verifier_output, cost, nuisance, censoring, sham,
analysis.json (+ post-hoc sensitivity_scores.jsonl, labeled).
Verifier reports per run + post-hoc finals in
`verifier_final_reports/`. Scripts: run_ab.py, run_tranche{2,3}.sh,
score_ab.py, measure_finals.py, build_ledgers.py, build_analysis.py.
Prereg hash `87550d26…` (A1 ← `713d35ef…` ← `ccbd9d1f…`). Verifier
v1.0.0 hashes in VERIFIER_VERSION.json. Product runtime untouched
(rc2 files unmodified). Reproduce scoring: `python3 phase12/score_ab.py`
(all pops) + `--variants=pre,recalc` for §22. Model spend $10.80 across the 92 Phase-12 runs (global file cap $25
respected; $17.88 cumulative incl. earlier phases).

