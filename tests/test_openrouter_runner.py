import ast
import importlib.util
import os
import subprocess
import sys
import textwrap
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
    """Typed nested items only load after Argument.items is dict[str, Any], not dict[str, str]."""

    pydantic = pytest.importorskip("pydantic")
    tools = yaml.safe_load(
        (Path(__file__).parents[1] / "benchmark/sweagent/librecalc/config.yaml").read_text(
            encoding="utf-8"
        )
    )["tools"]

    class UpstreamArgument(pydantic.BaseModel):
        name: str
        type: str
        items: dict[str, str] | None = None
        description: str
        required: bool
        enum: list[str] | None = None
        argument_format: str = "{{value}}"

    class OverlayArgument(pydantic.BaseModel):
        name: str
        type: str
        items: dict[str, object] | None = None
        description: str
        required: bool
        enum: list[str] | None = None
        argument_format: str = "{{value}}"

    class OverlayCommand(pydantic.BaseModel):
        name: str
        docstring: str | None = None
        signature: str | None = None
        arguments: list[OverlayArgument]

    class UpstreamCommand(pydantic.BaseModel):
        name: str
        docstring: str | None = None
        signature: str | None = None
        arguments: list[UpstreamArgument]

    with pytest.raises(pydantic.ValidationError, match="valid string"):
        UpstreamCommand(name="calc_read_ranges", **tools["calc_read_ranges"])

    loaded = {
        name: OverlayCommand(name=name, **tool_config) for name, tool_config in tools.items()
    }
    assert loaded.keys() >= {"calc_read", "calc_read_ranges", "calc_fill_formulas"}
    ranges = next(a for a in loaded["calc_read_ranges"].arguments if a.name == "ranges_json")
    assert ranges.items["properties"]["range"]["type"] == "string"
    blocks = next(
        a for a in loaded["calc_fill_formulas"].arguments if a.name == "formula_blocks_json"
    )
    assert blocks.items["required"] == ["sheet", "range", "formula"]


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


def test_provider_pin_disables_fallbacks_and_omits_aggregate_only_parameters() -> None:
    runner = _runner_module()
    args = type(
        "Args",
        (),
        {
            "max_tokens": None,
            "reasoning_effort": "high",
            "provider_only": ["inceptron"],
        },
    )()
    model = {
        "supported_parameters": ["tools", "reasoning", "parallel_tool_calls"],
        "safety_prompt_price_per_token": 0.000001,
        "safety_completion_price_per_token": 0.000002,
    }

    kwargs = runner._completion_kwargs(args, model)

    assert kwargs["provider"] == {
        "only": ["inceptron"],
        "allow_fallbacks": False,
    }
    assert "require_parameters" not in kwargs["provider"]
    assert "parallel_tool_calls" not in kwargs


def test_moonshot_pin_uses_auto_tools_with_reasoning() -> None:
    runner = _runner_module()
    args = type(
        "Args",
        (),
        {
            "max_tokens": None,
            "reasoning_effort": "high",
            "provider_only": ["moonshotai"],
        },
    )()
    model = {
        "id": "moonshotai/kimi-k2.7-code",
        "supported_parameters": ["tools", "reasoning", "tool_choice"],
        "safety_prompt_price_per_token": 0.000001,
        "safety_completion_price_per_token": 0.000002,
    }

    kwargs = runner._completion_kwargs(args, model)

    assert kwargs["tool_choice"] == "auto"


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
    assert "model_output_limit >= int(self.model_max_input_tokens)" in patched
    assert "counted_input = int(input_tokens * 1.5)" in patched
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
    commands_path = overlay / "sweagent/tools/commands.py"
    for path in (models_path, commands_path):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    commands = commands_path.read_text(encoding="utf-8")
    assert "items: dict[str, Any] | None = None" in commands
    assert "from typing import Any" in commands


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
    assert args.preserve_populated is False
    assert args.compute_read_budget is False


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


def test_skip_existing_flag_defaults_off(monkeypatch) -> None:
    runner = _runner_module()
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_openrouter_slice.py", "--slice", "slice.json", "--run-name", "probe"],
    )
    assert runner._arguments().skip_existing is False
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_openrouter_slice.py",
            "--slice",
            "slice.json",
            "--run-name",
            "probe",
            "--skip-existing",
        ],
    )
    assert runner._arguments().skip_existing is True


