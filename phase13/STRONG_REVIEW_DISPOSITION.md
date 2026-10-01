# Phase 13 — Gate-A Reviewer Disposition

Review: `phase13/STRONG_REVIEW_FRONTIER.md` (independent read-only
subagent; ~16 evidence claims re-verified). Every criticism below is
classified ACCEPTED / PARTIALLY ACCEPTED / REJECTED with evidence.
All ACCEPTED changes were implemented BEFORE finalizing the frontier
and verdict (§27). Raw census labels were never rewritten silently:
Pop-A edits are explicit record changes in `build_censusA.py`;
Pop-B v1→v3 rebuilds are scripted in `build_censusB.py` with the
rule change (mass-dominant score-only PRIMARY) disclosed in every
record's `first_divergence` tag ([T:...]/[S:...]).

## Q1 — renamed falsified hypothesis

**ACCEPTED.** C1 (Debugging misdiagnosis) renames (i) the Ph12
verifier, (ii) frozen formula-error feedback including timing
probes, and (iii) frozen UNIF/output-role transfer. C1 is relabeled
"DETECTION-REVIVAL VARIANT (triple rename, gated)": it may proceed
only as an explicitly-gated trial (benign ≤50% on K3, paired exact,
sham, recalc-constant, strata-separated). Class stays
MODEL-CAPABILITY; no HIGH-VALUE probe. Frontier + ledger updated.

## Q2 — misclassified cluster

**ACCEPTED** (three parts):
(a) L4 suppression: 18 records carried L5 primaries with zero L5
share. Root cause: branch-order rule (differs→L5) applied to
score-only records where earliest-divergence is inapplicable (action
order unknown). Fix: score-only records now use MASS-DOMINANT
PRIMARY (ties→L5); trajectory records keep earliest-divergence.
Result: L4-primary 1→16 runs, L4 mass 3.32→5.26. The recall<0.5
rule was dropped as subsumed.
(b) 11_01/10_02: flipped L0/L7 → L5/L0 per the taxonomy's own V1-fails
precedence (K8 hardcode-1 and E10 omission are agent-caused). 06_25
stays L0 under the new benchmark-state carve-out (residual is
pre-existing input/gold mismatch). Taxonomy + records updated.
(c) 18 zero-L5-share records: eliminated by construction (PRIMARY now
follows the dominant share; verified: zero records with empty
primary share).

## Q3 — misleading-effect confound

**ACCEPTED.** C1's confound channels (benign-rate, cache/formula-text
leakage, strata pooling) are now predeclared gates on the candidate
rather than prose warnings. C5 received the Goodhart hard-gate
(byte-level proof + no-score-rewrite + selective rule). No candidate
was promoted on confoundable grounds.

## Q4 — missed alternative explanation

**ACCEPTED** (both checks ran):
(a) Precedent-closure check (`phase13/q4_closure.py` + Q4b shape
split + magnitude sample + time-volatile sweep): 336
upstream-proven (24 edited / 312 untouched), 3,164
precedent-matched; shapes: OFFSET/array 86, named 947, plain
2,270; 22/30 exact-precedent sample at agent-scale magnitudes
(I29 sub-tolerance-cascade archetype: 0.475% upstream → 4.85%
downstream); time-volatile same-roots ZERO (exhaustive). Finding:
the same-formula interior is upstream content (family proven by
fresh caches in recalc-fair rows), unlocalized in the
named/dynamic/OFFSET channel → R5 rule (L5-upstream w/ PLAUSIBLE
cap when primary rides on it; UNSCORABLE shares UNALLOCATED).
(b) Color untouched-cell check (official comparator): 30,787
missed fixes → L5 vs 38,742 pipeline-destroyed → L6. Fix 7's
re-familying confirmed by evidence, not assumed.

## Q5 — architectural consequence

**ACCEPTED.** Only C1 (the rename) would change architecture —
precisely why it stays gated/demoted. Stated plainly in the
frontier pareto note and the verdict rationale. This reinforces
(rather than weakens) the no-probe conclusion.

## Fix list

