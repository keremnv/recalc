# Read Engine Phase 4 — warm-parent lifecycle optimization

**Status:** completed offline causal experiment; no public product or frozen Phase-1/2/3 change. The effective preregistration is [v1](read_engine_phase4/PREREGISTERED_SPEC.md) SHA-256 `0162f197c89c37ee63bafb5cfbbbc65f3e030eb830bd945ddffa042c560019ea` plus [amendment 1](read_engine_phase4/PREREGISTERED_SPEC_AMENDMENT_1.md) SHA-256 `81d5eecda220de9d6ba20f4f241a26c1b16910eba595c3cdc9db42ab30306239`. The amendment corrected a copied hash literal for the frozen eligible-population file before any probe or benchmark; it did not change identities, protocol or treatment. [Implementation identities](read_engine_phase4/implementation_identity.json) were pinned before execution. H0 is the frozen Phase-3 harness; H1 is the isolated Phase-4 parent; PY is direct Python/openpyxl. The parent/child process model, frozen child and bootstrap, safe artifact format, direct decoder, classifier, proxy/fallback, source hashing, capture, diagnostics and ordinary script interface were unchanged.

Primary evidence: [raw correctness](read_engine_phase4/raw_correctness.jsonl), [raw command timings](read_engine_phase4/raw_timings.jsonl), [observed sessions](read_engine_phase4/session_timings.jsonl), [profile](read_engine_phase4/profile.json), [import diagnostics](read_engine_phase4/import_diagnostics.json), and [paired analysis](read_engine_phase4/analysis.json). All ratios below are paired at the **same full-command external timer**; lower than one is faster. There were three scored repetitions and five actual invocations per arm/repetition on each of the same 22 scripts, with separate H0/H1 artifact roots and deterministic balanced arm rotation. Workload statistics use Phase-3's median-within-repetition warm rule. Bootstrap intervals use 2,000 resamples of the 22 script ratios, conditional on these fixed scripts; they are not broad task-population confidence intervals. The 22 scripts represent 14 tasks. OS page cache and CPU frequency were uncontrolled, so same-run H0/H1 is the causal comparison; archived Phase-3 medians are historical context.

## FROZEN PHASE 3 BASELINE

The old public RC cold median on these exact identities was **2.017**. Frozen Phase 3 measured cold **1.595**, warm **1.230** with 9/22 faster, and observed N=5 session **1.307**. All primary scored pairs were exact, all 22 contacted direct serving, and every warm invocation had a valid `REUSED` witness. These ledgers and implementations were not modified or rerun as archived Phase-3 evidence. A new same-run H0 arm used their exact frozen code; it measured cold H0/PY **1.610** and warm H0/PY **1.180** in this run. The difference from archived 1.595/1.230 is run-environment variation, not an optimization effect. In particular, several direct-Python control scripts ran substantially faster than in the historical run; comparing H1 only to archived medians would misattribute that variation.

## PHASE 4 TREATMENT

H1 changes the **warm parent validation/import ownership** only. The new [parent integrity gate](read_engine_phase4/parent_artifact.py) verifies source SHA-derived key, sidecar identity and fields, artifact existence/size, `LCRE3JZ1` magic, header source/decoder/contract/format identities, compressed length, sidecar artifact hash and envelope checksum. It does not decompress payload, parse semantic JSON, walk sheet/cell schema, convert values or create a `MemoryBook` on successful warm discovery. If absent or invalid, it lazily imports the **unchanged** Phase-3 builder and uses its existing direct decode/serialization/atomic publication. The [H1 harness](read_engine_phase4/harness.py) uses the frozen Phase-3 child/runtime/bootstrap. H0 retains full warm-parent `safe_artifact.validate()` and its discarded `MemoryBook`.

H1 finalizes `REUSED` only after the child emits `direct_served_load` following its complete safe artifact decode. If the child rejects semantic state, H1 records `REUSE_REJECTED` and the unchanged runtime uses normal reference openpyxl. This changes witness truthfulness, not the fallback decision. Cold H1/H0 artifact bytes were SHA-256 identical in **66/66** paired scored builds; no format/schema change occurred.

## PARENT TRUST BOUNDARY

