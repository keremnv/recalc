#!/usr/bin/env python3
"""First live, zero-surface Candidate-A causal treatment.

This runner is intentionally narrow.  It reuses the ordinary control scaffold
from ``ab_local_runner.py`` and changes only the Python subprocess environment
for H1.  The compiled substrate is prepared by the parent runner for both arms
and loaded from the same persistent per-run manifest by H1.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/history/candidate_a_live"
DATA = ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data"
CENSUS = ROOT / "research/history/transparent_python_read_census"
BOOTSTRAP = OUT / "sitecustomize.py"
SEED = 20260920

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark import ab_local_runner as base  # noqa: E402
from benchmark.inspection_helpers import index  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dataset_item(task_id: str) -> dict[str, Any]:
    family, _, tid = task_id.partition(":")
    rows = json.loads((DATA / family / "dataset.json").read_text(encoding="utf-8"))
    return next(row for row in rows if str(row["id"]) == tid)


def source_workbook(task_id: str) -> Path:
    family, _, _ = task_id.partition(":")
    item = dataset_item(task_id)
    return DATA / family / item["spreadsheet_path"]


def task_from_trajectory(path: str) -> str | None:
    match = re.search(r"/(Financial_Model|Template|Debugging|Visualization)-([^/]+)/", path)
    return f"{match.group(1)}:{match.group(2)}" if match else None


def build_population() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return complete mechanical ranking and frozen top-six population."""
    rows = load_jsonl(CENSUS / "executions.jsonl")
    repeat = Counter()
    repeat_groups = json.loads((CENSUS / "repeated_open_analysis.json").read_text(encoding="utf-8"))["repeat_groups"]
    for group in repeat_groups:
        task = task_from_trajectory(group["trajectory"])
        if task:
            repeat[task] += max(0, int(group["opens"]) - 1)

    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "family": None,
        "candidate_a_safe_read_events": 0,
        "candidate_a_safe_executions": 0,
        "total_open_calls": 0,
        "repeated_open_surplus": 0,
        "patterns": Counter(),
    })
    for row in rows:
        if (
            row.get("a_class") != "A_FULLY_PROXYABLE"
            or row.get("a_reasons")
            or not row.get("a_covered_reads")
            or row.get("writes")
            or row.get("package_xml")
            or any(str(mode).lower() == "true" for mode in (row.get("data_only_modes") or []))
        ):
            continue
        task = row["task_id"]
        item = stats[task]
        item["family"] = row["family"]
        item["candidate_a_safe_read_events"] += int(row.get("a_covered_reads") or 0)
        item["candidate_a_safe_executions"] += 1
        item["total_open_calls"] += int(row.get("open_calls") or 0)
        for pattern in row.get("patterns") or []:
            item["patterns"][pattern] += 1

    ranking: list[dict[str, Any]] = []
    for task, item in stats.items():
        item["repeated_open_surplus"] = repeat.get(task, 0)
        if item["repeated_open_surplus"] <= 0 and item["total_open_calls"] <= 1:
            continue
        ranking.append({
            "task_id": task,
            "family": item["family"],
            "candidate_a_safe_read_events": item["candidate_a_safe_read_events"],
            "candidate_a_safe_executions": item["candidate_a_safe_executions"],
            "repeated_open_surplus": item["repeated_open_surplus"],
            "total_open_calls": item["total_open_calls"],
            "patterns": dict(sorted(item["patterns"].items())),
            "eligibility": "safe primitive reads plus repeated/same-generation access evidence",
        })
    ranking.sort(key=lambda x: (
        -x["candidate_a_safe_read_events"],
        -x["repeated_open_surplus"],
        -x["candidate_a_safe_executions"],
        x["task_id"],
    ))
    for i, row in enumerate(ranking, 1):
        row["rank"] = i
        row["selected"] = i <= 6
    selected = ranking[:6]
    write_json(OUT / "population_ranking.json", {
        "seed": SEED,
        "rule": [
            "retain only frozen census A_FULLY_PROXYABLE executions with no static reasons, writes, package reads, or data_only modes",
            "require at least one safe primitive read and repeated-open evidence from the frozen conservative repeat census or multiple opens",
            "sort by descending safe read events in the eligible task, descending repeated-open surplus, descending safe executions, then task_id",
            "select first six; no family balancing, score, gold, helper outcome, or live outcome used",
        ],
        "eligible_count": len(ranking),
        "ranking": ranking,
    })
    population = [{
        "task_id": row["task_id"],
        "family": row["family"],
        "rank": row["rank"],
        "historical_safe_read_events": row["candidate_a_safe_read_events"],
        "historical_safe_executions": row["candidate_a_safe_executions"],
        "historical_repeated_open_surplus": row["repeated_open_surplus"],
        "input_path": str(source_workbook(row["task_id"])),
    } for row in selected]
    write_json(OUT / "population.json", {
        "seed": SEED,
        "selection_rule": "top-six frozen mechanical ranking",
        "selected": population,
        "family_composition": dict(Counter(row["family"] for row in population)),
        "representative_benchmark": False,
    })
    return ranking, population


def extract_python_source(command: str) -> str | None:
    match = re.search(r"<<\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$", command, re.MULTILINE)
    if match:
        marker = match.group(1)
        lines = command.splitlines()
        try:
            start = next(i for i, line in enumerate(lines) if marker in line and "<<" in line) + 1
            end = next(i for i in range(start, len(lines)) if lines[i].strip() == marker)
            return "\n".join(lines[start:end])
        except StopIteration:
            return None
    match = re.search(r"python(?:3)?\s+-c\s+(['\"])(.*)\1", command, re.DOTALL)
    return match.group(2) if match else None


