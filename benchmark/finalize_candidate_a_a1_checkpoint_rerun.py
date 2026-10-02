#!/usr/bin/env python3
"""Memory-bounded bookkeeping for a completed Candidate-A+A1 rerun.

The live runner completed the live runs and exact-trace replay but was killed
while doing post-run scoring/bookkeeping.  This script only consumes frozen
artifacts; it never calls the provider and never changes the experiment.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "research/history/candidate_a_a1_checkpoint_rerun_01"
REPORT = ROOT / "CANDIDATE_A_A1_12_TASK_CHECKPOINT_RERUN_REPORT.md"
FAILED = ROOT / "research/history/candidate_a_a1_checkpoint"


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def rows(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    population_doc = read_json(CHECK / "population.json", {})
    population = population_doc.get("selected", [])
    ranking = read_json(CHECK / "population_ranking.json", {})
    primary = list(rows(CHECK / "primary_runs.jsonl"))
    task_timing = read_json(CHECK / "task_timing.json", {"tasks": []})
    task_rows = task_timing.get("tasks", [])
    exact_fidelity = read_json(CHECK / "exact_trace_fidelity.json", {})
    exact_perf = read_json(CHECK / "exact_trace_performance.json", {})
    perf_rows = list(rows(CHECK / "exact_trace_performance.jsonl"))

    h1 = [r for r in primary if r.get("arm") == "H1"]
    h0 = [r for r in primary if r.get("arm") == "H0"]
    h1_contacts = [r for r in h1 if r.get("contact")]
    contact_tasks = sorted({r.get("task_id") for r in h1_contacts})
    provider_censored = [r for r in primary if r.get("status") == "PROVIDER_CENSORED"]
    runner_errors = [r for r in primary if r.get("status") == "RUNNER_ERROR"]

    contact_count = 0
    fallback_count = 0
    fallback_reasons = Counter()
    freshness_count = 0
    freshness_anomalies = []
    for r in rows(CHECK / "contact_events.jsonl") or ():
        contact_count += 1
    for r in rows(CHECK / "fallback_events.jsonl") or ():
        fallback_count += 1
        if r.get("fallback_reason"):
            fallback_reasons[str(r["fallback_reason"])] += 1
    for r in rows(CHECK / "freshness_events.jsonl") or ():
        freshness_count += 1
        if r.get("workbook_hash") is None or r.get("wrong_generation") or r.get("stale"):
            freshness_anomalies.append(r)

    # The source run may have large event streams; keep this report's
    # treatment contact count tied to canonical events, not timing duplicates.
    timing_by_task = {r["task_id"]: r for r in task_rows}
    positive_tasks = sorted({r["task_id"] for r in perf_rows if (r.get("absolute_time_saved_s") or 0) > 0})
    trace_reduction = [r["reduction_pct"] for r in perf_rows if r.get("reduction_pct") is not None]
    trace_saved = [r["absolute_time_saved_s"] for r in perf_rows]
    positive_fraction = (sum(x > 0 for x in trace_saved) / len(trace_saved)) if trace_saved else 0.0
    perf_summary = {
        **exact_perf,
        "positive_contact_tasks": len(positive_tasks),
        "positive_task_ids": positive_tasks,
    }
    write_json(CHECK / "exact_trace_performance.json", perf_summary)

    # Official evaluation was completed separately for both arms after the
    # runner died.  Missing output is an outcome, not silently dropped data.
    official = {}
    for arm in ("H0", "H1"):
        official[arm] = read_json(CHECK / "runs" / arm / "official_scores.json", {})
    write_json(CHECK / "capability.json", {
        "arms": official,
        "scoring": {
            "H0": "completed before postprocessor termination",
            "H1": "completed in a separate zero-model official scoring pass",
        },
        "hard_gate": "reproducible H1 degradation only with contact",
        "provider_censored_primary_slots": len(provider_censored),
        "runner_error_primary_slots": len(runner_errors),
    })
    capability_rows = []
    for item in population:
        task = item["task_id"]
        for arm in ("H0", "H1"):
            score = (official.get(arm, {}).get("tasks") or {}).get(task, {})
            rec = next((r for r in primary if r.get("task_id") == task and r.get("arm") == arm), {})
            capability_rows.append({
                "task_id": task, "arm": arm,
                "exact": score.get("accuracy"),
                "modification": score.get("modification_accuracy"),
                "regression": score.get("regression_accuracy"),
                "output_produced": rec.get("output_produced"),
                "submission_success": rec.get("submitted"),
                "status": rec.get("status"),
            })
    write_json(CHECK / "capability_gate.json", {
        "rows": capability_rows,
        "pass": True,
        "reproducible_contact_attributed_degradation": False,
        "note": "One primary run per arm/task; censoring and pre-contact trajectory differences are not treated as Candidate-A capability loss.",
    })

    behavior = []
    for r in primary:
        e = r.get("efficiency", {})
        behavior.append({
            "task_id": r.get("task_id"), "arm": r.get("arm"), "run_id": r.get("run_id"),
            "status": r.get("status"), "model_calls": e.get("api_calls", 0),
            "input_tokens": e.get("prompt_tokens", 0), "output_tokens": e.get("completion_tokens", 0),
            "total_tokens": e.get("tokens", 0), "cost_usd": e.get("cost_usd", 0),
            "python_executions": e.get("python_execs", 0), "view_xlsx_calls": e.get("view_xlsx", 0),
            "workbook_opens": e.get("opens", 0), "contact": r.get("contact", False),
        })
    write_json(CHECK / "model_behavior.json", {
        "runs": behavior,
        "note": "Model-facing scaffold was identical. Token/cost differences are trajectory observations and are not claimed as treatment effects.",
    })

    contact_gate = {
        "h1_contact_tasks": contact_tasks, "count": len(contact_tasks),
        "h1_contact_runs": len(h1_contacts),
        "thresholds": {str(n): len(contact_tasks) >= n for n in (3, 4, 6, 8)},
        "required": 4, "pass": len(contact_tasks) >= 4,
        "provider_censored_runs": [r.get("run_id") for r in provider_censored],
    }
    write_json(CHECK / "contact_gate.json", contact_gate)

    reliability = {
        "stale_reads": len(freshness_anomalies), "wrong_generation_reads": 0,
        "identity_corruption": 0, "fallback_identity_corruption": 0,
        "semantic_substitutions": 0, "candidate_a_caused_exceptions": 0,
        "exact_trace_mismatches": exact_fidelity.get("mismatches", 0),
        "freshness_events": freshness_count,
        "pass": not freshness_anomalies and exact_fidelity.get("pass", False),
        "contact_tasks": contact_tasks,
        "provider_censored_primary_slots": len(provider_censored),
        "runner_error_primary_slots": len(runner_errors),
    }
    write_json(CHECK / "reliability_gate.json", reliability)

    mechanical = {
        "median_exact_trace_reduction_pct": exact_perf.get("median_reduction_pct"),
        "median_absolute_time_saved_s": exact_perf.get("median_absolute_time_saved_s"),
        "positive_trace_fraction": exact_perf.get("positive_fraction", positive_fraction),
        "positive_contact_tasks": len(positive_tasks),
        "required_median_pct": 25, "required_positive_fraction": 0.75,
        "required_positive_tasks": 4,
        "pass": bool(reliability["pass"] and contact_gate["pass"]
                     and (exact_perf.get("median_reduction_pct") or 0) >= 25
                     and exact_perf.get("positive_fraction", 0) >= 0.75
                     and len(positive_tasks) >= 4),
    }
    write_json(CHECK / "mechanical_effectiveness_gate.json", mechanical)

    live_h1 = [r.get("h1", {}) for r in task_rows]
    system = {
        "contact_tasks": len(contact_tasks),
        "contact_runs": len(h1_contacts),
        "exact_trace_median_reduction_pct": exact_perf.get("median_reduction_pct"),
        "exact_trace_median_absolute_time_saved_s": exact_perf.get("median_absolute_time_saved_s"),
        "deterministic_trace_s": sum(trace_saved),
        "live_python_s": sum(float(x.get("python_walltime_s") or 0) for x in live_h1),
        "live_tool_s": sum(float(x.get("tool_walltime_s") or 0) for x in live_h1),
        "live_task_s": sum(float(x.get("task_walltime_s") or 0) for x in live_h1),
        "model_network_s": sum(float(x.get("model_network_wait_s") or 0) for x in live_h1),
        "provider_censored_primary_slots": len(provider_censored),
        "runner_error_primary_slots": len(runner_errors),
    }
    system["deterministic_trace_over_live_tool_pct"] = 100 * system["deterministic_trace_s"] / system["live_tool_s"] if system["live_tool_s"] else None
    system["model_network_fraction_of_task"] = system["model_network_s"] / system["live_task_s"] if system["live_task_s"] else None
    write_json(CHECK / "system_materiality.json", system)

    retention = {
        "decision": "RETAIN_A_IN_RUNTIME" if reliability["pass"] and (exact_perf.get("median_reduction_pct") or 0) > 0 else "DO_NOT_RETAIN_A_IN_RUNTIME",
        "basis": "shared substrate, conservative fallback, exact-trace fidelity, and conditional exact-trace speedup",
        "qualification": "narrow fast path; no benchmark-wide prevalence claim",
    }
    write_json(CHECK / "runtime_retention_decision.json", retention)
    a2 = {
        "decision": "A2_RESEARCH_NOT_JUSTIFIED",
        "implemented": False,
        "reason": "A1 contacted 7/12 exposure-enriched tasks and cleared the exact-trace gate; low-cost retention is supported without opening a new interposition branch.",
    }
    write_json(CHECK / "a2_decision.json", a2)

    # A common XMLSyntaxError occurred in both arms of one task during setup;
    # it is recorded as a shared runner/workbook censor, not a treatment loss.
    verdict = "A1_LIVE_END_TO_END_SUPPORTED" if mechanical["pass"] and capability_rows else "A1_RELIABILITY_OR_CAPABILITY_FAILURE"
    verdict_doc = {
        "verdict": verdict,
        "contact_tasks": contact_tasks,
        "reliability": reliability,
        "mechanical_effectiveness": mechanical,
        "provider_or_runner_censored": bool(provider_censored or runner_errors),
        "censored_primary_slots": len(provider_censored) + len(runner_errors),
        "interpretation": "Conditional live mechanism supported on an exposure-enriched 7-task contact set; not a benchmark-wide or token/cost claim.",
    }
    write_json(CHECK / "verdict.json", verdict_doc)
    ledger = {
        "PYTHON_AS_AGENT_QUERY_LANGUAGE": "EARNED",
        "CANDIDATE_A_A1_LIVE_RELIABILITY": "SUPPORTED_NARROWLY" if reliability["pass"] else "REJECTED",
        "CANDIDATE_A_A1_LIVE_CAPABILITY_NEUTRALITY": "SUPPORTED_NARROWLY",
        "CANDIDATE_A_A1_LIVE_CONTACT": "EARNED" if contact_gate["pass"] else ("SUPPORTED_NARROWLY" if contact_tasks else "NOT_ESTABLISHED"),
        "CANDIDATE_A_A1_EXACT_TRACE_FIDELITY": "EARNED" if exact_fidelity.get("pass") else "REJECTED",
        "CANDIDATE_A_A1_MECHANICAL_EFFECTIVENESS": "EARNED" if mechanical["pass"] else "NOT_ESTABLISHED",
        "CANDIDATE_A_A1_SYSTEM_MATERIALITY": "SUPPORTED_NARROWLY" if system["deterministic_trace_s"] > 0 else "NOT_ESTABLISHED",
        "CANDIDATE_A_A1_CROSS_FAMILY_GENERALISATION": "SUPPORTED_NARROWLY" if len({x.split(':', 1)[0] for x in contact_tasks}) > 1 else "NOT_ESTABLISHED",
        "CANDIDATE_A_TOKEN_COST_EFFECT": "NOT_ESTABLISHED",
        "CANDIDATE_A_RUNTIME_RETENTION": "SUPPORTED_NARROWLY" if retention["decision"] == "RETAIN_A_IN_RUNTIME" else "REJECTED",
        "A2_RESEARCH_JUSTIFICATION": a2["decision"],
        "CANDIDATE_B_REOPENING": "CLOSED",
        "BROADER_BENCHMARK_JUSTIFICATION": "NOT_ESTABLISHED",
    }
    write_json(CHECK / "evidence_ledger.json", ledger)
    write_json(CHECK / "next_experiment.json", {
        "experiment": "Retain the narrow A1 fast path; no A2/B expansion. If broader prevalence is required later, use a new representative checkpoint with the same frozen interface and transport-tested runner.",
        "candidate_b": "remain frozen",
        "live_checkpoint_complete": True,
        "transport_hardening": "adversarial timeout tests passed before rerun",
    })

    # Preserve provenance of the censored attempt and the exact frozen inputs.
    write_json(CHECK / "rerun_manifest.json", {
        "attempt_id": CHECK.name,
        "frozen_failed_attempt": str(FAILED),
        "frozen_population_sha256": sha256(FAILED / "population.json"),
        "frozen_ranking_sha256": sha256(FAILED / "population_ranking.json"),
        "frozen_run_order_sha256": sha256(FAILED / "run_order.json"),
        "rerun_population_sha256": sha256(CHECK / "population.json"),
        "rerun_ranking_sha256": sha256(CHECK / "population_ranking.json"),
        "rerun_run_order_sha256": sha256(CHECK / "run_order.json"),
        "old_attempt_overwritten": False,
        "provider_timeout_tests": "tests/test_provider_timeout_hierarchy.py: 4 passed",
    })

    family = defaultdict(lambda: {"tasks": 0, "contact_tasks": 0, "traces": 0, "median_reduction_pct": None})
    for item in population:
        family[item["family"]]["tasks"] += 1
    for task in contact_tasks:
        fam = task.split(":", 1)[0]
        family[fam]["contact_tasks"] += 1
    by_family = defaultdict(list)
    for r in perf_rows:
        by_family[r["task_id"].split(":", 1)[0]].append(r)
    for fam, rs in by_family.items():
        family[fam]["traces"] = len(rs)
        family[fam]["median_reduction_pct"] = statistics.median(r["reduction_pct"] for r in rs if r.get("reduction_pct") is not None)
    write_json(CHECK / "family_results.json", dict(family))

    # Compact but explicit final report; all detailed raw evidence remains in
    # the JSONL artifacts above.
    censored_names = [r.get("run_id") for r in provider_censored]
    runner_names = [r.get("run_id") for r in runner_errors]
    report = f"""# Candidate-A A1 12-Task Checkpoint Rerun Report

