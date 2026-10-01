# Phase 10B preregistered attribution amendment 2: bytecode-regime correction

Written and hashed before the normalized rerun. The original preregistration, amendment 1, both initial raw ledgers, and their logs are preserved. No population, budget, product source, arm source, comparator, repetition/order, timing endpoint or stop rule changes.

## Concrete benchmark-identity defect

The installed production `sitecustomize.py` had a valid CPython 3.13 `.pyc` cache, while the experimental P2/S0, S1 and S2 bootstrap files did not. `PYTHONDONTWRITEBYTECODE=1` prevents writing bytecode but does **not** prevent reading an existing cache. The initial full-command scores therefore charged source compilation to experimental arms and not to production P3/S3/P4. This can particularly distort P3−P2 and S3−S2; the surprising negative S3−S2 increment exposed it. The initial 440 main and 352 supplemental timing rows are diagnostic only. Their correctness results remain useful but do not validate import-cost attribution.

## Normalized condition

Before any rerun, compile only the experimental `sitecustomize.py` modules with the same installed CPython 3.13 interpreter. `bytecode_identity.json` pins the resulting P2/S0, S1, S2 and existing production P3/S3/P4 `.pyc` hashes. The empty P1 bootstrap intentionally has no module to compile. No compilation occurs inside timed commands; no arm changes Python bytecode policy. The source and compiled code hashes are fixed by the original spec/amendment and this identity file.

## Full rerun rule

Rerun the P0–P4 process fixtures and complete exact-22 scored batch, then the S0–S3 process fixtures and complete exact-22 supplemental batch, using fresh run roots and the original deterministic balanced orders. Preserve all initial rows under `scored_v1/` and `runs_v1/`/`supplement_runs_v1/`. The new canonical ledgers use the original filenames and must not append to v1. Stop on semantic/assurance mismatch. Compare the two normalized batches only through their own paired increments; do not subtract cross-batch medians. The frozen +10 ms P4−P0 criterion remains unchanged.

No P5 treatment is authorized by this amendment. Decide that only after normalized attribution.

Bytecode identity SHA-256: `4783fc0e02d6c4f76c64b630729ec70795fb89ee75b41f454d9f3d8d5e2713c0`.
