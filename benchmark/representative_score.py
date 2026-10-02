#!/usr/bin/env python3
"""Representative checkpoint scorer: stage -> LO refresh -> official evaluate.

Both arms, then capability rows, discordances (thresholds inherited from the
thin-checkpoint spec: output mismatch, |mod|>=0.10, |reg|>=0.05, corruption),
helper usage from telemetry + transcript cross-check, and per-slot economics.
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
OUT = PROJECT_ROOT / "research/history/representative_architecture_checkpoint"
REPS = OUT / "reps"
STAGE = OUT / "score_staging"
BENCH = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
EVAL = BENCH / "evaluation" / "evaluation.py"
REFRESH = BENCH / "evaluation" / "open_spreadsheet.py"

HELPER_RE = re.compile(r"(?:lx_helpers|lx|L)\.(periods|search|inspect\w*)\s*\(")
# Discordance thresholds inherited from research/history/thin_architecture_checkpoint/spec.json
MD = {"abs_mod_ge": 0.10, "abs_reg_ge": 0.05}


def tasks() -> list[tuple[str, str]]:
    pop = json.load(open(OUT / "population.json"))["selected"]
    out = []
    for fam, ids in pop.items():
        for tid in ids:
            out.append((f"{fam}:{tid}", fam))
    return out


def run_ids(replication: bool = False) -> dict[tuple[str, str], str]:
    merged: dict[tuple[str, str], str] = {}
    if replication:
        for f in sorted(OUT.glob("replication_runs*.json")):
            try:
                rows = json.load(open(f))
            except ValueError:
                continue
            for o in rows:
                merged[(o["task_id"], o["arm"])] = o["run_id"]
        return merged
    for f in sorted(OUT.glob("run_order*.json")):
        try:
            rows = json.load(open(f))
        except ValueError:
            continue
        for o in rows:
            merged[(o["task_id"], o["arm"])] = o["run_id"]
    return merged


def rep_dir(task: str, arm: str, rid: str) -> Path:
    return REPS / f"{task.replace(':', '_')}_{arm}_{rid}"


def usable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        with zipfile.ZipFile(path) as z:
            return "[Content_Types].xml" in z.namelist()
    except Exception:
        return False


def stage_scoped(rids: dict, scope: list) -> list[str]:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    missing = []
    for task, fam in scope:
        cat, _, tid = task.partition(":")
        for arm in ("H0", "H1"):
            rid = rids.get((task, arm))
            src = rep_dir(task, arm, rid) / "output.xlsx" if rid else None
            d = STAGE / arm / cat
            d.mkdir(parents=True, exist_ok=True)
            if src is not None and src.exists():
                shutil.copy2(src, d / f"{tid}_output.xlsx")
            else:
                missing.append(f"{arm}/{task}")
    return missing


def refresh_and_score() -> dict:
    official = {}
    for arm in ("H0", "H1"):
        root = STAGE / arm
        p = subprocess.run([sys.executable, str(REFRESH), "--dir_path", str(root)],
                           capture_output=True, text=True, timeout=1800,
                           cwd=str(BENCH / "evaluation"))
        print(f"refresh {arm}: rc={p.returncode}", flush=True)
        if p.returncode != 0:
            print((p.stdout + p.stderr)[-1000:])
            raise RuntimeError(f"refresh failed for {arm}")
        for cat in ("Financial_Model", "Template", "Debugging"):
            out_dir = root / cat
            out_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run([sys.executable, str(EVAL), "--dataset", cat,
                                   "--outputs-dir", str(out_dir)],
                                  capture_output=True, text=True, timeout=1800,
                                  cwd=str(BENCH))
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


def shim_calls(rep: Path) -> list[dict]:
    """One row per helper call: shim rows carry python_pid (both arms)."""
    rows = []
    hf = rep / "helpers.jsonl"
    if not hf.exists():
        return rows
    for line in hf.read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("event") == "helper_backend" and "python_pid" in d:
            rows.append(d)
    return rows


def transcript_cmds(rep: Path) -> list[tuple[str, dict, str]]:
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
            tcs = m.get("tool_calls") or []
            if not tcs:
                continue
            fn = tcs[0].get("function") or {}
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except ValueError:
                args = {}
            pending = (fn.get("name", ""), args, "")
            steps.append(pending)
        elif m.get("role") == "user" and pending is not None and not pending[2]:
            c = m.get("content", "")
            steps[-1] = (pending[0], pending[1],
                         c if isinstance(c, str) else json.dumps(c))
            pending = None
    return steps


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--replication", action="store_true",
                    help="score reps_replication/ into replication_*.json")
    args = ap.parse_args()
    global REPS, STAGE
    suffix = ""
    if args.replication:
        REPS = OUT / "reps_replication"
        STAGE = OUT / "score_staging_repl"
        suffix = "_replication"
    rids = run_ids(replication=args.replication)
    if args.replication:
        fams = {t: fam for fam, ids in
                json.load(open(OUT / "population.json"))["selected"].items()
                for tid in ids for t in (f"{fam}:{tid}",)}
        scoped = sorted({t for (t, a) in rids})
        scope = [(t, fams[t]) for t in scoped]
    else:
        scope = tasks()
    missing_stage = stage_scoped(rids, scope)
    official = refresh_and_score()
    cap, usage = [], []
    for task, fam in scope:
        cat, _, tid = task.partition(":")
        for arm in ("H0", "H1"):
            rid = rids.get((task, arm))
            if rid is None:
                continue
            rep = rep_dir(task, arm, rid)
            rec = json.loads((rep / "run_record.json").read_text())
            r = official.get((arm, cat, tid), {})
            outp = rep / "output.xlsx"
            cap.append({
                "task_id": task, "family": fam, "arm": arm, "run_id": rid,
                "official_exact": r.get("accuracy"),
                "official_modification": r.get("modification_accuracy"),
                "official_regression": r.get("regression_accuracy"),
                "eval_error": r.get("error_message", ""),
                "usable_workbook": usable(outp),
                "output_produced": rec.get("output_produced"),
                "task_completed": rec.get("status") == "SUBMITTED",
                "run_status": rec.get("status"),
                "censoring": rec.get("censoring"),
                "efficiency": rec.get("efficiency"),
                "timing_totals": rec.get("timing_totals"),
            })
            steps = transcript_cmds(rep)
            bash = [s for s in steps if s[0] == "bash"]
            views = [s for s in steps if s[0] == "view_xlsx"]
            hcalls = []
            for i, s in enumerate(bash):
                for m in HELPER_RE.finditer(str(s[1].get("command", ""))):
                    hcalls.append({"cmd_idx": i, "helper": m.group(1),
                                   "obs_bytes": len(s[2])})
            blob = " ".join(str(s[1].get("command", "")) for s in bash)
            shim = shim_calls(rep)
            usage.append({
                "task_id": task, "family": fam, "arm": arm, "run_id": rid,
                "n_helper_calls_telemetry": len(shim),
                "by_helper_telemetry": dict(Counter(
                    h.get("helper") for h in shim)),
                "helper_backend": sorted({h.get("backend") for h in shim}),
                "helper_duration_s": sum(
                    h.get("duration_ns", 0) for h in shim) / 1e9,
                "n_helper_calls_transcript": len(hcalls),
                "imported_but_unused": ("lx_helpers" in blob) and not hcalls,
                "available_but_bypassed": not hcalls and not shim,
                "view_xlsx_calls": len(views),
                "bash_calls": len(bash),
                "python_execs": sum(
                    1 for s in bash
                    if "python" in str(s[1].get("command", ""))),
            })
    json.dump(cap, open(OUT / f"capability_scores{suffix}.json", "w"),
              indent=1)
    with open(OUT / f"helper_usage{suffix}.jsonl", "w") as fh:
        for r in usage:
            fh.write(json.dumps(r) + "\n")
    by = {(c["task_id"], c["arm"]): c for c in cap}
    disc = []
    for task, fam in scope:
        a, b = by[(task, "H0")], by[(task, "H1")]
        reasons = []
        if a["output_produced"] != b["output_produced"]:
            reasons.append("output_mismatch")
        for key, thresh, name in (
                ("official_modification", MD["abs_mod_ge"], "mod"),
                ("official_regression", MD["abs_reg_ge"], "reg")):
            va, vb = a[key], b[key]
            if va is not None and vb is not None and abs(va - vb) >= thresh:
                reasons.append(f"{name}_delta_{abs(va - vb):.3f}")
        if reasons:
            disc.append({"task_id": task, "family": fam, "reasons": reasons,
                         "H0": {k: a[k] for k in (
                             "official_exact", "official_modification",
                             "official_regression", "output_produced",
                             "run_status")},
                         "H1": {k: b[k] for k in (
                             "official_exact", "official_modification",
                             "official_regression", "output_produced",
                             "run_status")}})
    json.dump(disc, open(OUT / f"capability_discordances{suffix}.json", "w"),
              indent=1)
    json.dump({"missing_outputs_staged": missing_stage,
               "n_scored": len(cap), "n_discordant": len(disc)},
              open(OUT / f"scoring_manifest{suffix}.json", "w"), indent=1)
    print(f"scored {len(cap)} rows; discordant: {len(disc)}; "
          f"missing: {len(missing_stage)}")


if __name__ == "__main__":
    main()
