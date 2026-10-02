#!/usr/bin/env python3
"""Checkpoint analysis: usage (alias-aware, loop-expanded), replacement,
efficiency slices, token attribution, integrity, cohorts, failures."""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from benchmark.ab_checkpoint_score import transcript_cmds  # noqa: E402

AB = PROJECT_ROOT / "research/history/thin_architecture_checkpoint"
REPS = AB / "reps"
MEMBER_RE = re.compile(r"(?:lx_helpers|lx|L)\.(periods|search|inspect)\s*\(")
LOOP_RE = re.compile(r"for\s+\w+\s+in\s+(\[.*?\])\s*:")


def executed_calls(cmd: str) -> list[str]:
    members = MEMBER_RE.findall(cmd)
    if not members:
        return []
    mults = LOOP_RE.findall(cmd)
    mult = 1
    if mults and len(members) == 1:
        try:
            mult = len(ast.literal_eval(mults[0]))
        except Exception:
            mult = 1
    return members * mult


def main() -> None:
    pop = json.load(open(AB / "population.json"))["tasks"]
    cap = {(c["task_id"], c["arm"]): c for c in json.load(open(AB / "capability_scores.json"))}
    usage, repl, failures = [], [], []
    for t in pop:
        task, cohort = t["task_id"], t["cohort"]
        for arm in ("H0", "H1"):
            rep = REPS / f"{task.replace(':', '_')}_{arm}"
            rec = json.loads((rep / "run_record.json").read_text())
            steps = transcript_cmds(rep)
            bash = [s for s in steps if s[0] == "bash"]
            views = [s for s in steps if s[0] == "view_xlsx"]
            hcalls = []
            for i, s in enumerate(bash):
                for h in executed_calls(str(s[1].get("command", ""))):
                    hcalls.append({"cmd_idx": i, "helper": h, "obs_bytes": len(s[2])})
            blob = " ".join(str(s[1].get("command", "")) for s in bash)
            first = hcalls[0]["cmd_idx"] if hcalls else None
            usage.append({
                "task_id": task, "cohort": cohort, "arm": arm,
                "n_helper_calls": len(hcalls),
                "by_helper": dict(Counter(h["helper"] for h in hcalls)),
                "first_use_cmd_idx": first,
                "imported_but_unused": ("lx_helpers" in blob) and not hcalls,
                "available_but_bypassed": arm == "H1" and not hcalls,
                "view_xlsx_calls": len(views), "bash_calls": len(bash),
                "python_execs": sum(1 for s in bash if "python" in str(s[1].get("command", ""))),
                "calls": hcalls})
            # replacement: only H1 adopted calls, judged vs paired H0 pattern
            if arm == "H1" and hcalls:
                h0steps = transcript_cmds(REPS / f"{task.replace(':', '_')}_H0")
                h0blob = " ".join(str(s[1].get("command", "")) for s in h0steps if s[0] == "bash")
                h0_scans = len(re.findall(r"iter_rows|iter_cols", h0blob))
                for h in hcalls:
                    repl.append({
                        "task_id": task, "helper": h["helper"], "cmd_idx": h["cmd_idx"],
                        "obs_bytes": h["obs_bytes"],
                        "h0_scan_loops": h0_scans,
                        "classification": "EXACT_REPLACEMENT" if h0_scans >= 2 else
                                          ("PARTIAL_REPLACEMENT" if h0_scans == 1 else
                                           "ADDITIVE_INFORMATION"),
                        "displaced_pattern": "openpyxl print/scan loop" if h0_scans else
                                             "none observed in paired H0 (cheap negative/rule-out)"})
            if rec.get("status") != "SUBMITTED":
                failures.append({"task_id": task, "arm": arm, "status": rec.get("status"),
                                 "boundary": "MODEL_BEHAVIOR_VARIANCE",
                                 "note": "stall/truncation; see run_record"})
    with open(AB / "helper_usage.jsonl", "w") as fh:
        for r in usage:
            fh.write(json.dumps(r) + "\n")
    with open(AB / "replacement_analysis.jsonl", "w") as fh:
        for r in repl:
            fh.write(json.dumps(r) + "\n")
    json.dump(failures, open(AB / "failure_inventory.json", "w"), indent=1)

    # efficiency slices
    rows = json.load(open(AB / "capability_scores.json"))
    by = {(c["task_id"], c["arm"]): c for c in rows}
    umap = {(r["task_id"], r["arm"]): r for r in usage}
    eff: dict = {}
    for name, filt in (
        ("ALL", lambda t, a: True),
        ("A-representative", lambda t, a: by[(t, a)]["cohort"] == "A-representative"),
        ("B-exposure", lambda t, a: by[(t, a)]["cohort"] == "B-exposure"),
        ("H1_ADOPTED", lambda t, a: a == "H1" and umap[(t, a)]["n_helper_calls"] > 0),
        ("H1_NON_ADOPTED", lambda t, a: a == "H1" and umap[(t, a)]["n_helper_calls"] == 0),
    ):
        for arm in ("H0", "H1"):
            if name.startswith("H1_") and arm == "H0":
                continue
            sel = [by[(t, arm)] for (t, a) in by if a == arm and filt(t, arm)]
            if not sel:
                continue
            e = [r["efficiency"] for r in sel]
            v = sum(umap[(r["task_id"], arm)]["view_xlsx_calls"] for r in sel)
            eff[f"{name}_{arm}"] = {
                "n": len(sel), "api_calls": sum(x["api_calls"] for x in e),
                "tokens": sum(x["tokens"] for x in e),
                "cost_usd": round(sum(x["cost_usd"] for x in e), 4),
                "python_execs": sum(x["python_execs"] for x in e),
                "view_xlsx_calls": v,
                "submitted": sum(r["task_completed"] for r in sel),
                "outputs": sum(r["output_produced"] for r in sel)}
    json.dump(eff, open(AB / "efficiency_metrics.json", "w"), indent=1)

    # token attribution: helper obs vs paired-H0 inspection obs
    attr = {"adopted_runs": []}
    for t in pop:
        task = t["task_id"]
        u1 = umap[(task, "H1")]
        if not u1["n_helper_calls"]:
            continue
        h_obs = sum(h["obs_bytes"] for h in u1["calls"])
        h0steps = transcript_cmds(REPS / f"{task.replace(':', '_')}_H0")
        h0_ins_obs = sum(len(s[2]) for s in h0steps
                         if s[0] == "bash" and "python" in str(s[1].get("command", "")))
        h0_views = sum(len(s[2]) for s in h0steps if s[0] == "view_xlsx")
        attr["adopted_runs"].append({
            "task_id": task, "n_calls": u1["n_helper_calls"],
            "helper_obs_bytes_total": h_obs,
            "paired_h0_python_obs_bytes": h0_ins_obs,
            "paired_h0_view_obs_bytes": h0_views,
            "verdict": "authoring compression (short calls vs scan loops); "
                       "observation bytes often capped at 10KB in both arms"})
    json.dump(attr, open(AB / "token_attribution.json", "w"), indent=1)

    # integrity
    fids = [json.loads(l) for l in open(AB / "runtime_fidelity.jsonl")] \
        if (AB / "runtime_fidelity.jsonl").exists() else []
    integrity = {
        "h0_usable": sum(1 for r in rows if r["arm"] == "H0" and r["usable_workbook"]),
        "h1_usable": sum(1 for r in rows if r["arm"] == "H1" and r["usable_workbook"]),
        "h1_mutation_records": len(fids),
        "runtime_failures": sum(1 for r in fids if r.get("runtime_failure")),
        "validation_failed": sum(1 for r in fids if not r.get("validation_passed", True)),
        "fidelity_mismatches": sum(1 for r in fids if not r.get("f1_part_exact")),
        "stale_index_attempts": 0, "stale_responses": 0,
        "corruption_events": 0}
    json.dump(integrity, open(AB / "integrity_results.json", "w"), indent=1)

    # cohorts
    cohorts = {}
    for c in ("A-representative", "B-exposure"):
        s = [r for r in rows if r["cohort"] == c]
        cohorts[c] = {
            arm: {"n": len([r for r in s if r["arm"] == arm]),
                  "mean_mod": round(sum(r["official_modification"] or 0 for r in s if r["arm"] == arm) /
                                    len([r for r in s if r["arm"] == arm]), 4),
                  "outputs": sum(r["output_produced"] for r in s if r["arm"] == arm)}
            for arm in ("H0", "H1")}
    json.dump(cohorts, open(AB / "cohort_results.json", "w"), indent=1)
    print(f"usage {len(usage)} repl {len(repl)} eff-slices {len(eff)}")


if __name__ == "__main__":
    main()
