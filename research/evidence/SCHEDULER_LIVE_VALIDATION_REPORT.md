# Scheduler live validation — Financial_Model:04_01

This is an isolated scheduler continuation. The archived Task IR, Edit Plan, authority,
ProgramGroups, repaired database lineage, evidence/cache state and three retained terminal
sessions were copied to a separate continuation directory. The frontend was not rerun.
The continuation invoked only the repaired compiled scheduler and the existing retrieval/
synthesis path for newly activated units. No writer, LibreOffice refresh or scorer ran.

## Frozen starting state

- Authorized cells: **73**.
- Earned ProgramGroups: **16**.
- Predicted independent units: **49**.
- Archived terminal session outcomes: **3**.
- Newly exposed independent units: **46**.
- Archived runtime profile: `z-ai/glm-5.3-flash`, reasoning `max`,
  `150` model-call ceiling, `$6.0` cost ceiling,
  frontend mode `sharded_projected`.

The archived terminal sessions were `PROVIDER_TIMEOUT`, `PROVIDER_TIMEOUT` and
`SESSION_RESOURCE_LIMIT`. Their scheduler dispositions remain archived as terminal state;
the trace reclassifies them from the persisted session failure fields so provider/resource
failure is not reported as model abstention.

## A. Zero-model verifier-crash reproduction

The prior continuation replenished after provider failure, invalid response, and explicit
abstention. Failed ProgramGroup members were not promoted. An accepted proposal for
`cell:s03:r11:c6` then aborted the run in `_validate_formula`
before that unit received a terminal disposition. That crash is a downstream verifier
invariant defect, not queue starvation.

- Persisted synthesis call: **56**.
- Parsed status: `PROPOSED` formula `=F10/E10-1`.
- References: `[{"host": null, "start": "F10", "end": null, "resolved_sheet": "Financials"}, {"host": null, "start": "E10", "end": null, "resolved_sheet": "Financials"}]`.
- Crashing worksheet object: `Financials` `ReadOnlyWorksheet`.
- Read-only bounds before force: `{"max_column": null, "max_row": null}`.
- Bounds after `calculate_dimension(force=True)`: `{"max_column": 34, "max_row": 1000, "dimension": "A1:AH1000", "error": null}`.
- Legal state: OOXML worksheets may omit <dimension>; openpyxl ReadOnlyWorksheet then leaves max_column/max_row as None even when the sheet is populated.
- Incorrect invariant: `ws.max_column and ws.max_row are always comparable integers`.
- Other workbooks: Any read_only workbook whose sheet XML omits <dimension> can hit the same comparison. In the frozen 60-task repaired_inputs set, only Financial_Model-04_01 is fully unsized.
- Raised after repair: `None`.
- Validation after repair: `{"parser_ok": true, "invalid_address": false, "invalid_sheet": false, "formula_present": true}`.

## B. Patch

`formula_synthesis_probe._used_sheet_bounds` materializes integer used-range maxima on
unsized read-only worksheets, then applies the original beyond-used-range predicate to
both range starts and range ends. The archived `=F10/E10-1` proposal is the regression
in `tests/test_formula_synthesis_bounds.py`. Authority, ProgramGroups, retrieval,
synthesis, and prompts were not changed.

## C. Continuation provenance

- Resume: **True**.
- Continuation directory: `/home/kerem/Desktop/Personal Projects/librecalc-mcp/scheduler_live_validation/Financial_Model-04_01`.
- Pre-resume snapshot: `/home/kerem/Desktop/Personal Projects/librecalc-mcp/scheduler_live_validation/pre_verifier_resume`.
- State SHA-256 before resume: `7609ca3b02d7ad4d3ea68bb747d4e4f811cf5e815ceda2b360abfc590f82633a`.
- Call 056 SHA-256: `8461b6c5f05380dd5637bb41f312b7efa9037058395f7153f467e65b0a2856fe`.
- Model-call count before resume: **56**.
- Persisted session ids: `["cell:s02:r141:c11", "cell:s03:r11:c4", "cell:s03:r11:c5", "cell:s03:r11:c6", "cell:s03:r6:c4", "cell:s03:r6:c5", "cell:s05:r12:c5"]`.
- Persisted disposition ids: `["cell:s02:r141:c11", "cell:s03:r11:c4", "cell:s03:r11:c5", "cell:s03:r6:c4", "cell:s03:r6:c5", "cell:s05:r12:c5"]`.

The scheduler re-entered the persisted F11 session and did not repeat those model calls.
Later independent units used the existing retrieval/synthesis path only when no session
was already checkpointed.

## D. Final independent-unit coverage

- Independent units reached: **49**.
- Attempted live or satisfied by persisted outcomes: **24**.
- Provider failures: **12**.
- Invalid responses: **1**.
- Abstentions: **4**.
- Accepted proposals: **0**.
- No-ops: **6**.
- Verifier rejections: **0**.
- Accepted edits: **1**.
- Session resource failures: **1**.
- Attempted without terminal disposition: **0**.
- Unattempted independent units: **25**.
- Total model calls after continuation: **150**.
- New persisted model calls: **127**.
- Provider cost after continuation: **$0.592068**.

Independent-unit outcome counts:

```json
{
  "EXPLICIT_MODEL_ABSTENTION": 4,
  "INVALID_RESPONSE": 1,
  "NO_OP": 6,
  "PROVIDER_FAILURE": 12,
  "SESSION_RESOURCE_FAILURE": 1,
  "UNATTEMPTED_INDEPENDENT": 25
}
```

Remaining unattempted independent units:

- `cell:s03:r27:c5` `Financials!E27`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r36:c4` `Financials!D36`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r36:c5` `Financials!E36`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r39:c4` `Financials!D39`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r39:c5` `Financials!E39`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r42:c4` `Financials!D42`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r42:c5` `Financials!E42`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r45:c4` `Financials!D45`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r45:c5` `Financials!E45`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r45:c6` `Financials!F45`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r47:c4` `Financials!D47`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r47:c5` `Financials!E47`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r51:c4` `Financials!D51`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r51:c5` `Financials!E51`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r51:c6` `Financials!F51`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r52:c4` `Financials!D52`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r52:c5` `Financials!E52`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r58:c4` `Financials!D58`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r58:c5` `Financials!E58`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r58:c6` `Financials!F58`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r59:c4` `Financials!D59`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r59:c5` `Financials!E59`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r68:c4` `Financials!D68`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s03:r68:c5` `Financials!E68`: global_resource_boundary: TASK_MODEL_CALL_LIMIT
- `cell:s05:r12:c6` `Ratio_Analysis !F12`: global_resource_boundary: TASK_MODEL_CALL_LIMIT

The full per-unit trace is in `scheduler_live_validation_trace.json`; the independent-unit
table is in `scheduler_live_validation_trace.csv`. Failed canonical groups never become
independent synthesis units. Formula correctness and benchmark score are outside this
experiment.

## Liveness verdict

- Latent work continued after terminal dispositions: **True**.
- Failed ProgramGroup members promoted: **False**.
- Terminal disposition failed to replenish: **False**.
- All independent work disposed or explicitly censored: **True**.
- Global resource failures: **1**.
- Scheduler exception: `None`.

**SCHEDULER_LIVENESS_PARTIAL_RESOURCE_CENSORED**
