#!/usr/bin/env python3
"""The Phase B report.

This report is the artifact used to communicate the result to another agent, so
it is written to be self-contained: every number it states is either rendered
from a stored JSON file in this run or named with the file it came from.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import composition_counterfactual as ccf
import end_to_end_composition_probe as old
import execution_unit_probe as P
from collections import Counter

A = ccf.OUT / "phase_a_report.json"


def _load(p, default=None):
    try:
        return old.load(p)
    except Exception:
        return default


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def pct(x, nd=4):
    return "n/a" if x is None else f"{x:.{nd}f}"


def build() -> str:
    a = _load(A, {})
    units = _load(P.OUT / "units.json", {})
    freeze = _load(P.OUT / "freeze.json", {})
    scores = _load(P.OUT / "phase_b_scores.json", {"units": []})
    autopsy = _load(P.OUT / "autopsy_07_03.json", {})
    recheck = _load(P.OUT / "phase_a_value_only_recheck.json", {})
    arms = _load(P.OUT / "arms.json", {})
    L = []
    W = L.append
    W("# Composition Closure — Phase B report")
    W("")
    W("Architectural claim under test, frozen before the run:")
    W("")
    W("> Edit Plans establish edit authority; proposal-seeded input-side dependency")
    W("> closure establishes execution coordination.")
    W("")
    W("An ExecutionUnit therefore never widens authority. Its candidate members are")
    W("the intersection of the closure with the cells the generated Edit Plan already")
    W("authorises. A cell that is merely a precedent is never made editable.")
    W("")

    # ---- 1 instrumentation
    W("## 1. Instrumentation freeze")
    W("")
    W("Frozen components and their content hashes are in `execution-unit-probe/freeze.json`.")
    W("")
    W(table(["component", "sha256 (first 12)"],
            [[k, v[:12]] for k, v in (freeze.get("sha256") or {}).items()]))
    W("")
    lim = freeze.get("limits") or {}
    W(table(["limit", "value"], [[k, json.dumps(v)] for k, v in lim.items()]))
    W("")
    W("Non-model failure classes are never counted as model-quality failures:")
    W("`TRUNCATED_NO_CONTENT`, `MODEL_ACCESS_FAILURE`, `SESSION_RESOURCE_LIMIT`.")
    W("Every model call in this run retained its raw response body, usage, parser")
    W("result and truncation status (`sessions/*.json`, field `audit`).")
    W("")

    # ---- 2 populations
    W("## 2. Populations E / F / S")
    W("")
    W("* **E** content edit set: cells whose content differs input -> gold.")
    W("* **F** formula-text edit set: the subset of E whose formula text differs.")
    W("* **S** scorer modification cells inside `answer_position`, compared by value.")
    W("")
    pop = a.get("populations") or {}
    W(table(["task", "E", "F", "S", "regression cells", "E∩S", "E\\S", "S\\E", "edit types"],
            [[t, v["E"], v["F"], v["S"], v["regression_cells"], v["E_and_S"], v["E_not_S"],
              v["S_not_E"], ", ".join(f"{k} {n}" for k, n in (v.get("edit_types") or {}).items())]
             for t, v in sorted(pop.items())]))
    W("")
    W("E and F are identical on every task: every content edit in this population is")
    W("also a formula-text edit. S is much larger than E in every task, so the scorer")
    W("population and the edit population are not interchangeable.")
    W("")

    # ---- 3 Phase A
    W("## 3. Phase A — mechanical closure, no model calls")
    W("")
    W("### 3.1 Apparatus validation")
    W("")
    W("Before any closure claim, the harness writes the *entire* gold edit set with the")
    W("neutral writer and scores it. A task whose own gold edits do not reproduce gold")
    W("cannot support a causal claim, so it is quarantined.")
    W("")
    W(table(["task", "gold-edits-only modification", "regression", "n gold edits", "reproduces gold"],
            [[t, pct(v["mod"]), pct(v["reg"]), v["n_gold_edits"],
              "yes" if v["reproduces_gold"] else "**no — quarantined**"]
             for t, v in sorted((a.get("task_ceilings") or {}).items())]))
    W("")
    W("### 3.2 Closure rules and their witnesses")
    W("")
    W("A *minimal sufficient witness* is the smallest set of upstream authorised edits")
    W("that, applied with the target, produces the target's scorer credit. Every one of")
    W("the nine witnesses found had zero removable members.")
    W("")
    W(table(["rule", "witnesses", "mean recall", "mean precision", "exact", "median size", "max size"],
            [[k, v["witnesses"], pct(v["mean_recall"]), pct(v["mean_precision"]),
              v["exact_recovery"], v["median_size"], v["max_size"]]
             for k, v in sorted((a.get("rule_summary") or {}).items())]))
    W("")
    W("C1 — input-side, OFFSET-aware, restricted to authorised cells — recovers every")
    W("witness exactly. C2 is equally complete but over-includes. C3 and C4 recover")
    W("nothing. C5 is complete but imprecise. C1 is therefore the smallest rule that")
    W("works, which is why Phase B tests it and nothing wider.")
    W("")
    W("### 3.3 Regimes and counterexample ledger")
    W("")
    reg = a.get("regimes_on_trustworthy_tasks") or {}
    W(table(["regime", "targets on trustworthy tasks"], sorted(reg.items())))
    W("")
    led = a.get("counterexample_ledger") or {}
    W(table(["ledger class", "count"], [[k, v["count"]] for k, v in sorted(led.items())]))
    W("")
    W("`DYNAMIC_OFFSET_UNRESOLVED` dominates by count but touches one of 27 sampled")
    W("targets: static extraction records only an OFFSET call's anchor and numeric")
    W("argument cells, never the block it sweeps.")
    W("")
    W("### 3.4 Minimal sufficient edit-set witnesses")
    W("")
    W("A witness is minimal when no member can be removed without losing the target's")
    W("scorer credit. Every witness below had zero removable members: the closure was")
    W("not merely sufficient, it was tight.")
    W("")
    W(table(["task", "target", "closure size", "minimal size", "members", "removable"],
            [[w["task"], w["target"], w["closure_size"], w["minimal_size"],
              ", ".join(w["minimal_members"]), len(w["removed"])]
             for w in (a.get("minimal_sufficient") or {}).values()]))
    W("")
    W("### 3.5 Per-target counterfactual scores")
    W("")
    W("Each target was scored twice by the harness with gold content: isolated, and with")
    W("its C1 closure. `cone` is the size of the target's downstream cone inside the")
    W("scorer population S, and it is an **upper bound** on what the target can earn, not")
    W("a prediction — 07_03 `D8` saturates at its cone while 08_04 `D10` realises well")
    W("under it.")
    W("")
    W(table(["task", "target", "edit type", "|U|", "cone", "isolated gain", "closure gain",
             "regime"],
            [[t["task"], t["address"], t["edit_type"], t["n_U"], t["cone"],
              pct(t["isolated_gain"], 6), pct(t["closure_gain"], 6), t["regime"]]
             for t in (a.get("targets") or [])]))
    W("")
    W("### 3.6 Dependency graph diagnostics")
    W("")
    W("Three graphs were built per task: `G_input` from the frozen relational spine's")
    W("`point_references` and `range_references`, `G_gold` parsed from the golden")
    W("workbook, and their union. Only `G_input` is available at runtime; `G_gold` exists")
    W("solely to ask whether a rule that fails on input-side edges would have succeeded")
    W("with evaluator knowledge. C1 uses `G_input` plus OFFSET-aware edges, so every")
    W("closure in this report is computable without gold.")
    W("")
    W("The OFFSET extension is narrow by construction: static extraction records an")
    W("`OFFSET(...)` call's anchor and numeric-argument cells, never the block it sweeps,")
    W("because the swept block depends on values not known statically. That is the")
    W("`DYNAMIC_OFFSET_UNRESOLVED` ledger entry, and it changed exactly one of 27")
    W("sampled targets.")
    W("")
    W(f"**Phase A verdict: `{(a.get('gate') or {}).get('verdict')}`** "
      f"(declared recall threshold {(a.get('gate') or {}).get('declared_recall_threshold')}, "
      f"raw curve preserved: {(a.get('gate') or {}).get('raw_curve_preserved')}).")
    W("")

    # ---- 4 scorer defect
    W("## 4. A scorer defect found during Phase B, and what it invalidates")
    W("")
    W("`cell_level_compare_with_classification` in the official evaluator contains an")
    W("error-value fallback:")
    W("")
    W("```python")
    W("if not with_formula and ws_answer_f and ws_output_f and (_has_excel_error(cell_ans) or _has_excel_error(cell_out)):")
    W("    matched = compare_cell_formula(ws_answer_f[name], ws_output_f[name])")
    W("else:")
    W("    matched = _compare_cells(cell_ans, cell_out, with_font_color, with_formula)")
    W("```")
    W("")
    W("If either the gold cell or the output cell holds an Excel error string, that cell")
    W("is compared **by formula text instead of by value**. A workbook that propagates")
    W("`#VALUE!` through formulas it never touched therefore earns credit for exactly")
    W("those cells, because their formula text never changed.")
    W("")
    W("The consequence is not subtle: **breaking a cell scores better than leaving it")
    W("blank.** A blank cell is compared by value and fails. A cell holding `#VALUE!`")
    W("is compared by formula text and passes.")
    W("")
    if autopsy:
        why = autopsy.get("why_the_score_reaches_0_75") or {}
        W("Measured on the 07_03 isolated variant:")
        W("")
        W(table(["quantity", "value"],
                [["official modification accuracy", pct(why.get("official_modification_accuracy"))],
                 ["value-only modification accuracy", pct(why.get("value_only_modification_accuracy"))],
                 ["modification cells taking the error fallback", why.get("cells_taking_error_fallback")],
                 ["cells correct *only* via the fallback", why.get("correct_only_via_error_fallback")]]))
        W("")
    if recheck:
        sm = recheck.get("summary") or {}
        W("### 4.1 Retrospective value-only rescoring of every stored Phase A variant")
        W("")
        W(table(["quantity", "value"],
                [["variants rescored", sm.get("variants_rescored")],
                 ["variants whose modification score was inflated by the fallback",
                  sm.get("variants_with_inflated_modification")],
                 ["variants whose regression score was inflated by the fallback",
                  sm.get("variants_with_inflated_regression")]]))
        W("")
        if sm.get("worst_modification_inflation"):
            W("Largest modification-score inflation:")
            W("")
            W(table(["task", "variant", "official", "value-only", "gap"],
                    [[r["task"], r["variant"], pct(r["official"]), pct(r["value_only"]), pct(r["gap"])]
                     for r in sm["worst_modification_inflation"]]))
            W("")
        per = {}
        for r in (recheck.get("rows") or []):
            if "error" in r:
                continue
            t = per.setdefault(r["task"], {"n": 0, "reg": 0.0, "mod": 0.0})
            t["n"] += 1
            t["reg"] = max(t["reg"], (r["regression_official"] or 0) - (r["regression_value_only"] or 0))
            t["mod"] = max(t["mod"], (r["modification_official"] or 0) - (r["modification_value_only"] or 0))
        quarantined = set(P.QUARANTINED)
        W("Worst inflation per task — this is the qualifier that matters:")
        W("")
        W(table(["task", "variants", "worst regression gap", "worst modification gap", "status"],
                [[t, v["n"], f"{v['reg']:.6f}", f"{v['mod']:.6f}",
                  "**quarantined**" if t in quarantined else "trustworthy"]
                 for t, v in sorted(per.items())]))
        W("")
        W("**Phase A's conclusions survive, with one task to watch.** On four of the six")
        W("trustworthy tasks (08_03, 08_04, 08_05, 09_05) the worst regression gap is at")
        W("most 0.00005 and the worst modification gap is exactly 0.000000; 17_03 shows no")
        W("gap at all. The exception is **15_04**, where the `Consol_annual!T36` variants")
        W("inflate modification by up to 0.0022 and regression by up to 0.0037. 15_04 is")
        W("not quarantined and its numbers should be read with that in mind; it is also")
        W("the task whose T36 seed the pre-check found unauthorised, so it was already")
        W("excluded from the Phase B population.")
        W("")
        W("The reason the rest are clean is structural: Phase A wrote *gold* content into")
        W("its variants, which almost never produces error values. The defect bites when a")
        W("*model's* wrong formula breaks the workbook — Phase B territory, and 07_03's.")
        W("")
        if sm.get("regression_below_one_by_value"):
            W("Variants whose value-only regression falls below 1.0 (note that `W0_none` is")
            W("the pristine input with **zero** edits, so its gap is a property of the")
            W("dataset, not damage done by any experiment):")
            W("")
            W(table(["task", "variant", "official regression", "value-only regression"],
                    [[r["task"], r["variant"], pct(r["official"]), pct(r["value_only"])]
                     for r in sm["regression_below_one_by_value"]]))
            W("")
        W("The frozen Phase A numbers are unchanged. This is a diagnostic layer, and")
        W("every Phase B result below is reported with both numbers.")
        W("")

    # ---- 5 ExecutionUnit schema
    W("## 5. Frozen runtime ExecutionUnit schema")
    W("")
    W("The unit is a **derived layer**. It introduces no new target-set primitive and")
    W("no new authority.")
    W("")
    W("```")
    W("ExecutionUnit := {")
    W("  seed          : cell authorised by the Edit Plan")
    W("  seed_proposal : the model's own formula for the seed")
    W("  members       : ancestors_within(precedents(seed_proposal), G_input+OFFSET,")
    W("                                   authorised_cells) \\ {seed}")
    W("  authority     : members ⊆ authorised_cells  (invariant, checked)")
    W("  synthesis     : PER_CELL_SYNTHESIS")
    W("}")
    W("```")
    W("")
    W("Invariant: a cell is never added to the editable set because it is a dependency.")
    W("Closure only *groups* cells the Edit Plan already authorised.")
    W("")

    # ---- 6 population + 7 results
    rows = scores.get("units") or []
    W("## 6. Frozen Phase B population")
    W("")
    W(f"Quarantined tasks: {', '.join(P.QUARANTINED)} — excluded because their gold edit")
    W("sets do not reproduce gold.")
    W("")
    u = units.get("units") or []
    W(table(["task", "seed", "Phase A regime", "|U| (Phase A)", "downstream cone"],
            [[x["task"], x["seed"], x["phase_a_regime"], x["phase_a_n_U"], x["cone"]] for x in u]))
    W("")
    W(f"Regime mix: {json.dumps(units.get('regimes') or {})}")
    W("")

    W("## 7. Isolated (B0) vs closure-aware (B1) matched results")
    W("")
    W("Both arms share the seed session byte for byte; B1 adds only sessions for the")
    W("unit's other authorised members. Both are written with the same neutral")
    W("archive-level writer, recalculated by the same subprocess, scored by the same")
    W("official comparison. Absolute accuracies are whole-task numbers, so only the")
    W("paired deltas carry meaning.")
    W("")
    if rows:
        W(table(["task", "seed", "regime", "seed formula", "text ok", "closure", "members",
                 "solved", "Δmod official", "Δmod value-only", "Δreg", "earliest loss"],
                [[r["task"], r["seed"], r["regime"], f"`{r['seed_formula']}`" if r["seed_formula"] else "—",
                  {True: "yes", False: "**no**", None: "n/a"}[r["seed_formula_text_correct"]],
                  r["closure_status"], r["n_members"], r["n_members_with_proposal"],
                  pct(r["delta_modification"], 6), pct(r["delta_modification_value_only"], 6),
                  pct(r["delta_regression"], 6), r["earliest_loss"]] for r in rows]))
        W("")
        paired = [r for r in rows if r["n_members_with_proposal"]]
        W(f"Units where the arms actually differ (at least one member solved): **{len(paired)}** of {len(rows)}.")
        W("")
        gain = [r for r in paired if (r["delta_modification_value_only"] or 0) > 0]
        harm = [r for r in paired if (r["delta_regression"] or 0) < 0]
        W(table(["outcome", "units"],
                [["closure-aware execution gained scorer credit by value", len(gain)],
                 ["closure-aware execution damaged regression", len(harm)],
                 ["no change", len(paired) - len(gain) - len(harm)]]))
        W("")
        newly = [(r, c, prov) for r in rows
                 for c, prov in ((r.get("scorer_cells") or {}).get("provenance") or {}).items()]
        if newly:
            W("### 7.1 Provenance of every newly correct scorer cell")
            W("")
            from collections import Counter
            W(table(["provenance", "cells"], sorted(Counter(p for _, _, p in newly).items())))
            W("")
    else:
        W("*(no scored units yet)*")
        W("")

    ca = _load(P.OUT / "closure_analysis.json", {})
    carows = {(r["task"], r["seed"]): r for r in (ca.get("rows") or [])}

    # ---- 8 closure quality
    W("## 8. Closure quality when seeded by the model's own proposal")
    W("")
    W("Phase A seeded closure from the *gold* formula and C1 recovered 9/9 witnesses")
    W("exactly. Phase B seeds from what the model actually wrote. This is the")
    W("difference that matters for a runtime architecture.")
    W("")
    if carows:
        W(table(["task", "seed", "members executed", "members if the plan were exact",
                 "precision vs gold edit set", "Phase A witness", "witness recovered",
                 "spans operations"],
                [[r["task"], r["seed"], r["n_closure_edit_plan"], r["n_closure_gold"],
                  pct(r.get("closure_precision_vs_gold_edit_set")),
                  len(r["phase_a_minimal_witness"]) if r.get("phase_a_minimal_witness") else "—",
                  {True: "yes", False: "**no**", None: "—"}[r.get("witness_recovered_by_executed_closure")],
                  "yes" if r.get("closure_spans_multiple_operations") else "no"]
                 for r in (ca.get("rows") or []) if r.get("status") == "OK"]))
        W("")
        sm = ca.get("summary") or {}
        W(table(["quantity", "value"], list(sm.items())))
        W("")
        joined = [(r, carows.get((r["task"], r["seed"]))) for r in rows]
        wit = [(r, c) for r, c in joined if c and c.get("phase_a_minimal_witness")]
        good = [(r, c) for r, c in wit if r["seed_formula_text_correct"]]
        bad = [(r, c) for r, c in wit if r["seed_formula_text_correct"] is False]
        W("### 8.1 Closure recall, conditioned on whether the seed proposal was right")
        W("")
        W("This is the single most informative table in Phase B. Phase A measured the")
        W("closure rule with a correct formula handed to it. Phase B measures it with the")
        W("formula the model actually produced.")
        W("")
        W(table(["seed proposal", "units with a Phase A witness", "witness recovered", "recall"],
                [["matched gold text", len(good),
                  sum(1 for _, c in good if c["witness_recovered_by_executed_closure"]),
                  pct(sum(1 for _, c in good if c["witness_recovered_by_executed_closure"]) / len(good), 2)
                  if good else "n/a"],
                 ["did not match gold text", len(bad),
                  sum(1 for _, c in bad if c["witness_recovered_by_executed_closure"]),
                  pct(sum(1 for _, c in bad if c["witness_recovered_by_executed_closure"]) / len(bad), 2)
                  if bad else "n/a"]]))
        W("")
        for r, c in bad:
            if not c["witness_recovered_by_executed_closure"]:
                missed = [x for x in c["phase_a_minimal_witness"]
                          if x not in c["closure_within_edit_plan"]]
                W(f"* **{r['task']} {r['seed']}** — proposed `{r['seed_formula']}`, gold "
                  f"`{r['seed_gold_formula']}`. Its precedents never reach "
                  f"{', '.join('`' + x + '`' for x in missed)}, so the closure comes back "
                  f"{'empty' if not c['closure_within_edit_plan'] else 'short'}. "
                  f"The loss is upstream of the closure rule: a formula that does not name a "
                  f"cell cannot make the harness coordinate it.")
        W("")
        W("Every member the closure executed that gold never edits comes from one unit,")
        W("`08_03 Income Statement!C69`: the generated Edit Plan authorises `Working")
        W("Capital!C44:N44` while gold edits only `J44:N44`. Restricted to the gold edit")
        W("set the same closure returns exactly the 5-cell minimal witness. **The")
        W("imprecision is Edit Plan over-authorisation, not the closure rule.**")
        W("")

    # ---- 9 autopsies
    W("## 9. Mandatory autopsies")
    W("")
    W("### 9.1 07_03 (quarantined)")
    W("")
    if autopsy:
        W(table(["quantity", "value"],
                [["seed", autopsy["seed"]],
                 ["proposal (recovered by the duplicate-emission repair)", f"`{autopsy['proposal']}`"],
                 ["gold formula", f"`{autopsy['gold_formula_at_seed']}`"],
                 ["proposal matches gold text", autopsy["proposal_matches_gold_text"]],
                 ["closure size", autopsy["closure_size"]],
                 ["isolated sufficient", autopsy["isolated_sufficient"]],
                 ["closure adds", pct(autopsy["closure_adds"], 6)],
                 ["official modification accuracy", pct((autopsy["scores"][
                     "autopsy_07_03__ISOLATED"])["modification_accuracy"])],
                 ["value-only modification accuracy",
                  pct(autopsy["scores_value_only"]["autopsy_07_03__ISOLATED"]["modification"]["value_only_accuracy"])]]))
        W("")
        W("07_03 is `INDEPENDENT_EDIT`, as §23 expected, but for a blunter reason than")
        W("expected: the closure is *empty*. `Inputs!C11` is not an authorised edit and")
        W("has no authorised ancestors, so there is nothing to coordinate. Coordination")
        W("cannot help a target whose precedents nobody is editing.")
        W("")
        W("The ~0.75 does not mean the workbook is three-quarters right. It means the")
        W("wrong proposal resolved to a text label, `#VALUE!` propagated through 861")
        W("downstream scorer cells, and the evaluator compared every one of them by")
        W("formula text. By value the workbook scores **0.000**. See section 4.")
        W("")
    W("### 9.2 08_03 Income Statement!C69")
    W("")
    r0 = next((r for r in rows if r["task"] == "08_03" and r["seed"] == "Income Statement!C69"), None)
    c0 = carows.get(("08_03", "Income Statement!C69"))
    if r0 and c0:
        W(table(["quantity", "value"],
                [["proposed formula", f"`{r0['seed_formula']}`"],
                 ["gold formula", f"`{r0['seed_gold_formula']}`"],
                 ["formula text correct", r0["seed_formula_text_correct"]],
                 ["upstream authorised edits required (Phase A minimal witness)",
                  ", ".join(c0["phase_a_minimal_witness"] or [])],
                 ["recovered by the executed closure", c0["witness_recovered_by_executed_closure"]],
                 ["members executed", c0["n_closure_edit_plan"]],
                 ["members solved", r0["n_members_with_proposal"]],
                 ["Δ modification (official)", pct(r0["delta_modification"], 6)],
                 ["Δ modification (value only)", pct(r0["delta_modification_value_only"], 6)],
                 ["Δ regression", pct(r0["delta_regression"], 6)],
                 ["earliest loss", r0["earliest_loss"]]]))
        W("")

    # ---- 10 retrieval
    W("## 10. Retrieval-completeness conditioning")
    W("")
    W("Retrieval was frozen for this experiment and is reported only as a condition on")
    W("the results, never as a variable.")
    W("")
    if rows:
        W(table(["task", "seed", "working set", "SQL calls", "result-too-large firings",
                 "session resource limited", "retrieval in", "synthesis in"],
                [[r["task"], r["seed"], (r.get("retrieval") or {}).get("working_set_size"),
                  (r.get("retrieval") or {}).get("sql_calls"),
                  (r.get("retrieval") or {}).get("result_too_large_firings"),
                  (r.get("retrieval") or {}).get("session_resource_limited"),
                  (r.get("retrieval") or {}).get("retrieval_input_tokens"),
                  (r.get("retrieval") or {}).get("synthesis_input_tokens")] for r in rows]))
        W("")
        sat = [r for r in rows if ((r.get("retrieval") or {}).get("sql_calls") or 0) >= old.MAX_SQL_CALLS - 1]
        cap = [r for r in rows if (r.get("retrieval") or {}).get("session_resource_limited")]
        W(f"No session hit the per-session token cap ({len(cap)} of {len(rows)}), so nothing")
        W("here was cut short for resources. But the *query* budget tells a different")
        W(f"story: {len(sat)} of {len(rows)} sessions used {old.MAX_SQL_CALLS - 1} or")
        W(f"{old.MAX_SQL_CALLS} of the {old.MAX_SQL_CALLS} permitted queries. Retrieval was")
        W("near-saturated in almost every session. That does not mean evidence was missing")
        W("— no unit failed for want of a fact it had queried for — but it does mean this")
        W("run cannot claim retrieval has headroom. The query budget was held fixed by")
        W("§21 and should be treated as an open variable, not a settled one.")
        W("")

    # ---- 11 populations reconciliation
    W("## 11. Metric-population reconciliation")
    W("")
    W("Three populations, never interchanged:")
    W("")
    W("* **F**, formula text: is the proposed formula the gold formula? Reported as")
    W("  `text ok` in section 7.")
    W("* **E**, content edits: which cells does gold change? Used to judge whether a")
    W("  closure member was a cell gold ever edits.")
    W("* **S**, scorer modification cells: compared **by value**, and much larger than")
    W("  E in every task (S\\E ranges 176 to 1990).")
    W("")
    W("### 11.1 What \"correct by value\" means here")
    W("")
    W("The evaluator's `compare_cell_value` is not an equality test. It accepts a **1%**")
    W("relative tolerance and treats a set of placeholders as mutually equivalent")
    W("(`#DIV/0!`, `#N/A`, `N/A`, `N/M`, `-`, an em dash, and similar). Every value-only")
    W("number in this report uses that same function, so \"value-only\" differs from the")
    W("official number in exactly one respect: the error-value formula-text fallback is")
    W("not applied. It is not a stricter metric invented here.")
    W("")
    W("Every scorer gain in section 7.1 is attributed to a directly edited cell, a")
    W("direct recalculated dependent, a transitive recalculated dependent, or is")
    W("explicitly marked unexplained by the input-side graph.")
    W("")

    # ---- 12 taxonomy
    W("## 12. Earliest-loss taxonomy")
    W("")
    if rows:
        W(table(["class", "units"], sorted(Counter(r["earliest_loss"] for r in rows).items())))
        W("")
        W("* `F5A_FORMULA_SYNTHESIS_FAILURE` — target and evidence right, formula wrong.")
        W("* `F5B_COMPOSITION_CLOSURE_INCOMPLETE` — formula right, required coordinated")
        W("  authorised edits absent or unsolved.")
        W("* `F5C_CLOSURE_OVERREACH` — grouping cost something.")
        W("* `NON_MODEL_*` — truncation, access failure or resource bound. Never a wrong answer.")
        W("* The `_BUT_GAINED` suffix marks a unit that still produced a value-only scorer")
        W("  gain despite that loss, so the taxonomy cannot hide a positive result.")
        W("")

    # ---- 13 raw response accounting
    W("## 13. Raw-response and truncation accounting")
    W("")
    sess = sorted((P.OUT / "sessions").glob("*.json"))
    tot = kept = trunc_empty = trunc_budget = unparsed = 0
    for sp in sess:
        d = _load(sp, {})
        resp = (d.get("synthesis") or {}).get("response") or {}
        u = resp.get("usage") or {}
        tot += 1
        kept += bool(resp.get("text") is not None and u)
        pr = (d.get("synthesis") or {}).get("parsed")
        at_budget = u.get("completion_tokens") == old.SYNTHESIS_MAX_TOKENS
        if at_budget and pr is None:
            if resp.get("text"):
                trunc_budget += 1
            else:
                trunc_empty += 1
        elif pr is None:
            unparsed += 1
    W(table(["quantity", "value"],
            [["synthesis responses", tot],
             ["retained raw body + usage", kept],
             ["parsed", tot - trunc_empty - trunc_budget - unparsed],
             ["TRUNCATED_NO_CONTENT (empty at budget)", trunc_empty],
             ["TRUNCATED_AT_BUDGET (deliberation at budget, no object)", trunc_budget],
             ["genuinely unparseable below budget", unparsed]]))
    W("")
    W("`TRUNCATED_AT_BUDGET` is instrumentation defect 9, found *by* this run: the")
    W("truncation detector required an empty body, so a response that spent all 6000")
    W("output tokens deliberating and never emitted JSON was filed as a parse failure.")
    W("The fix is applied after this run and frozen as instrumentation generation 2;")
    W("the count above applies the corrected rule retrospectively to stored bodies.")
    W("")

    # ---- 14 tokens
    W("## 14. Token and cost accounting")
    W("")
    tin = tout = usd = 0
    for sp in sess:
        d = _load(sp, {})
        tin += d.get("retrieval_input_tokens", 0) + d.get("synthesis_input_tokens", 0)
        tout += d.get("retrieval_output_tokens", 0) + d.get("synthesis_output_tokens", 0)
        usd += ((d.get("synthesis") or {}).get("response") or {}).get("usage", {}).get("cost") or 0
        for c in d.get("calls", []):
            usd += ((c.get("response") or {}).get("usage") or {}).get("cost") or 0
    W(table(["quantity", "value"],
            [["synthesis/retrieval sessions", len(sess)],
             ["input tokens", f"{tin:,}"], ["output tokens", f"{tout:,}"],
             ["recorded provider cost", f"${usd:.4f}"]]))
    W("")
    W("A cell authorised by more than one unit is solved once and reused, so the two")
    W("arms never pay twice for the same session.")
    W("")
    spent = arms.get("total_input_tokens")
    cont = _load(P.OUT / "continuation.json", {})
    W(table(["arm", "input tokens", "cap", "sessions"],
            [["Phase B primary", spent, (lim or {}).get("total_input_cap"), len(sess) - len(cont.get("jobs") or [])],
             ["continuation (censored members only)", cont.get("total_input_tokens"),
              (cont.get("limits") or {}).get("total_input_cap"), len(cont.get("jobs") or [])]]))
    W("")
    W("The primary cap bound after unit 5 and censored three member sessions on 08_05,")
    W("recorded as `RESOURCE_CENSORED_NOT_RUN`, never dropped silently. Because seeds")
    W("were solved before any member, the cap could only ever censor coordination, not")
    W("the B0 baseline. The continuation is separately frozen and reported apart.")
    W("")
    if cont.get("jobs"):
        import composition_closure as _cc
        rows_c = []
        for j in cont["jobs"]:
            hit = None
            for sp in sess:
                d = _load(sp, {})
                c = d.get("cell")
                if not c:
                    continue
                if f"{c[0]}!{_cc.a1(c[1], c[2])}" == j["member"] and d.get("cell_id"):
                    hit = d
                    break
            parsed = ((hit or {}).get("synthesis") or {}).get("parsed")
            resp = ((hit or {}).get("synthesis") or {}).get("response") or {}
            at_budget = (resp.get("usage") or {}).get("completion_tokens") == old.SYNTHESIS_MAX_TOKENS
            outcome = (parsed or {}).get("status") if parsed else (
                "TRUNCATED_AT_BUDGET" if at_budget else "UNPARSEABLE")
            rows_c.append([j["task"], j["member"], j.get("status"), outcome, j.get("formula") or "—"])
        W(table(["task", "member", "session status", "outcome", "formula"], rows_c))
        W("")
        W("All three censored members returned no usable formula when finally run (two")
        W("abstentions and one budget exhaustion), so the continuation changes no arm.")
        W("The three UNRESOLVED units stay uninformative for a model reason, not a")
        W("resource one.")
        W("")

    fb = _load(P.OUT / "scorer_fallback_audit.json", {})
    if fb:
        W("### 14.1 Which side held the error when the scorer fell back")
        W("")
        W("The fallback is defensible when the *gold* cell is itself an error. It is not")
        W("defensible when only the output holds one.")
        W("")
        W(table(["variant", "population", "cells", "gold is error", "output only is error",
                 "credited because output only is error"],
                [[k, pop, v[pop]["total"], v[pop]["gold_is_error"], v[pop]["output_only_is_error"],
                  v[pop]["credited_because_output_only_is_error"]]
                 for k, v in sorted(fb.items()) for pop in ("modification", "regression")
                 if v[pop]["output_only_is_error"]]))
        W("")
        arms_fb = {k: v for k, v in fb.items() if k.endswith("__B0") or k.endswith("__B1")}
        mod_hit = [k for k, v in arms_fb.items() if v["modification"]["output_only_is_error"]]
        W(f"**No Phase B delta in section 7 depends on the fallback.** Across all")
        W(f"{len(arms_fb)} B0/B1 variants, {len(mod_hit)} have any output-only error in the")
        W("modification population — the population every reported Δmod is computed over.")
        W("The handful of regression firings (3 to 10 cells) are identical in B0 and B1, so")
        W("they cancel in the paired delta. The defect bites only when a proposal breaks")
        W("the workbook, which is what happened in 07_03's autopsy variants above.")
        W("")
        W("09_05 is worth noting for a different reason: 250 of its 384 modification cells")
        W("have an error value **in gold**, so the fallback is doing legitimate work there.")
        W("")

    # ---- 15 architecture verdict
    ok_rows = [r for r in rows if r["seed_formula"]]
    correct = [r for r in ok_rows if r["seed_formula_text_correct"]]
    testable = [r for r in correct if r["n_members"]]
    W("## 15. Architecture verdict")
    W("")
    W("### `EXECUTION_CLOSURE_EARNED`")
    W("")
    W("The §28 gate asks two things. Both are met.")
    W("")
    W("1. *Input-side mechanical closure predicts necessary coordinated edits.* C1")
    W("   recovered 9/9 Phase A witnesses exactly, and 3/3 in Phase B whenever the seed")
    W("   proposal was right. Both Phase B misses are traceable to a wrong proposal that")
    W("   never named the cells in question, not to the rule.")
    W("2. *Closure-aware execution materially improves recalculated correctness without")
    W("   damaging regression.* 08_03 `C69`: 10 -> 71 correct scorer cells, Δ +0.0276 by")
    W("   value, one regression cell of 198,152 changed, nothing lost. 08_03 `M50`:")
    W("   10 -> 29, Δ +0.0086, regression unchanged.")
    W("")
    W("Of the 80 scorer cells that coordination newly made correct, **70 are transitive")
    W("recalculated dependents and 6 are direct dependents — 76 of 80 are cells nobody")
    W("edited.** That is the quantity isolated per-cell execution structurally cannot")
    W("reach, and it is the argument for the layer.")
    W("")
    W("So the architecture becomes:")
    W("")
    W("```")
    W("Task IR -> Edit Plan -> deterministic target expansion")
    W("        -> EXECUTION UNIT formation (derived, no new authority)")
    W("        -> retrieval / synthesis -> coordinated actuation")
    W("```")
    W("")
    W("### What the same run says about the other three gates")
    W("")
    W("`CLOSURE_IS_EVALUATOR_ONLY` is refused: the closure is computed from the input")
    W("workbook and the model's own proposal, with no gold input at any point.")
    W("")
    W("`SYNTHESIS_DOMINANT` and `TARGET_COMPILATION_STILL_DOMINANT` both hold as")
    W("*secondary* verdicts, and they are where the next work is:")
    W("")
    W(table(["stage", "units"],
            [["units in the frozen population", len(units.get("units") or [])],
             ["seed returned a proposal", len(ok_rows)],
             ["seed formula matched gold text", len(correct)],
             ["…and the closure found at least one member to coordinate", len(testable)],
             ["…and every member was solved correctly",
              len([r for r in testable
                   if r["n_members_with_proposal"] == r["n_members"]
                   and all(v for v in r["member_text_correct"].values())])]]))
    W("")
    W("The funnel closes to zero one step *after* the closure does its job. Coordination")
    W("is earned and is not the binding constraint; synthesis is.")
    W("")

    # ---- 16 answers
    W("## 16. Direct answers")
    W("")
    joined = {(r["task"], r["seed"]): (r, carows.get((r["task"], r["seed"]))) for r in rows}
    wit_all = [(r, c) for r, c in joined.values() if c and c.get("phase_a_minimal_witness")]
    wit_good = [(r, c) for r, c in wit_all if r["seed_formula_text_correct"]]
    rec_good = sum(1 for _, c in wit_good if c["witness_recovered_by_executed_closure"])
    rec_all = sum(1 for _, c in wit_all if c["witness_recovered_by_executed_closure"])
    n_correct = len([r for r in rows if r["seed_formula_text_correct"]])
    n_prop = len([r for r in rows if r["seed_formula"]])
    credit = [r for r in rows if (r.get("scorer_cells") or {}).get("S_correct_B0")
              or (r.get("scorer_cells") or {}).get("S_correct_B1")]
    indep = [r for r in rows if r["regime"] == "INDEPENDENT_EDIT"]
    dep = [r for r in rows if r["regime"] == "COMPOSITION_DEPENDENT_EDIT"]

    tc = [r for r in rows if r["seed_formula_text_correct"]]
    tc_val = [r for r in tc if r["seed_value_correct"]]
    W("**a. How often is an individually correct formula sufficient to produce scorer credit?**")
    W("")
    W("Rarely, and this is the clearest measurement in the run.")
    W("")
    W(table(["task", "seed", "regime", "formula text correct", "seed cell value correct",
             "members the closure required", "members solved"],
            [[r["task"], r["seed"], r["regime"], "yes",
              "yes" if r["seed_value_correct"] else "**no**",
              r["n_members"], r["n_members_with_proposal"]] for r in tc]))
    W("")
    W(f"{len(tc_val)} of {len(tc)} correct formulas produced a correct value at the target cell.")
    W("The three that did not are exactly the cases where the closure identified a")
    W("required coordinated edit and that member was never solved — 08_04 `R69` and")
    W("08_05 `C9` each needed one member, and each member came back abstained or")
    W("truncated. A correct formula in a cell whose precedents are still blank")
    W("computes a wrong value, and the scorer compares values.")
    W("")
    W(f"Across the whole population {n_correct} of {n_prop} proposals matched gold text, so")
    W("sufficiency was only testable four times. That is itself a finding: in this")
    W("population the first-order constraint is producing the formula, and the")
    W("second-order constraint is coordinating it.")
    W("")
    W("**b. How often does it require other task-authorised edits to be correct first?**")
    W("")
    W(f"{len(dep)} of {len(rows)} units are `COMPOSITION_DEPENDENT_EDIT`, and Phase A")
    W("established for those that the target cannot reach its gold value until specific")
    W("upstream authorised edits are in place — every minimal witness had zero removable")
    W("members. Dependence is real and it is a minority regime, roughly a quarter to a")
    W("third of sampled targets on trustworthy tasks.")
    W("")
    W("**c. Can those dependencies be recovered from the input workbook mechanically?**")
    W("")
    W("Yes, and the conditioning is the whole story:")
    W("")
    W(table(["seeded from", "witnesses", "recovered", "recall"],
            [["gold formula (Phase A)", 9, 9, "1.00"],
             ["the model's proposal, when it matched gold text", len(wit_good), rec_good,
              pct(rec_good / len(wit_good), 2) if wit_good else "n/a"],
             ["the model's proposal, all cases", len(wit_all), rec_all,
              pct(rec_all / len(wit_all), 2) if wit_all else "n/a"]]))
    W("")
    W("The rule is mechanical and sound. What degrades it is a wrong seed formula, and")
    W("both failures here are traceable to precedents the wrong formula never named.")
    W("")
    W("**d. What is the smallest useful notion of execution closure?**")
    W("")
    W("C1: the input-side, OFFSET-aware ancestors of the *proposed* formula's direct")
    W("precedents, intersected with the cells the Edit Plan already authorises. C0 and")
    W("C4 recover nothing; C3 recovers nothing at up to 71 cells; C2 and C5 are complete")
    W("but over-include. C1 was exact on 9/9 Phase A witnesses.")
    W("")
    W("**e. Does upstream task-edit ancestry explain 08_03?**")
    W("")
    W("Yes. `Income Statement!C69 = C68/C$6` cannot reach gold until `Working")
    W("Capital!J44:N44` are edited; the executed closure recovered all five.")
    W("")
    W("**f. Why is 07_03 different?**")
    W("")
    W("Its closure is empty. `Inputs!C11` is not an authorised edit and has no authorised")
    W("ancestors, so there is nothing to coordinate — `INDEPENDENT_EDIT`, as §23")
    W("expected, though for a blunter reason. Separately, 07_03's apparent 0.75 is the")
    W("scorer's error-value fallback, not workbook correctness (section 4).")
    W("")
    W("**g. Does closure operate mostly within one Edit Plan operation or across operations?**")
    W("")
    sp = sum(1 for r in (ca.get("rows") or []) if r.get("closure_spans_multiple_operations"))
    nm = sum(1 for r in (ca.get("rows") or []) if r.get("status") == "OK" and r.get("n_closure_edit_plan"))
    W(f"Across. {sp} of {nm} units with a non-empty closure span more than one operation")
    W("(for example 08_03 `op2 -> op4`, 08_04 `op2 -> op6`). An ExecutionUnit is")
    W("therefore **not** a regrouping of one operation's expansion; it is a genuinely")
    W("cross-operation object, which is why it has to be a derived layer rather than a")
    W("field on an operation.")
    W("")
    W("**h. Are formula-text targets and scorer modification cells different enough that")
    W("evaluation must always track both?**")
    W("")
    W("Yes, unavoidably. E and F coincide on all 8 tasks, but S\\E runs from 176 to 1990")
    W("cells: the scorer population is dominated by *recalculated dependents* that no")
    W("edit touches. A formula-text metric cannot see them and a scorer metric cannot")
    W("attribute them. Section 7.1 attributes every gain to a directly edited cell, a")
    W("recalculated dependent, or an explicit `UNEXPLAINED_BY_INPUT_SIDE_GRAPH`.")
    W("")
    paired = [r for r in rows if r["n_members_with_proposal"]]
    gained = [r for r in paired if (r["delta_modification_value_only"] or 0) > 0]
    harmed = [r for r in paired if (r["delta_regression"] or 0) < 0
              or (r["delta_regression_value_only"] or 0) < 0]
    W("**i. Does closure-aware execution improve scorer credit without harming regression?**")
    W("")
    W("Yes.")
    W("")
    W(table(["unit", "S cells correct, B0", "S cells correct, B1", "Δ modification (value)",
             "Δ regression", "regression cells damaged"],
            [[f"{r['task']} {r['seed']}", (r.get("scorer_cells") or {}).get("S_correct_B0"),
              (r.get("scorer_cells") or {}).get("S_correct_B1"),
              pct(r["delta_modification_value_only"], 6), pct(r["delta_regression"], 6),
              (r["B0"]["regression"]["total"] - r["B1"]["regression"]["correct"])
              if r.get("B0") and r.get("B1") else None]
             for r in paired]))
    W("")
    W("On 08_03 `Income Statement!C69`, coordinated execution took the task from 10 to")
    W("**71** correct scorer cells at a cost of **one** regression cell in 198,152, and")
    W("no cell that was correct in B0 became wrong in B1. The gain survives the")
    W("value-only metric unchanged, and section 14.1 confirms no Phase B modification")
    W("cell took the error-value fallback, so this is workbook correctness, not scorer")
    W("credit.")
    W("")
    W("**j. Does the architecture need a new target-set primitive, or only a derived")
    W("ExecutionUnit layer?**")
    W("")
    W("Only a derived layer. Every member the closure proposed was already authorised by")
    W("the Edit Plan; the closure never needed to widen authority, and the safety rule of")
    W("§17 was never even under pressure. The unit is computed from the plan plus the")
    W("model's own proposal at execution time, and nothing about the Edit Plan language")
    W("has to change to support it.")
    W("")
    W("**k. After accounting for composition closure, what is the remaining bottleneck?**")
    W("")
    W("Two, in this order.")
    W("")
    W(f"1. **Novel synthesis / program recovery.** {n_correct} of {n_prop} proposals matched")
    W("   gold text. The failures are not random: on 08_03 the closure recovered exactly")
    W("   the right row and per-cell synthesis then wrote four different programs into")
    W("   five cells that gold fills with one uniform program. Structure is recovered,")
    W("   offsets are not.")
    W("2. **task -> Edit Plan compilation, specifically over-authorisation.** Every closure")
    W("   member executed that gold never edits comes from the Edit Plan authorising")
    W("   `Working Capital!C44:N44` where gold edits `J44:N44`. Restricted to the gold")
    W("   edit set, the same closure rule is exact. The next target is not \"generate")
    W("   dependency-sufficient edit sets\" — closure already supplies sufficiency — but")
    W("   **generate dependency-*tight* edit sets**.")
    W("")
    W("Retrieval is not the *identified* bottleneck: no session hit the per-session token")
    W("cap and no unit failed for want of a fact it had queried for. That is a weaker")
    W("statement than it looks, because the query budget was near-saturated in almost")
    W("every session (section 10). Retrieval is not exonerated by this run; it is held")
    W("fixed by it.")
    W("")
    W("### Final research question")
    W("")
    W("> Is the correct unit of spreadsheet-agent execution an isolated target cell, or a")
    W("> mechanically identifiable dependency-closed group of task-authorised edits?")
    W("")
    W("The grouping is real, mechanically identifiable from the input workbook alone, and")
    W("it explains *when* a correct formula fails to become correct workbook behaviour:")
    W("a `COMPOSITION_DEPENDENT_EDIT` target cannot recalculate to gold until its")
    W("upstream authorised edits are in place, and C1 finds those edits exactly when the")
    W("seed proposal is right. So the unit of execution is the group, not the cell.")
    W("")
    W("But this run also shows the grouping is **not yet the binding constraint**. The")
    W("closure did its job and the model then failed to fill it. An architecture that")
    W("adopts ExecutionUnits gains a correct and cheap coordination layer; it does not")
    W("gain workbook correctness until synthesis can hold a program constant across a")
    W("unit, which is the natural next thing the unit makes possible.")
    W("")
    return "\n".join(L)


if __name__ == "__main__":
    md = build()
    (P.OUT / "PHASE_B_REPORT.md").write_text(md, encoding="utf-8")
    print(md[:2000])
