#!/usr/bin/env python3
"""Forced calc_query sidecar on Financial_Model:05_01 vs frozen official C0."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark")]

from compiled_context_sidecar_ab import (  # noqa: E402
    ARTIFACT,
    CALL_LIMIT,
    COST_LIMIT,
    EXECUTION_TIMEOUT,
    IDENTITY,
    MODEL,
    RUNNER,
    RUNS,
    SCORER,
    TIMEOUT,
    identity_audit,
    ledger_row,
    official_metrics,
    parse_calc_query_calls,
    prompt_hashes,
    source_xlsx,
    write_json,
)
from run_openrouter_slice import _load_dotenv  # noqa: E402

SLICE = ROOT / "benchmark/slices/compiled-context-forced-05_01.json"
CONTROL_RUN = "spark-sidecar-c0-Financial_Model-05_01-r1"
FORCED_RUN = "spark-sidecar-c1f-Financial_Model-05_01-r1"
TASK = "Financial_Model:05_01"
REPORT = ROOT / "COMPILED_CONTEXT_FORCED_05_01_REPORT.md"
FORCED_CONFIG = ROOT / "benchmark/sweagent/spreadsheet-control-compiled-context-forced.yaml"


def now() -> str:
    return datetime.now(UTC).isoformat()


def score_run(run_name: str) -> dict:
    run_root = RUNS / run_name
    official = run_root / "official_scores.json"
    if not official.is_file():
        subprocess.run(
            [sys.executable, str(SCORER), str(run_root), "--write-ledger"],
            cwd=ROOT,
            check=False,
        )
    payload = json.loads(official.read_text(encoding="utf-8")) if official.is_file() else {}
    return official_metrics({"official": (payload.get("tasks") or {}).get(TASK) or payload})


def launch_forced() -> int:
    _load_dotenv()
    cache = ARTIFACT / "job_cache" / FORCED_RUN
    cache.mkdir(parents=True, exist_ok=True)
    xlsx = source_xlsx("Financial_Model", "05_01")
    digest = hashlib.sha256(xlsx.read_bytes()).hexdigest()[:24]
    compiled = ARTIFACT / "world_cache" / "Financial_Model-05_01"
    dest = cache / digest
    if compiled.is_dir() and not (dest / "workbook.sqlite").is_file():
        shutil.copytree(compiled, dest, dirs_exist_ok=True)
    env = os.environ.copy()
    env["CALC_QUERY_HOST_CACHE"] = str(cache)
    cmd = [
        sys.executable,
        str(RUNNER),
        "--slice",
        str(SLICE),
        "--run-name",
        FORCED_RUN,
        "--task",
        TASK,
        "--model",
        MODEL,
        "--control-compiled-context-forced",
        "--call-limit",
        str(CALL_LIMIT),
        "--cost-limit",
        str(COST_LIMIT),
        "--timeout",
        str(TIMEOUT),
        "--execution-timeout",
        str(EXECUTION_TIMEOUT),
        "--max-requeries",
        "2",
        "--no-score",
    ]
    print("LAUNCH", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode


def write_report(c0: dict, c1f: dict, adoption: dict, identity: dict) -> None:
    hashes = prompt_hashes()
    forced_prompt = FORCED_CONFIG.read_text(encoding="utf-8")
    lines = [
        "# Forced compiled-context sidecar: Financial_Model:05_01",
        "",
        f"Generated at: {now()}",
        "",
        "This is not the optional C0/C1 A/B. C1F **requires** a first-pass `calc_query` on the official scaffold. Control is the frozen sidecar C0 run, not rerun.",
        "",
        "## Why this task",
        "",
        "- Optional C1 on `05_01` adopted `calc_query` then died on the Docker `parents[5]` wrapper crash, so that trajectory is not a model result.",
        "- C0 hit the 40-call envelope.",
        "- `13_05` is the wrong forced candidate: all four optional pairs already matched gold `I20:M20` without `calc_query`.",
        "- `15_05` is a negative-structure task. `09_04` C0 failed, but optional C1 was still running on that task id.",
        "",
        "## Identity",
        "",
        f"- Declared/request: `{MODEL}` / `openrouter/{MODEL}`",
        f"- Generation: temp 0, top_p 1, tool_choice auto, reasoning_effort unset. Envelope 40/${COST_LIMIT:.2f}.",
        f"- Identity ok: `{identity.get('ok')}`",
        f"- Source: `{IDENTITY['source_run']}`",
        "",
        "## Scores",
        "",
        "| Arm | run | modification | regression | exact | usable | calls | calc_query |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| C0 | `{CONTROL_RUN}` | {c0.get('modification')} | {c0.get('regression')} | {c0.get('exact')} | {c0.get('usable')} | {c0.get('model_calls')} | n/a |",
        f"| C1F | `{FORCED_RUN}` | {c1f.get('modification')} | {c1f.get('regression')} | {c1f.get('exact')} | {c1f.get('usable')} | {c1f.get('model_calls')} | {adoption.get('n_calls')} {adoption.get('classification')} |",
        "",
        f"C1F modes: `{adoption.get('modes')}` first_turn={adoption.get('first_turn')} uptake={adoption.get('evidence_uptake')}",
        "",
        f"C0 first miss: `{c0.get('error_message')}`. C1F first miss: `{c1f.get('error_message')}`.",
        "",
        "## Prompt hashes",
        "",
        f"- C0 system: `{hashes['c0_system_sha256']}`",
        f"- C1 optional instance: `{hashes['c1_instance_sha256']}`",
        f"- C1F config present: `{FORCED_CONFIG.is_file()}`",
        f"- Forced prompt requires calc_query before edits: `{'You must call `calc_query` at least once before any workbook modification' in forced_prompt}`",
        "",
        "Causal claim is only this C0/C1F pair on `Financial_Model:05_01`.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    launch_only = "--launch-only" in sys.argv
    score_only = "--score-only" in sys.argv
    if not score_only:
        code = launch_forced()
        if code != 0:
            print(f"FORCED_RUN_RC {code}", flush=True)
        if launch_only:
            return 0 if code == 0 else code
    c0_metrics = score_run(CONTROL_RUN)
    c1f_metrics = score_run(FORCED_RUN)
    task_root = RUNS / FORCED_RUN / "Financial_Model-05_01"
    adoption = parse_calc_query_calls(next(iter(task_root.rglob("*.traj")), None) if task_root.exists() else None)
    identity = identity_audit(
        {
            "run_name": FORCED_RUN,
            "category": "Financial_Model",
            "id": "05_01",
            "arm": "C1",
            "repeat": 1,
            "task": TASK,
        }
    )
    c0_ledger = ledger_row(RUNS / CONTROL_RUN / "Financial_Model-05_01")
    c1f_ledger = ledger_row(task_root)
    c0_metrics = {**c0_metrics, "model_calls": c0_ledger.get("model_calls")}
    c1f_metrics = {**c1f_metrics, "model_calls": c1f_ledger.get("model_calls")}
    payload = {
        "task": TASK,
        "control_run": CONTROL_RUN,
        "forced_run": FORCED_RUN,
        "c0": c0_metrics,
        "c1f": c1f_metrics,
        "adoption": adoption,
        "identity": identity,
        "written_at": now(),
    }
    write_json(ARTIFACT / "forced_05_01.json", payload)
    write_report(c0_metrics, c1f_metrics, adoption, identity)
    print(json.dumps({"c0": c0_metrics, "c1f": c1f_metrics, "used": adoption.get("used")}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
