# Phase 10C-A: release-readiness, product-surface, and evidence-attachment audit

Information gathering only. No product code, packaging, claims, or public
artifacts were changed. Audit of the working tree on 2026-09-28; all file and
line references verified by inspection. Companion files live in
`phase10c_audit/` (18 files); this report is the summary with the required
sections.

## VALIDATED PRODUCT STATUS CARRIED FORWARD

`PRODUCT INTEGRATION VALIDATED` under the Phase-10B gates, carried forward
unchanged. Cross-checks performed in this audit found no factual contradiction
in maintained source:

- 27/27 maintained product/process tests pass in the current tree (rerun here
  with system CPython 3.13 + repo `src` on `PYTHONPATH`).
- Reference-only transparency met the unchanged +10 ms budget in the pinned
  rerun (+6.39 ms median); Phase-10's +18.85 ms unpinned observation stands as
  archived evidence; timing is host-sensitive.
- Direct-contact benefit preserved (representative 0.608×, fixed-22 0.468×,
  warm only); P5 remains experimental, not in maintained product
  (bootstrap byte identity pinned in `P5_DISPOSITION.md`).
- No public claim or release artifact was changed by this audit.

## CURRENT PRODUCT ANATOMY

The product is `librecalc-agent 0.2.0rc1`: one Python package plus two native
executables. Full stage trace (install → launcher/CLI → observer → bootstrap →
admission → reference-only OR direct runtime → cache → script exit → capture →
receipt) is in `phase10c_audit/CURRENT_PRODUCT_ANATOMY.md`. In brief: a native
launcher execs a native observer (or delegates to the Python CLI); the observer
forks the user's real `python script.py` with a guarded `sitecustomize`; the
bootstrap classifies the script and either leaves openpyxl untouched
(reference-only) or installs the narrow direct-read runtime backed by
content-addressed artifacts; the observer snapshots XLSX bytes before/after,
runs a capture helper on change, and writes a receipt separating target status
from assurance status. Everything outside `src/librecalc_agent`,
`src/lx_helpers.py`, and `examples/basic` is evidence, research, or history —
not product.

## SMALLEST COHERENT V1

Per `phase10c_audit/V1_PRODUCT_BOUNDARY.md`: REQUIRED = `run`, `doctor`,
`status`, `example`, `--config`/`--no-runtime`/`--workdir`,
`enabled`/`capture`/`cache_dir` config, compact receipt, reference fallback +
`NOT_REQUESTED` truthfulness + "no task was run" blocking. OPTIONAL but keep =
`--json`/`--verbose`, `verbosity`, run-dir debug bundle (documented unstable).
POST-V1 = cache-management CLI, acceleration toggles beyond `enabled`,
routing-label API, Python library API, `lx_helpers`, non-Linux platforms,
derived-evidence outputs. Explicit non-goals: model client, recalc, sandboxing,
token/speed promises, broad equivalence, quota.

## MODULE OWNERSHIP

Census in `phase10c_audit/MODULE_OWNERSHIP_CENSUS.json`: 26 maintained runtime
files — 13 CORE PRODUCT, 2 PLATFORM IMPLEMENTATION (native C), 3
COMPATIBILITY/MIGRATION (frozen admission/capture + `lx_helpers` unit),
2 RESEARCH RESIDUE (`_frozen/{index,reads,runtime,substrate}`,
`src/librecalc_mcp`), 2 BUILD/PACKAGING, plus TEST SUPPORT. Headline: the
shipped `_frozen` package is three different things (live admission/capture:
keep; helper migration unit: windowed removal; old index runtime: dead),
and `src/librecalc_mcp` is repo history, not product (not imported, not shipped).

## PRODUCT SURFACE

Full enumeration in `phase10c_audit/PRODUCT_SURFACE_AUDIT.md`. The contract is
small and mostly honest: 4 CLI verbs, 6 config keys, 2 public env vars (+5
internal), exit codes 0/1/2/125/127/128+sig, a compact receipt, and a cache dir.
Pre-v1 cuts: retire `read_gate` research values from receipts, rename/retire
`substrate`+`candidate_a` keys, remove `lx_helpers` from the wheel, strip
`CANDIDATE_A_*`, declare run-dir internals unstable.

