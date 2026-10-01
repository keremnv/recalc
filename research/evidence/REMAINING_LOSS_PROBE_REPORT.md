# Remaining loss probe — frozen repaired Financial_Model

**Primary verdict: MULTIPLE_DISTINCT_LOSSES.** Zero new model calls; no prompt, architecture, runtime-code, or workbook changes; no FM20 A/B launch.

The zero-write aggregate label was misleading: 04_01, 07_01 and 08_01 contain **27 provider-failed synthesis attempts, one invalid null-formula response, and six accepted formulas identical to input**. No usable semantic-change proposal was discarded after verification. Separately, a supported scheduler coverage defect can exhaust the active queue while independent authorized work remains. Authority losses combine insufficient grounding, demonstrably wrong model selections, and missing planner responses. These are distinct boundaries.

## Population, evidence and definitions

The population is the same 11-task credit-restored aggregate: 01_01, 03_01, 04_01, 05_01, 06_01, 07_01, 08_01, 12_05, 13_05, 15_05 and 17_05. Excluded 14_05 remains excluded. 17_05 did not pass Task IR and 12_05 had invalid authority; neither enters canonical synthesis accuracy. The nine valid-authority tasks have 89 persisted synthesis decisions. “Reached synthesis” means an attempted request, not a successful GLM response.

Inputs are the resolved task directories under `benchmark-data/SpreadsheetBench-2/benchmark-runs/matched-glm-compiled-sixty/resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge`, plus the existing `credit_restored_bridge_audit` workbooks/lineage and the frozen source. Resolved original/retry paths, final evidence hashes and per-stage call census are in `suspected_code_boundaries.json`. All eight source hashes in the prior bridge freeze still match. The before/after comparison of 234 Python source/test files shows no changes. The merged evidence directories are symlinks: their final resolved hashes are recorded, without claiming an initial evidence-tree hash.

Gold targets here are evaluator-only **input→gold semantic-content differences**, using the existing autopsy blank/content rule. They are not every official modification cell affected by recalculation. Formula exactness and relative fingerprints use the existing harness evaluators. Gold is never passed to a planner, scheduler, or model. Per-obligation assignment is a manual diagnostic annotation from the instruction, sheet labels and gold-difference regions; it is not a new target ranking algorithm.

## 1. Actuation loss: all 34 attempts classified once

| Task | Attempts | Provider failure (`OTHER_EXPLICIT`) | Invalid response | Accepted input-identical formula (`OTHER_EXPLICIT`) | Actuated |
|---|---:|---:|---:|---:|---:|
| 04_01 | 3 | 3 | 0 | 0 | 0 |
| 07_01 | 11 | 5 | 1 | 5 | 0 |
| 08_01 | 20 | 19 | 0 | 1 | 0 |
| **Total** | **34** | **27** | **1** | **6** | **0** |

Exactly-once enum totals: `OTHER_EXPLICIT=33`, `INVALID_RESPONSE=1`; every other requested class is zero, including `ABSTAINED`, `INVALID_FORMULA`, `OUTSIDE_AUTHORITY`, `VERIFIER_REJECTED`, both supersession classes, both dropped classes, `VALID_BUT_NOT_ACTUATED`, and `ACTUATED`. Provider failures are not model abstentions merely because the scheduler records `ABSTAIN`.

- **04_01:** Financials!D6 and Assumptions!K141 returned `PROVIDER_TIMEOUT`; Ratio_Analysis !E12 returned `SESSION_RESOURCE_LIMIT`. All parsed synthesis responses are null. There is no GLM program to score or actuate.
- **07_01:** Sales Schedule!F16 returned exactly `{"target_id":"cell:s05:r16:c6","status":"PROPOSED","formula":null}`. Five other attempts timed out. The five usable formulas passed the hard verifier and exactly repeated input: Cashflow (Monthly)!J19 `=SUM(J13:J18)`, J24 `=SUM(J23)`, J35 `=SUM(J28:J34)`, J47 its existing cash-flow formula, and Executive Summary!F20 `=E33`. Across canonical and group members, 349 dispositions are `NO_SEMANTIC_CHANGE`; six are `ABSTAIN`.
- **08_01:** two timeouts and 17 `MODEL_ACCESS_FAILURE` attempts. The one returned formula, Income Statement!I54 `=I47-I50`, passed verification and repeated input. Its seven-member group generated only input-identical results. Dispositions: seven `NO_SEMANTIC_CHANGE`, 19 `ABSTAIN`.

