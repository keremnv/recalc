# GLM structural projection discriminator

Date: 2026-09-16  
Mode: mechanism / target-selection only  
Primary witness: `Financial_Model:05_01` O7  
Model: `z-ai/glm-5.3-flash`, reasoning `high`  
Verdict: **`STRUCTURAL_PROJECTION_MIXED`**

Same evidence packets as the Spark probe. Only the model identity changed. O6 was not run: the O7 verdict was not `NO_HEADROOM_ON_O7`.

---

## Answers

1. **Did CONTROL have headroom?** Yes, partial. CONTROL was exact on 2/4 repeats, not the ≥3/4 saturation bar. Misses were the parent header row `O27:DI27`, not the period extent.

2. **Did direct compiled structure change GLM's target decision?** Yes, on two pairs.

3. **Was the change correct?** Not stably. One pair improved (CONTROL `O27:DI27` → TREATMENT `O29:DI31`). One pair reversed (CONTROL `O29:DI31` → TREATMENT `O32:DI32`). Repeat 1 was wrong on both arms. Repeat 3 was exact on both.

4. **Was it repeatable?** No.

5. **Was any movement from the structured relation rather than extra raw facts?** Yes, the packet contrast is still isolated. CONTROL and TREATMENT shared one hashed raw-fact packet. TREATMENT added only the compiled member-run / temporal-axis block. GLM's errors stayed on the period axis `O:DI` and wandered among nearby rows (27 vs 29–31 vs 32).

6. **Does this preserve a model-facing compiled-context thesis?** It does not cash out. GLM had O7 headroom that Spark did not, and compiled structure moved the decision both toward and away from gold. That is mixed decision value, not a demonstrated gain.

---

## Paired O7 target sets

Gold is `Workings Cost Sheet!O29:DI31` (297 cells). Period extent was correct on every call.

| repeat | order | CONTROL | TREATMENT |
| ---: | --- | --- | --- |
| 1 | C→T | `O27:DI27` (Total Fund Raised parent row) | `O32:DI32` (Total Fund Size - Cumulative) |
| 2 | T→C | `O27:DI27` | exact `O29:DI31` |
| 3 | C→T | exact `O29:DI31` | exact `O29:DI31` |
| 4 | T→C | exact `O29:DI31` | `O32:DI32` |

Versus Spark on the same packets: Spark CONTROL was already exact 4/4, so that family never got a treatment test. GLM CONTROL was exact only 2/4, which is why this contrast is actually informative — and why the mixed result matters.

Identity: declared `z-ai/glm-5.3-flash`, request `openrouter/z-ai/glm-5.3-flash`, wire `z-ai/glm-5.3-flash`, temperature 0, top_p 1, reasoning high, all eight `response_model` values clean. Artifacts: `structural_projection_discriminator_glm/`.
