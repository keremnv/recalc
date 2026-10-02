# Post-cleanup maintainer review (independent re-read)

Written after all 10C-B implementation, reading the tree as if new.

## Is the installed product now conceptually smaller?

Yes. The wheel went from "runtime + dead index + helper API + research
runtimes" to exactly the v1 boundary: CLI/config/diagnostics/runner,
bootstrap, read engine, frozen admission/capture, two natives, examples.
`_frozen/` has 4 modules where it had 11; the top level lost `lx_helpers`;
`read_gate`/`CANDIDATE_A_*` are gone from all product surfaces. The receipt
gained `admitted`/`admission_reason`/`cache_summary` — additive, coherent,
boring. Net: smaller conceptually despite 13 new tests.

## Is any research mechanism still leaking into public vocabulary?

Two deliberate, windowed leaks, both labeled: config aliases
`substrate`/`candidate_a` (warn on use, removal post-v1) and the `CONTRACT =
"PHASE1_NARROW_V5"` token (keyed into artifact envelopes; renaming it buys
nothing and churns keys — internal, never CLI-surfaced). Everything else —
H0/H1, arms, phases, `read_gate` strings — is out of shipped code. The
benchmark-local `lx_helpers` shim keeps the name alive in `benchmark/`, which
is correct: that is where its users live.

## Is anything shipping solely because of sunk cost?

No. The closest call was `_frozen/eligibility.py`'s location (provenance, not
need), but moving it is cosmetic churn with re-validation cost — correctly
deferred. Native `.c` sources ride in the wheel alongside binaries; harmless
transparency, arguably good. The LibreOffice probe stays, justified by
`--require-libreoffice`.

## Did any cleanup create accidental coupling?

Reviewed each seam: `_identity.py` is imported one way (cache/artifact read
it; it reads nothing product-internal except `__version__`) — no cycle.
`cache_summary` reads the filesystem but never the runtime — diagnostics-only.
The XML guard lives inside `validate.py` with no new imports. Observer
diagnostics are message-only (exit codes unchanged). Config aliases AND with
`reads` — the one semantic choice; documented, tested, windowed. No coupling
found.

## Which remaining complexity is genuinely required?

- Two artifact `validate`/`ensure` layers (fast gate vs semantic gate) — yes,
  the lock placement demands it.
- Three-process config handling (launcher default, runner prepare, bootstrap
  fallback) — yes, each process hardens what it uses.
- `LIBRECALC_*` internal handoff vars — yes, minimal already.
- Dual receipt shapes (degraded `OBSERVER_RECEIPT_MISSING` vs full) — yes,
  honest degradation.
- `direct.py`'s openpyxl-utility imports (Translator, number formats) — yes,
  semantic mimicry requires them.

## Would you maintain this v1 for a year?

Yes, with two scheduled chores: (1) remove the config aliases post-v1
(the warning text promises a window — keep the promise or extend it loudly);
(2) grow the cache story (quota or better tooling) before heavy users arrive.
Neither is urgent; both are tracked.

## Blockers vs preferences

- No blockers found in this re-read.
- Preferences (noted, not acted on): codebase-wide ruff I001/BLE001 noise
  predates this phase and was deliberately left alone (only new F401s fixed);
  `profile_ns`/`times`/`events` remain in run dirs as documented-unstable;
  `--verbose` == `--json` is now documented rather than split.
