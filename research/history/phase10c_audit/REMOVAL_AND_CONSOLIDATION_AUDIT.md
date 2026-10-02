# Removal and consolidation audit

## SAFE TO REMOVE AFTER TEST

### 1. `_frozen/index.py`, `_frozen/reads.py`, `_frozen/runtime.py`, `_frozen/substrate.py`

- What uses it now: nothing in the maintained runtime. Verified by repo-wide
  import scan: the only `_frozen` imports outside `_frozen/` itself are
  `eligibility` (bootstrap + diagnostics probe), `capture` (`_capture_helper`
  + diagnostics probe), and `helpers` (`lx_helpers`). `runtime.py` imports
  `index`+`reads`; `substrate.py` imports `index`; nothing imports
  `runtime`/`substrate`.
- Historical purpose: RC-era SQLite read index (`index`), old decoder and
  candidate loader (`reads`), experimental live interposition runtime
  (`runtime`, `CANDIDATE_A_*` env), parent-maintained index publication
  (`substrate`). Phase-10 report explicitly lists the eager
  openpyxl-to-SQLite index path as dropped.
- Installed/public surface: shipped inside the wheel as
  `librecalc_agent/_frozen/*.py`, but no public API, CLI flag, config key, or
  documented import exposes them. Underscore package = internal by convention.
- Wheel/API/config change on deletion: wheel loses 4 files (~1,100 lines);
  no CLI/config/receipt change.
- Tests proving safe removal: (a) `test_no_research_imports` still passes;
  (b) 27/27 product tests pass; (c) repo-wide `grep -rn "_frozen.(index|reads|runtime|substrate)"`
  excluding `_frozen/` returns nothing; (d) clean-install + example run pass.
  Test-side prerequisite: `test_frozen_extraction_sources_unchanged` pins
  extraction sources including these files' origins — that test needs a
  scope decision (pin only retained extractions) before deletion reads green.
- Provenance: research history stays in `benchmark/` + `product_hygiene/`
  + git (once committed). No reason to ship the code to run the product.

### 2. `CANDIDATE_A_*` env handling in `runner.py` (strip-list)

- Dead once `_frozen/runtime.py` is gone: the strip-list
  (`runner.py:40-41`) exists only to shield the dead experimental runtime.
  Keep the `LIBRECALC_*` filtering. Low value alone; fold into the same
  cleanup step.

## REMOVE AFTER MIGRATION WINDOW

### 3. `src/lx_helpers.py` + `_frozen/helpers.py`, `_frozen/helper_common.py`, `_frozen/period_constants.py` (one unit)

- What uses it now: benchmark scripts (`representative_score.py`,
  `ab_checkpoint_score.py`, etc.) and `tests/test_fail_closed_substrate.py`.
  Zero `run`-path consumers.
- Historical purpose: model-facing inspection helpers Dobackend, kept
  reference-openpyxl-only for migration.
- Installed/public surface: YES — top-level `lx_helpers` module ships in the
  wheel and the RC-era docs/tests treat it as importable. This is the one
  removal with a real compatibility surface.
- Wheel/API change: wheel loses top-level `lx_helpers.py` + 3 frozen modules.
- Tests proving safe removal: 27/27 product tests (which never import it);
  benchmark/test migration off `lx_helpers` first; clean-install check.
- Recommendation: announce removal, migrate the one legacy test and any live
  benchmark tooling, then delete as a unit. Do not delete `helpers.py` while
  keeping `lx_helpers.py` or vice versa.

### 4. Config keys `substrate`, `candidate_a` (migration aliases)

- Accepted in `[runtime]` (`config.py`), combined into `config.reads` with
  `enabled`. Diagnostics deliberately say "direct read engine" instead.
  Removal changes config surface: old `runtime.toml` files with these keys
  would fail validation (which currently fails closed to disabled runtime +
  warning — safe but surprising). Migrate examples/docs to a single
  `reads`-style key first, then drop after a window. See configuration audit.

## CONSOLIDATE

### 5. `read_engine/cache.py` vs `read_engine/artifact.py` — shared identity/duplication

- `sha_file`, `identity`, `artifact_key`, `paths`, `MAGIC/FORMAT/CONTRACT/
  DECODER/MAX_*` constants are defined nearly identically in both files.
  Both define `validate` (different depth: integrity-only vs full decode)
  and `ensure` (locked fast-path vs build-and-publish).
- Recommendation: single-source the constants + `sha_file` + `identity` +
  `artifact_key` + `paths` in one module (e.g. `artifact.py` or a small
  `_identity.py`); keep the two `validate`/`ensure` layers — the fast
  integrity gate in front of the locked full build is legitimate layering,
  not accidental duplication. Risk on consolidation: key-format drift between
  the two copies would already be a bug today; a shared definition removes
  that hazard. Gate: key-stability test + 27/27 + concurrency test.

### 6. Admission ownership (`_frozen/eligibility.py` + `read_engine/certificate.py`)

