#!/usr/bin/env python3
"""Narrow integrated Architecture v1.1 retrieval plus formula synthesis probe.

This is one fresh R1 retrieval episode followed by one GLM formula proposal.
It never edits a workbook, runs the task parser, retries a formula, or uses a
second model.  Gold formulas and retrieval labels remain evaluator-side.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))

import formula_synthesis_probe as eval_tools  # noqa: E402
import hybrid_sql_retrieval_probe as hybrid  # noqa: E402
import relational_retrieval_probe as prior  # noqa: E402
from task_obligation_compile import extract_json_object  # noqa: E402
from workbook_spine_sqlite import ReadOnlySqlite, database_id_inventory  # noqa: E402


MODEL = "z-ai/glm-5.3-flash"
TEMPERATURE = 0.0
REASONING = "medium"
MAX_SQL_CALLS = 8
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/integrated-hybrid-synthesis-probe"
HYBRID_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/hybrid-sql-retrieval-probe"
ARMS = ("R1_INTEGRATED_RETRIEVAL_SYNTHESIS",)

KNOWN_CASES = {
    ("04_05", "O5", "K6"), ("09_05", "O2", "K163"), ("09_05", "O2", "L163"),
    ("14_05", "O2", "D10"), ("20_04", "O1", "H41"), ("14_05", "O5", "J31"),
    ("08_01", "O6", "J46"), ("08_01", "O3", "AF66"), ("08_01", "O3", "AG66"),
    ("17_03", "O6", "K104"), ("15_04", "O1", "Y39"), ("15_04", "O1", "Y40"),
}

SYNTHESIS_TRANSITION = """Retrieval is complete for this attempt. Using the task obligation, exact target, and all workbook evidence available in the current session/working set, produce the formula that should be placed in the target cell.

You may use any workbook entity present in the accumulated working set. Do not invent workbook cells, sheets, labels, or relationships. Existing patterns are evidence, not correctness guarantees. If the evidence is insufficient to justify a formula, abstain.

Return JSON only:
{
  "status": "PROPOSED" | "ABSTAIN",
  "target_id": "...",
  "formula": "=..." | null,
  "used_entity_ids": ["..."],
  "evidence_ids": ["..."]
}

Every used_entity_ids/evidence_ids value must already exist in the accumulated working set or be the exact target cell. Do not include rationale or markdown.
"""

INTEGRATED_RETRIEVAL_SYSTEM = """You are conducting one integrated retrieval-to-formula session for one exact spreadsheet target.

Until the explicit SYNTHESIS TRANSITION appears, retrieve implementation evidence only. Use the complete immutable workbook database through execute_sql(sql). Do not synthesize or edit a formula during retrieval. The deterministic bootstrap and session summaries are harness state; SQL results are automatically accumulated into a monotone working set outside your memory. Preserve ambiguity and never delete candidates.

At retrieval time return exactly one JSON action:
{"action":"execute_sql","sql":"SELECT ..."}
or:
{"action":"final","status":"ENOUGH_EVIDENCE"|"UNRESOLVED"}

