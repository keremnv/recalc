#!/usr/bin/env python3
"""Report for the downstream replay: delta state, the session bound, and the frontier."""
from __future__ import annotations
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import edit_plan_downstream_replay as replay
import edit_plan_replication as rep
import report_edit_plan_probe as primary_report

old = replay.old
OUT = replay.OUT
SOURCE = rep.OUT

# The frozen harness passes this literal to call_glm for both stages. Mirrored
# here rather than edited into the harness, which is under freeze during the run.
SYNTH_MAX_TOKENS = 2200


def frozen_extract_json_object(raw):
    """The reader's behaviour *before* defect 6 was repaired.

    Pinned here on purpose. Both this report and the retrospective sweep measure
    a historical comparison, so the "before" side must not silently improve when
    the shared extractor is fixed.
    """
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def posthoc_parse(text: str):
    """Post-hoc corrected parse of a stored synthesis response.

    The frozen extractor takes the span from the first '{' to the last '}' and
    json.loads it. When a model emits its answer and then repeats it verbatim,
    that span covers both objects, is not valid JSON, and a correct answer is
    scored UNPARSEABLE. The parser is a measurement instrument, not an
    experiment variable, so the fix is published as a post-hoc diagnostic over
    the stored raw text rather than applied to the frozen harness mid-run.

    Recovery is deliberately conservative: it decodes every top-level object and
    returns one only when the repeats agree. Two objects that disagree stay
    unparseable, because picking a winner would be a semantic repair rather than
    a parsing correction.
    """
    if not text:
        return None, "EMPTY"
    frozen = frozen_extract_json_object(text)
    if frozen is not None:
        return frozen, "PARSED_BY_FROZEN_EXTRACTOR"
    decoder = json.JSONDecoder()
    found, i = [], 0
    while True:
        start = text.find("{", i)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except ValueError:
            i = start + 1
            continue
        if isinstance(obj, dict):
            found.append(obj)
        i = end
    if not found:
        return None, "NO_JSON_OBJECT"
    if all(x == found[0] for x in found):
        return found[0], "RECOVERED_DUPLICATE_EMISSION" if len(found) > 1 else "RECOVERED_SINGLE_OBJECT"
    return None, "CONFLICTING_OBJECTS"


def stats(v):
    v = [x for x in v if x is not None]
    if not v:
        return None
    return {"n": len(v), "sum": sum(v), "mean": round(statistics.mean(v), 1),
            "median": statistics.median(v), "max": max(v)}


def ran(s):
    return bool(s.get("job")) and s.get("status") != "RESOURCE_CENSORED_NOT_RUN" and s.get("target")


def spend(s):
    return s.get("retrieval_input_tokens", 0) + s.get("synthesis_input_tokens", 0)


