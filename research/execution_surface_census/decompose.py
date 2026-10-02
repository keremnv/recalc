"""Cost decomposition + operation census from telemetry rows.

Writes committed compact ledgers:
  OPERATION_CENSUS.jsonl, COST_DECOMPOSITION.jsonl
Per-workload medians across reps; arms compared pairwise.
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TELE = HERE / "_staging" / "telemetry"

READ_OWNED_IF_ADMITTED = {"sheet_enumeration", "sheet_lookup", "cell_getitem",
                          "cell_call", "cell_value_get", "data_type_get",
                          "bounds", "dimensions"}


def load_all(pattern="runs_*.jsonl"):
    rows = []
    for p in sorted(TELE.glob(pattern)):
        with open(p) as f:
            for line in f:
                rows.append(json.loads(line))
    return rows


def med(xs):
    return statistics.median(xs) if xs else 0.0


def main():
    rows = load_all()
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[(r["kind"], r["workload"])][r["arm"]].append(r)
    man = json.loads((HERE / "WORKLOAD_MANIFEST.json").read_text())
    task_of = {}
    for pop in ("A", "B"):
        for w in man["populations"][pop]["workloads"]:
            task_of[(pop, w["workload_id"])] = (pop, w["task"], w["family"])
    for w in man["populations"]["C"]["workloads"]:
        task_of[("C", "C_%d" % w["exec_id"])] = ("C", w["task_id"], w["family"])

    census_f = open(HERE / "OPERATION_CENSUS.jsonl", "w")
    cost_f = open(HERE / "COST_DECOMPOSITION.jsonl", "w")
    for (kind, wid) in sorted(by):
        arms = by[(kind, wid)]
        pop, task, fam = task_of.get((kind, wid), ("?", "?", "?"))
        base = arms.get("BASE", [])
        hook = arms.get("HOOK", [])
        prod = arms.get("PROD", [])
        # Operation census from HOOK arm (reference shape; identical calls).
        fam_count, fam_time = defaultdict(list), defaultdict(list)
        n_loads, n_saves, n_reopens = [], [], []
        ref_parse_s = []
        genuine_materialized = []
        for r in hook:
            cen = r.get("census", {})
            for fam, d in (cen.get("families") or {}).items():
                if fam.startswith("parse_internal:") or fam.startswith("serialize_internal:"):
                    continue
                fam_count[fam].append(d["count"])
                fam_time[fam].append(d["total_s"])
            loads = cen.get("loads", [])
            n_loads.append(len(loads))
            ref_parse_s.append(sum(x.get("duration_s", 0) for x in loads))
            n_saves.append(len(cen.get("saves", [])))
            seen = defaultdict(int)
            for x in loads:
                seen[x.get("path")] += 1
            n_reopens.append(sum(max(0, n - 1) for n in seen.values()))
            genuine_materialized.append(True)  # HOOK arm is genuine openpyxl
        # Admission/fallback from PROD arm.
        admitted, routes, fallbacks, served, art_status = [], [], [], [], []
        for r in prod:
            st = r["receipt"].get("setup.json", {}) or {}
            rt = r["receipt"].get("runtime_state.json", {}) or {}
            admitted.append(bool(st.get("admitted")))
            routes.append(rt.get("route") or st.get("route"))
            fb = list(st.get("fallback") or [])
            fb += [{"reason": x} for x in (rt.get("fallback_reasons") or [])]
            fallbacks.append([f.get("reason") for f in fb])
            served.append((rt.get("counts") or {}).get("direct_served_loads", 0))
            arts = st.get("artifacts") or {}
            art_status.append(sorted({e.get("status") for e in arts.values()
                                      if isinstance(e, dict)}))
        census_f.write(json.dumps({
            "workload": wid, "population": pop, "task": task, "family": fam,
            "exit": [r["exit"] for r in base],
            "families": {f: {"count_median": med(v),
                             "time_s_median": round(med(fam_time[f]), 6)}
                         for f, v in sorted(fam_count.items())},
            "n_loads": n_loads, "n_saves": n_saves, "n_reopens": n_reopens,
            "reference_parse_s": [round(x, 4) for x in ref_parse_s],
            "admitted": admitted, "routes": routes, "fallbacks": fallbacks,
            "direct_served_loads": served, "artifact_status": art_status,
        }, sort_keys=True) + "\n")
        # Cost decomposition.
        base_wall = [r["wall_s"] for r in base]
        hook_wall = [r["wall_s"] for r in hook]
        prod_wall = [r["wall_s"] for r in prod]
        obs_ns, rt_times = [], defaultdict(list)
        for r in prod:
            ob = r["receipt"].get("observer_receipt.json", {}) or {}
            if isinstance(ob.get("profile_ns"), dict):
                obs_ns.append(ob["profile_ns"])
            rt = r["receipt"].get("runtime_state.json", {}) or {}
            for k, v in (rt.get("times") or {}).items():
                rt_times[k].append(v / 1e9)
        cost_f.write(json.dumps({
            "workload": wid, "population": pop, "task": task, "family": fam,
            "base_wall_s": [round(x, 4) for x in base_wall],
            "hook_wall_s": [round(x, 4) for x in hook_wall],
            "prod_wall_s": [round(x, 4) for x in prod_wall],
            "hook_overhead_s": round(med(hook_wall) - med(base_wall), 4) if base_wall and hook_wall else None,
            "prod_tax_s": round(med(prod_wall) - med(base_wall), 4) if base_wall and prod_wall else None,
            "observer_profile_ns": obs_ns,
            "runtime_times_s": {k: round(med(v), 6) for k, v in rt_times.items()},
        }, sort_keys=True) + "\n")
    census_f.close()
    cost_f.close()
    print("workloads:", len(by))


if __name__ == "__main__":
    main()
