# Operator state

Task: complete user-requested Phase12R zero-model historical recalc replay. No new
agent trajectories, product edits, verifier revival, or new derived diagnostics.
Independent stronger review gates only are allowed model use.

Frozen protocol SHA256: 81c95dacb181e4cc7316d4ce84490590ed356aed2f549d61dfa5b7273a4fee49.
Population: 1222 eligible primary rows = P1 183 archived ordinary controls,
P2 191 ordinary research (including 23 Phase12 submissions), P3 848 older harness
context. All eligible rows must finish; P3 never pooled with P1/P2. Some P2/P3
run-local candidates lack verified submission provenance; normalized-only.

Gate A complete: STRONG_REVIEW_PREREG.md, selected gpt-6-astra reviewer task
/root/strong_prereg_review. Initial same-family review retained separately.
Seven core tests and four execution-parity tests pass. Pilot 6 identities verified.
Phase12 D — DEMOTE and nuisance/mechanism findings carried forward unchanged.

Frozen replay.py and uno_recalc.py must not be edited. Full four-worker run caused
two host crashes. Both interrupted attempts, logs and recovered rows are preserved.
EXECUTION_RECOVERY.md documents execution-only resource correction: bounded_resume.py
uses one fresh process per workbook, 7GiB address-space cap, 900s timeout, unchanged
official process_single_item and comparison return values; GC after return. Exact
scoring identity may be reused. An additional wrapper captures existing official
counts to avoid evaluating twice; test confirms scores/counts/modes unchanged.
Frozen eligibility/treatment/thresholds/classifier/evaluator remain intact.

Current active command: LC_ALL=C.UTF-8 TZ=UTC .venv/bin/python phase12r/bounded_resume.py
Progress: BASELINE_CORRECTION_LEDGER.jsonl (count only while running),
REPLAY_PROGRESS.jsonl, REPLAY_STDERR.log. Do not interpret historical outcomes until
complete. Need keep commentary updates during prolonged work. A 7GiB process bound
protects UI; failures explicit unscorable, never silent score-zero success.

After primary completion:
1. Verify all 1222 IDs/ledger agreement, run analyze.py, freeze ledgers (LEDGER_FREEZE).
2. Inspect summary then invoke stronger reviewer Gate B ONLY if frozen surprise rules
trigger. Qualitative architecture contradiction also allowed. Persist separate review.
3. Supplement requested Phase12 all-final-files replication: five retained nonsubmitted
candidates in PHASE12_REPLICATION_MANIFEST.json, separately frozen, never prevalence.
Use same bounded worker by --row-id, commit supplementary ledgers separately.
4. Audit claims and case-level interpretations. Existing replay output's interpretation
fields are preliminary current-pair hints: unverified history/drift => UNKNOWN. Do not
infer a prior semantic failure just from a report reference. Preserve RAW main ledger
and add clearly labeled historical-audit qualifications to authoritative correction
ledger if needed. No historic report/score/JSON overwritten. Required claim inventory
already created with source paths. Reviewer C after primary analysis if baseline/scaffold
or historical interpretations materially change. No reviewer may rewrite primary analysis.
5. At most one bounded causal follow-up after main, only to resolve named contradiction;
no new trajectories/model work. Supplementary Phase12 requested replication is not a
contradiction probe. No routine reviewer debugging.
6. Create HISTORICAL_CLAIM_IMPACT.md, final RECALC_FAIR_BASELINE_SPEC decision scope,
STRONG_REVIEW_POST.md and root PHASE12R_RECALC_FAIR_REPLAY_REPORT.md with all user-required
31 final headings in exact sequence, ending NEXT STEP. Recalc-policy/historical/scaffold
verdicts distinct. Formula/error-cache score recovery does not prove numerical correctness.
7. Verify protected 2505 original/history/runtime files via PROTECTED_HISTORY_HASHES.json;
hash final deliverables, verify tests/manifests/complete ledgers. Preserve all Phase12 files.

