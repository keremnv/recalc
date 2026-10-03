# 0.2.0 release verification record

Release branch: `release/0.2.0` (from rc5 `35cbd43`).
Mechanism set: rc5 unchanged. Gates: `gates.py` (this directory).

## Results

- release commit: (filled at tag time — see tag annotation)
- tag: `v0.2.0` (no prior tag convention existed)
- master after promotion: (filled post-promotion)
- product suite: 49/49 green
- full suite: 893 passed, 13 skipped, 0 failed (4 research
  failures resolved test-only: jinja2 skip-guard, 2× import-path
  fix, 1× stale-fixture fix; product-path impact none)
- adversarial: 40/40, zero failures
- canon parity vs rc5: 52/52 equal
- corruption: 12/12 rejected
- A/B CLI differential: not re-run (identical product code to
  rc5 except version string; canon+adversarial+corruption cover
  the bump; R6 frozen suites stand)
- native build: clean (`cc -std=c11 -O2 -Wall -Wextra -Werror`,
  both binaries, from deleted state)
- wheel: `recalc_agent-0.2.0-py3-none-linux_x86_64.whl`
  (33 files, no staging/probe/pyc, native present, METADATA 0.2.0)
- sdist: `recalc_agent-0.2.0.tar.gz`
- fresh install: wheel → clean venv green
- `--version`: `0.2.0`; `doctor`: green
- Quick Start: example + 3 runs + status green, DIRECT_RUNTIME
  observed, assurance PASS
- reference smoke: `values_only` script → REFERENCE_FAST_PATH
  with correct output
- cache upgrade (rc5→0.2.0): rc5-seeded cache → 0.2.0 run exits
  0, correct output, DIRECT_RUNTIME, artifact BUILT under
  rotated key; old entries inert; no manual action
- concurrency smoke: `test_concurrent_publication` green
  (simultaneous build, both exit 0, artifact valid)
- lifecycle smokes: build-and-reuse, source-change
  invalidation, corrupt-cache rebuild, version-mismatch
  rebuild — all green
- tested platform: Linux x86_64, CPython 3.13.12,
  openpyxl==3.1.5, lxml==6.1.3, local filesystem
- known limitations: per CHANGELOG 0.2.0 entry (narrow
  contract; no cold/write/token/universal claims; no eviction;
  no sandbox; Linux-only tested)
- publication: git tag + master push (this task); no GitHub
  release convention exists (reported, not invented); PyPI:
  NOT_PUBLISHED — no established/available publication path

## Pre-tag decision: RELEASE

All MUST gates pass; release-only diff is narrow (tests +
docs + version/changelog + key vector); no unexplained
regression; no product-code change beyond the version string.
