#!/usr/bin/env python3
"""Narrow deterministic-bootstrap plus SQL retrieval experiment.

This probe does retrieval only.  It never synthesizes a formula or edits a
workbook.  R0 is the prior strong-SQL protocol; R1 adds a deterministic M0/M2/
M4 bootstrap and a monotone harness-managed working set.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))

import formula_projection_preflight as projection  # noqa: E402
import relational_retrieval_probe as prior  # noqa: E402
from formula_operational import parse_use_def_slots  # noqa: E402


MODEL = "z-ai/glm-5.3-flash"
OPENROUTER_URL = prior.OPENROUTER_URL
MAX_CALLS = 8
BOOTSTRAP_LIMIT = 8_000
RESULT_ROW_LIMIT = prior.RESULT_ROW_LIMIT
RESULT_BYTE_LIMIT = prior.RESULT_BYTE_LIMIT
EPISODE_TOKEN_LIMIT = prior.EPISODE_TOKEN_LIMIT
ARMS = ("R0_CURRENT_SQL", "R1_HYBRID_SQL")
KNOWN_ADDRESSES = {"K6", "K163", "L163", "D10", "H41", "J31", "J46", "AF66", "AG66", "K104", "Y39", "Y40"}

OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/hybrid-sql-retrieval-probe"
PROJECTION_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-projection-preflight"
PREVIOUS_FINAL = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/relational-retrieval-probe-glm-final-matched"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def estimate_tokens(value: Any) -> int:
    return max(1, len(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))) // 4)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def arm_paths(arm: str) -> list[Path]:
    """Return the primary ledger plus any deterministic worker ledgers."""
    return sorted(OUT.glob(f"calls_{arm}*.jsonl"))


def arm_rows(arm: str) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in arm_paths(arm):
        for row in read_jsonl(path):
            # A later successful retry supersedes an access-failure record.
            rows[row["target_job_id"]] = row
    return list(rows.values())


def projection_rows() -> dict[str, dict[str, Any]]:
    return {row["target_job_id"]: row for row in (json.loads(line) for line in (PROJECTION_OUT / "targets.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}


def reference_rows() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in (PROJECTION_OUT / "references.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["target_job_id"]].append(row)
    return out


def previous_sql_rows() -> dict[str, dict[str, Any]]:
    return {row["target_job_id"]: row for row in read_jsonl(PREVIOUS_FINAL / "calls_B_SQL_STRONG_CONTEXT.jsonl")}


def diverse_pick(rows: list[dict[str, Any]], n: int, excluded: set[str]) -> list[dict[str, Any]]:
    candidates = [row for row in rows if row["target_job_id"] not in excluded]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(candidates, key=lambda x: (x["task"], x.get("edit_type") or "", x["target_job_id"])):
        groups[(row["task"], row.get("edit_type") or "UNKNOWN")].append(row)
    keys = sorted(groups)
    picked = []
    while keys and len(picked) < n:
        next_keys = []
        for key in keys:
            values = groups[key]
            if values:
                picked.append(values.pop(0))
                if len(picked) >= n:
                    break
            if values:
                next_keys.append(key)
        keys = next_keys
    return picked


def build_population() -> list[dict[str, Any]]:
    all_rows = {row["target_job_id"]: row for row in prior.retrieval_population()}
    proj = projection_rows()
    refs = reference_rows()
    primary = [row for row in all_rows.values() if row.get("primary") and row.get("family") in prior.HELD_OUT]

    def supported(row: dict[str, Any]) -> bool:
        return bool(proj.get(row["target_job_id"], {}).get("gold_supported"))

    def existing(row: dict[str, Any]) -> bool:
        return proj.get(row["target_job_id"], {}).get("fingerprint_existing") is True

    selected: dict[str, dict[str, Any]] = {}
    reasons: dict[str, list[str]] = defaultdict(list)

    # Known cases are selected first and retained even when they are diagnostic rows.
    for row in sorted(all_rows.values(), key=lambda x: x["target_job_id"]):
        if row["target"]["address"] in KNOWN_ADDRESSES and supported(row):
            selected[row["target_job_id"]] = row
            reasons[row["target_job_id"]].append("S4_KNOWN_DIAGNOSTIC")

    strata = [
        ("S1_EXISTING_PROGRAM", [row for row in primary if supported(row) and existing(row)]),
        ("S2_NOVEL_PROGRAM", [row for row in primary if supported(row) and not existing(row)]),
        ("S3_STATIC_PROJECTION_FAILURE", [row for row in primary if supported(row) and not proj.get(row["target_job_id"], {}).get("C7_ALL", {}).get("complete")]),
    ]
    for label, candidates in strata:
        picked = diverse_pick(candidates, 12, set(selected))
        for row in picked:
            selected[row["target_job_id"]] = row
            reasons[row["target_job_id"]].append(label)

    previous = previous_sql_rows()
    missing_candidates = []
    for row in primary:
        tid = row["target_job_id"]
        if tid in selected or not supported(row):
            continue
        ref_features = refs.get(tid, [])
        labels = []
        if previous.get(tid) and not previous[tid].get("retrieved_evidence_coverage", {}).get("complete"):
            labels.append("PRIOR_SQL_FAILURE")
        if any(x.get("cross_sheet") for x in ref_features):
            labels.append("CROSS_SHEET_IDENTITY")
        if any(not x.get("same_formula_class_neighborhood") for x in ref_features):
            labels.append("FORMULA_CLASS_GAP")
        if labels:
            missing_candidates.append((row, labels))
    for row, labels in sorted(missing_candidates, key=lambda x: (x[0]["task"], x[0]["target_job_id"])):
        if len(selected) >= 48:
            break
        selected[row["target_job_id"]] = row
        reasons[row["target_job_id"]].extend(labels)

    if len(selected) < 48:
        for row in diverse_pick(primary, 48 - len(selected), set(selected)):
            selected[row["target_job_id"]] = row
            reasons[row["target_job_id"]].append("DETERMINISTIC_FILL")

    output = []
    for tid, row in sorted(selected.items()):
        p = proj.get(tid, {})
        status = "SUPPORTED" if p.get("gold_supported") else ("OPAQUE" if p.get("packet_reference_class") == "GOLD_REFERENCE_OPAQUE" else "NO_GOLD_ASSOCIATION")
        output.append({
            "target_job_id": tid,
            "task": row["task"],
            "family": row["family"],
            "split": row.get("split"),
            "obligation_id": row["obligation_id"],
            "target": row["target"],
            "edit_type": row.get("edit_type"),
            "gold_formula": row.get("gold_formula"),
            "gold_fingerprint": row.get("gold_fingerprint"),
            "primary": bool(row.get("primary")),
            "reference_support": status,
            "fingerprint_existing": p.get("fingerprint_existing"),
            "static_projection_complete": p.get("C7_ALL", {}).get("complete"),
            "selection_reasons": sorted(set(reasons[tid])),
            "obligation": row["obligation"],
            "packet_meta": row["packet_meta"],
        })
    return output


def compact_item(item: Any, *, include_text: bool = True) -> Any:
    if not isinstance(item, dict):
        return item
    keys = ("id", "cell_id", "row_id", "col_id", "sheet_id", "title", "address", "text", "query", "period_key", "header_text", "axis", "period", "class_id", "formula_id")
    if not include_text:
        keys = tuple(key for key in keys if key not in {"text", "query", "header_text"})
    return {key: item[key] for key in keys if key in item}


def canonical_ref_id(key: tuple[str, str, int, int, int | None, int | None]) -> str:
    kind, sid, r1, c1, r2, c2 = key
    sid = sid.removeprefix("sheet:")
    if kind == "POINT":
        return f"cell:{sid}:r{r1}:c{c1}"
    return f"range:{sid}:r{r1}:c{c1}:r{r2}:c{c2}"


def ids_from_value(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for child in value.values():
            out |= ids_from_value(child)
    elif isinstance(value, list):
        for child in value:
            out |= ids_from_value(child)
    elif isinstance(value, str) and re.match(r"^(?:cell|sheet|row|col|text|tcoord|temporal|formula|formula_class|range|dep):", value):
        out.add(value)
    return out


def compress_ids(ids: set[str]) -> dict[str, Any]:
    """Losslessly compress contiguous canonical cell IDs for model context."""
    cell_groups: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    cell_column_groups: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    col_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    row_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    axis_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    other = []
    for value in sorted(ids):
        match = re.fullmatch(r"(cell|text|formula):(s\d+):r(\d+):c(\d+)", value)
        if match:
            cell_groups[(match.group(1), match.group(2), int(match.group(3)))].append(int(match.group(4)))
            cell_column_groups[(match.group(1), match.group(2), int(match.group(4)))].append(int(match.group(3)))
            continue
        match = re.fullmatch(r"(col):(s\d+):c(\d+)", value)
        if match:
            col_groups[(match.group(1), match.group(2))].append(int(match.group(3)))
            continue
        match = re.fullmatch(r"(row):(s\d+):r(\d+)", value)
        if match:
            row_groups[(match.group(1), match.group(2))].append(int(match.group(3)))
            continue
        match = re.fullmatch(r"(tcoord|temporal):(s\d+):([a-z]):(\d+)", value)
        if match:
            axis_groups[(match.group(1), match.group(2), match.group(3))].append(int(match.group(4)))
        else:
            other.append(value)
    rows = []
    for (kind, sheet, row), columns in sorted(cell_groups.items()):
        runs = []
        start = previous = columns[0]
        for column in columns[1:]:
            if column == previous + 1:
                previous = column
            else:
                runs.append([start, previous])
                start = previous = column
        runs.append([start, previous])
        rows.append({"kind": kind, "sheet": sheet, "row": row, "column_runs": runs})
    columns_for_cells = []
    for (kind, sheet, column), values in sorted(cell_column_groups.items()):
        columns_for_cells.append({"kind": kind, "sheet": sheet, "column": column, "row_runs": _runs(values)})
    columns = []
    for (kind, sheet), values in sorted(col_groups.items()):
        columns.append({"kind": kind, "sheet": sheet, "column_runs": _runs(values)})
    row_runs = []
    for (kind, sheet), values in sorted(row_groups.items()):
        row_runs.append({"kind": kind, "sheet": sheet, "row_runs": _runs(values)})
    axes = [{"kind": kind, "sheet": sheet, "axis": axis, "index_runs": _runs(values)} for (kind, sheet, axis), values in sorted(axis_groups.items())]
    row_json = json.dumps(rows, separators=(",", ":"))
    column_json = json.dumps(columns_for_cells, separators=(",", ":"))
    return {"encoding": "canonical_entity_runs_v4", "cell_axis": "row" if len(row_json) <= len(column_json) else "column", "cells": rows if len(row_json) <= len(column_json) else columns_for_cells, "columns": columns, "rows": row_runs, "axes": axes, "other_ids": other}


def _runs(values: list[int]) -> list[list[int]]:
    values = sorted(set(values))
    if not values:
        return []
    result = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
        else:
            result.append([start, previous])
            start = previous = value
    result.append([start, previous])
    return result


def model_bootstrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove evaluator/serialization metadata while retaining all evidence."""
    value = json.loads(json.dumps(payload, ensure_ascii=False))
    for key in ("bootstrap_entity_ids", "bootstrap_sha256", "bootstrap_too_large", "model_bootstrap_tokens", "bootstrap_tokens", "mechanism_counts", "formula_count", "reference_count"):
        value.pop(key, None)
    value.get("grounded_core", {}).pop("fields", None)

    def strip_encoding(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("encoding", None)
            for child in node.values():
                strip_encoding(child)
        elif isinstance(node, list):
            for child in node:
                strip_encoding(child)
    strip_encoding(value)
    return value


def bootstrap_for(row: dict[str, Any]) -> dict[str, Any]:
    packet = prior.packet_for(row)
    spine = load(prior.SPINE_ROOT / f"{row['task']}.json")
    index = projection.formula_indexes(spine)
    sid = projection.sid_for(spine, row["target"]["sheet"])
    if sid is None:
        raise ValueError(f"target sheet missing from spine: {row['target_job_id']}")
    target_row, target_col = row["target"]["row"], row["target"]["col"]
    mechanisms = projection.generate_mechanisms(spine, packet, row, index)
    local = projection.local_formulas(index, sid, target_row, target_col)
    row_forms = list(index["by_row"].get((sid, target_row), []))
    col_forms = list(index["by_col"].get((sid, target_col), []))
    formula_records: dict[str, dict[str, Any]] = {}
    for form, provenance in [(f, ["M2"]) for f in local] + [(f, ["M4_ROW"]) for f in row_forms] + [(f, ["M4_COLUMN"]) for f in col_forms]:
        record = formula_records.setdefault(form["id"], {"formula_id": form["id"], "cell_id": form.get("cell_id"), "class_id": form.get("class_id"), "provenance": []})
        record["provenance"] = sorted(set(record["provenance"]) | set(provenance))

    ref_records: dict[str, dict[str, Any]] = {}
    for mechanism in ("M0", "M2", "M4"):
        data = mechanisms[mechanism]
        for key in sorted(data["points"] | data["ranges"]):
            rid = canonical_ref_id(key)
            record = ref_records.setdefault(rid, {"entity_id": rid, "provenance": []})
            record["provenance"].append(mechanism)
    for record in ref_records.values():
        record["provenance"] = sorted(set(record["provenance"]))

    grounded = {}
    for field in ("locus", "subject", "scope", "source"):
        # The obligation carries task wording.  Grounded candidates are
        # losslessly represented by their stable IDs; exact facts remain
        # queryable in SQL and are not repeated as verbose JSON objects.
        grounded[field] = compress_ids(set(projection.packet_ids({field: packet.get(field) or []})))
    packet_ids = set(projection.packet_ids(packet))
    packet_ids |= {item["entity_id"] for item in ref_records.values()}
    for item in formula_records.values():
        packet_ids |= {x for x in (item.get("formula_id"), item.get("cell_id"), item.get("class_id")) if x}

    ordered_formulas = [formula_records[key] for key in sorted(formula_records)]
    formula_ids = {value["formula_id"] for value in ordered_formulas}
    formula_provenance_records = []
    for value in ordered_formulas:
        match = re.fullmatch(r"formula:(s\d+):r(\d+):c(\d+)", value["formula_id"])
        if match:
            code = sum({"M2": 1, "M4_ROW": 2, "M4_COLUMN": 4}.get(provenance, 0) for provenance in value.get("provenance", []))
            formula_provenance_records.append([match.group(1), int(match.group(2)), int(match.group(3)), code])
    formula_payload = {
        "encoding": "grouped_formula_records_v2",
        "formula_ids": compress_ids(formula_ids),
        "cell_ids": {"encoding": "cell_id_is_formula_id_prefix", "formula_prefix": "formula:", "cell_prefix": "cell:"},
        "provenance_records": formula_provenance_records,
        "fingerprint_ids": sorted({value.get("class_id") for value in ordered_formulas if value.get("class_id")}),
    }
    ordered_refs = sorted(ref_records)
    reference_payload = {
        "encoding": "grouped_reference_records_v3",
        "entity_ids": {"encoding": "union_of_provenance_groups_v1", "count": len(ordered_refs)},
        "provenance": {mechanism: compress_ids({key for key, value in ref_records.items() if mechanism in value.get("provenance", [])}) for mechanism in ("M0", "M2", "M4")},
    }
    payload = {
        "target": {"target_id": row["target_job_id"], "sheet": row["target"]["sheet"], "address": row["target"]["address"], "current_input_content": row["target"].get("current_input_content"), "current_input_kind": row["target"].get("current_input_kind")},
        "obligation": row["obligation"],
        "grounded_core": {"fields": packet.get("fields") or {}, **grounded},
        "formula_evidence": formula_payload,
        "reference_candidates": reference_payload,
        "formula_count": len(ordered_formulas),
        "reference_count": len(ordered_refs),
        "bootstrap_entity_ids": sorted(packet_ids),
        "mechanism_counts": {m: {"points": len(mechanisms[m]["points"]), "ranges": len(mechanisms[m]["ranges"]), "formula_ids": len(mechanisms[m]["meta"].get("formula_ids", []))} for m in ("M0", "M2", "M4")},
    }
    model_payload = model_bootstrap_payload(payload)
    payload["model_bootstrap_tokens"] = estimate_tokens(model_payload)
    payload["bootstrap_tokens"] = payload["model_bootstrap_tokens"]
    payload["bootstrap_too_large"] = payload["model_bootstrap_tokens"] > BOOTSTRAP_LIMIT
    payload["bootstrap_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return payload


def freeze() -> dict[str, Any]:
    rows = build_population()
    records = []
    for row in rows:
        bootstrap = bootstrap_for(row)
        records.append({**row, "bootstrap": bootstrap})
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "narrow_population.json", {"n": len(records), "rows": records})
    contract = Path(ROOT / "benchmark/workbook_spine_contract.md").read_text(encoding="utf-8")
    strong = prior.sql_strong_context("", {})
    freeze_data = {
        "generated_at": datetime.now(UTC).isoformat(), "model": MODEL, "temperature": 0, "reasoning": "medium", "max_calls": MAX_CALLS,
        "arms": list(ARMS), "bootstrap_mechanisms": ["M0", "M2", "M4"], "bootstrap_limit_tokens": BOOTSTRAP_LIMIT,
        "result_row_limit": RESULT_ROW_LIMIT, "result_byte_limit": RESULT_BYTE_LIMIT, "episode_token_limit": EPISODE_TOKEN_LIMIT,
        "gold_in_model_context": False, "formula_synthesis": False, "workbook_edits": False,
        "population_sha256": hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "contract_sha256": hashlib.sha256(contract.encode()).hexdigest(), "strong_context_sha256": hashlib.sha256(strong.encode()).hexdigest(),
        "bootstrap_too_large": sum(bool(row["bootstrap"]["bootstrap_too_large"]) for row in records),
    }
    write(OUT / "freeze.json", freeze_data)
    write(OUT / "context_R0_CURRENT_SQL.txt", prior.sql_strong_context("", {}))
    write(OUT / "context_R1_HYBRID_SQL.txt", hybrid_system())
    return freeze_data


def hybrid_system() -> str:
    return prior.sql_strong_context("", {}) + """

HYBRID PROTOCOL:
The deterministic bootstrap is the initial evidence and the harness maintains a
monotone working set outside your memory. Every SQL result is automatically
added to that working set. Do not try to reproduce or remember all IDs in a
final answer. Use execute_sql(sql) to expand the evidence when needed. Preserve
ambiguity and do not invent or delete candidates. Finish with exactly:
{"action":"final","status":"ENOUGH_EVIDENCE"|"UNRESOLVED"}
"""


def canonicalize_ids(ids: set[str]) -> set[str]:
    out = set()
    for value in ids:
        if value.startswith("cell:"):
            out.add(prior.canonical_cell_id(value))
        elif value.startswith("formula:"):
            out.add(prior.canonical_formula_id(value))
        elif value.startswith("range:"):
            out.add(prior.canonical_range_id(*range_parts(value)))
        else:
            out.add(value)
    return out


def range_parts(value: str) -> tuple[str, int, int, int, int]:
    match = re.fullmatch(r"range:(s\d+):r(\d+):c(\d+):r(\d+):c(\d+)", value)
    if not match:
        raise ValueError(value)
    return f"sheet:{match.group(1)}", *(int(match.group(i)) for i in range(2, 6))


def summary_text(row: dict[str, Any], working: set[str], history: list[dict[str, Any]], latest: dict[str, Any] | None, *, bootstrap: bool = False) -> str:
    counts = Counter()
    for value in working:
        counts[value.split(":", 1)[0]] += 1
    state = {
        "SESSION_STATE": {
            "target": row["target"], "obligation": row["obligation"],
            "working_set_counts": dict(sorted(counts.items())),
            "working_set_entity_ids": sorted(working) if bootstrap else sorted(x for x in working if x.startswith(("cell:", "formula:", "range:", "formula_class:"))),
            "query_history": history,
        }
    }
    if latest is not None:
        state["LATEST_SQL_RESULT"] = latest
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"))


def safe_call(api_key: str, system: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    if MODEL != "z-ai/glm-5.3-flash" or MODEL.lower().startswith("openai/") or MODEL.lower().startswith("gpt"):
        raise RuntimeError(f"model guard rejected {MODEL}")
    body = {"model": MODEL, "max_tokens": 1800, "temperature": 0.0, "reasoning": {"effort": "medium"}, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}] + messages}
    request = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "X-Title": "librecalc-hybrid-sql-retrieval"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode())
        choices = payload.get("choices") or []
        content = (choices[0].get("message") or {}).get("content", "") if choices else ""
        return {"http_ok": True, "text": content or "", "usage": payload.get("usage"), "payload_model": payload.get("model")}
    except urllib.error.HTTPError as exc:
        return {"http_ok": False, "status": exc.code, "failure_class": "MODEL_ACCESS_FAILURE", "detail": exc.read().decode(errors="replace")[:1000]}
    except (urllib.error.URLError, TimeoutError, TimeoutError, http.client.IncompleteRead, ConnectionResetError, OSError) as exc:
        return {"http_ok": False, "status": 0, "failure_class": "MODEL_ACCESS_FAILURE", "detail": f"{type(exc).__name__}: {str(exc)[:500]}"}


