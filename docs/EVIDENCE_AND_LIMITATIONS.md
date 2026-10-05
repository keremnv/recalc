# Evidence and limitations — Recalc 0.2.0

This document describes the semantic and operational evidence boundary
for released `recalc-agent 0.2.0`. It covers interface parity,
direct-read eligibility, fallback behavior, persisted-state integrity,
observation/assurance behavior, tested execution environments, and
unsupported cases.

Performance measurements are intentionally not duplicated here; see
[`PERFORMANCE.md`](../PERFORMANCE.md). Release history lives in
[`CHANGELOG.md`](../CHANGELOG.md); the detailed support matrix in
[`COMPATIBILITY.md`](../COMPATIBILITY.md); historical studies in
[`research/`](../research/).

## What is established

### Ordinary Python/openpyxl execution surface

`recalc-agent run` executes the user's ordinary Python script in a real
Python interpreter; Recalc does not require spreadsheet logic to be
rewritten into a DSL or task IR. Validated: 543/543 oracle rows show
exit/stream/state parity between plain Python and Recalc execution,
including route/fallback parity; process-identity fixtures cover argv,
cwd, `__main__`, streams, atexit, subprocesses, inherited file
descriptors, and caught SIGINT. Nested interpreters and other Python
processes are unaffected by design.

### Certified direct-read contract

Whole-script static admission routes uncertain scripts to genuine
openpyxl without loading the direct runtime (audited: no proxy, no
artifact lookup, no direct state on that path). Admitted scripts get a
narrow surface: workbook/worksheet names and lookup, worksheet
bounds/dimensions, literal/integer point-cell access, cell value and
data type, selected merged-cell behavior under a closed
terminal-scalar grammar, and the certified full-cell `ws.iter_rows()`
contract (bounded or worksheet-dimension bounds, nested row → cell
consumption, `.value` / `.coordinate` / `.row` / `.column` /
`.data_type` cell surface).

Representative exclusions: `iter_cols`, `values_only`, `.values`,
range literals, direct writes/mutation, `data_only`, rich
attributes/object escape, and dynamic usage static admission cannot
certify. Certified iteration parity: 40/40 adversarial and 52/52 A/B
differential vs pinned openpyxl 3.1.5.

### Mixed reads and writes, precisely

A script/invocation containing workbook mutation (`.save()`,
workbook/cell assignment) is reference-routed as a whole by static
admission. Separately, certified read-only invocations may be directly
served inside a larger trajectory whose other invocations write —
each invocation is classified independently, and measured task replays
include such mixed trajectories. Mutations and uncertified behavior
always remain genuine-openpyxl/reference execution; a mixed
trajectory as a whole is neither "supported" nor "unsupported" — the
unit is the invocation.

### Fail-closed admission and genuine-openpyxl fallback

Uncertainty never causes Recalc to approximate openpyxl semantics.
Two distinct cases:

- **Not admitted.** The script runs on genuine openpyxl; the direct
  runtime is never loaded.
- **Admitted, but a runtime condition prevents direct service.**
  Unsupported load modes, proxy escapes, uncertified iteration, and
  missing/stale/corrupt/incompatible read state resolve per the
  implemented contract — rebuild where the state is at fault, lazy
  reference fallback where the operation escapes — and the route is
  recorded in the receipt.

Fallback is a designed outcome, not a semantic failure — and not
acceleration. Admission does not imply useful direct service:
admitted invocations have been observed serving zero direct loads.
Unsupported behavior retains openpyxl ownership throughout.

### Validated persistent workbook read state

The persisted semantic object is validated workbook read state
(artifact format `JSONZ_MEMORY_V1`), keyed by whole-file SHA-256 plus
runtime/decoder/contract/format versions, published atomically under
a per-key lock. Recalc 0.2.0 reconstructs supported Python values
directly from already-validated typed state while preserving the
same artifact representation, validation boundary, and direct-read
contract (semantic parity: 52/52 canonical state, 40/40 adversarial,
52/52 A/B differential, 12/12 corruption rejection; byte-identical
artifacts across the decoder change).

### Freshness and corruption handling

Stale, corrupt, truncated, malformed, missing, or incompatible state
is rejected and rebuilt — never served. Old-version entries are
orphaned by key rotation, never served. A second source hash at
first load closes the bootstrap-to-script race. Corrupt-cache
rebuild, malformed workbooks, cache denial, and related failure
injection are covered by the maintained battery plus the 12/12
identical-reject corruption confirmation.

### External observation and assurance

