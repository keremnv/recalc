# Phase 10C-B: release implementation report — librecalc-agent 0.2.0rc2

Implementation phase for the 10C-A audit verdict
(`READY AFTER BOUNDED PRE-RELEASE CLEANUP`). Architecture untouched by
design; all work was cleanup, hardening, docs, and release engineering.
No PyPI upload, no remote tag, no publication — local/CI candidate only.

## VALIDATED ARCHITECTURE CARRIED FORWARD

`PRODUCT INTEGRATION VALIDATED` (Phase-10/10B) carried forward with no
contradiction found: native launcher → external observer → real Python
script → guarded bootstrap/admission → negative: ordinary openpyxl, positive:
narrow direct-read runtime over persistent derived state with reference
fallback → external effect observation → capture/validation on change →
split target + assurance receipt. Model: ordinary Python, conditionally
accelerated, externally observed. No mechanism was redesigned, widened, or
optimized in this phase.

## BASELINE WORKTREE AND PROVENANCE

Recorded in `phase10c_b/BASELINE_WORKTREE_MANIFEST.md`: 20 pre-existing
tracked modifications, 4 + 9 in-flight staged/rename entries, and 471
untracked paths including the whole maintained product. Files classified
SOURCE (release diff) / EVIDENCE (retained, unstaged — 3.8 GB+ across the two
Phase-10/10B dirs alone) / GENERATED (ignored) / LOCAL (ignored).
`.gitignore` gained GENERATED/LOCAL rules only (built native binaries,
wheels, release staging); no evidence path newly ignored. One collateral
found and fixed: ignoring the built binaries excluded them from sdists, so
wheel-from-sdist lost the observer — fixed via explicit `artifacts` in
`hatch_build.py` (verified: binaries present at 0755).

## IMPLEMENTATION PLAN

`phase10c_b/IMPLEMENTATION_PLAN.md` was written before any code edit: 17
steps (0–16) each with files, behavior change, surface impact, compatibility,
gate, rollback, and class (NON-BEHAVIORAL / PUBLIC-SURFACE CLEANUP / INTERNAL
REFACTOR / HARDENING / RELEASE ENGINEERING). All steps executed; out-of-scope
list (P5, optimization, coverage, eviction, helpers, derivation research,
ports, benchmark reruns, marketing) held — no scope escape.

## VERSION CONTROL STATUS

No commits created, deliberately: the owner has in-flight staged/rename work
any commit would disturb, and the multi-GB evidence-commit policy is an owner
decision. Instead the exact release diff is STAGED (73 new paths: product,
tests, packaging, docs, CI, audit records; zero binaries, zero `__pycache__`),
all pre-existing staged/unstaged entries byte-identical and verified intact
afterwards. `git status` is now a reviewable release story: staged = candidate,
unstaged tracked = pre-existing work, untracked = evidence + history.

## LICENSE

