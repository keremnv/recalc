"""Observation and diff models, exercised against the in-memory backend.

These used to load the SWE-agent wrapper by file path because the models lived
inside the harness. They are product code now, so they import normally and run
without LibreOffice or the benchmark bundle.
"""

import importlib.util
import json
import urllib.parse
from pathlib import Path

import pytest

from librecalc_mcp.backend.memory import MemoryCalcBackend
from librecalc_mcp.domain import diff as diff_module
from librecalc_mcp.domain import grid as grid_module
from librecalc_mcp.domain import observation as observation_module
from librecalc_mcp.domain.models import CalcOperation, SheetInfo, WorkbookInfo


def _harness_module():
    """Only for the argument-parsing helpers that genuinely belong to the wrapper."""
    path = Path(__file__).parents[1] / "benchmark/sweagent/librecalc/lib/calc_tool.py"
    spec = importlib.util.spec_from_file_location("benchmark_calc_tool", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _calc_tool_module():
    """Domain models, plus the wrapper helpers these tests still cover.

    The observation and diff models are product code; the argument parsing, read
    budget, and neighborhood bound belong to the harness. Tests reach both through
    one namespace so the split stays invisible to the assertions themselves.
    """
    harness = _harness_module()
    for name, function in (
        ("_structure_sheet_observation", observation_module._structure_sheet_observation),
        ("_formula_anomaly_sheet", observation_module._formula_anomaly_sheet),
        (
            "_formula_anomaly_workbook_observation",
            observation_module._formula_anomaly_workbook_observation,
        ),
        ("_blank_dependency_bridges", observation_module._blank_dependency_bridges),
        ("_workbook_observation", observation_module.workbook_observation),
        ("_format_read_observation", observation_module.format_read_observation),
        ("_semantic_diff", diff_module.semantic_diff),
        ("_a1_cell_count", grid_module.a1_cell_count),
    ):
        setattr(harness, name, function)
    return harness


def test_sparse_addressed_observation_preserves_coordinates_and_live_formulas() -> None:
    calc_tool = _calc_tool_module()
    result = calc_tool._format_read_observation(
        {
            "values": [["", "Label", 3], ["", "", 6]],
            "formulas": [["", "Label", "3"], ["", "", "=C1*2"]],
        },
        sheet="Model",
        cell_range="B4:D5",
        variant="sparse-addressed-v1",
    )

    assert result == {
        "sheet": "Model",
        "range": "B4:D5",
        "cells": [
            {"address": "C4", "value": "Label"},
            {"address": "D4", "value": 3},
            {"address": "D5", "value": 6, "formula": "=C1*2"},
        ],
    }


def test_grid_observation_is_unchanged() -> None:
    calc_tool = _calc_tool_module()
    result = {"values": [[1]], "formulas": [["1"]]}
    assert (
        calc_tool._format_read_observation(
            result,
            sheet="Sheet1",
            cell_range="A1:A1",
            variant="grid-v1",
        )
        is result
    )


def test_sparse_addressed_observation_accepts_one_cell() -> None:
    calc_tool = _calc_tool_module()
    assert calc_tool._format_read_observation(
        {"values": [[5]], "formulas": [["5"]]},
        sheet="Sheet1",
        cell_range="AA12",
        variant="sparse-addressed-v1",
    ) == {
        "sheet": "Sheet1",
        "range": "AA12",
        "cells": [{"address": "AA12", "value": 5}],
    }


def test_structure_observation_exposes_labels_shapes_regions_and_formulas() -> None:
    calc_tool = _calc_tool_module()
    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="B2:F6",
        result={
            "values": [
                ["Debt Waterfall", "", "", "", ""],
                ["Year 1", "Year 2", "Year 3", "Year 4", ""],
                ["", "", "", "", ""],
                ["Beginning cash", 450, 420, 390, 360],
                ["Ending cash", 48, 50, 52, 54],
            ],
            "formulas": [
                ["Debt Waterfall", "", "", "", ""],
                ["Year 1", "Year 2", "Year 3", "Year 4", ""],
                ["", "", "", "", ""],
                ["Beginning cash", "450", "420", "390", "360"],
                ["Ending cash", "=C5-C6", "=D5-D6", "=E5-E6", "=F5-F6"],
            ],
        },
        include_cell_details=True,
    )

    assert observation["dimensions"] == {"rows": 5, "columns": 5}
    assert observation["nonempty_cells"] == 15
    assert observation["formula_cells"] == 4
    assert observation["regions"] == ["B2:E3", "B5:F6"]
    assert observation["labels"]["B2"] == "Debt Waterfall"
    assert observation["labels"]["B3"] == "Year 1"
    assert observation["labels_omitted"] == 0
    assert observation["inputs"]["C5"] == 450
    assert observation["formulas"]["C6"] == {"expression": "=C5-C6", "value": 48}
    assert observation["formula_errors"] == {}
    assert observation["row_bands"]["3"] == ["B:E=text"]
    assert observation["row_bands"]["6"] == ["B=text", "C:F=formula"]


def test_structure_observation_preserves_semantic_notes_before_truncating() -> None:
    calc_tool = _calc_tool_module()
    meaningful_note = (
        "Cash taxes are lower because the deferred tax asset reverses at maturity. " * 3
    )
    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="A1:A1",
        result={"values": [[meaningful_note]], "formulas": [[meaningful_note]]},
    )

    assert observation["labels"]["A1"] == meaningful_note

    oversized_note = meaningful_note + ("x" * 100)
    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="A1:A1",
        result={"values": [[oversized_note]], "formulas": [[oversized_note]]},
    )

    assert len(observation["labels"]["A1"]) == 240
    assert observation["labels"]["A1"].endswith("…")


def test_semantic_snapshot_exposes_formula_errors() -> None:
    calc_tool = _calc_tool_module()
    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="A1:A1",
        result={
            "values": [[0]],
            "formulas": [["=1/0"]],
            "errors": [["#DIV/0!"]],
        },
        include_cell_details=True,
    )

    assert observation["formulas"]["A1"] == {
        "expression": "=1/0",
        "value": 0,
        "error": "#DIV/0!",
    }
    assert observation["formula_errors"] == {"A1": "#DIV/0!"}


