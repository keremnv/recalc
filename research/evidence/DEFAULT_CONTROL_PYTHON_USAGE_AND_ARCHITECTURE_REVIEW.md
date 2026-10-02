# Default Control Python Usage and Architecture Review

Zero-model study: no harness implemented, no model inference, no prompt or benchmark-code changes. Evidence: 71 frozen control trajectories (9 matched GLM C0 + 60 historical GLM control + 2 viz, kept separate), 1,210 turns, 309 recovered Python sources (~302KB / 7,783 LOC), official scores for all 60 historical runs, plus deterministic AST/static analysis with documented mechanical rules. The prior audit's 707-script reconstructed corpus is used only for comparison after the freeze.

Artifacts: [`control_python_audit/`](../history/control_python_audit) — `population.json`, `artifact_integrity.json`, `python_executions.jsonl` (1,210), `script_features.jsonl`, `purpose_classification.jsonl`, `semantic_vs_mechanical.jsonl`, `mutation_shapes.jsonl` (113 mutators), `recurring_patterns.json`, `deterministic_work_census.json`, `ir_representability.json`, `capture_suitability.json`, `compiled_substrate_substitution.json`, `old_component_transfer.json`, `architecture_tradeoffs.json`, `architecture_falsifiers.json`, `recommended_architecture.json`, `next_experiment.json`. Probe scripts (scratch, not deliverables): `/tmp/extract_control_python.py`, `/tmp/analyze_control_python.py`, `/tmp/mutation_shapes.py`, `/tmp/work_and_substitution.py`.

Population integrity: 9/9 primary and 60/60 historical trajectories present with sha-pinned `.traj` files; outputs present per `artifact_integrity.json`; repeated runs never mixed (r1 only); viz reported separately. Missing: `python3 /tmp/*.py` file-form executions whose sources were created inside the container and not retained (20 turns); their creating heredocs are usually captured. Sixty-run scores: 60/60 scored, 6 exact, mean modification 0.6691.

## Answers to the ten primary questions

1. **What is Python used for?** Inspection dominates (300 WORKBOOK_INSPECTION labels), then verification (138), text search (124, Debugging-heavy), mutation (113), formula construction (106), submission prep (98), period search (81), semantic calculation (58). Non-Python turns: 183 view_xlsx, 70 submit, ~600 trivial shell/file ops.
2. **Semantics vs mechanics?** Python with source: 228 MECHANICAL / 71 MIXED / 10 UNRESOLVED — and zero pure-SEMANTIC, because semantic decisions are always embedded in mechanical Python (offsets, mappings, candidate tests). Exec-level: 1,000 / 71 / 139.
3. **Natural abstractions?** Period-header search (65 scripts/39 tasks, the largest inspection pattern), reopen-verify (52/20), formula-chain prints (45/18), sheet enumeration (46/12), text scans (36/11), two-workbook diffs (34/16), translated-formula generation (26/14), hand-rolled column arithmetic (19/8), formula maps (7/3), zip/XML surgery (17/8). Cross-task recurrence is the bar — all clear it.
4. **Construct frequencies?** Loops dominate inspection and mutation; 24 FORMULA_TRANSLATION_LIKE mutators; 19 scripts reimplement column-letter arithmetic despite `openpyxl.utils`; funcdefs cluster in XML-surgery scripts; pandas/numpy ~absent (agents use list-comps + openpyxl); conditionals gate 21 mutators (+COND shapes).
5. **Simple vs programmatic?** Of 113 mutators: 15 AGENT_KNOWS_EXACT_EDITS, 67 mixed static-template/dynamic-targets, 31 PYTHON_DETERMINES_EDITS. Straight-line concrete batches are rare (14); loop-applied templates are the norm (61 fill-family, 24 translation-like).
6. **Safely replaceable?** Save/recalc/verify/diff cycles (106/63 + 52/20 + 34/16), period/search lookups (65/39, 36/11), coordinate utilities (19/8), translation lowering (24) — all without touching choices.
7. **Awkward under a small IR?** 39% of mutators: 29 REPRESENTABLE_BUT_AWKWARD (conditionals, content-derived values needing inspect-then-stage, style mixes), 7 REQUIRES_RICHER_IR (content-discovered targets, style-only, structure), 8 NOT_EFFECT_IR_FRIENDLY (zip/XML). Plus 31 PYTHON_DETERMINES_EDITS cases that a declarative waist must split or exclude.
8. **Interception vs DSL?** Capture: 82 EASY / 17 NORMALIZATION / 14 OPAQUE-preservable / 0 DIFFICULT. Interception preserves 100% of the surface including the IR-hostile 39%; the DSL covers 61% naturally. Behavior favors interception.
9. **Substrate substitution?** EXACTLY replaceable: sheet lookup, text search, chain prints, col arithmetic, two-workbook diff, style-fact reads. MOSTLY: period lookup, reopen-verify, save/recalc, formula maps. PARTIALLY (facts yes, choice no): fills, translation, style choice. NOT: concrete values, zip/XML surgery.
10. **Independent choice?** E: transparent capture + compiled read acceleration, with C-helpers adoption-gated and B demoted to opt-in lowering. Ordering by capability risk: A < C < E < D < B.