The first boundary for the null-formula response is `compiled_scheduler.schedule`, lines 157–166: the parsed object produces `f=None`, then the no-formula branch records `ABSTAIN`. This is an invalid proposal, not a valid proposal dropped by a parser. For each of the six parseable valid formulas, the first boundary withholding a write is lines 175–176: `forms.get(seed) == f` → `NO_SEMANTIC_CHANGE`. All six targets are outside the gold semantic-change set. No authority mismatch, hard rejection, supersession, state loss or writer loss occurred among these proposals.

`actuation_loss_trace.csv` contains one row per attempt with operation/obligation, active group or residual work item, complete operation authority, retained retrieval evidence/history, exact returned message and raw provider body, parsed object, formula/value, validation, disposition, first code boundary and call artifact. Provider errors remain explicit rather than fabricated model answers.

**Answer:** these three tasks did not produce a usable returned semantic-change program. Most attempts did not return a model answer at all. The six structurally valid returned programs were no-ops. There is no supported downstream loss of an already usable semantic edit in this population.

## 2. Authority loss: evidence versus selection

| Task | Gold content targets | Authority | Intersection | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| 05_01 | 383 | 102 | 3 | 0.78% | 2.94% |
| 15_05 | 614 | 59 | 0 | 0.00% | 0.00% |
| 03_01 | 280 | 535 | 22 | 7.86% | 4.11% |
| 13_05 | 21 | 19 | 10 | 47.62% | 52.63% |

Per-obligation results follow. A dash means the denominator is zero. Gold sets can overlap: 15_05 O1 contains O2, and O4 is the parent of O5/O6. Use the task-union row above, not the sum of obligation rows.

| Task / obligation | Gold | Authority | ∩ | Recall | Precision | Earliest missed-target cause |
|---|---:|---:|---:|---:|---:|---|
| 05_01 O1 | 4 | 0 | 0 | 0.0% | — | OTHER_EXPLICIT: 4 |
| 05_01 O2 | 36 | 0 | 0 | 0.0% | — | MODEL_SELECTED_TOO_NARROW_TARGET_SET: 36 |
| 05_01 O3 | 1 | 1 | 1 | 100.0% | 100.0% | No missed content target |
| 05_01 O4 | 1 | 1 | 1 | 100.0% | 100.0% | No missed content target |
| 05_01 O5 | 1 | 1 | 1 | 100.0% | 100.0% | No missed content target |
| 05_01 O6 | 5 | 0 | 0 | 0.0% | — | OTHER_EXPLICIT: 5 |
| 05_01 O7 | 297 | 99 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 297 |
| 15_05 O1 | 193 | 4 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 193 |
| 15_05 O2 | 9 | 18 | 0 | 0.0% | 0.0% | MODEL_SELECTED_TOO_NARROW_TARGET_SET: 9 |
| 15_05 O3 | 132 | 0 | 0 | 0.0% | — | LOCUS_GROUNDING_MISS: 132 |
| 15_05 O4 | 21 | 0 | 0 | 0.0% | — | SUBJECT_GROUNDING_MISS: 21 |
| 15_05 O5 | 14 | 2 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 14 |
| 15_05 O6 | 7 | 1 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 7 |
| 15_05 O7 | 152 | 34 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 152 |
| 15_05 O8 | 30 | 0 | 0 | 0.0% | — | OTHER_EXPLICIT: 30 |
| 03_01 O1 | 18 | 0 | 0 | 0.0% | — | OTHER_EXPLICIT: 18 |
| 03_01 O2 | 11 | 11 | 11 | 100.0% | 100.0% | No missed content target |
| 03_01 O3 | 6 | 6 | 6 | 100.0% | 100.0% | No missed content target |
| 03_01 O4 | 230 | 510 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 230 |
| 03_01 O5 | 5 | 3 | 0 | 0.0% | 0.0% | LOCUS_GROUNDING_MISS: 5 |
| 03_01 O6 | 10 | 5 | 5 | 50.0% | 100.0% | MODEL_SELECTED_TOO_NARROW_TARGET_SET: 5 |
| 13_05 O1 | 5 | 0 | 0 | 0.0% | — | OTHER_EXPLICIT: 5 |
| 13_05 O2 | 0 | 5 | 0 | — | 0.0% | No missed content target |
| 13_05 O3 | 5 | 4 | 0 | 0.0% | 0.0% | SUBJECT_GROUNDING_MISS: 5 |
| 13_05 O4 | 1 | 0 | 0 | 0.0% | — | OTHER_EXPLICIT: 1 |
| 13_05 O5 | 5 | 5 | 5 | 100.0% | 100.0% | No missed content target |
| 13_05 O6 | 5 | 5 | 5 | 100.0% | 100.0% | No missed content target |

