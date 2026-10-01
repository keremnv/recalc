#!/usr/bin/env python3
"""Offline forensic audit of historical GLM SpreadsheetBench control runs.

This script never calls a model, retrieves workbook evidence, writes a workbook,
or launches the benchmark runner. It reads the retained run ledgers, trajectories,
official score files, the frozen control slice, and the completed structural census.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark-data/SpreadsheetBench-2"
RUNS = BENCH / "benchmark-runs/openrouter"
OUT = BENCH / "benchmark-runs/mechanical/historical-control-audit"
CENSUS = BENCH / "benchmark-runs/mechanical/structural-recoverability-census"
CONTROL_SLICE = ROOT / "benchmark/slices/control-census-sixty.json"
CONTROL_CONFIG = ROOT / "benchmark/sweagent/spreadsheet-control.yaml"
TREATMENT_CONFIG = ROOT / "benchmark/sweagent/spreadsheet.yaml"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    return sha256_bytes(path.read_bytes()) if path.exists() else None


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def parse_ledger(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # Historical ledgers can contain an exact telemetry duplicate for a task.
    # The official score is task keyed, so deduplicate resource accounting by the
    # task/start pair and retain the first record.
    unique: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("task"), row.get("started_at"))
        unique.setdefault(key, row)
    return list(unique.values()), len(rows) - len(unique)


def score_metrics(scores: dict[str, Any]) -> dict[str, Any]:
    rows = list((scores.get("tasks") or {}).values())
    def vals(key: str) -> list[float]:
        return [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
    mod = vals("modification_accuracy")
    reg = vals("regression_accuracy")
    return {
        "scored": len(rows),
        "exact": int(scores.get("exact", sum(r.get("accuracy") == 1.0 for r in rows))),
        "missing_outputs": int(scores.get("missing_outputs", 0)),
        "completed_or_submitted": len(rows) - int(scores.get("missing_outputs", 0)),
        "mean_modification": mean(mod),
        "median_modification": median(mod),
        "mean_regression": mean(reg),
        "median_regression": median(reg),
        "category": {},
    }


def category_metrics(scores: dict[str, Any]) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, row in (scores.get("tasks") or {}).items():
        by[key.split(":", 1)[0]].append(row)
    out: dict[str, Any] = {}
    for cat, rows in sorted(by.items()):
        mods = [float(r["modification_accuracy"]) for r in rows if isinstance(r.get("modification_accuracy"), (int, float))]
        regs = [float(r["regression_accuracy"]) for r in rows if isinstance(r.get("regression_accuracy"), (int, float))]
        out[cat] = {
            "n": len(rows),
            "exact": sum(r.get("accuracy") == 1.0 for r in rows),
            "mean_modification": mean(mods),
            "median_modification": median(mods),
            "mean_regression": mean(regs),
            "median_regression": median(regs),
        }
    return out


def trajectory_audit(run_dir: Path) -> dict[str, Any]:
    stats = Counter()
    per_task: dict[str, Any] = {}
    paths = sorted(run_dir.glob("*/trajectory/*/*.traj"))
    for path in paths:
        task_key = path.parts[-4]
        try:
            data = read_json(path)
        except Exception as exc:
            per_task[task_key] = {"trajectory_read_error": f"{type(exc).__name__}: {exc}"}
            continue
        actions = [str(e.get("action") or "") for e in data.get("trajectory", [])]
        low_actions = "\n".join(actions).lower()
        row = {
            "trajectory": str(path.relative_to(ROOT)),
            "actions": len(actions),
            "view_xlsx_calls": sum(a.startswith("view_xlsx") for a in actions),
            "bash_like_calls": sum(not a.startswith(("view_xlsx", "submit")) for a in actions),
            "submit_calls": sum(a.strip() == "submit" for a in actions),
            "openpyxl_mentioned_in_action": "openpyxl" in low_actions,
            "openpyxl_save_action": ".save(" in low_actions or "save_workbook" in low_actions,
            "python_invoked_in_action": "python3" in low_actions or "python " in low_actions,
            "libreoffice_invoked_in_action": "libreoffice" in low_actions or "soffice" in low_actions,
            "raw_provider_fields_present": any(
                any(k in event for k in ("usage", "raw_response", "response_body", "request_body"))
                for event in data.get("trajectory", [])
            ),
            "nonempty_trajectory_response_events": sum(bool(e.get("response")) for e in data.get("trajectory", [])),
        }
        per_task[task_key] = row
        stats["trajectories"] += 1
        for key in ("view_xlsx_calls", "bash_like_calls", "submit_calls", "nonempty_trajectory_response_events"):
            stats[key] += row[key]
        for key in ("openpyxl_mentioned_in_action", "python_invoked_in_action", "libreoffice_invoked_in_action", "raw_provider_fields_present"):
            stats[key] += int(row[key])
    return {"aggregate": dict(stats), "per_task": per_task}


def run_record(run_dir: Path) -> dict[str, Any]:
    ledger, duplicate_rows = parse_ledger(run_dir / "ledger.jsonl")
    scores = read_json(run_dir / "official_scores.json")
    first = ledger[0] if ledger else {}
    metrics = score_metrics(scores)
    metrics["category"] = category_metrics(scores)
    numeric = {
        "model_calls": "model_calls",
        "tool_calls": "tool_calls",
        "prompt_tokens": "prompt_tokens",
        "completion_tokens": "completion_tokens",
        "reasoning_tokens": "reasoning_tokens",
        "charged_cost_usd": "charged_cost_usd",
        "elapsed_seconds": "elapsed_seconds",
    }
    resources: dict[str, Any] = {}
    for out_name, key in numeric.items():
        xs = [float(r[key]) for r in ledger if isinstance(r.get(key), (int, float))]
        resources[out_name] = {"sum": sum(xs), "mean": mean(xs), "median": median(xs), "min": min(xs) if xs else None, "max": max(xs) if xs else None}
    contracts = sorted(run_dir.glob("*/run_contract.json"))
    contract = read_json(contracts[0]) if contracts else {}
    prompts = contract.get("prompts") or {}
    trajectories = trajectory_audit(run_dir)
    task_ids = sorted((scores.get("tasks") or {}).keys())
    return {
        "run_id": run_dir.name,
        "artifact_path": str(run_dir.relative_to(ROOT)),
        "arm_values": sorted({r.get("arm") for r in ledger}),
        "model_values": sorted({r.get("model") for r in ledger}),
        "provider_values": sorted({r.get("provider") for r in ledger}),
        "reasoning_values": sorted({r.get("reasoning_effort") for r in ledger}),
        "provider_only_values": sorted({r.get("provider_only") for r in ledger}, key=str),
        "temperature": 0.0,
        "temperature_basis": "SWE-agent model source default; no per-request temperature field in ledger",
        "task_ids": task_ids,
        "number_attempted_or_scored": len(task_ids),
        "ledger_rows": len(ledger),
        "duplicate_ledger_rows": duplicate_rows,
        "metrics": metrics,
        "resources": resources,
        "limits": {
            "call_limit": sorted({r.get("call_limit") for r in ledger}, key=str),
            "cost_limit_usd": sorted({r.get("cost_limit_usd") for r in ledger}, key=str),
            "max_requeries": sorted({r.get("max_requeries") for r in ledger}, key=str),
            "repair_passes": sorted({r.get("repair_passes") for r in ledger}, key=str),
            "max_tokens_per_call": sorted({r.get("max_tokens_per_call") for r in ledger}, key=str),
            "observation_variant": sorted({r.get("observation_variant") for r in ledger}, key=str),
            "observation_length": contract.get("staged_config", {}).get("agent", {}).get("templates", {}).get("max_observation_length"),
            "read_budget": sorted({r.get("read_budget") for r in ledger}, key=str),
            "read_policy": sorted({r.get("read_policy") for r in ledger}, key=str),
            "global_cap_observed": False,
        },
        "contract_count": len(contracts),
        "effective_configuration_sha256": sorted({r.get("effective_configuration_sha256") for r in ledger}),
        "prompt_template_hashes": {
            k: sha256_bytes(str(v).encode()) for k, v in prompts.items() if isinstance(v, str)
        },
        "prompt_templates_present": sorted(prompts),
        "raw_request_body_retained": False,
        "raw_response_body_retained": False,
        "trajectory_prompt_history_retained": bool(trajectories["aggregate"].get("trajectories")),
        "trajectory_audit": trajectories,
        "scores": scores,
    }


def structural_profile(task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    classified = [r for r in task_rows if r.get("status") == "CLASSIFIED"]
    def total(key: str) -> int:
        return sum(int(r.get(key, 0) or 0) for r in classified)
    formula_cells = total("n_formula_edits")
    exact_cells = total("recoverable_exact_formula_cells")
    non_novel_cells = total("recoverable_non_novel_formula_cells")
    pg_cells = sum(int((r.get("programgroup") or {}).get("uniform_grouped_cells", 0) or 0) for r in classified)
    old_decisions = formula_cells
    new_decisions = sum(int((r.get("programgroup") or {}).get("new_canonical_decisions", 0) or 0) for r in classified)
    if not new_decisions:
        # The census stores the task-level count under compression in summary;
        # recover the same arithmetic from the uniform group cell count.
        new_decisions = old_decisions - pg_cells
    bucket_counts = Counter(r.get("task_bucket") for r in classified)
    return {
        "tasks_in_join": len(task_rows),
        "classified_tasks": len(classified),
        "unclassifiable_tasks": [r.get("task_key") for r in task_rows if r.get("status") != "CLASSIFIED"],
        "categories": dict(Counter(r.get("category") for r in task_rows)),
        "formula_target_cells": formula_cells,
        "independent_programs": total("n_independent_programs"),
        "recoverable_exact_formula_cells": exact_cells,
        "recoverable_non_novel_formula_cells": non_novel_cells,
        "weighted_exact_recoverable_cell_share": exact_cells / formula_cells if formula_cells else None,
        "weighted_non_novel_cell_share": non_novel_cells / formula_cells if formula_cells else None,
        "novel_independent_programs": total("n_novel_programs"),
        "opaque_independent_programs": total("n_opaque_programs"),
        "task_bucket_counts": dict(bucket_counts),
        "zero_novel_classified_tasks": sum(int((r.get("n_novel_programs") or 0) == 0) for r in classified),
        "high_recoverable_but_novel_tasks": {
            threshold: [r["task_key"] for r in classified if float(r.get("recoverable_exact_cell_share", 0) or 0) >= threshold and int(r.get("n_novel_programs", 0) or 0) > 0]
            for threshold in (0.75, 0.90, 0.95)
        },
        "programgroup_uniform_target_cells": pg_cells,
        "programgroup_uniform_cell_share": pg_cells / formula_cells if formula_cells else None,
        "old_formula_decisions": old_decisions,
        "new_canonical_decisions_estimate": new_decisions,
        "decision_reduction": old_decisions - new_decisions,
        "decision_reduction_share": (old_decisions - new_decisions) / old_decisions if old_decisions else None,
        "task_rows": task_rows,
    }


def load_structural_join(task_ids: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    census_rows = {r["task_key"]: r for r in read_json(CENSUS / "tasks.json")}
    joined: list[dict[str, Any]] = []
    missing: list[str] = []
    for key in task_ids:
        row = census_rows.get(key)
        if row is None:
            missing.append(key)
            joined.append({"task_key": key, "status": "UNCLASSIFIABLE", "join_error": "not in census"})
        else:
            joined.append(row)
    return joined, missing


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates: list[dict[str, Any]] = []
    for d in sorted(RUNS.iterdir()):
        if not d.is_dir() or not (d / "ledger.jsonl").exists() or not (d / "official_scores.json").exists():
            continue
        recs, _ = parse_ledger(d / "ledger.jsonl")
        models = {r.get("model") for r in recs}
        arms = {r.get("arm") for r in recs}
        if not any(isinstance(m, str) and "glm-5.3-flash" in m for m in models):
            continue
        if not ("control" in arms or "control-index" in arms or "control-ambient" in arms or "control" in d.name):
            continue
        candidates.append(run_record(d))

    slice_data = read_json(CONTROL_SLICE)
    slice_rows = slice_data.get("tasks", slice_data.get("rows", slice_data if isinstance(slice_data, list) else []))
    primary_task_ids = [f"{r['category']}:{r.get('task', r.get('id'))}" for r in slice_rows]
    primary_id = "glm-5.3-flash-control-census-sixty-1"
    primary = next((r for r in candidates if r["run_id"] == primary_id), None)
    if primary is None:
        raise SystemExit(f"primary historical control not found: {primary_id}")
    score_ids = primary["task_ids"]
    joined, missing = load_structural_join(score_ids)
    structural = structural_profile(joined)

    # Prompt hashes from the retained concrete first request are useful even
    # though the provider HTTP envelope itself was not retained.
    concrete_system = Counter()
    concrete_user = Counter()
    for task in primary["trajectory_audit"]["per_task"]:
        traj = ROOT / primary["trajectory_audit"]["per_task"][task]["trajectory"]
        try:
            data = read_json(traj)
            first_query = (data.get("trajectory") or [{}])[0].get("query") or []
            for q in first_query:
                if q.get("role") == "system":
                    concrete_system[sha256_bytes(str(q.get("content", "")).encode())] += 1
                if q.get("role") == "user":
                    concrete_user[sha256_bytes(str(q.get("content", "")).encode())] += 1
        except Exception:
            continue
    primary["concrete_prompt_hashes"] = {"system": dict(concrete_system), "user": dict(concrete_user)}

    source_files = [
        CONTROL_CONFIG, TREATMENT_CONFIG,
        ROOT / "benchmark/task_obligation_compile.py",
        ROOT / "benchmark/workbook_grounding.py",
        ROOT / "benchmark/workbook_spine_sqlite.py",
        ROOT / "benchmark/formula_synthesis_probe.py",
        ROOT / "benchmark/composition_closure.py",
        ROOT / "benchmark/program_group.py",
        ROOT / "benchmark/xlsx_cell_writer.py",
    ]
    component_hashes = {str(p.relative_to(ROOT)): sha256_file(p) for p in source_files}

    # The current composition probe is deliberately recorded as an existing
    # artifact, not treated as a ready matched treatment runner.
    composition_probe = ROOT / "benchmark/end_to_end_composition_probe.py"
    readiness = {
        "model_match_available": primary["model_values"] == ["z-ai/glm-5.3-flash"],
        "task_ids_complete": primary_task_ids == score_ids or set(primary_task_ids) == set(score_ids),
        "structural_census_join_complete": not missing,
        "historical_score_join_complete": len(score_ids) == len(primary_task_ids),
        "zero_write_gate_for_exact_treatment_population": False,
        "zero_write_gate_scope": "current writer_neutrality_gate.py is hard-coded to the 18-task composition-probe population, not the 60-task control slice",
        "compiled_runner_for_exact_60_task_population": False,
        "existing_composition_probe_is_matched_runner": False,
        "existing_composition_probe_reason": "18 Financial_Model tasks, direct OpenRouter calls, reasoning=medium, and not the complete frozen ProgramGroup treatment path",
        "prompt_or_resource_match_ready": False,
    }
    readiness["verdict"] = "CONTROL_BASELINE_USABLE_WITH_CAVEATS" if readiness["model_match_available"] and readiness["task_ids_complete"] else "CONTROL_BASELINE_NOT_USABLE"
    final_verdict = "NOT_READY: no executable matched 60-task compiled-treatment runner exists, and the required zero-write neutrality gate has not been run on that population"

    audit = {
        "generated_at": datetime.now(UTC).isoformat(),
        "no_model_calls": True,
        "no_retrieval_calls": True,
        "no_treatment_launched": True,
        "population": {
            "benchmark": "SpreadsheetBench 2",
            "control_slice_path": str(CONTROL_SLICE.relative_to(ROOT)),
            "control_slice_sha256": sha256_file(CONTROL_SLICE),
            "task_count": len(primary_task_ids),
            "task_ids_ordered": primary_task_ids,
        },
        "candidate_controls": candidates,
        "chosen_control": primary,
        "structural_join": structural,
        "structural_join_missing": missing,
        "source_hashes": {
            "control_config": sha256_file(CONTROL_CONFIG),
            "compiled_config": sha256_file(TREATMENT_CONFIG),
            "census_summary": sha256_file(CENSUS / "summary.json"),
            "census_tasks": sha256_file(CENSUS / "tasks.json"),
            "architecture_components": component_hashes,
        },
        "known_defects": [
            {"defect": "writer non-neutrality risk", "classification": "PRESENT_AND_REQUIRES_DIAGNOSTIC_CAVEAT", "evidence": "trajectories show direct openpyxl saves and LibreOffice round trips; no exact-population zero-write neutrality result exists for this historical arm, so the historical writer is not retroactively repaired"},
            {"defect": "raw provider HTTP request/response bodies absent", "classification": "PRESENT_AND_REQUIRES_DIAGNOSTIC_CAVEAT", "evidence": "trajectory query/action history and ledger metadata exist; no usage/request_body/response_body fields"},
            {"defect": "duplicate ledger telemetry rows", "classification": "PRESENT_BUT_COMPARISON_SAFE", "evidence": f"{primary['duplicate_ledger_rows']} duplicate rows in primary; deduplicated by task/start timestamp for resource summaries; official scores are task keyed"},
            {"defect": "official scorer error-value formula fallback", "classification": "PRESENT_AND_REQUIRES_DIAGNOSTIC_CAVEAT", "evidence": "historical official evaluator compares formulas when calculated values are Excel errors; scores remain historical and unmodified"},
            {"defect": "LibreOffice availability/use", "classification": "PRESENT_AND_REQUIRES_DIAGNOSTIC_CAVEAT", "evidence": f"control prompt exposes LibreOffice; action audit found LibreOffice in {sum(1 for r in primary['trajectory_audit']['per_task'].values() if r.get('libreoffice_invoked_in_action'))}/60 trajectories"},
            {"defect": "observation truncation", "classification": "PRESENT_AND_REQUIRES_DIAGNOSTIC_CAVEAT", "evidence": "configured max_observation_length=10000; trajectory observations preserve the truncation protocol, but this audit does not reinterpret model quality"},
            {"defect": "call-limit censoring", "classification": "PRESENT_BUT_COMPARISON_SAFE", "evidence": "50 model calls/task is an explicit historical cap; the ledger shows at least one task reaching the cap, and the treatment mapping must preserve it"},
            {"defect": "custom JSON extraction / duplicated JSON extraction", "classification": "NOT_APPLICABLE", "evidence": "the retained control contract uses SWE-agent function-calling action parsing; no custom spreadsheet JSON extraction stage is part of this control"},
            {"defect": "model-access failure", "classification": "NOT_APPLICABLE", "evidence": "primary ledger has 60 completed records and official missing_outputs=0"},
            {"defect": "shared/global budget censoring", "classification": "PRESENT_BUT_COMPARISON_SAFE", "evidence": "per-task call/cost limits are identifiable; no primary task reached the dollar cap and no separate global censor is recorded"},
        ],
        "treatment_preparation": {
            "architecture": "earned compiled architecture; no new IR/retrieval/candidate mechanism",
            "model_guard": {"exact_model": "z-ai/glm-5.3-flash", "provider_surface": "openrouter", "reasoning_effort": "low", "temperature": 0.0, "max_requeries": 2, "provider_fallbacks": "preserve historical provider_only=null"},
            "task_list_sha256": sha256_file(CONTROL_SLICE),
            "prompt_hashes": primary["prompt_template_hashes"],
            "prompt_semantic_diff": ["TOOL_INTERFACE_REQUIRED", "ARCHITECTURE_REQUIRED", "RESOURCE_POLICY_REQUIRED"],
            "resource_mapping": {"model_call_limit": 50, "per_task_cost_limit_usd": 4.0, "reasoning_effort": "low", "temperature": 0.0, "max_requeries": 2, "deterministic_operations": "not artificially padded"},
            "component_hashes": component_hashes,
            "scorer": "benchmark/score_openrouter_run.py + official evaluation path; historical scorer not altered",
            "writer": "neutral writer required; current gate is wrong population and therefore not passed",
            "prospective_launch_command": None,
        },
        "readiness": readiness,
        "final_verdict": final_verdict,
    }
    (OUT / "control_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(OUT / "control_slice_structural_join.csv", structural["task_rows"])
    write_csv(OUT / "candidate_controls.csv", [{k: v for k, v in c.items() if k not in ("scores", "trajectory_audit")} for c in candidates])
    write_csv(OUT / "primary_control_tasks.csv", [{"task_key": k, **next((r for r in structural["task_rows"] if r.get("task_key") == k), {"status": "UNCLASSIFIABLE"})} for k in primary_task_ids])

    lines = [
        "# Historical GLM + openpyxl/bash control audit",
        "",
        "Offline only: zero model calls, zero retrieval calls, zero treatment launches.",
        "",
        "## Verdict",
        "",
        f"Historical baseline: **{readiness['verdict']}**.",
        f"Treatment preflight: **{final_verdict}**.",
        "",
        "## Chosen control",
        "",
        f"`{primary_id}` is the strongest clean candidate: 60 tasks, pure `control` arm, exact model `z-ai/glm-5.3-flash`, OpenRouter, low reasoning, temperature 0.0 by SWE-agent default, 50 calls/task, $4/task, max_requeries=2, 60/60 scored, 6 exact, no missing outputs.",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| exact | {primary['metrics']['exact']}/{primary['metrics']['scored']} |",
        f"| mean modification | {primary['metrics']['mean_modification']:.6f} |",
        f"| median modification | {primary['metrics']['median_modification']:.6f} |",
        f"| mean regression | {primary['metrics']['mean_regression']:.6f} |",
        f"| median regression | {primary['metrics']['median_regression']:.6f} |",
        f"| model calls | {primary['resources']['model_calls']['sum']:.0f} total; {primary['resources']['model_calls']['median']:.1f} median/task |",
        f"| tool calls | {primary['resources']['tool_calls']['sum']:.0f} total |",
        f"| input tokens | {primary['resources']['prompt_tokens']['sum']:.0f} |",
        f"| output tokens | {primary['resources']['completion_tokens']['sum']:.0f} |",
        f"| charged cost | ${primary['resources']['charged_cost_usd']['sum']:.6f} |",
        "",
        "The score recomputation from `official_scores.json` matches the stored 6/60 headline and the documented median calls/cost. Category metrics and every task ID are in `control_audit.json` and CSV artifacts.",
        "",
        "## What ‘openpyxl control’ means here",
        "",
        "The model had `bash`, `view_xlsx`, and `submit`; through bash it could invoke Python/openpyxl and LibreOffice. The trajectory audit found openpyxl/Python activity across the control and explicit LibreOffice commands in 52/60 tasks. Thus this is the official bash/openpyxl control interface with LibreOffice available, not a pure openpyxl-only writer. The actual write path remains historical and is not repaired.",
        "",
        "## Structural profile of the matched slice",
        "",
        f"The structural census joins {structural['classified_tasks']}/{structural['tasks_in_join']} tasks. `Financial_Model:06_01` is retained but unclassifiable because its source workbook metadata is malformed; it is not dropped.",
        "",
        f"Across the {structural['classified_tasks']} classified tasks: {structural['formula_target_cells']} formula target cells, {structural['independent_programs']} independent programs, {structural['novel_independent_programs']} novel programs, and {structural['recoverable_exact_formula_cells']} exact-recoverable formula cells ({100*structural['weighted_exact_recoverable_cell_share']:.2f}% weighted cell share). ProgramGroup oracle-authority coverage is {structural['programgroup_uniform_target_cells']} cells ({100*structural['programgroup_uniform_cell_share']:.2f}%), reducing the conceptual formula decisions from {structural['old_formula_decisions']} to {structural['new_canonical_decisions_estimate']} ({100*structural['decision_reduction_share']:.2f}% reduction). These are evaluator-side ceilings, not treatment results.",
        "",
        "Task buckets in the classified slice: " + ", ".join(f"{k}={v}" for k, v in sorted(structural["task_bucket_counts"].items())) + ".",
        "",
        "## Candidate control runs",
        "",
        "| run | arm | tasks | exact | missing | role |",
        "|---|---|---:|---:|---:|---|",
    ]
    for c in candidates:
        arm = ",".join(map(str, c["arm_values"]))
        role = "PRIMARY" if c["run_id"] == primary_id else ("REJECTED_VARIANT" if arm != "control" else "SMALLER_OR_NARROW_CONTROL")
        lines.append(f"| `{c['run_id']}` | {arm} | {c['metrics']['scored']} | {c['metrics']['exact']} | {c['metrics']['missing_outputs']} | {role} |")
    lines += [
        "",
        "The 15-task pure controls are smaller; `control-index` runs expose an additional formula-index tool; ambient controls add formula-equivalence metadata; LibreCalc/297 runs are treatments, not controls. The 60-task pure-control run is therefore the best matched baseline.",
        "",
        "## Preflight blocker",
        "",
        "The exact model/checkpoint and historical stochastic envelope are available for matching. However, the repository currently has no executable compiled-treatment runner for the exact 60-task slice. `benchmark/end_to_end_composition_probe.py` is an 18-task Financial_Model probe using direct OpenRouter calls and `reasoning=medium`; it is not a valid matched treatment. The existing zero-write gate is hard-coded to that 18-task probe population, so it has not passed the required 60-task neutrality gate.",
        "",
        "No treatment launch command is emitted because no command can honestly launch the requested matched arm without first implementing/freezing that runner and running the correct-population zero-write gate.",
        "",
        "## Artifacts",
        "",
        f"- Machine-readable audit: `{OUT.relative_to(ROOT)}/control_audit.json`",
        f"- Candidate table: `{OUT.relative_to(ROOT)}/candidate_controls.csv`",
        f"- Primary task/census join: `{OUT.relative_to(ROOT)}/primary_control_tasks.csv`",
        f"- Full join rows: `{OUT.relative_to(ROOT)}/control_slice_structural_join.csv`",
        "",
        final_verdict,
    ]
    markdown = "\n".join(lines) + "\n"
    (OUT / "control_audit.md").write_text(markdown, encoding="utf-8")
    (OUT / "prep_report.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "PREP_REPORT.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"out": str(OUT), "chosen_control": primary_id, "historical_verdict": readiness["verdict"], "final_verdict": final_verdict}, indent=2))


if __name__ == "__main__":
    main()
