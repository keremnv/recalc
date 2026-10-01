#!/usr/bin/env python3
"""C0 vs C1 default-harness deterministic formula execution experiment.

C0 is the ordinary SpreadsheetBench coding-agent scaffold. C1 adds one optional
primitive, calc_translate_fill. The model remains sovereign over intent; the
harness only executes a mechanically witnessed translation of a model-declared
formula onto a model-declared target set.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "src")]

from experiment_config import AUTHORITATIVE_EXPERIMENT_CONFIG  # noqa: E402
from run_openrouter_slice import _load_dotenv  # noqa: E402
from xlsx_metadata_repair import install as install_metadata_repair  # noqa: E402
import calc_translate_fill as fill  # noqa: E402
import program_group as pg  # noqa: E402

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
RUNS = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
RUNNER = ROOT / "benchmark/run_openrouter_slice.py"
SCORER = ROOT / "benchmark/score_openrouter_run.py"
CONTROL = ROOT / "benchmark/sweagent/spreadsheet-control.yaml"
TREATMENT = ROOT / "benchmark/sweagent/spreadsheet-control-translate-fill.yaml"
TOOL_SCHEMA = ROOT / "benchmark/sweagent/calc_translate_fill/config.yaml"
EXECUTOR = ROOT / "benchmark/calc_translate_fill.py"
SLICE = ROOT / "benchmark/slices/default-harness-deterministic-execution.json"
ARTIFACT = ROOT / "default_harness_deterministic_execution"
REPORT = ROOT / "DEFAULT_HARNESS_DETERMINISTIC_EXECUTION_REPORT.md"

GLM = AUTHORITATIVE_EXPERIMENT_CONFIG
MODEL = GLM.model
CALL_LIMIT = 60
COST_LIMIT = 5.0
TIMEOUT = 7200
EXECUTION_TIMEOUT = 180
WORKERS = 3
CATEGORIES = ("Financial_Model", "Template", "Debugging", "Visualization")
PROGRAMGROUP_DEVELOPMENT = {
    ("Financial_Model", "08_03"),
    ("Financial_Model", "08_04"),
    ("Financial_Model", "08_05"),
    ("Financial_Model", "09_05"),
    ("Financial_Model", "15_04"),
    ("Financial_Model", "17_03"),
    ("Financial_Model", "07_03"),
    ("Financial_Model", "14_05"),
}
LEGACY_WITNESSES = [
    {
        "category": "Financial_Model",
        "id": "08_03",
        "role": "positive_witness",
        "archived_region": "Working Capital!J44:N44",
        "reason": "Archived homogeneous J44:N44 group; independent synthesis was inconsistent; deterministic translation of one canonical formula filled all five members.",
    },
    {
        "category": "Financial_Model",
        "id": "08_04",
        "role": "wrong_canonical_negative_control",
        "reason": "Translation previously preserved mechanics while propagating a semantically wrong program. Executor must not repair that.",
    },
    {
        "category": "Financial_Model",
        "id": "08_05",
        "role": "absent_program_negative_control",
        "reason": "Previous canonical decision was absent/wrong. Executor must not manufacture a program.",
    },
    {
        "category": "Financial_Model",
        "id": "15_04",
        "role": "mechanical_boundary_witness",
        "reason": "Non-unit-stride homologues made automatic grouping unsafe. Unsupported declared sets must reject with zero writes.",
    },
]
HELD_OUT_CAP = 8
MIN_GROUP_SIZE = 4
MIN_MEMBERS = 8
FILL_RE = re.compile(r"^\s*calc_translate_fill\b", re.I)
WITNESS_08_03 = ("Working Capital", 44, 10, 14)  # J44:N44


def now() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=False, capture_output=True, text=True)
    return (result.stdout or "").strip()


def dataset_record(category: str, task_id: str) -> dict[str, Any]:
    records = load_json(DATA / category / "dataset.json")
    matches = [row for row in records if row["id"] == task_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one {category}:{task_id} record, found {len(matches)}")
    return matches[0]


def source_xlsx(category: str, task_id: str) -> Path:
    return DATA / category / dataset_record(category, task_id)["spreadsheet_path"]


def gold_xlsx(category: str, task_id: str) -> Path:
    return DATA / category / dataset_record(category, task_id)["golden_response_path"]


def list_tasks() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for category in CATEGORIES:
        path = DATA / category / "dataset.json"
        if not path.is_file():
            continue
        for row in load_json(path):
            out.append((category, row["id"]))
    return out


def _runs(coords: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for k in coords:
        if out and k == out[-1][-1] + 1:
            out[-1].append(k)
        else:
            out.append([k])
    return out


def _homogeneous_runs(sheet: str, axis: str, line: int, mapping: dict[int, str]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for run in _runs(sorted(mapping)):
        if len(run) < MIN_GROUP_SIZE:
            continue
        cells = [(sheet, line, k) if axis == "ROW" else (sheet, k, line) for k in run]
        anchor = cells[0]
        try:
            ok = all(
                pg.canonical(pg.translate(mapping[run[0]], anchor, cell)) == pg.canonical(mapping[k])
                for cell, k in zip(cells[1:], run[1:])
            )
        except Exception:
            ok = False
        if not ok:
            continue
        groups.append(
            {
                "sheet": sheet,
                "axis": axis,
                "line": line,
                "start": run[0],
                "end": run[-1],
                "size": len(run),
                "anchor": f"{sheet}!{fill.a1(*(cells[0][1:]))}",
            }
        )
    return groups


def census_workbook(xlsx: Path) -> dict[str, Any]:
    try:
        workbook = openpyxl.load_workbook(xlsx, data_only=False, read_only=True)
    except Exception as exc:
        return {
            "n_groups": 0,
            "n_members": 0,
            "max_group_size": 0,
            "n_sheets_with_groups": 0,
            "sheets": [],
            "groups": [],
            "unreadable": f"{type(exc).__name__}: {exc}",
        }
    groups: list[dict[str, Any]] = []
    try:
        for sheet in workbook.worksheets:
            by_row: dict[int, dict[int, str]] = defaultdict(dict)
            by_col: dict[int, dict[int, str]] = defaultdict(dict)
            for row in sheet.iter_rows():
                for cell in row:
                    value = cell.value
                    if isinstance(value, str) and value.startswith("="):
                        by_row[cell.row][cell.column] = value
                        by_col[cell.column][cell.row] = value
            for row_idx, cols in by_row.items():
                groups.extend(_homogeneous_runs(sheet.title, "ROW", row_idx, cols))
            for col_idx, rows in by_col.items():
                groups.extend(_homogeneous_runs(sheet.title, "COL", col_idx, rows))
    finally:
        workbook.close()
    members = sum(group["size"] for group in groups)
    sheets = sorted({group["sheet"] for group in groups})
    return {
        "n_groups": len(groups),
        "n_members": members,
        "max_group_size": max((group["size"] for group in groups), default=0),
        "n_sheets_with_groups": len(sheets),
        "sheets": sheets,
        "groups": groups,
    }


def held_out_census() -> dict[str, Any]:
    install_metadata_repair()
    rows: list[dict[str, Any]] = []
    for category, task_id in list_tasks():
        if (category, task_id) in PROGRAMGROUP_DEVELOPMENT:
            continue
        xlsx = source_xlsx(category, task_id)
        stats = census_workbook(xlsx)
        print(f"CENSUS {category}:{task_id} groups={stats['n_groups']} members={stats['n_members']}", flush=True)
        rows.append(
            {
                "category": category,
                "id": task_id,
                "qualified_id": f"{category}:{task_id}",
                "input_sha256": sha256_file(xlsx),
                **{k: stats[k] for k in ("n_groups", "n_members", "max_group_size", "n_sheets_with_groups", "sheets")},
                "groups": stats["groups"],
            }
        )
    eligible = [
        row
        for row in rows
        if row["max_group_size"] >= MIN_GROUP_SIZE and row["n_members"] >= MIN_MEMBERS
    ]
    eligible.sort(key=lambda row: (-row["n_members"], -row["n_groups"], -row["max_group_size"], row["category"], row["id"]))
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        buckets[row["category"]].append(row)
    selected: list[dict[str, Any]] = []
    while len(selected) < HELD_OUT_CAP:
        progressed = False
        for category in CATEGORIES:
            bucket = buckets.get(category) or []
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            progressed = True
            if len(selected) >= HELD_OUT_CAP:
                break
        if not progressed:
            break
    for row in selected:
        row["role"] = "held_out_execution_opportunity"
        row["reason"] = (
            f"Input-only: {row['n_groups']} mechanically witnessed repeat groups, "
            f"{row['n_members']} potential translated members, max group {row['max_group_size']}."
        )
    return {
        "scanned": len(rows),
        "eligible": len(eligible),
        "held_out_cap": HELD_OUT_CAP,
        "min_group_size": MIN_GROUP_SIZE,
        "min_members": MIN_MEMBERS,
        "excluded_programgroup_development": sorted(f"{c}:{i}" for c, i in PROGRAMGROUP_DEVELOPMENT),
        "gold_consulted": False,
        "evaluator_consulted": False,
        "historical_model_outcomes_consulted": False,
        "fewer_than_cap": len(selected) < HELD_OUT_CAP,
        "selected": selected,
        "eligible_ranked": [
            {k: row[k] for k in ("qualified_id", "n_groups", "n_members", "max_group_size", "n_sheets_with_groups")}
            for row in eligible
        ],
        "all_scanned_summary": [
            {k: row[k] for k in ("qualified_id", "n_groups", "n_members", "max_group_size")}
            for row in sorted(rows, key=lambda item: item["qualified_id"])
        ],
    }


def population(census: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for item in LEGACY_WITNESSES:
        tasks.append({**item, "repeats": 1, "qualified_id": f"{item['category']}:{item['id']}"})
    for item in census["selected"]:
        tasks.append(
            {
                "category": item["category"],
                "id": item["id"],
                "qualified_id": item["qualified_id"],
                "role": item["role"],
                "reason": item["reason"],
                "repeats": 1,
            }
        )
    return tasks


def pair_arms(index: int) -> tuple[str, str]:
    return ("C0", "C1") if index % 2 == 0 else ("C1", "C0")


def build_jobs(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    order = 0
    for index, spec in enumerate(tasks):
        for arm in pair_arms(index):
            order += 1
            jobs.append(
                {
                    "order": order,
                    "task": spec["qualified_id"],
                    "category": spec["category"],
                    "id": spec["id"],
                    "role": spec["role"],
                    "arm": arm,
                    "repeat": 1,
                    "run_name": f"glm-fill-{arm.lower()}-{spec['category']}-{spec['id']}-r1",
                    "pair_key": spec["qualified_id"],
                }
            )
    return jobs


def prompt_hashes() -> dict[str, str]:
    c0 = yaml.safe_load(CONTROL.read_text(encoding="utf-8"))
    c1 = yaml.safe_load(TREATMENT.read_text(encoding="utf-8"))
    return {
        "c0_system_sha256": sha256_text(c0["agent"]["templates"]["system_template"]),
        "c1_system_sha256": sha256_text(c1["agent"]["templates"]["system_template"]),
        "c0_instance_sha256": sha256_text(c0["agent"]["templates"]["instance_template"]),
        "c1_instance_sha256": sha256_text(c1["agent"]["templates"]["instance_template"]),
        "tool_schema_sha256": sha256_file(TOOL_SCHEMA),
        "executor_sha256": sha256_file(EXECUTOR),
        "c0_config_sha256": sha256_file(CONTROL),
        "c1_config_sha256": sha256_file(TREATMENT),
    }


def identity() -> dict[str, Any]:
    return {
        "declared_model": MODEL,
        "request_model": f"openrouter/{MODEL}",
        "temperature": GLM.temperature,
        "top_p": GLM.top_p,
        "reasoning_effort": GLM.reasoning,
        "tool_choice": "auto_or_required_by_catalog",
        "provider": dict(GLM.provider_options),
        "token_limit_policy": "remaining-budget",
        "cost_limit_usd": COST_LIMIT,
        "call_limit": CALL_LIMIT,
        "timeout_seconds": TIMEOUT,
        "execution_timeout": EXECUTION_TIMEOUT,
        "max_requeries": 2,
        "identity_source": "AUTHORITATIVE_EXPERIMENT_CONFIG",
    }


def freeze(census: dict[str, Any] | None = None) -> dict[str, Any]:
    census = census or held_out_census()
    tasks = population(census)
    jobs = build_jobs(tasks)
    hashes = prompt_hashes()
    workbooks = {
        f"{spec['category']}:{spec['id']}": sha256_file(source_xlsx(spec["category"], spec["id"]))
        for spec in tasks
    }
    spec = {
        "name": "default-harness-deterministic-execution",
        "frozen_at": now(),
        "git_commit": git_commit(),
        "hypothesis": "Once a general coding agent has chosen what cells to edit and what formula they should contain, does moving mechanically repetitive formula execution into a deterministic harness improve end-to-end spreadsheet capability over the default coding harness?",
        "primary_gate": "capability",
        "cost_secondary": True,
        "model": MODEL,
        "identity": identity(),
        "envelope": {"max_model_calls": CALL_LIMIT, "max_usd": COST_LIMIT, "timeout_seconds": TIMEOUT},
        "arms": {
            "C0": "official spreadsheet-control.yaml; bash+Python+openpyxl+view_xlsx+submit",
            "C1": "C0 plus optional calc_translate_fill; model remains sovereign",
        },
        "forbidden_architecture": [
            "Task IR",
            "Edit Plan authority",
            "scheduler",
            "retrieval",
            "synthesis",
            "autonomous compiled runner",
            "ProgramGroup-generated edit authority",
        ],
        "legacy_witnesses": LEGACY_WITNESSES,
        "held_out": {
            "n_selected": len(census["selected"]),
            "fewer_than_cap": census["fewer_than_cap"],
            "selected_ids": [row["qualified_id"] for row in census["selected"]],
        },
        "tasks": tasks,
        "jobs": jobs,
        "hashes": hashes,
        "source_workbook_sha256": workbooks,
        "slice": str(SLICE.relative_to(ROOT)),
    }
    write_json(ARTIFACT / "held_out_census.json", census)
    write_json(ARTIFACT / "experiment_spec.json", spec)
    write_json(ARTIFACT / "legacy_witness_mapping.json", LEGACY_WITNESSES)
    write_json(ARTIFACT / "frozen_task_list.json", tasks)
    write_json(ARTIFACT / "prompt_config_hashes.json", hashes)
    write_json(ARTIFACT / "provider_model_identity.json", identity())
    slice_payload = {
        "name": "default-harness-deterministic-execution",
        "purpose": "Frozen C0/C1 GLM capability probe: optional calc_translate_fill on the official SpreadsheetBench coding-agent scaffold. Legacy FM witnesses plus gold-blind held-out execution opportunities.",
        "model": MODEL,
        "max_tool_calls_per_task": CALL_LIMIT,
        "cost_limit_usd": COST_LIMIT,
        "arms": spec["arms"],
        "tasks": [{"category": row["category"], "id": row["id"]} for row in tasks],
    }
    write_json(SLICE, slice_payload)
    return spec


def run_name_root(run_name: str) -> Path:
    return RUNS / run_name


def job_task_root(job: dict[str, Any]) -> Path:
    return run_name_root(job["run_name"]) / f"{job['category']}-{job['id']}"


def runner_command(job: dict[str, Any]) -> list[str]:
    flag = "--control" if job["arm"] == "C0" else "--control-translate-fill"
    return [
        sys.executable,
        str(RUNNER),
        "--slice",
        str(SLICE),
        "--run-name",
        job["run_name"],
        "--task",
        job["task"],
        "--model",
        MODEL,
        flag,
        "--call-limit",
        str(CALL_LIMIT),
        "--cost-limit",
        str(COST_LIMIT),
        "--timeout",
        str(TIMEOUT),
        "--execution-timeout",
        str(EXECUTION_TIMEOUT),
        "--reasoning-effort",
        GLM.reasoning,
        "--max-requeries",
        "2",
        "--skip-existing",
        "--no-score",
    ]


def classify_failure(returncode: int, task_root: Path) -> str:
    if returncode == 0:
        return "ok"
    logs = list(task_root.rglob("*.log")) if task_root.exists() else []
    blob = ""
    for path in logs[-3:]:
        try:
            blob += path.read_text(encoding="utf-8", errors="replace")[-8000:]
        except OSError:
            continue
    ledger: dict[str, Any] = {}
    ledger_path = task_root.parent / "ledger.jsonl"
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            ledger = {}
    model_calls = int(ledger.get("model_calls") or 0)
    cost_usd = float(ledger.get("charged_cost_usd") or 0)
    envelope_marker = any(
        token in blob.lower()
        for token in ("reached maximum of", "cost limit reached", "call limit reached")
    )
    if (model_calls >= CALL_LIMIT or cost_usd >= COST_LIMIT or envelope_marker) and model_calls > 0:
        return "envelope_or_resource"
    markers = ("Rate limit", "APIError", "OpenRouter", "502", "503", "timeout after")
    if returncode in {120, 124, 137} or any(marker in blob for marker in markers) or model_calls == 0:
        return "provider_or_infra"
    return "semantic_or_other"


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    task_root = job_task_root(job)
    run_root = run_name_root(job["run_name"])
    if (task_root / "output.xlsx").is_file() and (task_root / "run_contract.json").is_file():
        return {"job": job, "status": "skipped_existing", "returncode": 0, "failure_class": "ok"}
    if run_root.exists() and not (task_root / "output.xlsx").is_file():
        ledger_path = run_root / "ledger.jsonl"
        model_calls = 0
        if ledger_path.is_file() and ledger_path.read_text(encoding="utf-8").strip():
            try:
                last = json.loads(ledger_path.read_text(encoding="utf-8").strip().splitlines()[-1])
                model_calls = int(last.get("model_calls") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                model_calls = 0
        if model_calls > 0:
            return {"job": job, "status": "failed", "returncode": 1, "failure_class": "semantic_or_other"}
        shutil.rmtree(run_root)
    started = now()
    result = subprocess.run(runner_command(job), cwd=ROOT, check=False)
    failure_class = classify_failure(result.returncode, task_root)
    payload = {
        "job": job,
        "status": "completed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "failure_class": failure_class,
        "started_at": started,
        "finished_at": now(),
    }
    write_json(task_root / "fill_job.json", payload)
    return payload


def launch(jobs: list[dict[str, Any]], *, workers: int = WORKERS, dry_run: bool = False) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for job in jobs:
        key = job["pair_key"]
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(job)
    groups = [grouped[key] for key in order]
    write_json(ARTIFACT / "manifest.json", {"jobs": jobs, "groups": [[j["run_name"] for j in g] for g in groups], "written_at": now()})
    if dry_run:
        return {"dry_run": True, "jobs": len(jobs), "groups": len(groups)}
    _load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY must be set")
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required")
    locks = {job["task"]: threading.Lock() for job in jobs}
    results: list[dict[str, Any]] = []

    def run_group(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with locks[group[0]["task"]]:
            return [run_job(job) for job in group]

    print(f"LAUNCH groups={len(groups)} jobs={len(jobs)} workers={workers}", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_group, group): group for group in groups}
        for future in as_completed(futures):
            results.extend(future.result())
            print(f"GROUP done {[job['run_name'] for job in futures[future]]}", flush=True)
    write_json(ARTIFACT / "launch_results.json", results)
    return {"results": results}


def score_runs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    scores: dict[str, Any] = {}
    for job in jobs:
        run_root = run_name_root(job["run_name"])
        key = f"{job['task']}:{job['arm']}"
        if not run_root.exists():
            scores[key] = {"status": "missing_run"}
            continue
        result = subprocess.run(
            [sys.executable, str(SCORER), str(run_root), "--write-ledger"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        official = run_root / "official_scores.json"
        payload = load_json(official) if official.is_file() else {}
        task_scores = {}
        if isinstance(payload.get("tasks"), dict):
            task_scores = payload["tasks"].get(job["task"]) or {}
        scores[key] = {"returncode": result.returncode, "official": task_scores, "stderr": (result.stderr or "")[-2000:]}
    write_json(ARTIFACT / "official_scores.json", scores)
    return scores


def _metrics(inner: dict[str, Any]) -> dict[str, Any]:
    if not inner:
        return {"modification": None, "regression": None, "exact": None, "usable": None}
    modification = inner.get("modification_accuracy")
    regression = inner.get("regression_accuracy")
    exact = inner.get("accuracy")
    usable = (
        modification is not None
        and regression is not None
        and float(modification) >= 0.99
        and float(regression) >= 0.99
    )
    return {"modification": modification, "regression": regression, "exact": exact, "usable": usable}


def formulas_in(path: Path, sheet: str, row: int, c1: int, c2: int) -> dict[str, str | None]:
    if not path.is_file():
        return {}
    workbook = openpyxl.load_workbook(path, data_only=False)
    try:
        if sheet not in workbook.sheetnames:
            return {}
        ws = workbook[sheet]
        return {fill.a1(row, col): ws.cell(row, col).value for col in range(c1, c2 + 1)}
    finally:
        workbook.close()


def parse_fill_calls(traj_path: Path | None, ledger_path: Path | None) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    if ledger_path and ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                calls.append(json.loads(line))
    if traj_path and traj_path.is_file():
        data = json.loads(traj_path.read_text(encoding="utf-8"))
        n_actions = 0
        for step in data.get("trajectory") or []:
            action = str(step.get("action") or "")
            extra = step.get("extra_info") or {}
            names = []
            if isinstance(extra, dict):
                for item in extra.get("tool_calls") or []:
                    if isinstance(item, dict):
                        names.append(((item.get("function") or {}).get("name")))
            if FILL_RE.search(action) or "calc_translate_fill" in names:
                n_actions += 1
        return {"used": n_actions > 0 or bool(calls), "n_tool_actions": n_actions, "invocations": calls}
    return {"used": bool(calls), "n_tool_actions": 0, "invocations": calls}


def classify_invocation(inv: dict[str, Any], gold: dict[str, str | None]) -> str:
    if inv.get("status") != "accepted":
        return "REJECTED"
    wrote = inv.get("translated_formulas") or {}
    declared = set(inv.get("targets") or [])
    written_cells = set(inv.get("changed_cells") or [])
    if written_cells - declared:
        return "OVERMERGED_MECHANICAL_GROUP"
    if declared - written_cells:
        return "UNDERFILLED_TARGET_SET"
    if not gold:
        return "UNRESOLVED"
    gold_formulas = {f"{list(gold)[0].split('!')[0] if False else ''}"}
    # gold keys are A1 on the known sheet; invocations use Sheet!A1
    mapped = {}
    for cell, formula in wrote.items():
        addr = cell.split("!", 1)[-1]
        mapped[addr] = formula
    if not any(gold.get(addr) for addr in mapped):
        return "WRONG_TARGET_AUTHORITY"
    canonical = inv.get("canonical_formula")
    origin = (inv.get("canonical_cell") or "").split("!", 1)[-1]
    gold_at_origin = gold.get(origin)
    faithful = True
    try:
        origin_cell = fill.parse_qualified_cell(inv["canonical_cell"])
        for target in inv.get("targets") or []:
            cell = fill.parse_qualified_cell(target)
            expected = pg.translate(canonical, origin_cell, cell)
            if wrote.get(target) != expected:
                faithful = False
                break
    except Exception:
        faithful = False
    exact_members = sum(1 for addr, formula in mapped.items() if gold.get(addr) == formula)
    if gold_at_origin == canonical and exact_members == len(mapped) and faithful:
        return "CORRECT_CANONICAL_CORRECT_EXECUTION"
    if gold_at_origin == canonical and not faithful:
        return "CORRECT_CANONICAL_WRONG_EXECUTION"
    if faithful and exact_members < len(mapped):
        return "WRONG_CANONICAL_FAITHFUL_EXECUTION"
    if declared and not set(mapped) <= set(gold):
        return "WRONG_TARGET_AUTHORITY"
    return "UNRESOLVED"


def ledger_usage(run_root: Path) -> dict[str, Any]:
    path = run_root / "ledger.jsonl"
    if not path.is_file():
        return {}
    try:
        rec = json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {}
    return {
        "model_calls": rec.get("model_calls"),
        "input_tokens": rec.get("prompt_tokens") or rec.get("input_tokens"),
        "output_tokens": rec.get("completion_tokens") or rec.get("output_tokens"),
        "tool_calls": rec.get("tool_calls"),
        "charged_cost_usd": rec.get("charged_cost_usd"),
        "wall_time_s": rec.get("elapsed_seconds") or rec.get("wall_time_s"),
        "status": rec.get("status"),
    }


def autopsy_08_03(jobs: list[dict[str, Any]], scores: dict[str, Any]) -> dict[str, Any]:
    sheet, row, c1, c2 = WITNESS_08_03
    gold = formulas_in(gold_xlsx("Financial_Model", "08_03"), sheet, row, c1, c2)
    out: dict[str, Any] = {"region": "Working Capital!J44:N44", "gold": gold}
    for job in jobs:
        if job["task"] != "Financial_Model:08_03":
            continue
        output = job_task_root(job) / "output.xlsx"
        got = formulas_in(output, sheet, row, c1, c2)
        exact = [addr for addr, value in got.items() if value == gold.get(addr)]
        out[job["arm"]] = {
            "formulas": got,
            "exact_members": len(exact),
            "n_members": len(gold),
            "official": _metrics((scores.get(f"{job['task']}:{job['arm']}") or {}).get("official") or {}),
        }
    c0 = out.get("C0") or {}
    if c0.get("exact_members") == c0.get("n_members") and c0.get("n_members"):
        out["headroom"] = "NO_HEADROOM_ON_08_03"
    else:
        out["headroom"] = "HEADROOM_PRESENT"
    return out


def analyze(spec: dict[str, Any], scores: dict[str, Any]) -> dict[str, Any]:
    rows = []
    invocations: list[dict[str, Any]] = []
    gold_08 = formulas_in(gold_xlsx("Financial_Model", "08_03"), *WITNESS_08_03)
    for task in spec["tasks"]:
        pair = {}
        for arm in ("C0", "C1"):
            key = f"{task['qualified_id']}:{arm}"
            job = next(j for j in spec["jobs"] if j["task"] == task["qualified_id"] and j["arm"] == arm)
            task_root = job_task_root(job)
            traj = sorted(task_root.rglob("*.traj"))
            fill_ledger = task_root / "output" / ".calc_translate_fill_ledger.jsonl"
            if not fill_ledger.is_file():
                matches = list(task_root.rglob(".calc_translate_fill_ledger.jsonl"))
                fill_ledger = matches[0] if matches else fill_ledger
            parsed = parse_fill_calls(traj[-1] if traj else None, fill_ledger if fill_ledger.is_file() else None)
            usage = ledger_usage(run_name_root(job["run_name"]))
            official = _metrics((scores.get(key) or {}).get("official") or {})
            pair[arm] = {
                "official": official,
                "usage": usage,
                "output_exists": (task_root / "output.xlsx").is_file(),
                "fill": parsed if arm == "C1" else None,
                "failure_class": ((scores.get(key) or {}).get("status")),
            }
            if arm == "C1":
                gold = gold_08 if task["id"] == "08_03" else {}
                if task["id"] != "08_03":
                    # Evaluator-side gold for classification only, after scoring.
                    try:
                        gpath = gold_xlsx(task["category"], task["id"])
                        gold = {"_workbook": str(gpath)}
                    except Exception:
                        gold = {}
                for inv in parsed.get("invocations") or []:
                    label = classify_invocation(inv, gold_08 if task["id"] == "08_03" else {})
                    record = {
                        "task": task["qualified_id"],
                        "role": task["role"],
                        "classification": label,
                        **inv,
                    }
                    invocations.append(record)
        c0, c1 = pair["C0"]["official"], pair["C1"]["official"]
        rows.append(
            {
                "task": task["qualified_id"],
                "role": task["role"],
                "c0_exact": c0.get("exact"),
                "c1_exact": c1.get("exact"),
                "c0_modification": c0.get("modification"),
                "c1_modification": c1.get("modification"),
                "c0_regression": c0.get("regression"),
                "c1_regression": c1.get("regression"),
                "c0_usable": c0.get("usable"),
                "c1_usable": c1.get("usable"),
                "c0_output": pair["C0"]["output_exists"],
                "c1_output": pair["C1"]["output_exists"],
                "c1_used_fill": (pair["C1"]["fill"] or {}).get("used"),
                "c0_calls": pair["C0"]["usage"].get("model_calls"),
                "c1_calls": pair["C1"]["usage"].get("model_calls"),
                "c0_cost": pair["C0"]["usage"].get("charged_cost_usd"),
                "c1_cost": pair["C1"]["usage"].get("charged_cost_usd"),
                "delta_exact": None
                if c0.get("exact") is None or c1.get("exact") is None
                else c1["exact"] - c0["exact"],
            }
        )
    write_json(ARTIFACT / "paired_scores.json", rows)
    with (ARTIFACT / "paired_scores.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["task"])
        writer.writeheader()
        writer.writerows(rows)
    write_json(ARTIFACT / "execution_ledger.json", invocations)
    classes = defaultdict(int)
    for inv in invocations:
        classes[inv["classification"]] += 1
    write_json(ARTIFACT / "semantic_vs_execution_census.json", dict(classes))
    return {"rows": rows, "invocations": invocations, "classes": dict(classes)}


def verdict(analysis: dict[str, Any], autopsy: dict[str, Any], launch_results: list[dict[str, Any]]) -> str:
    infra = [item for item in launch_results if item.get("failure_class") == "provider_or_infra"]
    envelope = [item for item in launch_results if item.get("failure_class") == "envelope_or_resource"]
    if infra or envelope:
        paired = defaultdict(set)
        for item in launch_results:
            job = item.get("job") or {}
            paired[job.get("pair_key")].add(item.get("failure_class"))
        if any("provider_or_infra" in classes or "envelope_or_resource" in classes for classes in paired.values()):
            if len(analysis["rows"]) and all(
                row.get("c0_exact") is None or row.get("c1_exact") is None for row in analysis["rows"]
            ):
                return "PROVIDER_OR_RESOURCE_CENSORED"
    rows = analysis["rows"]
    used = sum(1 for row in rows if row.get("c1_used_fill"))
    harmful = any(
        (row.get("c1_regression") or 1) < 0.99 <= (row.get("c0_regression") or 1) for row in rows
    )
    if harmful:
        return "EXECUTOR_HARMFUL"
    if used == 0:
        return "NO_EXECUTOR_ADOPTION"
    gain = any(
        (row.get("c1_exact") or 0) > (row.get("c0_exact") or 0)
        or (row.get("c1_usable") and not row.get("c0_usable"))
        or (row.get("c1_modification") or 0) > (row.get("c0_modification") or 0) + 1e-9
        for row in rows
    )
    correct_exec = analysis["classes"].get("CORRECT_CANONICAL_CORRECT_EXECUTION", 0)
    faithful_wrong = analysis["classes"].get("WRONG_CANONICAL_FAITHFUL_EXECUTION", 0)
    if gain and correct_exec and not harmful:
        return "DEFAULT_HARNESS_EXECUTION_GAIN"
    if autopsy.get("headroom") == "NO_HEADROOM_ON_08_03" and not gain:
        return "EXECUTOR_WORKS_NO_DEFAULT_HEADROOM"
    if used and not gain and (faithful_wrong or not correct_exec):
        return "SEMANTIC_CHOICE_DOMINANT"
    if used and not gain:
        return "EXECUTOR_WORKS_NO_DEFAULT_HEADROOM"
    return "SEMANTIC_CHOICE_DOMINANT"


def write_report(spec: dict[str, Any], analysis: dict[str, Any], autopsy: dict[str, Any], chosen: str) -> None:
    rows = analysis["rows"]
    lines = [
        "# Default harness deterministic execution",
        "",
        f"**Verdict:** `{chosen}`",
        "",
        "Primary question: once a general coding agent has chosen what cells to edit and what formula they should contain, does moving mechanically repetitive formula execution into a deterministic harness improve end-to-end spreadsheet capability over the default coding harness?",
        "",
        "Cost is recorded in the appendix and is not part of the gate.",
        "",
        "## Frozen contract",
        "",
        f"- Model: `{MODEL}` reasoning `{GLM.reasoning}` temperature {GLM.temperature} top_p {GLM.top_p}",
        f"- Envelope: {CALL_LIMIT} calls / ${COST_LIMIT:.2f} / {TIMEOUT}s timeout, matched across arms",
        f"- C0: `{CONTROL.name}`",
        f"- C1: `{TREATMENT.name}` plus `calc_translate_fill`",
        f"- Tasks: {len(spec['tasks'])} ({len(LEGACY_WITNESSES)} legacy witnesses + {spec['held_out']['n_selected']} held-out)",
        f"- Held-out fewer than cap: {spec['held_out']['fewer_than_cap']}",
        "",
        "## Paired official scores",
        "",
        "| Task | Role | C0 exact | C1 exact | C0 mod | C1 mod | C0 reg | C1 reg | C0 usable | C1 usable | C1 used fill |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['task']}` | {row['role']} | {row['c0_exact']} | {row['c1_exact']} | "
            f"{row['c0_modification']} | {row['c1_modification']} | {row['c0_regression']} | "
            f"{row['c1_regression']} | {row['c0_usable']} | {row['c1_usable']} | {row['c1_used_fill']} |"
        )
    lines += [
        "",
        "## 08_03 witness autopsy",
        "",
        f"- Region: `{autopsy.get('region')}`",
        f"- Headroom: `{autopsy.get('headroom')}`",
        f"- C0 exact members: {(autopsy.get('C0') or {}).get('exact_members')} / {(autopsy.get('C0') or {}).get('n_members')}",
        f"- C1 exact members: {(autopsy.get('C1') or {}).get('exact_members')} / {(autopsy.get('C1') or {}).get('n_members')}",
        "",
        "## Execution classifications",
        "",
    ]
    if analysis["classes"]:
        for key, value in sorted(analysis["classes"].items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- No accepted or rejected `calc_translate_fill` invocations were recorded.")
    lines += [
        "",
        "## Negative-control audit",
        "",
        "C1 must not repair a wrong canonical formula, must not invent a program on 08_05, must reject unsupported 15_04 declarations with zero writes, and must not write outside the model-declared set.",
        "",
        "## Appendix: cost (not in the gate)",
        "",
        "| Task | C0 calls | C1 calls | C0 $ | C1 $ |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['task']}` | {row['c0_calls']} | {row['c1_calls']} | {row['c0_cost']} | {row['c1_cost']} |"
        )
    lines += ["", f"Spec: `{ARTIFACT / 'experiment_spec.json'}`", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "launch", "score", "report", "run"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    if args.command == "freeze":
        spec = freeze()
        print(json.dumps({"tasks": [t["qualified_id"] for t in spec["tasks"]], "jobs": len(spec["jobs"])}, indent=2))
        return 0
    spec = load_json(ARTIFACT / "experiment_spec.json") if (ARTIFACT / "experiment_spec.json").is_file() else freeze()
    if args.command in {"launch", "run"}:
        launch(spec["jobs"], workers=args.workers, dry_run=args.dry_run)
        if args.dry_run:
            return 0
    if args.command in {"score", "run"} and not args.dry_run:
        scores = score_runs(spec["jobs"])
    else:
        scores = load_json(ARTIFACT / "official_scores.json") if (ARTIFACT / "official_scores.json").is_file() else {}
    if args.command in {"report", "run"} and not args.dry_run:
        analysis = analyze(spec, scores)
        autopsy = autopsy_08_03(spec["jobs"], scores)
        write_json(ARTIFACT / "08_03_autopsy.json", autopsy)
        launch_results = load_json(ARTIFACT / "launch_results.json") if (ARTIFACT / "launch_results.json").is_file() else []
        chosen = verdict(analysis, autopsy, launch_results)
        write_json(ARTIFACT / "verdict.json", {"verdict": chosen})
        write_report(spec, analysis, autopsy, chosen)
        print(chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
