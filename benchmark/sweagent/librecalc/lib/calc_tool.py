#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import pathlib
import sys
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_READ_NEIGHBORHOOD_MAX_CELLS = 96


def _ensure_product_on_path() -> None:
    """The product package is mounted into the agent container, not installed."""
    source_root = os.environ.get("LIBRECALC_SOURCE_ROOT", "/opt/librecalc/src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)


def _load_backend_types() -> tuple[type[Any], type[Any]]:
    _ensure_product_on_path()

    from librecalc_mcp.backend.uno import UnoCalcBackend
    from librecalc_mcp.domain.models import CalcOperation

    return UnoCalcBackend, CalcOperation


def _observation():
    """Observation/diff models live in the product, not in this wrapper."""
    _ensure_product_on_path()

    from librecalc_mcp.domain import diff, grid, observation

    return observation, diff, grid


def _read_budget():
    """Sibling module in this bundle: the budget is an instrument, not a primitive."""
    if str(pathlib.Path(__file__).parent) not in sys.path:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import read_budget

    return read_budget


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _parse_json(raw: str, expected_type: type[Any], label: str) -> Any:
    raw = urllib.parse.unquote(raw)
    raw = urllib.parse.unquote(raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, expected_type):
        raise TypeError(f"{label} must decode to {expected_type.__name__}")
    return value


def _parse_range_requests(raw: str) -> list[tuple[str, str]]:
    requests = _parse_json(raw, list, "ranges_json")
    parsed: list[tuple[str, str]] = []
    for index, request in enumerate(requests):
        if not isinstance(request, dict) or set(request) != {"sheet", "range"}:
            raise ValueError(f"ranges_json item {index} requires only sheet and range")
        sheet = request["sheet"]
        cell_range = request["range"]
        if not isinstance(sheet, str) or not isinstance(cell_range, str):
            raise TypeError(f"ranges_json item {index} fields must be strings")
        if _observation()[2].A1_RANGE.fullmatch(cell_range.upper()) is None:
            raise ValueError(f"ranges_json item {index} has invalid A1 range: {cell_range}")
        parsed.append((sheet, cell_range))
    if not parsed:
        raise ValueError("ranges_json must contain at least one range")
    return parsed


def _parse_sheet_names(raw: str) -> list[str]:
    values = _parse_json(raw, list, "target_sheets_json")
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("target_sheets_json must contain only non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError("target_sheets_json must not contain duplicates")
    return values


def _range_requests(raw: str) -> list[tuple[str, str]]:
    parsed = _parse_range_requests(raw)
    for index, (_, cell_range) in enumerate(parsed):
        _require_neighborhood_range(cell_range, label=f"ranges_json item {index}")
    return parsed


def _formula_blocks(raw_blocks: str, operation_type: type[Any]) -> list[Any]:
    blocks = _parse_json(raw_blocks, list, "formula_blocks_json")
    operations = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise TypeError(f"formula_blocks_json item {index} must be an object")
        required = {"sheet", "range", "formula"}
        if set(block) != required or not all(isinstance(block[key], str) for key in required):
            raise ValueError(
                f"formula_blocks_json item {index} requires only string fields "
                "sheet, range, and formula"
            )
        operations.append(operation_type(op="fill_formula", **block))
    return operations


def _read_neighborhood_limit() -> int | None:
    """Cell ceiling for a single read, or None to disable it.

    The 96-cell cap is an invariant of the *semantic* interface: calc_inspect already
    supplies structure there, so a whole-sheet dump is an inspect-spiral rather than a
    need. The thin ablation arm has no semantic inspect, so applying the same cap would
    handicap it for a reason unrelated to interface thickness and would bias the
    comparison toward the arm the project is arguing for.
    """
    raw = os.environ.get("LIBRECALC_READ_MAX_CELLS")
    if raw is None:
        return _READ_NEIGHBORHOOD_MAX_CELLS
    if raw.strip().lower() in {"", "0", "none", "unbounded"}:
        return None
    return int(raw)


def _require_neighborhood_range(cell_range: str, *, label: str) -> None:
    limit = _read_neighborhood_limit()
    if limit is None:
        return
    count = _observation()[2].a1_cell_count(cell_range)
    if count > limit:
        raise ValueError(
            f"{label} {cell_range} covers {count} cells; neighborhood reads are limited to "
            f"{limit} cells (a few rows or columns around a candidate). "
            "Narrow the range; do not dump a used range or whole sheet."
        )


@contextmanager
def _exclusive_runtime() -> Iterator[None]:
    """Serialize independent agent processes against Calc's single UNO runtime."""
    lock_path = os.environ.get("LIBRECALC_LOCK_PATH", "/tmp/librecalc-benchmark.lock")
    with open(lock_path, "w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def main(argv: list[str]) -> int:
    if not argv:
        raise ValueError("missing command")

    backend_type, operation_type = _load_backend_types()
    backend = backend_type()
    command, *args = argv

    if command == "health":
        result = backend.health()
        _emit(result)
        return 0 if result.get("ok") else 1

    if command == "inspect" and len(args) in {1, 2}:
        path = args[0]
        detailed_sheets = set(_parse_sheet_names(args[1])) if len(args) == 2 else set()
        variant = os.environ.get("LIBRECALC_OBSERVATION_VARIANT", "grid-v1")
        _read_budget().reset_read_budget()
        _emit(
            _observation()[0].workbook_observation(
                backend,
                path,
                variant,
                detailed_sheets=detailed_sheets,
            )
        )
        return 0

    if command == "compare" and len(args) == 2:
        before_path, after_path = args
        before = _observation()[0].workbook_observation(backend, before_path, "semantic-snapshot-v2")
        after = _observation()[0].workbook_observation(backend, after_path, "semantic-snapshot-v2")
        _emit(_observation()[1].semantic_diff(before, after))
        return 0

    if command == "read" and len(args) == 3:
        path, sheet, cell_range = args
        if _read_budget().read_budget_error() is not None:
            _emit({"ok": False, "error": _read_budget().read_budget_error()})
            return 1
        if _observation()[2].A1_RANGE.fullmatch(cell_range.upper()) is None:
            raise ValueError(f"invalid A1 range: {cell_range}")
        _require_neighborhood_range(cell_range, label="calc_read range")
        result = backend.read_range(sheet=sheet, cell_range=cell_range, path=path)
        variant = os.environ.get("LIBRECALC_OBSERVATION_VARIANT", "grid-v1")
        _read_budget().consume_read_budget(successful=True)
        _emit(
            _observation()[0].format_read_observation(
                result,
                sheet=sheet,
                cell_range=cell_range,
                variant=variant,
            )
        )
        return 0

    if command == "read-ranges" and len(args) == 2:
        path, raw_requests = args
        if (budget_error := _read_budget().read_budget_error()) is not None:
            _emit({"ok": False, "error": budget_error})
            return 1
        requests = _parse_range_requests(raw_requests)
        valid_requests: list[tuple[str, str]] = []
        valid_indexes: list[int] = []
        formatted: list[dict[str, Any] | None] = [None] * len(requests)
        for index, (sheet, cell_range) in enumerate(requests):
            try:
                _require_neighborhood_range(cell_range, label=f"ranges_json item {index}")
            except ValueError as exc:
                formatted[index] = {
                    "ok": False,
                    "sheet": sheet,
                    "range": cell_range.upper(),
                    "error": f"ValueError: {exc}",
                }
            else:
                valid_requests.append((sheet, cell_range))
                valid_indexes.append(index)

        results = backend.read_ranges(valid_requests, path=path) if valid_requests else []
        variant = os.environ.get("LIBRECALC_OBSERVATION_VARIANT", "grid-v1")
        for index, (request, result) in zip(valid_indexes, zip(valid_requests, results, strict=True)):
            sheet, cell_range = request
            observation = _observation()[0].format_read_observation(
                result,
                sheet=sheet,
                cell_range=cell_range,
                variant=variant,
            )
            if variant == "grid-v1":
                observation = {"sheet": sheet, "range": cell_range.upper(), **observation}
            formatted[index] = observation
        assert all(item is not None for item in formatted)
        _read_budget().consume_read_budget(successful=bool(valid_requests))
        _emit({"ranges": formatted})
        return 0

    if command == "write" and len(args) == 5:
        path, output_path, sheet, cell_range, raw_values = args
        values = _parse_json(raw_values, list, "values_json")
        _emit(
            backend.write_range(
                sheet=sheet,
                cell_range=cell_range,
                values=values,
                path=path,
                output_path=output_path,
            )
        )
        return 0

    if command == "fill-formulas" and len(args) == 3:
        path, output_path, raw_blocks = args
        operations = _formula_blocks(raw_blocks, operation_type)
        _emit(backend.execute_program(operations, path=path, output_path=output_path))
        return 0

    if command == "program" and len(args) == 3:
        path, output_path, raw_operations = args
        operation_dicts = _parse_json(raw_operations, list, "operations_json")
        operations = []
        for index, operation in enumerate(operation_dicts):
            if not isinstance(operation, dict):
                raise TypeError(f"operations_json item {index} must be an object")
            operations.append(operation_type.from_dict(operation))
        _emit(backend.execute_program(operations, path=path, output_path=output_path))
        return 0

    if command == "inspect-charts" and len(args) == 1:
        path = args[0]
        if not hasattr(backend, "inspect_charts"):
            _emit({"ok": False, "error": "backend does not support chart inspection"})
            return 1
        charts = backend.inspect_charts(path=path)
        _emit({"ok": True, "path": path, "count": len(charts), "charts": charts})
        return 0

    if command == "upsert-chart" and len(args) == 3:
        path, output_path, raw_chart = args
        chart = _parse_json(raw_chart, dict, "chart_json")
        operations = [operation_type.from_dict({"op": "upsert_chart", "chart": chart})]
        _emit(backend.execute_program(operations, path=path, output_path=output_path))
        return 0

    raise ValueError(f"invalid arguments for {command!r}")


if __name__ == "__main__":
    try:
        with _exclusive_runtime():
            raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        raise SystemExit(1) from exc
