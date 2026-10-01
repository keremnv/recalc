# Preregistered experiment spec — Phase 12 live verification A/B v1

Frozen before any live treatment call. Amendments require a labeled
amendment file made before affected runs + version bump.

## 1. Populations (fresh tasks; seed 12; Phase-11 frontier tasks excluded)

- Pilot (Tranche 1, NON-INFERENTIAL, excluded from causal estimate):
  Template:03_01, Debugging:09_09, Financial_Model:14_01 × {CONTROL, TREATMENT} = 6 runs.
- Population A — representative (Tranche 2, primary): 24 tasks × {CONTROL, TREATMENT} = 48 runs.
  Template: 01_03, 06_05, 06_25, 10_02, 11_03, 11_04, 14_03, 15_02.
  Debugging: 01_01, 03_03, 04_06, 05_04, 08_03, 08_06, 09_08, 10_03.
  Financial_Model: 03_02, 05_05, 07_01, 07_02, 12_01, 12_05, 14_05, 18_03.
- Population B — exposure-enriched (Tranche 3, separate inference): 12
  top-formula-density fresh tasks × {CONTROL, TREATMENT} = 24 runs.
  Template: 16_02, 06_16, 06_09, 16_05.
  Debugging: 10_01, 10_04, 10_05, 10_06.
  Financial_Model: 08_03, 08_04, 08_05, 17_05.
- SHAM diagnostic subset: 12 Pop-A tasks (4/family) × {SHAM} = 12 runs.
  Template: 01_03, 11_04, 14_03, 15_02. Debugging: 01_01, 08_03, 08_06,
  09_08. Financial_Model: 03_02, 07_02, 12_05, 18_03.

## 2. Model/scaffold (identical across arms)

z-ai/glm-5.3-flash via OpenRouter, temperature 0.0, top_p 1.0, max_tokens
8192, tools bash/view_xlsx/submit (tool_choice required, no parallel
calls), byte-identical system+instance templates from
benchmark/sweagent/spreadsheet-control.yaml, CALL_LIMIT 40, RUN_TIMEOUT
900s, INSTANCE_COST_LIMIT $0.25, MAX_OBS 10000. Runner:
phase12/run_ab.py (imports ab_local_runner primitives).

## 3. Arms

- CONTROL: plain loop to submit/budget end.
- TREATMENT: same loop; on first submit call: freeze candidate output as
  pre-intervention artifact, recalc, run frozen verifier 1.0.0; if
  positive, inject the evidence block as the submit observation and open
  ONE bounded repair window (≤8 model calls, ≤$0.10 additional,
  ≤300s wall, same tools); then accept final submit. If negative or
  VERIFIER_UNAVAILABLE: submit normally, record outcome.
