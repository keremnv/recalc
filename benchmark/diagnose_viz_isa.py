#!/usr/bin/env python3
"""Gold-blind diagnosis of the visualization chart ISA.

Does not change the world. Writes a JSON report Sol can implement against:
domain claims vs UNO apply vs inspect round-trip vs PNG size.

Live UNO probes run only when a listener is up (same as LIBRECALC_RUN_UNO=1).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, get_args

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from librecalc_mcp.domain.charts import (
    NATIVE_UNO_CHART_TYPES,
    ChartType,
    chart_compile_note,
)

UNO_CHARTS = PROJECT_ROOT / "src/librecalc_mcp/backend/uno_charts.py"
TOOL_DOCS = PROJECT_ROOT / "benchmark/sweagent/librecalc/config.yaml"


def _static_gaps() -> list[dict[str, str]]:
    source = UNO_CHARTS.read_text(encoding="utf-8")
    docs = TOOL_DOCS.read_text(encoding="utf-8")
    inspect_fn = source.split("def inspect_charts_from_document", 1)[-1].split("def ", 1)[0]
    gaps = []
    if "bubble_size_range" not in source or "x_values_range" not in source:
        gaps.append(
            {
                "id": "bubble_size_range_unwired",
                "severity": "blocking",
                "task_class": "Task 95 bubble",
                "finding": (
                    "Task 95 needs four independent channels: product labels, X=revenue, "
                    "Y=growth, and size=market. ChartSeriesSpec and UNO binding must expose "
                    "both x_values_range and bubble_size_range."
                ),
            }
        )
    if "number_format" not in source.split("def _apply_axis", 1)[-1].split("def ", 1)[0]:
        gaps.append(
            {
                "id": "axis_number_format_unwired",
                "severity": "blocking",
                "task_class": "Task 1411527 line dates",
                "finding": (
                    "ChartAxisSpec.number_format is accepted on ChartSpec but "
                    "_apply_axis never sets a NumberFormat / axis key. "
                    "dd/mm/yyyy on the category axis cannot land."
                ),
            }
        )
    if '"category_range"' not in inspect_fn and "'category_range'" not in inspect_fn:
        gaps.append(
            {
                "id": "uno_inspect_thin",
                "severity": "blocking",
                "task_class": "all viz",
                "finding": (
                    "calc_inspect_charts docs promise category_range, series ranges, "
                    "and compile_note. UNO inspect_charts_from_document only emits "
                    "id, sheet, title, chart_type, has_legend. Agents cannot verify "
                    "what they just upserted."
                ),
            }
        )
    if "compile_note" in docs and "compile_note" not in inspect_fn:
        gaps.append(
            {
                "id": "inspect_docstring_overclaim",
                "severity": "docs",
                "task_class": "all viz",
                "finding": "Tool docstring overclaims UNO inspect payload.",
            }
        )
    return gaps


def _compile_note_matrix() -> dict[str, str | None]:
    types: tuple[ChartType, ...] = get_args(ChartType)
    return {chart_type: chart_compile_note(chart_type) for chart_type in types}


def _uno_probes() -> dict[str, Any]:
    from librecalc_mcp.backend.uno import UnoCalcBackend
    from librecalc_mcp.domain.models import CalcOperation

    backend = UnoCalcBackend()
    health = backend.health()
    if not health.get("ok"):
        return {"ok": False, "health": health}

    from openpyxl import Workbook

    reports: list[dict[str, Any]] = []
    fixtures = [
        {
            "id": "bubble_task95_shape",
            "chart": {
                "id": "Portfolio",
                "sheet": "Sheet1",
                "chart_type": "bubble",
                "category_range": "A2:A5",
                "series": [
                    {
                        "name": "Products",
                        "x_values_range": "B2:B5",
                        "values_range": "C2:C5",
                        "bubble_size_range": "D2:D5",
                        "point_colors": ["#00AA00", "#888888", "#888888", "#FF0000"],
                    }
                ],
                "title": "Product Portfolio Analysis",
                "legend": False,
                "data_labels": True,
                "anchor": "E2",
            },
        },
        {
            "id": "line_task1411527_shape",
            "chart": {
                "id": "Burndown",
                "sheet": "Sheet1",
                "chart_type": "line",
                "category_range": "A2:A5",
                "series": [
                    {"name": "Goal", "values_range": "B2:B5", "color": "#808080"},
                    {"name": "Count", "values_range": "C2:C5", "color": "#0000FF"},
                ],
                "title": "Invoice Count Burndown August 2023",
                "x_axis": {"number_format": "dd/mm/yyyy", "label_rotation": 45},
                "y_axis": {"min": 0, "max": 800, "title": "Count"},
                "anchor": "E2",
            },
        },
        {
            "id": "stacked_task1417365_shape",
            "chart": {
                "id": "Sales",
                "sheet": "Sheet1",
                "chart_type": "stacked_column",
                "category_range": "A2:A5",
                "series": [
                    {"name": "Type A", "values_range": "B2:B5"},
                    {"name": "Type B", "values_range": "C2:C5"},
                ],
                "title": "Sales",
                "x_axis": {"title": "Quarter"},
                "y_axis": {"title": "Sales Value"},
                "anchor": "E2",
            },
        },
        {
            "id": "combo_honest_refusal",
            "chart": {
                "id": "Combo",
                "sheet": "Sheet1",
                "chart_type": "combo",
                "category_range": "A2:A5",
                "series": [{"name": "S", "values_range": "B2:B5"}],
            },
        },
    ]

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        seed = root / "seed.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet["A1"] = "Cat"
        sheet["B1"] = "X"
        sheet["C1"] = "Y"
        sheet["D1"] = "Size"
        for index, label in enumerate(["A", "B", "C", "D"], start=2):
            sheet[f"A{index}"] = label
            sheet[f"B{index}"] = index * 10
            sheet[f"C{index}"] = index * 3
            sheet[f"D{index}"] = index * 5
        workbook.save(seed)

        for fixture in fixtures:
            output = root / f"{fixture['id']}.xlsx"
            png_dir = root / fixture["id"]
            png_dir.mkdir()
            result = backend.execute_program(
                [
                    CalcOperation.from_dict(
                        {"op": "upsert_chart", "chart": fixture["chart"]}
                    )
                ],
                path=str(seed),
                output_path=str(output),
            )
            inspect = backend.inspect_charts(str(output)) if output.is_file() else []
            exported: list[str] = []
            png_error = None
            try:
                exported = backend.export_charts_png(
                    str(output), str(png_dir), file_prefix=fixture["id"]
                )
            except Exception as exc:  # noqa: BLE001 — diagnosis must record the miss
                png_error = f"{type(exc).__name__}: {exc}"
            sizes = []
            for path in exported:
                png = Path(path)
                sizes.append({"path": path, "bytes": png.stat().st_size if png.is_file() else 0})
            reports.append(
                {
                    "id": fixture["id"],
                    "execute": result,
                    "inspect": inspect,
                    "png": {"exported": exported, "sizes": sizes, "error": png_error},
                }
            )

    return {"ok": True, "health": health, "fixtures": reports}


def main() -> int:
    report = {
        "native_uno_types": sorted(NATIVE_UNO_CHART_TYPES),
        "compile_notes": _compile_note_matrix(),
        "static_gaps": _static_gaps(),
        "uno": _uno_probes(),
    }
    destination = PROJECT_ROOT / "docs" / "viz-isa-diagnosis.json"
    destination.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(destination), "gaps": [g["id"] for g in report["static_gaps"]], "uno_ok": report["uno"].get("ok")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
