"""Phase-9 pay-for-play overlay for the unchanged Phase-6 external observer."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_started = time.perf_counter_ns()
_context_path = os.environ.get("READ_ENGINE_PHASE6_CONTEXT")
_root = Path(__file__).resolve().parents[4]


def _run(path: Path) -> None:
    script_s, workdir_s, cache_s, run_dir_s = path.read_text().splitlines()
    script = Path(script_s).resolve()
    workdir = Path(workdir_s).resolve()
    cache_root = Path(cache_s)
    run_dir = Path(run_dir_s)
    if Path(sys.argv[0]).resolve() != script:
        return
    sys.path.append(str(_root))
    from librecalc_agent.config import load as load_config
    from librecalc_agent._frozen.eligibility import classify

    t = time.perf_counter_ns()
    config, issues = load_config()
    source = script.read_text(encoding="utf-8") if config.reads else ""
    decision = classify(source) if config.reads else {"decision": "DISABLED"}
    admitted = decision["decision"] == "A1_ADMIT"
    config_admission_ns = time.perf_counter_ns() - t
    setup_path = run_dir / "setup.json"

    if not admitted:
        # The frozen runtime already routes this whole script to reference
        # openpyxl. Leave its module and load_workbook object untouched.
        import atexit

        after_decision_ns = time.perf_counter_ns()
        setup = {
            "read_gate": decision["decision"],
            "admitted": False,
            "artifacts": {},
            "merged_certificate": {"certified": False, "reason": "NOT_ADMITTED"},
            "setup_failures": [],
            "issues": issues,
            "fast_path": "FAST_PATH_PROVEN_REFERENCE",
            "profile_ns": {
                "config_admission": config_admission_ns,
                "discovery": 0,
                "pre_runtime": after_decision_ns - _started,
                "runtime_import_install": 0,
                "bootstrap_total": after_decision_ns - _started,
            },
            "runtime_installed": False,
        }
        setup_path.write_text(json.dumps(setup, sort_keys=True, default=str) + "\n")

        def finish_reference_only() -> None:
            end = time.perf_counter_ns()
            profile = {
                "bootstrap_ns": after_decision_ns - _started,
                "post_bootstrap_to_exit_ns": end - after_decision_ns,
                "times": {"artifact_load_ns": 0, "reference_parse_ns": None,
                          "child_source_hash_ns": 0},
                "counts": {"direct_served_loads": 0, "direct_served_reads": 0,
                           "reference_loads": None, "fallback_loads": None},
                "script_identity_verified": True,
                "fast_path": "FAST_PATH_PROVEN_REFERENCE",
                "reference_call_count_observed": False,
            }
            try:
                (run_dir / "runtime_profile.json").write_text(
                    json.dumps(profile, sort_keys=True) + "\n")
                (run_dir / "runtime_events.jsonl").write_text(
                    json.dumps({"event": "proven_reference_route",
                                "reason": decision["decision"]}, sort_keys=True) + "\n")
            except OSError:
                pass

        atexit.register(finish_reference_only)
        return

    from read_engine_phase4 import parent_artifact
    from read_engine_phase8a.certificate import certify

    certificate = certify(source, decision)
    entries: dict[str, dict] = {}
    failures: list[dict] = []
    t = time.perf_counter_ns()
    sources = [p for p in sorted(workdir.glob("*.xlsx")) if ".tmp" not in p.name]
    discovery_ns = time.perf_counter_ns() - t
    for source_path in sources:
        resolved = str(source_path.resolve())
        try:
            t = time.perf_counter_ns()
            digest = parent_artifact.sha_file(source_path)
            source_hash_ns = time.perf_counter_ns() - t
            t = time.perf_counter_ns()
            artifact, witness, phases = parent_artifact.ensure(source_path, cache_root, digest)
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
               "admitted": True, "workbooks": entries,
               "merged_terminal_certified": bool(certificate["certified"])}
    setup = {"read_gate": decision["decision"], "admitted": True, "artifacts": entries,
             "merged_certificate": certificate,
             "setup_failures": failures, "issues": issues,
             "fast_path": None,
             "profile_ns": {"config_admission": config_admission_ns,
                            "discovery": discovery_ns,
                            "pre_runtime": time.perf_counter_ns() - _started},
             "runtime_installed": False}
    setup_path.write_text(json.dumps(setup, sort_keys=True, default=str) + "\n")
    t = time.perf_counter_ns()
    from read_engine_phase7.merge_runtime import install_cell_route
    from read_engine_phase3.runtime import Runtime
    install_cell_route()
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
        try:
            lines = Path(_context_path).read_text().splitlines()
            run_dir = Path(lines[3])
            (run_dir / "bootstrap_failure.json").write_text(
                json.dumps({"exception_class": type(exc).__name__,
                            "message": str(exc)[:300]}) + "\n")
        except Exception:
            pass
