# Uniformity study (C2/C8 → UNIF-FAMILY-BREAK, D2/D3, EXACT)

Detector (gold-blind): relative-family singletons with a same-row/column
neighbor in a family ≥3. Split into input-state breaks (D2) and post-edit
breaks (D3: in output, not in input).

## Prevalence

- Input-state breaks: 81/85 family workbooks (95%). Finding sets are LARGE
  (median ~100+, e.g. 259 in Debugging_06_05): legitimate edge formulas
  (totals, headers, first-column seeds) dominate. As a static list this is
  noise, not signal.
- Post-edit breaks: 28/59 outputs with matched inputs (47%). Finding sets
  are SMALL: 1–3 cells in 19/28 cases (e.g. LBO!C33+C40; PTA!R24;
  FCF_Calc!D13; DCF!X9 + 2). The D3 variant is high-precision by
  construction — it flags only what the agent's own edit broke.

## Natural reachability (input-state coding, n=81)

R2=69, R3=8, R4=4. The 4 R4 cases are all Debugging runs with explicit
evidence (e.g. `# Inconsistent net-debt formula in last exit column` +
  targeted fix). Agents essentially never enumerate breaks; the rare hits
  come from reading the outlier cell directly during debugging.

## Post-edit breaks vs scored misses (gold used only to classify)

- Debugging_02_01_C0: post-edit break set {DCF!X9, Synergies!D40,
  Synergies!Q40} CONTAINS the eval miss (DCF!X9). Agent reachability R2
  (saw formulas, never compared). Counterfactual: REDUCES_CANDIDATE_SET
  (3 cells, one of them the miss). Failure linkage: DIRECTLY_LINKED —
  the agent's own edit created the outlier it then submitted.
- Template_10_01_C1 (error case): post-edit region overlaps the new-error
  cascade; uniform-break and error-delta corroborate.
- No post-edit-break case was reached-and-used (R5=0): in all 28 cases the
  agent submitted without systematically comparing its edited formulas to
  neighboring families.

## False-positive structure

- Input-state breaks: mostly legitimate (edge/total/seed formulas).
  Surfacing them raw would be noise; they require the post-edit filter or
  a same-edit-session scope to be useful.
- Post-edit breaks: 28 cases include intended restructures (e.g. 55-cell
  RentRoll rewrite in Template_16_07 — the agent rewrote a region, so
  "breaks" are the task itself). Discrimination needs the conjunction:
  small break set + task not being a rewrite + (ideally) error/blank
  corroboration. 19/28 cases meet the small-set criterion.

## Interpretation

Input-state UNIF: MISSED BUT NON-DISCRIMINATIVE (too noisy to surface).
Post-edit UNIF (D3, small-set): MECHANICALLY VALUABLE + WORLD-STATE
FEEDBACK CANDIDATE — missed in all observed cases, exact, cheap (two
parses + diff), and directly linked to at least one scored miss with a
3-cell discriminator. Leading Phase-12 candidate, preferably bundled with
ERR-NEW-ERROR-DELTA and REF-BLANK-DELTA as one post-edit verification
evidence block.
