# Mutation-Authoring Decomposition — Report

Zero-model descriptive/eliminative probe over the 113 frozen default-control
Python mutators. No inference, no new helpers, no runtime changes. Question:
what mutation-side Python is repetitive deterministic boilerplate, and what is
inseparable from semantic choice?

## Corpus composition (bytes of mutator source)

| Bucket | Fraction |
|---|---|
| MIXED_SEMANTIC_AND_MECHANICAL | 0.418 |
| PLUMBING_OVERHEAD (load/bind/save/verify) | 0.241 |
| PURE_MECHANICAL_APPLICATION | 0.111 |
| SEMANTIC_DOMINANT | 0.048 |
| OPAQUE_STRUCTURAL | 0.011 |
| Formatting/comments gap | 0.170 |

Evidence linkage: 101/113 SOURCE_PLUS_EXACT_DELTA, 3 effects-only, 9
source-only. Families: FM 42, Template 41, Debugging 28, Visualization 2
(separate). Decision boundaries: 35 early / 36 partial / 42 no-clean.

## Required answers

1. **Purely mechanical?** 11.1% of bytes (739 LOC): direct applies, pure
   apply loops, local write-helper calls, trivial struct writes.
2. **Mixed with semantic choice?** 41.8% (1931 LOC) — the dominant bucket:
   208 loops that read/branch/compute while writing.
3. **Clean decision boundary?** 35/113 mutators early; 36 partial; 42 none.
4. **Recurring mechanical idioms?** Explicit address batches (34 scripts /
   26 tasks / 3 families), load/mutate/save (103/63/4), coordinate conversion
   (25/14/2F+T), formula-fill-shaped loops (39/18 tasks), style copies (7/5,
   FM-only).
5. **Surviving effect verification?** Explicit batches only: formula-batch
   confirm 0.83, value-batch 0.67. Everything fill/translation-shaped
   confirms at 0.0–0.15; style copies at 0.0.
6. **Source/effect contradiction explained?** Yes: 18 scripts look like
   contiguous formula translation (f-string + loop variable) but effects
   form one template in only 2 cases (confirm 0.111, clean 0.111). The loop
   variable usually parameterizes per-cell semantic content (different
   references/branches per target), not a translated constant. The lowering
   probe's zero families was correct; the source-level count mistook
   loop-shaped code for homogeneous effects. 26/113 mutators overstate
   regularity; only 5 show effect regularity invisible in source.
7. **Helpers removing code without removing freedom?** `write_cells`,
   `write_formulas`: explicit address→content maps, agent supplies all
   decisions. 34+6 scripts, 26+4 tasks, 3/2 families, separable-site rates
   ~1.0, effect agreement 0.67/0.83, LOW risk.
8. **Internal instead?** Fills/translation: neither model-facing nor (yet)
   internal — no homogeneous families to optimize. Style copies: neither
   (agents already use copy.copy; effects heterogeneous). Load/save: neither
   (2–4 LOC; hiding file identity risks more than it saves).
9. **Already solved by stdlib?** Style copy → copy.copy (NO_ACTION, already
   used). Coordinate conversion → get_column_letter (NO_ACTION). Translation
   → Translator (DOCUMENT, but moot after rejection). Batch writes have no
   stdlib equivalent → HARNESS_HELPER_JUSTIFIED.
10. **Efficiency ceiling?** Viable replacement: 8,997 bytes = 4.8% of corpus
    (22 tasks). All-mechanical replacement would be 5.4% including rejected
    candidates. Token savings not claimed.
11. **Is mutation authoring the next large cost center?** No. Pure mechanical
    application is 11% of bytes and the viable helper ceiling is under 5%.
    Most apparent volume is mixed semantic computation (42%) or plumbing
    (24%). The falsification target resolved negative: mutation authoring is
    a *small, narrow* opportunity, not a large one.
12. **One live A/B?** Formula-batch helper A/B: optional `write_cells` /
    `write_formulas` explicit-map helpers (one mechanism; `write_cells`
    carries most evidence). Capability preservation first; helpers optional;
    Python fallback intact.
13. **What falsifies the branch?** Already partially falsified: fill/style
    helpers rejected on effect evidence; viable ceiling 4.8%. The branch
    survives only as the narrow batch-helper probe. If agents don't adopt
    explicit maps live (they currently inline writes or invent `s/set/put`
    locals — 236 call blocks show the invented abstraction matches), or if
    the A/B shows no work reduction, close the mutation-helper branch and
    move to verify/repair-loop behavior as the next cost center.

## Adoption note

Agents already invent this abstraction: local write helpers (`s`, `set`,
`setv`, `put`, `setf`, `cpstyle`) defined in dozens of scripts with 236
mechanical call blocks, plus edits-dict literals. A batch helper matches
invented behavior; adoption plausibility is high.

## Artifacts (`mutation_authoring_audit/`)

`population.json`, `source_effect_linkage.jsonl`,
`block_classification.jsonl`, `decision_boundaries.jsonl`,
`recurring_mutation_idioms.json`, `source_effect_reconciliation.json`,
`candidate_helpers.json`, `efficiency_ceiling.json`,
`semantic_vs_mechanical_mutation.json`, `existing_python_utilities.json`,
`helper_vs_internal_optimization.json`, `adoption_evidence.json`,
`rejected_semantic_helpers.json`, `next_experiment.json`.

```text
WHAT THE AGENT IS ACTUALLY DECIDING
  Which cells matter (header scans, row filters, conditional branches) and
  what each should contain (per-cell formula construction with distinct
  references, computed values, chart configs). 42% of bytes decide while
  writing; only 11% merely applies.

WHAT IS PURE MUTATION BOILERPLATE
  Direct address writes, pure apply loops over prebuilt maps, local
  s/set/put helpers, load/save/bind plumbing. 739 LOC of application.

WHICH PATTERNS SURVIVE EFFECT-LEVEL CHECKING
  Explicit address batches only (confirm 0.67-0.83). All fill/translation/
  style-copy shapes fail (0.0-0.15): source regularity does not survive.

WHICH HELPERS EARNED A LIVE TEST
  write_cells + write_formulas (one explicit-map mechanism). Everything
  else rejected on effect evidence or stdlib redundancy.

WHAT SHOULD STAY ORDINARY PYTHON
  All target selection, content construction, conditional mutation logic,
  chart building, and any loop that reads while writing (the 42% mixed
  core). No declarative fill syntax; no semantic builders.

WHAT SHOULD STAY INTERNAL TO THE RUNTIME
  Delta capture/replay/validation (already earned). No new internal
  mutation optimization is justified: no homogeneous effect families exist
  to exploit.

NEXT LARGEST DETERMINISTIC COST CENTER
  Within authoring: none large remains (plumbing 24% is diffuse 2-4 LOC
  fragments, not a helper). Next probe after the batch A/B: verify/repair
  loops and reopen cycles (behavioral; needs live measurement).

SINGLE NEXT EXPERIMENT
  Formula-batch helper A/B: optional write_cells/write_formulas explicit
  maps, capability-gated, adoption-metered; close the branch on no-gain.
```
