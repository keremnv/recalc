# recalc

An agent-native application substrate for spreadsheet work: a selective
execution and observation layer for ordinary Python/openpyxl spreadsheet agents.

Recalc runs your agent's Python scripts unchanged — no rewrites, no new
workbook API. Supported warm reads can reuse validated workbook read state
instead of re-parsing the file; anything unsupported or uncertain stays on
genuine openpyxl. An external observer records how each run executed and what
workbook effects it produced.

`recalc-agent 0.2.0`, Linux-first, not published to an index.
Quantitative evidence: [PERFORMANCE.md](PERFORMANCE.md) ·
semantic boundary: [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md) ·
support matrix: [COMPATIBILITY.md](COMPATIBILITY.md).

## The cost Recalc targets

In spreadsheet-agent workflows that execute multiple ordinary Python
invocations against the same workbook, each `load_workbook` can parse
and materialize workbook state again even when the workbook has not
changed since the last invocation. When reading is substantial, that
repeated work can become a meaningful share of execution time.

Recalc targets that repeated read cost only. It does not accelerate
writes, cold first-touch construction, or work outside its certified
read contract.

## How Recalc removes that cost

Each invocation passes conservative admission. Certified reads may be
served from validated workbook read state; everything else runs on
genuine openpyxl. Either way, the script keeps its ordinary
Python/openpyxl interface and semantics, and the execution route is
recorded in a receipt.

```text
ordinary Python/openpyxl
          |
 conservative admission
      /          \
reference      direct path eligible
openpyxl             |
     |         supported reads
     |               |
     |      validated workbook state
     |               |
     +----> execution
                 |
       (fallback if needed)
                 |
               receipt
```

Fallback is a designed outcome, not an error: uncertain or unsupported
work keeps openpyxl ownership throughout.

## Measured on SpreadsheetBench-2

Warm paired task-execution replays of specific model trajectories,
BASE (plain Python) vs released Recalc 0.2.0:

| SpreadsheetBench-2 replay | BASE | Recalc 0.2.0 | Change |
| --- | ---: | ---: | ---: |
| Debugging:07_01 · Claude trajectory | 15.477 s | 13.210 s | −14.6% |
| Financial_Model:11_05 · Mimo trajectory | 28.001 s | 26.141 s | −6.6% |

In the first replay, 3 of 13 invocations were directly served (63
reads); their BASE time was 21.3% of the replay. In the second, 5 of
23 were served (9,271 reads, 5,822 iteration cells); 15.8% of BASE
time. These are specific trajectory results — not model-in-the-loop
end-to-end timings, and not family-wide claims. Methodology and
provenance: [PERFORMANCE.md](PERFORMANCE.md).

> **Boundary case.** On Debugging:08_06 (Mimo trajectory), the served
> block improved (0.614 → 0.356 s) but the complete task replay did
> not (12.254 → 13.176 s, +7.5%): the served block represented
> about 5% of BASE replay time. Recalc can make a directly served
> block faster without moving the task when most runtime lies
> elsewhere.

## When Recalc is a good fit

**Recalc helps most when expensive workbook reading, on state already
validated once, accounts for a meaningful share of the run.**

Strong-fit characteristics observed so far:

- workbook read state can be reused (warm);
- workbook reading is materially expensive;
- reads fall inside the certified direct contract;
- directly served read work represents enough execution cost to matter.

Little or no task-replay benefit has been observed when:

- execution is a cold first touch;
- reads are cheap or small;
- mutation-containing invocations dominate;
- unsupported or dynamic read semantics dominate;
- most runtime lies in unrelated Python, LibreOffice/recalculation,
  XML manipulation, or other reference execution.

Note on units: a mutation-containing invocation is reference-routed,
but separate certified read-only invocations may still be directly
served inside a larger trajectory that also contains writes. No
numeric fit threshold is established.

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

What to notice: the two write scripts run on the reference path, while
the supported read is served directly — the first read builds validated
state (`BUILT`). Run `read.py` once more and `recalc-agent status
--json` reports (excerpt, exact field names):

```text
route: DIRECT_RUNTIME
artifact: [REUSED]
direct_served_loads: 1
fallback: []
target_status: { exit_code: 0, signal: null }
assurance_status: PASS
```

Route tells how execution happened; `direct_served_loads` whether
Recalc actually served workbook loads; `fallback` whether and why
execution returned to genuine openpyxl; target status is the script's
own outcome; assurance status is the mechanical post-state check.

