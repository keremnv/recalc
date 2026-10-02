# Product hygiene report — PRODUCT_HYGIENE_RC

The frozen architecture now has a small installable `librecalc-agent` distribution, version **0.2.0rc1**. The supported interface remains ordinary Python/openpyxl. No architecture research, model calls, SpreadsheetBench, official scoring or recalc experiment ran in this phase.

Install from the checkout with `python -m pip install .` inside a fresh virtual environment. See [README.md](../../README.md) for the complete user path, [COMPATIBILITY.md](../../COMPATIBILITY.md) for tested limits, and [rc_manifest.json](../history/product_hygiene/rc_manifest.json) for the source/configuration/wheel identity.

## Maintained surface and extraction

The former package exposed the earlier MCP/UNO semantic tools. Their source and README are preserved under the historical surface; they are excluded from this distribution. The new package installs the CLI, TOML configuration, dependency diagnostics, script launcher, optional frozen read/capture mechanics, reference helpers and a tiny ordinary Python example. No benchmark imports, SDKs, datasets, scorer or research driver are required.

Eleven internal modules were copied or extracted from frozen source with only import relocation and exclusion of experiment entry points. The classifier, proxy operations, capture/commit code and helper functions were not redesigned. A parity test compares selected definitions as ASTs or full transformed source text. [extraction_manifest.json](../history/product_hygiene/extraction_manifest.json) records exact source hashes and transformations. The product uses the existing eligibility decision on the unchanged script source; it never rewrites the script. Child Python activation is scoped to that file, so nested unclassified interpreters do not silently inherit acceleration.

The original capture wrapper remains record-only and commits the script-produced bytes; its validation is not semantic authority. Optional setup/check failure is diagnosed without rerunning the script, repairing its output or replacing its exit status. Helpers use reference openpyxl, including style reads; the old substrate-backed helper implementation is not distributed.

Classifications and runtime reachability are in [product_surface.json](../history/product_hygiene/product_surface.json). Exclusion is by wheel/sdist allowlists, not destructive cleanup. Existing research sources, checkpoint evidence, closure ledgers and the prior architecture freeze remain unchanged.

## Installation and local verification

A new isolated venv with no system-site packages installed the project from the checkout. The package resolved openpyxl 3.1.5, lxml 6.1.3 and et_xmlfile 2.0.0. Installed imports resolve inside that environment, not the source checkout; imported modules include no benchmark, historical MCP, OpenAI or MCP client packages. The built wheel includes examples and excludes research surfaces.

Doctor/status, example creation, normal writes, conservative read acceleration, runtime-disabled execution, direct Python execution and reference helpers all passed. The formula is stored as `=A2*2`; no cached/calculated result is claimed. LibreOffice 26.2.5.2 was detected via `--version` only. Missing-LibreOffice behavior is tested locally by dependency substitution.

**27 installed product tests and 39 existing frozen regression tests pass.** The product tests exercise optional dependency absence, invalid configuration, missing/unusable cache, failed index build, malformed/unsupported workbooks, stale/corrupt/missing index, helper reference routing, single execution/exit propagation and nested-interpreter isolation. No paid/external model test was selected. See [clean_install_test.json](../history/product_hygiene/clean_install_test.json), [validation_results.json](../history/product_hygiene/validation_results.json), and the retained logs/JUnit outputs.

Default configuration enables runtime, conservative read acceleration/indexing and capture, with normal diagnostics and an XDG/home cache. Actual compiled serving also requires frozen eligibility and successful initialization. Without compiled serving, its freshness machinery is inactive. Capture remains independently optional. Invalid configuration disables runtime; optional index/cache failures preserve ordinary operation. Missing mandatory openpyxl is an installation failure; missing LibreOffice is optional unless expressly required. Raw internal failure details stay in diagnostics/verbose mode rather than normal installer output.

## Token-evidence preservation

The [future claim registry](../history/product_hygiene/future_claim_evidence_registry.json) preserves lower reported token observations without promoting them to product claims. Rows include study/cohort totals and individual paired observations, so they are not independent experiments and must not be pooled as such. Higher arm totals are retained for context. Missing fields are not newly imputed; source-provided zero usage for failed/censored runs is not evidence of zero work.

