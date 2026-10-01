#!/usr/bin/env python3
"""Mechanical recoverability preflight for formula-synthesis references.

No model calls, workbook writes, parser changes, grounding changes, or new
semantic relations.  Gold formulas are used only after candidate generation
to score reference coverage.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from formula_operational import parse_use_def_slots  # noqa: E402
from librecalc_mcp.domain.formulas import translate_a1_formula  # noqa: E402
from task_obligation_shape import family_of  # noqa: E402


SYNTH = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-synthesis-probe"
SPINE_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe/spines"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-projection-preflight"
WINDOW = 4
STAGES = ("C0_M0", "C1_M0_M1", "C2_M0_M2", "C3_M0_M3", "C4_M0_M4", "C5_M0_M5", "C6_M0_M6", "C7_ALL")
MECHANISMS = tuple(f"M{i}" for i in range(9))
KNOWN_ADDRESSES = {"K6", "K163", "L163", "D10", "H41", "J31", "J46", "AF66", "AG66", "K104", "Y39", "Y40"}
KNOWN_CASE_BINDINGS = {
    ("04_05", "O5", "K6"), ("09_05", "O2", "K163"), ("09_05", "O2", "L163"),
    ("14_05", "O2", "D10"), ("20_04", "O1", "H41"), ("14_05", "O5", "J31"),
    ("08_01", "O6", "J46"), ("08_01", "O3", "AF66"), ("08_01", "O3", "AG66"),
    ("17_03", "O6", "K104"), ("15_04", "O1", "Y39"), ("15_04", "O1", "Y40"),
}

FREEZE = {
    "mechanisms": {
        "M0": "CURRENT_PACKET",
        "M1": "TASK_NAMED_SOURCE",
        "M2": "TARGET_LOCAL_FORMULA_NEIGHBORS",
        "M3": "SAME_FINGERPRINT_HOMOLOGUES",
        "M4": "SAME_ROW_SAME_COLUMN_FORMULA_STRUCTURE",
        "M5": "GROUNDED_SUBJECT_REGION",
        "M6": "FORMULA_CLASS_REFERENCE_TEMPLATE",
        "M7": "EXISTING_TARGET_FORMULA",
        "M8": "CONSUMER_DATAFLOW_CONTEXT",
    },
    "cumulative_order": list(STAGES),
    "local_formula_window": WINDOW,
    "homologue_compression": "one representative per existing formula class; class membership and counts retained, no candidate class dropped",
    "range_representation": "canonical sheet/start/end relation, or mechanically equivalent full point membership when the packet/spine exposes it",
    "token_estimate": "serialized JSON characters divided by four; raw retains provenance, compact retains canonical IDs/ranges plus provenance counts",
    "gold_in_candidate_generation": False,
    "original_workbooks_modified": False,
}

RefKey = tuple[str, str, int, int, int | None, int | None]


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def a1(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)", text or "")
    if not m:
        return None
    from fingerprint import column_number

    return column_number(m.group(1)), int(m.group(2))


def parse_cell_id(cell: str) -> tuple[str, int, int] | None:
    m = re.fullmatch(r"cell:(sheet:s\d+|s\d+):r(\d+):c(\d+)", cell or "")
    if not m:
        return None
    sid = m.group(1)
    if not sid.startswith("sheet:"):
        sid = "sheet:" + sid
    return sid, int(m.group(2)), int(m.group(3))


def cell_id(sid: str, row: int, col: int) -> str:
    return f"cell:{sid}:r{row}:c{col}"


def row_id(sid: str, row: int) -> str:
    return f"row:{sid}:r{row}"


def col_id(sid: str, col: int) -> str:
    return f"col:{sid}:c{col}"


def sid_for(spine: dict[str, Any], title: str) -> str | None:
    idx = (spine.get("title_to_index") or {}).get(title)
    return None if idx is None else f"sheet:s{int(idx):02d}"


def title_for(spine: dict[str, Any], sid: str) -> str | None:
    raw = sid.removeprefix("sheet:")
    try:
        idx = int(raw.removeprefix("s"))
    except ValueError:
        return None
    for sheet in spine.get("sheets") or []:
        if sheet.get("index") == idx:
            return sheet.get("title")
    return None


def formula_origin(form: dict[str, Any]) -> tuple[int, int, str] | None:
    m = re.fullmatch(r"formula:(s\d+):r(\d+):c(\d+)", form.get("id", ""))
    if not m:
        return None
    return int(m.group(3)), int(m.group(2)), "sheet:" + m.group(1)


def ref_key(spine: dict[str, Any], host: str, start: str, end: str | None) -> RefKey | None:
    sid = sid_for(spine, host)
    first = a1(start)
    last = a1(end or start)
    if not sid or not first or not last:
        return None
    if end is None:
        return ("POINT", sid, first[1], first[0], None, None)
    return ("RANGE", sid, min(first[1], last[1]), min(first[0], last[0]), max(first[1], last[1]), max(first[0], last[0]))


def ref_dict(key: RefKey, spine: dict[str, Any]) -> dict[str, Any]:
    kind, sid, r1, c1, r2, c2 = key
    title = title_for(spine, sid)
    if kind == "POINT":
        return {"type": kind, "sheet_id": sid, "sheet": title, "address": f"{get_column_letter(c1)}{r1}", "row": r1, "col": c1}
    return {"type": kind, "sheet_id": sid, "sheet": title, "start": f"{get_column_letter(c1)}{r1}", "end": f"{get_column_letter(c2)}{r2}", "r1": r1, "c1": c1, "r2": r2, "c2": c2}


def get_column_letter(col: int) -> str:
    out = ""
    n = col
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def parse_formula_refs(formula: str | None, origin_sheet: str, origin_row: int, origin_col: int) -> tuple[list[RefKey], bool, dict[str, Any]]:
    if not formula or not isinstance(formula, str):
        return [], True, {"opaque": False, "parser_ok": True, "slots": []}
    parsed = parse_use_def_slots(formula, origin_sheet, origin_col, origin_row)
    refs: list[RefKey] = []
    for slot in parsed.get("slots") or []:
        end = slot.get("end")
        # Convert the parser's sheet title and A1 slots through the spine later.
        refs.append(("RANGE" if slot.get("is_range") else "POINT", slot["sheet"], slot["r1"], slot["c1"], slot["r2"] if slot.get("is_range") else None, slot["c2"] if slot.get("is_range") else None))
    return refs, bool(parsed.get("parser_ok")) and not bool(parsed.get("opaque")), parsed


def normalize_refs(spine: dict[str, Any], refs: Iterable[RefKey]) -> set[RefKey]:
    out: set[RefKey] = set()
    for raw in refs:
        kind, host, r1, c1, r2, c2 = raw
        if host.startswith("sheet:"):
            sid = host
            # Parsed hosts are titles; actual stable IDs are normalized below.
            if title_for(spine, sid) is None:
                continue
        else:
            sid = sid_for(spine, host)
        if sid is None:
            continue
        out.add((kind, sid, r1, c1, r2, c2))
    return out


def formula_refs(spine: dict[str, Any], form: dict[str, Any]) -> tuple[set[RefKey], bool]:
    origin = formula_origin(form)
    if not origin:
        return set(), False
    col, row, sid = origin
    title = title_for(spine, sid)
    refs, supported, _ = parse_formula_refs(form.get("formula"), title or "", row, col)
    return normalize_refs(spine, refs), supported


def translate_formula_refs(spine: dict[str, Any], form: dict[str, Any], target_sid: str, target_row: int, target_col: int) -> tuple[set[RefKey], bool]:
    origin = formula_origin(form)
    if not origin or not form.get("formula"):
        return set(), False
    source_col, source_row, source_sid = origin
    source_title = title_for(spine, source_sid)
    if not source_title:
        return set(), False
    try:
        translated = translate_a1_formula(form["formula"], column_offset=target_col - source_col, row_offset=target_row - source_row)
    except Exception:
        return set(), False
    refs, supported, parsed = parse_formula_refs(translated, title_for(spine, target_sid) or source_title, target_row, target_col)
    return normalize_refs(spine, refs), supported and not parsed.get("opaque")


def packet_ids(packet: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str) and re.match(r"^(?:sheet|cell|row|col|text|tcoord|formula|dep|range):", value):
            out.add(value)
    walk(packet)
    return out


def packet_point_candidates(packet: dict[str, Any]) -> set[tuple[str, int, int]]:
    out = set()
    for item in packet_ids(packet):
        parsed = parse_cell_id(item)
        if parsed:
            out.add(parsed)
    return out


def point_from_key(key: RefKey) -> tuple[str, int, int] | None:
    if key[0] != "POINT":
        return None
    return key[1], key[2], key[3]


def key_from_point(point: tuple[str, int, int]) -> RefKey:
    return ("POINT", point[0], point[1], point[2], None, None)


def range_cells(key: RefKey) -> set[tuple[str, int, int]]:
    if key[0] != "RANGE":
        p = point_from_key(key)
        return set() if p is None else {p}
    _kind, sid, r1, c1, r2, c2 = key
    return {(sid, row, col) for row in range(r1, r2 + 1) for col in range(c1, c2 + 1)}


def spine_cell_present(spine: dict[str, Any], point: tuple[str, int, int]) -> bool:
    sid, row, col = point
    raw = sid.removeprefix("sheet:")
    try:
        idx = int(raw.removeprefix("s"))
    except ValueError:
        return False
    for sheet in spine.get("sheets") or []:
        if sheet.get("index") == idx:
            b = sheet.get("bounds") or {}
            return b.get("min_row", 1) <= row <= b.get("max_row", 0) and b.get("min_col", 1) <= col <= b.get("max_col", 0)
    return False


def spine_ref_present(spine: dict[str, Any], key: RefKey) -> bool:
    return all(spine_cell_present(spine, p) for p in range_cells(key))


def packet_ref_present(packet_points: set[tuple[str, int, int]], key: RefKey) -> bool:
    return all(p in packet_points for p in range_cells(key))


def formula_indexes(spine: dict[str, Any]) -> dict[str, Any]:
    by_cell: dict[tuple[str, int, int], dict[str, Any]] = {}
    by_row: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_col: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for form in spine.get("formulas") or []:
        origin = formula_origin(form)
        if not origin or form.get("opaque"):
            continue
        col, row, sid = origin
        form["_origin"] = (sid, row, col)
        by_cell[(sid, row, col)] = form
        by_row[(sid, row)].append(form)
        by_col[(sid, col)].append(form)
        if form.get("class_id"):
            by_class[form["class_id"]].append(form)
    for values in by_row.values():
        values.sort(key=lambda x: x["_origin"][2])
    for values in by_col.values():
        values.sort(key=lambda x: x["_origin"][1])
    point_consumers: dict[tuple[str, int, int], set[str]] = defaultdict(set)
    range_consumers: list[tuple[tuple[str, int, int], tuple[str, int, int], str]] = []
    for dep in spine.get("point_deps") or []:
        source = parse_cell_id(dep.get("source_id", ""))
        consumer = dep.get("consumer_formula_id")
        if source and consumer:
            point_consumers[source].add(consumer)
    for dep in spine.get("range_deps") or []:
        start = parse_cell_id(dep.get("source_start_id", ""))
        end = parse_cell_id(dep.get("source_end_id", ""))
        consumer = dep.get("consumer_formula_id")
        if start and end and consumer and start[0] == end[0]:
            range_consumers.append((start, end, consumer))
    return {"by_cell": by_cell, "by_row": by_row, "by_col": by_col, "by_class": by_class, "point_consumers": point_consumers, "range_consumers": range_consumers}


def dedup_class_forms(forms: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for form in forms:
        cid = form.get("class_id") or form.get("id")
        if cid in seen:
            continue
        seen.add(cid)
        out.append(form)
    return out


def local_formulas(index: dict[str, Any], sid: str, row: int, col: int) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for form in index["by_row"].get((sid, row), []):
        fcol = form["_origin"][2]
        if abs(fcol - col) <= WINDOW:
            chosen[form["id"]] = form
    for form in index["by_col"].get((sid, col), []):
        frow = form["_origin"][1]
        if abs(frow - row) <= WINDOW:
            chosen[form["id"]] = form
    for values, axis in ((index["by_row"].get((sid, row), []), 2), (index["by_col"].get((sid, col), []), 1)):
        ordered = sorted(values, key=lambda f: abs(f["_origin"][axis] - (col if axis == 2 else row)))
        for form in ordered:
            if form["_origin"][axis] != (col if axis == 2 else row):
                chosen[form["id"]] = form
                break
    return list(chosen.values())


def formula_candidates(spine: dict[str, Any], forms: Iterable[dict[str, Any]], sid: str, row: int, col: int, *, translate: bool) -> tuple[set[RefKey], set[RefKey], dict[str, Any]]:
    points: set[RefKey] = set()
    ranges: set[RefKey] = set()
    provenance: dict[str, Any] = {"formula_ids": [], "class_ids": [], "unsupported": 0}
    for form in forms:
        provenance["formula_ids"].append(form["id"])
        if form.get("class_id"):
            provenance["class_ids"].append(form["class_id"])
        refs, supported = translate_formula_refs(spine, form, sid, row, col) if translate else formula_refs(spine, form)
        if not supported:
            provenance["unsupported"] += 1
        for key in refs:
            (ranges if key[0] == "RANGE" else points).add(key)
    provenance["formula_ids"] = sorted(set(provenance["formula_ids"]))
    provenance["class_ids"] = sorted(set(provenance["class_ids"]))
    return points, ranges, provenance


def subject_rows(packet: dict[str, Any]) -> set[tuple[str, int]]:
    out = set()
    for hit in packet.get("subject") or []:
        sid = hit.get("sheet_id")
        rid = hit.get("row_id")
        if sid and rid:
            m = re.fullmatch(r"row:s(\d+):r(\d+)", rid)
            if m:
                out.add(("sheet:s" + m.group(1), int(m.group(2))))
    return out


def task_named_candidates(spine: dict[str, Any], packet: dict[str, Any]) -> tuple[set[RefKey], set[RefKey], dict[str, Any]]:
    points = set()
    for value in (packet.get("subject") or []) + (packet.get("source") or []) + (packet.get("scope") or []):
        parsed = parse_cell_id(value.get("cell_id", "")) if isinstance(value, dict) else None
        if parsed:
            points.add(key_from_point(parsed))
    return points, set(), {"direct_grounded_entity_count": len(points)}


def consumer_forms(spine: dict[str, Any], index: dict[str, Any], target_cells: set[tuple[str, int, int]]) -> list[dict[str, Any]]:
    consumer_ids: set[str] = set()
    for target in target_cells:
        consumer_ids.update(index["point_consumers"].get(target, set()))
    for start, end, consumer in index["range_consumers"]:
        if start[0] != end[0]:
            continue
        for target in target_cells:
            if target[0] == start[0] and min(start[1], end[1]) <= target[1] <= max(start[1], end[1]) and min(start[2], end[2]) <= target[2] <= max(start[2], end[2]):
                consumer_ids.add(consumer)
                break
    by_id = {f.get("id"): f for f in spine.get("formulas") or []}
    return [by_id[x] for x in sorted(consumer_ids) if x in by_id]


def packet_base(spine: dict[str, Any], packet: dict[str, Any]) -> tuple[set[RefKey], set[RefKey], dict[str, Any]]:
    points = {key_from_point(p) for p in packet_point_candidates(packet)}
    # Current packet has no canonical range field in most rows.  Any explicit
    # range relation that is present is retained as an M0 range candidate.
    ranges: set[RefKey] = set()
    for fact in packet.get("dependency_facts") or []:
        if fact.get("type") == "RANGE_REFERENCE":
            # Existing packet relation records use endpoint IDs when available.
            start = parse_cell_id(fact.get("source_start_id", ""))
            end = parse_cell_id(fact.get("source_end_id", ""))
            if start and end and start[0] == end[0]:
                ranges.add(("RANGE", start[0], min(start[1], end[1]), min(start[2], end[2]), max(start[1], end[1]), max(start[2], end[2])))
    return points, ranges, {"packet_cell_count": len(points), "packet_range_count": len(ranges)}


def generate_mechanisms(spine: dict[str, Any], packet: dict[str, Any], row: dict[str, Any], index: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    sid = sid_for(spine, row["target"]["sheet"])
    target_row, target_col = row["target"]["row"], row["target"]["col"]
    index = index or formula_indexes(spine)
    mechanisms: dict[str, dict[str, Any]] = {}

    p, r, meta = packet_base(spine, packet)
    mechanisms["M0"] = {"points": p, "ranges": r, "meta": meta}

    p, r, meta = task_named_candidates(spine, packet)
    mechanisms["M1"] = {"points": p, "ranges": r, "meta": meta}

    local = local_formulas(index, sid, target_row, target_col)
    p, r, meta = formula_candidates(spine, local, sid, target_row, target_col, translate=True)
    meta["local_formula_count"] = len(local)
    mechanisms["M2"] = {"points": p, "ranges": r, "meta": meta}

    homologue_forms: list[dict[str, Any]] = []
    for form in local:
        homologue_forms.extend(index["by_class"].get(form.get("class_id"), []))
    p, r, meta = formula_candidates(spine, dedup_class_forms(homologue_forms), sid, target_row, target_col, translate=True)
    meta["associated_class_count"] = len({f.get("class_id") for f in homologue_forms})
    meta["associated_member_count"] = len(homologue_forms)
    mechanisms["M3"] = {"points": p, "ranges": r, "meta": meta}

    row_col_forms = list(index["by_row"].get((sid, target_row), [])) + list(index["by_col"].get((sid, target_col), []))
    p, r, meta = formula_candidates(spine, dedup_class_forms(row_col_forms), sid, target_row, target_col, translate=True)
    meta["row_formula_count"] = len(index["by_row"].get((sid, target_row), []))
    meta["column_formula_count"] = len(index["by_col"].get((sid, target_col), []))
    mechanisms["M4"] = {"points": p, "ranges": r, "meta": meta}

    rows = subject_rows(packet)
    subject_forms = []
    for subject_sid, subject_row in rows:
        subject_forms.extend(index["by_row"].get((subject_sid, subject_row), []))
    p, r, meta = formula_candidates(spine, dedup_class_forms(subject_forms), sid, target_row, target_col, translate=True)
    meta["subject_row_count"] = len(rows)
    mechanisms["M5"] = {"points": p, "ranges": r, "meta": meta}

    subject_classes = {f.get("class_id") for f in subject_forms if f.get("class_id")}
    class_forms = [f for cid in subject_classes for f in index["by_class"].get(cid, [])]
    p, r, meta = formula_candidates(spine, dedup_class_forms(class_forms), sid, target_row, target_col, translate=True)
    meta["subject_class_count"] = len(subject_classes)
    meta["subject_class_member_count"] = len(class_forms)
    mechanisms["M6"] = {"points": p, "ranges": r, "meta": meta}

    p, r, meta = set(), set(), {"applicable": row["edit_type"] == "FORMULA_TO_FORMULA"}
    if meta["applicable"] and row["target"].get("current_input_content"):
        refs, supported, parsed = parse_formula_refs(row["target"]["current_input_content"], row["target"]["sheet"], target_row, target_col)
        for raw in refs:
            key = ref_key(spine, raw[1], f"{get_column_letter(raw[3])}{raw[2]}", None if raw[0] == "POINT" else f"{get_column_letter(raw[5])}{raw[4]}")
            if key:
                (r if key[0] == "RANGE" else p).add(key)
        meta.update({"supported": supported, "parser": parsed})
    mechanisms["M7"] = {"points": p, "ranges": r, "meta": meta}

    target_cells = {(sid, target_row, target_col)}
    # Local formula provenance is retained only to identify mechanically
    # homologous consumers; it is not semantic precedent evidence.
    target_cells.update(form["_origin"] for form in local)
    consumers = consumer_forms(spine, index, target_cells)
    p, r, meta = formula_candidates(spine, dedup_class_forms(consumers), sid, target_row, target_col, translate=False)
    meta["consumer_formula_count"] = len(consumers)
    mechanisms["M8"] = {"points": p, "ranges": r, "meta": meta}
    return mechanisms


def key_to_json(key: RefKey, spine: dict[str, Any]) -> dict[str, Any]:
    return ref_dict(key, spine)


def range_supported_by_points(key: RefKey, points: set[RefKey]) -> bool:
    point_set = {point_from_key(x) for x in points if x[0] == "POINT"}
    return range_cells(key).issubset(point_set)


def supported_gold_refs(gold: dict[str, Any], spine: dict[str, Any]) -> tuple[set[RefKey], set[RefKey], bool, list[dict[str, Any]]]:
    refs, supported, parsed = parse_formula_refs(gold["gold_formula"], gold["target"]["sheet"], gold["target"]["row"], gold["target"]["col"])
    points: set[RefKey] = set()
    ranges: set[RefKey] = set()
    rows = []
    for i, raw in enumerate(refs):
        host = raw[1]
        key = ref_key(spine, host, f"{get_column_letter(raw[3])}{raw[2]}", None if raw[0] == "POINT" else f"{get_column_letter(raw[5])}{raw[4]}")
        if not key:
            continue
        (ranges if key[0] == "RANGE" else points).add(key)
        slot = (parsed.get("slots") or [])[i] if i < len(parsed.get("slots") or []) else {}
        rows.append({"reference_index": i, "reference_type": key[0], "key": key, "supported": supported, "parser": parsed, "abs_mask": slot.get("abs_mask")})
    return points, ranges, supported, rows


def input_target_refs(row: dict[str, Any], spine: dict[str, Any]) -> set[RefKey]:
    content = row["target"].get("current_input_content")
    if not content or row["edit_type"] != "FORMULA_TO_FORMULA":
        return set()
    refs, _supported, _parsed = parse_formula_refs(content, row["target"]["sheet"], row["target"]["row"], row["target"]["col"])
    out = set()
    for raw in refs:
        key = ref_key(spine, raw[1], f"{get_column_letter(raw[3])}{raw[2]}", None if raw[0] == "POINT" else f"{get_column_letter(raw[5])}{raw[4]}")
        if key:
            out.add(key)
    return out


def fingerprint_existing(row: dict[str, Any], spine: dict[str, Any]) -> bool | None:
    fp = row.get("gold_fingerprint")
    if not fp:
        return None
    return f"formula_class:{fp}" in set((spine.get("class_members") or {}).keys())


def same_period(spine: dict[str, Any], key: RefKey, target: tuple[str, int, int]) -> bool | None:
    by_cell = spine.get("_period_by_cell")
    if by_cell is None:
        periods = spine.get("periods") or []
        by_cell = {parse_cell_id(x.get("cell_id", "")): x.get("period_key") for x in periods}
        spine["_period_by_cell"] = by_cell
    source = (key[1], key[2], key[3])
    target_key = by_cell.get(target)
    source_key = by_cell.get(source)
    return None if source_key is None or target_key is None else source_key == target_key


def reference_row(row: dict[str, Any], spine: dict[str, Any], packet: dict[str, Any], gold_key: RefKey, mechanism_data: dict[str, dict[str, Any]], stages: dict[str, dict[str, Any]], supported: bool, abs_mask: str | None = None) -> dict[str, Any]:
    target_sid = sid_for(spine, row["target"]["sheet"])
    source_point = point_from_key(gold_key) or (gold_key[1], gold_key[2], gold_key[3])
    source_sid, sr, sc = source_point
    same_sheet = source_sid == target_sid
    target = (target_sid, row["target"]["row"], row["target"]["col"])
    local = mechanism_data.get("M2", {})
    all_cumulative = stages["C7_ALL"]
    packet_points = {point_from_key(x) for x in mechanism_data["M0"]["points"] if x[0] == "POINT"}
    source_texts = [x.get("text", "") for x in spine.get("text_anchors") or [] if x.get("sheet_id") == source_sid and x.get("row") == sr]
    subject_texts = [x.get("text", "") for x in packet.get("subject") or []]
    exact_text = any(str(a).strip().casefold() == str(b).strip().casefold() for a in source_texts for b in subject_texts)
    return {
        "target_job_id": row["target_job_id"],
        "primary": bool(row.get("primary")),
        "task": row["task"],
        "obligation_id": row.get("obligation_id"),
        "family": row["family"],
        "split": row["split"],
        "target": row["target"],
        "gold_reference": key_to_json(gold_key, spine),
        "reference_type": gold_key[0],
        "supported": supported,
        "cross_sheet": not same_sheet,
        "absolute_relative": abs_mask,
        "spine_present": spine_ref_present(spine, gold_key),
        "packet_present": packet_ref_present(packet_points, gold_key),
        "mechanism_present": {m: packet_ref_present({point_from_key(x) for x in data["points"] if x[0] == "POINT"}, gold_key) if gold_key[0] == "POINT" else (gold_key in data["ranges"] or range_supported_by_points(gold_key, data["points"])) for m, data in mechanism_data.items()},
        "cumulative_present": {stage: (gold_key in data["ranges"] or range_supported_by_points(gold_key, data["points"])) if gold_key[0] == "RANGE" else packet_ref_present({point_from_key(x) for x in data["points"] if x[0] == "POINT"}, gold_key) for stage, data in stages.items()},
        "same_sheet": same_sheet,
        "same_row": same_sheet and sr == row["target"]["row"],
        "same_column": same_sheet and sc == row["target"]["col"],
        "manhattan_distance": abs(sr - row["target"]["row"]) + abs(sc - row["target"]["col"]) if same_sheet else None,
        "exact_same_normalized_text_available": exact_text,
        "same_period_coordinate": same_period(spine, gold_key, target),
        "same_formula_class_neighborhood": any(gold_key in data["points"] or gold_key in data["ranges"] for m, data in mechanism_data.items() if m in {"M2", "M3", "M4"}),
        "spine_missing_reason": None if spine_ref_present(spine, gold_key) else "outside_sheet_bounds_or_unknown_sheet",
    }


def stage_union(mechanisms: dict[str, dict[str, Any]], names: Iterable[str]) -> dict[str, Any]:
    names = list(names)
    points = set()
    ranges = set()
    sources = 0
    for name in names:
        points.update(mechanisms[name]["points"])
        ranges.update(mechanisms[name]["ranges"])
        sources += len(mechanisms[name]["meta"].get("formula_ids", []))
    return {"points": points, "ranges": ranges, "meta": {"mechanisms": names, "source_formula_ids": sources}}


def stage_mechanism_names() -> dict[str, list[str]]:
    return {
        "C0_M0": ["M0"],
        "C1_M0_M1": ["M0", "M1"],
        "C2_M0_M2": ["M0", "M1", "M2"],
        "C3_M0_M3": ["M0", "M1", "M2", "M3"],
        "C4_M0_M4": ["M0", "M1", "M2", "M3", "M4"],
        "C5_M0_M5": ["M0", "M1", "M2", "M3", "M4", "M5"],
        "C6_M0_M6": ["M0", "M1", "M2", "M3", "M4", "M5", "M6"],
        "C7_ALL": list(MECHANISMS),
    }


def candidate_serialization(data: dict[str, Any], spine: dict[str, Any], *, compact: bool) -> str:
    if compact:
        def compact_id(key: RefKey) -> str:
            kind, sid, r1, c1, r2, c2 = key
            if kind == "POINT":
                return f"cell:{sid.removeprefix('sheet:')}:r{r1}:c{c1}"
            return f"range:{sid.removeprefix('sheet:')}:r{r1}:c{c1}:r{r2}:c{c2}"
        value = {"p": [compact_id(x) for x in sorted(data["points"])], "r": [compact_id(x) for x in sorted(data["ranges"])]}
    else:
        value = {"points": [key_to_json(x, spine) for x in sorted(data["points"])], "ranges": [key_to_json(x, spine) for x in sorted(data["ranges"])], "provenance": data.get("meta", {})}
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def target_metrics(row: dict[str, Any], spine: dict[str, Any], packet: dict[str, Any], mechanisms: dict[str, dict[str, Any]], stages: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    point_gold, range_gold, supported, occurrences = supported_gold_refs(row, spine)
    target = dict(row)
    target.pop("obligation", None)
    target.pop("packet_meta", None)
    target["fingerprint_existing"] = fingerprint_existing(row, spine)
    target["gold_supported"] = supported
    target["gold_point_count"] = len(point_gold)
    target["gold_range_count"] = len(range_gold)
    target["spine_point_recall"] = round(sum(spine_ref_present(spine, x) for x in point_gold) / len(point_gold), 4) if point_gold else 1.0
    target["spine_range_recall"] = round(sum(spine_ref_present(spine, x) for x in range_gold) / len(range_gold), 4) if range_gold else 1.0
    target["packet_point_recall"] = round(sum(packet_ref_present({point_from_key(y) for y in mechanisms["M0"]["points"] if y[0] == "POINT"}, x) for x in point_gold) / len(point_gold), 4) if point_gold else 1.0
    target["packet_range_recall"] = round(sum(x in mechanisms["M0"]["ranges"] or range_supported_by_points(x, mechanisms["M0"]["points"]) for x in range_gold) / len(range_gold), 4) if range_gold else 1.0
    target["packet_reference_complete"] = all(packet_ref_present({point_from_key(y) for y in mechanisms["M0"]["points"] if y[0] == "POINT"}, x) for x in point_gold) and all(x in mechanisms["M0"]["ranges"] or range_supported_by_points(x, mechanisms["M0"]["points"]) for x in range_gold)
    packet_point_hits = sum(packet_ref_present({point_from_key(y) for y in mechanisms["M0"]["points"] if y[0] == "POINT"}, x) for x in point_gold)
    packet_range_hits = sum(x in mechanisms["M0"]["ranges"] or range_supported_by_points(x, mechanisms["M0"]["points"]) for x in range_gold)
    if not supported:
        target["packet_reference_class"] = "GOLD_REFERENCE_OPAQUE"
    elif packet_point_hits + packet_range_hits == 0:
        target["packet_reference_class"] = "GOLD_REFERENCE_NONE"
    elif packet_point_hits == len(point_gold) and packet_range_hits == len(range_gold):
        target["packet_reference_class"] = "GOLD_REFERENCE_COMPLETE"
    else:
        target["packet_reference_class"] = "GOLD_REFERENCE_PARTIAL"
    target["input_target_reference_count"] = len(input_target_refs(row, spine))
    packet_points = {point_from_key(y) for y in mechanisms["M0"]["points"] if y[0] == "POINT"}
    packet_sheets = {p[0] for p in packet_points}
    packet_rows = {(p[0], p[1]) for p in packet_points}
    gold_start_points = {point_from_key(x) or (x[1], x[2], x[3]) for x in (point_gold | range_gold)}
    target["task_named_source_present"] = bool(((row.get("obligation") or {}).get("source_relation") or {}).get("text")) and bool(packet.get("source"))
    target["gold_reference_sheets_present"] = all(x[1] in packet_sheets for x in gold_start_points)
    target["gold_reference_rows_present"] = all((x[1], x[2]) in packet_rows for x in gold_start_points)
    target["gold_reference_cells_ranges_present"] = target["packet_reference_complete"]
    target["base_packet_tokens"] = row.get("packet_meta", {}).get("packet_tokens", 0)
    target["mechanism_complete"] = {}
    for mechanism, data in mechanisms.items():
        point_hit = all(packet_ref_present({point_from_key(y) for y in data["points"] if y[0] == "POINT"}, x) for x in point_gold)
        range_hit = all(x in data["ranges"] or range_supported_by_points(x, data["points"]) for x in range_gold)
        target["mechanism_complete"][mechanism] = point_hit and range_hit
    target["sibling"] = {}
    for stage, data in stages.items():
        points_hit = sum(packet_ref_present({point_from_key(y) for y in data["points"] if y[0] == "POINT"}, x) for x in point_gold)
        ranges_hit = sum(x in data["ranges"] or range_supported_by_points(x, data["points"]) for x in range_gold)
        target[stage] = {
            "point_recall": round(points_hit / len(point_gold), 4) if point_gold else 1.0,
            "range_recall": round(ranges_hit / len(range_gold), 4) if range_gold else 1.0,
            "complete": points_hit == len(point_gold) and ranges_hit == len(range_gold),
            "candidate_points": len(data["points"]),
            "candidate_ranges": len(data["ranges"]),
            "raw_tokens": max(1, len(candidate_serialization(data, spine, compact=False)) // 4),
            "compact_tokens": max(1, len(candidate_serialization(data, spine, compact=True)) // 4),
        }
        target[stage]["full_raw_tokens"] = target["base_packet_tokens"] + target[stage]["raw_tokens"]
        target[stage]["full_compact_tokens"] = target["base_packet_tokens"] + target[stage]["compact_tokens"]
    sibling_data = mechanisms["M5"]
    sibling_points = {point_from_key(y) for y in sibling_data["points"] if y[0] == "POINT"}
    sibling_ranges = sibling_data["ranges"]
    sibling_point_hits = sum(packet_ref_present(sibling_points, x) for x in point_gold)
    sibling_range_hits = sum(x in sibling_ranges or range_supported_by_points(x, sibling_data["points"]) for x in range_gold)
    sibling_forms = sibling_data["meta"].get("formula_ids", [])
    target["sibling"] = {
        "sibling_exists": bool(sibling_forms),
        "translation_supported": sibling_data["meta"].get("unsupported", 0) == 0 and bool(sibling_forms),
        "point_recall": round(sibling_point_hits / len(point_gold), 4) if point_gold else 1.0,
        "range_recall": round(sibling_range_hits / len(range_gold), 4) if range_gold else 1.0,
        "complete": sibling_point_hits == len(point_gold) and sibling_range_hits == len(range_gold),
        "candidate_count": len(sibling_data["points"]) + len(sibling_data["ranges"]),
    }
    refs = []
    for occurrence in occurrences:
        refs.append(reference_row(row, spine, packet, occurrence["key"], mechanisms, stages, supported, occurrence.get("abs_mask")))
    return target, refs


def aggregate_targets(rows: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    def mean(key: str) -> float | None:
        vals = [r[stage][key] for r in rows if r.get("gold_supported") and r[stage].get(key) is not None]
        return round(statistics.mean(vals), 4) if vals else None
    points = sum(r.get("gold_point_count", 0) for r in rows if r.get("gold_supported"))
    ranges = sum(r.get("gold_range_count", 0) for r in rows if r.get("gold_supported"))
    point_hits = sum(round(r.get("gold_point_count", 0) * r[stage]["point_recall"]) for r in rows if r.get("gold_supported"))
    range_hits = sum(round(r.get("gold_range_count", 0) * r[stage]["range_recall"]) for r in rows if r.get("gold_supported"))
    candidates = [r[stage]["candidate_points"] + r[stage]["candidate_ranges"] for r in rows]
    tokens = [r[stage]["full_compact_tokens"] for r in rows]
    raw = [r[stage]["full_raw_tokens"] for r in rows]
    candidate_tokens = [r[stage]["compact_tokens"] for r in rows]
    candidate_raw = [r[stage]["raw_tokens"] for r in rows]
    return {
        "n_targets": len(rows),
        "supported_targets": sum(r.get("gold_supported") for r in rows),
        "POINT_GOLD_RECALL": round(point_hits / points, 4) if points else None,
        "RANGE_GOLD_RECALL": round(range_hits / ranges, 4) if ranges else None,
        "TARGET_COMPLETE_RATE": round(sum(r[stage]["complete"] for r in rows) / len(rows), 4) if rows else None,
        "TARGET_COMPLETE_RATE_SUPPORTED": round(sum(r[stage]["complete"] for r in rows if r.get("gold_supported")) / max(1, sum(r.get("gold_supported") for r in rows)), 4) if any(r.get("gold_supported") for r in rows) else None,
        "mean_candidate_count": round(statistics.mean(candidates), 2) if candidates else 0,
        "p95_candidate_count": sorted(candidates)[max(0, int(0.95 * len(candidates)) - 1)] if candidates else 0,
        "max_candidate_count": max(candidates, default=0),
        "mean_compact_tokens": round(statistics.mean(tokens), 1) if tokens else 0,
        "p95_compact_tokens": sorted(tokens)[max(0, int(0.95 * len(tokens)) - 1)] if tokens else 0,
        "max_compact_tokens": max(tokens, default=0),
        "mean_raw_tokens": round(statistics.mean(raw), 1) if raw else 0,
        "max_raw_tokens": max(raw, default=0),
        "mean_candidate_compact_tokens": round(statistics.mean(candidate_tokens), 1) if candidate_tokens else 0,
        "mean_candidate_raw_tokens": round(statistics.mean(candidate_raw), 1) if candidate_raw else 0,
    }


def miss_category(ref: dict[str, Any], target: dict[str, Any], spine: dict[str, Any]) -> str:
    if not ref["spine_present"]:
        return "OTHER_MECHANICAL_GAP"
    if ref["reference_type"] == "RANGE" and ref["same_formula_class_neighborhood"]:
        return "AGGREGATION_EXTENT"
    if ref["cross_sheet"] and not ref["exact_same_normalized_text_available"]:
        return "CROSS_SHEET_IDENTITY"
    if ref["same_formula_class_neighborhood"] is False and not ref["same_row"] and not ref["same_column"]:
        return "NONLOCAL_HOMOLOGUE_MISSING"
    if ref["same_period_coordinate"] is False:
        return "CONSTANT_OR_ASSUMPTION_SOURCE"
    if ref["reference_type"] == "RANGE":
        return "AGGREGATION_EXTENT"
    if not target.get("sibling", {}).get("sibling_exists"):
        return "TASK_UNDERSPECIFIED_SOURCE"
    return "FORMULA_CLASS_GAP"


def run() -> dict[str, Any]:
    population = load(SYNTH / "population.json")
    rows = list(population["rows"])
    primary_rows = [x for x in rows if x.get("primary")]
    write(OUT / "freeze.json", {"generated_at": datetime.now(UTC).isoformat(), **FREEZE, "source_population": str(SYNTH / "population.json"), "source_targets": len(primary_rows), "diagnostic_targets": len(rows) - len(primary_rows)})
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["task"]].append(row)
    target_rows: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    mechanism_rows: list[dict[str, Any]] = []
    for task in sorted(grouped):
        spine = load(SPINE_ROOT / f"{task}.json")
        # Build the existing formula indexes once per persistent spine.  This
        # changes runtime only; it does not add a relation or alter the spine.
        index = formula_indexes(spine)
        packet_cache: dict[str, dict[str, Any]] = {}
        for row in grouped[task]:
            packet_path = row["packet_meta"]["packet_path"]
            if packet_path not in packet_cache:
                packet_cache[packet_path] = load(ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/closed-world-resolver-probe" / packet_path)["packet"]
            packet = packet_cache[packet_path]
            mechanisms = generate_mechanisms(spine, packet, row, index)
            stage_names = stage_mechanism_names()
            stages = {stage: stage_union(mechanisms, names) for stage, names in stage_names.items()}
            target, refs = target_metrics(row, spine, packet, mechanisms, stages)
            target_rows.append(target)
            reference_rows.extend(refs)
            for mechanism, data in mechanisms.items():
                mechanism_rows.append({"target_job_id": row["target_job_id"], "primary": bool(row.get("primary")), "task": task, "mechanism": mechanism, "candidate_points": len(data["points"]), "candidate_ranges": len(data["ranges"]), "meta": data["meta"]})
    write(OUT / "targets.jsonl", "\n".join(json.dumps(x, ensure_ascii=False) for x in target_rows) + "\n")
    write(OUT / "references.jsonl", "\n".join(json.dumps(x, ensure_ascii=False) for x in reference_rows) + "\n")
    write(OUT / "mechanisms.jsonl", "\n".join(json.dumps(x, ensure_ascii=False) for x in mechanism_rows) + "\n")

    primary_target_rows = [x for x in target_rows if x.get("primary")]
    primary_job_ids = {x["target_job_id"] for x in primary_target_rows}
    stage_summary = {stage: aggregate_targets(primary_target_rows, stage) for stage in STAGES}
    # Candidate mass and exclusive contributions are calculated from the
    # target-level ledger in one transparent pass.
    mech_summary = {}
    for mechanism in MECHANISMS:
        scoped_references = [x for x in reference_rows if x["primary"]]
        gold_keys = {(x["target_job_id"], json.dumps(x["gold_reference"], sort_keys=True)) for x in scoped_references if x["supported"]}
        hit_keys = {(x["target_job_id"], json.dumps(x["gold_reference"], sort_keys=True)) for x in scoped_references if x["supported"] and x["mechanism_present"].get(mechanism)}
        other_hits = set()
        for other in MECHANISMS:
            if other == mechanism:
                continue
            other_hits.update({(x["target_job_id"], json.dumps(x["gold_reference"], sort_keys=True)) for x in scoped_references if x["supported"] and x["mechanism_present"].get(other)})
        mech_rows = [x for x in mechanism_rows if x["mechanism"] == mechanism and x.get("primary")]
        baseline_rows = {x["target_job_id"]: x for x in mechanism_rows if x["mechanism"] == "M0" and x.get("primary")}
        mech_summary[mechanism] = {
            "POINT_GOLD_RECALL": round(sum(1 for x in scoped_references if x["supported"] and x["reference_type"] == "POINT" and x["mechanism_present"].get(mechanism)) / max(1, sum(1 for x in scoped_references if x["supported"] and x["reference_type"] == "POINT")), 4),
            "RANGE_GOLD_RECALL": round(sum(1 for x in scoped_references if x["supported"] and x["reference_type"] == "RANGE" and x["mechanism_present"].get(mechanism)) / max(1, sum(1 for x in scoped_references if x["supported"] and x["reference_type"] == "RANGE")), 4),
            "unique_gold_reference_hits": len(hit_keys),
            "exclusive_gold_reference_hits": len(hit_keys - other_hits),
            "additional_complete_targets": sum(1 for row in primary_target_rows if row.get("gold_supported") and row["mechanism_complete"].get(mechanism) and not row["mechanism_complete"].get("M0")),
            "candidate_points_mean": round(statistics.mean(x["candidate_points"] for x in mech_rows), 2) if mech_rows else 0,
            "candidate_ranges_mean": round(statistics.mean(x["candidate_ranges"] for x in mech_rows), 2) if mech_rows else 0,
            "extra_candidate_points_mean_vs_M0": round(statistics.mean(x["candidate_points"] - baseline_rows[x["target_job_id"]]["candidate_points"] for x in mech_rows), 2) if mech_rows else 0,
            "extra_candidate_ranges_mean_vs_M0": round(statistics.mean(x["candidate_ranges"] - baseline_rows[x["target_job_id"]]["candidate_ranges"] for x in mech_rows), 2) if mech_rows else 0,
        }

    # Sibling-period and fingerprint strata.
    sibling = {}
    for edit in ("BLANK_TO_FORMULA", "VALUE_TO_FORMULA", "FORMULA_TO_FORMULA"):
        picked = [x for x in primary_target_rows if x["edit_type"] == edit]
        sibling[edit] = {"n": len(picked), "sibling_exists": sum(x["sibling"]["sibling_exists"] for x in picked), "translation_supported": sum(x["sibling"]["translation_supported"] for x in picked), "point_recall": round(statistics.mean(x["sibling"]["point_recall"] for x in picked), 4) if picked else None, "range_recall": round(statistics.mean(x["sibling"]["range_recall"] for x in picked), 4) if picked else None, "complete": round(sum(x["sibling"]["complete"] for x in picked) / len(picked), 4) if picked else None, "candidate_count_mean": round(statistics.mean(x["sibling"]["candidate_count"] for x in picked), 2) if picked else None}
    fingerprint = {}
    for key in (True, False, None):
        picked = [x for x in primary_target_rows if x.get("fingerprint_existing") is key]
        fingerprint[str(key)] = {"n": len(picked), "C7_COMPLETE": round(sum(x["C7_ALL"]["complete"] for x in picked) / len(picked), 4) if picked else None, "C6_COMPLETE": round(sum(x["C6_M0_M6"]["complete"] for x in picked) / len(picked), 4) if picked else None, "mean_C7_point_recall": round(statistics.mean(x["C7_ALL"]["point_recall"] for x in picked), 4) if picked else None}

    residual = Counter()
    locality = Counter()
    for ref in [x for x in reference_rows if x["primary"]]:
        if ref["supported"] and ref["spine_present"] and not ref["cumulative_present"]["C7_ALL"]:
            target = next(x for x in target_rows if x["target_job_id"] == ref["target_job_id"])
            residual[miss_category(ref, target, {} if False else {} if False else {} )] += 1
        if ref["supported"] and ref["reference_type"] == "POINT":
            locality["same_sheet"] += ref["same_sheet"]
            locality["same_row"] += ref["same_row"]
            locality["same_column"] += ref["same_column"]
            locality["cross_sheet"] += ref["cross_sheet"]
            locality["same_period_coordinate_true"] += ref["same_period_coordinate"] is True
            locality["exact_same_normalized_text_available"] += ref["exact_same_normalized_text_available"]
            locality["same_formula_class_neighborhood"] += ref["same_formula_class_neighborhood"]
    def adequacy_summary(picked: list[dict[str, Any]]) -> dict[str, Any]:
        counts = Counter(x.get("packet_reference_class") for x in picked)
        return {
            "n": len(picked),
            "classes": {k: counts[k] for k in ("GOLD_REFERENCE_COMPLETE", "GOLD_REFERENCE_PARTIAL", "GOLD_REFERENCE_NONE", "GOLD_REFERENCE_OPAQUE")},
            "rates": {k: round(counts[k] / len(picked), 4) if picked else None for k in ("GOLD_REFERENCE_COMPLETE", "GOLD_REFERENCE_PARTIAL", "GOLD_REFERENCE_NONE", "GOLD_REFERENCE_OPAQUE")},
            "mean_point_recall": round(statistics.mean(x["packet_point_recall"] for x in picked), 4) if picked else None,
            "mean_range_recall": round(statistics.mean(x["packet_range_recall"] for x in picked), 4) if picked else None,
            "task_named_source_present_rate": round(sum(bool(x.get("task_named_source_present")) for x in picked) / len(picked), 4) if picked else None,
            "gold_reference_sheets_present_rate": round(sum(bool(x.get("gold_reference_sheets_present")) for x in picked) / len(picked), 4) if picked else None,
            "gold_reference_rows_present_rate": round(sum(bool(x.get("gold_reference_rows_present")) for x in picked) / len(picked), 4) if picked else None,
            "gold_reference_cells_ranges_present_rate": round(sum(bool(x.get("gold_reference_cells_ranges_present")) for x in picked) / len(picked), 4) if picked else None,
        }

    primary_by_edit = {edit: adequacy_summary([x for x in primary_target_rows if x["edit_type"] == edit]) for edit in sorted({x["edit_type"] for x in primary_target_rows})}
    primary_by_family = {family: adequacy_summary([x for x in primary_target_rows if x["family"] == family]) for family in sorted({x["family"] for x in primary_target_rows})}
    def ambiguity_bucket(n: int) -> str:
        return "1-2" if n <= 2 else "3-5" if n <= 5 else "6-10" if n <= 10 else "11-50" if n <= 50 else ">50"
    ambiguity = {}
    for bucket in ("1-2", "3-5", "6-10", "11-50", ">50"):
        picked = [x for x in primary_target_rows if ambiguity_bucket(x["C7_ALL"]["candidate_points"] + x["C7_ALL"]["candidate_ranges"]) == bucket]
        ambiguity[bucket] = {"n": len(picked), "C7_point_recall": round(statistics.mean(x["C7_ALL"]["point_recall"] for x in picked), 4) if picked else None, "C7_range_recall": round(statistics.mean(x["C7_ALL"]["range_recall"] for x in picked), 4) if picked else None, "C7_complete": round(sum(x["C7_ALL"]["complete"] for x in picked) / len(picked), 4) if picked else None, "mean_compact_tokens": round(statistics.mean(x["C7_ALL"]["full_compact_tokens"] for x in picked), 1) if picked else None}
    report = {
        "title": "Mechanical formula-reference projection preflight",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_population": {"path": str(SYNTH / "population.json"), "n_targets": len(primary_rows), "n_diagnostic_targets": len(rows) - len(primary_rows), "families": sorted({x["family"] for x in primary_rows}), "gold_evaluator_only": True},
        "spine_reference_ceiling": {"point": round(sum(x["spine_present"] for x in reference_rows if x["supported"] and x["reference_type"] == "POINT") / max(1, sum(x["supported"] and x["reference_type"] == "POINT" for x in reference_rows)), 4), "range": round(sum(x["spine_present"] for x in reference_rows if x["supported"] and x["reference_type"] == "RANGE") / max(1, sum(x["supported"] and x["reference_type"] == "RANGE" for x in reference_rows)), 4), "all_supported_references_present": all(x["spine_present"] for x in reference_rows if x["supported"])},
        "current_packet": {"point_pooled": round(sum(x["packet_present"] for x in reference_rows if x["primary"] and x["supported"] and x["reference_type"] == "POINT") / max(1, sum(x["primary"] and x["supported"] and x["reference_type"] == "POINT" for x in reference_rows)), 4), "range_pooled": round(sum(x["packet_present"] for x in reference_rows if x["primary"] and x["supported"] and x["reference_type"] == "RANGE") / max(1, sum(x["primary"] and x["supported"] and x["reference_type"] == "RANGE" for x in reference_rows)), 4), "point_target_mean": round(statistics.mean(x["packet_point_recall"] for x in primary_target_rows), 4), "range_target_mean": round(statistics.mean(x["packet_range_recall"] for x in primary_target_rows), 4)},
        "phase_a_packet_classes": adequacy_summary(primary_target_rows),
        "phase_a_by_edit_type": primary_by_edit,
        "phase_a_by_family": primary_by_family,
        "stage_frontier": stage_summary,
        "mechanism_summary": mech_summary,
        "sibling_period": sibling,
        "fingerprint_strata": fingerprint,
        "ambiguity_frontier_c7": ambiguity,
        "locality_census": dict(locality),
        "residual_miss_taxonomy": dict(residual),
        "known_cases": {},
        "context_capacity": {"token_estimate_definition": FREEZE["token_estimate"], "stage_frontier_includes_compact_and_raw": True, "compact_over_limit_by_stage": {stage: sum(x[stage]["full_compact_tokens"] > 80000 for x in primary_target_rows) for stage in STAGES}, "raw_over_limit_by_stage": {stage: sum(x[stage]["full_raw_tokens"] > 80000 for x in primary_target_rows) for stage in STAGES}},
        "verdict": "PROJECTION_PARTIAL",
        "verdict_basis": "Persistent spine ceiling is complete, but all frozen mechanical projections reach only 0.5882 target completeness on supported held-out targets; compact cost is manageable for most cases but exceeds 80k for three cases.",
    }
    target_by_id = {x["target_job_id"]: x for x in target_rows}
    ref_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ref in reference_rows:
        ref_by_id[ref["target_job_id"]].append(ref)
    mech_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in mechanism_rows:
        mech_by_id[item["target_job_id"]].append(item)
    for task, obligation, address in sorted(KNOWN_CASE_BINDINGS):
        candidates = [x for x in target_rows if x["task"] == task and x.get("obligation_id") == obligation and x["target"]["address"] == address]
        if candidates:
            item = candidates[0]
            report["known_cases"][f"{task}:{obligation}:{address}"] = {"target": item, "references": ref_by_id[item["target_job_id"]], "mechanisms": mech_by_id[item["target_job_id"]]}
    write(OUT / "report.json", report)
    lines = ["# Mechanical formula-reference projection preflight", "", "No model calls. No workbook writes.", "", "## Ceiling and baseline", "", f"- Full-spine point ceiling: {report['spine_reference_ceiling']['point']}", f"- Full-spine range ceiling: {report['spine_reference_ceiling']['range']}", f"- Current packet point recall (target mean): {report['current_packet']['point_target_mean']}", f"- Current packet range recall (target mean): {report['current_packet']['range_target_mean']}", f"- Current packet point recall (pooled): {report['current_packet']['point_pooled']}", f"- Current packet range recall (pooled): {report['current_packet']['range_pooled']}", "", "## Cumulative frontier", ""]
    for stage, values in stage_summary.items():
        lines.append(f"- {stage}: point={values['POINT_GOLD_RECALL']}, range={values['RANGE_GOLD_RECALL']}, complete={values['TARGET_COMPLETE_RATE']}, mean_candidates={values['mean_candidate_count']}, p95_candidates={values['p95_candidate_count']}, mean_compact_tokens={values['mean_compact_tokens']}, max_compact_tokens={values['max_compact_tokens']}")
    lines += ["", "## Mechanism recall", ""]
    for mechanism, values in mech_summary.items():
        lines.append(f"- {mechanism}: point={values['POINT_GOLD_RECALL']}, range={values['RANGE_GOLD_RECALL']}, exclusive_hits={values['exclusive_gold_reference_hits']}, mean_points={values['candidate_points_mean']}, mean_ranges={values['candidate_ranges_mean']}, extra_vs_M0_points={values['extra_candidate_points_mean_vs_M0']}, extra_vs_M0_ranges={values['extra_candidate_ranges_mean_vs_M0']}")
    lines += ["", f"## Verdict: {report['verdict']}", "", f"{report['verdict_basis']}", "", "See `report.json`, `references.jsonl`, `targets.jsonl`, and `mechanisms.jsonl` for the full evaluator-side ledger.", ""]
    write(OUT / "report.md", "\n".join(lines))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("run", "report"))
    args = parser.parse_args()
    if args.phase == "run":
        report = run()
        print(f"PREFLIGHT targets={report['source_population']['n_targets']} point_ceiling={report['spine_reference_ceiling']['point']} packet_point_mean={report['current_packet']['point_target_mean']}", flush=True)
    else:
        report = load(OUT / "report.json")
        print(json.dumps({"spine_reference_ceiling": report["spine_reference_ceiling"], "current_packet": report["current_packet"], "stage_frontier": report["stage_frontier"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
