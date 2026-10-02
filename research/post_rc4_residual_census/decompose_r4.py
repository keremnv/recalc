"""R4 analysis: routing census + cost decomposition + reference-parse mass.

Reads _staging/telemetry/runs.jsonl + classifier scans. Writes committed
compact ledgers: ROUTING_CENSUS.jsonl, COST_DECOMPOSITION.jsonl,
REFERENCE_PARSE_MASS.json. Prints parity/validity summary.
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
R1 = HERE.parent / "execution_surface_census"


def med(xs):
    return statistics.median(xs) if xs else None


def load_rows():
    rows = []
    with open(HERE / "_staging" / "telemetry" / "runs.jsonl") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def load_scan(name):
    out = {}
    with open(HERE / "_staging" / name) as f:
        for line in f:
            r = json.loads(line)
            out[r["workload"]] = r
    return out


BLOCKER_FAMILY = {
    "RICH_OBJECT_BOUNDARY": "rich_attributes",
    "rich object": "rich_attributes",
    "WRITE_BOUNDARY": "writes_mixed",
    "READ_WRITE_MIXED_BOUNDARY": "writes_mixed",
    "mutation/save": "writes_mixed",
    "cell mutation": "writes_mixed",
    "workbook/cell mutation": "writes_mixed",
    "STATIC_ANALYSIS_UNCERTAINTY": "dynamic_uncertain",
    "OBJECT_ESCAPE_BOUNDARY": "dynamic_uncertain",
    "function/object escape risk": "dynamic_uncertain",
    "unsupported active worksheet": "active_worksheets",
    "WORKBOOK_WORKSHEETS_BOUNDARY": "active_worksheets",
    "unsupported worksheet collection": "active_worksheets",
    "DATA_ONLY_BOUNDARY": "data_only",
    "data_only": "data_only",
    "CELL_OBJECT_ITERATION_BOUNDARY": "unsupported_iteration",
    "iterator shape not statically proven": "unsupported_iteration",
    "RANGE_OBJECT_BOUNDARY": "ranges",
    "explicit worksheet range": "ranges",
    "LOAD_OPTION_BOUNDARY": "load_options",
}


def families_of(blockers):
    fams = {BLOCKER_FAMILY.get(b, "other") for b in blockers}
    return sorted(fams)


def route_of(receipt):
    rt = (receipt.get("runtime_state.json") or {})
    st = (receipt.get("setup.json") or {})
    return rt.get("route") or st.get("route") or "UNKNOWN"


def main():
    rows = load_rows()
    scan = load_scan("classifier_scan_ALL.jsonl")
    by = defaultdict(list)
    for r in rows:
        if r.get("arm") == "INVALID":
            continue
        by[(r["population"], r["workload"])].append(r)

    routing_f = open(HERE / "ROUTING_CENSUS.jsonl", "w")
    cost_f = open(HERE / "COST_DECOMPOSITION.jsonl", "w")
    parse_mass = []  # (wid, pop, families, ref_parse_med, prod_warm_med)
    parity_ok, parity_bad = 0, []
    hook_ov, prod_tax = [], []

    for (pop, wid) in sorted(by):
        rs = by[(pop, wid)]
        base = [r for r in rs if r["arm"] == "BASE"]
        hook = [r for r in rs if r["arm"] == "HOOK"]
        warm = [r for r in rs if r["arm"] == "PROD" and r["tag"] in
                ("warm0", "warm1", "warm2")]
        cold = [r for r in rs if r["arm"] == "PROD" and r["tag"] == "cold0"]
        # Parity: HOOK vs BASE (exit + stdout-norm + state).
        for h in hook:
            match = any(
                b["exit"] == h["exit"]
                and b["stdout_norm_sha256"] == h["stdout_norm_sha256"]
                and b["state"] == h["state"] for b in base)
            if match:
                parity_ok += 1
            else:
                parity_bad.append((pop, wid, h["tag"]))
        routes = [route_of(r["receipt"]) for r in warm]
        art = []
        for r in warm:
            st = (r["receipt"].get("setup.json") or {})
            arts = st.get("artifacts") or {}
            art.append(sorted({e.get("status") for e in arts.values()
                               if isinstance(e, dict)}))
        fb = []
        for r in warm:
            st = (r["receipt"].get("setup.json") or {})
            rt = (r["receipt"].get("runtime_state.json") or {})
            reasons = [f.get("reason") for f in (st.get("fallback") or [])]
            reasons += list(rt.get("fallback_reasons") or [])
            fb.append(sorted(set(reasons)))
        sc = scan.get(wid, {})
        blockers = sc.get("blockers", [])
        routing_f.write(json.dumps({
            "workload": wid, "population": pop,
            "static_decision": sc.get("decision"),
            "static_blockers": blockers,
            "blocker_families": families_of(blockers),
            "warm_routes": routes,
            "warm_exits": [r["exit"] for r in warm],
            "artifact_status": art,
            "fallback_reasons": fb,
            "cold_route": route_of(cold[0]["receipt"]) if cold else None,
        }, sort_keys=True) + "\n")
        # Cost decomposition.
        base_wall = [r["wall_s"] for r in base]
        hook_wall = [r["wall_s"] for r in hook]
        warm_wall = [r["wall_s"] for r in warm]
        cold_wall = [r["wall_s"] for r in cold]
        if base_wall and hook_wall:
            hook_ov.append(med(hook_wall) - med(base_wall))
        if base_wall and warm_wall:
            prod_tax.append(med(warm_wall) - med(base_wall))
        rt_times = defaultdict(list)
        obs = []
        for r in warm:
            rt = (r["receipt"].get("runtime_state.json") or {})
            for k, v in (rt.get("times") or {}).items():
                rt_times[k].append(v / 1e9)
            ob = (r["receipt"].get("observer_receipt.json") or {})
            if isinstance(ob.get("profile_ns"), dict):
                obs.append(ob["profile_ns"])
        fam_count, fam_time = defaultdict(list), defaultdict(list)
        loads_s, saves_n, reopens = [], [], []
        for r in hook:
            cen = r.get("census", {}) or {}
            for fam, d in (cen.get("families") or {}).items():
                if fam.startswith("parse_internal:") or fam.startswith("serialize_internal:"):
                    continue
                fam_count[fam].append(d["count"])
                fam_time[fam].append(d["total_s"])
            loads = cen.get("loads", [])
            loads_s.append(round(sum(x.get("duration_s", 0) for x in loads), 4))
            saves_n.append(len(cen.get("saves", [])))
            seen = defaultdict(int)
            for x in loads:
                seen[x.get("path")] += 1
            reopens.append(sum(max(0, n - 1) for n in seen.values()))
        cost_f.write(json.dumps({
            "workload": wid, "population": pop,
            "base_wall_s": [round(x, 4) for x in base_wall],
            "hook_wall_s": [round(x, 4) for x in hook_wall],
            "prod_warm_wall_s": [round(x, 4) for x in warm_wall],
            "prod_cold_wall_s": [round(x, 4) for x in cold_wall],
            "hook_overhead_s": round(med(hook_wall) - med(base_wall), 4) if base_wall and hook_wall else None,
            "prod_tax_s": round(med(warm_wall) - med(base_wall), 4) if base_wall and warm_wall else None,
            "observer_profile_ns": obs,
            "runtime_times_s": {k: round(med(v), 6) for k, v in rt_times.items()},
            "op_families": {f: {"count_median": med(v), "time_s_median": round(med(fam_time[f]), 6)}
                            for f, v in sorted(fam_count.items())},
            "reference_parse_s": loads_s,
            "n_saves": saves_n,
            "n_reopens": reopens,
        }, sort_keys=True) + "\n")
        if pop == "A" and not all(x == "DIRECT_RUNTIME" for x in routes):
            parse_mass.append({
                "workload": wid,
                "route": max(set(routes), key=routes.count),
                "blocker_families": families_of(blockers),
                "reference_parse_s_median": med(loads_s),
                "prod_warm_s_median": round(med(warm_wall), 4) if warm_wall else None,
            })
    routing_f.close()
    cost_f.close()

    total_parse = sum(p["reference_parse_s_median"] or 0 for p in parse_mass)
    by_fam = defaultdict(lambda: {"workloads": [], "parse_s": 0.0})
    for p in parse_mass:
        for f in p["blocker_families"]:
            by_fam[f]["workloads"].append(p["workload"])
            by_fam[f]["parse_s"] += (p["reference_parse_s_median"] or 0)
    with open(HERE / "REFERENCE_PARSE_MASS.json", "w") as f:
        json.dump({
            "population": "A",
            "residual_reference_workloads": [p["workload"] for p in parse_mass],
            "total_residual_reference_parse_s": round(total_parse, 4),
            "by_blocker_family": {
                fam: {"workloads": v["workloads"],
                      "parse_s": round(v["parse_s"], 4),
                      "share": round(v["parse_s"] / total_parse, 4) if total_parse else 0}
                for fam, v in sorted(by_fam.items())},
            "note": "families overlap (multi-blocker workloads counted in each); shares may sum >1",
        }, f, indent=1, sort_keys=True)

    print("workloads:", len(by))
    print("hook/base parity ok=%d bad=%d %s" % (parity_ok, len(parity_bad), parity_bad))
    print("hook overhead median=%.4f max=%.4f" % (med(hook_ov), max(hook_ov) if hook_ov else 0))
    print("prod tax median=%.4f" % med(prod_tax))
    print("residual A reference parse mass=%.4fs over %d workloads" % (total_parse, len(parse_mass)))


if __name__ == "__main__":
    main()
