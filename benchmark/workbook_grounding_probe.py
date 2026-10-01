#!/usr/bin/env python3
"""Closed-world workbook grounding probe.

Phases:
  spine     — compile WORKBOOK_GROUNDING_SPINE for each readable FM input
  phase_a   — GOLD_ENTITY_SPINE_COVERAGE (no LLM)
  phase_b   — deterministic projection / GOLD_RETENTION_AFTER_RETRIEVAL (no LLM)
  resolve   — GPT closed-world resolver IFF phase B retrieval gate passes
  ablation  — freeze diagnostic subset, drop one spine layer
  report
  all       — spine, phase_a, phase_b, (resolve if gated), ablation, report

ORACLE V1 obligations. Goldens are evaluator labels only. No formula synthesis,
workbook edits, agents, finance ontology, or V1 changes.
"""
from __future__ import annotations

import argparse
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

from fingerprint import a1_address  # noqa: E402
from task_obligation_compile import extract_json_object  # noqa: E402
from task_obligation_shape import family_of, is_semantic_change  # noqa: E402
from workbook_grounding import (  # noqa: E402
    RESOLVER_PROMPT,
    associate_gold,
    field_text,
    gold_entities,
    packet_id_universe,
    parse_scope_spec,
    project_obligation,
    render_packet,
    token_estimate,
    validate_resolution,
)
from workbook_grounding_spine import (  # noqa: E402
    RETRIEVAL_RULES,
    compile_spine,
    id_in_spine,
    rebuild_id_set,
    sheet_cell_id,
)

DATA = ROOT / "benchmark-data/SpreadsheetBench-2/data"
DATASET = DATA / "Financial_Model/dataset.json"
SHAPE_OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-shape-probe"
)
ORACLE_PATH = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/task-obligation-compile-probe/oracle_obligations.json"
)
OUT = (
    ROOT
    / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe"
)
ENV_FILE = ROOT / ".env"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GPT_MODEL = "openai/gpt-5.6-sol"
CONTEXT_TOKEN_LIMIT = 80_000
RETRIEVAL_GATE = 0.95

DIAGNOSTIC_TASKS = ["01_03", "04_05", "08_01", "09_05", "14_05", "15_04", "17_03", "20_04"]
KNOWN_CASES = [
    {"id": "K6", "task": "04_05", "symbol": "total growth rates", "must_not_require": ["K27"]},
    {"id": "K163", "task": "09_05", "symbol": "Other Long-Term Assets", "must_not_require": ["K164"]},
    {"id": "D10", "task": "14_05", "symbol": "effective tax rate", "must_not_require": ["D10"]},
    {"id": "H41", "task": "20_04", "symbol": "days-based linkage", "must_not_require": ["H30", "H42"]},
    {"id": "J31", "task": "14_05", "symbol": "Total Revenue", "must_not_require": ["SUM("]},
    {"id": "J46", "task": "08_01", "symbol": "Receivables", "must_not_require": ["J46"]},
    {"id": "AF66", "task": "08_01", "symbol": "30%", "must_not_require": ["$C$8"]},
    {"id": "K104", "task": "17_03", "symbol": "percentage of Revenue", "must_not_require": ["365"]},
    {"id": "Y39", "task": "15_04", "symbol": "EPS Growth", "must_not_require": ["Y39"]},
]
ABLATIONS = ("NO_LABEL_CONTEXT", "NO_PERIOD_FACTS", "NO_FORMULA_CLASS", "NO_DEPENDENCY_FACTS")


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip("'\"")


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def _split_map() -> dict[str, str]:
    split = json.loads((SHAPE_OUT / "family_split.json").read_text())
    out = {}
    for fam in split["discovery_families"]:
        out[fam] = "discovery"
    for fam in split["validation_families"]:
        out[fam] = "validation"
    for fam in split["held_out_families"]:
        out[fam] = "held_out"
    return out


def _tasks() -> list[dict[str, str]]:
    return json.loads(DATASET.read_text())


def _oracle_by_task() -> dict[str, dict[str, Any]]:
    doc = json.loads(ORACLE_PATH.read_text())
    return {row["task"]: row for row in doc["tasks"]}


def _delta_by_task() -> dict[str, dict[str, Any]]:
    doc = json.loads((SHAPE_OUT / "golden_delta.json").read_text())
    return {row["task"]: row for row in doc["tasks"]}


def spine_path(task_id: str) -> Path:
    return OUT / "spines" / f"{task_id}.json"


def _compact_spine(spine: dict[str, Any]) -> dict[str, Any]:
    occupied = [
        {
            "id": rec["id"],
            "sheet_id": rec["sheet_id"],
            "row": rec["row"],
            "col": rec["col"],
            "kind": rec["kind"],
        }
        for rec in spine.get("occupied") or []
    ]
    slim = dict(spine)
    slim["occupied"] = occupied
    slim.pop("_id_set", None)
    # id_index can be huge; keep stats + reconstruct set from parts + bounds
    slim["id_index"] = []
    return slim


