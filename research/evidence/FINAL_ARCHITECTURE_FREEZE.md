# Final architecture freeze

Final corrective implementation and cumulative evidence snapshot, 2026-09-22. This supersedes [ARCHITECTURE_EVIDENCE_FREEZE.md](ARCHITECTURE_EVIDENCE_FREEZE.md) for architectural decisions while preserving it and its companion directory as evidence history. It incorporates the [representative checkpoint](REPRESENTATIVE_ARCHITECTURE_CHECKPOINT_REPORT.md), rather than replacing its results. Machine-readable decisions and verification artifacts are in [final_architecture_freeze/](final_architecture_freeze/).

**Final decision:** retain the ordinary coding-agent core, the existing conservative A+A1 fast path and cheap capture assurance; keep the compiled substrate only as conditional hidden infrastructure with mandatory fail-closed/freshness guards. Remove substrate-backed helper execution. A generic rebuild from zero is not compelled: the positive substrate economics depend on the large-workbook tail. Mechanism discovery is closed; the next phase is engineering and communication.

No new representative/full benchmark, model calls, scoring runs, mechanism experiments, helper surface design, A1 expansion, A2/A3/B, Track C intervention, formula-error feedback or productization was performed.

## Corrective gate and evidence preservation

The original H1 crash was an eager parse of malformed `docProps/core.xml`, not a failed agent semantic decision. The parent now disables that workbook's optional substrate, allowing ordinary agent execution to proceed. Exact-source mechanical replay under Python 3.13/openpyxl 3.1.5/lxml matches the original XMLSyntaxError and returns the same exception from H0 and H1. There is no published partial index or accelerated read. The narrower required outcome is met: **no additional substrate-specific veto**; malformed input does not become a valid workbook.

The archived transient `Template:06_08` UnicodeDecodeError is mechanically identified, but its input does not reproduce the error. It now opens in both paths. A separately labelled injected exception of the recorded class confirms successful ordinary fallback. The original transient's internal trigger is not established; injection is not historical reproduction. An earlier check with stdlib XML also produced equal H0/H1 errors (ParseError); that parser-environment difference is preserved separately.

See [corrective_replay.json](final_architecture_freeze/corrective_replay.json), [corrective_fix_manifest.json](final_architecture_freeze/corrective_fix_manifest.json), and [fail_closed_tests.json](final_architecture_freeze/fail_closed_tests.json). Tests cover malformed bytes/package, unexpected parser exceptions, initial/partial builds, substrate unavailability, unsupported structures, successful reference fallback, no serve after failure, valid acceleration and explicit generation recovery. Existing helper and mutation runtime regressions also pass. Database identity/completion is committed with the rows; stale authority is retired before replacement; failed bytes cannot accidentally revive. Failure scope is workbook/generation where known, process/runner scope only where unknown identity or unavailable publication storage prevents safe narrower recovery.

A focused fixture check exposed the pre-existing empty-sheet unbounded iterator edge (`[(None,)]` versus reference `[]`). That case now takes ordinary openpyxl, without adding an accelerated semantic operation. The A1 gate and normal earned primitive behavior remain unchanged. There is no new performance measurement; additional boundary validation is an implementation cost, not retroactive timing evidence.

The corrective runner verifies hashes of 1,436 original checkpoint JSON/JSONL/Markdown artifacts before and after replay; [preserved_checkpoint_hashes.json](final_architecture_freeze/preserved_checkpoint_hashes.json) records them. Original primary and replication outcomes, voids, censoring, shims and trajectories remain intact. Source reports have a separate [hash manifest](final_architecture_freeze/evidence_source_hashes.json). Corrective evidence is labelled `CORRECTIVE_FAIL_CLOSED_REPLAY` and is never inserted into the original score tables.

## Cumulative capability interpretation