| Prior observation | Control | Treatment | Interpretation for this RC |
|---|---:|---:|---|
| Stage-B inspection, 14 runs/arm | 6,319,843 | 3,760,254 | Descriptive; visible helper/note and stall mix differ. |
| Thin checkpoint overall, 24 runs/arm | 18,097,832 | 16,258,754 | Descriptive; non-adopters show much of the shift; exposure cohort increases. |
| Batch helpers primary totals | 4,104,791 | 4,058,278 | Descriptive; zero helper adoption. |
| Default deterministic execution, prompt tokens | 15,731,994 | 14,047,346 | Descriptive; executor never invoked. |
| Candidate A live reported totals | 6,690,612 | 5,501,280 | Descriptive; varying trajectories/completion. |
| A1 rerun reported totals | 8,749,268 | 3,565,421 | Descriptive; provider/workbook censoring and completion differ. |
| Historical compact encoding, 11 complete pairs, prompt tokens | 5,842,363 | 4,998,231 | Representation mechanism plausible; five treatment-only timeouts; rejected surface. |
| Historical bounded inspection, one task, prompt tokens | 549,294 | 178,294 | Visible observation redesign plausibly relevant; old MCP surface, no transfer established. |
| Historical Phase C same-files subset, rounded input tokens | ~4.17M | ~2.03M | Session consolidation plausible; historical architecture, not this product. |

The initial transparent-runtime and representative primary arm totals were higher in treatment; these are also preserved. No lower total is causal/claim-ready token-saving evidence for the invisible RC. Historical representation effects do not authorize resurrecting those mechanisms. Product README makes no token-savings claim.

## RC and release boundary

`PRODUCT_HYGIENE_RC` = **0.2.0rc1**, source/configuration SHA256 `1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee`, wheel SHA256 `532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e`. Git HEAD `254a5c14fa74fc3534493c565de84b38e7317175` is recorded, but the workspace contains substantial earlier uncommitted research work, so HEAD alone does not identify the RC. The manifest lists every product source/configuration file and exact installed dependency versions.

The validated product differs operationally from the research runner: a shell command wraps one Python script; cache/index lifetime is one invocation; model/network/scoring drivers are absent; diagnostics are user-oriented and credential-free. These are packaging/bootstrap choices, not new semantic mechanisms. In particular, cross-call amortization from the checkpoint cannot be assumed for this RC. No new efficiency claim is made.

This boundary is ready as input to future **claim-specific** validation, not as evidence that a claim passes. After validation begins, code/configuration/dependency changes require a new RC identity and relevant mechanical revalidation. Public release still needs license/release policy, publication/support decisions, wider compatibility CI, reproducible dependency/release automation and cache-retention UX. No mechanism research remains required.

## Required answers

1. **What exact command installs the product?** `python -m pip install .` from the repository checkout, inside `python3 -m venv .venv-product` activated with `. .venv-product/bin/activate`.

2. **What system dependencies remain?** Python with venv/pip; SQLite for optional indexing; LibreOffice Calc only for recalc/validation workflows. No UNO binding or model credentials are needed for this harness.

3. **What does a clean install require?** Checkout, supported Python, writable virtual environment and network access to resolve pinned openpyxl/lxml plus et_xmlfile and the isolated build backend. No research datasets.

4. **What command checks installation health?** `librecalc-agent doctor`; use `--require-libreoffice` when its availability is mandatory.

5. **What does that health check inspect?** Python/openpyxl/lxml versions and imports, SQLite, optional runtime imports, cache creation/writeability, config, LibreOffice executable/version. External agent credentials are not consulted.

6. **What is the default runtime configuration?** Runtime, read index, conservative Candidate A and capture enabled; normal diagnostics; XDG/home cache. Actual accelerated serving still requires the unchanged frozen eligibility gate and valid index.

7. **Can the user disable the invisible runtime?** Yes: `run --no-runtime`, or `[runtime] enabled=false`. Individual `substrate`, `candidate_a` and `capture` flags are supported.

8. **Can ordinary openpyxl operate if setup fails?** Yes. Optional import/cache/index/bootstrap failures select reference execution; valid workbook tests demonstrate successful reads. Invalid config disables optional runtime for the invocation.

