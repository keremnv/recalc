# Spark structural projection discriminator

Date: 2026-09-16  
Mode: mechanism / target-selection only  
Primary witness: `Financial_Model:05_01` O7  
O7 verdict: **`NO_HEADROOM_ON_O7`**  
O6 fallback verdict: **`OUTPUT_RELATION_NO_GAIN`**

This is not an official SpreadsheetBench score. Spark's only job was to return a target cell set. No `calc_query`, Task IR, Edit Plan, scheduler, ProgramGroups, writer, LibreOffice, or official scoring.

---

## Answers

1. **Did CONTROL have headroom?** No on O7. After canonicalizing sheet identity to stable cell IDs, CONTROL was exact on 4/4 repeats (`Workings Cost Sheet!O29:DI31`, 297/297 gold cells). The O6 fallback therefore ran. O6 CONTROL did have headroom: 0/4 exact, F1 0.40, recall 1.0, precision 0.25.

2. **Did direct compiled structure change Spark's target decision?** Not on the O7 cell set. All eight O7 calls returned `O29:DI31`. TREATMENT only changed the sheet *label* (`Workings Cost Sheet` vs CONTROL's `s04` on 3/4 repeats); that is the same packet sheet identity, not a different target. On O6, CONTROL and TREATMENT returned the identical ranges on all four pairs: `Dashboard!G43:G52` and `Dashboard!I43:I52`.

3. **Was the change correct?** There was no O7 target-set change to score. On O6 the unchanged decision was partially correct: every gold cell was included (`G43`, `I43`, `G44`, `I44`, `G45`) and then over-extended through deal rows 46–52 (15 false positives, no first-tranche or Ticket Size leakage).

4. **Was it repeatable?** Yes. O7 exact 8/8 once sheet IDs are canonicalized. O6 identical over-extension 8/8.

5. **Was any benefit from a structured relation rather than extra raw facts?** O7 does not support that claim: CONTROL already had the raw labels, the four First/Second/Third runs, and the Apr-25→Jun-33 header coordinates, and it selected the gold rectangle without the compiled block. O6 CONTROL and TREATMENT shared one raw Dashboard packet; TREATMENT added the earned occurrence/output relation, including the five gold Numbers-side endpoints, and Spark still did not change its ranges. The hashed common packets and canonical diffs are in `structural_projection_discriminator/payloads/`.

6. **Does this preserve a model-facing compiled-context thesis?** It weakens it under this isolation. When query formulation and tool adoption are removed, and task-relevant compiled relations are placed directly in the observation, Spark did not use them to improve a target-selection decision that still had headroom (O6). O7 was already solved from raw workbook facts. This does not license architecture changes; it is a mechanism result on one workbook and two clauses.

---

## Frozen Spark identity

| field | value |
| --- | --- |
| declared model | `meta/muse-spark-1.3-contributor` |
| request identity (sidecar/LiteLLM) | `openrouter/meta/muse-spark-1.3-contributor` |
| OpenRouter wire model | `meta/muse-spark-1.3-contributor` |
| temperature | `0` |
| top_p | `1` |
| reasoning_effort | unset (not sent) |
| provider | `allow_fallbacks: true`, `require_parameters: true` |
| response_model (all 16 live calls) | `meta/muse-spark-1.3-contributor` with no trailing backslash |

A first eight-call attempt used the LiteLLM prefix as the OpenRouter `model` field and returned HTTP 400 (`not a valid model ID`). Those pairs were censored and archived under `structural_projection_discriminator/censored_openrouter_prefix_attempt/`. Both arms of four new pairs were rerun. That is a transport mapping, not a model swap.

---

## O7 source preflight (gold-blind)

Recompiled from `05_01_AIF_input.xlsx` before gold was loaded.

Verified Workings Cost Sheet member runs:

| parent/header | parent cell | members |
| --- | --- | --- |
| Portfolio Building MoM | B9 | B11:B13 |
| Portfolio Building Cumulative | B15 | B17:B19 |
| Ticket Size per Portfolio | B21 | B23:B25 |
| Total Fund Raised | B27 | B29:B31 |

Temporal axis T1, column orientation, same sheet: Apr-25 → `O4`, Jun-33 → `DI4`.