def result_ids(result: dict[str, Any]) -> set[str]:
    return canonicalize_ids(ids_from_value(result))


def run_episode(row: dict[str, Any], arm: str, api_key: str, task_counts: dict[str, int]) -> dict[str, Any]:
    executor = prior.ReadOnlySqlite(prior.db_path(row["task"]), max_rows=RESULT_ROW_LIMIT, max_bytes=RESULT_BYTE_LIMIT)
    system = prior.sql_strong_context("", task_counts.get(row["task"], {}))
    if arm == "R1_HYBRID_SQL":
        system = system + "\n" + hybrid_system()
    boot = row["bootstrap"]
    if boot.get("bootstrap_too_large"):
        return {"target_job_id": row["target_job_id"], "arm": arm, "model": MODEL, "status": "BOOTSTRAP_TOO_LARGE", "model_ok": False, "failure_class": "BOOTSTRAP_TOO_LARGE", "bootstrap_tokens": boot["bootstrap_tokens"], "calls": []}
    gold_points, gold_ranges, gold_supported = prior.evaluator_refs({**row, "target": row["target"]})
    if arm == "R0_CURRENT_SQL":
        original = next(item for item in prior.retrieval_population() if item["target_job_id"] == row["target_job_id"])
        initial = prior.bootstrap(original, prior.packet_for(original))
    else:
        initial = json.dumps(model_bootstrap_payload(boot), ensure_ascii=False, separators=(",", ":"))
    working = canonicalize_ids(set(boot.get("bootstrap_entity_ids", [])) if arm == "R1_HYBRID_SQL" else ids_from_value(prior.packet_for(original)))
    initial_bootstrap_tokens = boot.get("bootstrap_tokens", estimate_tokens(initial)) if arm == "R1_HYBRID_SQL" else estimate_tokens(initial)
    initial_bootstrap_ids = set(working)
    history: list[dict[str, Any]] = []
    calls = []
    latest: dict[str, Any] | None = None
    messages = [{"role": "user", "content": initial}]
    started = time.perf_counter()
    materialized = 0
    for q in range(1, MAX_CALLS + 1):
        response = safe_call(api_key, system, messages)
        if not response.get("http_ok"):
            calls.append({"q": q, "model_ok": False, **response})
            break
        text = response.get("text") or ""
        action = prior.extract_action(text)
        usage = response.get("usage") or {}
        record = {"q": q, "model_ok": True, "raw_text": text[:12000], "usage": usage, "action": action}
        if not isinstance(action, dict):
            record["result"] = {"status": "ACTION_ERROR", "error": "Expected JSON action"}
            calls.append(record)
            if arm == "R1_HYBRID_SQL":
                messages = [{"role": "user", "content": summary_text(row, working, history, record["result"])}]
            else:
                messages.extend([{"role": "assistant", "content": text}, {"role": "user", "content": json.dumps({"retrieval_result": record["result"]})}])
            continue
        if action.get("action") == "final":
            record["final"] = True
            calls.append(record)
            break
        sql = action.get("sql") if action.get("action") == "execute_sql" else ""
        result = executor.execute(sql) if sql else {"status": "ACTION_ERROR", "error": "Expected execute_sql action"}
        result_token_estimate = estimate_tokens(result)
        if result.get("status") == "OK" and materialized + result_token_estimate > EPISODE_TOKEN_LIMIT:
            result = {"status": "RESULT_TOO_LARGE", "row_count": result.get("row_count"), "configured_episode_token_limit": EPISODE_TOKEN_LIMIT, "estimated_result_tokens": result_token_estimate}
        elif result.get("status") == "OK":
            materialized += result_token_estimate
        added = result_ids(result) - working
        working |= result_ids(result)
        coverage = prior.coverage(working, gold_points, gold_ranges)
        record.update({"interface": "sql", "sql": sql[:12000], "sql_classification": prior.classify_sql(sql), "result": result, "result_id_count": len(result_ids(result)), "new_working_set_ids": sorted(added), "cumulative_coverage": coverage})
        calls.append(record)
        history.append({"q": q, "status": result.get("status"), "row_count": result.get("row_count"), "new_ids": len(added), "sql_kind": prior.classify_sql(sql).get("query_kind")})
        if arm == "R1_HYBRID_SQL":
            latest = result
            messages = [{"role": "user", "content": summary_text(row, working, history, latest)}]
        else:
            messages.extend([{"role": "assistant", "content": text}, {"role": "user", "content": json.dumps({"retrieval_result": result, "retrieved_entity_ids_in_result": sorted(result_ids(result))}, ensure_ascii=False, separators=(",", ":"))}])
    final_coverage = prior.coverage(working, gold_points, gold_ranges)
    return {
        "target_job_id": row["target_job_id"], "task": row["task"], "family": row["family"], "obligation_id": row["obligation_id"], "target": row["target"], "edit_type": row.get("edit_type"), "primary": row.get("primary"), "arm": arm, "model": MODEL,
        "gold_supported_evaluator_only": gold_supported, "gold_point_count": len(gold_points), "gold_range_count": len(gold_ranges), "bootstrap_entity_count": len(initial_bootstrap_ids), "bootstrap_formula_count": boot.get("formula_count", 0) if arm == "R1_HYBRID_SQL" else 0, "bootstrap_reference_count": boot.get("reference_count", 0) if arm == "R1_HYBRID_SQL" else 0, "bootstrap_tokens": initial_bootstrap_tokens, "bootstrap_coverage": prior.coverage(initial_bootstrap_ids, gold_points, gold_ranges),
        "working_set_counts": dict(Counter(x.split(":", 1)[0] for x in working)), "working_set_ids": sorted(working), "working_set_size": len(working), "retrieved_evidence_coverage": final_coverage, "status": "MODEL_ACCESS_FAILURE" if any(not c.get("model_ok") for c in calls) else ("ENOUGH_EVIDENCE" if calls and calls[-1].get("final") else "UNRESOLVED"), "calls_used": len(calls), "sql_calls": sum(1 for c in calls if c.get("interface") == "sql"), "materialized_tokens": materialized, "session_summary_tokens": sum(estimate_tokens(c.get("result", {})) for c in calls if arm == "R1_HYBRID_SQL"), "model_output_tokens": sum(estimate_tokens(c.get("raw_text", "")) for c in calls), "elapsed_s": round(time.perf_counter() - started, 3), "calls": calls,
    }