Semantic execution occurs in the child Python process; an external
native observer independently launches it, waits for it (surviving
tested abrupt exits: `os._exit`, SIGTERM, uncaught exceptions),
snapshots workbook state before and after, and records raw exit/signal
status separately from assurance status. Target status reports the
script's own outcome; assurance status (`PASS`, `FAILED`,
`NOT_REQUESTED`) reports the mechanical post-state check. If
assurance fails while the script succeeded, the command exits `125`;
if the script failed, its own status is preserved.

### Changed-workbook capture

Five frozen fixtures establish: changed-XLSX detection, exact
package relation, mechanical validation, and delta capture/replay
(persisted, serialization valid, relationships preserved, captured ==
committed, replay reproduces the parts). This establishes mechanics
only. It does not establish task correctness, semantic intent,
formula correctness, or business correctness: capture records what
the script produced, never whether it is what the task wanted.

### Installation and process behavior

Tested: clean wheel install (native launcher + observer), green
doctor/example/run/status checks, the BUILT→REUSED artifact
lifecycle, 27+ maintained product/process tests, and a bounded
failure-injection battery (corrupt/truncated/missing/stale
artifacts, malformed workbook, cache denial, missing observer,
helper failure, launch failure). This is release behavior evidence,
not universal platform support.

## Current contract boundaries

- Narrow direct-read contract only; unsupported/dynamic semantics use
  genuine openpyxl.
- Writes are not directly served; cold first touch builds state.
- No broad object equivalence: proxy objects promise the narrow
  contract only (no identity, repr, style, or escape equivalence).
- Not a general openpyxl substitute: out-of-contract behavior stays
  reference-routed by design.
- Concurrent editing of the same task/script directory is
  unsupported; concurrent same-artifact cache builds are safe.
- No automatic cache eviction: orphaned entries stay inert on disk
  until deleted; `doctor`/`status` report size and count.
- No sandbox: scripts run with the user's permissions.
- Saving formulas does not recalculate them; LibreOffice presence is
  probed, not orchestrated, by this distribution.

## Platform and operational boundaries

Tested release baseline: Linux x86_64 with glibc, local filesystem,
CPython 3.13, pinned openpyxl 3.1.5 / lxml 6.1.3 (pins in
`pyproject.toml`, which accepts CPython 3.11–3.14). macOS and
Windows carry no validation claim; network filesystems and
containers are untested per-environment assumptions; other
openpyxl/lxml versions need re-validation. Full matrix:
[`COMPATIBILITY.md`](../COMPATIBILITY.md).

## What is not claimed

Recalc 0.2.0 does not claim: broad openpyxl equivalence; task,
intent, formula, or business correctness from capture or assurance;
sandbox/security isolation; universal platform support; direct-write
acceleration; or certified behavior for unsupported object/surface
usage. Performance claim boundaries — universal speedup, cold
acceleration, family-wide effects, thresholds — are maintained in
[`PERFORMANCE.md`](../PERFORMANCE.md).

## Performance evidence

**Performance evidence:** see [`PERFORMANCE.md`](../PERFORMANCE.md)
for task-replay cases, the released-product inspection example,
counterexamples, mechanism-population evidence, workload fit,
cold/write/memory measurements, methodology, and quantitative
non-claims.

## Evidence and provenance

| claim area | provenance |
|---|---|
| Ordinary-execution parity (543/543) | `research/history/phase10c_audit/EVIDENCE_ATTACHMENT_MATRIX.md`, `CURRENT_PRODUCT_ANATOMY.md`; `tests/test_product_hygiene.py`, `tests/test_product_process_semantics.py` |
| Iteration contract parity (40/40, 52/52) | `research/full_cell_iteration_product_confirmation/` (REPORT.md, ADVERSARIAL_RESULTS.jsonl, parity ledger) |
| Decoder parity + corruption (52/52, 12/12) | `research/artifact_decode_product_confirmation/PRODUCT_GATE.json`, REPORT.md |
| Target conversion (13/13) | Mechanism evidence; see PERFORMANCE.md §6, not repeated here |
| Changed-file fixtures (5/5) | `research/history/product_integration_phase10b/` amendment 3; `src/recalc_agent/_frozen/capture.py`, `delta.py`, `validate.py` |
| Admission blockers (write/mixed/uncertain) | `src/recalc_agent/_frozen/eligibility.py` (`WRITE_BOUNDARY`, `READ_WRITE_MIXED_BOUNDARY`, load-option boundaries) |
| Observer/assurance/exit policy | `src/recalc_agent/native/observer.c`, `src/recalc_agent/runner.py`; abrupt-exit fixtures in product tests |
| Platform baseline | `research/history/phase10c_b/LINUX_RELEASE_BASELINE.md`, COMPATIBILITY.md, `pyproject.toml` pins |

Validation host for the cited runs: Ubuntu 26.04.1, kernel 7.0.0-34,
Intel Core Ultra 5 125H, CPython 3.13.12, openpyxl 3.1.5.