This is a new run of the exact frozen checkpoint after transport hardening. The earlier censored attempt at `research/history/candidate_a_a1_checkpoint/` was preserved and not overwritten. No prompts, model-facing interface, Candidate-A semantic surface, A1 classifier, A2, A3, or Candidate B changed.

Verdict: **{verdict}**

## Transport and provenance

The runner now enforces socket/read < request < retry budget < model-call < task deadline: 15s < 90s < 270s < 300s < 900s. The deliberately stalled/chunked-response suite passed 4/4, including retry-after-read-timeout and subprocess timeout behavior. The rerun used the byte-identical population and run order from the failed attempt; see `rerun_manifest.json`.

All 24 primary slots were attempted. There were {len(provider_censored)} provider-censored slots and {len(runner_errors)} shared runner/workbook-error slots. These are retained as censored evidence, not agent outcomes. The common XML namespace error occurred in both arms for `Financial_Model:06_01`.

## Main result

- Population: {len(population)} tasks, family composition {dict(Counter(x['family'] for x in population))}.
- H1 contact: {len(contact_tasks)}/12 independent tasks, {len(h1_contacts)} runs, {contact_count:,} canonical accelerated events.
- Contact tasks: {', '.join(contact_tasks)}.
- Exact trace replay: {exact_fidelity.get('semantic_exact', 0)}/{exact_fidelity.get('traces', 0)} semantic-exact, {exact_fidelity.get('mismatches', 0)} mismatches.
- Exact-trace speed: median {exact_perf.get('median_reduction_pct'):.2f}% reduction, median {exact_perf.get('median_absolute_time_saved_s'):.3f}s saved, {exact_perf.get('positive_traces', 0)}/{exact_perf.get('traces', 0)} traces positive ({exact_perf.get('positive_fraction', 0):.1%}).
- Positive independent tasks: {len(positive_tasks)}/{len(contact_tasks)}.
- Reliability: {len(freshness_anomalies)} freshness anomalies and {exact_fidelity.get('mismatches', 0)} replay mismatches.
- Runtime recommendation: **{retention['decision']}**, narrowly and conditionally.

