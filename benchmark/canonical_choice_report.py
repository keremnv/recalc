#!/usr/bin/env python3
"""Assemble the canonical-program-choice report from the frozen run artifacts."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonical_choice_probe as CP
import canonical_choice_select as sel
import end_to_end_composition_probe as old
import program_candidate as pcand

OUT = sel.OUT


def _load(p, default=None):
    try:
        return old.load(p)
    except Exception:
        return default


def table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def yn(x):
    return "n/a" if x is None else ("yes" if x else "**no**")


def f6(x):
    return "n/a" if x is None else f"{x:.6f}"


def build() -> str:
    pre = _load(OUT / "candidate_preflight.json", {})
    aut = _load(OUT / "availability_autopsy.json", {"autopsies": []})
    units = _load(OUT / "units.json", {})
    freeze = _load(OUT / "freeze.json", {})
    fsc = _load(OUT / "formula_scores.json", {"units": []})
    wsc = _load(OUT / "workbook_scores.json", {"units": []})
    rep = _load(OUT / "choices_reparsed.json", {"rows": []})
    rows = fsc.get("units") or []
    wrows = {(r["task"], r["canonical_member"]): r for r in (wsc.get("units") or [])}

    L = []
    W = L.append
    W("# Canonical program choice — report")
    W("")
    W("One question, and the architecture before it is frozen:")
    W("")
    W("> When a ProgramGroup must run one program, should the model compose it")
    W("> freely, or choose it from the programs the workbook already contains?")
    W("")
    W("Phase C removed the harness's repeated asking and left exactly one")
    W("stochastic decision per group. This probe changes only that decision's")
    W("interface, and separates two things the previous phase could not tell")
    W("apart: recovering a program that exists, and synthesizing one that does not.")
    W("")
    W(table(["#", "deliverable", "section"],
            [["1", "ProgramCandidate definition", "2"],
             ["2", "M0-M3 candidate preflight", "3"],
             ["3", "exact / fingerprint recall curves", "3"],
             ["4", "candidate-set size distributions", "3"],
             ["5", "program-availability taxonomy", "4"],
             ["6", "08_04 and 08_05 availability autopsies", "5"],
             ["7", "frozen runtime candidate mechanism", "6"],
             ["8", "frozen Phase B population", "7"],
             ["9", "reused A0 canonical outputs", "8"],
             ["10", "A1 candidate-choice outputs", "8"],
             ["11", "canonical correctness by availability class", "9"],
             ["12", "all-member correctness after translation", "10"],
             ["13", "candidate ambiguity analysis", "11"],
             ["14", "recovery-vs-novel analysis", "12"],
             ["15", "failure taxonomy", "13"],
             ["16", "scorer / value-only / regression", "14"],
             ["17", "token and cost comparison", "15"],
             ["18", "oracle-choice ceiling", "17"],
             ["19", "architecture verdict", "19"],
             ["—", "retrieval usage (§24)", "16"],
             ["—", "instrumentation defects", "18"],
             ["—", "direct questions a-l (§29)", "20"]]))
    W("")

    # 1 frozen
    W("## 1. What is frozen")
    W("")
    W(table(["component", "sha256 (first 12)"],
            [[k, v[:12]] for k, v in (freeze.get("sha256") or {}).items()]))
    W("")
    lim = freeze.get("limits") or {}
    W(table(["limit", "value"], [[k, json.dumps(v) if isinstance(v, dict) else v]
                                 for k, v in lim.items()]))
    W("")
    W("Nothing before canonical program choice is under test. The retrieval claim")
    W("is stronger than \"unchanged\": A1 never queries. It rebuilds A0's synthesis")
    W("input from A0's own stored working set and appends the candidate list, so")
    W("both arms stand on literally the same eight queries.")
    W("")

    # 2 candidate definition
    W("## 2. ProgramCandidate")
    W("")
    W("A candidate is never invented. It is a formula the input workbook already")
    W("contains, rewritten by the existing translation so that it reads correctly")
    W("at the group's canonical cell.")
    W("")
    W("```")
    W("ProgramCandidate {")
    W("    candidate_id                     frozen, assigned from formula-text order")
    W("    source_cell_id                   where the program already exists")
    W("    source_formula_id                its text at that cell")
    W("    source_fingerprint               its relative program identity")
    W("    source_relation                  why the mechanism retrieved it")
    W("    translated_formula_at_canonical  what it becomes at the target")
    W("    provenance                       every source that produced this text")
    W("}")
    W("```")
    W("")
    W("Identical translated formulas collapse to one candidate and keep every")
    W("provenance. Ordering is by formula text, so the list carries no signal")
    W("about which candidate is better, and the model is shown no correctness, no")
    W("rank and no recommendation. A selected candidate is substituted verbatim;")
    W("the model cannot edit it. That is what makes SELECT closed-world rather")
    W("than advisory.")
    W("")
    W("The four generation mechanisms, in increasing breadth:")
    W("")
    W(table(["mechanism", "rule"],
            [["M0", "the repetition-witness line(s) that established the ProgramGroup"],
             ["M1", "every parallel line covering the group's coordinates, consistently"],
             ["M2", "same-sheet runs on the group's axis, including the group's own line"],
             ["M3", "every workbook formula that can legally translate to the canonical cell"]]))
    W("")

    # 3 preflight
    W("## 3. Candidate preflight (§7), no model calls")
    W("")
    W(f"Population: **{pre.get('groups')}** mechanically eligible ProgramGroups across the six")
    W(f"non-quarantined tasks, of which **{pre.get('groups_scored')}** have a canonical member the task's")
    W("gold actually edits and can therefore be scored.")
    W("")
    W(table(["mechanism", "exact recall", "fingerprint recall", "mean", "median", "p95", "max"],
            [[c["mechanism"], f6(c["exact_candidate_recall"]),
              f6(c["fingerprint_candidate_recall"]), c["candidates_mean"],
              c["candidates_median"], c["candidates_p95"], c["candidates_max"]]
             for c in (pre.get("recall_curve") or [])]))
    W("")
    W("Read the curve as cumulative gain: M0 alone finds the correct program for")
    W("one group in eight with a single candidate; adding parallel lines triples")
    W("fingerprint recall without moving exact recall at all; adding same-sheet")
    W("runs is what finally moves exact recall; and the whole-workbook ceiling")
    W("adds half again as much for fifteen times the candidates.")
    W("")

    # 4 taxonomy
    W("## 4. Program-availability taxonomy (§8)")
    W("")
    W(table(["class", "groups"], sorted((pre.get("availability_scored") or {}).items())))
    W("")
    W("`EXISTING_ELSEWHERE_NOT_TRANSLATABLE` is not in the specified list and was")
    W("added because the specified list cannot express what the data contains. M3")
    W("asks whether a program can *legally translate* to the canonical cell, which")
    W("silently merges \"this program is not in the workbook\" with \"it is here, but")
    W("its references would leave the grid from that position\". The class, and a")
    W("count of how often the gold fingerprint occurs anywhere in the workbook,")
    W("keep those apart.")
    W("")

    # 5 autopsies
    W("## 5. The two Phase C canonical failures (§10)")
    W("")
    for a in aut.get("autopsies", []):
        W(f"### {a['task']} {a['canonical_member']} — `{a['availability_class']}`")
        W("")
        W(f"Gold: `{a['gold_canonical_formula']}` (relative program `{a['gold_fingerprint']}`)")
        W("")
        W(table(["mechanism", "candidates", "contains gold exactly", "contains gold's shape"],
                [[m, d["n_candidates"], yn(d["gold_exact"]), yn(d["gold_fingerprint"])]
                 for m, d in a["by_mechanism"].items()]))
        W("")
    W("For 08_04 `Working Capital!C68` and 08_05 `Working Capital!C66` the answer is")
    W("the same and it is unambiguous: **nowhere**. Not in the runtime set, not in")
    W("the whole-workbook ceiling, and the gold fingerprints `=<REF>*<REF>/12` and")
    W("`=<REF>*<REF>+<REF>*<REF>` occur **zero** times among the 118,288 and 118,177")
    W("formulas of those workbooks. Both Phase C failures are genuine synthesis")
    W("failures. No candidate interface could have rescued either.")
    W("")

    # 6 frozen mechanism
    W("## 6. Frozen runtime mechanism (§9)")
    W("")
    W(f"**{pre.get('runtime_mechanism')}**, chosen on the aggregate preflight rather than on any")
    W("group it happens to rescue. It captures 7 of the 10 groups whose correct")
    W("program is reachable at all — 70% of the ceiling's exact recall — for 31")
    W("candidates on average against M3's 471. The three it still misses are")
    W("cross-sheet; a same-sheet rule that reached them would simply be M3.")
    W("")
    W("Disclosure. The first implementation of M2 scored 0.118 exact recall, and")
    W("two defects were found by inspecting which sources M3 reached and the")
    W("runtime set missed. That inspection read gold. §9 sanctions freezing the")
    W("rule on gold-scored aggregates, but the path is worth stating plainly. The")
    W("defects were structural, and the fixes are gold-blind: M2 skipped the")
    W("group's own line, where a row already holding the program at other columns")
    W("is the most homologous evidence available; and it required an entire")
    W("contiguous run to be translation-consistent, so a line carrying two")
    W("programs side by side contributed nothing instead of its regular part.")
    W("")

    # 7 population
    W("## 7. Frozen Phase B population (§11)")
    W("")
    W(table(["availability class", "groups"],
            sorted((units.get("by_availability_class") or {}).items())))
    W("")
    W(table(["task", "canonical", "class", "members", "group from", "candidates"],
            [[u["task"], u["canonical_member"], u["availability_class"], u["n_members"],
              u["execution_group_source"], u["n_candidates"]]
             for u in (units.get("units") or [])]))
    W("")
    W("Stratified by an evaluator-side label, as §11 requires. That makes every")
    W("number below a diagnostic contrast and none of them a benchmark rate.")
    W("Where Phase C executed a group, that group's member set is the one executed")
    W("here, so the end-to-end figures tie back to the Phase C funnel rather than")
    W("to a much wider authorised row the earlier probe never actuated.")
    W("")

    # 8 arm outputs
    W("## 8. What each arm produced (§§9, 10 deliverables)")
    W("")
    W(table(["task", "canonical", "class", "K", "A0 outcome", "A0 formula",
             "A1 outcome", "A1 pick", "A1 formula"],
            [[r["task"], r["canonical_member"], r["availability_class"], r["n_candidates"],
              r["A0_outcome"], f"`{r['A0_formula']}`" if r["A0_formula"] else "—",
              r["A1_outcome"], r["A1_candidate_id"] or "—",
              f"`{r['A1_formula']}`" if r["A1_formula"] else "—"] for r in rows]))
    W("")
    reused = [r for r in rows if r["A0_session_reused_from"]]
    W(f"A0 canonical sessions reused from earlier probes at no cost: **{len(reused)}** of {len(rows)}"
      + (" — " + ", ".join(f"{r['task']} {r['canonical_member']}" for r in reused) if reused else ""))
    W("")

    # 9 canonical correctness
    W("## 9. Canonical correctness by availability class (§17)")
    W("")
    cc_ = fsc.get("canonical_correctness") or {}
    W(table(["availability class", "groups", "A0 canonical exact", "A1 canonical exact",
             "A1 outcomes"],
            [[k, v["groups"], v["A0_canonical_exact"], v["A1_canonical_exact"],
              ", ".join(f"{a} {n}" for a, n in sorted(v["A1_outcomes"].items()))]
             for k, v in sorted(cc_.items())]))
    W("")
    a0 = sum(1 for r in rows if r["A0_canonical_exact"])
    a1 = sum(1 for r in rows if r["A1_canonical_exact"])
    W(f"Overall: A0 **{a0} of {len(rows)}**, A1 **{a1} of {len(rows)}**.")
    W("")
    W("The primary question of the probe is the first row. When the exact correct")
    W("program was already in the candidate set, A1 selected it in 5 of 7 groups —")
    W("and A0 composed that same program from scratch in exactly the same 5,")
    W("abstaining on exactly the same 2. Candidate-first exposure changed no")
    W("answer, in either direction, anywhere in the population.")
    W("")

    # 10 all-member
    W("## 10. All-member correctness after translation (§22)")
    W("")
    W(table(["task", "canonical", "required members", "A0 exact", "A1 exact",
             "A0 all", "A1 all"],
            [[r["task"], r["canonical_member"], r["A0_members_required"],
              r["A0_members_exact"], r["A1_members_exact"],
              yn(r["A0_all_members_exact"]), yn(r["A1_all_members_exact"])] for r in rows]))
    W("")
    W("Translation continues to behave exactly as Phase C measured: wherever the")
    W("canonical choice is right, every required member is right.")
    W("")

    # 11 ambiguity
    W("## 11. Candidate ambiguity (§19)")
    W("")
    W(table(["candidate-set size", "groups", "with an exact candidate",
             "A1 selected it", "A0 composed it"],
            [[k, v["groups"], v["groups_with_an_exact_candidate"],
              v["A1_selected_it"], v["A0_composed_it"]]
             for k, v in (fsc.get("ambiguity") or {}).items()]))
    W("")
    W("Selection accuracy does fall as the set grows — 4 of 4 at twenty candidates")
    W("or fewer, 1 of 3 above. But A0's column is identical in every bucket, and")
    W("A0 never saw a candidate list. The degradation therefore tracks how hard")
    W("the group is, not how long the list is, and this population cannot support")
    W("a claim that ambiguity is what defeats selection.")
    W("")

    # 12 recovery vs novel
    W("## 12. Recovery against novelty (§§20, 21)")
    W("")
    rec = [r for r in rows if r["availability_class"] == "RECOVERABLE_EXACT"]
    nov = [r for r in rows if r["availability_class"] == "GENUINELY_NOVEL"]
    W("**Recovery test** — could the model have solved these without inventing a formula?")
    W("")
    W(table(["outcome", "groups"],
            [["correct SELECT", sum(1 for r in rec if r["A1_outcome"] == "SELECTED_EXISTING"
                                    and r["A1_canonical_exact"])],
             ["wrong SELECT", sum(1 for r in rec if r["A1_outcome"] == "SELECTED_EXISTING"
                                  and not r["A1_canonical_exact"])],
             ["unnecessary COMPOSE_NEW", sum(1 for r in rec if r["A1_outcome"] == "COMPOSED_NEW")],
             ["abstention", sum(1 for r in rec if r["A1_outcome"] == "ABSTAIN")]]))
    W("")
    W("**Novel-synthesis test** — candidate selection cannot help here by construction.")
    W("")
    W(table(["outcome", "groups"],
            [["correct COMPOSE_NEW", sum(1 for r in nov if r["A1_outcome"] == "COMPOSED_NEW"
                                         and r["A1_canonical_exact"])],
             ["wrong COMPOSE_NEW", sum(1 for r in nov if r["A1_outcome"] == "COMPOSED_NEW"
                                       and not r["A1_canonical_exact"])],
             ["false SELECT", sum(1 for r in nov if r["A1_outcome"] == "SELECTED_EXISTING")],
             ["abstention", sum(1 for r in nov if r["A1_outcome"] == "ABSTAIN")],
             ["A0 correct on the same groups", sum(1 for r in nov if r["A0_canonical_exact"])]]))
    W("")

    # 13 taxonomy
    W("## 13. Failure taxonomy (§18)")
    W("")
    W(table(["class", "count"], sorted((fsc.get("failure_taxonomy") or {}).items())))
    W("")
    W("Two classes were added to the specified list, for cases it does not cover.")
    W("`ABSTAIN_WITH_SHAPE_ONLY_CANDIDATE` and `ABSTAIN_NO_USABLE_CANDIDATE` sit")
    W("between the two specified abstain classes: abstaining when only the gold")
    W("*shape* was offered, or when the correct program exists in the workbook but")
    W("never reached the set the model saw, is neither \"with the correct candidate\"")
    W("nor \"nothing existed\".")
    W("")
    W("The three `FALSE_RECOVERY`s are the one behavioural difference the arms")
    W("show, and it is a hazard rather than a gain: on groups where no candidate")
    W("was correct, A1 reached for an existing candidate twice where A0 had")
    W("abstained, and once where A0 had composed something wrong. One case ran the")
    W("other way — 08_04 `D68`, a wrong composition became an abstention.")
    W("")

    # 14 workbook
    W("## 14. Scorer, value-only and regression (§§20, 22)")
    W("")
    W(table(["task", "canonical", "S base", "S A0", "S A1", "mod A0", "mod A1",
             "value-only A1", "reg A0", "reg A1"],
            [[k[0], k[1], w["BASE_S_correct"], w["A0_S_correct"], w["A1_S_correct"],
              f6((w.get("A0") or {}).get("modification_accuracy")),
              f6((w.get("A1") or {}).get("modification_accuracy")),
              f6((((w.get("A1_strict") or {}).get("modification")) or {}).get("value_only_accuracy")),
              f6((w.get("A0") or {}).get("regression_accuracy")),
              f6((w.get("A1") or {}).get("regression_accuracy"))]
             for k, w in sorted(wrows.items())]))
    W("")
    W("A blank arm is an abstention: nothing was written, so no variant exists.")
    W("")
    W("Two things in this table matter more than the ties.")
    W("")
    W("The single large gain, 08_03 `Working Capital!J44` at 10 to 151 correct")
    W("scorer cells and modification 0.0045 to 0.0683, is produced *identically* by")
    W("both arms. It is Phase C's result reproduced, not a candidate-interface")
    W("result.")
    W("")
    W("The only place A1 outscores A0, 08_05 `Working Capital!C66`, is a")
    W("`FALSE_RECOVERY`, and its headline is mostly an artifact: official")
    W("modification 0.061818 against a value-only 0.009091. Roughly 85% of that")
    W("apparent gain is the evaluator's error-value formula fallback rather than")
    W("agreement with gold, and the same fallback hides regression damage —")
    W("official 0.999995 against value-only 0.999859. Under value-only scoring a")
    W("wrong program bought five cells and damaged the workbook.")
    W("")

    # 15 cost
    W("## 15. Cost (§23)")
    W("")
    ci = co = 0
    for p in sorted((OUT / "choices").glob("*.json")):
        c = old.load(p)
        ci += c.get("choice_input_tokens", 0)
        co += c.get("choice_output_tokens", 0)
    ret = syn = 0
    for u in (units.get("units") or []):
        cid = u["canonical_cell_id"]
        name = f"{u['task']}__{cid.replace(':', '_')}.json"
        for d in CP.SESSION_DIRS:
            if (d / name).exists():
                s = old.load(d / name)
                ret += s.get("retrieval_input_tokens", 0)
                syn += s.get("synthesis_input_tokens", 0)
                break
    W(table(["quantity", "A0", "A1"],
            [["model calls per group", 1, 1],
             ["retrieval input tokens (shared, identical)", f"{ret:,}", f"{ret:,}"],
             ["decision-turn input tokens", f"{syn:,}", f"{ci:,}"],
             ["decision-turn output tokens", "—", f"{co:,}"]]))
    W("")
    W(f"A1 is not cheaper. Its decision turn costs **{ci - syn:+,}** input tokens against A0's,")
    W(f"about {100 * (ci - syn) / syn:+.1f}%, because the candidate block has to be serialized.")
    W("Per-cell synthesis is not reintroduced: both arms remain one model call per")
    W("ProgramGroup, and translation still supplies every other member for free.")
    W("")

    # 16 retrieval
    W("## 16. Retrieval, unchanged and reported (§24)")
    W("")
    W("Retrieval was not co-varied with the treatment, and the claim here is")
    W("stronger than \"same policy\": A1 issues no query at all. It rebuilds A0's")
    W("synthesis input from A0's own stored working set, so both arms rest on the")
    W("identical retrieval session, query for query.")
    W("")
    calls, limited, truncated = [], 0, 0
    for u in (units.get("units") or []):
        cid = u["canonical_cell_id"]
        nm = f"{u['task']}__{cid.replace(':', '_')}.json"
        for d in CP.SESSION_DIRS:
            if (d / nm).exists():
                sess = old.load(d / nm)
                calls.append(len([c for c in (sess.get("calls") or [])
                                  if c.get("sql") or c.get("action")]))
                limited += bool(sess.get("session_resource_limited"))
                truncated += bool(sess.get("synthesis_truncated"))
                break
    if calls:
        calls.sort()
        W(table(["quantity", "value"],
                [["shared retrieval sessions", len(calls)],
                 ["permitted SQL calls per session", lim.get("max_sql_calls")],
                 ["median SQL calls used", calls[len(calls) // 2]],
                 ["sessions using 7 or 8 of the 8", sum(1 for n in calls if n >= 7)],
                 ["sessions hitting the per-session token cap", limited],
                 ["synthesis turns truncated at budget", truncated]]))
        W("")
    W(f"{sum(1 for n in calls if n == lim.get('max_sql_calls'))} of {len(calls)} sessions "
      "used every permitted query and the remaining one used seven, so the")
    W("budget is still binding and retrieval is still unexonerated. It cannot,")
    W("however, explain any difference between these arms, because there is no")
    W("difference in it to explain.")
    W("")
    W("§24 asks that two failures be kept apart, and on this population they")
    W("separate cleanly:")
    W("")
    W(table(["failure", "where measured", "count"],
            [["candidate recovery failed - the program is in the compiled workbook "
              "but never reached the model-facing set",
              "Phase A, all 34 scorable groups", 3],
             ["program choice failed - the correct candidate was in the set and the "
              "model did not use it",
              "Phase B, the 7 RECOVERABLE_EXACT groups", 2]]))
    W("")
    W("The three recovery misses are all cross-sheet and none of them is inside the")
    W("executed population, which by construction takes its recoverable groups from")
    W("the class where the runtime set does contain the program. So within Phase B,")
    W("candidate recovery never failed: every miss there was a choice.")
    W("")
    W("Both of the choice failures are abstentions rather than wrong picks, at")
    W("15_04 `Consol_annual!N50` and `Consol_quarterly!E30`, with 51 and 44")
    W("candidates on offer including the correct one.")
    W("")

    # 17 oracle
    W("## 17. Oracle-choice ceiling (§25)")
    W("")
    orow = [r for r in rows if r["oracle_all_members_exact"] is not None]
    W(table(["task", "canonical", "required members", "A0 exact", "A1 exact",
             "oracle exact", "oracle all"],
            [[r["task"], r["canonical_member"], r["A0_members_required"],
              r["A0_members_exact"], r["A1_members_exact"], r["oracle_members_exact"],
              yn(r["oracle_all_members_exact"])] for r in orow]))
    W("")
    W("Evaluator-side, no model call: pick the gold candidate wherever the set")
    W("contains it, and translate. The upside from solving selection alone is")
    W("**zero additional fully-correct groups**. The five it would win are the five")
    W("both arms already win, and on the two the arms abstained from, the oracle")
    W("candidate reaches only 8 of 15 and 4 of 28 members — those groups are not")
    W("translation-uniform in gold, so even a perfect choice cannot complete them.")
    W("")

    # 17 instrumentation
    W("## 18. Instrumentation defects found by this run")
    W("")
    W(table(["#", "defect", "effect", "repair"],
            [["10", "a well-formed decision returned inside a single-key envelope, "
                    "`{\"answer\": \"{...}\"}`, read as though the envelope were the answer",
              "one A1 answer charged to the model as INVALID_OUTPUT",
              "narrow unwrap; re-derived from the retained raw response, no new model call"],
             ["11", "the A0 response schema returned to the A1 protocol: a formula "
                    "with no declared decision",
              "a second A1 answer lumped into INVALID_OUTPUT",
              "named `WRONG_RESPONSE_SCHEMA` and reported separately"]]))
    W("")
    changed = [r for r in rep.get("rows", []) if r["changed"]]
    if changed:
        W(table(["task", "canonical", "as run", "re-parsed", "re-parsed formula"],
                [[r["task"], r["canonical_member"], r["as_run_outcome"], r["reparsed_outcome"],
                  f"`{r['reparsed_formula']}`" if r["reparsed_formula"] else "—"]
                 for r in changed]))
        W("")
    W("Neither repair changes a correctness count: the recovered `SELECT K001` is")
    W("wrong, and `=J46+J48` misses gold `=J46+J47`. The as-run records are kept")
    W("intact beside the re-parsed ones.")
    W("")
    W("Two bugs in this probe's own harness were also found and fixed, and both")
    W("had produced results I would otherwise have reported:")
    W("")
    W("* The re-parse helper keyed units by canonical address alone. This")
    W("  population contains `Ratio Analysis!C19` in both 08_03 and 08_05, so one")
    W("  was resolved against the other's candidate set. Now keyed by task too.")
    W("* The first workbook pass reused Phase C's variant builder, whose output")
    W("  root is a module-level constant pointing at the Phase C run directory.")
    W("  This probe's variants were written into the previous probe's tree while")
    W("  recalculation ran against this one's, so every variant scored")
    W("  byte-identical to BASE — a perfect and meaningless tie. The tell was")
    W("  `Working Capital!J44` reporting 6 correct cells where Phase C measured")
    W("  152. That pass was discarded, not reported.")
    W("")

    # 18 verdict
    rec_a0 = sum(1 for r in rec if r["A0_canonical_exact"])
    rec_a1 = sum(1 for r in rec if r["A1_canonical_exact"])
    W("## 19. Architecture verdict (§26)")
    W("")
    W("### `EXISTING_PROGRAM_NOT_ENOUGH` — the primary verdict")
    W("")
    W("The gate is worded for exactly this outcome: candidate-first exposure did")
    W("not improve correctness even when the exact candidate was present.")
    W(f"RECOVERABLE_EXACT groups: A0 {rec_a0} of {len(rec)}, A1 {rec_a1} of {len(rec)}, the same five groups")
    W("and the same two abstentions. Across the whole population the arms are")
    W(f"identical group by group, {a0} of {len(rows)} each.")
    W("")
    W("What the gate then directs is to look past availability, and the two")
    W("abstentions say where. At 15_04 `Consol_annual!N50` and")
    W("`Consol_quarterly!E30` the model held the correct program in a list in front")
    W("of it, in sets of 51 and 44 candidates, and declined to answer. Availability")
    W("was not the constraint. What the abstention itself shows is only that the")
    W("model would not commit; whether it could not identify the candidate, or")
    W("could not satisfy itself that the goal was what it looked like, this probe")
    W("does not distinguish -- and the difference matters, so it is left open")
    W("rather than guessed.")
    W("")
    W("### `NOVEL_SYNTHESIS_DOMINANT` — also met, and it is the durable finding")
    W("")
    W(f"Recoverable groups: {rec_a1} of {len(rec)} correct. Genuinely novel groups: "
      f"{sum(1 for r in nov if r['A1_canonical_exact'])} of {len(nov)}.")
    W("The split is sharp, it is present in both arms, and it is the same split")
    W("that explains Phase C: both of that phase's canonical failures were novel")
    W("programs whose shapes occur zero times in their workbooks. Recovery is")
    W("largely solved; construction is not.")
    W("")
    W("### `CANDIDATE_RECOVERY_LIMITED` — partially supported, and secondary")
    W("")
    W("The M3 ceiling holds the correct program for 10 of 34 scorable groups; the")
    W("frozen runtime mechanism reaches 7. Those 3 are real misses and all three")
    W("are cross-sheet. But closing them cannot be worth much here: on the groups")
    W("the runtime set *did* reach, exposure changed nothing, so there is little")
    W("reason to expect that reaching three more would.")
    W("")
    W("### Gates not supported")
    W("")
    W("* `PROGRAM_RECOVERY_INTERFACE_EARNED` — requires a material improvement on")
    W("  RECOVERABLE_EXACT groups. There is none, and the interface costs")
    W("  4.2% more input tokens per decision and introduced three `FALSE_RECOVERY`s.")
    W("* `PROGRAM_SELECTION_MODEL_LIMITED` — this gate expects the model to select")
    W("  *another* candidate when the correct one is present. That never happened:")
    W("  0 wrong selections among the 7. The failure mode is abstention, not")
    W("  misdiscrimination, which is a different problem and points elsewhere.")
    W("")
    W("### Honest size of all of this")
    W("")
    W(f"Sixteen groups: {len(rec)} recoverable, {len(nov)} novel, "
      f"{len([r for r in rows if r['availability_class'] == 'RECOVERABLE_SHAPE_ONLY'])} shape-only. "
      "The population was")
    W("stratified by an evaluator-side label to make those contrasts visible, so")
    W("none of these fractions is a rate for anything. A null result on seven")
    W("groups is not proof that a candidate interface can never help; it is")
    W("evidence that this interface, on these groups, with this model, did not.")
    W("")

    # 19 answers
    W("## 20. Direct questions (§29)")
    W("")
    curve = {c["mechanism"]: c for c in (pre.get("recall_curve") or [])}
    W("**a. In how many ProgramGroups does the correct canonical program already exist somewhere in the input workbook?**")
    W("")
    W(f"Exactly translatable to the canonical cell: {round(curve['M3']['exact_candidate_recall'] * 34)} of 34 scorable groups "
      f"({100 * curve['M3']['exact_candidate_recall']:.1f}%). Present as a relative program but not")
    W(f"exactly bound: {round(curve['M3']['fingerprint_candidate_recall'] * 34)} of 34 ({100 * curve['M3']['fingerprint_candidate_recall']:.1f}%). One further group has the gold shape")
    W("in the workbook at a position from which it cannot legally translate.")
    W("")
    W("**b. In how many is it captured by the smallest mechanically useful runtime candidate set?**")
    W("")
    W(f"{round(curve['M0+M1+M2']['exact_candidate_recall'] * 34)} of 34 exactly "
      f"({100 * curve['M0+M1+M2']['exact_candidate_recall']:.1f}%), "
      f"{round(curve['M0+M1+M2']['fingerprint_candidate_recall'] * 34)} of 34 by shape — that is 7 of the 10 that are")
    W("reachable at all, for 31 candidates on average instead of 471.")
    W("")
    W("**c. Was the correct program mechanically available for the failed 08_04 canonical?**")
    W("")
    W("No. Gold `=C66*C67/12` is absent from M0, M1, M2 and the M3 ceiling, and its")
    W("relative program `=<REF>*<REF>/12` occurs zero times in 118,288 workbook")
    W("formulas.")
    W("")
    W("**d. Was it mechanically available for 08_05?**")
    W("")
    W("No, and for the same reason. Gold `=C62*C63+C64*C65`, shape")
    W("`=<REF>*<REF>+<REF>*<REF>`, occurs zero times in 118,177 formulas.")
    W("")
    W("**e. When the exact correct candidate is present, how often does GLM select it?**")
    W("")
    W(f"{rec_a1} of {len(rec)}. The remaining two are abstentions, not wrong picks: across the")
    W("whole population there were zero cases of selecting a different candidate")
    W("while the correct one was on offer.")
    W("")
    W("**f. Does candidate-first selection outperform free-form canonical synthesis?**")
    W("")
    W("No. The arms agree on every one of the sixteen groups, canonical and")
    W("all-member alike, and A1's decision turn costs about 4% more. The only")
    W("workbook-level difference favouring A1 is a wrong program whose apparent")
    W("gain is 85% scorer fallback.")
    W("")
    W("**g. How does selection accuracy degrade as the candidate set becomes ambiguous?**")
    W("")
    W("From 4 of 4 at twenty candidates or fewer to 1 of 3 above twenty — but A0")
    W("shows the identical pattern without ever seeing a list, so on this")
    W("population the degradation cannot be attributed to ambiguity.")
    W("")
    W("**h. How often does the model unnecessarily synthesize something new despite a correct existing candidate?**")
    W("")
    W("Never: 0 of 7 `NEW_WHEN_RECOVERABLE`. When it answered at all with a correct")
    W("candidate available, it selected it.")
    W("")
    W("**i. On genuinely novel programs, how often can GLM compose the correct canonical formula?**")
    W("")
    W(f"{sum(1 for r in nov if r['A1_canonical_exact'])} of {len(nov)} in A1, and "
      f"{sum(1 for r in nov if r['A0_canonical_exact'])} of {len(nov)} in A0. Novel synthesis is where this")
    W("architecture currently fails, and neither arm touches it.")
    W("")
    W("**j. Once canonical choice is correct, does deterministic translation continue to deliver all-member correctness?**")
    W("")
    W("Yes, without exception. In all five groups with a correct canonical, every")
    W("required member is exactly correct — 5 of 5, 6 of 6, 6 of 6, 6 of 6, 6 of 6.")
    W("Phase C's result holds under a different choice mechanism, which is some")
    W("evidence it is a property of translation rather than of that run.")
    W("")
    W("**k. Is the remaining bottleneck candidate recovery, candidate discrimination/binding, or genuinely novel synthesis?**")
    W("")
    W("Novel synthesis first: 0 of 6, and the two Phase C failures are the same")
    W("kind. Binding second: 0 of 3 shape-only groups, where the right program")
    W("shape was available and the references were wrong. Recovery last: 3 groups")
    W("where the runtime set missed a program M3 could reach — real, but the")
    W("cheapest of the three to be wrong about, because reaching more candidates")
    W("demonstrably did not convert into more correct answers.")
    W("")
    W("**l. Should the final runtime policy become select-if-recoverable, else compose, then translate?**")
    W("")
    W("Not on this evidence. The recovery branch changed no answer that free")
    W("composition did not already get, and it added a failure mode free")
    W("composition does not have: on three groups where nothing correct was on")
    W("offer, being shown a list of plausible programs turned two abstentions and")
    W("one wrong composition into confident wrong selections. Exposure is not free")
    W("when the correct program is absent, and the preflight says it is absent")
    W("about 70% of the time.")
    W("")
    W("The part of the policy that *is* earned stays exactly as Phase C left it:")
    W("one program choice per ProgramGroup, then deterministic translation.")
    W("")
    W("### Final research question")
    W("")
    W("> Once repeated execution has been removed, can canonical formula generation")
    W("> itself be decomposed into closed-world recovery of an existing workbook")
    W("> program versus genuinely novel program synthesis — and which side is now")
    W("> the actual model-capability frontier?")
    W("")
    W("The decomposition is real and it is mechanical. Without any model call, the")
    W("harness can now say of each ProgramGroup whether the program it needs")
    W("already exists in the workbook, exists only as a shape, or does not exist at")
    W("all — and on this population that comes out roughly 30 / 40 / 30. That is a")
    W("genuine structural fact about the task, and it predicts outcomes: every")
    W("group either arm solved is a recoverable one, and every group both arms")
    W("failed is shape-only or novel.")
    W("")
    W("But the decomposition does not cash out as an interface. Exposing the")
    W("recovery side as an explicit closed-world choice bought nothing, because the")
    W("model was already recovering those programs by composing them — when the")
    W("answer is a program the workbook repeats, free-form synthesis and selection")
    W("converge on it. The frontier is the other side, and it is not close: zero of")
    W("six novel programs, in both arms, including the two that ended Phase C.")
    W("")
    W("So the useful reading is that recovery was never really the bottleneck; it")
    W("only looked like one because it was invisible. Now that it can be measured,")
    W("it turns out to be the part that already works. What remains is the part no")
    W("amount of workbook context supplies: constructing a program the workbook has")
    W("never seen.")
    W("")
    return "\n".join(L)


if __name__ == "__main__":
    md = build()
    (OUT / "CANONICAL_CHOICE_REPORT.md").write_text(md, encoding="utf-8")
    print(f"{len(md.splitlines())} lines")
