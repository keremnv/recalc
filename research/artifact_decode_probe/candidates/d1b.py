"""Candidate D1b: D1 direct reconstruction + manual coordinate validation.

Same payload, same accept/reject language as artifact.COORD
(^[A-Z]{1,4}[1-9][0-9]{0,7}$ with the len<=12 pre-check), without the
per-cell regex engine. Differentially tested against the regex in
score_d1 --step coordfuzz.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import d1 as _d1  # noqa: E402
from recalc_agent.read_engine import artifact as _art  # noqa: E402
from recalc_agent.read_engine.direct import MemoryBook, SheetInfo  # noqa: E402


def coord_ok(coord):
    if not isinstance(coord, str):
        return False
    n = len(coord)
    if n < 2 or n > 12:
        return False
    i = 0
    while i < n and "A" <= coord[i] <= "Z":
        i += 1
        if i > 4:
            return False
    letters = i
    if letters == 0 or i >= n:
        return False
    if not ("1" <= coord[i] <= "9"):
        return False
    i += 1
    while i < n:
        if not ("0" <= coord[i] <= "9"):
            return False
        i += 1
    return (n - letters) <= 8


def _book_d1b(raw: bytes) -> MemoryBook:
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
            if not coord_ok(coord) or coord in store:
                raise _art.ArtifactError("invalid or duplicate coordinate")
            if not isinstance(dtype, str) or dtype not in {"n", "s", "b", "e", "f", "d", "inlineStr", "str"}:
                raise _art.ArtifactError("invalid data type")
            _art._check_typed(typed)
            try:
                value = _d1._direct_value(typed)
            except (TypeError, ValueError, KeyError, OverflowError) as exc:
                raise _art.ArtifactError("invalid typed value") from exc
            store[coord] = (value, dtype)
            count += 1
            if count > _art.MAX_CELLS:
                raise _art.ArtifactError("too many cells")
        sheets.append(SheetInfo(name, *bounds, ranges, store))
    return MemoryBook(sheets)


def patch():
    _art._book = _book_d1b
    return _art
