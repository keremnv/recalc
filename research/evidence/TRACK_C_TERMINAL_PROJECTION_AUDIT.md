# Track-C Terminal Projection Audit

Zero-model terminal adjudication of model-visible spreadsheet context
efficiency. No inference, no prompt/agent/helper changes, no mechanisms
implemented, Candidate A/A1/B untouched.

**Verdicts:** `REPETITION_BRANCH_CLOSED` +
`PROJECTION_VOLUME_HIGH_BUT_NO_MECHANICAL_CUT` →
**`TRACK_C_CLOSED`**.

Part I independently recomputes repetition from raw archived
trajectories with a fresh block-based implementation (string fact keys,
action-sheet attribution, extended coord parser). Part II separately
measures first-seen projection lineage. The two questions are never
conflated: new ≠ useful, and unlinked ≠ useless.

## Required answers — repetition

1. **Exact frozen corpus reproduced:** yes — 71 trajectories, 70 tasks,
   1210 turns/observations, 0 missing files, no substitutions.
2. **Spreadsheet observations analyzable:** 1210 (1174 non-empty).
3. **Exact bytes/chars:** 13,549,360 bytes / 13,549,005 chars
   (block-partitioned accounting; cf. 13,551,492 raw bytes incl.
   newline-boundary treatment).
4. **Estimated tokens:** 6,359,809 obs-level (block total 6,363,335;
   closest-known GLM-family tokenizer, estimated).
5. **Independent C0:** 1.65% tokens (1.64% bytes/chars).
6. **Independent C1:** 1.65% tokens (1.64% bytes/chars).
7. **Independent C2:** 1.68% tokens (1.67% bytes/chars).
8. **Incorrect sequential within-observation matching (diagnostic):**
   C0=7.27%, C1=7.37%, C2=7.39% — a 5.62pp false-redundancy inflation.
9. **Granularity correction justified:** yes — reproduced as required,
   not assumed; within-observation duplicates are the model's own
   single-print output, not prior-context repetition.
10. **C0 concentration:** top-5 tasks 61.0%, top-10 80.4% of C0 tokens.
11. **Top-10 manual audit:** no systematic misclassification in final
    totals. Two overcount bugs were found and corrected before final
    numbers: (a) a 32KB new-cell block misclassified as derivation by
    one `charts: N` line; (b) duplicate sheet-prefix keys inflating
    partial-overlap old-fractions. Details in
    `repetition_top10_manual_audit.json`.
12. **Unit invariance:** yes — C0/C1/C2 agree across tokens/bytes/chars
    within 0.04pp.
13. **Below material gates:** yes — C0=1.65% < 5% and C1=1.65% < 10%.
14. **Repetition branch closed:** yes — `REPETITION_BRANCH_CLOSED`.

## Required answers — projection

15. **Broad-scan token fraction (T=500 cells):** 80.3% (162/1210 obs,
    5.11M/6.36M tokens).
16. **First-seen broad-scan fraction:** 79.1% of all observation tokens
    (5.03M first-seen broad fact-tokens over 6.36M).
17. **Threshold sensitivity:** T=100: 88.5% (321 obs); T=500: 80.3%
    (162); T=1000: 76.5% (134); T=5000: 65.8% (111). Dominance is
    robust — the mass lives in giant dumps, not near the cutoff.
18. **Dominant scan shapes:** WHOLE_WORKBOOK_SCAN 3.91M (109 obs, incl.
    two ~1.8M dumps); FORMULA_DUMP 0.66M (18); WHOLE_SHEET_SCAN 0.42M
    (22); LARGE_RANGE_SCAN 88k (8); OTHER 22k; MULTI_SHEET 8k.
19. **Dominant tools:** python 4.04M (119 obs); view_xlsx 1.03M (37);
    shell 36k (6).
20. **P0 strong lineage:** 4.0% strict (10.6% loose sensitivity).
21. **P1 regional lineage:** 4.6% strict (29.3% loose).
22. **P2 no-observed-lineage:** 95.4% strict (70.7% loose).
23. **P2 concentration:** top-5 tasks 85.3%, top-10 90.0%, top-20 95.5%
    (n=42 tasks with broad scans; median task P2 20k vs mean 114k).
24. **Broad scans leading to later narrow reads:** 79/162 scans (loose
    fact-overlap); 6 strict scan→narrow→action chains.
25. **Broad scans leading directly to writes/actions:** 40 scan→direct
    chains (write/formula overlap, no intervening shared narrow read).
26. **Broad scans with no later mechanical lineage:** 56/162 scans;
    remaining 106 have some link (79 narrow, 45 write/formula, 14
    code/struct-only, 4 region-only; overlapping).
27. **Broad payload later re-read narrowly:** 145k tokens strict
    (448k loose) — 2.9% (8.9%) of broad mass.
28. **Write/formula action linked to prior scans:** strict exact-target
    links ~0 facts (sheet confirmation rarely available on both sides);
    loose 240 write + 289 formula facts (~8k tokens); loop-write
    regions overlap 1.15M loose / 34k strict tokens.
