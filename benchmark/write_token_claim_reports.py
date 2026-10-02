#!/usr/bin/env python3
"""Write frozen-evidence reports and the independent-review packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"research/history/token_claim_discovery"

AFFORDANCE_REVIEW_REQUIREMENT = """## Affordance-induced verification / commitment hypothesis

Explicitly test whether B's lower call count is explained by a change in **verification and commitment behavior** rather than helper execution.

The hypothesis is:

> Merely knowing that narrow factual lookup capability is available may change the model's policy: it may commit to an interpretation/edit sooner, perform fewer redundant inspections or double-checks, or avoid reopening/re-reading facts it considers mechanically recoverable if needed — even when it never actually invokes the helper.

Do NOT assume this is true.

Using the frozen trajectories, classify model/tool activity where mechanically defensible into:

```text
initial discovery / navigation

new-evidence inspection

hypothesis testing

reinspection of previously observed facts

verification / double-checking before edit

post-edit verification

reopen / reread after mutation

repeated formula-chain or range inspection

additional inspection after the required edit is already mechanically complete

other / ambiguous
```

Compare A versus B first, with C/D only as supporting contrasts.

Answer specifically:

1. Does B perform fewer verification/reinspection cycles than A?

2. Does B reach its first mutation materially earlier in model-call count?

3. Does B submit materially sooner after its final mutation?

4. Are there fewer workbook reopens or rereads after relevant facts have already been observed?

5. Are repeated reads of the same cells/ranges/facts lower in B?

6. Are fewer model calls explained by less redundant checking, or simply by unrelated trajectory divergence?

7. Is there evidence that B commits to a correct-enough solution earlier without reducing workbook quality?

8. Does the one actual helper-using B run behave differently from the B runs that merely knew helpers were available?

9. Among B runs with zero helper invocation, is there still a systematic verification/commitment difference relative to A?

10. Is the best description of any supported effect:

```text
HELPER EXECUTION

HELPER AVAILABILITY / AFFORDANCE

TEXTUAL PRIMING

EARLIER COMMITMENT

REDUCED REDUNDANT VERIFICATION

GENERAL TRAJECTORY VARIANCE

NOT IDENTIFIABLE
```

Do not infer model confidence or internal mental state.

Use observable behavior only.

If an affordance-induced reduction in redundant verification is supported, explain the smallest fresh experiment that would distinguish:

```text
mere textual cue that "a helper exists"

actual helper availability

credible ability to query the helper if needed

generic statement that precise factual lookup is available

no affordance cue
```

