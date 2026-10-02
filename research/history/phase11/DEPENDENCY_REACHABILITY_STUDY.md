# Dependency reachability study (C6 → DEP-DIRECT-REFS, D1, EXACT)

Mechanical definition: one-hop precedent/dependent refs per formula cell
via tokenization. Diagnostic/localization use only — dependency ≠ intent,
and nothing here revives target authority.

## Natural reachability (n=87 formula workbooks)

R2=70, R3=17, R4=0. NO agent in 87 runs extracted references
systematically (no Tokenizer, no regex-over-formulas, no Translator for
tracing; agent-pattern census: dep_extraction=1 run corpus-wide). The R3
mass is manual tracing: read a formula, read its 1–3 referenced cells by
hand. Agents trace shallowly (one hop, named cells) and only when the
task forces it (Debugging).

## Failure linkage / discrimination

- Unrefined coding showed spurious DIRECTLY_LINKED hits (finding set =
  all precedents; overlap guaranteed). After the precision guard:
  GENERIC throughout, linkage UNRELATED/UNKNOWN. The full precedent map
  is too broad to discriminate anything.
- Narrowed variant (computed offline): precedents OF new-error cells and
  OF post-edit-break cells are small (1–8 cells) and diagnostic — e.g.
  the FM_01_01_H1 cascade roots to emptied BS-Segment-3 inputs. But this
  is dependency-as-explanation attached to an already-found signal, not
  an independent discovery fact.

## Interpretation

As a standalone surfaced fact (full dep map): TRIVIAL AND LOW VALUE —
cheap, exact, unreached, but useless in full (too broad) and redundant in
part (manual tracing suffices for the 1-hop cases agents actually need).
As attached localization for error/break findings: legitimate diagnostic
accessory — include "fed by / feeds into" one-hop context IN the
error-delta/uniformity evidence block, never as its own surface. No
transitive closure, no target inference. dependency ≠ intent preserved.
