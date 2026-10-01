# Packaged RC acceleration claim validation

**Claim decision: no packaged RC speed claim. Research stops.** The frozen `librecalc-agent 0.2.0rc1` wheel was validated byte for byte and exercised through its public `librecalc-agent run` command. Across 22 preregistered eligible read scripts, all 22 had acceleration contact and all 22 were slower than direct ordinary Python/openpyxl when fresh per-invocation setup was charged. The median treatment/control wall-time ratio was **2.017**. Four workloads also exposed genuine semantic differences, so the exactness guard fails independently of speed.

The frozen algorithm assigned `EXPERIMENT_INCONCLUSIVE` because exactness failed. That label has a [documented taxonomy gap](rc_acceleration_validation/decision_adjudication.json): the failure came from reproducible RC behavior, not benchmark infrastructure. The empirical product conclusion is stronger and simpler: **this RC has no supported total-invocation acceleration claim on the tested workload class**. This report does not repair the mapping after seeing outcomes.

## Identity, public path, and preregistration

The [RC identity record](rc_acceleration_validation/rc_identity.json) verifies version `0.2.0rc1`, source/config SHA-256 `1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee`, and wheel SHA-256 `532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e`. All 24 installed package files in the frozen isolated environment matched wheel contents. Python was 3.13.12 and openpyxl 3.1.5 on Linux. The public CLI syntax came from the packaged entry point and runner, not an internal shortcut.

The [preregistered specification](rc_acceleration_validation/preregistered_spec.json) was frozen at SHA-256 `a05a71536fcc1c56aa9164ab32824116f9c05d412551308370c1944dbe7987b5` before scored timing. The [primary freeze](rc_acceleration_validation/primary_freeze.json) records 384 raw invocation rows: 48 distinct scripts × two arms × one unscored warm-up plus three scored repetitions. One worker ran at a time. Each invocation used a new work directory, original workbook copy, and empty `XDG_CACHE_HOME`; workbook staging occurred before the clock. The same normalized script bytes ran in both arms. CONTROL used the installed environment's Python directly; TREATMENT used the installed `librecalc-agent run` with shipped defaults. The external `perf_counter_ns` interval included CLI startup, classification, index construction, child script, default assurance/capture work, diagnostics, and teardown. Workbook hashes stayed unchanged in all scored runs.

## Workload selection

Only archived H0 or neutral A/control Python sources and actual SpreadsheetBench workbooks were used. The [workload manifest](rc_acceleration_validation/workload_manifest.json) records 300 deduplicated candidates. A control-only direct-Python preflight found 296 usable scripts. Sources with exactly one source-workbook load and no detected workbook write were normalized only by replacing the original workbook literal with `input.xlsx`; the resulting file was shared byte for byte across arms. A static filter and control preflight preceded any treatment timing.

The treatment-blind [representative view](rc_acceleration_validation/representative_population.json) contains 30 scripts, 10 per family, from 21 underlying tasks. It did not require A1 admission. The [eligible view](rc_acceleration_validation/eligible_population.json) contains 22 distinct scripts from 14 underlying tasks: 14 Financial_Model, five Debugging, three Template. Eligibility required the unchanged packaged A1 classifier to admit the source and at least five static read API references, with at most two scripts per task. Workbook size and treatment speed played no part in selection. The scripts are the sampling unit; repeated timings are not independent samples. Task-cluster bootstrap sensitivity is reported because some scripts share an underlying workbook.

## Whole-invocation timing

The table reports ratios of workload-level medians from three scored repetitions. Ratios above one mean the packaged invocation was slower. Bootstrap intervals resample workloads; cluster sensitivity resamples underlying tasks.

| View | N scripts / tasks | Median ratio | Mean ratio | Geometric ratio | 95% bootstrap geometric CI | Faster / tie / slower |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| Eligible primary | 22 / 14 | **2.017** | 2.129 | 2.073 | **1.880–2.285** | **0 / 0 / 22** |
| Representative supporting | 30 / 21 | **1.704** | 1.721 | 1.650 | **1.487–1.834** | **0 / 1 / 29** |

The eligible median reduction, defined as `1 − treatment/control`, was **−101.7%**: treatment took about twice as long. The task-cluster geometric interval was **1.887–2.309** across 14 tasks. Removing the two largest apparent wins still left median ratio **2.047**; no favorable outliers create the result. The exact-output eligible subset also had no faster workloads and median ratio **2.005**, a descriptive check that cannot rescue the failed exactness gate. The per-workload [timing table](rc_acceleration_validation/workload_timings.json) and [raw ledger](rc_acceleration_validation/raw_timings.jsonl) preserve every measurement.

| Family | Eligible N | Eligible median ratio | Representative N | Representative median ratio |
| --- | ---: | ---: | ---: | ---: |
| Template | 3 | 2.453 | 10 | 2.204 |
| Financial_Model | 14 | 1.848 | 10 | 1.508 |
| Debugging | 5 | 2.030 | 10 | 1.417 |