9. **What happens without LibreOffice?** Ordinary edits continue. Doctor marks OPTIONAL_NOT_AVAILABLE; an explicit `--require-libreoffice` invocation fails preflight. Neither command implicitly recalculates.

10. **What is the minimal example?** `example DIR` copies normal create/read/update scripts. `run --workdir DIR DIR/update.py` loads example.xlsx, writes B2=`=A2*2`, and saves output.xlsx. No helpers are required.

11. **What is the product-facing API/surface?** Shell commands `run`, `example`, `doctor`, `status`; ordinary Python/openpyxl; optional existing lx_helpers facts. No embedded model client, SQL, IR or spreadsheet-specific planning language.

12. **Which research modules are excluded?** All benchmark/model/scoring/census runners, benchmark data/results, evidence directories and the earlier librecalc_mcp semantic/UNO server. Historical README preserved, not used as product instructions.

13. **Which components are packaged but optional?** Frozen read classifier/proxies/index/publication, scoped bootstrap, capture/delta/mechanical validation and reference factual helpers. CLI/reference operation survives optional failures.

14. **What compatibility is actually tested?** Clean Linux x86_64/POSIX, Python 3.13.12, openpyxl 3.1.5, lxml 6.1.3, SQLite 3.51.1. LibreOffice 26.2.5.2 detection. Prior 3.14/stdlib-XML boundary evidence is distinguished from this RC test.

15. **What remains untested?** RC installs on Python 3.11/3.12/3.14, Windows/macOS, containers/network filesystems, other package/LibreOffice versions, VBA/rich-content guarantees and concurrent writers.

16. **Does malformed/unsupported input still fail closed?** Yes. Installed tests cover malformed packages, unsupported chartsheets, initial failures, missing/corrupt/stale index and optional absence. Malformed input can still raise the reference openpyxl error.

17. **Do helpers use only reference openpyxl?** Yes. The wheel includes reference helper implementation plus formatting constants/utilities, with no substrate-backed helper API. Tests prohibit index and patched-loader contact, including styles.

18. **Do existing regressions pass?** Yes: 39 existing frozen tests; 27 product tests also pass against the clean installed wheel. No model/benchmark/scoring test was invoked.

19. **Did Candidate-A eligibility change?** No. Extracted A1 classifier definitions compare AST-exactly to frozen source. Existing admitted operations and rejection rules are unchanged.

20. **Did model-facing semantics change?** No new model prompts, tools, workbook semantics or mutation rules. New shell/configuration diagnostics wrap ordinary scripts. Selected capture/proxy definitions are source/AST-parity checked.

21. **Was any branch reopened?** No. Extraction, packaging, bootstrap and diagnostics are product engineering; all closed/frozen branches remain so.

22. **What lower-token observations were found?** 51 lower rows in a 55-row registry, including aggregates and selected paired observations, not independent experiments. Stage B: 6,319,843→3,760,254; thin overall: 18,097,832→16,258,754; batch helpers: 4,104,791→4,058,278; default deterministic execution: 15,731,994→14,047,346 prompt tokens; Candidate A/A1 and historical representation reductions are preserved too.

23. **Which are descriptive only?** Retained invisible-stack arm/task totals, thin/helper totals and non-adopted executor/helper comparisons. Censoring, noncompletion, note salience and trajectory length prevent attribution; source-provided zero usage is not proof of zero work.

24. **Is any token claim causal/claim-ready?** None for PRODUCT_HYGIENE_RC. Historical representation/session-consolidation changes are labelled CAUSAL_MECHANISM_PLAUSIBLE where appropriate, with transfer/censoring limits; no row is promoted to CLAIM_READY.

25. **What exact source/configuration is the RC?** Package 0.2.0rc1, source/configuration SHA256 `1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee`, wheel SHA256 `532e493f126087a45d86117343514a9a1cd0a4e0010af89bbd1be1b271d66b2e`, defaults and resolved dependencies in `rc_manifest.json`. Git HEAD is recorded but does not identify this dirty worktree by itself.

