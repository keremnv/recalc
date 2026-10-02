"""Fresh-process full-command P0–P4 attribution on frozen reference-only scripts."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from read_engine_phase3 import benchmark as b3

VENV = Path("/tmp/librecalc-phase10-clean")
PYTHON = VENV / "bin/python"
CONSOLE = VENV / "bin/librecalc-agent"
PACKAGE = VENV / "lib/python3.13/site-packages/librecalc_agent"
OBSERVER = PACKAGE / "native/observer"
BOOTSTRAP = PACKAGE / "_bootstrap"
HELPER = PACKAGE / "_capture_helper.py"
ARMS = ("P0", "P1", "P2", "P3", "P4")
SEED = 20260928 ^ 0x10B
TIMEOUT = 180


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def population() -> list[dict]:
    spec = json.loads((HERE / "population.json").read_text())
    rows = spec["workloads"]
    assert len(rows) == len(spec["ids"]) == 22
    assert [x["workload_id"] for x in rows] == spec["ids"]
    for row in rows:
        assert sha(Path(row["script_path"])) == row["script_sha256"]
        assert sha(Path(row["source_workbook_path"])) == row["source_workbook_sha256"]
    return rows


def arm_order(key: str) -> list[str]:
    values = list(ARMS)
    random.Random(SEED ^ int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)).shuffle(values)
    return values


def clean_env(base: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "LIBRECALC_CONFIG", "LIBRECALC_RUN_CONTEXT",
                        "LIBRECALC_EFFECTIVE_CONFIG", "LIBRECALC_NO_RUNTIME"}
           and not k.startswith("CANDIDATE_A_")}
    env["XDG_CACHE_HOME"] = str(base / "xdg")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def command(arm: str, work: Path, base: Path) -> list[str]:
    target = work / "workload.py"
    if arm == "P0":
        return [str(PYTHON), str(target)]
    if arm == "P4":
        return [str(CONSOLE), "run", "--workdir", str(work), str(target)]
    cache = base / "xdg/librecalc-agent"
    runs = cache / "runs"
    # The observer requires a parent directory; this is benchmark staging.
    # P4 charges its own launcher directory work, including repeat chmod.
    runs.mkdir(parents=True, exist_ok=True)
    bootstrap = (HERE / "empty_bootstrap" if arm == "P1" else
                 HERE / "minimal_bootstrap" if arm == "P2" else BOOTSTRAP)
    return [str(OBSERVER), str(PYTHON), str(target), str(work), str(cache),
            str(runs), str(bootstrap), str(HELPER)]


def run_arm(row: dict, arm: str, base: Path) -> dict:
    work = base / "work"
    b3.stage(row, work)
    env = clean_env(base)
    cmd = command(arm, work, base)
    start = time.perf_counter_ns()
    try:
        proc = subprocess.run(cmd, cwd=work, env=env, capture_output=True,
                              timeout=TIMEOUT, check=False)
        wall_ns = time.perf_counter_ns() - start
        code, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        wall_ns = time.perf_counter_ns() - start
        code, out, err, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
    result = {"workload_id": row["workload_id"], "arm": arm, "wall_ns": wall_ns,
              "exit_code": code, "timed_out": timed_out,
              "stdout": out, "stderr": err, "files_after": b3.files_after(work),
              "workdir": str(work), "command": cmd}
    if arm != "P0":
        pointer = base / "xdg/librecalc-agent/runs/last_run.json"
        try:
            run_dir = Path(json.loads(pointer.read_text())["run_dir"])
            receipt = json.loads((run_dir / "observer_receipt.json").read_text())
        except (OSError, ValueError, KeyError):
            run_dir, receipt = Path("/nonexistent"), {}
        setup_path = run_dir / "setup.json"
        setup = json.loads(setup_path.read_text()) if setup_path.exists() else {}
        result.update({"run_dir": str(run_dir), "observer": receipt,
                       "setup": setup, "route": setup.get("route"),
                       "artifact": setup.get("artifacts")})
    return result


def safe_row(result: dict) -> dict:
    return {k: v for k, v in result.items()
            if k not in {"stdout", "stderr", "files_after", "command", "observer", "setup"}}


def append(name: str, row: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def compare(results: dict) -> dict:
    reference = results["P0"]
    checks = {arm: b3.compare(reference, results[arm]) for arm in ARMS[1:]}
    good = {arm: (not results[arm]["timed_out"]
                  and results[arm]["exit_code"] == reference["exit_code"]
                  and checks[arm]["classification"] in {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
                  and results[arm]["observer"].get("assurance_status") == "PASS")
            for arm in ARMS[1:]}
    route_ok = (results["P3"]["route"] == results["P4"]["route"]
                == "REFERENCE_FAST_PATH"
                and results["P3"]["artifact"] == results["P4"]["artifact"] == {})
    return {"checks": checks, "valid_by_arm": good, "route_ok": route_ok,
            "valid": all(good.values()) and route_ok}


def run_score() -> None:
    for name in ("raw_timings.jsonl", "correctness.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"Scored ledger already exists: {name}")
    assert PYTHON.is_file() and CONSOLE.is_file() and OBSERVER.is_file()
    assert (HERE / "empty_bootstrap").is_dir()
    for pos, row in enumerate(population(), 1):
        for rep in (1, 2):
            for invocation in (1, 2):
                results = {}
                for arm in arm_order(f"{row['workload_id']}:{rep}:{invocation}"):
                    base = HERE / "runs" / row["workload_id"] / str(rep) / arm.lower()
                    result = run_arm(row, arm, base)
                    results[arm] = result
                    append("raw_timings.jsonl", {"rep": rep, "invocation": invocation,
                                                 **safe_row(result)})
                verdict = compare(results)
                append("correctness.jsonl", {"workload_id": row["workload_id"],
                                             "rep": rep, "invocation": invocation,
                                             **verdict})
                if not verdict["valid"]:
                    raise RuntimeError(f"Correctness gate failed: {row['workload_id']} {rep} {invocation}: {verdict}")
        print(f"reference-only {pos}/22 {row['workload_id']}", flush=True)


if __name__ == "__main__":
    run_score()
