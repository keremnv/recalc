# Read Engine Phase 7 — certified merged-cell terminal observations

Status: **offline semantic-edge and causal timing experiment; no public product change or public claim.** The [semantic review](read_engine_phase7/MERGED_CELL_SEMANTIC_REVIEW.md) was written before treatment code (SHA-256 `d8898c2fc0d0b910e86829d792a05da82e165e3702fb7c950051d8fa85029d54`). The [preregistration](read_engine_phase7/PREREGISTERED_SPEC.md) was hashed before implementation/scoring (SHA-256 `338cb6ab6d91a0005b492461b1de425ee3efd04ceec29d09869c7a550d3dd121`). The pinned [implementation identity](read_engine_phase7/implementation_identity.json) still verifies. Primary evidence: [37 adversarial fixtures](read_engine_phase7/merged_cell_fixtures.jsonl), [correctness/lifecycle ledger](read_engine_phase7/raw_correctness.jsonl), [raw command timings](read_engine_phase7/raw_timings.jsonl), [session timings](read_engine_phase7/session_timings.jsonl), [profile](read_engine_phase7/profile.json), and [paired analysis](read_engine_phase7/analysis.json).

## PHASE 6 BASELINE

The unchanged Phase-6 H2 architecture has a thin native external observer, one real Python script process, guarded startup interposition, safe persistent derived state, reference fallback and external pre/post effect observation. Phase 6's archived fixed-22 warm H2/PY was `0.598` (15/22 faster, bootstrap upper `0.952`); cold and N≤5 session support were absent. Phase 7 uses that **exact observer binary and frozen runtime as same-run H0**, not archived medians as its causal comparator. Absolute timings drift between runs, so Phase-7 H0/PY is reported independently. The scripts/workbooks are the original exact 22 RC eligible identities, not a newly selected population.

## MERGED CELL SEMANTIC REVIEW

Frozen `ProxyWorksheet.cell` sees a covered merged coordinate and immediately calls `_real_sheet().cell(...)`, materializing a normal reference workbook before the script observes the cell. The three target sources actually use immediate terminal properties: the two Debugging scripts only `.value`; the Financial Model script `.value`, and `.coordinate` only after a non-`None` scalar. Their reference workbook contact counts are 6, 8 and 38 covered children per invocation. Existing `SheetInfo.merged` geometry and `MemoryBook.cell` already encode `(None, 'n')` on those covered coordinates; no OOXML decoder or artifact-format change was needed.

The frozen classifier is **not** a proof that all admitted code observes only those properties. It can admit `type(ws.cell(...))`, `repr(ws.cell(...))` and object storage/escape. A blanket merged-child shortcut would therefore be unsound. The review compared genuine openpyxl `MergedCell`, a dedicated proxy, and a certified terminal-scalar path. A genuine `MergedCell` on a lightweight worksheet gets type/repr/basic fields but style descriptors require real workbook/style state, and parent identity can escape. A custom proxy cannot reproduce `type`/`isinstance`/identity. Both are broader than the evidence earns.

## SELECTED SEMANTIC DESIGN

H1 retains the Phase-6 native observer, real script process, classifier, artifact, decoder, capture and reference fallback. A conservative [whole-script certificate](read_engine_phase7/certificate.py) accepts only if every syntactic `.cell` call is immediately consumed by a read of `.value`, `.data_type`, `.coordinate`, `.row` or `.column`, no `.cell` method alias or cell-object escape appears, and no classifier-proven worksheet is subscripted. Frozen `A1_ADMIT` is also required. Uncertain source is rejected by this certificate, leaving the original merged-child reference route. The certificate does **not** broaden admission.

For a certified script only, the [experimental route](read_engine_phase7/merge_runtime.py) returns the existing `ProxyCell` temporary at a covered child. The script receives only the certified terminal scalar; the temporary object's class and identity are not exposed. Anchor and unmerged paths stay frozen. No script is re-executed, no reference fallback is deleted, and no direct object is later converted into a real object after escape. To use the unchanged hard-coded Phase-6 observer binary, H1 supplies an experimental bootstrap via a root overlay; this changes Python search-path setup slightly and is a measured/control-checked limitation, not a product architecture change.

## OBSERVATION CERTIFICATION

The three targets passed the certificate with 3, 1 and 2 syntactic `.cell` calls respectively. Their covered-child direct counts were exactly **6, 8 and 38** on every scored invocation. A source using `type`, `repr`, `str`, `bool`, comparison, storage, helper pass, dynamic lookup, rich style or parent observation of the **cell object** fails the certificate and retains the frozen reference route. False negatives are deliberate. The rule certifies source expression shape, not arbitrary Python behavior outside the frozen admitted-language boundary. This is an earned narrow surface, **not** a general openpyxl `MergedCell` implementation.

