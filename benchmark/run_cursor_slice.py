#!/usr/bin/env python3
"""Run a frozen SpreadsheetBench 2 slice through Cursor in an isolated container."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"
DEFAULT_CURSOR_AUTH = Path.home() / ".config" / "cursor" / "auth.json"
DEFAULT_CURSOR_BINARY = Path.home() / ".local" / "bin" / "agent"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--cursor-auth", type=Path, default=DEFAULT_CURSOR_AUTH)
    parser.add_argument("--cursor-binary", type=Path, default=DEFAULT_CURSOR_BINARY)
    parser.add_argument("--image", default="spreadsheetbench-v2")
    parser.add_argument("--model", help="Override the model recorded in the slice definition.")
    parser.add_argument(
        "--task",
        action="append",
        help="Run only CATEGORY:ID; repeat for multiple tasks. Defaults to the whole slice.",
    )
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted Cursor session and its private partial workbook.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _task_record(benchmark_root: Path, category: str, task_id: str) -> dict[str, Any]:
    dataset_path = benchmark_root / "data" / category / "dataset.json"
    records = _load_json(dataset_path)
    matches = [record for record in records if record["id"] == task_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one {category}:{task_id} record, found {len(matches)}")
    return matches[0]


def _prompt(instruction: str, max_tool_calls: int) -> str:
    return f"""You are completing an isolated SpreadsheetBench 2 task through LibreOffice Calc.

Use the shell tool only for these commands:
- calc_inspect /mnt/input/input.xlsx
- calc_read <input-or-output-path> <sheet> <range>
- calc_program <input-or-output-path> /mnt/output/output.xlsx <operations-json>
- calc_write <input-or-output-path> /mnt/output/output.xlsx <sheet> <range> <values-json>

Do not explore the filesystem, source code, environment, or installed programs. Do not use Python,
package libraries, direct archive/XML editing, or LibreOffice CLI to inspect or modify the workbook.
The Calc commands are the complete spreadsheet interface being evaluated.

calc_program takes a JSON array with these operation forms:
- {{"op":"write_range","sheet":"Sheet1","range":"A1:B2","values":[[1,2],[3,4]]}}
- {{"op":"set_formula","sheet":"Sheet1","range":"C2","formula":"=A2+B2"}}
- {{"op":"fill_formula","sheet":"Sheet1","range":"C2:G2","formula":"=A2+B2"}}
- {{"op":"clear_range","sheet":"Sheet1","range":"C2:G2"}}
- {{"op":"create_sheet","name":"Analysis","index":0}}
- {{"op":"insert_row","sheet":"Sheet1","index":5,"count":1}}
- {{"op":"delete_row","sheet":"Sheet1","index":8,"count":1}}

For fill_formula, the formula is written to the top-left cell and Calc autofills relative references
across and down the entire range. Combine all known operations into one JSON array when practical.

You have at most {max_tool_calls} shell tool calls. Inspect first, read focused ranges, preserve existing
populated cells unless the instruction requires changing them, and prefer fill_formula for repeated
relative formulas. Repayment, expense, and cash-flow rows may use signed conventions: infer them from
labels, neighboring formulas, checks, and existing values instead of assuming every magnitude is
positive. Write /mnt/output/output.xlsx, read it back to verify formulas and calculated values, and
finish only after the output exists. Do not merely describe the solution.

