"""Candidate D1: direct validated-dict -> value reconstruction (same payload).

Replaces artifact._book's per-cell canonical(typed).decode() +
_value_from_json() round-trip with a direct mapping. All product
validation (_check_typed, COORD, dtype, bounds, dupes, limits) is kept
identical; NaN/Infinity rejection (previously via canonical(allow_nan=False))
is preserved explicitly. No format change: same bytes in, same MemoryBook out.

Usage: d1.patch() swaps recalc_agent.read_engine.artifact._book.
"""
import datetime as dt
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "src"))

from recalc_agent.read_engine import artifact as _art  # noqa: E402
from recalc_agent.read_engine.direct import (ArrayFormula, DataTableFormula, MemoryBook, SheetInfo)  # noqa: E402


def _direct_value(typed):
    kind = typed["kind"]
    if kind == "scalar":
        v = typed["value"]
        if isinstance(v, float) and not math.isfinite(v):
            raise _art.ArtifactError("non-finite scalar")
        return v
    if kind == "array":
        return ArrayFormula(ref=typed["ref"], text=typed["text"])
    if kind == "datatable":
        return DataTableFormula(**typed["attrs"])
    if kind == "datetime":
        return dt.datetime.fromisoformat(typed["value"])
    if kind == "date":
        return dt.date.fromisoformat(typed["value"])
    if kind == "time":
        return dt.time.fromisoformat(typed["value"])
    if kind == "timedelta":
        s = typed["seconds"]
        if isinstance(s, float) and not math.isfinite(s):
            raise _art.ArtifactError("non-finite timedelta")
        return dt.timedelta(seconds=s)
    raise _art.ArtifactError("invalid typed value kind")


def _book_direct(raw: bytes) -> MemoryBook:
    import json
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise _art.ArtifactError("invalid payload JSON") from exc
    if not isinstance(obj, dict) or set(obj) != {"sheets"} or not isinstance(obj["sheets"], list) or len(obj["sheets"]) > _art.MAX_SHEETS:
        raise _art.ArtifactError("invalid sheet list")
    sheets = []
    seen = set()
    count = 0
    for entry in obj["sheets"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "bounds", "merged", "cells"}:
            raise _art.ArtifactError("invalid sheet record")
        name, bounds, merged, cells = entry["name"], entry["bounds"], entry["merged"], entry["cells"]
        if not isinstance(name, str) or len(name) > 255 or name in seen:
            raise _art.ArtifactError("invalid or duplicate sheet name")
        seen.add(name)
        if not isinstance(bounds, list) or len(bounds) != 4 or any(type(x) is not int or x < 1 or x > 2**31 - 1 for x in bounds):
            raise _art.ArtifactError("invalid bounds")
        if bounds[0] > bounds[2] or bounds[1] > bounds[3]:
            raise _art.ArtifactError("inverted bounds")
        if not isinstance(merged, list) or not isinstance(cells, list):
            raise _art.ArtifactError("invalid merged/cells list")
        if len(merged) > _art.MAX_CELLS:
            raise _art.ArtifactError("too many merged ranges")
        ranges = []
        for item in merged:
            if not isinstance(item, list) or len(item) != 4 or any(type(x) is not int or x < 1 or x > 2**31 - 1 for x in item):
                raise _art.ArtifactError("invalid merged range")
            if item[0] > item[2] or item[1] > item[3]:
                raise _art.ArtifactError("inverted merged range")
            ranges.append(tuple(item))
        store = {}
        for item in cells:
            if not isinstance(item, list) or len(item) != 3:
                raise _art.ArtifactError("invalid cell record")
            coord, dtype, typed = item
            if not isinstance(coord, str) or len(coord) > 12 or not _art.COORD.fullmatch(coord) or coord in store:
                raise _art.ArtifactError("invalid or duplicate coordinate")
            if not isinstance(dtype, str) or dtype not in {"n", "s", "b", "e", "f", "d", "inlineStr", "str"}:
                raise _art.ArtifactError("invalid data type")
            _art._check_typed(typed)
            try:
                value = _direct_value(typed)
            except (TypeError, ValueError, KeyError, OverflowError) as exc:
                raise _art.ArtifactError("invalid typed value") from exc
            store[coord] = (value, dtype)
            count += 1
            if count > _art.MAX_CELLS:
                raise _art.ArtifactError("too many cells")
        sheets.append(SheetInfo(name, *bounds, ranges, store))
    return MemoryBook(sheets)


def patch():
    _art._book = _book_direct
    return _art
