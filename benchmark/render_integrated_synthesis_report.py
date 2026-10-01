#!/usr/bin/env python3
"""Render the integrated retrieval+synthesis architecture-review report."""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/integrated-hybrid-synthesis-probe"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def pct(value):
    return "—" if value is None else f"{100 * value:.1f}%"


def main() -> None:
    report = load("report.json")
    scored = load("scored.json")["rows"]
    pop = load("synthesis_population.json")
    episodes = []
    for path in sorted(OUT.glob("episodes.worker*.jsonl")):
        episodes.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    episode_by_id = {row["target_job_id"]: row for row in episodes}
    lines = [
        "# Integrated Architecture v1.1 retrieval + formula-synthesis probe",
        "",
        "This diagnostic run used one fresh frozen R1 retrieval session followed by one formula proposal. It did not run the task parser, edit workbooks, run a benchmark submission, use GPT, use the typed API, use bare-schema SQL, or perform verifier-driven repair.",
        "",
        "## Executive result",
        "",
        "GLM 5.3 Flash synthesized **9/30 formulas correctly (30.0%)**. On evaluator-side retrieval-complete cases, it synthesized **9/18 correctly (50.0%)**; on retrieval-incomplete cases, it synthesized **0/12 correctly (0.0%)**. This is strong evidence that retrieval completeness is a dominant bottleneck, but it also shows a substantial residual synthesis problem: even when all supported gold references were in the working set, half the cases failed.",
        "",
        "Existing programs were much easier than novel programs: **7/12 (58.3%)** versus **2/18 (11.1%)**. Among retrieval-complete cases the split was **7/9 (77.8%)** existing versus **2/9 (22.2%)** novel. The result supports an explicit program-recovery/program-synthesis split.",
        "",
        "Verdict: **PROGRAM_RECOVERY_SUPPORTED + RETRIEVAL_DOMINANT, with residual MODEL_LIMITED behavior on complete/novel cases.** A small end-to-end composition is justified, but the architecture should preserve retrieval-completeness conditioning and should not treat synthesis as solved.",
        "",
        "## 1. Frozen population",
        "",
        "| Group | Definition | N | Correct |",
        "|---|---|---:|---:|",
        f"| G1 | Retrieval complete + existing fingerprint | 9 | {sum(x['formula_correct'] for x in scored if x['retrieval_group']=='G1_RETRIEVAL_COMPLETE_EXISTING')}/9 |",
        f"| G2 | Retrieval complete + novel fingerprint | 9 | {sum(x['formula_correct'] for x in scored if x['retrieval_group']=='G2_RETRIEVAL_COMPLETE_NOVEL')}/9 |",
        f"| G3 | Retrieval incomplete + existing fingerprint | 3 eligible | {sum(x['formula_correct'] for x in scored if x['retrieval_group']=='G3_RETRIEVAL_INCOMPLETE_EXISTING')}/3 |",
        f"| G4 | Retrieval incomplete + novel fingerprint | 9 | {sum(x['formula_correct'] for x in scored if x['retrieval_group']=='G4_RETRIEVAL_INCOMPLETE_NOVEL')}/9 |",
        "",
        "G3 had only three eligible targets in the frozen 54-target R1 population; it was not padded with ineligible cases. The exact frozen population and selection reasons are in `synthesis_population.json`.",
        "",
        "Known cases included: K6, K163, L163, D10, H41, J31, J46, AF66, AG66, K104, Y39, Y40, each at the eligible frozen obligation/target binding.",
        "",
        "## 2. Configuration and protocol",
        "",
        "| Item | Frozen value |",
        "|---|---|",
        "| Model | `z-ai/glm-5.3-flash` / GLM 5.3 Flash only |",
        "| Temperature | 0 |",
        "| Reasoning | medium |",
        "| Retrieval | Architecture v1.1 R1; M0+M2+M4 bootstrap; strong SQL context; max 8 SQL calls |",
        "| Working set | Harness-managed monotone union of bootstrap and SQL-returned IDs |",
        "| Synthesis | Same integrated episode; exactly one proposal call |",
        "| Gold in model context | No |",
        "| Retry/repair | None |",
        "| Workbook edits | None |",
        "| Model access failures | 0/30 |",
        "| Scorer-equivalent | Not run; no safe isolated single-cell scorer invoked |",
        "",
        "The exact model guard rejects `openai/*`, `GPT*`, and every model other than the exact GLM slug. Frozen system and transition hashes are in `freeze.json`.",
        "",
        "## 3. Conditional synthesis matrix",
        "",
        "| | Existing fingerprint | Novel fingerprint |",
        "|---|---:|---:|",
        "| Retrieval complete | 7/9 = 77.8% | 2/9 = 22.2% |",
        "| Retrieval incomplete | 0/3 = 0.0% | 0/9 = 0.0% |",
        "",
        "Overall:",
        "",
        "- Retrieval complete: 9/18 = 50.0%.",
        "- Retrieval incomplete: 0/12 = 0.0%.",
        "- Existing fingerprint: 7/12 = 58.3%.",
        "- Novel fingerprint: 2/18 = 11.1%.",
        "- Exact formula match: 9/30 = 30.0%.",
        "- Gold fingerprint match: 9/30 = 30.0%.",
        "",
        "All accepted formulas were exact matches in this population; no syntax-only or alternate-fingerprint acceptance was needed.",
        "",
        "## 4. Evidence source and retrieval completeness",
        "",
        "| Evidence class | N | Correct | Mean gold-reference recall in proposal |",
        "|---|---:|---:|---:|",
        f"| Bootstrap-complete | 18 | {sum(x['formula_correct'] for x in scored if x['bootstrap_complete'])}/18 | {pct(report['by_evidence_source']['BOOTSTRAP_COMPLETE']['mean_gold_reference_recall'])} |",
        f"| SQL-completed after q0 | 0 | — | — |",
        f"| Still incomplete at q8 | 12 | {sum(x['formula_correct'] for x in scored if x['still_incomplete'])}/12 | {pct(report['by_evidence_source']['STILL_INCOMPLETE']['mean_gold_reference_recall'])} |",
        "",
        "No selected target belonged to the SQL-completed-after-q0 category; therefore this experiment cannot estimate synthesis accuracy for that mechanism separately. The selected complete cases were all already complete at deterministic q0.",
        "",
        "The integrated harness itself preserved evidence correctly. The zero success rate for incomplete retrieval is not evidence that the model cannot ever use equivalent evidence; it is the observed result on this diagnostic set, with no incomplete-but-correct exceptions to inspect.",
        "",
        "## 5. Failure taxonomy",
        "",
        "| Failure tag | Count |",
        "|---|---:|",
    ]
    for tag, count in sorted(report["failure_taxonomy"].items()):
        lines.append(f"| {tag} | {count} |")
    lines += [
        "",
        "The dominant proposal errors were wrong operator and wrong source selection. Six proposals were wrong-source tagged and eight wrong-operator tagged; tags may overlap. There were four invalid entity-reference outputs, six abstentions, and five invalid synthesis-output objects. No proposal was rejected by the hard verifier.",
        "",
        "The invalid entity-reference cases are distinct from invalid workbook formulas: the formula can be parseable while the model declares an evidence/relation ID that was not in the accumulated working set. This is a protocol-output failure, not a workbook-reference parser failure.",
        "",
        "## 6. Hard-verifier interaction",
        "",
        "The existing sparse hard verifier was run on all 19 parseable formula proposals. Results: **0/19 HARD_REJECT**, **19/19 HARD_ACCEPT**. All nine correct proposals were accepted, but all ten incorrect formula proposals were also accepted. Abstentions and invalid synthesis-output objects had no formula to verify. Therefore the verifier had zero rejection power on this sample: it did not reject useful correct proposals, but it also did not catch a meaningful subset of synthesis errors. The failures were semantic/source/operator choices outside the verifier's hard-cycle/reference-safety scope.",
        "",
        "## 7. Token/context accounting",
        "",
        "| Metric | Mean | P95 | Max |",
        "|---|---:|---:|---:|",
    ]
    for key, label in [
        ("bootstrap_tokens", "Bootstrap tokens"),
        ("materialized_result_tokens", "SQL result tokens"),
        ("session_summary_tokens", "Session-summary tokens"),
        ("retrieval_input_tokens", "Retrieval input tokens"),
        ("synthesis_transition_input_estimate", "Synthesis transition/evidence estimate"),
        ("total_input_tokens", "Total model input tokens"),
    ]:
        values = sorted((episode_by_id[x["target_job_id"]].get(key) or 0) for x in scored)
        lines.append(f"| {label} | {statistics.mean(values):,.0f} | {values[int(.95*len(values))-1]:,.0f} | {max(values):,} |")
    lines += [
        "",
        f"The integrated run used {sum(x.get('total_input_tokens', 0) for x in episodes):,} total input tokens and {sum(x.get('total_output_tokens', 0) for x in episodes):,} output tokens across {sum(len(x.get('retrieval_calls', [])) + 1 for x in episodes)} model calls. The integrated synthesis transition adds substantial context: mean total input was about 130.9k tokens, compared with about 79.8k mean input in retrieval-only R1. The compact lossless representation prevented the largest selected evidence packet from exceeding the observed context envelope, but integration is not free.",
        "",
        "## 8. Known-case autopsy",
        "",
        "| Case | Retrieval | Proposal | Gold | Result |",
        "|---|---|---|---|---|",
    ]
    known_addresses = ["K6", "K163", "L163", "D10", "H41", "J31", "J46", "AF66", "AG66", "K104", "Y39", "Y40"]
    for address in known_addresses:
        rows = [x for x in scored if x["target"]["address"] == address]
        for row in rows:
            proposal = row["formula"] or row["formula_status"]
            lines.append(f"| {address} ({row['task']} {row['obligation_id']}) | {'complete' if row['retrieval_complete_q8'] else 'incomplete'} / q0={'complete' if row['retrieval_q0_complete'] else 'incomplete'} | `{proposal}` | `{row['gold_formula']}` | {'CORRECT' if row['formula_correct'] else ', '.join(row['failure_tags'])} |")
    lines += [
        "",
        "Interpretation of the cleanest cases:",
        "",
        "- K163 retrieval was complete at q0, but GLM abstained; L163 retrieved the same non-cyclic program structure and was synthesized correctly as `=L164*L18`. This is direct evidence that evidence presence is necessary but not sufficient.",
        "- J31, K104, AF66, AG66, J46, and Y40 had complete retrieval. J31, K104, AF66, and AG66 produced the correct formula; J46 and Y40 abstained. AG66's formula was correct, but its declared evidence included an invalid relation ID, so output-contract validity remains separate from formula correctness.",
        "- K6, D10, H41, and Y39 remained retrieval-incomplete. Their wrong/abstaining proposals cannot be cleanly attributed to synthesis rather than missing evidence.",
        "- H41 chose `=H42*'Income Statement'!H8/30` instead of the gold `=H42*-'Income Statement'!H30/30`; this is a complete-looking source/operator failure, but retrieval was incomplete for the gold source.",
        "",
        "## 9. Per-target proposals",
        "",
        "| Target | Group | Retrieval | Proposal | Correct | Tags |",
        "|---|---|---|---|---:|---|",
    ]
    for row in sorted(scored, key=lambda x: x["target_job_id"]):
        formula = row["formula"] or row["formula_status"]
        lines.append(f"| `{row['target']['address']}` ({row['task']}) | {row['retrieval_group'].replace('_',' ')} | {'complete' if row['retrieval_complete_q8'] else 'incomplete'} | `{formula}` | {'yes' if row['formula_correct'] else 'no'} | {', '.join(row['failure_tags']) or '—'} |")
    lines += [
        "",
        "## 10. Direct answers",
        "",
        "**a. When all supported golden references are present, how often is the formula correct?** 9/18 = 50.0%.",
        "",
        "**b. How much worse when retrieval is incomplete?** 0/12 = 0.0%, a 50-point conditional gap on this diagnostic set.",
        "",
        "**c. Is retrieval completeness a dominant bottleneck?** Yes. The complete/incomplete split is stark, but complete cases still fail 50% of the time.",
        "",
        "**d/e. Are existing programs easier and can GLM translate them?** Yes. Existing complete cases were 77.8% correct; novel complete cases were 22.2%. L163, J31, K104, AF66, AG66, and several same-program cases demonstrate successful binding, but K163 and Y40 show that existing evidence does not guarantee execution.",
        "",
        "**f. What dominates complete-case failures?** Wrong operator and source binding, with some abstention and invalid evidence IDs. No hard-verifier rejection occurred.",
        "",
        "**g. Did incomplete-but-correct formulas show the metric was too strict?** No. There were zero correct formulas in the incomplete stratum, so this run provides no evidence that the reference-completeness metric is too strict.",
        "",
        "**h. SQL-completed versus bootstrap-complete?** No SQL-completed targets were selected; this comparison remains unmeasured here.",
        "",
        "**i. Did the hard verifier catch useful wrong proposals?** No. It accepted all 19 parseable proposals, including all ten wrong formulas; it rejected no correct proposal either.",
        "",
        "**j. Which prior ORACLE_WHERE cases improved?** L163, J31, K104, AF66, and AG66 were solved; K163, J46, Y40, K6, D10, H41, and Y39 were not fully solved.",
        "",
        "**k. Is integrated context efficient?** It is workable but expensive: mean total input was about 130.9k tokens, with a maximum of 388.7k in provider accounting. Compact evidence avoids raw 140k-token entity serialization, but synthesis roughly doubles retrieval-only input context.",
        "",
        "**l. What next?** Proceed to a small end-to-end composition only with the R1 protocol and evaluator conditioning retained. At the same time, treat novel-program synthesis as a separate model-capability diagnosis; do not add more retrieval machinery based only on the complete/novel failures.",
        "",
        "## Verdict",
        "",
        "**PROGRAM_RECOVERY_SUPPORTED + RETRIEVAL_DOMINANT, with a residual MODEL_LIMITED novel-synthesis problem.** Architecture v1.1 delivers enough evidence for strong performance on many existing-program, retrieval-complete cases, but exact evidence presence does not make formula synthesis reliable. Retrieval incompleteness is a clear causal bottleneck; beyond it, novel program composition, operator choice, abstention, and evidence-ID discipline remain unresolved.",
        "",
        "## Artifacts",
        "",
        "- `synthesis_population.json` — frozen 30-target population and four strata.",
        "- `freeze.json`, `retrieval_system.txt`, `synthesis_transition.txt` — frozen configuration and hashes.",
        "- `episodes.worker*.jsonl` — integrated retrieval and one-shot synthesis ledgers.",
        "- `scored.json` — evaluator-side formula/reference/verifier results.",
        "- `report.json` — machine-readable aggregate metrics.",
    ]
    (OUT / "full_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT / "full_report.md")


if __name__ == "__main__":
    main()
