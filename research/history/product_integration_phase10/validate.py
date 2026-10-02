"""Independent full-command validation of the installed product against Phase 9."""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from read_engine_phase3 import benchmark as b3
from read_engine_phase8a import validation_runner as p8

PYTHON = Path("/tmp/librecalc-phase10-clean/bin/python")
CONSOLE = Path("/tmp/librecalc-phase10-clean/bin/librecalc-agent")
ARMS = ("PY", "EXP", "PROD")
SEED = 20260928
TIMEOUT = 180


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def write(name: str, item: dict) -> None:
    with (HERE / name).open("a") as stream:
        stream.write(json.dumps(item, sort_keys=True, default=str) + "\n")


def populations() -> tuple[dict, list[dict]]:
    population = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    assert len(population["primary_ids"]) == 22
    assert len(population["secondary_ids"]) == 30
    for row in population["workloads"]:
        assert sha(Path(row["script_path"])) == row["script_sha256"], row["workload_id"]
        assert sha(Path(row["source_workbook_path"])) == row["source_workbook_sha256"], row["workload_id"]
    assert population["secondary_ids"] == json.loads(
        (ROOT / "research/history/rc_acceleration_validation/representative_population.json").read_text()
    )["workload_ids"]
    changed = []
    source = p8.FIXTURE_BOOK
    for name in p8.FIXTURE_NAMES:
        script = ROOT / "read_engine_phase8/changed_file_fixtures" / f"{name}.py"
        changed.append({"workload_id": "phase8_changed_" + name,
                        "task": "PHASE8_CHANGED", "family": "ChangedFile",
                        "script_path": str(script), "script_sha256": sha(script),
                        "source_workbook_path": str(source),
                        "source_workbook_sha256": sha(source),
                        "staged_workbook_sha256": sha(source)})
    return population, changed


def order(key: str) -> list[str]:
    result = list(ARMS)
    random.Random(SEED ^ int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)).shuffle(result)
    return result


