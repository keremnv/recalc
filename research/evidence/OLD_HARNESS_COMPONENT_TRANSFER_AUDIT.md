# Old-Harness Component Transfer Audit

Zero-model, no-implementation architecture audit. No live model inference was run for this audit, no benchmark architecture was changed, no prompts were optimized, no broad benchmark was started. All numbers below come from committed reports, frozen experiment artifacts, git history (89 commits, full history), and new deterministic static analysis performed for this audit (notably a mechanical census of 707 reconstructed default-agent control scripts).

Headline: the full old architecture failed against the loose control scaffold, and most of its celebrated repair mechanisms fixed failures the architecture itself created. A small set of mechanisms has genuine isolated evidence and earns a narrow, non-semantic role. The proposed new architecture (general agent + compiled substrate + optional queries + mutation IR + deterministic runtime) survives review only in part: its substrate, runtime, and diagnostics layers are earned, but the structured Mutation IR as a required thin waist is the least-evidenced part of the proposal, with measured adoption resistance and a representability gap. Transparent interception (Architecture D) is the evidence-favored alternative if the forced-IR test fails.

Machine-readable companion: [`architecture_transfer_audit/`](../history/architecture_transfer_audit) (`component_ledger.json`, `evidence_index.json`, `implementation_map.json`, `architecture_induced_failures.json`, `layer_mapping.json`, `control_mutation_census.json`, `control_efficiency_census.json`, `architecture_tradeoffs.json`, `falsification_findings.json`, `narrow_transfer_candidates.json`, `next_experiment.json`).

## 1. Which old harness components have strong isolated evidence?

Strong meaning: a frozen, single-variable test with raw artifacts in the checkout.

- **Deterministic formula translation.** Zero translation failures across Phase C; static preflight (relative/absolute/mixed/cross-sheet, no-writes-outside-targets, typed shared-master reject, determinism) passes; Phase C gains (5/19 vs 2/19 exact, 71→152 scorer cells on 08_03 C69, all 83 gained cells exact, zero lost). Pure function of (program, source, target).
- **Formula fingerprints with the conservative design.** Opaque singletons for unsupported syntax forbid false equivalence by construction; preflight availability measurement (10/34 exact, 24/34 shape; M0+M1+M2 reaches 7/10 for 31 candidates vs the 471 whole-workbook ceiling) is fully reproducible offline.
- **Temporal coordinates on one causal bridge.** 13_05 O1 planner authority 0/5→5/5 recall, 0→1.0 precision, paired live probe with all else held equal (`TEMPORAL_INTEGRATION_CASHES_OUT`).
- **Parser / reference extraction.** 28/34 gold operands materialized; OFFSET-aware; nonempty closure for all 14 wrong-value seeds.
- **Writer / LibreOffice bridge.** 625/628 scheduled writes persisted; 12/12 feasibility outputs recalculated healthy; the Debugging zero is model damage, not translation.
- **Commit-gate diagnostics as detectors.** Loop closed once live (10_02 submit→findings→repair→resubmit); every check stronger on cheap-model output.

## 2. Which had actual capability evidence?

Distinguish mechanism-level capability (a frozen A/B moved scores) from system-level (the old harness beat control — it did not).

- **Translation: YES at mechanism level.** Phase C is the only component test in the program that moved official scores with retrieval frozen and gold blind. Caveat: it ran inside the old architecture (Edit-Plan-authorized groups), and its transfer to the default agent is unproven (0 live adoptions; the 08_03 fill succeeded by hand).
- **Closure coordination: WEAK YES at mechanism level.** Closure-aware execution gained scorer credit by value in Phase B, but the funnel stage that matters — a fully correct unit — was zero at the end of Phase B, and the default-harness transfer found zero T3 candidates. Coordination is correct and cheap, but correctness-changing only via synthesis it does not control.
- **Temporal: NARROW YES.** One obligation, planner-authority level (not scored workbooks). Everything broader (O6 relations, forced queries) is null.
- **Everything else: NO.** Fingerprints, retrieval/SQL, Task IR, grounding, Edit Plan, scheduler, working sets, candidate-choice interface, verification — none has an isolated end-to-end capability gain. Candidate-choice is actively NEGATIVE as an interface.

