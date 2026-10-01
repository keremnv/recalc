#!/usr/bin/env python3
"""Scheduler group-priority probe on Spark compiled Financial_Model:02_01.

CONTROL is the stored Spark compiled run. It is not rerun.
TREATMENT freezes that Task IR + Edit Plan (copied planning calls) and only
changes activation order: earned ProgramGroup canonicals before residual cells.
Same Spark identity, 40-call / $2.50 envelope. Measure modification gain and
resource efficiency, not exact. Do not raise the cap, add an absolute-reference
verifier, or reopen ProgramGroups.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
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
from official_score_probe import apply_glm_envelope  # noqa: E402
from score_openrouter_run import score_run  # noqa: E402

TASK = "Financial_Model:02_01"
TASK_DIR_NAME = "Financial_Model-02_01"
CONTROL_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/official-score-probe/spark-compiled"
TREATMENT_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/official-score-probe/spark-group-priority"
ARTIFACT = ROOT / "scheduler_group_priority_probe"
REPORT = ROOT / "SCHEDULER_GROUP_PRIORITY_PROBE_REPORT.md"
WORKER_ID = "spark-group-priority:Financial_Model:02_01"
ACTIVATION = "prefer_earned_program_groups"
MAX_CALLS = 40
MAX_COST = 2.50
PUBLISHED_CONTROL_MOD = 0.9938
LOCKS = TREATMENT_ROOT.parent / "locks"
PIDS = TREATMENT_ROOT.parent / "pids"
LOGS = TREATMENT_ROOT.parent / "logs"


def now() -> str:
    return datetime.now(UTC).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def spec() -> dict[str, Any]:
    return {
        "generated_at": now(),
        "claim": "scheduler_group_priority_on_frozen_authority",
        "not_exact_claim": True,
        "not_a_programgroup_repair": True,
        "task": TASK,
        "control": {
            "root": str(CONTROL_ROOT),
            "rerun": False,
            "scheduler_activation": "operation_order",
        },
        "treatment": {
            "root": str(TREATMENT_ROOT),
            "model": SPARK_COMPILED_EXPERIMENT_CONFIG.model,
            "reasoning": SPARK_COMPILED_EXPERIMENT_CONFIG.reasoning,
            "max_model_calls": MAX_CALLS,
            "max_cost_usd": MAX_COST,
            "scheduler_activation": ACTIVATION,
            "frozen": ["task_ir", "edit_plan", "authorised_target_set", "packets"],
            "live": ["retrieval", "synthesis", "schedule", "write", "score"],
        },
        "metrics": [
            "modification_accuracy",
            "modification_correct",
            "stochastic_formula_decisions",
            "translated_count",
            "residual_sessions",
            "group_sessions",
            "remaining_authorised",
            "modification_correct_per_call",
        ],
        "verdicts": [
            "GROUP_PRIORITY_MODIFICATION_GAIN",
            "GROUP_PRIORITY_RESOURCE_GAIN",
            "GROUP_PRIORITY_NO_GAIN",
            "GROUP_PRIORITY_TRADEOFF",
            "IDENTITY_FAIL",
            "PROVIDER_CENSORED",
        ],
        "exclusions": {
            "no_control_rerun": True,
            "no_cap_raise": True,
            "no_absolute_reference_verifier": True,
            "no_programgroup_reopen": True,
            "no_population_expansion": True,
        },
    }


def control_snapshot() -> dict[str, Any]:
    scores = read_json(CONTROL_ROOT / "official_scores.json")
    stored = scores["tasks"][TASK]
    result = read_json(CONTROL_ROOT / TASK_DIR_NAME / "result.json")
    schedule = result.get("schedule") or {}
    seeds = [tuple(p.get("seed") or []) for p in schedule.get("canonical_decisions") or []]
    return {
        "modification_accuracy": stored["modification_accuracy"],
        "regression_accuracy": stored["regression_accuracy"],
        "accuracy": stored["accuracy"],
        "error_message": stored.get("error_message"),
        "model_call_count": (result.get("state") or {}).get("model_call_count"),
        "provider_cost_usd": (result.get("state") or {}).get("provider_cost_usd"),
        "authorized_targets": schedule.get("authorized_targets"),
        "stochastic_formula_decisions": schedule.get("stochastic_formula_decisions"),
        "translated_count": schedule.get("translated_count"),
        "remaining_authorised": len(schedule.get("unresolved_authorised_targets") or []),
        "seeds": [list(s) for s in seeds],
        "published_control_modification_accuracy": PUBLISHED_CONTROL_MOD,
    }


def prepare_treatment_dir(*, resume: bool) -> Path:
    dest = TREATMENT_ROOT / TASK_DIR_NAME
    if dest.exists() and (dest / "output.xlsx").is_file() and not resume:
        raise RuntimeError(f"TREATMENT_ALREADY_EXISTS: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    calls = dest / "calls"
    calls.mkdir(exist_ok=True)
    source_calls = CONTROL_ROOT / TASK_DIR_NAME / "calls"
    for name in ("001_task_ir.json", "002_edit_plan.json"):
        src = source_calls / name
        dst = calls / name
        if not src.is_file():
            raise RuntimeError(f"CONTROL_PLANNING_CALL_MISSING: {src}")
        if not dst.is_file():
            shutil.copy2(src, dst)
        elif src.read_bytes() != dst.read_bytes():
            raise RuntimeError(f"FROZEN_PLANNING_CALL_DRIFT: {name}")
    return dest


def worker(*, resume: bool) -> dict[str, Any]:
    if CONTROL_ROOT.resolve() == TREATMENT_ROOT.resolve():
        raise RuntimeError("TREATMENT_ROOT_COLLIDES_WITH_CONTROL")
    lock = acquire_lock(LOCKS / "spark_group_priority_Financial_Model_02_01.lock")
    previous = None
    envelope = None
    try:
        PIDS.mkdir(parents=True, exist_ok=True)
        write_json(PIDS / "spark_group_priority_Financial_Model_02_01.json", {"worker_id": WORKER_ID, "pid": os.getpid(), "started_at": now()})
        previous = treatment.bind_compiled_identity(SPARK_COMPILED_EXPERIMENT_CONFIG)
        envelope = apply_glm_envelope()
        if treatment.MODEL != SPARK_COMPILED_EXPERIMENT_CONFIG.model:
            raise RuntimeError("SPARK_COMPILED_IDENTITY_NOT_BOUND")
        if treatment.ACTIVE_MAX_MODEL_CALLS != MAX_CALLS:
            raise RuntimeError("ENVELOPE_NOT_APPLIED")
        treatment.check_model(treatment.MODEL, treatment.REASONING, treatment.TEMPERATURE)
        dest = prepare_treatment_dir(resume=resume)
        result = treatment.run_one_task(
            TASK,
            stub=False,
            resume=True,
            output_root=TREATMENT_ROOT,
            extra_state={"scheduler_activation": ACTIVATION},
        )
        new_planning = sorted(p.name for p in (dest / "calls").glob("*_task_ir.json")) + sorted(
            p.name for p in (dest / "calls").glob("*_edit_plan.json")
        )
        if new_planning != ["001_task_ir.json", "002_edit_plan.json"]:
            raise RuntimeError(f"PLANNING_NOT_FROZEN: {new_planning}")
        write_json(dest / "worker.json", {"worker_id": WORKER_ID, "finished_at": now(), "result_status": result.get("status"), "model": treatment.MODEL})
        return result
    finally:
        if envelope is not None:
            treatment.restore_runtime(envelope)
        if previous is not None:
            treatment.restore_compiled_identity(previous)
        lock.close()


def _session_kind(seed: list[Any], groups: list[dict[str, Any]]) -> str:
    cell = tuple(seed)
    for group in groups:
        members = {tuple(x) for x in group.get("member_cells") or []}
        if cell in members or cell == tuple(group.get("canonical_cell") or []):
            return "group"
    return "residual"


def compare(control: dict[str, Any], treatment_result: dict[str, Any], treatment_scores: dict[str, Any]) -> dict[str, Any]:
    stored = (treatment_scores.get("tasks") or {}).get(TASK) or {}
    schedule = treatment_result.get("schedule") or {}
    seeds = [p.get("seed") for p in schedule.get("canonical_decisions") or []]
    groups = schedule.get("eligible_program_groups") or []
    kinds = [_session_kind(s or [], groups) for s in seeds]
    t_mod = stored.get("modification_accuracy")
    c_mod = control["modification_accuracy"]
    t_calls = (treatment_result.get("state") or {}).get("model_call_count") or 0
    c_calls = control["model_call_count"] or 1
    t_correct_per_call = None
    c_correct_per_call = None
    # Official replay uses 1125 modification cells; 0.9778 -> 1100.
    c_correct = round(float(c_mod) * 1125)
    t_correct = round(float(t_mod) * 1125) if t_mod is not None else None
    if t_calls:
        t_correct_per_call = None if t_correct is None else t_correct / t_calls
    if c_calls:
        c_correct_per_call = c_correct / c_calls
    identity_ok = treatment_result.get("status") not in {"INTEGRATION_FAILURE"} and all(
        (read_json(p).get("declared_model") == SPARK_COMPILED_EXPERIMENT_CONFIG.model)
        for p in sorted((TREATMENT_ROOT / TASK_DIR_NAME / "calls").glob("*.json"))
        if p.name.split("_", 1)[-1].split(".", 1)[0] in {"task_ir", "edit_plan", "retrieval", "synthesis"}
    )
    failures = {f.get("failure_class") for f in treatment_result.get("failure_ledger") or []}
    control_group_sessions = sum(1 for s in control["seeds"] if _session_kind(s, groups) == "group")
    if not identity_ok:
        verdict = "IDENTITY_FAIL"
    elif "MODEL_ACCESS_FAILURE" in failures or "PROVIDER_ERROR" in failures:
        verdict = "PROVIDER_CENSORED"
    elif t_mod is not None and t_mod > c_mod:
        verdict = "GROUP_PRIORITY_MODIFICATION_GAIN"
    elif t_mod is not None and t_mod < c_mod:
        verdict = "GROUP_PRIORITY_TRADEOFF" if kinds.count("group") > control_group_sessions else "GROUP_PRIORITY_NO_GAIN"
    elif t_correct_per_call and c_correct_per_call and t_correct_per_call > c_correct_per_call:
        verdict = "GROUP_PRIORITY_RESOURCE_GAIN"
    else:
        verdict = "GROUP_PRIORITY_NO_GAIN"
    return {
        "verdict": verdict,
        "control_modification_accuracy": c_mod,
        "treatment_modification_accuracy": t_mod,
        "published_control_modification_accuracy": PUBLISHED_CONTROL_MOD,
        "control_modification_correct": c_correct,
        "treatment_modification_correct": t_correct,
        "delta_modification_correct": None if t_correct is None else t_correct - c_correct,
        "control_calls": c_calls,
        "treatment_calls": t_calls,
        "control_correct_per_call": c_correct_per_call,
        "treatment_correct_per_call": t_correct_per_call,
        "control_seeds": control["seeds"],
        "treatment_seeds": seeds,
        "treatment_session_kinds": kinds,
        "treatment_group_sessions": kinds.count("group"),
        "treatment_residual_sessions": kinds.count("residual"),
        "treatment_remaining_authorised": len(schedule.get("unresolved_authorised_targets") or []),
        "control_remaining_authorised": control["remaining_authorised"],
        "treatment_translated_count": schedule.get("translated_count"),
        "treatment_error_message": stored.get("error_message"),
        "scheduler_activation": schedule.get("scheduler_activation"),
        "failures": sorted(x for x in failures if x),
        "exact_not_in_scope": True,
    }


def render_report(payload: dict[str, Any]) -> str:
    cmp = payload["comparison"]
    return f"""# Scheduler group-priority probe

