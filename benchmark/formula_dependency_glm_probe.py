#!/usr/bin/env python3
"""Controlled GLM-5.3-Flash probe: local blank classification with injected point deps.

This is a capability-localization experiment, not a SpreadsheetBench run.

Phases:
  select  — freeze a balanced 36-cell set and packets (goldens for construction only)
  run     — 108 independent OpenRouter calls (C0/C1/C2), optional ORACLE_WHERE
  score   — classification, paired transitions, rationale tags, report
  all     — select, then run, then score

Does not modify LibreCalc, workbooks, the official scorer, or the spreadsheet harness.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from fingerprint import a1_address, formula_text, relative_fingerprint  # noqa: E402
from formula_dependency_selection import blank_edge_types, build_graph  # noqa: E402
from formula_dependency_selection_probe import (  # noqa: E402
    _blank,
    _blank_formula_targets,
    _cell_map,
    _golden_path,
    _input_path,
    _label,
    _load_slice,
    _task_list,
)
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402

SLICE_12 = ROOT / "benchmark/slices/fm-target-selection-probe-12.json"
SLICE_36 = ROOT / "benchmark/slices/fm-dependency-glm-probe-36.json"
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-dependency-glm-probe"
)
ENV_FILE = ROOT / ".env"

MODEL = "z-ai/glm-5.3-flash"
REASONING_EFFORT = "low"
TEMPERATURE = 0.0
SEED = 20260906
CONTEXT_RADIUS = 3
CONSUMER_CAP = 12
MAX_PER_BOOK = 2
CELLS_PER_STRATUM = 12
TRUE_PER_STRATUM = 6
INTENTIONAL_PER_STRATUM = 6
STRATA = ("SAME_SHEET_ONLY", "CROSS_SHEET_ONLY", "BOTH")
CONDITIONS = ("C0", "C1", "C2")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CELL_WIDTH = 22

SLICE_LABEL = "BALANCED DIAGNOSTIC CLASSIFICATION SET"
SLICE_NOT = "NOT A PREVALENCE OR BENCHMARK ESTIMATE"

SYSTEM_CLASSIFY = """\
You classify one already-identified blank spreadsheet cell.
The cell location is supplied. Do not search for other candidate cells.
Decide exactly one of:
  MISSING_FORMULA
  INTENTIONAL_BLANK
Return JSON only, with keys:
  "label": one of those two strings
  "probability_missing_formula": number from 0.00 to 1.00
  "reason": one or two concise sentences
Do not propose a formula.
Do not discuss cells other than the supplied target except as evidence about that target.
"""

SYSTEM_ORACLE = """\
You infer one spreadsheet formula for an already-identified cell.
This cell is known to require a formula. Do not decide whether it should be blank.
Return JSON only, with keys:
  "formula": an Excel/LibreOffice formula starting with =
  "reason": one or two concise sentences
