#!/usr/bin/env python3
"""Post-hoc actuation and scoring of the replay under a corrected response parse.

Diagnostic only. It makes no model calls, replays stored raw synthesis text, and
writes to its own directory. The frozen run's actuation and scores are never
touched or replaced.

The frozen extractor spans the first '{' to the last '}', so a model that emits
a correct answer and then repeats it verbatim is scored unparseable. On this run
that discarded three answers, one of them a PROPOSED formula, which never
reached the workbook and so could not earn modification credit. This arm asks
what the benchmark score would have been had the instrument not dropped valid
answers. Recovery stays conservative: repeats must agree, or the response stays
unparseable.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_plan_downstream_replay as replay
from report_edit_plan_replay import posthoc_parse

old = replay.old
OUT = replay.OUT / "posthoc-parse-arm"


def repaired_sessions():
    """Stored sessions with `parsed` replaced by the corrected parse."""
    out, recovered = [], []
    for p in sorted((replay.OUT / "sessions").glob("*.json")):
        s = old.load(p)
        if not s.get("job") or not s.get("target"):
            continue
        resp = (s.get("synthesis") or {}).get("response") or {}
        obj, how = posthoc_parse(resp.get("text") or "")
        if how.startswith("RECOVERED") and (s["synthesis"].get("parsed") is None):
            recovered.append({"session": s["job"]["session_id"], "recovery": how, "parsed": obj})
            s["synthesis"] = dict(s["synthesis"], parsed=obj)
        out.append(s)
    return out, recovered


def actuate():
    from openpyxl.formula.translate import Translator
    from xlsx_cell_writer import write_cells
    sessions, recovered = repaired_sessions()
    old.write(OUT / "recovered.json", {"recovered": recovered, "count": len(recovered)})
    grouped = defaultdict(list)
    for s in sessions:
        grouped[s["job"]["task"]].append(s)
    for task, group in grouped.items():
        if (OUT / f"actuation/{task}.json").exists():
            continue
        spine = old._load_spine(task)
        cache, writes, edits = {}, [], []
        source = old.synth_tools._input_path(task)
        wb = old.openpyxl.load_workbook(source, data_only=False)  # verifier only; never saved
        for s in group:
            parsed = (s.get("synthesis") or {}).get("parsed") or {}
            formula = parsed.get("formula") if parsed.get("status") == "PROPOSED" else None
            if formula and parsed.get("target_id") != s["job"]["cell_id"]:
                writes.append({"session_id": s["job"]["session_id"], "status": "INVALID_TARGET_ID", "applied": False})
                continue
            if not isinstance(formula, str) or not formula.startswith("="):
                continue
            for cid in s["job"]["execution_cell_ids"]:
                target = old.target_address(spine, cid)
                translated = formula if cid == s["job"]["cell_id"] else Translator(
                    formula, origin=s["target"]["address"]).translate_formula(target["address"])
                validation = old.validate_and_apply(task, target, translated, cache, wb)
                writes.append({"session_id": s["job"]["session_id"], "target": target, "formula": translated, **validation})
                if validation.get("applied"):
                    edits.append({"sheet": target["sheet"], "address": target["address"], "formula": translated})
        wb.close()
        output = OUT / f"scoring/Financial_Model-{task}/output.xlsx"
        audit = write_cells(source, output, edits)
        for w in writes:
            if w.get("applied") and any(x["reason"].startswith("SHARED_FORMULA_MASTER") for x in audit["rejected"]
                                        if x["sheet"] == w["target"]["sheet"] and x["address"] == w["target"]["address"]):
                w["applied"] = False
                w["writer_rejected"] = True
        old.write(OUT / f"actuation/{task}.json", {"task": task, "writes": writes, "output": str(output), "writer_audit": audit})
        print(f"{task}: applied {sum(bool(w.get('applied')) for w in writes)}", flush=True)


def score():
    subprocess.run([sys.executable, str(old.ROOT / "benchmark/score_openrouter_run.py"), str(OUT / "scoring"),
                    "--model-name", "edit-plan-replay-posthoc-parse", "--metadata-tolerant"],
                   cwd=old.ROOT / "benchmark-data/SpreadsheetBench-2/evaluation", check=False)


def compare():
    """Frozen actuation against the corrected-parse arm, task by task."""
    rows = []
    frozen_scores = old.load(replay.OUT / "scoring/official_scores.json") if (replay.OUT / "scoring/official_scores.json").exists() else {}
    post_scores = old.load(OUT / "scoring/official_scores.json") if (OUT / "scoring/official_scores.json").exists() else {}
    for p in sorted((OUT / "actuation").glob("*.json")):
        task = p.stem
        a = old.load(p)
        b = old.load(replay.OUT / f"actuation/{task}.json") if (replay.OUT / f"actuation/{task}.json").exists() else {"writes": []}
        fr = (frozen_scores.get("tasks") or {}).get(f"Financial_Model:{task}") or {}
        pr = (post_scores.get("tasks") or {}).get(f"Financial_Model:{task}") or {}
        rows.append({"task": task,
                     "frozen_applied": sum(bool(w.get("applied")) for w in b["writes"]),
                     "posthoc_applied": sum(bool(w.get("applied")) for w in a["writes"]),
                     "frozen_modification": fr.get("modification_accuracy"),
                     "posthoc_modification": pr.get("modification_accuracy"),
                     "frozen_regression": fr.get("regression_accuracy"),
                     "posthoc_regression": pr.get("regression_accuracy")})
    old.write(OUT / "comparison.json", {"rows": rows, "recovered": old.load(OUT / "recovered.json")})
    for r in rows:
        print(r)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["actuate", "score", "compare"])
    args = parser.parse_args()
    {"actuate": actuate, "score": score, "compare": compare}[args.command]()
