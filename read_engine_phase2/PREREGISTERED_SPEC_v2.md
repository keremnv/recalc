# Read Engine Phase 2 preregistration — v2

Status: v2 implementation amendment, frozen and hashed before the complete scored rerun. The original v1 spec remains unchanged. No product or Phase-1 file may be changed.

## Amendment from v1 (before full benchmark results)

The v1 correctness gate completed successfully (51/51 traces; 38/38 loadable full-cell books; one known oracle-unavailable book), and four invalidation rows passed. During early construction timing, before the benchmark reached the known malformed-oracle workbook, review found that the P0 child would raise on that workbook and abort the entire run. This is a runner error-handling defect, not a decoder or population finding. The  v1 scored timing rows are preserved in `v1_partial/` and excluded from v2 analysis.

The v2 child records `REFERENCE_ORACLE_UNAVAILABLE` for P0 construction on the known workbook, with no valid P0 ready-time measurement. All 39 workbooks still receive P1/P2/P3 BUILD rows; P1/P0 BUILD pairs are reported only for the 38 reference-loadable workbooks. No other variant, timing boundary, artifact, source identity, trace, freshness rule, or order changes. The full correctness gate and all scored timing rows restart under v2; no v1 rows are mixed into v2 conclusions.

## Identity and environment

- Baseline commit `254a5c14fa74fc3534493c565de84b38e7317175`, tree `dc7ae5512e4d47e56663564ad72b7a18600bbf5c`. Local Phase-2 files are new and excluded from that baseline identity.
- Frozen Phase-1 decoder: `read_engine_phase1/prototype.py`, SHA-256 `a6e95f1503ec6090d6176065471372924bf447f907a2a428faceee12a2f72473`. Import its `decode_xlsx`, `MemoryBook`, `SQLiteBook`, `SQLiteSink`, and `canonical`; do not edit it. Phase-1 `build_r3` is the semantic/storage baseline, while Phase-2 publication adds metadata and durability around the same sink and decoder.
- Frozen population: byte-identical copy of `read_engine_phase1/population.json`, SHA-256 `6492d1cbc2163ea252c0d34cf346171d332a923bd5f05fc1fd54c3e851097afa`. Archived trace source `candidate_a_a1_checkpoint_rerun_01/contact_traces.jsonl`, SHA-256 `665244f6150dfbb74ae647dfc8a7b8b034c02794f6de9cf7419f6d56da41696f`.
- Python 3.13.12 (`/home/kerem/miniconda3/bin/python`), openpyxl 3.1.5, lxml 6.1.3, SQLite 3.51.1; Linux x86_64 kernel 7.0.0-31-generic, Intel Core Ultra 5 125H, 18 logical CPUs. Record actual machine metadata in results too. No CPU pinning, dropped filesystem caches, or claim of cold-disk measurement.

## Frozen populations and contract

- Construction and freshness: all 39 unique Phase-1 workbook SHA-256 identities in their population-file order, including `71233a0b02e0680361836392ca41c567aae657ce91dd24c4248f273f459fd53c` whose normal-openpyxl oracle fails on malformed core-properties XML. Use its construction/freshness rows but mark semantic oracle `REFERENCE_ORACLE_UNAVAILABLE`.
- Reusable sessions: all 51 archived exact traces in their population-file order; seven source snapshots. No filtering or ranking after timings. Load each trace by `trace_id` from the frozen JSONL and verify snapshot SHA-256.
- Exactly Phase-1 contract: ordered `sheetnames`, literal sheet lookup, worksheet `max_row`, `max_column`, calculated `dimensions`, literal coordinate lookup and integer `.cell(row,column)`, cell `.value` and `.data_type`; `data_only=False`. Phase-1 canonical comparison preserves scalar Python types, date/time, shared/array/data-table formulas, merged cells, errors and bounds. Writes and rich APIs excluded.

## Variants and format