"""

QUESTION_C0 = (
    "Based on the task and local workbook context, is this blank missing a "
    "formula or intentionally blank?"
)
QUESTION_C1 = (
    "Based on the task, local workbook context, and the mechanically extracted "
    "explicit formula references, is this blank missing a formula or intentionally blank?"
)
QUESTION_C2 = (
    "Based on the task, local workbook context, and the listed direct point-consumer "
    "formulas, is this blank missing a formula or intentionally blank?"
)

DEPENDENCY_PREFACE = (
    "These are mechanically extracted explicit formula references to this cell."
)

FORBIDDEN_PROBE_TERMS = (
    "suspicious",
    "likely missing",
    "anomaly",
    "recommended fix",
    "recommended",
    "confidence",
    "enriched",
    "predictive",
    "84%",
    "0.84",
    "unusual",
    "important",
    "benchmark statistics",
    "target precision",
)

LOCAL_WORDS = (
    "header",
    "label",
    "row",
    "column",
    "adjacent",
    "neighbor",
    "nearby",
    "table",
    "layout",
    "forecast",
    "total",
    "margin",
    "above",
    "below",
    "left",
    "right",
    "context",
    "next to",
    "structure",
    "pattern",
    "year",
    "same row",
    "same column",
)
DEP_WORDS = (
    "consumer",
    "consumed",
    "referenced",
    "referenced by",
    "references this",
    "reference to this",
    "depend",
    "downstream",
    "points to this",
    "uses this cell",
    "formula references",
    "cross-sheet",
    "cross sheet",
    "same-sheet",
    "same sheet",
    "other sheet",
    "another sheet",
    "point consumer",
    "explicit formula reference",
)
FORMULA_WORDS = (
    "consumer formula",
    "source formula",
    "the formula",
    "formula =",
    "computes",
    "links",
    "adds",
    "sums",
    "multiplies",
)
ZERO_WORDS = (
    "zero",
    "as 0",
    "as zero",
    "default",
    "unused",
    "optional",
    "placeholder",
    "empty means",
    "intentionally empty",
    "not needed",
    "no input",
)
GUESS_WORDS = (
    "unclear",
    "guess",
    "maybe",
    "no evidence",
    "cannot tell",
    "not enough",
    "insufficient",
    "hard to say",
    "unknown",
)


def even_space(items: list[Any], k: int) -> list[Any]:
    items = list(items)
    if k <= 0:
        return []
    if k >= len(items):
        return items
    if k == 1:
        return [items[0]]
    return [items[round(i * (len(items) - 1) / (k - 1))] for i in range(k)]


def point_stratum(info: dict[str, Any]) -> str | None:
    if not info.get("n_point"):
        return None
    same = bool(info.get("point_same_sheet"))
    cross = bool(info.get("point_cross_sheet"))
    if same and cross:
        return "BOTH"
    if cross:
        return "CROSS_SHEET_ONLY"
    if same:
        return "SAME_SHEET_ONLY"
    return None


def cell_id(task_id: str, sheet: str, col: int, row: int) -> str:
    return f"{task_id}:{sheet}!{a1_address(col, row)}"


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _display_value(value: object, *, is_target: bool) -> str:
    if is_target:
        return "TARGET [BLANK]"
    text = formula_text(value)
    if text:
        return text
    if value is None:
        return "(blank)"
    if isinstance(value, str):
        return "(blank)" if not value.strip() else value.replace("\n", " ")
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e12:
            return str(int(value))
        return f"{value:.8g}"
    return str(value)


def _clip(text: str, width: int = CELL_WIDTH) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def extract_window(ws, col: int, row: int, radius: int = CONTEXT_RADIUS) -> dict[str, Any]:
    # Used-range is not a hard boundary: referenced blanks often sit past the last
    # stored cell. Always keep the target inside the window; clip only at A1 / Excel limits.
    excel_max_col = 16384
    excel_max_row = 1_048_576
    used_max_col = max(int(ws.max_column or 1), 1)
    used_max_row = max(int(ws.max_row or 1), 1)
    requested = [col - radius, row - radius, col + radius, row + radius]
    c1 = max(1, col - radius)
    r1 = max(1, row - radius)
    c2 = min(excel_max_col, col + radius)
    r2 = min(excel_max_row, row + radius)
    cells: list[dict[str, Any]] = []
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            value = ws.cell(r, c).value
            cells.append(
                {
                    "col": c,
                    "row": r,
                    "address": a1_address(c, r),
                    "is_target": c == col and r == row,
                    "display": _display_value(value, is_target=(c == col and r == row)),
                }
            )
    merges: list[dict[str, Any]] = []
    for merged in ws.merged_cells.ranges:
        if merged.max_col < c1 or merged.min_col > c2 or merged.max_row < r1 or merged.min_row > r2:
            continue
        origin_in = c1 <= merged.min_col <= c2 and r1 <= merged.min_row <= r2
        clipped = (
            merged.min_col < c1
            or merged.min_row < r1
            or merged.max_col > c2
            or merged.max_row > r2
        )
        merges.append(
            {
                "range": str(merged),
                "origin_in_window": origin_in,
                "clipped": clipped,
            }
        )
    return {
        "sheet": ws.title,
        "target_col": col,
        "target_row": row,
        "radius": radius,
        "requested": requested,
        "used": [c1, r1, c2, r2],
        "clipped_left": col - radius < 1,
        "clipped_top": row - radius < 1,
        "clipped_right": col + radius > excel_max_col,
        "clipped_bottom": row + radius > excel_max_row,
        "beyond_used_range": c2 > used_max_col or r2 > used_max_row,
        "sheet_max_column": used_max_col,
        "sheet_max_row": used_max_row,
        "merged": merges,
        "cells": cells,
    }


def render_window(window: dict[str, Any]) -> str:
    c1, r1, c2, r2 = window["used"]
    by_pos = {(item["col"], item["row"]): item["display"] for item in window["cells"]}
    cols = list(range(c1, c2 + 1))
    header = "row".ljust(6) + "".join(a1_address(c, 1)[:-1].rjust(CELL_WIDTH + 1) for c in cols)
    lines = [header, "-" * len(header)]
    for r in range(r1, r2 + 1):
        row = str(r).ljust(6)
        for c in cols:
            row += _clip(by_pos.get((c, r), "(blank)")).rjust(CELL_WIDTH) + " "
        lines.append(row.rstrip())
    clip_bits = []
    for name in ("clipped_left", "clipped_top", "clipped_right", "clipped_bottom"):
        if window[name]:
            clip_bits.append(name)
    if window.get("beyond_used_range"):
        clip_bits.append("beyond_used_range")
    if window["merged"]:
        clip_bits.append(f"merged_intersects={len(window['merged'])}")
        for item in window["merged"]:
            extra = "clipped" if item["clipped"] else "fully_inside"
            clip_bits.append(f"{item['range']}({extra})")
    if not clip_bits:
        clip_bits.append("none")
    lines.append("clipping: " + "; ".join(clip_bits))
    return "\n".join(lines)


def point_consumers(graph, key: tuple[str, int, int], cap: int = CONSUMER_CAP) -> dict[str, Any]:
    seen: set[tuple[str, int, int]] = set()
    rows: list[dict[str, Any]] = []
    for formula_key, _slot in graph.point_rev.get(key) or []:
        if formula_key in seen:
            continue
        seen.add(formula_key)
        node = graph.formulas[formula_key]
        sheet, col, row = formula_key
        rows.append(
            {
                "sheet": sheet,
                "col": col,
                "row": row,
                "address": a1_address(col, row),
                "formula": node.formula,
                "eq_id": node.eq_id,
                "relation": "cross-sheet" if sheet != key[0] else "same-sheet",
            }
        )
    rows.sort(key=lambda item: (item["sheet"], item["col"], item["row"]))
    n_same = sum(1 for item in rows if item["relation"] == "same-sheet")
    n_cross = sum(1 for item in rows if item["relation"] == "cross-sheet")
    classes = []
    class_map: dict[str, str] = {}
    for item in rows:
        if item["eq_id"] not in class_map:
            class_map[item["eq_id"]] = f"EQ{len(class_map) + 1:02d}"
            classes.append(item["eq_id"])
        item["consumer_class_id"] = class_map[item["eq_id"]]
    listed = rows[:cap]
    return {
        "all": rows,
        "listed": listed,
        "n_point": len(rows),
        "n_point_same": n_same,
        "n_point_cross": n_cross,
        "n_point_eq": len(classes),
        "truncated": max(0, len(rows) - cap),
        "class_map": class_map,
    }


def _sort_key(row: dict[str, Any], book_rank: dict[str, int]) -> tuple:
    return (
        row["n_point_eq"],
        row["n_point"],
        book_rank.get(row["task_id"], 10_000),
        row["sheet"],
        row["col"],
        row["row"],
    )


def diversity_order(candidates: list[dict[str, Any]], book_order: list[str]) -> list[dict[str, Any]]:
    """Spread mechanical consumer-count features instead of taking the minimum first."""
    book_rank = {task_id: index for index, task_id in enumerate(book_order)}
    items = sorted(candidates, key=lambda row: _sort_key(row, book_rank))
    if len(items) <= 3:
        return items
    cuts = [
        items[: len(items) // 3],
        items[len(items) // 3 : (2 * len(items)) // 3],
        items[(2 * len(items)) // 3 :],
    ]
    queues = [list(even_space(band, len(band))) for band in cuts if band]
    ordered: list[dict[str, Any]] = []
    while any(queues):
        for queue in queues:
            if queue:
                ordered.append(queue.pop(0))
    return ordered


def feature_bands(
    candidates: list[dict[str, Any]], book_order: list[str]
) -> list[list[dict[str, Any]]]:
    book_rank = {task_id: index for index, task_id in enumerate(book_order)}
    items = sorted(candidates, key=lambda row: _sort_key(row, book_rank))
    if not items:
        return [[], [], []]
    if len(items) < 3:
        return [items, [], []]
    return [
        items[: len(items) // 3],
        items[len(items) // 3 : (2 * len(items)) // 3],
        items[(2 * len(items)) // 3 :],
    ]


def pick_stratum(
    true_candidates: list[dict[str, Any]],
    blank_candidates: list[dict[str, Any]],
    book_order: list[str],
    *,
    k_each: int = 6,
    max_per_book: int = MAX_PER_BOOK,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    true_bands = feature_bands(true_candidates, book_order)
    blank_bands = feature_bands(blank_candidates, book_order)
    true_fallback = diversity_order(true_candidates, book_order)
    blank_fallback = diversity_order(blank_candidates, book_order)
    band_quota = [k_each // 3 + (1 if index < k_each % 3 else 0) for index in range(3)]

    def fill(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        true_sel: list[dict[str, Any]] = []
        blank_sel: list[dict[str, Any]] = []
        used: set[str] = set()
        counts: Counter[str] = Counter()

        def try_add(cell: dict[str, Any], bucket: list[dict[str, Any]]) -> bool:
            if cell["cell_id"] in used:
                return False
            if counts[cell["task_id"]] >= limit:
                return False
            used.add(cell["cell_id"])
            counts[cell["task_id"]] += 1
            bucket.append(cell)
            return True

        def take_from(band: list[dict[str, Any]], bucket: list[dict[str, Any]]) -> bool:
            for cell in band:
                if try_add(cell, bucket):
                    return True
            return False

        for index, want in enumerate(band_quota):
            got_true = got_blank = 0
            while got_true < want or got_blank < want:
                progress = False
                if got_true < want and take_from(true_bands[index], true_sel):
                    got_true += 1
                    progress = True
                if got_blank < want and take_from(blank_bands[index], blank_sel):
                    got_blank += 1
                    progress = True
                if not progress:
                    break
        for cell in true_fallback:
            if len(true_sel) >= k_each:
                break
            try_add(cell, true_sel)
        for cell in blank_fallback:
            if len(blank_sel) >= k_each:
                break
            try_add(cell, blank_sel)
        return true_sel, blank_sel

    used_limit = max_per_book
    true_sel, blank_sel = fill(used_limit)
    relaxed = False
    if len(true_sel) < k_each or len(blank_sel) < k_each:
        used_limit = max(max_per_book + 1, k_each)
        true_sel, blank_sel = fill(used_limit)
        relaxed = True
    if len(true_sel) < k_each or len(blank_sel) < k_each:
        raise RuntimeError(
            f"stratum could not fill {k_each}+{k_each}; "
            f"true={len(true_candidates)} blank={len(blank_candidates)}"
        )
    selected = true_sel[:k_each] + blank_sel[:k_each]
    meta = {
        "true_pool": len(true_candidates),
        "blank_pool": len(blank_candidates),
        "true_n_point_pool": sorted({row["n_point"] for row in true_candidates}),
        "blank_n_point_pool": sorted({row["n_point"] for row in blank_candidates}),
        "true_n_eq_pool": sorted({row["n_point_eq"] for row in true_candidates}),
        "blank_n_eq_pool": sorted({row["n_point_eq"] for row in blank_candidates}),
        "selected_workbooks": len({row["task_id"] for row in selected}),
        "max_per_book_requested": max_per_book,
        "max_per_book_used": used_limit if relaxed else max_per_book,
        "relaxed": relaxed,
        "per_workbook": dict(Counter(row["task_id"] for row in selected)),
        "n_point": [row["n_point"] for row in selected],
        "n_point_eq": [row["n_point_eq"] for row in selected],
    }
    return true_sel[:k_each], blank_sel[:k_each], meta


def pick_bucket(
    candidates: list[dict[str, Any]],
    book_order: list[str],
    *,
    k: int = 6,
    max_per_book: int = MAX_PER_BOOK,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    order = diversity_order(candidates, book_order)

    def fill(limit: int) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        used: set[str] = set()
        counts: Counter[str] = Counter()
        for cell in order:
            if len(selected) >= k:
                break
            if cell["cell_id"] in used:
                continue
            if counts[cell["task_id"]] >= limit:
                continue
            used.add(cell["cell_id"])
            counts[cell["task_id"]] += 1
            selected.append(cell)
        return selected

    used_limit = max_per_book
    selected = fill(used_limit)
    relaxed = False
    if len(selected) < k:
        used_limit = max(max_per_book + 1, k)
        selected = fill(used_limit)
        relaxed = True
    if len(selected) < k:
        raise RuntimeError(f"bucket only has {len(candidates)} candidates; needed {k}")
    meta = {
        "pool": len(candidates),
        "workbooks_in_pool": len({row["task_id"] for row in candidates}),
        "selected_workbooks": len({row["task_id"] for row in selected[:k]}),
        "max_per_book_requested": max_per_book,
        "max_per_book_used": used_limit if relaxed else max_per_book,
        "relaxed": relaxed,
        "per_workbook": dict(Counter(row["task_id"] for row in selected[:k])),
        "n_point": [row["n_point"] for row in selected[:k]],
        "n_point_eq": [row["n_point_eq"] for row in selected[:k]],
    }
    return selected[:k], meta


def build_common_packet(cell: dict[str, Any]) -> str:
    return (
        "TASK INSTRUCTION\n"
        f"{cell['instruction']}\n\n"
        "WORKBOOK\n"
        f"category: {cell['category']}\n"
        f"task_id: {cell['task_id']}\n"
        f"file: {cell['spreadsheet_path']}\n"
        f"sheet: {cell['sheet']}\n\n"
        "TARGET\n"
        f"address: {cell['sheet']}!{cell['address']}\n"
        "This cell is currently blank.\n\n"
        "LOCAL CONTEXT\n"
        f"Fixed rectangular window of ±{cell['window']['radius']} rows and "
        f"±{cell['window']['radius']} columns around the target, clipped only "
        "at sheet boundaries or intersecting merged ranges.\n"
        f"{cell['window_text']}\n"
    )


def render_dependency_summary(cell: dict[str, Any]) -> str:
    lines = [
        "DEPENDENCY FACTS FOR TARGET",
        DEPENDENCY_PREFACE,
        f"explicit point consumers: {cell['n_point']}",
        f"same-sheet point consumers: {cell['n_point_same']}",
        f"cross-sheet point consumers: {cell['n_point_cross']}",
        f"distinct consumer formula classes: {cell['n_point_eq']}",
        "consumer addresses:",
    ]
    listed = cell["consumers"]
    for item in listed:
        lines.append(f"- {item['sheet']}!{item['address']} ({item['relation']})")
    if cell["consumers_truncated"]:
        lines.append(
            f"address list truncated: {cell['consumers_truncated']} additional "
            "point consumers omitted; counts above are complete."
        )
    return "\n".join(lines)


def render_consumer_evidence(cell: dict[str, Any]) -> str:
    lines = [
        "DIRECT POINT CONSUMER FORMULAS",
        "At most 12 are listed. Ordered by sheet then address. No ranking.",
    ]
    if cell["consumers_truncated"]:
        lines.append(
            f"truncated: {cell['consumers_truncated']} additional point consumers omitted."
        )
    else:
        lines.append("truncated: none.")
    for item in cell["consumers"]:
        lines.extend(
            [
                f"- source: {item['sheet']}!{item['address']}",
                f"  raw source formula: {item['formula']}",
                f"  relation: {item['relation']}",
                f"  consumer_class_id: {item['consumer_class_id']}",
            ]
        )
    return "\n".join(lines)


def build_prompt(cell: dict[str, Any], condition: str) -> str:
    parts = [build_common_packet(cell)]
    if condition in {"C1", "C2", "ORACLE_WHERE"}:
        parts.append(render_dependency_summary(cell))
        parts.append("")
    if condition in {"C2", "ORACLE_WHERE"}:
        parts.append(render_consumer_evidence(cell))
        parts.append("")
    if condition == "ORACLE_WHERE":
        parts.append(
            "This cell is known to require a formula. Do not decide whether it "
            "should be blank. Infer what formula belongs here."
        )
    elif condition == "C0":
        parts.append("QUESTION\n" + QUESTION_C0)
    elif condition == "C1":
        parts.append("QUESTION\n" + QUESTION_C1)
    elif condition == "C2":
        parts.append("QUESTION\n" + QUESTION_C2)
    else:
        raise ValueError(condition)
    return "\n".join(parts).rstrip() + "\n"


def prompt_leaks_eval(cell: dict[str, Any], prompt: str) -> list[str]:
    leaks: list[str] = []
    golden = cell.get("eval_golden_formula")
    if golden and golden in prompt:
        leaks.append("golden_formula")
    if "TRUE_TARGET" in prompt or "INTENTIONAL_BLANK" == prompt.strip():
        leaks.append("eval_role")
    if cell.get("eval_role") == "TRUE_TARGET" and "MISSING_FORMULA" in prompt and "Decide" not in SYSTEM_CLASSIFY:
        pass
    return leaks


def scan_forbidden(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in FORBIDDEN_PROBE_TERMS if term in lowered]


def parse_classify(text: str) -> dict[str, Any]:
    payload = _extract_json(text)
    label_raw = str(payload.get("label") or "").strip().upper().replace(" ", "_")
    if label_raw in {"MISSING_FORMULA", "MISSING"}:
        label = "MISSING_FORMULA"
    elif label_raw in {"INTENTIONAL_BLANK", "INTENTIONAL", "BLANK"}:
        label = "INTENTIONAL_BLANK"
    else:
        raise ValueError(f"invalid label {payload.get('label')!r}")
    prob = payload.get("probability_missing_formula")
    if isinstance(prob, str):
        prob = prob.strip().rstrip("%")
        prob = float(prob)
    else:
        prob = float(prob)
    if 1 < prob <= 100:
        prob = prob / 100.0
    if not 0.0 <= prob <= 1.0:
        raise ValueError(f"probability out of range: {prob}")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ValueError("empty reason")
    return {
        "label": label,
        "probability_missing_formula": prob,
        "reason": reason,
        "valid": True,
    }


def parse_oracle(text: str) -> dict[str, Any]:
    payload = _extract_json(text)
    formula = str(payload.get("formula") or "").strip()
    if not formula:
        raise ValueError("empty formula")
    if not formula.startswith("="):
        formula = "=" + formula
    reason = str(payload.get("reason") or "").strip()
    return {"formula": formula, "reason": reason, "valid": True}


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty model output")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return json.loads(fenced.group(1))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("no JSON object in model output")
        return json.loads(match.group(0))


def tag_reason(reason: str, condition: str) -> list[str]:
    text = reason.lower()
    tags: list[str] = []
    if any(word in text for word in LOCAL_WORDS):
        tags.append("LOCAL_SEMANTICS")
    if any(word in text for word in DEP_WORDS):
        tags.append("DEPENDENCY_USED")
    formula_used = any(word in text for word in FORMULA_WORDS) or (
        condition in {"C2", "ORACLE_WHERE"} and "=" in reason
    )
    if formula_used:
        tags.append("CONSUMER_FORMULA_USED")
    if any(word in text for word in ZERO_WORDS):
        tags.append("BLANK_AS_ZERO_ASSUMPTION")
    if not tags or any(word in text for word in GUESS_WORDS):
        if "UNSUPPORTED_GUESS" not in tags:
            if not tags or any(word in text for word in GUESS_WORDS):
                tags.append("UNSUPPORTED_GUESS")
    if not tags:
        tags.append("UNSUPPORTED_GUESS")
    seen: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen


def classification_metrics(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    valid = [row for row in rows if row.get("valid")]
    n = len(valid)
    tp = tn = fp = fn = 0
    brier_terms: list[float] = []
    p_true: list[float] = []
    p_blank: list[float] = []
    for row in valid:
        y = 1 if row["eval_role"] == "TRUE_TARGET" else 0
        pred_pos = row["label"] == "MISSING_FORMULA"
        p = float(row["probability_missing_formula"])
        brier_terms.append((p - y) ** 2)
        if y:
            p_true.append(p)
            if pred_pos:
                tp += 1
            else:
                fn += 1
        else:
            p_blank.append(p)
            if pred_pos:
                fp += 1
            else:
                tn += 1
    tpr = tp / (tp + fn) if (tp + fn) else None
    tnr = tn / (tn + fp) if (tn + fp) else None
    fpr = fp / (fp + tn) if (fp + tn) else None
    fnr = fn / (fn + tp) if (fn + tp) else None
    acc = (tp + tn) / n if n else None
    bal = None
    if tpr is not None and tnr is not None:
        bal = (tpr + tnr) / 2
    all_valid = n == len(rows) and n > 0
    return {
        "n": len(rows),
        "n_valid": n,
        "n_invalid": len(rows) - n,
        "accuracy": acc,
        "balanced_accuracy": bal,
        "true_positive_rate": tpr,
        "true_negative_rate": tnr,
        "false_positive_rate": fpr,
        "false_negative_rate": fnr,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "brier": (sum(brier_terms) / n) if all_valid else None,
        "mean_p_true_targets": (sum(p_true) / len(p_true)) if all_valid and p_true else None,
        "mean_p_intentional_blanks": (sum(p_blank) / len(p_blank)) if all_valid and p_blank else None,
        "probability_metrics_computed": all_valid,
    }


def paired_transitions(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(a) & set(b))
    counts = {
        "wrong_to_right": 0,
        "right_to_wrong": 0,
        "unchanged_right": 0,
        "unchanged_wrong": 0,
        "excluded_invalid": 0,
        "n_paired": 0,
    }
    d_correct: list[float] = []
    for key in keys:
        left, right = a[key], b[key]
        if not left.get("valid") or not right.get("valid"):
            counts["excluded_invalid"] += 1
            continue
        counts["n_paired"] += 1
        gold_pos = left["eval_role"] == "TRUE_TARGET"
        left_ok = (left["label"] == "MISSING_FORMULA") == gold_pos
        right_ok = (right["label"] == "MISSING_FORMULA") == gold_pos
        if left_ok and right_ok:
            counts["unchanged_right"] += 1
        elif (not left_ok) and right_ok:
            counts["wrong_to_right"] += 1
        elif left_ok and (not right_ok):
            counts["right_to_wrong"] += 1
        else:
            counts["unchanged_wrong"] += 1
        p_left = float(left["probability_missing_formula"])
        p_right = float(right["probability_missing_formula"])
        if gold_pos:
            d_correct.append(p_right - p_left)
        else:
            d_correct.append((1 - p_right) - (1 - p_left))
    counts["mean_delta_p_correct"] = (sum(d_correct) / len(d_correct)) if d_correct else None
    counts["net_correct"] = counts["wrong_to_right"] - counts["right_to_wrong"]
    return counts


def cmd_select(*, force: bool = False) -> dict[str, Any]:
    if SLICE_36.exists() and not force:
        print(f"exists {SLICE_36}", flush=True)
        return json.loads(SLICE_36.read_text())
    slice12 = _load_slice()
    by_id = {task["id"]: task for task in _task_list()}
    book_order = [item["id"] for item in slice12["tasks"]]
    pools: dict[tuple[str, str], list[dict[str, Any]]] = {
        (stratum, role): [] for stratum in STRATA for role in ("TRUE_TARGET", "INTENTIONAL_BLANK")
    }
    inventory: dict[str, Any] = {}
    t0 = time.perf_counter()
    for item in slice12["tasks"]:
        task_id = item["id"]
        task = by_id[task_id]
        print(f"SELECT {task_id}", flush=True)
        graph = build_graph(_input_path(task))
        types = blank_edge_types(graph)
        input_cells = _cell_map(_input_path(task))
        golden_cells = _cell_map(_golden_path(task))
        targets = set(_blank_formula_targets(input_cells, golden_cells))
        counts = Counter()
        n_point_seen: dict[str, set[int]] = defaultdict(set)
        for key, info in types.items():
            stratum = point_stratum(info)
            if stratum is None:
                continue
            sheet, col, row = key
            if not _blank(input_cells.get(key)):
                continue
            gold_label = _label(golden_cells.get(key))
            if gold_label == "A":
                role = "TRUE_TARGET"
            elif gold_label == "B":
                role = "INTENTIONAL_BLANK"
            else:
                counts["excluded_golden_value"] += 1
                continue
            if key in targets:
                assert role == "TRUE_TARGET"
            consumers = point_consumers(graph, key)
            address = a1_address(col, row)
            golden_formula = formula_text(golden_cells.get(key))
            rec = {
                "cell_id": cell_id(task_id, sheet, col, row),
                "category": "Financial_Model",
                "task_id": task_id,
                "family": item.get("family"),
                "spreadsheet_path": task["spreadsheet_path"],
                "instruction": task["instruction"],
                "sheet": sheet,
                "col": col,
                "row": row,
                "address": address,
                "stratum": stratum,
                "eval_role": role,
                "partition": info["partition"],
                "n_point": consumers["n_point"],
                "n_point_same": consumers["n_point_same"],
                "n_point_cross": consumers["n_point_cross"],
                "n_point_eq": consumers["n_point_eq"],
                "consumers": consumers["listed"],
                "consumers_truncated": consumers["truncated"],
                "eval_golden_formula": golden_formula,
            }
            pools[(stratum, role)].append(rec)
            counts[f"{stratum}:{role}"] += 1
            n_point_seen[f"{stratum}:{role}"].add(consumers["n_point"])
        inventory[task_id] = {
            **dict(counts),
            "n_point_values": {key: sorted(values) for key, values in n_point_seen.items()},
        }
        del graph, types, input_cells, golden_cells
    selected: list[dict[str, Any]] = []
    selection_meta: dict[str, Any] = {}
    for stratum in STRATA:
        true_sel, blank_sel, meta = pick_stratum(
            pools[(stratum, "TRUE_TARGET")],
            pools[(stratum, "INTENTIONAL_BLANK")],
            book_order,
            k_each=TRUE_PER_STRATUM,
        )
        selected.extend(true_sel)
        selected.extend(blank_sel)
        selection_meta[stratum] = meta
    selected.sort(key=lambda row: (STRATA.index(row["stratum"]), row["eval_role"], row["cell_id"]))
    apply_windows(selected)
    payload = {
        "name": "fm-dependency-glm-probe-36",
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "purpose": (
            "Once a potentially important blank is already identified, can "
            "GLM-5.3-Flash use mechanically recovered point-reference evidence "
            "to distinguish a missing formula from an intentional blank? "
            "Artificially balanced. Not a prevalence or benchmark estimate. "
            "Raw precision is not an estimate of real-world target precision."
        ),
        "frozen_at": datetime.now(UTC).isoformat(),
        "golden_used": "construction_and_evaluation_only",
        "golden_in_model_input": False,
        "source_slice": "fm-target-selection-probe-12",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": TEMPERATURE,
        "seed_execution": SEED,
        "context_radius": CONTEXT_RADIUS,
        "consumer_cap": CONSUMER_CAP,
        "max_per_workbook_per_stratum": MAX_PER_BOOK,
        "selection": {
            "algorithm": (
                "Per stratum, jointly select 6 TRUE TARGETS and 6 INTENTIONAL BLANKS. "
                "At most 2 cells from one workbook within the stratum. Candidates are "
                "sorted by (n_point_eq, n_point, frozen-12 order, sheet, col, row), split "
                "into tertiles, and interleaved so high consumer-count cells are considered "
                "alongside low-count cells. Relax max-per-book only if a stratum cannot fill."
            ),
            "excluded": ["RANGE_ONLY", "golden_value_not_formula_or_blank"],
            "included_partitions": ["POINT_ONLY", "POINT_AND_RANGE"],
            "buckets": selection_meta,
            "inventory_by_task": inventory,
        },
        "cells": selected,
        "runtime_s": round(time.perf_counter() - t0, 3),
    }
    SLICE_36.parent.mkdir(parents=True, exist_ok=True)
    SLICE_36.write_text(json.dumps(payload, indent=2) + "\n")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "slice.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"WROTE {SLICE_36} n={len(selected)}", flush=True)
    return payload


def apply_windows(cells: list[dict[str, Any]]) -> None:
    by_id = {task["id"]: task for task in _task_list()}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        grouped[cell["task_id"]].append(cell)
    for task_id, group in grouped.items():
        task = by_id[task_id]
        print(f"WINDOW {task_id}", flush=True)
        workbook = openpyxl.load_workbook(_input_path(task), data_only=False, read_only=False)
        sheets = {ws.title: ws for ws in workbook.worksheets}
        for cell in group:
            ws = sheets[cell["sheet"]]
            window = extract_window(ws, cell["col"], cell["row"])
            cell["window"] = window
            cell["window_text"] = render_window(window)
            if "TARGET [BLANK]" not in cell["window_text"]:
                raise RuntimeError(f"target missing from window {cell['cell_id']}")
        workbook.close()


def refresh_windows(slice_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rebuild ±3 windows for the frozen 36 without changing cell IDs."""
    slice_doc = slice_doc or json.loads(SLICE_36.read_text())
    apply_windows(slice_doc["cells"])
    slice_doc["windows_refreshed_at"] = datetime.now(UTC).isoformat()
    SLICE_36.write_text(json.dumps(slice_doc, indent=2) + "\n")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "slice.json").write_text(json.dumps(slice_doc, indent=2) + "\n")
    print(f"REFRESHED windows in {SLICE_36}", flush=True)
    return slice_doc


