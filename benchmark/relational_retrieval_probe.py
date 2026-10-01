#!/usr/bin/env python3
"""Controlled retrieval experiment over relational workbook spines.

The model retrieves evidence only. It never edits a workbook and never sees
gold formulas or evaluator-side reference sets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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

from formula_operational import parse_use_def_slots  # noqa: E402
from task_obligation_compile import extract_json_object  # noqa: E402
from workbook_spine_sqlite import (  # noqa: E402
    DDL_CONTEXT,
    ReadOnlySqlite,
    TypedWorkbookApi,
    build_database,
    canonical_cell_id,
    canonical_formula_id,
    canonical_range_id,
    canonical_sheet_id,
    database_id_inventory,
)

SYNTH = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-synthesis-probe"
SPINE_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe/spines"
TEMPORAL_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-closure-probe/coords"
PACKET_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/closed-world-resolver-probe"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/relational-retrieval-probe"
DB_ROOT = OUT / "db"
MODEL = "z-ai/glm-5.3-flash"
BLOCKED_MODELS = {"openai/gpt-5.6-sol", "openai/gpt-5.6"}
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ARMS = ("A_TYPED_API_STRONG_CONTEXT", "B_SQL_STRONG_CONTEXT", "C_SQL_BARE_SCHEMA")
MAX_CALLS = 8
RESULT_ROW_LIMIT = 5000
RESULT_BYTE_LIMIT = 8_000_000
EPISODE_TOKEN_LIMIT = 30_000
HELD_OUT = {"07", "08", "14", "19", "20"}
KNOWN_CASE_BINDINGS = {
    ("04_05", "O5", "K6"), ("09_05", "O2", "K163"), ("09_05", "O2", "L163"),
    ("14_05", "O2", "D10"), ("20_04", "O1", "H41"), ("14_05", "O5", "J31"),
    ("08_01", "O6", "J46"), ("08_01", "O3", "AF66"), ("08_01", "O3", "AG66"),
    ("17_03", "O6", "K104"), ("15_04", "O1", "Y39"), ("15_04", "O1", "Y40"),
}

COMMON_PROMPT = """You are performing evidence retrieval for one exact spreadsheet target.

You have an ORACLE obligation, an exact target cell, and a grounded bootstrap.
Retrieve workbook entities and formula/program evidence needed for a later
formula-synthesis step. Do not synthesize a formula now. Do not edit anything.

The database is complete and immutable. Preserve ambiguity: retrieve all
mechanically plausible evidence rather than choosing a single source merely
because it appears first. Do not invent IDs or workbook objects. Resolver-like
preferences are not authoritative and never remove candidates.

At every turn return exactly one JSON object and nothing else. Never emit a raw
SQL object separately from the action object. For a retrieval action use the interface
documented for this arm. To finish use:
{"action":"final","candidate_reference_ids":[],"candidate_formula_ids":[],"status":"ENOUGH_EVIDENCE"|"NEED_MORE"|"UNRESOLVED"}

Candidate reference IDs should be canonical cell IDs or canonical range IDs
returned by the database. Candidate formula IDs should be canonical formula
IDs returned by the database. You may make at most 8 retrieval calls.
"""

TYPED_DOC = """This arm exposes only these mechanical typed operations over the same database:

get_entities(ids: string[])
text_matches(text: string, sheet_ids?: string[])
formulas_in_row(row_id: string)
formulas_in_column(col_id: string)
references_of(formula_ids: string[])
dependents_of(entity_ids: string[])
formula_class_members(fingerprint_id: string)
temporal_at(sheet_id: string, axis: string, axis_index: integer)
entities_at_period(year?: integer, month?: integer)
translate_formula(formula_id: string, target_cell_id: string)

Return an action such as:
{"action":"typed_api","operation":"formulas_in_row","args":{"row_id":"row:s03:r41"}}

The API returns {status, columns, rows, row_count, elapsed_ms}. RESULT_TOO_LARGE
means refine the operation; results are never silently truncated.
"""

SQL_CONTRACT = """Use execute_sql(sql) against the immutable workbook database. Only SELECT/WITH
queries are allowed. Results have columns, rows, row_count, elapsed_ms, and may
return RESULT_TOO_LARGE; there is no hidden first-N truncation. Use canonical
IDs returned by one query in later queries. Preserve ambiguity and do not
invent workbook objects.

Important relation meanings:
- cells: one materialized workbook cell or explicit reference endpoint; physical
  existence is not task relevance.
- formulas: source formula attached to a formula cell.
- formula_classes: location-relative mechanical formula identity, not business
  semantic equivalence or authorization to copy.
