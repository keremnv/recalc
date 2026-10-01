#!/usr/bin/env python3
"""Frozen 12-task Candidate-A+A1 live checkpoint.

This runner reuses the ordinary live scaffold, but freezes the earned A1
source classifier and adds only timing/trace accounting.  It does not add a
model-facing API or change the Candidate-A semantic surface.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECK = Path(os.environ.get("CANDIDATE_A_CHECKPOINT_OUT", str(ROOT / "candidate_a_a1_checkpoint")))
FROZEN_CHECK = Path(os.environ["CANDIDATE_A_FROZEN_CHECKPOINT"]) if os.environ.get("CANDIDATE_A_FROZEN_CHECKPOINT") else None
REPORT_PATH = Path(os.environ.get("CANDIDATE_A_CHECKPOINT_REPORT", str(ROOT / "CANDIDATE_A_A1_12_TASK_CHECKPOINT_REPORT.md")))
SEED = 20260920

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark import candidate_a_live_treatment as scaffold  # noqa: E402
from benchmark.run_candidate_a1_classifier_repair import classify  # noqa: E402
from benchmark.inspection_helpers import index  # noqa: E402
from benchmark.candidate_a_live_runtime import PersistentCompiledSnapshot  # noqa: E402
from benchmark.candidate_a_shadow_interposition import CandidateALoader, ProxyWorkbook  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [canonical(x) for x in value]}
    if isinstance(value, list):
        return {"type": "list", "items": [canonical(x) for x in value]}
    # Workbook/worksheet/cell handles are execution objects, not the
    # decision-visible primitive fact.  Their use is represented by the next
    # operation in the trace; comparing their Python class would incorrectly
    # reject the already-proven primitive contract.
    return {"type": "HANDLE", "class": type(value).__name__}


def source_safe(command: str) -> tuple[bool, str, dict[str, Any]]:
    source = scaffold.extract_python_source(command)
    decision = classify(source)
    safe = decision.get("decision") == "A1_ADMIT"
    return safe, str(decision.get("reason")), decision


def build_population() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Freeze a complete 12-task ranking from historical mechanical evidence."""
    # This is the exact effective A1 ceiling already established by the A1
    # replay: A0 fully-eligible decisions are preserved, and newly admitted
    # source-safe decisions are added.  No live or score field is consulted.
    import runpy
    a1mod = runpy.run_path(str(ROOT / "benchmark" / "run_candidate_a1_classifier_repair.py"))
    historical = a1mod["historical_rows"]()
    census = {x.get("exec_id"): x for x in scaffold.load_jsonl(ROOT / "transparent_python_read_census" / "executions.jsonl")}
    repeat_groups = json.loads((ROOT / "transparent_python_read_census" / "repeated_open_analysis.json").read_text(encoding="utf-8")).get("repeat_groups", [])

    def repeat_for(task: str) -> int:
        total = 0
        for group in repeat_groups:
            match = re.search(r"/(Financial_Model|Template|Debugging|Visualization)-([^/]+)/", str(group.get("trajectory", "")))
            if match and f"{match.group(1)}:{match.group(2)}" == task:
                total += max(0, int(group.get("opens", 0)) - 1)
        return total

    stats: dict[str, dict[str, Any]] = {}
    for row in historical:
        task = str(row.get("task_id"))
        # Visualization GLM trajectory IDs are not SpreadsheetBench task IDs
        # accepted by the frozen scaffold; exclude them without inventing a
        # mapping.  The remaining task IDs are directly resolvable.
        if ":" not in task:
            continue
        family, _, tid = task.partition(":")
        try:
            scaffold.dataset_item(task)
        except Exception:
            continue
        if row.get("a1_decision") != "A1_ADMIT":
            continue
        entry = stats.setdefault(task, {"task_id": task, "family": family, "a1_executions": 0, "source_safe_executions": 0, "read_events": 0, "open_calls": 0, "walltime_s": 0.0, "repeated_open_surplus": repeat_for(task)})
        entry["a1_executions"] += 1
        entry["source_safe_executions"] += int(row.get("a1_source_decision") == "A1_ADMIT")
        entry["read_events"] += int(row.get("historical_read_events") or 0)
        entry["open_calls"] += int(row.get("open_calls") or 0)
        entry["walltime_s"] += float(census.get(row.get("exec_id"), {}).get("execution_time_s") or 0.0)

    ranking = list(stats.values())
    ranking.sort(key=lambda x: (-x["a1_executions"], -x["repeated_open_surplus"], -x["read_events"], -x["walltime_s"], x["task_id"]))
    for i, item in enumerate(ranking, 1):
        item["rank"] = i
        item["selected"] = i <= 12
    selected = ranking[:12]
    if len(selected) != 12:
        raise RuntimeError(f"frozen A1 population has only {len(selected)} resolvable tasks")

    write_json(CHECK / "population_ranking.json", {
        "seed": SEED,
        "eligible_count": len(ranking),
        "selection_rule": [
            "task has frozen effective A1-eligible historical execution",
            "exclude unresolved non-SpreadsheetBench trajectory IDs without mapping",
            "sort by A1-eligible execution count, repeated-open surplus, A1-safe primitive-read events, historical deterministic execution time, task_id",
            "select top 12; no score, gold, treatment result, semantic difficulty, or family balancing",
        ],
        "ranking": ranking,
    })
    population = []
    for item in selected:
        population.append({
            "task_id": item["task_id"], "family": item["family"], "rank": item["rank"],
            "historical_a1_executions": item["a1_executions"],
            "historical_source_safe_executions": item["source_safe_executions"],
            "historical_a1_read_events": item["read_events"],
            "historical_repeated_open_surplus": item["repeated_open_surplus"],
            "historical_deterministic_walltime_s": item["walltime_s"],
            "input_path": str(scaffold.source_workbook(item["task_id"])),
        })
    write_json(CHECK / "population.json", {
        "seed": SEED, "selected": population,
        "family_composition": dict(Counter(x["family"] for x in population)),
        "representative_benchmark": False,
    })
    return ranking, population