## REMOVAL CANDIDATES

Per `phase10c_audit/REMOVAL_AND_CONSOLIDATION_AUDIT.md`. SAFE TO REMOVE AFTER
TEST: `_frozen/{index,reads,runtime,substrate}.py` (~890 lines, zero maintained
consumers) + the `CANDIDATE_A_*` strip-list. REMOVE AFTER MIGRATION WINDOW:
`lx_helpers.py` + `_frozen/{helpers,helper_common,period_constants}.py` as one
unit (real import surface: benchmark scripts + 1 legacy test), and config keys
`substrate`/`candidate_a` (real config surface, incl. the product's own
example). Each candidate's consumers, history, wheel impact, and proving tests
are recorded in the audit file.

## CONSOLIDATION CANDIDATES

One genuine consolidation: `read_engine/cache.py` vs `artifact.py` duplicate
`sha_file`, `identity`, `artifact_key`, `paths`, and the
MAGIC/FORMAT/CONTRACT/DECODER/MAX constant block — single-source them (keeping
both `validate`/`ensure` layers, which are legitimate fast-gate vs semantic-gate
layering). Optional relocation: `_frozen/eligibility.py` → `read_engine/`
with byte-identical logic. Everything else examined (snapshots, config loading,
path hardening, admission gates, receipt writer vs synthesizer, launch layers,
merged-range handling, ZIP/XML bounds) is INTENTIONAL DEFENSE IN DEPTH or
LEGITIMATE DIFFERENT OWNERS — do not consolidate.

## COMPATIBILITY DEBT

Per `phase10c_audit/COMPATIBILITY_DEBT_AUDIT.md`. Staged plan: (1) pre-v1,
no-surface: delete dead frozen index modules + `CANDIDATE_A_*`; (2) pre-v1,
small-surface: retire `read_gate` values, add `admitted`; (3) migration window:
`lx_helpers` unit + config-alias rename with `reads` successor + example
rewrite; (4) never: keep research/evidence/old-RC archives outside the package.
The RC was unpublished `0.2.0rc1` with a self-negating claim registry — only
genuinely adopted surfaces (`lx_helpers` import, config keys, receipt JSON)
earn even a short window.

## DEPENDENCIES

Per `phase10c_audit/DEPENDENCY_AUDIT.md`. Production: `openpyxl==3.1.5` +
`lxml==6.1.3`, both REQUIRED, both exact-pinned, both lazily imported off the
reference path. Build: hatchling + `cc`. Dev: pytest (needed), ruff (needed),
pyyaml (unneeded by product tests). `sqlite3` becomes a zero-dependency once
the dead frozen modules go. Posture is already minimal — do not chase stdlib
replacement of lxml; add hashes/lock in release CI.

## INSTALLED WHEEL CONTENTS

Per `phase10c_audit/WHEEL_CONTENTS_AUDIT.md`. Ships: core runtime (~needed),
native observer+launcher (needed), examples (needed), frozen admission/capture
(needed), plus ~1,300 lines that should not ship (dead index modules +
`lx_helpers` unit). Ships no tests/benchmark/research/MCP — correct. No
`entry_points` by design (native launcher dispatches). Old RC wheel in
`product_hygiene/dist/` is archival, not representative. Release build must
verify no `__pycache__` and record the file list.

## CONFIGURATION SURFACE

Per `phase10c_audit/CONFIGURATION_AUDIT.md`. Six keys: `enabled`, `capture`,
`cache_dir`, `verbosity` (keep); `substrate`, `candidate_a` (migration aliases
— rename window, then drop). Fail-closed strictness (bad config → disabled +
WARNING) is public contract: document it. Minor wart: `--verbose` currently
implies JSON dump too — document or split post-v1.

## CACHE LIFECYCLE

Per `phase10c_audit/CACHE_LIFECYCLE_AUDIT.md`: verdict SHOULD FIX BEFORE
RELEASE BUT NOT FUNDAMENTAL. No quota/eviction; per-artifact bounds cap
single-run damage; realistic growth is MBs, heavy use reaches GBs of cruft
over months — no cliff. Manual deletion is safe; location is discoverable via
doctor/status. Pre-release minimum: document location/layout/safety/orphaning
+ show cache size in doctor/status. Automatic policy post-v1; do not freeze a
cache CLI now.

