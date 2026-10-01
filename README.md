# librecalc-agent

Run workbook tasks written in ordinary Python/openpyxl — with an optional
runtime underneath that can accelerate narrow reads, and an external observer
that records what happened.

> **ordinary Python, conditionally accelerated, externally observed**

Your scripts stay normal `.py` files using normal `openpyxl`. There is no new
workbook API to learn, no model account to configure, and no network access.
This package runs a script, optionally serves some of its reads from a derived
cache, watches the workbooks before and after, and writes a receipt separating
*what your script did* (target status) from *what was observed and checked*
(assurance status).

This is release candidate `0.2.0rc2`, Linux-first. It is not published to an
index. See [CHANGELOG.md](CHANGELOG.md) and
[docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md) for the
exact boundary of what is established, what is conditional, and what is not
claimed.

## Install

Linux x86_64, CPython 3.13 (3.11–3.14 accepted, 3.13 tested), local filesystem:

```bash
python3 -m venv .venv-product
. .venv-product/bin/activate
python -m pip install .
```

This installs `openpyxl`, the XML parser, the runtime, diagnostics, and the
`librecalc-agent` command (a small native launcher plus the Python CLI).
Installing from a built wheel needs no compiler; building from source needs
`cc` for two small C files. See [COMPATIBILITY.md](COMPATIBILITY.md) for the
supported baseline.

## Quick start

```bash
librecalc-agent example /tmp/librecalc-example
cd /tmp/librecalc-example
librecalc-agent run --workdir . ./create_input.py
librecalc-agent run --workdir . ./update.py
librecalc-agent run --workdir . ./read.py
librecalc-agent status
```

`example` copies three ordinary scripts (`create_input.py`, `update.py`,
`read.py`) plus a commented `runtime.toml`. `run` executes a script and prints
its normal output; `status` shows the last receipt.

## Public commands

```bash
librecalc-agent example <new-directory>   # copy the minimal example
librecalc-agent run --workdir <dir> <script.py> [script args...]
librecalc-agent doctor [--require-libreoffice] [--json] [--verbose]
librecalc-agent status [--json] [--verbose]
```

`--config <runtime.toml>` (or `LIBRECALC_CONFIG`) selects a configuration file;
`--no-runtime` runs with the optional runtime disabled. Harness flags go before
the script filename; anything after it is passed to the script.

## Ordinary Python execution

Scripts are ordinary Python files executed once in a real interpreter, with
stdout, stderr, argv, cwd, and exit status preserved. The harness does not rerun
failed scripts. `python task.py` remains valid for reference execution. The
runtime is scoped to the script launched by `run`; nested interpreters and
other Python processes are unaffected.

## How acceleration works

No extra workbook API is required. Before launch, a conservative whole-script
check (static admission) decides whether the script qualifies for the direct
read path:

- **Negative admission** (uncertain or unsupported scripts): the direct runtime
  is never loaded. The script runs on ordinary openpyxl. An external observer
  still records the run.
- **Positive admission**: supported reads — sheet names and literal lookup,
  worksheet bounds/dimensions, literal/integer cell access, cell value and
  data type — can be served from a persistent derived artifact instead of
  running the normal workbook parser for that load.

Anything outside that narrow surface — unsupported load options, iteration,
rich objects, writes, uncertain syntax — runs on real openpyxl through lazy
reference fallback, and the fallback is recorded in the receipt. Derived state
is keyed by whole-file SHA-256 plus runtime/decoder/contract/format versions;
a changed workbook or a new package version rebuilds instead of serving stale
data. There is no broad openpyxl-equivalence claim: proxy objects support the
narrow contract only (no identity, repr, style, or escape equivalence).

Cold runs are not accelerated: the first invocation builds state. Writes are
not accelerated. No token, cost, or benchmark-score claim is made.

## Effect observation

An external native process observes each run: it snapshots workbook bytes
before launch, waits for the real script process, snapshots again, and — only
when bytes changed and capture is enabled — runs a capture helper that derives
a package-level delta and mechanically validates it (persisted, serialization
valid, relationships preserved, captured == committed, replay reproduces the
parts).

The receipt keeps two outcomes distinct:

- **target status**: the script's exit code / signal.
- **assurance status**: `PASS`, `FAILED`, or `NOT_REQUESTED`.

Capture is assurance, not a correctness verdict: it records what the script
produced and checks the mechanics of the change; it never judges whether the
change is what the task wanted. Disabling capture (`capture = false`) or the
runtime (`--no-runtime`) reports `NOT_REQUESTED` and never implies validation.
If assurance fails while the script succeeded, the command exits `125`; if the
script failed, its own status is preserved and assurance failure stays visible
in the receipt.

The observer survives tested abrupt exits (`os._exit`, SIGTERM, exceptions)
so post-state is still examined. Observation covers recursive `*.xlsx` under
the workdir, up to 1,000 files / 512 MiB aggregate.

## Cache

Default location: `$XDG_CACHE_HOME/librecalc-agent`, or
`~/.cache/librecalc-agent`; override with `cache_dir` in `[runtime]`
(relative paths resolve beside the config file). Layout:

