# Scheduler group-priority probe

Spark compiled `Financial_Model:02_01` only. Control is the stored compiled run; it was not rerun. Treatment froze Task IR + Edit Plan and changed only activation order: earned ProgramGroup canonicals before residual cells.

Generated at: 2026-09-16T11:39:09.677951+00:00
Verdict: `GROUP_PRIORITY_TRADEOFF`

## Scores

| Arm | Modification | Calls | Remaining authorised | Seeds |
| --- | ---: | ---: | ---: | --- |
| Stored Spark compiled (control) | 0.9778 | 40 | 21 | [['IS,BS,CF', 34, 8], ['Revenue & COGS Schedule', 5, 12], ['Revenue & COGS Schedule', 5, 13], ['BS schedules', 11, 8], ['BS schedules', 11, 11]] |
| Group-first scheduler (treatment) | 0.7378 | 40 | 19 | [['IS,BS,CF', 34, 8], ['Revenue & COGS Schedule', 5, 13], ['BS schedules', 11, 8], ['Ratios', 9, 6], ['Realization & EBIT Per KG', 23, 9]] |
| Published SWE-agent control (reference, not rerun) | 0.9938 | — | — | — |

Delta modification cells: -270 (of 1125).
Correct per call: control 27.5, treatment 20.75.

Treatment sessions: 5 group, 0 residual.
First official error: 'Modification error at IS,BS,CF!E102: answer=2077.64005275567, output=-16184.7546366328'.

Exact is out of scope. Authority misses and EPS `$C$10` still independently block exact.

## What happened

The activation order changed as designed. Control seeds were EPS `H34`, residual Sales `L5`, Sales group `M5`, DSO `H11`, residual DSO `K11`. Treatment seeds were EPS `H34`, Sales group `M5`, DSO `H11`, ROE `F9`, Realization `I23`. Residual `L5` and `K11` never ran. That is the earned-group preference working.

The modification collapse is not a ProgramGroup translation bug. `M5:O5` wrote the gold formulas (`=M3*M7` etc.). `M7` is `=L7`, and `L7` is `=L5/L3`. Skipping residual `L5` (FY22E `=SUM(H5:K5)`) zeros the price copy-down, so refreshed `M5:O5` are 0. `IS,BS,CF!I19` links to `M5`, so PAT `H31` / `E102` go from 2077.64 to -16184.75 and about 270 official modification cells cascade. ROE `F9` was the gold formula and still scores as a miss because `H31` is now garbage.

Secondary, not the cascade: EPS `H34` abstained on this rerun (control had written `=H31/C10`, which scored by value coincidence). Realization `I23:K23` was `NO_SEMANTIC_CHANGE` (already gold from the input).

Naive group-over-residual is not free when a residual is upstream of a group's inputs. `L5` is a different formula form, so it is not a ProgramGroup member; it is still the FY22E sales backbone. Default `operation_order` accidentally wrote that residual first. Do not land this activation policy. Cap stays 40. No absolute-reference verifier. ProgramGroups unchanged.

## Policy

Default scheduler stays `operation_order`. This probe opted into `prefer_earned_program_groups` only.
