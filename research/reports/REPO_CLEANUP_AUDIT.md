# Repository cleanup audit — diagnostic pass only

Date: 2026-09-25. No file was deleted, moved, renamed, or rewritten to produce this
audit, except creating this file itself. All findings below are from static reads,
import/package analysis, and one observed test run (`tests/test_product_hygiene.py`:
27 passed).

Working-tree facts that frame everything else:

- Working tree is ~7.5 GB excluding `.venv`/`.git`/`benchmark-data`, plus 30 GB in
  `benchmark-data/` (gitignored nested SpreadsheetBench-2 checkout).
- Only ~190 paths are git-tracked; **422 paths are untracked**, including almost all
  top-level `*.md` reports and evidence directories. The "frozen research record" the
  freeze docs describe is largely **not in git**. There are also staged (`A`) and
  modified (`M`) entries, i.e. work in progress on top.
- There is **no `LICENSE` file**, although `pyproject.toml` sdist config references
  `LICENSE*` and this audit is for public release.

Product framing used for classification: the intended public surface is an ordinary
Python/openpyxl agent harness (`librecalc-agent` 0.2.0rc1) with optional invisible
runtime mechanics. Historical MCP/UNO architectures and benchmark research are
evidence to preserve, not product to present.

Final claim boundary: `FINAL_CLAIM_REGISTRY.md` (2026-09-24) supersedes all earlier
positive wording. It states there is **no packaged RC speed claim** (22/22 eligible
scripts slower, median T/C 2.017), **no exactness claim** (4 genuine semantic
failures), **no token/cost claim**, and **no capability-equivalence claim**. Anything
still worded positively against those four points is stale for public purposes even
when it was accurate as dated research history.

---

## 1. Inventory with classification

### Top level, product and release

| Path | Classification | Notes |
| ---- | -------------- | ----- |
| `README.md` | `CURRENT_PRODUCT` (needs wording update, §3) | Install/run/doctor/status docs. Links to `COMPATIBILITY.md`, `FINAL_ARCHITECTURE_FREEZE.md`, `PRODUCT_HYGIENE_REPORT.md`, `docs/HISTORICAL_MCP_README.md`, `examples/basic/runtime.toml`. Modified in working tree. |
| `COMPATIBILITY.md` | `CURRENT_PRODUCT` | RC boundary matrix (SUPPORTED/TESTED/EXPECTED_BUT_UNTESTED/UNSUPPORTED). Accurate; keep. |
| `pyproject.toml` | `CURRENT_PRODUCT` | Package `librecalc-agent`, entry point, wheel/sdist allowlists, pytest/ruff config. Contains historical references (§3, §8). Modified in working tree. |
| `examples/basic/` (4 files) | `CURRENT_EXAMPLE` | `create_input.py`, `update.py`, `read.py`, `runtime.toml`. Ordinary openpyxl; shipped in wheel. |
| `product_hygiene/` | `CURRENT_RELEASE_INFRA` | RC validation evidence: `extraction_manifest.json` (read by `test_product_hygiene.py`), `rc_manifest.json`, install/test logs, `dist/*.whl` (frozen 0.2.0rc1 wheel, 43 KB). Small (404K). Keep at top until Batch D. |
| `FINAL_CLAIM_REGISTRY.md`, `RESEARCH_RECORD_FREEZE.md`, `FINAL_PRESENTATION_HANDOFF.md`, `CLAIM_BACKLOG.md` | `CURRENT_RELEASE_INFRA` | Frozen claim boundary + research-stop records (Sep 24). Public wording source of truth. |
| `PRODUCT_HYGIENE_REPORT.md` | `CURRENT_RELEASE_INFRA` | RC build/install record (Sep 22). Accurate as build record; capability language predates the negative Sep 24 validation — needs registry caveat, not rewrite (it is evidence). |
| `RC_ACCELERATION_CLAIM_VALIDATION_REPORT.md`, `rc_acceleration_validation/` (1.2G) | `RESEARCH_EVIDENCE` | Final preregistered negative result. Frozen + hashed. Must be preserved exactly. |
| `RC_WARM_ACCELERATION_CHARACTERIZATION_REPORT.md`, `rc_warm_acceleration_characterization/` | `RESEARCH_EVIDENCE` | Warm-reuse verdict `WARM_PRODUCT_STATE_NOT_SUPPORTED_BY_RC`. Frozen. Preserve exactly. |
| `FINAL_ARCHITECTURE_FREEZE.md`, `final_architecture_freeze/` (396K) | `RESEARCH_EVIDENCE` | Sep 22 architecture decision record, superseded on claims by Sep 24 registry but still the cited "scoped technical record" from README. Preserve exactly; README link must keep resolving after any move. |
| `PRODUCT_PRESENTATION_HANDOFF.md` | `RESEARCH_EVIDENCE` (stale claims) | Sep 22 claims registry ("exact EARNED", "can pay materially SUPPORTED") directly contradicted by Sep 24 registry. Preserve as history; never use for public wording. |

### Source

| Path | Classification | Notes |
| ---- | -------------- | ----- |
| `src/librecalc_agent/` (`cli.py`, `config.py`, `diagnostics.py`, `runner.py`, `__init__.py`, `__main__.py`) | `CURRENT_PRODUCT` | CLI + config + diagnostics + subprocess launcher. 398 lines total. |
| `src/librecalc_agent/_frozen/` (11 modules) | `CURRENT_PRODUCT` | Frozen read/index/capture/helper mechanics, extracted from research sources (§2, §4). `test_no_research_imports` enforces no `benchmark`/`librecalc_mcp` imports. |
| `src/librecalc_agent/_bootstrap/sitecustomize.py` | `CURRENT_PRODUCT` | Process-local child bootstrap via `PYTHONPATH`; never installed globally. |
| `src/lx_helpers.py` | `CURRENT_PRODUCT` | 4-line re-export of reference-openpyxl helpers. Shipped at wheel top level. |
| `src/librecalc_mcp/` (server, backend, domain; 1.2 MB, ~5.7k lines) | `HISTORICAL_ARCHITECTURE` | The old MCP/UNO semantic-tool product. Excluded from wheel/sdist; imported only by `benchmark/*`, research tests, and `scripts/smoke_uno.py`. The single most confusing product-looking path. |

### Tests

| Path | Classification | Notes |
| ---- | -------------- | ----- |
| `tests/test_product_hygiene.py` | `CURRENT_PRODUCT_TEST` | The only product test file: 18 test defs / 27 tests (observed passing). Covers extraction parity, no-research-imports, run configs, capture bytes, fallback, diagnostics. |
| `tests/test_fail_closed_substrate.py`, `tests/test_transparent_runtime.py`, `tests/test_inspection_helpers.py`, `tests/test_closure_transfer_audit.py`, `tests/test_compact_evidence_delivery.py`, `tests/test_matched_compiled_treatment.py`, `tests/test_integration_repairs.py`, `tests/test_scheduler_terminal_paths.py`, `tests/test_frontend_projection_and_runtime.py` | `RESEARCH_EVIDENCE` (evidence-bearing regressions) | Test the research sources that `_frozen/` was extracted from, or the corrective fail-closed replay. Keep runnable; they guard extraction provenance. See §10. |
| Remaining ~74 files in `tests/` + `tests/fixtures/` | `RESEARCH_RUNNER` tests / historical-architecture tests | Cover `benchmark/*`, `librecalc_mcp`, UNO backends, probes, sweagent libs. They make the suite look 84-files broad; product behavior is 1 file. See §10. |
| `tests/__pycache__/` (~150 stale `.pyc`, incl. pytest-8/9 and py3.13/3.14 variants) | `CACHE_OR_TEMP` | Regenerable. |

### Benchmark, data, runners

| Path | Classification | Notes |
| ---- | -------------- | ----- |
| `benchmark/` (249 entries, 17 MB) | `RESEARCH_RUNNER` | Experiment runners, probes, analysis, slices, pattern catalog, sweagent tool worlds, and — importantly — the **frozen sources that `_frozen/` was extracted from** (see §4). Also `benchmark/README.md` (old semantic-tool framing). |
| `benchmark/sweagent/` (`librecalc/`, `calc_query/`, `calc_translate_fill/`, `formula_index/`, `view_xlsx_ambient/`, `*.yaml`) | `RESEARCH_RUNNER` | Vendored SWE-agent tool worlds + configs. `librecalc/lib` is on pytest `pythonpath`. |
| `benchmark/slices/` (~50 JSON slice manifests) | `RESEARCH_EVIDENCE` | Frozen task cohorts referenced by many studies. |
| `benchmark/pattern-catalog/` | `RESEARCH_EVIDENCE` | Method + cases + census. |
| `benchmark-data/` (30 GB, gitignored, nested `.git`) | `RESEARCH_EVIDENCE` (external, do not commit) | SpreadsheetBench-2 checkout: dataset zips, trajectory archive, official evaluator. Two tests `sys.path.insert` its `evaluation/` dir. Keep gitignored; public repo should document how to obtain it, not vendor it. |
| `candidate_a_a1_checkpoint_sitecustomize.py` (top level) | `RESEARCH_RUNNER` | Checkpoint-only bootstrap (`import benchmark.candidate_a_live_runtime`). Misplaced at top level; belongs with its study. |

