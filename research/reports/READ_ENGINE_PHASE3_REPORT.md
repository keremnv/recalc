# Read Engine Phase 3 — fixed RC-population product-boundary reversal test

Status: **offline experiment; no RC or public-product change**. The [v1 preregistration](../../read_engine_phase3/PREREGISTERED_SPEC.md) was hashed (`555a56750036c0cb5ded88fdfb636e9205f22aa0340dce00eb9bf93fa9a49ab7`) before harness/artifact implementation or benchmark execution. The [population](../../read_engine_phase3/population.json) (SHA-256 `ea83d4f603430d78b30b8b85b70bb5a8ee9ef916350060bbf52c8f67701651dc`) is copied by identity from the frozen RC eligible and representative views. [Implementation hashes](../../read_engine_phase3/implementation_identity.json) were pinned before correctness and timing; they still verify. Complete [correctness](../../read_engine_phase3/raw_correctness.jsonl), [invocation timings](../private-data-manifest.json), [session timings](../../read_engine_phase3/session_timings.jsonl), [runtime events](../../read_engine_phase3/runtime_events.jsonl), [profile](../../read_engine_phase3/profile.json), and [paired analysis](../../read_engine_phase3/analysis.json) are retained.

Ratios are treatment/control for the **same script and workbook bytes**; below 1 is faster. Primary workload ratios use the median of three scored repetitions; the secondary view uses two. The 2,000-resample bootstrap intervals are conditional on the frozen scripts. The 22 primary scripts represent 14 task IDs; the 30 secondary scripts represent 21. These intervals do not make the rows independent task-population draws. OS filesystem cache was uncontrolled. All staging happened outside the command timers, as in the old RC study.

## OLD RC FAILURE REPRODUCED AS BASELINE

The old packaged-RC result is carried forward as the **historical baseline**, not rerun: 22/22 eligible scripts were slower than direct Python, with median paired ratio **2.017**, and four genuine semantic failures across the selected RC views. The original RC built an openpyxl-derived broad SQLite index afresh per invocation. Phase 3 verified the same normalized script hashes and source/staged workbook hashes for every selected workload before execution. The original installed RC virtual environment still supplied Python 3.13.12 and openpyxl 3.1.5 for both Phase-3 arms. The product-shaped harness differs from the old installed CLI in implementation, so the old/new ratio comparison is a same-population historical bridge, not a same-run A/B estimate of a single code change.

## NEW PRODUCT-SHAPED ARCHITECTURE

CONTROL was direct `<RC Python> workload.py`. TREATMENT was a fresh parent command that loaded the RC defaults, validated the workdir/script, created a UUID run, used the **unchanged RC whole-script classifier**, discovered top-level `.xlsx` files, hashed sources, built or reused persistent state, captured a pre-snapshot, launched a fresh child, captured post-state, derived/validated any package effects, and persisted summary/events. Capture remained enabled for statically read-only admitted scripts. The child received process-local `sitecustomize`, an exact script-path guard, and interposed ordinary `openpyxl.load_workbook` without changing a script import or call. Supported reads used the direct representation; unsupported behavior went to normal reference openpyxl and was logged. The treatment parent/child code lives only under [read_engine_phase3](../../read_engine_phase3).

The new persistent cache was outside UUID run directories. Each scored primary repetition began with an empty private cache: first treatment invocation `BUILT`, next four `REUSED`. The same staged workdir path was reset from frozen bytes before each command. All control commands were independent. External command timing included parent startup through final exit; observed N-session totals summed N actual command walls, excluding symmetric restaging.

## SAFE PERSISTENT ARTIFACT

`JSONZ_MEMORY_V1` stores the Phase-1 `MemoryBook` logical state in a deterministic typed JSON payload compressed with zlib. Its envelope has `LCRE3JZ1` magic, length bounds, explicit source/decoder/contract/format identities, payload and whole-artifact hashes, and a schema validator. A sidecar is atomically published last after temporary-file writes, sync and rename. Artifact keys bind whole-file workbook SHA-256, decoder SHA, contract version and format version. It contains no pickle or executable deserializer.