Important limitations/frozen choices: unsupported volatile/macros/UDF/external connections
remain denominator unresolved. Iteration-enabled archives are attempted but excluded from
strong attribution. CACHE_ONLY requires semantic fingerprint equality and cache-only typed
transplant witness with complete assessed-cell equality + same official outcomes. The
current scorer uses error-triggered formula fallback; disclose this using cache census.
Historical scorer source identities unavailable; returned-score reproduction kept separate.
P1 baseline threshold: broad >=10% affected tasks overall + >=10% in two families + >=3
affected tasks each; narrow >=10% in one family + >=3 affected tasks. P2 never silently
substitutes for P1. All continuous deltas, per-category/task/run results reported. Unresolved
bounds prevent unsupported cases being misread as unchanged.

No historical conclusions have yet been drawn from partial replay. All new files are
under phase12r until root final report is written. Existing worktree is extensively dirty
from prior user work; do not reset/clean/stage unrelated changes.

Execution cache now also accepts exactly identical scored package-part bytes excluding validated nonscored docProps/core.xml and docProps/app.xml; source/V1 hashes stay distinct, reuse provenance explicit. Tested against unchanged official scorer. No failed/unscorable score is reused. Redundant score-stage copies are removed only after scoring; V0/V1/witness/originals remain. Disk initially ~7GiB free. Existing scoring computations were seeded with seed_equivalent_scores.py (hash/package only, no outcome interpretation).

Reference-only parse cache now clones unchanged input/golden openpyxl objects by source hash+loading args+Python/openpyxl versions. Candidates always parse fresh. Official scorer and comparator consume equivalent fresh cloned objects; three parity tests (including complex FM) pass. Cache files are compressed, no original/reference workbook modified. Record helper hash and cache events. Strong reviewers must be shown execution supplement as-is to assess parity/equivalence limits.

Candidate parse clones are local to each workbook job, keyed by exact full bytes + load mode/args + Python/openpyxl; every distinct file/mode first goes through native parser. Parsed-object temporary caches are discarded at completion. Four execution parity tests pass, including native-versus-cloned entire semantic snapshot and official scores on complex FM.

IMPORTANT CONFIG DEVIATION discovered 2026-10-01: frozen helper MacroExecutionMode4
is ALWAYS_EXECUTE_NO_WARN, NOT NEVER_EXECUTE0. Main treatment untouched, environment
original preserved. MACRO_CONFIG_DEVIATION.md and package audit are additive.
Conventional VBA excluded by original code; all eligible package content types and
rels audited. Reserve at most one post-primary deterministic follow-up for mode0
comparison, sample preregistered before running. Reviewers/report must see this.

Post-primary continuation worker: complete_primary_stages.py --replay-pid466677
(session20191). Waits without interfering with replay, then analyze/freeze,
render_tables, requested Phase12 supplemental replication, and additive history
qualification. POST_REPLAY_STAGE_STATE.json records checkpoints. No model calls,
no follow-up until explicit triggered independent review. Interpretation gates
remain manual. Current main session8989 was launched earlier; PID466677.
FOLLOWUP_MACRO_MODE_SPEC.md is hashed; followup_macro_mode.py implementation ready
but NOT RUN. It will compare all successful ordinary cases (<=379 including
nonsubmitted supplement) with correct macro mode0, not score-selected subset.
POPULATION_PROVENANCE_AUDIT.json confirms183 P1controls; P3=792 confirmed structured
plus56 old noncontrol/unknown context, never headline pooled.

2026-10-01 SERVER DAEMON RECOVERY: initial one-worker scheduler was interrupted
at605 commits. Orphan acd68259c91e290e finished successfully, recovered once =>606.
Attempt3 preserves prior7414.86s active-wall lower bound. New scheduler PID582901
and continuation PID582909 are detached with setsid/stdin closed/stdout files:
DETACHED_REPLAY_STDOUT.log and DETACHED_POST_STAGES_STDOUT.log. This prevents an
API-server session interruption from killing their process groups. No old driver
or competing worker exists. scheduler.lock prevents duplicate parent schedulers.

