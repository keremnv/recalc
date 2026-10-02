# Current product anatomy — librecalc-agent 0.2.0rc1 (Phase-10 integrated tree)

Audit date: 2026-09-28. Information gathering only; no product changes.
All paths relative to repo root. Line references verified against the working tree.

Product identity: `librecalc-agent 0.2.0rc1` (`src/librecalc_agent/__init__.py`,
`pyproject.toml`). One Python package plus two native executables, one bootstrap
module, one capture helper, one top-level helper alias, and example data.

## Stage 0 — install / package

- Package/module/file: `pyproject.toml` (hatchling), `hatch_build.py`,
  `src/librecalc_agent/`, `src/lx_helpers.py`, `examples/basic/`.
- Process ownership: build host (`cc`) at wheel-build time; `pip` at install time.
- Public or internal: public install surface (`pip install .` / wheel).
- Required dependencies: build: `hatchling>=1.25`, `cc`, Linux x86_64 host
  (`hatch_build.py:16-17` rejects anything else). Runtime: `openpyxl==3.1.5`,
  `lxml==6.1.3`, CPython `>=3.11,<3.15`.
- Configuration inputs: none at install time.
- Persistent state created: installed package, `librecalc-agent` script
  (via `shared_scripts`, `hatch_build.py:32`), native `observer` + `launcher`.
- User-visible outputs: install success/failure; no console `entry_points`
  (dispatch is via the native launcher, not a Python console script).
- Failure behavior: non-Linux-x86_64 build raises `RuntimeError`; missing `cc`
  fails the build. Installing from a prebuilt wheel needs no compiler.
- Evidence: `product_integration_phase10/install_results.json` (`pass: true`,
  clean venv, doctor/example/run/status all exit 0, BUILT then REUSED).

Note: the wheel archived at `product_hygiene/dist/` is the OLD pure-Python RC
(`py3-none-any`, no `read_engine/`, no native binaries). It does not represent
the current integrated product.

## Stage 1 — CLI / native launcher

Two entry routes, same product:

1. Installed command `librecalc-agent` → native launcher
   (`src/librecalc_agent/native/launcher.c`). Default `run` (no `LIBRECALC_CONFIG`
   / `LIBRECALC_NO_RUNTIME` in env, existing script+workdir) execs the observer
   directly (`launcher.c:96-134`). Everything else (`example`, `doctor`,
   `status`, explicit config, `--no-runtime`, unresolvable paths) delegates to
   `python -m librecalc_agent.cli` (`launcher.c:66-75`).
2. `python -m librecalc_agent` → `__main__.py` → `cli.py:main`.

- Process ownership: launcher is its own short-lived process; it `execv`s and
  never returns. Python CLI (`cli.py`) parses args, loads config, and for `run`
  calls `runner.exec_run`, which `os.execve`s the observer or direct Python
  (`runner.py:157-165`) — no retained Python parent on the run path.
- Public: `example`, `run`, `doctor`, `status`, `--config`, `--no-runtime`,
  `--workdir`, `--require-libreoffice`, `--json`, `--verbose`.
- Required dependencies: Python interpreter beside the launcher (`launcher.c:86`),
  installed package resolvable via `lib/python*/site-packages` glob
  (`launcher.c:48-64`).
- Configuration inputs: argv, `LIBRECALC_CONFIG`, `LIBRECALC_NO_RUNTIME`,
  `XDG_CACHE_HOME`/`HOME` (launcher-side cache resolution, `launcher.c:113-122`).
- Persistent state: launcher creates user-owned `0700` cache + `runs/`
  (`launcher.c:30-46`); rejects non-user-owned roots.
- User-visible outputs: stdout/stderr messages, exit codes 0/1/2.
- Failure behavior: any launcher self-failure prints to stderr and `exit(2)`;
  never silently runs an unintended path — unresolvable inputs fall through to
  the Python CLI.