## Second-opinion questions (condensed)

Python is the agent's natural language (309 scripts, hard tasks stay in Python — they escalate to zip/XML, not out of it); it buys both mechanics and embedded semantics; a required DSL removes real freedom (39% awkward-or-worse + measured adoption resistance); interception preserves control properties better; the internal representation must describe **observed effects** (intent is unobservable when Python determines edits — 31 cases); `WorkbookDelta` fits as the internal IR with cell effects + normalized structural diff + opaque package deltas; translation should be **inferred from captured repeated writes** (24 translation-like mutators say the pattern is detectable) with an explicit helper as backup, never required; indexes stay internal or optional-helper (dependency vocabulary is 0x; projection probes already rejected direct exposure); helpers justified by frequency: `periods()`, `search()`, `fill_formula()`, `references()` last and uptake-gated; concrete values, conditional targets, style choice, XML surgery, and semantic computation stay ordinary Python. Smallest architecture covering most prize: D's transaction boundary + runtime (absorbs ~106 save/recalc + 77 verify/diff loops + 68 agent soffice runs) with E's read acceleration for the inspection center (298 opens). Falsifiers are listed in `architecture_falsifiers.json` — sharpest: byte-identity replay failing on >5% of mutators kills D; forced-IR H1 matching H0 kills the effects-first claim.

## WHAT THE CONTROL ACTUALLY DOES WITH PYTHON

It runs a REPL loop of open → scan → compute → write → re-read → recalc → submit. Inspection is programmatic (list-comps over explicit ranges, regexes over labels/headers, formula-chain prints, two-workbook diffs), mutation is template-driven (one f-string program instantiated across a range with column arithmetic), verification is manual (reopen, compare, soffice recalc by hand), and hard cases escalate down the abstraction stack (openpyxl → hand-rolled helpers → raw zip/XML with regex surgery) rather than asking for new tools. It builds its own ephemeral abstractions per task — formula maps, col helpers, norm functions — instead of reusing libraries, and it patches its own scripts with sed and reruns them.

## WHAT PYTHON IS BUYING THE MODEL

Three things inseparably: (a) a query language for workbook facts (scans, searches, chain prints); (b) a reasoning scratchpad where semantic decisions take executable form (offset arithmetic with comments, mapping dicts, candidate comparisons, conditional row choice — 71 MIXED scripts, 58 semantic-calculation labels); (c) the only mutation surface, from one-cell sets to package surgery. The scratchpad function is why a DSL requirement is dangerous: 31 mutators compute *what the edits are* inside Python, and intent cannot be declared before it is computed.

## WHAT IS PURE MECHANICAL REIMPLEMENTATION

