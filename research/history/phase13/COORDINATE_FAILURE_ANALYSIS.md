# Phase 13 — Coordinate Failure Analysis

## Target-discovery error vs write-execution error (§31)

These are separated throughout. A discovery error means the agent
never identified the right coordinates; an execution error means it
aimed correctly but wrote wrong.

## Population A

| Run | Class | Detail |
|---|---|---|
| 11_04 CONTROL | Discovery (row-level) | Used row 24 where gold uses row 26 across D:H34; omitted D26:H26 — the agent never established row 26 as the live assumption row |
| 11_03 CONTROL | Discovery (implicit targets) | C35/D35 echo cells never written; C19 omitted while C22 pointed at empty D19 (execution-adjacent: aimed at the wrong column of the right row) |
| 09_03 TREATMENT-arm success (matched, Pop B traj) | Recovered execution | "Labels are actually in column C, data in D–H. Let me rewrite with correct offsets" — caught by verification, fixed, exact 1 |
| 11_01 FM success (Pop B traj) | Recovered execution | "FY30 is column M; column N is outside the model. Removing stray N9/N26" — caught, fixed, exact 1 |

No Population-A failure is a pure off-by-one write-execution error
on an otherwise-correct plan. The observed coordinate errors are
discovery-flavored (wrong row as assumption source, implicit echo
cells) and sit inside L5/L4 classifications.

## Population B (sampled trajectories + forensics)

- 16_12: correct coordinates, wrong formula content (×12 missing) —
  not a coordinate error at all.
- 05_08: fixed exactly the gold coordinates (L12, L14); the task
  is unpassable as scored (empty assessed MOD set), so targeting
  was never the issue.
- Transposed ranges, off-by-one rows/columns, wrong-sheet writes:
  **zero observed cases** in 18 sampled trajectories and 40 Pop-A
  transcripts. The only wrong-sheet-adjacent events are discovery
  gaps (never opened), not misdirected writes.

## Conclusion

Coordinate mistakes are **not a measurable loss class** in the
ordinary populations. Agents that reach the write stage aim
correctly (or self-correct offsets during verification, as both
sampled successes demonstrate). The coordinate-shaped residuals
(11_04 rows, 11_03 echoes) are target-discovery/intent failures,
not write mechanics. No coordinate probe is warranted; a coordinate
helper would repeat the closed batch-writer branch (0/13 adoption
on exact-selected tasks).
