# Default harness deterministic execution

**Verdict:** `NO_EXECUTOR_ADOPTION`

Live inference was stopped by the operator before the last incomplete pairs finished. The report uses every completed matched pair plus static preflight. Architecture was not changed after seeing scores.

Primary question: once a general coding agent has chosen what cells to edit and what formula they should contain, does moving mechanically repetitive formula execution into a deterministic harness improve end-to-end spreadsheet capability over the default coding harness?

That question was not answered end-to-end, because **C1 never called `calc_translate_fill`.**

Cost is recorded in the appendix and is not part of the gate.

---

## Frozen contract

- Model: `z-ai/glm-5.3-flash`, reasoning `high`, temperature `0.0`, top_p `1.0`, provider `allow_fallbacks` + `require_parameters`
- Envelope: 60 calls / $5.00 / 7200s timeout, matched across arms
- C0: `spreadsheet-control.yaml` (bash, Python/openpyxl, `view_xlsx`, `submit`)
- C1: same plus optional `calc_translate_fill`; model remains sovereign over targets and formulas
- Forbidden: Task IR, Edit Plan authority, scheduler, retrieval, synthesis, autonomous compiled runner, ProgramGroup-generated edit authority
- Git freeze and hashes: `default_harness_deterministic_execution/experiment_spec.json`, `prompt_config_hashes.json`, `provider_model_identity.json`

Prompt hashes:

- C0/C1 system templates identical: `0c36c45319b387fbdb58a3c899c1d8d0beed4d5426f0aa80422114165930b24b`
- C0 instance: `a659355097d0faeeff8aeb10bb728c34e40c002cda67cd439bcc99f9da9dafa9`
- C1 instance: `3b379ca7976614a2c4a5dd2dc785266f0d1345d57f4a87736cde581440b0d0aa`
- Tool schema: `a030b193ed43999e553403c97715e59b1f9957f86d2b99574fde0e93ab190f3f`
- Executor: `fee61e1c7ab57a146e712974ea67509940056981d26bf5cccf432b69e057e929`

C1 differs from C0 only by the `calc_translate_fill` schema and its short explanation. Ordinary tools are identical. Source workbooks are byte-identical across arms.

---

## Population

### Legacy witnesses (fully qualified)

| ID | Role |
| --- | --- |
| `Financial_Model:08_03` | positive witness (`Working Capital!J44:N44`) |
| `Financial_Model:08_04` | wrong-canonical negative control |
| `Financial_Model:08_05` | absent/novel-program negative control |
| `Financial_Model:15_04` | mechanical-boundary witness |

### Held-out input-only census

Gold, evaluator scores, and historical model outcomes were not used. Selection used mechanically witnessed repeat groups, member counts, group sizes, and category diversity.

Eight eligible tasks were selected (cap reached):

- `Financial_Model:08_02`, `Financial_Model:08_01`
- `Template:06_09`, `Template:06_16`
- `Debugging:10_02`, `Debugging:10_04`
- `Visualization:Task 1420776`, `Visualization:Task 1426290`

ProgramGroup development tasks `08_03/08_04/08_05/09_05/15_04/17_03/07_03/14_05` were excluded from held-out selection. Full census: `default_harness_deterministic_execution/held_out_census.json`.

This is a mechanism-enriched slice, not an unbiased benchmark sample.

---

## Preflight (before live inference)

Static executor tests passed: relative/absolute/mixed/cross-sheet translation, no writes outside declared targets, rejection leaves bytes unchanged, gold paths refused, shared-master typed reject, determinism.

On `08_03` input, `Working Capital!J44:N44` is empty. A parallel-line witness on row 45 permits fill. A local `calc_translate_fill` of a model-supplied canonical formula wrote exactly those five cells. A non-unit-stride target set rejected with zero mutation.

---

## Completion status

Live launch ran ~80 minutes with 3 workers, then was stopped.

