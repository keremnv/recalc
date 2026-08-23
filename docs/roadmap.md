# Roadmap

## v0 — establish the loop

- [x] MCP v2 skeleton
- [x] backend abstraction
- [x] in-memory backend for tests
- [x] UNO connection skeleton
- [x] inspect workbook
- [x] read range
- [x] write range
- [x] deterministic multi-operation execution
- [ ] run against a real local Calc instance
- [ ] run one SpreadsheetBench 2 task end-to-end

## v1 — benchmark-driven world design

Add capabilities only as benchmark failures demand them.

Likely early candidates:

- formula-aware writes,
- used-region / formula-region inspection,
- named ranges,
- sheet create/delete/rename,
- style/number-format inspection,
- dependency traversal,
- formula pattern comparison,
- workbook recalculation and error scan,
- chart inspection/construction,
- large rectangular write optimizations.

## v1.5 — interface ablation

Compare the same agent/model with:

1. low-level tools,
2. semantic tools,
3. semantic tools + program execution.

Measure accuracy, modification score, tool calls, model turns, tokens, execution time, and recovery.

## v2 — living models

Only after benchmark competence:

- transactions,
- snapshots,
- semantic diffs,
- rollback,
- dynamic/perturbation validation,
- provenance/lineage,
- recurring workbook maintenance.

## Explicitly later

Writer, Impress, Draw, cross-document artifact graphs, and workspace-wide propagation.
