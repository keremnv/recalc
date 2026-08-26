#!/usr/bin/env python3
"""Score Visualization outputs with OpenRouter GLM-4.6V (OpenAI-compatible vision).

Uses the official SpreadsheetBench VLM checklist evaluator. Checklist text comes from
each task's criteria in dataset.json — same context as the default BigModel path;
only the API endpoint/model/key change.

Requires either PNG outputs (Linux-friendly) or XLSX + Windows Excel/WPS COM export.

Example:
  uv run python benchmark/score_visualization_openrouter.py \\
    --output-dir path/to/outputs \\
    --task-ids "Task 1411527"
"""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
EVAL_SCRIPT = DEFAULT_BENCHMARK_ROOT / "evaluation" / "run_visual_vlm_checklist_eval.py"
DEFAULT_TASKS = DEFAULT_BENCHMARK_ROOT / "data" / "Visualization" / "dataset.json"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "z-ai/glm-4.6v"


def _load_dotenv(path: Path = DEFAULT_ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--tasks-json", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--task-ids", nargs="*", default=None)
    parser.add_argument("--report-path", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=OPENROUTER_BASE_URL)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--export-dir", default=None)
    parser.add_argument("--acc-threshold", type=float, default=0.7)
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("VLM_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENROUTER_API_KEY (or VLM_API_KEY / --api-key)")
    if not EVAL_SCRIPT.is_file():
        raise SystemExit(f"Missing evaluator: {EVAL_SCRIPT}")

    argv = [
        str(EVAL_SCRIPT),
        "--tasks-json",
        str(args.tasks_json.resolve()),
        "--output-dir",
        str(args.output_dir.resolve()),
        "--api-key",
        api_key,
        "--base-url",
        args.base_url,
        "--model",
        args.model,
        "--acc-threshold",
        str(args.acc_threshold),
    ]
    if args.task_ids:
        argv.extend(["--task-ids", *args.task_ids])
    if args.report_path:
        argv.extend(["--report-path", str(Path(args.report_path).resolve())])
    if args.export_dir:
        argv.extend(["--export-dir", str(Path(args.export_dir).resolve())])

    sys.argv = argv
    runpy.run_path(str(EVAL_SCRIPT), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
