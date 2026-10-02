# Read acceleration: historical evidence versus `librecalc-agent 0.2.0rc1`

This is an audit of archived evidence and frozen implementation, not a new timing experiment. No model was called, no RC file was changed, and no threshold or workload was reselected. Paths below are relative to this repository. A workbook hash is SHA-256 of its source `.xlsx`; a script hash is SHA-256 of the script bytes **after** the RC study's single workbook-literal normalization, unless stated otherwise. A 12-character hash in a table is an identifying prefix; full hashes are in the linked artifacts.

## Evidence provenance

> Curation note: bulk raw artifacts named below (per-run telemetry,
> per-slot transcripts, per-run index manifests, semantic replay) now
> live in the external evidence archive rather than in Git. Resolve
> them via [research/evidence-manifest.json](research/evidence-manifest.json)
> (locations and SHA-256) and [research/EVIDENCE_ARCHIVE.md](research/EVIDENCE_ARCHIVE.md)
> (preservation model). Compact scored tables and manifests remain
> in-repo at the paths shown.

| Study | Original report | Runner / accounting code | Population or workload manifest | Raw timing source |
|---|---|---|---|---|
| Initial Candidate-A shadow and P1/P2 access experiment | [shadow report](research/evidence/CANDIDATE_A_SHADOW_INTERPOSITION_REPORT.md) | [shadow runner](benchmark/candidate_a_shadow_interposition.py), [research index](benchmark/inspection_helpers/index.py) | [historical population](candidate_a_shadow_interposition/historical_population.json), fixture and explicit workbook list in runner | [performance runs](candidate_a_shadow_interposition/performance_runs.jsonl), [amortization](candidate_a_shadow_interposition/amortization.json) |
| A1 classifier repair | [repair report](research/evidence/CANDIDATE_A_A1_CLASSIFIER_REPAIR_REPORT.md) | [repair runner](benchmark/run_candidate_a1_classifier_repair.py) | [replay population](candidate_a_a1_classifier/replay_population.json), [historical contact ceiling](candidate_a_a1_classifier/historical_contact_ceiling.json) | **No speed endpoint**; [semantic replay (archived)](research/evidence-manifest.json), [newly admitted executions](candidate_a_a1_classifier/newly_admitted_executions.jsonl) |
| 12-task A1 checkpoint, hardened rerun and 51 traces | [rerun report](research/evidence/CANDIDATE_A_A1_12_TASK_CHECKPOINT_RERUN_REPORT.md); earlier censored [attempt report](research/evidence/CANDIDATE_A_A1_12_TASK_CHECKPOINT_REPORT.md) | [checkpoint runner](benchmark/run_candidate_a_a1_checkpoint.py), [live scaffold](benchmark/candidate_a_live_treatment.py), [finalizer](benchmark/finalize_candidate_a_a1_checkpoint_rerun.py) | [selected tasks](candidate_a_a1_checkpoint_rerun_01/population.json), [rank rule](candidate_a_a1_checkpoint_rerun_01/population_ranking.json), [identity](candidate_a_a1_checkpoint_rerun_01/identity_manifest.json), [contact traces (archived)](research/evidence-manifest.json), [workbook snapshots](candidate_a_a1_checkpoint_rerun_01/workbook_snapshots.json) | [exact-trace rows](candidate_a_a1_checkpoint_rerun_01/exact_trace_performance.jsonl), [replay fidelity](candidate_a_a1_checkpoint_rerun_01/exact_trace_replay.jsonl), [per-load](candidate_a_a1_checkpoint_rerun_01/per_load_timing.jsonl), [per-read (archived)](research/evidence-manifest.json), [live timing](candidate_a_a1_checkpoint_rerun_01/execution_timing.jsonl), [task timing](candidate_a_a1_checkpoint_rerun_01/task_timing.json) |
| Representative architecture checkpoint | [checkpoint report](research/evidence/REPRESENTATIVE_ARCHITECTURE_CHECKPOINT_REPORT.md) | [runner](benchmark/representative_checkpoint.py), [accounting](benchmark/representative_analyze.py) | [30-task family sample](representative_architecture_checkpoint/population.json), per-slot `reps/*/run_record.json` and `transcript_full.jsonl` | [economics](representative_architecture_checkpoint/economics.json), per-slot `reps/*/candidate_a.jsonl`, `substrate.jsonl`, `timing.jsonl` |
| Packaged RC fresh-invocation validation | [RC report](research/evidence/RC_ACCELERATION_CLAIM_VALIDATION_REPORT.md) | [preparation](benchmark/prepare_rc_acceleration_validation.py), [runner](benchmark/run_rc_acceleration_validation.py), [analysis](benchmark/analyze_rc_acceleration_validation.py) | [full 300-candidate manifest](rc_acceleration_validation/workload_manifest.json), [22 eligible](rc_acceleration_validation/eligible_population.json), [30 representative scripts](rc_acceleration_validation/representative_population.json), [frozen protocol](rc_acceleration_validation/preregistered_spec.json) | [384 raw invocation rows](rc_acceleration_validation/raw_timings.jsonl), [per-workload](rc_acceleration_validation/workload_timings.json), [decomposition](rc_acceleration_validation/timing_decomposition.json), individual `runs/*/cache/librecalc-agent/runs/*/index/manifest.json` |
| Packaged RC reused-state feasibility | [feasibility report](research/evidence/RC_WARM_ACCELERATION_CHARACTERIZATION_REPORT.md) | Public [RC runner](src/librecalc_agent/runner.py) and archived [probe commands](rc_warm_acceleration_characterization/commands.json); no standalone feasibility-runner source is present in the repository | [frozen manifest](rc_warm_acceleration_characterization/workload_manifest.json), [preregistration](rc_warm_acceleration_characterization/preregistered_spec.json) | [reuse validation](rc_warm_acceleration_characterization/warm_reuse_validation.json), [probe](rc_warm_acceleration_characterization/feasibility_probe/public_reuse_probe.json), [build diagnostics](rc_warm_acceleration_characterization/index_build_timings.json); [scored timings](rc_warm_acceleration_characterization/raw_timings.jsonl) is empty by stop rule |

The representative checkpoint and hardened live checkpoint historically called models to **generate** their archived traces. This audit only reads those artifacts. The RC timing study replayed archived control scripts with no model calls.

## Treatment and timer ledger