def test_resume_skips_ledgered_tasks_and_retries_incomplete_dirs(tmp_path: Path) -> None:
    runner = _runner_module()
    recorded = tmp_path / "Template-01_01"
    recorded.mkdir()
    (recorded / "output.xlsx").write_bytes(b"xlsx")
    incomplete = tmp_path / "Template-01_02"
    incomplete.mkdir()
    (incomplete / "stale.txt").write_text("partial", encoding="utf-8")

    assert runner._resume_action(recorded, skip_existing=True, recorded=True) == "skip"
    assert recorded.is_dir()
    assert runner._resume_action(incomplete, skip_existing=True, recorded=False) == "retry"
    assert not incomplete.exists()
    assert (
        runner._resume_action(tmp_path / "Template-01_03", skip_existing=True, recorded=False)
        == "run"
    )


def test_ledger_task_keys_read_finished_rows(tmp_path: Path) -> None:
    runner = _runner_module()
    (tmp_path / "ledger.jsonl").write_text(
        '{"task":"Template:01_01","status":"completed"}\n{"task":"Template:01_02","status":"failed"}\n',
        encoding="utf-8",
    )
    assert runner._ledger_task_keys(tmp_path) == {"Template:01_01", "Template:01_02"}


def test_no_score_flag_defaults_off(monkeypatch) -> None:
    runner = _runner_module()
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_openrouter_slice.py", "--slice", "slice.json", "--run-name", "probe"],
    )
    assert runner._arguments().no_score is False
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_openrouter_slice.py",
            "--slice",
            "slice.json",
            "--run-name",
            "probe",
            "--no-score",
        ],
    )
    assert runner._arguments().no_score is True


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
    assert (
        "focused range reads are intentionally unavailable"
        in config["agent"]["templates"]["instance_template"]
    )
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
    assert (
        "cell-by-cell formula enumeration is unavailable"
        in config["agent"]["templates"]["instance_template"]
    )


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
    assert (
        "After inspect, confirm the shortlist once if needed"
        in config["agent"]["templates"]["system_template"]
    )


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
    assert "deleted_row_geometry" in config["agent"]["templates"]["instance_template"]
    assert "do not dump that" in config["agent"]["templates"]["instance_template"]
    assert "insert_row at insert_row_index" in config["agent"]["templates"]["instance_template"]
    assert "insert_row is the write" in system
    assert "restarting from the input wipes" in system
    assert "do not retry dumps" in system


