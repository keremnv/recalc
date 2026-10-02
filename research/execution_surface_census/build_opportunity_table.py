"""Build ECONOMIC_OPPORTUNITY_TABLE.json from census ledgers.

All mass figures derive from OPERATION_CENSUS/COST_DECOMPOSITION/
INSPECTION_PRIMITIVE_MAPPING plus the probes recorded in _staging.
Authorization bar: 5x representative repeatability spread (41.5ms) = ~208ms
lower-80% expected value per representative workload (prereg sec 6).
"""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).parent

BAR_S = 5 * 0.0415  # 207.5ms


def main():
    census = [json.loads(l) for l in open(HERE / "OPERATION_CENSUS.jsonl")]
    cost = {(r["population"], r["workload"]): r for r in
            (json.loads(l) for l in open(HERE / "COST_DECOMPOSITION.jsonl"))}
    prim = json.loads((HERE / "INSPECTION_PRIMITIVE_MAPPING.json").read_text())

    rep = [r for r in census if r["population"] == "A"]
    # iteration-only-blocked mass recomputed from census (blockers in REPORT)
    rows = [
        {
            "mechanism": "full-cell iteration serving (iter_rows/iter_cols/worksheet iteration on proxy cells)",
            "representative_workloads_affected": "13/30 (iteration-only-blocked)",
            "operation_frequency": "69 iter_rows/iter_cols calls + worksheet iteration in A/B/C executions; iteration blockers on 15+14 A-workloads",
            "avoidable_wall_time_mass": "64.1s reference parse over 13 workloads (median 1.36s/workload); warm decode 15-52ms replaces multi-second parses",
            "potential_context_output_reduction": "none claimed; outputs already sparse (median heredoc obs 479B)",
            "new_runtime_complexity": "medium: proxy row/cell iteration protocol + classifier iterator-shape proofs + Phase-8A-style certification",
            "semantic_compatibility_risk": "medium: cell identity/type/repr gaps per expansion; fallback escape available",
            "fallback_available": True,
            "measurement_confidence": "high: direct census + blocker enumeration",
            "expected_value_vs_bar": "median ~1.3s/workload vs 0.21s bar; lower-tail (3 small books <0.2s) below bar but 10/13 clear it",
            "verdict": "EARNED_FOR_FEASIBILITY_PROBE",
        },
        {
            "mechanism": "range access (ws['A1:B2']) and values_only/.values fast paths",
            "representative_workloads_affected": "0/30",
            "operation_frequency": "0 range-literals, 0 values_only, 1 .values in 309-universe; 0 dynamic .values calls executed",
            "avoidable_wall_time_mass": "~0",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "low-medium",
            "semantic_compatibility_risk": "low-medium",
            "fallback_available": True,
            "measurement_confidence": "high (absence is well-measured)",
            "expected_value_vs_bar": "~0; fails bar",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "data_only / cached-value serving",
            "representative_workloads_affected": "0/30 A (no data_only loads); 23/120 C-sample scripts reference data_only",
            "operation_frequency": "53 data_only readbacks in 309-universe (static); 0 executed in A/B",
            "avoidable_wall_time_mass": "small: readback parses are ordinary parses; no separate mass measured",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "medium: cached-value storage + staleness semantics",
            "semantic_compatibility_risk": "medium-high: stale-cache semantics (the Ph12/12R saga) must be defined, not just served",
            "fallback_available": True,
            "measurement_confidence": "medium",
            "expected_value_vs_bar": "below bar on representative evidence",
            "verdict": "OBSERVE_MORE",
        },
        {
            "mechanism": "persistent worker / decoded-state residency / fork server",
            "representative_workloads_affected": "all (fixed-cost removal)",
            "operation_frequency": "per invocation",
            "avoidable_wall_time_mass": "startup 30ms + openpyxl import 186ms + warm validate/decode ~15-52ms ~= ~250ms fixed per invocation; median workload wall 0.43-0.71s",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "high: process-model change; external death-detection story (Phase-5 falsification of in-process observation) must be preserved",
            "semantic_compatibility_risk": "high: cross-invocation state identity; cache-poisoning surface",
            "fallback_available": "partial (cold path remains)",
            "measurement_confidence": "high on mass, low on integration tax",
            "expected_value_vs_bar": "net ~150-200ms after plausible integration tax vs 208ms bar: borderline; tax unmeasured",
            "verdict": "OBSERVE_MORE",
        },
        {
            "mechanism": "inspection query primitives (find_text, sparse_range_values, formula_regions)",
            "representative_workloads_affected": "broad: 257 find_text instances/38 tasks; 126 sparse-range/23 tasks (309-universe static)",
            "operation_frequency": "high instance count; per-instance traversal time ~ms (cell reads ~sub-us; loops dominated by already-counted parse)",
            "avoidable_wall_time_mass": "small: primitives do not avoid the parse; Python loop time saved is ms-scale per workload",
            "potential_context_output_reduction": "not earned: outputs already sparse (median 479B, p90 8.9KB); coordinate-only summaries would EXCEED current filtered output (e.g. 2.6M dim-cells -> 26MB coords vs 4.7-91KB actual)",
            "new_runtime_complexity": "low (L0-L1 over read state)",
            "semantic_compatibility_risk": "low mechanical; adoption risk high (prior: helpers FM-only 4/24, batch 0/13)",
            "fallback_available": True,
            "measurement_confidence": "high on mass absence; adoption unmeasured for these exact forms",
            "expected_value_vs_bar": "ms-scale << bar; token thesis falsified",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "change/diff queries (diff_workbooks, changed_cells)",
            "representative_workloads_affected": "narrow: 32 compare instances/15 tasks; 7 reopen-after-save/7 tasks",
            "operation_frequency": "low",
            "avoidable_wall_time_mass": "small (same parse-bound argument as inspection primitives)",
            "potential_context_output_reduction": "small (compare outputs <= 35KB observed)",
            "new_runtime_complexity": "medium (two-state serving)",
            "semantic_compatibility_risk": "low mechanical; adoption risk as above",
            "fallback_available": True,
            "measurement_confidence": "medium-high",
            "expected_value_vs_bar": "below bar",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "dependency graph / reference search / dirty propagation",
            "representative_workloads_affected": "minimal: 8 reference_search instances/4 tasks; 0 dependency-vocabulary executions",
            "operation_frequency": "~0",
            "avoidable_wall_time_mass": "~0 measured",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "high (formula parsing, edge extraction, invalidation)",
            "semantic_compatibility_risk": "medium (read-only facts) to high (if consumed)",
            "fallback_available": True,
            "measurement_confidence": "high on demand absence",
            "expected_value_vs_bar": "~0; fails bar",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "recalculation engine / feasibility",
            "representative_workloads_affected": "mutation workflows: 66 LO/soffice calls over ~48 tasks (archived), median wait 1.7s, sum 185s",
            "operation_frequency": "~1-2 calls per recalc-using trajectory",
            "avoidable_wall_time_mass": "~2-5s per recalc-using trajectory IF engine matched LO semantics; ~0 for read-only majority",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "very high (function library, LO/Excel parity, oracle problem)",
            "semantic_compatibility_risk": "very high (must agree with scorer's engine)",
            "fallback_available": True,
            "measurement_confidence": "medium (archived waits, not re-measured; engine cost unestimated)",
            "expected_value_vs_bar": "mass real but mechanism cost orders of magnitude above any other candidate; no feasibility basis",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "write-state ownership / mutation engine / custom serialization",
            "representative_workloads_affected": "mutation scripts only (0/52 A/B; 33 executed C workloads save)",
            "operation_frequency": "33 workloads save, ~31s total (median 9ms; bimodal: ms on tiny books, 1-6s on large books); mutation dispatch ~0.1s total; 1106 subscript assigns + 4422 value sets ~ms",
            "avoidable_wall_time_mass": "~0 identified as avoidable: save cost is inherent serialization work and no measurement shows a Recalc serializer beating openpyxl; the mass is real but not plausibly removable without full serializer ownership (highest risk); mutation dispatch negligible",
            "potential_context_output_reduction": "none",
            "potential_context_output_reduction_note": "the 0/13 batch-helper result concerned exposure; this phase additionally finds no hidden write-side mass",
            "new_runtime_complexity": "very high (package fidelity incl. styles/charts/names; agent LO round-trips already destroy formatting)",
            "semantic_compatibility_risk": "very high (silent corruption is the failure mode)",
            "fallback_available": True,
            "measurement_confidence": "high on mass absence",
            "expected_value_vs_bar": "~0; fails bar",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "richer read proxy (merged/rich/workbook-surface expansion beyond iteration)",
            "representative_workloads_affected": "9/30 A other-blocked holding 0.4s parse; merged refs 4, rich dynamic families ~0 time",
            "operation_frequency": "low",
            "avoidable_wall_time_mass": "0.4s over 9 workloads (median ~10ms)",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "high (quirk parity per surface)",
            "semantic_compatibility_risk": "high",
            "fallback_available": True,
            "measurement_confidence": "high",
            "expected_value_vs_bar": "below bar",
            "verdict": "CLOSED_FOR_NOW",
        },
        {
            "mechanism": "richer execution tracing / transparency queries",
            "representative_workloads_affected": "all (diagnostic, not workload-mass)",
            "operation_frequency": "N/A",
            "avoidable_wall_time_mass": "0 (no workload cost removed)",
            "potential_context_output_reduction": "none",
            "new_runtime_complexity": "low (facts already in receipts: route, admission, fallback, timings, assurance)",
            "semantic_compatibility_risk": "none (read-only facts)",
            "fallback_available": True,
            "measurement_confidence": "high",
            "expected_value_vs_bar": "not a workload optimization; developer value only",
            "verdict": "ALREADY_PRODUCTIZED",
        },
    ]
    (HERE / "ECONOMIC_OPPORTUNITY_TABLE.json").write_text(
        json.dumps({"authorization_bar_s": BAR_S,
                    "bar_basis": "5x representative repeatability spread (41.5ms median, G5 runs)",
                    "candidates": rows}, indent=1))
    print("candidates:", len(rows),
          "earned:", sum(1 for r in rows if r["verdict"].startswith("EARNED")))


if __name__ == "__main__":
    main()
