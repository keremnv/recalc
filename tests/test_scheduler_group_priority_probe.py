import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))

import scheduler_group_priority_probe as probe
import matched_compiled_treatment as treatment


def test_treatment_root_does_not_collide_with_control_or_live():
    assert probe.TREATMENT_ROOT != probe.CONTROL_ROOT
    assert probe.TREATMENT_ROOT != treatment.LIVE
    assert probe.TASK == "Financial_Model:02_01"


def test_spec_freezes_plan_and_refuses_tempting_repairs():
    spec = probe.spec()
    assert spec["treatment"]["scheduler_activation"] == "prefer_earned_program_groups"
    assert spec["control"]["rerun"] is False
    assert spec["exclusions"]["no_cap_raise"] is True
    assert spec["exclusions"]["no_absolute_reference_verifier"] is True
    assert spec["exclusions"]["no_programgroup_reopen"] is True
    assert spec["not_exact_claim"] is True
    assert spec["treatment"]["frozen"] == ["task_ir", "edit_plan", "authorised_target_set", "packets"]


def test_compare_gain_and_tradeoff_verdicts():
    control = {
        "modification_accuracy": 0.9778,
        "model_call_count": 40,
        "seeds": [["IS,BS,CF", 34, 8], ["Revenue & COGS Schedule", 5, 12]],
        "remaining_authorised": 21,
    }
    groups = [{"canonical_cell": ["Ratios", 9, 6], "member_cells": [["Ratios", 9, 6]]}]
    treatment_result = {
        "status": "COMPLETED",
        "state": {"model_call_count": 40},
        "schedule": {
            "canonical_decisions": [{"seed": ["IS,BS,CF", 34, 8]}, {"seed": ["Ratios", 9, 6]}],
            "eligible_program_groups": groups,
            "unresolved_authorised_targets": ["x"] * 17,
            "translated_count": 7,
            "scheduler_activation": "prefer_earned_program_groups",
        },
        "failure_ledger": [],
    }
    gain = probe.compare(control, treatment_result, {"tasks": {probe.TASK: {"modification_accuracy": 0.9804}}})
    assert gain["verdict"] == "GROUP_PRIORITY_MODIFICATION_GAIN"
    loss = probe.compare(control, treatment_result, {"tasks": {probe.TASK: {"modification_accuracy": 0.9760}}})
    assert loss["verdict"] == "GROUP_PRIORITY_TRADEOFF"