def test_structure_variant_uses_sparse_addressed_targeted_reads() -> None:
    calc_tool = _calc_tool_module()
    expected = {
        "sheet": "Sheet1",
        "range": "C7:D7",
        "cells": [
            {"address": "C7", "value": "Label"},
            {"address": "D7", "value": 5, "formula": "=1+4"},
        ],
    }
    payload = {"values": [["Label", 5]], "formulas": [["Label", "=1+4"]]}
    assert (
        calc_tool._format_read_observation(
            payload,
            sheet="Sheet1",
            cell_range="C7:D7",
            variant="structure-first-v1",
        )
        == expected
    )
    assert (
        calc_tool._format_read_observation(
            payload,
            sheet="Sheet1",
            cell_range="C7:D7",
            variant="format-conventions-v1",
        )
        == expected
    )


def test_parse_range_requests_accepts_cell_range_alias() -> None:
    calc_tool = _calc_tool_module()
    raw = json.dumps(
        [
            {"sheet": "Revenue Build", "cell_range": "A1:J33"},
            {"sheet": "Operating Model", "range": "A1:J20"},
        ]
    )

    assert calc_tool._parse_range_requests(raw) == [
        ("Revenue Build", "A1:J33"),
        ("Operating Model", "A1:J20"),
    ]


def test_parse_range_requests_accepts_the_strict_debugging_batch_that_was_rejected() -> None:
    """glm-optional-isa-strict-three-1 Debugging:06_09 first calc_read_ranges call."""

    calc_tool = _calc_tool_module()
    raw = json.dumps(
        [
            {"sheet": "Revenue Build", "cell_range": "A1:J33"},
            {"sheet": "Revenue Build", "cell_range": "F5:J20"},
            {"sheet": "Revenue Build", "cell_range": "W5:W20"},
            {"sheet": "Operating Model", "cell_range": "A1:J20"},
        ]
    )

    assert calc_tool._parse_range_requests(raw) == [
        ("Revenue Build", "A1:J33"),
        ("Revenue Build", "F5:J20"),
        ("Revenue Build", "W5:W20"),
        ("Operating Model", "A1:J20"),
    ]


def test_parse_range_requests_rejects_missing_or_conflicting_range_keys() -> None:
    calc_tool = _calc_tool_module()

    with pytest.raises(ValueError, match="string field range"):
        calc_tool._parse_range_requests(json.dumps([{"sheet": "Revenue Build"}]))
    with pytest.raises(ValueError, match="conflicting range and cell_range"):
        calc_tool._parse_range_requests(
            json.dumps(
                [{"sheet": "Revenue Build", "range": "A1:B1", "cell_range": "A1:C1"}]
            )
        )


