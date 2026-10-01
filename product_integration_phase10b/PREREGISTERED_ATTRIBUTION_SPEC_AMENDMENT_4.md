# Phase 10B preregistered attribution amendment 4: homogeneous CPU affinity

Written and hashed before any core-pinned process fixture or scored command. The original spec and amendments 1–3 remain unchanged. All completed unpinned runs, raw correctness and timing ledgers, analysis, profiles and logs are preserved in `scored_v2_unpinned/`; the earlier bytecode-confounded score remains in `scored_v1/`. No population, budget, product code, semantic comparator, arm implementation, repetition, ordering, timing boundary or stop condition is weakened.

## Concrete timing-identity defect

The current host is a hybrid Intel Core Ultra 5 125H with 4.5 GHz maximum performance-core logical CPUs 0–7, 3.6 GHz efficiency cores 8–15, and 2.5 GHz efficiency cores 16–17. Earlier scored parents and children were allowed on logical CPUs 0–17. The same frozen direct-Python scripts changed wall time sharply between otherwise comparable batches, and unchanged P4 crossed the +10 ms budget in opposite directions. This prevents a defensible millisecond-level causal attribution from the unpinned scores. Their correctness gates remain valid, but their performance results are diagnostic.

## Controlled condition

Run each entire scored batch under `taskset -c 1 python SCRIPT`, so the benchmark parent and every launched arm/target inherit a singleton Linux affinity mask on logical CPU 1, a 4.5 GHz maximum performance core. `taskset` is outside each per-command external timer; no arm receives a special per-command wrapper. The host governor remains `powersave`; no claim of fixed frequency or exclusive core reservation is made. `affinity_identity.json` pins the topology/governor evidence, SHA-256 `803af5ae54ab4a02413c9251a7981046a3100e2e80bc7f371edad92df518ffe3`. Validate the inherited affinity in an unscored process probe before each batch.

## Rerun and reliability gate

Rerun the full P0–P4, S0–S3 and P5/P4/Python batches from fresh arm-specific run roots, on the exact same 22 scripts/workbooks, with the same two scored repetitions and invocation-1/2 sequence, deterministic arm orders and unchanged 180-second timeout. Before score, rerun all process/reference-object fixtures under the same affinity. After the P5 primary batch, rerun the seven direct-contact and five changed-file correctness controls plus changed-workbook abrupt-exit fixtures under the same affinity. Preserve every earlier raw row; new canonical ledgers use their original filenames and must not append to old rows.

The primary budget remains median signed P5−PY_NEW second-invocation excess **≤ +10 ms**. P4−P0 in the pinned main batch is the tax replication check; P4−PY_OLD in the pinned P5 batch is a same-run bridge. Use only within-batch paired contrasts for causality and report both venv baselines. If more than three of the exact 22 workloads have >25% relative difference between their two scored second-invocation direct-Python control walls in either the main P0 or P5 PY_OLD batch, label millisecond attribution unreliable and do not claim a budget pass, regardless of median direction. This reliability rule catches the large earlier scheduling drift without excluding any workload.

A P5 semantic or assurance failure stops interpretation. No additional optimization or threshold change is authorized. If core pinning still cannot stabilize the fixed population, return `MULTIFACTOR / UNRESOLVED` and `PRODUCT INTEGRATION VALIDATION STILL BLOCKED — CAUSE UNRESOLVED` rather than seeking a favorable host regime.
