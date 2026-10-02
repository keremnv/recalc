#!/usr/bin/env python3
"""Batch-write helper A/B: C0 (earned surface) vs C1 (+ optional
write_cells/write_formulas). 10 tasks x n=1 x 2 arms = 20 runs.
Population frozen mechanically from mutation-authoring audit:
confirmed explicit address->content batching + clean/partial boundary.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AB = PROJECT_ROOT / "research/history/batch_write_helper_ab"
RUNNER = PROJECT_ROOT / "benchmark" / "ab_local_runner.py"
SHIM_C0 = PROJECT_ROOT / "benchmark" / "inspection_helpers" / "lx_helpers.py"
SHIM_C1 = PROJECT_ROOT / "benchmark" / "mutation_helpers" / "shim_c1.py"

# (task, batch_kind, boundary) from research/history/mutation_authoring_audit/source_effect_reconciliation.json:
# all 4 formula-batch-confirmed tasks + EARLY value-batch round-robin to n=10.
TASKS = [
    ("Financial_Model:08_01", "value+formula", "EARLY"),
    ("Template:10_01", "formula", "EARLY"),
    ("Template:15_01", "formula", "EARLY"),
    ("Template:16_01", "formula", "EARLY"),
    ("Debugging:02_01", "value", "EARLY"),
    ("Template:03_03", "value", "EARLY"),
    ("Debugging:05_08", "value", "EARLY"),
    ("Template:05_02", "value", "EARLY"),
    ("Debugging:06_07", "value", "EARLY"),
    ("Financial_Model:11_01", "value", "PARTIAL"),
]

NOTE_C0 = """## Optional inspection helpers (available in this environment)

A Python module `lx_helpers` is importable from your working directory. You may
use it or ignore it entirely; ordinary Python/openpyxl/view_xlsx all work as usual.
- `lx_helpers.periods(workbook_path, sheet=None)` returns mechanically recovered
  period/header coordinates (e.g. FY24 -> column letter). It does not say which
  periods the task needs.
- `lx_helpers.search(workbook_path, pattern, regex=False, sheet=None)` returns
  exact occurrences (sheet/address/value/formula) in sheet order. No ranking.
- `lx_helpers.inspect(workbook_path, sheet, range, with_styles=False)` returns
  values/formulas/dtypes for an explicitly requested range.
Example: `import lx_helpers; lx_helpers.search("input.xlsx", "revenue")`
"""

NOTE_C1 = NOTE_C0 + """
## Optional batch-write helpers (also available in this environment)

`lx_helpers.write_cells(mapping, workbook=...)` and
`lx_helpers.write_formulas(mapping, workbook=...)` apply an explicit
address->content mapping (e.g. {"Sheet1!B4": 10}) in one call. They do not
infer targets or formulas. The workbook path must be passed explicitly and
the file must already exist. Ordinary Python/openpyxl remains available.
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
    shutil.copy2(SHIM_C1 if arm == "C1" else SHIM_C0, live / "lx_helpers.py")
    return live


def dry_run(task: str, arm: str, live: Path) -> dict:
    cmd = [sys.executable, str(RUNNER), "--task", task, "--arm", arm,
           "--workdir", str(live),
           "--archive-dir", str(AB / "audit_tmp" / f"{task}_{arm}".replace(":", "_")),
           "--dry-run", "--note-file", str(AB / ("_c1_note.txt" if arm == "C1" else "_c0_note.txt"))]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"dry-run failed {task} {arm}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def write_frozen() -> None:
    AB.mkdir(parents=True, exist_ok=True)
    (AB / "_c0_note.txt").write_text(NOTE_C0)
    (AB / "_c1_note.txt").write_text(NOTE_C1)
    json.dump({
        "name": "batch-write-helper-ab",
        "gated_on": "research/history/mutation_authoring_audit/candidate_helpers.json: "
                     "write_cells + write_formulas == LIVE_TEST; all others REJECT",
        "arms": {"C0": "transparent runtime + ordinary Python/openpyxl + earned "
                       "periods/search/inspect",
                 "C1": "C0 + optional write_cells/write_formulas; usage note "
                       "paragraph appended; nothing else changes"},
        "helpers": ["write_cells", "write_formulas"],
        "helper_semantics": "exact map in -> exact writes out; explicit workbook "
                            "path required; no inference; effects flow through the "
                            "same transparent WorkbookDelta runtime",
        "forbidden": ["fill/translation/style helpers", "target inference",
                      "mandatory syntax", "tool removal", "read-side changes"],
        "n": 1, "discordant_cell_policy": "repeat discordant cells once before concluding",
    }, open(AB / "spec.json", "w"), indent=1)
    json.dump({"tasks": [{"task_id": t, "batch_kind": k, "boundary": b}
                         for t, k, b in TASKS],
               "selection": "mechanically from research/history/mutation_authoring_audit/"
                            "source_effect_reconciliation.json: rows with an "
                            "explicit_address_*_batch idiom + SOURCE_AND_EFFECT_AGREE + "
                            "EARLY/PARTIAL boundary; all 4 formula-batch tasks + "
                            "EARLY value-batch round-robin across families to n=10"},
              open(AB / "population.json", "w"), indent=1)


def identity_audit() -> dict:
    diffs, intended = [], ["instance_hash", "request_body.user_len"]
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
        if c1["instance_hash"] == c0["instance_hash"]:
            diffs.append({"task": task, "field": "note_has_no_effect"})
        n0 = (AB / "_c0_note.txt").read_text()
        n1 = (AB / "_c1_note.txt").read_text()
        if "write_cells" in n0 or "write_cells" not in n1:
            diffs.append({"task": task, "field": "note_presence_anomaly"})
        if "lx_helpers.py" not in c1["workdir_listing"] or "lx_helpers.py" not in c0["workdir_listing"]:
            diffs.append({"task": task, "field": "shim_missing"})
    audit = {"differences_unintended": diffs, "pass": not diffs,
             "intended_differences": intended + ["lx_helpers.py content: +write_cells/write_formulas (C1)",
                                                 "instance prompt + batch paragraph (C1 only)"]}
    json.dump(audit, open(AB / "identity_manifest.json", "w"), indent=1)
    print("identity audit:", "PASS" if audit["pass"] else f"FAIL {diffs}")
    return audit


def run_all() -> None:
    import os
    base = dict(os.environ)
    base["PYTHONDONTWRITEBYTECODE"] = "1"
    base["AB_FIDELITY_LOG"] = str(AB / "_fidelity.jsonl")
    base["AB_FULL_TRANSCRIPT"] = "1"
    base["LX_REPO_ROOT"] = str(PROJECT_ROOT)
    for task, _, _ in TASKS:
        for arm in ("C0", "C1"):
            live = reset_live(task, arm)
            arch = AB / "reps" / f"{task.replace(':', '_')}_{arm}"
            if arch.exists():
                shutil.rmtree(arch)
            arch.mkdir(parents=True)
            env = dict(base)
            env["AB_HELPER_LOG"] = str(arch / "helper_calls.jsonl")
            cmd = [sys.executable, "-B", str(RUNNER), "--task", task,
                   "--arm", arm, "--workdir", str(live), "--archive-dir", str(arch),
                   "--note-file", str(AB / ("_c1_note.txt" if arm == "C1" else "_c0_note.txt"))]
            print(f"=== {task} {arm} ===", flush=True)
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=1500, env=env)
            print((proc.stdout + proc.stderr)[-800:], flush=True)
    print("BATCH_AB_DONE")


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
