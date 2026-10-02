## Goal

Run a parallel product-presentation track for LibreCalc Agent rc2 that makes the frozen product immediately understandable to an external developer — ordinary Python, conditionally accelerated, externally observed — without redesigning the runtime, reopening performance research, or mixing in Phase 11–13 mechanisms.

## Success Criteria

- Presentation work is isolated from research (dedicated branch or worktree off the clean rc2 baseline); rc2 behavior is unchanged.
- A concise, reviewable presentation direction exists: README hierarchy, hero demo beats, one architecture visual, demo fixture/script design, asset list, and evidence/limitations placement.
- A reproducible demo foundation exists (`examples/demo/` + `scripts/demo.sh`) showing normal Python → BUILD → REUSED → reference fallback with result-equality checks and no faked output.
- Every visual and sentence survives a skeptical claim-discipline review: no universal speedup, cold-start, write, token/cost, broad-equivalence, or task-score claims.
- Discussion checkpoint with the user happens before large visual/README changes; only small exploratory prototypes land before that.

## Audit Findings (what exists today)

- `README.md`: accurate but research-shaped. Opens with install/quick-start, buries the conditional-acceleration story under "How acceleration works" (~line 74). No hero visual, no BUILD→REUSED terminal transcript, no architecture diagram. Good claim discipline already ("No universal speedup", "Cold runs are not accelerated", "No token, cost, or benchmark-score claim").
- `COMPATIBILITY.md`: strong contract matrix (Linux x86_64/glibc, CPython 3.13 tested, pinned openpyxl 3.1.5 + lxml 6.1.3, LibreOffice detection-only, macOS/Windows unsupported). Correct home for platform detail; README should link, not duplicate.
- `docs/EVIDENCE_AND_LIMITATIONS.md`: the claim boundary. Established: ordinary-Python parity (543/543 oracle rows), narrow conditional direct reads, reference fallback, content-addressed artifacts (whole-file SHA-256 + version keying), external observation, tested capture (~1.6× charged assurance overhead on 5 frozen fixtures), clean-install + 27+ tests + failure-injection battery. Conditional: +6.39 ms pinned reference-only overhead, 0.608× warm-reuse median on 7 frozen direct-contact workloads, cold 1.04–1.12×, all-30 median 1.044. Not claimed: universal/cold/write/token/score/equivalence claims. Presentation must not headline the conditional numbers.
- `examples/basic/`: minimal but opaque for demo purposes — `create_input.py` makes a 1-cell workbook; `read.py` prints one cell; `update.py` writes a formula. Good for install smoke, weak as a visual story (no understandable domain, reuse invisible on 1 cell).
- CLI (`src/librecalc_agent/cli.py`, `runner.py`, `diagnostics.py`): `example`, `run --workdir`, `doctor`, `status` (compact + `--json`/`--verbose`). Receipt compact fields are stable: `route` (`REFERENCE_FAST_PATH`/`DIRECT_RUNTIME`/`DIRECT_WITH_FALLBACK`), `admitted` + `admission_reason`, `artifact` (`BUILT`/`REUSED`/`NOT_APPLICABLE`/unconfirmed), `direct_served_loads`, `fallback`, `target_status` vs `assurance_status`, capture/validation, `failure_code`, `run_dir`. `status` compact prints `route/target/assurance`; full JSON has the BUILD/REUSED detail. Demo should parse `status --json` (or the `run` library receipt), not screen-scrape prose.
- Direct surface (frozen): whole-script static admission in `src/librecalc_agent/_frozen/eligibility.py` (fail-closed AST + preserved A0 lexical rules; blockers include iteration, ranges/slices, rich objects, writes, dynamic subscripts, function defs, load options). Narrow proxy contract in `read_engine/runtime.py`: sheet names, literal sheet lookup, bounds/dimensions, literal/integer cell access, value/data-type only; everything else lazily escapes to real openpyxl and is recorded. Decoder in `read_engine/direct.py` is OOXML-direct (no openpyxl at parse); artifacts in `read_engine/cache.py` + `artifact.py` keyed by SHA-256 + runtime/decoder/contract/format versions, atomic publish under per-key lock, validated before serving. Bootstrap in `_bootstrap/sitecustomize.py` pre-builds artifacts for `*.xlsx` in workdir on admission only; reference scripts never touch the cache (proven by `test_reference_branch_does_not_publish_artifact`).
- Existing BUILD→REUSED proof: `tests/test_product_hygiene.py::test_direct_build_and_reuse` (DIRECT script → `[BUILT]` then `[REUSED]`, `route=DIRECT_RUNTIME`, 1 served load) and `scripts/release-check.sh` steps 9–10 (reference script via `wb.active` → fallback; direct script via `ws.cell()` → BUILD then REUSE). Demo beats already have tested patterns to copy. Known-good direct idiom: `wb["Sheet1"]` + `ws.cell(row=,column=)` or `ws["H42"]`; known-good fallback idiom: `wb.active`, `for row in ws`, `ws["A1:B2"]`, `.save()`, `def` in script.

