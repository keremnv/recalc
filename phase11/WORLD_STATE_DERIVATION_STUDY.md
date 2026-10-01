# World-state derivation study (D3 class: ERR / post-edit UNIF / REF-BLANK-DELTA / CHG)

World-state facts cannot exist until after the agent acts. The question is
not whether agents inspect before acting, but whether they verify after.

## Post-mutation verification behavior (n=179)

- Agent-pattern census: recalc (soffice/libreoffice/data_only) 70 runs;
  before_after (input-vs-output/diff language) 52; save_mutation 50
  (detector undercounts: some saves via scripts); print_dump 116.
- ERR coding on 74 outputs: R4 (re-read values) 30, R3 8, R2 10, R1 26.
  So ~40% re-read output values in some form — but the recalc substudy
  shows what that verification buys: in all 4 new-error runs the agent
  reached at most R3 (reopened or recalculated, never scanned for errors).
  Verification confirms expected changes; it does not hunt for introduced
  damage.
- CHG-STRUCT-DIFF coding (n=154 exposed incl. R0): R4=34 systematic
  input-vs-output diffs — agents DO diff when suspicious. But 4 scored
  misses sit inside unreviewed change footprints (CHG DIRECTLY_LINKED×4,
  all R1, e.g. Template_06_12 ×4 runs: 30-cell change set contains miss
  CashFlow_Build!I9, never reviewed).

## REF-BLANK-DELTA (C7, D2, EXACT) — reported here (delta is post-edit)

- Exposure: 81 runs have blank-referenced formulas; post-edit became-blank
  deltas computed input→output.
- Reachability: R1=26, R2=47, R4=8. Agents check blankness only when
  staring at a failing cell (the 8 R4s are `is None` checks during
  debugging, not enumerations).
- Linkage: DIRECTLY_LINKED×2 (Debugging_02_01_C0: 18-cell delta contains
  miss DCF!X9 — same cell as the post-edit uniformity break; Template_16_08
  miss NOI_Analysis!C32 ∈ 49-cell delta), REDUCES×2.
- The DCF!X9 triple corroboration (post-edit break + became-blank ref +
  scored miss, all R≤2) is the census's cleanest multi-signal case.

## The verification gap (central D3 finding)

| check | runs doing it | runs needing it (finding>0) | needed-but-missed |
|---|---|---|---|
| error scan of output | 0 systematic | 4 | 4/4 |
| post-edit uniformity compare | 0 systematic | 28 | 28/28 |
| became-blank enumeration | 0 systematic | 18 w/ delta | 18/18 |
| input-vs-output diff | 34 | 49 w/ footprint | 15 (incl. 4 scored) |

Agents verify the task ("did my edit land?"), never the damage ("what else
changed?"). All three damage checks are exact, cheap (1–2 parses + recalc),
and at R≤3 in 100% of positive cases. This is the Phase-11 frontier:
a post-edit verification evidence block (error delta + uniformity delta +
blank-ref delta + change footprint), delivered at VERIFY_AFTER_EDIT/SUBMIT
from frozen artifacts, framed as evidence with veto-shaped presentation
("23 new #VALUE! — submit anyway?") but no repair authority.
