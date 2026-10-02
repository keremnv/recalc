#!/usr/bin/env python3
"""Phase 12 scorer: stage run outputs through the UNMODIFIED official evaluator.

Reads research/history/phase12/runs/<pop>/*_<ARM>/output.xlsx, stages per (pop, arm, cat),
runs benchmark-data/SpreadsheetBench-2/evaluation/evaluation.py once per
(pop, arm, cat) with a unique --model tag, and writes the scorer/outcome
ledger. Never modifies the evaluator. Safe to run while live batches are
in flight (reads staged copies only).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS = PROJECT_ROOT / "research/history/phase12" / "runs"
STAGE = PROJECT_ROOT / "research/history/phase12" / "score_staging"
LEDGERS = PROJECT_ROOT / "research/history/phase12" / "ledgers"
EVAL = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "evaluation" / "evaluation.py"
BENCH = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"

CATS = ("Template", "Debugging", "Financial_Model")


def usable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        with zipfile.ZipFile(path) as z:
            return "[Content_Types].xml" in z.namelist()
    except Exception:
        return False


def _parse(dirname: str, arm: str) -> tuple[str, str]:
    stem = dirname[: -len(arm) - 1]
    for _cat in CATS:
        if stem.startswith(_cat + "_"):
            return _cat, stem[len(_cat) + 1:]
    raise RuntimeError(f"unparseable run dir: {dirname}")


def stage_and_score(pops: list[str], variants: tuple[str, ...] = ()) -> dict:
    official: dict[tuple[str, str, str, str], dict] = {}
    recalc = None
    if "recalc" in variants:
        sys.path.insert(0, str(PROJECT_ROOT / "research/history/phase12"))
        from verification_block import recalc as _recalc
        recalc = _recalc
    arm_labels = ["CONTROL", "TREATMENT", "SHAM"]
    if "pre" in variants:
        arm_labels += ["PRE_TREATMENT", "PRE_SHAM"]
    if "recalc" in variants:
        arm_labels += ["RC_CONTROL", "RC_TREATMENT", "RC_SHAM"]
    for pop in pops:
        for arm_dir in sorted((RUNS / pop).glob("*")):
            arm = arm_dir.name.rsplit("_", 1)[-1]
            if arm not in ("CONTROL", "TREATMENT", "SHAM"):
                continue
            cat, tid = _parse(arm_dir.name, arm)
            jobs = [(arm, arm_dir / "output.xlsx")]
            if "pre" in variants and arm in ("TREATMENT", "SHAM"):
                jobs.append((f"PRE_{arm}", arm_dir / "pre_intervention.xlsx"))
            if "recalc" in variants:
                jobs.append((f"RC_{arm}", arm_dir / "output.xlsx"))
            for arm_label, src in jobs:
                if not src.exists():
                    continue
                if arm_label.startswith("RC_"):
                    tmp = Path(f"/tmp/p12_rc_{pop}_{arm_dir.name}.xlsx")
                    got = recalc(src)
                    if got is None:
                        continue
                    shutil.copy2(got, tmp)
                    src = tmp
                dst_dir = STAGE / pop / arm_label / cat
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst_dir / f"{tid}_output.xlsx")
    for pop in pops:
        for arm in arm_labels:
            for cat in CATS:
                out_dir = STAGE / pop / arm / cat
                out_dir.mkdir(parents=True, exist_ok=True)
                tag = f"p12{pop}{arm}"
                cmd = [sys.executable, str(EVAL), "--model", tag,
                       "--dataset", cat, "--outputs-dir", str(out_dir),
                       "--workers", "4"]
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=1800, cwd=str(BENCH))
                print(f"== {pop}/{arm}/{cat}: rc={proc.returncode}", flush=True)
                if proc.returncode != 0:
                    print((proc.stdout + proc.stderr)[-1500:])
                    raise RuntimeError(f"evaluator failed for {pop}/{arm}/{cat}")
                pat = str(BENCH / "results" / cat / f"{tag}_*_regression.json")
                cands = sorted(glob.glob(pat), key=lambda p: os.stat(p).st_mtime)
                if not cands:
                    raise RuntimeError(f"no result file for {pop}/{arm}/{cat}")
                full = json.loads(open(cands[-1]).read())
                for r in full["scores"]:
                    official[(pop, arm, cat, str(r["id"]))] = r
    return official


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    variants = tuple(v for a in sys.argv[1:] if a.startswith("--variants=")
                     for v in a.split("=", 1)[1].split(",") if v)
    pops = args or ["popA", "popB", "pilot", "pilot_ext"]
    pops = [p for p in pops if (RUNS / p).exists()]
    official = stage_and_score(pops, variants)
    LEDGERS.mkdir(parents=True, exist_ok=True)
    out_name = "scorer_outcome.jsonl" if not variants else "sensitivity_scores.jsonl"
    n = 0
    with open(LEDGERS / out_name, "w") as fp:
        for pop in pops:
            for arm_dir in sorted((RUNS / pop).glob("*")):
                arm = arm_dir.name.rsplit("_", 1)[-1]
                if arm not in ("CONTROL", "TREATMENT", "SHAM"):
                    continue
                cat, tid = _parse(arm_dir.name, arm)
                task = f"{cat}:{tid}"
                rec_path = arm_dir / "run_record.json"
                rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
                labels = [arm]
                if variants and "pre" in variants and arm in ("TREATMENT", "SHAM"):
                    labels.append(f"PRE_{arm}")
                if variants and "recalc" in variants:
                    labels.append(f"RC_{arm}")
                for lab in labels:
                    r = official.get((pop, lab, cat, tid), {})
                    src = arm_dir / ("pre_intervention.xlsx" if lab.startswith("PRE_")
                                     else "output.xlsx")
                    fp.write(json.dumps({
                        "pop": pop, "task_id": task, "arm": arm, "variant": lab,
                        "run_status": rec.get("status"),
                        "output_produced": rec.get("output_produced", False),
                        "variant_staged": src.exists(),
                        "usable_workbook": usable(src),
                        "official_exact": r.get("accuracy"),
                        "official_modification": r.get("modification_accuracy"),
                        "official_regression": r.get("regression_accuracy"),
                        "eval_error": r.get("error_message", ""),
                    }) + "\n")
                    n += 1
    print(f"wrote {n} rows to {out_name}")


if __name__ == "__main__":
    main()