## ADVERSARIAL MERGED CELL FIXTURES

All **37 preregistered fixtures** ran before scored timing: 11 `EXACT_DIRECT`, 25 `REQUIRES_REFERENCE`, one `UNSUPPORTED/UNPROVEN`; all passed their route/no-new-difference checks. The fixture workbook has multiple merges, an anchor, an unmerged cell and styled covered children. Direct fixtures covered value/type-of-scalar, data type, coordinate, row, column, repeated covered calls and a second merge. Object/rich fixtures covered `type`, `isinstance`, repr/str, equality/identity/hash/bool, style ID, font, fill, border, alignment, number format, protection, parent title, arbitrary attribute, variable/list/dict storage, function pass, conditionals, worksheet subscript, method alias and dynamic `getattr`. Of the 25 reference-required cases, 18 reached frozen `proxy_operation_escape`; seven were rejected by unchanged whole-script admission and used reference from load.

The `parent_identity` fixture is important: `cell.parent is ws` differs from normal PY under **both** frozen H0 and H1 because fallback returns a real cell while `ws` remains a proxy. H1 made no new difference and did **not** direct-serve it, but the inherited proxy boundary is not broadly exact for this admitted observation. It is classified `UNSUPPORTED/UNPROVEN`, not counted as a successful merged-cell direct observation or hidden by the fixture gate. Any future product claim about broad Python object fidelity must resolve it separately.

## REFERENCE FALLBACK RULE

For an uncertified script, a covered `.cell()` call still goes through the frozen `_real_sheet().cell(...)` branch and `_real_workbook()` remains available. Unknown named attributes on ordinary `ProxyCell` retain frozen fallback. Workbook iteration is unchanged. This prevents a false positive for `type`, rich styles and later object escape; it does not fix the inherited `parent_identity` limitation noted above. The three target scripts are certified before source execution, so direct serving has no late fallback transition or duplicate user-visible script execution.

## CORRECTNESS ON THE FIXED 22

Every fixed script/source/staged hash matched the Phase-3/RC manifest. Five focused H1 lifecycle checks passed: missing artifact→`BUILT`, valid warm→`REUSED`, truncated artifact→rebuild, changed bytes at the same path→new build, restored bytes→reuse of the original identity. All 22 unscored cold/warm three-arm gates passed. Scoring produced **990 command rows** (`22 × 3 repetitions × 5 invocations × 3 arms`), **330 exact scored correctness rows** and **264 observed session rows**, with no failed gate. All **264 scored H1 warm commands** had a child-confirmed `REUSED` artifact. Exit, stdout/stderr and package/output state were `EXACT` under the frozen comparator for PY/H0/H1. Direct-load contact was unchanged. Target reference-route removal was the only expected fallback difference; the workbook-iteration fallback and all other reference reasons remained unchanged.

## TARGET MERGED CELL WORKLOADS

Warm figures are per-workload **same-run** medians in milliseconds; paired ratios are medians derived from each workload's staged repetitions. `Parse` is the reference-openpyxl parse component, not full command time.

| Fixed workload | PY | H0 | H1 | H1/H0 | H1/PY | H0→H1 parse | Covered direct / invocation |
|---|---:|---:|---:|---:|---:|---:|---:|
| `Debugging_01_06__7b42a0f86b41` | 234.7 | 285.0 | 197.0 | **0.691** | 0.839 | 79.4→0 ms | 6 |
| `Debugging_05_02__9e6b464d2158` | 987.5 | 1,028.8 | 192.1 | **0.187** | 0.195 | 685.0→0 ms | 8 |
| `Financial_Model_08_03__59b98508fd79` | 2,785.3 | 3,517.4 | 1,002.8 | **0.285** | 0.360 | 2,040.1→0 ms | 38 |

All three target outputs remained exact. H0 had 12 `proxy_operation_escape` parses across each target's 12 scored warm commands; H1 had zero. H0/H1 warm artifact-load medians were similar respectively: 26.5/26.2 ms, 19.0/19.3 ms and 804.3/794.8 ms. The full-wall savings are consistent with removing reference parsing and its downstream double work, but component medians are not additive and should not be treated as a precise causal millisecond decomposition.

## REFERENCE PARSE ELIMINATION

The measured route transition is exact for the three certified workloads: 6/8/38 covered contacts become direct reads per invocation; their reference parse count drops from one to zero per command, with parse wall dropping from roughly 79/685/2,040 ms to zero on warm runs. The large case still pays about 795 ms to load the safe artifact; this experiment did not change representation/attach. No normal reference parse was removed for the workbook-iteration case or any uncertified adversarial fixture. The treatment therefore removes a **specific certified parse**, not reference openpyxl from the runtime.

## COLD RESULT

