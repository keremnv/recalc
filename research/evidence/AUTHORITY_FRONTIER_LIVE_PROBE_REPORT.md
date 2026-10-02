# Authority-frontier live probe: 13_05 O1 temporal evidence

The planner-only causal bridge was run for `Financial_Model:13_05`, obligation
`O1`. It made exactly two Edit Plan provider calls: one CONTROL call using the
old local-period spine and one TREATMENT call using the repaired shared
temporal projection. Task IR, raw task, obligation, non-temporal grounding,
prompt/schema, model settings, percentage parsing, target ordering, provider
configuration and cache/workbook lineage were held fixed. Retrieval,
synthesis, scheduling, workbook writes, LibreOffice refresh and scoring were
not run.

The machine-readable source of truth is
[`authority_frontier_live_probe/report.json`](../history/authority_frontier_live_probe/report.json).
The exact serialized planner inputs are in
[`control_context.json`](../history/authority_frontier_live_probe/control_context.json),
[`treatment_context.json`](../history/authority_frontier_live_probe/treatment_context.json),
and the exact request/response ledgers are in
[`control/calls/001_edit_plan.json`](../history/authority_frontier_live_probe/control/calls/001_edit_plan.json)
and
[`treatment/calls/001_edit_plan.json`](../history/authority_frontier_live_probe/treatment/calls/001_edit_plan.json).

## Evidence intervention

The non-temporal context comparison was exact: `non_temporal_context_equal`
is `true`. The user payload hashes differ only because the `GROUNDING` value
was changed by the intended temporal intervention.

| | CONTROL | TREATMENT |
|---|---:|---:|
| period source | original local-period spine | repaired shared temporal projection |
| period-universe records | 168 | 338 |
| scope records | 3 | 8 |
| target candidates | 6 | 161 |
| model calls | 1 | 1 |

CONTROL's three scope facts are the Projection Sheet FY26, FY27 and FY28
coordinates `period:s18:r2:c10`, `period:s18:r2:c14` and
`period:s18:r2:c18`. Its six target candidates are those three header cells
and `cell:s18:r8:c10`, `cell:s18:r8:c14`, `cell:s18:r8:c18`.

TREATMENT retains those same three Projection Sheet coordinates extensionally,
with the shared temporal IDs `tcoord:s18:c:10`, `tcoord:s18:c:14` and
`tcoord:s18:c:18`, and adds the Input Sheet propagated time coordinates:

```
tcoord:s08:c:9:p   Input Sheet!I5  (2026)
tcoord:s08:c:10:p  Input Sheet!J5  (2027)
tcoord:s08:c:11:p  Input Sheet!K5  (2028)
tcoord:s08:c:12:p  Input Sheet!L5  (2029)
tcoord:s08:c:13:p  Input Sheet!M5  (2030)
```

The treatment target delta is exactly 155 added candidates and zero removed
candidates. These are the 31 existing Input Sheet rows
`7, 8, 11, 12, 13, 16, 17, 19, 20, 22, 26, 29, 32, 33, 36, 38, 45, 46,
49, 50, 52, 53, 59, 63, 67, 70, 74, 75, 76, 77, 78`, crossed with columns
`I:M` (`c9:c13`). The old six Projection Sheet candidates are also retained.
The complete sorted cell list is persisted in `evidence_delta.json`.

The treatment therefore supplies the missing workbook-side FY26–FY30 growth
target region to the planner. This is an evidence projection change, not a
new target-ranking rule.

## Planner outputs and expanded authority

Both returned plans parsed as `VALID_PLAN` and expanded successfully.

CONTROL returned:

```json
{
  "operations": [
    {
      "operation_id": "op1",
      "obligation_id": "O1",
      "operation_kind": "SET_FORMULA",
      "target_set": {"kind": "CELL", "cell_id": "cell:s08:r20:c4"},
      "source_relation": {"entity_ids": ["cell:s08:r20:c2", "cell:s08:r20:c3", "cell:s08:r11:c4", "cell:s08:r16:c8"]}
    },
    {
      "operation_id": "op2",
      "obligation_id": "O1",
      "operation_kind": "SET_FORMULA",
      "target_set": {"kind": "RECTANGLE", "sheet_id": "sheet:s08", "r1": 20, "c1": 5, "r2": 20, "c2": 8},
      "source_relation": {"entity_ids": ["cell:s08:r20:c2", "cell:s08:r20:c3", "cell:s08:r11:c5", "cell:s08:r11:c8"]}
    }
  ]
}
```

