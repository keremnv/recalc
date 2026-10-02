# Phase 10 product integration report

Status: **INTEGRATION IMPLEMENTED — VALIDATION BLOCKED**. The maintained implementation passed the tested semantic, cache, install, and assurance gates. It did not meet the preregistered reference-only transparency budget. This report concerns the local integrated implementation; it is neither a release verdict nor authorization for public speed claims. Phase-1–9 evidence and public presentation files were left unchanged.

## RESEARCH ARCHITECTURE CARRIED FORWARD

The integration carries forward the earned architecture: ordinary Python/openpyxl script source; conditional direct OOXML read serving under positive admission; a user-scoped persistent derived artifact; reference openpyxl fallback; and an external observer that survives target termination. Negative admission leaves the direct runtime inactive. The narrow semantic contract, hardened terminal merged-cell certificate, source freshness, and experimental populations were not widened or selected anew.

## INDEPENDENT PRODUCTION ARCHITECTURE REVIEW

[The architecture plan](PRODUCT_INTEGRATION_ARCHITECTURE_PLAN.md) was written before maintained module edits. For a maintained product, I chose one real script interpreter plus a small external observer, with admission and read state owned by the script process. The observer owns process status and effects, not spreadsheet semantics. I rejected direct transplantation of the research observer's unbounded in-memory snapshots, generic failure handling, workspace paths, and research telemetry.

## WHAT WAS REUSED CONCEPTUALLY

The implementation retains the direct decoder's narrow typed values, positive whole-script admission, restricted merged-cell proof, guarded startup interposition, content-addressed persistent state, ordinary reference fallback, and pre/post effect observation. The Phase-9 pay-for-play route is retained: definite negative admission uses ordinary openpyxl without installing the direct runtime.

## WHAT WAS REENGINEERED

The maintained [read engine](src/librecalc_agent/read_engine/), [bootstrap](src/librecalc_agent/_bootstrap/sitecustomize.py), [runner](src/librecalc_agent/runner.py), native [observer](src/librecalc_agent/native/observer.c), and native [command launcher](src/librecalc_agent/native/launcher.c) were implemented under package ownership. Artifact limits, version binding, cache locking, atomic publication, private run directories, compact receipts, and explicit assurance failure policy were added. A native default `run` dispatcher avoids another Python CLI interpreter on the common command path; explicit configuration and administrative commands still use the Python CLI.

## WHAT WAS DROPPED AS RESEARCH SCAFFOLDING

The active runtime no longer creates benchmark arm ledgers, per-cell traces, or research timing profiles for users. It does not use the old openpyxl-read-only-to-broad-SQLite index path. Some `_frozen` compatibility and capture modules remain packaged as migration dependencies; unused legacy modules should be removed in a later compatibility cleanup, after release-impact review.

## PRODUCTION MODULE BOUNDARIES

CLI/config/diagnostics are separate from process launch, admission, read engine, artifact/cache, bootstrap, and capture. The native observer handles external process and file observation only. The target script process performs admission, direct artifact discovery/build/load, interposition, and fallback. The maintained boundaries and migration aliases are documented in [migration notes](PRODUCT_INTEGRATION_MIGRATION_NOTES.md).

## CACHE AND ARTIFACT POLICY

[The cache design](PRODUCT_CACHE_ARTIFACT_DESIGN.md) uses `$XDG_CACHE_HOME/librecalc-agent` or a user cache default, with persistent `read-engine/` state separate from `runs/` receipts. The artifact key binds whole-file source SHA-256 plus runtime, decoder, semantic-contract, and format versions. `JSONZ_MEMORY_V1` uses typed JSON/zlib, explicit envelope metadata, hashes, bounded sizes, full semantic validation in the serving process, no executable deserialization, per-key advisory build locking, fsync, and atomic publication. Corrupt, missing, stale, and version-incompatible entries rebuild. Cache size has per-artifact limits but no global quota or eviction policy yet.