Before script timing, the artifact matched the frozen direct decoder on **39/39 Phase-1 corpus workbooks** (all encoded cells, ordered sheets, bounds and merged metadata) and **51/51 archived traces reopened in fresh processes**. Two fixed staged workbooks passed missing/truncated, version-mismatch and same-path changed-source rejection/restoration probes. Direct construction/serving was guarded against `openpyxl.load_workbook`; fallback was the only treatment route to a normal reference parse. This gate establishes parity with the frozen narrow decoder, not full openpyxl coverage. The malformed-oracle Phase-1 workbook is still not a normal-openpyxl semantic pass.
The decoder continues to use openpyxl utility classes and helpers for formula and date/format semantics; it is independent of **openpyxl workbook parsing**, not of the whole openpyxl library.

## PRIMARY POPULATION IDENTITY

The primary view is exactly the old [22-script RC eligible list](../history/rc_acceleration_validation/eligible_population.json), with 14 tasks and 14 source workbook hashes. Source scripts were copied byte-for-byte from the old normalized workload archive as `workload.py`; each `input.xlsx` was copied byte-for-byte from the old manifest source. Before every command, the staged script and workbook SHA-256 values were verified. No workbook literal, eligibility criterion, task or script was changed. All 22 were admitted, all 22 contacted direct serving, and all 22 had valid `BUILT` cold and `REUSED` warm witnesses. The secondary population remained the separate exact 30-script RC representative view.

The workload-level historical bridge follows. `Fallback` means at least one normal reference parse in a scored treatment; every artifact status was `BUILT → REUSED`. New semantic status is exact across all scored comparisons.

| Workload | Old RC ratio | Phase-3 cold | Phase-3 warm | Old semantic status | New semantic status | Artifact status | Reference fallback? |
|---|---:|---:|---:|---|---|---|---|
| Financial_Model_15_03__103457370cae | 1.759 | 1.683 | 1.034 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_08_03__59b98508fd79 | 2.644 | 2.416 | 1.540 | EXACT | EXACT | BUILT → REUSED | Yes |
| Financial_Model_08_03__751f6966e68d | 1.930 | 1.508 | 0.608 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_08_01__2ea507d758dc | 1.541 | 1.495 | 0.596 | EXACT | EXACT | BUILT → REUSED | No |
| Debugging_01_06__7b42a0f86b41 | 2.794 | 2.407 | 2.073 | EXACT | EXACT | BUILT → REUSED | Yes |
| Financial_Model_08_01__8021d8d90c40 | 1.695 | 1.477 | 0.595 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_15_03__472e28fbd6e0 | 2.521 | 2.358 | 1.749 | GENUINE | EXACT | BUILT → REUSED | Yes |
| Financial_Model_02_04__5ac07a9edb67 | 1.665 | 1.502 | 1.281 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_18_05__39d21da726e7 | 2.005 | 1.974 | 1.481 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_07_01__23c57fc578fc | 2.538 | 1.212 | 0.427 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_02_01__4dbc773c2ade | 1.724 | 1.787 | 1.301 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_11_02__a443eee257b4 | 2.065 | 1.005 | 0.699 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_11_02__6a75b927c3f6 | 1.766 | 1.054 | 0.701 | EXACT | EXACT | BUILT → REUSED | No |
| Template_03_03__c76ea596b408 | 2.381 | 2.313 | 2.206 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_02_01__e87a34eb884e | 1.680 | 1.504 | 1.242 | EXACT | EXACT | BUILT → REUSED | No |
| Financial_Model_07_01__90a7533589a4 | 3.316 | 1.197 | 0.428 | EXACT | EXACT | BUILT → REUSED | No |
| Debugging_08_04__2dde74bd671e | 1.930 | 1.448 | 0.909 | GENUINE | EXACT | BUILT → REUSED | No |
| Debugging_01_06__26b457c478d0 | 2.690 | 2.028 | 1.711 | EXACT | EXACT | BUILT → REUSED | No |
| Template_06_12__17725eca76da | 2.453 | 2.312 | 2.152 | EXACT | EXACT | BUILT → REUSED | No |
| Debugging_05_02__31823ebc55b0 | 1.213 | 1.020 | 0.339 | EXACT | EXACT | BUILT → REUSED | No |
| Debugging_05_02__9e6b464d2158 | 2.030 | 1.955 | 1.217 | EXACT | EXACT | BUILT → REUSED | Yes |
| Template_16_07__9662584ede5e | 2.509 | 2.120 | 2.294 | GENUINE | EXACT | BUILT → REUSED | No |

