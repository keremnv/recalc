# Phase12R recalc-fair historical replay and baseline correction audit

## PHASE 12 MECHANISM CARRIED FORWARD

**D — DEMOTE** for the post-edit derived-evidence bundle. Do not promote or revive the verifier. The evidence block was behaviorally potent, but its observed outcome benefit was largely reproduced by recalculating CONTROL outputs without changing formulas. The surfaced Phase12 findings were mechanically true but actionability-poor in the primary population. The intervention under audit is the submission/evaluation pipeline. Zero new trajectories, formula repair, model treatment, product-runtime changes or new agent-facing derived diagnostics.

## REPLAY QUESTION

Holding submitted workbook formulas and structure fixed, how often and by how much does isolated LibreOffice recalculation before the same official scorer change outcomes? V0 is the exact retained submitted artifact where available; V1 is separately copied, recalculated and hashed. Historical original score is never overwritten. Byte-unverified candidate files answer a normalized fixed-file question, not a retroactive historical score question. Score recovery, numerical correctness and semantic repair are separate propositions.

## PREREGISTRATION

The final protocol was frozen before full replay: `phase12r/PREREGISTERED_REPLAY_SPEC.md`, SHA256 `81c95dacb181e4cc7316d4ce84490590ed356aed2f549d61dfa5b7273a4fee49`. Population SHA256 `db4a4b41da976b0c7be38cfd1784807114551dec5bc09b6a72e705a8e2c4b39d`. Eligibility/exclusions, evaluator, formula equivalence, cache witness, categories, claim rules and stopping conditions were frozen. Any exact change is material; absolute modification/regression change≥.01 is material. Primary rebaseline A requires≥10% affected P1 tasks overall and≥10% in two families, each with≥3 affected tasks; B requires the analogous≥10%/≥3-task narrow-family evidence. Neither is met. No favorable pilot tuning or outcome selection. Pilot covers known sensitivity, unaffected/error/no-formula/complex-financial mechanics; retained pilot manifest/results/tests document plumbing. The separate scoring-execution recovery and sole configuration follow-up preserve this protocol and first-pass freeze.

## STRONG REVIEW BEFORE REPLAY

Gate A independently attacked candidate/submission provenance, scorer fallback, formula equivalence, semantic metadata, causal denominators and hindsight risk. Accepted corrections were applied before hashing: exact historical byte linkage, scoped normalized-only candidates, strict assessed-cell cache witness equality, fixed category/task thresholds and explicit error/count handling. See `STRONG_REVIEW_PREREG.md` and raw review. Review-only model output never entered scored workbooks. Requested reviewer selection is recorded, rather than claiming attested backend superiority.

## POPULATION

1222 eligible submissions were replayed: P1=183 archived ordinary controls/98 tasks; P2=191 ordinary research outputs/60 tasks; P3=848 historical-context outputs/297 tasks. P3 contains792 confirmed structured-harness runs and56 older noncontrol/unknown context; never pool it with ordinary prevalence. P2 has31 archived and160 byte-unverified run-local candidates. Submission status and required source/input/golden/task/category/original official output availability determine eligibility. Exclusions:378 not submitted,63 no attributable submitted workbook,2 task identities missing from the current dataset,1 missing/ambiguous official score. Their retained records are in POPULATION_MANIFEST.json; no low-score/Template/formula selection. Repeated runs and overlapping tasks are not independent prevalence samples. Retention is a limitation, not a random sampling guarantee.

## RECALC ENVIRONMENT

