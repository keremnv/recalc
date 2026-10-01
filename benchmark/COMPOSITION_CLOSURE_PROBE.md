# Composition-closure probe — how to reproduce and extend

## What is frozen, and where

| artifact | file |
|---|---|
| instrumentation, generation 1 (what Phase A and Phase B ran on) | `benchmark-runs/mechanical/instrumentation-freeze/freeze.json` |
| instrumentation, generation 2 (adds `TRUNCATED_AT_BUDGET`) | `.../instrumentation-freeze/freeze.v2.json` |
| Phase A rules, witnesses, ledger, verdict | `.../composition-closure-probe/phase_a_report.json` |
| Phase B unit selection | `.../execution-unit-probe/units.json` |
| Phase B freeze (component hashes, limits, arm definitions) | `.../execution-unit-probe/freeze.json` |
| Phase B sessions, one per authorised cell, with raw bodies | `.../execution-unit-probe/sessions/*.json` |
| Phase B units, closure membership, member formulas | `.../execution-unit-probe/units/*.json` |
| continuation arm (censored members only) | `.../execution-unit-probe/continuation_freeze.json` |
| the report | `.../execution-unit-probe/PHASE_B_REPORT.md` |

The freeze is **generational**: a repair earned by an experiment is written as a
new generation rather than over the old one, so a completed run stays verifiable
against the instrument it actually ran on.

## Commands

```
python benchmark/instrumentation_freeze.py          # build the current generation
python benchmark/composition_closure_probe.py       # Phase A, no model calls
python benchmark/composition_closure_report.py      # Phase A verdict
python benchmark/execution_unit_probe.py select     # choose 8-12 units
python benchmark/execution_unit_probe.py freeze     # pin them
python benchmark/execution_unit_probe.py run        # B0/B1 sessions
python benchmark/execution_unit_continuation.py freeze && ... run
python benchmark/execution_unit_score.py            # build, recalculate, score both arms
python benchmark/execution_unit_closure_analysis.py # closure precision decomposition
python benchmark/execution_unit_autopsy.py          # 07_03, mechanical
python benchmark/scorer_fallback_audit.py           # error-value fallback accounting
python benchmark/phase_a_value_only_recheck.py      # value-only rescoring of Phase A
python benchmark/execution_unit_report.py           # render the report
```

## Invariants a change must not break

1. **Closure never widens authority.** Members are the intersection of the
   closure with the cells the generated Edit Plan already authorises. A cell is
   never editable because it is a dependency.
2. **Closure is seeded by the model's own proposal**, never by gold. Gold appears
   only in after-the-fact diagnostics.
3. **The arms differ in one thing.** B1 reuses B0's seed session byte for byte.
4. **Resource bounds are explicit.** A censored session is recorded as
   `RESOURCE_CENSORED_NOT_RUN`; context is never dropped silently.
5. **Non-model failures are never model-quality failures.**
   `TRUNCATED_NO_CONTENT`, `TRUNCATED_AT_BUDGET`, `MODEL_ACCESS_FAILURE`,
   `SESSION_RESOURCE_LIMIT`.
6. **Raw request and response bodies, usage, parser result and truncation status
   are retained for every call.**
7. **The official scorer is never modified.** Its error-value fallback is
   reported beside a value-only number instead.
8. **Quarantine is declared before results.** A task whose own gold edit set does
   not reproduce gold cannot carry a causal claim.
