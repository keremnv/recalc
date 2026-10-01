# Authority frontier: compiled-world fidelity before new representations

**Decision:** repair the incomplete integration of the already-earned temporal world first. That defect is now repaired, along with percentage-as-year parsing and hash-dependent evidence selection. Then investigate task-to-target roles with a small contrast set; do not implement a general scope-to-authority rule. **Zero new model calls; no FM20 A/B; no benchmark workbook or frozen cache modifications.**

This report qualifies both `REMAINING_LOSS_PROBE_REPORT.md` and `SCHEDULER_STATIC_REPAIR_REVIEW.md`. Their archived observations remain valid; the later review had not checked whether the earlier temporal repair actually reached the credit-restored runner. The temporal repair existed in private replay artifacts, but its integration into live planning was incomplete.

## 1. Investigation and evidence

The probe covers the eleven-task credit-restored population, with **72 obligations across ten successful Task IR outputs**. 17_05 remains an explicit missing-IR provider response. It reuses all saved IR, plan fragments, packets and responses; evaluator labels come only from the existing 27-obligation annotations on 03_01, 05_01, 13_05 and 15_05. Those annotations overlap and do not cover every evaluator difference. No new target-ranking algorithm or semantic judge was introduced.

`benchmark/authority_frontier_probe.py` reconstructs the archived target sets, constructs counterfactual packets from the existing repaired temporal database, and re-expands unchanged saved plans. A separate shadow measurement sends exact existing scope spans through the existing lexical matcher; its hits never become subjects or edit authority. Baseline replay uses the retained `authority_frontier_probe/baseline_workbook_grounding.py` snapshot. Source file hashes are checked before and after the probe.

Artifacts in `authority_frontier_probe/`:

- `obligation_lineage.csv`: all 72 obligations, fields, shard context, missing structural referents, packet variants, target-set deltas, evaluator intersections, and prior loss labels.
- `summary.json`, `source_hashes.json`: counts, database lineage, and unchanged-response expansion results.
- `scope_label_shadow.json`: all scope queries and extra lexical hits, including misleading matches.
- `hash_seed_evidence.json`: the complete before/after 15_05 O2 evidence sets for two Python hash seeds.
- `current_ir_ledger_recheck.json`, `historical_scope_anaphora_flags.json`: checks against the existing task-only ledger and historical GLM outputs.
- `distinction_cases.csv`: concrete cases separated by the seven requested loss boundaries, plus unresolved role interpretation.
- `runtime_repair.patch`, `validation.json`, `pre_repair_regression_results.txt`: isolated runtime changes and validation.

## 2. Newly demonstrated implementation defects and repairs

### A. The repaired temporal world was not the live planning world

The original `prep/temporal` files are empty placeholders for **all twenty Financial_Model tasks**. Their original SQLite databases also contain zero temporal coordinates. The earlier integration repair populated `integration_autopsy/repaired_temporal` and `integration_autopsy/repaired_db`; those facts are real, input-derived and already available.

| Task | Original DB coordinates | Repaired DB coordinates |
|---|---:|---:|
| 04_01 | 0 | 3,924 |
| 05_01 | 0 | 925 |
| 08_01 | 0 | 1,069 |
| 12_05 | 0 | 225 |
| 13_05 | 0 | 338 |
| 15_05 | 0 | 158 |

Three exact boundaries explain the gap:

| File / function | Before | Repair |
|---|---|---|
| `benchmark/fm_resource_feasibility.py::run_treatment_task` | Configured the repaired stochastic profile but left `m.DATABASES` at original `prep/db`. The older matched-run entry point did select the repaired DB; this entry point did not. | Selects `integration_autopsy/repaired_db` explicitly, refuses a missing database before starting work, and restores the previous path on return or exception. |
| `benchmark/matched_compiled_treatment.py::_plan_task_sharded`, `_plan_task` | `World` supplied expansion identities, while grounding separately loaded the original spine's local `periods`. Even selecting a repaired DB did not project its temporal closure into grounding. | `planning_spine_for(task_key, world)` reconstructs period records from that same `World.temporal` relation and reuses the existing `overlay_periods`. All planner modes and fallback packet construction use this view. No temporal inference rule changes. |
| `benchmark/matched_compiled_treatment.py::build_environment` | `if not temporal_path.exists()` treated an empty historical placeholder as a completed compiler result. An explicit rebuild could silently preserve it. | Recognizes a completed readable closure result rather than mere path existence. Explicit environment rebuilds recompile placeholders. A legitimate completed empty result is still reusable. |

