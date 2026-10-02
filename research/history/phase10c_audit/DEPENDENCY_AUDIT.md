# Dependency audit

## Production dependencies (`pyproject.toml`)

| Dependency | Class | Why needed | Import/startup impact | Wheel impact | Security/maintenance | Version constraint | Replaceable? |
|---|---|---|---|---|---|---|---|
| `openpyxl==3.1.5` | REQUIRED | Reference parser + fallback + utility modules (Translator, number formats, datetime, formula classes) + example scripts | Imported lazily (only when a script uses it or fallback engages); reference-only path never imports it in bootstrap | External wheel (~300 KB) | Pinned exact; mature, low-churn; XLSX parsing is the main attack surface but reference behavior is the compatibility anchor | `==3.1.5` — exact pin; upgrades need re-validation (decoder mimics its semantics) | No. It IS the reference implementation. |
| `lxml==6.1.3` | REQUIRED | Direct OOXML decode (`direct.py:13`, hard import) | Imported only on admitted path (via artifact build); reference-only path never imports it | External wheel (binary, ~MBs) | Pinned exact; C extension; parser configured `resolve_entities=False, no_network=True, huge_tree=False` | `==3.1.5`-style exact pin | In principle stdlib `xml.etree` (the OLD `_frozen/reads.py` used it), but the integrated decoder's behavior + bounds were validated with lxml; swapping parsers re-opens semantic risk for no product benefit. Keep. |

## Build-only

| Dependency | Class | Notes |
|---|---|---|
| `hatchling>=1.25` | BUILD ONLY | Build backend. Lower-bound only; unpinned upper bound is a minor reproducibility wart — pin in release CI. |
| `cc` (system C compiler) | BUILD ONLY | Compiles observer + launcher with `-std=c11 -O2 -Wall -Wextra -Werror`. No autotools/cmake. Wheel install needs no compiler. |

## Test-only / dev (`[project.optional-dependencies] dev`)

| Dependency | Class | Notes |
|---|---|---|
| `pytest>=8` | TEST ONLY | Runs the 27 product tests. Unpinned upper; fine for dev, pin in CI. |
| `pyyaml>=6` | TEST ONLY (arguably RESEARCH ONLY) | No maintained product module imports yaml (verified by import scan). Used by legacy research/benchmark tests. Do not install for product validation. |
| `ruff>=0.16,<0.17` | TEST ONLY (lint) | Pinned range; per-file ignores cover legacy UNO/test probes. Product code is ruff-clean by inspection scope. |

## Implicit / stdlib reliance worth naming

- `sqlite3`: used ONLY by dead `_frozen/{index,runtime,substrate}.py`. After
  their removal, the product has zero SQLite reliance. (COMPATIBILITY.md's
  SQLite rows describe the old RC and go stale — see docs inventory.)
- `tomllib` (3.11+): justifies `requires-python >=3.11`. Correct floor.
- `fcntl`, `os.getuid`, `os.execve`: POSIX-only stdlib; fine for Linux v1,
  part of Windows port cost (see platform feasibility).

## Possibly removable

- `pyyaml` from dev deps for product purposes (keep if legacy tests still run
  in the same env; the 27 product tests do not need it).
- Nothing else. The production set is already minimal: 2 runtime deps, both
  load-bearing. Do not chase stdlib replacement of lxml.

## Security/maintenance posture

- Exact pins (`==`) for both runtime deps: good for reproducibility; release CI
  should add hashes (lock file) per the known product limits gap.
- No network, no credentials, no subprocess-beyond-product, no deserialization
  of untrusted pickles (artifact codec is JSON/zlib with full validation).
- Native code is `-Werror`-clean C11 with no third-party C deps.