def test_multi_range_read_is_one_addressed_observation(monkeypatch, capsys) -> None:
    calc_tool = _calc_tool_module()
    backend = MemoryCalcBackend()
    backend.write_range("Sheet1", "A1:B1", [["PAT", 10]])
    backend.execute_program([CalcOperation(op="create_sheet", name="Valuation")])
    backend.write_range("Valuation", "E67", [[0.08]])
    monkeypatch.setattr(calc_tool, "_load_backend_types", lambda: (lambda: backend, CalcOperation))
    monkeypatch.setenv("LIBRECALC_OBSERVATION_VARIANT", "structure-first-v1")
    requests = urllib.parse.quote(
        '[{"sheet":"Sheet1","range":"A1:B1"},{"sheet":"Valuation","range":"E67"}]',
        safe="",
    )

    assert calc_tool.main(["read-ranges", "input.xlsx", requests]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result == {
        "ranges": [
            {
                "sheet": "Sheet1",
                "range": "A1:B1",
                "cells": [
                    {"address": "A1", "value": "PAT"},
                    {"address": "B1", "value": 10},
                ],
            },
            {
                "sheet": "Valuation",
                "range": "E67",
                "cells": [{"address": "E67", "value": 0.08}],
            },
        ]
    }


def test_multi_range_read_returns_valid_items_alongside_oversize_errors(
    monkeypatch, capsys
) -> None:
    calc_tool = _calc_tool_module()
    backend = MemoryCalcBackend()
    backend.write_range("Sheet1", "A1:B1", [["PAT", 10]])
    monkeypatch.setattr(calc_tool, "_load_backend_types", lambda: (lambda: backend, CalcOperation))
    monkeypatch.setenv("LIBRECALC_OBSERVATION_VARIANT", "structure-first-v1")
    monkeypatch.setenv("LIBRECALC_READ_MAX_CELLS", "96")
    requests = urllib.parse.quote(
        '[{"sheet":"Sheet1","range":"A1:I16"},{"sheet":"Sheet1","range":"A1:B1"}]',
        safe="",
    )

    assert calc_tool.main(["read-ranges", "input.xlsx", requests]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result == {
        "ranges": [
            {
                "ok": False,
                "sheet": "Sheet1",
                "range": "A1:I16",
                "error": (
                    "ValueError: ranges_json item 0 A1:I16 covers 144 cells; "
                    "neighborhood reads are limited to 96 cells (a few rows or columns "
                    "around a candidate). Narrow the range; do not dump a used range or "
                    "whole sheet. If you cannot narrow it, write from inspect with "
                    "calc_fill_formulas or calc_program; do not retry dumps or bash."
                ),
            },
            {
                "sheet": "Sheet1",
                "range": "A1:B1",
                "cells": [
                    {"address": "A1", "value": "PAT"},
                    {"address": "B1", "value": 10},
                ],
            },
        ]
    }


def test_structure_only_contract_does_not_include_cell_details() -> None:
    calc_tool = _calc_tool_module()
    observation = calc_tool._structure_sheet_observation(
        sheet="Sheet1",
        used_range="A1:B1",
        result={"values": [["Label", 5]], "formulas": [["Label", "5"]]},
    )

    assert "inputs" not in observation
    assert "formulas" not in observation


def test_formula_pattern_observation_compresses_only_exact_horizontal_fills() -> None:
    calc_tool = _calc_tool_module()
    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="B5:F7",
        result={
            "values": [
                ["Revenue", 10, 11, 12, 13],
                ["Margin", 1, 2, 3, 4],
                ["WACC", 0.08, None, None, None],
            ],
            "formulas": [
                ["Revenue", "=B1", "=C1", "=D1", "=E1"],
                ["Margin", "=SUM(C1:C2)", "=SUM(D1:D2)", "=SUM(E1:E2)", "=SUM(F1:F2)"],
                ["WACC", "=C1+C2", "", "", ""],
            ],
        },
        include_formula_patterns=True,
    )

    assert observation["formula_patterns"] == {
        "horizontal_fill_patterns": [
            {
                "range": "C5:F5",
                "top_left_formula": "=B1",
                "top_left_value": 10,
            },
            {
                "range": "C6:F6",
                "top_left_formula": "=SUM(C1:C2)",
                "top_left_value": 1,
            },
        ],
        "formula_cells_covered": 8,
        "formula_cells_unrepresented": 1,
        "note": (
            "Exact horizontal translated runs of at least four cells; shorter/non-fill formulas "
            "remain available by focused read."
        ),
    }


def test_formula_anomaly_observation_ranks_consensus_and_short_sequence_gaps() -> None:
    calc_tool = _calc_tool_module()
    sheet = calc_tool._formula_anomaly_sheet(
        sheet="Model",
        used_range="A1:E3",
        result={
            "values": [
                [0.03, 0.042, 0.038, 0.06, 0.07],
                [10, 20, 30, 40, None],
                [10, 20, 30, 40, None],
            ],
            "formulas": [
                [
                    "='3-month Term SOFR'!P27",
                    "0.042",
                    "0.038",
                    "='3-month Term SOFR'!P63",
                    "='3-month Term SOFR'!P75",
                ],
                ["", "", "", "", ""],
                ["=A2", "20", "=C2", "=D2", ""],
            ],
        },
    )
    weak_sheet = calc_tool._formula_anomaly_sheet(
        sheet="Small Schedule",
        used_range="F3:F5",
        result={
            "values": [[1.35], [2.0], [3.0]],
            "formulas": [["1.35"], ["=Model!E21"], ["=Model!E22"]],
        },
    )
    observation = calc_tool._formula_anomaly_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=[sheet, weak_sheet],
    )

    selected = {
        (candidate["sheet"], candidate["address"]): candidate
        for candidate in observation["translation_consensus"]["selected_candidates"]
    }
    assert selected[("Model", "B3")]["inferred_formula"] == "=B2"
    assert selected[("Model", "B3")]["agreement_count"] == 3
    assert selected[("Small Schedule", "F3")]["inferred_formula"] == "=Model!E20"
    assert selected[("Small Schedule", "F3")]["agreement_count"] == 2

    gaps = {
        candidate["address"]: candidate
        for candidate in observation["short_sequence_gaps"]["selected_candidates"]
    }
    assert set(gaps) == {"B1", "C1", "B3"}
    assert gaps["B1"]["before"]["formula"] == "='3-month Term SOFR'!P27"
    assert gaps["B1"]["after"]["formula"] == "='3-month Term SOFR'!P63"
    assert "validation failures" in observation["translation_consensus"]["note"]
    assert observation["formula_errors"]["cell_count"] == 0
    assert observation["formula_errors"]["selected_cells"] == []


def test_formula_anomaly_observation_deprioritizes_blue_financial_inputs() -> None:
    calc_tool = _calc_tool_module()

    def candidate(address: str) -> dict[str, object]:
        return {
            "sheet": "Model",
            "address": address,
            "current_value": 1.0,
            "inferred_formula": "=A1",
            "agreement_count": 2,
            "direction_count": 1,
            "immediate_count": 1,
            "evidence_sources": [],
        }

    def gap(address: str) -> dict[str, object]:
        return {
            "sheet": "Model",
            "address": address,
            "current_value": 1.0,
            "formula_shape": "=<REF>",
            "before": {"address": "A1", "formula": "=Z1"},
            "after": {"address": "C1", "formula": "=B1"},
            "nearby_same_shape_sources": ["A1", "C1", "D1"],
        }

    observation = calc_tool._formula_anomaly_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=[
            {
                "name": "Model",
                "used_range": "A1:D2",
                "formula_cells": 3,
                "numeric_constants": 2,
                "translation_candidate_count": 2,
                "sequence_gap_count": 2,
                "_translation_candidates": [candidate("B1"), candidate("B2")],
                "_sequence_gaps": [gap("B1"), gap("B2")],
            }
        ],
        formats={
            ("Model", "B1"): {"font_color": "#0000FF"},
            ("Model", "B2"): {"font_color": "#000000"},
        },
    )

    assert [
        item["address"] for item in observation["translation_consensus"]["selected_candidates"]
    ] == ["B2"]
    assert [
        item["address"] for item in observation["short_sequence_gaps"]["selected_candidates"]
    ] == ["B2"]
    assert observation["translation_consensus"]["format_candidates_deprioritized"] == 1