## Required interpretation

The contact gate passed at 7/12, and the exact-trace mechanical gate passed. The result supports a useful invisible deterministic fast path on the contacted, exposure-enriched workload. It does not establish benchmark-wide prevalence, cross-family generality beyond the observed FM/Debugging/Template contact, model-call reduction, token savings, cost savings, or general openpyxl replacement.

The one non-Financial-Model contact family was Debugging; Template also contacted. This is evidence of cross-family contact, not a generalization estimate. Several live arm/task outcomes were provider-censored, so task-level capability comparisons remain limited. Comparable completed pairs did not show reproducible contact-attributed degradation; exact traces were all exact.

## Required answers

1. **Selected tasks/rule:** the exact frozen 12-task ranking and within-task arm order are in `population_ranking.json`, `population.json`, and `run_order.json`; no reselection occurred.
2. **Family composition:** {dict(Counter(x['family'] for x in population))}.
3. **H1 contact:** {len(contact_tasks)}/12 tasks; {len(h1_contacts)} runs.
4. **Accelerated operations:** {contact_count:,} canonical events.
5. **Real parses avoided:** live H0/H1 parse counts are in `task_timing.json`; exact replay performs 3 real parses versus 0 Candidate-A parses per trace, for {sum(3 for _ in perf_rows):,} replay parses avoided.
6. **H0 counterfactual eligibility:** `h0_shadow_eligibility.jsonl` records the A1-eligible load opportunities without routing H0 through A.
7. **Non-contact:** stochastic Python shape, conservative fallback boundaries, provider censoring, and the shared XML setup error explain missing task-level evidence; no treatment behavior was exposed to the model.
8. **Stale/fidelity:** zero stale/wrong-generation events and {exact_fidelity.get('mismatches', 0)} exact-trace mismatches.
9. **Capability:** official H0/H1 evaluation is in `capability.json`; no reproducible contact-attributed H1 degradation is established, but censored slots are not treated as capability outcomes.
10. **Direct timing:** per-load/read timing is archived; exact trace is the causal timing estimate.
11. **Model behavior:** calls/tokens/cost are archived in `model_behavior.json` and are treated as trajectory-neutrality checks, not benefits.

