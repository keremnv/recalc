# Research storage plan (Phase 1 — classification only, no bytes moved to storage)

No Git LFS / release-asset / external-store decision is made here. This plan only
classifies the working tree so a later decision has exact numbers. Source of truth
for per-path bytes and hashes is `research_preservation_manifest.json` (473 entries,
generated pre-cleanup; inventory hashes exclude `__pycache__`/`*.pyc` caches).

## Totals by preservation class (untracked + ignored material)

| Class | Entries | Total bytes |
| ----- | ------- | ----------- |
| `GIT_NORMAL` | 423 | 0.42 GB |
| `GIT_LFS_CANDIDATE` | 10 | 1.99 GB |
| `EXTERNAL_ARTIFACT_CANDIDATE` | 3 | 5.53 GB |
| `EXTERNAL_DATASET` (`benchmark-data/`) | 1 | 31.75 GB |
| `GENERATED_DISPOSABLE` (caches, `.venv`, empty file) | 34 | 0.11 GB |
| `LOCAL_ONLY_SECRET_OR_ENV` (`.env`, `.secrets/`) | 2 | < 1 KB |

Rules: dir ≥ 1 GiB → external-artifact candidate; dir ≥ 100 MiB or file ≥ 25 MiB →
LFS candidate; else normal Git. `closure_transfer_audit/work/` (60 MB, ignored) is
counted both standalone and inside its parent dir; totals overstate by ~60 MB.

## Largest 30 paths

| Size | Class | Path |
| ---- | ----- | ---- |
| 31.75 GB | EXTERNAL_DATASET | `benchmark-data` (nested SpreadsheetBench-2 checkout, gitignored) |
| 3.17 GB | EXTERNAL_ARTIFACT | `compiled_context_sidecar_ab` |
| 1.21 GB | EXTERNAL_ARTIFACT | `rc_acceleration_validation` (final frozen study) |
| 1.16 GB | EXTERNAL_ARTIFACT | `candidate_a_a1_checkpoint_rerun_01` |
| 355 MB | LFS | `candidate_a_live` |
| 302 MB | LFS | `stochastic_work_census` |
| 212 MB | LFS | `token_affordance_discovery` |
| 206 MB | LFS | `transparent_capture_replay` |
| 195 MB | LFS | `scheduler_live_validation` |
| 191 MB | LFS | `representative_architecture_checkpoint` |
| 166 MB | LFS | `token_claim_discovery` |
| 145 MB | LFS | `track_c_terminal_projection` |
| 116 MB | LFS | `thin_architecture_checkpoint` |
| 108 MB | LFS | `compact_evidence_delivery` |
| 92 MB | DISPOSABLE | `.venv` (recreatable) |
| 70 MB | GIT_NORMAL | `formula_error_feedback_discovery` |
| 64 MB | GIT_NORMAL | `closure_transfer_audit` |
| 61 MB | GIT_NORMAL* | `closure_transfer_audit/work` (ignored subset of the above) |
| 49 MB | GIT_NORMAL | `resource_demand_autopsy` |
| 32 MB | GIT_NORMAL | `candidate_a_a1_classifier` |
| 22 MB | GIT_NORMAL | `default_harness_deterministic_execution` |
| 16 MB | GIT_NORMAL | `batch_write_helper_ab` |
| 16 MB | GIT_NORMAL | `candidate_a_a1_checkpoint` |
| 11 MB | GIT_NORMAL | `live_transparent_runtime_ab` |
| 11 MB | GIT_NORMAL | `actuation_loss_trace.csv` |
| 9 MB | DISPOSABLE | `benchmark/__pycache__` |
| 9 MB | GIT_NORMAL | `targeted_runtime_replication` |
| 8 MB | GIT_NORMAL | `inspection_efficiency_ab` |
| 7 MB | GIT_NORMAL | `transparent_python_read_census` |
| 5 MB | GIT_NORMAL | `integrated_feasibility_census.json` |

## Which frozen studies fit entirely in ordinary Git

Fit (all ≤ 100 MiB, human-readable-first): `final_architecture_freeze`,
`architecture_evidence_freeze`, `rc_warm_acceleration_characterization`,
`read_side_v2_adjudication`, `track_c_terminal_projection` (145 MB — over line, see
below), plus every study report `*.md` at top level and all slice/manifest/prereg
JSON. Concretely every evidence dir not listed as LFS/external above, including
`formula_error_feedback_discovery` (70 MB), `closure_transfer_audit` (64 MB),
`resource_demand_autopsy` (49 MB). The 50–100 MB tier is committable but heavy;
prefer committing it once, never rewriting it.

Need bulk artifact storage (bytes outside ordinary Git, pointers inside):

- `compiled_context_sidecar_ab` (3.17 GB)
- `rc_acceleration_validation` (1.21 GB — the final frozen study)
- `candidate_a_a1_checkpoint_rerun_01` (1.16 GB)
- The 10 LFS-candidate dirs (108–355 MB each)
- `benchmark-data` (31.75 GB — never in Git; nested-checkout provenance recorded
  in the manifest via its own Git identity)

## Reports/manifests that must remain in Git as pointers

Even when a study's bulk bytes live outside ordinary Git, these stay in Git so the
record is reconstructible:

- Every top-level study report `*.md` (small, human-readable).
- Every preregistration, decision, and `*_manifest.json` / `*hashes.json` /
  `spec_hash.json` / `primary_freeze.json` file.
- `research_preservation_manifest.json` (this plan's source: per-path bytes,
  inventory hashes, frozen-pin checks).
- `FINAL_CLAIM_REGISTRY.md`, `RESEARCH_RECORD_FREEZE.md`, `FINAL_PRESENTATION_HANDOFF.md`,
  `CLAIM_BACKLOG.md` (claim boundary; stay top-level in Phase 1).
- `product_hygiene/` (RC validation evidence incl. frozen wheel reference).
- Bulk candidates additionally need a small pointer file each (content hash +
  byte size + storage location) once a store is chosen — not created yet.

## Unresolved (deliberately, for a later phase)

- LFS vs release assets vs other content-addressed store for the ~7.5 GB bulk set.
- Whether the 50–100 MB `GIT_NORMAL` tier stays in ordinary history or joins bulk.
- `benchmark-data/` acquisition documentation (official SpreadsheetBench-2 source +
  pinned nested-HEAD from the manifest) for `research/README.md` (Phase 1 keeps the
  README minimal per instructions).
