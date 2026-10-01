#!/usr/bin/env python3
"""Gold-blind paired autopsy of a first-miss cell in already-paid trajectories.

For each task the evaluator names one first-miss address. This asks four questions of the
trajectory and never opens a golden:

1. Did inspect / view_xlsx *name* that cell (as an address, or as that sheet's row dump)?
   Boundary continuations count as a name; used-range alone does not.
2. Did any *successful* read include it? A failed oversize is attempted, not a read.
3. Did any write touch it?
4. After compare (or the control's last look), did the model submit anyway?

Those answers sort misses into targeting / commit / written-wrong buckets. A second axis,
still gold-blind, is whether the world had already decomposed the cell (it sat in an inspect
shortlist, possibly drowned among dozens of representatives) or the instruction was the only
place the target could have come from (unnamed, and the input cell is a calculating formula
the anomaly list did not select).
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmark"))

import characterize_commit_checks as cc
from inspect_decision import _MISS, _decode

from librecalc_mcp.domain.commit_checks import declared_targets, expand_range

RUNS_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/openrouter"
DATA_DIR = ROOT / "benchmark-data/SpreadsheetBench-2/data"
READ_TOOLS = ("calc_read", "calc_read_ranges", "view_xlsx")
WRITE_TOOLS = ("calc_write", "calc_fill_formulas", "calc_program")
_A1 = re.compile(r"^([A-Za-z]+)([0-9]+)$")
_VIEW_SHEET = re.compile(r"^Sheet:\s*(.+)\s*$")
_VIEW_ROW = re.compile(r"^Row (\d+):")
_PY_CELL = re.compile(
    r"""(?:\[|\.)(?:['\"](?P<addr>[A-Za-z]+[0-9]+)['\"]|(?P<addr2>[A-Za-z]+[0-9]+))"""
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control")
    parser.add_argument("ours")
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def _split_address(address: str) -> tuple[str, str]:
    sheet, _, cell = address.rpartition("!")
    return sheet, cell.upper()


def _range_covers(cell_range: str, address: str) -> bool:
    try:
        return ("_", address.upper()) in {
            ("_", cell) for _, cell in expand_range("_", cell_range)
        }
    except ValueError:
        return False


def _json_blobs(text: str) -> list[Any]:
    blobs: list[Any] = []
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            break
        try:
            value, offset = decoder.raw_decode(text, start)
        except ValueError:
            index = start + 1
            continue
        blobs.append(value)
        index = start + offset
    return blobs


def _candidate_hits(item: Any, sheet: str, cell: str) -> bool:
    return (
        isinstance(item, dict)
        and item.get("sheet") == sheet
        and str(item.get("address") or item.get("cell") or "").upper() == cell
    )


def _inspect_mentions(observation: str, sheet: str, cell: str) -> dict[str, Any]:
    """Where, if anywhere, an inspect payload names this cell as a candidate."""

    facts: dict[str, Any] = {
        "named": False,
        "rank": None,
        "selected_count": 0,
        "error_cell_count": 0,
        "extent_only": False,
        "named_sources": [],
    }
    sources: list[str] = []
    for blob in _json_blobs(observation):
        if not isinstance(blob, dict):
            continue
        errors = blob.get("formula_errors") or {}
        selected = errors.get("selected_cells") or []
        if isinstance(selected, list):
            facts["selected_count"] = max(facts["selected_count"], len(selected))
            facts["error_cell_count"] = max(
                facts["error_cell_count"], int(errors.get("cell_count") or 0)
            )
            for rank, item in enumerate(selected, start=1):
                if _candidate_hits(item, sheet, cell):
                    facts["named"] = True
                    facts["rank"] = rank
                    sources.append("formula_errors")
        for key, source in (
            ("translation_consensus", "translation_consensus"),
            ("short_sequence_gaps", "short_sequence_gaps"),
            ("deleted_row_geometry", "deleted_row_geometry"),
            ("boundary_continuations", "boundary_continuations"),
            ("blank_dependency_bridges", "blank_dependency_bridges"),
        ):
            group = blob.get(key) or {}
            if not isinstance(group, dict):
                continue
            for item in group.get("selected_candidates") or group.get("candidates") or []:
                if _candidate_hits(item, sheet, cell):
                    facts["named"] = True
                    sources.append(source)
        for item in blob.get("sheets") or []:
            if not isinstance(item, dict) or item.get("name") != sheet:
                continue
            used = item.get("used_range")
            if isinstance(used, str) and _range_covers(used, cell):
                facts["extent_only"] = not facts["named"]
    facts["named_sources"] = list(dict.fromkeys(sources))
    return facts


def _view_xlsx_covers(observation: str, sheet: str, cell: str) -> bool:
    match = _A1.match(cell)
    if match is None:
        return False
    row = match.group(2)
    current = None
    for line in observation.splitlines():
        header = _VIEW_SHEET.match(line.strip())
        if header:
            current = header.group(1).strip()
            continue
        row_match = _VIEW_ROW.match(line.strip())
        if current == sheet and row_match and row_match.group(1) == row:
            return True
    return False


def _read_action_covers(action: str, sheet: str, cell: str) -> bool:
    """Whether the *request* spanned the cell. Failed oversize reads still return True."""

    decoded = _decode(action)
    tool = decoded.split()[0] if decoded else ""
    if tool == "calc_read":
        try:
            parts = shlex.split(decoded)
        except ValueError:
            parts = decoded.split()
        if len(parts) >= 4 and parts[2] == sheet:
            return _range_covers(parts[3], cell)
        return False
    if tool == "calc_read_ranges":
        for payload in cc._decoded_payloads(action):
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict) or item.get("sheet") != sheet:
                    continue
                cell_range = item.get("range") or item.get("cell_range")
                if isinstance(cell_range, str) and _range_covers(cell_range, cell):
                    return True
        return False
    if "python" in tool or decoded.startswith(("cd ", "python", "cat ")):
        return sheet in decoded and cell in decoded.upper()
    return False


def _read_observation_succeeded(observation: str, sheet: str) -> bool:
    """True when a read returned cells for this sheet, not an oversize/budget error."""

    for blob in _json_blobs(observation or ""):
        if not isinstance(blob, dict):
            continue
        if blob.get("ok") is False and "ranges" not in blob:
            continue
        if blob.get("sheet") == sheet and isinstance(blob.get("cells"), list):
            return True
        for item in blob.get("ranges") or []:
            if not isinstance(item, dict) or item.get("ok") is False:
                continue
            if item.get("sheet") == sheet and isinstance(item.get("cells"), list):
                return True
    return False


def _read_covers(action: str, observation: str, sheet: str, cell: str) -> bool:
    """Whether the model was actually shown the cell, not merely asked for a covering range."""

    if _view_xlsx_covers(observation or "", sheet, cell):
        return True
    if not _read_action_covers(action, sheet, cell):
        return False
    decoded = _decode(action)
    tool = decoded.split()[0] if decoded else ""
    if tool in {"python", "python3"} or decoded.startswith(("cd ", "python", "cat ", "grep ")):
        return True
    return _read_observation_succeeded(observation or "", sheet)


def _write_covers(action: str, sheet: str, cell: str) -> bool:
    decoded = _decode(action)
    tool = decoded.split()[0] if decoded else ""
    if tool in WRITE_TOOLS:
        requests: list[dict[str, Any]] = []
        for payload in cc._decoded_payloads(action):
            if isinstance(payload, dict):
                payload = [payload]
            if isinstance(payload, list):
                requests.extend(item for item in payload if isinstance(item, dict))
        if tool == "calc_write":
            try:
                parts = shlex.split(decoded)
            except ValueError:
                parts = decoded.split()
            if len(parts) >= 5 and parts[3] == sheet:
                return _range_covers(parts[4], cell)
        return (sheet, cell) in declared_targets(requests)
    upper = decoded.upper()
    if "PYTHON" in upper or decoded.startswith(("cat ", "tee ")):
        if sheet not in decoded:
            return False
        return bool(_PY_CELL.search(decoded)) and cell in upper
    return False


def _thought_mentions(step: dict[str, Any], sheet: str, cell: str) -> bool:
    text = " ".join(
        str(step.get(key) or "") for key in ("thought", "response")
    )
    return cell in text.upper() or (sheet in text and cell[1:] in text)


def autopsy_trajectory(steps: list[dict[str, Any]], address: str) -> dict[str, Any]:
    sheet, cell = _split_address(address)
    named = False
    named_rank = None
    named_sources: list[str] = []
    selected_count = 0
    error_cell_count = 0
    extent_only = False
    read = False
    read_attempted = False
    written = False
    thought = False
    compare_indexes: list[int] = []
    submit_indexes: list[int] = []
    compare_mentions = False

    for index, step in enumerate(steps):
        action = (step.get("action") or "").strip()
        observation = step.get("observation") if isinstance(step.get("observation"), str) else ""
        tool = action.split()[0] if action else ""
        thought = thought or _thought_mentions(step, sheet, cell)

        if tool == "calc_inspect" or (tool == "view_xlsx" and index == 0):
            inspect = _inspect_mentions(observation, sheet, cell)
            named = named or inspect["named"]
            if inspect["rank"] is not None:
                named_rank = inspect["rank"]
            selected_count = max(selected_count, inspect["selected_count"])
            error_cell_count = max(error_cell_count, inspect["error_cell_count"])
            extent_only = extent_only or inspect["extent_only"]
            named_sources.extend(inspect.get("named_sources") or [])
            if tool == "view_xlsx" and _view_xlsx_covers(observation, sheet, cell):
                named = True
                read = True
        if tool in READ_TOOLS or tool in {"python3", "python", "cd", "cat", "grep", "sed", "awk"}:
            if _read_action_covers(action, sheet, cell) or (
                tool == "view_xlsx" and _view_xlsx_covers(observation, sheet, cell)
            ):
                read_attempted = True
            if _read_covers(action, observation, sheet, cell):
                read = True
        if _write_covers(action, sheet, cell):
            written = True
        if tool == "calc_compare":
            compare_indexes.append(index)
            if cell in observation.upper() and sheet in observation:
                compare_mentions = True
        if tool == "submit":
            submit_indexes.append(index)

    compared = bool(compare_indexes)
    submitted = bool(submit_indexes)
    after_compare = bool(
        compared and submitted and compare_indexes[0] < submit_indexes[-1]
    )
    drowned = bool(
        named and selected_count >= 10 and named_rank is not None and named_rank > 3
    )
    if written:
        bucket = "written_wrong"
    elif read:
        bucket = "read_unwritten"
    elif named:
        bucket = "named_unread"
    else:
        bucket = "unnamed"
    return {
        "named": named,
        "named_rank": named_rank,
        "named_sources": list(dict.fromkeys(named_sources)),
        "selected_count": selected_count,
        "error_cell_count": error_cell_count,
        "extent_only": extent_only and not named,
        "read": read,
        "read_attempted": read_attempted,
        "written": written,
        "thought": thought,
        "compared": compared,
        "submitted": submitted,
        "after_compare": after_compare,
        "compare_mentions": compare_mentions,
        "drowned": drowned,
        "bucket": bucket,
    }


def _input_kind(category: str, task_id: str, sheet: str, cell: str) -> str:
    datasets = _datasets()
    entry = datasets.get((category, task_id))
    if entry is None:
        return "unknown"
    path = DATA_DIR / category / entry["spreadsheet_path"]
    try:
        workbook = openpyxl.load_workbook(path, data_only=False, read_only=True)
        try:
            if sheet not in workbook.sheetnames:
                return "missing_sheet"
            value = workbook[sheet][cell].value
        finally:
            workbook.close()
    except Exception:  # noqa: BLE001 - stored inputs can fail to open
        return "unreadable"
    if isinstance(value, str) and value.startswith("="):
        return "formula"
    if value is None or value == "":
        return "blank"
    return "constant"


_DATASETS: dict[tuple[str, str], dict[str, Any]] | None = None


def _datasets() -> dict[tuple[str, str], dict[str, Any]]:
    global _DATASETS
    if _DATASETS is None:
        entries: dict[tuple[str, str], dict[str, Any]] = {}
        for directory in sorted(DATA_DIR.iterdir()):
            dataset = directory / "dataset.json"
            if not dataset.is_file():
                continue
            for task in json.loads(dataset.read_text(encoding="utf-8")):
                entries[(directory.name, task["id"])] = task
        _DATASETS = entries
    return _DATASETS


def _nuance(ours: dict[str, Any], input_kind: str) -> str:
    """Guess which of the two buckets a miss belongs to, from our trajectory + input only."""

    if ours["bucket"] in {"exact", "no_first_miss"}:
        return ours["bucket"]
    if ours["drowned"]:
        return "decomposable_drowned"
    if ours["bucket"] == "read_unwritten":
        return "decomposable_commit"
    if ours["compare_mentions"] and ours["after_compare"] and not ours["written"]:
        return "decomposable_commit"
    if ours["bucket"] == "named_unread":
        return "decomposable_targeting"
    if ours["bucket"] == "unnamed" and input_kind == "formula":
        return "task_nature_or_silent_logic"
    if ours["bucket"] == "unnamed" and input_kind in {"blank", "constant"}:
        return "decomposable_observation_gap"
    if ours["bucket"] == "written_wrong":
        return "compiler_wrote_the_wrong_thing"
    return "unclassified"


def _load_steps(run_dir: Path, task: str) -> list[dict[str, Any]]:
    category, _, task_id = task.partition(":")
    trajectories = sorted((run_dir / f"{category}-{task_id}").glob("trajectory/*/*.traj"))
    if not trajectories:
        return []
    return json.loads(trajectories[-1].read_text(encoding="utf-8")).get("trajectory", [])


def _first_miss(score: dict[str, Any]) -> tuple[str | None, str | None]:
    if score.get("accuracy"):
        return None, None
    match = _MISS.match(score.get("error_message") or "")
    if match is None:
        return None, None
    return match.group(1).lower(), match.group(2)


def main() -> int:
    args = _arguments()
    control_dir = args.runs_dir / args.control
    ours_dir = args.runs_dir / args.ours
    control_scores = json.loads((control_dir / "official_scores.json").read_text())["tasks"]
    ours_scores = json.loads((ours_dir / "official_scores.json").read_text())["tasks"]
    tasks = sorted(set(control_scores) | set(ours_scores))
    rows: list[dict[str, Any]] = []

    print(
        f"{'task':<24} {'o_miss':<28} {'in':<8} "
        f"{'c_n':>3} {'c_r':>3} {'c_w':>3} {'c_bkt':<16} "
        f"{'o_n':>3} {'o_r':>3} {'o_w':>3} {'o_rnk':>5} {'o_bkt':<16} nuance"
    )
    for task in tasks:
        category, _, task_id = task.partition(":")
        ours_score = ours_scores.get(task) or {}
        control_score = control_scores.get(task) or {}
        ours_kind, ours_address = _first_miss(ours_score)
        control_kind, control_address = _first_miss(control_score)
        control_steps = _load_steps(control_dir, task)
        ours_steps = _load_steps(ours_dir, task)
        if ours_address is None:
            ours_view = {
                "named": False,
                "read": False,
                "written": False,
                "bucket": "exact" if ours_score.get("accuracy") else "no_first_miss",
                "drowned": False,
                "after_compare": False,
                "compare_mentions": False,
                "named_rank": None,
                "selected_count": 0,
            }
            input_kind = "n/a"
        else:
            sheet, cell = _split_address(ours_address)
            ours_view = autopsy_trajectory(ours_steps, ours_address)
            input_kind = _input_kind(category, task_id, sheet, cell)
        if control_address is None:
            control_view = {
                "named": False,
                "read": False,
                "written": False,
                "bucket": "exact" if control_score.get("accuracy") else "no_first_miss",
                "drowned": False,
                "after_compare": False,
                "compare_mentions": False,
                "named_rank": None,
                "selected_count": 0,
            }
        else:
            control_view = autopsy_trajectory(control_steps, control_address)
        row = {
            "task": task,
            "ours_address": ours_address,
            "control_address": control_address,
            "shared_miss": ours_address == control_address and ours_address is not None,
            "ours_miss_kind": ours_kind,
            "control_miss_kind": control_kind,
            "input_kind": input_kind,
            "control": control_view,
            "ours": ours_view,
            "control_mod": control_score.get("modification_accuracy"),
            "ours_mod": ours_score.get("modification_accuracy"),
        }
        row["nuance"] = _nuance(ours_view, input_kind)
        rows.append(row)
        miss = ours_address or ours_view["bucket"]
        print(
            f"{task:<24} {str(miss)[:28]:<28} {input_kind:<8} "
            f"{int(control_view['named']):>3} {int(control_view['read']):>3} "
            f"{int(control_view['written']):>3} {control_view['bucket']:<16} "
            f"{int(ours_view['named']):>3} {int(ours_view['read']):>3} "
            f"{int(ours_view['written']):>3} {ours_view.get('named_rank') or '-'!s:>5} "
            f"{ours_view['bucket']:<16} {row['nuance']}"
        )
        if (
            control_address
            and ours_address
            and control_address != ours_address
        ):
            print(f"{'':<24} control first miss {control_address}")

    print()
    print("ours buckets:", dict(Counter(row["ours"]["bucket"] for row in rows)))
    print("nuance:", dict(Counter(row["nuance"] for row in rows)))
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2, default=str))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