- point_references: explicit single-cell formula slots.
- ranges/range_references: explicit rectangular range slots; not interchangeable
  with arbitrary point lists.
- text_anchors: exact/normalized workbook text; text similarity is not identity.
- temporal_coordinates: direct or propagated time identity from frozen E1-E3
  closure; do not rediscover long chains.

Warnings: dependency does not imply a missing formula; repeated patterns are not
output invariants; multiple entities may remain valid; formula classes are
evidence, not authorization; preserve ambiguity.
"""

SQL_EXAMPLES = """Generic examples:
1. SELECT formula_id, cell_id, fingerprint_id FROM row_formulas WHERE row_id='row:s03:r41' ORDER BY cell_id;
2. SELECT f.formula_id, f.cell_id, p.referenced_cell_id FROM formulas f JOIN point_references p USING(formula_id) WHERE f.fingerprint_id='formula_class:...';
3. SELECT f.formula_id, f.cell_id FROM formulas f JOIN cells c USING(cell_id) WHERE c.sheet_id='sheet:s03' AND c.col_idx=8 ORDER BY c.row_idx;
4. SELECT a.cell_id, a.exact_text FROM text_anchors a WHERE a.normalized_text LIKE '%revenue%';
5. SELECT temporal_id, cell_id, year, month, period_key FROM temporal_coordinates WHERE sheet_id='sheet:s03' AND axis='column' ORDER BY axis_index;
6. SELECT p.formula_id, p.referenced_cell_id FROM point_references p WHERE p.referenced_cell_id='cell:s03:r41:c8';
7. WITH siblings AS (SELECT formula_id, cell_id, fingerprint_id FROM formulas WHERE fingerprint_id='formula_class:...') SELECT * FROM siblings;
8. SELECT f.formula_id, f.cell_id, r.range_id, r.r1, r.c1, r.r2, r.c2 FROM formulas f JOIN range_references rr USING(formula_id) JOIN ranges r USING(range_id) WHERE f.cell_id LIKE 'cell:s03:%';
"""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def all_population() -> list[dict[str, Any]]:
    return load_json(SYNTH / "population.json")["rows"]


def population() -> list[dict[str, Any]]:
    return [x for x in all_population() if x.get("primary") and x.get("family") in HELD_OUT]


def retrieval_population() -> list[dict[str, Any]]:
    rows = population()
    seen = {(x["task"], x["obligation_id"], x["target"]["address"]) for x in rows}
    for row in all_population():
        key = (row["task"], row["obligation_id"], row["target"]["address"])
        if key in KNOWN_CASE_BINDINGS and key not in seen:
            rows.append(row)
            seen.add(key)
    return rows


def packet_for(row: dict[str, Any]) -> dict[str, Any]:
    return load_json(PACKET_ROOT / row["packet_meta"]["packet_path"])["packet"]


def db_path(task: str) -> Path:
    return DB_ROOT / f"{task}.sqlite"


def build_all() -> dict[str, Any]:
    rows = load_json(SYNTH / "population.json")["rows"]
    tasks = sorted({r["task"] for r in rows})
    outputs = []
    for task in tasks:
        result = build_database(SPINE_ROOT / f"{task}.json", TEMPORAL_ROOT / f"{task}.json", db_path(task))
        outputs.append(result)
        print(f"DB {task} cells={result['counts'].get('cells')} formulas={result['counts'].get('formulas')}", flush=True)
    manifest = {"generated_at": datetime.now(UTC).isoformat(), "schema_version": "workbook_spine_sqlite_v1", "workbooks": outputs}
    write(OUT / "database_manifest.json", manifest)
    return manifest


def schema_without_semantics() -> str:
    # DDL only: no contract, examples, warnings, or table interpretation.
    return DDL_CONTEXT.split("CREATE VIEW", 1)[0].strip() + "\n"


def typed_context() -> str:
    return COMMON_PROMPT + "\n" + Path(ROOT / "benchmark/workbook_spine_contract.md").read_text(encoding="utf-8") + "\n\n" + TYPED_DOC


def sql_strong_context(task: str, counts: dict[str, int]) -> str:
    contract = Path(ROOT / "benchmark/workbook_spine_contract.md").read_text(encoding="utf-8")
    return COMMON_PROMPT + "\n" + contract + "\n\n" + SQL_CONTRACT + "\n\nSQL schema, views, and indexes:\n" + DDL_CONTEXT + "\n\nThis workbook's row counts:\n" + json.dumps(counts, sort_keys=True) + "\n\n" + SQL_EXAMPLES


def sql_bare_context() -> str:
    return COMMON_PROMPT + "\nThe database has these SQLite tables and views. Use execute_sql(sql). Only SELECT/WITH is allowed.\n\n" + schema_without_semantics()


def bootstrap(row: dict[str, Any], packet: dict[str, Any]) -> str:
    obligation = dict(row["obligation"])
    payload = {
        "ORACLE_OBLIGATION": obligation,
        "TARGET": {"target_id": row["target_id"], "sheet": row["target"]["sheet"], "address": row["target"]["address"], "current_input_content": row["target"].get("current_input_content"), "current_input_kind": row["target"].get("current_input_kind")},
        "GROUNDED_BOOTSTRAP": {key: packet.get(key) or [] for key in ("locus", "subject", "scope", "source")},
        "NOTE": "This is the complete bootstrap only. Query the persistent database for additional evidence; no formula or golden reference is supplied.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def freeze() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    contract = Path(ROOT / "benchmark/workbook_spine_contract.md").read_text(encoding="utf-8")
    prompt_by_arm = {"A_TYPED_API_STRONG_CONTEXT": typed_context(), "B_SQL_STRONG_CONTEXT": sql_strong_context("", {}), "C_SQL_BARE_SCHEMA": sql_bare_context()}
    for arm, text in prompt_by_arm.items():
        write(OUT / f"context_{arm}.txt", text)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(), "population_source": str(SYNTH / "population.json"),
        "n_targets": len(population()), "n_known_diagnostic_targets": len(retrieval_population()) - len(population()), "held_out_families": sorted(HELD_OUT), "arms": list(ARMS),
        "model": MODEL, "temperature": 0, "reasoning": "medium", "max_calls": MAX_CALLS,
        "result_row_limit": RESULT_ROW_LIMIT, "result_byte_limit": RESULT_BYTE_LIMIT, "episode_token_limit": EPISODE_TOKEN_LIMIT,
        "gold_in_model_context": False, "workbook_edits": False, "formula_synthesis": False,
        "contract_sha256": hashlib.sha256(contract.encode()).hexdigest(),
        "context_sha256": {arm: hashlib.sha256(text.encode()).hexdigest() for arm, text in prompt_by_arm.items()},
    }
    write(OUT / "freeze.json", payload)
    write(OUT / "population.json", {"n": len(population()), "rows": population()})
    return payload


def id_like(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    patterns = (r"^(?:cell|sheet|row|col|formula|range|text|tcoord|temporal|formula_class):")
    return value if re.match(patterns, value) else None


def collect_ids(result: dict[str, Any]) -> set[str]:
    found = set()
    for row in result.get("rows") or []:
        for value in row.values():
            ident = id_like(value)
            if ident:
                found.add(ident)
    return found


def extract_action(text: str) -> dict[str, Any] | None:
    """Extract one syntactically valid action object without repairing it."""
    decoded = extract_json_object(text)
    if isinstance(decoded, dict) and decoded.get("action"):
        return decoded
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text or ""):
        try:
            candidate, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("action"):
            return candidate
    return None


def classify_sql(sql: str) -> dict[str, Any]:
    upper = sql.upper()
    tables = sorted(set(re.findall(r"\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)", upper)))
    return {"tables": tables, "query_kind": "recursive" if "WITH RECURSIVE" in upper else "aggregation" if re.search(r"\b(GROUP BY|COUNT\s*\(|SUM\s*\(|AVG\s*\(|ROW_NUMBER\s*\()", upper) else "join" if len(tables) > 1 else "lookup", "broad_scan": not bool(re.search(r"\bWHERE\b|\bLIMIT\b", upper)) and bool(set(tables) & {"CELLS", "FORMULAS", "POINT_REFERENCES", "RANGE_REFERENCES"})}


def evaluator_refs(row: dict[str, Any]) -> tuple[set[str], set[str], bool]:
    target = row["target"]
    parsed = parse_use_def_slots(row["gold_formula"], target["sheet"], target["col"], target["row"])
    spine = load_json(SPINE_ROOT / f"{row['task']}.json")
    points, ranges = set(), set()
    for slot in parsed.get("slots") or []:
        idx = (spine.get("title_to_index") or {}).get(slot.get("sheet"))
        if idx is None:
            continue
        sid = f"sheet:s{int(idx):02d}"
        if slot.get("is_range"):
            ranges.add(canonical_range_id(sid, slot["r1"], slot["c1"], slot["r2"], slot["c2"]))
        else:
            points.add(f"cell:{sid.removeprefix('sheet:')}:r{slot['r1']}:c{slot['c1']}")
    return points, ranges, bool(parsed.get("parser_ok")) and not bool(parsed.get("opaque"))


def range_members(range_id: str) -> set[str]:
    m = re.fullmatch(r"range:s(\d+):r(\d+):c(\d+):r(\d+):c(\d+)", range_id)
    if not m:
        return set()
    sid, r1, c1, r2, c2 = f"s{int(m.group(1)):02d}", int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
    return {f"cell:{sid}:r{r}:c{c}" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)}


def coverage(retrieved: set[str], gold_points: set[str], gold_ranges: set[str]) -> dict[str, Any]:
    point_hit = len(gold_points & retrieved)
    range_hit = sum(1 for rid in gold_ranges if rid in retrieved or range_members(rid).issubset(retrieved))
    return {"point_recall": round(point_hit / len(gold_points), 4) if gold_points else 1.0, "range_recall": round(range_hit / len(gold_ranges), 4) if gold_ranges else 1.0, "complete": point_hit == len(gold_points) and range_hit == len(gold_ranges), "point_hits": point_hit, "range_hits": range_hit}


def api_call(api: TypedWorkbookApi, operation: str, args: dict[str, Any]) -> dict[str, Any]:
    methods = {name: getattr(api, name) for name in ("get_entities", "text_matches", "formulas_in_row", "formulas_in_column", "references_of", "dependents_of", "formula_class_members", "temporal_at", "entities_at_period", "translate_formula")}
    if operation not in methods:
        return {"status": "API_ERROR", "error": f"Unknown typed operation: {operation}"}
    try:
        return methods[operation](**args)
    except Exception as exc:
        return {"status": "API_ERROR", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}


def call_model(api_key: str, system: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    if MODEL in BLOCKED_MODELS or MODEL.startswith("openai/"):
        raise RuntimeError(f"Blocked model without explicit approval: {MODEL}")
    body = {"model": MODEL, "max_tokens": 1800, "temperature": 0.0, "reasoning": {"effort": "medium"}, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}] + messages}
    req = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "X-Title": "librecalc-relational-retrieval"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            payload = json.loads(response.read().decode())
            choices = payload.get("choices") or []
            text = (choices[0].get("message") or {}).get("content", "") if choices else ""
            return {"http_ok": True, "text": text, "usage": payload.get("usage"), "payload_model": payload.get("model")}
    except urllib.error.HTTPError as exc:
        return {"http_ok": False, "status": exc.code, "detail": exc.read().decode(errors="replace")[:1000]}
    except urllib.error.URLError as exc:
        return {"http_ok": False, "status": 0, "detail": str(exc.reason)}


def arm_system(arm: str, task_counts: dict[str, int]) -> str:
    if arm == "A_TYPED_API_STRONG_CONTEXT":
        return typed_context()
    if arm == "B_SQL_STRONG_CONTEXT":
        return sql_strong_context("", task_counts)
    return sql_bare_context()


def run_episode(row: dict[str, Any], arm: str, api_key: str, task_counts: dict[str, int]) -> dict[str, Any]:
    db = db_path(row["task"])
    executor = ReadOnlySqlite(db, max_rows=RESULT_ROW_LIMIT, max_bytes=RESULT_BYTE_LIMIT)
    typed = TypedWorkbookApi(executor)
    system = arm_system(arm, task_counts.get(row["task"], {}))
    packet = packet_for(row)
    messages = [{"role": "user", "content": bootstrap(row, packet)}]
    gold_points, gold_ranges, gold_supported = evaluator_refs(row)
    seen_ids: set[str] = set()
    declared_refs: set[str] = set()
    declared_formulas: set[str] = set()
    calls = []
    materialized_tokens = 0
    model_output_tokens = 0
    started = time.perf_counter()
    final: dict[str, Any] | None = None
    for q in range(1, MAX_CALLS + 1):
        response = call_model(api_key, system, messages)
        if not response.get("http_ok"):
            calls.append({"q": q, "model_ok": False, **response})
            break
        model_text = response.get("text") or ""
        model_output_tokens += len(model_text) // 4
        action = extract_action(model_text)
        call_record: dict[str, Any] = {"q": q, "model_ok": True, "raw_text": model_text[:12000], "action": action, "usage": response.get("usage")}
        if not isinstance(action, dict):
            result = {"status": "ACTION_ERROR", "error": "Expected JSON action"}
            call_record["result"] = result
            calls.append(call_record)
            messages.extend([{"role": "assistant", "content": model_text}, {"role": "user", "content": json.dumps({"retrieval_result": result})}])
            continue
        if action.get("action") == "final":
            final = action
            declared_refs.update(x for x in action.get("candidate_reference_ids", []) if isinstance(x, str))
            declared_formulas.update(x for x in action.get("candidate_formula_ids", []) if isinstance(x, str))
            call_record["final"] = True
            calls.append(call_record)
            break
        if arm == "A_TYPED_API_STRONG_CONTEXT" and action.get("action") == "typed_api":
            result = api_call(typed, str(action.get("operation")), action.get("args") or {})
            call_record["interface"] = "typed_api"
            call_record["operation"] = action.get("operation")
        elif arm != "A_TYPED_API_STRONG_CONTEXT" and action.get("action") == "execute_sql":
            sql = action.get("sql") if isinstance(action.get("sql"), str) else ""
            result = executor.execute(sql)
            call_record["interface"] = "sql"
            call_record["sql"] = sql[:12000]
            call_record["sql_classification"] = classify_sql(sql)
        else:
            result = {"status": "ACTION_ERROR", "error": "Action does not match this arm's interface"}
        if result.get("status") == "OK":
            result_tokens = max(1, int(result.get("bytes", len(json.dumps(result, ensure_ascii=False))) / 4))
            if materialized_tokens + result_tokens > EPISODE_TOKEN_LIMIT:
                result = {"status": "RESULT_TOO_LARGE", "row_count": result.get("row_count"), "configured_episode_token_limit": EPISODE_TOKEN_LIMIT, "estimated_result_tokens": result_tokens, "reason": "episode_materialization_budget"}
            else:
                materialized_tokens += result_tokens
        result_ids = collect_ids(result)
        seen_ids.update(result_ids)
        result_text = json.dumps({"retrieval_result": result, "retrieved_entity_ids_in_result": sorted(result_ids)}, ensure_ascii=False, separators=(",", ":"))
        call_record["result"] = result
        call_record["result_id_count"] = len(result_ids)
        call_record["cumulative_coverage"] = coverage(seen_ids, gold_points, gold_ranges)
        calls.append(call_record)
        messages.extend([{"role": "assistant", "content": model_text}, {"role": "user", "content": result_text}])
    final_refs = {canonical_cell_id(x) or x for x in declared_refs}
    final_forms = {canonical_formula_id(x) or x for x in declared_formulas}
    inventory = database_id_inventory(db)
    invalid_refs = sorted(x for x in final_refs if x not in inventory)
    invalid_forms = sorted(x for x in final_forms if x not in inventory)
    final_cov = coverage(final_refs, gold_points, gold_ranges)
    retrieved_cov = coverage(seen_ids, gold_points, gold_ranges)
    sql_calls = [x for x in calls if x.get("interface") == "sql"]
    return {"target_job_id": row["target_job_id"], "primary": bool(row.get("primary")), "task": row["task"], "family": row["family"], "obligation_id": row["obligation_id"], "edit_type": row.get("edit_type"), "target": row["target"], "arm": arm, "model": MODEL, "gold_supported_evaluator_only": gold_supported, "gold_point_count": len(gold_points), "gold_range_count": len(gold_ranges), "candidate_reference_ids": sorted(final_refs), "candidate_formula_ids": sorted(final_forms), "invalid_reference_ids": invalid_refs, "invalid_formula_ids": invalid_forms, "status": final.get("status") if final else "UNRESOLVED", "final_coverage": final_cov, "retrieved_evidence_coverage": retrieved_cov, "calls_used": len(calls), "query_calls": len(sql_calls) if arm != "A_TYPED_API_STRONG_CONTEXT" else sum(1 for x in calls if x.get("interface") == "typed_api"), "materialized_tokens": materialized_tokens, "model_output_tokens": model_output_tokens, "elapsed_s": round(time.perf_counter() - started, 3), "calls": calls}


def run(limit: int | None = None, offset: int = 0, arms: tuple[str, ...] = ARMS, force: bool = False, ledger_path: Path | None = None, target_ids_path: Path | None = None) -> None:
    freeze()
    if not DB_ROOT.exists() or not list(DB_ROOT.glob("*.sqlite")):
        build_all()
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required; freeze and DB build are available with --offline")
    all_rows = retrieval_population()
    if target_ids_path:
        target_ids = {line.strip() for line in target_ids_path.read_text(encoding="utf-8").splitlines() if line.strip()}
        rows = [row for row in all_rows if row["target_job_id"] in target_ids]
    else:
        rows = all_rows[offset:]
        if limit is not None:
            rows = rows[:limit]
    counts_by_task = {}
    manifest = load_json(OUT / "database_manifest.json") if (OUT / "database_manifest.json").exists() else {}
    for item in manifest.get("workbooks", []):
        counts_by_task[str(item.get("workbook_id", "")).removeprefix("wb:")] = item.get("counts") or {}
    for arm in arms:
        path = ledger_path or (OUT / f"calls_{arm}.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        if force:
            path.write_text("", encoding="utf-8")
        done = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    if rec.get("target_job_id") and rec.get("calls") and all(call.get("model_ok") for call in rec["calls"]):
                        done.add(rec["target_job_id"])
                except json.JSONDecodeError:
                    continue
        pending = [row for row in rows if row["target_job_id"] not in done]
        print(f"RUN {arm} remaining={len(pending)}/{len(rows)}", flush=True)
        with path.open("a", encoding="utf-8") as handle:
            for i, row in enumerate(pending, 1):
                record = run_episode(row, arm, key, counts_by_task)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                print(f"CALL {arm} {i}/{len(pending)} {row['target_job_id']} calls={record['calls_used']} status={record['status']}", flush=True)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in records if r.get("gold_supported_evaluator_only")]
    def mean(field: str, source: str = "final_coverage") -> float | None:
        return round(sum(r[source][field] for r in eligible) / len(eligible), 4) if eligible else None
    calls = [c for r in records for c in r.get("calls", [])]
    statuses = Counter((c.get("result") or {}).get("status", "FINAL") for c in calls)
    return {
        "n": len(records), "supported": len(eligible),
        "final_point_recall": mean("point_recall"), "final_range_recall": mean("range_recall"),
        "final_complete_rate": round(sum(r["final_coverage"]["complete"] for r in eligible) / len(eligible), 4) if eligible else None,
        "retrieved_point_recall": mean("point_recall", "retrieved_evidence_coverage"),
        "retrieved_range_recall": mean("range_recall", "retrieved_evidence_coverage"),
        "retrieved_evidence_complete_rate": round(sum(r["retrieved_evidence_coverage"]["complete"] for r in eligible) / len(eligible), 4) if eligible else None,
        "mean_calls": round(sum(r["query_calls"] for r in records) / len(records), 2) if records else None,
        "mean_tokens": round(sum(r["materialized_tokens"] for r in records) / len(records), 1) if records else None,
        "p95_tokens": sorted((r["materialized_tokens"] for r in records))[max(0, int(0.95 * len(records)) - 1)] if records else None,
        "result_too_large": statuses.get("RESULT_TOO_LARGE", 0),
        "sql_errors": sum(statuses.get(s, 0) for s in ("SQL_ERROR", "QUERY_TIMEOUT", "SQL_REJECTED")),
        "api_errors": statuses.get("API_ERROR", 0),
        "empty_results": sum(1 for c in calls if (c.get("result") or {}).get("status") == "OK" and (c.get("result") or {}).get("row_count") == 0),
        "invalid_reference_ids": sum(bool(r["invalid_reference_ids"]) for r in records),
        "invalid_formula_ids": sum(bool(r["invalid_formula_ids"]) for r in records),
        "statuses": dict(statuses),
    }


def query_strategy(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for record in records:
        for call in record.get("calls", []):
            if call.get("interface") == "typed_api":
                op = str(call.get("operation", "other"))
                category = {
                    "get_entities": "local target inspection", "formulas_in_row": "row lookup",
                    "formulas_in_column": "column lookup", "formula_class_members": "formula-class lookup",
                    "references_of": "reference expansion", "dependents_of": "dependency lookup",
                    "text_matches": "text identity lookup", "temporal_at": "temporal filtering",
                    "entities_at_period": "temporal filtering", "translate_formula": "formula template",
                }.get(op, "other")
                counts[category] += 1
            elif call.get("interface") == "sql":
                info = call.get("sql_classification") or {}
                kind = info.get("query_kind", "other")
                counts[{"lookup": "lookup", "join": "join", "aggregation": "aggregation", "recursive": "recursive traversal"}.get(kind, "other")] += 1
                if info.get("broad_scan"):
                    counts["broad scan"] += 1
    return dict(sorted(counts.items()))


def sql_quality(records: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [c for r in records for c in r.get("calls", []) if c.get("interface") == "sql"]
    if not calls:
        return {"sql_calls": 0}
    classifications = [c.get("sql_classification") or {} for c in calls]
    errors = [c for c in calls if (c.get("result") or {}).get("status") in {"SQL_ERROR", "QUERY_TIMEOUT", "SQL_REJECTED"}]
    return {
        "sql_calls": len(calls), "syntax_or_sql_error_rate": round(len(errors) / len(calls), 4),
        "invalid_column_or_table_errors": sum("no such" in str((c.get("result") or {}).get("error", "")).lower() for c in errors),
        "empty_result_rate": round(sum((c.get("result") or {}).get("status") == "OK" and (c.get("result") or {}).get("row_count") == 0 for c in calls) / len(calls), 4),
        "broad_scan_frequency": round(sum(bool(x.get("broad_scan")) for x in classifications) / len(calls), 4),
        "result_too_large_rate": round(sum((c.get("result") or {}).get("status") == "RESULT_TOO_LARGE" for c in calls) / len(calls), 4),
        "mean_joins": round(sum(max(0, len(x.get("tables", [])) - 1) for x in classifications) / len(calls), 2),
        "recursive_cte_calls": sum(x.get("query_kind") == "recursive" for x in classifications),
        "aggregation_calls": sum(x.get("query_kind") == "aggregation" for x in classifications),
    }


def valid_model_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only episodes whose every model request completed successfully."""
    return [r for r in records if r.get("calls") and all(c.get("model_ok") for c in r["calls"])]


