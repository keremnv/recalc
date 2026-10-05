# Negative / boundary catalog

Preserved with equal traceability to the positive catalog. These rows
define where benefit stops.

## Direct service but no whole-task improvement (counterexamples)

### r14 — `Debugging:08_06`, Mimo (trajectory)

Task replay 12.254 → 13.176 s (**+0.922**, +7.5%) despite 1 served block
with 4,607 reads / 3,480 cells. The served block itself saved 0.258 s
(0.614 → 0.356); the other 25 blocks regressed +1.180 s (reference-path
mass + wrapper residuals). Direct-base share: 5.0%. Lesson: substantial
service at a 5% share cannot move the task.

### r18 — `Financial_Model:07_01`, Mimo (trajectory)

Task replay 39.132 → 41.958 s (**+2.826**, +7.2%) with 1 served block
(48 reads). The served block saved 1.545 s (1.891 → 0.346); the other 41
blocks (XML surgery, LO waits, reference Python) regressed +4.371 s.
Direct-base share: 4.8%. Lesson: a large task dominated by non-certified
work swamps a real local win.

Task-sum mirrors: `Debugging:08_06` +0.922, `Financial_Model:07_01`
+2.826 (single-trajectory tasks).

Boundary principle: **direct compatibility is not enough; enough costly
work must fall inside the direct path.** Winners' direct-base shares:
r01 21.3%, r06 15.8%. Losers': r14 5.0%, r18 4.8%. No calibrated
threshold is claimed (4 served trajectories cannot set one).

## Admitted but zero direct service

- Tier 1: all 8 `DIRECT_WITH_FALLBACK` blocks (7 controlled + 1 curated)
  served 0 loads / 0 reads (`missing_stale_corrupt_artifact`). Admission
  rate (17/136) must never be presented as applicability.
- R3: no zero-service admission occurred (the one fallback row served
  1 load before falling back; delta +0.001 s noise).

## No useful direct service

- 14 of 18 Tier 1 trajectories (all 9 curated + r02/r03/r04/r05/r16):
  deltas −0.087 … +0.986 s, all unattributable wrapper tax / noise.
- 9 of 30 R3 workloads (reference-routed throughout).
- 8 of 12 Tier 1 task sums (both Template tasks + all 6 curated).

## Cold / unsupported / write-heavy (no performance claim justified)

- R3 cold check: median ON−OFF −0.049 s (no cold benefit); FM:08_02 pair
  +1.29/+1.32 s cold (artifact-build economics, documented, not a
  regression). First-touch/cold runs carry no speedup claim.
- Writes were never served in any study (contract excludes mutation);
  write-heavy phases carry no claim.
- Unsupported/dynamic semantics fail closed by design (Tier 1 blockers:
  mixed read/write, dynamic uncertainty, escape, `data_only`, rich
  objects); no claim attaches to them.

## Population results showing no aggregate benefit

- Tier 1 full: 122.82 → 125.27 s (+2.5 s).
- Tier 1 SB2 controlled subset: 112.754 → 114.410 s (+1.656 s).
- Tier 1 curated subset: 10.066 → 10.864 s (+0.798 s).
- R3 is the opposite pole (102.26 → 21.51 s mechanism effect) and must
  always appear with its distribution context, never as a universal.
