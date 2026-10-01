#!/usr/bin/env python3
"""Separately frozen replication of the Edit Plan experiment.

Same 18 tasks, same GLM 5.3 Flash configuration, same Task IR, same Edit Plan
language and schema, same plan prompt (byte-identical), same grounding, same
retrieval, same synthesis logic, same deterministic expansion.

Only three harness defects found in the primary run are fixed, plus one resource
boundary that does not touch scoring:

  FIX 1  ID contract     citations accept every closed-world identity namespace
                         the grounding contract actually exposes (V2).
  FIX 2  Phase transition  synthesis gets its own system prompt instead of
                         reusing the retrieval protocol prompt.
  FIX 3  Writer neutrality  cells are written at the archive level, so a
                         zero-write round trip is byte-identical and scores
                         regression 1.0. Gated before any model call.
  GATE   Execution admissibility  an excessive expansion is not executed
                         downstream. Raw expansion is still scored in full;
                         inadmissibility never counts as target correctness.

The primary run's artifacts are never written by this module.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_plan_probe as base
from edit_plan import World, PlanError, expand_edit_plan

old = base.old
OUT = old.MECHANICAL / "edit-plan-replication-probe"
SOURCE = base.OUT
ID_CONTRACT = "V2"

# Predeclared before any model call. The largest gold target set in this
# population is 1,033 cells, so the per-operation cap leaves roughly five times
# the largest legitimate need; the sheet-fraction rule catches "select the whole
# sheet" plans that stay under the absolute cap on small sheets.
ADMISSIBILITY = {
    "max_operation_cells": 5000,
    "max_plan_cells": 20000,
    "max_sheet_fraction": 0.5,
    "rationale": "Resource and safety boundary on execution only. Raw expansion is scored in full; an inadmissible plan is never credited with target correctness.",
}
LIMITS = {**base.LIMITS, "id_contract": ID_CONTRACT, "admissibility": ADMISSIBILITY}


def save(name, data):
    old.write(OUT / name, data)


def sheet_area(world, sheet_id):
    s = world.sheets[sheet_id]
    return max(1, (s["used_r2"] - s["used_r1"] + 1) * (s["used_c2"] - s["used_c1"] + 1))


def expansion_audit(expansion, world):
    """Classify execution admissibility. Never alters the expansion or its metrics."""
    findings = []
    total = len(expansion["cell_ids"])
    for op in expansion["operations"]:
        n = len(op["cell_ids"])
        sheets = {c.rsplit(":", 2)[0].replace("cell:", "sheet:") for c in op["cell_ids"]}
        fraction = max((n / sheet_area(world, s) for s in sheets if s in world.sheets), default=0.0)
        reasons = []
        if n > ADMISSIBILITY["max_operation_cells"]:
            reasons.append(f"operation expands to {n} cells (cap {ADMISSIBILITY['max_operation_cells']})")
        if fraction > ADMISSIBILITY["max_sheet_fraction"]:
            reasons.append(f"operation covers {fraction:.0%} of a sheet's used area (cap {ADMISSIBILITY['max_sheet_fraction']:.0%})")
        findings.append({"operation_id": op["operation_id"], "cells": n, "max_sheet_fraction": round(fraction, 4),
                         "admissible": not reasons, "reasons": reasons})
    plan_reasons = [f"plan expands to {total} cells (cap {ADMISSIBILITY['max_plan_cells']})"] if total > ADMISSIBILITY["max_plan_cells"] else []
    return {"total_cells": total, "operations": findings, "plan_reasons": plan_reasons,
            "admissible_operation_ids": [f["operation_id"] for f in findings if f["admissible"]] if not plan_reasons else [],
            "plan_admissible": not plan_reasons and all(f["admissible"] for f in findings),
            "executable": not plan_reasons and any(f["admissible"] for f in findings)}


def plan_task(taskrow, key):
    task = taskrow["task"]
    dest = OUT / f"phase_b/{task}.json"
    if dest.exists():
        return old.load(dest)
    start = time.perf_counter()
    # Same Task IR and same grounding as the primary run: the compiler output is
    # reused verbatim and the packets are recomputed deterministically from it.
    compiler = old.load(SOURCE / f"compiler/{task}.json")["compiler"]
    spine = old._load_spine(task)
    world = World(old.relational.db_path(task))
    obligations = compiler["obligations"]
    packets = {ob["id"]: old.project_obligation(spine, ob) for ob in obligations}
    context = base.plan_context(task, compiler, packets, world)
    save(f"contexts/{task}.json", context)
    response = old.call_glm(key, base.PLAN_PROMPT, json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                            "librecalc-edit-plan-replication", LIMITS["plan_output_tokens"])
    parsed = old.extract_json_object(response.get("text", "")) if response.get("http_ok") else None
    expansion = audit = None
    error = None
    if not response.get("http_ok"):
        status = "MODEL_ACCESS_FAILURE"
    elif parsed is None:
        status = "INVALID_SCHEMA"
    else:
        try:
            expansion = expand_edit_plan(parsed, world, {o["id"] for o in obligations}, ID_CONTRACT)
            status = expansion["status"]
            audit = expansion_audit(expansion, world)
        except PlanError as exc:
            status, error = exc.category, str(exc)
    gold = base.gold_ids(task, world)
    found = set(expansion["cell_ids"]) if expansion else set()
    row = {"task": task, "status": status, "error": error, "id_contract": ID_CONTRACT,
           "compiler_reused_from_primary": True, "compiler": compiler,
           "compiler_eval": old.task_ir_eval(task, obligations, compiler["raw_task"]),
           "grounding": {"packets": packets, "evaluation": old.grounding_eval(task, obligations, packets, spine)},
           "response": response, "parsed": parsed, "expansion": expansion, "expansion_audit": audit,
           # Raw expansion metrics: computed on the full expansion regardless of
           # admissibility, so a rejected plan never looks more correct.
           "metrics": {"gold_count": len(gold), "expanded_count": len(found), "true_targets": len(found & gold),
                       "false_targets": len(found - gold), "missed_targets": len(gold - found),
                       "precision": len(found & gold) / len(found) if found else 0,
                       "recall": len(found & gold) / len(gold) if gold else None,
                       "plan_tokens": base.tokens(parsed) if parsed else None,
                       "context_tokens_estimate": base.tokens(context)},
           "elapsed_s": time.perf_counter() - start}
    save(f"phase_b/{task}.json", row)
    world.close()
    print(json.dumps({"task": task, "status": status, "admissible": (audit or {}).get("plan_admissible"), **row["metrics"]}), flush=True)
    return row


def freeze():
    if (OUT / "freeze.json").exists():
        raise RuntimeError("Already frozen")
    gate = old.load(old.MECHANICAL / "writer-neutrality-gate/gate.json")
    if not gate["pass"]:
        raise RuntimeError("Writer neutrality gate has not passed; model spend is not authorized")
    primary = old.load(SOURCE / "freeze.json")
    if hashlib.sha256(base.PLAN_PROMPT.encode()).hexdigest() != primary["plan_prompt_sha256"]:
        raise RuntimeError("Plan prompt is not byte-identical to the primary run")
    paths = [Path(__file__), Path(__file__).with_name("edit_plan.py"), Path(__file__).with_name("xlsx_cell_writer.py"),
             base.CONTRACT, Path(old.__file__)]
    save("freeze.json", {
        "limits": LIMITS,
        "sha256": {str(p.relative_to(old.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "plan_prompt_sha256": primary["plan_prompt_sha256"],
        "identical_to_primary": ["18-task population", "plan prompt", "Edit Plan schema and contract text",
                                 "Task IR (compiler output reused verbatim)", "grounding projection",
                                 "retrieval protocol and SQL limits", "synthesis proposal schema",
                                 "downstream selection rule", "GLM 5.3 Flash config: temperature 0, medium reasoning"],
        "changed": {"id_contract": "V2 accepts text anchors, rows, columns, workbook and period identities; period ids resolve per axis. Target-set algebra unchanged.",
                    "synthesis_system_prompt": "Phase-specific prompt replaces the reused retrieval protocol prompt.",
                    "writer": "Archive-level cell writer; zero-write round trip is byte-identical.",
                    "execution_admissibility": ADMISSIBILITY},
        "writer_gate": {k: gate[k] for k in ("gate", "tasks", "passing", "pass")},
        "not_changed": "No prompt tuning, no retries, no repair calls, no language primitives added, no new retrieval rules.",
    })
    print("Frozen", flush=True)


def check_freeze():
    f = old.load(OUT / "freeze.json")
    for name, digest in f["sha256"].items():
        if name == str(Path(__file__).relative_to(old.ROOT)):
            continue
        if hashlib.sha256((old.ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Frozen component changed: {name}")
    if hashlib.sha256(base.PLAN_PROMPT.encode()).hexdigest() != f["plan_prompt_sha256"]:
        raise RuntimeError("Prompt changed")
    old.guard(LIMITS["model"])


def phase_b():
    check_freeze()
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=LIMITS["workers"]) as pool:
        futures = {pool.submit(plan_task, r, key): r["task"] for r in old.load(base.POP)["rows"]}
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as exc:
                task = futures[f]
                save(f"phase_b/{task}.json", {"task": task, "status": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}"})
                print(task, type(exc).__name__, str(exc), flush=True)
    frontend_report()


def frontend_report():
    rows = [old.load(p) for p in sorted((OUT / "phase_b").glob("*.json"))]
    scored = [r for r in rows if r.get("metrics", {}).get("gold_count")]
    sel = sum(r["metrics"]["expanded_count"] for r in scored)
    true = sum(r["metrics"]["true_targets"] for r in scored)
    gold = sum(r["metrics"]["gold_count"] for r in scored)
    report = {
        "attempted_tasks": len(rows), "quality_tasks": len(scored),
        "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
        "micro_recall": true / gold if gold else None, "micro_precision": true / sel if sel else None,
        "true_targets": true, "expanded_targets": sel, "gold_targets": gold,
        "valid_plan_rate": sum(r["status"] in ("VALID_PLAN", "EMPTY_EXPANSION") for r in scored) / len(scored) if scored else None,
        "parse_rate": sum(isinstance(r.get("parsed"), dict) for r in rows) / len(rows),
        "admissible_plan_tasks": sum(bool((r.get("expansion_audit") or {}).get("plan_admissible")) for r in rows),
        "executable_plan_tasks": sum(bool((r.get("expansion_audit") or {}).get("executable")) for r in rows),
        "inadmissible": [{"task": r["task"], "cells": r["expansion_audit"]["total_cells"],
                          "reasons": r["expansion_audit"]["plan_reasons"] + [x for f in r["expansion_audit"]["operations"] for x in f["reasons"]],
                          "raw_recall": r["metrics"]["recall"], "raw_precision": r["metrics"]["precision"]}
                         for r in rows if r.get("expansion_audit") and not r["expansion_audit"]["plan_admissible"]],
        "rows": [{"task": r["task"], "status": r["status"], "error": r.get("error"),
                  "plan_admissible": (r.get("expansion_audit") or {}).get("plan_admissible"), **r.get("metrics", {})} for r in rows],
    }
    save("frontend_report.json", report)
    print(json.dumps({k: report[k] for k in ("attempted_tasks", "status_counts", "micro_recall", "micro_precision",
                                             "valid_plan_rate", "admissible_plan_tasks", "true_targets", "expanded_targets")}, indent=2))
    return report


def select_downstream():
    if (OUT / "downstream_selection.json").exists():
        return old.load(OUT / "downstream_selection.json")
    pop = old.load(base.POP)["rows"]
    order = [r["task"] for r in pop if r["task"] in old.KNOWN_TASKS] + [r["task"] for r in pop if r["task"] not in old.KNOWN_TASKS]
    candidates, audits, blocked = {}, {}, {}
    for task in order:
        r = old.load(OUT / f"phase_b/{task}.json")
        if not r.get("expansion"):
            continue
        audit = r["expansion_audit"]
        if not audit["executable"]:
            blocked[task] = audit["plan_reasons"] + [x for f in audit["operations"] for x in f["reasons"]]
            continue
        allowed = set(audit["admissible_operation_ids"])
        world = World(old.relational.db_path(task))
        groups = [g for g in base.execution_groups(r, world) if g["operation_id"] in allowed]
        world.close()
        audits[task] = groups
        queue = []
        for endpoint in (0, -1):
            for op in groups:
                if op["operation_kind"] == "CLEAR_CELL" or not op["cell_ids"]:
                    continue
                cid = op["cell_ids"][endpoint]
                if any(x["cell_id"] == cid for x in queue):
                    continue
                if endpoint == -1 and op["mode"] == "SYNTHESIZE_ONCE_TRANSLATE":
                    continue
                queue.append({"task": task, "cell_id": cid, "obligation_id": op["obligation_id"], "operation_id": op["operation_id"],
                              "mode": op["mode"], "execution_cell_ids": op["cell_ids"] if op["mode"] == "SYNTHESIZE_ONCE_TRANSLATE" else [cid],
                              "selection_reason": "operation-first/last-address round robin; evaluator blind"})
        candidates[task] = queue[:LIMITS["per_task_sessions"]]
    selected = []
    for i in range(LIMITS["per_task_sessions"]):
        for task in order:
            if i < len(candidates.get(task, [])) and len(selected) < LIMITS["downstream_sessions"]:
                selected.append(candidates[task][i])
    for i, x in enumerate(selected):
        x["session_id"] = f"session{i+1:02d}"
    censored = {}
    for task, groups in audits.items():
        allids = {cid for op in groups for cid in op["cell_ids"]}
        executed = {cid for x in selected if x["task"] == task for cid in x["execution_cell_ids"]}
        censored[task] = sorted(allids - executed, key=base.coord)
    data = {"selected": selected, "execution_audit": audits, "censored_target_ids": censored,
            "blocked_by_admissibility_gate": blocked, "gold_used_for_selection": False}
    save("downstream_selection.json", data)
    return data


def downstream_session(job, key):
    path = OUT / f"sessions/{job['session_id']}.json"
    if path.exists():
        return old.load(path)
    task = job["task"]
    r = old.load(OUT / f"phase_b/{task}.json")
    spine = old._load_spine(task)
    ob = next(o for o in r["compiler"]["obligations"] if o["id"] == job["obligation_id"])
    target = old.target_address(spine, job["cell_id"])
    info = old.input_cell_info(task, target["sheet"], target["address"])
    target.update({"target_id": job["cell_id"], "current_input_content": info["raw_value"], "current_input_kind": info["kind"]})
    start = time.perf_counter()
    try:
        session = old.run_target(task, r["compiler"]["raw_task"], ob, target, r["grounding"]["packets"][ob["id"]], spine, key,
                                 synthesis_system=old.SYNTHESIS_SYSTEM)
    except Exception as exc:
        session = {"status": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}", "target": target}
    session["job"] = job
    session["wall_seconds"] = time.perf_counter() - start
    save(f"sessions/{job['session_id']}.json", session)
    parsed = (session.get("synthesis") or {}).get("parsed") or {}
    print(json.dumps({"session": job["session_id"], "task": task, "target": target["address"], "status": session["status"],
                      "proposal_status": parsed.get("status") or (f"RETRIEVAL_ACTION_{parsed.get('action')}" if parsed.get("action") else "UNPARSEABLE"),
                      "formula": parsed.get("formula")}), flush=True)
    return session


def downstream():
    check_freeze()
    selection = select_downstream()
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    spent = sum(old.load(p).get("retrieval_input_tokens", 0) + old.load(p).get("synthesis_input_tokens", 0)
                for p in (OUT / "sessions").glob("*.json")) if (OUT / "sessions").exists() else 0
    # Concurrency is an execution-environment concession, not an experiment
    # variable: this host OOM-killed the run at two workers. It changes wall
    # time only. Every session's inputs, prompts and limits are unaffected.
    workers = max(1, int(os.environ.get("EDIT_PLAN_DOWNSTREAM_WORKERS", "2")))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [j for j in selection["selected"] if not (OUT / f"sessions/{j['session_id']}.json").exists()]
        for i in range(0, len(jobs), workers):
            if spent >= LIMITS["total_downstream_input_soft_cap"]:
                for job in jobs[i:]:
                    save(f"sessions/{job['session_id']}.json", {"job": job, "status": "RESOURCE_CENSORED_NOT_RUN"})
                break
            for f in [pool.submit(downstream_session, j, key) for j in jobs[i:i+workers]]:
                r = f.result()
                spent += r.get("retrieval_input_tokens", 0) + r.get("synthesis_input_tokens", 0)
    actuate()


def actuate():
    """Archive-level actuation. Untouched parts of the workbook stay byte-identical."""
    from openpyxl.formula.translate import Translator
    from xlsx_cell_writer import write_cells
    grouped = defaultdict(list)
    for p in sorted((OUT / "sessions").glob("*.json")):
        r = old.load(p)
        grouped[r["job"]["task"]].append(r)
    for task, sessions in grouped.items():
        if (OUT / f"actuation/{task}.json").exists():
            continue
        spine = old._load_spine(task)
        cache, writes, edits = {}, [], []
        source = old.synth_tools._input_path(task)
        wb = old.openpyxl.load_workbook(source, data_only=False)  # verifier only; never saved
        for session in sessions:
            parsed = (session.get("synthesis") or {}).get("parsed") or {}
            formula = parsed.get("formula") if parsed.get("status") == "PROPOSED" else None
            if formula and parsed.get("target_id") != session["job"]["cell_id"]:
                writes.append({"session_id": session["job"]["session_id"], "status": "INVALID_TARGET_ID", "applied": False})
                continue
            if not isinstance(formula, str) or not formula.startswith("="):
                continue
            for cid in session["job"]["execution_cell_ids"]:
                target = old.target_address(spine, cid)
                translated = formula
                if cid != session["job"]["cell_id"]:
                    translated = Translator(formula, origin=session["target"]["address"]).translate_formula(target["address"])
                validation = old.validate_and_apply(task, target, translated, cache, wb)
                writes.append({"session_id": session["job"]["session_id"], "target": target, "formula": translated, **validation})
                if validation.get("applied"):
                    edits.append({"sheet": target["sheet"], "address": target["address"], "formula": translated})
        wb.close()
        output = OUT / f"scoring/Financial_Model-{task}/output.xlsx"
        audit = write_cells(source, output, edits)
        for w in writes:
            if w.get("applied") and any(r["reason"].startswith("SHARED_FORMULA_MASTER") for r in audit["rejected"]
                                        if r["sheet"] == w["target"]["sheet"] and r["address"] == w["target"]["address"]):
                w["applied"] = False
                w["writer_rejected"] = True
        save(f"actuation/{task}.json", {"task": task, "writes": writes, "output": str(output),
                                        "writer_audit": audit, "bounded_partial_workbook": True})


def score():
    run_root = OUT / "scoring"
    if not run_root.is_dir():
        raise SystemExit("no actuated workbooks to score")
    subprocess.run([sys.executable, str(old.ROOT / "benchmark/score_openrouter_run.py"), str(run_root),
                    "--model-name", "edit-plan-replication-glm-5.3-flash", "--metadata-tolerant"],
                   cwd=old.ROOT / "benchmark-data/SpreadsheetBench-2/evaluation", check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["freeze", "phase-b", "frontend-report", "select-downstream", "downstream", "actuate", "score"])
    args = parser.parse_args()
    {"freeze": freeze, "phase-b": phase_b, "frontend-report": frontend_report, "select-downstream": select_downstream,
     "downstream": downstream, "actuate": actuate, "score": score}[args.command]()