def test_format_convention_observation_compacts_gold_blind_color_outliers() -> None:
    sheets = [
        {
            "name": "Model",
            "used_range": "A1:F2",
            "result": {
                "values": [
                    [1, 2, 3, None, None, None],
                    [None, None, None, 10, 20, 30],
                ],
                "formulas": [
                    [None, None, None, None, None, None],
                    [None, None, None, "=Other!A1", "=Other!B1", "=Other!C1"],
                ],
            },
        }
    ]
    requests, populated = observation_module.format_convention_requests(sheets)

    assert populated == 6
    assert requests == [
        ("Model", "A1"),
        ("Model", "B1"),
        ("Model", "C1"),
        ("Model", "D2"),
        ("Model", "E2"),
        ("Model", "F2"),
    ]

    observation = observation_module._format_convention_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=sheets,
        formats={
            ("Model", "A1"): {"font_color": "#0000ff"},
            ("Model", "B1"): {"font_color": "#0000FF"},
            ("Model", "C1"): {"font_color": "#000000"},
            ("Model", "D2"): {"font_color": "#00B050"},
            ("Model", "E2"): {"font_color": "#00B050"},
            ("Model", "F2"): {"font_color": "#000000"},
        },
        populated_cell_count=populated,
    )

    assert observation["observation"] == "format-conventions-v1"
    assert observation["population"] == {
        "populated_cells": 6,
        "format_cells_read": 6,
        "cells_omitted": 0,
    }
    candidates = {
        candidate["range"]: candidate for candidate in observation["format_outlier_candidates"]
    }
    assert candidates["C1"]["dominant_peer_font_color"] == "#0000FF"
    assert candidates["C1"]["sheet"] == "Model"
    assert candidates["F2"]["dominant_peer_font_color"] == "#00B050"
    assert candidates["F2"]["sheet"] == "Model"
    assert all(
        candidate["sheet"] not in {None, "*"}
        for candidate in observation["format_outlier_candidates"]
    )
    assert all(group["sheet"] != "*" for group in observation["mixed_color_groups"])
    workbook_groups = [
        group for group in observation["mixed_color_groups"] if group["sheet"] is None
    ]
    assert workbook_groups
    assert any(
        range_name.startswith("Model!")
        for group in workbook_groups
        for color in group["colors"]
        for range_name in color["ranges"]
    )
    assert "not validation failures" in observation["note"]


def test_format_convention_diff_compacts_same_color_runs() -> None:
    payload = observation_module.format_convention_diff_from_indexes(
        {
            ("Model", "A1"): "#000000",
            ("Model", "B1"): "#000000",
            ("Model", "C1"): "#0000FF",
            ("Model", "A2"): "#000000",
        },
        {
            ("Model", "A1"): "#00B050",
            ("Model", "B1"): "#00B050",
            ("Model", "C1"): "#00B050",
            ("Model", "A2"): "#000000",
        },
    )

    assert payload["observation"] == "format-conventions-diff-v1"
    assert payload["summary"] == {
        "font_colors_changed": 3,
        "font_color_runs_changed": 2,
    }
    assert payload["font_color_changes"] == [
        {
            "sheet": "Model",
            "range": "A1:B1",
            "cell_count": 2,
            "before": "#000000",
            "after": "#00B050",
        },
        {
            "sheet": "Model",
            "range": "C1",
            "cell_count": 1,
            "before": "#0000FF",
            "after": "#00B050",
        },
    ]
    assert payload["font_color_changes_omitted"] == 0
    assert "not a golden list" in payload["note"]


def test_format_convention_observation_does_not_emit_star_worksheet_names() -> None:
    sheets = [
        {
            "name": "Model",
            "used_range": "A1:C1",
            "result": {
                "values": [[1, 2, 3]],
                "formulas": [[None, None, None]],
            },
        },
        {
            "name": "Other",
            "used_range": "A1:A1",
            "result": {
                "values": [[4]],
                "formulas": [[None]],
            },
        },
    ]
    observation = observation_module._format_convention_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=sheets,
        formats={
            ("Model", "A1"): {"font_color": "#0000FF"},
            ("Model", "B1"): {"font_color": "#0000FF"},
            ("Model", "C1"): {"font_color": "#000000"},
            ("Other", "A1"): {"font_color": "#0000FF"},
        },
        populated_cell_count=4,
    )

    candidates = observation["format_outlier_candidates"]
    assert candidates
    assert all(candidate["sheet"] in {"Model", "Other"} for candidate in candidates)
    assert ("Model", "C1") in {(candidate["sheet"], candidate["range"]) for candidate in candidates}
    assert all(group["sheet"] != "*" for group in observation["mixed_color_groups"])


def test_tool_json_arguments_accept_url_encoded_structures() -> None:
    calc_tool = _calc_tool_module()
    value = [{"op": "set_formula", "formula": "='Inputs 1'.B2"}]
    encoded = urllib.parse.quote('[{"op":"set_formula","formula":"=\'Inputs 1\'.B2"}]', safe="")

    assert calc_tool._parse_json(encoded, list, "operations_json") == value


def test_semantic_snapshot_reports_candidate_gaps_without_claiming_task_truth() -> None:
    calc_tool = _calc_tool_module()
    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="B5:F9",
        result={
            "values": [
                ["Cash Available", "", "", "", ""],
                ["Beginning cash", 450, "", "", ""],
                ["Requirement", 48, 50, 52, 54],
                ["Cash flow", 1180, 1210, 1265, 1320],
                ["Total cash available", "", "", "", ""],
            ],
            "formulas": [
                ["Cash Available", "", "", "", ""],
                ["Beginning cash", "450", "", "", ""],
                ["Requirement", "48", "50", "52", "54"],
                ["Cash flow", "1180", "1210", "1265", "1320"],
                ["Total cash available", "", "", "", ""],
            ],
        },
        include_cell_details=True,
        include_candidate_gaps=True,
    )

    assert observation["inferred_table"] == {
        "label_column": "B",
        "data_columns": "C:F",
        "candidate_gaps": {
            "D6:F6": "Beginning cash",
            "C9:F9": "Total cash available",
        },
        "note": "Heuristic structural gaps, not task requirements.",
    }


