#!/usr/bin/env python3
"""Narrow read-side v2 adjudication.

This driver is deliberately an experiment harness, not a new spreadsheet
helper. Phase A reconstructs read episodes from frozen H0 trajectories and
replays only historically requested/printed facts through the current v2
surface. Phase B is an optional matched V1/V2 live probe using identical model
documentation and the same ``lx_helpers`` names.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUT = PROJECT_ROOT / "read_side_v2_adjudication"
CHECKPOINT = PROJECT_ROOT / "thin_architecture_checkpoint"
RANKING_PATH = CHECKPOINT / "exposure_ranking.json"
REPS = CHECKPOINT / "reps"
WORK = CHECKPOINT / "work"
DATA_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2" / "data"
V2_SHIM = PROJECT_ROOT / "benchmark" / "inspection_helpers" / "lx_helpers.py"
RUNNER = PROJECT_ROOT / "benchmark" / "ab_local_runner.py"

MAX_OBS = 10_000
PHASE_A_LIMIT = 10_000
SELECTION_N = 6
PHASE_B_N = 4
ORDER_SEED = 20260920

CELL_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Z]{1,3}\d+)(?![A-Za-z0-9_])")
QUOTED_CELL_RE = re.compile(r"['\"]([A-Z]{1,3}\d+)['\"]")
SHEET_RE = re.compile(r"(?:wb|workbook)\s*\[\s*['\"]([^'\"]+)['\"]\s*\]")
SHEET_LIST_RE = re.compile(r"(?:for\s+\w+\s+in\s+)?\[([^\]]+)\]")
RANGE_KW_RE = re.compile(
    r"(?:min_row\s*=\s*|range\(\s*)(\d+)\s*,\s*(?:max_row\s*=\s*)?(\d+)"
)

_SOURCE_FACTS: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_jsonl(name: str, rows: list[dict[str, Any]]) -> None:
    with (OUT / name).open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def task_source(task_id: str) -> Path:
    category, _, identifier = task_id.partition(":")
    records = json.loads((DATA_ROOT / category / "dataset.json").read_text(encoding="utf-8"))
    record = next(row for row in records if str(row["id"]) == identifier)
    return DATA_ROOT / category / record["spreadsheet_path"]


def load_messages(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def observation_after(messages: list[dict[str, Any]], index: int) -> str:
    if index + 1 < len(messages) and messages[index + 1].get("role") == "user":
        return str(messages[index + 1].get("content") or "")
    return ""


def is_truncated(observation: str) -> bool:
    return "elided_chars" in observation or "output of your last command was too long" in observation


def parse_tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls = []
    turn = 0
    for index, message in enumerate(messages):
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            continue
        turn += 1
        function = tool_calls[0].get("function") or {}
        try:
            args = json.loads(function.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append({
            "turn": turn,
            "message_index": index,
            "tool": function.get("name", ""),
            "args": args,
            "observation": observation_after(messages, index),
        })
    return calls


def workbook_bounds(path: Path, sheet: str) -> tuple[int, int, int, int] | None:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=False, read_only=True)
    try:
        ws = wb[sheet]
        cells = [cell for row in ws.iter_rows() for cell in row if cell.value is not None]
        if not cells:
            return None
        return (
            min(cell.row for cell in cells),
            max(cell.row for cell in cells),
            min(cell.column for cell in cells),
            max(cell.column for cell in cells),
        )
    finally:
        wb.close()


def _view_range(path: Path, args: dict[str, Any]) -> tuple[str, str] | None:
    if args.get("mode", args.get("mode_opt")) == "list":
        return None
    sheet = args.get("sheet") or args.get("sheet_opt")
    if not sheet:
        return None
    bounds = workbook_bounds(path, sheet)
    if bounds is None:
        return None
    min_row, max_row, min_col, max_col = bounds
    start = int(args.get("start_row") or args.get("start_row_opt") or min_row)
    end = int(args.get("end_row") or args.get("end_row_opt") or max_row)
    from openpyxl.utils import get_column_letter

    return sheet, f"{get_column_letter(min_col)}{start}:{get_column_letter(max_col)}{end}"


def extract_sheets(command: str) -> list[str]:
    sheets = list(SHEET_RE.findall(command))
    for match in re.finditer(r"for\s+(\w+)\s+in\s+\[([^\]]+)\]", command):
        sheets.extend(re.findall(r"['\"]([^'\"]+)['\"]", match.group(2)))
    # Preserve source order while removing duplicate names.
    return list(dict.fromkeys(sheets))


def _sheet_variables(command: str) -> dict[str, list[str]]:
    """Resolve literal worksheet bindings in a historical Python command."""
    bindings: dict[str, list[str]] = {}
    for variable, sheet in re.findall(
        r"(\w+)\s*=\s*wb\[\s*['\"]([^'\"]+)['\"]\s*\]", command
    ):
        bindings[variable] = [sheet]
    literal_lists: dict[str, list[str]] = {}
    for variable, raw in re.findall(
        r"for\s+(\w+)\s+in\s+\[([^\]]+)\]", command
    ):
        literal_lists[variable] = re.findall(r"['\"]([^'\"]+)['\"]", raw)
    for variable, sheet_variable in re.findall(
        r"(\w+)\s*=\s*wb\[\s*(\w+)\s*\]", command
    ):
        if sheet_variable in literal_lists:
            bindings[variable] = literal_lists[sheet_variable]
    return bindings


def _workbook_dimensions(path: Path, sheet: str) -> tuple[int, int]:
    bounds = workbook_bounds(path, sheet)
    if bounds is None:
        return 1, 1
    return bounds[1], bounds[3]


def _loop_ranges(command: str, path: Path, sheet: str) -> dict[str, tuple[int, int]]:
    """Return inclusive loop intervals for the simple cell-print idioms used."""
    max_row, max_col = _workbook_dimensions(path, sheet)
    loops: dict[str, tuple[int, int]] = {}
    for variable, start, end_expr in re.findall(
        r"for\s+(\w+)\s+in\s+(?:list\s*\(\s*)?range\(\s*(\d+)\s*,\s*([^\)]+)\)",
        command,
    ):
        end_expr = end_expr.strip()
        if end_expr.isdigit():
            end = int(end_expr)
        elif "min(" in end_expr and "max_column" in end_expr:
            bounded = re.search(r",\s*(\d+)\s*$", end_expr)
            end = int(bounded.group(1)) + 1 if bounded else max_col + 1
        elif "max_row" in end_expr:
            end = max_row + 1
        elif "max_column" in end_expr:
            end = max_col + 1
        else:
            continue
        loops[variable] = (int(start), max(int(start), end - 1))
    return loops


def _expr_interval(expr: str, loops: dict[str, tuple[int, int]], *, axis: str) -> tuple[int, int] | None:
    expr = expr.strip()
    if expr.isdigit():
        value = int(expr)
        return value, value
    if expr in loops:
        return loops[expr]
    # Handle the bounded column form min(ws.max_column, 12)+1.
    bounded = re.search(r"min\([^,]+,\s*(\d+)\)\s*\+\s*1", expr)
    if bounded and axis == "col":
        end = int(bounded.group(1))
        return 1, end
    return None


def command_requests(path: Path, command: str) -> list[dict[str, str]]:
    """Reconstruct explicit cell/range requests from the historical code."""
    bindings = _sheet_variables(command)
    if not bindings:
        return []
    requests: list[dict[str, str]] = []
    for variable, sheets in bindings.items():
        loops = _loop_ranges(command, path, sheets[0])
        for cell_match in re.finditer(
            rf"\b{re.escape(variable)}\.cell\(\s*([^,]+)\s*,\s*([^\)]+)\)",
            command,
        ):
            rows = _expr_interval(cell_match.group(1), loops, axis="row")
            cols = _expr_interval(cell_match.group(2), loops, axis="col")
            if rows is None or cols is None:
                continue
            from openpyxl.utils import get_column_letter
            cell_range = (
                f"{get_column_letter(cols[0])}{rows[0]}:"
                f"{get_column_letter(cols[1])}{rows[1]}"
            )
            for sheet in sheets:
                requests.append({"sheet": sheet, "range": cell_range})
    # Preserve command order while removing duplicate regex matches.
    return list({(row["sheet"], row["range"]): row for row in requests}.values())


def _source_facts(path: Path, sheet: str, addresses: set[str]) -> list[dict[str, Any]]:
    import openpyxl

    if not addresses:
        return []
    path_key = str(path)
    if path_key not in _SOURCE_FACTS:
        wb = openpyxl.load_workbook(path, data_only=False, read_only=True)
        try:
            workbook_facts: dict[str, dict[str, dict[str, Any]]] = {}
            for ws in wb.worksheets:
                sheet_facts: dict[str, dict[str, Any]] = {}
                for row in ws.iter_rows():
                    for cell in row:
                        if cell.value is None:
                            continue
                        if cell.data_type == "f":
                            formula = (
                                cell.value
                                if isinstance(cell.value, str)
                                else getattr(cell.value, "text", str(cell.value))
                            )
                        else:
                            formula = None
                        sheet_facts[cell.coordinate] = {
                            "sheet": ws.title,
                            "address": cell.coordinate,
                            "value": None if formula is not None else str(cell.value),
                            "formula": formula,
                            "dtype": cell.data_type,
                        }
                workbook_facts[ws.title] = sheet_facts
            _SOURCE_FACTS[path_key] = workbook_facts
        finally:
            wb.close()
    return [
        _SOURCE_FACTS[path_key].get(sheet, {}).get(address)
        for address in sorted(addresses, key=_address_key)
        if address in _SOURCE_FACTS[path_key].get(sheet, {})
    ]


def _facts_for_requests(path: Path, requests: list[dict[str, str]]) -> list[dict[str, Any]]:
    from openpyxl.utils import get_column_letter
    from openpyxl.utils.cell import range_boundaries

    facts: list[dict[str, Any]] = []
    for request in requests:
        min_col, min_row, max_col, max_row = range_boundaries(request["range"])
        addresses = {
            f"{get_column_letter(col)}{row}"
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        }
        facts.extend(_source_facts(path, request["sheet"], addresses))
    return facts


def _address_key(address: str) -> tuple[int, int]:
    from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

    column, row = coordinate_from_string(address)
    return row, column_index_from_string(column)


def _line_value_facts(line: str, current_sheet: str | None) -> list[tuple[str, str | None]]:
    facts: list[tuple[str, str | None]] = []
    # Printed ``B14 'label'`` or ``Model D2 =formula`` forms.
    match = re.match(r"^\s*(?:(.+?)\s+)?([A-Z]{1,3}\d+)\s+(.+?)\s*$", line)
    if match and not line.lstrip().startswith(("Row ", "Sheets:", "Loading ")):
        prefix, address, raw = match.groups()
        if prefix and prefix.strip() in {"Model", "FY2027P", "FY2028P", "FY2027P (Earnings)"}:
            current_sheet = prefix.strip()
        if current_sheet:
            try:
                value = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                value = raw
            facts.append((address, repr(value)))
            return facts

    # Printed ``('B2', 'value')`` / ``[('B2', 'value'), ...]`` forms.
    for quoted in QUOTED_CELL_RE.finditer(line):
        address = quoted.group(1)
        tail = line[quoted.end():].lstrip()
        if tail.startswith(","):
            tail = tail[1:].lstrip()
        try:
            value = ast.literal_eval(tail.rstrip(", ]"))
        except (SyntaxError, ValueError):
            value = None
        facts.append((address, repr(value)))
    return facts


def parse_observed_addresses(
    path: Path,
    operation: dict[str, Any],
) -> dict[str, set[str]]:
    """Extract addresses visibly returned by the archived observation.

    The parser intentionally records only coordinates visibly printed in the
    archived observation. It never scans the workbook to discover targets.
    """
    observation = operation["observation"]
    if operation["tool"] == "view_xlsx":
        args = operation["args"]
        requested = _view_range(path, args)
        if requested is None:
            return {}
        sheet, cell_range = requested
        from openpyxl.utils.cell import range_boundaries

        min_col, _min_row, _max_col, _max_row = range_boundaries(cell_range)
        addresses: set[str] = set()
        # view_xlsx prints row lists. Only non-empty positions are factual cell
        # observations for the sparse compiled surface.
        for line in observation.splitlines():
            match = re.match(r"\s*Row\s+(\d+):\s+(\[.*\])\s*$", line)
            if not match:
                continue
            try:
                values = ast.literal_eval(match.group(2))
            except (SyntaxError, ValueError):
                continue
            row = int(match.group(1))
            for index, value in enumerate(values):
                if value is not None:
                    from openpyxl.utils import get_column_letter

                    addresses.add(f"{get_column_letter(min_col + index)}{row}")
        if not addresses and not is_truncated(observation):
            # The official view output may contain only a header for an empty
            # range. No cell facts are available in that case.
            return {}
        return {sheet: addresses}

    command = str(operation["args"].get("command", ""))
    sheets = extract_sheets(command)
    current_sheet = sheets[0] if len(sheets) == 1 else None
    found: dict[str, set[str]] = defaultdict(set)
    for line in observation.splitlines():
        stripped = line.strip()
        if stripped.startswith("==="):
            label = stripped.strip("= ")
            if label in sheets:
                current_sheet = label
            continue
        for address, _ in _line_value_facts(line, current_sheet):
            sheet = current_sheet
            # A line like ``Model D2 ...`` carries its own sheet prefix.
            prefix = line.strip().split()[0] if line.strip() else ""
            if prefix in sheets and address in line:
                sheet = prefix
            if sheet:
                found[sheet].add(address)
    return dict(found)


def operation_requests(path: Path, operation: dict[str, Any]) -> list[dict[str, str]]:
    if operation["tool"] == "view_xlsx":
        requested = _view_range(path, operation["args"])
        return [{"sheet": requested[0], "range": requested[1]}] if requested else []
    command = str(operation["args"].get("command", ""))
    return command_requests(path, command)


def normalize_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    if "fields" in result and "cells" in result:
        return [dict(zip(result["fields"], row)) for row in result["cells"]]
    raw = result.get("results", [])
    if isinstance(raw, dict) and "fields" in raw:
        return [dict(zip(raw["fields"], row)) for row in raw["cells"]]
    if isinstance(raw, list):
        return [dict(row) for row in raw]
    return []


def response_facts(response: dict[str, Any], default_sheet: str | None = None) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if "results" in response and isinstance(response["results"], list):
        for item in response["results"]:
            if isinstance(item, dict) and "cells" in item:
                for fact in normalize_result(item):
                    fact.pop("sheet", None)
                    fact["sheet"] = item["sheet"]
                    facts.append(fact)
            elif isinstance(item, dict):
                facts.append(item)
    else:
        facts.extend(normalize_result(response))
        if default_sheet:
            for fact in facts:
                fact.setdefault("sheet", default_sheet)
    return facts


def fact_key(fact: dict[str, Any]) -> tuple[Any, ...]:
    return (
        fact.get("sheet"), fact.get("address"), fact.get("value"),
        fact.get("formula"), fact.get("dtype"),
    )


def verbose_response(facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"results": facts, "styles": None, "truncated": False, "next_offset": None,
            "index_generation": 1}


def replay_v2(path: Path, requests: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from benchmark.inspection_helpers.api import inspect, inspect_ranges

    if not requests:
        return {}, []
    if len(requests) == 1:
        item = requests[0]
        response = inspect(str(path), item["sheet"], item["range"], compact=True,
                           limit=PHASE_A_LIMIT)
        return response, response_facts(response, item["sheet"])
    response = inspect_ranges(str(path), requests, max_cells=PHASE_A_LIMIT)
    return response, response_facts(response)


def replay_single_v2(path: Path, request: dict[str, str]) -> dict[str, Any]:
    from benchmark.inspection_helpers.api import inspect

    return inspect(str(path), request["sheet"], request["range"], compact=True,
                   limit=PHASE_A_LIMIT)


def classify_facts(path: Path, operation: dict[str, Any], v2_facts: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    requests = operation.get("requests") or operation_requests(path, operation)
    visible = parse_observed_addresses(path, operation)
    visible_facts = [
        fact
        for sheet, addresses in visible.items()
        for fact in _source_facts(path, sheet, addresses)
    ]
    # view_xlsx exposes coordinates and values directly. Python inspection
    # output frequently prints values without coordinates (or only occupancy
    # metadata), so use the explicit code-derived range as its conservative
    # fidelity envelope.
    if operation["tool"] == "view_xlsx" and visible_facts:
        required = visible_facts
        factual_scope = "historically_visible_facts"
    else:
        required = _facts_for_requests(path, requests)
        factual_scope = "mechanically_requested_facts"
    required_keys = {fact_key(fact) for fact in required}
    returned_keys = {fact_key(fact) for fact in v2_facts}
    missing = sorted(required_keys - returned_keys, key=str)
    additional = sorted(returned_keys - required_keys, key=str)
    if not required_keys:
        classification = "INVALID_COUNTERFACTUAL"
    elif missing:
        classification = "MISSING_FACTS"
    elif additional or operation["tool"] == "bash" or operation.get("historical_truncated"):
        classification = "ADDITIONAL_BUT_MECHANICAL"
    else:
        classification = "FACT_EXACT"
    return classification, {
        "historical_fact_count": len(required_keys),
        "v2_fact_count": len(returned_keys),
        "missing_facts": missing[:100],
        "additional_facts": additional[:100],
        "historical_truncated": is_truncated(operation["observation"]),
        "factual_scope": factual_scope,
        "historical_visible_fact_count": sum(len(items) for items in visible.values()),
    }


def read_operation(call: dict[str, Any]) -> bool:
    if call["tool"] == "view_xlsx":
        return call["args"].get("mode", call["args"].get("mode_opt")) != "list"
    if call["tool"] != "bash":
        return False
    command = str(call["args"].get("command", ""))
    low = command.lower()
    if not any(marker in low for marker in (
        "load_workbook", "iter_rows", "iter_cols", "defined_names", "cat /tmp/",
        "cat /tmp", "quarterly_dump", "exec_dump",
    )):
        return False
    return not any(marker in low for marker in (
        ".save(", "wb.save", "soffice", "libreoffice", "sed -i", "cat >",
        "shutil.copy", "os.replace", "rm -rf", "cp input.xlsx output.xlsx",
    ))


def historical_records(task_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = task_id.replace(":", "_") + "_H0"
    rep = REPS / base
    work = WORK / task_id.replace(":", "_") / "input.xlsx"
    messages = load_messages(rep / "transcript_full.jsonl")
    calls = parse_tool_calls(messages)
    operations = []
    sequence = 0
    active = False
    operation_index = 0
    for call in calls:
        if not read_operation(call):
            active = False
            continue
        if not active:
            sequence += 1
            active = True
        operation_index += 1
        operation = {
            "task_id": task_id,
            "trajectory_id": str((rep / "transcript_full.jsonl").relative_to(PROJECT_ROOT)),
            "sequence_id": f"{task_id}:S{sequence}",
            "turn": call["turn"],
            "tool": call["tool"],
            "args": call["args"],
            "historical_observation_bytes": len(call["observation"].encode("utf-8")),
            "historical_observation_tokens_estimate": math.ceil(len(call["observation"].encode("utf-8")) / 4),
            "historical_truncated": is_truncated(call["observation"]),
            "observation": call["observation"],
        }
        requests = operation_requests(work, operation)
        visible = parse_observed_addresses(work, operation)
        operation.update({
            "operation_index": operation_index,
            "requests": requests,
            "historical_visible_fact_count_by_sheet": {
                sheet: len(addresses) for sheet, addresses in visible.items()
            },
            "historical_visible_fact_count": sum(
                len(addresses) for addresses in visible.values()
            ),
            "historical_visible_fact_addresses": {
                sheet: sorted(addresses, key=_address_key)
                for sheet, addresses in visible.items()
            },
            "historical_visible_facts": [
                fact
                for sheet, addresses in visible.items()
                for fact in _source_facts(work, sheet, addresses)
            ],
        })
        operations.append(operation)
    summary = {
        "task_id": task_id,
        "trajectory_id": str((rep / "transcript_full.jsonl").relative_to(PROJECT_ROOT)),
        "input_workbook": str(work.relative_to(PROJECT_ROOT)),
        "input_workbook_sha256": sha256(work),
        "historical_read_operations": len(operations),
        "historical_inspection_sequences": sequence,
        "historical_observation_bytes": sum(row["historical_observation_bytes"] for row in operations),
        "historical_truncated_operations": sum(row["historical_truncated"] for row in operations),
    }
    return summary, operations


def phase_a() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ranking = json.loads(RANKING_PATH.read_text(encoding="utf-8"))["ranking"]
    population = json.loads((CHECKPOINT / "population.json").read_text(encoding="utf-8"))["tasks"]
    frozen_population = {row["task_id"] for row in population}
    selected = [row for row in ranking if row["task_id"] in frozen_population][:SELECTION_N]
    selection = {
        "rule": "Take exactly the first six rows of the frozen control-only exposure_ranking, restricted to the frozen thin-checkpoint population; no gold, v2 outcome, or future behavior.",
        "source": str(RANKING_PATH.relative_to(PROJECT_ROOT)),
        "ranking_features": json.loads(RANKING_PATH.read_text(encoding="utf-8"))["features"],
        "complete_ranking": ranking,
        "selected": selected,
    }
    write_json("phase_a_population.json", selection)
    historical_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for selected_row in selected:
        task_id = selected_row["task_id"]
        summary, operations = historical_records(task_id)
        summaries[task_id] = summary
        for operation in operations:
            historical_rows.append({k: v for k, v in operation.items() if k != "observation"})
    write_jsonl("phase_a_historical_sequences.jsonl", historical_rows)

    from benchmark.inspection_helpers import index as index_module

    equivalence_rows: list[dict[str, Any]] = []
    payload_rows: list[dict[str, Any]] = []
    freshness = OUT / "phase_a_freshness.jsonl"
    if freshness.exists():
        freshness.unlink()
    os.environ["AB_FRESHNESS_LOG"] = str(freshness)
    task_results: dict[str, Any] = {}
    for selected_row in selected:
        task_id = selected_row["task_id"]
        path = WORK / task_id.replace(":", "_") / "input.xlsx"
        summary, operations = historical_records(task_id)
        index_module.reset()
        task_eq: list[dict[str, Any]] = []
        task_payload: list[dict[str, Any]] = []
        for op_index, operation in enumerate(operations):
            requests = operation.get("requests") or operation_requests(path, operation)
            if not requests:
                row = {"task_id": task_id, "operation_index": op_index,
                       "sequence_id": operation["sequence_id"], "turn": operation["turn"],
                       "tool": operation["tool"], "classification": "INVALID_COUNTERFACTUAL",
                       "historical_fact_count": 0, "v2_fact_count": 0,
                       "historical_truncated": operation["historical_truncated"],
                       "requests": []}
                task_eq.append(row)
                continue
            response, facts = replay_v2(path, requests)
            classification, comparison = classify_facts(path, operation, facts)
            v2_bytes = len(compact(response).encode("utf-8"))
            single_bytes = 0
            if len(requests) > 1:
                singles = [replay_single_v2(path, request) for request in requests]
                single_bytes = sum(len(compact(item).encode("utf-8")) for item in singles)
            verbose_bytes = len(compact(verbose_response(facts)).encode("utf-8"))
            eq_row = {
                "task_id": task_id, "operation_index": op_index,
                "sequence_id": operation["sequence_id"], "turn": operation["turn"],
                "tool": operation["tool"], "classification": classification,
                "requests": requests, **comparison,
                "v2_truncated": bool(response.get("truncated", False)) or any(
                    item.get("truncated", False)
                    for item in response.get("results", [])
                    if isinstance(item, dict)
                ),
                "v2_index_generation": response.get("index_generation"),
            }
            task_eq.append(eq_row)
            task_payload.append({
                "task_id": task_id, "operation_index": op_index,
                "sequence_id": operation["sequence_id"], "historical_bytes": operation["historical_observation_bytes"],
                "v2_bytes": v2_bytes, "historical_tokens_estimate": operation["historical_observation_tokens_estimate"],
                "v2_tokens_estimate": math.ceil(v2_bytes / 4),
                "historical_operations": 1, "v2_helper_operations": 1,
                "historical_ranges": len(requests), "v2_ranges": len(requests),
                "compactness_verbose_same_v2_facts_bytes": verbose_bytes,
                "compactness_reduction_pct": round((1 - v2_bytes / verbose_bytes) * 100, 2) if verbose_bytes else None,
                "batching_single_v2_bytes": single_bytes or None,
                "batching_reduction_pct": round((1 - v2_bytes / single_bytes) * 100, 2) if single_bytes else None,
                "classification": classification,
            })
        task_eq_counted = [row for row in task_eq if row["classification"] != "INVALID_COUNTERFACTUAL"]
        task_payload_counted = task_payload
        facts_ok = bool(task_eq_counted) and all(
            row["classification"] in {"FACT_EXACT", "ADDITIONAL_BUT_MECHANICAL"}
            for row in task_eq_counted
        )
        if not facts_ok:
            factual_classification = "PARTIAL"
        elif all(row["classification"] == "FACT_EXACT" for row in task_eq_counted):
            factual_classification = "FACT_EXACT"
        else:
            factual_classification = "FACT_EQUIVALENT"
        historical_bytes = sum(row["historical_bytes"] for row in task_payload_counted)
        v2_bytes = sum(row["v2_bytes"] for row in task_payload_counted)
        historical_ops = sum(row["historical_ranges"] for row in task_payload_counted)
        v2_ops = sum(row["v2_helper_operations"] for row in task_payload_counted)
        compact_verbose_bytes = sum(
            row["compactness_verbose_same_v2_facts_bytes"]
            for row in task_payload_counted
        )
        batch_rows = [row for row in task_payload_counted if row["batching_single_v2_bytes"]]
        batch_single_bytes = sum(row["batching_single_v2_bytes"] for row in batch_rows)
        batch_batched_bytes = sum(row["v2_bytes"] for row in batch_rows)
        task_results[task_id] = {
            **summary,
            "counted_operations": len(task_eq_counted),
            "fact_replay_ok": facts_ok,
            "factual_classification": factual_classification,
            "operation_classifications": dict(sorted(defaultdict(int, {
                row["classification"]: sum(1 for x in task_eq if x["classification"] == row["classification"])
                for row in task_eq
            }).items())),
            "historical_bytes": historical_bytes,
            "v2_bytes": v2_bytes,
            "payload_reduction_pct": round((1 - v2_bytes / historical_bytes) * 100, 2) if historical_bytes else None,
            "historical_operations": historical_ops,
            "v2_operations": v2_ops,
            "operation_reduction_pct": round((1 - v2_ops / historical_ops) * 100, 2) if historical_ops else None,
            "compactness_verbose_bytes": compact_verbose_bytes,
            "compactness_v2_bytes": v2_bytes,
            "compactness_reduction_pct": round((1 - v2_bytes / compact_verbose_bytes) * 100, 2) if compact_verbose_bytes else None,
            "batching_rows": len(batch_rows),
            "batching_single_v2_bytes": batch_single_bytes,
            "batching_batched_v2_bytes": batch_batched_bytes,
            "batching_reduction_pct": round((1 - batch_batched_bytes / batch_single_bytes) * 100, 2) if batch_single_bytes else None,
            "v2_truncated_operations": sum(1 for row in task_eq if row.get("v2_truncated")),
        }
        equivalence_rows.extend(task_eq)
        payload_rows.extend(task_payload)
    write_jsonl("phase_a_fact_equivalence.jsonl", equivalence_rows)
    write_jsonl("phase_a_payloads.jsonl", payload_rows)
    write_json("phase_a_task_results.json", task_results)

    reductions = [
        row["payload_reduction_pct"] for row in task_results.values()
        if row["payload_reduction_pct"] is not None
    ]
    operation_reductions = [
        row["operation_reduction_pct"] for row in task_results.values()
        if row["operation_reduction_pct"] is not None
    ]
    compactness_reductions = [
        row["compactness_reduction_pct"] for row in task_results.values()
        if row["compactness_reduction_pct"] is not None
    ]
    batching_reductions = [
        row["batching_reduction_pct"] for row in task_results.values()
        if row["batching_reduction_pct"] is not None
    ]
    exact_or_equiv = sum(bool(row["fact_replay_ok"]) for row in task_results.values())
    clears_payload = sum(value >= 25 for value in reductions)
    clears_operations = sum(value >= 25 for value in operation_reductions)
    clears_mechanical = sum(
        (row["payload_reduction_pct"] or -math.inf) >= 25
        or (row["operation_reduction_pct"] or -math.inf) >= 25
        for row in task_results.values()
    )
    freshness_rows = []
    if freshness.exists():
        freshness_rows = [json.loads(line) for line in freshness.read_text(encoding="utf-8").splitlines() if line.strip()]
    freshness_ok = all(
        not row.get("stale", False)
        and not row.get("freshness_failure", False)
        and not row.get("truncated", False)
        for row in freshness_rows
    )
    no_silent_truncation = all(
        result["v2_truncated_operations"] == 0 for result in task_results.values()
    )
    gate = {
        "tasks": SELECTION_N,
        "exact_or_equivalent_tasks": exact_or_equiv,
        "tasks_with_payload_reduction_ge_25_pct": clears_payload,
        "tasks_with_operation_reduction_ge_25_pct": clears_operations,
        "tasks_clearing_either_mechanical_threshold": clears_mechanical,
        "median_payload_reduction_pct": statistics.median(reductions) if reductions else None,
        "payload_reduction_range_pct": [min(reductions), max(reductions)] if reductions else None,
        "median_operation_reduction_pct": statistics.median(operation_reductions) if operation_reductions else None,
        "operation_reduction_range_pct": [min(operation_reductions), max(operation_reductions)] if operation_reductions else None,
        "median_compactness_reduction_pct": statistics.median(compactness_reductions) if compactness_reductions else None,
        "compactness_reduction_range_pct": [min(compactness_reductions), max(compactness_reductions)] if compactness_reductions else None,
        "median_batching_reduction_pct": statistics.median(batching_reductions) if batching_reductions else None,
        "batching_reduction_range_pct": [min(batching_reductions), max(batching_reductions)] if batching_reductions else None,
        "no_stale_or_freshness_failure": freshness_ok,
        "no_silent_truncation": no_silent_truncation,
        "no_systematic_decision_relevant_fact_loss": all(bool(row["fact_replay_ok"]) for row in task_results.values()),
        "pass": exact_or_equiv >= 4 and clears_mechanical >= 4 and freshness_ok and no_silent_truncation and all(bool(row["fact_replay_ok"]) for row in task_results.values()),
        "rule": ">=4/6 exact/equivalent; >=4/6 >=25% observation-byte or operation reduction; no stale/freshness failure; no systematic fact loss.",
    }
    write_json("phase_a_gate.json", gate)
    return gate, task_results


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gate, results = phase_a()
    print(json.dumps({"phase_a_gate": gate, "task_results": results}, indent=2))


if __name__ == "__main__":
    main()
