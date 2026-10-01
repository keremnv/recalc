# Phase 13 — Architecture Decision Ledger

| Choice | Why adopted / rejected | Evidence | Scope | Reopen condition |
|---|---|---|---|---|
| Ordinary Python as agent language; no DSL | Agents succeed with it; no structured waist required; helpers bypassed | Thin checkpoint neutrality; batch-helper 0 adoption; Ph13 successes use plain openpyxl | Tested agents | A new agent class that systematically fails at openpyxl mechanics |
| No required IR / edit plans / scheduler / program groups | No earned authority; variance explains discordances | Authority/scheduler/program-group probes; closure ledger | Runtime architecture | Repeated failure caused by missing plan structure that a preregistered probe shows an IR fixes |
| Narrow direct-read engine (rc2) | Exact on earned surface; tail value | A1 traces; representative economics | Admitted primitives; fail-closed fallback | Read-architecture failures specifically implicating it (none in Ph13) |
| Persistent artifact cache (content-keyed) | Safe derived state; rebuild-on-change | Freshness invariant; rc2 validation | Cache correctness, not token claims | Staleness incident |
| External observer (native, pre/post snapshots) | Cheap assurance; survives abrupt exits | Capture studies; rc2 observer tests | Assurance only, never correctness verdicts | Observer-missed corruption with prevention witness |
| Reference fallback for uncertain scripts | Preserves semantics; never vetoes valid work | Fail-closed replay; corrective gate | All non-admitted execution | Substrate veto incident |
| No derived post-edit verifier in product | Behaviorally potent but diagnostically void (100% benign) | Ph12 K3 + success-rule failure; D-demote | Product surface | A new verifier with predeclared benign-rate gate passing live (bar: ≤50% benign + paired exact gain) |
| No broad context compressor | No gain; added timeouts | Compact encoding; sidecar; Track C | Runtime | A no-hindsight selector meeting reduction/recall gates on fresh tasks |
| No persistent token-saving state | Savings unattributable (salience) | Token discovery; thin attribution | Runtime | Attributable per-mechanism token saving with capability preserved |
| Recalc-fair research evaluation policy | Endpoint measured hygiene as much as competence | Ph12 §22; Ph12R | All future formula-behavior research | Never — policy, not hypothesis; compatible boundaries declared per study |
| Harness recalc-before-submit (scaffold, not product) | Real sham-separated effect via hygiene | Ph12 D-demote follow-on (i) | Scaffold hygiene | Already directed; implement as scaffold fix |
| No model-facing SQL / calc_query default | Useful-but-unadopted; no score effect | Sidecar A/B | Default surface | Adoption + score effect in a powered trial |
| Helpers on reference openpyxl (optional surface) | Substrate backend earned nothing; surface unchanged | Freeze backend removal; batch/Stage-B adoption data | Optional surface | Product need + adoption evidence |
| Linux-first product posture | Test matrix + packaging scope | rc2 release validation | Initial release | Platform expansion decision (not research) |

## Decision principles (carried forward)

1. Retain-vs-rebuild are different decisions; sunk implementation
   earns nothing.
2. Missingness alone is not value (Ph11 output-role archetype).
3. Behavioral potency is not diagnostic value (Ph12 lesson).
4. Score movement is not mechanism proof until the cache channel is
   closed (Ph12R lesson).
5. Do not build the next abstraction until the unexplained loss mass
   earns it (Ph13 rule).