### Evidence / artifact directories (~50, mostly untracked)

All `RESEARCH_EVIDENCE` unless noted. Sizes from `du`:

- Large: `compiled_context_sidecar_ab/` (3.0G), `candidate_a_a1_checkpoint_rerun_01/` (1.1G), `candidate_a_live/` (341M), `stochastic_work_census/` (288M), `token_affordance_discovery/` (210M), `transparent_capture_replay/` (198M), `scheduler_live_validation/` (187M), `representative_architecture_checkpoint/` (187M), `token_claim_discovery/` (166M), `track_c_terminal_projection/` (139M), `thin_architecture_checkpoint/` (113M), `compact_evidence_delivery/` (104M), `formula_error_feedback_discovery/` (68M), `closure_transfer_audit/` (68M), `resource_demand_autopsy/` (47M), `candidate_a_a1_classifier/` (31M), `default_harness_deterministic_execution/` (21M), `batch_write_helper_ab/` (17M), `candidate_a_a1_checkpoint/` (16M), `live_transparent_runtime_ab/` (11M).
- Small: `architecture_evidence_freeze/`, `architecture_transfer_audit/`, `authority_frontier_live_probe/`, `authority_frontier_probe/`, `candidate_a_contact_ceiling/`, `candidate_a_shadow_interposition/`, `closure_transfer_audit/`, `control_python_audit/`, `fact_normalized_read_replay/`, `formula_error_delivery_probe/`, `formula_error_feedback_probe/`, `inspection_efficiency_ab/`, `mutation_authoring_audit/`, `official_score_probe/`, `output_role_planner_live_probe*/`, `post_mutation_verification_audit/`, `read_side_v2_adjudication/`, `scheduler_group_priority_probe/`, `structural_projection_discriminator*/`, `targeted_runtime_replication/`, `token_claim_review/`, `track_c_terminal_projection/`, `transparent_python_read_census/`.
- `results/` (2 llama regression JSONs) | `RESEARCH_EVIDENCE` (orphan: no references found in `tests/` or sampled benchmark runners; preserve, verify before any move).
- Top-level `*.csv` / `*.json` (~30 files, e.g. `actuation_loss_trace.csv` 11M, `integrated_feasibility_census.json` 5.2M) | `RESEARCH_EVIDENCE` | Loose evidence that belongs beside its study report. Two (`output_role_occurrence_contrast.*`) are staged (`A`) in git.

### Docs

| Path | Classification | Notes |
| ---- | -------------- | ----- |
| `docs/HISTORICAL_MCP_README.md` | `HISTORICAL_ARCHITECTURE` (correctly labeled) | The preserved old product README. README links here for the old interface. Accurate as history. |
| `docs/architecture.md`, `docs/roadmap.md`, `docs/benchmark-plan.md`, `docs/PROJECT_CONTEXT.md` (3380 lines), `docs/harness-value-packet.md`, `CONTRIBUTING.md` | `OBSOLETE_PRODUCT_SURFACE` | Describe the MCP/UNO semantic-tool product as the *current* architecture/loop/roadmap. Directly contradict the RC. Highest-doc-priority quarantine/flag. |
| `docs/public-trajectory-audit.md`, `docs/viz-isa-diagnosis.md` + `.json` | `RESEARCH_EVIDENCE` | Dated study records. |
| `spreadsheet_harness_architecture_checkpoint.md` (Sep 7) | `HISTORICAL_ARCHITECTURE` | Predates both freezes. |
| `ARCHITECTURE_EVIDENCE_FREEZE.md` + ~60 other top-level `*_REPORT.md` / `*_AUDIT.md` / `*_REVIEW.md` | `RESEARCH_EVIDENCE` | Dated study reports. Accurate-as-history; several contain claim language superseded by the Sep 24 registry (§3). |
| `ASTRA_TOKEN_DIAGNOSIS_PACKET.md` (78K), `ASTRA_FORMULA_ERROR_FEEDBACK_DIAGNOSIS.md` (31K) | `RESEARCH_EVIDENCE` | Independent forensic reviews. Internal. |
| `CLAUDE.md` (0 bytes) | `CACHE_OR_TEMP` (dead) | Empty. Safe to remove in Batch A. |

### Scripts, config, environment

| Path | Classification | Notes |
| ---- | -------------- | ----- |
| `scripts/extract_product_runtime.py` | `CURRENT_RELEASE_INFRA` | The provenance tool: extracts `_frozen/` from research sources, writes `product_hygiene/extraction_manifest.json`. `test_frozen_extraction_exact` verifies its output. Keep with product until Batch D. |
| `scripts/smoke_uno.py`, `scripts/start_libreoffice.sh` | `HISTORICAL_ARCHITECTURE` | Manual UNO tooling for the old backend. `smoke_uno.py` imports `librecalc_mcp`, uses `tests/fixtures/smoke.csv`. |
| `scripts/install_into_personal_projects.sh` | `OBSOLETE_PRODUCT_SURFACE` | Copies tree to `librecalc-mcp`, runs `uv sync --extra dev` against a stale lock. Dead as a procedure. |
| `uv.lock` | `OBSOLETE_PRODUCT_SURFACE` | Locks `librecalc-mcp 0.1.0` (editable) + `mcp/openai/uvicorn/...`; contains **zero** `openpyxl`/`lxml` entries. Fully stale; canonical install is `pip install .`. Preserve content (historical dep record) but remove from the install path. |
| `.venv/` (104M) | `CACHE_OR_TEMP` | Gitignored. Local dev env. |
| `.env`, `.secrets/` (contains `openrouter_api_key.b64`) | Secret, gitignored | Correctly ignored. Never commit. Contents not inspected beyond filenames. |
| `.pytest_cache/`, `.ruff_cache/`, all `__pycache__/` (463 dirs) | `CACHE_OR_TEMP` | Regenerable. Note: `__pycache__/` is already gitignored but present everywhere. |
| `benchmark/sweagent/*/__pycache__/`, `src/**/__pycache__/` | `CACHE_OR_TEMP` | Same. |

---

## 2. Real shipped product surface

From `pyproject.toml` (wheel `packages` + `force-include`, sdist `include`) and the
frozen wheel in `product_hygiene/dist/` (`librecalc_agent-0.2.0rc1-py3-none-any.whl`,
43,266 bytes; 24 installed files verified in the RC validation report):

**Installed package files**

- `librecalc_agent/__init__.py` (`__version__ = "0.2.0rc1"`), `__main__.py`
- `librecalc_agent/cli.py` — entry point `librecalc-agent`, subcommands
  `example | doctor | status | run`
- `librecalc_agent/config.py` — single `[runtime]` TOML surface + fail-closed `load()`
- `librecalc_agent/diagnostics.py` — credential-free checks (python/packages/sqlite/
  optional modules/cache/LibreOffice binary)
- `librecalc_agent/runner.py` — script launcher: classify → prepare index → subprocess
  with `PYTHONPATH=_bootstrap` → capture → per-run logs + `last_run.json`
- `librecalc_agent/_bootstrap/sitecustomize.py` — child-process-only interposition boot
- `librecalc_agent/_frozen/` — `eligibility, reads, index, substrate, runtime,
  capture, delta, validate, helpers, helper_common, period_constants`
- `lx_helpers.py` (top level) — re-export of `inspect/inspect_ranges/periods/search`
- `librecalc_agent/example/` — the 4 `examples/basic` files
- Metadata only: `pyproject.toml` name/version/requires-python. No shipped config
  file; defaults compiled in, user config via `--config`/`LIBRECALC_CONFIG`.

**Reachability view**

```text
public CLI (librecalc-agent)
  example  -> shutil copy of librecalc_agent/example/*          (no deps)
  doctor/status -> config.load -> diagnostics.check/status
      -> stdlib (platform, sqlite3, shutil, subprocess) + importlib probes
  run -> config.load -> runner.run
      -> openpyxl (required import gate)
      -> _frozen.eligibility.classify(script source)            (A1 gate)
      -> _frozen.index.reset + _frozen.substrate.prepare        (SQLite index build)
      -> subprocess [sys.executable, script] with
           PYTHONPATH=<pkg>/_bootstrap, CANDIDATE_A_* + LIBRECALC_RUN_CONTEXT env
         -> _bootstrap/sitecustomize.boot
           -> _frozen.runtime.main -> _frozen.reads proxy loader (openpyxl patch)
      -> _frozen.capture.snapshot_xlsx / capture_wrap_timed    (mutation assurance)
      -> per-run logs under <cache>/runs/<uuid>/ + last_run.json

optional components (all fail closed to ordinary openpyxl)
  compiled read path: eligibility + index + substrate + runtime + reads
  capture path:       capture + delta + validate
  helpers:            lx_helpers -> _frozen.helpers (always reference openpyxl)

external dependencies
  required:  openpyxl==3.1.5 (+et_xmlfile transitive)
  pinned:    lxml==6.1.3 (code-tolerant: diagnostics reports OPTIONAL_NOT_AVAILABLE)
  stdlib:    sqlite3 (missing sqlite disables indexing), tomllib, xml.etree
  system:    libreoffice/soffice binary, detection-only via --version
  dev-only:  pytest, pyyaml, ruff
```

