# V1 product boundary — smallest coherent release

Question: shipping the smallest coherent version of this architecture to an
external technical user, what is included? Goal: avoid freezing contracts for
machinery that does not need to be public.

## REQUIRED FOR V1

- `run`: ordinary script execution under the external observer with
  conditional direct reads + effect capture. The product.
- `doctor`: preflight (Python/openpyxl/lxml, runtime modules, observer,
  cache writability, LibreOffice detection, config). Required because install
  and platform failures must be diagnosable without reading source.
- `example`: copy-out onboarding (`create_input.py`, `read.py`, `update.py`,
  `runtime.toml`). Required because the product is otherwise behavior-only and
  invisible; a runnable example is the cheapest documentation.
- `--config` / `LIBRECALC_CONFIG`, `--no-runtime` / `LIBRECALC_NO_RUNTIME`,
  `--workdir`: the complete ordinary-use control surface.
- `capture` + `enabled` config keys, `cache_dir`, strict fail-closed config
  behavior. (Minus the two alias keys — see below.)
- Compact receipt (`route`, `target_status`, `assurance_status`, artifact
  states, fallback reasons, capture/validation status, failure code, run dir).
- `status`: last-receipt reader. Borderline, but removing it strands users
  with run dirs they cannot interpret; it is ~15 lines over `doctor`. Keep.
- `--require-libreoffice` preflight flag. Keep: it is the only honest bridge
  to recalc-dependent workflows, and its help text already disclaims recalc.
- Reference fallback + `NOT_REQUESTED` truthfulness + "no task was run"
  blocking. These are the safety contract, not features.

## USEFUL BUT OPTIONAL

- `--json` / `--verbose` on `doctor`/`status`: keep — cheap, and machine
  readers need a stable shape. Freeze the compact fields only.
- `verbosity` config key: keep (one line of behavior, gates warnings).
- `read.py` in the example using the direct path + `update.py` using capture:
  keep both behaviors; they demo the two earned mechanisms.
- Run-dir debug bundle (`setup.json`, `runtime_state.json`, observer receipt,
  capture detail): keep writing it, document as unstable/support-only.

## POST-V1

- Cache-management commands (`prune`, `gc`, `du`): needed eventually because
  there is no quota, but manual deletion + docs suffice for a small preview.
  Do NOT freeze a cache-CLI contract now.
- Explicit acceleration enable/disable beyond `enabled`/`capture`: the
  `substrate`/`candidate_a` split is the wrong granularity; a future single
  `reads` key can come with the rename window.
- User-visible routing labels beyond the 3 route states: `read_gate` research
  values must not become API.
- Python library API (`import librecalc_agent` beyond `__version__`,
  programmatic `runner.run`): keep internal until a library story is chosen.
- `lx_helpers` and inspection helpers: remove, not promote.
- macOS/Windows support: post-v1 (see platform feasibility; macOS may be cheap
  enough for fast-follow, but it is not v1).
- Derived/analytical evidence outputs (Phase-11 territory): post-v1, via a
  separate surface (see extension points).

## What v1 does NOT include (explicit non-goals)

- No model/API client, no credentials, no sandboxing (document all three).
- No recalculation, no task scoring, no formula validation.
- No token/cost claims, no cold/warm speed promises beyond the stated
  host-sensitive evidence, no broad openpyxl-equivalence claim.
- No global cache quota (document manual cleanup + location instead).
- No `index/reads/runtime/substrate` frozen modules (delete pre-v1).
- No `CANDIDATE_A_*` surface (delete with the above).
