#!/usr/bin/env python3
"""Mechanism probe: Spark target selection with vs without compiled structure.

CONTROL and TREATMENT share one raw-evidence packet. TREATMENT adds only a
deterministic compiled member-run / temporal-axis block generated from the
source workbook. No calc_query, Task IR, Edit Plan, scheduler, writer, or
official scoring. Evaluator gold is loaded only after payloads are frozen.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "benchmark"),
    str(ROOT / "src"),
    str(ROOT / "benchmark/sweagent/formula_index/lib"),
]

from formula_schema import parse_period  # noqa: E402
from run_openrouter_slice import _load_dotenv  # noqa: E402
from workbook_grounding_spine import compile_spine  # noqa: E402
from temporal_spine import compile_temporal_workbook  # noqa: E402
from compiled_context_sidecar_ab import (  # noqa: E402
    IDENTITY as SIDECAR_IDENTITY,
    normalize_response_model,
    source_xlsx,
)
from experiment_config import AUTHORITATIVE_EXPERIMENT_CONFIG  # noqa: E402

TASK = "Financial_Model:05_01"
O7_CLAUSE = (
    "In the Workings Cost sheet, compute total funds raised for all three "
    "tranches from Apr-25 to Jun-33."
)
O6_CLAUSE = (
    "In the Dashboard, update Exit Multiple for second and third tranches "
    "to 2.0x for all deals."
)
FAMILY = "spark"
DECLARED_MODEL = SIDECAR_IDENTITY["declared_model"]
REQUEST_MODEL = SIDECAR_IDENTITY["request_model"]
TEMPERATURE = 0.0
TOP_P = 1.0
PROVIDER = {"allow_fallbacks": True, "require_parameters": True}
MAX_TOKENS = 4096
REASONING_EFFORT: str | None = None
TIMEOUT_SECONDS = 180
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ORDINALS = ("first", "second", "third")
ARTIFACT = ROOT / "structural_projection_discriminator"
AUTHORITY_PATH = ROOT / "authority_loss_by_obligation.csv"
REPORT = ROOT / "SPARK_STRUCTURAL_PROJECTION_DISCRIMINATOR_REPORT.md"


def activate_family(family: str) -> None:
    """Swap only the model identity. Evidence packets stay gold-blind and shared."""
    global FAMILY, DECLARED_MODEL, REQUEST_MODEL, TEMPERATURE, TOP_P, PROVIDER
    global MAX_TOKENS, REASONING_EFFORT, TIMEOUT_SECONDS, ARTIFACT, REPORT
    FAMILY = family
    TEMPERATURE = 0.0
    TOP_P = 1.0
    PROVIDER = {"allow_fallbacks": True, "require_parameters": True}
    if family == "glm":
        glm = AUTHORITATIVE_EXPERIMENT_CONFIG
        DECLARED_MODEL = glm.model
        REQUEST_MODEL = f"openrouter/{glm.model}"
        REASONING_EFFORT = glm.reasoning
        MAX_TOKENS = glm.max_output_tokens
        TIMEOUT_SECONDS = 600
        ARTIFACT = ROOT / "structural_projection_discriminator_glm"
        REPORT = ROOT / "GLM_STRUCTURAL_PROJECTION_DISCRIMINATOR_REPORT.md"
        return
    if family != "spark":
        raise ValueError(f"unknown family: {family}")
    DECLARED_MODEL = SIDECAR_IDENTITY["declared_model"]
    REQUEST_MODEL = SIDECAR_IDENTITY["request_model"]
    REASONING_EFFORT = None
    MAX_TOKENS = 4096
    TIMEOUT_SECONDS = 180
    ARTIFACT = ROOT / "structural_projection_discriminator"
    REPORT = ROOT / "SPARK_STRUCTURAL_PROJECTION_DISCRIMINATOR_REPORT.md"
A1 = re.compile(r"^\$?([A-Za-z]{1,3})\$?(\d+)$")
FENCE_OPEN = re.compile(r"^```(?:json)?\s*", re.I)
FENCE_CLOSE = re.compile(r"\s*```$")
FORBIDDEN_TREATMENT = (
    "should edit",
    "intended cells",
    "correct target",
    "gold",
    "evaluator",
)
OPEN_PRODUCT_DEFECTS = [
    {
        "id": "inspect_wide_range_64_cell_clip",
        "surface": "calc_query inspect",
        "status": "open",
        "note": (
            "inspect LIMIT 64 clips wide ranges (truncated:true). This probe "
            "does not call inspect and does not repair that product defect."
        ),
    }
]
SYSTEM_PROMPT = """You identify spreadsheet cells. You do not write formulas or values.
Use only the supplied workbook evidence. Return strict JSON only, with no markdown and no commentary.
Schema:
{"sheet":"sheet name","ranges":[{"start":"A1","end":"A1"}],"evidence":["IDs or coordinates from the supplied evidence that support the selection"]}
Multiple ranges are allowed. Parse the quoted user instruction and select the cells it asks to modify."""
USER_INSTRUCTIONS = (
    "Identify the cells that the quoted user instruction asks to modify. "
    "Use the supplied workbook evidence. Return only the target set; do not perform the edits."
)
JSON_EXTRACT_POLICY = {
    "strip_markdown_fences": True,
    "salvage_partial_objects": False,
    "identical_both_arms": True,
    "frozen_before_execution": True,
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def col_letter(col: int) -> str:
    out = ""
    n = int(col)
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def a1(row: int, col: int) -> str:
    return f"{col_letter(col)}{row}"


def parse_a1(text: str) -> tuple[int, int] | None:
    match = A1.fullmatch((text or "").replace(" ", "").upper())
    if not match:
        return None
    n = 0
    for ch in match.group(1):
        n = n * 26 + ord(ch) - 64
    return int(match.group(2)), n


def parse_member(text: str) -> str | None:
    match = re.match(r"\s*(first|second|third)\s+tranche\b", (text or "").casefold())
    return match.group(1) if match else None


def month_label(year: int, month: int) -> str:
    return f"{calendar.month_abbr[month]}-{str(year)[-2:]}"


def provider_key() -> str | None:
    _load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    secret = ROOT / ".secrets/openrouter_api_key.b64"
    if not secret.exists():
        return None
    import base64

    try:
        return base64.b64decode(secret.read_text(encoding="ascii").strip(), validate=True).decode("ascii").strip()
    except (ValueError, UnicodeError):
        return None


def resolve_sheet(spine: dict[str, Any], wanted: str, fallback_title: str | None = None) -> dict[str, Any]:
    raw = (wanted or "").strip()
    candidates = [raw]
    if raw.startswith("sheet:"):
        candidates.append(raw.split(":", 1)[1])
    if fallback_title:
        candidates.append(fallback_title)
    compact_wanted = [re.sub(r"[^a-z0-9]+", "", item.casefold()) for item in candidates if item]
    for sheet in spine["sheets"]:
        titles = [
            sheet["title"],
            sheet["id"],
            sheet["id"].split(":")[-1],
        ]
        compact_titles = {re.sub(r"[^a-z0-9]+", "", item.casefold()) for item in titles}
        if any(item in compact_titles and item for item in compact_wanted):
            return sheet
        if raw in titles or raw == sheet["title"]:
            return sheet
    raise AssertionError(f"source sheet not found: {wanted}")


def sheet_by_title(spine: dict[str, Any], wanted: str) -> dict[str, Any]:
    return resolve_sheet(spine, wanted)


def build_member_runs(anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    members = [anchor for anchor in anchors if parse_member(anchor.get("text") or "")]
    runs: list[dict[str, Any]] = []
    by_column: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for anchor in members:
        by_column[(anchor["sheet_id"], anchor["col"])].append(anchor)

    def append_one(group: list[dict[str, Any]]) -> None:
        group = sorted(group, key=lambda item: item["row"])
        if len(group) != 3:
            return
        if {parse_member(item["text"]) for item in group} != set(ORDINALS):
            return
        rows = [item["row"] for item in group]
        if rows != list(range(rows[0], rows[0] + 3)):
            return
        runs.append(
            {
                "orientation": "vertical",
                "sheet_id": group[0]["sheet_id"],
                "start_row": rows[0],
                "end_row": rows[-1],
                "col": group[0]["col"],
                "member_cells": [a1(item["row"], item["col"]) for item in group],
                "member_cell_ids": [item["cell_id"] for item in group],
                "member_labels": [item["text"].strip() for item in group],
                "member_identities": [parse_member(item["text"]) for item in group],
            }
        )

    for group in by_column.values():
        ordered = sorted(group, key=lambda item: item["row"])
        windows = [ordered[index : index + 3] for index in range(len(ordered) - 2)] if len(ordered) > 3 else [ordered]
        for window in windows:
            append_one(window)
    return runs


def attach_parents(runs: list[dict[str, Any]], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pos = {(item["sheet_id"], item["row"], item["col"]): item for item in anchors}
    out = []
    for run in runs:
        parent = by_pos.get((run["sheet_id"], run["start_row"] - 2, run["col"]))
        item = dict(run)
        item["parent"] = None
        if parent:
            item["parent"] = {
                "text": parent["text"],
                "address": parent["address"],
                "cell_id": parent["cell_id"],
                "row": parent["row"],
                "col": parent["col"],
            }
        out.append(item)
    return out


def compile_source() -> dict[str, Any]:
    xlsx = source_xlsx("Financial_Model", "05_01")
    if "gold" in str(xlsx).casefold():
        raise AssertionError("source path looks like evaluator gold")
    spine = compile_spine(xlsx, workbook_key=TASK)
    temporal = compile_temporal_workbook(xlsx, closure=True)
    if not spine.get("readable") or not temporal.get("readable"):
        raise RuntimeError("source compile failed")
    return {"xlsx": xlsx, "spine": spine, "temporal": temporal}


def workings_runs(spine: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sheet = sheet_by_title(spine, "Workings Cost Sheet")
    anchors = [item for item in spine["text_anchors"] if item["sheet_id"] == sheet["id"]]
    runs = attach_parents(build_member_runs(anchors), anchors)
    return sheet, [run for run in runs if run["orientation"] == "vertical" and run.get("parent")]


def temporal_axis(temporal: dict[str, Any], sheet_title: str, start_label: str, end_label: str) -> dict[str, Any]:
    start_period = parse_period(start_label)
    end_period = parse_period(end_label)
    if not start_period or not end_period:
        raise AssertionError("requested period labels are not mechanically parseable")
    coords = [
        coord
        for coord in temporal.get("coordinates") or []
        if coord.get("sheet_title") == sheet_title
        and isinstance(coord.get("period"), dict)
        and coord["period"].get("year")
        and coord["period"].get("month")
    ]
    def match(period: dict[str, int]) -> list[dict[str, Any]]:
        return [
            coord
            for coord in coords
            if coord["period"].get("year") == period["year"]
            and coord["period"].get("month") == period["month"]
        ]
    starts = match(start_period)
    ends = match(end_period)
    if not starts or not ends:
        raise AssertionError("requested temporal extent is not represented on the source sheet")
    start = min(starts, key=lambda item: (item["row"], item["col"]))
    end = min(
        (item for item in ends if item["row"] == start["row"] and item["col"] >= start["col"]),
        key=lambda item: item["col"],
        default=min(ends, key=lambda item: (item["row"], item["col"])),
    )
    axis_coords = [
        coord
        for coord in coords
        if coord["row"] == start["row"] and start["col"] <= coord["col"] <= end["col"]
    ]
    axis_coords.sort(key=lambda item: item["col"])
    return {
        "sheet": sheet_title,
        "orientation": "column",
        "header_row": start["row"],
        "start": {
            "label": start_label,
            "address": start["address"],
            "cell_id": start["cell_id"],
            "row": start["row"],
            "col": start["col"],
            "period": start["period"],
            "header_text": start.get("header_text"),
        },
        "end": {
            "label": end_label,
            "address": end["address"],
            "cell_id": end["cell_id"],
            "row": end["row"],
            "col": end["col"],
            "period": end["period"],
            "header_text": end.get("header_text"),
        },
        "coordinates": [
            {
                "address": coord["address"],
                "cell_id": coord["cell_id"],
                "row": coord["row"],
                "col": coord["col"],
                "label": month_label(int(coord["period"]["year"]), int(coord["period"]["month"])),
                "period": coord["period"],
            }
            for coord in axis_coords
        ],
    }


def verify_o7_source(sheet: dict[str, Any], runs: list[dict[str, Any]], axis: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "Portfolio Building MoM": "B11:B13",
        "Portfolio Building Cumulative": "B17:B19",
        "Ticket Size per Portfolio": "B23:B25",
        "Total Fund Raised": "B29:B31",
    }
    found = {}
    for run in runs:
        parent = (run.get("parent") or {}).get("text") or ""
        extent = f"{run['member_cells'][0]}:{run['member_cells'][-1]}"
        found[parent] = extent
    missing = {name: extent for name, extent in expected.items() if found.get(name) != extent}
    if missing:
        raise AssertionError(f"source member runs do not match known Workings Cost layout: {missing} vs {found}")
    if axis["start"]["label"] != "Apr-25" or axis["end"]["label"] != "Jun-33":
        raise AssertionError("temporal boundaries were not recovered from source")
    return {
        "sheet_title": sheet["title"],
        "sheet_id": sheet["id"],
        "verified_member_runs": expected,
        "parent_anchors": {
            name: next(run["parent"] for run in runs if (run.get("parent") or {}).get("text") == name)
            for name in expected
        },
        "temporal_start": axis["start"],
        "temporal_end": axis["end"],
        "gold_used": False,
    }


def raw_label_facts(spine: dict[str, Any], sheet: dict[str, Any], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted_rows = set()
    for run in runs:
        wanted_rows.update(range(run["start_row"] - 2, run["end_row"] + 1))
        wanted_rows.add(run["end_row"] + 1)
    facts = []
    for anchor in spine["text_anchors"]:
        if anchor["sheet_id"] != sheet["id"]:
            continue
        if anchor["col"] not in {2, 3}:
            continue
        if anchor["row"] not in wanted_rows:
            continue
        facts.append(
            {
                "id": f"RAW:{anchor['address']}",
                "cell_id": anchor["cell_id"],
                "address": anchor["address"],
                "row": anchor["row"],
                "col": anchor["col"],
                "text": anchor["text"],
            }
        )
    facts.sort(key=lambda item: (item["row"], item["col"]))
    return facts


def raw_period_facts(axis: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    seen: set[str] = set()
    for coord in axis["coordinates"]:
        if coord["cell_id"] in seen:
            continue
        seen.add(coord["cell_id"])
        facts.append(
            {
                "id": f"RAW:{coord['address']}",
                "cell_id": coord["cell_id"],
                "address": coord["address"],
                "row": coord["row"],
                "col": coord["col"],
                "text": coord["label"],
                "kind": "period_header",
            }
        )
    return facts


def compiled_relations_block(runs: list[dict[str, Any]], axis: dict[str, Any]) -> str:
    lines = ["COMPILED STRUCTURAL RELATIONS", ""]
    for index, run in enumerate(runs, start=1):
        parent = run["parent"]
        lines.extend(
            [
                f"member_run R{index}",
                f"  parent/header: {parent['text']}",
                f"  parent_coordinate: {parent['address']}",
                f"  member cells: {run['member_cells'][0]}:{run['member_cells'][-1]}",
                f"  member labels: {', '.join(run['member_labels'])}",
                "  provenance: source workbook coordinates",
                "",
            ]
        )
    lines.extend(
        [
            "temporal_axis T1",
            f"  sheet: {axis['sheet']}",
            f"  orientation: {axis['orientation']}",
            "  requested boundary labels represented:",
            f"    Apr-25 → {axis['start']['address']}",
            f"    Jun-33 → {axis['end']['address']}",
            "  provenance: source workbook header coordinates",
        ]
    )
    text = "\n".join(lines) + "\n"
    lowered = text.casefold()
    if "o29:di31" in lowered.replace(" ", ""):
        raise AssertionError("compiled block leaked evaluator rectangle O29:DI31")
    if any(token in lowered for token in FORBIDDEN_TREATMENT):
        raise AssertionError("compiled block contains forbidden evaluator language")
    return text


def common_packet(clause: str, sheet: dict[str, Any], raw_facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "user_clause": clause,
        "sheet": {"title": sheet["title"], "id": sheet["id"]},
        "raw_workbook_facts": raw_facts,
        "instructions": USER_INSTRUCTIONS,
        "response_schema": {
            "sheet": "sheet name",
            "ranges": [{"start": "A1", "end": "A1"}],
            "evidence": ["IDs or coordinates from the supplied evidence that support the selection"],
        },
    }


def render_user(packet: dict[str, Any], compiled_block: str | None) -> str:
    facts = packet["raw_workbook_facts"]
    lines = [
        f'Quoted user instruction: "{packet["user_clause"]}"',
        "",
        USER_INSTRUCTIONS,
        "",
        f'Sheet identity: {packet["sheet"]["title"]} ({packet["sheet"]["id"]})',
        "",
        "RAW WORKBOOK FACTS",
    ]
    for fact in facts:
        extra = f" kind={fact['kind']}" if fact.get("kind") else ""
        lines.append(f"- {fact['id']} {fact['address']} text={fact['text']!r}{extra}")
    if compiled_block:
        lines.extend(["", compiled_block.rstrip(), ""])
    lines.extend(
        [
            "",
            "Return strict JSON only with keys sheet, ranges, evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def request_body(system: str, user: str) -> dict[str, Any]:
    # Sidecar/LiteLLM request identity is openrouter/<declared>. Direct
    # OpenRouter chat/completions requires the declared model ID on the wire.
    body: dict[str, Any] = {
        "model": DECLARED_MODEL,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "provider": PROVIDER,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if REASONING_EFFORT:
        body["reasoning"] = {"effort": REASONING_EFFORT}
    return body


def extract_json(text: str) -> tuple[Any, bool]:
    stripped = (text or "").strip()
    if JSON_EXTRACT_POLICY["strip_markdown_fences"] and stripped.startswith("```"):
        stripped = FENCE_OPEN.sub("", stripped)
        stripped = FENCE_CLOSE.sub("", stripped).strip()
    try:
        return json.loads(stripped), True
    except json.JSONDecodeError:
        return None, False


def freeze_o7(destination: Path) -> dict[str, Any]:
    compiled = compile_source()
    spine = compiled["spine"]
    sheet, runs = workings_runs(spine)
    axis = temporal_axis(compiled["temporal"], sheet["title"], "Apr-25", "Jun-33")
    verification = verify_o7_source(sheet, runs, axis)
    raw_facts = raw_label_facts(spine, sheet, runs) + raw_period_facts(axis)
    packet = common_packet(O7_CLAUSE, sheet, raw_facts)
    compiled_block = compiled_relations_block(runs, axis)
    control_user = render_user(packet, None)
    treatment_user = render_user(packet, compiled_block)
    if "calc_query" in control_user or "calc_query" in treatment_user:
        raise AssertionError("calc_query leaked into mechanism packets")
    control_body = request_body(SYSTEM_PROMPT, control_user)
    treatment_body = request_body(SYSTEM_PROMPT, treatment_user)
    control_hash = digest(control_body)
    treatment_hash = digest(treatment_body)
    if digest(packet) != digest(common_packet(O7_CLAUSE, sheet, raw_facts)):
        raise AssertionError("common packet is not stable")
    if control_hash == treatment_hash:
        raise AssertionError("CONTROL and TREATMENT payloads are identical")
    if compiled_block not in treatment_user:
        raise AssertionError("TREATMENT is missing the compiled block")
    if compiled_block in control_user:
        raise AssertionError("CONTROL received the compiled block")
    if control_user.replace(compiled_block, "") != treatment_user.replace(compiled_block, ""):
        # CONTROL never contains the block; compare by reconstructing.
        reconstructed = render_user(packet, compiled_block)
        if reconstructed != treatment_user:
            raise AssertionError("TREATMENT is not CONTROL plus the compiled block")
    source_record = {
        "task": TASK,
        "obligation": "O7",
        "xlsx": str(compiled["xlsx"]),
        "xlsx_sha256": hashlib.sha256(compiled["xlsx"].read_bytes()).hexdigest(),
        "spine_sha256": digest({k: spine[k] for k in ("workbook_id", "sheets", "text_anchors") if k in spine}),
        "temporal_sha256": digest({"n_coordinates": compiled["temporal"].get("n_coordinates"), "golden_used": compiled["temporal"].get("golden_used")}),
        "verification": verification,
        "member_runs": runs,
        "temporal_axis": {
            "sheet": axis["sheet"],
            "orientation": axis["orientation"],
            "header_row": axis["header_row"],
            "start": axis["start"],
            "end": axis["end"],
            "n_coordinates": len(axis["coordinates"]),
        },
        "gold_loaded": False,
        "written_at": now(),
    }
    write_json(destination / "source" / "o7_provenance.json", source_record)
    write_json(destination / "source" / "o7_raw_facts.json", raw_facts)
    (destination / "source" / "o7_compiled_relations.txt").write_text(compiled_block, encoding="utf-8")
    payloads = {
        "CONTROL": {
            "arm": "CONTROL",
            "system": SYSTEM_PROMPT,
            "user": control_user,
            "request_body": control_body,
            "request_sha256": control_hash,
            "json_extract_policy": JSON_EXTRACT_POLICY,
        },
        "TREATMENT": {
            "arm": "TREATMENT",
            "system": SYSTEM_PROMPT,
            "user": treatment_user,
            "request_body": treatment_body,
            "request_sha256": treatment_hash,
            "json_extract_policy": JSON_EXTRACT_POLICY,
        },
    }
    write_json(destination / "payloads" / "o7_control.json", payloads["CONTROL"])
    write_json(destination / "payloads" / "o7_treatment.json", payloads["TREATMENT"])
    raw_control = {k: v for k, v in packet.items()}
    raw_treatment_common = {k: v for k, v in packet.items()}
    canonical_diff = {
        "common_packet_sha256": digest(packet),
        "raw_facts_equal": digest(raw_control) == digest(raw_treatment_common),
        "system_prompt_equal": payloads["CONTROL"]["system"] == payloads["TREATMENT"]["system"],
        "json_extract_policy_equal": True,
        "treatment_only_delta": "compiled_structural_relations_block",
        "treatment_delta_sha256": hashlib.sha256(compiled_block.encode()).hexdigest(),
        "control_request_sha256": control_hash,
        "treatment_request_sha256": treatment_hash,
        "forbidden_language_absent": True,
        "evaluator_rectangle_absent": "O29:DI31" not in compiled_block and "O29:DI31" not in control_user,
        "calc_query_absent": True,
        "gold_used_in_payloads": False,
        "written_at": now(),
    }
    write_json(destination / "payloads" / "o7_canonical_diff.json", canonical_diff)
    spec = {
        "experiment": f"{FAMILY}_structural_projection_discriminator",
        "task": TASK,
        "primary_obligation": "O7",
        "fallback_obligation": "O6",
        "fallback_gate": "NO_HEADROOM_ON_O7",
        "model": {
            "family": FAMILY,
            "declared_model": DECLARED_MODEL,
            "request_model": REQUEST_MODEL,
            "openrouter_wire_model": DECLARED_MODEL,
            "wire_model_note": (
                "SWE-agent/LiteLLM request identity is openrouter/<declared>; "
                "direct OpenRouter chat/completions uses the declared model ID."
            ),
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "reasoning_effort": REASONING_EFFORT,
            "provider": PROVIDER,
            "max_tokens": MAX_TOKENS,
            "source_identity": (
                "experiment_config.AUTHORITATIVE_EXPERIMENT_CONFIG"
                if FAMILY == "glm"
                else "compiled_context_sidecar_ab.IDENTITY"
            ),
        },
        "repeats": 4,
        "order": [
            ["CONTROL", "TREATMENT"],
            ["TREATMENT", "CONTROL"],
            ["CONTROL", "TREATMENT"],
            ["TREATMENT", "CONTROL"],
        ],
        "no_calc_query": True,
        "no_task_ir": True,
        "no_edit_plan": True,
        "json_extract_policy": JSON_EXTRACT_POLICY,
        "open_product_defects": OPEN_PRODUCT_DEFECTS,
        "payload_hashes": {
            "control": control_hash,
            "treatment": treatment_hash,
            "common_packet": digest(packet),
        },
        "written_at": now(),
    }
    write_json(destination / "spec.json", spec)
    return {
        "sheet": sheet,
        "runs": runs,
        "axis": axis,
        "packet": packet,
        "compiled_block": compiled_block,
        "payloads": payloads,
        "canonical_diff": canonical_diff,
        "spec": spec,
        "source": source_record,
    }


def load_obligation_gold(obligation_id: str) -> list[str]:
    csv.field_size_limit(100_000_000)
    with AUTHORITY_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["task"] == TASK and row["obligation_id"] == obligation_id and row["row_type"] == "OBLIGATION":
                return json.loads(row["gold_target_cells"] or "[]")
    raise AssertionError(f"evaluator gold missing for {obligation_id}")


def gold_cell_ids(displays: list[str], spine: dict[str, Any]) -> set[str]:
    title_to_index = spine.get("title_to_index") or {
        sheet["title"]: int(sheet["id"].split("s")[-1]) for sheet in spine["sheets"]
    }
    out = set()
    for item in displays:
        title, address = item.rsplit("!", 1)
        parsed = parse_a1(address)
        if parsed is None:
            continue
        row, col = parsed
        index = title_to_index[title]
        out.add(f"cell:s{index:02d}:r{row}:c{col}")
    return out


def predicted_cell_ids(parsed: Any, fallback_sheet: str, spine: dict[str, Any]) -> tuple[set[str], dict[str, Any]]:
    meta = {"sheet": None, "ranges": [], "rows": [], "start_col": None, "end_col": None, "sheet_raw": None}
    if not isinstance(parsed, dict):
        return set(), meta
    sheet_name = parsed.get("sheet") or fallback_sheet
    meta["sheet_raw"] = parsed.get("sheet")
    meta["sheet"] = sheet_name
    try:
        sheet = resolve_sheet(spine, str(sheet_name), fallback_title=fallback_sheet)
        index = int(sheet["id"].split("s")[-1])
    except AssertionError:
        return set(), meta
    cells: set[str] = set()
    rows: set[int] = set()
    cols: set[int] = set()
    ranges = parsed.get("ranges") or []
    if not isinstance(ranges, list):
        return set(), meta
    for item in ranges:
        if not isinstance(item, dict):
            continue
        start = parse_a1(str(item.get("start") or ""))
        end = parse_a1(str(item.get("end") or item.get("start") or ""))
        if start is None or end is None:
            continue
        r1, c1 = start
        r2, c2 = end
        meta["ranges"].append({"start": a1(r1, c1), "end": a1(r2, c2)})
        for row in range(min(r1, r2), max(r1, r2) + 1):
            for col in range(min(c1, c2), max(c1, c2) + 1):
                cells.add(f"cell:s{index:02d}:r{row}:c{col}")
                rows.add(row)
                cols.add(col)
    meta["rows"] = sorted(rows)
    meta["start_col"] = min(cols) if cols else None
    meta["end_col"] = max(cols) if cols else None
    return cells, meta


def selection_class(pred: set[str], gold: set[str], pred_meta: dict[str, Any], gold_meta: dict[str, Any]) -> str:
    if pred and pred == gold:
        return "exact"
    member_ok = pred_meta.get("rows") == gold_meta.get("rows") and bool(pred_meta.get("rows"))
    period_ok = (
        pred_meta.get("start_col") == gold_meta.get("start_col")
        and pred_meta.get("end_col") == gold_meta.get("end_col")
        and pred_meta.get("start_col") is not None
    )
    if member_ok and not period_ok:
        return "correct_member_run_wrong_period_extent"
    if period_ok and not member_ok:
        return "wrong_member_run_correct_period_extent"
    return "both_wrong"


def score_prediction(parsed: Any, parse_ok: bool, gold: set[str], gold_meta: dict[str, Any], spine: dict[str, Any], sheet_title: str) -> dict[str, Any]:
    pred, pred_meta = predicted_cell_ids(parsed, sheet_title, spine) if parse_ok else (set(), {"sheet": None, "ranges": [], "rows": [], "start_col": None, "end_col": None})
    tp = pred & gold
    fp = pred - gold
    fn = gold - pred
    recall = len(tp) / len(gold) if gold else None
    precision = len(tp) / len(pred) if pred else None
    f1 = None
    if recall is not None and precision is not None and (recall + precision):
        f1 = 2 * recall * precision / (recall + precision)
    return {
        "parse_valid": parse_ok,
        "predicted_cell_count": len(pred),
        "gold_cell_count": len(gold),
        "true_positives": len(tp),
        "false_positives": len(fp),
        "false_negatives": len(fn),
        "target_recall": recall,
        "target_precision": precision,
        "f1": f1,
        "exact_target_set_equality": bool(parse_ok and pred == gold and gold),
        "selected_tranche_member_rows": pred_meta.get("rows") or [],
        "selected_start_period_column": pred_meta.get("start_col"),
        "selected_end_period_column": pred_meta.get("end_col"),
        "gold_member_rows": gold_meta.get("rows") or [],
        "gold_start_period_column": gold_meta.get("start_col"),
        "gold_end_period_column": gold_meta.get("end_col"),
        "error_class": selection_class(pred, gold, pred_meta, gold_meta) if parse_ok else "parse_invalid",
        "predicted_sheet": pred_meta.get("sheet"),
        "predicted_sheet_raw": pred_meta.get("sheet_raw"),
        "predicted_ranges": pred_meta.get("ranges") or [],
    }


def gold_extent(gold: set[str]) -> dict[str, Any]:
    rows: set[int] = set()
    cols: set[int] = set()
    for cell in gold:
        match = re.search(r":r(\d+):c(\d+)$", cell)
        if not match:
            continue
        rows.add(int(match.group(1)))
        cols.add(int(match.group(2)))
    return {
        "rows": sorted(rows),
        "start_col": min(cols) if cols else None,
        "end_col": max(cols) if cols else None,
    }


def call_spark(body: dict[str, Any]) -> dict[str, Any]:
    key = provider_key()
    record = {
        "request_body": body,
        "request_sha256": digest(body),
        "declared_model": DECLARED_MODEL,
        "request_model": REQUEST_MODEL,
        "openrouter_wire_model": body.get("model"),
        "temperature": body.get("temperature"),
        "top_p": body.get("top_p"),
        "reasoning_effort": REASONING_EFFORT,
        "provider": body.get("provider"),
        "started_at": now(),
    }
    if not key:
        record.update({"failure_class": "MODEL_ACCESS_FAILURE", "detail": "OPENROUTER_API_KEY missing", "raw_response": None})
        return record
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-Title": f"{FAMILY}-structural-projection-discriminator",
            "HTTP-Referer": "https://github.com/librecalc-mcp",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        record.update(
            {
                "failure_class": "PROVIDER_INFRA",
                "detail": f"HTTP {exc.code}",
                "raw_response": {"status": exc.code, "body": exc.read().decode(errors="replace")},
                "finished_at": now(),
            }
        )
        return record
    except Exception as exc:
        record.update(
            {
                "failure_class": "PROVIDER_INFRA",
                "detail": f"{type(exc).__name__}: {exc}",
                "raw_response": None,
                "finished_at": now(),
            }
        )
        return record
    message = ((raw.get("choices") or [{}])[0].get("message") or {})
    text = message.get("content") or ""
    parsed, parse_ok = extract_json(text)
    record.update(
        {
            "failure_class": None,
            "raw_response": raw,
            "response_model": normalize_response_model(raw.get("model")),
            "finish_reason": (raw.get("choices") or [{}])[0].get("finish_reason"),
            "usage": raw.get("usage") or {},
            "text": text,
            "parsed": parsed,
            "parse_valid": parse_ok,
            "finished_at": now(),
        }
    )
    return record


def pair_order(repeat: int) -> list[str]:
    return ["CONTROL", "TREATMENT"] if repeat % 2 == 1 else ["TREATMENT", "CONTROL"]


def run_o7_repeats(frozen: dict[str, Any], destination: Path, *, dry_run: bool = False) -> dict[str, Any]:
    ledger = []
    for repeat in range(1, 5):
        order = pair_order(repeat)
        pair: dict[str, Any] = {"repeat": repeat, "order": order, "arms": {}}
        for arm in order:
            payload = frozen["payloads"][arm]
            body = payload["request_body"]
            write_json(destination / "payloads" / f"o7_r{repeat}_{arm.lower()}_request.json", body)
            if dry_run:
                call = {
                    "failure_class": None,
                    "dry_run": True,
                    "request_sha256": payload["request_sha256"],
                    "parse_valid": False,
                    "parsed": None,
                    "text": "",
                    "response_model": None,
                }
            else:
                print(f"CALL O7 r{repeat} {arm}", flush=True)
                call = call_spark(body)
                time.sleep(1)
            write_json(destination / "ledgers" / f"o7_r{repeat}_{arm.lower()}.json", call)
            pair["arms"][arm] = call
        censored = any(pair["arms"][arm].get("failure_class") for arm in ("CONTROL", "TREATMENT"))
        pair["censored"] = bool(censored)
        ledger.append(pair)
        write_json(destination / "ledgers" / f"o7_r{repeat}_pair.json", pair)
    write_json(destination / "ledgers" / "o7_request_response_ledger.json", ledger)
    return {"pairs": ledger}


def measure_o7(frozen: dict[str, Any], ledger: dict[str, Any], destination: Path) -> dict[str, Any]:
    spine = compile_source()["spine"]
    gold_display = load_obligation_gold("O7")
    gold = gold_cell_ids(gold_display, spine)
    gold_meta = gold_extent(gold)
    write_json(
        destination / "measurement" / "o7_gold.json",
        {
            "obligation": "O7",
            "loaded_after_payload_freeze": True,
            "gold_display_count": len(gold_display),
            "gold_cell_count": len(gold),
            "gold_extent": gold_meta,
            "loaded_at": now(),
        },
    )
    rows = []
    for pair in ledger["pairs"]:
        for arm in ("CONTROL", "TREATMENT"):
            call = pair["arms"][arm]
            infra = bool(call.get("failure_class"))
            parsed = call.get("parsed")
            parse_ok = bool(call.get("parse_valid")) and not infra
            metrics = score_prediction(parsed, parse_ok, gold, gold_meta, spine, frozen["sheet"]["title"])
            rows.append(
                {
                    "obligation": "O7",
                    "repeat": pair["repeat"],
                    "arm": arm,
                    "order": pair["order"],
                    "censored": pair["censored"] or infra,
                    "failure_class": call.get("failure_class"),
                    "declared_model": DECLARED_MODEL,
                    "request_model": call.get("request_model") or REQUEST_MODEL,
                    "response_model": call.get("response_model"),
                    "request_sha256": call.get("request_sha256") or frozen["payloads"][arm]["request_sha256"],
                    **metrics,
                }
            )
    write_json(destination / "measurement" / "o7_metrics.json", rows)
    with (destination / "measurement" / "o7_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["obligation"])
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": rows, "gold_cell_count": len(gold), "gold_meta": gold_meta}


def paired_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_repeat: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_repeat[row["repeat"]][row["arm"]] = row
    out = []
    for repeat, arms in sorted(by_repeat.items()):
        control = arms.get("CONTROL") or {}
        treatment = arms.get("TREATMENT") or {}
        usable = not control.get("censored") and not treatment.get("censored")
        control_exact = bool(control.get("exact_target_set_equality"))
        treatment_exact = bool(treatment.get("exact_target_set_equality"))
        control_f1 = control.get("f1")
        treatment_f1 = treatment.get("f1")
        improved = usable and (
            (treatment_exact and not control_exact)
            or (
                control_f1 is not None
                and treatment_f1 is not None
                and treatment_f1 > control_f1
                and not (control_exact and not treatment_exact)
            )
        )
        reversal = usable and (
            (control_exact and not treatment_exact)
            or (
                control_f1 is not None
                and treatment_f1 is not None
                and control_f1 > treatment_f1
                and not (treatment_exact and not control_exact)
            )
        )
        precision_collapse = usable and (
            (control.get("target_precision") or 0) > 0
            and (treatment.get("target_precision") or 0) < 0.5 * (control.get("target_precision") or 0)
            and not treatment_exact
        )
        out.append(
            {
                "repeat": repeat,
                "usable": usable,
                "control_exact": control_exact,
                "treatment_exact": treatment_exact,
                "strict_treatment_improvement": improved and not reversal,
                "strict_control_reversal": reversal and not improved,
                "precision_collapse": precision_collapse,
                "control_f1": control_f1,
                "treatment_f1": treatment_f1,
            }
        )
    return out


def verdict_o7(comparisons: list[dict[str, Any]], planned: int = 4) -> str:
    usable = [item for item in comparisons if item["usable"]]
    if len(usable) < 3:
        return "PROVIDER_CENSORED"
    complete = usable
    treatment_exact = sum(1 for item in complete if item["treatment_exact"])
    control_exact = sum(1 for item in complete if item["control_exact"])
    if control_exact >= 3:
        return "NO_HEADROOM_ON_O7"
    improvements = sum(1 for item in complete if item["strict_treatment_improvement"])
    reversals = sum(1 for item in complete if item["strict_control_reversal"])
    collapse = any(item["precision_collapse"] for item in complete)
    treatment_bar = 3 if len(complete) >= 4 else len(complete)
    if (
        treatment_exact >= treatment_bar
        and control_exact <= 1
        and not collapse
        and improvements >= 2
        and reversals == 0
    ):
        return "STRUCTURAL_PROJECTION_CASHES_OUT"
    if improvements and reversals:
        return "STRUCTURAL_PROJECTION_MIXED"
    return "STRUCTURAL_PROJECTION_NO_GAIN"


def identity_audit(ledger: dict[str, Any]) -> dict[str, Any]:
    rows = []
    ok = True
    for pair in ledger["pairs"]:
        for arm, call in pair["arms"].items():
            response_model = normalize_response_model(call.get("response_model"))
            request_model = call.get("request_model") or REQUEST_MODEL
            arm_ok = (
                (call.get("declared_model") or DECLARED_MODEL) == DECLARED_MODEL
                and request_model in {DECLARED_MODEL, REQUEST_MODEL}
                and call.get("temperature") in {None, 0, 0.0}
                and (call.get("top_p") in {None, 1, 1.0} or "request_body" in call)
                and (response_model is None or response_model.startswith(DECLARED_MODEL))
                and "\\" not in (response_model or "")
            )
            if call.get("request_body"):
                body = call["request_body"]
                reasoning_ok = (
                    body.get("reasoning") == {"effort": REASONING_EFFORT}
                    if REASONING_EFFORT
                    else "reasoning" not in body
                )
                arm_ok = (
                    arm_ok
                    and body.get("model") == DECLARED_MODEL
                    and body.get("temperature") == 0
                    and body.get("top_p") == 1
                    and reasoning_ok
                )
            ok = ok and (arm_ok or bool(call.get("failure_class")))
            rows.append(
                {
                    "repeat": pair["repeat"],
                    "arm": arm,
                    "declared_model": DECLARED_MODEL,
                    "request_model": request_model,
                    "response_model": response_model,
                    "ok": arm_ok,
                }
            )
    return {"ok": ok, "rows": rows}


def replay_o6_relation(spine: dict[str, Any]) -> dict[str, Any]:
    import output_role_occurrence_contrast as role

    _case, included, excluded = role.frozen_members()
    indices = role.build_indices(spine)
    raw_sheet = role.load_raw_styles()
    copied = [
        role.copied_header_path(start, indices, spine, raw_sheet, set(), set(), accepted=True)
        for start in included
    ]
    excluded_paths = [
        role.copied_header_path(start, indices, spine, raw_sheet, set(), set(), accepted=False)
        for start in excluded
    ]
    def strip_gold(path: dict[str, Any]) -> dict[str, Any]:
        clean = dict(path)
        clean["endpoints"] = [
            {k: v for k, v in endpoint.items() if k not in {"is_gold", "false_endpoint", "endpoint_role_evidence"}}
            for endpoint in path.get("endpoints") or []
        ]
        return clean
    return {
        "included_occurrences": [
            {"address": item["address"], "cell_id": item["cell_id"], "member_identity": item["member_identity"], "text": item.get("text")}
            for item in included
        ],
        "excluded_occurrences": [
            {"address": item["address"], "cell_id": item["cell_id"], "member_identity": item["member_identity"], "text": item.get("text")}
            for item in excluded
        ],
        "copied_header_paths": [strip_gold(path) for path in copied],
        "excluded_member_paths": [strip_gold(path) for path in excluded_paths],
        "gold_used": False,
    }


def o6_compiled_block(relation: dict[str, Any]) -> str:
    lines = ["COMPILED STRUCTURAL RELATIONS", "", "occurrence identities"]
    for item in relation["included_occurrences"] + relation["excluded_occurrences"]:
        membership = "allowed Second/Third" if item["member_identity"] in {"second", "third"} else "excluded First"
        lines.append(f"  {item['address']} {item['member_identity']} ({membership})")
    lines.append("")
    for path in relation["copied_header_paths"]:
        lines.append(f"copied_header_path from {path['start_address']}")
        lines.append(f"  sequence: {', '.join(path.get('relation_sequence') or [])}")
        lines.append(f"  intermediates: {', '.join(path.get('intermediate_nodes') or [])}")
        if path.get("month_header"):
            lines.append(f"  month_header: {path['month_header']}")
        if path.get("numbers_header"):
            lines.append(f"  numbers_header: {path['numbers_header']}")
        if path.get("source_formula_rows"):
            rows = path["source_formula_rows"]
            lines.append(f"  contiguous_formula_bearing_month_rows: {rows[0]}:{rows[-1]}")
        endpoints = [item["endpoint_display"] for item in path.get("endpoints") or []]
        if endpoints:
            lines.append(f"  numbers_side_structural_endpoints: {', '.join(endpoints)}")
        lines.append("  provenance: source workbook coordinates")
        lines.append("")
    text = "\n".join(lines) + "\n"
    lowered = text.casefold()
    if any(token in lowered for token in ("correct", "intended", "should edit", "gold")):
        raise AssertionError("O6 compiled block contains forbidden evaluator language")
    return text


def o6_raw_facts(spine: dict[str, Any], relation: dict[str, Any]) -> list[dict[str, Any]]:
    cells = {}
    dashboard = sheet_by_title(spine, "Dashboard")
    for item in spine["text_anchors"]:
        if item["sheet_id"] != dashboard["id"]:
            continue
        if item["row"] <= 60 and item["col"] <= 12:
            cells[item["cell_id"]] = {
                "id": f"RAW:{item['address']}",
                "cell_id": item["cell_id"],
                "address": item["address"],
                "row": item["row"],
                "col": item["col"],
                "text": item["text"],
            }
    for path in relation["copied_header_paths"]:
        for endpoint in path.get("endpoints") or []:
            match = re.search(r":r(\d+):c(\d+)$", endpoint["endpoint"])
            if not match:
                continue
            row, col = int(match.group(1)), int(match.group(2))
            cells.setdefault(
                endpoint["endpoint"],
                {
                    "id": f"RAW:{a1(row, col)}",
                    "cell_id": endpoint["endpoint"],
                    "address": a1(row, col),
                    "row": row,
                    "col": col,
                    "text": None,
                    "kind": "occupied_or_formula_cell",
                },
            )
    return sorted(cells.values(), key=lambda item: (item["row"], item["col"]))


def freeze_o6(destination: Path, spine: dict[str, Any]) -> dict[str, Any]:
    relation = replay_o6_relation(spine)
    write_json(destination / "source" / "o6_provenance.json", relation)
    sheet = sheet_by_title(spine, "Dashboard")
    packet = common_packet(O6_CLAUSE, sheet, o6_raw_facts(spine, relation))
    compiled_block = o6_compiled_block(relation)
    (destination / "source" / "o6_compiled_relations.txt").write_text(compiled_block, encoding="utf-8")
    payloads = {
        "CONTROL": {
            "arm": "CONTROL",
            "system": SYSTEM_PROMPT,
            "user": render_user(packet, None),
            "request_body": request_body(SYSTEM_PROMPT, render_user(packet, None)),
        },
        "TREATMENT": {
            "arm": "TREATMENT",
            "system": SYSTEM_PROMPT,
            "user": render_user(packet, compiled_block),
            "request_body": request_body(SYSTEM_PROMPT, render_user(packet, compiled_block)),
        },
    }
    for arm, payload in payloads.items():
        payload["request_sha256"] = digest(payload["request_body"])
        payload["json_extract_policy"] = JSON_EXTRACT_POLICY
        write_json(destination / "payloads" / f"o6_{arm.lower()}.json", payload)
    write_json(
        destination / "payloads" / "o6_canonical_diff.json",
        {
            "common_packet_sha256": digest(packet),
            "control_request_sha256": payloads["CONTROL"]["request_sha256"],
            "treatment_request_sha256": payloads["TREATMENT"]["request_sha256"],
            "treatment_only_delta": "compiled_output_occurrence_relations",
            "gold_used_in_payloads": False,
            "written_at": now(),
        },
    )
    return {"sheet": sheet, "payloads": payloads, "packet": packet, "relation": relation}


def extra_o6_flags(parsed: Any, gold: set[str], spine: dict[str, Any]) -> dict[str, Any]:
    pred, _meta = predicted_cell_ids(parsed, "Dashboard", spine) if isinstance(parsed, dict) else (set(), {})
    first_tranche = {cell for cell in pred if re.search(r":c4$", cell) or "D22" in json.dumps(parsed or {})}
    # Measurement-only leakage flags from source addresses, not gold construction.
    display = {(re.search(r":r(\d+):c(\d+)$", cell).group(1), re.search(r":r(\d+):c(\d+)$", cell).group(2)) for cell in pred if re.search(r":r(\d+):c(\d+)$", cell)}
    addresses = {a1(int(row), int(col)) for row, col in display}
    return {
        "first_tranche_false_selections": sorted(addr for addr in addresses if addr in {"D22", "G15", "E43", "D43"}),
        "ticket_size_occurrence_leakage": sorted(addr for addr in addresses if addr in {"G16", "G17"}),
        "direct_dependency_only_false_selections": sorted(addr for addr in addresses if addr in {"G24", "I24", "G57", "I57"}),
        "output_occurrence_selection": sorted(addr for addr in addresses if addr in {"G43", "I43", "G44", "I44", "G45", "I45"}),
        "predicted_addresses": sorted(addresses),
        "gold_overlap": len(pred & gold),
    }


def measure_o6(frozen: dict[str, Any], ledger: dict[str, Any], destination: Path, spine: dict[str, Any]) -> dict[str, Any]:
    gold_display = load_obligation_gold("O6")
    gold = gold_cell_ids(gold_display, spine)
    gold_meta = gold_extent(gold)
    write_json(destination / "measurement" / "o6_gold.json", {"obligation": "O6", "gold_cell_count": len(gold), "loaded_after_payload_freeze": True, "loaded_at": now()})
    rows = []
    for pair in ledger["pairs"]:
        for arm in ("CONTROL", "TREATMENT"):
            call = pair["arms"][arm]
            infra = bool(call.get("failure_class"))
            parse_ok = bool(call.get("parse_valid")) and not infra
            metrics = score_prediction(call.get("parsed"), parse_ok, gold, gold_meta, spine, frozen["sheet"]["title"])
            flags = extra_o6_flags(call.get("parsed"), gold, spine) if parse_ok else {}
            rows.append({"obligation": "O6", "repeat": pair["repeat"], "arm": arm, "censored": pair["censored"] or infra, **metrics, **flags})
    write_json(destination / "measurement" / "o6_metrics.json", rows)
    with (destination / "measurement" / "o6_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["obligation"])
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": rows}


def verdict_o6(comparisons: list[dict[str, Any]]) -> str:
    usable = [item for item in comparisons if item["usable"]]
    if len(usable) < 3:
        return "PROVIDER_CENSORED"
    treatment_exact = sum(1 for item in usable if item["treatment_exact"])
    control_exact = sum(1 for item in usable if item["control_exact"])
    if control_exact >= 3:
        return "NO_HEADROOM_ON_O6"
    improvements = sum(1 for item in usable if item["strict_treatment_improvement"])
    reversals = sum(1 for item in usable if item["strict_control_reversal"])
    collapse = any(item["precision_collapse"] for item in usable)
    treatment_bar = 3 if len(usable) >= 4 else len(usable)
    if treatment_exact >= treatment_bar and control_exact <= 1 and not collapse and improvements >= 2 and reversals == 0:
        return "OUTPUT_RELATION_CASHES_OUT"
    if improvements and reversals:
        return "OUTPUT_RELATION_MIXED"
    return "OUTPUT_RELATION_NO_GAIN"


def write_report(destination: Path, o7: dict[str, Any], o6: dict[str, Any] | None) -> None:
    comparisons = o7["comparisons"]
    usable = [item for item in comparisons if item["usable"]]
    control_exact = sum(1 for item in usable if item["control_exact"])
    treatment_exact = sum(1 for item in usable if item["treatment_exact"])
    improved = sum(1 for item in usable if item["strict_treatment_improvement"])
    reversals = sum(1 for item in usable if item["strict_control_reversal"])
    headroom = control_exact <= 1 and len(usable) >= 3
    changed = any(item["control_exact"] != item["treatment_exact"] or item["control_f1"] != item["treatment_f1"] for item in usable)
    lines = [
        f"# {FAMILY} structural projection discriminator",
        "",
        f"Date: {datetime.now(UTC).date().isoformat()}",
        "Mode: mechanism / target-selection only",
        f"Primary witness: `{TASK}` O7",
        f"Model family: `{FAMILY}` (`{DECLARED_MODEL}`)",
        f"Verdict: **`{o7['verdict']}`**",
        "",
        "## Answers",
        "",
        f"1. Did CONTROL have headroom? **{'yes' if headroom and o7['verdict'] != 'NO_HEADROOM_ON_O7' else 'no' if o7['verdict'] == 'NO_HEADROOM_ON_O7' else 'limited / mixed'}** ({control_exact} exact of {len(usable)} complete CONTROL repeats).",
        f"2. Did direct compiled structure change Spark's target decision? **{'yes' if changed else 'no'}**.",
        f"3. Was the change correct? **{'yes' if o7['verdict'] == 'STRUCTURAL_PROJECTION_CASHES_OUT' else 'not under the predeclared cash-out rule'}** (TREATMENT exact {treatment_exact}/{len(usable)}; strict improvements {improved}; reversals {reversals}).",
        f"4. Was it repeatable? **{'yes' if treatment_exact >= 3 and reversals == 0 else 'no / insufficient'}**.",
        "5. Was the benefit from a structured relation rather than additional raw workbook facts? **yes, if TREATMENT moved at all**: CONTROL and TREATMENT shared one hashed raw-fact packet; TREATMENT added only the compiled member-run / temporal-axis block. `calc_query` was not exposed.",
        f"6. Does this preserve a model-facing compiled-context thesis, or weaken it? **{'preserves a narrow decision-value claim for this O7 target-selection problem' if o7['verdict'] == 'STRUCTURAL_PROJECTION_CASHES_OUT' else 'does not preserve an O7 decision-value claim under the predeclared rule; it does not license architecture changes'}**.",
        "",
        "## Isolation",
        "",
            "- Frozen model identity: "
            f"declared `{DECLARED_MODEL}`, request `{REQUEST_MODEL}`, temperature {TEMPERATURE}, "
            f"top_p {TOP_P}, reasoning `{REASONING_EFFORT}`, provider allow_fallbacks+require_parameters.",
        "- One model call per arm/repeat. Fresh conversations. Order CONTROL→TREATMENT, TREATMENT→CONTROL, CONTROL→TREATMENT, TREATMENT→CONTROL.",
        "- No `calc_query`, Task IR, Edit Plan, scheduler, ProgramGroups, writer, LibreOffice, or official scoring.",
        "- Evaluator gold loaded only after CONTROL/TREATMENT payloads were hashed.",
        "- `response_model` trailing-backslash cleanup is reporting-only.",
        "- Wide-range `inspect` 64-cell clipping remains an open product defect and was not exercised here.",
        "",
        "## O7 paired metrics",
        "",
        "| repeat | usable | CONTROL exact | TREATMENT exact | CONTROL F1 | TREATMENT F1 | class |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    rows_by_repeat = defaultdict(dict)
    for row in o7["rows"]:
        rows_by_repeat[row["repeat"]][row["arm"]] = row
    for item in comparisons:
        control = rows_by_repeat[item["repeat"]].get("CONTROL", {})
        treatment = rows_by_repeat[item["repeat"]].get("TREATMENT", {})
        klass = control.get("error_class", ""), treatment.get("error_class", "")
        lines.append(
            f"| {item['repeat']} | {item['usable']} | {item['control_exact']} | {item['treatment_exact']} | {item['control_f1']} | {item['treatment_f1']} | C:{klass[0]} / T:{klass[1]} |"
        )
    lines.extend(
        [
            "",
            f"Artifacts: `{destination.resolve().relative_to(ROOT)}/`.",
            "",
        ]
    )
    if o6:
        lines.extend(
            [
                "## O6 saturation fallback",
                "",
                "Gate fired: O7 verdict was `NO_HEADROOM_ON_O7`. CONTROL already selected the O7 gold rectangle from raw facts; compiled structure was not needed for this decision.",
                f"O6 verdict: **`{o6['verdict']}`**",
                "",
                "| repeat | usable | CONTROL exact | TREATMENT exact | CONTROL F1 | TREATMENT F1 |",
                "| ---: | --- | --- | --- | ---: | ---: |",
            ]
        )
        for item in o6["comparisons"]:
            lines.append(
                f"| {item['repeat']} | {item['usable']} | {item['control_exact']} | {item['treatment_exact']} | {item['control_f1']} | {item['treatment_f1']} |"
            )
        lines.append("")
    else:
        lines.extend(["## O6 saturation fallback", "", "Not run. The O7 verdict was not `NO_HEADROOM_ON_O7`.", ""])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(destination: Path, *, dry_run: bool = False, skip_calls: bool = False, remeasure: bool = False) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    frozen = freeze_o7(destination)
    if skip_calls:
        return {"frozen": True, "destination": str(destination)}
    ledger_path = destination / "ledgers" / "o7_request_response_ledger.json"
    if remeasure and ledger_path.is_file():
        ledger = {"pairs": json.loads(ledger_path.read_text(encoding="utf-8"))}
    else:
        ledger = run_o7_repeats(frozen, destination, dry_run=dry_run)
    identity = identity_audit(ledger)
    write_json(destination / "identity_audit.json", identity)
    measured = measure_o7(frozen, ledger, destination)
    comparisons = paired_comparisons(measured["rows"])
    write_json(destination / "measurement" / "o7_paired.json", comparisons)
    verdict = verdict_o7(comparisons)
    o7 = {"rows": measured["rows"], "comparisons": comparisons, "verdict": verdict}
    write_json(destination / "measurement" / "o7_verdict.json", {"verdict": verdict, "comparisons": comparisons})
    o6_out = None
    if verdict == "NO_HEADROOM_ON_O7" and not dry_run:
        spine = compile_source()["spine"]
        o6_frozen = freeze_o6(destination, spine)
        o6_ledger = {"pairs": []}
        for repeat in range(1, 5):
            order = pair_order(repeat)
            pair = {"repeat": repeat, "order": order, "arms": {}}
            for arm in order:
                print(f"CALL O6 r{repeat} {arm}", flush=True)
                call = call_spark(o6_frozen["payloads"][arm]["request_body"])
                write_json(destination / "ledgers" / f"o6_r{repeat}_{arm.lower()}.json", call)
                pair["arms"][arm] = call
                time.sleep(1)
            pair["censored"] = any(pair["arms"][a].get("failure_class") for a in ("CONTROL", "TREATMENT"))
            o6_ledger["pairs"].append(pair)
        write_json(destination / "ledgers" / "o6_request_response_ledger.json", o6_ledger)
        measured6 = measure_o6(o6_frozen, o6_ledger, destination, spine)
        comparisons6 = paired_comparisons(measured6["rows"])
        verdict6 = verdict_o6(comparisons6)
        write_json(destination / "measurement" / "o6_verdict.json", {"verdict": verdict6, "comparisons": comparisons6})
        o6_out = {"rows": measured6["rows"], "comparisons": comparisons6, "verdict": verdict6}
    write_report(destination, o7, o6_out)
    print(f"O7_VERDICT {verdict}", flush=True)
    if o6_out:
        print(f"O6_VERDICT {o6_out['verdict']}", flush=True)
    return {"o7_verdict": verdict, "o6": o6_out["verdict"] if o6_out else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=("spark", "glm"), default="spark")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--remeasure", action="store_true")
    args = parser.parse_args()
    activate_family(args.family)
    destination = args.output or ARTIFACT
    run(destination, dry_run=args.dry_run, skip_calls=args.freeze_only, remeasure=args.remeasure)


if __name__ == "__main__":
    main()
