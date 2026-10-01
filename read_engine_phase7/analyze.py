"""Phase-7 same-run paired analysis; no population selection."""
from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict

from read_engine_phase7.benchmark import HERE, TARGETS, ITERATION, verify

ARMS = ("PY", "H0", "H1")
PAIRS = (("H1", "H0"), ("H1", "PY"), ("H0", "PY"))
median = statistics.median


def rows(name: str) -> list[dict]:
    return [json.loads(s) for s in (HERE / name).read_text().splitlines() if s]


def effect(pairs: list[tuple[float, float]]) -> dict:
    ratios = [a / b for a, b in pairs]
    rng = random.Random(20261107)
    boot = sorted(median(rng.choices(ratios, k=len(ratios))) for _ in range(2000))
    return {"n": len(ratios), "median_ratio": median(ratios),
            "geometric_mean_ratio": math.exp(statistics.mean(math.log(x) for x in ratios)),
            "bootstrap_median_95pct": [boot[49], boot[1949]],
            "range": [min(ratios), max(ratios)],
            "faster": sum(x < 1 for x in ratios), "slower": sum(x > 1 for x in ratios),
            "tied": sum(x == 1 for x in ratios)}


def analyze() -> tuple[dict, dict]:
    pop = verify()
    raw = [x for x in rows("raw_timings.jsonl") if x["phase"] == "scored"]
    correct = [x for x in rows("raw_correctness.jsonl") if x.get("kind") == "script_three_arm" and x.get("phase") == "scored"]
    sessions = rows("session_timings.jsonl")
    fixtures = rows("merged_cell_fixtures.jsonl")
    if ((len(raw), len(correct), len(sessions)) != (22*3*5*3, 22*3*5, 22*3*4)
            or not all(x["valid"] for x in correct) or not all(x["passed"] for x in fixtures)):
        raise RuntimeError("Incomplete/invalid Phase-7 ledgers")
    by_id = {x["workload_id"]: x for x in pop["workloads"]}
    lookup = {(x["workload_id"], x["rep"], x["invocation"], x["arm"]): x for x in raw}
    per = {}
    for wid in pop["primary_ids"]:
        source = by_id[wid]
        result = {"task": source["task"], "family": source["family"]}
        for regime, positions in (("cold", (1,)), ("warm", (2,3,4,5))):
            times = {arm: median([median(lookup[(wid,rep,j,arm)]["wall_ns"] for j in positions)
                                  for rep in range(1,4)]) for arm in ARMS}
            result[regime] = {**{arm+"_ns": value for arm,value in times.items()},
                              **{a+"_"+b: times[a]/times[b] for a,b in PAIRS}}
        for arm in ("H0", "H1"):
            warm = [lookup[(wid,rep,j,arm)] for rep in range(1,4) for j in range(2,6)]
            result[arm+"_warm_reference_reasons"] = dict(Counter(reason for x in warm
                    for reason in x["summary"].get("reference_reasons", [])))
            result[arm+"_warm_reference_parse_ms"] = median(x["child_profile"]["times"]["reference_parse_ns"]/1e6 for x in warm)
            result[arm+"_warm_artifact_load_ms"] = median(x["child_profile"]["times"]["artifact_load_ns"]/1e6 for x in warm)
        h1 = [lookup[(wid,rep,j,"H1")] for rep in range(1,4) for j in range(2,6)]
        result["H1_merged_contact_median"] = median(x["merged"]["merged_child_contact"] for x in h1)
        result["H1_merged_direct_median"] = median(x["merged"]["merged_child_direct"] for x in h1)
        result["H1_merged_reference_median"] = median(x["merged"]["merged_child_reference"] for x in h1)
        result["H1_certified"] = all(x["summary"]["merged_certificate"]["certified"] for x in h1)
        result["warm_signed_excess_ms"] = (result["warm"]["H1_ns"]-result["warm"]["PY_ns"])/1e6
        per[wid] = result
    aggregate = {}
    for regime in ("cold", "warm"):
        aggregate[regime] = {a+"_"+b: effect([(per[wid][regime][a+"_ns"],per[wid][regime][b+"_ns"])
                                          for wid in pop["primary_ids"]]) for a,b in PAIRS}
    slookup = {(x["workload_id"],x["rep"],x["N"]):x for x in sessions}
    aggregate["session"] = {}
    for n in (1,2,3,5):
        t = {wid: {arm: median(slookup[(wid,rep,n)][arm+"_ns"] for rep in range(1,4))
                   for arm in ARMS} for wid in pop["primary_ids"]}
        aggregate["session"][str(n)] = {a+"_"+b: effect([(t[wid][a],t[wid][b]) for wid in pop["primary_ids"]])
                                        for a,b in PAIRS}
    tasks = defaultdict(list)
    for wid in pop["primary_ids"]:
        tasks[per[wid]["task"]].append(per[wid]["warm"]["H1_PY"])
    task_ratios = [math.exp(statistics.mean(math.log(x) for x in v)) for v in tasks.values()]
    warm = aggregate["warm"]["H1_PY"]
    losers = {}
    for wid,v in per.items():
        if v["warm"]["H1_PY"] <= 1:
            continue
        if wid in TARGETS and v["H1_warm_reference_reasons"].get("proxy_operation_escape",0):
            label = "MERGED_FALLBACK_REMAINING"
        elif wid == ITERATION:
            label = "WORKBOOK_ITERATION_FALLBACK"
        elif v["family"] == "Template":
            label = "SHORT_BOOTSTRAP_OVERHEAD"
        else:
            label = "OTHER"
        losers[wid] = label
    analysis = {"population": {"scripts":22,"tasks":len(tasks),"scored_invocations":len(raw),
                               "correctness_rows":len(correct),"fixture_cases":len(fixtures)},
                "per_workload":per,"aggregate":aggregate,
                "task_cluster_warm_H1_PY":effect([(x,1) for x in task_ratios]),
                "warm_signed_excess_ms":{"median":median(v["warm_signed_excess_ms"] for v in per.values()),
                                         "range":[min(v["warm_signed_excess_ms"] for v in per.values()),
                                                  max(v["warm_signed_excess_ms"] for v in per.values())]},
                "warm_speed_rule_passed":warm["median_ratio"]<1 and warm["faster"]>11 and warm["bootstrap_median_95pct"][1]<1,
                "remaining_warm_losers":losers,
                "limits":["22 scripts from 14 tasks are contact-selected", "OS cache/frequency uncontrolled",
                          "Phase-7 overlay path is an experimental launch indirection", "Offline POSIX, no public RC change"]}
    profile = {"cold":{},"warm":{}}
    for regime,positions in (("cold",(1,)),("warm",(2,3,4,5))):
        for arm in ("H0","H1"):
            across = defaultdict(list)
            for wid in pop["primary_ids"]:
                local = defaultdict(list)
                for rep in range(1,4):
                    for j in positions:
                        x = lookup[(wid,rep,j,arm)]
                        obs = x["parent_profile"]["observer"] or {}
                        boot = x["parent_profile"]["script_bootstrap"] or {}
                        for key,value in obs.items():
                            if isinstance(value,(int,float)):
                                local["observer_"+key].append(value/1e6)
                        for key,value in boot.items():
                            if isinstance(value,(int,float)):
                                local["bootstrap_"+key].append(value/1e6)
                        local["artifact_load_ms"].append(x["child_profile"]["times"]["artifact_load_ns"]/1e6)
                        local["reference_parse_ms"].append(x["child_profile"]["times"]["reference_parse_ns"]/1e6)
                for key,values in local.items():
                    across[key].append(median(values))
            profile[regime][arm] = {key:{"median":median(values),"range":[min(values),max(values)]}
                                    for key,values in across.items()}
    return analysis,profile


def main() -> None:
    analysis,profile = analyze()
    (HERE/"analysis.json").write_text(json.dumps(analysis,sort_keys=True,indent=2)+"\n")
    (HERE/"profile.json").write_text(json.dumps(profile,sort_keys=True,indent=2)+"\n")


if __name__ == "__main__":
    main()