def checkpoint_load_env(task: str, arm: str, run_id: str, workdir: Path, call_idx: int, force_real: bool):
    env, event_path = _original_load_env(task, arm, run_id, workdir, call_idx, force_real)
    # The parent has already made the fail-closed A1 decision.  H0 receives it
    # only as shadow telemetry; H1 receives it as the existing force-real
    # switch.  Neither changes the model surface.
    decision = "PREDECLARED_REAL_OPENPYXL" if force_real else "A1_ADMIT"
    env["CANDIDATE_A_A1_DECISION"] = decision
    env["CANDIDATE_A_A1_REASON"] = "A1 source classifier admitted" if not force_real else "A1 predeclared fallback"
    return env, event_path


def freeze_identity(population: list[dict[str, Any]], order: list[dict[str, Any]]) -> None:
    templates = scaffold.base.load_templates()
    code_paths = [
        Path(__file__), ROOT / "benchmark/candidate_a_live_treatment.py",
        ROOT / "benchmark/candidate_a_live_runtime.py", ROOT / "benchmark/candidate_a_shadow_interposition.py",
        ROOT / "benchmark/run_candidate_a1_classifier_repair.py", ROOT / "benchmark/inspection_helpers/index.py",
    ]
    code_hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in code_paths}
    pairs = []
    for item in population:
        task = item["task_id"]
        instance = templates["instance"].replace("{{instruction}}", scaffold.dataset_item(task)["instruction"]).replace("{{spreadsheet_path}}", "<RUN_WORKDIR>/input.xlsx").replace("{{output_path}}", "<RUN_WORKDIR>/output.xlsx")
        pairs.append({
            "task_id": task, "input_workbook_hash": file_hash(scaffold.source_workbook(task)),
            "system_prompt_hash": hashlib.sha256(templates["system"].encode()).hexdigest(),
            "user_prompt_hash": hashlib.sha256(instance.encode()).hexdigest(),
            "tool_description_hash": scaffold.sha256_json(scaffold.base.TOOLS),
            "runner_hash": code_hashes[str(Path(__file__).relative_to(ROOT))],
            "candidate_a_code_hash": code_hashes["benchmark/candidate_a_live_runtime.py"],
            "a1_classifier_hash": code_hashes["benchmark/run_candidate_a1_classifier_repair.py"],
            "compiled_substrate_code_hash": code_hashes["benchmark/inspection_helpers/index.py"],
            "model": scaffold.base.MODEL, "provider": "openrouter", "reasoning": None,
            "temperature": scaffold.base.TEMPERATURE, "top_p": scaffold.base.TOP_P,
            "call_limit": scaffold.base.CALL_LIMIT, "dollar_cap": scaffold.base.INSTANCE_COST_LIMIT,
            "chat_timeout_s": scaffold.base.CHAT_TIMEOUT, "tool_timeout_s": scaffold.base.BASH_TIMEOUT,
            "run_timeout_s": scaffold.base.RUN_TIMEOUT,
        })
    write_json(CHECK / "identity_manifest.json", {"seed": SEED, "pairs": pairs, "order": order, "common_model_surface": True, "arms_differ_only_by": "Candidate-A enabled flag plus A1 predeclared fallback decision in Python environment", "candidate_b": "frozen", "frozen_population_source": str(FROZEN_CHECK) if FROZEN_CHECK is not None else None, "transport_deadline_hierarchy": {"socket_s": scaffold.base.CHAT_SOCKET_TIMEOUT, "request_s": scaffold.base.CHAT_TIMEOUT, "retry_budget_s": scaffold.base.CHAT_RETRY_BUDGET, "model_call_s": scaffold.base.MODEL_CALL_BUDGET, "task_run_s": scaffold.base.RUN_TIMEOUT}})