After the SYNTHESIS TRANSITION appears, stop issuing SQL and return the requested formula-proposal JSON instead. Resolver preferences are not present in this experiment. Do not invent workbook entities.
"""


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def arm_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in HYBRID_OUT.glob("calls_R1_HYBRID_SQL*.jsonl"):
        for row in read_jsonl(path):
            rows[row["target_job_id"]] = row
    return rows


def target_cell_id(row: dict[str, Any]) -> str:
    match = re.search(r"(cell:s\d+:r\d+:c\d+)$", row["target_job_id"])
    if not match:
        raise ValueError(row["target_job_id"])
    return match.group(1)


def known(row: dict[str, Any]) -> bool:
    return (row["task"], row["obligation_id"], row["target"]["address"]) in KNOWN_CASES


def pick_diverse(rows: list[dict[str, Any]], n: int, label: str) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda x: (not known(x), x["task"], x.get("edit_type", ""), x["target_job_id"]))
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        groups[(row["task"], row.get("edit_type") or "UNKNOWN")].append(row)
    keys = sorted(groups)
    selected: list[dict[str, Any]] = []
    # Known diagnostics are mandatory where they fit, then round-robin task /
    # edit-type groups to avoid a single workbook dominating the stratum.
    for row in ordered:
        if known(row) and len(selected) < n:
            selected.append(row)
    while len(selected) < n:
        progress = False
        for key in keys:
            while groups[key] and groups[key][0] in selected:
                groups[key].pop(0)
            if groups[key] and len(selected) < n:
                selected.append(groups[key].pop(0))
                progress = True
        if not progress:
            break
    selected = sorted({r["target_job_id"]: r for r in selected}.values(), key=lambda x: x["target_job_id"])
    for row in selected:
        row["synthesis_selection_reason"] = label + ("+KNOWN_CASE" if known(row) else "+TASK_EDIT_DIVERSITY")
    return selected


def freeze_population() -> dict[str, Any]:
    population = json.loads((HYBRID_OUT / "narrow_population.json").read_text(encoding="utf-8"))["rows"]
    retrieval = arm_rows()
    supported = [row for row in population if row.get("reference_support") == "SUPPORTED" and row["target_job_id"] in retrieval]
    groups = {
        "G1_RETRIEVAL_COMPLETE_EXISTING": [r for r in supported if retrieval[r["target_job_id"]]["retrieved_evidence_coverage"]["complete"] and r.get("fingerprint_existing") is True],
        "G2_RETRIEVAL_COMPLETE_NOVEL": [r for r in supported if retrieval[r["target_job_id"]]["retrieved_evidence_coverage"]["complete"] and r.get("fingerprint_existing") is False],
        "G3_RETRIEVAL_INCOMPLETE_EXISTING": [r for r in supported if not retrieval[r["target_job_id"]]["retrieved_evidence_coverage"]["complete"] and r.get("fingerprint_existing") is True],
        "G4_RETRIEVAL_INCOMPLETE_NOVEL": [r for r in supported if not retrieval[r["target_job_id"]]["retrieved_evidence_coverage"]["complete"] and r.get("fingerprint_existing") is False],
    }
    targets = {"G1_RETRIEVAL_COMPLETE_EXISTING": 9, "G2_RETRIEVAL_COMPLETE_NOVEL": 9, "G3_RETRIEVAL_INCOMPLETE_EXISTING": 9, "G4_RETRIEVAL_INCOMPLETE_NOVEL": 9}
    selected: list[dict[str, Any]] = []
    for label, candidates in groups.items():
        selected.extend(pick_diverse(candidates, min(targets[label], len(candidates)), label))
    selected = sorted({row["target_job_id"]: row for row in selected}.values(), key=lambda x: x["target_job_id"])
    rows = []
    for row in selected:
        r = retrieval[row["target_job_id"]]
        group = next(label for label, candidates in groups.items() if row["target_job_id"] in {x["target_job_id"] for x in candidates})
        rows.append({
            "target_job_id": row["target_job_id"], "task": row["task"], "family": row["family"], "split": row["split"],
            "obligation_id": row["obligation_id"], "obligation": row["obligation"], "target": row["target"], "edit_type": row["edit_type"],
            "fingerprint_existing": row["fingerprint_existing"], "retrieval_group": group,
            "retrieval_complete_q8": bool(r["retrieved_evidence_coverage"]["complete"]),
            "retrieval_q0_complete": bool(r["bootstrap_coverage"]["complete"]),
            "retrieval_calls": r["calls_used"], "selection_reason": row.get("synthesis_selection_reason"),
            "gold_formula": row["gold_formula"], "gold_fingerprint": row.get("gold_fingerprint"),
            "primary_narrow_population": row.get("primary"), "narrow_selection_reasons": row.get("selection_reasons"),
        })
    payload = {
        "generated_at": datetime.now(UTC).isoformat(), "source": str(HYBRID_OUT / "narrow_population.json"),
        "retrieval_source": "fresh R1 run remains evaluator baseline; integrated run performs fresh retrieval calls",
        "requested_per_group": targets, "group_counts": {k: sum(row["retrieval_group"] == k for row in rows) for k in groups},
        "known_cases_included": [row["target_job_id"] for row in rows if known(row)],
        "n": len(rows), "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "synthesis_population.json", payload)
    return payload


def freeze() -> dict[str, Any]:
    pop = freeze_population()
    strong = prior.sql_strong_context("", {})
    system = strong + "\n" + INTEGRATED_RETRIEVAL_SYSTEM
    freeze_data = {
        "generated_at": datetime.now(UTC).isoformat(), "model": MODEL, "display_name": "GLM 5.3 Flash", "temperature": TEMPERATURE, "reasoning": REASONING,
        "max_sql_calls": MAX_SQL_CALLS, "retrieval_protocol": "Architecture v1.1 R1 frozen hybrid SQL", "bootstrap": ["M0", "M2", "M4"],
        "population_n": pop["n"], "group_counts": pop["group_counts"], "gold_in_model_context": False, "formula_synthesis": True,
        "workbook_edits": False, "typed_api": False, "bare_schema_sql": False, "task_parser": False, "repair_loops": False,
        "system_sha256": hashlib.sha256(system.encode()).hexdigest(), "transition_sha256": hashlib.sha256(SYNTHESIS_TRANSITION.encode()).hexdigest(),
        "model_guard": "exact z-ai/glm-5.3-flash only; reject openai/* and GPT*; no fallback",
        "scorer_equivalent": "not run unless an existing safe single-cell path is available; no original workbook edits",
    }
    write(OUT / "freeze.json", freeze_data)
    write(OUT / "retrieval_system.txt", system)
    write(OUT / "synthesis_transition.txt", SYNTHESIS_TRANSITION)
    write(OUT / "synthesis_prompt.txt", INTEGRATED_RETRIEVAL_SYSTEM + "\n\n" + SYNTHESIS_TRANSITION)
    return freeze_data


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_in(values: list[str]) -> str:
    return ",".join(sql_quote(v) for v in sorted(set(values))) or "NULL"


def query(executor: ReadOnlySqlite, sql: str) -> list[dict[str, Any]]:
    result = executor.execute(sql)
    return result.get("rows", []) if result.get("status") == "OK" else [{"status": result.get("status"), "error": result.get("error")}]


def compact_table(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    """Columnar JSON; every selected field is retained, keys are not repeated."""
    return {"columns": columns, "rows": [[row.get(column) for column in columns] for row in rows]}


def materialize_working_set(task: str, working: set[str]) -> dict[str, Any]:
    """Losslessly expose retrieved entities and direct relations for synthesis."""
    executor = ReadOnlySqlite(prior.db_path(task), max_rows=prior.RESULT_ROW_LIMIT, max_bytes=prior.RESULT_BYTE_LIMIT)
    groups: dict[str, list[str]] = defaultdict(list)
    for value in sorted(working):
        groups[value.split(":", 1)[0]].append(value)
    out: dict[str, Any] = {"entity_ids": sorted(working), "entities": {}, "relations": {}}
    if groups["cell"]:
        rows = query(executor, f"SELECT cell_id,kind,raw_value,display_value FROM cells WHERE cell_id IN ({sql_in(groups['cell'])}) ORDER BY cell_id")
        out["entities"]["cells"] = compact_table(rows, ["cell_id", "kind", "raw_value", "display_value"])
    if groups["formula"]:
        rows = query(executor, f"SELECT formula_id,cell_id,formula_text,fingerprint_id,opaque FROM formulas WHERE formula_id IN ({sql_in(groups['formula'])}) ORDER BY formula_id")
        out["entities"]["formulas"] = compact_table(rows, ["formula_id", "cell_id", "formula_text", "fingerprint_id", "opaque"])
        rows = query(executor, f"SELECT formula_id,referenced_cell_id,ref_slot,row_delta,col_delta,row_absolute,col_absolute,cross_sheet FROM point_references WHERE formula_id IN ({sql_in(groups['formula'])}) ORDER BY formula_id,ref_slot")
        out["relations"]["point_references"] = compact_table(rows, ["formula_id", "referenced_cell_id", "ref_slot", "row_delta", "col_delta", "row_absolute", "col_absolute", "cross_sheet"])
        rows = query(executor, f"SELECT rr.formula_id,rr.range_id,rr.ref_slot,rr.cross_sheet,r.sheet_id,r.r1,r.c1,r.r2,r.c2 FROM range_references rr JOIN ranges r ON r.range_id=rr.range_id WHERE rr.formula_id IN ({sql_in(groups['formula'])}) ORDER BY rr.formula_id,rr.ref_slot")
        out["relations"]["range_references"] = compact_table(rows, ["formula_id", "range_id", "ref_slot", "cross_sheet", "sheet_id", "r1", "c1", "r2", "c2"])
    if groups["range"]:
        rows = query(executor, f"SELECT range_id,sheet_id,r1,c1,r2,c2 FROM ranges WHERE range_id IN ({sql_in(groups['range'])}) ORDER BY range_id")
        out["entities"]["ranges"] = compact_table(rows, ["range_id", "sheet_id", "r1", "c1", "r2", "c2"])
    if groups["formula_class"]:
        rows = query(executor, f"SELECT fingerprint_id,canonical_fingerprint FROM formula_classes WHERE fingerprint_id IN ({sql_in(groups['formula_class'])}) ORDER BY fingerprint_id")
        out["entities"]["formula_classes"] = compact_table(rows, ["fingerprint_id", "canonical_fingerprint"])
        rows = query(executor, f"SELECT fingerprint_id,formula_id FROM formula_class_members WHERE fingerprint_id IN ({sql_in(groups['formula_class'])}) ORDER BY fingerprint_id,formula_id")
        out["relations"]["formula_class_members"] = compact_table(rows, ["fingerprint_id", "formula_id"])
    if groups["text"]:
        rows = query(executor, f"SELECT anchor_id,cell_id,exact_text,normalized_text,row_id,col_id FROM text_anchors WHERE anchor_id IN ({sql_in(groups['text'])}) ORDER BY anchor_id")
        out["entities"]["text_anchors"] = compact_table(rows, ["anchor_id", "cell_id", "exact_text", "normalized_text", "row_id", "col_id"])
    if groups["sheet"]:
        rows = query(executor, f"SELECT sheet_id,name,normalized_name,visibility,used_r1,used_c1,used_r2,used_c2 FROM sheets WHERE sheet_id IN ({sql_in(groups['sheet'])}) ORDER BY sheet_index")
        out["entities"]["sheets"] = compact_table(rows, ["sheet_id", "name", "normalized_name", "visibility", "used_r1", "used_c1", "used_r2", "used_c2"])
    if groups["row"]:
        rows = query(executor, f"SELECT row_id FROM rows WHERE row_id IN ({sql_in(groups['row'])}) ORDER BY row_id")
        out["entities"]["rows"] = compact_table(rows, ["row_id"])
    if groups["col"]:
        rows = query(executor, f"SELECT col_id,sheet_id,col_idx,n_text,n_formula,n_value,n_blank,periods_json FROM columns WHERE col_id IN ({sql_in(groups['col'])}) ORDER BY col_id")
        out["entities"]["columns"] = compact_table(rows, ["col_id", "sheet_id", "col_idx", "n_text", "n_formula", "n_value", "n_blank", "periods_json"])
    if groups["tcoord"] or groups["temporal"]:
        ids = groups["tcoord"] + groups["temporal"]
        rows = query(executor, f"SELECT temporal_id,sheet_id,axis,axis_index,year,month,quarter,marker,derivation_kind,cell_id,row_id,col_id,period_key,header_text FROM temporal_coordinates WHERE temporal_id IN ({sql_in(ids)}) ORDER BY temporal_id")
        out["entities"]["temporal_coordinates"] = compact_table(rows, ["temporal_id", "sheet_id", "axis", "axis_index", "year", "month", "quarter", "marker", "derivation_kind", "cell_id", "row_id", "col_id", "period_key", "header_text"])
    out["counts"] = {key: len(value) for key, value in out["entities"].items()}
    out["relation_counts"] = {key: len(value) for key, value in out["relations"].items()}
    return out


def integrated_summary(row: dict[str, Any], working: set[str], history: list[dict[str, Any]], latest: dict[str, Any] | None) -> str:
    counts = Counter(value.split(":", 1)[0] for value in working)
    payload = {"SESSION_STATE": {"target": row["target"], "obligation": row["obligation"], "working_set_counts": dict(sorted(counts.items())), "working_set_entity_ids": sorted(working), "query_history": history}}
    if latest is not None:
        payload["LATEST_SQL_RESULT"] = latest
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def call_synthesis(key: str, system: str, message: str) -> dict[str, Any]:
    if MODEL != "z-ai/glm-5.3-flash" or MODEL.startswith("openai/") or MODEL.lower().startswith("gpt"):
        raise RuntimeError(f"model guard rejected {MODEL}")
    body = {"model": MODEL, "max_tokens": 1800, "temperature": TEMPERATURE, "reasoning": {"effort": REASONING}, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": message}]}
    import urllib.request
    request = urllib.request.Request(prior.OPENROUTER_URL, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "librecalc-integrated-synthesis"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode())
        model_returned = payload.get("model")
        if model_returned and model_returned != MODEL:
            return {"http_ok": False, "failure_class": "MODEL_ACCESS_FAILURE", "detail": f"unexpected returned model: {model_returned}"}
        choices = payload.get("choices") or []
        text = (choices[0].get("message") or {}).get("content", "") if choices else ""
        return {"http_ok": True, "text": text, "usage": payload.get("usage"), "payload_model": model_returned}
    except Exception as exc:
        import urllib.error
        if isinstance(exc, urllib.error.HTTPError):
            detail = exc.read().decode(errors="replace")[:1000]
        else:
            detail = str(exc)[:1000]
        return {"http_ok": False, "failure_class": "MODEL_ACCESS_FAILURE", "detail": f"{type(exc).__name__}: {detail}"}


def run_episode(row: dict[str, Any], key: str, counts: dict[str, Any]) -> dict[str, Any]:
    retrieval_system = prior.sql_strong_context("", counts.get(row["task"], {})) + "\n" + INTEGRATED_RETRIEVAL_SYSTEM
    boot = json.loads((HYBRID_OUT / "narrow_population.json").read_text(encoding="utf-8"))["rows"]
    boot = next(x["bootstrap"] for x in boot if x["target_job_id"] == row["target_job_id"])
    target_row = {"target": row["target"], "obligation": row["obligation"], "target_job_id": row["target_job_id"]}
    initial = hybrid.model_bootstrap_payload(boot)
    working = hybrid.canonicalize_ids(set(boot.get("bootstrap_entity_ids", [])))
    working.add(target_cell_id(row))
    history: list[dict[str, Any]] = []
    latest = None
    retrieval_calls = []
    retrieval_input_tokens = 0
    retrieval_output_tokens = 0
    session_summary_tokens = 0
    materialized_result_tokens = 0
    started = time.perf_counter()
    messages = [{"role": "user", "content": json.dumps(initial, ensure_ascii=False, separators=(",", ":"))}]
    for q in range(1, MAX_SQL_CALLS + 1):
        response = hybrid.safe_call(key, retrieval_system, messages)
        if not response.get("http_ok"):
            retrieval_calls.append({"q": q, "model_ok": False, **response})
            return {"target_job_id": row["target_job_id"], "model": MODEL, "status": "MODEL_ACCESS_FAILURE", "failure_class": "MODEL_ACCESS_FAILURE", "retrieval_calls": retrieval_calls, "synthesis": None}
        if response.get("payload_model") and response["payload_model"] != MODEL:
            retrieval_calls.append({"q": q, "model_ok": False, "failure_class": "MODEL_ACCESS_FAILURE", "detail": f"unexpected returned model: {response['payload_model']}"})
            return {"target_job_id": row["target_job_id"], "model": MODEL, "status": "MODEL_ACCESS_FAILURE", "failure_class": "MODEL_ACCESS_FAILURE", "retrieval_calls": retrieval_calls, "synthesis": None}
        text = response.get("text") or ""
        usage = response.get("usage") or {}
        retrieval_input_tokens += int(usage.get("prompt_tokens") or 0)
        retrieval_output_tokens += int(usage.get("completion_tokens") or 0)
        action = prior.extract_action(text)
        rec = {"q": q, "model_ok": True, "raw_text": text[:12000], "usage": usage, "action": action}
        if not isinstance(action, dict):
            rec["result"] = {"status": "ACTION_ERROR", "error": "Expected retrieval action JSON"}
            retrieval_calls.append(rec)
            messages = [{"role": "user", "content": integrated_summary(target_row, working, history, rec["result"])}]
            session_summary_tokens += hybrid.estimate_tokens(messages[0]["content"])
            continue
        if action.get("action") == "final":
            rec["final"] = True
            retrieval_calls.append(rec)
            break
        sql = action.get("sql") if action.get("action") == "execute_sql" else ""
        executor = ReadOnlySqlite(prior.db_path(row["task"]), max_rows=prior.RESULT_ROW_LIMIT, max_bytes=prior.RESULT_BYTE_LIMIT)
        result = executor.execute(sql) if sql else {"status": "ACTION_ERROR", "error": "Expected execute_sql action"}
        result_tokens = hybrid.estimate_tokens(result)
        if result.get("status") == "OK" and materialized_result_tokens + result_tokens > prior.EPISODE_TOKEN_LIMIT:
            result = {"status": "RESULT_TOO_LARGE", "row_count": result.get("row_count"), "estimated_result_tokens": result_tokens, "configured_episode_token_limit": prior.EPISODE_TOKEN_LIMIT}
        elif result.get("status") == "OK":
            materialized_result_tokens += result_tokens
        ids = hybrid.result_ids(result)
        added = ids - working
        working |= ids
        rec.update({"interface": "sql", "sql": sql[:12000], "sql_classification": prior.classify_sql(sql), "result": result, "result_id_count": len(ids), "new_working_set_ids": sorted(added)})
        retrieval_calls.append(rec)
        history.append({"q": q, "status": result.get("status"), "row_count": result.get("row_count"), "new_ids": len(added), "sql_kind": prior.classify_sql(sql).get("query_kind")})
        latest = result
        messages = [{"role": "user", "content": integrated_summary(target_row, working, history, latest)}]
        session_summary_tokens += hybrid.estimate_tokens(messages[0]["content"])

    evidence = materialize_working_set(row["task"], working)
    transition = {"SYNTHESIS_TRANSITION": SYNTHESIS_TRANSITION, "TASK": row["obligation"], "TARGET": {"id": target_cell_id(row), **row["target"]}, "WORKING_SET_COUNTS": evidence["counts"], "WORKING_SET_RELATION_COUNTS": evidence["relation_counts"], "WORKING_SET_ENTITY_IDS": sorted(working), "WORKING_SET_EVIDENCE": evidence}
    synthesis_message = json.dumps(transition, ensure_ascii=False, separators=(",", ":"))
    synth_response = call_synthesis(key, retrieval_system, synthesis_message)
    synth = {"input_tokens_estimate": hybrid.estimate_tokens(synthesis_message), **synth_response}
    if synth_response.get("http_ok"):
        synth["parsed"] = extract_json_object(synth_response.get("text", ""))
        synth["output_tokens"] = int((synth_response.get("usage") or {}).get("completion_tokens") or 0)
        synth["input_tokens"] = int((synth_response.get("usage") or {}).get("prompt_tokens") or 0)
    else:
        synth["parsed"] = None
    return {
        "target_job_id": row["target_job_id"], "task": row["task"], "family": row["family"], "obligation_id": row["obligation_id"], "target": row["target"], "edit_type": row["edit_type"], "model": MODEL, "model_guard": "exact", "status": "MODEL_ACCESS_FAILURE" if not synth.get("http_ok") else "PROPOSAL_RETURNED", "retrieval_calls": retrieval_calls, "synthesis": synth,
        "working_set_ids": sorted(working), "working_set_counts": dict(Counter(x.split(":", 1)[0] for x in working)), "working_set_size": len(working), "working_set_evidence": evidence, "bootstrap_tokens": boot.get("bootstrap_tokens"), "bootstrap_entity_count": len(boot.get("bootstrap_entity_ids", [])), "materialized_result_tokens": materialized_result_tokens, "session_summary_tokens": session_summary_tokens, "retrieval_input_tokens": retrieval_input_tokens, "retrieval_output_tokens": retrieval_output_tokens, "synthesis_transition_input_estimate": hybrid.estimate_tokens(synthesis_message), "total_input_tokens": retrieval_input_tokens + int(synth.get("input_tokens") or 0), "total_output_tokens": retrieval_output_tokens + int(synth.get("output_tokens") or 0), "elapsed_s": round(time.perf_counter() - started, 3),
    }


def load_dotenv() -> None:
    prior.load_dotenv()


def run(worker_index: int = 0, worker_count: int = 1) -> None:
    if MODEL != "z-ai/glm-5.3-flash":
        raise SystemExit("hard model guard failure")
    pop = json.loads((OUT / "synthesis_population.json").read_text(encoding="utf-8"))["rows"]
    manifest = json.loads((prior.OUT / "database_manifest.json").read_text(encoding="utf-8"))
    counts = {str(x.get("workbook_id", "")).removeprefix("wb:"): x.get("counts") or {} for x in manifest.get("workbooks", [])}
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required")
    path = OUT / f"episodes.worker{worker_index:02d}.jsonl"
    done = {r["target_job_id"] for r in read_jsonl(path) if r.get("status") != "MODEL_ACCESS_FAILURE"}
    assigned = [r for i, r in enumerate(pop) if i % worker_count == worker_index and r["target_job_id"] not in done]
    print(f"RUN integrated worker={worker_index}/{worker_count} remaining={len(assigned)}", flush=True)
    with path.open("a", encoding="utf-8") as handle:
        for i, row in enumerate(assigned, 1):
            result = run_episode(row, key, counts)
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"CALL integrated worker={worker_index} {i}/{len(assigned)} {row['target_job_id']} status={result['status']}", flush=True)


def canonical_formula(value: str | None) -> str | None:
    return eval_tools._canonical_formula(value)


def formula_ref_sets(row: dict[str, Any], formula: str | None) -> tuple[set[tuple[str, str, str | None]], set[tuple[str, str, str | None]], dict[str, Any]]:
    refs = eval_tools._ref_records(formula, row["target"]["sheet"], row["target"]["row"], row["target"]["col"])
    points = {(x["sheet"], x["start"], x.get("end")) for x in refs.get("points", [])}
    ranges = {(x["sheet"], x["start"], x.get("end")) for x in refs.get("ranges", [])}
    return points, ranges, refs


def ref_ids(row: dict[str, Any], refs: dict[str, Any], spine: dict[str, Any]) -> set[str]:
    out = set()
    for ref in refs.get("points", []) + refs.get("ranges", []):
        sid = (spine.get("title_to_index") or {}).get(ref["sheet"])
        if sid is None:
            continue
        first = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)", ref["start"])
        if not first:
            continue
        col = 0
        for char in first.group(1).upper():
            col = col * 26 + ord(char) - 64
        row_num = int(first.group(2))
        if ref.get("is_range"):
            last = re.fullmatch(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)", ref.get("end") or ref["start"])
            if last:
                c2 = 0
                for char in last.group(1).upper():
                    c2 = c2 * 26 + ord(char) - 64
                r2 = int(last.group(2))
                out.add(f"range:s{int(sid):02d}:r{min(row_num,r2)}:c{min(col,c2)}:r{max(row_num,r2)}:c{max(col,c2)}")
        else:
            out.add(f"cell:s{int(sid):02d}:r{row_num}:c{col}")
    return out


def score_rows() -> dict[str, Any]:
    population = {r["target_job_id"]: r for r in json.loads((OUT / "synthesis_population.json").read_text(encoding="utf-8"))["rows"]}
    records = {}
    for path in OUT.glob("episodes.worker*.jsonl"):
        for row in read_jsonl(path):
            records[row["target_job_id"]] = row
    scored = []
    view_cache: dict[str, tuple[Any, Any]] = {}
    previous_task = None
    ordered_population = sorted(population.items(), key=lambda item: (item[1]["task"], item[0]))
    for tid, row in ordered_population:
        episode = records.get(tid)
        if not episode:
            continue
        if previous_task is not None and row["task"] != previous_task:
            view_cache.clear()
            view = None
            scc = None
            gc.collect()
        previous_task = row["task"]
        parsed = ((episode.get("synthesis") or {}).get("parsed"))
        formula = parsed.get("formula") if isinstance(parsed, dict) and parsed.get("status") == "PROPOSED" else None
        working = set(episode.get("working_set_ids", []))
        spine = eval_tools._load_spine(row["task"])
        gold_points, gold_ranges, gold_supported = prior.evaluator_refs({**row, "target": row["target"]})
        gold_refs = {"points": set(gold_points), "ranges": set(gold_ranges)}
        pred_points, pred_ranges, pred_ref_obj = formula_ref_sets(row, formula)
        pred_ref_ids = ref_ids(row, pred_ref_obj, spine)
        gold_ref_ids = gold_points | gold_ranges
        in_working = {x for x in pred_ref_ids if x in working}
        inventory = database_id_inventory(prior.db_path(row["task"]))
        in_spine_not_working = {x for x in pred_ref_ids if x in inventory and x not in working}
        invalid_workbook = {x for x in pred_ref_ids if x not in inventory}
        invalid_entity_ids = []
        if isinstance(parsed, dict):
            allowed = working | {target_cell_id(row)}
            for key in ("used_entity_ids", "evidence_ids"):
                invalid_entity_ids.extend(x for x in (parsed.get(key) or []) if x not in allowed)
            if parsed.get("target_id") is not None and parsed.get("target_id") not in {target_cell_id(row), row["target_job_id"]}:
                invalid_entity_ids.append(str(parsed.get("target_id")))
        exact = bool(formula and canonical_formula(formula) == canonical_formula(row["gold_formula"]))
        pred_fp = None
        validation = {"hard_reject": False, "parser_ok": False, "cycle": False, "hard_verifier": None}
        if formula:
            try:
                fp = eval_tools.relative_fingerprint(formula, row["target"]["col"], row["target"]["row"], sheet=row["target"]["sheet"])
                pred_fp = None if fp.opaque else fp.eq_id
            except Exception:
                pred_fp = None
            if row["task"] not in view_cache:
                grids = eval_tools.load_grids(eval_tools._input_path(row["task"]))
                from formula_dependency_selection import build_graph_from_grids
                view = eval_tools.build_view(build_graph_from_grids(grids))
                view_cache[row["task"]] = (view, eval_tools.scc_stats(view))
            validation = eval_tools._validate_formula(row, formula, {}, spine, *view_cache[row["task"]])
        fingerprint = bool(pred_fp and row.get("gold_fingerprint") and pred_fp == row["gold_fingerprint"])
        all_gold = gold_ref_ids
        all_pred = pred_ref_ids
        recall = len(all_gold & all_pred) / len(all_gold) if all_gold else 1.0
        extra = len(all_pred - all_gold) / len(all_pred) if all_pred else 0.0
        tags: list[str] = []
        status = parsed.get("status") if isinstance(parsed, dict) else "INVALID_OUTPUT"
        if status == "ABSTAIN" or not formula:
            tags.append("ABSTAIN")
        elif invalid_entity_ids:
            tags.append("INVALID_ENTITY_REFERENCE")
        elif not validation.get("parser_ok") or validation.get("invalid_sheet") or validation.get("invalid_address") or validation.get("unsupported_external"):
            tags.append("INVALID_FORMULA")
        if validation.get("hard_reject"):
            tags.append("HARD_REJECT")
        if formula and not exact and not fingerprint:
            if pred_ref_ids != gold_ref_ids:
                tags.append("WRONG_SOURCE")
            if pred_ranges != gold_ranges:
                tags.append("WRONG_RANGE_EXTENT")
            if eval_tools._operator_structure(formula, (row["target"]["sheet"], row["target"]["row"], row["target"]["col"])) != eval_tools._operator_structure(row["gold_formula"], (row["target"]["sheet"], row["target"]["row"], row["target"]["col"])):
                tags.append("WRONG_OPERATOR")
            if [x.get("abs_mask") for x in pred_ref_obj.get("slots", [])] != [x.get("abs_mask") for x in eval_tools._ref_records(row["gold_formula"], row["target"]["sheet"], row["target"]["row"], row["target"]["col"]).get("slots", [])]:
                tags.append("WRONG_ABSOLUTE_RELATIVE")
            if not tags:
                tags.append("OTHER")
        scored.append({
            "target_job_id": tid, "task": row["task"], "obligation_id": row["obligation_id"], "target": row["target"], "retrieval_group": row["retrieval_group"], "retrieval_complete_q8": row["retrieval_complete_q8"], "retrieval_q0_complete": row["retrieval_q0_complete"], "fingerprint_existing": row["fingerprint_existing"], "edit_type": row["edit_type"], "formula_status": status, "formula": formula, "gold_formula": row["gold_formula"], "exact_formula_match": exact, "gold_fingerprint_match": fingerprint, "formula_correct": exact or fingerprint, "gold_reference_recall": round(recall, 4), "extra_reference_rate": round(extra, 4), "reference_in_working_set": sorted(in_working), "reference_in_spine_not_working_set": sorted(in_spine_not_working), "invalid_workbook_references": sorted(invalid_workbook), "invalid_entity_ids": sorted(set(invalid_entity_ids)), "validation": validation, "hard_verifier_result": "HARD_REJECT" if validation.get("hard_reject") else "HARD_ACCEPT", "failure_tags": sorted(set(tags)), "used_entity_ids": parsed.get("used_entity_ids", []) if isinstance(parsed, dict) else [], "evidence_ids": parsed.get("evidence_ids", []) if isinstance(parsed, dict) else [], "bootstrap_complete": row["retrieval_q0_complete"], "sql_completed": (not row["retrieval_q0_complete"]) and row["retrieval_complete_q8"], "still_incomplete": not row["retrieval_complete_q8"], "gold_supported": gold_supported, "scorer_equivalent": None, "scorer_note": "Not run: no existing safe single-cell scorer path was invoked in this retrieval/synthesis-only probe."})
    payload = {"generated_at": datetime.now(UTC).isoformat(), "n": len(scored), "rows": scored}
    write(OUT / "scored.json", payload)
    return payload


def repair_reference_scoring() -> dict[str, Any]:
    """Repair only evaluator ID normalization in an already verifier-scored ledger."""
    payload = json.loads((OUT / "scored.json").read_text(encoding="utf-8"))
    population = {r["target_job_id"]: r for r in json.loads((OUT / "synthesis_population.json").read_text(encoding="utf-8"))["rows"]}
    episodes = {}
    for path in OUT.glob("episodes.worker*.jsonl"):
        for row in read_jsonl(path):
            episodes[row["target_job_id"]] = row
    for scored in payload["rows"]:
        row = population[scored["target_job_id"]]
        formula = scored.get("formula")
        spine = eval_tools._load_spine(row["task"])
        gold_points, gold_ranges, _ = prior.evaluator_refs({**row, "target": row["target"]})
        _, _, pred_obj = formula_ref_sets(row, formula)
        pred_ids = ref_ids(row, pred_obj, spine)
        gold_ids = gold_points | gold_ranges
        all_pred = pred_ids
        scored["gold_reference_recall"] = round(len(gold_ids & all_pred) / len(gold_ids), 4) if gold_ids else 1.0
        scored["extra_reference_rate"] = round(len(all_pred - gold_ids) / len(all_pred), 4) if all_pred else 0.0
        working = set((episodes.get(row["target_job_id"]) or {}).get("working_set_ids", []))
        scored["reference_in_working_set"] = sorted(pred_ids & working)
        inventory = database_id_inventory(prior.db_path(row["task"]))
        scored["reference_in_spine_not_working_set"] = sorted({x for x in pred_ids if x in inventory and x not in working})
        scored["invalid_workbook_references"] = sorted({x for x in pred_ids if x not in inventory})
        tags = [x for x in scored.get("failure_tags", []) if x not in {"WRONG_SOURCE", "WRONG_RANGE_EXTENT", "ABSTAIN", "INVALID_OUTPUT"}]
        if scored.get("formula_status") not in {"PROPOSED", "ABSTAIN"}:
            tags.append("INVALID_OUTPUT")
        elif scored.get("formula_status") == "ABSTAIN" or not formula:
            tags.append("ABSTAIN")
        if formula and not scored.get("formula_correct") and pred_ids != gold_ids:
            tags.append("WRONG_SOURCE")
        scored["failure_tags"] = sorted(set(tags))
    write(OUT / "scored.json", payload)
    return payload


def rate(rows: list[dict[str, Any]], key: str) -> float | None:
    return sum(bool(row.get(key)) for row in rows) / len(rows) if rows else None


def report() -> dict[str, Any]:
    scored = json.loads((OUT / "scored.json").read_text(encoding="utf-8"))["rows"]
    def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {"n": len(rows), "formula_correct": rate(rows, "formula_correct"), "exact": rate(rows, "exact_formula_match"), "fingerprint": rate(rows, "gold_fingerprint_match"), "abstain": sum("ABSTAIN" in x["failure_tags"] for x in rows) / len(rows) if rows else None, "invalid_entity_reference": sum("INVALID_ENTITY_REFERENCE" in x["failure_tags"] for x in rows) / len(rows) if rows else None, "hard_reject": sum(x["hard_verifier_result"] == "HARD_REJECT" for x in rows) / len(rows) if rows else None, "mean_gold_reference_recall": statistics.mean([x["gold_reference_recall"] for x in rows]) if rows else None}
    groups = {}
    for group in sorted({x["retrieval_group"] for x in scored}):
        groups[group] = summary([x for x in scored if x["retrieval_group"] == group])
    by_retrieval = {k: summary([x for x in scored if x["retrieval_complete_q8"] is v]) for k, v in [("RETRIEVAL_COMPLETE", True), ("RETRIEVAL_INCOMPLETE", False)]}
    by_fp = {k: summary([x for x in scored if x["fingerprint_existing"] is v]) for k, v in [("EXISTING", True), ("NOVEL", False)]}
    by_source = {k: summary([x for x in scored if x["bootstrap_complete"] and not x["sql_completed"] and not x["still_incomplete"]]) for k in ["BOOTSTRAP_COMPLETE"]}
    by_source["SQL_COMPLETED"] = summary([x for x in scored if x["sql_completed"]])
    by_source["STILL_INCOMPLETE"] = summary([x for x in scored if x["still_incomplete"]])
    failure = Counter(tag for row in scored for tag in row["failure_tags"])
    episodes = []
    for path in OUT.glob("episodes.worker*.jsonl"):
        episodes.extend(read_jsonl(path))
    input_rows = [x for x in episodes if x.get("status") != "MODEL_ACCESS_FAILURE"]
    token = {"n": len(input_rows), "mean_bootstrap": statistics.mean([x.get("bootstrap_tokens") or 0 for x in input_rows]) if input_rows else None, "mean_sql_result": statistics.mean([x.get("materialized_result_tokens") or 0 for x in input_rows]) if input_rows else None, "mean_session_summary": statistics.mean([x.get("session_summary_tokens") or 0 for x in input_rows]) if input_rows else None, "mean_retrieval_input": statistics.mean([x.get("retrieval_input_tokens") or 0 for x in input_rows]) if input_rows else None, "mean_synthesis_input": statistics.mean([((x.get("synthesis") or {}).get("input_tokens") or 0) for x in input_rows]) if input_rows else None, "mean_total_input": statistics.mean([x.get("total_input_tokens") or 0 for x in input_rows]) if input_rows else None, "mean_total_output": statistics.mean([x.get("total_output_tokens") or 0 for x in input_rows]) if input_rows else None}
    payload = {"generated_at": datetime.now(UTC).isoformat(), "freeze": json.loads((OUT / "freeze.json").read_text(encoding="utf-8")), "n": len(scored), "overall": summary(scored), "by_group": groups, "by_retrieval": by_retrieval, "by_fingerprint": by_fp, "by_evidence_source": by_source, "failure_taxonomy": dict(failure), "token_accounting": token, "model_access_failures": sum(x.get("status") == "MODEL_ACCESS_FAILURE" for x in episodes)}
    write(OUT / "report.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--worker-index", type=int, default=0)
    run_parser.add_argument("--worker-count", type=int, default=1)
    sub.add_parser("score")
    sub.add_parser("repair-score")
    sub.add_parser("report")
    args = parser.parse_args()
    if args.command == "freeze":
        print(json.dumps(freeze(), indent=2))
    elif args.command == "run":
        run(args.worker_index, args.worker_count)
    elif args.command == "score":
        print(json.dumps(score_rows(), indent=2))
    elif args.command == "repair-score":
        print(json.dumps(repair_reference_scoring(), indent=2))
    else:
        print(json.dumps(report(), indent=2))


if __name__ == "__main__":
    main()