def test_format_conventions_prompt_uses_bounded_census_and_set_format(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="format-conventions-v1",
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    template = config["agent"]["templates"]["instance_template"]

    assert "font-color census" in template
    assert "Use at most one calc_read_ranges call" in template
    assert "only font_color" in template
    assert "Do not rewrite cell values or formulas" in template
    assert "font-color changes as ranges" in template
    assert "one additional set_format" in template
    assert "empty diff" not in template
    assert "calc_program set_format operations" in config["agent"]["templates"]["system_template"]


def test_formula_anomalies_two_pass_policy_allows_one_output_reinspection(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="formula-anomalies-v1",
        repair_passes=2,
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    instance = config["agent"]["templates"]["instance_template"]
    system = config["agent"]["templates"]["system_template"]

    assert "call calc_inspect once on the output" in instance
    assert "third inspection or repair pass" in instance
    assert "inspect the output once" in system
    assert "Do not start another inspection" not in instance


def test_compute_read_budget_stages_write_from_inspect_prompt(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="formula-blocks-v1",
        observation="formula-patterns-v1",
        compute_read_budget=True,
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    instance = config["agent"]["templates"]["instance_template"]
    system = config["agent"]["templates"]["system_template"]

    assert "at most one calc_read_ranges batch" in instance
    assert "Include those cells in the same calc_fill_formulas" not in instance
    assert "Include boundary_continuations in the same fill" in instance
    assert "write from inspect; do not dump or bash" in system


def test_empty_assistant_turn_is_repaired_before_the_provider_sees_it() -> None:
    runner = _runner_module()
    source = "        messages = self._history_to_messages(history)\n"

    patched = runner._patch_sweagent_empty_assistant(source)

    assert "(no content returned)" in patched
    assert runner._patch_sweagent_empty_assistant(patched) == patched

    body = textwrap.dedent(patched.split(source, 1)[1])
    namespace = {
        "messages": [
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "   "},
            {"role": "assistant", "content": None},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1"}]},
            {"role": "assistant", "content": "a real thought"},
            {"role": "user", "content": ""},
        ]
    }
    exec(body, namespace)  # noqa: S102
    contents = [message["content"] for message in namespace["messages"]]

    # Content-free assistant turns are repaired.
    assert contents[0] == "(no content returned)"
    assert contents[1] == "(no content returned)"
    assert contents[2] == "(no content returned)"
    # A tool-calling assistant turn is legitimately empty and must be left intact.
    assert contents[3] == ""
    # Real assistant content and non-assistant roles are untouched.
    assert contents[4] == "a real thought"
    assert contents[5] == ""


def test_bad_request_is_not_retried() -> None:
    runner = _runner_module()
    source = "                    litellm.exceptions.UnsupportedParamsError,\n"

    patched = runner._patch_sweagent_bad_request_retry(source)

    assert "litellm.exceptions.BadRequestError," in patched
    assert patched.index("BadRequestError") < patched.index("UnsupportedParamsError")
    assert runner._patch_sweagent_bad_request_retry(patched) == patched


def test_sweagent_model_patches_apply_to_the_vendored_source() -> None:
    runner = _runner_module()
    models_path = (
        Path(__file__).parents[1]
        / "benchmark-data/SpreadsheetBench-2/SWE-agent/sweagent/agent/models.py"
    )
    if not models_path.exists():
        pytest.skip("vendored SWE-agent checkout is not present")

    patched = runner._patch_sweagent_call_boundary(models_path.read_text(encoding="utf-8"))
    patched = runner._patch_sweagent_budget_boundary(patched)
    patched = runner._patch_sweagent_empty_assistant(patched)
    patched = runner._patch_sweagent_bad_request_retry(patched)

    ast.parse(patched)
    assert "(no content returned)" in patched
    assert "litellm.exceptions.BadRequestError," in patched


def test_argument_items_overlay_applies_to_the_vendored_source() -> None:
    runner = _runner_module()
    commands_path = (
        Path(__file__).parents[1]
        / "benchmark-data/SpreadsheetBench-2/SWE-agent/sweagent/tools/commands.py"
    )
    if not commands_path.exists():
        pytest.skip("vendored SWE-agent checkout is not present")

    patched = runner._patch_sweagent_nested_argument_items(commands_path.read_text(encoding="utf-8"))
    ast.parse(patched)
    assert "items: dict[str, Any] | None = None" in patched
    assert "from typing import Any" in patched


def test_argument_items_overlay_widens_nested_object_schema() -> None:
    runner = _runner_module()
    source = """from __future__ import annotations

class Argument:
    items: dict[str, str] | None = None
"""

    patched = runner._patch_sweagent_nested_argument_items(source)

    assert "from typing import Any" in patched
    assert "items: dict[str, Any] | None = None" in patched
    assert runner._patch_sweagent_nested_argument_items(patched) == patched


def test_commit_gate_shadows_submit_and_drops_the_builtin_bundle(tmp_path) -> None:
    runner = _runner_module()
    root = Path(__file__).parents[1]
    source_config = root / "benchmark/sweagent/spreadsheet.yaml"
    sweagent_root = root / "benchmark-data/SpreadsheetBench-2/SWE-agent"
    if not source_config.is_file() or not sweagent_root.is_dir():
        pytest.skip("benchmark checkout is not present")

    staged = runner._stage_tool_policy(
        source_config=source_config,
        sweagent_root=sweagent_root,
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="formula-anomalies-v1",
        commit_gate=True,
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))

    bundle_names = [Path(bundle["path"]).name for bundle in config["agent"]["tools"]["bundles"]]
    assert "submit" not in bundle_names, "SWE-agent's ungated submit must not remain registered"
    assert "librecalc" in bundle_names

    librecalc = next(
        Path(bundle["path"])
        for bundle in config["agent"]["tools"]["bundles"]
        if Path(bundle["path"]).name == "librecalc"
    )
    tools = yaml.safe_load((librecalc / "config.yaml").read_text(encoding="utf-8"))["tools"]
    assert "submit" in tools
    assert (librecalc / "bin" / "submit").is_file()
    assert "report" in config["agent"]["templates"]["instance_template"]


def test_commit_gate_off_leaves_the_builtin_submit_alone(tmp_path) -> None:
    runner = _runner_module()
    root = Path(__file__).parents[1]
    source_config = root / "benchmark/sweagent/spreadsheet.yaml"
    sweagent_root = root / "benchmark-data/SpreadsheetBench-2/SWE-agent"
    if not source_config.is_file() or not sweagent_root.is_dir():
        pytest.skip("benchmark checkout is not present")

    staged = runner._stage_tool_policy(
        source_config=source_config,
        sweagent_root=sweagent_root,
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="formula-anomalies-v1",
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))

    assert "submit" in [Path(b["path"]).name for b in config["agent"]["tools"]["bundles"]]


