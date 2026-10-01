# Edit Plan probe artifacts and reproduction

Implementation: `edit_plan.py`. It contains no evaluator access or model calls.
The runtime uses SQLite read-only and the installed `jsonschema` package
(validated with 4.26.0). Exact grammar: `SCHEMA`; model documentation:
`edit_plan_contract.md`.

Experiment orchestration: `edit_plan_probe.py`. Evaluator-only report:
`report_edit_plan_probe.py`. Output directory:
`benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/edit-plan-composition-probe/`.

Commands, in order for a fresh output directory:

```sh
python benchmark/edit_plan_probe.py phase-a
python benchmark/edit_plan_probe.py freeze
python benchmark/edit_plan_probe.py phase-b
python benchmark/edit_plan_probe.py select-downstream
python benchmark/edit_plan_probe.py downstream
python benchmark/edit_plan_probe.py score
python benchmark/report_edit_plan_probe.py
```

`phase-b` and `downstream` make paid GLM calls; `score` and the report are
mechanical. `score` runs the normal benchmark evaluator over the bounded partial
workbooks in `scoring/` and needs LibreOffice.
The run is already frozen: do not regenerate or overwrite its primary artifacts.
Completed task/compiler/session checkpoints are reused, not retried. The original
18-task population is copied byte-semantically into the artifact directory.

The model guard accepts only exact `z-ai/glm-5.3-flash` through the existing
OpenRouter path. There is no fallback or critique/repair call. A plan rejected
by validation is not partly expanded or executed. The report's expression-only
diagnostic is explicitly evaluator-only and must not be used as a repaired plan.

Phase A proves compact target-set membership witnesses, not program homogeneity
or obligation routing. Downstream output workbooks are bounded partial outputs;
their benchmark scores do not estimate complete-task model performance.

Known frozen interface limitations are recorded in the full report: optional
source metadata rejects text-anchor IDs; temporal-coordinate and grounding-period
IDs are distinct. Do not silently change those rules and mix results into this run.

Separately, the actuation writer is not score-neutral: an openpyxl load/save with
zero applied writes changes 07_03's regression accuracy from 1.0 to 0.9841 under
the official refresh, while the pristine input through the same refresh scores
clean. Treat sub-1.0 regression accuracy on this suite as partly a writer
artifact until that is fixed. `actuation_audit.json` records the per-task diff.

Verification:

```sh
python -m pytest -q tests/test_edit_plan.py tests/test_formula_verifier.py tests/test_workbook_spine_sqlite.py
```


## Replication probe (three harness fixes)

`edit_plan_replication.py` reruns the same 18 tasks with a byte-identical plan
prompt, the primary run's Task IR reused verbatim, and only three fixes:

1. `edit_plan.py` gained an `id_contract` argument. `V1` is the frozen contract
   the primary run validated against and reproduces it exactly on all 15 stored
   plans; `V2` accepts every closed-world identity namespace grounding exposes
   (text anchors, rows, columns, workbook, and period ids resolved per axis).
2. `end_to_end_composition_probe.SYNTHESIS_SYSTEM` gives the synthesis call its
   own system prompt. `run_target` still defaults to the old behaviour, so the
   primary run's protocol is unchanged unless a caller opts in.
3. `xlsx_cell_writer.py` replaces the openpyxl load/save round trip. A zero-write
   round trip is byte-identical to the input.

`writer_neutrality_gate.py` is a blocking precondition: it writes zero cells over
the whole population and requires regression = 1.0 on every task before any model
spend is authorised. It passed 18/18.

`edit_plan_revalidate.py` is a zero-model-call diagnostic that replays the frozen
primary responses under `V2`. It never repairs or executes a plan.

```sh
python benchmark/edit_plan_revalidate.py          # free, no model calls
python benchmark/writer_neutrality_gate.py        # blocking gate
python benchmark/edit_plan_replication.py freeze
python benchmark/edit_plan_replication.py phase-b
python benchmark/edit_plan_replication.py downstream
python benchmark/edit_plan_replication.py score
python benchmark/report_edit_plan_replication.py
```

`EDIT_PLAN_DOWNSTREAM_WORKERS` sets downstream concurrency (default 2). It is an
execution-environment concession only: this host OOM-killed the run at two
workers, and it changes wall time, never any prompt or limit.