def _jobs(slice_doc: dict[str, Any], *, oracle: bool) -> list[dict[str, Any]]:
    jobs = []
    for cell in slice_doc["cells"]:
        for condition in CONDITIONS:
            jobs.append(
                {
                    "job_id": f"{cell['cell_id']}::{condition}",
                    "cell_id": cell["cell_id"],
                    "condition": condition,
                    "kind": "classify",
                }
            )
        if oracle and cell["eval_role"] == "TRUE_TARGET":
            jobs.append(
                {
                    "job_id": f"{cell['cell_id']}::ORACLE_WHERE",
                    "cell_id": cell["cell_id"],
                    "condition": "ORACLE_WHERE",
                    "kind": "oracle",
                }
            )
    rng = random.Random(SEED)
    rng.shuffle(jobs)
    for index, job in enumerate(jobs, 1):
        job["order"] = index
    return jobs


def openrouter_chat(
    *,
    api_key: str,
    system: str,
    user: str,
    max_tokens: int,
    include_reasoning: bool = True,
    temperature: float | None = TEMPERATURE,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        body["temperature"] = temperature
    if include_reasoning:
        body["reasoning"] = {"effort": REASONING_EFFORT}
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "librecalc-dependency-glm-probe",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {"http_ok": True, "payload": payload}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"http_ok": False, "status": exc.code, "detail": detail}