## 3. Which had only efficiency/reliability evidence?

- **Efficiency-only (or efficiency-claimed):** fingerprints (candidate/session halving), translation (32→16 sessions, 4.17M→2.03M input tokens — same-files subset sum, exact not modelled), working-set/SQL machinery (claimed; actually NEGATIVE — 83.7% of calls, 11.25MB request bytes for 6 edits), compact encoding (14.5% tokens, but 5/16 timeouts vs 0/16 — rejected).
- **Reliability-only:** hard verifier (bounds crash found+fixed, disposition correctness, replay reachability), writer containment (120/120 executions inside authority; 7 dropped proposals all non-gold), stable IDs (cross-process determinism; hash-seed repair), scheduler liveness repair (3→49 exposed units — a correctness fix to the mechanism, not a capability gain), commit-gate checks, formula error detection, scalar/temporal/hash-seed representation repairs.
- **Characterization-only (no intervention tested):** uniformity-break/overfill taxonomy, region occupancy, boundary continuations.

## 4. Which positive mechanisms mainly repaired old-architecture failures?

Four of five investigated cases classify `ARCHITECTURE_INDUCED_PROBLEM` (details in `architecture_induced_failures.json`):

1. **Per-cell stochastic synthesis → translation.** The inconsistency was manufactured by asking the model to rediscover one program per cell in isolated sessions. The default agent never does this (08_03: 5/5 value-correct via ordinary Python). Natural residue: choosing the program once is still hard.
2. **Isolated execution → closure.** Isolation was the architecture's execution choice. The default agent authors upstream and downstream edits in one trajectory; the surviving gap is semantic (T2: wrong upstream programs), which ordering cannot fix.
3. **Giant grounding packets → SQL working sets.** The 6–8k-ID serialization per session and per-session re-materialization were design choices (`compile_bootstrap` union, `delta=None` protocol defect). The default agent has no such packets.
4. **Generated authority → closure∩authority safety.** Authority is generated by the planner and then constrains closure — a closed loop of the architecture's own making. Without Edit Plan, blank-keep over-generates 146–191 cells. Safety in the new architecture must come from validate+diff+receipt, not generated authority.
5. **Wrong-program propagation: MIXED/UNRESOLVED.** Mechanical propagation is symmetric between harness fills and agent Python loops; the live wrong-canonical test never ran (executor never invoked).

Consequence: carry mechanisms forward only where they attach to a measured default-agent cost center — never as restoration of old coordination.

## 5. Which components remain useful if all semantic authority stays with the general agent?

The narrow-transfer list (each has a cost center + a cheapest test in `narrow_transfer_candidates.json`):

- Fingerprints → read-only pattern index, optional uniformity queries, fill homogeneity gate.
- Dependency edges → optional impact/trace queries, regression-break localization. Never execution order, never model-facing authority.
- Temporal coordinates → exact period-coordinate lookup. Never target ranking.
- Translation → opt-in lowering pass: agent supplies (program, targets), runtime fills.
- Writer + recalc + diff/receipt → infrastructure.
- Verifier (minus authority check) → pre-write validation; error scan → detached post-execution diagnostics.
- SQL → hidden L0 implementation only. No model-facing retrieval API on the critical path.

Explicitly not transferred: Task IR (as runtime), grounding (as stage), Edit Plan/authority, scheduler, working-set protocol, ExecutionUnits, candidate-choice interface, in-harness synthesis.

## 6. What should the dependency graph's role be now?

Partially alive, at a lower abstraction level. Per-role verdicts:

1. **Representation: STRONGLY USEFUL (L0).** Extraction fidelity is high and relied upon by every surviving mechanism.
2. **Model-facing semantic evidence: DEAD.** Injection failed to improve missing-formula decisions; operands-in-hand still produce wrong programs (6/11 construction failures); QUERIED_BUT_WRONG_MODEL_CHOICE cases in the sidecar.
3. **Retrieval substrate: ALIVE AS HIDDEN INDEX (L0), dead as protocol.** Completeness gains are real (28/34) but the 8-query working-set protocol that delivered them is rejected (budget fragmentation, zero-growth queries).
4. **Execution coordination: DEAD.** T3=0 under the default agent; do not build the coordination runtime. The one earned compositional relation (O6 output-role path, 5/5 endpoints zero false positives) transfers as a query/diagnostic, not as coordination.