Spark compiled `Financial_Model:02_01` only. Control is the stored compiled run; it was not rerun. Treatment froze Task IR + Edit Plan and changed only activation order: earned ProgramGroup canonicals before residual cells.

Generated at: {payload['generated_at']}
Verdict: `{cmp['verdict']}`

## Scores

| Arm | Modification | Calls | Remaining authorised | Seeds |
| --- | ---: | ---: | ---: | --- |
| Stored Spark compiled (control) | {cmp['control_modification_accuracy']} | {cmp['control_calls']} | {cmp['control_remaining_authorised']} | {cmp['control_seeds']} |
| Group-first scheduler (treatment) | {cmp['treatment_modification_accuracy']} | {cmp['treatment_calls']} | {cmp['treatment_remaining_authorised']} | {cmp['treatment_seeds']} |
| Published SWE-agent control (reference, not rerun) | {cmp['published_control_modification_accuracy']} | — | — | — |

Delta modification cells: {cmp['delta_modification_correct']} (of 1125).
Correct per call: control {cmp['control_correct_per_call']}, treatment {cmp['treatment_correct_per_call']}.

Treatment sessions: {cmp['treatment_group_sessions']} group, {cmp['treatment_residual_sessions']} residual.
First official error: {cmp['treatment_error_message']!r}.

