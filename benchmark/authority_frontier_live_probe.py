"""Two-call O1 planner-only temporal integration experiment.

The archived Task IR and workbook are fixed. CONTROL uses the current grounder
over the old local-period spine; TREATMENT uses the repaired temporal relation
from the shared database. This script makes exactly one Edit Plan request per
condition, then expands the returned plans offline. It never invokes retrieval,
synthesis, scheduling, writing, LibreOffice, or scoring.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import fm_resource_feasibility as feasibility
import matched_compiled_treatment as m
from openpyxl.utils.cell import coordinate_to_tuple

TASK = "Financial_Model:13_05"
SHORT = "13_05"
OBLIGATION_ID = "O1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cell_id(spine: dict[str, Any], label: str) -> str:
    sheet, address = label.rsplit("!", 1)
    row, col = coordinate_to_tuple(address)
    return f"cell:s{int(spine['title_to_index'][sheet]):02d}:r{row}:c{col}"


def expand(condition: str, parsed: Any, world: m.World, obligation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"status": "NO_PARSED_PLAN", "cell_ids": [], "operations": []}
    try:
        result = m.expand_edit_plan(parsed, world, {OBLIGATION_ID}, id_contract="V2")
        return {"status": result["status"], "cell_ids": result.get("cell_ids", []), "operations": result.get("operations", []), "provenance": result.get("provenance", {})}
    except m.PlanError as exc:
        return {"status": exc.category, "error": str(exc), "cell_ids": [], "operations": []}


def run(output: Path) -> dict[str, Any]:
    archive = m.RUN_ROOT / "resource_feasibility/live/repaired_treatment_credit_restored_merged_for_bridge" / "Financial_Model-13_05" / "result.json"
    result = read(archive)
    compiler = result["compiler"]
    obligation = next(o for o in compiler["obligations"] if o["id"] == OBLIGATION_ID)
    task = {"instruction": compiler["raw_task"]}
    local_spine = m.spine_for(TASK)
    old_db_path = m.DATABASES / "Financial_Model-13_05.sqlite"
    repaired_db_path = feasibility.REPAIRED_DATABASES / "Financial_Model-13_05.sqlite"
    if not old_db_path.is_file() or not repaired_db_path.is_file():
        raise FileNotFoundError("Both original and repaired 13_05 databases are required")
    control_world = m.World(old_db_path)
    treatment_world = m.World(repaired_db_path)
    try:
        treatment_spine = m.planning_spine_for(TASK, treatment_world)
        control_packet = m.project_obligation(local_spine, obligation)
        treatment_packet = m.project_obligation(treatment_spine, obligation)
        compiler_o1 = copy.deepcopy(compiler)
        contexts = {
            "CONTROL": m._fragment_context(task, compiler_o1, obligation, control_packet, control_world, projected=True),
            "TREATMENT": m._fragment_context(task, compiler_o1, obligation, treatment_packet, treatment_world, projected=True),
        }
        user_payloads = {k: json.dumps(v, ensure_ascii=False, separators=(",", ":")) for k, v in contexts.items()}
        # Everything in the model request is shared except the deterministic
        # GROUNDING value. Confirm this before spending either provider call.
        control_without_grounding = copy.deepcopy(contexts["CONTROL"])
        treatment_without_grounding = copy.deepcopy(contexts["TREATMENT"])
        control_without_grounding.pop("GROUNDING", None)
        treatment_without_grounding.pop("GROUNDING", None)
        assert control_without_grounding == treatment_without_grounding
        output.mkdir(parents=True, exist_ok=True)
        (output / "control_context.json").write_text(json.dumps(contexts["CONTROL"], ensure_ascii=False, indent=2) + "\n")
        (output / "treatment_context.json").write_text(json.dumps(contexts["TREATMENT"], ensure_ascii=False, indent=2) + "\n")
        delta = {
            "control_packet": {"scope": control_packet["scope"], "target_cell_ids": control_packet["target_cell_ids"], "counts": control_packet["counts"]},
            "treatment_packet": {"scope": treatment_packet["scope"], "target_cell_ids": treatment_packet["target_cell_ids"], "counts": treatment_packet["counts"]},
            "scope_added": sorted({x["id"] for x in treatment_packet["scope"]} - {x["id"] for x in control_packet["scope"]}),
            "scope_removed": sorted({x["id"] for x in control_packet["scope"]} - {x["id"] for x in treatment_packet["scope"]}),
            "target_added": sorted(set(treatment_packet["target_cell_ids"]) - set(control_packet["target_cell_ids"])),
            "target_removed": sorted(set(control_packet["target_cell_ids"]) - set(treatment_packet["target_cell_ids"])),
            "non_temporal_context_equal": True,
            "control_user_sha256": digest(user_payloads["CONTROL"]),
            "treatment_user_sha256": digest(user_payloads["TREATMENT"]),
        }
        (output / "evidence_delta.json").write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n")
    finally:
        control_world.close()
        treatment_world.close()

    old_runtime = m.configure_runtime(
        max_model_calls=1, max_cost_usd=feasibility.NATURAL_COST_CEILING,
        frontend_mode="sharded_projected",
    )
    calls: dict[str, dict[str, Any]] = {}
    try:
        for condition in ("CONTROL", "TREATMENT"):
            task_dir = output / condition.lower()
            state = {"model_call_count": 0, "provider_cost_usd": 0.0, "failure_ledger": []}
            call = m.call_or_stub(task_dir, TASK, "edit_plan", m.EDIT_PLAN_PROMPT, user_payloads[condition], state, stub=False)
            calls[condition] = {"call": call, "state": state}
    finally:
        m.restore_runtime(old_runtime)

    gold_labels = ["Input Sheet!I20", "Input Sheet!J20", "Input Sheet!K20", "Input Sheet!L20", "Input Sheet!M20"]
    gold = {cell_id(local_spine, label) for label in gold_labels}
    expanded = {}
    for condition, world_path, world_factory in (("CONTROL", old_db_path, m.World), ("TREATMENT", repaired_db_path, m.World)):
        world = world_factory(world_path)
        try:
            parsed = calls[condition]["call"].get("parsed_response")
            expanded[condition] = expand(condition, parsed, world, obligation)
        finally:
            world.close()
    quality = {}
    for condition in ("CONTROL", "TREATMENT"):
        ids = set(expanded[condition].get("cell_ids", []))
        quality[condition] = {
            "authority_count": len(ids),
            "gold_count": len(gold),
            "intersection_count": len(ids & gold),
            "recall": len(ids & gold) / len(gold),
            "precision": len(ids & gold) / len(ids) if ids else None,
            "true_positive_cells": sorted(ids & gold),
            "false_positive_cells": sorted(ids - gold),
            "false_negative_cells": sorted(gold - ids),
        }
    provider = {}
    for condition in ("CONTROL", "TREATMENT"):
        call = calls[condition]["call"]
        provider[condition] = {
            "failure_class": call.get("failure_class"),
            "provider_attempt": call.get("failure_class") not in {"TASK_MODEL_CALL_LIMIT", "TASK_COST_LIMIT"},
            "finish_reason": call.get("finish_reason"),
            "parsed": isinstance(call.get("parsed_response"), dict),
            "raw_response_retained": call.get("raw_response_body") is not None,
            "model_call_count": calls[condition]["state"].get("model_call_count"),
            "provider_cost_usd": call.get("provider_cost_usd", 0.0),
        }
    both_returned = all(provider[c]["failure_class"] is None and provider[c]["parsed"] for c in ("CONTROL", "TREATMENT"))
    if not both_returned:
        verdict = "PROVIDER_CENSORED"
    elif quality["TREATMENT"]["recall"] > quality["CONTROL"]["recall"] and quality["TREATMENT"]["precision"] >= quality["CONTROL"]["precision"]:
        verdict = "TEMPORAL_INTEGRATION_CASHES_OUT"
    elif quality["TREATMENT"]["recall"] == quality["CONTROL"]["recall"] and quality["TREATMENT"]["precision"] == quality["CONTROL"]["precision"]:
        verdict = "TEMPORAL_EVIDENCE_NOT_USED"
    elif quality["TREATMENT"]["recall"] < quality["CONTROL"]["recall"] or quality["TREATMENT"]["precision"] < quality["CONTROL"]["precision"]:
        verdict = "TEMPORAL_PROJECTION_INTERFERENCE"
    else:
        verdict = "TEMPORAL_EVIDENCE_NOT_USED"
    report = {
        "experiment": "authority_frontier_live_probe",
        "task": TASK,
        "obligation_id": OBLIGATION_ID,
        "model_calls": 2,
        "downstream_calls": {"retrieval": 0, "synthesis": 0},
        "workbook_writes": 0,
        "libreoffice_runs": 0,
        "scoring_runs": 0,
        "conditions": {"CONTROL": {"period_source": "original local-period spine", "database": str(old_db_path)}, "TREATMENT": {"period_source": "repaired shared temporal projection", "database": str(repaired_db_path)}},
        "freeze": {"raw_task_sha256": digest(compiler["raw_task"]), "obligation_sha256": digest(obligation), "system_prompt_sha256": digest(m.EDIT_PLAN_PROMPT), "model": feasibility.MODEL, "reasoning": feasibility.REASONING, "temperature": feasibility.TEMPERATURE, "top_p": feasibility.TOP_P, "provider_policy": feasibility.PROVIDER_POLICY, "max_tokens": feasibility.MAX_OUTPUT_TOKENS, "percentage_parser": "corrected", "target_ordering": "sorted", "non_temporal_context_equal": delta["non_temporal_context_equal"]},
        "evidence_delta": delta,
        "returned_plans": {c: calls[c]["call"].get("parsed_response") for c in ("CONTROL", "TREATMENT")},
        "raw_calls": {c: calls[c]["call"] for c in ("CONTROL", "TREATMENT")},
        "expanded_authority": expanded,
        "quality": quality,
        "provider": provider,
        "causal_verdict": verdict,
        "interpretation": "This tests temporal evidence integration into one Edit Plan decision only. It does not test retrieval, synthesis, scheduling, writing or scoring.",
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("task", "obligation_id", "model_calls", "evidence_delta", "quality", "provider", "causal_verdict")}, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