29. **Structural navigation from scans:** 53.7k tokens strict
    (sheet-name/header reuse in later actions), 17.1k loose-strongest;
    linked facts concentrate in early turns (68% of strict-linked mass
    within 3 turns).
30. **Oracle saving if narrow reads were known:** 1.86M tokens (29% of
    budget) — hindsight only, not implementable.
31. **Oracle concentration:** single-trajectory phenomenon — 1.81M of
    1.86M from the Debugging:10_05 giant-dump chain; other 5 chains
    total ~50k.
32. **Selectors tested:** S01 formulas; S02 task-sheets (keep unknown);
    S03 keywords-or-sheet; S04 header rows≤10; S05 head rows≤25; S06
    compact union; S07 head rows≤50; S08 task-sheets strict; S09
    formula-or-header. Inputs: task text + scan-time facts only.
33. **Token reductions:** 22.5%–99.0% (S02 lowest, S08 highest).
34. **P0 recall (pooled, strict):** 2.8%–58.5% (best S06 compact 58.5%;
    head-200 sweep 93.5% pooled but fails per-task gate).
35. **Precision:** 3.6%–30.6% (S08 30.6% at 5.9% recall; rest 4–8%).
36. **Gate (≥25% red + ≥95% recall on ≥10 tasks):** no selector passes;
    best per-task count is 4 (S04/S05/S09, on near-trivial tasks).
37. **90/95/99/100% recall:** head-row sweep reaches 93.5% pooled
    recall only at K=200 rows (43% reduction); 95% requires nearly the
    full scan; 99/100% unattainable at any material reduction.
38. **Hindsight dependence:** none — selectors are functions of
    (instruction text, exposed facts, row/col/formula structure) only;
    verified by construction (no future inputs in selector code).
39. **Mechanically coherent cut:** no — later-used evidence is
    scattered across depths/formats without a simple mechanical
    signature; recall collapses under every deterministic cut.
40. **Semantic/model judgment required:** yes — preserving useful
    evidence appears to require the model's own relevance judgment.

## Required architectural answers

41. **Prior repetition conclusion survives:** yes — independent
    C0=1.65%/C1=1.65% vs prior 2.36%/2.38% (stricter cross-sheet
    identity explains the delta); gates agree with margin.
42. **"Python already projects efficiently" too strong:** as a
    value-claim, yes — 95.4% of broad mass lacks demonstrated
    downstream use. The earned claim is narrower: no mechanical
    repetition problem (Part I) and no demonstrable mechanical
    projection improvement (Part II).
43. **First-seen projection materially large:** yes — ~80% of tokens.
44. **Large volume low-value by observable lineage:** largely
    unlinked (P2=95.4% strict), but unlinked ≠ useless — the model may
    use information internally without mechanical traces.
45. **Unlinked mass safely removable:** no — not demonstrated; P2 is an
    oracle ceiling only.
46. **No-hindsight rule earning a trial:** no — gate failed by all 9
    selectors with margin.
47. **Query DSL/helpers remain closed:** yes.
48. **Persistent-state/token-reduction closed:** yes.
49. **Delta/reference/derivation branches:** closed/frozen — repetition
    closure covers them; nothing here reopens any.
50. **What remains of Track C:** nothing actionable — a closed
    measurement record plus reopen criteria.
51. **Any intervention justified:** no.
52. **Single next experiment:** NONE — Track C is terminally closed
    (see `next_experiment.json` for reopen criteria).

## Evidence ledger

See `track_c_terminal_projection/evidence_ledger.json`. Headline:
`REPETITION_REDUNDANCY_LOW: EARNED`,
`OBSERVATION_GRANULARITY_RULE: EARNED`,
`FIRST_SEEN_PROJECTION_VOLUME: EARNED`,
`BROAD_SCAN_UNLINKED_MASS: EARNED`,
`NO_HINDSIGHT_PROJECTION_SELECTIVITY: REJECTED`,
`TRACK_C_INTERVENTION_JUSTIFICATION: CLOSED`.

## Deliverables

All files under `track_c_terminal_projection/`: `spec.json`,
`corpus_manifest.json`, `repetition_recompute.json`,
`repetition_observations.jsonl`, `repetition_blocks.jsonl`,
`repetition_top10_manual_audit.json`,
`token_byte_char_sensitivity.json`, `broad_scan_events.jsonl`,
`broad_scan_threshold_sensitivity.json`, `first_seen_facts.jsonl`,
`downstream_lineage.jsonl`, `lineage_rollup.json`,
`scan_narrow_action_chains.jsonl`, `scan_direct_action_chains.jsonl`,
`scan_no_lineage.jsonl`, `p0_strong_use.json`, `p1_regional_use.json`,
`p2_unlinked_ceiling.json`, `oracle_narrow_substitution.json`,
`no_hindsight_selectors.jsonl`, `selector_results.json`,
`selector_sensitivity.json`, `task_projection_results.jsonl`,
`family_projection_results.json`, `tool_projection_results.json`,
`opportunity_concentration.json`, `success_failure_projection.json`
(NOT_ESTABLISHED — no joinable outcome labels),
`repetition_verdict.json`, `projection_verdict.json`,
`track_c_final_status.json`, `evidence_ledger.json`,
`next_experiment.json`, `top_c0_tasks.json`.