def test_control_arm_stages_the_official_config_untouched(tmp_path) -> None:
    """The control arm answers "does the ISA buy anything" against the shipped baseline.

    Every prompt rewrite in the staging function is written against the LibreCalc instance
    template. If one of them ran here it would either fail to match or quietly import our
    guidance into the baseline, and the arm would stop being the official one.
    """
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    official = yaml.safe_load(
        (
            project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent/config/spreadsheet.yaml"
        ).read_text(encoding="utf-8")
    )

    staged = runner._stage_tool_policy(
        source_config=runner.CONTROL_CONFIG,
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        control=True,
    )

    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    templates = config["agent"]["templates"]

    assert templates["instance_template"] == official["agent"]["templates"]["instance_template"]
    assert templates["system_template"] == official["agent"]["templates"]["system_template"]
    assert config["agent"]["tools"]["enable_bash_tool"] is True
    assert "calc_inspect" not in templates["instance_template"]
    bundles = [Path(item["path"]) for item in config["agent"]["tools"]["bundles"]]
    assert [bundle.name for bundle in bundles] == ["submit", "view_xlsx"]
    assert all(bundle.is_absolute() for bundle in bundles)


def test_control_index_stages_formula_index_without_touching_control_prompt(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    control_cfg = yaml.safe_load(runner.CONTROL_CONFIG.read_text(encoding="utf-8"))

    staged = runner._stage_tool_policy(
        source_config=runner.CONTROL_INDEX_CONFIG,
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        control_index=True,
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundles = [Path(item["path"]) for item in config["agent"]["tools"]["bundles"]]
    assert [bundle.name for bundle in bundles] == ["submit", "view_xlsx", "formula_index"]
    assert (project_root / "benchmark/sweagent/formula_index").resolve() in {
        bundle.resolve() for bundle in bundles
    }
    assert "formula_index" in config["agent"]["templates"]["instance_template"]
    prompt = config["agent"]["templates"]["instance_template"]
    assert "likely" not in prompt.lower()
    assert "complete unranked" not in prompt.lower()
    assert "are not grouped" in prompt
    assert "opaque" in prompt.lower()
    assert config["agent"]["templates"]["max_observation_length"] == 10_000
    assert config["agent"]["tools"]["enable_bash_tool"] is True
    assert (
        control_cfg["agent"]["templates"]["instance_template"]
        != config["agent"]["templates"]["instance_template"]
    )
    assert "formula_index" not in control_cfg["agent"]["templates"]["instance_template"]


def test_control_index_flag_selects_treatment_config(monkeypatch) -> None:
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
            "--control-index",
        ],
    )
    arguments = runner._arguments()
    assert arguments.control_index is True
    assert arguments.control is False
    runner._apply_arm_config(arguments)
    assert arguments.config == runner.CONTROL_INDEX_CONFIG


def test_control_arm_selects_the_control_config_when_none_is_named(monkeypatch) -> None:
    runner = _runner_module()
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_openrouter_slice.py", "--slice", "slice.json", "--run-name", "probe", "--control"],
    )
    arguments = runner._arguments()

    assert arguments.control is True
    assert arguments.config == runner.DEFAULT_CONFIG


def _env_for(runner, monkeypatch, argv: list[str]) -> dict[str, str]:
    """The env block the runner would hand the container, without running a task."""
    monkeypatch.setattr(sys, "argv", ["run_openrouter_slice.py", *argv])
    return runner._arguments()


