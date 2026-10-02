# Read Engine Phase 5 — one-interpreter architecture falsification

**Status:** offline architecture experiment; no public RC/product, decoder, artifact, classifier, proxy, fallback, presentation or frozen Phase-1–4 file changed. No model calls. [Preregistration](../../read_engine_phase5/PREREGISTERED_SPEC.md) SHA-256 `b3ccd771d1125ebd73ea070ba77c8f8df03c1b914550c96f432248362cea0d08` was written and hashed before H1 implementation or timing; [implementation identities](../../read_engine_phase5/implementation_identity.json) were pinned before the process fixtures. Source HEAD and committed tree were `254a5c14fa74fc3534493c565de84b38e7317175` and `dc7ae5512e4d47e56663564ad72b7a18600bbf5c`; the working tree was already dirty, so exact file hashes, not cleanliness, define authority.

Evidence: [process fixtures](../../read_engine_phase5/process_semantics.jsonl), [correctness/invalidation](../../read_engine_phase5/raw_correctness.jsonl), [command timings](../private-data-manifest.json), [observed sessions](../../read_engine_phase5/session_timings.jsonl), [profile](../../read_engine_phase5/profile.json), and [paired analysis](../../read_engine_phase5/analysis.json). The [one-interpreter harness](../../read_engine_phase5/harness.py) and [runner](../../read_engine_phase5/benchmark.py) remain experimental. The direct-Python and frozen Phase-4 H1 arms were rerun **in the same Phase-5 run** as PY and H0. Archived Phase-4 ratios are context, not the causal control.

**Protocol disclosure:** The preregistered pre-scoring process suite covered 15 fixtures, including the critical atexit workbook write, `import __main__` from atexit, `os._exit`, and fatal signal. Explicit SIGINT and an extra inherited file descriptor were inadvertently omitted from that pre-scored driver. They were run as **two labeled post-scored, unscored diagnostics**, without treatment-code changes. This does not retroactively satisfy their pre-scoring order. The fixed-script timing remains a measured normal-exit architecture comparison; the process-assurance failures already preclude product integration. No scored row was selected or rerun in response.

## PHASE 4 BASELINE

The same exact 22 eligible scripts/workbooks produced old RC cold `2.017×`, Phase-3 cold `1.595×` and warm `1.230×`, then Phase-4 H1 cold `1.589×` and warm `0.833×` versus direct Python. Phase-4 warm H1/H0 was `0.704×`, 22/22 faster; its 13/22 warm wins and bootstrap upper bound above one left aggregate speed formally unsupported. Three tiny Templates had control ~93–101 ms, child ~95–97 ms and full Phase-4 treatment ~154–158 ms. Phase 5 changed none of that archived evidence.

## ONE-INTERPRETER ARCHITECTURE

PY ran `<RC Python> workload.py`. H0 ran the **frozen** Phase-4 parent, which launched a fresh child with `sitecustomize`. H1 ran one fresh Python interpreter: the Phase-4 parent preflight/classifier, whole-file SHA, artifact integrity/build, and pre-snapshot ran there; it installed the **frozen** Phase-3 `Runtime` directly, set script argv/cwd/path, and executed the byte-identical source via `runpy.run_path(..., run_name="__main__")`. Its post-snapshot, mechanical capture/validation, and diagnostic writes ran in an exit hook registered before the script could register its own hooks. There was no second target-script Python process, daemon, new artifact, new parser, changed merged-cell behavior, or new serving API. The source still said `import openpyxl` and `openpyxl.load_workbook(...)`.

H1 kept the Phase-4 artifact integrity gate and the frozen runtime's **second** source SHA at first served load, although the original parent→child race no longer exists. It fully ran `safe_artifact.load()` in that same process before `direct_served_load`. Thus this experiment does not take credit for removing freshness or semantic validation work. It removes the extra interpreter/handoff and changes ownership of already-required work. The absence of `sitecustomize` startup is part of that process-shape change; runtime/proxy behavior is the same frozen code.

## PROCESS SEMANTICS GATE

Fifteen pre-scored cases produced eight automatic `EXACT`, four `OBSERVABLE_DIFFERENCE_BUT_PRODUCT_ACCEPTABLE`, and three `PRODUCT-CONTRACT_VIOLATION` labels. The raw automatic labels are observations, not final contract adjudication. Strict review upgrades module metadata, parent module-cache visibility, and uncaught-exception traceback differences to **contract concerns**: ordinary Python can inspect or rely on them. The two supplemental post-scored cases are marked in the ledger and cannot repair the gate chronology.