- Evidence: Phase-10 install check (command executable, all four commands pass);
  `tests/test_product_hygiene.py::test_cli_example_and_doctor`.

## Stage 2 — observer (external, native)

- File: `src/librecalc_agent/native/observer.c`, argv contract
  `observer PYTHON SCRIPT WORKDIR CACHE_ROOT RUN_ROOT BOOTSTRAP HELPER [ARGS]`.
- Process ownership: observer is the parent; target script is a `fork`+`execv`
  child (`observer.c:177-188`). Observer ignores SIGINT/SIGTERM in itself and
  restores handlers in the child (`observer.c:174-180`).
- Public or internal: internal. Invoked by launcher/runner; argv shape is an
  implementation detail (also exercised directly by process tests).
- Required dependencies: POSIX (`fork`/`execv`/`waitpid`/`sigaction`/`nftw`/
  `mkdtemp`), libc only. No Python embedding, no openpyxl.
- Configuration inputs: `LIBRECALC_CAPTURE_ENABLED`, `LIBRECALC_RECEIPT_POINTER`.
- Persistent state: `runs/run-XXXXXX/` (`mkdtemp`): `context.txt`,
  `pre_index.tsv` + `pre/*.bin` (only when changed bytes + capture enabled),
  `capture.json` (or `[]`), `observer_receipt.json`; updates `runs/last_run.json`
  and the private receipt pointer.
- User-visible outputs: child's stdout/stderr inherited untouched; observer's own
  stderr only on self-failure; exit status (see failure semantics file).
- Failure behavior: self-failure → stderr + `exit(125)` (`die()`); child exec
  failure → child `_exit(127)` recorded as target status. Target death never
  suppresses post-observation.
- Evidence: 27/27 product/process tests; Phase-10 abrupt-exit fixtures
  (`os._exit`, SIGTERM); Phase-10B 65/65 + 20/20 + 60/60 process-semantics rows.

## Stage 3 — target interpreter / bootstrap (`sitecustomize`)

- File: `src/librecalc_agent/_bootstrap/sitecustomize.py`, injected via
  `PYTHONPATH` prefix + `LIBRECALC_RUN_CONTEXT` (`observer.c:169-181`).
- Process ownership: runs inside the target script's interpreter at startup.
- Public or internal: internal. Guarded to the exact script identity
  (`sitecustomize.py:22-23`); nested interpreters are unaffected (tested).
- Required dependencies: `librecalc_agent.config`, `_frozen.eligibility`,
  and on admission only `read_engine.cache` / `certificate` / `runtime`.
- Configuration inputs: `LIBRECALC_EFFECTIVE_CONFIG` (JSON, preferred) or
  `LIBRECALC_CONFIG`/`LIBRECALC_NO_RUNTIME` fallback; context file lines.
- Persistent state: `setup.json` in run dir (always on context path);
  `bootstrap_failure.json` on exception; artifacts via cache `ensure` (admitted
  only). Negative path writes `setup.json` and returns without importing the
  direct stack (`sitecustomize.py:42-44`).
- User-visible outputs: none directly; script stdout/stderr/exit preserved.
- Failure behavior: any exception is swallowed into `bootstrap_failure.json`;
  ordinary Python remains available (`sitecustomize.py:84-92`).
- Evidence: Phase-10/10B route parity (22 reference / 7 direct / 1 fallback
  on representative30); nested-interpreter test; bootstrap-failure receipt rule
  (`runner.py:103-107`).

## Stage 4 — admission (classifier + certificate)

- Files: `src/librecalc_agent/_frozen/eligibility.py` (`classify`, whole-script
  A1 AST + preserved A0 lexical blockers), `src/librecalc_agent/read_engine/certificate.py`
  (`certify`, closed-grammar merged-child scalar proof, admitted scripts only).
- Process ownership: target script process, during bootstrap.
- Public or internal: internal. `read_gate` decision string leaks into receipts
  (`A1_ADMIT`, `PREDECLARED_REAL_OPENPYXL`, `DISABLED`).