The external cold command timer includes the unchanged observer/process/assurance path, source hash, direct build and publication, script and post work. Paired full-22 results:

| Ratio | Median | Geometric mean | Bootstrap median 95% | Faster / slower | Range |
|---|---:|---:|---:|---:|---:|
| H1/PY | **1.194** | 1.136 | [1.029, 1.274] | 6 / 16 | [0.845, 1.483] |
| H1/H0 | 1.012 | 0.949 | [0.975, 1.031] | 9 / 13 | [0.600, 1.170] |
| H0/PY | 1.208 | 1.197 | [0.987, 1.287] | 8 / 14 | [0.812, 2.179] |

Cold speed remains **unsupported** for the full fixed population. The three target cold H1/H0 ratios were 0.761, 0.626 and 0.600, but construction still dominates many first uses; this targeted edge does not solve the cold lifecycle.

## WARM RESULT

Warm commands require actual child-confirmed reuse and include the same full observer→script→observer command boundary as Phase 6.

| Ratio | Median | Geometric mean | Bootstrap median 95% | Faster / slower | Range |
|---|---:|---:|---:|---:|---:|
| H1/PY | **0.513** | 0.508 | **[0.357, 0.749]** | **18 / 4** | [0.195, 1.114] |
| H1/H0 | **1.001** | 0.860 | [0.986, 1.012] | 11 / 11 | [0.187, 1.026] |
| H0/PY | 0.610 | 0.591 | [0.389, 1.042] | 15 / 7 | [0.197, 1.263] |

H1/PY passes the unchanged Phase-6 warm rule (median <1, majority faster, bootstrap upper <1) on the same contact-selected 22. Median signed H1−PY excess is −249.1 ms (range −1,922.0 to +52.5 ms). A task-cluster descriptive sensitivity view has H1/PY median 0.606 over 14 tasks, 11 faster/3 slower, interval [0.357, 0.847]. These are fixed-workload offline results, not broad product speed evidence. H1/H0's median near one correctly reflects that only three of 22 workloads contact the new semantic edge.

## SESSION RESULT

Each measured N-command session starts without an artifact and then performs fresh commands with genuine reuse. Ratios use observed full-command sums, not multiplication of a warm microtiming.

| N | Ratio | Median | Geometric mean | Bootstrap median 95% | Faster / slower | Range |
|---:|---|---:|---:|---:|---:|---:|
| 1 | H1/PY | 1.194 | 1.136 | [1.029, 1.274] | 6 / 16 | [0.845, 1.483] |
| 1 | H1/H0 | 1.012 | 0.949 | [0.975, 1.031] | 9 / 13 | [0.600, 1.170] |
| 2 | H1/PY | **0.878** | 0.841 | **[0.737, 0.965]** | 16 / 6 | [0.555, 1.240] |
| 2 | H1/H0 | 1.004 | 0.921 | [0.974, 1.023] | 10 / 12 | [0.416, 1.225] |
| 3 | H1/PY | **0.708** | 0.747 | **[0.650, 0.916]** | 17 / 5 | [0.433, 1.330] |
| 3 | H1/H0 | 1.013 | 0.918 | [0.985, 1.021] | 8 / 14 | [0.357, 1.176] |
| 5 | H1/PY | **0.662** | 0.659 | **[0.534, 0.858]** | 18 / 4 | [0.333, 1.326] |
| 5 | H1/H0 | 1.008 | 0.901 | [0.988, 1.018] | 9 / 13 | [0.300, 1.108] |

Under the same median/majority/bootstrap criterion, **N=2, 3 and 5 support a favorable measured session result on these 22 scripts**; N=1 does not. This improves on Phase 6's unresolved N≤5 intervals, but does not imply a representative or public product session claim. H1/H0 session medians remain near one because three large target gains are concentrated in a minority of workloads; full pair distributions are in `analysis.json`.

## H1 VS H0 CAUSAL EFFECT

The same observer binary, identical source/workbook bytes, frozen artifact and fallback code, and balanced arm order make the three target H1/H0 contrasts the causal test. They improve by roughly 31%, 81% and 72% in warm full wall, with exact outputs and zero target parse events. The full-22 **median H1/H0 is 1.001 with 11 faster/11 slower**, so there is no population-wide median optimization effect to claim. Its geometric mean of 0.860 reflects the concentrated large target gains. H1's overlay bootstrap also changes import-path setup and adds a certificate check; non-target controls show no uniform gain, and the cross-workload warm bootstrap median was about 1.9 ms higher in H1. These component medians are not a causal subtraction for individual script savings.

## FULL POPULATION EFFECT