| Fixture group | PY/H1 result | Product judgment |
|---|---|---|
| normal return, `SystemExit(0)`, `SystemExit(7)`, stdout/stderr bytes, local/repeated import, `try/finally`/file close, subprocess, caught SIGUSR1 | Core observed result/exit generally exact; local imports and subprocess output work | Acceptable for the tested behavior; module-cache details below differ. |
| script metadata and `__main__` at script execution | `__name__="__main__"`, script path, argv and `sys.path[0]` match after path normalization; H1 `__package__=""` and loader `NoneType`, whereas PY/H0 have `None` and `SourceFileLoader` | Observable Python semantic difference, not certified exact. |
| `atexit` workbook save | H1/PY/H0 write the same A1 value; H1 and H0 each record one post-run capture | Required ordering gate **passed**. |
| atexit hook importing `__main__` | PY/H0 print `main-marker=script-main`; H1 prints `main-marker=None` | **Product-contract violation.** `runpy` restores launcher `__main__` before process exit. |
| `os._exit(7)`; fatal SIGTERM after workbook write | H0 still writes summary and one capture record. H1 writes neither; workbook mutation happened | **Assurance violation.** An in-process hook cannot observe a terminated interpreter. |
| uncaught exception | Exit code 1 and error class match; H1 stderr includes launcher/`runpy` frames absent from PY/H0 | Observable error/traceback fidelity loss. |
| explicit SIGINT and extra inherited FD (**post-scored diagnostics**) | H1 matches PY's SIGINT exit `-2`; H0 wraps it to `254` yet records capture. H1 and PY inherit/read the extra FD; H0 child closes it. | These reveal process-shape differences; timing-order protocol gap remains disclosed. |

The normal-exit fixed 22 were not affected by the demonstrated atexit-`__main__` behavior, so their timing answers a narrower causal question. They cannot establish a generally equivalent Python process contract.

## ARGV PATH MAIN AND IMPORT SEMANTICS

The execution fixture verified script `__name__`, `__file__`, `__spec__`, argv, cwd, and `sys.path[0]`; local and repeated imports worked. H1's `__package__` and `__loader__` differ. While the script executes, `import __main__` points at its temporary runpy module, but after it returns Python restores the launcher's module; a later script atexit hook therefore observes the wrong main module. H1 also exposes already imported parent config/capture modules in `sys.modules`; H0's child does not. Full `sys.path` and runtime-specific environment differ between arms, though PY/H0 themselves differ because H0 injects bootstrap context. These are process-visible facts, not evidence of changed narrow read values.

## STDOUT STDERR AND EXIT SEMANTICS

Normal/flush output, `sys.exit(0)`, and `sys.exit(7)` fixture bytes and exit codes matched PY. The fixed 22 scored scripts also had exact stdout/stderr bytes and exit codes in every triplet. H1 sends output directly through inherited streams rather than H0's captured/re-forwarded child streams. This did not change tested bytes, but concurrent observation/flush ordering beyond the fixture is unmeasured. Uncaught exceptions add launcher frames to H1 traceback. For fatal SIGTERM, H1/PY exit `-15`; H0's Python launcher returns the child code through `sys.exit(-15)`, externally observed as `254`. That is a pre-existing H0 exit-code imperfection, while H0 preserves effect observation.

## ATEXIT SEMANTICS

The H1 post-capture callback is registered before the frozen runtime's finish callback and before user code. Python's LIFO exit order then runs user callbacks, runtime telemetry/cleanup, and finally H1 capture/validation/summary. The workbook-write fixture confirmed the intended ordering on ordinary shutdown: the changed cell was present and one capture record persisted. This solves **effect timing for that fixture**, not full `atexit` equivalence. A user hook importing `__main__` sees the launcher, and a hook calling `os._exit` can prevent H1's capture entirely. Manually flushing private atexit internals was neither attempted nor treated as safe.

## ABNORMAL TERMINATION

The dedicated fixtures changed an XLSX and then terminated by `os._exit(7)` or SIGTERM. H0's parent survived, observed the changed package, and wrote capture/summary; H1's entire process died and had **no** post-run capture or diagnostic witness. For the fatal-signal fixture, H0's external signal code is imperfect as noted above, but its external observer still runs. A crash in a native extension or fatal interpreter error has the same H1 structural problem: Python callbacks cannot run after the only process is gone. No in-process rearrangement can guarantee external observation of such a death. A separate observer or a weakened assurance contract would be required; neither is part of H1. **PROCESS/ASSURANCE SEMANTICS: UNACCEPTABLE.**