The words *index-ready*, *fresh invocation*, and *reused state* below refer to the mechanics in this table. They are not interchangeable benchmark conditions. `INCLUDED` means inside the stated headline's clock, `EXCLUDED` means outside it, `AMORTIZED` means prepared once and shared across several measured accesses/operations, `NOT PRESENT` means that study did not perform it, and `UNKNOWN` means the archive cannot establish it.

| Headline / clock start → stop | CONTROL | TREATMENT and state lifetime | Construction / hash / SQLite / publication | Process + bootstrap / attach + metadata | Workbook load + read / fallback parse | Full script / capture + delta + diagnostics |
|---|---|---|---|---|---|---|
| Shadow P1, two repetitions per access count, `perf_counter` immediately before `CandidateALoader.load_workbook` → after N traversals of up to 20×10 cells | N `openpyxl.load_workbook(..., read_only=True)` calls, each followed by read and close; clock surrounds loop | `index.reset()` immediately before timer; first proxy load builds in-process index, then the same proxy/DB is used for N reads. No SQLite publication to child | **INCLUDED:** initial hash, openpyxl read-only parse, cell traversal and in-memory SQLite population, freshness hash. **NOT PRESENT:** file backup/publication | **EXCLUDED:** process startup/imports. **INCLUDED:** proxy acquisition and raw OOXML metadata parse | **INCLUDED:** N reference parses versus one indexed load and N indexed accesses. **NOT PRESENT:** fallback for selected supported operation | **NOT PRESENT:** complete user script, capture, delta, diagnostic persistence |
| Shadow P2, `perf_counter` just before N indexed traversals → after them | Reuses the P1 N-load reference medians as comparator | A single prebuilt proxy/index persists for all N and both timed repetitions | **AMORTIZED/EXCLUDED:** build and hashes before clock; **NOT PRESENT:** publication | **EXCLUDED:** process startup, acquisition/metadata | **INCLUDED:** indexed reads only; comparator includes N `read_only=True` reference loads and reads | **NOT PRESENT** |
| A1 classifier repair | No speed timer | Source admission and semantic replay only; admitted source executes with proxy when supported | Construction can occur in semantic replay, but **NO SPEED ENDPOINT** | **NO SPEED ENDPOINT** | 20/20 newly admitted semantic-exact, not timed acceleration | **NO SPEED ENDPOINT** |
| Hardened live H0/H1 task wall clock, `run_task` timer after input copy → task end | H0 executes ordinary openpyxl under inert spy; **also** receives the common prepared substrate in its parent task runner | H1 uses A1 admission plus child `sitecustomize`, persistent on-disk SQLite per task/workdir, parent in-memory index across tool calls, refresh after shell executions; unsupported source forced to reference | **INCLUDED in both task arms:** initial openpyxl-derived build and refreshes; output/input copy before timer. SQLite publication is part of shared setup | **INCLUDED per Python tool call:** child process/startup, bootstrap, manifest, attach and XML metadata where H1 contacts | **INCLUDED per actual Python call:** reads and fallback parses; task may reopen workbook repeatedly | **INCLUDED:** model/provider wait and full tool trajectory; not the 44.46% estimator |
| Hardened exact-trace 44.46%, `execute_trace` timer immediately before backend acquisition → after trace operations and close (or exception) | For each of 51 recorded H1 traces, three fresh normal `openpyxl.load_workbook(..., data_only=False)` parses, reads, close | For each trace, a prepared SQLite file already exists; three R1 proxy acquisitions/recorded primitive operations, zero normal reference parses on exact traced path. Process-local preparation/DB file reused over six alternating backend runs | **EXCLUDED:** `index.reset/ensure_fresh` openpyxl read-only parse, hashing, traversal, SQLite population and backup performed in `replay_traces` *before* trace timers. That preparation occurs once per trace, not once for the whole experiment | **EXCLUDED:** process startup and sitecustomize. **INCLUDED:** per-R1 SQLite read-only attach, two freshness hashes and raw XML metadata parsing during proxy acquisition | **INCLUDED:** one acquisition plus recorded operations per repetition, and three R0 normal parses per trace; no R1 reference parse for these exact cases. The recorded `load_workbook` event is skipped after acquisition to avoid a second parse | **NOT PRESENT:** complete workload script, capture, delta, diagnostic persistence in timer |
| Representative checkpoint per-load 0.41→0.09 s medians, timer inside load wrappers | H0 inert spy surrounds normal `load_workbook` call; 281 eligible load durations | H1 A1-admitted `load_workbook` wrapper surrounds proxy acquisition; 59 accelerated durations. Parent prepared SQLite initially and refreshes after calls; DB persists per slot/task | **EXCLUDED from load durations**, but initial 24.76 s and refresh 1.16 s are separately charged in task economics. Openpyxl read-only build runs for H1 initial state. H0 has no initial substrate in this study | **INCLUDED in H1 load duration:** attach, freshness hashing and XML metadata on first proxy acquisition; **EXCLUDED:** Python process/sitecustomize import before call | **INCLUDED:** H0 normal parse versus H1 proxy acquisition. **EXCLUDED:** subsequent reads, fallback parses, full script. H0 and H1 durations come from different generated calls, so medians are not script-paired | **EXCLUDED from per-load number**, separately measured task/tool/capture economics |
| RC eligible median ratio 2.017, external `perf_counter_ns` immediately before subprocess invocation → subprocess exit | Fresh direct Python process runs unchanged normalized `workload.py` in staged workdir; normal openpyxl | Fresh CLI process classifies script, creates UUID run dir, builds/publishes index; one child Python process runs script; capture/diagnostics follow. New cache and workdir on **every** invocation, including warm-ups and three scored repetitions | **INCLUDED:** all hashes, openpyxl read-only build, SQLite work, backup, publication. One index build per contacted invocation, 78 scored accelerated loads and 78 builds across selected union | **INCLUDED:** CLI and child startup, sitecustomize, manifest, attach, freshness, XML metadata | **INCLUDED:** complete script, actual proxy reads and any reference fallback parse | **INCLUDED:** pre/post capture snapshots, changed-file delta/validation if any, diagnostics, teardown. Workbook/script staging **EXCLUDED** |
| RC reused-state feasibility | Ordinary direct-Python reference check, no scored ratio | Same cache/workdir/script/workbook for two public RC calls; both made distinct UUID dirs and SQLite files and `rebuilt: true` | Each invocation constructed anew; diagnostic `ensure_s`/`backup_s` recorded, but **NO SCORED SPEED TIMER** | **NO SCORED SPEED TIMER** | One accelerated load in each probe invocation | [raw scored timing file](rc_warm_acceleration_characterization/raw_timings.jsonl) has zero rows |

