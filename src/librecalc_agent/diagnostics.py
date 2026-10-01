"""Credential-free, local dependency and configuration checks."""
from __future__ import annotations

import importlib
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .config import Config

_MAX_SCAN_FILES = 5000


def writable(directory: Path) -> tuple[bool, str]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".doctor-") as stream:
            stream.write(b"ok")
            stream.flush()
        return True, "Directory is writable."
    except OSError as exc:
        return False, f"Cache is unavailable ({type(exc).__name__}). Ordinary Python can continue. Choose a writable runtime.cache_dir."


def cache_summary(cache_dir: Path) -> dict:
    """Bounded cache inventory for visibility (no retention promise).

    Walks at most _MAX_SCAN_FILES entries so a huge cache cannot stall
    `doctor`/`status`; sets `truncated` when the cap hits. Counts derived
    artifacts (`read-engine/*.r3jz`) and run receipts (`runs/run-*`).
    """
    root = cache_dir.expanduser()
    summary: dict = {"path": str(root), "exists": root.is_dir(),
                     "total_bytes": 0, "file_count": 0, "artifact_count": 0,
                     "run_count": 0, "truncated": False,
                     "guidance": ("Derived state and receipts only; safe to "
                                  "delete while no invocation uses them. No "
                                  "automatic eviction is performed.")}
    if not summary["exists"]:
        return summary
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    summary["total_bytes"] += os.path.getsize(full)
                except OSError:
                    continue
                summary["file_count"] += 1
                if name.endswith(".r3jz"):
                    summary["artifact_count"] += 1
                if summary["file_count"] >= _MAX_SCAN_FILES:
                    summary["truncated"] = True
                    return summary
            for name in dirnames:
                if name.startswith("run-"):
                    summary["run_count"] += 1
    except OSError:
        summary["truncated"] = True
    return summary


def libreoffice() -> dict:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        return {"available": False, "executable": None, "version": None}
    try:
        proc = subprocess.run([executable, "--version"], capture_output=True,
                              text=True, timeout=10, check=False)
        return {"available": proc.returncode == 0, "executable": executable,
                "version": (proc.stdout or proc.stderr).strip()[:300]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "executable": executable, "version": None,
                "error": type(exc).__name__}


def check(config: Config, issues: list[dict], require_lo: bool = False) -> dict:
    checks = list(issues)
    checks.append({"check": "python", "status": "PASS" if (3, 11) <= sys.version_info < (3, 15) else "FAIL",
                   "message": platform.python_version()})
    versions = {}
    for name, required in [("openpyxl", True), ("lxml", False)]:
        try:
            importlib.import_module(name)
            versions[name] = importlib.metadata.version(name)
            checks.append({"check": name, "status": "PASS", "message": versions[name]})
        except Exception as exc:  # noqa: BLE001 - diagnosis never assumes optional imports work
            versions[name] = None
            checks.append({"check": name, "status": "FAIL" if required else "OPTIONAL_NOT_AVAILABLE",
                           "message": f"{name} is unavailable ({type(exc).__name__}). Reinstall with python -m pip install . in the checkout. " + ("Workbook tasks need openpyxl." if required else "openpyxl can use its standard XML parser; this differs from the pinned RC environment.")})
    available = True
    for name in ("librecalc_agent._frozen.eligibility",
                 "librecalc_agent._frozen.capture",
                 "librecalc_agent.read_engine.cache",
                 "librecalc_agent.read_engine.runtime"):
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - optional runtime must not veto ordinary Python
            available = False
            checks.append({"check": f"runtime_module:{name}", "status": "OPTIONAL_NOT_AVAILABLE",
                           "message": f"Runtime module unavailable ({type(exc).__name__}). Reinstall to restore direct reads; ordinary openpyxl remains available."})
    if available:
        checks.append({"check": "direct_runtime", "status": "PASS", "message": "Direct runtime modules import successfully."})
    from .runner import observer_binary
    observer = observer_binary()
    observer_ok = observer.is_file() and observer.stat().st_mode & 0o111 != 0
    checks.append({"check": "external_observer", "status": "PASS" if observer_ok else "FAIL",
                   "message": str(observer) if observer_ok else "No executable observer in this installation."})
    cache_ok, message = writable(Path(config.cache_dir))
    checks.append({"check": "cache", "status": "PASS" if cache_ok else "WARNING", "message": message})
    lo = libreoffice()
    checks.append({"check": "libreoffice", "status": "PASS" if lo["available"] else ("FAIL" if require_lo else "OPTIONAL_NOT_AVAILABLE"),
                   "message": lo["version"] or "LibreOffice is unavailable. Python edits can continue; install LibreOffice Calc before tasks that require recalculation or validation."})
    if not issues:
        checks.append({"check": "configuration", "status": "PASS", "message": "Runtime settings loaded. No model credentials are required; configure your coding agent separately."})
    return {"product": "librecalc-agent", "version": __version__, "python": platform.python_version(),
            "versions": versions, "platform": platform.platform(), "configuration": config.public(),
            "direct_read_engine_available": config.reads_effective and available and cache_ok and observer_ok,
            "cache_summary": cache_summary(Path(config.cache_dir)),
            "libreoffice": lo, "checks": checks,
            "pass": not any(c["status"] == "FAIL" for c in checks)}


def status(config: Config, issues: list[dict]) -> dict:
    report = check(config, issues)
    from .runner import read_last_receipt
    last = read_last_receipt(Path(config.cache_dir)) or None
    path = Path(config.cache_dir) / "runs" / "last_run.json"
    report.update(last_run=last, diagnostic_logging_location=str(Path(config.cache_dir) / "runs"),
                  last_run_record=str(path),
                  freshness="whole-file SHA-256 for direct serving" if config.reads_effective else "inactive")
    return report
