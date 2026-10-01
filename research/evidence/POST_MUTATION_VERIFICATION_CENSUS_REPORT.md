# Post-Mutation Verification / Repair / Reopen Census Report

Zero-model descriptive/eliminative probe. No inference, no prompts changed, no
helpers added, no runtime changes. Analyzer: `benchmark/postmut_census.py`
(deterministic heuristics, AST-free regex + event sequencing; unresolvable
cases labeled UNRESOLVED/*).

## Population

71 historical default-control trajectories (P-A 9 + P-B 60 + P-C 2 Viz;
1210 linearized execs, full `python3 -c` bodies recovered from `.traj`) plus
1391 live execs from all four live experiments (both arms; treatment runs used
only for runtime-observable comparison). Total: **232 mutation→post-mutation
episodes, 405 post-mutation actions**. Cross-check: 114/405 post actions carry
an independent purpose-label of VERIFICATION from the earlier census.

Method note: episode boundaries use purpose MUTATION labels + static write
detection (literal addresses, `.cell(r,c)`, `range()` expansion) + live
`WORKBOOK_MUTATION` boundary events. 159/232 mutations use dynamic
(variable-index/f-string/iterator) writes; readback overlap is therefore a
measured lower bound, and repair attribution on unlocated writes is honest
UNRESOLVED rather than guessed.

## What the agent does after writing

Post-mutation actions (405): CELL_READ 153, REOPEN_WORKBOOK 102 (transport),
LIBREOFFICE_CONVERT 100, RANGE_PRINT 81, RELOAD_DATA_ONLY 77,
SHEET_EXISTENCE_CHECK 25, FORMULA_SCAN 19, STYLE_CHECK 19, VIEW_XLSX 18,
PACKAGE_XML_INSPECTION 13 (discovered: `unzip -l`/XML greps for charts/cells),
FILE_EXISTENCE_CHECK 12, SCRIPT_PATCH_RERUN 11 (discovered),
READ_BACK_WRITTEN_FORMULAS 9, DIMENSION_CHECK 8, LIBRARY_SOURCE_READING 8
(discovered, Viz), MANUAL_EXPECTED_VALUE_CHECK 7, READ_BACK_WRITTEN_CELLS 5,
SAVE_CHECK 5, ERROR_SCAN 4, plus ARITHMETIC_CHECK / ENV_SETUP /
DUMP_TEXT_SEARCH / AMBIGUOUS_FILE_RUN (1–2 each). Remainder: 5 unclassified.

Dominant cycles: `LO_CONVERT > RELOAD_DATA_ONLY` (30),
`REOPEN > REOPEN` (22), `RELOAD_DATA_ONLY > RELOAD_DATA_ONLY` (22) —
i.e. **recalc-then-read-values** and **re-read loops**, not save-confirm loops.

Mechanical/semantic split (action-weighted): MIXED 148, RECALC-fact-for-
reasoning 101, MIXED+RECALC 61, pure mechanical 23, SEMANTIC 7 (remainder
mixed combinations). Persistence/structural-only questions are a small
minority; nearly everything is values-in-context or recalc outcomes.

## Self-readback (Phase 7)

Of 232 episodes: 74 have no post reads; 24 (10.3%) reread ≥1 written cell;
only **4 reread written cells alone** while 20 read written cells + wider
context. Formula rereads 8, value rereads 5 episodes. The governing
distinction holds empirically: agents read J35:N50 after writing J44:N44 —
semantic context gathering, not receipt-shaped confirmation.

## Follow-through and repair (Phases 4, 9)

VERIFY→SUBMIT 82, VERIFY→NEXT_MUTATION 74, MUTATE→MUTATE 43 (no reads),
MUTATE→SUBMIT 27. Verification precedes another mutation in 74/158
read-episodes (47%) — the loop is real, but its content is semantic review.

117 mutate→verify→mutate loops: MECHANICAL_RETRY 28 (+10 textual-fallback),
SEMANTIC_REPAIR 13, EXPANSION 3, UNRESOLVED 63 (39 unlocated dynamic writes,
24 truncated live args). The resolved subset leans retry, but resolution is
biased toward static-address scripts; triggers are correspondingly
PERSISTENCE_FAILURE 37 vs semantic/observed classes 14, UNRESOLVED 66.
No evidence that verification frequently catches runtime-known persistence
failures — retries rewrite the same targets, consistent with agents
iterating on content, not recovering from failed saves.

## LO/recalc branch (Phase 8)

91 episodes across all 4 families invoke LO convert; agents then seek
VALUE_RESULT (33), DOWNSTREAM_CHANGE (46), SEMANTIC_PLAUSIBILITY (5),
FORMULA_ERROR (1). A recalc receipt ("recalc succeeded, N downstream
changed") attests the step but cannot deliver the values/plausibility
judgments agents actually read. Separately, soffice cannot run in this
sandbox, so no LO-dependent intervention is earnable here; the cached-value
witness stays an integration caveat.

## Replaceability and ceiling (Phases 5, 10)

EXACTLY_REPLACEABLE: **12/405 calls (3.0%)** — every one a file-existence
shell check, 0 Python bytes, 3.6 KB observations, across 7 tasks / 3
families. The recurrence threshold (≥3 tasks, ≥2 families) is met
mechanically but the materiality bar fails outright: a commit receipt would
push "file exists / save succeeded" facts that agents almost never query
(SAVE_CHECK 5, pure persistence reads ~23/405). PARTIALLY_REPLACEABLE 127
(pullable facts, mostly via existing `inspect`), NOT_REPLACEABLE 120.

Total post-mutation work: 405 calls, 335 Python execs, 157 KB Python,
327 KB observations. Exactly-replaceable subset: 12 calls, 0 Python, 3.6 KB.
No token-savings claim (attribution unavailable); no aggregate-difference
causal estimate.

## Push vs pull, inspect overlap (Phases 12–13, 15)

58.5% (237/405) of post actions are pullable by earned `inspect()`; a new
primitive would save at most one pull call per read, at the cost of pushed
context that risks salience effects. Minimal pushable facts (save succeeded,
N changed, writes persisted) have near-zero measured demand. Details must
stay pullable; correctness-adjacent statements are rejected outright.

## Stalls (Phase 16)

17 stall episodes: 13 repeated semantic reconsideration, 4 repeated broad
inspection, 0 repeated mechanical verification. Stalls are not a receipt
problem.

## Required answers

1. Post-mutation verification occurs in 158/232 episodes (68%).
2. Dominant patterns: value/cell re-reads, LO convert→data_only value reads, reopen loops.
3. Pure mechanical persistence checking: ~23/405 actions (5.7%); exactly-replaceable 12 (3.0%).
4. Recalculation observation: 91 LO episodes; ~178 convert/reopen actions (44%).
5. Semantic reconsideration dominates: mixed/semantic verdicts on ~85% of actions.
6. Reread ≥1 written cell: 24/232 episodes (10.3%, lower bound).
7. Wider context instead: 20/24 readback episodes (83%).
8. Runtime-exact facts: persistence/structural checks (dims, sheets, file, save, declared writes).
9. Real reopens needed for: broad value context, formula scans over unindexed state, XML/package checks.
10. LO required for: recalc values, downstream changes, post-recalc errors (91 episodes).
11. Semantic interpretation required for: correctness, plausibility, expected-value, target choice.
12. Verification→another mutation: 74/158 read-episodes (47%).
13. Resolved repairs: 38 mechanical retry vs 13 semantic vs 3 expansion (63 unresolved, bias noted).
14. Exactly replaceable: 3.0% of post-mutation calls.
15. Ceiling: 12 calls / 0 Python / 3.6 KB obs removable; totals 405 / 335 execs / 157 KB / 327 KB.
16. Push vs pull: nothing earned push; pull via `inspect` already covers 58.5%.
17. Yes — `inspect` covers most pullable opportunity; no gap evidenced.
18. No new model-facing verification abstraction is justified.
19. Falsifier (observed): agents query values-in-context, not persistence attestations.
20. Next: none — NO_VERIFICATION_INTERVENTION.

## Verdict: `NO_VERIFICATION_INTERVENTION`

No candidate clears the retention threshold on materiality. Do not add a
commit receipt, verify helper, recalc receipt, or inspect extension. The
verification branch is closed alongside mutation-authoring. Artifacts:
`post_mutation_verification_audit/` (17 files as specified).

```text
WHAT THE AGENT CHECKS AFTER WRITING
Resulting values in context, recalc outcomes via LO convert + data_only
reopen, ranges beyond the written cells; rarely whether the save persisted.

WHAT IS PURELY MECHANICAL
File/dimension/sheet/save checks: 12 exactly-replaceable calls (3.0%).

WHAT ACTUALLY DRIVES SEMANTIC REPAIR
Value reads and recalc observations feeding plausibility judgment; 47% of
read-episodes lead to another mutation, mostly content iteration.

WHAT THE RUNTIME ALREADY KNOWS
Declared writes, cell/formula persistence, structural facts, package diffs —
facts agents almost never ask for.

WHAT IS EXACTLY REPLACEABLE
12 file-existence shell checks. Nothing material.

WHAT MUST REMAIN AGENT-DRIVEN
Reading values in context, judging recalc results, deciding correctness.

PUSH VS PULL
Nothing earned push; inspect() already serves 58.5% on pull.

MEASURED OPPORTUNITY CEILING
12 calls / 0 Python bytes / 3.6 KB obs out of 405 / 157 KB / 327 KB.

WHETHER A NEW PRIMITIVE IS JUSTIFIED
No.

SINGLE NEXT EXPERIMENT
None. NO_VERIFICATION_INTERVENTION; verification branch closed.
```