**Looks product-facing but is NOT distributed:** `src/librecalc_mcp/` (entire old
server), `benchmark/`, `tests/`, `docs/`, `scripts/`, `uv.lock`, all evidence dirs.
Exclusion is by wheel/sdist allowlist, verified by `test_no_research_imports` and the
isolated-install check (`isolated_imports.log`).

---

## 3. Stale architecture language

### Product surface proper — clean except registry drift

`README.md`, `COMPATIBILITY.md`, `pyproject.toml`, `src/librecalc_agent/`,
`src/lx_helpers.py`, `examples/` contain **none** of: EditPlan, Task IR, obligation
IR, grounding, ProgramGroup, ExecutionUnit, dependency closure, compiled context,
spreadsheet DSL, planner, semantic MCP, deterministic executor, substrate-backed
helpers, token-saving, speed, equivalence, or formula-error capability language.
(The only `token` hits are `helpers.py` comments about JOIN anchor tokens — accurate,
unrelated.)

BUT the Sep 24 claim registry moved the boundary after the README was written:

| Occurrence | Classification |
| ---------- | -------------- |
| README "optional conservative read acceleration", "Eligible reads can use the conservative fast path", "Acceleration depends on the workload" | **needs wording update** — the frozen RC showed 22/22 slower fresh invocations and 4 admitted-read semantic failures. "Acceleration"/"fast path" implies a benefit this RC did not deliver. Per `FINAL_PRESENTATION_HANDOFF.md`, demos should use `--no-runtime`. |
| README "mutation capture observes and checks" / "Capture is assurance, not a formula-correctness check" | **still accurate** (matches registry: assurance supported, failure-prevention not established). |
| `librecalc_agent` identifiers: `candidate_a` config key, `CANDIDATE_A_*` env vars, `compiled_substrate_available`, `effective_compiled_serving_and_freshness`, "Compiled reads available" (CLI output) | **research-only naming in product paths** — mechanically accurate, but leaks Candidate-A/compiled-substrate archaeology into user-visible surface. Rename later (Batch E); document meanwhile. |
| `_frozen/*` "Frozen implementation; packaging extraction only" | **still accurate**. |
| `lx_helpers` "always backed by reference openpyxl" | **still accurate** (substrate-backed helpers removed per freeze). |

### Obsolete product voice (stale / misleading for current product)

| Location | Language | Classification |
| -------- | -------- | -------------- |
| `docs/architecture.md` | MCP surface → domain → UNO; "librecalc-mcp exposes a world" | **misleading** — describes old product as current. |
| `docs/roadmap.md` | MCP v0/v1 milestones, "semantic tools + program execution", token/tool-call metrics | **misleading** — old roadmap as current. |
| `docs/PROJECT_CONTEXT.md` (3380 lines) | Compiled-agent architecture, Task IR/Edit Plan/scheduler/ProgramGroups sidecar studies | **research-only** history file sitting in `docs/`; stale as guidance. |
| `docs/benchmark-plan.md`, `docs/harness-value-packet.md` | Semantic-world hypothesis, "LibreCalc MCP world" | **research-only**; MCP product framing. |
| `CONTRIBUTING.md` | "Reproduce with the current MCP surface", benchmark-task loop | **stale** — wrong contribution loop for the RC. |
| `benchmark/README.md` | grid-v1/semantic-snapshot-v2/calc_read/calc_program arms | **research-only** (fine once quarantined; confusing at top level). |
| `PRODUCT_PRESENTATION_HANDOFF.md` | "exact on earned surface EARNED", "can pay materially SUPPORTED" | **stale** — contradicted by `FINAL_CLAIM_REGISTRY.md`. Preserve, never cite publicly. |
| `FINAL_ARCHITECTURE_FREEZE.md` | "51/51 exact traces", "positive substrate economics on tail", retain A+A1 | **research-only, partially stale** — accurate Sep 22 record; Sep 24 RC validation found packaged-RC semantic failures + no speed. Keep as evidence with registry caveat. |
| `pyproject.toml` ruff section | "architecture.md designates backend/uno*.py as the only layer…" | **stale pointer** — config comments reference the historical arch doc. Harmless while code stays; update on quarantine. |
| `pyproject.toml` pytest `pythonpath` | includes `benchmark/sweagent/librecalc/lib` | **research-only** path baked into test config. |
| `scripts/install_into_personal_projects.sh` | `librecalc-mcp` target, `uv sync --extra dev` | **obsolete** — old name + stale lock. |
| `LX_REPO_ROOT` default `/home/kerem/Desktop/Personal Projects/librecalc-mcp` (6 benchmark files) | hardcoded home path + old repo name | **research-only**; machine-specific. |
| `uv.lock` | `librecalc-mcp 0.1.0`, mcp/openai/uvicorn deps | **obsolete** — not the RC dependency set. |

---

## 4. Duplicate / competing implementations

| Responsibility | Implementations | Verdict |
| -------------- | --------------- | ------- |
| Workbook loading / indexed reads | (P) `_frozen/{reads,index,substrate,runtime}.py` ⟸ extracted from (R) `benchmark/candidate_a_shadow_interposition.py`, `benchmark/inspection_helpers/{index,substrate}.py`, `benchmark/candidate_a_live_runtime.py` | **active product + frozen research source**, bound by AST-parity test. Keep both; do not edit `_frozen` by hand (edit source + re-extract, or freeze the link). Older rivals: `benchmark/workbook_spine_sqlite.py`, `workbook_grounding_spine.py`, `closed_world_resolver.py` (superseded retrieval impls). |
| Candidate A/A1 admission | (P) `_frozen/eligibility.py` ⟸ (R) `benchmark/run_candidate_a1_classifier_repair.py`; plus `candidate_a_a1_classifier/`, `run_candidate_a_a1_checkpoint.py`, `finalize_candidate_a_a1_checkpoint*.py` | **active + historical predecessors**. |
| Helpers | (P) `src/lx_helpers.py` + `_frozen/helpers.py` (reference openpyxl) ⟸ (R) `benchmark/inspection_helpers/reference_api.py`; rival (R, removed from product) `benchmark/inspection_helpers/api.py` (substrate-backed); shims `benchmark/inspection_helpers/lx_helpers.py`, `benchmark/mutation_helpers/shim_c1.py`; experimental `benchmark/mutation_helpers/batch.py` (`write_cells/write_formulas`) | **one active + several experimental**. `api.py` vs `reference_api.py` is the exact substrate-backed-vs-reference split the freeze decided — keep both as evidence of the decision. |
| Mutation capture | (P) `_frozen/capture.py` ⟸ (R) `benchmark/representative_checkpoint.py`; (P) `_frozen/{delta,validate}.py` ⟸ (R) `benchmark/transparent_runtime/{delta,validate}.py`; leftover (R) `benchmark/transparent_runtime/{transaction,telemetry}.py` (never extracted) | **active + research remainder**. `transaction.py`/`telemetry.py` have no product counterpart — research-only. |
| Freshness / invalidation | (P) `_frozen/index.py` generations/completion markers; older `workbook_spine_sqlite` schema; grounding-probe freshness checks | **active + superseded**. |
| Index creation | (P) `_frozen/substrate.prepare` ⟸ (R) `inspection_helpers/substrate.py`; plus ad-hoc builders in checkpoint runners | **active + historical**. |
| Configuration | (P) `librecalc_agent/config.py` TOML `[runtime]`; (R) `benchmark/experiment_config.py`, sweagent `*.yaml`, `CANDIDATE_A_*`/`LX_REPO_ROOT` env vars | **separate surfaces, no conflict** — but env-var overlap is guarded in `runner.py` (strips `CANDIDATE_A_*`). |
| CLI execution | (P) `librecalc-agent run` (classify→prepare→subprocess→capture); (R) `ab_local_runner.py`, `run_openrouter_slice.py`, `run_cursor_slice.py`, `run_kimi_frozen.py`, `scheduler_terminal_replay.py`, … | **one product + many historical runners**. |
| UNO recalculation | (H) `src/librecalc_mcp/backend/{uno,uno_charts}.py`; (R) official-evaluator container path; (P) `diagnostics.libreoffice()` detection-only | **historical + research + thin product probe**. No product recalc path (by design). |
| Agent-facing surfaces | (H) `src/librecalc_mcp/server.py` MCP tools; (R) `benchmark/sweagent/*/bin/calc_*` + `lib/calc_tool.py` | **two historical surfaces**, neither shipped. |
| Benchmark scoring | `run_evaluation.py`, `score_openrouter_run.py`, `ab_score.py`, `ab_checkpoint_score.py`, `formula_index_score.py`, … | **multiple generations of runners** — research archaeology, preserve. |
| Bootstrap | (P) `_bootstrap/sitecustomize.py`; (R) top-level `candidate_a_a1_checkpoint_sitecustomize.py`; (R) `candidate_a_live_runtime.main()` | **active + misplaced research twin** (top-level file belongs with its study). |

