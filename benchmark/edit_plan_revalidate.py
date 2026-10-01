#!/usr/bin/env python3
"""Post-hoc revalidation of the frozen Phase B responses under the corrected ID contract.

Zero model calls. The stored plan JSON is replayed verbatim through the same
expansion algebra; only which citation identities are legal changes. This is a
diagnostic on the frozen run, never a replacement for its primary result: it
answers "how much of the frontend failure was our validator?" and nothing else.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_plan_probe as p
from edit_plan import World, PlanError, expand_edit_plan

old = p.old


def replay(record, contract):
    task = record["task"]
    if not isinstance(record.get("parsed"), dict):
        return {"task": task, "status": record["status"], "error": record.get("error")}
    world = World(old.relational.db_path(task))
    obligations = {o["id"] for o in record["compiler"]["obligations"]}
    try:
        expansion = expand_edit_plan(record["parsed"], world, obligations, contract)
        gold = p.gold_ids(task, world)
        ids = set(expansion["cell_ids"])
        out = {"task": task, "status": expansion["status"], "error": None, "gold_count": len(gold),
               "expanded_count": len(ids), "true_targets": len(ids & gold), "false_targets": len(ids - gold),
               "missed_targets": len(gold - ids),
               "precision": len(ids & gold) / len(ids) if ids else 0,
               "recall": len(ids & gold) / len(gold) if gold else None}
    except PlanError as exc:
        world_gold = None
        try:
            world_gold = len(p.gold_ids(task, world))
        except Exception:
            pass
        out = {"task": task, "status": exc.category, "error": str(exc), "gold_count": world_gold,
               "expanded_count": 0, "true_targets": 0, "false_targets": 0,
               "missed_targets": world_gold, "precision": 0, "recall": 0.0}
    world.close()
    return out


def micro(rows):
    scored = [r for r in rows if r.get("gold_count")]
    sel = sum(r["expanded_count"] for r in scored)
    true = sum(r["true_targets"] for r in scored)
    gold = sum(r["gold_count"] for r in scored)
    return {"tasks": len(scored), "selected": sel, "true_targets": true, "gold": gold,
            "micro_recall": true / gold if gold else None,
            "micro_precision": true / sel if sel else None,
            "valid_plan_tasks": sum(r["status"] in ("VALID_PLAN", "EMPTY_EXPANSION") for r in scored)}


def main():
    records = [old.load(f) for f in sorted((p.OUT / "phase_b").glob("*.json"))]
    v1 = [replay(r, "V1") for r in records]
    v2 = [replay(r, "V2") for r in records]
    by_task = {r["task"]: r for r in v1}
    moved = [{"task": r["task"], "was": by_task[r["task"]]["status"], "was_error": by_task[r["task"]].get("error"),
              "now": r["status"], "now_error": r.get("error"), "true_targets": r["true_targets"],
              "false_targets": r["false_targets"], "recall": r["recall"], "precision": r["precision"]}
             for r in v2 if r["status"] != by_task[r["task"]]["status"]]
    payload = {
        "kind": "POST_HOC_DIAGNOSTIC_ON_FROZEN_RESPONSES",
        "model_calls": 0,
        "scope": "Replays the stored Phase B plan JSON through the same expansion algebra under the corrected citation contract. Does not replace the frozen primary result and does not repair any plan.",
        "v1_micro": micro(v1), "v2_micro": micro(v2),
        "tasks_recovered_by_contract_fix": moved,
        "v1_rows": v1, "v2_rows": v2,
    }
    p.save("posthoc_revalidation.json", payload)
    print(json.dumps({k: payload[k] for k in ("v1_micro", "v2_micro")}, indent=2))
    print(f"tasks whose validity changed: {len(moved)}")
    for m in moved:
        print(f"  {m['task']}: {m['was']} ({m['was_error']}) -> {m['now']}"
              + (f" recall={m['recall']:.3f} precision={m['precision']:.3f}" if m["recall"] is not None else ""))


if __name__ == "__main__":
    main()
