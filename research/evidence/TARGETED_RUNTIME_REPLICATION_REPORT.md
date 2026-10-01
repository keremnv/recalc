# Stage A: Targeted Capability Replication — Report

Question: are the three prior H1-only pre-mutation stalls reproducibly
associated with the transparent-runtime arm, or ordinary trajectory variance?

**Verdict: RUNTIME_CAPABILITY_PRESERVATION_SUPPORTED.**

## Design

6 tasks (discordant: Template:01_02, Template:01_07, Debugging:02_06;
sentinels: Financial_Model:01_01, Financial_Model:13_05, Template:06_12),
n=2 per task per arm (user-capped from frozen n=5; reps 1–2 retained, 3–5
never run — recorded in spec.json), 24 live runs. Arm-neutral shared workdir
per task: model-visible paths identical across arms. Identity audit before
inference: system/instance/tool/model/sampling/request-field/workdir/input
hashes equal, PASS with zero differences. Treatment code (h1_wrap) executes
only after a bash call completes; pre-first-bash divergence cannot be
runtime-caused. No early stopping (stopped only by user n=2 directive).

## Repetition table (official evaluator)

| Task | H0 r1 mod/reg | H0 r2 | H1 r1 | H1 r2 |
|---|---|---|---|---|
| Template:01_02 | .77/.996 | .15/.886 | .40/1.0 | .06/1.0 |
| Template:01_07 | stall | stall | .42/.970 | stall |
| Debugging:02_06 | 0/.898 | stall | stall | stall |
| Financial_Model:01_01 | .0074/.8500 | .0074/.8501 | .0074/.8501 | .0074/.8501 |
| Financial_Model:13_05 | .0268/.8483 | .0268/.8483 | .0268/.8483 | .0268/.8483 |
| Template:06_12 | stall | .57/1.0 | 0/1.0 | 0/1.0 |

## Primary statistic

P(no output before mutation | discordant tasks): H0 = 3/6 = 0.50,
H1 = 3/6 = 0.50 — exactly equal. Overall stalls: H0 4/12, H1 3/12.
Prior H1-only stalls did not replicate as H1-associated: 01_02 H1 completed
2/2; 01_07 H0 stalled 2/2 while H1 completed 1/2; 02_06 stalls hit both arms.

## Completed-pair alignment

FM sentinels bit-identical across all 8 reps. 01_02 scores overlap within
wide task variance (H0 .77/.15, H1 .40/.06 — variance dominates arm). 06_12
shows task variance, not arm effect (H0 r2 mod .57 is the outlier in either
direction). Zero exacts both arms (consistent with Stage-1 difficulty).

## Causal boundary

14 H1 mutation telemetry records, 0 runtime failures, 0 validation failures.
H1 stall runs (3): two never executed any treatment code (pure view/text
event sequences); one ran the wrapper only over no-change snapshots
(zero mutations, zero telemetry records, byte-identical passthrough).
Combined with the passing identity audit: no systematic arm difference
exists before runtime activation, and no runtime-caused workbook failure
appears anywhere.

## Failure inventory

No CAPTURE/DELTA/VALIDATION/OPAQUE/COMMIT/SERIALIZATION failures. All 7
stalls (4 H0, 3 H1) boundary MODEL_BEHAVIOR_DRIFT (pre-mutation inspection
or text-only loops). LO cached-value witness remains open and uncounted
(soffice unrunnable here).

## Interpretation

All SUPPORTED criteria hold: stalls do not concentrate in H1 (exactly tied
on discordant tasks, H0-higher overall); completion overlaps; completed
scores aligned; zero runtime failures; no pre-activation arm difference.
Stage B is unlocked.
