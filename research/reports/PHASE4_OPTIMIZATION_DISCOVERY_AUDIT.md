# Phase 4 optimization discovery audit

**Status:** offline evidence and implementation audit; no optimization, product change, or scored rerun. This examines the frozen 22-script Phase-3 primary population at the same external full-command boundary. The 30-script representative view is used only to inspect non-contact behavior. Sources are [Phase-3 report](READ_ENGINE_PHASE3_REPORT.md), [paired analysis](../../read_engine_phase3/analysis.json), [profile](../../read_engine_phase3/profile.json), [raw invocation ledger](../private-data-manifest.json), [runtime events](../../read_engine_phase3/runtime_events.jsonl), [population](../../read_engine_phase3/population.json), and the Phase-3 [parent](../../read_engine_phase3/harness.py), [runtime](../../read_engine_phase3/runtime.py), [bootstrap](../../read_engine_phase3/bootstrap/sitecustomize.py), and [artifact](../../read_engine_phase3/safe_artifact.py) implementations. Phase-1 [decoder](../../read_engine_phase1/prototype.py) and frozen RC admission/capture were inspected as dependencies. All arithmetic below uses existing scored rows. The only new execution was diagnostic fresh-interpreter import timing and static workbook/script inspection; no workload benchmark was rerun. Existing uncommitted workspace changes were left alone.

Classification key in the lifecycle table: **S** = `REQUIRED_FOR_SEMANTICS`; **F** = `REQUIRED_FOR_SAFETY/FRESHNESS`; **O** = `REQUIRED_FOR_OBSERVABILITY`; **R** = `RESEARCH/PROTOTYPE OVERHEAD`; **D** = `DUPLICATED`; **L** = `POTENTIALLY DEFERRABLE`; **E** = `POTENTIALLY ELIMINABLE`; **?** = `UNKNOWN`. More than one may apply.

## CURRENT BREAK-EVEN GAP

The historical packaged RC cold median was **2.017**. Phase 3, on the same 22 script/workbook identities, measured cold **1.595** (22/22 slower), warm **1.230** (9 faster, 13 slower), and observed N=5 session **1.307**. All scored primary pairs were exact, all contacted direct serving, and every warm treatment had a `REUSED` witness. This is an offline product-shaped harness, not a changed public RC.

The following differences subtract the per-workload warm control median from the per-workload warm treatment median in `analysis.json`; they are **not** medians of invocation-level differences. Milliseconds are rounded. Negative means treatment saved time.

| Workload | Family | Control ms | Treatment ms | Excess ms | Ratio | Fallback |
|---|---|---:|---:|---:|---:|---|
| Financial_Model_08_01__8021d8d90c40 | Financial_Model | 4504.5 | 2678.1 | -1826.3 | 0.595 | no |
| Financial_Model_08_01__2ea507d758dc | Financial_Model | 4338.0 | 2584.0 | -1754.0 | 0.596 | no |
| Financial_Model_08_03__751f6966e68d | Financial_Model | 4333.9 | 2636.7 | -1697.2 | 0.608 | no |
| Financial_Model_07_01__90a7533589a4 | Financial_Model | 1751.9 | 749.5 | -1002.3 | 0.428 | no |
| Financial_Model_07_01__23c57fc578fc | Financial_Model | 1644.2 | 702.5 | -941.7 | 0.427 | no |
| Debugging_05_02__31823ebc55b0 | Debugging | 1237.6 | 419.9 | -817.7 | 0.339 | no |
| Financial_Model_11_02__a443eee257b4 | Financial_Model | 946.2 | 661.5 | -284.7 | 0.699 | no |
| Financial_Model_11_02__6a75b927c3f6 | Financial_Model | 918.3 | 644.2 | -274.2 | 0.701 | no |
| Debugging_08_04__2dde74bd671e | Debugging | 568.0 | 516.2 | -51.9 | 0.909 | no |
| Financial_Model_15_03__103457370cae | Financial_Model | 551.1 | 569.6 | +18.5 | 1.034 | no |
| Financial_Model_02_01__e87a34eb884e | Financial_Model | 317.8 | 394.7 | +76.9 | 1.242 | no |
| Financial_Model_02_04__5ac07a9edb67 | Financial_Model | 315.8 | 404.7 | +88.9 | 1.281 | no |
| Financial_Model_02_01__4dbc773c2ade | Financial_Model | 331.9 | 431.9 | +100.0 | 1.301 | no |
| Financial_Model_18_05__39d21da726e7 | Financial_Model | 298.9 | 442.8 | +143.9 | 1.481 | no |
| Debugging_01_06__26b457c478d0 | Debugging | 254.3 | 435.2 | +180.9 | 1.711 | no |
| Template_06_12__17725eca76da | Template | 172.3 | 370.9 | +198.5 | 2.152 | no |
| Template_03_03__c76ea596b408 | Template | 168.9 | 372.6 | +203.7 | 2.206 | no |
| Template_16_07__9662584ede5e | Template | 180.2 | 413.5 | +233.2 | 2.294 | no |
| Debugging_01_06__7b42a0f86b41 | Debugging | 248.9 | 516.1 | +267.2 | 2.073 | yes |
| Debugging_05_02__9e6b464d2158 | Debugging | 1233.6 | 1501.6 | +268.0 | 1.217 | yes |
| Financial_Model_15_03__472e28fbd6e0 | Financial_Model | 558.1 | 976.0 | +418.0 | 1.749 | yes |
| Financial_Model_08_03__59b98508fd79 | Financial_Model | 4457.3 | 6865.3 | +2408.1 | 1.540 | yes |

