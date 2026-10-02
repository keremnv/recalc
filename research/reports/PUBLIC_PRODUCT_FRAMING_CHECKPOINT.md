# Public product framing checkpoint

**Status:** archival checkpoint for presentation pause. This records the implemented `librecalc-agent 0.2.0rc1`, the current evidence boundary, and the intended explanatory structure. It is not marketing copy or a design decision for the next read engine. Sources: [product anatomy audit](PRODUCT_ANATOMY_AUDIT.md), [read acceleration reconciliation](READ_ACCELERATION_RECONCILIATION.md), [authoritative claim registry](FINAL_CLAIM_REGISTRY.md), and current [README](../../README.md).

## Physical product now

The model-facing interface is an ordinary agent-written Python/openpyxl script. `librecalc-agent run` is a parent launcher around one execution of that script in a child Python process; it preserves the script's normal output and exit status. The parent loads runtime configuration, checks the script and workdir, applies whole-script static admission for optional indexed reads, and creates a per-run directory. On admission, it hashes and parses discovered top-level `.xlsx` workbooks with **reference openpyxl**, builds a derived read index in memory, and publishes a SQLite copy plus an identity manifest for the child. This RC rebuilds that state on each invocation.

Before launch, the parent takes a byte snapshot of workbooks when capture is enabled. The child starts with a process-local `sitecustomize` hook, guarded to the classified script, that rebinds `openpyxl.load_workbook` within that interpreter. Supported reads can be served through proxy objects backed by the derived index and child-parsed workbook metadata. Non-admitted scripts, unsupported load options, unavailable or stale state, and unsupported proxy behavior route to reference openpyxl under the runtime's fallback rules. Four admitted RC workloads exposed semantic failures, so this routing is **not** a broad exactness guarantee.

After the script exits, the parent observes workbook bytes again, derives package-level deltas for changed files, performs mechanical validation and replay checks, and records per-run diagnostics and provenance. The script's produced workbook remains the output; capture does not judge whether it satisfies the user's task. Operator-facing records include the index manifest, load/fallback events, capture records, summary, and `doctor`/`status` output. No computed workbook substrate is inserted into the model prompt or context; the model is not asked to use a new workbook API or choose an indexed mode. The current product is also not a prompt-side rich semantic workbook representation.

## Terminology to preserve

| Preferred architectural/public description | Meaning in this checkpoint |
|---|---|
| `runtime` | The optional parent/child execution machinery around ordinary Python. |
| `derived read index` | Hash-pinned workbook facts prepared for the narrow read path; SQLite is its current storage choice. |
| `process-local interface-preserving interposition` | The child startup hook and openpyxl-facing proxy path, scoped to one interpreter and intended to preserve the script interface. This phrase does not assert universal semantic equivalence. |
| `effect capture` | Byte and package-part observation after execution, with mechanical checks. |
| `operator observability` | Local status, event, fallback, capture, and provenance records. |
| `reference openpyxl` | The ordinary openpyxl parser and object behavior used for construction and reference routing. |

These are architectural descriptions, not necessarily current code identifiers. Research-era identifiers to retire **from eventual public language**, without renaming code now, are `candidate_a`; `substrate` when its referent is ambiguous; `compiled` when nothing is compiled into executable code; `accelerated` when it only reports *index-served* routing rather than measured speed; and `H0/H1`. Some remain current configuration, environment, telemetry, and source identifiers, so this checkpoint does not change them.

## Front-page explanatory model to preserve

| Phase | What happens |
|---|---|
| **BEFORE EXECUTION** | Whole-script admission; workbook identity and freshness checks; construction/publication of derived state for admitted reads; pre-execution workbook observation. |
| **DURING EXECUTION** | The same Python/openpyxl program runs once; process-local interposition serves supported operations deterministically from derived state; reference openpyxl handles other paths. |
| **AFTER EXECUTION** | Effect capture, package-level delta, mechanical validation, and diagnostics/provenance. |

The key comparison is **the same agent program without LibreCalc** versus **the same agent program with LibreCalc machinery around and under execution**. The agent's program and workbook task remain the center of that explanation. This is a proposed presentation structure, not a claim that every interposed read is exact or faster.

