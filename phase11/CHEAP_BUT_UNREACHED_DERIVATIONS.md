# Cheap but unreached derivations

Candidates where the algorithm is trivial, the miss rate is high, and
failure linkage exists. These falsify "if Python makes it easy, the model
will naturally do it."

## 1. Post-edit new-error scan (ERR-NEW-ERROR-DELTA)

- Algorithm: recalc output (one headless convert), list error-valued cells
  absent from input. 4–10 lines + recalc invocation.
- Miss rate: 4/4 positive runs at R≤3 (two at R1: never re-read values).
- Failure linkage: DIRECTLY_LINKED×1 (miss ∈ 23-cell set), PLAUSIBLY×2.
- Why missed: verification behavior exists (70 runs recalc/read back) but
  targets expected-change confirmation, never error hunting. Discovery
  cost is zero (same file, same read) — the gap is purely cognitive:
  agents don't ask "did I break anything?"

## 2. Post-edit uniformity-break check (UNIF, D3 variant)

- Algorithm: family fingerprints pre/post, diff. 11–30 lines, two parses.
- Miss rate: 28/28 positive runs never systematically compared (R5=0;
  input-state coding R4=4/81, all Debugging eyeball finds).
- Failure linkage: DIRECTLY_LINKED×1 (3-cell set contains miss DCF!X9).
- Why missed: requires holding pre-edit structure in mind across the
  mutation boundary — agents live in the post-edit present. Discovery
  cost (reopening input + diffing) exceeds the perceived value until a
  failure teaches otherwise.

## 3. Became-blank reference enumeration (REF-BLANK-DELTA)

- Algorithm: refs per formula × blankness, diffed pre/post. 4–10 lines.
- Miss rate: positive-delta runs at R≤2 throughout (R4=8/81 are
  during-debugging spot checks, not enumerations).
- Failure linkage: DIRECTLY_LINKED×2 (incl. the DCF!X9 triple
  corroboration with the uniformity break).
- Why missed: blankness is invisible in formula view and silent in cached
  values; agents encounter it only downstream via errors — which they
  also don't scan for. A double-blind spot.

## 4. Change-footprint review (CHG-STRUCT-DIFF)

- Algorithm: cell-level input-vs-output diff. 4–10 lines.
- Miss rate: 15/49 footprints never reviewed (R1/R2); 4 contain scored
  misses (DIRECTLY_LINKED×4, all R1 — e.g. Template_06_12's 30-cell
  footprint containing CashFlow_Build!I9 across 4 runs).
- Why missed (partially): 34/49 ARE reviewed (R4=34 — the highest D3
  reach rate). Agents diff when suspicious; the misses are runs where
  nothing felt wrong. The value is in the unsuspicious cases — which is
  exactly where a system check complements rather than duplicates.

## Common structure

All four are POST-ACTION verifications, all cheap, all missed precisely
because agent attention moves forward (next edit, submit) while the facts
face backward (what did I just break). Ease-of-Python is irrelevant when
the agent never frames the question. This is the strongest evidence for
the Phase-11 hypothesis: the gap is question-framing, not computation.
