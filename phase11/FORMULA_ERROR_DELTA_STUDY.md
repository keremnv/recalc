# Formula-error delta study (C3 → ERR-NEW-ERROR-DELTA, D3, CONDITIONAL)

Method: LibreOffice headless recalc (fullCalcOnLoad-patched scratch copies)
of 59 matched input/output pairs; 59/59 recalced ok. Compared error-valued
cells pre vs post. Cached-value comparison alone found ZERO deltas (openpyxl
writes no cached values for new formulas) — recalc was necessary, which is
itself a finding about discovery cost.

## Prevalence (n=59 recalculated pairs)

- 4/59 runs (7%) introduced new errors: 23, 29, 442, 24 cells (#VALUE! ×3
  runs, #DIV/0! ×1 run). Total 518 new error cells.
- All 4 submitted (SUBMITTED) and all 4 failed (official_exact=0.0 where
  scored; the 4th unscored).
- By family: Template 1, Debugging 1, Financial_Model 2. No Debugging
  over-concentration — errors arise wherever agents mutate.

## Case details

1. Template_10_01_C1: 23 new #VALUE! (EPS_Accretion cascade). Eval miss
   EPS_Accretion!B15 ∈ finding set → DIRECTLY_LINKED,
   REDUCES_CANDIDATE_SET. Agent R3 (reopened output, never read values).
2. live Debugging_02_06_H0: 3 → 29 #VALUE!. Eval miss is a text mismatch
   (Andarko/Anadarko), disjoint from errors → error delta is GENERIC here,
   but 26 net-new errors shipped without any check (R1).
3. live FM_01_01_H1: 0 → 442 #DIV/0!. Agent emptied ≥200 input cells and
   added 75 formulas (structural diff verified) — genuine destruction,
   R1 (never re-read values), submitted, failed.
4. token FM_03_03_B: 16 → 24 #VALUE! (net +8 on an already-errored base),
   R3, unscored.

## Natural reachability (n=179 coded; 105 R0 no-output)

Of 74 runs with outputs: R1=26, R2=10, R3=8, R4=30. The R4 mass is
verification behavior: 70/179 runs invoke recalc (soffice/libreoffice) or
data_only readback somewhere (agent-pattern census). But verification is
shallow: agents confirm expected changes (EXPECTED_CHANGE_CONFIRMATION in
the prior census), not absence-of-errors. In all 4 new-error runs the agent
reached at most R3 — reopened or recalculated, but never scanned for error
values. No run computed an error delta (R5=0).

## Counterfactual discrimination

- Template_10_01_C1: REDUCES_CANDIDATE_SET (miss ∈ 23-cell set; B15 is the
  cascade root region — root-cause localization would narrow further).
- FM_01_01_H1: GENERIC_WARNING_ONLY (miss disjoint) — but a 442-error
  warning is decision-bearing as a stop signal regardless of overlap.
- Debugging_02_06_H0: GENERIC (disjoint miss).
- The discriminator question "would the fact have changed the decision" is
  strongest as a SUBMIT-time veto: 4/4 error runs submitted; a "23 new
  #VALUE!" fact at VERIFY_AFTER_EDIT/SUBMIT is a natural stop-and-revisit
  trigger.

## Category note

Debugging vs completion-heavy: only 1/4 error runs is Debugging. The
candidate is not a Debugging specialty — it is a universal post-mutation
hygiene check. Prevalence 7% of submitted runs is low-frequency,
high-severity: exactly the shape where agent-side checking is unreliable
(agents optimize for the common case) and system-side verification pays.

## Interpretation

WORLD-STATE FEEDBACK CANDIDATE, leading Phase-12. Exact modulo recalc
trust (CONDITIONAL: LO-recalc ≈ Excel-recalc for these functions; UDF/
macro workbooks excluded), cheap (one headless convert per submit,
seconds), missed in 4/4 positive cases, directly linked once and
plausibly linked twice, discriminative as a submit-time veto. Satisfies
the promotion rule inputs; final promotion in PHASE12_PROMOTION.