def test_semantic_diff_separates_exact_changes_from_heuristic_gaps() -> None:
    calc_tool = _calc_tool_module()
    before = {
        "title": "input.xlsx",
        "sheets": [
            {
                "name": "Model",
                "used_range": "B5:F9",
                "labels": {"B6": "Beginning cash", "B9": "Total cash"},
                "inputs": {"C6": 450},
                "formulas": {},
                "formula_errors": {},
                "inferred_table": {
                    "candidate_gaps": {"D6:F6": "Beginning cash", "C9:F9": "Total cash"}
                },
            }
        ],
    }
    after = {
        "title": "output.xlsx",
        "sheets": [
            {
                "name": "Model",
                "used_range": "B5:F9",
                "labels": {"B6": "Beginning cash", "B9": "Total cash"},
                "inputs": {"C6": 450},
                "formulas": {
                    "D6": {"expression": "=C9", "value": 48},
                    "E6": {"expression": "=D9", "value": None, "error": "#VALUE!"},
                    "F6": {"expression": "=E9", "value": 52},
                },
                "formula_errors": {"E6": "#VALUE!"},
                "inferred_table": {"candidate_gaps": {"C9:F9": "Total cash"}},
            }
        ],
    }

    diff = calc_tool._semantic_diff(before, after)

    assert diff["summary"]["formulas_added"] == 3
    assert diff["summary"]["formula_errors_added"] == 1
    assert diff["summary"]["candidate_gaps_resolved"] == 1
    assert diff["summary"]["candidate_gaps_remaining"] == 1
    assert diff["sheet_changes"]["Model"]["formulas"]["added"] == {
        "D6": "=C9",
        "E6": "=D9",
        "F6": "=E9",
    }
    assert diff["sheet_changes"]["Model"]["formula_errors"]["added"] == {"E6": "#VALUE!"}
    assert diff["sheet_changes"]["Model"]["candidate_gaps"] == {
        "resolved": {"D6:F6": "Beginning cash"},
        "new": {},
        "note": "Heuristic structural gaps, not validation failures.",
    }


def test_semantic_diff_filters_numeric_noise_and_bounds_downstream_values() -> None:
    calc_tool = _calc_tool_module()
    before_formulas = {
        f"A{row}": {"expression": f"=B{row}", "value": float(row)} for row in range(1, 102)
    }
    after_formulas = {
        address: {**details, "value": details["value"] + 1}
        for address, details in before_formulas.items()
    }
    after_formulas["A1"]["value"] = 1.0000000001
    before = {
        "title": "before.xlsx",
        "sheets": [
            {
                "name": "Model",
                "used_range": "A1:B101",
                "formulas": before_formulas,
            }
        ],
    }
    after = {
        "title": "after.xlsx",
        "sheets": [
            {
                "name": "Model",
                "used_range": "A1:B101",
                "formulas": after_formulas,
            }
        ],
    }

    diff = calc_tool._semantic_diff(before, after)

    assert diff["summary"]["formula_values_changed"] == 100
    downstream = diff["downstream_formula_values"]
    assert downstream["count"] == 100
    assert downstream["by_sheet"] == {"Model": {"count": 100, "affected_range": "A2:A101"}}
    assert downstream["representatives_returned"] == 8
    assert downstream["omitted"] == 92
    assert downstream["representatives"][0]["address"] == "A2"
    assert downstream["representatives"][-1]["address"] == "A101"
    assert diff["sheet_changes"] == {}


def test_scoped_workbook_observation_keeps_manifest_and_selected_detail() -> None:
    calc_tool = _calc_tool_module()

    class InspectMemoryBackend(MemoryCalcBackend):
        def inspect_workbook(self, path=None):
            return WorkbookInfo(
                title="input.xlsx",
                url=None,
                sheets=[
                    SheetInfo(name="Model", used_range="A1:D1"),
                    SheetInfo(name="Assumptions", used_range="A1:B1"),
                ],
            )

        def read_ranges(self, ranges, path=None, include_errors=False):
            values = {
                "Model": {
                    "values": [["Revenue", 1, 2, 3]],
                    "formulas": [["Revenue", "=A2", "=B2", "=C2"]],
                },
                "Assumptions": {
                    "values": [["Tax rate", 0.25]],
                    "formulas": [["Tax rate", "0.25"]],
                },
            }
            return [values[sheet] for sheet, _ in ranges]

    observation = calc_tool._workbook_observation(
        InspectMemoryBackend(),
        "input.xlsx",
        "formula-patterns-v1",
        detailed_sheets={"Model", "Unknown"},
    )

    by_name = {sheet["name"]: sheet for sheet in observation["sheets"]}
    assert "labels" in by_name["Model"]
    assert by_name["Model"]["labels"] == {"A1": "Revenue"}
    assert by_name["Assumptions"]["detail"] == "manifest-only"
    assert "labels" not in by_name["Assumptions"]
    assert observation["detail_scope"] == {
        "requested": ["Model", "Unknown"],
        "returned": ["Model"],
        "unknown": ["Unknown"],
        "note": (
            "All sheets are listed in the manifest. Labels, structural bands, and formula "
            "patterns are returned only for requested sheets; use exact manifest names."
        ),
    }


def test_formula_patterns_compact_inspect_includes_boundary_continuations(monkeypatch) -> None:
    payload = {
        "candidates": [
            {
                "sheet": "Working Capital Schedule",
                "address": "M3",
                "inferred_formula": "=EOMONTH(L3,12)",
                "run": "D3:L3",
                "run_length": 9,
            }
        ],
        "note": "heuristic",
    }
    monkeypatch.setattr(
        observation_module,
        "_boundary_continuations_payload",
        lambda path: payload,
    )

    class InspectMemoryBackend:
        def inspect_workbook(self, path=None):
            return WorkbookInfo(
                title="input.xlsx",
                url=None,
                sheets=[
                    SheetInfo(name="Model", used_range="A1:D1"),
                    SheetInfo(name="Working Capital Schedule", used_range="A1:M7"),
                ],
            )

        def read_ranges(self, ranges, path=None, include_errors=False):
            return [{"values": [["x"]], "formulas": [["x"]]} for _ in ranges]

    observation = observation_module.workbook_observation(
        InspectMemoryBackend(),
        "input.xlsx",
        "formula-patterns-v1",
        detailed_sheets=set(),
    )

    assert observation["boundary_continuations"] == payload
    assert all(sheet.get("detail") == "manifest-only" for sheet in observation["sheets"])


