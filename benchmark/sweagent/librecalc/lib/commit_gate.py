"""Commit gate: the world's own report on a submission, delivered before it is final.

`calc_compare` answers "what did I change?", which is self-confirming -- it reports the edits
the agent intended and made, so it can never surface an edit the agent did not know to make.
This gate answers the questions the agent did not ask, from references the agent did not author:
the input-to-output error delta, the author's own uniform formula runs, and the author's own
tie-out cells.

It is a measuring instrument like the read budget, not a world primitive. It runs for one pass:
the first submit returns findings and does not finalise, and the next submit always succeeds, so
a model that cannot satisfy the report still produces a workbook.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any

INPUT_GLOB = "/mnt/spreadsheet_data/**/*_input.xlsx"
OUTPUT_GLOB = "/mnt/spreadsheet_output/*.xlsx"
_MAX_REPORTED_PER_CHECK = 12


def commit_gate_enabled() -> bool:
    return os.environ.get("LIBRECALC_COMMIT_GATE_ENABLED") == "1"


def commit_gate_path() -> Path | None:
    raw = os.environ.get("LIBRECALC_COMMIT_GATE_PATH")
    return Path(raw) if raw else None


def already_reported() -> bool:
    path = commit_gate_path()
    if path is None or not path.is_file():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("reported"))
    except ValueError:
        return False


def mark_reported() -> None:
    path = commit_gate_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reported": True}, separators=(",", ":")), encoding="utf-8")


def _single(pattern: str) -> str | None:
    matches = sorted(
        candidate
        for candidate in glob.glob(pattern, recursive=True)
        if not os.path.basename(candidate).startswith(".")
    )
    return matches[0] if matches else None


def discover_paths() -> tuple[str | None, str | None]:
    """The task mounts exactly one input workbook and one private output directory."""
    return _single(INPUT_GLOB), _single(OUTPUT_GLOB)


def _read_workbook(backend: Any, path: str, commit_checks: Any) -> dict:
    workbook = backend.inspect_workbook(path=path)
    requests = [
        (sheet.name, sheet.used_range) for sheet in workbook.sheets if sheet.used_range
    ]
    if not requests:
        return {}
    results = backend.read_ranges(requests, path=path, include_errors=True)
    return commit_checks.cell_map_from_reads(
        [(sheet, cell_range, result) for (sheet, cell_range), result in zip(requests, results)]
    )


def evaluate(backend: Any, commit_checks: Any) -> dict[str, Any]:
    """Run the checks that survived offline measurement against stored runs.

    Only the three that cleared the gate on Debugging output are included. `unrequested_write`
    and `referential_integrity` were measured and rejected; `unextended_continuation` belongs to
    the completion categories and is not part of the repair report.
    """
    input_path, output_path = discover_paths()
    if input_path is None or output_path is None:
        return {"ok": True, "reason": "no output workbook to verify"}

    before = _read_workbook(backend, input_path, commit_checks)
    after = _read_workbook(backend, output_path, commit_checks)
    findings = (
        commit_checks.new_formula_errors(before, after)
        + commit_checks.uniformity_breaks(before, after)
        + commit_checks.broken_check_cells(before, after)
    )
    if not findings:
        return {"ok": True, "reason": "no findings"}

    grouped: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        grouped.setdefault(finding.check, []).append(finding.as_dict())
    return {
        "ok": False,
        "schema": "commit-checks-v1",
        "finding_count": len(findings),
        "checks": {
            name: {
                "count": len(entries),
                "findings": entries[:_MAX_REPORTED_PER_CHECK],
            }
            for name, entries in grouped.items()
        },
        "note": (
            "These are facts about your output, not suggestions. Each names a cell whose state "
            "the input did not have. Fix what is wrong and submit again, or submit again "
            "unchanged if you judge every finding acceptable. The next submit is final."
        ),
    }