The A1 repair's historical 72→86 fully eligible executions and +28 estimated read-event opportunity are contact estimates, not performance measurements. The earlier 12-task attempt was censored; the later rerun, rather than the failed attempt, supplies the 51/51 and timing claim.

| Study state scope | Who builds, and how often? | SQLite file reuse / in-memory reuse / workbook reopen |
|---|---|---|
| Shadow P1/P2 | `CandidateALoader` calls research `index.ensure_fresh`, which calls openpyxl read-only builder. P1 resets and builds once **per timed repetition and access-count point**; P2 builds once before all of its access-count points for a workbook. | No on-disk SQLite. P1 reuses in-memory DB/proxy for N traversals in that repetition; P2 reuses both across points. Reference reopens the workbook N times in each P1 repetition; P2's comparator comes from those P1 loops. |
| A1 repair | Repair runner executes frozen sources for semantic differential only; proxy eligibility, not construction frequency, is the treatment under test. | No scored index lifetime or timing ratio to infer. |
| Hardened live | Parent live scaffold calls `prepare_shared_substrate` **once per task/arm** initially and again after shell executions in both arms. Initial construction uses read-only openpyxl; refresh hashes and rebuilds only on generation change. | Each task/arm has its own workdir and SQLite file(s), reused across child Python calls within that task. Parent in-memory state survives calls within the task, resets for next task. H0 child still does normal openpyxl loads; H1 child uses proxy for admitted calls and normal openpyxl for fallbacks. |
| Hardened exact replay | `replay_traces` resets the research index and calls `ensure_fresh` **once for each trace** before *any* of that trace's six timed repetitions. It builds an in-memory DB with read-only openpyxl every time; it backs up only if the hash-named SQLite file does not already exist. | Equal-hash traces may reuse a previously published SQLite **file**; each R1 timed repetition opens a new read-only SQLite connection and reparses OOXML metadata, while R0 reopens the workbook normally. No product process persists across invocations because this is an in-process replay. |
| Representative checkpoint | Parent builds initially **once per H1 slot/task** and refreshes after each call, using read-only openpyxl on build. H0 has no initial index. | One slot's SQLite file and parent in-memory state survive its tool calls; next slot is separate. Each Python tool call starts a child, and reference H0 loads reopen as dictated by generated code. |
| RC cold validation | Public parent resets state and builds every discovered top-level workbook **once per admitted invocation**. Fresh workdir/cache for each warm-up and scored repetition. | Hash-named SQLite sits under a newly generated run UUID; no reuse across invocations or repetitions. Parent in-memory state dies with CLI. Child snapshot can reuse within its one script process, but each selected script has one source load. CONTROL opens normally once. |
| RC reused-state feasibility | Both public invocations each rebuilt from openpyxl despite identical cache/workbook/script. | Distinct UUID paths and SQLite files. The previous on-disk file survived but was never discovered/attached by the second invocation; no in-memory state survived processes. |

**Shadow-report/raw discrepancy:** The shadow narrative says Template P1 first breaks even at **3** accesses and quotes first-access P1 times of 4.694 s (Financial_Model) and 0.0125 s (Template). The preserved [amortization points](candidate_a_shadow_interposition/amortization.json) and [raw performance rows](candidate_a_shadow_interposition/performance_runs.jsonl) instead show Template P1 at three accesses **0.010288 s versus 0.010274 s** (still slower), first observed faster point at **five** accesses, and first-access P1 times **4.778463 s** and **0.013728 s** respectively. This report uses raw rows for those figures. The discrepancy does not affect the index-ready P2 direction or the later 51-trace result, but the narrative's P1 break-even count should not be reused as data.

## Population and identity crosswalk

**Shadow:** 71 source trajectories/309 recoverable Python executions/258 inspection executions were the census; the strict held-out replay admitted three Financial_Model executions and predeclared fallback for 105. The timed P1/P2 subset was only the actual Financial_Model `08_03_Seafood_input.xlsx` (2,173,244 bytes, hash `2b7a84044765`) and Template `06_09_input.xlsx` (6,460 bytes, hash `711ee0011139`). This was a deliberately chosen pair of workbook/access patterns, with synthetic read loops of 1, 2, 3, 5 and 10 traversals; no fixed workload-script hash applies. Other historical and synthetic workbooks in the runner were semantic tests, not the two performance workbooks. A1 repair reused frozen census/live sources, selected by known classifier false positives; it generated no speed population.

The A1 repair's 20 newly admitted source replays came from `Financial_Model:07_01` (9) and `Financial_Model:08_01` (11), with 92 recorded primitive read events across those replay rows. Their individual original source hashes are in [newly admitted executions](candidate_a_a1_classifier/newly_admitted_executions.jsonl); both workbooks and their sizes/hashes appear in the hardened-task table below. The larger historical A0/A1 contact ceiling spans the frozen 309-execution census, not these 20 alone. Neither the 34 known lexical false-positive turns nor the 20 admitted replays is a timed performance sample.

**Hardened rerun:** 12 tasks were ranked by prior A1-eligible executions, repeated-open surplus, read opportunities and deterministic wall time, hence exposure-enriched. The table gives source workbook identity and **dynamic exact-replay** trace/operation volume; zero means no exact contact trace, not zero workbook reads in every live trajectory. Its source scripts were generated within live tasks; there is no single script per task or predeclared script hash. The archived `contact_traces.jsonl` binds each replay trace to task, run, turn, snapshot hash and operation list; `runs/H1/*/transcript.jsonl` holds source commands where recoverable.

| Task | Workbook bytes | Workbook hash prefix | Exact traces | Recorded operations |
|---|---:|---|---:|---:|
| Financial_Model:07_01 | 590,007 | e918281d3d70 | 0 | 0 |
| Financial_Model:08_03 | 2,173,244 | 2b7a84044765 | 11 | 8,332 |
| Financial_Model:08_01 | 2,164,521 | 6d742f67e84f | 14 | 43,109 |
| Financial_Model:15_04 | 292,736 | 9ff136a80080 | 9 | 21,681 |
| Debugging:10_10 | 8,323,836 | 3d95978b7640 | 8 | 220 |
| Financial_Model:06_01 | 1,924,873 | 71233a0b02e0 | 0 | 0 |
| Debugging:01_06 | 57,771 | 9af630a02079 | 0 | 0 |
| Debugging:10_04 | 8,321,373 | e4edbd9397e3 | 0 | 0 |
| Debugging:05_02 | 412,320 | fa7c8d05a020 | 2 | 3,226 |
| Template:13_08 | 7,152 | 591b6250a393 | 1 | 123 |
| Template:03_03 | 7,552 | 3dc2f7d65a9f | 0 | 0 |
| Financial_Model:10_01 | 2,600,708 | 26f8817083ad | 6 | 59,298 |

