# R5 artifact-decode probe — preregistration

Written and hashed BEFORE mechanism scoring. Baseline: rc4 `fed04b5`
(`master`). No codec/format pre-picked: decomposition first, then
candidates justified by the measured dominant component.

## 1. Populations (frozen)

- A: representative 30, B: fixed 22 — R1 manifest identities
  (`ab71c8d4…`), R4-verified staging.
- Decode-heavy subset (frozen, from R4 §10 — the 7 workloads holding
  ~4.97 s decode mass):
  - Debugging_10_07__6dd8f6d3a4dd
  - Debugging_10_07__e3a79d24091a
  - Debugging_10_10__c7eca76e6646
  - Financial_Model_08_01__2ea507d758dc
  - Financial_Model_08_02__4ca3ae46295d
  - Financial_Model_08_02__625ec1db4acb
  - Financial_Model_08_03__e48ea186deeb
- A authorizes. B supporting. The 7-book subset never authorizes alone.

## 2. Decomposition gate (validity, not success)

Phase timing (file/envelope, decompress, structural parse, typed
reconstruction, structure allocation, post-parse validation) must sum
to within ±15% of observed `artifact_load` wall on the 7-book subset
(median), else instrumentation is invalid and findings are
descriptive-only. Bytes/cells/sheets/sizes recorded per artifact.

## 3. Sheet-touch rule

Per 7-book workload, in-process through the real runtime with a
`MemoryBook.cell` touch counter: sheets total/touched, first-access
order, cells read per sheet, touched cell-mass fraction, global
metadata needs. Classification: touched-mass ≤0.5 → LAZY_SHEET_PROMISING;
≥0.8 → LAZY_SHEET_WEAK; between → MIXED (leans weak); plus
FORMAT_BLOCKED assessed from format analysis if segmentation would
require full-payload decode anyway.

## 4. Candidate economics (all must hold for PRODUCT_CANDIDATE)

- (a) Semantic: canonical workbook-state comparison identical on all
  frozen A/B artifacts; current adversarial + iteration suites green;
  A/B differential program behavior green. Any unexplained deviation
  disqualifies.
- (b) Corruption: every case in CORRUPTION_CASES rejects/rebuilds/
  falls back per existing policy; never silently serves corrupt state.
- (c) Warm mass: A decode-mass reduction ≥1.0 s absolute AND ≥25%
  relative (1.0 s ≈ 24× the 41.5 ms repeatability floor; 25% of the
  4.97 s mass = clearly material, not noise).
- (d) Full-command: A warm total improves correspondingly; a
  microbenchmark win that disappears whole-command fails.
- (e) Non-regression: no A workload warm-regresses vs the rc4 control
  beyond 0.083 s (R3 rule; candidate-vs-rc4 comparator per R3 §9
  lesson — never vs bare BASE).
- (f) Build/storage: build time, cold full-command, artifact size,
  and memory reported per book. Tripwire: >50% cold full-command
  regression on any A workload without reuse-grounded justification
  drops the candidate to MECHANISM_REAL_BUT_NOT_PRODUCT. No invented
  amortization: reuse frequency unknown ⇒ reported, not assumed.
- (g) Scope: narrow decoder/artifact change only; no pickle/eval/
  executable formats; new dependencies weighed against the win;
  migration via format-version rebuild (never silent reinterpretation).

MECHANISM_REAL_BUT_NOT_PRODUCT: measurable decode win failing (c)–(g).
REVISE_AND_RETEST: narrow mechanical defect only. CLOSE: nothing
meaningful. One-variable candidates; combined prototypes are
descriptive, never the authorization basis.