So: L0 edges, optional L1 trace/impact queries, L5 break localization. Nothing that orders, authorizes, or diagnoses-by-construction.

## 7. What should formula fingerprints' role be now?

Runtime-internal first, query-facing second, model-facing never as a correctness claim.

- The mechanical regularity established: location-relative structural equivalence with a principled refusal class (opaque singletons). Compression measured: 471→31 candidates where programs pre-exist; ~51% session/token reduction where translation applied.
- Fingerprints never improved capability themselves, and `same fingerprint` ≠ `same business meaning` (08_03: commutative operand reorder fails exact-match while value-correct — a scorer-identity lesson, not a fingerprint failure).
- Strongest future role is **runtime-internal** (homogeneity gate for fill lowering, uniformity flags) with a secondary **query-facing** role (pattern-availability questions the agent can ask but need not). The model must never be told a fingerprint class is a correctness endorsement — the candidate-choice probe proved that plausible programs convert abstentions into confident errors.

## 8. Is SQL/model-facing compiled retrieval still justified, or only the underlying compiled index?

Only the underlying index. The evidence against a model-facing retrieval API:

- Adoption: 8/13 optional runs never called `calc_query`; all four 13_05 repeats solved gold without it; `calc_translate_fill` 0 invocations.
- Where used: wrong-model-choice persistence (03_03, 16_12, 01_01), available-not-queried misses, forced-05_01 identical first miss.
- Projection discriminators: placing compiled relations directly in context did not improve decisions with headroom (Spark O6), moved GLM both ways (1 improve, 1 reversal).
- Cost: the working-set protocol consumed 83.7% of calls and starved synthesis; compact re-encoding saved 14.5% tokens and introduced timeouts.

Keep SQL as the hidden L0 implementation (it is a fine index). The one untested claim — compiled queries as an *accelerator* (time-to-evidence, capability fixed) — earns exactly one replay experiment, not an API commitment.

## 9. Is a structured Mutation IR actually the best thin waist?

Not proven, and the audit surfaces three specific wounds:

1. **Representability gap.** Of 115 reconstructed mutating scripts: 73 loop-driven fills (coverable only if the IR has a fill primitive), 17 straight-line (naturally covered), 23 style/layout + 2 zip/xml + struct ops (~22%) requiring richer semantics. A minimal declarative IR covers ~78% at pattern level and lupus cases (conditional targets, programmatic program choice, charts) are unmeasured for awkwardness.
2. **Behavioral adoption resistance.** The clearly explained fill tool was considered and then bypassed for openpyxl on 4 tasks, invoked 0 times overall. Forcing what agents demonstrably route around is a capability risk, not a simplification.
3. **The 08_04 precedent cuts the other way.** Agent-side Python propagation achieved official-exact where the harness path was never even exercised — the control's mutation surface works.

The thin waist is therefore a hypothesis with a mandatory gate, not a decision. Its best case: agent supplies (program, target set), runtime lowers — i.e., the IR as an opt-in lowering target, not a required language.

## 10. Would transparent interception preserve capability better?

