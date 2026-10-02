# Documentation inventory

What an initial external technical user needs, and where it stands.
Verdicts: READY / NEEDS REVISION / MISSING. No final docs written in this phase.

| Needed doc | Status | Notes |
|---|---|---|
| Install (wheel from release, Linux x86_64) | NEEDS REVISION | README's `pip install .` path describes a checkout install of the OLD RC; installed-command behavior, wheel tag, and glibc recency are undocumented. |
| Requirements (Python, deps, LibreOffice, platform) | NEEDS REVISION | README/COMPATIBILITY.md describe RC-era matrix (SQLite, RC pins, POSIX-everywhere). Needs the audited Linux scope + tested-vs-accepted Python split. |
| Supported platforms | NEEDS REVISION | Currently "EXPECTED_BUT_UNTESTED" mush. Needs the exact honest wording from the platform audit. |
| Minimal run example | NEEDS REVISION | `example` command works, but the shipped `runtime.toml` teaches alias keys and no hand-holding narrative exists for first-run → receipt. |
| What acceleration does (and doesn't) | MISSING | No v1-accurate narrative: conditional direct reads, narrow contract, warm-only benefit, no cold/write/token story. The frozen RC registry actively contradicts the new engine and must be superseded by a new evidence boundary doc. |
| Fallback behavior | MISSING | Matrix exists in this audit; no user-facing page. |
| Cache (location, safety, cleanup, no-quota) | MISSING | Design doc exists (`PRODUCT_CACHE_ARTIFACT_DESIGN.md`) but is internal; user-facing retention/cleanup story missing (pre-release minimum). |
| Effect capture (what it validates, what it doesn't) | MISSING | Failure policy doc is internal; users need "mechanical package delta, not task correctness" in plain words. |
| Diagnostics (`doctor`/`status`, receipts, exit codes) | NEEDS REVISION | Receipt schema doc is internal and accurate; user-facing exit-code + receipt-field guide missing. |
| Known limitations | NEEDS REVISION | `known_product_limits.json` is RC-era (index-lifetime, SQLite). Needs a v1-accurate rewrite from this audit. |
| Uninstall / cache cleanup | MISSING | `pip uninstall` + delete cache dir; trivial to write, must exist. |
| Security posture (not a sandbox, perms, no network) | MISSING | One honest paragraph + pointer. |
| License | MISSING | No LICENSE file in repo; `pyproject.toml` sdist references `/LICENSE*` which matches nothing. BLOCKER (see final report). |
| Changelog / version story | MISSING | `0.2.0rc1` still; no CHANGELOG. Needed at release even if brief. |

## Research/product separation note (§25 result)

Maintained runtime code depends on research terminology in exactly three
places, all flagged for retirement (not redesign):

1. Config keys `substrate` / `candidate_a` (`config.py`).
2. Receipt `read_gate` values (`runner.py` synthesis of classifier output).
3. `CANDIDATE_A_*` strip-list (`runner.py`) + dead `_frozen/runtime.py`.

No benchmark terminology, experiment manifests, fixture knowledge, archived
paths, or phase-specific semantics leak into the runtime path. `profile_ns` /
`times` / `events` in run dirs are diagnostic residue, not research coupling —
document as unstable and move on. Evidence files live outside the package as
required.
