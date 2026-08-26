from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


def _runner_module():
    path = Path(__file__).parents[1] / "benchmark/run_openrouter_slice.py"
    spec = importlib.util.spec_from_file_location("benchmark_openrouter_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_find_output_scopes_by_category(tmp_path: Path) -> None:
    runner = _runner_module()
    work_root = tmp_path / "SWE-agent"
    template_output = work_root / "trajectories/output_excel/Template/run/01_04_output.xlsx"
    fm_output = work_root / "trajectories/output_excel/Financial_Model/run/01_04_output.xlsx"
    template_output.parent.mkdir(parents=True)
    fm_output.parent.mkdir(parents=True)
    template_output.write_bytes(b"template")
    fm_output.write_bytes(b"financial-model")

    found_template = runner._find_output(work_root, "Template", "01_04", set())
    found_fm = runner._find_output(work_root, "Financial_Model", "01_04", set())

    assert found_template.read_bytes() == b"template"
    assert found_fm.read_bytes() == b"financial-model"


def test_viz_config_exposes_chart_tools(tmp_path: Path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet-viz.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="grid-v1",
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundle_path = Path(config["agent"]["tools"]["bundles"][0]["path"])
    tool_names = yaml.safe_load((bundle_path / "config.yaml").read_text(encoding="utf-8"))["tools"]
    assert "calc_inspect_charts" in tool_names
    assert "calc_upsert_chart" in tool_names
    template = config["agent"]["templates"]["instance_template"]
    assert "calc_upsert_chart" in template
    assert "calc_inspect_charts" in template


def test_memory_chart_roundtrip_via_domain_ops() -> None:
    from librecalc_mcp.backend.memory import MemoryCalcBackend
    from librecalc_mcp.domain.models import CalcOperation

    backend = MemoryCalcBackend()
    spec = {
        "id": "sales_chart",
        "sheet": "Sheet1",
        "chart_type": "line",
        "category_range": "A2:A5",
        "series": [{"name": "Revenue", "values_range": "B2:B5"}],
        "title": "Revenue Trend",
    }
    result = backend.execute_program(
        [CalcOperation.from_dict({"op": "upsert_chart", "chart": spec})]
    )
    assert result["ok"] is True
    charts = backend.inspect_charts()
    assert charts[0]["id"] == "sales_chart"
    assert charts[0]["title"] == "Revenue Trend"
    assert charts[0]["category_range"] == "A2:A5"