The first scored implementation omitted runtime-version key binding. Its complete score remains in `product_integration_phase10/scored_v1/`. [Amendment 1](PRODUCT_INTEGRATION_VALIDATION_SPEC_AMENDMENT_1.md) pinned the bounded repair before the entire unchanged score was rerun. The final canonical ledgers correspond to the amended implementation.

## OBSERVER ARCHITECTURE

The packaged observer launches a genuine `python script.py`, inherits stdout/stderr, waits for raw target status, snapshots XLSX bytes before and after, runs the capture helper only when bytes change, and writes a final receipt. It survives `os._exit` and target signals. Snapshot bounds are 1,000 XLSX files and 512 MiB aggregate bytes. A target error does not suppress post-observation. The [failure policy](PRODUCT_OBSERVER_FAILURE_POLICY.md) separates target outcome from assurance outcome.

## PLATFORM AND PACKAGING POLICY

Initial implementation and local validation cover **Linux x86_64 only**. The Hatch build hook compiles the native observer and default command launcher into a platform wheel. A clean wheel install required no manual compilation. macOS and Windows need platform-specific observer implementations and process-semantic validation; the local wheel is not a manylinux certification. Details are in the [platform note](PRODUCT_PLATFORM_PACKAGING_POLICY.md). The package version and public RC were not advanced.

## REFERENCE ONLY FAST PATH

Negative admission does not install the interposition or construct/read direct artifacts; the script uses ordinary openpyxl. The external observer remains present for effects. This preserves the intended asymmetric architecture, but the full-command reference-only cost remains measurable in this environment.

## DIRECT READ PATH

Positive admission activates the narrow direct OOXML decoder and persistent artifact. Direct construction and serving do not call `openpyxl.load_workbook`; the reference parser remains available for unsupported behavior. Artifact `REUSED` requires integrity validation and actual direct contact. The second source SHA check protects the bootstrap-to-first-load interval. This is workbook-parser independence, not complete independence from openpyxl utility modules.

## MERGED CELL CERTIFICATE

The Phase-8A restricted positive proof was carried into the maintained runtime. Zero recognized calls do not imply certification. Unknown or indirect object-access syntax routes to reference handling. The three historically targeted terminal scalar cases remain directly served in the fixed-22 oracle comparison. The certificate was not broadened during integration.

## REFERENCE FALLBACK

Unsupported load modes or proxy operations lazily invoke normal openpyxl, without replaying script logic. Fallback reasons are recorded. The representative workbook-iteration fallback remains a measured double-work case; it was deliberately not optimized in Phase 10. An optional-engine failure loses acceleration where ordinary reference execution can proceed.

## PROXY SEMANTIC LIMITS

The direct contract is ordered sheet names and literal lookup, worksheet bounds/dimensions and literal/integer cell access, and cell value/data type. It does not promise rich openpyxl object equivalence. Type, repr, identity, parent worksheet identity (including `cell.parent is ws`), styles, arbitrary object escape, writes, and broad workbook iteration require reference handling or remain known unsupported observations under the narrow contract. No broad read-exactness or openpyxl-equivalence claim follows.

## EFFECT CAPTURE AND FAILURE POLICY

The observer compares package bytes and invokes the Python capture helper on changes for package-level delta and mechanical validation. It does not judge task correctness or accelerate writes. A helper failure records `ASSURANCE_STATUS=FAILED`; a successful target then yields command status 125, while a failed target retains its own status and the separate assurance failure remains visible. A missing observer or inaccessible run/cache directory blocks before script launch. Explicit capture disabling records `NOT_REQUESTED` instead of implying validation.

## PRODUCT DIAGNOSTICS

[The compact receipt schema](PRODUCT_RECEIPT_SCHEMA.md) reports route, artifact state, direct contact, fallback reason, target exit/signal, assurance/capture status, and failures. Research timing and JSONL events are not part of user-facing diagnostics. The `status` command reads the latest private receipt.

## CLEAN INSTALL VALIDATION

