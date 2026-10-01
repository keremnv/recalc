# Spreadsheet Agent Harness — Bottom-Up Architecture Checkpoint

**Status:** Milestone reached — architecture shape is coherent enough to freeze as a research checkpoint, but not yet complete enough for an end-to-end architecture claim.

**Date:** 2026-09-07

---

## 1. Why this is a milestone

The project began with a vague harness hypothesis:

> Better spreadsheet tools / more semantic actuation might let model intelligence express itself more effectively.

That hypothesis did not survive in its original form.

Across a sequence of causal and eliminative experiments, the project has converged on a different architecture:

> **A valuable harness moves deterministic, global, mechanically checkable work out of stochastic model reasoning, while preserving ambiguity where the workbook or task genuinely underspecifies the answer.**

The harness is not primarily a semantic oracle.

It is increasingly shaped like a **compiler + static-analysis + grounding + verification substrate** around a model.

The current evidence supports a staged system:

```text
Natural-language task
        ↓
Task compiler
        ↓
Lifted Task IR
        ↓
Workbook grounding
        ↓
Grounded obligations
        +
Persistent Workbook IR / Spine
        ↓
Task-conditioned projection
        ↓
Model resolves residual ambiguity
        ↓
Candidate workbook edit
        ↓
Hard mechanical verification
        ↓
Actuation
```

The most important milestone is not that every stage is solved.

It is that **each stage now has a distinct epistemic role**, and those roles were discovered experimentally rather than designed top-down.

---

# 2. Core architectural thesis

## 2.1 Current thesis

> **Harnesses create leverage by converting latent workbook structure and task constraints into persistent, addressable, mechanically derived facts and obligations, while leaving genuinely ambiguous intent and synthesis to the model.**

A stronger version:

> **Model proposes and resolves ambiguity; the harness compiles structure, preserves specification, constrains search, and verifies only properties it can actually establish.**

The harness should not try to “understand the spreadsheet” in a global semantic sense.

It should instead make the environment:

- mechanically addressable;
- queryable;
- provenance-preserving;
- closed-world where possible;
- loss-minimizing;
- explicit about ambiguity;
- cheap to recompute once and reuse.

---

# 3. The three major information layers

## 3.1 Task specification

The task says what transformation is requested.

The experimentally induced minimum unit is:

```text
CLAUSE_OBLIGATION
    provenance
    locus
    subject
    subject_interval?
    required_change
    scope
    source_relation?
    condition?
    result_property?
    then_after?
    occupancy_filter?
```

A task is generally a conjunction of these clause-level obligations.

The natural unit is **transformation + task-licensed constraints**, not:

- the whole task;
- a single action enum;
- a cell address;
- a finance semantic role.

Task IR is good at expressing:

- which sheet / section;
- which named object / line item;
- which periods or scope;
- calculate vs link vs hardcode vs populate;
- explicit conditions;
- explicit source relations;
- ordering / composition.

Task IR is not expected to contain:

- exact workbook addresses;
- exact precedents;
- formula structure;
- reduction extents;
- workbook-only homolog choices.

---

## 3.2 Workbook mechanical IR / grounding spine

The workbook spine is the closed mechanical world the grounder and later model may refer to.

Its purpose is not semantic interpretation.

Its purpose is to expose mechanically recoverable workbook structure as stable entities and relations.

Current strongly supported base objects include:

```text
Workbook
Sheet
Cell
Row
Column
Text anchor
Formula
Formula fingerprint / equivalence class
Point reference
Range reference
Dependency relation
Header / period evidence
Temporal coordinate
```

Important distinction:

```text
physical workbook coordinates
    sheet / row / column

+
task-addressable coordinate systems
    locus / subject / time / other mechanically recoverable dimensions
```

The spine is increasingly not just a collection of extracted facts.

It is:

```text
raw workbook
    ↓
base facts
    ↓
typed relations
    ↓
deterministic closure
    ↓
derived facts
    ↓
persistent addressable spine
```

---

## 3.3 Verification

Verification is not prediction.

The verifier asks:

> Given a proposed implementation, can the harness mechanically prove that it violates a hard property?

Hard graph checks were safe but sparse.

Empirical workbook patterns were much less safe.

Current hierarchy:

```text
HARD CONTRADICTION
    authoritative when valid

EXACT REPEATED REGULARITY
    advisory evidence, not invariant

SOFT ANALOGY
    model-facing evidence only
```

This is a major architectural boundary.

---

# 4. What has been experimentally earned

## 4.1 Formula fingerprints / structural identity

Formula strings massively obscure repeated computation.