## SEMANTIC RESULTS

The primary gate compared direct Python to T-COLD and T-WARM before scoring: **44/44 exact pairs**. All **330/330 scored primary pairs** were exact by exit code, stdout/stderr bytes and post-run file/package state. No normalized exception was needed in the primary view. Every scored treatment had a runtime profile and a valid artifact witness; all 22 scripts contacted the direct path. These results repair the old primary semantic failures within the tested script surface, but do not claim broad openpyxl equivalence.

The secondary view had **104 exact** and **16 `VOLATILE_ONLY_DIFFERENCE`** scored pairs, all 120 with matching normalized observable results and output state. The 16 rows came from four scripts printing Python memory addresses of openpyxl formula objects; the normalization replaced only those addresses, as in the old RC diagnostic method. No genuine semantic or execution failure was recorded in either view.

## OLD FOUR FAILURE WORKLOADS

The historical four genuine failures were three primary scripts and one representative-only script. All four are exact now:

| Workload | View | Old failure surface | Phase-3 result and route |
|---|---|---|---|
| Debugging_08_04__2dde74bd671e | Primary | Repeated cell-value observation | Exact through direct cell reads; no reference fallback |
| Financial_Model_15_03__472e28fbd6e0 | Primary | Workbook iteration/worksheet observations | Exact; workbook iteration uses logged reference fallback |
| Template_16_07__9662584ede5e | Primary and secondary | Formula object `.text` observation | Exact through typed direct formula value |
| Template_06_23__fc41ad37c48b | Secondary only | Workbook iteration/dimensions | Exact; iteration uses logged reference fallback |

The fallback cases pay for both direct state construction and a later normal reference parse on cold contact. Semantic success does not imply that their read-engine economics are favorable.

## COLD END-TO-END RESULT

The primary T-COLD/CONTROL paired median was **1.595**, geometric mean **1.652**, 2,000-resample median interval **1.477–2.028**, range **1.005–2.416**; **0 faster, 22 slower, 0 tied**. All pairs were exact, all scripts contacted direct serving, and all cold artifacts were built inside the command. The old same-population RC median was 2.017, so the magnitude narrowed historically, but the sign remained negative. This does **not** support cold product-shaped speed. The cold result charges config/admission, source SHA, direct build, safe serialization/publication, pre/post capture, child process/bootstrap, script/fallback, validation and diagnostics.

## WARM END-TO-END RESULT

The primary T-WARM/CONTROL paired median was **1.230**, geometric mean **1.040**, median interval **0.700–1.540**, range **0.339–2.294**; **9 faster, 13 slower, 0 tied**. Each warm treatment actually reused a previously published valid artifact in a fresh command and child process. The 14-task equal-weight warm geometric ratio was **1.146** (task-cluster bootstrap interval **0.867–1.512**). Reuse is established; aggregate warm speed is **not**. A favorable subset of scripts is visible in the fixed distribution, but no new population was selected or used as the primary verdict.

## SESSION RESULT

These are observed sums of N complete treatment commands divided by N independent control commands on the same script, with each repetition starting without an artifact. No construction or process startup was amortized away. Session N=1 agrees with T-COLD.