- Two static-analysis modules with different jobs (whole-script routing vs
  merged-child proof) — keep both logics, but the `_frozen` location of the
  classifier is pure provenance. A move to `read_engine/admission.py` with
  byte-identical logic + a provenance comment would end the split-brain
  ownership. Optional; do not change classifier behavior in the same step.

### 7. Snapshot logic (observer C vs `_frozen/capture.py::snapshot_xlsx`)

- The observer snapshots pre/post bytes natively; the capture helper
  re-snapshots post bytes in Python. Overlapping but separately owned
  (survivor vs analyzer) — see duplication section. Consolidation NOT
  recommended (defense in depth across processes).

## KEEP

- `cli.py`, `__main__.py`, `__init__.py`, `config.py` (minus alias cleanup),
  `diagnostics.py`, `runner.py`, `_bootstrap/sitecustomize.py`,
  `read_engine/{artifact,cache,certificate,direct,runtime}.py`,
  `_frozen/{eligibility,capture,delta,validate}.py`, `_capture_helper.py`,
  `native/{observer,launcher}.c`, `hatch_build.py`, `pyproject.toml`,
  `examples/basic/*`, both product test files.

## KEEP FOR NOW — UNCERTAIN

- `src/librecalc_mcp/` (15 files): not in the product (not imported, not
  shipped), but it is the only git-tracked `src/` content and legacy tests
  depend on it. Repo-level retention decision, not a runtime decision.
  Do not ship; do not delete in the product cleanup pass.
- `diagnostics.libreoffice()`: small, honest, supports `--require-libreoffice`.
  Keep unless CLI surface is cut harder (see V1 boundary).

## Duplicated-responsibility classifications

| Responsibility | Locations | Verdict |
|---|---|---|
| Source hashing (`sha_file`) | `cache.py:29`, `artifact.py:44` | LIKELY CONSOLIDATABLE (identical) |
| Artifact identity/key/paths/constants | `cache.py:37-52`, `artifact.py:56-71` | LIKELY CONSOLIDATABLE (shared module) |
| Artifact validation | `cache.validate` (integrity-only) vs `artifact.validate` (full decode) | LEGITIMATE DIFFERENT OWNERS (fast gate vs semantic gate) |
| `ensure` (locked publish) | `cache.ensure` wraps `artifact.ensure` | INTENTIONAL DEFENSE IN DEPTH (lock + revalidate + build) |
| Config loading | `config.load` (CLI/runner) + launcher-side XDG default + bootstrap fallback branch | LEGITIMATE DIFFERENT OWNERS (three processes, one effective-config handoff); the bootstrap fallback branch is nearly dead in practice but harmless |
| Runtime/version identity | `__version__` (single source) + `DECODER/CONTRACT/FORMAT` duplicated across cache/artifact | MIGRATION DUPLICATION for the trio; consolidate |
| Path resolution (cache/runs) | launcher `private_directory` + runner `_prepare` + observer `mkdir` | INTENTIONAL DEFENSE IN DEPTH (each process hardens what it uses) |
| Admission checks | `_frozen/eligibility` (routing) + `read_engine/certificate` (merged proof) + `runtime.load` supported-mode gate | LEGITIMATE DIFFERENT OWNERS (static route vs proof vs per-load enforcement) |
| Workbook discovery | bootstrap `workdir.glob("*.xlsx")` (artifacts) vs observer `nftw` recursive (effects) | LEGITIMATE DIFFERENT OWNERS (different scopes by design: top-level build vs recursive observe) |
| Cache validation | covered above | see validation row |
| Receipt creation | observer receipt (native, process/effects) + `runner.read_last_receipt` (synthesis) | LEGITIMATE DIFFERENT OWNERS (writer vs reader/synthesizer) |
| Effect snapshots | observer pre/post (bytes) + capture helper post re-snapshot | INTENTIONAL DEFENSE IN DEPTH (cross-process check; helper validates what observer detected) |
| Failure classification | observer exit codes + helper exit 3 + receipt `failure_code` + `ASSURANCE_STATUS` | LEGITIMATE DIFFERENT OWNERS (layered signals, one synthesis rule) |
| Subprocess launch | observer fork/exec (target + helper) + runner subprocess/execve (observer or direct) + launcher execv | LEGITIMATE DIFFERENT OWNERS (each layer launches exactly one child) |
| Platform detection | `hatch_build.py` (build gate) + `diagnostics` platform report + `sys.version_info` check | LIKELY CONSOLIDATABLE only cosmetically; harmless as is |
| Merged-range handling | `direct.py` merged lists + `runtime.py` merged-child gate + `certificate.py` proof | INTENTIONAL DEFENSE IN DEPTH (data + enforcement + proof) |
| ZIP/XML bounds | `direct.py` decode bounds + `artifact.py` payload bounds + observer snapshot bounds | INTENTIONAL DEFENSE IN DEPTH (per-layer ceilings) |

No case was found where consolidation is both safe and urgent except the
cache/artifact shared-identity module (item 5).
