# Frozen 06_01 O3 Evidence-Access Baseline

This is an offline accounting of the preserved content-addressed pool and manifests. No provider request was made and the pool/manifests were not modified.

Scope: 16 O3 target sessions. Shared records across every O3 target: **7743**. Each target retains its complete archived synthesis-visible record set; the table below reports the lossless shared/delta decomposition.

| Target | Final synthesis records | Shared records | Target delta | Retrieval calls | Final working-set IDs |
|---|---:|---:|---:|---:|---:|
| DCF!C49 | 7965 | 7743 | 222 | 8 | 7737 |
| DCF!D49 | 8038 | 7743 | 295 | 2 | 7821 |
| DCF!E49 | 8292 | 7743 | 549 | 8 | 8070 |
| DCF!F49 | 8330 | 7743 | 587 | 5 | 7952 |
| DCF!G49 | 8369 | 7743 | 626 | 6 | 8172 |
| DCF!H49 | 8422 | 7743 | 679 | 8 | 8048 |
| DCF!I49 | 8490 | 7743 | 747 | 7 | 8297 |
| DCF!J49 | 7743 | 7743 | 0 | 4 | 7563 |
| DCF!K49 | 8377 | 7743 | 634 | 5 | 7996 |
| DCF!L49 | 8154 | 7743 | 411 | 7 | 7974 |
| DCF!M49 | 7952 | 7743 | 209 | 2 | 7767 |
| DCF!N49 | 7842 | 7743 | 99 | 7 | 7648 |
| DCF!O49 | 7998 | 7743 | 255 | 2 | 7817 |
| DCF!P49 | 7922 | 7743 | 179 | 8 | 7752 |
| DCF!Q49 | 8042 | 7743 | 299 | 8 | 7857 |
| DCF!R49 | 7799 | 7743 | 56 | 6 | 7617 |

## Lossless interface

```text
authoritative evidence store
    + stable record IDs / ordered manifests
    + per-target delta
```

The archived `cell:s01:r49:c3` synthesis evidence was reconstructed from only its manifest and the content-addressed pool. The reconstructed content hash is:

`e0ec34a13c32208d5a975f78860e71cb9e48159f59ac7712498ebc60c73eb88c`

Content-equivalent: **True**. The archived evidence hash is `e0ec34a13c32208d5a975f78860e71cb9e48159f59ac7712498ebc60c73eb88c` and the manifest hash is `e0ec34a13c32208d5a975f78860e71cb9e48159f59ac7712498ebc60c73eb88c`.

The exact shared IDs are in `evidence_access_baseline.json` under `shared_records_across_all_o3_targets.record_ids`; exact per-target/final-synthesis IDs are under each `per_target[].record_ids` entry. Retrieval history/state is recorded alongside each target.

This proves storage/reconstruction deduplication, not model-token savings. A stateless model cannot access omitted shared facts from a record ID alone. A model-facing compact representation therefore needs a persistent retrieval/materialization tool, or a shared model-visible context carrying the shared records, plus the manifest and target delta.

Retrieval history/state is retained per target in `resource_demand_autopsy/evidence_access_baseline.json`, including working-set IDs before/after each archived retrieval call and the final synthesis-visible record count.