## FRESHNESS AND ARTIFACT TRUST

H1 kept the same source SHA, artifact key/version bindings, Phase-4 sidecar/header/whole-artifact integrity gate, and frozen full semantic payload decode. The runtime still hashes the source again at first direct load, matching H0 code; future removal of that duplicate check would be a separate trust experiment. H1 only finalizes `REUSED` when a matching `direct_served_load` follows successful semantic decode. A schema-invalid but integrity-consistent artifact fell back through `runtime_failure` and was marked `REUSE_REJECTED`, never successfully reused.

The two frozen source generations passed **24/24** missing/truncated/modified/version/source-change/restoration cases and **2/2** semantic-payload rejection checks. Thus the observed one-process speed did not come from omitted source hashing, integrity checks, corruption rejection, or stale serving.

## CORRECTNESS ON THE FIXED 22

Every one of the 22 source script, source workbook and staged workbook hashes matched the frozen population. There were **374/374 exact** PY/H0/H1 triplets: 44 unscored cold/warm gate triplets plus 330 scored triplets (22 × 3 repetitions × 5 invocations). All 22 contacted direct serving. All **264/264 scored warm H1 invocations** had a semantic-load-backed `REUSED` witness; the same gate held for H0. The four fallback scripts retained one `proxy_operation_escape` route per invocation, with equal H0/H1 count/reason. No output package, exit, stdout or stderr difference occurred on the scored primary scripts. These exactness results cover the fixed scripts, not all arbitrary Python process observations.

The runner's inherited raw field name `child_confirmed` means an H1 `direct_served_load` event following in-process full validation; H1 has no child process. The field name was not used as evidence of a hidden second interpreter.

## COLD RESULT

The timer is the complete external command launch→exit, with symmetric staging outside it. Same-run paired statistics over the 22 fixed scripts:

| Cold comparison | Median ratio | Geometric mean | 95% script-bootstrap median interval | Faster/slower | Range |
|---|---:|---:|---:|---:|---:|
| H0/PY | 1.563 | 1.656 | 1.431–2.014 | 0/22 | 1.057–2.482 |
| H1/H0 | **0.811** | 0.759 | 0.661–0.896 | **22/0** | 0.510–0.968 |
| H1/PY | **1.244** | 1.258 | 1.140–1.440 | 6/16 | 0.858–2.396 |

The one-process shape causally improved cold wall against H0, but cold remains slower than direct Python on the fixed aggregate. H0's same-run `1.563` differs from archived Phase-4 `1.589`; the causal comparison is H1/H0 here.

## WARM RESULT

Warm means each fresh command finds a previously built valid artifact and semantically reopens it; all warm witnesses passed. Same external clock:

| Warm comparison | Median ratio | Geometric mean | 95% script-bootstrap median interval | Faster/slower | Range |
|---|---:|---:|---:|---:|---:|
| H0/PY | 0.871 | 0.705 | 0.427–1.183 | 13/9 | 0.219–1.589 |
| H1/H0 | **0.793** | 0.804 | 0.742–0.831 | **22/0** | 0.707–0.998 |
| H1/PY | **0.633** | 0.567 | 0.343–0.970 | 15/7 | 0.164–1.270 |

The fixed **normal-exit timing rule** (median <1, majority faster, bootstrap upper <1) passes H1/PY for these 22 contact-selected scripts. This is an offline one-process *timing result*, **not an earned warm-product speed claim**: process/assurance semantics fail, and the two supplemental fixtures missed pre-scoring order. The 22 scripts represent only 14 tasks; script resampling does not imply a broad workbook population.

As a clustering sensitivity check, equal-task-weighted warm ratios gave median **0.641** across 14 tasks with a task bootstrap interval **0.413–0.956**. This remains conditional on the same fixed eligible tasks and does not cure the process-contract failure or make them representative of ordinary product use.

## SESSION RESULT

Observed sessions start cold and then genuinely reuse the artifact; all startup, hashing, capture, fallback and diagnostics remain charged. Each ratio is against N independent full PY commands.

