# Public visual evidence bundle

Step 1 of the public visual evidence roadmap: four documentation figures
with a deterministic generator. The figures distinguish schematic mechanism
from measured evidence, and keep scope boundaries inside the image so each
figure survives on its own.

## Figures

| asset | kind | in-image scope | used in |
| --- | --- | --- | --- |
| `docs/assets/recalc-selective-execution.svg` | schematic | `SCHEMATIC · NO TIMING` | README |
| `docs/assets/recalc-task-replay-outcomes.svg` | measured | `MEASURED · WARM PAIRED TASK REPLAY · BASE vs RECALC 0.2.0` | README, PERFORMANCE |
| `docs/assets/recalc-controlled-applicability.svg` | measured | `MEASURED · SPREADSHEETBENCH-2 CONTROLLED STRATUM · 6 TASKS · 9 TRAJECTORIES` | PERFORMANCE |
| `docs/assets/recalc-r3-distribution.svg` | measured | `MEASURED · HISTORICAL R3 MECHANISM POPULATION · WARM · OFF → ON · 30 WORKLOADS` | PERFORMANCE only |

Machine-readable provenance: [manifest.json](manifest.json).
Asset status (current vs secondary vs historical):
[docs/assets/README.md](../../assets/README.md).

## Sources

Measured pixels trace only to frozen evidence; the generator recomputes
every displayed number and fails on mismatch:

- Figure B trajectories (`tier1-r01-P-Debugging-07_01`,
  `tier1-r06-O-mimo-Financial_Model-11_05`,
  `tier1-r14-O-mimo-Debugging-08_06`) from
  `research/benefit_evidence_ledger/benefit_ledger.json`.
- Figure C controlled stratum (`controlled_subset`: 136 executed
  invocations = 119 reference + 10 fully direct + 7 admitted-but-zero)
  from `research/spreadsheetbench_applicability_audit/summary.json`.
- Figure A is schematic: it encodes current product semantics (admission,
  reference path, validated read state supplying supported reads,
  fallback, external observer, receipt) and carries no measurements.
- Figure D plots all 30 per-workload ON/OFF ratios from
  `research/tier2_distribution_audit/tier2_workloads.json`, cross-checked
  against `tier2_summary.json`. It exists to show
  distribution/concentration behind the historical R3 aggregate, not to
  provide a new headline performance claim: OFF→ON is historical
  mechanism evidence, must not be relabeled BASE→Recalc 0.2.0, and the
  aggregate is heavy-tailed.

## Verify and rebuild

```bash
python docs/evidence/public_visuals/generate.py --verify
python docs/evidence/public_visuals/generate.py --build
```

`--verify` checks identities, comparator, warm regime, runtimes, relative
changes, invocation counts, and served shares; it runs no workloads, calls
no models, and needs no network. `--build` verifies first, then rewrites
the three SVGs byte-deterministically (no timestamps or paths): two
consecutive builds with unchanged inputs produce no diff.

## Visual conventions

- BASE/reference is neutral; Recalc/directly-served is one accent; shape
  (square vs circle), direct labels, and hatching carry meaning so the
  figures survive grayscale. No red/green good-vs-bad encoding.
- Fallback and reference execution are neutral by design: they are the
  documented outcome for uncertain or unsupported work, not failure. The
  admitted-but-zero segment is hatched, never failure-coded.
- Served-block BASE shares are descriptive; no threshold is established.
- Operation counts (direct reads, iteration cells) measure depth inside
  served invocations, not prevalence across workloads, so they appear in
  prose only and never as prevalence bars.

## Scope notes

- The existing `docs/assets/recalc-performance-vignette.svg` (FM:08_02
  read-only inspection step) is untouched and stays a PERFORMANCE-only
  secondary figure with its own generator.
- Figure D is the distribution figure: ranked per-workload ratios with
  concentration context. No aggregate `−79%` hero graphic is built.
