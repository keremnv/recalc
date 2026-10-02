# R5: Artifact-decode probe — REPORT

Branch: `research/artifact-decode-probe` (from rc4 `fed04b5`; `master` untouched)
Preregistration: `PREREGISTRATION.md` (`2b626d27…`), committed before scoring (`a0c66c4`).
Probe implementation (research branch only, NOT merged): D1 in
`src/recalc_agent/read_engine/artifact.py` (~35-line diff).

## 1. Executive verdict

**PRODUCT_CANDIDATE.** Candidate D1 (direct validated-dict → value
reconstruction, same artifact bytes, no format change) passes every
preregistered gate:

- semantics: 52/52 canon-identical vs pristine rc4, 40/40 adversarial,
  52/52 full-command program parity;
- corruption: 12/12 reject, including NaN-payload parity;
- decode mass: −3.24 s (−61.4%), far above the ≥1.0 s / ≥25% bar;
- full-command: −3.40 s on A, tracking decode (no disappearance);
- non-regression: max +0.056 s (initial straddles resolved by
  arm-reversal as order-bias noise);
- build/storage: no tripwire, artifacts byte-identical, memory −5.6%;
- scope: decoder-only, no dependency, no migration, no API change.

D1b (manual coord validation) is correct but slower than D1 — rejected
by one-variable discipline. Codec, binary-format, and sheet-segmented
candidates were rejected/ deferred by the decomposition (see §7).
Per the stop rule, D1 is NOT integrated here; that awaits a separate
confirmation/productization decision.

## 2. Why decode became the frontier

R4 (`8b21a4f1…`) closed the reference-parse frontier (64.5 s → 0.23 s)
and re-measured the rc4 residual: PROD-warm 12.95 s, of which artifact
decode was 4.97 s (38%), concentrated in 7 large-book workloads at
~0.65–0.73 s each (~70% of those walls). R4 authorized exactly one
feasibility probe: artifact decode acceleration — this phase.

## 3. Current artifact format and decode path

Format `JSONZ_MEMORY_V1` (`src/recalc_agent/read_engine/artifact.py`):
`MAGIC + u32 header-len + JSON header + u64 compressed-len +
zlib(level=1) payload + sha256(body)`. Header carries source/decoder/
contract/format identity + payload sha. Payload: one JSON doc
`{"sheets": [{name, bounds[4], merged[[4]], cells[[coord, dtype,
typed]...]}]}` with canonical (sorted-keys, compact) encoding.
Typed values: `scalar/array/datatable/datetime/date/time/timedelta`
dicts. Validation: whole-blob sha, header shape/identity, decompress
caps (512 MiB), payload sha, per-sheet/per-cell structural checks
(bounds, COORD regex, dtype set, `_check_typed`, dupe/cell caps),
sheet-count match. Reconstruction: `SheetInfo` (bounds, merged
tuples, `cells: dict[coord, (value, dtype)]`) → `MemoryBook`.
Always fully eager; sheet offsets are NOT recoverable without parsing
the whole JSON doc (single-document layout → FORMAT_BLOCKED for lazy
decode, §6). Copies per decode: file bytes → decompressed bytes →
parsed JSON tree → validated store (+ per-cell re-encode strings).

## 4. Preregistered gates

Decomposition-validity (±15% sum), sheet-touch rule (≤0.5
PROMISING / ≥0.8 WEAK), and the 7-clause candidate economics
(semantics, corruption, ≥1.0 s + ≥25% mass, full-command tracking,
≤83 ms non-regression vs rc4 control, build tripwire at >50% cold
regression, narrow scope). No codec pre-picked. Full text:
`PREREGISTRATION.md`.

## 5. Decode component profile

Low-perturbation duplicate-instrumented decode on the frozen 7-book
subset (~135k cells/book). Gate: instrumented/ref = 0.962 → PASS.
7-book sums (in-process window):

| component | s | share |
|---|---|---|
| per-cell typed re-encode (`canonical`) | 3.70 | 46% |
| per-cell typed re-parse (`_value_from_json`) | 1.84 | 23% |
| per-cell validation (regex + `_check_typed`) | 1.29 | 16% |
| whole-payload `json.loads` | 0.78 | 10% |
| dict/tuple allocation | 0.19 | 2% |
| zlib decompress | 0.16 | 2% |
| sha/header/envelope | 0.06 | <1% |

