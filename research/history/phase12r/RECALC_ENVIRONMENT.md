# Recalculation environment

**frozen_utc**: `2026-09-30T14:04:58.976646+00:00`

**OS**: `Linux HP-Spectre-x360-14-eu0xxx 7.0.0-34-generic #34-Ubuntu SMP PREEMPT_DYNAMIC Wed Sep  2 14:29:37 UTC 2026 x86_64 GNU/Linux`

**Python**: `3.14.4 (main, Aug 20 2026, 10:41:58) [GCC 15.2.0]`

**python_executable**: `/home/kerem/Desktop/Personal Projects/librecalc-mcp/.venv/bin/python`

**system_python**: `Python 3.14.4`

**LibreOffice**: `LibreOffice 26.2.5.2 620(Build:2)`

**locale**: `C.UTF-8`

**timezone**: `UTC`

**openpyxl**: `3.1.5`

**evaluator_path**: `/home/kerem/Desktop/Personal Projects/librecalc-mcp/benchmark-data/SpreadsheetBench-2/evaluation/evaluation.py`

**evaluator_hash**: `04a2a75b29805ab40efe93e202384c365d1d32b9c924c1a4aed56e41249facb0`

**evaluator_metadata**: `current retained official local evaluator, unmodified; historical source identities unavailable`

**scorer_entrypoint**: `process_single_item (unchanged official evaluation.py); compare_workbooks_with_regression for explicit cell-count/read-failure capture`

**scoring_environment**: `same input/golden/dataset rows across V0/V1/witness; no refresh inside scorer`

**workers**: `4`

**recalc_timeout_seconds**: `180`

**macro_policy**: `MacroExecutionMode=4 (NEVER_EXECUTE)`

**link_policy**: `UpdateDocMode=0 (NO_UPDATE); detected external links excluded`

**calculation**: `enableAutomaticCalculation(True); calculateAll(); storeAsURL(..., FilterName=Calc MS Excel 2007 XML)`

**profile_policy**: `fresh isolated profile and UNO pipe per workbook hash; reused only byte-identical candidates and same helper hash; profiles discarded after execution`

Full input/golden/dataset and protected-history identities: ENVIRONMENT.json and PROTECTED_HISTORY_HASHES.json. Command/config is retained per execution in correction ledger. Original LO workbooks are never overwritten. Profile contents are disposable; fresh-profile command records reproduce configuration.

## Additive execution qualifications (2026-10-01)

The frozen table above is preserved as the original record. Its macro-policy
name is incorrect: installed UNO mode 4 is ALWAYS_EXECUTE_NO_WARN; mode 0 is
NEVER_EXECUTE. See MACRO_CONFIG_DEVIATION.md and MACRO_CONFIG_PACKAGE_AUDIT.json.
The main treatment is the frozen mode-4 helper. The single post-primary follow-up
will compare correct mode 0 without replacing any primary artifact.

The original four-worker scheduler caused two resource interruptions. The resumed
execution uses one fresh bounded workbook subprocess, unchanged official scoring
semantics, explicit failures and validated parse/score identity reuse. See
EXECUTION_RECOVERY.md, REPLAY_EXECUTION*.json and EXECUTION_PARITY_TEST.log.
The original frozen ENVIRONMENT.json remains byte-identical for audit.

The later403-row older-context recovery fixes auxiliary nested DimensionHolder
serialization, not scorer semantics. It uses the frozen Python3.14.4 environment;
native score/count parity and nested graph identity tests passed. Completed first
execution rows are preserved; remaining rows reuse frozen full inspection results
for identical bytes and repeat scoring only, escalating any newly assessable gain
to the full frozen cache witness/classifier. Both execution implementations and the
selected population/implementation amendment are separately hashed. See
SCORING_EXECUTION_RECOVERY_SPEC.md and SCORING_RECOVERY_EXECUTION_AMENDMENT.md.
