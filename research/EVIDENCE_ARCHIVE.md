# Evidence archive

Large raw research evidence is preserved outside Git. A Git clone carries
the reports, ledgers, specifications, analysis scripts, and compact
supporting datasets; the multi-gigabyte run telemetry, staged workbooks,
caches, and transcripts it was computed from are archived separately.

## Preservation model

- One compressed archive per experiment family (`.tar.zst`), content
  deduplicated by ordering files with identical content adjacently.
- Every archive is checksummed (SHA-256) and file-count verified at
  creation time.
- `evidence-manifest.json` in this directory is the machine-readable
  index: archive id, family, description, original in-repo paths,
  originating commit, hashes, sizes, and redistribution status.
- Original in-repo paths and the pre-curation commit SHA are retained
  verbatim so archived material stays citable even if later history
  rewrites change SHAs.

## Archive families

50 archives in two classes. Bulk archives hold run dirs, staged
workbooks, telemetry, and caches. Transcript archives (suffixed
`-transcripts`) hold verbatim model prompts/completions and are kept
separate because their redistribution terms are unresolved.

## Checksum policy

SHA-256 over the compressed archive file, recorded in
`evidence-manifest.json` at creation. Re-verify after any transfer
before citing archived contents.

## Redistribution status

- `PUBLIC_ARCHIVE_WITH_ATTRIBUTION`: derived from MIT-licensed
  SpreadsheetBench-2 workbooks; may be published with attribution and
  the upstream license notice.
- `PROVENANCE_UNCLEAR`: contains third-party model API inputs/outputs
  whose redistribution terms were not verified in-repo. Preserved
  locally; do not publish until provider terms are manually confirmed.

## Locations

No archive has been uploaded yet. All `archive_url` fields in
`evidence-manifest.json` are `null` (pending). Recommended destination
when ready: a DOI-minted Zenodo dataset with this manifest attached.

## Private working data (not in Git, not for upload)

Separate from the archive above, bulk working data lives in a private
directory outside the repository and is intentionally not published:

- run caches and ignored raw JSONLs that were never committed;
- tracked bulk data files over 5 MB removed from Git during the
  repository tidy (ledgers, timings, baselines, logs);
- stale local release-candidate staging.

`private-data-manifest.json` in this directory indexes every unit with
its in-repo path, size, and SHA-256/tree hash. To reproduce analyses
that read these files, symlink them back into a worktree with:

```sh
scripts/restore-private-data.sh        # link all units
scripts/restore-private-data.sh --check
scripts/restore-private-data.sh --clean
```

The private root defaults to the manifest's `private_root` and can be
overridden with `RECALC_PRIVATE_DATA`. Restored symlinks are gitignored
and must never be committed. A public clone builds, tests, and runs the
product without any of this data; only historical reproduction scripts
need it.