## FAILURE SEMANTICS

Full matrix in `phase10c_audit/FAILURE_SEMANTICS_MATRIX.md` (20 rows). The
product fails loudly and safely everywhere examined: blocking before launch
(missing observer, bad cache), reference fallback (artifacts, decoder,
admission, proxy escapes), split target/assurance statuses (helper failure →
125), shell-standard signal behavior, PY-identical reference failures. Four
doc-worthy surprises, none blocking: invalid-config degradation to no-observer
(loud WARNING, needs prominent docs), `capture=false`-vs-observer-present
distinction, opaque snapshot-bound error message, partial run dir on
pre-receipt observer death.

## SECURITY AND RESOURCE BOUNDARIES

Per `phase10c_audit/SECURITY_RESOURCE_AUDIT.md`: no BLOCKING ISSUE. 12 of 14
categories SUFFICIENT FOR TECHNICAL PREVIEW (ZIP/artifact/XML-direct bounds,
traversal, symlinks, perms, temp dirs, no-shell invocation, env hygiene,
atomic publication, snapshot/artifact ceilings, no executable deserialization).
Two NEEDS HARDENING (low severity, pre-release list): capture-path stdlib-ET
entity-expansion note/guard, and the cache-retention story above.

## LINUX RELEASE SCOPE

Per `phase10c_audit/PLATFORM_FEASIBILITY.md`. `Linux x86_64` alone is not
precise enough. Audited wording: Linux x86_64 with glibc, CPython 3.13,
installed from the provided wheel; other 3.11–3.14 accepted but untested;
built against recent glibc (2.43) so older distros are untested; local
filesystems only. Only one hard Linuxism exists (`/proc/self/exe` in the
launcher); all else is POSIX + libc. Pre-release: pick a manylinux baseline
(or per-distro builds) + release CI (rebuild + reinstall + 27 tests on the
declared floor).

## MACOS FEASIBILITY

LOW COST. Python + read engine + bootstrap + capture portable as-is;
observer needs a rebuild + validation pass (`nftw`/fork/exec/sigaction exist);
launcher needs a ~30-line `_NSGetExecutablePath` adapter; build hook needs a
macOS branch. No contract changes. Recommend fast-follow AFTER v1, not in v1.

## WINDOWS FEASIBILITY

HIGH COST. `fork`/`exec`/`wait`/`sigaction`/`nftw`/`fcntl`/`getuid` absent —
requires a Win32 observer rewrite, a launcher rewrite, a new cache-locking
protocol, and Windows interpretations of the signal vocabulary, private-dir
ACLs, and survival guarantee. A genuine port. Never a blocker; never promised.

## HOST SENSITIVE PERFORMANCE POLICY

Per `phase10c_audit/PERFORMANCE_VALIDATION_POLICY.md`: same-run PY controls
mandatory; paired per-workload effects; CPU-affinity + full host identity
recorded for any budget-gating run (pinning required for verdicts, not for all
timing); 2-repetition minimum with the ≤3-drifty-controls batch gate; always
ms + ratios + counts; functional support and perf characterization are separate
claims; NEVER average timings across hosts; `LINUX PERFORMANCE CHARACTERIZED`
needs 3+ host classes with per-host rows (future, not v1); regression =
same-host/protocol/population move outside the prior 95% interval with clean
gates both sides. The +10 ms budget stands; no data justifies raising it.

## EVIDENCE ATTACHMENT MATRIX

In `phase10c_audit/EVIDENCE_ATTACHMENT_MATRIX.md` (13 components × 6 columns).
Every mechanism is attached to its narrowest tested regime: ordinary-interface
and fallback claims to the 543-row oracle; direct-engine benefit to the 7
representative + 22 fixed contact-selected warm runs; reference-only cost to
the fixed-22 under two named protocols (+18.85 unpinned archived, +6.39 pinned);
assurance claims to the 5 changed-file + abrupt-exit fixtures; install claims
to the single-host clean install. Populations must never be mixed
(contact-selected ≠ representative ≠ market).

## CLAIMS SUPPORTED BY THE INTEGRATED PRODUCT