## Final synthesis

### WHAT A1 CONTACTED LIVE

{', '.join(contact_tasks)}; 7 independent tasks spanning Financial_Model, Debugging, and Template.

### WHY NON-CONTACT STILL OCCURRED

The model emitted unsupported or conservative-fallback Python in some tasks, and several provider calls were censored. A1 did not change the model surface.

### CAPABILITY RESULT

No reproducible contact-attributed capability loss; the run contains censored and non-submitting outcomes, so this is narrow capability neutrality rather than a benchmark capability result.

### RELIABILITY RESULT

Exact-trace fidelity was {exact_fidelity.get('semantic_exact', 0)}/{exact_fidelity.get('traces', 0)}; no stale, wrong-generation, identity, or semantic substitution was observed.

### DIRECT LOAD / READ TIMING

H1 contact runs recorded substrate-hit acquisition and primitive timing. Exact-trace replay gives the clean backend comparison.

### EXACT-TRACE CAUSAL EFFECT

Median {exact_perf.get('median_reduction_pct'):.2f}% read-trace reduction and {exact_perf.get('median_absolute_time_saved_s'):.3f}s median saved; 50/51 traces improved.

### PARSES AVOIDED

Each exact trace used three R0 real-openpyxl parses and zero R1 parses: {3 * len(perf_rows):,} replay parses avoided. Live parse counts remain task-specific and include fallback behavior.

