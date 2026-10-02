# Changelog — recalc-agent

## 0.2.0rc4 (release candidate, Linux-first)

Real product-mechanism expansion beyond rc3: the direct runtime now serves
the certified full-cell `ws.iter_rows()` contract (bounded or worksheet-
dimension bounds, nested row → cell consumption, `.value` / `.coordinate` /
`.row` / `.column` / `.data_type`) from the existing persisted read state.
No new agent API: scripts still write ordinary openpyxl. `iter_cols`,
`values_only`, `.values`, range literals, rich attributes, writes, and
`data_only` remain reference-routed by design.

- Representative-30 warm routing on the frozen confirmation population went
  from 7 direct (+1 pre-existing fallback) to 20 direct (+1 unchanged
  pre-existing fallback); representative warm total (median sums) 102.26 s
  → 21.51 s. Parity: 40/40 adversarial, 52/52 A/B differential, zero
  iteration-attributed fallbacks. See
  `research/full_cell_iteration_product_confirmation/REPORT.md`.
- Narrow exception-parity fix: missing-sheet lookup now raises the exact
  pinned-openpyxl `KeyError("Worksheet {name} does not exist.")`.
- Read-artifact keys rotate with the version bump by design, so rc3
  artifacts rebuild once on first rc4 touch (cold cost only).
- No cold-acceleration, write-acceleration, token-saving, or broad
  openpyxl-equivalence claim is added.

## 0.2.0rc3 (release candidate, Linux-first)

Rename and release-hygiene candidate. No runtime-mechanism change from
`0.2.0rc2`: the validated read/observer behavior and all rc2-established
evidence stand unchanged (see
[docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md)).

- Product renamed to `recalc`: distribution and command are now
  `recalc-agent`, the Python package is `recalc_agent`, public
  environment variables are `RECALC_CONFIG` / `RECALC_NO_RUNTIME`
  (plus internal `RECALC_*` handoff keys), and the default cache is
  `~/.cache/recalc-agent`. No old-name compatibility aliases.
- Licensed under the MIT License (`LICENSE`, copyright 2026 keremnv);
  the license blocker is resolved.

## 0.2.0rc2 (release candidate, Linux-first)

Version rationale: same architecture generation as `0.2.0rc1` (the validated
integrated product), with pre-release cleanup, documentation, and hardening.
Pre-release, not stable: the license decision is still open
(`LICENSE DECISION REQUIRED`) and support is Linux-first.

### USER-VISIBLE

- New product documentation describing the actual integrated implementation:
  ordinary Python scripts, conditional direct reads, external observer,
  reference fallback, effect capture, cache, diagnostics, limitations.
- Receipt `read_gate` research strings (`A1_ADMIT`, `PREDECLARED_REAL_OPENPYXL`)
  replaced with `admitted` (bool) plus a plain `admission_reason` code.
  Classifier detail remains in the run-dir `setup.json` for support.
- New documented config key `reads` (bool, default true) replacing the
  research-era `substrate` / `candidate_a` pair. Old keys are still accepted
  with a loud deprecation warning for one window and AND with `reads`, so old
  configs keep their meaning; removal is planned post-v1.
- `doctor` and `status` now report cache location, bounded size summary,
  artifact count, and safe-deletion guidance.
- Observer snapshot-limit failures now name which bound was exceeded
  (file count, aggregate bytes, unreadable file, allocation/read failure).
- Shipped `example` uses the new `reads` config key.

### INTERNAL

- Removed dead shipped research modules `_frozen/index.py`, `_frozen/reads.py`,
  `_frozen/runtime.py`, `_frozen/substrate.py` (zero maintained consumers;
  superseded RC index path). Research history stays in the repository and
  evidence archives.
- Removed `CANDIDATE_A_*` environment filtering from the runner (only the dead
  experimental runtime read those variables).
- Single-sourced artifact identity (`_identity.py`): file hashing, identity,
  artifact key, paths, magic, and format/contract/decoder versions. Artifact
  keys are byte-identical; key stability is regression-tested.
- Capture-path XML parsing now rejects DOCTYPE/entity constructs loudly
  instead of parsing them (adversarial XML regression test added).
- `--verbose` on `doctor`/`status` documented: prints the full JSON report
  (same as `--json`).

### COMPATIBILITY

- Receipt JSON: `read_gate` removed; `admitted` + `admission_reason` added.
  `route`, `artifact`, `fallback`, `target_status`, `assurance_status`, and
  capture fields are unchanged.
- Config: `substrate` and `candidate_a` deprecated (warning), removal planned
  post-v1. New key `reads`.
- `lx_helpers` top-level import: see `research/history/phase10c_b/LX_HELPERS_DISPOSITION.md`
  for the deprecate-vs-remove decision and timeline.
- Cached artifacts from `0.2.0rc1` are NOT reused: the runtime version is part
  of the artifact key, so old entries are orphaned and rebuilt (never served
  stale). Safe to delete the old cache.
- Wheel no longer contains the removed `_frozen` modules.

### KNOWN LIMITATIONS

- Linux x86_64 with glibc only; CPython 3.13 tested, 3.11–3.14 accepted.
  macOS fast-follow, Windows separate port. Local filesystems only.
- Narrow direct-read semantics; no broad openpyxl equivalence.
- No universal speedup; cold runs not accelerated; writes not accelerated.
- No token/model-cost claims. Effect capture is mechanical assurance, not
  task-correctness certification.
- No automatic global cache eviction (manual deletion documented and safe).

## 0.2.0rc1 (superseded research candidate — historical)

- Packaged RC with per-invocation openpyxl-to-SQLite index path, since
  superseded by the integrated persistent direct-read engine.
- Its frozen claim registry (`research/reports/FINAL_CLAIM_REGISTRY.md`, now historical) found
  packaged fresh-invocation wall-time reduction UNSUPPORTED (median T/C
  2.017) and exact read semantics for all admitted workloads UNSUPPORTED
  (four semantic failures on the old index path).
- Do not use rc1 docs or rc1 numbers to describe rc2. The old wheel in
  `research/history/product_hygiene/dist/` is an archive, never to be shipped.
