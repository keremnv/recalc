# recalc

An agent-native application substrate for spreadsheet work: a selective
execution and observation layer for ordinary Python/openpyxl spreadsheet agents.

Recalc runs your agent's Python scripts unchanged — no rewrites, no new
workbook API. Supported expensive reads can reuse validated workbook state
instead of re-parsing the file; anything unsupported or uncertain stays on
genuine openpyxl. An external observer records how each run executed and what
workbook effects it produced.

This is `0.2.0`, Linux-first. It is not published to an
index. The exact boundary of what is established, what is conditional, and
what is not claimed is [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).

## SpreadsheetBench-2 task: scanning assumptions in a financial model

One real read-only inspection step from a public benchmark trajectory
(SpreadsheetBench-2 FM:08_02 · Project Seafood Model). The agent scanned
`Assumptions - Line 01` of the benchmark workbook using ordinary
Python/openpyxl iteration. On the same workbook and code, the measured warm
step fell from **3.69 s** to **0.73 s** (medians of 3 warm reps, same window),
saving **2.95 s**, while producing the same findings. Input bytes were verified
unchanged. Full instruction, code, and raw rep timings:
[docs/evidence/readme_vignette/](docs/evidence/readme_vignette/).

![Measured vignette: one real read-only inspection step from the SpreadsheetBench-2 FM:08_02 agent trajectory; the frozen Assumptions-tab scan took 3.69 s under plain Python and 0.73 s under warm Recalc, saving 2.95 s (80.1% lower) with identical delivered findings](docs/assets/recalc-performance-vignette.svg)

Across the preregistered 30-workload read-heavy representative population used
to productize certified full-cell iteration, aggregate warm runtime changed
from **102.26 s** to **21.51 s**; artifact decode (D1) separately moved decode
mass from **5.014 s** to **1.896 s** with warm total **13.158 s** to
**10.157 s**, and peak RSS on the large confirmation workbook fell from
**997,968 KB** to **148,296 KB**. These are measured, workload-specific
results on the validation host — Recalc is not a universal openpyxl
accelerator.

Recalc materially helps when expensive spreadsheet reads fall within its
certified direct contract; mixed/dynamic workloads may remain on genuine
openpyxl and can see little or no speedup. In a later mixed-workflow
external-validity study, fully direct execution was uncommon and aggregate
replay showed no speedup; most dynamic and mixed read/write work correctly
remained on genuine openpyxl.

**Recalc helps when:**

- Reads are expensive (large workbooks, wide scans) and fall inside the certified direct contract
- The workbook has been seen before, so validated state is warm and reused

**Recalc won't help when:**

- It is the first/cold load — state must be built first
- Scripts are dynamic or mix reads with writes — they often stay on genuine openpyxl
- The work is writes — writes are not accelerated
- Reads use unsupported semantics — execution fails closed to the reference path

## Quick start

Linux x86_64, CPython 3.13 (3.11–3.14 accepted, 3.13 tested), local
filesystem:

```bash
python3 -m venv .venv-product
. .venv-product/bin/activate
python -m pip install .
```

This installs `openpyxl`, the XML parser, the runtime, diagnostics, and the
`recalc-agent` command (a small native launcher plus the Python CLI).
Installing from a built wheel needs no compiler; building from source needs
`cc` for two small C files. See [COMPATIBILITY.md](COMPATIBILITY.md) for the
supported baseline.

```bash
recalc-agent example /tmp/recalc-example
cd /tmp/recalc-example
recalc-agent run --workdir . ./create_input.py
recalc-agent run --workdir . ./update.py
recalc-agent run --workdir . ./read.py
recalc-agent status
```

`example` copies three ordinary scripts (`create_input.py`, `update.py`,
`read.py`) plus a commented `runtime.toml`. `run` executes a script and prints
its normal output; `status` shows the last receipt.

What to notice:

- The two write scripts run on the reference path.
- The supported read is served directly — the first read builds validated state (`BUILT`).
- Run `read.py` once more and `recalc-agent status --json` reports (excerpt):

```text
route: DIRECT_RUNTIME, artifact: REUSED, direct_served_loads: 1,
fallback: [], target: exit 0, assurance: PASS
```

Route tells how execution happened, target whether the script succeeded, and
assurance whether observed workbook effects passed mechanical checks.

## Substrate diagram

