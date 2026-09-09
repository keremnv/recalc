# ProgramGroup execution probe (Phase C)

Tests one hypothesis and nothing else: when an ExecutionUnit contains
mechanically homologous formula targets, synthesize the program once and
translate it deterministically across the unit, instead of asking the model to
rediscover the same program at every cell.

Execution closure is **not** under test here. C1 is frozen exactly as Phase B
left it: input-side, OFFSET-aware, seeded by the model's own proposed formula
and intersected with the cells the generated Edit Plan authorises.

## Reproduce

```bash
PY=/home/kerem/miniconda3/bin/python

# 1. preflight — mechanical ceiling, no model calls at all
$PY benchmark/program_group_preflight.py
$PY benchmark/program_group_preflight.py --sweep      # 1/2/3 witness lines

# 2. freeze the population before any member is generated
$PY benchmark/program_group_select.py

# 3. run both arms (long; keep it under a memory cap)
systemd-run --user --unit=phasec --property=MemoryMax=6G \
  --property=MemorySwapMax=0 --property=Nice=15 \
  $PY benchmark/program_group_probe.py run

# 4. build, recalculate and score SEED / P0 / P1
systemd-run --user --unit=phasecscore --property=MemoryMax=6G \
  --property=MemorySwapMax=0 --property=Nice=15 \
  $PY benchmark/program_group_score.py

# 5. post-run diagnostics, then the report
$PY benchmark/program_group_posthoc.py
$PY benchmark/program_group_exactness.py
$PY benchmark/program_group_cost.py
$PY benchmark/program_group_report.py
```

Outputs land in `benchmark-runs/mechanical/program-group-probe/`, with
`PHASE_C_REPORT.md` as the readable artefact.

## Invariants

These are the properties the probe must not lose. Most are covered by
`tests/test_program_group.py`.

1. **Region membership never implies one program.** A ProgramGroup exists only
   when the *input* workbook demonstrates the repetition at the group's own
   coordinates. No semantic finance roles, no gold fingerprints.
2. **Gold never reaches runtime.** It is used to measure a ceiling and to score,
   never to form, trim or seed a group, and never to choose a canonical member.
3. **`ProgramGroup.members ⊆ Edit-Plan-authorised members`.** Translation grants
   no edit authority the plan did not already grant.
4. **The canonical member is deterministic and evaluator-blind.** It is not the
   cell the model historically got right.
5. **P1 issues no model call P0 does not.** The canonical session *is* one of
   P0's sessions, byte for byte, which is what makes the cost claim exact rather
   than modelled.
6. **No silent fallback.** A `TRANSLATION_FAILURE` inside a group leaves the
   member empty in the primary P1 arm; it never reverts to independent
   synthesis.
7. **Members in no group are byte-identical across arms.** The treatment is
   confined to grouped members.
8. **Retrieval is frozen** at the same bootstrap, SQL contract and 8-query
   maximum. Retrieval and translation are never changed in the same experiment.
9. **Architectural claims survive value-only scoring.** The evaluator's
   error-value formula fallback may not carry a delta, and the report also
   separates exact matches from cells credited only by the 1% tolerance band.
