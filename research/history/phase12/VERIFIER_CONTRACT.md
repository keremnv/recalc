# Verifier contract — Phase 12 post-edit verification block v1

Research-only. Pure function of run artifacts. No gold, no scorer, no
benchmark keys, no future messages.

## Inputs

- `input_path`: pre-edit workbook (bytes frozen at run start).
- `candidate_path`: current candidate output workbook (bytes frozen at the
  submit boundary).
- `recalc_fn`: LibreOffice headless recalc producing evaluated workbooks
  (timeout-bounded; failure → `VERIFIER_UNAVAILABLE`, never a clean bill).
- `config`: this document's frozen thresholds (see VERIFIER_VERSION.json).

## Outputs (machine-readable `VerificationReport`)

```json
{
  "verifier_version": "1.0.0+<sha>",
  "positive": true,
  "signals": {
    "ERR": {"items": [{"cell": "Forecast!J23", "error": "#REF!"}], "count": 3,
            "sheets": 1, "types": {"#REF!": 3}, "changed_overlap": 3},
    "UNIF": {"items": [{"cell": "...", "pattern": "row-pattern"}], "count": 1},
    "REF": {"items": [{"formula": "...", "blank": "..."}], "count": 0},
    "CHG": {"changed_cells": 14, "sheets": 2, "regions": ["Forecast!J20:L25"]}
  },
  "dep_context": [{"for": "Forecast!J23", "fed_by": ["..."], "feeds": ["..."]}],
  "model_block": "<rendered text or null when negative>",
  "positive_families": ["ERR", "UNIF"]
}
```

## Signal contracts

- ERR: cell is error-valued in recalculated candidate AND NOT error-valued
  in recalculated input. Both sides recalculated (comparability). Type +
  location preserved.
- UNIF: cell's formula fingerprint differs from its row/column family while
  the family matched in input; post-edit break not present pre-edit; passes
  rewrite filter (see UNIFORMITY_REWRITE_FILTER.md).
- REF: formula-referenced cell blank in candidate but populated in input
  (became-blank), or reference chain structurally broken by the edit.
  Static pre-existing blanks never reported.
- CHG: counts + region rollup of value/formula presence changes. Context,
  not a warning. CHG-alone triggers a block ONLY under the broad-footprint
  rule (≥150 changed cells OR ≥5 sheets touched); otherwise accessory.

## Positivity

Block shown iff ERR>0 OR UNIF>0 OR REF>0 OR broad-CHG rule fires.
Otherwise `model_block` is null → no intervention (no congratulatory text).

## Failure semantics

Any recalc/verifier exception → `{"positive": null,
"status": "VERIFIER_UNAVAILABLE"}`. The experiment submits normally with
the failure recorded. Never fabricate clean or dirty.

## Mechanical truth standard

Each item must describe a state transition that actually occurred between
the two artifacts. Validated on frozen Phase-11 fixtures before live use;
any BUG/UNSOUND item stops the experiment.
