# Transparent-Capture Feasibility Experiment — Report

Zero-model, no-implementation audit over the 113 frozen default-control Python
mutators (`control_python_audit/`). No inference ran, no prompts/tasks changed,
no model-facing tools added. Question tested: can ordinary control
Python/openpyxl mutation programs be wrapped in a transparent workbook
transaction that captures observed effects into an internal `WorkbookDelta` and
faithfully reproduces them without changing agent code?

**Verdict: TRANSPARENT_CAPTURE_FEASIBLE** (with two environmental caveats below).
`transparent_capture_replay/verdict.json`. The experiment eliminates the
uncertainty it was designed to resolve; the gate was not weakened to get here
(see §6 for everything that was *not* counted).

## 1. Primary gate (PASS_CAPTURE, threshold 0.95)

| Population | n | Faithful | Rate |
|---|---|---|---|
| ELIGIBLE frozen mutators | 38 | 38 | **1.00** |

All 38 capture verdicts are exact-or-equivalent with zero failures/partials
(`_gate.json`, `_per_mutator.json`). Fidelity over all 102 replayed files:
70 F0 byte-exact, 32 F0-false-but-F1/F2-exact (zip/save normalization only),
**zero** files with F1 part diffs, **zero** with F2 state diffs after a
documented comparator-bugfix recompute (§5). 104/113 mutators captured OK;
8 produced no xlsx change (nothing to capture); 1 capture exception
(INELIGIBLE, prior turn failed — §5).

Eligibility over all 113: 38 ELIGIBLE, 14 ELIGIBLE_PARTIAL (both sides errored
identically — exception-effects analysis only), 48 INELIGIBLE (replay/archive
divergence: exit mismatch, uncertain state), 13 INELIGIBLE_ENV_LO (divergence
via broken LibreOffice in this sandbox). `_eligibility.json`.

## 2. Phase-0 reference check (replay vs archived container output, 71 trajectories)

| Class | n |
|---|---|
| REPLAY_EXACT (0 state diffs) | 62 |
| REPLAY_EQUIVALENT (only environmental noise, §3) | 6 |
| REPLAY_DIFF (attributed, §4) | 2 |
| NO_ARCHIVED_OUTPUT | 1 (P-C viz task, no archived file exists) |

`phase0_results.json`. The 6 equivalents carry 2–8 noise sections each
(cells/styles/dims all classified noise by the rules in §3).

## 3. Normalization ledger (each rule grounded, none assumed)

Same script ran on both sides by construction, so a literal script-set value is
byte-identical; observed skews are serializer/environment version math. Each
rule was added only after sampling raw bytes on both sides:

1. **Theme-indexed colors** (theme table incl. hlink/folHlink 10/11; stale-bg
   drop, auto→None, align defaults, builtin-format renames).
2. **Number-format unescape**: LO writes `\( \) \-` where openpyxl keeps bare
   chars; backslash is escape-only in number formats so `\X ≡ X` always.
   Unescape-then-lookup also unifies builtin 17 (`mmm-yy`) across versions.