def build():
    sessions = [old.load(f) for f in sorted((OUT / "sessions").glob("*.json"))]
    prior = {p.stem: old.load(p) for p in sorted((SOURCE / "sessions").glob("*.json"))}
    spines = {}
    for s in sessions:
        t = s["job"]["task"]
        if t not in spines:
            spines[t] = old._load_spine(t)
    live = [s for s in sessions if ran(s)]
    scored = []
    for s in live:
        c = primary_report.classify_session(s, spines[s["job"]["task"]])
        c["transition_response"] = rep_label(s)
        c["mode"] = s["job"]["mode"]
        c["input_tokens"] = spend(s)
        c["queries_issued"] = sum(1 for x in s.get("calls", []) if x.get("sql"))
        c["session_resource_limited"] = bool(s.get("session_resource_limited"))
        c["result_too_large_firings"] = s.get("result_too_large_firings", 0)
        scored.append(c)

    # A/B against the same session under the frozen FULL serialization. Only the
    # 11 sessions the frozen run could afford have a counterpart; the other 13
    # exist only because the delta run could reach them at all.
    ab = []
    for s in live:
        sid = s["job"]["session_id"]
        p = prior.get(sid) or {}
        had = p.get("status") not in (None, "RESOURCE_CENSORED_NOT_RUN")
        ab.append({"session": sid, "task": s["job"]["task"],
                   "full_input_tokens": spend(p) if had else None,
                   "delta_input_tokens": spend(s),
                   "reduction": round(1 - spend(s) / spend(p), 4) if had and spend(p) else None,
                   "full_working_set": len(p.get("working_set_ids", [])) if had else None,
                   "delta_working_set": len(s.get("working_set_ids", [])),
                   "full_queries": sum(1 for x in p.get("calls", []) if x.get("sql")) if had else None,
                   "delta_queries": sum(1 for x in s.get("calls", []) if x.get("sql")),
                   "full_response": rep_label(p) if had else None,
                   "delta_response": rep_label(s),
                   "counterpart_in_frozen_run": had})

    # Cost is not the only thing the change can move. Track whether the
    # synthesis outcome itself improved, held, or degraded on matched sessions.
    rank = {"PROPOSED": 3, "ABSTAIN": 2}
    def tier(x):
        return rank.get(x, 1)
    outcome_shift = {"same": [], "degraded": [], "improved": []}
    for x in ab:
        if not x["counterpart_in_frozen_run"]:
            continue
        if x["full_response"] == x["delta_response"]:
            outcome_shift["same"].append(x["session"])
        elif tier(x["delta_response"]) < tier(x["full_response"]):
            outcome_shift["degraded"].append(x["session"])
        else:
            outcome_shift["improved"].append(x["session"])

    gold = [s for s in scored if s["gold_target"]]
    conditional = {}
    for complete in (True, False):
        for existing in (True, False):
            sub = [s for s in gold if s["retrieval_complete"] == complete and s["existing_program"] == existing]
            conditional[f"{'COMPLETE' if complete else 'INCOMPLETE'}_{'EXISTING' if existing else 'NOVEL'}"] = {
                "n": len(sub), "correct": sum(s["formula_correct"] for s in sub),
                "fingerprint_match": sum(s["fingerprint_match"] for s in sub),
                "sessions": [s["session_id"] for s in sub]}

    per = sorted(({"session": s["job"]["session_id"], "task": s["job"]["task"],
                   "input_tokens": spend(s), "working_set_ids": len(s.get("working_set_ids", [])),
                   "capped": bool(s.get("session_resource_limited"))} for s in live),
                 key=lambda x: -x["input_tokens"])
    total = sum(x["input_tokens"] for x in per)
    # Only sessions that exist in both arms can be compared. The frozen run
    # could afford 11 of 24, so a headline against its full total would compare
    # different session sets.
    matched = [x for x in ab if x["counterpart_in_frozen_run"]]
    prior_total = sum(x["full_input_tokens"] for x in matched)
    matched_delta_total = sum(x["delta_input_tokens"] for x in matched)
    budget = {"per_session_cap": replay.LIMITS["per_session_input_cap"],
              "global_soft_cap": replay.LIMITS["total_downstream_input_soft_cap"],
              "measured_total": total, "matched_sessions": len(matched),
              "matched_delta_total": matched_delta_total, "matched_full_total": prior_total,
              "matched_reduction": round(1 - matched_delta_total / prior_total, 4) if prior_total else None,
              "sessions_run": len(live),
              "sessions_selected": len(old.load(OUT / "selection.json")["selected"]),
              "sessions_not_yet_written": len(old.load(OUT / "selection.json")["selected"]) - len(sessions),
              "sessions_censored_by_global_cap": sum(1 for s in sessions if s.get("status") == "RESOURCE_CENSORED_NOT_RUN"),
              "sessions_stopped_by_per_session_cap": [x["session"] for x in per if x["capped"]],
              "median_session_tokens": statistics.median([x["input_tokens"] for x in per]) if per else None,
              "largest_session": per[0] if per else None,
              "largest_share_of_total": round(per[0]["input_tokens"] / total, 4) if per and total else None,
              "per_session": per}

    transition = {"sessions_run": len(scored),
                  "counts": dict(Counter(s["transition_response"] for s in scored)),
                  "proposal_rate": sum(s["transition_response"] in ("PROPOSED", "ABSTAIN") for s in scored) / len(scored) if scored else None,
                  "output_budget_truncations": sum(s["transition_response"] == "TRUNCATED_NO_CONTENT" for s in scored),
                  "proposal_rate_excluding_truncated": (
                      sum(s["transition_response"] in ("PROPOSED", "ABSTAIN") for s in scored)
                      / max(1, sum(s["transition_response"] != "TRUNCATED_NO_CONTENT" for s in scored))) if scored else None,
                  "retrieval_protocol_leakage": sum(s["transition_response"].startswith(("RETRIEVAL_ACTION", "RETRIEVAL_STATUS")) for s in scored),
                  "leaked_sessions": [s["session_id"] for s in scored if s["transition_response"].startswith(("RETRIEVAL_ACTION", "RETRIEVAL_STATUS"))]}

    # Post-hoc re-parse of stored raw text, over both arms, published as a
    # diagnostic beside the frozen labels rather than replacing them.
    def posthoc(session_list):
        rows, changed = [], 0
        for s in session_list:
            resp = (s.get("synthesis") or {}).get("response") or {}
            obj, how = posthoc_parse(resp.get("text") or "")
            frozen = rep_label(s)
            new = rep_label({"synthesis": {"parsed": obj, "response": resp}})
            if obj is None and how == "EMPTY":
                new = frozen
            changed += new != frozen
            rows.append({"session": s["job"]["session_id"], "frozen_label": frozen,
                         "posthoc_label": new, "recovery": how})
        return {"rows": rows, "labels_changed": changed,
                "counts_frozen": dict(Counter(x["frozen_label"] for x in rows)),
                "counts_posthoc": dict(Counter(x["posthoc_label"] for x in rows)),
                "proposal_rate_posthoc": sum(x["posthoc_label"] in ("PROPOSED", "ABSTAIN") for x in rows) / len(rows) if rows else None}

    prior_live = [x for x in prior.values() if ran(x)]

    actuation = {f.stem: old.load(f) for f in (OUT / "actuation").glob("*.json")} if (OUT / "actuation").exists() else {}
    official = old.load(OUT / "scoring/official_scores.json") if (OUT / "scoring/official_scores.json").exists() else None
    gate = old.load(old.MECHANICAL / "writer-neutrality-gate/gate.json")
    floor = {r["task"]: r for r in gate["rows"]}
    scores = []
    for task, act in sorted(actuation.items()):
        row = (official or {}).get("tasks", {}).get(f"Financial_Model:{task}") or {}
        f = floor.get(task, {})
        gain = None
        if row.get("modification_accuracy") is not None and f.get("modification_accuracy") is not None:
            gain = round(row["modification_accuracy"] - f["modification_accuracy"], 6)
        scores.append({"task": task, "applied_writes": sum(bool(w.get("applied")) for w in act["writes"]),
                       "writer_rewrote_parts": len(act.get("writer_audit", {}).get("rewritten_parts", [])),
                       "regression_accuracy": row.get("regression_accuracy"),
                       "modification_accuracy": row.get("modification_accuracy"),
                       "zero_edit_modification_floor": f.get("modification_accuracy"),
                       "modification_gain_over_floor": gain, "error_message": row.get("error_message")})

    usages = defaultdict(list)
    for s in live:
        for call in s.get("calls", []):
            u = (call.get("response") or {}).get("usage") or {}
            usages["retrieval"].append({"input": int(u.get("prompt_tokens") or 0), "output": int(u.get("completion_tokens") or 0), "cost": u.get("cost") or 0})
        u = ((s.get("synthesis") or {}).get("response") or {}).get("usage") or {}
        usages["synthesis"].append({"input": int(u.get("prompt_tokens") or 0), "output": int(u.get("completion_tokens") or 0), "cost": u.get("cost") or 0})

    # Post-hoc actuation arm (corrected parse), if it has been run.
    pa = OUT / "posthoc-parse-arm"
    posthoc_arm = old.load(pa / "comparison.json") if (pa / "comparison.json").exists() else None

    # Where retrieval input actually goes now. The bootstrap first send and the
    # system prompt resent on every turn are fixed costs that delta state cannot
    # touch; only the per-turn summary is variable.
    sys_tok = len(old.DELTA_RETRIEVAL_SYSTEM) // 4
    decomp = []
    for s_ in live:
        calls = [c for c in s_.get("calls", []) if c.get("response")]
        if not calls:
            continue
        q1 = int(((calls[0].get("response") or {}).get("usage") or {}).get("prompt_tokens") or 0)
        retr = s_.get("retrieval_input_tokens", 0)
        fixed = q1 + sys_tok * len(calls)
        decomp.append({"session": s_["job"]["session_id"], "calls": len(calls), "bootstrap_first_send": q1,
                       "system_prompt_resent": sys_tok * len(calls), "variable_summaries": retr - fixed,
                       "retrieval_total": retr, "fixed_share": round(fixed / retr, 4) if retr else None,
                       "synthesis_input": s_.get("synthesis_input_tokens", 0),
                       "synthesis_share_of_session": round(s_.get("synthesis_input_tokens", 0) / spend(s_), 4) if spend(s_) else None,
                       "provider_cached_tokens": sum(((c.get("response") or {}).get("usage") or {}).get("prompt_tokens_details", {}).get("cached_tokens", 0) for c in calls)})

    result = {
        "freeze": old.load(OUT / "freeze.json"),
        "posthoc_actuation_arm": posthoc_arm,
        "retrieval_cost_decomposition": {"system_prompt_tokens_estimated": sys_tok, "rows": decomp},
        "serialization_ab": ab,
        "outcome_shift": outcome_shift,
        "delta_reduction": stats([x["reduction"] for x in ab if x["reduction"] is not None]),
        "downstream_budget": budget,
        "synthesis_transition": transition,
        "posthoc_parse_replay": posthoc(live),
        "posthoc_parse_frozen_replication": posthoc(prior_live),
        "conditional_synthesis": conditional,
        "scored_sessions": scored,
        "execution_modes": dict(Counter(s["mode"] for s in scored)),
        "size_guard_firings": {"result_too_large": sum(s.get("result_too_large_firings", 0) for s in live),
                               "note": "Both size guards were inert before this run because token_estimate was fed dicts. "
                                       "Replaying the frozen run's 76 OK results with the corrected estimator fired the "
                                       "episode limit 0 times, so the fix is behaviour-preserving there; this counter "
                                       "reports whether it stayed inert once live."},
        "benchmark_scores": scores,
        "official_scores_summary": {k: (official or {}).get(k) for k in ("exact", "scored", "evaluation_runtime")},
        "tokens_by_stage": {k: {"calls": len(v), "input": stats([x["input"] for x in v]),
                                "output": stats([x["output"] for x in v]),
                                "reported_cost": sum(x["cost"] for x in v)} for k, v in usages.items()},
    }
    old.write(OUT / "report.json", result)
    return result


