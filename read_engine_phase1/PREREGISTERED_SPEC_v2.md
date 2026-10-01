# Read-engine Phase 1 — preregistered specification v1

**Frozen before prototype implementation, correctness replay, or benchmark timing.** Offline experiment; no model calls; no product, RC, README, claim-registry, or frozen-evidence edits. This document is immutable after its SHA-256 is recorded in `PREREGISTERED_SPEC.sha256`. An implementation defect found after frozen execution requires a new versioned spec with the defect and changed code identity documented before rerun; v1 results remain archived.

## Identity and environment

- Repository HEAD: `254a5c14fa74fc3534493c565de84b38e7317175`; committed tree: `dc7ae5512e4d47e56663564ad72b7a18600bbf5c`. This workspace has pre-existing uncommitted/untracked material; the exact source inputs below are pinned by SHA-256, aggregate digest `0520c95a2ab1af08f11bd19941edf3e43fadc3f05859fd754ab0ad432c12a61b`. Prototype code does not yet exist; its SHA-256 will be recorded separately before the first frozen run.
- Python: `3.13.12 | packaged by Anaconda, Inc. | (main, Feb 24 2026, 16:13:31) [GCC 14.3.0]`; executable `/home/kerem/miniconda3/bin/python`. openpyxl `3.1.5`, lxml `6.1.3`, SQLite `3.51.1`. OS `Linux-7.0.0-31-generic-x86_64-with-glibc2.43`; CPU `Intel Core Ultra 5 125H`, x86_64, 18 logical CPUs; one benchmark worker, no deliberate CPU affinity or cache flush.
- Source input SHA-256: {"benchmark/run_candidate_a_a1_checkpoint.py": "8d3ae850dda789d4ffc228b4054fdec8d55fec3cd000b600f2c6a9db8ec33669", "candidate_a_a1_checkpoint_rerun_01/contact_traces.jsonl": "665244f6150dfbb74ae647dfc8a7b8b034c02794f6de9cf7419f6d56da41696f", "rc_acceleration_validation/eligible_population.json": "b6be87f570bfd33c499038526a45b8624d7752531a79dda29a55bd9cddbcf1a8", "rc_acceleration_validation/workload_manifest.json": "4d2f9ea32dce55c12f3f7e44696177979c781f32e565f0dd5c5c857e847fb3d9", "representative_architecture_checkpoint/population.json": "3ad50de3f18f22f5bf2b174fb680c52c5401e45556b514b65009e0a74c8217ef", "src/librecalc_agent/_frozen/index.py": "2b95da432222706f208c35f6277032ebffb0cf832efb3f1b0f329545679ad854", "src/librecalc_agent/_frozen/reads.py": "7aa7c155ce81932e86408a2fb3affaee82c41c99dcc252683b912fdb7d8c584c", "src/librecalc_agent/_frozen/runtime.py": "84fdb05f3a2eac5deb84fcda3c58bd93274874c4d514965e6abcd1f47ae857ed", "src/librecalc_agent/_frozen/substrate.py": "60bf7805e255a4c47125f7c5c8d35779d0f008bda37716370e3934683dcbdf14"}.
- Population JSON SHA-256: `6492d1cbc2163ea252c0d34cf346171d332a923bd5f05fc1fd54c3e851097afa`. Freeze `population.json` bytes exactly; rows below mirror it. Every workbook and snapshot hash is rechecked before execution.

## Populations (frozen before treatment)

- Construction: 39 unique workbook SHA-256 values, union of the 14 unique RC eligible workbook hashes and 30 representative task workbooks, deduplicated strictly by full-file hash. All 39 stay in denominators. `xml_nonempty_cell_count` is a package-level census of `<c>` elements with `<v>`, `<f>`, or `<is>`, computed without building a treatment representation; it is not an openpyxl semantic cell count.
- Trace: all 51 archived exact Candidate-A contact traces, in archived order, with seven unique snapshot hashes. No ranking or contact threshold is applied. A trace starts with one workbook acquisition; subsequent archived `load_workbook` markers are skipped, matching the historical replay. Only recorded operations in the frozen contract are executed.
- Per-workbook data: full hash, provenance, byte size, worksheet count, XML nonempty count.

