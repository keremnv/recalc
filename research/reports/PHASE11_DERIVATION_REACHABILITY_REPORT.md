# Phase 11: deterministic derivation reachability census

Research phase. Product runtime untouched (no rc2 file modified; all analysis
under `phase11/` plus one unit test for a research helper). Offline replay of
frozen ordinary-Python trajectories; no live model calls; gold used only to
classify outcomes, never to generate facts.

## RESEARCH QUESTION

Which mechanically derivable spreadsheet facts does a strong ordinary
Python/openpyxl agent already discover reliably, which does it fail to
discover, how expensive would self-discovery be, and which missed derivations
plausibly sit on real failure paths? Hypothesis: a class of deterministic
facts exists that is mechanically reliable and cheap, yet naturally
unreached even when relevant. Null: missed facts are too rare, expensive,
semantic, or failure-disconnected to justify a new evidence surface.

## CORPUS

179 ordinary-Python runs (bash/python/view_xlsx/submit, GLM-family) with full
model-visible transcripts + run records: representative 59, token-primary 48,
inspection 28, batch 26, live-transparent 18. Readable inputs: 146; with
outputs: 74; matched pairs: 59 (all LibreOffice-recalced ok). Outcomes:
SUBMITTED with scores for ~130; 105 runs R0 for D3 (no output: NO_SUBMIT 45,
noncompletion 30, censored 19, truncated 11). Old structured-harness
trajectories (~1000 MCP-era) used for context only, never prevalence.
Details: `phase11/CORPUS_POPULATION.md`.

## DERIVATION SPECTRUM

D0 raw facts excluded as non-derivations; D4 semantic judgments excluded as
non-deterministic. Census covers 8 candidates + 2 controls: D1 (formula
list, merged map, direct deps), D2 (family, uniformity, period map, role
sets, blank refs), D3 (error delta, post-edit breaks, change diff).
Registry: `phase11/DERIVATION_CANDIDATE_REGISTRY.json`.

## MECHANICAL CERTAINTY

EXACT: family, uniformity, deps, blank delta, change diff, merged, formula
list. CONDITIONAL: error delta (on recalc trust — validated: LO recomputes
values and error types on synthetic + corpus files; UDF/macro workbooks
excluded), period map (clean headers), role sets (positional repetition).
Nothing HEURISTIC or SEMANTIC advanced. Full precedent maps and raw
input-state break lists are exact but non-actionable (breadth without
precision) — classified accordingly, not promoted.

## NATURAL REACHABILITY

Per-candidate R-distributions over exposed runs (906 matrix rows;
`phase11/DERIVATION_REACHABILITY_MATRIX.jsonl`):

| candidate | n | R4+R5 reach rate |
|---|---|---|
| CTRL-FORMULA-LIST | 87 | 67% (control: apparatus works) |
| FAM-REL-FAMILY | 85 | 8% |
| UNIF-FAMILY-BREAK | 81 | 5% |
| ERR-NEW-ERROR-DELTA | 74 w/ output | 41% re-read values, 0% scanned errors |
| TEMP-PERIOD-MAP | 74 | 16% |
| ROLE-EQUIV-SET | 78 | 1% |
| DEP-DIRECT-REFS | 87 | 0% systematic (R3 manual 20%) |
| REF-BLANK-DELTA | 81 | 10% (spot checks, never enumeration) |
| CHG-STRUCT-DIFF | 49 w/ footprint | 69% diff when suspicious |
| CTRL-MERGED-MAP | 0 | unexposed (no merges in corpus) |

Rules were validated by trigger-snippet review; two overcoding bugs found
and fixed (FAM `==`-comparison, ROLE block-loop), one false positive
corrected ("equivalent formula"). Coding is conservative throughout.

## DECISION BEARING EVENTS

