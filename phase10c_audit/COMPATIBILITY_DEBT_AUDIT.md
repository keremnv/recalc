# Compatibility debt audit

Scope: `_frozen/*`, `lx_helpers`, config aliases, retained old modules, and
anything kept for migration rather than product need.

| Item | Current public path needs it? | Only old research fixtures? | Existing RC compat? | Removal breaks installed users? | Ever public/documented? | Recommendation |
|---|---|---|---|---|---|---|
| `_frozen/eligibility.py` | YES (`run` admission) | No | Behavior-compatible by design | Yes | No (internal) | KEEP. Optionally relocate with identical logic. |
| `_frozen/capture.py+delta.py+validate.py` | YES (capture helper) | No | n/a (new packaging) | Yes | No (internal) | KEEP. Revisit redundant byte-rewrite. |
| `_frozen/helpers.py+helper_common.py+period_constants.py` | NO (`run` never touches) | Benchmark scripts + 1 legacy test | RC-era `lx_helpers` import surface | Only importers of `lx_helpers` | YES (shipped top-level, RC docs/tests) | REMOVE AFTER MIGRATION WINDOW, with `lx_helpers` as one unit. |
| `src/lx_helpers.py` | NO | Benchmark + `test_fail_closed_substrate` | YES — the actual compat surface | Importers only | YES | Same as above: migrate consumers, then delete. |
| `_frozen/index.py+reads.py+runtime.py+substrate.py` | NO | No (superseded; even research uses frozen copies elsewhere) | NO (RC index path explicitly dropped in Phase-10) | No (underscore-internal, no public path) | NO | SAFE TO REMOVE AFTER TEST (pre-v1). |
| Config `substrate`, `candidate_a` | NO (defaults suffice; diagnostics avoid the terms) | Old `runtime.toml` files (incl. shipped example!) | YES — RC config files use them | Only configs that set them (fail-closed to disabled + warning, so "breaks" = degrades loudly) | YES (RC config surface) | REMOVE AFTER MIGRATION WINDOW: add `reads` successor, warn on old keys, then drop. |
| `CANDIDATE_A_*` env family | NO | Dead with `_frozen/runtime.py` | NO | No | NO (research-internal) | Delete with `_frozen/runtime.py`. |
| `read_gate` receipt values | NO (route implies routing) | No | NO (new receipt schema) | Only `--json` consumers parsing the string | YES (shipped in receipts) | Retire values pre-v1 (still early; schema is RC-age). Replace with `admitted` + plain reason. |
| `src/librecalc_mcp/` | NO (not imported, not shipped) | Legacy tests import it | NO (COMPATIBILITY.md: UNSUPPORTED by this distribution) | No (never installed) | YES historically (old MCP server) | KEEP IN REPO, OUT OF PRODUCT. No action in product passes. |
| Old RC wheel in `product_hygiene/dist/` | NO | Archival evidence | It IS the RC artifact | No | It was the RC | KEEP AS ARCHIVE. Never ship, never delete. |
| `examples/basic/runtime.toml` using alias keys | Ships via `example` | n/a | Self-inflicted compat: the product's own example teaches the aliases | New users copy it | YES (installed example) | REWRITE pre-v1 to successor keys (part of the alias migration). |

## Staged deletion recommendation

1. **Pre-v1, step 1** (no compat surface): delete
   `_frozen/{index,reads,runtime,substrate}.py` + `CANDIDATE_A_*` handling.
   Gate: import scan clean + 27/27 + install check. Prerequisite: scope the
   extraction-pin test to retained modules.
2. **Pre-v1, step 2** (trivially small surface): retire `read_gate` research
   values; add `admitted` boolean. Gate: receipt-shape test update + 27/27.
3. **Migration window** (real surface): `lx_helpers` + frozen helpers unit;
   config alias rename (`reads` successor + deprecation warning). Gate:
   benchmark/test migration complete + example rewrite + 27/27.
4. **Never from product history**: keep `benchmark/`, `research/`,
   `product_hygiene/`, `product_integration_*`, old RC wheel as archives
   outside the installed package.

RC internal behavior deserves NO indefinite compatibility: the RC was
`0.2.0rc1`, never published to an index, with known-unsupported claims in its
own registry. Only surfaces a real external user could have adopted
(`lx_helpers` import, config keys, receipt JSON shape) get a window — and a
short one.