**05_01:**

- **O7, 297 missed tranche cells:** the complete subject packet never retrieves First/Second/Third Tranche labels at Workings Cost Sheet rows 29–31. It retrieves Total Fund Raised at B27 and unrelated fund/total labels. `subject_queries` uses the subject field; “all three tranches” is in scope. `compose_targets` uses retrieved subject rows. The model chooses O27:DI27, while gold changes O29:DI31. This supports **subject evidence loss preceding a narrow plan**, not a claim that the correct tranche rows were shown and ignored.
- **O2, 36 missed totals:** the projected subject foreground explicitly begins with **DK7 “Total”**. Gold totals are in column DK. The planner instead selects monthly O:DI in five subtotal rows. It then requests `BLANK_ONLY`, removing all 495 selected existing cells. Crucially, the raw 495-cell selection intersects gold in **zero** cells: occupancy removed no gold target. The first loss is model selection of the wrong output region despite the relevant Total-column evidence. Other period evidence is incomplete/noisy, so this does not prove every intended component row was fully grounded.
- **O1 and O6, nine missed targets:** both planner calls timed out. A valid composed plan does not establish successful planning for these obligations. This is an explicit provider-fragment loss, not an observed choice of a narrow set.
- **O3–O5:** all three rate targets are authorized. Their proposed constant formulas `=0.12`, `=0.16`, `=0.2` encode the gold numeric values. The aggregate’s strict content equality does not count those formula-versus-literal representations as exact gold writes; that is not evidence of wrong percentages.

**15_05:**

- **O1:** grounding reduces “all elements of the first Consolidated Financials table” to heading anchors and a rows-1:2 region. The first table body is absent from the complete subject/target packet. The returned plan copies the heading rectangle and filters to four occupied heading cells. This is a **table-body evidence limitation**. No deterministic expansion bug is shown.
- **O2:** the exact needed E25:M25 region is represented by projected E24:M25, with D25 “Net Margin (%)”. The planner selects P25:X25 and AA25:AI25 instead. All nine missed targets are a clear **model-selection loss despite sufficient target-region evidence**.
- **O3:** the Task IR locus lacks the surrounding Formats context; deterministic candidates are Work Sheet and Report Tables, with zero subject anchors. The relevant ratio outputs are not grounded as a locus. Later, the response contains malformed JSON followed by a corrected JSON object and explanatory prose; the persisted parser rejects the whole message. That is a model output-contract violation, not proof that a valid standalone response was improperly dropped. No parser repair is attempted.
- **O4–O6:** the logical-output block at rows 50, 52, 54, 56, 59, 61 and 63 is not grounded. O4’s generic “logical functions” has no subject hits and its planner call times out. O5/O6 ground period headings; the below-table/metric context resides in the parent obligation. Their plans guess rows 12–18 and 38–44. Correct output-row evidence is absent, so an exclusive “planner ignored sufficient evidence” attribution is unsupported.
- **O7:** Particulars B2 is the only complete subject hit; the target region is row 2. The model chooses C2:AJ2. The table body is absent from the grounding packet. This is another heading-to-body evidence limitation.
- **O8:** the packet contains useful cost/margin/%-change anchors, but the planner times out. Its 30 missed targets are `OTHER_EXPLICIT`, rather than forcing a selection/evidence attribution without a returned plan.

**Controls:** 03_01 successfully authorizes Risk Factor, Basic EPS and Required Equity, but still loses growth targets through missing subject evidence and opening cash through wrong locus grounding. It is a positive write control, not a fully correct localization control. 13_05 fully authorizes the two five-cell depreciation/link groups. Its growth-input fragment times out; the interest fragment has provider `finish_reason=error` with null content (wrapped as `PARSE_FAILURE`); cost-side warehousing row58 is a formula-linked label `=B25`, while subject matching selects the revenue-side text label B25. There are no gold content changes in Revenue Drivers itself, so O2 content-target recall is undefined.

**Attribution limits:** 38 auxiliary differences in 05_01 and 86 surrounding helper-formula differences in 15_05 cannot be safely assigned to a direct instruction clause. The CSV lists each as `OTHER_EXPLICIT` in an `UNASSIGNED_EVALUATOR_DIFFERENCES` row and retains them in task-wide denominators. They are not silently turned into `OBLIGATION_MISSING`. The definite ratio rows used for 15_05 O3 are documented in the per-cell lists; surrounding debt/depreciation helpers are kept separate. O4/O5/O6 overlap means their cause counts must not be summed as distinct targets.