Exact is out of scope. Authority misses and EPS `$C$10` still independently block exact.

## Policy

Default scheduler stays `operation_order`. This probe opted into `prefer_earned_program_groups` only.
Cap stayed 40 / $2.50. No absolute-reference verifier. ProgramGroups unchanged.
"""


def score_treatment() -> dict[str, Any]:
    score_run(TREATMENT_ROOT, model_name="official-score-spark-group-priority", metadata_tolerant=True)
    return read_json(TREATMENT_ROOT / "official_scores.json")


def launch() -> dict[str, Any]:
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    TREATMENT_ROOT.mkdir(parents=True, exist_ok=True)
    log = LOGS / "spark_group_priority_Financial_Model_02_01.log"
    command = [sys.executable, str(Path(__file__)), "worker"]
    handle = log.open("ab")
    proc = subprocess.Popen(command, cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT)
    write_json(ARTIFACT / "launch.json", {"pid": proc.pid, "started_at": now(), "log": str(log), "output_root": str(TREATMENT_ROOT)})
    return {"pid": proc.pid, "log": str(log)}


def wait(timeout: int = 7200) -> dict[str, Any]:
    deadline = time.time() + timeout
    dest = TREATMENT_ROOT / TASK_DIR_NAME
    while time.time() < deadline:
        worker = dest / "worker.json"
        result = dest / "result.json"
        if worker.is_file() and result.is_file():
            return read_json(result)
        time.sleep(15)
    raise TimeoutError("GROUP_PRIORITY_WORKER_TIMEOUT")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["spec", "worker", "launch", "wait", "score", "report", "run"])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "spec":
        write_json(ARTIFACT / "spec.json", spec())
        print(json.dumps(spec(), indent=2))
        return 0
    if args.command == "worker":
        result = worker(resume=args.resume)
        print(json.dumps({"status": result.get("status"), "calls": (result.get("state") or {}).get("model_call_count")}, indent=2))
        return 0
    if args.command == "launch":
        print(json.dumps(launch(), indent=2))
        return 0
    if args.command == "wait":
        result = wait()
        print(json.dumps({"status": result.get("status")}, indent=2))
        return 0
    if args.command == "score":
        print(json.dumps(score_treatment().get("tasks", {}).get(TASK), indent=2))
        return 0
    if args.command == "report":
        control = control_snapshot()
        treatment_result = read_json(TREATMENT_ROOT / TASK_DIR_NAME / "result.json")
        scores = read_json(TREATMENT_ROOT / "official_scores.json")
        payload = {"generated_at": now(), "spec": spec(), "control": control, "comparison": compare(control, treatment_result, scores)}
        write_json(ARTIFACT / "comparison.json", payload)
        REPORT.write_text(render_report(payload), encoding="utf-8")
        print(payload["comparison"]["verdict"])
        return 0
    if args.command == "run":
        write_json(ARTIFACT / "spec.json", spec())
        launched = launch()
        result = wait()
        scores = score_treatment()
        control = control_snapshot()
        payload = {"generated_at": now(), "spec": spec(), "launch": launched, "control": control, "comparison": compare(control, result, scores)}
        write_json(ARTIFACT / "comparison.json", payload)
        REPORT.write_text(render_report(payload), encoding="utf-8")
        print(json.dumps({"verdict": payload["comparison"]["verdict"], "treatment_mod": payload["comparison"]["treatment_modification_accuracy"]}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