Events detected per run: CHOOSE_TARGETS (first mutation), COPY_FORMULA
(formula-string write), VERIFY_AFTER_EDIT (post-save output read),
SUBMIT/DECLARE_COMPLETE. Candidates bound to their primary event
(ERR→SUBMIT, FAM→COPY_FORMULA, UNIF/ROLE/DEP→CHOOSE_TARGETS,
TEMP→CHOOSE_SOURCE_PERIOD, REF/CHG→VERIFY_AFTER_EDIT). The unit of analysis
is candidate × event × run, not all-possible-facts.

## TRIVIAL PYTHON BASELINE

1–3 lines: formula list, merged map. 4–10 lines: error scan (given recalc),
blank-ref enumeration, change diff, period parse (clean), dep extraction.
11–30 lines: family grouping, uniformity diff. Multi-stage/recalc: error
delta end-to-end. The census's punchline: the 4–10-line D3 checks have the
lowest reach rates where they matter (0% systematic error scans,
0% systematic uniformity compares) — code length predicts nothing.

## DISCOVERY COST

Implementation cost is trivial for all promoted candidates; discovery cost
dominates and takes three forms: (1) temporal — D3 facts require
re-entering the pre-edit past after acting (uniformity, blank delta);
(2) attentional — error values hide in unopened outputs (agents confirm
expected changes, never hunt damage); (3) framing — no trigger poses the
question ("did I break anything?"). Recalc itself is NOT a discovery
barrier (70/179 runs recalc unprompted); the missing step is the scan
afterward.

## FORMULA FAMILY STRUCTURE

Near-universal (85/87 formula workbooks; families of hundreds–thousands)
and near-never computed (R4 8%, all Debugging). But membership is
background, not signal: GENERIC throughout, no discriminator. Verdict:
infrastructure for the uniformity detector, never a surface. Details:
`phase11/FORMULA_FAMILY_STUDY.md`.

## UNIFORMITY BREAKS

Input-state breaks: ubiquitous (81/85) and noisy (legitimate edges) —
unfit to surface. Post-edit breaks: 28/59 outputs (47%), small sets
(1–3 cells in 19/28), NEVER systematically compared by agents, and
containing a scored miss in the cleanest case (DCF!X9 ∈ 3-cell set,
DIRECTLY_LINKED). D2 variant rejected as noise; D3 variant promoted.
Details: `phase11/UNIFORMITY_STUDY.md`.

## FORMULA ERROR DELTA

