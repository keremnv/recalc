# `new_formula_error` Feedback: Task Population & Preregistration Probe

Zero-model, mechanical task-selection probe. No model inference was run, no live
treatment was executed, the product RC (`0.2.0rc1`) and frozen architecture were
not changed, no diagnostics were added, and `new_formula_error` was not tuned.

Research question: when an ordinary Python/openpyxl spreadsheet agent creates
newly introduced formula errors, does exposing a mechanically computed list of
those errors during the trajectory cause it to produce a better final workbook?

Machine-readable deliverables live in
[formula_error_feedback_probe](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe).

## 1. Implementation inventory (PART 1, frozen)

Source files (all read-only in this probe):

- Pure check logic:
  [commit_checks.py](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/src/librecalc_mcp/domain/commit_checks.py),
  `new_formula_errors(before, after)` (lines 211-233). Inputs: two cell maps
  `{(sheet, address): (value, formula)}`. Output: `CommitFinding(check=
  "new_formula_error", sheet, address, detail="output has {KIND} here; the
  input did not")` for every cell where the output shows a spreadsheet error
  and the input shows none at the same address.
- Error recognition:
  [grid.py](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/src/librecalc_mcp/domain/grid.py)
  `SPREADSHEET_ERROR_TOKEN` =
  `#(?:DIV/0!|N/A|NAME?|NULL!|NUM!|REF!|VALUE!)|Err:\d+` (case-insensitive).
  Both evaluated error values and formula text already carrying a broken token
  (e.g. `=#REF!`) count. LibreOffice-native `Err:NNN` codes count live.
- Live error-delta computation: per-cell error presence, input vs output. No
  value-equality: a recalculated formula whose value moved but stayed non-error
  is not a finding. Both workbooks are read through the SAME engine (UNO), so
  Excel-authored vs saved representation differences cannot register.
- LibreOffice recalc path:
  [uno.py](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/src/librecalc_mcp/backend/uno.py).
  Writes call `doc.calculateAll()` before saving. Reads open the document and
  read used ranges (`getDataArray` values, `getFormulaArray` formulas,
  cell-by-cell `cell.Error`/`cell.String` for formula cells only,
  `include_errors=True`). No `calculateAll` on the read path itself; live-gate
  reads of UNO-written outputs always see freshly calculated values because the
  write path calculated before saving.
- Report summarisation: `commit_gate._summarise` — complete counts plus
  per-sheet totals, at most 8 representative addresses per sheet / 80 overall,
  with a `representatives_are_a_sample` flag.
- Write-stage reporting (informational, never blocks):
  [calc_tool.py](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/benchmark/sweagent/librecalc/lib/calc_tool.py)
  `_with_write_report`, attached to `write`, `fill-formulas`, and `program`
  (not `upsert-chart`). Fires on the first saving write with a nonempty report;
  zero-finding writes pass through silently; report exceptions never break a
  successful write.
- Submit-stage reporting (blocks once):
  [commit_gate.py](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/benchmark/sweagent/librecalc/lib/commit_gate.py)
  `evaluate` via the `commit_report` command, invoked by the `bin/submit`
  wrapper, which prints `<<SWE_AGENT_SUBMISSION>>` only when the gate exits 0.
  The first submit returns findings and does not finalise; the next submit
  always succeeds. Gate errors fail open. Deliveries are tracked per stage
  (`reported_write` / `reported_submit`).
- Durable recording: `record_report` appends `{stage, report}` to
  `.librecalc_commit_report.json` beside the workbook; trajectories carry the
  observation as the durable record (the output mount is discarded).

All Phase-4 fixes are present in the harness bundle: write-stage delivery,
complete counts, per-sheet counts, sampled addresses, durable recording
(pinned by [tests/test_commit_gate.py](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/tests/test_commit_gate.py)).

Product RC status: the live mechanism (gate + wiring) exists ONLY in the old
structured-harness bundle (`benchmark/sweagent/librecalc/`) plus the frozen pure
domain logic (`src/librecalc_mcp/domain/commit_checks.py`). It is NOT in the
current product package (no reference in `src/librecalc_agent/*` or
`src/librecalc_mcp/server.py`), and the frozen architecture retains the ordinary
coding-agent core with mechanism discovery CLOSED. `calc_compare`/`semantic_diff`
carries a related `formula_errors` added/removed/changed section, but that is
agent-invoked self-comparison, not the world-initiated gate. Nothing was ported
or modified by this probe.

