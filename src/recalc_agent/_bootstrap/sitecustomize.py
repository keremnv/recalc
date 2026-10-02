"""Guarded startup for an ordinary Python script launched by recalc."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, default=str) + "\n")


def _start(context_path: Path) -> None:
    started_ns = time.perf_counter_ns()
    lines = context_path.read_text().splitlines()
    if len(lines) != 4:
        raise ValueError("invalid observer context")
    script_s, workdir_s, cache_s, run_dir_s = lines
    script = Path(script_s).resolve()
    if Path(sys.argv[0]).resolve() != script:
        return
    workdir, cache_root, run_dir = Path(workdir_s), Path(cache_s), Path(run_dir_s)
    from recalc_agent.config import Config, load as load_config
    from recalc_agent._frozen.eligibility import classify

    effective = os.environ.get("RECALC_EFFECTIVE_CONFIG")
    if effective:
        config, issues = Config(**json.loads(effective)), []
    else:
        config, issues = load_config(os.environ.get("RECALC_CONFIG"),
                                    os.environ.get("RECALC_NO_RUNTIME") == "1")
    source = script.read_text(encoding="utf-8") if config.reads_effective else ""
    decision = classify(source) if config.reads_effective else {"decision": "DISABLED"}
    admitted = decision["decision"] == "A1_ADMIT"
    setup = {"script": str(script), "admission_decision": decision["decision"],
             "route": "REFERENCE_FAST_PATH", "admitted": admitted,
             "runtime_installed": False, "artifacts": {}, "fallback": [],
             "issues": issues, "merged_certificate": {"certified": False,
                                                     "reason": "NOT_ADMITTED"}}
    if not admitted:
        _write(run_dir / "setup.json", setup)
        return

    from recalc_agent.read_engine import cache
    from recalc_agent.read_engine.certificate import certify

    certificate = certify(source, decision)
    setup["merged_certificate"] = certificate
    entries: dict[str, dict] = {}
    for path in sorted(workdir.glob("*.xlsx")):
        if ".tmp" in path.name:
            continue
        resolved = str(path.resolve())
        try:
            digest = cache.sha_file(path)
            artifact, status, _ = cache.ensure(path, cache_root, digest)
            entries[resolved] = {"status": status, "source_sha256": digest,
                                 "artifact_path": str(artifact.resolve())}
        except Exception as exc:  # optional acceleration cannot veto reference execution
            entries[resolved] = {"status": "UNAVAILABLE", "reason": type(exc).__name__}
            setup["fallback"].append({"reason": "artifact_unavailable",
                                      "exception_class": type(exc).__name__,
                                      "path": resolved})
    setup["artifacts"] = entries
    _write(run_dir / "setup.json", setup)
    from recalc_agent.read_engine.runtime import Runtime

    context = {"script": str(script), "admitted": True,
               "workbooks": entries,
               "merged_terminal_certified": bool(certificate["certified"]),
               "runtime_state": str(run_dir / "runtime_state.json")}
    Runtime(context, started_ns).install()
    setup["route"] = "DIRECT_RUNTIME"
    setup["runtime_installed"] = True
    _write(run_dir / "setup.json", setup)


_context = os.environ.get("RECALC_RUN_CONTEXT")
if _context:
    try:
        _start(Path(_context))
    except Exception as exc:  # sitecustomize must leave ordinary Python available
        try:
            lines = Path(_context).read_text().splitlines()
            if len(lines) == 4:
                _write(Path(lines[3]) / "bootstrap_failure.json",
                       {"exception_class": type(exc).__name__,
                        "message": str(exc)[:300]})
        except Exception:
            pass