def execution_quality(records: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [c for r in records for c in r.get("calls", [])]
    return {
        "records": len(records),
        "valid_complete_episodes": len(valid_model_records(records)),
        "http_failures": sum(not c.get("model_ok", False) for c in calls),
        "credit_failures_402": sum(c.get("status") == 402 for r in records for c in r.get("calls", [])),
        "valid_for_primary_scoring": not any(not c.get("model_ok", False) for c in calls),
    }


def curve(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for q in range(0, MAX_CALLS + 1):
        covered = []
        for r in records:
            # Use the persisted cumulative coverage on each call; q=0 is zero
            # retrieval except targets with no references, which are complete.
            if q == 0:
                c = {"point_recall": 1.0 if r["gold_point_count"] == 0 else 0.0, "range_recall": 1.0 if r["gold_range_count"] == 0 else 0.0, "complete": r["gold_point_count"] == 0 and r["gold_range_count"] == 0}
            else:
                candidates = [x.get("cumulative_coverage") for x in r["calls"] if x.get("q") <= q and x.get("cumulative_coverage")]
                c = candidates[-1] if candidates else {"point_recall": 1.0 if r["gold_point_count"] == 0 else 0.0, "range_recall": 1.0 if r["gold_range_count"] == 0 else 0.0, "complete": r["gold_point_count"] == 0 and r["gold_range_count"] == 0}
            covered.append((r, c))
        eligible = [(r, c) for r, c in covered if r.get("gold_supported_evaluator_only")]
        rows.append({"q": q, "n": len(eligible), "point_recall": round(sum(c["point_recall"] for _, c in eligible) / len(eligible), 4) if eligible else None, "range_recall": round(sum(c["range_recall"] for _, c in eligible) / len(eligible), 4) if eligible else None, "complete_rate": round(sum(c["complete"] for _, c in eligible) / len(eligible), 4) if eligible else None})
    return {"curve": rows}


def report() -> dict[str, Any]:
    freeze_data = load_json(OUT / "freeze.json")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for arm in ARMS:
        path = OUT / f"calls_{arm}.jsonl"
        grouped[arm] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    primary_grouped_all = {arm: [r for r in rows if r.get("primary")] for arm, rows in grouped.items()}
    primary_grouped = {arm: valid_model_records(rows) for arm, rows in primary_grouped_all.items()}
    summaries = {arm: summarize_records(rows) for arm, rows in primary_grouped.items()}
    curves = {arm: curve(rows) for arm, rows in primary_grouped.items()}
    strategies = {arm: query_strategy(rows) for arm, rows in primary_grouped.items()}
    quality = {arm: sql_quality(rows) for arm, rows in primary_grouped.items()}
    execution = {arm: execution_quality(rows) for arm, rows in primary_grouped_all.items()}
    by_edit = {}
    rows_by_target = {r["target_job_id"]: r for r in retrieval_population()}
    for arm, records in primary_grouped.items():
        by_edit[arm] = {}
        for edit in ("BLANK_TO_FORMULA", "VALUE_TO_FORMULA", "FORMULA_TO_FORMULA"):
            by_edit[arm][edit] = summarize_records([r for r in records if rows_by_target.get(r["target_job_id"], {}).get("edit_type") == edit])
    existing = {}
    # Fingerprint labels are evaluator-side and are joined only in the report.
    label_map = {}
    target_lines = OUT.parent / "formula-projection-preflight" / "targets.jsonl"
    if target_lines.exists():
        for line in target_lines.read_text(encoding="utf-8").splitlines():
            target_record = json.loads(line)
            label_map[target_record["target_job_id"]] = target_record.get("fingerprint_existing")
    for arm, records in primary_grouped.items():
        existing[arm] = {}
        for label in ("GOLD_FINGERPRINT_EXISTING", "GOLD_FINGERPRINT_NOVEL"):
            picked = []
            for r in records:
                is_existing = label_map.get(r["target_job_id"]) is True
                if (label == "GOLD_FINGERPRINT_EXISTING") == is_existing:
                    picked.append(r)
            existing[arm][label] = summarize_records(picked)
    static = load_json(OUT.parent / "formula-projection-preflight" / "report.json") if (OUT.parent / "formula-projection-preflight" / "report.json").exists() else None
    known = {}
    for key in KNOWN_CASE_BINDINGS:
        task, obligation, address = key
        target = next((r for r in retrieval_population() if r["task"] == task and r["obligation_id"] == obligation and r["target"]["address"] == address), None)
        if not target:
            continue
        known[f"{task}:{obligation}:{address}"] = {arm: [r for r in grouped[arm] if r["target_job_id"] == target["target_job_id"]] for arm in ARMS}
    static_baseline = (static or {}).get("stage_frontier", {}).get("C7_ALL")
    def complete(arm: str) -> float:
        return float(summaries.get(arm, {}).get("retrieved_evidence_complete_rate") or 0.0)
    a, b, c = complete(ARMS[0]), complete(ARMS[1]), complete(ARMS[2])
    static_complete = float((static_baseline or {}).get("complete_rate") or 0.5882)
    blocked = any(not x["valid_for_primary_scoring"] for x in execution.values())
    if blocked:
        verdict = "EXECUTION_BLOCKED_MODEL_ACCESS"
    elif max(a, b) <= static_complete + 0.05:
        verdict = "QUERYING_WEAK"
    elif b >= 0.85 and b >= static_complete + 0.10:
        verdict = "SQL_STRONG"
    elif a >= b + 0.05:
        verdict = "API_STRONGER"
    elif b >= c + 0.10:
        verdict = "CONTEXT_DOMINANT"
    elif abs(b - c) <= 0.05:
        verdict = "SQL_CONTEXT_INDEPENDENT"
    elif max(a, b) <= static_complete + 0.05:
        verdict = "QUERYING_WEAK"
    else:
        verdict = "CONTEXT_CAPACITY_LIMITED"
    manifest = load_json(OUT / "database_manifest.json") if (OUT / "database_manifest.json").exists() else {}
    result = {"title": "Relational workbook spine retrieval interface experiment", "generated_at": datetime.now(UTC).isoformat(), "freeze": freeze_data, "database_manifest_summary": [{"workbook_id": x.get("workbook_id"), "counts": x.get("counts"), "temporal": x.get("temporal")} for x in manifest.get("workbooks", [])], "static_projection_baseline": static_baseline, "execution": execution, "arms": summaries, "retrieval_curves": curves, "query_strategy": strategies, "sql_quality": quality, "edit_type": by_edit, "fingerprint_strata": existing, "known_cases": known, "comparisons": {"B_minus_A_retrieved_complete": round(b - a, 4), "B_minus_C_retrieved_complete": round(b - c, 4), "B_minus_static_complete": round(b - static_complete, 4)}, "verdict": verdict}
    write(OUT / "report.json", result)
    lines = ["# Relational workbook spine retrieval experiment", "", "No workbook editing and no formula synthesis.", "", "## Arm summaries", ""]
    for arm, summary in summaries.items():
        lines.append(f"- {arm}: n={summary['n']}, point={summary['final_point_recall']}, range={summary['final_range_recall']}, final_complete={summary['final_complete_rate']}, retrieved_complete={summary['retrieved_evidence_complete_rate']}, mean_calls={summary['mean_calls']}, mean_tokens={summary['mean_tokens']}, too_large={summary['result_too_large']}, errors={summary['sql_errors'] + summary['api_errors']}")
    lines += ["", "## Interface comparisons", "", f"- B-A retrieved completeness delta: {result['comparisons']['B_minus_A_retrieved_complete']}", f"- B-C retrieved completeness delta: {result['comparisons']['B_minus_C_retrieved_complete']}", f"- B-static projection completeness delta: {result['comparisons']['B_minus_static_complete']}", f"- Verdict: {result['verdict']}", "", "Execution validity by arm is in `report.json`. HTTP/model-access failures are excluded from primary scoring; no conclusion is drawn from an incomplete ledger.", ""]
    write(OUT / "report.md", "\n".join(lines))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    sub.add_parser("build")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--offset", type=int, default=0)
    run_parser.add_argument("--arms", nargs="*", choices=ARMS, default=list(ARMS))
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--ledger-path", type=Path)
    run_parser.add_argument("--target-id-file", type=Path)
    sub.add_parser("report")
    args = parser.parse_args()
    if args.command == "freeze":
        print(json.dumps(freeze(), indent=2))
    elif args.command == "build":
        freeze(); print(json.dumps(build_all(), indent=2))
    elif args.command == "run":
        run(args.limit, args.offset, tuple(args.arms), args.force, args.ledger_path, args.target_id_file)
    else:
        print(json.dumps(report(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