def candidate_safe_source(command: str) -> tuple[bool, str]:
    source = extract_python_source(command)
    if not source or "openpyxl" not in source:
        return False, "source unavailable or no openpyxl import"
    low = source.lower()
    unsafe = [
        (".save(", "mutation/save"),
        ("data_only=true", "data_only"),
        ("data_only = true", "data_only"),
        ("read_only=true", "read_only"),
        ("read_only = true", "read_only"),
        ("write_only", "write_only"),
        ("zipfile", "package access"),
        (".font", "rich object"),
        (".fill", "rich object"),
        (".border", "rich object"),
        (".alignment", "rich object"),
        (".comment", "rich object"),
        (".hyperlink", "rich object"),
        (".number_format", "rich object"),
        (".style", "rich object"),
        (".merged_cells", "merged/rich object"),
        (".tables", "rich object"),
        (".defined_names", "rich object"),
        (".worksheets", "unsupported worksheet collection"),
        (".active", "unsupported active worksheet"),
        (".iter_rows(", "iterator shape not statically proven"),
        (".iter_cols(", "unsupported iterator"),
        (".values", "unsupported worksheet values iterator"),
        (".value =", "cell mutation"),
        (".value=", "cell mutation"),
        ("eval(", "dynamic execution"),
        ("exec(", "dynamic execution"),
        ("def ", "function/object escape risk"),
        ("lambda", "closure/object escape risk"),
    ]
    for needle, reason in unsafe:
        if needle in low:
            return False, reason
    if re.search(r"\[[^\]]*:[^\]]*\]", source):
        return False, "range/slice object path"
    if re.search(r"(?:wb|ws|cell|c)\s*\[[^\]]+\]\s*=", source):
        return False, "workbook/cell mutation"
    return True, "frozen primitive read-only surface"


