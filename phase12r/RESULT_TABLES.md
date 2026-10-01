# Frozen replay result tables

P1 is primary; P2 is research validation; P3 is secondary historical context. No pooled prevalence. All denominators include eligible unresolved rows unless explicitly labeled scorable.

## Population and official outcomes

| Stratum | Eligible runs | Tasks | Scorable pairs | Exact 0→1 | Exact 1→0 | Modification +≥.01 | Modification −≥.01 | Regression +≥.01 | Regression −≥.01 |
|---|---|---|---|---|---|---|---|---|---|
| P1 | 183 | 98 | 142 | 0 | 0 | 0 | 1 | 0 | 1 |
| P2 | 191 | 60 | 163 | 17 | 0 | 123 | 3 | 36 | 14 |
| P3 | 848 | 297 | 331 | 0 | 0 | 1 | 2 | 0 | 2 |

## Cache attribution

| Stratum | Cache-only recovery runs | All-run rate | Historically score-compatible runs | Affected tasks | Task rate | Unresolved historical run bound |
|---|---|---|---|---|---|---|
| P1 | 0 | 0.00% | 0 | 0 | 0.00% | 0.00%–22.40% |
| P2 | 46 | 24.08% | 9 | 21 | 35.00% | 4.71%–72.77% |
| P3 | 0 | 0.00% | 0 | 0 | 0.00% | 0.00%–61.08% |

## P1 categories

| Category | Runs / tasks | Scorable | Cache-only runs / tasks | All-run rate | Task rate | Exact + / − | Modification + / − | Harms / unresolved |
|---|---|---|---|---|---|---|---|---|
| Template | 41 / 27 | 41 | 0 / 0 | 0.00% | 0.00% | 0 / 0 | 0 / 0 | 0 / 0 |
| Financial_Model | 101 / 43 | 73 | 0 / 0 | 0.00% | 0.00% | 0 / 0 | 0 / 1 | 1 / 28 |
| Debugging | 41 / 28 | 28 | 0 / 0 | 0.00% | 0.00% | 0 / 0 | 0 / 0 | 0 / 13 |

### P1 classifications

| Class | Runs |
|---|---|
| RECALC_NO_MATERIAL_EFFECT | 141 |
| RECALC_REGRESSION | 1 |
| UNSCORABLE | 41 |

### P1 identity

| Identity | Runs |
|---|---|
| FORMULAS_BYTE_IDENTICAL | 143 |
| UNDETERMINED | 40 |

### P1 continuous score deltas

| Score | N | Min | p10 | Median | p90 | Max | Mean | Sum |
|---|---|---|---|---|---|---|---|---|
| accuracy | 142 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| modification_accuracy | 142 | -0.1129 | 0.0 | 0.0 | 0.0 | 0.0 | -0.0007950704225352113 | -0.1129 |
| regression_accuracy | 142 | -0.012900000000000023 | 0.0 | 0.0 | 0.0 | 0.0 | -9.507042253521096e-05 | -0.013499999999999956 |

## P2 categories

| Category | Runs / tasks | Scorable | Cache-only runs / tasks | All-run rate | Task rate | Exact + / − | Modification + / − | Harms / unresolved |
|---|---|---|---|---|---|---|---|---|
| Template | 108 / 32 | 106 | 45 / 20 | 41.67% | 62.50% | 11 / 0 | 73 / 0 | 12 / 2 |
| Financial_Model | 64 / 17 | 40 | 0 / 0 | 0.00% | 0.00% | 6 / 0 | 38 / 0 | 0 / 24 |
| Debugging | 19 / 11 | 17 | 1 / 1 | 5.26% | 9.09% | 0 / 0 | 12 / 3 | 5 / 2 |

### P2 classifications

| Class | Runs |
|---|---|
| CACHE_ONLY_SCORE_RECOVERY | 46 |
| RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN | 65 |
| RECALC_NO_MATERIAL_EFFECT | 35 |
| RECALC_REGRESSION | 17 |
| UNSCORABLE | 28 |

### P2 identity

| Identity | Runs |
|---|---|
| FORMULAS_BYTE_IDENTICAL | 33 |
| FORMULAS_CHANGED_BY_LIBREOFFICE | 31 |
| FORMULAS_SEMANTICALLY_IDENTICAL_BUT_PACKAGE_CHANGED | 99 |
| UNDETERMINED | 28 |

