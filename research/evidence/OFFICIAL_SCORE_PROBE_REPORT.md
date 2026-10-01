# Official-score probe

Prospectively specified three-task compiled GLM 5.3 Flash / `high` run against the published SpreadsheetBench 2 control reference. Muse Spark 1.3 Contributor on `Financial_Model:02_01` uses the LibreCalc harness. The published-control Spark run is retained because it already completed; it is not a causal scaffold claim.

Generated at: 2026-09-16T09:04:42.462381+00:00

## Envelope

- GLM compiled: `z-ai/glm-5.3-flash` / `high`, 40 calls, $2.50 per task
- Spark LibreCalc harness: `meta/muse-spark-1.3-contributor`, 50 calls, $2.50
- Spark published control (kept): `meta/muse-spark-1.3-contributor`, 50 calls, $2.50

## Official accuracy

| Task | Published control | GLM compiled | Spark 1.3 control (kept) | Spark 1.3 LibreCalc harness |
| --- | --- | --- | --- | --- |
| `Template:01_02` | 0.0 | 0.0 | — | — |
| `Financial_Model:02_01` | 0.0 | 0.0 | 1.0 | 1.0 |
| `Debugging:01_01` | 0.0 | 0.0 | — | — |

## Reading

- GLM vs published control is the system benchmark claim.
- Spark on the LibreCalc harness vs GLM on `Financial_Model:02_01` is an extra model observation, not a matched causal arm.
- The Spark published-control run is kept only because it already ran; do not treat it as the authorised extra arm.
- Do not rerun the published GLM control merely to recreate an already stored number.
## Compiled model discriminator

See `OFFICIAL_SCORE_COMPILED_MODEL_DISCRIMINATOR_REPORT.md`.
