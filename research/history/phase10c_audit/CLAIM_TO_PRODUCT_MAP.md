# Claim-to-product map

For each plausible external claim: verdict, scope, denominator, implementation
version, strongest evidence, strongest limitation, recommended wording, and the
overclaim to avoid. Public materials are NOT updated in this phase.

Verdicts: SUPPORTED BY INTEGRATED PRODUCT / SUPPORTED ONLY HISTORICALLY /
SUPPORTED CONDITIONALLY / NOT SUPPORTED / NEEDS WORDING CHANGE.

## Architecture claims (implementation + correctness fixtures)

### Same ordinary Python/openpyxl program
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope/denominator: any script launched via `run`; verified on 543 oracle rows
  + process-semantics fixtures. Implementation: integrated observer + bootstrap
  identity guard.
- Strongest evidence: stream/exit/state parity; nested-interpreter test.
- Strongest limitation: untested with pre-existing user `sitecustomize`.
- Recommended: "Runs your unchanged `.py` file in a real Python interpreter."
- Overclaim: "Zero behavioral difference in all environments."

### Conditional acceleration
- Verdict: SUPPORTED BY INTEGRATED PRODUCT (as description, not benefit).
- Scope: admitted scripts only; 7/30 representative + fixed-22.
- Evidence: route + artifact + contact parity.
- Limitation: 22/30 representative scripts cannot benefit by construction.
- Recommended: "An optional direct-read path activates only for statically
  admitted scripts; everything else runs ordinary openpyxl."
- Overclaim: "Automatically accelerates your workbook code."

### Unsupported behavior uses reference openpyxl
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope: negative admission, unsupported load modes, proxy escapes,
  artifact/build failures. Implementation: integrated bootstrap + runtime.
- Evidence: 543/543 route/fallback parity; fallback-after-contact row.
- Limitation: fallback-after-contact iteration pays double-work.
- Recommended: "Anything outside the narrow direct contract runs on real
  openpyxl, and the fallback is recorded in the receipt."
- Overclaim: "Full openpyxl equivalence."

### Direct read serving avoids normal workbook parsing on its earned surface
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope: direct-contact loads only (second invocation, valid artifact).
  Denominator: 7 representative + 22 fixed contact scripts.
- Evidence: `decode_xlsx` never calls `load_workbook` (code) + contact-gated
  `REUSED` receipts (measurement).
- Limitation: openpyxl utility modules still used; fallback re-parses.
- Recommended: "Direct-contact reads are served from a derived artifact without
  running the normal workbook parser for that load."
- Overclaim: "No longer uses openpyxl."

### Persistent reuse
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope: same machine, same user cache, unchanged source + versions.
- Evidence: BUILT→REUSED sequences; concurrency pair; invalidation tests.
- Limitation: no cross-machine/distributed story; no quota.
- Recommended: "Derived read state persists across invocations until the
  workbook or runtime version changes."
- Overclaim: "Build once, reuse everywhere."

### Negative admission leaves direct runtime inactive
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope: all `PREDECLARED_REAL_OPENPYXL` / `DISABLED` decisions.
- Evidence: reference-only path audit (no proxy install, no artifact lookup,
  no direct state) + no-artifact-dir test.
- Limitation: none material.
- Recommended: "Scripts the classifier rejects never load the direct runtime."
- Overclaim: none; keep narrow.

### Observer is external to target process
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope: all observer-mediated runs on Linux.
- Evidence: native parent/child architecture + abrupt-exit survival fixtures.
- Limitation: `--no-runtime` and disabled config intentionally skip it.
- Recommended: "A native parent process observes the script process and
  survives its abrupt death on tested paths."
- Overclaim: "Survives all crashes on all platforms."

## Performance claims (exact population/timing boundaries required)

### Reference-only practical overhead
- Verdict: SUPPORTED CONDITIONALLY (controlled host/run protocol only).
- Scope: fixed 22 reference-only scripts, second invocation, CPU-pinned.
  Implementation: unchanged Phase-10 product.
- Evidence: +6.39 ms median [5.63, 9.71], ratio 1.037.
- Limitation: unpinned run on same host showed +18.85 ms; host-sensitive.
- Recommended: "On the fixed 22-script reference-only set, the unchanged
  product added a median +6.39 ms per script in a CPU-pinned rerun on one
  host (earlier unpinned observation: +18.85 ms)."
- Overclaim: "Adds only ~6 ms overhead" (drops population + host + pinning).

### Direct-contact timing reduction
- Verdict: SUPPORTED CONDITIONALLY (contact-selected populations, warm only).
- Scope: 7 representative direct-contact (0.608×) and fixed-22 (0.468×),
  second invocation. Implementation: integrated read engine.
