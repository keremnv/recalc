# Pattern catalog — method

This directory is the gold-blind case collection for GLM 5.3 Flash on SpreadsheetBench 2.
It is not a design doc and not a punch list. Another agent should be able to continue
from `BRIEFING.md` without the originating chat.

## Identity

A case is `(run, task, first-miss address)`. `Debugging:06_09` is not a case: the 15-run
first miss is `Cover!G10` and the 297-run first miss is `Revenue Build!K26`.

## Allowed sources

- `official_scores.json` first-miss line (`error_message` is an **evaluator leak**, tagged
  `evaluator_leak: true`, not a golden)
- Input workbook neighborhood around that address
- Trajectory: inspect payload, reads, writes, compare summary, thoughts
- **Any arm's** output xlsx at the miss cell — ours, our repeats, and the control's. All
  three are the same evidence class: a produced workbook read at one already-leaked
  address. v1 allowed only ours, which is what left the catalog single-armed.
- The published accuracy scalars. `min_misses` recovers the smallest miss count consistent
  with a 4dp `modification_accuracy`; that is arithmetic on a number the evaluator prints,
  not an `answer_position` dump.
- Task instruction and input **filename** (Debugging planted class lives in the filename)

## Forbidden

- Golden workbooks, `golden_response_path`, `answer_position` dumps
- Adding tools, prompts, or inspect fields because of a case
- Quoting n=3 or n=15 exact as a result
- Treating autopsy buckets as ground truth without the v2 caveats below

## Autopsy v2

`benchmark/paired_autopsy.py` plus `benchmark/pattern_census.py`.

1. **Named** if the address is in `formula_errors.selected_cells`,
   `translation_consensus` / `short_sequence_gaps` / `deleted_row_geometry`
   `selected_candidates`, **or** `boundary_continuations.candidates`.
   Used-range alone is extent, not a name.
2. **Read** only if a read returned cells for that sheet. A failed oversize
   (`ok: false`, "covers N cells") is `read_attempted`, not `read`.
3. **Written** if a write tool’s range covers the cell.
4. **Compare then submit** as before.

v1 (the 15-run paired table in chat) counted action-range as read and ignored
boundary. Do not mix v1 buckets with this census.

## The gate (v2)

v1 collected. It could not decide, because deciding needs a comparison v1 never made.
`benchmark/catalog_gate.py` asks four questions per case, cheapest first, and the first
answer that applies ends the case:

1. **Self-stability.** Do our *own* repeat runs get that cell right sometimes? Measured
   variance on this model is exact <-> 0.9854 across repeats of one task, so a cell we win
   on repeat is variance and not a pattern. Verdict `noise`.
2. **Arm delta.** Does the control arm get that cell right? A cell both arms miss is a
   property of the model or the task and no interface change reaches it. Verdict `shared`.
   Only `induced` (control right, we wrong) and `recovered` (we right, control wrong) are
   evidence about the interface.
3. **Distance to exact.** How many misses does the task still carry? A first miss on a task
   thirty misses from exact converts nothing if fixed. Verdict `far`.
4. **Lever.** Which family would the fix belong to? Verdict `refuted-lever`.

Only `survives` earns design attention. `unjudged` means the comparison could not be made
-- almost always because no control run covers the task -- and is a **work item, not a
result**: run the control on that task.

An arm's agreement counts only when at least `--min-decided` runs actually decided the
cell. `no-output`, `no-sheet`, `no-cache` and `blank-vs-zero` are undecided and are
excluded from every count; `no-cache` exists because a workbook saved without cached
values reads as all-`None` and would otherwise manufacture agreement.

## Lever families

`lever` is a human claim on the case, and each family carries a measured prior:

| lever | meaning | measured |
|---|---|---|
| `information` | the world tells the model something true it did not know | **refuted** |
| `constraint` | the world refuses an action | untested |
| `substitution` | the world performs the decision; the model does not make it | untested |
| `selection` | the world ranks candidate outputs | untested |
| `none` | no world-side action reaches it | refuted by definition |
| `agent_scan` | *candidate, not a lever* -- the agent runs its own predicate over the whole workbook | 1 case, see below |

`agent_scan` is not one of the four families a case can be closed against; `arms.yaml`
documents it separately so the gate never assigns it by accident. It exists because
`d-02-05-d7` does not fit the other four: control finds `WACC!D7` in 2/2 runs and our
arm's read windows land next to it in 3/3 independent trajectories without ever
including it, and the plausible mechanism -- bash + openpyxl lets the model load the
whole workbook and scan every formula cell, which our interface does not expose -- is
neither telling, deciding, refusing, nor ranking. One case does not make a lever. Do not
build a tool from it; measure whether the pattern repeats before naming a fifth family.

`information` is refuted, not merely disappointing: `unrequested_write` 0.0%,
`broken_check_cell` on completion 0.2%, `region_width_extensions` 5.6%, and on the 297 the
commit gate delivered findings at 100% and 96.1% precision and converted **zero** exact.
A case whose only lever is `information` does not earn a design change, whatever its mass.

Roles live in `arms.yaml`: which stored runs count as `control`, which as `ours`, and the
prior on each lever. Add a run there rather than passing it on the command line, so the
next agent gets the same verdicts.

## Layers

| file | who edits | what |
|---|---|---|
| `METHOD.md` | rarely | this contract |
| `surface.yaml` | when a pattern is established or parked | the grid |
| `cases/*.yaml` | one per visit | facts (script) + claims (human) |
| `arms.yaml` | when a run lands | run roles and lever priors |
| `census/<run>.json` | regenerate | 297-row dump, no prose |
| `BRIEFING.md` | after surface/cases change | what the next agent reads first |

Regenerate census:

```
python benchmark/pattern_census.py glm-5.3-flash-nonvisual-297-1 \
  --json benchmark/pattern-catalog/census/glm-5.3-flash-nonvisual-297-1.json
```

Extract facts for a new visit (no claims):

```
python benchmark/pattern_catalog.py extract-facts glm-5.3-flash-nonvisual-297-1 'Debugging:01_05'
```

Validate:

```
python benchmark/pattern_catalog.py validate
```

Gate:

```
python benchmark/catalog_gate.py
python benchmark/catalog_gate.py --near 3 --min-decided 2 --json /tmp/gate.json
```

## Claims vs facts

`facts.opened_golden` must be false. Claims that used the filename plus the
`answer=` leak stay `nuance: open` until they can be decided without a golden.
`nuance` is one of `decomposable`, `task_nature`, `harness`, `open`.

`design` on a pattern is `later` or `never`. Never means do not invent a tool
for it. Later means gather is done; design is a different conversation.

`design: later` is now **subordinate to the gate**. A pattern marked `later` whose cases
all come back `noise`, `shared` or `unjudged` has not earned a design conversation; it has
earned a control run, or nothing. Do not promote a pattern past the gate by hand.

Two case fields carry the human half of the gate and start unset:

- `claims.lever` — one of the families above.
- `claims.mechanism` — the geometry shared with other cases, not the surface. Fourteen
  pattern names that resolve to two or three mechanisms will not generalise into a design.

## Stance that does not belong in a case file

- Do not rerun 297.
- Hybrid is dropped.
- GLM 5.3 Flash throughout.
- n=15 exact is noise.
- Do not add tools from these autopsies.
