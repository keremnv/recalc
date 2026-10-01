# Phase 9 reference-only architecture review

Status: independent pre-treatment inspection. Sources are the frozen Phase-8A raw/profile ledgers, Phase-8A bootstrap, Phase-3 runtime, frozen classifier, and Phase-6 native observer. Diagnostic import probes were unscored and did not run the 30-workload protocol.

## Actual loss boundary

The Phase-8A script process enters guarded `sitecustomize`, reads the launch context, verifies `sys.argv[0]`, imports configuration, classifier, parent artifact validator and merged certificate, reads/classifies the script, then imports `merge_runtime` and `Runtime`, imports real `openpyxl` in `Runtime.install`, patches `load_workbook`, and registers runtime telemetry. **It does all of this even when classification has already returned `PREDECLARED_REAL_OPENPYXL`.** Runtime then delegates each load to the saved normal openpyxl function with `source_rejected_before_interposition`.

All 22 Phase-8A reference-only scripts have that exact classifier decision; none reaches artifact discovery, hashing or proxy serving. Their second-command median signed H1/PY excess was +22.0 ms (ratio 1.089). In the same rows, bootstrap profile medians were: `pre_runtime` 21.94 ms; config/classification 0.84 ms within that startup/import region; runtime import/install 91.11 ms; total bootstrap 113.26 ms. Observer pre-snapshot, post comparison and empty receipt medians were 0.11, 0.26 and 0.13 ms; its target wait was about 303 ms. Nested medians are not additive. In isolated fresh-process import probes, normal `openpyxl` import was about 155 ms external wall and `Runtime`/merge imports about 165 ms, so the 91 ms runtime phase is **not** a 91 ms removable full-command saving: the script still imports real openpyxl when it executes.

| Cost on rejected script | Classification | Evidence / disposition |
|---|---|---|
| Real Python script process, ordinary openpyxl execution | UNAVOIDABLE FOR ASSURANCE / reference semantics | Required unchanged interface and genuine script process. |
| Native observer, pre/post XLSX observation, wait, receipt, changed-file helper on mutation | UNAVOIDABLE FOR ASSURANCE | Phase-6 observer survives script death; keep byte-for-byte. |
| Guarded `sitecustomize` entry and script/context identity | UNAVOIDABLE TO DECIDE ROUTE | Prevent unrelated Python children receiving the injected runtime. |
| Config read and unchanged whole-script classifier | UNAVOIDABLE TO DECIDE ROUTE in the selected design | The classifier gives an authoritative negative decision before artifact work. |
| Parent artifact module, merged certificate, direct runtime/proxy modules, early real-openpyxl import/patch | DIRECT-PATH-ONLY | Imported even for the 22 rejected scripts; first removable category. |
| Run setup JSON, detailed runtime event/profile writes | RESEARCH/PROTOTYPE OVERHEAD, with some necessary diagnostic content | Keep enough experimental witness to establish route and assurance; avoid claiming unobserved reference-call counts. |
| Interpreter and module shutdown residual | UNKNOWN | Full-command A/B, not timer subtraction, must measure effect. |

## Why the 22 scripts are reference-only

The table is derived afresh from the **unchanged classifier** on each frozen script, not used as a treatment lookup. Full blocker lists and per-script diagnostic profiles are in [reference_only_diagnostics.json](reference_only_diagnostics.json).

| Workload | Authoritative primary blocker |
|---|---|
| `Template_15_03__5ad5663409d0` | `STATIC_ANALYSIS_UNCERTAINTY`: dynamic worksheet subscript |
| `Template_06_12__3d05a7ee874d` | `STATIC_ANALYSIS_UNCERTAINTY`: dynamic worksheet subscript |
| `Template_06_12__83f82ce3f62b` | `STATIC_ANALYSIS_UNCERTAINTY`: dynamic worksheet subscript |
| `Template_15_03__68f4733f2576` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Template_15_01__fa75e25f6a90` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Template_06_02__c26a4c6508ba` | `RICH_OBJECT_BOUNDARY` |
| `Template_06_02__85fab8c95cea` | `RICH_OBJECT_BOUNDARY` |
| `Financial_Model_08_02__4ca3ae46295d` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_15_03__64092e664e9b` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_02_05__c75ecb00f745` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_02_05__90004332940a` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Financial_Model_08_02__625ec1db4acb` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_05_02__f274eaa3cc8e` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_09_03__0828d4dfbd13` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_10_07__6dd8f6d3a4dd` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_09_03__59822a6e11e7` | `RICH_OBJECT_BOUNDARY`: defined names |
| `Debugging_02_06__7252ca64cf1c` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_04_07__62a7766ef582` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_10_07__e3a79d24091a` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_10_10__c7eca76e6646` | `CELL_OBJECT_ITERATION_BOUNDARY` |
| `Debugging_02_06__88edc6528ef0` | `STATIC_ANALYSIS_UNCERTAINTY`: dynamic worksheet subscript |
| `Debugging_01_04__542f8461a344` | `WORKBOOK_WORKSHEETS_BOUNDARY` |

Counts: 14 cell-object iteration, four static uncertainty, three rich object, one worksheet collection. Each was rejected before direct artifact discovery in Phase 8A. The five fixed write fixtures are also classifier-rejected by the unchanged write boundary.

## Architecture alternatives

- **Early definite-reference bypass:** after the existing classifier rejects, leave real openpyxl untouched and skip certificate, artifact and runtime imports/install. This has the earliest existing authoritative negative point and the smallest semantic surface. Selected for a causal test.
- **Lazy heavy bootstrap / first-contact activation:** a small loader hook could defer the decision until a load call. All 22 scripts do call normal openpyxl, so the classifier still must run; an import hook would add module identity and monkeypatch risk without removing this particular decision cost. It has value for scripts with no load, but this fixed population does not test that case.
- **Import-time deferred interposition:** would alter the successful direct path and import order. The frozen negative classifier decision already supplies a simpler boundary.
- **Admission-result persistence or native observer classification:** could avoid future classifier startup, but introduces a new cache/trust contract or makes the observer heavy. It would confound the single-change experiment and is deferred if the simple bypass fails the practical budget.

The observer remains necessary regardless of read route. The product ownership question is whether **only the thin observer** is always present while direct acceleration imports/install are conditional. Phase 9 measures the first, low-surface version of that design.
