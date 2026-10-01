"""Unscored exact fixed-22 cold/reuse regression after semantic hardening."""
from __future__ import annotations

import json
from pathlib import Path

from read_engine_phase3 import benchmark as b3
from read_engine_phase6 import benchmark as b6
from read_engine_phase7 import benchmark as b7

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "overlay"
TARGETS = {"Debugging_01_06__7b42a0f86b41",
           "Debugging_05_02__9e6b464d2158",
           "Financial_Model_08_03__59b98508fd79"}


def hardened(row: dict, base: Path) -> dict:
    original = b6.ROOT
    try:
        b6.ROOT = OVERLAY
        result = b6.command(row, "H2", base)
    finally:
        b6.ROOT = original
    last = base / "runs/last_run.json"
    if last.exists():
        run = Path(json.loads(last.read_text())["run_dir"])
        setup = run / "setup.json"
        if setup.exists():
            result["certificate"] = json.loads(setup.read_text()).get("merged_certificate")
    return result


def compact(result: dict) -> dict:
    summary = result.get("summary") or {}
    return {"exit_code": result["exit_code"], "wall_ns_diagnostic_only": result["wall_ns"],
            "artifact_status": [x.get("status") for x in summary.get("artifacts", {}).values()],
            "direct_served_loads": summary.get("direct_served_loads"),
            "fallback_reasons": summary.get("reference_reasons"),
            "merged_direct": sum(e.get("event") == "merged_child_direct" for e in result["events"]),
            "merged_reference": sum(e.get("event") == "merged_child_reference" for e in result["events"]),
            "capture_helper_exit": (summary.get("observer_receipt") or {}).get("capture_helper_exit"),
            "certificate": result.get("certificate")}


def main() -> None:
    b7.verify()
    pop = b6.verify()
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    out = HERE / "fixed22_correctness.jsonl"
    if out.exists():
        raise RuntimeError("fixed22 ledger exists")
    with out.open("w") as stream:
        for pos, wid in enumerate(pop["primary_ids"], 1):
            row = by_id[wid]
            base = HERE / "runs/fixed22" / wid
            for invocation in (1, 2):
                results = {"PY": b7.command(row, "PY", base / "py"),
                           "PHASE7": b7.command(row, "H1", base / "phase7"),
                           "HARDENED": hardened(row, base / "hardened")}
                checks = {name: b3.compare(results["PY"], results[name])
                          for name in ("PHASE7", "HARDENED")}
                old, new = compact(results["PHASE7"]), compact(results["HARDENED"])
                expected = ["BUILT"] if invocation == 1 else ["REUSED"]
                valid = (all(x["classification"] == "EXACT" for x in checks.values())
                         and old["artifact_status"] == new["artifact_status"] == expected
                         and old["direct_served_loads"] == new["direct_served_loads"]
                         and new["merged_direct"] <= old["merged_direct"]
                         and old["capture_helper_exit"] == new["capture_helper_exit"] == 0
                         and results["PY"]["exit_code"] == 0)
                if wid in TARGETS:
                    valid = valid and new["certificate"]["certified"] \
                        and new["merged_direct"] == old["merged_direct"] > 0
                record = {"workload_id": wid, "invocation": invocation,
                          "regime": "COLD" if invocation == 1 else "REUSED",
                          "checks": checks, "phase7": old, "hardened": new, "valid": valid}
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                stream.flush()
                print(f"{pos}/22 {wid} invocation={invocation} valid={valid}", flush=True)
                if not valid:
                    raise RuntimeError(f"fixed22 semantic regression: {wid} {invocation}")


if __name__ == "__main__":
    main()
