"""Small shell entry point; the coding agent and model remain external."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .config import load
from .diagnostics import check, status
from .runner import ProductError, exec_run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="recalc-agent", description="Run ordinary Python workbook scripts with optional invisible runtime.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    example = commands.add_parser("example", help="Copy a small ordinary Python example into a new directory.")
    example.add_argument("directory", type=Path)
    for name in ("doctor", "status", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", help="Runtime TOML file; alternatively RECALC_CONFIG.")
        sub.add_argument("--no-runtime", action="store_true", help="Use ordinary Python/openpyxl only.")
        if name != "run":
            sub.add_argument("--json", action="store_true", help="Machine-readable diagnostic output.")
            sub.add_argument("--verbose", action="store_true", help="Print the full JSON report (same as --json).")
        if name in {"doctor", "run"}:
            sub.add_argument("--require-libreoffice", action="store_true", help="Fail preflight if LibreOffice is unavailable; does not itself recalculate.")
        if name == "run":
            sub.add_argument("--workdir", type=Path, default=Path.cwd(), help="Workbook working directory (default: current directory).")
            sub.add_argument("script", type=Path)
            sub.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == "example":
        source = Path(__file__).parent / "example"
        if not source.is_dir():
            source = Path(__file__).resolve().parents[2] / "examples/basic"
        files = [source / name for name in ("create_input.py", "update.py", "read.py", "runtime.toml")]
        if any((args.directory / p.name).exists() for p in files):
            print("FAIL: Example files already exist. Choose a new directory; no files were overwritten.", file=sys.stderr)
            return 2
        try:
            args.directory.mkdir(parents=True, exist_ok=True)
            for path in files:
                shutil.copy2(path, args.directory / path.name)
        except OSError as exc:
            print(f"FAIL: Cannot copy the example ({type(exc).__name__}). Choose a writable directory.", file=sys.stderr)
            return 2
        print(f"Example copied to {args.directory.resolve()}")
        return 0
    config, issues = load(args.config, args.no_runtime)
    if args.command == "run":
        try:
            exec_run(args.script, args.script_args, args.workdir, config, issues,
                     args.require_libreoffice)
            raise AssertionError("exec_run returned after process replacement")
        except (ProductError, OSError) as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 2
    report = status(config, issues) if args.command == "status" else check(config, issues, args.require_libreoffice)
    if args.json or args.verbose:
        print(json.dumps(report, indent=2))
    else:
        print(f"recalc-agent {__version__} | Python {report['python']} | openpyxl {report['versions'].get('openpyxl')}")
        for item in report["checks"]:
            print(f"{item['status']}: {item['check']}: {item['message']}")
        print(f"Runtime: {'enabled' if config.enabled else 'disabled'}; read acceleration: {'enabled' if config.reads_effective else 'disabled'}; capture: {'enabled' if config.assurance else 'disabled'}")
        print(f"Direct reads available: {report['direct_read_engine_available']}; cache: {config.cache_dir}")
        summary = report["cache_summary"]
        truncated = ", scan truncated" if summary["truncated"] else ""
        print(f"Cache use: {summary['file_count']} files, {summary['total_bytes']} bytes "
              f"({summary['artifact_count']} artifacts, {summary['run_count']} runs{truncated}); "
              f"safe to delete while idle")
        print(f"Diagnostic logs: {Path(config.cache_dir) / 'runs'}")
        if args.command == "status":
            last = report["last_run"]
            print("Last run: " + (f"route={last.get('route')}, target={last.get('target_status')}, assurance={last.get('assurance_status')}; see --verbose for details" if last else "none recorded"))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
