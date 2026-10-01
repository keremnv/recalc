# Phase 13 — Program Synthesis

Causal (not chronological) map of where the loss boundary moved and why.

```text
raw workbook access
    │  expensive loads / repeated scans dominate cost
    ▼
read-cost bottleneck
    │  → solved mechanically, productized (rc2 narrow direct reads;
    │     exact on earned surface, tail economics narrow)
    ▼
agent context / derivation
    │  → context compression FALSIFIED (timeouts, no gain)
    │  → Track C projection FALSIFIED (no safe cut)
    │  → persistent token state FALSIFIED (salience, not mechanism)
    │  → structural facts REAL but not decision-bearing
    │     (family generic; output-role "missed but useless";
    │      dependency ≠ intent; temporal accessory-only)
    ▼
compiled planning / authority
    │  → FALSIFIED across the board (IR, edit plans, scheduler,
    │     closure, program groups, SQL surface, fingerprint authority,
    │     mutation IR, batch writers at ZERO adoption)
    ▼
post-edit verification
    │  → behaviorally POTENT, mechanism WRONG (Ph12 D-demote:
    │     100% benign findings; effect was recalc prompting)
    ▼
evaluation/cache state
    │  → REAL in research endpoints (P2: 46 strong recoveries),
    │     NOT a broad archived-baseline correction (P1: 0)
    │  → recalc-fair policy earned going forward
    ▼
remaining unexplained behavior (this census)
       tight regime:  L8 no-submit/budget death (70% of Pop A)
       loose regime:  small-residual reasoning errors (P1 mod median 0.93)
       both regimes:  no coherent unclosed mechanical cluster
```

## Which boundaries moved and why

1. **Access → product**: Candidate A+A1 narrowed to an exact
   primitive surface and shipped as rc2 reads. The boundary moved
   because exactness was proven (51/51 traces), not because speed
   was universal.
2. **Context → closed**: every attempt to outsmart the transcript
   (compress, project, persist, elide) either failed to preserve
   outcomes or saved nothing attributable. The boundary moved by
   falsification.
3. **Authority → closed**: agents ignore offered authority
   structures (0/13 batch-helper adoption is the cleanest
   bypass ever measured) and do as well without them. The
   boundary moved by demonstrated indifference.
4. **Verification → demoted**: the strongest candidate diagnostic
   bundle changed behavior without diagnosing anything. The
   boundary moved by mechanism decomposition (RC_C reproduces).
5. **Cache → policy**: the strongest confound in program history
   was bounded, not universalized: it moves research endpoints,
   not the archived baseline. The boundary moved by stratification
   (P1 vs P2).
6. **Remaining → the model**: after all of the above, what is left
   is agents that (a) under tight budgets inspect without acting,
   and (b) under loose budgets reason slightly wrongly about
   signs, scales, rows, and bugs — with the deciding evidence
   already in context. No deterministic fact, helper, plan, or
   check earns a new abstraction against this residue.

## The program's three durable lessons

1. **Missingness is not value.** (Output-role archetype; Ph11.)
2. **Behavioral potency is not diagnostic value.** (Ph12.)
3. **Score movement is not mechanism proof until the cache channel
   is closed.** (Ph12R.)

## Phase-13 addition

4. **Budget death is not mechanism evidence.** Tight-regime
   no-submit measures the budget, not a missing primitive — the
   mechanizable slice was already tested (Stage B) without
   arm-level effect, and the loose regime completes the same
   families.