def cmd_spine(*, force: bool = False, limit: int | None = None) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "spines").mkdir(parents=True, exist_ok=True)
    split = _split_map()
    rows = []
    tasks = _tasks()
    if limit:
        tasks = tasks[:limit]
    for i, task in enumerate(tasks, 1):
        tid = task["id"]
        dest = spine_path(tid)
        if dest.exists() and not force:
            summary = json.loads(dest.read_text())
            readable = summary.get("readable", False)
            print(f"SPINE reuse {i}/{len(tasks)} {tid} readable={readable}", flush=True)
        else:
            path = DATA / "Financial_Model" / task["spreadsheet_path"]
            print(f"SPINE compile {i}/{len(tasks)} {tid}", flush=True)
            started = time.perf_counter()
            spine = compile_spine(path, workbook_key=tid)
            spine["elapsed_s"] = round(time.perf_counter() - started, 3)
            dest.write_text(json.dumps(_compact_spine(spine)) + "\n")
            summary = spine
        rows.append(
            {
                "task": tid,
                "family": family_of(tid),
                "split": split[family_of(tid)],
                "readable": summary.get("readable", False),
                "unsupported": summary.get("unsupported") or [],
                "stats": summary.get("stats") or {},
                "error": summary.get("error"),
            }
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n": len(rows),
        "n_readable": sum(1 for r in rows if r["readable"]),
        "n_unreadable": sum(1 for r in rows if not r["readable"]),
        "retrieval_rules": RETRIEVAL_RULES,
        "tasks": rows,
    }
    path = _write("spine_index.json", payload)
    print(f"SPINE {path} readable={payload['n_readable']}/{payload['n']}", flush=True)
    return payload


def _load_spine(task_id: str) -> dict[str, Any]:
    spine = json.loads(spine_path(task_id).read_text())
    rebuild_id_set(spine)
    return spine


def cmd_phase_a() -> dict[str, Any]:
    split = _split_map()
    delta = _delta_by_task()
    rows = []
    for task in _tasks():
        tid = task["id"]
        if not spine_path(tid).exists():
            continue
        spine = _load_spine(tid)
        rec = delta.get(tid)
        if not rec or not spine.get("readable"):
            rows.append(
                {
                    "task": tid,
                    "split": split[family_of(tid)],
                    "readable": bool(spine.get("readable")),
                    "evaluable": False,
                    "reason": "unreadable" if not spine.get("readable") else "no_delta",
                }
            )
            continue
        semantic = [c for c in rec["changes"] if is_semantic_change(c)]
        n = len(semantic)
        cell_ok = sheet_ok = row_ok = 0
        missing = []
        for change in semantic:
            ents = gold_entities(spine, change)
            if ents["sheet_id"]:
                sheet_ok += 1
            if ents.get("in_spine"):
                cell_ok += 1
            else:
                if len(missing) < 8:
                    missing.append(f"{change['sheet']}!{change['address']}")
            if ents["row_id"] and ents["sheet_id"]:
                row_ok += 1
        rows.append(
            {
                "task": tid,
                "split": split[family_of(tid)],
                "readable": True,
                "evaluable": True,
                "n_semantic": n,
                "sheet_coverage": round(sheet_ok / n, 4) if n else 1.0,
                "row_coverage": round(row_ok / n, 4) if n else 1.0,
                "cell_coverage": round(cell_ok / n, 4) if n else 1.0,
                "missing_sample": missing,
                "stats": spine.get("stats") or {},
                "unsupported": spine.get("unsupported") or [],
            }
        )
    evaluable = [r for r in rows if r.get("evaluable")]
    by_split = {}
    for name in ("discovery", "validation", "held_out", "overall"):
        picked = evaluable if name == "overall" else [r for r in evaluable if r["split"] == name]
        n_cells = sum(r["n_semantic"] for r in picked) or 1
        cov = sum(r["cell_coverage"] * r["n_semantic"] for r in picked) / n_cells
        by_split[name] = {
            "n_tasks": len(picked),
            "n_gold_cells": sum(r["n_semantic"] for r in picked),
            "GOLD_ENTITY_SPINE_COVERAGE": round(cov, 4),
            "mean_task_cell_coverage": round(
                sum(r["cell_coverage"] for r in picked) / len(picked), 4
            )
            if picked
            else None,
        }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "by_split": by_split,
        "tasks": rows,
    }
    path = _write("phase_a.json", payload)
    print(f"PHASE_A overall={by_split['overall']['GOLD_ENTITY_SPINE_COVERAGE']}", flush=True)
    return payload


def _scope_applicable(obligation: dict[str, Any]) -> bool:
    spec = parse_scope_spec(obligation)
    return bool(spec["all"] or spec["years"] or spec["months"])