- SHAM: same boundary; neutral message ("Post-edit check complete. The
  workbook was recalculated and the current file is ready for review.
  Review it before deciding whether to submit or revise.") + identical
  repair window regardless of verifier state.

## 4. Verifier

Version 1.0.0, hashes in phase12/VERIFIER_VERSION.json. Rewrite filter v1,
block format v1, CHG-alone rule (≥150 cells or ≥5 sheets), sample caps 10.
One verify → one repair window → final submit (no loop).

## 5. Repair budget (frozen)

≤8 additional model calls, ≤$0.10, ≤300s wall, ≤8 tool calls after block
delivery. Actual use reported. Window ends on submit or budget exhaustion
(auto-submit of current candidate).

## 6. Endpoints

- Primary: official_exact (benchmark evaluator) paired difference
  TREATMENT−CONTROL on Pop A completed pairs + harmful-submit rate
  (fraction submitted with verifier-positive damage remaining).
- Secondary: revisit rate (IGNORED/INSPECTED/REVISED/RECALCULATED/
  RESUBMITTED), repair success (signal removed, score Δ, new damage),
  nuisance (ACTIONABLE/TRUE-BUT-BENIGN/FALSE/AMBIGUOUS per finding),
  regressions (correct→incorrect pairs), cost (calls/tokens/wall/$ split
  model vs verifier), prevalence per family (Pop A only), conjunctions,
  sham comparison.
- Behavioral coding guide frozen in §9 below.

## 7. Kill rules (program closes/demotes if ANY fires on primary tranche)

- K1 uptake: <25% of treatment-positive runs reach INSPECTED or beyond.
- K2 benefit: zero reduction in harmful-submit rate AND no directional
  official_exact gain (paired Δ ≤ 0).
- K3 nuisance: >50% of surfaced findings TRUE-BUT-BENIGN (finding level,
  adjudicated post-hoc with gold).
- K4 regressions: ≥2 paired correct→incorrect reversals attributable to
  treatment-induced edits.
- K5 economics: <5% positive rate on Pop A representative runs with zero
  rescues (no signal-removed + score-improved case).
- K6 salience: sham matches treatment on revisit rate (±10pp) AND on
  harmful-submit reduction (no separation), implicating generic reminder.

## 8. Success rules (ALL required to earn product candidacy)

Positives observed on fresh tasks; uptake ≥50% INSPECTED+; fewer harmful
final submissions (treatment < control, paired); no regression spike
(≤1 unattributed reversal); directional official_exact gain (paired Δ>0);
nuisance acceptable (≤50% benign); sham below treatment on uptake or
harmful-submit separation; cost defensible (<2× control per run).

## 9. Behavioral coding guide (frozen)

First model response after block delivery: ACKNOWLEDGE_ONLY (text, no
tool), INSPECT_SIGNAL (views/reads flagged cells), TRACE_CAUSE
(precedent/dependency inspection of flagged cells), REPAIR_DIRECTLY
(edits flagged cells), RECALC_VERIFY (recalc + readback),
DISMISS_WITH_REASON (states why block is wrong/irrelevant, then submits),
IGNORE_AND_SUBMIT (submits unchanged without engaging),
CONFUSED/MALADAPTIVE (looping, destructive unrelated edits). Coded from
transcript; ambiguous cases double-checked manually.

## 10. Censoring

Statuses preserved: PROVIDER_ERROR/CENSORED, TRUNCATED_*,
NO_SUBMIT, VERIFIER_UNAVAILABLE, RECALC_FAILED, INVALID_WORKBOOK.
Censored runs excluded from paired denominators, listed in censoring
ledger with stage. No silent replacement.

## 11. Analysis

Task-level paired units (Pop A); exact counts for rare events; bootstrap
95% intervals for paired exact-Δ; family breakdowns; cell-level counts
never treated as independent. Pilot excluded. Pop B separate.
Blinding: treatment constructed from artifacts only; gold joined at
analysis. Verifier frozen — no changes during live tranches except
stop+amend+bump+invalidate on mechanical-truth bugs.

## 12. Amendments (pilot-stage only; no inferential tranche started)

A1 (2026-09-28): per-call absolute provider deadline 90s → 300s
(phase12/run_ab.py sets base.CHAT_TIMEOUT=300; per-socket 15s,
RUN_TIMEOUT 900s, CALL_LIMIT 40, cost caps unchanged). Cause: pilot
run Template:03_01 CONTROL showed the model emitting max-length
reasoning (6332 reasoning tokens, finish_reason=length, ≈195s
server-side, headers in 0.7s) on an ordinary 52-row observation; the
90s deadline censored a legitimate slow generation as PROVIDER_ERROR.
Bisected halves of the observation succeeded only because the model
then generated short completions — the trigger is output length, not
input content. NO_TOOL_CALL responses (incl. finish_reason) are now
logged as trajectory events; the existing no-tool-call nudge path is
unchanged. Prior spec hash
ccbd9d1fce10fd9650c552982fef0e610c6abc92a1f5c6dd52d58a499be1ac0c
superseded before any inferential run.

A2 (2026-09-28): extended pilot (Tranche 1 continued, NON-INFERENTIAL).
Cause: pilot proper ended 0/6 SUBMITTED, 0/6 outputs (vs 6/10 C0
baseline on the same model, p≈0.004): Template:03_01 ramble-trapped
in both arms (13 length-events, ~8 productive calls); Debugging:09_09
worked genuinely (19/28 bash) but hit the 900s wall; Financial_Model
runs mixed. The TREATMENT intervention path never fired, so the live
machinery is unvalidated. Before any scaffold change, test the
task-vs-scaffold hypothesis on fresh tasks: up to 6 additional tasks
× {CONTROL, TREATMENT} = up to 12 runs, stop early once ≥2 runs reach
SUBMITTED AND the intervention path has fired ≥1 with recorded
outcome. Draw: random.Random(1212).sample over per-family pools of
all dataset tasks minus (Phase-11 matrix tasks ∪ pilot ∪ PopA ∪
PopB), 2 per family → Template:11_01, Template:09_03,
Debugging:07_08, Debugging:03_05, Financial_Model:19_04,
Financial_Model:20_03. These tasks are permanently excluded from
Tranches 2/3 (disjoint by construction; PopA/B lists unchanged).
Decision rule: non-trivial submits → Tranche 2 as preregistered;
continued ~0 submits → scaffold amendment A3 (budget/behavior) +
re-pilot. Instrumentation (no behavior change): finish_reason logged
on every trajectory tool event (A1 had it only on NO_TOOL_CALL;
pilot showed finish_reason=length can also truncate mid-tool-call
arguments, observed once in Financial_Model:14_01 CONTROL msg 36).
Prior spec hash
713d35efeadd7f7634fdfaed41e40a885e267247fc4b09b6b832bbf214d76ca
superseded before any inferential run.