def load_dotenv() -> None:
    prior.load_dotenv()


def freeze_and_prepare() -> list[dict[str, Any]]:
    freeze()
    return load(OUT / "narrow_population.json")["rows"]


def run(arm: str, worker_index: int = 0, worker_count: int = 1) -> None:
    if worker_index < 0 or worker_index >= worker_count:
        raise SystemExit("worker index must be in [0, worker count)")
    rows = load(OUT / "narrow_population.json")["rows"]
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required")
    path = OUT / (f"calls_{arm}.jsonl" if worker_count == 1 else f"calls_{arm}.worker{worker_index:02d}.jsonl")
    done = {row["target_job_id"] for row in arm_rows(arm) if row.get("status") != "MODEL_ACCESS_FAILURE"}
    manifest = load(prior.OUT / "database_manifest.json")
    counts = {str(x.get("workbook_id", "")).removeprefix("wb:"): x.get("counts") or {} for x in manifest.get("workbooks", [])}
    with path.open("a", encoding="utf-8") as handle:
        assigned = [row for i, row in enumerate(rows) if i % worker_count == worker_index]
        pending = [row for row in assigned if row["target_job_id"] not in done]
        print(f"RUN {arm} worker={worker_index}/{worker_count} remaining={len(pending)}/{len(assigned)}", flush=True)
        for i, row in enumerate(pending, 1):
            record = run_episode(row, arm, key, counts)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"CALL {arm} worker={worker_index} {i}/{len(pending)} {row['target_job_id']} calls={record['calls_used']} status={record['status']}", flush=True)