Per `phase10c_audit/CLAIM_TO_PRODUCT_MAP.md` — architecture: ordinary
Python/openpyxl program, conditional acceleration (as description), unsupported
→ reference, parser-avoidance on earned surface, persistent reuse, negative
admission inactivity, external observer. Assurance (tested scope): process
survival, changed-file detection, package replay/validation, freshness,
clean install (single-host). Deliberate true negatives: no model/API
dependency, no token claim, no universal speed claim.

## CLAIMS THAT REMAIN HISTORICAL OR CONDITIONAL

Conditional (controlled-host only): reference-only overhead (+6.39 ms pinned;
+18.85 ms unpinned archived), direct-contact reductions (0.608× rep-7, 0.468×
fixed-22, warm only), 2-process publication atomicity, single-config clean
install. Historical-only (never cite for the product): RC wall-time,
RC exactness-for-all-admitted, Phase-9 +8.73 ms, per-read/trace microfigures.

## CLAIMS THAT MUST NOT BE MADE

Any unqualified speedup; cold-start, write-acceleration, cost/token, or broad
equivalence claims; cross-host millisecond guarantees; task-correctness or
output-certification from capture; platform claims beyond tested Linux scope.

## DOCUMENTATION GAPS

Per `phase10c_audit/DOCUMENTATION_INVENTORY.md`: 4 NEEDS REVISION (install,
requirements, platforms, example), 7 MISSING (acceleration narrative,
fallback, cache, capture, diagnostics guide, uninstall, security paragraph,
LICENSE, changelog — license + changelog are the acute items). The frozen RC
registry + RC-era README/COMPATIBILITY actively contradict the new engine and
must be superseded by a v1 evidence boundary. Research/product separation is
clean: only the three known terminology leaks (alias keys, `read_gate`,
`CANDIDATE_A_*`), no manifest/fixture/phase coupling in runtime code.

## INITIAL RELEASE BLOCKERS

Only concrete unsafe/misleading/broken/operationally-unreasonable items:

1. **No version-control provenance for the product.** The entire maintained
   product (`src/librecalc_agent`, `src/lx_helpers.py`, `hatch_build.py`,
   product tests, all evidence dirs, all product docs) is UNTRACKED — git
   tracks 191 files, 468 paths untracked, and the only tracked `src/` is the
   legacy MCP server. Shipping an uncommitted tree means no identity, no
   reviewable diff, no reproducible release. BLOCKING.
2. **No license.** No LICENSE file exists; `pyproject.toml` sdist references
   `/LICENSE*` matching nothing. Cannot publish or invite external use.
   BLOCKING.
3. **Public docs describe the wrong product.** README / COMPATIBILITY /
   FINAL_CLAIM_REGISTRY describe the failed RC (old index path, old pins,
   SQLite matrix, negative registry). An external user following them is
   misled about what ships. BLOCKING (docs, not code).
4. **No release engineering.** Local wheel tag (not manylinux), glibc-2.43
   build host, single-config validation, no CI, no hashes/lock, stale
   in-tree `__pycache__`, version still `0.2.0rc1`. BLOCKING (process, not
   architecture).

Nothing architectural blocks: no semantic, assurance, security, or packaging
defect requiring redesign was found.

## PRE RELEASE CLEANUP

Ordered, each with its regression gate. No step changes behavior except where
named:

1. Commit the product tree to version control (blocker 1). Gate: clean
   `git status` story + tag-worthy tree.
2. Add LICENSE + decide version/changelog (blockers 2, 4-part). Gate: legal
   review, sdist/wheel contain license.
3. Rewrite user docs to the v1 boundary (blocker 3): install, requirements,
   platforms (audited wording), acceleration narrative, fallback, cache,
   capture, diagnostics/exit codes, limitations, uninstall, security note.
   Gate: docs-review checklist against this audit; example walkthrough passes.
4. Release CI on declared floor: rebuild wheel, clean install, 27/27,
   example run, wheel file-list artifact (blocker 4). Gate: green on floor.
5. Delete dead `_frozen/{index,reads,runtime,substrate}` + `CANDIDATE_A_*`
   handling (needs extraction-pin test scoping first). Gate: import scan
   clean + 27/27 + install check.
6. Retire `read_gate` research values (add `admitted`). Gate: receipt-shape
   test update + 27/27.