def test_unbounded_reads_survives_the_anomalies_budget_block(monkeypatch) -> None:
    """The anomalies lane sets the read budget after the flag is read, so order matters.

    The 96-cell ceiling and the one-shot budget are independent ways the interface refuses a
    read. An arm that removes one and not the other measures neither.
    """
    runner = _runner_module()
    source = (Path(__file__).parents[1] / "benchmark/run_openrouter_slice.py").read_text(
        encoding="utf-8"
    )

    unbounded = source.index('if getattr(args, "unbounded_reads", False)')
    anomalies = source.index(
        'env_variables["LIBRECALC_READ_BUDGET_ENABLED"] = "1" if args.read_budget'
    )
    compute = source.index('env_variables["LIBRECALC_INSPECTION_LIMIT"] = "2"')

    assert unbounded > anomalies, "the unbounded arm must win over the anomalies budget"
    assert unbounded > compute, "the unbounded arm must win over the computed budget"

    arguments = _env_for(
        runner,
        monkeypatch,
        ["--slice", "s.json", "--run-name", "probe", "--unbounded-reads"],
    )
    assert arguments.unbounded_reads is True


def test_unbounded_stage_rewrites_prompt_and_native_tool_schema(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="formula-blocks-v1",
        observation="formula-patterns-v1",
        unbounded_reads=True,
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    template = config["agent"]["templates"]["instance_template"]
    bundle = Path(config["agent"]["tools"]["bundles"][0]["path"])
    tools = yaml.safe_load((bundle / "config.yaml").read_text(encoding="utf-8"))["tools"]

    assert "no cell-count ceiling or post-inspect read budget" in template
    assert "reads over 96 cells are rejected" not in template
    assert "no cell-count ceiling" in tools["calc_read"]["docstring"]
    assert "no per-range cell-count ceiling" in tools["calc_read_ranges"]["docstring"]
    ranges_json = next(
        argument
        for argument in tools["calc_read_ranges"]["arguments"]
        if argument["name"] == "ranges_json"
    )
    assert ranges_json["items"]["properties"]["sheet"]["type"] == "string"
    assert ranges_json["items"]["properties"]["range"]["type"] == "string"
    assert ranges_json["items"]["required"] == ["sheet", "range"]
    assert "cell_range is accepted as an alias" in ranges_json["description"]
    formula_blocks = next(
        argument
        for argument in tools["calc_fill_formulas"]["arguments"]
        if argument["name"] == "formula_blocks_json"
    )
    assert formula_blocks["items"]["required"] == ["sheet", "range", "formula"]
    assert formula_blocks["items"]["properties"]["range"]["type"] == "string"
    assert "cell_range is accepted as an alias" in formula_blocks["description"]


def test_slice_model_mismatch_fails_closed() -> None:
    runner = _runner_module()

    runner._validate_slice_model({"model": "example/a"}, "example/a")
    with pytest.raises(ValueError, match="Slice declares model"):
        runner._validate_slice_model({"model": "example/a"}, "example/b")
    runner._validate_slice_model({"model": "example/a"}, "example/b", allow_mismatch=True)


def test_run_contract_records_effective_prompt_tools_environment_and_hash(tmp_path) -> None:
    runner = _runner_module()
    project_root = Path(__file__).parents[1]
    staged = runner._stage_tool_policy(
        source_config=project_root / "benchmark/sweagent/spreadsheet-hybrid.yaml",
        sweagent_root=project_root / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        observation="formula-patterns-v1",
        hybrid=True,
        unbounded_reads=True,
    )
    args = type(
        "Args",
        (),
        {
            "control": False,
            "hybrid": True,
            "model": "example/model",
            "reasoning_effort": "low",
            "observation": "formula-patterns-v1",
            "execution": "semantic-program-v1",
            "read_policy": "progressive",
            "unbounded_reads": True,
            "read_budget": True,
            "compute_read_budget": False,
        },
    )()
    contract = runner._run_contract(
        args=args,
        task_key="Template:01_01",
        staged_config=staged,
        model_preflight={"id": "example/model"},
        completion_kwargs={"provider": {"only": ["example"], "allow_fallbacks": False}},
        env_variables={"LIBRECALC_READ_MAX_CELLS": "none"},
    )

    assert contract["arm"] == "hybrid"
    assert contract["effective_environment"]["LIBRECALC_READ_MAX_CELLS"] == "none"
    assert contract["effective_tool_schema"]["bash_enabled"] is True
    bundle_names = {bundle["name"] for bundle in contract["effective_tool_schema"]["bundles"]}
    assert {"librecalc", "submit", "view_xlsx"} <= bundle_names
    assert contract["prompts"]["system_template"]
    assert len(contract["effective_configuration_sha256"]) == 64