def test_blank_bridges_can_be_disabled(monkeypatch) -> None:
    from librecalc_mcp.domain.observation import blank_bridges_enabled

    monkeypatch.delenv("LIBRECALC_BLANK_BRIDGES", raising=False)
    assert blank_bridges_enabled() is True
    monkeypatch.setenv("LIBRECALC_BLANK_BRIDGES", "0")
    assert blank_bridges_enabled() is False


def test_blank_dependency_bridge_ranks_missing_base_of_carry_forward_chain() -> None:
    calc_tool = _calc_tool_module()
    result = calc_tool._blank_dependency_bridges(
        [
            (
                "Working Capital",
                "A1:F4",
                {
                    "values": [
                        ["", "", "", "", "", ""],
                        ["Receivable", 10, 11, None, None, None],
                        ["Revenue", 100, 110, 120, 130, 140],
                        ["Receivable Days", 36.5, 36.5, 0, 0, 0],
                    ],
                    "formulas": [
                        ["", "", "", "", "", ""],
                        ["", "", "", "", "", ""],
                        ["", "", "", "", "", ""],
                        ["", "=B2/B3*365", "=C2/C3*365", "=D2/D3*365", "=D4", "=E4"],
                    ],
                },
            )
        ],
        selected_sheets={"Working Capital"},
    )

    assert result["candidate_count"] == 1
    assert result["omitted"] == 0
    assert result["selected_candidates"] == [
        {
            "sheet": "Working Capital",
            "address": "D2",
            "dependent": {
                "sheet": "Working Capital",
                "address": "D4",
                "formula": "=D2/D3*365",
            },
            "carry_forward_range": "D4:F4",
            "carry_forward_length": 2,
            "downstream_formula_count": 3,
            "context": [
                {
                    "address": "A2",
                    "value": "Receivable",
                    "relation": "blank_row_label",
                },
                {
                    "address": "A4",
                    "value": "Receivable Days",
                    "relation": "dependent_row_label",
                },
            ],
        }
    ]


def test_blank_dependency_bridge_omits_one_step_continuations() -> None:
    calc_tool = _calc_tool_module()
    result = calc_tool._blank_dependency_bridges(
        [
            (
                "Working Capital",
                "A1:C2",
                {
                    "values": [["", None, None], ["", 1, 2]],
                    "formulas": [["", "", ""], ["", "=A1", "=B2"]],
                },
            )
        ],
        selected_sheets={"Working Capital"},
    )

    assert result["candidate_count"] == 0
    assert result["selected_candidates"] == []