```text
                    AGENT-WRITTEN PROGRAM
                            │
                   existing interface
                    (plain openpyxl)
                            │
        ┌───────────────────┴───────────────────┐
        │          APPLICATION SUBSTRATE         │
        │                                       │
        │   EXECUTION              OBSERVATION   │
        │                                       │
        │   admission              before state  │
        │      ↓                       ↓         │
        │   validated              run observed  │
        │   workbook read state        ↓         │
        │      ↓                   after state   │
        │   supported reads            ↓         │
        │      │                   effect capture│
        │      └─ reference fallback   ↓         │
        │                          validation    │
        │                               ↓        │
        │                            receipt     │
        └───────────────────┬───────────────────┘
                            │
                         WORKBOOK
```

The agent-facing surface is the normal program and its existing interface.
The substrate underneath has two independent sides: execution, which may
serve supported reads from validated workbook read state or fall back to the
reference path; and observation, which watches workbook state before and
after the run and records the outcome in a receipt. Neither side requires
a recalc-specific workbook-intent API: the execution side changes how
supported reads may be served, while observation records what happened
around the run.

## What the substrate adds

Relative to running the same script directly with plain Python/openpyxl:

| Reference/plain execution | With recalc substrate |
| --- | --- |
| workbook follows normal load path | supported warm reads can reuse persistent, validated workbook read state |
| execution outcome is primarily process status/output | workbook effects are independently observed |
| unsupported optimization would otherwise require special handling | uncertain/unsupported paths use reference behavior |
| state reuse/freshness is not supplied by the execution layer | workbook read state is content-addressed and rebuilt when invalid |
| execution and post-state assurance are not separated | target and assurance outcomes are reported separately |

Nothing here replaces ordinary execution: the reference path remains
available through conservative admission and lazy fallback, and scripts
that never touch the supported surface use reference openpyxl behavior,
with the launcher and observer still surrounding execution.

### What is actually stored

```text
persistent, content-addressed workbook read state
├── workbook identity / freshness
└── sheets
    └── Forecast
        ├── bounds
        ├── merged ranges
        └── cells
            └── D12 → value + data type
```

The current persisted state is deliberately mechanical: it is decoded
from workbook data for the validated narrow read contract and holds the
mechanical state that contract needs — sheet names, bounds, merged
ranges, and sparse coordinate → value/data-type entries. It is
content-addressed and versioned, so stale or incompatible state is
rebuilt rather than served. It is not a semantic workbook model: it
derives no dependency graphs, no formula fingerprints as runtime
authority, no formula intent, no task semantics, and no plans or
mutation IR.

For example, in an admitted script with an eligible workbook:

```python
ws["D12"].value
```

conceptually maps to:

```text
Forecast / D12 / value
        ↓
workbook read state
        ↓
ordinary Python value
```

The operation resolves through the narrow proxy surface to the stored
workbook read state, and the program receives the ordinary Python value.
When an operation cannot be served under the narrow contract, execution
uses genuine reference openpyxl behavior.

## Current evidence snapshot

Product evidence below was established on `0.2.0rc2` and carried forward
through the rename-only `0.2.0rc3`. `0.2.0rc4` added the certified full-cell
`iter_rows` contract to the direct runtime, and `0.2.0rc5` decodes
already-validated typed values directly with no representation change (see
[docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md) and
[CHANGELOG.md](CHANGELOG.md)). `0.2.0` ships that mechanism set unchanged.
All timing figures are host- and
run-sensitive; the validation host is recorded in
[docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).

| Observation | Scope |
| --- | --- |
| 543 / 543 oracle rows show exit/stream/state parity with plain Python | ordinary execution surface |
| 0.608× median vs plain Python on warm direct-contact workloads | 7 frozen contact-selected workloads, warm reuse only |
| 1.04–1.12× plain Python on cold direct-contact runs: no cold acceleration | cold runs; first invocation builds state |
| 5 frozen changed-file fixtures: changed-XLSX detection, mechanical validation, delta replay | changed-file capture/assurance |

In short: warm direct-contact acceleration is real on the tested narrow
surface; cold state construction produces no speedup; the normal execution
surface has been parity-tested; and assurance is mechanical — it checks
what the change is and that it replayed, never whether the change is what
the task wanted.

## How it works

### Before: admission, identity, observation setup

- **Admission/eligibility.** A conservative whole-script check (static
  admission) decides whether the script qualifies for the direct read path.
  Uncertain or unsupported scripts are routed to ordinary openpyxl without
  ever loading the direct runtime.
- **Source/workbook identity.** Workbook read state is keyed by whole-file SHA-256
  plus runtime/decoder/contract/format versions, so a changed workbook or a
  new package version rebuilds instead of serving stale data.
