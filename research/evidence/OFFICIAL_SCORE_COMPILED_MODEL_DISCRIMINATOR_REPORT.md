# Compiled model discriminator

Muse Spark 1.3 Contributor vs GLM 5.3 Flash on the **same compiled architecture** and frozen three-task official-score slice. Existing Spark control and Spark LibreCalc-harness observations are not part of this A/B.

Generated at: 2026-09-16T10:20:41.363179+00:00
Primary verdict: `MIXED_MODEL_ARCHITECTURE_LIMITS`
Spark identity: PASS

## Per-task comparison

| Task | GLM exact / mod / reg | Spark compiled exact / mod / reg | GLM calls / $ / tokens | Spark compiled calls / $ / tokens | GLM terminal | Spark compiled terminal |
| --- | --- | --- | --- | --- | --- | --- |
| `Template:01_02` | 0.0/0.0/1.0 | 0.0/0.0/1.0 | 40 / $0.0195 / 182578+18902 | 40 / $0.0253 / 189969+40896 | `TASK_MODEL_CALL_LIMIT` | `TASK_MODEL_CALL_LIMIT` |
| `Financial_Model:02_01` | 0.0/0.7351/1.0 | 0.0/0.9778/1.0 | 2 / $0.0026 / 11815+3925 | 40 / $0.0476 / 370858+55443 | `edit_plan` | `HARD_VERIFIER_REJECT` |
| `Debugging:01_01` | 0.0/0.9364/1.0 | 0.0/0.9364/1.0 | 2 / $0.0035 / 23158+3073 | 1 / $0.0005 / 955+2162 | `UNSUPPORTED_EDIT_KIND` | `None` |

## GLM boundaries under test

- `Template:01_02`: GLM hit the 40-call cap with 181 authorised targets remaining.
- `Financial_Model:02_01`: GLM failed at Edit Plan parse after two calls.
- `Debugging:01_01`: GLM terminated with `UNSUPPORTED_EDIT_KIND` after two calls.

## Reading

- This is a model-on-fixed-architecture discriminator, not a scaffold comparison.
- Do not use the earlier Spark LibreCalc-harness 1/1 as evidence about Spark on the compiled architecture.
- A Spark success here would show the compiled architecture can cash out differently with another similarly priced model. It does not show population-level superiority or causal scaffold gain.