**Representative checkpoint:** uniformly sampled 10 tasks in each of Template, Financial_Model and Debugging, without exposure ranking. The 30 task IDs are frozen in `representative_architecture_checkpoint/population.json`: Template `01_05,01_06,02_01,04_04,06_02,06_08,06_23,07_02,16_07,16_08`; Financial_Model `02_04,02_05,06_01,08_02,09_02,09_03,10_01,11_02,15_03,18_05`; Debugging `01_04,03_06,04_07,06_05,06_10,07_05,08_01,09_03,09_04,10_07`. Source workbook path/hash is in each slot's `run_record.json`/dataset source; size spans roughly 6 KB to 8.3 MB. Scripts were generated during the archived tasks, so there is no single fixed script hash or read volume per task. Across 60 primary slots, H1 had 282 workbook loads, 59 accelerated loads and 91,231 logged non-load acceleration events. The per-load reference pool has 281 H0 eligible load timings, not matched copies of the 59 H1 scripts. Six exact H0 source scripts from this checkpoint were later normalized into the eligible RC view: `Financial_Model:02_04` one, `11_02` two, `15_03` two, `18_05` one; their archive and line are in the RC manifest.

The following H1 volume is from each primary slot's `candidate_a.jsonl`; a non-load event is a telemetry event, and value timing companions are included, so it is not a count of unique cell reads. A zero may reflect no contact, conservative fallback or a censored trajectory.

| Representative task | Workbook bytes | Hash prefix | H1 loads / accelerated loads | H1 non-load events |
|---|---:|---|---:|---:|
| Template:01_05 | 7,434 | 5f7440ee995d | 10 / 0 | 0 |
| Template:01_06 | 7,335 | 5b57294aba2f | 0 / 0 | 0 |
| Template:02_01 | 6,727 | 1768dcc784d3 | 5 / 1 | 0 |
| Template:04_04 | 7,021 | 6fe31393f4e1 | 15 / 3 | 585 |
| Template:06_02 | 6,303 | 76ff3caea333 | 3 / 2 | 265 |
| Template:06_08 | 6,984 | df35d4aa5498 | 9 / 0 | 0 |
| Template:06_23 | 6,437 | 45dcae55a68f | 2 / 0 | 0 |
| Template:07_02 | 7,745 | 7d63102f21e2 | 0 / 0 | 0 |
| Template:16_07 | 9,480 | d3a7de73ce86 | 15 / 4 | 4,531 |
| Template:16_08 | 7,920 | e624bbe0a36c | 6 / 0 | 0 |
| Financial_Model:02_04 | 66,611 | 1b64bd5ac59b | 7 / 2 | 662 |
| Financial_Model:02_05 | 66,570 | f61402df84ff | 0 / 0 | 0 |
| Financial_Model:06_01 | 1,924,873 | 71233a0b02e0 | 0 / 0 | 0 |
| Financial_Model:08_02 | 2,147,654 | 9928600b0184 | 19 / 3 | 1,747 |
| Financial_Model:09_02 | 2,577,759 | a6aad8ddac8b | 11 / 3 | 9,768 |
| Financial_Model:09_03 | 2,580,566 | 80a0621898fe | 17 / 0 | 0 |
| Financial_Model:10_01 | 2,600,708 | 26f8817083ad | 9 / 7 | 22,639 |
| Financial_Model:11_02 | 593,808 | 2102c51421d7 | 17 / 9 | 15,524 |
| Financial_Model:15_03 | 297,984 | 318eed515474 | 10 / 9 | 34,612 |
| Financial_Model:18_05 | 88,645 | 56adf80d06ec | 6 / 3 | 628 |
| Debugging:01_04 | 85,553 | d01f1c102517 | 26 / 2 | 58 |
| Debugging:03_06 | 103,312 | 04fd2d7d1a21 | 4 / 0 | 0 |
| Debugging:04_07 | 676,567 | d148f7eefd3b | 9 / 5 | 160 |
| Debugging:06_05 | 1,347,154 | 2a690378dc1e | 6 / 0 | 0 |
| Debugging:06_10 | 1,059,926 | 56e031f5fa3e | 11 / 1 | 0 |
| Debugging:07_05 | 415,159 | acb75164e5ce | 17 / 0 | 0 |
| Debugging:08_01 | 282,123 | 623d33a48cd5 | 15 / 0 | 0 |
| Debugging:09_03 | 59,783 | f1ca163a1198 | 4 / 3 | 51 |
| Debugging:09_04 | 58,348 | 84d2660500cc | 16 / 0 | 0 |
| Debugging:10_07 | 8,320,856 | 0d51c60e2cbe | 13 / 2 | 1 |

**RC eligible view:** one normalized read-only source-workbook load per script, at least five *static* read API references, at most two scripts/task. All 22 contacted the accelerated load in each scored repetition. Static counts below are not dynamic cell reads; shipped telemetry does not preserve that count. The script hash prefix is the suffix of the workload ID. The full script and workbook hashes, source provenance, family and byte size are in `workload_manifest.json`; the following makes the selected population inspectable without reselecting it.

