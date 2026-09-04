#!/usr/bin/env python3
"""Run an isolated SpreadsheetBench 2 slice with SWE-agent through OpenRouter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_metrics import append_record, generation_ids, generation_metrics, trajectory_metrics

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "benchmark-data" / "SpreadsheetBench-2"


def _load_dotenv(path: Path = DEFAULT_ENV_FILE) -> None:
    """Load KEY=VALUE pairs from ``.env`` without overriding existing env vars."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


DEFAULT_SWEAGENT_ROOT = DEFAULT_BENCHMARK_ROOT / "SWE-agent"
DEFAULT_CONFIG = PROJECT_ROOT / "benchmark" / "sweagent" / "spreadsheet.yaml"
CONTROL_CONFIG = PROJECT_ROOT / "benchmark" / "sweagent" / "spreadsheet-control.yaml"
CONTROL_INDEX_CONFIG = PROJECT_ROOT / "benchmark" / "sweagent" / "spreadsheet-control-index.yaml"
HYBRID_CONFIG = PROJECT_ROOT / "benchmark" / "sweagent" / "spreadsheet-hybrid.yaml"
DEFAULT_MODEL = "moonshotai/kimi-k2.7-code"
SUPPORTED_OBSERVATIONS = (
    "grid-v1",
    "sparse-addressed-v1",
    "structure-first-v1",
    "formula-patterns-v1",
    "formula-anomalies-v1",
    "format-conventions-v1",
    "semantic-snapshot-v1",
    "semantic-snapshot-v2",
)
SUPPORTED_EXECUTIONS = ("semantic-program-v1", "formula-blocks-v1", "cell-writes-v1")
READ_POLICIES = ("progressive", "overview-only", "thin")
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slice", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--sweagent-root", type=Path, default=DEFAULT_SWEAGENT_ROOT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--observation", choices=SUPPORTED_OBSERVATIONS, default="grid-v1")
    parser.add_argument("--execution", choices=SUPPORTED_EXECUTIONS, default="semantic-program-v1")
    parser.add_argument("--read-policy", choices=READ_POLICIES, default="progressive")
    parser.add_argument("--cost-limit", type=float, default=0.03)
    parser.add_argument("--call-limit", type=int, default=10)
    parser.add_argument(
        "--max-requeries",
        type=int,
        default=2,
        help="Maximum attempts for one agent step; two allows one bounded format repair.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help=(
            "Optional fixed response-token cap for a controlled ablation. By default, each "
            "request receives the largest allowance that fits the remaining dollar budget."
        ),
    )
    parser.add_argument("--reasoning-effort", choices=REASONING_EFFORTS)
    parser.add_argument(
        "--unbounded-reads",
        action="store_true",
        help=(
            "Remove the 96-cell read ceiling and the post-inspect read budget. Tests whether "
            "the cheap model is comprehension-bound rather than expression-bound."
        ),
    )
    parser.add_argument(
        "--control",
        action="store_true",
        help=(
            "Run the official bash+openpyxl baseline instead of the LibreCalc tools. "
            "--observation/--execution/--read-policy describe an interface this arm does not "
            "have and are ignored."
        ),
    )
    parser.add_argument(
        "--control-index",
        action="store_true",
        help=(
            "Control harness plus the read-only formula_index tool. Same bash/view_xlsx/submit "
            "surface and observation cap as --control; no LibreCalc tools or read budget."
        ),
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help=(
            "Expose the official bash+view_xlsx surface alongside LibreCalc's semantic tools. "
            "This measures whether the primitives add capability without making the ISA compulsory."
        ),
    )
    parser.add_argument(
        "--allow-model-mismatch",
        action="store_true",
        help=(
            "Allow --model to differ from a slice's declared model. This is an explicit escape "
            "hatch for compiler comparisons; ordinary runs fail closed."
        ),
    )
    parser.add_argument(
        "--commit-gate",
        action="store_true",
        help=(
            "Two-phase submit: the first submit returns world-computed findings and does not "
            "finalise. Measuring instrument; not the 297 default."
        ),
    )
    parser.add_argument(
        "--provider-only",
        action="append",
        help=(
            "Restrict OpenRouter to this provider slug; repeat to allow more than one. "
            "Disables provider fallback."
        ),
    )
    parser.add_argument(
        "--execution-timeout",
        type=int,
        default=180,
        help="Per-tool command timeout in seconds; large semantic comparisons may exceed 60.",
    )
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--blank-bridges",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Attach blank_dependency_bridges on formula-patterns-v1 inspect (default on).",
    )
    parser.add_argument(
        "--read-budget",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "On formula-anomalies-v1 and format-conventions-v1, allow one successful "
            "neighborhood read after inspect then block further reads (default on). "
            "Measuring instrument, not a product primitive."
        ),
    )
    parser.add_argument(
        "--compute-read-budget",
        action="store_true",
        help=(
            "On formula-patterns-v1 (Template/Financial Model), allow two inspects and "
            "one neighborhood read, then block further reads. Write-commit experiment; "
            "not a 297 default."
        ),
    )
    parser.add_argument(
        "--repair-passes",
        type=int,
        choices=(1, 2),
        default=1,
        help=(
            "For formula-anomalies-v1, permit one write/compare pass (default) or one "
            "bounded output re-inspection and final repair pass. Does not raise call limits."
        ),
    )
    parser.add_argument(
        "--preserve-populated",
        action="store_true",
        help=(
            "Skip writes to non-empty cells on write_range, set_formula, and fill_formula. "
            "Template/Financial Model target-safety arm; Debugging groups must not set this."
        ),
    )
    parser.add_argument(
        "--task",
        action="append",
        help="Run only CATEGORY:ID; repeat for multiple tasks. Defaults to the whole slice.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tasks whose run directory already exists (resume a long slice).",
    )
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="Skip the in-run official eval pack. Default is to score after inference.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _task_record(benchmark_root: Path, category: str, task_id: str) -> dict[str, Any]:
    records = _load_json(benchmark_root / "data" / category / "dataset.json")
    matches = [record for record in records if record["id"] == task_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one {category}:{task_id} record, found {len(matches)}")
    return matches[0]


def _selected_tasks(slice_data: dict[str, Any], filters: list[str] | None) -> list[dict[str, str]]:
    tasks = slice_data["tasks"]
    if not filters:
        return tasks
    requested = set(filters)
    selected = [task for task in tasks if f"{task['category']}:{task['id']}" in requested]
    found = {f"{task['category']}:{task['id']}" for task in selected}
    missing = requested - found
    if missing:
        raise ValueError(f"Tasks are not in the slice: {', '.join(sorted(missing))}")
    return selected


def _validate_slice_model(
    slice_data: dict[str, Any], model: str, *, allow_mismatch: bool = False
) -> None:
    declared = slice_data.get("model")
    if declared and declared != model and not allow_mismatch:
        raise ValueError(
            f"Slice declares model {declared!r}, but the run requested {model!r}. "
            "Use --allow-model-mismatch only for an intentional compiler comparison."
        )


def _key_usage(api_key: str) -> float:
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return float(payload["data"]["usage"])


def _openrouter_model(catalog: dict[str, Any], model: str) -> dict[str, Any]:
    matches = [record for record in catalog.get("data", []) if record.get("id") == model]
    if len(matches) != 1:
        raise ValueError(f"OpenRouter model {model!r} was not found in the current catalog")
    record = matches[0]
    supported_parameters = record.get("supported_parameters") or []
    missing = {"max_tokens", "tools"} - set(supported_parameters)
    if missing:
        raise ValueError(f"OpenRouter model {model!r} lacks required parameters: {sorted(missing)}")
    return record


def _maximum_token_price(model_record: dict[str, Any], key: str) -> float:
    pricing = model_record.get("pricing") or {}
    candidates = [pricing.get(key)]
    candidates.extend(override.get(key) for override in pricing.get("overrides", []))
    values = [float(value) for value in candidates if value is not None]
    if not values or min(values) < 0:
        raise ValueError(f"OpenRouter model has invalid {key!r} pricing: {candidates}")
    return max(values)


def _model_preflight(model: str) -> dict[str, Any]:
    request = urllib.request.Request(OPENROUTER_MODELS_URL)
    with urllib.request.urlopen(request, timeout=30) as response:
        catalog = json.load(response)
    record = _openrouter_model(catalog, model)
    return {
        "id": record["id"],
        "name": record.get("name"),
        "context_length": record.get("context_length"),
        "supported_parameters": record.get("supported_parameters"),
        "reasoning": record.get("reasoning"),
        "catalog_prompt_price_per_token": float(record["pricing"]["prompt"]),
        "catalog_completion_price_per_token": float(record["pricing"]["completion"]),
        "safety_prompt_price_per_token": _maximum_token_price(record, "prompt"),
        "safety_completion_price_per_token": _maximum_token_price(record, "completion"),
    }


def _validate_reasoning_effort(model: dict[str, Any], effort: str | None) -> None:
    if effort is None:
        return
    if "reasoning" not in (model.get("supported_parameters") or []):
        raise ValueError(f"OpenRouter model {model['id']!r} does not expose reasoning controls")
    reasoning = model.get("reasoning") or {}
    if effort == "none" and reasoning.get("mandatory"):
        raise ValueError(f"OpenRouter model {model['id']!r} requires reasoning")
    supported_efforts = reasoning.get("supported_efforts")
    if effort != "none" and supported_efforts and effort not in supported_efforts:
        raise ValueError(
            f"OpenRouter model {model['id']!r} supports reasoning efforts {supported_efforts}, "
            f"not {effort!r}"
        )


def _tool_choice(model: dict[str, Any]) -> str:
    # These advertise tools but reject tool_choice=required ("only auto is supported" /
    # "Tool choice must be auto"). SWE-agent still requires one tool per turn in the prompt.
    model_id = str(model.get("id") or "")
    if "muse-spark-1.2" in model_id or "glm-5.3" in model_id:
        return "auto"
    return "required"


def _completion_kwargs(args: argparse.Namespace, model: dict[str, Any]) -> dict[str, Any]:
    provider_only = getattr(args, "provider_only", None)
    tool_choice = _tool_choice(model)
    if (
        args.reasoning_effort not in {None, "none"}
        and provider_only
        and any(provider.casefold() == "moonshotai" for provider in provider_only)
    ):
        # Moonshot's native endpoint rejects `tool_choice=required` when thinking is enabled.
        # The strict SWE-agent prompt still requires exactly one tool call per turn.
        tool_choice = "auto"
    kwargs: dict[str, Any] = {
        "input_cost_per_token": model["safety_prompt_price_per_token"],
        "output_cost_per_token": model["safety_completion_price_per_token"],
        # Every SWE-agent turn must execute exactly one tool. Enforce the first half of that
        # contract at the provider boundary instead of paying for a no-tool repair response.
        "tool_choice": tool_choice,
    }
    if args.max_tokens is None:
        # This private flag is consumed by the staged SWE-agent overlay before LiteLLM is called.
        # It is never forwarded to OpenRouter.
        kwargs["librecalc_budget_max_tokens"] = True
    else:
        kwargs["max_tokens"] = args.max_tokens
    # The model catalog is an aggregate across endpoints. A pinned endpoint can support tools and
    # tool_choice without supporting parallel_tool_calls (both current Moonshot K2.7 endpoints do).
    # Do not forward aggregate-only controls to a provider-pinned endpoint. tool_choice still
    # enforces the one-tool side of the loop contract where the endpoint supports `required`.
    if not provider_only and "parallel_tool_calls" in (model.get("supported_parameters") or []):
        kwargs["parallel_tool_calls"] = False
    if args.reasoning_effort:
        kwargs["reasoning"] = {"effort": args.reasoning_effort}
    if provider_only:
        kwargs["provider"] = {
            "only": provider_only,
            "allow_fallbacks": False,
        }
    return kwargs


def _patch_sweagent_call_boundary(source: str) -> str:
    """Move SWE-agent's call-limit check before the next paid query."""
    needle = """    def query(self, history: History, n: int = 1, temperature: float | None = None) -> list[dict] | dict:
        messages = self._history_to_messages(history)
"""
    replacement = """    def query(self, history: History, n: int = 1, temperature: float | None = None) -> list[dict] | dict:
        if 0 < self.config.per_instance_call_limit <= self.stats.api_calls:
            self.logger.warning(
                f\"API calls {self.stats.api_calls} reached limit {self.config.per_instance_call_limit}\"
            )
            msg = \"Per instance call limit reached before query\"
            raise InstanceCallLimitExceededError(msg)
        messages = self._history_to_messages(history)
"""
    if replacement in source:
        return source
    if source.count(needle) != 1:
        raise RuntimeError("Unsupported SWE-agent models.py: LiteLLM query boundary was not found")
    return source.replace(needle, replacement)


def _patch_sweagent_budget_boundary(source: str) -> str:
    """Derive a safe response allowance and reserve its cost before a paid query."""
    needle = """        if self.model_max_input_tokens is None:
"""
    replacement = """        if not hasattr(self, "_librecalc_budget_max_tokens"):
            self._librecalc_budget_max_tokens = bool(
                self.config.completion_kwargs.pop("librecalc_budget_max_tokens", False)
            )
        safety_input_price = float(self.config.completion_kwargs.get("input_cost_per_token", 0))
        safety_output_price = float(self.config.completion_kwargs.get("output_cost_per_token", 0))
        # Provider prompt accounting can exceed LiteLLM's local counter because native tool
        # schemas are represented differently. Reserve a 50% prompt-token margin.
        safety_input_cost = input_tokens * 1.5 * safety_input_price
        remaining_limits = []
        if 0 < self.config.per_instance_cost_limit:
            remaining_limits.append(self.config.per_instance_cost_limit - self.stats.instance_cost)
        if 0 < self.config.total_cost_limit:
            remaining_limits.append(self.config.total_cost_limit - GLOBAL_STATS.total_cost)
        remaining_cost = min(remaining_limits) if remaining_limits else float("inf")
        if self._librecalc_budget_max_tokens:
            if safety_output_price <= 0:
                # A free completion needs no dollar-derived response ceiling. Let the provider's
                # context/default output policy apply instead of inventing an arbitrary cap.
                self.config.completion_kwargs.pop("max_tokens", None)
                safety_max_output = 0
            elif remaining_cost == float("inf"):
                msg = "Automatic response allowance requires a cost limit for a priced model"
                raise ModelConfigurationError(msg)
            else:
                affordable_output = int((remaining_cost - safety_input_cost) / safety_output_price)
                # Dollar room is not a legal OpenRouter max_tokens. Unknown model output/context
                # limits used to copy affordable_output (hundreds of thousands of tokens) and the
                # provider rejected the request. Cap missing limits at a thought-sized 8,192.
                model_output_limit = int(self.model_max_output_tokens or 8192)
                # Catalogs that advertise the whole context as max output are not a usable
                # completion ceiling. OpenRouter counts max_tokens into the context window, so
                # requesting ~context-minus-local-input overflows once tool schemas are counted.
                if self.model_max_input_tokens and model_output_limit >= int(self.model_max_input_tokens):
                    model_output_limit = 8192
                counted_input = int(input_tokens * 1.5)
                if self.model_max_input_tokens:
                    context_output_limit = int(max(0, self.model_max_input_tokens - counted_input))
                else:
                    context_output_limit = 8192
                safety_max_output = min(affordable_output, model_output_limit, context_output_limit)
                if safety_max_output < 1:
                    msg = "No response tokens fit within the remaining cost/context budget"
                    self.logger.warning(msg)
                    raise InstanceCostLimitExceededError(msg)
                self.config.completion_kwargs["max_tokens"] = safety_max_output
        else:
            safety_max_output = int(
                self.config.completion_kwargs.get("max_tokens", self.model_max_output_tokens or 0)
            )
        # Reserve the full dynamically affordable or explicitly configured response before
        # issuing a request, so the advertised dollar budget remains a hard cap.
        estimated_next_cost = safety_input_cost + safety_max_output * safety_output_price
        if (
            0 < self.config.per_instance_cost_limit
            and self.stats.instance_cost + estimated_next_cost > self.config.per_instance_cost_limit
        ):
            msg = "Projected next response exceeds per-instance cost limit before query"
            self.logger.warning(msg)
            raise InstanceCostLimitExceededError(msg)
        if (
            0 < self.config.total_cost_limit
            and GLOBAL_STATS.total_cost + estimated_next_cost > self.config.total_cost_limit
        ):
            msg = "Projected next response exceeds total cost limit before query"
            self.logger.warning(msg)
            raise TotalCostLimitExceededError(msg)

        if self.model_max_input_tokens is None:
"""
    if replacement in source:
        return source
    if source.count(needle) != 1:
        raise RuntimeError("Unsupported SWE-agent models.py: token-count boundary was not found")
    return source.replace(needle, replacement)


def _patch_sweagent_empty_assistant(source: str) -> str:
    """Keep an empty assistant turn from poisoning the whole conversation.

    A cheap compiler that format-exits emits an assistant message with no content. Some
    provider-pinned endpoints (Moonshot K2.7) reject *every* later request whose history
    contains one, so a single empty completion ends the trajectory instead of costing one
    requery. Substitute a placeholder for content-free assistant turns that carry no tool
    call; turns that do carry one are legitimately empty and are left alone.
    """
    needle = """        messages = self._history_to_messages(history)
"""
    replacement = """        messages = self._history_to_messages(history)
        for _message in messages:
            if _message.get("role") != "assistant":
                continue
            if _message.get("tool_calls") or _message.get("function_call"):
                continue
            _content = _message.get("content")
            if _content is None or (isinstance(_content, str) and not _content.strip()):
                _message["content"] = "(no content returned)"
"""
    if replacement in source:
        return source
    if source.count(needle) != 1:
        raise RuntimeError(
            "Unsupported SWE-agent models.py: history-to-messages boundary was not found"
        )
    return source.replace(needle, replacement)


def _patch_sweagent_bad_request_retry(source: str) -> str:
    """Stop retrying a deterministically invalid request.

    A 400 is a property of the message history, not of the network, so tenacity replays the
    same rejected request up to twenty times with exponential backoff and burns the task
    timeout. Fail immediately instead and let the run harvest whatever exists.
    """
    needle = """                    litellm.exceptions.UnsupportedParamsError,
"""
    replacement = """                    litellm.exceptions.BadRequestError,
                    litellm.exceptions.UnsupportedParamsError,
"""
    if replacement in source:
        return source
    if source.count(needle) != 1:
        raise RuntimeError("Unsupported SWE-agent models.py: retry exclusion tuple was not found")
    return source.replace(needle, replacement)


def _patch_sweagent_nested_argument_items(source: str) -> str:
    """Allow batched object schemas to declare required keys.

    Upstream Argument.items is dict[str, str], so LibreCalc could only advertise
    ``{type: object}``. Models then copied calc_read's ``cell_range`` into the
    untyped item and the validator rejected a semantically valid batch.
    """

    field_needle = "    items: dict[str, str] | None = None"
    field_replacement = "    items: dict[str, Any] | None = None"
    if field_needle in source:
        if source.count(field_needle) != 1:
            raise RuntimeError(
                "Unsupported SWE-agent commands.py: Argument.items was not found exactly once"
            )
        source = source.replace(field_needle, field_replacement)
    elif field_replacement not in source:
        raise RuntimeError("Unsupported SWE-agent commands.py: Argument.items was not found")

    typing_import = "from typing import Any\n"
    if typing_import in source:
        return source
    marker = "from __future__ import annotations\n\n"
    if source.count(marker) != 1:
        raise RuntimeError("Unsupported SWE-agent commands.py: typing import site was not found")
    return source.replace(marker, marker + typing_import, 1)


def _stage_sweagent_overlay(sweagent_root: Path, temporary_root: Path) -> Path:
    overlay_root = temporary_root / "sweagent-overlay"
    package_root = overlay_root / "sweagent"
    shutil.copytree(sweagent_root / "sweagent", package_root)
    models_path = package_root / "agent" / "models.py"
    model_source = models_path.read_text(encoding="utf-8")
    model_source = _patch_sweagent_call_boundary(model_source)
    model_source = _patch_sweagent_budget_boundary(model_source)
    model_source = _patch_sweagent_empty_assistant(model_source)
    model_source = _patch_sweagent_bad_request_retry(model_source)
    models_path.write_text(model_source, encoding="utf-8")
    commands_path = package_root / "tools" / "commands.py"
    commands_path.write_text(
        _patch_sweagent_nested_argument_items(commands_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return overlay_root


def _replace_workflow_step(template: str, number: int, replacement: str) -> str:
    """Replace one numbered workflow step without depending on treatment-specific wording."""

    start_marker = f"\n{number}. "
    end_marker = f"\n{number + 1}. "
    if template.count(start_marker) != 1 or template.count(end_marker) != 1:
        raise RuntimeError(f"Could not locate workflow step {number} exactly once")
    start = template.index(start_marker) + 1
    end = template.index(end_marker)
    return f"{template[:start]}{number}. {replacement}{template[end:]}"


def _make_read_tools_unbounded(tool_config: dict[str, Any]) -> None:
    """Make the staged function schema tell the truth about the unbounded treatment."""

    tools = tool_config.get("tools", {})
    read = tools.get("calc_read")
    read_ranges = tools.get("calc_read_ranges")
    if read is not None:
        read["docstring"] = (
            "Read one addressed rectangular range through LibreOffice Calc. There is no "
            "cell-count ceiling in this run; full relevant blocks are allowed."
        )
        for argument in read.get("arguments", []):
            if argument.get("name") == "cell_range":
                argument["description"] = (
                    "Any exact A1 range needed for the task, from a small neighborhood to a "
                    "full relevant block."
                )
    if read_ranges is not None:
        read_ranges["docstring"] = (
            "Read several addressed ranges in one workbook pass. There is no per-range "
            "cell-count ceiling in this run; batch every relevant block you need."
        )
        for argument in read_ranges.get("arguments", []):
            if argument.get("name") == "ranges_json":
                argument["description"] = (
                    "Array of {sheet, range} objects. Each item requires keys sheet and range; "
                    "cell_range is accepted as an alias for range. Ranges may cover full "
                    "relevant blocks; there is no 96-cell ceiling in this run."
                )


def _make_read_tools_bounded(tool_config: dict[str, Any]) -> None:
    """Describe the historical 96-cell treatment when the runner enables it."""

    tools = tool_config.get("tools", {})
    read = tools.get("calc_read")
    read_ranges = tools.get("calc_read_ranges")
    if read is not None:
        read["docstring"] = (
            "Read one small rectangular neighborhood through LibreOffice Calc. Ranges are "
            "limited to 96 cells; whole sheets and used-range dumps are rejected."
        )
        for argument in read.get("arguments", []):
            if argument.get("name") == "cell_range":
                argument["description"] = (
                    "A1 neighborhood of at most 96 cells, for example D35:O42. Whole sheets "
                    "are rejected."
                )
    if read_ranges is not None:
        read_ranges["docstring"] = (
            "Read several small addressed neighborhoods in one workbook pass. Each range is "
            "limited to 96 cells; used-range dumps are rejected."
        )
        for argument in read_ranges.get("arguments", []):
            if argument.get("name") == "ranges_json":
                argument["description"] = (
                    "Array of {sheet, range} objects. Each item requires keys sheet and range; "
                    "cell_range is accepted as an alias for range. Each range is limited to "
                    "96 cells in this treatment."
                )


def _stage_tool_policy(
    *,
    source_config: Path,
    sweagent_root: Path,
    temporary_root: Path,
    read_policy: str,
    execution: str,
    execution_timeout: int | None = None,
    observation: str = "grid-v1",
    repair_passes: int = 1,
    compute_read_budget: bool = False,
    commit_gate: bool = False,
    control: bool = False,
    control_index: bool = False,
    unbounded_reads: bool = False,
    hybrid: bool = False,
) -> Path:
    config = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    if execution_timeout is not None:
        config["agent"]["tools"]["execution_timeout"] = execution_timeout
    bundle_configs = config["agent"]["tools"]["bundles"]
    for bundle_config in bundle_configs:
        bundle_path = Path(bundle_config["path"])
        if not bundle_path.is_absolute():
            bundle_path = (sweagent_root / bundle_path).resolve()
        bundle_config["path"] = str(bundle_path)
    if control or control_index:
        # Official-surface arms: absolutize bundle paths only. Do not rewrite the prompt.
        staged = temporary_root / source_config.name
        staged.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        return staged

    instance_template = config["agent"]["templates"]["instance_template"]

    if not control:
        bundle_source = Path(bundle_configs[0]["path"])
        # Bundle upload paths are derived from the directory basename. Keep the stable runtime
        # name expected by LIBRECALC_TOOL_ROOT and the bundle's install script.
        staged_bundle = temporary_root / "bundles" / "librecalc"
        staged_bundle.parent.mkdir(parents=True)
        shutil.copytree(bundle_source, staged_bundle)

        tool_config_path = staged_bundle / "config.yaml"
        tool_config = yaml.safe_load(tool_config_path.read_text(encoding="utf-8"))
        if read_policy == "overview-only":
            for tool_name in ("calc_read", "calc_read_ranges"):
                removed = tool_config["tools"].pop(tool_name, None)
                if removed is None:
                    raise RuntimeError(f"Overview-only policy expected a {tool_name} tool")
        if read_policy == "thin":
            # Interface A keeps one raw read per call: no batched reads, no semantic diff.
            for tool_name in ("calc_read_ranges", "calc_compare"):
                removed = tool_config["tools"].pop(tool_name, None)
                if removed is None:
                    raise RuntimeError(f"Thin policy expected a {tool_name} tool")
        if execution == "formula-blocks-v1":
            for tool_name in (
                "calc_write",
                "calc_program",
                "calc_inspect_charts",
                "calc_upsert_chart",
            ):
                removed = tool_config["tools"].pop(tool_name, None)
                if removed is None:
                    raise RuntimeError(f"Formula-block policy expected a {tool_name} tool")
        if execution == "cell-writes-v1":
            # Interfaces A and B: calc_write is the only write surface. One range per call,
            # every formula enumerated explicitly, no relative translation, no batching.
            for tool_name in (
                "calc_fill_formulas",
                "calc_program",
                "calc_inspect_charts",
                "calc_upsert_chart",
            ):
                removed = tool_config["tools"].pop(tool_name, None)
                if removed is None:
                    raise RuntimeError(f"Cell-write policy expected a {tool_name} tool")
        if commit_gate:
            # Shadow SWE-agent's submit. Its bundle is dropped below so only this one is
            # registered; otherwise the agent keeps an ungated path to finalising.
            tool_config["tools"]["submit"] = {
                "signature": "submit",
                "docstring": (
                    "Submit the output workbook. The first submit returns a report of facts "
                    "about your output that the input did not have; fix them or submit again "
                    "to finalise."
                ),
                "arguments": [],
            }
        if unbounded_reads or read_policy == "thin":
            _make_read_tools_unbounded(tool_config)
        else:
            _make_read_tools_bounded(tool_config)
        tool_config_path.write_text(yaml.safe_dump(tool_config, sort_keys=False), encoding="utf-8")
        bundle_configs[0]["path"] = str(staged_bundle)

    if commit_gate:
        remaining = [
            bundle_config
            for bundle_config in bundle_configs
            if Path(bundle_config["path"]).name != "submit"
        ]
        if len(remaining) == len(bundle_configs):
            raise RuntimeError("Commit gate expected SWE-agent's submit bundle to be present")
        config["agent"]["tools"]["bundles"] = remaining

    if read_policy == "overview-only" and not hybrid:
        old_read_guidance = """2. Do not reread a whole used range. Use calc_read for one focused region or calc_read_ranges
   for several.
   Treat inferred candidate_gaps as a heuristic checklist, not requirements; ignore obvious
   section headers and notes. formula-patterns-v1 inspect may also list
   boundary_continuations: one-cell date-run extensions of an existing formula.
   Include those cells in the same calc_fill_formulas as the named work unless the
   instruction excludes that continuation."""
        new_read_guidance = """2. Treat inferred candidate_gaps as a heuristic checklist, not requirements; ignore obvious
   section headers and notes. The semantic overview is the complete read surface for this run;
   focused range reads are intentionally unavailable."""
        if old_read_guidance not in instance_template:
            raise RuntimeError("Overview-only policy could not locate the progressive-read prompt")
        config["agent"]["templates"]["instance_template"] = instance_template.replace(
            old_read_guidance,
            new_read_guidance,
        )
        instance_template = config["agent"]["templates"]["instance_template"]

    if observation == "formula-anomalies-v1" and read_policy == "progressive" and not hybrid:
        old_inspect_guidance = """1. Call calc_inspect without target sheets for the compact workbook manifest. Then call it once
   with the exact manifest names of only the worksheets required by the instruction."""
        new_inspect_guidance = """1. Call calc_inspect once. This anomaly variant is already a compact workbook-wide shortlist;
   target-sheet scoping is unnecessary."""
        if old_inspect_guidance not in instance_template:
            raise RuntimeError("Anomaly policy could not locate the scoped-inspect prompt")
        instance_template = instance_template.replace(
            old_inspect_guidance,
            new_inspect_guidance,
        )
        old_anomaly_guidance = """2. Do not reread a whole used range. Use calc_read for one focused region or calc_read_ranges
   for several.
   Treat inferred candidate_gaps as a heuristic checklist, not requirements; ignore obvious
   section headers and notes. formula-patterns-v1 inspect may also list
   boundary_continuations: one-cell date-run extensions of an existing formula.
   Include those cells in the same calc_fill_formulas as the named work unless the
   instruction excludes that continuation."""
        if repair_passes == 1:
            new_anomaly_guidance = """2. Inspect includes ranked translation/sequence candidates and a compact formula-error
   representative list. Both are heuristics, not requirements. At most one confirmation pass:
   one calc_read_ranges call covering small neighborhoods around the cells you intend to change,
   a few surrounding rows or columns (reads over 96 cells are rejected). Never read a whole sheet,
   used range, or extra sheets after that. Then write."""
        else:
            new_anomaly_guidance = """2. Inspect includes ranked translation/sequence candidates and a compact formula-error
   representative list. Both are heuristics, not requirements. For the first repair pass, use at
   most one calc_read_ranges call covering small neighborhoods around cells you intend to change
   (each range is capped at 96 cells), then write. Never read a whole sheet or used range."""
        if execution == "semantic-program-v1":
            new_anomaly_guidance += """
   Inspect may include deleted_row_geometry, a heuristic that a row was deleted (a #REF! remnant,
   sometimes with a duplicate adjacent label). If that matches the instruction, do not dump that
   sheet to confirm the remnant. Restore structure with calc_program insert_row at insert_row_index
   before rewriting dependent formulas."""
        if old_anomaly_guidance not in instance_template:
            raise RuntimeError(
                "Anomaly shortlist policy could not locate the progressive-read prompt"
            )
        instance_template = instance_template.replace(old_anomaly_guidance, new_anomaly_guidance)
        old_verify_guidance = """5. Compare input and output with calc_compare. Check that exact changes match the instruction;
   candidate gaps remain heuristic. Use focused reads only for a real unresolved ambiguity,
   then submit."""
        if repair_passes == 1:
            new_verify_guidance = """5. Compare input and output with calc_compare, then submit. Do not start another inspection
   loop after the write."""
        else:
            new_verify_guidance = """5. Compare input and output with calc_compare. Then call calc_inspect once on the output
   workbook to surface remaining anomalies. If a final repair is needed, use at most one focused
   calc_read_ranges call, write to that same output path, and compare once more. Then submit; never
   begin a third inspection or repair pass."""
        if old_verify_guidance not in instance_template:
            raise RuntimeError("Anomaly shortlist policy could not locate the verify prompt")
        instance_template = instance_template.replace(old_verify_guidance, new_verify_guidance)
        config["agent"]["templates"]["instance_template"] = instance_template
        system_template = config["agent"]["templates"]["system_template"]
        if execution == "formula-blocks-v1":
            write_hint = (
                "\nAfter inspect, confirm the shortlist once if needed, then calc_fill_formulas.\n"
            )
        else:
            write_hint = (
                "\nAfter inspect, confirm the shortlist once if needed, then write. "
                "Use calc_program for mixed operations including insert_row/delete_row; "
                "use calc_fill_formulas for formula-only patterned ranges. "
                "If inspect listed deleted_row_geometry that matches the instruction, "
                "insert_row is the write; do not spend the confirmation read on that sheet. "
                "After the first save, further writes must use the output path as source; "
                "restarting from the input wipes the restore. "
                "If a read is rejected as too large, write from inspect; do not retry dumps "
                "or bash.\n"
            )
        if repair_passes == 2:
            write_hint += (
                "After the first compare, inspect the output once and make at most one final "
                "repair before submitting.\n"
            )
        config["agent"]["templates"]["system_template"] = system_template.rstrip() + write_hint

    if observation == "format-conventions-v1" and read_policy == "progressive" and not hybrid:
        if execution != "semantic-program-v1":
            raise ValueError("format-conventions-v1 requires semantic-program-v1 execution")
        replacements = (
            (
                """1. Call calc_inspect without target sheets for the compact workbook manifest. Then call it once
   with the exact manifest names of only the worksheets required by the instruction.""",
                """1. Call calc_inspect once. This format variant is already a compact workbook-wide
   font-color census; target-sheet scoping is unnecessary.""",
            ),
            (
                """2. Do not reread a whole used range. Use calc_read for one focused region or calc_read_ranges
   for several.
   Treat inferred candidate_gaps as a heuristic checklist, not requirements; ignore obvious
   section headers and notes. formula-patterns-v1 inspect may also list
   boundary_continuations: one-cell date-run extensions of an existing formula.
   Include those cells in the same calc_fill_formulas as the named work unless the
   instruction excludes that continuation.""",
                """2. Inspect reports mixed font-color convention groups and bounded minority-color ranges.
   These are heuristics, not requirements. Use at most one calc_read_ranges call covering small
   neighborhoods around ranges you intend to change (each range is capped at 96 cells).""",
            ),
            (
                """3. Infer only the missing or incorrect formulas/values required by the instruction.""",
                """3. Infer only the inconsistent font colors required by the instruction. Preserve cell
   values, formulas, and every unrelated format property.""",
            ),
            (
                """4. Write the result to the exact output path. Use calc_fill_formulas for formula-only work;
   use calc_program for mixed operations. Keep patterned edits range-based.""",
                """4. Write with one calc_program call using range-based set_format operations containing
   only font_color. Do not rewrite cell values or formulas to simulate formatting.""",
            ),
            (
                """5. Compare input and output with calc_compare. Check that exact changes match the instruction;
   candidate gaps remain heuristic. Use focused reads only for a real unresolved ambiguity,
   then submit.""",
                """5. Compare input and output with calc_compare. It reports font-color changes as ranges
   on the same bounded census. If colors are still wrong, make at most one additional set_format
   on the same output path, then submit. Do not rewrite values or formulas.""",
            ),
        )
        for old, new in replacements:
            if old not in instance_template:
                raise RuntimeError("Format-convention policy could not locate its base prompt")
            instance_template = instance_template.replace(old, new)
        config["agent"]["templates"]["instance_template"] = instance_template
        system_template = config["agent"]["templates"]["system_template"]
        config["agent"]["templates"]["system_template"] = (
            system_template.rstrip()
            + "\nInspect the font-color convention census, confirm only real outliers, then use "
            "calc_program set_format operations.\n"
        )

    if execution == "cell-writes-v1" and not hybrid:
        old_write_guidance = """4. Write the result to the exact output path. Use calc_fill_formulas for formula-only work;
   use calc_program for mixed operations. Keep patterned edits range-based."""
        new_write_guidance = """4. Write the result to the exact output path with calc_write. Each call writes one
   rectangular range, and every cell must be given explicitly: a value, or a formula string
   beginning with '=' spelled out for that exact cell. Relative fill and multi-operation
   batching are unavailable in this run."""
        if old_write_guidance not in instance_template:
            raise RuntimeError("Cell-write policy could not locate the mixed-operation prompt")
        instance_template = instance_template.replace(old_write_guidance, new_write_guidance)
        config["agent"]["templates"]["instance_template"] = instance_template
        system_template = config["agent"]["templates"]["system_template"]
        system_template = system_template.replace(
            "Prefer calc_program for related edits\nso the workbook is recalculated and saved once. "
            "For formula-only completion, prefer\ncalc_fill_formulas with one block per patterned "
            "range; never enumerate translated cells.\n",
            "Write with calc_write, one rectangular range per call, enumerating every cell.\n",
        )
        config["agent"]["templates"]["system_template"] = system_template

    if read_policy == "thin" and not hybrid:
        old_inspect_guidance = """1. Call calc_inspect without target sheets for the compact workbook manifest. Then call it once
   with the exact manifest names of only the worksheets required by the instruction."""
        new_inspect_guidance = """1. Call calc_inspect for the workbook structure."""
        if old_inspect_guidance not in instance_template:
            raise RuntimeError("Thin policy could not locate the scoped-inspect prompt")
        instance_template = instance_template.replace(old_inspect_guidance, new_inspect_guidance)
        old_read_guidance = """2. Do not reread a whole used range. Use calc_read for one focused region or calc_read_ranges
   for several.
   Treat inferred candidate_gaps as a heuristic checklist, not requirements; ignore obvious
   section headers and notes. formula-patterns-v1 inspect may also list
   boundary_continuations: one-cell date-run extensions of an existing formula.
   Include those cells in the same calc_fill_formulas as the named work unless the
   instruction excludes that continuation."""
        new_read_guidance = """2. Use calc_read for one region at a time. Batched reads are unavailable in this run."""
        if old_read_guidance not in instance_template:
            raise RuntimeError("Thin policy could not locate the progressive-read prompt")
        instance_template = instance_template.replace(old_read_guidance, new_read_guidance)
        old_verify_guidance = """5. Compare input and output with calc_compare. Check that exact changes match the instruction;
   candidate gaps remain heuristic. Use focused reads only for a real unresolved ambiguity,
   then submit."""
        new_verify_guidance = """5. Verify with calc_read against the output path if needed, then submit.
   Semantic comparison is unavailable in this run."""
        if old_verify_guidance not in instance_template:
            raise RuntimeError("Thin policy could not locate the verify prompt")
        instance_template = instance_template.replace(old_verify_guidance, new_verify_guidance)
        config["agent"]["templates"]["instance_template"] = instance_template
        system_template = config["agent"]["templates"]["system_template"]
        config["agent"]["templates"]["system_template"] = system_template.replace(
            "When two or more focused regions are needed, use one calc_read_ranges call.\n", ""
        )

    if execution == "formula-blocks-v1" and not hybrid:
        old_write_guidance = """4. Write the result to the exact output path. Use calc_fill_formulas for formula-only work;
   use calc_program for mixed operations. Keep patterned edits range-based."""
        new_write_guidance = """4. Write the result with one calc_fill_formulas call. Use one block per patterned range;
   cell-by-cell formula enumeration is unavailable in this run."""
        if old_write_guidance not in instance_template:
            raise RuntimeError("Formula-block policy could not locate the mixed-operation prompt")
        config["agent"]["templates"]["instance_template"] = instance_template.replace(
            old_write_guidance,
            new_write_guidance,
        )
        system_template = config["agent"]["templates"]["system_template"]
        config["agent"]["templates"]["system_template"] = system_template.replace(
            "Prefer calc_program for related edits\nso the workbook is recalculated and saved once. ",
            "",
        )
    instance_template = config["agent"]["templates"]["instance_template"]
    if (
        observation == "formula-patterns-v1"
        and compute_read_budget
        and read_policy == "progressive"
        and not hybrid
    ):
        old_read_guidance = """2. Do not reread a whole used range. Use calc_read for one focused region or calc_read_ranges
   for several.
   Treat inferred candidate_gaps as a heuristic checklist, not requirements; ignore obvious
   section headers and notes. formula-patterns-v1 inspect may also list
   boundary_continuations: one-cell date-run extensions of an existing formula.
   Include those cells in the same calc_fill_formulas as the named work unless the
   instruction excludes that continuation."""
        new_read_guidance = """2. After the two inspects, at most one calc_read_ranges batch of neighborhoods
   (each range capped at 96 cells). Then write. If a read is rejected as too large,
   write from inspect with calc_fill_formulas; do not retry dumps or bash.
   Treat inferred candidate_gaps as a heuristic checklist, not requirements.
   Include boundary_continuations in the same fill unless the instruction excludes them."""
        if old_read_guidance not in instance_template:
            raise RuntimeError(
                "Compute read-budget policy could not locate the progressive-read prompt"
            )
        instance_template = instance_template.replace(old_read_guidance, new_read_guidance)
        config["agent"]["templates"]["instance_template"] = instance_template
        system_template = config["agent"]["templates"]["system_template"]
        config["agent"]["templates"]["system_template"] = (
            system_template.rstrip()
            + "\nAfter inspect, at most one neighborhood read, then write. "
            "If a read is rejected as too large, write from inspect; do not dump or bash.\n"
        )
    if unbounded_reads:
        instance_template = config["agent"]["templates"]["instance_template"]
        config["agent"]["templates"]["instance_template"] = _replace_workflow_step(
            instance_template,
            2,
            (
                "Read every exact workbook region needed to resolve the task. This arm has no "
                "cell-count ceiling or post-inspect read budget: calc_read can return a full "
                "relevant block, and calc_read_ranges can batch several blocks. Prefer addressed "
                "ranges over irrelevant sheets, but do not narrow a read merely to satisfy an "
                "interface limit. Treat any inferred candidates as heuristics, not requirements."
            ),
        )
        system_template = config["agent"]["templates"]["system_template"]
        config["agent"]["templates"]["system_template"] = (
            system_template.rstrip()
            + "\nReads are unbounded in this run. Request every addressed workbook block needed "
            "to decide the correct edit.\n"
        )
    if commit_gate:
        # Last, so the earlier read-policy and execution rewrites cannot clobber it.
        config["agent"]["templates"]["instance_template"] = config["agent"]["templates"][
            "instance_template"
        ].rstrip() + (
            "\n\nWhen you submit, the world reports facts about your output that the input did "
            "not have: cells that now hold a formula error, cells that break a formula run the "
            "input carried across a row, and the workbook's own check cells that no longer "
            "balance. Read that report and repair what is wrong. Submitting again is final, so "
            "submit unchanged only if every finding is acceptable."
        )

    staged_config = temporary_root / f"spreadsheet-{read_policy}-{execution}.yaml"
    staged_config.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return staged_config


def _effective_tool_schema(staged_config: Path) -> dict[str, Any]:
    """Resolve the exact native tools and bash capability exposed by a staged config."""

    config = yaml.safe_load(staged_config.read_text(encoding="utf-8"))
    tool_policy = config["agent"]["tools"]
    bundles: list[dict[str, Any]] = []
    for bundle in tool_policy.get("bundles", []):
        path = Path(bundle["path"])
        config_path = path / "config.yaml"
        bundle_tools: dict[str, Any] = {}
        if config_path.is_file():
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            bundle_tools = payload.get("tools", {})
        bundles.append(
            {
                "name": path.name,
                "source_path": str(path),
                "tools": bundle_tools,
            }
        )
    return {
        "bash_enabled": bool(tool_policy.get("enable_bash_tool", False)),
        "bundles": bundles,
    }


def _configuration_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _portable_configuration(value: dict[str, Any]) -> dict[str, Any]:
    """Remove task identity and temporary absolute bundle paths from a hash basis."""

    portable = json.loads(json.dumps(value))
    portable.pop("task", None)
    for bundle in portable.get("effective_tool_schema", {}).get("bundles", []):
        bundle.pop("source_path", None)
    staged_bundles = (
        portable.get("staged_config", {}).get("agent", {}).get("tools", {}).get("bundles", [])
    )
    for bundle in staged_bundles:
        if "path" in bundle:
            bundle["path"] = Path(bundle["path"]).name
    return portable


def _run_contract(
    *,
    args: argparse.Namespace,
    task_key: str,
    staged_config: Path,
    model_preflight: dict[str, Any],
    completion_kwargs: dict[str, Any],
    env_variables: dict[str, str],
) -> dict[str, Any]:
    """Durable, secret-free description of what the agent actually saw and could call."""

    config = yaml.safe_load(staged_config.read_text(encoding="utf-8"))
    effective = {
        "task": task_key,
        "arm": (
            "control"
            if getattr(args, "control", False)
            else "control-index"
            if getattr(args, "control_index", False)
            else "hybrid"
            if getattr(args, "hybrid", False)
            else "librecalc"
        ),
        "model": args.model,
        "model_catalog_id": model_preflight["id"],
        "provider_policy": completion_kwargs.get("provider", {"allow_fallbacks": True}),
        "reasoning_effort": args.reasoning_effort,
        "observation_variant": args.observation,
        "execution_variant": args.execution,
        "read_policy": args.read_policy,
        "unbounded_reads": bool(getattr(args, "unbounded_reads", False)),
        "read_budget_requested": bool(getattr(args, "read_budget", True)),
        "compute_read_budget_requested": bool(getattr(args, "compute_read_budget", False)),
        "effective_environment": dict(sorted(env_variables.items())),
        "effective_tool_schema": _effective_tool_schema(staged_config),
        "prompts": {
            "system_template": config["agent"]["templates"].get("system_template"),
            "instance_template": config["agent"]["templates"].get("instance_template"),
        },
        "staged_config": config,
    }
    return {
        "schema_version": 1,
        "effective_configuration_sha256": _configuration_hash(_portable_configuration(effective)),
        **effective,
    }


def _cost_accounting(
    key_usage_delta: float,
    generation_cost: float,
    harness_cost: float,
) -> tuple[float, float]:
    """Return provider-billed and conservative budget-enforcement costs."""
    charged_cost = max(key_usage_delta, generation_cost)
    return charged_cost, max(charged_cost, harness_cost)


def _generation_metadata(api_key: str, generation_id: str) -> dict[str, Any]:
    url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
    for attempt in range(12):
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            return payload["data"]
        except urllib.error.HTTPError as exc:
            if exc.code != 404 or attempt == 11:
                raise
            time.sleep(min(attempt + 1, 5))
    raise RuntimeError("unreachable generation metadata retry state")


def _safe_name(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_." else "-" for character in value
    )
    return cleaned.strip("-.")


def _stage_task(
    staging_root: Path,
    benchmark_root: Path,
    category: str,
    record: dict[str, Any],
) -> Path:
    dataset_root = staging_root / category
    relative_input = Path(record["spreadsheet_path"])
    if relative_input.is_absolute() or ".." in relative_input.parts:
        raise ValueError(f"Spreadsheet path escapes the dataset: {relative_input}")
    source = benchmark_root / "data" / category / relative_input
    destination = dataset_root / relative_input
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    (dataset_root / "dataset.json").write_text(
        json.dumps([record], indent=2),
        encoding="utf-8",
    )
    return dataset_root


def _find_output(
    work_root: Path,
    category: str,
    task_id: str,
    previous_outputs: set[Path],
) -> Path | None:
    outputs = sorted(
        (
            path
            for path in work_root.glob(
                f"trajectories/output_excel/{category}/**/{task_id}_output.xlsx"
            )
            if path not in previous_outputs
        ),
        key=lambda path: path.stat().st_mtime_ns,
    )
    return outputs[-1] if outputs else None


def _ledger_task_keys(run_root: Path) -> set[str]:
    ledger_path = run_root / "ledger.jsonl"
    keys: set[str] = set()
    if not ledger_path.is_file():
        return keys
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        task = json.loads(line).get("task")
        if task:
            keys.add(str(task))
    return keys


def _resume_action(task_root: Path, *, skip_existing: bool, recorded: bool) -> str:
    """Decide whether to run, skip, or retry a task directory on resume.

    A ledger row is the checkpoint. A directory with no ledger row is an interrupted
    attempt and is removed so ``--skip-existing`` can retry it.
    """
    if not task_root.exists():
        return "run"
    if not skip_existing:
        raise FileExistsError(f"Refusing to overwrite an existing task run: {task_root}")
    if recorded:
        return "skip"
    shutil.rmtree(task_root)
    return "retry"


def _run_task(
    *,
    args: argparse.Namespace,
    api_key: str,
    task: dict[str, str],
    run_root: Path,
    model_preflight: dict[str, Any],
) -> int:
    category = task["category"]
    task_id = task["id"]
    record = _task_record(args.benchmark_root, category, task_id)
    task_name = f"{category}-{task_id}"
    task_key = f"{category}:{task_id}"
    task_root = run_root / task_name
    trace_root = task_root / "trajectory"
    output_path = task_root / "output.xlsx"
    action = _resume_action(
        task_root,
        skip_existing=bool(getattr(args, "skip_existing", False)),
        recorded=task_key in _ledger_task_keys(run_root),
    )
    if action == "skip":
        print(f"SKIP {task_key} existing={task_root}", flush=True)
        return 0
    if action == "retry":
        print(f"RETRY {task_key} incomplete={task_root}", flush=True)
    task_root.mkdir(parents=True)

    before_usage = _key_usage(api_key)
    started_at = datetime.now(UTC)
    started_monotonic = time.monotonic()
    return_code = 1
    status = "failed"
    error: str | None = None
    trajectory_path: Path | None = None
    effective_contract: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="librecalc-openrouter-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        staged_config = _stage_tool_policy(
            source_config=args.config,
            sweagent_root=args.sweagent_root,
            temporary_root=temporary_root,
            read_policy=args.read_policy,
            execution=args.execution,
            execution_timeout=args.execution_timeout,
            observation=args.observation,
            repair_passes=args.repair_passes,
            compute_read_budget=bool(getattr(args, "compute_read_budget", False)),
            commit_gate=bool(getattr(args, "commit_gate", False)),
            control=bool(getattr(args, "control", False)),
            control_index=bool(getattr(args, "control_index", False)),
            unbounded_reads=bool(getattr(args, "unbounded_reads", False)),
            hybrid=bool(getattr(args, "hybrid", False)),
        )
        sweagent_overlay = _stage_sweagent_overlay(args.sweagent_root, temporary_root)
        dataset_root = _stage_task(
            temporary_root / "dataset", args.benchmark_root, category, record
        )
        work_root = args.sweagent_root
        previous_outputs = set(
            work_root.glob(f"trajectories/output_excel/{category}/**/{task_id}_output.xlsx")
        )
        control = bool(getattr(args, "control", False))
        control_index = bool(getattr(args, "control_index", False))
        env_variables = {
            "PIP_PROGRESS_BAR": "off",
            "LIBRECALC_SOURCE_ROOT": "/opt/librecalc/src",
            "LIBRECALC_TOOL_ROOT": "/root/tools/librecalc",
            "LIBRECALC_OBSERVATION_VARIANT": args.observation,
            "LIBRECALC_BLANK_BRIDGES": "1" if args.blank_bridges else "0",
            **(
                {
                    "LIBRECALC_COMMIT_GATE_ENABLED": "1",
                    "LIBRECALC_COMMIT_GATE_PATH": (
                        "/mnt/spreadsheet_output/.librecalc_commit_gate.json"
                    ),
                }
                if getattr(args, "commit_gate", False)
                else {}
            ),
            # Read rationing is an experiment treatment, not a product default. Bounded
            # LibreCalc arms therefore request the historical ceiling explicitly.
            "LIBRECALC_READ_MAX_CELLS": ("none" if args.read_policy == "thin" else "96"),
        }
        if control or control_index:
            # No LibreCalc tool reads these, and leaving them set would make a control
            # trajectory look like it had an interface it never had.
            env_variables = {"PIP_PROGRESS_BAR": "off"}
        if args.preserve_populated and category != "Debugging":
            env_variables["LIBRECALC_PRESERVE_POPULATED"] = "1"
        if args.observation in {"formula-anomalies-v1", "format-conventions-v1"}:
            env_variables["LIBRECALC_READ_BUDGET_ENABLED"] = "1" if args.read_budget else "0"
            if args.read_budget:
                env_variables["LIBRECALC_READ_BUDGET_PATH"] = (
                    "/mnt/spreadsheet_output/.librecalc_read_budget.json"
                )
                env_variables["LIBRECALC_INSPECTION_LIMIT"] = str(args.repair_passes)
        elif args.observation == "formula-patterns-v1" and args.compute_read_budget:
            env_variables["LIBRECALC_READ_BUDGET_ENABLED"] = "1"
            env_variables["LIBRECALC_READ_BUDGET_PATH"] = (
                "/mnt/spreadsheet_output/.librecalc_read_budget.json"
            )
            env_variables["LIBRECALC_INSPECTION_LIMIT"] = "2"
        if getattr(args, "unbounded_reads", False) and not control and not control_index:
            # The ceiling and the budget are the two ways the interface refuses a read. The
            # 297 spent 19.7% of its calls on refusals, and a single oversized first read
            # sets write_now and locks the model out of reading at all, so both come off
            # together or the arm measures neither.
            env_variables["LIBRECALC_READ_MAX_CELLS"] = "none"
            env_variables["LIBRECALC_READ_BUDGET_ENABLED"] = "0"
            env_variables.pop("LIBRECALC_READ_BUDGET_PATH", None)
            env_variables.pop("LIBRECALC_INSPECTION_LIMIT", None)
        completion_kwargs = _completion_kwargs(args, model_preflight)
        effective_contract = _run_contract(
            args=args,
            task_key=task_key,
            staged_config=staged_config,
            model_preflight=model_preflight,
            completion_kwargs=completion_kwargs,
            env_variables=env_variables,
        )
        (task_root / "run_contract.json").write_text(
            json.dumps(effective_contract, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        command = [
            str(args.sweagent_root / ".venv" / "bin" / "sweagent"),
            "run",
            "--config",
            str(staged_config),
            "--dataset_path",
            str(dataset_root),
            "--output_dir",
            str(trace_root),
            "--agent.model.name",
            f"openrouter/{args.model}",
            "--agent.model.per_instance_cost_limit",
            str(args.cost_limit),
            "--agent.model.total_cost_limit",
            str(args.cost_limit),
            "--agent.model.per_instance_call_limit",
            # The staged overlay checks before a query, so the Nth response can execute without
            # allowing an N+1 charge.
            str(args.call_limit),
            "--agent.max_requeries",
            # SWE-agent counts the initial attempt, so two permits one billable repair response.
            str(args.max_requeries),
            "--agent.model.completion_kwargs",
            json.dumps(completion_kwargs, separators=(",", ":")),
            "--agent.tools.env_variables",
            json.dumps(
                env_variables,
                separators=(",", ":"),
            ),
        ]
        environment = os.environ.copy()
        environment["OPENROUTER_API_KEY"] = api_key
        environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(sweagent_overlay), environment.get("PYTHONPATH")) if value
        )
        environment["SWE_AGENT_CONFIG_DIR"] = str(args.sweagent_root / "config")
        environment["SWE_AGENT_TOOLS_DIR"] = str(args.sweagent_root / "tools")
        environment["SWE_AGENT_TRAJECTORY_DIR"] = str(args.sweagent_root / "trajectories")
        environment.setdefault("OR_APP_NAME", "LibreCalc SpreadsheetBench")
        try:
            completed = subprocess.run(
                command,
                cwd=work_root,
                env=environment,
                timeout=args.timeout,
                check=False,
            )
            return_code = completed.returncode
            produced_output = _find_output(work_root, category, task_id, previous_outputs)
            trajectories = sorted(trace_root.glob(f"**/{task_id}.traj"))
            trajectory_path = trajectories[-1] if trajectories else None
            if return_code == 0 and produced_output is not None:
                shutil.copy2(produced_output, output_path)
                status = "completed"
            elif produced_output is None:
                error = "no output workbook"
            else:
                error = f"SWE-agent exited with status {return_code}"
        except subprocess.TimeoutExpired:
            return_code = 124
            error = f"timeout after {args.timeout} seconds"
        except KeyboardInterrupt:
            return_code = 130
            error = "interrupted"

    secondary_metrics: dict[str, int | float] = {}
    if trajectory_path is not None:
        secondary_metrics = trajectory_metrics(trajectory_path)
    usage_metrics: dict[str, int | float] = {}
    debug_log = trace_root / task_id / f"{task_id}.debug.log"
    if debug_log.is_file():
        metadata = []
        metadata_errors = 0
        for value in generation_ids(debug_log):
            try:
                metadata.append(_generation_metadata(api_key, value))
            except (KeyError, TypeError, ValueError, TimeoutError, urllib.error.URLError) as exc:
                metadata_errors += 1
                print(f"USAGE-WARNING {value}: {type(exc).__name__}: {exc}", file=sys.stderr)
        usage_metrics = generation_metrics(metadata)
        usage_metrics["generation_metadata_errors"] = metadata_errors
    after_usage = _key_usage(api_key)
    key_usage_delta = max(0.0, after_usage - before_usage)
    generation_cost = float(usage_metrics.get("generation_cost_usd", 0.0))
    harness_cost = float(secondary_metrics.get("harness_estimated_cost_usd", 0.0))
    # OpenRouter's key delta and generation records measure provider billing. SWE-agent's
    # estimate intentionally uses worst-case catalog prices and is useful for enforcing a
    # ceiling, but it must not be presented as money actually charged by the provider.
    charged_cost, budget_enforcement_cost = _cost_accounting(
        key_usage_delta,
        generation_cost,
        harness_cost,
    )
    finished_at = datetime.now(UTC)
    ledger_record: dict[str, Any] = {
        "schema_version": 1,
        "run_name": args.run_name,
        "task": f"{category}:{task_id}",
        "category": category,
        "task_id": task_id,
        "provider": "openrouter",
        "provider_only": getattr(args, "provider_only", None),
        "harness": "swe-agent-1.1.0",
        "model": args.model,
        # The control arm has no observation or execution variant. The fields stay for schema
        # stability but carry the flag's answer, so a mixed ledger cannot be misread.
        "arm": (
            "control"
            if getattr(args, "control", False)
            else "control-index"
            if getattr(args, "control_index", False)
            else "hybrid"
            if getattr(args, "hybrid", False)
            else "librecalc"
        ),
        "observation_variant": args.observation,
        "blank_bridges": bool(getattr(args, "blank_bridges", True)),
        "read_budget": env_variables.get("LIBRECALC_READ_BUDGET_ENABLED") == "1",
        "compute_read_budget": bool(getattr(args, "compute_read_budget", False))
        and env_variables.get("LIBRECALC_READ_BUDGET_ENABLED") == "1",
        "unbounded_reads": bool(getattr(args, "unbounded_reads", False)),
        "effective_environment": effective_contract.get("effective_environment", {}),
        "effective_tool_schema": effective_contract.get("effective_tool_schema", {}),
        "effective_configuration_sha256": effective_contract.get("effective_configuration_sha256"),
        "repair_passes": int(getattr(args, "repair_passes", 1)),
        "read_policy": args.read_policy,
        "execution_variant": args.execution,
        "status": status,
        "return_code": return_code,
        "error": error,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": time.monotonic() - started_monotonic,
        "charged_cost_usd": charged_cost,
        "charged_cost_method": "max(key_usage_delta,generation_sum)",
        "budget_enforcement_cost_usd": budget_enforcement_cost,
        "key_usage_before_usd": before_usage,
        "key_usage_after_usd": after_usage,
        "key_usage_delta_usd": key_usage_delta,
        "cost_limit_usd": args.cost_limit,
        "call_limit": args.call_limit,
        "max_requeries": args.max_requeries,
        "max_tokens_per_call": args.max_tokens,
        "token_limit_policy": "fixed" if args.max_tokens is not None else "remaining-budget",
        "execution_timeout_seconds": args.execution_timeout,
        "reasoning_effort": args.reasoning_effort,
        "model_catalog_name": model_preflight["name"],
        "model_context_length": model_preflight["context_length"],
        "catalog_prompt_price_per_token": model_preflight["catalog_prompt_price_per_token"],
        "catalog_completion_price_per_token": model_preflight["catalog_completion_price_per_token"],
        "safety_prompt_price_per_token": model_preflight["safety_prompt_price_per_token"],
        "safety_completion_price_per_token": model_preflight["safety_completion_price_per_token"],
        "exact_success": None,
        **secondary_metrics,
        **usage_metrics,
    }
    append_record(run_root / "ledger.jsonl", ledger_record)
    print(
        f"{status.upper()} {category}:{task_id} "
        f"cost=${ledger_record['charged_cost_usd']:.6f} output={output_path if output_path.exists() else '-'}",
        flush=True,
    )
    if status == "completed":
        return 0
    return return_code or 2


def _apply_arm_config(args: argparse.Namespace) -> argparse.Namespace:
    """When an arm flag is set and the caller left the default LibreCalc config, switch it."""
    if getattr(args, "control", False) and args.config == DEFAULT_CONFIG:
        args.config = CONTROL_CONFIG
    if getattr(args, "control_index", False) and args.config == DEFAULT_CONFIG:
        args.config = CONTROL_INDEX_CONFIG
    if getattr(args, "hybrid", False) and args.config == DEFAULT_CONFIG:
        args.config = HYBRID_CONFIG
    return args


def main() -> int:
    _load_dotenv()
    args = _arguments()
    args.slice = args.slice.resolve()
    args.benchmark_root = args.benchmark_root.resolve()
    args.sweagent_root = args.sweagent_root.resolve()
    args.config = args.config.resolve()
    if args.cost_limit <= 0:
        raise ValueError("--cost-limit must be positive")
    if (
        args.call_limit < 2
        or args.max_requeries < 1
        or (args.max_tokens is not None and args.max_tokens <= 0)
        or args.execution_timeout <= 0
    ):
        raise ValueError(
            "--call-limit must be at least 2, --max-requeries at least 1, and token/tool timeouts "
            "positive"
        )
    if getattr(args, "control", False) and getattr(args, "hybrid", False):
        raise ValueError("--control and --hybrid are mutually exclusive")
    if getattr(args, "control_index", False) and getattr(args, "control", False):
        raise ValueError("--control-index and --control are mutually exclusive")
    if getattr(args, "control_index", False) and getattr(args, "hybrid", False):
        raise ValueError("--control-index and --hybrid are mutually exclusive")
    if args.read_policy == "overview-only" and not args.observation.startswith(
        "semantic-snapshot-"
    ):
        raise ValueError("--read-policy overview-only requires a semantic-snapshot observation")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY must be set in the environment or in .env at the repo root"
        )
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required")
    slice_data = _load_json(args.slice)
    _validate_slice_model(
        slice_data,
        args.model,
        allow_mismatch=bool(getattr(args, "allow_model_mismatch", False)),
    )
    model_preflight = _model_preflight(args.model)
    _validate_reasoning_effort(model_preflight, args.reasoning_effort)
    print(
        f"MODEL {model_preflight['id']} tools=yes "
        f"prompt=${model_preflight['catalog_prompt_price_per_token']:.9f}/token "
        f"completion=${model_preflight['catalog_completion_price_per_token']:.9f}/token",
        flush=True,
    )
    sweagent_binary = args.sweagent_root / ".venv" / "bin" / "sweagent"
    if not sweagent_binary.is_file():
        raise FileNotFoundError(f"SWE-agent environment not found: {sweagent_binary}")
    _apply_arm_config(args)
    run_name = _safe_name(args.run_name)
    if not run_name:
        raise ValueError("--run-name must contain a filename-safe character")
    run_root = args.benchmark_root / "benchmark-runs" / "openrouter" / run_name
    run_root.mkdir(parents=True, exist_ok=True)

    tasks = _selected_tasks(slice_data, args.task)
    failures = sum(
        _run_task(
            args=args,
            api_key=api_key,
            task=task,
            run_root=run_root,
            model_preflight=model_preflight,
        )
        != 0
        for task in tasks
    )
    print(f"SUMMARY tasks={len(tasks)} failures={failures} ledger={run_root / 'ledger.jsonl'}")
    score_status = 0
    if not args.no_score:
        score_status = subprocess.call(
            [
                sys.executable,
                str(PROJECT_ROOT / "benchmark" / "score_openrouter_run.py"),
                str(run_root),
                "--write-ledger",
            ],
            cwd=PROJECT_ROOT,
        )
    return 1 if failures or score_status else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
