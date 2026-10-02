# Phase 10 validation amendment 1: runtime-version cache binding

Written and hashed before any scored rerun. The original `PRODUCT_INTEGRATION_VALIDATION_SPEC.md` and its SHA-256 remain unchanged. The first full PY/EXP/PROD run completed with all 543 correctness rows valid; its 1,629 timing rows, 120 session rows and analysis are preserved under `product_integration_phase10/scored_v1/`. Those performance rows describe the earlier product implementation and are diagnostic for the final implementation.

## Concrete implementation defect

The initial integrated cache key bound source SHA-256, decoder identity, semantic-contract version and artifact-format version, but not the maintained package runtime version. The requested runtime-upgrade invalidation test could therefore not prove that a new package version would bypass old derived state when the other identities remained unchanged. This is a lifecycle identity defect, not a discovered timing result or a changed population.

## Bounded repair

`read_engine/cache.py` and `read_engine/artifact.py` now include the package runtime version in the content-addressed artifact key. The sidecar explicitly records `runtime_version` and must match before warm reuse. The `JSONZ_MEMORY_V1` semantic payload and header, direct OOXML decoder, admission, proxy/read contract, fallback, observer, capture, CLI, fixture populations and timing boundaries remain unchanged. The package runtime version change creates a different artifact path; old artifacts are never accepted as a new generation. A product test now checks this key transition.

The repaired maintained implementation and installed wheel are pinned in `product_integration_phase10/implementation_identity_v2.json`, SHA-256 `9c457162c45ca337aa736e0da0bc59dd976d42be54051a8278d664b4fb64fa34`. New wheel SHA-256: `4cdd46e918704c56598a4965325a8a7ad29d63a532eada6cb3f74a17c1da37be`. All other source identities remain those in the original manifest. Maintained product tests passed 25/25 before this amendment.

## Rerun rule

Rerun the entire scored validator, not only favorable or affected-looking scripts. Keep the original exact fixed 22, representative 30, changed five, PY/EXP/PROD arms, two cold/second repetitions, observed N=1/2/3/5 representative sessions, order seed, comparator, correctness gate, reference-only +10 ms practical budget and direct-contact 1.10 migration-regression flag. Use empty version-2 caches. A second failure must stop interpretation and be reported; it must not be repaired by excluding rows.
