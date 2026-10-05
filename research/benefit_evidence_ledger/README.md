# Benefit evidence ledger

Canonical, mechanically traceable record of where Recalc has demonstrated
benefit — and where it has not. Future source of truth for README examples
and `PERFORMANCE.md`. Research-only; no public docs changed here.

- Branch: `research/benefit-evidence-ledger`
- Builder: `build_ledger.py` (deterministic; primaries read-only)
- Ledger: `benefit_ledger.csv` / `benefit_ledger.json` (77 rows)
- Summary: `summary.json`
- Catalogs: `positive_cases.md`, `boundary_cases.md`
- Matrix: `claim_support_matrix.md`
- Sources: `sources.md`

No new execution. No historical verdict modified.

## Benefit-status taxonomy

Row-local statuses; never transfer a result across units (a faster block
is not a faster task; an aggregate is not a typical case).

| status | definition | rows |
|---|---|---|
| `WHOLE_TASK_BENEFIT` | complete measured trajectory/task replay faster under Recalc | 4 |
| `SUBSTEP_BENEFIT` | defined substep faster; no whole-task result from that measurement | 18 |
| `DIRECT_BLOCK_BENEFIT` | served block faster (block unit only) | 10 |
| `DIRECT_SERVICE_NO_WHOLE_TASK_BENEFIT` | useful service occurred but the task did not improve | 4 |
| `NO_USEFUL_DIRECT_SERVICE` | executed; zero served loads/reads (any delta is unattributable noise/tax) | 31 |
| `SUBSTEP_NO_BENEFIT` | measured substep not faster | 5 |
| `CONDITIONAL_MECHANISM_EFFECT` | population aggregate showing mechanism value | 2 |
| `NO_POPULATION_BENEFIT` | population aggregate showing no benefit | 3 |
| `NOT_EVALUATED` | no valid paired evidence at that unit (valid label; zero rows currently) | 0 |

Assignment rules (mechanical, in `build_ledger.py`): served =
`direct_served_loads >= 1`; faster = `recalc < base` on the row's
comparator. Unserved rows can never be benefit rows, even when trivially
faster (e.g. r08/r09: −0.09/−0.07 s with zero service).

## Evidence hierarchy (task section 17)

| rank | evidence | permits claiming |
|---|---|---|
| A. whole-task measured benefit | 2 trajectories (r01, r06) | "this task ran faster" — for those tasks only |
| B. substep measured benefit | vignette + 17 frozen workload windows | "this step ran faster" — never a task claim |
| C. direct-block measured benefit | 10 served blocks, all faster | "served blocks were faster" — never beyond observed blocks |
| D. mechanism/population evidence | R3/R2 aggregates | "certified reads gain when the contract applies" — with distribution context |
| E. boundary / no-benefit evidence | counterexamples, fallbacks, no-benefit populations | "and here it did not help" — mandatory companion to A–D |
| F. research-only hypothetical | thresholds, fit models | nothing public; questions only |

## Recommended public case studies (task section 18)

**Whole-task #1: r06 `Financial_Model:11_05` (Mimo).** 28.001 → 26.141 s
(−1.860, −6.6%); 5 served blocks, 9,271 reads, 5,822 iteration cells.
Teaches: an iteration-heavy analysis phase inside a real mixed
trajectory can move the task total. Supports: whole-task benefit exists.
Does not support: FM-family generality (FM:07_01 regressed).

**Whole-task #2: r01 `Debugging:07_01` (Claude).** 15.477 → 13.210 s
(−2.267, −14.6%); 3 served blocks, 63 point reads, 0 iteration cells.
Teaches: even modest point-read service wins when the rest of the task
is quiet. Nonredundant with #1: different model, different read shape
(points vs iteration), no cells. Does not support: Debugging-family
generality (D:08_06 regressed).

**Substep: FM:08_02 vignette (released 0.2.0).** 3.6866 → 0.7320 s
(−80.14%) on one read-only inspection step. Teaches: the mechanism on a
clean, fully provenanced step. It survives on evidence quality (release
version, BASE comparator, parity, repro bundle) but must stay labeled
`SUBSTEP_BENEFIT` — top-quintile, not typical.

**Counterexample: r14 `Debugging:08_06` (Mimo).** +0.922 s task
regression despite 4,607 reads / 3,480 cells served (direct block itself
−0.258 s). Teaches the share boundary: 5% direct share cannot move the
task. Nonredundant: substantial service, still insufficient (r18 shows
the tiny-service variant).

## Vignette verdict (task section 18/22)

The existing FM:08_02 vignette **survives** as the substep/mechanism
example: released-0.2.0 measurement, bare-BASE comparator, full parity,
strongest provenance packaging of any substep row. It must keep its
step-only framing; it is the 5th of 30 by R3 savings, not the median.

## Claims to retire or rewrite (task section 23)

1. Any wording letting `102.26 → 21.51` read as bare-BASE → released-Recalc:
   rewrite with the OFF (rc3) comparator stated.
2. Any implication that 79% is a typical-workload effect: add the
   distribution context (median ratio 0.91; top-3 = 84%).
3. Any family-level speedup phrasing ("FM/Debugging tasks"): rewrite to
   named case studies ("a SpreadsheetBench-2 FM task").
4. Any admission count presented as applicability (17/136): replace with
   served counts (10/136) plus the fallback-zero-service note.

## New benchmark needed? (task section 19)

**`NO_NEW_BENCHMARK_NEEDED_FOR_CURRENT_DOCS`.** Frozen evidence already
provides 2 whole-task positives, a strong substep example, clean
counterexamples, and both population poles. The open refinement —
calibrating the "meaningful share" threshold behind statement F — would
improve precision but no planned doc claim depends on it. Do not run it
for the docs redesign.