26. **Is it ready for claim-specific validation?** Yes as a mechanically verified, hashed installation/runtime input. That is not evidence for a performance/capability/token claim. Changes after this boundary require a new RC identity.

27. **What product work remains before public release?** License/release policy, publication/support process, broader compatibility CI, dependency/release reproducibility, and cache-retention UX. Agent convenience integration may follow without changing the semantic interface.

28. **What research work remains?** No mechanism-discovery work is required or reopened. Future empirical work must be explicitly claim-specific and start from this fixed RC; frozen research leads are not scheduled.

29. **What should happen next?** Review the RC boundary, address public-release engineering gaps, and draft a Claim Validation Plan against explicitly scoped claims. No automatic full benchmark or new mechanism experiment.

## Final synthesis

### PRODUCT SURFACE

Ordinary Python/openpyxl plus run/example/doctor/status; optional frozen mechanics, no research architecture in the user path.

### INSTALLATION

One canonical path: isolated environment, then python -m pip install . from the checkout.

### DEPENDENCIES

Pinned openpyxl/lxml, et_xmlfile; SQLite for indexing; optional system LibreOffice. No model SDK/UNO dependency.

### DOCTOR / DIAGNOSTICS

Credential-free local checks; PASS/WARNING/FAIL/OPTIONAL_NOT_AVAILABLE; compact status and optional detailed logs.

### DEFAULT CONFIGURATION

Runtime, conservative reads/index and capture enabled; normal diagnostics; writable XDG/home cache. Dependencies enforced.

### FAIL-CLOSED BEHAVIOR

Optional failure loses acceleration; ordinary operations continue. Bad workbook bytes may still raise the normal reference error.

### MINIMAL EXAMPLE

A normal openpyxl script writes B2 = =A2*2 and saves output.xlsx, with enabled/disabled/direct execution verified.

### LIBREOFFICE INTEGRATION

Detected/versioned as a system prerequisite; explicitly required workflows fail preflight if absent. No automatic recalc added.

### HELPER BACKEND

Reference openpyxl only, including style reads. Rejected substrate helper execution absent from the package.

### COMPATIBILITY

Clean RC tested on Linux/Python 3.13.12/openpyxl 3.1.5/lxml 6.1.3/SQLite 3.51.1; other environments clearly qualified.

### CLEAN-INSTALL RESULT

PASS: new venv, no system-site packages, canonical pip install, isolated imports, doctor/status/example and installed-package tests.

### REGRESSION RESULT

27 installed product tests and 39 existing frozen regressions pass; source/AST extraction parity passes. No model calls or benchmarks.

### RESEARCH SURFACE EXCLUDED

Benchmark/model/scoring runners, datasets, evidence and historical MCP/UNO package excluded by distribution allowlists; history preserved.

### PRODUCT_HYGIENE_RC

0.2.0rc1 frozen at source/config SHA256 1aba31178faca5533c4a594cf1ee8bae2bf3668fcb5f7a9df65f84361f972aee; wheel and exact dependency versions recorded. Future validation must keep this identity fixed.

### TOKEN-EVIDENCE REGISTRY

51 lower rows preserved in 55 descriptive/historical entries; scopes, censorship and non-transfer are explicit. No product token claim.

### CLAIMS CURRENTLY SAFE

Ordinary Python interface; conservative workload-dependent read acceleration; fail-closed reference behavior; transparent mutation assurance, all within the frozen evidence scopes.

### CLAIMS STILL REQUIRING VALIDATION

Any RC-level speed, total-task cost, token saving or capability comparison. No universal speed, formal equivalence or corruption-prevention claim.

### KNOWN LIMITATIONS

Single-writer local .xlsx script workflow; per-invocation index lifetime; manual cache cleanup; no automatic recalc/model client or rich-content preservation guarantee.

### ARCHITECTURE-CHANGE CHECK

No eligibility, mutation/helper semantics, model prompt or semantic architecture changed. No closed/frozen branch reopened.

### PUBLIC-RELEASE GAPS

License/release policy, publication/support, compatibility CI, dependency/release automation and cache-retention UX remain engineering work.

### NEXT PHASE

Review the hashed RC and prepare scoped claim-specific validation after the remaining release hygiene; start with a claim, not a benchmark.
