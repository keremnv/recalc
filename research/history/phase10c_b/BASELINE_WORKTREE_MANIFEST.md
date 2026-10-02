# Baseline worktree manifest (Phase 10C-B step 0)

Recorded 2026-09-28 before any 10C-B product edit (only
`phase10c_b/IMPLEMENTATION_PLAN.md` existed as a new file).

## Baseline `git status` (summary)

- Tracked modified (`M`): 20 files — `.gitignore`, `README.md`,
  11× `benchmark/*`, `pyproject.toml`, `src/librecalc_mcp/backend/uno.py`,
  6× legacy `tests/*`. All predate this phase; DO NOT OVERWRITE.
- Staged new (`A`): 4 — `benchmark/output_role_occurrence_contrast.py`,
  `output_role_occurrence_contrast.{csv,json}`,
  `research/evidence/OUTPUT_ROLE_OCCURRENCE_CONTRAST_REPORT.md`.
  In-flight user staging; DO NOT DISTURB.
- Renames (`R`/`RM`): 9 — docs → `research/archive/*` moves. Same: leave alone.
- Untracked (`??`): 471 paths, including the ENTIRE maintained product
  (`src/librecalc_agent/`, `src/lx_helpers.py`, `hatch_build.py`, product
  tests, all `PRODUCT_*`/`READ_ENGINE_*` docs, all evidence dirs, all audit
  dirs). Only `src/librecalc_mcp` (15 files) is tracked.

## Classification

### SOURCE (intended release diff — to be staged, then committed by owner)

- `src/librecalc_agent/**` (minus `__pycache__`, minus built native binaries)
- `src/lx_helpers.py` (or its disposition outcome)
- `hatch_build.py`, `pyproject.toml`
- `examples/basic/**`
- `tests/test_product_hygiene.py`, `tests/test_product_process_semantics.py`
- `README.md`, `CHANGELOG.md` (new), `COMPATIBILITY.md` successor docs,
  `docs/**` (new current docs), `LICENSE*` (pending decision)
- `.github/workflows/release-candidate.yml` (new),
  `scripts/release-check.sh` (new), `scripts/build_native.sh` (new),
  `requirements-release.txt` (new)
- `phase10c_audit/**`, `phase10c_b/**` (audit + implementation records)
- `PRODUCT_*.md` integration specs/reports (product-adjacent records)
- `src/librecalc_mcp/**` — already tracked; KEEP AS IS (not in product,
  not touched by this phase except incidentally never)

### EVIDENCE (retained on disk + in worktree; NOT staged — volume decision is owner's)

- `product_integration_phase10/` (1.6 GB), `product_integration_phase10b/`
  (2.2 GB), `product_hygiene/` (404 KB), `benchmark/` (new files, 6.9 MB),
  `read_engine_phase*/`, `research/`, `architecture_*`, `*_probe/`,
  `*_audit/`, `*.csv` ledgers, `candidate_a*`, `thin_architecture_checkpoint/`,
  old RC wheel in `product_hygiene/dist/`.
- Rationale: multi-GB bulk; committing is an owner storage/policy call
  (LFS? annex? external?). Nothing in 10C-B deletes or rewrites evidence.

### GENERATED (must stay ignored / never staged)

- `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.ruff_cache/`
- `dist/`, `build/`, `*.egg-info/`, `*.whl`
- Built native binaries: `src/librecalc_agent/native/observer`,
  `src/librecalc_agent/native/launcher` (rebuilt by hook/script)
- `phase10c_b/RELEASE_CANDIDATE_MANIFEST.json` — generated record: commit the
  manifest CONTENT (hashes), not the archives it points at.

### LOCAL (ignored, machine-specific)

- `.venv/`, `.venv-product/`, `benchmark-data/` (30 GB),
  `closure_transfer_audit/work/`, `.env`, `.secrets/`, `.librecalc/`,
  `~/.cache/librecalc-agent` (outside repo).

## Provenance decision

NO COMMITS will be created by this phase. Reasons:

1. The user has in-flight staged/renamed work (`A`/`R`/`RM` entries); any
   commit I create would either sweep it in (wrong) or sit awkwardly beside
   it.
2. The evidence-volume commit policy (3.8 GB+ in two dirs alone) is an owner
   decision this phase must not preempt.
3. Review-first is safer: the deliverable is an exact, staged, reviewable
   release diff + this manifest.

Instead, at phase end: `git add` exactly the SOURCE release set above (new
paths only; never `git add -A`), leaving all pre-existing staged/unstaged
tracked modifications byte-identical, and report the staged diff stat.
`.gitignore` gains only GENERATED/LOCAL rules (native binaries, release
archives); no evidence path is newly ignored.
