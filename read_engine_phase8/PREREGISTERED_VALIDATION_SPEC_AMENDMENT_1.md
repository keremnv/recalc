# Phase 8 validation specification — Amendment 1

Status: **preregistered after semantic hardening, before any Phase-8 representative or changed-file scored timing**. The original stopped Phase-8 report and base spec remain unchanged. This amendment changes only the experimental merged-cell proof implementation and provides its gates; it does not change population, read contract, artifact, observer, fallback, capture or timing accounting.

- Base Phase-8 spec SHA-256: `20a149e390f102d26ef259082b34948d0d9eb5b4f2029e6ae5bbf268f2c1cd11`.
- Representative population: exact same 30 ordered IDs/21 tasks and script/workbook hashes from the base spec and frozen RC manifest; no replacement, re-ranking or changed eligibility.
- Changed-file population: exact same five fixtures (`existing_cell`, `formula`, `multi_cell`, `new_sheet`, `output_file`) and the same `Template_15_03` source workbook from the base spec.
- H0: unchanged Phase-6 H2 architecture. H1: Phase-6 H2 observer plus Phase-8A overlay bootstrap and hardened certificate; same Phase-7 merge runtime, direct decoder, JSONZ_MEMORY_V1 artifact, SHA freshness and reference fallback. PY unchanged.
- Endpoint, repetitions, balanced order, N=1/2/3/5 sessions, reference-only descriptive standard and bootstrap seed remain exactly the base spec.

## Repair and trust boundary

Phase 7 scanned syntactic `.cell` nodes and treated zero recognized nodes as safe. That did not prove dispatch reachability. Phase 8A validates the entire module against a closed grammar: direct load, literal sheet binding, direct terminal `.cell` consumption, bounded scalar loops/comprehensions/conditionals, and a few scalar builtins/list append operations. Any unknown attribute/call/subscript, indirect method acquisition, alias, function, dynamic execution, rebinding or unrecognized AST statement/expression returns `NOT_CERTIFIED`. Zero cell calls returns `NOT_CERTIFIED`. An admitted but uncertified script takes the unchanged covered-merged-child reference route. The three original target scripts are positively certified; no script-specific identity checks exist.

No source rewriting, new API, proxy implementation change or reference-fallback change is included. The prior `cell.parent is ws` proxy/reference identity mismatch remains a known semantic limit and is not counted as a successful direct observation.

## Completed unscored semantic gates

- Original Phase-7 37 fixtures plus 32 additional adversarial/zero-call fixtures: **69/69 passed**, with 13 certified direct fixtures, 54 exact reference/no-merged-contact fixtures, and two known parent-identity-limit fixtures that remained H0/H1-equal with zero direct merged serving. No false-positive direct route.
- Deterministic terminal-expression mutation matrix: **15/15 passed**.
- Exact frozen primary 22 scripts: **44/44** cold/reused H1-vs-PY correctness rows exact; artifact `BUILT → REUSED` retained; zero new direct routes; fallback reasons unchanged; the three original merged targets retained direct counts 6, 8 and 38. These are unscored correctness runs, not a Phase-7 speed rerun.
- Gate artifacts: `read_engine_phase8a/certificate_matrix.jsonl`, `read_engine_phase8a/certificate_review/mutations.jsonl`, `read_engine_phase8a/fixed22_correctness.jsonl`.

## Implementation identity

The pinned implementation manifest `read_engine_phase8a/implementation_identity.json` has SHA-256 `90d6a398938d0efa093b33a20bb1d738331f45286c3fe438eb6ae9acf325fd36` and pins 21 code/fixture/authority files. Relevant treatment hashes:

| File | SHA-256 |
|---|---|
| `read_engine_phase8a/certificate.py` | `b0505f938568e7ab1ee4c26085d6f56b551ec8c46fb3a75b47ec1ca0ba911ba1` |
| `read_engine_phase8a/overlay/read_engine_phase6/bootstrap/sitecustomize.py` | `9d0dab30e5123c9b45d1c7953067a4ee6dd925dc57a11d9c27c660ce8551178e` |
| `read_engine_phase8a/validation_runner.py` | `de37d98f936a4fce505fbc1bf7c1c75ad1dd43a495242569e20697b53efcc274` |
| `read_engine_phase7/merge_runtime.py` | `ab8ae2222238eebb468add237986943a43524ecf4a7c9101ee5776857aa97b56` |
| `read_engine_phase6/observer.c` | `46732be5b2c53f2fc73ee542a71afcab4e64c8878249189157bf0b07217d5664` |
| `read_engine_phase3/safe_artifact.py` | `9cf0b12ba9f47a5b2af045c5d68457638ebc301e54db1113a58b5eba3ee64848` |

Changed-file fixture hashes remain identical to the base spec:
- `existing_cell` `6de4258a0ec586642ce5b49af71c9aadb7a5e6f56f1f7bdb55f821b9e4fb50ad`
- `formula` `b30d43f3d4fb47bd69c7ebe2ce4765f25426da312a5db72ae8ab37548ee925f4`
- `multi_cell` `909c7f1a2a8e1f776e7176b2cd40a0d9d0a22306f65daca9bf92d030edcca1d4`
- `new_sheet` `e83ba283a3821b68afbfa632f7e22c6dc47816ae12b7427349945c513ad56f5b`
- `output_file` `01c558c4788f4664fd420552aba6bb93ef304f0adffd5045e53daa43b2a8b48e`

Abrupt-exit diagnostic scripts are now versioned before execution:
- `exit_after_save` `c6b7507d38d96aaffab2f38c60799d94c84f30eb3a579cb1eb399baf910724d8`
- `signal_after_save` `d138e79b9818a1061352e32b970efaa6260b3706a276a1d1bed52fcf4b3c4865`

## Correctness and scored protocol clarification

Before scoring, run an unscored cold and second-command PY/H0/H1 gate on all 30; then all five changed-file correctness gates, then the two abrupt-exit changed-file diagnostics. Any genuine semantic mismatch, stale/false reuse, missing observer receipt, failed package validation/replay or unintended effect path stops scoring. H1/H0 may differ in merged direct versus reference route only where the hardened certificate deliberately becomes more conservative; output state must remain exact or address-volatile only under the base comparator.

Changed-file fixture output comparison requires exact XLSX package-part name/hash mapping plus exact non-XLSX file hashes and stdout/stderr/exit parity. Whole ZIP container hashes are recorded separately; container metadata differences alone are not treated as different workbook/package state. Each observer must record exactly one expected changed XLSX path, a successful helper, `validation_passed=true`, `f1_part_exact=true`, `f2_state_exact=true`, and `runtime_failure=false`. This makes the already-frozen package-state rule explicit before write timing; it is not a workload exclusion.

If all gates pass, run exactly 3 scored repetitions × 5 invocations × PY/H0/H1 on all 30, with one unscored warmup per arm/workload and the base spec seed/rotation. Run 3 scored repetitions × PY/H0/H1 on each fixed changed-file fixture. Any scored semantic mismatch stops interpretation; no patch-and-continue. All command walls include the same complete external boundary. Direct-contact, reference-only and fallback subviews remain diagnostic under ALL 30.

## Amendment rule

A runner or semantic defect discovered after this amendment requires a separately named/hashes amendment and a fresh affected gate before any scored rerun. The original Phase-8 stop and Phase-7 evidence must not be overwritten.
