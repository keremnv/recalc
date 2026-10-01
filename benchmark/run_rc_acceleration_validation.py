"""Run frozen, fresh-cache, public-CLI RC read timing study."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import random
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "rc_acceleration_validation"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def append(name, row):
    with (OUT / name).open("a") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        stream.flush()


def ensure_frozen():
    spec = read("preregistered_spec.json")
    if sha((OUT / "preregistered_spec.json").read_bytes()) != read("spec_hash.json")["sha256"]:
        raise RuntimeError("Preregistration changed")
    if sha((OUT / "rc_identity.json").read_bytes()) != spec["identity_sha256"]:
        raise RuntimeError("RC identity record changed")
    for name, digest in spec["design_hashes"].items():
        if sha((OUT / name).read_bytes()) != digest:
            raise RuntimeError(f"Frozen design changed: {name}")
    from benchmark.prepare_rc_acceleration_validation import verify_rc
    # Verify bytes without changing the identity record or spec.
    original = (OUT / "rc_identity.json").read_bytes()
    verify_rc()
    if (OUT / "rc_identity.json").read_bytes() != original:
        raise RuntimeError("RC identity changed during pre-run verification")


def run_one(row, arm: str, repetition: int, warmup: bool) -> dict:
    label = f"{row['workload_id']}__{arm}__{'warmup' if warmup else 'score'}_{repetition}"
    home = OUT / "runs" / label
    home.mkdir(parents=True, exist_ok=False)
    work = home / "work"
    work.mkdir()
    shutil.copyfile(row["workbook_path"], work / "input.xlsx")
    shutil.copyfile(OUT / "workloads" / (row["workload_id"] + ".py"), work / "workload.py")
    if sha((work / "input.xlsx").read_bytes()) != row["workbook_sha256"]:
        raise RuntimeError("Staged workbook bytes differ from frozen input")
    cache_home = home / "cache"
    cache_home.mkdir()
    if any(cache_home.iterdir()):
        raise RuntimeError("Cache not fresh")
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "LIBRECALC_CONFIG", "LIBRECALC_RUN_CONTEXT"} and not k.startswith("CANDIDATE_A_")}
    env["XDG_CACHE_HOME"] = str(cache_home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = read("control_command.json" if arm == "CONTROL" else "treatment_command.json")["argv_template"]
    argv = [x.replace("{workdir}", str(work)) for x in argv]
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=180)
        elapsed = time.perf_counter_ns() - started
        exit_code, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter_ns() - started
        exit_code, stdout, stderr, timed_out = None, exc.stdout or b"", exc.stderr or b"", True
    after_hash = sha((work / "input.xlsx").read_bytes())
    (home / "stdout.bin").write_bytes(stdout)
    (home / "stderr.bin").write_bytes(stderr)
    summary = None
    manifest = None
    events = []
    if arm == "TREATMENT":
        summaries = list((cache_home / "librecalc-agent/runs").glob("*/summary.json"))
        if len(summaries) == 1:
            summary = json.loads(summaries[0].read_text())
            manifest_path = summaries[0].parent / "index/manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text())
            event_path = summaries[0].parent / "runtime.jsonl"
            if event_path.exists():
                for line in event_path.read_text().splitlines():
                    try: events.append(json.loads(line))
                    except ValueError: pass
    operation = [e for e in events if e.get("event") == "candidate_operation"]
    output = {
        "workload_id": row["workload_id"], "task": row["task"], "family": row["family"],
        "arm": arm, "repetition": repetition, "warmup": warmup, "argv": argv,
        "wall_ns": elapsed, "exit_code": exit_code, "timed_out": timed_out,
        "stdout_sha256": sha(stdout), "stdout_bytes": len(stdout),
        "stderr_sha256": sha(stderr), "stderr_bytes": len(stderr),
        "workbook_unchanged": after_hash == row["workbook_sha256"],
        "cache_fresh_before_start": True, "run_dir": str(home.relative_to(ROOT)),
        "read_gate": summary.get("read_gate") if summary else None,
        "accelerated_loads": summary.get("accelerated_loads") if summary else 0,
        "compiled_workbooks": summary.get("compiled_workbooks") if summary else 0,
        "fallback_count": len(summary.get("fallback", [])) if summary else 0,
        "capture_enabled": summary.get("capture_enabled") if summary else None,
        "capture_records": summary.get("capture_records") if summary else None,
        "index_setup_s": manifest.get("total_s") if manifest else None,
        "index_ensure_s": manifest.get("ensure_s") if manifest else None,
        "index_backup_s": manifest.get("backup_s") if manifest else None,
        "index_rebuilt": manifest.get("n_rebuilt") if manifest else None,
        "index_failures": len(manifest.get("failures", [])) if manifest else None,
        "runtime_events": len(events),
        "accelerated_events": sum(e.get("status") == "ACCELERATED" for e in operation),
        "fallback_events": sum("FALLBACK" in str(e.get("status")) for e in operation),
        "accelerated_operation_ns": sum(e.get("duration_ns") or 0 for e in operation if e.get("status") == "ACCELERATED"),
        "fallback_operation_ns": sum(e.get("duration_ns") or 0 for e in operation if "FALLBACK" in str(e.get("status"))),
        "event_status_counts": {str(k): sum(e.get("status") == k for e in operation) for k in sorted({e.get("status") for e in operation})},
    }
    append("raw_timings.jsonl", output)
    return output


def main():
    ensure_frozen()
    if (OUT / "raw_timings.jsonl").exists():
        raise RuntimeError("Raw timing ledger already exists; no unplanned reruns")
    manifest = read("workload_manifest.json")
    by_id = {r["workload_id"]: r for r in manifest["all_candidates"]}
    selected = sorted(set(read("representative_population.json")["workload_ids"] + read("eligible_population.json")["workload_ids"]))
    protocol = read("timing_protocol.json")
    rng = random.Random(20261011)
    order = selected[:]
    rng.shuffle(order)
    for index, workload_id in enumerate(order, 1):
        row = by_id[workload_id]
        for arm in (("CONTROL", "TREATMENT") if index % 2 else ("TREATMENT", "CONTROL")):
            run_one(row, arm, 0, True)
        for rep in range(1, protocol["repetitions"] + 1):
            arms = ("CONTROL", "TREATMENT") if (index + rep) % 2 else ("TREATMENT", "CONTROL")
            for arm in arms:
                run_one(row, arm, rep, False)
        print(f"completed {index}/{len(order)} {workload_id}", flush=True)


if __name__ == "__main__":
    main()
