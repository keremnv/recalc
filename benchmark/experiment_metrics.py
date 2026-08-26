"""Stable records and summaries for LibreCalc benchmark experiments."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def trajectory_metrics(path: Path) -> dict[str, int | float]:
    """Extract secondary model and tool metrics from a SWE-agent trajectory."""
    data = json.loads(path.read_text(encoding="utf-8"))
    info = data.get("info", {})
    stats = info.get("model_stats", {})
    trajectory = data.get("trajectory", [])
    return {
        "harness_estimated_cost_usd": float(stats.get("instance_cost", 0.0)),
        "harness_prompt_tokens": int(stats.get("tokens_sent", 0)),
        "harness_completion_tokens": int(stats.get("tokens_received", 0)),
        "model_calls": int(stats.get("api_calls", 0)),
        "tool_calls": sum(bool(step.get("action")) for step in trajectory),
    }


def generation_ids(path: Path) -> list[str]:
    """Return OpenRouter generation IDs from a SWE-agent debug log in request order."""
    values = re.findall(r"id='(gen-[A-Za-z0-9_-]+)'", path.read_text(encoding="utf-8"))
    return list(dict.fromkeys(values))


def generation_metrics(metadata: Iterable[dict[str, Any]]) -> dict[str, int | float]:
    """Aggregate authoritative OpenRouter usage metadata for individual generations."""
    rows = list(metadata)
    return {
        "generation_records": len(rows),
        "generation_cost_usd": sum(
            float(row.get("total_cost", row.get("usage", 0.0))) for row in rows
        ),
        "prompt_tokens": sum(
            int(row.get("native_tokens_prompt") or row.get("tokens_prompt") or 0) for row in rows
        ),
        "completion_tokens": sum(
            int(row.get("native_tokens_completion") or row.get("tokens_completion") or 0)
            for row in rows
        ),
        "reasoning_tokens": sum(int(row.get("native_tokens_reasoning") or 0) for row in rows),
        # Measure the cache hit rate instead of inferring it by dividing charged cost
        # by catalog price. Providers differ in which field they populate.
        "cached_prompt_tokens": sum(
            int(row.get("native_tokens_cached") or row.get("cached_tokens") or 0) for row in rows
        ),
    }


def append_record(path: Path, record: dict[str, Any]) -> None:
    """Append one durable JSON record without rewriting earlier experiment data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path}:{line_number} is not a JSON object")
            records.append(value)
    return records


def summarize(records: Iterable[dict[str, Any]]) -> dict[str, int | float | None]:
    """Compute the cost-first scoreboard for a collection of task records."""
    rows = list(records)
    completed = sum(row.get("status") == "completed" for row in rows)
    successful = sum(row.get("exact_success") is True for row in rows)
    scored = sum(isinstance(row.get("exact_success"), bool) for row in rows)
    charged_cost = sum(float(row.get("charged_cost_usd", 0.0)) for row in rows)
    return {
        "tasks": len(rows),
        "completed": completed,
        "scored": scored,
        "successful": successful,
        "charged_cost_usd": charged_cost,
        "completion_rate": completed / len(rows) if rows else None,
        "success_rate": successful / scored if scored else None,
        "cost_per_success_usd": charged_cost / successful if successful else None,
    }