| Workbook SHA-256 | Bytes | Sheets | XML nonempty cells | Provenance |
|---|---:|---:|---:|---|
| `04fd2d7d1a21b8aa74ff151cdad8c2e0f9c6904b56e7528454b94d675e1ee3fb` | 103312 | 13 | 1609 | representative_checkpoint:Debugging:03_06 |
| `0d51c60e2cbef7e4b675815f9873fe69c01cac1e06cd69bf8a5751c1f64ee956` | 8320856 | 99 | 133373 | representative_checkpoint:Debugging:10_07 |
| `1768dcc784d3c9bd2319dabeaa3a7c27d4bc0ab048a63c7084450abab3f3a1a2` | 6727 | 1 | 42 | representative_checkpoint:Template:02_01 |
| `1b64bd5ac59b13beceb019da28ee25a8e12d479e14d625ce3ead88ccc344c741` | 66611 | 9 | 1963 | rc_eligible:Financial_Model:02_04, representative_checkpoint:Financial_Model:02_04 |
| `2102c51421d746b2a090e83b46e37c927b6a839d82d3df75b39f8c5d058b2105` | 593808 | 18 | 18223 | rc_eligible:Financial_Model:11_02, representative_checkpoint:Financial_Model:11_02 |
| `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 2600708 | 8 | 121558 | representative_checkpoint:Financial_Model:10_01 |
| `2a690378dc1e0d2330661457c9c95a26a65efbba08624a9c59548e64ab202c44` | 1347154 | 18 | 5879 | representative_checkpoint:Debugging:06_05 |
| `2a7aa7cbeda9ebbd90c52b28090030140e30a5d019af05da4844b21396c673e8` | 66494 | 9 | 1947 | rc_eligible:Financial_Model:02_01 |
| `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 2173244 | 13 | 137318 | rc_eligible:Financial_Model:08_03 |
| `318eed515474a4e8c0684d3895e49e4726728d1166c2f83ef71b936d32dbf3d7` | 297984 | 9 | 12774 | rc_eligible:Financial_Model:15_03, representative_checkpoint:Financial_Model:15_03 |
| `3463b88f927d0153e58141167f35da823656ec9249c1c8dc1c3205f75a5af802` | 281911 | 13 | 8658 | rc_eligible:Debugging:08_04 |
| `3dc2f7d65a9f792a86cb3f0183a029e0ceb206ed138a5c1c67d40d9c2428de7b` | 7552 | 1 | 75 | rc_eligible:Template:03_03 |
| `45dcae55a68ffcdbf86156fe4c692fa255fc943f5cd8b3d6bdb8627086efd265` | 6437 | 1 | 82 | representative_checkpoint:Template:06_23 |
| `56adf80d06ec4014d5189805adcafdfe38508c58a5391d7d40147621773aac9e` | 88645 | 14 | 3166 | rc_eligible:Financial_Model:18_05, representative_checkpoint:Financial_Model:18_05 |
| `56e031f5fa3e13c65bf5e85e6bf92c7852a910eac3c4538053f57bbcae6fdd8d` | 1059926 | 18 | 5879 | representative_checkpoint:Debugging:06_10 |
| `5b57294aba2fca619f95dcd411118728e62ecf546e0e261f2111bf2fa82477aa` | 7335 | 1 | 95 | representative_checkpoint:Template:01_06 |
| `5f7440ee995da046723e17d03de8d4cfd0d96e055d0834fa2dfafe7d0affcc28` | 7434 | 1 | 80 | representative_checkpoint:Template:01_05 |
| `623d33a48cd5417b98e9feeb6f5a6d2f794bb3b7f45209f44de58bc6898d2e5f` | 282123 | 13 | 8657 | representative_checkpoint:Debugging:08_01 |
| `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 2164521 | 13 | 136813 | rc_eligible:Financial_Model:08_01 |
| `6fe31393f4e12241ffd547f79a8fe62a718e12f9d9f8f9f2074c411a5a55e134` | 7021 | 1 | 55 | representative_checkpoint:Template:04_04 |
| `71233a0b02e0680361836392ca41c567aae657ce91dd24c4248f273f459fd53c` | 1924873 | 14 | 27865 | representative_checkpoint:Financial_Model:06_01 |
| `76ff3caea33395983113db652c35d5a14b46e7be8588f06f26092990fef1cc19` | 6303 | 1 | 85 | representative_checkpoint:Template:06_02 |
| `7d63102f21e2cdb0c8ef7ba630004c3e789540a4b8444c02f3c782d8ff426ea9` | 7745 | 1 | 80 | representative_checkpoint:Template:07_02 |
| `80a0621898fef8ffc7df0a83d157bf447e24756de5993fa622a0e049ff536b49` | 2580566 | 7 | 122053 | representative_checkpoint:Financial_Model:09_03 |
| `84d2660500cc576f53a65b7fad6073103011376cb205e71519657ffe528b96cb` | 58348 | 3 | 1895 | representative_checkpoint:Debugging:09_04 |
| `9928600b0184036b03a8664c1e2dcd8994e5f90e866d68c140dd6543b3ac0aff` | 2147654 | 13 | 137227 | representative_checkpoint:Financial_Model:08_02 |
| `9af630a02079a57a7542217de50822bd1c5b92e1e08416128be3dc600ad0aeeb` | 57771 | 14 | 3586 | rc_eligible:Debugging:01_06 |
| `a6aad8ddac8bf96574fec50f577cfe1038ae9a566a97ed26aef0019d07e8b7f0` | 2577759 | 7 | 122033 | representative_checkpoint:Financial_Model:09_02 |
| `acb75164e5ce88cb741ef59d87637707c33ce88b3978ed85076d1517ef3e407c` | 415159 | 9 | 2523 | representative_checkpoint:Debugging:07_05 |
| `d01f1c1025176da9cfbabe38cfca0776fd77e7287f6138e6fe85ab06394d457a` | 85553 | 14 | 3585 | representative_checkpoint:Debugging:01_04 |
| `d05d2bcd62e971dab1907e3b290cc7e46c161f5d1d3bfac6266d04bd831ddeba` | 7558 | 1 | 95 | rc_eligible:Template:06_12 |
| `d148f7eefd3b1578aaf1b39dc3f34dbf2628719a68e9f956d7b3ca49c245c886` | 676567 | 13 | 3264 | representative_checkpoint:Debugging:04_07 |
| `d3a7de73ce86d28dccf1879795495172a906f0268188217b3e7d99f16da47d1c` | 9480 | 2 | 141 | rc_eligible:Template:16_07, representative_checkpoint:Template:16_07 |
| `df35d4aa5498819bd8cc9792ad7ae3f5a9d04a21cf9120db889073a3049c785d` | 6984 | 1 | 53 | representative_checkpoint:Template:06_08 |
| `e624bbe0a36c50d190ff7ecddf892580f2289b689309b26a463a684e2c3afdeb` | 7920 | 2 | 166 | representative_checkpoint:Template:16_08 |
| `e918281d3d7072ceb87fce285e49e77fa8843a260fc827f9c554dc0b47a6b185` | 590007 | 8 | 20766 | rc_eligible:Financial_Model:07_01 |
| `f1ca163a1198e742864c9814016b49f397a0f1d0469685a5d7efd618aec7ca5a` | 59783 | 3 | 1873 | representative_checkpoint:Debugging:09_03 |
| `f61402df84ff17d94590f86939a408f786cb4fdeba82eb3e1911d8ebb839febd` | 66570 | 9 | 1960 | representative_checkpoint:Financial_Model:02_05 |
| `fa7c8d05a020ef079d6330fe7d1e3de64b35be0e9cc99d413c1bc30e7e19565e` | 412320 | 10 | 2649 | rc_eligible:Debugging:05_02 |

| Trace ID | Snapshot SHA-256 | Recorded operations |
|---|---|---:|
| `primary_03_Financial_Model_08_03_H1:3` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 1006 |
| `primary_03_Financial_Model_08_03_H1:4` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 5705 |
| `primary_03_Financial_Model_08_03_H1:5` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 463 |
| `primary_03_Financial_Model_08_03_H1:10` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 463 |
| `primary_03_Financial_Model_08_03_H1:11` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 299 |
| `primary_03_Financial_Model_08_03_H1:12` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 172 |
| `primary_03_Financial_Model_08_03_H1:18` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 31 |
| `primary_03_Financial_Model_08_03_H1:21` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 87 |
| `primary_03_Financial_Model_08_03_H1:23` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 4 |
| `primary_03_Financial_Model_08_03_H1:25` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 61 |
| `primary_03_Financial_Model_08_03_H1:26` | `2b7a84044765a4664ddb197de168fbd7feb8fff395a027a4923ee2d9ab9e8dc1` | 41 |
| `primary_06_Financial_Model_08_01_H1:4` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 239 |
| `primary_06_Financial_Model_08_01_H1:5` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 286 |
| `primary_06_Financial_Model_08_01_H1:6` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 531 |
| `primary_06_Financial_Model_08_01_H1:8` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 499 |
| `primary_06_Financial_Model_08_01_H1:10` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 355 |
| `primary_06_Financial_Model_08_01_H1:11` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 7477 |
| `primary_06_Financial_Model_08_01_H1:12` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 5221 |
| `primary_06_Financial_Model_08_01_H1:13` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 115 |
| `primary_06_Financial_Model_08_01_H1:14` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 16444 |
| `primary_06_Financial_Model_08_01_H1:15` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 163 |
| `primary_06_Financial_Model_08_01_H1:16` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 1097 |
| `primary_06_Financial_Model_08_01_H1:17` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 3248 |
| `primary_06_Financial_Model_08_01_H1:18` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 2745 |
| `primary_06_Financial_Model_08_01_H1:19` | `6d742f67e84fcc3d92d1dec6b285417093b99dec1469686f1c6813aee9ad2a0a` | 4689 |
| `primary_08_Financial_Model_15_04_H1:3` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 6025 |
| `primary_08_Financial_Model_15_04_H1:4` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 4727 |
| `primary_08_Financial_Model_15_04_H1:5` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 2076 |
| `primary_08_Financial_Model_15_04_H1:6` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 559 |
| `primary_08_Financial_Model_15_04_H1:7` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 357 |
| `primary_08_Financial_Model_15_04_H1:8` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 3195 |
| `primary_08_Financial_Model_15_04_H1:9` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 4152 |
| `primary_08_Financial_Model_15_04_H1:10` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 147 |
| `primary_08_Financial_Model_15_04_H1:11` | `9ff136a8008051fc400bcade977f9732fef6f3b9c3116ebc46ee366d24406f53` | 443 |
| `primary_10_Debugging_10_10_H1:15` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 31 |
| `primary_10_Debugging_10_10_H1:17` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 23 |
| `primary_10_Debugging_10_10_H1:18` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 15 |
| `primary_10_Debugging_10_10_H1:19` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 39 |
| `primary_10_Debugging_10_10_H1:21` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 35 |
| `primary_10_Debugging_10_10_H1:22` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 29 |
| `primary_10_Debugging_10_10_H1:23` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 15 |
| `primary_10_Debugging_10_10_H1:29` | `3d95978b76409416f96be4645daeb2e28f949c171cc159560627506ef1c7eb34` | 33 |
| `primary_17_Debugging_05_02_H1:17` | `fa7c8d05a020ef079d6330fe7d1e3de64b35be0e9cc99d413c1bc30e7e19565e` | 801 |
| `primary_17_Debugging_05_02_H1:21` | `fa7c8d05a020ef079d6330fe7d1e3de64b35be0e9cc99d413c1bc30e7e19565e` | 2425 |
| `primary_19_Template_13_08_H1:8` | `591b6250a393b2606573631b5a9e66f415d68704d2d95756cd1cb8bca7327343` | 123 |
| `primary_24_Financial_Model_10_01_H1:5` | `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 1123 |
| `primary_24_Financial_Model_10_01_H1:6` | `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 199 |
| `primary_24_Financial_Model_10_01_H1:7` | `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 52944 |
| `primary_24_Financial_Model_10_01_H1:8` | `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 423 |
| `primary_24_Financial_Model_10_01_H1:9` | `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 4246 |
| `primary_24_Financial_Model_10_01_H1:10` | `26f8817083ad13636971bc7fa18d75fd4a3d10111d8872fa1ab98e7cbd1aa8a7` | 363 |