59/59 pairs recalced; 4 runs introduced errors (23/29/442/24 cells;
#VALUE!/#DIV/0!), all submitted, all failed, all at R≤3 (two never
re-read values at all). One DIRECTLY_LINKED (miss ∈ 23-cell set); one
442-error genuine destruction (agent emptied ≥200 inputs). Cached-value
comparison found zero — recalc was necessary. Prevalence 4/59 observed
(low-frequency, high-severity — the exact shape agents don't self-check).
Promoted. Details: `phase11/FORMULA_ERROR_DELTA_STUDY.md`.

## TEMPORAL RELATIONS

Present in 51% of inputs; parsed 16% of the time; modal behavior is
see-without-parsing (R2=53/74). Plausibly relevant to period choice in FM
tasks, but no discriminator demonstrated (upstream leverage inferred).
Verdict: bundle-only accessory, not a standalone promotion. Details:
`phase11/TEMPORAL_REACHABILITY_STUDY.md`.

## OUTPUT ROLE RELATIONS

Present in 53%; structurally compared in 1% (single genuine eyeball
analogy). The extreme gap with zero demonstrated leverage: no twin-block
failure isolated, no discriminator. The "missed but useless" archetype —
missingness alone is not value. Rejected. Details:
`phase11/OUTPUT_ROLE_REACHABILITY_STUDY.md`.

## DEPENDENCY FACTS

Zero systematic extraction in 87 runs (agents hand-trace 1 hop when
forced). Full map too broad to discriminate; one-hop context of
already-found signals is the legitimate use. Verdict: accessory inside
the error/break block, never standalone. dependency ≠ intent preserved.
Details: `phase11/DEPENDENCY_REACHABILITY_STUDY.md`.

## REFERENTIAL INTEGRITY

Became-blank deltas: exact, cheap, enumerated by no agent (R4s are
debugging spot-checks). DIRECTLY_LINKED ×2 incl. the DCF!X9 triple
corroboration (break + blank-ref + miss). Static blank lists are noise
(MEDIUM); the delta is signal (LOW overreach). Promoted as part of the
verification block. Details: `phase11/WORLD_STATE_DERIVATION_STUDY.md`.

## WORLD STATE DERIVATIONS

The verification gap is the census's central D3 finding: agents verify
the task (did my edit land — 69% diff when suspicious, 70 recalcs) but
never the damage (0 systematic error scans, 0 uniformity compares, 0
blank enumerations across all positive cases). All damage checks are
exact, cheap, and at R≤3 in 100% of positive cases. See the verification
table in `phase11/WORLD_STATE_DERIVATION_STUDY.md`.

## CHEAP BUT UNREACHED DERIVATIONS

Four: error scan, post-edit uniformity check, became-blank enumeration,
change-footprint review (unsuspicious subset). All 4–30 lines, all missed
where positive, all failure-linked. Common structure: post-action,
backward-facing, never framed as a question. Full section:
`phase11/CHEAP_BUT_UNREACHED_DERIVATIONS.md`.

## HARD BUT NATURALLY REACHED DERIVATIONS

Five: formula inventory + eyeball matching, suspicious-case diffing,
recalc mechanics, manual 1-hop tracing, header eyeballing. Each is
evidence against building its systematized twin. Full section:
`phase11/HARD_BUT_NATURALLY_REACHED_DERIVATIONS.md`.

## MISSED DERIVATIONS ON FAILURE PATHS

Precision-guarded linkages (finding set ≤50 + miss overlap + R<4):
DIRECTLY_LINKED — ERR ×1 (Template_10_01 B15), UNIF-D3 ×1 (DCF!X9),
REF ×2 (DCF!X9, NOI_Analysis!C32), CHG ×4 (Template_06_12 ×4, I9).
PLAUSIBLY_LINKED — UNIF ×44, TEMP ×35, ROLE ×45 (mechanical rule;
ROLE's mass discounted as prevalence artifact), CHG ×11, REF ×10,
ERR ×2. All linkage observational, never causal.

## COUNTERFACTUAL DISCRIMINATION

REDUCES_CANDIDATE_SET: ERR ×1 (23-cell), UNIF-D3 ×1 (3-cell), REF ×2,
CHG ×16 (small footprints; 12 already R4-reached by agents — the
discriminator matters only for the 4 unreached). UNIQUE_DISCRIMINATOR:
×0 — no singleton facts observed; the honest ceiling is small-set
narrowing plus severity veto (442 errors) plus multi-signal conjunction
(X9 triple). No live causal effect claimed.

## CATEGORY HETEROGENEITY

Template: error + change-footprint misses dominate (completion tasks,
unsuspicious submits). Debugging: uniformity/blank/triple-corroboration
cases + all eyeball R4s (task forces formula attention, yet systematic
comparison still absent). Financial_Model: the destruction case
(FM_01_01) + period-map relevance + blank-ref mass. No candidate is
Debugging-only or Template-only; the verification block is universal,
TEMP is FM-concentrated. Nothing averaged away: matrix rows carry family
throughout.

## DERIVATION FRONTIER

`phase11/CANDIDATE_FRONTIER.json`. The frontier is exactly one bundle —
the post-edit verification evidence block (error delta + uniformity
delta + blank-ref delta + change footprint + one-hop dep context) —
computed from frozen artifacts at VERIFY_AFTER_EDIT/SUBMIT. Intersection
verified per candidate: mechanically trustworthy ∩ naturally
under-reached ∩ decision-bearing ∩ cheap. Pareto, not scalar: ERR wins
on severity-veto, UNIF-D3 on precision, REF on corroboration, CHG on
coverage of the unsuspicious.

## CANDIDATES REJECTED

FAM standalone (non-discriminative background), ROLE (1% reach, zero
leverage — missingness ≠ value), DEP standalone (broad + manually
covered), TEMP standalone (no demonstrated discriminator; bundle-only),
CTRL-MERGED (unexposed in corpus; no conclusion), input-state UNIF (noise),
static blank lists (noise). Historical closures (IR, planners, SQL,
compression, authority claims) remain closed; nothing revived.

## CANDIDATES PROMOTED TO PHASE 12

ERR-NEW-ERROR-DELTA, UNIF-FAMILY-BREAK (post-edit small-set),
REF-BLANK-DELTA, CHG-STRUCT-DIFF — as ONE bundled evidence treatment
with veto-shaped presentation ("23 new #VALUE! — submit anyway?") and
zero repair authority. Standard applied criterion-by-criterion in
`phase11/PHASE12_PROMOTION_RECOMMENDATIONS.md`. Nothing implemented.

## LOW COUPLING DELIVERY SURFACES

First choice: `analyze <run-dir>`-style post-run analysis over frozen
(input.xlsx, output.xlsx) + recalc — pure function, no read-engine/live
coupling, no bootstrap changes (the 10C-A extension point, validated
intact). Alternatives in descending preference: optional versioned
diagnostic field, explicit verify command. Never: live runtime hooks,
admission coupling, model-facing helpers.

## AGENT CHALLENGE TO THE DERIVATION PROGRAM

Strongest kill-case: (1) Positive counts are tiny (4 error runs) — the
frontier could be a 4-anecdote artifact; prevalence is unestablished.
(2) The 442-error case needed no derivation — any glance at the output
would do; the failure is carelessness, and a block the agent ignores is
worth nothing (alert fatigue unmeasured). (3) CHG's value concentrates
where agents already self-serve (69%); the system adds only the
unsuspicious tail. (4) UNIF-D3's 28 positives include intended rewrites;
without rewrite-awareness the veto misfires on legitimate restructuring.
(5) Most "linked" misses would also be caught by task-specific review the
agent skipped for cost reasons — we may be measuring effort allocation,
not information lack. (6) The gold knows the miss; every discriminator is
computed with knowledge of where to look — live precision will be worse.
If Phase 12 shows agents dismissing the block or precision collapsing on
fresh tasks, close the program.

## ZERO SUNK COST INTERPRETATION

Invented-from-corpus-today list: post-edit error scan (yes — 4 silent
submits demand it), post-edit uniformity diff (yes — DCF!X9 earns it),
became-blank enumeration (yes — same case), change footprint (weak yes —
agents mostly self-serve). Everything else — families-as-surface, roles,
ontology, dep maps, period tools — the corpus would NOT invent: either
agents already do it, or no failure turns on it. Notably, the corpus
invents verification, not inspection: every surviving candidate faces
backward at the agent's own action. No historical machinery is carried
for its own sake; family/temporal/role apparatuses stay frozen.

## RESEARCH VERDICT

**A. `DERIVED EVIDENCE FRONTIER ESTABLISHED`.** Four candidates satisfy
all eight promotion criteria as one bundled verification block, with
recalc-verified ground truth, conservative validated coding, and
demonstrated (if small-sample) failure linkage plus counterfactual
discrimination. The verdict is existence, not prevalence — Phase 12 must
pre-register thresholds and a larger budget, and the challenge section
above is its kill-criteria draft.

## NEXT STEP

Phase 12: build the offline verification-block prototype (frozen-artifact
analyzer, no product changes), pre-register endpoints (submit-with-errors
rate, miss∩flag overlap, revisit rate, cost), and A/B it on fresh
ordinary-Python tasks with rewrite-aware filtering. If the block doesn't
move submit behavior or precision collapses, close the derivation program
per verdict E. Do not promote TEMP/ROLE/DEP/FAM surfaces; do not couple
to the read engine; do not frame anything as repair authority.
