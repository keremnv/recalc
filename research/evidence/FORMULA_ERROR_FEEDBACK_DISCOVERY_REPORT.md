# FORMULA_ERROR_FEEDBACK_DISCOVERY_N8 — Discovery Report

Final capability-discovery test of world-initiated `new_formula_error` feedback.
16 primary slots (8 tasks × CONTROL/TREATMENT) + 7 PART-19 replacements, all run
under the frozen preregistration (`preregistered_spec.json`, hashes verified
byte-identical after the last run).

Machine-readable deliverables:
[formula_error_feedback_discovery](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_discovery).

## Verdict: FORMULA_ERROR_FEEDBACK_INCONCLUSIVE

- Enriched treatment contact: **2/7** (gate needs ≥6/7).
- Paired official outcomes: **1/7** enriched tasks (02_06 via replacements):
  mod Δ 0.0, reg Δ −0.001.
- 11/23 runs provider-censored (OpenRouter 90s-deadline timeouts); the
  lx_helpers scaffold saved in only 5/23 runs.
- The mechanism was never tested at the preregistered contact level. Per PART 17,
  insufficient treatment delivery is not a negative mechanism result. No
  confirmation, no product change, no claim revision.

## Required answers

1. Were all 16 primary slots attempted? YES (slots 1–16, frozen order).
2. Was the population unchanged? YES (02_01, 02_06, 02_09, 04_09, 07_03, 10_05,
   10_10 + clean 01_06; no substitutions).
3. Was the confirmation reserve untouched? YES (hash re-verified; zero reserve
   tasks in runs/).
4. Was the exact report template frozen before inference? YES
   (`exact_report_template.json`, sha in `spec_hash.json`).
5. Was `new_formula_error` the only exposed check? YES (no uniformity /
   broken-cell / continuation / integrity content anywhere in reports).
6. Was feedback delivered only once? YES (max one episode; verified: exactly
   one `treatment_report.json` per contacted run, one report append in
   observations).
7. Was feedback delivered only after the first nonempty save? YES (07_03:
   save 1/2 nonempty fired, save 2 silent; R14: save 1 fired; clean saves
   silent everywhere).
8. Was total call budget identical? YES (call cap 50, instance $0.25, timeouts,
   model, prompts, tools identical both arms; verified by shared frozen code).
9. What provider censoring occurred? 11/23 runs PROVIDER_CENSORED (90s request
   deadline timeouts after retries); 7 primaries + 4 replacements.
10. How many of 7 enriched treatment tasks contacted? 2 (07_03 primary, 02_06 R1).
11. Did the negative control contact? NO (both 01_06 treatment cells censored
    before any save; 01_06 control R1 saved clean).
12. What were report finding counts? 36 (07_03) and 30 (02_06 R1).
13. Which error kinds appeared? Err:522 only in reports (66 shown-counted
    findings); one #VALUE! appeared in a control invisible event.
14. Changed vs unchanged/cascade share? 1 changed / 366 unchanged (99.7%
    cascade) across all save events.
15. How many treatment agents wrote after feedback? 2/2 contacted (10 and 4
    post-report bash calls).
16. How many read after feedback? 0/2 (no view_xlsx after either report).
17. How many submitted? 1/2 contacted (R14 at call 43; 07_03 hit call cap).
18. How many shown errors were removed? 8/8 (07_03), 0/8 (02_06 R1).
19. What was final live-NFE reduction? 36→0 (07_03); 30→30 (02_06 R1).
20. How many new errors introduced after feedback? 0 in both contacted runs.
21. Did error removal correspond to official modification improvement?
    UNMEASURABLE: the reducing run (07_03, mod 0.0029) is unpaired (control
    noncompletion); the paired run (02_06) did not reduce (Δ 0.0).
22. Were any errors "fixed" by destructive clearing? NO blank-clearing: all 8
    shown 07_03 cells retain formulas in the final (circularity broken by
    upstream edits). But mod ≈ 0, so removal ≠ repair (class B-like).
23. Each task's paired modification delta? 02_06: 0.0; all other enriched
    tasks: no paired outcome.
24. Mean modification delta? 0.0 (n=1).
25. Median modification delta? 0.0 (n=1).
26. Modification wins/ties/losses? 0/1/0.
27. Bootstrap interval? [0.0, 0.0] degenerate (10k resamples over n=1).
28. Each task's regression delta? 02_06: −0.001; rest: no paired outcome.
29. Mean regression delta? −0.001 (n=1).
30. Did any task breach regression safety? NO (−0.001 within all bounds).
31. Does every LOTO modification mean remain positive? UNDEFINED (n=1; omitting
    the only pair leaves zero pairs) → condition fails.
32. Is any benefit concentrated in one task? MOOT (no benefit observed).
33. What happened on circularity-heavy tasks? 07_03 T resolved 36→0 (mod
    0.0029, unpaired); 02_06 T held 30→30 (paired Δ 0.0); 02_09 C carried 30
    invisibly (mod 0.8138 solo).