Test-only-in-product-paths / product-in-research-paths: none found in `src/`
(`test_no_research_imports` enforces the boundary). Reverse direction exists:
`benchmark/prepare_rc_acceleration_validation.py`,
`benchmark/run_rc_acceleration_validation.py`,
`benchmark/analyze_rc_acceleration_validation.py` are **product-validation drivers
living under research paths** (they drive the installed RC through its public CLI).
Consider promoting them to release infra (Batch D) or leaving with a pointer.

---

## 5. Dead / unreachable code

| Candidate | Evidence | Caveat |
| --------- | -------- | ------ |
| `src/librecalc_mcp/*` as product | Not in wheel/sdist allowlists; zero imports from `librecalc_agent`; importers are only `benchmark/*` (~30 files), ~15 research tests, `scripts/smoke_uno.py` | **Live as research dependency** (many benchmark modules + tests import it). Quarantine, don't delete. |
| `scripts/install_into_personal_projects.sh` | Old package name, `uv sync` against stale lock, one-shot copy script; no references | Dead procedure. Archive. |
| `scripts/smoke_uno.py`, `scripts/start_libreoffice.sh` | Manual UNO tooling; no test/CI references found (tests import `UnoCalcBackend` directly) | Likely dead; keep with UNO code until Batch D confirms. |
| `uv.lock` | Locks old package, lacks openpyxl/lxml; README install path ignores it | Dead as lockfile; keep content as historical dep record. |
| `CLAUDE.md` | 0 bytes | Dead. |
| `results/` (2 JSONs) | No references in `tests/` or sampled benchmark runners | Orphan evidence — preserve; verify with a full-text search before moving. |
| `benchmark/sweagent/{calc_query,calc_translate_fill,formula_index,view_xlsx_ambient}/` | Older tool-world generations; `formula_index/lib` still on 9 tests' `sys.path` | Partially live (`formula_index/lib` imported by tests). Verify per-dir in Batch D. |
| `benchmark/pattern-catalog/cases` etc. | Evidence, referenced by pattern tests | Live (tests). |
| Top-level loose `*.csv/*.json` | Most unreferenced from code; cited by their study reports | Evidence, not dead. Reunite with studies. |
| `src/librecalc_agent/*` | All reachable from CLI (verified by reading `cli.py`/`runner.py`/`diagnostics.py`) | None dead. |
| `tests/test_transparent_runtime.py` imports | Only stdlib in header — verify body before judging | Check in Batch D; likely tests `_frozen`-equivalent logic via path insert. |

Dynamic-loading caveat: product `importlib` uses are all statically visible
(`openpyxl`, `lxml`, `librecalc_agent._frozen.*`); diagnostics probes enumerate names
explicitly. Research tests load some modules by file path (`importlib.util`) and by
`sys.path.insert("benchmark")` (43 test files), so a plain `grep ^import` miss does
**not** prove a `benchmark/*.py` file is unreferenced — Batch D must check
`sys.path`-relative imports and `importlib.util.spec_from_file_location` call sites.

---

## 6. Research material to quarantine

Principle: **commit first, then `git mv`**. Almost everything below is untracked, so
the immediate preservation risk is failure to commit, not deletion.

| Material | Proposed eventual home | Preservation requirement |
| -------- | ---------------------- | ------------------------ |
| `benchmark/` (runners, probes, sweagent worlds) | `research/benchmark/` (or keep name `research/runners/`) | Exact; `_frozen` extraction sources + parity test depend on paths — move together with import/`sys.path`/extraction-script updates + full test run (Batch D). Lowest-risk alternative: keep `benchmark/` at top with a `README` banner. Decide before moving. |
| Frozen hashed studies: `rc_acceleration_validation/`, `rc_warm_acceleration_characterization/`, `token_claim_discovery/`, `token_affordance_discovery/`, `final_architecture_freeze/`, `representative_architecture_checkpoint/`, `candidate_a_a1_checkpoint*/`, `architecture_evidence_freeze/` | `research/evidence/` | **Byte-exact** — reports cite SHA-256 manifests inside these dirs. `git mv` only; never edit contents. |
| Other evidence dirs (~35, §1) | `research/evidence/` (small) | Exact via `git mv`. |
| Giant dirs: `compiled_context_sidecar_ab/` (3.0G), `candidate_a_live/` (341M), `stochastic_work_census/` (288M), `transparent_capture_replay/` (198M), `scheduler_live_validation/` (187M), `token_claim_discovery/` (166M), `track_c_terminal_projection/` (139M), `thin_architecture_checkpoint/` (113M), `compact_evidence_delivery/` (104M) | `research/evidence/` **or** Git LFS / release-artifact storage | Exact, but 7+ GB total should not bloat the public clone. Prefer: commit pointer/manifest in repo, bulk bytes in LFS or versioned artifact storage. Decide per-dir by whether reports cite internal hashes (if hashed → must stay content-addressable). |
| Top-level study reports (`*_REPORT.md`, `*_AUDIT.md`, `*_REVIEW.md`, ASTRA packets, `TOKEN_*`, `FORMULA_ERROR_*`, etc.) | `research/evidence/` alongside their dirs, or `research/reports/` with fixed relative links | Exact — several are hash-manifested (`evidence_source_hashes.json`). Keep report↔dir relative links working. |
| `PRODUCT_PRESENTATION_HANDOFF.md`, `FINAL_ARCHITECTURE_FREEZE.md` | `research/evidence/` with a top-level pointer | Exact; README currently links the freeze doc — update link or keep a stub. |
| Top-level loose `*.csv`/`*.json` evidence | Reunite with their study dir under `research/evidence/` | Exact. |
| `benchmark-data/` (30G, gitignored) | **Stay gitignored, stay out of repo** | Do not commit. Document acquisition (official SpreadsheetBench-2 source) in `research/README.md`. |
| `benchmark/slices/`, `benchmark/pattern-catalog/` | Move with `benchmark/` | Exact (frozen cohorts). |
| `results/` | `research/evidence/results/` | Exact; verify references first. |
| `candidate_a_a1_checkpoint_sitecustomize.py` | `research/evidence/candidate_a_a1_checkpoint/` | Exact. |
| `src/librecalc_mcp/`, `scripts/smoke_uno.py`, `scripts/start_libreoffice.sh`, `docs/HISTORICAL_MCP_README.md` | `research/archive/historical-mcp/` (code + smoke + readme together) | Exact; update the ~45 importer path references (`benchmark/*`, tests, ruff ignores) or keep an import shim during transition. |
| `docs/architecture.md`, `docs/roadmap.md`, `docs/benchmark-plan.md`, `docs/PROJECT_CONTEXT.md`, `docs/harness-value-packet.md`, `docs/public-trajectory-audit.md`, `docs/viz-isa-diagnosis.*`, `spreadsheet_harness_architecture_checkpoint.md`, `CONTRIBUTING.md` (after rewriting a new one) | `research/archive/` | Exact. |
| `uv.lock` | `research/archive/uv.lock.historical` (or delete after recording dep list — prefer archive) | Content preserved; remove from install path. |
| `product_hygiene/` | **Remain where it is** (release infra + test dependency) | Exact — `test_product_hygiene.py` reads `extraction_manifest.json` here. |
| `scripts/extract_product_runtime.py` | **Remain** (`scripts/`) | Exact — provenance tool + test dependency. |
| `*.sqlite` under evidence dirs | Stay with their study | Some are cited evidence (e.g. shared substrates); some are regenerable caches (e.g. `rc_warm_*/feasibility_probe/cache/`) — distinguish per-dir in Batch A, never bulk-delete. |
| `*.xlsx` under evidence dirs | Stay with their study | Evidence inputs/outputs. |
| `.secrets/`, `.env` | **Never in repo** (already ignored) | N/A. |

Nothing in this section should be "removed from the public repository entirely":
everything listed is either evidence (preserve) or regenerable cache (gitignore).

---

## 7. Generated / cache / temp material

