# Model-Visible Stochastic Work Census

Zero-model measurement of spreadsheet observation redundancy in the frozen
ordinary-agent control corpus. No inference, no agent changes, no helpers,
no Candidate-A modification, no A2/A3, Candidate B untouched.

**Corpus (exact frozen match):** 71 trajectories / 70 tasks / 1210 turns.
Populations P-A_matched_c0 (9) + P-B_sixty_control (60) + P-C_viz (2).
All 71 `.traj` files present; zero substitutions.

**Tokenizer:** closest-known GLM-family tokenizer
(`THUDM/glm-4-9b-chat` ChatGLM4Tokenizer; the exact `z-ai/glm-5.3-flash`
tokenizer is unavailable). All token counts are ESTIMATED; byte/character
counts are exact.

**Headline result:** 95.4% of model-visible spreadsheet observation tokens
are genuinely new evidence. Strict-safe redundancy C0 = 2.36%,
deterministic ceiling C1 = 2.38%, oracle ceiling C2 = 3.65%.
Decision: `CONTEXT_REDUNDANCY_LOW_CLOSE_BRANCH`.

## Method in brief

- Reconstructed exact model-visible history per trajectory
  (`observations_raw.jsonl`, 1210 events).
- Segmented into 335,613 typed segments partitioning every character
  (`observations_segmented.jsonl`).
- Extracted 792,298 atomic facts with deterministic parsers
  (view_xlsx rows/listings, coord prints, tuple prints, formula refs,
  opaque text hashes for unparsed formats) (`atomic_facts.jsonl`).
- Classified each segment against the visibility snapshot strictly
  **before** its observation (governing principle: a fact is redundant
  only relative to what the model had been shown before that
  observation). Intra-observation duplicates are NOT redundancy.
- Workbook generation bumps on save/write or LibreOffice/recalc actions
  (197 boundaries); cross-generation facts never match.
- Token buckets per segment: new / old / derivation / repeated labels /
  control / reinspection (`token_accounting.json`).

## Required answers

1. **Analyzable trajectories/tasks:** 71/71 trajectories, 70 tasks, 1210
   turns. No archival loss.
2. **Model-visible spreadsheet observation events:** 1210 total, of which
   1174 non-empty (36 empty; 70 are submit acknowledgements).
3. **Total observation tokens:** 6,359,809 est (13,551,492 bytes).
   Segment-level total 7,029,210 est (per-segment tokenizer overhead,
   ratio 1.105; shares are scale-free).
4. **NEW_EVIDENCE:** 95.40% of segment tokens (6,705,655; 1082 obs rollups).
5. **EXACT_REPEAT:** 1.40% (98,411; 34 obs rollups).
6. **DETERMINISTIC_DERIVATION:** 0.008% (528; 2 obs rollups).
7. **MECHANICAL_REFORMAT:** 0.24% (16,896; 6 obs rollups).
8. **PARTIAL_OVERLAP:** 1.64% (115,143; 29 obs rollups; old portion
   ~51,751, i.e. ~0.74%).
9. **SEMANTIC_REINSPECTION:** 1.26% (88,625; 21 obs rollups).
10. **CONTROL_OR_ERROR_RECOVERY:** 0.0004% (26; first-seen errors count as
    new evidence; only repeated error text lands here).
11. **C0 strict-safe share:** 2.36% (166,237 seg-tokens; ~150k scaled).
12. **C1 deterministic-context ceiling:** 2.38% (167,607).
13. **C2 oracle repetition ceiling:** 3.65% (256,232).
14. **Concentration:** top-5 tasks hold 48.8% of C0, top-10 68.4%; 58/70
    tasks have nonzero C0 (broad-but-thin, with a heavy head).
