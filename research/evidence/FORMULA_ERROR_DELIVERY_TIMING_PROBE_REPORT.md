# ASSISTED_DELIVERY_TIMING_PROBE — frozen result

**Preregistered verdict: `DELIVERY_TIMING_NOT_SUPPORTED`.** This is a delivery feasibility result, not a capability or natural-workflow product verdict. The previous `FORMULA_ERROR_FEEDBACK_INCONCLUSIVE` verdict is unchanged. No confirmation reserve task or outcome was used.

## Frozen protocol and integrity

The [preregistration](../history/formula_error_delivery_probe/preregistered_spec.json), [population](../history/formula_error_delivery_probe/population.json), [run order](../history/formula_error_delivery_probe/run_order.json), [provider configuration](../history/formula_error_delivery_probe/provider_config.json), [exact template](../history/formula_error_delivery_probe/treatment_template.json), and [pre-run hash file](../history/formula_error_delivery_probe/spec_hash.json) were written before the first model call. All 15 frozen hashes still match after the final run. A mechanical source comparison confirmed the copied `compute_nfe_delta`, `select_representatives`, and `render_report` functions, report introduction, and model-visible tool definitions match the prior runner. The new runner changed only experiment paths, arm-neutral provider timing/routing, and invisible output snapshots. Every transcript contains the exact common instruction:

> After your first substantive workbook edit, save a provisional `output.xlsx` by call 20, then continue inspecting, correcting, verifying, and completing the task normally.

The selected tasks were `Debugging:01_03`, `02_02`, `02_03`, and `02_05`. The frozen gold-blind rule selected the first four eligible Debugging tasks with at least three errors on an unedited openpyxl round-trip under the frozen detector; the screen is in `population.json`. These tasks exclude all eight prior discovery tasks and every task ID listed in the prior reserve **manifest**. The reserve workbooks and outcomes were not opened. The original narrow `XX_03` screen was broadened **before preregistration and before any live inference** because it found only two positive tasks; the final rule and its screen rows were frozen before the first run. Three selected tasks belong to the 02 workbook family, so this is a correlated feasibility sample, not a prevalence sample.

All eight primary slots ran in the frozen counterbalanced order; one preregistered 02_03 treatment replacement ran after its provider-censored primary. No model outcome was replaced. Arm-neutral provider repair set an ordered OpenRouter route (`Modal`, `CoreWeave`, `DigitalOcean`, fallback allowed), a 30-second socket timeout, a 120-second absolute request deadline, and an 1,800-second run timeout. Model ID `z-ai/glm-5.3-flash`, sampling, prompt scaffold apart from the common instruction, tools, 50-call cap, $0.25 instance cap, detector, report renderer, and official scorer stayed frozen. The provider still served multiple endpoints and censored both 02_03 treatment attempts. The exact configuration is recorded, not retroactively optimized.

The local UNO calculation service was started and health-checked before inference. During 02_02 treatment the agent itself issued `pkill -f soffice` at call 18, which also stopped that service. I restarted the same predeclared service; it was healthy for the remaining runs, and final 02_02 NFE evaluation succeeded. This operational intervention is visible here and in the transcript. It did not change the model-visible report, runner code, or contact rule. No run was classified as workbook-infrastructure censored.

## Run and contact ledger

| Slot | Task | Arm | Attempt class | Calls | Output saves | Report | Official submission status |
|---:|---|---|---|---:|---|---|---|
| 1 | 02_02 | Treatment | `VALID_SUBMISSION` | 49 | call 4, 30 NFE | call 4, 46 left | Valid output submitted |
| 2 | 02_02 | Control | `MODEL_NONCOMPLETION` | 50 | none | invisible | Call cap |
| 3 | 02_05 | Treatment | `MODEL_NONCOMPLETION` | 50 | none | none | Call cap |
| 4 | 02_05 | Control | `MODEL_NONCOMPLETION` | 47 | none | invisible | Cost cap |
| 5 | 02_03 | Control | `MODEL_NONCOMPLETION` | 46 | call 5, 30 invisible NFE | invisible | Cost cap; workbook exists |
| 6 | 02_03 | Treatment | `PROVIDER_CENSORED` | 43 | none | none | Three request-deadline failures |
| 7 | 01_03 | Control | `MODEL_NONCOMPLETION` | 48 | none | invisible | Cost cap |
| 8 | 01_03 | Treatment | `MODEL_NONCOMPLETION` | 23 | none | none | `submit` invoked with **no** output workbook |
| R1 | 02_03 | Treatment | `PROVIDER_CENSORED` | 24 | none | none | Three request-deadline failures |

