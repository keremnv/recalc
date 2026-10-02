# Phase 10C-B implementation plan

Ledger for every Phase-10C-A cleanup item. No code modified before this file
existed. Architecture frozen: ordinary Python, conditionally accelerated,
externally observed.

## Step 0 — baseline + provenance (RELEASE ENGINEERING)

- Files: `phase10c_b/BASELINE_WORKTREE_MANIFEST.md`, `.gitignore`, git index.
- Behavior change: none.
- Public surface: none.
- Compatibility: none.
- Regression gate: `git status` understood; no unrelated tracked change
  overwritten; hygiene rules distinguish SOURCE/EVIDENCE/GENERATED/LOCAL.
- Rollback: unstage; `.gitignore` revert.
- Class: RELEASE ENGINEERING.

## Step 1 — license (RELEASE ENGINEERING)

- Files: `LICENSE` (new), `pyproject.toml` (`license =` field), sdist/wheel
  include check.
- Behavior change: none.
- Public surface: adds license text + metadata (new, not breaking).
- Compatibility: none (previously unlicensed; any use was already ungrounded).
- Regression gate: `LICENSE` present in repo root, sdist, and wheel;
  `pip show -f` lists it.
- Rollback: remove file + metadata line.
- Class: RELEASE ENGINEERING.
- Blocker branch: if no license is inferable, record LICENSE DECISION
  REQUIRED, continue everything else.

## Step 2 — version + changelog (RELEASE ENGINEERING)

- Files: `src/librecalc_agent/__init__.py` (`__version__`),
  `pyproject.toml` (`version`), `CHANGELOG.md` (new).
- Behavior change: artifact keys change (runtime version is keyed) → old
  cached artifacts orphan (rebuild, never served). Intended + safe.
- Public surface: `--version` output, `doctor`/`status` version fields.
- Compatibility: cache orphans (safe rebuild); receipt `version` value change.
- Regression gate: 27/27 (or successor count); version consistency test
  (package `__version__` == installed metadata); upgrade-invalidation logic test.
- Rollback: revert version strings (note: published RC must never be
  re-minted under the same version).
- Class: RELEASE ENGINEERING.
- Candidate: `0.2.0rc2` (same architecture generation, cleanup release).

## Step 3 — docs rewrite (NON-BEHAVIORAL)

- Files: `README.md` (rewrite), `COMPATIBILITY.md` → superseded by
  `docs/SUPPORTED_PLATFORMS.md`-style current docs; new
  `docs/EVIDENCE_AND_LIMITATIONS.md`; `examples/basic/*` narrative;
  historical docs moved under `research/archive/` or marked HISTORICAL.
- Behavior change: none.
- Public surface: documentation only (no code surface change).
- Compatibility: none in code; docs stop describing the old RC.
- Regression gate: docs checklist vs audit (install, platform, quickstart,
  acceleration, capture, cache, diagnostics, limitations, uninstall,
  security); example walkthrough passes verbatim.
- Rollback: git revert.
- Class: NON-BEHAVIORAL.

## Step 4 — release CI + Linux baseline + dep reproducibility (RELEASE ENGINEERING)

- Files: `.github/workflows/release-candidate.yml` (new),
  `phase10c_b/LINUX_RELEASE_BASELINE.md`, dependency lock/hash material
  (`requirements-release.txt` with `--hash` or `pip freeze` record),
  `scripts/release-check.sh` (new, runnable locally).
- Behavior change: none to product.
- Public surface: none.
- Compatibility: none.
- Regression gate: CI-equivalent script passes locally: clean build →
  clean install → 27/27 → doctor/example/run/status → reference + direct
  BUILD/REUSE → capture → abrupt-exit smoke → wheel-list/license/no-pycache
  checks → checksums recorded.
- Rollback: delete workflow/script.
- Class: RELEASE ENGINEERING.
- manylinux: attempt straightforwardly; if risky, document narrow baseline.

## Step 5 — dead frozen module removal (PUBLIC-SURFACE CLEANUP)

- Files: DELETE `src/librecalc_agent/_frozen/{index,reads,runtime,
  substrate}.py` (+ stale `__pycache__`); EDIT
  `tests/test_product_hygiene.py::test_frozen_extraction_sources_unchanged`
  scope (pin retained extractions only) — test-side, pre-approved by audit.
- Behavior change: none (zero maintained consumers; verified by import scan
  + dynamic-import grep for `importlib`/`__import__`/entry-point references).