def rep_label(s):
    """Label a stored synthesis response.

    Ordering mirrors the replication report's transition_label exactly, so the
    two arms are labelled by the same rule: a real proposal first, then
    retrieval-protocol leakage, then everything else. Checking `status` before
    `action` would hide a leaked {"action":"final","status":"ENOUGH_EVIDENCE"}
    behind its retrieval status.

    TRUNCATED_NO_CONTENT is the one addition. max_tokens is shared between
    reasoning and content on this model, so an empty response at exactly the
    output budget is a truncation, not a malformed answer, and the frozen
    replication has the same artifact.
    """
    if not s.get("synthesis"):
        return "NOT_RUN"
    parsed = (s["synthesis"] or {}).get("parsed") or {}
    if parsed.get("status") in ("PROPOSED", "ABSTAIN"):
        return parsed["status"]
    if parsed.get("action"):
        return f"RETRIEVAL_ACTION_{str(parsed['action']).upper()}"
    if parsed.get("status"):
        return f"RETRIEVAL_STATUS_{parsed['status']}"
    resp = s["synthesis"].get("response") or {}
    u = resp.get("usage") or {}
    if not (resp.get("text") or "") and u.get("completion_tokens") == SYNTH_MAX_TOKENS:
        return "TRUNCATED_NO_CONTENT"
    return "UNPARSEABLE"