| Claim | Final status | Meaning |
|---|---|---|
| REPRESENTATIVE_CHECKPOINT_CAPABILITY_NEUTRALITY | SUPPORTED_NARROWLY | Mixed completed-pair scores, no systematic direction; small uncensored sample and substantial variance. |
| CUMULATIVE_PRACTICAL_STACK_CAPABILITY_PRESERVATION | SUPPORTED | Multiple independent causal scopes and replications support practical preservation after fixing the documented parser veto. |
| STATISTICAL_EQUIVALENCE | NOT_ESTABLISHED | No equivalence design, margin or powered uncensored evidence; nonsignificance is insufficient. |

The initial transparent-runtime study was MIXED, with three H1-only pre-mutation stalls. Its targeted replication found discordant-task stalls exactly tied (3/6 per arm), overlapping completed outcomes and no runtime failures. The thin checkpoint resolved apparent losses through replication and activation-boundary autopsies; its helper/note experiment is not identical to the later invisible-stack comparison. Initial Candidate-A live contact was insufficient and its positive timing did not replicate; that negative evidence stands. Later A1 earned 51/51 exact traces and 7/12 exposure-enriched contact, with provider/workbook censoring explicitly retained.

The representative checkpoint supplies 8 dual-scored pairs, mixed H1−H0 modification deltas, 14 H0 versus 9 H1 outputs, and McNemar p=.125. Provider/model censoring and within-arm swings up to .50 prevent a formal equivalence claim. The stable Template:16_07 completion gap is not erased; two draws showed an H0 advantage without an identified treatment mechanism. The deterministic malformed-input veto was causally real and is corrected here, not explained away as variance.

Across these studies, no unresolved reproducible degradation attributable to the retained invisible mechanisms is established within the tested scopes. This is cumulative practical support, not a pooled statistical estimator, a guarantee for all workloads, or a new live capability claim for this corrected source. Details and per-study limitations: [cumulative_capability_evidence.json](final_architecture_freeze/cumulative_capability_evidence.json).

## Representative economics and final component decisions

| Component | Preserved measurement | Decision and limit |
|---|---|---|
| Candidate A+A1 | 59/282 loads (~21%); median saving ~.32s/load, mean ~1.43s/load | Retain narrow gate; large-workbook tail matters. No universal applicability requirement. |
| Non-load contact | 91,231 accelerated operations; 95% in 5 slots; 15/30 H1 slots with zero | Uneven observed contact, not an invitation to broaden A1. Zero runtime fallback failures does not erase the two pre-fix initialization crashes. |
| Compiled substrate | 24.7568s initial + 1.1599s refresh/maintenance = 25.9167s | Existing practical retention supported narrowly; general rebuild-from-zero justification not established. |
| Mutation capture | .3424s total; 16 mutations; 0 runtime and 0 validation failures; 0 prevention witnesses | Assurance earned. Failure prevention and capability necessity not established. |
| Freshness | ~1.16s / 493 refresh calls; zero stale serving where measured | Required only if substrate-backed serving exists; no independent architectural entitlement. |
| Helpers | Report comparison ~2.6s substrate/call versus ~.1s reference inspect; 8/60 slots; no adoption advantage | Remove substrate execution; keep same optional contract on reference openpyxl. |

The mean-based unit-cost estimate yields ~84s gross A savings (~58s after substrate), whereas median-based ~19s gross is about ~7s below the ~25.9s substrate cost. The latter is near/below break-even, not a positive broad rebuild case. These are approximate checkpoint estimates; exact-trace causal timing comes from the earlier A1 study. Cross-arm total-task speedup is not established. For helpers, the rounded report comparison is not an all-helper average: exact per-helper means and call counts remain in [checkpoint_adjudication.json](final_architecture_freeze/checkpoint_adjudication.json) and the original economics file.

