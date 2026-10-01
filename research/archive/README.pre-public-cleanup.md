# librecalc-agent

A small harness for workbook tasks written in ordinary Python/openpyxl. Use your existing coding agent and model; this package runs its Python scripts with optional conservative read acceleration and transparent mutation assurance. Acceleration depends on the workload.

## Install

From this repository checkout, use Python 3.11–3.14 and one isolated environment:

```bash
python3 -m venv .venv-product
. .venv-product/bin/activate
python -m pip install .
```

This is the canonical installation path for `0.2.0rc1`; it is not a published package release. It installs openpyxl, the XML parser, the local runtime and diagnostics. Research datasets, model SDKs and the historical MCP/UNO server are excluded.

## Prerequisites

A Linux/POSIX shell and Python with `venv`, pip and SQLite support are the tested setup. Network access is needed to resolve installation dependencies. No model credentials are needed for installation or local checks.

LibreOffice Calc is a separate system dependency **only for tasks requiring recalculation or LibreOffice validation**. Saving a formula with openpyxl does not calculate its result. Python UNO bindings are not required by this harness.

## Configure

Configure your coding agent/model through its own normal setup. Let it run Python scripts through the command below. This harness supplies no embedded model client or spreadsheet-specific planning interface.

Defaults enable the optional runtime. To customize them, copy `examples/basic/runtime.toml` and pass it with `--config` (or set `LIBRECALC_CONFIG`):

```toml
[runtime]
enabled = true
substrate = true
candidate_a = true
capture = true
verbosity = "normal"
# cache_dir = "/your/writable/cache/path"
```

`candidate_a` controls conservative read acceleration; it requires `substrate`. Capture is independent. Turning off compiled reads also disables their freshness machinery. Verbosity accepts `quiet`, `normal`, or `verbose`. The default cache is `$XDG_CACHE_HOME/librecalc-agent`, or `~/.cache/librecalc-agent`; missing directories are created. Relative configured cache paths resolve beside the configuration file.

## Run the minimal example

After installation, from any directory:

```bash
librecalc-agent example /tmp/librecalc-example
librecalc-agent run --workdir /tmp/librecalc-example /tmp/librecalc-example/create_input.py
librecalc-agent run --workdir /tmp/librecalc-example /tmp/librecalc-example/update.py
```

The update script is ordinary Python:

```python
import openpyxl

wb = openpyxl.load_workbook("example.xlsx")
ws = wb["Sheet1"]
ws["B2"] = "=A2*2"
wb.save("output.xlsx")
wb.close()
```

`/tmp/librecalc-example/output.xlsx` contains the formula. Use a dedicated task directory. Script arguments follow the script filename; harness flags go before it. The harness preserves script stdout, stderr and exit status, and does not rerun failed scripts.

## Optional invisible runtime

No extra workbook API is required. Eligible reads can use the conservative fast path. Writes and unsupported script shapes use real openpyxl; mutation capture observes and checks the resulting workbook bytes. Capture is assurance, not a formula-correctness check.

```bash
librecalc-agent run --workdir /tmp/librecalc-example /tmp/librecalc-example/read.py
librecalc-agent run --no-runtime --workdir /tmp/librecalc-example /tmp/librecalc-example/update.py
```

For reference execution, `python task.py` remains valid too. The runtime is scoped to the script launched by `librecalc-agent run`; it is not globally installed into every Python process. Existing optional `lx_helpers.search`, `periods`, `inspect`, and `inspect_ranges` always use reference openpyxl.

## Fallback

Unavailable optional modules, failed index setup, unsupported reads, and stale/corrupt indices lose acceleration. Ordinary openpyxl receives the original workbook and arguments. If the workbook itself is malformed, openpyxl may still raise its normal error; this harness does not repair it.

An invalid runtime configuration disables optional runtime for that invocation and explains how to fix it. An unavailable cache disables optimized reads; normal scripts and independently available capture continue. Diagnostic failures do not replace task output.

## Doctor and status

```bash
librecalc-agent doctor
librecalc-agent status
librecalc-agent doctor --require-libreoffice
librecalc-agent status --json
```

Doctor checks Python/packages, XML/SQLite support, writable cache, optional imports, configuration and LibreOffice availability/version, without credentials. Results distinguish `PASS`, `WARNING`, `FAIL` and `OPTIONAL_NOT_AVAILABLE`. `--require-libreoffice` makes absence a preflight failure; it does **not** perform recalculation. It is also available on `run`.

Status reports effective settings, versions, cache/log locations and the last recorded run. Use `--verbose` for internal fallback detail. Per-run logs live in the cache's `runs/` directory; `last_run.json` is a summary, not authoritative workbook state. Logs may contain file paths and hashes, so treat them as local task data.

## Limitations and evidence

See [COMPATIBILITY.md](COMPATIBILITY.md) for tested versions and platform limits. Use one writer per task directory. Only local Python scripts and top-level `.xlsx` read indexing are supported by this RC. Macro preservation, embedded objects, external links and untested environments retain openpyxl's caveats; capture does not restore content that Python removed. Existing startup customizations and arbitrary nested interpreters are not a supported acceleration path.

No task scoring or automatic recalculation is added. Scripts may invoke installed LibreOffice through their normal workflow. Cache retention/cleanup is manual in this RC: after tasks finish, the configured cache can be removed; it contains diagnostics and derived indexes, not workbook authority.

The scoped technical record is [FINAL_ARCHITECTURE_FREEZE.md](FINAL_ARCHITECTURE_FREEZE.md); installation validation and the exact RC boundary are in [PRODUCT_HYGIENE_REPORT.md](PRODUCT_HYGIENE_REPORT.md). The earlier MCP interface remains documented only in [the historical README](docs/HISTORICAL_MCP_README.md).
