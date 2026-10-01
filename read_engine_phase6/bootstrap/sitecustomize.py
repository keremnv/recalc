"""Guarded Phase-6 script-process preparation; observer stays Python-free."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_started = time.perf_counter_ns()
_context_path = os.environ.get("READ_ENGINE_PHASE6_CONTEXT")


def _run(path: Path) -> None:
    script_s, workdir_s, cache_s, run_dir_s = path.read_text().splitlines()
    script = Path(script_s).resolve()
    workdir = Path(workdir_s).resolve()
    cache_root = Path(cache_s)
    run_dir = Path(run_dir_s)
    # A different Python process launched by a script must not inherit this
    # runtime merely because it inherits the environment.
    if Path(sys.argv[0]).resolve() != script:
        return
    from librecalc_agent.config import load as load_config
    from librecalc_agent._frozen.eligibility import classify
    from read_engine_phase4 import parent_artifact

    t = time.perf_counter_ns()
    config, issues = load_config()
    decision = classify(script.read_text(encoding="utf-8"))["decision"] if config.reads else "DISABLED"
    admitted = decision == "A1_ADMIT"
    config_admission_ns = time.perf_counter_ns() - t
    entries: dict[str, dict] = {}
    failures: list[dict] = []
    t = time.perf_counter_ns()
    sources = [p for p in sorted(workdir.glob("*.xlsx")) if ".tmp" not in p.name] if admitted else []
    discovery_ns = time.perf_counter_ns() - t
    for source in sources:
        resolved = str(source.resolve())
        try:
            t = time.perf_counter_ns()
            digest = parent_artifact.sha_file(source)
            source_hash_ns = time.perf_counter_ns() - t
            t = time.perf_counter_ns()
            artifact, witness, phases = parent_artifact.ensure(source, cache_root, digest)
            entries[resolved] = {"status": witness, "source_sha256": digest,
                                 "artifact_path": str(artifact.resolve()),
                                 "source_hash_ns": source_hash_ns,
                                 "ensure_ns": time.perf_counter_ns() - t,
                                 "phases": phases}
        except Exception as exc:
            entries[resolved] = {"status": "UNAVAILABLE", "reason": type(exc).__name__}
            failures.append({"path": resolved, "exception_class": type(exc).__name__,
                             "message": str(exc)[:300]})
    context = {"script": str(script), "events": str(run_dir / "runtime_events.jsonl"),
               "runtime_profile": str(run_dir / "runtime_profile.json"),
               "admitted": admitted, "workbooks": entries}
    setup = {"read_gate": decision, "admitted": admitted, "artifacts": entries,
             "setup_failures": failures, "issues": issues,
             "profile_ns": {"config_admission": config_admission_ns,
                            "discovery": discovery_ns,
                            "pre_runtime": time.perf_counter_ns() - _started},
             "runtime_installed": False}
    setup_path = run_dir / "setup.json"
    setup_path.write_text(json.dumps(setup, sort_keys=True, default=str) + "\n")
    t = time.perf_counter_ns()
    from read_engine_phase3.runtime import Runtime
    runtime = Runtime(context, _started)
    runtime.install()
    setup["profile_ns"]["runtime_import_install"] = time.perf_counter_ns() - t
    setup["profile_ns"]["bootstrap_total"] = time.perf_counter_ns() - _started
    setup["runtime_installed"] = True
    setup_path.write_text(json.dumps(setup, sort_keys=True, default=str) + "\n")


if _context_path:
    try:
        _run(Path(_context_path))
    except Exception as exc:
        # Match frozen startup's fail-open reference route, but leave a witness
        # so the Phase-6 correctness gate rejects this command for direct speed.
        try:
            lines = Path(_context_path).read_text().splitlines()
            run_dir = Path(lines[3])
            (run_dir / "bootstrap_failure.json").write_text(
                json.dumps({"exception_class": type(exc).__name__, "message": str(exc)[:300]}) + "\n")
        except Exception:
            pass
