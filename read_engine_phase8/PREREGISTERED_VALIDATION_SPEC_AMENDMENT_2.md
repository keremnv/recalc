# Phase 8 validation specification — Amendment 2

Status: **versioned before scored timing**. The original stopped Phase-8 report, base spec and Amendment 1 remain unchanged. Amendment 1 SHA-256: `8616338db08aa404c186f4ad33b359f5195919eccfa70d777754b79fa249789b`.

## Why the amendment is necessary

The unscored Amendment-1 gate passed all **30/30 representative scripts** on cold and second invocation (60 valid pair sets). It then stopped at the first fixed changed-file fixture. PY and frozen H0 produced byte-identical output; H1 differed only in `docProps/core.xml` because ordinary reference openpyxl stamped `dcterms:modified` one second later when that arm ran. The other eight XLSX package parts, stdout/stderr, exit, effect path, capture helper, validation and replay were exact. This is launch-time volatile workbook metadata, not a read-engine semantic difference. The failed unscored gate ledgers are preserved under `read_engine_phase8a/gate_attempt_1/`; no Phase-8 scored rows existed.

## Exact comparison clarification

For changed-file fixtures only, compare every XLSX part by exact SHA-256, except `docProps/core.xml` may differ **only** in one `dcterms:modified` UTC timestamp matching the strict `YYYY-MM-DDTHH:MM:SSZ` shape. The complete XML bytes must become identical after replacing exactly that field with a fixed marker. Any other XML byte difference, additional/missing part, different non-XLSX output, exit/stdout/stderr mismatch, missing effect, helper failure, failed validation or failed replay remains a hard correctness failure. Record each normalized part explicitly. Raw ZIP and part hashes remain in the ledger. Representative read-only comparison is unchanged.

The new gate root `read_engine_phase8/runs_resume_v2/` starts with independent empty caches, so the prior unscored attempt cannot make a cold command warm. Re-run the **full** 30-script representative gate and all five changed-file gates before scoring. The population, five fixture scripts/workbook bytes, PY/H0/H1 arms, repetitions/order, full-command timers, N horizons, reference-only standard and analysis rules remain unchanged. A subsequent semantic mismatch stops scoring; there is no patch-and-continue within a scored run.

## Version-2 code identity

`read_engine_phase8a/implementation_identity_v2.json` SHA-256: `14cfa74aa384540153b1380be268177e101a17b1725485a439a621d52eca59ea`. It pins the same 21 files as Amendment 1, with only the validation runner changed. Runner SHA-256: `8c2649314f5770e81b28a6ce9bfb06cc37901b6602cb8d1f83b82db1efd7923c`. The certificate, overlay, Phase-6 observer, Phase-7 merge runtime, artifact format, direct decoder and all population/fixture hashes are unchanged. No treatment behavior or timer boundary changed.