The H1 parent remains a **publication/integrity gate**, not a semantic gate. It does whole-file source SHA on every invocation, verifies the sidecar and whole artifact bytes, checks envelope identity and lengths, and sends the artifact path/hash to a fresh child. The child rehashes the source, rechecks artifact envelope and payload integrity, decompresses, parses typed JSON, validates every record and constructs the serving `MemoryBook` before emitting `direct_served_load`. Thus parent acceptance is only a reuse candidate. H1's summary marks a child failure `REUSE_REJECTED` rather than successful `REUSED`.

This separation preserves fail-closed serving but has an important limit: the parent no longer proves semantic payload validity *before* child launch. A syntactically integrity-consistent artifact with invalid semantic JSON is accepted as a candidate; the child rejects it and falls back to reference, with no direct state served. This is the specified trust boundary, not a hidden weakening of the child gate. Source change between parent and child is still detected by the unchanged child source recheck. The complete `JSONZ_MEMORY_V1` format and atomic cold publication remain frozen.

## LAZY IMPORT BOUNDARY

The Phase-3 parent imported `safe_artifact` at module load; that imported Phase-1 `prototype`, `lxml` and openpyxl helper/package modules before it knew whether a build was needed. It also explicitly imported openpyxl in `run()`. H1's warm parent imports only the light integrity module; the construction stack is imported through `importlib` only on build/rebuild. The child import path was not edited. Across **264/264** scored H1 warm invocations, the parent reported `builder_stack_imported=false`, no `prototype`/`lxml`/`openpyxl` in `sys.modules` at successful reuse, and zero parent `MemoryBook` construction. H1 cold builds did import the frozen builder as required.

## CORRECTNESS AND INVALIDATION

There were **374 exact script triplets**: 44 unscored gate triplets (22 cold, 22 warm) and 330 scored triplets (22 × 3 repetitions × 5 invocations). Every triplet had exact PY/H0, PY/H1 and H0/H1 exit, stdout/stderr and post-run file/package state under Phase-3 comparison rules. There were no volatile-only or genuine semantic differences. All primary scripts contacted direct serving in both harness arms; all **264/264** scored H1 warm commands were child-confirmed `REUSED`. H0/H1 fallback count and route matched on every triplet; the four fixed fallback scripts still produced only `proxy_operation_escape`.

The corruption/freshness gate used the preregistered first two distinct primary workbook hashes: **24/24** invalidation sequence cases and **2/2** explicit child-semantic-rejection checks passed. For each source it covered missing state, valid reuse, removed state, truncation, modified bytes, format/decoder/contract mismatch, integrity-consistent but schema-invalid payload, same-path changed bytes, and restored original bytes. The schema-invalid candidate was rejected by the child, served by reference (`runtime_failure`), and marked `REUSE_REJECTED`; no false successful reuse was emitted. The changed source built a new identity, and restoration rediscovered the original artifact. These probes are correctness evidence, not scored speed rows.

## WORK REMOVED

At the same-run warm boundary, H0 parent artifact discovery/full validation was **32.27 ms** median across per-workload medians; H1 integrity-only discovery was **0.18 ms**. H1's measured warm artifact read/hash/header checks were approximately **0.01/0.07/0.08 ms** at the same aggregate level; larger artifacts cost more. H0's full parent semantic decode of cells was removed from warm reuse, while child artifact load stayed **31.40 ms H0 vs 31.13 ms H1**. The former is a measured component reduction, not automatically the whole-command saving. H1 also removed the warm parent builder import stack. Source SHA, capture, process count, child semantic decode and fallback all remained charged.

On cold builds the same frozen builder/serializer was invoked after lazy import; median direct decode was **195.4 ms H0 vs 202.5 ms H1**, serialization **33.7 vs 35.0 ms**, and publication **11.1 vs 11.0 ms**. These small differences are run/order variation, not intended construction optimization. H1 paid **49.5 ms** median lazy builder import inside its cold run, while H0 had imported that stack before `run()`'s timer. External cold clocks, rather than these nested clocks, decide regression.

## IMPORT EFFECT

Diagnostic fresh-interpreter probes (15 per case; OS cache uncontrolled) measured external process medians: bare Python **9.7 ms**, frozen H0 parent `--help` **96.7 ms**, H1 metadata-only parent `--help` **28.4 ms**, and H1 with cold builder imports **89.2 ms**. A warm H1 module-presence probe found `prototype=false`, `lxml=false`, `openpyxl=false`. These probes explain the intended import boundary but are not workload speed estimates.