## Evidence boundary and explicit non-claims

| Regime | What the evidence establishes |
|---|---|
| **INDEX-READY MECHANISM** | Historical exact-trace replay demonstrated cheaper supported load/read traces after derived state had already been prepared: 51/51 exact on those traces and median 44.46% trace-time reduction. Its timer excluded construction and full product lifecycle; this is internal technical evidence only. |
| **COLD PRODUCT** | The packaged `0.2.0rc1` public path rebuilt state on each invocation. In the preregistered eligible view, all 22 scripts were slower end-to-end than direct Python/openpyxl; median treatment/control ratio 2.017. Four genuine admitted-path semantic failures were also found. |
| **WARM PRODUCT** | No scored warm-product speed result exists. A public reuse probe found that a second invocation with the same workbook, script, workdir, and cache created a new run directory and rebuilt the index. |
| **UNRESOLVED** | Whether a public implementation with valid reusable and cheaper derived state can yield net invocation or session speedup on fixed identical scripts/workbooks. |

The [claim registry](FINAL_CLAIM_REGISTRY.md) governs public claims. There is **no packaged speed claim** for `0.2.0rc1`; no broad admitted-read exactness or universal fallback claim; and no token, cost, capability-improvement, or capability-equivalence claim. Effect capture is mechanical/package-level observation, not task correctness or formula correctness. The product does not expose a rich semantic workbook representation to the model. The index-ready, cold-product, and absent warm-product findings remain separate; none substitutes for another.

## Why read-engine performance is the active branch

The reconciliation isolated lifecycle and representation costs rather than a new favorable workload population. Current index construction itself uses reference openpyxl. If later proxy behavior needs a normal reference workbook, setup can precede another openpyxl parse: four of the 22 eligible RC scripts logged this A+B pattern in all scored repetitions. The other 18 A-only scripts were still slower in the cold product study. Construction eagerly traverses all cells, computes anchor and temporal structures unused by the current product read path, and rebuilds state every invocation. The isolated contributions of these costs are not all timed. Whether SQLite is the best representation, whether state should persist, and whether construction should be demand-scoped remain unproven.

The next branch is therefore: **Determine the cheapest semantically exact representation and lifecycle for the already-demonstrated narrow read-substitution surface.** This checkpoint does not propose or select a mechanism.

## Representation neutrality

SQLite is inherited from the research implementation; it is **not an architectural requirement**. Representations open to empirical comparison include SQLite, compact binary structures, memory-mapped structures, direct OOXML offsets or indexes, per-sheet derived files, and other deterministic forms. The objective is the **fastest complete system under a fixed read contract and correctness requirement**, including construction and lifecycle costs. Preserving the current representation is not itself an objective. No representation is endorsed here.

## Presentation and naming status

**Presentation: `PAUSED — PRODUCT MODEL PRESERVED`.** When work resumes, the likely public order is: (1) physical product; (2) with/without execution scenario; (3) before/during/after lifecycle; (4) what gets computed; (5) how interposition works; (6) current benefits and evidence; (7) limitations and non-claims; (8) install/use; (9) research trajectory as appendix or deep history. This is an outline only.

**Naming: `UNRESOLVED`.** The current architecture is substantially less LibreOffice-specific than the project name implies. No rename decision has been made, and package/project identifiers remain unchanged.

Presentation should resume once the performance branch can say what the read engine actually is, which representation it uses, when derived state is constructed, whether it persists, which operations it replaces, and what measured benefit survives at product level. The front page should describe the resulting product without prematurely binding engineering to the RC's current index and lifecycle.

PRODUCT MODEL FROZEN FOR PRESENTATION PAUSE

PRESENTATION STATUS: PAUSED

ACTIVE BRANCH: READ-ENGINE PERFORMANCE

UNRESOLVED REPRESENTATION: YES

UNRESOLVED LIFETIME: YES

UNRESOLVED PRODUCT SPEED: YES

SAFE TO RESUME PRESENTATION AFTER PERFORMANCE BRANCH: YES
