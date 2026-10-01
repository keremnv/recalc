#!/usr/bin/env python3
"""Checkpoint scorer: stage -> LO refresh -> official evaluate (both arms),
then capability gate, discordances, usage, efficiency, integrity artifacts.
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
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AB = PROJECT_ROOT / "thin_architecture_checkpoint"
REPS = AB / "reps"
STAGE = AB / "score_staging"
BENCH = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
EVAL = BENCH / "evaluation" / "evaluation.py"
REFRESH = BENCH / "evaluation" / "open_spreadsheet.py"

HELPER_RE = re.compile(r"(?:lx_helpers|lx|L)\.(periods|search|inspect)\s*\(")


def usable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        with zipfile.ZipFile(path) as z:
            return "[Content_Types].xml" in z.namelist()
    except Exception:
        return False


def stage() -> None:
    pop = json.load(open(AB / "population.json"))["tasks"]
    if STAGE.exists():
        shutil.rmtree(STAGE)
    for arm in ("H0", "H1"):
        for t in pop:
            cat, _, tid = t["task_id"].partition(":")
            src = REPS / f"{t['task_id'].replace(':', '_')}_{arm}" / "output.xlsx"
            d = STAGE / arm / cat
            d.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, d / f"{tid}_output.xlsx")


def refresh_and_score() -> dict:
    official = {}
    for arm in ("H0", "H1"):
        root = STAGE / arm
        p = subprocess.run([sys.executable, str(REFRESH), "--dir_path", str(root)],
                           capture_output=True, text=True, timeout=1800, cwd=str(BENCH / "evaluation"))
        print(f"refresh {arm}: rc={p.returncode}", flush=True)
        if p.returncode != 0:
            print((p.stdout + p.stderr)[-1000:])
            raise RuntimeError(f"refresh failed for {arm}")
        for cat in ("Financial_Model", "Template", "Debugging"):
            out_dir = root / cat
            out_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run([sys.executable, str(EVAL), "--dataset", cat,
                                   "--outputs-dir", str(out_dir)],
                                  capture_output=True, text=True, timeout=1800, cwd=str(BENCH))
            print(f"== {arm}/{cat}: rc={proc.returncode}", flush=True)
            if proc.returncode != 0:
                print((proc.stdout + proc.stderr)[-1500:])
                raise RuntimeError(f"eval failed for {arm}/{cat}")
            pat = str(BENCH / "results" / cat / "llama_*_regression.json")
            cands = sorted(glob.glob(pat), key=lambda q: os.stat(q).st_mtime)
            full = json.loads(open(cands[-1]).read())
            for r in full["scores"]:
                official[(arm, cat, str(r["id"]))] = r
    return official


def transcript_cmds(rep: Path) -> list[tuple[str, dict, str]]:
    """(tool, args, obs) from full transcript."""
    steps = []
    tf = rep / "transcript_full.jsonl"
    if not tf.exists():
        return steps
    pending = None
    for line in tf.read_text().splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("role") == "assistant":
            # runner executes calls[0] only; mirror that for obs pairing
            tcs = m.get("tool_calls") or []
            if not tcs:
                continue
            fn = (tcs[0].get("function") or {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except ValueError:
                args = {}
            pending = (fn.get("name", ""), args, "")
            steps.append(pending)
        elif m.get("role") == "user" and pending is not None and not pending[2]:
            c = m.get("content", "")
            steps[-1] = (pending[0], pending[1], c if isinstance(c, str) else json.dumps(c))
            pending = None
    return steps


def main() -> None:
    pop = json.load(open(AB / "population.json"))["tasks"]
    spec = json.load(open(AB / "spec.json"))
    stage()
    official = refresh_and_score()
    cap, usage, primary = [], [], []
    for t in pop:
        task, cohort = t["task_id"], t["cohort"]
        cat, _, tid = task.partition(":")
        for arm in ("H0", "H1"):
            rep = REPS / f"{task.replace(':', '_')}_{arm}"
            rec = json.loads((rep / "run_record.json").read_text())
            r = official.get((arm, cat, tid), {})
            outp = rep / "output.xlsx"
            row = {"task_id": task, "cohort": cohort, "arm": arm,
                   "official_exact": r.get("accuracy"),
                   "official_modification": r.get("modification_accuracy"),
                   "official_regression": r.get("regression_accuracy"),
                   "eval_error": r.get("error_message", ""),
                   "usable_workbook": usable(outp),
                   "output_produced": rec.get("output_produced"),
                   "task_completed": rec.get("status") == "SUBMITTED",
                   "run_status": rec.get("status"),
                   "efficiency": rec.get("efficiency")}
            cap.append(row)
            primary.append({"task_id": task, "arm": arm, "status": rec.get("status"),
                            "output_produced": rec.get("output_produced"),
                            "api_calls": rec["efficiency"]["api_calls"],
                            "tokens": rec["efficiency"]["tokens"],
                            "cost_usd": rec["efficiency"]["cost_usd"]})
            steps = transcript_cmds(rep)
            bash = [s for s in steps if s[0] == "bash"]
            views = [s for s in steps if s[0] == "view_xlsx"]
            hcalls = []
            for i, s in enumerate(bash):
                for m in HELPER_RE.finditer(str(s[1].get("command", ""))):
                    hcalls.append({"cmd_idx": i, "helper": m.group(1),
                                   "obs_bytes": len(s[2])})
            blob = " ".join(str(s[1].get("command", "")) for s in bash)
            usage.append({
                "task_id": task, "cohort": cohort, "arm": arm,
                "n_helper_calls": len(hcalls),
                "by_helper": dict(Counter(h["helper"] for h in hcalls)),
                "first_use_cmd_idx": hcalls[0]["cmd_idx"] if hcalls else None,
                "imported_but_unused": ("lx_helpers" in blob) and not hcalls,
                "available_but_bypassed": arm == "H1" and not hcalls,
                "view_xlsx_calls": len(views),
                "bash_calls": len(bash),
                "python_execs": sum(1 for s in bash if "python" in str(s[1].get("command", ""))),
                "calls": hcalls,
            })
    json.dump(cap, open(AB / "capability_scores.json", "w"), indent=1)
    with open(AB / "primary_runs.jsonl", "w") as fh:
        for r in primary:
            fh.write(json.dumps(r) + "\n")
    with open(AB / "helper_usage.jsonl", "w") as fh:
        for r in usage:
            fh.write(json.dumps(r) + "\n")

    # discordances (predeclared thresholds)
    md = spec["material_discordance"]
    by = {(c["task_id"], c["arm"]): c for c in cap}
    disc = []
    for t in pop:
        task = t["task_id"]
        a, b = by[(task, "H0")], by[(task, "H1")]
        reasons = []
        if a["output_produced"] != b["output_produced"]:
            reasons.append("output_mismatch")
        for key, thresh, name in (("official_modification", md["abs_mod_ge"], "mod"),
                                  ("official_regression", md["abs_reg_ge"], "reg")):
            va, vb = a[key], b[key]
            if va is not None and vb is not None and abs(va - vb) >= thresh:
                reasons.append(f"{name}_delta_{abs(va-vb):.3f}")
        if reasons:
            disc.append({"task_id": task, "cohort": t["cohort"], "reasons": reasons,
                        "H0": {k: a[k] for k in ("official_exact", "official_modification",
                                                "official_regression", "output_produced",
                                                "run_status")},
                        "H1": {k: b[k] for k in ("official_exact", "official_modification",
                                                "official_regression", "output_produced",
                                                "run_status")}})
    json.dump(disc, open(AB / "capability_discordances.json", "w"), indent=1)
    print(f"scored {len(cap)} rows; discordant: {len(disc)}")


if __name__ == "__main__":
    main()