## Frozen semantic contract and comparison

R0 oracle is normal `openpyxl.load_workbook(path, data_only=False)` under the pinned library version. Contract: ordered `Workbook.sheetnames`; literal named `Workbook.__getitem__`; `Worksheet.max_row`, `.max_column`, `.calculate_dimension()`/`.dimensions` observable bounds; literal single coordinate lookup and integer `.cell(row,column)`; `Cell.value` and `.data_type`. No writes, styles, fonts, rich object identity, arbitrary ranges or workbook iteration. Trace handle objects compare by handle category, not Python class, as in archived replay. Scalar comparison preserves Python type and value, including `None`, `bool`, `int`, `float`, `str`, `date`, `datetime`, `time` and errors; NaN is compared as typed NaN if encountered. Formula-mode values include exact reference formula string; array/shared formula objects are compared by concrete type name and their observable text/attributes, never silently coerced to strings. Exceptions compare class and message at operation boundary.

Dimensions are compared to normal openpyxl's materialized worksheet bounds, including metadata-only/merged/empty cases. Full-cell differential compares all reference non-empty cells in every corpus workbook for `.value`, `.data_type`, and formula observable text, plus sheet order and bounds. XML-address cells absent from reference semantics are recorded separately. If a workbook has >250,000 package nonempty cells (none of the frozen 39 do), use a deterministic fallback comprising first 100 and last 100 non-empty coordinates per sheet plus coordinates whose SHA-256 of `workbook_hash|sheet|coordinate` begins with hex `00`; record counts and reason. A reference load failure/MemoryError is recorded as an unresolved full-cell gate, not silently sampled. Mismatch taxonomy: shared string, inline string, number, boolean, date/time, error, normal formula, array/shared formula, merged cell, bounds/dimension, other. No variant with any mismatch is eligible for a speed claim.

