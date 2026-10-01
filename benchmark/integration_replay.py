#!/usr/bin/env python3
"""Replay repaired scheduling using archived responses only; no model adapter.

Missing responses remain missing. The evaluator never supplies formula text.
Archived workbooks, databases, calls and task states are never overwritten.
"""
from __future__ import annotations

import argparse
import copy
import gc
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import integration_autopsy as a
import matched_compiled_treatment as m
from temporal_spine import compile_temporal_workbook
from workbook_spine_sqlite import build_database

REPLAY = a.OUT / "replay"


def forbidden(*args, **kwargs):
    raise RuntimeError("OFFLINE_REPLAY_MODEL_CALL_FORBIDDEN")


def replay():
    original_db = m.DATABASES
    m.model_call = forbidden
    m.retrieval_synthesis = forbidden
    rows = []
    for row in m.task_rows():
        gc.collect()
        key = row["task_key"]
        dest = REPLAY / key.replace(":", "-")
        if (dest / "result.json").exists():
            rows.append(m.read_json(dest / "result.json")["audit"])
            continue
        print("REPLAY", key, flush=True)
        old = m.read_json(m.LIVE / key.replace(":", "-") / "result.json")
        plan = copy.deepcopy(old["edit_plan"])
        plan["spine"] = m.spine_for(key)
        # Restore the existing temporal compiler in a private database. Freeze
        # the result separately; the failed run's evidence stays immutable.
        temporal_path = a.OUT / "repaired_temporal" / (key.replace(":", "-") + ".json")
        if not temporal_path.exists():
            m.write_json(temporal_path, compile_temporal_workbook(m.task_source(key), closure=True))
        m.DATABASES = a.OUT / "repaired_db"
        db_path = m.db_for(key)
        if not db_path.exists():
            build_database(m.SPINES / (key.replace(":", "-") + ".json"), temporal_path, db_path)
        status_before = plan.get("status")
        if isinstance(plan.get("parsed"), dict):
            world = m.World(db_path)
            try:
                expansion = m.expand_edit_plan(plan["parsed"], world, {o["id"] for o in old["compiler"].get("obligations", [])}, id_contract="V2")
                plan.update(expansion=expansion, status=expansion["status"])
            except m.PlanError as exc:
                plan.update(expansion=None, status=exc.category, expansion_error=str(exc))
            finally:
                world.close()
        sessions = {p["target"]["cell_id"]: p for p in old["schedule"].get("canonical_decisions", [])}
        state = {"model_call_count": 0, "provider_cost_usd": 0, "replay_stored_sessions_only": True, "scheduler_v2": {"sessions": sessions, "edits": {}, "dispositions": {}, "units": [], "failures": []}}
        result = m.schedule_formula_work(key, row, old["compiler"], plan, state, dest, stub=False)
        write = m.write_cells(m.task_source(key), dest / "output.xlsx", result["edits"])
        old_audit = m.read_json(a.OUT / "tasks" / (key.replace(":", "-") + ".json"))
        source, gold = a.cells(m.task_source(key)), a.cells(Path(row["gold_path"]))
        output = a.cells(dest / "output.xlsx")
        gold_edits = a.changed(source, gold); output_edits = a.changed(source, output)
        audit = {"task": key, "old_submitted_writes": old_audit["totals"]["output_semantic_edits"], "replay_submitted_writes": len(output_edits), "old_gold_writes": old_audit["totals"]["output_edits_intersect_gold"], "replay_gold_writes": len(gold_edits & output_edits), "old_gold_write_recall": old_audit["totals"]["gold_write_recall"], "replay_gold_write_recall": a.ratio(len(gold_edits & output_edits), len(gold_edits)), "old_plan_status": status_before, "replay_plan_status": plan["status"], "old_authority_count": old["schedule"].get("authorized_targets", 0), "replay_authority_count": result["authorized_targets"], "new_model_calls": 0, "write_rejections": write.get("rejected"), "replay_missing_response_count": sum(v["status"] == "REPLAY_NO_STORED_RESPONSE" for v in result["dispositions"].values()), "temporal_coordinates": m.read_json(temporal_path).get("n_coordinates")}
        m.write_json(dest / "result.json", {"audit": audit, "schedule": result, "write_audit": write})
        rows.append(audit)
        m.DATABASES = original_db
    m.DATABASES = original_db
    m.write_json(a.OUT / "deterministic_replay_scores.json", {"model_calls": 0, "status": "WRITES_REPLAYED_SCORING_PENDING", "rows": rows})