| Eligible workload ID | Bytes | Workbook hash | Static refs | Median RC/control ratio |
|---|---:|---|---:|---:|
| Debugging_01_06__26b457c478d0 | 57,771 | 9af630a02079 | 15 | 2.69 |
| Debugging_01_06__7b42a0f86b41 | 57,771 | 9af630a02079 | 11 | 2.79 |
| Debugging_05_02__31823ebc55b0 | 412,320 | fa7c8d05a020 | 5 | 1.21 |
| Debugging_05_02__9e6b464d2158 | 412,320 | fa7c8d05a020 | 5 | 2.03 |
| Debugging_08_04__2dde74bd671e | 281,911 | 3463b88f927d | 8 | 1.93 |
| Financial_Model_02_01__4dbc773c2ade | 66,494 | 2a7aa7cbeda9 | 8 | 1.72 |
| Financial_Model_02_01__e87a34eb884e | 66,494 | 2a7aa7cbeda9 | 6 | 1.68 |
| Financial_Model_02_04__5ac07a9edb67 | 66,611 | 1b64bd5ac59b | 5 | 1.67 |
| Financial_Model_07_01__23c57fc578fc | 590,007 | e918281d3d70 | 9 | 2.54 |
| Financial_Model_07_01__90a7533589a4 | 590,007 | e918281d3d70 | 13 | 3.32 |
| Financial_Model_08_01__2ea507d758dc | 2,164,521 | 6d742f67e84f | 13 | 1.54 |
| Financial_Model_08_01__8021d8d90c40 | 2,164,521 | 6d742f67e84f | 13 | 1.69 |
| Financial_Model_08_03__59b98508fd79 | 2,173,244 | 2b7a84044765 | 7 | 2.64 |
| Financial_Model_08_03__751f6966e68d | 2,173,244 | 2b7a84044765 | 7 | 1.93 |
| Financial_Model_11_02__6a75b927c3f6 | 593,808 | 2102c51421d7 | 19 | 1.77 |
| Financial_Model_11_02__a443eee257b4 | 593,808 | 2102c51421d7 | 15 | 2.06 |
| Financial_Model_15_03__103457370cae | 297,984 | 318eed515474 | 6 | 1.76 |
| Financial_Model_15_03__472e28fbd6e0 | 297,984 | 318eed515474 | 5 | 2.52 |
| Financial_Model_18_05__39d21da726e7 | 88,645 | 56adf80d06ec | 6 | 2.00 |
| Template_03_03__c76ea596b408 | 7,552 | 3dc2f7d65a9f | 7 | 2.38 |
| Template_06_12__17725eca76da | 7,558 | d05d2bcd62e9 | 9 | 2.45 |
| Template_16_07__9662584ede5e | 9,480 | d3a7de73ce86 | 5 | 2.51 |

The RC's separate 30-script representative *view* is a seeded sample of usable archived control scripts, with at most two/task and no A1 admission requirement. It is not the earlier 30-task representative checkpoint. The two RC views overlap each other; their union is 48 distinct scripts, not 52. The warm-feasibility probe reused the exact RC `Template_03_03__c76ea596b408` bytes and script, with no new population.

**Set overlap by underlying task:** hardened ∩ earlier representative = `Financial_Model:06_01,10_01` (2); hardened ∩ RC eligible = `Debugging:01_06,05_02`, `Financial_Model:07_01,08_01,08_03`, `Template:03_03` (6, covering 11 of 22 RC scripts); earlier representative ∩ RC eligible = `Financial_Model:02_04,11_02,15_03,18_05`, `Template:16_07` (5, covering 7 RC scripts). The three-way intersection is empty. The five exact same **source workbook hashes** in representative ∩ RC are listed in the table; the six normalized H0 scripts above are also source-script identical. In hardened ∩ RC, workbook bytes match for all six tasks, but the 51 timed traces only contact three of them: `Financial_Model:08_01,08_03` and `Debugging:05_02` (27 of 51 traces). The RC scripts come from archived H0/control sources; the hardened timed traces came from separate H1 live runs. For 48 recoverable H1 traced commands, comparison with original and normalized RC eligible script SHA-256 found zero script matches; three trace commands could not be reliably recovered from the transcript mapping. Thus an **exact script plus workbook plus trace** pairing between those two speed studies is not established.

## Public RC cost anatomy and parse mechanics

The actual path is `T_total = T_pre + T_child_start + T_workload + T_post`, where `T_pre` ends immediately before the child `subprocess.run`, and `T_post` begins when that child exits. The external RC timer encloses all four. It does not separately timestamp the boundaries, so the equation is an accounting partition, not a measured additive fit. [runner.py](src/librecalc_agent/runner.py), [index.py](src/librecalc_agent/_frozen/index.py), [substrate.py](src/librecalc_agent/_frozen/substrate.py), [runtime.py](src/librecalc_agent/_frozen/runtime.py), [reads.py](src/librecalc_agent/_frozen/reads.py), [capture.py](src/librecalc_agent/_frozen/capture.py) and the child [sitecustomize](src/librecalc_agent/_bootstrap/sitecustomize.py) establish the sequence.

| Phase / operation | Mechanical location and charging | Existing quantitative evidence |
|---|---|---|
| CLI/config/preflight, openpyxl import, run-dir UUID/mkdir, script classification | Parent `cli.main`/`runner.run`, before index construction | **UNMEASURED separately** |
| Workbook discovery | `substrate.prepare`: every top-level `*.xlsx`, excluding `.tmp` names; not limited to paths the script will load | **UNMEASURED separately** |
| Initial workbook hash | `index.ensure_fresh` calls `workbook_hash` before build | **UNMEASURED separately** |
| Parse A; cell traversal/materialization; in-memory SQLite inserts and index creation; second and third whole-file hashes | `index.build_index`: its own initial hash, `openpyxl.load_workbook(..., data_only=False, read_only=True)`, `ws.iter_rows()` over all sheets, `cells`, `anchors`, `temporal` inserts, `ia`/`ic` creation, final freshness hash | Folded into each manifest's `ensure_s`: eligible median **0.252 s** across per-script medians; its pieces are **UNMEASURED** |
| SQLite backup/publication | `substrate.prepare`: in-memory DB backed up to a new file, then renamed; manifest written before and after publication | Backup folded into `backup_s`: eligible median **0.014 s** across per-script medians; manifest writing **UNMEASURED**. `ensure_s+backup_s` per invocation is eligible median **0.264 s** across per-script medians |
| Pre-execution capture snapshot | `capture.snapshot_xlsx` recursively reads all `.xlsx` bytes under workdir | **UNMEASURED separately** in RC |
| Child Python startup; sitecustomize; imports; manifest read | New interpreter executes bootstrap, imports `openpyxl` and runtime, parses manifest once | **UNMEASURED separately** in RC |
| First admitted `load_workbook`: attach, metadata, hashes | `PersistentCompiledSnapshot` rehashes workbook, parses workbook/sheet XML and cell metadata directly, read-only SQLite attach + identity check, rehashes workbook. Subsequent proxy loads in same child can reuse snapshot but rehash at load boundary | RC eligible accelerated-load-event median **0.083 s** across per-script medians. This includes attach/metadata/freshness on first load; parts **UNMEASURED**. It excludes child startup and later reads |
| Proxy operation; optional lazy Parse B | `reads.py`: cell lookups use SQLite; unsupported object behavior invokes `_real_workbook()` and normal `openpyxl.load_workbook(..., data_only=False)` once per proxy object; predeclared unsupported load calls original normal loader directly | Dynamic proxy-read counts absent from RC telemetry; Parse B has event witnesses in four eligible scripts; its elapsed time is **UNMEASURED separately** |
| Complete workload script | Child runs normal Python script once | Isolated `T_workload` **UNMEASURED** in RC; included in total |
| Post snapshot; delta/commit/validation/replay; diagnostic writes | `capture_wrap_timed` always takes post snapshot; delta and verification run for changed `.xlsx` bytes; parent reads event file, writes summary/capture/last-run diagnostics | RC component times **UNMEASURED**; representative checkpoint separately observed 0.342 s total capture across 30 H1 slots, a different lifecycle |

