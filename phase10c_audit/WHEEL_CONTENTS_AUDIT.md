# Installed-wheel contents audit

Method: static packaging analysis (`pyproject.toml` `[tool.hatch.build]`
+ `hatch_build.py`) cross-checked against the recorded Phase-10 clean install
(`observer_in_wheel: true`, `command_executable: true`). The wheel archived at
`product_hygiene/dist/*.whl` is the OLD pure-Python RC and is NOT representative;
no rebuild was performed in this audit phase (build metadata inspection only).

## What the current build ships

Hatch `packages = ["src/librecalc_agent"]` ships the whole package dir,
plus force-includes, plus build-hook outputs:

| Shipped category | Contents | Verdict |
|---|---|---|
| Needed runtime code | `cli.py`, `config.py`, `diagnostics.py`, `runner.py`, `__init__.py`, `__main__.py`, `_bootstrap/sitecustomize.py`, `_capture_helper.py`, `read_engine/*.py`, `_frozen/{__init__,eligibility,capture,delta,validate}.py` | Needed. Core product. |
| Native binaries | `native/observer`, `native/launcher` (compiled by hook, `chmod 0755`), installed command via `shared_scripts` | Needed. The product's process architecture. |
| Native sources | `native/*.c` ride along inside `packages` (whole-dir include) | Harmless transparency (~16 KB); optionally excludable, not worth churn. |
| Examples | `librecalc_agent/example/*` (4 files, ~560 bytes, from `examples/basic`) | Needed (the `example` command copies from here). |
| Top-level helper | `lx_helpers.py` (4 lines + frozen helpers below) | SHOULD NOT SHIP (post-migration removal; see below). |
| Compatibility code (retain) | `_frozen/eligibility`, `_frozen/capture+delta+validate` | Needed at runtime (admission + capture). Frozen-provenance, not dead weight. |
| Compatibility code (remove) | `_frozen/{helpers,helper_common,period_constants}.py` | SHOULD NOT SHIP after the `lx_helpers` migration window. Only `lx_helpers` consumers. |
| Research artifacts | `_frozen/{index,reads,runtime,substrate}.py` (~1,100 lines) | SHOULD NOT SHIP. Zero maintained consumers; superseded RC index path. Pre-v1 deletion candidate. |
| Tests | None (tests/ not in `packages`) | Correct. |
| Metadata | `METADATA` (from README.md + pins), `WHEEL` (local platform tag), `RECORD` | Needed. Note: README currently describes the OLD RC (docs blocker, not a wheel-layout issue). |
| Entry points | None (`entry_points.txt` absent; dispatch via `shared_scripts` launcher) | Intended. The old RC wheel's `entry_points.txt` is gone by design. |
| Accidental files | `__pycache__/*.pyc` present in the SOURCE TREE (stale, e.g. `cli.cpython-313.pyc`) | Must verify hatch excludes them (default hatch behavior excludes `__pycache__`; confirm at release build). No `.pyc` was found in the old RC wheel listing, which suggests exclusion works. |

## Approximate size contributions (source tree, for orientation)

- `read_engine/`: ~1,150 lines (~45 KB) — the earned engine.
- `_frozen/` retained (eligibility+capture+delta+validate): ~670 lines.
- `_frozen/` removal candidates (index+reads+runtime+substrate): ~890 lines.
- `_frozen/` migration unit (helpers+helper_common+period_constants): ~390 lines.
- CLI/config/diagnostics/runner/bootstrap/capture-helper: ~370 lines.
- Native sources: ~16 KB; built binaries ~43 KB (observer 26 KB + launcher 17 KB).
- Examples: <1 KB.

Size is not a problem (total well under 1 MB); the issue is purely
responsibility hygiene: ~1,300 lines of shipped code (research residue +
migration helpers) that the runtime path never executes.

## Recommendations

1. Pre-v1: delete `_frozen/{index,reads,runtime,substrate}.py` → wheel loses
   the research index path entirely. (Requires the extraction-pin test scope
   decision first.)
2. Migration window: remove `lx_helpers.py` + `_frozen/{helpers,
   helper_common,period_constants}.py` → wheel loses the accidental top-level
   API.
3. At release build: verify no `__pycache__`, no `tests/`, no `benchmark/`,
   no `research/`, no `librecalc_mcp` in the wheel; record the file list as a
   release artifact (the RC-era `packaging_manifest.json` pattern, refreshed).
4. Do not chase size optimization (no minification, no binary stripping
   beyond what the toolchain does by default).
