#!/usr/bin/env python3
"""Run the frozen repaired treatment sequentially for the bridge probe.

This is deliberately a runner-only diagnostic.  It does not change prompts,
compiler stages, scheduler rules, or model settings.  The only operational
property it adds is one benchmark task at a time, so provider concurrency
failures cannot contaminate the replication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
import fm_resource_feasibility as f  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def frozen_check() -> dict:
    freeze_path = f.RUN_ROOT / "freeze.json"
    freeze = f.read_json(freeze_path, {})
    expected = {
        "model": f.MODEL,
        "temperature": f.TEMPERATURE,
        "top_p": f.TOP_P,
        "reasoning_request_value": f.REASONING,
        "maximum_stochastic_calls_per_task": f.NATURAL_CALL_CEILING,
        "per_task_cost_ceiling_usd": f.NATURAL_COST_CEILING,
        "frontend_timeout_seconds": f.FRONTEND_TIMEOUT_SECONDS,
    }
    mismatches = {
        key: {"expected": value, "actual": freeze.get(key)}
        for key, value in expected.items()
        if freeze.get(key) != value
    }
    if not freeze_path.exists():
        raise RuntimeError(f"missing frozen resource probe config: {freeze_path}")
    if mismatches:
        raise RuntimeError(f"frozen config mismatch: {json.dumps(mismatches, sort_keys=True)}")
    freeze_sha256 = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    return {
        "freeze_path": str(freeze_path),
        "freeze_sha256": freeze_sha256,
        "model_config": expected,
        "provider_policy": f.PROVIDER_POLICY,
        "no_task_concurrency": True,
    }


def run(clean_root: Path, *, resume: bool) -> dict:
    freeze = frozen_check()
    clean_root.mkdir(parents=True, exist_ok=True)
    manifest_path = clean_root / "clean_sequential_manifest.json"
    manifest = f.read_json(manifest_path, {}) if resume else {}
    # Index by the short frozen task id (01_01), matching ``tasks`` below.
    # The row retains the fully-qualified task key for traceability.
    rows = {row["task_id"]: row for row in (manifest.get("rows") or []) if isinstance(row, dict) and row.get("task_id")}
    tasks = f._selected_ids()
    old_root = f.REPAIRED_LIVE
    f.REPAIRED_LIVE = clean_root
    try:
        for task in tasks:
            task_key = f.key(task)
            task_dir = clean_root / task_key.replace(":", "-")
            prior = rows.get(task_key, {})
            result_path = task_dir / "result.json"
            state_path = task_dir / "state.json"
            # A completed task is never rerun during resume.  Incomplete state
            # is handed back to the frozen state machine, which resumes only
            # persisted calls and uses no semantic-quality retry.
            if prior.get("status") in {"COMPLETED", "NON_MODEL_FAILURE", "INTEGRATION_FAILURE"} and result_path.exists():
                continue
            print(f"CLEAN_SEQUENTIAL_START {task}", flush=True)
            result = f.run_treatment_task(task, resume=resume)
            row = {
                "task_id": task,
                "task": task_key,
                "status": result.get("status"),
                "result_path": str(result_path),
                "state_path": str(state_path),
                "finished_at": result.get("finished_at"),
            }
            rows[task_key] = row
            manifest = {
                "status": "IN_PROGRESS",
                "started_at": manifest.get("started_at", now()),
                "updated_at": now(),
                "task_order": tasks,
                "completed_count": sum(1 for t in tasks if t in rows),
                "max_workers": 1,
                "freeze": freeze,
                "rows": [rows[t] for t in tasks if t in rows],
            }
            write_json(manifest_path, manifest)
            print(f"CLEAN_SEQUENTIAL_DONE {task} {row['status']}", flush=True)
    finally:
        f.REPAIRED_LIVE = old_root
    final = {
        "status": "COMPLETE" if all(t in rows for t in tasks) else "INCOMPLETE",
        "started_at": manifest.get("started_at", now()),
        "updated_at": now(),
        "task_order": tasks,
        "completed_count": sum(1 for t in tasks if t in rows),
        "max_workers": 1,
        "freeze": freeze,
        "rows": [rows[t] for t in tasks if t in rows],
    }
    write_json(manifest_path, final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=f.LIVE / "repaired_treatment_clean_sequential",
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run(args.output_root, resume=args.resume)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