- **Validated reuse or rebuild.** A matching artifact is validated before
  serving; corrupt, missing, stale, or incompatible entries rebuild, and a
  second source hash at first load closes the bootstrap-to-script race.
- **Pre-run observation.** The external observer snapshots workbook bytes
  before launch.

### During: one ordinary execution

- The script executes once in a real interpreter, with stdout, stderr, argv,
  cwd, and exit status preserved. The harness does not rerun failed scripts,
  and `python task.py` remains valid for reference execution.
- Supported direct reads — sheet names and literal lookup, worksheet
  bounds/dimensions, literal/integer cell access, cell value and data type,
  and the certified full-cell `iter_rows` contract — may be served from the
  persistent read artifact instead of running the normal workbook parser
  for that load.
- Anything outside that narrow surface — unsupported load options,
  uncertified iteration, rich objects, writes, uncertain syntax — runs on
  real openpyxl through lazy reference fallback, and the fallback is
  recorded in the receipt.

### After: observation, capture, receipt

- Final workbook state is observed: the native parent waits for the real
  script process (surviving tested abrupt exits such as `os._exit`, SIGTERM,
  and exceptions), then snapshots again.
- Changed files may be captured: only when bytes changed and capture is
  enabled, a capture helper derives a package-level delta and mechanically
  validates it (persisted, serialization valid, relationships preserved,
  captured == committed, replay reproduces the parts).
- Effects are mechanically validated and replayed where supported; full
  details are in [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).
- The receipt records two outcomes separately: **target status** (the
  script's exit code / signal) and **assurance status** (`PASS`, `FAILED`,
  or `NOT_REQUESTED`).

The supported read surface and fallback boundaries above are the contract.
There is no broad openpyxl-equivalence claim: proxy objects support the
narrow contract only (no identity, repr, style, or escape equivalence).

## Public commands

```bash
recalc-agent example <new-directory>   # copy the minimal example
recalc-agent run --workdir <dir> <script.py> [script args...]
recalc-agent doctor [--require-libreoffice] [--json] [--verbose]
recalc-agent status [--json] [--verbose]
```

`--config <runtime.toml>` (or `RECALC_CONFIG`) selects a configuration file;
`--no-runtime` runs with the optional runtime disabled. Harness flags go before
the script filename; anything after it is passed to the script.

## Ordinary Python execution

Scripts are ordinary Python files. The runtime is scoped to the script
launched by `run`; nested interpreters and other Python processes are
unaffected.

## Direct reads and fallback

No extra workbook API is required. As described above, static admission
routes each script before launch: uncertain or unsupported scripts never
load the direct runtime, while admitted scripts may have supported reads
served from the persistent read artifact.

The following lazily use real openpyxl and are recorded in the receipt:

- Unsupported load modes
- Proxy escapes
- Uncertified iteration
- Artifact/decoder failures

Representative fallback-after-contact behavior is covered by tests.

Cold runs are not accelerated: the first invocation builds state. Writes are
not accelerated. No token, cost, or benchmark-score claim is made.

## Effect observation

Observation covers recursive `*.xlsx` under the workdir, up to 1,000 files /
512 MiB aggregate.

- Capture is assurance, not a correctness verdict: it records what the script produced and checks the mechanics of the change; it never judges whether the change is what the task wanted.
- Disabling capture (`capture = false`) or the runtime (`--no-runtime`) reports `NOT_REQUESTED` and never implies validation.
- If assurance fails while the script succeeded, the command exits `125`; if the script failed, its own status is preserved and assurance failure stays visible in the receipt.

## Cache

Default location: `$XDG_CACHE_HOME/recalc-agent`, or
`~/.cache/recalc-agent`; override with `cache_dir` in `[runtime]`
(relative paths resolve beside the config file). Layout:

- `read-engine/` — persistent read artifacts (safe to delete while no
  invocation uses them; they rebuild).
- `runs/` — per-run receipts and debug bundles; `last_run.json` points at the
  latest run. Safe to delete; `status` then reports "none recorded".

Cache directories are created user-private (`0700`); symlinked roots are
rejected. There is **no automatic global eviction yet**: old entries from
edited workbooks or upgraded versions are orphaned, never served. `doctor`
and `status` report the location, a bounded size summary, and artifact count
so growth stays visible. Delete the directory (or the whole cache root) to
reclaim space.

Upgrading `recalc-agent` orphans prior artifacts by versioned key; the first
touch under the new version rebuilds automatically. No manual cache migration
is ever required; stale entries stay inert on disk until deleted.

