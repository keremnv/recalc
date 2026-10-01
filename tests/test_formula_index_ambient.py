from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]
INDEX_LIB = ROOT / "benchmark/sweagent/formula_index/lib"
AMBIENT_LIB = ROOT / "benchmark/sweagent/view_xlsx_ambient/lib"
sys.path.insert(0, str(INDEX_LIB))
sys.path.insert(0, str(ROOT / "benchmark"))

from ambient import (  # noqa: E402
    build_ambient_payload,
    parse_view_xlsx_action,
    render_ambient,
)
from fingerprint import relative_fingerprint  # noqa: E402
from formula_index_ambient import AVOID, select_ambient_six  # noqa: E402
from formula_index_ambient_launch import SEED, build_jobs, runner_command  # noqa: E402
from workbook import EquivalenceClass, build_index  # noqa: E402


def _xlsx(tmp_path: Path, cells: dict[tuple[str, str], object]) -> Path:
    path = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    first = True
    sheets: dict[str, object] = {}
    for (sheet, addr), value in cells.items():
        if sheet not in sheets:
            if first:
                ws = wb.active
                ws.title = sheet
                first = False
            else:
                ws = wb.create_sheet(sheet)
            sheets[sheet] = ws
        sheets[sheet][addr] = value
    wb.save(path)
    return path


def _frozen_census_rows() -> list[dict]:
    """Occupancy flags from the frozen 20, used only to lock selection. Not scores."""
    nearest = {
        "03_02": {"unrecoverable": 31},
        "09_05": {"unrecoverable": 37},
        "19_04": {"unrecoverable": 26},
        "18_02": {"same_row_nonadjacent": 16, "same_column_nonadjacent": 7},
        "02_05": {"same_row_nonadjacent": 6, "same_column_nonadjacent": 4},
        "08_03": {"same_row_nonadjacent": 6},
        "04_05": {"cross_sheet": 5},
        "01_01": {
            "same_row_nonadjacent": 5,
            "same_column_nonadjacent": 5,
            "cross_sheet": 4,
        },
        "11_04": {"same_row_nonadjacent": 14, "cross_sheet": 1},
        "20_05": {"same_column_nonadjacent": 42, "same_row_nonadjacent": 42},
        "11_02": {"same_column_nonadjacent": 20, "same_row_nonadjacent": 7},
        "11_01": {
            "same_column_nonadjacent": 10,
            "cross_sheet": 9,
            "same_row_nonadjacent": 10,
        },
        "20_01": {"cross_sheet": 46, "same_column_nonadjacent": 4},
        "01_02": {},
        "04_03": {"same_row_nonadjacent": 8, "cross_sheet": 1},
        "07_04": {"same_column_nonadjacent": 85},
        "10_05": {"same_row_nonadjacent": 11, "same_column_nonadjacent": 11},
        "14_01": {"cross_sheet": 8, "same_row_nonadjacent": 15},
        "16_05": {"same_row_nonadjacent": 9, "same_column_nonadjacent": 6},
        "20_04": {"same_row_nonadjacent": 82},
    }
    return [
        {
            "id": task_id,
            "formulas": 1000,
            "opaque": 0,
            "nearest": flags,
            "recoverable_blanks": 0 if task_id in {"03_02", "09_05", "19_04"} else 1,
        }
        for task_id, flags in nearest.items()
    ]


def test_select_ambient_six_is_frozen_and_avoids_08_03() -> None:
    picked = select_ambient_six(_frozen_census_rows())
    ids = [item["id"] for item in picked]
    assert ids == ["03_02", "01_01", "20_05", "11_02", "02_05", "11_01"]
    assert "08_03" not in ids
    assert AVOID == {"08_03"}
    roles = {item["id"]: item["role"] for item in picked}
    assert roles["03_02"] == "negative_control"
    assert roles["01_01"] == "same_row_nonadjacent"
    assert roles["20_05"] == "same_row_nonadjacent"
    assert roles["11_02"] == "same_column_nonadjacent"
    assert roles["02_05"] == "same_column_nonadjacent"
    assert roles["11_01"] == "cross_sheet"
    assert all("score" not in item["reason"].lower() for item in picked)


def test_frozen_slice_matches_selector() -> None:
    payload = json.loads((ROOT / "benchmark/slices/fm-ambient-six.json").read_text())
    assert [task["id"] for task in payload["tasks"]] == [
        "03_02",
        "01_01",
        "20_05",
        "11_02",
        "02_05",
        "11_01",
    ]
    assert payload["repeats"] == 1
    assert payload["max_tool_calls_per_task"] == 50


def test_ambient_groups_visible_classes_once_and_includes_other_sheets(tmp_path: Path) -> None:
    path = _xlsx(
        tmp_path,
        {
            ("Model", "F20"): "=E20-E25",
            ("Model", "G20"): "=F20-F25",
            ("Model", "Q20"): "=P20-P25",
            ("Schedule", "F51"): "=E51-E56",
            ("Model", "A1"): "=A2+1",
        },
    )
    payload = build_ambient_payload(path, sheet="Model", start_row=20, end_row=20)
    text = payload["text"]
    eq = relative_fingerprint("=E20-E25", 6, 20, sheet="Model").eq_id
    assert text.startswith("STRUCTURAL INDEX")
    assert text.count(f"eq {eq}") == 1
    assert "visible_source: Model!F20" in text
    assert "formula: =E20-E25" in text
    assert "instances: 4" in text
    assert "Model!F20:G20" in text or "Model!F20" in text
    assert "Schedule!F51" in text
    assert "likely" not in text.lower()
    assert "golden" not in text.lower()
    other = relative_fingerprint("=A2+1", 1, 1, sheet="Model").eq_id
    assert other not in payload["eq_ids"]