def render(r):
    def pct(x):
        return "n/a" if x is None else f"{100 * x:.1f}%"

    def table(headers, rows):
        out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
        out += ["| " + " | ".join("" if c is None else str(c) for c in row) + " |" for row in rows]
        return "\n".join(out)

    b, t, c = r["downstream_budget"], r["synthesis_transition"], r["conditional_synthesis"]
    d = r["delta_reduction"]
    L = [
        "# Edit Plan downstream replay: delta working-set state and a per-session bound",
        "",
        "No plans were generated. The frozen replication's Edit Plans and its 24 selected target",
        "sessions are reused verbatim; only the downstream half was rerun. Two predeclared changes:",
        "the monotone working set stays complete in the harness but is serialized as a handle, exact",
        "per-kind counts and a per-turn delta; and a per-session bound on measured input tokens stops",
        "retrieval with an explicit `SESSION_RESOURCE_LIMIT` record instead of dropping context.",
        "",
        "## 1. Did moving persistent state out of the prompt pay for the run?",
        "",
        f"- Sessions completed: **{b['sessions_run']} of {b['sessions_selected']}** "
        f"(frozen run: 11 of 24, the rest censored by the shared cap).",
        f"- Measured input tokens: **{b['measured_total']:,}** against a {b['global_soft_cap']:,} soft cap.",
        f"- On the **{b['matched_sessions']} sessions both arms ran**: {b['matched_full_total']:,} under full "
        f"serialization against {b['matched_delta_total']:,} under delta, a **{pct(b['matched_reduction'])}** cut.",
        f"- Per-session reduction on matched sessions: median **{pct(d['median']) if d else 'n/a'}**, "
        f"max **{pct(d['max']) if d else 'n/a'}**." if d else "- No matched sessions.",
        f"- Largest session now takes **{pct(b['largest_share_of_total'])}** of the total "
        f"({b['largest_session']['session']}, {b['largest_session']['input_tokens']:,} tokens); median session "
        f"{b['median_session_tokens']:,.0f}." if b["largest_session"] else None,
        f"- Stopped by the per-session bound: {b['sessions_stopped_by_per_session_cap'] or 'none'}.",
        "",
        table(["session", "task", "full", "delta", "reduction", "full WS", "delta WS", "full resp", "delta resp"],
              [[x["session"], x["task"],
                f"{x['full_input_tokens']:,}" if x["full_input_tokens"] else "not run",
                f"{x['delta_input_tokens']:,}", pct(x["reduction"]),
                x["full_working_set"], x["delta_working_set"], x["full_response"], x["delta_response"]]
               for x in r["serialization_ab"]]),
        "",
        "## 2. Did the change move outcomes as well as cost?",
        "",
        f"On matched sessions: **{len(r['outcome_shift']['same'])} unchanged**, "
        f"**{len(r['outcome_shift']['degraded'])} degraded** {r['outcome_shift']['degraded']}, "
        f"**{len(r['outcome_shift']['improved'])} improved** {r['outcome_shift']['improved']}. "
        "Degradation is ranked PROPOSED > ABSTAIN > anything that did not yield a decision.",
        "",
        "Two of those four degradations are instrument artifacts, not model behaviour: session01 is an",
        "output-budget truncation and session02 a parser failure on a correct answer (defects 5 and 6 in",
        "section 5). The genuine ones are session05 PROPOSED -> ABSTAIN and session06, which leaked a",
        "retrieval action into the synthesis turn. Against 3 genuine improvements, this is a wash.",
        "",
        f"After the post-hoc parse correction the label counts become "
        f"`{json.dumps(r['posthoc_parse_replay']['counts_posthoc'])}`, a corrected proposal-or-abstain rate of "
        f"**{pct(r['posthoc_parse_replay']['proposal_rate_posthoc'])}** "
        f"({r['posthoc_parse_replay']['labels_changed']} labels changed). The frozen labels are kept beside them.",
        "",
        f"Proposal rate **{pct(t['proposal_rate'])}** over {t['sessions_run']} sessions, "
        f"retrieval-protocol leakage **{t['retrieval_protocol_leakage']}** {t['leaked_sessions']}. Responses: `{json.dumps(t['counts'])}`.",
        "",
        "## 3. The composed frontier",
        "",
        "Conditioned on evaluator-supported gold targets only. `COMPLETE` means the working set covered",
        "every source the gold formula reads; `EXISTING` means the gold program's relative fingerprint",
        "already occurs in the input workbook.",
        "",
        table(["condition", "n", "exact correct", "fingerprint match"],
              [[k, v["n"], v["correct"], v["fingerprint_match"]] for k, v in c.items()]),
        "",
        "## 4. Workbook scoring",
        "",
        table(["task", "applied writes", "regression", "modification", "zero-edit floor", "gain over floor"],
              [[x["task"], x["applied_writes"], x["regression_accuracy"], x["modification_accuracy"],
                x["zero_edit_modification_floor"], x["modification_gain_over_floor"]] for x in r["benchmark_scores"]]),
        "",
        "### Why every task gained exactly zero over its zero-edit floor",
        "",
        "Not because the writes failed. Regression is 1.0 on all 14 tasks, so the writer stayed",
        "neutral end to end, and the one exactly-correct formula did reach the scored workbook.",
        "session22 proposed `=C68/C$6` for `Income Statement!C69` in 08_03, which is gold's formula",
        "character for character. The recalculated output holds -0.236143090300948 there against",
        "gold's -0.239276339842573, and the cell is scored wrong.",
        "",
        "The difference is `C68`. It is itself one of the evaluator's 342 modification cells on that",
        "range: gold changes its *value* while leaving its formula text alone, so the target computes",
        "from a stale precedent. **Per-cell formula correctness does not compose into workbook credit",
        "when a target's precedents are themselves modified cells.** Twelve isolated writes cannot move",
        "a value-based metric over workbooks that need hundreds of coordinated value changes; 08_03",
        "scores 10/2210 modification cells both with and without our edits.",
        "",
        "This also exposes a population mismatch that the conditional frontier above inherits. The",
        "`gold_target` classification diffs formula *text* (221 changed cells in 08_03); the evaluator",
        "classifies by *value* inside `answer_position` (2,210 modification cells). They are different",
        "sets, so the frontier and the benchmark score are not measured over the same population.",
        "",
        "### 4b. Post-hoc parse arm: the instrument was suppressing a real score",
        "",
        "Diagnostic arm, no model calls: stored raw responses re-parsed with the corrected reader,",
        "then actuated and scored through the identical path. It recovered three answers the frozen",
        "extractor discarded, one of them a PROPOSED formula.",
        "",
        table(["task", "frozen applied", "posthoc applied", "frozen modification", "posthoc modification"],
              [[x["task"], x["frozen_applied"], x["posthoc_applied"], x["frozen_modification"], x["posthoc_modification"]]
               for x in (r["posthoc_actuation_arm"] or {}).get("rows", [])]) if r.get("posthoc_actuation_arm") else "_Not yet run._",
        "",
        "**07_03 moves 0.0 -> 0.75** on the single recovered write `Cashflow (Monthly)!D8 = =Inputs!C11`",
        "(session21), against a zero-edit floor of 0.0. Every other task is identical between arms and",
        "regression stays 1.0 across all 14 in both. So the parser defect was not cosmetic: it was",
        "suppressing the largest score this system has produced. It is also the converse of the 08_03",
        "case — where a target's precedents are already correct, one recovered formula can carry most",
        "of a task." if r.get("posthoc_actuation_arm") else "",
        "",
        "## 5. Defect inventory",
        "",
        "Every defect found across the primary run, the replication and this replay. They are one",
        "family: a control that silently fails to do its job and is then read as a model failure.",
        "",
        table(["#", "defect", "effect", "status"], [
            ["1", "Plan validator disproportion", "optional `source_relation` citations voided whole plans; the rejected `text:` IDs were all real", "fixed in replication (V2 contract)"],
            ["2", "Synthesis transition", "`RETRIEVAL_SYSTEM` reused for the synthesis call", "fixed; proposal rate 12.5% -> 81.8%"],
            ["3", "Writer non-neutrality", "openpyxl round trip changed recalculated values on workbooks it never edited (D23: 122.13 -> 62.84)", "fixed; archive-level writer, gate 18/18 at regression 1.0"],
            ["4", "Inert size guards", "`token_estimate(text)` fed dicts, so `bootstrap_tokens` read 1 for a 15,726-identity bootstrap and the 30k episode limit compared against 6", "fixed; fired once live (session22 q7)"],
            ["5", "Output-budget truncation", "`max_tokens` is shared with reasoning, so a reasoning-heavy turn returns empty text and is scored a bad answer. Retrospective sweep: **34 responses across 4 runs**, 17 of them in the primary composition probe", "repaired: separate `SYNTHESIS_MAX_TOKENS`, and the harness now records `synthesis_truncated` / `TRUNCATED_NO_CONTENT`"],
            ["6", "Duplicate-emission parser", "`extract_json_object` spans first `{` to last `}`, so a correct answer emitted twice is unparseable. Cost 07_03 a 0.75 score. Retrospective sweep: **3 responses, all in this replay** — localised, not project-wide", "repaired at the shared source; repeats must agree or it still fails"],
            ["7", "Metric population mismatch", "`gold_target` diffs formula text; the evaluator diffs values inside `answer_position`", "documented, not resolved"],
        ]),
        "",
        "Defects 5 and 6 were left in the frozen harness while this run was scored, corrected only over",
        "stored raw responses so the primary result stayed frozen, and repaired afterwards. The",
        "pre-repair reader is pinned as `frozen_extract_json_object` so historical comparisons cannot",
        "improve just because the instrument was fixed. Repairing them changes the hashes in this run's",
        "and the replication's `freeze.json`; both are complete, so `check_freeze` failing on them is the",
        "intended signal.",
        "",
        "The retrospective sweep (`benchmark/posthoc_parser_sweep.py`, free) settles their reach.",
        "**Defect 6 is localised**: 3 recoverable responses, all in this replay, none in any other",
        "audited run. **Defect 5 is the widespread one**: 34 responses across 4 runs, concentrated 17 in",
        "`edit-plan-composition-probe` — the primary run whose headline was a 12.5% proposal rate,",
        "measured over responses of which about one in seven was a truncation.",
        "",
        "The sweep also found that **only 5 of 29 runs retained raw response bodies**. Fourteen more",
        "reference a model but kept none, so they cannot be audited for either defect. That is missing",
        "evidence, not a clean bill; retaining raw bodies should be standing practice.",
        "",
        "## 6. Where the cost is now",
        "",
        "Delta state removed the working-set resend. What is left is mostly fixed overhead that it",
        "cannot touch: the bootstrap first send, and the retrieval system prompt re-sent on every one",
        "of the 8 turns. On ordinary sessions that is 65-80% of retrieval input.",
        "",
        table(["session", "calls", "bootstrap q1", "system prompt resent", "variable summaries", "fixed share", "synthesis share of session", "provider cached"],
              [[x["session"], x["calls"], f"{x['bootstrap_first_send']:,}", f"{x['system_prompt_resent']:,}",
                f"{x['variable_summaries']:,}", pct(x["fixed_share"]), pct(x["synthesis_share_of_session"]),
                f"{x['provider_cached_tokens']:,}"] for x in r["retrieval_cost_decomposition"]["rows"]]),
        "",
        "(System-prompt figure is estimated from the frozen prompt text at 4 chars/token, so +/-10%.)",
        "",
        "Three consequences, in the order I would act on them:",
        "",
        "1. **The synthesis turn is now the largest single line item**, 36-64% of a session. It still",
        "   ships the complete working-set ID list plus materialized evidence. The same principle that",
        "   motivated delta state applies to it, though it is harder: synthesis genuinely needs evidence.",
        "2. **The retrieval system prompt is the dominant retrieval cost** at ~3,073 tokens x 8 turns.",
        "   The provider is already caching part of it incidentally (14,400 and 14,016 cached tokens on",
        "   sessions 02 and 03; 0 on synthesis calls). Making that caching deliberate is a saving with",
        "   no semantic change at all, and I would do it before any further working-set work.",
        "3. **The 8-query budget may be over-provisioned.** session04 was stopped by the per-session",
        "   bound after ONE query and produced the identical formula the frozen arm produced with eight",
        "   queries and 1.02M more tokens. One session is an observation, not a finding, but it is cheap",
        "   to test by sweeping the query maximum.",
        "",
        "## 7. Caveats a reader must carry forward",
        "",
        "- **Three changes, not the two predeclared.** `RESULT_TOO_LARGE` fired once (session22 q7,",
        "  16,999 tokens against the 30,000 episode limit). The guard was inert in the frozen arm, so",
        "  that query would have returned in full there. \"Same SQL semantics\" needs this qualifier.",
        "- **session04 is not a like-for-like serialization measurement.** The per-session bound stopped",
        "  it after one query, so its 56% cut mixes delta state with censorship. Its bootstrap first send",
        "  (516,223 tokens) is a cost delta state cannot reach.",
        "- **That bootstrap is a property of one obligation, not of the task.** 04_05/O1 carries a",
        "  15,726-identity bootstrap; 04_05/O2 carries 720 and ran uncapped at 90,180 tokens (session18).",
        "  The pathology is one grounding packet, not bootstrap size in general.",
        "- **The frontier rests on 7 gold-supported targets of 24.** Target selection was evaluator-blind,",
        "  which is methodologically right but leaves the conditional table underpowered. n=7 cannot",
        "  establish the pattern it is directionally consistent with.",
        "- **Outcome shifts are near a wash**, not a regression: of 11 matched sessions, 5 unchanged,",
        "  3 improved, 3 degraded, and only two of those degradations are genuine rather than instrument",
        "  artifacts (session05 PROPOSED->ABSTAIN, session06 leaked a retrieval action).",
        "- **The one leak is a hypothesis worth testing.** `DELTA_RETRIEVAL_SYSTEM` may hold the model in",
        "  retrieval mode harder than the prompt it replaced, partially undoing defect 2's fix. One case",
        "  in 24 does not establish that.",
        "",
        "## 8. What I would do next",
        "",
        "1. Free, before anything else: sweep every probe's stored responses with the corrected parser",
        "   and the truncation label, and republish affected numbers as diagnostics.",
        "2. Separately frozen harness fix for defects 5 and 6 (raise or separate the synthesis output",
        "   budget; make the reader tolerate repeated emissions), then re-run only what it changes.",
        "3. Deliberate prompt caching for the retrieval system prompt.",
        "4. Only then the task -> Edit Plan semantic compilation. The composition finding in section 4",
        "   argues it should target *dependency-closed sets* of cells rather than isolated targets:",
        "   repairing one cell whose precedents are stale earns nothing, which is a property of the",
        "   evaluation, not an artifact of it.",
        "",
    ]
    text = "\n".join(x for x in L if x is not None)
    (OUT / "full_report.md").write_text(text)
    return text


if __name__ == "__main__":
    print(render(build()))
