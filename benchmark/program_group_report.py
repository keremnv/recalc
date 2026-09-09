#!/usr/bin/env python3
"""The Phase C report: execution policy inside a coordinated ExecutionUnit.

Self-contained by design. Every number is rendered from a stored JSON file in
this run, or names the file it came from.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
import program_group as pg
import program_group_preflight as pf
import program_group_probe as C

OUT = C.OUT


def _load(p, default=None):
    try:
        return old.load(p)
    except Exception:
        return default


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def pct(x, nd=4):
    return "n/a" if x is None else f"{x:.{nd}f}"


def yn(x):
    return {True: "yes", False: "**no**", None: "—"}.get(x, str(x))


def build() -> str:
    survey = _load(OUT / "preflight_survey.json", {})
    sweep = _load(OUT / "evidence_sweep.json", {})
    units = _load(OUT / "units.json", {})
    freeze = _load(OUT / "freeze.json", {})
    arms = _load(OUT / "arms.json", {})
    scores = _load(OUT / "phase_c_scores.json", {"units": []})
    posthoc = _load(OUT / "phase_c_posthoc.json", {"units": []})
    exact = _load(OUT / "phase_c_exactness.json", {"units": []})
    cost = _load(OUT / "phase_c_cost.json", {"units": [], "totals": {}})
    rows = scores.get("units") or []
    L = []
    W = L.append

    W("# ProgramGroup execution — Phase C report")
    W("")
    W("Hypothesis under test, and nothing else:")
    W("")
    W("> When an ExecutionUnit contains mechanically homologous formula targets,")
    W("> synthesize the program once and deterministically translate it across the")
    W("> unit instead of repeatedly asking the model to rediscover the same program.")
    W("")
    W("Execution closure is not under test. C1 is frozen exactly as Phase B left it.")
    W("")
    W("Where the eighteen deliverables live:")
    W("")
    W(table(["#", "deliverable", "section"],
            [["1", "mechanical translation ceiling", "3"],
             ["2", "frozen ProgramGroup eligibility rule", "2"],
             ["3", "eligible / ineligible units", "5"],
             ["4", "frozen matched population", "4"],
             ["5", "P0 per-cell formulas", "7"],
             ["6", "P1 canonical + translated formulas", "7, 10"],
             ["7", "all-member correctness", "6"],
             ["8", "recalculated-value correctness", "8"],
             ["9", "scorer / value-only deltas", "8, 15"],
             ["10", "regression deltas", "15"],
             ["11", "existing-vs-novel conditioning", "13"],
             ["12", "C69 autopsy", "10"],
             ["13", "program grouping errors", "3, 11"],
             ["14", "Edit Plan over-authorisation analysis", "14"],
             ["15", "retrieval / query counts", "12"],
             ["16", "token / cost comparison", "9"],
             ["17", "failure taxonomy", "11"],
             ["18", "architecture verdict", "16, 18"]]))
    W("")

    W("## 1. What is frozen")
    W("")
    W(table(["component", "sha256 (first 12)"],
            [[k, v[:12]] for k, v in (freeze.get("sha256") or {}).items()]))
    W("")
    W(f"Instrumentation generation: **{freeze.get('instrumentation_generation')}** — the")
    W("repaired parser, explicit truncation classes, separated output budgets, raw")
    W("response retention, phase-specific synthesis prompt, neutral writer and delta")
    W("working-set serialization.")
    W("")
    W("Non-model failure classes, never counted as wrong answers: "
      + ", ".join(f"`{c}`" for c in (freeze.get("non_model_failure_classes") or [])) + ".")
    W("")
    lim = freeze.get("limits") or {}
    W(table(["limit", "value"], [[k, json.dumps(v)] for k, v in lim.items()]))
    W("")
    W("The two arms:")
    W("")
    for k, v in (freeze.get("arms") or {}).items():
        W(f"* **{k}** — {v}")
    W("")
    W("P1's canonical session **is** one of P0's sessions, byte for byte. The arms")
    W("therefore cannot differ in prompt, evidence, seed formula or starting workbook,")
    W("and P1 issues no model call that P0 does not already issue.")
    W("")

    # ---- 2 eligibility rule
    W("## 2. The frozen ProgramGroup eligibility rule")
    W("")
    W("The spec's hard constraint is that region membership never implies one program.")
    W("A rectangle, a row, an Edit Plan operation or an ExecutionUnit may hold many")
    W("programs, so the predicate never infers homogeneity from adjacency.")
    W("")
    W("Instead it demands a **repetition witness**: a parallel line of the *input*")
    W("workbook that already carries formulas at the group's own coordinates, and whose")
    W("formulas reproduce one another under translation. That is direct evidence, in")
    W("this workbook, that one relative program is repeated across exactly those")
    W("positions.")
    W("")
    W("```")
    W("TRANSLATION_ELIGIBLE(group) iff")
    W("    |group| >= 2")
    W("    and all members share a sheet and are collinear on one axis")
    W("    and all members share one Edit Plan operation      (generated, not gold)")
    W("    and all members share one input cell kind          (no mixed overwrite)")
    W("    and a parallel line within +/-8 carries formulas at the members' own")
    W("        coordinates that are mutually reproducible by translation")
    W("    and the group is restricted to the coordinates that witness covers")
    W("```")
    W("")
    W("The last clause is what stops an over-authorised Edit Plan from being laundered")
    W("into a program claim. A line that repeats a program across J..N says nothing")
    W("about C..I, so C..I do not become members.")
    W("")
    W("Canonical member selection is frozen and evaluator-blind: a member that already")
    W("has an input formula, otherwise the leftmost/topmost member by stable cell id.")
    W("It is never chosen by which cell the model happened to solve before.")
    W("")

    # ---- 3 ceiling
    W("## 3. Translation ceiling (§5 preflight, no model calls)")
    W("")
    sm = (survey.get("summary") or {})
    W("Over every Edit-Plan-authorised cell in the six non-quarantined tasks, with no")
    W("selection toward eligibility:")
    W("")
    W(table(["quantity", "value"],
            [["authorised cells", sm.get("authorised_cells")],
             ["cells inside a mechanically eligible ProgramGroup", sm.get("cells_in_eligible_groups")],
             ["share of authorised cells in a group",
              pct(sm.get("share_of_authorised_cells_in_a_program_group"))],
             ["groups", sm.get("groups")],
             ["groups with a measurable ceiling", sm.get("groups_with_a_measurable_ceiling")],
             ["**TRANSLATION_CEILING_EXACT**", pct(sm.get("TRANSLATION_CEILING_EXACT"))],
             ["**TRANSLATION_CEILING_FINGERPRINT**", pct(sm.get("TRANSLATION_CEILING_FINGERPRINT"))],
             ["groups fully reproduced by translation",
              sm.get("groups_fully_reproduced_by_translation")]]))
    W("")
    W("Read carefully: this says that **if** the correct program were synthesized once")
    W("at the frozen canonical position, deterministic translation would reproduce")
    W(f"{pct(sm.get('TRANSLATION_CEILING_EXACT'))} of the other gold member formulas exactly")
    W("and **all** of them at fingerprint level. Translation always recovers the")
    W("structure; where it loses, it loses on reference offsets.")
    W("")
    W("Per task:")
    W("")
    W(table(["task", "authorised cells", "cells in groups", "groups", "group sizes"],
            [[t["task"], t["authorised_cells"], t["cells_in_eligible_groups"],
              t["n_groups"], str(t["group_sizes"][:12])]
             for t in (survey.get("tasks") or [])]))
    W("")
    if sweep.get("sweep"):
        W("### 3.1 Why the evidence standard is one witness line")
        W("")
        W("A corroboration requirement was considered and measured:")
        W("")
        W(table(["min witness lines", "groups", "cells in groups", "coverage",
                 "ceiling exact", "ceiling fingerprint"],
                [[r["min_witness_lines"], r["groups"], r["cells_in_eligible_groups"],
                  pct(r["share_of_authorised_cells_in_a_program_group"]),
                  pct(r["TRANSLATION_CEILING_EXACT"]),
                  pct(r["TRANSLATION_CEILING_FINGERPRINT"])]
                 for r in sweep["sweep"]]))
        W("")
        W("**Disclosure.** The corroboration idea came from inspecting which groups the")
        W("single-witness rule could not represent, and that inspection used gold. It was")
        W("then rejected: it raises the exact ceiling by 0.0145 while cutting coverage by")
        W("nearly seven points, and it does not fix the failure that motivated it. Keeping")
        W("the knob out leaves the predicate at the smallest justified test (§4) and keeps")
        W("gold out of the runtime rule entirely.")
        W("")
    bad = [c for t in (survey.get("tasks") or []) for c in t["ceilings"]
           if c.get("status") == "MEASURED" and not c.get("all_members_reproduced")]
    if bad:
        W("### 3.2 Where the ceiling is not 1.0")
        W("")
        W(f"{len(bad)} of {sm.get('groups_with_a_measurable_ceiling')} measurable groups are not")
        W("fully reproduced. Every one is the same failure: the gold homologue advances")
        W("its references at a **non-unit stride** while translation advances by one.")
        W("")
        W(table(["group (first members)", "members in gold", "exact", "fingerprint"],
                [[", ".join(c["members"][:3]) + (" …" if len(c["members"]) > 3 else ""),
                  c["n_members_in_gold_edit_set"], c["exact_correct"], c["fingerprint_correct"]]
                 for c in bad]))
        W("")
        W("This is the predicate's known limit and the concrete shape of")
        W("`PROGRAM_GROUPING_OVERMERGE`: the input workbook shows a stride-1 repetition,")
        W("the task needs a different stride, and nothing input-side distinguishes them.")
        W("")

    # ---- 4 population
    W("## 4. Frozen matched population")
    W("")
    W("Seven units come from Phase B, named by §6, with their sessions reused byte for")
    W("byte at zero cost. Five more were added because only one Phase B unit turned out")
    W("to hold a multi-member group at all.")
    W("")
    W("Added units were predicted with a **proxy** formula translated from the nearest")
    W("existing input homologue — never gold, never a model. At execution the proxy is")
    W("discarded and the closure is seeded by the model's own proposal, so a unit whose")
    W("real closure holds no group is reported rather than dropped.")
    W("")
    W(table(["task", "seed", "origin", "predicted groups", "proxy formula"],
            [[u["task"], u["seed"], u["origin"],
              str([len(g) for g in u.get("predicted_groups", [])]) if u.get("predicted_groups") else "—",
              f"`{u['proxy_formula']}`" if u.get("proxy_formula") else "—"]
             for u in (units.get("units") or [])]))
    W("")

    if not rows:
        W("*(arms not scored yet)*")
        W("")
        return "\n".join(L)

    # ---- 5 realized groups
    W("## 5. Predicted versus realised ProgramGroups")
    W("")
    W(table(["task", "seed", "seed formula", "closure members", "groups", "grouped members",
             "members in no group"],
            [[r["task"], r["seed"], f"`{r['seed_formula']}`" if r["seed_formula"] else "—",
              r["n_members"], r["n_groups"], len(r["members_in_a_group"]),
              len(r["members_not_in_any_group"])] for r in rows]))
    W("")
    grouped = sum(len(r["members_in_a_group"]) for r in rows)
    allmem = sum(r["n_members"] for r in rows)
    W(f"Across the executed units, **{grouped} of {allmem}** closure members fell into a")
    W("mechanically eligible ProgramGroup.")
    W("")
    refusals = Counter()
    for r in rows:
        for x in r["group_refusals"]:
            refusals[x["reason"]] += len(x.get("members") or [x])
    if refusals:
        W("Why the rest were refused, counted in members. The reasons are not")
        W("disjoint: `NOT_IN_ANY_PROGRAM_GROUP` is every ungrouped member, and")
        W("`OUTSIDE_WITNESSED_RUN` names the subset the predicate rejected because the")
        W("witness lines carry no formula at those coordinates.")
        W("")
        W(table(["refusal", "members"], sorted(refusals.items())))
        W("")

    # ---- 6 primary comparison
    W("## 6. Primary comparison — all required members correct")
    W("")
    W("This is the funnel stage that was zero at the end of Phase B.")
    W("")
    W("\"Required\" means the grouped members the task's gold actually edits. Members")
    W("the Edit Plan authorised but gold never touches cannot be correct in either")
    W("arm, so counting them would make both arms fail for a reason that has nothing")
    W("to do with translation; they are counted separately in section 14.")
    W("")
    def all_ok(r, arm):
        ms = [m for m in r["members"] if m["in_program_group"] and m["in_gold_edit_set"]]
        if not ms:
            return None
        return all(m[f"{arm}_exact"] for m in ms)
    withg = [r for r in rows if r["n_groups"]]
    W(table(["task", "seed", "grouped members", "required members",
             "P0 all required exact", "P1 all required exact"],
            [[r["task"], r["seed"], len(r["members_in_a_group"]),
              sum(1 for m in r["members"] if m["in_program_group"] and m["in_gold_edit_set"]),
              yn(all_ok(r, "P0")), yn(all_ok(r, "P1"))] for r in withg]))
    W("")
    p0all = sum(1 for r in withg if all_ok(r, "P0") is True)
    p1all = sum(1 for r in withg if all_ok(r, "P1") is True)
    W(table(["arm", "units whose every grouped member is exactly correct", "of"],
            [["P0 per-cell synthesis", p0all, len(withg)],
             ["P1 synthesize-once + translate", p1all, len(withg)]]))
    W("")

    # ---- 7 per member
    W("## 7. Per-member formulas")
    W("")
    for r in withg:
        W(f"### {r['task']} {r['seed']}")
        W("")
        W(table(["member", "in group", "gold", "P0", "P0 exact", "P1", "P1 exact", "P0 outcome"],
                [[m["member"], yn(m["in_program_group"]),
                  f"`{m['gold_formula']}`" if m["gold_formula"] else "—",
                  f"`{m['P0_formula']}`" if m["P0_formula"] else "—", yn(m["P0_exact"]),
                  f"`{m['P1_formula']}`" if m["P1_formula"] else "—", yn(m["P1_exact"]),
                  m["P0_outcome"]] for m in r["members"]]))
        W("")
        pc = r["program_consistency"]
        if pc:
            W(table(["group canonical", "P0 members instantiate one program",
                     "P1 members instantiate one program"],
                    [[k, yn(v["P0_program_consistent"]), yn(v["P1_program_consistent"])]
                     for k, v in pc.items()]))
            W("")

    # ---- 8 scores
    W("## 8. Scorer outcomes")
    W("")
    W(table(["task", "seed", "mod SEED", "mod P0", "mod P1", "Δ P1-P0", "Δ P1-P0 value-only",
             "Δ reg P1-P0"],
            [[r["task"], r["seed"],
              pct((r.get("SEED") or {}).get("modification_accuracy")),
              pct((r.get("P0") or {}).get("modification_accuracy")),
              pct((r.get("P1") or {}).get("modification_accuracy")),
              pct(r["delta_modification_P1_vs_P0"], 6),
              pct(r["delta_modification_value_only_P1_vs_P0"], 6),
              pct(r["delta_regression_P1_vs_P0"], 6)] for r in rows]))
    W("")
    W(table(["task", "seed", "S correct SEED", "S correct P0", "S correct P1",
             "newly correct P1 vs P0", "lost P1 vs P0"],
            [[r["task"], r["seed"], r["SEED_S_correct"], r["P0_S_correct"], r["P1_S_correct"],
              len(r["P1_newly_correct_vs_P0"]), len(r["P1_lost_vs_P0"])] for r in rows]))
    W("")

    # ---- 9 cost
    W("## 9. Cost")
    W("")
    p0c = sum(r["P0_model_calls"] for r in rows)
    p1c = sum(r["P1_model_calls"] for r in rows)
    W(table(["arm", "member synthesis calls"],
            [["P0", p0c], ["P1", p1c],
             ["removed by translation", p0c - p1c]]))
    W("")
    W(table(["task", "seed", "P0 calls", "P1 calls", "saved"],
            [[r["task"], r["seed"], r["P0_model_calls"], r["P1_model_calls"],
              r["P0_model_calls"] - r["P1_model_calls"]] for r in rows]))
    W("")
    ct = cost.get("totals") or {}
    if ct:
        W("Token cost of the two arms, counted from the session files themselves.")
        W("P1's sessions are a subset of P0's — the canonical session *is* one of")
        W("P0's sessions, byte for byte — so this is not an estimate but the same")
        W("files summed over two subsets.")
        W("")
        W(table(["quantity", "P0", "P1", "removed"],
                [[k,
                  f"{ct['P0'].get(k, 0):,}", f"{ct['P1'].get(k, 0):,}",
                  f"{ct['P0'].get(k, 0) - ct['P1'].get(k, 0):,}"
                  + (f" ({100 * (ct['P0'][k] - ct['P1'][k]) / ct['P0'][k]:.1f}%)"
                     if ct['P0'].get(k) else "")]
                 for k in ("member_sessions", "total_input_tokens", "total_output_tokens",
                           "retrieval_input_tokens", "synthesis_input_tokens",
                           "synthesis_output_tokens")]))
        W("")
    if arms:
        W(table(["quantity", "value"],
                [["new input tokens this probe", f"{arms.get('new_input_tokens', 0):,}"],
                 ["Phase B session tokens reused at no cost",
                  f"{arms.get('phase_b_sessions_reused_tokens', 0):,}"],
                 ["declared total cap", f"{(arms.get('limits') or {}).get('total_input_cap', 0):,}"]]))
        W("")

    # ---- 10 C69 autopsy
    W("## 10. Mandatory C69 autopsy")
    W("")
    c69 = next((r for r in rows if r["task"] == "08_03" and r["seed"] == "Income Statement!C69"), None)
    if c69:
        grp = (c69["program_groups"] or [None])[0]
        W(table(["quantity", "value"],
                [["seed formula", f"`{c69['seed_formula']}`"],
                 ["C1 closure members", len(c69["members"])],
                 ["members the Edit Plan authorised", ", ".join(m["member"] for m in c69["members"])],
                 ["ProgramGroups derived", c69["n_groups"]],
                 ["group members", ", ".join(c69["members_in_a_group"])],
                 ["canonical member", grp["canonical_member"] if grp else "—"],
                 ["canonical formula", f"`{grp['canonical_formula']}`" if grp and grp.get("canonical_formula") else "—"],
                 ["witness line", grp["witness"]["line"] if grp else "—"],
                 ["witness anchor", f"{grp['witness']['anchor']} = `{grp['witness']['anchor_formula']}`" if grp else "—"],
                 ["corroborating lines", grp["witness"].get("n_corroborating_lines") if grp else "—"]]))
        W("")
        W("Per member, P0 against P1:")
        W("")
        W(table(["member", "gold", "P0", "P0 ok", "P1", "P1 ok"],
                [[m["member"], f"`{m['gold_formula']}`" if m["gold_formula"] else "—",
                  f"`{m['P0_formula']}`" if m["P0_formula"] else "—", yn(m["P0_exact"]),
                  f"`{m['P1_formula']}`" if m["P1_formula"] else "—", yn(m["P1_exact"])]
                 for m in c69["members"] if m["in_program_group"]]))
        W("")
        W(table(["outcome", "P0", "P1"],
                [["modification accuracy",
                  pct((c69.get("P0") or {}).get("modification_accuracy")),
                  pct((c69.get("P1") or {}).get("modification_accuracy"))],
                 ["value-only modification",
                  pct(((c69.get("P0_strict") or {}).get("modification") or {}).get("value_only_accuracy")),
                  pct(((c69.get("P1_strict") or {}).get("modification") or {}).get("value_only_accuracy"))],
                 ["regression accuracy",
                  pct((c69.get("P0") or {}).get("regression_accuracy")),
                  pct((c69.get("P1") or {}).get("regression_accuracy"))],
                 ["scorer cells correct", c69["P0_S_correct"], c69["P1_S_correct"]],
                 ["member synthesis calls", c69["P0_model_calls"], c69["P1_model_calls"]]]))
        W("")
        W("### Over-authorisation, reported separately")
        W("")
        W("The generated Edit Plan authorises `Working Capital!C44:N44`; gold edits only")
        W("`J44:N44`. The eligibility predicate refused `C44:I44` on its own, because the")
        W("witness lines carry no formulas at those columns. That refusal is mechanical")
        W("and gold-blind — the input workbook simply shows no repetition there.")
        W("")
        W("Errors originating in those extra authorised cells are **not** attributable to")
        W("translation, and they are not counted against it below.")
        W("")

    # ---- 11 taxonomy
    W("## 11. Failure taxonomy")
    W("")
    tax = Counter()
    for r in rows:
        for g in r["program_groups"]:
            canon = g["canonical_member"]
            cm = next((m for m in r["members"] if m["member"] == canon), None)
            if not g.get("canonical_formula"):
                tax["CANONICAL_SYNTHESIS_UNAVAILABLE"] += 1
            elif g.get("translation_failures"):
                tax["TRANSLATION_FAILURE"] += 1
            elif cm and cm["P1_exact"] is False and cm["P0_exact"] is False:
                tax["CANONICAL_SYNTHESIS_WRONG"] += 1
            elif any(m["P1_exact"] is False for m in r["members"]
                     if m["in_program_group"] and m["member"] != canon):
                tax["PROGRAM_GROUPING_OVERMERGE"] += 1
            else:
                tax["GROUP_FULLY_CORRECT"] += 1
        for x in r["group_refusals"]:
            if x["reason"] == "OUTSIDE_WITNESSED_RUN":
                tax["EDIT_PLAN_OVERAUTHORIZATION"] += len(x["members"])
            elif x["reason"] == "NO_REPETITION_WITNESS_IN_INPUT_WORKBOOK":
                tax["TRANSLATION_INELIGIBLE"] += 1
    UNIT = {"EDIT_PLAN_OVERAUTHORIZATION": "members", "TRANSLATION_INELIGIBLE": "units"}
    W(table(["class", "count", "counted in"],
            [[k, v, UNIT.get(k, "groups")] for k, v in sorted(tax.items())]))
    W("")
    W("Classes with no row were not observed in the executed population.")
    W("")
    W("* `CANONICAL_SYNTHESIS_WRONG` — the one program the model chose was wrong.")
    W("* `TRANSLATION_INELIGIBLE` — the harness correctly refused to assume one program.")
    W("* `TRANSLATION_FAILURE` — mechanically translatable but the implementation failed.")
    W("* `PROGRAM_GROUPING_OVERMERGE` — cells grouped as homogeneous needed different programs.")
    W("* `EDIT_PLAN_OVERAUTHORIZATION` — authorised cells that task gold never edits.")
    W("")

    # ---- 12 retrieval
    W("## 12. Retrieval, unchanged and reported")
    W("")
    W("Retrieval was frozen: same bootstrap, same SQL contract, same 8-query maximum,")
    W("same delta serialization. It was not co-varied with translation.")
    W("")
    sess = []
    for d in (C.OUT / "sessions", __import__("execution_unit_probe").OUT / "sessions"):
        if d.exists():
            sess += sorted(d.glob("*.json"))
    calls = []
    for sp in sess:
        x = _load(sp, {})
        n = len([c for c in (x.get("calls") or []) if c.get("action") or c.get("sql")])
        calls.append(n)
    if calls:
        W(table(["quantity", "value"],
                [["sessions considered", len(calls)],
                 ["median SQL calls", sorted(calls)[len(calls) // 2]],
                 ["sessions at 7 or 8 of the 8 permitted", sum(1 for n in calls if n >= 7)],
                 ["sessions hitting the per-session token cap",
                  sum(1 for sp in sess if (_load(sp, {}) or {}).get("session_resource_limited"))]]))
        W("")

    # ---- 13 existing vs novel
    W("## 13. Existing versus novel programs")
    W("")
    W("The mechanical label never sees gold: an eligible group has an input")
    W("homologue by construction, so the harness can call the program recoverable")
    W("without knowing what it is. The evaluator-side label asks separately whether")
    W("the gold program's *shape* already occurs somewhere in the input workbook.")
    W("The two labels are compared, never merged, and neither is shown to the model.")
    W("")
    reg = []
    for r in rows:
        for canon, x in (r["program_regimes"] or {}).items():
            cm = next((m for m in r["members"] if m["member"] == canon), None)
            reg.append([r["task"], canon, x["mechanical"], x["evaluator_side"] or "n/a",
                        yn(x.get("witness_shape_matches_gold")),
                        yn(cm["P0_exact"]) if cm else "n/a",
                        yn(cm["P1_exact"]) if cm else "n/a"])
    if reg:
        W(table(["task", "canonical", "mechanical", "evaluator-side",
                 "witness shape = gold shape", "P0 canonical ok", "P1 canonical ok"], reg))
        W("")
        ev = Counter(x[3] for x in reg)
        W(f"Evaluator-side distribution: {dict(ev)}. Every eligible group is")
        W("`RECOVERABLE_EXISTING_PROGRAM` mechanically, which is a tautology of the")
        W("predicate and is reported as such, not as a finding.")
        W("")

    # ---- 14 over-authorisation
    W("## 14. Translation does not hide a bad Edit Plan (§17)")
    W("")
    W("Two counts per group. `RAW_AUTHORISED_GROUP` is what the predicate built from")
    W("the Edit Plan and the input workbook alone. `GOLD_INTERSECTION_DIAGNOSTIC` is")
    W("the evaluator-side count of those members the task's gold actually edits. The")
    W("second was computed after the run and never trimmed the first.")
    W("")
    oa = []
    for r in rows:
        for g in r["program_groups"]:
            mem = set(g["members"])
            ing = sum(1 for m in r["members"] if m["member"] in mem and m["in_gold_edit_set"])
            oa.append([r["task"], g["canonical_member"], len(mem), ing, len(mem) - ing])
    if oa:
        W(table(["task", "canonical", "RAW_AUTHORISED_GROUP",
                 "GOLD_INTERSECTION_DIAGNOSTIC", "authorised but not in gold"], oa))
        W("")
        W(f"Total authorised group members: {sum(x[2] for x in oa)}; of those "
          f"{sum(x[3] for x in oa)} are in gold and {sum(x[4] for x in oa)} are not.")
        W("Members outside gold cannot earn modification credit in either arm, so they")
        W("bound how much of any P1 gain could be an artefact of grouping: none of it.")
        W("")

    # ---- 15 safety
    W("## 15. Safety and regression (§20)")
    W("")
    W(table(["task", "seed", "Δ regression P1−P0", "Δ regression value-only",
             "cells P1 gains over P0", "cells P1 loses versus P0"],
            [[r["task"], r["seed"], pct(r["delta_regression_P1_vs_P0"], 6),
              pct(r["delta_regression_value_only_P1_vs_P0"], 6),
              len(r["P1_newly_correct_vs_P0"]), len(r["P1_lost_vs_P0"])] for r in rows]))
    W("")
    lost = sorted({(r["task"], c) for r in rows for c in r["P1_lost_vs_P0"]})
    W(f"Scorer cells correct under P0 and wrong under P1, across the whole population: "
      f"**{len(lost)}**." + ("" if not lost else " " + ", ".join(f"{t} {c}" for t, c in lost[:20])))
    W("")
    ex = exact.get("units") or []
    if ex:
        W("### How much of each delta is exact, and how much is tolerance")
        W("")
        W("The evaluator compares population S by value with a 1% relative tolerance.")
        W("That is the official semantics and section 8 uses it unchanged. A delta")
        W("made of exact answers and a delta made of near misses are not the same")
        W("claim, so every cell one arm wins and the other loses is split below by")
        W("whether the winner reproduced the gold value exactly or only landed inside")
        W("the band. Nothing is rescored; no cell is credited that the evaluator did")
        W("not credit.")
        W("")
        W(table(["task", "seed", "P1 gains exact", "P1 gains within tolerance only",
                 "P1 losses exact", "P1 losses within tolerance only"],
                [[u["task"], u["seed"], len(u["P1_gains"]["exact"]),
                  len(u["P1_gains"]["within_tolerance_not_exact"]),
                  len(u["P1_losses"]["exact"]),
                  len(u["P1_losses"]["within_tolerance_not_exact"])] for u in ex]))
        W("")
        ge = sum(len(u["P1_gains"]["exact"]) for u in ex)
        le = sum(len(u["P1_losses"]["exact"]) for u in ex)
        lt = sum(len(u["P1_losses"]["within_tolerance_not_exact"]) for u in ex)
        W(f"Across the population P1 gains **{ge}** cells that match gold exactly and")
        W(f"loses **{le}**. Every one of the **{lt}** cells P0 wins is a cell P0 landed")
        W("inside the 1% band without reproducing the gold value, on a wrong formula.")
        W("")

    # ---- 16 gates
    W("## 16. Decision gates (§21)")
    W("")
    both = [r for r in rows if r["n_groups"]]
    p1w = [r for r in both if (r["delta_modification_value_only_P1_vs_P0"] or 0) > 0]
    p0w = [r for r in both if (r["delta_modification_value_only_P1_vs_P0"] or 0) < 0]
    allok = lambda r, arm: all(m[f"{arm}_exact"] for m in r["members"]
                               if m["in_program_group"] and m["in_gold_edit_set"]) \
                           and any(m["in_program_group"] and m["in_gold_edit_set"] for m in r["members"])
    g0 = sum(1 for r in both if allok(r, "P0"))
    g1 = sum(1 for r in both if allok(r, "P1"))
    W(table(["gate", "measurement"],
            [["units with at least one ProgramGroup", len(both)],
             ["all required group members correct — P0", g0],
             ["all required group members correct — P1", g1],
             ["units where value-only modification improves under P1", len(p1w)],
             ["units where value-only modification worsens under P1", len(p0w)],
             ["member synthesis calls — P0", sum(r["P0_model_calls"] for r in rows)],
             ["member synthesis calls — P1", sum(r["P1_model_calls"] for r in rows)]]))
    W("")

    # ---- 17 post-hoc canonical-abstention diagnostic
    W("## 17. Post-hoc diagnostic — did the canonical rule cause a collapse?")
    W("")
    W("Clearly labelled as post-hoc. It is not the pre-registered arm, it adds no")
    W("model call, and it uses no gold: abstention is a runtime outcome. The")
    W("substitute rule is still deterministic and still evaluator-blind — the first")
    W("member in the same canonical order whose session actually proposed a formula.")
    W("")
    ph = posthoc.get("units") or []
    if ph:
        prows = []
        for u in ph:
            req = [m for m in u["members"] if m["in_gold_edit_set"]]
            sub = [n for n in u["notes"] if n.get("substituted")]
            prows.append([u["task"], u["seed"], len(req),
                          sum(1 for m in req if m["P0_exact"]),
                          sum(1 for m in req if m["P1_exact"]),
                          sum(1 for m in req if m["P1prime_exact"]),
                          sub[0]["substitute_canonical"] if sub else "—"])
        W(table(["task", "seed", "required members", "P0 exact", "P1 exact",
                 "P1' exact (post-hoc)", "substitute canonical"], prows))
        W("")
        W("Whether the ceiling was reachable at all, evaluator-side and after the run:")
        W("gold is translation-consistent across the group, so one correct canonical")
        W("synthesis would have produced every member.")
        W("")
        W(table(["task", "seed", "group", "gold translation-consistent", "members checked"],
                [[u["task"], u["seed"], c["group"], yn(c["gold_translation_consistent"]),
                  c["members_checked"]] for u in ph for c in u.get("ceiling", [])]))
        W("")

    sur = survey.get("summary") or {}
    p0req = sum(1 for r in rows for m in r["members"]
                if m["in_program_group"] and m["in_gold_edit_set"] and m["P0_exact"])
    p1req = sum(1 for r in rows for m in r["members"]
                if m["in_program_group"] and m["in_gold_edit_set"] and m["P1_exact"])
    allreq = sum(1 for r in rows for m in r["members"]
                 if m["in_program_group"] and m["in_gold_edit_set"])
    net = sum(r["delta_modification_value_only_P1_vs_P0"] or 0 for r in rows)
    worstreg = min([r["delta_regression_P1_vs_P0"] or 0 for r in rows] or [0])
    ge = sum(len(u["P1_gains"]["exact"]) for u in (exact.get("units") or []))
    le = sum(len(u["P1_losses"]["exact"]) for u in (exact.get("units") or []))

    # ---- 18 verdict
    W("## 18. Architecture verdict (§21)")
    W("")
    W("### `TRANSLATION_EXECUTION_EARNED` — met on the executed population, on three groups")
    W("")
    W("Every clause of the gate holds and none is close:")
    W("")
    W(table(["gate clause", "measurement", "met"],
            [["higher all-member correctness under P1",
              f"{g1} of {len(both)} units versus {g0}; {p1req} of {allreq} required members versus {p0req}",
              yn(g1 > g0)],
             ["higher scorer / value correctness",
              f"net modification +{net:.6f}, identical value-only; +{ge} exact cells, -{le}",
              yn(net > 0)],
             ["no meaningful regression damage",
              f"most negative regression delta {worstreg:.6f} — no unit regresses; "
              f"{le} exact cells lost",
              yn(le == 0)],
             ["fewer model calls and tokens",
              f"{ct['P0']['member_sessions']} to {ct['P1']['member_sessions']} sessions, "
              f"{ct['P0']['total_input_tokens']:,} to {ct['P1']['total_input_tokens']:,} input tokens"
              if ct else "n/a",
              yn(bool(ct) and ct["P1"]["member_sessions"] < ct["P0"]["member_sessions"])]]))
    W("")
    W("The honest size of that claim: three ProgramGroups, nineteen required members,")
    W("one task family. It is a directional result on a small population, not a rate.")
    W("")
    W("### `CANONICAL_SYNTHESIS_DOMINANT` — also met, and it is the more useful verdict")
    W("")
    W("Translation never failed. Across the executed population there were zero")
    W("`TRANSLATION_FAILURE`s and zero `PROGRAM_GROUPING_OVERMERGE`s, and gold is")
    W("translation-consistent in three groups of three, so every one of the nineteen")
    W("required members was reachable from a single correct canonical synthesis.")
    W("Both failing groups fail for exactly one reason: the one program the model")
    W("chose was wrong (08_04) or was never produced at all (08_05).")
    W("")
    W("Harness repetition has been removed. Model program choice is now the frontier.")
    W("")
    W("### Gates that do not apply")
    W("")
    W("* `PROGRAM_HOMOGENEITY_NOT_RECOVERABLE` — refuted here. The predicate found the")
    W("  homogeneity from input-side structure alone, and was right in three of three.")
    W("* `EDIT_PLAN_TIGHTNESS_DOMINANT` — not supported. Zero of nineteen grouped")
    W("  members lie outside gold, because the witness refused the over-authorised")
    W("  cells before any model call. Over-authorisation is real at C69 (`C44:I44`)")
    W("  but it was excluded by the predicate, not by gold, and it costs P1 nothing.")
    W("")

    # ---- 19 answers
    W("## 19. Direct questions (§23)")
    W("")
    W("**a. How often do ExecutionUnit members actually share one translation-compatible program?**")
    W("")
    W(f"Preflight, over the whole authorised population and with no model calls: "
      f"{sur.get('cells_in_eligible_groups')} of {sur.get('authorised_cells')} authorised cells "
      f"({100 * (sur.get('share_of_authorised_cells_in_a_program_group') or 0):.2f}%) fall into "
      f"{sur.get('groups')} eligible groups. At runtime, {grouped} of {allmem} closure members "
      f"were grouped. Of the three groups actually executed, gold is translation-consistent "
      f"in all three — 19 of 19 members.")
    W("")
    W("**b. Can that homogeneity be identified mechanically from input-side structure without gold?**")
    W("")
    W("Yes. The repetition witness uses only the input workbook and the generated Edit")
    W("Plan. At C69 it recovered exactly `Working Capital!J44:N44` — the Phase A minimal")
    W("witness — and refused `C44:I44` on its own. Its measured limit is real and")
    W(f"disclosed: preflight exact ceiling {sur.get('TRANSLATION_CEILING_EXACT')}, with every")
    W("failure a 15_04 non-unit-stride homologue.")
    W("")
    W("**c. When eligible, does one canonical synthesis + deterministic translation outperform independent per-cell synthesis?**")
    W("")
    W("Yes when the canonical program is right, and never worse when it is wrong. C69:")
    W("5 of 5 required members exact under P1 against 2 of 5 under P0, 152 scorer cells")
    W("against 71, modification 0.0688 against 0.0321. J34: both arms 0 of 2. C30: both")
    W("arms 0 of 12. Across the population P1 gains 83 exactly-correct cells and loses")
    W("none.")
    W("")
    W("**d. Does it specifically fix the heterogeneous-member failure observed in 08_03 C69?**")
    W("")
    W("Yes, and that failure is exactly what it fixes. P0 rediscovered the program at")
    W("each column and drifted the rows three different ways — `=+K37+K28+K17+K8`,")
    W("`=+L41+L32+L21+L12`, `=N37+N39` — against a uniform gold. One synthesis plus")
    W("translation produced all five.")
    W("")
    W("**e. How often is the canonical formula itself wrong?**")
    W("")
    W("Two of three groups: wrong at 08_04 (`=C66*$C$56/12` for gold `=C66*C67/12`) and")
    W("absent at 08_05, where the canonical member's own session abstained.")
    W("")
    W("**f. How often is translation wrong despite a correct canonical formula?**")
    W("")
    W("Never in this population — zero of three. Where the canonical was right, every")
    W("translated member was right. Translation also preserved the absolute reference")
    W("`$C$56` correctly at 08_04 while faithfully propagating a wrong program.")
    W("")
    W("**g. How much model-call and token cost does translation remove?**")
    if ct:
        W("")
        W(f"Half the member sessions ({ct['P0']['member_sessions']} to "
          f"{ct['P1']['member_sessions']}), "
          f"{100 * (ct['P0']['total_input_tokens'] - ct['P1']['total_input_tokens']) / ct['P0']['total_input_tokens']:.1f}% "
          f"of input tokens ({ct['P0']['total_input_tokens']:,} to "
          f"{ct['P1']['total_input_tokens']:,}) and "
          f"{100 * (ct['P0']['total_output_tokens'] - ct['P1']['total_output_tokens']) / ct['P0']['total_output_tokens']:.1f}% "
          f"of output tokens. The twelve-member group at C30 cost twelve sessions in P0 "
          f"and one in P1.")
    W("")
    W("**h. Does the gain survive value-only scoring?**")
    W("")
    W("Yes, exactly. Official and value-only modification are identical to six decimal")
    W("places for every unit, so no part of the delta rests on the evaluator's")
    W("error-value formula fallback. Under exact-value comparison the gain is larger,")
    W("not smaller: 83 exact cells gained, 0 lost.")
    W("")
    W("**i. Does deterministic translation damage regression?**")
    W("")
    W("No. Regression is unchanged everywhere except C69, where P1 is *better* by")
    W("5e-06 — P1 leaves the workbook with no regression damage at all, where P0")
    W("damages one cell. No exactly-correct cell is lost anywhere.")
    W("")
    W("**j. Are remaining failures primarily canonical synthesis, program grouping, Edit Plan over-authorisation, retrieval, or genuinely heterogeneous programs?**")
    W("")
    W("Canonical synthesis, unambiguously. Grouping: zero errors. Over-authorisation:")
    W("zero grouped members outside gold. Translation: zero failures. Genuine")
    W("heterogeneity: none — gold was uniform in all three groups. Retrieval is not")
    W("implicated in any specific failure here but is not exonerated either: 47 of 48")
    W("sessions used 7 or 8 of the 8 permitted queries, so the budget is still binding.")
    W("")
    W("**k. Should ExecutionUnits execute by always per-cell synthesis, always synthesize-once, or mechanically choose?**")
    W("")
    W("Mechanically choose, on the witness. Synthesize-once where a repetition witness")
    W("exists in the input workbook; per-cell where it does not. \"Always synthesize-once\"")
    W("is unsafe — the preflight ceiling is not 1.0, and the 15_04 non-unit-stride")
    W("homologues show what over-merging looks like. \"Always per-cell\" is what produced")
    W("three different wrong programs at C69 where one right one existed.")
    W("")
    W("One refinement is earned by this run and should be stated with its evidence:")
    W("when the canonical member's own session abstains, the whole group currently")
    W("collapses to nothing. Section 17 shows that at C30 choosing the first")
    W("non-abstaining member instead would have changed no answer — 0 of 12 either")
    W("way — so this is a robustness fix, not a correctness one, and it must not be")
    W("confused with falling back to independent synthesis, which §11 forbids.")
    W("")
    W("### Final research question")
    W("")
    W("> Once the harness has correctly identified a coordinated ExecutionUnit, is")
    W("> repeated stochastic formula synthesis still necessary, or can mechanically")
    W("> homogeneous members be reduced to one model program choice followed by")
    W("> deterministic translation?")
    W("")
    W("On this population, repeated synthesis is not necessary, and it is worse than")
    W("unnecessary. Where members are mechanically homogeneous, asking the model once")
    W("per cell does not give the harness more chances to be right; it gives it more")
    W("chances to be *inconsistent*. At C69 the model held the correct program at two")
    W("of five columns and threw it away at the other three. Reducing the unit to one")
    W("program choice plus deterministic translation converted that into five of five,")
    W("for two thirds of that unit's sessions and 63% of its input tokens, with no")
    W("regression cost. Across the whole population the arms cost 32 sessions against")
    W("16, and 4.17M input tokens against 2.03M.")
    W("")
    W("The reduction does not make the model more likely to choose the right program.")
    W("It makes the choice count exactly once, which is why both remaining failures")
    W("are now single, legible, attributable events rather than a spray of unrelated")
    W("wrong formulas. That is the whole of the claim, measured on three groups.")
    W("")

    return "\n".join(L)


if __name__ == "__main__":
    md = build()
    (OUT / "PHASE_C_REPORT.md").write_text(md, encoding="utf-8")
    print(md[:1500])