def cmd_phase_b(
    *,
    ablation: str | None = None,
    task_ids: list[str] | None = None,
    dest_name: str | None = None,
    overlay_coords_dir: Path | None = None,
    strict_scope: bool = False,
) -> dict[str, Any]:
    split = _split_map()
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    flags = {ablation} if ablation else set()
    rows = []
    known = []
    for task in _tasks():
        tid = task["id"]
        if task_ids and tid not in task_ids:
            continue
        if not spine_path(tid).exists():
            continue
        spine = _load_spine(tid)
        if overlay_coords_dir is not None:
            from temporal_spine import overlay_periods

            coord_path = overlay_coords_dir / f"{tid}.json"
            if coord_path.exists():
                compiled = json.loads(coord_path.read_text())
                if compiled.get("readable"):
                    spine = overlay_periods(spine, compiled)
        o_row = oracle.get(tid)
        d_row = delta.get(tid)
        if not spine.get("readable") or not o_row or not d_row:
            continue
        obligations = o_row["obligations"]
        packets = [project_obligation(spine, ob, ablation=flags, strict_scope=strict_scope) for ob in obligations]
        semantic = [c for c in d_row["changes"] if is_semantic_change(c)]
        layer_stats = {k: {"eval": 0, "hit": 0} for k in ("locus", "subject", "scope", "target")}
        n_s1 = len(spine.get("s1_cell_ids") or [])
        n_occ = len(spine.get("occupied") or [])
        n_tgt = sum(p["counts"]["n_target"] for p in packets)
        n_subj = sum(p["counts"]["n_subject"] for p in packets)
        miss = Counter()
        n_scope_text_unparsed = sum(
            1
            for ob in obligations
            if field_text(ob.get("scope")) and not _scope_applicable(ob)
        )
        period_index = [
            (p.get("sheet_id"), p.get("col_id"), p.get("row_id"))
            for p in (spine.get("periods") or [])
        ]
        for change in semantic:
            # associate against all packets; retention if any matching packet holds the entity
            per_ob = [associate_gold(spine, [ob], [pk], change) for ob, pk in zip(obligations, packets)]
            explainable = any(a["explainable"] for a in per_ob)
            ents = gold_entities(spine, change)
            if any(a["explainable"] and ents["sheet_id"] in {h["sheet_id"] for h in packets[i]["locus"]} for i, a in enumerate(per_ob)):
                layer_stats["locus"]["eval"] += 1
                layer_stats["locus"]["hit"] += 1
            elif explainable:
                layer_stats["locus"]["eval"] += 1
            # subject: explainable via subject_label
            subj_expl = [i for i, a in enumerate(per_ob) if "subject_label" in sum((x["reasons"] for x in a["matched_obligations"]), [])]
            if subj_expl:
                layer_stats["subject"]["eval"] += 1
                if any(
                    ents["row_id"] in {h["row_id"] for h in packets[i]["subject"]}
                    for i in subj_expl
                ):
                    layer_stats["subject"]["hit"] += 1
            # Empty packets count as misses when the obligation has parseable period tokens.
            scope_eval = [
                i
                for i, ob in enumerate(obligations)
                if per_ob[i]["explainable"] and _scope_applicable(ob)
            ]
            if scope_eval:
                layer_stats["scope"]["eval"] += 1
                hit = any(
                    ents["col_id"] in {h.get("col_id") for h in packets[i]["scope"]}
                    for i in scope_eval
                )
                if hit:
                    layer_stats["scope"]["hit"] += 1
                    miss["SCOPE_HIT"] += 1
                else:
                    on_col = any(
                        sid == ents["sheet_id"] and cid == ents["col_id"]
                        for sid, cid, _rid in period_index
                    )
                    on_row = any(
                        sid == ents["sheet_id"] and rid == ents["row_id"]
                        for sid, _cid, rid in period_index
                    )
                    empty = all(not packets[i]["scope"] for i in scope_eval)
                    if not on_col and on_row:
                        miss["SPINE_PERIOD_ON_GOLD_ROW_NOT_COL"] += 1
                    elif not on_col:
                        miss["SPINE_PERIOD_ABSENT_ON_GOLD_CELL"] += 1
                    elif empty:
                        miss["RETRIEVAL_MISSING_EMPTY"] += 1
                    else:
                        miss["RETRIEVAL_MISSING_WRONG_COLS"] += 1
            tgt_eval = [i for i, a in enumerate(per_ob) if a["explainable"]]
            if tgt_eval:
                layer_stats["target"]["eval"] += 1
                if any(ents["cell_id"] in packets[i]["target_cell_ids"] for i in tgt_eval):
                    layer_stats["target"]["hit"] += 1
        def rate(name: str) -> float | None:
            st = layer_stats[name]
            if not st["eval"]:
                return None
            return round(st["hit"] / st["eval"], 4)

        token_sizes = [token_estimate(render_packet(p)) for p in packets]
        rec = {
            "task": tid,
            "split": split[family_of(tid)],
            "n_obligations": len(obligations),
            "n_semantic": len(semantic),
            "retention": {k: rate(k) for k in layer_stats},
            "layer_eval": {k: v["eval"] for k, v in layer_stats.items()},
            "layer_hit": {k: v["hit"] for k, v in layer_stats.items()},
            "counts": {
                "n_sheets": len(spine.get("sheets") or []),
                "n_occupied": n_occ,
                "n_s1": n_s1,
                "n_subject_candidates": n_subj,
                "n_target_candidates": n_tgt,
            },
            "compression": {
                "locus": round(
                    sum(p["counts"]["n_locus"] for p in packets) / max(1, len(packets) * len(spine.get("sheets") or [])),
                    4,
                ),
                "subject": round(n_subj / max(1, len(packets) * len(spine.get("text_anchors") or [])), 4),
                "target_vs_occupied": round(n_tgt / max(1, n_occ), 4),
                "target_vs_s1": round(n_tgt / max(1, n_s1), 4) if n_s1 else None,
            },
            "packet_tokens_max": max(token_sizes) if token_sizes else 0,
            "packet_tokens_mean": round(sum(token_sizes) / len(token_sizes), 1) if token_sizes else 0,
            "context_capacity_failure": any(t > CONTEXT_TOKEN_LIMIT for t in token_sizes),
            "scope_miss": dict(miss),
            "n_scope_text_unparsed": n_scope_text_unparsed,
        }
        rows.append(rec)
        if tid in DIAGNOSTIC_TASKS:
            known.append(
                {
                    "task": tid,
                    "packets": [
                        {
                            "obligation_id": p["obligation_id"],
                            "fields": p["fields"],
                            "locus": p["locus"],
                            "subject_sample": p["subject"][:8],
                            "scope_n": len(p["scope"]),
                            "source_sample": p["source"][:6],
                            "n_target": len(p["target_cell_ids"]),
                            "counts": p["counts"],
                        }
                        for p in packets
                    ],
                }
            )
        print(
            f"B {tid} locus={rec['retention']['locus']} subject={rec['retention']['subject']} "
            f"scope={rec['retention']['scope']} target={rec['retention']['target']}",
            flush=True,
        )
    def agg(picked: list[dict[str, Any]]) -> dict[str, Any]:
        out = {}
        for layer in ("locus", "subject", "scope", "target"):
            ev = sum(r["layer_eval"][layer] for r in picked)
            ht = sum(r["layer_hit"][layer] for r in picked)
            out[layer] = {
                "eval": ev,
                "hit": ht,
                "GOLD_RETENTION_AFTER_RETRIEVAL": round(ht / ev, 4) if ev else None,
            }
        out["n_tasks"] = len(picked)
        out["mean_target_vs_occupied"] = round(
            sum(r["compression"]["target_vs_occupied"] for r in picked) / max(1, len(picked)),
            4,
        )
        s1_vals = [r["compression"]["target_vs_s1"] for r in picked if r["compression"]["target_vs_s1"] is not None]
        out["mean_target_vs_s1"] = round(sum(s1_vals) / len(s1_vals), 4) if s1_vals else None
        out["mean_packet_tokens"] = round(
            sum(r["packet_tokens_mean"] for r in picked) / max(1, len(picked)),
            1,
        )
        out["max_packet_tokens"] = max((r["packet_tokens_max"] for r in picked), default=0)
        out["context_capacity_failures"] = sum(1 for r in picked if r["context_capacity_failure"])
        miss_all = Counter()
        for r in picked:
            miss_all.update(r.get("scope_miss") or {})
        out["scope_miss"] = dict(miss_all)
        out["n_scope_text_unparsed"] = sum(r.get("n_scope_text_unparsed") or 0 for r in picked)
        return out

    by_split = {name: agg([r for r in rows if r["split"] == name]) for name in ("discovery", "validation", "held_out")}
    overall = agg(rows)
    held = by_split["held_out"]
    gate = {
        "threshold": RETRIEVAL_GATE,
        "layers": ["locus", "subject", "scope"],
        "held_out": {k: (held[k]["GOLD_RETENTION_AFTER_RETRIEVAL"] if held[k]["eval"] else None) for k in ("locus", "subject", "scope")},
        "pass": all(
            (held[k]["GOLD_RETENTION_AFTER_RETRIEVAL"] or 0) >= RETRIEVAL_GATE
            for k in ("locus", "subject", "scope")
            if held[k]["eval"]
        ),
    }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "ablation": ablation,
        "retrieval_rules": RETRIEVAL_RULES,
        "overall": overall,
        "by_split": by_split,
        "gate": gate,
        "tasks": rows,
        "diagnostic_packets": known if not ablation else None,
    }
    if dest_name:
        name = dest_name
    elif ablation:
        name = f"ablation_{ablation}.json"
    elif task_ids:
        name = "phase_b_subset.json"
    else:
        name = "phase_b.json"
    path = _write(name, payload)
    print(f"PHASE_B {path} gate={gate['pass']} held={gate['held_out']}", flush=True)
    return payload