def _message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content or "")


def cmd_run(*, oracle: bool, force: bool = False) -> dict[str, Any]:
    slice_doc = json.loads(SLICE_36.read_text()) if SLICE_36.exists() else cmd_select()
    cells = {cell["cell_id"]: cell for cell in slice_doc["cells"]}
    OUT.mkdir(parents=True, exist_ok=True)
    raw_path = OUT / "calls.jsonl"
    summary_path = OUT / "responses.json"
    jobs = _jobs(slice_doc, oracle=oracle)
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "reasoning_effort": REASONING_EFFORT,
                "temperature": TEMPERATURE,
                "seed": SEED,
                "n_jobs": len(jobs),
                "oracle": oracle,
                "independent_calls": True,
                "conversational_history": False,
                "jobs": jobs,
            },
            indent=2,
        )
        + "\n"
    )
    done: dict[str, dict[str, Any]] = {}
    if summary_path.exists() and not force:
        done = {row["job_id"]: row for row in json.loads(summary_path.read_text())["calls"]}
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY must be set in the environment or repo .env")
    results = list(done.values())
    done_ids = set(done)
    if force:
        raw_path.write_text("")
        results = []
        done_ids = set()
    with raw_path.open("a", encoding="utf-8") as raw:
        for job in jobs:
            if job["job_id"] in done_ids:
                print(f"SKIP {job['order']}/{len(jobs)} {job['job_id']}", flush=True)
                continue
            cell = cells[job["cell_id"]]
            prompt = build_prompt(cell, job["condition"])
            system = SYSTEM_ORACLE if job["kind"] == "oracle" else SYSTEM_CLASSIFY
            print(f"CALL {job['order']}/{len(jobs)} {job['job_id']}", flush=True)
            started = time.perf_counter()
            attempt = 0
            http: dict[str, Any] = {}
            include_reasoning = True
            temperature: float | None = TEMPERATURE
            while attempt < 8:
                attempt += 1
                http = openrouter_chat(
                    api_key=api_key,
                    system=system,
                    user=prompt,
                    max_tokens=500 if job["kind"] == "oracle" else 700,
                    include_reasoning=include_reasoning,
                    temperature=temperature,
                )
                if http.get("http_ok"):
                    break
                status = http.get("status")
                detail = str(http.get("detail") or "").lower()
                if status == 400 and include_reasoning and "reasoning" in detail:
                    include_reasoning = False
                    continue
                if status == 400 and temperature is not None and "temperature" in detail:
                    temperature = None
                    continue
                if status in {429, 502, 503, 504}:
                    time.sleep(min(30, 2 ** attempt))
                    continue
                break
            elapsed = round(time.perf_counter() - started, 3)
            record: dict[str, Any] = {
                "job_id": job["job_id"],
                "order": job["order"],
                "cell_id": job["cell_id"],
                "condition": job["condition"],
                "kind": job["kind"],
                "elapsed_s": elapsed,
                "attempts": attempt,
                "eval_role": cell["eval_role"],
                "stratum": cell["stratum"],
                "n_point": cell["n_point"],
                "n_point_eq": cell["n_point_eq"],
            }
            if not http.get("http_ok"):
                record.update({"valid": False, "error": http})
            else:
                payload = http["payload"]
                text = _message_text(payload)
                record["raw_text"] = text
                record["usage"] = payload.get("usage")
                try:
                    parsed = parse_oracle(text) if job["kind"] == "oracle" else parse_classify(text)
                    record.update(parsed)
                except Exception as exc:
                    record.update({"valid": False, "parse_error": str(exc)})
            raw.write(json.dumps(record) + "\n")
            raw.flush()
            results.append(record)
            done_ids.add(job["job_id"])
            summary_path.write_text(
                json.dumps(
                    {
                        "model": MODEL,
                        "reasoning_effort": REASONING_EFFORT,
                        "temperature": TEMPERATURE,
                        "n": len(results),
                        "calls": results,
                    },
                    indent=2,
                )
                + "\n"
            )
            time.sleep(0.15)
    return {"n": len(results), "path": str(summary_path)}