LibreOffice26.2.5.2; Ubuntu26.04.1; Python3.14.4/openpyxl3.1.5; C.UTF-8/TZUTC. Unchanged official evaluator SHA256 `04a2a75b29805ab40efe93e202384c365d1d32b9c924c1a4aed56e41249facb0`. Unique isolated UNO pipe/profile, forced automatic calculateAll(), Calc XLSX export,180-second LO timeout;7GiB/900-second row envelope, one worker after resource recovery. Complete commands/hash/settings recorded per artifact. Primary macro mode actually4=ALWAYS_EXECUTE_NO_WARN, despite erroneous frozen description;0 disables macros. UpdateDocMode0 disables link updates. Preserve the deviation;1219 readable packages had no conventional macro declarations, three unreadable files were never loaded. The sole bounded follow-up tests0 versus4. Primary statuses:969 RECALC_PASS,250 RECALC_UNSUPPORTED,3 NOT_ATTEMPTED/uninspectable; zero operational LO failures among attempted sources. No silent unrecalculated fallback. Recalc errors/unsupported/scorer failures stay explicit.

## ORIGINAL SCORE REPRODUCTION

All183 P1 current V0 numeric tuples reproduce their original scores. P2:85 reproduce,106 differ; byte-unverified numeric coincidence does not prove submission identity. Historical evaluator source versions are unavailable. P3 first-pass reproduction={'True': 473, 'False': 372, 'None': 3}; separately normalized execution reproduction={'True': 838, 'False': 7, 'None': 3}. Auxiliary DimensionHolder clone failures selected403 P3 rows for same-byte/scorer execution recovery; no P1/P2 scores change. First-pass RAW ledger/SUMMARY remain frozen. The authoritative correction ledger adds normalized-result references rather than replacing original/current first-pass tuples. Native malformed XML remains an error.

## FORMULA IDENTITY

P1 formula identity={'FORMULAS_BYTE_IDENTICAL': 143, 'UNDETERMINED': 40}; P2={'FORMULAS_CHANGED_BY_LIBREOFFICE': 31, 'FORMULAS_BYTE_IDENTICAL': 33, 'FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED': 99, 'UNDETERMINED': 28}. The46 strong P2 cases include1 V0→V1 raw cell-formula-byte-identical case and45 semantic-identical/package-changed cases. Semantic identity permits expanded shared formulas and function identifier case only, preserving quoted content, coordinates and array extent; no arbitrary algebraic equivalence. Every strong recovery's sufficiency witness retains V0 raw formulas/structure and changes cache payloads only, reproducing the full assessed typed/formula/color surface of V1. LO formula rewrites are not counted as cache-only. XLSX ZIP ordering/compression is irrelevant to cell-level proof. See FORMULA_IDENTITY.jsonl and witness hashes.

## CACHE STATE

P1:179 formula-bearing workbooks,0 missing-cache workbooks;30 with present caches changed relative to LO replay. P2:171 formula-bearing,153 missing-cache workbooks,4 with present-cache changes. P3:845 formula-bearing,0 missing-cache workbooks;57 changed-present-cache cases. Missing and changed-present can overlap. P1 formula cells=3688057, absent=0; P2 formula cells=1956564, absent=1936046. CACHE_STATE.jsonl measures formula/cache presence, error/numeric/string/boolean values, missing/refreshed/unchanged and changes. CACHE_STALE_RELATIVE_TO_REPLAY means a present value changed; it is not independent correctness proof. No cache-state-only semantic diagnosis.

## PACKAGE PART CHANGES

Changed-part type counts over first-pass recalculated pairs: `{'styles': 583, 'worksheet_formulas_values_and_metadata': 2604, 'other_package_part': 6525, 'core_properties': 389, 'workbook_and_calculation_metadata': 191, 'relationships': 505, 'other_properties': 319, 'calcChain': 1}`. Cache values are extracted independently from worksheet package rewrites. CalcChain/workbook calculation metadata/styles/core properties/relationships/other parts are separately recorded in PACKAGE_DIFFS.jsonl. LO's unrelated metadata/style rewrites do not automatically explain gain; frozen semantic fingerprint and assessed-surface witness control those alternatives. Display/export equivalence beyond captured semantics is not claimed.

## RECALCULATED SCORE RESULTS

