#!/usr/bin/env python3
"""Launch the frozen Financial_Model formula-index pilot.

Interleaves task × arm × repeat so provider drift is not arm-correlated.
Does not stop because exact looks good or bad. Individual task failures are
recorded and the remaining jobs still run.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "benchmark/slices/fm-index-pilot-twenty.json"
RUNNER = ROOT / "benchmark/run_openrouter_slice.py"
SCORER = ROOT / "benchmark/score_openrouter_run.py"
PROXIMAL = ROOT / "benchmark/formula_index_score.py"
RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
ORDER_FILE = RUNS / "fm-index-pilot-twenty" / "manifest.json"

MODEL = "z-ai/glm-5.3-flash"
SEED = 20260904
CALL_LIMIT = 50
COST_LIMIT = 2.0
TIMEOUT = 1800
EXECUTION_TIMEOUT = 180
REASONING = "low"
REPEATS = (1, 2)
ARM_RUNS = {
    "control": {
        1: "glm-5.3-flash-fm-index-control-1",
        2: "glm-5.3-flash-fm-index-control-2",
    },
    "control-index": {
        1: "glm-5.3-flash-fm-index-control-index-1",
        2: "glm-5.3-flash-fm-index-control-index-2",
    },
}


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def build_jobs(slice_data: dict, *, seed: int = SEED) -> list[dict]:
    tasks = [
        {"category": task["category"], "id": task["id"]} for task in slice_data["tasks"]
    ]
    jobs = []
    for task in tasks:
        for arm, names in ARM_RUNS.items():
            for repeat in REPEATS:
                jobs.append(
                    {
                        "task": f"{task['category']}:{task['id']}",
                        "category": task["category"],
                        "id": task["id"],
                        "arm": arm,
                        "repeat": repeat,
                        "run_name": names[repeat],
                    }
                )
    rng = random.Random(seed)
    rng.shuffle(jobs)
    for index, job in enumerate(jobs, 1):
        job["order"] = index
    return jobs


def runner_command(job: dict) -> list[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--slice",
        str(SLICE),
        "--run-name",
        job["run_name"],
        "--task",
        job["task"],
        "--model",
        MODEL,
        "--control" if job["arm"] == "control" else "--control-index",
        "--call-limit",
        str(CALL_LIMIT),
        "--cost-limit",
        str(COST_LIMIT),
        "--reasoning-effort",
        REASONING,
        "--timeout",
        str(TIMEOUT),
        "--execution-timeout",
        str(EXECUTION_TIMEOUT),
        "--max-requeries",
        "2",
        "--skip-existing",
        "--no-score",
    ]
    return command


def write_order(jobs: list[dict], *, commit: str, extra: dict | None = None) -> dict:
    payload = {
        "seed": SEED,
        "model": MODEL,
        "call_limit": CALL_LIMIT,
        "cost_limit_usd": COST_LIMIT,
        "reasoning_effort": REASONING,
        "token_limit_policy": "remaining-budget",
        "timeout_seconds": TIMEOUT,
        "execution_timeout_seconds": EXECUTION_TIMEOUT,
        "git_commit": commit,
        "control_config": "benchmark/sweagent/spreadsheet-control.yaml",
        "treatment_config": "benchmark/sweagent/spreadsheet-control-index.yaml",
        "slice": str(SLICE.relative_to(ROOT)),
        "jobs": jobs,
        **(extra or {}),
    }
    ORDER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ORDER_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _score_run(run_name: str) -> int:
    run_root = RUNS / run_name
    return subprocess.call(
        [sys.executable, str(SCORER), str(run_root), "--write-ledger"],
        cwd=ROOT,
    )


def _score_proximal() -> int:
    status = 0
    for repeat in REPEATS:
        control = ARM_RUNS["control"][repeat]
        treatment = ARM_RUNS["control-index"][repeat]
        out = RUNS / f"fm-index-pilot-proximal-repeat-{repeat}.json"
        status |= subprocess.call(
            [
                sys.executable,
                str(PROXIMAL),
                control,
                treatment,
                "--json",
                str(out),
            ],
            cwd=ROOT,
        )
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-order-only", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "benchmark"))
    from run_openrouter_slice import _load_dotenv

    _load_dotenv()
    slice_data = json.loads(SLICE.read_text())
    jobs = build_jobs(slice_data)
    commit = git_commit()
    payload = write_order(
        jobs,
        commit=commit,
        extra={
            "written_at": datetime.now(UTC).isoformat(),
            "worktree_dirty": git_dirty(),
            "resume_after_incident": "incident-sweagent-signature.json",
            "original_launch_commit": "20783284622db2e20652e2ae82befce866d8ddaa",
        },
    )
    print(f"ORDER jobs={len(jobs)} seed={SEED} commit={commit} file={ORDER_FILE}", flush=True)
    if args.write_order_only or args.dry_run:
        for job in jobs:
            print(
                f"{job['order']:02d} {job['arm']:14} r{job['repeat']} {job['task']}",
                flush=True,
            )
        return 0

    if shutil.which("docker") is None:
        raise RuntimeError("docker is required")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY must be set")

    log_path = ORDER_FILE.parent / "launch.log"

    failures = 0
    with log_path.open("a", encoding="utf-8") as log:
        for job in jobs:
            started = datetime.now(UTC).isoformat()
            header = (
                f"JOB {job['order']}/{len(jobs)} {job['arm']} r{job['repeat']} "
                f"{job['task']} run={job['run_name']} started={started}"
            )
            print(header, flush=True)
            log.write(header + "\n")
            log.flush()
            command = runner_command(job)
            result = subprocess.run(command, cwd=ROOT)
            if result.returncode != 0:
                failures += 1
                msg = f"JOB-FAIL {job['order']} rc={result.returncode} {job['task']} {job['arm']}"
                print(msg, flush=True)
                log.write(msg + "\n")
            else:
                msg = f"JOB-DONE {job['order']} {job['task']} {job['arm']}"
                print(msg, flush=True)
                log.write(msg + "\n")
            log.flush()

        print("SCORING official eval on four run directories", flush=True)
        score_status = 0
        for names in ARM_RUNS.values():
            for run_name in names.values():
                score_status |= _score_run(run_name)
        print("SCORING proximal fingerprint metric", flush=True)
        score_status |= _score_proximal()

    print(
        f"SUMMARY jobs={len(jobs)} failures={failures} score_status={score_status} "
        f"order={ORDER_FILE}",
        flush=True,
    )
    return 1 if failures or score_status else 0


if __name__ == "__main__":
    raise SystemExit(main())