| N | H1/H0 median | H1/PY median | H1/PY bootstrap interval | H1/PY faster/slower |
|---:|---:|---:|---:|---:|
| 1 | 0.811 | 1.244 | 1.140–1.440 | 6/16 |
| 2 | 0.818 | 0.909 | 0.760–1.138 | 13/9 |
| 3 | 0.813 | 0.721 | 0.699–1.096 | 14/8 |
| 5 | 0.806 | 0.687 | 0.556–1.076 | 14/8 |

None of N=1,2,3,5 meets the fixed median-upper-bound-below-one session standard. The apparent N=5 advantage is not a supported product/session claim.

## H1 VS H0 ARCHITECTURE EFFECT

H1 beat same-run H0 on **22/22 cold and 22/22 warm** workload medians. Median per-workload wall saved was **96.6 ms cold** and **41.5 ms warm** (warm range **6.6–63.5 ms**); warm paired ratio `0.793` satisfies the preregistered materiality rule. This causal result is narrower than “one interpreter is a valid product”: H1 and H0 use the same scripts, decoder, artifact, whole-script admission, normal fallback, capture function and complete external timer, but they differ in process semantics and exit behavior. The improvement is not attributable to an omitted product capture or freshness step; their code paths and gate records show those steps ran. Component medians are nested and do not sum to the full-command median.

All **nine archived Phase-4 warm losers** remained in the fixed population. Their Phase-5 same-run outcomes were:

| Archived Phase-4 loser | H1/H0 warm | H1/PY warm | Phase-5 classification |
|---|---:|---:|---|
| Debugging_01_06__26b457c478d0 | 0.714 | 0.898 | `FIXED_BY_PROCESS_MODEL` |
| Debugging_01_06__7b42a0f86b41 | 0.778 | 1.199 | `STILL_FALLBACK_BOUND` |
| Debugging_05_02__9e6b464d2158 | 0.939 | 1.041 | `STILL_FALLBACK_BOUND` |
| Financial_Model_08_03__59b98508fd79 | 0.998 | 1.270 | `STILL_FALLBACK_BOUND` |
| Financial_Model_15_03__472e28fbd6e0 | 0.896 | 1.215 | `STILL_FALLBACK_BOUND` |
| Financial_Model_18_05__39d21da726e7 | 0.751 | 0.784 | `FIXED_BY_PROCESS_MODEL` |
| Template_03_03__c76ea596b408 | 0.716 | 1.137 | `STILL_FIXED_OVERHEAD_BOUND` |
| Template_06_12__17725eca76da | 0.707 | 1.111 | `STILL_FIXED_OVERHEAD_BOUND` |
| Template_16_07__9662584ede5e | 0.708 | 1.123 | `STILL_FIXED_OVERHEAD_BOUND` |

These are timing classifications for the fixed scripts, not proof of a generally valid H1 process contract. No new read-engine bottleneck was isolated by the one-change experiment.

## SHORT SCRIPT RESULT

The three Template scripts were the clearest fixed-overhead discriminator. Warm numbers below are per-workload medians from the same Phase-5 run; internal components are separate medians and need not sum.

| Template | PY command ms | H0 child / full command ms | H1 runtime install / script / full command ms | H1/PY |
|---|---:|---:|---:|---:|
| 03_03 | 87.6 | 86.3 / 139.2 | 44.3 / 1.1 / 99.6 | 1.137 |
| 06_12 | 89.2 | 88.7 / 140.1 | 44.0 / 2.1 / 99.1 | 1.111 |
| 16_07 | 88.4 | 86.8 / 140.4 | 43.7 / 1.4 / 99.4 | 1.123 |

H1 removed roughly **40–41 ms** of each Template's full-command wall versus H0, yet they still lose **~10–12 ms** to PY. The H0 child was already approximately PY; H1 moved real openpyxl/runtime imports into the same interpreter before the script, leaving the script-body timer tiny. A 1 ms H1 script-body timer must **not** be compared with an 88 ms PY whole process as if the import vanished.

## FALLBACK WORKLOAD RESULT

The three covered-merged-cell escapes and one workbook-iteration escape were intentionally unchanged. Same-run H1 warm median ratios to PY:

| Workload | H1/PY | H1 reference parse median ms | H1 artifact load median ms | Result |
|---|---:|---:|---:|---|
| Debugging_01_06__7b42a0f86b41 | 1.199 | 43 | 17 | Still fallback-bound. |
| Debugging_05_02__9e6b464d2158 | 1.041 | 470 | 13 | Still fallback-bound, near parity. |
| Financial_Model_08_03__59b98508fd79 | 1.270 | 1,948 | 612 | Still double-work/fallback-bound; H1/H0 ~0.998. |
| Financial_Model_15_03__472e28fbd6e0 | 1.215 | 193 | 57 | Workbook iteration remains reference-only. |

