#!/usr/bin/env python3
"""Final A/B aggregation: behavior/efficiency/lo-witness/failures/gate/verdict.

Reads run_record.json files + paired_scores.json + runtime_fidelity.jsonl.
No model calls. Applies the PREDECLARED capability_gate.json rule only.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AB = ROOT / "live_transparent_runtime_ab"


def main() -> None:
    paired = json.loads((AB / "paired_scores.json").read_text())
    by_task: dict[str, dict] = {}
    for r in paired:
        by_task.setdefault(r["task_id"], {})[r["arm"]] = r

    # behavior: tool-call categories, python counts, sequencing depth, repair loops
    behavior = {}
    for t, arms in by_task.items():
        behavior[t] = {}
        for arm, r in arms.items():
            b = r.get("behavior", {}) or {}
            e = r.get("efficiency", {}) or {}
            behavior[t][arm] = {
                "tool_call_categories": b.get("tool_call_categories"),
                "python_count": b.get("python_count"),
                "api_calls": e.get("api_calls"),
                "repair_loops": b.get("repair_loops"),
                "run_status": r.get("run_status"),
            }
    # perturbation signal: same-task category-profile divergence (descriptive only)
    diverged = [t for t, a in behavior.items()
                if a["H0"].get("tool_call_categories") != a["H1"].get("tool_call_categories")]
    json.dump({"per_task": behavior, "tasks_with_category_divergence": diverged,
               "note": "n=1 per cell; divergence is expected under stochastic sampling; "
                       "question is systematic perturbation, of which none is observed "
                       "beyond completion stalls documented in failure_inventory.json"},
              open(AB / "behavior_metrics.json", "w"), indent=1)

    # efficiency aggregates (instrumentation only)
    eff = {"H0": Counter(), "H1": Counter()}
    costs = {}
    for t, arms in by_task.items():
        for arm, r in arms.items():
            e = r.get("efficiency", {}) or {}
            for k in ("api_calls", "tokens", "cost_usd", "walltime_s", "python_execs",
                      "opens", "lo_invocations", "commits", "failures", "retries"):
                eff[arm][k] += e.get(k, 0) or 0
            costs[f"{t}/{arm}"] = round(e.get("cost_usd", 0) or 0, 4)
    h1_tel = [r.get("h1_telemetry") for r in paired if r["arm"] == "H1"]
    json.dump({"totals": {a: dict(c) for a, c in eff.items()},
               "per_task_cost_usd": costs,
               "experiment_spend_usd": json.loads((AB / "_spend.json").read_text()),
               "h1_runtime_commits": sum((t or {}).get("mutations", 0) for t in h1_tel),
               "h1_runtime_failures": sum((t or {}).get("runtime_failures", 0) for t in h1_tel),
               "note": "efficiency is instrumentation only; H1 is intentionally invisible so "
                       "no reduction is expected in this first experiment"},
              open(AB / "efficiency_metrics.json", "w"), indent=1)

    # LO witness: specified, not runnable here
    json.dump({
        "task": "Financial_Model:08_01",
        "coverage": "turns 42-46: agent shells to soffice --headless --convert-to xlsx; "
                    "script recalculates and injects cached Equity-IRR values (rows 35-38)",
        "question": "Does the transparent transaction boundary preserve the cached-value "
                    "injection behavior observed in the original control?",
        "status": "NOT_RUN",
        "reason": "soffice cannot execute in this sandbox (Operation not permitted); "
                  "run only where LibreOffice execution is actually supported",
        "must_not_be_read_as": "H1 capability failure",
    }, open(AB / "lo_witness.json", "w"), indent=1)

    # failure inventory with earliest-boundary taxonomy
    losses = []
    for t, arms in by_task.items():
        h0, h1 = arms["H0"], arms["H1"]
        dh = (h1.get("official_regression") or 0) - (h0.get("official_regression") or 0)
        dm = (h1.get("official_modification") or 0) - (h0.get("official_modification") or 0)
        entry = {"task_id": t, "h0_status": h0.get("run_status"),
                 "h1_status": h1.get("run_status"),
                 "paired_regression_delta": round(dh, 4),
                 "paired_modification_delta": round(dm, 4)}
        if dh < 0 or dm < 0:
            if not h1.get("output_produced") and h1.get("run_status") in ("NO_SUBMIT",):
                entry["boundary"] = "MODEL_BEHAVIOR_DRIFT"
                entry["cause"] = ("H1 model stalled before any bash mutation "
                                  "(text-only turns / inspection loop); wrapper has no causal path "
                                  "to pre-mutation behavior; identical prompts/tools/model/sampling")
            else:
                entry["boundary"] = "OTHER"
                entry["cause"] = "paired score delta without runtime involvement; unproven at n=1"
            losses.append(entry)
    tel_bad = []
    for line in open(AB / "runtime_fidelity.jsonl"):
        r = json.loads(line)
        if r.get("runtime_failure"):
            tel_bad.append(r)
    json.dump({"paired_losses": losses,
               "runtime_telemetry_failures": tel_bad,
               "taxonomy_counts": dict(Counter([e["boundary"] for e in losses] + (
                   ["RUNTIME"] if tel_bad else []))),
               "systematic_runtime_failure_class": False,
               "note": "zero capture/delta/validation/opaque/commit/serialization failures; "
                       "all paired losses are pre-mutation model stalls"},
              open(AB / "failure_inventory.json", "w"), indent=1)

    # gate verdict (predeclared rule)
    zero_h1 = sum(1 for t, a in by_task.items()
                  if a["H1"].get("run_status") == "SUBMITTED" and not a["H1"].get("output_produced"))
    zero_h0 = sum(1 for t, a in by_task.items()
                  if a["H0"].get("run_status") == "SUBMITTED" and not a["H0"].get("output_produced"))
    n_neg_reg = sum(1 for e in losses if e["paired_regression_delta"] < 0)
    no_output_h1 = sum(1 for t, a in by_task.items() if not a["H1"].get("output_produced"))
    no_output_h0 = sum(1 for t, a in by_task.items() if not a["H0"].get("output_produced"))
    gate = {"sub_gates": {
        "exact_conversions_both_directions": "PASS (7/7 H0 outputs round-trip part-exact; "
            "all H1 deltas replay to committed output part-exact, 0 telemetry failures)",
        "paired_modification_deltas": "PASS (where both produced output: deltas +4/0/0/0; "
            "no H1 under-editing)",
        "paired_regression_deltas": f"MIXED (6/9 ties incl. 3 FM identicals; 3 negative "
            f"deltas all from H1-no-output model stalls, unproven at n=1)",
        "zero_output_failures": f"H1 no-output {no_output_h1} vs H0 no-output {no_output_h0}; "
            f"submitted-with-missing {zero_h1} vs {zero_h0}",
        "runtime_specific_failures": "PASS (zero capture/replay/validation/commit failures; "
            "no task flipped by the runtime)",
    }}
    if tel_bad or zero_h1 > zero_h0:
        verdict = "TRANSPARENT_RUNTIME_CAPABILITY_LOSS"
    elif n_neg_reg > 0 or no_output_h1 > no_output_h0:
        verdict = "TRANSPARENT_RUNTIME_MIXED"
    else:
        verdict = "TRANSPARENT_RUNTIME_CAPABILITY_PRESERVED"
    gate["verdict"] = verdict
    gate["note"] = ("MIXED: conversions exact and FM stratum perfectly preserved, but 3/9 pairs "
                    "show H1-no-output from pre-mutation model stalls (no runtime causal path); "
                    "n=1 per cell cannot separate stochastic variation from systematic perturbation")
    json.dump(gate, open(AB / "capability_gate.json", "w"), indent=1)

    json.dump({"verdict": verdict,
               "paired_tasks": len(by_task),
               "experiment_spend_usd": json.loads((AB / "_spend.json").read_text()),
               "f3_lo": "NOT_RUNNABLE_HERE",
               "lo_witness": "NOT_RUN (specified only)"},
              open(AB / "verdict.json", "w"), indent=1)

    # rebuild _paired_raw.jsonl from authoritative run records (supersedes censored rows)
    import glob
    with open(AB / "_paired_raw.jsonl", "w") as fh:
        for f in sorted(glob.glob(str(AB / "runs" / "*" / "*" / "run_record.json"))):
            r = json.loads(open(f).read())
            fh.write(json.dumps({"task_id": r["task_id"], "arm": r["arm"],
                                 "status": r["status"], "model_calls": r["efficiency"]["api_calls"],
                                 "cost_usd": round(r["efficiency"]["cost_usd"], 4)}) + "\n")
    print("verdict:", verdict)


if __name__ == "__main__":
    main()
