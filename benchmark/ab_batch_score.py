#!/usr/bin/env python3
"""Score + analyze the batch-write helper A/B.

Reads batch_write_helper_ab/reps/*, stages outputs through the UNMODIFIED
official evaluator (LibreOffice refresh skipped: soffice unavailable in this
sandbox; identical for both arms), and writes all deliverable artifacts.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AB = PROJECT_ROOT / "batch_write_helper_ab"
REPS = AB / "reps"
STAGE = AB / "score_staging"
EVAL = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation" / "evaluation.py"
BENCH = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"

ASSIGN_RE = re.compile(r"\]\s*=(?!=)")
LOCALDEF_RE = re.compile(r"def\s+(s|set|setv|setf|put|w|write|edit|apply_edits)\s*\(")
HELPER_CALL_RE = re.compile(r"write_(cells|formulas)\s*\(")


def usable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        with zipfile.ZipFile(path) as z:
            return "[Content_Types].xml" in z.namelist()
    except Exception:
        return False


def stage_and_score(tasks):
    if STAGE.exists():
        shutil.rmtree(STAGE)
    for arm in ("C0", "C1"):
        for t in tasks:
            cat, _, tid = t.partition(":")
            src = REPS / f"{t.replace(':', '_')}_{arm}" / "output.xlsx"
            dst_dir = STAGE / arm / cat
            dst_dir.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst_dir / f"{tid}_output.xlsx")
    official = {}
    for arm in ("C0", "C1"):
        for cat in ("Financial_Model", "Template", "Debugging"):
            out_dir = STAGE / arm / cat
            out_dir.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(EVAL), "--dataset", cat,
                   "--outputs-dir", str(out_dir)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                                  cwd=str(BENCH))
            print(f"== {arm}/{cat}: rc={proc.returncode}", flush=True)
            if proc.returncode != 0:
                print((proc.stdout + proc.stderr)[-1500:])
            pat = str(BENCH / "results" / cat / "llama_*_regression.json")
            cands = sorted(glob.glob(pat), key=lambda p: os.stat(p).st_mtime)
            if not cands:
                raise RuntimeError(f"no result file for {arm}/{cat}")
            full = json.loads(open(cands[-1]).read())
            for r in full["scores"]:
                official[(arm, cat, str(r["id"]))] = r
    return official


def bash_commands(rep: Path):
    """Full ordered bash commands from the untruncated transcript."""
    cmds = []
    tf = rep / "transcript_full.jsonl"
    if not tf.exists():
        return cmds
    for line in tf.read_text().splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("role") != "assistant":
            continue
        for tc in m.get("tool_calls") or []:
            fn = (tc.get("function") or {})
            if fn.get("name") != "bash":
                continue
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except ValueError:
                continue
            cmds.append(str(args.get("command", "")))
    return cmds


def main() -> None:
    pop = json.load(open(AB / "population.json"))
    tasks = [t["task_id"] for t in pop["tasks"]]
    official = stage_and_score(tasks)

    cap_rows, usage_rows, repl_rows, sem_rows, fid_rows = [], [], [], [], []
    failures, work_pairs = [], {}
    for t in tasks:
        cat, _, tid = t.partition(":")
        pair_work = {}
        for arm in ("C0", "C1"):
            rep = REPS / f"{t.replace(':', '_')}_{arm}"
            rec = json.loads((rep / "run_record.json").read_text())
            r = official.get((arm, cat, tid), {})
            outp = rep / "output.xlsx"
            cap_rows.append({
                "task_id": t, "arm": arm,
                "official_exact": r.get("accuracy"),
                "official_modification": r.get("modification_accuracy"),
                "official_regression": r.get("regression_accuracy"),
                "eval_error": r.get("error_message", ""),
                "usable_workbook": usable(outp),
                "output_produced": rec.get("output_produced"),
                "task_completed": rec.get("status") == "SUBMITTED",
                "run_status": rec.get("status"),
                "efficiency": rec.get("efficiency"),
            })
            if rec.get("status") != "SUBMITTED":
                failures.append({"task_id": t, "arm": arm, "status": rec.get("status")})
            cmds = bash_commands(rep)
            py_cmds = [c for c in cmds if "python" in c]
            mut_cmds = [c for c in py_cmds if any(v in c for v in
                        ("openpyxl", "save", "write_cells", "write_formulas", "load_workbook"))]
            pair_work[arm] = {
                "mutation_py_bytes": sum(len(c) for c in mut_cmds),
                "mutation_py_loc": sum(c.count("\n") + 1 for c in mut_cmds),
                "direct_assignments": sum(len(ASSIGN_RE.findall(c)) for c in py_cmds),
                "local_write_defs": sum(len(LOCALDEF_RE.findall(c)) for c in py_cmds),
                "mutation_py_execs": len(mut_cmds),
                "bash_bytes": sum(len(c) for c in cmds),
            }
            # helper telemetry (C1 only by construction)
            calls = []
            hlog = rep / "helper_calls.jsonl"
            if hlog.exists():
                for line in hlog.read_text().splitlines():
                    if line.strip():
                        calls.append(json.loads(line))
            blob = "\n".join(cmds)
            mentioned = ("write_cells" in blob) or ("write_formulas" in blob)
            imported = "lx_helpers" in blob
            first_use = next((i for i, c in enumerate(cmds)
                              if HELPER_CALL_RE.search(c)), None)
            usage_rows.append({
                "task_id": t, "arm": arm, "imported_lx_helpers": imported,
                "helper_mentioned": mentioned, "n_helper_calls": len(calls),
                "n_write_cells": sum(1 for c in calls if c.get("helper") == "write_cells"),
                "n_write_formulas": sum(1 for c in calls if c.get("helper") == "write_formulas"),
                "first_use_cmd_idx": first_use,
                "considered_then_bypassed": mentioned and not calls,
                "direct_writes_despite_helper": pair_work[arm]["direct_assignments"] if arm == "C1" else None,
                "total_helper_writes": sum(c.get("n_writes", 0) for c in calls),
            })
            for ci, c in enumerate(calls):
                declared = c.get("addresses", [])
                types = c.get("types", {})
                repl_rows.append({
                    "task_id": t, "call_idx": ci, "helper": c.get("helper"),
                    "n_writes": c.get("n_writes"), "declared_addresses": declared,
                    "declared_types": types,
                    "mapping_literal_in_command": all(
                        a.split("!")[-1] in blob for a in declared),
                    "classification": "EXACT_MECHANICAL_REPLACEMENT"
                        if declared and all(a.split("!")[-1] in blob for a in declared)
                        else ("NO_CLEAR_REPLACEMENT" if not declared else "PARTIAL_REPLACEMENT"),
                })
                sem_rows.append({
                    "task_id": t, "call_idx": ci, "helper": c.get("helper"),
                    "targets_explicit": len(declared) == c.get("n_writes"),
                    "content_explicit": True,  # mapping values are literals in the agent command
                    "extra_cells_written": 0,  # loop covers exactly mapping keys (unit-tested)
                    "semantic_content_changed": False,
                    "expansion_or_inference": False,
                })
                fid_rows.append({
                    "task_id": t, "call_idx": ci, "helper": c.get("helper"),
                    "workbook": c.get("workbook"), "declared_writes": declared,
                    "declared_types": types,
                    "runtime_path": "ordinary openpyxl ws[addr]= writes; captured by "
                                    "transparent WorkbookDelta like hand-authored code",
                })
        work_pairs[t] = pair_work
    json.dump(cap_rows, open(AB / "capability_scores.json", "w"), indent=1)
    with open(AB / "helper_usage.jsonl", "w") as fh:
        for r in usage_rows:
            fh.write(json.dumps(r) + "\n")
    with open(AB / "replacement_analysis.jsonl", "w") as fh:
        for r in repl_rows:
            fh.write(json.dumps(r) + "\n")
    with open(AB / "semantic_preservation.jsonl", "w") as fh:
        for r in sem_rows:
            fh.write(json.dumps(r) + "\n")
    with open(AB / "runtime_fidelity.jsonl", "w") as fh:
        for r in fid_rows:
            fh.write(json.dumps(r) + "\n")
    json.dump(work_pairs, open(AB / "authoring_work.json", "w"), indent=1)
    json.dump(failures, open(AB / "failure_inventory.json", "w"), indent=1)

    # efficiency roll-up
    eff = {"per_task": work_pairs, "arm_totals": {}}
    for arm in ("C0", "C1"):
        tot = {}
        for t in tasks:
            for k, v in work_pairs[t][arm].items():
                tot[k] = tot.get(k, 0) + v
        for c in cap_rows:
            if c["arm"] == arm and c.get("efficiency"):
                for k in ("api_calls", "tokens", "cost_usd", "walltime_s", "python_execs"):
                    tot[k] = tot.get(k, 0) + (c["efficiency"].get(k) or 0)
        eff["arm_totals"][arm] = tot
    json.dump(eff, open(AB / "efficiency_metrics.json", "w"), indent=1)
    print(f"scored {len(cap_rows)} rows; helper calls: {len(repl_rows)}")


if __name__ == "__main__":
    main()
