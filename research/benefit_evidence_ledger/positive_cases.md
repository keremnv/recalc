# Positive-case catalog

Every currently proven positive case, separated by unit. Timings are
exact ledger values; comparators stated per row.

## Whole-task positive cases (2 trajectories + 2 descriptive task sums)

### r01 — `Debugging:07_01`, Claude-Sonnet-4.5 (trajectory)

```text
task:      Debugging:07_01 (SpreadsheetBench-2, controlled)
study:     Tier 1 external-validity (7d0db1e)
BASE:      15.477 s
RECALC:    13.210 s (released 0.2.0, same-window replay)
saved:     2.267 s (-14.6%)
served:    3 invocations / 3 loads / 63 reads / 0 iteration cells
parity:    11 VALID + 1 VALID-both-failed + 1 MISMATCH (triaged env-only)
workbook:  415,162 bytes, 9 sheets, mutating trajectory
source:    RUNTIME_REPLAY.jsonl run tier1-r01-P-Debugging-07_01
```

### r06 — `Financial_Model:11_05`, Mimo-v2.6-Pro (trajectory)

```text
task:      Financial_Model:11_05 (SpreadsheetBench-2, controlled)
study:     Tier 1 external-validity (7d0db1e)
BASE:      28.001 s
RECALC:    26.141 s (released 0.2.0, same-window replay)
saved:     1.860 s (-6.6%)
served:    5 invocations / 5 loads / 9,271 reads / 5,822 iteration cells
parity:    20 VALID + 3 MISMATCH (triaged env-only)
workbook:  593,396 bytes, 18 sheets, mutating trajectory
source:    RUNTIME_REPLAY.jsonl run tier1-r06-O-mimo-Financial_Model-11_05
```

### Task sums (descriptive, driven by the trajectories above)

- `Debugging:07_01` (r01+r02): 23.886 → 21.980 s (−1.906). r02 alone
  regressed (+0.361, no service); the task-sum win is entirely r01.
- `Financial_Model:11_05` (r05+r06): 32.923 → 32.049 s (−0.874). r05
  alone regressed (+0.986, no service); the win is entirely r06.

## Substep positive cases (18)

### Released-0.2.0 vignette window (1)

- `Financial_Model_08_02__4ca3ae46295d`, read-only inspection step:
  3.6866 → 0.7320 s (−2.9546, −80.14%), BASE→0.2.0, 4,800 cells,
  parity address-normalized identical, workbook bytes unchanged.
  (`docs/evidence/readme_vignette/timing.json`)

### R3 frozen confirmation windows (16 of 30 workloads, OFF→ON)

| workload | OFF → ON (s) | saved |
|---|---|---|
| Debugging_10_10__c7ec | 24.5964 → 1.7292 | −22.8672 |
| Debugging_10_07__e3a7 | 24.3776 → 1.7098 | −22.6678 |
| Debugging_10_07__6dd8 | 24.2102 → 1.6284 | −22.5818 |
| Financial_Model_08_02__625e | 5.4594 → 1.5600 | −3.8994 |
| Financial_Model_08_02__4ca3 | 5.4570 → 1.6696 | −3.7874 |
| Debugging_04_07__62a7 | 3.1048 → 0.5077 | −2.5971 |
| Debugging_05_02__f274 | 1.8285 → 0.4099 | −1.4186 |
| Financial_Model_15_03__6409 | 0.8845 → 0.5581 | −0.3264 |
| Financial_Model_02_05__9000 | 0.5807 → 0.4227 | −0.1580 |
| Financial_Model_02_05__c75e | 0.5783 → 0.4344 | −0.1439 |
| Debugging_02_06__7252 | 0.5577 → 0.4409 | −0.1168 |
| Debugging_09_03__0828 | 0.4969 → 0.3971 | −0.0998 |
| Template_15_03__68f4 | 0.4002 → 0.3732 | −0.0270 |
| Financial_Model_08_03__e48e | 1.6086 → 1.5902 | −0.0184 |
| Financial_Model_11_02__a443 | 0.5599 → 0.5487 | −0.0112 |
| Template_03_03__c76e | 0.4130 → 0.4125 | −0.0005 |

All `DIRECT_RUNTIME`, median-of-3, 30/30 A-differential parity. Each is a
single script execution (a substep of its source control trajectory).

### R2 frozen probe window (1)

- `Financial_Model_08_02__4ca3ae46295d`: BASE 3.0459 → ON 1.0388 s
  (−2.0071) on the probe host. Window 1 of 3 for this workload.

## Direct-block positive cases (10 of 10 served blocks)

Paired aggregate: 10.226 → 3.447 s (−6.779 s). Every served block
individually faster. Membership: r01 ×3 (63 reads), r06 ×5 (9,271 reads,
5,822 cells), r14 ×1 (4,607 reads, 3,480 cells), r18 ×1 (48 reads).
Evidence: "When Recalc actually served the relevant block directly in
this study, those observed blocks were faster" — and no further.
