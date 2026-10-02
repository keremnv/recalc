# Phase 10B preregistered attribution spec

Written after the path audit and experimental P1/P2/P3 arm implementation, before process fixtures and any scored Phase-10B timing. No +10 ms budget revision is permitted. The frozen Phase-10 evidence remains unchanged.

## Identity

- Repository HEAD: `254a5c14fa74fc3534493c565de84b38e7317175`; dirty worktree is identified by hashes below.
- Product P4: the exact installed Phase-10 v2 clean-environment wheel at `/tmp/librecalc-phase10-clean`.
- Phase-10B arm code and frozen comparator are pinned by SHA-256:

| File | SHA-256 |
|---|---|
| `product_integration_phase10b/population.json` | `c3a3c450e757a3d593174db0f0b0a09514edd334ed848f34452eed8ce1cf1d40` |
| `product_integration_phase10b/run_attribution.py` | `5bbad60aac1cca41840bb2bf3b73395adbbfe801b479287cbbd8a2b66f18ac87` |
| `product_integration_phase10b/process_fixtures.py` | `d6fa499629e5de0a1d23cb2e0ba2a32a06d9dda4d65e0405d0749b564692cfea` |
| `product_integration_phase10b/minimal_bootstrap/sitecustomize.py` | `5af71a50b314c4e6078349c25f2252d16f2ab5f49d241efd50df9fea2c77a709` |
| `src/librecalc_agent/native/launcher.c` | `4bca47ec5a19e86758ac03f15575a0e1f82e268ca6cce14ac08646865d84bf51` |
| `src/librecalc_agent/native/observer.c` | `d964837aaee179aa46da1353786baed2c0100eed2a5cba7fa25620ac5279e104` |
| `src/librecalc_agent/_bootstrap/sitecustomize.py` | `f4a64dcb0706a0670675502fba4663eba7b2519dbd197bdfe744d33ed5ee177b` |
| `src/librecalc_agent/config.py` | `abc1eb0a84ad4a1921bbf4a58ffe5ef011213291744e175e5b5301bae067f79e` |
| `src/librecalc_agent/_frozen/eligibility.py` | `bcd4a0f9b1d5f5b220b95c4fd5ce54d57bd444a77bb4376e4bfc90fd4f974381` |
| `product_integration_phase10/validate.py` | `d4a6c6afb11de64e8872262537446ad978453ec5aa231da1062f7bf96364502d` |
| `read_engine_phase3/benchmark.py` | `2e440684abdc5037dc589351cede87b039be58b78bd8104b0da574a38db00d2b` |
| `/tmp/librecalc-phase10-clean/bin/python` | `d3da5db3943ca4b8dac8e55f426ace65fd131c34e9d0da77b2454015662b9e2c` |
| `/tmp/librecalc-phase10-clean/bin/librecalc-agent` | `27d644a6f23218c74c190970c761126675ffcf9124fc2f241588e014e4fd4b3a` |
| `/tmp/librecalc-phase10-clean/lib/python3.13/site-packages/librecalc_agent/native/observer` | `31c1867c0ffc39e0de2b982923069781283297f2ab306a1e423c6ad190a6e46b` |
| `/tmp/librecalc-phase10-clean/lib/python3.13/site-packages/librecalc_agent/_bootstrap/sitecustomize.py` | `f4a64dcb0706a0670675502fba4663eba7b2519dbd197bdfe744d33ed5ee177b` |
| `/tmp/librecalc-phase10-clean/lib/python3.13/site-packages/librecalc_agent/_capture_helper.py` | `8c26994f8f40a819029839212a92a45d68822cf5639aea0cab916375e34219e7` |

- `empty_bootstrap/` contains no `sitecustomize.py`; its `.keep` file is excluded from Python imports.
- Host metadata is frozen in `environment.json`, SHA-256 `3295e7355777c5982cc0e16c14cce98db308300e908aeb67cf139cae32264a00`.

## Exact primary population

The exact 22 frozen Phase-10 representative `REFERENCE_ONLY` scripts are listed below in original representative order. `population.json` pins paths, task/family, script SHA-256, source workbook SHA-256 and staged workbook SHA-256; its digest appears above. No reranking or omission is allowed.