Scorer-only answer-position parsed-object optimization now active. EVAL source
unchanged/frozen; all existing accessed cell objects, workbook metadata and names
retained; only unused in-memory cells released. Full workbook audits remain full.
Five scoped native-return parity tests plus four wrapper tests pass. First wrapper
rerun failed only a now-obsolete full-reference-hit expectation, not any score/count;
updated assertion accepts actual reuse from either equivalent clone cache. See
scored_object_cache.py, SCORED_OBJECT_PARITY_TEST.log, EXECUTION_PARITY_AFTER_SCOPING.log,
EXECUTION_RECOVERY.md. No outcome interpretation from partial results. Frozen
protocol/helper/population/test_replay/evaluator still byte-identical.

2026-10-01 FULL PRIMARY REPLAY COMPLETE:1222 rows; all post stages completed.
First-pass SUMMARY/RAW ledger frozen. P1=0 strong recoveries183 retained archives,
P2=46 strong (9 archived/numeric-compatible),17 harms. GateB surprise review done,
STRONG_REVIEW_SURPRISE_RAW.md/disposition; expected-blank cell inspection explains
two harms without reference intervention. P1 retained archive pipeline explicitly
refreshes before official scoring. Auxiliary nested DimensionHolder pickle bug
identified in old-context scoring; lossless reducer nested-graph tests and frozen
Python native-score/count parity passed. All technical decoder failures selected
before scoring recovery, separate immutable-normalized artifacts only. Detached
PID in NORMALIZATION_FOLLOWUP_PID runs scoring_execution_recovery then the SOLE
frozen macro-mode0/config contrast. Original mode4 documented as ALWAYS_EXECUTE_NO_WARN;
package audit no conventional macro declarations on1219 readable files. No history,
product runtime, frozen replay or Phase12 files changed. Final report/reviewC pending.
Resume these detached processes rather than duplicate execution.

Scoring recovery execution optimization: after28 completed full replay rows,
paused scheduler between jobs; preserved initial script/manifest and completed
rows. Remaining selected rows rescore identical existing V0/V1 and reuse frozen
full inspections; newly assessable gains escalate to frozen r.replay+witness.
Actual first-row native-full versus optimized score/count/classifier parity passed.
Amendment identities in scoring_recovery/IMPLEMENTATION_AMENDMENT.json. Scheduler
resumed; no selected rows or thresholds changed. Follow-up exact-part equality
shortcut prepared BEFORE its manifest freeze; full snapshot fallback unchanged.
After both detached stages finish: finalize_execution_recovery.py, then
write_primary_analysis.py (requires full normalized/followup summaries), GateC,
write_final_report.py, final verifier. Do not start another causal probe.

2026-10-01 PHASE12R COMPLETE: main1222 rows;403 same-byte technical score
recoveries complete;P1/P2 unchanged. Normalized P3=657pairs/654no-effect/2harms/
1ambiguous/191unresolved/0strong. Mode0 follow-up310rows/306unique sources:
309successful confirmations/1native-golden-prefix-unscorable;all extracted formula,
cache/captured semantic comparisons equal. Sole probe consumed. GateC reviewed
frozen completed analysis;final evaluator answer narrowed to YES—RECOMMENDED BUT
NARROW, compatibility/target-dependent, with before-review snapshots preserved.
C=no demonstrated material alteration of retained ordinary baseline;selective
score qualifications, not refuted semantic diagnoses;minimum eval-only scaffold
policy, not proven optimal placement. Frozen PRIMARY_ANALYSIS remains untouched.
Final report31sections written. All2505 protected files,source/derived hashes,
freezes,ledgers,cache witnesses and completed normalization/follow-up validated.
18 mechanical/execution-parity tests passed. No new trajectories/runtime changes.
Read-only P1 harm cell inspection illustrates near-zero residual/relative-tolerance
mismatch without changing official scorer/classification or making another probe.