**CURRENT PRACTICAL RETENTION:** conditional hidden substrate + A1 is worth retaining at low marginal cost, with hardening and assurance. **ZERO-SUNK-COST BUILD DECISION:** default to the ordinary core; choose a minimal read index only for an expected workload tail that pays its full cost. Candidate A is the retained economic consumer; freshness is its correctness obligation, not a second benefit that justifies the index. Capture earns assurance independently. The rejected helper backend receives no accounting credit. This prevents A↔substrate circularity.

## Three separate architectures

A — evidence-compelled core:

```text
GENERAL-PURPOSE CODING AGENT
        ↓
ordinary Python / openpyxl + normal scaffold conveniences
        ↓
actual workbook
        ↓
LibreOffice recalc / validation / score
```

B — practical retained architecture:

```text
agent / Python / openpyxl
        ├─ Candidate A+A1 (narrow frozen gate)
        │       fail-closed → real openpyxl
        ├─ transparent mutation capture (assurance)
        ├─ freshness / generation guards (conditional invariant)
        └─ compiled/indexed substrate (conditional hidden infrastructure)
        ↓
actual workbook → LibreOffice

optional existing helper surface → plain/reference openpyxl
```

C — zero-sunk-cost rebuild:

```text
ordinary coding-agent core first
        ├─ thin transparent capture if assurance is wanted
        ├─ optional existing helpers → reference openpyxl, if product need warrants
        └─ only with a demonstrated large/repeated-read workload tail:
              minimal read index + narrow A1 + fail-closed + freshness
```

There is no default generic substrate build, and no stand-alone compiled freshness infrastructure without compiled serving. Nothing closed or frozen is included merely because its implementation exists. See the three architecture JSON files for dependency and cost constraints.

## Final evidence ledger

| Claim | Status | Scope |
|---|---|---|
| PYTHON_OPENPYXL_CORE | EARNED | Ordinary Python + scaffold + workbook + LO; no universal optimality. |
| CUMULATIVE_PRACTICAL_STACK_CAPABILITY_PRESERVATION | SUPPORTED | Tested causal scopes; known pre-fix veto preserved and corrected; not equality. |
| REPRESENTATIVE_CHECKPOINT_CAPABILITY_NEUTRALITY | SUPPORTED_NARROWLY | No systematic score direction, not formal neutrality proof. |
| STATISTICAL_EQUIVALENCE | NOT_ESTABLISHED | No formal score, completion or distribution equivalence claim. |
| CANDIDATE_A_CONDITIONAL_FIDELITY | EARNED | Earned primitive read surface only; unsupported cases reference. |
| CANDIDATE_A_REPRESENTATIVE_CONTACT | EARNED | Observed 30-task sample; no universal coverage or A1 broadening. |
| CANDIDATE_A_EXISTING_SUBSTRATE_ECONOMICS | SUPPORTED | Low marginal retention cost; model/network/total-task gains not inferred. |
| CANDIDATE_A_ZERO_SUNK_COST_ECONOMICS | SUPPORTED_NARROWLY | Tail-dependent workload build case only, not general substrate mandate. |
| COMPILED_SUBSTRATE_PRACTICAL_RETENTION | SUPPORTED_NARROWLY | Keep existing hidden implementation after hardening; no helper consumer credit. |
| COMPILED_SUBSTRATE_FROM_ZERO_JUSTIFICATION | NOT_ESTABLISHED | Do not rebuild generic substrate by default; known heavy readers may justify minimal index. |
| TRANSPARENT_MUTATION_CAPTURE_ASSURANCE | EARNED | Cheap deterministic assurance/detection, transparent mutation semantics. |
| TRANSPARENT_MUTATION_CAPTURE_FAILURE_PREVENTION | NOT_ESTABLISHED | Do not claim prevention in practice; no witness hunt. |
| TRANSPARENT_MUTATION_CAPTURE_CAPABILITY_NECESSITY | NOT_ESTABLISHED | Assurance can justify retention without necessity. |
| FRESHNESS_GENERATION_INVARIANT | EARNED | Mandatory only when compiled serving exists; no independent consumer/rebuild credit. |
| SUBSTRATE_HELPER_BACKEND | REJECTED | Removed from active contract; historical implementation/evidence retained. |
| HELPER_MODEL_FACING_SURFACE | SUPPORTED_NARROWLY | Unchanged; product retention independently adjudicable, no optimization now. |
| FAIL_CLOSED_SUBSTRATE_BOUNDARY | EARNED | Ordinary openpyxl may itself reject bad workbook; no extra substrate veto. |
| TRACK_C_CLOSURE | CLOSED | Large new context is not mechanically removable projection. |
| MECHANISM_DISCOVERY | CLOSED | No unresolved new semantic failure in corrective replay; remaining work engineering/communication. |