Full detail:
[implementation_inventory.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/implementation_inventory.json).

## 2. Historical live evidence (PART 2)

### 2a. A corrected extractor changes the counts

The shipped `benchmark/extract_commit_reports.py` regex only matches top-level
submit-stage payloads (`{"ok":false,"schema":"commit-checks-v1",...}` at end of
observation). Write-stage deliveries are embedded as
`{...,"commit_checks":{...},"note":...}` inside the write result, so the regex
match swallows trailing braces and its `json.loads` fails silently. Every
write-stage delivery was dropped from all previously reported live counts.

A corrected extractor (JSON-parse the whole observation; accept top-level
reports and `commit_checks` embeddings; balanced-brace fallback) recovers:

- 106 deliveries (71 write-stage + 35 submit-stage) over 74 tasks
  (previously: 33 submit-only reports).
- 297 run: 60 write + 25 submit deliveries over 60/100 Debugging tasks
  (previously: 25 tasks).
- One previously unknown gate-enabled run: `glm-optional-isa-strict-three-1`
  (Debugging:06_09, write-stage, 26 `new_formula_error`).
- `kimi-k2.7-commit-write-four-low-1` is NOT a gate run at all: it ran
  2026-08-27, four days before the gate was committed (2026-08-31). Its name is
  a red herring ("commit" = write-commit canary, pre-gate).

Live precision over ALL recovered `new_formula_error` representatives (same
shared verdict rule, gold used only to score): write-stage 99.6% (500/502),
submit-stage 100% (124/124), combined 99.7% (624/626). The documented "100% on
72" was the submit-only subset.

### 2b. Phase-4 A/B (the only clean causal comparison)

`kimi-k2.7-commit-gate-off-low-1` vs `-on-low-1` (K2.7 low, call cap 12,
submit-only gate, flat-12 cap):

- 10_02: gate fired (30 live findings, 12 shown, all `#REF!` on
  `FY2024A (Earnings)`). Trajectory: submit -> blocked report -> read (BLOCKED,
  read budget exhausted) -> `clear_range C6:AF6` repair -> resubmit. The model
  removed exactly the 12 shown cells (30 -> 18 live; this probe verified 18 on
  the final output with the live-equivalent path) and 0 unshown cells.
  Official modification unchanged (0.2340 both arms). The "repair" deleted the
  error cells rather than fixing formulas.
- 07_01: no findings live (offline replay claims 94 `broken_check_cell`;
  live found 0). ON mod 0.0581 vs OFF mod 0.0000 (unrelated drift, not gate
  contact).
- 06_01: bypassed — 12/12 calls, autosubmitted, submit tool never invoked.
- 05_03: ON produced no workbook (gate correctly passes); OFF produced one
  (mod 0.1273).

### 2c. 297 single-arm repair telemetry (GLM 5.3 Flash, cap 24, write+submit gate)

- 60/100 tasks contacted at write stage; 25/100 at submit stage (all 25 also
  contacted at write).
- 35 tasks: write delivery only, then submitted with NO submit-stage report,
  i.e. zero findings at submit. Includes large resolutions (03_01: 210
  `new_formula_error` at write -> 0 at submit; the 06_01..06_10 family:
  ~44-60 each -> 0; 09_02/04/05/09/10: 26-32 each -> 0).
- 7 tasks with both deliveries resolved ALL write-stage `new_formula_error` by
  submit (catalog 01_05: 264 -> 0; 297 04_04: 85 -> 0; 09_08: 26 -> 0; 07_02:
  6 -> 0; 09_06: 3 -> 0; 02_07: 2 -> 0; strict 02_09: 30 -> 0).
- Post-submit-report behavior (25 tasks): 11 immediately resubmitted unchanged,
  12 wrote again (48% repair-write rate).
- Official Debugging exact stayed 0/100. Without per-task controls, the
  write->submit reductions are repair-correlated, NOT causal: the agent was
  mid-task and would have kept editing anyway.
- Counter-case 01_09: write report showed 5 `new_formula_error`; the agent
  then ran 18 more fill/compare steps, never submitted (autosubmitted), and the
  final holds 118 (verified live-equivalent) at mod 0.8713 / reg 1.0.
  Post-report error introduction is real; feedback is not sufficient.

### 2d. What has never run

No clean same-scaffold gate-on-vs-off A/B of the write-stage gate, or of
`new_formula_error` feedback on official capability, has ever run. Phase 4 is
the only clean comparison (submit-only gate, 4 tasks, K2.7). The catalog
control/ours contrast is confounded (bash+openpyxl vs calc tools). The proposed
experiment would be the first causal test.