Reopening workbooks every turn (298 opens), full scans (36), period regexes (65/39), text scans (36/11), column-arithmetic helpers (19/8), save/recalc/reopen cycles (106/63), hand diffs (34/16), agent-run soffice recalcs (68), expected-vs-actual print loops. None of this reasons; it plumbs.

## WHAT CAN SAFELY MOVE UNDER THE MODEL

The transaction boundary (snapshot → WorkbookDelta → validate → preserve → recalc → diff → receipt) absorbs the save/verify/recalc/diff center with zero freedom cost; compiled-index reads absorb sheet/text/period/chain lookups; transparent lowering absorbs the 24 translation-like fills once detected; three tiny helpers (`periods`, `search`, `fill_formula`) absorb the most frequent hand-rolled code, uptake-gated. Total: the plumbing majority of ~302KB of agent Python, with choices untouched.

## WHAT SHOULD REMAIN PYTHON

Task content (concrete values), content-discovered and conditional targets, style/layout choice, zip/XML surgery (preserved opaquely, never normalized), semantic calculations and candidate testing, and any inspection the agent prefers to do by hand. Also deliberately: dependency-graph construction (agents don't do it — 0x — so a trace helper would be additive, and must prove uptake rather than assume it).

## SECOND OPINION ON THE ARCHITECTURE

The evidence supports E, recommends C as complement, demotes B, keeps A as fallback, rejects F. The prior audit's hypothesis — Python stays agent-facing, structure describes captured effects underneath — is confirmed by control behavior, with one correction: the prior diagram under-weighted optional helpers (agents demonstrably want callable utilities, not just queries) and over-trusted transparent read substitution (staleness is the substrate's demonstrated failure mode; freshness invariants come first). Interception was stress-tested, not favored: 9 save/reload chains (must be single transactions), 14 opaque deltas (byte-preserve, don't normalize), 5 try-around-write scripts (per-statement attribution), 2 multi-workbook trajectories, 1 broad (>500-cell) mutation — all quantified in `deterministic_work_census.json`.

## SINGLE NEXT EXPERIMENT

**Zero-model transparent capture replay** (`next_experiment.json`): replay the 113 archived mutators through snapshot→WorkbookDelta capture; gates are byte-identity vs archived outputs, single-transaction chains, byte-identical opaque deltas, per-statement attribution. Pass (≥95%) unlocks the live H0-vs-capture capability test; fail adopts A+C with no live budget spent. It resolves the architectural uncertainty (can D work at all?) instead of collecting more statistics.

## Evidence-supported architecture

```text
TASK
 ↓
GENERAL AGENT — normal Python/openpyxl (only surface; 309 scripts prove it suffices)
 ├── semantic computation (ratios, mappings, candidates, conditional choice) — stays
 ├── hand inspection (scans, prints, diffs) — stays, accelerated optionally
 └── mutation (fills → package surgery) — stays, captured
 ↓  TRANSPARENT TRANSACTION BOUNDARY (no new language)
 scratch workbook → WorkbookDelta (OBSERVED EFFECTS)
   ├── cell effects (82/113 EASY)
   ├── normalized structural diff (17: styles, merges, sheets, dims)
   └── opaque package delta, byte-preserved (14: charts, names, zip/XML)
 ↓
DETERMINISTIC RUNTIME — validate (no authority check) → preserve →
recalc (absorbs 68 agent soffice runs) → diff → receipt + advisory diagnostics
 ↓ transparent optimizations: captured-fill lowering (24 patterns); compiled reads
 OPTIONAL HELPERS (uptake-gated): periods() [65/39] · search() [36/11] ·
 fill_formula() [24+19] · references() [additive, must prove uptake]
SUBSTRATE (hidden SQL, freshness invariants first): cells · formulas ·
fingerprints · edges · text · periods · provenance
L6 (not reconsidered — 0x vocabulary in control): Task IR, Edit Plan,
scheduler, retrieval protocol, ExecutionUnits, semantic authority
```

Rule: every box below the agent names the counted control behavior that pays for it; nothing model-facing is required; what Python determines (31 edits-cases) is captured, never pre-declared.