The per-cell `canonical(typed).decode() → _value_from_json` round-trip
is 69% of decode: the already-parsed JSON tree is re-serialized and
re-parsed once per cell. Decompression (2%) and structural JSON parse
(10%) are minor. Raw rows: `CURRENT_DECODE_PROFILE.jsonl`.

## 6. Sheet-touch census

In-process real-runtime driver with a `MemoryBook.cell` touch counter
(all 7 workloads DIRECT_RUNTIME): every workload touches 1–2 sheets
with a touched cell-mass fraction of 0.005–0.205 — all ≤0.5, hence
**LAZY_SHEET_PROMISING** by the prereg rule. But the single-JSON
layout requires full parse before any sheet is reachable, so lazy
decode needs a new segmented format + migration. Deferred (see §7):
D1 captures most of the same mass with zero format change. Raw rows:
`SHEET_TOUCH_CENSUS.jsonl`.

## 7. Candidate selection

- **D1 (implemented):** drop the round-trip; map validated dicts
  directly to values (NaN/Infinity rejection preserved explicitly —
  `canonical(allow_nan=False)` previously did this). Attacks 69%.
- **D1b (implemented, REJECTED):** D1 + manual coord validation.
  Language-identical (200,009-case fuzz, 0 mismatches) and 52/52 +
  12/12 clean, but 2.27–2.59× vs D1's 2.45–3.42× — the C regex beats
  the Python loop; validation cost is `_check_typed`, not COORD.
- **A (codec):** REJECTED — decompression is 2%.
- **B (binary format):** REJECTED — JSON parse is 10%; schema/
  dependency burden unjustified.
- **C (sheet segmentation):** DEFERRED — touch data supports it but
  it needs a new format + migration for mass D1 already captures.
- **E (close):** not needed.
Record: `CANDIDATES.json`.

## 8. Semantic parity

- Canon state comparison (duck-typed, module-copy-robust) of pristine
  rc4 vs candidate decode on all 52 A/B artifacts: D1 **52/52**,
  D1b 52/52. (`SEMANTIC_PARITY.jsonl`)
- R3 40-case adversarial suite executed over in-src D1 vs genuine
  openpyxl: **40/40, 0 failures** (26 direct / 14 reference).
- Full-command program parity (exit + address-normalized stdout +
  workbook state), rc4 vs D1: **52/52**. (Raw-byte diffs were only
  object-address reprs — proven benign by direct diff.)

## 9. Corruption/fail-closed behavior

12 cases (truncated header/payload, wrong checksum/source-hash/
decoder/format versions, corrupt stream/structure, dup coordinates,
NaN typed value, impossible coordinate/kind): rc4 and D1/D1b all
**REJECT — 12/12 PASS**, never silently serve. The NaN case is the
critical D1-specific parity point (explicit finite checks replace
`canonical(allow_nan=False)`). (`CORRUPTION_CASES.json`)

## 10. Decode microbenchmarks

In-process, pristine-rc4 baseline, ×5 medians (`DECODE_BENCHMARKS.jsonl`):

- D1: 2.45–3.42× on the 7 books (e.g. 0.67→0.27 s), ~3.1× on smalls.
- D1b: 2.27–2.59× (uniformly slower than D1 → rejected).
- Remainder ≈ `json.loads` + `_check_typed` + direct-value mapping.

## 11. Representative full-command results

rc4 (pristine `master` worktree) vs D1 (branch src), paired same-window,
warmup+3 warm + 1 cold, normalized parity (`FULL_COMMAND_RESULTS.jsonl`):

- A warm total: 15.244 → **11.848 s (−3.40 s, −22%)**.
- A decode mass: 5.272 → **2.036 s (−3.24 s, −61.4%)**.
- Gate (c) needs ≥1.0 s + ≥25%: exceeded ~3× / ~2.5×.
- Full-command tracks decode (−3.40 ≈ −3.24): no disappearance.
- Routes identical everywhere; B supporting consistent (all improve
  or flat within noise).