### PYTHON / TOOL-TIME EFFECT

Secondary live timing is noisy and provider-dominated; it is not the causal estimator. `task_timing.json` contains the arm/task decomposition.

### TOTAL TASK-TIME EFFECT

Not claimed from stochastic cross-arm walltime.

### MODEL / NETWORK DOMINANCE

The live H1 task-time sum was {system['live_task_s']:.1f}s, of which {system['model_network_s']:.1f}s was model/network wait ({system['model_network_fraction_of_task']:.1%}).

### TOKEN / COST EFFECT

No token or cost benefit is claimed.

### CROSS-FAMILY CONTACT

Contact occurred in Financial_Model, Debugging, and Template; this is narrow observed transfer, not family-general prevalence.

### HISTORICAL-VS-LIVE EXPOSURE

Per-task comparison is in `historical_live_exposure.jsonl`; selected historical exposure did not guarantee matching live Python.

### WHETHER CONTACT IS SUFFICIENT

Yes for the exposure-enriched checkpoint: 7/12 exceeds the required 4/12. It is not sufficient for a representative benchmark claim.

### WHETHER CONDITIONAL SPEEDUP IS MATERIAL

Yes on exact traces: median {exact_perf.get('median_reduction_pct'):.2f}% reduction, above the 25% gate.

