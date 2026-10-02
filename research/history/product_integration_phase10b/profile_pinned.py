"""Summarize diagnostic observer timers for the CPU-pinned attribution run."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def summarize(values: list[float]) -> dict:
    return {"count": len(values), "median": statistics.median(values),
            "min": min(values), "max": max(values)}


def main() -> None:
    output = {}
    for ledger in ("raw_timings.jsonl", "p5_raw_timings.jsonl"):
        groups: dict[str, dict[str, list[float]]] = {}
        for line in (HERE / ledger).read_text().splitlines():
            row = json.loads(line)
            if row["invocation"] != 2 or row["arm"] in {"P0", "PY_OLD", "PY_NEW"}:
                continue
            run_dir = row.get("run_dir")
            if run_dir is None:
                continue
            receipt = json.loads((Path(run_dir) / "observer_receipt.json").read_text())
            group = groups.setdefault(row["arm"], {})
            for name, ns in receipt["profile_ns"].items():
                group.setdefault(name, []).append(ns / 1e6)
            group.setdefault("external_wall_minus_observer_profile", []).append(
                row["wall_ns"] / 1e6 - receipt["profile_ns"]["observer_to_receipt"] / 1e6)
        output[ledger] = {arm: {name: summarize(values) for name, values in timers.items()}
                          for arm, timers in groups.items()}
    output["note"] = "Nested diagnostic timers; full-command paired differences in analysis.json are causal authority."
    output["affinity_cpu"] = 1
    output["environment"] = json.loads((HERE / "environment.json").read_text())
    output["affinity_identity"] = json.loads((HERE / "affinity_identity.json").read_text())
    (HERE / "profile.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
