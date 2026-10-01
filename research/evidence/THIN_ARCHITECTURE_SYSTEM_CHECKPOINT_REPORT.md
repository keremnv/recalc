# Thin Architecture System Checkpoint Report (FINAL)

Mid-scale matched checkpoint: H0 (default scaffold) vs H1 (frozen thin
architecture). 24 tasks (12 representative + 12 exposure) x n=1 x 2 arms =
48 primary runs + 1 repair rerun (runner crash, no data) + 7-pair replication
+ 1 third repetition (Template:02_05). Total 64 runs. All scoring official
WITH-refresh (LibreOffice 26.2.5.2, predeclared before selection). Identity
audit PASS. Verdict: `THIN_ARCHITECTURE_CAPABILITY_NEUTRAL_NO_EFFICIENCY_GAIN`.
Full 297-task run: NOT recommended.

## Q1 — Capability: PASS, no reproducible systematic degradation

Primary: 17/24 concordant. 7 discordant → replicated: 5 resolved as variance
(FM:17_02 flipped to H0 exact-1.0; T:08_02 converged identical; FM:08_01
both-fail; FM:15_04 reversed hard to H0 +0.59; T:13_08 both-fail); T:16_06
repeated H1-favoring (not a loss signal); T:02_05 went to r3 where H0 itself
collapsed (0.85/0.90/0.00 across reps, joint NO_SUBMIT in r3) →
MODEL_BEHAVIOR_VARIANCE. H1's T:02_05 failures were helper-contact-free with
two distinct modes (churn-stall vs early stall); helper-fact/staleness causes
impossible. Debugging 8/8 joint 0.0 both arms (family effect, not arm effect).

## Q2 — Efficiency: narrow mechanism real; no arm-level gain

Adoption (telemetry-reconciled): 4/24 H1 runs, 21 calls (16 search + 5
inspect, 0 periods), ALL Financial_Model; 0/12 representative cohort; Template/
Debugging zero execution adoption (3 shim-read-then-bypassed). Reproduces
Stage-B's FM-only pattern. Replacement where adopted: EXACT (08_03: 3 searches
displaced 9 H0 scan loops, equal 0.9973) to ADDITIVE (cheap-negative searches);
authoring compression real, observation bytes usually 10KB-capped both arms.

Aggregates are NOT helper effects: views 146→44, tokens −10%, cost −9%, but
A cohort −31% with zero adoption while B cohort +5% with all the adoption.
Sign tests prove systematic note-salience (views H1<H0 19–0, p<0.0001;
python 19–3, p=0.0004; persists in non-adopters). Token decomposition:
per-call −18% (fewer fat view obs, salience) × calls +10% (trajectory
variance) = −10%. No token-savings claim made; Stage-B's −51% views reframed
as largely priming. Positive criterion 4 fails → neutral verdict.

## Q3 — Reliability: clean

All H1 mutation records (primary + reruns): 0 capture/delta/validation/commit
failures, all replay-exact, freshness perfect (21/21 primary + rerun calls at
current generation), 0 stale responses, 0 corruption either arm. Caveat: H0
never corrupts either, so the demonstrated gain is assurance/detection
capability, not observed failure prevention.

## Required answers

1. Yes — preserved, no reproducible loss. 2. No H1-attributable losses.
3. No new failure class. 4. 4/24 runs, 21 calls. 5. No — FM only.
6. Scan-loop displacement (search); targeted range reads (inspect).
7. Authoring brevity; obs bytes mostly capped. 8. Views −70% via salience.
9. Tokens −10%, cost −9%, unattributable. 10. No — B cohort +5%.
11. No arm-level gain even among adopters. 12. No — non-adopters still show
the salience shift. 13. No unexpected cost in A. 14. Yes, perfect.
15. Reliability + narrow FM efficiency. 16. Justified: free integrity,
FM micro-mechanism, true negatives, neutral capability. 17. Unsupported:
savings, speed, capability gain, any T/D effect. 18. No full run.
19. Debt: T/D adoption unproven; note-example neutrality untested; H0/H1
differential failure prevention unmeasured. 20. Next: neutral-example prompt
micro-test for T/D adoption (cheap, terminal for the salience question) —
or close the efficiency program.

```text
WHAT WAS PROVEN BEFORE THIS CHECKPOINT
Free transparent runtime; narrow FM helper mechanism; closed branches.

WHAT THE FROZEN ARCHITECTURE IS
Default scaffold + optional search/periods/inspect + invisible transparent
runtime. Nothing else.

CAPABILITY RESULT
Preserved. 17/24 concordant; all 7 discordances resolved (6 variance-classed,
1 H1-favoring repeat). No reproducible H1 loss.

EFFICIENCY RESULT
No arm-level gain. Adoption 4/24, FM-only; aggregates confounded.

MECHANISM ATTRIBUTION
Adopted calls exactly replace scan loops (micro, real); views/tokens gaps
are note-salience + trajectory variance (macro, unattributable).

RUNTIME / INTEGRITY RESULT
Clean: zero failures, replay-exact, freshness perfect, zero corruption.

REPRESENTATIVE VS EXPOSURE COHORT
A: concordant, zero adoption, no cost. B: all adoption, all loss candidates
(resolved), +5% tokens. Exposure bought contact, not savings.

WHAT THE ARCHITECTURE ACTUALLY BUYS US
Free integrity proofs + a narrow FM lookup mechanism + ruled-out directions.

WHAT IT DOES NOT BUY US
Token/cost savings, speed, capability gains, or anything in Template/Debugging.

OPEN INTEGRATION DEBT
T/D adoption; example-neutrality test; differential failure-prevention evidence.

WHETHER A FULL RUN IS NOW JUSTIFIED
No.

SINGLE NEXT EXPERIMENT
Neutral-example prompt micro-test for T/D adoption; on failure, close the
efficiency program and keep the runtime as audit infrastructure.
```