**Persisted example:** 13_05 Input Sheet FY26–FY30 already exists at I5:M5 in the repaired temporal data. The old O1 packet's period records instead came from another matched sheet and offered no gold growth targets. Restoring the temporal world adds all five growth targets to candidates. O1's planner response was a timeout, so this is evidence recovery, not proof of corrected model selection.

The old default prep files remain frozen. The repaired feasibility entry point now routes to the populated DB. The historical default configuration is not silently migrated by a read-only helper. Existing scalar-omitting caches likewise remain frozen; testing the previous scalar fix still requires isolated rebuilt caches. The temporal experiment keeps that cache lineage explicit.

### B. Typed percentages were parsed as calendar years

`workbook_grounding.py::parse_scope_spec` passed the entire scope through `YEAR_TOKEN`. In the saved 13_05 O1 scope `10% FY26` / `30% FY27–FY30`, `10%` contributed year 2010. The min/max interval then became **2010–2030**, instead of 2026–2030.

The parser now excludes explicitly percent-marked numeric spans from period extraction while retaining the raw scope. This is a lexical type correction, not financial semantics. In the historical 100-task GLM archive, it changes two task outputs: 13_01 and 13_05. On 13_01, rates such as 40% had extended the inferred interval through 2040.

On 13_05 O1 with the repaired temporal world held fixed, this correction reduces target candidates **320 → 161**, retaining all five annotated gold targets. It does not interpret rates, select a row, or produce formulas.

### C. A deterministic packet depended on Python's hash seed

`workbook_grounding.py::project_obligation` used `targets[:200]` to select dependency evidence after `compose_targets` iterated sets. On actual 15_05 O2, independent processes with hash seeds 1 and 2 produced the **same 294 target candidates**, but their eighty dependency records shared only **67** records: thirteen were replaced, a symmetric difference of 26.

Target IDs are now sorted before the existing bound. Both processes produce identical eighty-record dependency packets. This is stable set serialization before an existing limit, not a new relevance ranking. The eighty-fact and two-hundred-target limits remain unchanged. Their coverage sufficiency is a separate question. This defect demonstrates unstable evidence membership; it does not establish that one of those omitted facts caused the observed wrong plan.

## 3. What the zero-model intervention establishes

- All **72 archived target sets** reproduce extensionally with the pre-repair grounder. One packet's dependency membership differs under replay because of the hash-order defect above.
- Replacing the local period view with the repaired temporal world supplies different temporal evidence to **41 obligations** and changes candidate sets on **30/72** obligations. Temporal IDs change namespace to the existing compiled coordinates, so the first count is evidence-view replacement, not a recall-gain count.
- Across the **27 annotated obligations**, candidate/gold intersections rise **59 → 68**, with no annotated obligation losing a gold candidate. These are obligation-cell memberships, not unique task cells or writes; overlapping annotations remain overlapping.
- The gains are four memberships on 03_01 O1 and five on 13_05 O1. The large named tranche, growth-output and table-body misses remain.
- Re-expanding identical saved responses against the repaired DB leaves the authority of **all nine previously valid plans exactly unchanged**. This repair does not automatically widen authority.
- 12_05 remains invalid. Its temporal-endpoint error is cleared, but the same plan then fails on `cell:s10:r3:c1`, outside the compiled world. An implementation repair must not launder that model selection error.