This yields **one valid submission, six model noncompletions, two provider-censored attempts, and zero runner/workbook-infrastructure censors** across nine attempts. Both provider censors occurred on the same treatment task. The 02_03 control's scored workbook is a solo *noncompletion* output, not a valid paired submission.

Two runs created `output.xlsx` by call 20: 02_02 treatment at call 4 and 02_03 control at call 5. In each, the [saved snapshot](../history/formula_error_delivery_probe/workbook_mutations.jsonl) is **SHA-256 byte-identical to `input.xlsx`**. The agents copied the input rather than saving after a substantive workbook cell edit. Thus **2/8 early output creations, 0/8 verified provisional saves after a substantive edit**. Only one enriched treatment had a nonempty qualifying save and report. The other observed treatment trajectories did not save; 02_03 remains provider-censored after its allowed replacement.

The observed timely-contact count is **1/4**, at call 4 with 46 calls remaining. Treating the doubly censored 02_03 task as unknown gives an upper bound of **2/4**, still below the frozen **≥3/4** feasibility gate. This is why the result is `DELIVERY_TIMING_NOT_SUPPORTED` rather than `PROBE_INCONCLUSIVE`: provider failure remains real, but it cannot change the gate decision. The old ≥6/7 discovery gate was not reinterpreted.

## Contacted treatment: 02_02

At call 4, before any substantive workbook edit, the model copied `input.xlsx` to `output.xlsx` and printed input workbook content. The output's bytes remained identical to the input's through submission. The frozen detector nonetheless recalculated the output copy and compared it with input read as-is, finding 30 `Err:522` cells with unchanged formulas in `Berk-Hath Investment Package`. This is a real **recalculated-state** error signal, but it is not evidence that the agent's formula edit caused those errors. The report's “newly introduced” phrasing therefore overstates causal attribution in this case. This is the same unchanged report identity as the prior 02_06 contact: its rendered report SHA-256 is `a652a84532efe66947811bafbfec0812bf950e87388124e2d84ebdbfe0f33a1a`.

Exact model-visible report (appended once after the call-4 observation):

```text
A spreadsheet recalculation found newly introduced formula errors that were not present in the input workbook.

Total: 30

By sheet:
    Berk-Hath Investment Package: 30

Representative cells:
    Berk-Hath Investment Package!F10: Err:522
    Berk-Hath Investment Package!F11: Err:522
    Berk-Hath Investment Package!F12: Err:522
    Berk-Hath Investment Package!F13: Err:522
    Berk-Hath Investment Package!F14: Err:522
    Berk-Hath Investment Package!G10: Err:522
    Berk-Hath Investment Package!G11: Err:522
    Berk-Hath Investment Package!G12: Err:522

Note: showing 8 of 30 representative cells.
```

The first post-feedback action, **call 5**, used Python/openpyxl through `bash` to print formulas and values on the **reported sheet**, including the shown cells. Later commands inspected the sensitivity grid, `G10` data-table formula, its XML, and recalculated input copies. The [post-contact ledger](../history/formula_error_delivery_probe/post_contact_actions.jsonl) records 45 subsequent calls and 13 conservatively tagged as traceably relevant inspections. These commands satisfy the preregistered `TRACEABLE_EVIDENCE_USE` definition by inspection; `view_xlsx` was not required. Temporal targeting is evident, but the record cannot prove that feedback *caused* the investigation rather than the broad audit task.

There were **zero post-feedback `output.xlsx` saves or cell edits**. Temporary recalculated files and bash calls are not workbook repair. The model performed calculation experiments on input copies, but never verified a *repaired output* because none existed. It called `submit` at 49 with the unchanged output copy. The detector still found **30/30** live new errors; all eight shown cells remained present and no post-report new errors appeared. The official score of this submitted treatment was modification **0.0**, regression **0.9851**, accuracy **0.0**. Its control had no submitted workbook, so the score is unpaired. No `MECHANICAL_REPAIR_WITHOUT_CAPABILITY_EVIDENCE` event occurred here because live errors did not decrease.

## Official capability and safety signal

The unchanged official `open_spreadsheet.py` refresh and `evaluation.py` scorer processed the two archived output workbooks; raw scorer files are under [score_staging](../history/formula_error_delivery_probe/score_staging). The 02_02 treatment scored modification 0.0 and regression 0.9851. The 02_03 control's noncompleted, byte-copy workbook scored modification 0.7265 and regression 0.9896. Missing outputs were recorded as **null**, not treated as the scorer's placeholder zeros. [paired_scores.json](../history/formula_error_delivery_probe/paired_scores.json) contains **0/4 valid pairs** and no deltas. Consequently there is no official capability benefit estimate, no paired regression-safety assessment, and no efficiency inference. The only contacted output retained 30 errors and scored no modification credit.

