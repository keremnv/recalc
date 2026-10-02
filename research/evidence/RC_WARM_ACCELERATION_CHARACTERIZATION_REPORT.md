# RC warm/index-ready acceleration characterization

**Verdict: `WARM_PRODUCT_STATE_NOT_SUPPORTED_BY_RC`.** The existing public `librecalc-agent 0.2.0rc1 run` command cannot reuse an index from a prior invocation. The preregistered feasibility stop rule therefore fired before scored warm timings. No warm speed ratio or reuse break-even count is estimable for this packaged RC.

## Integrity and method

The [preregistration](../history/rc_warm_acceleration_characterization/preregistered_spec.json) was written and SHA-256 hashed (`72bf038a4a1cf29fc4286c73179a0b088bacf3fd00dc097eebce61c13717b01c`) before the public reuse probe. It froze the previous workload IDs, the four previously established semantic failures, the supported eligible subset rule, the exact public command, and a stop rule: if the second public invocation rebuilds, perform no scored warm timings. The [probe record](../history/rc_warm_acceleration_characterization/feasibility_probe/public_reuse_probe.json) and [reuse adjudication](../history/rc_warm_acceleration_characterization/warm_reuse_validation.json) document the result. An initial reference-check command used a relative path from the workload directory and failed to locate the script; the record preserves that invalid attempt and the corrected successful reference check. It did not enter any timing endpoint.

The source/config identity hash matched `1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee`; the wheel matched `532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e`. The installed CLI reported `0.2.0rc1`, and every `librecalc_agent/` file checked inside the installed package matched the wheel. No product file was changed or rebuilt.

The public command was the installed CLI's `run --workdir <workdir> <workdir>/workload.py`, with shipped defaults. The probe reused the *same* `XDG_CACHE_HOME`, workbook bytes, workload script bytes, and work directory for both product invocations. It used `Template_03_03__c76ea596b408`, already in the frozen representative and semantically supported eligible populations. The two public invocations and the ordinary reference invocation exited successfully with the same output. The workbook hash remained unchanged.

The first and second public runs nevertheless had different UUID run directories, different SQLite paths, and `rebuilt: true` in both index manifests. Each recorded one accelerated workbook load. This is the expected behavior of the frozen code: [runner.py](src/librecalc_agent/runner.py) creates a new UUID run directory, resets in-process index state, calls `prepare(..., run_dir / "index", ...)`, and points the child at that run's manifest. [substrate.py](src/librecalc_agent/_frozen/substrate.py) places the SQLite index inside that new directory. The shared cache root does not imply reuse because no prior manifest or database is discovered by the public path. Passing a previous manifest through internal environment variables or retaining an in-memory substrate would create a different, unsupported execution condition.

## Frozen populations and prior evidence

The [previous manifest](../history/rc_acceleration_validation/workload_manifest.json), [eligible population](../history/rc_acceleration_validation/eligible_population.json), and [representative population](../history/rc_acceleration_validation/representative_population.json) were reused by hash. The eligible population contains 22 scripts; the representative population contains 30 scripts. The previous semantic forensics identified four genuine failures: `Debugging_08_04__2dde74bd671e`, `Financial_Model_15_03__472e28fbd6e0`, `Template_06_23__fc41ad37c48b`, and `Template_16_07__9662584ede5e`. Three are in the eligible population, leaving **19 preregistered semantically supported eligible scripts**. The fourth is in the representative population. These classifications preceded this probe and remain product limitations; this experiment did not retest or erase them.

The [frozen cold-start study](RC_ACCELERATION_CLAIM_VALIDATION_REPORT.md) remains unchanged: all 22 eligible scripts were slower under fresh packaged invocation, with a median paired RC/reference ratio of **2.017** (approximately 102% more wall time). Across the 19 previously supported eligible scripts, the prior median reference time was **0.561 s**, median cold RC time **0.809 s**, and median paired cold/reference ratio **2.005**. The separate medians are descriptive and their quotient is not the median paired ratio. Previous instrumented index setup had a median **0.323 s** in that 19-script subset, but it was a cost inside each cold invocation, not a reusable one-time investment. The prior primary verdict was `EXPERIMENT_INCONCLUSIVE` because of semantic failures and the earlier verdict mapping, despite the clear negative observed cold timings.

## Answers to the required questions

