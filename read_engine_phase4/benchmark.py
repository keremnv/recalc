"""Frozen-population three-arm Phase-4 full-command runner."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from read_engine_phase3 import benchmark as b3
from read_engine_phase4 import parent_artifact

VENV = Path("/tmp/librecalc-hygiene-rc-v55taghk/venv/bin/python")
SPEC_SHA = "0162f197c89c37ee63bafb5cfbbbc65f3e030eb830bd945ddffa042c560019ea"
AMENDMENT_SHA = "81d5eecda220de9d6ba20f4f241a26c1b16910eba595c3cdc9db42ab30306239"
PINNED = {
    "read_engine_phase3/harness.py": "033a34544deeee07af27db7a5729f7bd763a614709744cc4abb36aea0741adfa",
    "read_engine_phase3/safe_artifact.py": "9cf0b12ba9f47a5b2af045c5d68457638ebc301e54db1113a58b5eba3ee64848",
    "read_engine_phase3/runtime.py": "a6ba03f6bebdffe14e1b1b3c73ddac662fc2be7948bd26e25ec8ac9ebd8df875",
    "read_engine_phase3/bootstrap/sitecustomize.py": "9b7158871fa3b143e9d9aa493fd872fb8aa525d3ffa4ee5b5771df32cacb2804",
    "read_engine_phase1/prototype.py": "a6e95f1503ec6090d6176065471372924bf447f907a2a428faceee12a2f72473",
    "read_engine_phase3/population.json": "ea83d4f603430d78b30b8b85b70bb5a8ee9ef916350060bbf52c8f67701651dc",
    "research/history/rc_acceleration_validation/eligible_population.json": "b6be87f570bfd33c499038526a45b8624d7752531a79dda29a55bd9cddbcf1a8",
}
ARMS = ("PY", "H0", "H1")


def sha_file(path: Path) -> str:
    return parent_artifact.sha_file(path)


def append(name: str, row: dict) -> None:
    with (HERE / name).open("a") as out:
        out.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def verify() -> dict:
    if sha_file(HERE / "PREREGISTERED_SPEC.md") != SPEC_SHA:
        raise RuntimeError("Phase-4 preregistration changed")
    if sha_file(HERE / "PREREGISTERED_SPEC_AMENDMENT_1.md") != AMENDMENT_SHA:
        raise RuntimeError("Phase-4 preregistration amendment changed")
    for name, digest in PINNED.items():
        if sha_file(ROOT / name) != digest:
            raise RuntimeError(f"Frozen authority changed: {name}")
    impl = json.loads((HERE / "implementation_identity.json").read_text())
    for name, digest in impl.items():
        if sha_file(HERE / name) != digest:
            raise RuntimeError(f"Phase-4 implementation changed: {name}")
    if not VENV.is_file():
        raise RuntimeError("Frozen RC interpreter missing")
    population = json.loads((ROOT / "read_engine_phase3/population.json").read_text())
    ids = population["primary_ids"]
    by_id = {x["workload_id"]: x for x in population["workloads"]}
    if len(ids) != 22 or len(set(ids)) != 22:
        raise RuntimeError("Primary population identity mismatch")
    for wid in ids:
        row = by_id[wid]
        if sha_file(Path(row["script_path"])) != row["script_sha256"]:
            raise RuntimeError(f"Script changed: {wid}")
        if sha_file(Path(row["source_workbook_path"])) != row["source_workbook_sha256"]:
            raise RuntimeError(f"Source workbook changed: {wid}")
        if row["staged_workbook_sha256"] != row["source_workbook_sha256"]:
            raise RuntimeError(f"Staged/source workbook mismatch: {wid}")
    return population


def command(row: dict, arm: str, base: Path) -> dict:
    work = base / "work"
    b3.stage(row, work)
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "LIBRECALC_CONFIG", "LIBRECALC_RUN_CONTEXT", "READ_ENGINE_PHASE3_CONTEXT"}
           and not k.startswith("CANDIDATE_A_")}
    env["XDG_CACHE_HOME"] = str(base / "xdg")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if arm == "PY":
        argv = [str(VENV), str(work / "workload.py")]
    else:
        harness = ROOT / ("read_engine_phase3/harness.py" if arm == "H0" else "read_engine_phase4/harness.py")
        argv = [str(VENV), str(harness), "run", "--workdir", str(work),
                "--cache-root", str(base / "persistent-cache"),
                "--run-root", str(base / "runs"), str(work / "workload.py")]
    t = time.perf_counter_ns()
    try:
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=180)
        wall = time.perf_counter_ns() - t
        code, stdout, stderr, timeout = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        wall = time.perf_counter_ns() - t
        code, stdout, stderr, timeout = None, exc.stdout or b"", exc.stderr or b"", True
    summary = profile = child_profile = None
    events = []
    if arm != "PY":
        last = base / "runs/last_run.json"
        if last.exists():
            run_dir = Path(json.loads(last.read_text())["run_dir"])
            sp, pp, ep = run_dir / "summary.json", run_dir / "parent_profile.json", run_dir / "runtime_events.jsonl"
            if sp.exists():
                summary = json.loads(sp.read_text())
                child_profile = summary.get("runtime_profile")
            if pp.exists():
                profile = json.loads(pp.read_text())
            if ep.exists():
                events = [json.loads(line) for line in ep.read_text().splitlines()]
    return {"wall_ns": wall, "exit_code": code, "timed_out": timeout,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "stdout_bytes": len(stdout), "stderr_bytes": len(stderr),
            "files_after": b3.files_after(work), "summary": summary,
            "parent_profile": profile, "child_profile": child_profile,
            "events": events, "stdout": stdout, "stderr": stderr,
            "argv": argv}


def persist(row: dict, arm: str, phase: str, rep: int, invocation: int, result: dict) -> None:
    keep = {k: v for k, v in result.items() if k not in {"events", "stdout", "stderr"}}
    append("raw_timings.jsonl", {"workload_id": row["workload_id"], "task": row["task"],
          "family": row["family"], "arm": arm, "phase": phase, "rep": rep,
          "invocation": invocation, **keep})


def confirm(row: dict, phase: str, rep: int, invocation: int, results: dict) -> bool:
    py, h0, h1 = (results[x] for x in ARMS)
    checks = {"PY_H0": b3.compare(py, h0), "PY_H1": b3.compare(py, h1),
              "H0_H1": b3.compare(h0, h1)}
    def state(x):
        sm = x.get("summary") or {}
        return (sorted(a.get("status") for a in sm.get("artifacts", {}).values()),
                sm.get("direct_served_loads"), sm.get("reference_reasons", []))
    state0, state1 = state(h0), state(h1)
    warm = invocation > 1
    witness = ((not warm or (state0[0] == ["REUSED"] and state1[0] == ["REUSED"]))
               and state0[1] == state1[1] and state0[1] and state0[2] == state1[2]
               and h0.get("child_profile") is not None and h1.get("child_profile") is not None)
    child_confirmed = any(e.get("event") == "direct_served_load" for e in h1["events"])
    parent_clean = True
    if warm:
        entries = list((h1["summary"] or {}).get("artifacts", {}).values())
        parent_clean = bool(entries) and all(
            not e.get("phases", {}).get("parent_memorybook_constructed")
            and not e.get("phases", {}).get("builder_stack_imported")
            and not any(e.get("phases", {}).get("builder_modules_present_in_parent", {}).values())
            for e in entries)
    exact = all(c["classification"] == "EXACT" for c in checks.values())
    valid = exact and witness and child_confirmed and parent_clean and all(x["exit_code"] == 0 and not x["timed_out"] for x in results.values())
    append("raw_correctness.jsonl", {"kind": "script_triplet", "workload_id": row["workload_id"],
           "phase": phase, "rep": rep, "invocation": invocation, "regime": "WARM" if warm else "COLD",
           "checks": checks, "H0_state": state0, "H1_state": state1,
           "child_confirmed": child_confirmed, "warm_parent_clean": parent_clean,
           "witness_ok": witness, "valid": valid})
    return valid


def run_gate(pop: dict) -> bool:
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    for position, wid in enumerate(pop["primary_ids"], 1):
        row = by_id[wid]
        base = HERE / "runs/gate" / wid
        results = {"PY": command(row, "PY", base / "py"),
                   "H0": command(row, "H0", base / "h0"),
                   "H1": command(row, "H1", base / "h1")}
        for arm in ARMS:
            persist(row, arm, "gate", 0, 1, results[arm])
        if not confirm(row, "gate", 0, 1, results):
            print(f"STOP: cold semantic gate {wid}", flush=True)
            return False
        for arm in ("H0", "H1"):
            results[arm] = command(row, arm, base / arm.lower())
            persist(row, arm, "gate", 0, 2, results[arm])
        if not confirm(row, "gate", 0, 2, results):
            print(f"STOP: warm semantic gate {wid}", flush=True)
            return False
        print(f"semantic gate {position}/22 {wid}", flush=True)
    return True


def run_scored(pop: dict) -> bool:
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    order = list(pop["primary_ids"])
    random.Random(20261104).shuffle(order)
    for position, wid in enumerate(order, 1):
        row = by_id[wid]
        for arm in ARMS:
            command(row, arm, HERE / "runs/warmup" / wid / arm.lower())
        for rep in range(1, 4):
            base = HERE / "runs/scored" / wid / f"rep-{rep}"
            totals = {arm: 0 for arm in ARMS}
            for invocation in range(1, 6):
                shift = (position + rep + invocation) % 3
                arm_order = ARMS[shift:] + ARMS[:shift]
                results = {}
                for arm in arm_order:
                    results[arm] = command(row, arm, base / arm.lower())
                    persist(row, arm, "scored", rep, invocation, results[arm])
                    totals[arm] += results[arm]["wall_ns"]
                if not confirm(row, "scored", rep, invocation, results):
                    print(f"STOP: scored semantic/reuse failure {wid} rep={rep} invocation={invocation}", flush=True)
                    return False
                if invocation in (1, 2, 3, 5):
                    append("session_timings.jsonl", {"workload_id": wid, "task": row["task"],
                           "rep": rep, "N": invocation, "PY_ns": totals["PY"],
                           "H0_ns": totals["H0"], "H1_ns": totals["H1"],
                           "all_warm_reused": True})
        print(f"scored {position}/22 {wid}", flush=True)
    return True


def main() -> None:
    pop = verify()
    for name in ("raw_correctness.jsonl", "raw_timings.jsonl", "session_timings.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"Ledger already exists: {name}")
        (HERE / name).write_text("")
    from read_engine_phase4 import gates
    if not gates.run(pop, lambda row: append("raw_correctness.jsonl", row)):
        print("STOP: invalidation/corruption gate failed", flush=True)
        return
    if not run_gate(pop):
        return
    if not run_scored(pop):
        return


if __name__ == "__main__":
    main()
