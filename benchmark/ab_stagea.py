#!/usr/bin/env python3
"""Stage A: targeted capability replication (n=5 per task per arm).

6 tasks (3 discordant + 3 sentinels) x 5 reps x 2 arms = 60 live runs.
Arm-neutral shared workdir per task (identical model-visible paths both arms).
Identity audit via --dry-run BEFORE any inference. No early stopping.

Usage: python3 benchmark/ab_stagea.py [--audit-only]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AB = PROJECT_ROOT / "research/history/targeted_runtime_replication"
RUNNER = PROJECT_ROOT / "benchmark" / "ab_local_runner.py"

TASKS = ["Template:01_02", "Template:01_07", "Debugging:02_06",
         "Financial_Model:01_01", "Financial_Model:13_05", "Template:06_12"]
N_REPS = 5


def task_paths(task: str) -> tuple[str, str, Path]:
    cat, _, tid = task.partition(":")
    ds = json.loads((PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" /
                     "data" / cat / "dataset.json").read_text())
    item = next(d for d in ds if str(d["id"]) == tid)
    src = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data" / cat / item["spreadsheet_path"]
    return cat, tid, src


def reset_live(task: str) -> Path:
    live = AB / "work" / task.replace(":", "_")
    if live.exists():
        shutil.rmtree(live)
    live.mkdir(parents=True)
    _, _, src = task_paths(task)
    shutil.copy2(src, live / "input.xlsx")
    return live


def dry_run(task: str, arm: str, live: Path) -> dict:
    cmd = [sys.executable, str(RUNNER), "--task", task, "--arm", arm,
           "--workdir", str(live),
           "--archive-dir", str(AB / "audit_tmp" / f"{task}_{arm}".replace(":", "_")),
           "--dry-run"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"dry-run failed {task} {arm}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def identity_audit() -> dict:
    diffs, records = [], {}
    for task in TASKS:
        live = reset_live(task)
        h0 = dry_run(task, "H0", live)
        h1 = dry_run(task, "H1", live)
        records[task] = {"H0": h0, "H1": h1}
        for field in ("system_hash", "instance_hash", "tool_order", "model",
                      "temperature", "top_p", "max_tokens", "tool_choice",
                      "parallel_tool_calls", "workdir_listing", "input_hash"):
            if h0[field] != h1[field]:
                diffs.append({"task": task, "field": field,
                              "H0": str(h0[field])[:120], "H1": str(h1[field])[:120]})
        rb0, rb1 = dict(h0["request_body"]), dict(h1["request_body"])
        if rb0 != rb1:
            diffs.append({"task": task, "field": "request_body",
                          "H0": str(rb0)[:200], "H1": str(rb1)[:200]})
    audit = {"n_tasks": len(TASKS), "differences": diffs,
             "pass": not diffs,
             "note": "shared arm-neutral workdir => model-visible paths identical; "
                     "prompts/tools/model/sampling/request fields hashed equal"}
    AB.mkdir(parents=True, exist_ok=True)
    json.dump(audit, open(AB / "identity_audit.json", "w"), indent=1)
    json.dump(records, open(AB / "_dryrun_records.json", "w"), indent=1)
    print("identity audit:", "PASS" if audit["pass"] else f"FAIL {len(diffs)} diffs")
    return audit


def write_frozen() -> None:
    AB.mkdir(parents=True, exist_ok=True)
    json.dump({
        "name": "targeted-runtime-replication-stage-a",
        "n_reps_frozen": N_REPS,
        "freeze_policy": "n frozen before inference; no early stopping for favorable looks",
        "arms": {"H0": "default agent, ordinary Python/openpyxl, existing path",
                 "H1": "identical surface + transparent transaction underneath; "
                       "no new model info/helpers/receipts/prompts"},
        "causal_boundary": "treatment code (h1_wrap) executes only after a bash call "
                           "completes; pre-first-bash divergence cannot be runtime-caused",
        "verdicts": ["RUNTIME_CAPABILITY_PRESERVATION_SUPPORTED",
                     "RUNTIME_BEHAVIORAL_EFFECT_DETECTED",
                     "RUNTIME_CAPABILITY_LOSS", "INCONCLUSIVE"],
    }, open(AB / "spec.json", "w"), indent=1)
    json.dump({
        "discordant": TASKS[:3], "sentinels": TASKS[3:],
        "rationale": "discordant = prior H1-only pre-mutation stalls; "
                     "sentinels = stable completed pairs (FM 01_01/13_05, Template 06_12)",
    }, open(AB / "population.json", "w"), indent=1)


def run_all() -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AB_FIDELITY_LOG"] = str(AB / "runtime_fidelity.jsonl")
    rep_log = open(AB / "repetitions.jsonl", "a")
    bnd_log = open(AB / "pre_mutation_boundary.jsonl", "a")
    for rep in range(1, N_REPS + 1):
        arms = ("H0", "H1") if rep % 2 == 1 else ("H1", "H0")
        for task in TASKS:
            for arm in arms:
                live = reset_live(task)
                arch = AB / "reps" / f"{task.replace(':', '_')}_rep{rep}_{arm}"
                if arch.exists():
                    shutil.rmtree(arch)
                cmd = [sys.executable, "-B", str(RUNNER), "--task", task,
                       "--arm", arm, "--workdir", str(live), "--archive-dir", str(arch)]
                print(f"=== {task} rep{rep} {arm} ===", flush=True)
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=1500, env=env)
                print((proc.stdout + proc.stderr)[-800:], flush=True)
                rec_p = arch / "run_record.json"
                if rec_p.exists():
                    rec = json.loads(rec_p.read_text())
                    rep_log.write(json.dumps({
                        "task_id": task, "rep": rep, "arm": arm,
                        "status": rec.get("status"),
                        "output_produced": rec.get("output_produced"),
                        "first_event": rec.get("first_event"),
                        "first_mutation_idx": rec.get("first_mutation_idx"),
                        "pre_mutation_stall": rec.get("pre_mutation_stall"),
                        "api_calls": (rec.get("efficiency") or {}).get("api_calls"),
                        "cost_usd": round((rec.get("efficiency") or {}).get("cost_usd", 0), 4),
                    }) + "\n")
                    rep_log.flush()
                    for e in rec.get("boundary_events", []):
                        bnd_log.write(json.dumps({
                            "task_id": task, "rep": rep, "arm": arm, **e}) + "\n")
                    bnd_log.flush()
                else:
                    rep_log.write(json.dumps({"task_id": task, "rep": rep, "arm": arm,
                                              "status": "NO_RECORD",
                                              "stderr": proc.stderr[-300:]}) + "\n")
                    rep_log.flush()
    print("ALLDONE")


def main() -> None:
    write_frozen()
    audit = identity_audit()
    if not audit["pass"]:
        print("IDENTITY AUDIT FAILED — repair before inference")
        sys.exit(2)
    if "--audit-only" in sys.argv:
        return
    run_all()


if __name__ == "__main__":
    main()