### P2 continuous score deltas

| Score | N | Min | p10 | Median | p90 | Max | Mean | Sum |
|---|---|---|---|---|---|---|---|---|
| accuracy | 163 | 0.0 | 0.0 | 0.0 | 0.8000000000000114 | 1.0 | 0.10429447852760736 | 17.0 |
| modification_accuracy | 163 | -0.3333 | 0.0 | 0.6204 | 0.99856 | 1.0 | 0.5402576687116565 | 88.062 |
| regression_accuracy | 163 | -0.06680000000000008 | -0.005979999999999986 | 0.0 | 0.14839999999999998 | 0.35509999999999997 | 0.031726380368098155 | 5.171399999999999 |

## P3 categories

| Category | Runs / tasks | Scorable | Cache-only runs / tasks | All-run rate | Task rate | Exact + / − | Modification + / − | Harms / unresolved |
|---|---|---|---|---|---|---|---|---|
| Template | 269 / 97 | 173 | 0 / 0 | 0.00% | 0.00% | 0 / 0 | 0 / 0 | 0 / 96 |
| Financial_Model | 316 / 100 | 88 | 0 / 0 | 0.00% | 0.00% | 0 / 0 | 0 / 2 | 2 / 228 |
| Debugging | 263 / 100 | 70 | 0 / 0 | 0.00% | 0.00% | 0 / 0 | 1 / 0 | 0 / 193 |

### P3 classifications

| Class | Runs |
|---|---|
| RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN | 1 |
| RECALC_NO_MATERIAL_EFFECT | 328 |
| RECALC_REGRESSION | 2 |
| UNSCORABLE | 517 |

### P3 identity

| Identity | Runs |
|---|---|
| FORMULAS_BYTE_IDENTICAL | 663 |
| UNDETERMINED | 185 |

### P3 continuous score deltas

| Score | N | Min | p10 | Median | p90 | Max | Mean | Sum |
|---|---|---|---|---|---|---|---|---|
| accuracy | 331 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| modification_accuracy | 331 | -0.16579999999999995 | 0.0 | 0.0 | 0.0 | 0.0588 | -0.0008241691842900299 | -0.2727999999999999 |
| regression_accuracy | 331 | -0.012700000000000045 | 0.0 | 0.0 | 0.0 | 0.0 | -8.761329305135993e-05 | -0.029000000000000137 |

## Formula cache census

| Stratum | V0 inspected | Formula workbooks | Missing-cache workbooks | Replay-stale workbooks | V0 formula cells | V0 missing cells | V0 error cells |
|---|---|---|---|---|---|---|---|
| P1 | 183 | 179 | 0 | 30 | 3688057 | 0 | 5599 |
| P2 | 191 | 171 | 153 | 4 | 1956564 | 1936046 | 48 |
| P3 | 845 | 845 | 0 | 57 | 12834123 | 0 | 40147 |

A present cache that changed is stale relative to this LibreOffice execution; it is not independently established to have been wrong. Missing and changed-present workbooks can overlap.

## Original score reproduction

| Stratum | Returned tuple reproduced | Returned tuple different | Unavailable | Archived / unverified |
|---|---|---|---|---|
| P1 | 183 | 0 | 0 | {'ARCHIVED_SUBMISSION': 183} |
| P2 | 85 | 106 | 0 | {'RUN_LOCAL_UNVERIFIED': 160, 'ARCHIVED_SUBMISSION': 31} |
| P3 | 473 | 372 | 3 | {'RUN_LOCAL_UNVERIFIED': 29, 'ARCHIVED_SUBMISSION': 819} |

Historical evaluator source versions are unavailable. Numeric reproduction does not establish historical implementation identity.

## P2 experiments