The RC's manifest on disk contains per-workbook `ensure_s`/`backup_s`; `total_s` is added to the returned Python object **after** final manifest publication and is absent from that file. The RC [analysis](benchmark/analyze_rc_acceleration_validation.py) reconstructs setup from per-workbook refresh entries; `raw_timings.jsonl` has `index_setup_s: null` for these runs. Treat those nulls as an instrumentation detail, not zero setup. The eligible median control invocation was 0.313 s; median setup/control fraction across workloads was 0.644, and setup alone exceeded whole control on three scripts. The residual after subtracting instrumented setup has median 0.403 s across per-script medians, but mixes child and wrapper work. Medians of components are not an additive decomposition. The 0.083 s load event is nested in that residual and must not be added again.

**Parse A** happens when a script is A1-admitted and a top-level `.xlsx` exists in its workdir, before the child starts. The current code constructs one index for *every* such workbook even if the child will not load it. `ensure_fresh` hashes once, `build_index` hashes before and after its read-only openpyxl parse: at least three full-file hash reads in the parent per freshly built workbook. A freshly attached child snapshot hashes before and after XML/SQLite initialization; a later load of the same snapshot rehashes again. Capture pre/post makes two further byte reads of each `.xlsx`, for different assurance purposes. These are mechanical counts, not measured time allocations.

**Parse B** is a normal read/write-mode openpyxl workbook parse. It occurs if the A1-admitted child asks for a rich/unsupported behavior from an already returned proxy, such as a worksheet range returning Cell objects, a style/merged feature or other delegated attribute, which calls `_real_workbook()`. It also occurs for a predeclared unsupported load option, failed/absent substrate, or source rejected before setup; in the rejected-source case Parse A is not charged by the public runner. An admitted proxy caches its real workbook, so several unsupported operations on that proxy generally share one B. A new proxy or repeated fallback load can produce additional B parses. A file loaded outside the top-level discovery scope can likewise fall back while an unrelated top-level index was eagerly built.

From the **existing scored RC runtime event files**, 4 of the 22 eligible scripts emitted `openpyxl_fallback_load` once in each of their three treatment repetitions: `Debugging_01_06__7b42a0f86b41`, `Debugging_05_02__9e6b464d2158`, `Financial_Model_08_03__59b98508fd79`, `Financial_Model_15_03__472e28fbd6e0`. Thus 12 of 66 eligible scored treatment invocations **actually paid A+B** as logged; the other 18 scripts paid A with no logged B. All 22 selected scripts have exactly one source `load_workbook` call, so the observed eligible records do not show multiple B parses within one invocation. This is separate from the four known semantic-failure scripts; the sets are not identical. The event identifies B's occurrence, not its isolated duration. Fail-closed paths could cause B in other workloads, and multiple B parses remain possible in scripts with repeated loads or distinct proxy instances.

## Work classification and future timing contracts

These are cost classifications under the **current representation**, not proposals to change this RC.

| Current operation | Classification | Reason |
|---|---|---|
| `cells` representation and its materialization for a fully built index | `INTRINSIC_TO_CURRENT_INDEX`; `COULD_BE_DEFERRED_UNTIL_FIRST_USE` under a different lifecycle | The current proxy's scalar lookups require this table, although current code builds it for every cell before knowing access |
| Parent read-only openpyxl Parse A and full traversal | `INTRINSIC_TO_CURRENT_INDEX` **as implemented**; `REUSABLE_ACROSS_INVOCATIONS`; `COULD_BE_SCOPED_TO_ACCESSED_WORKBOOK` | It is the builder's current source of cell values; the resulting derived state is content-addressed by workbook hash but the public runner does not discover prior state |
| Every top-level `.xlsx` discovered and built | `COULD_BE_SCOPED_TO_ACCESSED_WORKBOOK`; `POTENTIALLY_REDUNDANT` | Admission is script-wide, while discovery ignores actual load paths; the RC study staged one workbook, so its measured 22 scripts do not quantify extra-workbook waste |
| Whole-file freshness hashes | `INTRINSIC_TO_CURRENT_INDEX` validity policy; `POTENTIALLY_REDUNDANT` for repeated reads of unchanged bytes; `REUSABLE_ACROSS_INVOCATIONS` only with a valid identity protocol | Multiple parent/child hashes protect separate boundaries; their current frequency is a lifecycle choice |
| `anchors`, `temporal`, `ia` index | `DEAD_PRODUCT_WORK` for this RC public Candidate-A read path | Product `reads.py` queries `cells`; no product query consumes anchor or temporal rows or `ia`. Archived *research* inspection helpers did use them. They remain paid in RC index build |
| `ic` index on `cells(sheet,row,col)` | `INTRINSIC_TO_CURRENT_INDEX` schema as implemented, but `POTENTIALLY_REDUNDANT` for current lookup shape | Product scalar query filters `sheet,addr`, so the index may help only by its `sheet` prefix; no query-plan measurement attributes benefit |
| SQLite backup to per-run file; manifest publication | `INTRINSIC_TO_CURRENT_INDEX` cross-process delivery as implemented; `REUSABLE_ACROSS_INVOCATIONS` in a different lifecycle | Child cannot attach the parent's in-memory DB; public path always makes a new run-local file |
| Child raw OOXML metadata parse | `INTRINSIC_TO_CURRENT_INDEX` proxy semantics as implemented; `REUSABLE_ACROSS_INVOCATIONS` or `COULD_BE_DEFERRED_UNTIL_FIRST_USE` conceptually | Sheet names, dimensions, merges and cell types are rebuilt per child; it is **not** normal openpyxl Parse B |
| Capture pre/post snapshots, delta/validation/replay | `POTENTIALLY_REDUNDANT` for verified read-only invocations, separate from index serving | Assurance defaults on. Post snapshot runs even with zero changed workbooks; delta/replay require a detected mutation. Their RC share is unmeasured |
| Diagnostic event, summary, capture and last-run persistence | `POTENTIALLY_REDUNDANT` to read serving, but current product observability work | Timed by external RC clock; unmeasured in isolation |