The clean-environment wheel check passed: native command and observer were installed and executable; `doctor`, `example`, `run`, and `status` completed; first direct run reported `BUILT` and the next reported `REUSED`. The result is in [install results](../history/product_integration_phase10/install_results.json). Maintained product/process tests passed **27/27**, including real `__main__`, argv/path, exit, atexit write, abrupt termination, subprocess, inherited descriptor, and caught SIGINT checks. Test evidence is in [test results](../history/product_integration_phase10/test_results.json).

## FAILURE INJECTION

[Failure results](../history/product_integration_phase10/failure_injection.json) passed for corrupt, truncated, missing and stale artifacts; malformed workbook reference behavior; cache path/permission denial; missing observer; capture-helper failure; and observer child-launch failure. Artifact defects rebuilt; unlaunchable assurance infrastructure failed visibly. These are bounded local injections, not a comprehensive hostile-input audit.

## CONCURRENCY AND CACHE PUBLICATION

Two simultaneous invocations against the same source both completed and directly served; one observed `BUILT`, the other `REUSED`, and the final artifact validated. [Concurrency results](../history/product_integration_phase10/concurrency_results.json) and [upgrade invalidation](../history/product_integration_phase10/upgrade_invalidation.json) also show new keys/rebuilds for runtime, decoder, contract and format changes. Distributed caches, many-process stress, and global eviction remain untested.

## ORACLE PARITY

The complete amended PY/frozen-Phase-9-EXP/PROD validator produced **543/543 valid correctness rows**, **1,629 raw timing rows**, and **120 session rows**. Route, artifact, fallback and assurance parity held in all 543 rows. The raw Phase-3 comparator labeled 481 EXP/PROD rows exact, 60 volatile-only, and two changed-file rows as byte-state differences. For those two changed-file rows, the preregistered Phase-8 package-parts comparison normalized only volatile `docProps/core.xml` modified-time metadata and passed. No rows were dropped or relabeled in the raw ledger. See [oracle parity](../history/product_integration_phase10/oracle_parity.json), [correctness ledger](../history/product_integration_phase10/correctness.jsonl), and [validator](../history/product_integration_phase10/validate.py).

## FIXED 22 REGRESSION

All exact historical contact-selected identities retained direct contact and passed semantic/routing gates. On second invocation, PROD/PY median paired ratio was **0.468**, with **18/22 faster**, median signed difference **−307.4 ms**, and a workload-bootstrap median interval **[0.313, 0.688]**. PROD/EXP median was approximately **0.985**. Cold PROD/PY median was **1.121**; cold speed remains unsupported. These are contact-selected results, not a representative product claim.

## REPRESENTATIVE 30 CORRECTNESS

All 30 frozen scripts passed the preregistered semantic comparator. Routes matched the frozen experimental architecture: **22 reference-only, 7 direct-contact, 1 fallback-after-contact**. The population covers 21 tasks and is a fixed product-boundary view, not a market-prevalence estimate.

## REPRESENTATIVE 30 PERFORMANCE

On second invocation, all-30 PROD/PY median paired ratio was **1.044**, geometric mean **0.903**, median signed excess **+16.0 ms**, and **5 faster / 25 slower**. The geometric mean reflects large wins on several contact scripts while the median captures the majority reference-only tax; neither alone describes the distribution. Same-run PROD/EXP was near parity on the route views. [Analysis](../history/product_integration_phase10/analysis.json) retains per-workload rows, bootstrap intervals and task sensitivity.

## REFERENCE ONLY TRANSPARENCY

For the 22 reference-only scripts, second-invocation PROD/PY median was **1.050**, geometric mean **1.053**, interval **[1.029, 1.064]**, **0 faster / 22 slower**, and median signed excess **+18.85 ms**. This **fails the preregistered +10 ms practical budget**. Same-run PROD/EXP median was about **1.009**, so the migration preserved much of the experimental path, but that does not satisfy the product budget. Historical Phase-9 +8.73 ms and current same-run results differ; the fixed rule was not revised after observation.

