# Phase 10B reference-only path audit

Written before attribution-arm implementation or scored Phase-10B timing. The maintained path is `native/launcher.c` → `native/observer.c` → a real Python script interpreter with `_bootstrap/sitecustomize.py`. The direct read engine is **not** installed after negative admission.

## Ordered path and ownership

| Stage | Actual work and files/processes | Classification |
|---|---|---|
| User command / native launcher | `librecalc-agent run`; resolve executable via `/proc/self/exe`, locate adjacent Python and installed package via `glob`, parse simple `--workdir`, `realpath` script/workdir, derive XDG cache, create/chmod cache and `runs`, then `execv` observer. No Python interpreter yet. | PRODUCT CONVENIENCE; REQUIRED FOR PROCESS CONTRACT for locating the observer; possible residual cost. |
| Observer setup | Resolve paths, create `run-XXXXXX`, write `context.txt`, establish run identity. | REQUIRED FOR EFFECT ASSURANCE; PRODUCT CONVENIENCE for the exact receipt layout. |
| Pre-observation | `nftw` the workdir; read eligible XLSX files completely into a bounded snapshot (1,000 files/512 MiB). | REQUIRED FOR EFFECT ASSURANCE under the current package-delta contract. |
| Target launch | `fork`, set `PYTHONPATH` to package bootstrap plus inherited path and `LIBRECALC_RUN_CONTEXT`, `chdir`, `execv` the real Python interpreter and byte-identical script. | REQUIRED FOR PROCESS CONTRACT; REQUIRED FOR EFFECT ASSURANCE because the observer must survive script death. |
| Python startup / sitecustomize | Normal Python `site` loads guarded `sitecustomize`; import `json`, `os`, `sys`, `time`, `pathlib`; read four-line context and confirm `sys.argv[0]` resolves to the target script. | REQUIRED FOR ROUTING AUTHORITY for guarded activation; some import cost is UNKNOWN until causal arms. |
| Config | Import `librecalc_agent.config` (`dataclasses`, `tomllib`, `pathlib`); load defaults or explicit configuration. The scored native default path has no explicit config file. | REQUIRED FOR ROUTING AUTHORITY for supported configuration; potential PRODUCT CONVENIENCE residue in the default path. |
| Admission | Read the target source as UTF-8; import frozen classifier (`ast`, `re`); parse and classify whole source. All 22 primary scripts receive `PREDECLARED_REAL_OPENPYXL`. | REQUIRED FOR ROUTING AUTHORITY; the classifier's work must not be omitted in a proposed product treatment without equivalent proof. |
| Negative path | Write `setup.json` with `REFERENCE_FAST_PATH`, decision and issues; return from `sitecustomize`. No artifact lookup, SHA, direct decoder, certificate, runtime import, proxy install, or `openpyxl.load_workbook` patch. | PRODUCT CONVENIENCE for setup receipt; ordinary reference semantics REQUIRED FOR PROCESS CONTRACT. |
| User script | Normal script `import openpyxl` and normal `load_workbook`; real workbook, worksheet and cell objects. Script stdout/stderr are inherited, not captured and re-forwarded. | REQUIRED FOR PROCESS CONTRACT. |
| Target exit / observer survival | `waitpid`; retain raw exit/signal, then take a second bounded XLSX snapshot and compare bytes. Changed files invoke the existing Python capture helper; unchanged files get `capture.json` containing `[]`. | REQUIRED FOR EFFECT ASSURANCE; REQUIRED FOR PROCESS CONTRACT. |
| Final receipt / exit | Write `observer_receipt.json` and `last_run.json` (plus optional private pointer); propagate target status or signal. | REQUIRED FOR EFFECT ASSURANCE for a durable outcome; exact JSON/layout is PRODUCT CONVENIENCE. |

The default negative route's notable files are `context.txt`, `setup.json`, `capture.json`, `observer_receipt.json`, and `last_run.json` inside a per-invocation run directory. The observer and target are the only normal processes for an unchanged workbook. The capture helper is conditional on changed bytes. No read-engine artifact is created.

## Frozen 22 reasons for reference routing

Every row below is a negative result of the maintained classifier on the exact frozen script source. These are mechanistic reasons, not performance choices. Multiple blockers may apply; the table shows the primary reported reason.

| Workload | Primary classifier reason |
|---|---|
| `Debugging_01_04__542f8461a344` | `WORKBOOK_WORKSHEETS_BOUNDARY` |
| `Debugging_02_06__7252ca64cf1c` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_02_06__88edc6528ef0` | `STATIC_ANALYSIS_UNCERTAINTY` |
| `Debugging_04_07__62a7766ef582` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_05_02__f274eaa3cc8e` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_09_03__0828d4dfbd13` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_09_03__59822a6e11e7` | `RICH_OBJECT_BOUNDARY` |
| `Debugging_10_07__6dd8f6d3a4dd` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_10_07__e3a79d24091a` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_10_10__c7eca76e6646` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_02_05__90004332940a` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_02_05__c75ecb00f745` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_08_02__4ca3ae46295d` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_08_02__625ec1db4acb` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_15_03__64092e664e9b` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Template_06_02__85fab8c95cea` | `RICH_OBJECT_BOUNDARY` |
| `Template_06_02__c26a4c6508ba` | `RICH_OBJECT_BOUNDARY` |
| `Template_06_12__3d05a7ee874d` | `STATIC_ANALYSIS_UNCERTAINTY` |
| `Template_06_12__83f82ce3f62b` | `STATIC_ANALYSIS_UNCERTAINTY` |
| `Template_15_01__fa75e25f6a90` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Template_15_03__5ad5663409d0` | `STATIC_ANALYSIS_UNCERTAINTY` |
| `Template_15_03__68f4733f2576` | `CELL_OBJECT_ITERATION_BOUNDARY` |

## Causal question left by static inspection

Static inspection proves that reference-only commands avoid direct artifacts and proxies, but it cannot assign the remaining wall excess among observer startup/snapshots/receipts, the guarded Python startup, config/classifier, and the native launcher. The planned P0–P4 full-command ladder isolates these increments. Existing internal observer timers are diagnostic only; they do not provide additive causal savings.
