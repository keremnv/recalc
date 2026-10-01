#!/usr/bin/env python3
"""Assemble the offline census and repair gates from persisted evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import integration_autopsy as a
import matched_compiled_treatment as m


def pct(v):
    return "N/A" if v is None else f"{100*v:.2f}%"


def report():
    f = m.read_json(a.OUT / "funnel.json")
    floor_path = a.OUT / "zero_edit_floor_scores.json"
    floors = m.read_json(floor_path) if floor_path.exists() else {"rows": [], "inert_count": None}
    floor_by = {r["task"]: r for r in floors["rows"]}
    allcalls = [c for t in f["tasks"] for c in t["calls"]]
    props = [p for t in f["tasks"] for p in t["proposals"]]
    groups = [g for t in f["tasks"] for g in t["groups"]]
    units = [u for t in f["tasks"] for u in t["units"]]
    conditions = [c for t in f["tasks"] for c in t["conditional"]]
    missed = [g for t in f["tasks"] for g in t["missed_groups"]]
    stage_counts = Counter((c["task"], c["category"], c["stage"]) for c in allcalls if c["provider_attempt"])
    m.write_csv(a.OUT / "model_call_events.csv", allcalls)
    call_stages = ["Task IR", "grounding/resolution", "Edit Plan", "retrieval/query selection", "canonical synthesis", "ungrouped-cell synthesis", "closure-member synthesis", "other"]
    m.write_csv(a.OUT / "call_stage_counts.csv", [{"task": t["totals"]["task"], "category": t["totals"]["category"], "stage": stage, "provider_attempts": stage_counts[(t["totals"]["task"], t["totals"]["category"], stage)]} for t in f["tasks"] for stage in call_stages])
    rows = []
    for task in f["tasks"]:
        row = task["totals"]
        g = set(task["raw_content_edits"]["gold"])
        if row["task"] in floor_by:
            floor = floor_by[row["task"]]
            row.update(floor)
            row["calls_per_correct_scorer_cell_gained"] = a.ratio(row["model_calls"], floor["correct_scorer_cells_gained"])
            detail = m.read_json(a.OUT / "scorer_cells" / (row["task"].replace(":", "-") + ".json"))
            correct = set(detail["treatment"]["modification"]["value_cells"]) | set(detail["treatment"]["regression"]["value_cells"])
            task["stages"]["R1"] = {"count_entering": len(g), "count_surviving": len(g & correct), "stage_count": len(g & correct), "survival_percent": 100*len(g & correct)/len(g) if g else None, "gold_target_recall": a.ratio(len(g & correct), len(g)), "precision": None, "unit": "gold content edit cells within scorer ranges correct by value"}
            mods = set(detail["treatment"]["modification"]["value_cells"])
            task["stages"]["R2"] = {"stage_count": len(mods-g), "count_entering": detail["treatment"]["modification"]["total"], "count_surviving": len(mods-g), "gold_target_recall": None, "precision": None, "unit": "correct scorer modification cells outside gold content edit coordinates"}
        # The funnel branches between units, groups and ungrouped actuation.
        # Explicit predecessors prevent interpreting a branch merge as a loss.
        predecessors = {"G1": "G0", "P1": "G0", "P2": "P1", "P3": "P1", "S0": "P3", "S1": "S0", "S2": "S1", "S3": "S2", "S4": "S3", "S5": "S4", "E0": "S4", "E2": "P1", "E3": "E2", "E4": "E0", "E5": "E3", "W0": "P1", "W1": "W0", "W2": "W1", "W3": "W2"}
        for name, prev in predecessors.items():
            stage = task["stages"][name]; before = task["stages"][prev]
            entry, after = set(before.get("cells", [])), set(stage.get("cells", []))
            stage.update(predecessor=prev, count_entering=len(entry), count_surviving=len(entry & after), survival_percent=100*len(entry & after)/len(entry) if entry else None)
        task["stages"]["E3"]["program_group_count"] = len(task["groups"])
        task["stages"]["E4"]["invalid_origin_group_count"] = sum(not g["origin_is_member"] for g in task["groups"])
        for stage in task["stages"].values():
            for field in ("count_entering", "count_surviving", "survival_percent", "gold_target_recall", "precision"):
                stage.setdefault(field, None)
        for name, stage in task["stages"].items():
            for field in ("stage_count", "count_entering", "count_surviving", "survival_percent", "gold_target_recall", "precision"):
                row[f"{name}_{field}"] = stage.get(field)
        rows.append(row)
    f["stage_aggregates"] = {}
    for category in ("ALL", "Template", "Financial_Model", "Debugging"):
        selected = [t for t in f["tasks"] if category == "ALL" or t["totals"]["category"] == category]
        f["stage_aggregates"][category] = {}
        for stage in selected[0]["stages"]:
            entries = [t["stages"][stage] for t in selected]
            aggregate = {}
            for field in ("stage_count", "count_entering", "count_surviving"):
                ns = [e.get(field) for e in entries]
                aggregate[field] = sum(ns) if all(n is not None for n in ns) else None
            aggregate["survival_percent"] = 100*a.ratio(aggregate["count_surviving"], aggregate["count_entering"]) if aggregate.get("count_entering") and aggregate.get("count_surviving") is not None else None
            if all("cells" in e for e in entries):
                hits = sum(len(set(t["stages"][stage]["cells"]) & set(t["raw_content_edits"]["gold"])) for t in selected)
                aggregate["gold_target_recall"] = a.ratio(hits, sum(t["totals"]["gold_edit_cells"] for t in selected))
                aggregate["precision"] = a.ratio(hits, aggregate["stage_count"])
            else:
                aggregate["gold_target_recall"] = aggregate["precision"] = None
            f["stage_aggregates"][category][stage] = aggregate
    m.write_json(a.OUT / "funnel.json", f)
    m.write_csv(a.OUT / "per_task_funnel.csv", rows)
    m.write_csv(a.OUT / "financial_model_authority_distribution.csv", [r for r in rows if r["category"] == "Financial_Model"])
    correct_gold_props = [p for p in props if p.get("gold_target")]
    lines = ["# Integration autopsy — failed matched 60-task treatment", "", "Classification: **MULTIPLE_INTEGRATION_FAILURES**, dominated by frontend target loss and budget fragmentation. No new model calls were used. The artifacts do not support a claim that the earned mechanisms are harmful, nor a low-reasoning causal attribution.", "", "## Primary findings", "", "| Category | Gold content edits | Output edits | Output ∩ gold | Outside gold | Gold-write recall | Write precision |", "|---|---:|---:|---:|---:|---:|---:|"]
    for cat, s in f["summary"].items():
        lines.append(f"| {cat} | {s['gold_edit_cells']} | {s['output_semantic_edits']} | {s['output_edits_intersect_gold']} | {s['output_edits_outside_gold']} | {pct(s['gold_write_recall'])} | {pct(s['write_precision'])} |")
    lines += ["", f"The zero-edit-floor test finds **{floors['inert_count']}/60 effectively inert** tasks using the predeclared |modification gain| ≤ 0.001 threshold. Per-cell official and value-only outcomes, including cells newly correct over floor, are retained in `scorer_cells/` and `zero_edit_floor_scores.json`.", "", f"There were {len(correct_gold_props)} parseable proposals at true gold formula targets, {sum(p['exact_formula'] for p in correct_gold_props)} exact formula matches. {sum(p['classification']=='WRITTEN_AS_PROPOSED' for p in correct_gold_props)} were written as proposed; the remainder were explicitly hard-rejected. The seven scheduler-dropped proposals were all non-gold targets. Thus proposal-to-writer loss is a real defect, but does not explain the missing useful writes in this run.", "", "## Earliest supported loss", "", "| Category | Task spec | Edit Plan authority | Scheduling | Operational |", "|---|---:|---:|---:|---:|"]
    for cat, s in f["summary"].items():
        c = s["diagnosis_counts"]
        lines.append(f"| {cat} | {c.get('F0_TASK_SPEC',0)} | {c.get('F2_EDIT_PLAN_AUTHORITY',0)} | {c.get('F3_TARGET_SCHEDULING',0)} | {c.get('OPERATIONAL_FAILURE',0)} |")
    lines += ["", "Earliest supported mechanical loss wins. Structured Task IR is empty on nine tasks. Invalid/empty authority or gold-content recall below 50% precedes scheduling. The other valid plans leave gold formula targets without sessions. No unsupported semantic judgments were used to separate F1 grounding from F2 authority: independent clause-level semantic annotations are absent from this run. The raw instruction survives in full, but that does not prove its structured requirements, subject or scope survive.", "", "## Calls and budget fragmentation", "", "The state totals sum to 1,936; the immutable call-file census has **1,937 provider attempts** plus 74 budget-block pseudo-call records. Financial_Model:04_01 contains both `002_edit_plan.json` (provider rejection) and `002_task_ir.json` (resumed parse), followed by `003_edit_plan.json`. This exactly explains the one-call undercount. Timeouts are attempts, not successful completions; their provider usage/cost is unavailable. Archived invalid earlier runs are excluded from this 60-task population.", "", "| Stage | Attempts |", "|---|---:|"]
    for stage, n in f["call_stage_totals"].items(): lines.append(f"| {stage} | {n} |")
    lines += ["| Stochastic grounding | 0 |", "| Dedicated closure-member synthesis | 0 |", "| Other | 0 |", "", "1,622/1,937 attempts (83.7%) were retrieval. Of 234 persisted target sessions, 176 used all eight retrieval turns. The normal active task reached the cap after about six sessions; 38 tasks reached 50 counted calls. The final retrieval episode could consume the remaining budget and prevent synthesis. No writes occurred until the terminal writer batch, so calls before the first useful gold write equal all task attempts when such a write exists; otherwise that metric is undefined.", "", "The retrieval continuation passed `delta=None` even after 622 calls added entities, advertising an empty NEW_SINCE_LAST_TURN. Only the latest SQL result was shown on the next request. The synthesis prompt inherited a retrieval preamble explicitly saying not to synthesize. Both are protocol/composition defects. Their semantic effect cannot be measured by pretending stored responses would have changed under a corrected prompt.", "", "## Authority and Financial_Model distribution", "", "| Task | Gold edits | Authority | Gold recall | Formula recall | Precision | Plan status |", "|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        if r["category"] == "Financial_Model": lines.append(f"| {r['task']} | {r['gold_edit_cells']} | {r['authority_cells']} | {pct(r['authority_gold_recall'])} | {pct(r['formula_target_recall'])} | {pct(r['authority_precision'])} | {r['plan_status']} |")
    lines += ["", "Every frozen temporal JSON was an empty placeholder. The database therefore had no temporal coordinates even when the Edit Plan used TEMPORAL_INTERVAL and period IDs. This is a supported integration defect: the earned temporal compiler was not called. Restoring it uses input-only facts and does not change temporal inference rules. Plans that remain too narrow or broad after that repair are not repaired with benchmark-derived selection rules.", "", "## Conditional synthesis and mechanism cash-out", "", f"There are {len(conditions)} sessions selected at true gold formula targets. Under the mechanical direct-reference coverage definition, {sum(c['retrieval_complete'] for c in conditions)} have complete coverage; this does not prove semantic sufficiency. Exact formula and relative fingerprint results are cross-tabulated by existing/novel and retrieval coverage in `conditional_synthesis.csv`. False selected targets are excluded.", "", f"Runtime formed {len(groups)} ProgramGroups across the run, but just one in Financial_Model: Assumption sheet E44:F44 on 06_01. Both were false targets, and no grouped Financial_Model gold cells were cashed out. Evaluator-side missed eligible groups: {dict(Counter(g['cause'] for g in missed))}. Those causes are ordered observations, not proof that every authorized group would pass the runtime operation partition/witness contract.", "", f"There are {len(units)} C1 execution records. All recorded execution members are inside authority: {all(u['authority_invariant'] for u in units)}. There are {sum(len(u['unsolved_marked_assigned_same_operation']) for u in units)} recorded member occurrences which the old scheduler marks assigned in the current operation without a session or write. Safety containment held, but membership was incorrectly treated as completion. Group formation could also translate a seed into an unrelated prerequisite group and omit the seed's own write.", "", "## Measurement limits and reproducibility", "", "`funnel.json` contains all requested G/T/P/S/E/W/R stages per task and category. Cell stages report entering/surviving counts, intersection survival, gold recall and precision. Groups/programs/tasks have different units; null metrics denote non-comparable units or missing semantic-retention annotations, never guessed zeroes. Group and ungrouped branches merge at actuation, so the funnel has explicit predecessors rather than a misleading single nesting chain.", "", "Semantic writes compare formula/literal content in the delivered output.xlsx against its effective input; recalculation-cache drift is not a write. Gold content differences ignore empty strings/whitespace as blanks, include all workbook cells, and use no score-derived tolerance. 06_01 is metadata repaired and included (83 content edits, 76 formula edits); the old structural census could not classify it. Financial_Model:04_01 has 487 semantic content edits under this rule versus the old census's 4,978; formula edits agree at 421. These definitions and denominator differences must not be conflated.", "", "The zero-edit floor uses the exact staged original input copies and official LibreOffice refresh. Scoring invokes the official cell-classification and comparison functions, including Debugging Color/Embedded modes, formula-error fallback, four-decimal rounding and regression snapping. A compact read-only cell adapter prevents large workbook evaluations from retaining multiple full openpyxl object graphs; it changes no comparator. Official treatment scores are checked against the frozen scores before accepting this path.", "", "Reproduce with `python benchmark/integration_autopsy.py analyze`, `score-details`, then `python benchmark/integration_report.py`. Gold/evaluator code is confined to the offline audit and report. The runtime scheduler imports no autopsy or gold data. Phase B remains blocked until the separate repair gates pass."]
    mpath = m.ROOT / "INTEGRATION_AUTOPSY_REPORT.md"
    mpath.write_text("\n".join(lines) + "\n")
    (a.OUT / "INTEGRATION_AUTOPSY_REPORT.md").write_text("\n".join(lines) + "\n")
    print(mpath)


if __name__ == "__main__":
    report()