| # | Answer |
| --- | --- |
| 1–2 | **No** cross-invocation index reuse through the existing RC; **yes**, the exact installed public product command was used. |
| 3 | The same frozen workload manifests, workbook bytes, and script identity were retained. Only one previously selected script was run for the feasibility check; no new scored workload sample was substituted. |
| 4–5 | Four known genuine semantic failures are named above; 19 eligible scripts remained in the preregistered supported subset. |
| 6 | No valid warm execution existed, so new warm semantic mismatches were **not testable**. The feasibility probe matched ordinary reference output exactly. |
| 7–8 | **0 of 2** public probe invocations reused an index; both rebuilt. One probe workload contacted acceleration, but it was cold-style contact on each run. No warm workload was scored. |
| 9–13 | On the frozen 19-script subset, prior reference median **0.561 s**, cold RC median **0.809 s**, cold paired ratio **2.005**. Warm runtime, warm paired ratio, and warm geometric mean are **not estimable**. All 22 eligible prior scripts had median cold paired ratio **2.017**. |
| 14–16 | Warm geometric mean, workload-bootstrap interval, and faster/tied/slower count are **not estimable** because there are no scored warm runs. |
| 17–19 | Residual warm overhead and per-use warm saving are **not estimable**. Prior cold instrumented index setup median was **0.323 s** on the supported eligible subset; no reusable one-time `I` exists in the public lifecycle. |
| 20–22 | Median break-even reuse count, fractions by 2/3/5/10/20 uses, and a finite never-break-even fraction are **not estimable**. The RC does not offer the required indexed warm condition. |
| 23–26 | Warm effects by family, workbook size, read volume, and the representative population are **not measured**. Prior cold eligible ratios exceeded 1 in every family and all 22 scripts; prior representative median ratio was **1.704**, with 29 slower and one tie. |
| 27–30 | No warm product-speed claim is supported. Cold packaged execution was slower in every tested eligible workload, and four genuine semantic failures persist. Verdict: `WARM_PRODUCT_STATE_NOT_SUPPORTED_BY_RC`. |
| 31 | **No** further performance research experiment is needed for this frozen RC. Any cross-invocation reuse would require product engineering and a new product identity. |

The nominal amortization equation is `I + N·C < N·A`. Here `C` (a public invocation using an existing index without rebuilding) is unavailable. Assigning the prior cold setup time to a one-time `I` and using an internal fast-path time for `C` would not describe the shipped RC. The [break-even artifact](../history/rc_warm_acceleration_characterization/break_even_analysis.json) therefore contains no finite count.

## Final synthesis

### EXPERIMENT INTEGRITY

Identity and preregistration were checked before the public probe; the feasibility stop rule was honored. No scored warm timings were run or fabricated.

### PRODUCT IDENTITY

Frozen `librecalc-agent 0.2.0rc1`; source/config and wheel hashes match the requested identities.

### WARM STATE FEASIBILITY

Unsupported through the public RC path. The second invocation created a new UUID index directory and rebuilt the index despite an unchanged workbook and shared cache.

### SEMANTICALLY SUPPORTED POPULATION

19 of the 22 frozen eligible scripts satisfied the prior semantic-supported rule. None received a scored warm timing.

### KNOWN SEMANTIC FAILURES

Four prior genuine failures remain in the record; three overlap the eligible set.

### INDEX BUILD COST

The prior supported-eligible median instrumented setup was 0.323 s, paid inside each cold invocation. A public reusable one-time index cost does not exist.

### COLD PERFORMANCE

Frozen median eligible paired ratio 2.017; all 22 eligible scripts slower than ordinary openpyxl.

### WARM PERFORMANCE

Not measurable on the packaged public RC.

### ACCELERATION CONTACT

Both public probe runs accelerated one workbook load and rebuilt the index. Warm reuse contact was zero.

### SEMANTIC EXACTNESS

The probe matched ordinary reference output, but no warm exactness gate was run. The four prior genuine semantic failures persist.

### BREAK-EVEN AMORTIZATION

No valid public `C` exists, so no per-use saving or break-even count can be calculated.

### REPRESENTATIVE WORKLOAD EFFECT

No warm effect measured. The frozen cold representative median ratio was 1.704.

### ELIGIBLE WORKLOAD EFFECT

No warm effect measured. The frozen cold eligible median ratio was 2.017.

### PRIMARY VERDICT

`WARM_PRODUCT_STATE_NOT_SUPPORTED_BY_RC`.

### SUPPORTED SPEED CLAIM

The RC has a narrow accelerated read path, but this packaged release does not provide a reusable-index warm invocation through its public command.

### REQUIRED QUALIFIERS

Cold packaged execution was slower on all tested eligible scripts; four genuine semantic failures limit coverage. No warm, amortization, or general product-speed percentage is supported.

### RESEARCH STOP DECISION

No additional performance research for this RC. Preserve the frozen cold result and this warm-feasibility result; move to final presentation within these claim limits.