**Answer:** both mechanisms occur. The largest directly attributable 05_01 miss is missing tranche evidence; both tasks also show explicit wrong selections despite useful correct-region evidence. Missing provider fragments are a third cause. Calling the entire loss either deterministic grounding or GLM plan selection would be unsupported.

Every selected target set was re-expanded read-only with the existing V2 expander. Cells and operation expansions exactly match the persisted plans for all four tasks. No missed gold target in these probes is supported as an expansion bug, explicit-exception removal, or occupancy-first removal. Full raw obligations, complete grounding packets, model-facing projections, chosen operations, expanded cells and every missed-cell classification are in `authority_loss_by_obligation.csv`.

## 3. Canonical synthesis conditioned on localization and retrieval

One decision is one persisted canonical or ungrouped seed session. Group members translated from it are not additional stochastic decisions. `retrieval_complete` means every direct cell reference of the evaluator gold formula was actually materialized as a cell/formula evidence record. This is stricter than checking a working-set handle alone, but still does **not** prove semantic sufficiency, correct upstream values, or provision of every useful label. Gold-literal targets have no formula-retrieval denominator.

| Population | Exact / decisions | Accuracy |
|---|---:|---:|
| All authorized synthesis attempts, exact formula at selected cell | 21/89 | 23.60% |
| Gold target, including three gold-literal targets | 7/35 | 20.00% |
| Gold **formula** target only | 7/32 | 21.88% |
| Gold target **and complete retrieval** | 7/23 | 30.43% |
| Returned model content, all selected targets | 21/35 | 60.00% |
| Returned model content, gold target | 7/16 | 43.75% |
| **Returned proposal, gold target and complete retrieval** | **7/11** | **63.64%** |
| Any produced formula, all selected targets | 21/30 | 70.00% |
| Useful exact gold formula, unconditional attempt denominator | 7/89 | 7.87% |

Thus the requested attempt-level probabilities are **P(exact formula | target gold)=7/35**, or **7/32 for formula targets**, and **P(exact formula | target gold and retrieval complete)=7/23**. Twelve of the latter 23 attempts have provider failures, so **7/11 is the relevant returned-formula construction rate**. The unconditional 21/89 includes 14 exact matches at unchanged/non-gold cells; it must not be described as 21 useful repairs. Fingerprint correctness has the same numerators in these populations.

All four returned exact mismatches in the fully conditioned sample:

| Target | Proposal | Gold | Supported interpretation |
|---|---|---|---|
| 01_01 Fixed Assets Schedule!H7 | `=-(H5+H6)*$C$10` | `=-$C$10*(H5+H6)` | Same scalar algebra; strict exact/fingerprint mismatch. |
| 01_01 Consolidated BS!C50 | `=C48-C22` | `=C22-C48` | Genuine reversed-subtraction error. |
| 03_01 Balance Sheet!I42 | `=$H$42` | `=+H42` | Same referenced value at canonical cell; absolute/relative representation differs. Task explicitly holds FY13 constant. |
| 06_01 Balance Sheet!M31 | `=M19+M24+M27` | `=M27+M24+M19` | Same three addends; order differs. Ordinary scalar arithmetic equivalence, subject to floating rounding. |

This supports **one definite semantic construction error among those 11 returned decisions**, plus three strict-representation mismatches, rather than four demonstrated financial-program mistakes. The I42 observation concerns the canonical cell; it is not a blanket claim that every relative/absolute translation has the same formula fingerprint. This is a manual diagnostic interpretation, not a new semantic verifier or adjusted benchmark score. The sample is small and excludes most failed/poorly localized opportunities.

ProgramGroup cash-out remains consistent with the bridge: **35 actual member writes, 22 exact member formulas**. The decision CSV records eligible member count and actual translated/written/exact member counts per seed, excludes seeds from member-write counts, and reports whether an input formula elsewhere has the gold relative fingerprint. The latter is structural recoverability, not proof that the matching example was retrieved. The seven exact gold canonical writes plus 22 exact member writes reproduce the known 29 exact writes.

**Answer:** strict construction accuracy with a right target, complete direct-reference evidence and an actual returned proposal is 63.64%; operational attempt accuracy is 30.43%. The exact metric understates canonical semantic quality here. These records do not support diagnosing a dominant GLM formula-construction limit from the unconditional score.