7. Single-source cache/artifact identity block. Gate: key-stability test +
   27/27 + concurrency test.
8. Cache visibility: size in doctor/status + retention docs (cache minimum).
   Gate: 27/27 + docs check.
9. Capture-path XML entity-expansion note/guard. Gate: 27/27 + adversarial-
   XML unit test.
10. Snapshot-bound error message naming the bound. Gate: unit test of message.
11. Open migration windows (can overlap v1): `lx_helpers` unit removal +
    config-alias rename with `reads` successor + example rewrite. Gate:
    consumer migration complete + 27/27.

## POST V1 WORK

Cache quota/eviction + `prune` (no frozen CLI yet); run-dir retention policy;
observer receipt-durability hardening; macOS fast-follow validation;
`--verbose`/JSON split; `_frozen/eligibility` relocation (cosmetic);
`diagnostics.libreoffice` retention decision; many-process/NFS/concurrency
stress; native-crash matrix; Phase-11 derivations via new additive surfaces;
`LINUX PERFORMANCE CHARACTERIZED` multi-host campaign.

## FUTURE DERIVATION EXTENSION POINTS

Per `phase10c_audit/FUTURE_DERIVATION_EXTENSION_POINTS.md`: no choice made.
Viable hosts ranked by coupling risk: new `analyze <run-dir>` command (LOW),
optional receipt-extension fields (LOW if optional/versioned), additive
diagnostic fields (LOW), agent-visible helper (MEDIUM — new public API),
Python library imports (HIGH — defer past cleanup). Rules: derive from frozen
artifacts only, never live internals; derivation failure must never move
target/assurance status; no research vocabulary in new surfaces; `run_dir` is
the handoff pointer.

## AGENT ZERO SUNK COST PRODUCT REVIEW

If this repo appeared today with no history, I would keep: the native
observer + launcher (small, honest, tested survival semantics), the guarded
bootstrap with fail-closed admission, the narrow read engine with its
version-bound atomic cache, the capture helper with mechanical validation, the
split target/assurance receipt, and the four CLI verbs. I would delete on
sight: the dead SQLite index modules, the experimental candidate runtime, the
top-level `lx_helpers` (a public API for someone else's benchmark), the
`CANDIDATE_A_*` env family, and the `substrate`/`candidate_a` config keys.
I would refuse to freeze: `read_gate` strings, run-dir internals, any cache
CLI, any library import path.

Phase 10B genuinely simplifies the architecture story: the product no longer
needs an excuse for its reference path. +6 ms for an external survivor that
catches `os._exit` is a defensible trade stated in one sentence — no P5
shortcut, no budget revision, no second bootstrap. The claim surface that
remains is small enough to be honest.

Is it one coherent product? Almost. `run` + observer + admission + engine +
capture + receipt is one thing: "ordinary Python, conditionally accelerated,
externally observed." The separable subsystem pretending to belong is the
inspection-helper/`lx_helpers` layer — a model-facing query API riding in a
runtime-observation product. Its removal is the single highest-clarity cut.
The MCP server is already correctly exiled (not shipped); leave it in the repo
as history and stop thinking about it.

## INDEPENDENT RELEASE RECOMMENDATION

**B. `READY AFTER BOUNDED PRE-RELEASE CLEANUP`.**

Required cleanup: the 11-step list under PRE RELEASE CLEANUP — dominated by
non-code blockers (version control, license, docs rewrite, release CI) plus
bounded code hygiene (dead-module deletion, `read_gate` retirement, identity
dedup, cache visibility, XML-entity note, error message). No semantic,
assurance, security-redesign, or architectural work is required. This verdict
authorizes only the next implementation phase; it changes no release files
or claims.

## NEXT IMPLEMENTATION PHASE

A release-implementation pass executing the PRE RELEASE CLEANUP list in order,
ending with: committed tree, license, v1 docs, green release CI on the
declared Linux floor, cleaned wheel contents, and a versioned release
candidate distinct from `0.2.0rc1`. Out of scope for that phase: performance
optimization experiments, P5 revival, deterministic-derivation research,
Windows/macOS ports, cache eviction algorithms, and any public claim beyond
the audited wording in the claim map.
