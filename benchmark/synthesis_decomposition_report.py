#!/usr/bin/env python3
"""Report the N0-N3 factorial and the oracle evidence-completion arm.

Both diagnostics read gold, so nothing here is a rate estimate for anything
deployable. The factorial is mechanism validation on four cells carrying three
independent programs; the completion arm is a counterfactual about evidence, not
a retrieval result. The report is written to keep both of those caveats attached
to every number rather than in a footnote.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import end_to_end_composition_probe as old
import synthesis_decomposition as sd

OUT = sd.OUT
NON_MODEL = set(("TRUNCATED_NO_CONTENT", "TRUNCATED_AT_BUDGET",
                 "MODEL_ACCESS_FAILURE", "SESSION_RESOURCE_LIMIT"))


def table(headers, rows):
    L = ["| " + " | ".join(headers) + " |",
         "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        L.append("| " + " | ".join("" if x is None else str(x) for x in r) + " |")
    return L


def yn(v):
    return "yes" if v else "no"


def _cells(rows, arm):
    return [r for r in rows if r["arm"] == arm]


def _programs(rows, arm):
    by = defaultdict(list)
    for r in _cells(rows, arm):
        by[r["program_key"]].append(r)
    return by


def report() -> str:
    d = old.load(OUT / "results.json")
    N, E = d["N"], d["E"]
    L = ["# Synthesis decomposition: N0-N3 factorial and oracle evidence completion", ""]

    # 1 ---------------------------------------------------------------
    L += ["## 1. What these two diagnostics are", "",
          "The operand audit split Phase D's eleven wrong canonicals into six whose gold",
          "operands were all materialized in the synthesis working set and five whose were",
          "not. Two different earliest losses, so two probes.", "",
          "**N0-N3** is a factorial over the four *clean* construction failures, where all",
          "four arms rest on identical delivered evidence. N0 is the stored payload",
          "rebuilt; N1 adds the gold operator/function skeleton with numbered holes; N2",
          "adds the exact gold reference set, sorted, with no operators; N3 adds both. It",
          "is mechanism validation, not a rate estimate.", "",
          "**E1** is oracle evidence completion over the five delivery failures. The stored",
          "payload is rebuilt byte for byte and the missing gold operand cells are added to",
          "the working set with their ordinary materialized evidence, exactly as retrieval",
          "would have delivered them. No skeleton, no reference list, no candidate list, no",
          "hint of how the operands combine.", "",
          "Both arms read gold. **E1 is an oracle evidence-completion arm, not a retrieval",
          "improvement.** It measures what a perfect retriever would have bought, which is",
          "the precondition for deciding whether a gold-blind retrieval mechanism is worth",
          "designing -- it is not itself such a mechanism and cannot be deployed.", "",
          "The two RECOVERABLE_EXACT abstentions are in neither population. Correct program",
          "present, operands present, model declines to commit: that is a commitment or",
          "calibration phenomenon, and folding it into \"construction failure\" would assume",
          "the answer instead of earning it.", ""]

    # 2 ---------------------------------------------------------------
    L += ["## 2. Populations", ""]
    L += table(["arm", "groups", "members"],
               [["N0-N3", len(d["population_N"]), ", ".join(d["population_N"])],
                ["E1", len(d["population_E"]), ", ".join(d["population_E"])]])
    keys = sorted({r["program_key"] for r in N})
    L += ["", f"The four N cells carry **{len(keys)} independent programs**: `08_04 C68` and",
          "`D68` are the same program on adjacent columns, related by translation. Every N",
          "result below is reported at both levels, so four cells are never read as four",
          "independent trials.", ""]

    # 3 ---------------------------------------------------------------
    L += ["## 3. Payload reconstruction fidelity", "",
          "N0 is the stored synthesis payload rebuilt from the session record. If the",
          "reconstruction is faithful the provider's measured prompt token count must equal",
          "the one stored from the original call. This is the only check available -- the",
          "original request body was not retained -- and it validates the same rebuild",
          "procedure that E1 depends on.", ""]
    L += table(["group", "stored prompt_tokens", "N0 prompt_tokens", "identical"],
               [[r["canonical_member"], r["stored_synthesis_input_tokens"], r["input_tokens"],
                 yn(r["input_tokens"] == r["stored_synthesis_input_tokens"])]
                for r in _cells(N, "N0")])
    same = sum(1 for r in _cells(N, "N0")
               if r["input_tokens"] == r["stored_synthesis_input_tokens"])
    L += ["", f"Exact on {same} of {len(_cells(N, 'N0'))}.", ""]
    n0_repro = sum(1 for r in _cells(N, "N0") if r["formula"] == _a0(r))
    L += [f"N0 also re-asks a question already answered: at temperature 0 it should return",
          f"the A0 formula. It reproduced it on {n0_repro} of {len(_cells(N, 'N0'))}.", ""]

    # 4 ---------------------------------------------------------------
    L += ["## 4. The factorial, cell level", ""]
    rows = []
    for r in sorted(N, key=lambda x: (x["canonical_member"], x["arm"])):
        rows.append([r["arm"], f'{r["task"]} {r["canonical_member"]}', r["gold"],
                     r["status"], r["formula"], yn(r["exact"]),
                     r["truncation_class"] or r["failure_class"] or ""])
    L += table(["arm", "group", "gold", "status", "formula", "exact", "non-model"], rows)
    L += [""]
    L += table(["arm", "cells exact", "of", "abstained"],
               [[a, sum(1 for r in _cells(N, a) if r["exact"]), len(_cells(N, a)),
                 sum(1 for r in _cells(N, a) if r["status"] == "ABSTAIN")] for a in sd.ARMS])

    # 5 ---------------------------------------------------------------
    L += ["", "## 5. The factorial, independent-program level", "",
          "A program counts as solved only when every cell carrying it is exact.", ""]
    prow = []
    for a in sd.ARMS:
        by = _programs(N, a)
        solved = [k for k, rs in by.items() if rs and all(r["exact"] for r in rs)]
        split = [k for k, rs in by.items() if len(rs) > 1 and len({r["exact"] for r in rs}) > 1]
        prow.append([a, len(solved), len(by), ", ".join(sorted(solved)) or "--",
                     ", ".join(sorted(split)) or "none"])
    L += table(["arm", "programs solved", "of", "solved", "cells disagree"], prow)

    # 6 ---------------------------------------------------------------
    L += ["", "## 6. What the factorial says", ""]
    n1 = sum(1 for r in _cells(N, "N1") if r["exact"])
    n2 = sum(1 for r in _cells(N, "N2") if r["exact"])
    n3 = sum(1 for r in _cells(N, "N3") if r["exact"])
    n0 = sum(1 for r in _cells(N, "N0") if r["exact"])
    tot = len(_cells(N, "N0")) or 1
    if n3 == 0:
        verdict = ("`PROTOCOL_INVALID` -- N3 supplies both the skeleton and the reference "
                   "set and still fails, so the residual assembly step, the response "
                   "schema or the oracle wording is broken. Nothing else in the factorial "
                   "can be read until that is fixed.")
    elif n1 > n2:
        verdict = ("`LOCAL_SHAPE_EFFECT` -- in this four-cell shakedown, supplying the "
                   "shape converted more cells than supplying the reference set. This is "
                   "mechanism validation only, not a prevalence estimate.")
    elif n2 > n1:
        verdict = ("`LOCAL_REFERENCE_SET_EFFECT` -- in this four-cell shakedown, supplying "
                   "the reference set converted more cells than supplying the shape. The "
                   "conversion is the single clean shape-only case, J50; it shows a binding "
                   "phenomenon, not a prevalent second frontier.")
    elif n1 == n2 == 0 and n3 > 0:
        verdict = ("`BOTH_FACTORS_REQUIRED_LOCALLY` -- neither factor alone converted a "
                   "cell in this shakedown and both together did. This is mechanism "
                   "validation only, not a prevalence estimate.")
    else:
        verdict = ("`BOTH_FACTORS_SUFFICIENT_LOCALLY` -- shape and references converted "
                   "equally in this shakedown. This is mechanism validation only, not a "
                   "prevalence estimate.")
    L += table(["arm", "supplied", "cells exact"],
               [["N0", "nothing (stored payload)", f"{n0}/{tot}"],
                ["N1", "gold skeleton, holes unbound", f"{n1}/{tot}"],
                ["N2", "gold reference set, no operators", f"{n2}/{tot}"],
                ["N3", "both", f"{n3}/{tot}"]])
    L += ["", "**Verdict.** " + verdict, ""]

    # 7 ---------------------------------------------------------------
    L += ["## 7. Oracle evidence completion", "",
          "E0 is the original A0 answer as run. E1 is the same payload with the missing",
          "gold operand cells delivered and nothing else changed.", ""]
    erows = []
    for r in sorted(E, key=lambda x: x["canonical_member"]):
        erows.append([f'{r["task"]} {r["canonical_member"]}', r["gold"],
                      len(r["completed_operand_ids"]),
                      r["E0_formula"], yn(r["E0_exact"]),
                      r["formula"], yn(r["exact"]),
                      r["truncation_class"] or r["failure_class"] or ""])
    L += table(["group", "gold", "cells added", "E0 formula", "E0 exact",
                "E1 formula", "E1 exact", "non-model"], erows)
    conv = sum(1 for r in E if r["exact"] and not r["E0_exact"])
    lost = sum(1 for r in E if r["E0_exact"] and not r["exact"])
    L += ["", f"Converted by delivery alone: **{conv} of {len(E)}**."
          + (f" Lost: {lost}." if lost else "")]
    if len(E) and conv >= (len(E) + 1) // 2:
        ev = ("`EVIDENCE_DELIVERY_CAUSAL` -- the missing operands were not merely missing, "
              "they were decisive. A gold-blind retrieval mechanism aimed at cross-sheet "
              "and cross-region operand discovery is now an earned research branch. Note "
              "what is *not* earned: raising the SQL budget, which this probe never tested.")
    elif conv == 0:
        ev = ("`APPARENT_RETRIEVAL_LIMIT` -- delivering the operands converted nothing. "
              "Those groups were only apparently retrieval-limited: the missing operands "
              "were real but not sufficient to explain the failure, which strengthens the "
              "construction thesis rather than opening a retrieval branch.")
    else:
        ev = ("`EVIDENCE_DELIVERY_PARTIAL` -- delivery converts some groups and not others, "
              "so missing evidence has causal value on part of this population and the "
              "rest is a second loss stacked behind it.")
    L += ["", "**Verdict.** " + ev, ""]

    # 8 ---------------------------------------------------------------
    L += ["## 8. Instrumentation and cost", ""]
    allr = N + E
    bad = [r for r in allr if (r["truncation_class"] or r["failure_class"])]
    L += table(["", "value"],
               [["model", d["limits"]["model"]],
                ["temperature", d["limits"]["temperature"]],
                ["reasoning", d["limits"]["reasoning"]],
                ["retries", d["limits"]["retries"]],
                ["SQL queries issued", 0],
                ["model calls", len(allr)],
                ["input tokens", d["input_tokens"]],
                ["output tokens", sum(r["output_tokens"] for r in allr)],
                ["non-model failures", len(bad)],
                ["input cap", d["limits"]["total_input_cap"]]])
    if bad:
        L += [""] + table(["call", "class"],
                          [[r["name"], r["truncation_class"] or r["failure_class"]] for r in bad])

    # 9 ---------------------------------------------------------------
    L += ["", "## 9. The causal map, as it now stands", "", "```text",
          "Canonical program failure",
          "        |",
          "        +-- required operand not materialized",
          "        |      -> EVIDENCE DELIVERY   [5 groups; E1 says whether it is causal]",
          "        |",
          "        +-- operands fully materialized",
          "               |",
          "               +-- program shape exists, references wrong",
          "               |      -> BINDING       [one clean case: 08_03 J50; prevalence unresolved]",
          "               |",
          "               +-- program genuinely novel, construction wrong",
          "               |      -> NOVEL CONSTRUCTION  [strongest result]",
          "               |",
          "               +-- exact program available, model abstains",
          "                      -> COMMITMENT / GOAL-EVIDENCE  [unresolved, 2 groups]",
          "```", "",
          "One meta-result is worth keeping attached to this: **query-budget saturation was",
          "a warning, not a diagnosis.** Nearly every Phase D session spent all eight",
          "queries, and the construction failures lost almost as many turns to timeouts and",
          "oversized results as the delivery failures did while still having every operand.",
          "Raising the budget would have been a top-down intervention justified by a",
          "correlation. E1 tests whether the missing evidence has causal value first.", ""]
    return "\n".join(L)


def _a0(r):
    """A0's stored formula for an N-population group, for the N0 reproduction check."""
    import canonical_choice_select as sel
    for row in old.load(sel.OUT / "operand_availability.json")["units"]:
        if row.get("canonical_member") == r["canonical_member"] and row.get("task") == r["task"]:
            return row["A0_formula"]
    return None


if __name__ == "__main__":
    text = report()
    old.write(OUT / "SYNTHESIS_DECOMPOSITION_REPORT.md", text)
    print(text)
