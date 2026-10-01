# Representative Architecture Economics & Capability Checkpoint — Report

Frozen thin spreadsheet-agent architecture, 30 representative tasks (10/family,
seed 20260921) x 2 arms (H0 ordinary reference / H1 retained invisible stack).
Model z-ai/glm-5.3-flash (verified served), t=0, 40 calls, $0.25/instance,
900s run. H0/H1 prompts, schemas, settings identical except invisible flags.

## Verdict

- **Scores preserved**: on 8 dual-scored pairs, H1-H0 deltas are mixed
  (+0.43 to -0.46, mean -0.02) with no systematic direction; within-arm
  draw-to-draw swings (up to 0.50) dwarf between-arm deltas.
- **Completion edge to H0, not significant**: 14 vs 9 outputs; McNemar exact
  p=0.125 on all 30 pairs (6 H0-only vs 1 H1-only) and p=0.125 on the 20
  dual-uncensored pairs (4 vs 0). Replication flips both ways; one task
  (Template:16_07) shows a stable 2/2-vs-0/2 H0 gap with no mechanism
  implicated (H1 adds <1s/slot; cannot explain 900s non-completions).
- **Deterministic costs are small**: substrate 25.9s / 508s tool time (5.1%),
  capture 0.34s, freshness refreshes 1.16s. No capture failure in 16
  mutations; no validation failure.
- **Per-component decisions** (details below): retain substrate + Candidate A
  gate + capture + freshness; **drop the substrate helper backend** (slower
  than plain openpyxl, 13% adoption); **harden unguarded parsing** (1
  deterministic + 1 transient H1-only crash on untrusted bytes).

## Capability

| framing | pairs | H0-only out | H1-only out | McNemar p |
|---|---|---|---|---|
| all 30 (censoring = non-completion) | 30 | 6 | 1 | 0.125 |
| dual-uncensored only | 20 | 4 | 0 | 0.125 |

Dual-scored mod deltas (H1-H0): +0.003, -0.459, -0.042, +0.028, -0.212,
+0.057, +0.000, +0.429. Regression accuracy ~1.0 in both arms wherever
an output exists.

Replication (10 discordant pairs x 2 arms, 20 slots): 7 submitted,
4 no-submit, 9 censored. Within-arm score swings: 16_07 H0 0.40->0.90,
06_02 H0 1.00->0.50, 01_05 H0 0.68->0.47, 18_05 both arms converge 0.65.
Single-draw score gaps are noise; completion flips both ways. Stable:
03_06 H1 high both draws (0.996/0.966); 16_07 H1 fails twice; 01_06 and
02_05-H1/09_02-pair censor repeatedly.

Censoring (symmetric; not capability): H0 7, H1 6 provider-censored
(request timeouts). Taxonomy established by replay/curl proofs: (a)
provider slowdown window (~8x, 40s/call); (b) slow-finite deep histories
(84K-token prompt completes in 126s — rescued by the 240s amendment);
(c) non-terminating runaway whitespace generation at t=0 (01_06: 0/8
attempts, 280s curl yields 1034 whitespace bytes only).

## Deterministic economics (H1 totals over 60 primary slots)

- **Substrate**: initial build 24.76s (mean 0.85s/slot, ~6MB DB) + refresh
  1.16s over 493 calls + 16 rebuilds = 25.9s. Shared-fixed charged first.
- **Candidate A loads**: 59/282 loads accelerated (21%); 223 predeclared
  fallbacks ("forced real path"). H0 spy rated 281/350 loads eligible
  (80%): the A1 gate is far narrower than spy eligibility (frozen).
  Per-load saving vs H0 unit cost: median 0.32s (0.41->0.09s), mean 1.43s
  (1.93->0.50s; tail to 13.6s). Net of fast-path cost over 59 loads:
  mean-based +84s gross (+58s from-zero after substrate); median-based
  ~+19s gross (roughly neutral from-zero). A pays on large workbooks.
- **Candidate A non-load ops**: 91,231 accelerated (cell/value/sheetnames),
  but 95% concentrate in 5 bulk-iteration slots; 15/30 H1 slots have zero.
  542 fallbacks: 444 forced-real, 92 merged-cell, 4 unsupported, 2
  substrate-unavailable. Zero runtime fallback failures.
- **Capture**: 0.34s total (mean 11ms/slot), 16 mutations, 0 runtime
  failures, 0 validation failures. Cheap assurance; zero
  failure-prevention witnesses (nothing failed) — assurance value only.
- **Freshness**: included in refresh above (1.16s/493 calls). Cheap.
- **Helpers**: 8/60 slots used them (H0: 2 slots/40 calls; H1: 6/31).
  H1 substrate backend costs a fixed ~2.6s/call regardless of helper vs
  H0 reference ~0.1s for inspect (search ~2.6-3.3s both). The backend is
  slower than plain openpyxl with no adoption advantage. Surface identical
  both arms (no differential surface cost).

## Decisions

| component | decision | basis |
|---|---|---|
| substrate (build+refresh) | RETAIN | 5% of tool time; enables A; pays from-zero on tails |
| Candidate A + A1 gate | RETAIN (conditional) | 21% loads accelerated, net positive; narrow gate is frozen design |
| capture | RETAIN (assurance) | 0.34s; zero failures; no prevention witnesses, negligible cost |
| freshness refresh | RETAIN | 1.16s/493 calls; cheap |
| substrate helper backend | DROP -> reference in both arms | slower than openpyxl, 13% adoption; zero model-facing change |
| helper surface (lx_helpers+note) | product call, not economics | identical both arms; 8/60 adoption |
| unguarded index parsing | HARDEN (fail-closed) | 1 deterministic + 1 transient H1-only crash; veto on malformed input |

Per the stop rule, mechanism discovery stops: no component except the
helper backend fails its accounting, and no new consumers are proposed.

## Methods appendix

- Waves: A (90s request deadline): main 4-worker run + parallel/serial
  retries. B (240s, arm-symmetric, predeclared in amendment_01_timeout.md
  after curl proof, final): 23 re-released slots, 2 chains. 01_06 pair
  (Class-W proven) and 06_01 H1 (deterministic crash) stand as censored.
- Harness fixes during measurement (all invisible, audit re-PASSed):
  absolute telemetry paths; run-loop clock mix; H0 counterfactual + H1
  accelerated-load archival; fail-safe reference_api logging. 21 pre-fix
  slots voided (void_log.json); originals preserved (reps_preserved_*).
- Identity audit PASS at every worker launch; helper parity 120/120
  differential throughout.
- Spend: 129 billed attempts, $6.08 tracked from records (primaries
  $4.48); shared _spend.json meter undercounts under parallel writers
  (known defect, records are source of truth). Cap $25 never approached.
- Artifacts: reps/ (60), reps_replication/ (20), capability_scores[.json,
  _replication.json], capability_discordances[.json], helper_usage[.jsonl],
  economics.json, capability_summary.json, void_log.json,
  infra_retry_set.json, amendment_01_timeout.md, fidelity_primary.jsonl.

## Risks and limits

- 13/60 primary slots provider-censored despite 2 waves + amendment;
  dual-scored n=8. Score conclusion is "no systematic direction," not
  equivalence.
- Runaway generation is model-endpoint behavior (OpenRouter routing varies
  per call); replication under a different endpoint may censor differently.
- Median-based A savings roughly neutral from-zero; the retain case rests
  on large-workbook tails + concentration in bulk readers.
- Helper-backend verdict rests on 71 calls; direction consistent across
  helpers but n is small.