## 4. The ten formula-correct/value-wrong cells

Only the ten roots from the existing bridge lineage were inspected. The existing `proposal_precedents` parser was reused. Traversal follows value-wrong immediate/transitive precedents and stops each branch at the first wrong formula/literal content; correct formulas with wrong cached values are intermediate nodes. All branch endpoints are retained. A shortest-path/lexical tie-break supplies one root label without hiding other causes. This traversal is diagnostic glue over the existing parser, not a new dependency graph/compiler.

| Root cells | First divergent upstream content | Classification |
|---|---|---|
| 01_01 Working Capital Schedule!H22:M22 | Revenue Drivers!I137:M137; Cost Drivers!I16:M16 and I19:M19 | `NO_PROPOSAL`, `TARGET_AUTHORISED_NOT_ACTIVE`, `TARGET_NOT_AUTHORISED` |
| 13_05 Assets Sch.!N9:O9 and IS!N15:O15 | Input Sheet!I20:M20 | `TARGET_NOT_AUTHORISED` |

There are **20 distinct first-divergence cells** across the ten roots: **15 unauthorized, 4 authorized-not-active, and 1 no-proposal**. These comprise Revenue Drivers!I137:M137, Cost Drivers!I16:M16 and I19:M19, and Input Sheet!I20:M20. Root labels and all branch paths are in the CSV; overlapping roots do not create new unique failures.

Example 01_01 chain: Working Capital Schedule!H22 → H21 → H19 → H4 → H5 → Consolidated P&L!H9 → H6 → Revenue Drivers!I137. The revenue canonical has no formula proposal. The later revenue members depend on that failed canonical and are not translated. Parallel cost branches reach unauthorized I16/I19 (and later columns). Membership in a failed canonical group is not evidence that a usable member proposal existed.

Example 13_05 chain: IS!N15 → Assets Sch.!N9 → N15 → N14 → IS!N8 → N6 → Revenue Drivers!L44 → L29 → Input Sheet!L20. The missing O1 planner fragment never authorized transport-growth inputs I20:M20. The correct depreciation/link programs persist, but consume values derived from those unchanged wrong inputs.

**Answer:** all ten roots reduce to the already observed authority/no-proposal/inactive-group-member losses. No new writer failure, mistranslation of a correct canonical, wrong source literal outside the repair targets, or unexplained recalculation mechanism is needed for these roots. No root requires `WRONG_PROPOSAL`, `PROPOSAL_NOT_ACTUATED` or `PROGRAM_GROUP_WRONG_CANONICAL` as its first content divergence.

## 5. Supported code boundary and implementation-versus-model distinction

**Highest-leverage boundary to inspect next: `benchmark/compiled_scheduler.py`, `schedule`, lines 164–166, relative to `activate_available()` at line 212.**

Before the final 04_01 iteration exits, its active Ratio_Analysis !E12 session has no formula (`SESSION_RESOURCE_LIMIT`); after popping it the queue is empty. The branch records `ABSTAIN`, calls `flush()`, and executes `continue`. It never reaches `activate_available()`. The loop then returns with **70 unresolved authorized targets**, including **15 never-attempted independent ProgramGroup canonicals and 31 residual cells**. Four other unresolved cells belong to an attempted, failed canonical group; those are a different issue and should not be advertised as ready independent formulas. Only 23 of the frozen 150 calls were used, and no task-budget failure was recorded.

Concrete unattempted groups include Ratio_Analysis !F12:L12 and Financials!E12:F12, E16:F16 and E19:F19. Those already-valid work units are lost from the active queue because its replenishment is reached only after a successful formula branch. This is a supported **coverage/control-flow implementation defect**. It does not establish that the available provider would have returned a useful next formula.

The frozen scheduler was replayed in memory with stored sessions, archived grouping and disabled I/O/inference. Its 04_01 dispositions reproduce exactly, including the final empty queue. Seven other task disposition sets also reproduce; the resumed 07_01 trajectory does not match a fresh-order replay, so no claim is based on that replay. Persisted no-op/proposal counts for 07_01 do not depend on replay.

Other tasks also retain pending work; the distinction between independently unattempted units and members requiring a failed canonical matters:

| Task | Unresolved authority | Pending independent group canonicals | Unattempted residual cells | Unresolved members of attempted groups |
|---|---:|---:|---:|---:|
| 01_01 | 12 | 0 | 0 | 12 |
| 03_01 | 510 | 4 | 476 | 8 |
| 04_01 | 70 | 15 | 31 | 4 |
| 05_01 | 98 | 0 | 0 | 98 |
| 06_01 | 13 | 0 | 12 | 1 |
| 07_01 | 127 | 0 | 2 | 125 |
| 08_01 | 671 | 0 | 71 | 600 |
| 15_05 | 32 | 0 | 22 | 10 |

Group counts and member-cell counts are different units, so the columns are not additive. For example, 08_01 has 71 residual cells plus 600 unresolved members of failed groups; its many missing writes cannot all be attributed to queue replenishment alone. The 01_01 and 05_01 unresolved tails consist entirely of failed-canonical group members. There is no newly generated valid proposal for these tails to “restore.”

| Boundary | Exact before → after | Supported interpretation |
|---|---|---|
| `compiled_scheduler.schedule:164–166` / `:212` | Last session has no formula, queue empty, independent work still latent → `ABSTAIN`, skip activation, return | **Implementation defect:** independent work not replenished. |
| `compiled_scheduler.schedule:175–176` | Accepted formula equals input → `NO_SEMANTIC_CHANGE`, no writer entry | Correct suppression of redundant writes; no actuation bug. |
| `compiled_scheduler.schedule:157–166` | `PROPOSED` with `formula:null` → no formula, `ABSTAIN` | Model response-contract failure; scheduler label is broader than true abstention. |
| `matched_compiled_treatment.call_or_stub` / `retrieval_synthesis:936–939` | Timeout/access/resource failure → no parsed proposal | Infrastructure failure, not GLM semantic evidence. |
| `workbook_grounding.project_obligation:380–406`, `compose_targets:307,361–369` | Subject/locus anchors miss body/tranche/linked-label region → narrow or empty candidate packet | Observed frontend evidence limitation; **not automatically a code defect** under the frozen grounding contract. |
| `matched_compiled_treatment._plan_task_sharded:789–816` | Some fragments lack parsed operations; others exist → composed plan remains `VALID_PLAN` | Plan-validity is not obligation-completeness; missing fragment/infrastructure or output-contract loss. No valid operation demonstrated dropped. |
| `edit_plan.expand_edit_plan:241–244` | Selected monthly rectangles, explicit `BLANK_ONLY` → zero authorized cells | Correct execution of a bad selection/filter combination; zero gold cells removed by filter. |
| `matched_compiled_treatment.validate_formula:867` | Structurally valid reversed subtraction → `HARD_ACCEPT`, scheduled/persisted | Genuine semantic model error outside the hard verifier contract; not a verifier implementation defect. |
| `compiled_scheduler.schedule:180–211` | Upstream edit outside authority or canonical has no formula → no completed upstream edit | Known authority/proposal prerequisite loss; exact downstream formula can remain value-wrong. |

`suspected_code_boundaries.json` supplies file, function, control-flow boundary, before/after state, reason and evidence for each supported record. It separates the one demonstrated implementation defect from evidence limitations, provider failures, explicit model choices and correct no-op suppression. No source fix, new ranking, new semantic verifier or dependency machinery was added.

## Deliverables and verification

- `actuation_loss_trace.csv`: 34 synthesis attempts, each classified exactly once.
- `authority_loss_by_obligation.csv`: all 27 obligations across the four probes, task-union metrics, and explicit unassigned gold differences.
- `synthesis_conditioned_accuracy.csv`: all 89 decisions, conditioned aggregate rows, exact/fingerprint quality, recoverability and translated-write lineage.
- `dependency_first_loss.csv`: exactly the ten known roots, immediate dependencies, complete visited wrong-value branches and first divergent content.
- `suspected_code_boundaries.json`: evidence inventory, freeze checks, expansion parity, scheduler state accounting and before/after failure boundaries.

Validation reconciled 568 archived call records, 34 exactly-once actuation rows, 27 obligations, 89 canonical decisions, ten dependency roots, and 35/22 actual/exact translated member writes. CSV fields preserve full JSON evidence; Python readers should set `csv.field_size_limit(sys.maxsize)`.

The analysis reuses persisted responses and existing evaluators. No model endpoint, benchmark runner, scheduler persistence writer, LibreOffice refresh or official scoring run was invoked. Existing LO-refreshed bridge files were read. Local diagnostic helpers lived in `/tmp`; the only repository additions from this diagnostic are these six deliverables.

**Primary verdict: MULTIPLE_DISTINCT_LOSSES**
