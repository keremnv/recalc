# Product integration architecture plan

Status: Phase-10 implementation plan, written before changes to maintained `src/librecalc_agent` modules. The Phase-1–9 reports and experimental code are frozen oracles. This plan is not a release or public claim decision.

## Independent maintainer opinion

I would maintain one real Python script process and a minimal external survivor. The observer should own process status and pre/post effects; the script process should own admission, freshness, direct artifact construction/load, interposition and ordinary openpyxl fallback. A negative admission decision should leave openpyxl untouched. Persistent state belongs in a user-scoped content-addressed cache, separate from run receipts. The script remains byte-identical Python.

I would **not copy the research `observer.c` directly**: it accumulates all workbook bytes in RAM, has research-root paths and hard-coded process arguments, and its failure policy is a generic `die(125)`. I would also not ship research JSONL event streams or profiling. The research `Runtime` abstraction should become simpler: one process-local route and one compact receipt, with no parent/child semantic handoff or global research arm.

## Component disposition

| Component | Disposition | Production reason |
|---|---|---|
| Thin native observer and external-survivor architecture | REUSE CONCEPT; REENGINEER | Preserve real script semantics and abrupt-exit observation, but harden paths, resource limits, status and receipt durability. |
| Observer snapshots | REENGINEER | Keep pre/post XLSX comparison and capture inputs; bound count/bytes and make failures explicit. |
| Guarded `sitecustomize` | REUSE CONCEPT; REENGINEER | Script identity guard and ordinary `python script.py`; package-local context and compact setup receipt. |
| Frozen whole-script admission | COPY WITH HARDENING | Keep its accepted positive/negative decisions; remove research names from public diagnostics, not its proof behavior. |
| Phase-8A merged-cell certificate | COPY WITH HARDENING | Restrictive positive grammar, zero-call rejection, fail-closed unknown syntax; retain exact algorithm for parity. |
| Direct OOXML decoder | COPY WITH HARDENING | Preserve narrow Python-level values/types; add ZIP/XML and artifact resource bounds around the same semantics. |
| MemoryBook/proxies/read runtime | REENGINEER | Keep supported read surface and lazy reference fallback; integrate merged terminal route without global monkeypatch of a research class. |
| `JSONZ_MEMORY_V1` artifact concept | REUSE CONCEPT; REENGINEER | Keep typed deterministic schema and version/hash binding; bounded decompression and atomic publication. |
| Source hashing and persistent cache | REENGINEER | User-scoped cache, content/version key, atomic concurrent publication and source recheck before serving. |
| Reference-only fast path | REUSE CONCEPT | Negative admission does not import/install direct machinery. |
| Capture helper and package delta | COPY WITH HARDENING | Keep mechanical capture and validation; package-local helper and explicit assurance failure status. |
| Phase-6/9 run directories and large profiles | RESEARCH ONLY | Replace with one compact product receipt plus capture detail only when changed. |
| Benchmark ledgers, phases, arm names, timers | DROP from product | Remain in experimental evidence, not user-facing runtime. |

## Maintained module/API boundary

| Module | Internal API / responsibility |
|---|---|
| `cli`, `config`, `diagnostics`, `runner` | Stable `run`, `example`, `doctor`, `status`; config resolution, observer launch and last receipt. |
| `admission` | Re-export/own frozen whole-script classifier and restricted merged certificate. A negative result is authoritative only for bypass of *this* direct runtime. |
| `read_engine.decoder` | `decode_xlsx(path) -> MemoryBook` for the earned narrow contract; no `load_workbook`. |
| `read_engine.artifact` | Versioned deterministic encoding/decoding, validation and cache `ensure`/`load`; no executable deserialization. |
| `read_engine.runtime` | Install per-process `load_workbook` interposition only for admitted scripts; narrow proxies and lazy real fallback. |
| `_bootstrap.sitecustomize` | Verify exact script/context, route negative sources to ordinary Python, activate admitted direct runtime, write compact route state. |
| `observer` and native command dispatcher | Package-owned native survivor and default `run` launcher; no spreadsheet semantics. Complex CLI/config parsing remains in Python. |
| `effects`/`_capture_helper` | Package-level pre/post effect delta, validation and helper outcome. |
| `receipt` | One invocation record with separate target and assurance status. |

No new model-facing API, task IR, DSL, source rewrite or `runpy` path is planned.

## Platform and package policy

Initial integrated observer support is **Linux x86_64**, the tested research platform. macOS and Windows remain explicit unsupported scopes until their observer/process semantics are implemented and tested. A build hook compiles the small native observer into a platform wheel; users do not compile it manually. Source distributions contain the C source and build hook, so wheel builders compile it. `doctor` reports observer availability and platform support. No cross-platform claim follows from Linux validation.

## Cache and trust policy

Default cache is the existing user-scoped `~/.cache/librecalc-agent` or `$XDG_CACHE_HOME/librecalc-agent`. Persistent content-addressed artifacts live in `read-engine/`; invocation receipts live in `runs/`. Key binds whole-file source SHA-256, decoder version, semantic-contract version and artifact-format version. Readers validate size, magic, identity, whole-artifact and payload hashes, schema and typed values. Builders publish temporary files with fsync then atomic rename, under a per-key advisory lock on supported Linux; a racing reader must either see a fully valid generation or fall back/retry. No run-directory artifact is authoritative. Corruption, incompatibility or stale source cause rebuild; if build/load fails, use reference openpyxl for that load where safe. Successful direct serving rechecks source SHA at first load to close the bootstrap-to-script race.

Resource ceilings are part of direct admission to the optional engine: ZIP member count, declared and actual expansion, XML size/depth, artifact compressed/uncompressed size, sheet/cell count and string lengths. A direct-path resource rejection routes to reference; it does not veto the user's script merely because the optimization cannot run. Cache cleanup is manual/status-visible in this phase; no unsafe implicit eviction. Version upgrades naturally invalidate keys. Cache and run directories use user-only permissions; symlinked/untrusted cache paths are rejected for direct use.

## Observer and failure policy

The observer launches a genuine `python script.py` process, inherits stdout/stderr and the documented descriptor policy, waits for raw exit/signal, takes post-state after atexit, then invokes the package capture helper only for changed XLSX bytes. It records target and assurance outcomes separately. A target failure must not suppress post-observation. An assurance failure must be recorded distinctly and produce an explicit command-level failure/diagnostic policy; target files are never silently repaired or rerun. A missing/unlaunchable observer blocks an assurance-enabled invocation before the script runs with an explicit error; silently running without the promised external observer would be unsafe. An explicit disabled-runtime invocation remains ordinary Python. Observer self-failure, disk-full or failed receipt is a visible assurance failure. This policy will be checked with failure injection before a validated verdict.

## Migration and validation sequence

1. Implement decoder/artifact/cache with oracle parity and hostile-input limits.
2. Integrate admission/certificate, process-local runtime and reference-only branch; test supported/unsupported observations.
3. Package the native observer and capture helper, then connect the existing CLI and compact receipt.
4. Gate process/assurance, cache invalidation/concurrency/failure cases and clean installation.
5. Hash a separate validation spec before PY/EXP/PROD scored full-command comparisons on the fixed 22, representative 30, five changed-file fixtures and process cases.

The score may fail. No benchmark-specific route or threshold will be added during implementation to recover a favorable result. Public claims and presentation remain unchanged.
