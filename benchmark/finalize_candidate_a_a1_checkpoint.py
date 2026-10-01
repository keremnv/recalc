#!/usr/bin/env python3
"""Finalize a censored Candidate-A+A1 checkpoint without inventing outcomes.

The live runner was interrupted while an OpenRouter response was stalled.  This
postprocessor preserves the completed H0 run and the partial H1 runtime events,
marks the remaining live evidence censored, and writes all required artifacts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "candidate_a_a1_checkpoint"
REPORT = ROOT / "CANDIDATE_A_A1_12_TASK_CHECKPOINT_REPORT.md"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    population_doc = read_json(CHECK / "population.json", {})
    ranking_doc = read_json(CHECK / "population_ranking.json", {})
    population = population_doc.get("selected", [])
    ranking = ranking_doc.get("ranking", [])
    all_tasks = [x.get("task_id") for x in population]
    completed_h0 = read_json(CHECK / "runs/H0/Financial_Model-07_01/run_record.json", {})
    partial_h1_run_id = "primary_02_Financial_Model_07_01_H1"
    partial_h1_work = CHECK / "work" / partial_h1_run_id
    h1_event_files = sorted((partial_h1_work / "runtime_events").glob("call_*.jsonl"))
    h1_events: list[dict[str, Any]] = []
    for path in h1_event_files:
        h1_events.extend(read_jsonl(path))
    h1_runtime_events = [x for x in h1_events if x.get("event") == "candidate_operation"]
    h1_loads = [x for x in h1_runtime_events if x.get("operation") == "load_workbook"]
    h1_fallbacks = [x for x in h1_runtime_events if x.get("status") in {"PREDECLARED_FALLBACK", "RUNTIME_FALLBACK", "FAIL_CLOSED"}]
    h0_archive = CHECK / "runs/H0/Financial_Model-07_01"
    h0_events = []
    for path in sorted((CHECK / "work/primary_01_Financial_Model_07_01_H0/runtime_events").glob("call_*.jsonl")):
        h0_events.extend(read_jsonl(path))

    # The runner never reached its post-run write for the censored H1 call.  A
    # censored placeholder is explicit and is not counted as a completed run.
    h1_censored = {
        "task_id": "Financial_Model:07_01", "arm": "H1", "run_id": partial_h1_run_id,
        "status": "PROVIDER_OR_RUNNER_CENSORED", "submitted": False,
        "completed": False, "contact": False, "contact_count": 0,
        "partial_runtime_event_count": len(h1_runtime_events),
        "partial_load_count": len(h1_loads),
        "censoring": {"cause": "provider response stalled during chunked HTTP read", "runner_interrupt": True,
                      "last_completed_runtime_event": h1_event_files[-1].name if h1_event_files else None},
        "workdir": str(partial_h1_work),
    }
    primary = [completed_h0, h1_censored]
    write_jsonl(CHECK / "primary_runs.jsonl", primary)
    write_jsonl(CHECK / "replication_runs.jsonl", [])

    spec = {
        "experiment": "larger identical-interface Candidate-A+A1 live checkpoint",
        "model_inference_requested": True, "model_surface_changed": False,
        "semantic_surface_changed": False, "a1_classifier_frozen": True,
        "requested_primary_runs": 24, "selected_tasks": all_tasks,
        "selection_rule": "top 12 by A1-eligible historical executions, repeated-open surplus, safe primitive reads, historical deterministic read/open time, task ID",
        "arms": {"H0": "ordinary openpyxl; shared substrate common", "H1": "same scaffold with frozen Candidate-A+A1 acceleration"},
        "shared_substrate": True, "candidate_b": "frozen",
        "censoring": {"valid_completed_primary_runs": 1, "partial_runs": 1, "unstarted_primary_runs": 22,
                       "reason": "provider response stalled beyond practical observation window; process interrupted; no live outcomes fabricated"},
    }
    write_json(CHECK / "spec.json", spec)

    # Preserve the completed H0 telemetry and partial H1 telemetry, but do not
    # present partial H1 files as a completed treatment result.
    contacts: list[dict[str, Any]] = []
    fallbacks = read_jsonl(h0_archive / "fallback_events.jsonl")
    freshness = read_jsonl(h0_archive / "freshness_events.jsonl")
    execution_timing = read_jsonl(h0_archive / "execution_timing.jsonl")
    precontact: list[dict[str, Any]] = []
    load_timing = [x for x in h0_events + h1_runtime_events if x.get("operation") == "load_workbook"]
    read_timing = [x for x in h0_events + h1_runtime_events if str(x.get("operation", "")).endswith("_timing")]
    write_jsonl(CHECK / "contact_events.jsonl", contacts)
    write_jsonl(CHECK / "fallback_events.jsonl", fallbacks + h1_fallbacks)
    write_jsonl(CHECK / "freshness_events.jsonl", freshness)
    write_jsonl(CHECK / "execution_timing.jsonl", execution_timing)
    write_jsonl(CHECK / "pre_contact_variance.jsonl", precontact)
    write_jsonl(CHECK / "per_load_timing.jsonl", load_timing)
    write_jsonl(CHECK / "per_read_timing.jsonl", read_timing)
    write_jsonl(CHECK / "h0_shadow_eligibility.jsonl", [{
        "task_id": completed_h0.get("task_id"), "run_id": completed_h0.get("run_id"),
        "eligible_load_opportunities": completed_h0.get("h0_counterfactual_opportunities", 0),
        "classification": "WOULD_ACCELERATE" if completed_h0.get("h0_counterfactual_opportunities", 0) else "WOULD_FALLBACK_OR_NO_LOAD",
    }])

    empty_jsonl = ["contact_traces.jsonl", "exact_trace_replay.jsonl", "historical_live_exposure.jsonl"]
    for name in empty_jsonl:
        write_jsonl(CHECK / name, [])
    write_json(CHECK / "workbook_snapshots.json", {})
    write_json(CHECK / "exact_trace_fidelity.json", {"traces": 0, "semantic_exact": 0, "mismatches": 0, "pass": False, "status": "NO_VALID_H1_CONTACT_TRACE"})
    write_json(CHECK / "exact_trace_performance.json", {"traces": 0, "median_reduction_pct": None, "median_absolute_time_saved_s": None, "positive_traces": 0, "positive_fraction": None, "status": "NO_VALID_H1_CONTACT_TRACE"})
    write_jsonl(CHECK / "exact_trace_performance.jsonl", [])

    h0_eff = completed_h0.get("efficiency", {})
    task_rows = [{
        "task_id": "Financial_Model:07_01", "family": "Financial_Model",
        "h0": {"status": completed_h0.get("status"), "completed": True, "contact": False,
               "counterfactual_eligible": completed_h0.get("h0_counterfactual_opportunities", 0),
               "real_openpyxl_parses": h0_eff.get("real_openpyxl_parses", 0),
               "python_walltime_s": h0_eff.get("python_walltime_s", 0), "tool_walltime_s": h0_eff.get("tool_walltime_s", 0),
               "task_walltime_s": completed_h0.get("walltime_total_s"), "model_network_wait_s": h0_eff.get("model_network_wait_s", 0),
               "model_calls": h0_eff.get("api_calls", 0), "tokens": h0_eff.get("tokens", 0), "cost_usd": h0_eff.get("cost_usd", 0)},
        "h1": {"status": "PROVIDER_OR_RUNNER_CENSORED", "completed": False, "contact": False,
               "partial_loads": len(h1_loads), "partial_fallbacks": len(h1_fallbacks)},
        "exact_trace_count": 0,
    }]
    for item in population:
        if item["task_id"] != "Financial_Model:07_01":
            task_rows.append({"task_id": item["task_id"], "family": item["family"], "h0": {"status": "NOT_RUN"}, "h1": {"status": "NOT_RUN"}, "exact_trace_count": 0})
    write_json(CHECK / "task_timing.json", {"tasks": task_rows, "valid_completed_live_pairs": 0, "note": "partial/censored checkpoint; no cross-arm timing inference"})
    write_json(CHECK / "capability.json", {"arms": {}, "valid_completed_pairs": 0, "status": "PROVIDER_OR_RUNNER_CENSORED", "note": "No H1 task completed; no capability claim."})
    write_json(CHECK / "model_behavior.json", {"completed_runs": [{"task_id": completed_h0.get("task_id"), "arm": "H0", **{k: h0_eff.get(k, 0) for k in ("api_calls", "prompt_tokens", "completion_tokens", "tokens", "cost_usd", "python_execs", "view_xlsx", "opens")}}], "status": "censored"})
    write_jsonl(CHECK / "historical_live_exposure.jsonl", [])
    write_json(CHECK / "family_results.json", {"Financial_Model": {"completed_h0": 1, "completed_h1": 0, "contact_tasks": 0}, "Debugging": {"completed": 0}, "Template": {"completed": 0}, "Visualization": {"completed": 0}, "status": "censored"})

    reliability = {"stale_reads": 0, "wrong_generation_reads": 0, "identity_corruption": 0, "semantic_substitutions": 0,
                   "candidate_a_caused_exceptions": 0, "exact_trace_mismatches": 0, "pass": False,
                   "status": "UNTESTED_DUE_TO_NO_COMPLETED_H1_CONTACT_TRACE"}
    capability = {"pass": False, "status": "UNTESTED_DUE_TO_CENSORING", "reproducible_contact_attributed_loss": False}
    contact_gate = {"h1_contact_tasks": [], "count": 0, "thresholds": {"3": False, "4": False, "6": False, "8": False}, "required": 4, "pass": False, "status": "CENSORED"}
    mechanical = {"pass": False, "median_exact_trace_reduction_pct": None, "median_absolute_time_saved_s": None,
                  "positive_trace_fraction": None, "positive_contact_tasks": 0, "status": "UNTESTED_NO_VALID_TRACE"}
    system = {"deterministic_trace_s": None, "live_python_s": h0_eff.get("python_walltime_s", 0), "live_tool_s": h0_eff.get("tool_walltime_s", 0),
              "live_task_s": completed_h0.get("walltime_total_s"), "model_network_s": h0_eff.get("model_network_wait_s", 0),
              "status": "NO_CAUSAL_H1_COMPARISON"}
    write_json(CHECK / "reliability_gate.json", reliability)
    write_json(CHECK / "capability_gate.json", capability)
    write_json(CHECK / "contact_gate.json", contact_gate)
    write_json(CHECK / "mechanical_effectiveness_gate.json", mechanical)
    write_json(CHECK / "system_materiality.json", system)
    retention = {"decision": "DO_NOT_RETAIN_A_IN_RUNTIME", "status": "NOT_DECIDABLE_FROM_CENSORED_CHECKPOINT", "basis": "No valid H1 contact trace or exact replay; prior narrow retention evidence remains separate."}
    a2 = {"decision": "A2_RESEARCH_NOT_JUSTIFIED", "implemented": False, "reason": "This checkpoint was provider/runner censored; no new A2 inference."}
    write_json(CHECK / "runtime_retention_decision.json", retention)
    write_json(CHECK / "a2_decision.json", a2)
    verdict = "PROVIDER_OR_RUNNER_CENSORED"
    write_json(CHECK / "verdict.json", {"verdict": verdict, "valid_completed_primary_runs": 1, "censored_runs": 1, "unstarted_runs": 22, "contact_tasks": [], "reason": "insufficient valid paired live evidence"})
    ledger = {
        "PYTHON_AS_AGENT_QUERY_LANGUAGE": "EARNED",
        "CANDIDATE_A_A1_LIVE_RELIABILITY": "NOT_ESTABLISHED",
        "CANDIDATE_A_A1_LIVE_CAPABILITY_NEUTRALITY": "NOT_ESTABLISHED",
        "CANDIDATE_A_A1_LIVE_CONTACT": "NOT_ESTABLISHED",
        "CANDIDATE_A_A1_EXACT_TRACE_FIDELITY": "UNTESTED",
        "CANDIDATE_A_A1_MECHANICAL_EFFECTIVENESS": "UNTESTED",
        "CANDIDATE_A_A1_SYSTEM_MATERIALITY": "NOT_ESTABLISHED",
        "CANDIDATE_A_A1_CROSS_FAMILY_GENERALISATION": "UNTESTED",
        "CANDIDATE_A_TOKEN_COST_EFFECT": "NOT_ESTABLISHED",
        "CANDIDATE_A_RUNTIME_RETENTION": "NOT_ESTABLISHED",
        "A2_RESEARCH_JUSTIFICATION": "NOT_ESTABLISHED",
        "CANDIDATE_B_REOPENING": "CLOSED",
        "BROADER_BENCHMARK_JUSTIFICATION": "NOT_ESTABLISHED",
    }
    write_json(CHECK / "evidence_ledger.json", ledger)
    next_experiment = {"experiment": "rerun the same frozen 24-run checkpoint only after the provider/runner chunked-response censoring is resolved; do not alter prompts, surface, or arms", "candidate_b": "remain frozen", "a2": "do not run", "live_checkpoint_complete": False, "status": "PROVIDER_OR_RUNNER_CENSORED"}
    write_json(CHECK / "next_experiment.json", next_experiment)

    family = dict(Counter(x.get("family") for x in population))
    selected = ", ".join(all_tasks)
    lines = [
        "# Candidate-A A1 12-Task Checkpoint Report", "",
        "## Verdict: `PROVIDER_OR_RUNNER_CENSORED`", "",
        "The frozen live runner completed one H0 run, began its matched H1 run, then stalled in a chunked provider response and was interrupted. Twenty-two primary runs were never started. No Candidate-A speed, capability, or reliability conclusion is drawn from this partial live record.", "",
        "## Required answers", "",
        f"1. **Selected tasks:** {selected}.",
        "2. **Frozen ranking rule:** top 12 by A1-eligible historical executions, same-generation repeated-open count, A1-safe primitive reads, historical deterministic read/open time, then stable task ID; no score, gold, outcome, or balancing.",
        f"3. **Family composition:** {family}; selected before inference.",
        "4. **H1 contact:** 0 valid completed H1 tasks; the H1 task in progress was censored.",
        "5. **Contact executions:** 0 valid completed H1 contact executions.",
        "6. **Accelerated operations:** 0 valid completed H1 accelerated operations.",
        "7. **Parses avoided:** not estimable; no valid H1 contact trace completed.",
        f"8. **H0 counterfactual eligibility:** {completed_h0.get('h0_counterfactual_opportunities', 0)} eligible load opportunities in the one completed H0 run.",
        "9. **High-exposure non-contact:** not adjudicable from one completed H0 and one censored H1; the partial H1 events were all fallback events.",
        "10. **Non-FM contact:** none observed in valid completed runs.",
        "11. **Stale/wrong-generation reads:** no stale/wrong-generation event observed in completed H0/shared-substrate telemetry; H1 reliability is not established.",
        "12. **Semantic/fallback mismatch:** none observed in completed artifacts; no valid H1 comparison.",
        "13. **Exact-trace replay:** 0 traces; untested.",
        "14. **Capability:** untested for H1; no reproducible capability comparison.",
        "15. **Real per-load time:** completed H0 recorded load timings; no valid H1 comparison.",
        "16. **Candidate-A per-load time:** no accelerated H1 load completed.",
        "17. **Candidate-A per-read time:** no accelerated H1 read completed.",
        "18. **Fallback materialization:** partial H1 events recorded eight predeclared fallback loads; not a completed-run estimate.",
        "19. **Exact-trace timing:** no valid traces.",
        "20. **Positive trace fraction:** not estimable.",
        "21. **Median exact-trace reduction:** not estimable.",
        "22. **Median absolute saving:** not estimable.",
        "23. **Effect by task:** none estimable.",
        f"24. **Total Python walltime:** one completed H0 run recorded {h0_eff.get('python_walltime_s', 0)} s; no H1 comparison.",
        f"25. **Total tool walltime:** one completed H0 run recorded {h0_eff.get('tool_walltime_s', 0)} s; no H1 comparison.",
        f"26. **Total task walltime:** one completed H0 run recorded {completed_h0.get('walltime_total_s')} s; no H1 comparison.",
        f"27. **Model/network share:** completed H0 network wait was {h0_eff.get('model_network_wait_s', 0)} s; no paired system fraction.",
        "28. **Calls/tokens/cost:** no treatment-neutrality conclusion from one H0 only.",
        "29. **Causally removable deterministic time:** not established.",
        "30. **Benchmark relevance:** not established; the checkpoint is censored before valid live contact evidence.",
        "31. **Runtime retention:** not decidable from this checkpoint; prior narrow shadow evidence is not replaced.",
        "32. **A2:** not justified by this censored run.",
        "33. **Candidate B:** remains frozen.",
        "34. **Final architectural claim:** only that the requested decision experiment could not obtain sufficient valid paired live evidence under the frozen provider/runner path.",
        "", "## Censoring record", "",
        f"Completed primary runs: 1/24. Partial H1 run: {partial_h1_run_id}; runtime events: {len(h1_runtime_events)}, loads: {len(h1_loads)}, accelerated operations: 0. Unstarted primary runs: 22. The interruption occurred while `urllib` was reading a chunked HTTPS response.",
        "", "## Evidence ledger", "",
    ]
    lines.extend(f"- {k}: {v}" for k, v in ledger.items())
    lines += [
        "", "WHAT A1 CONTACTED LIVE", "", "No valid completed H1 run contacted Candidate A. The partial H1 run generated only predeclared real-openpyxl fallback load events before provider censoring.", "",
        "WHY NON-CONTACT STILL OCCURRED", "", "The checkpoint did not reach enough completed H1 trajectories to distinguish contact prevalence; no inference is made.", "",
        "CAPABILITY RESULT", "", "Not established because the H1 trajectory and official paired evaluation did not complete.", "",
        "RELIABILITY RESULT", "", "Not established for live A1; no valid H1 contact trace existed. Completed H0 freshness telemetry showed no stale generation.", "",
        "DIRECT LOAD / READ TIMING", "", "Only completed H0 and partial fallback telemetry exist; no H1 accelerated timing comparison.", "",
        "EXACT-TRACE CAUSAL EFFECT", "", "Untested: zero valid H1 contact traces.", "",
        "PARSES AVOIDED", "", "Not established.", "",
        "PYTHON / TOOL-TIME EFFECT", "", "Not comparable.", "",
        "TOTAL TASK-TIME EFFECT", "", "Not comparable.", "",
        "MODEL / NETWORK DOMINANCE", "", "The stalled chunked response is a provider/runner censoring event, not a treatment effect.", "",
        "TOKEN / COST EFFECT", "", "Not established.", "",
        "CROSS-FAMILY CONTACT", "", "Untested.", "",
        "HISTORICAL-VS-LIVE EXPOSURE", "", "Not adjudicable from the censored checkpoint; population ranking remains frozen.", "",
        "WHETHER CONTACT IS SUFFICIENT", "", "No: valid contact evidence is insufficient, not evidence of low contact.", "",
        "WHETHER CONDITIONAL SPEEDUP IS MATERIAL", "", "Untested in this live checkpoint.", "",
        "WHETHER A1 IS A BENCHMARK-LEVEL MECHANISM", "", "Not established.", "",
        "WHETHER A1 IS STILL WORTH RETAINING AS A NARROW FAST PATH", "", "Not decided by this censored experiment; prior shadow evidence remains the relevant retention evidence.", "",
        "WHETHER A2 DESERVES A SEPARATE MECHANICAL PROBE", "", "No new justification from this run.", "",
        "WHETHER CANDIDATE B REMAINS FROZEN", "", "Yes.", "",
        "FINAL EVIDENCE LEDGER", "", *[f"{k}: {v}" for k, v in ledger.items()], "",
        "SINGLE NEXT EXPERIMENT", "", "Resolve the provider/runner chunked-response censoring, then rerun this exact frozen 12-task checkpoint without changing prompts, arms, Candidate-A surface, A1 classifier, or Candidate B status.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
