"""Post-P5 direct-contact and changed-file correctness controls."""
from __future__ import annotations

import json
from pathlib import Path

from run_attribution import HERE, ROOT, b3
from run_p5 import run_arm
from read_engine_phase8a import validation_runner as p8


def append(name: str, item: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(item, sort_keys=True, default=str) + "\n")


def main() -> None:
    for name in ("p5_direct_contact_regression.jsonl", "p5_changed_file_regression.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"Regression ledger exists: {name}")
    original = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    routes = json.loads((ROOT / "research/history/product_integration_phase10/analysis.json").read_text())["route_by_workload"]
    by_id = {row["workload_id"]: row for row in original["workloads"]}
    direct_ids = [wid for wid in original["secondary_ids"] if routes[wid] == "DIRECT_CONTACT"]
    assert len(direct_ids) == 7
    for wid in direct_ids:
        row = by_id[wid]
        for invocation in (1, 2):
            results = {arm: run_arm(row, arm,
                       HERE / "p5_regression_runs/direct" / wid / arm.lower())
                       for arm in ("PY_OLD", "P4", "P5")}
            checks = {arm: b3.compare(results["PY_OLD"], results[arm])
                      for arm in ("P4", "P5")}
            expected = "BUILT" if invocation == 1 else "REUSED"
            states = {arm: sorted({x.get("status") for x in
                                  (results[arm]["setup"].get("artifacts") or {}).values()})
                      for arm in ("P4", "P5")}
            valid = (all(x["classification"] in {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
                         for x in checks.values())
                     and all(results[a]["exit_code"] == 0 for a in results)
                     and all(results[a]["route"] == "DIRECT_RUNTIME"
                             and results[a]["observer"].get("assurance_status") == "PASS"
                             and states[a] == [expected] for a in ("P4", "P5")))
            append("p5_direct_contact_regression.jsonl",
                   {"workload_id": wid, "invocation": invocation,
                    "checks": checks, "artifact_statuses": states, "valid": valid})
            if not valid:
                raise RuntimeError(f"Direct-contact P5 regression: {wid} {invocation}")
        print(f"direct-contact {wid}: exact build/reuse", flush=True)

    for name in p8.FIXTURE_NAMES:
        script = ROOT / "read_engine_phase8/changed_file_fixtures" / f"{name}.py"
        row = {"workload_id": "phase8_changed_" + name,
               "script_path": str(script), "script_sha256": b3.safe_artifact.sha_file(script),
               "source_workbook_path": str(p8.FIXTURE_BOOK),
               "source_workbook_sha256": b3.safe_artifact.sha_file(p8.FIXTURE_BOOK),
               "staged_workbook_sha256": b3.safe_artifact.sha_file(p8.FIXTURE_BOOK)}
        results = {arm: run_arm(row, arm,
                   HERE / "p5_regression_runs/changed" / name / arm.lower())
                   for arm in ("PY_OLD", "P4", "P5")}
        package = {arm: p8.package_relation(results["PY_OLD"], results[arm])[0]
                   for arm in ("P4", "P5")}
        captures = {}
        for arm in ("P4", "P5"):
            state_path = Path(results[arm]["run_dir"]) / "capture_state.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            captures[arm] = {"changed_xlsx": results[arm]["observer"].get("changed_xlsx"),
                             "helper_exit": results[arm]["observer"].get("capture_helper_exit"),
                             "validation_passed": state.get("validation_passed")}
        valid = (all(results[a]["exit_code"] == 0 for a in results)
                 and all(package.values())
                 and all((results[arm]["stdout"], results[arm]["stderr"]) ==
                         (results["PY_OLD"]["stdout"], results["PY_OLD"]["stderr"])
                         for arm in ("P4", "P5"))
                 and all(captures[a] == {"changed_xlsx": 1, "helper_exit": 0,
                                         "validation_passed": True}
                         for a in ("P4", "P5")))
        append("p5_changed_file_regression.jsonl",
               {"workload_id": row["workload_id"], "package_relation": package,
                "capture": captures, "valid": valid})
        if not valid:
            raise RuntimeError(f"Changed-file P5 regression: {name}")
        print(f"changed-file {name}: exact effect/capture", flush=True)


if __name__ == "__main__":
    main()
