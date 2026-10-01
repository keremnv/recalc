#!/usr/bin/env python3
"""Small raw-task to scored-workbook Architecture v1.2 composition probe.

This file is intentionally an integration harness, not a new spreadsheet agent.
It reuses the frozen task compiler, workbook grounding/spine, Architecture v1.1
bootstrap/SQL session, sparse verifier, and official scorer.  Golden data is
loaded only by evaluator-side scoring/diagnostics and is never placed in model
messages.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import statistics
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
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "benchmark/sweagent/formula_index/lib"), str(ROOT / "src")]

import formula_projection_preflight as projection  # noqa: E402
import formula_synthesis_probe as synth_tools  # noqa: E402
import hybrid_sql_retrieval_probe as hybrid  # noqa: E402
import relational_retrieval_probe as relational  # noqa: E402
from formula_completion_certs import load_grids  # noqa: E402
from formula_operational import build_view  # noqa: E402
from formula_verifier import scc_stats  # noqa: E402
from task_obligation_compile import (  # noqa: E402
    PARSER_PROMPT,
    critical_requirements,
    extract_json_object,
    normalize_prediction,
    score_task,
)
from task_obligation_shape import family_of, is_semantic_change  # noqa: E402
from workbook_grounding import (  # noqa: E402
    field_text,
    gold_entities,
    project_obligation,
    token_estimate,
)
from workbook_grounding_probe import _load_spine  # noqa: E402
from workbook_spine_sqlite import ReadOnlySqlite, database_id_inventory  # noqa: E402
from xlsx_metadata_repair import install  # noqa: E402

install()
import openpyxl  # noqa: E402
from openpyxl.cell.cell import MergedCell  # noqa: E402


MODEL = "z-ai/glm-5.3-flash"
DISPLAY_MODEL = "GLM 5.3 Flash"
TEMPERATURE = 0.0
REASONING = "medium"
# The provider counts reasoning against the output budget, so a reasoning-heavy
# turn can spend the whole allowance and return an empty body. That is a
# truncation, not a malformed answer, and conflating the two scored real
# proposals as model failures. Synthesis reasons the longest, so it gets its own
# larger budget, and an exhausted budget is now labelled instead of guessed at.
RETRIEVAL_MAX_TOKENS = 2200
SYNTHESIS_MAX_TOKENS = 6000

MAX_SQL_CALLS = 8
DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
BENCHMARK_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2"
OUT = BENCHMARK_ROOT / "benchmark-runs/mechanical/end-to-end-composition-probe"
MECHANICAL = BENCHMARK_ROOT / "benchmark-runs/mechanical"
DATASET_PATH = DATA / "Financial_Model/dataset.json"
DELTA_PATH = MECHANICAL / "task-obligation-shape-probe/golden_delta.json"
ORACLE_PATH = MECHANICAL / "task-obligation-compile-probe/oracle_obligations.json"
PARSER_PATH = MECHANICAL / "task-obligation-compile-probe/parser_prompt.txt"
NARROW_PATH = MECHANICAL / "hybrid-sql-retrieval-probe/narrow_population.json"
INTEGRATED_PATH = MECHANICAL / "integrated-hybrid-synthesis-probe"
SQL_CONTEXT = relational.sql_strong_context("", {})

KNOWN_TASKS = ("04_05", "08_01", "09_05", "14_05", "15_04", "17_03", "20_04")
KNOWN_ADDRESSES = {"K6", "K163", "L163", "D10", "H41", "J31", "J46", "AF66", "AG66", "K104", "Y39", "Y40"}

TARGET_SYSTEM = """You are the target-generation stage of a spreadsheet agent.

You receive the raw task, a generated TASK_OBLIGATION_SHAPE_V1 representation,
and conservative grounding packets. Select every candidate cell that should be
considered for a FORMULA edit in this task. Use only candidate IDs supplied in
the packets. Do not invent sheet/cell IDs. Preserve ambiguity by returning all
plausible candidate cells rather than choosing a single one without evidence.
Do not write formulas and do not use golden information.

Return JSON only:
{"status":"PROPOSED_TARGETS"|"UNRESOLVED","targets":[{"target_id":"cell:...","obligation_id":"O1"}]}
"""

RETRIEVAL_SYSTEM = relational.sql_strong_context("", {}) + """

ARCHITECTURE V1.1 RETRIEVAL PROTOCOL:
The deterministic bootstrap below is initial evidence. The immutable SQLite
workbook database is complete and execute_sql is read-only. Every SQL result is
automatically accumulated by the harness into a monotone working set outside
your memory. Never delete candidates. Preserve ambiguity. Do not synthesize a
formula during retrieval.

Until the synthesis transition, return exactly one JSON action:
{"action":"execute_sql","sql":"SELECT ..."}
or {"action":"final","status":"ENOUGH_EVIDENCE"|"UNRESOLVED"}.
"""

SYNTHESIS_TRANSITION = """Retrieval is complete for this attempt. Using the raw task, generated obligations, exact target, and all workbook evidence available in the accumulated working set, produce the formula that should be placed in the target.

You may use any workbook entity present in the accumulated working set. Do not invent workbook cells, sheets, labels, or relationships. Existing patterns are evidence, not correctness guarantees. If the evidence is insufficient, abstain.

Return JSON only:
{"target_id":"cell:...","status":"PROPOSED"|"ABSTAIN","formula":"=..."|null}
"""

DELTA_RETRIEVAL_SYSTEM = relational.sql_strong_context("", {}) + """

ARCHITECTURE V1.1 RETRIEVAL PROTOCOL (delta state):
The deterministic bootstrap is initial evidence. The immutable SQLite workbook
database is complete and execute_sql is read-only.

The harness holds the complete monotone working set for this session outside
your context. It is never truncated and never loses an entity. To keep each turn
small it is not re-sent: SESSION_STATE gives you its handle and exact per-kind
counts, and NEW_SINCE_LAST_TURN lists only the identities added by your last
query. Any entity accumulated earlier still exists and can be re-materialized
exactly by querying it again by ID. Never delete candidates. Preserve ambiguity.
Do not synthesize a formula during retrieval.

Until the synthesis transition, return exactly one JSON action:
{"action":"execute_sql","sql":"SELECT ..."}
or {"action":"final","status":"ENOUGH_EVIDENCE"|"UNRESOLVED"}.
"""

SYNTHESIS_SYSTEM = relational.sql_strong_context("", {}) + """

