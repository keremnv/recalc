"""Prefer earned ProgramGroups over residual cells; default order stays frozen."""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import compiled_scheduler
import matched_compiled_treatment as m

FIXTURE = Path(__file__).parent / "fixtures/fm_02_01_scheduler_priority.json"
CELL_RE = re.compile(r"cell:s(\d+):r(\d+):c(\d+)")
TITLES = {
    0: "IS,BS,CF",
    1: "Revenue & COGS Schedule",
    2: "BS schedules",
    3: "Ratios",
    7: "Realization & EBIT Per KG",
}


def _parse_cell(cell_id: str) -> tuple[str, int, int]:
    match = CELL_RE.fullmatch(cell_id)
    assert match, cell_id
    sheet_index, row, col = (int(x) for x in match.groups())
    return TITLES[sheet_index], row, col


def _fm_runtime(tmp_path: Path, fixture: dict):
    meta = {}
    cids = {}
    op_by_id = {op["operation_id"]: op for op in fixture["operations"]}
    for op in fixture["operations"]:
        for cell_id in op["cell_ids"]:
            cell = _parse_cell(cell_id)
            meta[cell] = {
                "operation_id": op["operation_id"],
                "obligation_id": op["obligation_id"],
                "operation_kind": op["operation_kind"],
            }
            cids[cell] = cell_id
    calls = []

    def session(*args, **kwargs):
        target = args[3]
        calls.append(tuple(target["seed"] if "seed" in target else _parse_cell(target["cell_id"])))
        return {"synthesis": {"parsed": {"status": "PROPOSED", "formula": "=1"}}, "calls": []}

    def target_from_id(spine, cid, key, oid):
        cell = _parse_cell(cid)
        return {"cell_id": cid, "sheet": cell[0], "address": m.closure.a1(cell[1], cell[2]), "row": cell[1], "col": cell[2]}

    def synth(task_key, task, obligation, target, packet, state, task_dir, stub=False):
        seed = (target["sheet"], target["row"], target["col"])
        calls.append(seed)
        return {"synthesis": {"parsed": {"status": "PROPOSED", "formula": "=1"}}, "calls": [], "target": target}

    groups = fixture["groups"]
    pg = SimpleNamespace(groups_for=lambda *a, **k: (groups, []), translate=m.program_group.translate)
    runtime = SimpleNamespace(
        spine_for=lambda k: {},
        authorised_cells=lambda p: (meta, cids),
        task_source=lambda k: tmp_path / "input.xlsx",
        formula_forms=lambda p: {},
        input_kinds=lambda p: {},
        db_for=lambda k: None,
        db_precedent_graph=lambda p: {},
        program_group=pg,
        closure=m.closure,
        TaskBudget=m.TaskBudget,
        write_json=m.write_json,
        target_from_id=target_from_id,
        retrieval_synthesis=synth,
        validate_formula=lambda *a, **k: {"hard_verifier_result": "HARD_ACCEPT"},
        proposal_precedents=lambda f, c: set(),
    )
    obligations = [{"id": op["obligation_id"]} for op in fixture["operations"]]
    plan = {
        "expansion": {"operations": fixture["operations"], "cell_ids": fixture["cell_ids"]},
        "packets": {op["obligation_id"]: {} for op in fixture["operations"]},
    }
    compiler = {"obligations": obligations}
    return runtime, calls, compiler, plan, op_by_id


def _schedule(tmp_path, fixture, *, activation=None, call_limit=None):
    runtime, calls, compiler, plan, _ = _fm_runtime(tmp_path, fixture)
    if call_limit is not None:
        runtime.TaskBudget = lambda state: SimpleNamespace(
            failure=lambda: "TASK_MODEL_CALL_LIMIT" if len(calls) >= call_limit else None
        )
    state = {}
    if activation:
        state["scheduler_activation"] = activation
    result = compiled_scheduler.schedule(
        runtime, fixture["task"], {}, compiler, plan, state, tmp_path
    )
    return result, calls


def test_default_activation_matches_stored_spark_compiled_seeds(tmp_path):
    fixture = json.loads(FIXTURE.read_text())
    result, calls = _schedule(tmp_path, fixture, call_limit=5)
    assert [list(c) for c in calls] == fixture["control_seeds"]
    assert result["scheduler_activation"] == "operation_order"


def test_group_priority_defers_residuals_and_activates_later_groups(tmp_path):
    fixture = json.loads(FIXTURE.read_text())
    result, calls = _schedule(
        tmp_path, fixture, activation="prefer_earned_program_groups", call_limit=5
    )
    assert [list(c) for c in calls] == fixture["treatment_seeds_first_five"]
    assert result["scheduler_activation"] == "prefer_earned_program_groups"
    residual_l5 = ["Revenue & COGS Schedule", 5, 12]
    residual_k11 = ["BS schedules", 11, 11]
    assert residual_l5 not in [list(c) for c in calls]
    assert residual_k11 not in [list(c) for c in calls]
    assert ["Ratios", 9, 6] in [list(c) for c in calls]


def test_default_still_lets_earlier_residual_precede_group_canonical(tmp_path):
    """Sales-like: residual L5 sorts before group canonical M5 under the frozen rule."""
    fixture = json.loads(FIXTURE.read_text())
    _, calls = _schedule(tmp_path, fixture, call_limit=2)
    assert list(calls[0]) == ["IS,BS,CF", 34, 8]
    assert list(calls[1]) == ["Revenue & COGS Schedule", 5, 12]


def test_group_priority_does_not_split_failed_groups(tmp_path):
    fixture = json.loads(FIXTURE.read_text())
    runtime, calls, compiler, plan, _ = _fm_runtime(tmp_path, fixture)
    original = runtime.retrieval_synthesis

    def synth(*args, **kwargs):
        result = original(*args, **kwargs)
        seed = (args[3]["sheet"], args[3]["row"], args[3]["col"])
        if seed == ("IS,BS,CF", 34, 8):
            return {"synthesis": {"parsed": None}, "failure_class": "PROVIDER_TIMEOUT", "calls": []}
        return result

    runtime.retrieval_synthesis = synth
    state = {"scheduler_activation": "prefer_earned_program_groups"}
    result = compiled_scheduler.schedule(runtime, fixture["task"], {}, compiler, plan, state, tmp_path)
    eps_members = {("IS,BS,CF", 34, c) for c in (8, 9, 10, 11)}
    disposed = {tuple(v["cell"]) for v in result["dispositions"].values()}
    assert ("IS,BS,CF", 34, 8) in disposed
    assert not (eps_members - {("IS,BS,CF", 34, 8)}) & disposed
    assert calls[0] == ("IS,BS,CF", 34, 8)
    assert calls[1] == ("Revenue & COGS Schedule", 5, 13)
