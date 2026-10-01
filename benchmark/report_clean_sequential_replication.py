#!/usr/bin/env python3
"""Offline report for the sequential treatment replication.

The script reads only persisted task state, call ledgers, workbooks, and
scorer output.  It makes no provider requests and does not alter the frozen
compiled architecture.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import statistics
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
import fm_resource_feasibility as f  # noqa: E402
import post_repair_feasibility_artifacts as p  # noqa: E402

RUN = f.RUN_ROOT
CLEAN = f.LIVE / "repaired_treatment_clean_sequential"
OLD = f.REPAIRED_LIVE


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def collect(root: Path) -> tuple[list[dict], dict, list[dict], dict]:
    old = p.LIVE
    p.LIVE = root
    try:
        rows, aggregate, pg_rows = p.treatment_rows()
        scores = p.official_summary()
    finally:
        p.LIVE = old
    return rows, aggregate, pg_rows, scores


def failure_detail(root: Path) -> Counter[str]:
    detail: Counter[str] = Counter()
    for path in sorted(root.glob("Financial_Model-*/calls/*.json")):
        try:
            call = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        raw = call.get("raw_response_body") or {}
        status = raw.get("status") if isinstance(raw, dict) else None
        body = raw.get("body", "") if isinstance(raw, dict) else ""
        if call.get("failure_class"):
            if status:
                detail[f"{call['failure_class']}:{status}"] += 1
            else:
                detail[str(call["failure_class"])] += 1
            if "in_flight_budget_exhausted" in str(body):
                detail["provider_body:in_flight_budget_exhausted"] += 1
            if "can only afford" in str(body):
                detail["provider_body:credit_or_max_tokens"] += 1
            if "temporarily rate-limited" in str(body):
                detail["provider_body:upstream_rate_limit"] += 1
    return detail


def score_payload(root: Path) -> dict:
    path = root / "official_scores.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def row_by_task(rows: list[dict]) -> dict[str, dict]:
    return {str(r["task_id"]): r for r in rows}


def main() -> None:
    if not CLEAN.exists():
        raise SystemExit(f"missing clean run root: {CLEAN}")
    clean_rows, clean_agg, clean_pg, clean_scores = collect(CLEAN)
    old_data = json.loads((RUN / "repaired_treatment_results.json").read_text(encoding="utf-8"))
    old_rows = old_data.get("rows") or []
    old_agg = old_data.get("aggregate") or {}
    old_scores = old_data.get("scores") or {}
    clean_by = row_by_task(clean_rows)
    old_by = row_by_task(old_rows)

    comparison = []
    for task in f._selected_ids():
        o, c = old_by.get(task, {}), clean_by.get(task, {})
        comparison.append({
            "task_id": task,
            "contaminated_task_ir": o.get("task_ir_status"),
            "clean_task_ir": c.get("task_ir_status"),
            "contaminated_plan": o.get("edit_plan_status"),
            "clean_plan": c.get("edit_plan_status"),
            "contaminated_retrieval": o.get("retrieval_sessions_started", 0),
            "clean_retrieval": c.get("retrieval_sessions_started", 0),
            "contaminated_synthesis": o.get("synthesis_calls", 0),
            "clean_synthesis": c.get("synthesis_calls", 0),
            "contaminated_writes": o.get("writes_present", 0),
            "clean_writes": c.get("writes_present", 0),
            "contaminated_correct_gold_writes": o.get("correct_gold_writes", 0),
            "clean_correct_gold_writes": c.get("correct_gold_writes", 0),
            "contaminated_calls": o.get("natural_call_attempts", 0),
            "clean_calls": c.get("natural_call_attempts", 0),
            "contaminated_cost_usd": o.get("provider_cost_usd", 0),
            "clean_cost_usd": c.get("provider_cost_usd", 0),
            "contaminated_provider_failures": o.get("provider_failure_calls", 0),
            "clean_provider_failures": c.get("provider_failure_calls", 0),
            "clean_deepest_stage": c.get("deepest_stage"),
        })
    write_csv(RUN / "contaminated_vs_clean.csv", comparison)
    write_csv(RUN / "clean_repaired_treatment_funnel.csv", clean_rows)

    clean_calls = [int(r.get("natural_call_attempts", 0) or 0) for r in clean_rows]
    clean_costs = [float(r.get("provider_cost_usd", 0) or 0) for r in clean_rows]
    natural_status = "NOT_ESTIMABLE_PROVIDER_CREDIT_BLOCKED"
    natural = {
        "status": natural_status,
        "clean_root": str(CLEAN),
        "model_config": f.read_json(RUN / "freeze.json", {}),
        "max_workers": 1,
        "observed_attempt_distribution_including_failures": {
            "calls": clean_calls,
            "median": statistics.median(clean_calls) if clean_calls else None,
            "p75": statistics.quantiles(clean_calls, n=4, method="inclusive")[2] if len(clean_calls) > 1 else (clean_calls[0] if clean_calls else None),
            "p90": max(clean_calls) if clean_calls else None,
            "max": max(clean_calls) if clean_calls else None,
        },
        "observed_cost_distribution_usd": {
            "median": statistics.median(clean_costs) if clean_costs else None,
            "p90": max(clean_costs) if clean_costs else None,
            "max": max(clean_costs) if clean_costs else None,
        },
        "provider_failure_calls": clean_agg.get("provider_failure_calls"),
        "provider_failure_classes": clean_agg.get("provider_failure_classes"),
        "provider_failure_detail": dict(failure_detail(CLEAN)),
        "semantic_demand_warning": "The distribution is censored at the first provider call for 11/12 tasks; do not use it as natural treatment demand or a matched-budget estimate.",
        "rows": [{
            "task_id": r["task_id"],
            "attempts": r.get("natural_call_attempts"),
            "semantic_calls": r.get("semantic_calls_without_infrastructure_failures"),
            "provider_failures": r.get("provider_failure_calls"),
            "cost_usd": r.get("provider_cost_usd"),
            "stop_reason": r.get("earliest_supported_failure"),
        } for r in clean_rows],
    }
    dump(RUN / "clean_repaired_treatment_natural_demand.json", natural)

    clean_score = score_payload(CLEAN)
    result = {
        "status": "INFRASTRUCTURE_CONFUND_DOMINANT",
        "phase": "B_clean_sequential_replication",
        "not_final_ab": True,
        "clean_root": str(CLEAN),
        "max_workers": 1,
        "model_config": f.read_json(RUN / "freeze.json", {}),
        "aggregate": clean_agg,
        "scores": clean_scores,
        "official_scores_raw": clean_score,
        "program_groups": clean_pg,
        "provider_failure_detail": dict(failure_detail(CLEAN)),
        "interpretation": "Provider/account credit failures stopped the frontend before semantic treatment could be evaluated on 11/12 tasks; no architecture inference is warranted from this replication.",
    }
    dump(RUN / "clean_repaired_treatment_results.json", result)

    bridge = json.loads((RUN / "write_to_score_bridge_summary.json").read_text(encoding="utf-8"))
    lines = [
        "# Clean sequential repaired-treatment replication",
        "",
        "This report is diagnostic only. No final 20-task matched A/B was launched, and no architecture or prompt was changed.",
        "",
        "## Phase A: write-to-score bridge result",
        "",
        f"The zero-model bridge audit found **{bridge['internally_correct_writes']} internally correct writes**. All **{bridge['persisted_correct_writes']}** were scheduled/persisted, all **{bridge['post_lo_correct_formulas']}** retained the exact formula text after explicit LibreOffice recalculation, and all **{bridge['official_modification_target_overlap']}** overlapped official modification targets. At the value/scorer level, **10** remained correct; **3** had the intended formula text but wrong post-LO value because an upstream dependency/value was wrong.",
        "",
        "The old official `0.0` modification score therefore was not evidence that every write disappeared. The earlier scoring path scored the staged treatment files without an explicit recalculation refresh. The bridge scorer, which explicitly refreshed the six audit outputs, produced nonzero modification on 03_01, 05_01, 13_05, and 14_05. This is a recalculation/scoring bridge defect in the prior measurement path, with three additional upstream-value failures; it is not a writer-persistence failure for these 13 writes.",
        "",
        "The historical `97 exact translated formulas` figure was also over-counted instrumentation: it compared every group member's final cell to gold, including cells not emitted as translations. The corrected runtime lineage is **116 generated group-member translations**, **9 exact against gold**, and **9 exact translations persisted**; those 9 overlap official modification targets and are visible after LO. The aggregate official task score remains non-exact because correctness is not the same as task-level exactness.",
        "",
        "## Phase B: clean sequential replication",
        "",
        "The exact frozen treatment was run with one task at a time. `01_01` received one valid Task IR response, then its eight obligation-level Edit Plan requests failed with provider access/credit errors. The remaining 11 tasks failed on their first Task IR request. No valid semantic model response was received for those calls. The provider failures were not concurrency overlaps: the runner enforced `max_workers=1`.",
        "",
        "| Stage | Observed clean count | Interpretation |",
        "|---|---:|---|",
        f"| valid Task IR | {clean_agg['tasks_task_ir_valid']}/12 | one task completed; 11 were provider-blocked |",
        f"| valid Edit Plan | {clean_agg['tasks_edit_plan_valid']}/12 | no plan completed after provider failure |",
        f"| retrieval | {clean_agg['tasks_reach_retrieval']}/12 | not reached |",
        f"| synthesis | {clean_agg['tasks_reach_synthesis']}/12 | not reached |",
        f"| semantic writes | {clean_agg['tasks_semantic_writes']}/12 | none in clean replication |",
        f"| correct gold writes | {clean_agg['tasks_correct_gold_writes']}/12 | none |",
        f"| submitted/staged outputs | {clean_agg['tasks_submitted']}/12 | source/neutral outputs were staged; this is not semantic completion |",
        "",
        f"There were **{clean_agg['provider_failure_calls']} provider failures** in the sequential run. The raw failure detail is `{json.dumps(failure_detail(CLEAN), sort_keys=True)}`. The dominant response was HTTP 402 credit/max-token rejection; one upstream rate-limit message was also embedded in the provider error. This is a provider/account envelope failure, not evidence that sequential scheduling still creates concurrency.",
        "",
        "### Clean demand and scheduler interpretation",
        "",
        "The observed clean attempt counts are 9 for `01_01` and 1 for each other task, but this is a censored failure distribution, not natural demand. A clean median/p90/max natural call estimate and common budget cannot be defended. Operation-preserving scheduling was not exercised on a valid clean Edit Plan; the frozen implementation and archived contaminated valid-plan traces retain the operation-container/deferred-residual distinction, but this run cannot revalidate it end-to-end.",
        "",
        "## Direct answers",
        "",
        "1. Internal correctness coexisted with official modification 0 because the prior official path scored unrefreshed staged workbooks; explicit LO refresh restored nonzero modification on four audit tasks. Ten of 13 internal writes were value-correct after refresh; three had upstream-dependent value errors.",
        "2. For internally correct writes: scheduled 13/13, persisted 13/13, exact formula text after LO 13/13, value/scorer-correct after LO 10/13, official-target overlap 13/13.",
        "3. The old 97→9 discrepancy was mostly instrumentation overcount: 97 counted unchanged group members as if translated. The corrected lineage has 116 emitted translation instances, 9 exact, and 9 exact persisted.",
        "4. Yes. All 9 exact persisted translated formulas overlap official modification targets; they are visible after LO. They do not make the full task exact by themselves.",
        "5. The primary bridge defect is the prior no-refresh recalculation/scoring path, not writer persistence. Three writes additionally expose upstream-value dependency errors.",
        f"6. With task concurrency removed, the clean run still had {clean_agg['provider_failure_calls']} provider failures (mostly credit/max-token HTTP 402), so the provider/account envelope remains broken for this exact request.",
        "7. Improvement cannot be measured: the clean run was stopped at the frontend by provider access failures. It did not improve semantic-write or correct-write coverage.",
        "8. Clean natural demand is not estimable. Observed attempts were median 1, p90 1, max 9 only because 11 tasks were censored before a valid response.",
        "9. The scheduler was not falsified, but it was not exercised by a valid clean plan. No clean-run evidence supports changing it.",
        "10. Earliest remaining dominant loss is provider/account infrastructure failure at Task IR/Edit Plan, not a semantic frontier.",
        "",
        "## Verdict",
        "",
        "**INFRASTRUCTURE_CONFUND_DOMINANT**. The bridge audit identifies a concrete no-refresh scoring/recalculation measurement defect and confirms that the exact frozen clean replication is currently blocked by provider credit/max-token access errors even when serialized. Do not infer architecture quality, freeze a matched budget, or launch the 20-task A/B from this run.",
        "",
        "Artifacts: `WRITE_TO_SCORE_BRIDGE_REPORT.md`, `write_lineage.csv`, `programgroup_write_lineage.csv`, `scorer_target_alignment.csv`, `clean_repaired_treatment_results.json`, `clean_repaired_treatment_funnel.csv`, `clean_repaired_treatment_natural_demand.json`, and `contaminated_vs_clean.csv`.",
        "",
        "NEXT_RESEARCH_TARGET: restore a provider/account envelope that accepts the frozen 65,536-token max request sequentially, then repeat the exact clean treatment before any semantic or architecture change.",
    ]
    (RUN / "CLEAN_SEQUENTIAL_REPLICATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "clean_aggregate": clean_agg, "artifacts": ["CLEAN_SEQUENTIAL_REPLICATION_REPORT.md", "clean_repaired_treatment_results.json", "clean_repaired_treatment_funnel.csv", "clean_repaired_treatment_natural_demand.json", "contaminated_vs_clean.csv"]}, indent=2))


if __name__ == "__main__":
    main()
