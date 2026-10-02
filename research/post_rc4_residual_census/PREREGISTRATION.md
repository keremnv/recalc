# R4 post-rc4 residual census — preregistration

Written and hashed BEFORE final scoring. Baseline: rc4 product commit
`fed04b5fb1b6bc4e3510b93c20673434fa4c83f8` (`master`).

## 1. Question

After rc4 removed the dominant iteration-gated reference parse cost, where
does remaining representative full-command time go, and is any additional
narrow Recalc mechanism economically earned?

## 2. Populations (frozen reuse)

- A: representative 30, B: fixed 22 — identities from R1
  `research/execution_surface_census/WORKLOAD_MANIFEST.json`
  (sha256 `ab71c8d4…037bb`). Staged clean dirs under R1 `_staging`
  re-verified by script/workbook SHA before scoring; any mismatch or
  irreproducible workload is reported and the denominator preserved
  honestly (no substitution).
- C: ordinary agent-script sample — R1 C identities reused; execution
  ledgers reused frozen (§7); only a static classifier re-scan is new.
- A authorizes product claims. B/C are supporting only. No
  contact-selected or mechanism-selected population may authorize a
  representative claim.

## 3. Timing protocol

- Arms per A/B workload: BASE (plain `python workload.py`, 3 reps),
  HOOK (R1 census hook under plain python, 2 reps — op counts/parse
  attribution), PROD-WARM (`recalc-agent run`, warmup + 3 reps on a
  persistent per-workload cache, REUSED artifacts), PROD-COLD (1 rep,
  fresh cache, for artifact-build cost).
- Warmup rep discarded. Medians across reps. Timeout 300 s; timeouts
  reported, never silently dropped.
- Fixed-tax microbench: empty script + tiny direct script, BASE vs
  PROD-WARM (10 reps each), plus `-X importtime` split and receipt
  setup/observer timings.
- Memory: `/usr/bin/time -v` peak RSS on 4 workloads (large reference,
  large direct-iteration, small direct, write-heavy), BASE vs PROD-WARM.
- Noise floor: R1 G5 repeatability median 41.5 ms; small-workload
  wrapped-vs-bare noise ±~50 ms (R3 §9). A candidate's representative
  value must materially exceed both noise and plausible integration
  cost — no fixed round-number bar.

## 4. Attribution buckets

Process envelope (launcher, observer, python startup, openpyxl import,
bootstrap, admission, receipt/teardown); Recalc read path (freshness,
validation, build, decode, install, literal serving, iter_rows serving,
proxy construction, merged handling); reference path (parse,
materialization, fallback); user program; mutation (dispatch, save,
reopen); external recalc; assurance (snapshot, detection, delta,
validation, replay, receipt); explicit `unattributed` remainder.
No invented precision: unmeasurable splits stay aggregated.

## 5. Routing/blocker census

Per A/B workload: route, admission decision, exact classifier blocker
set (static, on frozen scripts), direct-throughout vs fallback vs
reference, artifact state, fallback reasons, materialization. Every
remaining reference workload gets a blocker-family classification.
Blocker presence alone never earns removal.

## 6. EARNED rule

A candidate is `EARNED_FOR_FEASIBILITY_PROBE` only if, on Population A:

    representative affected mass × realistically avoidable fraction
    − integration/runtime tax − compatibility risk
    = clearly positive full-command value

with affected mass concentrated (not diffuse across rich/uncertain
shapes), avoidable fraction grounded in measured bucket splits, and
value materially above the §3 noise floor. Otherwise `OBSERVE_MORE`
or `CLOSED_FOR_NOW`. At most one or two EARNED items; “rc4 exhausts
the frontier” is an acceptable verdict. Inspection/token APIs stay
closed absent genuinely new overturning data (R1: median observation
479 B, agents already filter).

## 7. Frozen-reuse declarations (not new scoring)

- R1 `OPERATION_CENSUS.jsonl` op-count demand (deterministic per
  script) and R1 C inspection ledgers: reused as demand evidence.
- R3 A/B ON-arm walls/routes: cross-check only, never the R4 headline.
- R4 headlines come only from §3 runs on the rc4 baseline.

## 8. Instrumentation validity

HOOK/BASE parity (exit/stdout-norm/workbook-state) re-verified on the
scored workloads; hook overhead quantified; any workload where
instrumentation changes admission is flagged and excluded from
attribution (kept in routing with a note).
