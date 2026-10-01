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
- [x] run against a real local Calc instance
- [x] run one SpreadsheetBench 2 development canary end-to-end through the official evaluator
- [x] run one untouched SpreadsheetBench 2 task in an isolated agent container and retain its scored baseline
- [x] add benchmark-motivated formula-fill and content-clear operations with memory and UNO tests

## v1 — benchmark-driven world design

Add capabilities only as benchmark failures demand them.

Likely early candidates, to be promoted only after repeated failures:

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

Immediate milestone: establish clean exact upper-model anchors on the contaminated public tasks
`Template:01_01`, `Financial_Model:09_04`, and `Debugging:10_02`. They respectively test accounting
reasoning, residual exactness, and debugging localization, and their published Opus example traces
did not access golden workbooks. Use those anchors for controlled cheaper-model threshold experiments.
Keep untouched slice tasks for frozen transfer and competitive measurements; the first
`Template:01_02` transfer is now development-only after revealing a fixed UNO formula-separator
defect and independent accounting-reasoning errors. The public trajectory audit and its benchmark
isolation caveat are recorded in `docs/public-trajectory-audit.md`.

`Template:06_01` is excluded from the ladder: its golden workbook contains six `=#REF!` cells where
valid translated formulas belong. A clean Opus 5 run reproduced Opus 4.6's 85% modification score by
generating correct formulas. Keep it only as an evaluator/golden-quality regression fixture.

The clean `Template:01_01` probe now marks the first useful threshold. Kimi K2.5 failed before
mutation, while Opus 5 at low reasoning completed the tool loop but scored 72/87 modification cells
because it selected the wrong tax-basis convention. The trace justified two general fixes: one
bounded format-repair response in the harness and 240-character semantic notes. Move to
`Financial_Model:09_04` rather than tuning further on this public task. Its single public residual
(`Valuation!G59`, a blank WACC anchor beneath a header) motivated an offline table-corner signal, but
the full public slice yielded only 1 true hit from 23 candidates (4.35% precision, 0.14% recall).
Do not ship that heuristic; establish the clean upper anchor using the unchanged observation model.

The attempted `09_04` anchor changed the immediate order of work. Full semantic v2 is not a viable
initial observation on the 2.58 MB workbook: even after backend batching it emits 5.77 MB, while a
structure-first overview is 49.8 KB and localized every requested region. Opus then repeatedly
requested parallel focused reads, spending `$1.151565` without mutation. `calc_read_ranges`, batched
UNO reads, a 180-second recorded command timeout, and a pre-request hard budget reserve are now in
place and tested. Cheap-model probes verified the tool loop but did not produce a workbook. Kimi
K2.7 Code localized all requested edits and inferred the ordinary formula families, then exhausted
every response deliberating under both low and minimal reasoning. Kimi K2.5 issued valid single
batch-read calls on all eight turns but kept expanding its inspection instead of writing. These are
model-policy/observation failures, not transport failures. Fixed response-token caps are no longer
the default: the runner now derives the largest allowance that fits the remaining hard dollar
budget on every request. Keep explicit caps only for controlled ablations.

The compact formula-pattern experiment has now crossed the write threshold on `09_04`: Kimi K2.7
produced a 0.9981-modification workbook with only `Valuation!G59` missing. Work has moved to
`Debugging:10_02`. Its first anomaly-attention canary found all nine real hardcodes but
overgeneralized and spent `$0.061632` without writing. The refined `formula-anomalies-v1` now emits
21.2 KB and, in offline characterization of this contaminated development task, selects all nine
repairs with no false selected cells after format, edge-block, literal-error, and saturation
filtering. The confirm-then-write K2.7 canary scored official regression `1.0` and modification
`41/47` (`0.8723`): all nine hardcode→formula repairs match; the six misses are P&L `(-)` label
prefixes. Frozen formula-blocks transfers: `07_01` modification `85/86`; `05_03` and `08_03` no
workbook (repeated deleted-row / `#REF!` diagnosis). Geometry ops `insert_row` / `delete_row` are
now in the domain algebra; the next probe un-freezes `calc_program`. Overlays stay measurement
instruments. Do not add task-specific restore heuristics.

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