Per-task records (131 tasks x 10 runs, deliveries, trajectories, scores):
[historical_live_evidence.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/historical_live_evidence.json)
(final-live-error merge pending LO batch).
Offline detector evidence (frozen Phase-2 figures):
[historical_offline_evidence.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/historical_offline_evidence.json).

## 3-5. Census, firing prevalence, repair opportunity (PARTS 3-5)

Best available ordinary-agent Debugging population: 48 archived control slots,
45 usable workbooks (38 SWE-bash-era GLM controls + 2 spark sidecar-C0 + 5
lx_helpers-era H0/C0), all measured live-equivalent (LO recalc-output):

- N usable: 45. N with >=1: 14 (31%). N>=3: 14. N>=5: 12. N>=10: 12.
- Distribution: p25 0, median 0, p75 30, p90 30, max 147.
- Kinds: Err:522 x486 (circular reference), #DIV/0! x4. No #VALUE!/#REF! fired
  live on ordinary outputs (cf. offline cache replay, which hallucinates both
  directions).
- Attribution: changed-formula 14 (3%), unchanged/cascade 476 (97%). Ordinary
  new errors are overwhelmingly cascade circularities the agent did not
  directly author, not broken formulas it wrote.
- Firing tasks: 02_01 (30 x2), 02_06 (30 x4), 02_09 (30 x2), 02_05 (30 x2, Tier
  A), 07_03 (36), 10_05 (3), 04_09 (4 then 0), 10_10 (147 spark; GLM 0 x2).
- Repair headroom: all 9 would-contact run-style trajectories have >=8 calls
  remaining even measuring from the LAST write (min 23); all 5 lx_helpers-era
  outputs have >=16. Every contacted trajectory submitted. Ordinary agents
  write late (first write typically within 5 steps of submit) under caps 40-60
  they rarely exhaust, so a first-write report lands with ample budget.

The lx_helpers-era H0 Debugging output rate itself is low (5 outputs across 6
studies; thin checkpoint 0/16, representative H0 1/10), dominated by
NO_SUBMIT / PROVIDER_CENSORED / TRUNCATED_CALL_LIMIT - not by lack of firing.

Full per-output records:
[debugging_candidate_census.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/debugging_candidate_census.json).
Distributions:
[firing_distribution.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/firing_distribution.json).
Headroom:
[repair_opportunity.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/repair_opportunity.json).
Measurement warning verified both directions (98 comparable finals, 60 agree;
e.g. 09_09 offline 458 vs live 0; 02_01 offline 0 vs live 30; 10_02 counts
reproduce exactly with a #REF!-to-#NAME? kind-label shift across LO
versions):
[live_offline_parity.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/live_offline_parity.json).

## 6. Contamination audit (PART 6)

Tiers by mechanism-development role and distinct-live-run reuse (100 tasks):

- Tier A (EXCLUDE from primary AND confirmation; 10 tasks): 05_03, 06_01, 07_01,
  10_02 (commit-gate Phase-4 development), 01_02, 01_05, 02_05, 09_09
  (pattern-catalog cases + catalog-gate arms), 04_06, 08_03 (formula-anomalies
  observation development). Valuable ONLY as positive/negative controls and
  implementation checks.
- Tier B (CAUTION; 19 tasks): >=6 distinct live runs, no mechanism-development
  role. Usable in primary only if needed for N, with pre-registered
  leave-one-task-out + tier sensitivity analysis.
- Tier C (USABLE; 71 tasks): <6 distinct live runs, no mechanism role. Prior
  scoring (297/Sol/census) is measurement, not contamination.

Required marks: 10_02, 07_01, 06_01, 05_03 are all Tier A (development-contaminated).

Full per-task runs and flags:
[contamination_audit.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/contamination_audit.json).

## 7-8. Selection rule and N (PARTS 7-8)

Frozen gold-blind control-side rule:
[candidate_selection_rule.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/candidate_selection_rule.json).
Debugging + valid ordinary-agent control workbook + max live-equivalent NFE
>= 3 over ordinary outputs + >=8 calls headroom + not Tier A + not reserved.
Threshold >=3 separates the observed bimodal control distribution (31 zeros,
14 at >=3, nothing at 1-2) and is set from controls only. Tier B allowed with
declared sensitivity analysis. Never selects on treatment improvement, gold
identity, score deltas, or prior feedback success.