- **P0**: each fresh invocation calls normal `openpyxl.load_workbook(source, data_only=False)`, executes trace, closes. No artifact or source hash for execution; corpus BUILD comparator is reference load only.
- **P1**: each fresh invocation calls frozen `decode_xlsx` into `MemoryBook`, executes trace, closes; no artifact or source hash. Corpus BUILD is decode-to-ready only.
- **P2**: frozen direct decoder + Phase-1 minimal SQLite schema (`sheets`, `cells`); add only `artifact_meta(key TEXT PRIMARY KEY,value TEXT)` with format, decoder, contract, source SHA. One SQLite connection read-only on reuse. No source required after attach for frozen reads.
- **P3**: frozen direct decoder + pickle protocol 5 of the `MemoryBook` after clearing its nonsemantic timing `profile`; envelope includes format, decoder, contract, source SHA and book. Fully deserialized on reuse. **EXPERIMENTAL_TRUSTED_CACHE_FORMAT — NOT A PRODUCT SAFETY DECISION.** Only benchmark-created trusted cache roots may be unpickled, after sidecar/hash validation.
- No fourth arm. Format versions `P2_SQLITE_V1`, `P3_PICKLE_V1`; decoder ID is the above Phase-1 SHA, contract ID `PHASE1_NARROW_V5`.

## Identity, discovery, freshness and publication

- **F1 only**: every P2/P3 process computes SHA-256 over all source bytes before discovery or reuse. No F2 metadata shortcut: ordinary path/mtime/size cannot fail-closed detect arbitrary byte changes. P0/P1 have no persistent artifact and therefore do not hash for freshness; this is an intentional comparator asymmetry.
- Deterministic key: SHA-256 of `source_sha256|decoder_id|contract_id|format_version`. Cache root is Phase-2 temporary storage, never the product cache. Artifact path is `<root>/<variant>/<key>.sqlite` or `.pkl`; sidecar `<artifact>.json`.
- Manifest contains key, identities/versions, source bytes, artifact bytes and artifact SHA-256. On discovery check exact manifest fields, artifact existence/size and full artifact SHA-256; P2 additionally checks internal `artifact_meta` and `PRAGMA integrity_check`, P3 checks envelope after validated deserialization. Any failure is a cache miss, never a stale hit. Record `BUILT` or `REUSED` with reason. Artifact SHA verification is charged to warm attach/discovery and reported separately.
- Build temporary artifact in same directory; complete writes and `fsync` file; `os.replace` to final path; `fsync` directory. Write/fsync temporary manifest, atomically rename it last and sync directory. A valid manifest is the publication marker. On invalid/missing artifact, rebuild from source (or surface source failure); do not serve stale data. Scored sessions start with private empty cache roots. No in-memory registry.

## Process model, endpoints and order

- Every measured invocation is a fresh `python` process. No Python book object survives. OS filesystem cache is allowed and uncontrolled; label first observation separately.
- One scored 10-invocation session per trace and variant. The ten **observed cumulative prefixes** give N=1,2,3,5,10; each prefix starts at invocation 0 with empty per-session artifact state. P2/P3 invocation 0 must be `BUILT`, 1–9 must be `REUSED`, else session is invalid. P0/P1 independently parse/decode every invocation. Do not carry artifacts between sessions. Parent records exact cumulative wall time from first launch to each prefix exit; child records interior timings. Child emits one JSON result line after release.
- Variant order rotates deterministically by trace index (P0/P1/P2/P3 cyclic rotation); corpus BUILD order rotates by workbook index. Thus each variant occupies each order position approximately equally. No result-dependent reordering. One scored corpus BUILD observation per workbook/variant; this is labeled first observation under current OS cache. Session invocations provide repeated observations. Random seed `20260926` is fixed for bootstrap only. No filesystem-cache drop.
- **BUILD**: child timer from source identity/freshness start to ready representation/artifact. P0 normal load, P1 direct decode, P2/P3 hash + decode + storage + artifact hash/manifest publication. Benchmark staging excluded. For P2/P3 construction session, trace follows BUILD; attach is separately timed.
- **WARM ENGINE**: child timer from source freshness start to trace completion and handle release on a verified reused artifact. Includes source SHA, discovery, manifest/artifact validation, attach/deserialization and trace. For P0 analogous interior load+trace without SHA. P1 rebuilt interior reported in session, not called reused.
- **WARM PROCESS**: external parent timer from child launch to exit for invocation 1–9, including interpreter startup and output. Compare same invocation index of P0.
- **SESSION**: external parent cumulative wall time from first process launch to Nth process exit for N=1,2,3,5,10, compared to N independent P0 processes for the identical trace.
- Trace operation timer starts after book acquisition and stops before release. First lookup is separately timed by executing the first applicable trace operation, while preserving exact operation sequence. Child phase durations: source hash, manifest discovery, artifact hash, format validation, attach/load, first operation, remaining trace, close, publication, and total; unavailable components `UNMEASURED` rather than inferred. Process overhead is external wall minus child interior, labeled residual (includes interpreter startup, imports, telemetry and IPC).

