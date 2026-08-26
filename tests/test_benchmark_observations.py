"""Observation and diff models, exercised against the in-memory backend.

These used to load the SWE-agent wrapper by file path because the models lived
inside the harness. They are product code now, so they import normally and run
without LibreOffice or the benchmark bundle.
"""

import importlib.util
import json
import urllib.parse
from pathlib import Path

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
    meaningful_note = "Cash taxes are lower because the deferred tax asset reverses at maturity. " * 3
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
    assert calc_tool._format_read_observation(
        {"values": [["Label", 5]], "formulas": [["Label", "=1+4"]]},
        sheet="Sheet1",
        cell_range="C7:D7",
        variant="structure-first-v1",
    ) == {
        "sheet": "Sheet1",
        "range": "C7:D7",
        "cells": [
            {"address": "C7", "value": "Label"},
            {"address": "D7", "value": 5, "formula": "=1+4"},
        ],
    }


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
    requests = urllib.parse.quote(
        '[{"sheet":"Sheet1","range":"A1:I16"},'
        '{"sheet":"Sheet1","range":"A1:B1"}]',
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
                    "whole sheet."
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
        item["address"]
        for item in observation["translation_consensus"]["selected_candidates"]
    ] == ["B2"]
    assert [
        item["address"] for item in observation["short_sequence_gaps"]["selected_candidates"]
    ] == ["B2"]
    assert observation["translation_consensus"]["format_candidates_deprioritized"] == 1


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
    assert diff["sheet_changes"]["Model"]["formula_errors"]["added"] == {
        "E6": "#VALUE!"
    }
    assert diff["sheet_changes"]["Model"]["candidate_gaps"] == {
        "resolved": {"D6:F6": "Beginning cash"},
        "new": {},
        "note": "Heuristic structural gaps, not validation failures.",
    }


def test_semantic_diff_filters_numeric_noise_and_bounds_downstream_values() -> None:
    calc_tool = _calc_tool_module()
    before_formulas = {
        f"A{row}": {"expression": f"=B{row}", "value": float(row)}
        for row in range(1, 102)
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
    assert downstream["by_sheet"] == {
        "Model": {"count": 100, "affected_range": "A2:A101"}
    }
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
    assert result["sheet_changes"]["Model"]["formulas"]["added"] == {
        "B1": "=SUM(B2:B3)"
    }


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


def test_neighborhood_reads_reject_used_range_dumps() -> None:
    calc_tool = _calc_tool_module()

    assert calc_tool._a1_cell_count("A1:H12") == 96
    assert calc_tool._a1_cell_count("A1") == 1
    calc_tool._require_neighborhood_range("A1:H12", label="range")

    try:
        calc_tool._range_requests(
            '[{"sheet":"Operating Model + DCF","range":"A1:AA43"}]'
        )
    except ValueError as exc:
        assert "1161 cells" in str(exc)
        assert "96 cells" in str(exc)
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


def test_formula_blocks_reject_incomplete_operations_before_execution() -> None:
    calc_tool = _calc_tool_module()

    try:
        calc_tool._formula_blocks('[{"sheet":"Model","formula":"=1"}]', CalcOperation)
    except ValueError as exc:
        assert "requires only string fields" in str(exc)
    else:
        raise AssertionError("incomplete formula block was accepted")
