#!/usr/bin/env python3
"""Score an OpenRouter run with the official evaluator and write the submission pack.

This is the same scoring step the frozen and OpenRouter runners invoke at the end of
inference. It is not a second model run. Re-invoking this script only refreshes outputs
and re-runs evaluation.py.

Default runtime is unmodified evaluation/evaluation.py after LibreOffice refresh via
evaluation/open_spreadsheet.py. Missing workbooks stay missing and score 0. Financial_Model
06_01..06_05 goldens may surface as openpyxl ParseError rows; that is official eval
behavior. --metadata-tolerant is a local-only escape hatch, not the submission runtime.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
EVALUATION_DIR = DEFAULT_BENCHMARK_ROOT / "evaluation"
EVALUATION_SCRIPT = EVALUATION_DIR / "evaluation.py"
OPEN_SPREADSHEET = EVALUATION_DIR / "open_spreadsheet.py"
EVALUATION_RUNNER = Path(__file__).resolve().parent / "run_evaluation.py"
NONVISUAL = ("Template", "Financial_Model", "Debugging")
OFFICIAL_RUNTIME = "unmodified-official-evaluation.py"
METADATA_RUNTIME = "metadata-tolerant-local-v1"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ledger_records(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _latest_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        task = str(record.get("task", ""))
        if not task:
            continue
        finished = record.get("finished_at") or ""
        prior = latest.get(task)
        if prior is None or finished >= str(prior.get("finished_at") or ""):
            latest[task] = record
    return latest


def _attempted_tasks(run_root: Path) -> list[dict[str, str]]:
    tasks: list[dict[str, str]] = []
    for path in sorted(run_root.iterdir()):
        if not path.is_dir() or "-" not in path.name:
            continue
        category, _, task_id = path.name.partition("-")
        if category not in NONVISUAL or not task_id:
            continue
        tasks.append({"category": category, "id": task_id})
    return tasks


def _stage_outputs(run_root: Path, tasks: list[dict[str, str]], staging_root: Path) -> int:
    staged = 0
    if staging_root.exists():
        shutil.rmtree(staging_root)
    for task in tasks:
        category = task["category"]
        task_id = task["id"]
        source = run_root / f"{category}-{task_id}" / "output.xlsx"
        if not source.is_file():
            continue
        destination_dir = staging_root / category
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / f"{task_id}_output.xlsx")
        staged += 1
    staging_root.mkdir(parents=True, exist_ok=True)
    return staged


def _refresh_outputs(outputs_root: Path) -> None:
    command = [
        sys.executable,
        str(OPEN_SPREADSHEET),
        "--dir_path",
        str(outputs_root),
    ]
    completed = subprocess.run(command, cwd=EVALUATION_DIR, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"open_spreadsheet.py refresh failed with status {completed.returncode}"
        )


def _official_result_path(model_name: str, category: str) -> Path:
    results_dir = EVALUATION_DIR / "research/history/results" / category
    matches = sorted(
        results_dir.glob(f"{model_name}_{category}_*_regression.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not matches:
        raise FileNotFoundError(
            f"evaluator JSON not found for {category} under {results_dir}"
        )
    return matches[-1]


def _evaluate_category(
    *,
    model_name: str,
    category: str,
    outputs_dir: Path,
    evaluator: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(evaluator),
        "--model",
        model_name,
        "--dataset",
        category,
        "--outputs-dir",
        str(outputs_dir),
    ]
    completed = subprocess.run(command, cwd=EVALUATION_DIR, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"evaluation failed for {category} with status {completed.returncode}")
    return _load_json(_official_result_path(model_name, category))


def _score_lookup(
    results_by_category: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for category, payload in results_by_category.items():
        for item in payload.get("scores", []):
            scores[f"{category}:{item['id']}"] = item
    return scores


def _missing_item(task_id: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "error_message": "output file not exist",
        "regression_accuracy": 0.0,
        "modification_accuracy": 0.0,
        "accuracy": 0.0,
    }


def score_run(
    run_root: Path,
    *,
    model_name: str | None = None,
    write_ledger: bool = False,
    refresh: bool = True,
    metadata_tolerant: bool = False,
) -> int:
    run_root = run_root.resolve()
    if not run_root.is_dir():
        raise FileNotFoundError(run_root)
    tasks = _attempted_tasks(run_root)
    if not tasks:
        print(f"SCORE skip: no non-visual task directories in {run_root}", flush=True)
        return 0

    model_name = model_name or run_root.name
    runtime = METADATA_RUNTIME if metadata_tolerant else OFFICIAL_RUNTIME
    evaluator = EVALUATION_RUNNER if metadata_tolerant else EVALUATION_SCRIPT
    submission_root = run_root / "submission"
    outputs_root = submission_root / "outputs"
    results_root = submission_root / "results"
    staged = _stage_outputs(run_root, tasks, outputs_root)
    print(f"STAGE workbooks={staged}/{len(tasks)} dir={outputs_root}", flush=True)
    if refresh:
        print(f"REFRESH {OPEN_SPREADSHEET.name} {outputs_root}", flush=True)
        _refresh_outputs(outputs_root)

    categories = sorted({task["category"] for task in tasks})
    results_by_category: dict[str, dict[str, Any]] = {}
    results_root.mkdir(parents=True, exist_ok=True)
    for category in categories:
        payload = _evaluate_category(
            model_name=model_name,
            category=category,
            outputs_dir=outputs_root / category,
            evaluator=evaluator,
        )
        results_by_category[category] = payload
        official_json = _official_result_path(model_name, category)
        shutil.copy2(official_json, results_root / official_json.name)
        print(f"OFFICIAL_JSON {results_root / official_json.name}", flush=True)

    score_lookup = _score_lookup(results_by_category)
    exact = 0
    scored = 0
    missing = 0
    print(f"RUN {run_root.name}", flush=True)
    print(f"EVALUATION_RUNTIME {runtime}", flush=True)
    task_rows: dict[str, Any] = {}
    for task in tasks:
        key = f"{task['category']}:{task['id']}"
        item = score_lookup.get(key) or _missing_item(task["id"])
        task_rows[key] = item
        scored += 1
        is_exact = item.get("accuracy") == 1.0
        exact += int(is_exact)
        error = str(item.get("error_message") or "")
        if "not exist" in error:
            missing += 1
        print(
            f"  {key}: reg={item.get('regression_accuracy')} "
            f"mod={item.get('modification_accuracy')} exact={is_exact} {error[:90]}",
            flush=True,
        )

    print(f"SUMMARY exact={exact}/{scored} missing_outputs={missing}", flush=True)

    ledger_path = run_root / "ledger.jsonl"
    if write_ledger:
        updates = _latest_records(_ledger_records(ledger_path))
        for task in tasks:
            key = f"{task['category']}:{task['id']}"
            item = task_rows.get(key)
            if item is None or key not in updates:
                continue
            row = dict(updates[key])
            row["exact_success"] = item.get("accuracy") == 1.0
            row["regression_accuracy"] = item.get("regression_accuracy")
            row["modification_accuracy"] = item.get("modification_accuracy")
            row["evaluator_error"] = item.get("error_message") or None
            row["evaluation_runtime"] = runtime
            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"LEDGER appended scored rows to {ledger_path}", flush=True)

    results_path = run_root / "official_scores.json"
    results_path.write_text(
        json.dumps(
            {
                "run_name": run_root.name,
                "model_name": model_name,
                "evaluation_runtime": runtime,
                "exact": exact,
                "scored": scored,
                "missing_outputs": missing,
                "submission": {
                    "outputs": str(outputs_root),
                    "official_json": str(results_root),
                },
                "tasks": task_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"RESULTS {results_path}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path, help="Path to benchmark-runs/openrouter/<run-name>")
    parser.add_argument("--model-name", help="Label passed to the official evaluator")
    parser.add_argument(
        "--write-ledger",
        action="store_true",
        help="Append exact_success updates to ledger.jsonl (does not rewrite prior rows)",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Skip LibreOffice open_spreadsheet.py refresh (not for submission packets)",
    )
    parser.add_argument(
        "--metadata-tolerant",
        action="store_true",
        help="Local-only openpyxl docProps repair; do not email this JSON as official eval",
    )
    args = parser.parse_args()
    return score_run(
        args.run_root,
        model_name=args.model_name,
        write_ledger=args.write_ledger,
        refresh=not args.no_refresh,
        metadata_tolerant=args.metadata_tolerant,
    )


if __name__ == "__main__":
    raise SystemExit(main())