ARCHITECTURE V1.1 SYNTHESIS PROTOCOL:
Retrieval is over. No further query will be executed, and any retrieval action
you return is discarded as a non-answer. The accumulated working set supplied
below is the complete evidence available for this target.

Using it, decide the formula for the exact target cell. Existing patterns are
evidence, not correctness guarantees. Do not invent workbook cells, sheets,
labels, or relationships. If the evidence is insufficient, abstain.

Return exactly one JSON object and nothing else:
{"target_id":"cell:...","status":"PROPOSED"|"ABSTAIN","formula":"=..."|null}
"""

FORMULA_ONLY_SCOPE = "The composed Architecture v1.2 scope is formula insertion/replacement/model completion. The output schema accepts formula edits only."


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def guard(model: str) -> None:
    if model != MODEL or model.startswith("openai/") or model.upper().startswith("GPT"):
        raise RuntimeError(f"model guard rejected {model!r}; exact {MODEL!r} required")


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def call_glm(key: str, system: str, user: str, title: str, max_tokens: int = 4000) -> dict[str, Any]:
    guard(MODEL)
    body = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "reasoning": {"effort": REASONING},
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        relational.OPENROUTER_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": title},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            payload = json.loads(response.read().decode())
        returned = payload.get("model")
        if returned and returned != MODEL:
            return {"http_ok": False, "failure_class": "MODEL_ACCESS_FAILURE", "detail": f"unexpected returned model {returned}"}
        choices = payload.get("choices") or []
        text = ((choices[0].get("message") or {}).get("content") or "") if choices else ""
        return {"http_ok": True, "text": text, "usage": payload.get("usage") or {}, "payload_model": returned}
    except urllib.error.HTTPError as exc:
        return {"http_ok": False, "failure_class": "MODEL_ACCESS_FAILURE", "status": exc.code, "detail": exc.read().decode(errors="replace")[:2000]}
    except Exception as exc:  # infrastructure only; never fallback
        return {"http_ok": False, "failure_class": "MODEL_ACCESS_FAILURE", "status": 0, "detail": f"{type(exc).__name__}: {exc}"}


def task_map() -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in load(DATASET_PATH)}


def delta_map() -> dict[str, dict[str, Any]]:
    return {r["task"]: r for r in load(DELTA_PATH)["tasks"]}


def narrow_rows() -> list[dict[str, Any]]:
    return load(NARROW_PATH)["rows"]


def task_profile(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for task in sorted({r["task"] for r in rows}):
        rs = [r for r in rows if r["task"] == task]
        out[task] = {
            "n_prior_targets": len(rs),
            "existing_n": sum(r.get("fingerprint_existing") is True for r in rs),
            "novel_n": sum(r.get("fingerprint_existing") is False for r in rs),
            "prior_complete_n": sum(bool(r.get("retrieval_complete_q8")) for r in rs),
            "prior_incomplete_n": sum(not bool(r.get("retrieval_complete_q8")) for r in rs),
            "static_failure_n": sum(not bool(r.get("static_projection_complete")) for r in rs),
            "edit_types": sorted({r.get("edit_type") for r in rs}),
        }
    prior_synth = INTEGRATED_PATH / "synthesis_population.json"
    if prior_synth.exists():
        for row in load(prior_synth).get("rows", []):
            rec = out.setdefault(row["task"], {"n_prior_targets": 0, "existing_n": 0, "novel_n": 0, "prior_complete_n": 0, "prior_incomplete_n": 0, "static_failure_n": 0, "edit_types": []})
            rec["existing_n"] += int(row.get("fingerprint_existing") is True)
            rec["novel_n"] += int(row.get("fingerprint_existing") is False)
            rec["prior_complete_n"] += int(bool(row.get("retrieval_complete_q8")))
            rec["prior_incomplete_n"] += int(not bool(row.get("retrieval_complete_q8")))
    return out


def formula_gold_changes(task: str) -> list[dict[str, Any]]:
    return [c for c in delta_map()[task]["changes"] if is_semantic_change(c) and c.get("golden_kind") == "formula"]


def choose_tasks() -> dict[str, Any]:
    profiles = task_profile(narrow_rows())
    all_tasks = task_map()
    delta = delta_map()
    known = []
    for task in KNOWN_TASKS:
        if task in all_tasks and formula_gold_changes(task):
            known.append(task)
    # P3 deliberately keeps all known diagnostic workbook/task regimes except
    # the least diagnostic one when exact 18-task balance is possible.
    p3 = sorted(known, key=lambda t: (-sum(1 for r in narrow_rows() if r["task"] == t and r["target"]["address"] in KNOWN_ADDRESSES), t))[:6]
    excluded = set(p3)
    candidates = [t for t in profiles if t not in excluded and formula_gold_changes(t)]
    existing = [t for t in candidates if profiles[t]["existing_n"] > 0 and profiles[t]["prior_complete_n"] > 0]
    novel = [t for t in candidates if profiles[t]["novel_n"] > 0]
    # Deterministic round-robin over family, task, and prior retrieval evidence.
    def pick(pool: list[str], n: int, used: set[str]) -> list[str]:
        pool = sorted(set(pool), key=lambda t: (family_of(t), t))
        out: list[str] = []
        for fam in sorted({family_of(t) for t in pool}):
            for t in pool:
                if t not in used and t not in out and family_of(t) == fam:
                    out.append(t)
                    if len(out) == n:
                        return out
        for t in pool:
            if t not in used and t not in out:
                out.append(t)
                if len(out) == n:
                    break
        return out
    p1 = pick(existing, 6, set(p3))
    p2 = pick(novel, 6, set(p3) | set(p1))
    selected = p3 + p1 + p2
    # If a stratum is short, fill deterministically with formula-bearing tasks.
    for task in sorted(all_tasks):
        if len(selected) >= 18:
            break
        if task not in selected and formula_gold_changes(task):
            selected.append(task)
    selected = selected[:18]
    rows = []
    for task in selected:
        if task in p3:
            stratum = "P3_KNOWN_DIAGNOSTIC_COMPOSITION"
        elif task in p1:
            stratum = "P1_PROGRAM_RECOVERY_FAVORABLE"
        elif task in p2:
            stratum = "P2_NOVEL_PROGRAM"
        else:
            stratum = "DETERMINISTIC_FORMULA_SCOPE_FILL"
        rs = [r for r in narrow_rows() if r["task"] == task]
        rows.append({
            "task": task,
            "family": family_of(task),
            "split": next((r.get("split") for r in rs), "unknown"),
            "category": "Financial_Model",
            "selection_stratum": stratum,
            "selection_reason": {
                "formula_gold_targets": len(formula_gold_changes(task)),
                "prior_target_rows": len(rs),
                "existing_prior_targets": sum(r.get("fingerprint_existing") is True for r in rs),
                "novel_prior_targets": sum(r.get("fingerprint_existing") is False for r in rs),
                "prior_retrieval_complete": sum(bool(r.get("retrieval_complete_q8")) for r in rs),
                "known_addresses": sorted({r["target"]["address"] for r in rs if r["target"]["address"] in KNOWN_ADDRESSES}),
            },
            "known_cases_present": sorted({r["target"]["address"] for r in rs if r["target"]["address"] in KNOWN_ADDRESSES}),
            "prior_evidence_available": bool(rs),
            "semantic_change_counts": delta[task]["change_kind_counts"],
            "gold_formula_target_count_evaluator_only": len(formula_gold_changes(task)),
        })
    return {"generated_at": datetime.now(UTC).isoformat(), "requested": 18, "n": len(rows), "rows": rows,
            "stratum_counts": dict(Counter(r["selection_stratum"] for r in rows)),
            "note": "Selection uses only pre-existing evaluator artifacts and is frozen before new model calls."}


def target_address(spine: dict[str, Any], cell_id: str) -> dict[str, Any] | None:
    m = re.fullmatch(r"cell:s(\d+):r(\d+):c(\d+)", cell_id or "")
    if not m:
        return None
    sid, row, col = int(m.group(1)), int(m.group(2)), int(m.group(3))
    title = next((s.get("title") for s in spine.get("sheets", []) if int(s.get("index", -1)) == sid), None)
    if not title:
        return None
    from openpyxl.utils import get_column_letter
    return {"sheet": title, "address": f"{get_column_letter(col)}{row}", "row": row, "col": col, "cell_id": cell_id}


def cell_kind_value(spine: dict[str, Any], cell_id: str) -> dict[str, Any]:
    for cell in spine.get("occupied", []):
        if cell.get("id") == cell_id:
            return {"kind": cell.get("kind"), "raw_value": cell.get("value") or cell.get("raw_value")}
    return {"kind": "blank", "raw_value": None}


def input_cell_info(task_id: str, sheet: str, address: str) -> dict[str, Any]:
    wb = openpyxl.load_workbook(synth_tools._input_path(task_id), data_only=False, read_only=True)
    try:
        value = wb[sheet][address].value
    finally:
        wb.close()
    if value is None or (isinstance(value, str) and not value.strip()):
        kind = "blank"
    elif isinstance(value, str) and value.startswith("="):
        kind = "formula"
    else:
        kind = "value"
    return {"kind": kind, "raw_value": value}


def compile_bootstrap(spine: dict[str, Any], packet: dict[str, Any], obligation: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    row = {"target": target, "obligation": obligation, "edit_type": "UNKNOWN"}
    idx = projection.formula_indexes(spine)
    sid = projection.sid_for(spine, target["sheet"])
    mechanisms = projection.generate_mechanisms(spine, packet, row, idx)
    forms: dict[str, dict[str, Any]] = {}
    for f, prov in [(f, ["M2"]) for f in projection.local_formulas(idx, sid, target["row"], target["col"])] + [(f, ["M4_ROW"]) for f in idx["by_row"].get((sid, target["row"]), [])] + [(f, ["M4_COLUMN"]) for f in idx["by_col"].get((sid, target["col"]), [])]:
        rec = forms.setdefault(f["id"], {"formula_id": f["id"], "cell_id": f.get("cell_id"), "class_id": f.get("class_id"), "provenance": []})
        rec["provenance"] = sorted(set(rec["provenance"]) | set(prov))
    refs: dict[str, dict[str, Any]] = {}
    for mech in ("M0", "M2", "M4"):
        for key in mechanisms[mech]["points"] | mechanisms[mech]["ranges"]:
            eid = hybrid.canonical_ref_id(key)
            refs.setdefault(eid, {"entity_id": eid, "provenance": []})["provenance"].append(mech)
    for rec in refs.values():
        rec["provenance"] = sorted(set(rec["provenance"]))
    packet_ids = projection.packet_ids(packet) | set(refs) | {x for f in forms.values() for x in (f.get("formula_id"), f.get("cell_id"), f.get("class_id")) if x}
    payload = {
        "target": {"target_id": target["cell_id"], "sheet": target["sheet"], "address": target["address"], "current_input_content": target.get("current_input_content"), "current_input_kind": target.get("current_input_kind")},
        "obligation": obligation,
        "grounded_core": {"locus": sorted(projection.packet_ids({"locus": packet.get("locus") or []})), "subject": sorted(projection.packet_ids({"subject": packet.get("subject") or []})), "scope": sorted(projection.packet_ids({"scope": packet.get("scope") or []})), "source": sorted(projection.packet_ids({"source": packet.get("source") or []}))},
        "formula_evidence": {"formula_ids": sorted(forms), "formula_records": [forms[k] for k in sorted(forms)], "fingerprint_ids": sorted({f.get("class_id") for f in forms.values() if f.get("class_id")})},
        "reference_candidates": {"records": [refs[k] for k in sorted(refs)]},
        "bootstrap_entity_ids": sorted(packet_ids),
    }
    payload["bootstrap_tokens"] = token_estimate(payload)
    payload["bootstrap_too_large"] = payload["bootstrap_tokens"] > 8000
    return payload


def candidate_context(task: str, raw: str, obligations: list[dict[str, Any]], packets: dict[str, dict[str, Any]], spine: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    seen = set()
    for ob in obligations:
        packet = packets.get(ob["id"], {})
        for cid in packet.get("target_cell_ids") or []:
            if cid in seen:
                continue
            seen.add(cid)
            info = target_address(spine, cid) or {"cell_id": cid}
            info.update(cell_kind_value(spine, cid))
            info["obligation_ids"] = [ob["id"]]
            candidates.append(info)
    byid = {x["cell_id"]: x for x in candidates}
    for ob in obligations:
        for cid in packets.get(ob["id"], {}).get("target_cell_ids") or []:
            if cid in byid and ob["id"] not in byid[cid]["obligation_ids"]:
                byid[cid]["obligation_ids"].append(ob["id"])
    return {"RAW_TASK": raw, "GENERATED_TASK_IR": {"obligations": obligations}, "GROUNDED_TARGET_CANDIDATES": candidates, "candidate_count": len(candidates)}


def compile_task(task: dict[str, Any], key: str) -> dict[str, Any]:
    raw = task["instruction"]
    response = call_glm(key, PARSER_PROMPT, "Compile the following task instruction into TASK_OBLIGATION_SHAPE_V1 JSON.\n\nTASK INSTRUCTION:\n" + raw, "librecalc-end-to-end-task-compiler", 5000)
    parsed = extract_json_object(response.get("text", "")) if response.get("http_ok") else None
    obligations = normalize_prediction(parsed)
    return {"task": task["id"], "raw_task": raw, "model": MODEL, "response": response, "parsed": parsed, "obligations": obligations, "parse_valid": bool(parsed and isinstance(parsed.get("obligations"), list))}


def target_select(task_id: str, context: dict[str, Any], key: str) -> dict[str, Any]:
    response = call_glm(key, TARGET_SYSTEM, json.dumps(context, ensure_ascii=False, separators=(",", ":")), "librecalc-end-to-end-target-selection", 6000)
    parsed = extract_json_object(response.get("text", "")) if response.get("http_ok") else None
    return {"task": task_id, "response": response, "parsed": parsed}


def sql_query(executor: ReadOnlySqlite, sql: str) -> dict[str, Any]:
    return executor.execute(sql)


def canonical_ids(result: dict[str, Any]) -> set[str]:
    return hybrid.result_ids(result)


def session_summary(target: dict[str, Any], obligation: dict[str, Any], working: set[str], history: list[dict[str, Any]], latest: dict[str, Any] | None, delta: set[str] | None = None, handle: str | None = None) -> str:
    """Serialize one retrieval turn.

    Default (handle is None) reproduces the frozen protocol: the whole working
    set is re-sent every turn. With a handle, the logical state is unchanged and
    still monotone and complete, but the prompt carries only the handle, the
    exact per-kind counts, and the identities added since the last turn. Anything
    accumulated earlier is re-materializable by ID through SQL.
    """
    counts = dict(Counter(x.split(":", 1)[0] for x in working))
    inner: dict[str, Any] = {"target": target, "obligation": obligation, "working_set_counts": counts}
    if handle is None:
        inner["working_set_entity_ids"] = sorted(working)
    else:
        inner["working_set_handle"] = handle
        inner["working_set_total"] = len(working)
        inner["working_set_note"] = "The harness holds the complete monotone working set. Earlier identities are omitted here, not lost; re-materialize any of them by querying their ID."
    inner["query_history"] = history
    state = {"SESSION_STATE": inner}
    if handle is not None:
        state["NEW_SINCE_LAST_TURN"] = {"count": len(delta or ()), "entity_ids": sorted(delta or ())}
    if latest is not None:
        state["LATEST_SQL_RESULT"] = latest
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"))


def run_target(task_id: str, raw_task: str, obligation: dict[str, Any], target: dict[str, Any], packet: dict[str, Any], spine: dict[str, Any], key: str, synthesis_system: str | None = None, retrieval_system: str | None = None, delta_state: bool = False, session_input_cap: int | None = None) -> dict[str, Any]:
    boot = compile_bootstrap(spine, packet, obligation, target)
    working = set(boot["bootstrap_entity_ids"]) | {target["cell_id"]}
    executor = ReadOnlySqlite(relational.db_path(task_id), max_rows=relational.RESULT_ROW_LIMIT, max_bytes=relational.RESULT_BYTE_LIMIT)
    history, calls = [], []
    latest = None
    materialized = 0
    retrieval_in = retrieval_out = summary_tokens = 0
    start = time.perf_counter()
    messages = [{"role": "user", "content": json.dumps({"RAW_TASK": raw_task, "OBLIGATION": obligation, "TARGET": target, "DETERMINISTIC_BOOTSTRAP": boot}, ensure_ascii=False, separators=(",", ":"))}]
    handle = f"ws-{hashlib.sha256((task_id + target['cell_id']).encode()).hexdigest()[:8]}" if delta_state else None
    resource_limited = False
    for q in range(1, MAX_SQL_CALLS + 1):
        # Predeclared per-session bound on measured provider input tokens. It
        # stops further retrieval explicitly rather than silently dropping
        # context, and the session still proceeds to its synthesis turn.
        if session_input_cap is not None and retrieval_in >= session_input_cap:
            resource_limited = True
            calls.append({"q": q, "action": None, "failure_class": "SESSION_RESOURCE_LIMIT",
                          "result": {"status": "SESSION_RESOURCE_LIMIT", "retrieval_input_tokens": retrieval_in, "cap": session_input_cap}})
            break
        response = call_glm(key, retrieval_system or RETRIEVAL_SYSTEM, messages[0]["content"], "librecalc-end-to-end-retrieval", RETRIEVAL_MAX_TOKENS)
        usage = response.get("usage") or {}
        retrieval_in += int(usage.get("prompt_tokens") or 0)
        retrieval_out += int(usage.get("completion_tokens") or 0)
        record = {"q": q, "response": response, "action": None}
        if not response.get("http_ok"):
            record["failure_class"] = "MODEL_ACCESS_FAILURE"
            calls.append(record)
            return {"status": "MODEL_ACCESS_FAILURE", "failure_class": "MODEL_ACCESS_FAILURE", "target": target, "obligation": obligation, "bootstrap": boot, "working_set_ids": sorted(working), "calls": calls}
        action = relational.extract_action(response.get("text", ""))
        record["action"] = action
        if not isinstance(action, dict):
            record["result"] = {"status": "ACTION_ERROR", "error": "Expected JSON retrieval action"}
            calls.append(record)
            messages = [{"role": "user", "content": session_summary(target, obligation, working, history, record["result"], set(), handle)}]
            summary_tokens += token_estimate(messages[0]["content"])
            continue
        if action.get("action") == "final":
            record["final"] = True
            calls.append(record)
            break
        sql = action.get("sql") if action.get("action") == "execute_sql" else ""
        result = sql_query(executor, sql) if sql else {"status": "ACTION_ERROR", "error": "Expected execute_sql"}
        # Same defect as the bootstrap estimate: the episode token limit was
        # measuring a dict key count, so RESULT_TOO_LARGE never triggered.
        est = token_estimate(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        if result.get("status") == "OK" and materialized + est > relational.EPISODE_TOKEN_LIMIT:
            result = {"status": "RESULT_TOO_LARGE", "estimated_result_tokens": est, "configured_episode_token_limit": relational.EPISODE_TOKEN_LIMIT}
        elif result.get("status") == "OK":
            materialized += est
        ids = canonical_ids(result)
        added = ids - working
        working |= ids
        record.update({"sql": sql, "sql_classification": relational.classify_sql(sql), "result": result, "new_working_set_ids": sorted(added)})
        calls.append(record)
        history.append({"q": q, "status": result.get("status"), "row_count": result.get("row_count"), "new_ids": len(added), "query_kind": relational.classify_sql(sql).get("query_kind")})
        latest = result
        messages = [{"role": "user", "content": session_summary(target, obligation, working, history, latest, added, handle)}]
        summary_tokens += token_estimate(messages[0]["content"])
    evidence = materialize_working_set(task_id, working)
    transition = {"SYNTHESIS_TRANSITION": SYNTHESIS_TRANSITION, "RAW_TASK": raw_task, "TARGET": target, "OBLIGATION": obligation, "WORKING_SET_COUNTS": dict(Counter(x.split(":", 1)[0] for x in working)), "WORKING_SET_ENTITY_IDS": sorted(working), "WORKING_SET_EVIDENCE": evidence}
    synth_response = call_glm(key, synthesis_system or RETRIEVAL_SYSTEM, json.dumps(transition, ensure_ascii=False, separators=(",", ":")), "librecalc-end-to-end-synthesis", SYNTHESIS_MAX_TOKENS)
    parsed = extract_json_object(synth_response.get("text", "")) if synth_response.get("http_ok") else None
    synth_usage = synth_response.get("usage") or {}
    # A response that spends its whole output budget and still carries no
    # parseable object was cut off, whether it emitted nothing at all or pages of
    # deliberation. Both are budget exhaustion; neither is a wrong answer.
    at_budget = synth_usage.get("completion_tokens") == SYNTHESIS_MAX_TOKENS
    synthesis_truncated = bool(synth_response.get("http_ok") and at_budget and parsed is None)
    truncation_class = ("TRUNCATED_NO_CONTENT" if synthesis_truncated and not (synth_response.get("text") or "")
                        else "TRUNCATED_AT_BUDGET" if synthesis_truncated else None)
    synth_failure = truncation_class or ("SESSION_RESOURCE_LIMIT" if resource_limited else None)
    return {"status": "PROPOSAL_RETURNED" if synth_response.get("http_ok") else "MODEL_ACCESS_FAILURE", "failure_class": synth_failure if synth_response.get("http_ok") else "MODEL_ACCESS_FAILURE", "synthesis_truncated": synthesis_truncated, "truncation_class": truncation_class, "session_resource_limited": resource_limited, "working_set_serialization": "DELTA" if delta_state else "FULL", "target": target, "obligation": obligation, "bootstrap": boot, "working_set_ids": sorted(working), "calls": calls, "synthesis": {"response": synth_response, "parsed": parsed}, "materialized_result_tokens": materialized, "retrieval_input_tokens": retrieval_in, "retrieval_output_tokens": retrieval_out, "session_summary_tokens": summary_tokens, "synthesis_input_tokens": int((synth_response.get("usage") or {}).get("prompt_tokens") or 0), "synthesis_output_tokens": int((synth_response.get("usage") or {}).get("completion_tokens") or 0), "elapsed_s": round(time.perf_counter() - start, 3)}


def materialize_working_set(task: str, working: set[str]) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    for x in sorted(working):
        groups[x.split(":", 1)[0]].append(x)
    ex = ReadOnlySqlite(relational.db_path(task), max_rows=relational.RESULT_ROW_LIMIT, max_bytes=relational.RESULT_BYTE_LIMIT)
    def in_sql(xs: list[str]) -> str:
        return ",".join("'" + x.replace("'", "''") + "'" for x in xs) or "NULL"
    out = {"entity_ids": sorted(working), "entities": {}, "relations": {}}
    if groups["cell"]:
        rows = ex.execute(f"SELECT cell_id,kind,raw_value,display_value FROM cells WHERE cell_id IN ({in_sql(groups['cell'])}) ORDER BY cell_id").get("rows", [])
        out["entities"]["cells"] = {"columns": ["cell_id", "kind", "raw_value", "display_value"], "rows": [[r.get(k) for k in ["cell_id", "kind", "raw_value", "display_value"]] for r in rows]}
    if groups["formula"]:
        rows = ex.execute(f"SELECT formula_id,cell_id,formula_text,fingerprint_id,opaque FROM formulas WHERE formula_id IN ({in_sql(groups['formula'])}) ORDER BY formula_id").get("rows", [])
        out["entities"]["formulas"] = {"columns": ["formula_id", "cell_id", "formula_text", "fingerprint_id", "opaque"], "rows": [[r.get(k) for k in ["formula_id", "cell_id", "formula_text", "fingerprint_id", "opaque"]] for r in rows]}
        rows = ex.execute(f"SELECT formula_id,referenced_cell_id,ref_slot,row_delta,col_delta,row_absolute,col_absolute,cross_sheet FROM point_references WHERE formula_id IN ({in_sql(groups['formula'])}) ORDER BY formula_id,ref_slot").get("rows", [])
        out["relations"]["point_references"] = {"columns": list(rows[0]) if rows else [], "rows": [list(r.values()) for r in rows]}
        rows = ex.execute(f"SELECT rr.formula_id,rr.range_id,rr.ref_slot,rr.cross_sheet,r.sheet_id,r.r1,r.c1,r.r2,r.c2 FROM range_references rr JOIN ranges r ON r.range_id=rr.range_id WHERE rr.formula_id IN ({in_sql(groups['formula'])}) ORDER BY rr.formula_id,rr.ref_slot").get("rows", [])
        out["relations"]["range_references"] = {"columns": list(rows[0]) if rows else [], "rows": [list(r.values()) for r in rows]}
    if groups["range"]:
        rows = ex.execute(f"SELECT range_id,sheet_id,r1,c1,r2,c2 FROM ranges WHERE range_id IN ({in_sql(groups['range'])}) ORDER BY range_id").get("rows", [])
        out["entities"]["ranges"] = {"columns": ["range_id", "sheet_id", "r1", "c1", "r2", "c2"], "rows": [[r.get(k) for k in ["range_id", "sheet_id", "r1", "c1", "r2", "c2"]] for r in rows]}
    if groups["formula_class"]:
        rows = ex.execute(f"SELECT fingerprint_id,canonical_fingerprint FROM formula_classes WHERE fingerprint_id IN ({in_sql(groups['formula_class'])}) ORDER BY fingerprint_id").get("rows", [])
        out["entities"]["formula_classes"] = {"columns": ["fingerprint_id", "canonical_fingerprint"], "rows": [[r.get(k) for k in ["fingerprint_id", "canonical_fingerprint"]] for r in rows]}
        rows = ex.execute(f"SELECT fingerprint_id,formula_id FROM formula_class_members WHERE fingerprint_id IN ({in_sql(groups['formula_class'])}) ORDER BY fingerprint_id,formula_id").get("rows", [])
        out["relations"]["formula_class_members"] = {"columns": ["fingerprint_id", "formula_id"], "rows": [[r.get(k) for k in ["fingerprint_id", "formula_id"]] for r in rows]}
    return out


def task_ir_eval(task_id: str, generated: list[dict[str, Any]], raw: str) -> dict[str, Any]:
    oracle = next((r for r in load(ORACLE_PATH)["tasks"] if r["task"] == task_id), None)
    if not oracle:
        return {"available": False}
    return {"available": True, **score_task(task_id=task_id, instruction=raw, oracle=oracle["obligations"], pred=generated, parse_valid=True)}


def grounding_eval(task_id: str, obligations: list[dict[str, Any]], packets: dict[str, dict[str, Any]], spine: dict[str, Any]) -> dict[str, Any]:
    delta = [c for c in delta_map()[task_id]["changes"] if is_semantic_change(c) and c.get("golden_kind") == "formula"]
    rows = []
    for change in delta:
        ents = gold_entities(spine, change)
        matches = []
        for ob in obligations:
            packet = packets.get(ob["id"], {})
            pids = set(projection.packet_ids(packet))
            labels = {x.get("cell_id") for x in packet.get("subject", [])} | {x.get("row_id") for x in packet.get("subject", [])}
            if ents["sheet_id"] in pids or ents["row_id"] in labels or ents["cell_id"] in set(packet.get("target_cell_ids") or []):
                matches.append(ob["id"])
        rows.append({"sheet": change["sheet"], "address": change["address"], "gold_entities": ents, "matched_obligation_ids": matches, "target_retained": any(ents["cell_id"] in set(packets[o].get("target_cell_ids") or []) for o in matches), "grounded_entity_retained": bool(matches)})
    return {"n_formula_gold_targets": len(rows), "rows": rows, "target_recall": sum(r["target_retained"] for r in rows) / len(rows) if rows else None, "grounded_recall": sum(r["grounded_entity_retained"] for r in rows) / len(rows) if rows else None}


def validate_and_apply(task_id: str, target: dict[str, Any], formula: str | None, view_cache: dict[str, Any], workbook: Any) -> dict[str, Any]:
    row = {"task": task_id, "target": target, "edit_type": "UNKNOWN"}
    spine = _load_spine(task_id)
    if not formula:
        return {"formula": None, "hard_verifier": "NOT_APPLICABLE", "hard_reject": False, "parser_ok": True}
    if task_id not in view_cache:
        grids = load_grids(synth_tools._input_path(task_id))
        from formula_dependency_selection import build_graph_from_grids
        view = build_view(build_graph_from_grids(grids))
        view_cache[task_id] = (view, scc_stats(view))
    validation = synth_tools._validate_formula(row, formula, {}, spine, *view_cache[task_id])
    accepted = not validation.get("hard_reject") and validation.get("parser_ok") and not validation.get("invalid_sheet") and not validation.get("invalid_address") and not validation.get("unsupported_external")
    if accepted:
        cell = workbook[target["sheet"]][target["address"]]
        if isinstance(cell, MergedCell):
            # Integration guard: openpyxl cannot assign to a non-anchor merged
            # cell.  Preserve the workbook and record the actuation boundary;
            # this is not a verifier rejection and is never retried.
            return {**validation, "hard_verifier_result": "HARD_ACCEPT", "applied": False, "actuation_error": "MERGED_CELL_NON_ANCHOR"}
        cell.value = formula
    return {**validation, "hard_verifier_result": "HARD_ACCEPT" if accepted else "HARD_REJECT", "applied": accepted}


def run_task(task_row: dict[str, Any], key: str) -> dict[str, Any]:
    task_id = task_row["task"]
    task = task_map()[task_id]
    spine = _load_spine(task_id)
    compiler = compile_task(task, key)
    obligations = compiler["obligations"]
    packets = {ob["id"]: project_obligation(spine, ob) for ob in obligations}
    target_ctx = candidate_context(task_id, task["instruction"], obligations, packets, spine)
    target_result = target_select(task_id, target_ctx, key)
    candidate_id_set = {x["cell_id"] for x in target_ctx["GROUNDED_TARGET_CANDIDATES"]}
    targets = []
    invalid_targets = []
    if isinstance(target_result.get("parsed"), dict):
        for item in target_result["parsed"].get("targets") or []:
            cid = item.get("target_id") if isinstance(item, dict) else None
            oid = item.get("obligation_id") if isinstance(item, dict) else None
            if cid not in candidate_id_set or oid not in packets:
                invalid_targets.append({"target_id": cid, "obligation_id": oid})
                continue
            addr = target_address(spine, cid)
            if addr:
                cell = input_cell_info(task_id, addr["sheet"], addr["address"])
                addr.update({"current_input_content": cell.get("raw_value"), "current_input_kind": cell.get("kind")})
                targets.append({"target_id": f"{task_id}:{oid}:{cid}", "cell_id": cid, "obligation_id": oid, **addr})
    dedup = {}
    for t in targets:
        dedup[(t["cell_id"], t["obligation_id"])] = t
    targets = list(dedup.values())
    # Deterministic task order: obligation reading order, then workbook address.
    order = {ob["id"]: i for i, ob in enumerate(obligations)}
    targets.sort(key=lambda x: (order.get(x["obligation_id"], 999), x["sheet"], x["row"], x["col"]))
    target_sessions = []
    wb = openpyxl.load_workbook(synth_tools._input_path(task_id), data_only=False, read_only=False)
    view_cache: dict[str, Any] = {}
    try:
        for t in targets:
            session = run_target(task_id, task["instruction"], obligations[order[t["obligation_id"]]], t, packets[t["obligation_id"]], spine, key)
            parsed = ((session.get("synthesis") or {}).get("parsed")) if session.get("status") != "MODEL_ACCESS_FAILURE" else None
            formula = parsed.get("formula") if isinstance(parsed, dict) and parsed.get("status") == "PROPOSED" else None
            session["target_job_id"] = t["target_id"]
            session["proposal"] = parsed
            session["validation"] = validate_and_apply(task_id, t, formula, view_cache, wb)
            target_sessions.append(session)
    finally:
        out_dir = OUT / f"Financial_Model-{task_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        wb.save(out_dir / "output.xlsx")
        wb.close()
    compiler_eval = task_ir_eval(task_id, obligations, task["instruction"])
    return {"task": task_id, "raw_task": task["instruction"], "compiler": compiler, "compiler_eval": compiler_eval, "grounding": {"obligations": obligations, "packets": packets, "evaluation": grounding_eval(task_id, obligations, packets, spine)}, "target_context": {"candidate_count": len(candidate_id_set), "tokens": token_estimate(target_ctx)}, "target_selection": target_result, "targets": targets, "invalid_targets": invalid_targets, "target_sessions": target_sessions}


def freeze() -> dict[str, Any]:
    population = choose_tasks()
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "end_to_end_population.json", population)
    component_paths = [PARSER_PATH, ROOT / "benchmark/task_obligation_compile.py", ROOT / "benchmark/workbook_grounding.py", ROOT / "benchmark/workbook_grounding_spine.py", ROOT / "benchmark/workbook_spine_sqlite.py", ROOT / "benchmark/hybrid_sql_retrieval_probe.py", ROOT / "benchmark/relational_retrieval_probe.py", ROOT / "benchmark/formula_synthesis_probe.py", ROOT / "benchmark/formula_verifier.py", ROOT / "benchmark/score_openrouter_run.py"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in component_paths if p.exists()}
    prompt_files = {"task_compiler": PARSER_PROMPT, "target_selection": TARGET_SYSTEM, "retrieval": RETRIEVAL_SYSTEM, "synthesis_transition": SYNTHESIS_TRANSITION}
    for name, text in prompt_files.items():
        write(OUT / f"{name}_prompt.txt", text)
    freeze_data = {"generated_at": datetime.now(UTC).isoformat(), "model": MODEL, "display_name": DISPLAY_MODEL, "temperature": TEMPERATURE, "reasoning": REASONING, "max_sql_calls": MAX_SQL_CALLS, "population_sha256": hashlib.sha256(json.dumps(population, sort_keys=True).encode()).hexdigest(), "component_sha256": hashes, "prompt_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in prompt_files.items()}, "oracle_in_model_context": False, "typed_api": False, "bare_schema_sql": False, "gpt": False, "retry": False, "self_critique": False, "verifier_repair": False, "original_workbooks_edited": False, "selection_frozen_before_model_calls": True}
    write(OUT / "freeze.json", freeze_data)
    return freeze_data


def run(worker_index: int = 0, worker_count: int = 1) -> None:
    guard(MODEL)
    pop = load(OUT / "end_to_end_population.json")["rows"]
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY required")
    path = OUT / f"task_runs.worker{worker_index:02d}.jsonl"
    done = {r.get("task") for r in read_jsonl(path) if r.get("status") != "MODEL_ACCESS_FAILURE"}
    assigned = [r for i, r in enumerate(pop) if i % worker_count == worker_index and r["task"] not in done]
    with path.open("a", encoding="utf-8") as handle:
        for i, row in enumerate(assigned, 1):
            print(f"TASK {worker_index} {i}/{len(assigned)} {row['task']}", flush=True)
            started = time.perf_counter()
            try:
                result = run_task(row, key)
                result["status"] = "OK"
            except Exception as exc:  # integration failure, not silently a model result
                result = {"task": row["task"], "status": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}"}
            result["elapsed_s"] = round(time.perf_counter() - started, 3)
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"DONE {row['task']} status={result['status']}", flush=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def all_runs() -> dict[str, dict[str, Any]]:
    out = {}
    for path in OUT.glob("task_runs.worker*.jsonl"):
        for row in read_jsonl(path):
            out[row["task"]] = row
    return out


def score_official() -> None:
    command = [sys.executable, str(ROOT / "benchmark/score_openrouter_run.py"), str(OUT), "--model-name", "architecture-v1.2-glm-5.3-flash", "--metadata-tolerant"]
    subprocess.run(command, cwd=ROOT / "benchmark-data/SpreadsheetBench-2/evaluation", check=False)


def report() -> dict[str, Any]:
    runs = all_runs()
    pop = {r["task"]: r for r in load(OUT / "end_to_end_population.json")["rows"]}
    target_rows = []
    for task, run in runs.items():
        if run.get("status") != "OK":
            continue
        gold = {c["sheet"] + "!" + c["address"] for c in formula_gold_changes(task)}
        selected = {t["sheet"] + "!" + t["address"] for t in run.get("targets", [])}
        target_rows.append({"task": task, "selected": len(selected), "gold_formula_targets": len(gold), "true_targets": len(selected & gold), "false_targets": len(selected - gold), "missed_targets": len(gold - selected), "target_precision": len(selected & gold) / len(selected) if selected else None, "target_recall": len(selected & gold) / len(gold) if gold else None})
    proposals = []
    for task, run in runs.items():
        for s in run.get("target_sessions", []):
            parsed = s.get("proposal") or {}
            formula = parsed.get("formula") if parsed.get("status") == "PROPOSED" else None
            proposals.append({"task": task, "target": s.get("target"), "proposal": parsed, "formula": formula, "validation": s.get("validation"), "working_set_size": len(s.get("working_set_ids", [])), "bootstrap_tokens": (s.get("bootstrap") or {}).get("bootstrap_tokens"), "retrieval_complete": None})
    # Evaluator-side exact formula labels for every proposed target.
    dm = delta_map()
    for p in proposals:
        target = p["target"]
        change = next((c for c in dm[p["task"]]["changes"] if c["sheet"] == target["sheet"] and c["address"] == target["address"]), None)
        p["gold_formula"] = change.get("golden_payload") if change else None
        p["gold_target"] = bool(change and is_semantic_change(change) and change.get("golden_kind") == "formula")
        p["formula_correct"] = bool(p["formula"] and p["gold_formula"] and synth_tools._canonical_formula(p["formula"]) == synth_tools._canonical_formula(p["gold_formula"]))
        p["program_regime"] = None
        if change:
            p["program_regime"] = "EXISTING_PROGRAM" if change.get("golden_formula_fingerprint") and any(r.get("gold_fingerprint") == change.get("golden_formula_fingerprint") and r.get("task") == p["task"] for r in narrow_rows()) else "NOVEL_PROGRAM"
    formula_targets = [p for p in proposals if p["gold_target"]]
    all_formula_proposals = [p for p in proposals if p.get("formula")]
    correct = [p for p in formula_targets if p["formula_correct"]]
    valid_target_tasks = [r for r in runs.values() if r.get("status") == "OK"]
    funnel = {"tasks": len(pop), "valid_task_runs": len(valid_target_tasks), "task_ir_valid": sum(bool(r.get("compiler", {}).get("parse_valid")) for r in valid_target_tasks), "task_ir_critical_present": sum(bool(r.get("compiler_eval", {}).get("all_critical_requirements_preserved")) for r in valid_target_tasks), "grounding_entity_retained": sum(bool((r.get("grounding", {}).get("evaluation") or {}).get("grounded_recall") == 1.0) for r in valid_target_tasks), "targets_generated": sum(len(r.get("targets", [])) for r in valid_target_tasks), "formula_gold_targets_in_valid_tasks": sum(len(formula_gold_changes(t)) for t in runs if runs[t].get("status") == "OK"), "formula_proposals": len(all_formula_proposals), "formula_proposals_on_gold_targets": len(formula_targets), "formula_correct_on_gold_targets": len(correct), "verifier_accepted": sum((p.get("validation") or {}).get("hard_verifier_result") == "HARD_ACCEPT" for p in all_formula_proposals), "verifier_rejected": sum((p.get("validation") or {}).get("hard_verifier_result") == "HARD_REJECT" for p in all_formula_proposals), "scored_workbooks": len(valid_target_tasks)}
    official_path = OUT / "scoring-valid/official_scores.json"
    official = load(official_path) if official_path.exists() else None
    earliest = {}
    target_by_task = {x["task"]: x for x in target_rows}
    for task_row in load(OUT / "end_to_end_population.json")["rows"]:
        tid = task_row["task"]
        r = runs.get(tid)
        if not r:
            earliest[tid] = "RESOURCE_CENSORED_NOT_RUN"
        elif r.get("status") == "MODEL_ACCESS_FAILURE":
            earliest[tid] = "MODEL_ACCESS_FAILURE"
        elif r.get("status") == "RESOURCE_CENSORED_NOT_RUN":
            earliest[tid] = "RESOURCE_CENSORED_NOT_RUN"
        elif r.get("status") == "INTEGRATION_FAILURE":
            earliest[tid] = "F7_ACTUATION_FAILURE"
        elif not (r.get("compiler_eval") or {}).get("all_critical_requirements_preserved"):
            earliest[tid] = "F0_TASK_SPEC_LOSS"
        elif not (target_by_task.get(tid) or {}).get("selected"):
            earliest[tid] = "F2_TARGET_MISS"
        elif not (target_by_task.get(tid) or {}).get("true_targets"):
            earliest[tid] = "F2_TARGET_MISS"
        else:
            earliest[tid] = "F5_NOVEL_SYNTHESIS_FAILURE_OR_PROGRAM_RECOVERY_UNTESTED"
    payload = {"generated_at": datetime.now(UTC).isoformat(), "population": load(OUT / "end_to_end_population.json"), "runs": {k: {"status": v.get("status"), "compiler_eval": v.get("compiler_eval"), "grounding": v.get("grounding", {}).get("evaluation"), "target_count": len(v.get("targets", [])), "invalid_target_count": len(v.get("invalid_targets", [])), "target_selection": v.get("target_selection", {}).get("parsed")} for k, v in runs.items()}, "target_metrics": target_rows, "formula_metrics": {"all_formula_proposals": len(all_formula_proposals), "gold_target_proposals": len(formula_targets), "correct_gold_target_proposals": len(correct), "conditional_rate_on_gold_target_proposals": len(correct) / len(formula_targets) if formula_targets else None, "by_regime": {reg: {"n": sum(p["program_regime"] == reg for p in formula_targets), "correct": sum(p["program_regime"] == reg and p["formula_correct"] for p in formula_targets)} for reg in ("EXISTING_PROGRAM", "NOVEL_PROGRAM")}}, "proposals": proposals, "stage_funnel": funnel, "earliest_failure": earliest, "official_scores": official, "model": {"id": MODEL, "display_name": DISPLAY_MODEL, "temperature": TEMPERATURE, "reasoning": REASONING}, "model_access_failures": sum(v.get("status") == "MODEL_ACCESS_FAILURE" for v in runs.values()), "resource_censored_not_run": sum(v.get("status") == "RESOURCE_CENSORED_NOT_RUN" for v in runs.values()), "integration_failures": sum(v.get("status") == "INTEGRATION_FAILURE" for v in runs.values())}
    write(OUT / "report.json", payload)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze")
    r = sub.add_parser("run"); r.add_argument("--worker-index", type=int, default=0); r.add_argument("--worker-count", type=int, default=1)
    sub.add_parser("score")
    sub.add_parser("report")
    args = ap.parse_args()
    if args.cmd == "freeze": print(json.dumps(freeze(), indent=2))
    elif args.cmd == "run": run(args.worker_index, args.worker_count)
    elif args.cmd == "score": score_official()
    else: print(json.dumps(report(), indent=2))


if __name__ == "__main__":
    main()