| Pair | Status |
| --- | --- |
| 8 matched non-visual pairs | completed and officially scored |
| `Debugging:10_02` | both arms hit the 60-call cap; no output; resource-censored |
| `Debugging:10_04` | C0 completed and scored; C1 stopped mid-run |
| `Visualization:Task 1420776` | both arms wrote outputs; Visualization is outside the official non-visual scorer |
| `Visualization:Task 1426290` | C1 wrote an output; C0 stopped; not officially scored |

No OpenRouter identity/provider crash on completed jobs.

---

## Paired official scores

Usable means modification ≥ 0.99 and regression ≥ 0.99. Visualization rows are not official.

| Task | Role | C0 exact | C1 exact | C0 mod | C1 mod | C0 reg | C1 reg | C0 usable | C1 usable | C1 used fill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Financial_Model:08_03` | positive witness | no | no | 0.9973 | 0.9923 | 1.0 | 1.0 | yes | yes | no |
| `Financial_Model:08_04` | wrong-canonical NC | no | **yes** | 0.5336 | **1.0** | 1.0 | 1.0 | no | **yes** | no |
| `Financial_Model:08_05` | absent-program NC | no | no | 0.9782 | 0.9782 | 1.0 | 1.0 | no | no | no |
| `Financial_Model:15_04` | mechanical boundary | no | no | 0.8574 | 0.8529 | 1.0 | 1.0 | no | no | no |
| `Financial_Model:08_02` | held-out | no | no | 0.9984 | 0.9984 | 1.0 | 1.0 | yes | yes | no |
| `Financial_Model:08_01` | held-out | no | no | 0.6393 | 0.9294 | 1.0 | 1.0 | no | no | no |
| `Template:06_09` | held-out | no | **yes** | 0.958 | **1.0** | 1.0 | 1.0 | no | **yes** | no |
| `Template:06_16` | held-out | no | **yes** | 0.7736 | **1.0** | 1.0 | 1.0 | no | **yes** | no |
| `Debugging:10_02` | held-out | censored | censored | — | — | — | — | — | — | no |
| `Debugging:10_04` | held-out | no | stopped | 0.9008 | — | 0.7805 | — | no | — | no |
| `Visualization:Task 1420776` | held-out | unscored | unscored | — | — | — | — | — | — | no |
| `Visualization:Task 1426290` | held-out | stopped | unscored | — | — | — | — | — | — | no |

Among the 8 scored matched pairs: C1 exact 3/8, C0 exact 0/8; C1 usable 5/8, C0 usable 3/8. Those deltas are **not** an executor result. C1 never delegated a fill to `calc_translate_fill`. The C1 prompt is slightly different (optional tool explanation), and GLM remains stochastic across matched reruns even at temperature 0. Do not read this table as `DEFAULT_HARNESS_EXECUTION_GAIN`.

---

## Execution ledger

Accepted invocations: **0**

Rejected invocations: **0**

No `.calc_translate_fill_ledger.jsonl` files exist.

A few C1 runs mentioned the tool in reasoning and then wrote openpyxl loops instead: `08_03`, `08_04`, `08_02`, `Template:06_16`.

---

## 08_03 witness autopsy

Region: `Working Capital!J44:N44` (empty on input; gold formulas are `=+J35+J26+J15+J6` and column translations).

| | C0 | C1 |
| --- | --- | --- |
| Identified a translated five-cell fill | yes | yes |
| Used `calc_translate_fill` | no | no |
| Members written | 5/5 | 5/5 |
| Gold-identical formula text | 0/5 (`=J6+J15+J26+J35` order) | 0/5 (`=J35+J26+J15+J6`, no unary `+`) |
| Official exact | no | no |
| Official usable | yes (mod 0.9973) | yes (mod 0.9923) |

C0 already executed the repeated region with a Python fill. The archived ProgramGroup failure (inconsistent independent synthesis, 2/5 exact members) did **not** reproduce on this default GLM coding agent.

Record: `NO_REPEATED_EXECUTION_FAILURE_ON_08_03`.

Official misses were outside that region (C0 `Ratio Analysis!C19`; C1 first reported error `DCF Valuation!J16` while regression stayed 1.0).

---

## Negative-control audit

- **Wrong canonical (`08_04`).** The executor never ran, so it neither repaired nor faithfully propagated a wrong program. C1’s official-exact score was ordinary Python.
- **Absent program (`08_05`).** Both arms 0.9782 modification; no executor-invented program.
- **Unsupported homogeneity (`15_04`).** The live tool-reject path was not exercised. Static preflight still rejects non-unit-stride / holed sets with zero writes. Official mods 0.8574 vs 0.8529.
- **Regression outside declared targets.** Not applicable: no accepted harness writes.

---

## Capability verdict

`NO_EXECUTOR_ADOPTION`

The clearly explained primitive was never invoked, so this run cannot test whether deterministic translation improves the default harness.

Per the spec, that first requires asking whether C0 already performs equivalent fills in Python. On the distinguishing witness `08_03`, it does: C0 wrote all five translated members without the helper. Several other C1 exact/usable wins therefore remain unexplained by the mechanism under test.

This is not `DEFAULT_HARNESS_EXECUTION_GAIN`.
This is not `EXECUTOR_HARMFUL` (the executor never wrote).
This is not a GLM-vs-Spark comparison.

Do not redesign the interface from this stop. A later experiment can ask why the agent prefers Python, or whether forcing the primitive changes anything. That is a different question.

---

## Appendix: cost (not in the gate)

| Task | C0 calls | C1 calls | C0 $ | C1 $ |
| --- | --- | --- | --- | --- |
| `Financial_Model:08_03` | 25 | 31 | 0.091 | 0.119 |
| `Financial_Model:08_04` | 25 | 34 | 0.071 | 0.173 |
| `Financial_Model:08_05` | 34 | 28 | 0.098 | 0.152 |
| `Financial_Model:15_04` | 45 | 33 | 0.185 | 0.140 |
| `Financial_Model:08_02` | 41 | 43 | 0.109 | 0.241 |
| `Financial_Model:08_01` | 50 | 45 | 0.383 | 0.265 |
| `Template:06_09` | 8 | 7 | 0.049 | 0.036 |
| `Template:06_16` | 7 | 6 | 0.054 | 0.012 |
| `Debugging:10_02` | 60 | 60 | 0.579 | 0.424 |
| `Debugging:10_04` | 41 | stopped | scored C0 only | — |

No completed job approached the $5 cap. `10_02` is the only resource-censored pair (call cap, no workbook).

A cheaper-C1 reading is irrelevant here: the executor was not used, and capability was the gate.

---

## Artifacts

- Frozen spec: `default_harness_deterministic_execution/experiment_spec.json`
- Slice: `benchmark/slices/default-harness-deterministic-execution.json`
- Legacy mapping: `default_harness_deterministic_execution/legacy_witness_mapping.json`
- Held-out census: `default_harness_deterministic_execution/held_out_census.json`
- Frozen task list: `default_harness_deterministic_execution/frozen_task_list.json`
- Prompt/config hashes: `default_harness_deterministic_execution/prompt_config_hashes.json`
- Identity: `default_harness_deterministic_execution/provider_model_identity.json`
- Preflight: `default_harness_deterministic_execution/preflight.json`
- Official scores: `default_harness_deterministic_execution/official_scores.json`
- Paired CSV/JSON: `default_harness_deterministic_execution/paired_scores.csv`, `paired_scores.json`
- Execution ledger: `default_harness_deterministic_execution/execution_ledger.json`
- Semantic vs execution census: `default_harness_deterministic_execution/semantic_vs_execution_census.json`
- `08_03` autopsy: `default_harness_deterministic_execution/08_03_autopsy.json`
- Negative-control audit: `default_harness_deterministic_execution/negative_control_audit.json`
- Verdict: `default_harness_deterministic_execution/verdict.json`
