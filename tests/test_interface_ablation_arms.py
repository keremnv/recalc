"""The three interface arms of the ablation in PROJECT_CONTEXT.md section 28.

A -> B isolates observation richness; B -> C isolates one-call program execution.
Each arm's tool set and its prompt have to agree, or the run measures the mismatch
instead of the interface.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parents[1]


def _runner_module():
    spec = importlib.util.spec_from_file_location(
        "run_openrouter_slice", PROJECT_ROOT / "benchmark/run_openrouter_slice.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _stage(tmp_path, *, read_policy: str, execution: str, observation: str):
    runner = _runner_module()
    staged = runner._stage_tool_policy(
        source_config=PROJECT_ROOT / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=PROJECT_ROOT / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy=read_policy,
        execution=execution,
        observation=observation,
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundle = Path(config["agent"]["tools"]["bundles"][0]["path"])
    tools = yaml.safe_load((bundle / "config.yaml").read_text(encoding="utf-8"))["tools"]
    return config, set(tools)


def test_arm_a_thin_has_no_semantic_or_batched_affordances(tmp_path) -> None:
    config, tools = _stage(
        tmp_path, read_policy="thin", execution="cell-writes-v1", observation="grid-v1"
    )

    assert tools == {"calc_inspect", "calc_read", "calc_write"}
    template = config["agent"]["templates"]["instance_template"]
    assert "Batched reads are unavailable" in template
    assert "Semantic comparison is unavailable" in template
    assert "every cell must be given explicitly" in template
    assert "calc_read_ranges" not in config["agent"]["templates"]["system_template"]


def test_arm_b_semantic_keeps_observation_but_not_program_execution(tmp_path) -> None:
    config, tools = _stage(
        tmp_path,
        read_policy="progressive",
        execution="cell-writes-v1",
        observation="formula-patterns-v1",
    )

    assert tools == {"calc_inspect", "calc_read", "calc_read_ranges", "calc_compare", "calc_write"}
    template = config["agent"]["templates"]["instance_template"]
    assert "Relative fill and multi-operation" in template
    # B keeps the semantic surface A lacks.
    assert "Semantic comparison is unavailable" not in template


def test_arm_c_semantic_program_is_the_frozen_lane(tmp_path) -> None:
    _config, tools = _stage(
        tmp_path,
        read_policy="progressive",
        execution="formula-blocks-v1",
        observation="formula-patterns-v1",
    )

    assert tools == {"calc_inspect", "calc_read", "calc_read_ranges", "calc_compare",
                     "calc_fill_formulas"}


def test_arms_differ_only_where_the_ablation_intends(tmp_path) -> None:
    _a_config, a_tools = _stage(
        tmp_path / "a", read_policy="thin", execution="cell-writes-v1", observation="grid-v1"
    )
    _b_config, b_tools = _stage(
        tmp_path / "b",
        read_policy="progressive",
        execution="cell-writes-v1",
        observation="formula-patterns-v1",
    )
    _c_config, c_tools = _stage(
        tmp_path / "c",
        read_policy="progressive",
        execution="formula-blocks-v1",
        observation="formula-patterns-v1",
    )

    # A -> B adds only read-side affordances; the write surface is identical.
    assert b_tools - a_tools == {"calc_read_ranges", "calc_compare"}
    assert "calc_write" in a_tools and "calc_write" in b_tools
    # B -> C changes only the write surface.
    assert b_tools - c_tools == {"calc_write"}
    assert c_tools - b_tools == {"calc_fill_formulas"}


def test_thin_arm_lifts_the_semantic_lane_read_cap() -> None:
    """The 96-cell cap presumes calc_inspect exists. Arm A has none."""
    import importlib
    import os
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "benchmark/sweagent/librecalc/lib"))
    calc_tool = importlib.import_module("calc_tool")
    try:
        previous = os.environ.pop("LIBRECALC_READ_MAX_CELLS", None)
        assert calc_tool._read_neighborhood_limit() == 96
        calc_tool._require_neighborhood_range("A1:L8", label="calc_read range")

        os.environ["LIBRECALC_READ_MAX_CELLS"] = "none"
        assert calc_tool._read_neighborhood_limit() is None
        # A whole used range is a legitimate read when nothing summarises it for you.
        calc_tool._require_neighborhood_range("A1:Z400", label="calc_read range")
    finally:
        os.environ.pop("LIBRECALC_READ_MAX_CELLS", None)
        if previous is not None:
            os.environ["LIBRECALC_READ_MAX_CELLS"] = previous
        sys.path.remove(str(PROJECT_ROOT / "benchmark/sweagent/librecalc/lib"))


def test_default_read_cap_still_binds_for_the_semantic_lane() -> None:
    import importlib
    import os
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "benchmark/sweagent/librecalc/lib"))
    calc_tool = importlib.import_module("calc_tool")
    try:
        os.environ.pop("LIBRECALC_READ_MAX_CELLS", None)
        try:
            calc_tool._require_neighborhood_range("A1:L41", label="calc_read range")
        except ValueError as exc:
            assert "492 cells" in str(exc)
        else:
            raise AssertionError("oversize read should still be rejected by default")
    finally:
        sys.path.remove(str(PROJECT_ROOT / "benchmark/sweagent/librecalc/lib"))
