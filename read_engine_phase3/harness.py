"""Offline product-shaped parent. Imports existing RC admission/capture without edits."""
from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from read_engine_phase3 import safe_artifact


def tick() -> int:
    return time.perf_counter_ns()


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, default=str) + "\n")


def run(script: Path, workdir: Path, cache_root: Path, run_root: Path) -> int:
    from librecalc_agent.config import load as load_config
    from librecalc_agent._frozen.eligibility import classify
    from librecalc_agent._frozen import capture

    profile = {}
    t_all = tick()
    t = tick()
    config, issues = load_config()
    script, workdir = script.resolve(), workdir.resolve()
    if not script.is_file() or not workdir.is_dir() or script.parent != workdir:
        print("FAIL: invalid script/workdir", file=sys.stderr)
        return 2
    importlib.import_module("openpyxl")
    run_id = uuid.uuid4().hex
    cache_root.mkdir(parents=True, exist_ok=True)
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True)
    profile["config_preflight_run_dir_ns"] = tick() - t

    t = tick()
    decision = classify(script.read_text(encoding="utf-8"))["decision"] if config.reads else "DISABLED"
    admitted = decision == "A1_ADMIT"
    profile["admission_ns"] = tick() - t
    entries = {}
    setup_failures = []
    if admitted:
        t = tick()
        sources = [p for p in sorted(workdir.glob("*.xlsx")) if ".tmp" not in p.name]
        profile["discovery_ns"] = tick() - t
        for source in sources:
            resolved = str(source.resolve())
            try:
                t = tick()
                digest = safe_artifact.sha_file(source)
                source_hash_ns = tick() - t
                t = tick()
                artifact, witness, phases = safe_artifact.ensure(source, cache_root, digest)
                ensure_ns = tick() - t
                entries[resolved] = {"status": witness, "source_sha256": digest,
                                     "artifact_path": str(artifact.resolve()), "source_hash_ns": source_hash_ns,
                                     "ensure_ns": ensure_ns, "phases": phases}
            except Exception as exc:
                entries[resolved] = {"status": "UNAVAILABLE", "reason": type(exc).__name__}
                setup_failures.append({"path": resolved, "exception_class": type(exc).__name__,
                                       "message": str(exc)[:300]})
    else:
        profile["discovery_ns"] = 0

    t = tick()
    pre = capture.snapshot_xlsx(workdir) if config.assurance else None
    profile["pre_capture_ns"] = tick() - t

    context = {"script": str(script), "events": str(run_dir / "runtime_events.jsonl"),
               "runtime_profile": str(run_dir / "runtime_profile.json"),
               "admitted": admitted, "workbooks": entries}
    env = {k: v for k, v in os.environ.items()
           if k not in {"LIBRECALC_RUN_CONTEXT", "LIBRECALC_CONFIG", "READ_ENGINE_PHASE3_CONTEXT"}
           and not k.startswith("CANDIDATE_A_")}
    env["READ_ENGINE_PHASE3_CONTEXT"] = json.dumps(context, separators=(",", ":"), default=str)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "read_engine_phase3/bootstrap"), str(ROOT)])
    t = tick()
    child = subprocess.run([sys.executable, str(script)], cwd=workdir, env=env, capture_output=True)
    profile["child_wall_ns"] = tick() - t
    sys.stdout.buffer.write(child.stdout)
    sys.stderr.buffer.write(child.stderr)
    sys.stdout.flush(); sys.stderr.flush()

    capture_rows = []
    capture_sections = {}
    if pre is not None:
        t = tick()
        try:
            capture_rows, capture_sections = capture.capture_wrap_timed(workdir, pre, run_id, "PHASE3", 1)
        except Exception as exc:
            setup_failures.append({"stage": "capture", "exception_class": type(exc).__name__,
                                   "message": str(exc)[:300]})
        profile["post_capture_delta_validation_ns"] = tick() - t
    else:
        profile["post_capture_delta_validation_ns"] = 0
    profile["capture_sections_s"] = capture_sections

    t = tick()
    runtime_profile_path = run_dir / "runtime_profile.json"
    runtime_events_path = run_dir / "runtime_events.jsonl"
    runtime_profile = json.loads(runtime_profile_path.read_text()) if runtime_profile_path.exists() else None
    runtime_events = [json.loads(line) for line in runtime_events_path.read_text().splitlines()] if runtime_events_path.exists() else []
    summary = {"run_id": run_id, "returncode": child.returncode, "read_gate": decision,
               "admitted": admitted, "artifacts": entries, "setup_failures": setup_failures,
               "capture_enabled": config.assurance, "capture_records": len(capture_rows),
               "capture_failures": sum(bool(r.get("runtime_failure")) for r in capture_rows),
               "capture_work_performed_despite_static_read_only": bool(config.assurance and decision == "A1_ADMIT"),
               "runtime_profile": runtime_profile, "runtime_events": len(runtime_events),
               "direct_served_loads": runtime_profile["counts"]["direct_served_loads"] if runtime_profile else None,
               "reference_loads": runtime_profile["counts"]["reference_loads"] if runtime_profile else None,
               "reference_reasons": [e.get("reason") for e in runtime_events if e.get("event") == "reference_parse"],
               "issues": issues}
    profile["diagnostic_read_ns"] = tick() - t
    t = tick()
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "capture.json", capture_rows)
    write_json(run_dir / "parent_profile.json", profile)
    write_json(run_root / "last_run.json", {"run_id": run_id, "run_dir": str(run_dir),
                                             "summary": str(run_dir / "summary.json")})
    profile["diagnostic_write_ns"] = tick() - t
    profile["parent_total_ns"] = tick() - t_all
    write_json(run_dir / "parent_profile.json", profile)
    return child.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workdir", type=Path, required=True)
    r.add_argument("--cache-root", type=Path, required=True)
    r.add_argument("--run-root", type=Path, required=True)
    r.add_argument("script", type=Path)
    args = parser.parse_args()
    return run(args.script, args.workdir, args.cache_root, args.run_root)


if __name__ == "__main__":
    sys.exit(main())
