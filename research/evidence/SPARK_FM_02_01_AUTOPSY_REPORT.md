# Spark compiled Financial_Model:02_01 forensic autopsy

Zero-model replay of the scored Spark compiled near-miss. Architecture frozen. No live provider calls.

Witness: same compiled runner, GLM dies at Edit Plan parse (mod 0.7351), Spark clears planning (VALID_PLAN, completeness COMPLETE) then stops at 40 calls with mod **0.9778 / exact 0**.

Artifacts: `spark_fm_02_01_autopsy.json`, `spark_fm_02_01_autopsy.csv`, `benchmark/spark_fm_02_01_autopsy.py`.

## Answer

The last 2.2% is **not** “21 pending cells, therefore scheduling only.”

Official modification is 1100/1125 = 0.9778 (replay matches stored). There are **25 modification misses and 0 regression misses**. Of those 25:

| Class | Cells | Share of the 25 |
| --- | ---: | ---: |
| Authorised, never activated, 40-call censored | 17 | 68% |
| Missing authority | 5 | 20% |
| Wrong proposal (written, formula ≠ gold) | 3 | 12% |

Exactness is already independently blocked by the 3 wrong EPS formulas. The first official error is `IS,BS,CF!I34` (`#DIV/0!` vs 23.91). Infinite remaining budget would not make this task exact unless those formulas and the five unauthorised gold cells also changed.

The 21 unresolved authorised cells are real, but only **17** of them are official modification misses. The other four (`Realization!I23:K23`, `Revenue!K4`) already match gold from the input, so leaving them blank does not cost points.

## What ran

- 33 authorised cells, 7 operations, 7 obligations, planning COMPLETE.
- 40 calls: 1 Task IR, 1 Edit Plan, 33 retrieval, 5 synthesis.
- 5 stochastic seeds, 11 writes applied, 0 writer rejects.
- Dispositions: 4 `WRITES_SCHEDULED`, 7 `TRANSLATED_WRITE_SCHEDULED`, 1 `REJECTED_HARD`.
- Ledger: `HARD_VERIFIER_REJECT` on `BS schedules!K11`, then `TASK_MODEL_CALL_LIMIT` with `remaining_count` 21.

Successful writes that scored: Sales `L5:O5` (exact gold formulas) and DSO `H11:J11` (exact gold formulas). EPS `H34` scored by **value coincidence** (`=H31/C10` vs gold `=H31/$C$10`; `C10=110.6`).

## The 25 official modification misses

### 3 wrong proposals — EPS `I34:K34`

Seed `IS,BS,CF!H34` proposed `=H31/C10` instead of gold `=H31/$C$10`. Translation then shifted the unlocked denominator:

| Cell | Written | Gold | Output value |
| --- | --- | --- | --- |
| I34 | `=I31/D10` | `=I31/$C$10` | `#DIV/0!` |
| J34 | `=J31/E10` | `=J31/$C$10` | `#DIV/0!` |
| K34 | `=K31/F10` | `=K31/$C$10` | `#DIV/0!` |

`D10:F10` are empty share-count cells. This is a wrong relative formula, not a missing upstream write. The `#DIV/0!` is the symptom. H34 is officially correct only because the relative `C10` still points at 110.6.

Not 40-call censored. Not a verifier reject.

### 5 missing authority

Planner completeness is schema-complete, not gold-complete (`semantic_completeness: NOT_ESTABLISHED`).

| Cell | Gold formula | Planner did |
| --- | --- | --- |
| `Revenue & COGS Schedule!D4` | `=D3/C3-1` (Q1FY21 volume growth) | Started Volume Growth at E4:K4, one column late; extra K4 is gold-blank |
| `BS schedules!G11` | DSO `=AVERAGE(F8:G8)/'IS,BS,CF'!H19*'IS,BS,CF'!$C$9` | Started forecast DSO at H11:K11, one year late; extra K11 is gold-blank |
| `Realization & EBIT Per KG!I11:K11` | Supreme EBIT/KG `=I7/I4` etc. 2019–2021 | Authorised Finolex row 23 `I23:K23`, already filled in the input |

These five never entered the scheduler. They cannot be blamed on the 40-call envelope.

### 17 authorised blanks censored by the envelope

All `direct blank target: unchanged`. Remaining when `TASK_MODEL_CALL_LIMIT` fired. Scheduler had earned ProgramGroups for them; they were never seeded.

- Volume Growth `E4:J4` (6) — authorised remainder of O3 after the late start. `K4` also remaining but gold-blank.
- Current Ratio `C4:I4` (7) — entire O6 group, gold-aligned authority.
- Forecast ROE `F9:I9` (4) — entire O5 group, gold-aligned authority.

That is 17 of 21 remaining authorised cells. Sequencing (`op3` after `op2`, `op6` after `op5`) plus one-active-unit exposure kept these latent while EPS, Sales, and DSO consumed the envelope (four 9-call retrieval/synthesis sessions before the last seed).

## HARD_VERIFIER_REJECT

Rejected cell: `BS schedules!K11`.
Proposed: `=AVERAGE(J8:K8)/'IS,BS,CF'!L19*'IS,BS,CF'!$C$9` after 2 calls.

Existing `validate_formula` contract (`matched_compiled_treatment.py`): `HARD_ACCEPT` iff `parser_ok` and not `hard_reject` and not `invalid_sheet` and not `invalid_address` and not `unsupported_external`.

| Gate | Observed |
| --- | --- |
| inner `hard_reject` / hard policy H | False / PASS |
| `parser_ok` | True |
| `invalid_sheet` | False |
| `unsupported_external` | False |
| `invalid_address` | **True** — `'IS,BS,CF'!L19` is column 12; input used range is K121 |
| wrapper `hard_verifier_result` | HARD_REJECT |

The rejection is **correct under the existing contract**. It is also gold-aligned: gold `K11` is blank, and `K11` is outside `'BS schedules'!A1:J164`, so this reject is **not one of the 25 official misses**. Not a mechanical bug.

## Counterfactuals (offline, not run)

Hold writes and authority fixed:

- Fill the 17 envelope cells correctly → 1117/1125 = 0.9929, still not exact (I34 remains first error).
- Also restore the 5 missing-authority cells → 1122/1125 = 0.9964, still not exact.
- Only the 3 EPS formulas stand between that world and exact.

So the envelope is the largest *count* of remaining official misses, and it is a real scheduling/resource bound. Exactness on this witness is already lost to a wrong unlocked share-count reference plus five planner authority gaps (late start / wrong company row).

## Architecture

No mechanical bug in writer, verifier wrapper, or scoring. Do not change the architecture from this audit. Do not expand the official-score population on this evidence.

The next architecture boundary after the model bottleneck moved is mixed: **resource scheduling of remaining authorised groups**, plus residual **planner period/entity alignment** and **synthesis absolute-reference** failures that already make exact impossible.