The goal is to determine whether the product changes **how much checking the agent believes it needs to perform**, while describing that entirely through observable trajectory behavior rather than anthropomorphic claims."""


def read(name,default=None):
    p=OUT/name
    return json.loads(p.read_text()) if p.exists() else default


def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()


def fmt(x):
    return "unavailable" if x is None else (f"{x:,.3f}" if isinstance(x,float) else f"{x:,}" if isinstance(x,int) else str(x))


def main():
    spec=read("preregistered_spec.json",{})
    notes=read("exact_notes.json",{})
    pop=read("population.json",{})
    order=read("run_order.json",{})
    tasks=read("task_token_summary.json",[])
    fx=read("factorial_effects.json",{})
    cap=read("capability_guard.json",{})
    gate=read("discovery_gate.json",{})
    censor=read("censoring.json",{})
    behavior=read("inspection_behavior.json",{})
    adoption=read("helper_adoption.json",{})
    traj=read("trajectory_decomposition.json",{})
    success=read("token_to_success.json",{})
    hist=read("historical_token_summary.json",{})
    official=read("official_scores.json",{})
    routing=read("provider_routing.json",{})
    audit=read("analysis_audit.json",{})
    mechanism=read("mechanism_adjudication.json",{})
    replication=read("replication_decision.json",{})
    next_action=read("next_action.json",{})
    schemas=read("helper_schemas.json",{})
    primary=(OUT/"primary_runs.jsonl").read_text().splitlines() if (OUT/"primary_runs.jsonl").exists() else []
    reps=(OUT/"replication_runs.jsonl").read_text().splitlines() if (OUT/"replication_runs.jsonl").exists() else []
    contrasts=fx.get("contrasts",{})
    lines=["# Token-efficiency claim discovery", "",
           "This is a preregistered 2×2 **claim-discovery** experiment on a mechanism-enriched cohort. Architecture discovery remains closed; this is not a public claim-validation result.", "",
           f"Frozen specification: `{read('spec_hash.json',{}).get('sha256')}`. Product RC: `0.2.0rc1`, source/config `1aba3117…`, wheel `532e493f…`. Primary slots recorded: **{len(primary)}/60**. Replication slots: **{len(reps)}**.", "",
           "## Design and integrity", "",
           "| Arm | Strategy note | Helpers |", "| --- | --- | --- |", "| A | Neutral | Off |", "| B | Neutral | On |", "| C | Targeted-inspection salience | Off |", "| D | Targeted-inspection salience | On |", "",
           "Invisible runtime: Candidate A off; compiled substrate off; capture off; ordinary openpyxl in every arm. Helpers, when visible, are the frozen `lx_helpers` Python functions from the RC wheel using reference openpyxl. The provider tool schemas remain bash/view_xlsx/submit in all arms; H changes Python helper availability and its exact addendum. This preserves the frozen product interface.", "",
           f"The strategy notes are {notes.get('neutral_estimated_tokens')} and {notes.get('salience_estimated_tokens')} tokens under the recorded local `cl100k_base` estimate (difference {notes.get('difference')}); no model-native tokenizer count is claimed.", "",
           "**Neutral note**", "", "```text", notes.get("neutral",""), "```", "",
           "**Salience note**", "", "```text", notes.get("salience",""), "```", "",
           "**Helpers-on addendum**", "", "```text", notes.get("helper_on_addendum",""), "```", "",
           f"Population label: `{pop.get('label')}`. Selection used frozen H0 completion and broad-observation headroom only. All other tasks, including the independent seed-20261001 30-task reservation, were left unrun.", "",
           "## Historical lower-token observations", "",
           "These are experiment/cohort records, not 55 independent registry rows. They vary in token measure and are not pooled.", "",
           "| Experiment | Control | Treatment | Measure | Attribution defect |", "| --- | ---: | ---: | --- | --- |"]
    for r in hist.get("rows",[]):
        control=r.get("control_input_tokens") if r.get("control_input_tokens") is not None else r.get("control_total_tokens")
        treatment=r.get("treatment_input_tokens") if r.get("treatment_input_tokens") is not None else r.get("treatment_total_tokens")
        if control is None:continue
        lines.append(f"| {r['experiment']} ({r.get('population')}) | {fmt(control)} | {fmt(treatment)} | {r.get('token_measure')} | {str(r.get('known_attribution_problem') or r.get('censoring') or '')[:120].replace('|','/')} |")
    lines += ["", "## Primary provider-input-token contrasts", "",
              "Task-level paired ratios are the unit. Censored pairs are excluded from E2 paired contrasts; model noncompletion stays in E2 as an outcome and cannot be interpreted as a saving.", "",
              "| Contrast | E2 pairs | Median ratio | Median reduction | Geometric mean ratio | Bootstrap 95% CI | Favorable direction | E1 dual-valid pairs |",
              "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |"]
    for label in ("D_vs_A","C_vs_A","B_vs_A","D_vs_C","D_vs_B"):
        c=contrasts.get(label,{})
        e=c.get("E2_all_uncensored",{});e1=c.get("E1_dual_valid",{})
        lines.append(f"| {label.replace('_vs_',' / ')} | {e.get('n',0)} | {fmt(e.get('median_ratio'))} | {fmt(e.get('median_reduction_pct'))}% | {fmt(e.get('geometric_mean_ratio'))} | {e.get('bootstrap_95pct_ci_geometric_ratio')} | {e.get('treatment_lower_count',0)} | {e1.get('n',0)} |")
    lines += ["", "## Mechanism and capability", "",
              "| Arm | Calls | Input per call | Cumulative prior-observation bytes | Visible observation bytes | Broad views | Python calls | Helper mentions | Valid submissions | Tokens per valid submission |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for a in "ABCD":
        t=traj.get(a,{}) or {};b=behavior.get(a,{}) or {};s=success.get(a,{}) or {}
        lines.append(f"| {a} | {fmt(t.get('total_model_calls'))} | {fmt(t.get('input_tokens_per_call'))} | {fmt(t.get('cumulative_prior_observation_bytes'))} | {fmt(b.get('observation_bytes'))} | {fmt(b.get('broad_views'))} | {fmt(b.get('python_calls'))} | {fmt(b.get('helper_mention_calls'))} | {fmt(s.get('valid_submissions'))} | {fmt(s.get('tokens_per_valid_submission'))} |")
    lines += ["", f"Censoring by arm: `{json.dumps(censor.get('by_arm',{}),sort_keys=True)}`.", "",
              f"Actually served model/provider routing: `{json.dumps(routing,sort_keys=True)}`.", "",
              f"Capability: submitted `{cap.get('submitted')}`; valid `{cap.get('valid')}`; mean modification on valid outputs `{cap.get('mean_modification_valid_only')}`; mean regression `{cap.get('mean_regression_valid_only')}`. Formal equivalence: **NOT ESTABLISHED**.", "",
              f"Factorial mean log effects (secondary): `{json.dumps(fx.get('overall_mean_log_effects',{}),sort_keys=True)}`. Helper adoption: `{json.dumps(adoption.get('by_arm',{}),sort_keys=True)}`. Helper mentions alone do not prove backend invocation or mechanical displacement.", "",
              "## Task-level ratios", "", "| Task | A input | B input | C input | D input | D/A | A status | D status |", "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |"]
    for r in tasks:
        a,b,c,d=(r.get(x) or {} for x in "ABCD")
        ratio=(d.get("provider_input_tokens")/a.get("provider_input_tokens")) if a.get("provider_input_tokens") and d.get("provider_input_tokens") else None
        lines.append(f"| {r['task']} | {fmt(a.get('provider_input_tokens'))} | {fmt(b.get('provider_input_tokens'))} | {fmt(c.get('provider_input_tokens'))} | {fmt(d.get('provider_input_tokens'))} | {fmt(ratio)} | {a.get('status')} | {d.get('status')} |")
    lines += ["", "## Discovery adjudication", "",
              f"Primary verdict: **{gate.get('primary_verdict','EXPERIMENT_INCONCLUSIVE')}**. Gate details: `{json.dumps(gate,sort_keys=True)}`.", "",
              "The result is frozen regardless of direction. No representative holdout was run; any product refinement requires independent forensic diagnosis, a new RC/profile identity, a fresh discovery cohort, and a new preregistration.", "",
              "The strongest current external token claim remains none. Earlier lower-token totals are descriptive; a prompt effect here, if supported, would be an effect of the product-facing inspection strategy, not of the invisible runtime.", ""]
    lines += ["## Analysis audit and integrity", "",
              f"The preregistration and 60 primary outcomes remain frozen. The official scorer was not rerun for this correction. {audit.get('previously_misclassified_submitted_workbooks')} submitted workbooks were initially marked invalid because the evaluator's `error_message` also reports ordinary cell mismatches. All **39 submitted workbooks** reached the scorer as valid workbooks; this does not mean their edits were correct. E1, E3, censoring, and capability summaries were recomputed from the archived official scores.", "",
              f"The append-only provider ledger has {audit.get('raw_provider_call_rows')} successful call rows, including {audit.get('superseded_rows_from_interrupted_partial_block')} from an interrupted, incomplete block. The {audit.get('selected_provider_call_rows')} final call rows reconcile exactly to the frozen primary task totals. The raw ledger and primary hashes are preserved. An earlier historical-summary omission was corrected after preregistration without changing selection or the live design. See `analysis_audit.json`, `primary_freeze.json`, and `historical_normalization_correction.json`.", "",
              "The helper factor exposed the existing Python module and an 83-token local-estimate addendum; the provider tool schemas did **not** change. Thus H identifies that *combined availability-and-description profile*, not an isolated tool-schema effect. The S notes were matched at 38 local cl100k tokens each; this is not model-native token matching.", "",
              "## What the primary effect actually shows", "",
              "D/A has an E2 median ratio of **0.888** (11.2% lower) in 14 uncensored pairs, but the geometric-ratio bootstrap interval is **0.563–1.212**, crossing no effect. Only 8/14 pairs favor D. Removing two extreme Template pairs (`Template:01_05`, `Template:04_04`) changes the median to **1.034** and geometric ratio to **1.096** across the other 12 pairs. Template favors D; Financial_Model is near even; Debugging favors A. The preregistered robustness gate therefore fails.", "",
              "B/A is lower in this sample (median ratio **0.848**, 9/14 favorable; secondary geometric-ratio interval **0.502–0.939**), but helper execution occurred in only one B run and no D run. It cannot be described as helper-driven token saving. C/A is near neutral (median **0.972**) and D/C is modest (median **0.949**), both with wide intervals. The factorial interaction has a mean multiplicative ratio near **1.28** with a wide interval crossing no interaction.", "",
              "## Trajectory and observation mechanism", "",
              "D used **275 calls** versus A's **329**; aggregate input per call increased from **24,190** to **27,408** provider tokens. Across 14 uncensored D/A pairs, the geometric call-count ratio is **0.821** and per-call input ratio is **1.041**. Lower total input is principally fewer calls, not lighter calls. The paired path and per-arm cache/cost accounting are in `mechanism_adjudication.json`.", "",
              "Broad `view_xlsx` calls fell from **39 (A)** to **12 (D)**, but model-visible observation bytes rose from **957,611** to **1,008,265**, and Python stdout rose from **284,513** to **685,468** bytes. C likewise had fewer broad views but greater observation and Python-output burden than A. Cumulative prior-observation bytes summed across requests fell in D only because there were fewer requests; mean prior-observation bytes per D call was higher. The hypothesized `fewer fat workbook observations → smaller per-call input` path was **not observed**. The syntactic inspection classifiers do not establish semantic usefulness.", "",
              "One B run (`Financial_Model:09_02`) made four `lx_helpers.search` command calls: one failed and three returned exit status 0. Transcript review shows only the final command clearly printed cell hits; an earlier successful command iterated the result object's keys. The initial alias-blind classifier missed these calls. No D run invoked a helper. That B run also continued with broad Python output, so actual displacement of larger inspection work is not mechanically established. Helper availability may have changed the model's plan or trajectory without invocation, but this study cannot isolate that from the note itself.", "",
              "## Completion, scores, and commercial burden", "",
              "Valid submissions were **A 10, B 12, C 8, D 9**. D/A has two A-only and one D-only valid submission; C's `Template:06_02` even produced an exact workbook but never submitted it after consuming 827,565 input tokens. Model noncompletion is an outcome, not censoring. On eight dual-valid D/A pairs the median input ratio is 0.888, with a wide interval; modification deltas are mixed, including two lower-scoring low-token Template outputs. No formal capability equivalence or capability-preserving token claim follows.", "",
              "E3 provider input tokens per valid submission: **A 795,849; B 592,731; C 1,042,557; D 837,462**. This discovery-only ratio uses all attempted-slot input and is not a prospective cost estimate. D had fewer total reported input tokens than A but **more uncached input tokens** (856,031 vs 788,581), more output tokens (165,158 vs 130,269), and higher provider-reported cost in these calls ($0.295 vs $0.281). No cost-saving claim is supported.", "",
              f"No targeted replication was run. Eligible pathologies and the decision are recorded in `replication_decision.json`: {replication.get('reason_not_run')}", "",
              "## My findings and opinion", "",
              "The most diagnostic result is the mismatch between the visible behavior shift and the proposed token path. The salience wording changed *which interface* carried inspection—fewer `view_xlsx` calls, more Python output—but did not reduce bytes shown to the model or input per call. That is a useful product-design finding, but it is not the advertised token mechanism.", "",
              "The B/A reduction deserves forensic attention because it appeared without broad helper adoption and with better completion counts. I would treat it as a possible effect of the helper *description or availability* on trajectory planning, not as evidence that the helper implementation saved tokens. It may also be stochastic: two Template tasks strongly influence the paired result, and the cohort was selected for headroom. The current four-arm design cannot distinguish these explanations.", "",
              "My verdict is deliberately conservative: `TOKEN_EFFECT_TRAJECTORY_NOISE` means the combined D/A product-surface effect is not stable or mechanistically identified here; it does **not** prove that a future, narrower integration cannot save tokens. The capability guard did not affirmatively pass, but the small discordances and mixed scores do not establish a reproducible treatment degradation either. The first loss boundary is the absence of a lower per-call observation burden, followed by concentration in two Template trajectories.", "",
              "## Next action", "",
              f"{next_action.get('single_next_action')} The 30 reserved validation tasks remain untouched. A later refinement, if justified, needs a new integration-profile identity, fresh discovery tasks, and a new preregistration; do not tune this RC against the reserved holdout.", "",
              "## Summary of findings", "",
              "The combined product-facing profile produced an 11.2% lower median provider-input count in the uncensored discovery pairs, but that result is concentrated in two Template tasks, lacks a stable cross-family effect, and has no affirmative capability guard. Salience reduced broad views without reducing observation bytes or per-call input. Helper use occurred in one B run and none in D, so helper execution is not the identified cause. The primary verdict is `TOKEN_EFFECT_TRAJECTORY_NOISE`; no token or cost claim is ready. Independent Astra review of the frozen packet is the next step, with the representative holdout still untouched.", ""]
    (ROOT/"research/reports/TOKEN_EFFICIENCY_CLAIM_DISCOVERY_REPORT.md").write_text("\n".join(lines))
    packet=["# Astra token diagnosis packet", "",
            "Independent forensic review only. GPT-6 Astra did not run as an experimental arm and this packet is not evidence that any claim passes. Do not inspect, tune against, or run the reserved validation cohort.", "",
            f"Spec SHA-256: `{read('spec_hash.json',{}).get('sha256')}`. Product RC hashes and exact design are in `research/history/token_claim_discovery/preregistered_spec.json`, `exact_notes.json`, `helper_schemas.json`, `arm_configs.json`, `selection_manifest.json`, and `run_order.json`.", "",
            "The exact notes are:", "", "```text", "NEUTRAL: " + notes.get("neutral",""), "SALIENCE: " + notes.get("salience",""), "HELPERS ON: " + notes.get("helper_on_addendum",""), "```", "",
            f"Population: `{pop.get('tasks')}`. Primary slots: {len(primary)}/60. Replications: {len(reps)}. Censoring: `{censor.get('by_arm')}`. Primary verdict: `{gate.get('primary_verdict')}`.", "",
            "The provider tool schemas are identical in all arms: see `helper_schemas.json`. The helper factor is the frozen Python module, import availability, and exact signature addendum. This is a possible limitation for a claim about directly exposed tool schemas.", "",
            "## Task-level token table", "", "| Task | A | B | C | D |", "| --- | ---: | ---: | ---: | ---: |"]
    for r in tasks:
        packet.append("| " + r["task"] + " | " + " | ".join(fmt((r.get(a) or {}).get("provider_input_tokens")) for a in "ABCD") + " |")
    packet += ["", "## Contrasts, capability, mechanism, and contradictions", "", "```json",
               json.dumps({"factorial":fx,"capability":cap,"censoring":censor,"routing":routing,"inspection":behavior,
                           "adoption":adoption,"trajectory":traj,"token_to_success":success,
                           "replication_runs":reps},indent=2), "```", "",
               "Exact requests, responses, provider usage, local request decomposition, model-visible observations, official scores, and all primary and replication records are linked by the manifest in `research/history/token_claim_discovery/astra_packet_manifest.json`. Provider-reported token counts and local estimates are never substituted for one another.", "",
               "Known limitations and contradictions include prior lower-token totals with completion/censoring confounding; treatment note overhead; helper adoption endogeneity; provider latency and served-model routing; model noncompletion; local tokenizer mismatch; and any task-level sign reversals shown above. The reserved validation tasks were not inspected for treatment outcomes.", ""]
    packet += ["## Frozen run order", "", "| Task | Slot and arm sequence |", "| --- | --- |"]
    by_task={}
    for slot in order.get("slots",[]):
        by_task.setdefault(slot["task"],[]).append(f"{slot['slot']}:{slot['arm']}")
    for task, sequence in by_task.items():
        packet.append(f"| {task} | {', '.join(sequence)} |")
    packet += ["", "## Exact provider tool schemas and helper contract", "", "```json",
               json.dumps(schemas,indent=2,sort_keys=True), "```", "",
               "## Request decomposition and lineage", "",
               f"The {audit.get('selected_provider_call_rows')} final provider calls reconcile to the primary ledger. The raw append-only ledger retains {audit.get('superseded_rows_from_interrupted_partial_block')} superseded successful calls from an interrupted partial block. `provider_usage_raw.jsonl` is frozen; `provider_usage.jsonl` is the derived selected-call view. Exact request segmentation is in `request_decomposition_exact.jsonl`, with provider counts separately in `provider_usage.jsonl`. Local cl100k estimates are not substituted for provider counts. All archived successful requests were decomposed: {audit.get('all_archived_successful_requests_decomposed')}.", "",
               "| Arm | Calls | Prior observation bytes summed over calls | Mean prior-observation bytes/call | Reported cached input | Input minus cached | Provider-reported cost USD |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    cache=mechanism.get("per_arm_caching_and_cost",{})
    for a in "ABCD":
        t=traj.get(a,{}) or {};c=cache.get(a,{})
        packet.append(f"| {a} | {fmt(t.get('total_model_calls'))} | {fmt(t.get('cumulative_prior_observation_bytes'))} | {fmt(t.get('mean_prior_observation_bytes_per_call'))} | {fmt(c.get('reported_cached_input_tokens'))} | {fmt(c.get('input_tokens_minus_reported_cached'))} | {fmt(c.get('provider_reported_cost_usd'))} |")
    packet += ["", "## Mechanism and score contradictions", "",
               f"D/A after omitting two extreme Template tasks: `{mechanism.get('D_vs_A_without_two_extreme_template_tasks')}`. Paired trajectory decomposition: `{mechanism.get('paired_trajectory_decomposition')}`.", "",
               f"Helper execution audit: `{mechanism.get('helper_audit')}`. One alias-imported helper user was missed by the first syntax detector, then corrected from frozen events. A/B/C/D broad views were {', '.join(str(behavior.get(a,{}).get('broad_views')) for a in 'ABCD')}; model-visible observation bytes were {', '.join(str(behavior.get(a,{}).get('observation_bytes')) for a in 'ABCD')}. Lower broad-view count did not yield lower observation burden.", "",
               "D/A completion discordance: two A-only and one D-only valid submission. D/A low-token Template outputs include lower modification scores. B/A is favorable as a secondary contrast but has actual helper use in only one B task and none in D. C/A includes an extreme 22.7× Template trajectory in which the workbook was exact but no submit occurred. Provider routing and caching differ stochastically by arm despite a common policy. These are contradictions to any simple helper or salience token-saving story.", "",
               f"Replication decision: `{replication}`. Historical normalization correction and interrupted partial-block recovery are preserved as distinct audit records. The future validation reservation remains untouched.", "",
               "## My forensic read", "",
               "I expect the earliest failure of the intended claim to be the proposed observation-burden mediator: per-call input and visible observation bytes did not fall. The combined median then depends on two Template trajectories and lacks a positive capability guard. A narrower note/availability effect is possible, particularly in B/A, but helper execution is too sparse to credit and the extra helper addendum is confounded with availability. This is a hypothesis for independent diagnosis, not a revised positive result.", "",
               "## Questions for independent reviewer", "",
               "1. Is the claimed token mechanism actually identified by this design?",
               "2. Which contrast provides the strongest causal evidence?",
               "3. Is any apparent token saving explained by completion, censoring, trajectory length, or call-count differences?",
               "4. Does the salience note create a legitimate product effect or merely an experimental prompt artifact?",
               "5. Do helper calls actually displace larger inspection work?",
               "6. Is the D-vs-A effect decomposable into salience, helpers, and interaction?",
               "7. Is the discovery gate too weak, too strong, or correctly scoped?",
               "8. What is the earliest loss boundary if the claim fails?",
               "9. What is the smallest product refinement justified by the evidence?",
               "10. What should explicitly NOT be changed?",
               "11. What fresh experiment would discriminate the leading explanations?",
               "12. Is representative holdout validation justified?", ""]
    packet.append(AFFORDANCE_REVIEW_REQUIREMENT)
    (ROOT/"research/reports/ASTRA_TOKEN_DIAGNOSIS_PACKET.md").write_text("\n".join(packet))
    sources=[p for p in OUT.iterdir() if p.is_file() and p.name!="astra_packet_manifest.json"]
    sources.extend([ROOT/"research/reports/TOKEN_EFFICIENCY_CLAIM_DISCOVERY_REPORT.md",ROOT/"research/reports/ASTRA_TOKEN_DIAGNOSIS_PACKET.md",ROOT/"research/reports/CLAIM_BACKLOG.md"])
    manifest={"role":"independent forensic review only; not treatment evidence","sources":{str(p.relative_to(ROOT)):sha(p) for p in sources},
              "request_archives":{str(p.relative_to(ROOT)):sha(p) for p in OUT.glob("runs/primary/*/requests/*.json")},
              "primary_runs":len(primary),"replication_runs":len(reps),"future_holdout_untouched":True}
    (OUT/"astra_packet_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print("wrote reports and packet")


if __name__=="__main__":main()
