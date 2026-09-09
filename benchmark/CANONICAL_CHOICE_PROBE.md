# Canonical program choice probe

Phase C removed the harness's repeated asking and left exactly one stochastic
decision per ProgramGroup: which program should it run? This probe changes only
that decision's interface, and separates two things earlier phases could not
tell apart — recovering a program the workbook already contains, and
synthesizing one it does not.

Everything up to and including deterministic translation is frozen.

## Reproduce

```bash
PY=/home/kerem/miniconda3/bin/python

# Phase A: mechanical availability, no model calls
$PY benchmark/program_candidate_preflight.py
$PY benchmark/program_candidate_preflight.py autopsy

# freeze the runtime candidate mechanism and the population
$PY benchmark/canonical_choice_select.py

# Phase B: A0 free-form canonical synthesis vs A1 candidate-first choice
systemd-run --user --unit=phased --property=MemoryMax=6G \
  --property=MemorySwapMax=0 --property=Nice=15 \
  $PY benchmark/canonical_choice_probe.py

# score, then report
$PY benchmark/canonical_choice_reparse.py
$PY benchmark/canonical_choice_score.py
systemd-run --user --unit=phasedscore --property=MemoryMax=6G \
  --property=MemorySwapMax=0 --property=Nice=15 \
  $PY benchmark/canonical_choice_score.py workbooks
$PY benchmark/canonical_choice_report.py
```

Outputs land in `benchmark-runs/mechanical/canonical-choice-probe/`, with
`CANONICAL_CHOICE_REPORT.md` as the readable artefact.

## Invariants

Covered by `tests/test_canonical_choice.py` unless noted.

1. **Every candidate is a real workbook formula**, translated to the canonical
   cell by the existing translation. Candidates are never composed.
2. **The list leaks nothing.** No correctness, no rank, no recommendation, and
   ordering is by formula text so position carries no signal.
3. **A selection is executed verbatim.** The harness substitutes the stored
   translated formula and ignores any text the model writes beside it.
4. **Invented candidate ids are refused**, never resolved to a near match.
5. **Gold never reaches runtime.** It scores availability after the candidate
   sets exist, and it chose the runtime mechanism only through published
   aggregates (§9), never per group.
6. **Both arms share one retrieval session.** A1 does not query; it rebuilds
   A0's synthesis input from A0's stored working set. The 8-query policy is not
   merely unchanged, it is the same eight queries.
7. **One model call per ProgramGroup in both arms.** Per-cell synthesis is not
   reintroduced; translation supplies every other member.
8. **Translation is untouched** — the Phase C implementation, unmodified.
9. **Nothing is written outside the group's authorised members.**
10. **Architectural claims survive value-only scoring.** The evaluator's
    error-value formula fallback may not carry a delta; §14 of the report shows
    where it would have.
11. **Each probe owns its own output tree.** Writing variants into a previous
    probe's directory silently produced a perfect, meaningless tie once; the
    builder is local for that reason.