## Variants (fixed)

- **R0:** normal openpyxl full load, no persistent derived state.
- **R1:** frozen current `index`/`substrate` schema and proxy read mechanics, using a one-workbook isolated workdir and actual prepare/SQLite backup/manifest. Parent builder uses openpyxl read-only parse. No schema changes.
- **R2:** direct ZIP/OOXML decoder into only the specified Python in-memory read state. No `openpyxl.load_workbook` in construction or serving.
- **R3:** the same R2 decoder into a minimal persistent SQLite representation, only contract fields/indexes, with atomic publication and read-only attach. No openpyxl workbook parse in construction or serving.

Direct variants may use openpyxl utility constants or date/number-format helper functions, but any call to `openpyxl.load_workbook` (including `openpyxl.reader.excel.load_workbook`) is forbidden under a sentinel around treatment build and serving. Sentinel violations fail independence. Oracle generation occurs outside treatment timers/sentinel. R2/R3 decoder semantics are shared; differences are storage and lookup only. No exotic format, adaptive mode, anchor/temporal/search/dependency state or product integration.

## Correctness before speed

Run 51 exact trace replays through R0/R1/R2/R3, then full-cell R2/R3 differential on all 39 books, then sentinel independence checks. Preserve per-trace/per-workbook/cell raw rows. If R2/R3 fail exact trace on a feature requiring substantial semantic reimplementation, stop and report; do not drop traces or repair by exclusion. One bounded implementation phase precedes the frozen gate; synthetic local tests may be used before frozen execution. Any post-gate defect correction requires v2 spec and a fresh result set, not overwriting v1.

