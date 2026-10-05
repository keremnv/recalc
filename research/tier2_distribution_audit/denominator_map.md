# Tier 2 denominator map

```text
30 = 13 TARGETS + 8 ADMITTED_PREEXISTING + 9 BLOCKED_OTHER
13 = iteration-only-blocked subset of the 30 (frozen target rule)
relationship = 13 ⊂ 30 (strict subset; disjoint 13/8/9 partition covers all 30)
aggregate timing denominator = all 30 (OFF → ON, Σ per-workload medians)
direct-route denominator = 13 targets (13/13 DIRECT_RUNTIME throughout)
```

## The 13 targets (subset of the 30)

Rule (`research/full_cell_iteration_probe/TARGET_WORKLOADS.json`):
Population A workloads whose classifier blockers ⊆ {iterator shape not
statically proven, `CELL_OBJECT_ITERATION_BOUNDARY`}. Held 64.1/64.5 s of
reference-path parse (R1 `OPERATION_CENSUS.jsonl`).

- Debugging_02_06__7252ca64cf1c
- Debugging_04_07__62a7766ef582
- Debugging_05_02__f274eaa3cc8e
- Debugging_09_03__0828d4dfbd13
- Debugging_10_07__6dd8f6d3a4dd
- Debugging_10_07__e3a79d24091a
- Debugging_10_10__c7eca76e6646
- Financial_Model_02_05__90004332940a
- Financial_Model_02_05__c75ecb00f745
- Financial_Model_08_02__4ca3ae46295d (vignette workload)
- Financial_Model_08_02__625ec1db4acb
- Financial_Model_15_03__64092e664e9b
- Template_15_03__68f4733f2576

## The 8 pre-existing admitted (not targets, already direct under rc3/OFF)

- Financial_Model_02_01__79352976d750 (DIRECT)
- Financial_Model_02_01__bb15e0fe3832 (DIRECT)
- Financial_Model_08_01__2ea507d758dc (DIRECT)
- Financial_Model_08_03__e48ea186deeb (DIRECT)
- Financial_Model_11_02__a443eee257b4 (DIRECT)
- Template_03_03__c76ea596b408 (DIRECT)
- Template_16_07__9662584ede5e (DIRECT)
- Template_06_23__fc41ad37c48b (pre-existing DIRECT_WITH_FALLBACK)

## The 9 blocked on other grounds (reference throughout)

- Debugging_01_04__542f8461a344
- Debugging_02_06__88edc6528ef0
- Debugging_09_03__59822a6e11e7
- Template_06_02__85fab8c95cea
- Template_06_02__c26a4c6508ba
- Template_06_12__3d05a7ee874d
- Template_06_12__83f82ce3f62b
- Template_15_01__fa75e25f6a90
- Template_15_03__5ad5663409d0

## Qualification rule for public writing

"13/13 direct" may appear beside the 30-workload aggregate only with the
subset relation stated (the 13 are the iteration-blocked subset; the
other 17 were never expected to convert). The aggregate denominator is
30; the conversion denominator is 13.
