#!/usr/bin/env python3
"""Official-score outputs from an OpenRouter benchmark run and optionally update its ledger."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
EVALUATION_SCRIPT = DEFAULT_BENCHMARK_ROOT / "evaluation" / "evaluation.py"
# Invoked instead of EVALUATION_SCRIPT so that workbooks with malformed docProps metadata
# (Financial_Model 06_01..06_05) can be scored at all. See benchmark/run_evaluation.py.
EVALUATION_RUNNER = Path(__file__).resolve().parent / "run_evaluation.py"


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


def _stage_outputs(run_root: Path, tasks: list[dict[str, str]], staging_root: Path) -> None:
    for task in tasks:
        category = task["category"]
        task_id = task["id"]
        source = run_root / f"{category}-{task_id}" / "output.xlsx"
        if not source.is_file():
            raise FileNotFoundError(f"Missing output workbook: {source}")
        destination_dir = staging_root / category
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / f"{task_id}_output.xlsx")


def _evaluate_category(
    *,
    model_name: str,
    category: str,
    outputs_dir: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(EVALUATION_RUNNER),
        "--model",
        model_name,
        "--dataset",
        category,
        "--outputs-dir",
        str(outputs_dir),
    ]
    completed = subprocess.run(command, cwd=EVALUATION_SCRIPT.parent, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"evaluation failed for {category} with status {completed.returncode}")
    result_path = (
        EVALUATION_SCRIPT.parent
        / "results"
        / category
        / f"{model_name}_{category}__regression.json"
    )
    return _load_json(result_path)


def _tasks_from_run(run_root: Path, ledger_path: Path) -> list[dict[str, str]]:
    latest = _latest_records(_ledger_records(ledger_path))
    tasks: list[dict[str, str]] = []
    for task_name, record in sorted(latest.items()):
        if record.get("status") != "completed":
            continue
        category, task_id = task_name.split(":", 1)
        tasks.append({"category": category, "id": task_id})
    return tasks


def _score_lookup(
    results_by_category: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for category, payload in results_by_category.items():
        for item in payload.get("scores", []):
            scores[f"{category}:{item['id']}"] = item
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path, help="Path to benchmark-runs/openrouter/<run-name>")
    parser.add_argument("--model-name", help="Label passed to the official evaluator")
    parser.add_argument(
        "--write-ledger",
        action="store_true",
        help="Append exact_success updates to ledger.jsonl (does not rewrite prior rows)",
    )
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    ledger_path = run_root / "ledger.jsonl"
    if not run_root.is_dir():
        raise FileNotFoundError(run_root)
    tasks = _tasks_from_run(run_root, ledger_path)
    if not tasks:
        raise RuntimeError(f"No completed tasks with output workbooks found in {run_root}")

    model_name = args.model_name or run_root.name
    categories = sorted({task["category"] for task in tasks})

    with tempfile.TemporaryDirectory(prefix="librecalc-score-") as temporary_directory:
        staging_root = Path(temporary_directory)
        _stage_outputs(run_root, tasks, staging_root)
        results_by_category = {
            category: _evaluate_category(
                model_name=model_name,
                category=category,
                outputs_dir=staging_root / category,
            )
            for category in categories
        }

    score_lookup = _score_lookup(results_by_category)
    exact = 0
    scored = 0
    print(f"RUN {run_root.name}")
    for task in tasks:
        key = f"{task['category']}:{task['id']}"
        item = score_lookup.get(key)
        if item is None:
            print(f"  {key}: missing evaluator row")
            continue
        scored += 1
        is_exact = item.get("accuracy") == 1.0
        exact += int(is_exact)
        err = (item.get("error_message") or "")[:90]
        print(
            f"  {key}: reg={item.get('regression_accuracy')} "
            f"mod={item.get('modification_accuracy')} exact={is_exact} {err}"
        )

    print(f"SUMMARY exact={exact}/{scored}")

    if args.write_ledger:
        updates = _latest_records(_ledger_records(ledger_path))
        for task in tasks:
            key = f"{task['category']}:{task['id']}"
            item = score_lookup.get(key)
            if item is None or key not in updates:
                continue
            row = dict(updates[key])
            row["exact_success"] = item.get("accuracy") == 1.0
            row["regression_accuracy"] = item.get("regression_accuracy")
            row["modification_accuracy"] = item.get("modification_accuracy")
            row["evaluator_error"] = item.get("error_message") or None
            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"LEDGER appended scored rows to {ledger_path}")

    results_path = run_root / "official_scores.json"
    results_path.write_text(
        json.dumps(
            {
                "run_name": run_root.name,
                "model_name": model_name,
                "exact": exact,
                "scored": scored,
                "tasks": {
                    f"{task['category']}:{task['id']}": score_lookup.get(
                        f"{task['category']}:{task['id']}"
                    )
                    for task in tasks
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"RESULTS {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