Location-relative fingerprints revealed strong internal regularity:

- ~3.95M formula cells;
- ~79.6k within-workbook fingerprint classes;
- ~49.6× compression;
- ~99.36% of formula cells in non-singleton classes;
- raw formula strings barely compress.

This established:

> **Formula-level mechanical representation exists and is highly compressible.**

It also killed the current `<REF>` shape abstraction as too lossy:

- many distinct fingerprints collapse into one generic shape;
- mechanical distinctions matter downstream.

---

## 4.2 Formula equivalence solves a bounded WHAT problem

For Financial_Model blank→formula gold edits, a substantial fraction of correct formulas instantiate a formula fingerprint already present in the input workbook.

This means equivalence classes can help answer:

> **What computation might belong here?**

But they do not answer:

> **Which blank should contain computation?**

That WHAT / WHERE distinction became foundational.

---

## 4.3 Generic occupancy does not solve WHERE

Mechanical completion rules and occupancy topology produced huge overfill.

Local formula agreement is structurally real but mostly applies to intentional blanks.

Key lesson:

> **Structural plausibility is not action authorization.**

---

## 4.4 Typed dependency structure contains real candidate-generation signal

A blank referenced by formulas is much more likely to be a true missing target than an arbitrary blank.

But generic dependency was too lossy.

Point references and range membership behave very differently.

This earned typed relations such as:

```text
POINT_REFERENCE
RANGE_REFERENCE
```

and rejected a generic `DEPENDS_ON` as the only dependency type.

Dependency is useful primarily for:

> **candidate generation / search-space reduction**

not direct repair authorization.

---

## 4.5 More explicit relation exposure can make the model worse

When point-dependency information was explicitly shown to GLM, false positives increased.

The model correctly used the information but overgeneralized:

```text
consumed by formulas
    ⇒
probably missing formula
```

That result established:

> **A true relation can still be harmful if the representation omits the distinctions required to interpret it.**

---

## 4.6 Liveness / continuation / block extent did not collapse into scalar semantics

Attempts to derive liveness, continuation, frontier, and block extent vs role extent produced heterogeneous or inverted relationships.

This rejected the idea that a small number of intuitive semantic annotations would solve WHERE.

Repeated pattern:

> When mechanically distinct situations are compressed into one intuitive semantic variable, the data splits them again.

---

## 4.7 Descriptive schema did not solve operational formula intent

Labels, row text, headers, and period information were often extractable.

But they did not distinguish gold precedents from wrong model precedents in the hard ORACLE cases.

So:

```text
descriptive schema
    ≠
operational semantics
```

This prevented premature construction of a finance ontology.

---

## 4.8 Operational dependence roles also did not solve precedent selection

Use-def slots, reduction structure, cycle checks, and local templates were tested.

Important conflict:

```text
wrong formula
    matches local historical template

gold formula
    violates that template
    but avoids a hard cycle
```

This exposed:

```text
predictive analogy
    ≠
falsifying constraint
```

and led directly to the verifier branch.

---

# 5. Verification result

## 5.1 Hard checks

Hard checks such as cycle / SCC expansion produced:

- perfect observed precision in the retrospective census;
- zero correct/equivalent rejection;
- extremely low wrong-formula coverage (~0.3%).

Conclusion:

> **Hard mechanical falsification is real, but sparse.**

It is a guardrail, not the main capability engine.

## 5.2 Empirical contracts are not invariants

Repeated peer contracts increased wrong rejection but also rejected many correct formulas.

Critical observation:

> A correct task often requires intentionally breaking the input workbook’s existing pattern.

Therefore:

```text
existing workbook regularity
    ≠
output invariant
```

Repeated patterns remain useful as model evidence, but not as hard authority.

---

# 6. Task-obligation IR discovery

A task→input→golden census was used to induce the minimum task representation.

The shape generalized across held-out project families without adding a V2 field.

Fields that survived because concrete counterexamples required them:

- provenance;
- locus;
- subject;
- subject interval;
- required change;
- scope;
- source relation;
- condition;
- result property;
- explicit ordering (`then_after`);
- occupancy filter.

Fields that were **not earned**:

- finance role ontology;
- target address;
- blanket cell preservation;
- “complete the model” as an obligation;
- single operation enum.

> **The IR shape was induced by counterexamples rather than authored from intuition.**

---

# 7. Task parsing result

One-shot task→V1 compilation is viable but not reliable enough yet.

Held-out full task-spec preservation:

- GLM: ~0.52
- GPT-5.6: ~0.56

Critical requirement recall:

- GLM: ~0.89
- GPT-5.6: ~0.93

The main failures are:

- omitted constraints;
- wrong attachment;
- clause decomposition on long tasks;
- result_property vs source_relation confusion.

Notably:

- workbook-like invention was essentially zero;
- known diagnostic tasks preserved task-side facts;
- failure rises sharply with number of obligations.

Conclusion:

> **V1 is usable; one-shot compilation is model-limited, especially on long compositional tasks.**

This does not justify redesigning V1.

---

# 8. Grounding spine result

The grounding experiment introduced a closed-world rule:

> The model may only bind to workbook entities that were mechanically compiled into the spine.

This allowed failures to be decomposed into:

```text
SPINE_MISSING
RETRIEVAL_MISSING
RESOLUTION_MISS
```

Results:

- golden cell entity coverage: 1.0;
- locus retrieval: ~0.99;
- subject retrieval: ~0.97;
- retrieval of already-represented period facts: ~0.99;
- entity invention: 0 by construction.

The major failure was not retrieval.

It was:

> **the workbook spine did not expose the temporal coordinate system densely enough.**

---

# 9. Temporal coordinate milestone

## 9.1 One-cell period facts were the wrong abstraction

V1 only attached time when a column directly contained a parseable period cell.

But workbook time often lives in:

- EOMONTH / EDATE chains;
- FY tokens;
- copied date headers;
- row-oriented calendars;
- cross-sheet date references.

This earned:

```text
TEMPORAL_COORDINATE
    axis
    normalized temporal components
    evidence cells
    provenance
```

rather than:

```text
one header cell = one period fact
```

## 9.2 Local V2 improved only modestly

Same-sheet formula-derived dates and FY normalization improved held-out temporal coverage only from roughly 0.25 to 0.31.

A shallow provenance walker found only ~21% of the remaining coordinates within six hops.

## 9.3 Depth-sensitivity changed the conclusion

A depth-sensitivity preflight held the relation vocabulary fixed:

```text
E1 DIRECT_REFERENCE
E2 EOMONTH / EDATE date transform
E3 SAFE_DATE_OFFSET
```

Only traversal depth changed.

Result:

- 609 / 615 previous DEPTH_LIMIT coordinates eventually reached a valid temporal seed;
- 99% recovery of that class;
- median successful depth ~41;
- p90 ~71;
- max ~85;
- no new seed types required;
- no new semantic relation types required;
- safe closure was computationally modest.

Counterfactual held-out temporal coverage rose to roughly **0.934** from roughly **0.460** under shallow traversal.

This is one of the strongest positive findings in the project.

---

# 10. Architectural implication of temporal closure

The result is broader than time.

It demonstrates that:

> **Mechanically implied properties may be globally present in the workbook program even when they are not locally observable.**

Therefore the spine should support:

```text
BASE FACTS
    ↓
TYPED RELATIONS
    ↓
DETERMINISTIC CLOSURE
    ↓
DERIVED FACTS
```

A raw fact being represented is not enough.

The harness should materialize mechanically implied facts that a model would otherwise have to rediscover through long reasoning traces.

This strongly supports the broader harness thesis.

---

# 11. Rejected / eliminated primary hypotheses

The following should no longer be treated as leading explanations:

1. Semantic actuation API is intrinsically better than bash/openpyxl.
2. Formula regularity does not exist.
3. Simply exposing better representation makes the model use it well.
4. Local formula agreement can safely authorize blank completion.
5. Formula occupancy topology solves target selection.
6. Generic dependency is a direct repair rule.
7. Explicit dependency evidence necessarily improves model decisions.
8. Scalar liveness solves WHERE.
9. Universal continuation/frontier semantics solve WHERE.
10. Block extent vs role extent is a canonical abstraction.
11. Descriptive labels/schema disambiguate operational precedents.
12. Semantic edge roles are the missing relation layer.
13. Repeated workbook patterns are safe output contracts.
14. Short local temporal provenance is sufficient.

These eliminations are as important as the positive findings.

---

# 12. Current architecture

## 12.1 Stage A — Task compilation

```text
Natural-language task
    ↓
Lifted Task IR
```

Responsibility:

- preserve requested transformations;
- preserve constraints and provenance;
- do not infer workbook-only implementation.

Status: **PARTIAL / MODEL_LIMITED**

## 12.2 Stage B — Workbook compilation

```text
Workbook
    ↓
Persistent mechanical IR / spine
```

Responsibility:

- enumerate workbook entities;
- preserve formula/reference distinctions;
- expose task-addressable coordinate systems;
- retain provenance;
- avoid hidden top-k / ranking losses.

