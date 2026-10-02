# Evidence and limitations — recalc-agent 0.2.0rc3

Measurements below were established on `0.2.0rc2`. `0.2.0rc3` is a rename
and release-hygiene candidate only: it changes product identity, licensing,
and release surfaces without changing the validated mechanism, so the rc2
evidence stands for rc3.

Concise technical boundary for users who care about implementation guarantees.
Research-oriented readers: full ledgers live in `research/history/product_integration_phase10/`,
`research/history/product_integration_phase10b/`, `research/history/product_hygiene/`, and `research/history/phase10c_audit/`.

Validation host for the cited runs: Ubuntu 26.04.1, kernel 7.0.0-34, Intel
Core Ultra 5 125H, CPython 3.13.12, openpyxl 3.1.5.

## Established

- **Ordinary Python/openpyxl interface.** `run` launches the unchanged script
  in a real interpreter. 543/543 oracle rows show exit/stream/state parity
  with plain Python; process-identity fixtures cover argv, cwd, `__main__`,
  streams, atexit, subprocesses, inherited FDs, and caught SIGINT.
- **Conditional narrow direct reads.** Whole-script static admission routes
  uncertain scripts to ordinary openpyxl without loading the direct runtime
  (audited: no proxy, no artifact lookup, no direct state). Admitted scripts
  get a narrow surface (sheet names, bounds, literal cell access, value/data
  type); the merged-cell certificate covers only a closed terminal-scalar
  grammar.
- **Reference fallback.** Unsupported load modes, proxy escapes, iteration,
  and artifact/decoder failures lazily use real openpyxl and are recorded in
  the receipt. Representative fallback-after-contact behavior is covered.
- **Persistent derived state.** Content-addressed artifacts (`JSONZ_MEMORY_V1`)
  keyed by whole-file SHA-256 plus runtime/decoder/contract/format versions,
  validated before serving, published atomically under a per-key lock.
  Corrupt/missing/stale/incompatible entries rebuild; a second source hash at
  first load closes the bootstrap-to-script race.
- **External process observation.** A native parent launches and waits for the
  script process, survives tested abrupt exits (`os._exit`, SIGTERM), and
  records raw exit/signal status separately from assurance status.
- **Tested changed-file capture.** Five frozen write fixtures: exact package
  relation, changed-XLSX detection, mechanical validation and delta replay.
  Full-command cost on those fixtures was ~1.6× plain Python — charged
  assurance overhead, not acceleration.
- **Tested Linux installation/process behavior.** Clean wheel install
  (native launcher + observer executable; doctor/example/run/status green;
  BUILT then REUSED), 27+ maintained tests, bounded failure-injection battery
  (corrupt/truncated/missing/stale artifacts, malformed workbook, cache
  denial, missing observer, helper failure, launch failure).

## Conditional measurements (host/run-sensitive, not portable)

- **Reference-only overhead.** Fixed 22-script set, second invocation:
  +18.85 ms median unpinned (Phase-10, archived) vs +6.39 ms median
  [5.63, 9.71] CPU-pinned (Phase-10B) on the same host. Same code, different
  run protocol — timing is host identity, never averaged across hosts.
- **Direct-contact speedups.** Warm reuse only: median 0.608× vs plain Python
  on 7 frozen representative direct-contact workloads; 0.468× on the fixed-22
  contact-selected set. Small clustered views; cold runs show no benefit
  (1.04–1.12×); the all-30 representative median is 1.044 (5 faster/25 slower)
  because most scripts are reference-only by design.

## Not claimed

Universal speedup; cross-host timing guarantees; cold acceleration; write
acceleration; token/model-cost savings; benchmark-score improvement; task
correctness or output certification from capture; broad openpyxl equivalence.