- Public surface: wheel loses 4 internal files; no documented surface changes.
- Compatibility: anyone importing the underscore-internal dead modules breaks
  loudly (acceptable: never public/documented).
- Regression gate: repo-wide import scan clean; 27/27; clean install;
  example; direct BUILD/REUSE; reference-only path.
- Rollback: git revert (files are small; history retains them).
- Class: PUBLIC-SURFACE CLEANUP.

## Step 6 — `CANDIDATE_A_*` removal (PUBLIC-SURFACE CLEANUP)

- Files: `src/librecalc_agent/runner.py` (strip-list → keep only
  `LIBRECALC_*` filtering); confirm no other product reader survives Step 5.
- Behavior change: `CANDIDATE_A_*` env vars now inherit into the target env
  like any other user var (previously stripped). No maintained consumer ever
  read them, so observable behavior is unchanged except env passthrough.
- Public surface: removes undocumented filtering of undocumented vars.
- Compatibility: none (vars were research-internal).
- Regression gate: 27/27 incl. env/FD parity tests.
- Rollback: one-line revert.
- Class: PUBLIC-SURFACE CLEANUP.

## Step 7 — `read_gate` retirement + receipt schema audit (PUBLIC-SURFACE CLEANUP)

- Files: `src/librecalc_agent/runner.py` (`read_last_receipt`),
  `src/librecalc_agent/_bootstrap/sitecustomize.py` (`setup.json` fields),
  tests asserting receipt shape, docs (receipt guide).
- Behavior change: compact receipt replaces `read_gate` research strings
  (`A1_ADMIT`, `PREDECLARED_REAL_OPENPYXL`) with product shape:
  `admitted: bool` + `admission_reason: <plain code>`. Full classifier detail
  stays in `setup.json` (run dir, unstable/support-only).
- Public surface: YES — `--json` receipt shape changes (RC-age schema;
  migration: keep route/artifact/fallback fields untouched; document change in
  CHANGELOG as COMPATIBILITY).
- Compatibility: bounded break for `--json` parsers reading `read_gate`;
  justified pre-v1, announced in changelog. No dual-write (avoid freezing both).
- Regression gate: new receipt-shape test; 27/27 successor suite; status/doctor
  JSON validated.
- Rollback: revert synthesis + setup fields together (never half).
- Class: PUBLIC-SURFACE CLEANUP.

## Step 8 — `--verbose`/JSON clarification (NON-BEHAVIORAL or tiny fix)

- Files: `src/librecalc_agent/cli.py`, docs.
- Behavior change: none OR one bounded correction (TBD on inspection; prefer
  documenting that `--verbose` prints the full JSON report).
- Public surface: docs only, unless the one-line fix is taken (then minor).
- Compatibility: none.
- Regression gate: doctor/status output tests.
- Rollback: revert.
- Class: NON-BEHAVIORAL.

## Step 9 — cache/artifact identity consolidation (INTERNAL REFACTOR)

- Files: new `src/librecalc_agent/read_engine/_identity.py` (constants +
  `sha_file` + `identity` + `artifact_key` + `paths`); slim `cache.py` and
  `artifact.py` to import it; keep both `validate`/`ensure` layers;
  new key-stability fixture test.
- Behavior change: none intended (byte-identical keys; key-stability test
  locks `artifact_key` for fixed inputs + version-bump invalidation).
- Public surface: none (internal module; underscore name).
- Compatibility: artifact keys MUST stay stable (test-enforced); any drift is
  a rollback trigger, not a migration.
- Regression gate: key-stability test; 27/27; concurrency test;
  corrupt/stale rebuild tests; version-invalidation test.
- Rollback: revert to duplicated definitions (keys identical either way).
- Class: INTERNAL REFACTOR.

## Step 10 — cache visibility (HARDENING-adjacent; small feature, docs-backed)

- Files: `src/librecalc_agent/diagnostics.py` (`check`/`status`:
  cache path + bounded size summary + artifact count + deletion guidance),
  docs.
- Behavior change: additive diagnostic fields/lines only.
- Public surface: additive (new JSON keys + human lines; document as
  informational, no retention promise).
- Compatibility: additive only.
- Regression gate: doctor/status tests incl. missing-cache and huge-cache
  boundedness (size scan capped: max files/bytes walked, then `truncated: true`).
- Rollback: remove fields.
- Class: HARDENING (operational visibility; no eviction algorithm).

## Step 11 — capture XML hardening (HARDENING)

- Files: `src/librecalc_agent/_frozen/delta.py`, `validate.py`
  (smallest mitigation: DTD/entity guard or bounded parse wrapper),
  new adversarial XML unit test.
