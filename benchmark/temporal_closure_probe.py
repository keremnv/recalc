#!/usr/bin/env python3
"""Compile E1–E3 temporal provenance closure and rerun frozen grounding.

Gold-blind compilation. No retrieval-rule changes, no GPT/GLM, no V1 edits.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
sys.path.insert(0, str(ROOT / "benchmark/sweagent/formula_index/lib"))
sys.path.insert(0, str(ROOT / "src"))

import temporal_spine_probe as tsp  # noqa: E402
from task_obligation_shape import family_of, is_semantic_change  # noqa: E402
from temporal_spine import compile_temporal_workbook, overlay_periods  # noqa: E402
from workbook_grounding import gold_entities, parse_scope_spec, project_obligation  # noqa: E402
from workbook_grounding_probe import (  # noqa: E402
    DATA,
    cmd_phase_b,
    _delta_by_task,
    _load_spine,
    _oracle_by_task,
    _split_map,
    _tasks,
    spine_path,
)

SPINE_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-spine-probe"
GROUNDING_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/workbook-grounding-probe"
DEPTH_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-provenance-depth"
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/temporal-closure-probe"
PREDICTED_COVERAGE = 0.934
KNOWN = [
    {"id": "J46", "task": "08_01", "symbol": "Receivables"},
    {"id": "AF66", "task": "08_01", "symbol": "30%"},
    {"id": "H41", "task": "20_04", "symbol": "days-based linkage"},
    {"id": "D10", "task": "14_05", "symbol": "effective tax rate"},
    {"id": "J31", "task": "14_05", "symbol": "Total Revenue"},
    {"id": "K163", "task": "09_05", "symbol": "Other Long-Term Assets"},
    {"id": "K6", "task": "04_05", "symbol": "total growth rates"},
    {"id": "K104", "task": "17_03", "symbol": "percentage of Revenue"},
    {"id": "Y39", "task": "15_04", "symbol": "EPS Growth"},
]


def _write(name: str, payload: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def _frozen_features() -> set[str]:
    path = SPINE_OUT / "frozen_v2.json"
    if path.exists():
        return set(json.loads(path.read_text()).get("features") or [])
    return set(tsp.ALL_FEATURES)


def cmd_compile(*, force: bool = False, limit: int | None = None) -> dict[str, Any]:
    features = _frozen_features()
    dest_dir = OUT / "coords"
    dest_dir.mkdir(parents=True, exist_ok=True)
    split = _split_map()
    rows = []
    t0 = time.perf_counter()
    tasks = _tasks()
    if limit is not None:
        tasks = tasks[:limit]
    for task in tasks:
        tid = task["id"]
        dest = dest_dir / f"{tid}.json"
        if dest.exists() and not force:
            compiled = json.loads(dest.read_text())
        else:
            path = DATA / "Financial_Model" / task["spreadsheet_path"]
            print(f"CLOSE {tid}", flush=True)
            started = time.perf_counter()
            compiled = compile_temporal_workbook(path, features=features, closure=True)
            compiled["compile_s"] = round(time.perf_counter() - started, 3)
            slim = {
                "readable": compiled.get("readable"),
                "error": compiled.get("error"),
                "features": compiled.get("features"),
                "n_sheets": compiled.get("n_sheets"),
                "n_coordinates": compiled.get("n_coordinates"),
                "n_local_coordinates": compiled.get("n_local_coordinates"),
                "n_propagated_coordinates": compiled.get("n_propagated_coordinates"),
                "coordinates": compiled.get("coordinates") or [],
                "temporal_conflicts": compiled.get("temporal_conflicts") or [],
                "closure": compiled.get("closure"),
                "golden_used": compiled.get("golden_used"),
                "compile_s": compiled.get("compile_s"),
            }
            dest.write_text(json.dumps(slim) + "\n")
            compiled = slim
        fam = family_of(tid)
        rows.append(
            {
                "task": tid,
                "split": split.get(fam),
                "family": fam,
                "readable": compiled.get("readable"),
                "n_local": compiled.get("n_local_coordinates"),
                "n_propagated": compiled.get("n_propagated_coordinates"),
                "n_coordinates": compiled.get("n_coordinates"),
                "n_conflicts": len(compiled.get("temporal_conflicts") or []),
                "closure": compiled.get("closure"),
                "compile_s": compiled.get("compile_s"),
                "golden_used": compiled.get("golden_used"),
                "error": compiled.get("error"),
            }
        )
    elapsed = time.perf_counter() - t0
    by_split: dict[str, dict[str, Any]] = {}
    for name in ("discovery", "validation", "held_out"):
        picked = [r for r in rows if r["split"] == name]
        closures = [r.get("closure") or {} for r in picked]
        by_split[name] = {
            "n_tasks": len(picked),
            "n_local": sum(int(r.get("n_local") or 0) for r in picked),
            "n_propagated": sum(int(r.get("n_propagated") or 0) for r in picked),
            "n_total": sum(int(r.get("n_coordinates") or 0) for r in picked),
            "n_conflicts": sum(int(r.get("n_conflicts") or 0) for r in picked),
            "n_opaque": sum(int((c.get("n_opaque") or 0)) for c in closures),
            "n_cycle": sum(int((c.get("n_cycle") or 0)) for c in closures),
            "n_closure_limit": sum(int((c.get("n_closure_limit") or 0)) for c in closures),
            "visited_total": sum(int((c.get("visited_total") or 0)) for c in closures),
            "edges": {
                "E1": sum(int(((c.get("edges") or {}).get("E1") or 0)) for c in closures),
                "E2": sum(int(((c.get("edges") or {}).get("E2") or 0)) for c in closures),
                "E3": sum(int(((c.get("edges") or {}).get("E3") or 0)) for c in closures),
            },
        }
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "golden_used": False,
        "features": sorted(features),
        "wall_s": round(elapsed, 3),
        "n": len(rows),
        "n_readable": sum(1 for r in rows if r["readable"]),
        "overall": {
            "n_local": sum(int(r.get("n_local") or 0) for r in rows),
            "n_propagated": sum(int(r.get("n_propagated") or 0) for r in rows),
            "n_total": sum(int(r.get("n_coordinates") or 0) for r in rows),
            "n_conflicts": sum(int(r.get("n_conflicts") or 0) for r in rows),
        },
        "by_split": by_split,
        "tasks": rows,
    }
    _write("compile.json", payload)
    print(
        f"COMPILE readable={payload['n_readable']}/{payload['n']} "
        f"local={payload['overall']['n_local']} prop={payload['overall']['n_propagated']} "
        f"conflicts={payload['overall']['n_conflicts']} {elapsed:.1f}s",
        flush=True,
    )
    return payload


def _stage_eval_inputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("population.json", "frozen_v2.json"):
        src = SPINE_OUT / name
        if src.exists():
            shutil.copyfile(src, OUT / name)


def cmd_evaluate() -> dict[str, Any]:
    _stage_eval_inputs()
    prev_out = tsp.OUT
    tsp.OUT = OUT
    try:
        coverage = tsp.cmd_coverage()
        retrieve = tsp.cmd_retrieve(strict=True)
        funnel = tsp.cmd_funnel()
        examples = tsp.cmd_examples()
    finally:
        tsp.OUT = prev_out
    return {"coverage": coverage, "retrieve": retrieve, "funnel": funnel, "examples": examples}


def cmd_phase_b_overlay() -> dict[str, Any]:
    return cmd_phase_b(
        dest_name="phase_b_temporal_closure.json",
        overlay_coords_dir=OUT / "coords",
        strict_scope=False,
    )


def cmd_known() -> dict[str, Any]:
    oracle = _oracle_by_task()
    delta = _delta_by_task()
    out = []
    for case in KNOWN:
        tid = case["task"]
        compiled = json.loads((OUT / "coords" / f"{tid}.json").read_text()) if (OUT / "coords" / f"{tid}.json").exists() else {}
        spine = overlay_periods(_load_spine(tid), compiled) if spine_path(tid).exists() and compiled.get("readable") else {}
        o_row = oracle.get(tid) or {}
        d_row = delta.get(tid) or {}
        packets = []
        gold_kept = None
        n_targets = None
        if spine:
            for ob in o_row.get("obligations") or []:
                packet = project_obligation(spine, ob, strict_scope=True)
                fields = json.dumps(packet.get("fields") or {})
                if case["symbol"].lower() in fields.lower():
                    packets.append(
                        {
                            "obligation_id": packet["obligation_id"],
                            "scope_text": (packet.get("fields") or {}).get("scope"),
                            "n_scope": len(packet["scope"]),
                            "n_target_strict": len(packet["target_cell_ids"]),
                            "n_subject": len(packet["subject"]),
                        }
                    )
            semantic = [c for c in d_row.get("changes") or [] if is_semantic_change(c)]
            gold_ids = {gold_entities(spine, c)["cell_id"] for c in semantic}
            gold_ids.discard(None)
            target_ids = set()
            for ob in o_row.get("obligations") or []:
                target_ids.update(project_obligation(spine, ob, strict_scope=True)["target_cell_ids"])
            n_targets = len(target_ids)
            gold_kept = round(len(gold_ids & target_ids) / len(gold_ids), 4) if gold_ids else None
        coords = [
            {
                "id": c["id"],
                "axis": c.get("axis"),
                "address": c.get("address"),
                "period": c.get("period"),
                "derivation_status": c.get("derivation_status"),
                "path_length": c.get("path_length"),
                "seed_cell": c.get("seed_cell"),
                "compact": ((c.get("provenance") or [{}])[0].get("compact")),
            }
            for c in (compiled.get("coordinates") or [])
            if c.get("derivation_status") == "PROPAGATED_TEMPORAL_COORDINATE"
        ][:8]
        out.append(
            {
                **case,
                "n_local": compiled.get("n_local_coordinates"),
                "n_propagated": compiled.get("n_propagated_coordinates"),
                "n_conflicts": len(compiled.get("temporal_conflicts") or []),
                "propagated_sample": coords,
                "packets": packets[:6],
                "n_target_union_strict": n_targets,
                "gold_in_strict_targets": gold_kept,
            }
        )
    payload = {"generated_at": datetime.now(UTC).isoformat(), "cases": out}
    _write("known_cases.json", payload)
    return payload


def cmd_report() -> Path:
    compile_doc = json.loads((OUT / "compile.json").read_text()) if (OUT / "compile.json").exists() else {}
    cov = json.loads((OUT / "coverage.json").read_text()) if (OUT / "coverage.json").exists() else {}
    ret = json.loads((OUT / "retrieve.json").read_text()) if (OUT / "retrieve.json").exists() else {}
    funnel = json.loads((OUT / "funnel.json").read_text()) if (OUT / "funnel.json").exists() else {}
    known = json.loads((OUT / "known_cases.json").read_text()) if (OUT / "known_cases.json").exists() else {}
    prev_cov = json.loads((SPINE_OUT / "coverage.json").read_text()) if (SPINE_OUT / "coverage.json").exists() else {}
    prev_ret = json.loads((SPINE_OUT / "retrieve.json").read_text()) if (SPINE_OUT / "retrieve.json").exists() else {}
    prev_funnel = json.loads((SPINE_OUT / "funnel.json").read_text()) if (SPINE_OUT / "funnel.json").exists() else {}
    v1 = json.loads((GROUNDING_OUT / "phase_b.json").read_text()) if (GROUNDING_OUT / "phase_b.json").exists() else {}
    held_c = (cov.get("by_split") or {}).get("held_out") or {}
    held_r = (ret.get("by_split") or {}).get("held_out") or {}
    prev_held_c = (prev_cov.get("by_split") or {}).get("held_out") or {}
    prev_held_r = (prev_ret.get("by_split") or {}).get("held_out") or {}
    coverage = held_c.get("GOLD_TEMPORAL_COORDINATE_COVERAGE") or 0
    scope = ((held_r.get("scope") or {}).get("GOLD_RETENTION")) or 0
    miss = held_r.get("scope_miss") or {}
    represented = (miss.get("SCOPE_HIT") or 0) + (miss.get("RETRIEVAL_MISSING") or 0)
    cond = round((miss.get("SCOPE_HIT") or 0) / represented, 4) if represented else None
    strict = ((held_r.get("target_strict") or {}).get("GOLD_RETENTION"))
    fallback = ((held_r.get("target_fallback") or {}).get("GOLD_RETENTION"))
    delta = round(coverage - PREDICTED_COVERAGE, 4)
    unparsed = cov.get("unparsed_by_split") or {}
    if coverage < 0.80:
        gate = "IMPLEMENTATION_FAILURE"
        conclusion = "Actual closure coverage did not reproduce the preflight. Diagnose before resolver."
    elif coverage >= 0.90 and (cond or 0) >= 0.95 and (strict or 0) > ((prev_held_r.get("target_strict") or {}).get("GOLD_RETENTION") or 0) + 0.05:
        gate = "RESOLVER_JUSTIFIED"
        conclusion = "Held-out temporal coverage and retrieval justify a closed-world resolver experiment."
    else:
        gate = "PARTIAL"
        conclusion = (
            "Closure works mechanically but composed grounding and/or coverage remain below the resolver gate."
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "gate": gate,
        "conclusion": conclusion,
        "actual_held_out_coverage": coverage,
        "predicted_coverage": PREDICTED_COVERAGE,
        "delta_vs_preflight": delta,
        "local_v2_coverage": prev_held_c.get("GOLD_TEMPORAL_COORDINATE_COVERAGE"),
        "v1_scope": ((v1.get("by_split") or {}).get("held_out") or {}).get("scope"),
        "scope_retention": scope,
        "retrieval_given_represented": cond,
        "strict_target": strict,
        "fallback_target": fallback,
        "scope_miss": miss,
        "unparsed_by_split": unparsed,
        "compile": {
            "wall_s": compile_doc.get("wall_s"),
            "overall": compile_doc.get("overall"),
            "by_split": compile_doc.get("by_split"),
            "golden_used": compile_doc.get("golden_used"),
        },
    }
    _write("summary.json", payload)
    lines = [
        "# Temporal provenance closure confirmation",
        "",
        "Gold-blind E1–E3 closure materialized into TEMPORAL_COORDINATE. Retrieval rules unchanged. No GPT/GLM.",
        "",
        f"- golden_used: {compile_doc.get('golden_used')}",
        f"- compile wall: {compile_doc.get('wall_s')}s",
        f"- local / propagated / total: {compile_doc.get('overall')}",
        f"- conflicts: {(compile_doc.get('overall') or {}).get('n_conflicts')}",
        "",
        "## Coverage (scope-evaluable gold cells)",
        "",
        f"- V1 scope retention (prior phase B): {(payload['v1_scope'] or {}).get('GOLD_RETENTION_AFTER_RETRIEVAL') if isinstance(payload['v1_scope'], dict) else payload['v1_scope']}",
        f"- local V2: {payload['local_v2_coverage']}",
        f"- predicted closure: {PREDICTED_COVERAGE}",
        f"- **actual closure: {coverage}** (delta {delta})",
        f"- by split: `{ {k: (cov.get('by_split') or {}).get(k, {}).get('GOLD_TEMPORAL_COORDINATE_COVERAGE') for k in ('discovery', 'validation', 'held_out')} }`",
        "",
        "## Scope retrieval",
        "",
        f"- held-out scope retention: {scope}",
        f"- retrieval given represented: {cond}",
        f"- miss taxonomy: `{miss}`",
        f"- TASK_SCOPE_UNPARSED by split: `{unparsed}`",
        "",
        "## Targets",
        "",
        f"- STRICT_TARGET_RETENTION: {strict} (was {(prev_held_r.get('target_strict') or {}).get('GOLD_RETENTION')})",
        f"- FALLBACK_TARGET_RETENTION: {fallback} (was {(prev_held_r.get('target_fallback') or {}).get('GOLD_RETENTION')})",
        f"- target vs occupied: {(held_r.get('mean_target_vs_occupied'))} (was {prev_held_r.get('mean_target_vs_occupied')})",
        "",
        "## Funnel held-out",
        "",
        f"- previous: `{(prev_funnel.get('by_split') or {}).get('held_out')}`",
        f"- closure: `{(funnel.get('by_split') or {}).get('held_out')}`",
        "",
        "## Compile by split",
        "",
        f"`{compile_doc.get('by_split')}`",
        "",
        "## Known cases",
        "",
    ]
    for case in known.get("cases") or []:
        lines.append(
            f"- **{case.get('id')}** `{case.get('task')}` propagated={case.get('n_propagated')} "
            f"conflicts={case.get('n_conflicts')} gold_in_strict={case.get('gold_in_strict_targets')} "
            f"n_target={case.get('n_target_union_strict')}"
        )
    lines += [
        "",
        "## Gate",
        "",
        f"**{gate}**",
        "",
        conclusion,
        "",
        "## Direct answers",
        "",
        f"a. Actual vs predicted: {coverage} vs {PREDICTED_COVERAGE} (delta {delta}).",
        f"b. Held-out temporal coverage: {coverage}.",
        f"c. Retrieval given represented: {cond}.",
        f"d. Strict target {strict}; fallback {fallback}; compression {held_r.get('mean_target_vs_occupied')}.",
        f"e. Residual miss: `{miss}`.",
        f"f. Unparsed task-side: `{unparsed}`.",
        f"g. See known cases.",
        f"h. Gate={gate}.",
        "",
    ]
    dest = OUT / "report.md"
    dest.write_text("\n".join(lines) + "\n")
    print(f"REPORT {dest} {gate} coverage={coverage} scope={scope} strict={strict}", flush=True)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compile", "evaluate", "phase_b", "known", "report", "all"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.cmd == "compile":
        cmd_compile(force=args.force, limit=args.limit)
    elif args.cmd == "evaluate":
        cmd_evaluate()
    elif args.cmd == "phase_b":
        cmd_phase_b_overlay()
    elif args.cmd == "known":
        cmd_known()
    elif args.cmd == "report":
        cmd_report()
    else:
        cmd_compile(force=args.force, limit=args.limit)
        cmd_evaluate()
        cmd_known()
        cmd_phase_b_overlay()
        cmd_report()


if __name__ == "__main__":
    main()
