#!/usr/bin/env python3
"""Frozen checkpoint cohort selection. Deterministic; persists seed, universe,
exclusions, full exposure ranking, and selection rule. No outcome peeking:
Cohort A = stratified random; Cohort B = historical-control inspection burden.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "research/history/thin_architecture_checkpoint"
DATA = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data"
SEED = 20260919


def universe() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    tasks, excluded = {}, {}
    for cat in ("Financial_Model", "Template", "Debugging"):
        ds = json.loads((DATA / cat / "dataset.json").read_text())
        ok, bad = [], []
        for d in ds:
            tid = str(d["id"])
            src = DATA / cat / d["spreadsheet_path"]
            (ok if src.exists() else bad).append(tid)
        tasks[cat] = sorted(ok)
        if bad:
            excluded[cat] = sorted(bad)
    return tasks, excluded


def cohort_a(tasks: dict[str, list[str]]) -> dict[str, list[str]]:
    rng = random.Random(SEED)
    return {cat: sorted(rng.sample(tasks[cat], 4)) for cat in
            ("Financial_Model", "Template", "Debugging")}


def exposure_ranking() -> list[dict]:
    ex = [json.loads(l) for l in
          open(PROJECT_ROOT / "research/history/control_python_audit" / "python_executions.jsonl")]
    labels = {}
    for line in open(PROJECT_ROOT / "research/history/control_python_audit" / "purpose_classification.jsonl"):
        p = json.loads(line)
        labels[p["exec_id"]] = p["labels"]
    feats: dict[str, dict] = defaultdict(
        lambda: {"views": 0, "opens": 0, "scans": 0, "inspect_events": 0, "inspect_bytes": 0,
                 "fam": ""})
    for e in ex:
        k = f"{e['family']}:{e['task_id'].split(':')[-1]}"
        f = feats[k]
        f["fam"] = e["family"]
        lab = labels.get(e["exec_id"], [])
        if e["action_kind"] == "view_xlsx":
            f["views"] += 1
        src = e.get("source") or ""
        f["opens"] += src.count("load_workbook")
        f["scans"] += src.count("iter_rows") + src.count("iter_cols")
        if any(x in lab for x in ("HEADER_PERIOD_SEARCH", "TEXT_SEARCH", "WORKBOOK_INSPECTION")):
            f["inspect_events"] += 1
            f["inspect_bytes"] += e.get("script_bytes", 0) + e.get("observation_bytes", 0)
    rows = [{"task_id": k, **v} for k, v in feats.items()]
    for key in ("views", "opens", "scans", "inspect_events", "inspect_bytes"):
        mx = max(r[key] for r in rows) or 1
        for r in rows:
            r[f"n_{key}"] = r[key] / mx
    for r in rows:
        r["exposure"] = (r["n_views"] + r["n_opens"] + r["n_scans"] +
                         r["n_inspect_events"] + r["n_inspect_bytes"]) / 5
    return sorted(rows, key=lambda r: (-r["exposure"], r["task_id"]))


def cohort_b(ranking: list[dict], taken: set[str]) -> dict[str, list[str]]:
    sel: dict[str, list[str]] = {"Financial_Model": [], "Template": [], "Debugging": []}
    for r in ranking:
        fam = r["fam"]
        if fam not in sel:  # nonvisual checkpoint; Viz ranked but not selected
            continue
        if len(sel[fam]) >= 4:
            continue
        if r["task_id"] in taken:
            continue  # keep cohorts disjoint where practical
        sel[fam].append(r["task_id"])
    return {k: sorted(v) for k, v in sel.items()}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tasks, excluded = universe()
    a = cohort_a(tasks)
    taken = {f"{c}:{t}" for c, ts in a.items() for t in ts}
    ranking = exposure_ranking()
    b = cohort_b(ranking, taken)
    json.dump({"seed": SEED, "universe_sizes": {k: len(v) for k, v in tasks.items()},
               "excluded_missing_file": excluded, "selected": a,
               "rule": "random.Random(20260919).sample(sorted_ids, 4) per family"},
              open(OUT / "representative_selection.json", "w"), indent=1)
    json.dump({"features": ["views", "opens", "scans", "inspect_events", "inspect_bytes"],
               "score": "mean of per-feature max-normalized values; NOT tuned post hoc",
               "source": "control_python_audit historical default-control trajectories only",
               "ranking": ranking}, open(OUT / "exposure_ranking.json", "w"), indent=1)
    json.dump({"selected": b, "rule": "top-4 per family by exposure, skipping Cohort-A members"},
              open(OUT / "exposure_selection.json", "w"), indent=1)
    pop = [{"task_id": f"{c}:{t}", "cohort": "A-representative"} for c, ts in a.items() for t in ts]
    pop += [{"task_id": t, "cohort": "B-exposure"} for c, ts in b.items() for t in ts]
    json.dump({"tasks": pop, "n": len(pop)}, open(OUT / "population.json", "w"), indent=1)
    print("A:", a)
    print("B:", b)


if __name__ == "__main__":
    main()
