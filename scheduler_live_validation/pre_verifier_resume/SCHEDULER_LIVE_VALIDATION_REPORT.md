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

## Live continuation

- Independent units: **49**.
- Newly exposed: **46**.
- Newly attempted: **4**.
- Newly unattempted: **42**.
- Total model calls after continuation: **56**.
- New persisted model calls: **33**.
- Provider cost after continuation: **$0.333418**.
- New provider cost: **$0.081203**.

Terminal outcomes are preserved in the machine-readable trace with their exact
`failure_class`, parsed status, disposition and call ledger. The independent-unit outcome
counts were:

```json
{
  "ATTEMPTED_NO_TERMINAL_DISPOSITION": 1,
  "EXPLICIT_MODEL_ABSTENTION": 1,
  "INVALID_RESPONSE": 1,
  "PROVIDER_FAILURE": 3,
  "SESSION_RESOURCE_FAILURE": 1,
  "UNATTEMPTED_INDEPENDENT": 42
}
```

The full per-unit trace is in `scheduler_live_validation_trace.json`; the independent-unit
table is in `scheduler_live_validation_trace.csv`. ProgramGroup members are separately
listed there. Failed canonical groups never become independent synthesis units.

## Liveness result

- Latent work continued after terminal dispositions: **True**.
- Failed ProgramGroup members promoted: **False**.
- All independent work disposed or explicitly censored: **False**.
- Global resource failures: **0**.

The continuation was blocked by an uncaught downstream verifier exception after an
accepted proposal, before the scheduler could assign that unit a terminal disposition:

```text
Traceback (most recent call last):
  File "benchmark/compiled_scheduler.py", line 207, in schedule
    validation = m.validate_formula(task_key, proposal["target"], f, cache, plan["spine"])
  File "benchmark/matched_compiled_treatment.py", line 919, in validate_formula
    result = prior.synth_tools._validate_formula(row, formula, {}, spine, *cache[task_key])
  File "benchmark/formula_synthesis_probe.py", line 779, in _validate_formula
    if a and (a[0] > ws.max_column or a[1] > ws.max_row):
TypeError: '>' not supported between instances of 'int' and 'NoneType'

```

This is not evidence that the queue failed to replenish. It is a separate runtime
boundary in formula validation; no global task/resource boundary had fired.

The trace separates provider/resource failure, explicit model abstention, invalid response,
no-op, verifier rejection, accepted proposal, failed ProgramGroup canonical/member state,
global budget stop and genuinely unattempted independent work. Formula correctness and
benchmark score are outside this experiment.

**SCHEDULER_LIVENESS_DEFECT_REMAINS**
