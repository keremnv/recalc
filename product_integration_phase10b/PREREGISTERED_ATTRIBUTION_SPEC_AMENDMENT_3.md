# Phase 10B preregistered attribution amendment 3: one bounded P5 treatment

Written and hashed after normalized P0–P4/S0–S3 attribution and P5 implementation review, before P5 process fixtures, P5 scored timing, or P5 regression controls. The original spec and amendments 1–2 remain unchanged. No Phase-10 evidence was altered.

## Causal eligibility and exact change

- Normalized P4−P0 median reference-only excess was +15.39 ms, above the unchanged +10 ms budget. P3−P2 (full negative bootstrap/config/classifier/setup) was +9.04 ms with bootstrap signed interval [5.48, 22.51] ms. P1−P0 current observer envelope was +4.16 ms. Fine subarm increments were noisy and do not establish a precise import-saving claim.
- The frozen classifier unconditionally treats each non-range A0 lexical match as a blocker. Twenty of the exact 22 reference-only scripts contain one; none of the frozen seven direct-contact or one fallback-after-contact scripts does. The P5 proof and coverage files are pinned below.
- P5 changes only the maintained negative-admission bootstrap path: on default configuration, after script identity guard and source read, a literal subset of the **existing** definitive A0 lexical blockers immediately writes the same reference route/setup and skips config/classifier imports. Unknown/nonmatching scripts and explicit/effective config use the old full bootstrap. No direct engine, cache, observer, capture, fallback or public configuration change. A `negative_proof` setup witness is diagnostic.
- This is a single treatment targeting redundant full classification on a positively proven reference subset. The treatment is allowed to fail. No second optimization may be stacked.

## Pinned identities

| File or binary | SHA-256 |
|---|---|
| `product_integration_phase10b/P5_TREATMENT_DECISION.md` | `9d106a905cd11698a23cde6dee7ac768be800d8d0ca91be0ad527d2d8e14f0de` |
| `product_integration_phase10b/p5_coverage.json` | `ab370b084cf7e0f4fb7914bcef63d0a3e83c571518c76dc3dcd6022e8b734c76` |
| `product_integration_phase10b/p5_proof.json` | `63d16921f79c2444d802574862151dcd0be830b999a23a070ba37839fb049091` |
| `product_integration_phase10b/p5_fixtures.py` | `d968972568095c7c565016994b2e682098d3b27a95246e3939d7b5f8ce8c6d24` |
| `product_integration_phase10b/run_p5.py` | `48a94aced6d9911457d5575b9159e67a4be9ce60d2d76f77bf876c29dac902d6` |
| `product_integration_phase10b/p5_regressions.py` | `563f72607370e7cb6948deb5d8b2d760d0e6d4b626aea7b827cb9bb9f01e5ba1` |
| `src/librecalc_agent/_bootstrap/sitecustomize.py` | `92f6dadcd54cf2d8de58f381fedd7d121d9ac1a641d5381a5ec1cca857bbc826` |
| `/tmp/librecalc-phase10b-p5-wheel/librecalc_agent-0.2.0rc1-py3-none-linux_x86_64.whl` | `a461194b41c87b81fea04504f4c1072c1629f5af2e4533ed4495cef0fa51bbd7` |
| `/tmp/librecalc-phase10b-p5-clean/bin/librecalc-agent` | `27d644a6f23218c74c190970c761126675ffcf9124fc2f241588e014e4fd4b3a` |
| `/tmp/librecalc-phase10b-p5-clean/lib/python3.13/site-packages/librecalc_agent/_bootstrap/sitecustomize.py` | `92f6dadcd54cf2d8de58f381fedd7d121d9ac1a641d5381a5ec1cca857bbc826` |
| `/tmp/librecalc-phase10-clean/bin/librecalc-agent` | `27d644a6f23218c74c190970c761126675ffcf9124fc2f241588e014e4fd4b3a` |
| `/tmp/librecalc-phase10-clean/lib/python3.13/site-packages/librecalc_agent/_bootstrap/sitecustomize.py` | `f4a64dcb0706a0670675502fba4663eba7b2519dbd197bdfe744d33ed5ee177b` |

- P4 is the frozen Phase-10 installed wheel in `/tmp/librecalc-phase10-clean`; P5 is a separately clean-installed wheel with the same package version and dependency versions in `/tmp/librecalc-phase10b-p5-clean`. Both use CPython 3.13.12, openpyxl 3.1.5 and lxml 6.1.3. The different installation prefixes are a possible millisecond-scale confound and are explicitly controlled with paired PY_OLD and PY_NEW arms. No cross-venv subtraction is called proof by itself.
- P5 binary/sitecustomize and both reference Python executables are pinned above or in the original spec. The installed P5 bytecode is present before score.

## Gates before timing interpretation

- Run `p5_fixtures.py` on all 13 original process/reference-object fixtures plus changed-workbook SIGTERM and a direct-route control. Compare PY_OLD, PY_NEW, P4 and P5 for exit, stdout, workbook value, stderr except traceback path, observer `PASS`, route, changed-file helper outcome, FD and signal behavior. Any failure stops scoring.
- Run the maintained product/process test suite. Require all tests to pass.
- On every scored row, require P4 and P5 reference route, no artifact, observer `PASS`, exact/volatile-only output comparison to PY_OLD and truthful P5 quick-negative witness for exactly the frozen 20 covered IDs. No timeout or exit mismatch. Stop on first failure; do not remove rows.

## P5 full-command score

- Exact primary population is the original 22 in `population.json`; no identity or order change. Run PY_OLD, PY_NEW, P4 and P5 in balanced deterministic order under the same full external `subprocess.run` command boundary. Each arm gets its own work/cache root. Stage exact input bytes outside timer.
- Two repetitions per workload, each with invocation 1 then invocation 2, fresh arm-specific cache per repetition. Primary endpoint is invocation 2. Timeout 180 seconds. No daemon or background benchmark. Raw rows are append-only and the batch stops on first semantic failure.
- Order seed is `((20260928 XOR 0x10B) XOR 0x55) XOR first12hex(SHA256(workload_id:rep:invocation))`, then shuffle PY_OLD/PY_NEW/P4/P5, exactly as pinned in `run_p5.py`.
- Per workload compute median of two paired-repetition signed milliseconds and ratios. Primary budget is median signed P5−PY_NEW **≤ +10 ms**. P4−PY_OLD is same-run replication. Report P5−P4 raw and environment-adjusted `(P5−P4)−(PY_NEW−PY_OLD)` per workload, bootstrap intervals (5,000 seeded resamples), faster/slower and task sensitivity. Do not infer exact equality of the two venvs.
- If the P5 budget passes and all gates pass, the frozen budget is met. If not, budget remains failed. Do not alter threshold.

## Post-score regression controls

- Run the seven exact frozen direct-contact representative scripts as PY_OLD/P4/P5 with first build and second valid reuse. Require output/route parity, `BUILT` then `REUSED`, no assurance failure, and no systematic P5/P4 migration slowdown above 1.10 median on second invocation. These are negative controls, not a new speed-selection population.
- Run the five frozen changed-file fixtures as PY_OLD/P4/P5. Require the frozen Phase-8 package-parts comparator, stream/exit parity, observer changed-file detection, helper success and validation. Speed is not an endpoint here.
- Abrupt changed-workbook `os._exit` and SIGTERM must pass the P5 fixture suite before score; after infrastructure has not changed further, those fixtures serve as the regression record.
- A new semantic, route, assurance, packaging or benchmark-identity defect stops interpretation. Any repair requires another versioned/hash amendment and affected-row rerun.
