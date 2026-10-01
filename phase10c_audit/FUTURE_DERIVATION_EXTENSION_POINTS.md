# Future derivation extension points (Phase-11 orientation only)

No research performed here. This file records where derived evidence COULD
attach later without redesigning the runtime, so future work doesn't couple
itself to internal machinery. No choice is made.

## Candidate hosts for derived evidence

| Host | What would attach | Why it fits | Coupling risk |
|---|---|---|---|
| Separate analysis command (e.g. `librecalc-agent analyze <run-dir>`) | Post-hoc derivations over run-dir bundles + workbooks | Run dirs already persist setup/runtime/capture/observer receipts; read-only analysis can't perturb execution | LOW — new command, new module, consumes frozen files |
| Post-run receipt extension | Small derived summaries alongside `observer_receipt.json` | Receipt synthesis (`runner.read_last_receipt`) already merges per-layer files; a new optional file + new optional fields compose cleanly | LOW if new fields are optional and versioned; MEDIUM if derivation runs inline in the observer path (don't) |
| Optional agent-visible helper (library import) | Query-style derivations over workbooks | `lx_helpers`-shaped precedent (top-level import, reference backend) shows the packaging pattern — but that surface is slated for removal, so a new helper must be a deliberate NEW contract, not a revival | MEDIUM — creates a public Python API; freeze only when the derivation contract is validated |
| Diagnostic output (`doctor`/`status` additions) | Environment/capability derivations | Diagnostics already merge config + modules + receipts; additive fields are cheap | LOW for additive fields; MEDIUM if it changes exit semantics |
| Python library (`import librecalc_agent.<submodule>`) | Programmatic access to admission/artifact/capture primitives | Modules are already import-structured; `runner.run()` is a proto-API | HIGH — freezing import paths + signatures now would constrain the pre-v1 cleanup (alias retirement, `_frozen` relocation). Defer. |

## Guidance for the future branch

- Derive from FROZEN ARTIFACTS (run dirs, receipts, workbooks), never from live
  runtime internals (no importing `Runtime`, no hooking the observer, no
  bootstrap coupling).
- New surfaces must be additive and optional: derivation failure must never
  change target/assurance status (same rule as capture: report, don't perturb).
- Do not reuse research-arm vocabulary (`CANDIDATE_A_*`, `read_gate` values)
  in any new surface — those are being retired.
- The receipt's `run_dir` pointer is the intended handoff: durable,
  content-addressable enough (uuid), and already the support bundle.