## Timing endpoints and protocol

Timing starts only after correctness gate; mismatch variants may receive diagnostic timing clearly marked ineligible, unless stop rule 1 fires. Use `time.perf_counter_ns`, one worker, `PYTHONDONTWRITEBYTECODE=1`, fixed source bytes and a fresh isolated temp directory for generated DBs. No OS cache flush: label the first observation **cold-ish first observation**, not cold disk. For each workbook and R0–R3, record one first observation and two subsequent repetitions. For the repeated pass, shuffle variants independently per workbook with `random.Random(20260925 + workbook rank)`; first-observation variant order rotates by workbook rank. Close and discard state and reset R1 between construction repetitions. File staging/hardlink and import setup occur outside timer; construction timer starts just before builder call and stops when state is ready for reads, including required hashing, decode, DB population and publication. R0 ends after normal load completes. Record R1 manifest `ensure_s`/`backup_s` as nested components; do not fabricate uninstrumented parse/traversal times.

INDEX_READY on all 51 traces: prepare R1/R2/R3 once per trace outside timer; R0 has no prepared representation. Two timed repetitions per variant per trace, order independently shuffled by `random.Random(20260925 + trace rank + 10000 * repetition)`. Start before backend acquisition/open/attach, stop after trace operations and close/release. Record acquisition and operation intervals separately where practical. Construction excluded. R0 parses normally inside read timer. The per-trace paired median is the unit.

