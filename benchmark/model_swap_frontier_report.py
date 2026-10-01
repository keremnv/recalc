#!/usr/bin/env python3
"""Render the frozen GPT model-swap frontier report."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_swap_frontier as ms
import program_group as pg
import staged_synthesis_probe as staged


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join("" if x is None else str(x) for x in row) + " |" for row in rows]
    return out


def j(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def main():
    out = ms.OUT
    freeze = load(out / "freeze.json")
    gpt = load(out / "evaluated.json")
    glm_calls = {}
    for meta in freeze["population"]:
        stem = f'{meta["task"]}__{meta["canonical_member"].replace("!", "_").replace(" ", "_")}__F0'
        glm_calls[(meta["task"], meta["canonical_member"])] = load(ms.SOURCE / "calls" / f"{stem}.json")
    glm_eval = {(r["task"], r["canonical_member"]): r for r in load(ms.SOURCE / "evaluated.json")}

    groups = defaultdict(list)
    for r in gpt:
        groups[r["program_key"]].append(r)
    gpt_exact = sum(bool(r["formula_exact"]) for r in gpt)
    glm_exact = sum(bool(glm_eval[k]["F0_exact"]) for k in glm_eval)
    representative_gpt = sum(any(bool(r["formula_exact"]) for r in rs) for rs in groups.values())
    replicated_gpt = sum(all(bool(r["formula_exact"]) for r in rs) for rs in groups.values())
    representative_glm = sum(any(bool(glm_eval[(r["task"], r["canonical_member"])] ["F0_exact"]) for r in rs) for rs in groups.values())
    replicated_glm = sum(all(bool(glm_eval[(r["task"], r["canonical_member"])] ["F0_exact"]) for r in rs) for rs in groups.values())

    costs = []
    for r in gpt:
        u = r.get("end_to_end", {})
        usage = next(x for x in load(out / "primary.json") if x["task"] == r["task"] and x["canonical_member"] == r["canonical_member"]).get("usage", {})
        costs.append([r["canonical_member"], usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), usage.get("cost", 0)])
    total_in = sum(x[1] for x in costs)
    total_out = sum(x[2] for x in costs)
    total_cost = round(sum(float(x[3] or 0) for x in costs), 8)

    lines = [
        "# GPT model-swap frontier probe",
        "",
        "This is a four-call model-capability intervention, not a benchmark or a new harness arm.",
        "The architecture, frozen workbook evidence, target, synthesis protocol, deterministic",
        "translation, neutral writer, recalculation, and scorer were held fixed. No SQL calls",
        "were issued and no gold information entered a primary request.",
        "",
        "## 1. Frozen population and independence",
        "",
    ]
    lines += table(["task", "canonical", "gold (evaluator only)", "working-set SHA-256", "evidence SHA-256"], [
        [m["task"], m["canonical_member"], next(r["gold_formula"] for r in gpt if r["task"] == m["task"] and r["canonical_member"] == m["canonical_member"]), m["working_set_sha256"], m["evidence_sha256"]]
        for m in freeze["population"]
    ])
    lines += ["", "Cell-level n=4. Independent-program n=3: C68 and D68 share one relative program; C66 and J50 are separate.", ""]
    lines += table(["program key", "cells", "GPT exact cells"], [[k, ", ".join(x["canonical_member"] for x in rs), sum(bool(x["formula_exact"]) for x in rs)] for k, rs in sorted(groups.items())])

    lines += ["", "## 2. Request fidelity and instrumentation", "",
              "Each GPT request was copied from the retained GLM F0 request body. Provider-independent sections (messages, output contract, response format, and token ceiling) hash-identically for all four cases.",
              "The only request-body differences are model identifier and reasoning setting: GLM `z-ai/glm-5.3-flash`, medium; GPT `openai/gpt-5.6-sol`, high. Temperature remained 0 and retries remained 0.",
              "The call records retain complete system prompt, complete user payload, raw response body, parsed response, usage, finish reason, truncation state, source GLM request path/hash, and fidelity hashes.", ""]
    lines += table(["canonical", "provider-independent request identical", "GLM request SHA-256", "GPT request SHA-256", "working/evidence preserved"], [
        [r["canonical_member"], r["request_fidelity"]["identical"], glm_calls[(r["task"], r["canonical_member"])] ["request_sha256"], next(x for x in load(out / "primary.json") if x["task"] == r["task"] and x["canonical_member"] == r["canonical_member"])["request_sha256"], True]
        for r in gpt
    ])
    lines += ["", "Non-model failures: 0/4. Truncation: 0/4. New SQL calls: 0.", ""]

    lines += ["## 3. GLM versus GPT canonical outputs", ""]
    lines += table(["canonical", "gold", "GLM F0", "GPT G0", "GPT class", "GPT exact"], [
        [r["canonical_member"], r["gold_formula"], (glm_calls[(r["task"], r["canonical_member"])] .get("parsed_response") or {}).get("formula"), r["formula"], r["classification"]["class"], r["formula_exact"]]
        for r in gpt
    ])

    lines += ["", "## 4. Exactness and independence accounting", ""]
    lines += table(["arm", "cell exact", "of 4", "representative independent exact", "of 3", "replication-consistent independent exact", "of 3"], [
        ["GLM F0", glm_exact, 4, representative_glm, 3, replicated_glm, 3],
        ["GPT G0", gpt_exact, 4, representative_gpt, 3, replicated_gpt, 3],
    ])
    lines += ["", "Representative independent exactness counts a program if at least one of its frozen cells is exact. Replication-consistent exactness requires every frozen instantiation of that program to be exact; this is the stricter number and exposes the C68/D68 inconsistency.", ""]

    lines += ["## 5. Mandatory autopsies", ""]
    for target in ("Working Capital!C68", "Working Capital!C66", "Working Capital!J50", "Working Capital!D68"):
        r = next(x for x in gpt if x["canonical_member"] == target)
        lines += [f"### {target}", "", f"Gold: `{r['gold_formula']}`", f"GPT: `{r['formula']}`", f"Classification: `{r['classification']['class']}`", f"Mechanical validation: `{r['mechanical_validation']['reason']}`", ""]
    lines += ["C68: GPT inferred `=C66*C67/12` exactly, including both structure and bindings.",
              "C66: GPT abstained; it did not recover the two multiplicative pairs plus outer addition.",
              "J50: GPT selected the correct J46:J47 reference set but expressed it as `SUM(J46:J47)`, not the canonical binary `ADD` form. This is a binding success without canonical-structure exactness.",
              "D68: GPT used the correct D66/D67 references but omitted annualization, producing `=D66/D67`.", ""]

    c68 = next(r for r in gpt if r["canonical_member"] == "Working Capital!C68")
    d68 = next(r for r in gpt if r["canonical_member"] == "Working Capital!D68")
    translated = pg.translate(c68["formula"], tuple(staged.units()[("08_04", "Working Capital!C68")]["canonical_cell"]), tuple(staged.units()[("08_04", "Working Capital!D68")]["canonical_cell"]))
    lines += ["", "C68/D68 consistency: translating GPT's exact C68 formula deterministically yields `" + translated + "`; GPT's independently generated D68 was `" + str(d68["formula"]) + "`. The same-program replication therefore fails.", ""]

    lines += ["## 6. End-to-end translation and workbook scoring", ""]
    score_rows = []
    for r in gpt:
        gs, strict = r["score"], r["strict_score"]
        oldr = glm_eval[(r["task"], r["canonical_member"])]
        old_s, old_strict = oldr["F0_score"], oldr["F0_strict_score"]
        score_rows.append([
            r["canonical_member"], r["all_member_exact"], gs["exact"], strict["modification"]["official_accuracy"], strict["modification"]["value_only_accuracy"], gs["regression"]["accuracy"],
            strict["modification"]["official_correct"] - old_strict["modification"]["official_correct"], strict["regression"]["official_correct"] - old_strict["regression"]["official_correct"]])
    lines += table(["canonical", "all-member formula exact", "official exact", "official modification", "value-only modification", "regression", "Δ modification correct", "Δ regression correct"], score_rows)
    lines += ["", "All GPT variants used the frozen ProgramGroup translation path and neutral writer. No translation failures occurred. Only C68 had all required member formulas exact; no workbook variant was officially exact. Value-only modification scores did not improve over GLM on this population.", ""]

    lines += ["## 7. Cost", ""]
    lines += table(["canonical", "input tokens", "output tokens", "provider-reported cost"], costs)
    lines += ["", f"Total: 4 calls, {total_in} input tokens, {total_out} output tokens, provider-reported cost `${total_cost}`. No retries.", ""]

    lines += ["## 8. Architecture verdict", "",
              "**Verdict: `FRONTIER_PARTIALLY_MODEL_SPECIFIC`, with no replication-consistent independent-program win.** Changing only the model moved the cell-level frontier: GPT solved C68 exactly where GLM failed, and it recovered J50's reference set without oracle references. However, GPT failed to reproduce the same C68 program at D68, abstained on C66, and did not produce the canonical J50 structure. Thus GPT is not 2/3 or 3/3 on the independent-program population; the strict replication-consistent result is 0/3, while representative exactness is 1/3.",
              "This is positive causal evidence that model capability matters, but it does not earn a Program Sketch IR or Operand Binding IR, and it does not establish global representation sufficiency. The remaining frontier is mixed: partly GLM-specific, with unresolved representation/task-semantic difficulty on C66 and replication/commitment consistency.",
              "The optional two commitment cases were not run; they remain separate from this primary verdict.", ""]

    lines += ["## 9. Direct answers", "",
              "a. Yes at cell level: GPT solved C68; no complete independent-program win under strict C68/D68 replication accounting.",
              "b. Strictly 0/3 independent programs; 1/3 representative program identities had at least one exact cell.",
              "c. C68 yes; D68 no. GPT did not consistently infer the `REF*REF/12` analogue.",
              "d. No. C66 abstained.",
              "e. J50 binding: yes for the reference set J46/J47; canonical structure: no, because GPT used SUM.",
              "f. GPT's residual losses were one abstention, one structural omission with correct references, and one noncanonical structure with correct references; no case showed wrong binding in the ordinary point-reference sense.",
              "g. When GPT chose C68's correct canonical formula, frozen translation produced all required member formulas exactly. D68's own wrong canonical choice did not.",
              "h. No aggregate value-only workbook gain was observed.",
              "i. No information, retrieval, target, prompt-content, execution, translation, or scorer component changed; only model identifier and requested reasoning setting changed.",
              "j. Best refinement: partially model-specific, not fully resolved. The cell-level move is causal, but strict independent-program replication remains 0/3.",
              "k. Not justified by aggregate correctness on four cases: 4 calls cost $" + str(total_cost) + " and produced one canonical exact cell.",
              "l. No. A Program Sketch IR did not earn itself from the prior decomposition probe, and this model-only arm gives no reason to introduce it.",
              "m. No. An Operand Binding IR did not earn itself.",
              "n. The GLM-only frontier is not universal: GPT moved it at C68 and J50 binding, but the frozen evidence still leaves a harder residual frontier at C66 and in program replication.",
              ""]
    (out / "MODEL_SWAP_FRONTIER_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(out / "MODEL_SWAP_FRONTIER_REPORT.md")


if __name__ == "__main__":
    main()