Median signed excess is **+82.9 ms**; range **-1826.3 to +2408.1 ms**; inclusive quartiles approximately **-684.5 and +202.4 ms**. A fixed subtraction from *every* warm treatment median would give the following **diagnostic counterfactual**, not an expected effect of any actual change:

| Hypothetical saving per workload | Faster / slower | Recomputed median paired ratio |
|---:|---:|---:|
| 0 ms | 9 / 13 | 1.230 |
| 25 ms | 10 / 12 | 1.180 |
| 50 ms | 10 / 12 | 1.104 |
| 100 ms | 13 / 9 | 0.946 |
| 150 ms | 14 / 8 | 0.788 |
| 200 ms | 16 / 6 | 0.659 |

The median signed gap is not a universal fixed-overhead estimate. Large winners and large fallback losers make this distribution highly heterogeneous. The old Phase-3 decision rule also required a majority faster and a bootstrap upper bound below one; the counterfactual rows establish neither.

## WHAT OPENPYXL WORK HAS ALREADY BEEN REMOVED

For admitted supported loads that never escape the proxy, normal `openpyxl.load_workbook` workbook parsing, creation of normal worksheet/cell objects, and openpyxl's reference read operations are avoided. A source hash and direct OOXML decode create the cold artifact; a warm command reopens that artifact. The proxy supplies ordered sheet names, literal worksheet lookup, bounds/dimensions, single-cell and integer `.cell` access, and cell `.value`/`.data_type`. The direct decoder's contract was established in Phases 1–2, and all Phase-3 primary scored outputs remained exact. In the Phase-3 raw events, 18/22 primary scripts never invoked a reference parse; all 22 invoked direct serving.

The amount of **normal reference parse time saved on the 18 non-fallback Phase-3 scripts is not separately timed**: CONTROL only has a whole-script clock. The nine long-workload warm wins show net savings after treatment costs, not a clean parse-only saving. Phase-1 trace timings establish a different index-ready boundary and cannot be inserted as an additive Phase-3 component. The four fallback parse timers below measure reference cost only on those scripts and are not a matched estimate for the others.

## WHAT OPENPYXL WORK REMAINS

Both CONTROL and every primary treatment child import `openpyxl`, because the ordinary script imports it and the runtime patches `openpyxl.load_workbook`. The direct decoder module also imports openpyxl formula translation, number-format/date helpers, and formula observable classes; importing an openpyxl submodule initializes its package. The child imports this builder-bearing decoder indirectly through `safe_artifact`, including `lxml`, although an already-built artifact needs no XML parsing. Thus “no openpyxl **workbook parse** in direct construction/serving” is accurate; “no openpyxl library cost” is false. Moving the child's openpyxl import from bootstrap into the script would mostly move a shared cost, not eliminate it.

On the four fallback scripts, `ProxyWorkbook._real_workbook()` calls the saved normal loader exactly once per invocation and caches that real workbook. The frozen narrow direct state has already been built or loaded. That invocation therefore pays both direct-state machinery and a normal reference parse. The reference parse is required for the unsupported observable operation unless a semantically exact narrower route is demonstrated; removing fallback by fiat is not a valid optimization.

## FULL TREATMENT LIFECYCLE