Yield: 7 enriched {02_01, 02_06, 02_09, 04_09, 07_03, 10_05, 10_10} + 1 Tier-C
clean negative control {01_06} = N=8 (16 slots). Two error kinds (Err:522 +
#DIV/0!), five families, no Tier A. N=10/12 cannot be filled honestly (no 8th
enriched task exists under the rule). Contact expectation 6-7/7 enriched at
historical refire rates (02_06 4/4, 02_01 2/2, 02_09 2/2; risk points 04_09
1/2, 10_05 small-n, 10_10 model-mismatched).

Recommended N=8:
[proposed_discovery_population.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/proposed_discovery_population.json).
N=8 is enough for mechanism discovery because contact is near-certain on most
enriched tasks (historical refire is 100% on the three 02_xx tasks across 8
combined outputs), two kinds and five families prevent monoculture, LOTO gates
concentration, and the gates require mechanical repair alongside any score
move - a score-only fluctuation cannot pass. It is not powered for small
effects and pretends nothing else.

## 9. Proposed live causal design (PART 9, NOT executed)

Paired task-level A/B, same frozen population both arms, pairing by task:

- CONTROL: ordinary Python/openpyxl coding-agent scaffold (bash + view_xlsx +
  submit), same model/settings (recommend GLM 5.3 Flash t=0, matching the
  ordinary census), same call cap (50 recommended), same deadline/guards, same
  LibreOffice scoring, NO model-visible error feedback. The harness may compute
  the delta invisibly for measurement but must not expose it.
- TREATMENT: identical, plus at most ONE model-visible episode: after a
  successful save, if the live recalculated input->current-output
  `new_formula_error` delta is nonempty FOR THE FIRST TIME, expose one factual,
  concise, non-blocking report (complete total count, per-sheet counts, error
  kind, sampled addresses <=8/sheet and <=80 overall, current error value).
  Never: gold value/formula, suggested formula, repair instruction, semantic
  interpretation, priority. Same total call cap (no extra budget); the report
  rides on the save observation and consumes zero model calls. No submit-stage
  report in either arm (keeps the contact mode singular and unconfounded).

Full spec:
[proposed_ab_design.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/proposed_ab_design.json).

## 10. Why first-nonempty-write (PART 10)

297 evidence (100 Debugging tasks, write+submit gate): 26 tasks never invoked
submit, 27 autosubmitted, 10 produced no workbook. Write-stage fired on 60
tasks vs submit-stage on 25 (all 25 also write-contacted). Of 71
submitted-with-output trajectories, write delivery reached 53 (75%) vs submit
delivery 25 (35%). Phase 4 (submit-only) fired on 1/4 for exactly these
reasons (06_01 call-cap autosubmit, 05_03 no workbook). A submit-only design
misses the trajectories that fail by never getting there. First-nonempty-write
contacts the agent while repair budget remains, and fires nothing on clean
saves (no perturbation without cause). Mechanically implementable today: the
frozen `_with_write_report` path does exactly this (informational, zero-finding
saves silent, exceptions swallowed).

## 11. Endpoints (PART 11)

- Primary: paired official modification-accuracy delta (treatment minus
  control, per task). The mechanism is supposed to repair incorrect
  modifications.
- Mandatory guard: paired regression-accuracy delta. Feedback is not useful if
  errors are cleared by damaging unrelated cells (the 10_02 `clear_range`
  pattern).
- Mechanism: contact rate, finding count at first report, fraction of shown
  findings absent at final, absolute live new-error reduction, agent response
  rate, repair-write rate after report, new errors introduced after report,
  calls consumed after report, submission rate.
- Secondary: exact success (never the sole gate on a small Debugging
  population), total calls, wall time, cost.

Full spec:
[proposed_endpoints.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/proposed_endpoints.json).

## 12. Discovery gates (PART 12, preregistered from control distributions only)

Control basis: ordinary-agent scored outputs (n=38): mod mean 0.713 / median
0.921 / p25 0.458; reg mean 0.9826 / median 1.0. High control median means
absolute gates must be modest; headroom lives in low-mod tasks.

- PROMISING (all required): contact >=6/8 (N=8) or >=7/10 (N=10); mean paired
  mod delta >= +0.05; reg safety (mean >= -0.01 AND no task <= -0.02); LOTO
  minimum stays >0; >=50% of contacted trajectories reduce live NFE at final
  vs report. Action: freeze byte-identical, run ONE fresh confirmation.
