# Phase 12R preregistered causal replay specification

Carry forward D — DEMOTE. The Phase-12 evidence block was behaviorally potent,
but its outcome benefit was largely reproduced by recalculating CONTROL outputs
without changing formulas. Findings were mechanically true but actionability-poor.
No verifier promotion, product changes, agent trajectories, repair, or new derived
diagnostics. Independent reviews are the only model calls.

## Population and exclusions
Inventory all retained official-scored openrouter runs and ordinary research
run_record directories in this repository. Eligibility requires nonvisual task
identity in benchmark dataset, original official numeric scores, attributable
submitted output bytes, matching benchmark input and golden, and reproducible
current official evaluator. Retain missing, censored, ambiguous shared outputs,
unknown harness and unjoinable scores as explicit exclusions. Never select on score,
formula presence, category, or recalc outcome. Run-local output takes precedence
over shared work trees; never attribute shared output to repeated runs.

P1: historical ordinary control runs whose ledger confirms control arm and plain
bash/view_xlsx/submit tools (no calc semantic tools). Prefer exact archived
submission/outputs bytes actually scored. If absent use run-local output and mark
historical byte linkage as unverified. P2: ordinary Python research run_record
submissions (all arms, separately broken down by experiment, pilot and discovery).
P3: official-scored structured tool harness runs; historical context only. Unknown
tool provenance excluded, not guessed from run names. P3 never pooled with P1/P2.
Phase-12 discovery and pilots never count as independent primary prevalence.
Identical archived copies of the same run/task are aliases, not repeated runs;
separate runs with identical workbook bytes remain runs and are clustered by task.
Also retain agent-output hash when submission bytes differ; do not silently join
an unrefreshed agent output to a score of its refreshed submission.

## Intervention and evaluator boundary
V0 is an exact copy of original submitted bytes. V1 is independently copied V0,
loaded in an isolated headless LibreOffice profile with macros disabled, links
not updated, calculation forced via UNO calculateAll(), then saved as XLSX.
Every input and derived artifact is SHA256 hashed. Original history is immutable.
Locale C.UTF-8, timezone UTC, controlled fresh profile per workbook; 180s timeout.
Current official evaluation.py is imported without modification and its exact
process_single_item used on staged copies; record hash and all benchmark data
hashes. No metadata repair or tolerant evaluator. Historical evaluator identity
is not assumed: historical score and current V0 score separate. V2 normalization
is the current V0/V1 scoring pair when historical version unavailable. Drift
and missing byte linkage block historical cache-only attribution, not current
normalized results. No refresh is run inside V0 scoring.

## Identity, cache and package rules
Extract formulas by sheet name/cell independently of ZIP order, expand shared
formulas through openpyxl; preserve array formula metadata. Byte identical means
identical extracted text and formula attributes per cell (not ZIP bytes).
Semantic identity permits only shared formula expansion and function-name case
outside quoted literals, no removal of dollar signs or range rewriting. All other
rewrites are FORMULAS_CHANGED_BY_LIBREOFFICE; read failures UNDETERMINED.
Record formula/cached value census, missing/typed/error caches, numeric/string
cache transitions; a changed present cache is stale relative to this LO execution,
not evidence of semantic correctness. Package diffs enumerate all added/removed/
changed parts with hashes and part types (worksheets/caches, calcChain, calcPr,
styles, properties, relationships and other metadata).

## Attribution safeguard
CACHE_ONLY_SCORE_RECOVERY requires material improvement, semantic formula identity,
valid V0/V1, cache transition on scorer-observed cells consistent with improvement,
no structural/formula/literal/defined-name change plausibly explaining gains, and
historical score reproduction if claiming a historical failure correction.
For strong attribution create a separately labeled mechanical cache sufficiency
witness: copy only V1 cached formula values into V0 XML at identical formula cells,
leave V0 formula text and every other package part intact, score with same official
function, and require witness scores equal V1 across all three outcomes. This is
an attribution check, never a repaired submission or replacement V1. Restrict it
to formula-identical pairs. Record witness hash and score. Rewrites, ambiguous
semantics, unmatched witness or evaluator drift => RECALC_ASSOCIATED_BUT_NOT_CACHE_PROVEN.
Regression takes priority if exact decreases or modification/regression decreases
materially even alongside gains; report mixed signs explicitly. No material change
=> RECALC_NO_MATERIAL_EFFECT; evaluator/recalc errors => explicit UNSCORABLE.

## Materiality and analysis
Exact 0→1 or 1→0 is material. Modification or regression change >=0.01 absolute
(on [0,1]) is material; report every continuous delta including smaller ones.
Primary endpoint: eligible P1 submissions with proven cache-only material gain /
all eligible P1 submissions, including unscorable in denominator. Also conditional
scorable denominator and task-level any affected / eligible tasks. P2 separately,
with and without Phase12 and pilots. No pooled independent-run confidence claims.
Report all exact transitions, mod/reg gains/losses, ties, distributions, category
Template/Financial Model/Debugging, per-experiment and task clustering. A broad
material baseline effect requires >=10% proven recovery across eligible ordinary
tasks in at least two families; narrow material effect >=10% within one family
and >=3 distinct tasks; lower prevalence is cache effect without material broad
baseline alteration. Report rates alongside this decision, not solely the label.

## Failure policy and environment
Crash/timeout/invalid workbook => RECALC_FAILED; password/encryption, macros/UDF,
external links or volatile formulas => RECALC_UNSUPPORTED in main deterministic
arm, recorded explicitly with no unrecalculated success fallback. Detect common
volatile functions NOW/TODAY/RAND/RANDBETWEEN/OFFSET/INDIRECT/CELL/INFO; conservative
unsupported scope disclosed. Unsupported features detected by LO or formula
changes are ambiguous, never cache-only. Record LO/OS/Python/openpyxl, commands,
profiles, calculation settings, elapsed recalc/scoring/total time, failure rate.

