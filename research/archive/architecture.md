# Architecture

## Boundary

The project exposes a **world**, not an intelligence layer.

```text
natural-language intent
        |
        v
external coding agent
        |
        | writes tool calls / temporary programs
        v
librecalc-mcp
        |
        | typed deterministic semantics
        v
Calc backend
        |
        v
LibreOffice UNO
```

## Layers

### MCP surface

Small tools for discovery/debugging plus one multi-operation execution tool.

### Domain layer

Stable Python types for workbook structure, ranges, operations, and results.

Also the **observation models** (`domain/observation.py`, `domain/diff.py`,
`domain/grid.py`): structure manifests, formula patterns, anomaly shortlists,
dependency bridges, and semantic diff. Observation is a compiled interface, not a
dump, and it is half the world -- so it belongs here, behind `CalcBackend`, not in a
benchmark harness. Deterministic workbook facts stay in different fields from
heuristic affordances, and heuristics are always labelled as such.

The dividing line against the harness: anything that shapes *what the agent sees* is
domain. Anything that rations, strips, or instruments the loop in order to measure it
-- read budgets, tool-set overlays, prompt variants -- is a measuring instrument and
lives in `benchmark/`.

### Backend interface

A protocol separating spreadsheet semantics from UNO details. Operations include range
read/write, formula fill, clear, sheet create, and row insert/delete. Geometry ops are
algebra, not task-specific restore tools.

### UNO adapter

The only layer allowed to know `com.sun.star.*` details.

## Future transaction model

Target execution shape:

```text
snapshot -> execute -> recalculate -> validate -> diff -> commit/rollback
```

Version control should be semantic, not merely binary file copies. A future diff should be able to report formula, range, sheet, chart, and dependency changes.