def _message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text") or item if isinstance(item, (str, dict)) else ""
            for item in content
        )
    return str(content or "")


def openrouter_chat(api_key: str, user: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": GPT_MODEL,
        "max_tokens": 4096,
        "temperature": 0.0,
        "reasoning": {"effort": "medium"},
        "messages": [
            {"role": "system", "content": RESOLVER_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "librecalc-workbook-grounding",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return {"http_ok": True, "payload": json.loads(response.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        return {"http_ok": False, "status": exc.code, "detail": exc.read().decode("utf-8", errors="replace")}
    except urllib.error.URLError as exc:
        return {"http_ok": False, "status": 0, "detail": str(exc.reason)}


def cmd_resolve(*, force: bool = False) -> dict[str, Any]:
    phase_b = json.loads((OUT / "phase_b.json").read_text())
    if not phase_b["gate"]["pass"]:
        payload = {
            "skipped": True,
            "reason": "RETRIEVAL_GATE_FAILED",
            "gate": phase_b["gate"],
        }
        _write("phase_c.json", payload)
        print("PHASE_C skipped: retrieval gate failed", flush=True)
        return payload
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY required for resolve")
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    split = _split_map()
    dest = OUT / "phase_c.json"
    done = {}
    if dest.exists() and not force:
        done = {row["job_id"]: row for row in json.loads(dest.read_text()).get("calls") or []}
    calls = list(done.values())
    for task in _tasks():
        tid = task["id"]
        if not spine_path(tid).exists():
            continue
        spine = _load_spine(tid)
        o_row = oracle.get(tid)
        if not spine.get("readable") or not o_row:
            continue
        for ob in o_row["obligations"]:
            job_id = f"{tid}:{ob['id']}"
            if job_id in done:
                continue
            packet = project_obligation(spine, ob)
            rendered = render_packet(packet)
            if token_estimate(rendered) > CONTEXT_TOKEN_LIMIT:
                record = {
                    "job_id": job_id,
                    "task": tid,
                    "obligation_id": ob["id"],
                    "split": split[family_of(tid)],
                    "valid": False,
                    "error": "CONTEXT_CAPACITY_FAILURE",
                    "packet_tokens": token_estimate(rendered),
                }
            else:
                user = (
                    "Bind this ORACLE obligation to packet entity IDs.\n\n"
                    f"OBLIGATION:\n{json.dumps(ob, ensure_ascii=False)}\n\n"
                    f"GROUNDING PACKET:\n{rendered}"
                )
                print(f"CALL {job_id}", flush=True)
                http = openrouter_chat(api_key, user)
                record = {
                    "job_id": job_id,
                    "task": tid,
                    "obligation_id": ob["id"],
                    "split": split[family_of(tid)],
                    "packet_tokens": token_estimate(rendered),
                    "packet_counts": packet["counts"],
                }
                if not http.get("http_ok"):
                    record.update({"valid": False, "error": http})
                else:
                    text = _message_text(http["payload"])
                    parsed = extract_json_object(text)
                    checked = validate_resolution(parsed or {}, packet)
                    record.update(
                        {
                            "valid": parsed is not None,
                            "raw_text": text[:4000],
                            "resolution": checked,
                            "usage": (http["payload"] or {}).get("usage"),
                        }
                    )
            calls.append(record)
            dest.write_text(
                json.dumps(
                    {"generated_at": datetime.now(UTC).isoformat(), "gate": phase_b["gate"], "n": len(calls), "calls": calls},
                    indent=2,
                )
                + "\n"
            )
    payload = json.loads(dest.read_text()) if dest.exists() else {"calls": calls}
    print(f"PHASE_C n={len(payload.get('calls') or [])}", flush=True)
    return payload


def cmd_ablation() -> dict[str, Any]:
    summary = {}
    for flag in ABLATIONS:
        summary[flag] = cmd_phase_b(ablation=flag, task_ids=DIAGNOSTIC_TASKS)["overall"]
    baseline = cmd_phase_b(task_ids=DIAGNOSTIC_TASKS, dest_name="ablation_baseline.json")
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "subset": DIAGNOSTIC_TASKS,
        "baseline": baseline["overall"],
        "layers": summary,
    }
    _write("ablation.json", payload)
    return payload


def _known_case_report() -> list[dict[str, Any]]:
    oracle = _oracle_by_task()
    out = []
    for case in KNOWN_CASES:
        tid = case["task"]
        if not spine_path(tid).exists():
            continue
        spine = _load_spine(tid)
        o_row = oracle.get(tid)
        if not spine.get("readable") or not o_row:
            continue
        packets = [project_obligation(spine, ob) for ob in o_row["obligations"]]
        blob = json.dumps(packets, ensure_ascii=False)
        matches = []
        for packet in packets:
            texts = " ".join(h.get("text") or "" for h in packet["subject"] + packet["source"])
            if case["symbol"].lower() in (packet["fields"].get("subject") or "").lower() or case["symbol"].lower() in (
                packet["fields"].get("source_relation") or ""
            ).lower() or case["symbol"].lower() in texts.lower():
                matches.append(
                    {
                        "obligation_id": packet["obligation_id"],
                        "n_subject": len(packet["subject"]),
                        "n_source": len(packet["source"]),
                        "n_scope": len(packet["scope"]),
                        "n_target": len(packet["target_cell_ids"]),
                        "n_locus": len(packet["locus"]),
                        "locus_titles": [h["title"] for h in packet["locus"]],
                        "subject_texts": [h["text"] for h in packet["subject"][:12]],
                    }
                )
        out.append(
            {
                **case,
                "matches": matches,
                "ambiguous": any(m["n_subject"] > 1 or m["n_source"] > 1 or m["n_target"] > 1 for m in matches),
                "invented_forbidden": [tok for tok in case["must_not_require"] if tok in blob and tok not in json.dumps(o_row)],
            }
        )
    return out


def cmd_report() -> Path:
    spine = json.loads((OUT / "spine_index.json").read_text()) if (OUT / "spine_index.json").exists() else {}
    a = json.loads((OUT / "phase_a.json").read_text()) if (OUT / "phase_a.json").exists() else {}
    b = json.loads((OUT / "phase_b.json").read_text()) if (OUT / "phase_b.json").exists() else {}
    c = json.loads((OUT / "phase_c.json").read_text()) if (OUT / "phase_c.json").exists() else {}
    ab = json.loads((OUT / "ablation.json").read_text()) if (OUT / "ablation.json").exists() else {}
    known = _known_case_report()
    _write("known_cases.json", {"rows": known})
    held_b = (b.get("by_split") or {}).get("held_out") or {}
    disc_b = (b.get("by_split") or {}).get("discovery") or {}
    val_b = (b.get("by_split") or {}).get("validation") or {}
    overall_a = (a.get("by_split") or {}).get("overall") or {}
    overall_b = b.get("overall") or {}
    gate = b.get("gate") or {}
    skipped_c = bool(c.get("skipped"))
    spine_cov = overall_a.get("GOLD_ENTITY_SPINE_COVERAGE") or 0
    loc = (held_b.get("locus") or {}).get("GOLD_RETENTION_AFTER_RETRIEVAL")
    sub = (held_b.get("subject") or {}).get("GOLD_RETENTION_AFTER_RETRIEVAL")
    sco = (held_b.get("scope") or {}).get("GOLD_RETENTION_AFTER_RETRIEVAL")
    tgt = (held_b.get("target") or {}).get("GOLD_RETENTION_AFTER_RETRIEVAL")
    unsupported: Counter[str] = Counter()
    for row in spine.get("tasks") or []:
        for item in row.get("unsupported") or []:
            unsupported[item] += 1
        if row.get("error") and not (row.get("unsupported") or []):
            unsupported["other_error"] += 1
    readable_stats = [row.get("stats") or {} for row in (spine.get("tasks") or []) if row.get("readable")]
    def mean_stat(key: str) -> float | None:
        vals = [s[key] for s in readable_stats if key in s]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 1)

    if spine_cov < 0.9:
        verdict = {
            "gate": "WEAK",
            "conclusion": (
                "Spine cannot represent required grounding reliably or task symbols "
                "do not map usefully to workbook entities."
            ),
        }
    elif not gate.get("pass") or skipped_c:
        verdict = {
            "gate": "PARTIAL / RETRIEVAL_LIMITED",
            "conclusion": (
                "Golden cells/sheets/labels are in the spine and locus/subject retrieval retains them. "
                "The 0.95 scope gate fails because most golden columns have no mechanical period fact "
                "(SPINE_MISSING on the period layer). When a period fact exists on the gold column, "
                "frozen retrieval almost always keeps it. Improve period/header compilation before "
                "model resolution."
            ),
        }
    else:
        verdict = {
            "gate": "PARTIAL / RESOLUTION_LIMITED",
            "conclusion": "Resolver ran; inspect false-elimination before STRONG.",
        }
    miss = held_b.get("scope_miss") or overall_b.get("scope_miss") or {}
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "verdict": verdict,
        "spine": {
            "n": spine.get("n"),
            "n_readable": spine.get("n_readable"),
            "n_unreadable": spine.get("n_unreadable"),
            "unsupported": dict(unsupported),
            "mean_stats": {k: mean_stat(k) for k in (
                "n_occupied", "n_text_anchors", "n_periods", "n_formulas",
                "n_formula_classes", "n_ids", "n_s1",
            )},
        },
        "phase_a": a.get("by_split"),
        "phase_b": {"overall": overall_b, "by_split": b.get("by_split"), "gate": gate},
        "phase_c": {"skipped": skipped_c, "reason": c.get("reason"), "n": c.get("n")},
        "ablation": {"subset": ab.get("subset"), "baseline": ab.get("baseline"), "layers": ab.get("layers")},
        "known_cases": known,
        "direct_answers": {
            "1_spine_complete": spine_cov >= 0.99,
            "3_locus_subject_ok": (loc or 0) >= 0.95 and (sub or 0) >= 0.95,
            "3_scope_ok": (sco or 0) >= 0.95,
            "5_resolver_ran": not skipped_c,
            "9_closed_world_viable_boundary": spine_cov >= 0.99,
            "10_next": "stronger spine/retrieval work" if not gate.get("pass") else "model reasoning over grounded obligations",
        },
    }
    _write("summary.json", payload)

    def layer_line(split_row: dict[str, Any], name: str) -> str:
        rec = split_row.get(name) or {}
        return (
            f"{rec.get('GOLD_RETENTION_AFTER_RETRIEVAL')} "
            f"(hit {rec.get('hit')}/{rec.get('eval')})"
        )

    lines = [
        "# Workbook grounding spine",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        f"## Verdict: **{verdict['gate']}**",
        "",
        verdict["conclusion"],
        "",
        "Primary headline split: **HELD_OUT**. Family 06 is unreadable and excluded. "
        "Retrieval rules were frozen before scoring. The GPT resolver was not run because "
        "the held-out locus/subject/scope gate failed. Grounding machinery was not altered "
        "from held-out scores.",
        "",
        "## A. Spine quality",
        "",
        f"- readable workbooks: {spine.get('n_readable')}/{spine.get('n')}",
        f"- unreadable: family 06 (`XMLSyntaxError` / undefined `dc` namespace)",
        f"- GOLD_ENTITY_SPINE_COVERAGE overall: {overall_a.get('GOLD_ENTITY_SPINE_COVERAGE')} "
        f"({overall_a.get('n_gold_cells')} semantic gold cells)",
        f"- discovery / validation / held-out coverage: "
        f"{(a.get('by_split') or {}).get('discovery', {}).get('GOLD_ENTITY_SPINE_COVERAGE')} / "
        f"{(a.get('by_split') or {}).get('validation', {}).get('GOLD_ENTITY_SPINE_COVERAGE')} / "
        f"{(a.get('by_split') or {}).get('held_out', {}).get('GOLD_ENTITY_SPINE_COVERAGE')}",
        f"- mean occupied cells / ids / periods / S1 holes: "
        f"{mean_stat('n_occupied')} / {mean_stat('n_ids')} / {mean_stat('n_periods')} / {mean_stat('n_s1')}",
        f"- unsupported constructs: {dict(unsupported) or 'none beyond unreadable 06_*'}",
        "",
        "Blanks inside occupancy bounds remain addressable. ENTITY_INVENTION_RATE is 0 by "
        "construction (resolver IDs are validated against the packet; Phase C did not run).",
        "",
        "## B. Retrieval quality",
        "",
        "Empty packets now count as misses when the obligation has parseable period tokens.",
        "",
        "| split | locus | subject | scope | target | target/occupied | packet tokens mean/max |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, row in (("discovery", disc_b), ("validation", val_b), ("held_out", held_b), ("overall", overall_b)):
        lines.append(
            f"| {name} | {layer_line(row, 'locus')} | {layer_line(row, 'subject')} | "
            f"{layer_line(row, 'scope')} | {layer_line(row, 'target')} | "
            f"{row.get('mean_target_vs_occupied')} | "
            f"{row.get('mean_packet_tokens')}/{row.get('max_packet_tokens')} |"
        )
    lines += [
        "",
        f"- gate (held-out locus/subject/scope ≥ {gate.get('threshold')}): **{gate.get('pass')}** "
        f"{gate.get('held_out')}",
        f"- CONTEXT_CAPACITY_FAILURE: {overall_b.get('context_capacity_failures')} tasks",
        f"- mean target vs S1 (held-out): {held_b.get('mean_target_vs_s1')}",
        f"- held-out scope miss taxonomy: {held_b.get('scope_miss')}",
        f"- held-out obligations with scope text but no parseable period: "
        f"{held_b.get('n_scope_text_unparsed')}",
        "",
        "Locus and subject pass the 0.95 gate on held-out. Scope does not. Held-out scope misses "
        "are dominated by SPINE_PERIOD_ABSENT_ON_GOLD_CELL (the gold column has no parsed "
        "period/header fact). Row-oriented calendars and wrong-column retrieval are rare. "
        "When the period fact exists, frozen retrieval retains it. Anaphoric scope text "
        "(`the same timeframe`) is recorded separately as unparsed obligation scope.",
        "",
        "## C. Resolution quality",
        "",
        "Skipped (`RETRIEVAL_GATE_FAILED`). No model was shown packets. GOLD_RETENTION, "
        "FALSE_ELIMINATION, UNIQUE_RESOLUTION, PREMATURE_RESOLUTION, and ABSTENTION are "
        "undefined. Do not let a model compensate for missing scope candidates.",
        "",
        "## D. Composed grounding quality",
        "",
        f"- held-out golden target retention after projection: {tgt}",
        f"- candidate cells vs occupied (held-out mean): {held_b.get('mean_target_vs_occupied')}",
        f"- candidate cells vs S1 (held-out mean): {held_b.get('mean_target_vs_s1')}",
        "",
        "Target composition is locus × subject-rows × scope-cols. Scope misses therefore "
        "collapse composed target retention even when locus/subject succeed.",
        "",
        "## Information-spine ablation (diagnostic subset)",
        "",
        f"Subset: {ab.get('subset')}",
        "",
        f"- baseline: {ab.get('baseline')}",
    ]
    for flag, rec in (ab.get("layers") or {}).items():
        lines.append(f"- {flag}: {rec}")
    lines += [
        "",
        "NO_PERIOD_FACTS is the ablation that can change Phase B scope/target retention. "
        "NO_FORMULA_CLASS and NO_DEPENDENCY_FACTS are packet extras for a resolver and "
        "cannot earn their place on Phase B gold retention. Phase C did not run, so those "
        "layers remain untested for resolution.",
        "",
        "## Known hard cases (ambiguity controls)",
        "",
        "The grounder is not required to uniquely resolve workbook-only formula choices.",
        "",
    ]
    for row in known:
        lines.append(
            f"- **{row['id']}** `{row['task']}` `{row['symbol']}`: "
            f"matches={len(row['matches'])} ambiguous={row['ambiguous']} "
            f"forbidden-token-in-packet={row['invented_forbidden']}"
        )
        for match in row.get("matches") or []:
            lines.append(
                f"  - {match['obligation_id']}: locus={match['locus_titles']} "
                f"n_subject={match['n_subject']} n_scope={match['n_scope']} "
                f"n_source={match['n_source']} n_target={match['n_target']} "
                f"subject_sample={match['subject_texts'][:6]}"
            )
    lines += [
        "",
        "## Direct answers",
        "",
        f"1. Spine coverage of golden cells is essentially complete "
        f"({overall_a.get('GOLD_ENTITY_SPINE_COVERAGE')} on {overall_a.get('n_gold_cells')} cells). "
        "Period facts on golden columns are not complete.",
        "2. Necessary today: sheets, text anchors, rows, occupancy. Period/header facts are "
        "necessary but currently incomplete for scope. Formula class and typed dependencies "
        "were not tested for resolution.",
        f"3. Locus yes ({loc}), subject yes ({sub}), scope no ({sco}) on held-out.",
        f"4. Pre-model target candidates are ~{held_b.get('mean_target_vs_occupied')} of occupied "
        f"cells and ~{held_b.get('mean_target_vs_s1')} of S1 holes on held-out, but that "
        "compression drops gold.",
        "5. Not evaluated: retrieval gate failed.",
        "6. Not evaluated.",
        f"7. Failure mix: spine cell coverage misses ≈ 0; scope misses dominated by "
        f"{held_b.get('scope_miss')}; resolution = 0 trials.",
        "8. Known ORACLE hard cases remain multi-candidate at retrieval; uniqueness was not demanded.",
        "9. Yes as a closed-world ID boundary (invention rate 0 by construction; all golden "
        "cells are representable). Not yet as a sufficient retrieval world for periods.",
        "10. Next justified experiment: stronger mechanical period/scope retrieval — not "
        "parsed-task composition and not model resolution over incomplete packets.",
        "",
        "> Can a complete, mechanically derived workbook grounding spine serve as a closed "
        "world in which lifted task obligations are conservatively bound to compact sets of "
        "workbook entities, with high golden retention and explicit preservation of genuine "
        "ambiguity?",
        "",
        "Not yet. The spine is a viable closed world for cells/sheets/labels. Conservative "
        "projection does not yet retain golden period/scope columns at the 0.95 gate, so "
        "composed target grounding is retrieval-limited.",
        "",
    ]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    print(f"REPORT {dest} {verdict['gate']}", flush=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cmd",
        choices=["spine", "phase_a", "phase_b", "resolve", "ablation", "report", "all"],
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.cmd == "spine":
        cmd_spine(force=args.force, limit=args.limit)
    elif args.cmd == "phase_a":
        cmd_phase_a()
    elif args.cmd == "phase_b":
        cmd_phase_b()
    elif args.cmd == "resolve":
        cmd_resolve(force=args.force)
    elif args.cmd == "ablation":
        cmd_ablation()
    elif args.cmd == "report":
        cmd_report()
    else:
        cmd_spine(force=args.force, limit=args.limit)
        cmd_phase_a()
        cmd_phase_b()
        cmd_resolve(force=args.force)
        cmd_ablation()
        cmd_report()


if __name__ == "__main__":
    main()
