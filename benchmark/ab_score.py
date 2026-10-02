#!/usr/bin/env python3
"""Stage A/B outputs and score with the UNMODIFIED official evaluator.

Deviation (documented, identical for both arms): LibreOffice refresh is
skipped (soffice is not executable in this sandbox). score_openrouter_run.py
--no-refresh documents the same escape hatch.

Usage: python3 benchmark/ab_score.py
Reads research/history/live_transparent_runtime_ab/runs/*/*_{H0,H1}/output.xlsx, writes
research/history/live_transparent_runtime_ab/paired_scores.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "research/history/live_transparent_runtime_ab" / "runs"
STAGE = PROJECT_ROOT / "research/history/live_transparent_runtime_ab" / "score_staging"
EVAL = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation" / "evaluation.py"


def main() -> None:
    tasks = json.load(open(PROJECT_ROOT / "research/history/live_transparent_runtime_ab" / "population.json"))["frozen_tasks"]
    if STAGE.exists():
        shutil.rmtree(STAGE)
    for arm in ("H0", "H1"):
        for t in tasks:
            cat = t["category"] if "category" in t else t.get("family", "")
            tid = t["id"]
            src = RUNS_DIR / cat / f"{cat}_{tid}_{arm}" / "output.xlsx"
            dst_dir = STAGE / arm / cat
            dst_dir.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst_dir / f"{tid}_output.xlsx")
    import glob
    bench = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
    paired = []
    for arm in ("H0", "H1"):
        for cat in ("Financial_Model", "Template", "Debugging"):
            out_dir = STAGE / arm / cat
            out_dir.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(EVAL), "--dataset", cat,
                   "--outputs-dir", str(out_dir)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                                  cwd=str(bench))
            print(f"== {arm}/{cat}: rc={proc.returncode}", flush=True)
            if proc.returncode != 0:
                print((proc.stdout + proc.stderr)[-1500:])
            pat = str(bench / "research/history/results" / cat / "llama_*_regression.json")
            cands = sorted(glob.glob(pat), key=lambda p: os.stat(p).st_mtime)
            if not cands:
                raise RuntimeError(f"no result file for {arm}/{cat}")
            full = json.loads(open(cands[-1]).read())
            by_id = {r["id"]: r for r in full["scores"]}
            for t in tasks:
                cc = t["category"] if "category" in t else t.get("family", "")
                if cc != cat:
                    continue
                r = by_id.get(t["id"], {})
                rec = json.loads((RUNS_DIR / cat / f"{cat}_{t['id']}_{arm}" /
                                  "run_record.json").read_text())
                paired.append({
                    "task_id": f"{cat}:{t['id']}", "arm": arm,
                    "official_exact": r.get("accuracy"),
                    "official_modification": r.get("modification_accuracy"),
                    "official_regression": r.get("regression_accuracy"),
                    "eval_error": r.get("error_message", ""),
                    "usable_workbook": _usable(RUNS_DIR / cat / f"{cat}_{t['id']}_{arm}" / "output.xlsx"),
                    "output_produced": rec.get("output_produced"),
                    "task_completed": rec.get("status") == "SUBMITTED",
                    "run_status": rec.get("status"),
                    "efficiency": rec.get("efficiency"),
                    "behavior": {k: v for k, v in rec.get("behavior", {}).items()
                                 if k != "trajectory"},
                    "h1_telemetry": rec.get("h1_telemetry"),
                })
    json.dump(paired, open(PROJECT_ROOT / "research/history/live_transparent_runtime_ab" /
                           "paired_scores.json", "w"), indent=1)
    print(f"wrote paired_scores.json ({len(paired)} rows)")


def _usable(path: Path) -> bool:
    try:
        import zipfile
        if not path.exists():
            return False
        with zipfile.ZipFile(path) as z:
            return "[Content_Types].xml" in z.namelist()
    except Exception:
        return False


if __name__ == "__main__":
    main()