For an admitted warm, no-fallback command the ordered path is below. `harness.run()` starts its `parent_total` timer **after** the parent module and RC capture/classifier imports; external wall includes these imports and final exit. `Runtime.bootstrap_ns` runs from `sitecustomize` entry through patch installation; `post_bootstrap_to_exit_ns` includes script operations and exit work. These clocks nest and their medians cannot be summed.

| # | Actual call/action | Class | What CONTROL does / observation |
|---:|---|---|---|
| 1 | New parent interpreter, `site`, top-level `harness` imports `safe_artifact` → Phase-1 `prototype` → `lxml` and openpyxl utility/package modules | R, D, L, E | CONTROL starts one interpreter and imports openpyxl in its script; treatment starts this **additional** interpreter. Parent parser imports are unnecessary to attach an already-valid artifact. External-minus-`parent_total` also includes shutdown and is not fully split. |
| 2 | `argparse`; import RC config, classifier and capture | S, O, L | CONTROL has no launcher/config/capture imports. |
| 3 | Load config; resolve/validate script and workdir; explicit parent `import openpyxl`; create UUID/cache/run directories | S, F, O, D, E | CONTROL runs the staged script directly; parent openpyxl import is redundant for a warm metadata-only path. |
| 4 | Read script and run unchanged whole-script classifier | S | CONTROL has no admission gate; median <1 ms after imports. |
| 5 | Glob every top-level `.xlsx` | S, L | CONTROL opens only paths named by script. Phase-3 primary staging had one source each. |
| 6 | SHA-256 each discovered source; derive artifact key | F | CONTROL has no separate freshness hash; primary median ~0.65 ms. |
| 7 | Read sidecar; check identities/key/size; read entire artifact; hash it; call `decode` for envelope, payload and schema validation | F, D, L, E | No CONTROL artifact. Parent creates and discards a complete `MemoryBook`; median 48.5 ms, varying from <1 to ~1095 ms. |
| 8 | Pre-capture `snapshot_xlsx`: recursively read workbook bytes | O, D | CONTROL has no capture; median ~0.38 ms. Distinct from source hash because it preserves pre-execution package bytes. |
| 9 | Serialize context, copy/filter environment, set bootstrap `PYTHONPATH`, invoke `subprocess.run` with captured stdout/stderr | S, F, O, ? | CONTROL itself is the only child of benchmark runner. Treatment adds a parent→child transition; environment-construction time is uninstrumented. |
| 10 | New child interpreter and `site` startup | S, ? | CONTROL also needs one interpreter. The **second** process is treatment-only; measured child startup residual ~54 ms is not pure interpreter startup. |
| 11 | `sitecustomize` reads context; imports `runtime` → `safe_artifact` → decoder, `lxml`, openpyxl helpers; parses context | S, F, O, L | CONTROL imports openpyxl later in the script. The extra runtime/decoder import portion is not separately measured. |
| 12 | Script-path guard; `Runtime.install` imports openpyxl, saves loader, patches `load_workbook`, registers atexit | S, F, O | CONTROL imports openpyxl but does not patch it. Child bootstrap/import median ~121 ms, mostly overlapping work CONTROL also needs. |
| 13 | Script starts, `import openpyxl` finds module cached; executes normal `load_workbook` call | S | CONTROL's call enters normal parser. |
| 14 | `Runtime.load` checks load mode/path, entry and status; rehashes source | F, D | CONTROL does no second SHA. Child hash ~0.65 ms protects parent→child TOCTOU. |
| 15 | Child reads artifact, verifies envelope/hash/identity, decompresses, parses JSON, checks every record, reconstructs `MemoryBook` | S, F, D | CONTROL parses source workbook. Child artifact load median ~47.8 ms; it is a second full semantic decode after parent validation. |
| 16 | Construct proxy workbook/worksheet/cells on demand and execute direct reads; count events | S, O | CONTROL uses native openpyxl objects. Served-read time is uninstrumented. |
| 17 | Unsupported proxy operation, if any, materializes normal workbook once and caches it | S, ? | Absent on the no-fallback path; present on four primary scripts. |
| 18 | Script exits; atexit closes real fallback books if any, writes runtime profile and event JSONL | S, O, R | CONTROL exits without runtime telemetry; exit overhead is not separately timed. |
| 19 | Parent waits, forwards stdout/stderr, reads child profile/events | S, O, R | Benchmark receives CONTROL stdout/stderr directly. Diagnostic read median ~0.27 ms. |
| 20 | Post `snapshot_xlsx`; compare packages; derive delta, commit, mechanical validate/replay only if changed | O, F, L | CONTROL has no product effect capture. Primary median ~0.54 ms; derive/commit/validation/replay medians zero on unchanged workbooks. |
| 21 | Write summary, capture, parent profile, last-run record, then final profile rewrite; parent exits | O, R, E | CONTROL has no run ledger. Diagnostic write median ~0.73 ms; final rewrite and teardown not separately measured. |

