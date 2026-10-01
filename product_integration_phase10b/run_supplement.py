"""Versioned same-run split of the material P3−P2 config/classifier/setup cost."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import time
from pathlib import Path

from run_attribution import (HERE, HELPER, OBSERVER, PYTHON, TIMEOUT, b3,
                             clean_env, population)

ARMS = ("S0", "S1", "S2", "S3")
SEED = (20260928 ^ 0x10B) ^ 0x52
BOOTSTRAPS = {"S0": HERE / "minimal_bootstrap",
              "S1": HERE / "config_only_bootstrap",
              "S2": HERE / "config_classifier_bootstrap",
              "S3": Path("/tmp/librecalc-phase10-clean/lib/python3.13/site-packages/librecalc_agent/_bootstrap")}


def order(key: str) -> list[str]:
    values = list(ARMS)
    random.Random(SEED ^ int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)).shuffle(values)
    return values


def run_arm(row: dict, arm: str, base: Path) -> dict:
    work = base / "work"
    b3.stage(row, work)
    cache = base / "xdg/librecalc-agent"
    runs = cache / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    cmd = [str(OBSERVER), str(PYTHON), str(work / "workload.py"), str(work),
           str(cache), str(runs), str(BOOTSTRAPS[arm]), str(HELPER)]
    start = time.perf_counter_ns()
    try:
        proc = subprocess.run(cmd, cwd=work, env=clean_env(base),
                              capture_output=True, timeout=TIMEOUT)
        wall_ns = time.perf_counter_ns() - start
        code, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        wall_ns = time.perf_counter_ns() - start
        code, out, err, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
    pointer = json.loads((runs / "last_run.json").read_text())
    run_dir = Path(pointer["run_dir"])
    receipt = json.loads((run_dir / "observer_receipt.json").read_text())
    setup_path = run_dir / "setup.json"
    setup = json.loads(setup_path.read_text()) if setup_path.exists() else {}
    return {"workload_id": row["workload_id"], "arm": arm, "wall_ns": wall_ns,
            "exit_code": code, "timed_out": timed_out, "stdout": out, "stderr": err,
            "files_after": b3.files_after(work), "workdir": str(work),
            "run_dir": str(run_dir), "observer": receipt, "setup": setup,
            "route": setup.get("route")}


def append(name: str, row: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def score() -> None:
    for name in ("supplement_raw_timings.jsonl", "supplement_correctness.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"Supplemental ledger already exists: {name}")
    for pos, row in enumerate(population(), 1):
        for rep in (1, 2):
            for invocation in (1, 2):
                results = {}
                for arm in order(f"{row['workload_id']}:{rep}:{invocation}"):
                    base = HERE / "supplement_runs" / row["workload_id"] / str(rep) / arm.lower()
                    result = run_arm(row, arm, base)
                    results[arm] = result
                    append("supplement_raw_timings.jsonl", {"rep": rep,
                            "invocation": invocation, **{k: v for k, v in result.items()
                            if k not in {"stdout", "stderr", "files_after", "observer", "setup"}}})
                checks = {arm: b3.compare(results["S0"], results[arm])
                          for arm in ARMS[1:]}
                valid = (all(x["classification"] in {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
                             for x in checks.values())
                         and all(not x["timed_out"] and x["exit_code"] == 0
                                 and x["observer"].get("assurance_status") == "PASS"
                                 for x in results.values())
                         and results["S3"]["route"] == "REFERENCE_FAST_PATH"
                         and results["S3"]["setup"].get("artifacts") == {})
                verdict = {"workload_id": row["workload_id"], "rep": rep,
                           "invocation": invocation, "checks": checks, "valid": valid}
                append("supplement_correctness.jsonl", verdict)
                if not valid:
                    raise RuntimeError(f"Supplement correctness failure: {verdict}")
        print(f"supplement {pos}/22 {row['workload_id']}", flush=True)


if __name__ == "__main__":
    score()
