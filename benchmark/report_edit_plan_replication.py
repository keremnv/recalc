#!/usr/bin/env python3
"""Evaluator-only report for the replication. Never imported by model-facing code."""
from __future__ import annotations
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_plan_replication as rep
import edit_plan_probe as base
import report_edit_plan_probe as primary_report

old = rep.old
OUT = rep.OUT


def stats(values):
    values = sorted(values)
    return {"n": len(values), "sum": sum(values), "median": statistics.median(values) if values else None,
            "max": max(values) if values else None}


def transition_label(parsed):
    if not isinstance(parsed, dict) or not parsed:
        return "UNPARSEABLE"
    if parsed.get("status") in ("PROPOSED", "ABSTAIN"):
        return parsed["status"]
    if parsed.get("action"):
        return f"RETRIEVAL_ACTION_{str(parsed['action']).upper()}"
    return parsed.get("status") or "UNPARSEABLE"


def build():
    front = old.load(OUT / "frontend_report.json")
    rows = [old.load(f) for f in sorted((OUT / "phase_b").glob("*.json"))]
    sessions = [old.load(f) for f in sorted((OUT / "sessions").glob("*.json"))] if (OUT / "sessions").exists() else []
    spines = {r["task"]: old._load_spine(r["task"]) for r in rows}
    scored = [primary_report.classify_session(s, spines[s["job"]["task"]]) for s in sessions if s.get("job") and s.get("target")]
    for s, raw in zip(scored, [x for x in sessions if x.get("job") and x.get("target")]):
        s["transition_response"] = transition_label((raw.get("synthesis") or {}).get("parsed"))
        s["mode"] = raw["job"]["mode"]

    primary_front = old.load(base.OUT / "frontend_report.json")
    primary_by_task = {r["task"]: r for r in primary_front["rows"]}
    ab = [{"task": r["task"], "primary_status": primary_by_task.get(r["task"], {}).get("status"),
           "primary_recall": primary_by_task.get(r["task"], {}).get("recall"),
           "primary_precision": primary_by_task.get(r["task"], {}).get("precision"),
           "replication_status": r["status"], "replication_recall": r.get("recall"),
           "replication_precision": r.get("precision")} for r in front["rows"]]

    # Q2: does the retrieval / program-recovery frontier reappear?
    gold_sessions = [s for s in scored if s["gold_target"]]
    conditional = {}
    for complete in (True, False):
        for existing in (True, False):
            sub = [s for s in gold_sessions if s["retrieval_complete"] == complete and s["existing_program"] == existing]
            conditional[f"{'COMPLETE' if complete else 'INCOMPLETE'}_{'EXISTING' if existing else 'NOVEL'}"] = {
                "n": len(sub), "correct": sum(s["formula_correct"] for s in sub),
                "fingerprint_match": sum(s["fingerprint_match"] for s in sub)}
    proposals = [s for s in scored if s["transition_response"] in ("PROPOSED", "ABSTAIN")]
    censored = [s for s in sessions if s.get("status") == "RESOURCE_CENSORED_NOT_RUN"]
    transition = {"sessions_selected": len(sessions), "sessions_run": len(scored),
                  "sessions_censored_by_token_cap": len(censored),
                  "counts": dict(Counter(s["transition_response"] for s in scored)),
                  "proposal_rate": len(proposals) / len(scored) if scored else None}
    # One session monopolising the shared budget starves the rest, so record the
    # concentration explicitly rather than only the total.
    spend = sorted(((s["job"]["task"], s["job"]["session_id"], len(s.get("working_set_ids", [])),
                     s.get("retrieval_input_tokens", 0) + s.get("synthesis_input_tokens", 0))
                    for s in sessions if s.get("retrieval_input_tokens") is not None and s.get("job")),
                   key=lambda x: -x[3])
    total_spend = sum(x[3] for x in spend)
    budget = {"soft_cap": rep.LIMITS["total_downstream_input_soft_cap"], "measured_total": total_spend,
              "largest_session": {"session": spend[0][1], "task": spend[0][0], "working_set_ids": spend[0][2],
                                  "input_tokens": spend[0][3],
                                  "share_of_total": spend[0][3] / total_spend if total_spend else None} if spend else None,
              "median_session_tokens": statistics.median([x[3] for x in spend]) if spend else None,
              "per_session": [{"session": b, "task": a, "working_set_ids": c, "input_tokens": d} for a, b, c, d in spend],
              "censored_sessions": [{"session": s["job"]["session_id"], "task": s["job"]["task"],
                                     "cell_id": s["job"]["cell_id"]} for s in censored]}

    actuation = {f.stem: old.load(f) for f in (OUT / "actuation").glob("*.json")} if (OUT / "actuation").exists() else {}
    official = old.load(OUT / "scoring/official_scores.json") if (OUT / "scoring/official_scores.json").exists() else None
    gate = old.load(old.MECHANICAL / "writer-neutrality-gate/gate.json")
    null_floor = {r["task"]: r for r in gate["rows"]}
    scores = []
    for task, a in sorted(actuation.items()):
        row = (official or {}).get("tasks", {}).get(f"Financial_Model:{task}") or {}
        floor = null_floor.get(task, {})
        scores.append({"task": task, "applied_writes": sum(bool(w.get("applied")) for w in a["writes"]),
                       "writer_rewrote_parts": len(a.get("writer_audit", {}).get("rewritten_parts", [])),
                       "writer_rejected": a.get("writer_audit", {}).get("rejected", []),
                       "regression_accuracy": row.get("regression_accuracy"),
                       "modification_accuracy": row.get("modification_accuracy"),
                       "zero_edit_modification_floor": floor.get("modification_accuracy"),
                       "modification_gain_over_floor": round(row.get("modification_accuracy") - floor.get("modification_accuracy"), 6)
                       if row.get("modification_accuracy") is not None and floor.get("modification_accuracy") is not None else None,
                       "error_message": row.get("error_message")})

    usages = defaultdict(list)
    for r in rows:
        if r.get("response"):
            u = r["response"].get("usage") or {}
            usages["plan"].append({"input": int(u.get("prompt_tokens") or 0), "output": int(u.get("completion_tokens") or 0), "cost": u.get("cost") or 0})
    for s in sessions:
        for call in s.get("calls", []):
            u = (call.get("response") or {}).get("usage") or {}
            usages["retrieval"].append({"input": int(u.get("prompt_tokens") or 0), "output": int(u.get("completion_tokens") or 0), "cost": u.get("cost") or 0})
        if s.get("synthesis"):
            u = (s["synthesis"].get("response") or {}).get("usage") or {}
            usages["synthesis"].append({"input": int(u.get("prompt_tokens") or 0), "output": int(u.get("completion_tokens") or 0), "cost": u.get("cost") or 0})

    result = {
        "posthoc_revalidation": old.load(base.OUT / "posthoc_revalidation.json") if (base.OUT / "posthoc_revalidation.json").exists() else None,
        "writer_gate": {k: gate[k] for k in ("gate", "tasks", "passing", "pass")},
        "frontend": {k: v for k, v in front.items() if k != "rows"},
        "frontend_rows": front["rows"],
        "primary_vs_replication": ab,
        "comparison": {
            "explicit_enumeration": {"precision": 0.073, "recall": 0.0024, "note": "previously published composed frontend"},
            "primary_edit_plan": {"micro_recall": primary_front["micro_recall"], "micro_precision": primary_front["micro_precision"],
                                  "valid_plan_rate": primary_front["valid_plan_rate"]},
            "replication_edit_plan": {"micro_recall": front["micro_recall"], "micro_precision": front["micro_precision"],
                                      "valid_plan_rate": front["valid_plan_rate"]},
        },
        "synthesis_transition": transition, "downstream_budget": budget,
        "conditional_synthesis": conditional,
        "scored_sessions": scored,
        "execution_modes": dict(Counter(s["mode"] for s in scored)),
        "admissibility": {"thresholds": rep.ADMISSIBILITY, "inadmissible_tasks": front["inadmissible"],
                          "blocked": old.load(OUT / "downstream_selection.json").get("blocked_by_admissibility_gate", {})
                          if (OUT / "downstream_selection.json").exists() else {}},
        "benchmark_scores": scores, "official_scores_summary": {k: (official or {}).get(k) for k in ("exact", "scored", "evaluation_runtime")},
        "tokens_by_stage": {k: {"calls": len(v), "input": stats([x["input"] for x in v]), "output": stats([x["output"] for x in v]),
                                "reported_cost": sum(x["cost"] for x in v)} for k, v in usages.items()},
    }
    result["verdicts"] = verdicts(result)
    old.write(OUT / "report.json", result)
    return result


