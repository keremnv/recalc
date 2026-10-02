# Compatibility — recalc-agent 0.2.0rc3

Current product document. `SUPPORTED` describes this candidate's intended
contract. `TESTED` means local mechanical checks actually ran.
`EXPECTED_BUT_UNTESTED` is not a promise; `UNSUPPORTED` is outside the release
boundary. (The `0.2.0rc1` matrix this file replaces is preserved in git
history; rc1's SQLite-index rows do not apply to rc2, which has no SQLite
path in the maintained runtime.)

| Component/environment | Status | Evidence or limit |
|---|---|---|
| Linux x86_64 with glibc, local filesystem | SUPPORTED | Release baseline in `research/history/phase10c_b/LINUX_RELEASE_BASELINE.md`. |
| CPython 3.13, openpyxl 3.1.5, lxml 6.1.3 | TESTED | Clean wheel install + 27+ maintained product/process tests + smoke battery. Exact pins in `pyproject.toml`. |
| CPython 3.11/3.12/3.14 | EXPECTED_BUT_UNTESTED | Metadata accepts 3.11–3.14; release CI covers the declared floor only. |
| Other openpyxl/lxml versions | UNSUPPORTED by this candidate | The direct decoder mimics openpyxl semantics; upgrades need re-validation. |
| LibreOffice (any recent) present | TESTED detection only | `--version` probe; no recalc/scoring experiment in this phase. |
| LibreOffice absent | SUPPORTED for Python-only work | `OPTIONAL_NOT_AVAILABLE`; `--require-libreoffice` fails preflight. Saving formulas does not recalculate them. |
| macOS | UNSUPPORTED (fast-follow candidate) | Audited LOW cost port; not implemented or validated. |
| Windows | UNSUPPORTED (separate port) | Audited HIGH cost; needs a Win32 observer + receipt dialect. |
| Network filesystems, containers | EXPECTED_BUT_UNTESTED | Atomic replace + `flock` + fsync assumed; must be verified per environment. |
| Simultaneous writers to a task directory; concurrently edited script source | UNSUPPORTED | No locking/coordination. Concurrent same-source *cache builds* are safe (atomic publication); concurrent *script edits* are not. |
| `.xlsm`/VBA and rich Excel content | UNSUPPORTED as a preservation guarantee | Direct reads cover `.xlsx`/`.xlsm` cell values only; use ordinary openpyxl flags (e.g. `keep_vba=True`) yourself. Capture cannot recover content the script discarded. |
| Malformed workbook/package | SUPPORTED reference-error behavior | Optional engine must not veto ordinary execution; reference openpyxl can still reject the original bytes. |
| Stale/corrupt/unavailable derived artifact | SUPPORTED fallback | Rebuild; reference serving when build fails. Old-version entries are orphaned, never served. |
| Global Python interposition, arbitrary shells/notebooks, nested-Python acceleration | UNSUPPORTED | `run` wraps one local Python file; bootstrap is guarded to that file. Nested interpreters use ordinary Python. Pre-existing user `sitecustomize` is untested with the product hook. |
| Historical MCP/UNO server | UNSUPPORTED by this distribution | Source preserved in repo, not installed. No UNO binding needed. |
| `lx_helpers` top-level import | See disposition | `research/history/phase10c_b/LX_HELPERS_DISPOSITION.md` (removed pre-v1 with vendored benchmark shim retained in `benchmark/`). |
| Model clients, credentials, network | No dependency | The harness has no model client or credential store. Configure any external coding agent separately. |

The harness executes the supplied Python with the user's permissions; it is
not a sandbox. Only isolated installation checks and mechanical tests ran for
this candidate — never model calls or SpreadsheetBench.
