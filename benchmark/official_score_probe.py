#!/usr/bin/env python3
"""Small official-score experiment vs published SpreadsheetBench 2.

Three frozen control-census-sixty tasks run as isolated compiled GLM 5.3 Flash
/ high workers (40 calls, $2.50 each). One extra observation uses Muse Spark
1.3 Contributor on Financial_Model:02_01 through the LibreCalc SWE-agent
harness. A published-control Spark run of the same task is retained if it
already completed. Workers are separate OS processes with unique output roots
and exclusive locks so SIGALRM, SQLite, SWE-agent trajectories, and LibreOffice
scoring cannot collide.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "src")]

import matched_compiled_treatment as treatment  # noqa: E402
from experiment_config import (  # noqa: E402
    AUTHORITATIVE_EXPERIMENT_CONFIG,
    SPARK_COMPILED_EXPERIMENT_CONFIG,
)

GLM_SLICE = ROOT / "benchmark/slices/official-score-three.json"
SPARK_SLICE = ROOT / "benchmark/slices/official-score-spark-fm-02_01.json"
SPARK_HARNESS_SLICE = ROOT / "benchmark/slices/official-score-spark-fm-02_01-librecalc.json"
CONTROL_SLICE = ROOT / "benchmark/slices/control-census-sixty.json"
ARTIFACT = ROOT / "official_score_probe"
REPORT = ROOT / "OFFICIAL_SCORE_PROBE_REPORT.md"
RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/official-score-probe"
GLM_ROOT = RUNS / "glm-compiled"
SPARK_COMPILED_ROOT = RUNS / "spark-compiled"
DISCRIMINATOR_REPORT = ROOT / "OFFICIAL_SCORE_COMPILED_MODEL_DISCRIMINATOR_REPORT.md"
SPARK_RUN_NAME = "official-score-spark-1.3-contributor-fm-02_01"
SPARK_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter" / SPARK_RUN_NAME
SPARK_HARNESS_RUN_NAME = "official-score-spark-1.3-contributor-fm-02_01-librecalc"
SPARK_HARNESS_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter" / SPARK_HARNESS_RUN_NAME
OPENROUTER_RUNNER = ROOT / "benchmark/run_openrouter_slice.py"
LIBRECALC_CONFIG = ROOT / "benchmark/sweagent/spreadsheet.yaml"

GLM_TASKS = ("Template:01_02", "Financial_Model:02_01", "Debugging:01_01")
SPARK_TASK = "Financial_Model:02_01"
SPARK_MODEL = "meta/muse-spark-1.3-contributor"
SPARK_CONTROL_WORKER = f"spark:{SPARK_TASK}"
SPARK_HARNESS_WORKER = f"spark-harness:{SPARK_TASK}"
GLM_CALLS = 40
GLM_COST_USD = 2.50
SPARK_CALLS = 50
SPARK_COST_USD = 2.50
SPARK_COMPILED_WORKER_IDS = tuple(f"spark-compiled:{key}" for key in GLM_TASKS)
BURNED = frozenset({"Template:02_05", "Financial_Model:06_01"})
WORKER_IDS = (*[f"glm:{key}" for key in GLM_TASKS], SPARK_CONTROL_WORKER, SPARK_HARNESS_WORKER)
TERMINAL_STATUSES = frozenset({"COMPLETED", "DRY_COMPLETED", "NON_MODEL_FAILURE", "INTEGRATION_FAILURE", "WORKER_FAILURE"})


def now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def task_dir_name(task_key: str) -> str:
    return task_key.replace(":", "-")


def spark_compiled_task_dir(task_key: str) -> Path:
    return SPARK_COMPILED_ROOT / task_dir_name(task_key)


def glm_task_dir(task_key: str) -> Path:
    return GLM_ROOT / task_dir_name(task_key)


def spark_task_dir() -> Path:
    return SPARK_ROOT / task_dir_name(SPARK_TASK)


def spark_harness_task_dir() -> Path:
    return SPARK_HARNESS_ROOT / task_dir_name(SPARK_TASK)


def worker_lock_path(worker_id: str) -> Path:
    return RUNS / "locks" / f"{worker_id.replace(':', '_')}.lock"


def pid_path(worker_id: str) -> Path:
    return RUNS / "pids" / f"{worker_id.replace(':', '_')}.json"


def log_path(worker_id: str) -> Path:
    return RUNS / "logs" / f"{worker_id.replace(':', '_')}.log"


def acquire_lock(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError(f"WORKER_LOCK_HELD: {path}") from exc
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} at={now()}\n")
    handle.flush()
    return handle


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def load_slice_tasks(path: Path) -> list[str]:
    payload = read_json(path)
    return [f"{row['category']}:{row['id']}" for row in payload["tasks"]]


def published_control_scores() -> dict[str, Any]:
    payload = read_json(treatment.PREP / "control_scores.json")
    tasks = payload.get("tasks") or {}
    return {key: tasks[key] for key in GLM_TASKS if key in tasks}


def spec() -> dict[str, Any]:
    glm_slice = read_json(GLM_SLICE)
    spark_slice = read_json(SPARK_SLICE)
    harness_slice = read_json(SPARK_HARNESS_SLICE)
    population = {f"{row['category']}:{row['id']}" for row in read_json(CONTROL_SLICE)["tasks"]}
    selected = load_slice_tasks(GLM_SLICE)
    spark_tasks = load_slice_tasks(SPARK_SLICE)
    harness_tasks = load_slice_tasks(SPARK_HARNESS_SLICE)
    missing = [key for key in selected if key not in population]
    burned = [key for key in selected if key in BURNED]
    if missing:
        raise RuntimeError(f"SLICE_NOT_IN_FROZEN_POPULATION: {missing}")
    if burned:
        raise RuntimeError(f"SLICE_CONTAINS_BURNED_TASKS: {burned}")
    if selected != list(GLM_TASKS):
        raise RuntimeError(f"SLICE_TASKS_DRIFT: {selected}")
    if spark_tasks != [SPARK_TASK] or harness_tasks != [SPARK_TASK]:
        raise RuntimeError(f"SPARK_SLICE_MUST_BE_SINGLE_FM_02_01: {spark_tasks} {harness_tasks}")
    if spark_slice.get("model") != SPARK_MODEL or harness_slice.get("model") != SPARK_MODEL:
        raise RuntimeError(f"SPARK_MODEL_DRIFT: {spark_slice.get('model')} {harness_slice.get('model')}")
    if glm_slice.get("model") != AUTHORITATIVE_EXPERIMENT_CONFIG.model:
        raise RuntimeError(f"GLM_MODEL_DRIFT: {glm_slice.get('model')}")
    payload = {
        "generated_at": now(),
        "claim": "system_benchmark_vs_published_control",
        "not_a_causal_scaffold_claim": True,
        "glm": {
            "model": AUTHORITATIVE_EXPERIMENT_CONFIG.model,
            "reasoning": AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning,
            "max_model_calls_per_task": GLM_CALLS,
            "max_cost_usd_per_task": GLM_COST_USD,
            "tasks": selected,
            "output_root": str(GLM_ROOT),
            "architecture": "compiled_matched_treatment",
        },
        "spark_extra": {
            "model": SPARK_MODEL,
            "task": SPARK_TASK,
            "scaffold": "librecalc_sweagent_harness",
            "config": str(LIBRECALC_CONFIG.relative_to(ROOT)),
            "max_tool_calls": SPARK_CALLS,
            "max_cost_usd": SPARK_COST_USD,
            "output_root": str(SPARK_HARNESS_ROOT),
            "label": "extra_comparison_not_causal",
        },
        "spark_control_kept": {
            "model": SPARK_MODEL,
            "task": SPARK_TASK,
            "scaffold": "published_spreadsheetbench2_control",
            "config": str(treatment.CONTROL_CONFIG.relative_to(ROOT)),
            "max_tool_calls": SPARK_CALLS,
            "max_cost_usd": SPARK_COST_USD,
            "output_root": str(SPARK_ROOT),
            "label": "kept_because_already_ran",
            "rerun": False,
        },
        "published_control_reference": published_control_scores(),
        "isolation": {
            "one_os_process_per_task": True,
            "unique_output_roots": True,
            "exclusive_file_locks": True,
            "shared_prep_is_read_only": True,
            "scoring": "sequential_after_workers",
            "compiled_runner_max_workers": 1,
        },
        "exclusions": {
            "no_fm20": True,
            "no_template_02_05": True,
            "no_financial_model_06_01": True,
            "no_published_control_rerun": True,
            "no_new_frontend_ir": True,
        },
    }
    write_json(ARTIFACT / "spec.json", payload)
    return payload


def gates() -> dict[str, Any]:
    freeze = treatment.validate_freeze() if (treatment.PREP / "freeze.json").exists() else {"pass": False, "reason": "freeze.json missing"}
    rows = treatment.task_rows()
    population = {
        "pass": len(rows) == 60,
        "count": len(rows),
        "contains_slice": all(key in {row["task_key"] for row in rows} for key in GLM_TASKS),
    }
    environment = treatment.ensure_environment()
    needed = {key: False for key in GLM_TASKS}
    for record in environment.get("records", []):
        if record.get("task_key") in needed:
            needed[record["task_key"]] = record.get("status") != "TREATMENT_INPUT_UNRUNNABLE"
    checks = {
        "freeze": freeze,
        "population": population,
        "environment_slice": {"pass": all(needed.values()), "tasks": needed},
        "neutrality": (treatment.read_json(treatment.PREP / "neutrality_results.json") if (treatment.PREP / "neutrality_results.json").exists() else {"status": "MISSING"}),
        "dry_run": (treatment.read_json(treatment.PREP / "dry_run_results.json") if (treatment.PREP / "dry_run_results.json").exists() else {"status": "MISSING"}),
        "request_identity": {
            "pass": AUTHORITATIVE_EXPERIMENT_CONFIG.model == "z-ai/glm-5.3-flash"
            and AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning == "high"
        },
        "sweagent": {"pass": (ROOT / "benchmark-data/SpreadsheetBench-2/SWE-agent/.venv/bin/sweagent").is_file()},
        "docker_image": _docker_image_present(),
    }
    checks["freeze_artifacts"] = {
        "pass": not checks["freeze"].get("missing_artifacts") and bool(checks["freeze"].get("manifest")),
        "hash_drift": checks["freeze"].get("hash_drift") or [],
        "note": "Historical freeze hashes are diagnostic. Request identity is AUTHORITATIVE_EXPERIMENT_CONFIG / high, not the archived low/50/$4 freeze.",
    }
    checks["pass"] = all(
        [
            bool(checks["freeze_artifacts"].get("pass")),
            bool(checks["population"].get("pass") and checks["population"].get("contains_slice")),
            bool(checks["environment_slice"].get("pass")),
            checks["neutrality"].get("status") == "PASS",
            checks["dry_run"].get("status") == "PASS",
            bool(checks["request_identity"].get("pass")),
            bool(checks["sweagent"].get("pass")),
            bool(checks["docker_image"].get("pass")),
        ]
    )
    return checks


def _docker_image_present() -> dict[str, Any]:
    completed = subprocess.run(
        ["docker", "images", "-q", "spreadsheetbench-v2"],
        check=False,
        capture_output=True,
        text=True,
    )
    image_id = (completed.stdout or "").strip()
    return {"pass": completed.returncode == 0 and bool(image_id), "image_id": image_id[:12]}


def apply_glm_envelope() -> dict[str, Any]:
    previous = treatment.configure_runtime(max_model_calls=GLM_CALLS, max_cost_usd=GLM_COST_USD)
    if treatment.ACTIVE_MAX_MODEL_CALLS != GLM_CALLS or treatment.ACTIVE_MAX_COST_USD != GLM_COST_USD:
        raise RuntimeError("GLM_ENVELOPE_NOT_APPLIED")
    if AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning != "high":
        raise RuntimeError("REASONING_MUST_REMAIN_HIGH")
    return previous


def prepare() -> dict[str, Any]:
    RUNS.mkdir(parents=True, exist_ok=True)
    GLM_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": now(), "spec": spec(), "gates": gates()}
    if not payload["gates"].get("pass"):
        write_json(ARTIFACT / "prepare.json", payload)
        raise RuntimeError(f"OFFICIAL_SCORE_PREPARE_FAILED: {json.dumps(payload['gates'], ensure_ascii=False)[:2000]}")
    write_json(ARTIFACT / "prepare.json", payload)
    return payload


def _write_pid(worker_id: str, extra: dict[str, Any] | None = None) -> None:
    write_json(pid_path(worker_id), {"worker_id": worker_id, "pid": os.getpid(), "started_at": now(), **(extra or {})})


def glm_worker(task_key: str, *, resume: bool = False) -> dict[str, Any]:
    if task_key not in GLM_TASKS:
        raise SystemExit(f"invalid glm task: {task_key}")
    worker_id = f"glm:{task_key}"
    lock = acquire_lock(worker_lock_path(worker_id))
    try:
        _write_pid(worker_id, {"task": task_key, "kind": "glm_compiled"})
        apply_glm_envelope()
        treatment.check_model(treatment.MODEL, treatment.REASONING, treatment.TEMPERATURE)
        result = treatment.run_one_task(task_key, stub=False, resume=resume, output_root=GLM_ROOT)
        write_json(glm_task_dir(task_key) / "worker.json", {"worker_id": worker_id, "finished_at": now(), "result_status": result.get("status")})
        return result
    finally:
        lock.close()


def spark_compiled_worker(task_key: str, *, resume: bool = False) -> dict[str, Any]:
    if task_key not in GLM_TASKS:
        raise SystemExit(f"invalid spark-compiled task: {task_key}")
    worker_id = f"spark-compiled:{task_key}"
    lock = acquire_lock(worker_lock_path(worker_id))
    previous = None
    try:
        _write_pid(worker_id, {"task": task_key, "kind": "spark_compiled_discriminator"})
        previous = treatment.bind_compiled_identity(SPARK_COMPILED_EXPERIMENT_CONFIG)
        apply_glm_envelope()
        if treatment.MODEL != SPARK_COMPILED_EXPERIMENT_CONFIG.model:
            raise RuntimeError("SPARK_COMPILED_IDENTITY_NOT_BOUND")
        if treatment.REASONING != AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning:
            raise RuntimeError("SPARK_COMPILED_REASONING_DRIFT")
        treatment.check_model(treatment.MODEL, treatment.REASONING, treatment.TEMPERATURE)
        SPARK_COMPILED_ROOT.mkdir(parents=True, exist_ok=True)
        result = treatment.run_one_task(task_key, stub=False, resume=resume, output_root=SPARK_COMPILED_ROOT)
        write_json(
            spark_compiled_task_dir(task_key) / "worker.json",
            {"worker_id": worker_id, "finished_at": now(), "result_status": result.get("status"), "model": treatment.MODEL},
        )
        return result
    finally:
        if previous is not None:
            treatment.restore_compiled_identity(previous)
        lock.close()


def spark_worker() -> dict[str, Any]:
    return _sweagent_spark_worker(
        worker_id=SPARK_CONTROL_WORKER,
        kind="spark_control_kept",
        slice_path=SPARK_SLICE,
        run_name=SPARK_RUN_NAME,
        output_root=SPARK_ROOT,
        task_dir=spark_task_dir(),
        extra_args=["--control"],
        label="kept_because_already_ran",
    )


def spark_harness_worker() -> dict[str, Any]:
    return _sweagent_spark_worker(
        worker_id=SPARK_HARNESS_WORKER,
        kind="spark_librecalc_harness",
        slice_path=SPARK_HARNESS_SLICE,
        run_name=SPARK_HARNESS_RUN_NAME,
        output_root=SPARK_HARNESS_ROOT,
        task_dir=spark_harness_task_dir(),
        extra_args=["--config", str(LIBRECALC_CONFIG)],
        label="extra_comparison_not_causal",
    )


def _sweagent_spark_worker(
    *,
    worker_id: str,
    kind: str,
    slice_path: Path,
    run_name: str,
    output_root: Path,
    task_dir: Path,
    extra_args: list[str],
    label: str,
) -> dict[str, Any]:
    lock = acquire_lock(worker_lock_path(worker_id))
    try:
        _write_pid(worker_id, {"task": SPARK_TASK, "kind": kind})
        command = [
            sys.executable,
            str(OPENROUTER_RUNNER),
            "--slice",
            str(slice_path),
            "--run-name",
            run_name,
            *extra_args,
            "--model",
            SPARK_MODEL,
            "--call-limit",
            str(SPARK_CALLS),
            "--cost-limit",
            str(SPARK_COST_USD),
            "--timeout",
            "3600",
            "--skip-existing",
            "--no-score",
        ]
        completed = subprocess.run(command, cwd=ROOT, check=False)
        payload = {
            "worker_id": worker_id,
            "task": SPARK_TASK,
            "model": SPARK_MODEL,
            "kind": kind,
            "label": label,
            "return_code": completed.returncode,
            "output_root": str(output_root),
            "finished_at": now(),
            "status": "COMPLETED" if completed.returncode == 0 else "WORKER_FAILURE",
        }
        write_json(task_dir / "worker.json", payload)
        return payload
    finally:
        lock.close()


def _spawn(worker_id: str, args: list[str]) -> dict[str, Any]:
    log = log_path(worker_id)
    log.parent.mkdir(parents=True, exist_ok=True)
    pid_file = pid_path(worker_id)
    if pid_file.exists():
        existing = read_json(pid_file)
        if pid_alive(int(existing.get("pid") or 0)):
            raise RuntimeError(f"WORKER_ALREADY_RUNNING: {worker_id} pid={existing['pid']}")
    handle = log.open("ab")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *args],
        cwd=ROOT,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    write_json(pid_file, {"worker_id": worker_id, "pid": process.pid, "started_at": now(), "spawned": True})
    return {"worker_id": worker_id, "pid": process.pid, "log": str(log), "command": args}


def glm_finished(task_key: str) -> bool:
    result = glm_task_dir(task_key) / "result.json"
    if not result.exists():
        return False
    return read_json(result).get("status") in TERMINAL_STATUSES


def spark_finished() -> bool:
    marker = spark_task_dir() / "worker.json"
    if not marker.exists():
        return False
    return read_json(marker).get("status") in TERMINAL_STATUSES


def spark_harness_finished() -> bool:
    marker = spark_harness_task_dir() / "worker.json"
    if not marker.exists():
        return False
    return read_json(marker).get("status") in TERMINAL_STATUSES


def launch(*, resume: bool = False) -> dict[str, Any]:
    coordinator = acquire_lock(RUNS / "locks" / "coordinator.lock")
    try:
        prepared = prepare()
        workers = []
        glm_args_tail = ["--resume"] if resume else []
        for task_key in GLM_TASKS:
            if resume and glm_finished(task_key):
                workers.append({"worker_id": f"glm:{task_key}", "pid": None, "skipped": True, "reason": "already_terminal"})
                continue
            workers.append(_spawn(f"glm:{task_key}", ["glm-worker", "--task", task_key, *glm_args_tail]))
        if resume and spark_finished():
            workers.append({"worker_id": SPARK_CONTROL_WORKER, "pid": None, "skipped": True, "reason": "already_terminal"})
        else:
            workers.append(_spawn(SPARK_CONTROL_WORKER, ["spark-worker"]))
        if resume and spark_harness_finished():
            workers.append({"worker_id": SPARK_HARNESS_WORKER, "pid": None, "skipped": True, "reason": "already_terminal"})
        else:
            workers.append(_spawn(SPARK_HARNESS_WORKER, ["spark-harness-worker"]))
        payload = {
            "generated_at": now(),
            "status": "WORKERS_STARTED",
            "prepare_pass": prepared["gates"]["pass"],
            "workers": workers,
            "glm_output_root": str(GLM_ROOT),
            "spark_control_output_root": str(SPARK_ROOT),
            "spark_harness_output_root": str(SPARK_HARNESS_ROOT),
            "note": "Spark 1.3 Contributor on the LibreCalc harness is the extra observation. The published-control Spark run is kept if it already completed.",
        }
        write_json(ARTIFACT / "launch.json", payload)
        write_json(RUNS / "launch.json", payload)
        return payload
    finally:
        coordinator.close()


def launch_harness() -> dict[str, Any]:
    coordinator = acquire_lock(RUNS / "locks" / "coordinator.lock")
    try:
        if spark_harness_finished():
            payload = {"generated_at": now(), "status": "ALREADY_TERMINAL", "worker_id": SPARK_HARNESS_WORKER}
            write_json(ARTIFACT / "harness_launch.json", payload)
            return payload
        worker = _spawn(SPARK_HARNESS_WORKER, ["spark-harness-worker"])
        payload = {
            "generated_at": now(),
            "status": "HARNESS_WORKER_STARTED",
            "worker": worker,
            "spark_control_output_root": str(SPARK_ROOT),
            "spark_harness_output_root": str(SPARK_HARNESS_ROOT),
            "control_kept": spark_finished(),
        }
        write_json(ARTIFACT / "harness_launch.json", payload)
        return payload
    finally:
        coordinator.close()


def spark_compiled_finished(task_key: str) -> bool:
    result = spark_compiled_task_dir(task_key) / "result.json"
    if not result.exists():
        return False
    return read_json(result).get("status") in TERMINAL_STATUSES


def launch_spark_compiled(*, resume: bool = False) -> dict[str, Any]:
    coordinator = acquire_lock(RUNS / "locks" / "coordinator.lock")
    try:
        checks = gates()
        if not checks.get("pass"):
            raise RuntimeError(f"SPARK_COMPILED_PREPARE_FAILED: {json.dumps({k: checks.get(k) for k in ('pass', 'request_identity', 'environment_slice')}, ensure_ascii=False)}")
        SPARK_COMPILED_ROOT.mkdir(parents=True, exist_ok=True)
        workers = []
        for task_key in GLM_TASKS:
            worker_id = f"spark-compiled:{task_key}"
            if resume and spark_compiled_finished(task_key):
                workers.append({"worker_id": worker_id, "pid": None, "skipped": True, "reason": "already_terminal"})
                continue
            args = ["spark-compiled-worker", "--task", task_key]
            if resume:
                args.append("--resume")
            workers.append(_spawn(worker_id, args))
        payload = {
            "generated_at": now(),
            "status": "SPARK_COMPILED_WORKERS_STARTED",
            "claim": "model_on_fixed_compiled_architecture",
            "not_a_scaffold_comparison": True,
            "model": SPARK_COMPILED_EXPERIMENT_CONFIG.model,
            "reasoning": SPARK_COMPILED_EXPERIMENT_CONFIG.reasoning,
            "max_model_calls_per_task": GLM_CALLS,
            "max_cost_usd_per_task": GLM_COST_USD,
            "output_root": str(SPARK_COMPILED_ROOT),
            "glm_baseline_root": str(GLM_ROOT),
            "do_not_rerun": ["published_control", "glm_compiled", "spark_control", "spark_librecalc_harness"],
            "workers": workers,
        }
        write_json(ARTIFACT / "spark_compiled_launch.json", payload)
        return payload
    finally:
        coordinator.close()


def spark_compiled_status() -> dict[str, Any]:
    rows = []
    for task_key in GLM_TASKS:
        worker_id = f"spark-compiled:{task_key}"
        record: dict[str, Any] = {"worker_id": worker_id, "task": task_key}
        path = pid_path(worker_id)
        if path.exists():
            record.update(read_json(path))
            record["alive"] = pid_alive(int(record.get("pid") or 0))
        else:
            record["alive"] = False
        result = spark_compiled_task_dir(task_key) / "result.json"
        state = spark_compiled_task_dir(task_key) / "state.json"
        if result.exists():
            payload = read_json(result)
            record["status"] = payload.get("status")
            record["model_call_count"] = (payload.get("state") or {}).get("model_call_count")
            record["provider_cost_usd"] = (payload.get("state") or {}).get("provider_cost_usd")
        elif state.exists():
            payload = read_json(state)
            record["status"] = payload.get("status") or ("INTERRUPTED" if not record.get("alive") else "RUNNING")
            record["model_call_count"] = payload.get("model_call_count")
        rows.append(record)
    payload = {"generated_at": now(), "workers": rows, "all_finished": all(row.get("status") in TERMINAL_STATUSES for row in rows)}
    write_json(ARTIFACT / "spark_compiled_status.json", payload)
    return payload


def _call_usage(task_dir: Path) -> dict[str, Any]:
    prompt = completion = 0
    identity_ok = True
    identity_failures = []
    stages: list[dict[str, Any]] = []
    for path in sorted((task_dir / "calls").glob("*.json")):
        rec = read_json(path)
        usage = rec.get("usage") or {}
        prompt += int(usage.get("prompt_tokens") or 0)
        completion += int(usage.get("completion_tokens") or 0)
        if rec.get("failure_class") == "REQUEST_IDENTITY_FAILURE" or rec.get("identity_failure"):
            identity_ok = False
            identity_failures.append({"call": rec.get("call_index_within_task"), "detail": rec.get("detail")})
        declared = rec.get("declared_model") or rec.get("model")
        wire = rec.get("request_model") or (rec.get("request_body") or {}).get("model")
        returned = rec.get("response_model")
        if declared and wire and declared != wire:
            identity_ok = False
            identity_failures.append({"call": rec.get("call_index_within_task"), "mismatch": "declared_wire", "declared": declared, "wire": wire})
        if returned not in (None, wire, declared) and rec.get("failure_class") != "REQUEST_IDENTITY_FAILURE":
            identity_ok = False
        stages.append({
            "index": rec.get("call_index_within_task"),
            "stage": rec.get("stage"),
            "failure_class": rec.get("failure_class"),
            "declared_model": declared,
            "request_model": wire,
            "response_model": returned,
        })
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "identity_ok": identity_ok,
        "identity_failures": identity_failures,
        "stages": stages,
    }


def compiled_loss_boundary(result: dict[str, Any], *, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    compiler = (result.get("compiler") or {}).get("status")
    plan = (result.get("edit_plan") or {}).get("status")
    ledger = result.get("failure_ledger") or []
    if usage and not usage.get("identity_ok"):
        return {"terminal_stage": "identity", "boundary": "REQUEST_IDENTITY_FAILURE", "earliest": "REQUEST_IDENTITY_FAILURE"}
    provider = next((f.get("failure_class") for f in ledger if f.get("failure_class") in {"MODEL_ACCESS_FAILURE", "PROVIDER_TIMEOUT", "PROVIDER_ERROR", "REQUEST_IDENTITY_FAILURE"}), None)
    if provider:
        return {"terminal_stage": "provider", "boundary": provider, "earliest": provider}
    if compiler not in {"OK"}:
        return {"terminal_stage": "task_ir", "boundary": compiler, "earliest": "task_ir"}
    if plan not in {"VALID_PLAN", "EMPTY_EXPANSION"}:
        return {"terminal_stage": "edit_plan", "boundary": plan, "earliest": "edit_plan"}
    first = next((item for item in ledger if item.get("failure_class")), None)
    if first:
        cls = str(first.get("failure_class"))
        stage = "resource" if cls in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"} else "actuation"
        return {"terminal_stage": stage, "boundary": cls, "earliest": cls, "detail": first}
    return {"terminal_stage": "completed", "boundary": None, "earliest": None}


def compiled_task_snapshot(root: Path, task_key: str) -> dict[str, Any]:
    task_dir = root / task_dir_name(task_key)
    result = read_json(task_dir / "result.json") if (task_dir / "result.json").exists() else {}
    state = read_json(task_dir / "state.json") if (task_dir / "state.json").exists() else {}
    usage = _call_usage(task_dir) if (task_dir / "calls").exists() else {"prompt_tokens": 0, "completion_tokens": 0, "identity_ok": False, "identity_failures": [], "stages": []}
    boundary = compiled_loss_boundary(result, usage=usage)
    started = state.get("started_at")
    finished = result.get("finished_at") or state.get("finished_at")
    return {
        "task": task_key,
        "status": result.get("status") or state.get("status"),
        "model": state.get("model"),
        "compiler_status": (result.get("compiler") or state.get("task_ir") or {}).get("status"),
        "edit_plan_status": (result.get("edit_plan") or state.get("edit_plan") or {}).get("status"),
        "failure_ledger": result.get("failure_ledger") or state.get("failure_ledger") or [],
        "model_call_count": (result.get("state") or {}).get("model_call_count") or state.get("model_call_count") or 0,
        "provider_cost_usd": (result.get("state") or {}).get("provider_cost_usd") if (result.get("state") or {}).get("provider_cost_usd") is not None else state.get("provider_cost_usd") or 0.0,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "identity_ok": usage["identity_ok"],
        "identity_failures": usage["identity_failures"],
        "authorised_targets": len(state.get("authorised_target_set") or []),
        "unresolved_authorised_targets": next((item.get("remaining_count") for item in (result.get("failure_ledger") or []) if "remaining_count" in item), None),
        "started_at": started,
        "finished_at": finished,
        "output_exists": (task_dir / "output.xlsx").exists(),
        **boundary,
    }


def discriminator_verdict(comparisons: list[dict[str, Any]]) -> str:
    if not comparisons:
        return "PROVIDER_CENSORED"
    if all(not row["spark"].get("identity_ok") or row["spark"].get("terminal_stage") == "provider" for row in comparisons):
        return "PROVIDER_CENSORED"
    moved = []
    shared = []
    for row in comparisons:
        glm_b = row["glm"].get("earliest")
        spark_b = row["spark"].get("earliest")
        spark_stage = row["spark"].get("terminal_stage")
        if spark_stage in {"provider", "identity"}:
            continue
        if row["task"] == "Financial_Model:02_01":
            if glm_b == "edit_plan" and row["spark"].get("edit_plan_status") == "VALID_PLAN":
                moved.append(row["task"])
            elif glm_b == spark_b:
                shared.append(row["task"])
            else:
                moved.append(row["task"]) if spark_b != glm_b else shared.append(row["task"])
        elif row["task"] == "Debugging:01_01":
            glm_unsup = glm_b == "UNSUPPORTED_EDIT_KIND"
            spark_unsup = spark_b == "UNSUPPORTED_EDIT_KIND"
            if glm_unsup and not spark_unsup:
                moved.append(row["task"])
            elif glm_unsup and spark_unsup:
                shared.append(row["task"])
            else:
                (moved if glm_b != spark_b else shared).append(row["task"])
        elif row["task"] == "Template:01_02":
            glm_cap = glm_b == "TASK_MODEL_CALL_LIMIT"
            spark_exact = (row.get("spark_official") or {}).get("accuracy")
            glm_unresolved = row["glm"].get("unresolved_authorised_targets")
            spark_unresolved = row["spark"].get("unresolved_authorised_targets")
            if spark_exact not in (None, 0.0) or (glm_cap and spark_b != "TASK_MODEL_CALL_LIMIT") or (
                glm_unresolved is not None and spark_unresolved is not None and spark_unresolved < glm_unresolved
            ):
                moved.append(row["task"])
            else:
                shared.append(row["task"])
        elif glm_b == spark_b:
            shared.append(row["task"])
        else:
            moved.append(row["task"])
    if moved and shared:
        return "MIXED_MODEL_ARCHITECTURE_LIMITS"
    if moved:
        return "MODEL_SENSITIVITY_SUPPORTED"
    return "ARCHITECTURE_LIMIT_SHARED_ACROSS_MODELS"


def score_spark_compiled() -> dict[str, Any]:
    status = spark_compiled_status()
    spark_scores = _score_root(SPARK_COMPILED_ROOT, "official-score-spark-compiled-three") if any((spark_compiled_task_dir(key) / "output.xlsx").exists() for key in GLM_TASKS) else {"status": "NO_SPARK_COMPILED_OUTPUT"}
    glm_scores = read_json(GLM_ROOT / "official_scores.json") if (GLM_ROOT / "official_scores.json").exists() else {"status": "MISSING_GLM_BASELINE"}
    comparisons = []
    for key in GLM_TASKS:
        glm_snap = compiled_task_snapshot(GLM_ROOT, key)
        spark_snap = compiled_task_snapshot(SPARK_COMPILED_ROOT, key)
        glm_off = ((glm_scores.get("tasks") or {}).get(key) if isinstance(glm_scores.get("tasks"), dict) else None) or {}
        spark_off = ((spark_scores.get("tasks") or {}).get(key) if isinstance(spark_scores.get("tasks"), dict) else None) or {}
        comparisons.append({
            "task": key,
            "glm": glm_snap,
            "spark": spark_snap,
            "glm_official": glm_off,
            "spark_official": spark_off,
        })
    verdict = discriminator_verdict(comparisons)
    payload = {
        "generated_at": now(),
        "claim": "model_on_fixed_compiled_architecture",
        "not_a_scaffold_comparison": True,
        "verdict": verdict,
        "worker_status": status,
        "glm_official_scores": glm_scores,
        "spark_compiled_official_scores": spark_scores,
        "comparisons": comparisons,
        "integrity": {
            "spark_identity_ok": all(row["spark"].get("identity_ok") for row in comparisons),
            "glm_identity_ok": all(row["glm"].get("identity_ok") for row in comparisons),
        },
    }
    write_json(ARTIFACT / "spark_compiled_scores.json", payload)
    write_json(SPARK_COMPILED_ROOT / "discriminator.json", payload)
    return payload


def report_spark_compiled(payload: dict[str, Any] | None = None) -> str:
    payload = payload or (read_json(ARTIFACT / "spark_compiled_scores.json") if (ARTIFACT / "spark_compiled_scores.json").exists() else score_spark_compiled())
    lines = [
        "# Compiled model discriminator",
        "",
        "Muse Spark 1.3 Contributor vs GLM 5.3 Flash on the **same compiled architecture** and frozen three-task official-score slice. Existing Spark control and Spark LibreCalc-harness observations are not part of this A/B.",
        "",
        f"Generated at: {payload.get('generated_at')}",
        f"Primary verdict: `{payload.get('verdict')}`",
        f"Spark identity: {'PASS' if (payload.get('integrity') or {}).get('spark_identity_ok') else 'FAIL'}",
        "",
        "## Per-task comparison",
        "",
        "| Task | GLM exact / mod / reg | Spark compiled exact / mod / reg | GLM calls / $ / tokens | Spark compiled calls / $ / tokens | GLM terminal | Spark compiled terminal |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("comparisons") or []:
        glm_off = row.get("glm_official") or {}
        spark_off = row.get("spark_official") or {}
        glm = row.get("glm") or {}
        spark = row.get("spark") or {}
        lines.append(
            "| `{task}` | {ge}/{gm}/{gr} | {se}/{sm}/{sr} | {gc} / ${gcost:.4f} / {gpt}+{gct} | {sc} / ${scost:.4f} / {spt}+{sct} | `{gb}` | `{sb}` |".format(
                task=row["task"],
                ge=glm_off.get("accuracy"),
                gm=glm_off.get("modification_accuracy"),
                gr=glm_off.get("regression_accuracy"),
                se=spark_off.get("accuracy"),
                sm=spark_off.get("modification_accuracy"),
                sr=spark_off.get("regression_accuracy"),
                gc=glm.get("model_call_count"),
                gcost=float(glm.get("provider_cost_usd") or 0),
                gpt=glm.get("prompt_tokens"),
                gct=glm.get("completion_tokens"),
                sc=spark.get("model_call_count"),
                scost=float(spark.get("provider_cost_usd") or 0),
                spt=spark.get("prompt_tokens"),
                sct=spark.get("completion_tokens"),
                gb=glm.get("earliest") or glm.get("boundary"),
                sb=spark.get("earliest") or spark.get("boundary"),
            )
        )
    lines.extend(
        [
            "",
            "## GLM boundaries under test",
            "",
            "- `Template:01_02`: GLM hit the 40-call cap with 181 authorised targets remaining.",
            "- `Financial_Model:02_01`: GLM failed at Edit Plan parse after two calls.",
            "- `Debugging:01_01`: GLM terminated with `UNSUPPORTED_EDIT_KIND` after two calls.",
            "",
            "## Reading",
            "",
            "- This is a model-on-fixed-architecture discriminator, not a scaffold comparison.",
            "- Do not use the earlier Spark LibreCalc-harness 1/1 as evidence about Spark on the compiled architecture.",
            "- A Spark success here would show the compiled architecture can cash out differently with another similarly priced model. It does not show population-level superiority or causal scaffold gain.",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    DISCRIMINATOR_REPORT.write_text(text, encoding="utf-8")
    existing = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    pointer = "\n## Compiled model discriminator\n\nSee `OFFICIAL_SCORE_COMPILED_MODEL_DISCRIMINATOR_REPORT.md`.\n"
    if "OFFICIAL_SCORE_COMPILED_MODEL_DISCRIMINATOR_REPORT.md" not in existing:
        REPORT.write_text(existing.rstrip() + pointer, encoding="utf-8")
    return text


def wait_spark_compiled_and_score(*, poll_seconds: int = 30, timeout_seconds: int = 8 * 3600) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = spark_compiled_status()
        finished = [row["worker_id"] for row in status["workers"] if row.get("status") in TERMINAL_STATUSES]
        for row in status["workers"]:
            if row.get("status") in TERMINAL_STATUSES:
                continue
            if row.get("alive"):
                continue
            raise RuntimeError(f"WORKER_DIED_INCOMPLETE: {row['worker_id']} status={row.get('status')}")
        if len(finished) == len(SPARK_COMPILED_WORKER_IDS):
            scored = score_spark_compiled()
            report_spark_compiled(scored)
            return {"status": "COMPLETE", "verdict": scored.get("verdict"), "scores": scored}
        time.sleep(poll_seconds)
    raise TimeoutError("SPARK_COMPILED_WORKERS_TIMEOUT")


def worker_status() -> dict[str, Any]:
    rows = []
    for worker_id in WORKER_IDS:
        record: dict[str, Any] = {"worker_id": worker_id}
        path = pid_path(worker_id)
        if path.exists():
            record.update(read_json(path))
            record["alive"] = pid_alive(int(record.get("pid") or 0))
        else:
            record["alive"] = False
        if worker_id.startswith("glm:"):
            task_key = worker_id.split(":", 1)[1]
            state = glm_task_dir(task_key) / "state.json"
            result = glm_task_dir(task_key) / "result.json"
            if result.exists():
                payload = read_json(result)
                record["status"] = payload.get("status")
                record["model_call_count"] = (payload.get("state") or {}).get("model_call_count")
                record["provider_cost_usd"] = (payload.get("state") or {}).get("provider_cost_usd")
            elif state.exists():
                payload = read_json(state)
                record["status"] = payload.get("status") or ("INTERRUPTED" if not record.get("alive") else "RUNNING")
                record["model_call_count"] = payload.get("model_call_count")
        else:
            task_dir = spark_harness_task_dir() if worker_id == SPARK_HARNESS_WORKER else spark_task_dir()
            marker = task_dir / "worker.json"
            if marker.exists():
                payload = read_json(marker)
                record["status"] = payload.get("status")
                record["return_code"] = payload.get("return_code")
            elif task_dir.exists():
                record["status"] = "INTERRUPTED" if not record.get("alive") else "RUNNING"
        rows.append(record)
    complete = all(row.get("status") in TERMINAL_STATUSES for row in rows)
    payload = {"generated_at": now(), "workers": rows, "all_finished": complete}
    write_json(ARTIFACT / "status.json", payload)
    return payload


def _score_root(run_root: Path, model_name: str) -> dict[str, Any]:
    return treatment.scorer(run_root, model_name, refresh=True)


def score() -> dict[str, Any]:
    status = worker_status()
    glm_scores = _score_root(GLM_ROOT, "official-score-glm-compiled-three") if any((glm_task_dir(key) / "output.xlsx").exists() for key in GLM_TASKS) else {"status": "NO_GLM_OUTPUT"}
    spark_control_scores = _score_root(SPARK_ROOT, "official-score-spark-1.3-contributor-control-fm-02_01") if (spark_task_dir() / "output.xlsx").exists() else {"status": "NO_SPARK_CONTROL_OUTPUT"}
    spark_harness_scores = _score_root(SPARK_HARNESS_ROOT, "official-score-spark-1.3-contributor-librecalc-fm-02_01") if (spark_harness_task_dir() / "output.xlsx").exists() else {"status": "NO_SPARK_HARNESS_OUTPUT"}
    payload = {
        "generated_at": now(),
        "worker_status": status,
        "glm_official_scores": glm_scores,
        "spark_control_official_scores": spark_control_scores,
        "spark_harness_official_scores": spark_harness_scores,
        "spark_official_scores": spark_harness_scores,
        "published_control_reference": published_control_scores(),
        "spark_label": "extra_comparison_not_causal",
        "spark_control_label": "kept_because_already_ran",
    }
    write_json(ARTIFACT / "scores.json", payload)
    write_json(GLM_ROOT / "official_score_probe_scores.json", payload)
    return payload


def _accuracy(pack: dict[str, Any], task_key: str) -> float | None:
    tasks = pack.get("tasks") if isinstance(pack, dict) else None
    if not isinstance(tasks, dict):
        return None
    row = tasks.get(task_key)
    if not isinstance(row, dict):
        return None
    value = row.get("accuracy")
    return None if value is None else float(value)


def report(scores: dict[str, Any] | None = None) -> str:
    scores = scores or (read_json(ARTIFACT / "scores.json") if (ARTIFACT / "scores.json").exists() else score())
    published = scores.get("published_control_reference") or published_control_scores()
    glm_pack = scores.get("glm_official_scores") or {}
    spark_control_pack = scores.get("spark_control_official_scores") or {}
    spark_harness_pack = scores.get("spark_harness_official_scores") or scores.get("spark_official_scores") or {}
    lines = [
        "# Official-score probe",
        "",
        "Prospectively specified three-task compiled GLM 5.3 Flash / `high` run against the published SpreadsheetBench 2 control reference. Muse Spark 1.3 Contributor on `Financial_Model:02_01` uses the LibreCalc harness. The published-control Spark run is retained because it already completed; it is not a causal scaffold claim.",
        "",
        f"Generated at: {now()}",
        "",
        "## Envelope",
        "",
        f"- GLM compiled: `{AUTHORITATIVE_EXPERIMENT_CONFIG.model}` / `{AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning}`, {GLM_CALLS} calls, ${GLM_COST_USD:.2f} per task",
        f"- Spark LibreCalc harness: `{SPARK_MODEL}`, {SPARK_CALLS} calls, ${SPARK_COST_USD:.2f}",
        f"- Spark published control (kept): `{SPARK_MODEL}`, {SPARK_CALLS} calls, ${SPARK_COST_USD:.2f}",
        "",
        "## Official accuracy",
        "",
        "| Task | Published control | GLM compiled | Spark 1.3 control (kept) | Spark 1.3 LibreCalc harness |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key in GLM_TASKS:
        pub = (published.get(key) or {}).get("accuracy")
        glm = _accuracy(glm_pack, key)
        spark_control = _accuracy(spark_control_pack, key) if key == SPARK_TASK else "—"
        spark_harness = _accuracy(spark_harness_pack, key) if key == SPARK_TASK else "—"
        lines.append(f"| `{key}` | {pub} | {glm} | {spark_control} | {spark_harness} |")
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- GLM vs published control is the system benchmark claim.",
            "- Spark on the LibreCalc harness vs GLM on `Financial_Model:02_01` is an extra model observation, not a matched causal arm.",
            "- The Spark published-control run is kept only because it already ran; do not treat it as the authorised extra arm.",
            "- Do not rerun the published GLM control merely to recreate an already stored number.",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    return text


def wait_and_score(*, poll_seconds: int = 30, timeout_seconds: int = 8 * 3600) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = worker_status()
        finished = []
        running = []
        for row in status["workers"]:
            if row.get("status") in TERMINAL_STATUSES:
                finished.append(row["worker_id"])
            elif row.get("alive"):
                running.append(row["worker_id"])
            else:
                raise RuntimeError(f"WORKER_DIED_INCOMPLETE: {row['worker_id']} status={row.get('status')}")
        if len(finished) == len(WORKER_IDS):
            scored = score()
            report(scored)
            return {"status": "COMPLETE", "scores": scored}
        time.sleep(poll_seconds)
    raise TimeoutError("OFFICIAL_SCORE_WORKERS_TIMEOUT")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("spec")
    sub.add_parser("prepare")
    launch_p = sub.add_parser("launch")
    launch_p.add_argument("--resume", action="store_true")
    sub.add_parser("status")
    glm = sub.add_parser("glm-worker")
    glm.add_argument("--task", required=True)
    glm.add_argument("--resume", action="store_true")
    sub.add_parser("spark-worker")
    sub.add_parser("spark-harness-worker")
    sub.add_parser("launch-harness")
    spark_c = sub.add_parser("spark-compiled-worker")
    spark_c.add_argument("--task", required=True)
    spark_c.add_argument("--resume", action="store_true")
    launch_sc = sub.add_parser("launch-spark-compiled")
    launch_sc.add_argument("--resume", action="store_true")
    sub.add_parser("spark-compiled-status")
    sub.add_parser("score-spark-compiled")
    sub.add_parser("report-spark-compiled")
    wait_sc = sub.add_parser("wait-spark-compiled")
    wait_sc.add_argument("--poll-seconds", type=int, default=30)
    sub.add_parser("score")
    sub.add_parser("report")
    wait = sub.add_parser("wait-and-score")
    wait.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    if args.command == "spec":
        print(json.dumps(spec(), indent=2))
        return 0
    if args.command == "prepare":
        print(json.dumps(prepare()["gates"], indent=2))
        return 0
    if args.command == "launch":
        print(json.dumps(launch(resume=args.resume), indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(worker_status(), indent=2))
        return 0
    if args.command == "glm-worker":
        result = glm_worker(args.task, resume=args.resume)
        print(json.dumps({"task": args.task, "status": result.get("status"), "state": result.get("state")}, indent=2))
        return 0 if result.get("status") in {"COMPLETED", "DRY_COMPLETED", "NON_MODEL_FAILURE"} else 1
    if args.command == "spark-worker":
        result = spark_worker()
        print(json.dumps(result, indent=2))
        return int(result.get("return_code") or 0)
    if args.command == "spark-harness-worker":
        result = spark_harness_worker()
        print(json.dumps(result, indent=2))
        return int(result.get("return_code") or 0)
    if args.command == "launch-harness":
        print(json.dumps(launch_harness(), indent=2))
        return 0
    if args.command == "spark-compiled-worker":
        result = spark_compiled_worker(args.task, resume=args.resume)
        print(json.dumps({"task": args.task, "status": result.get("status"), "state": result.get("state"), "model": result.get("model") or treatment.MODEL}, indent=2))
        return 0 if result.get("status") in {"COMPLETED", "DRY_COMPLETED", "NON_MODEL_FAILURE"} else 1
    if args.command == "launch-spark-compiled":
        print(json.dumps(launch_spark_compiled(resume=args.resume), indent=2))
        return 0
    if args.command == "spark-compiled-status":
        print(json.dumps(spark_compiled_status(), indent=2))
        return 0
    if args.command == "score-spark-compiled":
        payload = score_spark_compiled()
        print(json.dumps({"generated_at": payload.get("generated_at"), "verdict": payload.get("verdict"), "integrity": payload.get("integrity")}, indent=2))
        return 0
    if args.command == "report-spark-compiled":
        print(report_spark_compiled())
        return 0
    if args.command == "wait-spark-compiled":
        print(json.dumps(wait_spark_compiled_and_score(poll_seconds=args.poll_seconds), indent=2)[:4000])
        return 0
    if args.command == "score":
        payload = score()
        glm_pack = payload.get("glm_official_scores") or {}
        spark_pack = payload.get("spark_official_scores") or {}
        print(json.dumps({
            "generated_at": payload.get("generated_at"),
            "spark_label": payload.get("spark_label"),
            "glm_status": glm_pack.get("status") if isinstance(glm_pack, dict) else glm_pack,
            "spark_status": spark_pack.get("status") if isinstance(spark_pack, dict) else spark_pack,
        }, indent=2))
        return 0
    if args.command == "report":
        print(report())
        return 0
    if args.command == "wait-and-score":
        print(json.dumps(wait_and_score(poll_seconds=args.poll_seconds), indent=2)[:4000])
        return 0
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