## Required answers

| # | Answer from the frozen artifacts |
|---:|---|
| 1 | All eight primary slots and four pairs were attempted under the frozen specification; 02_03 treatment remained provider-censored after one permitted replacement. |
| 2 | Two provider censors on 02_03 treatment; zero runner and zero workbook-infrastructure censors. |
| 3 | Two output paths were created by call 20; **zero** were verified post-substantive-edit provisional saves. Both were byte-identical input copies. |
| 4 | One observed treatment task had a nonempty qualifying save; 02_03 is censored/unknown. |
| 5 | One treatment task contacted by call 25. |
| 6 | 02_02 report at call 4; 46 calls remained. |
| 7 | No. Observed 1/4; even the censoring upper bound is 2/4. |
| 8 | 02_02 first used bash/openpyxl to inspect the reported sheet at call 5. |
| 9 | 02_02 gathered relevant sensitivity-grid/data-table evidence; causal effect of the report on that behavior is unknown. |
| 10 | No contacted agent modified `output.xlsx` after feedback (0/1). |
| 11 | No post-feedback workbook edits existed to relate to the report. |
| 12 | Contacted live NFE stayed 30→30; all eight shown errors remained. |
| 13 | It inspected recalculated input copies but did not verify a repaired output workbook. |
| 14 | The one contacted agent submitted at call 49. |
| 15 | Zero valid paired official outcomes; only solo scores are available. |
| 16 | No mechanical error reduction occurred, so no repair-to-capability association can be assessed. |
| 17 | No paired regression-safety issue can be assessed; no guard conclusion is warranted. |
| 18 | The dominant boundary remains **agent obeys early-save opportunity → timely qualifying save**. For 02_03, provider execution is a separate earlier censoring boundary. Copy-only saves expose a later causal-attribution problem in the report. |
| 19 | `DELIVERY_TIMING_NOT_SUPPORTED`. |
| 20 | Close the unchanged assisted-delivery capability retry route; do not run a larger unchanged-mechanism benchmark. |

## EXPERIMENT INTEGRITY

The four selected pairs and one permitted infrastructure replacement were attempted in the frozen order. All frozen hashes verified after the last run. The report was delivered once in the sole contacted run; control telemetry stayed invisible. The original discovery verdict and reserve remained untouched.

## ASSISTED DELIVERY REGIME

The exact common provisional-save instruction was present in all nine transcripts. Two early output creations were input copies; none was an observed post-edit provisional save. Results concern this assisted scaffold only.

## PROVIDER RELIABILITY

The arm-neutral route/deadline repair did not fully stabilize execution: 02_03 treatment primary and R1 each had three 120-second request-deadline failures. No runner or workbook infrastructure censor prevented the gate determination.

## TIMELY CONTACT

Observed 1/4 at call 4 with 46 calls left; censoring upper bound 2/4. The ≥3/4 gate failed.

## POST-CONTACT MODEL BEHAVIOR

The contacted agent inspected the reported grid immediately and continued investigating related data-table calculations. That is traceable evidence use by inspection, with no demonstrated causal effect on task success.

## WORKBOOK MUTATIONS

No post-feedback `output.xlsx` mutation occurred. The triggering output was a byte-identical copy of input; bash commands and temporary recalculation files were not counted as workbook edits.

## MECHANICAL ERROR EFFECT

The contacted live-error count remained 30→30. Error disappearance did not occur, so `MECHANICAL_REPAIR_WITHOUT_CAPABILITY_EVIDENCE` was not triggered.

## OFFICIAL CAPABILITY SIGNAL

There were zero valid paired submissions. The contacted solo treatment scored modification 0.0 and regression 0.9851; no benefit, harm, or paired safety conclusion follows.

## EARLIEST LOSS BOUNDARY

The common early-save instruction did not reliably yield a post-edit qualifying save. Provider censoring independently blocked 02_03. The only early contact came from a copy-only output, revealing that the frozen input-as-is versus recalculated-output representation can label exposed computation errors as “newly introduced” without a formula edit.

## PRIMARY VERDICT

`DELIVERY_TIMING_NOT_SUPPORTED`

## WHAT THIS DOES NOT ESTABLISH

This result does not establish capability failure conditional on genuine post-edit timely contact, provider-independent contact prevalence, or natural-workflow product value. One agent's relevant inspection is not a semantic repair; no paired capability outcome exists.

## SINGLE NEXT ACTION

Freeze and close the **unchanged assisted-delivery capability retry route**. Do not run a larger unchanged-mechanism test or open the confirmation reserve. Any future different trigger, wording, selection, or causal localization must be registered as a new mechanism on a fresh discovery population.
