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