`LICENSE DECISION REQUIRED` — the only unresolved release blocker. Full-repo
search found zero license signals, and `PUBLIC_RELEASE_BLOCKERS.md` explicitly
records `LICENSE_NOT_CHOSEN` ("No license is selected on the user's behalf by
this note"). Per the phase spec §9, nothing was invented; all non-legal work
continued. Packaging is license-ready: sdist already includes `/LICENSE*`,
`release-check.sh` step 15 auto-activates its wheel-license assertion the
moment a `LICENSE` file exists, and the manifest records the gap.

## VERSION AND CHANGELOG

`0.2.0rc2` (`src/librecalc_agent/__init__.py`, `pyproject.toml`): same
architecture generation as rc1, cleanup release, still pre-release (license
open, Linux-first). Rationale recorded in `CHANGELOG.md`, which distinguishes
USER-VISIBLE / INTERNAL / COMPATIBILITY / KNOWN LIMITATIONS and documents the
rc1→rc2 architecture transition, receipt/config migrations, cache orphaning
(runtime version is keyed — old entries rebuild, never served), and explicit
nonclaims. Receipt/doctor `--version` outputs move with the bump (covered by
tests).

## V1 PRODUCT BOUNDARY

Held per audit: `run`, `doctor`, `status`, `example`, `--config`,
`--no-runtime`, `--workdir`, `enabled`/`reads`/`capture`/`cache_dir`/
`verbosity`, compact receipt, reference fallback, truthful `NOT_REQUESTED`,
"no task was run" blocking; `--json`/`--verbose`/run-dir bundle stay as cheap
coherent optionals. Nothing added: no cache CLI, no library API, no routing
API, no new modes, no derived outputs.

## DOCUMENTATION REWRITE

README rewritten around the integrated product (install, platform, quickstart,
acceleration, capture, cache, config, diagnostics, limitations, uninstall,
security, repo map); walkthrough verified verbatim against the staged
candidate. COMPATIBILITY rewritten as the current rc2 matrix (rc1 SQLite rows
gone with the dead path). New `docs/EVIDENCE_AND_LIMITATIONS.md` (established
/ conditional / not-claimed). rc1 claim docs kept as evidence with HISTORICAL
banners. A user entering the repo can no longer follow rc1 instructions by
accident.

## LINUX SUPPORT BASELINE

`phase10c_b/LINUX_RELEASE_BASELINE.md`: x86_64, glibc ≥ 2.34 (established by
symbol audit of both binaries — max `GLIBC_2.34`, far below the 2.43 build
host), CPython 3.13 tested / 3.11–3.14 accepted, local POSIX filesystem,
`py3-none-linux_x86_64` local tag (NOT manylinux). manylinux path defined but
explicitly deferred (needs official image + `auditwheel repair`; label not
claimed). Unsupported list explicit (older glibc, musl, macOS, Windows,
remote FS, unpinned deps).

## RELEASE CI

`.github/workflows/release-candidate.yml` (ubuntu-24.04 + CPython 3.13) runs
`scripts/build_native.sh`, the maintained suite, then `scripts/release-check.sh`
— a 17-step local-runnable battery: clean build, env record, hash-locked clean
install into an in-project gitignored venv, native checks, 40 tests,
doctor/example, reference + BUILD/REUSE, capture, abrupt-exit smoke,
wheel-list/no-pycache/license checks, dep versions, checksums + staging to
`release-candidate/` (+ artifact upload). No benchmark suite in CI; functional
and perf characterization stay separate. Battery passes exit 0; two
consecutive builds produced identical archive hashes.

## DEPENDENCY REPRODUCIBILITY

Exact pins kept (`openpyxl==3.1.5`, `lxml==6.1.3`). New
`requirements-release.txt`: runtime closure locked with hashes for the cp313
floor (openpyxl, et_xmlfile 2.0.0, lxml manylinux wheel), consumed by release
CI with `--require-hashes`; build backend version recorded with hash for
audit. `sqlite3` reliance is now zero (died with the dead modules).
`pyyaml` left in dev deps (legacy tests still use it; product tests don't).

## DEAD MODULE REMOVAL

Deleted `_frozen/{index,reads,runtime,substrate}.py` (~890 lines) after
static + dynamic-import + packaging + test verification (zero maintained
consumers; diagnostics probes only the live four). `scripts/extract_product_runtime.py`
and the extraction manifest intentionally untouched (historical tooling /
evidence; the source-pin test still passes and still means what it says).
Gate: import scan clean, 40/40, clean install, example, BUILD/REUSE,
reference path — all green.

## RESEARCH TERMINOLOGY RETIREMENT

`CANDIDATE_A_*` env filtering removed from `runner.py` (only the dead runtime
read those vars; zero `CANDIDATE_A` remains in shipped code).
`read_gate` retired from the compact receipt and setup schema (see below).
`H1` docstring reworded. Remaining shipped occurrences are exactly the
windowed config aliases (warn on use) and the keyed `CONTRACT` token
(internal, never CLI-surfaced) — both classified INTERNAL/COMPATIBILITY in
the sweep.

## RECEIPT SCHEMA CLEANUP

Narrow audit, not redesign. Compact receipt replaces `read_gate` research
strings with `admitted: bool` + `admission_reason` in
{`admitted`, `not-admitted`, `runtime-disabled`, `setup-failed`}; raw
classifier detail stays in run-dir `setup.json` as `admission_decision`
(unstable/support-only). Disabled-runtime path returns the same shape
(`runtime-disabled`) for stability. Target/assurance/route/artifact/fallback/
capture/version fields unchanged; no dual-write (rc1 schema was RC-age;
break announced in CHANGELOG). `--verbose` documented (and help-text fixed)
as full-JSON-report, same as `--json`. `PRODUCT_RECEIPT_SCHEMA.md` updated.

## CACHE AND ARTIFACT CONSOLIDATION

New `read_engine/_identity.py` single-sources magic, versions, `sha_file`,
`sha_bytes`, `identity`, `artifact_key`, `paths`; `cache.py`/`artifact.py`
slimmed to import it. Both `validate`/`ensure` layers preserved (fast
integrity gate vs full semantic gate — legitimate layering). Key format
independently re-verified; fixed-vector key-stability test locks it
(rc2 vector `f32685c5…`, version bump intentionally orphans rc1 entries);
`is`-identity test locks single-sourcing; version-invalidation test now
patches `_identity` and asserts both layers move together. My new ruff F401s
fixed; pre-existing codebase-wide lint noise left alone deliberately.

## CACHE VISIBILITY

`diagnostics.cache_summary()` (bounded: 5000-file walk cap, `truncated` flag)
reports path/existence/bytes/files/artifacts/runs + safe-deletion guidance;
wired into `check()`/`status()` JSON (additive keys) and a human `Cache use:`
line. No eviction, no CLI, no retention promise — documented as such in code,
README, and the summary's own `guidance` string.

## CAPTURE XML HARDENING

Smallest mitigation in `_frozen/validate.py`: `_safe_fromstring()` rejects
DOCTYPE/ENTITY constructs and 64 MiB-oversize parts before stdlib parsing at
the only two capture XML sites (`[Content_Types].xml`, `*.rels`); rejections
surface as ordinary `serialization_valid`/`relationships_preserved` check
failures with naming detail — deterministic, package-focused, no new deps.
Adversarial regression test added (internal-entity bomb + external entity →
loud `False`, DOCTYPE named). All 5 changed-file fixtures + capture tests
still pass (benign workbooks bit-identical).

## SNAPSHOT BOUND DIAGNOSTICS

`observer.c` now classifies snapshot failures: file-count limit, 512 MiB
aggregate limit, unreadable file (basename + errno, no full paths), bad file
name, OOM, workdir-changed, plus raw nftw fallback. Same situations, same
exit 125, clear stderr (`snapshot XLSX: too many XLSX files (limit 1000)`).
Bounds unchanged. Three regression tests (1001-file dir, sparse 600 MB file,
mode-000 file) + one launch-failure receipt test. Rebuilt `-Werror`-clean via
`scripts/build_native.sh`.

## LX_HELPERS DISPOSITION

`REMOVE_PRE_V1` (`phase10c_b/LX_HELPERS_DISPOSITION.md`): import scan proved
ZERO consumers of the installed module — all benchmark/test users resolve to
the benchmark-local shim backed by benchmark code. Removed as one unit:
`src/lx_helpers.py`, `_frozen/{helpers,helper_common,period_constants}.py`,
pyproject force-include + sdist entries. No deprecation window (nothing to
migrate); benchmark shim untouched and self-sufficient. Wheel loses the
accidental top-level API; `COMPATIBILITY.md`/CHANGELOG record it.

## CONFIG MIGRATION

New documented `reads` key (bool, default true); `substrate`/`candidate_a`
kept one window as deprecated aliases that AND with `reads` (old configs keep
exact meaning) and emit loud WARNING issues naming the replacement.
`config.reads` property → `reads_effective`; all 5 use sites updated;
`LIBRECALC_EFFECTIVE_CONFIG` round-trip unaffected (full-field serde).
Example `runtime.toml` rewritten to successor keys; README/CHANGELOG document
the window; removal post-v1. Config regression test added (new key, alias
warning, AND semantics).

## WHEEL CONTENTS

`phase10c_b/WHEEL_CONTENTS_FINAL.md` classifies all 30 shipped files: 20 core
runtime, 4 native (binaries 0755 + sources), 4 examples, metadata +
installed launcher script. Absent as required: dead modules, helper unit,
`lx_helpers`, tests, benchmark, research, MCP, `__pycache__`, entry-points
shim. Every battery run re-asserts list + modes + no-pycache. SDist carries
sources + hook + current docs (+`LICENSE*` slot ready).

## PROCESS SEMANTICS REGRESSION

All invariants re-green in `tests/test_product_process_semantics.py` (now 13
tests): real `__main__`/argv/cwd/`sys.path[0]`, stdout/stderr identity,
SystemExit/exception exits, atexit observation, subprocess + env, inherited
FD, caught SIGINT, `os._exit`/SIGTERM survival with capture, plus new
launch-failure-as-target-status and 3 snapshot-bound classifications. No
process-identity regression from cleanup.

## REFERENCE PATH REGRESSION

Negative admission still leaves openpyxl untouched: no proxy install, no
artifact directory, `REFERENCE_FAST_PATH`, `admitted: false` /
`not-admitted`, observer active, correct receipt. Battery step 9–10 + unit
`test_reference_branch_does_not_publish_artifact` green on the installed
candidate.

## DIRECT BUILD AND REUSE REGRESSION

First invocation `BUILT`, second `REUSED`, direct contact, semantic exactness
(`21` round-trip) — unit + installed-candidate battery green. Version bump
correctly orphaned rc1 keys (rebuild, never stale-serve); key-stability test
locks the rc2 format.

## REFERENCE FALLBACK REGRESSION

New permanent test: admitted workbook-iteration script →
`DIRECT_WITH_FALLBACK` with `proxy_operation_escape` recorded and correct
output. Malformed-workbook test: identical nonzero exit to direct Python.
Known double-work on iteration unchanged (documented, not optimized — scope
held).

## CHANGED FILE ASSURANCE REGRESSION

Unit capture test + battery step 11 green on the candidate
(`effect_capture_status: PASS` asserted from installed `status --json`).
New merged-terminal test proves the restricted certificate path end to end
(certified setup + direct `None` child read). XML guard changes nothing for
benign packages (all fixtures pass).

## ABRUPT EXIT ASSURANCE REGRESSION

`os._exit`-after-mutation and SIGTERM fixtures green (observer survives,
change detected, capture passes, signal/exit recorded); battery step 12
asserts exit 7 + `assurance_status: PASS` from the installed candidate.
Retained observer logic untouched except diagnostic messages.

## CACHE CONCURRENCY AND INVALIDATION

Concurrent-publication test (BUILT+REUSED pair, valid final artifact) green
after consolidation; corrupt-cache rebuild, source-change invalidation,
version-key change, and new sidecar-tamper rebuild tests green. No
distributed/NFS semantics added (scope held).

## FAILURE INJECTION

Battery: corrupt/truncated/missing/stale/version-mismatched artifacts →
rebuild + serve; malformed workbook → PY-identical failure; cache denial +
missing observer → block before launch ("no task was run"); helper-failure
and launch-failure paths covered by Phase-10 evidence (code paths unchanged)
plus the new launch-failure unit test; target exception/signal/`os._exit`/
SIGTERM/changes covered above. The stale Phase-10 `failure_checks.py`
harness was deliberately NOT re-executed (hardcoded paths; re-running would
overwrite archived evidence) — its cases are now permanent unit/battery gates
instead. No failure-semantics regression found.

## CLEAN BUILD AND INSTALL

`python -m build` from the worktree → sdist + `py3-none-linux_x86_64` wheel;
hash-locked clean install into a fresh in-project venv; installed
`librecalc-agent` (native launcher) + observer executable; doctor PASS,
example copy, run/status, reference + BUILD/REUSE, capture, abrupt-exit —
all green, twice, with identical archive hashes across runs
(wheel `dac2c30b…`, sdist `2b5bd1c5…`).

## RELEASE CANDIDATE MANIFEST

`phase10c_b/RELEASE_CANDIDATE_MANIFEST.json`: version, wheel tag, artifact
hashes + sizes, build env (CPython 3.13.12, gcc 15.2, glibc floor 2.34),
locked deps, 40/40 tests, smoke list, timing sanity (+6.2 ms, not a verdict),
license status, and explicit not-done list (no PyPI/tag/announcement).
Staged archives + SHA256SUMS under gitignored `release-candidate/`.

## CLAIMS AND LIMITATIONS

Per the 10C-A claim map, now live in README + `docs/EVIDENCE_AND_LIMITATIONS.md`
+ CHANGELOG: ordinary-Python interface, conditional narrow reads, reference
fallback, persistent reuse, external observer, tested capture/install —
established; reference-only overhead (+6.39 pinned / +18.85 archived) and
direct-contact warm ratios (0.608 rep-7, 0.468 fixed-22) — conditional,
host-bound, never headlined; universal/cold/write/token/correctness/
equivalence claims — explicitly disclaimed. rc1 registry retained as marked
history. Timing sanity (+6.2 ms, CPU 1, same-run controls, 3 synthetic
scripts) confirms no gross startup change; not a budget verdict, recorded
as such.

## PHASE 10C-A BLOCKER RESOLUTION

- Version-control provenance: RESOLVED (staged). Exact 73-path release diff
  staged and verified (no binaries, no pycache); pre-existing work intact;
  mechanical commit left to owner by design. Remaining: owner reviews +
  commits (+ stages the 3 tracked files mixing pre-existing and 10C-B edits:
  `pyproject.toml`, `README.md`, `.gitignore`).
- License: UNRESOLVED — `LICENSE DECISION REQUIRED` (explicit repo policy
  forbids selecting on the user's behalf). Single bounded drop-in remains.
- Wrong public docs: RESOLVED. README/COMPATIBILITY rewritten to rc2,
  evidence boundary published, rc1 docs bannered as history, example
  verified verbatim.
- Release engineering / Linux build: RESOLVED. CI workflow + local battery
  (exit 0), Linux baseline with audited glibc floor, hashed lockfile,
  artifacts fix, clean install, reproducible hashes.
- Follow-ups: cache visibility RESOLVED, XML hardening RESOLVED, wheel
  residue RESOLVED, compatibility migration RESOLVED (aliases windowed,
  helpers removed with zero-consumer proof).

## REMAINING PRE-RELEASE RISKS

1. License unchosen — blocks any publication, nothing else.
2. Diff uncommitted — staged and safe, but one owner command away from
   durable.
3. Single-host validation (same as Phase-10/10B) — multi-host
   characterization stays post-v1 by policy.
4. No cache quota — documented + visible; automatic policy post-v1.
5. CI workflow file written but not executed on GitHub (no remote here) —
   the identical script passes locally; first remote run must be watched.

## POST CLEANUP MAINTAINER REVIEW

`phase10c_b/POST_CLEANUP_MAINTAINER_REVIEW.md`: product conceptually smaller;
no research leakage beyond two labeled windowed items (alias keys, keyed
contract token); nothing ships on sunk cost; no accidental coupling found;
remaining complexity (dual validate layers, 3-process config, handoff vars,
degraded receipt shape, openpyxl-utility imports) all justified; comfortable
maintaining for a year with two scheduled chores (alias removal, cache story).
No blockers; preferences recorded, not acted on.

## LINUX RELEASE CANDIDATE VERDICT

**B. `RELEASE CANDIDATE READY AFTER ONE BOUNDED FIX`.**

The fix: owner selects the license, adds the `LICENSE` file (+ one
`pyproject.toml` license line), rebuilds, re-runs `scripts/release-check.sh`
— whose step 15 automatically enforces wheel license inclusion. Everything
else in §43-A is met: 40/40 tests, clean build/install, local battery exit 0
on the declared floor, clean wheel, process/read/capture/concurrency/failure
regressions green, docs describe the actual product, versioned `0.2.0rc2`
produced with recorded hashes. Criteria not lowered: license and commit
execution are genuinely the only gaps, and neither is mine to take.

## NEXT STEP

Owner: (1) choose license (see `PUBLIC_RELEASE_BLOCKERS.md`), (2) review +
commit the staged release diff (plus the 3 mixed tracked files), (3) re-run
the battery once, (4) push + watch CI green, (5) then — and only then — make
the explicit release decision (tag, publish, announce). Post-v1 backlog:
alias removal, cache quota/retention, macOS fast-follow, multi-host perf
characterization, Phase-11 derivations via additive surfaces only.