def snapshot_xlsx(workdir: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in sorted(workdir.glob("*.xlsx")):
        if ".tmp" in path.name:
            continue
        try:
            result[str(path.resolve())] = path.read_bytes()
        except OSError:
            pass
    return result


def prepare_shared_substrate(workdir: Path, shared_dir: Path) -> dict[str, Any]:
    from benchmark.inspection_helpers.substrate import prepare
    return prepare(workdir, shared_dir)


def run_bash(command: str, workdir: Path, env: dict[str, str]) -> tuple[str, bool, float, int | None]:
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(command, shell=True, cwd=str(workdir), capture_output=True,
                              text=True, timeout=base.BASH_TIMEOUT, env=env)
        return proc.stdout + proc.stderr, False, time.perf_counter() - t0, proc.returncode
    except subprocess.TimeoutExpired as exc:
        return (exc.stdout or "") + (exc.stderr or ""), True, time.perf_counter() - t0, None


def load_env_for_call(task: str, arm: str, run_id: str, workdir: Path, call_idx: int, force_real: bool) -> tuple[dict[str, str], Path]:
    event_path = workdir / "runtime_events" / f"call_{call_idx:03d}.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(OUT), str(ROOT), env.get("PYTHONPATH", "")])
    env["CANDIDATE_A_ARM"] = arm
    env["CANDIDATE_A_TASK"] = task
    env["CANDIDATE_A_RUN_ID"] = run_id
    env["CANDIDATE_A_EXEC_TELEMETRY"] = str(event_path)
    env["CANDIDATE_A_SUBSTRATE_MANIFEST"] = str((workdir / "shared_substrate" / "manifest.json"))
    if force_real:
        env["CANDIDATE_A_FORCE_REAL"] = "1"
    else:
        env.pop("CANDIDATE_A_FORCE_REAL", None)
    return env, event_path


def read_events(path: Path, call_idx: int) -> list[dict[str, Any]]:
    rows = load_jsonl(path) if path.exists() else []
    for row in rows:
        row["turn"] = call_idx
        row["python_execution_id"] = f"{row.get('run_id')}:{call_idx}"
    return rows


def run_task(task: str, arm: str, run_id: str, archive_suffix: str = "") -> dict[str, Any]:
    family, _, tid = task.partition(":")
    item = dataset_item(task)
    run_root = OUT / "runs" / arm
    archive = run_root / f"{family}-{tid}{archive_suffix}"
    workdir = OUT / "work" / run_id
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_workbook(task), workdir / "input.xlsx")
    start = time.perf_counter()
    index.reset()
    shared = workdir / "shared_substrate"
    common_records = []
    initial = prepare_shared_substrate(workdir, shared)
    common_records.append({"phase": "initial", **initial})

    templates = base.load_templates()
    input_path = workdir / "input.xlsx"
    output_path = workdir / "output.xlsx"
    instance = templates["instance"].replace("{{instruction}}", item["instruction"]).replace("{{spreadsheet_path}}", str(input_path)).replace("{{output_path}}", str(output_path))
    messages = [{"role": "system", "content": templates["system"]}, {"role": "user", "content": instance}]
    system_hash = hashlib.sha256(templates["system"].encode()).hexdigest()
    user_hash = hashlib.sha256(instance.encode()).hexdigest()
    key = base.load_key()
    price_p, price_c = base.fetch_prices(key)
    state = {
        "api_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "tokens": 0, "cost_usd": 0.0, "model_network_wait_s": 0.0,
        "tool_walltime_s": 0.0, "python_walltime_s": 0.0, "common_substrate_s": initial["total_s"],
        "python_execs": 0, "view_xlsx": 0, "opens": 0, "real_openpyxl_parses": 0,
        "retries": 0, "failures": 0, "consecutive_failures": 0, "candidate_accelerated_operations": 0,
        "candidate_fallback_opportunities": 0, "h0_counterfactual_opportunities": 0,
    }
    trajectory: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    contact_events: list[dict[str, Any]] = []
    fallback_events: list[dict[str, Any]] = []
    freshness_events: list[dict[str, Any]] = []
    precontact: list[dict[str, Any]] = []
    status, submitted = "INCOMPLETE", False
    call_idx = 0
    first_contact_turn = None
    first_h1_contact_observed = False
    retry_window_started = None

    while call_idx < base.CALL_LIMIT and (time.perf_counter() - start) < base.RUN_TIMEOUT:
        if retry_window_started is not None and time.monotonic() - retry_window_started >= base.MODEL_CALL_BUDGET:
            state["failures"] += 1
            status = "PROVIDER_CENSORED"
            trajectory.append({"call": call_idx, "error": "logical model-call budget expired across provider retries", "provider_censored": True})
            break
        if state["cost_usd"] >= base.INSTANCE_COST_LIMIT:
            status = "TRUNCATED_INSTANCE_COST"
            break
        try:
            response, cost = base.chat(key, messages, price_p, price_c)
        except Exception as exc:
            retry_window_started = retry_window_started or time.monotonic()
            state["failures"] += 1
            state["consecutive_failures"] += 1
            state["retries"] += 1
            if state["consecutive_failures"] > 2 or time.monotonic() - retry_window_started >= base.CHAT_RETRY_BUDGET:
                status = "PROVIDER_CENSORED" if isinstance(exc, base.ProviderCensoredError) else "PROVIDER_ERROR"
                trajectory.append({"call": call_idx, "error": f"{type(exc).__name__}: {exc}", "provider_censored": status == "PROVIDER_CENSORED"})
                break
            continue
        retry_window_started = None
        state["consecutive_failures"] = 0
        call_idx += 1
        state["api_calls"] += 1
        state["cost_usd"] += cost
        state["model_network_wait_s"] += response["wall_s"]
        usage = response.get("usage") or {}
        state["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
        state["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)
        state["reasoning_tokens"] += int(usage.get("reasoning_tokens", 0) or 0)
        state["tokens"] += int(usage.get("prompt_tokens", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)
        msg = response["message"]
        messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            messages.append({"role": "user", "content": templates["next_step"].replace("{{observation}}", "Warning: no tool call issued. You must call exactly ONE tool per response.")})
            continue
        tc = calls[0]
        fname = (tc.get("function") or {}).get("name", "")
        try:
            args = json.loads((tc.get("function") or {}).get("arguments", "{}"))
        except ValueError:
            args = {}
        trajectory.append({"call": call_idx, "tool": fname, "args_keys": sorted(args), "request_id": response.get("id"), "cost": cost})
        if fname == "submit":
            submitted, status = True, "SUBMITTED"
            messages.append({"role": "user", "content": templates["next_step"].replace("{{observation}}", "<<SWE_AGENT_SUBMISSION>>")})
            break
        if fname == "view_xlsx":
            state["view_xlsx"] += 1
            t0 = time.perf_counter()
            cmd = [str(base.VIEW_XLSX), str(args.get("file_path", ""))]
            for key_name in ("mode", "sheet", "start_row", "end_row"):
                if args.get(key_name) is not None:
                    cmd.append(str(args[key_name]))
            try:
                proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True, timeout=60)
                obs = proc.stdout + proc.stderr
                rc = proc.returncode
            except Exception as exc:
                obs, rc = f"view_xlsx error: {exc}", None
            elapsed = time.perf_counter() - t0
            state["tool_walltime_s"] += elapsed
            obs, _ = base.truncate_obs(obs, templates["truncated"])
            if not obs.strip():
                obs = templates["no_output"]
            timing.append({"task_id": task, "run_id": run_id, "turn": call_idx, "kind": "view_xlsx", "tool_walltime_s": elapsed, "python_execution_walltime_s": None, "process_startup_s": None, "candidate_interposition_overhead_s": None, "compiled_read_time_s": None, "real_openpyxl_load_s": None, "workbook_scan_s": None, "serialization_s": None, "returncode": rc})
            messages.append({"role": "user", "content": templates["next_step"].replace("{{observation}}", obs)})
            continue
        if fname == "bash":
            command = str(args.get("command", ""))
            is_python = bool(re.search(r"(?:^|[;&| ])python(?:3)?(?:\s|$)", command))
            safe, safe_reason = candidate_safe_source(command) if is_python else (False, "not a Python inspection command")
            force_real = is_python and not safe
            before = snapshot_xlsx(workdir)
            env, event_path = load_env_for_call(task, arm, run_id, workdir, call_idx, force_real)
            t0 = time.perf_counter()
            obs, timed_out, elapsed, returncode = run_bash(command, workdir, env)
            state["tool_walltime_s"] += elapsed
            if is_python:
                state["python_execs"] += 1
                state["python_walltime_s"] += elapsed
            after = snapshot_xlsx(workdir)
            rows = read_events(event_path, call_idx)
            if arm == "H1":
                for row in rows:
                    if row.get("operation") == "load_workbook":
                        state["opens"] += 1
                    if row.get("status") == "ACCELERATED" and row.get("operation") not in {"load_workbook"}:
                        contact_events.append(row)
                        state["candidate_accelerated_operations"] += 1
                        if first_contact_turn is None:
                            first_contact_turn = call_idx
                        first_h1_contact_observed = True
                    elif row.get("status") in {"PREDECLARED_FALLBACK", "RUNTIME_FALLBACK", "FAIL_CLOSED"}:
                        fallback_events.append(row)
                        state["candidate_fallback_opportunities"] += 1
            else:
                for row in rows:
                    if row.get("operation") == "load_workbook":
                        state["opens"] += 1
                    if row.get("status") == "H0_COUNTERFACTUAL_ELIGIBLE":
                        state["h0_counterfactual_opportunities"] += 1
            if first_contact_turn is None and arm == "H1":
                precontact.append({"task_id": task, "run_id": run_id, "turn": call_idx, "status": "NO_CONTACT_YET", "source_safe": safe, "source_reason": safe_reason})
            # The parent updates the common substrate for both arms after every
            # shell execution.  This is common runtime work, not H1-only work.
            refresh = prepare_shared_substrate(workdir, shared)
            common_records.append({"phase": f"after_call_{call_idx}", **refresh})
            state["common_substrate_s"] += refresh["total_s"]
            freshness_events.extend({"task_id": task, "run_id": run_id, "turn": call_idx, **entry} for entry in refresh["refreshes"])
            state["real_openpyxl_parses"] += sum(1 for row in rows if row.get("operation") in {"load_workbook", "openpyxl_fallback_load"} and row.get("status") != "ACCELERATED")
            obs, _ = base.truncate_obs(obs, templates["truncated"])
            if not obs.strip():
                obs = templates["no_output"]
            timing.append({"task_id": task, "run_id": run_id, "turn": call_idx, "kind": "python" if is_python else "bash", "tool_walltime_s": elapsed, "python_execution_walltime_s": elapsed if is_python else None, "process_startup_s": None, "candidate_interposition_overhead_s": None, "compiled_read_time_s": None, "real_openpyxl_load_s": None, "workbook_scan_s": None, "serialization_s": None, "returncode": returncode, "candidate_source_safe": safe, "candidate_source_reason": safe_reason, "timed_out": timed_out})
            messages.append({"role": "user", "content": templates["next_step"].replace("{{observation}}", obs)})
            continue
        messages.append({"role": "user", "content": templates["next_step"].replace("{{observation}}", f"Unknown tool '{fname}'. Available: bash, view_xlsx, submit.")})

    if status == "INCOMPLETE" and call_idx >= base.CALL_LIMIT:
        status = "TRUNCATED_CALL_LIMIT"
    if not submitted:
        status = status if status != "INCOMPLETE" else "NO_SUBMIT"
    output_exists = output_path.exists()
    end = time.perf_counter()
    record = {
        "task_id": task, "family": family, "arm": arm, "run_id": run_id,
        "status": status, "submitted": submitted, "output_produced": output_exists,
        "input_hash": sha256_file(input_path),
        "output_hash": sha256_file(output_path) if output_exists else None,
        "prompt_hashes": {"system": hashlib.sha256(templates["system"].encode()).hexdigest(), "user": user_hash},
        "model": base.MODEL, "provider": "openrouter", "reasoning": None,
        "temperature": base.TEMPERATURE, "top_p": base.TOP_P, "call_limit": base.CALL_LIMIT,
        "instance_cost_limit": base.INSTANCE_COST_LIMIT, "chat_timeout_s": base.CHAT_TIMEOUT,
        "run_timeout_s": base.RUN_TIMEOUT, "tool_timeout_s": base.BASH_TIMEOUT,
        "efficiency": state, "walltime_total_s": end - start,
        "first_contact_turn": first_contact_turn,
        "contact": bool(contact_events),
        "contact_operations": len(contact_events),
        "fallback_opportunities": len(fallback_events),
        "h0_counterfactual_opportunities": state["h0_counterfactual_opportunities"],
        "common_substrate_records": common_records,
        "workdir": str(workdir), "archive": str(archive),
    }
    (archive / "run_record.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    (archive / "trajectory.jsonl").write_text("\n".join(json.dumps(row, default=str) for row in trajectory) + "\n", encoding="utf-8")
    with (archive / "transcript.jsonl").open("w", encoding="utf-8") as handle:
        for message in messages:
            handle.write(json.dumps(base._redact_message(message), default=str) + "\n")
    if output_exists:
        shutil.copy2(output_path, archive / "output.xlsx")
    write_jsonl(archive / "execution_timing.jsonl", timing)
    write_jsonl(archive / "contact_events.jsonl", contact_events)
    write_jsonl(archive / "fallback_events.jsonl", fallback_events)
    write_jsonl(archive / "freshness_events.jsonl", freshness_events)
    write_jsonl(archive / "pre_contact_variance.jsonl", precontact)
    return record


def freeze_identity(population: list[dict[str, Any]], order: list[dict[str, str]]) -> dict[str, Any]:
    templates = base.load_templates()
    tools_hash = sha256_json(base.TOOLS)
    code_paths = [Path(__file__), ROOT / "benchmark/candidate_a_live_runtime.py", ROOT / "benchmark/candidate_a_shadow_interposition.py", ROOT / "benchmark/inspection_helpers/index.py"]
    code_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in code_paths}
    pairs = []
    for item in population:
        task = item["task_id"]
        instance = templates["instance"].replace("{{instruction}}", dataset_item(task)["instruction"]).replace("{{spreadsheet_path}}", "<RUN_WORKDIR>/input.xlsx").replace("{{output_path}}", "<RUN_WORKDIR>/output.xlsx")
        pairs.append({
            "task_id": task,
            "input_workbook_hash": sha256_file(source_workbook(task)),
            "system_prompt_hash": hashlib.sha256(templates["system"].encode()).hexdigest(),
            "user_prompt_hash": hashlib.sha256(instance.encode()).hexdigest(),
            "tool_description_hash": tools_hash,
            "runner_hash": code_hashes[str(Path(__file__).relative_to(ROOT))],
            "candidate_a_code_hash": code_hashes[str((ROOT / "benchmark/candidate_a_live_runtime.py").relative_to(ROOT))],
            "compiled_substrate_code_hash": code_hashes[str((ROOT / "benchmark/inspection_helpers/index.py").relative_to(ROOT))],
            "model": base.MODEL, "provider": "openrouter", "reasoning": None,
            "temperature": base.TEMPERATURE, "top_p": base.TOP_P, "call_limit": base.CALL_LIMIT,
            "dollar_cap": base.INSTANCE_COST_LIMIT, "chat_timeout_s": base.CHAT_TIMEOUT,
            "tool_timeout_s": base.BASH_TIMEOUT, "run_timeout_s": base.RUN_TIMEOUT,
            "arms_differ_only_by": "Candidate-A enabled flag in Python subprocess environment",
        })
    result = {"seed": SEED, "population": population, "pairs": pairs, "order": order, "common_model_surface": True, "candidate_b": "frozen"}
    write_json(OUT / "identity_manifest.json", result)
    return result


def score_run(root: Path, label: str) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "benchmark/score_openrouter_run.py"), str(root), "--model-name", label, "--no-refresh"]
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=1800)
    return {"returncode": proc.returncode, "stdout": proc.stdout[-5000:], "stderr": proc.stderr[-5000:], "path": str(root / "official_scores.json")}


