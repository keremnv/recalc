#!/usr/bin/env python3
"""Downstream replay: delta working-set state and a per-session resource bound.

No new Edit Plans are generated. This reuses the frozen replication run's plans
and its 24 already-selected target sessions verbatim, and reruns only the
downstream half. Identical: model and sampling, targets, obligations, grounding
packets, deterministic bootstrap facts, SQL semantics and the 8-query maximum,
the synthesis system prompt, the proposal schema, actuation and scoring.

Changed, both predeclared:

  DELTA STATE   the monotone working set stays logically complete in the
                harness, but the prompt no longer re-sends it every turn. Each
                turn carries a handle, exact per-kind counts, and the identities
                added since the previous turn. Earlier entities are recoverable
                by querying their ID, which the retrieval prompt states.

  SESSION BOUND a per-session cap on measured provider input tokens. Exceeding
                it stops further retrieval with an explicit SESSION_RESOURCE_LIMIT
                record; it never silently drops context, and the session still
                takes its synthesis turn with the evidence it has.

Also fixed en route: token_estimate takes text, but two call sites passed dicts,
so the bootstrap size figure and the 30k episode token limit were measuring a
key count. Both now measure serialized text. Replaying the stored sessions shows
the episode limit would have fired on 0 of 76 results, so this is inert here;
every firing in this run is recorded so any divergence stays visible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_plan_replication as rep

old = rep.old
OUT = old.MECHANICAL / "edit-plan-downstream-replay"
SOURCE = rep.OUT

# Predeclared before any call. The per-session cap is ~3x the median session
# measured in the replication run (126,793 input tokens), so an ordinary session
# never approaches it while no single session can take more than a tenth of the
# budget. The global cap is raised from 3M only because completing all 24
# sessions is the point of this run and the per-session bound now prevents one
# session from monopolising it.
LIMITS = {
    "model": rep.LIMITS["model"], "temperature": 0, "reasoning": "medium", "retries": 0,
    "max_sql_calls": rep.LIMITS["max_sql_calls"], "downstream_sessions": 24, "workers": 1,
    "per_session_input_cap": 400_000,
    "total_downstream_input_soft_cap": 4_000_000,
    "working_set_serialization": "DELTA",
}


def save(name, data):
    old.write(OUT / name, data)


def freeze():
    if (OUT / "freeze.json").exists():
        raise RuntimeError("Already frozen")
    selection = old.load(SOURCE / "downstream_selection.json")
    save("selection.json", selection)
    paths = [Path(__file__), Path(old.__file__), Path(__file__).with_name("xlsx_cell_writer.py")]
    save("freeze.json", {
        "limits": LIMITS,
        # The prompts are the experiment variables, so they are hashed by content
        # and not only by the file that happens to hold them.
        "prompt_sha256": {n: hashlib.sha256(getattr(old, n).encode()).hexdigest()
                          for n in ("DELTA_RETRIEVAL_SYSTEM", "SYNTHESIS_SYSTEM", "SYNTHESIS_TRANSITION")},
        "sha256": {str(p.relative_to(old.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "selection_sha256": hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest(),
        "reused_verbatim": ["frozen replication Edit Plans", "the same 24 selected target sessions",
                            "obligations and grounding packets", "deterministic bootstrap facts",
                            "SQL semantics and the 8-query maximum", "synthesis system prompt and proposal schema",
                            "archive-level writer and the normal scoring path"],
        "changed": {"working_set_serialization": "handle + counts + per-turn delta instead of the full set each turn",
                    "retrieval_system_prompt": "states that the harness holds the complete set and that earlier IDs are re-materializable by SQL",
                    "per_session_input_cap": LIMITS["per_session_input_cap"],
                    "global_cap": "raised 3M -> 4M so all 24 sessions can complete"},
        "no_new_plan_generation": True,
    })
    print("Frozen", flush=True)


def check_freeze():
    f = old.load(OUT / "freeze.json")
    for name, digest in f["sha256"].items():
        if name == str(Path(__file__).relative_to(old.ROOT)):
            continue
        if hashlib.sha256((old.ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Frozen component changed: {name}")
    for name, digest in f["prompt_sha256"].items():
        if hashlib.sha256(getattr(old, name).encode()).hexdigest() != digest:
            raise RuntimeError(f"Frozen prompt changed: {name}")
    old.guard(LIMITS["model"])


def session(job, key):
    path = OUT / f"sessions/{job['session_id']}.json"
    if path.exists():
        return old.load(path)
    task = job["task"]
    r = old.load(SOURCE / f"phase_b/{task}.json")
    spine = old._load_spine(task)
    ob = next(o for o in r["compiler"]["obligations"] if o["id"] == job["obligation_id"])
    target = old.target_address(spine, job["cell_id"])
    info = old.input_cell_info(task, target["sheet"], target["address"])
    target.update({"target_id": job["cell_id"], "current_input_content": info["raw_value"], "current_input_kind": info["kind"]})
    start = time.perf_counter()
    try:
        s = old.run_target(task, r["compiler"]["raw_task"], ob, target, r["grounding"]["packets"][ob["id"]], spine, key,
                           synthesis_system=old.SYNTHESIS_SYSTEM,
                           retrieval_system=old.DELTA_RETRIEVAL_SYSTEM,
                           delta_state=True,
                           session_input_cap=LIMITS["per_session_input_cap"])
    except Exception as exc:
        s = {"status": "INTEGRATION_FAILURE", "error": f"{type(exc).__name__}: {exc}", "target": target}
    s["job"] = job
    s["wall_seconds"] = time.perf_counter() - start
    s["result_too_large_firings"] = sum((c.get("result") or {}).get("status") == "RESULT_TOO_LARGE" for c in s.get("calls", []))
    save(f"sessions/{job['session_id']}.json", s)
    parsed = (s.get("synthesis") or {}).get("parsed") or {}
    print(json.dumps({"session": job["session_id"], "task": task, "target": target["address"],
                      "proposal": parsed.get("status") or (f"RETRIEVAL_ACTION_{parsed.get('action')}" if parsed.get("action") else "UNPARSEABLE"),
                      "input_tokens": s.get("retrieval_input_tokens", 0) + s.get("synthesis_input_tokens", 0),
                      "capped": s.get("session_resource_limited"), "working_set": len(s.get("working_set_ids", []))}), flush=True)
    return s


def run():
    check_freeze()
    old.load_dotenv()
    key = os.environ["OPENROUTER_API_KEY"]
    jobs = old.load(OUT / "selection.json")["selected"]
    spent = sum(old.load(p).get("retrieval_input_tokens", 0) + old.load(p).get("synthesis_input_tokens", 0)
                for p in (OUT / "sessions").glob("*.json")) if (OUT / "sessions").exists() else 0
    for job in jobs:
        if (OUT / f"sessions/{job['session_id']}.json").exists():
            continue
        if spent >= LIMITS["total_downstream_input_soft_cap"]:
            save(f"sessions/{job['session_id']}.json", {"job": job, "status": "RESOURCE_CENSORED_NOT_RUN"})
            continue
        s = session(job, key)
        spent += s.get("retrieval_input_tokens", 0) + s.get("synthesis_input_tokens", 0)
    actuate()


def actuate():
    from openpyxl.formula.translate import Translator
    from xlsx_cell_writer import write_cells
    grouped = defaultdict(list)
    for p in sorted((OUT / "sessions").glob("*.json")):
        r = old.load(p)
        if r.get("job"):
            grouped[r["job"]["task"]].append(r)
    for task, sessions in grouped.items():
        if (OUT / f"actuation/{task}.json").exists():
            continue
        spine = old._load_spine(task)
        cache, writes, edits = {}, [], []
        source = old.synth_tools._input_path(task)
        wb = old.openpyxl.load_workbook(source, data_only=False)  # verifier only; never saved
        for s in sessions:
            parsed = (s.get("synthesis") or {}).get("parsed") or {}
            formula = parsed.get("formula") if parsed.get("status") == "PROPOSED" else None
            if formula and parsed.get("target_id") != s["job"]["cell_id"]:
                writes.append({"session_id": s["job"]["session_id"], "status": "INVALID_TARGET_ID", "applied": False})
                continue
            if not isinstance(formula, str) or not formula.startswith("="):
                continue
            for cid in s["job"]["execution_cell_ids"]:
                target = old.target_address(spine, cid)
                translated = formula if cid == s["job"]["cell_id"] else Translator(formula, origin=s["target"]["address"]).translate_formula(target["address"])
                validation = old.validate_and_apply(task, target, translated, cache, wb)
                writes.append({"session_id": s["job"]["session_id"], "target": target, "formula": translated, **validation})
                if validation.get("applied"):
                    edits.append({"sheet": target["sheet"], "address": target["address"], "formula": translated})
        wb.close()
        output = OUT / f"scoring/Financial_Model-{task}/output.xlsx"
        audit = write_cells(source, output, edits)
        for w in writes:
            if w.get("applied") and any(x["reason"].startswith("SHARED_FORMULA_MASTER") for x in audit["rejected"]
                                        if x["sheet"] == w["target"]["sheet"] and x["address"] == w["target"]["address"]):
                w["applied"] = False
                w["writer_rejected"] = True
        save(f"actuation/{task}.json", {"task": task, "writes": writes, "output": str(output), "writer_audit": audit})


def score():
    run_root = OUT / "scoring"
    if not run_root.is_dir():
        raise SystemExit("no actuated workbooks to score")
    subprocess.run([sys.executable, str(old.ROOT / "benchmark/score_openrouter_run.py"), str(run_root),
                    "--model-name", "edit-plan-replay-glm-5.3-flash", "--metadata-tolerant"],
                   cwd=old.ROOT / "benchmark-data/SpreadsheetBench-2/evaluation", check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["freeze", "run", "actuate", "score"])
    args = parser.parse_args()
    {"freeze": freeze, "run": run, "actuate": actuate, "score": score}[args.command]()