| Population | Eligible | Pairs | Exact + / − | Mod + / − | Strong | Harm | Unresolved |
|---|---|---|---|---|---|---|---|
| P1 primary | 183 | 142 | 0 / 0 | 0 / 1 | 0 | 1 | 41 |
| P2 validation | 191 | 163 | 17 / 0 | 123 / 3 | 46 | 17 | 28 |
| P3 normalized context | 848 | 657 | 0 / 0 | 1 / 2 | 0 | 2 | 191 |

183 runs / 98 tasks; 142 scorable pairs; any returned-score tuple change=2; exact0→1=0,1→0=0; modification increases≥.01=0, decreases≥.01=1; regression increases≥.01=0, decreases≥.01=1; classes={'RECALC_NO_MATERIAL_EFFECT': 141, 'UNSCORABLE': 41, 'RECALC_REGRESSION': 1}.

191 runs / 60 tasks; 163 scorable pairs; any returned-score tuple change=129; exact0→1=17,1→0=0; modification increases≥.01=123, decreases≥.01=3; regression increases≥.01=36, decreases≥.01=14; classes={'RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN': 65, 'RECALC_NO_MATERIAL_EFFECT': 35, 'RECALC_REGRESSION': 17, 'CACHE_ONLY_SCORE_RECOVERY': 46, 'UNSCORABLE': 28}.

848 runs / 297 tasks; 657 scorable pairs; any returned-score tuple change=10; exact0→1=0,1→0=0; modification increases≥.01=1, decreases≥.01=2; regression increases≥.01=0, decreases≥.01=2; classes={'RECALC_NO_MATERIAL_EFFECT': 654, 'UNSCORABLE': 191, 'RECALC_REGRESSION': 2, 'RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN': 1}.

P1 modification delta min−.1129/median0/max0, mean−.0007951; no exact gain. P2 modification min−.3333/median+.6204/max+1, mean+.54026; regression min−.0668/median0/max+.3551. These distributions include ambiguous and mixed effects, not only cache-proven recovery. Complete continuous distributions, run/task/category tables and exact outcomes are in RESULT_TABLES.md and scoring_recovery/RESULT_TABLES.md. First-pass P3 had331 pairs/517 unresolved; corrected technical execution is separately labeled.

## CACHE ONLY SCORE RECOVERY

Frozen class requires formula semantic identity, valid structural/semantic snapshot, material gain, changed caches and a cache-only sufficiency witness with complete assessed-cell agreement. P1:0/183 runs,0/98 tasks. P2:46/191=24.08% runs,21/60=35.00% affected tasks;45 Template and1 Debugging. Components:7 exact recoveries,45 modification gains and1 regression-only recovery. Nine archived/numeric-compatible rows support historical qualifications (7 Phase12,2 candidate checkpoint);37 additional gains are normalized-only. One Debugging gain enters error/formula-text fallback on30 cells; it is official-score recovery, not demonstrated numerical correctness. P2 excluding Phase12:39/168 strong cases across14 tasks, with2 archived compatible corrections. Discovery cases are not independent ordinary prevalence. Original P1 loss attributable by this strong class is0 of154 exact failures and0 of41.4766 summed modification-score loss; unresolved bounds prevent a global-zero claim. Verified P2 exact recovery is3 of175 original failures and7.615 summed modification score points of91.2471 loss (descriptive lower bounds,1.71%/8.35%, not representative historic prevalence).

## RECALC ASSOCIATED AMBIGUOUS CASES

P2 has65 RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN gains; P3 normalized count=1. Formula changes, names/structure/metadata changes, iteration, assessed-surface disagreement or other semantic uncertainty block strong attribution. Historical/current drift or unverified source bytes separately block retroactive correction even when a current pair is causally strong. Ambiguous cases never inflate the cache-only numerator.

## RECALC REGRESSIONS

