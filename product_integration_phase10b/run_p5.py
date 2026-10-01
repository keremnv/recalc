"""Same-run P4/P5 bounded-treatment score on exact frozen reference-only scripts."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import time
from pathlib import Path

from run_attribution import (CONSOLE, HERE, PYTHON, TIMEOUT, b3,
                             clean_env, population)
from p5_fixtures import P5_CONSOLE, P5_PYTHON

ARMS = ("PY_OLD", "PY_NEW", "P4", "P5")
SEED = (20260928 ^ 0x10B) ^ 0x55


def order(key: str) -> list[str]:
    values = list(ARMS)
    random.Random(SEED ^ int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)).shuffle(values)
    return values


def run_arm(row: dict, arm: str, base: Path) -> dict:
    work = base / "work"
    b3.stage(row, work)
    target = work / "workload.py"
    if arm == "PY_OLD":
        cmd = [str(PYTHON), str(target)]
    elif arm == "PY_NEW":
        cmd = [str(P5_PYTHON), str(target)]
    else:
        cmd = [str(CONSOLE if arm == "P4" else P5_CONSOLE),
               "run", "--workdir", str(work), str(target)]
    start = time.perf_counter_ns()
    try:
        proc = subprocess.run(cmd, cwd=work, env=clean_env(base),
                              capture_output=True, timeout=TIMEOUT)
        wall_ns = time.perf_counter_ns() - start
        code, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        wall_ns = time.perf_counter_ns() - start
        code, out, err, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
    result = {"workload_id": row["workload_id"], "arm": arm, "wall_ns": wall_ns,
              "exit_code": code, "timed_out": timed_out,
              "stdout": out, "stderr": err,
              "files_after": b3.files_after(work), "workdir": str(work)}
    if arm in {"P4", "P5"}:
        pointer = base / "xdg/librecalc-agent/runs/last_run.json"
        try:
            run_dir = Path(json.loads(pointer.read_text())["run_dir"])
            observer = json.loads((run_dir / "observer_receipt.json").read_text())
            setup = json.loads((run_dir / "setup.json").read_text())
        except (OSError, ValueError, KeyError):
            run_dir, observer, setup = Path("/nonexistent"), {}, {}
        result.update({"run_dir": str(run_dir), "observer": observer,
                       "setup": setup, "route": setup.get("route"),
                       "negative_proof": setup.get("negative_proof")})
    return result


def append(name: str, item: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(item, sort_keys=True, default=str) + "\n")


def score() -> None:
    for name in ("p5_raw_timings.jsonl", "p5_correctness.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"P5 score ledger exists: {name}")
    coverage = json.loads((HERE / "p5_coverage.json").read_text())
    quick = set(coverage["quick_negative_ids"])
    assert len(quick) == 20
    for pos, row in enumerate(population(), 1):
        for rep in (1, 2):
            for invocation in (1, 2):
                results = {}
                for arm in order(f"{row['workload_id']}:{rep}:{invocation}"):
                    base = HERE / "p5_runs" / row["workload_id"] / str(rep) / arm.lower()
                    result = run_arm(row, arm, base)
                    results[arm] = result
                    append("p5_raw_timings.jsonl", {"rep": rep,
                        "invocation": invocation, **{k: v for k, v in result.items()
                        if k not in {"stdout", "stderr", "files_after", "observer", "setup"}}})
                checks = {arm: b3.compare(results["PY_OLD"], results[arm])
                          for arm in ARMS[1:]}
                witness_ok = ((results["P5"]["negative_proof"] == "FROZEN_A0_LEXICAL_BLOCKER")
                              == (row["workload_id"] in quick))
                valid = (all(x["classification"] in {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
                             for x in checks.values())
                         and all(not x["timed_out"] and x["exit_code"] == 0
                                 for x in results.values())
                         and all(results[arm]["observer"].get("assurance_status") == "PASS"
                                 and results[arm]["route"] == "REFERENCE_FAST_PATH"
                                 and results[arm]["setup"].get("artifacts") == {}
                                 for arm in ("P4", "P5"))
                         and witness_ok)
                verdict = {"workload_id": row["workload_id"], "rep": rep,
                           "invocation": invocation, "checks": checks,
                           "quick_negative_witness_ok": witness_ok, "valid": valid}
                append("p5_correctness.jsonl", verdict)
                if not valid:
                    raise RuntimeError(f"P5 correctness gate failed: {verdict}")
        print(f"P5 reference-only {pos}/22 {row['workload_id']}", flush=True)


if __name__ == "__main__":
    score()
