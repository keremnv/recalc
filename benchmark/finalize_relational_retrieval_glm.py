"""Create the matched, valid GLM retrieval ledgers and run the frozen report."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MECHANICAL = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical"
SOURCE = MECHANICAL / "relational-retrieval-probe"
DEST = MECHANICAL / "relational-retrieval-probe-glm-final-matched"
ARMS = {
    "A_TYPED_API_STRONG_CONTEXT": "a",
    "B_SQL_STRONG_CONTEXT": "b",
    "C_SQL_BARE_SCHEMA": "c",
}


def records(path: Path) -> list[dict]:
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("calls") and all(call.get("model_ok") for call in row["calls"]):
            result.append(row)
    return result


def main() -> None:
    a_records = records(SOURCE / "glm_retry_a.jsonl")
    matched_ids = {row["target_job_id"] for row in a_records}
    if len(matched_ids) != 220:
        raise SystemExit(f"expected 220 A target IDs, got {len(matched_ids)}")
    DEST.mkdir(parents=True, exist_ok=True)
    for name in ("freeze.json", "population.json", "database_manifest.json"):
        shutil.copy2(SOURCE / name, DEST / name)
    counts = {}
    for arm, prefix in ARMS.items():
        picked = {}
        for row in records(SOURCE / f"glm_retry_{prefix}.jsonl"):
            if row.get("arm") == arm and row["target_job_id"] in matched_ids:
                picked.setdefault(row["target_job_id"], row)
        if set(picked) != matched_ids:
            raise SystemExit(f"{arm} does not cover the matched A target set: {len(picked)}")
        output = DEST / f"calls_{arm}.jsonl"
        with output.open("w", encoding="utf-8") as handle:
            for target_id in sorted(matched_ids):
                handle.write(json.dumps(picked[target_id], ensure_ascii=False) + "\n")
        counts[arm] = len(picked)

    sys.path.insert(0, str(ROOT / "benchmark"))
    import relational_retrieval_probe as probe

    probe.OUT = DEST
    result = probe.report()
    print(json.dumps({"destination": str(DEST), "counts": counts, "verdict": result["verdict"]}, indent=2))


if __name__ == "__main__":
    main()