In scored warm commands, external wall minus the internal `parent_total` clock fell from **111.2 ms H0** to **52.1 ms H1** as a median of per-workload medians. That residual contains interpreter startup, module and RC imports before `run()`'s timer, argument handling, final profile write, shutdown and external reaping; it is **not** pure import time. H1 measured `module_import_to_run` **16.9 ms** and RC imports **15.7 ms** inside its new instrumentation; H0 did not split these, so the diagnostic probes are the comparison for import content. Child bootstrap stayed **69.6 ms H0 vs 68.6 ms H1**, and child wall **172.0 vs 172.5 ms**. The combined warm-parent effect is causally measured; its precise split between imports and semantic materialization is not.

## COLD RESULT

Same-run H1/H0 cold paired median was **1.007**, geometric mean **1.008**, bootstrap median interval **0.997–1.019**, range **0.892–1.119**, with **9/22 faster**. H1/PY cold median was **1.589**, geometric mean **1.688**, interval **1.473–2.107**, range **1.061–2.504**, with **0/22 faster**. H0/PY cold median was **1.610**. H1 did not materially improve or destroy cold economics; some per-workload cold fluctuation was larger than the small aggregate difference. `COLD PRODUCT-SHAPED SPEED: NOT SUPPORTED`.

The following table preserves paired per-workload cold medians in milliseconds. `PY` is direct Python; `H1/H0` is the direct optimization comparison.

| Workload | PY cold ms | H0 cold ms | H1 cold ms | H1/H0 cold |
|---|---:|---:|---:|---:|
| Financial_Model_15_03__103457370cae | 344.9 | 587.7 | 598.9 | 1.019 |
| Financial_Model_08_03__59b98508fd79 | 2789.0 | 6662.5 | 6786.7 | 1.019 |
| Financial_Model_08_03__751f6966e68d | 2629.0 | 4218.7 | 4211.7 | 0.998 |
| Financial_Model_08_01__2ea507d758dc | 2664.3 | 4140.5 | 4117.3 | 0.994 |
| Debugging_01_06__7b42a0f86b41 | 153.3 | 409.2 | 364.9 | 0.892 |
| Financial_Model_08_01__8021d8d90c40 | 2681.9 | 4329.6 | 4224.0 | 0.976 |
| Financial_Model_15_03__472e28fbd6e0 | 343.2 | 801.2 | 816.9 | 1.020 |
| Financial_Model_02_04__5ac07a9edb67 | 268.1 | 394.7 | 392.8 | 0.995 |
| Financial_Model_18_05__39d21da726e7 | 166.2 | 310.1 | 313.7 | 1.011 |
| Financial_Model_07_01__23c57fc578fc | 968.7 | 1259.6 | 1308.3 | 1.039 |
| Financial_Model_02_01__4dbc773c2ade | 187.1 | 269.9 | 276.8 | 1.025 |
| Financial_Model_11_02__a443eee257b4 | 585.1 | 599.0 | 620.9 | 1.037 |
| Financial_Model_11_02__6a75b927c3f6 | 565.3 | 634.2 | 632.9 | 0.998 |
| Template_03_03__c76ea596b408 | 93.5 | 212.2 | 208.0 | 0.981 |
| Financial_Model_02_01__e87a34eb884e | 191.8 | 271.4 | 268.3 | 0.989 |
| Financial_Model_07_01__90a7533589a4 | 1026.1 | 1273.8 | 1277.0 | 1.003 |
| Debugging_08_04__2dde74bd671e | 367.6 | 500.3 | 559.9 | 1.119 |
| Debugging_01_06__26b457c478d0 | 144.8 | 303.3 | 305.1 | 1.006 |
| Template_06_12__17725eca76da | 98.8 | 224.7 | 231.6 | 1.031 |
| Debugging_05_02__31823ebc55b0 | 982.5 | 1100.0 | 1108.9 | 1.008 |
| Debugging_05_02__9e6b464d2158 | 720.5 | 1443.1 | 1439.5 | 0.997 |
| Template_16_07__9662584ede5e | 90.8 | 217.7 | 227.4 | 1.044 |

## WARM RESULT

