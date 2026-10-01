#!/usr/bin/env python3
"""Isolated formula synthesis over frozen closed-world packets.

This experiment is deliberately downstream of the existing architecture:
oracle V1 obligations, frozen temporal-closure grounding packets, exact oracle
targets, and the existing hard verifier.  It never edits benchmark workbooks
and never sends golden formulas to the model.

Phases:
  freeze     freeze the synthesis prompt/schema and target population
  adequacy   evaluator-side packet/reference coverage only
  run        one GPT-5.6 Sol call per target x arm
  score      validate and score calls without repair
  report     write the architecture-review report
  all-offline run all non-LLM phases
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

from closed_world_resolver import associated_gold  # noqa: E402
from formula_completion_certs import load_grids  # noqa: E402
from formula_operational import build_view  # noqa: E402
from formula_verifier import scc_stats, verify_formula  # noqa: E402
from fingerprint import relative_fingerprint  # noqa: E402
from librecalc_mcp.domain.formulas import formula_a1_references  # noqa: E402
from task_obligation_compile import extract_json_object  # noqa: E402
from task_obligation_shape import family_of  # noqa: E402
from workbook_grounding import token_estimate  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402
from openpyxl.utils.cell import column_index_from_string, get_column_letter  # noqa: E402


DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model"
SHAPE = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-shape-probe"
GROUND = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/closed-world-resolver-probe"
SPINE_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe"
ORACLE_PATH = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-compile-probe/oracle_obligations.json"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-synthesis-probe"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-5.6-sol"
ARMS = ("S0_FULL_PACKET", "S1_FULL_PACKET_PLUS_ADVISORY")
HELD_OUT_FAMILIES = {"07", "08", "14", "19", "20"}
CONTEXT_TOKEN_LIMIT = 80_000
_SPINE_CACHE: dict[str, dict[str, Any]] = {}
_PACKET_CACHE: dict[str, dict[str, Any]] = {}
_INPUT_WB_CACHE: dict[str, Any] = {}
_VIEW_CACHE: dict[str, tuple[Any, dict[str, Any]]] = {}

# Historical ORACLE_WHERE cases are a small diagnostic overlay.  They are not
# added to the held-out headline population when their family is outside
# 07/08/14/19/20, and are never used to tune prompts or sampling.
KNOWN_CASE_BINDINGS = {
    ("04_05", "O5", "K6"),
    ("09_05", "O2", "K163"),
    ("09_05", "O2", "L163"),
    ("14_05", "O2", "D10"),
    ("20_04", "O1", "H41"),
    ("14_05", "O5", "J31"),
    ("08_01", "O6", "J46"),
    ("08_01", "O3", "AF66"),
    ("08_01", "O3", "AG66"),
    ("17_03", "O6", "K104"),
    ("15_04", "O1", "Y39"),
    ("15_04", "O1", "Y40"),
}

SYNTHESIS_PROMPT = """\
You are given one exact spreadsheet target cell, the task obligation governing it, and a mechanically compiled closed workbook packet.

Produce the formula that should be placed in the target.

All workbook facts you may rely on are in the packet. Resolver preferences, when present, are advisory and may be wrong. You may select any entity in the full packet. Never delete or ignore candidates merely because a preference did not select them.

Do not invent workbook cells, sheets, labels, or relationships absent from the packet. Do not modify any other cell.

If the supplied evidence is genuinely insufficient, abstain rather than inventing a formula.

Return JSON only with exactly this shape:
{
  "status": "PROPOSED" | "ABSTAIN",
  "target_id": "...",
  "formula": "=..." | null,
  "used_entity_ids": ["..."],
  "evidence_ids": ["..."]
}

