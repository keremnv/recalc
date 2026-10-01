# Product surface audit

Everything externally observable, with contract classification.
Shrink before v1 freezes it.

## Executable / CLI

| Surface | Classification | Notes |
|---|---|---|
| `librecalc-agent` command name | PUBLIC CONTRACT | Installed via `shared_scripts`. Keep. |
| `run` subcommand + `script`, `script_args`, `--workdir` | PUBLIC CONTRACT | Core verb. Keep. |
| `example <dir>` | PUBLIC CONTRACT | Onboarding path; keep but see V1 note on example content. |
| `doctor` (+ `--json`, `--verbose`) | PUBLIC CONTRACT | Preflight; keep. `--require-libreoffice` keep. |
| `status` (+ `--json`, `--verbose`) | DOCUMENTED BUT OPTIONAL | Reads last receipt. Useful; could merge into `doctor` output, but harmless. Recommend keep. |
| `--config PATH` | PUBLIC CONTRACT | Keep. |
| `--no-runtime` | PUBLIC CONTRACT | Escape hatch to ordinary Python; keep (safety narrative depends on it). |
| `python -m librecalc_agent` | DOCUMENTED BUT OPTIONAL | Works via `__main__.py`; keep as fallback entry. |
| `librecalc_agent.cli:main(argv)` Python entry | IMPLEMENTATION DETAIL | Importable but not documented as API; do not promise stability. |
| `librecalc_agent.runner:run()` | IMPLEMENTATION DETAIL | Docstring says "Library/testing API". Tests use it. Do not advertise. |

## Flags/words to retire or rename before v1

| Surface | Classification | Notes |
|---|---|---|
| `--require-libreoffice` wording | PUBLIC CONTRACT (keep) | Honest: preflight only, "does not itself recalculate". |
| `substrate`, `candidate_a` config keys | RESEARCH TERM TO RETIRE | Migration aliases; user diagnostics already say "direct read engine". Rename window, then drop. |
| `read_gate` receipt field values (`A1_ADMIT`, `PREDECLARED_REAL_OPENPYXL`) | RESEARCH TERM TO RETIRE | Research-arm vocabulary in a user receipt. Route + fallback reasons already carry the meaning. |
| `DIRECT_RUNTIME` / `REFERENCE_FAST_PATH` / `DIRECT_WITH_FALLBACK` route labels | DOCUMENTED BUT OPTIONAL | Keep the 3-way distinction (it is load-bearing for support), but document as diagnostic, not API. |
| `REUSE_NOT_CONFIRMED`, `NOT_APPLICABLE` artifact states | DOCUMENTED BUT OPTIONAL | Honest states; document. |
| `CANDIDATE_A_*` env vars | RESEARCH TERM TO RETIRE | Only the dead `_frozen/runtime.py` reads them; runner strips them. Delete with that module. |

## Environment variables

| Variable | Classification | Notes |
|---|---|---|
| `LIBRECALC_CONFIG` | PUBLIC CONTRACT | Documented alt to `--config`. Keep. |
| `LIBRECALC_NO_RUNTIME=1` | DOCUMENTED BUT OPTIONAL | Alt to `--no-runtime`, honored by launcher + bootstrap fallback. Keep (cheap, tested implicitly). |
| `XDG_CACHE_HOME` | PUBLIC CONTRACT | Standard; keep. |
| `LIBRECALC_EFFECTIVE_CONFIG` | IMPLEMENTATION DETAIL | Internal handoff runner→bootstrap. Never document as user input. |
| `LIBRECALC_RUN_CONTEXT` | IMPLEMENTATION DETAIL | Internal handoff observer→bootstrap. |
| `LIBRECALC_RECEIPT_POINTER` | IMPLEMENTATION DETAIL | Concurrency-safe receipt discovery. |
| `LIBRECALC_CAPTURE_ENABLED` | IMPLEMENTATION DETAIL | Derived from config; not a user knob. |
| `PYTHONPATH` (managed) | IMPLEMENTATION DETAIL | Runner prepends import root; observer prepends bootstrap. Inherited paths preserved as absolute. |
| `CANDIDATE_A_*` | RESEARCH TERM TO RETIRE | See above. |

## Config file (`[runtime]` TOML)

| Key | Classification | Notes |
|---|---|---|
| `enabled` | PUBLIC CONTRACT | Master switch. Keep. |
| `capture` | PUBLIC CONTRACT | Effect-capture switch with truthful `NOT_REQUESTED`. Keep. |
| `cache_dir` | PUBLIC CONTRACT | Keep. |
| `verbosity` (`quiet/normal/verbose`) | DOCUMENTED BUT OPTIONAL | Only gates config-issue warnings today. Keep; low cost. |
| `substrate`, `candidate_a` | RESEARCH TERM TO RETIRE | See above. |
| Whole-file strictness (unknown key disables runtime + warning) | PUBLIC CONTRACT | Fail-closed behavior; keep and document. |

## stdout / stderr / exit codes