Same-run H1/H0 warm paired median was **0.704**, geometric mean **0.683**, bootstrap median interval **0.655–0.725**, range **0.512–0.908**; **22/22** workloads were faster under H1. H1/PY warm median was **0.833**, geometric mean **0.705**, interval **0.437–1.205**, range **0.231–1.666**, with **13 faster, 9 slower**. Same-run H0/PY warm median was **1.180**, with 10 faster/12 slower. The observed median direction crossed one, but the fixed Phase-3 decision rule also requires a bootstrap median upper bound below one; H1's upper bound was 1.205. Therefore the observed favorable median is **not** an aggregate warm-speed support verdict.

Per-workload warm medians and required artifact/fallback diagnostics follow. Times and validation values are milliseconds; artifact size is KiB. `M` means H1 warm parent constructed a `MemoryBook` (all rows `no`); every cold artifact was `BUILT`, every scored warm artifact was child-confirmed `REUSED` in both H0 and H1. `Fallback` counts across 12 scored warm H1 invocations per workload.

| Workload | PY warm ms | H0 warm ms | H1 warm ms | H1/H0 | H1/PY | Fallback | Artifact KiB | Parent validation H0→H1 ms | M |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Financial_Model_15_03__103457370cae | 342.0 | 337.0 | 227.3 | 0.675 | 0.665 | no | 114.2 | 66.0→0.3 | no |
| Financial_Model_08_03__59b98508fd79 | 2636.3 | 4119.9 | 3378.0 | 0.820 | 1.281 | yes | 1183.4 | 690.1→2.2 | no |
| Financial_Model_08_03__751f6966e68d | 2749.0 | 1853.8 | 949.4 | 0.512 | 0.345 | no | 1183.4 | 701.7→2.2 | no |
| Financial_Model_08_01__2ea507d758dc | 2654.1 | 1643.5 | 876.7 | 0.533 | 0.330 | no | 1176.7 | 682.3→2.1 | no |
| Debugging_01_06__7b42a0f86b41 | 151.0 | 331.6 | 239.9 | 0.723 | 1.588 | yes | 33.3 | 17.8→0.1 | no |
| Financial_Model_08_01__8021d8d90c40 | 2663.7 | 1601.4 | 887.3 | 0.554 | 0.333 | no | 1176.7 | 686.5→2.2 | no |
| Financial_Model_15_03__472e28fbd6e0 | 341.6 | 573.4 | 450.5 | 0.786 | 1.319 | yes | 114.2 | 63.1→0.3 | no |
| Financial_Model_02_04__5ac07a9edb67 | 233.1 | 268.8 | 188.4 | 0.701 | 0.808 | no | 19.6 | 11.0→0.2 | no |
| Financial_Model_18_05__39d21da726e7 | 162.7 | 237.1 | 172.5 | 0.728 | 1.060 | no | 29.8 | 15.0→0.1 | no |
| Financial_Model_07_01__23c57fc578fc | 1003.9 | 440.8 | 267.5 | 0.607 | 0.266 | no | 168.4 | 107.7→0.4 | no |
| Financial_Model_02_01__4dbc773c2ade | 182.7 | 226.7 | 164.8 | 0.727 | 0.902 | no | 19.3 | 9.2→0.1 | no |
| Financial_Model_11_02__a443eee257b4 | 555.4 | 382.1 | 242.6 | 0.635 | 0.437 | no | 153.9 | 85.4→0.3 | no |
| Financial_Model_11_02__6a75b927c3f6 | 578.6 | 384.9 | 253.4 | 0.658 | 0.438 | no | 153.9 | 88.4→0.3 | no |
| Template_03_03__c76ea596b408 | 93.3 | 215.1 | 155.4 | 0.722 | 1.666 | no | 1.3 | 0.5→0.1 | no |
| Financial_Model_02_01__e87a34eb884e | 190.2 | 230.5 | 163.3 | 0.708 | 0.858 | no | 19.3 | 9.5→0.1 | no |
| Financial_Model_07_01__90a7533589a4 | 1033.5 | 436.5 | 269.6 | 0.618 | 0.261 | no | 168.4 | 101.0→0.4 | no |
| Debugging_08_04__2dde74bd671e | 335.4 | 310.4 | 202.1 | 0.651 | 0.603 | no | 66.9 | 46.7→0.2 | no |
| Debugging_01_06__26b457c478d0 | 147.4 | 252.4 | 177.6 | 0.704 | 1.205 | no | 33.3 | 17.2→0.1 | no |
| Template_06_12__17725eca76da | 101.0 | 216.3 | 157.7 | 0.729 | 1.561 | no | 1.4 | 0.6→0.1 | no |
| Debugging_05_02__31823ebc55b0 | 905.2 | 297.0 | 209.2 | 0.704 | 0.231 | no | 22.0 | 15.7→0.1 | no |
| Debugging_05_02__9e6b464d2158 | 738.1 | 891.1 | 808.9 | 0.908 | 1.096 | yes | 22.0 | 12.3→0.1 | no |
| Template_16_07__9662584ede5e | 96.8 | 204.4 | 154.1 | 0.754 | 1.592 | no | 2.2 | 0.8→0.1 | no |