- Required dependencies: stdlib `ast`/`re` only.
- Configuration inputs: script source text; `config.reads` gate
  (`enabled and substrate and candidate_a`).
- Persistent state: none beyond `setup.json` fields (`read_gate`, `admitted`,
  `merged_certificate`).
- User-visible outputs: routing behavior only (direct vs reference).
- Failure behavior: fail-closed — unparseable source, missing openpyxl import,
  function definitions, or any blocker → `PREDECLARED_REAL_OPENPYXL`.
- Evidence: Phase-10 oracle parity 543/543 with route parity; frozen 22
  classifier reasons recorded in
  `product_integration_phase10b/REFERENCE_ONLY_PATH_AUDIT.md`.

## Stage 5a — reference-only path

- Files: none beyond bootstrap negative branch. `openpyxl.load_workbook` is
  never rebound; no artifact lookup; no direct state (`sitecustomize.py:42-44`).
- Process ownership: target script process (ordinary openpyxl).
- Public or internal: behavior is public (ordinary execution + observer +
  receipt); mechanism is internal.
- Required dependencies: `openpyxl` only.
- Configuration inputs: admission decision; capture flag (observer still runs).
- Persistent state: `setup.json` (`route: REFERENCE_FAST_PATH`); observer
  receipt as usual.
- User-visible outputs: identical to direct Python plus receipt.
- Failure behavior: identical to direct Python; observer failures still apply.
- Evidence: Phase-10B pinned rerun: P4−P0 +6.39 ms median [5.63, 9.71] on the
  fixed 22, within the +10 ms budget; process fixtures 65/65 + 20/20.

## Stage 5b — direct runtime (admitted path)

- Files: `read_engine/runtime.py` (`Runtime.install`, `load_workbook`
  interposition, `ProxyWorkbook`/`ProxyWorksheet`/`ProxyCell`),
  `read_engine/direct.py` (`decode_xlsx`, lxml-based, no `load_workbook`),
  `read_engine/artifact.py` (encode/decode/validate/ensure/load),
  `read_engine/cache.py` (fast integrity gate + locked publication).
- Process ownership: target script process, process-local only.
- Public or internal: internal; narrow supported surface is behavioral:
  ordered sheet names + literal lookup, bounds/dimensions, literal/integer cell
  access, cell value/data type. Everything else lazily escapes to real openpyxl
  (`runtime.py:133-146, 172-208, 228-232`).
- Required dependencies: `openpyxl` (fallback + utilities + Translator +
  number formats), `lxml` (direct decode — hard import, `direct.py:13`).
- Configuration inputs: admitted context (workbook entries, merged certificate),
  cache root.
- Persistent state: `runtime_state.json` at exit (`atexit`), artifact files
  under `read-engine/`.
- User-visible outputs: script output; receipt route `DIRECT_RUNTIME` or
  `DIRECT_WITH_FALLBACK`, artifact statuses, fallback reasons.
- Failure behavior: per-load fallback to reference openpyxl on any artifact/
  decode failure (`runtime.py:83-86`); source rehash at first load closes the
  bootstrap-to-script race (`runtime.py:65-70`).
- Evidence: 543/543 oracle rows; fixed-22 contact regression (PROD/PY 0.468
  second-invocation); representative 7 direct-contact PROD/PY 0.608;
  corrupt/truncated/missing/stale injections rebuild.

## Stage 6 — cache / artifact / reference fallback

- Files: `read_engine/cache.py`, `read_engine/artifact.py`.
- Key: `sha256(source_sha|decoder|contract|format|runtime)`; format
  `JSONZ_MEMORY_V1`, contract `PHASE1_NARROW_V5`.
- Process ownership: target script process (bootstrap `ensure`, first-load
  rehash); publication under per-key `fcntl.flock` + temp file + fsync + atomic
  `os.replace` (`cache.py:130-148`, `artifact.py:245-257`).