| N | Median ratio | Geometric mean | 95% bootstrap median interval | Faster/slower/tied | Range |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.595 | 1.652 | 1.477–2.028 | 0/22/0 | 1.005–2.416 |
| 2 | 1.397 | 1.371 | 1.056–1.859 | 5/17/0 | 0.684–2.334 |
| 3 | 1.338 | 1.260 | 0.898–1.810 | 8/14/0 | 0.566–2.276 |
| 5 | 1.307 | 1.181 | 0.783–1.709 | 8/14/0 | 0.476–2.255 |

No measured primary session horizon has median ratio below 1 or a majority faster. Phase-2's 51 contact-selected trace sessions broke even by N=2, but that endpoint excluded this full parent/child/capture boundary and used seven snapshots. Phase 3 does not contradict that mechanism result.

## REPRESENTATIVE VIEW

The exact frozen [30-script RC representative list](../history/rc_acceleration_validation/representative_population.json) was run after the primary test. **8/30** scripts were admitted, contacted direct serving, built cold artifacts and reused them warm; **22/30** remained reference-only. **23/30** had at least one logged normal reference parse, including reference-only and proxy-escape paths. Semantic results were 104 exact and 16 volatile-address-only pairs, with no genuine difference.

| Secondary endpoint | Median ratio | Geometric mean | 95% bootstrap median interval | Faster/slower/tied | Range |
|---|---:|---:|---:|---:|---:|
| Cold | 1.571 | 1.602 | 1.463–1.934 | 0/30/0 | 1.012–2.471 |
| Warm command | 1.618 | 1.480 | 1.234–2.022 | 3/27/0 | 0.594–2.372 |
| Observed N=2 session | 1.582 | 1.551 | 1.267–1.992 | 1/29/0 | 0.878–2.421 |

For 22 non-contact scripts, “warm” denotes the second command in the sequence; it is **not** an artifact-reuse measurement. The representative view is descriptive prevalence/product shape, not a substitute primary speed population or a broad equivalence proof.

## REFERENCE FALLBACK

Four primary workloads triggered reference fallback during scored treatment. All **60** primary scored reference parses were classified `proxy_operation_escape`, one per affected invocation. Of the 330 primary scored treatment invocations, **12** paid `BUILT` direct state **plus** later normal reference parse, and **48** paid `REUSED` state plus reference parse. No unsupported-mode, missing/stale artifact, source-rejected, or runtime-failure parse occurred in the primary view. The logged route is the Phase-3 analogue of the old A+B double-parse concern. Workbook iteration and other behavior outside the frozen narrow read contract deliberately use reference openpyxl. Secondary reference-only scripts were observed with `source_rejected_before_interposition` events; the experimental bootstrap still logged them, an observability overhead relative to the old RC reference-only path.

## OLD VS NEW SETUP COST

Old RC `index_setup_s` on these 22 historical workloads had a **0.264 s** median (range 0.010–2.857 s); its index was built from an openpyxl read-only parse and a broad SQLite schema, then published per invocation. The new measured cold per-workload median components were direct OOXML decode **305 ms**, typed JSON/zlib serialization **50 ms**, atomic publication **13 ms**, and complete artifact `ensure` **448 ms**; source SHA alone was about **0.61 ms**. These new component medians are not additive, and the old/new setup clocks came from different runs and include different internal work. The evidence supports elimination of openpyxl **construction parsing**, not an assertion that this first safe serializer made total cold setup cheaper on every RC workload.

For matched primary workloads, the old SQLite artifact size had median **980,992 bytes** and the safe Phase-3 artifact median **51,306 bytes**; median *paired* new/old size ratio was **0.0438** (range **0.0243–0.0592**). New warm parent artifact discovery/validation took a median **48.5 ms** per workload, and child artifact load/deserialization another **47.8 ms**. Old RC had no genuine reused-artifact product path to compare with those warm attach costs.

## NEW BOTTLENECK

Coarse Phase-3 timers identify the residual boundary. Values below are medians of per-workload component medians on the 22 primary scripts; they are nested or taken from different workloads, so they must not be summed into a synthetic total.