3. **Single-cell range collapse** `I13:I13 ≡ I13` (LO expands; Excel doesn't).
4. **Default-dim presence**: LO materializes sheet-default row heights as
   explicit rows (13.0/15.0), openpyxl 3.1.5 leaves them unmaterialized; rule
   keys off each sheet's own `defaultRowHeight`, plus known Excel defaults.
5. **indexed:64 border color ≡ rgb black** (system foreground; LO resolves it
   to `FF000000`; verified at 20_05 Income Statement B10).
6. **Sub-perceptual color closeness** (per-channel ≤4/255): openpyxl 3.1 changed
   theme+tint→rgb math by 1–4 LSB (verified `E2EFDA/E2F0D9`, `E0ECD8/E0F0D9`,
   `3A3A3A/3B3838`, hyperlink blue `0563C1/0460C0` — an Office theme variant).
7. **Column-width tolerance 0.02** (MDW/pixel rounding on LO rewrite, e.g.
   24.5 vs 24.49).
8. **1-ulp float tolerance** for cached values.

## 4. The two DIFFs (both environmental, both evidenced)

**Financial_Model:20_05** (25 raw sections, 5 residual reals). All 5 pass
re-verifying evidence checks (`overrides_20_05.json`, `cap_overrides.py`;
any check fails loudly, no silent attribution):

- *O1*: turn-12 script (43 lines) touches only Cost Drivers / Ratio Analysis /
  Balance Sheet; zero dims/indent/alignment-construction ops.
- *O2 DCF DataTable*: input stores a real DataTable; replay preserves the
  `DataTableFormula` object and input-identical cached values
  (J8 = 32726762.14303546 both sides, 1 ulp); the container's older
  openpyxl+LO flattened cells to `=TABLE(...)` text and **lost all cached
  values** (archived data-only read: all `None`). Replay is strictly more
  faithful. LO-visible consequence (§7): replay shows values where archived
  shows errors/blanks — container-side loss, not capture error.
- *O3/O4 container dim loss*: Manpower col D (12.5) and DCF col H
  (8.83203125) present in input and replay, dropped by the container pipeline.
- *O5 LO indent inflation*: replay == input indents (9.0/2.0); archived
  inflated (12.0/3.0) on script-untouched sheets — known LO round-trip skew.

**Financial_Model:08_01 (P-A)**: capture fidelity F2 = 0 (capture exact), but
the agent's own script shells to `soffice --headless --convert-to xlsx` to
recalculate and inject Equity-IRR cached values (rows 35–38). This sandbox
cannot execute soffice (`Operation not permitted`), so the script aborts before
injection here while it succeeded in the container. Environmental block, not a
capture failure. Same root cause makes the F3 LO round-trip gate unrunnable
in this environment.

## 5. Prototype bugs vs architectural falsifiers (Q13)

- *Prototype bug, found and fixed*: F2 state reader serialized
  `DataTableFormula` via object repr (memory addresses) → 6 phantom diffs on
  byte-identical files. Fixed with structural read; all 6 recomputed to F2n=0
  with F0/F1 unchanged (`recomputed_with_current_comparator` provenance flag).
- *No architectural falsifier observed*: zero systematic failures in ordinary
  cell/formula/style mutation across 104 captures, including 22+ true
  in-place mutations (non-creation replays) at exact/package fidelity and one
  byte-exact (`CAPTURE_EXACT`) in-place mutation.

## 6. What was NOT counted (gate integrity)

- 20_05's equivalence rests on re-verifiable override checks, not on relaxing
  the classifier: the classifier still labels it REPLAY_DIFF.
- INELIGIBLE/ENV_LO/PARTIAL mutators are excluded from the 38/38 rate and
  reported separately, not folded in.
- F3 (LO-visible identity) is reported NOT_RUNNABLE_HERE, not passed.
- The 14_05-style `mm/dd/yyyy`-vs-builtin-14 display-padding question never
  materialized in this population (the one suspected case was a mislabeled
  path); no ruling was needed and none was smuggled in.

## 7. Experiment questions (Q1–Q14, condensed)

1. **Transaction boundaries**: pre/post snapshots + per-file effect counts for
   all 104 captured mutators (`transaction_boundaries.json`).
2. **Capture completeness**: 38/38 eligible faithful; 0 gate failures.
3. **Statement-level tracing**: not needed — pre/post state diff fully
   explains all observed shapes (fills, translations-like, loop-computed);
   tracing would only matter for non-idempotent re-execution, which the
   snapshot design avoids by construction.
4. **Opaque parts**: 33 captures carried some parts opaquely (mostly
   `docProps/core.xml` timestamps; one charts/sheets case at 08_01 t42);
   final fidelity exact in all cases — opaque-but-preservable works
   (`opaque_part_results.json`).
5. **Lowering**: 26 formula-bearing deltas analyzed; **zero** translation
   families (no ≥3-template contiguous runs). Nothing in this population
   lowers to fill-programs (`lowering_diagnostic.json`).
6. **Save/reload**: 70 byte-exact, 32 normalized-exact; F0 recorded, never
   required (`save_reload_results.json`).
7. **Exception partials**: 14 both-failed-identically mutators inventoried;
   capture verdicts apply to produced files
   (`exception_partial_effects.json`).
8. **Multi-turn chains**: all 71 trajectories replayed through full turn
   sequences; finals match per §2.
9. **Multi-workbook**: 1 of 104 captured mutators spans 2 files
   (Debugging:09_09 t18, out + tmp file); both replay within-partition, no
   cross-workbook formula effects observed (`multi_workbook_results.json`).
10. **LO-visible behavior**: unrunnable here (soffice denied); cached-value
    analysis shows the only LO-visible divergence (20_05 DCF) favors replay.
11. **Translation-like fills**: none detected in 113 mutators; recognition
    question is moot for this population — and the control audit already
    showed 0 fill adoptions, so there is nothing to recognize.
12. **Invalidation map**: category-keyed, lazy, generation-guarded
    (`substrate_invalidation_map.json`): cell/formula → cells, formulas,
    fingerprints, point/range refs, reverse dependents, text anchors;
    style-only → styles-if-indexed; dims/merges/hidden/validations/CF/tables →
    sheet metadata; sheet add/remove/rename/order → everything + all refs;
    defined names → formulas + refs; opaque-part carry → no relation updatable,
    mark partition stale and recompile lazily (staleness impossible by
    construction via per-partition generation counters, not by discipline).
13. **Prototype vs falsifier**: §5 — one of each, correctly sorted.
14. **Feasible enough for live H0/H1**: yes — with the scope below.

## 8. Final synthesis

```text
WHAT CAPTURE CAN REPRESENT
  Cell values/formulas (incl. shared/array formulas, DataTable structures with
  cached values), styles (font/fill/border/align/number-format), dims, merges,
  sheet add/remove/rename/order, defined names, validations, CF, tables, and
  opaque parts (charts/drawings/docProps) by byte-carry. 104/113 mutators fully
  captured; 102/102 replayed files at F1/F2 fidelity; 70 additionally byte-exact.

WHAT MUST STAY OPAQUE
  Parts the differ has no structural reader for (chart XML, docProps
  timestamps) — carried as bytes, never interpreted. LO-executed effects
  (recalc-injected cached values) cannot be reproduced where LO cannot run;
  they are boundary events, not representable deltas.

WHAT BREAKS TRANSPARENCY
  Nothing in the method. Observed breaks are environmental: (a) sandbox without
  executable LibreOffice (08_01 cached-value injection; F3 unrunnable);
  (b) container-vs-replay library version skew (openpyxl theme-tint math,
  DataTable support, LO rewrites of builtins/indents/dims) — all classified by
  sampled evidence, never assumed. One prototype comparator bug (object-repr
  formulas) found and fixed with recompute provenance.

WHAT THIS MEANS FOR THE ARCHITECTURE
  Keep Python as the agent surface with WorkbookDelta effects underneath;
  lowering stays opt-in (this population contains zero lowering candidates, and
  the control audit showed 0 fill adoptions — there is nothing to compile);
  SQL stays hidden at L0. The transparent wrapper is justified: capture is
  complete, replay is faithful, opacity is confined to byte-carried parts.

SINGLE NEXT EXPERIMENT
  Run the live H0/H1 capability A/B **only on LO-independent tasks** (exclude
  scripts that shell to soffice, detectable statically by `soffice|libreoffice|
  subprocess.*convert` grep), since F3 LO-visible arbitration is unrunnable in
  this sandbox. The single highest-information addition: a paired LO-capable
  rerun of Financial_Model:08_01 turns 42–46 elsewhere to confirm cached-value
  injection reproduces under transparent capture.
```

## Machine-readable artifacts (`transparent_capture_replay/`)

`verdict.json`, `phase0_results.json`, `overrides_20_05.json`,
`_eligibility.json`, `_gate.json`, `_per_mutator.json`,
`fidelity_results.json`, `captured_deltas.jsonl`,
`delta_replay_results.jsonl`, `replay_integrity.json`, `population.json`,
`spec.json`, `transaction_boundaries.json`, `opaque_part_results.json`,
`save_reload_results.json`, `exception_partial_effects.json`,
`multi_workbook_results.json`, `lowering_diagnostic.json`,
`substrate_invalidation_map.json`, `failure_inventory.json`.
Scratch comparators/sandbox live under `/tmp` (`cap_state.py` holds the
normalization rules; `cap_overrides.py`, `cap_recompute.py` the evidenced
re-verifications) and are not part of the deliverable.

