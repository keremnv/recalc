# Visual assets + claim/evidence check (DRAFT for discussion)

Simplified visual plan per the benefits-first brief: three assets maximum,
each communicating exactly one product property. No polished GIF/SVG work
until the direction is approved.

## Asset 1 — terminal demo animation (the hero)

- What: screen recording of `scripts/demo.sh` (this demo / this machine):
  ordinary Python → first run BUILT → second run REUSED with identical
  results → unsupported operation on the reference path.
- Communicates: same code, same result, repeated parsing avoided; fallback
  is a first-class path, not an error.
- Source: generated from the reproducible demo only. Static fallback until
  the animation exists: the real transcript in `scripts/demo.sh` output
  (verified this session; see below).
- Tooling choice needed: VHS (scripted, reproducible, `demo.tape` checked
  in) vs asciinema (real recording, harder to regenerate). Proposal: VHS,
  with the tape invoking `scripts/demo.sh` so visuals regenerate via
  `demo.sh --check` + `vhs demo.tape`.
- Length: aim ≤ 60 s, no audio.

## Asset 2 — reuse + fallback diagram (static SVG)

- What: `product_presentation/DIAGRAM_DRAFT.svg` — one diagram: unchanged
  script → can this read reuse the saved decode? → yes: load saved decode
  (green accent) / no: ordinary openpyxl → same result → receipt records
  the path.
- Communicates: the before/after mental model (decode once, reuse; step
  aside otherwise) plus visibility (you can see which path happened).
- Styling is draft quality: monochrome + one green accent, system fonts.
  Open choices: dark-mode background handling, final accent, corner/shape
  language. ASCII fallback for text contexts: the Before/After strip and
  the YES/NO strip already in `README_DRAFT.md`.

## Asset 3 (optional) — small timing card from the demo run

- What: one compact read-phase comparison, e.g. `ordinary 38 ms →
  reused 23 ms`, labeled "demo workbook, this machine, in-script read
  phase (parse + reads), excludes interpreter startup — not a benchmark".
- Communicates: the avoided mechanical work is real and measured — modestly.
- Condition: include only if the numbers are stable enough across re-runs to
  not mislead. Measured this session (CPython 3.13.12, Linux x86_64):
  plain 37.9 ms, BUILT 22.6 ms, REUSED 23.5 ms, reference 41.0 ms
  (in-script read phase; totals ~330–470 ms, startup-dominated).
- Proposal: generate the card from `demo.sh` output at release time rather
  than hand-drawing it, or drop the asset if the delta ever inverts on the
  recording machine.

## Explicitly deferred

- Aggregate research charts, benchmark populations, confidence intervals:
  out of the product README (internal research document instead).
- `doctor`/`status` screenshots: only if a reviewer finds the receipt story
  unclear without one.
- Architecture-internals graphics (cache layout, observers, certificates):
  link to docs instead.

## Claim/evidence check (prototype sentences → source)

| Planned sentence / visual | Evidence source | Status |
|---|---|---|
| Same ordinary openpyxl code; only the invocation changes | `examples/demo/read.py` runs under both `python` and `run`; 543/543 oracle parity rows in `docs/EVIDENCE_AND_LIMITATIONS.md` | OK |
| Repeated reads skip repeated parsing (BUILT → REUSED) | `scripts/demo.sh` asserts `BUILT` then `REUSED` with `served_loads ≥ 1`; demo transcript this session | OK |
| Identical results across plain / BUILT / REUSED | `demo.sh` byte-compares stdout (`cmp`); verified this session | OK |
| Unsupported operations run on ordinary openpyxl | `unsupported.py` → `REFERENCE_FAST_PATH`, output matches plain; `demo.sh` asserts it | OK |
| Receipt shows which path each run took | `route`/`artifact` compact fields (`PRODUCT_RECEIPT_SCHEMA.md`), shown live in demo | OK |
| Saved state follows the exact bytes; edits rebuild | Whole-file SHA-256 keying + versioned identity (`_identity.py`, evidence doc) | OK (keep wording qualitative, no mechanism detail in hero) |
| "Faster repeated spreadsheet reads" (headline) | Demo read-phase 38→23 ms this machine + frozen 0.608× median on 7 direct-contact workloads (conditional, host-specific) | WEAK — headline needs the skeptical review; must stay adjacent to the demo scope label, never standalone as universal |
| Any specific ratio or bar in Asset 3 | Single demo run only | Only with full scope label; never averaged, never headlined |

## Forbidden in presentation (unchanged)

Universal speedup, cold-start acceleration, write acceleration, token or
model-cost savings, broad openpyxl equivalence, task-score improvement,
"X% faster agents", cross-host timing guarantees, rc1 numbers as rc2
behavior, Phase 11–13 mechanisms.

## Open questions for discussion

1. Headline wording: is "Faster repeated spreadsheet reads. Same ordinary
   openpyxl code." correctly scoped, or does "faster" still overclaim
   without an adjacent qualifier?
2. Timing card: include Asset 3 with the modest honest numbers, or cut it
   and let route/artifact carry the story?
3. Animation tooling: VHS (reproducible tape) vs asciinema vs static
   transcript only?
4. Diagram styling: keep monochrome+green, or match a future site/doc theme?
   How should the SVG behave in GitHub dark mode?
5. Research-lineage document: where should the internal evidence-lineage
   page live, and who is its audience (maintainers only)?
6. Branch/worktree: cut `product-presentation/rc2` from which exact commit
   as the clean rc2 baseline? (Prototype currently sits uncommitted on the
   working tree; no commits made.)