On the fixed 22, H1/PY warm changed from 15/7 for same-run H0/PY to **18/4** for H1/PY; the three former merged-fallback losers crossed ratio one. The full-population H1/PY median is 0.513 versus same-run H0/PY 0.610. This is a valid paired fixed-population comparison, while H1/H0 median remains near one because the treatment only helps three scripts. The 22 scripts represent 14 tasks and were selected for indexed contact in the old RC study. Neither the task bootstrap nor this exactness gate establishes broader Python/openpyxl equivalence or representative prevalence.

## NEGATIVE CONTROL WORKLOADS

The three tiny Templates had zero merged-child direct events and no reference parse in either arm. Their H1/H0 warm ratios were **0.962, 1.025 and 0.991**; H1/PY remained **1.067, 1.114 and 1.053**. This offers no evidence of a uniform bootstrap/process improvement and leaves their short-script fixed tax visible. The workbook-iteration negative control (`Financial_Model_15_03__472e28fbd6e0`) retained 12/12 warm `proxy_operation_escape` events, with reference parse medians 327.3 ms in H0 and 328.4 ms in H1; its H1/PY was 1.099. Its H1/H0 0.928 should be treated as observed timing variation, not a changed iteration route.

## REMAINING WARM LOSERS

Exactly **four** fixed H1/PY warm losers remain: `Financial_Model_15_03__472e28fbd6e0` is `WORKBOOK_ITERATION_FALLBACK`; `Template_03_03__c76ea596b408`, `Template_06_12__17725eca76da` and `Template_16_07__9662584ede5e` are `SHORT_BOOTSTRAP_OVERHEAD`. `MERGED_FALLBACK_REMAINING`: zero. `OTHER`: zero. These labels describe the observed fixed workload mechanisms; they are not an eligibility selector for a new speed population.

## MERGED CELL SEMANTIC VERDICT

**`EXACT MERGED-CELL DIRECT SERVING EARNED` for the certified terminal-scalar surface only.** The direct state already represented the needed merge geometry and `(None, 'n')` scalar; 11 direct adversarial fixtures and all three exact target scripts passed, and uncertain object observations retained reference routing. This verdict does **not** extend to general `MergedCell` objects, style/parent identity, arbitrary admitted code, or the inherited `parent_identity` mismatch. A false positive in the certificate would be a semantic defect, so a production version needs focused review of the AST proof and import/alias boundary before integration.

## WARM SPEED VERDICT

**`SUPPORTED` for H1/PY warm on the fixed 22** under the unchanged preregistered rule: median 0.513, 18/22 faster, bootstrap upper 0.749, exact outputs and 264 valid warm reuse witnesses. Targeted causal speed improvement is clear on each of the three merged scripts. **No full-population H1/H0 median advantage is established** (1.001, interval crosses one), and cold remains unsupported. Measured N≥2 session ratios are favorable under the same fixed-population standard; this is not a public warm/product claim for the unchanged RC.

## AGENT INDEPENDENT SEMANTIC / PERFORMANCE OPINION

The abstraction was worth adding **as an experimental, explicit observation certificate**, not as an always-on merged-cell proxy. It removed expensive full reference parses with no decoder or artifact change, and it made the previously implicit distinction between scalar reads and cell-object escape testable. The 37 fixtures also exposed a useful limit: fallback alone does not make proxy worksheet identity broadly exact. I would preserve that falsifier in any integration review rather than allowing the three successful scripts to stand for general merged-object compatibility.

If responsible for performance next, I would **not** broaden workbook iteration merely to fix one residual script; its object semantics are wider than this earned scalar path. I would first assess production integration and a representative/non-contact run with robust capture semantics. For a focused remaining read-only optimization, child bootstrap/import cost on the three short Templates is the safer next target. Cold demand-scoped construction is a separate, larger lifecycle question.

## INTEGRATION IMPLICATIONS

The offline line now has an earned narrow direct read engine, cross-process persistent state, a tested assurance-preserving thin observer, and a certified merged-child scalar edge. Warm full-boundary speed is supported on the fixed 22, and observed N=2/3/5 session results are favorable on that same population. **Actual product integration is still a separate decision.** Cold first use remains slower; representative and reference-only prevalence was not rerun here; changed-file capture-helper performance was not measured by these read-only scripts; native observer capture bounds/symlinks, portability and production error handling remain open. The inherited proxy `parent_identity` observation also limits any broad compatibility claim. No public RC, README, presentation or claim registry was changed.

## NEXT STEP

Hold the Phase-7 result as frozen experimental evidence and perform an integration-readiness review before changing public product code. That review should validate the certificate as a formal fail-closed boundary, exercise representative/non-contact and changed-file workloads under the full observer timer, and specify production capture/portability behavior. If another isolated speed experiment is warranted first, target short-script bootstrap/import overhead on the unchanged fixed population; keep workbook iteration and cold demand-scoping as separate semantic/lifecycle questions.