- NO_CAPABILITY_EFFECT: adequate contact + mean mod delta in (-0.02, +0.05) +
  mechanism flat/absent. Action: close the branch permanently (clean negative).
- HARMFUL: mean reg delta <= -0.02 or any task <= -0.05 with adequate contact.
  Action: close permanently, report the harm mechanism.
- INCONCLUSIVE: contact below gate (treatment not delivered; not a negative),
  or any gate read missing a required element.

No power analysis is pretended; these are discovery thresholds. Full spec:
[proposed_discovery_gates.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/proposed_discovery_gates.json).

## 13. Confirmation reservation (PART 13)

A separate fresh Debugging confirmation population is reserved (not run, no
treatment outcomes computed):
[reserved_confirmation_population.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/reserved_confirmation_population.json).
Funnel: enriched 8-10-task paired discovery -> negative closes the branch;
positive -> fresh confirmation once -> replicate earns freeze+close, failure
closes. No architecture discovery beyond this mechanism is reopened.

## Required answers

1. Is `new_formula_error` still mechanically reproducible? YES - frozen pure
   function + live UNO path verified this session (10_02 counts reproduce
   exactly; 297 submit counts reproduce on finals).
2. Is the live/UNO path available independently of the old harness? YES -
   `UnoCalcBackend` + `commit_checks` are product code; this probe drove them
   directly (pyuno + isolated LO 26.2 listener, health ok).