## Required answers

1. **What exactly caused the deterministic H1 substrate crash?** Financial_Model:06_01 has an undeclared `dc` prefix on `creator` in `docProps/core.xml`. openpyxl/lxml raises `XMLSyntaxError` (line 1, column 574). H1 eagerly called `prepare_substrate → ensure_fresh → build_index → load_workbook(read_only=True)` without a catch, so an optional build became a runner veto. Ordinary openpyxl also rejects these bytes.

2. **What fail-closed boundary was added?** Transactional index construction and atomic publication, generation failure tombstones, validated read-only snapshot acquisition, proxy retirement/reference delegation, and bootstrap rollback. Every caught substrate failure records exception class, stage, workbook/generation identity, reason, partial initialization and prior accelerated serving; no gold/evaluator content enters telemetry.

3. **Does the affected case now behave no worse than reference openpyxl?** Yes at the corrected boundary: preparation proceeds, publishes no workbook index, and H1 ordinary loading returns the identical XMLSyntaxError/message as H0. The invalid workbook itself is not repaired. This is mechanical reference parity, not a new model success.

4. **Is partial/stale substrate serving impossible after failed initialization?** The corrected state machine provides no authoritative handle/manifest after a failed build. Old handles are retired before rebuild; completed rows and an identity marker commit together; publication is atomic. Failed generations stay disabled, including already returned proxies. Tests cover partial DBs, missing/corrupt/stale databases, failed refresh and post-load DB failure. This is the enforced boundary invariant, not a claim of exhaustive proof for arbitrary OS/concurrent failures.

5. **Did valid-workbook Candidate-A behavior remain unchanged?** The A1 classifier and admitted primitive operations are unchanged; valid fixtures still accelerate and match ordinary openpyxl. A pre-existing empty-sheet unbounded iterator mismatch discovered in corrective tests now falls back. Guards add validation work; performance was not remeasured and the historical timing evidence remains historical.

6. **What is checkpoint-only capability-neutrality status?** `REPRESENTATIVE_CHECKPOINT_CAPABILITY_NEUTRALITY: SUPPORTED_NARROWLY`.

7. **What is cumulative capability-preservation status?** `CUMULATIVE_PRACTICAL_STACK_CAPABILITY_PRESERVATION: SUPPORTED` for the tested causal scopes, informed by independent runtime replications, thin-checkpoint autopsies and A/A1 exact fidelity. The real pre-fix parser veto is preserved and corrected, not relabelled as noise. This does not establish unconditional capability equality for the revised code.

8. **Is formal equivalence established?** `STATISTICAL_EQUIVALENCE: NOT_ESTABLISHED`. There was no equivalence margin/design or adequate uncensored equivalence evidence; p=.125 is not equivalence.

9. **What does representative A contact establish?** Observed sample contact: 59/282 loads (~21%) and 91,231 accelerated non-load operations. 95% of non-load operations sit in 5 slots; 15/30 H1 slots have none. This replaces the old unmeasured-prevalence placeholder with uneven measured contact, not universal applicability.

10. **Is A worth retaining with an existing substrate?** Yes, conditionally: exact earned surface, conservative fallback, low marginal retention cost and material large-workbook-tail savings. The narrow A1 gate stays fixed.

