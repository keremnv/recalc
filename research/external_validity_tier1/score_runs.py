#!/usr/bin/env python3
"""Tier 1 correctness scoring (prereg §6). Post-hoc, uniform across cells.

- Controlled tasks: official unmodified evaluation.py via
  benchmark/score_openrouter_run.score_run (refresh=True, write_ledger=False).
- Curated tasks: frozen research/external_validity_tier1/evaluate_curated.py.
- Missing outputs score 0 (official _missing_item semantics).

Emits CORRECTNESS_ROWS.jsonl (one row per cell) to stdout.
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parents[1]
RUNS = BASE / "_overlay/benchmark-root/benchmark-runs/openrouter"
sys.path.insert(0, str(PROJECT_ROOT / "benchmark"))
from score_openrouter_run import (  # noqa: E402
    EVALUATION_DIR,
    EVALUATION_SCRIPT,
    _attempted_tasks,
    _missing_item,
    _refresh_outputs,
    _score_lookup,
    _stage_outputs,
)


def score_controlled(run_dir: Path, task: str) -> dict:
    # Same official flow as score_run (stage + LO refresh + unmodified
    # evaluation.py), but reading the result JSON from where this checkout's
    # evaluation.py actually writes it (evaluation/results/<cat>/). The
    # committed scorer's research/history/results path does not exist here.
    run_dir = run_dir.resolve()
    model_name = f"tier1-{run_dir.name}"
    tasks = _attempted_tasks(run_dir)
    submission_root = run_dir / "submission"
    outputs_root = submission_root / "outputs"
    _stage_outputs(run_dir, tasks, outputs_root)
    _refresh_outputs(outputs_root)
    category = task.split(":")[0]
    cmd = [sys.executable, str(EVALUATION_SCRIPT), "--model", model_name,
           "--dataset", category, "--outputs-dir", str(outputs_root / category)]
    completed = subprocess.run(cmd, cwd=EVALUATION_DIR, check=False,
                               capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"evaluation.py failed: {completed.stderr[-300:]}")
    results = sorted((EVALUATION_DIR / "results" / category).glob(f"{model_name}_*.json"))
    assert results, f"{run_dir}: no official result json"
    payload = json.loads(results[-1].read_text())
    lookup = _score_lookup({category: payload})
    item = lookup.get(task) or _missing_item(task.split(":")[1])
    return {"task": task, "evaluator": "official-evaluation.py",
            "exact_success": item.get("accuracy") == 1.0,
            "regression_accuracy": item.get("regression_accuracy", 0.0),
            "modification_accuracy": item.get("modification_accuracy", 0.0),
            "accuracy": item.get("accuracy", 0.0),
            "error": item.get("error_message")}


def score_curated(run_dir: Path, task: str) -> dict:
    tid = task.split(":")[1]
    out = run_dir / f"Curated_Tier1-{tid}" / "output.xlsx"
    row = {"task": task, "evaluator": "tier1-evaluate_curated.py",
           "exact_success": False, "detail": None}
    if not out.is_file():
        row["detail"] = "output file not exist"
        return row
    golden = BASE / "curated" / f"{tid}_golden.xlsx"
    cmd = [sys.executable, str(BASE / "evaluate_curated.py"),
           str(BASE / "curated" / "specs.json"), tid, str(out), str(golden)]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        text = completed.stdout
        detail = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (IndexError, ValueError):
        detail = {"raw_stdout": completed.stdout[-500:], "returncode": completed.returncode,
                  "stderr_tail": completed.stderr[-500:]}
    row["detail"] = detail
    row["exact_success"] = bool(detail.get("exact_success", False))
    return row


def main() -> None:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "tier1-r*"
    for run_dir in sorted(RUNS.glob(pattern)):
        rec = json.loads((run_dir / "ledger.jsonl").read_text().strip().splitlines()[0])
        task = rec.get("task")
        try:
            if task.startswith("Curated_Tier1:"):
                row = score_curated(run_dir, task)
            else:
                row = score_controlled(run_dir, task)
        except Exception as exc:  # noqa: BLE001 - scoring must not kill the sweep
            row = {"task": task, "evaluator": "ERROR", "exact_success": False,
                   "error": f"{type(exc).__name__}: {exc}"[:300]}
        row.update({"ledger": "CORRECTNESS_ROWS.jsonl", "run_name": run_dir.name,
                    "model": rec.get("model"), "run_status": rec.get("status")})
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