The corresponding CONTROL path is: external launcher → one fresh Python interpreter/site → script import of openpyxl → normal `load_workbook` parse → ordinary object reads/possible output → process exit. Input staging, output/package hashing, and semantic comparison in `benchmark.py` occur **after** the external command timer for both arms. The treatment cost equation is therefore `avoided normal workbook parse/object/read work − direct representation and proxy work − additional parent/child/runtime/capture work`, with reference parse added back on fallback. No Phase-3 timer directly isolates avoided normal parse or served-read execution.

## PARENT CHILD DUPLICATION

| Operation on reused artifact | Parent `validate` | Child `load` | Assessment |
|---|---|---|---|
| Source whole-file SHA | yes, in `harness` | yes, in `Runtime.load` | Two reads; child check protects changes after parent check. Cheap on this population. |
| Sidecar read, key, identity, length | yes | no | Parent-only discovery/publication check. |
| Artifact stat/full file read | yes | yes | Duplicated; full artifact bytes required by child, parent can potentially validate without reconstructing cells. |
| Whole artifact SHA | **twice**: sidecar comparison and `decode` envelope | once: `decode` envelope | Repeated integrity work. |
| Envelope identity and structural checks | yes | yes | Child fail-closed check remains necessary for serving; parent can check a compact envelope. |
| zlib decompression, payload SHA | yes | yes | Duplicated. Parent need for full payload proof versus child trust boundary needs an explicit policy. |
| JSON parse, every sheet/cell schema check, typed conversion, `MemoryBook` allocation | yes, then discarded | yes, retained for reads | Confirmed unnecessary **semantic** materialization in parent on successful warm reuse. |
| Cold direct OOXML decode and safe encode | parent only | no | Construction rather than duplication. |

`safe_artifact.validate()` calls `decode(blob, source_sha)` only for its boolean return; `ensure()` discards the book. `Runtime.load()` calls `safe_artifact.load()` and reconstructs it again. The parent's validation timer is an upper bound on a parent-only removal: median **48.5 ms**, range by workbook **0.8–1095 ms**. It includes useful sidecar/integrity checks, so the realizable saving is smaller. On the short losing Template scripts, this timer is only **0.8–1.3 ms**. Idealized subtraction of the *entire* recorded parent validation from each workload leaves **10/22** faster and median ratio **1.198**; it cannot alone explain or reverse the aggregate loss. A safe future handoff could let the parent verify source identity, sidecar, format/header and file integrity, with child full schema/semantic decode before serving and fail-closed fallback if invalid. That trust split is a hypothesis, not an implemented guarantee; a parent `REUSED` label alone must not substitute for successful child validation.

## BOOTSTRAP AND IMPORT COST

Phase-3 warm component medians are child bootstrap/import **121.3 ms**, child startup residual **53.7 ms**, and child wall **281.7 ms**. The residual is computed as `child_wall − bootstrap − post_bootstrap_to_exit`, so it also includes scheduling/IPC and is **not** a pure interpreter clock. Warm external wall minus `parent_total` has median **199.6 ms** across per-workload medians (range 190.1–222.3 ms). This bucket includes parent interpreter startup, top-level and RC imports, CLI parsing before `run()`'s timer, final profile write, shutdown, and external launch/reaping; its internal split is **UNMEASURED** in Phase 3. For each of the three tiny Template scripts, parent non-child work *inside* `run()` is only ~4–5 ms, yet this external-parent residual is ~199–222 ms. Their artifacts each load in ~1 ms. This fixed command shape, rather than duplicate artifact decode, dominates their losses.

