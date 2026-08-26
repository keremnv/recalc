# Agent instructions

## Mission

Build a thick, deterministic, programmable Calc world for external coding agents.

## Non-goals

Do not add:

- an LLM dependency,
- prompts/planners inside the server,
- a chat UI,
- web search,
- Writer/Impress/Draw support,
- generic dataframe/scientific-computing replacements,
- speculative features not motivated by a benchmark task or a clearly documented architectural need.

## Priorities

1. SpreadsheetBench 2 compatibility and measurable task success.
2. Inspection quality.
3. Correct target selection.
4. Efficient multi-edit execution.
5. Dynamic correctness after recalculation/input changes.
6. Transactions / semantic diffs.

## Architectural rule

Keep domain semantics independent of UNO. Code should depend on `CalcBackend`, not directly on UNO, except in `backend/uno.py`.

This lets us:

- test without LibreOffice,
- compare alternate backends later,
- keep the world model stable if UNO details are ugly.

## Primitive design rule

Avoid both extremes:

- too thin: `click`, `type`, one-cell-at-a-time APIs;
- too high-level: `make_financial_model`, `build_sales_dashboard`.

Prefer orthogonal spreadsheet-semantic primitives that compose.

Flexibility lives in programs, not in minting a tool per miss and not in a generic shell.
Experiment overlays (for example formula-fill-only) are measurement instruments, not the product.

## Program execution

`program_execute` is a first experiment in amortizing tool/model round trips. Keep it deterministic and inspectable. Do not execute arbitrary Python supplied by the model in v0.

## Changes

When adding a tool or operation, add at least one test against the in-memory backend first.