def score():
    summary = m.read_json(a.OUT / "deterministic_replay_scores.json")
    for row, audit in zip(m.task_rows(), summary["rows"], strict=True):
        gc.collect()
        key = row["task_key"]
        path = REPLAY / key.replace(":", "-") / "scorer_cells.json"
        if path.exists(): detail = m.read_json(path)
        else:
            rel = Path("submission/outputs") / row["category"] / f"{row['task']}_output.xlsx"
            detail = a.detailed_score(row, {"replay": REPLAY / rel})
            m.write_json(path, detail)
        old = m.read_json(a.OUT / "scorer_cells" / (key.replace(":", "-") + ".json"))
        audit["old_modification"] = old["treatment"]["modification"]["official_accuracy"]
        audit["replay_modification"] = detail["replay"]["modification"]["official_accuracy"]
        audit["modification_delta"] = (audit["replay_modification"] or 0) - (audit["old_modification"] or 0)
        audit["replay_value_only"] = detail["replay"]["modification"]["value_accuracy"]
        print("REPLAY_SCORE", key, audit["modification_delta"], flush=True)
    summary["status"] = "COMPLETE"
    m.write_json(a.OUT / "deterministic_replay_scores.json", summary)


def reconcile_noops():
    """Reapply no-op filtering to completed replay states without resynthesis.

    This is the exact post-verifier no-op branch in compiled_scheduler. All
    removed writes must equal input formulas, and output bytes must be unchanged
    before accepting existing recalculation/scorer artifacts as reusable.
    """
    records = []
    for row in m.task_rows():
        gc.collect()
        directory = REPLAY / row["task_key"].replace(":", "-")
        result = m.read_json(directory / "result.json")
        before_hash = m.file_digest(directory / "output.xlsx")
        forms = m.formula_forms(m.task_source(row["task_key"]))
        schedule = result["schedule"]
        noops = {a.cellkey(e) for e in schedule["edits"] if forms.get(a.cellkey(e)) == e["formula"]}
        if not noops:
            continue
        schedule["edits"] = [e for e in schedule["edits"] if a.cellkey(e) not in noops]
        schedule["translated_formula_instances"] = [e for e in schedule["translated_formula_instances"] if tuple(e["cell"]) not in noops]
        for rec in schedule["dispositions"].values():
            if tuple(rec["cell"]) in noops:
                rec["status"] = "NO_SEMANTIC_CHANGE"
        schedule["translated_count"] = sum(v["status"] == "TRANSLATED_WRITE_SCHEDULED" for v in schedule["dispositions"].values())
        result["write_audit"] = m.write_cells(m.task_source(row["task_key"]), directory / "output.xlsx", schedule["edits"])
        result["audit"]["write_rejections"] = result["write_audit"]["rejected"]
        after_hash = m.file_digest(directory / "output.xlsx")
        # A no-op can still alter XML caches. Check formula/content identity
        # against the already refreshed copy via scheduled payloads separately;
        # if archive bytes differ require a refresh, never reuse silently.
        records.append({"task": row["task_key"], "noops": sorted(map(a.label, noops)), "byte_identical": before_hash == after_hash})
        state = m.read_json(directory / "state.json")
        state["completed_edits"] = schedule["edits"]
        for rec in state.get("scheduler_v2", {}).get("dispositions", {}).values():
            if tuple(rec["cell"]) in noops:
                rec["status"] = "NO_SEMANTIC_CHANGE"
        state["scheduler_v2"]["edits"] = {k: v for k, v in state["scheduler_v2"]["edits"].items() if tuple(v["cell"]) not in noops}
        m.write_json(directory / "state.json", state)
        cache = directory / "scorer_cells.json"
        if before_hash != after_hash and cache.exists():
            cache.rename(directory / "scorer_cells.pre_noops.json")
        m.write_json(directory / "result.json", result)
    m.write_json(a.OUT / "replay_noop_reconciliation.json", records)
    summary = m.read_json(a.OUT / "deterministic_replay_scores.json")
    for row in summary["rows"]:
        row["write_rejections"] = m.read_json(REPLAY / row["task"].replace(":", "-") / "result.json")["write_audit"]["rejected"]
    summary["status"] = "NOOPS_RECONCILED_REFRESH_PENDING"
    m.write_json(a.OUT / "deterministic_replay_scores.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["replay", "refresh", "score", "reconcile-noops"])
    args = parser.parse_args()
    if args.command == "replay": replay()
    elif args.command == "refresh":
        from score_openrouter_run import _stage_outputs, _refresh_outputs
        tasks = [{"category": r["category"], "id": r["task"]} for r in m.task_rows()]
        _stage_outputs(REPLAY, tasks, REPLAY / "submission/outputs")
        _refresh_outputs(REPLAY / "submission/outputs")
    elif args.command == "reconcile-noops": reconcile_noops()
    else: score()
