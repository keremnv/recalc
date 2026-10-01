"""Post-score warm timing check on seven preregistered direct-contact controls."""
from __future__ import annotations

import json
import statistics

from p5_regressions import HERE, ROOT, b3, run_arm


def main() -> None:
    original = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    routes = json.loads((ROOT / "product_integration_phase10/analysis.json").read_text())["route_by_workload"]
    by_id = {row["workload_id"]: row for row in original["workloads"]}
    ids = [wid for wid in original["secondary_ids"] if routes[wid] == "DIRECT_CONTACT"]
    assert len(ids) == 7
    output = HERE / "p5_direct_contact_timing.jsonl"
    if output.exists():
        raise RuntimeError(f"Already exists: {output}")
    ratios = []
    for wid in ids:
        results = {arm: run_arm(by_id[wid], arm,
                   HERE / "p5_regression_runs/direct" / wid / arm.lower())
                   for arm in ("P4", "P5")}
        valid = all(results[a]["route"] == "DIRECT_RUNTIME"
                    and results[a]["observer"].get("assurance_status") == "PASS"
                    and sorted({x.get("status") for x in
                                (results[a]["setup"].get("artifacts") or {}).values()}) == ["REUSED"]
                    for a in ("P4", "P5"))
        if not valid:
            raise RuntimeError(f"Warm direct control failed: {wid}")
        ratio = results["P5"]["wall_ns"] / results["P4"]["wall_ns"]
        ratios.append(ratio)
        with output.open("a") as stream:
            stream.write(json.dumps({"workload_id": wid, "ratio": ratio,
                "P4_wall_ns": results["P4"]["wall_ns"],
                "P5_wall_ns": results["P5"]["wall_ns"], "valid": valid}) + "\n")
    print(json.dumps({"count": len(ids), "median_P5_P4": statistics.median(ratios)}))


if __name__ == "__main__":
    main()