## Final synthesis

### REPETITION RECOMPUTATION

Independent block-based recomputation: C0=1.65%, C1=1.65%,
C2=1.68% — reproducing the prior 2.36%/2.38%/3.65% within
methodological tolerance (stricter cross-sheet identity lowers C0;
block-vs-segment granularity lowers C2). All gates agree with margin.

### OBSERVATION-GRANULARITY CHECK

Correct 1.65% vs diagnostic-sequential 7.27%: the granularity rule
removes 5.62pp of false redundancy. Justified and required.

### TOKEN / BYTE / CHARACTER SENSITIVITY

Conclusions invariant: 1.64–1.68% across all three units. Tokenizer
choice cannot move any gate.

### TOP-10 REPETITION AUDIT

All top contributors verified genuine (exact-line prior-visibility
57–100% or same-file adjacent-obs overlap); two overcount bugs found
and corrected pre-final; no systematic undercount.

### REPETITION VERDICT

`REPETITION_BRANCH_CLOSED`. Recoverable repetition is immaterial.

### HOW MUCH CONTEXT IS FIRST-SEEN

Prior census 95.4% new-evidence stands unchallenged; this audit did
not need to relitigate it. First-seen-ness is factual novelty, not
value.

### HOW MUCH COMES FROM BROAD SCANS

80.3% of observation tokens at T=500 cells (65.8–88.5% across
T=5000–100); 162 broad obs, dominated by whole-workbook scans
(3.91M) and formula dumps (0.66M), themselves dominated by two
~1.8M-token dumps.

### WHAT BROAD SCANS ARE USED FOR LATER

Demonstrated use is thin but real: 4.0% strict P0 (narrow re-reads,
code references, structural reuse, concentrated within 3 turns),
4.6% P1 with regions. Loose sensitivity: 10.6%/29.3%.

### DIRECT WRITE / FORMULA LINEAGE

Exact-target strict links are ~zero (sheet confirmation rarely
available on both sides); loose exact links ~8k tokens; loop-write
regions overlap up to 1.15M loose / 34k strict. Writes usually
target loop regions, not individually re-identified cells.

### SCAN → NARROW READ → ACTION BEHAVIOR

6 strict chains (79 scans show some narrow re-read overlap); the
canonical orient-then-focus pattern exists but covers a minority of
broad mass. 40 scans link directly to writes without a narrow step.

### STRUCTURAL / NAVIGATION LINEAGE

53.7k tokens strict — sheet names and headers from scans reused in
later code. Real orientation value, small mass.

### NO-OBSERVED-LINEAGE MASS

Strict P2=95.4% of broad mass (4.8M tokens, ~75% of all obs tokens);
loose 70.7%. Oracle ceiling only; top-5 tasks hold 85%.

### ORACLE PROJECTION CEILING

1.86M tokens (29% of budget) if future narrow reads were known —
1.81M from a single giant-dump chain. Hindsight, concentrated,
unimplementable.

### NO-HINDSIGHT SELECTOR RESULTS

9 selectors + head-row sweep: none passes 25%/95%/10-task gate.
Best compact union: 29.8% reduction at 58.5% pooled recall.
Later-used evidence has no simple mechanical signature.

### WHETHER LARGE PROJECTION VOLUME IS ACTUALLY MECHANICALLY REMOVABLE

No. Large P2 oracle mass exists, but no no-hindsight rule preserves
demonstrated-use evidence at acceptable recall. Volume ≠ removability.

### WHETHER PYTHON'S PROJECTION BEHAVIOR IS SUPPORTED OR ONLY UNFALSIFIED

Only unfalsified as efficient, but supported as rational: broad
projection is the model's own relevance judgment, and no mechanical
alternative preserves what it later uses. Leave the choice with
the model.

### WHETHER REPETITION COMPRESSION REMAINS CLOSED

Yes — independently reproduced and audit-confirmed.

### WHETHER A DISTINCT PROJECTION PROBLEM EXISTS

As observable lineage, mostly no demonstrated-use mass exists — but
as an actionable resource, no: unlinked ≠ useless, and no cut is
viable. The "problem" is an oracle appearance, not an earned resource.

### WHETHER ANY PROJECTION INTERVENTION IS JUSTIFIED

No — `PROJECTION_VOLUME_HIGH_BUT_NO_MECHANICAL_CUT`. Large volume,
no mechanical cut, no intervention.

### TRACK C FINAL STATUS

`TRACK_C_CLOSED`. Repetition closed on reproduced low ceilings;
projection closed on failed selectivity. Reopen only on materially
new corpus evidence per `next_experiment.json`.

### SINGLE NEXT EXPERIMENT

NONE. Track C is terminally closed; no follow-up trial is authorized.
