# README direction — benefits-first draft (FOR DISCUSSION, not release copy)

This is a structure + copy sketch for a benefits-first README. It has not been
through the claim-discipline review and must not be published as-is. Internal
terms (admission, frozen surface, phase numbers, benchmark populations) are
deliberately kept out of the top; they appear only in the deeper sections.

Proposed order follows the brief: why → what changes → what work is avoided
→ fallback → try it → limitations → deeper material.

---

# LibreCalc

**Faster repeated spreadsheet reads. Same ordinary openpyxl code.**

Every time a script opens a workbook, it pays to parse the XLSX and rebuild
the workbook in memory — even when nothing changed since the last run.
LibreCalc decodes the workbook once, saves that decoded state, and reuses it
on later runs, so repeated reads skip the repeated parsing.

When LibreCalc cannot safely serve an operation, your code runs on ordinary
openpyxl, untouched. Nothing silently changes meaning.

[demo animation: same script, plain Python → BUILT → REUSED → fallback]

## Why use this?

Agent workflows read the same workbooks over and over: check a total, scan a
column, verify an edit. Each run re-parses the whole file. LibreCalc turns
that repeated mechanical work into a decode-once, reuse-many-times pattern —
like a compiler cache or an incremental build, but for spreadsheet reads.

## What do you have to change?

Almost nothing. Keep writing ordinary Python:

```python
from openpyxl import load_workbook

wb = load_workbook("model.xlsx")
ws = wb["Forecast"]
print(ws["H402"].value)
```

The only change is how you invoke the script:

```bash
python read.py                        # as before
librecalc-agent run --workdir . ./read.py   # with LibreCalc underneath
```

No SDK, no DSL, no workbook API to learn.

## What work is avoided?

Before: every run pays the same price.

```text
run 1:  parse XLSX ──► build workbook ──► read cells
run 2:  parse XLSX ──► build workbook ──► read cells
run 3:  parse XLSX ──► build workbook ──► read cells
```

After: the decode is saved once and reused.

```text
run 1:  parse XLSX ──► save decoded state ──► read cells   (BUILT)
run 2:  load saved state ──► read cells                    (REUSED)
run 3:  load saved state ──► read cells                    (REUSED)
```

The demo prints its in-script read phase so you can see the repeated parsing
disappear across runs. Timings shown are from that demo run on that machine
only — the reusable point is the execution path, not a ratio.

[optional: small timing card generated from the demo run, clearly labeled]

## What happens when LibreCalc cannot help?

Some operations are outside what LibreCalc knows how to serve — row
iteration, ranges, rich objects, writes, anything it cannot recognize. Those
run on ordinary openpyxl, exactly as if LibreCalc were not there. The run
receipt says which path each run took, so you can always see what happened.

```text
Can LibreCalc serve this read from saved state?

YES ──► reuse the saved decode
NO  ──► ordinary openpyxl
```

LibreCalc does not need to understand all of openpyxl. Its value is owning a
narrow path well and getting out of the way everywhere else.

## Try it

Linux x86_64, CPython 3.13:

```bash
python3 -m venv .venv-product && . .venv-product/bin/activate
python -m pip install .
scripts/demo.sh          # reproducible demo with checks
```

The demo runs ordinary Python, then LibreCalc twice (BUILT → REUSED), verifies
identical results, and shows an unsupported operation taking the reference
path. `scripts/demo.sh --check` replays the same assertions without the
transcript.

## Limitations (short, honest)

- Repeated reads only: the first run decodes (no cold-start win); writes are
  never accelerated.
- A narrow, documented read surface; everything else stays on openpyxl.
- Linux-first release candidate; no universal speedup claim; no token,
  model-cost, or task-score claims.
- Full boundary: [Evidence & limitations](docs/EVIDENCE_AND_LIMITATIONS.md).

## How it works (deeper)

[one reuse + fallback diagram — see DIAGRAM_DRAFT.svg]

- Your unchanged script runs in a real Python process.
- LibreCalc checks whether the script's reads are ones it can serve from
  saved state; uncertain or unsupported scripts never touch the fast path.
- Saved state is keyed to the exact workbook bytes plus the runtime version,
  so an edited workbook or an upgraded LibreCalc rebuilds instead of serving
  stale data.
- An external observer records each run separately from the script's own
  result: what your script did vs what was observed and checked.

Details live in the docs, not here: [Compatibility](../../../../../COMPATIBILITY.md),
[Evidence & limitations](docs/EVIDENCE_AND_LIMITATIONS.md),
[receipt fields](../../../../reports/PRODUCT_RECEIPT_SCHEMA.md), [changelog](../../../../../CHANGELOG.md).

---

## Notes for the discussion

- The "Before/After" strip above is the central mental model; the diagram and
  the demo animation should reinforce it, not introduce a second story.
- Internal terms to keep out of the hero: frozen surface, whole-script
  admission, artifact/cache internals, glibc floor, phase numbers,
  populations, confidence intervals, rc1 negative results.
- Research lineage (phases, populations, negative results) moves to a
  separate internal document; the public README links only to the short
  Evidence & limitations page.
- Every sentence above still needs the skeptical claim review before it
  becomes release copy — see ASSETS_AND_CLAIMS.md.
