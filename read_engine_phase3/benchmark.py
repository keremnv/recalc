"""Frozen RC-population, product-shaped Phase-3 runner. No model calls."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from read_engine_phase3 import artifact_gate, safe_artifact  # noqa: E402

VENV = Path("/tmp/librecalc-hygiene-rc-v55taghk/venv/bin/python")
SPEC_SHA = "555a56750036c0cb5ded88fdfb636e9205f22aa0340dce00eb9bf93fa9a49ab7"
POP_SHA = "ea83d4f603430d78b30b8b85b70bb5a8ee9ef916350060bbf52c8f67701651dc"
FROZEN = {"eligible_population.json": "b6be87f570bfd33c499038526a45b8624d7752531a79dda29a55bd9cddbcf1a8",
          "representative_population.json": "efc5d8c2e553ab0af90d18d45e1326817e55178a5d521fec23bde5c0c43504f5",
          "workload_manifest.json": "4d2f9ea32dce55c12f3f7e44696177979c781f32e565f0dd5c5c857e847fb3d9"}
ADDRESS = re.compile(rb"(<openpyxl\.worksheet\.formula\.(?:ArrayFormula|DataTableFormula) object at )0x[0-9a-fA-F]+")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def append(filename: str, row: dict) -> None:
    with (HERE / filename).open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def verify() -> dict:
    if safe_artifact.sha_file(HERE / "PREREGISTERED_SPEC.md") != SPEC_SHA:
        raise RuntimeError("Preregistration changed")
    if safe_artifact.sha_file(HERE / "population.json") != POP_SHA:
        raise RuntimeError("Phase-3 population changed")
    for name, digest in FROZEN.items():
        if safe_artifact.sha_file(ROOT / "rc_acceleration_validation" / name) != digest:
            raise RuntimeError(f"Frozen RC source changed: {name}")
    if safe_artifact.sha_file(ROOT / "read_engine_phase1/prototype.py") != safe_artifact.DECODER:
        raise RuntimeError("Phase-1 decoder changed")
    identity = json.loads((HERE / "implementation_identity.json").read_text())
    for name, digest in identity.items():
        if safe_artifact.sha_file(HERE / name) != digest:
            raise RuntimeError(f"Phase-3 implementation changed: {name}")
    if not VENV.is_file():
        raise RuntimeError("Frozen RC venv unavailable")
    pop = json.loads((HERE / "population.json").read_text())
    if len(pop["primary_ids"]) != 22 or len(pop["secondary_ids"]) != 30:
        raise RuntimeError("Population cardinality changed")
    for row in pop["workloads"]:
        if safe_artifact.sha_file(Path(row["script_path"])) != row["script_sha256"]:
            raise RuntimeError("Script identity changed: " + row["workload_id"])
        if safe_artifact.sha_file(Path(row["source_workbook_path"])) != row["source_workbook_sha256"]:
            raise RuntimeError("Workbook identity changed: " + row["workload_id"])
    return pop


def files_after(work: Path) -> dict:
    hashes = {}
    for path in sorted(work.rglob("*")):
        if not path.is_file() or path.name == "workload.py":
            continue
        rel = str(path.relative_to(work))
        data = path.read_bytes()
        row = {"sha256": sha(data), "bytes": len(data)}
        if path.suffix.lower() == ".xlsx":
            try:
                with zipfile.ZipFile(path) as z:
                    row["package_parts"] = {name: sha(z.read(name)) for name in sorted(z.namelist())}
            except Exception as exc:
                row["package_error"] = type(exc).__name__
        hashes[rel] = row
    return hashes


def normalized(data: bytes) -> bytes:
    return ADDRESS.sub(rb"\g<1>0xADDR", data)


def compare(control: dict, treatment: dict) -> dict:
    if control["timed_out"] or treatment["timed_out"] or control["exit_code"] is None or treatment["exit_code"] is None:
        status = "EXECUTION_FAILURE"
    elif control["exit_code"] != treatment["exit_code"] or control["exit_code"] != 0:
        status = "EXECUTION_FAILURE"
    else:
        state_equal = control["files_after"] == treatment["files_after"]
        stdout_exact = control["stdout"] == treatment["stdout"]
        stderr_exact = control["stderr"] == treatment["stderr"]
        if state_equal and stdout_exact and stderr_exact:
            status = "EXACT"
        elif (state_equal and normalized(control["stdout"]) == normalized(treatment["stdout"])
              and normalized(control["stderr"]) == normalized(treatment["stderr"])):
            status = "VOLATILE_ONLY_DIFFERENCE"
        else:
            status = "GENUINE_SEMANTIC_DIFFERENCE"
    return {"classification": status,
            "exit_equal": control["exit_code"] == treatment["exit_code"],
            "stdout_exact": control["stdout"] == treatment["stdout"],
            "stdout_normalized_equal": normalized(control["stdout"]) == normalized(treatment["stdout"]),
            "stderr_exact": control["stderr"] == treatment["stderr"],
            "stderr_normalized_equal": normalized(control["stderr"]) == normalized(treatment["stderr"]),
            "output_state_equal": control["files_after"] == treatment["files_after"]}


def stage(row: dict, work: Path) -> None:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copyfile(row["source_workbook_path"], work / "input.xlsx")
    shutil.copyfile(row["script_path"], work / "workload.py")
    if safe_artifact.sha_file(work / "input.xlsx") != row["staged_workbook_sha256"]:
        raise RuntimeError("Staged workbook identity changed")
    if safe_artifact.sha_file(work / "workload.py") != row["script_sha256"]:
        raise RuntimeError("Staged script identity changed")


def run_one(row: dict, view: str, phase: str, rep: int, invocation: int, arm: str,
            base: Path) -> dict:
    work = base / "work"
    stage(row, work)
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "LIBRECALC_CONFIG", "LIBRECALC_RUN_CONTEXT", "READ_ENGINE_PHASE3_CONTEXT"}
           and not k.startswith("CANDIDATE_A_")}
    env["XDG_CACHE_HOME"] = str(base / "xdg")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if arm == "CONTROL":
        argv = [str(VENV), str(work / "workload.py")]
    else:
        argv = [str(VENV), str(HERE / "harness.py"), "run", "--workdir", str(work),
                "--cache-root", str(base / "persistent-cache"),
                "--run-root", str(base / "runs"), str(work / "workload.py")]
    t = time.perf_counter_ns()
    try:
        process = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=180)
        wall_ns = time.perf_counter_ns() - t
        code, stdout, stderr, timed_out = process.returncode, process.stdout, process.stderr, False
    except subprocess.TimeoutExpired as exc:
        wall_ns = time.perf_counter_ns() - t
        code, stdout, stderr, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
    slot = base / "outputs" / f"{phase}-{rep}-{invocation}-{arm.lower()}"
    slot.mkdir(parents=True, exist_ok=True)
    (slot / "stdout.bin").write_bytes(stdout)
    (slot / "stderr.bin").write_bytes(stderr)
    summary = parent_profile = child_profile = None
    events = []
    if arm == "TREATMENT":
        last = base / "runs/last_run.json"
        if last.exists():
            run_dir = Path(json.loads(last.read_text())["run_dir"])
            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text())
            parent_path = run_dir / "parent_profile.json"
            if parent_path.exists():
                parent_profile = json.loads(parent_path.read_text())
            child_profile = summary.get("runtime_profile") if summary else None
            event_path = run_dir / "runtime_events.jsonl"
            if event_path.exists():
                events = [json.loads(s) for s in event_path.read_text().splitlines()]
    core = {"workload_id": row["workload_id"], "task": row["task"], "family": row["family"],
            "view": view, "phase": phase, "rep": rep, "invocation": invocation,
            "arm": arm, "wall_ns": wall_ns, "exit_code": code, "timed_out": timed_out,
            "stdout_sha256": sha(stdout), "stdout_bytes": len(stdout),
            "stderr_sha256": sha(stderr), "stderr_bytes": len(stderr),
            "files_after": files_after(work), "summary": summary,
            "parent_profile": parent_profile, "child_profile": child_profile,
            "event_count": len(events), "output_dir": str(slot.relative_to(ROOT)),
            "argv": argv}
    append("raw_timings.jsonl", core)
    for event in events:
        append("runtime_events.jsonl", {"workload_id": row["workload_id"], "view": view,
                                        "phase": phase, "rep": rep, "invocation": invocation,
                                        "arm": arm, **event})
    return {**core, "stdout": stdout, "stderr": stderr}


def record_pair(control: dict, treatment: dict, row: dict, regime: str) -> bool:
    comparison = compare(control, treatment)
    summary = treatment.get("summary")
    artifacts = summary.get("artifacts", {}) if summary else {}
    witnesses = sorted({a.get("status") for a in artifacts.values()})
    contact = bool(summary and summary.get("direct_served_loads"))
    expected_warm = regime == "WARM" and contact
    witness_ok = not expected_warm or bool(artifacts and all(a.get("status") == "REUSED" for a in artifacts.values()))
    result = {"kind": "script_pair", "workload_id": row["workload_id"],
              "view": control["view"], "phase": control["phase"],
              "rep": control["rep"], "invocation": control["invocation"],
              "regime": regime, "old_semantic_status": row["old_semantic_status"],
              "artifact_witnesses": witnesses, "contact": contact,
              "reference_reasons": summary.get("reference_reasons", []) if summary else [],
              "witness_ok": witness_ok, **comparison}
    append("raw_correctness.jsonl", result)
    return (comparison["classification"] in {"EXACT", "VOLATILE_ONLY_DIFFERENCE"}
            and witness_ok and summary is not None and treatment["child_profile"] is not None)


def run_view(pop: dict, view: str, repetitions: int, horizons: tuple[int, ...]) -> bool:
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    ids = pop["primary_ids"] if view == "PRIMARY" else pop["secondary_ids"]
    rng = random.Random(20261011 if view == "PRIMARY" else 20261012)
    order = ids[:]
    rng.shuffle(order)
    okay = True
    for position, wid in enumerate(order, 1):
        row = by_id[wid]
        warmup = HERE / "runs" / view.lower() / wid / "warmup"
        run_one(row, view, "warmup", 0, 0, "CONTROL", warmup / "control")
        run_one(row, view, "warmup", 0, 0, "TREATMENT", warmup / "treatment")
        for rep in range(1, repetitions + 1):
            base = HERE / "runs" / view.lower() / wid / f"rep-{rep}"
            controls = []
            treatments = []
            for j in range(1, max(horizons) + 1):
                arm_order = ("CONTROL", "TREATMENT") if (position + rep + j) % 2 else ("TREATMENT", "CONTROL")
                pair = {}
                for arm in arm_order:
                    pair[arm] = run_one(row, view, "scored", rep, j, arm, base)
                controls.append(pair["CONTROL"])
                treatments.append(pair["TREATMENT"])
                valid = record_pair(pair["CONTROL"], pair["TREATMENT"], row,
                                    "COLD" if j == 1 else "WARM")
                okay &= valid
                if view == "PRIMARY" and not valid:
                    return False
                if j in horizons:
                    append("session_timings.jsonl", {"view": view, "workload_id": wid,
                                                      "rep": rep, "N": j,
                                                      "control_ns": sum(x["wall_ns"] for x in controls),
                                                      "treatment_ns": sum(x["wall_ns"] for x in treatments),
                                                      "all_warm_reused": all((t["summary"] and
                                                       all(a.get("status") == "REUSED" for a in t["summary"].get("artifacts", {}).values()))
                                                       for t in treatments[1:])})
        print(f"scored {view} {position}/{len(order)} {wid}", flush=True)
    return okay


def main() -> None:
    pop = verify()
    for name in ("raw_correctness.jsonl", "raw_timings.jsonl", "session_timings.jsonl", "runtime_events.jsonl"):
        if (HERE / name).exists():
            raise RuntimeError(f"Ledger already exists: {name}; do not mix reruns")
        (HERE / name).write_text("")
    if not artifact_gate.run(lambda row: append("raw_correctness.jsonl", row)):
        print("STOP: safe artifact gate failed", flush=True)
        return
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    primary_ok = True
    for idx, wid in enumerate(pop["primary_ids"], 1):
        row = by_id[wid]
        base = HERE / "runs" / "primary_gate" / wid
        control = run_one(row, "PRIMARY", "gate", 0, 1, "CONTROL", base / "control")
        cold = run_one(row, "PRIMARY", "gate", 0, 1, "TREATMENT", base / "treatment")
        warm = run_one(row, "PRIMARY", "gate", 0, 2, "TREATMENT", base / "treatment")
        primary_ok &= record_pair(control, cold, row, "COLD")
        primary_ok &= record_pair(control, warm, row, "WARM")
        print(f"semantic gate {idx}/22 {wid}", flush=True)
    if not primary_ok:
        print("STOP: primary semantic or reuse gate failed; no scored speed endpoint", flush=True)
        return
    if not run_view(pop, "PRIMARY", 3, (1, 2, 3, 5)):
        print("STOP: primary scored semantic or reuse failure; aggregate speed invalid", flush=True)
        return
    run_view(pop, "SECONDARY", 2, (1, 2))


if __name__ == "__main__":
    main()
