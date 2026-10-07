# Recalc visual assets

Front door for every presentation visual. Status is explicit: current
public evidence, secondary evidence, reproducibility inputs, or
historical/retired material.

## Current public figures

| Asset | Status | Evidence level | Consumers | Generator / source |
| --- | --- | --- | --- | --- |
| `recalc-selective-execution.svg` | current public | schematic (not measured) | README | `docs/evidence/public_visuals/` |
| `recalc-task-replay-outcomes.svg` | current public | measured task replay | README, PERFORMANCE | `docs/evidence/public_visuals/` |
| `recalc-controlled-applicability.svg` | current public | measured applicability | PERFORMANCE | `docs/evidence/public_visuals/` |
| `recalc-r3-distribution.svg` | current public | historical mechanism distribution | PERFORMANCE | `docs/evidence/public_visuals/` |

Figures A–D are the current public visual system. Measured figures are
generated deterministically from frozen evidence and carry their
comparator, population, and regime inside the image.

## Secondary public evidence

| Asset | Status | Evidence level | Consumers | Generator / source |
| --- | --- | --- | --- | --- |
| `recalc-performance-vignette.svg` | secondary public | measured read-only substep | PERFORMANCE (linked) | `docs/evidence/readme_vignette/` |

The FM:08_02 vignette is still valid: one released-product read-only
inspection substep. It is not primary task-replay evidence and stays
out of the README.

## Evidence hierarchy

The ordering below is about evidence unit and scope, not “best result
to worst result”:

1. measured task replay — primary user-level performance evidence;
2. released-product read-only substep — secondary mechanism illustration;
3. historical R3 distribution — mechanism-population evidence;
4. controlled-stratum applicability — service-incidence/generalization evidence;
5. schematic architecture — explanatory, not measured.

## Reproducibility

Sanctioned documentation generator locations (only these two):

- `docs/evidence/public_visuals/` — Figures A–D
  (`generate.py`, `manifest.json`, `README.md`).
- `docs/evidence/readme_vignette/` — FM:08_02 vignette, including the
  workbook render (`sheet_crop.png`) and frozen timing/provenance.

New public numeric figures should normally extend `public_visuals`
rather than creating a third generator framework. The vignette
generator stays separate because of its workbook-rendering and
provenance requirements.

## Historical / retired presentation assets

Preserved for provenance. Historical assets may contain superseded
wording, old comparator framing, or retired visual grammar, and should
not be quoted as current product claims — the same principle as the
research archive.

- `recalc-side-by-side.gif` — retired race GIF. Not tracked on the
  current branch and not referenced by any current doc. Survives only
  on branch `docs/readme-reader-flow` at
  `docs/assets/recalc-side-by-side.gif` (introduced in `41711f9`,
  which is not an ancestor of the current line). Do not restore it to
  the README or treat it as quantitative evidence.
- `research/history/product_presentation/` — research-era presentation
  drafts (`DIAGRAM_DRAFT.svg`, `site/*.svg`, README drafts). Referenced
  only from within that historical directory.

No bytes were duplicated into this taxonomy for archival purposes;
historical items are cited by branch/path provenance.

## Rules for new figures

Any future measured public visual should:

- derive from canonical frozen evidence;
- use a sanctioned deterministic generator (normally `public_visuals`);
- carry comparator, population, and regime inside the image;
- include accessibility metadata (`role="img"`, `<title>`, `<desc>`);
- avoid red/green winner/failure semantics;
- distinguish fallback/reference execution from failure;
- preserve the measured unit and denominator;
- link to canonical evidence and provenance.

Do not hand-edit measured SVGs or create ad-hoc chart one-offs. Every
file added to `docs/assets/` needs an explicit row in this taxonomy.