Diagnostic-only fresh-process probes used the frozen RC Python 3.13.12 environment, `PYTHONDONTWRITEBYTECODE=1`, no benchmark script, 7–15 observations per import case, OS cache uncontrolled. External median process walls: bare Python **~10 ms**; `import openpyxl` **~85 ms**; `import lxml.etree` **~26 ms**; `import read_engine_phase3.safe_artifact` **~86–87 ms**; parent config/classifier/capture imports without artifact/openpyxl **~39 ms**; with openpyxl or current safe-artifact stack **~88–90 ms**; `harness.py --help` **~93 ms**. `-X importtime` showed `safe_artifact → prototype → openpyxl.formula.translate` with cumulative import timing around 97 ms in one process, including openpyxl's workbook/chart/reader modules. These are diagnostic import costs, not scored treatment deltas. The ~50 ms diagnostic difference between a parent with and without artifact/openpyxl imports is a *plausible upper neighborhood* for lazy warm-parent imports, not a measured full-command saving. It also does not explain all of the scored ~200 ms external-parent residual.

**Product relevance:** an ordinary script imports openpyxl, so removing its child import is not a free saving. The Phase-3 warm child also imports builder-only `lxml`/decoder code through a convenience module, but the incremental cost over mandatory openpyxl import looked small in isolated probes and is not split by the scored timer. Parent openpyxl/decoder import is treatment-only and unnecessary for metadata-only warm reuse. A second process, and therefore its startup, is inherent to this prototype's parent/child shape but not to the narrow read contract. The present numbers do not justify claiming 121+54 ms as removable bootstrap cost.

## REFERENCE FALLBACK COST

All **60** scored primary reference parses were `proxy_operation_escape`: four scripts × 15 invocations each. The parent always built or reused the direct artifact first. Twelve cold invocations combined `BUILT` with a later normal parse; 48 warm invocations combined `REUSED` with a later normal parse. In the inspected scripts and frozen workbook merged ranges:

| Workload | Escape demonstrated by code/data | Warm median normal parse | Warm excess |
|---|---|---:|---:|
| Financial_Model_08_03__59b98508fd79 | `.cell(...).value` touches 38 covered merged coordinates in `DCF Valuation`; `ProxyWorksheet.cell` asks reference for merged-cell identity | 3509 ms | +2408 ms |
| Debugging_01_06__7b42a0f86b41 | Six covered merged-coordinate contacts in `Ex 10 - Balance Sheet` | 80 ms | +267 ms |
| Debugging_05_02__9e6b464d2158 | Eight covered merged-coordinate contacts in `Model` | 831 ms | +268 ms |
| Financial_Model_15_03__472e28fbd6e0 | `for ws in wb`: workbook iteration is outside frozen narrow contract | 334 ms | +418 ms |

The first three are a more specific cause than the generic event label: `ProxyWorksheet.cell()` explicitly sends covered merged cells to `_real_sheet()`. The Phase-1 `MemoryBook.cell()` already returns the frozen narrow `None`/`n` behavior for covered merged coordinates, but the proxy preserves full openpyxl `MergedCell` identity by materializing reference. Workbook iteration remains a distinct unsupported operation. These parse medians are nested in child wall and cannot be added to treatment excess. Once materialized, the real workbook is cached, so there is one normal parse per invocation, not one per merged cell. Existing direct reads before/after fallback can still save work; calling the whole artifact “wasted” would overstate it.

An idealized subtraction of the three merged-case parse timers, with no replacement cost or semantic change, moves the fixed-population median ratio to **0.971** but only **11/22** faster; it fails the earlier majority criterion and says nothing about confidence or compatibility. This identifies leverage, not a valid result. Serving covered merged coordinates directly would require exact observable `MergedCell` behavior or a proven rule that admitted scripts observe only the narrow attributes. A silent fallback bypass is unsafe.

## REFERENCE-ONLY FAST PATH

The secondary frozen 30-script view had **22 reference-only/non-contact scripts**. They still traverse parent interpreter/import/config/classifier/run-dir/pre-capture, launch a child with `sitecustomize`, install the runtime and import openpyxl, record `source_rejected_before_interposition` reference parses, then post-capture and persist diagnostics. They skip workbook discovery/artifact `ensure` in `harness.run()`. Median reference-only treatment child bootstrap was **~116.6 ms** and treatment wall **~506.9 ms** across those scripts; these are descriptive, not a paired control saving. The same source-rejected child ultimately performs the script's normal reference parse.

A production reference-only path could avoid read-engine bootstrap, artifact machinery and its event detail once the unchanged static classifier rejects serving, while retaining whatever pre/post effect capture and diagnostic contract the product actually requires. The current behavior is largely Phase-3 harness observability rather than a necessity of direct reads. It cannot improve the primary 22-script result, because every one is admitted/contacted. It matters for representative product economics, where 22/30 scripts otherwise pay runtime overhead without read replacement. The existing RC had a reference-only path; Phase 3's experimental bootstrap intentionally logged these paths.

