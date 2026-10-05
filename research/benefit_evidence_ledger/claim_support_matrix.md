# Claim-support matrix

Strict evaluation of candidate workload-fit statements against frozen
evidence only. Family labels are never causal explanations.

| candidate | verdict | evidence |
|---|---|---|
| A. benefits tasks with expensive certified reads | `SUPPORTED_WITH_QUALIFICATION` | 10/10 served blocks faster; r01/r06 task wins on served reads. Qualification: r14 had 4,607 expensive served reads yet regressed — expensiveness alone is insufficient without F's share condition |
| B. benefits tasks with repeated workbook reads | `NOT_ESTABLISHED` | No frozen measurement isolates within-task read repetition as a benefit driver. Warm-REUSED describes artifact state across invocations, not a tested user-task property |
| C. benefits large workbooks | `SUPPORTED_WITH_QUALIFICATION` | R3 savings concentrate in giant parses (top-3 = 84%); r06 won on a 593 KB book. Qualification: size predicts direct-block savings magnitude, not task outcome — r18 (590 KB) and r14 (282 KB) regressed; r01 won with 63 reads on a mid-size book |
| D. benefits Financial Model tasks | `NOT_ESTABLISHED` | Within-family mixed: FM:11_05 won (r06) but FM:07_01 regressed (+7.2%) with service, and FM:11_05 r05 regressed (+20%) without. Valid: "a SpreadsheetBench-2 FM task" as a named case study |
| E. benefits Debugging tasks | `NOT_ESTABLISHED` | Within-family mixed: D:07_01 won (r01) but D:08_06 regressed (+7.5%) with service and D:07_01 r02 regressed without. Valid: "a SpreadsheetBench-2 Debugging task" as a named case study |
| F. benefits tasks where served read cost is a meaningful share of total execution | `SUPPORTED_WITH_QUALIFICATION` | Best-supported mechanistic statement. Winners' direct-base shares: r01 21.3%, r06 15.8%; losers': r14 5.0%, r18 4.8%; R3 giants won their (single-phase) executions near-100% share. Qualification: no calibrated threshold — 4 served trajectories cannot set one; "meaningful" is directional, not numeric |
| G. benefits warm inspection/analysis phases more than mutation-heavy phases | `SUPPORTED_WITH_QUALIFICATION` | Service occurred only in read-only blocks; no write block was ever served (contract-structural); R3 cold check shows no cold benefit. Qualification: phase-level, not trajectory-level — all 4 served trajectories contain writes; and the mutation side is excluded by design, not by empirical horse race |

## Family-level summary (task section 16)

Neither family claim is supported as a generalization:

- Financial_Model: 1 trajectory win (r06), 1 served loss (r18), 1 unserved loss (r05) → mixed.
- Debugging: 1 trajectory win (r01), 1 served loss (r14), 1 unserved loss (r02) → mixed.
- Template: 0 served trajectories, 0 wins → no benefit observed at all.

Use families only to identify concrete cases ("a SpreadsheetBench-2
Financial Model task"), never as the explanation ("because it is FM").

## Workload-fit recommendation (task section 13)

**Technically precise:** tasks whose total execution cost contains a
sufficiently large share of warm certified workbook-read cost (point
reads and full-cell iteration within the direct contract), such that
served-read savings exceed wrapper plus reference-path residuals.

**Reader-facing:** Recalc speeds up spreadsheet work where expensive
workbook reading — on data already loaded once — dominates the run.
Mixed, mutation-heavy, cold, or dynamic runs typically see little or
no gain.

**Explicitly avoid:** family-level speedups ("FM tasks", "Debugging
tasks"); typical-case percentages ("79% faster"); universal accelerator
language; admission-as-applicability; substep figures as task claims;
cold/first-run speedup implications.