11. **Would A alone justify rebuilding the substrate from zero?** Not as a general default. It supplies a workload-tail-specific case: estimated mean-based ~84s gross savings covers ~25.9s substrate, while median-based ~19s does not. Do not claim broad self-funding or count the index as free.

12. **What is final practical substrate status?** `COMPILED_SUBSTRATE_PRACTICAL_RETENTION: SUPPORTED_NARROWLY` — retain existing conditional hidden infrastructure after hardening, with Candidate A as the retained paying consumer.

13. **What is final zero-sunk-cost substrate status?** `COMPILED_SUBSTRATE_FROM_ZERO_JUSTIFICATION: NOT_ESTABLISHED` as a general build. A minimal index may be chosen for a known large/repeated-read tail on full-cost accounting; the default rebuild omits a generic substrate.

14. **What is capture's final status?** Assurance `EARNED`; retain transparent capture as a cheap deterministic property. Checkpoint: 0.3424s, 16 mutations, zero runtime/validation failures.

15. **What does capture still not establish?** Failure prevention and capability necessity are both `NOT_ESTABLISHED`; there were zero prevention witnesses and no untreated-corruption differential. Do not search for witnesses to justify the component.

16. **What is freshness's final status?** `EARNED` conditional invariant: ~1.16s / 493 refresh calls, zero stale serving where measured. Required with substrate-backed reads; no independent architectural claim without them.

17. **Was the substrate helper backend removed?** Yes from active retained execution: the general helper shim and both retained runner arms use reference openpyxl. Historical API source and original checkpoint shims/evidence remain for archaeology, not as retained consumers.

18. **What backend now serves helpers?** Plain/reference openpyxl, including style reads; tests assert that helpers bypass Candidate A and index construction.

19. **Does the helper model-facing surface remain unchanged?** Yes: existing names, arguments, factual contract and prompt note remain. Reference backend uses its already established generation metadata (index_generation=0). Optional helper-surface product status remains independently adjudicable; no helper optimization or expansion occurred.

20. **What is the final evidence-compelled architecture?** General-purpose coding agent → ordinary Python/openpyxl + normal scaffold conveniences → actual workbook → LibreOffice recalc/validation/score.

21. **What is the practical retained architecture?** That core plus invisible narrow A+A1 with fail-closed fallback, transparent mutation capture, conditional freshness guards and a hidden compiled/indexed substrate. Optional helpers → reference openpyxl. No substrate helper backend.

22. **What is the zero-sunk-cost rebuild?** Build the ordinary core first. Thin transparent capture may be added explicitly for assurance. Build minimal index+A1+fail-closed/freshness only for a known workload tail with full-cost justification; otherwise omit compiled serving and its freshness machinery. Optional helpers can use openpyxl without an index.

23. **Which branches are permanently closed absent materially new evidence?** All 22 prior closure entries and their reopening gates are preserved in `final_closed_branches.json`: required IR/authority/scheduler/closure/program-group runtime; model-facing SQL; dependency-as-intent; fingerprint-as-program-choice; required mutation IR; batch writers; verification receipts; generic compression; persistent state for tokens; delta/reference handles; derivation elision; Track C projection/repetition; and the remaining semantic restoration/helper branches.

24. **Which branches remain frozen?** A2, A3, narrow opt-in Candidate B, general temporal/output-role ontology, program-group opt-in lowering, formula-error feedback, uniformity-flag transfer and output-role break localization. None is integrated. The former representative-A placeholder is now adjudicated, with its prior frozen entry preserved as history.

25. **Is mechanism discovery closed?** `MECHANISM_DISCOVERY: CLOSED`. Corrective replay found no unresolved new semantic failure; the fixture edge was resolved by losing acceleration. Uneven contact, tail economics, low adoption and absent prevention witnesses do not reopen discovery.