def test_opaque_cells_are_labelled_singletons(tmp_path: Path) -> None:
    path = _xlsx(
        tmp_path,
        {
            ("Model", "A1"): '=INDIRECT("B1")',
            ("Model", "A2"): '=INDIRECT("B1")',
        },
    )
    payload = build_ambient_payload(path, sheet="Model", start_row=1, end_row=2)
    assert payload["opaque_classes"] == 2
    assert payload["text"].count("opaque=true") == 2
    ids = payload["eq_ids"]
    assert ids[0] != ids[1]


def test_truncation_keeps_every_visible_eq_id() -> None:
    records = []
    for index in range(40):
        record = EquivalenceClass(
            eq_id=f"{index:010x}"[:10],
            fingerprint=f"=C[0]R[{index}]",
            opaque=False,
            reason=None,
            n=12,
            exemplar_sheet="Model",
            exemplar_col=1,
            exemplar_row=index + 1,
            exemplar_formula="=A1+B1+" + ("X" * 80),
        )
        record.members["Model"].update({(col, index + 1) for col in range(1, 20)})
        record.members["Other"].update({(col, index + 1) for col in range(1, 20)})
        records.append((record, f"Model!A{index + 1}", record.exemplar_formula))
    text = render_ambient(records, sheet="Model", c1=1, r1=1, c2=20, r2=40, limit=800)
    assert "truncated=true" in text.split("\n", 1)[0]
    for record, _source, _formula in records:
        assert f"eq {record.eq_id}" in text


def test_wrapper_appends_only_on_first_content_inspect(tmp_path: Path) -> None:
    path = _xlsx(
        tmp_path,
        {
            ("Model", "B2"): "=A2+1",
            ("Model", "C2"): "=B2+1",
        },
    )
    wrapper = ROOT / "benchmark/sweagent/view_xlsx_ambient/bin/view_xlsx"
    flag = tmp_path / "emitted"
    env = {**os.environ, "AMBIENT_INDEX_FLAG": str(flag)}
    first = subprocess.run(
        [sys.executable, str(wrapper), str(path), "content", "Model", "2", "2"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "STRUCTURAL INDEX" in first.stdout
    assert first.stdout.count("STRUCTURAL INDEX") == 1
    second = subprocess.run(
        [sys.executable, str(wrapper), str(path), "content", "Model", "2", "2"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "STRUCTURAL INDEX" not in second.stdout
    listed = subprocess.run(
        [sys.executable, str(wrapper), str(path), "list"],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "AMBIENT_INDEX_FLAG": str(tmp_path / "other")},
    )
    assert "STRUCTURAL INDEX" not in listed.stdout
    assert "Sheets:" in listed.stdout


def test_treatment_prompt_is_control_prompt() -> None:
    control = yaml.safe_load(
        (ROOT / "benchmark/sweagent/spreadsheet-control.yaml").read_text()
    )
    treatment = yaml.safe_load(
        (ROOT / "benchmark/sweagent/spreadsheet-control-ambient.yaml").read_text()
    )
    assert (
        control["agent"]["templates"]["instance_template"]
        == treatment["agent"]["templates"]["instance_template"]
    )
    assert "formula_index" not in treatment["agent"]["templates"]["instance_template"]
    assert treatment["agent"]["templates"]["max_observation_length"] == 10_000
    bundles = [item["path"] for item in treatment["agent"]["tools"]["bundles"]]
    assert bundles == [
        "tools/submit",
        "../../../benchmark/sweagent/view_xlsx_ambient",
    ]


def test_vendored_index_lib_matches_formula_index_lib() -> None:
    for name in ("fingerprint.py", "ranges.py", "workbook.py", "xlsx_metadata_repair.py", "ambient.py"):
        left = (INDEX_LIB / name).read_bytes()
        right = (AMBIENT_LIB / name).read_bytes()
        assert left == right, name


def test_wrapper_source_does_not_consult_goldens() -> None:
    blob = (ROOT / "benchmark/sweagent/view_xlsx_ambient/bin/view_xlsx").read_text()
    blob += (INDEX_LIB / "ambient.py").read_text()
    assert "golden" not in blob.lower()
    assert "likely" not in blob.lower()


def test_launch_jobs_are_twelve_interleaved_and_deterministic() -> None:
    payload = json.loads((ROOT / "benchmark/slices/fm-ambient-six.json").read_text())
    jobs = build_jobs(payload)
    assert jobs == build_jobs(payload, seed=SEED)
    assert len(jobs) == 12
    keys = [(job["task"], job["arm"]) for job in jobs]
    assert len(set(keys)) == 12
    assert {job["arm"] for job in jobs} == {"control", "control-ambient"}
    assert {job["arm"] for job in jobs[:4]} == {"control", "control-ambient"}
    control = next(job for job in jobs if job["arm"] == "control")
    treatment = next(job for job in jobs if job["arm"] == "control-ambient")
    assert "--control" in runner_command(control)
    assert "--control-ambient" in runner_command(treatment)
    assert "--max-tokens" not in runner_command(control)
    assert "--no-score" in runner_command(control)


def test_parse_prior_control_view_xlsx_action() -> None:
    parsed = parse_view_xlsx_action(
        "view_xlsx '/mnt/spreadsheet_data/spreadsheet/book.xlsx' content 'Consolidated P&L'"
    )
    assert parsed is not None
    assert parsed.mode == "content"
    assert parsed.sheet == "Consolidated P&L"
    assert parsed.start_row is None
    listed = parse_view_xlsx_action("view_xlsx /tmp/a.xlsx list")
    assert listed is not None
    assert listed.mode == "list"