Yes on the model side, with a concrete technical risk that is cheaply testable. Interception keeps Python as the programming interface (115/115 census patterns expressible by construction — the representability debate disappears), moves validate/recalc/diff/receipt underneath, and permits post-capture lowering of detected loop-fills (recovering translation's efficiency without its adoption problem). The risk — capture completeness for zip-level edits, partial failures, non-workbook side effects — is a zero-model question: replay the 707-script corpus through a capture sandbox and demand byte-identity before any live claim. No such prototype exists (`UNTESTED`), so feasibility must be demonstrated, not asserted. Experimentally it is cleaner than B/C: one executor wrap, no prompt changes, capability A/B unconfounded by learning effects.

## 11. Where does the default agent currently spend the most stochastic work on deterministic mechanics?

Ranked by the ledger + census:

1. **Workbook inspection** (largest): 527/586 inspect-only scripts re-open the workbook; 474 contain scan loops; ~1M prompt tokens and 25–50 calls per task. Re-open + full-scan-per-turn is the dominant deterministic work center.
2. **Formula-fill construction**: 68/73 loop-driven mutators build values programmatically; 443 computed assignments. This is translation's natural prey.
3. **Verification/reopen cycles**: 115 saves across 68 tasks with manual re-verification; commit diagnostics attach here.
4. **Search loops**: manual Python search; `calc_query` used 5/13 when offered.
5. Old-arch-only: retrieval serialization (11.25MB request bytes for 6 edits) — gone with the architecture, not a transfer target.

## 12. Which old component is best positioned to eliminate that work?

- Inspection → **compiled substrate reads** (persistent spine: open once, query often) + optional search/period/pattern lookups. No component has yet demonstrated this saving (UNTESTED) — it is the largest open efficiency prize and the least-evidenced transfer.
- Fill construction → **translation lowering** (exact old-arch precedent, needs adoption-safe invocation).
- Verification → **detached commit diagnostics + error scan** (loop-closed-once precedent; cap sensitivity unmeasured).
- Nothing in the old harness addresses semantic program choice — correctly, per `NOVEL_SYNTHESIS_DOMINANT`. That work stays with the model.

## 13. What evidence contradicts the current proposed architecture?

The falsification slate (`falsification_findings.json`): adoption resistance is SUPPORTED behaviorally (0 fill uses; agents route around); old positives mostly repair induced failures (SUPPORTED); minimal-IR lossiness is PARTIAL (22% richer mutations + unmeasured awkward cases); query-duplication is PARTIAL (capability-duplicate yes, latency-duplicate untested); inspection-vs-reasoning apportionment is PARTIAL (both matter, decomposition unmeasured); interception feasibility and substrate maintenance cost are UNTESTED. The architecture is not refuted — its L0/L4/L5 layers are earned — but its L3 thin waist and L1 query API are assumed, not earned.

## 14. What parts of the current architecture survive independent review?

- **L0 compiled substrate**: survives (addressing, parsing, edges, fingerprints, periods, lineage, hidden SQL). With one new obligation: freshness invariants (the program's demonstrated failure mode is stale/empty artifacts served silently — placeholder temporal DBs, scalar-omitting caches — not cost).
- **L2 agent sovereignty**: survives and hardens ("harness: computation and invariants; model: semantic choice" is the one principle with consistent evidence; every semantic-harness restoration failed).
- **L4 deterministic runtime**: survives (writer, recalc, verifier-minus-authority, translation as opt-in lowering, diff/receipt).
- **L5 diagnostics**: survives as observation layer (error scan, uniformity flags pending transfer test, finding-cap sensitivity owed).
- **L3 required Mutation IR**: does NOT survive as a requirement — demote to opt-in lowering pending the forced-boundary test.
- **L1 optional queries**: survive as options with adoption-gated retention — keep only what beats agent Python loops in the efficiency replay.
- **Architectures compared**: A is the safe baseline (lowest risk, smallest prize); C is the highest-ceiling, least-evidenced stack (two adoption gambles); D dominates B/C on capability risk while preserving their mutation-side prizes, conditional on the byte-identity capture proof; no fifth architecture is earned (E explicitly rejected — planner-first and retrieval-first variants are contradicted by the choice and projection probes).

## 15. What is the single highest-information next experiment?

**H0 vs H1 structured mutation boundary (forced)** — free-Python control vs IR-required treatment on the frozen mechanism-enriched slice, capability-gated, with a zero-model Phase 0 (lower the 115 archived mutating scripts into the candidate IR; publish the awkward-expansion inventory) and an interception shadow arm (capture-only wrapper, byte-identity gate). It eliminates B/C in one shot if capability drops or agents route around, earns the thin waist if capability holds, and de-risks D simultaneously. Full spec in `next_experiment.json`. Rationale for largest-elimination-first: representability is already ~answered zero-model by this audit; adoption resistance is measured; the only remaining unknown on the critical path is behavioral capability effect, which only forced comparison answers.

---

## WHAT SURVIVED

Parser and reference extraction; stable IDs; compiled spine as hidden index; fingerprints as index/gate (not as correctness claims); dependency edges as queries/diagnostics (not coordination); temporal coordinates as lookup (not authority); translation as opt-in lowering (not capability mechanism); writer + LibreOffice recalc; verifier minus authority; commit diagnostics detached from submit; the agent-sovereignty principle itself.

## WHAT DIED

Task IR, grounding stage, Edit Plan/authority, scheduler, working-set/retrieval protocol, ExecutionUnits, candidate-first choice interface, in-harness synthesis, model-facing SQL API, execution coordination runtime, compact-packet re-encoding, and the proposition that the old positives transfer as a system.

## WHAT MOVED TO A LOWER LAYER

Everything that survived moved down: authority → deleted; cognition → queries; coordination → diagnostics; requirements → opt-in lowering; SQL → hidden implementation. The pattern is uniform: mechanisms keep their mechanics and lose their vote. No surviving component retains semantic authority, target selection, program choice, or execution ordering.

## WHAT WE STILL DO NOT KNOW

Whether a required Mutation IR preserves capability (the forced-boundary test); whether interception capture is complete (byte-identity replay); whether compiled reads actually beat agent Python loops on time-to-evidence (efficiency replay); whether uniformity flags predict official misses (transfer test); whether the 12-finding cap bound the one closed loop (cap sensitivity); how inspection vs reasoning apportion the ~1M prompt tokens per task (work-center decomposition); and what substrate freshness invariants cost (staleness, not compute, is the demonstrated risk).

---

## Evidence-supported architecture (post-audit)

```text
                        L2  AGENT SEMANTIC WORKSPACE (sole authority)
                        ┌──────────────────────────────────────────────┐
                        │ general coding agent: Python/openpyxl,       │
                        │ free analysis, program choice, target choice │
                        └──────┬───────────────────────────┬───────────┘
                               │ optional queries (adopt   │ explicit intent OR
                               │ or drop on merit)         │ captured mutations
                               ▼                           ▼
 L0 COMPILED SUBSTRATE   L1 OPTIONAL READ/QUERY     L3/L4  MUTATION PATH
 ┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────────────┐
 │ stable cells/ids │──▶│ period lookup        │   │ (B/C) opt-in IR lowering │
 │ formulas         │──▶│ pattern/uniformity   │   │    program + targets     │
 │ fingerprints     │──▶│ impact/trace         │   │         ── OR ──         │
 │ point/range refs │──▶│ search               │   │ (D) transparent capture: │
 │ reverse edges    │   │ program-availability │   │    snapshot → diff →     │
 │ text index       │   │   (transfer-test)    │   │    internal IR           │
 │ temporal coords  │   └──────────────────────┘   └────────────┬─────────────┘
 │ provenance       │    SQL hidden inside L0                       │
 │ (hidden SQL)     │    freshness invariants                       ▼
 └──────────────────┘                                  L4 EXECUTION RUNTIME
                                                          validate (no authority
                                                          check) → homogeneity
                                                          gate → atomic write →
                                                          structure preserve →
                                                          LibreOffice recalc →
                                                          exact diff + receipt
                                                                    │
                                                                    ▼
                                                          L5 POST-EXECUTION
                                                          DIAGNOSTICS (advisory):
                                                          error scan, uniformity
                                                          flags*, finding caps
                                                          measured (* = pending
                                                          transfer test)

 L6 RESEARCH ONLY: Task IR vocabulary, Edit Plan/authority, scheduler,
    working sets, ExecutionUnits, candidate-choice (negative result kept)
```

Design rule from the audit: a component enters L0/L1/L4/L5 only with a measured default-agent cost center attached; L3 is opt-in until the forced-boundary test says otherwise; anything requiring semantic authority stays in L6.