## SESSION RESULT

Each session is an observed sum of N complete commands, beginning with cold build and followed by genuine reuse; denominator is N independent direct-Python commands. No per-trace extrapolation or omitted startup.

| N | Comparison | Median ratio | Geometric mean | 95% bootstrap median interval | Faster/slower/tied | Range |
|---:|---|---:|---:|---|---|---|
| 1 | H1/H0 | 1.007 | 1.008 | 0.997–1.019 | 9/13/0 | 0.892–1.119 |
| 1 | H1/PY | 1.589 | 1.688 | 1.473–2.107 | 0/22/0 | 1.061–2.504 |
| 2 | H1/H0 | 0.892 | 0.884 | 0.859–0.913 | 22/0/0 | 0.784–0.962 |
| 2 | H1/PY | 1.170 | 1.218 | 0.963–1.585 | 8/14/0 | 0.698–2.024 |
| 3 | H1/H0 | 0.831 | 0.835 | 0.811–0.853 | 22/0/0 | 0.769–0.952 |
| 3 | H1/PY | 1.040 | 1.050 | 0.756–1.458 | 9/13/0 | 0.527–1.875 |
| 5 | H1/H0 | 0.784 | 0.786 | 0.775–0.793 | 22/0/0 | 0.693–0.932 |
| 5 | H1/PY | 0.964 | 0.919 | 0.579–1.374 | 13/9/0 | 0.410–1.744 |

The N=5 observed median is below one but does not meet the fixed majority-plus-bootstrap rule. The H1/H0 session improvement grows with reuse because only warm invocations avoid parent semantic reconstruction and eager imports. Full range and faster/slower/tied counts for every comparison, including H0/PY sessions, are preserved in `analysis.json`.

## H1 VS H0 CAUSAL EFFECT

The three-arm same-run comparison isolates the bundled parent ownership change from historical run conditions. H1 saved a median **100.0 ms** of warm full-command wall across workloads, range **50.3–904.4 ms**, with 22/22 positive savings. Savings grew with old H0 parent validation on large artifacts, while even tiny artifacts gained ~50–60 ms where eager parent imports dominated. No proxy, child, fallback or capture code was changed. H0 and H1 child wall/bootstrap/artifact-load medians were close, supporting parent-side attribution at this coarse boundary; small component differences and uncontrolled OS cache remain. The design changed semantic materialization and eager imports together, so their **individual causal effects are not identified**. The supported causal label is `COMBINED WARM-PARENT OPTIMIZATION EFFECT`.

## BREAK-EVEN GAP AFTER PHASE 4

The Phase-4 same-run H0 median signed warm excess was **+37.9 ms** relative to direct Python; H1's was **−35.8 ms**, range **−1799.6 to +741.8 ms**. This is the median of workload-level treatment-minus-control medians, distinct from the median ratio. The archived Phase-3 signed excess was +82.9 ms; that historical difference should not be treated as a causal estimate because control runtimes changed between runs. H0/PY warm median ratio was **1.180** with 10/22 faster; H1/PY was **0.833** with 13/22 faster. **Three** workloads crossed from H0 slower to H1 faster: `Financial_Model_02_04__5ac07a9edb67`, `Financial_Model_02_01__4dbc773c2ade`, and `Financial_Model_02_01__e87a34eb884e`. No workload crossed the other way. The largest absolute H1/H0 warm gains were the large 08_03/08_01 workbooks (roughly 714–904 ms); the smallest were the tiny Templates (~50–60 ms).

## WARM WINNERS AND LOSERS

