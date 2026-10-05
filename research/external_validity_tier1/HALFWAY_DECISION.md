# Tier 1 halfway decision

Written after the 12 halfway cells (6 P + 6 Mimo O) and before any
second-half run. Prereg §11.

## Verdict: CONTINUE

No decisive reversal; finish Tier 1. No prompt, cap, threshold, or
population change under any consideration below.

## Halfway cell status (all scored as observed, 0 provider-invalid)

| cell | model | task | status | exit | correctness |
|---|---|---|---|---|---|
| r01 | P Claude | Debugging:07_01 | completed | submitted | exact F (reg 0.9956, mod 0.1047) |
| r02 | O Mimo | Debugging:07_01 | failed | timeout 3600s | no output |
| r03 | P Claude | Template:07_01 | completed | submitted | exact F (reg 0.9868, mod 0.7018) |
| r04 | O Mimo | Template:07_01 | failed | exit_format | no output |
| r05 | P Claude | Financial_Model:11_05 | completed | submitted | exact F (reg 1.0, mod 0.9853) |
| r06 | O Mimo | Financial_Model:11_05 | failed | timeout 3600s | no output |
| r07 | P Claude | T1_R1 | completed | submitted | exact T (6/6) |
| r08 | O Mimo | T1_R1 | completed | submitted | exact T (6/6) |
| r09 | P Claude | T1_W1 | completed | submitted | exact T (1206/1206) |
| r10 | O Mimo | T1_W1 | failed | timeout 3600s | no output (correct program written, unsubmitted) |
| r11 | P Claude | T1_M1 | completed | submitted | exact T (33/33) |
| r12 | O Mimo | T1_M1 | completed | submitted | exact T (33/33) |

Failure forensics: r02/r06/r10 timeouts after 26/32/7 productive steps
with zero provider errors (verified per-run greps); r04 tool-envelope
format death (parallel tool calls + malformed JSON, no provider errors).
All four are behavioral/observed outcomes per §7, not retried.
Served-model audit: P 83/83 generations of the requested snapshot
(`anthropic/claude-4.5-sonnet-20250929`) via Bedrock; O 96/96
(`xiaomi/mimo-v2.6-pro-20260921`) via DeepInfra. No substitution.

EARLY_DIVERGENCE check: no claim meets its full reopen bar (see below).
INFRASTRUCTURE_INVALID check: 0/12 provider-invalid; one harness defect
found (D1) with a clean halfway-boundary fix (see below). Neither
alternative outcome is met.

## Preliminary behavioral notes (no verdicts drawn)

- Claim A: ordinary Python/openpyxl (+pandas/shutil/re) in all 12 runs;
  both models drop below openpyxl to raw OOXML XML grepping (r02, r04);
  IR-awkward ops (dynamic search, computed f-string coordinates,
  cross-sheet computed refs, ad-hoc filtering, pandas groupby) in every
  non-trivial script. No openpyxl-mechanics failure observed (r04's death
  was tool-envelope format, not spreadsheet mechanics).
- Claim B: 2 helper import attempts in 12 runs (r01, r05, both P `search`,
  one call each); 0 write-helper calls despite eligibility; 0 spontaneous
  plan artifacts. BUT both attempts failed on harness defect D1 (below):
  success/benefit is uninterpretable for halfway cells.
- Claim C: python-observation bytes mostly 0.4-16 KB; r06 emitted 123.8 KB
  of row-dump prints (flagged dense run; emission-ratio analysis at
  final). Harness `view_xlsx content` whole-sheet dumps (58.6 KB, r07/r08
  Sales sheet) are harness-provided context, NOT model emission: the two
  are separated in analysis (pyobs vs total).
- Failure forensics (Claim F): controlled-task completions show
  reasoning/action residue (high reg, partial mod); timeouts are
  budget/termination; r04 is tool-contract action failure. Full
  classification with loss-boundary method at final.
- Surveillance: `data_only=True` used (r02, cache audit + recalc diff);
  external `soffice --headless` recalc invoked (r06, r12); repeated
  `load_workbook` per probe step (both models); no `iter_cols`/`.values`/
  `values_only`/range-literal demand yet.
- Miner note: 1/70 python blocks unparseable (r06 step 6, shell
  backslash-continuation artifact in `-c` extraction); content
  human-verified as the BG-reference search. Negligible count effect.

## Infrastructure defect D1: helper bundle staging (FIXED at halfway)

Symptom: both halfway `import lx_helpers` attempts died with
`ModuleNotFoundError: No module named 'benchmark'` at
`lx_helpers.py` line 17 (`from benchmark.inspection_helpers...`).

Root cause: the Tier 1 runner patch staged ONLY `lx_helpers.py` into the
container mount dir, not the accompanying `benchmark/` package directory.
The pre-study container check mounted the complete SOURCE dir, so it
missed the staging-path defect. Unambiguous mechanical bug, evident from
the traceback alone.

Fix (this commit, before run 13): stage the whole bundle directory
(`shutil.copytree`), keeping the sha256 fail-closed check on
`lx_helpers.py`. No prompt/config/bundle-content change; the fix makes the
implementation match the preregistered description ("stages the frozen
bundle"). Verified WITHOUT consuming a model smoke run (2/2 already used):
real `_stage_tool_policy` staging output mounted in the agent image with
the exact runner mount flags; all six helpers imported and CALLED
successfully (search/inspect/inspect_ranges/periods return dicts;
write_cells/write_formulas round-trip verified via openpyxl re-read).

Timing is clean: no scored cell straddles the fix (12 pre-fix, 6 post-fix).

## Frozen analysis rule for Claim B (stratified by helper condition)

Because D1 splits the study into two helper conditions, Claim B is scored
in strata (bar itself unchanged: adoption on >=3 eligible tasks + paired
benefit, per A2 own-denominator counting):

- Broken-helper stratum (12 halfway cells): IMPORT-ATTEMPT rate is
  interpretable (the note was visible; the try/no-try decision precedes
  the failure). Success/benefit is NOT interpretable and is excluded.
- Working-helper stratum (6 second-half Mimo cells): full
  adoption+benefit scoring. Small-N limit reported honestly.

Attempt-rate is reported pooled with strata labeled; success/benefit only
from the working stratum. If the working stratum is too thin for a firm
verdict, Claim B closes as HOLDS_WITH_LIMITATION / NOT_TESTED_CLEANLY
with the defect as the documented limitation — never as a silent pass.

## Cost so far (generation-API authoritative; charged figures inflated by parallel key attribution)

- Smoke P: $0.99 charged. P halfway (6): charged ~$3.5. Mimo halfway (6):
  generation $0.86 total. DeepSeek-era superseded: $1.56 charged / $0.18
  generation. Total generation-API ≈ $5.3 of the $52 ceiling.

## Next: second-half order (per A2)

Mimo cells 14/16/18/20/22/24 (Debugging:08_06, Template:03_02,
Financial_Model:07_01, T1_R2, T1_W2, T1_M2), up to 6-way parallel
(proven safe). No P runs remain. Replay layer + final verdicts after.
