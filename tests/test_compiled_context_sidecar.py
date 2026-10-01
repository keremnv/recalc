from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "tests"))

from test_openrouter_runner import _runner_module  # noqa: E402

import compiled_context_sidecar_ab as sidecar  # noqa: E402

CONTROL = ROOT / "benchmark/sweagent/spreadsheet-control.yaml"
TREATMENT = ROOT / "benchmark/sweagent/spreadsheet-control-compiled-context.yaml"
SLICE = ROOT / "benchmark/slices/compiled-context-sidecar-ten.json"
CENSUS = ROOT / "benchmark/slices/control-census-sixty.json"


def test_frozen_slice_is_subset_of_census_and_does_not_include_fm20() -> None:
    slice_data = sidecar.load_json(SLICE)
    census = sidecar.load_json(CENSUS)
    census_ids = {(row["category"], row["id"]) for row in census["tasks"]}
    tasks = [(row["category"], row["id"]) for row in slice_data["tasks"]]
    assert tasks[0] == ("Financial_Model", "13_05")
    assert ("Financial_Model", "20_05") not in tasks
    assert "FM20" not in str(slice_data)
    assert all(item in census_ids for item in tasks)
    assert slice_data["model"] == sidecar.MODEL
    assert slice_data["max_tool_calls_per_task"] == 40


def test_c0_c1_prompts_differ_only_by_calc_query_disclosure() -> None:
    c0 = yaml.safe_load(CONTROL.read_text(encoding="utf-8"))
    c1 = yaml.safe_load(TREATMENT.read_text(encoding="utf-8"))
    hashes = sidecar.prompt_hashes()
    assert hashes["c0_system_sha256"] == hashes["c1_system_sha256"]
    assert hashes["c0_instance_sha256"] != hashes["c1_instance_sha256"]
    assert c0["agent"]["templates"]["system_template"] == c1["agent"]["templates"]["system_template"]
    for key in (
        "next_step_template",
        "next_step_no_output_template",
        "next_step_truncated_observation_template",
        "command_cancelled_timeout_template",
        "max_observation_length",
    ):
        assert c0["agent"]["templates"][key] == c1["agent"]["templates"][key]
    assert c0["agent"]["tools"]["enable_bash_tool"] is True
    assert c1["agent"]["tools"]["enable_bash_tool"] is True
    assert c0["agent"]["templates"]["max_observation_length"] == 10_000
    c0_prompt = c0["agent"]["templates"]["instance_template"]
    c1_prompt = c1["agent"]["templates"]["instance_template"]
    assert "calc_query" not in c0_prompt
    assert "calc_query" in c1_prompt
    assert "read-only deterministic structural index" in c1_prompt
    assert "does not decide what should be edited" in c1_prompt
    assert "Prefer `calc_query` for structural workbook questions" in c1_prompt
    lowered = c1_prompt.lower()
    assert "always call it first" not in lowered
    assert "you must use it" not in lowered
    assert "trust it over" not in lowered
    assert "intended edit targets" not in lowered
    assert [item["path"] for item in c0["agent"]["tools"]["bundles"]] == [
        "tools/submit",
        "tools/view_xlsx",
    ]
    assert [item["path"] for item in c1["agent"]["tools"]["bundles"]] == [
        "tools/submit",
        "tools/view_xlsx",
        "../../../benchmark/sweagent/calc_query",
    ]


def test_pair_order_is_predeclared() -> None:
    jobs = sidecar.build_jobs()
    assert len(jobs) == 26
    thirteen = [job for job in jobs if job["task"] == "Financial_Model:13_05"]
    assert [job["arm"] for job in thirteen] == [
        "C0",
        "C1",
        "C1",
        "C0",
        "C0",
        "C1",
        "C1",
        "C0",
    ]
    others = [job for job in jobs if job["task"] != "Financial_Model:13_05"]
    by_task = {}
    for job in others:
        by_task.setdefault(job["task"], []).append(job["arm"])
    generalization = sidecar.GENERALIZATION
    for index, spec in enumerate(generalization):
        key = f"{spec['category']}:{spec['id']}"
        expected = ["C0", "C1"] if index % 2 == 0 else ["C1", "C0"]
        assert by_task[key] == expected
    assert sidecar.MODEL == "meta/muse-spark-1.3-contributor"
    assert sidecar.IDENTITY["reasoning_effort"] is None
    assert sidecar.IDENTITY["temperature"] == 0.0
    assert sidecar.IDENTITY["tool_choice"] == "auto"


