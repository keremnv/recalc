# librecalc-mcp

An **agent-native programmable LibreOffice Calc world** exposed through MCP.

This is deliberately **not** a chat interface and **not** an embedded agent. The host agent (Codex, Claude Code, Cursor, etc.) owns reasoning, web access, Python, shell use, and planning. This project owns a deterministic semantic interface to Calc.

## v0 thesis

Compare three interaction layers for spreadsheet agents:

1. low-level tools,
2. semantic spreadsheet tools,
3. semantic tools + one-call program/batch execution.

The initial north star is **SpreadsheetBench 2**. Do not add features merely because they sound useful; add them when a benchmark failure exposes a missing world abstraction.

## Architecture

```text
Host agent
  |  reasoning / shell / Python / web / files
  v
MCP server
  |
  +-- inspection tools
  +-- deterministic writes
  +-- batch/program execution
  v
Calc domain layer
  v
UNO adapter
  v
LibreOffice Calc
```

The MCP server is not an agent. No model calls belong in this repository.

## Current tools

The initial server exposes:

- `calc_health` — check whether LibreOffice is reachable.
- `workbook_inspect` — get workbook/sheet structure and used ranges.
- `range_read` — read values, formulas, and calculated formula errors from a range.
- `range_write` — write rectangular values and persist in place or to an output copy.
- `program_execute` — execute a batch of deterministic Calc operations in one MCP call.

`program_execute` is intentionally small. It is the seed of the future generated-program layer, not the final DSL.
Its current operations are `write_range`, `set_formula`, `fill_formula`, `clear_range`, and
`create_sheet`. `fill_formula` deterministically translates relative A1 references across and
down a range, while `clear_range` removes cell contents without discarding formatting.

## Prerequisites

- Python 3.11+
- `uv` recommended
- LibreOffice Calc
- Python UNO bindings available to the Python process running the server

On Debian/Ubuntu, UNO is commonly provided by the distro's LibreOffice/Python packages rather than PyPI. Verify with:

```bash
python -c 'import uno; print("UNO OK")'
```

If that fails, first locate the Python environment shipped/used by LibreOffice or install the distro UNO binding package appropriate to your system.

## Start LibreOffice as an API runtime

LibreOffice supports headless/API-controlled operation and a UNO accept socket. The repo defaults to `localhost:2021`.

```bash
./scripts/start_libreoffice.sh
```

Equivalent command:

```bash
libreoffice --headless --nologo --nodefault --norestore \
  --accept='socket,host=localhost,port=2021;urp;StarOffice.ServiceManager'
```

## Install

```bash
uv venv --python /usr/bin/python3 --system-site-packages
uv sync --extra dev --python .venv/bin/python
```

The explicit environment creation matters on Linux systems where UNO is installed into the
distribution Python rather than a Conda, pyenv, or uv-managed Python. Confirm the resulting
environment can see both project and native dependencies:

```bash
.venv/bin/python -c 'import mcp, uno; print("MCP + UNO OK")'
```

Run tests that do not require LibreOffice:

```bash
uv run pytest
```

Run the opt-in real UNO integration test after starting LibreOffice:

```bash
LIBRECALC_RUN_UNO=1 uv run pytest -m uno
```

Run the MCP inspector:

```bash
uv run mcp dev src/librecalc_mcp/server.py
```

Or run the server over stdio:

```bash
uv run librecalc-mcp
```

## Smoke test UNO directly

With LibreOffice running:

```bash
uv run python scripts/smoke_uno.py
```

## Persistence semantics

For `range_write` and `program_execute`:

- `path` only: load and update that workbook in place.
- `path` plus `output_path`: load the source and save a separate output workbook.
- `output_path` only: edit the active Calc document and save an output workbook.
- neither path: edit the active document without saving it.

Benchmark tasks should use separate input and output paths so the input artifact remains unchanged.

## Design constraint

When deciding whether functionality belongs here, use this rule:

> The host owns arbitrary computation. This project owns computation that has persistent meaning inside the spreadsheet world.

Good examples:

- formulas,
- workbook-native transformations,
- table/range structure,
- dependency/lineage inspection,
- charts/pivots,
- transactions and semantic diffs.

Bad examples:

- rebuilding pandas,
- generic web scraping,
- generic statistical packages,
- another LLM planner.

## v1 target

A stock coding agent should be able to take an unfamiliar workbook and, using this server as its spreadsheet interface:

1. inspect it,
2. synthesize a multi-step program,
3. modify it in a bounded way,
4. recalculate/validate it,
5. leave behind a native workbook whose formulas still work when inputs change.

See `docs/roadmap.md` and `AGENTS.md` before adding scope.