34. What happened on the #DIV/0! task(s)? 04_09: NO DATA (both arms
    provider-censored in primary and replacement).
35. Did capability improve when NFE mechanically fell? UNKNOWN (only fall is
    unpaired).
36. Did capability worsen anywhere despite error removal? NO paired worsening
    observed.
37. Did PROMISING pass? NO (contact 2/7; mean mod 0.0; LOTO undefined).
38. Did NO_CAPABILITY_EFFECT pass? NO (requires adequate contact ≥6/7).
39. Did HARMFUL pass? NO (reg −0.001; no breach).
40. Is the experiment INCONCLUSIVE? YES (contact <6/7; 1/7 paired outcomes).
41. Is fresh confirmation justified? NO (PROMISING did not pass).
42. Should the mechanism remain diagnostic-only? YES (no capability evidence
    either way; detector/audit use only).
43. Did any existing product claim change? NO (untouched per PART 22).
44. What is the single next action? With user authorization, repair experiment
    reliability (provider + save rate) under a NEW preregistration and
    re-attempt discovery once; otherwise close out as INCONCLUSIVE (see
    `next_action.json`).

## Final synthesis

```text
EXPERIMENT INTEGRITY

Preregistration frozen and hashed before first inference; all 12 artifacts
re-verified byte-identical after the last run. 16/16 primaries attempted in
frozen order; 7 PART-19 replacements (provider failures only, one each,
labeled _R1). Reserve untouched. No mechanism, template, budget, or gate
change after seeing outcomes.

POPULATION

FORMULA_ERROR_FEEDBACK_DISCOVERY_N8 unchanged: 7 enriched + clean 01_06.

TREATMENT CONTACT

2/7 enriched tasks (07_03: 36 Err:522 at call 40; 02_06 R1: 30 Err:522 at
call 38). Gate needed ≥6/7. Five enriched treatments never produced a
qualifying save (3 noncompletions without saving, 2 double-censored).

NEGATIVE CONTROL

Silent: no 01_06 treatment save ever occurred (both cells censored); the
01_06 control replacement saved clean (0 invisible). Specificity holds
vacuously — no evidence for or against live refire.

LIVE ERROR TYPES

Err:522 exclusively in treatment reports (66 findings); one #VALUE! in a
control invisible event. No #REF!/#DIV/0!/#NAME? live contact.

CASCADE VS DIRECT ERRORS

1 changed / 366 unchanged (99.7% cascade) across all save events. The live
signal is computational-damage cascades, as the probe predicted.

MODEL RESPONSE TO FEEDBACK

2/2 contacted agents wrote after the report (10 and 4 bash calls, first
action next call in both); 0/2 read; 1/2 submitted. Response without
inspection: neither agent viewed a shown cell.

MECHANICAL ERROR REMOVAL

07_03: 36→0 (8/8 shown absent, via formula edits, not blank-clearing).
02_06 R1: 30→30 (0/8 absent; submitted with all errors intact). Repair
fraction 1/2 = 50% (gate element met in isolation).

POST-FEEDBACK ERROR INTRODUCTION

Zero in both contacted runs.

OFFICIAL MODIFICATION EFFECT

One paired outcome: 02_06 Δ 0.0. Mean/median 0.0; wins/ties/losses 0/1/0;
bootstrap [0.0, 0.0] degenerate. Solo scores: 02_09 C 0.8138, 01_06 C R1
0.7595, 07_03 T 0.0029, 10_10 T 0.242.

OFFICIAL REGRESSION EFFECT

02_06 Δ −0.001. No guard breach anywhere (PROMISING reg elements met).

CAPABILITY VS ERROR-REMOVAL RELATION

Unmeasurable: the reducing run is unpaired (control noncompletion); the
paired run did not reduce. Classes: 07_03 B-like (reduced, mod≈0),
02_06 E (not reduced, unchanged).

CONCENTRATION / LEAVE-ONE-OUT

Undefined with n=1 (omitting the pair leaves zero pairs). Moot.

PROMISING GATE

FAIL (contact 2/7; mod 0.0; LOTO undefined; repair-fraction and reg-safety
elements met).

NO-CAPABILITY-EFFECT GATE

NOT APPLICABLE (requires adequate contact).

HARMFUL GATE

NOT MET (no regression harm observed).

PRIMARY VERDICT

FORMULA_ERROR_FEEDBACK_INCONCLUSIVE.

WHETHER CONFIRMATION IS JUSTIFIED

NO.

WHETHER CAPABILITY BRANCH CLOSES

NO — INCONCLUSIVE closes nothing; the branch awaits a valid test.

DIAGNOSTIC-ONLY STATUS

Mechanism remains diagnostic/audit-only; no capability claim in either
direction.

EXISTING CLAIMS UNAFFECTED

All PART-22 claims untouched.

SINGLE NEXT ACTION

With user authorization, repair experiment reliability (provider stability
plus scaffold save rate) under a NEW preregistration and re-attempt
discovery once; otherwise close out as INCONCLUSIVE.
```
