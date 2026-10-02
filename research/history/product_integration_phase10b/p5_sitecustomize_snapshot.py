"""Guarded startup for an ordinary Python script launched by LibreCalc."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, default=str) + "\n")


# These substrings are the definitive, non-range A0 lexical blockers in the
# frozen whole-script classifier. It preserves each as a reference-only
# decision regardless of AST analysis. A match can only decline acceleration.
_DEFINITE_REFERENCE_NEEDLES = (
    ".save(", "data_only=true", "data_only = true", "read_only=true",
    "read_only = true", "write_only", "zipfile", ".font", ".fill",
    ".border", ".alignment", ".comment", ".hyperlink", ".number_format",
    ".style", ".merged_cells", ".tables", ".defined_names", ".worksheets",
    ".active", ".iter_rows(", ".iter_cols(", ".values", ".value =",
    ".value=", "eval(", "exec(", "def ", "lambda",
)


def _definite_reference(source: str) -> bool:
    low = source.lower()
    return any(needle in low for needle in _DEFINITE_REFERENCE_NEEDLES)


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

    preloaded_source = None
    default_config = not any(os.environ.get(key) for key in (
        "LIBRECALC_CONFIG", "LIBRECALC_NO_RUNTIME", "LIBRECALC_EFFECTIVE_CONFIG"))
    if default_config:
        preloaded_source = script.read_text(encoding="utf-8")
        if _definite_reference(preloaded_source):
            _write(run_dir / "setup.json", {
                "script": str(script), "read_gate": "PREDECLARED_REAL_OPENPYXL",
                "route": "REFERENCE_FAST_PATH", "admitted": False,
                "runtime_installed": False, "artifacts": {}, "fallback": [],
                "issues": [], "merged_certificate": {"certified": False,
                                                       "reason": "NOT_ADMITTED"},
                "negative_proof": "FROZEN_A0_LEXICAL_BLOCKER",
            })
            return

    from librecalc_agent.config import Config, load as load_config
    from librecalc_agent._frozen.eligibility import classify

    effective = os.environ.get("LIBRECALC_EFFECTIVE_CONFIG")
    if effective:
        config, issues = Config(**json.loads(effective)), []
    else:
        config, issues = load_config(os.environ.get("LIBRECALC_CONFIG"),
                                    os.environ.get("LIBRECALC_NO_RUNTIME") == "1")
    source = (preloaded_source if preloaded_source is not None else
              script.read_text(encoding="utf-8")) if config.reads else ""
    decision = classify(source) if config.reads else {"decision": "DISABLED"}
    admitted = decision["decision"] == "A1_ADMIT"
    setup = {"script": str(script), "read_gate": decision["decision"],
             "route": "REFERENCE_FAST_PATH", "admitted": admitted,
             "runtime_installed": False, "artifacts": {}, "fallback": [],
             "issues": issues, "merged_certificate": {"certified": False,
                                                     "reason": "NOT_ADMITTED"}}
    if not admitted:
        _write(run_dir / "setup.json", setup)
        return

    from librecalc_agent.read_engine import cache
    from librecalc_agent.read_engine.certificate import certify

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
    from librecalc_agent.read_engine.runtime import Runtime

    context = {"script": str(script), "admitted": True,
               "workbooks": entries,
               "merged_terminal_certified": bool(certificate["certified"]),
               "runtime_state": str(run_dir / "runtime_state.json")}
    Runtime(context, started_ns).install()
    setup["route"] = "DIRECT_RUNTIME"
    setup["runtime_installed"] = True
    _write(run_dir / "setup.json", setup)


_context = os.environ.get("LIBRECALC_RUN_CONTEXT")
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