1. Truncation (P0) — **ACCEPTED**. All 70 truncated runs rerun
   UNCAPPED (checkpointed); roots/cause/footprints rebuilt on full
   sets (109,034 mismatches → 77,340 roots); per-run reg/mod/
   official self-check fields restored; 71/71 exact validations;
   df44beb5-class inversion noise verified spurious by direct
   official-function rerun (5498/5506). All "2053/1308→117"-class
   numbers replaced.
2. Validation fields — **ACCEPTED** (71 exact + structural identity
   + direct-function spot proof; implied-total check dropped as
   rounding-unsound, documented).
3. Stale numbers — **ACCEPTED**: recalc triple (141/1/41; 142
   resolved) stated everywhere; sign-flip 368 roots (full-set);
   traj sample 19 (17 fail + 2 success); L0 cells 7/5 runs;
   runs/tasks standardized (tasks primary, runs alongside).
4. 11_01/10_02 + carve-out — **ACCEPTED** (above, Q2b). A-counts
   now L8×26 L5×5 L0×5 L7×3 L6×1; C4 recounted (3 exact + 1 near
   + 4 partial-gains; hygiene-PRIMARY only on full recovery).
5. L4 suppression — **ACCEPTED** (above, Q2a).
6. Volatility/L0 consistency — **ACCEPTED**: 5 fully-unallocated
   runs → PRIMARY UNKNOWN (now 10, all UNSCORABLE-same, each with
   best-attributed secondary); per-assessed-cell volatility/UDF
   audit ran with NEGATIVE result (zero time-volatile; 86
   OFFSET/array are deterministic dynamic refs → unlocalized
   channel, not L0); no blanket confidence cap needed (differs
   roots are cache-independent).
7. COLOR re-family — **ACCEPTED**: measured split (30,787→L5 /
   38,742→L6); tooling share re-familied L5→L6 (agent's lossy
   round-trip); REG partition carries L6 0.52; 08_04→(L6,UNALLOC),
   10_04→(L6,L5) via combined-loss PRIMARY.
8. 12_01 — **PARTIALLY ACCEPTED**: "perfect work" hedged to
   V1-exact-ambiguous (RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN);
   removed from C4 mass (never submitted); L7 PRIMARY kept with
   tightened justification (earliest-divergence at the verify-vs-
   submit choice + §33 exact match) and the L8 counterargument
   recorded in the notes. Rationale for keeping: the wall death
   is when the consequence landed, not when the run diverged.
9. C1 relabel + gates — **ACCEPTED** (above, Q1).
10. C2 split + REG partition — **ACCEPTED**: attempted (3,465) /
    never-attempted (1,043→L4) / upstream-cascade split stated;
    REG loss fully partitioned (L0 1.00 / L5 0.60 / L6 0.52 /
    UNALLOC 0.001, exact-sum).
11. C5 separation — **ACCEPTED**: C36 added to L0 set (7 cells /
    5 runs); scoreless-equivalent vs error-valued (19_05 D6/E6:
    artifact real, recovery nil) separated; selective-rule
    hard-gate added. Never sole cause, verified.
12. C3 corrections — **ACCEPTED**: "26 never-submitted + 2
    degenerate" (12_01/17_05 wrote; 04_06/08_06 are L7);
    "28.0 mass-equivalent" dropped (unscored runs carry no
    measured loss).

## What verified clean (kept as-is)

Mod-loss total 41.4766, medians (mod 0.93), recall/precision
(0.966/~1.0), P1 zero-recovery, 06_05-class byte identity,
05_08 empty-set, 16_12 ×12, 07_03 recall 0.014, FM06_01 input
defect, color-task flagging, C4/C6/C7/C8 classifications.

## Net effect on the verdict

C (MODEL CAPABILITY LIMIT) **holds** with stronger numbers:
reasoning family (L5+L4) 74% of P1 mod loss with evidence in
context; UNALLOCATED 14% (bounded, UNSCORABLE-interior); L0/L6
explained 6%/~0%; tight-regime D-mass unchanged in shape
(26 never-submit, budget artifact, Stage-B null stands). No
candidate advanced to HIGH-VALUE; Gate B not triggered.
