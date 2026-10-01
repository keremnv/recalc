# Final presentation and demo handoff

> HISTORICAL — rc1-era presentation wording. Superseded for rc2; see
> [README.md](README.md) and
> [docs/EVIDENCE_AND_LIMITATIONS.md](docs/EVIDENCE_AND_LIMITATIONS.md).

Research is closed. Use [FINAL_CLAIM_REGISTRY.md](FINAL_CLAIM_REGISTRY.md) as the source of truth for external wording and [RC_ACCELERATION_CLAIM_VALIDATION_REPORT.md](RC_ACCELERATION_CLAIM_VALIDATION_REPORT.md) for methods and evidence.

## Public narrative

`librecalc-agent 0.2.0rc1` is a packaged way to run ordinary Python/openpyxl spreadsheet scripts with an optional deterministic read runtime. In the final preregistered fresh-invocation benchmark, the optional runtime did **not** deliver a packaged wall-clock advantage: all 22 eligible read scripts were slower, and four scripts revealed genuine read-semantic differences. We therefore make no RC speed or full exactness claim.

## Presentation sequence

1. Explain the ordinary Python/openpyxl interface and the frozen RC identity.
2. Show the claim boundary: deterministic read acceleration was historically fast on selected operations, while product-level setup must be charged on every invocation.
3. Present the final experiment: 30 ordinary scripts, 22 eligible scripts, public CLI, fresh cache, three paired scored repetitions.
4. Present the negative result and semantic failures plainly. Do not headline historical microbenchmark speedups.
5. Close with the final claim registry and research stop decision.

## Demo preparation

Use the packaged example or a small ordinary Python/openpyxl script with `librecalc-agent run --no-runtime` to demonstrate the supported invocation interface. Do not stage an acceleration-speed demo or imply that the optional runtime preserves every admitted read on this RC. If discussing optional acceleration, display the qualified result and the product defect rather than selecting a favorable workbook. Any corrected runtime requires a newly identified package and belongs to later release engineering, outside this frozen research record.