No speed result for these four may be credited to changed merge/iteration semantics. The large merged case shows why process removal alone cannot solve every loss: the full artifact decode and full normal parse both remain.

## WHERE THE WRAPPER COST WENT

On the three Templates, H0 external wall minus child wall is about **52–54 ms**. H1 eliminated the child process but retained two real cost groups: roughly **44 ms** warm runtime/import installation inside its process, and about **52 ms** external-minus-internal-run residual containing interpreter entry, CLI/top-level and RC imports, shutdown, and external reaping. H1's script body is ~1–2 ms; other internal setup/post work is ~2 ms. PY's ~88–89 ms includes its own interpreter and real openpyxl import. Thus the **extra process/handoff cost is real**, but not all H0 wrapper milliseconds disappear: necessary work relocates, and H1 still has an ~10 ms short-script deficit. The external residual's startup/shutdown split is unmeasured.

Across all 22 warm rows, H0 median child wall was **154.7 ms**, H1 median script-body **61.9 ms** plus runtime install **44.3 ms**; H0 external-minus-parent residual **46.2 ms**, H1 **54.1 ms**. These are cross-workload component medians, **not additive** and not a claim of 93 ms saved per workload. H1 still performs source SHA, artifact integrity, pre/post snapshots, and diagnostics. H0 post-capture median was 4.8 ms versus H1 0.2 ms in this run despite calling the same capture function; cache/scheduling/placement may contribute, so that difference is not assigned causally to omitted capture. The more robust attribution is the same-run full-command H1/H0 contrast.

The diagnostic Phase-4 child-wall/PY idealized median `0.545` was a zero-cost lower bound, not a forecast. Actual H1/PY warm was `0.633`: required setup/import/capture/exit work remained inside the one interpreter.

## NORMAL EXIT PERFORMANCE VERDICT

**MATERIALLY FASTER than H0** on the same complete command boundary and same exact 22 scripts: warm `0.793×`, cold `0.811×`, both 22/22 faster. H1/PY fixed normal-exit warm timing rule numerically passed at `0.633×`, 15/22 faster, script-bootstrap upper `0.970`. Cold H1/PY remained negative at `1.244×`; sessions N≤5 did not meet the fixed interval rule. Same-run H0/PY warm `0.871` differs from archived Phase-4 `0.833`, so archived-to-new ratio differences are not the causal effect. This performance verdict is explicitly **conditional on normal-exit fixed-workload semantics**.

## PROCESS ASSURANCE VERDICT

**UNACCEPTABLE for the current execution/effect-observation contract.** H1 correctly captured the tested normal atexit workbook write, but `runpy` changed exit-hook `__main__` identity, module metadata/cache and exception traceback; more decisively, `os._exit` and fatal signal prevented all H1 post-run capture/diagnostics after a real workbook mutation. H0's surviving parent performed that observation. The post-scored SIGINT/FD supplements show additional process differences but do not remove the pre-gate chronology gap. No fixed-22 speed advantage can waive these semantic failures.

## ONE INTERPRETER DECISION

**B — FAST + SEMANTICALLY UNACCEPTABLE.**

`PROCESS_OVERHEAD_CONFIRMED_BUT_PARENT/SUPERVISOR_REQUIRED`

The pure one-interpreter H1 is **not** an integration candidate. The result does establish that the current *heavy Python* parent+child shape costs meaningful wall time on the full boundary. It does **not** establish that any observer is unnecessary: an external process or changed assurance contract is required to observe abrupt termination. The user-facing ordinary Python/openpyxl interface and earned narrow read semantics remain intact only for the fixed normal scripts measured here.

## NEXT ARCHITECTURAL STEP

Design, then preregister a separate **thin external observer plus one script interpreter** or a session-amortized supervisor comparison. It must retain crash/abrupt-exit capture and the fixed artifact/freshness/fallback contract while measuring its own startup, IPC, post-run validation and failure recovery on the same 22 full commands. Before that timing, resolve Python script metadata/`__main__` and exception-traceback fidelity in whichever process actually executes the script. Do not merge H1 into the public RC, remove capture, change the artifact/decoder, or claim public warm speed from this branch. A separate merged-cell fallback experiment remains worthwhile for the four scripts that process ownership did not fix.
