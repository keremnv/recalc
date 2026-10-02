# Phase 13 — Loss-Boundary Taxonomy

## Boundaries

- **L0 benchmark/evaluator state**: stale cached values, evaluator
  normalization mismatch (formula-text, float tolerance, volatile
  functions), unsupported recalc semantics, scorer tolerance edges,
  input/gold inconsistencies. The agent's workbook is right (or the
  comparison is unanswerable) but the score says otherwise.
- **L1 environment/tool execution**: process failure, timeout of a tool
  (not the agent budget), tool error, missing dependency, workbook
  corruption produced by tooling round-trips, scorer XML/parse failures,
  external-data failure.
- **L2 observation/discovery**: needed evidence existed but the model did
  not inspect or find it (wrong sheet, uninspected region, missed
  target cells).
- **L3 representation/comprehension**: model saw the relevant evidence
  but misunderstood its structure or significance (e.g. saw a buggy
  formula but did not recognize the bug).
- **L4 target/intent inference**: model misunderstood what the user
  wanted changed (wrong target region, wrong units, missed implicit
  targets, fixed the wrong bug).
- **L5 action selection / formula choice**: model knew the target but
  chose an incorrect transformation, formula, or value (wrong
  operator/refs/sign/offset, omitted formula).
- **L6 execution mechanics**: intended action conceptually right but
  implemented incorrectly in Python/openpyxl (script bug, wrong
  coordinates at write time, broken package XML, chart/drawing errors).
- **L7 verification / stopping**: model had enough evidence to detect a
  problem (or to finish) but submitted prematurely, never submitted a
  valid workbook, overwrote good work, or stopped without submitting.
- **L8 resource allocation**: token/call/time/cost budget expired before
  task state moved enough (inspection loops, ramble traps, slow tools);
  includes wall-time deaths and cost/call-cap truncations.
- **L9 benchmark ambiguity / irreducible uncertainty**: gold, workbook,
  or task definition does not permit a confident mechanistic
  interpretation (volatile TODAY vs frozen gold, unknowable gold-only
  information).

## Classification rules

1. Classify at the **earliest supported point where the trajectory
   diverged** from a plausible successful path (§5 of the brief).
2. One PRIMARY boundary plus at most one SECONDARY contributing
   boundary. No causal graphs.
3. Confidence per record: DIRECT / STRONGLY_SUPPORTED / PLAUSIBLE /
   UNKNOWN. PLAUSIBLE never counts as proven in loss-mass rollups.
4. Submitted-but-incorrect and no-valid-submission are never pooled.
5. Recalc-fair status is recorded before any score-dependent claim:
   ALREADY_RECALC_FAIR / NEEDS_NORMALIZED_RECALC /
   INCOMPATIBLE_UNSUPPORTED.

## Boundary precedences established during the census

- **L0 vs L7 (stale cache)**: when formulas are gold-correct but caches
  are empty at submit, the earliest divergence is the submit-boundary
  hygiene failure. L0 is PRIMARY (score loss is an evaluator-state
  artifact), L7 SECONDARY (the agent verified a /tmp recalc copy but
  submitted the stale file — verified the wrong artifact).
- **L0 vs L5 (stale cache + wrong formulas)**: when recalculated
  scores still fail, the wrong formulas were written before the
  submit boundary, so L5 is PRIMARY and L0 SECONDARY. This applies
  even to near-miss residuals (10_02 E10 omission, 11_01 K8
  hardcode — Gate-A fix 4). Carve-out: when the V1 residual is a
  pre-existing input/gold inconsistency the agent never touched
  (06_25 B31 label), the run stays L0 PRIMARY — the residual is
  benchmark state, not agent error.
- **L3 vs L4 (Debugging misdiagnosis)**: seeing a buggy formula and not
  recognizing the bug is L3; choosing to fix a non-gold region (or
  missing an implicit target) is L4. Fixing a plausible-but-wrong bug
  after inspecting the whole sheet is L4 PRIMARY.
- **L7 vs L8 (no-submit)**: budget/cap/wall-time deaths are L8
  PRIMARY even when the trajectory also shows poor stopping, because
  the run did not choose to stop — it was stopped. L7 applies when
  the agent submitted (or ended) by its own action with usable
  evidence in context: empty submits, submit-without-inspection,
  never-submit-despite-valid-workbook where the loop ended by agent
  action rather than a cap. The phase-12 runner only exits the loop
  on caps, wall-time, provider error, or submit, so most
  never-submit runs are L8; 12_01 (correct workbook on disk at
  wall-time death after an over-verification loop) is L7 PRIMARY /
  L8 SECONDARY because the agent chose to keep verifying instead of
  submitting a finished workbook.
- **L1 vs L6 (corrupt output)**: corruption traceable to the agent's
  own script/round-trip choices is L6; scorer-side-only parse
  failures on bytes that load cleanly today are L1.
- **L9**: reserved for cases where no agent action within the task
  information could have scored (volatile functions vs frozen gold).
  Model ignorance of gold-only facts is L9 only when the information
  is genuinely absent from the input, not merely hard to find.