FIRST_USE: construct + execute one trace for R1/R2/R3, and R0 normal acquisition/read once, with constituent timers retained; label mechanism-level, not product speed. Reuse horizons `N=1,2,3,5,10`: for each trace and variant, construct once, execute the **same trace N times**, acquiring a fresh backend view each time, with independent R0 normal loads; record observed sum through each prefix N. Use seed-rotated variant order by trace rank. Report first observed break-even among those N; do not extrapolate. These endpoints exclude public CLI/child/capture/diagnostics.

Persist raw construction/read/reuse timing rows, artifact bytes/source bytes ratios, R2 in-memory footprint (recursive estimator with shared-object deduplication, explicitly approximate), R3/R1 read-only cross-process attach feasibility (one child process probe per artifact, untimed), and stage profiles. R2/R3 profiles where feasible: ZIP open/list; workbook/relationships; shared strings; styles/date metadata; worksheet XML; value decode; structure insertion; SQLite insertion/index creation; publication. R1 categories: hash, read-only Parse A, traversal/materialization, SQLite, publication; label uninstrumented components `UNMEASURED`.

## Analysis and stopping

Report construction, INDEX_READY, FIRST_USE, and repeated-use separately. Use per-workbook/per-trace paired ratios; median, geometric mean, min/max/range, faster/slower/tie (exact equality), and bootstrap 95% percentile CI for geometric ratio with 2,000 resamples, seed 20260925, where identities and sample count permit. No unpaired difference of medians as causal savings. Raw rows remain authoritative. Do not auto-select fastest variant or alter populations. A material construction difference for stop rule 2 means at least 10% paired median R2 or R3 reduction versus R1; if neither reaches that and profiles do not show representation/storage as a bottleneck, stop without adding formats. Stop earlier if exact trace requires substantial semantic reimplementation or identity/timing reliability fails. Record stopped endpoints as `NOT_RUN`, not zero.

## v2 amendment before first result row

The first attempted frozen correctness invocation failed before recording any result because `os.link` could not cross from the archived snapshot filesystem to `/tmp` (`Errno 18`). This was an implementation/staging defect, not a population, semantic, or timing observation. The active v2 protocol replaces hardlink staging with a byte-for-byte copy outside every timer, verifies the copied SHA-256, and keeps the same 39 workbooks, 51 traces, variants, semantic contract, repetitions, randomization, and gates. V1 remains preserved under its original filename and hash. The active specification hash is recorded in `PREREGISTERED_SPEC_v2.sha256`; later run metadata must name v2 explicitly.