- Non-regression: max +0.056 s. Three initial +0.07…+0.12 straddles
  on tiny/reference workloads (mechanistically impossible — reference
  path never decodes) were re-run with reversed arm order and all
  vanished (+0.018/−0.029/+0.005/−0.012): order-bias noise, documented
  in `_rev2`/`_rev3` rows.

## 12. Build/cold economics

Encode path untouched → artifacts **byte-identical** (all 52:
`ARTIFACT_SIZE_RESULTS.json`). Cold full-command: no tripwire — ratios
0.72–1.32, all small-book noise or faster (cold-serve also benefits
from D1); giants 0.76–1.12. No amortization claim needed: build is
unchanged, cold never systematically worse. (`BUILD_RESULTS.jsonl`)

## 13. Artifact-size impact

Zero — same bytes in, same bytes out. No migration, no cache clear,
no old-decoder fallback needed. (`ARTIFACT_SIZE_RESULTS.json`)

## 14. Memory

D_10_10 peak RSS warm: rc4 148,580 KB → D1 **140,212 KB (−5.6%)**.
Removing the per-cell re-encode strings cuts transient allocation;
no regression.

## 15. Lazy-sheet result, if tested

Not implemented as a candidate (deferred per §7): touch census says
PROMISING, but the format is blocked and D1 captures ~61% of decode
mass without a format change. A segmented format would now chase at
most the ~2.0 s D1 remainder, minus JSON-parse floor (~0.8 s) and
migration burden — left as a documented non-pursuit with the touch
census preserved for any future re-evaluation.

## 16. Dependency/packaging implications

None. D1 is stdlib-only (`math`, `datetime`), same-module, ~35 lines.
No wheel-size, platform, or maintenance impact beyond the small diff.

## 17. Updated persistence opportunity

R4's theoretical residency prize (~5.0 s decode) shrinks to the D1
remainder (~2.0 s on this window, ~40% of former), minus any
IPC/validity tax — and only across same-workbook invocations (reuse
still unmeasured). Persistent-worker prize unchanged (~1.6 s parent
CLI). Do not double-count the 3.24 s D1 already removes. Verdicts
stand: persistence remains OBSERVE_MORE with a smaller prize.

## 18. Product-candidate decision

**PRODUCT_CANDIDATE** for D1: all seven preregistered clauses pass,
most with large headroom; the change is narrow, dependency-free,
format-preserving, and migration-free. D1b/A/B/C/E all resolved
(rejected/deferred with recorded reasons). Per the stop rule, D1 is
NOT integrated into product here — the branch carries the probe diff
for a future confirmation/productization decision. Suggested
confirmation (not begun): re-run hygiene + full suite + adversarial +
A/B parity on the merged state, plus packaging/venv/doctor checks.

## 19. Limitations/reopen conditions

- Single-host windows; giant-book absolutes vary ±30% across windows
  (same-bytes control: the two D_10_07 tasks share workbook
  `0d51c60e…`, yet D1 decode measured 0.24–0.40 across runs) — gates
  use paired within-window deltas, robust to this.
- Small-workload ±50–120 ms order-bias noise handled by reversal
  checks; the 83 ms rule needed its control-comparator lesson again.
- Incidents, all resolved transparently: (1) the sitecustomize
  injector was silently defeated by the product bootstrap's own
  `sitecustomize.py` shadowing it on the script child's PYTHONPATH —
  the first full-command dataset measured rc4+injector-overhead and
  was discarded; evidence was re-collected with the in-src probe vs
  a pristine worktree control; (2) an A∩B ledger-merge clobber was
  repaired by re-measurement; (3) a DE crash mid-merge lost the d1
  bench/parity files — both re-run (bench vs pristine baseline,
  parity with a duck-typed canon), d1b files were unaffected.
- D1b/coordinate micro-optimization: closed unless a future profile
  shows validation dominant after D1.
- Sheet segmentation reopens only if a future use case needs the
  sub-2 s remainder AND justifies a format migration.
- Raw run dirs/caches under `_staging/` (ignored); intermediate
  diagnostic ledgers (`_clean7`, `_rev2`, `_rev3`, `_fixB`) kept as
  provenance for the merges above.