P1 has one material Financial_Model:14_05 harm (9052cf9b7b3c3997): modification−.1129/regression−.0129, exact unchanged, formula-byte identity and no captured semantic difference. It remains recalc-associated harm; the frozen harm branch does not generate a sufficiency witness. P2 has17 harms, including mixed modification gains with regression losses; do not hide them behind an average. Gate B read-only inspected Template:10_01 EPS_Accretion!D39 and Template:11_04 PPA!C24. Golden cells are genuinely blank (not missing golden formula caches); V0 already contains formulas with empty caches, while V1 materializes200/−7.5. Recalc exposes pre-existing erroneous fills rather than necessarily damaging formulas. This does not explain every harm or prove cache-only harm; no new harm witness was introduced. A separately labeled read-only inspection of existing P1 harm cells found near-zero floating cache changes: Cash Flow!H48 changes from−5.456968e−12 (equal to frozen gold) to+1.818989e−12 with the same H45-H47 formula. The unchanged official numeric comparator uses relative error when both operands are nonzero, so these tiny residual changes can lose score agreement. This explains inspected cell mismatches, not the entire harm; no tolerance/scorer change or further causal probe was made. See P1_HARM_EXISTING_CELL_INSPECTION.json. Volatility/external/UDF exclusions and formula-change records remain relevant. Native errors remain explicit.

## TEMPLATE

P1: 41 runs / 27 tasks; 41 scorable pairs; any returned-score tuple change=0; exact0→1=0,1→0=0; modification increases≥.01=0, decreases≥.01=0; regression increases≥.01=0, decreases≥.01=0; classes={'RECALC_NO_MATERIAL_EFFECT': 41}.

P2: 108 runs / 32 tasks; 106 scorable pairs; any returned-score tuple change=73; exact0→1=11,1→0=0; modification increases≥.01=73, decreases≥.01=0; regression increases≥.01=7, decreases≥.01=12; classes={'RECALC_NO_MATERIAL_EFFECT': 33, 'RECALC_REGRESSION': 12, 'CACHE_ONLY_SCORE_RECOVERY': 45, 'UNSCORABLE': 2, 'RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN': 16}.

P3 normalized context: 269 runs / 97 tasks; 257 scorable pairs; any returned-score tuple change=0; exact0→1=0,1→0=0; modification increases≥.01=0, decreases≥.01=0; regression increases≥.01=0, decreases≥.01=0; classes={'RECALC_NO_MATERIAL_EFFECT': 257, 'UNSCORABLE': 12}.

All41 P1 Template rows across27 tasks are resolved with no material effect; their submitted caches were already populated. P2 has45 strong cases across20 tasks,9 archived compatible corrections. The research cache effect is heavily Template-concentrated and is not a material alteration of the retained archived-control Template baseline.

## FINANCIAL MODEL

P1: 101 runs / 43 tasks; 73 scorable pairs; any returned-score tuple change=1; exact0→1=0,1→0=0; modification increases≥.01=0, decreases≥.01=1; regression increases≥.01=0, decreases≥.01=1; classes={'UNSCORABLE': 28, 'RECALC_NO_MATERIAL_EFFECT': 72, 'RECALC_REGRESSION': 1}.

P2: 64 runs / 17 tasks; 40 scorable pairs; any returned-score tuple change=39; exact0→1=6,1→0=0; modification increases≥.01=38, decreases≥.01=0; regression increases≥.01=21, decreases≥.01=0; classes={'UNSCORABLE': 24, 'RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN': 38, 'RECALC_NO_MATERIAL_EFFECT': 2}.

P3 normalized context: 316 runs / 100 tasks; 218 scorable pairs; any returned-score tuple change=2; exact0→1=0,1→0=0; modification increases≥.01=0, decreases≥.01=2; regression increases≥.01=0, decreases≥.01=2; classes={'UNSCORABLE': 98, 'RECALC_NO_MATERIAL_EFFECT': 216, 'RECALC_REGRESSION': 2}.

