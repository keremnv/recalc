#!/usr/bin/env python3
"""Stage B: inspection-efficiency probe. C0 (transparent runtime, ordinary
tools) vs C1 (+ optional lx_helpers). 9 tasks x n=1 x 2 arms = 18 runs.
Population frozen from measured inspection volume; identity audit first.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AB = PROJECT_ROOT / "research/history/inspection_efficiency_ab"
RUNNER = PROJECT_ROOT / "benchmark" / "ab_local_runner.py"
SHIM = PROJECT_ROOT / "benchmark" / "inspection_helpers" / "lx_helpers.py"

TASKS = [
    # (task, views, pyexecs) measured in stored Stage-1/Stage-A trajectories
    ("Debugging:02_06", 72, 69),
    ("Financial_Model:01_01", 59, 30),
    ("Debugging:04_01", 34, 0),
    ("Financial_Model:13_05", 31, 33),
    ("Template:01_02", 16, 17),
    ("Template:06_12", 13, 57),
    ("Template:01_07", 13, 25),
    ("Financial_Model:02_01", 12, 9),
    ("Debugging:05_02", 8, 11),
]

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
  a total output budget. It does not infer which ranges are relevant.
Example: `import lx_helpers; lx_helpers.search("input.xlsx", "revenue")`
"""


def task_src(task: str) -> Path:
    cat, _, tid = task.partition(":")
    ds = json.loads((PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" /
                     "data" / cat / "dataset.json").read_text())
    item = next(d for d in ds if str(d["id"]) == tid)
    return PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data" / cat / item["spreadsheet_path"]


def reset_live(task: str, arm: str) -> Path:
    live = AB / "work" / task.replace(":", "_")
    if live.exists():
        shutil.rmtree(live)
    live.mkdir(parents=True)
    shutil.copy2(task_src(task), live / "input.xlsx")
    if arm == "C1":
        shutil.copy2(SHIM, live / "lx_helpers.py")
    return live


def dry_run(task: str, arm: str, live: Path) -> dict:
    cmd = [sys.executable, str(RUNNER), "--task", task, "--arm", arm,
           "--workdir", str(live),
           "--archive-dir", str(AB / "audit_tmp" / f"{task}_{arm}".replace(":", "_")),
           "--dry-run"] + (["--note-file", str(AB / "_c1_note.txt")] if arm == "C1" else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"dry-run failed {task} {arm}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def write_frozen() -> None:
    AB.mkdir(parents=True, exist_ok=True)
    (AB / "_c1_note.txt").write_text(NOTE)
    json.dump({
        "name": "inspection-efficiency-ab-stage-b",
        "gated_on": "research/history/targeted_runtime_replication/verdict.json == "
                     "RUNTIME_CAPABILITY_PRESERVATION_SUPPORTED",
        "arms": {"C0": "transparent runtime + ordinary Python/openpyxl/view_xlsx",
                 "C1": "C0 + optional lx_helpers (periods/search/inspect); "
                       "usage note appended to instance prompt; nothing else changes"},
                 "helpers": ["periods", "search", "inspect", "inspect_ranges"],
        "forbidden": ["references()", "target recommendations", "likely formulas",
                      "dependency closure", "correctness claims", "semantic roles",
                      "mandatory syntax", "tool removal"],
        "freshness": "every call rehashes workbook; rebuild-on-mismatch; "
                     "workbook/index/query generations logged; fail closed",
        "n": 1, "discordant_cell_policy": "repeat discordant cells once before concluding",
    }, open(AB / "spec.json", "w"), indent=1)
    json.dump({"tasks": [{"task_id": t, "measured_views": v, "measured_pyexecs": p}
                         for t, v, p in TASKS],
               "selection": "ranked by measured inspection volume in stored "
                            "Stage-1/Stage-A trajectories; no gold-peeking"},
              open(AB / "population.json", "w"), indent=1)


def identity_audit() -> dict:
    diffs, intended = [], ["instance_hash", "workdir_listing", "request_body.user_len"]
    for task, _, _ in TASKS:
        live0 = reset_live(task, "C0")
        c0 = dry_run(task, "C0", live0)
        live1 = reset_live(task, "C1")
        c1 = dry_run(task, "C1", live1)
        for field in ("system_hash", "tool_order", "model", "temperature",
                      "top_p", "max_tokens", "tool_choice", "parallel_tool_calls",
                      "input_hash"):
            if c0[field] != c1[field]:
                diffs.append({"task": task, "field": field})
        # intended: note text + shim file only
        if "lx_helpers" not in json.dumps(c1) or "lx_helpers" in json.dumps(c0):
            diffs.append({"task": task, "field": "note_presence_anomaly"})
        if "lx_helpers.py" not in c1["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_missing_C1"})
        if "lx_helpers.py" in c0["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_leaked_C0"})
    audit = {"differences_unintended": diffs, "pass": not diffs,
             "intended_differences": intended + ["workdir contains lx_helpers.py (C1 only)",
                                                 "instance prompt + usage note (C1 only)"]}
    json.dump(audit, open(AB / "identity_manifest.json", "w"), indent=1)
    print("identity audit:", "PASS" if audit["pass"] else f"FAIL {diffs}")
    return audit


def run_all() -> None:
    env = dict(__import__("os").environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AB_FIDELITY_LOG"] = str(AB / "_fidelity.jsonl")
    env["AB_FRESHNESS_LOG"] = str(AB / "freshness_checks.jsonl")
    env["LX_REPO_ROOT"] = str(PROJECT_ROOT)
    for task, _, _ in TASKS:
        for arm in ("C0", "C1"):
            live = reset_live(task, arm)
            arch = AB / "reps" / f"{task.replace(':', '_')}_{arm}"
            if arch.exists():
                shutil.rmtree(arch)
            cmd = [sys.executable, "-B", str(RUNNER), "--task", task,
                   "--arm", arm, "--workdir", str(live), "--archive-dir", str(arch)
                   ] + (["--note-file", str(AB / "_c1_note.txt")] if arm == "C1" else [])
            print(f"=== {task} {arm} ===", flush=True)
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=1500, env=env)
            print((proc.stdout + proc.stderr)[-800:], flush=True)
    print("STAGEB_DONE")


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