| Experiment | Runs / tasks | Scorable | Strong / historical gains | Exact + / − | Modification + / − | Harms |
|---|---|---|---|---|---|---|
| batch_write_helper_ab | 11 / 6 | 11 | 4 / 0 | 1 / 0 | 7 / 0 | 2 |
| candidate_a_a1_checkpoint_rerun_01 | 7 / 5 | 3 | 2 / 2 | 0 / 0 | 2 / 0 | 0 |
| candidate_a_live | 1 / 1 | 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 |
| formula_error_delivery_probe | 1 / 1 | 1 | 0 / 0 | 0 / 0 | 0 / 0 | 1 |
| formula_error_feedback_discovery | 4 / 3 | 4 | 0 / 0 | 0 / 0 | 4 / 0 | 1 |
| inspection_efficiency_ab | 12 / 5 | 12 | 3 / 0 | 1 / 0 | 8 / 0 | 0 |
| live_transparent_runtime_ab | 11 / 7 | 9 | 3 / 0 | 1 / 0 | 6 / 0 | 0 |
| phase12 | 23 / 12 | 21 | 7 / 7 | 3 / 0 | 10 / 0 | 2 |
| representative_architecture_checkpoint | 31 / 13 | 31 | 10 / 0 | 1 / 0 | 29 / 0 | 4 |
| targeted_runtime_replication | 15 / 6 | 12 | 3 / 0 | 0 / 0 | 8 / 0 | 0 |
| thin_architecture_checkpoint | 26 / 12 | 18 | 5 / 0 | 4 / 0 | 15 / 0 | 0 |
| token_affordance_discovery | 10 / 3 | 6 | 4 / 0 | 0 / 0 | 5 / 0 | 0 |
| token_claim_discovery | 39 / 13 | 35 | 5 / 0 | 6 / 0 | 29 / 3 | 7 |

## Task clustering