H1 beat direct Python on 13/22 fixed scripts. The nine residual losers include all four fallback scripts, all three short Template scripts, `Debugging_01_06__26b457c478d0`, and `Financial_Model_18_05__39d21da726e7`. The Template control medians were **93–101 ms**, while H1 remained **154–158 ms**: the artifact is <3 KiB and parent validation is ~0.1 ms, so remaining fixed command/process cost dominates. The two non-fallback non-Template losers are relatively close (`H1/PY` **1.205** and **1.060**). Large no-fallback models still win strongly even after full command overhead. Because scripts share tasks/workbooks, neither 13/22 nor the bootstrap interval is a broad workbook-population estimate. The 14-task equal-weight warm geometric ratio was **0.781** (task-cluster bootstrap interval **0.520–1.383**), which also does not establish a broad advantage.

## FALLBACK WORKLOADS

Fallback count/reason remained exactly H0's: four scripts, one `proxy_operation_escape` parse per scored invocation; **60** scored reference parses per arm, including 12 cold build-plus-reference and 48 warm reuse-plus-reference. The three covered-merged-cell routes and one workbook-iteration route identified in the Phase-4 audit were unchanged. Same-run H1 warm reference-parse medians were approximately **53 ms** (`Debugging_01_06__7b42a0f86b41`), **502 ms** (`Debugging_05_02__9e6b464d2158`), **2162 ms** (`Financial_Model_08_03__59b98508fd79`), and **203 ms** for workbook iteration (`Financial_Model_15_03__472e28fbd6e0`). These timers nest in child wall and differ from archived Phase-3 values under the current runtime environment. All four still lose to direct Python in H1, with warm ratios **1.588**, **1.096**, **1.281**, and **1.319** respectively. Phase 4 did not remove reference fallback or alter its semantics.

## DID DUPLICATE MATERIALIZATION MATTER?

**Yes as part of the combined parent optimization, but its isolated causal share is unresolved.** Static code inspection showed that H0 constructed and discarded a full `MemoryBook` during warm validation, while the child reconstructed it again. H1 removed the parent's semantic decode in every warm row, taking the parent validation median from 32.27 to 0.18 ms, with child load essentially stable. The full-command H1/H0 warm ratio was 0.704 and all workloads improved. Because lazy imports were removed in the same H1, the 0.704 result cannot be assigned solely to duplicate materialization; tiny Templates had <1 ms old parent validation but still gained ~50–60 ms.

## DID LAZY IMPORTS MATTER?

**The combined effect and diagnostic evidence say they matter; an isolated causal estimate was not run.** H1 valid warm parents had no builder/parser modules loaded; fresh-parent `--help` diagnostic median fell from 96.7 to 28.4 ms, and the scored external-parent residual fell from 111.2 to 52.1 ms. H1 cold paid the deferred builder import and remained near H0 cold. Those facts strongly locate a fixed warm-parent saving, especially on tiny artifacts, but the H1/H0 treatment simultaneously changed validation. Decision label: `COMBINED WARM-PARENT OPTIMIZATION EFFECT`; attribution between duplicate materialization and lazy imports remains unresolved. A new two-factor ablation would be needed to label either component independently.

## IS AGGREGATE WARM SPEED NOW SUPPORTED?

**No under the unchanged preregistered Phase-3 decision standard.** The fixed scripts showed a favorable observed H1/PY median **0.833** and a majority **13/22** faster with exact semantics and child-confirmed reuse. The 2,000-resample median upper bound was **1.205**, above one; task clustering reinforces the uncertainty. Cold remained 22/22 slower, and no observed N≤5 session met the same fixed rule. The causal warm-parent optimization itself is strongly supported by same-run H1/H0 0.704 and 22/22 faster; that conclusion is separate from a population-level product-shaped speed verdict. This is still an offline harness, not a public RC measurement or claim.

## NEXT OPTIMIZATION

The remaining low-surface opportunity is a **separate merged-cell proxy semantic experiment**, not an automatic fallback bypass. Three of the four reference-fallback losers are triggered by covered merged-cell `.cell(...).value` reads; the direct representation already records the narrow value/type behavior, but the current proxy materializes reference to preserve richer `MergedCell` identity. A next preregistered test would first prove exactly which merged-cell observations can be served compatibly under the unchanged admission contract, retain reference fallback for richer observations, and then score the **same 22 scripts and full-command endpoint** against this Phase-4 H1 baseline. The fourth workbook-iteration fallback and the short-Template process overhead remain separate. If merged-cell identity cannot be preserved without widening the semantic contract, record that limit rather than suppress fallback. No such optimization was implemented here; public product integration and speed claims remain unearned.