| Material | Status | Recommendation |
| -------- | ------ | -------------- |
| `__pycache__/` (463 dirs, incl. stale py3.13/3.14 × pytest-8/9 `.pyc`) | Already gitignored, present on disk | `REMOVE_GENERATED` from disk (Batch A). Present even in `src/` and `benchmark/sweagent/*/lib`. |
| `.pytest_cache/`, `.ruff_cache/` | Already gitignored | `REMOVE_GENERATED` from disk (Batch A). |
| `product_hygiene/dist/*.whl` | Build output **but frozen evidence** (hash cited in `RESEARCH_RECORD_FREEZE.md`) | `KEEP` exactly. Do not rebuild/overwrite. |
| `feasibility_probe/cache/` sqlite + run dirs under `rc_warm_acceleration_characterization/` | Regenerable probe cache, inside a frozen study | `KEEP` (frozen-study integrity beats tidiness; they're small). |
| `closure_transfer_audit/work/` | Already gitignored (`closure_transfer_audit/work/` in `.gitignore`) | Leave ignored; disk cleanup optional. |
| `.venv/` (104M) | Gitignored | Keep ignored; disk-local. |
| `.venv-product/` (created by README install path) | **Not** in `.gitignore` | **Add ignore rule** (Batch A). Users following the README would otherwise create an untracked 100M+ dir. |
| `.dist/` entry in `.gitignore` | Odd but harmless | Leave. |
| OS/editor files | `.DS_Store` already ignored | No action. |
| `*.log` under evidence dirs (e.g. `launch.log`, `default_harness_deterministic_execution/launch.log` 21M) | Committed-or-to-be-committed evidence in some studies; clutter in others | Do **not** blanket-ignore `*.log`. Decide per study dir in Batch A. |
| `last_run.json`, `<cache>/runs/` | Live outside repo (XDG cache) | No repo action. |

**Missing ignore rules to add (Batch A):** `.venv-product/`. Consider: `*.egg-info/`
(already), `.coverage/`, `*.tmp`. Do not add `*.sqlite`, `*.xlsx`, `*.log`, `*.csv`,
`*.json` — too broad, would hide evidence.

**Committed evidence vs accidental clutter:** `product_hygiene/*.log|*.json|*.xml`
are deliberate RC records (keep). `__pycache__`/`.pytest_cache`/`.ruff_cache` are
accidental (remove from disk). Evidence-dir `work/`/`runs/`/`reps/` trees are
deliberate study records even when bulky (keep; LFS decision separately).

---

## 8. Names and package identity

| Identity slot | Current value | Historical value | Notes |
| ------------- | ------------- | ---------------- | ----- |
| Directory name | `librecalc-mcp` | — | Working-tree dir; also in `LX_REPO_ROOT` default and install script. |
| Package name (`pyproject`) | `librecalc-agent 0.2.0rc1` | `librecalc-mcp 0.1.0` (`uv.lock`, `src/librecalc_mcp/__init__.py`) | Current name is consistent in metadata + entry point. |
| Import names | `librecalc_agent`, `lx_helpers` | `librecalc_mcp` (57 files across `src/tests/benchmark` import it) | Old import stays alive via research code. |
| CLI | `librecalc-agent` (`example/doctor/status/run`) | MCP server (no CLI; `mcp` lib `MCPServer("librecalc-mcp")` in `server.py`) | Single entry point, no duplicates. |
| README/docs voice | `librecalc-agent`, ordinary Python/openpyxl | `docs/*`, `CONTRIBUTING.md`, `HISTORICAL_MCP_README.md`: LibreCalc MCP world / UNO / semantic tools | Old voice dominates `docs/` + 76 top-level `.md`. |
| Config/env/cache | `LIBRECALC_CONFIG`, `LIBRECALC_RUN_CONTEXT`, `~/.cache/librecalc-agent` | `LIBRECALC_HOST/PORT` (UNO), `CANDIDATE_A_*`, `LX_REPO_ROOT` | `LIBRECALC_*` prefix shared by product + history. |
| Release metadata | `librecalc-agent` wheel/sdist | `uv.lock`: `librecalc-mcp` | Lock is stale (§5). |

**Does the current name overstate LibreOffice identity?** The package is
`librecalc-agent` with tagline "ordinary Python/openpyxl harness". LibreOffice appears
only as an optional recalculation/validation dependency (detection-only in code).
The `librecalc` stem is inherited history, not a functional claim — defensible, but a
rename would touch: `pyproject` (6 refs), 7 code files, cache-dir default, env-var
prefix, wheel name, README/COMPATIBILITY, `product_hygiene` manifests (hashed —
renaming invalidates RC identity hashes, so a rename implies a **new release
identity**, consistent with the freeze's "new package identity" rule), and cosmetically
~80 frozen evidence files that **must not be rewritten** (hash-manifested). Bluntly:
product-code blast radius is small (~15 files); evidence blast radius is huge and
frozen. Any rename keeps old strings inside `research/` permanently — plan for that.

---

## 9. Examples audit

| Example | Runs on RC? | Teaches current arch? | Verdict |
| ------- | ----------- | --------------------- | ------- |
| `examples/basic/create_input.py` | Yes — ordinary openpyxl; exercised in `product_hygiene/example_create_input.log` | Yes | `KEEP` |
| `examples/basic/update.py` | Yes — `example_update.log`; quoted in README | Yes | `KEEP` |
| `examples/basic/read.py` | Yes — `example_read.log` | Yes (A1-eligible read shape) | `KEEP` |
| `examples/basic/runtime.toml` | Yes — copied by `librecalc-agent example` | Yes, but exposes research-named keys (`candidate_a`, `substrate`) | `KEEP`; key renames are Batch E only. No unsupported claims. |

No other examples exist. No dead/historical examples. The set is minimal and correct;
it needs no archival work — only protection from research clutter around it.

---

## 10. Tests audit

84 files in `tests/`. One is product; the rest are research/history. No `conftest.py`;
43 test files `sys.path.insert("benchmark")`, 9 insert
`benchmark/sweagent/formula_index/lib`, 2 insert
`benchmark-data/SpreadsheetBench-2/evaluation`, 5 insert `src`.

| Class | Files (representative) | Verdict |
| ----- | ---------------------- | ------- |
| Current product behavior + regression/fail-closed | `test_product_hygiene.py` (27 tests, observed passing) | `KEEP`. The entire product suite. |
| Evidence-bearing regressions for `_frozen` provenance | `test_fail_closed_substrate`, `test_transparent_runtime`, `test_inspection_helpers`, `test_closure_transfer_audit`, `test_compact_evidence_delivery`, `test_matched_compiled_treatment`, `test_integration_repairs`, `test_scheduler_terminal_paths`, `test_frontend_projection_and_runtime`, `test_default_harness_deterministic_execution`, `test_compiled_context_sidecar`, `test_compiled_model_discriminator`, `test_official_score_probe`, `test_authority_frontier`, `test_integrity_gate`, `test_experiment_metrics`, `test_run_report` | `KEEP` runnable. Do not delete: they guard the research sources `_frozen/` was extracted from and the corrective replay. May move with `benchmark/` in Batch D if imports follow. |
| Historical MCP/UNO architecture | `test_uno_backend`, `test_uno_backend_validation` (need live LibreOffice; `uno` marker), `test_uno_chart_ranges`, `test_memory_backend`, `test_chart_*` (4), `test_commit_*` (2), `test_tool_schema_contract`, `test_score_and_chart_tools`, `test_formula_translation`, `test_write_formula_semantics`, `test_xlsx_format_persist`, `test_xlsx_metadata_repair`, `test_boundary_continuations`, `test_blank_ranking`, `test_catalog_gate`, `test_benchmark_observations` | Quarantine with research code (Batch B/D). UNO-marked ones need a live server. |
| Research mechanism / probe validation | `test_edit_plan*` (2), `test_execution_unit`, `test_program_group`, `test_task_obligation_*` (2), `test_temporal_*` (2), `test_workbook_grounding`, `test_workbook_spine_sqlite`, `test_canonical_choice`, `test_closed_world_resolver`, `test_staged_synthesis_probe`, `test_synthesis_decomposition`, `test_operand_availability`, `test_target_classification`, `test_formula_*` (~13: completion/dependency/frontier/hierarchy/index/liveness/operational/schema/synthesis/target/verifier), `test_scheduler_group_priority*` (2), `test_structural_projection_discriminator`, `test_mismatch_census`, `test_paired_autopsy`, `test_pattern_catalog`, `test_calc_query`, `test_interface_ablation_arms`, `test_kimi_frozen`, `test_openrouter_runner`, `test_provider_timeout_hierarchy`, `test_read_budget`, `test_score_openrouter_run` | Quarantine with research code (Batch B/D). Several need provider keys / docker / benchmark-data. |

Where the suite misleads: a visitor running `pytest` sees 84 files / hundreds of
tests spanning MCP servers, planners, schedulers, and model probes — implying a
broad supported API. The supported product is the 27 tests in one file. Fix by
quarantine + a tests/README split ("product suite" vs "research suite"), not by
deleting evidence-bearing tests.

---

## 11. Dependencies audit

| Dependency | Source | Verdict |
| ---------- | ------ | ------- |
| `openpyxl==3.1.5` (+ `et_xmlfile` transitive) | `pyproject` required | **Product-required.** Import-gated in `runner.py`. |
| `lxml==6.1.3` | `pyproject` required (pinned) | **Product-pinned, code-optional.** Diagnostics tolerates absence; COMPATIBILITY documents the stdlib-XML difference. Keep pin for RC identity. |
| stdlib `sqlite3` | CPython | **Product-optional at runtime** (missing sqlite disables indexing). Tested 3.51.1. |
| LibreOffice binary (`libreoffice`/`soffice`) | System | **Product-optional** (detection-only `--version`); required only for recalc/validation tasks. No UNO Python bindings needed. |
| `pytest`, `pyyaml`, `ruff` | `pyproject` dev extra | **Dev-only.** Note `pyyaml` is used by research tests/sweagent configs, not by product code. |
| `mcp`, `openai`, `python-dotenv`, `uvicorn/starlette/*`, `typer`, `pydantic`, … | `uv.lock` only | **Historical/research-only.** Needed by `src/librecalc_mcp/server.py` and benchmark runners, not installed by `pip install .`. |
| Docker / official SpreadsheetBench container, model provider accounts | Benchmark harness, benchmark-data | **Research-only.** No product path touches them. |
| `python3-uno` / LibreOffice Python bindings | System (historical UNO backend) | **Historical-only.** Explicitly not required by the RC. |

Separation recommendation: packaging is already correctly separated (`pip install .`
pulls only openpyxl+lxml). The confusion is presentational: `uv.lock` advertises the
old dep set, and research tests need undeclared extras. Fix by archiving `uv.lock`
(Batch B) and, if research reproducibility is wanted later, adding a separate
`research/requirements.txt` (Batch D) — do not add research deps to `pyproject`.

---

## 12. Public-release confusion risks (ranked)

1. **76 top-level `.md` + ~50 evidence dirs bury the product.** A visitor lands in
   research archaeology, not a README-led product. Root is 7.5 GB.
2. **`src/librecalc_mcp/` (1.2 MB) reads as current product architecture.**
   It's the excluded old MCP/UNO server sitting beside the real package in `src/`.
3. **Claim conflict across front-page docs.** README says "read acceleration / fast
   path"; `PRODUCT_PRESENTATION_HANDOFF`/`FINAL_ARCHITECTURE_FREEZE` say exactness +
   tail economics earned/supported; `FINAL_CLAIM_REGISTRY` (latest, authoritative)
   says no speed, no exactness, no token, no equivalence claims. A visitor cannot
   tell which is true. (Answer: the registry.)
4. **84 test files imply a broad supported API.** Product behavior is 27 tests in
   one file; the rest test MCP servers, planners, probes.
5. **`docs/architecture.md` + `docs/roadmap.md` + `CONTRIBUTING.md` describe a
   different product** (MCP semantic tools, UNO loop) as current.
6. **`benchmark/` (249 files) at top level looks product-facing**, including
   model/provider invocation (`run_openrouter_slice.py`) and scoring.
7. **Name soup.** Repo dir `librecalc-mcp`, package `librecalc-agent`,
   `uv.lock` says `librecalc-mcp 0.1.0`, `LX_REPO_ROOT` hardcodes the old path.
8. **Stale `uv.lock`** (no openpyxl/lxml; mcp+openai) contradicts the documented
   `pip install .` path; `uv sync` would build the wrong product.
9. **No `LICENSE` file** despite sdist `LICENSE*` reference and release intent —
   a public-repo blocker, not confusion per se, but the most visible gap.
10. **422 untracked paths: the cited research record is not in git.** A fresh
    clone loses nearly every artifact the freeze/registry docs cite by hash.

Honorable mentions: `product_hygiene/` name reads as hygiene tooling rather than
"RC validation evidence"; `CANDIDATE_A_*`/`candidate_a` user-visible naming;
`.secrets/` + `.env` with provider keys (correctly ignored, but a public repo should
say so once); `results/` orphan JSONs; hardcoded `/home/kerem/...` paths in
shims (research-only, but greppable).

---

## 13. Minimal target repository shape

Proposed (not created). Principles: front page carries the product; research keeps
one door (`research/README.md`); frozen hashed bytes move by `git mv` only; nothing
rewritten inside evidence.

```text
README.md                  # product front page (registry-compliant wording)
COMPATIBILITY.md
LICENSE                    # ADD (public-release blocker)
pyproject.toml             # product-only; ruff/pytest stanzas updated post-move
CONTRIBUTING.md            # rewritten for RC loop (ordinary Python + product tests)

src/
  librecalc_agent/         # unchanged product package
  lx_helpers.py

scripts/
  extract_product_runtime.py   # provenance tool (release infra)

tests/
  test_product_hygiene.py      # the product suite
  README.md                    # "product suite here; research suite under research/"
  fixtures/                    # only fixtures the product suite needs

examples/
  basic/                   # unchanged

product_hygiene/           # RC validation evidence (test dependency; keep at top)
  dist/                    # frozen wheel (byte-exact, never rebuilt)

research/
  README.md                # what research/ is, claim boundary pointer, acquisition
                           # notes for benchmark-data, "do not rewrite history"
  benchmark/               # moved benchmark/ (runners, probes, sweagent, slices)
  evidence/                # all hashed + study dirs, study reports, loose csv/json
  archive/
    historical-mcp/        # src/librecalc_mcp + smoke_uno + start_libreoffice +
                           # HISTORICAL_MCP_README
    docs-history/          # old architecture/roadmap/PROJECT_CONTEXT/benchmark-plan/
                           # harness-value-packet + superseded handoffs
    uv.lock.historical
    install_into_personal_projects.sh
```

Deliberately absent: `docs/` product folder (front page carries it until real need),
extra READMEs per study (reports already exist), `results/` at top, `benchmark-data/`
(remains gitignored + documented), `CLAUDE.md` (empty), any new doc except the two
small READMEs above.

Open structural questions (decide before Batch B): (a) move `benchmark/` under
`research/` (43+ test `sys.path` inserts + extraction script + parity test must move
in lockstep) vs keep at top with a banner README; (b) LFS/artifact storage for the
~7 GB giant evidence dirs vs committing bytes; (c) whether the old `docs/` history
lives in `research/archive/` or a separate history branch.

---

## 14. Cleanup action matrix

Actions: `KEEP` | `KEEP_AND_RENAME_LATER` | `MOVE_TO_RESEARCH` |
`MOVE_TO_RESEARCH_ARCHIVE` | `MOVE_TO_PRODUCT` | `REMOVE_GENERATED` | `GITIGNORE` |
`CONSOLIDATE` | `REWRITE_PUBLIC_SURFACE` | `REVIEW_MANUALLY`.

| Path | Current role | Actual reachability | Proposed action | Risk | Evidence preservation requirement |
| ---- | ------------ | ------------------- | --------------- | ---- | --------------------------------- |
| `README.md` | Product front page | Shipped (sdist); first visitor contact | `REWRITE_PUBLIC_SURFACE` (wording only, Batch C) | Low (no code) | N/A — but keep a copy of the RC-era README with the RC record if wording changes materially. |
| `COMPATIBILITY.md` | RC boundary | Shipped (sdist) | `KEEP` | None | N/A (add registry pointer in Batch C). |
| `pyproject.toml` | Packaging + test/lint config | Shipped; defines wheel | `KEEP` (+ Batch D: update ruff/pytest paths after moves) | Low | N/A. |
| `src/librecalc_agent/` (+ `_frozen`, `_bootstrap`) | Product runtime | Shipped in wheel; sole CLI dependency | `KEEP` | None | N/A. |
| `src/lx_helpers.py` | Product helper re-export | Shipped at wheel top level | `KEEP` | None | N/A. |
| `examples/basic/` | Product example | Shipped in wheel; verified by logs | `KEEP` | None | N/A. |
| `product_hygiene/` incl. `dist/*.whl` | RC validation evidence | Read by `test_product_hygiene.py`; cited by reports | `KEEP` | None | Byte-exact (hashes cited in freeze/registry). |
| `FINAL_CLAIM_REGISTRY.md`, `RESEARCH_RECORD_FREEZE.md`, `FINAL_PRESENTATION_HANDOFF.md`, `CLAIM_BACKLOG.md` | Claim boundary + stop records | Cited as source of truth | `KEEP` | None | Byte-exact (hashed record). |
| `PRODUCT_HYGIENE_REPORT.md` | RC build record | Linked from README | `KEEP` | None | Exact; add registry-caveat pointer, don't rewrite history. |
| `scripts/extract_product_runtime.py` | Provenance/extraction tool | Run manually; output verified by test | `KEEP` | None | Exact (update paths only if `benchmark/` moves, Batch D). |
| `tests/test_product_hygiene.py` | Product suite | Run by pytest; observed 27 passed | `KEEP` | None | N/A. |
| `candidate_a` / `substrate` / `compiled` user-visible names in product | Config keys, env vars, CLI output | User-facing | `KEEP_AND_RENAME_LATER` | Medium (config compat, cache paths, docs) | Only after product description frozen (Batch E). |
| `benchmark/` | Research runners + `_frozen` sources | Imported by 83 tests; extraction sources | `MOVE_TO_RESEARCH` | **High** — 43+ `sys.path` inserts, extraction script, parity test, `pythonpath` move in lockstep | Exact; full test run before/after; commit before moving. Alternative: keep at top with banner (decide first). |
| `benchmark/slices/`, `benchmark/pattern-catalog/` | Frozen cohorts/evidence | Referenced by studies + tests | Move with `benchmark/` | Medium | Exact. |
| `benchmark/sweagent/` | Historical tool worlds | `lib` on pytest path; imported by tests | Move with `benchmark/` | Medium | Exact. |
| `rc_acceleration_validation/` + report | Final negative result | Cited by registry (hashes) | `MOVE_TO_RESEARCH` (`research/evidence/`) | Low (`git mv`; links) | **Byte-exact.** |
| `rc_warm_acceleration_characterization/` + report | Warm-reuse verdict | Cited (hashes) | `MOVE_TO_RESEARCH` | Low | **Byte-exact.** |
| `final_architecture_freeze/` + `FINAL_ARCHITECTURE_FREEZE.md` | Sep 22 decision record | README-linked; hash-manifested | `MOVE_TO_RESEARCH` + top-level pointer or link update | Low | **Byte-exact.** |
| `PRODUCT_PRESENTATION_HANDOFF.md` | Superseded claims registry | Historical | `MOVE_TO_RESEARCH` | Low | Exact; mark superseded by pointer, not by editing. |
| All other top-level `*_REPORT.md`/`*_AUDIT.md`/`*_REVIEW.md`/ASTRA/TOKEN/FORMULA docs | Study reports | Historical | `MOVE_TO_RESEARCH` | Low | Exact (several hash-manifested). |
| All evidence dirs in §1 (~45) | Study artifacts | Historical | `MOVE_TO_RESEARCH` | Low–Medium (size; link fixups) | Exact via `git mv`. |
| Giant dirs (`compiled_context_sidecar_ab` 3.0G, `candidate_a_a1_checkpoint_rerun_01` 1.1G, `candidate_a_live`, `stochastic_work_census`, `transparent_capture_replay`, `scheduler_live_validation`, `token_claim_discovery`, `track_c_terminal_projection`, `thin_architecture_checkpoint`, `compact_evidence_delivery`, …) | Study artifacts | Historical | `REVIEW_MANUALLY` then `MOVE_TO_RESEARCH` or LFS/artifact storage | Medium (clone size vs hash integrity) | Exact bytes either way; pointer/manifest in repo if bytes go to LFS. |
| Top-level loose `*.csv`/`*.json` (~30) | Loose evidence | Cited by study reports | `MOVE_TO_RESEARCH` (reunite with study) | Low | Exact. |
| `results/` | Orphan evidence | No references found | `MOVE_TO_RESEARCH` | Low | Exact; full-text reference check first. |
| `candidate_a_a1_checkpoint_sitecustomize.py` | Checkpoint bootstrap | Research runner import | `MOVE_TO_RESEARCH` (into its study dir) | Low | Exact. |
| `src/librecalc_mcp/` | Historical product code | Research-only imports (~45 files) | `MOVE_TO_RESEARCH_ARCHIVE` | **High** — import churn across `benchmark/` + tests + ruff ignores | Exact; move with import updates or shim; full test run. |
| `scripts/smoke_uno.py`, `scripts/start_libreoffice.sh` | Historical UNO tooling | Manual only | `MOVE_TO_RESEARCH_ARCHIVE` (with UNO code) | Low | Exact. |
| `docs/HISTORICAL_MCP_README.md` | Labeled history | README-linked | `MOVE_TO_RESEARCH_ARCHIVE` + link update (or `KEEP` in place with banner — decide in Batch B) | Low | Exact. |
| `docs/architecture.md`, `docs/roadmap.md`, `docs/benchmark-plan.md`, `docs/PROJECT_CONTEXT.md`, `docs/harness-value-packet.md`, `docs/public-trajectory-audit.md`, `docs/viz-isa-diagnosis.*`, `spreadsheet_harness_architecture_checkpoint.md` | Obsolete product voice / study records | Historical | `MOVE_TO_RESEARCH_ARCHIVE` | Low | Exact. |
| Research/history `tests/test_*.py` (~74) | Research test suite | Run by pytest today | `MOVE_TO_RESEARCH` (with code) **or** keep with split config | Medium (suite split mechanics) | Keep runnable; never delete evidence-bearing regressions. Decide split design in Batch D. |
| `uv.lock` | Stale lockfile | Nothing (install path ignores it) | `MOVE_TO_RESEARCH_ARCHIVE` (as `uv.lock.historical`) | Low | Content preserved. |
| `scripts/install_into_personal_projects.sh` | Dead procedure | None | `MOVE_TO_RESEARCH_ARCHIVE` | None | Content preserved. |
| `CONTRIBUTING.md` | Obsolete loop doc | None (not shipped) | `REWRITE_PUBLIC_SURFACE` (new RC loop) + archive old | Low | Archive old content. |
| `benchmark/README.md` | Research harness doc | Research | Move with `benchmark/` (add banner that it is research) | Low | Exact + banner. |
| `__pycache__/` (463), `.pytest_cache/`, `.ruff_cache/` | Caches | None | `REMOVE_GENERATED` (disk only) | None | None. |
| `CLAUDE.md` (0 bytes) | Dead | None | `REMOVE_GENERATED` | None | None. |
| `.venv/` | Local env | None (ignored) | `KEEP` (ignored; disk-local) | None | None. |
| `.venv-product/` | User-created by README path | None | `GITIGNORE` (add rule) | None | None. |
| `benchmark-data/` (30G) | External dataset | 2 tests' `sys.path`; runners | `KEEP` (gitignored) + document acquisition in `research/README.md` | None | Do not commit. |
| `.env`, `.secrets/` | Secrets | None (ignored) | `KEEP` (ignored) | None | Never commit. |
| `LICENSE` | **Missing** | sdist references `LICENSE*` | Create (release blocker, Batch A) | None | N/A. |
| Duplicate impls (§4) | Active + predecessors | Mixed | `CONSOLIDATE` — Batch D only, after proven reachability; default is document-not-merge for extraction pairs | High if rushed | Extraction sources must survive any consolidation. |
| `benchmark/sweagent/{calc_query,calc_translate_fill,formula_index,view_xlsx_ambient}/` | Older tool worlds | Partial (`formula_index/lib` in 9 tests) | `REVIEW_MANUALLY` | Low | Exact until reviewed. |
| `tests/test_transparent_runtime.py` body | Unknown (header is stdlib-only) | Verify in Batch D | `REVIEW_MANUALLY` | Low | N/A. |

---

## 15. Cleanup batches (proposed order — not executed)

### Batch A — zero-risk hygiene (execute first)

1. Add `LICENSE` (release blocker; choose license first).
2. Add `.venv-product/` to `.gitignore`.
3. Remove caches from disk only: all `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`.
4. Remove `CLAUDE.md` (0 bytes).
5. **Commit the research record**: stage + commit all untracked evidence/reports/dirs
   (respecting `.gitignore`: `benchmark-data/`, `.venv/`, `.env`, `.secrets/` stay
   out). Separately commit the existing staged/working-tree WIP first so the two
   don't mix. Nothing moves until this commit exists.
6. Per-dir triage of regenerable-vs-evidence caches *inside* frozen studies (default:
   keep; only ignore future regrowth, e.g. `feasibility_probe/cache/` patterns if
   re-runnable — careful, these sit in hashed studies, so prefer keep).

### Batch B — research quarantine (content-preserving moves)

1. Create `research/{evidence,archive}/` + `research/README.md` (what/why/boundary/
   benchmark-data acquisition/"don't rewrite history").
2. `git mv` study reports + evidence dirs + loose csv/json → `research/evidence/`
   (giants pending the LFS decision — §13 open question b).
3. `git mv` old docs + `spreadsheet_harness_architecture_checkpoint.md` →
   `research/archive/`; archive `uv.lock` + install script.
4. Decide `benchmark/` fate (move to `research/benchmark/` vs banner-in-place) and
   `src/librecalc_mcp/` fate (move to `research/archive/historical-mcp/` vs
   banner-in-place). If moving, do it as its own commit with import updates (Batch D
   mechanics) — B and D merge for these two paths.
5. Keep `product_hygiene/`, `scripts/extract_product_runtime.py` at top.

### Batch C — stale public surface (wording only, no code)

1. README: align with `FINAL_CLAIM_REGISTRY.md` ("acceleration/fast path" →
   registry-compliant qualified description; point to registry; demo via
   `--no-runtime` posture). Keep a copy of the RC-era README with the RC record.
2. `COMPATIBILITY.md`: add pointer to claim registry (no claim changes).
3. New `CONTRIBUTING.md` for the RC loop; archive the old.
4. `tests/README.md`: product suite vs research suite split explanation.
5. Banners on quarantined-but-unmoved research paths (if any stay at top).
6. `pyproject.toml` comment touch-ups only where quarantine orphaned a pointer.

### Batch D — code consolidation (only after proven reachability)

1. Lock the move mechanics: `sys.path` inserts (43+ test files), pytest `pythonpath`,
   extraction-script source paths, `test_frozen_extraction_exact` paths,
   `test_product_hygiene` `product_hygiene/` path, README links, ruff ignores.
2. Full test run before + after each move group (`pytest tests/` plus the RC's
   isolated-install checks). A move that reddens the suite is reverted, not patched
   by deleting tests.
3. Decide per duplicate pair in §4 (default: keep extraction pairs; document the
   rest; merge only exact dead twins like the top-level checkpoint sitecustomize
   placement).
4. Optional: `research/requirements.txt` for research reproducibility (never in
   `pyproject`).

### Batch E — naming (separately, after product description frozen)

1. Decide whether `librecalc-agent` stays (recommendation: keep the stem; the
   LibreOffice-overstatement risk is low since LO is documented as optional).
2. If renaming anything user-visible (`candidate_a`/`substrate` keys, cache dir,
   env prefix): new release identity (per freeze rule — RC hashes pin the old
   strings), migration notes, and acceptance that `research/` keeps old strings
   forever (frozen evidence).

---

## 16. Required final answers

1. **Actual current product code path.** `librecalc-agent` CLI (`cli.py`) →
   `config.load` → `runner.run` (classify via `_frozen.eligibility`, prepare index
   via `_frozen.index/substrate`, subprocess with `_bootstrap/sitecustomize` →
   `_frozen.runtime/reads` interposition, capture via `_frozen.capture/delta/
   validate`) → per-run diagnostics; `doctor`/`status` via `diagnostics.py`;
   `lx_helpers` re-exports reference-openpyxl helpers. Deps: openpyxl required,
   lxml pinned-but-tolerated, stdlib sqlite3, optional LO binary detection.
2. **Genuinely product-facing top-level paths.** `README.md`, `COMPATIBILITY.md`,
   `pyproject.toml`, `src/librecalc_agent/`, `src/lx_helpers.py`, `examples/`,
   `tests/test_product_hygiene.py`, `scripts/extract_product_runtime.py`,
   `product_hygiene/`, claim/stop records (`FINAL_CLAIM_REGISTRY.md`,
   `RESEARCH_RECORD_FREEZE.md`, `FINAL_PRESENTATION_HANDOFF.md`, `CLAIM_BACKLOG.md`,
   `PRODUCT_HYGIENE_REPORT.md`). Everything else at top level is research, history,
   or cache.
3. **Research-only paths.** `benchmark/`, `benchmark-data/`, all `*_REPORT/AUDIT/
   REVIEW/TOKEN/FORMULA_ERROR/ASTRA*` docs, all ~50 evidence dirs, loose top-level
   `*.csv/*.json`, `results/`, `candidate_a_a1_checkpoint_sitecustomize.py`,
   83 of 84 test files' subject matter, `uv.lock`, historical scripts.
4. **Historical architectures in product-looking locations.**
   `src/librecalc_mcp/` (old MCP/UNO server in `src/`); `docs/architecture.md`,
   `docs/roadmap.md`, `docs/PROJECT_CONTEXT.md`, `docs/benchmark-plan.md`,
   `docs/harness-value-packet.md`, `CONTRIBUTING.md` (old product voice in
   docs/root); `benchmark/sweagent/*/bin/calc_*` + `server.py` (two historical
   agent surfaces); `uv.lock` (old dep set).
5. **Appears dead.** `CLAUDE.md` (empty); `uv.lock` (as a lockfile);
   `scripts/install_into_personal_projects.sh`; probably `scripts/smoke_uno.py` /
   `start_libreoffice.sh` (manual-only); `results/` orphan JSONs (preserve anyway);
   all caches/`__pycache__`. Everything else is either live product, live research
   dependency, or evidence.
6. **Duplicate implementations.** Seven extraction pairs (`_frozen/*` ⟸
   `benchmark/*` sources, parity-tested — keep both); substrate-backed vs reference
   helpers (`api.py` vs `reference_api.py`, the freeze decision — keep both);
   `transparent_runtime/{transaction,telemetry}` with no product twin; two
   historical agent surfaces (MCP server vs sweagent `calc_*`); three bootstraps
   (product `_bootstrap`, top-level checkpoint shim, `candidate_a_live_runtime`);
   generations of benchmark runners/scorers; three config surfaces (TOML, experiment
   config, sweagent YAML).
7. **Stale public docs/examples.** README ("acceleration/fast path" vs Sep 24
   registry — needs rewording, not archival); `docs/architecture.md`,
   `docs/roadmap.md`, `CONTRIBUTING.md` (wrong product — quarantine + rewrite);
   `PRODUCT_PRESENTATION_HANDOFF.md` (superseded claims — quarantine, never cite).
   Examples are current and verified. `FINAL_ARCHITECTURE_FREEZE.md` and
   `PRODUCT_HYGIENE_REPORT.md` are accurate dated records that need a registry
   pointer, not edits.
8. **Unsupported claims remaining.** Any "acceleration / fast path / exactness /
   token / equivalence / tail-economics" phrasing outside the Sep 24 registry —
   principally README's acceleration framing and the Sep 22 handoff/freeze positive
   rows. The registry's own negative statements are the supported ones.
9. **Research evidence that must be preserved exactly.** All hashed/frozen studies
   (`rc_acceleration_validation`, `rc_warm_acceleration_characterization`,
   `token_claim_discovery`, `token_affordance_discovery`,
   `final_architecture_freeze`, `representative_architecture_checkpoint`,
   `candidate_a_a1_checkpoint*`, `architecture_evidence_freeze`), their reports,
   `product_hygiene/` (incl. the frozen wheel), `_frozen` extraction sources +
   parity test, evidence-bearing regression tests (§10), and — as a set — every
   study report/dir (they cite each other and internal hashes). Commit before
   moving; `git mv` only; LFS-or-bytes decision for giants must preserve
   content-addressability.
10. **Generated clutter safe to remove.** All `__pycache__/` (463), `.pytest_cache/`,
    `.ruff_cache/`, `CLAUDE.md`. Everything else that looks generated (sqlite,
    xlsx, logs, wheel) is either cited evidence or lives inside frozen studies —
    keep.
11. **Product vs research-only dependencies.** Product: openpyxl (required),
    lxml (pinned, tolerated-absent), stdlib sqlite3, optional LO binary,
    dev pytest/pyyaml/ruff. Research-only: mcp, openai, dotenv, uvicorn/starlette
    stack (historical server), docker + provider accounts + benchmark-data
    (benchmark harness), python3-uno (historical backend). Packaging already
    separates them; only presentation (`uv.lock`) is wrong.
12. **LibreCalc/LibreOffice/MCP naming depth.** Product-code depth is shallow
    (~15 files: pyproject, 7 code files, cache/env/wheel names). Research-code
    depth is deep (57 files import `librecalc_mcp`; `LX_REPO_ROOT` + old repo dir
    name; `uv.lock`). Evidence depth is total and frozen (~80 files must keep old
    strings — hash-manifested). A rename is cheap in product, impossible in
    evidence (by design), and forces a new release identity (RC hashes).
13. **Top 10 confusion sources.** §12: (1) 76 md + 50 dirs bury the product;
    (2) `src/librecalc_mcp` reads as current; (3) claim conflict across front-page
    docs; (4) 84 test files vs 27 product tests; (5) `docs/` + CONTRIBUTING describe
    another product; (6) top-level `benchmark/` with model invocation; (7) name
    soup; (8) stale `uv.lock`; (9) missing LICENSE; (10) 422 untracked paths —
    the cited record isn't in git.
14. **Minimal cleaned repository.** §13: product front page + `src/` + `scripts/`
    (extraction) + one-file product suite + `examples/` + `product_hygiene/` +
    `research/{benchmark,evidence,archive}` + two small READMEs + LICENSE.
15. **Which batch first.** **Batch A**, in this order: choose + add LICENSE,
    add `.venv-product/` ignore, clear caches, delete the empty file, then commit
    the WIP and the research record. The single highest-value action in the whole
    audit is the commit in A5 — until it exists, every preservation guarantee in
    this document is aspirational.