- Required dependencies: POSIX `fcntl` (Linux-tested), filesystem with atomic
  rename + fsync.
- Configuration inputs: `cache_dir` (default `$XDG_CACHE_HOME/librecalc-agent`
  or `~/.cache/librecalc-agent`).
- Persistent state: `read-engine/<key>.r3jz` + `.r3jz.json` sidecar; no global
  quota (known gap, see cache lifecycle audit).
- Failure behavior: any validation failure → rebuild; build failure → per-load
  reference fallback recorded in `setup.fallback`.
- Evidence: concurrency test (BUILT+REUSED pair, valid final artifact);
  upgrade-invalidation keys; `test_corrupt_cache_rebuilds`,
  `test_source_change_invalidates`, `test_version_change_changes_artifact_key`.

## Stage 7 — script exit

- Ordinary Python exit: return code, `SystemExit`, uncaught exception,
  `os._exit`, or fatal signal. `Runtime.finish` runs via `atexit`
  (skipped on `os._exit`/signals — then `runtime_state.json` is absent and the
  receipt falls back to `setup.json`, `runner.py:105`).
- Observer `waitpid` records raw exit/signal (`observer.c:190-191`); on target
  signal the observer re-raises it to itself and returns 128+signo
  (`observer.c:222-227`), preserving shell signal semantics.

## Stage 8 — effect observation / capture

- Files: observer pre/post snapshots (`observer.c:92-114`), `_capture_helper.py`
  + `_frozen/capture.py` + `_frozen/delta.py` + `_frozen/validate.py`.
- Scope: recursive `*.xlsx` under workdir (excluding `*.tmp*` names),
  ≤1000 files / ≤512 MiB aggregate. Pre-bytes persisted only when a change is
  detected and capture is enabled.
- Helper runs as a separate Python child of the observer with
  `LIBRECALC_RUN_CONTEXT` unset (`observer.c:132-143`); exit 0 on
  full validation pass, 3 otherwise (`_capture_helper.py:22`).
- Evidence: 5/5 Phase-10 changed-file fixtures (package relation exact,
  changed XLSX detected, validation/replay pass); `test_changed_workbook_capture`;
  abrupt-exit capture checks.

## Stage 9 — receipt / status

- Files: observer receipt (`observer_receipt.json`), `runner.read_last_receipt`
  (`runner.py:83-134`), `diagnostics.status`, `cli.py` (`status`, `--json`).
- Fields: invocation id, route, read gate, artifact statuses, direct-served
  loads, fallback reasons, target exit/signal, assurance/capture/validation
  statuses, capture records, failure code, run dir.
- Rules: `REUSED` requires actual direct-serving contact, else
  `REUSE_NOT_CONFIRMED` (`runner.py:108-114`); changed bytes without passing
  capture → assurance `FAILED`; bootstrap failure on direct route → assurance
  `FAILED`, route demoted to reference; assurance `FAILED` + target success →
  command exit 125 (`runner.py:152-153`, `observer.c:228`).
- `status` reads the latest private receipt; `--json`/`--verbose` print the
  full report; default prints a short human summary (`cli.py:62-74`).

## Out-of-product (present in repo, not in the runtime path)

- `src/librecalc_mcp/` — historical MCP/UNO server; not imported by the agent,
  not in the wheel (`COMPATIBILITY.md`: UNSUPPORTED by this distribution).
- `_frozen/{index,reads,runtime,substrate}.py` — old SQLite-index read path and
  experimental live runtime; zero maintained consumers (see ownership census).
- `_frozen/{helpers,helper_common,period_constants}.py` + `src/lx_helpers.py` —
  reference-backend inspection helpers; consumed only by benchmark scripts and
  one legacy test, not by `run`.
- `benchmark/`, `research/`, `read_engine_phase*/`, `product_integration_*`,
  `product_hygiene/` — evidence and research archives, not shipped.
