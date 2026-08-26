import json

import pytest

from benchmark.experiment_metrics import (
    append_record,
    generation_ids,
    generation_metrics,
    read_records,
    summarize,
    trajectory_metrics,
)


def test_trajectory_metrics_extracts_model_and_tool_usage(tmp_path) -> None:
    trajectory = tmp_path / "task.traj"
    trajectory.write_text(
        json.dumps(
            {
                "info": {
                    "model_stats": {
                        "instance_cost": 0.012,
                        "tokens_sent": 1200,
                        "tokens_received": 300,
                        "api_calls": 4,
                    }
                },
                "trajectory": [{"action": "inspect"}, {"action": ""}, {"action": "write"}],
            }
        ),
        encoding="utf-8",
    )

    assert trajectory_metrics(trajectory) == {
        "harness_estimated_cost_usd": 0.012,
        "harness_prompt_tokens": 1200,
        "harness_completion_tokens": 300,
        "model_calls": 4,
        "tool_calls": 2,
    }


def test_generation_ids_and_authoritative_usage(tmp_path) -> None:
    debug_log = tmp_path / "task.debug.log"
    debug_log.write_text(
        "Response(id='gen-one')\nResponse(id='gen-two')\nDuplicate(id='gen-one')\n",
        encoding="utf-8",
    )

    assert generation_ids(debug_log) == ["gen-one", "gen-two"]
    assert generation_metrics(
        [
            {
                "native_tokens_prompt": 100,
                "native_tokens_completion": 20,
                "native_tokens_reasoning": 5,
                "total_cost": 0.001,
            },
            {
                "tokens_prompt": 40,
                "tokens_completion": 10,
                "usage": 0.002,
                "native_tokens_cached": 32,
            },
        ]
    ) == {
        "generation_records": 2,
        "generation_cost_usd": pytest.approx(0.003),
        "prompt_tokens": 140,
        "completion_tokens": 30,
        "reasoning_tokens": 5,
        # Cache hits are measured, not inferred from charged-vs-catalog price.
        "cached_prompt_tokens": 32,
    }


def test_append_read_and_cost_first_summary(tmp_path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    append_record(
        ledger,
        {"task": "A", "status": "completed", "exact_success": True, "charged_cost_usd": 0.01},
    )
    append_record(
        ledger,
        {"task": "B", "status": "failed", "exact_success": False, "charged_cost_usd": 0.02},
    )

    records = read_records(ledger)
    assert [record["task"] for record in records] == ["A", "B"]
    assert summarize(records) == {
        "tasks": 2,
        "completed": 1,
        "scored": 2,
        "successful": 1,
        "charged_cost_usd": pytest.approx(0.03),
        "completion_rate": 0.5,
        "success_rate": 0.5,
        "cost_per_success_usd": pytest.approx(0.03),
    }


def test_unscored_summary_does_not_claim_a_success_rate() -> None:
    summary = summarize([{"status": "completed", "exact_success": None, "charged_cost_usd": 0.01}])
    assert summary["success_rate"] is None
    assert summary["cost_per_success_usd"] is None