| Workload | Script SHA-256 | Source workbook SHA-256 | Staged workbook SHA-256 |
|---|---|---|---|
| `Template_15_03__5ad5663409d0` | `5ad5663409d0c391afd0f36dc925a338c502ed7afd47b7187293d690611641b6` | `6b59c89a4a3c05e503c9df94cbb965a7246bea9c2446d7dceaf79be6f6ae258f` | `6b59c89a4a3c05e503c9df94cbb965a7246bea9c2446d7dceaf79be6f6ae258f` |
| `Template_06_12__3d05a7ee874d` | `3d05a7ee874db894026f7f48981f5d8cde2fe22fbd65042bcb29edfe140c934d` | `d05d2bcd62e971dab1907e3b290cc7e46c161f5d1d3bfac6266d04bd831ddeba` | `d05d2bcd62e971dab1907e3b290cc7e46c161f5d1d3bfac6266d04bd831ddeba` |
| `Template_06_12__83f82ce3f62b` | `83f82ce3f62bbbcb5333f6ca5cdd270576d044b6fae192efe5c76a19410b7d4a` | `d05d2bcd62e971dab1907e3b290cc7e46c161f5d1d3bfac6266d04bd831ddeba` | `d05d2bcd62e971dab1907e3b290cc7e46c161f5d1d3bfac6266d04bd831ddeba` |
| `Template_15_03__68f4733f2576` | `68f4733f25762dd3f9c85f6a80f970bc04371cad59adce693f3337f550a51bf1` | `6b59c89a4a3c05e503c9df94cbb965a7246bea9c2446d7dceaf79be6f6ae258f` | `6b59c89a4a3c05e503c9df94cbb965a7246bea9c2446d7dceaf79be6f6ae258f` |
| `Template_15_01__fa75e25f6a90` | `fa75e25f6a904785d20c0acbf833cf4c6c5a1c940210e1b82e6c0a04775f5a17` | `0cce1cbcae88e9dbcc2d33743c76179443119357d80e8d24d38b3e99a404a0c6` | `0cce1cbcae88e9dbcc2d33743c76179443119357d80e8d24d38b3e99a404a0c6` |
| `Template_06_02__c26a4c6508ba` | `c26a4c6508ba40e1186fc8eba8fe5b653dc04c6ff6dadb69d24d942527fc8d22` | `76ff3caea33395983113db652c35d5a14b46e7be8588f06f26092990fef1cc19` | `76ff3caea33395983113db652c35d5a14b46e7be8588f06f26092990fef1cc19` |
| `Template_06_02__85fab8c95cea` | `85fab8c95cea9d5419d812a21f36fd315fda9d014a8af1dfd47c8053009fc2cc` | `76ff3caea33395983113db652c35d5a14b46e7be8588f06f26092990fef1cc19` | `76ff3caea33395983113db652c35d5a14b46e7be8588f06f26092990fef1cc19` |
| `Financial_Model_08_02__4ca3ae46295d` | `4ca3ae46295d01eb593acad8ea57be99442fbfeee4f1a5376b5ba284acfd88b6` | `9928600b0184036b03a8664c1e2dcd8994e5f90e866d68c140dd6543b3ac0aff` | `9928600b0184036b03a8664c1e2dcd8994e5f90e866d68c140dd6543b3ac0aff` |
| `Financial_Model_15_03__64092e664e9b` | `64092e664e9b7cf08c10b5205b302bf9005c0d5890b2bf082cf76e82983ecd40` | `318eed515474a4e8c0684d3895e49e4726728d1166c2f83ef71b936d32dbf3d7` | `318eed515474a4e8c0684d3895e49e4726728d1166c2f83ef71b936d32dbf3d7` |
| `Financial_Model_02_05__c75ecb00f745` | `c75ecb00f74516f13a4a8049a7459be03356b89e52098736463b619518b41bf6` | `f61402df84ff17d94590f86939a408f786cb4fdeba82eb3e1911d8ebb839febd` | `f61402df84ff17d94590f86939a408f786cb4fdeba82eb3e1911d8ebb839febd` |
| `Financial_Model_02_05__90004332940a` | `90004332940ab83e9b76bee957d8d87dd6ba0e9d044906c6a269c53e4d97ac78` | `f61402df84ff17d94590f86939a408f786cb4fdeba82eb3e1911d8ebb839febd` | `f61402df84ff17d94590f86939a408f786cb4fdeba82eb3e1911d8ebb839febd` |
| `Financial_Model_08_02__625ec1db4acb` | `625ec1db4acbbfeac9b8daaa50457b6a137a5d0481d9d8ab81a6d1d53d8e8246` | `9928600b0184036b03a8664c1e2dcd8994e5f90e866d68c140dd6543b3ac0aff` | `9928600b0184036b03a8664c1e2dcd8994e5f90e866d68c140dd6543b3ac0aff` |
| `Debugging_05_02__f274eaa3cc8e` | `f274eaa3cc8e366dabb404cbc85db6c0d998ca67f50fb941fbf9c892a9f00cd5` | `fa7c8d05a020ef079d6330fe7d1e3de64b35be0e9cc99d413c1bc30e7e19565e` | `fa7c8d05a020ef079d6330fe7d1e3de64b35be0e9cc99d413c1bc30e7e19565e` |
| `Debugging_09_03__0828d4dfbd13` | `0828d4dfbd137e47a235624d244a4e3e8996643edd2c5a5e6cdf42045b65cda5` | `f1ca163a1198e742864c9814016b49f397a0f1d0469685a5d7efd618aec7ca5a` | `f1ca163a1198e742864c9814016b49f397a0f1d0469685a5d7efd618aec7ca5a` |
| `Debugging_10_07__6dd8f6d3a4dd` | `6dd8f6d3a4dd5f9b166e269862419e4a1f2b33ed91da0058630adee76fc56a42` | `0d51c60e2cbef7e4b675815f9873fe69c01cac1e06cd69bf8a5751c1f64ee956` | `0d51c60e2cbef7e4b675815f9873fe69c01cac1e06cd69bf8a5751c1f64ee956` |
| `Debugging_09_03__59822a6e11e7` | `59822a6e11e748dced202ff39c6e03af4f09a84147e1da3116a53bad9434fe4b` | `f1ca163a1198e742864c9814016b49f397a0f1d0469685a5d7efd618aec7ca5a` | `f1ca163a1198e742864c9814016b49f397a0f1d0469685a5d7efd618aec7ca5a` |
| `Debugging_02_06__7252ca64cf1c` | `7252ca64cf1c7e434feb481f5a531a6ec38ec25852e3a3ccfc6556a0b8c40b1e` | `8201c6f818b331626002113e51b43d30aafb7ebe27218b3457111042ee3f6d1f` | `8201c6f818b331626002113e51b43d30aafb7ebe27218b3457111042ee3f6d1f` |
| `Debugging_04_07__62a7766ef582` | `62a7766ef582f2ed6abd70dea493060185d1ed1de93ce7a026ad2d1c295c4e96` | `d148f7eefd3b1578aaf1b39dc3f34dbf2628719a68e9f956d7b3ca49c245c886` | `d148f7eefd3b1578aaf1b39dc3f34dbf2628719a68e9f956d7b3ca49c245c886` |
| `Debugging_10_07__e3a79d24091a` | `e3a79d24091a5d792f9c9c017b59e00b563fa1da4d2da35e1f6332a2a803e5e3` | `0d51c60e2cbef7e4b675815f9873fe69c01cac1e06cd69bf8a5751c1f64ee956` | `0d51c60e2cbef7e4b675815f9873fe69c01cac1e06cd69bf8a5751c1f64ee956` |
| `Debugging_10_10__c7eca76e6646` | `c7eca76e664673057398fd0113bd5d46b4641651030b6d91e6023cdac28c4afc` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` |
| `Debugging_02_06__88edc6528ef0` | `88edc6528ef05d20e9f9c555d8aaf494ab384f893e3c5fc01d4994249c1fc0e0` | `8201c6f818b331626002113e51b43d30aafb7ebe27218b3457111042ee3f6d1f` | `8201c6f818b331626002113e51b43d30aafb7ebe27218b3457111042ee3f6d1f` |
| `Debugging_01_04__542f8461a344` | `542f8461a344298bf6f633eca6053a9d512b1954438e8d3f0817a96318258160` | `d01f1c1025176da9cfbabe38cfca0776fd77e7287f6138e6fe85ab06394d457a` | `d01f1c1025176da9cfbabe38cfca0776fd77e7287f6138e6fe85ab06394d457a` |

## Causal arms and attribution

- **P0**: `/tmp/librecalc-phase10-clean/bin/python workload.py`, no observer or LibreCalc bootstrap.
- **P1**: installed production native observer with empty bootstrap directory; observer pre/post XLSX snapshots, target wait/exit/signal, changed-file helper capability and receipt remain. The observer still sets its normal launch context/PYTHONPATH; P1−P0 measures the **current observer envelope**, not a theoretical minimum.
- **P2**: P1 plus `minimal_bootstrap/sitecustomize.py`, which reads the four-line context and checks the real target script path; no config, classifier, artifact or direct runtime.
- **P3**: direct production observer plus the installed full production bootstrap. Negative admission must yield `REFERENCE_FAST_PATH`, no artifact and ordinary openpyxl. This includes config, source read, classifier and setup receipt.
- **P4**: unchanged installed `librecalc-agent run --workdir WORK workload.py`, including native launcher dispatch, observer, production bootstrap and negative route.
- P1–P3 precreate the observer cache/run parent directories as benchmark staging because the observer expects them. P4 charges its launcher-owned creation/chmod. On the scored second invocation, directories already exist for every observer arm.
- The designed increments are P1−P0 (observer/assurance envelope), P2−P1 (minimal target guard), P3−P2 (config/classifier/setup), P4−P3 (launcher and remaining production dispatch). These are per-workload paired full-command differences, never subtraction of aggregate medians.
- No optional sixth causal arm is included. P5 is conditional and would require a versioned preregistration amendment and separately pinned implementation before any P5 score.

## Process, object and correctness gates

Before score, `process_fixtures.py` runs P0–P4 on `module_argv_path`, `stdout_stderr`, `system_exit`, `uncaught_exception`, `atexit`, `local_import`, `subprocess`, `inherited_fd`, `caught_sigint`, `fatal_sigterm`, `abrupt_exit_after_write`, `atexit_write`, and `reference_objects`. Target exit, stdout, workbook value and (except traceback file paths) stderr must match P0. P1–P4 must write `assurance_status=PASS`; P3/P4 must report `REFERENCE_FAST_PATH` with no artifacts. The reference-object fixture checks real workbook/worksheet/cell types, real `load_workbook` module and cell-parent identity. An abnormal-exit changed workbook must still be observed and captured. Any gate failure stops scoring.
For every scored workload and invocation, stage exact bytes outside the timer. Compare each P1–P4 against P0 using the frozen Phase-3 result comparator; only `EXACT` and `VOLATILE_ONLY_DIFFERENCE` are acceptable. Require exit parity, no timeout, observer `PASS`, P3/P4 reference route and empty artifact map. Stop on a mismatch; do not select surviving rows.

## Timing protocol

- Two scored repetitions per workload, with invocation 1 and invocation 2 in each repetition; primary analysis uses invocation 2 only. Fresh arm-specific caches and workdirs begin each repetition. This matches Phase 10 repetition count without a larger search.
- Every scored command is a fresh process. The external timer starts immediately before `subprocess.run` and stops after command exit. Staging, input hash checks and result-file inspection are outside the timer.
- Arm order is `random.Random((20260928 XOR 0x10B) XOR first12hex(SHA256(workload_id:rep:invocation))).shuffle(P0..P4)`, implemented in the pinned runner. No favorable ordering adjustment.
- OS filesystem caching is not controlled; first and second invocations are labeled. No cold-disk claim is allowed.
- Timeout: 180 seconds per command. A timeout stops interpretation. No benchmark daemon/background run. A single one-shot scored batch writes append-only rows.
- Host/runtime: Python 3.13.12, openpyxl 3.1.5, Ubuntu 26.04.1, Linux 7.0.0-34-generic x86_64, Intel Core Ultra 5 125H, ext2/ext3 reported filesystem, as pinned in `environment.json`. Environment removes `PYTHONPATH`, LibreCalc context/config and Candidate-A research variables; sets `PYTHONDONTWRITEBYTECODE=1` and an arm-specific XDG cache.

## Analysis and fixed decisions

For each workload and repetition, calculate signed full-command differences and ratios for P4/P0, P1/P0, P2/P1, P3/P2 and P4/P3 on invocation 2. Take the median of the two repetition effects within workload; then report population median, geometric mean ratio, range, faster/slower/tied and seeded 5,000-resample workload-bootstrap median intervals. Preserve raw rows and task-cluster sensitivity. Profile observer internal times/import diagnostics only to explain, not to replace causal increments.
- **Budget**: median signed P4−P0 second-invocation excess must be **≤ +10 ms**. This exact margin is frozen from Phase 10.
- **Tax replicated**: P4−P0 population median signed excess > +10 ms in the same direction on the same-run 22. Otherwise `TAX DID NOT REPLICATE`.
- **Material removable candidate**: a non-assurance, non-routing increment has median signed cost at least +5 ms with bootstrap interval lower bound above zero; there must be a general semantically safe single change plausibly capable of closing the observed gap. If none, do not implement P5.
- If P5 is earned, amend this spec, hash the amendment, then rerun fixture gates and the exact 22 with same full-command endpoint. Seven frozen direct-contact scripts and five changed-file plus abrupt-exit fixtures are regression controls only after P5; do not run them across P0–P4.
- A future budget review can be *recommended* only if tax replicates, the measured P1 observer envelope explains a substantial part, remaining increments lack a safe bounded removal sufficient to meet +10 ms, and correctness/direct benefits remain intact. The budget cannot be changed or used to pass Phase 10B.
- Stop on unreliable identity, process semantic failure, comparator mismatch, missing receipt, invalid route, or timing environment instability that makes same-run pairing unusable. Do not add arms or broaden population to seek a favorable result.

## Required evidence

Write `process_semantics.jsonl`, `correctness.jsonl`, `raw_timings.jsonl`, `analysis.json`, `profile.json` and a final report. Keep Phase-10 ledgers unchanged. Only an earned P5 requires direct-contact/changed-file/abrupt regression ledgers.