- Behavior change: hostile XML (DOCTYPE/entities) rejected loudly instead of
  parsed; benign workbooks bit-identical behavior.
- Public surface: none (error path only).
- Compatibility: files that previously parsed now reject ONLY if they contain
  entity/DTD constructs (outside the supported corpus; capture otherwise
  preserves reference behavior).
- Regression gate: adversarial test (billion-laughs + external entity);
  changed-file fixtures still pass; 27/27.
- Rollback: revert guard; document residual risk.
- Class: HARDENING.

## Step 12 — snapshot-bound diagnostics (HARDENING)

- Files: `src/librecalc_agent/native/observer.c` (distinct error codes/
  messages per bound: file-count, aggregate-bytes, unreadable file,
  allocation failure), process-semantics test additions.
- Behavior change: same failure situations, clearer stderr + distinct
  classification (add `snapshot_error` to receipt where writable).
- Public surface: stderr text (documented as diagnostic, not API).
- Compatibility: none (failure paths only; exit codes unchanged).
- Regression gate: bound-classification tests (synthetic: 1001-file dir,
  oversized file, unreadable file).
- Rollback: revert observer.c (rebuild binaries).
- Class: HARDENING.

## Step 13 — `lx_helpers` disposition (PUBLIC-SURFACE CLEANUP)

- Files: `phase10c_b/LX_HELPERS_DISPOSITION.md` (decision record), then per
  verdict: deprecation marker + docs + timeline, or removal (module +
  `_frozen/{helpers,helper_common,period_constants}` + `pyproject.toml`
  force-include + legacy-test/benchmark migration).
- Behavior change: none to `run` (zero run-path consumers).
- Public surface: YES if removed (top-level import disappears); deprecation
  warning if windowed.
- Compatibility: per disposition; benchmark/test migration first if removing.
- Regression gate: 27/27; import scan; clean install; wheel-list check.
- Rollback: revert (re-add files + include rule).
- Class: PUBLIC-SURFACE CLEANUP.

## Step 14 — config alias migration (PUBLIC-SURFACE CLEANUP)

- Files: `src/librecalc_agent/config.py` (new `reads` key + `substrate`/
  `candidate_a` deprecated aliases with warning), `examples/basic/runtime.toml`
  (rewrite to successor), docs, config tests.
- Behavior change: old keys still accepted with loud deprecation warning for
  one window; `reads` is the documented key; `reads` + alias conflict →
  fail-closed (invalid config) to avoid ambiguity.
- Public surface: additive key + deprecation warnings; later removal is post-v1.
- Compatibility: old configs keep working (warning added on stderr path via
  issues list).
- Regression gate: config unit tests (new key, alias, conflict, unknown key);
  27/27; example uses new key.
- Rollback: revert config.py + example.
- Class: PUBLIC-SURFACE CLEANUP.

## Step 15 — terminology sweep + wheel manifest (NON-BEHAVIORAL)

- Files: `phase10c_b/WHEEL_CONTENTS_FINAL.md`; source edits only for
  PRODUCT SURFACE occurrences of research vocabulary (candidate_a, substrate
  outside compat shims, H0/H1, phase names in shipped code).
- Behavior change: none (comments/identifiers/docs only; no logic renames
  that change pickle/key formats).
- Public surface: none beyond Step 7/14 changes.
- Compatibility: none.
- Regression gate: grep-based vocabulary test for the wheel file list; 27/27.
- Rollback: revert.
- Class: NON-BEHAVIORAL.

## Step 16 — regression battery + clean RC build (RELEASE ENGINEERING)

- Files: `phase10c_b/RELEASE_CANDIDATE_MANIFEST.json`,
  `PHASE10C_B_RELEASE_IMPLEMENTATION_REPORT.md`.
- Covers: failure injection, process semantics, reference/direct/fallback/
  merged-cell/capture/abrupt-exit/concurrency regressions, clean sdist/wheel
  build + fresh-env install + smoke battery, SHA-256 records.
- Regression gate: everything above green; any red → fix-forward if bounded,
  else verdict B/C/E (never lower criteria).
- Class: RELEASE ENGINEERING.

## Out of scope (record, don't solve)

P5, engine optimization/coverage, merged-cell semantics, helper perf, cold
start, eviction algorithm, model helpers, derivation/temporal/formula-error/
token research, macOS/Windows implementation, benchmark reruns beyond narrow
gates, marketing, broad speed claims.
