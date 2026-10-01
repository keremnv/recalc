"""Launch an ordinary script under the package-owned external observer."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .diagnostics import libreoffice


class ProductError(Exception):
    """An invocation could not safely start; the target script was not run."""


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def observer_binary() -> Path:
    return Path(__file__).parent / "native" / "observer"


def _prepare(script: Path, args: list[str], workdir: Path, config: Config,
             require_lo: bool) -> tuple[list[str], dict[str, str], Path | None, Path | None]:
    script, workdir = script.resolve(), workdir.resolve()
    if not script.is_file() or not workdir.is_dir():
        raise ProductError("Script or working directory does not exist; no task was run.")
    if require_lo and not libreoffice()["available"]:
        raise ProductError("LibreOffice is required for this invocation but is unavailable; no task was run.")
    # Only internal handoff keys are filtered; everything else (user env,
    # PATH, FD markers) inherits so the target matches direct Python.
    env = {k: v for k, v in os.environ.items()
           if k not in {"LIBRECALC_RUN_CONTEXT", "LIBRECALC_EFFECTIVE_CONFIG"}}
    # The observer changes cwd before launching the real script. Preserve the
    # caller's import paths as absolute paths, including a source checkout.
    import_root = str(Path(__file__).resolve().parents[1])
    inherited = [str((Path.cwd() / part).resolve()) if part else str(Path.cwd())
                 for part in env.get("PYTHONPATH", "").split(os.pathsep) if part]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys([import_root, *inherited]))
    if not config.enabled:
        return [sys.executable, str(script), *args], env, None, None
    binary = observer_binary()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ProductError("The external observer is unavailable. Reinstall a supported platform wheel; no task was run.")
    cache = Path(config.cache_dir).expanduser().absolute()
    try:
        if cache.is_symlink():
            raise OSError("symlinked cache root")
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        runs = cache / "runs"
        if runs.is_symlink():
            raise OSError("symlinked run root")
        runs.mkdir(mode=0o700, exist_ok=True)
        for directory in (cache, runs):
            stat = directory.stat()
            if stat.st_uid != os.getuid():
                raise OSError("cache/run directory is not user-owned")
            if stat.st_mode & 0o077:
                directory.chmod(0o700)
            if not os.access(directory, os.W_OK):
                raise OSError("cache/run directory must be user-owned and private")
    except OSError as exc:
        raise ProductError("The observer cannot write the cache/run directory; no task was run.") from exc
    env["LIBRECALC_EFFECTIVE_CONFIG"] = json.dumps(asdict(config), sort_keys=True)
    env["LIBRECALC_CAPTURE_ENABLED"] = "1" if config.assurance else "0"
    pointer = runs / f"receipt-{uuid.uuid4().hex}.json"
    env["LIBRECALC_RECEIPT_POINTER"] = str(pointer)
    bootstrap = Path(__file__).parent / "_bootstrap"
    helper = Path(__file__).parent / "_capture_helper.py"
    command = [str(binary), sys.executable, str(script), str(workdir), str(cache),
               str(runs), str(bootstrap), str(helper), *args]
    return command, env, cache, pointer


def read_last_receipt(cache: Path, pointer_path: Path | None = None) -> dict:
    pointer = _json(pointer_path or cache / "runs" / "last_run.json")
    raw = pointer.get("run_dir")
    if not isinstance(raw, str):
        return {}
    run_dir = Path(raw)
    # The observer creates run directories inside the selected user cache.
    if run_dir.parent.resolve() != (cache / "runs").resolve():
        return {}
    observer = _json(run_dir / "observer_receipt.json")
    setup = _json(run_dir / "setup.json")
    runtime = _json(run_dir / "runtime_state.json")
    capture = _json(run_dir / "capture_state.json")
    bootstrap_failure = _json(run_dir / "bootstrap_failure.json")
    if not observer:
        return {"invocation_id": run_dir.name, "assurance_status": "FAILED",
                "failure_code": "OBSERVER_RECEIPT_MISSING", "run_dir": str(run_dir)}
    assurance = observer.get("assurance_status", "FAILED")
    if observer.get("changed_xlsx") and assurance == "PASS" and (not capture or not capture.get("validation_passed")):
        assurance = "FAILED"
    if bootstrap_failure:
        assurance = "FAILED" if setup.get("route") == "DIRECT_RUNTIME" else assurance
    route = runtime.get("route") or setup.get("route") or "REFERENCE_FAST_PATH"
    admitted = bool(setup.get("admitted"))
    if bootstrap_failure:
        route = "REFERENCE_FAST_PATH"
        admitted = False
    if bootstrap_failure:
        admission_reason = "setup-failed"
    elif admitted:
        admission_reason = "admitted"
    elif setup.get("admission_decision") == "DISABLED":
        admission_reason = "runtime-disabled"
    else:
        admission_reason = "not-admitted"
    artifacts = setup.get("artifacts") or {}
    statuses = sorted({entry.get("status") for entry in artifacts.values()
                       if isinstance(entry, dict) and entry.get("status")})
    served = (runtime.get("counts") or {}).get("direct_served_loads", 0)
    if not served and "REUSED" in statuses:
        statuses = ["REUSE_NOT_CONFIRMED" if status == "REUSED" else status
                    for status in statuses]
    fallback = list(setup.get("fallback") or [])
    fallback.extend({"reason": reason} for reason in runtime.get("fallback_reasons", []))
    return {"invocation_id": run_dir.name, "route": route,
            "admitted": admitted, "admission_reason": admission_reason,
            "artifact": statuses or ["NOT_APPLICABLE"],
            "direct_served_loads": served,
            "fallback": fallback,
            "target_status": {"exit_code": observer.get("target_exit_code"),
                              "signal": observer.get("target_signal")},
            "assurance_status": assurance,
            "effect_capture_status": "PASS" if observer.get("changed_xlsx") and assurance == "PASS"
            else "FAILED" if observer.get("changed_xlsx") and assurance == "FAILED"
            else "NOT_REQUESTED" if observer.get("changed_xlsx") else "NOT_APPLICABLE",
            "capture_records": capture.get("records", 0),
            "validation_status": "PASS" if capture.get("validation_passed") is True
            else "FAILED" if observer.get("changed_xlsx") and assurance == "FAILED"
            else "NOT_REQUESTED" if observer.get("changed_xlsx") else "NOT_APPLICABLE",
            "failure_code": "DIRECT_SETUP_UNAVAILABLE" if bootstrap_failure else
            "ASSURANCE_FAILURE" if assurance != "PASS" else None,
            "run_dir": str(run_dir)}


def run(script: Path, args: list[str], workdir: Path, config: Config,
        issues: list[dict], require_lo: bool = False) -> tuple[int, dict]:
    """Library/testing API. The CLI uses exec_run to avoid retaining a Python parent."""
    command, env, cache, pointer = _prepare(script, args, workdir, config, require_lo)
    if issues and config.verbosity != "quiet":
        for issue in issues:
            print(f"WARNING: {issue['message']}", file=sys.stderr)
    proc = subprocess.run(command, cwd=workdir.resolve(), env=env, check=False)
    if cache is None:
        return proc.returncode, {"route": "REFERENCE_FAST_PATH", "admitted": False,
                                 "admission_reason": "runtime-disabled",
                                 "artifact": ["NOT_APPLICABLE"],
                                 "assurance_status": "NOT_REQUESTED", "target_status": {
                                     "exit_code": proc.returncode, "signal": 0}}
    summary = read_last_receipt(cache, pointer)
    if pointer:
        pointer.unlink(missing_ok=True)
    if summary.get("assurance_status") == "FAILED" and proc.returncode == 0:
        return 125, summary
    return proc.returncode, summary


def exec_run(script: Path, args: list[str], workdir: Path, config: Config,
             issues: list[dict], require_lo: bool = False) -> None:
    """Replace the CLI interpreter with the observer or direct Python process."""
    command, env, _, _ = _prepare(script, args, workdir, config, require_lo)
    if issues and config.verbosity != "quiet":
        for issue in issues:
            print(f"WARNING: {issue['message']}", file=sys.stderr, flush=True)
    os.chdir(workdir.resolve())
    os.execve(command[0], command, env)