| Stratum | Task | Runs | Scorable | Cache-only runs | Historically score-compatible gains | Exact + / − |
|---|---|---|---|---|---|---|
| P1 | Debugging:01_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Debugging:01_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Debugging:01_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Debugging:01_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:02_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:02_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Debugging:02_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:02_09 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Debugging:03_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:03_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:04_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:04_07 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:04_09 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Debugging:05_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:05_08 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:06_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:06_07 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:06_09 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Debugging:07_03 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:07_08 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Debugging:08_04 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:08_09 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:08_10 | 2 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:09_04 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:09_09 | 3 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:10_04 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:10_05 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Debugging:10_10 | 3 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:01_01 | 4 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:01_02 | 4 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:02_01 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:02_05 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:03_01 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:03_02 | 4 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:04_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:04_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:04_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:04_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:05_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:06_01 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:07_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:07_04 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:08_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:08_02 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:08_03 | 4 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:08_04 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:08_05 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:09_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:10_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:10_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:11_01 | 4 | 4 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:11_02 | 8 | 8 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:11_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:11_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:12_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:13_02 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:13_05 | 5 | 5 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:14_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:14_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:15_04 | 1 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:15_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:16_05 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:17_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:17_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:18_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:18_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:19_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:19_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:20_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:20_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Financial_Model:20_05 | 10 | 10 | 0 | 0 | 0 / 0 |
| P1 | Template:01_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:01_07 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:02_05 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:03_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Template:04_04 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Template:05_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:06_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:06_09 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:06_12 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:06_16 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:06_17 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Template:06_18 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Template:06_21 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:07_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:08_03 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:09_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Template:09_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P1 | Template:10_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:10_02 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Template:11_03 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:13_03 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:13_08 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:14_05 | 3 | 3 | 0 | 0 | 0 / 0 |
| P1 | Template:15_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:16_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:16_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P1 | Template:16_12 | 4 | 4 | 0 | 0 | 0 / 0 |
| P2 | Debugging:01_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Debugging:02_01 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Debugging:02_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Debugging:02_06 | 5 | 5 | 1 | 0 | 0 / 0 |
| P2 | Debugging:02_09 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Debugging:03_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Debugging:04_07 | 2 | 2 | 0 | 0 | 0 / 0 |
| P2 | Debugging:06_10 | 2 | 2 | 0 | 0 | 0 / 0 |
| P2 | Debugging:07_05 | 3 | 3 | 0 | 0 | 0 / 0 |
| P2 | Debugging:09_03 | 1 | 0 | 0 | 0 | 0 / 0 |
| P2 | Debugging:10_10 | 1 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:01_01 | 5 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:02_01 | 4 | 4 | 0 | 0 | 2 / 0 |
| P2 | Financial_Model:02_04 | 6 | 6 | 0 | 0 | 1 / 0 |
| P2 | Financial_Model:02_05 | 5 | 5 | 0 | 0 | 1 / 0 |
| P2 | Financial_Model:03_03 | 6 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:04_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:07_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:08_01 | 1 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:08_03 | 5 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:09_02 | 3 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:09_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:11_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:13_05 | 9 | 9 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:15_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:17_02 | 3 | 3 | 0 | 0 | 2 / 0 |
| P2 | Financial_Model:18_03 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Financial_Model:18_05 | 8 | 8 | 0 | 0 | 0 / 0 |
| P2 | Template:01_02 | 7 | 7 | 0 | 0 | 0 / 0 |
| P2 | Template:01_05 | 7 | 7 | 0 | 0 | 0 / 0 |
| P2 | Template:01_07 | 2 | 2 | 0 | 0 | 0 / 0 |
| P2 | Template:02_01 | 2 | 2 | 2 | 0 | 0 / 0 |
| P2 | Template:02_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P2 | Template:03_03 | 4 | 4 | 1 | 1 | 0 / 0 |
| P2 | Template:04_04 | 6 | 6 | 4 | 0 | 0 / 0 |
| P2 | Template:05_02 | 1 | 1 | 0 | 0 | 0 / 0 |
| P2 | Template:06_02 | 6 | 6 | 1 | 0 | 4 / 0 |
| P2 | Template:06_05 | 2 | 2 | 1 | 1 | 1 / 0 |
| P2 | Template:06_08 | 4 | 4 | 4 | 0 | 0 / 0 |
| P2 | Template:06_09 | 1 | 1 | 1 | 1 | 1 / 0 |
| P2 | Template:06_12 | 8 | 8 | 8 | 0 | 0 / 0 |
| P2 | Template:06_16 | 2 | 2 | 1 | 1 | 1 / 0 |
| P2 | Template:06_17 | 2 | 2 | 2 | 0 | 1 / 0 |
| P2 | Template:06_22 | 2 | 2 | 0 | 0 | 1 / 0 |
| P2 | Template:06_23 | 2 | 2 | 1 | 0 | 0 / 0 |
| P2 | Template:06_25 | 2 | 2 | 1 | 1 | 0 / 0 |
| P2 | Template:10_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P2 | Template:10_02 | 2 | 2 | 1 | 1 | 0 / 0 |
| P2 | Template:11_01 | 2 | 2 | 1 | 1 | 0 / 0 |
| P2 | Template:11_03 | 2 | 2 | 1 | 1 | 0 / 0 |
| P2 | Template:11_04 | 3 | 3 | 0 | 0 | 0 / 0 |
| P2 | Template:13_08 | 4 | 4 | 2 | 1 | 0 / 0 |
| P2 | Template:14_03 | 3 | 3 | 0 | 0 | 0 / 0 |
| P2 | Template:15_01 | 4 | 4 | 3 | 0 | 1 / 0 |
| P2 | Template:15_03 | 6 | 6 | 5 | 0 | 0 / 0 |
| P2 | Template:16_01 | 2 | 2 | 2 | 0 | 0 / 0 |
| P2 | Template:16_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P2 | Template:16_06 | 3 | 3 | 0 | 0 | 0 / 0 |
| P2 | Template:16_07 | 6 | 6 | 0 | 0 | 0 / 0 |
| P2 | Template:16_08 | 5 | 5 | 3 | 0 | 1 / 0 |
| P3 | Debugging:01_01 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_02 | 4 | 4 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_04 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_05 | 5 | 4 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_06 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_09 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:01_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_01 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_03 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_04 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_05 | 4 | 3 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_06 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_09 | 7 | 2 | 0 | 0 | 0 / 0 |
| P3 | Debugging:02_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_01 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_04 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_06 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_07 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_09 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:03_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_02 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_04 | 7 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_06 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_09 | 8 | 2 | 0 | 0 | 0 / 0 |
| P3 | Debugging:04_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_01 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_03 | 8 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_04 | 6 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_06 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_08 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_09 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:05_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_01 | 4 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_04 | 5 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_06 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_07 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_09 | 11 | 2 | 0 | 0 | 0 / 0 |
| P3 | Debugging:06_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_01 | 6 | 2 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_04 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_06 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_09 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:07_10 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_03 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_06 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_07 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_08 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_09 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:08_10 | 7 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_03 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_04 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_06 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_07 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_08 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_09 | 4 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:09_10 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_02 | 4 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_06 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_07 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_08 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_09 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Debugging:10_10 | 7 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:01_01 | 5 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:01_02 | 13 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:01_03 | 4 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:01_04 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:01_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:02_01 | 4 | 4 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:02_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:02_03 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:02_04 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:02_05 | 5 | 5 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:03_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:03_02 | 7 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:03_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:03_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:03_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:04_01 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:04_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:04_03 | 4 | 3 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:04_04 | 8 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:04_05 | 4 | 3 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:05_01 | 3 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:05_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:05_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:05_04 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:05_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:06_01 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:06_02 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:06_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:06_04 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:06_05 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:07_01 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:07_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:07_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:07_04 | 4 | 3 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:07_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:08_01 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:08_02 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:08_03 | 11 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:08_04 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:08_05 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:09_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:09_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:09_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:09_04 | 8 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:09_05 | 4 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:10_01 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:10_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:10_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:10_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:10_05 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:11_01 | 5 | 3 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:11_02 | 10 | 8 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:11_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:11_04 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:11_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:12_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:12_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:12_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:12_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:12_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:13_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:13_02 | 10 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:13_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:13_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:13_05 | 6 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:14_01 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:14_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:14_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:14_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:14_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:15_01 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:15_02 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:15_03 | 1 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:15_04 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:15_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:16_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:16_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:16_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:16_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:16_05 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:17_01 | 8 | 1 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:17_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:17_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:17_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:17_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:18_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:18_02 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:18_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:18_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:18_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:19_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:19_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:19_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:19_04 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:19_05 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:20_01 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:20_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:20_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:20_04 | 4 | 2 | 0 | 0 | 0 / 0 |
| P3 | Financial_Model:20_05 | 16 | 11 | 0 | 0 | 0 / 0 |
| P3 | Template:01_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:01_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:01_03 | 3 | 3 | 0 | 0 | 0 / 0 |
| P3 | Template:01_04 | 3 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:01_05 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:01_06 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:01_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:01_08 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:01_09 | 1 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:02_01 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:02_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:02_03 | 3 | 3 | 0 | 0 | 0 / 0 |
| P3 | Template:02_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:02_05 | 13 | 8 | 0 | 0 | 0 / 0 |
| P3 | Template:02_06 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:03_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:03_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:03_03 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:03_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:04_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:04_04 | 8 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:05_01 | 13 | 13 | 0 | 0 | 0 / 0 |
| P3 | Template:05_02 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:06_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:06_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_06 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_07 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_08 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:06_09 | 3 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:06_11 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_12 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:06_13 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_14 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_15 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_16 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:06_17 | 3 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:06_18 | 8 | 6 | 0 | 0 | 0 / 0 |
| P3 | Template:06_19 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_20 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_21 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:06_22 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:06_23 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:06_24 | 12 | 12 | 0 | 0 | 0 / 0 |
| P3 | Template:06_25 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:07_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:07_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:07_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:08_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:08_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:08_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:09_01 | 4 | 3 | 0 | 0 | 0 / 0 |
| P3 | Template:09_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:09_03 | 4 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:09_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:10_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:10_02 | 10 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:11_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:11_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:11_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:11_04 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:12_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_06 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_07 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:13_08 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:14_01 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:14_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:14_03 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:14_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:14_05 | 8 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:14_06 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:14_07 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:14_08 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:14_09 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:15_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:15_02 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:15_03 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:15_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:16_01 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:16_02 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:16_03 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:16_04 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:16_05 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:16_06 | 1 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:16_07 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:16_08 | 2 | 1 | 0 | 0 | 0 / 0 |
| P3 | Template:16_09 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:16_10 | 2 | 0 | 0 | 0 | 0 / 0 |
| P3 | Template:16_11 | 2 | 2 | 0 | 0 | 0 / 0 |
| P3 | Template:16_12 | 9 | 1 | 0 | 0 | 0 / 0 |

Run identities are in SUMMARY.json and BASELINE_CORRECTION_LEDGER.jsonl. No independent-run significance claims are made.