## Approach

Keep rc2 frozen; add only presentation + demo scaffolding on an isolated branch/worktree. Prototype a small honest demo fixture and driver first (result equality + route assertions), then draft README structure and one architecture visual from the real receipt fields. Defer polished GIF/SVG and README rewrite until the user approves direction. End with an independent claim-discipline review before anything is treated as release-facing.

Non-goals: no runtime, admission, decoder, artifact, observer, or receipt changes; no Phase 11–13 incorporation; no benchmark tuning or aggregate research charts; no token/cost/score claims; no macOS/Windows/doc restructuring beyond presentation layering.

## Key Decisions

- Isolation: dedicated presentation branch (or worktree if the user prefers parallel research checkouts) cut from the clean rc2 baseline commit, not from the current dirty tree. Rationale: current tree has extensive uncommitted research artifacts; presentation must not sweep them into user-facing diffs. Alternative rejected: working on `probe/program-group-execution` directly (mixes research + presentation).
- Demo source of truth: `status --json` / `runner.run` receipt fields (`route`, `artifact`, `direct_served_loads`, `fallback`, `target_status`, `assurance_status`), plus script stdout comparison. Rationale: stable compact fields; screen-scraping prose is brittle. Rejected: custom log parsing or hand-written transcripts.
- Workbook: generated deterministic fixture (checked-in generator + small committed `.xlsx`), domain-readable (e.g. Forecast grid with named sheets/rows), sized so REUSE is visible but repo stays small. Rationale: no existing workbook fits (basic example is 1 cell; benchmark workbooks are opaque/large). Rejected: reusing an opaque benchmark workbook or hand-tuning a giant sheet for a dramatic ratio.
- Timing display: real wall-clock from the demo machine, labeled "this demo / this machine", shown as secondary detail under the route/artifact story — never as the headline. Rejected: leading with 0.608×/0.468× frozen numbers or any bar chart without a reproducible run behind it.
- Architecture visual: one SVG (ASCII fallback in docs) showing ordinary script → admission → direct vs openpyxl fork → workbook work → external observer. Rejected: multi-diagram hero or detailed cache-internals graphic at the top.
- README layering: hero answers what/what-changes/what-happens in ~20 seconds; receipt schema, cache internals, glibc floor, methodology, and compatibility matrix stay in linked docs. Rejected: moving evidence detail into the hero.

## Steps

1. Isolate presentation work.
   - Cut `product-presentation/rc2` branch (or worktree) from the clean rc2 baseline commit; verify `git status` clean and `scripts/release-check.sh` smoke passes or is unblocked.
   - Surfaces: git only; no product code touched.
2. Prototype the demo fixture (small, reviewable).
   - Add `examples/demo/`: `generate_model.py` (deterministic, seeded), committed `model.xlsx`, `read.py` (Beat A/B: literal reads via `wb["Forecast"]` + `ws.cell()`/`ws["H402"]`), `unsupported.py` (Beat C: iteration + print, must stay on reference path), `README.md` (what each file proves). (Named `read.py`, not `inspect.py`, to avoid shadowing the stdlib.)
   - Keep `read.py` free of `def`, iteration, ranges, rich attributes, and load kwargs so it admits; keep `unsupported.py` minimal with exactly one deliberate fallback trigger.
3. Prototype `scripts/demo.sh` with a validation mode.
   - Flow: fresh demo cache (`XDG_CACHE_HOME` or `cache_dir` override) → plain `python inspect.py` (Beat A) → `librecalc-agent run` #1 (expect `DIRECT_RUNTIME`, `BUILT`) → `run` #2 (expect `DIRECT_RUNTIME`, `REUSED`, `direct_served_loads ≥ 1`) → stdout equality check across all three → `run unsupported.py` (expect `REFERENCE_FAST_PATH` or `DIRECT_WITH_FALLBACK` with a recorded fallback reason, never silent direct) → concise timing/status table.
   - Flags: default human-readable transcript; `--check` for assertion-only CI mode (nonzero exit on any mismatch); `--keep-cache` for iteration.
   - No faked output: every displayed line comes from a real invocation in that run.
