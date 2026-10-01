#!/usr/bin/env python3
"""Minimal model-only swap at the frozen novel-program frontier.

This runner consumes the retained GLM F0 request bodies from the staged
synthesis probe.  It does not rebuild prompts, perform retrieval, or run a
staged arm.  For each case it copies the exact retained request and changes
only the provider/model configuration needed for the GPT arm.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import execution_unit_score as ES
import program_group as pg
import staged_synthesis_probe as staged
import synthesis_decomposition as sd
import instrumentation_freeze as instr


ROOT = old.ROOT
SOURCE = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/staged-synthesis-probe"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/model-swap-frontier"
CALLS = OUT / "calls"
VARIANTS = OUT / "variants"
MODEL = "openai/gpt-5.6-sol"
DISPLAY_MODEL = "GPT-5.6 Sol"
TEMPERATURE = 0.0
REASONING = "high"
RETRIES = 0


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def source_records() -> list[dict]:
    freeze = load(SOURCE / "freeze.json")
    out = []
    for meta in freeze["population"]:
        stem = f'{meta["task"]}__{meta["canonical_member"].replace("!", "_").replace(" ", "_")}__F0'
        path = SOURCE / "calls" / f"{stem}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        rec = load(path)
        if rec.get("request", {}).get("model") != "z-ai/glm-5.3-flash":
            raise RuntimeError(f"unexpected GLM source model in {path}")
        out.append({"meta": meta, "source_path": str(path), "source": rec})
    return out


def provider_independent_request(req: dict) -> dict:
    """Remove only model/provider configuration from a retained request body."""
    out = copy.deepcopy(req)
    out.pop("model", None)
    out.pop("reasoning", None)
    return out


def request_diff(glm_req: dict, gpt_req: dict) -> dict:
    a = provider_independent_request(glm_req)
    b = provider_independent_request(gpt_req)
    return {"identical": a == b, "glm_sha256": sha(a), "gpt_sha256": sha(b),
            "glm_request": a if a != b else None, "gpt_request": b if a != b else None}


def call_one(source: dict, key: str) -> dict:
    meta, old_rec = source["meta"], source["source"]
    name = f'{meta["task"]}__{meta["canonical_member"].replace("!", "_").replace(" ", "_")}__G0'
    path = CALLS / f"{name}.json"
    if path.exists():
        return load(path)

    body = copy.deepcopy(old_rec["request"])
    body["model"] = MODEL
    body["reasoning"] = {"effort": REASONING}
    started = time.perf_counter()
    raw_body = ""
    status_code = None
    payload = None
    failure = None
    detail = None
    try:
        req = urllib.request.Request(
            old.relational.OPENROUTER_URL,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Title": "librecalc-model-swap-frontier",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as response:
            status_code = response.status
            raw_body = response.read().decode(errors="replace")
        payload = json.loads(raw_body)
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        raw_body = exc.read().decode(errors="replace")
        failure, detail = "MODEL_ACCESS_FAILURE", raw_body[:2000]
    except Exception as exc:
        failure, detail = "MODEL_ACCESS_FAILURE", f"{type(exc).__name__}: {exc}"

    choices = (payload or {}).get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    text = message.get("content") or ""
    finish = choices[0].get("finish_reason") if choices else None
    parsed = old.extract_json_object(text) if payload is not None else None
    usage = (payload or {}).get("usage") or {}
    max_tokens = int(body.get("max_tokens") or 0)
    at_budget = int(usage.get("completion_tokens") or 0) == max_tokens
    truncation = None
    if failure is None and at_budget and parsed is None:
        truncation = "TRUNCATED_NO_CONTENT" if not text else "TRUNCATED_AT_BUDGET"
    returned_model = (payload or {}).get("model")
    if failure is None and returned_model and returned_model != MODEL:
        failure, detail = "MODEL_ACCESS_FAILURE", f"unexpected returned model {returned_model!r}"

    rec = {
        "name": name,
        "arm": "G0",
        "task": meta["task"],
        "canonical_member": meta["canonical_member"],
        "source_glm_call": source["source_path"],
        "source_glm_request_sha256": sha(old_rec["request"]),
        "request": body,
        "request_sha256": sha(body),
        "system_prompt": body["messages"][0]["content"],
        "user_payload": body["messages"][1]["content"],
        "system_sha256": hashlib.sha256(body["messages"][0]["content"].encode()).hexdigest(),
        "user_payload_sha256": hashlib.sha256(body["messages"][1]["content"].encode()).hexdigest(),
        "request_fidelity": request_diff(old_rec["request"], body),
        "model": MODEL,
        "display_model": DISPLAY_MODEL,
        "temperature": TEMPERATURE,
        "reasoning": REASONING,
        "retries": RETRIES,
        "response_http_status": status_code,
        "response_raw_body": raw_body,
        "response_body": payload,
        "raw_response_text": text,
        "parsed_response": parsed,
        "finish_reason": finish,
        "usage": usage,
        "truncation_class": truncation,
        "failure_class": failure,
        "failure_detail": detail,
        "returned_model": returned_model,
        "input_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
        "wall_seconds": round(time.perf_counter() - started, 3),
    }
    write(path, rec)
    return rec


def formula_from_response(rec: dict) -> str | None:
    parsed = rec.get("parsed_response") or {}
    if parsed.get("status") != "PROPOSED":
        return None
    formula = parsed.get("formula")
    return formula if isinstance(formula, str) and formula.startswith("=") else None


def formula_refs(task: str, member: str, formula: str) -> list[str] | None:
    try:
        home = member.split("!", 1)[0]
        ops = sd.oa.operands(formula, home)
        con = sd.oa._conn(task)
        try:
            sheets, cells = sd.oa._sheet_ids(con), sd.oa._cell_index(con)
            refs = []
            for op in ops:
                sid = sheets.get(op["sheet"])
                if not sid:
                    continue
                if op["kind"] == "POINT":
                    cell = cells.get((sid, op["start"]))
                    if cell:
                        refs.append(cell["cell_id"])
                elif op["kind"] == "RANGE":
                    from openpyxl.utils.cell import range_boundaries
                    start = f'{op["start"]}:{op["end"]}'
                    min_col, min_row, max_col, max_row = range_boundaries(start)
                    for (cell_sid, _address), cell in cells.items():
                        row_idx, col_idx = cell["row_idx"], cell["col_idx"]
                        if cell_sid == sid and min_row <= row_idx <= max_row and min_col <= col_idx <= max_col:
                            refs.append(cell["cell_id"])
            return refs
        finally:
            con.close()
    except Exception:
        return None


def classify_formula(task: str, member: str, formula: str | None, gold: str) -> dict:
    if formula is None:
        return {"class": "ABSTAIN", "formula_parseable": False, "refs": None}
    refs = formula_refs(task, member, formula)
    gold_refs = formula_refs(task, member, gold)
    try:
        ast = staged.gold_ast(formula)
        parseable = True
    except Exception as exc:
        # The small evaluator AST intentionally covers the canonical binary
        # grammar, while the workbook validator also accepts ordinary function
        # formulas such as SUM(J46:J47).  Keep those formulas syntactically
        # valid and classify their structure from the available reference set.
        if refs is not None and gold_refs is not None and set(refs) == set(gold_refs):
            cls = "WRONG_STRUCTURE_CORRECT_REFERENCE_SET"
        else:
            cls = "WRONG_STRUCTURE_WRONG_BINDING"
        return {"class": cls, "formula_parseable": mechanical_check(member, formula)["valid"],
                "ast_comparable": False, "parse_error": f"{type(exc).__name__}: {exc}",
                "refs": refs, "gold_refs": gold_refs, "formula_exact": False}
    g_ast = staged.gold_ast(gold)
    exact = bool(ES._same(formula, gold))
    if exact:
        cls = "CORRECT_STRUCTURE_CORRECT_BINDING"
    elif staged.abstract(ast) == staged.abstract(g_ast):
        cls = "CORRECT_STRUCTURE_WRONG_BINDING"
    elif refs is not None and gold_refs is not None and set(refs) == set(gold_refs):
        cls = "WRONG_STRUCTURE_CORRECT_REFERENCE_SET"
    else:
        cls = "WRONG_STRUCTURE_WRONG_BINDING"
    return {"class": cls, "formula_parseable": parseable, "refs": refs,
            "gold_refs": gold_refs, "abstract_exact": staged.abstract(ast) == staged.abstract(g_ast),
            "formula_exact": exact}


def mechanical_check(member: str, formula: str | None) -> dict:
    if formula is None:
        return {"valid": True, "reason": "NO_FORMULA"}
    try:
        from openpyxl.formula import Tokenizer
        target = member.split("!", 1)[1].replace("$", "").upper()
        for token in Tokenizer(formula).items:
            if token.type == "OPERAND" and token.subtype == "RANGE":
                ref = token.value.replace("$", "").upper()
                if "!" not in ref and ref == target:
                    return {"valid": False, "reason": "DIRECT_SELF_REFERENCE"}
        return {"valid": True, "reason": "OK"}
    except Exception as exc:
        return {"valid": False, "reason": f"PARSE_FAILURE:{type(exc).__name__}"}


def end_to_end(task: str, member: str, formula: str | None) -> dict:
    unit = staged.units()[(task, member)]
    name = f'{task}__{member.replace("!", "_").replace(" ", "_")}__G0'
    dest_dir = VARIANTS / task / name
    dest = dest_dir / f"{task}_output.xlsx"
    edits = []
    applied = {"formulas": {}, "failures": {}}
    if formula:
        applied = pg.apply_program(formula, unit)
        for addr, value in applied["formulas"].items():
            sheet, address = addr.split("!", 1)
            edits.append({"sheet": sheet, "address": address, "formula": value})
    audit = staged.write_cells(ccf.cc.workbook_paths(task)[0], dest, edits)
    write(dest_dir / "audit.json", {"stage": "G0", "edits": edits, "translation": applied, "audit": audit})
    return {"path": str(dest), "edits": edits, "translation_failures": applied.get("failures", {}), "audit": audit}


def evaluate_rows(source_rows: list[dict], calls: list[dict]) -> list[dict]:
    by_key = {(r["meta"]["task"], r["meta"]["canonical_member"]): r for r in source_rows}
    out = []
    for rec in calls:
        task, member = rec["task"], rec["canonical_member"]
        meta = by_key[(task, member)]["meta"]
        formula = formula_from_response(rec)
        gold = staged.gold_for(task, member)
        cls = classify_formula(task, member, formula, gold)
        row = {
            "task": task, "canonical_member": member,
            "program_key": sd.program_key(next(x for x in sd.audit_rows() if x["task"] == task and x["canonical_member"] == member)),
            "gold_formula": gold, "formula": formula,
            "formula_exact": bool(ES._same(formula, gold)),
            "classification": cls,
            "mechanical_validation": mechanical_check(member, formula),
            "working_set_sha256": meta["working_set_sha256"],
            "evidence_sha256": meta["evidence_sha256"],
            "request_fidelity": rec["request_fidelity"],
            "model_failure": rec.get("failure_class") is not None,
            "truncation_class": rec.get("truncation_class"),
            "non_model_failure": rec.get("failure_class") is not None or rec.get("truncation_class") is not None,
        }
        row["end_to_end"] = end_to_end(task, member, formula)
        out.append(row)
    return out


def main() -> None:
    instr.check()
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    sources = source_records()
    manifest = {
        "arm": "G0",
        "model": MODEL,
        "display_model": DISPLAY_MODEL,
        "temperature": TEMPERATURE,
        "reasoning": REASONING,
        "retries": RETRIES,
        "max_tokens": sources[0]["source"]["request"].get("max_tokens"),
        "source_probe": str(SOURCE),
        "population": [x["meta"] for x in sources],
        "independence": {"cell_level_n": 4, "independent_program_n": 3,
                         "program_keys": sorted({sd.program_key(next(r for r in sd.audit_rows() if r["task"] == x["meta"]["task"] and r["canonical_member"] == x["meta"]["canonical_member"])) for x in sources})},
        "new_sql_calls": 0,
        "gold_in_primary_request": False,
        "request_source_is_retained_body": True,
    }
    write(OUT / "freeze.json", manifest)
    calls = []
    for source in sources:
        rec = call_one(source, key)
        calls.append(rec)
        print(json.dumps({"task": rec["task"], "member": rec["canonical_member"],
                          "status": (rec.get("parsed_response") or {}).get("status"),
                          "failure": rec.get("failure_class"), "tokens": rec.get("usage", {})}), flush=True)
    write(OUT / "primary.json", calls)
    evaluated = evaluate_rows(sources, calls)
    for task in sorted({r["task"] for r in evaluated}):
        ccf.recalculate(VARIANTS / task)
    # Score the full translated workbook variants with the same staged scorer.
    for task in sorted({r["task"] for r in evaluated}):
        paths = {r["canonical_member"]: Path(r["end_to_end"]["path"]) for r in evaluated if r["task"] == task}
        scored = staged.batched_scores(task, paths)
        for row in evaluated:
            if row["task"] != task:
                continue
            official, strict = scored[row["canonical_member"]]
            row["score"] = official
            row["strict_score"] = strict
            unit = staged.units()[(task, row["canonical_member"])]
            formulas = row["end_to_end"]["edits"]
            def gold_for_cell(cell):
                edit = ccf.gold_edit(task, tuple(cell))
                return edit["golden_payload"] if edit else None
            row["all_member_exact"] = all(
                bool(ES._same(next((x["formula"] for x in formulas if x["sheet"] == c[0] and x["address"] == sd.cc.a1(c[1], c[2])), None), gold_for_cell(c)))
                for c in unit["member_cells"]
            )
    write(OUT / "evaluated.json", evaluated)
    print(json.dumps({"output": str(OUT), "n": len(evaluated),
                      "exact_cells": sum(bool(x["formula_exact"]) for x in evaluated),
                      "non_model_failures": sum(bool(x["non_model_failure"]) for x in evaluated)}, indent=2))


if __name__ == "__main__":
    main()