The TREATMENT block listed all four runs and the two period anchors. It did not name `O29:DI31`, evaluator gold, or “intended” cells. CONTROL received the same raw B-column labels and the same O4:DI4 period headers.

Gold (297 cells, rows 29–31, columns O–DI) was loaded only after payload hashes were written.

### O7 paired target-selection

| repeat | order | CONTROL | TREATMENT |
| ---: | --- | --- | --- |
| 1 | C→T | exact `O29:DI31`; sheet field `s04` | exact `O29:DI31`; sheet field `Workings Cost Sheet` |
| 2 | T→C | exact `O29:DI31`; sheet field `s04` | exact `O29:DI31`; sheet field `Workings Cost Sheet` |
| 3 | C→T | exact `O29:DI31`; sheet field `s04` | exact `O29:DI31`; sheet field `Workings Cost Sheet` |
| 4 | T→C | exact `O29:DI31`; sheet field `Workings Cost Sheet` | exact `O29:DI31`; sheet field `Workings Cost Sheet` |

`s04` is the sheet id supplied in both packets (`Workings Cost Sheet (sheet:s04)`). Canonical cell IDs treat it as the same sheet. CONTROL therefore has no O7 headroom: **`NO_HEADROOM_ON_O7`**.

---

## O6 saturation fallback

Gate: O7 CONTROL exact on ≥3/4 complete repeats. O6 is decision-only: *In the Dashboard, update Exit Multiple for second and third tranches to 2.0x for all deals.*

The already-earned header-copy / Month–Numbers / formula-extent relation was replayed on the input workbook with gold held out of the packet. TREATMENT exposed Second/Third vs excluded First identities, F22/H22 copied-header paths, Month/Numbers pairs, contiguous Month-row extents, and Numbers-side endpoints `G43:G45` and `I43:I44`. Those five endpoints are exactly the evaluator gold, which was not loaded until after O6 payloads were hashed. CONTROL received the underlying Dashboard raw cells, not those composed relations.

| repeat | usable | CONTROL exact | TREATMENT exact | recall | precision | F1 |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | yes | no | no | 1.0 | 0.25 | 0.40 |
| 2 | yes | no | no | 1.0 | 0.25 | 0.40 |
| 3 | yes | no | no | 1.0 | 0.25 | 0.40 |
| 4 | yes | no | no | 1.0 | 0.25 | 0.40 |

Both arms, all repeats: `G43:G52` and `I43:I52` (20 cells vs 5 gold). First-Tranche false selections: none. Ticket Size occurrence leakage (`G16`/`G17`): none. Direct-dependency-only false selections: none. Output occurrences `G43:G45` and `I43:I45` were included inside the over-extended block. TREATMENT cited the compiled endpoints in `evidence` and still did not stop at the formula-bearing extent.

Predeclared verdict: **`OUTPUT_RELATION_NO_GAIN`**. CONTROL had headroom; TREATMENT did not improve target selection; there were no paired reversals.

---

## Integrity cleanup (not model-facing)

1. `response_model` logging now strips a trailing backslash. Requests are unchanged. Covered by `tests/test_compiled_context_sidecar.py`.
2. A task that reaches its model-call or cost cap is `envelope_or_resource`, not `provider_or_infra`. Covered by the same tests.
3. The Docker `calc_query` wrapper still walks `Path.parents` instead of indexing `parents[5]`.
4. Wide-range `calc_query inspect` still clips at 64 cells. Recorded as an open product defect in `structural_projection_discriminator/spec.json`. This probe never called `inspect`.

No architecture, sidecar, ProgramGroup, or evidence-path change followed from the result.

---

## Artifacts

- `structural_projection_discriminator/spec.json`
- `structural_projection_discriminator/source/` — O7/O6 provenance and compiled relation text
- `structural_projection_discriminator/payloads/` — frozen CONTROL/TREATMENT bodies, hashes, canonical diffs
- `structural_projection_discriminator/ledgers/` — raw request/response per arm/repeat
- `structural_projection_discriminator/measurement/` — gold-after-freeze metrics and verdicts
- `structural_projection_discriminator/identity_audit.json`
- `tests/test_structural_projection_discriminator.py`
- `tests/test_compiled_context_sidecar.py` (integrity regressions)