def _index_calls(calls: list[dict[str, Any]], kind: str) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in calls:
        if row.get("kind") != kind:
            continue
        out[row["condition"]][row["cell_id"]] = row
    return out


def score_oracle(slice_doc: dict[str, Any], calls: list[dict[str, Any]]) -> dict[str, Any]:
    cells = {cell["cell_id"]: cell for cell in slice_doc["cells"]}
    rows = [row for row in calls if row.get("kind") == "oracle"]
    exact = canonical = invalid = 0
    details = []
    for row in rows:
        cell = cells[row["cell_id"]]
        gold = cell.get("eval_golden_formula")
        if not row.get("valid"):
            invalid += 1
            details.append({"cell_id": row["cell_id"], "valid": False})
            continue
        pred = row["formula"]
        gold_fp = relative_fingerprint(gold, cell["col"], cell["row"], sheet=cell["sheet"])
        pred_fp = relative_fingerprint(pred, cell["col"], cell["row"], sheet=cell["sheet"])
        is_exact = pred.replace(" ", "") == gold.replace(" ", "")
        is_canonical = (
            (not gold_fp.opaque)
            and (not pred_fp.opaque)
            and gold_fp.eq_id == pred_fp.eq_id
        )
        exact += int(is_exact)
        canonical += int(is_canonical or is_exact)
        details.append(
            {
                "cell_id": row["cell_id"],
                "stratum": cell["stratum"],
                "valid": True,
                "exact": is_exact,
                "canonical": is_canonical or is_exact,
                "predicted": pred,
            }
        )
    n = len(rows)
    return {
        "n": n,
        "n_invalid": invalid,
        "exact": exact,
        "canonical_fingerprint": canonical,
        "exact_rate": (exact / n) if n else None,
        "canonical_rate": (canonical / n) if n else None,
        "cells": details,
    }