- `read-engine/` — persistent derived read artifacts (safe to delete while no
  invocation uses them; they rebuild).
- `runs/` — per-run receipts and debug bundles; `last_run.json` points at the
  latest run. Safe to delete; `status` then reports "none recorded".

Cache directories are created user-private (`0700`); symlinked roots are
rejected. There is **no automatic global eviction yet**: old entries from
edited workbooks or upgraded versions are orphaned, never served. `doctor`
and `status` report the location, a bounded size summary, and artifact count
so growth stays visible. Delete the directory (or the whole cache root) to
reclaim space.

## Configuration

Copy `examples/basic/runtime.toml` and pass it with `--config`:

```toml
[runtime]
enabled = true    # master switch for the optional runtime
reads = true      # direct-read acceleration (needs enabled)
capture = true    # changed-file effect capture (needs enabled)
verbosity = "normal"  # quiet | normal | verbose
# cache_dir = "/your/writable/cache/path"
```

An invalid configuration disables the optional runtime for that invocation
with a loud warning (fail-closed); the script still runs as ordinary Python.
`--no-runtime` / `LIBRECALC_NO_RUNTIME=1` does the same explicitly.

The old keys `substrate` and `candidate_a` are deprecated aliases of `reads`
for one window and warn when used; setting both `reads` and an alias is
invalid. See [CHANGELOG.md](CHANGELOG.md).

## Diagnostics

- `doctor` checks Python version, packages, runtime modules, the external
  observer, cache writability, configuration, and LibreOffice availability —
  without credentials. Results distinguish `PASS`, `WARNING`, `FAIL`, and
  `OPTIONAL_NOT_AVAILABLE`.
- `status` shows effective settings, versions, cache info, and the last
  recorded run. `--json` (or `--verbose`, which prints the same full report)
  gives the machine-readable shape; only the compact fields
  (`route`, `target_status`, `assurance_status`, `artifact`,
  `direct_served_loads`, `fallback`, capture/validation status, `failure_code`,
  `run_dir`) are stable. Run-dir internals are explicitly unstable support
  material.
- Exit codes: `0` success; `1` doctor/status check failure; `2`
  usage/config/launcher failure ("no task was run"); `125` assurance failure
  with a successful target, or observer self-failure; `127` target-exec
  failure; `128+signal` when the target dies by signal.

LibreOffice Calc matters only for tasks requiring recalculation or
LibreOffice validation: saving a formula with openpyxl does not calculate its
result. `--require-libreoffice` (on `doctor` and `run`) makes LibreOffice
absence a preflight failure; it does not recalculate anything. No UNO bindings
are required.

## Limitations

- Linux x86_64 with glibc, CPython 3.13 tested; local filesystems only.
  macOS is future fast-follow, Windows a separate port. Neither is supported.
- Narrow direct-read semantics; no broad openpyxl equivalence.
- No universal speedup. Reference-only scripts pay a small measured wrapper
  cost; cold runs are not faster; writes are not accelerated.
- No token, model-cost, or benchmark-score claims.
- Effect capture is mechanical assurance, not task-correctness certification.
- One writer per task directory; concurrently edited script sources are
  unsupported. This is not a sandbox: scripts run with your permissions.
- No automatic cache eviction (manual deletion documented above).

The full boundary is [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).

## Uninstall / cleanup

```bash
python -m pip uninstall librecalc-agent
rm -rf ~/.cache/librecalc-agent   # or your configured cache_dir
```

The cache holds only diagnostics and derived state — never workbook
authority. Deleting it cannot harm your workbooks.

## Security and resources

Bounded by design: ZIP member count and declared expansion, XML part sizes,
artifact compressed/uncompressed ceilings, sheet/cell/string limits, and
snapshot file-count/byte limits are enforced per layer; violations fall back
to reference openpyxl or fail loudly, never silently. Artifact deserialization
is JSON/zlib with full validation (no executable formats). The observer and
helpers are invoked by exact path with no shell. See
[docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md) for scope:
this review is bounded behavior, not a formal certification — and the harness
is not a sandbox.

## Repository map

- Current product docs: this file, [COMPATIBILITY.md](COMPATIBILITY.md),
  [CHANGELOG.md](CHANGELOG.md), [docs/](docs/).
- Integration records: `PRODUCT_INTEGRATION_*.md`, `PRODUCT_*_POLICY.md`,
  `PRODUCT_*_DESIGN.md`, `phase10c_audit/`, `phase10c_b/`.
- Historical evidence and research: [research/](research/), `benchmark/`,
  `read_engine_phase*/`, `product_integration_phase10*/`, `product_hygiene/`,
  and `*-REPORT.md` files. These preserve how the product was validated; they
  are not user documentation and may contain superseded wording.
- The old `0.2.0rc1` claim registry ([FINAL_CLAIM_REGISTRY.md](FINAL_CLAIM_REGISTRY.md))
  is retained as history and marked as such; it must not be used to describe
  this candidate.