- Evidence: per-workload paired ratios + bootstrap intervals.
- Limitation: small clustered views; cold is slower (1.04–1.12×); all-30
  median is 1.044 (majority reference-only).
- Recommended: "On 7 frozen representative direct-contact workloads, warm
  reuse showed median 0.608× vs plain Python; cold runs show no benefit."
- Overclaim: any global speedup ("1.6× faster workbook reads").

## Assurance claims (neither performance nor task-correctness)

### External process survival
- Verdict: SUPPORTED BY INTEGRATED PRODUCT (tested cases).
- Scope: `os._exit`, SIGTERM, exception, SystemExit, caught SIGINT, atexit.
- Evidence: process fixtures incl. 65/65 + 20/20 + 60/60 Phase-10B rows.
- Limitation: native crashes (SIGSEGV/SIGKILL), all-signal matrix untested.
- Recommended: "The observer survived tested abrupt exits including `os._exit`
  and SIGTERM and still recorded status and effects."
- Overclaim: "Guaranteed observation under any failure."

### Changed-file effect detection
- Verdict: SUPPORTED BY INTEGRATED PRODUCT (mechanical only).
- Scope: 5 frozen write fixtures + unit capture test.
- Evidence: exact package relation, detection, validation+replay pass.
- Limitation: byte/package-level only; says nothing about task correctness;
  2 fixtures rely on the volatile-metadata normalization rule.
- Recommended: "Changed workbooks were detected and mechanically
  validated (package delta + replay) in 5 frozen fixtures."
- Overclaim: "Verifies your script did the right thing."

### Exact package replay/validation
- Verdict: SUPPORTED BY INTEGRATED PRODUCT (same scope as above).
- Recommended: "Capture replays the recorded delta and compares package parts."
- Overclaim: "Certified correct output."

### Cache freshness
- Verdict: SUPPORTED BY INTEGRATED PRODUCT.
- Scope: whole-file SHA-256 + version-bound keys + second-hash race guard.
- Evidence: invalidation, key-change, upgrade, concurrency ledgers.
- Limitation: concurrent script editing unsupported.
- Recommended: "Stale or mismatched derived state is never served; it rebuilds."
- Overclaim: "Safe under concurrent writers."

### Concurrency-safe artifact publication
- Verdict: SUPPORTED CONDITIONALLY (two local processes, one filesystem).
- Evidence: BUILT+REUSED pair, valid final artifact.
- Limitation: no stress/NFS/distributed evidence.
- Recommended: "Two simultaneous same-source builds publish atomically with a
  valid final artifact on local disk."
- Overclaim: "Safe for parallel/distributed workloads."

### Clean wheel installation
- Verdict: SUPPORTED CONDITIONALLY (one host, CPython 3.13.12).
- Evidence: `install_results.json` pass.
- Limitation: single configuration; local wheel tag, not manylinux.
- Recommended: "A clean wheel install passed on Linux x86_64 with CPython 3.13."
- Overclaim: "Installs anywhere."

## Negative / boundary claims

### No model/API dependency
- Verdict: SUPPORTED BY INTEGRATED PRODUCT. No client, no credentials, no
  network in the runtime path (verified by import scan + hygiene test).
- Recommended: "No model account, API key, or network access required."

### No token savings claim
- Verdict: SUPPORTED BY INTEGRATED PRODUCT (as a deliberate non-claim).
  Frozen token discovery found no reproducible mechanism; product makes no
  token claim. Keep stating the absence.

### No universal speed claim
- Verdict: SUPPORTED BY INTEGRATED PRODUCT (as a deliberate non-claim).
  All-30 median 1.044 with 5 faster/25 slower forbids it; cold unsupported.
  Keep stating the absence.

## Historical-only (do NOT attach to the integrated product)

- RC-era "reduces total invocation wall time": NOT SUPPORTED then (T/C 2.017)
  and superseded now; never cite.
- RC-era "exact read semantics for all admitted workloads": NOT SUPPORTED then
  (4 semantic failures on the old index path); the integrated engine is a
  different implementation with its own parity evidence — cite only the new
  543/543 + narrow-contract limits.
- Phase-9 +8.73 ms reference-only figure: SUPPORTED ONLY HISTORICALLY; the
  integrated product has its own +18.85/+6.39 ms observations.
- Per-read/trace micro-benchmarks: internal technical evidence only; never a
  product percentage.

## Claims that must not be made (any version)

- Any unqualified speedup ("faster Excel in Python").
- Cold-start, write-acceleration, cost/token, or broad-equivalence claims.
- Cross-host millisecond guarantees from single-host timings.
- Task-correctness or output-certification claims from effect capture.
- Platform claims beyond tested Linux x86_64 scope.