def test_control_compiled_context_stages_calc_query_without_rewriting_c0_prompt(tmp_path, monkeypatch) -> None:
    runner = _runner_module()
    monkeypatch.setenv("CALC_QUERY_HOST_CACHE", str(tmp_path / "cache"))
    control_cfg = yaml.safe_load(runner.CONTROL_CONFIG.read_text(encoding="utf-8"))
    staged = runner._stage_tool_policy(
        source_config=runner.CONTROL_COMPILED_CONTEXT_CONFIG,
        sweagent_root=ROOT / "benchmark-data/SpreadsheetBench-2/SWE-agent",
        temporary_root=tmp_path,
        read_policy="progressive",
        execution="semantic-program-v1",
        control_compiled_context=True,
    )
    config = yaml.safe_load(staged.read_text(encoding="utf-8"))
    bundles = [Path(item["path"]) for item in config["agent"]["tools"]["bundles"]]
    assert [bundle.name for bundle in bundles] == ["submit", "view_xlsx", "calc_query"]
    prompt = config["agent"]["templates"]["instance_template"]
    assert "calc_query" in prompt
    assert prompt == yaml.safe_load(TREATMENT.read_text())["agent"]["templates"]["instance_template"]
    assert control_cfg["agent"]["templates"]["instance_template"] != prompt
    docker_args = config["env"]["deployment"]["docker_args"]
    joined = " ".join(docker_args)
    assert "/opt/librecalc/src:ro" in joined
    assert "/opt/librecalc/benchmark:ro" in joined
    assert "/opt/librecalc/calc_query_cache" in joined
    assert "Task IR" not in prompt
    assert "calc_apply" not in prompt


def test_control_compiled_context_flag_selects_treatment_config(monkeypatch) -> None:
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
            "--control-compiled-context",
        ],
    )
    arguments = runner._arguments()
    assert arguments.control_compiled_context is True
    assert arguments.control is False
    runner._apply_arm_config(arguments)
    assert arguments.config == runner.CONTROL_COMPILED_CONTEXT_CONFIG


def test_forced_calc_query_prompt_requires_first_pass_query() -> None:
    forced = yaml.safe_load(
        (ROOT / "benchmark/sweagent/spreadsheet-control-compiled-context-forced.yaml").read_text()
    )
    optional = yaml.safe_load(TREATMENT.read_text())
    prompt = forced["agent"]["templates"]["instance_template"]
    assert prompt != optional["agent"]["templates"]["instance_template"]
    assert "You must call `calc_query` at least once before any workbook modification" in prompt
    assert "Do not implement edits until at least one `calc_query` call has returned" in prompt
    assert "intended edit" not in prompt.lower()
    assert "Task IR" not in prompt
    assert "calc_apply" not in prompt
    assert forced["agent"]["templates"]["system_template"] == optional["agent"]["templates"]["system_template"]
    assert [item["path"] for item in forced["agent"]["tools"]["bundles"]] == [
        "tools/submit",
        "tools/view_xlsx",
        "../../../benchmark/sweagent/calc_query",
    ]


def test_control_compiled_context_forced_flag_selects_forced_config(monkeypatch) -> None:
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
            "--control-compiled-context-forced",
        ],
    )
    arguments = runner._arguments()
    assert arguments.control_compiled_context_forced is True
    assert arguments.control_compiled_context is False
    runner._apply_arm_config(arguments)
    assert arguments.config == runner.CONTROL_COMPILED_CONTEXT_FORCED_CONFIG
    assert runner._arm_name(arguments) == "control-compiled-context-forced"
    source = sidecar.identity_source_contract()
    assert source["model"] == sidecar.MODEL
    assert source["request_model_from_traj"] == f"openrouter/{sidecar.MODEL}"
    assert source["temperature"] == 0.0
    assert source["top_p"] == 1.0
    assert source["reasoning_effort"] is None
    assert source["tool_choice"] == "auto"
    assert source["provider"]["allow_fallbacks"] is True
    assert source["provider"]["require_parameters"] is True


