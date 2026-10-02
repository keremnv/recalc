# Failure semantics matrix

Compiled from `runner.py`, `observer.c`, `sitecustomize.py`, `read_engine/*`,
`_capture_helper.py`, `cli.py`, plus `failure_injection.json` and the 27
product tests. Columns: does the script launch? reference fallback? target
status? assurance status? user-visible result? release concern?

| Failure | Script launches? | Reference fallback? | Target status | Assurance status | User-visible result | Release concern? |
|---|---|---|---|---|---|---|
| Artifact missing/corrupt/truncated/stale | YES | Rebuild; reference if build fails | Normal | PASS (if capture path clean) | Exit 0, `BUILT`, stdout normal | No |
| Decoder failure (direct) | YES | Per-load reference (`runtime_failure`) | Normal | PASS | Exit 0, fallback reason recorded | No |
| Classifier uncertainty (any blocker) | YES | Whole-script reference (no interposition) | Normal | PASS | Exit 0, `REFERENCE_FAST_PATH` | No |
| Unsupported operation (load mode / proxy escape / iteration) | YES | Lazy real openpyxl | Normal | PASS | Exit 0, `DIRECT_WITH_FALLBACK` + reasons | No (double-work on iteration is known + documented) |
| Reference parser failure (malformed workbook) | YES (then dies like PY) | n/a (reference IS the behavior) | Same as PY (exit 1 observed) | PASS | Same stderr/exit as plain Python | No |
| Observer binary missing/not executable | NO ("no task was run") | n/a | n/a | n/a | `FAIL: ...` stderr, exit 2 | No (correct blocking) |
| Observer child-launch failure (bad python) | Attempted, `_exit(127)` | n/a | exit 127, signal 0 | PASS | Exit 127 | No (matches exec-failure convention) |
| Helper failure (capture exit 3 / crash) | Already ran | n/a | Preserved | FAILED | Exit 125 if target succeeded, else target's status; receipt records both | No |
| Capture disabled (`capture=false`) with changes | YES | n/a | Normal | NOT_REQUESTED | Exit 0, capture fields `NOT_REQUESTED` | No |
| Cache path unusable (file/symlink/perms/ownership) | NO ("no task was run") | n/a | n/a | n/a | `FAIL: ...` stderr, exit 2 | No (correct blocking) |
| Run dir failure (mkdir/mkdtemp/receipt write) | Depends on stage | n/a | Preserved if ran | FAILED or exit 125 | Exit 125 + stderr; possibly partial run dir | LOW — pre-receipt observer death leaves only stderr + partial dir (known, documented in failure policy; no silent success) |
| Disk-full during run | YES | Best-effort | Preserved | FAILED (receipt/helper write fails loudly) | Nonzero exit + stderr | LOW — fails loudly, not silently; no explicit disk-full test exists |
| Target exception / SystemExit(n) | YES | n/a | exit n / 1 | PASS | Identical to PY | No |
| Target signal (incl. SIGTERM) | YES | n/a | signal recorded; observer re-raises → 128+signo | PASS (observation complete) | Shell-standard signal exit | No |
| Target `os._exit(n)` (skips atexit → no `runtime_state.json`) | YES | n/a | exit n | PASS | Exit n; receipt falls back to `setup.json` | No |
| Bootstrap failure (any sitecustomize exception) | YES (as ordinary PY) | Whole-script reference | Normal | FAILED if setup route was direct, else unchanged | Exit 125 if target succeeded on direct route; route demoted to reference | No (conservative + tested rule) |
| Malformed workbook (reference rejects) | YES | n/a | Matches PY | PASS | Matches PY | No |
| Bad config file | YES (as direct Python, no observer) | Whole-run reference | Direct-Python exit | NOT_REQUESTED + WARNING on stderr | Exit 0 + warning | LOW — surprising at first (invalid config silently degrades to no-observer), but WARNING is loud and fail-closed is the safe direction. Document prominently. |
| `--no-runtime` / disabled | YES (direct Python) | Whole-run reference | Direct-Python exit | NOT_REQUESTED | Exit = script's | No |
| Concurrent same-source builds | YES (both) | n/a | Both normal | PASS | One BUILT, one REUSED | No |
| 1000-file / 512 MiB snapshot bound exceeded | Pre-snapshot: NO (die 125); post: target ran, assurance FAILED via die | n/a | Preserved if ran | FAILED | Exit 125 + `snapshot XLSX: ...` stderr | LOW — loud failure, but the bound + error should be documented (users with huge workdirs will hit it). |

## Ambiguous or surprising behaviors (none blocking, all need docs)

1. Invalid config → observer silently absent (only a stderr WARNING). Safe
   direction, but a user who typo'd a key loses assurance without a nonzero
   exit on success. Mitigation: docs + `doctor` shows the warning path.
2. `capture=false` still runs the observer (snapshots + target status) but
   skips the helper. Correct, but "capture disabled" vs "observer present"
   needs one doc paragraph.
3. Snapshot-bound death message (`snapshot XLSX: File too large`) doesn't name
   the bound. Improve the message in a cleanup pass (one-line change).
4. Pre-final-receipt observer death leaves a partial run dir + stderr only.
   Acceptable for preview (never silent success); durability hardening is
   post-v1.