def representative_cases(
    slice_doc: dict[str, Any],
    by_cond: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    cells = {cell["cell_id"]: cell for cell in slice_doc["cells"]}

    def ok(row: dict[str, Any], cell: dict[str, Any]) -> bool | None:
        if not row.get("valid"):
            return None
        gold_pos = cell["eval_role"] == "TRUE_TARGET"
        return (row["label"] == "MISSING_FORMULA") == gold_pos

    improved = []
    regression = []
    all_true = []
    all_blank_wrong = []
    for cell in slice_doc["cells"]:
        cid = cell["cell_id"]
        c0, c1, c2 = by_cond["C0"].get(cid), by_cond["C1"].get(cid), by_cond["C2"].get(cid)
        if not (c0 and c1 and c2):
            continue
        o0, o1, o2 = ok(c0, cell), ok(c1, cell), ok(c2, cell)
        if o0 is False and (o1 or o2):
            improved.append(cid)
        if o0 is True and (o1 is False or o2 is False):
            regression.append(cid)
        if cell["eval_role"] == "TRUE_TARGET" and o0 and o1 and o2:
            all_true.append(cid)
        if cell["eval_role"] == "INTENTIONAL_BLANK" and o0 is False and o1 is False and o2 is False:
            all_blank_wrong.append(cid)

    def pack(cid: str | None) -> dict[str, Any] | None:
        if cid is None:
            return None
        cell = cells[cid]
        return {
            "cell_id": cid,
            "stratum": cell["stratum"],
            "eval_role": cell["eval_role"],
            "n_point": cell["n_point"],
            "n_point_eq": cell["n_point_eq"],
            "C0": _brief(by_cond["C0"][cid]),
            "C1": _brief(by_cond["C1"][cid]),
            "C2": _brief(by_cond["C2"][cid]),
        }

    return {
        "c0_wrong_to_c1_or_c2_right": pack(improved[0] if improved else None),
        "c0_right_dependency_regression": pack(regression[0] if regression else None),
        "all_conditions_true_target": pack(all_true[0] if all_true else None),
        "all_conditions_wrong_intentional_blank": pack(all_blank_wrong[0] if all_blank_wrong else None),
        "counts": {
            "c0_wrong_to_c1_or_c2_right": len(improved),
            "c0_right_dependency_regression": len(regression),
            "all_conditions_true_target": len(all_true),
            "all_conditions_wrong_intentional_blank": len(all_blank_wrong),
        },
    }


def _brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": row.get("valid"),
        "label": row.get("label"),
        "probability_missing_formula": row.get("probability_missing_formula"),
        "reason": row.get("reason"),
        "tags": row.get("tags"),
    }


