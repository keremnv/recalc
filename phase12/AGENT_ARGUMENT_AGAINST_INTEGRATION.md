# Agent Argument Against Integration (Phase 12)

*Steelmanned case for closing or demoting the post-edit verification program.
Written from the evidence, against the author's own intervention.*

## 1. The headline result is a cache artifact, not a diagnostic triumph

The treatment "works": paired exact Δ +1/7, mod gains of +0.5 to +1.0 on six
Template pairs, sham separation. But the mechanism decomposition
(`sensitivity_scores.jsonl`) shows post-hoc recalculation of CONTROL outputs
reproduces the treatment effect — including exact 1.0 on four tasks whose
CONTROL formulas were byte-identical to TREATMENT's. The model never needed a
diagnosis; it needed `soffice --convert-to`. A one-line "recalculate before
submit" reminder captures ~100% of the observed benefit at ~0% of the
machinery. Integrating a four-family verifier to deliver a recalc reminder is
absurd on its face.

## 2. Every finding was benign

Finding-level adjudication: 7/7 popA findings TRUE-BUT-BENIGN. The flagship
REF signal ("X now references blank Y") fired on cells containing correct
formulas — "blank" meant "no cached value," a true mechanical fact with zero
defect behind it. The single UNIF item was ignored by the model with no
consequence. A diagnostic layer whose precision on fresh tasks is 0% actionable
defects is not a diagnostic layer; it is a noise generator that happened to
nudge productively. K3 fired. Success rule 6 failed. By the preregistered
rules, product candidacy is not earned. End of story.

## 3. The verifier contradicts itself across recalc states

16_02-T: identical formulas pre vs final, UNIF 0 → 9, because injected cached
values flipped rewrite-filter rules via `cells_filled`. A verifier whose
positive/negative distinction changes while the formulas stand still cannot be
trusted as "what the workbook can prove." The positive/negative boundary is a
function of cache state, not workbook correctness. Any downstream consumer
(harmful-submit gating, repair triage) inherits this instability.

## 4. The effect generalizes nowhere demonstrated

All submits, all interventions, all rescues are Template-family. Debugging and
Financial_Model contributed 60+ censored runs and zero paired signal. The
"deterministic post-edit diagnostic layer" has been demonstrated on exactly one
task shape (formula-fill templates where the failure mode is forgetting to
recalculate). The bundle's other families (ERR, UNIF-as-defect, CHG) never
fired meaningfully on fresh tasks. We validated a recalc reminder on templates,
not a verification layer for spreadsheets.

## 5. The sham arm is too thin to carry the separation claim

K6 survives only because n=2 sham submits split 1/1 on spontaneous recalc. The
14_03-SHAM model discovered the stale cache and fixed it unprompted — proof
that the generic reminder sometimes suffices. With 12 sham runs planned and 10
censored, the "evidence content matters" claim rests on 6 treatment recalcs
against 1 sham recalc and 1 sham miss. One more sham recalc and K6's second
conjunct gets uncomfortable. Do not claim content-specificity on n=2.

## 6. Censoring ate the experiment

7 completed pairs out of 24 planned. 14 tasks with neither arm submitting. The
paired exact Δ (+1, bootstrap [0.0, 0.43]) touches zero. The mod gains are
striking but the prereg primary endpoint is exact, and on exact we have one
rescue and six ties. A program-killing reading: the intervention moves partial
credit on templates via cache refresh and has no demonstrated exact-level
effect (lower CI bound 0.0).

## 7. The repair window is unprincipled extra budget

Treatment submits get up to 8 extra calls, $0.10, 300s that CONTROL never
sees. The 14_03 pair shows the window can also HURT (T mod 0.891 < C 0.982).
Extra budget after submit is a scaffold choice, not a verifier property — any
"check then continue" loop gets it. The verifier is taking credit for budget.

## 8. What integration would actually ship

A ~500-line verifier + LO recalc dependency + repair-window scaffold that: (a)
fires only REF-on-stale-cache in practice, (b) misdescribes cache state as
missing content, (c) contradicts itself across recalc states, (d) was never
tested where it matters (Debugging/FM), (e) duplicates a reminder that fits in
one sentence. Shipping this as "deterministic post-edit verification" would
mislead every downstream user about what was validated.

## 9. The honest redirect

The durable findings are scaffold fixes, not a product: (1) recalculate before
submit (or before score); (2) the official evaluator's data_only reads make
stale cache fatal — stage a recalc in the harness; (3) models respond to
concrete mechanical reports with verification behavior (recalc + readback),
which is worth remembering for future scaffold design. None of these needs the
bundle. Close the program; keep the lesson.