| Task / obligation | Gold targets | Old candidate ∩ gold | Repaired candidate ∩ gold | Interpretation |
|---|---:|---:|---:|---|
| 03_01 O1 | 18 | 0 | 4 | Some temporal evidence recovered; row/program role remains incomplete. |
| 13_05 O1 | 5 | 0 | 5 | Needed compiled time facts now reach candidates; saved planner response is missing. |
| 05_01 O7 | 297 | 0 | 0 | Restored time axis cannot recover absent tranche rows. |
| 03_01 O4 | 230 | 0 | 0 | Growth output role remains absent from subject grounding. |
| 15_05 O1 | 193 | 0 | 0 | Heading-to-body relation is not established. |
| 15_05 O2 | 9 | 9 | 9 | Evidence was already sufficient for the target-region choice; saved model selected other columns. |
| 13_05 O3 | 5 | 0 | 0 | Linked-label role ambiguity is not repaired by more temporal facts. |

Validation: **139 selected tests passed**. Thirteen relevant tests fail against the pre-repair functions in an isolated process. The hash-seed counterexample also fails before the ordering repair and agrees afterward. Tests cover all three planner modes, real XLSX → temporal closure → SQLite → grounding → Edit Plan expansion, placeholder reuse, percentage parsing, runner routing and restoration, and stable bounded evidence. Scheduler, ProgramGroup, authority-expansion, temporal, retrieval and writer-related regression suites remain green. New probe/test files pass Ruff. Prompt/schema/model configuration assignments remain unchanged.

## 4. The seven loss boundaries remain distinct

### 1 — Information missing from Task IR

15_05 O3 omits the surrounding Formats locus in its own locus field, retaining only the balance-sheet/table phrase. Its other-tab matches precede planning. That is different from a sheet identity absent from the workbook.

The historical Task IR experiment reported 52% held-out GLM full-specification preservation, 81 omitted-constraint errors and 28 wrong attachments overall. Current schema validity therefore cannot establish semantic completeness. Reusing the old task-only ledger on the ten current IR outputs accepts two fully; this is a **decomposition-sensitive diagnostic**, not an 80% proven semantic-error rate. For example, it penalizes splitting the useful Dashboard rate obligations. No parser rewrite or new inheritance rule was made from that score.

### 2 — Information in IR that candidate construction does not consume in its target role

- **05_01 O7:** tranche membership is in scope; subject retrieval asks about total funds raised. Existing scope parsing consumes temporal/all quantifiers, not the entity population named by the scope.
- **01_01 O5:** Foundation Course is in scope, while subject is operational costs. A shadow query finds eleven extra labels, including source/revenue occurrences. Correct role is still necessary.
- **03_01 O4:** “year-on-year growth” is in `required_change`, while subject is “all line items.” The existing matcher, queried with that unchanged change span, finds R2 “Growth (%)”. R2 identifies an output column block; treating it as a subject row would be wrong. This is not solely a scope-field problem.
- **15_05 O4:** the metric list and below-table placement are in scope/change. Its child obligations O5/O6 specify output encodings and refer to O4. Generic logical-function subject matching misses the output block.

All **20 obligations with `then_after` edges** are sharded without the referenced obligations in `GENERATED_TASK_IR`. However, **all 72 requests retain the full raw task**, and many obligations already carry their locus correctly. Thus there are twenty absent structural referents, not twenty demonstrated semantic losses. Sequencing is not proof of inherited subject/locus/scope. Automatic copying along every edge would overreach.

### 3 — Workbook facts absent from the active compiled world

The original DB's empty temporal relation is the demonstrated case, even though the facts already exist in repaired artifacts. This is a materialization/routing defect, not a new time-encoding frontier.

For implicit table bodies, the situation differs: the reviewed 15_05 workbook has no explicit Excel Table objects establishing those bodies. Heading merges and formula runs do not alone define the task's table extent. There is no known complete table-body fact to restore.

### 4 — Compiled facts present but not projected

The repaired DB's temporal relation was not consumed by the old planning-spine path. That is now fixed. The hash-order counterexample separately shows unstable selection of already-present dependency facts under a bound.

By contrast, **13_05 B58→B25 survives the full and projected packet**. Its semantic role remains unresolved; calling it a lost edge would be incorrect. Existing bounded foregrounds and dependency caps also should not be described as complete semantic evidence merely because their remainder exists elsewhere.

### 5 — Sufficient evidence, wrong planner choice