def valid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("status") != "MODEL_ACCESS_FAILURE" and row.get("status") != "BOOTSTRAP_TOO_LARGE"]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row.get("gold_supported_evaluator_only")]
    def mean(path: str) -> float | None:
        values = []
        for row in eligible:
            value: Any = row
            for part in path.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if value is not None:
                values.append(value)
        return round(statistics.mean(values), 4) if values else None
    return {"n": len(rows), "supported": len(eligible), "point_recall": mean("retrieved_evidence_coverage.point_recall"), "range_recall": mean("retrieved_evidence_coverage.range_recall"), "complete_rate": mean("retrieved_evidence_coverage.complete"), "bootstrap_complete_rate": mean("bootstrap_coverage.complete"), "mean_calls": mean("calls_used"), "median_calls": statistics.median([row["calls_used"] for row in eligible]) if eligible else None, "p90_calls": sorted([row["calls_used"] for row in eligible])[max(0, int(len(eligible) * .9) - 1)] if eligible else None, "mean_input_tokens": round(statistics.mean(sum((call.get("usage") or {}).get("prompt_tokens", 0) or 0 for call in row.get("calls", [])) for row in eligible)) if eligible else None, "mean_output_tokens": round(statistics.mean(sum((call.get("usage") or {}).get("completion_tokens", 0) or 0 for call in row.get("calls", [])) for row in eligible)) if eligible else None, "mean_materialized_tokens": mean("materialized_tokens"), "mean_bootstrap_tokens": mean("bootstrap_tokens"), "model_access_failures": sum(row.get("status") == "MODEL_ACCESS_FAILURE" for row in rows)}


