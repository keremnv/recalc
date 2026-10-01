#!/usr/bin/env python3
"""Frozen zero-model population screen for ASSISTED_DELIVERY_TIMING_PROBE.

No agent, treatment, golden workbook, scorer, or confirmation-reserve outcome is read.
Eligible tasks are Debugging inputs outside prior discovery and the reserved-ID
manifest, with input ZIP <= 1 MiB. In ascending ID order, round-trip the input
once through openpyxl and use the *frozen* detector to measure the input-as-is
versus recalculated round-trip copy. Select the first four tasks with >=3
findings. The >=3 threshold follows the prior probe's zero-versus-3+ split.
The screen establishes contact opportunity only; it is not an agent outcome or
a capability prediction. It does not read gold data or agent outcomes.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from formula_error_feedback_discovery.frozen_runner import compute_nfe_delta

EXCLUDE_DISCOVERY = {"01_06", "02_01", "02_06", "02_09", "04_09", "07_03", "10_05", "10_10"}
EXCLUDE_RESERVE_IDS = {"03_01", "06_08", "06_06", "06_03", "06_10", "06_07", "09_05", "02_08", "02_10", "02_04"}
MAX_INPUT_BYTES = 1_048_576


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    data_root = ROOT / "benchmark-data/SpreadsheetBench-2/data/Debugging"
    items = json.loads((data_root / "dataset.json").read_text())
    eligible = []
    for item in sorted(items, key=lambda x: str(x["id"])):
        tid = str(item["id"])
        if tid in EXCLUDE_DISCOVERY | EXCLUDE_RESERVE_IDS:
            continue
        source = data_root / item["spreadsheet_path"]
        if source.stat().st_size > MAX_INPUT_BYTES:
            continue
        eligible.append((tid, source))

    rows = []
    for tid, source in eligible:
        with tempfile.TemporaryDirectory(prefix="formula_error_population_screen_") as tmp:
            tmpdir = Path(tmp)
            roundtrip = tmpdir / "roundtrip.xlsx"
            wb = openpyxl.load_workbook(source)
            wb.save(roundtrip)
            try:
                d = compute_nfe_delta(str(source), str(roundtrip), str(tmpdir / "scratch"))
                nfe = d["total"]
                error = None
            except Exception as exc:
                nfe = None
                error = f"{type(exc).__name__}: {exc}"[:300]
        rows.append({"task_id": f"Debugging:{tid}", "input_sha256": sha(source),
                     "input_bytes": source.stat().st_size,
                     "zero_model_nfe": nfe, "screen_error": error})
        if sum(r["zero_model_nfe"] is not None and r["zero_model_nfe"] >= 3 for r in rows) >= 4:
            break

    positive = [r["task_id"] for r in rows if r["zero_model_nfe"] is not None and r["zero_model_nfe"] >= 3]
    selected = positive[:4]
    if len(selected) != 4:
        raise RuntimeError("fewer than four zero-model positive tasks in the eligible population")
    result = {"experiment": "ASSISTED_DELIVERY_TIMING_PROBE",
              "rule": "eligible Debugging tasks, excluding prior discovery and reserved IDs, input <=1 MiB; ascending task ID; first four zero-model NFE >=3",
              "threshold": 3, "selected_tasks": selected,
              "screen_rows": rows}
    out = ROOT / "formula_error_delivery_probe/population.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"selected_tasks": selected, "screen_rows": rows}, indent=2))


if __name__ == "__main__":
    main()
