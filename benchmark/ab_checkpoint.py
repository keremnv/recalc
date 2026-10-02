#!/usr/bin/env python3
"""Thin-architecture system checkpoint: H0 (default scaffold) vs H1 (frozen
thin architecture: +search/periods/inspect note+shim, +transparent runtime).
24 tasks x n=1 x 2 arms = 48 runs; discordant cells replicated separately.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AB = PROJECT_ROOT / "research/history/thin_architecture_checkpoint"
RUNNER = PROJECT_ROOT / "benchmark" / "ab_local_runner.py"
SHIM = PROJECT_ROOT / "benchmark" / "inspection_helpers" / "lx_helpers.py"
ORDER_SEED = 77031

NOTE = """## Optional inspection helpers (available in this environment)

A Python module `lx_helpers` is importable from your working directory. You may
use it or ignore it entirely; ordinary Python/openpyxl/view_xlsx all work as usual.
- `lx_helpers.periods(workbook_path, sheet=None)` returns mechanically recovered
  period/header coordinates (e.g. FY24 -> column letter). It does not say which
  periods the task needs.
- `lx_helpers.search(workbook_path, pattern, regex=False, sheet=None)` returns
  exact occurrences (sheet/address/value/formula) in sheet order. No ranking.
- `lx_helpers.inspect(workbook_path, sheet, range, with_styles=False)` returns
  values/formulas/dtypes for an explicitly requested range and reports paging
  when its bounded result is truncated.
- `lx_helpers.inspect_ranges(workbook_path, ranges)` reads several explicitly
  requested ranges in one freshness-checked call, using compact cell rows and
  a total output budget.
Example: `import lx_helpers; lx_helpers.search("input.xlsx", "revenue")`
"""


def tasks() -> list[dict]:
    return json.load(open(AB / "population.json"))["tasks"]


def task_src(task: str) -> Path:
    cat, _, tid = task.partition(":")
    ds = json.loads((PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" /
                     "data" / cat / "dataset.json").read_text())
    item = next(d for d in ds if str(d["id"]) == tid)
    return PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data" / cat / item["spreadsheet_path"]


def reset_live(task: str, arm: str, workdir: Path) -> Path:
    live = workdir / task.replace(":", "_")
    if live.exists():
        shutil.rmtree(live)
    live.mkdir(parents=True)
    shutil.copy2(task_src(task), live / "input.xlsx")
    if arm == "H1":
        shutil.copy2(SHIM, live / "lx_helpers.py")
    return live


def dry_run(task: str, arm: str, live: Path) -> dict:
    cmd = [sys.executable, str(RUNNER), "--task", task, "--arm", arm,
           "--workdir", str(live),
           "--archive-dir", str(AB / "audit_tmp" / f"{task}_{arm}".replace(":", "_")),
           "--dry-run"] + (["--note-file", str(AB / "_h1_note.txt")] if arm == "H1" else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"dry-run failed {task} {arm}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def write_frozen() -> None:
    (AB / "_h1_note.txt").write_text(NOTE)
    import platform
    lo = subprocess.run(["soffice", "--headless", "--version"], capture_output=True,
                        text=True, timeout=60)
    json.dump({
        "soffice_executable": lo.returncode == 0,
        "soffice_version": lo.stdout.strip(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "scoring": "official evaluation.py WITH open_spreadsheet.py LO refresh, both arms",
        "lo_policy": "both arms may use soffice identically; no exclusion needed",
    }, open(AB / "environment.json", "w"), indent=1)
    json.dump({
        "name": "thin-architecture-system-checkpoint",
        "h0": "default coding-agent scaffold: Python/openpyxl/bash/view_xlsx/submit",
        "h1": "H0 + optional search/periods/inspect (note+shim) + transparent mutation runtime",
        "model_config": "unchanged from recent live component experiments (z-ai/glm-5.3-flash, t=0, top_p=1, call cap 40, $0.25/instance)",
        "n": 1, "cohorts": {"A-representative": 12, "B-exposure": 12},
        "material_discordance": {"output_mismatch": True, "abs_mod_ge": 0.10,
                                 "abs_reg_ge": 0.05, "corruption": True},
        "rerun_policy": "one matched repetition per discordant task; third rep if same-direction repeat",
        "forbidden": ["new helpers", "architecture changes", "rescue paths"],
    }, open(AB / "spec.json", "w"), indent=1)


def identity_audit() -> dict:
    diffs = []
    for t in tasks():
        task = t["task_id"]
        live0 = reset_live(task, "H0", AB / "work")
        c0 = dry_run(task, "H0", live0)
        live1 = reset_live(task, "H1", AB / "work")
        c1 = dry_run(task, "H1", live1)
        for field in ("system_hash", "tool_order", "model", "temperature",
                      "top_p", "max_tokens", "tool_choice", "parallel_tool_calls",
                      "input_hash"):
            if c0[field] != c1[field]:
                diffs.append({"task": task, "field": field})
        if c1["instance_hash"] == c0["instance_hash"]:
            diffs.append({"task": task, "field": "note_has_no_effect"})
        if "lx_helpers.py" not in c1["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_missing_H1"})
        if "lx_helpers.py" in c0["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_leaked_H0"})
    audit = {"differences_unintended": diffs, "pass": not diffs,
             "intended_differences": ["instance_hash", "request_body.user_len",
                                      "workdir lx_helpers.py (H1 only)",
                                      "instance prompt + usage note (H1 only)",
                                      "transparent runtime wrap (H1 only, invisible)"]}
    json.dump(audit, open(AB / "identity_manifest.json", "w"), indent=1)
    print("identity audit:", "PASS" if audit["pass"] else f"FAIL {diffs}")
    return audit


def run_all() -> None:
    import os
    base = dict(os.environ)
    base["PYTHONDONTWRITEBYTECODE"] = "1"
    base["AB_FIDELITY_LOG"] = str(AB / "runtime_fidelity.jsonl")
    base["AB_FRESHNESS_LOG"] = str(AB / "freshness_checks.jsonl")
    base["AB_FULL_TRANSCRIPT"] = "1"
    base["LX_REPO_ROOT"] = str(PROJECT_ROOT)
    rng = random.Random(ORDER_SEED)
    order = []
    for t in tasks():
        task = t["task_id"]
        arms = ["H0", "H1"]
        rng.shuffle(arms)
        for arm in arms:
            live = reset_live(task, arm, AB / "work")
            arch = AB / "reps" / f"{task.replace(':', '_')}_{arm}"
            if arch.exists():
                shutil.rmtree(arch)
            cmd = [sys.executable, "-B", str(RUNNER), "--task", task,
                   "--arm", arm, "--workdir", str(live), "--archive-dir", str(arch)
                   ] + (["--note-file", str(AB / "_h1_note.txt")] if arm == "H1" else [])
            start = time.time()
            print(f"=== {task} {arm} ===", flush=True)
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=1500, env=base)
            print((proc.stdout + proc.stderr)[-600:], flush=True)
            order.append({"task": task, "arm": arm, "start_epoch": start,
                          "cohort": t["cohort"]})
            json.dump(order, open(AB / "run_order.json", "w"), indent=1)
    print("CHECKPOINT_RUNS_DONE")


def main() -> None:
    write_frozen()
    audit = identity_audit()
    if not audit["pass"]:
        sys.exit(2)
    if "--audit-only" in sys.argv:
        return
    run_all()


if __name__ == "__main__":
    main()