Larger workbooks were less slow in this sample, but still slower: median eligible ratio was **2.381** below 100 KB, **2.030** from 100 KB to 1 MB, and **1.812** at or above 1 MB. Eligible workbook sizes ranged from 7,552 to 2,173,244 bytes and static read references from five to 19. The preregistered ≥1 MB and ≥10-reference tail had only two scripts from one task, so it cannot earn a narrow subclass claim. No observed size/read-volume break-even region exists within this tested range.

## Contact, setup, and economics

The [contact ledger](rc_acceleration_validation/acceleration_contact.json) shows contact on **22/22 eligible** scripts and **8/30 representative** scripts. Across scored treatment repetitions the shipped runtime logged **78 accelerated `load_workbook` events and 78 fresh index creations**, with zero index-build failures. It logs admitted workbook loads, not every proxied cell or range read; dynamic read-event totals and escaped-object counts cannot be recovered from the shipped telemetry. Static source read references are retained but are not substituted for dynamic counts.

The RC's on-disk index manifest records per-workbook `ensure_s` and `backup_s`, although it omits the in-memory aggregate returned to the parent runner. The [decomposition](rc_acceleration_validation/timing_decomposition.json) sums the recorded parts for each invocation. Eligible median fresh index setup was **0.264 s**, against median CONTROL invocation time **0.313 s**; the median per-workload setup/control fraction was **0.644**, and setup alone exceeded the entire control run on three scripts. Median eligible net wall-time saving was **−0.263 s**. Treatment's median timed accelerated load event was **0.083 s**, but the unchanged CONTROL scripts did not separately time matching load operations. Thus current-workload *gross read savings* are not directly identifiable; the authoritative measured quantity is the negative net total-invocation effect. Residual treatment wall time includes process startup, child work, default capture, diagnostics, and teardown, so capture's individual cost cannot be isolated without changing the frozen measurement.

Historical exact-trace tests support a faster admitted-read mechanism under their lifecycle. They do not establish that those gains exceed the packaged RC's fresh setup and wrapper cost. No persistent-index amortization was assumed or used in this study.

## Semantic and fail-closed guards

Raw stdout and exit codes agreed on **40/48** workloads. [Forensic normalization](rc_acceleration_validation/semantic_forensics.json) identified four raw differences caused solely by process-specific memory addresses in printed openpyxl formula-object representations; this is a descriptive explanation, not a change to the frozen raw exactness gate. **Four genuine differences remain**, reproduced in all three scored repetitions:

| Workbook script | Observed treatment divergence |
| --- | --- |
| `Template:06_23` | `for ws in wb` raised `KeyError: Worksheet 0 does not exist`; CONTROL completed. |
| `Financial_Model:15_03` | The same workbook-iteration failure after treatment printed sheet names. |
| `Debugging:08_04` | Array-formula values were exposed as formula strings rather than openpyxl formula objects, changing printed observations. |
| `Template:16_07` | A script reading an array formula's `.text` failed because treatment returned a string. |

These are product semantic failures, not provider or timing noise. The workbook-iteration path tried to delegate a numeric sequence lookup to real openpyxl's sheet-name `__getitem__`, which still raised; optional acceleration therefore vetoed valid reference work in those scripts. The [small fail-closed probe](rc_acceleration_validation/failclosed_checks.json) also confirmed the narrower positive guard: when the cache was unavailable, the CLI returned the same output and exit code as ordinary Python; a preregistered unsupported source used `PREDECLARED_REAL_OPENPYXL` and matched CONTROL. That success does not negate the four admitted-path failures. No RC file was patched.

## Preregistered verdict and claim discipline

The frozen primary algorithm returned **`EXPERIMENT_INCONCLUSIVE`** because the exactness gate failed. Its prose had reserved that label for benchmark/environment failure, leaving a taxonomy gap for a genuine RC semantic failure. [Adjudication](rc_acceleration_validation/decision_adjudication.json) preserves the algorithm's label and names the gap rather than rewriting a gate. Timing remains a strong negative observation: 22/22 eligible slower, bootstrap interval wholly above one, and no favorable family. Semantic mismatches independently prohibit the requested “while preserving reference reads exactly” clause.

**Strongest supported public statement:** “In a preregistered fresh-invocation replay of 22 eligible SpreadsheetBench-derived read scripts, packaged `librecalc-agent 0.2.0rc1` was slower than direct ordinary Python/openpyxl on every script, and four distinct scripts exposed genuine read-semantic differences. This RC does not support a packaged wall-clock acceleration claim for that workload class.”

Unsupported: universal speedup, eligible-workload speedup, exactness for all admitted reads, provider or token savings, lower total cost, capability equivalence, or cross-invocation amortization. Historical per-read speed evidence remains historical and cannot be promoted to a packaged RC claim. No further research experiment is justified under the requested stop rule; the product defect belongs in post-research engineering, with any changed artifact requiring a new product identity.

## Required answers

