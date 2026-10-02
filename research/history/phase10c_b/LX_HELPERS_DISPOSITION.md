# lx_helpers disposition

Verdict: `REMOVE_PRE_V1`

## Zero-sunk-cost answers

- **Shipped for current users or historical experiments?** Historical.
  The installed top-level `lx_helpers` (`src/lx_helpers.py`, backed by
  `_frozen/helpers.py`) has ZERO consumers anywhere in the repository:
  no product module imports it, no test imports it, and every benchmark
  mention resolves to `benchmark/inspection_helpers/lx_helpers.py`
  (a benchmark-local shim backed by `benchmark/.../reference_api.py`)
  or to string/regex mentions in scoring scripts. Verified by import scan
  2026-09-28.
- **Is its contract documented?** Only in the superseded rc1 README paragraph
  (now rewritten out) and benchmark-internal notes. No v1 contract exists.
- **Maintenance/dependency cost?** It ships 3 extra frozen modules
  (`helpers`, `helper_common`, `period_constants`, ~390 lines) in the wheel
  and forces the wheel to carry a model-facing query API inside a
  runtime-observation product.
- **Implied product promise?** Yes — keeping it implies a supported
  model-facing helper API, which v1 explicitly does not offer.
- **Can benchmarks vendor a historical copy?** They already do: the
  benchmark-local shim is self-contained and does not import the installed
  module. Nothing migrates; nothing breaks.

## Decision

Remove pre-v1 as one unit: `src/lx_helpers.py`,
`src/librecalc_agent/_frozen/{helpers,helper_common,period_constants}.py`,
the `pyproject.toml` force-include + sdist entries, and stale
`__pycache__`. No deprecation window is needed because there are no
consumers to migrate — announcing a window for zero users would only freeze
the surface longer. Recorded here and in CHANGELOG/COMPATIBILITY.

## Regression gate

- Repo-wide import scan for `lx_helpers` (installed) and
  `_frozen.{helpers,helper_common,period_constants}`: clean except
  benchmark-local shim + historical docs.
- Maintained suite green; clean wheel install; wheel file-list check.
