# Static scheduler repair and architecture review

The terminal-path replenishment defect is repaired. Mechanical replay of the frozen 04_01 evidence exposes all **49 independent semantic units**, versus three previously. It does not establish that the newly exposed work can be solved: 46 units have no stored response. The 13_05 positive control preserves all ten scheduled edits exactly. **114 selected tests passed. No new provider/LLM requests, physical workbook writes, live benchmark runs, or FM20 A/B were performed.**

The earlier diagnostic artifacts remain frozen. This document records the subsequent authorized repair and qualifies the linked-label diagnosis below. Existing unrelated workspace changes were preserved. `scheduler_static_repair.patch` isolates the three runtime-file changes against snapshots taken before this repair; new regression tests and the replay tool are separate files.

## Changes and exact boundaries

| Boundary | Before | After | Reason |
|---|---|---|---|
| `benchmark/compiled_scheduler.py::schedule`, terminal `continue` paths | A failed/no-formula seed acquired a terminal disposition, then flushed and continued without `activate_available()`. The queue could empty while independent authority remained latent. | Every normal terminal path calls `finish_turn()`, which activates independent available work and checkpoints. | Proven liveness defect; no need to change semantic planning or formulas. |
| `compiled_scheduler.py::schedule.enqueue` and canonical seed selection | A dependency could enqueue a failed group's member; `seed = canon if canon not in done else candidate` then made that member a fresh semantic decision. | A member request resolves to its existing canonical before the done/queued checks. Terminal canonicals cannot promote members to independent work. | Prevents the replenishment repair from violating the existing ProgramGroup contract. Regression fails against the old code, including after resume. Group construction and translation are unchanged. |
| `compiled_scheduler.py::synthesis_outcome`; `matched_compiled_treatment.py::retrieval_synthesis` | Missing formulas became scheduler `ABSTAIN`, including provider failures; session status conflated several outcomes. | Explicit model abstention, invalid response, and provider/resource failure remain distinct. Usable returned proposals still reach verification even if accounting reports a cost ceiling. | Instrumentation fidelity, without treating operational failures as returned-model judgments. |
| `matched_compiled_treatment.py::model_call` | A response with `finish_reason=error` could have no provider failure label and be interpreted later as parse failure. | Records `PROVIDER_ERROR`; keeps the raw response, actual truncation classification, and accounting separately. | Provider failure is an operational outcome. The final task can report `NON_MODEL_FAILURE`; this label does not short-circuit scheduler replenishment. |
| `matched_compiled_treatment.py::planning_completeness`, `plan_task`, `run_one_task` | A composed `VALID_PLAN` could omit obligation fragments without an explicit overall completeness field. | Adds fragment/authority coverage, `COMPLETE`/`PARTIAL`/`NO_VALID_AUTHORITY`, and `semantic_completeness=NOT_ESTABLISHED`. | Schema validity remains legal for partial plans. No target expansion or authority widening. |
| `workbook_grounding_spine.py::_payload`, `_compile_open`; `matched_compiled_treatment.py::target_from_id` | Numeric payloads were omitted. Input Sheet!I25 in 13_05 contains 35, but its frozen occupied record has `kind=numeric` and no payload. SQL evidence loses the scalar; target construction called it blank. | Fresh compilation retains numeric/boolean payloads, including zero and false. Target kind respects recorded occupancy, including legacy records with missing payloads. | Additional demonstrated representation invariant violation: occupied input facts were lost at a deterministic boundary. Missing legacy values are not invented. |

The scalar fix requires **new, isolated spine/SQLite caches** to supply previously omitted values. Frozen caches and archives have not been rebuilt. Restoring those values changes future evidence content, not prompts or ranking. This review does not claim that restoring I25 alone would correct the warehousing plan.

## Scheduler exit-path audit