def interpret(metrics: dict[str, Any], paired: dict[str, Any], tags: dict[str, Any]) -> dict[str, Any]:
    acc = {cond: (metrics[cond]["accuracy"] or 0) for cond in CONDITIONS}
    net_01 = paired["C0->C1"]["net_correct"]
    net_12 = paired["C1->C2"]["net_correct"]
    net_02 = paired["C0->C2"]["net_correct"]
    d_p = {
        "C0->C1": paired["C0->C1"]["mean_delta_p_correct"],
        "C1->C2": paired["C1->C2"]["mean_delta_p_correct"],
        "C0->C2": paired["C0->C2"]["mean_delta_p_correct"],
    }
    dep_c1 = tags["C1"].get("DEPENDENCY_USED", 0)
    dep_c2 = tags["C2"].get("DEPENDENCY_USED", 0)
    formula_c2 = tags["C2"].get("CONSUMER_FORMULA_USED", 0)
    n = metrics["C0"]["n_valid"] or 36
    material = 3
    used = (dep_c1 + dep_c2 + formula_c2) >= max(6, n // 3)
    labels: list[str] = []
    notes: list[str] = []
    if acc["C2"] > acc["C1"] + 1e-9 and acc["C1"] > acc["C0"] + 1e-9 and net_01 >= 0 and net_12 >= 0:
        labels.append("A")
        notes.append(
            "C2 > C1 > C0. GLM can reason with dependency evidence once the relation "
            "is recovered and placed at the decision point. Normal agent failure is "
            "substantially upstream: global relation construction / retrieval / salience."
        )
    if abs(acc["C1"] - acc["C0"]) * n < material and (acc["C2"] - acc["C0"]) * n >= material:
        labels.append("B")
        notes.append(
            "C1 does little, C2 materially improves. The compressed typed relation is "
            "not sufficiently operational, but concrete consumer formulas are. This is "
            "an interface/representation result: computation → retrieve relevant concrete "
            "evidence, rather than computation → expose IR metadata."
        )
    if abs(net_02) < material and any(
        (delta or 0) >= 0.05 for delta in d_p.values()
    ):
        labels.append("C")
        notes.append(
            "C1/C2 change confidence but not correctness. The model recognizes the "
            "evidence as relevant but lacks enough semantic information to decide."
        )
    if net_02 < material and not used:
        labels.append("D")
        notes.append(
            "C1/C2 do not improve and rationales rarely use the information. "
            "Interface/policy mismatch: even when globally useful structure is locally "
            "available, GLM does not reliably operationalize it. Not yet raw capability failure."
        )
    if used and acc["C2"] < 0.7:
        labels.append("E")
        notes.append(
            "C1/C2 information is explicitly used, but decisions remain poor. "
            "Strongest evidence for a deeper reasoning limitation or missing schema/"
            "semantic information. Dependency evidence itself may not be decision-sufficient."
        )
    if not labels:
        labels.append("mixed")
        notes.append("No single Result A–E template dominates; see paired tables.")
    return {
        "primary": labels[0],
        "also": labels[1:],
        "labels": labels,
        "accuracy": acc,
        "net_correct": {"C0->C1": net_01, "C1->C2": net_12, "C0->C2": net_02},
        "notes": notes,
    }


def cmd_score() -> dict[str, Any]:
    slice_doc = json.loads(SLICE_36.read_text())
    responses = json.loads((OUT / "responses.json").read_text())
    calls = responses["calls"]
    cells = {cell["cell_id"]: cell for cell in slice_doc["cells"]}
    for row in calls:
        if row.get("kind") == "classify" and row.get("valid"):
            row["tags"] = tag_reason(row.get("reason") or "", row["condition"])
        cell = cells[row["cell_id"]]
        row["eval_role"] = cell["eval_role"]
        row["stratum"] = cell["stratum"]
        row["n_point"] = cell["n_point"]
        row["n_point_eq"] = cell["n_point_eq"]
    by_cond = _index_calls(calls, "classify")
    metrics = {}
    for condition in CONDITIONS:
        rows = list(by_cond[condition].values())
        metrics[condition] = classification_metrics(rows)
        metrics[condition]["by_stratum"] = {
            stratum: classification_metrics(
                [row for row in rows if row["stratum"] == stratum]
            )
            for stratum in STRATA
        }
        metrics[condition]["by_n_point"] = {
            "eq1": classification_metrics([row for row in rows if row["n_point"] == 1]),
            "ge2": classification_metrics([row for row in rows if row["n_point"] >= 2]),
        }
        metrics[condition]["by_n_point_eq"] = {
            "eq1": classification_metrics([row for row in rows if row["n_point_eq"] == 1]),
            "ge2": classification_metrics([row for row in rows if row["n_point_eq"] >= 2]),
        }
    paired = {
        "C0->C1": paired_transitions(by_cond["C0"], by_cond["C1"]),
        "C1->C2": paired_transitions(by_cond["C1"], by_cond["C2"]),
        "C0->C2": paired_transitions(by_cond["C0"], by_cond["C2"]),
    }
    paired_by_stratum = {}
    for stratum in STRATA:
        def subset(mapping: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
            return {cid: row for cid, row in mapping.items() if cells[cid]["stratum"] == stratum}

        paired_by_stratum[stratum] = {
            "C0->C1": paired_transitions(subset(by_cond["C0"]), subset(by_cond["C1"])),
            "C1->C2": paired_transitions(subset(by_cond["C1"]), subset(by_cond["C2"])),
            "C0->C2": paired_transitions(subset(by_cond["C0"]), subset(by_cond["C2"])),
        }
    tag_counts = {
        condition: dict(
            Counter(
                tag
                for row in by_cond[condition].values()
                if row.get("valid")
                for tag in row.get("tags") or []
            )
        )
        for condition in CONDITIONS
    }
    oracle = score_oracle(slice_doc, calls)
    interp = interpret(metrics, paired, tag_counts)
    cases = representative_cases(slice_doc, by_cond)
    distribution = _distribution(slice_doc)
    report = {
        "label": SLICE_LABEL,
        "not": SLICE_NOT,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": TEMPERATURE,
        "n_cells": len(slice_doc["cells"]),
        "n_classify_calls": sum(1 for row in calls if row.get("kind") == "classify"),
        "n_oracle_calls": sum(1 for row in calls if row.get("kind") == "oracle"),
        "distribution": distribution,
        "validity": {
            condition: {
                "n": metrics[condition]["n"],
                "n_valid": metrics[condition]["n_valid"],
                "n_invalid": metrics[condition]["n_invalid"],
            }
            for condition in CONDITIONS
        },
        "metrics": metrics,
        "paired": paired,
        "paired_by_stratum": paired_by_stratum,
        "rationale_tags": tag_counts,
        "oracle_where": oracle,
        "representative": cases,
        "interpretation": interp,
        "scored_at": datetime.now(UTC).isoformat(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "score.json").write_text(json.dumps(report, indent=2) + "\n")
    (OUT / "report.md").write_text(render_report(slice_doc, report) + "\n")
    print(f"WROTE {OUT / 'report.md'}", flush=True)
    return report


def _distribution(slice_doc: dict[str, Any]) -> dict[str, Any]:
    by_stratum: dict[str, Any] = {}
    for stratum in STRATA:
        cells = [cell for cell in slice_doc["cells"] if cell["stratum"] == stratum]
        by_stratum[stratum] = {
            "n": len(cells),
            "true_targets": sum(1 for cell in cells if cell["eval_role"] == "TRUE_TARGET"),
            "intentional_blanks": sum(1 for cell in cells if cell["eval_role"] == "INTENTIONAL_BLANK"),
            "workbooks": dict(Counter(cell["task_id"] for cell in cells)),
            "n_point": [cell["n_point"] for cell in cells],
            "n_point_eq": [cell["n_point_eq"] for cell in cells],
            "partitions": dict(Counter(cell["partition"] for cell in cells)),
        }
    return {
        "by_stratum": by_stratum,
        "workbooks_overall": dict(Counter(cell["task_id"] for cell in slice_doc["cells"])),
    }


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100 * value:.1f}%"


def _num(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def render_report(slice_doc: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        "# GLM-5.3-Flash dependency localization probe",
        "",
        f"**{SLICE_LABEL}**",
        f"**{SLICE_NOT}**",
        "",
        "This is a capability-localization experiment. It is not a SpreadsheetBench "
        "score, not a population accuracy estimate, and not a claim that dependency "
        "should automatically trigger edits.",
        "",
        "## 1. Frozen 36-cell construction",
        "",
        slice_doc["purpose"],
        "",
        f"- source slice: `{slice_doc['source_slice']}`",
        f"- context: ±{slice_doc['context_radius']} rows/columns",
        f"- consumer cap: {slice_doc['consumer_cap']}",
        f"- max cells per workbook within a stratum: {slice_doc['max_per_workbook_per_stratum']} (relax only if a bucket cannot fill)",
        f"- goldens: {slice_doc['golden_used']}; in model input: {slice_doc['golden_in_model_input']}",
        "",
        "Selection algorithm:",
        "",
        slice_doc["selection"]["algorithm"],
        "",
        "IDs:",
        "",
    ]
    for cell in slice_doc["cells"]:
        lines.append(
            f"- `{cell['cell_id']}`  {cell['stratum']}  {cell['eval_role']}  "
            f"n_point={cell['n_point']} n_eq={cell['n_point_eq']}  {cell['partition']}"
        )
    lines.extend(["", "## 2. Workbook / stratum distribution", ""])
    dist = report["distribution"]
    for stratum in STRATA:
        item = dist["by_stratum"][stratum]
        lines.append(
            f"### {stratum}  n={item['n']}  true={item['true_targets']}  "
            f"intentional={item['intentional_blanks']}"
        )
        lines.append("")
        for task_id, count in item["workbooks"].items():
            lines.append(f"- {task_id}: {count}")
        lines.append("")
    lines.extend(
        [
            "Overall workbook counts: "
            + ", ".join(f"{k}={v}" for k, v in dist["workbooks_overall"].items()),
            "",
            "## 3. Prompt templates",
            "",
            "### System (C0/C1/C2)",
            "",
            "```",
            SYSTEM_CLASSIFY.strip(),
            "```",
            "",
            "### Common packet",
            "",
            "Original task instruction; workbook/sheet identity; target address; "
            "statement that the target is currently blank; fixed ±3 window of raw "
            "formulas/values; mechanical clipping notes. No golden contents.",
            "",
            "### C0 question",
            "",
            QUESTION_C0,
            "",
            "### C1 addition",
            "",
            DEPENDENCY_PREFACE,
            "",
            "Counts: explicit point consumers, same-sheet, cross-sheet, distinct "
            "consumer formula classes, plus consumer addresses. No consumer formulas.",
            "",
            "### C2 addition",
            "",
            "Up to 12 direct point-consumer formulas: source address, raw formula, "
            "same-sheet/cross-sheet, consumer_class_id. Deterministic sheet/address "
            "order. Truncation reported. No range consumers.",
            "",
            "### ORACLE_WHERE system",
            "",
            "```",
            SYSTEM_ORACLE.strip(),
            "```",
            "",
            "## 4. Model / configuration",
            "",
            f"- model: `{report['model']}`",
            f"- reasoning_effort: `{report['reasoning_effort']}`",
            f"- temperature: {report['temperature']}",
            f"- seed (execution order only): {SEED}",
            "- each case/condition is an independent call with no conversational history",
            "",
            "## 5. Validity / failure counts",
            "",
        ]
    )
    for condition, item in report["validity"].items():
        lines.append(
            f"- {condition}: valid {item['n_valid']}/{item['n']}  invalid {item['n_invalid']}"
        )
    lines.extend(["", "## 6. Classification metrics by condition", ""])
    lines.append(
        "| condition | acc | bal acc | TPR | TNR | FPR | FNR | Brier | mean p true | mean p blank |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for condition in CONDITIONS:
        m = report["metrics"][condition]
        lines.append(
            f"| {condition} | {_pct(m['accuracy'])} | {_pct(m['balanced_accuracy'])} | "
            f"{_pct(m['true_positive_rate'])} | {_pct(m['true_negative_rate'])} | "
            f"{_pct(m['false_positive_rate'])} | {_pct(m['false_negative_rate'])} | "
            f"{_num(m['brier'])} | {_num(m['mean_p_true_targets'])} | "
            f"{_num(m['mean_p_intentional_blanks'])} |"
        )
    lines.extend(["", "## 7. Paired transition table", ""])
    for name, item in report["paired"].items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(
            f"- wrong→right: {item['wrong_to_right']}"
        )
        lines.append(f"- right→wrong: {item['right_to_wrong']}")
        lines.append(f"- unchanged right: {item['unchanged_right']}")
        lines.append(f"- unchanged wrong: {item['unchanged_wrong']}")
        lines.append(f"- net correct: {item['net_correct']}")
        lines.append(f"- mean ΔP(correct label): {_num(item['mean_delta_p_correct'])}")
        lines.append("")
    lines.extend(["", "## 8. Results by stratum", ""])
    for stratum in STRATA:
        lines.append(f"### {stratum}")
        lines.append("")
        lines.append("| condition | acc | TPR | TNR |")
        lines.append("|---|---:|---:|---:|")
        for condition in CONDITIONS:
            m = report["metrics"][condition]["by_stratum"][stratum]
            lines.append(
                f"| {condition} | {_pct(m['accuracy'])} | {_pct(m['true_positive_rate'])} | "
                f"{_pct(m['true_negative_rate'])} |"
            )
        lines.append("")
        p = report["paired_by_stratum"][stratum]["C0->C2"]
        lines.append(
            f"C0→C2: wrong→right {p['wrong_to_right']}, right→wrong {p['right_to_wrong']}, "
            f"net {p['net_correct']}, mean ΔP(correct) {_num(p['mean_delta_p_correct'])}"
        )
        lines.append("")
    lines.extend(["", "## 9. Secondary consumer-count slices", ""])
    for slice_name, key in (("1 vs ≥2 point consumers", "by_n_point"), ("1 vs ≥2 consumer classes", "by_n_point_eq")):
        lines.append(f"### {slice_name}")
        lines.append("")
        lines.append("| condition | slice | n | acc | TPR | TNR |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for condition in CONDITIONS:
            for bucket, label in (("eq1", "1"), ("ge2", "≥2")):
                m = report["metrics"][condition][key][bucket]
                lines.append(
                    f"| {condition} | {label} | {m['n_valid']} | {_pct(m['accuracy'])} | "
                    f"{_pct(m['true_positive_rate'])} | {_pct(m['true_negative_rate'])} |"
                )
        lines.append("")
    lines.extend(["", "## 10. Rationale-use tags", ""])
    lines.append("Mechanical tags from the returned `reason` only. Multiple tags may apply.")
    lines.append("")
    lines.append("| condition | LOCAL_SEMANTICS | DEPENDENCY_USED | CONSUMER_FORMULA_USED | BLANK_AS_ZERO_ASSUMPTION | UNSUPPORTED_GUESS |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for condition in CONDITIONS:
        tags = report["rationale_tags"][condition]
        lines.append(
            f"| {condition} | {tags.get('LOCAL_SEMANTICS', 0)} | {tags.get('DEPENDENCY_USED', 0)} | "
            f"{tags.get('CONSUMER_FORMULA_USED', 0)} | {tags.get('BLANK_AS_ZERO_ASSUMPTION', 0)} | "
            f"{tags.get('UNSUPPORTED_GUESS', 0)} |"
        )
    lines.extend(["", "## 11. Representative cases", ""])
    names = {
        "c0_wrong_to_c1_or_c2_right": "C0 wrong → C1/C2 right",
        "c0_right_dependency_regression": "C0 right → dependency evidence regression",
        "all_conditions_true_target": "All conditions correctly identify a true target",
        "all_conditions_wrong_intentional_blank": "All conditions incorrectly classify an intentional blank",
    }
    counts = report["representative"]["counts"]
    for key, title in names.items():
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"n in class: {counts[key]}")
        case = report["representative"][key]
        if not case:
            lines.append("None in this run.")
            lines.append("")
            continue
        lines.append(
            f"`{case['cell_id']}`  {case['stratum']}  {case['eval_role']}  "
            f"n_point={case['n_point']} n_eq={case['n_point_eq']}"
        )
        for condition in CONDITIONS:
            brief = case[condition]
            lines.append(
                f"- {condition}: {brief.get('label')} p={brief.get('probability_missing_formula')} "
                f"tags={brief.get('tags')}"
            )
            if brief.get("reason"):
                lines.append(f"  reason: {brief['reason']}")
        lines.append("")
    oracle = report["oracle_where"]
    lines.extend(
        [
            "## 12. ORACLE_WHERE",
            "",
            f"- n: {oracle['n']}",
            f"- invalid: {oracle['n_invalid']}",
            f"- exact: {oracle['exact']} ({_pct(oracle['exact_rate'])})",
            f"- canonical fingerprint: {oracle['canonical_fingerprint']} ({_pct(oracle['canonical_rate'])})",
            "",
            "Primary experiment is C0/C1/C2. ORACLE_WHERE only estimates WHERE→WHAT "
            "after the location is supplied and marked as requiring a formula.",
            "",
            "## 13. Causal interpretation",
            "",
            f"Primary template: **Result {report['interpretation']['primary']}**",
            "",
        ]
    )
    if report["interpretation"]["also"]:
        lines.append("Also consistent with: " + ", ".join(report["interpretation"]["also"]))
        lines.append("")
    for note in report["interpretation"]["notes"]:
        lines.append(note)
        lines.append("")
    lines.extend(
        [
            "Question answered:",
            "",
            "> When the expensive global relation-construction problem is removed, "
            "can GLM-5.3-Flash use typed dependency evidence to make a better local "
            "semantic decision?",
            "",
            "Do not read this as expected SpreadsheetBench gain, population accuracy, "
            "or a rule that BOTH cells should be edited.",
            "",
            "Harness not altered on the basis of this probe.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("select", "refresh-windows", "run", "score", "all"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-oracle", action="store_true")
    args = parser.parse_args()
    if args.phase == "select":
        cmd_select(force=args.force)
    elif args.phase == "refresh-windows":
        refresh_windows()
    elif args.phase == "run":
        cmd_run(oracle=not args.no_oracle, force=args.force)
    elif args.phase == "score":
        cmd_score()
    else:
        cmd_select(force=args.force)
        cmd_run(oracle=not args.no_oracle, force=args.force)
        cmd_score()


if __name__ == "__main__":
    main()