1. **Exact wheel?** Yes; frozen wheel and source/config hashes matched, and installed package files matched wheel bytes.
2. **Public invocation?** Yes: installed `librecalc-agent run` with shipped defaults.
3. **Identical workload?** Yes, one normalized script and workbook copy per workload in both arms.
4. **Fresh setup?** Yes, separate empty product cache for every treatment invocation.
5. **Selection?** Archived control scripts, original workbooks, control-only preflight and static rules.
6. **Treatment-blind?** Yes; no historical treatment speed or live treatment timing selected tasks.
7. **Eligibility?** A1 admission, read-only one-workbook source, usable control preflight, at least five static read API references, max two scripts per task.
8. **Representative N?** 30 scripts, 21 tasks, 10 scripts per family.
9. **Eligible N?** 22 scripts, 14 tasks.
10. **Contact workloads?** 22/22 eligible, 8/30 representative, 26/48 union.
11. **Accelerated events?** 78 logged accelerated workbook loads over scored repetitions; cell-level dynamic count unavailable.
12. **Mismatches?** Four genuine semantic/exit mismatches, plus four volatile-address-only raw differences.
13. **Fallback exact?** Unavailable-cache and unsupported-source checks passed; admitted workbook iteration did not fail closed correctly.
14. **Setup/index cost?** Eligible median 0.264 s; one fresh index per contacted scored invocation.
15. **Gross read saving?** Not separately measurable for unchanged scripts; historical per-read savings do not quantify this RC run's gross savings.
16. **Net invocation saving?** Median eligible saving −0.263 s; all 22 slower.
17. **Eligible median ratio?** 2.017.
18. **Mean/geometric mean?** 2.129 / 2.073.
19. **Bootstrap interval?** 1.880–2.285 for the geometric ratio; task-cluster sensitivity 1.887–2.309.
20. **Faster/tie/slower?** Eligible 0/0/22; representative 0/1/29.
21. **Concentration?** No one- or two-workload win drives the result; every eligible ratio exceeds one.
22. **By family?** Eligible medians Template 2.453, Financial_Model 1.848, Debugging 2.030.
23. **By size/reads?** Larger workbooks were less slow but remained slower; no observed break-even up to 2.17 MB and 19 static read references.
24. **Representative view?** 8/30 contact, median ratio 1.704, one near tie and 29 slower.
25. **Break-even?** None observed; index setup consumed median 64.4% of control invocation time before other product overhead.
26. **Optional overhead?** Fresh index setup materially consumed potential savings; capture/startup residual cannot be individually isolated.
27. **Supported speed claim?** None for the packaged RC.
28. **Explicitly unsupported?** Any total-invocation acceleration or exact-admitted-read claim for this tested class.
29. **Verdict?** Frozen algorithm: `EXPERIMENT_INCONCLUSIVE`, with a documented product-semantic-failure taxonomy gap; substantive claim decision: no RC acceleration claim.
30. **Further research experiment?** **NO**. Research ends; the failure is a product-engineering issue.

## Final synthesis

### EXPERIMENT INTEGRITY

Frozen 48-workload union, 384 invocations, three scored paired repetitions, fresh cache each time; raw ledger and preregistration hashes preserved.

### PRODUCT IDENTITY

Exact `librecalc-agent 0.2.0rc1` source/config and wheel hashes verified, including installed files; no patch.

### WORKLOAD POPULATIONS

30 treatment-blind representative scripts and 22 A1-admitted eligible scripts from archived control traces.

### ACCELERATION CONTACT

22/22 eligible and 8/30 representative scripts contacted acceleration; 78 scored accelerated load events and index builds.

### SEMANTIC EXACTNESS

Four genuine product-semantic failures, four volatile-address-only stdout differences, 40/48 raw exact workloads. The guard fails.

### SETUP COST

Median fresh eligible index setup 0.264 s, or 64.4% of each script's control time at the median of per-workload fractions.

### FAST-PATH SAVINGS

Historical admitted-read speedup remains supported only within earlier lifecycles. Gross savings for unchanged scripts were not separately identifiable here.

### TOTAL INVOCATION EFFECT

Eligible median ratio 2.017; all 22 slower. Net median saving −0.263 s.

### REPRESENTATIVE WORKLOAD EFFECT

Median ratio 1.704; 8/30 contact, zero clearly faster, one tie, 29 slower.

### ELIGIBLE WORKLOAD EFFECT

Geometric ratio 2.073 with 95% workload bootstrap interval 1.880–2.285; every family adverse.

### BREAK-EVEN REGION

None observed within 7.5 KB–2.17 MB and five to 19 static read references.

### PRIMARY VERDICT

`EXPERIMENT_INCONCLUSIVE` under the frozen but incomplete verdict mapping because the exactness guard failed from RC behavior. No packaged acceleration claim is supported.

### SUPPORTED CLAIM

The tested packaged RC incurred fresh setup and was slower on every eligible script; the study also exposed four reproducible semantic failures.

### UNSUPPORTED CLAIMS

Packaged RC wall-clock acceleration, universal speedup, exact admitted-read replay, token/cost/capability claims, and cross-invocation index amortization.

### RESEARCH STOP DECISION

`NO_FURTHER_RESEARCH_EXPERIMENT`. Freeze this negative result and move to final claim registry, technical report, presentation, and demo preparation.