26. **What implementation work remains?** No corrective hardening or mechanism implementation required by this task remains. Future engineering should review/integrate this source into the selected maintained harness and verify compatibility in its release configuration; the workspace also contains unrelated pre-existing research changes.

27. **What productization work remains?** Single installation/bootstrap path; dependency and LibreOffice checks; enable/disable controls; safe defaults; unavailable-substrate fallback; minimal example; diagnostic status; versioned compatibility. Not implemented here.

28. **What presentation/communication work remains?** An evidence-linked technical narrative and scoped claims using PRODUCT_PRESENTATION_HANDOFF.md. Preserve denominators, negative results, censoring, uncertainty and retention-versus-rebuild accounting; no website/marketing built.

29. **What are the strongest defensible external claims?** Ordinary Python remains the working interface; a structured semantic waist was not required by this tested agent; read acceleration is exact on its earned surface and can pay on large-workbook tails; capture is cheap assurance; measured repetition is small; large first-seen context does not imply a safe mechanical cut; unsupported optimized paths use reference semantics.

30. **What claims must not be made?** Better benchmark scores; universally faster; Python universally optimal; formal capability equivalence; compiled substrate always pays; capture prevents corruption in practice; all spreadsheet agents should use this architecture. No total-task, token or cost benefit is inferred from conditional read timing.

31. **What is final research status?** `FINAL_ARCHITECTURE_AND_EVIDENCE_FROZEN`; mechanism discovery closed, practical components adjudicated, original outcomes retained, known deterministic veto corrected. Transient historical trigger remains unproven, explicitly bounded by natural replay and exception injection.

32. **What should happen next?** Engineering integration and basic installability/packaging, followed by evidence presentation within the claims registry. Neither requires a new benchmark, consumer, interface, semantic mechanism or reopening of frozen leads.

## Closure, frozen leads and handoff

The [22-entry closure ledger](final_architecture_freeze/final_closed_branches.json) preserves each reason and materially-new-evidence reopening gate. Closed branches include task/obligation IR runtime; required edit plans; scheduler; execution closure; program-group runtime; model-facing SQL/compiled cognition; dependency-as-intent; formula-fingerprint-as-program-choice; required mutation IR; batch write helpers; verification receipts; generic context compression; persistent state for token reduction; delta/reference handles; derivation elision; Track C projection/repetition and semantic authority restoration.

The [frozen ledger](final_architecture_freeze/final_frozen_branches.json) retains A2, A3, Candidate B, general temporal/output-role ontology, program-group opt-in lowering, formula-error feedback, uniformity-flag transfer and output-role break localization without integration. The earlier representative-A claim is archived as a prior frozen entry and now adjudicated by the checkpoint. Formula-error precision provenance remains flagged as in the prior freeze; no new precision result or closed-loop benefit is invented.

Track C remains closed: C0/C1≈1.65%, C2≈1.68%; first-seen broad scans are large, but no viable no-hindsight selector met the reduction/recall gate. The existence of a large oracle P2 mass does not earn projection machinery. No repetition/projection mechanism is reopened.

The [research-lead registry](final_architecture_freeze/final_research_leads.json) adds `BASIC_INSTALLABILITY_AND_PACKAGING / PRODUCTIZATION_TASK / NOT_RESEARCH_MECHANISM` and `EVIDENCE_PRESENTATION_AND_CLAIMS / COMMUNICATION_TASK / NOT_RESEARCH_MECHANISM`. They are future authorized engineering/communication work, not invitations to discover another mechanism. The [product and presentation handoff](PRODUCT_PRESENTATION_HANDOFF.md) records minimum installability requirements and an evidence-linked five-column claims registry. No productization is implemented here.

One noisy checkpoint does not erase cumulative causal evidence; neither does cumulative evidence create statistical equivalence that was never measured. Unsupported optimization loses acceleration, never reference semantics. Retention and rebuild are different decisions. Tail-dependent value and cheap assurance are legitimate properties without universal speed or prevention claims. Remaining work is implementation integration, packaging and communication.