P2 Financial Model supplies38 ambiguous gains and no strong recovery. Formula/semantic changes and24 unresolved cases prevent assigning those gains to cache-only repair. P1 unresolved28/101 prevents a global stability claim; one measured harm is retained.

## DEBUGGING

P1: 41 runs / 28 tasks; 28 scorable pairs; any returned-score tuple change=1; exact0→1=0,1→0=0; modification increases≥.01=0, decreases≥.01=0; regression increases≥.01=0, decreases≥.01=0; classes={'RECALC_NO_MATERIAL_EFFECT': 28, 'UNSCORABLE': 13}.

P2: 19 runs / 11 tasks; 17 scorable pairs; any returned-score tuple change=17; exact0→1=0,1→0=0; modification increases≥.01=12, decreases≥.01=3; regression increases≥.01=8, decreases≥.01=2; classes={'RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN': 11, 'UNSCORABLE': 2, 'RECALC_REGRESSION': 5, 'CACHE_ONLY_SCORE_RECOVERY': 1}.

P3 normalized context: 263 runs / 100 tasks; 182 scorable pairs; any returned-score tuple change=8; exact0→1=0,1→0=0; modification increases≥.01=1, decreases≥.01=0; regression increases≥.01=0, decreases≥.01=0; classes={'RECALC_NO_MATERIAL_EFFECT': 181, 'UNSCORABLE': 81, 'RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN': 1}.

P2 has one strong regression-only fallback-sensitive gain, five harms, eleven ambiguous gains. Official embedded-formula/color modes remain unchanged. P1 has13 unsupported rows and one below-threshold regression change−.0006; no material recovery.

## TASK LEVEL CLUSTERING

All run results are clustered by task and family, never treated as independent repeated prevalence draws. P1=98 distinct tasks,0 affected; P2=60,21 affected (20 Template,1 Debugging); Phase12 overlap is explicitly marked. Task-any-recovery is a descriptive retained-corpus endpoint, not a statistical claim of population prevalence. P1 unresolved potential-recovery range is0–41/183 runs (22.40%) and0–21/98 tasks (21.43%). Known resolved evidence is informative; unsupported or censored cases remain unknown. Full task identities/run multiplicities are in SUMMARY.json and normalized task tables.

## PHASE 12 REPLICATION

All28 retained CONTROL/TREATMENT/SHAM final files replayed;23 eligible submitted candidates and5 retained nonsubmitted supplements (excluded from prevalence). Seven CONTROL files satisfy strong cache recovery; three exact failures resolve. CONTROL modification gains total6.5536. Template:11_04 CONTROL/SHAM are mixed gain/harm; Template:16_02 remains unsupported under frozen volatility policy. Financial Model gains remain ambiguous. Per-file tuples/formula identity/cache transitions are in PHASE12_REPLICATION.jsonl; no supplemental discovery becomes independent prevalence.

