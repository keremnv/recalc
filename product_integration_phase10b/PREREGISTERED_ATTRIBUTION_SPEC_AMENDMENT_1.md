# Phase 10B preregistered attribution amendment 1

Written and hashed after the original P0–P4 batch completed, before any S-arm fixture or scored execution. The original spec and first scored ledgers remain unchanged. This is an explicit adaptive diagnostic amendment: the original P3−P2 increment was material but combined default configuration, classifier/source work, and setup receipt. The first batch cannot distinguish those costs, so a bounded two-arm split is necessary to answer the already-preregistered attribution questions. No population, budget, product code, observer, comparator or timing boundary changes.

## New arm identity

| File | SHA-256 |
|---|---|
| `product_integration_phase10b/run_supplement.py` | `0f1c5c4bd06c33d0679cd46b8fe0189a72123843127cd956898ae0a4a0c9d71a` |
| `product_integration_phase10b/supplement_fixtures.py` | `c0ee4ae6c66ce29650f45c7c228f3772c7766c611d9586fb4be173305dfd1beb` |
| `product_integration_phase10b/config_only_bootstrap/sitecustomize.py` | `21c09dfc25c14d22ab5b39633223313e54dc707cee22a1cc5a834a079a526dc9` |
| `product_integration_phase10b/config_classifier_bootstrap/sitecustomize.py` | `46f5ac2cad2f0073277c1079a4d51153ecf477612b37420fda4e37ca30574024` |

## Frozen supplemental arms

- S0: original P2 minimal guard through direct installed observer.
- S1: S0 plus production-shaped standard-library/config imports and default config load, without classifier or setup receipt.
- S2: S1 plus unchanged production classifier import, source read, and `classify(source)` call; no setup receipt.
- S3: original P3 installed full production bootstrap through direct installed observer, including negative setup receipt.
- S1/S2 are attribution-only diagnostics on the exact frozen negative scripts. They are not product routing candidates.
- Incremental questions: S1−S0 = default-config/bootstrap imports and load; S2−S1 = source read/classifier import/execution; S3−S2 = setup receipt and residual production bootstrap structure. As before, paired full-command differences are causal authority; module timers are diagnostic.

## Gate and score

Before scored S-arm timing, run `supplement_fixtures.py` on module/argv/path, uncaught exception, atexit workbook write, abrupt exit after workbook write, and genuine reference-object fixtures. Require same exit/stdout/workbook value as S0, same stderr except traceback path, observer `PASS`, and S3 `REFERENCE_FAST_PATH`. Any failure stops.
Then run two scored repetitions of invocation 1 and invocation 2 per exact 22 frozen reference-only workload; each repetition starts fresh arm-specific state. Use the same full external command boundary, 180-second timeout, staging and frozen Phase-3 comparator. Require exact/volatile-only output state, exit parity, observer `PASS`, and S3 negative route with no artifact. Stop on first failure.
Arm order is `random.Random(((20260928 XOR 0x10B) XOR 0x52) XOR first12hex(SHA256(workload_id:rep:invocation))).shuffle(S0..S3)` as pinned in `run_supplement.py`. Store append-only `supplement_raw_timings.jsonl` and `supplement_correctness.jsonl`.
Use invocation 2 for primary supplemental effects. For each workload compute the median of two paired-repetition signed differences and ratios; aggregate across all 22 with a seeded 5,000-resample workload bootstrap interval. Do not combine S0/S3 medians numerically with P0/P4 medians from the separate batch; within-batch S0/S3 anchor the split.
The +10 ms product budget stays unchanged. This amendment does not authorize P5. A separate treatment decision must follow analysis.
