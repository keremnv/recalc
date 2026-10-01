# Output-role planner live probe

Date: 2026-09-14
Mode: paired planner-only A/B; no retrieval, synthesis, scheduling, writes, LibreOffice, or scoring
Verdict: **`OUTPUT_ROLE_INTEGRATION_CASHES_OUT`**

## Result

The control and treatment used the archived O6 planner context. Treatment added only the five accepted output-role endpoints and their deterministic path provenance. The paired provider status, parse status, and expanded authority are reported separately below.

## Exact evidence delta

- Control context SHA-256: `afab05664692c75edbac860994df5f62af757f0ccada94f57f5c51d2a77597f1`
- Treatment context SHA-256: `c39d82e7c8b844a235a6594e5f75c60f0f4334125500e629d9d70042b4384d16`
- New endpoint IDs: `["cell:s00:r43:c7", "cell:s00:r44:c7", "cell:s00:r45:c7", "cell:s00:r43:c9", "cell:s00:r44:c9"]`
- Non-output-role context equal: `True`
- Target candidates: `24 → 29`

The complete context delta is in `output_role_planner_rerun_context_diff.json`; the request-body comparison is in `output_role_planner_rerun_request_diff.json`. The only request component changed is `messages[1].content`.

## Frozen model calls

Model: `z-ai/glm-5.3-flash`; reasoning `max`; temperature `0.0`; top-p `1.0`; max tokens `65536`.
Prompt SHA-256: `3d486f0e3d5f8c027ddcb3116e8b7ae9dd896a1736d33cfec3f88d0929460004`.

| arm | provider attempted | provider success | failure | parse valid | finish | call count | cost USD |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| CONTROL | True | True | `None` | True | `stop` | 1 | 0.005553525 |
| TREATMENT | True | True | `None` | True | `stop` | 1 | 0.0015584625 |

Raw request/response ledgers are retained in `output_role_planner_rerun_request_response_ledger.json` and each arm's `raw_request.json`, `raw_response.json`, and `calls/001_edit_plan.json`.

## Returned plans and expanded authority

### CONTROL

Returned operations:
```json
[
  {
    "operation_id": "op1",
    "obligation_id": "O6",
    "operation_kind": "SET_FORMULA",
    "target_set": {
      "kind": "UNION",
      "sets": [
        {
          "kind": "CELL",
          "cell_id": "cell:s00:r39:c6"
        },
        {
          "kind": "CELL",
          "cell_id": "cell:s00:r39:c8"
        }
      ]
    },
    "occupancy_filter": null,
    "source_relation": {
      "entity_ids": [
        "cell:s00:r39:c2",
        "cell:s00:r22:c6",
        "cell:s00:r22:c8"
      ]
    }
  }
]
```

Expansion status: `VALID_PLAN`
Expanded operation count: `1`
Expanded target forms: `[{"kind": "UNION", "sets": [{"kind": "CELL", "cell_id": "cell:s00:r39:c6"}, {"kind": "CELL", "cell_id": "cell:s00:r39:c8"}]}]`
Authority (2 cells): `["Dashboard!F39", "Dashboard!H39"]`

### TREATMENT

Returned operations:
```json
[
  {
    "operation_id": "op1",
    "obligation_id": "O6",
    "operation_kind": "SET_FORMULA",
    "target_set": {
      "kind": "UNION",
      "sets": [
        {
          "kind": "RECTANGLE",
          "sheet_id": "sheet:s00",
          "r1": 43,
          "c1": 7,
          "r2": 45,
          "c2": 7
        },
        {
          "kind": "RECTANGLE",
          "sheet_id": "sheet:s00",
          "r1": 43,
          "c1": 9,
          "r2": 44,
          "c2": 9
        }
      ]
    },
    "occupancy_filter": null,
    "source_relation": {
      "entity_ids": [
        "cell:s00:r22:c6",
        "cell:s00:r22:c8",
        "cell:s00:r39:c2",
        "cell:s00:r42:c7",
        "cell:s00:r42:c9",
        "cell:s00:r43:c7",
        "cell:s00:r44:c7",
        "cell:s00:r45:c7",
        "cell:s00:r43:c9",
        "cell:s00:r44:c9"
      ]
    }
  }
]
```

Expansion status: `VALID_PLAN`
Expanded operation count: `1`
Expanded target forms: `[{"kind": "UNION", "sets": [{"kind": "RECTANGLE", "sheet_id": "sheet:s00", "r1": 43, "c1": 7, "r2": 45, "c2": 7}, {"kind": "RECTANGLE", "sheet_id": "sheet:s00", "r1": 43, "c1": 9, "r2": 44, "c2": 9}]}]`
Authority (5 cells): `["Dashboard!G43", "Dashboard!G44", "Dashboard!G45", "Dashboard!I43", "Dashboard!I44"]`

## Authority comparison

Gold target cells: `["Dashboard!G43", "Dashboard!G44", "Dashboard!G45", "Dashboard!I43", "Dashboard!I44"]`

| arm | authority | recall | precision | FP count | FN count |
| --- | ---: | ---: | ---: | ---: | ---: |
| CONTROL | 2 | 0.0 | 0.0 | 2 | 5 |
| TREATMENT | 5 | 1.0 | 1.0 | 0 | 0 |

- Control-only cells: `["Dashboard!F39", "Dashboard!H39"]`
- Treatment-only cells: `["Dashboard!G43", "Dashboard!G44", "Dashboard!G45", "Dashboard!I43", "Dashboard!I44"]`
- Shared cells: `[]`
- CONTROL false positives: `["Dashboard!F39", "Dashboard!H39"]`
- CONTROL false negatives: `["Dashboard!G43", "Dashboard!G44", "Dashboard!G45", "Dashboard!I43", "Dashboard!I44"]`
- TREATMENT false positives: `[]`
- TREATMENT false negatives: `[]`
- The same comparison is machine-readable in `output_role_planner_rerun_authority_comparison.json` / `output_role_planner_rerun_authority_comparison.csv`.

## Safety and role-evidence checks

- First-Tranche counterfactual endpoints in treatment authority: `[]`
- Ticket Size-derived endpoints in treatment authority: `[]`
- Rejected direct/adjacent dependency endpoints in treatment authority: `[]`
- Output endpoints introduced: `["Dashboard!G43", "Dashboard!G44", "Dashboard!G45", "Dashboard!I43", "Dashboard!I44"]`
- Treatment source-relation use: `True`
- Treatment cited new endpoints: `["cell:s00:r43:c7", "cell:s00:r43:c9", "cell:s00:r44:c7", "cell:s00:r44:c9", "cell:s00:r45:c7"]`

The member restriction was held fixed. No First-Tranche path was added, and G16/G17 were not aliased to the F22/H22 row-22 occurrence. Dependency-connected cells were not exposed as treatment targets beyond the five accepted endpoints.

## Causal interpretation

`OUTPUT_ROLE_INTEGRATION_CASHES_OUT`. This result, if provider-successful, establishes only whether this deterministic composition is planner-useful for `Financial_Model:05_01 O6`; it does not establish a general output-role ontology or justify runtime integration across the benchmark.

## Smallest next experiment

Keep runtime grounding unchanged and run the smallest static cross-task test of this exact structural family before considering runtime integration.

## Artifacts

- `output_role_planner_rerun_authority_comparison.json` / `output_role_planner_rerun_authority_comparison.csv`
- `output_role_planner_rerun_request_response_ledger.json`
- `output_role_planner_rerun_request_diff.json`
- `output_role_planner_rerun_context_diff.json`
- `output_role_planner_live_probe_rerun/`