3. What differs between offline and live measurement? Reader (openpyxl caches
   vs UNO recalculated), normalization (offline needs DataTable sentinels; live
   never sees them), and both failure directions (missing input caches ->
   overcount; stale/empty output caches -> blind). Kind labels can shift
   across LO versions (#REF! -> #NAME? on 10_02).
4. How many usable ordinary-agent Debugging outputs exist? 45 (48 slots).
5. How many produce any live-equivalent new formula errors? 14 (31%).
6. Finding-count distribution? p25 0, median 0, p75 30, p90 30, max 147.
7. What error kinds dominate? Err:522 (circular, 486/490); #DIV/0! x4.
8. Changed vs unchanged/cascade? 3% changed (14), 97% unchanged/cascade (476).
9. How many tasks would contact treatment early enough? All 9 would-contact
   run-style trajectories + 4/5 lx_helpers outputs (the 5th saved on its last
   call without submitting).
10. What call headroom exists? >=8 on every would-contact trajectory even from
    the last write (min 23 run-style, 16 lx_helpers).
11. Which historical tasks are development-contaminated? Tier A (10): 05_03,
    06_01, 07_01, 10_02, 01_02, 01_05, 02_05, 09_09, 04_06, 08_03.
12. What exactly happened on 10_02? Phase-4 ON: 30 live #REF!, 12 shown, model
    cleared exactly the 12 shown (clear_range, blind - reads blocked), 0
    unshown touched; mod unchanged 0.2340. Verified: final 18 live.
13. What happened on 07_01, 06_01, 05_03? 07_01: silent live (0; offline
    claimed 94), drift mod +0.0581. 06_01: cap-bypass (12/12, autosubmit, no
    gate contact). 05_03: ON no workbook (gate passes); OFF workbook mod
    0.1273 with 21 live NFE.
14. What did submit-only miss? 26/100 never-submit, 27 autosubmit, 10
    no-workbook in 297; write-stage reached 60 tasks vs submit-stage 25.
15. Is first-nonempty-write reporting implementable? YES - frozen
    `_with_write_report` does exactly this (informational, silent on clean
    saves, fail-open).
16. Can treatment receive feedback without extra budget? YES - report rides on
    the save observation (zero model calls); same total cap both arms.
17. What gold-blind selection rule? Debugging + valid ordinary control
    workbook + max ordinary live-NFE >= 3 + >=8 headroom + not Tier A + not
    reserved; rank by (maxNFE, n-firing, id); +1 Tier-C clean control.
18. Which 8-12 fresh tasks? 7 enriched: 02_01, 02_06, 02_09, 04_09, 07_03,
    10_05, 10_10; + clean 01_06. No 8th enriched task exists.
19. What N? 8 paired tasks (16 slots).
20. Why enough? Near-certain contact on most enriched tasks (100% refire on
    02_xx x8 outputs), 2 kinds, 5 families, LOTO + mechanical-repair gates; not
    powered, discovery only.
21. Which confirmation reserve? 10 Tier-C: 03_01, 06_08, 06_06, 06_03, 06_10,
    06_07, 09_05, 02_08, 02_10, 02_04 (ranked by 297-write-NFE; ordinary firing
    unknown - contact risk declared).
22. Primary endpoint? Paired official modification-accuracy delta.
23. Regression guard? Paired reg delta: mean >= -0.01 AND no task <= -0.02.
24. Mechanism telemetry? Contact rate, report count, shown-absent fraction,
    absolute reduction, response/repair-write rates, post-report new errors,
    post-report calls, submission rate.
25. Discovery gates? PROMISING (>=6/7 enriched contact + clean unfired + mod
    >= +0.05 + reg safe + LOTO>0 + >=50% mechanical repair); NO_EFFECT;
    HARMFUL; INCONCLUSIVE - see proposed_discovery_gates.json.
26. Clean negative? Adequate contact + mod in (-0.02,+0.05) + mechanism flat.
27. What justifies confirmation? PROMISING on all five gate elements.
28. What closes the branch? NO_EFFECT or HARMFUL with adequate contact;
    failed confirmation; INCONCLUSIVE only after a second enriched attempt
    fails for cause.
29. Did this probe alter frozen mechanisms? NO - read-only throughout; no
    product/RC/harness file modified (all probe code in /tmp; deliverables are
    new JSON/MD only).
30. Single next action? Build the one-episode treatment harness (no product
    change), verify on Tier-A checks, launch the frozen N=8 A/B once - see
    [next_action.json](/home/kerem/Desktop/Personal%20Projects/librecalc-mcp/formula_error_feedback_probe/next_action.json).

## Final synthesis

IMPLEMENTATION STATUS: frozen and intact in the old-harness bundle + product
domain logic; absent from the product RC (correctly - not ported).

LIVE VS OFFLINE MEASUREMENT: offline cache replay fails both directions
(overcounts without input caches, blind without output caches); 10_02 and all
297 submit counts reproduce live-equivalent exactly (kind labels may shift).

HISTORICAL CLOSED-LOOP EVIDENCE: detector SUPPORTED (99.7% live precision,
626 reps); model-reacts DEMONSTRATED broadly (10_02 12/12; seven 297 tasks
resolving 100% of write-stage NFE by submit; 48% post-submit repair-write
rate); official capability IMPROVEMENT not established (only clean A/B is
Phase 4: mod unchanged; everything else single-arm or confounded).

DEBUGGING CONTACT PREVALENCE: 31% of ordinary-agent outputs fire (14/45).

ERROR-TYPE DISTRIBUTION: Err:522 circularities 99%, nearly all
unchanged-formula cascade.

REPAIR HEADROOM: ample (>=8 calls on every would-contact trajectory).

CONTAMINATION AUDIT: Tier A 10 / B 19 / C 71; Phase-4 four all Tier A.

FRESH DISCOVERY CANDIDATES: 7 enriched + 1 clean control (above).

RECOMMENDED N: 8 paired (16 slots); 10/12 unfillable honestly.

CONTROL: ordinary scaffold, GLM t=0, cap 50, LO scoring, invisible measurement
only.

TREATMENT: control + ONE factual non-blocking first-nonempty-write report,
same total budget.

FEEDBACK TIMING: first save with nonempty live recalculated delta.

FEEDBACK CONTENT: complete counts, per-sheet counts, kinds, sampled addresses,
current values; never gold/formulas/instructions/semantics.

PRIMARY ENDPOINT: paired official modification delta.

REGRESSION GUARD: paired reg delta, mean >= -0.01 and no task <= -0.02.

MECHANISM ENDPOINTS: contact/reduction/response/repair telemetry (above).

PROPOSED DISCOVERY GATES: five-element PROMISING / NO_EFFECT / HARMFUL /
INCONCLUSIVE (above).

CONFIRMATION RESERVATION: 10 fresh Tier-C tasks, frozen, not run.

CLOSURE RULE: negative or harmful with adequate contact closes permanently;
PROMISING earns exactly one frozen confirmation; single-task or Tier-B-only
effects do not.

WHETHER LIVE A/B IS JUSTIFIED: YES - treatment contact and repair headroom
are mechanically established (31% prevalence enriched to near-certain contact
on 7 tasks; headroom >=8 everywhere; invisible measurement proven). The
detector is not the experiment; the repair loop is untested causally, and this
is the minimum honest test of it.

SINGLE NEXT ACTION: build the one-episode treatment harness (no product
change), verify on Tier-A checks, launch the frozen N=8 A/B once.