Instruction:
{instruction}
"""


def _json_events(paths: list[Path]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    events.append(value)
    return events


def _resume_details(trace_directory: Path, max_tool_calls: int) -> tuple[str, int, Path]:
    traces = sorted(trace_directory.glob("cursor*.stream.jsonl"))
    if not traces:
        raise FileNotFoundError("No Cursor trace is available to resume")
    events = _json_events(traces)
    sessions = [event.get("session_id") for event in events if event.get("type") == "system"]
    session_id = next((value for value in reversed(sessions) if isinstance(value, str)), None)
    if session_id is None:
        raise ValueError("No Cursor session id was found in the traces")
    used_calls = sum(
        event.get("type") == "tool_call" and event.get("subtype") == "started" for event in events
    )
    remaining_calls = max_tool_calls - used_calls
    if remaining_calls <= 0:
        raise RuntimeError(f"Cannot resume: all {max_tool_calls} tool calls were used")
    trace_path = trace_directory / f"cursor.resume-{len(traces)}.stream.jsonl"
    return session_id, remaining_calls, trace_path


def _cursor_directory(cursor_binary: Path) -> Path:
    resolved = cursor_binary.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Cursor binary not found: {cursor_binary}")
    return resolved.parent


def _selected_tasks(slice_data: dict[str, Any], filters: list[str] | None) -> list[dict[str, str]]:
    tasks = slice_data["tasks"]
    if not filters:
        return tasks
    requested = set(filters)
    selected = [task for task in tasks if f"{task['category']}:{task['id']}" in requested]
    found = {f"{task['category']}:{task['id']}" for task in selected}
    missing = requested - found
    if missing:
        raise ValueError(f"Tasks are not in the slice: {', '.join(sorted(missing))}")
    return selected


def _run_task(
    *,
    task: dict[str, str],
    slice_data: dict[str, Any],
    args: argparse.Namespace,
    cursor_directory: Path,
) -> int:
    category = task["category"]
    task_id = task["id"]
    record = _task_record(args.benchmark_root, category, task_id)
    input_path = args.benchmark_root / "data" / category / record["spreadsheet_path"]
    if not input_path.is_file():
        raise FileNotFoundError(f"Task input not found: {input_path}")

    output_directory = (
        args.benchmark_root
        / "SWE-agent"
        / "trajectories"
        / "output_excel"
        / category
        / args.run_name
    )
    trace_directory = (
        args.benchmark_root
        / "SWE-agent"
        / "trajectories"
        / "cursor"
        / args.run_name
        / f"{category}-{task_id}"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    trace_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{task_id}_output.xlsx"
    private_output_directory = trace_directory / "task-output"
    private_output_directory.mkdir(parents=True, exist_ok=True)
    private_output_path = private_output_directory / "output.xlsx"
    trace_path = trace_directory / "cursor.stream.jsonl"
    cursor_home = trace_directory / "cursor-home"
    (cursor_home / ".config" / "cursor").mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing result: {output_path}")
    if private_output_path.exists() and not args.resume:
        raise FileExistsError(
            f"Refusing to reuse an existing private output: {private_output_path}"
        )

    max_tool_calls = slice_data["max_tool_calls_per_task"]
    call_limit_for_attempt = max_tool_calls
    resume_session_id: str | None = None
    if args.resume:
        resume_session_id, remaining_calls, trace_path = _resume_details(
            trace_directory, max_tool_calls
        )
        call_limit_for_attempt = remaining_calls
        prompt = (
            "Resume the interrupted spreadsheet task. The provider failed after your last recorded "
            f"action; you have {remaining_calls} of the original {max_tool_calls} tool calls left. "
            "A partial workbook may exist at /mnt/output/output.xlsx. Continue from it rather than "
            "starting over, verify the completed workbook, and finish the task."
        )
    else:
        if trace_path.exists():
            raise FileExistsError(f"Refusing to overwrite an existing trace: {trace_path}")
        prompt = _prompt(record["instruction"], max_tool_calls)
    model = args.model or slice_data["model"]
    resume_option = f"--resume {resume_session_id} " if resume_session_id else ""
    wrapper_mounts: list[str] = []
    for command_name in ("calc_inspect", "calc_read", "calc_write", "calc_program"):
        wrapper = (PROJECT_ROOT / "benchmark/sweagent/librecalc/bin" / command_name).resolve()
        wrapper_mounts.extend(
            [
                "--mount",
                f"type=bind,src={wrapper},dst=/usr/local/bin/{command_name},readonly",
            ]
        )
    docker_command = [
        "docker",
        "run",
        "--rm",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        *wrapper_mounts,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--env",
        "HOME=/home/benchmark",
        "--env",
        "LIBRECALC_TOOL_ROOT=/opt/librecalc-tools/librecalc",
        "--mount",
        f"type=bind,src={input_path.resolve()},dst=/mnt/input/input.xlsx,readonly",
        "--mount",
        f"type=bind,src={private_output_directory.resolve()},dst=/mnt/output",
        "--mount",
        f"type=bind,src={(PROJECT_ROOT / 'src').resolve()},dst=/opt/librecalc/src,readonly",
        "--mount",
        (
            "type=bind,"
            f"src={(PROJECT_ROOT / 'benchmark/sweagent/librecalc').resolve()},"
            "dst=/opt/librecalc-tools/librecalc,readonly"
        ),
        "--mount",
        f"type=bind,src={cursor_directory},dst=/opt/cursor,readonly",
        "--mount",
        f"type=bind,src={cursor_home.resolve()},dst=/home/benchmark",
        "--mount",
        (
            f"type=bind,src={args.cursor_auth.resolve()},"
            "dst=/home/benchmark/.config/cursor/auth.json,readonly"
        ),
        "--workdir",
        "/work",
        args.image,
        "bash",
        "-lc",
        (
            "source /opt/librecalc-tools/librecalc/install.sh && "
            "export PATH=/opt/librecalc-tools/librecalc/bin:/opt/cursor:$PATH && "
            "command -v calc_inspect >/dev/null && "
            "exec /opt/cursor/cursor-agent --print --output-format stream-json "
            f"--model {model} {resume_option}--force --sandbox disabled --trust "
            '--workspace /work "$0"'
        ),
        prompt,
    ]

    print(f"START {category}:{task_id} -> {output_path}", flush=True)
    timed_out = threading.Event()
    budget_exceeded = False
    started_calls = 0
    with trace_path.open("w", encoding="utf-8") as trace:
        process = subprocess.Popen(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def interrupt_on_timeout() -> None:
            timed_out.set()
            if process.poll() is None:
                process.send_signal(signal.SIGINT)

        timer = threading.Timer(args.timeout, interrupt_on_timeout)
        timer.start()
        assert process.stdout is not None
        try:
            for line in process.stdout:
                trace.write(line)
                trace.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "tool_call" and event.get("subtype") == "started":
                    started_calls += 1
                    if started_calls > call_limit_for_attempt:
                        budget_exceeded = True
                        process.send_signal(signal.SIGINT)
                        break
            try:
                return_code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait()
        finally:
            timer.cancel()

    if timed_out.is_set():
        print(f"TIMEOUT {category}:{task_id} after {args.timeout}s", flush=True)
        return 124
    if budget_exceeded:
        print(
            f"BUDGET {category}:{task_id} attempted more than {max_tool_calls} total tool calls",
            flush=True,
        )
        return 125
    if return_code != 0:
        print(f"ERROR {category}:{task_id} cursor_exit={return_code}", flush=True)
        return return_code
    if not private_output_path.is_file():
        print(f"ERROR {category}:{task_id} produced no workbook", flush=True)
        return 2

    shutil.copy2(private_output_path, output_path)

    print(
        f"DONE {category}:{task_id} bytes={output_path.stat().st_size} trace={trace_path}",
        flush=True,
    )
    return 0


def main() -> int:
    args = _arguments()
    args.slice = args.slice.resolve()
    args.benchmark_root = args.benchmark_root.resolve()
    args.cursor_auth = args.cursor_auth.resolve()

    if not args.cursor_auth.is_file():
        raise FileNotFoundError(f"Cursor authentication not found: {args.cursor_auth}")
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required")

    slice_data = _load_json(args.slice)
    tasks = _selected_tasks(slice_data, args.task)
    cursor_directory = _cursor_directory(args.cursor_binary)
    failures = 0
    for task in tasks:
        return_code = _run_task(
            task=task,
            slice_data=slice_data,
            args=args,
            cursor_directory=cursor_directory,
        )
        failures += return_code != 0
    print(f"SUMMARY tasks={len(tasks)} failures={failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
