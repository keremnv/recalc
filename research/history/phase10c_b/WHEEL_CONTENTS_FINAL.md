# Final wheel contents — librecalc-agent 0.2.0rc2

Source: `librecalc_agent-0.2.0rc2-py3-none-linux_x86_64.whl` as built by
`scripts/release-check.sh` (wheel-from-sdist, hatch hook compiled natives).
Every shipped file classified. No `__pycache__`, no tests, no benchmark, no
research, no MCP server, no dead frozen modules, no `lx_helpers`.

## Needed runtime code (CORE)

| File | Role |
|---|---|
| `librecalc_agent/__init__.py` | Version (`0.2.0rc2`) |
| `librecalc_agent/__main__.py` | `python -m` entry |
| `librecalc_agent/cli.py` | `example/run/doctor/status` |
| `librecalc_agent/config.py` | `[runtime]` config (`enabled/reads/capture/verbosity/cache_dir` + 2 deprecated aliases) |
| `librecalc_agent/diagnostics.py` | Preflight + status + cache summary |
| `librecalc_agent/runner.py` | Launch + receipt synthesis + exit policy |
| `librecalc_agent/_bootstrap/sitecustomize.py` | Guarded admission + route setup |
| `librecalc_agent/_capture_helper.py` | Observer-exec'd capture entry |
| `librecalc_agent/read_engine/__init__.py` | Package marker |
| `librecalc_agent/read_engine/_identity.py` | Single-sourced artifact identity (NEW in rc2) |
| `librecalc_agent/read_engine/artifact.py` | Codec + full validation + publication |
| `librecalc_agent/read_engine/cache.py` | Fast integrity gate + locked ensure |
| `librecalc_agent/read_engine/certificate.py` | Merged-child proof |
| `librecalc_agent/read_engine/direct.py` | Narrow OOXML decoder |
| `librecalc_agent/read_engine/runtime.py` | Interposition + proxies + fallback |
| `librecalc_agent/_frozen/__init__.py` | Package marker |
| `librecalc_agent/_frozen/eligibility.py` | Whole-script admission (frozen) |
| `librecalc_agent/_frozen/capture.py` | Capture transaction (frozen) |
| `librecalc_agent/_frozen/delta.py` | Package delta (frozen) |
| `librecalc_agent/_frozen/validate.py` | Mechanical validation + XML guard (frozen + rc2 guard) |

## Native binaries (PLATFORM, mode 0755)

| File | Role |
|---|---|
| `librecalc_agent/native/observer` | External process/effect observer |
| `librecalc_agent/native/launcher` | Installed-command dispatcher (also shipped as `.data/scripts/librecalc-agent`) |
| `librecalc_agent/native/observer.c` | Source transparency (rides along with `packages`) |
| `librecalc_agent/native/launcher.c` | Source transparency |

## Examples (TEST SUPPORT / onboarding)

`librecalc_agent/example/{create_input.py,read.py,update.py,runtime.toml}`
(`runtime.toml` rewritten to the `reads` key in rc2).

## Metadata

`METADATA` (rc2 README + pins), `WHEEL` (local `linux_x86_64` tag),
`RECORD`, `.data/scripts/librecalc-agent` (0755).

## Removed vs rc1 wheel (by audit decision)

- `_frozen/{index,reads,runtime,substrate}.py` — dead research runtime.
- `_frozen/{helpers,helper_common,period_constants}.py` + top-level
  `lx_helpers.py` — separable helper API, zero consumers.
- `entry_points.txt` console script — superseded by the native launcher
  (unchanged since Phase-10; noted for completeness).

## Verification

File list + modes asserted by `scripts/release-check.sh` steps 13–15 on every
release battery run. SDist additionally contains `pyproject.toml`,
`hatch_build.py`, C sources, README/COMPATIBILITY/CHANGELOG, evidence-boundary
doc, and examples (plus `LICENSE*` once the license decision lands).
