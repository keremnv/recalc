#!/usr/bin/env python3
"""Launch the 20_05 / 11_02 forced-exposure replication.

20 jobs: 2 tasks × 2 arms × 5 repeats, interleaved. Does not change the
intervention. Infrastructure failures before meaningful model execution are
retried once; timeouts after work are outcomes.
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
SLICE = ROOT / "benchmark/slices/fm-ambient-replication-two.json"
RUNNER = ROOT / "benchmark/run_openrouter_slice.py"
SCORER = ROOT / "benchmark/score_openrouter_run.py"
PROXIMAL = ROOT / "benchmark/formula_index_ambient_replication_score.py"
RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
ORDER_FILE = RUNS / "fm-ambient-replication-two" / "manifest.json"

MODEL = "z-ai/glm-5.3-flash"
SEED = 202609051
CALL_LIMIT = 50
COST_LIMIT = 2.0
TIMEOUT = 1800
EXECUTION_TIMEOUT = 180
REASONING = "low"
REPEATS = (1, 2, 3, 4, 5)
ARM_RUNS = {
    "control": {n: f"glm-5.3-flash-fm-ambient-repl-control-{n}" for n in REPEATS},
    "control-ambient": {
        n: f"glm-5.3-flash-fm-ambient-repl-treatment-{n}" for n in REPEATS
    },
}
INFRA_MARKERS = (
    "Server disconnected",
    "OpenrouterException",
    "litellm.APIError",
    "APIError: OpenrouterException",
)


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
    return [
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
        "--control" if job["arm"] == "control" else "--control-ambient",
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
        "treatment_config": "benchmark/sweagent/spreadsheet-control-ambient.yaml",
        "slice": str(SLICE.relative_to(ROOT)),
        "targets": "benchmark/slices/fm-ambient-replication-targets.json",
        "jobs": jobs,
        **(extra or {}),
    }
    ORDER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ORDER_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _task_root(job: dict) -> Path:
    return RUNS / job["run_name"] / f"{job['category']}-{job['id']}"


def _find_traj(task_root: Path) -> Path | None:
    matches = list(task_root.rglob("*.traj"))
    return matches[0] if matches else None


def infrastructure_before_execution(task_root: Path) -> bool:
    """True when the provider/harness failed before the model did any work."""
    if not task_root.exists():
        return True
    if (task_root / "output.xlsx").is_file():
        return False
    traj = _find_traj(task_root)
    if traj is None:
        return True
    sys.path.insert(0, str(ROOT / "benchmark"))
    from experiment_metrics import trajectory_metrics

    metrics = trajectory_metrics(traj)
    if (metrics.get("model_calls") or 0) > 0 or (metrics.get("tool_calls") or 0) > 0:
        return False
    text = traj.read_text(encoding="utf-8", errors="replace")
    return any(marker in text for marker in INFRA_MARKERS) or True


def _finished_orders(log_path: Path) -> set[int]:
    if not log_path.is_file():
        return set()
    done: set[int] = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("JOB-DONE ") or line.startswith("JOB-FAIL "):
            done.add(int(line.split()[1]))
    return done


def _quarantine(task_root: Path) -> Path:
    parent = task_root.parent
    index = 1
    while True:
        dest = parent / f"{task_root.name}.infra-fail-{index}"
        if not dest.exists():
            if task_root.exists():
                task_root.rename(dest)
            return dest
        index += 1


def run_job(job: dict, log) -> tuple[int, list[str]]:
    notes: list[str] = []
    result = subprocess.run(runner_command(job), cwd=ROOT)
    task_root = _task_root(job)
    if result.returncode == 0:
        return 0, notes
    if not infrastructure_before_execution(task_root):
        notes.append("meaningful-failure-kept")
        return result.returncode, notes
    dest = _quarantine(task_root)
    notes.append(f"infra-fail quarantined={dest.name}; retrying once")
    retry = subprocess.run(runner_command(job), cwd=ROOT)
    if retry.returncode != 0 and infrastructure_before_execution(_task_root(job)):
        notes.append("infra-fail-retry-also-failed; leaving for review")
    return retry.returncode, notes


def _score_run(run_name: str) -> int:
    return subprocess.call(
        [sys.executable, str(SCORER), str(RUNS / run_name), "--write-ledger"],
        cwd=ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-order-only", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip jobs already JOB-DONE/JOB-FAIL in launch.log; do not rewrite the order file.",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "benchmark"))
    from run_openrouter_slice import _load_dotenv

    _load_dotenv()
    slice_data = json.loads(SLICE.read_text())
    jobs = build_jobs(slice_data)
    commit = git_commit()
    if args.resume:
        if not ORDER_FILE.is_file():
            raise RuntimeError(f"--resume requires existing order file: {ORDER_FILE}")
        stored = json.loads(ORDER_FILE.read_text())
        jobs = stored["jobs"]
        commit = str(stored.get("git_commit") or commit)
    else:
        write_order(
            jobs,
            commit=commit,
            extra={
                "written_at": datetime.now(UTC).isoformat(),
                "worktree_dirty": git_dirty(),
            },
        )
    print(f"ORDER jobs={len(jobs)} seed={SEED} commit={commit} file={ORDER_FILE}", flush=True)
    if args.write_order_only or args.dry_run:
        for job in jobs:
            print(
                f"{job['order']:02d} {job['arm']:16} r{job['repeat']} {job['task']}",
                flush=True,
            )
        return 0

    if shutil.which("docker") is None:
        raise RuntimeError("docker is required")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY must be set")

    log_path = ORDER_FILE.parent / "launch.log"
    finished = _finished_orders(log_path) if args.resume else set()
    failures = 0
    if args.resume and log_path.is_file():
        failures = sum(
            1
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("JOB-FAIL ")
        )
    with log_path.open("a", encoding="utf-8") as log:
        for job in jobs:
            if job["order"] in finished:
                msg = f"SKIP {job['order']} already recorded in launch.log"
                print(msg, flush=True)
                log.write(msg + "\n")
                continue
            started = datetime.now(UTC).isoformat()
            header = (
                f"JOB {job['order']}/{len(jobs)} {job['arm']} r{job['repeat']} "
                f"{job['task']} run={job['run_name']} started={started}"
            )
            print(header, flush=True)
            log.write(header + "\n")
            log.flush()
            rc, notes = run_job(job, log)
            for note in notes:
                print(f"NOTE {job['order']} {note}", flush=True)
                log.write(f"NOTE {job['order']} {note}\n")
            if rc != 0:
                failures += 1
                msg = f"JOB-FAIL {job['order']} rc={rc} {job['task']} {job['arm']}"
            else:
                msg = f"JOB-DONE {job['order']} {job['task']} {job['arm']}"
            print(msg, flush=True)
            log.write(msg + "\n")
            log.flush()

        print("SCORING official eval on ten run directories", flush=True)
        score_status = 0
        run_names = sorted(
            {names[repeat] for names in ARM_RUNS.values() for repeat in REPEATS}
        )
        for run_name in run_names:
            score_status |= _score_run(run_name)
        print("SCORING replication proximal", flush=True)
        out = ORDER_FILE.parent / "proximal.json"
        score_status |= subprocess.call(
            [sys.executable, str(PROXIMAL), "--json", str(out)],
            cwd=ROOT,
        )

    print(
        f"LAUNCH done jobs={len(jobs)} failures={failures} score_rc={score_status} "
        f"order={ORDER_FILE}",
        flush=True,
    )
    return 1 if failures or score_status else 0


if __name__ == "__main__":
    raise SystemExit(main())