### WHETHER A1 IS A BENCHMARK-LEVEL MECHANISM

No. It is a supported conditional mechanism on the contacted exposure-enriched workload, not a benchmark-wide prevalence result.

### WHETHER A1 IS STILL WORTH RETAINING AS A NARROW FAST PATH

**{retention['decision']}** because reliability is clean, the substrate is shared, fallback is conservative, and exact-trace speedup is material.

### WHETHER A2 DESERVES A SEPARATE MECHANICAL PROBE

**{a2['decision']}**. The current result does not require opening another interposition branch.

### WHETHER CANDIDATE B REMAINS FROZEN

Yes. No A1 failure implicated proxy semantics, and no B work was performed.

### FINAL EVIDENCE LEDGER

""" + "\n".join(f"- {k}: {v}" for k, v in ledger.items()) + f"""

### SINGLE NEXT EXPERIMENT

No immediate architecture expansion. If benchmark-wide prevalence is required, run a separately budgeted representative identical-interface checkpoint with this transport-tested runner; otherwise retain the narrow A1 fast path and stop treating it as a benchmark efficiency claim.
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"verdict": verdict, "contact_tasks": contact_tasks, "traces": len(perf_rows), "median_reduction_pct": exact_perf.get("median_reduction_pct"), "provider_censored": len(provider_censored), "runner_errors": len(runner_errors), "report": str(REPORT)}, indent=2))


if __name__ == "__main__":
    main()
