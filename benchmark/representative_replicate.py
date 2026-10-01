#!/usr/bin/env python3
"""Targeted replication: re-run BOTH arms once for each discordant task.

Reads capability_discordances.json (written by representative_score.py).
Run IDs are deterministic (repl_00, repl_01, ...) so reruns overwrite.
Archives land in reps_replication/ via phase=replication. No model-facing
or harness changes: same run_one path as primary slots.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "representative_architecture_checkpoint"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tasks", default="",
                    help="comma-separated task_ids to skip with reason")
    ap.add_argument("--partition", default=None,
                    help="i/N over global discordance index")
    args = ap.parse_args()
    skip = {t for t in args.skip_tasks.split(",") if t}
    disc_path = OUT / "capability_discordances.json"
    if not disc_path.exists():
        print("no discordances file; run representative_score.py first")
        sys.exit(2)
    disc = json.load(open(disc_path))
    indexed = [(i, d) for i, d in enumerate(disc)
               if d["task_id"] not in skip]
    if args.partition:
        i, n = (int(x) for x in args.partition.split("/"))
        indexed = [(gi, d) for gi, d in indexed if gi % n == i]
    if not indexed:
        print("zero discordances in scope: nothing to replicate")
        return
    runs = []
    for gi, d in indexed:
        task = d["task_id"]
        for arm in ("H0", "H1"):
            run_id = f"repl_{gi:02d}{arm}"
            print(f"=== {task} {arm} ({run_id}) ===", flush=True)
            p = subprocess.run(
                [sys.executable, "benchmark/representative_checkpoint.py",
                 "--run-one", f"{task}:{arm}:{run_id}",
                 "--phase", "replication"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                timeout=1500)
            print((p.stdout + p.stderr)[-500:], flush=True)
            if p.returncode != 0:
                print(f"REPLICATION SLOT FAILED: {task} {arm}")
                sys.exit(3)
            runs.append({"task_id": task, "arm": arm, "run_id": run_id,
                         "reason": d["reasons"]})
    out = OUT / (f"replication_runs_p{args.partition.replace('/', '_')}.json"
                 if args.partition else "replication_runs.json")
    json.dump(runs, open(out, "w"), indent=1)
    print(f"replicated {len(runs)} slots over {len(indexed)} discordant tasks")


if __name__ == "__main__":
    main()