| Component | Cold median | Warm median | Boundary |
|---|---:|---:|---|
| Config/preflight/run directory | 0.50 ms | 0.45 ms | Parent setup |
| Whole-script admission | 0.84 ms | 0.85 ms | Unchanged RC classifier |
| Workbook discovery | 0.22 ms | 0.23 ms | Parent top-level `.xlsx` scan |
| Parent direct decode | 305 ms | absent | Cold artifact build |
| Parent serialization | 50 ms | absent | Cold artifact build |
| Parent artifact discovery/validation | 0.04 ms before build | 48.5 ms | Source/cache verification; warm fully validates and decodes |
| Parent source SHA | 0.61 ms | 0.65 ms | Whole-file freshness |
| Child artifact load | 48.5 ms | 47.8 ms | Fresh-process deserialization |
| Child bootstrap/import | 124 ms | 121 ms | Process-local sitecustomize/openpyxl/runtime setup |
| Child startup residual | 56 ms | 54 ms | External child wall minus measured bootstrap/post-bootstrap; includes interpreter startup/IPC |
| Child wall | 284 ms | 282 ms | Complete script process |
| Pre-capture | 0.33 ms | 0.38 ms | Workbook byte snapshot |
| Post capture/delta/validation | 0.59 ms | 0.54 ms | Mechanical after-run work |
| Diagnostic read + write | 0.27 + 0.66 ms | 0.27 + 0.73 ms | Parent event/summary persistence |
| Parent total | 756 ms | 350 ms | Internal parent timer; external endpoint also charges command startup/exit |

The post-capture timer includes a separately recorded second workbook snapshot (median 0.52 ms cold, 0.47 ms warm); derive, commit, replay and mechanical validation sections were zero on the median read-only workload because no workbook package changed. The warm design fully validates/decodes the artifact in the parent, then loads it again in the child. That duplicate representation work, plus a roughly 121 ms child bootstrap and process residual, matters more than source hashing on these scripts. Capture was retained and charged but was small here. `served_read_time`, pure interpreter startup, and the internal split of parent artifact validation are **UNMEASURED**; no per-cell profiler was added. The measured profile explains why faster supported reads and genuine reuse can coexist with median full-command loss.

## DID THE 2.017 FAILURE REVERSE?

**No.** The same 22 script/workbook identities moved from historical RC median **2.017** to Phase-3 product-shaped cold median **1.595**, but all 22 still ran slower than direct Python. The old semantic failures were fixed in this offline harness; the end-to-end cold sign was not. The historical and new ratios are separately valid full-command measurements with different implementations and runs, not directly subtractable operation savings.

## HAS WARM PRODUCT SPEED BEEN DEMONSTRATED?

**No aggregate product-shaped warm advantage was demonstrated.** This is the first genuine full-command reused-artifact measurement on the frozen eligible scripts, and every primary warm command had a valid `REUSED` witness. Its median ratio was **1.230**, with 9/22 scripts faster; the median interval crossed 1. Some fixed scripts benefited, but the preregistered primary warm decision is `NOT SUPPORTED`. This is an offline product-shaped harness result, not a measurement of a modified public RC.

## HAS ACTUAL PRODUCT INTEGRATION BEEN EARNED?

**No.** The preregistered labels are `READ ENGINE SEMANTICS: SUPPORTED`, `COLD PRODUCT-SHAPED SPEED: NOT SUPPORTED`, `WARM PRODUCT-SHAPED SPEED: NOT SUPPORTED`, and `INTEGRATION CANDIDATE: NOT EARNED`. Safe persistent state and ordinary-script interposition worked mechanically, and the old four semantic failures were resolved on their exact scripts. Neither cold, warm, nor N≤5 session economics passed the fixed full-boundary rule. The public RC, README, presentation files and claim registry remain untouched.

## NEXT STEP

Keep the same 22 primary identities and full-command timer. Inspect the measured parent artifact validation/deserialization duplication, child bootstrap/startup residual and the four direct-plus-reference cases before pre-registering one focused lifecycle change. Then rerun exact semantics and cold/warm/session endpoints on this unchanged population. Do not integrate the artifact or make a public speed claim from Phase 3.