15_05 O2 remains the clean counterexample: projected E24:M25 includes the required E25:M25 region and Net Margin label; the saved plan chooses P:X and AA:AI. 03_01 O6 similarly loses part of an available target set. 05_01 O2 has the relevant DK Total evidence but selects monthly columns; the evidence claim there is narrower than proof that every component row was fully grounded.

These remain model selection errors. No target-specific heuristic, semantic verifier or automatic authority widening was introduced.

### 6 — Missing provider/model response

The 72 saved fragment statuses comprise 45 `VALID_PLAN`, 14 `PROVIDER_TIMEOUT`, eight `TRUNCATED_NO_CONTENT`, one `EMPTY_EXPANSION`, two `INVALID_ENTITY`, and two `PARSE_FAILURE`. One parse failure is the already-identified provider `finish_reason=error`; the other contains invalid model output. Thus **23 fragments lack a usable response through timeout, truncation or provider error**, separate from the 17_05 IR timeout. A candidate improvement cannot retrospectively turn those into observed planner decisions.

### 7 — Correct authority, later loss

The earlier scheduler coverage, provider-synthesis, canonical-semantic and upstream-dependency diagnoses remain applicable. The repaired temporal/field interface does not replace that attribution. All nine valid saved authorities remain unchanged in this probe; no scheduler, ProgramGroup or writer experiment was rerun with new formulas.

## 5. Which representation distinction has earned itself?

**Already earned and now properly connected:** local/propagated temporal identity in the shared compiled world, with the same identities visible to planning and expansion. This is restoration of an established representation, not a new one. Explicit percentage units versus year tokens and stable bounded-set ordering are fidelity invariants.

**Supported as a research distinction, not yet a runtime abstraction:** a task mention's field location is different from its workbook target role. A scope can name an entity population; a change phrase can identify an output column; a label link can denote a different occurrence; a parent clause can carry context needed by a child. These counterexamples are real, but a single “search all fields and expand the hits” mechanism has not earned itself.

The exact scope-span shadow has extra hits on **16/72 obligations**. It recovers all three required 05_01 tranche-row labels, but returns fourteen extra labels across multiple rows. On 05_01 O6 it retrieves **First Tranche** despite the request for second and third tranches. On 15_05 O4 it retrieves **55 extra labels across 48 rows**, recovering none of the annotated logical-output rows. A period-only clause can also match “from” in unrelated cash-flow labels. These are concrete overreach counterexamples, not hypothetical objections.

Any proposed role representation must therefore specify:

| Requirement | What is established / still needed |
|---|---|
| Counterexamples | Tranche row population, growth output columns, parent-scoped logical outputs, linked-label occurrence, implicit table body. |
| Mechanical definition | Existing task spans → existing workbook identities, retaining field provenance and ambiguity. No hit alone establishes row/column/output/source role. The role relation itself still needs a justified definition. |
| Expected coverage | Scope search demonstrably exposes three needed tranche rows; other role recoveries are not yet established. No corpus-wide authority gain is claimed. |
| Overreach risk | Wrong tranche ordinal, wrong revenue/cost occurrence, a growth heading mistaken for a data row, input table mistaken for requested output block. |
| Existing compiled distinction | Text anchors, row/column identities, temporal coordinates and explicit dependency edges already exist. An implicit table-body or semantic alias-role relation generally does not. |

No new runtime representation was installed.

## 6. Updated architecture assessment and dominant remaining boundary

Preserve relative fingerprints, explicit authority, operation-preserving scheduling, proposal-seeded authority-intersected dependency closure, ProgramGroups, monotone working state/bootstrap, and the audited writer/refresh/scorer path. The current findings do not contradict their experiments.

The important qualification is **integration fidelity between earned components**. A component can pass its own experiment while the live runner fails to consume its artifacts. The new tests connect temporal compilation, model-facing evidence and expansion in one check; checking each component's existence independently was insufficient.