| Surface | Classification | Notes |
|---|---|---|
| Target script streams inherited byte-identical | PUBLIC CONTRACT | Tested (`test_script_process_metadata_and_exit`). Keep. |
| `example`/`doctor`/`status` human text | DOCUMENTED BUT OPTIONAL | Human-readable; `--json` is the stable machine shape. |
| `WARNING: ...` config-issue lines on stderr | DOCUMENTED BUT OPTIONAL | Keep. |
| Exit 0 success | PUBLIC CONTRACT | |
| Exit 1 `doctor`/`status` check failure | PUBLIC CONTRACT | |
| Exit 2 usage/config/launcher failure, "no task was run" | PUBLIC CONTRACT | Keep the "no task was run" wording — it is a safety promise. |
| Exit 125 assurance-failed-with-target-success; observer self-failure | PUBLIC CONTRACT | Document. |
| Exit 127 target-exec failure | IMPLEMENTATION DETAIL | Surfaced as target status; document briefly. |
| Exit 128+signo on target signal | PUBLIC CONTRACT | Standard shell semantics; keep. |
| Helper exit 3 | IMPLEMENTATION DETAIL | Internal; surfaces as 125 + `FAILED`. |
| `status` values `PASS/FAILED/NOT_REQUESTED` | PUBLIC CONTRACT | Keep trio. |

## Receipt / status fields (`status --json`)

| Field | Classification | Notes |
|---|---|---|
| `route`, `target_status`, `assurance_status` | PUBLIC CONTRACT | Minimal stable receipt. Keep. |
| `artifact`, `direct_served_loads`, `fallback` | DOCUMENTED BUT OPTIONAL | Needed to explain acceleration behavior. Keep. |
| `read_gate` | RESEARCH TERM TO RETIRE | Values are research vocabulary. Replace with `admitted: bool` + reason code in plain words, or drop (route implies it). |
| `effect_capture_status`, `validation_status`, `capture_records` | DOCUMENTED BUT OPTIONAL | Keep; they are the capture contract. |
| `failure_code` (`ASSURANCE_FAILURE`, `DIRECT_SETUP_UNAVAILABLE`, `OBSERVER_RECEIPT_MISSING`) | DOCUMENTED BUT OPTIONAL | Keep; actionable. |
| `invocation_id`, `run_dir` | SUPPORT/DEBUG (see receipt audit) | Keep `run_dir` (support needs it); id is harmless. |
| `profile_ns` (observer), `times`/`events` (runtime_state) | IMPLEMENTATION DETAIL | Research timing residue in run dirs. Keep behind the run dir, never in the compact receipt. |
| `merged_certificate` (setup.json) | SUPPORT/DEBUG | Keep in run dir, out of compact receipt. |

## Filesystem / cache

| Surface | Classification | Notes |
|---|---|---|
| `$XDG_CACHE_HOME/librecalc-agent` (or `~/.cache/...`) default | PUBLIC CONTRACT | Document + cleanup instructions (blocker-adjacent). |
| `runs/` receipts + `last_run.json` | DOCUMENTED BUT OPTIONAL | `status` depends on it. |
| `read-engine/*.r3jz` artifacts | IMPLEMENTATION DETAIL | Safe to delete when idle (document); never hand-edit. |
| `0700` private dirs, symlink rejection | PUBLIC CONTRACT | Security promise; keep. |
| `pre/*.bin`, `pre_index.tsv`, `context.txt`, `setup.json`, `runtime_state.json`, `capture*.json` in run dir | IMPLEMENTATION DETAIL | Support/debug bundle. Do not promise stability. |
| Example files (`create_input.py`, `read.py`, `update.py`, `runtime.toml`) | PUBLIC CONTRACT | `example` output shape; changing names breaks docs. |
| `lx_helpers` top-level import (`inspect`, `inspect_ranges`, `periods`, `search`) | ACCIDENTALLY EXPOSED | Ships in wheel; not part of `run` product. Migrate + remove (see removal audit). |

## Imported Python APIs

| Surface | Classification | Notes |
|---|---|---|
| `import librecalc_agent` (`__version__` only) | IMPLEMENTATION DETAIL | No public library API today. Keep it that way for v1 unless a library story is chosen (see extension points). |
| `import lx_helpers` | ACCIDENTALLY EXPOSED | See above. |
| `librecalc_agent._frozen.*`, `read_engine.*`, `_bootstrap.*` | IMPLEMENTATION DETAIL | Underscore + unadvertised; fine. |

## Fallback behavior (observable contract)

| Behavior | Classification | Notes |
|---|---|---|
| Negative admission → ordinary openpyxl, no artifact dir created | PUBLIC CONTRACT | Tested. |
| Unsupported load/proxy op → lazy reference openpyxl | PUBLIC CONTRACT | Tested via fallback row + proxies. |
| Corrupt/missing/stale artifact → rebuild, reference if build fails | PUBLIC CONTRACT | Tested injections. |
| `capture=false` / `--no-runtime` → `NOT_REQUESTED`, never fake validation | PUBLIC CONTRACT | Tested. |
| Missing observer / bad cache → block before launch, "no task was run" | PUBLIC CONTRACT | Tested. |
| Disabled runtime → direct Python, no observer | PUBLIC CONTRACT | Tested. |

## Pre-v1 surface cuts recommended

1. Retire `read_gate` research values from the compact receipt (keep in
   `setup.json` for support).
2. Rename/retire `substrate` + `candidate_a` config keys (migration window).
3. Remove `lx_helpers` from the wheel (migration window).
4. Strip `CANDIDATE_A_*` handling with dead `_frozen/runtime.py`.
5. Declare run-dir internals (`profile_ns`, `times`, `events`) explicitly
   unstable in docs.