It expanded to `cell:s08:r20:c4` through `cell:s08:r20:c8` (`D20:H20`, with
`D20` supplied by `op1` and `E20:H20` by `op2`). Against the evaluator gold
set `{cell:s08:r20:c9, ..., cell:s08:r20:c13}`, this is five
false positives, five false negatives, recall `0.0` and precision `0.0`.

TREATMENT returned:

```json
{
  "operations": [
    {
      "operation_id": "op1",
      "obligation_id": "O1",
      "operation_kind": "SET_FORMULA",
      "target_set": {"kind": "CELL", "cell_id": "cell:s08:r20:c9"},
      "source_relation": {"entity_ids": ["cell:s08:r20:c2", "tcoord:s08:c:9:p"]}
    },
    {
      "operation_id": "op2",
      "obligation_id": "O1",
      "operation_kind": "SET_FORMULA",
      "target_set": {"kind": "RECTANGLE", "sheet_id": "sheet:s08", "r1": 20, "r2": 20, "c1": 10, "c2": 13},
      "source_relation": {"entity_ids": ["cell:s08:r20:c2", "tcoord:s08:c:10:p", "tcoord:s08:c:13:p"]}
    }
  ]
}
```

It expanded to exactly the five gold cells `cell:s08:r20:c9` through
`cell:s08:r20:c13`. It produced zero false positives and zero false
negatives, recall `1.0` and precision `1.0`.

| condition | authority | gold overlap | false positives | false negatives | recall | precision |
|---|---:|---:|---:|---:|---:|---:|
| CONTROL | 5 | 0 | 5 | 5 | 0.0 | 0.0 |
| TREATMENT | 5 | 5 | 0 | 0 | 1.0 | 1.0 |

## Provider and operational status

Both calls reached the provider, finished with `stop`, retained raw response
text, parsed into a plan, and had `failure_class: null`. Provider cost was
`$0.00307925135` for CONTROL and `$0.0021793653` for TREATMENT. There were
exactly two model calls and no retrieval or synthesis calls, workbook writes,
LibreOffice runs or scoring runs. Neither result is provider-censored; a
timeout or provider failure was not treated as a planner decision.

## Causal interpretation

The result is **`TEMPORAL_INTEGRATION_CASHES_OUT`**. The repaired temporal
projection added task-relevant Input Sheet FY26–FY30 evidence, the planner
selected that newly visible region, and evaluator-side authority changed from
0/5 to 5/5 recall with precision improving from 0.0 to 1.0. No treatment false
authority appeared. Because all other context keys were held equal and both
calls succeeded, the observed authority gain is attributable to the temporal
evidence intervention in this paired run.

This promotes the temporal representation from “mechanically earned” to
**demonstrated planner-useful representation for this task/obligation**. It
does not establish that temporal integration solves the frontend generally;
the known tranche/target-role, inherited-context, growth-output and implicit
table-body losses remain outside this probe.

No deterministic defect was found in the live bridge, and no code or runtime
architecture was changed as a result of this probe. The result does not justify
reopening scheduler, ProgramGroup, retrieval, synthesis, writer, scorer or
semantic verification.

## Next research boundary

The next boundary is **Task IR obligation fields and inherited context →
role-aware grounding/authority**, beginning with tranche population and
output-column/occurrence roles. The smallest useful follow-up is an
evaluator-side role contrast using the existing 05_01, 03_01, 08_01, 15_05
and 13_05 counterexamples, preserving field provenance and inclusion/
exclusion semantics. Do not add a generic scope-to-target relation until that
contrast establishes a mechanically defined relation with acceptable
false-positive behavior.