| Path in `schedule` | Terminal handling / invariant |
|---|---|
| Empty authority early return | No independent authorized work exists. |
| Stale queued candidate already done | Replenishes and checkpoints before continuing. |
| Unsupported `CLEAR_CELL` | Explicit terminal failure; replenishes and checkpoints. |
| Seed already in edits | Recovers a write disposition and replenishes without synthesizing again; normal atomic checkpoints already include this disposition. |
| Replay lacks stored response | Explicit replay-only terminal disposition; replenishes. It is not a live model attempt. |
| Task call/cost budget prevents starting a session | Breaks with explicit budget failure; unattempted authority stays unresolved. Budget exhaustion is not a terminal response for the popped item. |
| Invalid target entity | Explicit terminal failure; replenishes. |
| No formula, abstention, provider/resource failure, malformed response | Distinct outcome recorded; replenishes. |
| Hard verifier rejection | Explicit rejection; replenishes. |
| Input-identical accepted formula | Retains `NO_SEMANTIC_CHANGE`, processes existing group/closure rules, then replenishes. |
| Accepted changed formula | Schedules existing canonical/group writes, then replenishes. |
| Inner member skip, translation exception, translated verifier rejection | Continue within the current group. The common terminal tail replenishes after group processing. No failed member becomes a new canonical. |
| Unexpected exception | Propagates to existing task failure handling. It is not silently treated as a completed session; no additional provider work is launched after the exception. |
| Queue exhaustion / final return | All normal terminal branches have offered independent work activation. Failed noncanonical members may legitimately remain unresolved. |

## Mechanical validation

`benchmark/scheduler_terminal_replay.py` invokes the existing scheduler, ProgramGroup builder, and verifier over archived responses. It replaces inference with a function that raises, disables checkpoint writes, checks archive hashes and file inventory, and writes only the requested report outside the archive. It does not call the workbook writer or scorer.

| Measure | 04_01 | 13_05 control |
|---|---:|---:|
| Authorized targets | 73 | 19 |
| Independent units | 49 | 6 |
| Retained synthesis sessions | 3 | 6 |
| Dispositions before → after | 3 → 49 | 19 → 19 |
| Unresolved targets before → after | 70 → 24 | 0 → 0 |
| Newly exposed units without stored responses | 46 | 0 |
| Scheduled edits | 0 | 10, exactly equal to archive |
| ProgramGroups | Exactly unchanged | Exactly unchanged |
| Archive files | Hashes and inventory unchanged | Hashes and inventory unchanged |

The 24 unresolved 04_01 cells are noncanonical members. The 46 newly exposed units comprise independent group canonicals and residual work; they are neither invented formulas nor scored improvements. The three retained failures are two provider timeouts and one session resource limit.

Regression coverage includes the archive-derived 04_01 authority/groups/failures, useful later writes after terminal failures, explicit abstention, null/non-string formula responses, malformed response shape, invalid entity, unsupported edit kind, verifier rejection, replay misses, dependency requests for failed group members, resume, budget stop, exception propagation, precise provider-error classification, additive plan metadata, and XLSX → spine → SQL → target scalar fidelity. The two central scheduler regressions fail against the pre-repair scheduler.

Validation: `tests/test_scheduler_terminal_paths.py`, `test_integration_repairs.py`, `test_frontend_projection_and_runtime.py`, `test_workbook_spine_sqlite.py`, `test_workbook_grounding.py`, `test_task_obligation_compile.py`, `test_edit_plan.py`, `test_matched_compiled_treatment.py`, `test_matched_fm_max.py`, and `test_execution_unit.py`: **114 passed**. The new replay script and terminal-path test file pass Ruff. Runtime prompt/schema/model/reasoning/temperature assignments are AST-identical to their pre-repair snapshots. See `scheduler_static_repair_validation.json` for hashes and commands.

## Plan completeness review

The new metric answers whether every emitted Task IR obligation obtained a valid fragment with nonempty authority. It does **not** establish that the IR captured the entire instruction, or that any operation covers all intended cells.

| Archived schema-valid plan | Obligations with authority | Obligations without authority | New coverage status |
|---|---|---|---|
| 04_01 | O1, O4, O6 | O2, O3, O5, O7, O8 | PARTIAL |
| 05_01 | O3, O4, O5, O7 | O1, O2, O6 | PARTIAL |
| 13_05 | O2, O3, O5, O6 | O1, O4 | PARTIAL |
| 15_05 | O1, O2, O5, O6, O7 | O3, O4, O8 | PARTIAL |

Historical aggregates retain their original labels; these annotations are computed from the archived plans without rewriting them. Provider, parse, and expansion failures must remain visible separately from model target-selection errors. A future `COMPLETE` status still cannot substitute for evaluator-side authority recall.

## Grounding representation review — no selection changes

**05_01, all three tranches.** `workbook_grounding.py::subject_queries` consumes subject and subject-interval fields. The tranche phrase resides in scope, which is handled by temporal/all-scope matching rather than recovery of the existing First/Second/Third Tranche row anchors. `compose_targets` derives rows from recovered subject hits. Thus available workbook labels fail to enter the relevant subject/target packet before plan selection. This is an interface coverage limitation. No new lexical weights, row ranking, benchmark-specific query, or automatic authority widening was added.

