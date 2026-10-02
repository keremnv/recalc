# Repository cleanup Phase 1 report (conservative pass)

Date: 2026-09-25. No commits were made. No runtime code was edited. No frozen
evidence bytes were modified. No license was chosen. `benchmark/` and
`src/librecalc_mcp/` were not moved.

## Baseline (pre-cleanup)

- HEAD: `254a5c14fa74fc3534493c565de84b38e7317175`
- Status: 191 tracked paths; 4 staged-new (A); 22 modified (M); 423 untracked (??).
- Ignored: `.env`, `.secrets/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`,
  `benchmark-data/`, `closure_transfer_audit/work/`, `product_hygiene/dist/`
  (the frozen wheel), plus scattered `__pycache__/`.
- Existing WIP was preserved untouched: all 4 staged and 22 modified entries are
  intact after cleanup (two modified docs now show as `RM` renames with identical
  worktree bytes; the staged report followed its move as staged-new at the new
  path). Cleanup index changes are exclusively the 9 renames + 1 staged-move below.

## Preservation manifest

`research_preservation_manifest.json` (473 entries): every untracked/ignored path
plus Phase 1 move candidates, with type, bytes, git state, preservation class,
nearby hash manifests, per-file SHA-256 or deterministic directory inventory hash
(sorted repo-relative paths + sizes + file hashes; `__pycache__`/`*.pyc` excluded
and counted separately), and frozen-pin checks.