Status: **SUPPORTED, still incomplete**

## 12.3 Stage C — Deterministic closure

```text
Base facts + typed relations
    ↓
Derived properties
```

Current earned example:

```text
temporal seed
    +
direct references
    +
date transforms
    ↓
propagated temporal coordinate
```

Responsibility:

- perform global deterministic computations once;
- materialize properties models should not repeatedly infer.

Status: **STRONGLY SUPPORTED by temporal provenance experiment**

## 12.4 Stage D — Conservative task-conditioned projection

```text
Lifted Task IR
    +
Workbook spine
    ↓
closed candidate world
```

Responsibility:

- retrieve all mechanically plausible entities;
- no hidden top-k;
- compress via canonical representation, not deletion;
- preserve ambiguity.

Status: **SUPPORTED for locus / subject; temporal scope awaiting closure implementation**

## 12.5 Stage E — Model resolution / synthesis

```text
Grounded obligations
    +
mechanical candidates
    ↓
model chooses implementation
```

Responsibility:

- resolve residual ambiguity;
- synthesize formulas;
- use task semantics and workbook evidence;
- not reconstruct deterministic global structure from scratch.

Status: **NOT YET CLEANLY TESTED**

## 12.6 Stage F — Verification

```text
candidate edit
    ↓
hard mechanical checks
```

Responsibility:

- reject mechanically impossible / forbidden candidates;
- preserve correct/equivalent formulas;
- avoid treating empirical regularities as invariants.

Status: **SUPPORTED but low coverage**

## 12.7 Stage G — Actuation

Perform the selected workbook transformation and verify workbook state.

Status: existing mechanisms appear sufficient for research; no evidence that richer actuation is the main capability bottleneck.

---

# 13. Architecture diagram

```text
                  ┌──────────────────────┐
                  │  Natural-language    │
                  │        task          │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    Task compiler     │
                  │ specification-pres.  │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   Lifted Task IR     │
                  │ clause obligations   │
                  └──────────┬───────────┘
                             │
                             │
Workbook                     │
   │                         │
   ▼                         │
┌──────────────────┐         │
│ Mechanical       │         │
│ workbook compile │         │
└────────┬─────────┘         │
         │                   │
         ▼                   │
┌──────────────────┐         │
│ Base facts +     │         │
│ typed relations  │         │
└────────┬─────────┘         │
         │                   │
         ▼                   │
┌──────────────────┐         │
│ Deterministic    │         │
│ closure / static │         │
│ analysis         │         │
└────────┬─────────┘         │
         │                   │
         ▼                   │
┌──────────────────┐         │
│ Persistent       │◄────────┘
│ Workbook Spine   │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│ Task-conditioned conservative│
│ projection / grounding       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Closed candidate world       │
│ ambiguity explicitly retained│
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Model resolution / synthesis │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Candidate workbook edit      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Hard verifier                │
│ sparse mechanical checks     │
└──────────────┬───────────────┘
               │
               ▼
          Workbook actuation
```

---

# 14. Design principles now supported by evidence

## 14.1 Recover structure; do not invent intent

> **Harness: recover structure. Model: infer meaning.**

## 14.2 Abstract computation, not choice

> **Do not abstract away choices from the model. Abstract away computation the model should not have to repeat.**

Temporal closure is now a concrete example.

## 14.3 Preserve distinctions until proven irrelevant

Lossy compression repeatedly caused failure:

- `<REF>` shape vs fingerprints;
- generic dependency vs point/range;
- scalar liveness vs heterogeneous structural states;
- shallow provenance vs closure.

## 14.4 Facts, regularities, and invariants are different epistemic objects

```text
mechanical fact
    ≠
empirical pattern
    ≠
hard obligation
```

Do not collapse them into one confidence score.

## 14.5 Grounding should preserve ambiguity

Correct output may be a candidate set rather than one guessed entity.

Premature resolution is a real error class.

## 14.6 Closed-world IDs prevent environmental invention

Once the workbook spine is compiled, model outputs should refer only to mechanically existing entity IDs.

## 14.7 Completeness before ranking

Avoid:

```text
workbook
→ heuristic
→ rank
→ cap
→ model
```

Prefer:

```text
workbook
→ complete deterministic compilation
→ persistent IR
→ conservative task-conditioned projection
→ model
```

Compress by canonicalization and indexing, not by deleting potentially relevant entities.

## 14.8 Derived facts need provenance

Derived temporal coordinates should retain the paths that established them.

Derived facts should never become opaque annotations.

---