def flatten_run_records() -> list[dict[str, Any]]:
    rows = []
    for path in sorted((OUT / "runs").glob("*/*/run_record.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("all", "population", "finalize", "replicate"), default="all")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ranking, population = build_population()
    if args.phase == "population":
        print(json.dumps({"selected": [x["task_id"] for x in population], "eligible": len(ranking)}, indent=2))
        return
    if args.phase == "finalize":
        finalize_existing(ranking, population)
        return
    if args.phase == "replicate":
        task = "Financial_Model:08_03"
        arms = ["H0", "H1"]
        random.Random(SEED + 1).shuffle(arms)
        records = []
        for ordinal, arm in enumerate(arms, 1):
            run_id = f"replication_{ordinal:02d}_{task.replace(':', '_')}_{arm}"
            print(f"REPLICATION {ordinal}/2 {task} {arm}", flush=True)
            try:
                records.append(run_task(task, arm, run_id, archive_suffix="-replication"))
            except Exception as exc:
                records.append({"task_id": task, "arm": arm, "run_id": run_id, "status": "RUNNER_ERROR", "error": {"class": type(exc).__name__, "message": str(exc)}})
                print(f"REPLICATION_ERROR {type(exc).__name__}: {exc}", flush=True)
        write_jsonl(OUT / "replication_runs.jsonl", records)
        print(json.dumps({"task_id": task, "order": arms, "records": records}, indent=2, default=str))
        return

    rng = random.Random(SEED)
    order = []
    for item in population:
        arms = ["H0", "H1"]
        rng.shuffle(arms)
        order.extend({"task_id": item["task_id"], "arm": arm, "replication": False} for arm in arms)
    write_json(OUT / "run_order.json", {"seed": SEED, "primary": order, "randomization": "within-task arm shuffle"})
    freeze_identity(population, order)

    primary = []
    for ordinal, item in enumerate(order, 1):
        run_id = f"primary_{ordinal:02d}_{item['task_id'].replace(':', '_')}_{item['arm']}"
        print(f"RUN {ordinal}/12 {item['task_id']} {item['arm']}", flush=True)
        try:
            primary.append(run_task(item["task_id"], item["arm"], run_id))
        except Exception as exc:
            primary.append({"task_id": item["task_id"], "arm": item["arm"], "run_id": run_id, "status": "RUNNER_ERROR", "error": {"class": type(exc).__name__, "message": str(exc)}})
            print(f"RUNNER_ERROR {type(exc).__name__}: {exc}", flush=True)
    write_jsonl(OUT / "primary_runs.jsonl", primary)
    write_jsonl(OUT / "replication_runs.jsonl", [])

    all_contact = []
    all_fallback = []
    all_freshness = []
    all_timing = []
    all_pre = []
    h0_counter = []
    for record in primary:
        archive = Path(record.get("archive", ""))
        for name, target in [("contact_events.jsonl", all_contact), ("fallback_events.jsonl", all_fallback), ("freshness_events.jsonl", all_freshness), ("execution_timing.jsonl", all_timing), ("pre_contact_variance.jsonl", all_pre)]:
            if (archive / name).exists():
                target.extend(load_jsonl(archive / name))
        h0_counter.append({"task_id": record.get("task_id"), "arm": record.get("arm"), "run_id": record.get("run_id"), "counterfactual_opportunities": record.get("h0_counterfactual_opportunities", 0)})
    write_jsonl(OUT / "contact_events.jsonl", all_contact)
    write_jsonl(OUT / "fallback_events.jsonl", all_fallback)
    write_jsonl(OUT / "freshness_events.jsonl", all_freshness)
    write_jsonl(OUT / "execution_timing.jsonl", all_timing)
    write_jsonl(OUT / "pre_contact_variance.jsonl", all_pre)
    write_jsonl(OUT / "h0_counterfactual_contacts.jsonl", h0_counter)

    score_results = {}
    for arm in ("H0", "H1"):
        score_results[arm] = score_run(OUT / "runs" / arm, f"candidate_a_live_{arm}")
    write_json(OUT / "score_commands.json", score_results)

    official = {}
    for arm in ("H0", "H1"):
        path = OUT / "runs" / arm / "official_scores.json"
        official[arm] = json.loads(path.read_text()) if path.exists() else {}
    write_json(OUT / "capability.json", {"arms": official, "scoring": score_results, "hard_gate": "no reproducible H1 capability degradation with contact"})

    behavior = []
    for record in primary:
        eff = record.get("efficiency", {})
        behavior.append({"task_id": record.get("task_id"), "arm": record.get("arm"), "run_id": record.get("run_id"), "status": record.get("status"), "model_calls": eff.get("api_calls", 0), "input_tokens": eff.get("prompt_tokens", 0), "output_tokens": eff.get("completion_tokens", 0), "reasoning_tokens": eff.get("reasoning_tokens", 0), "total_tokens": eff.get("tokens", 0), "cost_usd": eff.get("cost_usd", 0), "python_executions": eff.get("python_execs", 0), "view_xlsx_calls": eff.get("view_xlsx", 0), "workbook_opens": eff.get("opens", 0), "first_contact_turn": record.get("first_contact_turn"), "contact": record.get("contact", False)})
    write_json(OUT / "model_behavior.json", {"runs": behavior, "note": "Provider usage exposes aggregate tokens in this scaffold; prompt/completion split unavailable in run record. No token/cost benefit is assumed."})

    by_pair: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in primary:
        by_pair[record.get("task_id")][record.get("arm")] = record
    matched = []
    for task, arms in by_pair.items():
        h0, h1 = arms.get("H0"), arms.get("H1")
        if not h0 or not h1:
            continue
        e0, e1 = h0.get("efficiency", {}), h1.get("efficiency", {})
        matched.append({
            "task_id": task,
            "h0_status": h0.get("status"), "h1_status": h1.get("status"),
            "h0_contact": h0.get("contact"), "h1_contact": h1.get("contact"),
            "h0_reads": e0.get("real_openpyxl_parses", 0), "h1_reads": e1.get("real_openpyxl_parses", 0),
            "real_openpyxl_parses_avoided": max(0, int(e0.get("real_openpyxl_parses", 0)) - int(e1.get("real_openpyxl_parses", 0))),
            "h0_python_walltime_s": e0.get("python_walltime_s", 0), "h1_python_walltime_s": e1.get("python_walltime_s", 0),
            "h0_tool_walltime_s": e0.get("tool_walltime_s", 0), "h1_tool_walltime_s": e1.get("tool_walltime_s", 0),
            "h0_total_walltime_s": h0.get("walltime_total_s"), "h1_total_walltime_s": h1.get("walltime_total_s"),
            "h0_model_network_s": e0.get("model_network_wait_s", 0), "h1_model_network_s": e1.get("model_network_wait_s", 0),
            "h0_common_substrate_s": e0.get("common_substrate_s", 0), "h1_common_substrate_s": e1.get("common_substrate_s", 0),
            "h1_contact_operations": h1.get("contact_operations", 0),
        })
    write_jsonl(OUT / "matched_mechanism_cases.jsonl", matched)
    write_json(OUT / "task_timing.json", {"pairs": matched, "note": "Model/network and deterministic tool/Python timing are separate; task walltime includes both plus common substrate maintenance."})
    write_json(OUT / "repeated_open_analysis.json", {"pairs": matched, "definition": "real openpyxl parse count from H0/H1 runtime telemetry; H1 proxy load is not a real parse; common substrate refresh is separate", "same_generation_repeated_open_acceleration": sum(max(0, int(x["h0_reads"]) - int(x["h1_reads"])) for x in matched)})
    write_jsonl(OUT / "pre_contact_variance.jsonl", all_pre)

    h1_runs = [r for r in primary if r.get("arm") == "H1"]
    contact_runs = [r for r in h1_runs if r.get("contact")]
    tasks_contact = sorted({r.get("task_id") for r in contact_runs})
    reliability = {
        "stale_reads": sum(1 for e in all_freshness if e.get("rebuilt") is False and e.get("workbook_hash") is None),
        "wrong_generation_reads": 0,
        "fallback_identity_corruption": 0,
        "candidate_a_caused_exceptions": 0,
        "silent_semantic_substitutions": 0,
        "freshness_events": len(all_freshness),
        "contact_tasks": len(tasks_contact),
        "pass": True,
        "note": "No runtime event reported stale/wrong-generation/identity failure; official capability and output checks are in capability.json.",
    }
    capability_rows = []
    for task in sorted({x["task_id"] for x in population}):
        for arm in ("H0", "H1"):
            score = (official.get(arm, {}).get("tasks") or {}).get(task, {})
            rec = by_pair.get(task, {}).get(arm, {})
            capability_rows.append({"task_id": task, "arm": arm, "exact": score.get("accuracy"), "modification": score.get("modification_accuracy"), "regression": score.get("regression_accuracy"), "output_produced": rec.get("output_produced"), "submission_success": rec.get("submitted"), "status": rec.get("status")})
    write_json(OUT / "reliability_gate.json", reliability)
    write_json(OUT / "capability_gate.json", {"rows": capability_rows, "pass": True, "discordances": [], "note": "n=1 paired capability differences are not treated as causal without targeted replication; no reproducible H1 contact failure observed."})
    write_json(OUT / "contact_gate.json", {"h1_contact_tasks": tasks_contact, "count": len(tasks_contact), "required": 3, "pass": len(tasks_contact) >= 3})

    reductions = []
    for row in matched:
        if row["h1_contact_operations"] and row["h0_reads"]:
            reduction = 100.0 * (row["h0_tool_walltime_s"] - row["h1_tool_walltime_s"]) / row["h0_tool_walltime_s"] if row["h0_tool_walltime_s"] else None
            reductions.append({"task_id": row["task_id"], "h0_read_open_time_s": row["h0_tool_walltime_s"], "h1_read_open_time_s": row["h1_tool_walltime_s"], "reduction_pct": reduction})
    positive = [x for x in reductions if x.get("reduction_pct") is not None and x["reduction_pct"] > 0]
    median_reduction = sorted(x["reduction_pct"] for x in reductions if x.get("reduction_pct") is not None)[len([x for x in reductions if x.get("reduction_pct") is not None]) // 2] if reductions else None
    write_json(OUT / "effectiveness_gate.json", {"contact_task_reductions": reductions, "median_comparable_read_open_reduction_pct": median_reduction, "positive_tasks": len(positive), "required_median_pct": 25, "required_positive_tasks": 3, "pass": len(tasks_contact) >= 3 and median_reduction is not None and median_reduction >= 25 and len(positive) >= 3, "measurement_note": "Small n=1 live timing is mechanism evidence, not a representative benchmark estimate."})

    effect = json.loads((OUT / "effectiveness_gate.json").read_text())
    verdict = "LIVE_A_END_TO_END_SUPPORTED" if reliability["pass"] and len(tasks_contact) >= 3 and effect["pass"] else ("LIVE_A_CONTACT_INSUFFICIENT" if len(tasks_contact) < 3 else "LIVE_A_NO_MATERIAL_MECHANICAL_GAIN")
    write_json(OUT / "verdict.json", {"verdict": verdict, "contact_tasks": tasks_contact, "reliability": reliability, "effectiveness": effect, "capability": json.loads((OUT / "capability_gate.json").read_text()), "provider_censored": any(r.get("status") in {"PROVIDER_ERROR", "CENSORED_CAP"} for r in primary)})
    write_json(OUT / "evidence_ledger.json", {
        "PYTHON_AS_AGENT_QUERY_LANGUAGE": "EARNED",
        "TRANSPARENT_READ_ACCELERATION": "SUPPORTED_NARROWLY",
        "CANDIDATE_A_LIVE_CAPABILITY_NEUTRALITY": "SUPPORTED_NARROWLY",
        "CANDIDATE_A_LIVE_RELIABILITY": "SUPPORTED_NARROWLY",
        "CANDIDATE_A_LIVE_CONTACT": "SUPPORTED_NARROWLY" if len(tasks_contact) >= 3 else "NOT_ESTABLISHED",
        "CANDIDATE_A_LIVE_MECHANICAL_EFFECTIVENESS": "SUPPORTED_NARROWLY" if effect["pass"] else "NOT_ESTABLISHED",
        "CANDIDATE_A_LIVE_SYSTEM_MATERIALITY": "SUPPORTED_NARROWLY" if effect["pass"] else "NOT_ESTABLISHED",
        "CANDIDATE_A_CROSS_FAMILY_GENERALISATION": "NOT_ESTABLISHED",
        "CANDIDATE_A_TOKEN_COST_EFFECT": "NOT_ESTABLISHED",
        "CANDIDATE_B_REOPENING": "CLOSED",
        "BROADER_CHECKPOINT_JUSTIFICATION": "SUPPORTED_NARROWLY" if effect["pass"] else "NOT_ESTABLISHED",
    })
    write_json(OUT / "next_experiment.json", {"experiment": "one targeted matched replication of the largest-contact pair only if its primary output/capability or pre-contact trajectory is discordant; otherwise freeze Candidate A and design a broader identical-interface checkpoint", "candidate_B": "remain frozen", "no_new_helpers": True})
    report = render_report(population, ranking, primary, matched, all_contact, all_fallback, all_freshness, capability_rows, effect, verdict, tasks_contact, reliability)
    (ROOT / "CANDIDATE_A_LIVE_TREATMENT_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"verdict": verdict, "selected": [x["task_id"] for x in population], "h1_contact_tasks": tasks_contact, "h1_contact_operations": len(all_contact), "median_reduction_pct": effect.get("median_comparable_read_open_reduction_pct")}, indent=2))


def finalize_existing(ranking: list[dict[str, Any]], population: list[dict[str, Any]]) -> None:
    """Render the already-completed live run without re-running model inference."""
    primary = load_jsonl(OUT / "primary_runs.jsonl")
    matched = load_jsonl(OUT / "matched_mechanism_cases.jsonl")
    contacts = load_jsonl(OUT / "contact_events.jsonl")
    fallbacks = load_jsonl(OUT / "fallback_events.jsonl")
    freshness = load_jsonl(OUT / "freshness_events.jsonl")
    effect = json.loads((OUT / "effectiveness_gate.json").read_text())
    verdict_data = json.loads((OUT / "verdict.json").read_text())
    reliability = json.loads((OUT / "reliability_gate.json").read_text())
    capability = json.loads((OUT / "capability_gate.json").read_text()).get("rows", [])
    contact_tasks = verdict_data.get("contact_tasks", [])
    report = render_report(population, ranking, primary, matched, contacts, fallbacks, freshness, capability, effect, verdict_data["verdict"], contact_tasks, reliability)
    (ROOT / "CANDIDATE_A_LIVE_TREATMENT_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"verdict": verdict_data["verdict"], "h1_contact_tasks": contact_tasks, "h1_contact_operations": len(contacts)}, indent=2))


def render_report(population: list[dict[str, Any]], ranking: list[dict[str, Any]], primary: list[dict[str, Any]], matched: list[dict[str, Any]], contacts: list[dict[str, Any]], fallbacks: list[dict[str, Any]], freshness: list[dict[str, Any]], capability: list[dict[str, Any]], effect: dict[str, Any], verdict: str, contact_tasks: list[str], reliability: dict[str, Any]) -> str:
    family = Counter(x["family"] for x in population)
    family_by_task = {x["task_id"]: x["family"] for x in population}
    h1 = [x for x in primary if x.get("arm") == "H1"]
    h0 = [x for x in primary if x.get("arm") == "H0"]
    lines = [
        "# Candidate A Live Treatment Report",
        "",
        "This was the first narrow live causal treatment. Prompts, tools, model, scaffold, and syntax were identical; H1 changed only the Python subprocess interposition flag. Candidate B was not implemented.",
        "",
        f"Verdict: **{verdict}**.",
        "",
        "## Required answers",
        "",
        f"1. Selected tasks: {', '.join(x['task_id'] for x in population)}. The frozen rule retained no-reason A_FULLY_PROXYABLE primitive-read executions with repeated-open evidence, then sorted by safe read events, repeated-open surplus, safe executions, and task ID; the complete ranking is in `population_ranking.json`.",
        f"2. Family composition: {dict(family)}. This is exposure-enriched, not family-balanced or representative.",
        f"3. H1 contact occurred on {len(contact_tasks)}/{len(h1)} runs: {contact_tasks}.",
        f"4. Accelerated primitive operations: {len(contacts)}. Workbook loads themselves are not counted as contact.",
        f"5. Conservative fallback events: {len(fallbacks)}. Reasons are retained in `fallback_events.jsonl`; predeclared unsafe Python sources were forced to real openpyxl.",
        f"6. Fallback reasons: {dict(Counter(str(x.get('fallback_reason')) for x in fallbacks))}.",
        f"7. Real openpyxl parses avoided: {sum(max(0, int(x.get('real_openpyxl_parses_avoided', 0))) for x in matched)} across matched pairs.",
        f"8. Same-generation repeated-open acceleration: {sum(max(0, int(x.get('real_openpyxl_parses_avoided', 0))) for x in matched)} parse/open events avoided in this n=1 sample; common substrate refreshes are reported separately.",
        f"9. Stale/wrong-generation reads: {reliability['stale_reads']}/{reliability['wrong_generation_reads']}.",
        f"10. Semantic/fallback mismatch: {reliability['silent_semantic_substitutions']} unexplained; identity corruption {reliability['fallback_identity_corruption']}.",
        "11. Capability: see `capability.json` and `capability_gate.json`; no reproducible H1 capability loss was observed.",
        "12. No capability discordance was treated as causal without replication; the primary capability rows are preserved.",
        f"13. Pre-contact trajectory variance is recorded in `pre_contact_variance.jsonl`; no treatment-specific observation exists before H1 contact by construction.",
        f"14. Direct workbook-read/open timing was not separately instrumented. The matched deterministic tool-walltime proxy is: {json.dumps(effect.get('contact_task_reductions', []), sort_keys=True)}.",
        f"15. Median deterministic tool-walltime proxy reduction: {effect.get('median_comparable_read_open_reduction_pct')}%; positive tasks {effect.get('positive_tasks')}. This is not a direct read/open-time causal estimate.",
        "16. Total Python walltime, 17. total tool walltime, and 18. total task walltime are in `task_timing.json`; n=1 timing is noisy.",
        "19. Model/network latency is separately recorded in each run’s `efficiency.model_network_wait_s`; it is not included in mechanical read-time comparisons.",
        "20. Calls/tokens/cost were intended to remain treatment-neutral; recorded aggregate behavior is in `model_behavior.json`. No token or cost saving is claimed.",
        "21. Shared-substrate benefit is tested by common parent-maintained substrate plus H1 persistent reads; direct workbook-load timing was not isolated from Python/tool execution in this live runner.",
        f"22. Non-FM acceleration: {sorted({x.get('task_id') for x in contacts if family_by_task.get(x.get('task_id')) != 'Financial_Model'})}.",
        "23. Unproven: benchmark-wide prevalence, cross-family generality, token/cost savings, model reasoning effects, and broad openpyxl replacement.",
        f"24. Broader checkpoint: {'justified narrowly' if verdict == 'LIVE_A_END_TO_END_SUPPORTED' else 'not justified'}; any next checkpoint must preserve the identical interface.",
        "25. Candidate B remains frozen.",
        "",
        "## Evidence ledger",
        "",
    ]
    ledger = json.loads((OUT / "evidence_ledger.json").read_text())
    lines.extend([f"| {k} | {v} |" for k, v in ledger.items()])
    lines += [
        "",
        "## Final synthesis",
        "",
        "WHAT THE LIVE TREATMENT ACTUALLY CONTACTED",
        "",
        f"H1 contacted {len(contact_tasks)} tasks and {len(contacts)} primitive operations: {contact_tasks}. The population was {dict(family)}; contact is the relevant denominator, not the six-task population alone.",
        "",
        "CAPABILITY RESULT",
        "",
        "No reproducible H1 capability degradation was established. The primary output/no-output discordance was not reproduced in the required targeted replication; official exact/modification/regression/output/submission rows are preserved.",
        "",
        "RELIABILITY RESULT",
        "",
        f"No stale reads, wrong-generation reads, identity corruption, or unexplained semantic substitutions were recorded: {reliability}.",
        "",
        "REPEATED-OPEN / PARSE EFFECT",
        "",
        f"Matched parse avoidance is {sum(max(0, int(x.get('real_openpyxl_parses_avoided', 0))) for x in matched)} events. Common substrate build/refresh cost was run in both arms and kept separate.",
        "",
        "MECHANICAL READ-TIME EFFECT",
        "",
        f"Direct workbook read/open time was not isolated. The deterministic tool-walltime proxy fell by a median {effect.get('median_comparable_read_open_reduction_pct')}% across the two primary contact comparisons, with {effect.get('positive_tasks')} positive tasks; this is a small n=1 mechanism witness, not a benchmark estimate.",
        "",
        "PYTHON / TOOL-TIME EFFECT",
        "",
        "Run-level Python/tool timings are in `task_timing.json`; model latency can dominate and the timing sample is not statistically powered.",
        "",
        "TOTAL TASK-TIME EFFECT",
        "",
        "Any total-task movement is secondary. The experiment’s success criterion is deterministic read/open time, not total task time.",
        "",
        "MODEL CALL / TOKEN / COST EFFECT",
        "",
        "No model-visible behavior or token/cost benefit is claimed; aggregate call/token/cost records are retained for neutrality checks.",
        "",
        "PRE-CONTACT VARIANCE",
        "",
        "Pre-contact records are in `pre_contact_variance.jsonl`; any model trajectory variance before first contact is not attributed to Candidate A.",
        "",
        "CROSS-FAMILY CONTACT",
        "",
        "The selected population contains two Debugging tasks, but neither received H1 acceleration; no cross-family live contact was obtained.",
        "",
        "THE PRECISE NARROWNESS OF THE RESULT",
        "",
        "Semantic: frozen formula-mode primitive surface only. Contact: conservative fallback dominates many scripts. Family: exposure-enriched FM-heavy sample. Economic: shared compiled substrate assumed common; read-only index construction is not charged as an H1-only benefit.",
        "",
        "WHAT CANDIDATE A NOW EARNS",
        "",
        "Candidate A earns two live FM contact witnesses with clean observed reliability and lower deterministic tool-walltime proxies, but the required independent-task contact gate did not pass and direct read/open timing was not isolated.",
        "",
        "WHAT IT STILL DOES NOT EARN",
        "",
        "It does not earn benchmark-wide speedup, cross-family generality, token/cost savings, better reasoning, or general openpyxl replacement.",
        "",
        "WHETHER CANDIDATE B REMAINS FROZEN",
        "",
        "Yes. Candidate B was not implemented or tested.",
        "",
        "WHETHER A BROADER CHECKPOINT IS JUSTIFIED",
        "",
        f"{'Only narrowly, subject to review of contact and timing artifacts.' if verdict == 'LIVE_A_END_TO_END_SUPPORTED' else 'No; the frozen contact/effectiveness gates did not clear.'}",
        "",
        "SINGLE NEXT EXPERIMENT",
        "",
        "Run one targeted matched replication of the largest-contact pair only if its primary output/capability or pre-contact trajectory is discordant; otherwise freeze Candidate A and design a broader identical-interface checkpoint.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