**15_05, table heading versus body.** `compose_targets` has subject-row/scope composition, not a table-heading-to-body relation. The actual workbook contains no explicit Excel Table objects. Existing region records are formula-equivalence runs; heading merges do not define the requested table body. The observed packet contains heading evidence without body evidence, but this is not proof that a known table-body object was discarded. Recovering implicit tables needs an explicit representation and validation contract.

**13_05, warehousing linked label.** B58 contains `=B25`. The dependency survives the spine, the full O3 packet, and projected foreground; all nine of that packet's point dependencies survive projection. B58 is not a text anchor, and the lexical hit points to B25. Therefore the earlier diagnosis needs qualification: the relation is present, but candidate construction/plan interpretation does not establish the linked row's role. It is incorrect to blame foreground truncation for losing this edge. Copying the source label's semantics to every formula-linked occurrence would itself require justification. No such rule was added.

**Instruction context.** The 15_05 inherited locus and parent/sub-obligation examples also limit how confidently Task IR can be called healthy. Passing the IR schema is evidence of structural validity, not complete preservation of the user's scope and relationships.

## Architecture assessment after repair

The architecture has credible boundaries: explicit authority limits writes; operations retain scheduling identity; a canonical decision can amortize justified repetition; persistence and recalculation have direct evidence behind them. The low aggregate modification score does not invalidate those components.

My assessment is more qualified than calling the entire front end healthy:

| Stage | Assessment |
|---|---|
| Task IR | Structurally useful; semantic completeness and inherited context remain unproven. |
| Grounding / evidence projection | Major coverage frontier, plus the repaired scalar-fidelity defect. Some needed relations survive but lack useful role interpretation. |
| Edit Plan / authority | Mixed evidence and model-selection failures; schema-valid partial plans now explicitly labelled. |
| Operation scheduler | Design supported; proven replenishment defect repaired and mechanically validated. Live continuation remains unmeasured. |
| Retrieval | Useful when reached; reference materialization alone does not prove all necessary facts are available. |
| Provider response availability | Separate major operational loss. Never include a timeout as a returned-model abstention. |
| Canonical synthesis | Promising conditional performance, based on a small selected sample, not established general robustness. |
| ProgramGroup propagation | Supported conditional on a correct canonical; group algorithms unchanged. |
| Writer / LibreOffice / scorer | Existing persistence and refresh evidence remains healthy. |

The earlier conditional result is **7/11 exact formulas among returned proposals on gold targets with all direct references materialized (63.64%)**, versus **7/23 attempts (30.43%)** when twelve provider failures remain in the denominator. Three of four strict mismatches were canonical algebra/reference equivalents; one was a genuine reversed subtraction. These are different quality measures. The eleven returned cases are too few and too selected to call synthesis solved. Also, the probe's retrieval-complete label measured materialized references, not full semantic sufficiency; the scalar omission demonstrates that distinction.

The highest-leverage next design review is **Task IR obligation → grounded evidence packet → expanded authority**. Trace whether scope, inherited locus, linked-label roles, and explicit structure survive that interface, and keep missing evidence separate from model choices made despite sufficient evidence. There is no basis here for adding a reversed-subtraction verifier, changing ProgramGroups, rewriting synthesis, or treating input-identical formulas as writer failures.

## Next experiment

The requested mechanical gate is complete. The smallest informative live experiment would continue only 04_01 from isolated copies of its retained IR/plan/session evidence under the repaired scheduler, recording whether the 46 newly exposed independent units actually receive attempts. A full front-end rerun changes authority and would confound that scheduler comparison. The 13_05 mechanical control already establishes unchanged scheduling of its saved formulas.

No live continuation was launched: the earlier explicit no-new-model-call constraint has not been lifted by a direct request to execute that experiment. Before a future live run, pin its cache lineage. A scheduler-only comparison should keep frozen evidence; a run testing the scalar repair should rebuild isolated input-derived caches and be labelled as such. Both should preserve the original prompts, authority, ProgramGroup contract, and archived artifacts. Neither requires an FM20 A/B.

**Primary architectural verdict: MULTIPLE_DISTINCT_LOSSES.** One demonstrated runtime liveness defect is repaired, a deterministic evidence-fidelity defect is repaired, and substantial representation/authority selection and provider-availability losses remain. The evidence supports focused work at those boundaries rather than an architecture redesign.
