"""The per-task join: failure taxonomy and the usable-output metric."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "benchmark/run_report.py"
    spec = importlib.util.spec_from_file_location("benchmark_run_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["benchmark_run_report"] = module
    spec.loader.exec_module(module)
    return module


def _write_run(root: Path, rows: list[dict], scores: dict) -> Path:
    run = root / "a-run"
    run.mkdir()
    (run / "ledger.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    (run / "official_scores.json").write_text(json.dumps({"tasks": scores}))
    return run


def test_usable_separates_a_near_miss_from_a_real_failure(tmp_path) -> None:
    """Exact is 0 for both; only one is a deliverable a person would accept."""
    report = _module()
    rows = [
        {"task": "Template:05_01", "category": "Template", "task_id": "05_01",
         "status": "completed", "model_calls": 8, "call_limit": 12, "charged_cost_usd": 0.003},
        {"task": "Template:06_24", "category": "Template", "task_id": "06_24",
         "status": "completed", "model_calls": 8, "call_limit": 12, "charged_cost_usd": 0.001},
    ]
    scores = {
        "Template:05_01": {"accuracy": 0.0, "regression_accuracy": 0.9942,
                           "modification_accuracy": 1.0,
                           "error_message": "Regression error at DeferredTax!C23: answer=None"},
        "Template:06_24": {"accuracy": 0.0, "regression_accuracy": 0.9322,
                           "modification_accuracy": 0.3590,
                           "error_message": "Regression error at RevenueBuild!G11: answer=None"},
    }
    run = _write_run(tmp_path, rows, scores)
    for row in rows:
        (run / f"{row['category']}-{row['task_id']}").mkdir()
        (run / f"{row['category']}-{row['task_id']}" / "output.xlsx").write_bytes(b"x")

    collected = {row["task"]: row for row in report.collect(run)}

    assert collected["Template:05_01"]["exact"] is False
    assert collected["Template:05_01"]["usable"] is True
    assert collected["Template:06_24"]["usable"] is False
    # The first miss is parsed into a kind and an address, not left as prose.
    assert collected["Template:05_01"]["first_miss_kind"] == "regression"
    assert collected["Template:05_01"]["first_miss_address"] == "DeferredTax!C23"
    assert collected["Template:05_01"]["failure_mode"] == "wrote_regression_first"


def test_failure_modes_separate_the_ways_a_run_produces_nothing() -> None:
    report = _module()
    base = {"exact": False, "has_workbook": False, "wrote": False, "call_limit": 12}

    assert report._failure_mode({**base, "transport_400": True}) == "no_workbook_transport"
    assert report._failure_mode({**base, "return_code": 124}) == "no_workbook_timeout"
    assert (
        report._failure_mode({**base, "empty_completions": 3}) == "no_workbook_format_exit"
    )
    assert report._failure_mode({**base, "model_calls": 12}) == "no_workbook_call_cap"
    assert report._failure_mode({"exact": True}) == "exact"