4. Draft the README restructure (proposal + copy sketch, not a full rewrite yet).
   - Proposed order: one-line value prop → visual demo (transcript + timing label) → Keep writing normal Python → See LibreCalc work (BUILD→REUSED→fallback) → Why this exists → How it works (diagram) → What it accelerates / What happens when it cannot → External observation → Installation → Evidence and performance (link + scope note) → Limitations → Documentation.
   - Keep top-20-seconds code block exactly the `load_workbook("model.xlsx")` / `ws["H42"]` shape from the request.
5. Draft one architecture diagram + fallback micro-visual.
   - Main: ordinary script → admission → supported/unsupported fork → persistent derived state vs openpyxl → workbook work → external observer.
   - Secondary: "Can LibreCalc prove this operation is supported? YES→direct, NO→openpyxl."
   - Deliver as inline SVG proposal + ASCII fallback; defer styling polish until the user picks a direction.
6. Define the visual asset list (one property per asset).
   - Terminal transcript/GIF of BUILD→REUSED; terminal transcript/GIF of fallback; static architecture SVG; optional timing card only if the demo measurement is stable and labeled; `doctor`/`status` screenshot only if it earns its place.
   - Each asset maps to a `demo.sh` step so visuals regenerate without manual checking.
7. Evidence/limitations placement + claim/evidence check.
   - README keeps short "Evidence and performance" + "Limitations" sections linking to `docs/EVIDENCE_AND_LIMITATIONS.md`, `COMPATIBILITY.md`, `PRODUCT_RECEIPT_SCHEMA.md`, and `phase10c_b/LINUX_RELEASE_BASELINE.md`.
   - Tabulate each planned sentence/visual against its evidence source; flag anything lacking direct integrated-product evidence for removal or rewording.
8. Independent strong-agent claim review (before release-facing copy).
   - Reviewer asks only: which sentence/visual could read broader than evidence, which claim lacks integrated evidence, does the demo imply universal performance, is fallback accurate, is any historical/rc1 number presented as rc2.
   - Critic role only; no copywriting.
9. Discussion checkpoint.
   - Present this plan + fixture prototype + diagram sketch + asset list + claim check + open questions; wait for direction before polished GIF/SVG/README work.

## Validation Plan

- Isolation: `git status --short --branch` clean on the presentation branch; `git log --oneline -3` shows the rc2 baseline as parent.
- Fixture admission: direct script admits (`status --json` → `admitted=true`, `admission_reason=admitted`); fallback script does not silently take direct (`route=REFERENCE_FAST_PATH` or `DIRECT_WITH_FALLBACK` with `fallback[].reason` present).
- Demo correctness: `scripts/demo.sh --check` exits 0 on a fresh cache and asserts BUILD→REUSED, `direct_served_loads ≥ 1` on reuse, byte-identical stdout across plain Python and both LibreCalc runs, and fallback on the unsupported script.
- Demo honesty: delete the demo cache, re-run `scripts/demo.sh`; every displayed number/route comes from that run; timings labeled with host identity (no cached transcripts).
- Product regression: `python -m pytest -q tests/test_product_hygiene.py tests/test_product_process_semantics.py` green; `ruff check .` clean if touched files require it.
- Claim check: each README sentence/visual traces to `docs/EVIDENCE_AND_LIMITATIONS.md`, `COMPATIBILITY.md`, a receipt field, or a `demo.sh --check` assertion; no sentence depends on rc1 registries, Phase 11–13 notes, or cross-host averages.
- Highest-risk validation: the `--check` route/artifact assertions on a fresh machine cache — this is what prevents a future GIF from silently showing a fallback as REUSED.

## Risks / Open Questions

- Branch or worktree for the presentation track, and which exact commit is the clean rc2 baseline?
- Workbook domain/size tradeoff: how large a generated `model.xlsx` is acceptable in-repo (e.g. ~50–200 KB) while keeping REUSE visible?
- Should the demo show wall times by default, or hide them behind a `--timings` flag with route/artifact as the primary message?
- SVG/diagram styling preference before polish (hand-authored minimal SVG vs Mermaid-rendered vs ASCII-only)?
- GIF/video tooling and length cap (e.g. asciinema/vhs, ~30–60 s, no audio)?
- README hero order: demo transcript first vs architecture diagram first?
- Should the external-observer visual appear in the hero or lower under assurance?
