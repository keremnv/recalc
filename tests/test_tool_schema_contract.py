"""Advertised tool JSON must be what the wrapper and SWE-agent actually accept.

Live runs are not the fuzzer for this. The Debugging calc_read_ranges rejection was a
model copying calc_read's ``cell_range`` into an untyped object that the parser then
refused. This file fails that class of bug without an API call.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from librecalc_mcp.domain.models import CalcOperation

PROJECT_ROOT = Path(__file__).parents[1]
BUNDLE_CONFIG = PROJECT_ROOT / "benchmark/sweagent/librecalc/config.yaml"
# Heterogeneous payloads; a closed key-set would be a lie.
OPEN_OBJECT_ARGUMENTS = {"operations_json", "chart_json"}
EXAMPLE_A1 = "C9:F9"


def _calc_tool_module():
    path = PROJECT_ROOT / "benchmark/sweagent/librecalc/lib/calc_tool.py"
    spec = importlib.util.spec_from_file_location("benchmark_calc_tool_schema", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tools() -> dict[str, Any]:
    return yaml.safe_load(BUNDLE_CONFIG.read_text(encoding="utf-8"))["tools"]


def _object_arguments() -> list[tuple[str, str, dict[str, Any]]]:
    found: list[tuple[str, str, dict[str, Any]]] = []
    for tool_name, tool in _tools().items():
        for argument in tool.get("arguments", []):
            items = argument.get("items") or {}
            if (argument.get("type") == "array" and items.get("type") == "object") or argument.get(
                "type"
            ) == "object":
                found.append((tool_name, argument["name"], argument))
    return found


def _parser_for(name: str):
    calc_tool = _calc_tool_module()
    parsers = {
        "ranges_json": lambda raw: calc_tool._parse_range_requests(raw),
        "formula_blocks_json": lambda raw: calc_tool._formula_blocks(raw, CalcOperation),
    }
    return parsers.get(name)


def _example_value(property_schema: dict[str, Any], name: str) -> Any:
    if name in {"range", "cell_range"}:
        return EXAMPLE_A1
    if name == "formula":
        return "=C6-C7+C8"
    if name == "sheet":
        return "Model"
    if property_schema.get("type") == "string":
        return "x"
    raise AssertionError(f"no example value for property {name!r}")


def test_closed_object_arrays_declare_properties() -> None:
    """Untyped {type: object} plus a closed parser is the calc_read_ranges bug."""

    for tool_name, argument_name, argument in _object_arguments():
        if argument_name in OPEN_OBJECT_ARGUMENTS:
            continue
        items = argument.get("items") or argument
        assert items.get("properties"), (
            f"{tool_name}.{argument_name} advertises an untyped object; "
            "give it properties or add it to OPEN_OBJECT_ARGUMENTS"
        )
        assert _parser_for(argument_name) is not None, (
            f"{tool_name}.{argument_name} has a typed schema but no registered parser"
        )


def test_advertised_required_keys_parse() -> None:
    for _tool_name, argument_name, argument in _object_arguments():
        parser = _parser_for(argument_name)
        if parser is None:
            continue
        items = argument["items"]
        required = items["required"]
        properties = items["properties"]
        payload = {name: _example_value(properties[name], name) for name in required}
        parser(json.dumps([payload]))


def test_range_fields_accept_calc_read_cell_range_alias() -> None:
    """calc_read's argument is cell_range. Nested objects must accept that copy."""

    for _tool_name, argument_name, argument in _object_arguments():
        parser = _parser_for(argument_name)
        if parser is None:
            continue
        properties = argument["items"]["properties"]
        if "range" not in properties:
            continue
        required = [name for name in argument["items"]["required"] if name != "range"]
        payload = {name: _example_value(properties[name], name) for name in required}
        payload["cell_range"] = EXAMPLE_A1
        parser(json.dumps([payload]))


def test_nested_item_schema_is_not_a_flat_string_map() -> None:
    """SWE-agent Argument.items was dict[str, str]; nested properties cannot live there."""

    for tool_name, argument_name, argument in _object_arguments():
        if _parser_for(argument_name) is None:
            continue
        items = argument["items"]
        assert any(not isinstance(value, str) for value in items.values()), (
            f"{tool_name}.{argument_name} items are a flat string map; "
            "nested properties would be dropped by SWE-agent's Argument type"
        )


def test_operations_accept_cell_range_alias() -> None:
    operation = CalcOperation.from_dict(
        {
            "op": "fill_formula",
            "sheet": "Model",
            "cell_range": "B2",
            "formula": "=SUM(B3:B5)",
        }
    )
    assert operation.range == "B2"
    same = CalcOperation.from_dict(
        {
            "op": "set_formula",
            "sheet": "Model",
            "range": "B2",
            "cell_range": "B2",
            "formula": "=1",
        }
    )
    assert same.range == "B2"
    with pytest.raises(ValueError, match="conflicting range and cell_range"):
        CalcOperation.from_dict(
            {
                "op": "set_formula",
                "sheet": "Model",
                "range": "B2",
                "cell_range": "C2",
                "formula": "=1",
            }
        )
