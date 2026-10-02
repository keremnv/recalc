# R6: D1 confirmation + productization — REPORT

Branch: `research/artifact-decode-product-confirmation` (from rc4 `fed04b5`)
Preregistration: `PREREGISTRATION.md` (`d84a3bfd…`), committed before scoring.
R5 probe verdict left intact: `PRODUCT_CANDIDATE`. This phase is the
independent confirmation.

## 1. Executive verdict

**PRODUCTIZE.** Every preregistered gate passes: 52/52 semantic canon,
40/40 adversarial, 12/12 corruption, 52/52 full-command parity, decode
−3.12 s (−62.2%), full-command −3.00 s tracking decode, worst
persistent delta +0.036 s, cold/build clean, artifacts byte-identical
with 52/52 rc4-built reuse, memory −5.3%. D1 integrated as rc5 (§18).

## 2. R5 evidence being confirmed

R5 (`2b626d27…`, branch `research/artifact-decode-probe`): per-cell
canonicalize/reparse round-trip = 69% of decode; D1 (direct
validated-dict reconstruction, same bytes) measured 2.45–3.42× decode,
A decode 5.272→2.036 s, warm 15.244→11.848 s, 52/52 + 40/40 + 52/52
parity, 12/12 corruption, byte-identical artifacts. D1b rejected
(slower); codec/format/segmentation rejected/deferred. R5 never
productized. Absolute seconds differ by window (single-host variance);
R6 gates use paired same-window gains.

## 3. Frozen D1 contract

`CONTRACT.md`: replace `_value_from_json(canonical(typed).decode())`
with `_direct_value(typed)` after unchanged `_check_typed` validation;
explicit `math.isfinite` rejection preserves `allow_nan=False`
behavior. Invariants: same bytes/format/validation/encode/admission/
routing/API; stdlib-only; no D1b, no format/persistence/API changes.

## 4. rc4 source revalidation

Branch src == `master` (`fed04b5`) before porting: format
`JSONZ_MEMORY_V1`, `_check_typed` at :139 runs before reconstruction
at :141, redundant round-trip present, no intervening master changes.
R5 evidence fully applicable. Note (pre-recorded in prereg §8):
`RUNTIME_VERSION` participates in `artifact_key` + sidecar validation,
so a package-version bump mechanically invalidates artifacts (one-time
rebuild) — existing key policy, not a D1 requirement.

## 5. Preregistered gates

Semantic (52/52 canon + 40/40 adversarial + 52/52 parity + suites),
corruption (12/12), economic (≥25% + ≥1.0 s decode, full-command
tracking, ≤83 ms vs rc4 control), order-bias rule (alternating arms
by workload index; flags re-run once with opposite order and count
only if persistent), compatibility (bytes/format/migration/deps/
admission), build/cold (no systematic regression; >50% tripwire).
Full text: `PREREGISTRATION.md`.

## 6. D1 product implementation

Exact R5 `be806c3` delta ported (`artifact.py`, +35/−2) with the
comment sharpened to the stated invariant; nothing else touched.
Six maintained unit tests added (`test_product_hygiene.py`): scalar/
temporal/formula reconstruction, legacy-equivalence battery, NaN/±Inf
rejection, unknown-kind rejection. Hygiene: 36/36.

## 7. Semantic-state equality

Pristine rc4 (control worktree) vs merged D1 on frozen 52 A/B
artifacts, identity-independent canon comparison: **52/52 exact**
(`SEMANTIC_PARITY.jsonl`).

## 8. Adversarial certification

R3/R5 40-case suite over D1 vs pinned openpyxl: **40/40, 0 failures**
(26 direct / 14 reference), same routing/exit/streams/state/
exceptions, unweakened normalization. (`ADVERSARIAL_RESULTS.jsonl`)

## 9. Corruption/fail-closed certification

All 12 R5 cases on rc4 control vs D1: **identical reject, PASS**
(`CORRUPTION_RESULTS.json`). NaN/non-finite payloads reject on both
(explicit finite checks replace the canonicalization side effect).

## 10. Full-command parity

Frozen A/B, rc4 vs D1, exit + normalized stdout + state + route:
**52/52** (`FULL_COMMAND_PARITY.jsonl`). Zero route differences
(admission/serving untouched, as required).

## 11. Warm decode result