| Task / retained arm | Class | Formula identity | V0 exact/mod/reg | V1 exact/mod/reg | Cache changed |
|---|---|---|---|---|---|
| Template:11_01 / Template_11_01_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 0.0/0.9792/1.0 | 48 |
| Template:11_01 / Template_11_01_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 0.0/0.9792/1.0 | 0.0/0.9792/1.0 | 0 |
| Financial_Model:07_02 / Financial_Model_07_02_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_CHANGED_BY_LIBREOFFICE | 0.0/0.0025/1.0 | 0.0/0.0117/1.0 | 3255 |
| Financial_Model:18_03 / Financial_Model_18_03_TREATMENT | RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.7568/1.0 | 0.0/0.9459/1.0 | 1272 |
| Template:06_05 / Template_06_05_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 1.0/1.0/1.0 | 24 |
| Template:06_05 / Template_06_05_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 1.0/1.0/1.0 | 1.0/1.0/1.0 | 0 |
| Template:06_25 / Template_06_25_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 0.0/0.9643/1.0 | 55 |
| Template:06_25 / Template_06_25_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.9464/1.0 | 0.0/0.9464/1.0 | 12 |
| Template:10_02 / Template_10_02_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 0.0/0.963/1.0 | 26 |
| Template:10_02 / Template_10_02_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 0.0/0.6667/0.9927 | 0.0/0.6667/0.9927 | 0 |
| Template:11_03 / Template_11_03_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 0.0/0.6471/0.9965 | 31 |
| Template:11_03 / Template_11_03_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 0.0/0.5294/1.0 | 0.0/0.5294/1.0 | 0 |
| Template:11_04 / Template_11_04_CONTROL | RECALC_REGRESSION | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 0.0/0.3571/0.9509 | 34 |
| Template:11_04 / Template_11_04_SHAM | RECALC_REGRESSION | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 0.0/0.3571/0.9509 | 34 |
| Template:11_04 / Template_11_04_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 0.0/1.0/0.9509 | 0.0/1.0/0.9509 | 0 |
| Template:14_03 / Template_14_03_CONTROL | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 0.0/0.9818/1.0 | 0.0/0.9818/1.0 | 0 |
| Template:14_03 / Template_14_03_SHAM | RECALC_NO_MATERIAL_EFFECT | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.9818/1.0 | 0.0/0.9818/1.0 | 0 |
| Template:14_03 / Template_14_03_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 0.0/0.8909/1.0 | 0.0/0.8909/1.0 | 0 |
| Template:06_09 / Template_06_09_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 1.0/1.0/1.0 | 119 |
| Template:06_16 / Template_06_16_CONTROL | CACHE_ONLY_SCORE_RECOVERY | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0/1.0 | 1.0/1.0/1.0 | 106 |
| Template:06_16 / Template_06_16_TREATMENT | RECALC_NO_MATERIAL_EFFECT | FORMULAS_BYTE_IDENTICAL | 1.0/1.0/1.0 | 1.0/1.0/1.0 | 0 |
| Template:16_02 / Template_16_02_CONTROL | UNSCORABLE | UNDETERMINED | 0.0/0.0/0.9956 | NA/NA/NA | 0 |
| Template:16_02 / Template_16_02_TREATMENT | UNSCORABLE | UNDETERMINED | 0.0/1.0/0.9978 | NA/NA/NA | 0 |
| Debugging:03_03 / Debugging_03_03_TREATMENT | UNSCORABLE | FORMULAS_CHANGED_BY_LIBREOFFICE | 0.0/0.0/0.0 | 0.0/0.0/0.0 | 553 |
| Financial_Model:12_01 / Financial_Model_12_01_CONTROL | RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.057/1.0 | 1.0/1.0/1.0 | 1685 |
| Financial_Model:12_01 / Financial_Model_12_01_TREATMENT | RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN | FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 0.0/0.0092/1.0 | 0.0/0.9596/1.0 | 1688 |
| Financial_Model:17_05 / Financial_Model_17_05_CONTROL | UNSCORABLE | UNDETERMINED | NA/NA/NA | NA/NA/NA | 0 |
| Template:06_09 / Template_06_09_TREATMENT | UNSCORABLE | FORMULAS_BYTE_IDENTICAL | 0.0/0.0/0.0 | 0.0/0.0/0.0 | 0 |

## HISTORICAL FAILURE REINTERPRETATION

Nine verified archived P2 score boundaries are cache-sensitive; see HISTORICAL_FAILURE_CORRECTIONS.jsonl and HISTORICAL_CLAIM_IMPACT.md. Only three exact failures resolve; six remain failures despite component gains. Task-specific semantic/model-error attribution was not established by the retained linked report/failure-tag audit, so no named architectural diagnosis is declared false merely from a score change. A broad report reference is insufficient. The authoritative correction ledger preserves old scores, current V0, recalc V1, hashes, formula/cache proof, interpretation scope and original references. Raw byte-unverified candidates do not justify retroactive failure corrections.

## PRIOR CLAIM IMPACT