## PROTOTYPE-ONLY OVERHEAD

Inside the scored treatment command: per-call coarse timers, detailed runtime event JSONL, `last_run.json`, profile/summary/capture records, and a final duplicate parent-profile write are experimental/audit features. Measured parent diagnostic read/write medians total only about **1 ms**; eliminating them alone is immaterial and would reduce observability. The context is passed as JSON in an environment variable; parse/build cost is uninstrumented but likely far smaller than the 100–200 ms gaps on short scripts. Research constants and openpyxl-load spy guards add small unmeasured work; they establish independence and should remain during semantic validation. `capture.snapshot_xlsx` is product-shaped mechanical effect capture, not disposable benchmark bookkeeping; its median read-only cost is <1 ms per side here, though importing capture contributes to startup.

Outside the external timer: `benchmark.py` restages scripts/workbooks, computes post-run file and XLSX package hashes, compares control/treatment output and writes raw ledgers. Removing this work would **not change** the Phase-3 command ratios and would make correctness evidence weaker. The correctness artifact gate and Phase-1/2 differential checks were not ordinary treatment operations. `safe_artifact` uses a safe typed JSON/zlib format as a product-shaped choice, not mere benchmark bookkeeping; changing it would be a new representation experiment. The parent/child double semantic decode is prototype implementation convenience with product-relevant cost, not a required validity rule.

## WARM WINNERS VS WARM LOSERS

The nine winners have median CONTROL **1644 ms** and median treatment **703 ms**; the 13 losers have median CONTROL **316 ms** and treatment **435 ms**. Winner median artifact size is **168 KiB**, loser median **22 KiB**: larger artifacts do not imply loss here because long reference execution offers more to replace. This is descriptive across a contact-selected set with repeated tasks, not causal inference. Seven Financial_Model and two Debugging scripts win; seven Financial_Model, three Debugging, and all three Template scripts lose. The clear pattern is **short control duration and fixed harness overhead**, with fallback creating large exceptions among longer scripts.

The tiny Templates control in **169–180 ms** and lose **199–233 ms**. Their parent artifact validation and child artifact load are only **~0.8–1.3 ms each**; child bootstrap is **~114–129 ms**, but much openpyxl import work is common to control. External-parent residual is **~199–222 ms**, and parent non-child in-run work only **~4–5 ms**. Financial_Model_15_03__103457370cae is near break-even at **+18.5 ms**. The three 02_01/02_04 scripts need **~77–100 ms**. Large warm winners have expensive artifact decoding (e.g. the 08_01/08_03 no-fallback cluster **~1.07–1.10 s** in both parent and child) and still win because CONTROL is ~4.3–4.5 s. The four fallback losers have median excess **~343 ms**; the 18 no-fallback scripts' median signed excess is **~-17 ms**. No single artifact-size or family rule explains the full distribution. Read volume is not recorded as a separate operation timer; `direct_served_reads` exists per invocation but does not establish which read types dominated elapsed time.

## OPTIMIZATION CANDIDATES

Here “isolation” means a future single-change A/B on the same 22 identities and full-command endpoint. Leverage is a measured category or idealized ceiling, **not** a predicted speedup. `Low surface` means the parent/child architecture and script interface can remain intact; `process model` signals a larger change.