def test_compare_tool_runs_against_an_in_memory_backend(monkeypatch, capsys) -> None:
    calc_tool = _calc_tool_module()

    class CompareMemoryBackend(MemoryCalcBackend):
        def __init__(self):
            super().__init__()
            self.snapshots = {
                "before.xlsx": {
                    "values": [["Total", ""]],
                    "formulas": [["Total", ""]],
                },
                "after.xlsx": {
                    "values": [["Total", 3]],
                    "formulas": [["Total", "=SUM(B2:B3)"]],
                },
            }

        def inspect_workbook(self, path=None):
            return WorkbookInfo(
                title=path,
                url=None,
                sheets=[SheetInfo(name="Model", used_range="A1:B1")],
            )

        def read_range(self, sheet, cell_range, path=None):
            return self.snapshots[path]

    monkeypatch.setattr(
        calc_tool,
        "_load_backend_types",
        lambda: (CompareMemoryBackend, CalcOperation),
    )

    assert calc_tool.main(["compare", "before.xlsx", "after.xlsx"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["observation"] == "semantic-diff-v1"
    assert result["summary"]["formulas_added"] == 1
    assert result["sheet_changes"]["Model"]["formulas"]["added"] == {"B1": "=SUM(B2:B3)"}


def test_compare_tool_uses_format_convention_diff_for_format_observation(
    monkeypatch, capsys
) -> None:
    calc_tool = _calc_tool_module()

    class FormatCompareBackend:
        def inspect_workbook(self, path=None):
            return WorkbookInfo(
                title=path,
                url=None,
                sheets=[SheetInfo(name="Model", used_range="A1:C1")],
            )

        def read_range(self, sheet, cell_range, path=None):
            del sheet, cell_range
            return {
                "values": [[1, 2, 3]],
                "formulas": [[None, None, None]],
            }

        def read_ranges(self, ranges, path=None, include_errors=False):
            del include_errors
            return [self.read_range(sheet, cell_range, path) for sheet, cell_range in ranges]

        def read_formats(self, cells, path=None):
            colors = {
                "before.xlsx": {"A1": "#000000", "B1": "#000000", "C1": "#0000FF"},
                "after.xlsx": {"A1": "#000000", "B1": "#00B050", "C1": "#00B050"},
            }
            table = colors[path]
            return [{"font_color": table[address]} for _sheet, address in cells]

    monkeypatch.setenv("LIBRECALC_OBSERVATION_VARIANT", "format-conventions-v1")
    monkeypatch.setattr(
        calc_tool,
        "_load_backend_types",
        lambda: (FormatCompareBackend, CalcOperation),
    )

    assert calc_tool.main(["compare", "before.xlsx", "after.xlsx"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["observation"] == "format-conventions-diff-v1"
    assert result["summary"]["font_colors_changed"] == 2
    assert [item["range"] for item in result["font_color_changes"]] == ["B1", "C1"]


def test_formula_block_tool_uses_range_fill_on_memory_backend(monkeypatch, capsys) -> None:
    calc_tool = _calc_tool_module()
    backend = MemoryCalcBackend()
    monkeypatch.setattr(
        calc_tool,
        "_load_backend_types",
        lambda: (lambda: backend, CalcOperation),
    )
    blocks = urllib.parse.quote(
        '[{"sheet":"Sheet1","range":"C9:F9","formula":"=C6-C7+C8"},'
        '{"sheet":"Sheet1","range":"D6:F6","formula":"=C35"}]',
        safe="",
    )

    assert calc_tool.main(["fill-formulas", "input.xlsx", "output.xlsx", blocks]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["ok"] is True
    assert result["saved_to"] == "output.xlsx"
    assert backend.read_range("Sheet1", "C9:F9")["formulas"] == [["=C6-C7+C8"]]
    assert backend.read_range("Sheet1", "D6:F6")["formulas"] == [["=C35"]]


def test_bounded_treatment_rejects_used_range_dumps(monkeypatch) -> None:
    calc_tool = _calc_tool_module()
    monkeypatch.setenv("LIBRECALC_READ_MAX_CELLS", "96")

    assert calc_tool._a1_cell_count("A1:H12") == 96
    assert calc_tool._a1_cell_count("A1") == 1
    calc_tool._require_neighborhood_range("A1:H12", label="range")

    try:
        calc_tool._range_requests('[{"sheet":"Operating Model + DCF","range":"A1:AA43"}]')
    except ValueError as exc:
        assert "1161 cells" in str(exc)
        assert "96 cells" in str(exc)
        assert "write from inspect" in str(exc)
    else:
        raise AssertionError("used-range dump was accepted")


def test_formula_anomaly_observation_surfaces_error_shape_representatives() -> None:
    calc_tool = _calc_tool_module()
    sheet = calc_tool._formula_anomaly_sheet(
        sheet="Model",
        used_range="A1:C3",
        result={
            "values": [[None, None, None], [None, None, None], [None, None, None]],
            "formulas": [
                ["=B10*#REF!", "=C10*#REF!", "=D10*#REF!"],
                ["=#REF!", "=#REF!", "=INDEX(#REF!,1)"],
                ["=A1/0", "", ""],
            ],
            "errors": [
                ["#REF!", "#REF!", "#REF!"],
                ["#REF!", "#REF!", "#REF!"],
                ["#DIV/0!", None, None],
            ],
        },
    )
    observation = calc_tool._formula_anomaly_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=[sheet],
    )

    errors = observation["formula_errors"]
    selected = {
        (cell["sheet"], cell["address"], cell["error"], cell["shape"]): cell
        for cell in errors["selected_cells"]
    }

    assert errors["cell_count"] == 7
    assert errors["by_error"] == {"#DIV/0!": 1, "#REF!": 6}
    assert selected[("Model", "A1", "#REF!", "=<REF>*#REF!")]["repeat_count"] == 3
    assert selected[("Model", "A2", "#REF!", "=#REF!")]["repeat_count"] == 2
    assert ("Model", "A3", "#DIV/0!", "=<REF>/0") in selected
    assert "not auto-edits" in errors["note"]
    assert sheet["formula_error_count"] == 7


def test_formula_anomaly_observation_surfaces_deleted_row_geometry() -> None:
    overview = observation_module._formula_anomaly_sheet(
        sheet="Financial Overview",
        used_range="B4:F9",
        result={
            "values": [
                ["Energy", 1, 2, 3, 4],
                ["% Growth", None, None, None, None],
                ["Engineering", 5, 6, 7, 8],
                ["% Growth", None, None, None, None],
                ["% Growth", None, None, None, None],
                ["% Energy", None, None, None, None],
            ],
            "formulas": [
                ["", "", "", "", ""],
                ["", "", "=(D4/C4)-1", "=(E4/D4)-1", "=(F4/E4)-1"],
                ["", "", "", "", ""],
                ["", "", "=(D6/C6)-1", "=(E6/D6)-1", "=(F6/E6)-1"],
                ["", "", "=(#REF!/#REF!)-1", "=(#REF!/#REF!)-1", "=(#REF!/#REF!)-1"],
                ["", "", "=D4/#REF!", "=E4/#REF!", "=F4/#REF!"],
            ],
            "errors": [
                [None, None, None, None, None],
                [None, None, None, None, None],
                [None, None, None, None, None],
                [None, None, None, None, None],
                [None, None, "#REF!", "#REF!", "#REF!"],
                [None, None, "#REF!", "#REF!", "#REF!"],
            ],
        },
    )
    model = observation_module._formula_anomaly_sheet(
        sheet="Model",
        used_range="E22:G22",
        result={
            "values": [[None, None, None]],
            "formulas": [
                [
                    "='Financial Overview'!#REF!",
                    "='Financial Overview'!#REF!",
                    "='Financial Overview'!#REF!",
                ]
            ],
            "errors": [["#REF!", "#REF!", "#REF!"]],
        },
    )
    mixed = observation_module._formula_anomaly_sheet(
        sheet="Debt",
        used_range="J96:K96",
        result={
            "values": [[None, None]],
            "formulas": [
                ["=SUM($I96,#REF!)*AVERAGE(J93,J95)", "=SUM($I96,#REF!)*AVERAGE(K93,K95)"]
            ],
            "errors": [["#REF!", "#REF!"]],
        },
    )

    observation = observation_module._formula_anomaly_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=[overview, model, mixed],
    )
    geometry = observation["deleted_row_geometry"]
    selected = geometry["selected_candidates"]

    assert geometry["candidate_count"] == 1
    assert selected[0]["sheet"] == "Financial Overview"
    assert selected[0]["insert_row_index"] == 8
    assert selected[0]["row_label"] == "% Growth"
    assert selected[0]["previous_row_label"] == "% Growth"
    assert "duplicate_adjacent_label" in selected[0]["evidence"]
    assert selected[0]["downstream_ref_count"] == 3
    assert selected[0]["downstream_sample"][0]["sheet"] == "Model"
    assert "not a golden insert list" in geometry["note"]
    assert all(candidate["sheet"] != "Debt" for candidate in selected)
    assert all(candidate["sheet"] != "Model" for candidate in selected)


def test_formula_error_representative_includes_capped_neighboring_literals() -> None:
    calc_tool = _calc_tool_module()
    blank_row = ["", "", "", "", ""]
    sheet = calc_tool._formula_anomaly_sheet(
        sheet="Model",
        used_range="A1:E5",
        result={
            "values": [
                [None, None, 2024, None, None],
                list(blank_row),
                ["Gross margin", 123, None, None, 456],
                list(blank_row),
                [None, None, "Forecast", None, None],
            ],
            "formulas": [
                list(blank_row),
                list(blank_row),
                ["", "", "=C1*#REF!", "", ""],
                list(blank_row),
                list(blank_row),
            ],
            "errors": [
                [None, None, None, None, None],
                [None, None, None, None, None],
                [None, None, "#REF!", None, None],
                [None, None, None, None, None],
                [None, None, None, None, None],
            ],
        },
    )

    observation = calc_tool._formula_anomaly_workbook_observation(
        title="input.xlsx",
        url=None,
        sheets=[sheet],
    )

    representative = observation["formula_errors"]["selected_cells"][0]
    assert representative["context"] == [
        {"address": "A3", "value": "Gross margin", "relation": "row_left", "distance": 2},
        {"address": "E3", "value": 456, "relation": "row_right", "distance": 2},
        {"address": "C1", "value": 2024, "relation": "column_above", "distance": 2},
        {
            "address": "C5",
            "value": "Forecast",
            "relation": "column_below",
            "distance": 2,
        },
    ]


def test_formula_blocks_accept_cell_range_alias() -> None:
    calc_tool = _calc_tool_module()
    operations = calc_tool._formula_blocks(
        json.dumps(
            [{"sheet": "Model", "cell_range": "C9:F9", "formula": "=C6-C7+C8"}]
        ),
        CalcOperation,
    )

    assert operations[0].sheet == "Model"
    assert operations[0].range == "C9:F9"
    assert operations[0].formula == "=C6-C7+C8"


def test_formula_blocks_reject_incomplete_operations_before_execution() -> None:
    calc_tool = _calc_tool_module()

    with pytest.raises(ValueError, match="range"):
        calc_tool._formula_blocks('[{"sheet":"Model","formula":"=1"}]', CalcOperation)


def test_region_occupancy_exposes_a_ragged_block_the_bounding_box_hides() -> None:
    """A region is a bounding box, and three unrelated models overfilled its implied corners.

    Template 05_01 C23 and 06_24 G11:G17 were both filled because the rectangle read as solid.
    The occupancy descriptor names the columns that do not span the whole block.
    """
    calc_tool = _calc_tool_module()

    observation = calc_tool._structure_sheet_observation(
        sheet="DeferredTax",
        used_range="B16:F19",
        result={
            "values": [
                ["Schedule", "", "", "", ""],
                ["", "Y1", "Y2", "Y3", "Y4"],
                ["Opening", 10, 20, 30, 40],
                # Row 19 is a total row: B is populated, C never is.
                ["Total", "", 20, 30, 40],
            ],
            "formulas": [[""] * 5 for _ in range(4)],
            "errors": [[None] * 5 for _ in range(4)],
        },
    )

    occupancy = {entry["range"]: entry for entry in observation["region_occupancy"]}
    assert occupancy, "a ragged region must be reported"
    entry = next(iter(occupancy.values()))
    # C stops at row 18; the bounding box runs to 19, which is the cell models overfill.
    assert entry["column_extents"]["C"] == "17:18"
    # D:F share one extent, so they collapse into a single run rather than three entries.
    assert entry["column_extents"]["D:F"] == "17:19"
    # The header row is narrower than the block, the shape that produced row_extended_right.
    assert entry["row_extents"]["16"] == "B:B"
    # Row 18 spans the whole block, so it is absent and it breaks the run around it.
    assert "18" not in entry["row_extents"]


def test_region_occupancy_reports_a_column_that_stops_before_the_block_ends() -> None:
    """21 of Template's 34 regression-first failures are a column continued past its last row.

    The extent states where the run stops. It is a fact, not an instruction: the same geometry
    is what boundary_continuations asks models to extend.
    """
    calc_tool = _calc_tool_module()

    observation = calc_tool._structure_sheet_observation(
        sheet="Schedule",
        used_range="B19:C23",
        result={
            "values": [
                ["Jan", 1],
                ["Feb", 2],
                ["Mar", 3],
                ["Apr", 4],
                # C23 is the blank three models filled because the rectangle implied it.
                ["Total", ""],
            ],
            "formulas": [[""] * 2 for _ in range(5)],
            "errors": [[None] * 2 for _ in range(5)],
        },
    )

    entry = observation["region_occupancy"][0]
    assert entry["range"] == "B19:C23"
    assert entry["column_extents"]["C"] == "19:22"


def test_region_occupancy_caps_runs_and_reports_the_remainder() -> None:
    calc_tool = _calc_tool_module()

    # Alternating extents defeat run grouping, so every column is its own entry.
    limit = observation_module._OCCUPANCY_RUN_LIMIT
    columns = 2 * limit + 4
    values = [
        ["x" if row == 0 or column % 2 == row else "" for column in range(columns)]
        for row in range(3)
    ]
    observation = calc_tool._structure_sheet_observation(
        sheet="Wide",
        used_range=f"A1:{grid_module.column_label(columns)}3",
        result={
            "values": values,
            "formulas": [[""] * columns for _ in range(3)],
            "errors": [[None] * columns for _ in range(3)],
        },
    )

    entry = observation["region_occupancy"][0]
    assert len(entry["column_extents"]) == limit
    assert entry["column_extents_omitted"] > 0


def test_region_occupancy_stays_silent_when_a_block_really_is_solid() -> None:
    calc_tool = _calc_tool_module()

    observation = calc_tool._structure_sheet_observation(
        sheet="Model",
        used_range="B2:D3",
        result={
            "values": [["a", "b", "c"], ["d", "e", "f"]],
            "formulas": [[""] * 3 for _ in range(2)],
            "errors": [[None] * 3 for _ in range(2)],
        },
    )

    assert observation["region_occupancy"] == []
