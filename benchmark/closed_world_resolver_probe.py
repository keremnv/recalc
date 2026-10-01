#!/usr/bin/env python3
"""Closed-world model resolution over frozen temporal-closure grounding packets.

ORACLE TASK_OBLIGATION_SHAPE_V1. No parser composition, formula synthesis,
workbook edits, retrieval changes, or V1 edits. Goldens are evaluator labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

from closed_world_resolver import (  # noqa: E402
    COMPATIBILITY_RULES,
    LAYERS,
    RESOLVER_PROMPT,
    RESOLVER_SCHEMA,
    aggregate_scores,
    associated_gold,
    baseline_exact_match,
    baseline_keep_all,
    classify_eligibility,
    classify_output,
    compare_models,
    evidence_available,
    formula_synthesis_leakage,
    packet_callable,
    validate_resolution,
)
from task_obligation_compile import extract_json_object  # noqa: E402
from task_obligation_shape import family_of, is_semantic_change  # noqa: E402
from temporal_spine import overlay_periods  # noqa: E402
from workbook_grounding import (  # noqa: E402
    field_text,
    project_obligation,
    token_estimate,
)
from workbook_grounding_probe import (  # noqa: E402
    ENV_FILE,
    load_dotenv,
    _delta_by_task,
    _load_spine,
    _oracle_by_task,
    _split_map,
    _tasks,
    spine_path,
)

COORDS = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-closure-probe/coords"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/closed-world-resolver-probe"
)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CONTEXT_TOKEN_LIMIT = 80_000
MODELS = {
    "gpt": {
        "id": "openai/gpt-5.6-sol",
        "label": "GPT-5.6 Sol",
        "reasoning": "medium",
        "temperature": 0.0,
        "max_tokens": 768,
    },
    "glm": {
        "id": "z-ai/glm-5.3-flash",
        "label": "GLM 5.3 Flash",
        "reasoning": "low",
        "temperature": 0.0,
        "max_tokens": 8192,
    },
}
KNOWN = [
    {"id": "K6", "task": "04_05", "symbol": "total growth rates"},
    {"id": "K163", "task": "09_05", "symbol": "Other Long-Term Assets"},
    {"id": "L163", "task": "09_05", "symbol": "Other Long-Term Assets"},
    {"id": "D10", "task": "14_05", "symbol": "effective tax rate"},
    {"id": "H41", "task": "20_04", "symbol": "days-based linkage"},
    {"id": "J31", "task": "14_05", "symbol": "Total Revenue"},
    {"id": "J46", "task": "08_01", "symbol": "Receivables"},
    {"id": "AF66", "task": "08_01", "symbol": "30%"},
    {"id": "AG66", "task": "08_01", "symbol": "30%"},
    {"id": "K104", "task": "17_03", "symbol": "percentage of Revenue"},
    {"id": "Y39", "task": "15_04", "symbol": "EPS Growth"},
    {"id": "Y40", "task": "15_04", "symbol": "EPS Growth"},
]


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def cmd_freeze() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    prompt_path = OUT / "resolver_prompt.txt"
    if prompt_path.exists() and prompt_path.read_text() != RESOLVER_PROMPT:
        raise SystemExit("Refusing to overwrite a frozen resolver prompt.")
    prompt_path.write_text(RESOLVER_PROMPT)
    schema_path = _write("resolver_schema.json", RESOLVER_SCHEMA)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "prompt_sha256": hashlib.sha256(RESOLVER_PROMPT.encode()).hexdigest(),
        "prompt_len": len(RESOLVER_PROMPT),
        "schema_path": str(schema_path),
        "compatibility_rules": COMPATIBILITY_RULES,
        "models": MODELS,
        "strict_scope": True,
        "oracle": "TASK_OBLIGATION_SHAPE_V1",
        "coords": str(COORDS),
        "contains_spreadsheetbench_examples": False,
        "tuned_on_outputs": False,
        "golden_used_in_prompt": False,
    }
    path = _write("freeze.json", payload)
    print(f"FREEZE {path}", flush=True)
    return payload


def render_resolver_packet(packet: dict[str, Any]) -> str:
    def slim_hits(hits: list[dict[str, Any]], extra: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        keys = ("id", "cell_id", "row_id", "col_id", "sheet_id", "text", "address", "rules") + extra
        return [{k: h[k] for k in keys if k in h} for h in hits]

    slim = {
        "obligation_id": packet["obligation_id"],
        "fields": packet["fields"],
        "locus_candidates": packet.get("locus") or [],
        "subject_candidates": slim_hits(
            packet.get("subject") or [],
            extra=("neighbor_left", "neighbor_right"),
        ),
        "scope_candidates": slim_hits(
            packet.get("scope") or [],
            extra=("period_key", "header_text", "axis", "period"),
        ),
        "source_candidates": slim_hits(packet.get("source") or []),
        "target_cell_ids": list(packet.get("target_cell_ids") or []),
        "formula_class_facts": (packet.get("formula_class_facts") or [])[:40],
        "dependency_facts": (packet.get("dependency_facts") or [])[:40],
        "counts": packet.get("counts"),
    }
    return json.dumps(slim, ensure_ascii=False)


def _overlay_spine(task_id: str) -> dict[str, Any] | None:
    if not spine_path(task_id).exists():
        return None
    spine = _load_spine(task_id)
    coords_path = COORDS / f"{task_id}.json"
    if coords_path.exists():
        compiled = json.loads(coords_path.read_text())
        if compiled.get("readable"):
            spine = overlay_periods(spine, compiled)
    return spine


def cmd_packets(*, limit: int | None = None) -> dict[str, Any]:
    cmd_freeze()
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    split = _split_map()
    rows = []
    tasks = _tasks()
    if limit is not None:
        tasks = tasks[:limit]
    t0 = time.perf_counter()
    for task in tasks:
        tid = task["id"]
        print(f"PACKET {tid}", flush=True)
        spine = _overlay_spine(tid)
        o_row = oracle.get(tid)
        d_row = delta.get(tid)
        if not spine or not spine.get("readable") or not o_row:
            rows.append(
                {
                    "task": tid,
                    "split": split.get(family_of(tid)),
                    "readable": bool(spine and spine.get("readable")),
                    "n_obligations": 0,
                    "error": None if spine and spine.get("readable") else "unreadable_or_missing",
                }
            )
            continue
        semantic = [c for c in (d_row or {}).get("changes") or [] if is_semantic_change(c)]
        for ob in o_row["obligations"]:
            packet = project_obligation(spine, ob, strict_scope=True)
            rendered = render_resolver_packet(packet)
            tokens = token_estimate(rendered)
            gold_ents, matched, refs = associated_gold(spine, ob, packet, semantic)
            elig = classify_eligibility(packet, ob, gold_ents, ref_cells=refs)
            job_id = f"{tid}:{ob['id']}"
            rec = {
                "job_id": job_id,
                "task": tid,
                "split": split.get(family_of(tid)),
                "family": family_of(tid),
                "obligation_id": ob["id"],
                "fields": packet["fields"],
                "counts": packet["counts"],
                "packet_tokens": tokens,
                "context_ok": tokens <= CONTEXT_TOKEN_LIMIT,
                "callable": packet_callable(elig) and tokens <= CONTEXT_TOKEN_LIMIT,
                "eligibility": {k: {kk: vv for kk, vv in v.items() if kk != "input_ids"} for k, v in elig.items()},
                "input_ids": {k: v["input_ids"] for k, v in elig.items()},
                "gold_ids": {k: v["gold_ids"] for k, v in elig.items()},
                "coambiguous_ids": {k: v["coambiguous_ids"] for k, v in elig.items()},
                "n_gold_changes": len(matched),
                "evidence_available": evidence_available(packet),
                "golden_used": False,
            }
            dest = OUT / "packets" / f"{job_id.replace(':', '_')}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            slim_packet = {
                "obligation_id": packet["obligation_id"],
                "fields": packet["fields"],
                "locus": packet["locus"],
                "subject": packet["subject"],
                "scope": packet["scope"],
                "source": packet["source"],
                "target_cell_ids": packet["target_cell_ids"],
                "formula_class_facts": packet["formula_class_facts"],
                "dependency_facts": packet["dependency_facts"],
                "counts": packet["counts"],
            }
            dest.write_text(json.dumps({"packet": slim_packet, "meta": rec}, separators=(",", ":")) + "\n")
            rec["packet_path"] = str(dest.relative_to(OUT))
            rows.append(rec)
    elapsed = time.perf_counter() - t0
    callable_rows = [r for r in rows if r.get("callable")]
    layer_counts = {}
    for layer in LAYERS:
        statuses = Counter((r.get("eligibility") or {}).get(layer, {}).get("status") for r in rows if "eligibility" in r)
        layer_counts[layer] = dict(statuses)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "strict_scope": True,
        "wall_s": round(elapsed, 3),
        "n_obligation_rows": sum(1 for r in rows if r.get("job_id")),
        "n_callable": len(callable_rows),
        "by_split": {
            name: {
                "n": sum(1 for r in rows if r.get("split") == name and r.get("job_id")),
                "n_callable": sum(1 for r in rows if r.get("split") == name and r.get("callable")),
            }
            for name in ("discovery", "validation", "held_out")
        },
        "layer_eligibility": layer_counts,
        "upstream_missing": {
            layer: sum(
                1
                for r in rows
                if (r.get("eligibility") or {}).get(layer, {}).get("status") == "UPSTREAM_MISSING"
            )
            for layer in LAYERS
        },
        "unparsed_scope": sum(
            1
            for r in rows
            if (r.get("eligibility") or {}).get("scope", {}).get("status") == "TASK_SCOPE_UNPARSED"
        ),
        "rows": rows,
    }
    _write("population.json", payload)
    print(
        f"PACKETS n={payload['n_obligation_rows']} callable={payload['n_callable']} {elapsed:.1f}s",
        flush=True,
    )
    return payload


def _load_packet_file(rel: str) -> dict[str, Any]:
    return json.loads((OUT / rel).read_text())


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


def openrouter_chat(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    reasoning: str | None,
    temperature: float | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if temperature is not None:
        body["temperature"] = temperature
    if reasoning:
        body["reasoning"] = {"effort": reasoning}
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "librecalc-closed-world-resolver",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return {"http_ok": True, "payload": json.loads(response.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        return {"http_ok": False, "status": exc.code, "detail": exc.read().decode("utf-8", errors="replace")}
    except urllib.error.URLError as exc:
        return {"http_ok": False, "status": 0, "detail": str(exc.reason)}


def _call_model(api_key: str, spec: dict[str, Any], user: str) -> dict[str, Any]:
    attempt = 0
    include_reasoning = True
    temperature: float | None = spec["temperature"]
    http: dict[str, Any] = {}
    while attempt < 8:
        attempt += 1
        http = openrouter_chat(
            api_key=api_key,
            model=spec["id"],
            system=RESOLVER_PROMPT,
            user=user,
            max_tokens=spec["max_tokens"],
            reasoning=spec["reasoning"] if include_reasoning else None,
            temperature=temperature,
        )
        if http.get("http_ok"):
            text = _message_text(http["payload"])
            parsed = extract_json_object(text)
            if parsed is not None:
                http["parsed"] = parsed
                http["raw_text"] = text
                http["attempts"] = attempt
                return http
            http["parse_fail"] = True
            http["raw_text"] = text
            if attempt < 3:
                time.sleep(1)
                continue
            http["attempts"] = attempt
            return http
        status = http.get("status")
        detail = str(http.get("detail") or "").lower()
        if status == 400 and include_reasoning and "reasoning" in detail:
            include_reasoning = False
            continue
        if status == 400 and temperature is not None and "temperature" in detail:
            temperature = None
            continue
        if status in {429, 502, 503, 504, 0}:
            time.sleep(min(30, 2 ** attempt))
            continue
        if status == 402:
            detail = str(http.get("detail") or "")
            if "in_flight" in detail.lower() or "retry-after" in detail.lower():
                time.sleep(min(120, 15 * attempt))
                continue
            break
        http["attempts"] = attempt
        return http
    http["attempts"] = attempt
    return http


def cmd_run(*, model_key: str, force: bool = False, limit: int | None = None, split: str | None = None, tasks: list[str] | None = None) -> dict[str, Any]:
    cmd_freeze()
    pop = json.loads((OUT / "population.json").read_text())
    jobs = [r for r in pop["rows"] if r.get("callable")]
    if split:
        jobs = [r for r in jobs if r.get("split") == split]
    if tasks:
        wanted = set(tasks)
        jobs = [r for r in jobs if r.get("task") in wanted]
    if limit is not None:
        jobs = jobs[:limit]
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY required")
    spec = MODELS[model_key]
    dest = OUT / f"calls_{model_key}.jsonl"
    done: set[str] = set()
    kept: list[str] = []
    if force and dest.exists():
        dest.write_text("")
    elif dest.exists():
        for line in dest.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("valid"):
                done.add(rec["job_id"])
                kept.append(line)
        dest.write_text("\n".join(kept) + ("\n" if kept else ""))
    remaining = [j for j in jobs if j["job_id"] not in done]
    print(f"RUN {model_key} remaining={len(remaining)}/{len(jobs)}", flush=True)
    with dest.open("a", encoding="utf-8") as handle:
        for index, job in enumerate(remaining, 1):
            packed = _load_packet_file(job["packet_path"])
            packet = packed["packet"]
            rendered = render_resolver_packet(packet)
            user = (
                "Bind this ORACLE obligation to packet entity IDs. "
                "Return JSON only.\n\n"
                f"OBLIGATION FIELDS:\n{json.dumps(packet['fields'], ensure_ascii=False)}\n\n"
                f"GROUNDING PACKET:\n{rendered}"
            )
            print(f"CALL {model_key} {index}/{len(remaining)} {job['job_id']}", flush=True)
            started = time.perf_counter()
            http = _call_model(api_key, spec, user)
            elapsed = round(time.perf_counter() - started, 3)
            record: dict[str, Any] = {
                "job_id": job["job_id"],
                "task": job["task"],
                "split": job["split"],
                "obligation_id": job["obligation_id"],
                "model": spec["id"],
                "model_key": model_key,
                "elapsed_s": elapsed,
                "attempts": http.get("attempts"),
                "packet_tokens": job["packet_tokens"],
            }
            if not http.get("http_ok"):
                record.update({"valid": False, "error": {k: http.get(k) for k in ("status", "detail")}})
            else:
                parsed = http.get("parsed")
                checked = validate_resolution(parsed, packet, input_ids=job["input_ids"])
                record.update(
                    {
                        "valid": parsed is not None,
                        "raw_text": (http.get("raw_text") or "")[:8000],
                        "resolution": checked,
                        "usage": (http.get("payload") or {}).get("usage"),
                        "formula_leak": formula_synthesis_leakage(http.get("raw_text")),
                    }
                )
            handle.write(json.dumps(record) + "\n")
            handle.flush()
    return {"model": model_key, "n_done": len(done) + len(remaining)}


def _load_calls(model_key: str) -> list[dict[str, Any]]:
    path = OUT / f"calls_{model_key}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _score_calls(pop: dict[str, Any], calls: list[dict[str, Any]], model_key: str) -> dict[str, Any]:
    jobs = {r["job_id"]: r for r in pop["rows"] if r.get("job_id")}
    layer_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    examples = {"false_elimination": [], "safe_reduction": [], "premature": []}
    n_leak = 0
    n_invalid_calls = 0
    scored_calls = 0
    for call in calls:
        job = jobs.get(call["job_id"])
        if not job or not job.get("callable"):
            continue
        if not call.get("valid"):
            n_invalid_calls += 1
            continue
        scored_calls += 1
        if call.get("formula_leak"):
            n_leak += 1
        checked = call.get("resolution") or {"fields": {}, "invalid": []}
        for layer in LAYERS:
            elig = (job.get("eligibility") or {}).get(layer) or {}
            if elig.get("status") != "ELIGIBLE":
                continue
            field = (checked.get("fields") or {}).get(layer) or {
                "status": "UNRESOLVED",
                "candidate_ids": [],
                "invalid_ids": [],
            }
            classified = classify_output(
                input_ids=job["input_ids"][layer],
                output_ids=field.get("candidate_ids") or [],
                gold_ids=set(job["gold_ids"][layer]),
                coambiguous_ids=set(job["coambiguous_ids"][layer]),
                status=field.get("status") or "UNRESOLVED",
                invalid=bool(field.get("invalid_ids") or checked.get("invalid")),
            )
            row = {
                "job_id": call["job_id"],
                "task": call["task"],
                "split": call["split"],
                "obligation_id": call["obligation_id"],
                "layer": layer,
                "model_key": model_key,
                "evidence_available": job.get("evidence_available") or [],
                **classified,
            }
            layer_rows[layer].append(row)
            sample = {
                "job_id": row["job_id"],
                "layer": layer,
                "category": classified["category"],
                "n_input": classified["n_input"],
                "n_output": classified["n_output"],
                "fields": job["fields"],
            }
            if classified["false_elimination"] and len(examples["false_elimination"]) < 12:
                examples["false_elimination"].append(sample)
            if classified["safe_reduction"] and len(examples["safe_reduction"]) < 12:
                examples["safe_reduction"].append(sample)
            if classified["premature_resolution"] and len(examples["premature"]) < 12:
                examples["premature"].append(sample)
    all_rows = [r for rows in layer_rows.values() for r in rows]
    by_split: dict[str, Any] = {}
    for name in ("discovery", "validation", "held_out"):
        picked = [r for r in all_rows if r["split"] == name]
        by_split[name] = {
            "overall": aggregate_scores(picked),
            "by_layer": {layer: aggregate_scores([r for r in picked if r["layer"] == layer]) for layer in LAYERS},
        }
    by_evidence: dict[str, Any] = {}
    for tag in sorted({t for r in all_rows for t in r.get("evidence_available") or []}):
        picked = [r for r in all_rows if tag in (r.get("evidence_available") or [])]
        by_evidence[tag] = {
            "n": len(picked),
            "FALSE_ELIMINATION_RATE": round(sum(1 for r in picked if r["false_elimination"]) / max(1, len(picked)), 4),
            "SAFE_REDUCTION_RATE": round(sum(1 for r in picked if r["safe_reduction"]) / max(1, len(picked)), 4),
        }
    return {
        "model_key": model_key,
        "n_calls": len(calls),
        "n_scored_calls": scored_calls,
        "n_invalid_json": n_invalid_calls,
        "FORMULA_SYNTHESIS_LEAKAGE": round(n_leak / max(1, scored_calls), 4),
        "overall": aggregate_scores(all_rows),
        "by_split": by_split,
        "by_layer": {layer: aggregate_scores(layer_rows[layer]) for layer in LAYERS},
        "by_evidence": by_evidence,
        "examples": examples,
        "rows": all_rows,
    }


def cmd_score() -> dict[str, Any]:
    pop = json.loads((OUT / "population.json").read_text())
    keep_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in pop["rows"]:
        if not job.get("callable"):
            continue
        packed = _load_packet_file(job["packet_path"])
        packet = packed["packet"]
        keep = baseline_keep_all(packet, job["input_ids"])
        exact = baseline_exact_match(packet, job["input_ids"])
        for layer in LAYERS:
            elig = (job.get("eligibility") or {}).get(layer) or {}
            if elig.get("status") != "ELIGIBLE":
                continue
            for name, checked, sink in (("keep_all", keep, keep_rows), ("exact_match", exact, exact_rows)):
                field = checked["fields"][layer]
                classified = classify_output(
                    input_ids=job["input_ids"][layer],
                    output_ids=field["candidate_ids"],
                    gold_ids=set(job["gold_ids"][layer]),
                    coambiguous_ids=set(job["coambiguous_ids"][layer]),
                    status=field["status"],
                    invalid=False,
                )
                sink[layer].append(
                    {
                        "job_id": job["job_id"],
                        "task": job["task"],
                        "split": job["split"],
                        "obligation_id": job["obligation_id"],
                        "layer": layer,
                        "model_key": name,
                        **classified,
                    }
                )
    baselines = {
        "keep_all": {
            "overall": aggregate_scores([r for rows in keep_rows.values() for r in rows]),
            "held_out": aggregate_scores([r for rows in keep_rows.values() for r in rows if r["split"] == "held_out"]),
            "by_layer": {layer: aggregate_scores(keep_rows[layer]) for layer in LAYERS},
        },
        "exact_match": {
            "overall": aggregate_scores([r for rows in exact_rows.values() for r in rows]),
            "held_out": aggregate_scores([r for rows in exact_rows.values() for r in rows if r["split"] == "held_out"]),
            "by_layer": {layer: aggregate_scores(exact_rows[layer]) for layer in LAYERS},
        },
    }
    models = {}
    for key in MODELS:
        calls = _load_calls(key)
        if calls:
            models[key] = _score_calls(pop, calls, key)
            slim = {k: models[key][k] for k in models[key] if k != "rows"}
            _write(f"score_{key}.json", slim)
    comparison = None
    if "gpt" in models and "glm" in models:
        comparison = compare_models(models["gpt"]["rows"], models["glm"]["rows"])
        held_g = [r for r in models["gpt"]["rows"] if r["split"] == "held_out"]
        held_z = [r for r in models["glm"]["rows"] if r["split"] == "held_out"]
        comparison["held_out"] = compare_models(held_g, held_z)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "baselines": baselines,
        "comparison": comparison,
        "models_present": sorted(models),
    }
    _write("score.json", payload)
    print(f"SCORE models={payload['models_present']}", flush=True)
    return payload


def cmd_known() -> dict[str, Any]:
    pop = json.loads((OUT / "population.json").read_text())
    jobs = [r for r in pop["rows"] if r.get("job_id")]
    gpt = {c["job_id"]: c for c in _load_calls("gpt")}
    glm = {c["job_id"]: c for c in _load_calls("glm")}
    out = []
    for case in KNOWN:
        matches = []
        for job in jobs:
            if job["task"] != case["task"]:
                continue
            blob = json.dumps(job.get("fields") or {}).lower()
            if case["symbol"].lower() not in blob:
                continue
            gpt_c = gpt.get(job["job_id"])
            glm_c = glm.get(job["job_id"])
            layer_view = {}
            for layer in LAYERS:
                elig = (job.get("eligibility") or {}).get(layer) or {}
                rec = {
                    "eligibility": elig.get("status"),
                    "n_input": elig.get("n_input"),
                    "n_gold": elig.get("n_gold"),
                    "gold_ids": (job.get("gold_ids") or {}).get(layer),
                }
                for name, call in (("gpt", gpt_c), ("glm", glm_c)):
                    if not call or not call.get("resolution"):
                        continue
                    field = call["resolution"]["fields"].get(layer) or {}
                    if elig.get("status") == "ELIGIBLE":
                        classified = classify_output(
                            input_ids=job["input_ids"][layer],
                            output_ids=field.get("candidate_ids") or [],
                            gold_ids=set(job["gold_ids"][layer]),
                            coambiguous_ids=set(job["coambiguous_ids"][layer]),
                            status=field.get("status") or "UNRESOLVED",
                            invalid=bool(field.get("invalid_ids")),
                        )
                    else:
                        classified = None
                    rec[name] = {
                        "status": field.get("status"),
                        "n_output": len(field.get("candidate_ids") or []),
                        "classification": classified,
                    }
                layer_view[layer] = rec
            matches.append(
                {
                    "job_id": job["job_id"],
                    "fields": job["fields"],
                    "callable": job.get("callable"),
                    "layers": layer_view,
                }
            )
        out.append({**case, "matches": matches[:8]})
    payload = {"generated_at": datetime.now(UTC).isoformat(), "cases": out}
    _write("known_cases.json", payload)
    return payload


def _gate(held: dict[str, Any] | None, premature_known: bool, invention: float | None) -> tuple[str, str]:
    if not held or held.get("n") == 0:
        return "PARTIAL / LOW_VALUE", "No held-out eligible scored rows."
    fe = held.get("FALSE_ELIMINATION_RATE") or 0
    sr = held.get("SAFE_REDUCTION_RATE") or 0
    mean_r = held.get("mean_reduction_ratio")
    invent = invention or 0
    if fe > 0.15:
        return "UNSAFE", "Held-out false elimination is high; do not prune mechanically."
    if fe > 0.05:
        return (
            "PARTIAL / MODEL_LIMITED",
            "False elimination is modest but above 5%. Use as advisory ordering, not authoritative pruning.",
        )
    if sr < 0.10 or (mean_r is not None and mean_r > 0.90):
        return "PARTIAL / LOW_VALUE", "False elimination is low but the model adds little narrowing."
    if premature_known:
        return (
            "PARTIAL / MODEL_LIMITED",
            "Safety is acceptable but known genuine-ambiguity cases were collapsed.",
        )
    if invent > 0.01:
        return "UNSAFE", "Entity invention is non-zero."
    return (
        "STRONG",
        "Closed-world resolution narrows candidates while preserving the mechanical gold-retention guarantee.",
    )


def cmd_report() -> Path:
    pop = json.loads((OUT / "population.json").read_text()) if (OUT / "population.json").exists() else {}
    score = json.loads((OUT / "score.json").read_text()) if (OUT / "score.json").exists() else {}
    gpt = json.loads((OUT / "score_gpt.json").read_text()) if (OUT / "score_gpt.json").exists() else {}
    glm = json.loads((OUT / "score_glm.json").read_text()) if (OUT / "score_glm.json").exists() else {}
    known = json.loads((OUT / "known_cases.json").read_text()) if (OUT / "known_cases.json").exists() else {}
    freeze = json.loads((OUT / "freeze.json").read_text()) if (OUT / "freeze.json").exists() else {}
    held = ((gpt.get("by_split") or {}).get("held_out") or {}).get("overall")
    premature_known = False
    for case in known.get("cases") or []:
        if case.get("id") in {"K6", "H41", "J31", "AF66"}:
            for match in case.get("matches") or []:
                for layer, rec in (match.get("layers") or {}).items():
                    gpt_c = (rec.get("gpt") or {}).get("classification") or {}
                    if gpt_c.get("premature_resolution"):
                        premature_known = True
    invent = (held or {}).get("INVALID_ENTITY_REFERENCE_RATE")
    gate, conclusion = _gate(held, premature_known, invent)
    gpt_fe = (held or {}).get("FALSE_ELIMINATION_RATE")
    glm_held = ((glm.get("by_split") or {}).get("held_out") or {}).get("overall") or {}
    glm_fe = glm_held.get("FALSE_ELIMINATION_RATE")
    if gate == "STRONG" and gpt_fe is not None and glm_fe is not None and abs(gpt_fe - glm_fe) > 0.05:
        gate = "PARTIAL / MODEL_LIMITED"
        conclusion = "Strong GPT safety but material GPT/GLM gap; resolution is model-capability-sensitive."
    advisory = {
        "authoritative_false_elim_held_gpt": gpt_fe,
        "advisory_false_elim": 0.0,
        "failures_that_disappear_if_advisory": (held or {}).get("categories", {}).get("GOLD_DROPPED", 0)
        + (held or {}).get("categories", {}).get("WRONG_UNIQUE", 0),
    }
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "gate": gate,
        "conclusion": conclusion,
        "n_callable": pop.get("n_callable"),
        "layer_eligibility": pop.get("layer_eligibility"),
        "held_out_gpt": held,
        "held_out_glm": glm_held,
        "baselines_held_keep_all": ((score.get("baselines") or {}).get("keep_all") or {}).get("held_out"),
        "comparison_held": ((score.get("comparison") or {}).get("held_out")),
        "formula_leak_gpt": gpt.get("FORMULA_SYNTHESIS_LEAKAGE"),
        "advisory": advisory,
        "prompt_sha256": freeze.get("prompt_sha256"),
        "golden_used": False,
    }
    _write("summary.json", summary)
    lines = [
        "# Closed-world resolver confirmation",
        "",
        "ORACLE V1 obligations. Frozen temporal-closure packets. No parser, synthesis, or workbook edits.",
        "",
        f"- golden_used: false",
        f"- callable packets: {pop.get('n_callable')} / {pop.get('n_obligation_rows')}",
        f"- layer eligibility: `{pop.get('layer_eligibility')}`",
        f"- upstream missing: `{pop.get('upstream_missing')}`",
        f"- unparsed scope obligations: {pop.get('unparsed_scope')}",
        "",
        "## Held-out GPT primary",
        "",
        f"`{held}`",
        "",
        "## Held-out by layer (GPT)",
        "",
        f"`{((gpt.get('by_split') or {}).get('held_out') or {}).get('by_layer')}`",
        "",
        "## Baselines held-out KEEP_ALL / EXACT_MATCH",
        "",
        f"`{((score.get('baselines') or {}).get('keep_all') or {}).get('held_out')}`",
        "",
        f"`{((score.get('baselines') or {}).get('exact_match') or {}).get('held_out')}`",
        "",
        "## GLM held-out",
        "",
        f"`{glm_held}`",
        "",
        "## GPT vs GLM held-out",
        "",
        f"`{((score.get('comparison') or {}).get('held_out'))}`",
        "",
        "## Advisory vs authoritative",
        "",
        f"`{advisory}`",
        "",
        "## Known cases",
        "",
    ]
    for case in known.get("cases") or []:
        n = len(case.get("matches") or [])
        lines.append(f"- **{case.get('id')}** `{case.get('task')}` matches={n}")
        for match in (case.get("matches") or [])[:2]:
            gpt_subj = ((match.get("layers") or {}).get("subject") or {}).get("gpt")
            lines.append(f"  - {match.get('job_id')} subject={gpt_subj}")
    lines += [
        "",
        f"## Gate: **{gate}**",
        "",
        conclusion,
        "",
    ]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    print(f"REPORT {dest} {gate}", flush=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cmd",
        choices=["freeze", "packets", "run", "score", "known", "report", "all"],
    )
    parser.add_argument("--model", choices=["gpt", "glm"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--split", choices=["discovery", "validation", "held_out"])
    parser.add_argument("--tasks", help="comma-separated task ids")
    args = parser.parse_args()
    if args.cmd == "freeze":
        cmd_freeze()
    elif args.cmd == "packets":
        cmd_packets(limit=args.limit)
    elif args.cmd == "run":
        if not args.model:
            raise SystemExit("--model gpt|glm required")
        cmd_run(
            model_key=args.model,
            force=args.force,
            limit=args.limit,
            split=args.split,
            tasks=args.tasks.split(",") if args.tasks else None,
        )
    elif args.cmd == "score":
        cmd_score()
    elif args.cmd == "known":
        cmd_known()
    elif args.cmd == "report":
        cmd_report()
    else:
        cmd_packets(limit=args.limit)
        task_ids = args.tasks.split(",") if args.tasks else None
        if args.model:
            cmd_run(model_key=args.model, force=args.force, limit=args.limit, split=args.split, tasks=task_ids)
        else:
            cmd_run(model_key="gpt", force=args.force, limit=args.limit, split=args.split, tasks=task_ids)
            cmd_run(model_key="glm", force=args.force, limit=args.limit, split=args.split, tasks=task_ids)
        cmd_score()
        cmd_known()
        cmd_report()


if __name__ == "__main__":
    main()