| Candidate | Mechanism and evidence / plausible ceiling | Semantic/safety risk | Isolation and product relevance |
|---|---|---|---|
| **Parent metadata-only warm validation and lazy builder import** (low surface) | Do not construct/discard a `MemoryBook` in parent; defer Phase-1 decoder/openpyxl import until a build is needed. Parent keeps source SHA, sidecar/header/whole-artifact integrity; child remains full schema gate. Parent validation median 48.5 ms, but <2 ms for Templates; diagnostic warm-parent import stack could offer ~50 ms more. | Must preserve fail-closed corrupt/version/stale rejection and honest `REUSED` witness after child success. | One warm-parent ownership change; cleanly testable. Product-relevant. It cannot be assumed to reverse median: idealized full validation removal alone leaves ratio 1.198, 10/22 faster. |
| **Covered-merged-cell narrow serving with reference escape for richer observation** (low surface, semantic edge) | Avoid full normal parse for three fixed scripts whose `.cell(...).value` touches merged children. Reference parse medians 80/831/3509 ms; idealized median ratio 0.971, 11/22 faster. | `MergedCell` class/identity, style and other rich attributes must remain compatible. The classifier may not rule out every such observation. No blanket fallback removal. | One proxy-path change plus explicit contract gate; product-relevant to merged workbooks. More semantic risk than parent handoff. |
| **Warm child serving-only import split** (low surface) | Stop importing XML decoder/lxml and builder-only utilities when child only loads an artifact. Child bootstrap median 121 ms, but mandatory openpyxl import accounts for much of it; isolated child-stack median ~89 ms versus openpyxl ~85 ms. | Wrong lazy import could break formula classes or fallback; no freshness change. | Separately testable module split; likely modest, product-relevant. 121 ms is not a legitimate saving estimate. |
| **Smaller/sheet-lazy safe artifact** (representation change) | Avoid decoding all cells before first read and/or reduce JSON/zlib reconstruction. Child load ranges <1 to ~1081 ms; parent load duplicates it. | Higher corruption, type, random-read and atomicity complexity; may change first-read latency. | Requires a new preregistered format and correctness gate; product-relevant, but Phase 3 was not a format shootout. Defer until lifecycle waste isolated. |
| **Reference-only direct child path** (low surface for rejected scripts) | Skip runtime bootstrap/event machinery when unchanged admission rejects. Secondary has 22/30 non-contact; primary has 0/22. | Preserve capture, reference invocation and truthful diagnostics. | Isolatable on fixed secondary view; product-relevant, **zero primary leverage**. |
| **Fallback-aware pre-bypass** (rule change) | If a whole-script proof establishes guaranteed unsupported use, skip direct state for that invocation. Could save parent/child artifact costs on four fallbacks, especially ~1 s loads on one large case. | Static proof may be incomplete; an incorrect pre-bypass changes contact/serving and may lose savings. Existing admission was frozen for Phase 3. | Test only under separate preregistration; not the next fixed-mechanism test. |
| **Remove redundant hashes/capture/diagnostic writes** (micro) | Child source SHA ~0.65 ms; pre/post capture ~0.38/0.54 ms; parent diagnostic I/O ~1 ms. | Hash removal weakens TOCTOU; capture removal changes observability. | Some pieces isolatable and product-relevant only with safety proof; cannot close ~83 ms median gap. |
| **One-process command with in-process interposition and capture**, or **persistent parent/worker** (process model) | Address the ~200 ms external-parent residual and/or ~54 ms child residual by eliminating or amortizing an interpreter/process boundary. Tiny Templates show this is the only single fixed category of their ~200 ms loss. | Significant process isolation, failure capture, environment, stdout/stderr and stale-state risks. A long-lived worker cannot reuse arbitrary script globals safely without stronger isolation. | Product-relevant but architectural. Keep deferred until lower-surface tests show how much residual remains. |
| **`fork`/memory handoff, mmap or shared-memory state** (process/representation model) | Could share parent-decoded cells with child or avoid duplicate deserialization. Child load median 47.8 ms, ~1 ms on tiny losers and ~1.1 s on largest. | Fresh-interpreter semantics, platform portability, typed object safety, and crash isolation. | Multiple causal mechanisms entangled; defer. |

## MAXIMUM PLAUSIBLE LEVERAGE

Measured component ceilings are highly workload-specific. Removing the **entire** warm parent artifact validation would save at most its recorded 48.5 ms median and much less on the short scripts; it produces only 10/22 idealized winners. Removing **all** child artifact load has the same shape and would also alter the serving architecture. Eliminating only source hashes/capture/diagnostics is single-digit milliseconds on the median primary workload. The child bootstrap's 121 ms cannot be treated as removable because CONTROL imports openpyxl too. Parent imports and the additional process boundary are the largest fixed treatment-only category; the **~199.6 ms external-parent residual** is a descriptive bucket, not a validated removable block. Its ~50 ms diagnostic import differential and remaining unexplained portion require a causal test before any full-command savings claim.

Fallback is a large **localized** lever: three covered-merge parses of ~80, 831, and 3509 ms plus one workbook-iteration parse ~334 ms. Only the first three have an apparent route within the frozen narrow value/type contract. A no-cost subtraction from those three yields median ratio 0.971 but only 11 faster; it is deliberately an optimistic bound, not a speed prediction. A causal change must preserve exactness and be charged at the full endpoint. The idealized uniform 100 ms row in the first section crosses a majority, but existing low-surface costs are not uniform across workloads.

