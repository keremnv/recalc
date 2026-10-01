#!/usr/bin/env python3
"""Render the staged-synthesis probe without adding evaluator information to runs."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import staged_synthesis_probe as sp
import synthesis_decomposition as sd


OUT = sp.OUT


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join("" if x is None else str(x) for x in row) + " |" for row in rows]
    return out


def j(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def costs():
    out = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
    for p in (OUT / "calls").glob("*.json"):
        d = load(p); a = out[d["stage"]]
        a["calls"] += 1; a["input_tokens"] += d.get("input_tokens", 0); a["output_tokens"] += d.get("output_tokens", 0)
        a["cost"] += float(((d.get("response_body") or {}).get("usage") or {}).get("cost") or 0)
    for a in out.values(): a["cost"] = round(a["cost"], 8)
    return out


def artifact_fidelity(primary):
    rows = []
    complete = True
    for p in (OUT / "calls").glob("*.json"):
        d = load(p)
        required = ("request", "system_prompt", "user_payload", "response_raw_body",
                    "parsed_response", "usage", "finish_reason", "truncation_class",
                    "stage")
        ok = all(k in d for k in required)
        complete &= ok
        rows.append({"name": d["name"], "complete": ok})
    return complete, rows


def info_preservation(primary):
    rows = []
    for r in primary:
        calls = {}
        prefix = f'{r["meta"]["task"]}__{r["meta"]["canonical_member"].replace("!", "_").replace(" ", "_")}'
        for p in (OUT / "calls").glob(prefix + "__*.json"):
            d = load(p); calls[d["stage"]] = json.loads(d["user_payload"])
        base = calls.get("F0", {})
        base_ids = base.get("WORKING_SET_ENTITY_IDS")
        base_ev = sp.sha(base.get("WORKING_SET_EVIDENCE"))
        ok = True
        for stage, payload in calls.items():
            same = payload.get("WORKING_SET_ENTITY_IDS") == base_ids and sp.sha(payload.get("WORKING_SET_EVIDENCE")) == base_ev
            ok &= same
        rows.append({"canonical_member": r["meta"]["canonical_member"], "all_stages_preserve_evidence": ok,
                     "working_set_sha256": sp.sha(base_ids), "evidence_sha256": base_ev})
    return rows


def report():
    freeze = load(OUT / "freeze.json")
    primary = load(OUT / "primary.json")
    evaluated = load(OUT / "evaluated.json")
    c = costs()
    fidelity, _ = artifact_fidelity(primary)
    preserve = info_preservation(primary)
    total_calls = sum(x["calls"] for x in c.values())
    total_in = sum(x["input_tokens"] for x in c.values())
    total_out = sum(x["output_tokens"] for x in c.values())
    total_cost = round(sum(x["cost"] for x in c.values()), 8)
    L = ["# Staged novel-formula synthesis probe", "",
         "This is a narrow mechanism diagnostic, not a rate estimate. The only primary",
         "treatment is whether the model's own computation/operand decision is persisted",
         "between two model calls. No gold sketch, gold reference set, candidate list, or",
         "oracle evidence was supplied to F0/F1/F2.", ""]

    L += ["## 1. Frozen population and independence", ""]
    L += table(["task", "canonical", "availability", "working-set size", "working-set SHA-256", "evidence SHA-256"],
               [[r["task"], r["canonical_member"], r["availability_class"], r["working_set_size"], r["working_set_sha256"], r["evidence_sha256"]] for r in freeze["population"]])
    groups = defaultdict(list)
    for r in evaluated: groups[r["program_key"]].append(r)
    L += ["", "Cell-level population is 4. Independent-program population is 3:", ""]
    L += table(["program key", "cells"], [[k, ", ".join(x["canonical_member"] for x in v)] for k, v in sorted(groups.items())])
    L += ["", "C68 and D68 are counted as one independent program under translation.", ""]

    L += ["## 2. Information preservation and retained artifacts", "",
          f"All staged calls preserve the same frozen working-set IDs and evidence as F0: **{all(x['all_stages_preserve_evidence'] for x in preserve)}**.",
          f"Every persisted call has system prompt, user payload, raw response body, parsed response, usage, finish reason, truncation class, and arm metadata: **{fidelity}**.", ""]
    L += table(["canonical", "evidence preserved", "working-set SHA-256", "evidence SHA-256"],
               [[x["canonical_member"], x["all_stages_preserve_evidence"], x["working_set_sha256"], x["evidence_sha256"]] for x in preserve])
    L += ["", "The previous decomposition calls remain preserved under `retries/`; this run retains original request bodies in `calls/`.", ""]

    L += ["## 3. Stage artifacts and evaluator classifications", ""]
    for r in evaluated:
        L += [f"### {r['task']} {r['canonical_member']}", "",
              f"Gold (evaluator only): `{r['gold_formula']}`", "",
              f"- F0: `{r['F0_formula']}`; exact={r['F0_exact']}",
              f"- F1a sketch: `{j(r['F1a_sketch'])}`; class=`{r['F1a_class']}`",
              f"- F1b bindings: `{j(r['F1b_bindings'])}`; unconditional class=`{r['F1b_bindings_unconditional_class']}`; given-correct-sketch=`{r['F1b_class_given_correct_sketch']}`",
              f"- F1 assembled: `{r['F1_assembled_formula']}`; exact={r['F1_assembled_exact']}",
              f"- F2a operands: `{j(r['F2a_operand_ids'])}`; class=`{r['F2a_class']}`",
              f"- F2b structure: `{j(r['F2b_structure'])}`; unconditional shape exact={r['F2b_structure_unconditional_exact']}; conditioned class=`{r['F2b_class_given_sufficient_operands']}`",
              f"- F2 assembled: `{r['F2_assembled_formula']}`; exact={r['F2_assembled_exact']}", ""]

    L += ["## 4. Stage-level results", ""]
    L += table(["stage", "cell outcomes"], [
        ["F1a sketch", dict(Counter(r["F1a_class"] for r in evaluated))],
        ["F1b bindings, unconditional", dict(Counter(r["F1b_bindings_unconditional_class"] for r in evaluated))],
        ["F2a operands", dict(Counter(r["F2a_class"] for r in evaluated))],
        ["F2b structure, unconditional", {"correct": sum(r["F2b_structure_unconditional_exact"] for r in evaluated), "of_calls": sum(r["F2b_structure"] is not None for r in evaluated)}],
    ])
    L += ["", "No F1a sketch was evaluator-correct. No F2a operand set was exact. Therefore no second-stage result is conditioned on a correct first-stage artifact.", ""]
    L += ["Mechanical validation (syntax/entity/self-reference/translation gate):", ""]
    L += table(["canonical", "F0", "F1", "F2", "translation failures"], [
        [r["canonical_member"], r["F0_mechanical_validation"]["reason"], r["F1_mechanical_validation"]["reason"], r["F2_mechanical_validation"]["reason"],
         sum(len(r[f"{s}_end_to_end"]["translation_failures"]) for s in ("F0", "F1", "F2"))]
        for r in evaluated
    ])

    L += ["## 5. Canonical and independent-program exactness", ""]
    L += table(["arm", "cell exact", "of 4", "independent programs exact", "of 3"], [
        ["F0", sum(bool(r["F0_exact"]) for r in evaluated), 4, sum(all(bool(x["F0_exact"]) for x in rs) for rs in groups.values()), 3],
        ["F1", sum(bool(r["F1_assembled_exact"]) for r in evaluated), 4, sum(all(bool(x["F1_assembled_exact"]) for x in rs) for rs in groups.values()), 3],
        ["F2", sum(bool(r["F2_assembled_exact"]) for r in evaluated), 4, sum(all(bool(x["F2_assembled_exact"]) for x in rs) for rs in groups.values()), 3],
    ])

    L += ["", "## 6. Mandatory autopsies", ""]
    for target in ("Working Capital!C68", "Working Capital!C66", "Working Capital!J50"):
        r = next(x for x in evaluated if x["canonical_member"] == target)
        L += [f"### {target}", "", f"F0 `{r['F0_formula']}` → exact={r['F0_exact']}",
              f"F1a `{j(r['F1a_sketch'])}` → {r['F1a_class']}; F1 assembled `{r['F1_assembled_formula']}` → {r['F1_assembled_exact']}",
              f"F2a `{j(r['F2a_operand_ids'])}` → {r['F2a_class']}; F2b `{j(r['F2b_structure'])}`; F2 assembled `{r['F2_assembled_formula']}` → {r['F2_assembled_exact']}", ""]

    L += ["## 7. End-to-end translation and workbook scoring", "",
          "Each produced canonical formula was translated through the frozen ProgramGroup,",
          "written with the neutral writer, recalculated, and scored. Empty/invalid staged",
          "outputs produce a neutral no-edit workbook; no gold formula is written.", ""]
    score_rows = []
    for r in evaluated:
        for stage in ("F0", "F1", "F2"):
            s = r[f"{stage}_score"]; strict = r[f"{stage}_strict_score"]
            score_rows.append([f"{r['canonical_member']} {stage}", r[f"{stage}_all_member_exact"], s["exact"], s["modification"]["accuracy"], strict["modification"]["value_only_accuracy"], s["regression"]["accuracy"]])
    L += table(["variant", "all-member formula exact", "official exact", "official modification", "value-only modification", "regression"], score_rows)

    L += ["", "## 8. Cost and failure taxonomy", ""]
    L += table(["arm", "calls", "input tokens", "output tokens", "cost"], [[k, v["calls"], v["input_tokens"], v["output_tokens"], v["cost"]] for k, v in sorted(c.items())])
    L += ["", f"Total: {total_calls} calls, {total_in} input tokens, {total_out} output tokens, provider-reported cost ${total_cost}.", ""]
    L += table(["taxonomy", "count"], [
        ["F1 SKETCH_WRONG_OPERATOR", sum(r["F1a_class"] == "SKETCH_WRONG_OPERATOR" for r in evaluated)],
        ["F1 SKETCH_ABSTAIN", sum(r["F1a_class"] == "SKETCH_ABSTAIN" for r in evaluated)],
        ["F2 OPERANDS_WRONG", sum(r["F2a_class"] == "OPERANDS_WRONG" for r in evaluated)],
        ["F2 OPERANDS_ABSTAIN", sum(r["F2a_class"] == "OPERANDS_ABSTAIN" for r in evaluated)],
        ["F1/F2 ASSEMBLY_FAILURE", sum(bool(r["F1_assembly_error"] and r["F1_assembled_formula"] is None) or bool(r["F2_assembly_error"] and r["F2_assembled_formula"] is None) for r in evaluated)],
        ["non-model failures", sum(bool(load(p).get("failure_class") or load(p).get("truncation_class")) for p in (OUT / "calls").glob("*.json"))],
    ])

    L += ["", "## 9. Architecture verdict and direct answers", "",
          "**Verdict: `MODEL_CAPABILITY_FRONTIER`.** F0, F1, and F2 are all 0/4 cells and",
          "0/3 independent programs. The prior N3 oracle ceiling remains 4/4 over the same",
          "four cells, so the evidence does not support an entanglement-based architectural",
          "gain. The first-stage artifacts themselves are the dominant loss: no sketch was",
          "correct and no operand set was exact.", "",
          "a. No: GLM did not infer a correct structure on this population when references were forbidden.",
          "b. No: it did not infer an exact operand set when operators were forbidden.",
          "c. No observed sketch-to-binding gain; F1 produced 0/4 exact.",
          "d. No observed operand-first construction gain; F2 produced 0/4 exact.",
          "e. Neither ordering performs better: F1=F2=F0 at 0/4.",
          "f. C68 loses at F1a structure and F2a operands; neither second stage can recover it.",
          "g. C66 abstains in F1a and selects the wrong operands in F2a; it does not recover the two multiply-pairs.",
          "h. No: F2 does not reproduce J50's prior oracle reference-set effect without gold; it selects J47/J48 rather than J46/J47.",
          "i. No evaluator-correct first-stage artifact was later corrupted, so `STAGED_COMPOSITION_LOSS` is not observed.",
          "j. No staged canonical gain survives translation or workbook scoring.",
          "k. The extra calls/tokens are not justified by correctness on this diagnostic population.",
          "l. A Program Sketch IR does not earn itself.",
          "m. An Operand Binding IR does not earn itself.",
          "n. Yes, provisionally: with N3 still perfect and model-generated first-stage artifacts wrong, this probe reaches the stated novel-program capability frontier.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    text = report()
    sp.write(OUT / "STAGED_SYNTHESIS_REPORT.md", text)
    print(text)