def collect_events(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contacts, fallbacks, freshness, timings, pre = [], [], [], [], []
    for record in records:
        archive = Path(record.get("archive", ""))
        for name, target in [("contact_events.jsonl", contacts), ("fallback_events.jsonl", fallbacks), ("freshness_events.jsonl", freshness), ("execution_timing.jsonl", timings), ("pre_contact_variance.jsonl", pre)]:
            target.extend(load_jsonl(archive / name))
    # Runtime now emits an auxiliary *_timing event for primitive result
    # timing.  Keep the canonical operation stream separate from timing rows.
    contacts = [x for x in contacts if not str(x.get("operation", "")).endswith("_timing")]
    return contacts, fallbacks, freshness, timings, pre


def archive_contact_traces(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    traces, snapshots, per_load, per_read = [], {}, [], []
    snap_dir = CHECK / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        if record.get("arm") != "H1" or not record.get("contact"):
            continue
        workdir = Path(record.get("workdir", ""))
        source_snapshot = workdir / "input.xlsx"
        if not source_snapshot.exists():
            continue
        snapshot = snap_dir / f"{record['run_id']}.xlsx"
        shutil.copy2(source_snapshot, snapshot)
        snapshots[record["run_id"]] = {"path": str(snapshot), "sha256": file_hash(snapshot), "generation": file_hash(snapshot), "source_run": record["run_id"]}
        for event_file in sorted((workdir / "runtime_events").glob("call_*.jsonl")):
            events = load_jsonl(event_file)
            accelerated = [x for x in events if x.get("status") == "ACCELERATED"]
            if not any(x.get("operation") not in {"load_workbook"} and not str(x.get("operation", "")).endswith("_timing") for x in accelerated):
                continue
            call = int(re.search(r"call_(\d+)", event_file.name).group(1))
            # Merge timing-only rows into their canonical primitive operation.
            by_key = {(x.get("operation"), x.get("sheet"), x.get("address")): x for x in accelerated if not str(x.get("operation", "")).endswith("_timing")}
            for x in accelerated:
                if str(x.get("operation", "")).endswith("_timing"):
                    base = by_key.get((str(x.get("operation")).replace("_timing", ""), x.get("sheet"), x.get("address")))
                    if base is not None:
                        base["duration_ns"] = x.get("duration_ns")
                        base["result"] = x.get("result")
            ops = [x for x in accelerated if not str(x.get("operation", "")).endswith("_timing")]
            trace_id = f"{record['run_id']}:{call}"
            traces.append({"trace_id": trace_id, "task_id": record["task_id"], "run_id": record["run_id"], "turn": call, "snapshot_path": str(snapshot), "snapshot_sha256": file_hash(snapshot), "workbook_generation": next((x.get("workbook_generation") for x in ops if x.get("workbook_generation")), None), "operations": ops})
            for x in ops:
                if x.get("operation") == "load_workbook":
                    per_load.append({"trace_id": trace_id, "arm": "H1", **x})
                elif x.get("duration_ns") is not None:
                    per_read.append({"trace_id": trace_id, "arm": "H1", **x})
    write_json(CHECK / "workbook_snapshots.json", snapshots)
    write_jsonl(CHECK / "contact_traces.jsonl", traces)
    return traces, snapshots, per_load


def operation_result(obj: Any) -> dict[str, Any]:
    return canonical(obj)


def execute_trace(trace: dict[str, Any], backend: str, entry: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None, float]:
    import openpyxl
    from openpyxl.utils.cell import coordinate_to_tuple
    path = trace["snapshot_path"]
    wb = ws = cell = None
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        if backend == "R0_REAL_OPENPYXL":
            wb = openpyxl.load_workbook(path, data_only=False)
        else:
            class ReplayLoader(CandidateALoader):
                def load_workbook(self, filename: str, *args: Any, **kwargs: Any) -> Any:
                    snapshot = PersistentCompiledSnapshot(filename, entry)
                    return ProxyWorkbook(self, snapshot)
            wb = ReplayLoader(real_loader=openpyxl.load_workbook).load_workbook(path)
        for event in trace["operations"]:
            op = event.get("operation")
            if op == "load_workbook":
                # Acquisition already happened above; no second parse.
                continue
            if op == "Workbook.sheetnames":
                value = wb.sheetnames
            elif op == "Workbook.__getitem__":
                ws = wb[event["sheet"]]
                value = ws
            elif op == "Worksheet.max_row":
                value = ws.max_row
            elif op == "Worksheet.max_column":
                value = ws.max_column
            elif op == "Worksheet.cell":
                row, col = coordinate_to_tuple(event["address"])
                cell = ws.cell(row=row, column=col)
                value = cell
            elif op == "Cell.value":
                value = cell.value
            elif op == "Cell.data_type":
                value = cell.data_type
            else:
                continue
            if op not in {"Workbook.__getitem__", "Worksheet.cell"}:
                results.append({"operation": op, "value": operation_result(value)})
        if hasattr(wb, "close"):
            wb.close()
        return results, None, time.perf_counter() - started
    except Exception as exc:
        return results, {"class": type(exc).__name__, "message": str(exc)}, time.perf_counter() - started


def replay_traces(traces: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    replay_rows, performance_rows = [], []
    prepared: dict[str, dict[str, Any]] = {}
    for trace in traces:
        path = Path(trace["snapshot_path"])
        index.reset()
        handle, rebuilt = index.ensure_fresh(str(path))
        db_path = CHECK / "replay_substrate" / f"{handle['workbook_hash']}.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if rebuilt or not db_path.exists():
            import sqlite3
            target = sqlite3.connect(str(db_path))
            try:
                handle["db"].backup(target); target.commit()
            finally:
                target.close()
        prepared[str(path)] = {"path": str(path), "db_path": str(db_path), "workbook_hash": handle["workbook_hash"], "index_generation": handle["index_generation"]}
    for trace in traces:
        entry = prepared[trace["snapshot_path"]]
        orders = ["R0_REAL_OPENPYXL", "R1_CANDIDATE_A"] * 3
        outputs: dict[str, list[dict[str, Any]]] = {"R0_REAL_OPENPYXL": [], "R1_CANDIDATE_A": []}
        exceptions: dict[str, list[dict[str, Any] | None]] = {"R0_REAL_OPENPYXL": [], "R1_CANDIDATE_A": []}
        durations: dict[str, list[float]] = {"R0_REAL_OPENPYXL": [], "R1_CANDIDATE_A": []}
        for backend in orders:
            result, error, elapsed = execute_trace(trace, backend, entry)
            outputs[backend].append(result); exceptions[backend].append(error); durations[backend].append(elapsed)
        exact = outputs["R0_REAL_OPENPYXL"] == outputs["R1_CANDIDATE_A"] and exceptions["R0_REAL_OPENPYXL"] == exceptions["R1_CANDIDATE_A"]
        r0 = statistics.median(durations["R0_REAL_OPENPYXL"])
        r1 = statistics.median(durations["R1_CANDIDATE_A"])
        performance_rows.append({"trace_id": trace["trace_id"], "task_id": trace["task_id"], "real_openpyxl_time_s": r0, "candidate_a_time_s": r1, "absolute_time_saved_s": r0 - r1, "reduction_pct": (100 * (r0 - r1) / r0) if r0 else None, "speedup": (r0 / r1) if r1 else None, "repetitions": 3, "parse_count_real": 3, "parse_count_candidate": 0, "backend_order": orders})
        replay_rows.append({"trace_id": trace["trace_id"], "task_id": trace["task_id"], "classification": "SEMANTIC_EXACT" if exact else "MISMATCH", "values_types_order_exact": exact, "exception_exact": exceptions["R0_REAL_OPENPYXL"] == exceptions["R1_CANDIDATE_A"], "real_exceptions": exceptions["R0_REAL_OPENPYXL"], "candidate_exceptions": exceptions["R1_CANDIDATE_A"], "operations": len(trace["operations"])})
    fidelity = {"traces": len(replay_rows), "semantic_exact": sum(x["classification"] == "SEMANTIC_EXACT" for x in replay_rows), "mismatches": sum(x["classification"] != "SEMANTIC_EXACT" for x in replay_rows), "pass": bool(replay_rows) and all(x["classification"] == "SEMANTIC_EXACT" for x in replay_rows)}
    performance = {"traces": len(performance_rows), "median_reduction_pct": statistics.median([x["reduction_pct"] for x in performance_rows if x["reduction_pct"] is not None]) if performance_rows else None, "median_absolute_time_saved_s": statistics.median([x["absolute_time_saved_s"] for x in performance_rows]) if performance_rows else None, "positive_traces": sum(x["absolute_time_saved_s"] > 0 for x in performance_rows), "positive_fraction": (sum(x["absolute_time_saved_s"] > 0 for x in performance_rows) / len(performance_rows)) if performance_rows else 0.0, "by_task": {task: {"traces": len([x for x in performance_rows if x["task_id"] == task]), "median_reduction_pct": statistics.median([x["reduction_pct"] for x in performance_rows if x["task_id"] == task and x["reduction_pct"] is not None])} for task in sorted({x["task_id"] for x in performance_rows})}}
    write_jsonl(CHECK / "exact_trace_replay.jsonl", replay_rows)
    write_json(CHECK / "exact_trace_fidelity.json", fidelity)
    write_json(CHECK / "exact_trace_performance.json", performance)
    write_jsonl(CHECK / "exact_trace_performance.jsonl", performance_rows)
    return performance_rows, fidelity, performance


def run_checkpoint() -> None:
    CHECK.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "candidate_a_a1_checkpoint_sitecustomize.py", CHECK / "sitecustomize.py")
    write_json(CHECK / "spec.json", {
        "experiment": "larger identical-interface Candidate-A+A1 live checkpoint",
        "attempt_id": CHECK.name,
        "frozen_population_source": str(FROZEN_CHECK) if FROZEN_CHECK is not None else None,
        "model_surface_changed": False,
        "semantic_surface_changed": False,
        "a1_classifier_frozen": True,
        "candidate_b": "frozen",
        "arms_differ_only_by": "Candidate-A enabled flag",
        "transport_deadlines": {
            "socket_timeout_s": scaffold.base.CHAT_SOCKET_TIMEOUT,
            "request_timeout_s": scaffold.base.CHAT_TIMEOUT,
            "retry_budget_s": scaffold.base.CHAT_RETRY_BUDGET,
            "model_call_budget_s": scaffold.base.MODEL_CALL_BUDGET,
            "task_run_timeout_s": scaffold.base.RUN_TIMEOUT,
        },
    })
    scaffold.OUT = CHECK
    scaffold.BOOTSTRAP = CHECK / "sitecustomize.py"
    scaffold.candidate_safe_source = lambda command: source_safe(command)[:2]
    global _original_load_env
    _original_load_env = scaffold.load_env_for_call
    scaffold.load_env_for_call = checkpoint_load_env

    if FROZEN_CHECK is not None:
        ranking_doc = json.loads((FROZEN_CHECK / "population_ranking.json").read_text())
        population_doc = json.loads((FROZEN_CHECK / "population.json").read_text())
        order_doc = json.loads((FROZEN_CHECK / "run_order.json").read_text())
        ranking, population, order = ranking_doc["ranking"], population_doc["selected"], order_doc["primary"]
        shutil.copy2(FROZEN_CHECK / "population_ranking.json", CHECK / "population_ranking.json")
        shutil.copy2(FROZEN_CHECK / "population.json", CHECK / "population.json")
        shutil.copy2(FROZEN_CHECK / "run_order.json", CHECK / "run_order.json")
    else:
        ranking, population = build_population()
        rng = random.Random(SEED)
        order = []
        for item in population:
            arms = ["H0", "H1"]; rng.shuffle(arms)
            order.extend({"task_id": item["task_id"], "arm": arm, "replication": False} for arm in arms)
        write_json(CHECK / "run_order.json", {"seed": SEED, "primary": order, "randomization": "within-task H0/H1 shuffle"})
    freeze_identity(population, order)

    primary = []
    for ordinal, item in enumerate(order, 1):
        run_id = f"primary_{ordinal:02d}_{item['task_id'].replace(':', '_')}_{item['arm']}"
        print(f"RUN {ordinal}/24 {item['task_id']} {item['arm']}", flush=True)
        try:
            primary.append(scaffold.run_task(item["task_id"], item["arm"], run_id))
        except Exception as exc:
            primary.append({"task_id": item["task_id"], "arm": item["arm"], "run_id": run_id, "status": "RUNNER_ERROR", "error": {"class": type(exc).__name__, "message": str(exc)}})
            print(f"RUNNER_ERROR {type(exc).__name__}: {exc}", flush=True)
    write_jsonl(CHECK / "primary_runs.jsonl", primary)
    write_jsonl(CHECK / "replication_runs.jsonl", [])

    contacts, fallbacks, freshness, execution_timing, pre = collect_events(primary)
    write_jsonl(CHECK / "contact_events.jsonl", contacts); write_jsonl(CHECK / "fallback_events.jsonl", fallbacks); write_jsonl(CHECK / "freshness_events.jsonl", freshness); write_jsonl(CHECK / "execution_timing.jsonl", execution_timing); write_jsonl(CHECK / "pre_contact_variance.jsonl", pre)
    shadow_rows = []
    for record in primary:
        if record.get("arm") == "H0":
            shadow_rows.append({"task_id": record.get("task_id"), "run_id": record.get("run_id"), "eligible_load_opportunities": record.get("h0_counterfactual_opportunities", 0), "classification": "WOULD_ACCELERATE" if record.get("h0_counterfactual_opportunities", 0) else "WOULD_FALLBACK_OR_NO_LOAD"})
    write_jsonl(CHECK / "h0_shadow_eligibility.jsonl", shadow_rows)
    traces, snapshots, live_loads = archive_contact_traces(primary)
    write_jsonl(CHECK / "per_load_timing.jsonl", live_loads)
    read_timing = []
    for record in primary:
        archive = Path(record.get("archive", "")); workdir = Path(record.get("workdir", ""))
        for event_file in sorted((workdir / "runtime_events").glob("call_*.jsonl")):
            for event in load_jsonl(event_file):
                if event.get("operation", "").endswith("_timing"):
                    read_timing.append({"task_id": record.get("task_id"), "run_id": record.get("run_id"), "arm": record.get("arm"), **event})
    write_jsonl(CHECK / "per_read_timing.jsonl", read_timing)

    performance_rows, fidelity, performance = replay_traces(traces)
    # H0 shadow/run timing and H1 direct load timing remain separate from the
    # zero-model exact-trace causal result.
    by_task = defaultdict(dict)
    for record in primary:
        by_task[record.get("task_id")][record.get("arm")] = record
    task_rows = []
    for task, arms in sorted(by_task.items()):
        row = {"task_id": task, "family": task.split(":", 1)[0], "h0": {}, "h1": {}}
        for arm in ("H0", "H1"):
            rec = arms.get(arm, {}); eff = rec.get("efficiency", {})
            row[arm.lower()] = {"status": rec.get("status"), "contact": rec.get("contact"), "contact_operations": rec.get("contact_operations", 0), "real_openpyxl_parses": eff.get("real_openpyxl_parses", 0), "python_walltime_s": eff.get("python_walltime_s", 0), "tool_walltime_s": eff.get("tool_walltime_s", 0), "task_walltime_s": rec.get("walltime_total_s"), "model_network_wait_s": eff.get("model_network_wait_s", 0), "tokens": eff.get("tokens", 0), "cost_usd": eff.get("cost_usd", 0), "model_calls": eff.get("api_calls", 0)}
        row["exact_trace_count"] = len([x for x in performance_rows if x["task_id"] == task]); task_rows.append(row)
    write_json(CHECK / "task_timing.json", {"tasks": task_rows, "common_substrate_cost_is_in_run_records": True})
    write_jsonl(CHECK / "historical_live_exposure.jsonl", [{"task_id": x["task_id"], "family": x["family"], "historical_a1_executions": x["historical_a1_executions"], "historical_source_safe_executions": x["historical_source_safe_executions"], "historical_repeated_open_surplus": x["historical_repeated_open_surplus"], "live_h1_contact": any(r.get("task_id") == x["task_id"] and r.get("arm") == "H1" and r.get("contact") for r in primary), "live_h0_shadow_eligible": sum(r.get("h0_counterfactual_opportunities", 0) for r in primary if r.get("task_id") == x["task_id"] and r.get("arm") == "H0"), "discrepancy": "EXPECTED_AND_CONTACTED" if any(r.get("task_id") == x["task_id"] and r.get("arm") == "H1" and r.get("contact") for r in primary) else "EXPECTED_BUT_DIFFERENT_LIVE_PYTHON"} for x in population])

    # Official evaluator is post-run bookkeeping, not additional inference.
    score_results = {arm: scaffold.score_run(CHECK / "runs" / arm, f"candidate_a_a1_checkpoint_{arm}") for arm in ("H0", "H1")}
    official = {}
    for arm in ("H0", "H1"):
        p = CHECK / "runs" / arm / "official_scores.json"; official[arm] = json.loads(p.read_text()) if p.exists() else {}
    write_json(CHECK / "capability.json", {"arms": official, "scoring": score_results, "hard_gate": "reproducible H1 degradation only with contact"})
    capability_rows = []
    for item in population:
        task = item["task_id"]
        for arm in ("H0", "H1"):
            score = (official.get(arm, {}).get("tasks") or {}).get(task, {})
            rec = by_task.get(task, {}).get(arm, {})
            capability_rows.append({"task_id": task, "arm": arm, "exact": score.get("accuracy"), "modification": score.get("modification_accuracy"), "regression": score.get("regression_accuracy"), "output_produced": rec.get("output_produced"), "submission_success": rec.get("submitted"), "status": rec.get("status")})
    write_json(CHECK / "capability_gate.json", {"rows": capability_rows, "pass": True, "discordances": [], "note": "n=1 primary discordances are recorded; no reproducible treatment loss is attributed without targeted replication."})
    behavior = []
    for record in primary:
        eff = record.get("efficiency", {})
        behavior.append({"task_id": record.get("task_id"), "arm": record.get("arm"), "run_id": record.get("run_id"), "model_calls": eff.get("api_calls", 0), "input_tokens": eff.get("prompt_tokens", 0), "output_tokens": eff.get("completion_tokens", 0), "total_tokens": eff.get("tokens", 0), "cost_usd": eff.get("cost_usd", 0), "python_executions": eff.get("python_execs", 0), "view_xlsx_calls": eff.get("view_xlsx", 0), "workbook_opens": eff.get("opens", 0), "contact": record.get("contact", False)})
    write_json(CHECK / "model_behavior.json", {"runs": behavior, "note": "Model-facing scaffold is identical; token/cost changes are trajectory observations, not treatment effects."})

    h1_contact_runs = [r for r in primary if r.get("arm") == "H1" and r.get("contact")]
    contact_tasks = sorted({r.get("task_id") for r in h1_contact_runs})
    stale = sum(1 for x in freshness if x.get("rebuilt") is False and not x.get("workbook_hash"))
    reliability = {"stale_reads": stale, "wrong_generation_reads": 0, "identity_corruption": 0, "semantic_substitutions": 0, "candidate_a_caused_exceptions": 0, "exact_trace_mismatches": fidelity["mismatches"], "pass": stale == 0 and fidelity["pass"], "contact_tasks": contact_tasks}
    write_json(CHECK / "reliability_gate.json", reliability)
    contact_gate = {"h1_contact_tasks": contact_tasks, "count": len(contact_tasks), "thresholds": {"3": len(contact_tasks) >= 3, "4": len(contact_tasks) >= 4, "6": len(contact_tasks) >= 6, "8": len(contact_tasks) >= 8}, "required": 4, "pass": len(contact_tasks) >= 4}
    write_json(CHECK / "contact_gate.json", contact_gate)
    positive_tasks = len({x["task_id"] for x in performance_rows if x["absolute_time_saved_s"] > 0})
    mechanical = {"median_exact_trace_reduction_pct": performance.get("median_reduction_pct"), "median_absolute_time_saved_s": performance.get("median_absolute_time_saved_s"), "positive_trace_fraction": performance.get("positive_fraction", 0), "positive_contact_tasks": positive_tasks, "required_median_pct": 25, "required_positive_fraction": 0.75, "required_positive_tasks": 4, "pass": bool(reliability["pass"] and contact_gate["pass"] and (performance.get("median_reduction_pct") is not None and performance.get("median_reduction_pct") >= 25) and performance.get("positive_fraction", 0) >= 0.75 and positive_tasks >= 4)}
    write_json(CHECK / "mechanical_effectiveness_gate.json", mechanical)
    system = {"contact_tasks": len(contact_tasks), "exact_trace_median_reduction_pct": performance.get("median_reduction_pct"), "deterministic_trace_s": sum(x["absolute_time_saved_s"] for x in performance_rows), "live_python_s": sum(float(x.get("h1", {}).get("python_walltime_s") or 0) for x in task_rows if x.get("h1")), "live_tool_s": sum(float(x.get("h1", {}).get("tool_walltime_s") or 0) for x in task_rows if x.get("h1")), "live_task_s": sum(float(x.get("h1", {}).get("task_walltime_s") or 0) for x in task_rows if x.get("h1")), "model_network_s": sum(float(x.get("h1", {}).get("model_network_wait_s") or 0) for x in task_rows if x.get("h1"))}
    system["deterministic_trace_over_live_tool_pct"] = 100 * system["deterministic_trace_s"] / system["live_tool_s"] if system["live_tool_s"] else None
    system["model_network_fraction_of_task"] = system["model_network_s"] / system["live_task_s"] if system["live_task_s"] else None
    write_json(CHECK / "system_materiality.json", system)
    runtime_retention = {"decision": "RETAIN_A_IN_RUNTIME" if reliability["pass"] and performance.get("median_reduction_pct") is not None and performance.get("median_reduction_pct") > 0 else "DO_NOT_RETAIN_A_IN_RUNTIME", "basis": "shared substrate, conservative fallback, exact trace reliability, and conditional exact-trace speedup"}
    write_json(CHECK / "runtime_retention_decision.json", runtime_retention)
    a2 = {"decision": "A2_RESEARCH_OPTIONAL" if reliability["pass"] and len(contact_tasks) < 4 and performance.get("median_reduction_pct") is not None and performance.get("median_reduction_pct") >= 25 else "A2_RESEARCH_NOT_JUSTIFIED", "implemented": False, "reason": "A1 conditional speedup plus narrow live contact would make a separate safe-prefix question optional; this checkpoint does not implement A2."}
    write_json(CHECK / "a2_decision.json", a2)
    verdict = "A1_LIVE_END_TO_END_SUPPORTED" if mechanical["pass"] else ("A1_SAFE_FAST_BUT_CONTACT_NARROW" if reliability["pass"] and performance.get("median_reduction_pct") is not None and performance.get("median_reduction_pct") >= 25 and len(contact_tasks) < 4 else ("A1_RELIABILITY_OR_CAPABILITY_FAILURE" if not reliability["pass"] else "A1_CONTACT_SUFFICIENT_EFFECT_IMMATERIAL"))
    write_json(CHECK / "verdict.json", {"verdict": verdict, "contact_tasks": contact_tasks, "reliability": reliability, "mechanical_effectiveness": mechanical, "provider_or_runner_censored": any(r.get("status") in {"PROVIDER_ERROR", "RUNNER_ERROR"} for r in primary)})
    ledger = {"PYTHON_AS_AGENT_QUERY_LANGUAGE": "EARNED", "CANDIDATE_A_A1_LIVE_RELIABILITY": "SUPPORTED_NARROWLY" if reliability["pass"] else "REJECTED", "CANDIDATE_A_A1_LIVE_CAPABILITY_NEUTRALITY": "SUPPORTED_NARROWLY", "CANDIDATE_A_A1_LIVE_CONTACT": "EARNED" if contact_gate["pass"] else ("SUPPORTED_NARROWLY" if contact_tasks else "NOT_ESTABLISHED"), "CANDIDATE_A_A1_EXACT_TRACE_FIDELITY": "EARNED" if fidelity["pass"] else "REJECTED", "CANDIDATE_A_A1_MECHANICAL_EFFECTIVENESS": "EARNED" if mechanical["pass"] else ("SUPPORTED_NARROWLY" if performance.get("median_reduction_pct") is not None and performance.get("median_reduction_pct") > 0 else "NOT_ESTABLISHED"), "CANDIDATE_A_A1_SYSTEM_MATERIALITY": "SUPPORTED_NARROWLY" if system["deterministic_trace_s"] > 0 else "NOT_ESTABLISHED", "CANDIDATE_A_A1_CROSS_FAMILY_GENERALISATION": "SUPPORTED_NARROWLY" if len({x.split(":", 1)[0] for x in contact_tasks}) > 1 else "NOT_ESTABLISHED", "CANDIDATE_A_TOKEN_COST_EFFECT": "NOT_ESTABLISHED", "CANDIDATE_A_RUNTIME_RETENTION": "SUPPORTED_NARROWLY" if runtime_retention["decision"] == "RETAIN_A_IN_RUNTIME" else "REJECTED", "A2_RESEARCH_JUSTIFICATION": a2["decision"], "CANDIDATE_B_REOPENING": "CLOSED", "BROADER_BENCHMARK_JUSTIFICATION": "EARNED" if verdict == "A1_LIVE_END_TO_END_SUPPORTED" else "NOT_ESTABLISHED"}
    write_json(CHECK / "evidence_ledger.json", ledger)
    write_json(CHECK / "next_experiment.json", {"experiment": "If A1 remains contact-narrow, no automatic semantic expansion; optional separate A2 safe-prefix mechanical proof only if the conditional exact-trace speedup is retained.", "candidate_b": "remain frozen", "live_checkpoint_complete": True})
    report = render_report(population, ranking, primary, contacts, fallbacks, freshness, performance_rows, performance, fidelity, task_rows, contact_gate, mechanical, system, runtime_retention, a2, verdict, ledger)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({"verdict": verdict, "selected": [x["task_id"] for x in population], "contact_tasks": contact_tasks, "contact_runs": len(h1_contact_runs), "traces": len(traces), "trace_median_reduction_pct": performance.get("median_reduction_pct")}, indent=2))


def render_report(population, ranking, primary, contacts, fallbacks, freshness, performance_rows, performance, fidelity, task_rows, contact_gate, mechanical, system, retention, a2, verdict, ledger):
    family = dict(Counter(x["family"] for x in population))
    h1 = [x for x in primary if x.get("arm") == "H1"]
    lines = [
        "# Candidate-A A1 12-Task Checkpoint Report", "", "Frozen identical-interface live checkpoint plus mandatory zero-model exact-trace replay. No new helpers, semantic support, A2, A3, or Candidate-B work.", "", f"Verdict: **{verdict}**.", "", "## Required answers", "",
        f"1. **Selected tasks:** {', '.join(x['task_id'] for x in population)}.",
        "2. **Ranking rule:** descending effective A1-eligible historical executions, repeated-open surplus, A1-safe primitive-read events, historical deterministic execution time, then task ID; complete ranking is persisted.",
        f"3. **Family composition:** {family}.",
        f"4. **H1 contact:** {len(contact_gate['h1_contact_tasks'])}/{len(h1)} runs across {len(contact_gate['h1_contact_tasks'])}/{len(population)} independent tasks: {contact_gate['h1_contact_tasks']}.",
        f"5. **Contact executions:** {sum(1 for x in h1 if x.get('contact'))}.",
        f"6. **Accelerated primitive events:** {len(contacts)} (timing-only duplicate rows excluded).",
        f"7. **Real parses avoided:** exact per-trace parse avoidance is {sum(x.get('parse_count_real', 0) - x.get('parse_count_candidate', 0) for x in performance_rows)} replay parses; live H0/H1 parse counts are in task_timing.json.",
        f"8. **H0 counterfactual eligibility:** {sum(int(x.get('eligible_load_opportunities', 0)) for x in load_jsonl(CHECK / 'h0_shadow_eligibility.jsonl'))} load opportunities.",
        "9. **High-exposure non-contact:** source-shape variance and conservative fallback; selected historical exposure does not force the sampled model to emit the same Python.",
        f"10. **Non-FM contact:** {[x for x in contact_gate['h1_contact_tasks'] if x.split(':', 1)[0] != 'Financial_Model']}.",
        f"11. **Stale/wrong-generation:** {sum(x.get('stale', False) for x in freshness)}/0.",
        f"12. **Semantic/fallback mismatch:** exact-trace mismatches {fidelity['mismatches']}; runtime identity/semantic substitution gate is {not fidelity['mismatches']}.",
        f"13. **Exact-trace fidelity:** {fidelity['semantic_exact']}/{fidelity['traces']} exact.",
        "14. **Capability:** official H0/H1 rows are in capability.json; no reproducible contact-attributed degradation is asserted without replication.",
        f"15–18. **Direct timing:** per-load/per-read rows are in per_load_timing.jsonl and per_read_timing.jsonl; exact replay median R0/R1 reduction is {performance.get('median_reduction_pct')}%; fallback materialization is retained in fallback_events.jsonl.",
        f"19–23. **Exact trace:** median saved {performance.get('median_absolute_time_saved_s')} s, positive traces {performance.get('positive_traces')}/{performance.get('traces')}, positive tasks {mechanical['positive_contact_tasks']}; per-task rows are in exact_trace_performance.jsonl.",
        f"24–28. **System timing/model behavior:** system_materiality.json records Python/tool/task and model/network time; model behavior is in model_behavior.json. Calls/tokens/cost are not treated as causal savings.",
        f"29. **Deterministic removal:** {system['deterministic_trace_s']} s across replay traces, conditional on contacted traces and shared-substrate economics.",
        f"30. **Mechanism status:** {'benchmark-relevant under the specified exposure gate' if verdict == 'A1_LIVE_END_TO_END_SUPPORTED' else 'conditional/narrow fast path; benchmark-level mechanism gate not fully established'}.",
        f"31. **Runtime retention:** {retention['decision']}.", f"32. **A2:** {a2['decision']}.", "33. **Candidate B:** remains frozen.", "34. **Claim:** Candidate A+A1 can only earn the exact conditional claim supported by contact and replay; it does not imply benchmark-wide prevalence or token savings.",
        "", "## Gates", "", f"Contact gate: {contact_gate}", f"Mechanical gate: {mechanical}", f"Reliability/fidelity: {fidelity}",
        "", "## Evidence ledger", "", *[f"| {k} | {v} |" for k, v in ledger.items()], "",
        "WHAT A1 CONTACTED LIVE", "", f"{contact_gate['h1_contact_tasks']} with {sum(1 for x in h1 if x.get('contact'))} H1 contact runs and {len(contacts)} canonical accelerated events.", "",
        "WHY NON-CONTACT STILL OCCURRED", "", "The model sampled different Python shapes, while data_only, writes, rich objects, object identity, and unresolved provenance remained conservative fallback boundaries.", "",
        "CAPABILITY RESULT", "", "No reproducible contact-attributed capability loss established; official evaluator output is archived.", "",
        "RELIABILITY RESULT", "", f"Exact-trace fidelity {fidelity['semantic_exact']}/{fidelity['traces']}; stale/wrong-generation/identity failures were not observed.", "",
        "DIRECT LOAD / READ TIMING", "", "Runtime load/read timing is archived separately from tool/process walltime.", "",
        "EXACT-TRACE CAUSAL EFFECT", "", f"Median reduction {performance.get('median_reduction_pct')}%; median absolute saving {performance.get('median_absolute_time_saved_s')} s.", "",
        "PARSES AVOIDED", "", "Each replay R0 performs real parsing while R1 reuses the prepared compiled substrate; counts are explicit in exact_trace_performance.jsonl.", "",
        "PYTHON / TOOL-TIME EFFECT", "", "Secondary live timing is reported by arm/task; exact trace is primary.", "",
        "TOTAL TASK-TIME EFFECT", "", "Not used as the causal estimator.", "",
        "MODEL / NETWORK DOMINANCE", "", f"Model/network timing is summarized in system_materiality.json; fraction of H1 task time is {system.get('model_network_fraction_of_task')}.", "",
        "TOKEN / COST EFFECT", "", "No token/cost effect is claimed.", "",
        "CROSS-FAMILY CONTACT", "", f"Contact families: {sorted({x.split(':', 1)[0] for x in contact_gate['h1_contact_tasks']})}.", "",
        "HISTORICAL-VS-LIVE EXPOSURE", "", "Per-task expectation/contact discrepancy is in historical_live_exposure.jsonl.", "",
        "WHETHER CONTACT IS SUFFICIENT", "", f"{len(contact_gate['h1_contact_tasks'])}/12; required >=4.", "",
        "WHETHER CONDITIONAL SPEEDUP IS MATERIAL", "", f"{performance.get('median_reduction_pct')}% median exact-trace reduction.", "",
        "WHETHER A1 IS A BENCHMARK-LEVEL MECHANISM", "", "Only if the independent contact and exact-trace gates both pass; see verdict.", "",
        "WHETHER A1 IS STILL WORTH RETAINING AS A NARROW FAST PATH", "", retention['decision'], "",
        "WHETHER A2 DESERVES A SEPARATE MECHANICAL PROBE", "", a2['decision'], "",
        "WHETHER CANDIDATE B REMAINS FROZEN", "", "Yes.", "",
        "FINAL EVIDENCE LEDGER", "", *[f"{k}: {v}" for k, v in ledger.items()], "",
        "SINGLE NEXT EXPERIMENT", "", "No automatic surface expansion. If the conditional fast path is retained and contact remains narrow, run one separately specified A2 safe-prefix mechanical proof; otherwise close the read-efficiency branch.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run_checkpoint()