Population A paired medians: decode 5.014 → **1.896 s (−3.12 s,
−62.2%)**, clearing the ≥25% + ≥1.0 s bar ~2.5×/~3×. All 7 giants
improve (−0.35…−0.53 s each); smalls neutral-to-better at ms scale.

## 12. Representative full-command economics

A warm total: 13.158 → **10.157 s (−3.00 s, −23%)**, tracking decode
(−3.12 s) — no disappearance. B supporting consistent. Rows:
`PERFORMANCE_RESULTS.jsonl`. (Absolutes differ from R5's window per
the documented single-host variance; paired gains reproduce.)

## 13. Non-regression/order-bias analysis

Alternating arm order per prereg. One +0.113 s flag (FM_02_01__bb15,
tiny direct, decode delta −4 ms — mechanistically implausible):
re-run 3 consecutive times including opposite arm order →
−0.005/−0.006/−0.039, never reproduced → order-bias noise per the
predefined rule. Worst persistent delta: **+0.036 s** (noise scale).
Gate passes. Reversal rows: `*_revflag*.jsonl` (provenance).

## 14. Cold/build sanity

Encode untouched; D1/rc4 artifacts byte-identical (52/52). Cold
ratios 0.72–1.12 except one single-rep 1.54× flag on D_10_10, which
the prereg-ordered investigation resolved as noise (3-rep fresh-cache
characterization fully overlapping: rc4 [10.0,9.4,9.9] vs d1
[9.5,9.9,9.1]). No systematic cold regression. (`COLD_RESULTS.jsonl`)
No cold-acceleration claim made.

## 15. Artifact/cache compatibility

rc4-built artifacts under D1: **52/52 REUSED with equal semantics**
(`ARTIFACT_COMPATIBILITY.json`). D1 is byte-compatible: no format
bump, no migration, no D1-caused invalidation. (The rc5 *package
version* bump below does rotate keys once via existing
`RUNTIME_VERSION` policy — documented in §18, not a D1 requirement.)

## 16. Memory

D_10_10 peak RSS warm: 148,460 → **140,612 KB (−5.3%)**. No
regression; reduction secondary, population-limited claim only.

## 17. Productization decision

**PRODUCTIZE.** All semantic, corruption, economic, compatibility,
and non-regression gates pass, several with large headroom. CLOSE
and REVISE_AND_RETEST do not fit (no reproduction failure, no
mechanical defect — both flags resolved as noise by predefined rule).

## 18. Conditional rc5 integration

Performed (verdict PRODUCTIZE): D1 product commit (`ad715bf`: decoder
+ 6 unit tests, +70/−2), rc5 version/docs commit (`c476c36`:
`pyproject`, `__version__`, CHANGELOG, README, COMPATIBILITY,
evidence docs with conservative decode-only claims), vector-rotation
commit (`8350b7f`: fixed key vector rotated for the intentional bump,
sanctioned by the test's update rule). `RUNTIME_VERSION` key policy
mechanically rebuilds rc4 artifacts once on first rc5 touch (cold
only) — documented in CHANGELOG, not redesigned; D1 itself reuses
rc4-built artifacts (52/52 proven in §15).

## 19. Release verification

On the rc5 tree, all green: product suites 49/49; full suite 890
passed + 4 documented pre-existing + 12 skipped; adversarial 40/40;
corruption 12/12 PASS; semantic parity 52/52; full-command parity
re-run 52/52 (independent window: decode −64.1%, warm −3.0 s, max
delta +0.012); clean native build; wheel + sdist;
fresh-venv install; `--version` → 0.2.0rc5; `doctor` 8 PASS; Quick
Start end-to-end (DIRECT_RUNTIME/PASS); wheel contains 0
research/staging/probe paths; doc links intact. No probe-only
harness ships (research lives only under `research/`, excluded from
the wheel by existing packaging rules).

## 20. Limitations

- Single-host timing; giant-book absolutes vary ±30% across windows;
  gates use paired within-window deltas.
- Small-workload ±50–120 ms order noise handled by the predefined
  alternation + reversal rule.
- Confirmation covers the 52-workload + 40-case + 12-case frozen
  populations; no claim beyond them.
- rc5 key rotation (§18) is version-policy-caused, not D1-caused.
- Stopping here per §25: no R7 mechanism begun.
