"""Paired four-arm Phase-6 analysis of the frozen 22."""
from __future__ import annotations
import json, math, random, statistics
from collections import Counter, defaultdict
from read_engine_phase6.benchmark import HERE, verify

ARMS=("PY","H0","H1","H2")
PAIRS=(("H2","PY"),("H2","H0"),("H2","H1"),("H0","PY"),("H1","PY"),("H1","H0"))
median=statistics.median

def rows(name):
    return [json.loads(s) for s in (HERE/name).read_text().splitlines() if s]

def effect(pairs):
    r=[a/b for a,b in pairs]
    rng=random.Random(20261106)
    boot=sorted(median(rng.choices(r,k=len(r))) for _ in range(2000))
    return {"n":len(r),"median_ratio":median(r),"geometric_mean_ratio":math.exp(statistics.mean(math.log(x) for x in r)),
            "bootstrap_median_95pct":[boot[49],boot[1949]],"range":[min(r),max(r)],
            "faster":sum(x<1 for x in r),"slower":sum(x>1 for x in r),"tied":sum(x==1 for x in r)}

def analyze():
    pop=verify()
    raw=[x for x in rows("raw_timings.jsonl") if x["phase"]=="scored"]
    correct=[x for x in rows("raw_correctness.jsonl") if x.get("kind")=="script_triplet" and x.get("phase")=="scored"]
    sessions=rows("session_timings.jsonl")
    if (len(raw),len(correct),len(sessions))!=(22*3*5*4,22*3*5,22*3*4) or not all(x["valid"] for x in correct):
        raise RuntimeError("Incomplete/invalid scored ledgers")
    byid={x["workload_id"]:x for x in pop["workloads"]}
    lookup={(x["workload_id"],x["rep"],x["invocation"],x["arm"]):x for x in raw}
    per={}
    for wid in pop["primary_ids"]:
        source=byid[wid]
        result={"task":source["task"],"family":source["family"]}
        for regime,positions in (("cold",(1,)),("warm",(2,3,4,5))):
            t={arm:median([median(lookup[(wid,rep,j,arm)]["wall_ns"] for j in positions)
                           for rep in range(1,4)]) for arm in ARMS}
            result[regime]={**{a+"_ns":v for a,v in t.items()},**{a+"_"+b:t[a]/t[b] for a,b in PAIRS}}
        for arm in ("H0","H1","H2"):
            warm=[lookup[(wid,rep,j,arm)] for rep in range(1,4) for j in range(2,6)]
            result[arm+"_warm_statuses"]=dict(Counter(next(iter(x["summary"]["artifacts"].values()))["status"] for x in warm))
            result[arm+"_fallback_reasons"]=dict(Counter(reason for x in warm for reason in x["summary"]["reference_reasons"]))
        h2=[lookup[(wid,rep,j,"H2")] for rep in range(1,4) for j in range(2,6)]
        result["H2_artifact_bytes"]=median(next(iter(x["summary"]["artifacts"].values()))["phases"]["artifact_bytes"] for x in h2)
        result["H2_changed_xlsx"]=dict(Counter(x["summary"]["observer_receipt"]["changed_xlsx"] for x in h2))
        result["warm_signed_excess_ms"]=(result["warm"]["H2_ns"]-result["warm"]["PY_ns"])/1e6
        per[wid]=result
    aggregate={}
    for regime in ("cold","warm"):
        aggregate[regime]={a+"_"+b:effect([(per[wid][regime][a+"_ns"],per[wid][regime][b+"_ns"])
                                           for wid in pop["primary_ids"]]) for a,b in PAIRS}
    slookup={(x["workload_id"],x["rep"],x["N"]):x for x in sessions}
    aggregate["session"]={}
    for n in (1,2,3,5):
        t={wid:{a:median(slookup[(wid,rep,n)][a+"_ns"] for rep in range(1,4))
                for a in ARMS} for wid in pop["primary_ids"]}
        aggregate["session"][str(n)]={a+"_"+b:effect([(t[wid][a],t[wid][b]) for wid in pop["primary_ids"]])
                                      for a,b in PAIRS}
    task=defaultdict(list)
    for wid in pop["primary_ids"]:task[per[wid]["task"]].append(per[wid]["warm"]["H2_PY"])
    task_ratios=[math.exp(statistics.mean(math.log(x) for x in v)) for v in task.values()]
    w=aggregate["warm"]["H2_PY"]
    analysis={"population":{"scripts":22,"tasks":len(task),"scored_invocations":len(raw),"correctness_rows":len(correct)},
              "per_workload":per,"aggregate":aggregate,
              "task_cluster_warm":effect([(x,1) for x in task_ratios]),
              "warm_signed_excess_ms":{"median":median(x["warm_signed_excess_ms"] for x in per.values()),
                                        "range":[min(x["warm_signed_excess_ms"] for x in per.values()),
                                                 max(x["warm_signed_excess_ms"] for x in per.values())]},
              "timing_rule_passed":w["median_ratio"]<1 and w["faster"]>11 and w["bootstrap_median_95pct"][1]<1,
              "limits":["OS cache and CPU frequency uncontrolled","22 scripts represent 14 tasks",
                        "offline POSIX architecture, not public RC"]}
    profile={"cold":{},"warm":{}}
    for regime,positions in (("cold",(1,)),("warm",(2,3,4,5))):
        for arm in ("H0","H1","H2"):
            across=defaultdict(list)
            for wid in pop["primary_ids"]:
                local=defaultdict(list)
                for rep in range(1,4):
                    for j in positions:
                        row=lookup[(wid,rep,j,arm)]
                        if arm=="H2":
                            obs=row["parent_profile"]["observer"] or {}
                            setup=row["parent_profile"]["script_bootstrap"] or {}
                            for k,v in obs.items():
                                if isinstance(v,(int,float)):local["observer_"+k].append(v/1e6)
                            for k,v in setup.items():
                                if isinstance(v,(int,float)):local["bootstrap_"+k].append(v/1e6)
                            local["external_observer_residual"].append((row["wall_ns"]-obs.get("observer_to_receipt",0))/1e6)
                        else:
                            p=row["parent_profile"]
                            for k in ("parent_total_ns","child_wall_ns","script_wall_ns","runtime_install_ns",
                                      "pre_capture_ns","post_capture_delta_validation_ns"):
                                if isinstance(p.get(k),(int,float)):local[k].append(p[k]/1e6)
                            local["external_parent_residual"].append((row["wall_ns"]-p["parent_total_ns"])/1e6)
                        c=row["child_profile"]
                        for k in ("artifact_load_ns","child_source_hash_ns","reference_parse_ns"):
                            local["runtime_"+k].append(c["times"][k]/1e6)
                for k,v in local.items():across[k].append(median(v))
            profile[regime][arm]={k:{"median":median(v),"range":[min(v),max(v)]} for k,v in across.items()}
    return analysis,profile

def main():
    a,p=analyze()
    (HERE/"analysis.json").write_text(json.dumps(a,sort_keys=True,indent=2)+"\n")
    (HERE/"profile.json").write_text(json.dumps(p,sort_keys=True,indent=2)+"\n")

if __name__=="__main__":main()