The target_id must be the exact supplied target ID. Every entity/evidence ID must exist in the packet. Do not include rationale or markdown.
"""

SYNTHESIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "target_id", "formula", "used_entity_ids", "evidence_ids"],
    "properties": {
        "status": {"type": "string", "enum": ["PROPOSED", "ABSTAIN"]},
        "target_id": {"type": "string"},
        "formula": {"type": ["string", "null"]},
        "used_entity_ids": {"type": "array", "items": {"type": "string"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
}


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dataset() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in _load_json(DATA / "dataset.json")}


def _oracle() -> dict[str, dict[str, Any]]:
    return {row["task"]: row for row in _load_json(ORACLE_PATH)["tasks"]}


def _population_rows() -> dict[str, dict[str, Any]]:
    return {row["job_id"]: row for row in _load_json(GROUND / "population.json")["rows"] if row.get("job_id")}


def _delta() -> dict[str, dict[str, Any]]:
    return {row["task"]: row for row in _load_json(SHAPE / "golden_delta.json")["tasks"]}


def _load_spine(task: str) -> dict[str, Any]:
    if task in _SPINE_CACHE:
        return _SPINE_CACHE[task]
    path = SPINE_ROOT / "spines" / f"{task}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    _SPINE_CACHE[task] = _load_json(path)
    return _SPINE_CACHE[task]


def _input_path(task: str) -> Path:
    return DATA / _dataset()[task]["spreadsheet_path"]


def _gold_path(task: str) -> Path:
    return DATA / _dataset()[task]["golden_response_path"]


def _cell_id(spine: dict[str, Any], sheet: str, row: int, col: int) -> str | None:
    index = (spine.get("title_to_index") or {}).get(sheet)
    if index is None:
        return None
    return f"cell:s{int(index):02d}:r{row}:c{col}"


def _row_id(spine: dict[str, Any], sheet: str, row: int) -> str | None:
    index = (spine.get("title_to_index") or {}).get(sheet)
    return None if index is None else f"row:s{int(index):02d}:r{row}"


def _col_id(spine: dict[str, Any], sheet: str, col: int) -> str | None:
    index = (spine.get("title_to_index") or {}).get(sheet)
    return None if index is None else f"col:s{int(index):02d}:c{col}"


def _target_match(spine: dict[str, Any], ob: dict[str, Any], packet: dict[str, Any], change: dict[str, Any]) -> bool:
    """Use the existing evaluator-side association, with exact target support.

    Exact target association is retained even when the previous grounding
    target layer was upstream-missing; the experiment supplies WHERE by oracle.
    """
    target_id = _cell_id(spine, change["sheet"], change["row"], change["col"])
    if target_id in set(packet.get("target_cell_ids") or []):
        return True
    assoc = associated_gold(spine, ob, packet, [change])
    return bool(assoc[1])


def _edit_type(change: dict[str, Any]) -> str:
    mapping = {
        "blank→formula": "BLANK_TO_FORMULA",
        "value→formula": "VALUE_TO_FORMULA",
        "formula→formula": "FORMULA_TO_FORMULA",
    }
    return mapping.get(change.get("change_kind"), change.get("change_kind", "UNKNOWN"))


def _input_content(path: Path, sheet: str, row: int, col: int) -> dict[str, Any]:
    key = str(path)
    if key not in _INPUT_WB_CACHE:
        _INPUT_WB_CACHE[key] = openpyxl.load_workbook(path, data_only=False, read_only=False)
    value = _INPUT_WB_CACHE[key][sheet].cell(row=row, column=col).value
    if value is None or (isinstance(value, str) and not value.strip()):
        kind = "blank"
    elif isinstance(value, str) and value.startswith("="):
        kind = "formula"
    else:
        kind = "value"
    return {"content": value, "kind": kind}


def _packet_ids(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            ids.update(_packet_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_packet_ids(item))
    elif isinstance(value, str) and re.match(r"^(?:sheet|cell|row|col|text|tcoord|formula|dep|range):", value):
        ids.add(value)
    return ids


def _load_packet(row: dict[str, Any]) -> dict[str, Any]:
    rel = row["packet_path"]
    if rel not in _PACKET_CACHE:
        _PACKET_CACHE[rel] = _load_json(GROUND / rel)["packet"]
    return _PACKET_CACHE[rel]


def _load_resolver_preferences() -> dict[str, dict[str, Any]]:
    """Use the complete prior GLM resolver ledger, never prune its packet."""
    path = GROUND / "calls_glm.jsonl"
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if not rec.get("valid"):
            continue
        checked = rec.get("resolution") or {}
        fields = checked.get("fields") or {}
        out[rec["job_id"]] = {
            "source_model": rec.get("model"),
            "fields": {
                key: {
                    "status": value.get("status"),
                    "preferred_entity_ids": list(value.get("candidate_ids") or []),
                }
                for key, value in fields.items()
            },
        }
    return out


def _select_targets() -> dict[str, Any]:
    dataset = _dataset()
    oracle = _oracle()
    rows = _population_rows()
    deltas = _delta()
    selected: list[dict[str, Any]] = []
    diagnostic_selected: list[dict[str, Any]] = []
    population_rows: list[dict[str, Any]] = []
    candidate_obligations = 0
    eligible_targets_before_sampling = 0
    eligible_edit_counts = Counter()
    known_tasks = {task for task, _obligation, _address in KNOWN_CASE_BINDINGS}
    for task, task_meta in sorted(dataset.items()):
        family = family_of(task)
        if family not in HELD_OUT_FAMILIES and task not in known_tasks:
            continue
        if task not in oracle or task not in deltas:
            continue
        spine = _load_spine(task)
        input_path = _input_path(task)
        changes = [c for c in deltas[task]["changes"] if c.get("golden_kind") == "formula"]
        changes = [c for c in changes if _edit_type(c) in {"BLANK_TO_FORMULA", "VALUE_TO_FORMULA", "FORMULA_TO_FORMULA"}]
        for ob in oracle[task]["obligations"] if family in HELD_OUT_FAMILIES else []:
            job_id = f"{task}:{ob['id']}"
            row = rows.get(job_id)
            if not row or not row.get("packet_path"):
                continue
            packet = _load_packet(row)
            associated = [c for c in changes if _target_match(spine, ob, packet, c)]
            associated.sort(key=lambda c: (c["sheet"], c["row"], c["col"], c["address"]))
            if not associated:
                continue
            candidate_obligations += 1
            eligible_targets_before_sampling += len(associated)
            eligible_edit_counts.update(_edit_type(c) for c in associated)
            if len(associated) <= 3:
                sample = associated
                sampling = "ALL"
            else:
                sample = [associated[0], associated[len(associated) // 2], associated[-1]]
                # de-duplicate for the two-element middle edge case
                sample = list({(c["sheet"], c["row"], c["col"]): c for c in sample}.values())
                sample.sort(key=lambda c: (c["sheet"], c["row"], c["col"]))
                sampling = "FIRST_MIDDLE_LAST"
            for change in sample:
                tid = _cell_id(spine, change["sheet"], change["row"], change["col"])
                if not tid:
                    continue
                # The frozen evaluator delta already records the exact input
                # content at this target; do not reopen workbooks during
                # population construction.
                current_value = change.get("input_payload")
                current_kind = change.get("input_kind", "blank")
                selected.append({
                    "target_job_id": f"{job_id}:{tid}",
                    "job_id": job_id,
                    "task": task,
                    "family": family,
                    "split": "held_out",
                    "obligation_id": ob["id"],
                    "obligation": ob,
                    "target_id": tid,
                    "target": {
                        "sheet": change["sheet"],
                        "address": change["address"],
                        "row": change["row"],
                        "col": change["col"],
                        "current_input_content": current_value,
                        "current_input_kind": current_kind,
                    },
                    "edit_type": _edit_type(change),
                    "gold_formula": change["golden_payload"],
                    "gold_fingerprint": change.get("golden_formula_fingerprint"),
                    "input_formula": change.get("input_payload"),
                    "gold_refs_added": list(change.get("refs_added") or []),
                    "sampling": sampling,
                    "primary": True,
                    "packet_path": row["packet_path"],
                    "packet_meta": row,
                })
        # Add explicitly named historical cases as a separate, evaluator-side
        # diagnostic overlay.  This preserves the prior case definitions even
        # where the old grounding target layer was UPSTREAM_MISSING.
        for known_task, known_obligation, known_address in KNOWN_CASE_BINDINGS:
            if known_task != task:
                continue
            ob = next((x for x in oracle[task]["obligations"] if x["id"] == known_obligation), None)
            row = rows.get(f"{task}:{known_obligation}")
            if not ob or not row or not row.get("packet_path"):
                continue
            change = next((c for c in changes if c["address"] == known_address), None)
            if not change:
                continue
            tid = _cell_id(spine, change["sheet"], change["row"], change["col"])
            if not tid:
                continue
            diagnostic_selected.append({
                "target_job_id": f"{task}:{known_obligation}:{tid}",
                "job_id": f"{task}:{known_obligation}",
                "task": task,
                "family": family,
                "split": "known_diagnostic",
                "obligation_id": known_obligation,
                "obligation": ob,
                "target_id": tid,
                "target": {"sheet": change["sheet"], "address": change["address"], "row": change["row"], "col": change["col"], "current_input_content": change.get("input_payload"), "current_input_kind": change.get("input_kind", "blank")},
                "edit_type": _edit_type(change),
                "gold_formula": change["golden_payload"],
                "gold_fingerprint": change.get("golden_formula_fingerprint"),
                "input_formula": change.get("input_payload"),
                "gold_refs_added": list(change.get("refs_added") or []),
                "sampling": "KNOWN_CASE_DIAGNOSTIC",
                "primary": False,
                "packet_path": row["packet_path"],
                "packet_meta": row,
            })
    # One target row is the frozen unit; ordering is part of the freeze.
    selected.sort(key=lambda x: (x["task"], x["obligation_id"], x["target"]["sheet"], x["target"]["row"], x["target"]["col"]))
    existing = {x["target_job_id"] for x in selected}
    for row in sorted(diagnostic_selected, key=lambda x: (x["task"], x["obligation_id"], x["target"]["address"])):
        if row["target_job_id"] not in existing:
            selected.append(row)
            existing.add(row["target_job_id"])
    primary_rows = [x for x in selected if x["primary"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": "evaluator_side_only",
        "held_out_families": sorted(HELD_OUT_FAMILIES),
        "sampling_rule": "all targets when <=3 per obligation; otherwise address order first/middle/last",
        "population_rule": "Financial_Model formula-producing gold targets associated with ORACLE V1 obligations",
        "n_tasks": len({x["task"] for x in selected if x["primary"]}),
        "n_obligations": len({x["job_id"] for x in selected if x["primary"]}),
        "n_targets": sum(1 for x in selected if x["primary"]),
        "n_known_diagnostic_targets": sum(1 for x in selected if not x["primary"]),
        "edit_type_distribution": dict(Counter(x["edit_type"] for x in primary_rows)),
        "sampling_distribution": dict(Counter(x["sampling"] for x in primary_rows)),
        "rows": selected,
        "candidate_obligations": candidate_obligations,
        "eligible_targets_before_sampling": eligible_targets_before_sampling,
        "eligible_edit_type_distribution_before_sampling": dict(eligible_edit_counts),
    }


def _canonical_formula(text: str | None) -> str | None:
    if not isinstance(text, str):
        return None
    out = text.strip()
    if not out.startswith("="):
        out = "=" + out
    out = out.replace("\u00a0", " ")
    out = re.sub(r"\s+", "", out).casefold()
    out = out.replace("''", "'")
    # A quoted sheet and its unquoted safe identifier are equivalent.
    out = re.sub(r"'([A-Za-z_][A-Za-z0-9_]*)'!", r"\1!", out)
    return out


def _ref_records(formula: str | None, sheet: str, row: int, col: int) -> dict[str, Any]:
    if not formula or not isinstance(formula, str):
        return {"parser_ok": True, "opaque": False, "points": [], "ranges": [], "cross_sheet": [], "slots": []}
    from formula_operational import parse_use_def_slots

    parsed = parse_use_def_slots(formula, sheet, col, row)
    slots = parsed.get("slots") or []
    points = []
    ranges = []
    for slot in slots:
        item = {
            "sheet": slot["sheet"],
            "start": slot["start"],
            "end": slot.get("end"),
            "is_range": bool(slot.get("is_range")),
            "cross_sheet": bool(slot.get("cross_sheet")),
            "abs_mask": slot.get("abs_mask"),
        }
        (ranges if item["is_range"] else points).append(item)
    return {
        "parser_ok": bool(parsed.get("parser_ok")),
        "opaque": bool(parsed.get("opaque")),
        "opaque_reason": parsed.get("opaque_reason"),
        "points": points,
        "ranges": ranges,
        "cross_sheet": [x for x in points + ranges if x["cross_sheet"]],
        "slots": slots,
    }


def _a1_bounds(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)", text or "")
    if not m:
        return None
    return column_index_from_string(m.group(1)), int(m.group(2))


def _packet_cell_ids(packet: dict[str, Any]) -> set[str]:
    return {x for x in _packet_ids(packet) if x.startswith("cell:")}


def _relevant_candidate_count(packet: dict[str, Any]) -> int:
    ids: set[str] = set(packet.get("target_cell_ids") or [])
    for key in ("subject", "source"):
        ids.update(x.get("cell_id") for x in packet.get(key) or [] if x.get("cell_id"))
    for fact in packet.get("formula_class_facts") or []:
        if fact.get("cell_id"):
            ids.add(fact["cell_id"])
    for fact in packet.get("dependency_facts") or []:
        for key in ("source_id", "consumer_id"):
            if fact.get(key):
                ids.add(fact[key])
    return len(ids)


def _sheet_id_for(spine: dict[str, Any], title: str) -> str | None:
    idx = (spine.get("title_to_index") or {}).get(title)
    return None if idx is None else f"sheet:s{int(idx):02d}"


def _range_members(spine: dict[str, Any], ref: dict[str, Any]) -> list[str]:
    first = _a1_bounds(ref["start"])
    last = _a1_bounds(ref.get("end") or ref["start"])
    sid = _sheet_id_for(spine, ref["sheet"])
    if not first or not last or not sid:
        return []
    c1, r1 = first
    c2, r2 = last
    if (c2 - c1 + 1) * (r2 - r1 + 1) > 20_000:
        return []
    return [f"cell:{sid}:r{r}:c{c}" for r in range(min(r1, r2), max(r1, r2) + 1) for c in range(min(c1, c2), max(c1, c2) + 1)]


def _coverage(row: dict[str, Any], packet: dict[str, Any], spine: dict[str, Any]) -> dict[str, Any]:
    gold = _ref_records(row["gold_formula"], row["target"]["sheet"], row["target"]["row"], row["target"]["col"])
    packet_ids = _packet_ids(packet)
    cell_ids = _packet_cell_ids(packet)
    if gold["opaque"] or not gold["parser_ok"] or "[" in (row["gold_formula"] or "") or "]" in (row["gold_formula"] or ""):
        cls = "GOLD_REFERENCE_OPAQUE"
        point_cov = range_cov = None
    else:
        point_ids = []
        for ref in gold["points"]:
            sid = _sheet_id_for(spine, ref["sheet"])
            addr = _a1_bounds(ref["start"])
            point_ids.append(None if not sid or not addr else f"cell:{sid}:r{addr[1]}:c{addr[0]}")
        point_ids = [x for x in dict.fromkeys(point_ids) if x]
        point_hits = sum(x in cell_ids for x in point_ids)
        range_rows = []
        for ref in gold["ranges"]:
            members = _range_members(spine, ref)
            exact_range = any(
                isinstance(item, str) and item.startswith("range:") and ref["start"].lower() in item.lower()
                for item in packet_ids
            )
            range_rows.append({"ref": ref, "members_n": len(members), "represented": bool(exact_range or (members and set(members).issubset(cell_ids)))})
        range_hits = sum(1 for x in range_rows if x["represented"])
        point_cov = round(point_hits / len(point_ids), 4) if point_ids else 1.0
        range_cov = round(range_hits / len(range_rows), 4) if range_rows else 1.0
        total = len(point_ids) + len(range_rows)
        hits = point_hits + range_hits
        if total == 0 or hits == total:
            cls = "GOLD_REFERENCE_COMPLETE"
        elif hits == 0:
            cls = "GOLD_REFERENCE_NONE"
        else:
            cls = "GOLD_REFERENCE_PARTIAL"
    sheet_ids = {_sheet_id_for(spine, x["sheet"]) for x in gold["points"] + gold["ranges"]}
    sheet_ids.discard(None)
    row_ids = set()
    cell_present = []
    for ref in gold["points"] + gold["ranges"]:
        sid = _sheet_id_for(spine, ref["sheet"])
        start = _a1_bounds(ref["start"])
        if sid and start:
            row_ids.add(f"row:{sid[5:]}:r{start[1]}")
        cell_present.append({"sheet": ref["sheet"], "start": ref["start"], "represented": ref.get("is_range") is False and bool(sid and start and f"cell:{sid}:r{start[1]}:c{start[0]}" in cell_ids)})
    source_present = bool((row["obligation"].get("source_relation") or {}).get("text")) and bool(packet.get("source"))
    return {
        "class": cls,
        "gold_point_reference_coverage": point_cov,
        "gold_range_reference_coverage": range_cov,
        "gold_reference_complete": cls == "GOLD_REFERENCE_COMPLETE",
        "gold_reference_partial": cls == "GOLD_REFERENCE_PARTIAL",
        "gold_reference_none": cls == "GOLD_REFERENCE_NONE",
        "gold_reference_opaque": cls == "GOLD_REFERENCE_OPAQUE",
        "n_gold_points": len(gold["points"]),
        "n_gold_ranges": len(gold["ranges"]),
        "cross_sheet_refs": len(gold["cross_sheet"]),
        "task_named_source_present": source_present,
        "gold_reference_sheets_present": sheet_ids.issubset(packet_ids),
        "gold_reference_rows_present": row_ids.issubset(packet_ids),
        "gold_reference_cells_ranges_present": cls == "GOLD_REFERENCE_COMPLETE",
        "gold_refs": gold,
        "packet_entity_count": len(packet_ids),
        "relevant_candidate_count": _relevant_candidate_count(packet),
        "packet_token_count": token_estimate(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))),
    }


def cmd_freeze() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    prompt_path = OUT / "synthesis_prompt.txt"
    if prompt_path.exists() and prompt_path.read_text(encoding="utf-8") != SYNTHESIS_PROMPT:
        raise SystemExit("Refusing to overwrite frozen synthesis_prompt.txt")
    _write(prompt_path, SYNTHESIS_PROMPT)
    _write(OUT / "synthesis_schema.json", SYNTHESIS_SCHEMA)
    population = _select_targets()
    prefs = _load_resolver_preferences()
    for row in population["rows"]:
        row["resolver_available"] = row["job_id"] in prefs
        row["resolver_source_model"] = prefs.get(row["job_id"], {}).get("source_model")
    _write(OUT / "population.json", population)
    freeze = {
        "generated_at": datetime.now(UTC).isoformat(),
        "oracle": "TASK_OBLIGATION_SHAPE_V1",
        "model": MODEL,
        "arms": list(ARMS),
        "held_out_families": sorted(HELD_OUT_FAMILIES),
        "prompt_sha256": hashlib.sha256(SYNTHESIS_PROMPT.encode()).hexdigest(),
        "prompt_len": len(SYNTHESIS_PROMPT),
        "schema_sha256": hashlib.sha256(json.dumps(SYNTHESIS_SCHEMA, sort_keys=True).encode()).hexdigest(),
        "resolver_preference_source": "closed-world-resolver-probe/calls_glm.jsonl",
        "resolver_output_is_advisory": True,
        "golden_in_prompt": False,
        "golden_in_population_evaluator_only": True,
        "no_truncation_by_synthesis_experiment": True,
    }
    _write(OUT / "freeze.json", freeze)
    print(f"FROZEN targets={population['n_targets']} obligations={population['n_obligations']} prompt_sha256={freeze['prompt_sha256']}", flush=True)
    return population


def cmd_adequacy() -> dict[str, Any]:
    population = _load_json(OUT / "population.json")
    rows = []
    for row in population["rows"]:
        packet = _load_packet(row["packet_meta"])
        spine = _load_spine(row["task"])
        cov = _coverage(row, packet, spine)
        row_out = {k: row[k] for k in ("target_job_id", "job_id", "task", "family", "obligation_id", "target", "edit_type", "gold_formula", "gold_fingerprint", "sampling", "primary")}
        row_out.update(cov)
        rows.append(row_out)
    def aggregate(picked: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(picked)
        counts = Counter(r["class"] for r in picked)
        return {
            "n": n,
            "classes": {k: counts[k] for k in ("GOLD_REFERENCE_COMPLETE", "GOLD_REFERENCE_PARTIAL", "GOLD_REFERENCE_NONE", "GOLD_REFERENCE_OPAQUE")},
            "rates": {k: round(counts[k] / n, 4) if n else None for k in ("GOLD_REFERENCE_COMPLETE", "GOLD_REFERENCE_PARTIAL", "GOLD_REFERENCE_NONE", "GOLD_REFERENCE_OPAQUE")},
            "mean_point_coverage": round(sum((r["gold_point_reference_coverage"] or 0) for r in picked) / n, 4) if n else None,
            "mean_range_coverage": round(sum((r["gold_range_reference_coverage"] or 0) for r in picked) / n, 4) if n else None,
            "task_named_source_present_rate": round(sum(bool(r.get("task_named_source_present")) for r in picked) / n, 4) if n else None,
            "gold_reference_sheets_present_rate": round(sum(bool(r.get("gold_reference_sheets_present")) for r in picked) / n, 4) if n else None,
            "gold_reference_rows_present_rate": round(sum(bool(r.get("gold_reference_rows_present")) for r in picked) / n, 4) if n else None,
            "gold_reference_cells_ranges_present_rate": round(sum(bool(r.get("gold_reference_cells_ranges_present")) for r in picked) / n, 4) if n else None,
            "context_capacity_failures": sum((r.get("packet_token_count") or 0) > CONTEXT_TOKEN_LIMIT for r in picked),
            "max_packet_tokens": max((r.get("packet_token_count") or 0 for r in picked), default=0),
        }
    by_edit = {k: aggregate([r for r in rows if r["edit_type"] == k and r["primary"]]) for k in sorted({r["edit_type"] for r in rows if r["primary"]})}
    by_family = {k: aggregate([r for r in rows if r["family"] == k and r["primary"]]) for k in sorted(HELD_OUT_FAMILIES)}
    payload = {"generated_at": datetime.now(UTC).isoformat(), "overall": aggregate([r for r in rows if r["primary"]]), "known_diagnostic": aggregate([r for r in rows if not r["primary"]]), "by_edit_type": by_edit, "by_family": by_family, "rows": rows}
    _write(OUT / "phase_a_adequacy.json", payload)
    print(f"ADEQUACY n={len(rows)} complete={payload['overall']['rates']['GOLD_REFERENCE_COMPLETE']}", flush=True)
    return payload


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in content)
    return str(content or "")


def _openrouter_call(api_key: str, user: str) -> dict[str, Any]:
    body = {
        "model": MODEL,
        "max_tokens": 1024,
        "temperature": 0.0,
        "reasoning": {"effort": "medium"},
        "messages": [{"role": "system", "content": SYNTHESIS_PROMPT}, {"role": "user", "content": user}],
    }
    request = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "X-Title": "librecalc-formula-synthesis"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return {"http_ok": True, "payload": json.loads(response.read().decode())}
    except urllib.error.HTTPError as exc:
        return {"http_ok": False, "status": exc.code, "detail": exc.read().decode(errors="replace")}
    except urllib.error.URLError as exc:
        return {"http_ok": False, "status": 0, "detail": str(exc.reason)}


def _render_user(row: dict[str, Any], arm: str, packet: dict[str, Any], prefs: dict[str, Any] | None) -> str:
    payload = {
        "TASK": row["obligation"],
        "TARGET": {"id": row["target_id"], **row["target"]},
        "CLOSED_WORKBOOK_PACKET": packet,
    }
    if arm == "S1_FULL_PACKET_PLUS_ADVISORY":
        payload["OPTIONAL_RESOLVER_PREFERENCES"] = prefs or {"available": False, "note": "No prior preference record; use the full packet."}
        payload["ADVISORY_WARNING"] = "These resolver preferences are advisory and may be wrong. ALL original packet candidates remain available."
    return json.dumps(payload, ensure_ascii=False, indent=2)


def cmd_run(*, arms: tuple[str, ...] = ARMS, limit: int | None = None, offset: int = 0, force: bool = False, diagnostic_only: bool = False, known_only: bool = False) -> None:
    cmd_freeze()
    _load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required")
    population = _load_json(OUT / "population.json")
    prefs = _load_resolver_preferences()
    rows = [r for r in population["rows"] if (not diagnostic_only or not r["primary"]) and (not known_only or (r["task"], r["obligation_id"], r["target"]["address"]) in KNOWN_CASE_BINDINGS)]
    rows = rows[offset:]
    rows = rows[:limit] if limit else rows
    for arm in arms:
        dest = OUT / f"calls_{arm}.jsonl"
        if force:
            dest.write_text("")
        done = set()
        if dest.exists():
            for line in dest.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("http_ok"):
                        done.add(rec["target_job_id"])
        pending = [r for r in rows if f"{r['target_job_id']}::{arm}" not in done]
        print(f"RUN {arm} remaining={len(pending)}/{len(rows)}", flush=True)
        with dest.open("a", encoding="utf-8") as handle:
            for i, row in enumerate(pending, 1):
                packet = _load_packet(row["packet_meta"])
                user = _render_user(row, arm, packet, prefs.get(row["job_id"]))
                started = time.perf_counter()
                response = _openrouter_call(key, user)
                elapsed = round(time.perf_counter() - started, 3)
                rec = {"target_job_id": f"{row['target_job_id']}::{arm}", "base_target_job_id": row["target_job_id"], "job_id": row["job_id"], "task": row["task"], "family": row["family"], "obligation_id": row["obligation_id"], "arm": arm, "model": MODEL, "elapsed_s": elapsed, "packet_tokens": token_estimate(user), "resolver_available": row["job_id"] in prefs}
                if response.get("http_ok"):
                    raw = _message_text(response["payload"])
                    rec.update({"http_ok": True, "raw_text": raw[:12000], "parsed": extract_json_object(raw), "usage": (response.get("payload") or {}).get("usage")})
                else:
                    rec.update({"http_ok": False, "status": response.get("status"), "detail": response.get("detail")})
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
                handle.flush()
                print(f"CALL {arm} {i}/{len(pending)} {row['target_job_id']} ok={rec['http_ok']}", flush=True)


def _target_key(row: dict[str, Any]) -> tuple[str, int, int]:
    return row["target"]["sheet"], row["target"]["row"], row["target"]["col"]


def _actual_ref_ids(spine: dict[str, Any], refs: dict[str, Any]) -> set[str]:
    out = set()
    for ref in refs.get("points", []):
        sid = _sheet_id_for(spine, ref["sheet"])
        a = _a1_bounds(ref["start"])
        if sid and a:
            out.add(f"cell:{sid}:r{a[1]}:c{a[0]}")
    for ref in refs.get("ranges", []):
        out.update(_range_members(spine, ref))
    return out


def _used_sheet_bounds(ws: Any) -> tuple[int | None, int | None]:
    """Return comparable used-range maxima for a worksheet.

    openpyxl ReadOnlyWorksheet leaves ``max_column`` / ``max_row`` as None when
    the worksheet XML omits ``<dimension>``.  That is legal OOXML, including for
    populated sheets.  Force calculation so the existing beyond-used-range
    predicate still runs on integers instead of raising ``TypeError``.
    """
    max_col = ws.max_column
    max_row = ws.max_row
    if max_col is None or max_row is None:
        calculate = getattr(ws, "calculate_dimension", None)
        if callable(calculate):
            try:
                calculate(force=True)
            except (TypeError, ValueError):
                pass
        max_col = ws.max_column
        max_row = ws.max_row
    return max_col, max_row


def _validate_formula(row: dict[str, Any], formula: str | None, packet: dict[str, Any], spine: dict[str, Any], view: Any, scc: dict[str, Any]) -> dict[str, Any]:
    target = _target_key(row)
    result = {"formula_present": bool(formula), "parser_ok": True, "invalid_sheet": False, "invalid_address": False, "unsupported_external": False, "self_reference": False, "cycle": False, "hard_reject": False, "hard_verifier": None, "parsed_refs": None}
    if not formula or not isinstance(formula, str):
        return result
    if not formula.startswith("="):
        result["parser_ok"] = False
    refs = _ref_records(formula, target[0], target[1], target[2])
    result["parsed_refs"] = refs
    result["parser_ok"] = result["parser_ok"] and refs["parser_ok"] and not refs["opaque"]
    if "[" in formula or "]" in formula or "#REF!" in formula.upper():
        result["unsupported_external"] = True
    known = set((spine.get("title_to_index") or {}).keys())
    # Callers outside the original four-cell synthesis probe may already have
    # resolved the authoritative workbook path.  Prefer that explicit path;
    # retain the historical dataset lookup as the fallback for old callers.
    input_path = row.get("input_path") or _input_path(row["task"])
    wb = openpyxl.load_workbook(input_path, data_only=False, read_only=True)
    try:
        for host, start, end in formula_a1_references(formula):
            sheet = host or target[0]
            if sheet not in known:
                result["invalid_sheet"] = True
                continue
            if _a1_bounds(start) is None or (end and _a1_bounds(end) is None):
                result["invalid_address"] = True
                continue
            ws = wb[sheet]
            max_col, max_row = _used_sheet_bounds(ws)
            for addr in [start] + ([end] if end else []):
                a = _a1_bounds(addr)
                if a is None:
                    continue
                if max_col is None or max_row is None:
                    continue
                if a[0] > max_col or a[1] > max_row:
                    result["invalid_address"] = True
        result["self_reference"] = any(slot["sheet"] == target[0] and slot["c1"] <= target[2] <= slot["c2"] and slot["r1"] <= target[1] <= slot["r2"] for slot in refs["slots"])
    finally:
        wb.close()
    try:
        if view is None:
            return result
        checked = verify_formula(view, target, formula, sccs=scc)
        result["hard_verifier"] = checked
        result["hard_reject"] = any(p["verdict"] == "REJECT" for p in checked.get("policies", []) if p["policy"] == "H")
        result["cycle"] = "A1" in (checked.get("policies", [{}])[0].get("reject_ids") or []) or any(x.get("reason") in {"DIRECT_CYCLE_IF_ADDED", "TRANSITIVE_CYCLE_IF_ADDED"} for x in checked.get("results", []))
    except Exception as exc:  # verifier must not prevent evaluator scoring
        result["hard_verifier_error"] = f"{type(exc).__name__}: {exc}"
    return result


def _operator_structure(formula: str | None, target: tuple[str, int, int]) -> str | None:
    if not formula:
        return None
    from formula_verifier import operator_skeleton
    return operator_skeleton(formula)


def _score_one(row: dict[str, Any], rec: dict[str, Any], adequacy: dict[str, Any]) -> dict[str, Any]:
    packet = _load_packet(row["packet_meta"])
    spine = _load_spine(row["task"])
    parsed = rec.get("parsed") if rec.get("http_ok") else None
    valid_ids = _packet_ids(packet)
    invalid_ids = []
    if not isinstance(parsed, dict):
        status = "INVALID_OUTPUT"
        formula = None
    else:
        status = parsed.get("status")
        formula = parsed.get("formula")
        for key in ("used_entity_ids", "evidence_ids"):
            for value in parsed.get(key) or []:
                if value not in valid_ids:
                    invalid_ids.append(value)
        if parsed.get("target_id") != row["target_id"]:
            invalid_ids.append(str(parsed.get("target_id")))
    view = scc = None
    if status == "PROPOSED" and formula:
        if row["task"] not in _VIEW_CACHE:
            grids = load_grids(_input_path(row["task"]))
            from formula_dependency_selection import build_graph_from_grids
            _VIEW_CACHE[row["task"]] = (build_view(build_graph_from_grids(grids)), None)
            _VIEW_CACHE[row["task"]] = (_VIEW_CACHE[row["task"]][0], scc_stats(_VIEW_CACHE[row["task"]][0]))
        view, scc = _VIEW_CACHE[row["task"]]
    validation = _validate_formula(row, formula if status == "PROPOSED" else None, packet, spine, view, scc)
    gold_formula = row["gold_formula"]
    gold_refs = _ref_records(gold_formula, row["target"]["sheet"], row["target"]["row"], row["target"]["col"])
    pred_refs = _ref_records(formula, row["target"]["sheet"], row["target"]["row"], row["target"]["col"])
    exact = _canonical_formula(formula) == _canonical_formula(gold_formula) if formula else False
    pred_fp = None
    if formula and validation["parser_ok"]:
        fp = relative_fingerprint(formula, row["target"]["col"], row["target"]["row"], sheet=row["target"]["sheet"])
        pred_fp = None if fp.opaque else fp.eq_id
    fingerprint = bool(pred_fp and row.get("gold_fingerprint") and pred_fp == row["gold_fingerprint"])
    point_gold = {(x["sheet"], x["start"], x.get("end")) for x in gold_refs["points"]}
    point_pred = {(x["sheet"], x["start"], x.get("end")) for x in pred_refs["points"]}
    range_gold = {(x["sheet"], x["start"], x.get("end")) for x in gold_refs["ranges"]}
    range_pred = {(x["sheet"], x["start"], x.get("end")) for x in pred_refs["ranges"]}
    all_gold = point_gold | range_gold
    all_pred = point_pred | range_pred
    compatible = (len(point_gold & point_pred) + len(range_gold & range_pred)) / max(1, len(all_gold))
    extra = len(all_pred - all_gold) / max(1, len(all_pred))
    source_gold_retained = bool(all_gold and all_gold.issubset(all_pred)) or (not all_gold and not all_pred)
    tags: list[str] = []
    if status == "INVALID_OUTPUT":
        tags.append("INVALID_OUTPUT")
    elif status == "ABSTAIN" or not formula:
        tags.append("ABSTAIN")
    elif invalid_ids:
        tags.append("INVALID_ENTITY_REFERENCE")
    elif not validation["parser_ok"] or validation["invalid_sheet"] or validation["invalid_address"] or validation["unsupported_external"]:
        tags.append("INVALID_FORMULA")
    if validation.get("cycle"):
        tags.append("CYCLE")
    if formula and not exact and not fingerprint:
        if _operator_structure(formula, _target_key(row)) != _operator_structure(gold_formula, _target_key(row)):
            tags.append("WRONG_OPERATOR")
        if point_gold != point_pred or range_gold != range_pred:
            tags.append("WRONG_SOURCE")
        if range_gold != range_pred and len(range_gold) == len(range_pred):
            tags.append("WRONG_RANGE_EXTENT")
        gold_cols = {(_a1_bounds(x["start"]) or (0, 0))[0] for x in gold_refs["points"] + gold_refs["ranges"]}
        pred_cols = {(_a1_bounds(x["start"]) or (0, 0))[0] for x in pred_refs["points"] + pred_refs["ranges"]}
        if gold_cols and pred_cols and gold_cols != pred_cols:
            tags.append("WRONG_PERIOD")
        if [x.get("abs_mask") for x in gold_refs["slots"]] != [x.get("abs_mask") for x in pred_refs["slots"]]:
            tags.append("WRONG_ABSOLUTE_RELATIVE_REFERENCE")
        if {x["sheet"] for x in gold_refs["points"] + gold_refs["ranges"]} != {x["sheet"] for x in pred_refs["points"] + pred_refs["ranges"]}:
            tags.append("WRONG_CROSS_SHEET_BINDING")
        if not tags:
            tags.append("OTHER")
    if not tags and not exact and not fingerprint:
        tags.append("OTHER")
    return {
        "target_job_id": row["target_job_id"], "job_id": row["job_id"], "task": row["task"], "family": row["family"], "obligation_id": row["obligation_id"], "target": row["target"], "edit_type": row["edit_type"], "arm": rec.get("arm"), "status": status, "formula": formula, "gold_formula": gold_formula, "exact_formula_match": exact, "gold_fingerprint_match": fingerprint, "formula_correct": bool(exact or fingerprint), "scorer_equivalent": None, "reference_compatibility": round(compatible, 4), "exact_reference_set_match": point_gold == point_pred and range_gold == range_pred, "gold_reference_recall": round(compatible, 4), "extra_reference_rate": round(extra, 4), "operator_structure_match": _operator_structure(formula, _target_key(row)) == _operator_structure(gold_formula, _target_key(row)) if formula else False, "used_entity_ids": (parsed or {}).get("used_entity_ids") if isinstance(parsed, dict) else [], "evidence_ids": (parsed or {}).get("evidence_ids") if isinstance(parsed, dict) else [], "invalid_entity_ids": sorted(set(invalid_ids)), "source_gold_retained": source_gold_retained, "source_wrong_selection": bool(formula and not source_gold_retained), "source_extra": sorted(all_pred - all_gold), "source_missing": sorted(all_gold - all_pred), "failure_tags": sorted(set(tags)), "validation": validation, "packet_adequacy": adequacy}


def cmd_score() -> dict[str, Any]:
    population = _load_json(OUT / "population.json")
    adequacy = {r["target_job_id"]: r for r in _load_json(OUT / "phase_a_adequacy.json")["rows"]}
    rows_by_id = {r["target_job_id"]: r for r in population["rows"]}
    scored: list[dict[str, Any]] = []
    for arm in ARMS:
        path = OUT / f"calls_{arm}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            base = rows_by_id.get(rec.get("base_target_job_id"))
            if not base:
                continue
            scored.append(_score_one(base, rec, adequacy.get(base["target_job_id"], {})))
    payload = {"generated_at": datetime.now(UTC).isoformat(), "rows": scored, "n": len(scored)}
    _write(OUT / "scored.json", payload)
    print(f"SCORED n={len(scored)}", flush=True)
    return payload


def _rate(rows: list[dict[str, Any]], predicate) -> float | None:
    return round(sum(1 for r in rows if predicate(r)) / len(rows), 4) if rows else None


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classes = Counter(r.get("packet_adequacy", {}).get("class") for r in rows)
    tags = Counter(tag for r in rows for tag in r.get("failure_tags", []))
    return {"n": len(rows), "FORMULA_CORRECT": _rate(rows, lambda r: r["formula_correct"]), "EXACT_FORMULA_MATCH": _rate(rows, lambda r: r["exact_formula_match"]), "GOLD_FINGERPRINT_MATCH": _rate(rows, lambda r: r["gold_fingerprint_match"]), "SCORER_EQUIVALENT": _rate(rows, lambda r: r["scorer_equivalent"] is True), "HARD_REJECT": _rate(rows, lambda r: r["validation"].get("hard_reject")), "ABSTAIN": _rate(rows, lambda r: "ABSTAIN" in r["failure_tags"]), "INVALID_ENTITY_REFERENCE": _rate(rows, lambda r: "INVALID_ENTITY_REFERENCE" in r["failure_tags"]), "failure_taxonomy": dict(tags), "packet_adequacy": dict(classes), "mean_packet_tokens": round(sum((r.get("packet_adequacy", {}).get("packet_token_count") or 0) for r in rows) / len(rows), 1) if rows else None}


def _paired(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = defaultdict(dict)
    for r in rows:
        by[r["target_job_id"]][r["arm"]] = r
    out = Counter()
    for pair in by.values():
        s0, s1 = pair.get(ARMS[0]), pair.get(ARMS[1])
        if not s0 or not s1:
            continue
        c0, c1 = s0["formula_correct"], s1["formula_correct"]
        out["BOTH_CORRECT" if c0 and c1 else "S1_ONLY_CORRECT" if c1 else "S0_ONLY_CORRECT" if c0 else "BOTH_WRONG_SAME" if s0.get("formula") == s1.get("formula") else "BOTH_WRONG_DIFFERENT"] += 1
    n = sum(out.values())
    return {"n": n, "counts": dict(out), "rates": {k: round(v / n, 4) for k, v in out.items()} if n else {}, "delta_formula_correct": round(sum(1 for pair in by.values() if pair.get(ARMS[1], {}).get("formula_correct")) / max(1, n) - sum(1 for pair in by.values() if pair.get(ARMS[0], {}).get("formula_correct")) / max(1, n), 4) if n else None}


def cmd_report() -> None:
    scored = _load_json(OUT / "scored.json")["rows"]
    adequacy = _load_json(OUT / "phase_a_adequacy.json")
    by_arm = {arm: _summary([r for r in scored if r["arm"] == arm]) for arm in ARMS}
    complete = {arm: _summary([r for r in scored if r["arm"] == arm and r["packet_adequacy"].get("class") == "GOLD_REFERENCE_COMPLETE"]) for arm in ARMS}
    by_class = {cls: {arm: _summary([r for r in scored if r["arm"] == arm and r["packet_adequacy"].get("class") == cls]) for arm in ARMS} for cls in ("GOLD_REFERENCE_COMPLETE", "GOLD_REFERENCE_PARTIAL", "GOLD_REFERENCE_NONE", "GOLD_REFERENCE_OPAQUE")}
    amb = {}
    for bucket in ("1-2", "3-5", "6-10", "11-50", ">50"):
        picked = [r for r in scored if (lambda n: "1-2" if n <= 2 else "3-5" if n <= 5 else "6-10" if n <= 10 else "11-50" if n <= 50 else ">50")((r.get("packet_adequacy", {}).get("relevant_candidate_count") or 0)) == bucket]
        amb[bucket] = {arm: _summary([r for r in picked if r["arm"] == arm]) for arm in ARMS}
    known = {}
    for target in ("K6", "K163", "L163", "D10", "H41", "J31", "J46", "AF66", "AG66", "K104", "Y39", "Y40"):
        rows = [r for r in scored if r["target"]["address"] == target]
        if rows:
            known[target] = [{k: r.get(k) for k in ("task", "obligation_id", "target", "arm", "formula", "gold_formula", "formula_correct", "failure_tags", "source_gold_retained", "source_wrong_selection", "validation", "packet_adequacy")} for r in rows]
    report = {
        "title": "Isolated formula synthesis over compiled workbook architecture",
        "generated_at": datetime.now(UTC).isoformat(),
        "population": _load_json(OUT / "population.json"),
        "phase_a_adequacy": adequacy,
        "arms": by_arm,
        "gold_reference_complete_primary": complete,
        "by_packet_completeness": by_class,
        "paired_advisory_effect": _paired(scored),
        "ambiguity_bucket_by_packet_entity_count": amb,
        "known_case_autopsy": known,
        "primary_synthesis_status": {
            "run": False,
            "reason": "SYNTHESIS_PACKET_LIMITED: held-out GOLD_REFERENCE_COMPLETE rate was 0.0, below the preregistered 0.70 gate",
            "diagnostic_calls_only": True,
        },
        "historical_oracle_where": {"reported_prior": "about 3/18 exact/canonical", "comparison": "descriptive and unmatched"},
        "notes": [
            "S1 retained the complete S0 packet; resolver IDs were preferences only.",
            "Scorer-equivalence was not asserted unless a safe single-cell recalculation path was available; the current report records it as unavailable.",
            "Gold-reference completeness is packet adequacy, not a claim that the model must reproduce the exact gold precedent set.",
        ],
    }
    _write(OUT / "report.json", report)
    lines = ["# Isolated formula synthesis experiment", "", f"Prompt SHA-256: `{_load_json(OUT / 'freeze.json')['prompt_sha256']}`", "", "## Primary held-out COMPLETE subset", ""]
    for arm in ARMS:
        lines.append(f"- {arm}: n={complete[arm]['n']}, FORMULA_CORRECT={complete[arm]['FORMULA_CORRECT']}, EXACT={complete[arm]['EXACT_FORMULA_MATCH']}, FINGERPRINT={complete[arm]['GOLD_FINGERPRINT_MATCH']}, HARD_REJECT={complete[arm]['HARD_REJECT']}")
    lines += ["", "## All eligible", ""]
    for arm in ARMS:
        lines.append(f"- {arm}: n={by_arm[arm]['n']}, FORMULA_CORRECT={by_arm[arm]['FORMULA_CORRECT']}, EXACT={by_arm[arm]['EXACT_FORMULA_MATCH']}, FINGERPRINT={by_arm[arm]['GOLD_FINGERPRINT_MATCH']}")
    lines += ["", f"Paired effect: `{json.dumps(_paired(scored), sort_keys=True)}`", "", "See `report.json` for taxonomy, source analysis, completeness classes, ambiguity buckets, hard verifier interaction, and known-case autopsy.", ""]
    _write(OUT / "report.md", "\n".join(lines))
    print(f"REPORT {OUT / 'report.md'}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "adequacy", "run", "score", "report", "all-offline"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--diagnostic-only", action="store_true")
    parser.add_argument("--known-only", action="store_true")
    parser.add_argument("--arm", action="append", choices=ARMS)
    args = parser.parse_args()
    if args.phase == "freeze":
        cmd_freeze()
    elif args.phase == "adequacy":
        cmd_adequacy()
    elif args.phase == "run":
        cmd_run(arms=tuple(args.arm) if args.arm else ARMS, limit=args.limit, offset=args.offset, force=args.force, diagnostic_only=args.diagnostic_only, known_only=args.known_only)
    elif args.phase == "score":
        cmd_score()
    elif args.phase == "report":
        cmd_report()
    else:
        cmd_freeze()
        cmd_adequacy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
