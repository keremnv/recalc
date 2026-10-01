# Live Transparent-Runtime A/B — Report

First live capability-preservation experiment for the transparent workbook
transaction architecture. H0: default coding-agent scaffold → ordinary
Python/openpyxl → existing mutation path → submit. H1: identical scaffold,
surface, prompts, model, sampling, and budgets → transparent workbook
transaction underneath → WorkbookDelta → mechanical validate/preserve/commit →
submit. The runtime is the only treatment variable. No other architectural
feature was added.

**Verdict: TRANSPARENT_RUNTIME_MIXED** (`live_transparent_runtime_ab/verdict.json`).
Conversions exact, FM stratum perfectly preserved, zero runtime failures — but
3/9 pairs show H1-no-output from pre-mutation model stalls, so a global
preservation claim is not earned at n=1. No systematic runtime failure class
was introduced. This report does not force a positive verdict.

## 1. Population, identity, execution

9 frozen tasks (3 each Financial_Model / Template / Debugging; Visualization
excluded; soffice-dependent tasks excluded by the static grep rule:
Financial_Model:08_01, Template:03_03, Template:16_06). Model
`openrouter/z-ai/glm-5.3-flash` both arms, temperature 0.0, top_p 1.0, tools
bash/view_xlsx/submit, prompts loaded byte-identical from
`benchmark/sweagent/spreadsheet-control.yaml` at runtime. 18 matched live
pairs (n=1 per task per arm), $0.48 total spend vs $25 cap. Per-task call
limit 40 and $0.25 instance cap apply identically to both arms (set by user
directive; lineage parser defaults of 10/$0.03 were tried, truncated a healthy
trajectory, and reverted).

Environment deviation (identical both arms, documented): the SWE-agent/docker
runner cannot execute here (docker daemon unreachable), so both arms ran on a
local runner implementing the same prompt/tool/budget contract; official
scoring used the unmodified evaluator with the LO refresh skipped
(`--no-refresh` escape hatch), since soffice cannot execute in this sandbox.

## 2. Paired capability (official evaluator only)

| Task | H0 exact/mod/reg | H1 exact/mod/reg | Δ |
|---|---|---|---|
| Financial_Model:01_01 | 0 / .0074 / .8500 | 0 / .0074 / .8501 | tie |
| Financial_Model:02_01 | 0 / 0 / 1.0 | 0 / 0 / 1.0 | tie |
| Financial_Model:13_05 | 0 / .0268 / .8483 | 0 / .0268 / .8483 | tie |
| Template:01_02 | 0 / .5577 / .9737 | no output | H1 loss (stall) |
| Template:01_07 | 0 / .5579 / .9070 | no output | H1 loss (stall) |
| Template:06_12 | 0 / 0 / 1.0 | 0 / 0 / 1.0 | tie |
| Debugging:02_06 | 0 / 0 / .9824 | no output | H1 loss (stall) |
| Debugging:04_01 | no output | no output | tie (difficulty) |
| Debugging:05_02 | no output | no output | tie (difficulty) |

Zero exacts in either arm (hard tasks; parity, not level, is the question).
Where both arms produced output, scores are identical to 4 decimals and edit
volumes match (cells-changed H1−H0: +4/0/0/0 — no under-editing).

## 3. Gate outcome (predeclared rule applied as written)

- Exact conversions both directions: PASS (7/7 H0 outputs round-trip
  part-exact; every H1 delta replays to its committed output part-exact).
- Paired modification deltas: PASS (no H1 under-editing).
- Paired regression deltas: MIXED (6 ties; 3 negatives, all H1-no-output).
- Zero-output (submitted-with-missing): 0 vs 0 PASS; no-output overall 5 vs 2.
- Runtime-specific failures: PASS (zero; no task flipped by the runtime).

## 4. Required answers

1. **Capability preserved?** Partially: yes on all completed pairs (FM stratum
   bit-identical scores), no global claim — verdict MIXED.
2. **New systematic failure class?** No. Zero capture/delta/validation/opaque/
   commit/serialization failures across all H1 telemetry (5 mutations, 0
   runtime failures). The only H1 losses are pre-mutation model stalls.
3. **Faithful commits?** Yes: every H1 committed workbook is byte-identical to
   the Python-produced state (hash-verified); every delta replays part-exact.
4. **Behavior perturbed?** No systematic perturbation observed. Category
   profiles diverge per task as expected under stochastic sampling at n=1;
   the wrapper has no causal path to pre-mutation behavior (it acts only
   after bash calls; stalled runs never reached bash).
5. **Capture/runtime-caused failures?** None. All 3 paired losses boundary
   MODEL_BEHAVIOR_DRIFT; 2 further mutual failures are task difficulty.
6. **LO witness?** Specified, NOT_RUN: Financial_Model:08_01 turns 42–46
   cached-value injection requires executable LibreOffice. Not an H1 failure.
7. **Earned as production foundation?** Not yet on live evidence alone: the
   static capture study (38/38, 113 mutators) plus exact live conversions earn
   a larger-n rerun, not a production decision. The next run should use n≥3
   per cell to separate stochastic stalls from systematic effects.
8. **Single next intervention?** Repeated-workbook-inspection efficiency study
   (the largest deterministic work center: H1 runs averaged ~14 view calls);
   designed separately, capability-preserving, optional Python-native helpers
   vs ordinary scanning. Not implemented here.

## Artifacts (`live_transparent_runtime_ab/`)

`spec.json`, `population.json`, `identity_manifest.json`,
`capability_gate.json`, `paired_scores.json`, `verdict.json`,
`runtime_fidelity.jsonl`, `behavior_metrics.json`, `efficiency_metrics.json`,
`lo_witness.json`, `failure_inventory.json`, `runs/` (18 run dirs with
run_record.json, trajectory.jsonl, transcript.jsonl).
Harness: `benchmark/ab_local_runner.py`, `benchmark/ab_score.py`,
`benchmark/ab_aggregate.py`, `benchmark/transparent_runtime/`,
`tests/test_transparent_runtime.py` (7 passed).