# 15. Relation to established architecture families

The emerging architecture resembles a hybrid of:

## Compiler architecture

- parsing;
- IR;
- name resolution;
- progressive lowering;
- static analysis;
- dataflow closure.

## AI planning

- lifted task representation;
- grounding against environment entities;
- partial-order constraints.

## Formal refinement

- abstract specification;
- progressively concrete implementation;
- proof obligations at boundaries.

## Static analysis / abstract interpretation

- deterministic mechanical properties;
- sound-but-incomplete checking;
- closure over relations.

## CEGAR-like methodology

The research method itself has been:

```text
coarse representation
    ↓
counterexample
    ↓
add only required distinction
    ↓
retest
```

This has repeatedly prevented speculative ontology growth.

---

# 16. Is the architecture complete?

## Short answer

**The skeleton is now coherent enough to freeze. The architecture is not yet empirically complete.**

We have evidence-backed answers for:

```text
task representation
workbook representation
typed mechanical relations
deterministic closure
candidate projection
verification role
ambiguity preservation
```

We do **not** yet have strong evidence for the most important remaining stage:

```text
grounded candidate world
    ↓
model resolution / synthesis
```

Nor have we yet shown that the composed architecture improves end-to-end benchmark performance.

Therefore this checkpoint should be treated as:

> **Architecture v0 — experimentally induced skeleton**

not a final production architecture.

---

# 17. What remains open

## 17.1 Implement temporal closure

The depth-sensitivity result has earned this.

Implement frozen E1–E3 provenance closure and materialize propagated `TEMPORAL_COORDINATE` facts.

Then rerun the existing deterministic grounding experiment unchanged.

Primary checks:

- actual temporal coverage;
- scope retention;
- strict target retention;
- candidate compression.

Do not change retrieval.

## 17.2 Separate task-side scope anaphora

A separate class remains:

```text
"same timeframe"
"following years"
"the corresponding period"
```

Do not mix this with workbook temporal recovery.

First census whether these collapse into a small task-reference relation such as:

```text
SAME_SCOPE_AS(Ox)
```

Only add such a relation if earned by repeated counterexamples.

## 17.3 Closed-world resolver experiment

Only after deterministic grounding packets have high retention.

Question:

> Given all relevant candidates in context, can the model safely narrow ambiguity without dropping the correct entity?

Primary metric:

```text
false elimination rate
```

not unique-resolution rate.

## 17.4 Formula synthesis under grounded obligations

Once grounding is safe enough:

```text
task obligation
+
grounded candidate entities
+
workbook IR
    ↓
model formula proposal
```

This is the true remaining WHAT problem.

## 17.5 End-to-end composition

Only after the individual boundaries work:

```text
Task compiler
    ↓
Grounder
    ↓
Model
    ↓
Verifier
    ↓
Actuation
```

Compare against control/current harness and oracle-task/oracle-grounding arms where useful.

---

# 18. Recommended next experiment order

```text
1. IMPLEMENT TEMPORAL CLOSURE
        ↓
2. RERUN DETERMINISTIC GROUNDING
        ↓
3. IF RETENTION PASSES:
   CLOSED-WORLD RESOLVER
        ↓
4. MODEL SYNTHESIS OVER GROUNDED OBLIGATIONS
        ↓
5. COMPOSE PARSER + GROUNDER
        ↓
6. END-TO-END HARNESS TEST
```

Parallel, low-priority:

```text
task-scope anaphora census
```

Do not spend effort yet on:

- richer parser prompting;
- finance ontology;
- semantic edge roles;
- more completion heuristics;
- broader verifier contracts;
- UI/API redesign.

---

# 19. Broader research claim emerging

A plausible general research thesis is now:

> **Agent harnesses are most valuable when they act as specification-preserving, mechanically compiled environments around stochastic models: recovering globally derivable structure, exposing task-addressable coordinate systems, preserving ambiguity, and enforcing only mechanically justified obligations.**

An even more compact formulation:

> **Compile what is deterministic. Preserve what is specified. Expose what is addressable. Let the model decide what remains ambiguous. Verify only what can be proved.**

This formulation appears to unify both the Spreadsheet and OCC lines of work.

---

# 20. Current milestone statement

The project has crossed from:

> “Which spreadsheet tools should we expose?”

to:

> “What information transformations should the harness perform deterministically, and what obligations must survive each boundary?”

That is a meaningful architectural milestone.

The architecture is not complete because the model-resolution/synthesis stage and end-to-end composition remain unproven.

But the system boundaries are now stable enough that future experiments can test the architecture rather than continue inventing it.
