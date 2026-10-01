#!/usr/bin/env python3
"""Finish Stage A at n=2 per user directive (2026-09-18): run the 10 missing
rep-2 pairs with identical driver logic, then stop. No reps 3-5."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ab_stagea import AB, RUNNER, reset_live  # noqa: E402

MISSING = [
    ("Template:01_07", "H1"), ("Template:01_07", "H0"),
    ("Debugging:02_06", "H1"), ("Debugging:02_06", "H0"),
    ("Financial_Model:01_01", "H1"), ("Financial_Model:01_01", "H0"),
    ("Financial_Model:13_05", "H1"), ("Financial_Model:13_05", "H0"),
    ("Template:06_12", "H1"), ("Template:06_12", "H0"),
]


def main() -> None:
    env = dict(__import__("os").environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AB_FIDELITY_LOG"] = str(AB / "runtime_fidelity.jsonl")
    rep_log = open(AB / "repetitions.jsonl", "a")
    bnd_log = open(AB / "pre_mutation_boundary.jsonl", "a")
    for task, arm in MISSING:
        live = reset_live(task)
        arch = AB / "reps" / f"{task.replace(':', '_')}_rep2_{arm}"
        if arch.exists():
            shutil.rmtree(arch)
        cmd = [sys.executable, "-B", str(RUNNER), "--task", task,
               "--arm", arm, "--workdir", str(live), "--archive-dir", str(arch)]
        print(f"=== {task} rep2 {arm} ===", flush=True)
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=1500, env=env)
        print((proc.stdout + proc.stderr)[-800:], flush=True)
        rec_p = arch / "run_record.json"
        if rec_p.exists():
            rec = json.loads(rec_p.read_text())
            rep_log.write(json.dumps({
                "task_id": task, "rep": 2, "arm": arm,
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
                bnd_log.write(json.dumps(
                    {"task_id": task, "rep": 2, "arm": arm, **e}) + "\n")
            bnd_log.flush()
    print("STAGEA_N2_DONE")


if __name__ == "__main__":
    main()
