# Configuration audit

All configuration/environment controls in the maintained product
(`config.py`, `cli.py`, `launcher.c`, `runner.py`, `observer.c`,
`sitecustomize.py`). Dead `_frozen/runtime.py` `CANDIDATE_A_*` knobs listed
once at the end for deletion tracking.

## Config file keys (`[runtime]` TOML, `config.py:10-30`)

| Key | Required for ordinary use? | Safe default? | Category | Remain user-facing? |
|---|---|---|---|---|
| `enabled` (bool, default true) | No (default suffices) | Yes | Public master switch | YES |
| `capture` (bool, default true) | No | Yes | Public capture switch | YES |
| `cache_dir` (str, default XDG/`~/.cache`) | No | Yes | Public path control | YES |
| `verbosity` (quiet/normal/verbose, default normal) | No | Yes | Gates config-warning print only | YES (harmless, documented) |
| `substrate` (bool, default true) | No | Yes | MIGRATION-ONLY alias (RC term) | NO — rename window then drop |
| `candidate_a` (bool, default true) | No | Yes | MIGRATION-ONLY alias (research-arm term) | NO — rename window then drop |

Strictness: unknown key / wrong type / bad `[runtime]` shape / unreadable file
→ runtime disabled + WARNING (fail-closed, `config.py:62-66`). This behavior
is itself public contract and must be documented.

Recommendation: introduce a single documented `reads` key as the successor of
the `substrate`+`candidate_a` pair (keeping `enabled` as master), accept the
old keys with a deprecation warning for one window, then remove. Do NOT add
new knobs (no per-path admission flags, no cache-size flags pre-v1).

## CLI flags (all four commands take `--config`; `run` adds `--workdir`)

| Flag | Category | Notes |
|---|---|---|
| `--config PATH` | Public | Alternative: `LIBRECALC_CONFIG`. Document precedence (flag wins). |
| `--no-runtime` | Public | Escape hatch. Alternative: `LIBRECALC_NO_RUNTIME=1`. |
| `--workdir DIR` | Public | Default cwd. Observer snapshots + artifact discovery root. |
| `--require-libreoffice` | Public (doctor/run) | Preflight only; honest help text. |
| `--json`, `--verbose` | Public (doctor/status) | `--verbose` currently implies JSON dump too (`cli.py:63`) — document or split post-v1 (minor wart, not a blocker). |
| `--version` | Public | Prints `__version__`. |

## Environment variables

| Variable | Category | Notes |
|---|---|---|
| `LIBRECALC_CONFIG` | Public | Documented alternative to `--config`. |
| `LIBRECALC_NO_RUNTIME=1` | Public (advanced) | Documented alternative to `--no-runtime`. |
| `XDG_CACHE_HOME` | Public (standard) | Cache base. |
| `LIBRECALC_EFFECTIVE_CONFIG` | INTERNAL | Runner→bootstrap handoff. Never user-set; document as internal. |
| `LIBRECALC_RUN_CONTEXT` | INTERNAL | Observer→bootstrap handoff. |
| `LIBRECALC_RECEIPT_POINTER` | INTERNAL | Concurrency-safe receipt discovery. |
| `LIBRECALC_CAPTURE_ENABLED` | INTERNAL | Derived from config. |
| `CANDIDATE_A_*` (8 vars) | TEST-ONLY/DEAD | Read only by dead `_frozen/runtime.py`; stripped by runner. Delete with that module. |

## Research-era knobs that must disappear before compatibility freezes

1. `substrate`, `candidate_a` config keys (user-facing research terms).
2. `CANDIDATE_A_*` env vars (whole family dead).
3. `read_gate` receipt values (`A1_ADMIT`, `PREDECLARED_REAL_OPENPYXL`) —
   not config, but the same retirement class.

None of the three affects the 27 product tests' happy paths; all need
migration-window handling because old config files / scripts may reference them.
