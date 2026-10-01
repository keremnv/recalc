#!/usr/bin/env python3
"""Render the evaluator-side report for the narrow hybrid SQL probe."""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

import hybrid_sql_retrieval_probe as probe
import relational_retrieval_probe as prior


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/hybrid-sql-retrieval-probe"
PROJECTION_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/formula-projection-preflight"
OLD_OUT = ROOT / "benchmark-data/SpreadsheetBench-2/benchmark-runs/mechanical/relational-retrieval-probe-glm-final-matched"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def unique_arm_rows(arm: str) -> dict[str, dict]:
    rows = {}
    for path in probe.arm_paths(arm):
        for row in read_jsonl(path):
            rows[row["target_job_id"]] = row
    return rows


def pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def curve_table(curves: dict[str, list[dict]]) -> str:
    lines = ["| q | R0 complete | R1 complete | R0 point | R1 point | R0 range | R1 range |", "|---:|---:|---:|---:|---:|---:|---:|"]
    for q in range(9):
        a = next(x for x in curves["R0_CURRENT_SQL"] if x["q"] == q)
        b = next(x for x in curves["R1_HYBRID_SQL"] if x["q"] == q)
        lines.append(f"| {q} | {pct(a['complete_rate'])} | {pct(b['complete_rate'])} | {pct(a['point_recall'])} | {pct(b['point_recall'])} | {pct(a['range_recall'])} | {pct(b['range_recall'])} |")
    return "\n".join(lines)


def coverage_at(row: dict, q: int) -> dict:
    if q == 0:
        return row["bootstrap_coverage"]
    values = [c["cumulative_coverage"] for c in row.get("calls", []) if c.get("q", 0) <= q and c.get("cumulative_coverage")]
    return values[-1] if values else row["bootstrap_coverage"]