After these repairs, the dominant **annotated coverage** loss remains at **Task IR fields/context → grounded target roles**, before Edit Plan selection. The largest counterexamples still lack the appropriate row population, output-column role or table/body relation. This is not a claim that every task first fails there: inherited context can disappear earlier, provider failures are numerous, and some plans choose incorrectly despite adequate evidence. The 27-obligation labels cannot support an exhaustive seven-way numerical decomposition of all eleven tasks.

Canonical synthesis remains conditionally promising and unproven generally. The recent 7/11 favorable returned-proposal result should be read alongside the older integrated probe's 9/18 reference-complete formulas and 2/9 complete/novel formulas. Different populations and runtime conditions prevent pooling them. Neither result justifies redesigning synthesis in response to current authority misses.

## 7. Smallest next experiment

The static repair gate is complete. **Before adding a new representation**, freeze a small role contrast set using existing cases: 05_01 O7 (entity population), 03_01 O4 (output column), 08_01 O3 (explicit same-timeframe reference), 15_05 O4–O6 (parent context plus output block), 13_05 O3 (linked occurrence), and 15_05 O1 (implicit-table negative control). Annotate only the necessary task spans, existing workbook identities and missing role relation. Reuse current matchers in shadow mode, report row/column/occurrence coverage separately, and reject proposals that solve a positive case by broadening the negative controls. This is an evaluator-side test of a proposed relation, not a new runtime selector.

If the next step is a live validation of the completed repair, the smallest discriminating probe is **two Edit Plan calls for 13_05 O1 only**: original local-period evidence versus the repaired temporal-world projection. Hold the saved Task IR, raw task, percentage fix, stable ordering, model settings, limits, scalar cache lineage and schema fixed in both arms. Do not rerun Task IR, retrieval, synthesis, scheduler or writer. Record response availability separately from expanded-authority recall/precision against the five existing evaluator labels. A provider failure is inconclusive, not a reason for an undeclared retry. 13_05 O5 can be an optional two-call positive control because its five targets were already recoverable.

No live probe was needed to establish or validate the implementation defects, so none was launched. A full 04_01 rerun would now conflate scheduler liveness with changed frontend evidence; any later scheduler experiment should continue its frozen authority explicitly.

**Leave alone:** ProgramGroup eligibility/translation, authority algebra, dependency authority intersection, scheduler work-unit granularity, synthesis prompts and architecture, no-op handling, hard verifier semantics, persistent working-state policy, and writer/LO/scorer. Do not revive pruning, closed-world program selection, Sketch/Operand IR, a finance ontology, semantic repair, voting or retries on this evidence.

**Primary assessment: MULTIPLE_DISTINCT_LOSSES, with compiled-world fidelity defects repaired and task-to-target role representation still provisional.**

## Source reports read

- Root: `REMAINING_LOSS_PROBE_REPORT.md`, `SCHEDULER_STATIC_REPAIR_REVIEW.md`, `INTEGRATION_AUTOPSY_REPORT.md`, `REPAIR_REPORT.md`.
- `resource_feasibility/credit_restored_aggregate/CREDIT_RESTORED_BRIDGE_AND_AGGREGATE_REPORT.md` and its bridge lineage.
- Mechanical runs: `task-obligation-compile-probe/report.md`, `workbook-grounding-probe/report.md`, `temporal-spine-probe/report.md`, `temporal-closure-probe/report.md`.
- Mechanical runs: `edit-plan-composition-probe/full_report.md`, `edit-plan-replication-probe/full_report.md`, `relational-retrieval-probe-glm-final-matched/full_report.md`, `integrated-hybrid-synthesis-probe/full_report.md`.
- Mechanical runs: `execution-unit-probe/PHASE_B_REPORT.md`, `program-group-probe/PHASE_C_REPORT.md`, `structural-recoverability-census/CENSUS_REPORT.md`.
- Current code and contracts: `task_obligation_compile.py`, `workbook_grounding.py`, `frontend_projection.py`, `temporal_spine.py`, `workbook_spine_sqlite.py`, `edit_plan.py`, `matched_compiled_treatment.py`, `fm_resource_feasibility.py`, `run_clean_sequential_replication.py`, `matched_fm_max.py`, `integration_replay.py`, and the workbook/Edit Plan contracts.