HISTORICAL_CLAIM_IMPACT.md covers every preregistered claim ID using UNAFFECTED, NUMERICALLY CHANGED, INTERPRETATION SAME, BOUNDARY MOVED, REQUIRES REBASELINE and UNKNOWN with scoped distinctions. Phase12 demotion/mechanical exposure, recorded tool behavior/tokens/costs, deterministic product read timing and explicit runtime events survive. Unequal-refresh score contrasts require a compatible future endpoint. P1 resolved submitted scores show no cache-only baseline correction; unsupported coverage and historical build identities remain unknown. Other research raw-output gains flag endpoint sensitivity, without proving their archived historical scores or architectural interpretations were wrong.

## RECALC COST

Main unique-source recalculation965 executions:1263.965s total, median.9464s,p90 2.5789s,max7.555s, mean1.3098s. Scoring/count validation6361.701s summed; row time sum10597.226s,median2.4678s,p90 23.271s. Final detached main attempt2812.411s wall; interrupted attempts preserved separately (host/resource crashes and API-server restart; attempt3 active-wall lower bound7414.86s). These sums are not a clean production service benchmark and include audits/caches/retries. Operational recalc failures among attempted primary executions were zero; unsupported and scorer failures are separately explicit. New normalization cost: {"rows": 403, "wall_seconds": 4310.447028319002, "new_recalculations": 0, "results_hash": "e73f2da80c08c1c99579a862f02eea2ba1eb2cbcdcc808e27b5028ef9a5aaa07"}. Sole follow-up cost: 1085.515258452011s wall; {"rows": 310, "unique_source_executions": 306, "unique_recalc_seconds": 336.83300937496824, "recalc_statuses_unique_sources": {"RECALC_PASS": 306}, "scoring_seconds_sum": 407.691595323995, "failure_policy": "one unscorable official comparison remains unresolved; no silent raw fallback", "wall_seconds": 1085.515258452011}. Trajectory/model treatment/API-dollar cost zero; permitted independent-review usage/cost is not exposed by collaboration tools and is not claimed free.

## SURPRISE TRIGGER STATUS

Frozen trigger P2 MATERIAL_REGRESSIONS_GE_5_PERCENT fired (17/191=8.90%). Ledgers and summary were frozen before Gate B; raw reviewer output and disposition are separate. No threshold/classifier/population changes followed the surprise. More than20% exact-change and frequent-formula-rewrite triggers did not fire in ordinary strata. Technical normalization cannot retroactively erase the frozen surprise. The macro description/execution discrepancy was separately disclosed and bounded, without changing already-run primary mode4 evidence.

## FOLLOW UP PROBE

The only bounded causal follow-up compares mode0 (NEVER_EXECUTE) against retained primary mode4. Frozen spec SHA256 `36fa620a9015aafd60ed53b1c4b30f37f99aaf4ea54a89ffe47d631e104f3998`; all successful readable P1/P2 plus separately labeled Phase12 supplement, no score selection. Results: `{'MACRO_MODE_EQUIVALENCE_CONFIRMED': 309, 'FOLLOWUP_UNRESOLVED': 1}` across310 rows/306 unique sources (143 P1,163 P2,4 separately labeled supplements); official tuple differences=0, captured semantic differences=0, typed-cache differences=0. Compare both variants under one validated current official execution wrapper; original mode4 scores/failures retained separately. This qualifies only tested successful sources and never turns primary mode4 into disabled-macro execution. Formula/cache/semantic equality and score equality are distinct requirements; unresolved cases stay unresolved. No second causal probe. Auxiliary same-byte scoring recovery is routine execution normalization, not another workbook intervention.

## STRONG REVIEW AFTER REPLAY