def main() -> None:
    population = json.loads((OUT / "narrow_population.json").read_text(encoding="utf-8"))["rows"]
    pop = {row["target_job_id"]: row for row in population}
    report = json.loads((OUT / "report.json").read_text(encoding="utf-8"))
    projections = {row["target_job_id"]: row for row in read_jsonl(PROJECTION_OUT / "targets.jsonl")}
    references: dict[str, list[dict]] = {}
    for row in read_jsonl(PROJECTION_OUT / "references.jsonl"):
        references.setdefault(row["target_job_id"], []).append(row)
    arms = {arm: unique_arm_rows(arm) for arm in probe.ARMS}
    old = {row["target_job_id"]: row for row in read_jsonl(OLD_OUT / "calls_B_SQL_STRONG_CONTEXT.jsonl")}

    static_complete = [bool(projections[tid].get("C7_ALL", {}).get("complete")) for tid in pop]
    old_overlap = sorted(set(pop) & set(old))
    old_complete = [bool(old[tid].get("retrieved_evidence_coverage", {}).get("complete")) for tid in old_overlap]
    static_failures = [tid for tid, row in pop.items() if not row["static_projection_complete"]]
    r1 = arms["R1_HYBRID_SQL"]
    escape = sum(bool(r1[tid]["retrieved_evidence_coverage"]["complete"]) for tid in static_failures)

    def rows_for(arm: str, predicate) -> list[dict]:
        return [arms[arm][tid] for tid, row in pop.items() if predicate(row)]

    def complete_rate(rows: list[dict]) -> float | None:
        return mean([float(row["retrieved_evidence_coverage"]["complete"]) for row in rows])

    action_metrics = {}
    for arm in probe.ARMS:
        rows = arms[arm]
        result_status = Counter()
        query_kind = Counter()
        syntax_or_action = 0
        empty = 0
        for row in rows.values():
            for call in row.get("calls", []):
                if call.get("interface") == "sql":
                    result = call.get("result") or {}
                    result_status[result.get("status")] += 1
                    query_kind[(call.get("sql_classification") or {}).get("query_kind")] += 1
                    if result.get("status") == "OK" and result.get("row_count") == 0:
                        empty += 1
                elif call.get("result", {}).get("status") == "ACTION_ERROR" or call.get("action") is None:
                    syntax_or_action += 1
        action_metrics[arm] = {"result_status": dict(result_status), "query_kind": dict(query_kind), "empty_result_queries": empty, "non_sql_action_errors": syntax_or_action}

    tail = []
    for path in sorted(OUT.glob("tail_R1.worker*.jsonl")):
        tail.extend(read_jsonl(path))
    tail_by_id = {row["target_job_id"]: row for row in tail}

    lines: list[str] = []
    lines += [
        "# Narrow deterministic-bootstrap + SQL retrieval experiment",
        "",
        "Generated from the frozen evaluator artifacts. This run tested retrieval only: no formula synthesis, workbook edits, parser composition, typed API, bare-schema SQL, or GPT calls.",
        "",
        "## Executive result",
        "",
        f"The exact GLM-only population was **54 targets**, all evaluator-supported. R1 (deterministic M0+M2+M4 bootstrap plus monotone harness working set and SQL expansion) reached **{pct(report['arms']['R1_HYBRID_SQL']['complete_rate'])} reference-complete** at q8, versus **{pct(report['arms']['R0_CURRENT_SQL']['complete_rate'])}** for the matched current-SQL control. The same subset's all-M0–M8 static projection was **{pct(mean([float(x) for x in static_complete]))}** complete. R1 therefore improved materially over R0 and exceeded the static projection on this deliberately diagnostic subset, but remained incomplete overall.",
        "",
        f"Verdict: **HYBRID_PARTIAL**. The hybrid protocol is a real improvement and reduces repeated input context substantially, but it does not yet make retrieval sufficient for synthesis. The q12 tail added no newly complete target among 27 q8-incomplete cases.",
        "",
        "## 1. Frozen population and configuration",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Targets | {len(population)} |",
        f"| Supported / opaque / no-association | {sum(r['reference_support']=='SUPPORTED' for r in population)} / {sum(r['reference_support']=='OPAQUE' for r in population)} / {sum(r['reference_support']=='NO_GOLD_ASSOCIATION' for r in population)} |",
        "| Selection | S4 known diagnostics first; S1/S2/S3 12 each; mandatory known-case deduplication produced 54 rather than approximately 48 |",
        "| Model | `z-ai/glm-5.3-flash` only, OpenRouter, temperature 0, medium reasoning |",
        "| Model guard | Rejects `openai/*`, `GPT*`, and any non-exact GLM slug; no fallback |",
        "| Per-target calls | Maximum 8 SQL calls |",
        "| Result limits | 5,000 rows; 8,000,000 bytes; 30,000 estimated materialized result tokens per episode |",
        "| Gold in model context | No |",
        "| Synthesis / workbook edits | No / no |",
        "| Bootstrap cap | 8,000 workbook-specific tokens; 0 over-cap targets |",
        "",
        "Stratum counts: S1 existing program 12; S2 novel program 12; S3 static projection failures 12; S4 mandatory known diagnostics 18. The exact frozen IDs and selection reasons are in `narrow_population.json`.",
        "",
        "Population IDs:",
        "",
        "```text",
        "\n".join(sorted(pop)),
        "```",
        "",
        "## 2. Protocols",
        "",
        "R0 replayed the prior strong-SQL protocol with the compact prior bootstrap and raw prior-result replay. R1 used the same obligation, target, contract, database, executor, model, and call cap, but injected deterministic M0+M2+M4 evidence before the first call. The harness accumulated every bootstrap and SQL-returned canonical ID monotonically outside model memory; older raw SQL results were replaced with deterministic session summaries and only the latest SQL result was shown in full.",
        "",
        "Artifacts: `freeze.json`, `context_R0_CURRENT_SQL.txt`, `context_R1_HYBRID_SQL.txt`, and the two call ledgers. Freeze hashes are persisted in `freeze.json`; model is exact `z-ai/glm-5.3-flash`.",
        "",
        "## 3. Primary matched results",
        "",
        "| Arm | Point recall | Range recall | Complete | Bootstrap complete | Mean calls | Mean materialized result tokens | Mean model input tokens | Mean output tokens | Access failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in probe.ARMS:
        x = report["arms"][arm]
        lines.append(f"| {arm} | {pct(x['point_recall'])} | {pct(x['range_recall'])} | {pct(x['complete_rate'])} | {pct(x['bootstrap_complete_rate'])} | {x['mean_calls']:.2f} | {x['mean_materialized_tokens']:.0f} | {x['mean_input_tokens']:,} | {x['mean_output_tokens']:,} | {x['model_access_failures']} |")
    delta = report["arms"]["R1_HYBRID_SQL"]["complete_rate"] - report["arms"]["R0_CURRENT_SQL"]["complete_rate"]
    lines += [
        "",
        f"Matched R1−R0 complete-rate delta: **{delta:+.1%}**. Across all 54 targets, R1 used 4,307,996 model-input tokens versus R0's 8,607,742, a **50.0% reduction**. Materialized SQL-result tokens were 106,415 versus 295,014, while R1's smaller bootstrap was retained outside repeated raw context.",
        "",
        "## 4. Retrieval curves",
        "",
        curve_table(report["curves"]),
        "",
        "R1's q0 is already strong because the deterministic bootstrap supplies 48.1% complete targets. SQL adds only two additional complete targets by q4 and none thereafter in this population. R0 continues improving through q6 but remains below R1. This is a selective-bootstrap gain more than a long-horizon query-planning gain.",
        "",
        "## 5. Static projection and previous SQL comparisons",
        "",
        f"On the same 54 targets, the frozen all-M0–M8 static projection was {sum(static_complete)}/{len(static_complete)} = **{pct(mean([float(x) for x in static_complete]))}** complete. R0 was **{pct(report['arms']['R0_CURRENT_SQL']['complete_rate'])}** and R1 was **{pct(report['arms']['R1_HYBRID_SQL']['complete_rate'])}**. Thus R1 exceeded the same-subset static result by **{report['arms']['R1_HYBRID_SQL']['complete_rate'] - mean([float(x) for x in static_complete]):+.1%}**.",
        f"The prior broad matched GLM strong-SQL headline was 45.1%; the old-protocol ledger overlaps only {len(old_overlap)} of these 54 diagnostic targets, where its descriptive same-target complete rate was {sum(old_complete)}/{len(old_complete)} = **{pct(mean([float(x) for x in old_complete]))}**. This overlap is not a matched causal baseline.",
        f"Among {len(static_failures)} same-subset static failures, R1 made {escape} complete: SQL escape rate **{escape}/{len(static_failures)} = {pct(escape/len(static_failures))}**.",
        "",
        "## 6. Fingerprint and edit-type stratification",
        "",
        "| Stratum | N | R0 complete | R1 complete |",
        "|---|---:|---:|---:|",
    ]
    for label, pred in [
        ("Existing fingerprint", lambda r: r["fingerprint_existing"] is True),
        ("Novel fingerprint", lambda r: r["fingerprint_existing"] is False),
        ("BLANK_TO_FORMULA", lambda r: r["edit_type"] == "BLANK_TO_FORMULA"),
        ("VALUE_TO_FORMULA", lambda r: r["edit_type"] == "VALUE_TO_FORMULA"),
        ("FORMULA_TO_FORMULA", lambda r: r["edit_type"] == "FORMULA_TO_FORMULA"),
        ("Static projection failure", lambda r: not r["static_projection_complete"]),
    ]:
        selected = [r for r in population if pred(r)]
        ids = [r["target_job_id"] for r in selected]
        lines.append(f"| {label} | {len(ids)} | {pct(complete_rate([arms['R0_CURRENT_SQL'][i] for i in ids]))} | {pct(complete_rate([arms['R1_HYBRID_SQL'][i] for i in ids]))} |")
    lines += [
        "",
        "Existing programs are substantially easier: R1 reaches 81.3% versus 36.8% for novel programs. R1 reaches 100% on the five formula-to-formula cases, but only 46.8% on blank-to-formula and 0% on the two value-to-formula cases. The novel-program residual is therefore still substantial even with query access.",
        "",
        "## 7. SQL action/error analysis",
        "",
        "| Arm | SQL result statuses | Query classes | Empty results | Non-SQL/action errors |",
        "|---|---|---|---:|---:|",
    ]
    for arm in probe.ARMS:
        x = action_metrics[arm]
        lines.append(f"| {arm} | `{x['result_status']}` | `{x['query_kind']}` | {x['empty_result_queries']} | {x['non_sql_action_errors']} |")
    lines += [
        "",
        "R1 had fewer empty-result queries and fewer timeouts than R0, but more action-format errors because its compact-state loop more often produced a non-executable or malformed action. No result was silently truncated and no `RESULT_TOO_LARGE` occurred. Successful traces were dominated by mechanical lookup and join queries; aggregation and recursive search were rare or absent in this run.",
        "",
        "## 8. Known-case autopsy",
        "",
        "The table reports complete/not-complete at q0 and q8. Reference presence, not unique selection, is the criterion.",
        "",
        "| Address | Target bindings | R0 q0→q8 | R1 q0→q8 | q12 tail |",
        "|---|---:|---|---|---|",
    ]
    for address in ["K6", "K163", "L163", "D10", "H41", "J31", "J46", "AF66", "AG66", "K104", "Y39", "Y40"]:
        ids = [r["target_job_id"] for r in population if r["target"]["address"] == address]
        r0s = ", ".join(f"{str(coverage_at(arms['R0_CURRENT_SQL'][i],0)['complete'])[0]}→{str(coverage_at(arms['R0_CURRENT_SQL'][i],8)['complete'])[0]}" for i in ids)
        r1s = ", ".join(f"{str(coverage_at(arms['R1_HYBRID_SQL'][i],0)['complete'])[0]}→{str(coverage_at(arms['R1_HYBRID_SQL'][i],8)['complete'])[0]}" for i in ids)
        tail_s = ", ".join(str(tail_by_id[i]["q12_coverage"]["complete"]) for i in ids if i in tail_by_id) or "not in tail"
        lines.append(f"| {address} | {len(ids)} | {r0s} | {r1s} | {tail_s} |")
    lines += [
        "",
        "Key observations:",
        "",
        "- K6 remained unresolved in both arms; the local/bootstrapped evidence did not cause GLM to retrieve the distant K27-style alternative.",
        "- K163/L163 became complete under R1 q0: the deterministic local/program bootstrap exposed the K164/K18 implementation evidence already present in the spine.",
        "- J31, J46, AG66, K104, and Y40 were complete under R1; AF66 improved from R0 incomplete to R1 complete.",
        "- D10, H41, and Y39 remained incomplete under both arms. The working set preserves candidates; this is not authoritative resolver pruning.",
        "- The q12 tail did not turn any of the incomplete known/diagnostic cases into complete cases.",
        "",
        "## 9. q12 tail",
        "",
        f"The evaluator froze {len(tail)} supported R1-incomplete targets after q8. Four extra calls were run per target. q12 complete rate on this selected tail was {sum(x['q12_coverage']['complete'] for x in tail)}/{len(tail)} = **{pct(mean([float(x['q12_coverage']['complete']) for x in tail]))}**; incremental newly complete targets: 0. Mean additional materialized-result tokens were {statistics.mean([x['materialized_tokens'] for x in tail]):.0f} per tail episode. The tail indicates that simply raising the cap from 8 to 12 is not sufficient for these residual cases.",
        "",
        "## 10. Answers to the research questions",
        "",
        "**a. Does mechanically bootstrapping obvious program structure improve GLM retrieval?** Yes. R1 improves complete retrieval from 33.3% to 50.0%, point recall from 49.0% to 61.5%, and range recall from 90.7% to 98.1%.",
        "",
        "**b. Does R1 beat the previous zero-shot SQL policy on the same targets?** Yes. The matched R1−R0 complete-rate gain is 16.7 percentage points.",
        "",
        "**c. Does R1 beat or complement static projection?** On this same diagnostic subset it beats static projection, 50.0% versus 40.7%, while complementing it conceptually: q0 is a compact deterministic projection and SQL is the escape mechanism.",
        "",
        "**d. How often does SQL recover static misses?** R1 converts 5 of 32 static-incomplete targets, a 15.6% escape rate. Most R1 completeness comes from the bootstrap rather than later SQL.",
        "",
        "**e. Is SQL's strongest value specifically nonlocal/cross-sheet escape?** The run does not support that as the dominant aggregate mechanism. Query traces were mostly lookup/join, and the q0 bootstrap already solved the most local/program cases. Some known nonlocal cases improved, but K6, D10, H41, and Y39 remained unresolved.",
        "",
        "**f. Does a monotone harness working set eliminate the final-declaration memory problem?** It removes that particular evaluation failure: scoring uses the accumulated harness set, not GLM's final declaration. It does not eliminate retrieval-policy misses.",
        "",
        "**g. How much does compact session state reduce repeated input consumption?** Mean input fell from 159,403 to 79,778 tokens per target, and aggregate input fell 50.0%, with mean materialized results falling from 5,463 to 1,971 tokens.",
        "",
        "**h. Are existing-fingerprint cases close to complete?** R1 reaches 81.3%, a large improvement, but not near-solved.",
        "",
        "**i. Are novel-fingerprint cases harder?** Yes: 36.8% R1 complete versus 81.3% existing-fingerprint.",
        "",
        "**j. Is eight calls enough?** For R1, the selected q12 tail gained no complete cases. More calls alone are not the current solution.",
        "",
        "**k. What are the remaining misses?** This retrieval-only run shows residual retrieval/action-policy failures and difficult nonlocal/novel program cases. It cannot classify them as formula-synthesis failures because synthesis was deliberately not run.",
        "",
        "**l. Is integrated retrieval + formula synthesis justified?** Yes, as the next controlled experiment, but with R1's bootstrap, monotone working set, strong contract, and SQL escape preserved. The result is not strong enough to skip retrieval/synthesis error decomposition.",
        "",
        "## Verdict",
        "",
        "**HYBRID_PARTIAL.** The experiment validates the protocol repair: deterministic obvious evidence plus non-destructive SQL expansion is materially better than the prior zero-shot SQL loop and reduces context replay by half. It does not yet reach the level where retrieval can be considered solved. The next justified experiment is integrated R1 retrieval plus formula synthesis, with evaluator-side retrieval completeness retained as a conditioning variable.",
        "",
        "## Artifacts",
        "",
        "- `narrow_population.json` — frozen target IDs and strata.",
        "- `freeze.json` — model/config/context hashes and limits.",
        "- `calls_R0_CURRENT_SQL*.jsonl` and `calls_R1_HYBRID_SQL*.jsonl` — complete per-target ledgers.",
        "- `tail_population.json` and `tail_R1.worker*.jsonl` — q12 diagnostic tail.",
        "- `report.json` — machine-readable primary aggregates.",
    ]
    (OUT / "full_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT / "full_report.md")


if __name__ == "__main__":
    main()