The 3M downstream input-token cap fired after 11 of 24 selected sessions, because
one session consumed 60% of the budget: the monotone working set is re-serialised
into every retrieval prompt, so cost scales with working-set size times call
count. A per-session cap and working-set deltas are the next fixes; both change
downstream behaviour, so neither belongs in this replication.

## Downstream replay: delta working-set state and a per-session bound

`edit_plan_downstream_replay.py` generates no plans. It reuses the frozen
replication's Edit Plans and its 24 selected target sessions verbatim and reruns
only the downstream half, holding model, targets, obligations, grounding,
bootstrap facts, SQL semantics, the 8-query maximum, the synthesis prompt, the
writer and the scoring path fixed. Two predeclared changes:

* **Delta state.** The monotone working set stays logically complete inside the
  harness and is never truncated. It is no longer re-sent every turn: each turn
  carries a handle, exact per-kind counts, and `NEW_SINCE_LAST_TURN`. The
  retrieval prompt states that earlier identities still exist and can be
  re-materialised by querying their ID. Passing no handle reproduces the old
  full serialisation byte for byte, which a test asserts.
* **Per-session bound.** 400,000 measured provider input tokens, about 3x the
  frozen run's median session. Exceeding it appends an explicit
  `SESSION_RESOURCE_LIMIT` record and stops further retrieval; it never drops
  context silently, and the session still takes its synthesis turn. The bound is
  checked against tokens already spent, so a session can overshoot by at most
  one call.

```sh
python benchmark/edit_plan_downstream_replay.py freeze
python benchmark/edit_plan_downstream_replay.py run     # actuates on completion
python benchmark/edit_plan_downstream_replay.py score
python benchmark/report_edit_plan_replay.py
```

The freeze records content hashes of the three prompts as well as file hashes,
because the prompts are the experiment variables.

Two further measurement defects were found during the replay and are corrected
post hoc over stored raw responses rather than in the frozen harness:

* `max_tokens` is shared between reasoning and content, so a reasoning-heavy
  synthesis turn can spend the whole 2,200-token budget and return empty text.
  That is an output-budget truncation, not a malformed answer; it is labelled
  `TRUNCATED_NO_CONTENT`. The frozen replication has the same artifact.
* `extract_json_object` spans the first `{` to the last `}`, so a model that
  emits a correct answer and then repeats it verbatim is scored unparseable.
  `report_edit_plan_replay.posthoc_parse` decodes every top-level object and
  recovers one only when the repeats agree; disagreeing objects stay
  unparseable, because choosing between them would be a semantic repair.

## Measurement repairs (defects 5 and 6)

Both were found during the replay, corrected post hoc over stored responses so the
frozen runs kept their published numbers, and only then repaired in the harness.
They are measurement repairs, not architecture changes.

* **Defect 6, duplicate emission.** `task_obligation_compile.extract_json_object`
  took the span from the first `{` to the last `}`, so a model that emitted a
  valid answer and then repeated it verbatim was scored unparseable. It now
  decodes every top-level object and returns one **only when the repeats agree**;
  disagreeing objects still fail, because choosing between two different answers
  would be a semantic repair rather than a parse. This function is shared by at
  least six probes. On the replay the defect suppressed a real end-to-end
  success: 07_03 scored 0.0 with the answer discarded and 0.75 with it recovered,
  regression 1.0 in both.
* **Defect 5, output-budget truncation.** `max_tokens` is shared between
  reasoning and content, so a reasoning-heavy synthesis turn could spend the
  whole 2,200-token budget and return an empty body, which was then read as a
  bad answer. Retrieval and synthesis now have separate budgets
  (`RETRIEVAL_MAX_TOKENS`, `SYNTHESIS_MAX_TOKENS`), and an empty body at full
  budget is recorded as `synthesis_truncated` with failure class
  `TRUNCATED_NO_CONTENT` rather than being inferred later.

The pre-repair reader is pinned as `report_edit_plan_replay.frozen_extract_json_object`
and used for the "before" side of every historical comparison, so repairing the
live parser cannot quietly erase the evidence of what it used to discard.

Repairing these changes the hashes recorded in the replication and replay
`freeze.json` files. Those runs are complete and their artifacts final; the
repaired harness is for the next probe, and `check_freeze` failing on them is the
intended signal, not a regression.

```sh
python benchmark/posthoc_parser_sweep.py     # free: sweeps every stored response
```