Primary interpretation was frozen before Gate C and remains unchanged. Independent review accepts the scoped C decision and selective score qualifications, while challenging universal LibreOffice fairness and optimal evaluation-only placement. Accepted final wording is YES — RECOMMENDED BUT NARROW; the earlier REQUIRED proposal remains in the frozen primary analysis and before-review policy snapshot. Evaluation-only is the minimum evidenced boundary, not tested superiority or futility of submit/readback. No verified old semantic-failure attribution was refuted. See STRONG_REVIEW_POST.md and verbatim raw review. Neither review rewrites primary evidence or enters scoring.

## RECALC FAIR BASELINE VERDICT

**C — CACHE EFFECT EXISTS BUT DOES NOT MATERIALLY ALTER BASELINE.** This is a no-demonstrated-material-alteration decision, not established absence of effect. It concerns the preregistered primary archived ordinary-control population and its already refreshed submission pipeline. Zero proven P1 task recoveries meets neither broad nor narrow threshold. It does not dismiss the large normalized P2 effect or establish zero effect in unresolved/unretained ordinary submissions. The mechanism generalizes beyond the Phase12 discovery outputs, predominantly in research Template endpoints; a material flaw across the retained historical ordinary archive baseline was not established.

## HISTORICAL EVIDENCE VERDICT

**SELECTIVE HISTORICAL REINTERPRETATION REQUIRED.** Qualify the nine verified research score boundaries and unequal-refresh causal contrasts. Do not discard the ordinary archived baseline wholesale or rewrite original history. Distinguish scope of component recovery from complete task correctness and lack of specific semantic-attribution evidence.

## SCAFFOLD RECOMMENDATION

**ADD RECALC BEFORE EVALUATION ONLY.** This is the minimum evidenced fixed-output policy, not experimentally established optimal placement. Evaluation-side recalculation is sufficient for the demonstrated fixed-workbook gains. The replay does not identify an incremental score benefit from additionally recalculating inside the agent scaffold before submission once evaluation refresh is reliable. Competent deliverable/readback tooling could justify submission refresh separately; this phase provides no treatment evidence for its additional necessity. Existing ordinary archive refresh should be retained, not duplicated as a claimed new agent capability. No runtime implementation in this phase.

## EVALUATOR RECOMMENDATION

**YES — RECOMMENDED BUT NARROW**, for compatible research endpoints targeting evaluated formula behavior; the strongest numerical recovery is Template-concentrated. Preserve the existing ordinary archive refresh and make that boundary explicit in research scoring. Same original formulas plus changed caches reproduce complete assessed-surface gains, so unrefreshed data_only evaluation can confound semantics with cache materialization. A calculation boundary does not itself certify reference/engine compatibility, and universal LibreOffice normalization is not compelled. Recalc can expose wrong formulas at expected blanks and can regress; that is not a reason to accept false blank-cache agreement as semantics. Use isolated immutable original/copy→pinned LO calculate/save→separately hashed result→official scorer, with errors explicit and no model/repair. Formula-only or color evaluation modes remain declared; unsupported functions/macros/links/volatility require explicit policy, not universal claims. See RECALC_FAIR_BASELINE_SPEC.md.

## REBASELINE SCOPE

Retain P1 scores as evidence of the old already-refreshed pipeline. Add nine local research score qualifications; audit endpoint compatibility for raw-output research comparisons before reusing them as clean causal baselines. Do not insert the160 unverified candidate scores into old ledgers. P3 remains secondary, with separate normalized execution evidence and no ordinary prevalence pooling. No automatic rerun of historical model experiments. Scope future rebaselining to comparisons whose retained bytes/evaluator boundary are actually affected; preserve transcript/cost/runtime evidence.

## NEXT STEP

Close Phase12R with the additive correction ledger, frozen raw evidence, separately normalized execution and the single follow-up. Future score-dependent model research must declare a recalc-fair candidate/evaluator boundary and verify reference/engine compatibility before it begins. Identify which archived comparisons require endpoint qualification first; do not reopen the verifier or launch historical model reruns. Any production adoption is a separate authorized implementation phase. Original history and product runtime remain untouched.