## Pilot, freeze and stopping
Pilot five deterministic selected cases, plus one supported complex-FM plumbing case if the first FM is unsupported: known Phase12 cache-sensitive,
known unaffected, formula-error, no-formula and complex Financial Model. If a
class is unavailable report it; never manufacture a historical sample. Pilot
validates mechanics only, no threshold tuning. Review Gate A before final hash;
freeze protocol and population manifest before full replay. All eligible rows
replayed, resume only against same hashes; stop only at exhaustion or genuine
reproducibility failure. No outcome-based exclusions or favorable stopping.

## Review and claims
Gate B triggers: >20% exact changes in a stratum; >=20pp category exact shift;
>=5% material regressions; >=20% formula rewrites; or major contradiction to
Phase12/architecture interpretation. Freeze ledgers first; review as-is; any probe
new labeled follow-up, never retroactive protocol change. At most one bounded
zero-model contradiction probe after replay. Gate C after primary analysis if
baseline, scaffold, or historical interpretation changes materially. Reviews may
attack design/interpretation only, never generate scored workbooks.
After replay audit report claims linked to recovered runs. UNAFFECTED requires
scope evidence, not merely absence of a joined run. Scores move without architectural
change => NUMERICALLY CHANGED, INTERPRETATION SAME; specific failure location
changes => BOUNDARY MOVED; dirty score contrast => REQUIRES REBASELINE; missing
coverage => UNKNOWN. Preserve reports, attach only a new correction ledger.

## Gate-A corrections accepted before freeze (binding)
Byte-unverified run-local research candidates remain in P2 normalized replay only;
they are never historical-primary or historically proven correction numerators.
P1 requires archived submitted bytes. Historical numeric reproduction tolerance
is exactly equal returned accuracy/modification/regression scores, not approximate.
P3 also separates byte-unverified normalized candidates. Final inventory hash fixes
all rows before outcomes. Primary baseline rule uses P1 only: broad requires at
least 10% affected P1 tasks overall AND >=10% within each of two families AND >=3
distinct proven affected tasks in each family. Narrow requires >=10% within one
family AND >=3 affected distinct tasks. P2 supports validation and policy but
cannot silently replace the P1 headline. Mixed material gains/losses are harms,
not recovery numerator; all signed deltas remain visible.

Operational semantics equality uses interpreted typed nonformula values, sheet
names/order/visibility, merged ranges, tables, global and sheet-local defined
names, date epoch, full precision and iterative settings. Automatic/full-calc
metadata, package order, core properties and style serialization may differ only
if interpreted values and applicable scored colors remain unchanged. Strict
literal equality is conservative (even representational float differences are
ambiguous). Rewritten formula text/ranges/references except the frozen narrow
case/shared expansion rule are ambiguous. Array/spill interior literal changes
fail semantic equality. No semantic fingerprint is a proof for every possible
Excel feature; unknown calculation-relevant changes remain an attribution limit.
The witness must match V1's complete typed values, expanded formulas and scored
colors at all answer-position cells, not merely aggregate scores. It must preserve
V0 extracted raw formula text/attributes, nonformula semantics, and all non-sheet
package parts. Witness tests include numeric/string/empty/error/Boolean caches,
shared-string decoding, no-op transplant, and literal-change rejection.

The official evaluator's error-cache-triggered formula fallback is retained.
Cache recovery means recovery of the official score, never numerical correctness
inferred from an error cache. Cache census explicitly reports error transitions;
scorer-observed error fallback is recorded for strong cases. Zero assessed cells
or workbook read exceptions are unscorable, not semantic score-zero failures.
Gate B is evaluated once at full replay completion using all eligible rows per
P1/P2/P3 stratum (including unresolved) and categories within each, with >=5 rows
for threshold triggers; qualitative architecture contradiction can trigger at any
size. Exact-change proportion >20%, category net exact shift absolute >=20pp,
material harm rate >=5%, formula-rewrite rate >=20%. Unsupported/failures have
explicit bounds and never count as unchanged. Concurrent deterministic workers=4;
pilot workers=1. Hash-identical recalculation may be reused with locked artifacts
and unique-execution cost counted once. Fresh profile configuration recorded;
disposable LO profiles removed after execution, not scored workbooks.

Review suggestion disposition: provenance separation, semantics fingerprint,
assessed-cell witness equality, error fallback disclosure, fixed denominators,
no-op/type tests, unresolved bounds and tooling/fairness separation ACCEPTED.
No outcome thresholds were changed after observing scores. More exploratory arms
REJECTED as unnecessary: the frozen V0/V1 plus sufficiency witness discriminates
the cache hypothesis within this bounded environment. Strong reviewer selection:
gpt-6-astra, independent review only; initial same-family review retained separately.

## Pilot plumbing amendment before final freeze
The pilot identified stored iteration-enabled metadata even in a formula-free
workbook. Treating the flag alone as unsupported would prevent the prescribed
replay on otherwise loadable archives. All iteration-enabled workbooks will
therefore be recalculated with their archived settings recorded, but any improved
score remains ambiguous: iterative starting caches can change computation paths.
Iteration-enabled cases cannot enter CACHE_ONLY_SCORE_RECOVERY. This change
expands deterministic replay coverage; it does not expand the strong class or
change materiality thresholds. Volatile functions, macros/UDFs and external links
remain unsupported as previously specified. Repeat the pilot after this plumbing
correction. UNO pipe identity must be unique per isolated profile/hash, as verified
before any concurrent full replay; pilot caches from the earlier pipe configuration
are retained but not reused in the frozen execution namespace.
