# recalc demo fixture

A small, readable workbook plus two ordinary openpyxl scripts. No SDK, no DSL,
no rewrite: both scripts also run under plain `python`.

## Files

- `model.xlsx` — the demo workbook (checked in; regenerate with
  `python generate_model.py`). Sheet `Forecast`: 400 entries across three
  regions plus a totals row, so `H402` is the total margin. Sheet `Regions`:
  a three-row lookup table.
- `generate_model.py` — deterministic generator. Every cell value is a pure
  function of (row, column); workbook properties use a fixed timestamp.
- `read.py` — supported reads only (sheet names, literal sheet lookup,
  dimensions, literal/integer cell access, values). recalc can serve this
  from reusable decoded state. (Named `read.py`, not `inspect.py`, so it does
  not shadow the standard library.)
- `unsupported.py` — row iteration (`iter_rows`), which is outside the
  supported read surface. recalc runs it on ordinary openpyxl instead of
  pretending to accelerate it.

## Run it

From this directory, with a fresh demo cache:

```bash
python read.py                                      # ordinary Python
XDG_CACHE_HOME=/tmp/lc-demo recalc-agent run --workdir . ./read.py         # first run: BUILT
XDG_CACHE_HOME=/tmp/lc-demo recalc-agent run --workdir . ./read.py         # second run: REUSED
XDG_CACHE_HOME=/tmp/lc-demo recalc-agent run --workdir . ./unsupported.py # reference path
```

Or run the full reproducible demo with checks from the repo root:

```bash
scripts/demo.sh          # human-readable transcript
scripts/demo.sh --check  # assertion-only mode (exit nonzero on mismatch)
```

Both scripts print their in-script read phase (parse + reads) on stderr so
the demo can show the mechanical work per run; results go to stdout so they
stay byte-comparable. Timings shown by the demo are wall clock on the demo
machine only, not a benchmark. The point of the demo is the execution path
(direct reuse vs reference openpyxl) and identical results, not a speedup
ratio.
