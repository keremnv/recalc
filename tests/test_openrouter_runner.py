import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


def _runner_module():
    path = Path(__file__).parents[1] / "benchmark/run_openrouter_slice.py"
    spec = importlib.util.spec_from_file_location("benchmark_openrouter_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_preflight_helpers_require_tools_and_use_worst_case_prices() -> None:
    runner = _runner_module()
    catalog = {
        "data": [
            {
                "id": "example/model",
                "supported_parameters": ["max_tokens", "tools"],
                "pricing": {
                    "prompt": "0.000001",
                    "completion": "0.000002",
                    "overrides": [
                        {"min_prompt_tokens": 1000, "prompt": "0.000003", "completion": "0.000004"}
                    ],
                },
            }
        ]
    }

    model = runner._openrouter_model(catalog, "example/model")
    assert runner._maximum_token_price(model, "prompt") == pytest.approx(0.000003)
    assert runner._maximum_token_price(model, "completion") == pytest.approx(0.000004)


def test_librecalc_bundle_passes_sweagent_command_validation() -> None:
    project_root = Path(__file__).parents[1]
    sweagent_root = project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent"
    bundle = project_root / "benchmark/sweagent/librecalc"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(sweagent_root)

    result = subprocess.run(
        [
            str(sweagent_root / ".venv/bin/python"),
            "-c",
            (
                "from pathlib import Path; "
                "from sweagent.tools.bundle import Bundle; "
                f"bundle = Bundle(path=Path({str(bundle)!r})); "
                "assert {command.name for command in bundle.commands} >= "
                "{'calc_read', 'calc_read_ranges'}"
            ),
        ],
        cwd=sweagent_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_calc_wrapper_preserves_agent_shell_after_structured_tool_error(tmp_path) -> None:
    project_root = Path(__file__).parents[1]
    tool_root = tmp_path / "librecalc"
    (tool_root / "lib").mkdir(parents=True)
    (tool_root / "lib/calc_tool.py").write_text(
        'import sys\nprint(\'{"ok":false,"error":"invalid blocks"}\')\nraise SystemExit(1)\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["LIBRECALC_TOOL_ROOT"] = str(tool_root)

    result = subprocess.run(
        [
            "bash",
            "-c",
            "set -e; benchmark/sweagent/librecalc/bin/calc_fill_formulas x y z; printf survived",
        ],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        '{"ok":false,"error":"invalid blocks"}',
        "survived",
    ]


def test_model_preflight_helpers_reject_a_model_without_tools() -> None:
    runner = _runner_module()
    catalog = {
        "data": [
            {
                "id": "example/no-tools",
                "supported_parameters": ["max_tokens"],
                "pricing": {"prompt": "0.1", "completion": "0.2"},
            }
        ]
    }

    with pytest.raises(ValueError, match="lacks required parameters"):
        runner._openrouter_model(catalog, "example/no-tools")


def test_reasoning_effort_validation_respects_model_capabilities() -> None:
    runner = _runner_module()
    model = {
        "id": "example/reasoner",
        "supported_parameters": ["reasoning"],
        "reasoning": {"mandatory": True, "supported_efforts": ["high", "low"]},
    }

    runner._validate_reasoning_effort(model, "low")
    with pytest.raises(ValueError, match="requires reasoning"):
        runner._validate_reasoning_effort(model, "none")
    with pytest.raises(ValueError, match="supports reasoning efforts"):
        runner._validate_reasoning_effort(model, "medium")


def test_strict_loop_requires_one_nonparallel_tool_call() -> None:
    runner = _runner_module()
    args = type("Args", (), {"max_tokens": 2048, "reasoning_effort": "minimal"})()
    model = {
        "supported_parameters": ["tools", "parallel_tool_calls"],
        "safety_prompt_price_per_token": 0.000001,
        "safety_completion_price_per_token": 0.000002,
    }

    kwargs = runner._completion_kwargs(args, model)

    assert kwargs["tool_choice"] == "required"
    assert kwargs["parallel_tool_calls"] is False
    assert kwargs["reasoning"] == {"effort": "minimal"}
    assert kwargs["max_tokens"] == 2048


def test_muse_spark_uses_auto_tool_choice() -> None:
    runner = _runner_module()
    args = type("Args", (), {"max_tokens": None, "reasoning_effort": "medium"})()
    for model_id in ("meta/muse-spark-1.2", "meta/muse-spark-1.2-contributor"):
        kwargs = runner._completion_kwargs(
            args,
            {
                "id": model_id,
                "supported_parameters": ["tools", "parallel_tool_calls", "reasoning"],
                "safety_prompt_price_per_token": 0.0000001,
                "safety_completion_price_per_token": 0.0000002,
            },
        )
        assert kwargs["tool_choice"] == "auto", model_id
        assert kwargs["parallel_tool_calls"] is False


def test_glm_53_uses_auto_tool_choice() -> None:
    runner = _runner_module()
    args = type("Args", (), {"max_tokens": None, "reasoning_effort": "high"})()
    kwargs = runner._completion_kwargs(
        args,
        {
            "id": "z-ai/glm-5.3",
            "supported_parameters": ["tools", "reasoning", "reasoning_effort"],
            "safety_prompt_price_per_token": 0.0000014,
            "safety_completion_price_per_token": 0.0000044,
        },
    )
    assert kwargs["tool_choice"] == "auto"
    assert "parallel_tool_calls" not in kwargs


def test_default_response_allowance_is_derived_from_remaining_budget() -> None:
    runner = _runner_module()
    args = type("Args", (), {"max_tokens": None, "reasoning_effort": None})()
    model = {
        "supported_parameters": ["tools"],
        "safety_prompt_price_per_token": 0.000001,
        "safety_completion_price_per_token": 0.000002,
    }

    kwargs = runner._completion_kwargs(args, model)

    assert kwargs["librecalc_budget_max_tokens"] is True
    assert "max_tokens" not in kwargs


def test_provider_billing_is_not_inflated_by_harness_safety_prices() -> None:
    runner = _runner_module()

    charged_cost, budget_enforcement_cost = runner._cost_accounting(
        key_usage_delta=0.03727344,
        generation_cost=0.03727344,
        harness_cost=0.038928,
    )

    assert charged_cost == pytest.approx(0.03727344)
    assert budget_enforcement_cost == pytest.approx(0.038928)


def test_call_limit_overlay_checks_before_an_additional_query() -> None:
    runner = _runner_module()
    source = """    def query(self, history: History, n: int = 1, temperature: float | None = None) -> list[dict] | dict:
        messages = self._history_to_messages(history)
"""

    patched = runner._patch_sweagent_call_boundary(source)

    assert "per_instance_call_limit <= self.stats.api_calls" in patched
    assert "Per instance call limit reached before query" in patched
    assert runner._patch_sweagent_call_boundary(patched) == patched


def test_budget_overlay_derives_and_reserves_an_affordable_response() -> None:
    runner = _runner_module()
    source = """        if self.model_max_input_tokens is None:
            pass
"""

    patched = runner._patch_sweagent_budget_boundary(source)

    assert 'pop("librecalc_budget_max_tokens", False)' in patched
    assert 'self.config.completion_kwargs.pop("max_tokens", None)' in patched
    assert "remaining_cost - safety_input_cost" in patched
    assert "self.model_max_output_tokens or 8192" in patched
    assert 'self.config.completion_kwargs["max_tokens"] = safety_max_output' in patched
    assert "safety_max_output * safety_output_price" in patched
    assert "exceeds per-instance cost limit before query" in patched
    assert runner._patch_sweagent_budget_boundary(patched) == patched


def test_staged_sweagent_overlay_with_dynamic_budget_compiles(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]

    overlay = runner._stage_sweagent_overlay(
        project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        tmp_path,
    )
    models_path = overlay / "sweagent/agent/models.py"
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(models_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_runner_allows_one_bounded_format_repair_by_default(monkeypatch) -> None:
    runner = _runner_module()
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_openrouter_slice.py", "--slice", "slice.json", "--run-name", "probe"],
    )

    args = runner._arguments()

    assert args.max_requeries == 2
    assert args.execution_timeout == 180
    assert args.max_tokens is None
    assert args.read_budget is True
    assert args.blank_bridges is True


def test_read_budget_flag_can_be_disabled(monkeypatch) -> None:
    runner = _runner_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_openrouter_slice.py",
            "--slice",
            "slice.json",
            "--run-name",
            "probe",
            "--no-read-budget",
        ],
    )

    args = runner._arguments()

    assert args.read_budget is False


def test_overview_only_policy_removes_read_tool_and_updates_prompt(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="overview-only",
        execution="semantic-program-v1",
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundle = Path(config["agent"]["tools"]["bundles"][0]["path"])
    tools = yaml.safe_load((bundle / "config.yaml").read_text(encoding="utf-8"))["tools"]

    assert "calc_read" not in tools
    assert "calc_read_ranges" not in tools
    assert "calc_compare" in tools
    assert bundle.name == "librecalc"
    assert "focused range reads are intentionally unavailable" in config["agent"]["templates"][
        "instance_template"
    ]
    assert all(Path(item["path"]).is_absolute() for item in config["agent"]["tools"]["bundles"])


def test_progressive_policy_keeps_read_tool_and_absolutizes_bundles(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        execution_timeout=180,
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundles = config["agent"]["tools"]["bundles"]

    assert all(Path(item["path"]).is_absolute() for item in bundles)
    assert config["agent"]["tools"]["execution_timeout"] == 180
    assert "Do not inspect directories, guess" in config["agent"]["templates"]["system_template"]
    tools = yaml.safe_load((Path(bundles[0]["path"]) / "config.yaml").read_text(encoding="utf-8"))
    assert "calc_read" in tools["tools"]
    assert "calc_read_ranges" in tools["tools"]


def test_formula_block_policy_exposes_only_compact_formula_writes(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="overview-only",
        execution="formula-blocks-v1",
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundle = Path(config["agent"]["tools"]["bundles"][0]["path"])
    tools = yaml.safe_load((bundle / "config.yaml").read_text(encoding="utf-8"))["tools"]

    assert set(tools) == {"calc_inspect", "calc_compare", "calc_fill_formulas"}
    assert "cell-by-cell formula enumeration is unavailable" in config["agent"]["templates"][
        "instance_template"
    ]


def test_formula_anomalies_progressive_prompt_confirms_shortlist_then_writes(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="formula-blocks-v1",
        observation="formula-anomalies-v1",
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    template = config["agent"]["templates"]["instance_template"]
    tools = yaml.safe_load(
        (Path(config["agent"]["tools"]["bundles"][0]["path"]) / "config.yaml").read_text(
            encoding="utf-8"
        )
    )["tools"]

    assert "calc_read" in tools
    assert "calc_read_ranges" in tools
    assert "At most one confirmation pass" in template
    assert "compact formula-error" in template
    assert "reads over 96 cells are rejected" in template
    assert "Never read a whole sheet" in template
    assert "Do not start another inspection" in template
    assert "do not reread the whole used" not in template
    assert "The anomaly shortlist is the confirmation surface" not in template
    assert "After inspect, confirm the shortlist once if needed" in config["agent"]["templates"][
        "system_template"
    ]


def test_formula_anomalies_with_program_execution_allows_geometry_ops(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="formula-anomalies-v1",
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    tools = yaml.safe_load(
        (Path(config["agent"]["tools"]["bundles"][0]["path"]) / "config.yaml").read_text(
            encoding="utf-8"
        )
    )["tools"]
    system = config["agent"]["templates"]["system_template"]

    assert "calc_program" in tools
    assert "calc_write" in tools
    assert "insert_row/delete_row" in system
    assert "then calc_fill_formulas." not in system