## How Recalc works

Ordinary Python/openpyxl remains the agent interface; mechanically
exact complexity lives underneath it. No Recalc-specific workbook
DSL, no rewritten logic.

**Execution.** Conservative whole-script admission decides whether an
invocation qualifies for the direct path; uncertain scripts never load
the direct runtime. Supported reads — sheet names and lookup,
bounds/dimensions, point-cell access, value/data type, and the
certified full-cell `iter_rows` contract — may be served from
validated workbook read state instead of re-parsing. Anything else
runs on genuine openpyxl through lazy reference fallback.

**Observation.** An external native observer snapshots workbook bytes
before launch, waits for the real script process (surviving tested
abrupt exits), snapshots again, and records the outcome in a receipt:
target status (exit code/signal) separate from assurance status
(`PASS`, `FAILED`, `NOT_REQUESTED`).

Persisted state is deliberately mechanical — workbook identity and
freshness, sheet bounds, merged ranges, sparse coordinate →
value/data-type entries:

```text
validated workbook read state
└── sheets
    └── Forecast
        ├── bounds
        ├── merged ranges
        └── cells
            └── D12 → value + data type
```

It is content-addressed and versioned, so stale or incompatible state
rebuilds rather than serving. Full semantic boundary:
[docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).

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

## Configuration and cache

Copy `examples/basic/runtime.toml` and pass it with `--config`:

```toml
[runtime]
enabled = true    # master switch for the optional runtime
reads = true      # direct-read serving (needs enabled)
capture = true    # changed-file effect capture (needs enabled)
verbosity = "normal"  # quiet | normal | verbose
# cache_dir = "/your/writable/cache/path"
```

An invalid configuration disables the optional runtime for that invocation
with a loud warning (fail-closed); the script still runs as ordinary Python.
`--no-runtime` / `RECALC_NO_RUNTIME=1` does the same explicitly.

Default cache: `$XDG_CACHE_HOME/recalc-agent`, or `~/.cache/recalc-agent`.
`read-engine/` holds validated read artifacts (safe to delete while unused;
they rebuild); `runs/` holds receipts (`last_run.json` points at the latest;
safe to delete — `status` then reports "none recorded"). Cache roots are
user-private (`0700`); symlinked roots are rejected. There is no automatic
eviction: orphaned entries stay inert until deleted. Upgrading `recalc-agent`
orphans prior artifacts by versioned key; the first touch rebuilds
automatically.

Uninstall:

```bash
python -m pip uninstall recalc-agent
rm -rf ~/.cache/recalc-agent   # or your configured cache_dir
```

The cache holds only diagnostics and workbook read state — never workbook
authority. Deleting it cannot harm your workbooks.

## Compatibility and limitations

Tested baseline: Linux x86_64 with glibc, CPython 3.13, pinned
`openpyxl`/`lxml`, local filesystem. macOS and Windows carry no
validation claim; concurrently edited task directories are
unsupported; scripts run with your permissions — the harness is not a
sandbox. Enforced bounds (package sizes, artifact ceilings, snapshot
limits) fall back to reference openpyxl or fail loudly, never
silently. Full matrix: [COMPATIBILITY.md](COMPATIBILITY.md); semantic
boundary: [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).
Recalc is under the MIT License (see [LICENSE](LICENSE)).

## Development

```bash
python -m pytest tests/test_product_hygiene.py tests/test_product_process_semantics.py
```

These two files are the maintained product/process regression gate.
The wider `tests/` tree largely covers frozen research and benchmark
history rather than the shipped runtime.

## Evidence

- **Performance:** [PERFORMANCE.md](PERFORMANCE.md) —
  task-replay cases, the released-product inspection example,
  counterexamples, mechanism-population evidence, workload fit,
  cold/write/memory measurements, methodology.
- **Evidence & limitations:**
  [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md) —
  semantic parity, certified contract, fallback, persisted-state
  integrity, observation and assurance.
- **Compatibility:** [COMPATIBILITY.md](COMPATIBILITY.md) —
  tested platforms, dependencies, operational support matrix.
- **Release history:** [CHANGELOG.md](CHANGELOG.md).
- **Research archive:** [research/](research/) preserves how the
  product was validated, including the benefit ledger
  ([research/benefit_evidence_ledger/](research/benefit_evidence_ledger/)).
  Historical records may contain superseded wording and must not be
  quoted as product claims.
