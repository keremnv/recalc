# Batch-Write Helper A/B Report (`write_cells` / `write_formulas`)

Terminal experiment for the mutation-helper branch. C0 (earned surface:
transparent runtime + ordinary Python/openpyxl + periods/search/inspect) vs C1
(C0 + optional `write_cells(mapping, workbook=...)` /
`write_formulas(mapping, workbook=...)`). 10 tasks x n=1 x 2 arms = 20 runs,
plus 3 discordant pairs repeated once (6 runs). Total: 26 runs, ~$0.91 added
spend ($2.12 -> $3.03 cumulative).

Population was frozen mechanically from
`mutation_authoring_audit/source_effect_reconciliation.json`: rows with a
confirmed explicit address->content batch idiom + `SOURCE_AND_EFFECT_AGREE` +
EARLY/PARTIAL boundary — all 4 formula-batch tasks + EARLY value-batch
round-robin across families to n=10 (FM 08_01, 11_01; Debugging 02_01, 05_08,
06_07; Template 03_03, 05_02, 10_01, 15_01, 16_01). Identity audit PASS
(system/tools/model/sampling/input identical; intended differences only:
batch note paragraph + extended shim, C1 only).

## 1. Capability gate: HELPER_CAPABILITY_PRESERVED

r1: 7/10 pairs concordant (Financial_Model:08_01 bit-identical scores;
15_01, 16_01 identical; 05_08, 06_07, 11_01 jointly failing). 3 discordant
pairs repeated once: Debugging:02_01 and Template:05_02 discordances vanished
(both arms NO_SUBMIT in r2 — run noise); Template:03_03 C1 shortfall repeated
(C0 0.808 mod / C1 fail in r2).

Crucially, the helper was invoked **zero times in all 13 C1 runs** (telemetry
+ full transcripts agree; the r2 03_03 C1 run stalled after 2 views without
writing any code at all). No C1-side gap is attributable to helper *use*; the
03_03 residual sits inside demonstrated task variance (its own C0 arm varies
0.106 -> 0.808 modification across reps). No `BATCH_HELPER_CAPABILITY_LOSS`.

## 2. Adoption: zero

| signal | result |
|---|---|
| runs invoking helper | 0 / 13 C1 runs |
| `write_cells` / `write_formulas` calls | 0 / 0 |
| assistant mentions of either helper | 0 |
| shim reads | 1 (FM_11_01, read then ignored) |
| C1 runs hand-rolling dict-apply loops instead | 5 / 10 r1 runs |

The bypass evidence is direct, not an artifact of discoverability: on the
very tasks selected for batching, agents wrote the exact replaceable pattern
by hand. Template_15_01_C1 built a 20-entry formula dict `f={...}` plus
`for a,v in f.items(): ws[a]=v` — a two-line equivalent of `write_formulas`
— with the helper one import away. Agents consider the module (one C1 run
used `lx_helpers.search`) and still author their own loops.

## 3. Replacement / authoring work removed: none

No adopted calls -> 0 bytes / 0 LOC / 0 assignments removed. Arm-level
authoring totals differ (C0 78.0k vs C1 60.5k mutation-Python bytes) but with
zero adoption this is trajectory variance (stalls/truncations), not a helper
effect — and it is directionally confounded, so no efficiency claim is made
in either direction. Whole-task tokens (-1.1%) and cost (-0.3%) sit in noise
and do not exceed what the ~4.8% source ceiling would allow; there is no
mechanism for them anyway.

## 4. Semantic preservation / runtime fidelity: vacuous (no calls)

Every specified check (explicit targets, explicit content, no expansion,
declared-effects == delta-effects) has an empty extension. The implementation
itself was unit-tested (`/tmp/batch_test.py`, all pass): exact-map
application, per-address value/formula type recording, loud failure on empty
maps / missing sheets / missing workbook path. Design note: `workbook=` is
**required** — a silent default could have clobbered `input.xlsx`, a semantic
hazard incompatible with "compress already-decided edits". Helper writes are
plain `ws[addr] = content` assignments, indistinguishable to the transparent
runtime from hand-authored code (telemetry excepted).

## 5. Required answers

1. Adopted? No — 0 invocations in 13 C1 runs.
2. On how many tasks? 0 of 10.
3. Capability preserved? Yes — no helper-attributable effect possible.
4. Explicit agent-supplied maps? Vacuous (no calls); implementation enforces it.
5. Expansion/reinterpretation? Never observed; implementation forbids it.
6. Source removed? 0 bytes — nothing adopted.
7. `write_cells` earned? No.
8. `write_formulas` earned? No — including on all 4 formula-selected tasks.
9. Token/cost beyond ceiling? No (-1.1% / -0.3%, noise, no mechanism).
10. Should either remain model-facing? No.
11. Branch closed? Yes.
12. Next cost center? Post-mutation verification / repair / reopen loops.

## 6. Verdict: `BATCH_HELPER_NO_GAIN`

Neither helper earned model-facing surface. Do not expose them; do not
iterate into fill/style/translation/dependency variants (already failed or
unsupported). The mutation-helper branch is now closed. Artifacts:
`batch_write_helper_ab/` (`spec.json`, `population.json`,
`identity_manifest.json`, `capability_scores.json`,
`capability_scores_r2.json`, `helper_usage.jsonl`,
`replacement_analysis.jsonl` (empty), `authoring_work.json`,
`runtime_fidelity.jsonl` (empty), `semantic_preservation.jsonl` (empty),
`efficiency_metrics.json`, `failure_inventory.json`, `helper_verdicts.json`,
`verdict.json`); implementation `benchmark/mutation_helpers/batch.py`;
driver `benchmark/ab_batch.py`; scorer `benchmark/ab_batch_score.py`.

```text
WHAT WAS ADOPTED
Nothing. Zero invocations of write_cells/write_formulas in 13 C1 runs;
one shim read followed by non-use; agents hand-rolled the equivalent loops.

WHAT WORK WAS ACTUALLY REMOVED
None. 0 bytes, 0 LOC, 0 assignments. Arm totals differ only by run noise.

CAPABILITY EFFECT
None attributable to the helper (no contact). 2/3 r1 discordances vanished
on repeat; the 03_03 residual sits inside 8x task variance. Gate: preserved.

WHAT SURVIVES
Ordinary Python/openpyxl + transparent runtime + search/periods/inspect.
No mutation helper earns model-facing surface.

WHAT IS NOW CLOSED
The entire mutation-helper branch: batch writes, fills, translation, style
builders, and any richer mutation API iteration.

NEXT LARGEST DETERMINISTIC COST CENTER
Post-mutation verification / repair / reopen loops.

SINGLE NEXT EXPERIMENT
Which mechanical facts does the agent repeatedly rediscover after writing,
and can the runtime return those facts directly without semantic judgment?
```
