# Phase 13 — Research Mechanism Ledger

One row per major mechanism studied in program history. Verdicts quote
the terminal evidence; "Phase-13 note" records whether the current
census reopens anything (it does not, unless stated).

| Mechanism | Original hypothesis | Evidence | Verdict | Current status | Remaining open question |
|---|---|---|---|---|---|
| Task/obligation IR | Tasks need a compiled obligation representation to drive reliable action | Authority-frontier live probes; role-aware authority census | No systematic gain; ordinary scaffold unaffected | CLOSED (final_closed_branches) | None — reopen only on repeated failure caused by missing obligation relation that ordinary agents demonstrably cannot derive |
| Edit-plan authority | A required edit plan / plan authority improves correctness | Edit-plan probes + replays | No earned authority; variance dominates | CLOSED | None |
| Planner/scheduler | Scheduling/grouping work orders beats reactive loops | Scheduler live validation, group-priority probe, static repair | Discordances resolved as variance; no systematic effect | CLOSED | None |
| Execution closure | Closing the execution unit (continuations) fixes stalls | Execution-unit probes, closure transfer audit | No attributable gain | CLOSED | None |
| Program-group runtime | Program-group lowering/exactness improves outcomes | Program-group probes, exactness/cost studies | No earned lowering | CLOSED | None — opt-in lowering stays frozen, unintegrated |
| Model-facing SQL / compiled cognition | SQL retrieval surface beats Python inspection | Hybrid SQL probe, relational retrieval, calc_query sidecar (CONTEXT_USEFUL_BUT_ADOPTION_LIMITED) | Useful when used; adoption minimal; no score effect | CLOSED as default surface | None |
| Dependency-as-intent | Dependency structure expresses intent and should be surfaced | Dependency GLM/selection probes; Ph11 DEP reachability (0% systematic extraction, hand-trace when forced) | Real facts, not decision-bearing standalone; one-hop accessory at most | CLOSED as standalone surface | Reopen only if corpus shows repeated failure caused by a missing exact dependency relation that discriminates the correct action |
| Formula fingerprint as program-choice authority | Fingerprint similarity should authorize program choice | Formula index / ambient / frontier probes | No earned authority | CLOSED | None |
| Generic context compression | Compressed/compact evidence preserves outcomes at lower cost | COMPACT_ENCODING_NO_RESOURCE_GAIN (14.5% tokens, 5/16 timeouts vs 0/16); compiled-context sidecar (no score effect) | Not earned; timeouts added | CLOSED | None |
| Persistent context state for token savings | Persisted state across calls saves tokens | Token-claim discovery, affordance discovery; thin checkpoint: −10% tokens unattributable (salience, not mechanism) | No attributable saving | CLOSED | None |
| Reference handles as default abstraction | Delta/reference handles should replace direct state | Reference/delta branches in closure ledger | No earned default | CLOSED (reference-only survives only as narrow product fallback path) | None |
| Required mutation IR | Mutations must go through a required IR | Mutation authoring audit; batch-write helper A/B (0/13 C1 runs invoked helper; hand-rolled loops preferred) | Zero adoption on exactly-selected tasks; capability preserved trivially | CLOSED | None |
| Broad projection / context-selector work (Track C) | Large first-seen context contains a safe mechanical cut | Track C audit: C0/C1≈1.65%, C2≈1.68%; no no-hindsight selector met gate | CLOSED | CLOSED | None — oracle mass does not earn projection machinery |
| Formula family (as surface) | Family membership is decision-bearing signal | Ph11: near-universal (85/87), computed 8%; GENERIC throughout, no discriminator | Infrastructure for uniformity detection, never a surface | CLOSED as surface | None |
| Temporal relations (standalone) | Period maps drive period choice | Ph11: present 51%, parsed 16%; no discriminator demonstrated | Bundle-only accessory | CLOSED as standalone | None |
| Output-role relations | Twin-block/role analogy fixes failures | Ph11: present 53%, compared 1%; "missed but useless" archetype | REJECTED | CLOSED | None |
| Context redundancy | Redundant context can be mechanically removed | Repetition census: measured repetition small; thin checkpoint salience finding | No earned cut | CLOSED | None |
| Derivation elision | Eliding derivations preserves outcomes | Derivation/elision branches in closure ledger | No earned elision | CLOSED | None |
| Helper tooling (search/inspect/periods) | Deterministic helpers displace inspection work | Stage B INSPECTION_HELPERS_EFFICIENCY_EARNED (narrow, FM-only adoption); thin checkpoint: 4/24 runs, FM-only, no arm-level gain; batch helpers zero adoption | Narrow mechanism real (FM search/inspect); no arm-level efficiency gain; batch writers dead | CLOSED as research direction; helpers serve reference openpyxl in product | None — Ph13 finds inspection loops persist, but Stage-B-verified helpers did not move arm-level outcomes, so re-proposing them repeats a closed hypothesis |
| Persistent read acceleration (Candidate A+A1) | Narrow direct reads pay on the workload tail | 51/51 exact traces; representative contact 59/282 loads; tail economics supported narrowly | EARNED narrowly; productized as rc2 direct-read engine | PRODUCTIZED (not research-open) | None for research; engineering owns tail measurement |
| Reference-only product path | Uncertain scripts must keep working via fallback | rc2 negative admission + lazy reference fallback, receipt-recorded | VALIDATED in product | PRODUCTIZED | None |
| Post-edit derived-evidence verifier | Diagnostic block at submit boundary fixes damage | Ph11 existence frontier → Ph12 live A/B: behaviorally potent but K3 FIRED (100% TRUE-BUT-BENIGN); effect = recalc prompting, ~zero genuine formula fixes | D — DEMOTE (scaffold recalc fix, not a product) | CLOSED, do not revive | None |
| Recalc/evaluator boundary | Score loss is partly stale-cache artifact | Ph12 mechanism decomposition (RC_C reproduces effect); Ph12R: P1 0 recoveries (archived baseline stands); P2 46 strong cache-only recoveries (research-endpoint effect, Template-concentrated) | Real in research endpoints; NOT a broad archived-baseline correction; recalc-fair policy required going forward | CLOSED as reinterpretation; OPEN as evaluation policy (must be declared per study) | Narrow: future formula-behavior research declares a compatible recalc-fair boundary before model calls |
| Formula-error feedback | Surfacing formula errors mid-task improves repair | FORMULA_ERROR_FEEDBACK_INCONCLUSIVE; delivery-timing probes | INCONCLUSIVE, frozen unintegrated | FROZEN (not closed, not open-by-default) | Reopen only with a powered recalc-fair design + evidence that error-blindness causes current failures (Ph13: error-blindness not observed as a primary cause) |
| Uniformity-flag transfer / output-role break localization | Transfer Ph11 D3 flags into live loop | Frozen at architecture freeze; Ph12 UNIF value-sensitivity (self-contradiction across recalc states) | FROZEN; Ph12 weakened the semantic-stability premise | FROZEN | None — Ph13 finds no uniformity-shaped residual demanding it |

## Anti-repetition index (new names for old hypotheses)

| If a candidate sounds like… | It is probably… | Status |
|---|---|---|
| "show the agent what changed / damage report" | post-edit verifier (Ph12 D) | CLOSED |
| "give the agent dependencies / formula graph" | dependency-as-intent | CLOSED |
| "compress the context / smart observation" | generic compression / Track C | CLOSED |
| "helper tools for reading/writing" | Stage-B helpers / batch writers | CLOSED (narrow FM effect already measured; arm-level gain absent) |
| "plan before acting / structured edits" | edit-plan authority / program groups | CLOSED |
| "cache the reads / persistent index" | Candidate A / substrate | PRODUCTIZED; no research reopen |
| "the scores are wrong, recount" | recalc reinterpretation | CLOSED for archives; policy-only going forward |
| "detect errors and tell the agent" | formula-error feedback | FROZEN; needs powered recalc-fair design + demonstrated current-cause |