The engineering opportunity map is conceptual; none is ranked or implemented here.

| State design | Existing cost removed / cost remaining | First-read and repeated-read economics | Complexity, semantic risk, partial support |
|---|---|---|---|
| Current eager per-invocation full index | Removes normal reference parse on supported child load; retains full Parse A, all-cell/unused-table build, publication, attach and assurance on every invocation | First read waits for full build; repeated reads within same child can use attached state; no public cross-invocation gain | Known semantics and four RC failures; parent in-memory and child snapshot reuse already exist only within one run |
| Persistent eager by workbook hash | Removes repeated Parse A/traversal/SQLite build and backup **if** valid published DB is reused; retains validity checks, child attach/metadata, proxy and product wrapper | First invocation still pays full build; later invocations plausibly improve | Needs atomic cache publication, invalidation, schema/version identity, locking and fail-closed recovery; SHA and `substrate_identity` are partial primitives, public discovery absent |
| Lazy per-workbook | Removes build for unopened top-level workbooks; loaded workbook still pays its full build and publication | First read of a contacted workbook can worsen if build moves onto it; tasks that never load benefit | Needs safe coordination between child demand and parent builder, generation rules and fallback; existing manifest is eager and offers no request protocol |
| Lazy per-read | Avoids materializing unrequested sheets/cells and unused search tables; on-demand parsing/lookup remains | First targeted read could improve on large sparse workbooks, but repeated uncached reads may worsen; cache could improve repetition | Harder formula/type/merged/dimension semantics and mutation freshness; current proxy/query interface is a partial surface, current DB builder is fully eager |
| Direct OOXML representation | Could eliminate Parse A's openpyxl object construction; ZIP/XML decoding, typing, metadata, SQLite or other storage and publication remain | First read plausibly improves if parsing is selective; repeated-read gain depends on representation | High semantic risk for formulas, dates, shared strings, merged cells and package variants; `WorkbookMetadata` already parses limited OOXML but is not a full cell decoder |
| Reference-first adaptive | Avoids derived build on cheap/one-off reference work; normal openpyxl B cost remains until threshold; derived state pays only after repeated demand | First read uses reference latency; repeated demand may improve once build is amortized | Threshold policy, observation, replay and transparent handoff complicate semantics; existing predeclared fallback/spy telemetry is partial support. No threshold is selected here |

Future benchmark names must include the accounting boundary in the reported result:

| Regime | Timer rule |
|---|---|
| `MECHANISM / INDEX-READY` | Begin only after a valid immutable derived state has been built and published. Time backend acquisition/attach, freshness checks, metadata, target `load_workbook` and exactly specified reads, including any fallback parse. State creation is reported separately with hash and build time. State whether process/imports are inside; if excluded, call it operation trace, never product speed |
| `COLD PRODUCT` | External clock from public command launch to exit with no usable product state. Include CLI and child startup, classification, discovery, hashes, index build, publication, complete script, capture/validation/diagnostics and teardown. Stage identical input bytes before clock in both arms and declare that exclusion |
| `WARM PRODUCT` | External clock from public command launch to exit after a prior **public** invocation left valid reusable state and the next public invocation actually discovers/reuses it. Include validation/freshness, attach, complete script and all product work; record a reuse witness and fail the regime if rebuilt. A shared `XDG_CACHE_HOME` alone is insufficient |
| `AMORTIZED SESSION` | Clock begins before first public construction and ends after N real public invocations over an explicitly defined workbook generation and reuse horizon. Include first build plus every invocation's startup, validity checks, script, assurance and diagnostics; compare with N reference invocations under the same staging/OS-cache rules. Report N, mutations/invalidation and total, never infer N from an index-ready trace |

## Direct answers to the 20 questions

1. **Same underlying workloads?** Partly by task and workbook, not generally by script, trace or benchmark unit.
2. **Identical where?** Six hardened/RC task workbooks match, but only three have hardened timed contact; six earlier representative H0 scripts and their workbooks are exactly reused after normalization in RC eligible; the warm probe reuses one exact RC script/workbook.
3. **Different where?** Shadow synthetic access loops on two books; enriched 12-task H1 traces; uniformly sampled 30-task live checkpoint; control-defined 22 eligible scripts with one load each; distinct 30-script RC representative view.
4. **Did population explain the sign change?** It could alter magnitude and prevalence, but cannot by itself explain a change between an index-ready trace endpoint and complete cold product time. No paired same-script mechanism-vs-product decomposition proves a population-only effect.
5. **Did timer boundaries explain it?** Yes as an accounting explanation: historical 44.46% excludes build/process/capture; RC includes them. It is not proof of an exact causal share for each overhead.
6. **Did state lifetime explain it?** Yes: historical exact replay used prebuilt per-trace SQLite, and live checkpoints shared per task/slot; public RC rebuilds per invocation. The warm probe demonstrated no reuse.
7. **When charged historically?** Shadow P1 charges build once inside each timed repetition; shadow P2 excludes a prior build. Hardened live task accounting charges shared substrate in **both** arms per task plus refresh; 44.46% trace timer excludes a build performed once per trace. Representative per-load excludes initial/refresh build but task economics charges it separately.
8. **Historical build openpyxl?** Yes: the research `index.build_index` uses `openpyxl.load_workbook(..., read_only=True)`; RC frozen builder does too.
9. **How many current reference parses?** One Parse A read-only build per freshly indexed workbook per eligible invocation, plus zero or one normal B on each proxy that materializes reference; repeated proxy/fallback loads can create multiple B. In the selected 22 one-load scripts, 18 had A only and four had A+B in each scored repetition.
10. **Does setup repeat later execution work?** Yes for A+B cases: full workbook facts are decoded during Parse A and a normal workbook is materialized during B. All admitted cases also reread package metadata XML in child, though that is not normal B.
11. **Fundamental current-representation costs?** Cell-derived state, some validity check, a child-accessible state transfer and metadata needed for proxy semantics; exact full traversal, current hash frequency and unused search tables are implementation choices.
12. **Eager consequences?** Build of all top-level workbooks/all cells before contact, per-invocation rebuild, full backup/publication, metadata at first proxy acquisition, and default assurance snapshots.
13. **Amortizable?** Parsed cell state and published SQLite by workbook generation; potentially metadata and some validity work with an appropriate protocol. Current public RC does not do it.
14. **Delayable?** Workbook-specific build/attach until load; sheet/cell materialization until requested read; assurance work could be scoped to actual change if semantics permit. No measured benefit is claimed.
15. **Never consumed?** `anchors`, `temporal` and `ia` in the RC product read path; research inspection helper use is separate. The `ic` index's full benefit is unmeasured.
16. **Was ~44% valid?** Yes for the recorded exact-trace clock and 51 selected contacted traces, with 51/51 exact outcomes and 50/51 positive median trace differences. It was not whole-invocation savings.
17. **Was per-load saving valid?** Yes as descriptive timed H0 eligible-load versus H1 proxy-load distributions (median 0.410 vs 0.093 s), with initial substrate cost separate. The advertised ~0.32 s is a difference of medians across unpaired generated calls, not a same-script causal or end-to-end saving; mean-based 113.64 s avoided-parse credit is an estimate.
18. **Cold contradiction?** No. It measures a larger boundary and state charged at every invocation; it also found four semantic failures on its own selected scripts.
19. **Actual warm-RC speed?** None. The feasibility stop rule left `raw_timings.jsonl` empty after two public runs both rebuilt.
20. **Unresolved question?** For the same semantically supported script/workbook bytes, what is the complete public invocation effect once the product demonstrably reuses a valid published index, and at what real reuse horizon does construction plus N invocations beat N reference invocations? The RC cannot currently instantiate that condition, and the archived same-boundary measurements do not answer it.

