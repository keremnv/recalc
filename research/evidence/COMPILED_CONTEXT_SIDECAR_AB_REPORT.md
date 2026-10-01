# Compiled-context sidecar A/B

Verdict: **CONTEXT_USEFUL_BUT_ADOPTION_LIMITED**

This experiment tests Spark on the normal SpreadsheetBench coding-agent scaffold, with vs without one optional compiled-context capability. It does not test the old LibreCalc harness, the autonomous compiled treatment, Task IR, ProgramGroups, a scheduler, Spark vs GLM, or published-control superiority.

## Identity

- Declared model: `meta/muse-spark-1.3-contributor`
- Request model: `openrouter/meta/muse-spark-1.3-contributor`
- Generation: temperature 0.0, top_p 1.0, reasoning_effort unset, tool_choice auto, provider allow_fallbacks + require_parameters
- Envelope: 40 model calls / $2.50 per task (censoring boundary, not a target)
- Source identity run: `official-score-spark-1.3-contributor-fm-02_01`

## Prompt hashes

- `c0_system_sha256`: `0c36c45319b387fbdb58a3c899c1d8d0beed4d5426f0aa80422114165930b24b`
- `c1_system_sha256`: `0c36c45319b387fbdb58a3c899c1d8d0beed4d5426f0aa80422114165930b24b`
- `c0_instance_sha256`: `a659355097d0faeeff8aeb10bb728c34e40c002cda67cd439bcc99f9da9dafa9`
- `c1_instance_sha256`: `088238307584b443653efc2a8bcd83ba794288fa5126cff9238279dc9ae45f1b`
- `c0_config_sha256`: `c3cc1b506956bc73a9560716e739bfb2fb19d96477df540f3837d17c3cd53c3d`
- `c1_config_sha256`: `bdb7702fcde649ebded7690edbd94e22230e5630a37158856db6d09c53493e4a`
- `c1_tool_schema_sha256`: `1a2318955f9a4c70e60cda173d7b4e4961ccd913bec5f1ddb4c8f2c7397a17c4`
- `c0_bundles`: `['tools/submit', 'tools/view_xlsx']`
- `c1_bundles`: `['tools/submit', 'tools/view_xlsx', '../../../benchmark/sweagent/calc_query']`

## Paired official scores

| Task | Repeat | C0 mod | C1 mod | C0 reg | C1 reg | C0 exact | C1 exact | C0 usable | C1 usable | C1 used calc_query |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Financial_Model:13_05` | 1 | 0.6472 | 0.6472 | 0.9967 | 0.9967 | False | False | False | False | False |
| `Financial_Model:13_05` | 2 | 0.6472 | 0.6472 | 0.9967 | 0.9967 | False | False | False | False | False |
| `Financial_Model:13_05` | 3 | 0.6472 | 0.6472 | 0.9967 | 0.9967 | False | False | False | False | False |
| `Financial_Model:13_05` | 4 | 0.6472 | 0.6472 | 0.9967 | 0.9967 | False | False | False | False | False |
| `Financial_Model:05_01` | 1 | 0.999 | 0.0 | 0.9973 | 0.0 | False | False | True | False | True |
| `Financial_Model:02_01` | 1 | 1.0 | 1.0 | 1.0 | 1.0 | True | True | True | True | False |
| `Financial_Model:15_05` | 1 | 0.2595 | 0.0 | 1.0 | 0.0 | False | False | False | False | False |
| `Template:03_03` | 1 | 0.9574 | 0.8936 | 0.99 | 0.9867 | False | False | False | False | True |
| `Template:06_17` | 1 | 1.0 | 1.0 | 1.0 | 1.0 | True | True | True | True | True |
| `Template:16_12` | 1 | 1.0 | 0.9792 | 1.0 | 1.0 | True | False | True | False | True |
| `Debugging:01_01` | 1 | 0.8035 | 0.7973 | 0.9871 | 0.9849 | False | False | False | False | True |
| `Debugging:09_04` | 1 | 0.0 | 0.9942 | 0.0 | 0.9656 | False | False | False | False | False |
| `Debugging:10_10` | 1 | 0.0845 | 0.0787 | 0.997 | 0.9936 | False | False | False | False | False |

## Tool adoption (C1)

5/13 C1 trajectories used `calc_query`.

## Financial_Model:13_05 mechanism

| Repeat | Arm | periods queried | FY26–30 exposed | I20:M20 gold match | D20:H20 conflict | exact |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | C0 | False | False | True | False | False |
| 1 | C1 | False | False | True | False | False |
| 2 | C1 | False | False | True | False | False |
| 2 | C0 | False | False | True | False | False |
| 3 | C0 | False | False | True | False | False |
| 3 | C1 | False | False | True | False | False |
| 4 | C1 | False | False | True | False | False |
| 4 | C0 | False | False | True | False | False |

## Post-hoc opportunity audit

- `Financial_Model:13_05:C1:r1`: `AVAILABLE_NOT_QUERIED` (Regression error at Summary Valuation!E11: answer=11.3281525647495, output=11.5097743684789)
- `Financial_Model:13_05:C1:r2`: `AVAILABLE_NOT_QUERIED` (Regression error at Summary Valuation!E11: answer=11.3281525647495, output=11.5097743684789)
- `Financial_Model:13_05:C1:r3`: `AVAILABLE_NOT_QUERIED` (Regression error at Summary Valuation!E11: answer=11.3281525647495, output=11.5097743684789)
- `Financial_Model:13_05:C1:r4`: `AVAILABLE_NOT_QUERIED` (Regression error at Summary Valuation!E11: answer=11.3281525647495, output=11.5097743684789)
- `Financial_Model:05_01:C1:r1`: `PROVIDER_OR_RESOURCE_CENSORED` (output file not exist)
- `Financial_Model:15_05:C1:r1`: `PROVIDER_OR_RESOURCE_CENSORED` (output file not exist)
- `Template:03_03:C1:r1`: `QUERIED_BUT_WRONG_MODEL_CHOICE` (Regression error at Consolidation!C32: answer=None, output=630)
- `Template:16_12:C1:r1`: `QUERIED_BUT_WRONG_MODEL_CHOICE` (Modification error at Valuation!C43: answer=368442.563744589, output=None)
- `Debugging:01_01:C1:r1`: `QUERIED_BUT_WRONG_MODEL_CHOICE` (Regression error at Ex 1 - LBO!R59: answer=0, output=95.8833120588848)
- `Debugging:09_04:C1:r1`: `AVAILABLE_NOT_QUERIED` (Regression error at LBO!B35: answer=Revolver, output=Revolver)
- `Debugging:10_10:C1:r1`: `AVAILABLE_NOT_QUERIED` (Regression error at Model!D17: answer=177.359960324625, output=169.837029607725)

## Claim boundary

Causal claims are only from these fresh C0/C1 Spark pairs. Historical GLM or compiled-agent results explain task predeclaration only.

Generated at: 2026-09-16T13:55:56.905437+00:00