## DIRECT CONTACT PERFORMANCE

For seven representative direct-contact scripts with valid reuse, PROD/PY second-invocation median was **0.608**, **5/7 faster**, median signed difference **−121.9 ms**. PROD/EXP median was **0.979**, below the preregistered 1.10 migration-regression flag. The workload-bootstrap interval **[0.307, 1.011]** reflects the small clustered view; this supports preserved mechanism benefit, not a broad speed claim.

## CHANGED FILE ASSURANCE

All five frozen write fixtures passed final package/effect and capture validation. Full-command PROD/PY median ratio was **1.599** with median excess **+107.7 ms**; PROD/EXP median was **1.003**. This is charged assurance overhead, not write acceleration. The raw byte comparator caveat for two fixtures is resolved only by the frozen package-parts rule described above.

## ABRUPT EXIT ASSURANCE

Dedicated process fixtures changed a workbook before `os._exit` and SIGTERM. The external observer survived, found the change, ran the helper, wrote a passing capture/receipt, and retained target exit/signal classification. Caught SIGINT, atexit mutation, inherited FD and normal exception/SystemExit behavior were also exercised in the 27 passing tests. This validates the tested Linux process contract, not all native-crash or platform variants.

## COLD AND SESSION ECONOMICS

All-30 cold PROD/PY median was **1.040**; fixed-22 cold was **1.121**. Cold acceleration is unsupported. Observed all-30 session median ratios were **1.044, 1.030, 1.053, 1.046** for N=1,2,3,5 respectively. Direct-contact sessions improved to **0.865, 0.698, 0.661** for N=2,3,5, while reference-only sessions remained around **1.03–1.06**. Each session started without an artifact and charged all command launches; no horizon was extrapolated.

## KNOWN REMAINING PRODUCT RISKS

The blocking economic risk is the repeatable reference-only full-command tax beyond the frozen practical budget. Other release risks include Linux x86_64-only packaging, absence of a global cache quota, prototype-scale observer file-count/byte bounds, symlink/permission and concurrent-mutation corner cases beyond tested injections, observer failure before a durable receipt, and retained compatibility modules. The direct semantic surface remains intentionally narrow. Explicit-config commands take a slower Python CLI path. The five changed-file cases show substantial but understood assurance cost. No public speed, cold, write-acceleration, cost, token, or broad-equivalence claim is justified here.

## PRODUCT INTEGRATION VERDICT

**`INTEGRATION IMPLEMENTED — VALIDATION BLOCKED`**. The architecture survived migration on the tested semantic, assurance, route, cache, install and direct-contact boundaries. The preregistered reference-only transparency criterion did not pass: +18.85 ms versus the +10 ms budget. The integrated implementation must therefore not be called fully validated or released on the strength of these measurements.

## AGENT INDEPENDENT MAINTAINER OPINION

I would keep the real script interpreter, external survivor, pay-for-play admission, and content-addressed direct state. I would not copy research ledgers, arm terminology, or unbounded snapshot behavior into product code. The first engineering issue I would investigate is the current reference-only full-command tax using same-run attribution, because 22/30 representative scripts cannot benefit from read substitution and the fixed budget missed by about 8.85 ms. I would not trade away effect observation to erase that cost. Separately, I would harden platform packaging, global cache lifecycle, and observer receipt durability before release.

## POST INTEGRATION RESEARCH HANDOFF

[The backlog](POST_INTEGRATION_RESEARCH_BACKLOG.md) records derived-information ideas separately. Formula-error feedback, temporal/output-role evidence, context projection, and wider model-facing derivations were not begun in this integration. Public claim registry and presentation remain paused pending a separate decision.

## NEXT STEP

Run one preregistered causal attribution/replication experiment on the unchanged representative reference-only population and full-command boundary to isolate the remaining assurance-wrapper tax; keep the direct path, observer contract, and capture unchanged. Then decide whether a bounded product change or a revised, explicitly justified product budget is warranted. Public claims and release work remain separate.