## HISTORICAL TREATMENT

The strongest historical timing treatment was a proxy reading a **previously constructed** SQLite representation. Preparation was outside each exact trace timer and repeated once per trace before its six alternating backend runs. The research builder itself used openpyxl. Shadow P1 is the counterexample to a universal build-free claim: on the 2.17 MB Seafood workbook it charged roughly 4.5–4.8 s to build and did not break even through ten synthetic accesses; P2 excluded that build and improved access-only time.

## CURRENT RC TREATMENT

The public RC classifies, builds from openpyxl, backs up SQLite, launches an instrumented child, optionally materializes normal openpyxl, captures workbook state, and persists diagnostics on every admitted invocation. It does not discover a prior run's index.

## POPULATION OVERLAP

Workbook overlap is real: hardened contacted traces and RC eligible scripts share `Financial_Model:08_01`, `08_03`, and `Debugging:05_02` bytes. Exact script/trace overlap for those speed measurements is unproven; 48 recoverable H1 trace sources had no original-or-normalized hash match among RC eligible scripts. The earlier representative checkpoint supplied six exact H0 scripts to RC eligible, but its per-load comparison was between different H0/H1 generated calls.

## TIMER BOUNDARY RECONCILIATION

The 44.46% clock surrounds acquisition and trace operations with an index ready; the 0.32 s per-load estimate surrounds individual loads with a separately accounted substrate; the RC 2.017 ratio surrounds two whole fresh subprocess invocations. Comparing their percentages directly is a category error. The RC external clock includes process and product work absent from the historical exact trace clock.

## STATE LIFETIME RECONCILIATION

Historical exact replay prepared per trace and reused that state for repetitions; live checkpoints reused per task/slot. RC cold validation made a new cache, run dir and index per scored invocation. Even with a shared cache, its public second invocation rebuilt into a new UUID directory.

## DOUBLE-PARSE ANALYSIS

Parse A is the builder's read-only openpyxl parse. Parse B is lazy normal openpyxl materialization on proxy delegation or load fallback. Four of 22 eligible RC scripts have logged A+B in all scored repetitions; the other 18 have A only in those records. A rejected source ordinarily has B without A for its target workbook; repeated rich fallback/proxies can produce multiple B parses. The B event's isolated cost is unmeasured.

## CURRENT SETUP COST DECOMPOSITION

Eligible per-script median instrumented setup was 0.264 s (ensure 0.252, backup 0.014 as separate medians), versus median direct-Python whole invocation 0.313 s. CLI/classification, parsing versus inserts, startup, metadata, capture and diagnostics have no separate RC timers. Neither the residual nor the accelerated load event identifies gross same-script reference-read savings.

## EAGER WORK

The parent scans every top-level workbook and builds every cell, anchor and temporal row before the child loads anything. Anchor/temporal product consumption is absent; whole-file hashes, publication and snapshots repeat each invocation. These facts identify avoidable *work categories*, not a measured optimization gain.

## LAZY / REUSABLE OPPORTUNITIES

Persistent eager state, per-workbook or per-read construction, direct OOXML decoding and reference-first adaptation each move or remove different costs and introduce validity or semantic obligations. The opportunity map above records those mechanics without ranking them or setting a threshold.

## WHAT THE POSITIVE RESULT ACTUALLY MEANT

On exposure-enriched, exactly replayed traces, the already-derived Candidate-A mechanism avoided three normal reference parses per trace and reduced median load/read trace time by 44.46%; 51/51 trace outputs were exact. On the representative checkpoint, observed individual accelerated loads were cheaper than the distribution of H0 eligible reference loads, with separately charged substrate cost. Neither established packaged per-invocation speed.

## WHAT THE NEGATIVE RESULT ACTUALLY MEANT

For 22 preregistered, control-defined eligible scripts, the unchanged packaged RC with a fresh index each invocation was slower than direct Python on all 22; median paired ratio 2.017. Four scripts also had genuine semantic differences. This is a valid cold product result for that population and identity, not a measurement of a reusable-index product mode.

## DO THE RESULTS CONTRADICT?

No. A positive already-derived mechanism effect and negative first-invocation product effect can coexist. Shared workbook identities limit a pure population story; different timer boundaries and index lifetimes are directly established. The archives do not identify the exact share of the RC penalty due to each uninstrumented component or prove a same-script indexed serving speedup for the RC.

## REMAINING PERFORMANCE QUESTION

Can a public, semantically correct invocation genuinely reuse valid derived state and deliver a net speed benefit on a fixed, treatment-blind set of identical script/workbook pairs, after charging the first build over a declared number of real invocations? No warm-RC speed measurement currently answers that question.