def verdicts(r):
    f = r["frontend"]
    out = []
    out.append("EDIT_PLAN_GENERATION_SUPPORTED" if f["micro_recall"] >= .75
               else "EDIT_PLAN_GENERATION_MATERIALLY_IMPROVED" if f["micro_recall"] >= .40
               else "REPRESENTATION_GOOD_MODEL_WEAK")
    t = r["synthesis_transition"]
    out.append("SYNTHESIS_TRANSITION_FIXED" if (t["proposal_rate"] or 0) >= .75
               else "SYNTHESIS_TRANSITION_IMPROVED" if (t["proposal_rate"] or 0) > .125
               else "SYNTHESIS_TRANSITION_STILL_BROKEN")
    out.append("WORKBOOK_SCORING_TRUSTWORTHY" if r["writer_gate"]["pass"] else "WORKBOOK_SCORING_UNTRUSTWORTHY")
    c = r["conditional_synthesis"]
    reached = sum(v["n"] for v in c.values())
    out.append("DOWNSTREAM_FRONTIER_OBSERVABLE" if reached >= 4 else "DOWNSTREAM_SAMPLE_TOO_SMALL")
    return out


def render(r):
    def pct(x):
        return "N/A" if x is None else f"{100*x:.1f}%"

    def table(headers, rows):
        return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                          *["| " + " | ".join("—" if x is None else str(x).replace("|", "/") for x in row) + " |" for row in rows]])

    f = r["frontend"]
    ph = r["posthoc_revalidation"]
    t = r["synthesis_transition"]
    lines = [
        "# Edit Plan replication: three harness fixes",
        "Same 18 Financial_Model tasks, same `z-ai/glm-5.3-flash` at temperature 0 with medium reasoning, same Task IR (the primary run's compiler output reused verbatim), same grounding projection, same Edit Plan language, schema and contract text, and a byte-identical plan prompt. Only three defects found in the primary run were fixed, plus one execution boundary that never touches scoring. No prompt tuning, no retries, no repair calls, no new language primitives. See `freeze.json`.",
        "## The three questions",
        f"**1. Does valid plan generation survive once the validator agrees with the world it exposes?** Yes. Valid plans went from {pct(r['comparison']['primary_edit_plan']['valid_plan_rate'])} to {pct(f['valid_plan_rate'])} of tasks, micro recall from {pct(r['comparison']['primary_edit_plan']['micro_recall'])} to {pct(f['micro_recall'])}, and micro precision from {pct(r['comparison']['primary_edit_plan']['micro_precision'])} to {pct(f['micro_precision'])}. Against the explicit-enumeration frontend this architecture replaced (7.3% precision, 0.24% recall), both axes now differ by more than an order of magnitude.",
        f"**2. Once true targets reach synthesis, does the retrieval / program-recovery frontier reappear?** Partly, and the answer is now budget-limited rather than protocol-limited. The transition itself is fixed: proposal rate is {pct(t['proposal_rate'])} across the {t['sessions_run']} sessions that ran, against 1/8 in the primary run, with responses `{json.dumps(t['counts'])}`. But {t['sessions_censored_by_token_cap']} of the {t['sessions_selected']} selected sessions never ran, because the predeclared 3M downstream input-token cap was reached, so only {sum(v['n'] for v in r['conditional_synthesis'].values())} sessions landed on evaluator-supported gold targets. That is too few to re-establish the frontier.",
        f"**3. Can workbook scoring be trusted now?** The zero-write gate passes {r['writer_gate']['passing']}/{r['writer_gate']['tasks']} tasks at regression exactly 1.0, where the openpyxl writer scored 0.9841 on 07_03 with no edits at all. Benchmark deltas measured through this writer are attributable to the agent.",
        "Verdicts: " + ", ".join(r["verdicts"]) + ".",
        "## Free diagnostic first: replaying the frozen responses",
        f"Before spending anything, the primary run's stored plan JSON was replayed through the same expansion algebra under the corrected contract — zero model calls. Valid plans went {ph['v1_micro']['valid_plan_tasks']} → {ph['v2_micro']['valid_plan_tasks']} of {ph['v1_micro']['tasks']} and micro recall {pct(ph['v1_micro']['micro_recall'])} → {pct(ph['v2_micro']['micro_recall'])} on identical model output. That establishes the validator, not the model, as the cause of those rejections."
        if ph else "Post-hoc revalidation artifact missing.",
        table(["Task", "Was", "Now", "Recall", "Precision"],
              [[m["task"], m["was"], m["now"], pct(m["recall"]), pct(m["precision"])] for m in (ph["tasks_recovered_by_contract_fix"] if ph else [])]),
        "Four plans stayed invalid under the corrected contract for reasons that are genuinely the model's: a malformed cell identity, an obligation ID that does not exist, a rectangle corner outside the sheet's used bounds, and temporal endpoints invented on sheets that expose no such coordinate. The fix does not launder model errors.",
        "## Fix 1 — the identity contract",
        "The primary validator accepted only cells, sheets, formula classes and temporal coordinates in the optional `source_relation` field. The contract text did name those four, so the model deviated; but the surrounding context is dominated by `text:` anchors, and every rejected identifier resolves 1:1 onto a real cell in the task's own world database. The disproportion is the defect: an optional citation that cannot change which cells expand was discarding an otherwise correct target expression. V2 accepts every namespace the grounding contract exposes — text anchors, rows, columns, workbook, and period ids resolved per axis — while still rejecting identities absent from the world. The target-set algebra is untouched, and V1 was verified to reproduce the frozen run exactly on all 15 stored plans.",
        "## Frontend results",
        table(["Task", "Status", "Expanded", "True", "Recall", "Precision", "Admissible"],
              [[x["task"], x["status"], x["expanded_count"], x["true_targets"], pct(x.get("recall")), pct(x.get("precision")), x.get("plan_admissible")] for x in r["frontend_rows"]]),
        table(["Task", "Primary status", "Primary recall", "Replication status", "Replication recall"],
              [[x["task"], x["primary_status"], pct(x["primary_recall"]), x["replication_status"], pct(x["replication_recall"])] for x in r["primary_vs_replication"]]),
        "Per-task comparison is indicative only: these are fresh generations, so plan-to-plan variation is confounded with the fix. The aggregate and the zero-call replay above are the load-bearing evidence.",
        "## Execution-admissibility gate",
        f"Thresholds predeclared before any model call: `{json.dumps(r['admissibility']['thresholds'])}`. Raw expansion is always scored in full, so an inadmissible plan is never credited with target correctness; the gate only decides whether an expansion may spawn downstream sessions. In this run it blocked nothing — every valid plan was admissible — but on the primary run's 08_01 plan it correctly refuses a 264,133-cell expansion covering 100% of four sheets while still reporting that plan's raw recall of 1.000 at precision 0.002.",
        "## Fix 2 — the synthesis phase transition",
        f"The primary run reused the retrieval system prompt for the synthesis call, so the model was still being told to return `execute_sql` or `final` when it was asked for a formula. Giving synthesis its own prompt moved the proposal rate from 1/8 to {t['counts'].get('PROPOSED', 0) + t['counts'].get('ABSTAIN', 0)}/{t['sessions_run']}. Not one session returned a retrieval action at the transition, where 7 of 8 did before.",
        "## The budget became the binding constraint",
        f"The predeclared cap stopped new sessions after {r['downstream_budget']['measured_total']:,} downstream input tokens, censoring {t['sessions_censored_by_token_cap']} of {t['sessions_selected']} selected sessions. The spend was not spread evenly: session `{r['downstream_budget']['largest_session']['session']}` on task {r['downstream_budget']['largest_session']['task']} alone consumed {r['downstream_budget']['largest_session']['input_tokens']:,} tokens, {pct(r['downstream_budget']['largest_session']['share_of_total'])} of the total, against a median session of {r['downstream_budget']['median_session_tokens']:,.0f}.",
        table(["Session", "Task", "Working-set IDs", "Input tokens"],
              [[b["session"], b["task"], b["working_set_ids"], f"{b['input_tokens']:,}"] for b in r["downstream_budget"]["per_session"]]),
        "The cause is structural, not incidental: the monotone working set is re-serialised in full into every retrieval prompt, so a session's cost is roughly its working-set size times its call count. That session's set was 15,904 identities against 236 for the cheapest, and almost all of it came from the deterministic bootstrap rather than from anything the model retrieved. Compact Edit Plans removed the output-side scaling problem; the retrieval input side is still unbounded, and it now decides how much of the experiment can run. A per-session cap, and sending working-set deltas instead of the whole set each turn, are the obvious next fixes — but both change downstream behaviour, so neither belongs in this replication.",
        f"Censored sessions: `{json.dumps([c['session'] + ':' + c['task'] for c in r['downstream_budget']['censored_sessions']])}`.",
        table(["Session", "Task", "Target", "Mode", "Gold target", "Retrieval complete", "Transition", "Formula correct"],
              [[s["session_id"], s["task"], (s.get("target") or {}).get("address"), s["mode"], s["gold_target"],
                s.get("retrieval_complete"), s["transition_response"], s.get("formula_correct")] for s in r["scored_sessions"]]),
        "## Conditional synthesis",
        table(["Stratum", "Sessions", "Formula correct", "Fingerprint match"],
              [[k, v["n"], v["correct"], v["fingerprint_match"]] for k, v in r["conditional_synthesis"].items()]),
        f"Execution modes exercised: `{json.dumps(r['execution_modes'])}`. Only evaluator-supported gold targets enter this table, so its denominators are much smaller than the frontend's and it cannot carry a capability claim on its own.",
        "## Fix 3 — writer neutrality and benchmark scores",
        f"Gate: `{json.dumps(r['writer_gate'])}`. The writer copies the archive entry by entry and rewrites only the sheet parts that receive an edit, so a zero-write round trip is byte-identical to the input. The openpyxl round trip it replaces dropped `calcChain.xml`, `sharedStrings.xml`, three worksheet relationship parts and the chart styling parts, and changed recalculated values on workbooks it never edited.",
        table(["Task", "Applied writes", "Parts rewritten", "Regression acc.", "Modification acc.", "Zero-edit floor", "Gain over floor"],
              [[s["task"], s["applied_writes"], s["writer_rewrote_parts"], s["regression_accuracy"], s["modification_accuracy"],
                s["zero_edit_modification_floor"], s["modification_gain_over_floor"]] for s in r["benchmark_scores"]]),
        f"Scorer summary: `{json.dumps(r['official_scores_summary'])}`. Modification accuracy is not zero-based on this suite — with no edits at all it already ranges from 0.0 to 0.651 — so only the gain over each task's measured zero-edit floor is attributable to the agent. These remain bounded partial workbooks: at most two target cells per task were executed out of thousands expanded, so exact task success is not the quantity this run is designed to move.",
        "## Tokens and cost",
        table(["Stage", "Calls", "Input tokens", "Output tokens", "Reported cost"],
              [[k, v["calls"], v["input"]["sum"], v["output"]["sum"], f"${v['reported_cost']:.4f}"] for k, v in r["tokens_by_stage"].items()]),
        "## What this does and does not establish",
        "It establishes that the primary run's frontend number was mostly harness artifact, that the synthesis transition failure was a prompt-plumbing defect rather than a model limitation, and that benchmark scoring on this suite now has a clean floor. It does not establish that Edit Plan compilation is solved: micro recall is far below the 100% representational ceiling, one task still selects a nearly disjoint region, and two plans failed the JSON schema outright. The remaining frontend loss is now genuinely about task-to-plan semantics, which is the question the primary run could not ask.",
    ]
    old.write(OUT / "full_report.md", "\n\n".join(lines) + "\n")


if __name__ == "__main__":
    render(build())
