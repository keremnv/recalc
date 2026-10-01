"""Focused unchanged-artifact lifecycle checks for the Phase-7 overlay."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import openpyxl


def run(pop: dict, append: Callable[[dict], None]) -> bool:
    from read_engine_phase7 import benchmark as bench

    wid = "Debugging_01_06__7b42a0f86b41"
    row = next(x for x in pop["workloads"] if x["workload_id"] == wid)
    base = bench.HERE / "runs/lifecycle" / wid / "h1"
    shutil.rmtree(base, ignore_errors=True)

    def check(case: str, selected: dict, status: str) -> tuple[dict, bool]:
        result = bench.command(selected, "H1", base)
        entries = list((result["summary"] or {}).get("artifacts", {}).values())
        observed = entries[0].get("status") if len(entries) == 1 else None
        passed = (result["exit_code"] == 0 and observed == status
                  and result["summary"].get("direct_served_loads", 0) > 0
                  and not result["summary"].get("reference_reasons")
                  and result["summary"].get("observer_receipt", {}).get("capture_helper_exit") == 0)
        append({"kind": "lifecycle", "case": case, "workload_id": wid,
                "expected_status": status, "status": observed,
                "direct_served_loads": result["summary"].get("direct_served_loads"),
                "reference_reasons": result["summary"].get("reference_reasons"),
                "passed": passed})
        return result, passed

    first, ok = check("missing_artifact", row, "BUILT")
    if not ok:
        return False
    second, ok = check("valid_reuse", row, "REUSED")
    if not ok:
        return False
    artifact = Path(next(iter(second["summary"]["artifacts"].values()))["artifact_path"])
    artifact.write_bytes(artifact.read_bytes()[:20])
    _, ok = check("truncated_artifact", row, "BUILT")
    if not ok:
        return False

    mutated = bench.HERE / "runs/lifecycle/mutated_source.xlsx"
    wb = openpyxl.load_workbook(row["source_workbook_path"], data_only=False)
    wb.worksheets[0]["Z100"] = "PHASE7_FRESHNESS_GENERATION"
    wb.save(mutated)
    wb.close()
    alternate = dict(row, source_workbook_path=str(mutated),
                     source_workbook_sha256=bench.sha(mutated), staged_workbook_sha256=bench.sha(mutated))
    changed, ok = check("same_path_changed_bytes", alternate, "BUILT")
    if not ok:
        return False
    old_hash = next(iter(first["summary"]["artifacts"].values()))["source_sha256"]
    new_hash = next(iter(changed["summary"]["artifacts"].values()))["source_sha256"]
    if old_hash == new_hash:
        append({"kind": "lifecycle", "case": "hash_change", "passed": False})
        return False
    _, ok = check("restored_original_bytes", row, "REUSED")
    return ok
