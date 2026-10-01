#!/usr/bin/env python3
"""Bounded compact evidence-delivery experiment for frozen 06_01 O3 targets.

CONTROL serializes the current full synthesis evidence from a fresh
integrity-verified lineage. TREATMENT encodes the same facts through a
compact lossless representation. The only experimental variable is evidence
representation. No retrieval, planner, scheduler, writes, LibreOffice, or
scorer execution.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "benchmark"), str(ROOT / "src"), str(ROOT / "benchmark/sweagent/formula_index/lib")]

import compact_evidence as encoding  # noqa: E402
import integrity_gate  # noqa: E402
import matched_compiled_treatment as treatment  # noqa: E402
from compiled_scheduler import synthesis_outcome  # noqa: E402
from experiment_config import AUTHORITATIVE_EXPERIMENT_CONFIG  # noqa: E402
from fingerprint import relative_fingerprint  # noqa: E402
from formula_synthesis_probe import _canonical_formula  # noqa: E402

TASK_KEY = "Financial_Model:06_01"
OBLIGATION_ID = "O3"
ARCHIVE_LIVE = integrity_gate.ARCHIVE_LIVE
AUTOPSY = ROOT / "resource_demand_autopsy"
SOURCE = integrity_gate.SOURCE
GOLD = ROOT / "benchmark-data/SpreadsheetBench-2/data/Financial_Model/spreadsheet/06_Project DigiMark/06_DigiMark_golden.xlsx"
OUT = ROOT / "compact_evidence_delivery"
RUN_ROOT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/compact-evidence-delivery"
REPORT = ROOT / "COMPACT_EVIDENCE_DELIVERY_REPORT.md"
WITNESSES = {
    "cell:s01:r47:c3": {"address": "DCF!C47", "raw_value": "0.11", "display_value": "0.11"},
    "cell:s01:r48:c3": {"address": "DCF!C48", "raw_value": "0.25", "display_value": "0.25"},
    "cell:s01:r51:c3": {"address": "DCF!C51", "raw_value": "0.15", "display_value": "0.15"},
}
PROVIDER_FAILURES = {"PROVIDER_TIMEOUT", "PROVIDER_ERROR", "MODEL_ACCESS_FAILURE", "REQUEST_IDENTITY_FAILURE", "SESSION_RESOURCE_LIMIT"}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def median(values: list[float]) -> float | None:
    clean = [x for x in values if x is not None]
    return float(statistics.median(clean)) if clean else None


def load_o3_population() -> list[dict[str, Any]]:
    manifests = read_json(AUTOPSY / "evidence_manifests.json")
    o3 = [m for m in manifests if m["session"].startswith("cell:s01:")]
    if len(o3) != 16:
        raise AssertionError(f"EXPECTED_16_O3_MANIFESTS: {len(o3)}")
    state = read_json(ARCHIVE_LIVE / "state.json")
    sessions = state["scheduler_v3"]["sessions"]
    task_ir = read_json(ARCHIVE_LIVE / "calls/001_task_ir.json")["parsed_response"]
    obligation = next(item for item in task_ir["obligations"] if item["id"] == OBLIGATION_ID)
    task = next(row for row in treatment.task_rows() if row["task_key"] == TASK_KEY)
    population = []
    for manifest in sorted(o3, key=lambda item: (int(item["session"].split(":")[2][1:]), int(item["session"].split(":")[3][1:]))):
        cell_id = manifest["session"]
        session = sessions[cell_id]["session"]
        target_meta = sessions[cell_id].get("target") or session.get("target")
        working = list(session["working_set_ids"])
        population.append({
            "cell_id": cell_id,
            "target_label": f"{target_meta['sheet']}!{target_meta['address']}",
            "sheet": target_meta["sheet"],
            "address": target_meta["address"],
            "obligation_id": target_meta.get("obligation_id") or OBLIGATION_ID,
            "archived_record_keys": list(manifest["record_keys"]),
            "archived_evidence_sha256": manifest["evidence_sha256"],
            "archived_working_set_ids": working,
            "archived_working_set_count": len(working),
            "archived_outcome": session.get("status"),
            "task_instruction": task["instruction"],
            "obligation": obligation,
        })
    return population


def gold_formulas() -> dict[str, str | None]:
    import openpyxl
    workbook = openpyxl.load_workbook(GOLD, data_only=False, read_only=True)
    try:
        sheet = workbook["DCF"]
        return {f"DCF!{col}49": (sheet[f"{col}49"].value if isinstance(sheet[f"{col}49"].value, str) and str(sheet[f"{col}49"].value).startswith("=") else None) for col in list("CDEFGHIJKLMNOPQR")}
    finally:
        workbook.close()


def ensure_fresh_lineage() -> dict[str, Any]:
    source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    lineage_dir = Path(integrity_gate.OUT) / f"fresh_lineage_{source_sha[:12]}"
    db_path = lineage_dir / "world.sqlite"
    spine_path = lineage_dir / "spine.json"
    if db_path.exists() and spine_path.exists():
        spine = read_json(spine_path)
        return {"directory": str(lineage_dir), "spine": str(spine_path), "database": str(db_path), "source_sha256": source_sha, "reused": True, "spine_object": spine}
    spine, db_path, _temporal, _counts, lineage = integrity_gate.build_fresh_lineage()
    lineage["reused"] = False
    lineage["spine_object"] = spine
    return lineage


def witness_check(evidence: dict[str, Any], working: set[str]) -> dict[str, Any]:
    rows = []
    ok = True
    for cell_id, expected in WITNESSES.items():
        present = cell_id in working or encoding.cell_fact(evidence, cell_id) is not None
        fact = encoding.cell_fact(evidence, cell_id)
        value_ok = True
        if fact is not None:
            value_ok = fact.get("raw_value") == expected["raw_value"] and fact.get("display_value") == expected["display_value"]
            if not value_ok:
                ok = False
        rows.append({
            "cell_id": cell_id,
            "address": expected["address"],
            "in_working_set": cell_id in working,
            "present_in_evidence": fact is not None,
            "required_where_present": present,
            "value_ok": value_ok if fact is not None else True,
            "observed": {k: fact.get(k) for k in ("raw_value", "display_value", "kind")} if fact else None,
        })
    return {"ok": ok, "witnesses": rows}


def build_transition(row: dict[str, Any], target: dict[str, Any], working: list[str], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "SYNTHESIS_TRANSITION": treatment.SYNTHESIS_SYSTEM,
        "RAW_TASK": row["task_instruction"],
        "TARGET": target,
        "OBLIGATION": row["obligation"],
        "WORKING_SET_COUNTS": dict(Counter(item.split(":", 1)[0] for item in working)),
        "WORKING_SET_ENTITY_IDS": working,
        "WORKING_SET_EVIDENCE": evidence,
    }


def evidence_bytes(evidence: dict[str, Any]) -> int:
    return encoding.byte_size(evidence)


def usage_fields(call: dict[str, Any]) -> dict[str, Any]:
    usage = call.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    reasoning = usage.get("reasoning_tokens")
    if reasoning is None:
        reasoning = details.get("reasoning_tokens") or prompt_details.get("reasoning_tokens")
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": reasoning,
        "provider_cost_usd": call.get("provider_cost_usd"),
        "usage_cost": usage.get("cost"),
    }


def arm_order(index_1_based: int) -> tuple[str, str]:
    return ("CONTROL", "TREATMENT") if index_1_based % 2 == 1 else ("TREATMENT", "CONTROL")


def prepare(out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or OUT
    population = load_o3_population()
    lineage = ensure_fresh_lineage()
    spine = lineage["spine_object"]
    db_path = Path(lineage["database"])
    rows = []
    excluded = []
    gold = gold_formulas()
    for row in population:
        working = list(row["archived_working_set_ids"])
        target = treatment.target_from_id(spine, row["cell_id"], TASK_KEY, OBLIGATION_ID)
        if target is None:
            excluded.append({**row, "exclusion": "TARGET_NOT_IN_FRESH_SPINE"})
            continue
        evidence = treatment.materialize_complete(db_path, set(working))
        if list(evidence.get("entity_ids") or []) != working:
            # materialize_complete sorts working; archived lists are already sorted.
            if sorted(evidence.get("entity_ids") or []) != sorted(working):
                excluded.append({**row, "exclusion": "WORKING_SET_IDENTITY_MISMATCH", "fresh_entity_id_count": len(evidence.get("entity_ids") or [])})
                continue
        compact = encoding.encode_evidence(evidence)
        decoded = encoding.decode_evidence(compact)
        comparison = encoding.factual_diff(evidence, compact)
        witnesses = witness_check(evidence, set(working))
        reconstruction_ok = comparison["equal"] and witnesses["ok"]
        if not reconstruction_ok:
            excluded.append({
                **{k: row[k] for k in ("cell_id", "target_label")},
                "exclusion": "FACTUAL_MISMATCH" if not comparison["equal"] else "WITNESS_VALUE_MISMATCH",
                "comparison": comparison,
                "witnesses": witnesses,
            })
            continue
        control_transition = build_transition(row, target, sorted(working), evidence)
        treatment_transition = build_transition(row, target, sorted(working), compact)
        control_user = json.dumps(control_transition, ensure_ascii=False, separators=(",", ":"))
        treatment_user = json.dumps(treatment_transition, ensure_ascii=False, separators=(",", ":"))
        control_body = treatment.request_body(treatment.SYNTHESIS_SYSTEM, control_user)
        treatment_body = treatment.request_body(treatment.SYNTHESIS_SYSTEM, treatment_user)
        prepared = {
            "cell_id": row["cell_id"],
            "target_label": row["target_label"],
            "sheet": row["sheet"],
            "address": row["address"],
            "target": target,
            "obligation_id": OBLIGATION_ID,
            "task_instruction": row["task_instruction"],
            "obligation": row["obligation"],
            "working_set_ids": sorted(working),
            "gold_formula": gold.get(row["target_label"]),
            "archived_working_set_count": row["archived_working_set_count"],
            "archived_outcome": row["archived_outcome"],
            "fresh_entity_id_count": len(evidence.get("entity_ids") or []),
            "fresh_record_count": encoding.canonical_facts(evidence)["record_count"],
            "witnesses": witnesses,
            "equivalence": comparison,
            "canonical_sha256": comparison["control_canonical_sha256"],
            "control": {
                "evidence_sha256": encoding.digest(evidence),
                "evidence_bytes": evidence_bytes(evidence),
                "user_bytes": len(control_user.encode()),
                "request_sha256": treatment.digest(control_body),
                "request_bytes": encoding.byte_size(control_body),
            },
            "treatment": {
                "evidence_sha256": encoding.digest(compact),
                "evidence_bytes": evidence_bytes(compact),
                "user_bytes": len(treatment_user.encode()),
                "request_sha256": treatment.digest(treatment_body),
                "request_bytes": encoding.byte_size(treatment_body),
            },
            "decoded_matches_control": encoding.factual_diff(evidence, decoded)["equal"],
        }
        if not prepared["decoded_matches_control"]:
            excluded.append({**{k: prepared[k] for k in ("cell_id", "target_label")}, "exclusion": "DECODER_ROUNDTRIP_FAILURE"})
            continue
        target_dir = out_dir / "targets" / row["cell_id"].replace(":", "_")
        write_json(target_dir / "canonical_facts.json", {
            "cell_id": row["cell_id"],
            "canonical_sha256": prepared["canonical_sha256"],
            "record_count": prepared["fresh_record_count"],
            "entity_id_count": prepared["fresh_entity_id_count"],
            "equivalence": comparison,
        })
        write_json(target_dir / "control_request_identity.json", {
            "request_sha256": prepared["control"]["request_sha256"],
            "evidence_sha256": prepared["control"]["evidence_sha256"],
            "evidence_bytes": prepared["control"]["evidence_bytes"],
            "user_bytes": prepared["control"]["user_bytes"],
            "request_bytes": prepared["control"]["request_bytes"],
        })
        write_json(target_dir / "treatment_request_identity.json", {
            "request_sha256": prepared["treatment"]["request_sha256"],
            "evidence_sha256": prepared["treatment"]["evidence_sha256"],
            "evidence_bytes": prepared["treatment"]["evidence_bytes"],
            "user_bytes": prepared["treatment"]["user_bytes"],
            "request_bytes": prepared["treatment"]["request_bytes"],
        })
        write_json(target_dir / "control_evidence.json", evidence)
        write_json(target_dir / "treatment_evidence.json", compact)
        write_json(target_dir / "target.json", {
            "target": target,
            "working_set_ids": sorted(working),
            "task_instruction": row["task_instruction"],
            "obligation": row["obligation"],
            "gold_formula": prepared["gold_formula"],
        })
        rows.append(prepared)
    mismatch = any(item.get("exclusion") in {"FACTUAL_MISMATCH", "DECODER_ROUNDTRIP_FAILURE", "WITNESS_VALUE_MISMATCH"} for item in excluded)
    result = {
        "status": "PASS" if len(rows) == 16 and not excluded else ("EVIDENCE_EQUIVALENCE_DEFECT" if mismatch else "RECONSTRUCTION_EXCLUSIONS"),
        "authoritative_config": AUTHORITATIVE_EXPERIMENT_CONFIG.metadata(),
        "lineage": {k: v for k, v in lineage.items() if k != "spine_object"},
        "population_requested": 16,
        "included": len(rows),
        "excluded": excluded,
        "targets": rows,
    }
    if result["status"] != "PASS":
        result["blocks_live"] = True
    else:
        result["blocks_live"] = False
    write_json(out_dir / "equivalence.json", result)
    return result


def semantic_row(call: dict[str, Any], prepared: dict[str, Any], spine: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    failure = call.get("failure_class")
    parsed = call.get("parsed_response") if not failure else None
    session = {"synthesis": {"parsed": parsed}, "failure_class": failure, "calls": [call]}
    outcome = synthesis_outcome(session)
    formula = parsed.get("formula") if isinstance(parsed, dict) else None
    status = parsed.get("status") if isinstance(parsed, dict) else None
    validation = {}
    fingerprint = None
    if outcome == "PROPOSED" and isinstance(formula, str):
        validation = treatment.validate_formula(TASK_KEY, prepared["target"], formula, cache, spine)
        try:
            fp = relative_fingerprint(formula, prepared["target"]["col"], prepared["target"]["row"], sheet=prepared["target"]["sheet"])
            fingerprint = None if getattr(fp, "opaque", False) else getattr(fp, "eq_id", None)
        except Exception as exc:
            fingerprint = f"ERROR:{type(exc).__name__}"
    gold = prepared.get("gold_formula")
    exact = _canonical_formula(formula) == _canonical_formula(gold) if formula and gold else None
    gold_fp = None
    if gold:
        try:
            fp = relative_fingerprint(gold, prepared["target"]["col"], prepared["target"]["row"], sheet=prepared["target"]["sheet"])
            gold_fp = None if getattr(fp, "opaque", False) else getattr(fp, "eq_id", None)
        except Exception:
            gold_fp = None
    fingerprint_match = bool(fingerprint and gold_fp and fingerprint == gold_fp)
    invalid_ref = bool(validation.get("invalid_sheet") or validation.get("invalid_address") or validation.get("unsupported_external"))
    hard = validation.get("hard_verifier_result")
    proposed = outcome == "PROPOSED" and bool(formula)
    hard_accept = proposed and hard == "HARD_ACCEPT" and not invalid_ref
    return {
        "outcome": outcome,
        "proposal_or_abstention": status if isinstance(parsed, dict) else None,
        "formula": formula,
        "invalid_reference": invalid_ref,
        "hard_verifier_result": hard,
        "parser_ok": validation.get("parser_ok"),
        "source_reference_valid": proposed and validation.get("parser_ok") and not invalid_ref,
        "exact_formula_match": exact,
        "relative_fingerprint": fingerprint,
        "gold_formula": gold,
        "gold_fingerprint_match": fingerprint_match if gold else None,
        "hard_accept_proposal": hard_accept,
        "provider_failure": failure in PROVIDER_FAILURES if failure else False,
        "failure_class": failure,
        "identity_failure": bool(call.get("identity_failure") or failure == "REQUEST_IDENTITY_FAILURE"),
    }


def pair_category(control: dict[str, Any], treatment_row: dict[str, Any]) -> str:
    if control["provider_failure"] or treatment_row["provider_failure"] or control["identity_failure"] or treatment_row["identity_failure"]:
        return "provider-censored pair"
    c_ok, t_ok = control["hard_accept_proposal"], treatment_row["hard_accept_proposal"]
    if c_ok and t_ok:
        if control.get("formula") == treatment_row.get("formula"):
            return "both semantically correct"
        return "both semantically correct"
    if c_ok and not t_ok:
        return "control correct / treatment wrong"
    if t_ok and not c_ok:
        return "treatment correct / control wrong"
    if control.get("formula") == treatment_row.get("formula") and control.get("outcome") == treatment_row.get("outcome"):
        return "both wrong but same error"
    return "both wrong differently"


def live_call(prepared: dict[str, Any], arm: str, evidence: dict[str, Any], state: dict[str, Any], call_dir: Path) -> dict[str, Any]:
    working = list(prepared["working_set_ids"])
    target = prepared["target"]
    row = {"task_instruction": prepared["task_instruction"], "obligation": prepared["obligation"]}
    user = json.dumps(build_transition(row, target, working, evidence), ensure_ascii=False, separators=(",", ":"))
    started = time.perf_counter()
    call = treatment.model_call(TASK_KEY, "synthesis", treatment.SYNTHESIS_SYSTEM, user, state, stub=False, evidence_hash=encoding.digest(evidence), working_hash=treatment.digest(working))
    latency = time.perf_counter() - started
    call["latency_seconds"] = latency
    call["arm"] = arm
    call["cell_id"] = prepared["cell_id"]
    call["target_label"] = prepared["target_label"]
    call["serialized_evidence_bytes"] = evidence_bytes(evidence)
    call["total_request_bytes"] = encoding.byte_size(call["request_body"])
    expected = prepared["control" if arm == "CONTROL" else "treatment"]["request_sha256"]
    if call.get("request_sha256") != expected:
        raise RuntimeError(f"REQUEST_HASH_DRIFT[{arm}:{prepared['cell_id']}]: expected {expected} got {call.get('request_sha256')}")
    if call.get("declared_reasoning") != "high" or call.get("request_reasoning") != "high":
        raise RuntimeError(f"REASONING_NOT_HIGH[{arm}:{prepared['cell_id']}]: {call.get('declared_reasoning')} {call.get('request_reasoning')}")
    path = call_dir / f"{int(call['call_index_within_task']):03d}_{arm.lower()}_{prepared['cell_id'].replace(':', '_')}.json"
    write_json(path, call)
    return call


def run_live(prepared: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or OUT
    if prepared.get("blocks_live") or prepared.get("status") != "PASS":
        result = {"status": "EVIDENCE_EQUIVALENCE_DEFECT", "provider_calls": 0, "reason": prepared.get("status")}
        write_json(out_dir / "live.json", result)
        return result
    if AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning != "high":
        raise RuntimeError(f"REASONING_MUST_BE_HIGH: {AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning}")
    if AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning == "max":
        raise RuntimeError("REASONING_MAX_FORBIDDEN")
    treatment.configure_runtime(max_model_calls=40, max_cost_usd=25.0)
    lineage = ensure_fresh_lineage()
    spine = lineage["spine_object"]
    cache: dict[str, Any] = {}
    state = {"model_call_count": 0, "provider_cost_usd": 0.0}
    call_dir = out_dir / "calls"
    call_dir.mkdir(parents=True, exist_ok=True)
    ledger = []
    pairs = []
    for index, row in enumerate(prepared["targets"], start=1):
        order = arm_order(index)
        target_dir = out_dir / "targets" / row["cell_id"].replace(":", "_")
        evidence_by_arm = {
            "CONTROL": read_json(target_dir / "control_evidence.json"),
            "TREATMENT": read_json(target_dir / "treatment_evidence.json"),
        }
        calls = {}
        for arm in order:
            existing = sorted(call_dir.glob(f"*_{arm.lower()}_{row['cell_id'].replace(':', '_')}.json"))
            if existing:
                call = read_json(existing[0])
                if call.get("failure_class") in PROVIDER_FAILURES or call.get("raw_response_body") is not None or call.get("parsed_response") is not None:
                    state["model_call_count"] = max(int(state.get("model_call_count") or 0), int(call.get("call_index_within_task") or 0))
                    state["provider_cost_usd"] = float(state.get("provider_cost_usd") or 0) + float(call.get("provider_cost_usd") or 0)
                    calls[arm] = call
                    continue
            calls[arm] = live_call(row, arm, evidence_by_arm[arm], state, call_dir)
            print(
                f"{row['target_label']} {arm} index={calls[arm].get('call_index_within_task')} "
                f"failure={calls[arm].get('failure_class')} "
                f"prompt={((calls[arm].get('usage') or {}).get('prompt_tokens'))} "
                f"cost={calls[arm].get('provider_cost_usd')} "
                f"latency={round(float(calls[arm].get('latency_seconds') or 0), 1)}s",
                flush=True,
            )
        scored = {arm: {**usage_fields(calls[arm]), **semantic_row(calls[arm], row, spine, cache), "latency_seconds": calls[arm].get("latency_seconds"), "request_sha256": calls[arm].get("request_sha256"), "response_model": calls[arm].get("response_model"), "declared_reasoning": calls[arm].get("declared_reasoning"), "request_reasoning": calls[arm].get("request_reasoning"), "serialized_evidence_bytes": calls[arm].get("serialized_evidence_bytes"), "total_request_bytes": calls[arm].get("total_request_bytes"), "finish_reason": calls[arm].get("finish_reason")} for arm in ("CONTROL", "TREATMENT")}
        category = pair_category(scored["CONTROL"], scored["TREATMENT"])
        pair = {
            "cell_id": row["cell_id"],
            "target_label": row["target_label"],
            "call_order": list(order),
            "canonical_sha256": row["canonical_sha256"],
            "control_request_sha256": row["control"]["request_sha256"],
            "treatment_request_sha256": row["treatment"]["request_sha256"],
            "category": category,
            "CONTROL": scored["CONTROL"],
            "TREATMENT": scored["TREATMENT"],
        }
        pairs.append(pair)
        for arm in ("CONTROL", "TREATMENT"):
            ledger.append({
                "cell_id": row["cell_id"],
                "target_label": row["target_label"],
                "arm": arm,
                "call_index": calls[arm].get("call_index_within_task"),
                "request_sha256": calls[arm].get("request_sha256"),
                "declared_model": calls[arm].get("declared_model"),
                "request_model": calls[arm].get("request_model"),
                "response_model": calls[arm].get("response_model"),
                "declared_reasoning": calls[arm].get("declared_reasoning"),
                "request_reasoning": calls[arm].get("request_reasoning"),
                **scored[arm],
            })
        write_json(target_dir / "pair.json", pair)
    result = {"status": "LIVE_COMPLETE", "provider_calls": len(ledger), "pairs": pairs, "ledger": ledger, "state": {"model_call_count": state["model_call_count"], "provider_cost_usd": state["provider_cost_usd"]}}
    write_json(out_dir / "live.json", result)
    write_json(out_dir / "ledger.json", ledger)
    return result


def _num(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def aggregate(prepared: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    pairs = live.get("pairs") or []
    control_prompt, treatment_prompt = [], []
    control_bytes, treatment_bytes = [], []
    control_cost, treatment_cost = [], []
    control_fail = treatment_fail = 0
    for pair in pairs:
        c, t = pair["CONTROL"], pair["TREATMENT"]
        if _num(c, "prompt_tokens") is not None:
            control_prompt.append(_num(c, "prompt_tokens"))
        if _num(t, "prompt_tokens") is not None:
            treatment_prompt.append(_num(t, "prompt_tokens"))
        control_bytes.append(_num(c, "total_request_bytes") or 0)
        treatment_bytes.append(_num(t, "total_request_bytes") or 0)
        control_cost.append(_num(c, "provider_cost_usd") or 0)
        treatment_cost.append(_num(t, "provider_cost_usd") or 0)
        control_fail += int(bool(c.get("provider_failure") or c.get("identity_failure")))
        treatment_fail += int(bool(t.get("provider_failure") or t.get("identity_failure")))
    prompt_pairs = [(pair["CONTROL"].get("prompt_tokens"), pair["TREATMENT"].get("prompt_tokens")) for pair in pairs if isinstance(pair["CONTROL"].get("prompt_tokens"), (int, float)) and isinstance(pair["TREATMENT"].get("prompt_tokens"), (int, float))]
    byte_pairs = [(pair["CONTROL"].get("total_request_bytes") or 0, pair["TREATMENT"].get("total_request_bytes") or 0) for pair in pairs]
    prompt_reductions = [c - t for c, t in prompt_pairs]
    byte_reductions = [c - t for c, t in byte_pairs]
    categories = dict(Counter(pair["category"] for pair in pairs))
    treatment_loss = categories.get("control correct / treatment wrong", 0)
    resource = {
        "pairs_with_prompt_tokens": len(prompt_pairs),
        "median_control_prompt_tokens": median(control_prompt),
        "median_treatment_prompt_tokens": median(treatment_prompt),
        "total_control_prompt_tokens": sum(control_prompt) if control_prompt else None,
        "total_treatment_prompt_tokens": sum(treatment_prompt) if treatment_prompt else None,
        "median_prompt_token_reduction": median(prompt_reductions),
        "total_prompt_token_reduction": sum(prompt_reductions) if prompt_reductions else None,
        "median_control_request_bytes": median(control_bytes),
        "median_treatment_request_bytes": median(treatment_bytes),
        "total_control_request_bytes": sum(control_bytes),
        "total_treatment_request_bytes": sum(treatment_bytes),
        "median_request_byte_reduction": median(byte_reductions),
        "total_request_byte_reduction": sum(byte_reductions),
        "total_control_cost_usd": sum(control_cost),
        "total_treatment_cost_usd": sum(treatment_cost),
        "cost_difference_usd": sum(treatment_cost) - sum(control_cost),
        "control_provider_failures": control_fail,
        "treatment_provider_failures": treatment_fail,
    }
    semantic = {
        "categories": categories,
        "control_hard_accept": sum(pair["CONTROL"]["hard_accept_proposal"] for pair in pairs),
        "treatment_hard_accept": sum(pair["TREATMENT"]["hard_accept_proposal"] for pair in pairs),
        "treatment_specific_loss": treatment_loss,
        "control_gold_exact": sum(pair["CONTROL"].get("exact_formula_match") is True for pair in pairs),
        "treatment_gold_exact": sum(pair["TREATMENT"].get("exact_formula_match") is True for pair in pairs),
    }
    return {"resource": resource, "semantic": semantic, "pair_count": len(pairs)}


def verdict_of(prepared: dict[str, Any], live: dict[str, Any], summary: dict[str, Any] | None) -> str:
    if prepared.get("status") != "PASS":
        return "EVIDENCE_EQUIVALENCE_DEFECT"
    if not live or live.get("status") in (None, "EVIDENCE_EQUIVALENCE_DEFECT"):
        if live is None:
            return "EQUIVALENCE_PASSED_OFFLINE"
        return "EVIDENCE_EQUIVALENCE_DEFECT"
    resource = summary["resource"]
    semantic = summary["semantic"]
    n = summary["pair_count"]
    censored = semantic["categories"].get("provider-censored pair", 0)
    prompt_pairs = resource["pairs_with_prompt_tokens"]
    if n and censored == n:
        return "PROVIDER_CENSORED"
    token_gain = False
    byte_gain = False
    if resource["total_prompt_token_reduction"] is not None and resource["total_control_prompt_tokens"]:
        token_gain = resource["total_prompt_token_reduction"] / resource["total_control_prompt_tokens"] >= 0.15
    if resource["total_control_request_bytes"]:
        byte_gain = resource["total_request_byte_reduction"] / resource["total_control_request_bytes"] >= 0.15
    if prompt_pairs:
        material = token_gain
    else:
        material = byte_gain
        if censored >= max(1, n // 2):
            return "PROVIDER_CENSORED"
    if semantic["treatment_specific_loss"] > 0:
        return "COMPACT_ENCODING_REDUCES_COST_BUT_SEMANTIC_RISK" if material else "COMPACT_ENCODING_REDUCES_COST_BUT_SEMANTIC_RISK"
    if not material:
        return "COMPACT_ENCODING_NO_RESOURCE_GAIN"
    interpretable = n - censored
    if interpretable < 4 and censored:
        return "PROVIDER_CENSORED"
    return "COMPACT_EVIDENCE_DELIVERY_EARNED"


def envelope(summary: dict[str, Any] | None, verdict: str) -> dict[str, Any]:
    autopsy = read_json(AUTOPSY / "summary.json") if (AUTOPSY / "summary.json").exists() else {}
    frontend = ((autopsy.get("attribution") or {}).get("exclusive") or {}).get("successful_frontend") or {}
    retrieval = ((autopsy.get("attribution") or {}).get("exclusive") or {}).get("retained_successful_retrieval") or {}
    synthesis_cost = (summary or {}).get("resource", {}).get("total_treatment_cost_usd") if verdict == "COMPACT_EVIDENCE_DELIVERY_EARNED" else (summary or {}).get("resource", {}).get("total_control_cost_usd")
    n_synth = (summary or {}).get("pair_count") or 0
    per_synth = (synthesis_cost / n_synth) if summary and n_synth and synthesis_cost is not None else None
    control_failures = (summary or {}).get("resource", {}).get("control_provider_failures")
    treatment_failures = (summary or {}).get("resource", {}).get("treatment_provider_failures")
    proposed_calls = 60
    proposed_cost = 4.0
    if per_synth:
        # Frontend ~8, retrieval empirically ~5 per synthesis historically on this task,
        # but the next envelope is not fitted to finish 06_01. It is a prospective cap
        # that can complete a small official-score slice if compact synthesis holds.
        proposed_calls = 40
        proposed_cost = round(0.05 + 8 * 0.04 + 20 * (per_synth + 0.04), 2)
        proposed_cost = max(2.5, min(proposed_cost, 6.0))
    return {
        "model": AUTHORITATIVE_EXPERIMENT_CONFIG.model,
        "reasoning": AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning,
        "proposed_max_model_calls": proposed_calls,
        "proposed_cost_usd": proposed_cost,
        "per_target_synthesis_cost_usd": per_synth,
        "historical_frontend_cost_usd": frontend.get("cost") or 0.035686,
        "historical_retrieval_calls": 101,
        "historical_retrieval_cost_usd": retrieval.get("cost") or 0.755029,
        "observed_control_provider_failures": control_failures,
        "observed_treatment_provider_failures": treatment_failures,
        "what_would_censor": [
            "provider timeouts at the 180-second synthesis ceiling",
            "identity mismatch (run invalid)",
            "task cost cap if retrieval is still repeated per target",
            "call cap if a task still materializes an independent synthesis session per residual cell",
        ],
        "not_used": "historical 150-call 06_01 cap",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def render_report(prepared: dict[str, Any], live: dict[str, Any] | None, summary: dict[str, Any] | None, verdict: str, env: dict[str, Any]) -> str:
    resource = (summary or {}).get("resource") or {}
    semantic = (summary or {}).get("semantic") or {}
    lines = [
        "# Compact Evidence Delivery",
        "",
        f"Verdict: `{verdict}`",
        "",
        "This is an evidence-transport experiment on frozen `Financial_Model:06_01` O3 targets. Semantic architecture was held fixed. The only experimental variable is synthesis-evidence representation. No retrieval, planner, scheduler, writes, LibreOffice, or official scorer ran.",
        "",
        "## Configuration",
        "",
        f"- model: `{AUTHORITATIVE_EXPERIMENT_CONFIG.model}`",
        f"- reasoning: `{AUTHORITATIVE_EXPERIMENT_CONFIG.reasoning}` (not `max`)",
        f"- temperature: `{AUTHORITATIVE_EXPERIMENT_CONFIG.temperature}`",
        f"- top-p: `{AUTHORITATIVE_EXPERIMENT_CONFIG.top_p}`",
        "- constructor: `matched_compiled_treatment.request_body` with fail-closed `experiment_config.request_identity`",
        "",
        "## Population and equivalence",
        "",
        f"Requested 16 frozen O3 targets. Included: **{prepared.get('included')}**. Excluded before live calls: **{len(prepared.get('excluded') or [])}**.",
        "",
    ]
    if prepared.get("excluded"):
        lines += ["| Target | Exclusion |", "|---|---|"]
        for item in prepared["excluded"]:
            lines.append(f"| {item.get('target_label') or item.get('cell_id')} | {item.get('exclusion')} |")
        lines.append("")
    lines += [
        "CONTROL is the current full `materialize_complete` serialization from the fresh integrity-verified source → spine → SQLite lineage. TREATMENT is `columnar_dict_v1`, a deterministic column-major dictionary encoding of the same tables. A decoder/canonicalizer required `canonical_facts(CONTROL) == canonical_facts(TREATMENT)` before any provider call.",
        "",
        "Witness values in rematerialized packets, where those cells occur:",
        "",
        "- `DCF!C47 = 0.11`",
        "- `DCF!C48 = 0.25`",
        "- `DCF!C51 = 0.15`",
        "",
        "## Resource",
        "",
        "| Metric | CONTROL | TREATMENT | Reduction |",
        "|---|---:|---:|---:|",
        f"| Median prompt tokens | {resource.get('median_control_prompt_tokens')} | {resource.get('median_treatment_prompt_tokens')} | {resource.get('median_prompt_token_reduction')} |",
        f"| Total prompt tokens | {resource.get('total_control_prompt_tokens')} | {resource.get('total_treatment_prompt_tokens')} | {resource.get('total_prompt_token_reduction')} |",
        f"| Median request bytes | {resource.get('median_control_request_bytes')} | {resource.get('median_treatment_request_bytes')} | {resource.get('median_request_byte_reduction')} |",
        f"| Total request bytes | {resource.get('total_control_request_bytes')} | {resource.get('total_treatment_request_bytes')} | {resource.get('total_request_byte_reduction')} |",
        f"| Cost USD | {resource.get('total_control_cost_usd')} | {resource.get('total_treatment_cost_usd')} | {resource.get('cost_difference_usd')} |",
        f"| Provider failures | {resource.get('control_provider_failures')} | {resource.get('treatment_provider_failures')} | |",
        "",
        "Token savings are taken from provider-reported prompt tokens when both arms reported them. Byte reduction is not treated as a token claim in that case.",
        "",
        "## Semantic preservation",
        "",
        f"Paired categories: `{json.dumps(semantic.get('categories') or {}, ensure_ascii=False)}`.",
        "",
        f"Hard-accept proposals: CONTROL {semantic.get('control_hard_accept')}, TREATMENT {semantic.get('treatment_hard_accept')}. Treatment-specific loss of otherwise-correct synthesis: **{semantic.get('treatment_specific_loss')}**. Gold exact matches are diagnostic only and were never sent to either arm.",
        "",
        "| Target | Order | Category | CONTROL | TREATMENT |",
        "|---|---|---|---|---|",
    ]
    for pair in (live or {}).get("pairs") or []:
        c, t = pair["CONTROL"], pair["TREATMENT"]
        lines.append(
            f"| {pair['target_label']} | {' → '.join(pair['call_order'])} | {pair['category']} | "
            f"{c.get('outcome')} `{c.get('formula')}` hard={c.get('hard_verifier_result')} gold={c.get('exact_formula_match')} | "
            f"{t.get('outcome')} `{t.get('formula')}` hard={t.get('hard_verifier_result')} gold={t.get('exact_formula_match')} |"
        )
    lines += [
        "",
        "## Prospective envelope",
        "",
        f"Proposed next-benchmark envelope: **{env.get('proposed_max_model_calls')} model calls** and **${env.get('proposed_cost_usd')}**, GLM 5.3 Flash / `{env.get('reasoning')}`. This is not the historical 150-call 06_01 cap and is not fitted so that historical residual cells finish.",
        "",
        "It would still censor a task that repeats an independent full synthesis session for every residual cell, or that spends the 180-second synthesis timeout on uncompressed packets. Provider failures remain provider failures, not semantic demand.",
        "",
        "## Artifacts",
        "",
        "- `compact_evidence_delivery/equivalence.json`",
        "- `compact_evidence_delivery/live.json`",
        "- `compact_evidence_delivery/ledger.json`",
        "- `compact_evidence_delivery/pairs.csv`",
        "- `compact_evidence_delivery/targets/*/canonical_facts.json`",
        "- `benchmark/compact_evidence_delivery.py`",
        "",
        "No FM20, GPT model swap, old-harness comparison, or published-control rerun was launched.",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(prepared: dict[str, Any], live: dict[str, Any] | None) -> dict[str, Any]:
    summary = aggregate(prepared, live or {}) if live and live.get("pairs") else None
    verdict = verdict_of(prepared, live or {}, summary)
    env = envelope(summary, verdict)
    OUT.mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    csv_rows = []
    for pair in (live or {}).get("pairs") or []:
        csv_rows.append({
            "cell_id": pair["cell_id"],
            "target": pair["target_label"],
            "category": pair["category"],
            "control_request_sha256": pair["control_request_sha256"],
            "treatment_request_sha256": pair["treatment_request_sha256"],
            "canonical_sha256": pair["canonical_sha256"],
            "control_formula": pair["CONTROL"].get("formula"),
            "treatment_formula": pair["TREATMENT"].get("formula"),
            "control_outcome": pair["CONTROL"].get("outcome"),
            "treatment_outcome": pair["TREATMENT"].get("outcome"),
            "control_prompt_tokens": pair["CONTROL"].get("prompt_tokens"),
            "treatment_prompt_tokens": pair["TREATMENT"].get("prompt_tokens"),
            "control_request_bytes": pair["CONTROL"].get("total_request_bytes"),
            "treatment_request_bytes": pair["TREATMENT"].get("total_request_bytes"),
            "control_cost_usd": pair["CONTROL"].get("provider_cost_usd"),
            "treatment_cost_usd": pair["TREATMENT"].get("provider_cost_usd"),
            "control_hard_accept": pair["CONTROL"].get("hard_accept_proposal"),
            "treatment_hard_accept": pair["TREATMENT"].get("hard_accept_proposal"),
            "control_gold_exact": pair["CONTROL"].get("exact_formula_match"),
            "treatment_gold_exact": pair["TREATMENT"].get("exact_formula_match"),
        })
    write_csv(OUT / "pairs.csv", csv_rows)
    write_json(OUT / "summary.json", {"verdict": verdict, "summary": summary, "envelope": env, "equivalence_status": prepared.get("status")})
    write_json(RUN_ROOT / "summary.json", {"verdict": verdict, "summary": summary, "envelope": env})
    REPORT.write_text(render_report(prepared, live, summary, verdict, env), encoding="utf-8")
    return {"verdict": verdict, "summary": summary, "envelope": env}


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    prepared = prepare(OUT)
    live = None
    if not args.offline_only and prepared.get("status") == "PASS":
        live = run_live(prepared, OUT)
    elif not args.offline_only:
        live = {"status": "EVIDENCE_EQUIVALENCE_DEFECT", "provider_calls": 0, "pairs": []}
        write_json(OUT / "live.json", live)
    result = write_outputs(prepared, live)
    result["equivalence"] = {"status": prepared.get("status"), "included": prepared.get("included"), "excluded": len(prepared.get("excluded") or [])}
    result["live_status"] = None if live is None else live.get("status")
    print(json.dumps({"verdict": result["verdict"], "equivalence": result["equivalence"], "live_status": result["live_status"]}, indent=2))
    return result


if __name__ == "__main__":
    main()