Concurrency: simultaneous reads, simultaneous same-artifact builds (one
builder wins under a per-key lock; the other reuses the result), reads
during a build, and crashes mid-publication are safe — validation plus
atomic publication mean torn or partial state is never served. Concurrent
editing of the same task/script directory and external writer races outside
this model are unsupported (see [COMPATIBILITY.md](COMPATIBILITY.md)).

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
`--no-runtime` / `RECALC_NO_RUNTIME=1` does the same explicitly.

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

## Uninstall / cleanup

```bash
python -m pip uninstall recalc-agent
rm -rf ~/.cache/recalc-agent   # or your configured cache_dir
```

The cache holds only diagnostics and workbook read state — never workbook
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

## Why this shape?

This architecture was reached empirically rather than imposed as a doctrine.
The underlying idea is simple: preserve a compositional application
interface, and place mechanically exact infrastructure underneath it when the
evidence supports doing so.

During the research program, richer agent-facing structures around
context, planning, querying, execution, and verification were tested
rather than assumed beneficial; they generally did not establish enough
task-level benefit to justify becoming required interface structure.
Narrower deterministic mechanisms were retained where the evidence
supported them, and semantic abstractions remain hypotheses rather than
presumed improvements.

That is a statement about this project's evidence, not a universal rule for
agent systems. The research record is summarized below; it exists to explain
the shape, not to relitigate every experiment on this page.

## Evidence and limitations

The claim boundary for this candidate:

- no universal speedup claim;
- no cold acceleration claim;
- no write acceleration claim;
- no token/model-cost claim;
- no benchmark-score improvement claim;
- no task correctness/output certification claim;
- no broad openpyxl-equivalence claim;
- timing measurements are host/run-sensitive and never averaged across hosts.

Product limits also include: Linux x86_64 with glibc, CPython 3.13 tested;
local filesystems only; macOS is future fast-follow, Windows a separate port
(neither supported); one writer per task directory with concurrently edited
script sources unsupported; no automatic cache eviction; and no sandbox —
scripts run with your permissions.

The full boundary is [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).

## Research background

The architecture emerged from experiments around access/read cost, context
representation, planning/authority, execution mechanisms, verification,
evaluation state, and residual failure analysis. The durable outcomes were:
a narrow direct-read path exact enough to productize, an external observer
worth keeping as assurance, and a set of richer abstractions that did not
earn a place in the required interface.

The most useful synthesis and decision documents are:

- [phase13/PROGRAM_SYNTHESIS.md](research/history/phase13/PROGRAM_SYNTHESIS.md) — causal map
  of where the loss boundary moved and why.
- [phase13/ARCHITECTURE_DECISION_LEDGER.md](research/history/phase13/ARCHITECTURE_DECISION_LEDGER.md) —
  adopted/rejected choices with evidence, scope, and reopen conditions.
- [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md) —
  the current product claim boundary.

Research supports the architecture; it is not the product. Historical
records may contain superseded wording and must not be quoted as product
claims.

## Product and release status

`recalc-agent 0.2.0` is a Linux-first release, not yet
published to an index, under the MIT License (see [LICENSE](LICENSE) and
[CHANGELOG.md](CHANGELOG.md)). The tested baseline is Linux x86_64 with
glibc, CPython 3.13, pinned `openpyxl`/`lxml`, and a local filesystem; see
[COMPATIBILITY.md](COMPATIBILITY.md) for the full supported/tested boundary,
including the macOS fast-follow and Windows separate-port posture.

## Repository map

- Current product docs: this file, [COMPATIBILITY.md](COMPATIBILITY.md),
  [CHANGELOG.md](CHANGELOG.md), [docs/](docs/).
- Integration records: `research/reports/PRODUCT_INTEGRATION_*.md`,
  `research/reports/PRODUCT_*_POLICY.md`, `research/reports/PRODUCT_*_DESIGN.md`,
  `research/history/phase10c_audit/`, `research/history/phase10c_b/`.
- Historical evidence and research: [research/](research/), `benchmark/`,
  `read_engine_phase*/`, `research/history/product_integration_phase10*/`,
  `research/history/product_hygiene/`, and the `research/reports/*-REPORT.md`
  files. These preserve how the product was validated; they are not user
  documentation and may contain superseded wording.
- The old `0.2.0rc1` claim registry ([FINAL_CLAIM_REGISTRY.md](research/reports/FINAL_CLAIM_REGISTRY.md))
  is retained as history and marked as such; it must not be used to describe
  this candidate.
