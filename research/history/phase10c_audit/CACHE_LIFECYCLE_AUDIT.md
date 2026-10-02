# Cache lifecycle audit

Phase-10 intentionally deferred global quota/eviction. Question: must that
block an initial release?

## Facts

- Layout: `<cache>/read-engine/<key>.r3jz{,.json}` (persistent artifacts) +
  `<cache>/runs/run-*/` (receipts + debug bundle, incl. `pre/*.bin` only when
  changed bytes were captured) + `<cache>/runs/last_run.json`.
- Per-artifact bounds: 256 MiB compressed / 512 MiB uncompressed / 10M cells.
  Realistic workbook artifacts are KBs–MBs (typed JSON+zlib of cell values).
- No eviction, no quota, no TTL, no `prune` command anywhere in the product.
- Run dirs accumulate forever (one per observer-mediated invocation).
- Version upgrades orphan old keys (new key per runtime/decoder/contract/
  format change; old files never served, never deleted).
- Source edits orphan old keys the same way (keyed by whole-file SHA-256).
- Manual deletion safety: GOOD. Artifacts are pure derived state — deleting
  `read-engine/` while idle only forces rebuild; deleting `runs/` only loses
  history (`status` reports "none recorded"). Nothing authoritative lives here.
- Discoverability: GOOD. `doctor`/`status` print the cache path
  (`Diagnostic logs: .../runs`); `status --json` reports locations.
- Existing evidence of accumulation: none adverse — validation hosts show
  trivial cache sizes; no growth incident recorded.

## Estimates

- Steady-state technical-preview user (tens of workbooks, hundreds of runs):
  single-digit MB artifacts + small receipts. Negligible.
- Heavy user (daily runs × large workbooks × frequent edits × version
  upgrades): unbounded linear growth in orphaned keys + run dirs. Could reach
  GBs over months. No cliff, just cruft.
- Worst case per invocation is bounded (one artifact ≤256 MB + one run dir);
  there is no amplification vector.

## Verdict: SHOULD FIX BEFORE RELEASE BUT NOT FUNDAMENTAL

Rationale: for a SMALL Linux-first technical preview with documented manual
cleanup, missing eviction is operationally reasonable — it must not block v1.
But "reasonable" requires the docs + visibility half:

Pre-release minimum (no eviction algorithm needed):
1. Document the location, layout, manual-deletion safety, and that old
   versions/sources orphan entries.
2. Show cache size in `doctor`/`status` (a `du`-style summary line) so growth
   is visible, not mysterious.

Post-v1: automatic policy (LRU/TTL/size cap + `prune` command). Do NOT freeze
a cache-CLI contract now; design it with usage data.

What would escalate this to BLOCKING: a shared/multi-tenant install story or
a promise of bounded disk use — neither is in v1 scope.
