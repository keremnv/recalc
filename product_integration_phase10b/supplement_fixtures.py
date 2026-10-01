"""Unscored semantic gate for S1/S2 attribution-only bootstraps."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import openpyxl

from process_fixtures import FIXTURES
from run_attribution import HERE, HELPER, OBSERVER, PYTHON, clean_env
from run_supplement import ARMS, BOOTSTRAPS

CASES = ("module_argv_path", "uncaught_exception", "atexit_write",
         "abrupt_exit_after_write", "reference_objects")


def one(name: str, arm: str, root: Path) -> dict:
    base = root / name / arm.lower()
    work = base / "work"
    work.mkdir(parents=True)
    book = openpyxl.Workbook()
    book.active["A1"] = 1
    book.save(work / "input.xlsx")
    (work / "workload.py").write_text(FIXTURES[name])
    cache = base / "xdg/librecalc-agent"
    runs = cache / "runs"
    runs.mkdir(parents=True)
    cmd = [str(OBSERVER), str(PYTHON), str(work / "workload.py"), str(work),
           str(cache), str(runs), str(BOOTSTRAPS[arm]), str(HELPER)]
    proc = subprocess.run(cmd, cwd=work, env=clean_env(base), capture_output=True, timeout=20)
    run_dir = Path(json.loads((runs / "last_run.json").read_text())["run_dir"])
    receipt = json.loads((run_dir / "observer_receipt.json").read_text())
    setup_path = run_dir / "setup.json"
    setup = json.loads(setup_path.read_text()) if setup_path.exists() else {}
    return {"exit": proc.returncode, "out": proc.stdout,
            "err": proc.stderr, "value": openpyxl.load_workbook(work / "input.xlsx").active["A1"].value,
            "receipt": receipt, "setup": setup}


def main() -> None:
    ledger = HERE / "supplement_process_semantics.jsonl"
    if ledger.exists():
        raise RuntimeError("Supplement process ledger exists")
    with tempfile.TemporaryDirectory(prefix="phase10b-supplement-fixtures-") as d:
        root = Path(d)
        for name in CASES:
            results = {arm: one(name, arm, root) for arm in ARMS}
            ref = results["S0"]
            for arm, result in results.items():
                valid = (result["exit"] == ref["exit"] and result["out"] == ref["out"]
                         and result["value"] == ref["value"]
                         and result["receipt"].get("assurance_status") == "PASS")
                if name != "uncaught_exception":
                    valid = valid and result["err"] == ref["err"]
                else:
                    valid = valid and b"RuntimeError: expected" in result["err"]
                if arm == "S3":
                    valid = valid and result["setup"].get("route") == "REFERENCE_FAST_PATH"
                with ledger.open("a") as stream:
                    stream.write(json.dumps({"fixture": name, "arm": arm,
                                             "valid": valid, "exit": result["exit"],
                                             "value": result["value"]}, sort_keys=True) + "\n")
                if not valid:
                    raise RuntimeError(f"Supplement process fixture failed: {name} {arm}")
            print(f"supplement fixture {name}: S0–S3 exact", flush=True)


if __name__ == "__main__":
    main()