## IS ONE CHANGE ENOUGH?

**No low-surface change is established as sufficient.** Parent duplicate decode is large on workloads that often already win and negligible on the tiny losers. The targeted merged-cell path could move the numerical median below one under an impossible zero-cost/zero-risk subtraction, but does not reach the old majority rule in that bound. A wholesale removal of the additional parent-process cost would be large enough to matter across short workloads, yet that is a process-model change with substantial semantic and observability obligations. The most defensible expectation is at least two independent reductions: a cheap, safe warm-parent path plus either an exact merged-cell proxy escape repair or a justified command/process overhead reduction. This is a hypothesis about engineering sequence, not a new performance finding.

## SELECTED NEXT EXPERIMENT

Test **parent warm artifact validation without semantic materialization, with decoder/openpyxl imports deferred until a cold build**. This is selected first for its direct code evidence, limited semantic surface, ability to fail cleanly, and importance to both fast and slow artifacts. It is not selected because its existing timer guarantees median break-even; the idealized bound says it probably will **not** do so alone. It establishes whether the safest confirmed duplication can be removed at the unchanged full boundary and how much of the external-parent residual was actually due to eager imports. Merged-cell fallback handling is the next distinct semantic hypothesis, not bundled into this test. A process-model experiment is deferred until these lower-surface opportunities have measured effects.

## EXPERIMENT DESIGN

**Control implementation:** freeze the exact Phase-3 harness/decoder/artifact/runtime. **Treatment implementation:** change only warm parent artifact discovery/validation ownership: verify source SHA and sidecar/identity/format/length/integrity without calling `_book` or creating `MemoryBook`; import decoder/openpyxl construction modules only on missing/invalid artifact requiring build. Keep existing artifact format, child full `decode`/schema validation, proxy/fallback, RC classifier, capture, parent/child process model, output ledgers and script interface. A child decode failure must fail closed into the same reference route and invalidate any claimed successful reuse; corruption must not be served. Do not weaken whole-file freshness.

Before timing, preregister exact Phase-3 22 identities, control/treatment code hashes, repetitions/order, the same external CONTROL/T-COLD/T-WARM/N=1,2,3,5 session clocks, and the old semantic/output comparison. Require 22/22 identity matches; exact scored outputs and package state; all warm `REUSED` witnesses confirmed by successful child decode; missing, truncated, same-path changed-source and version-mismatch rejection; unchanged fallback event classes/counts unless the implementation itself reveals a defect. Instrument parent import-to-`run` time and post-`run` shutdown residual separately, plus sidecar/read/hash/header checks, zlib/JSON/schema/`MemoryBook` work in parent and child. Preserve child process startup and existing profile boundaries so observed changes can be attributed. Report per-workload paired ratios, medians, counts and intervals with task clustering caveat.

**Predicted affected components, not predicted result:** warm parent semantic-decode portion of `artifact_discovery_validation_ns` should vanish; parent warm decoder/openpyxl import time should fall; child artifact load, normal script work, source SHA, capture and fallback should remain materially stable. Cold builds should still import the decoder and produce the same artifact. **Falsification:** a semantic/invalidation failure, loss of actual reuse, a material unexplained child/control timing shift, or no measurable full-command reduction despite removal of the measured parent work. If exactness passes but median remains ≥1, record that result; do not change population, extend the contract, or stack another optimization into the same run.

## EARNED VS HYPOTHESIZED

**EARNED:** direct OOXML is exact on the frozen narrow surface; safe persistent state reopens across fresh processes; Phase 3 repaired the old four semantic failures on their exact scripts; on the same failed 22-script population, cold 1.595 and warm 1.230 remain net losses despite nine warm wins and genuine reuse. **LIKELY ENGINEERING WASTE:** warm parent fully reconstructs and discards the same artifact the child reconstructs; warm parent imports construction/parser machinery; three fallback scripts incur a full reference parse when covered merged cells are read for their values. These are implementation facts, while their removable milliseconds are not yet causally measured. **HYPOTHESIS:** a metadata-only warm parent with lazy builder imports reduces full-command wall materially and preserves fail-closed validation; it is unlikely by itself to make all short scripts competitive. **DEFERRED:** merged-cell proxy semantics, reference-only bypass, a new persistent representation, direct OOXML expansion, and any single-process/persistent-worker model. The public RC and claims remain unchanged.