def test_prompt_hash_is_stable() -> None:
    hashes = sidecar.prompt_hashes()
    assert hashes["c0_system_sha256"] == hashlib.sha256(
        yaml.safe_load(CONTROL.read_text())["agent"]["templates"]["system_template"].encode()
    ).hexdigest()
    assert len(hashes["c1_tool_schema_sha256"]) == 64


def test_calc_query_signature_uses_named_placeholders() -> None:
    schema = yaml.safe_load((ROOT / "benchmark/sweagent/calc_query/config.yaml").read_text())
    signature = schema["tools"]["calc_query"]["signature"]
    assert "<a1>" not in signature
    assert "<target>" in signature
    assert "<mode>" in signature
    names = [item["name"] for item in schema["tools"]["calc_query"]["arguments"]]
    assert names == ["mode", "xlsx", "sheet", "target", "text"]


def test_wrapper_crash_is_retryable_infra(tmp_path: Path) -> None:
    traj = tmp_path / "trajectory" / "task.traj"
    traj.parent.mkdir(parents=True)
    traj.write_text('{"observation": "IndexError: 5\\ncalc_query inspect book.xlsx"}', encoding="utf-8")
    assert sidecar.calc_query_wrapper_crash(tmp_path) is True
    other = tmp_path / "clean"
    other.mkdir()
    (other / "x.traj").write_text('{"observation": "status OK"}', encoding="utf-8")
    assert sidecar.calc_query_wrapper_crash(other) is False


def test_response_model_strips_trailing_backslash() -> None:
    assert sidecar.normalize_response_model("meta/muse-spark-1.3-contributor\\") == (
        "meta/muse-spark-1.3-contributor"
    )
    assert sidecar.normalize_response_model("meta/muse-spark-1.3-contributor|openrouter") == (
        "meta/muse-spark-1.3-contributor"
    )
    assert sidecar.normalize_response_model(None) is None


def test_call_cap_is_envelope_not_provider_infra(tmp_path: Path) -> None:
    task_root = tmp_path / "task"
    task_root.mkdir()
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps({"model_calls": 40, "prompt_tokens": 12, "cost_usd": 0.4, "error": "no output workbook"})
        + "\n",
        encoding="utf-8",
    )
    (task_root / "run.log").write_text("Reached maximum of 40 API calls\nBeginning environment shutdown\n")
    assert sidecar.classify_failure(1, task_root) == "envelope_or_resource"
    assert sidecar.opportunity_class(
        {"role": "generalization", "arm": "C1"},
        {},
        {"used": True},
        {"ok": True},
        "envelope_or_resource",
    ) == "ENVELOPE_OR_RESOURCE_CENSORED"


def test_zero_call_crash_remains_provider_infra(tmp_path: Path) -> None:
    task_root = tmp_path / "task"
    task_root.mkdir()
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps({"model_calls": 0, "prompt_tokens": 0}) + "\n",
        encoding="utf-8",
    )
    (task_root / "run.log").write_text("Failed to start container\n")
    assert sidecar.classify_failure(1, task_root) == "provider_or_infra"


def test_calc_query_wrapper_survives_shallow_docker_path() -> None:
    wrapper = (ROOT / "benchmark/sweagent/calc_query/bin/calc_query").read_text()
    assert "Path(__file__).resolve().parents[5]" not in wrapper
    assert "for parent in resolved.parents" in wrapper
    assert 'Path("/opt/librecalc/benchmark")' in wrapper
    # Docker copies the bundle to /root/tools/calc_query/bin/calc_query,
    # which has only 5 parents. The old tuple evaluated parents[5] eagerly.
    resolved = Path("/root/tools/calc_query/bin/calc_query")
    assert len(resolved.parents) == 5
    candidates = [Path("/opt/librecalc/benchmark"), *[parent / "benchmark" for parent in resolved.parents]]
    assert Path("/opt/librecalc/benchmark") in candidates