def _json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def run_arm(row: dict, arm: str, base: Path) -> dict:
    work = base / "work"
    b3.stage(row, work)
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "LIBRECALC_CONFIG", "LIBRECALC_RUN_CONTEXT",
                        "READ_ENGINE_PHASE6_CONTEXT", "LIBRECALC_EFFECTIVE_CONFIG"}
           and not k.startswith("CANDIDATE_A_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["XDG_CACHE_HOME"] = str(base / "xdg")
    if arm == "PY":
        command = [str(PYTHON), str(work / "workload.py")]
    elif arm == "EXP":
        command = [str(ROOT / "read_engine_phase6/observer"), str(PYTHON),
                   str(work / "workload.py"), str(work), str(base / "cache"),
                   str(base / "runs"), str(ROOT / "read_engine_phase9/overlay")]
    else:
        command = [str(CONSOLE), "run", "--workdir", str(work),
                   str(work / "workload.py")]
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run(command, cwd=work, env=env, capture_output=True,
                              timeout=TIMEOUT, check=False)
        elapsed = time.perf_counter_ns() - started
        code, out, err, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter_ns() - started
        code, out, err, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
    result = {"workload_id": row["workload_id"], "arm": arm, "wall_ns": elapsed,
              "exit_code": code, "timed_out": timed_out,
              "stdout_sha256": hashlib.sha256(out).hexdigest(),
              "stderr_sha256": hashlib.sha256(err).hexdigest(),
              "stdout_bytes": len(out), "stderr_bytes": len(err),
              "stdout": out, "stderr": err, "files_after": b3.files_after(work),
              "workdir": str(work), "command": command}
    if arm == "PY":
        return result
    root = base / ("runs" if arm == "EXP" else "xdg/librecalc-agent/runs")
    pointer = _json(root / "last_run.json") or {}
    run_dir = Path(pointer.get("run_dir", "/nonexistent"))
    setup = _json(run_dir / "setup.json") or {}
    runtime = _json(run_dir / ("runtime_profile.json" if arm == "EXP" else "runtime_state.json")) or {}
    observer = _json(run_dir / "observer_receipt.json") or {}
    capture = _json(run_dir / "capture.json")
    capture_state = _json(run_dir / ("capture_profile.json" if arm == "EXP" else "capture_state.json")) or {}
    artifacts = setup.get("artifacts") or {}
    statuses = sorted({x.get("status") for x in artifacts.values() if isinstance(x, dict)
                       and x.get("status")})
    direct = (runtime.get("counts") or {}).get("direct_served_loads") or 0
    if arm == "EXP":
        events = (run_dir / "runtime_events.jsonl")
        reasons = [x.get("reason") for x in
                   (json.loads(line) for line in events.read_text().splitlines())
                   if x.get("event") == "reference_parse"] if events.exists() else []
    else:
        reasons = runtime.get("fallback_reasons") or []
    result.update({"setup": setup, "runtime": runtime, "observer": observer,
                   "capture": capture, "capture_state": capture_state,
                   "run_dir": str(run_dir), "artifact_statuses": statuses,
                   "direct_served_loads": direct, "fallback_reasons": reasons,
                   "route": "FALLBACK_AFTER_CONTACT" if direct and reasons else
                            "DIRECT_CONTACT" if direct else "REFERENCE_ONLY"})
    return result


def safe_row(result: dict) -> dict:
    return {k: v for k, v in result.items()
            if k not in {"stdout", "stderr", "files_after", "command", "setup", "runtime",
                         "observer", "capture", "capture_state"}}


def compare(row: dict, results: dict, invocation: int, changed: bool) -> dict:
    py, exp, prod = (results[x] for x in ARMS)
    checks = {"PY_EXP": b3.compare(py, exp), "PY_PROD": b3.compare(py, prod),
              "EXP_PROD": b3.compare(exp, prod)}
    allowed = {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
    if changed:
        state_ok = all(p8.package_relation(py, results[x])[0] for x in ("EXP", "PROD"))
        streams_ok = all((py["stdout"], py["stderr"]) ==
                         (results[x]["stdout"], results[x]["stderr"])
                         for x in ("EXP", "PROD"))
    else:
        state_ok = all(x["classification"] in allowed for x in checks.values())
        streams_ok = True
    route_ok = exp["route"] == prod["route"]
    expected = ["BUILT"] if invocation == 1 else ["REUSED"]
    if exp["route"] != "REFERENCE_ONLY":
        artifact_ok = exp["artifact_statuses"] == prod["artifact_statuses"] == expected
    else:
        artifact_ok = exp["artifact_statuses"] == prod["artifact_statuses"] == []
    assurance_ok = (exp["observer"].get("capture_helper_exit") == 0
                    and prod["observer"].get("assurance_status") == "PASS")
    if changed:
        assurance_ok = assurance_ok and (prod["capture_state"].get("validation_passed") is True
                                        and len(prod.get("capture") or []) == 1
                                        and len(exp.get("capture") or []) == 1)
    exits = all(results[a]["exit_code"] == 0 and not results[a]["timed_out"] for a in ARMS)
    result = {"workload_id": row["workload_id"], "invocation": invocation,
              "changed": changed, "checks": checks, "state_ok": state_ok,
              "streams_ok": streams_ok, "route_ok": route_ok,
              "artifact_ok": artifact_ok, "assurance_ok": assurance_ok,
              "fallback_ok": exp["fallback_reasons"] == prod["fallback_reasons"],
              "exit_ok": exits}
    result["valid"] = all(result[k] for k in ("state_ok", "streams_ok", "route_ok",
                                            "artifact_ok", "assurance_ok", "fallback_ok", "exit_ok"))
    return result


def paired_rows(row: dict, label: str, rep: int, base: Path, invocations: int,
                changed: bool = False) -> list[dict]:
    all_results = []
    for invocation in range(1, invocations + 1):
        results = {}
        for arm in order(f"{row['workload_id']}:{label}:{rep}:{invocation}"):
            result = run_arm(row, arm, base / arm.lower())
            results[arm] = result
            write("raw_timings.jsonl", {"population": label, "rep": rep,
                                         "invocation": invocation, **safe_row(result)})
        verdict = compare(row, results, invocation, changed)
        write("correctness.jsonl", {"population": label, "rep": rep, **verdict})
        if not verdict["valid"]:
            raise RuntimeError(f"Correctness gate failed: {label} {row['workload_id']} {rep} {invocation}: {verdict}")
        all_results.append(results)
    return all_results


def run_validation() -> None:
    population, changed = populations()
    if not PYTHON.is_file() or not CONSOLE.is_file():
        raise RuntimeError("clean installed environment missing")
    for name in ("raw_timings.jsonl", "correctness.jsonl", "session_timings.jsonl"):
        if (HERE / name).exists() and (HERE / name).stat().st_size:
            raise RuntimeError(f"Refusing to append to existing scored ledger: {name}")
    by_id = {row["workload_id"]: row for row in population["workloads"]}
    for label, ids in (("representative30", population["secondary_ids"]),
                       ("fixed22", population["primary_ids"])):
        for pos, wid in enumerate(ids, 1):
            row = by_id[wid]
            for rep in range(1, 3):
                paired_rows(row, label, rep, HERE / "runs" / label / wid / str(rep), 2)
            print(f"{label} {pos}/{len(ids)} {wid}", flush=True)
    for pos, row in enumerate(changed, 1):
        paired_rows(row, "changed5", 1, HERE / "runs/changed5" / row["workload_id"],
                    1, changed=True)
        print(f"changed5 {pos}/5 {row['workload_id']}", flush=True)
    for pos, wid in enumerate(population["secondary_ids"], 1):
        row = by_id[wid]
        for n in (1, 2, 3, 5):
            results = paired_rows(row, "session30", n,
                                  HERE / "runs/session30" / wid / str(n), n)
            write("session_timings.jsonl", {"workload_id": wid, "n": n,
                                           "route": results[-1]["PROD"]["route"],
                                           "sum_ns": {arm: sum(item[arm]["wall_ns"]
                                                               for item in results)
                                                      for arm in ARMS}})
        print(f"session30 {pos}/30 {wid}", flush=True)


if __name__ == "__main__":
    run_validation()