## Final synthesis

### CORRECTIVE FAIL-CLOSED FIX

Index/build/publication/snapshot failures explicitly disable acceleration; ordinary path and mutation authority remain intact.

### CORRECTIVE REPLAY RESULT

PASS: malformed case matches reference XMLSyntaxError with no substrate veto. Transient input naturally opens in both; labelled injection tests fallback only. Original primary results preserved.

### CUMULATIVE CAPABILITY INTERPRETATION

SUPPORTED within tested causal scopes, after correcting the documented veto; formal equivalence NOT_ESTABLISHED.

### REPRESENTATIVE CHECKPOINT INTERPRETATION

SUPPORTED_NARROWLY: 8 mixed dual-scored pairs, 14 vs 9 outputs, p=.125, heavy censoring and large within-arm variation.

### FINAL EVIDENCE-COMPELLED ARCHITECTURE

General coding agent → ordinary Python/openpyxl + scaffold → workbook → LibreOffice recalc/validation/score.

### FINAL PRACTICAL RETAINED ARCHITECTURE

Core + narrow invisible A+A1, capture assurance, mandatory conditional freshness and hidden substrate; optional helpers use reference openpyxl.

### FINAL ZERO-SUNK-COST REBUILD

Ordinary core first; optional capture for assurance; minimal index+A1 only on a fully costed large/repeated-read tail. No generic substrate mandate.

### CANDIDATE A+A1

Retain narrow gate: 59/282 load contact and earned fidelity; uneven non-load contact does not call for expansion.

### COMPILED SUBSTRATE

Practical retention supported narrowly; ~25.9s checkpoint cost. General from-zero justification not established; tail-specific value is supported narrowly.

### MUTATION CAPTURE

Assurance EARNED; .34s / 16 mutations, zero runtime/validation failures. Prevention and capability necessity NOT_ESTABLISHED.

### FRESHNESS / GENERATION

EARNED conditional correctness invariant; ~1.16s / 493 calls, zero stale serving where measured. No independent claim without substrate reads.

### HELPERS

Substrate execution removed from active contract. Reference openpyxl serves unchanged optional surface; surface product status stays separate.

### TRACK C

CLOSED: measured repetition is small; voluminous first-seen context lacks an earned mechanical cut.

### CLOSED BRANCHES

All 22 closure entries and their materially-new-evidence gates preserved; none reopened.

### FROZEN BRANCHES

A2, A3, B, ontology, opt-in program groups, formula-error feedback, uniformity transfer and output-role localization remain unintegrated.

### RESEARCH LEADS

Three original leads stay frozen. Installability/packaging and claims/presentation are future engineering/communication, not mechanisms.

### MECHANISM-DISCOVERY STATUS

CLOSED. No unresolved new semantic failure from corrective replay and no economic finding licenses invention.

### PRODUCTIZATION HANDOFF

Registry written; ordinary coding-agent experience retained. No installer, packaging, UI, website or marketing built.

### INSTALLABILITY REQUIREMENTS

One documented path, dependency/LibreOffice checks, runtime controls, safe defaults/fallback, example, diagnostics and versioned compatibility.

### PRESENTATION CLAIMS

Scoped ordinary-interface success, earned exact read acceleration, tail value, cheap assurance, measured Track C limits and reference fallback. Preserve semantic freedom; move only proven mechanical work underneath the existing interface.

### CLAIMS WE MUST NOT MAKE

Better scores; universal speed/Python optimality; formal equivalence; always-profitable substrate; observed corruption prevention; universal agent prescription.

### FINAL RESEARCH VERDICT

FINAL_ARCHITECTURE_AND_EVIDENCE_FROZEN. Known boundary veto corrected, evidence history intact, remaining questions are bounded engineering/product choices.

### NEXT PHASE

Review/integrate the correction, then basic installability/packaging and evidence presentation. No automatic benchmark or mechanism reopening.