- All frozen-pin checks match, including the 0.2.0rc1 wheel and all
  `rc_manifest.json` source entries — except two explained era-mismatches
  (recorded in the manifest's `provenance_notes`): `CLAIM_BACKLOG.md` vs
  token-era pins (document legitimately evolved; RC-era pin matches) and
  `TOKEN_EFFICIENCY_CLAIM_DISCOVERY_REPORT.md` vs the Sep-23 astra pin (correction
  documented in the report itself; Sep-24 final pin matches). No stop condition.
- `phase1_moves` in the manifest records all 77 old→new paths with post-move
  SHA-256 (including the `uv.lock` → `uv.lock.historical` rename).

## Storage classification (no bytes committed)

Per `RESEARCH_STORAGE_PLAN.md` (no LFS/asset decision made):

| Class | Entries | Bytes |
| ----- | ------- | ----- |
| `GIT_NORMAL` | 423 | 0.42 GB |
| `GIT_LFS_CANDIDATE` (dir ≥ 100 MiB) | 10 | 1.99 GB |
| `EXTERNAL_ARTIFACT_CANDIDATE` (dir ≥ 1 GiB) | 3 | 5.53 GB |
| `EXTERNAL_DATASET` (`benchmark-data/`) | 1 | 31.75 GB |
| `GENERATED_DISPOSABLE` | 34 | 0.11 GB |
| `LOCAL_ONLY_SECRET_OR_ENV` | 2 | < 1 KB |

No giant tree was added to Git. `benchmark-data/` stays gitignored; its nested
checkout identity is recorded in the manifest instead of a deep hash.

## Generated clutter removed (disk only)

- 463 `__pycache__/` directories (pre-verified: no hash manifest references any
  `__pycache__` path).
- `.pytest_cache/` (112K), `.ruff_cache/` (196K).
- `CLAUDE.md` (0 bytes).
- Verification runs regenerated some `__pycache__`; swept again after. Final
  count: 0 (excluding `.venv/`).

## Ignore changes

- `.gitignore`: added `.venv-product/` (the directory the README install path
  creates). No broad `*.json`/`*.csv`/`*.log`/`*.sqlite`/`*.xlsx` rules added, per
  instructions. The pre-existing WIP lines (`.secrets/`,
  `closure_transfer_audit/work/`) are untouched; the cleanup line is the last line
  of the diff.

## License

No `LICENSE` file created, per instructions. `PUBLIC_RELEASE_BLOCKERS.md` records
`PUBLIC_RELEASE_BLOCKER: LICENSE_NOT_CHOSEN`. Public release stays blocked on a
license choice.

## Research boundary created

- `research/README.md` (short: not the product surface, frozen evidence,
  superseded claims, registry authority, external dataset, no rewriting history).
- `research/evidence/` (66 moved reports), `research/archive/` (11 moved files +
  1 archived README copy).

## Files moved to `research/evidence/` (66, bytes exact, SHA-verified before/after)

All top-level `*.md` reports except the keep-list (`README`, `COMPATIBILITY`,
`CONTRIBUTING`, `FINAL_CLAIM_REGISTRY`, `RESEARCH_RECORD_FREEZE`,
`FINAL_PRESENTATION_HANDOFF`, `CLAIM_BACKLOG`, `PRODUCT_HYGIENE_REPORT`,
`REPO_CLEANUP_AUDIT`, plus Phase 1 outputs). Includes `FINAL_ARCHITECTURE_FREEZE.md`,
`PRODUCT_PRESENTATION_HANDOFF.md`, both RC validation reports, both ASTRA packets,
token/formula studies, and the staged `OUTPUT_ROLE_OCCURRENCE_CONTRAST_REPORT.md`
(moved via `git mv`, still staged-new).

The 14 hash-manifested moved files were re-verified at their new paths against
`evidence_source_hashes.json` (10), `rc root_report_sha256` (1),
`token root_reports` (1), and `review source_sha256` (2): **14/14 MATCH**.

## Files moved to `research/archive/` (11, bytes exact, SHA-verified)

- `docs/architecture.md`, `docs/roadmap.md`, `docs/benchmark-plan.md`,
  `docs/PROJECT_CONTEXT.md`, `docs/harness-value-packet.md`,
  `docs/public-trajectory-audit.md`, `docs/viz-isa-diagnosis.md` (+`.json`)
  (via `git mv`; two carry pre-existing WIP bytes, preserved).
- `spreadsheet_harness_architecture_checkpoint.md`.
- `scripts/install_into_personal_projects.sh` (via `git mv`).
- `uv.lock` → `uv.lock.historical` (via `git mv`; path-only change).
- `docs/` now contains only `docs/HISTORICAL_MCP_README.md` (still README-linked).

## Old README preserved

`research/archive/README.pre-public-cleanup.md`, SHA-256
`1d4a64dae30b49fd9726d4a2c507fe1679db0f07bf1696343002f898192834ed` — identical to
the frozen `rc_manifest.json` pin. It is not presented as current documentation.

## README changes

Rewrote `README.md` (new SHA-256 `8fff04bf…95ce4`) as a technical front page with
the 10 required sections, using the mandated neutral physical wording for indexing
("rebuilds this index per run; … no packaged speed claim") and semantic coverage
("edge cases in workbook iteration and array-formula handling … broad exactness is
not claimed"). Removed packaged-speed / fast-path / token / cost / capability
language. Added a claims-and-limitations box pointing to `FINAL_CLAIM_REGISTRY.md`
and the moved validation report. Updated the freeze-doc link to
`research/evidence/FINAL_ARCHITECTURE_FREEZE.md`. Install, config, command, example,
doctor/status, and fallback content is unchanged in substance.

Consequence (authorized by this phase's scope): `rc_manifest.json`'s
`source_configuration_sha256` no longer reproduces from the worktree, since README
is one of its 29 pinned files. Verified: **28/29 pinned files byte-identical, only
`README.md` differs**; the frozen value remains verifiable against the archived
copy, and the frozen wheel is untouched (see below). No product code, config,
example, or test bytes changed.

## Verification results

- `tests/test_product_hygiene.py`: **27 passed**.
- Move-adjacent research tests (`test_compiled_context_sidecar`,
  `test_catalog_gate`): **46 passed** (confirms the `PROJECT_CONTEXT.md` move broke
  no test; the only in-repo reader is a closed-research updater function).
- Wheel build: `hatchling` is not installed and no network install was attempted;
  instead verified the frozen wheel read-only against the worktree: **24/24 shipped
  files byte-identical** (only `dist-info/METADATA` embeds the old README prose,
  as expected). Frozen wheel hash still
  `532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e` — never
  rebuilt or overwritten.
- Isolated smoke (fresh venv, frozen wheel installed read-only, fresh cache):
  `doctor` all PASS, `example` + `run` of create/update/read all exit 0,
  `output.xlsx` contains `B2 == =A2*2`, no `benchmark`/`librecalc_mcp` imports.
- `git status --short`: 427 untracked / 4 staged / 20 modified / 9 renamed —
  all pre-existing WIP intact, cleanup renames cleanly separated.

## Broken links / references (known, reported per stop-condition policy)

- 18 moved reports contain relative links to top-level evidence directories
  (e.g. `candidate_a_a1_checkpoint_rerun_01/…`), now stale until Phase 2 reunites
  reports with their studies. Frozen bytes were not edited to fix them, per
  instructions. Sibling report↔report links still resolve (same directory).
- `benchmark/README.md` → `docs/public-trajectory-audit.md`: stale (research-side
  link; left untouched, not product-side).
- `benchmark/compiled_context_sidecar_ab.py::update_project_context()` reads
  `ROOT/docs/PROJECT_CONTEXT.md`: stale for reruns (research closed; not called by
  any test — verified).
- `product_hygiene/*.json` path pointers to moved reports/docs: stale as pointers
  (frozen records; hashes still verify against moved bytes via the manifest's
  `phase1_moves` map).
- New README links: all 8 resolve. No staying product file references any moved
  path.
- User-visible CLI strings still say "read acceleration" (`doctor`/`status`
  output). Left unchanged per the no-product-code rule; belongs to the naming
  batch (Phase 2).

## Remaining state

- Root Markdown: 76 → **12** (11 listed + this report).
- Remaining untracked: 427 paths (evidence dirs, benchmark/research/test files,
  loose CSV/JSON, Phase 1 outputs). Nothing was committed in this phase.
- `benchmark/`, `src/librecalc_mcp/`, research tests, extraction paths: untouched
  in place for Phase 2.

## Unresolved preservation/storage decisions

1. LFS vs release assets vs other store for the ~7.5 GB bulk set (3 external +
   10 LFS candidates).
2. Whether the 50–100 MB `GIT_NORMAL` tier joins bulk storage.
3. `benchmark-data/` acquisition documentation (official source + pinned nested
   HEAD from the manifest).
4. `benchmark/` fate (move under `research/` vs banner-in-place) with import-path
   lockstep.
5. `src/librecalc_mcp/` quarantine mechanics (45+ importer references).
6. Product vs research test split design.
7. License choice (release blocker).