15. **Successful trajectories:** not answerable — no benchmark outcome
    labels join to frozen trajectories (`official_scores.json` covers a
    different experiment's arms). Exit-status split only: 70 submitted,
    1 other. Redundancy is present across the submitted population.
16. **Families:** most redundant Financial_Model (C1 5.89% of family
    tokens); least Template (1.19%); Debugging 1.23% (volume-dominated
    by two one-shot whole-workbook dumps); Visualization 1.46%.
17. **Tool sources:** python carries 79.5% of all tokens; redundant-token
    density is highest in shell (re-grep/re-read loops), then view_xlsx,
    then python.
18. **Inspection patterns:** whole-workbook scans hold 60.8% of tokens
    and are ~entirely first-seen; range_inspection holds the most
    old-content tokens (114k); formula_chain holds the most reinspection
    tokens (32k).
19. **Facts shown more than once:** 33,472 of 779,768 distinct facts
    (4.3%) appear in 2+ observations (30,057 twice, 3,389 3-5x, 26 >5x).
20. **Tokens re-showing unchanged facts:** ~254k est (cross-observation
    re-exposure, fact-share attribution).
21. **Repetition across mutation/recalc boundaries:** zero by the
    generation rule (mechanically counted); value-level post-mutation
    unchanged confirmation is 3 tokens (4 events).
22. **Safely redundant after generation enforcement:** C0 = 2.36% — the
    generation rule is already enforced in all redundancy counts.
23. **Verification output that is unchanged confirmation:** 4 events,
    3 tokens (value-level, file-agnostic).
24. **Verification revealing genuinely new changed state:** 144
    EXPECTED_CHANGE_CONFIRMATION events, 57,617 tokens, plus 89 AMBIGUOUS
    (41,526) and 25 ERROR_RECOVERY (11,076). Verification is new
    evidence, not repeat output.
25. **Repeated opens producing repeated context:** 834 reopen
    observations deliver 6.55M new-evidence tokens vs 169k repeat tokens
    (2.5%). Repeated opens overwhelmingly produce new context.
26. **Execution-only redundancy:** 766 reopen events pair with
    new-evidence output (execution-only) vs 59 pairing with repeat-class
    output. Execution repetition and context repetition are nearly
    orthogonal — Candidate A territory, not context waste.
27. **Fully reconstructable payload:** 63 observations, 161,694 tokens
    (2.5% of obs budget) are FULLY_RECOVERABLE from visible prior history.
28. **Partially reconstructable:** 29 observations (103,811 tokens carry
    partial repeats); total recoverable token volume 216,854 (3.4%).
29. **Theoretical delta representation:** 217,060 oracle-avoidable tokens
    (3.09%), assuming 10-token reference overhead per repeated observation.
30. **Stable references/handles:** 8 candidate events, 70,906 tokens
    (~1.0%) — large (p90+) observations that are >=80% old content.
31. **Deterministic calculations over visible facts:** 528 tokens
    (0.008%): filter 117, sort 332, aggregation 25, coordinate lookup 26,
    formula parsing 7, other 21.
32. **Visible redundancy from lost Python/tool state:** 59 events,
    117,901 tokens (1.68%). The state-loss story is execution-heavy
    (766 execution-only reopens), not context-heavy.
33. **Largest token-weighted redundancy class:** PARTIAL_OVERLAP
    (115,143 seg-tokens, 1.64%; old portion ~51,751), followed by
    EXACT_REPEAT (98,411, 1.40%).
34. **Broad or pathological:** broad-but-thin — 58/70 tasks contribute,
    but the top 10 contribute 68% and no task exceeds 37.5% local C0
    except small-budget ones.
35. **Mechanically coherent enough for one intervention:** No. The three
    largest repeat classes each sit at 1.3-1.6% with different shapes
    (exact re-prints, overlapping scans, deliberate revisits); no
    threshold (C0>=10% or C1>=20%) is met.
36. **Best-matching mechanism family:** none earned. Tentative mapping
    recorded in `mechanism_mapping.json` for the record only.
37. **Should Track C be closed:** Yes — `CONTEXT_REDUNDANCY_LOW_CLOSE_BRANCH`
    (C0=2.36% < 5% AND C1=2.38% < 10%).
38. **Exact next experiment:** `TRACK_C_TERMINAL_AUDIT` — zero-model
    independent recomputation of C0/C1 plus manual audit of the top-10
    C0 tasks, then close Track C (see `next_experiment.json`).

## Materiality gates

| Gate | C0 2.36% | C1 2.38% |
|---|---|---|
| 5% | miss | miss |
| 10% | miss | miss |
| 20% | miss | miss |
| 30% | miss | miss |
| 40% | miss | miss |

## Evidence ledger

| Claim | Verdict |
|---|---|
| PYTHON_AS_AGENT_QUERY_LANGUAGE | EARNED |
| MODEL_VISIBLE_REDUNDANCY | SUPPORTED_NARROWLY |
| STRICT_SAFE_CONTEXT_REDUNDANCY | SUPPORTED_NARROWLY |
| DETERMINISTIC_CONTEXT_REDUNDANCY | SUPPORTED_NARROWLY |
| SEMANTIC_REINSPECTION_PREVALENCE | SUPPORTED_NARROWLY |
| REPEATED_QUERY_REDUNDANCY | NOT_ESTABLISHED |
| VERIFICATION_CONTEXT_REDUNDANCY | REJECTED |
| PERSISTENT_STATE_OPPORTUNITY | REJECTED |
| DELTA_OBSERVATION_OPPORTUNITY | NOT_ESTABLISHED |
| REFERENCE_HANDLE_OPPORTUNITY | NOT_ESTABLISHED |
| DERIVATION_ELISION_OPPORTUNITY | REJECTED |
| TRACK_C_INTERVENTION_JUSTIFICATION | CLOSED |

Rationale per claim is recorded in
`stochastic_work_census/evidence_ledger.json`.

## Deliverables

All files under `stochastic_work_census/`: `spec.json`,
`corpus_manifest.json`, `trajectory_manifest.jsonl`,
`observations_raw.jsonl`, `observations_segmented.jsonl`,
`atomic_facts.jsonl`, `observation_classification.jsonl`,
`recoverability.jsonl`, `repeated_facts.jsonl`,
`repeated_queries.jsonl` (+ `repeated_query_rollup.json`),
`mutation_recalc_boundaries.jsonl`, `verification_analysis.jsonl`,
`semantic_reinspection.jsonl`, `persistent_state_ceiling.json`,
`delta_ceiling.json`, `reference_handle_ceiling.json`,
`derivation_elision_ceiling.json`, `task_results.jsonl`,
`family_results.json`, `tool_source_results.json`,
`success_failure_results.json`, `token_accounting.json`,
`conservative_ceiling.json`, `deterministic_ceiling.json`,
`oracle_ceiling.json`, `opportunity_concentration.json`,
`mechanism_mapping.json`, `decision.json`, `evidence_ledger.json`,
`next_experiment.json`, `secondary_corpus.json`.

Secondary corpus: not pooled. The A1 live-checkpoint population file
exists but its runs are treatment trajectories under a modified runtime;
primary conclusions rest on the frozen corpus only.

Note: the four bulk deliverables (`observations_raw.jsonl`,
`observations_segmented.jsonl`, `atomic_facts.jsonl`,
`repeated_facts.jsonl`) now live in private working data outside Git;
see `research/EVIDENCE_ARCHIVE.md` and
`research/private-data-manifest.json`. All other deliverables above
remain in `research/history/stochastic_work_census/`.

## Final synthesis

### WHAT THE MODEL ACTUALLY SAW

1210 tool observations across 71 trajectories: 761 python outputs, 183
view_xlsx outputs, 177 shell outputs, 70 submit acks, 19 misc/empty.
13.55M bytes / 6.36M est tokens, dominated by first-seen workbook scans.

### TOTAL OBSERVATION TOKEN BUDGET

6,359,809 est tokens (whole-observation counts; segment-level 7,029,210
with per-segment tokenizer overhead). Two one-shot whole-workbook dumps
(Debugging:10_05, 10_10) hold ~57% of the budget and are ~94% new each.

### GENUINELY NEW EVIDENCE

95.40% of segment tokens. The ordinary agent's Python/view_xlsx/shell
projections are already highly efficient: each observation overwhelmingly
shows cells, formulas, and listings the model had never been shown.

### EXACT REPEATS

1.40% (98,411 tokens; 34 observations). Genuine cross-observation cases:
re-printed cells/formulas, repeated sheet listings, re-emitted status
lines. Identical-result query repeats total 110 tokens.

### DETERMINISTIC DERIVATIONS

0.008% (528 tokens). Negligible; no derivation-cache opportunity exists.

### MECHANICAL REFORMATS

0.24% (16,896 tokens). Same cells re-serialized (e.g. view_xlsx rows vs
tuple prints). Real but tiny.

### PARTIAL OVERLAP

1.64% total (115,143 tokens) with ~0.74% old-content portion (~51,751).
Overlapping range scans where most rows are new and a few repeat.

### SEMANTIC REINSPECTIONS

1.26% (88,625 tokens; 5,994 segments). Deliberate-looking revisits after
intervening work: memory refresh (4,591), comparison (967), error
recovery (419), navigation (4), verification (12). Not safely removable.

### ERROR / RECOVERY OVERHEAD

Control/error buckets total ~0.16% (11k tokens). Only 26 tokens are
repeated error text; first-seen errors are (correctly) new evidence.

### STRICT SAFE REDUNDANCY CEILING

C0 = 2.36% — same-generation, non-verification, non-error,
non-post-mutation-recency deterministic repeats. Below the 5% gate.

### DETERMINISTIC CONTEXT CEILING

C1 = 2.38% — C0 without the verification/error/recency guards. The
guards exclude almost nothing, so C0 ≈ C1; both far below the 10% gate.

### ORACLE REPETITION CEILING

C2 = 3.65% — C1 plus semantic-reinspection repeats. The absolute upper
bound on repetition of any kind, still below every materiality gate.

### REPEATED FACT BEHAVIOR

95.7% of distinct facts are shown in exactly one observation; 4.3% recur
across observations. Cross-observation re-exposure costs ~254k tokens.

### REPEATED QUERY BEHAVIOR

23 canonical-query repeat groups; re-runs return changed workbook
results in 33 cases vs identical results in 3 cases (110 tokens).
Re-querying is how the model tracks a changing workbook, not waste.

### MUTATION / RECALC EFFECT

197 save/recalc boundaries across 71 trajectories. Generation-gating
removes all cross-state false redundancy; value-level post-mutation
unchanged confirmation is 3 tokens.

### VERIFICATION BEHAVIOR

Post-mutation re-reads show model-authored new state: 144
expected-change confirmations (57.6k tokens) vs 4 unchanged
confirmations (3 tokens). Verification is a new-evidence behavior.

### PERSISTENT-STATE OPPORTUNITY

Rejected as a context opportunity: 97.5% of reopen-observation tokens
are new evidence. Only 59 events (1.68%) pair a reopen with repeat
output; 766 reopens are execution-only (Candidate-A territory).

### DELTA-OBSERVATION OPPORTUNITY

Not established: 3.09% oracle ceiling, below gates, with no coherent
partial-overlap pattern dominating.

### REFERENCE / HANDLE OPPORTUNITY

Not established: 8 candidates, ~1.0% of budget. Large structures are
rarely retransmitted merely to reference subsets.

### DERIVATION-ELISION OPPORTUNITY

Rejected: 528 tokens total. Nothing to elide.

### TASK CONCENTRATION

58/70 tasks contribute C0 tokens (broad), but top-5 hold 48.8% and
top-10 68.4% (head-heavy). Largest: Financial_Model:10_01 (27.3k),
Financial_Model:08_03 (19.3k).

### FAMILY DISTRIBUTION

Financial_Model shows the highest local redundancy (C1 5.89%);
Debugging/Template/Visualization sit at 1.2-1.5%. No family justifies a
family-specific mechanism.

### SUCCESSFUL-VS-FAILED TRAJECTORIES

Untestable: no benchmark outcome labels join to the frozen trajectories.
70/71 trajectories submitted. Redundancy is present across submitted
trajectories at uniformly low levels.

### DOMINANT SOURCE OF STOCHASTIC WASTE

PARTIAL_OVERLAP (1.64%) nominally, EXACT_REPEAT (1.40%) by removable
content — both small, neither dominant in any material sense.

### WHETHER THE REDUNDANCY IS MECHANICALLY COHERENT

No. Redundancy fragments across exact re-prints, overlapping scans, and
deliberate revisits at ~1.3-1.6% each, with no class or pattern that
could carry a mechanism.

### WHETHER TRACK C DESERVES AN INTERVENTION

No. `CONTEXT_REDUNDANCY_LOW_CLOSE_BRANCH`: ordinary agent-generated
Python already projects workbook information efficiently enough that
transparent context optimization is immaterial. Close the branch.

### SINGLE NEXT EXPERIMENT

TRACK_C_TERMINAL_AUDIT: independently recompute C0/C1 from the frozen
census artifacts, manually audit the top-10 C0 tasks for
generation/matching leakage, confirm identical-result query repeats and
unchanged verification stay negligible, then close Track C.