def curves(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for q in range(0, MAX_CALLS + 1):
        eligible = [row for row in rows if row.get("gold_supported_evaluator_only")]
        covs = []
        for row in eligible:
            if q == 0:
                covs.append(row["bootstrap_coverage"])
            else:
                values = [call.get("cumulative_coverage") for call in row.get("calls", []) if call.get("q", 0) <= q and call.get("cumulative_coverage")]
                covs.append(values[-1] if values else row["bootstrap_coverage"])
        out.append({"q": q, "n": len(covs), "point_recall": round(statistics.mean(x["point_recall"] for x in covs), 4) if covs else None, "range_recall": round(statistics.mean(x["range_recall"] for x in covs), 4) if covs else None, "complete_rate": round(statistics.mean(x["complete"] for x in covs), 4) if covs else None})
    return out


def report() -> dict[str, Any]:
    population = load(OUT / "narrow_population.json")["rows"]
    result = {"title": "Hybrid deterministic bootstrap plus SQL retrieval probe", "generated_at": datetime.now(UTC).isoformat(), "freeze": load(OUT / "freeze.json"), "population": {"n": len(population), "supported": sum(row["reference_support"] == "SUPPORTED" for row in population), "strata": Counter(reason for row in population for reason in row["selection_reasons"])}, "arms": {}, "curves": {}, "static_baseline": load(PROJECTION_OUT / "report.json").get("stage_frontier", {}).get("C7_ALL"), "previous_sql_baseline": 0.451, "verdict": None}
    for arm in ARMS:
        rows = arm_rows(arm)
        scored = valid(rows)
        result["arms"][arm] = summarize(scored)
        result["curves"][arm] = curves(scored)
    r0 = result["arms"].get("R0_CURRENT_SQL", {}).get("complete_rate") or 0
    r1 = result["arms"].get("R1_HYBRID_SQL", {}).get("complete_rate") or 0
    static = (result["static_baseline"] or {}).get("complete_rate", 0.5882)
    if r1 >= r0 + 0.10 and r1 >= static:
        result["verdict"] = "HYBRID_STRONG"
    elif r1 >= r0 + 0.05:
        result["verdict"] = "HYBRID_PARTIAL"
    elif r1 <= r0 - 0.05:
        result["verdict"] = "HYBRID_HARMFUL"
    elif abs(r1 - r0) <= 0.05:
        result["verdict"] = "HYBRID_NEUTRAL"
    else:
        result["verdict"] = "SQL_PROTOCOL_WEAK"
    write(OUT / "report.json", result)
    return result


def tail_rows() -> list[dict[str, Any]]:
    """Freeze the evaluator-only q8-incomplete R1 tail population."""
    population = {row["target_job_id"]: row for row in load(OUT / "narrow_population.json")["rows"]}
    rows = {row["target_job_id"]: row for row in arm_rows("R1_HYBRID_SQL")}
    selected = []
    for target_id in sorted(rows):
        row = rows[target_id]
        if row.get("gold_supported_evaluator_only") and not row.get("retrieved_evidence_coverage", {}).get("complete"):
            selected.append({"target_job_id": target_id, "selection": "R1_Q8_INCOMPLETE_SUPPORTED", "q8_complete": False, "task": population[target_id]["task"]})
    write(OUT / "tail_population.json", {"n": len(selected), "rows": selected})
    return selected


def run_tail(worker_index: int = 0, worker_count: int = 1) -> None:
    if worker_index < 0 or worker_index >= worker_count:
        raise SystemExit("worker index must be in [0, worker count)")
    tail = tail_rows()
    all_r1 = {row["target_job_id"]: row for row in arm_rows("R1_HYBRID_SQL")}
    population = {row["target_job_id"]: row for row in load(OUT / "narrow_population.json")["rows"]}
    path = OUT / f"tail_R1.worker{worker_index:02d}.jsonl"
    done = {row["target_job_id"] for row in read_jsonl(path)}
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required")
    manifest = load(prior.OUT / "database_manifest.json")
    counts = {str(x.get("workbook_id", "")).removeprefix("wb:"): x.get("counts") or {} for x in manifest.get("workbooks", [])}
    assigned = [item for i, item in enumerate(tail) if i % worker_count == worker_index and item["target_job_id"] not in done]
    print(f"TAIL R1 worker={worker_index}/{worker_count} remaining={len(assigned)}/{sum(i % worker_count == worker_index for i in range(len(tail)))}", flush=True)
    with path.open("a", encoding="utf-8") as handle:
        for i, item in enumerate(assigned, 1):
            target_id = item["target_job_id"]
            prior_row = all_r1[target_id]
            row = population[target_id]
            gold_points, gold_ranges, _ = prior.evaluator_refs({**row, "target": row["target"]})
            executor = prior.ReadOnlySqlite(prior.db_path(row["task"]), max_rows=RESULT_ROW_LIMIT, max_bytes=RESULT_BYTE_LIMIT)
            system = prior.sql_strong_context("", counts.get(row["task"], {})) + "\n" + hybrid_system()
            working = canonicalize_ids(set(prior_row.get("working_set_ids", [])))
            history = []
            latest = None
            for call in prior_row.get("calls", []):
                if call.get("interface") == "sql":
                    result = call.get("result") or {}
                    classification = call.get("sql_classification") or prior.classify_sql(call.get("sql", ""))
                    history.append({"q": call.get("q"), "status": result.get("status"), "row_count": result.get("row_count"), "new_ids": len(call.get("new_working_set_ids", [])), "sql_kind": classification.get("query_kind")})
                    latest = result
            messages = [{"role": "user", "content": summary_text(row, working, history, latest)}]
            calls = []
            materialized = 0
            started = time.perf_counter()
            for offset in range(1, 5):
                q = MAX_CALLS + offset
                response = safe_call(key, system, messages)
                if not response.get("http_ok"):
                    calls.append({"q": q, "model_ok": False, **response})
                    break
                text = response.get("text") or ""
                action = prior.extract_action(text)
                usage = response.get("usage") or {}
                record = {"q": q, "model_ok": True, "raw_text": text[:12000], "usage": usage, "action": action}
                if not isinstance(action, dict):
                    record["result"] = {"status": "ACTION_ERROR", "error": "Expected JSON action"}
                    calls.append(record)
                    messages = [{"role": "user", "content": summary_text(row, working, history, record["result"])}]
                    continue
                if action.get("action") == "final":
                    record["final"] = True
                    calls.append(record)
                    break
                sql = action.get("sql") if action.get("action") == "execute_sql" else ""
                result = executor.execute(sql) if sql else {"status": "ACTION_ERROR", "error": "Expected execute_sql action"}
                result_tokens = estimate_tokens(result)
                if result.get("status") == "OK" and materialized + result_tokens > EPISODE_TOKEN_LIMIT:
                    result = {"status": "RESULT_TOO_LARGE", "row_count": result.get("row_count"), "configured_episode_token_limit": EPISODE_TOKEN_LIMIT, "estimated_result_tokens": result_tokens}
                elif result.get("status") == "OK":
                    materialized += result_tokens
                result_ids_value = result_ids(result)
                added = result_ids_value - working
                working |= result_ids_value
                record.update({"interface": "sql", "sql": sql[:12000], "sql_classification": prior.classify_sql(sql), "result": result, "result_id_count": len(result_ids_value), "new_working_set_ids": sorted(added), "cumulative_coverage": prior.coverage(working, gold_points, gold_ranges)})
                calls.append(record)
                history.append({"q": q, "status": result.get("status"), "row_count": result.get("row_count"), "new_ids": len(added), "sql_kind": prior.classify_sql(sql).get("query_kind")})
                messages = [{"role": "user", "content": summary_text(row, working, history, result)}]
            final = prior.coverage(working, gold_points, gold_ranges)
            output = {"target_job_id": target_id, "model": MODEL, "q8_working_set_size": prior_row.get("working_set_size"), "q8_coverage": prior_row.get("retrieved_evidence_coverage"), "q12_coverage": final, "calls": calls, "calls_used": len(calls), "materialized_tokens": materialized, "elapsed_s": round(time.perf_counter() - started, 3), "status": "MODEL_ACCESS_FAILURE" if any(not c.get("model_ok") for c in calls) else "TAIL_COMPLETE"}
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"TAIL R1 worker={worker_index} {i}/{len(assigned)} {target_id} calls={len(calls)} status={output['status']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--arm", choices=ARMS, required=True)
    run_parser.add_argument("--worker-index", type=int, default=0)
    run_parser.add_argument("--worker-count", type=int, default=1)
    sub.add_parser("report")
    tail_parser = sub.add_parser("tail")
    tail_parser.add_argument("--worker-index", type=int, default=0)
    tail_parser.add_argument("--worker-count", type=int, default=1)
    args = parser.parse_args()
    if args.command == "freeze":
        print(json.dumps(freeze(), indent=2))
    elif args.command == "run":
        run(args.arm, args.worker_index, args.worker_count)
    elif args.command == "tail":
        run_tail(args.worker_index, args.worker_count)
    else:
        print(json.dumps(report(), indent=2))


if __name__ == "__main__":
    main()