## Correctness and lifecycle gates before timing conclusions

1. Verify preregistration hash, frozen decoder/population/trace hashes and all source workbook hashes. Guard P1/P2/P3 build and serving by patching both `openpyxl.load_workbook` entry points to raise.
2. From fresh processes, reopen P2/P3 artifacts and compare all 51 trace observable sequences against P0/Phase-1 canonical reference results. Also assert P1 exact replay. No mismatching persistent arm gets a speed claim.
3. For each of 38 normal-reference-loadable corpus books, compare reopened P2/P3 against reference for ordered sheet names, bounds and every Phase-1 nonempty cell, including `.value` and `.data_type`. Compare P2/P3 with each other. Keep the 39th separately oracle-unresolved. No silent sample.
4. Invalidation uses staged copies, never source fixture mutation. Fixed representatives: `1768dcc784d3c9bd2319dabeaa3a7c27d4bc0ab048a63c7084450abab3f3a1a2` (Template:02_01, 6,727 bytes) and `1b64bd5ac59b13beceb019da28ee25a8e12d479e14d625ce3ead88ccc344c741` (Financial_Model:02_04, 66,611 bytes). H2 is a byte-different, semantically different copy made by replacing one existing scalar cell in worksheet XML with another same-type scalar; chosen before timings, inspect exact edit in invalidation rows. Test H1 build, H1 reuse, H2 same-path build, restore H1 reuse, missing artifact rebuild, and truncated artifact rebuild per P2/P3. H1/H2 different keys must prevent stale service. No corruption timings are ordinary performance data.
5. Only after correctness/invalidation gates, run corpus BUILD and trace sessions. If persistent reopen mismatches, deterministic freshness fails, separate-process reuse fails, or identities/timing cannot be trusted, stop and report. If neither persistent arm beats P0 at measured meaningful horizons N=2,3,5,10, report negative evidence and add no representations.

## Analysis

- Preserve every raw row. Corpus BUILD: paired workbook ratios P1/P0, P2/P1, P3/P1, P3/P2. Trace WARM ENGINE/PROCESS: P2/P0, P3/P0 and P3/P2 on same trace/invocation; SESSION: P1/P0, P2/P0, P3/P0 for each N. Report median paired ratio, geometric mean, min/max, faster/slower/tied; 2,000 percentile bootstrap resamples of paired identities (seed above) where sensible. Summarize per trace and separately per seven source snapshots; no broad-population claim from trace bootstrap.
- Break-even is first **observed** N among 1,2,3,5,10 with session ratio below 1 for each trace; no extrapolation. Report count by arm and N, including never by N=10. N=1 and N=2 explicitly reported.
- Profile build, warm hash, artifact validation/load, trace, startup residual. Artifact bytes/source ratio per workbook, warm RSS after attach (Linux `ru_maxrss`, coarse process high-water mark), P2 file-backed and P3 fully loaded. Keep aggregate and workbook-specific analysis separate. Relate size to attach descriptively, without causal claim.
- Phase-1 evidence is carried forward, never recomputed as a new Phase-2 result. No public product-speed claim; these are offline mechanism sessions. Do not choose an integration candidate solely from a single headline.
