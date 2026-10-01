"""Prepare resumable GLM retrieval ledgers without discarding valid episodes."""

from __future__ import annotations

import json
from pathlib import Path

from relational_retrieval_probe import retrieval_population


ARMS = (
    "A_TYPED_API_STRONG_CONTEXT",
    "B_SQL_STRONG_CONTEXT",
    "C_SQL_BARE_SCHEMA",
)


def valid(record: dict) -> bool:
    calls = record.get("calls") or []
    return bool(calls) and all(call.get("model_ok") for call in calls)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/relational-retrieval-probe"
    for arm in ARMS:
        prefix = arm[0].lower()
        sources = [root / f"glm_shards_{prefix}1.jsonl"] + sorted(root.glob(f"glm_pending_{prefix}*.jsonl"))
        by_target: dict[str, dict] = {}
        for source in sources:
            if not source.exists():
                continue
            for line in source.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("arm") == arm and valid(record):
                    by_target.setdefault(record["target_job_id"], record)
        output = root / f"glm_retry_{prefix}.jsonl"
        with output.open("w", encoding="utf-8") as handle:
            for target_id in sorted(by_target):
                handle.write(json.dumps(by_target[target_id], ensure_ascii=False) + "\n")
        print(f"{arm}: preserved_valid={len(by_target)} ledger={output}")

    # Controlled-size continuation: use A's valid target IDs so all arms remain matched.
    population_ids = [row["target_job_id"] for row in retrieval_population()]
    a_ledger = root / "glm_retry_a.jsonl"
    a_targets = {
        json.loads(line)["target_job_id"]
        for line in a_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    matched_population_ids = [target_id for target_id in population_ids if target_id in a_targets]
    for prefix, target_count in (("b", 220), ("c", 220)):
        ledger = root / f"glm_retry_{prefix}.jsonl"
        existing = {
            json.loads(line)["target_job_id"]
            for line in ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        existing_matched = len(existing & set(matched_population_ids))
        selected = [target_id for target_id in matched_population_ids if target_id not in existing][: max(0, target_count - existing_matched)]
        ids_path = root / f"glm_retry_{prefix}_target_ids.txt"
        ids_path.write_text("\n".join(selected) + "\n", encoding="utf-8")
        print(f"{prefix.upper()}: selected_new={len(selected)} target_id_file={ids_path}")


if __name__ == "__main__":
    main()
