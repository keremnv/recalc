# Phase 10 preregistered integration validation

This specification freezes the first scored product integration validation. Written after implementation and unscored smoke/fixture checks, before any scored PY/EXP/PROD population execution. It must not be edited after its SHA-256 is recorded. A defect requiring a protocol/code change requires a numbered amendment and a fresh run of affected rows.

## Source and runtime identity

- Repository HEAD: `254a5c14fa74fc3534493c565de84b38e7317175`. The worktree contains pre-existing and Phase-10 uncommitted files; `product_integration_phase10/implementation_identity.json` freezes maintained Python/C modules, the validator, experimental bootstrap/observer and population manifests by SHA-256. Manifest SHA-256: `ae5c9547b88c4fd697fa587cabf20f62796994c96fe4187b795f9c0d7ec47989`.
- Installed product wheel SHA-256: `680e6f60f2ac9772c8dc059303db28a7b8a722cc3fdd872bd4ae9df425f8d408` at `/tmp/librecalc-phase10-dist/librecalc_agent-0.2.0rc1-py3-none-linux_x86_64.whl`.
- PY/EXP/PROD use `/tmp/librecalc-phase10-clean/bin/python`, CPython 3.13.12, openpyxl 3.1.5, lxml 6.1.3. PROD invokes the clean-wheel installed `/tmp/librecalc-phase10-clean/bin/librecalc-agent` native command. EXP invokes the frozen Phase-6 observer with the frozen Phase-9 overlay using this same Python environment. Linux x86_64, kernel 7.0.0-34-generic, glibc 2.43. OS filesystem cache is uncontrolled; arm order is balanced deterministically.
- No model calls. Source scripts are byte-identical; no source rewrite. Staging is outside each command timer.

## Frozen populations

1. Fixed 22: `read_engine_phase3/population.json` `primary_ids` in original order, exact script/source/staged workbook hashes. This is a direct-read regression population, not the representative primary view.
2. Representative 30: the same manifest's `secondary_ids`, checked equal to `rc_acceleration_validation/representative_population.json`, exact hashes. This is the primary product-boundary population. Historical route split is 22 reference-only, seven direct contact, one fallback after contact; PROD routing is determined from source/runtime, never workload ID.
3. Changed five: the five frozen `read_engine_phase8/changed_file_fixtures/{existing_cell,formula,multi_cell,new_sheet,output_file}.py` with the frozen Template source workbook in the Phase-8A validation runner. These test assurance, not write acceleration.
4. Process/assurance fixtures: maintained tests for normal return, nonzero SystemExit, uncaught exception, atexit workbook write, subprocess/FD, changed-workbook `os._exit`, changed-workbook SIGTERM; additional bounded failure/cache/version/concurrency tests are separate diagnostic gates.

## Arms and timing

- PY: a fresh clean-venv Python process executes staged `workload.py` directly.
- EXP: frozen Phase-9 overlay under the Phase-6 native observer; same real script process and external full-command boundary.
- PROD: installed native dispatcher, maintained observer and maintained runtime.
- External elapsed time starts immediately before launching an arm command and ends after command exit, including observer, bootstrap, artifact/capture work, target, diagnostics and teardown. Workdir reset and file/package hashing are outside the timer.
- Each arm has an independent cache. Every cold pair starts with no artifact. Second invocation retains that arm's cache but restages exact source/script bytes; it is called `VALID_REUSE` only with actual direct contact and `REUSED` witness, otherwise `SECOND_INVOCATION`.
- Fixed 22 and representative 30: two scored repetitions of cold then second invocation per workload/arm. Changed five: one scored full command per fixture/arm. Representative sessions: one observed sequence each at N=1,2,3,5 per workload/arm, with a fresh cache at each horizon; all invocations are timed and summed. No extrapolation.
- Order of the three arms for each workload/phase/repetition/invocation is `random.Random(20260928 XOR first-12-hex-of-SHA256(key)).shuffle([PY,EXP,PROD])`, as implemented in the pinned validator. Session arms alternate at each invocation under the same deterministic order. Timeout is 180 seconds per command.

## Correctness gate and stop rule

For each paired row, compare exit, stdout/stderr under the frozen Phase-3 comparator normalization, output files and XLSX package state. Changed-file state uses the frozen Phase-8A package comparator, which permits only its documented volatile core-property timestamp difference. Require EXP/PROD route class agreement, artifact `BUILT` on cold direct contact and `REUSED` on second/subsequent direct contact, fallback reason agreement, PROD assurance `PASS`, EXP helper success, and changed-file capture/validation success. A new genuine difference, wrong route/reuse, missing assurance or timeout stops scored interpretation immediately. Rows already collected remain diagnostic, not speed evidence. No workload is excluded after timing.

The separate process/assurance, clean-install, corruption, source mutation, version-key invalidation and concurrent publication checks must pass before a validated product verdict. A failure is recorded, not patched inside the same scored run.

## Analysis and decision rules

Preserve raw per-invocation rows and complete session sums. Per workload, take the median of paired repetition ratios for cold and second invocation. Report paired median ratio, geometric mean, min/max, faster/slower/tied counts, median signed milliseconds and a seeded 5,000-resample workload bootstrap interval for the median. Keep task-cluster caveat and route-specific distributions; do not interpret an unpaired difference of medians as a saving.

The preregistered practical reference-only budget is median signed PROD minus PY second-invocation excess at most **+10 ms** across the frozen 22 representative reference-only workloads, matching the Phase-9 integration target. Also report PROD/EXP and its distribution; no claim of zero overhead follows from meeting the budget. Direct-contact integration requires exactness, valid reuse and no systematic regression versus EXP; interpret median PROD/EXP above 1.10 as a material migration regression, without suppressing raw heterogeneity. Cold speed is descriptive, not an integration requirement. Changed-file speed versus PY is descriptive assurance cost. A validated verdict requires all semantic/assurance/install/concurrency/failure gates, not merely favorable timing.

No population adaptation, read-engine optimization, helper optimization, benchmark-specific routing or public claim changes are authorized during this run.
