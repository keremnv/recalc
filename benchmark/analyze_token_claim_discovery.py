#!/usr/bin/env python3
"""Mechanical post-hoc summaries of the frozen token discovery primary runs."""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import shutil
import statistics as stats
import subprocess
import sys
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/history/token_claim_discovery"
ARMS = "ABCD"
FAMILIES = ("Template", "Financial_Model", "Debugging")
ENC = tiktoken.get_encoding("cl100k_base")


def load(name: str, default=None):
    p=OUT/name
    return json.loads(p.read_text()) if p.exists() else default


def rows(name: str):
    p=OUT/name
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def put(name: str, value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True,default=str)+"\n")


def ratio_summary(nums: list[float]) -> dict:
    if not nums: return {"n":0,"median_ratio":None,"mean_ratio":None,"geometric_mean_ratio":None,"bootstrap_95pct_ci_geometric_ratio":None,"treatment_lower_count":0}
    rng=random.Random(20260922)
    logs=[math.log(x) for x in nums if x>0]
    boot=[]
    for _ in range(10000):
        sample=[rng.choice(logs) for _ in logs]
        boot.append(math.exp(stats.mean(sample)))
    boot.sort()
    return {"n":len(nums),"median_ratio":stats.median(nums),"median_reduction_pct":100*(1-stats.median(nums)),
            "mean_ratio":stats.mean(nums),"geometric_mean_ratio":math.exp(stats.mean(logs)),
            "bootstrap_95pct_ci_geometric_ratio":[boot[249],boot[9749]],
            "treatment_lower_count":sum(x<1 for x in nums),"treatment_higher_count":sum(x>1 for x in nums)}


def score_all(records: list[dict]) -> dict:
    score_root=OUT/"score_staging"
    per_arm={}
    for arm in ARMS:
        stage=score_root/arm
        stage.mkdir(parents=True,exist_ok=True)
        for rec in records:
            if rec["arm"]!=arm: continue
            family,tid=rec["task"].split(":")
            dst=stage/f"{family}-{tid}";dst.mkdir(exist_ok=True)
            src=ROOT/rec["run_dir"]/"output.xlsx"
            if src.exists(): shutil.copy2(src,dst/"output.xlsx")
        cmd=[sys.executable,str(ROOT/"benchmark/score_openrouter_run.py"),str(stage),"--model-name",f"token_claim_discovery_{arm}"]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=3600)
        (stage/"scorer_stdout.txt").write_text(proc.stdout+proc.stderr)
        if proc.returncode==0 and (stage/"official_scores.json").exists():
            per_arm[arm]=json.loads((stage/"official_scores.json").read_text())
        else:
            per_arm[arm]={"scorer_failed":True,"returncode":proc.returncode,"error_tail":(proc.stdout+proc.stderr)[-1000:]}
    return per_arm


def decompose_requests(records: list[dict]):
    output=[]
    for rec in records:
        req_dir=ROOT/rec["run_dir"]/"requests"
        for p in sorted(req_dir.glob("call_*.json")):
            call=int(p.stem.split("_")[-1])
            # Exclude the final failed request, if any. The primary run ledger
            # counts only successful model calls.
            if call>rec["api_calls"]:continue
            payload=json.loads(p.read_text())
            parts={"SYSTEM_BASE_SCAFFOLD":"","TASK_PROMPT":"","EXPERIMENT_NOTE":"","TOOL_SCHEMAS":json.dumps(payload.get("tools") or []),
                   "PRIOR_ASSISTANT_OUTPUT":"","PRIOR_TOOL_OBSERVATIONS":"","CURRENT_TOOL_USER_INPUT":"","OTHER":""}
            msgs=payload.get("messages") or []
            if msgs:parts["SYSTEM_BASE_SCAFFOLD"]=str(msgs[0].get("content") or "")
            if len(msgs)>1:
                s=str(msgs[1].get("content") or "")
                marker="\n\n## Working note"
                at=s.find(marker)
                if at>=0:parts["TASK_PROMPT"]=s[:at];parts["EXPERIMENT_NOTE"]=s[at:]
                else:parts["TASK_PROMPT"]=s
            for idx,m in enumerate(msgs[2:],2):
                txt=json.dumps(m) if m.get("role")=="assistant" else str(m.get("content") or "")
                if m.get("role")=="assistant":parts["PRIOR_ASSISTANT_OUTPUT"]+=txt
                elif idx==len(msgs)-1:parts["CURRENT_TOOL_USER_INPUT"]+=txt
                elif m.get("role") in ("user","tool"):parts["PRIOR_TOOL_OBSERVATIONS"]+=txt
                else:parts["OTHER"]+=txt
            out={"task":rec["task"],"arm":rec["arm"],"call":call,
                 "exact_bytes_by_category":{k:len(v.encode()) for k,v in parts.items()},
                 "local_cl100k_estimate_by_category":{k:len(ENC.encode(v)) for k,v in parts.items()},
                 "method":"exact archive request segmentation; local cl100k estimate, not provider usage"}
            output.append(out)
    with open(OUT/"request_decomposition_exact.jsonl","w") as fh:
        for x in output:fh.write(json.dumps(x)+"\n")
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--reuse-scores", action="store_true", help="Recalculate summaries from the archived official score output; do not invoke LibreOffice or the scorer")
    args=parser.parse_args()
    records=rows("primary_runs.jsonl")
    by={(r["task"],r["arm"]):r for r in records}
    population=load("population.json")["tasks"]
    scores=load("official_scores.json",{}).get("arms",{}) if args.reuse_scores else score_all(records) if len(records)==60 else {}
    official=[]
    for rec in records:
        x=(scores.get(rec["arm"]) or {}).get("tasks",{}).get(rec["task"],{})
        scorer_error=x.get("error_message")
        scored_workbook=bool(x and isinstance(x.get("modification_accuracy"),(int,float))
                             and isinstance(x.get("regression_accuracy"),(int,float))
                             and (not scorer_error or str(scorer_error).startswith(("Modification error at ","Regression error at "))))
        official.append({"task":rec["task"],"arm":rec["arm"],"submitted":rec["submitted"],
                         "output_exists":rec["output_exists"],"exact":x.get("accuracy"),
                         "modification":x.get("modification_accuracy"),"regression":x.get("regression_accuracy"),
                         "scorer_error":scorer_error,
                         "valid_submission":bool(rec["submitted"] and rec["output_exists"] and scored_workbook)})
    put("official_scores.json",{"official_runtime":"unmodified official evaluation.py after LibreOffice refresh", "arms":scores,"rows":official})
    sby={(x["task"],x["arm"]):x for x in official}
    classification=[]
    for rec in records:
        x=sby.get((rec["task"],rec["arm"]),{})
        event_file=ROOT/rec["run_dir"]/"events.jsonl"
        event_lines=[json.loads(line) for line in event_file.read_text().splitlines() if line.strip()] if event_file.exists() else []
        ended_after_provider_error=bool(event_lines and event_lines[-1].get("event")=="provider_error")
        if rec["status"] in ("PROVIDER_CENSORED","RUNNER_CENSORED"):cat=rec["status"]
        elif rec["status"]=="MODEL_NONCOMPLETION" and ended_after_provider_error:cat="PROVIDER_CENSORED"
        elif rec["status"]=="SUBMITTED":cat="VALID_SUBMISSION" if x.get("valid_submission") else "INVALID_SUBMISSION"
        elif rec["status"]=="MODEL_NONCOMPLETION":cat="MODEL_NONCOMPLETION"
        else:cat="OTHER"
        classification.append({"task":rec["task"],"arm":rec["arm"],"category":cat,"status":rec["status"],
                               "provider_error_at_deadline":ended_after_provider_error})
    put("censoring.json",{"rows":classification,"by_arm":{a:dict(Counter(x["category"] for x in classification if x["arm"]==a)) for a in ARMS}})
    # The append-only global event ledger also contains eight tool events from
    # an interrupted partial block. Per-run event files belong to the frozen
    # primary outcome and select the completed draw without changing raw data.
    ev=[]
    for rec in records:
        event_file=ROOT/rec["run_dir"]/"events.jsonl"
        ev.extend(event for line in event_file.read_text().splitlines() if line.strip()
                  if (event:=json.loads(line)).get("tool"))
    assert len({(e["task"],e["arm"],e["call"]) for e in ev})==len(ev)
    events=defaultdict(list)
    for e in ev:events[(e["task"],e["arm"])].append(e)
    raw_usage=rows("provider_usage_raw.jsonl") or rows("provider_usage.jsonl")
    if raw_usage and not (OUT/"provider_usage_raw.jsonl").exists():
        shutil.copy2(OUT/"provider_usage.jsonl",OUT/"provider_usage_raw.jsonl")
    # An interrupted, incomplete block was resumed from its first unfinished
    # slot. The append-only raw call ledger retains eight superseded calls.
    # Last record per task/arm/call is the call in the frozen primary run.
    by_call={}
    for u in raw_usage:
        by_call[(u["task"],u["arm"],u["call"])]=u
    usage=list(by_call.values())
    assert len(usage)==sum(r["api_calls"] for r in records)
    for r in records:
        relevant=[u for u in usage if (u["task"],u["arm"])==(r["task"],r["arm"])]
        assert len(relevant)==r["api_calls"]
        assert sum(u["prompt_tokens"] for u in relevant)==r["prompt_tokens"]
    event_by_call={(e["task"],e["arm"],e["call"]):e for e in ev}
    for u in usage:
        event=event_by_call.get((u["task"],u["arm"],u["call"]),{})
        u["tool_result_bytes"] = event.get("observation_bytes_model_visible",0)
        u["tool_result_local_tokens"] = event.get("observation_local_tokens_model_visible",0)
        u["billed_tokens_if_distinct"] = (u.get("raw_usage") or {}).get("billed_tokens")
    with open(OUT/"provider_usage.jsonl","w") as fh:
        for u in usage:fh.write(json.dumps(u)+"\n")
    uses=defaultdict(list)
    for u in usage:uses[(u["task"],u["arm"])].append(u)
    put("provider_routing.json",{"served_models":dict(Counter(str(u.get("served_model")) for u in usage)),
                                 "served_providers_by_arm":{a:dict(Counter(str(u.get("served_provider")) for u in usage if u["arm"]==a)) for a in ARMS},
                                 "provider_wait_s_by_arm":{a:sum(u.get("wait_s",0) for u in usage if u["arm"]==a) for a in ARMS},
                                 "note":"Default OpenRouter routing policy is common to arms; actually served provider may vary stochastically and is reported, not treated as a factorial arm."})
    decomp=decompose_requests(records)
    task_rows=[]
    for t in population:
        row={"task":t,"family":t.split(":")[0]}
        for a in ARMS:
            r=by.get((t,a))
            if not r:row[a]=None;continue
            ee=events[(t,a)]
            event_file=ROOT/r["run_dir"]/"events.jsonl"
            all_events=[json.loads(line) for line in event_file.read_text().splitlines() if line.strip()] if event_file.exists() else []
            helper_invocations=[]
            for event in ee:
                cmd=str((event.get("arguments") or {}).get("command") or "")
                # The frozen helper is commonly imported as ``lx_helpers as lx``.
                # Count actual call syntax, not an import/mention alone.
                helper_invocations += re.findall(r"\b(?:lx_helpers|lx)\.(search|periods|inspect)\s*\(",cmd)
            first_broad=next((event["call"] for event in ee if event.get("broad_view")),None)
            first_targeted=next((event["call"] for event in ee if event.get("targeted_range") or
                                 (event.get("tool")=="view_xlsx" and not event.get("broad_view") and (event.get("arguments") or {}).get("mode")!="list")),None)
            row[a]={"provider_input_tokens":r["prompt_tokens"],"provider_output_tokens":r["completion_tokens"],
                    "calls":r["api_calls"],"status":r["status"],"censoring":next((x["category"] for x in classification if x["task"]==t and x["arm"]==a),"OTHER"),
                    "valid_submission":sby.get((t,a),{}).get("valid_submission",False),
                    "modification":sby.get((t,a),{}).get("modification"),"regression":sby.get((t,a),{}).get("regression"),
                    "broad_views":sum(bool(x.get("broad_view")) for x in ee),
                    "view_calls":sum(x.get("tool")=="view_xlsx" for x in ee),
                    "python_calls":sum(bool(x.get("python_inspection")) for x in ee),
                    "whole_workbook_scans":sum(bool(x.get("whole_workbook_scan")) for x in ee),
                    "targeted_range_inspections":sum(bool(x.get("targeted_range")) for x in ee),
                    "helper_mention_calls":sum(bool(x.get("helper_mentioned")) for x in ee),
                    "helper_invocation_syntax":helper_invocations,
                    "helper_output_bytes_proxy":sum(x.get("observation_bytes_model_visible",0) for x in ee if re.search(r"\b(?:lx_helpers|lx)\.(search|periods|inspect)\s*\(",str((x.get("arguments") or {}).get("command") or ""))),
                    "formula_dump_calls":sum(bool(re.search(r"data_type\s*==\s*['\"]f['\"]|formula|\.value",str((x.get("arguments") or {}).get("command") or ""),re.I)) for x in ee if x.get("tool")=="bash"),
                    "python_stdout_bytes":sum(x.get("observation_bytes_model_visible",0) for x in ee if x.get("tool")=="bash" and x.get("python_inspection")),
                    "first_broad_inspection_turn":first_broad,"first_targeted_inspection_turn":first_targeted,
                    "provider_retry_events":sum(event.get("event")=="provider_error" for event in all_events),
                    "observation_bytes":sum(x.get("observation_bytes_model_visible",0) for x in ee),
                    "observation_local_tokens":sum(x.get("observation_local_tokens_model_visible",0) for x in ee),
                    "truncations":sum(bool(x.get("truncated")) for x in ee),
                    "mean_input_tokens_per_call":r["prompt_tokens"]/r["api_calls"] if r["api_calls"] else None,
                    "served_models":sorted(set(str(x.get("served_model")) for x in uses[(t,a)]))}
        task_rows.append(row)
    put("task_token_summary.json",task_rows)
    contrasts={}
    for label,treat,control in [("D_vs_A","D","A"),("C_vs_A","C","A"),("B_vs_A","B","A"),("D_vs_C","D","C"),("D_vs_B","D","B")]:
        ratios=[];dual=[];family={f:[] for f in FAMILIES};pairs=[]
        for row in task_rows:
            tr=row[treat];co=row[control]
            if not tr or not co or not co["provider_input_tokens"] or not tr["provider_input_tokens"]:continue
            if tr["censoring"] in ("PROVIDER_CENSORED","RUNNER_CENSORED","WORKBOOK_INFRA_CENSORED") or co["censoring"] in ("PROVIDER_CENSORED","RUNNER_CENSORED","WORKBOOK_INFRA_CENSORED"):continue
            v=tr["provider_input_tokens"]/co["provider_input_tokens"]
            ratios.append(v);family[row["family"]].append(v)
            if tr["valid_submission"] and co["valid_submission"]:dual.append(v)
            pairs.append({"task":row["task"],"ratio":v,"log_ratio":math.log(v),
                          "dual_valid":bool(tr["valid_submission"] and co["valid_submission"])})
        contrasts[label]={"E2_all_uncensored":ratio_summary(ratios),"E1_dual_valid":ratio_summary(dual),"family":{f:ratio_summary(v) for f,v in family.items()},"task_pairs":pairs}
    factorial=[]
    for row in task_rows:
        if any(not row[a] or not row[a]["provider_input_tokens"] or row[a]["censoring"] in ("PROVIDER_CENSORED","RUNNER_CENSORED","WORKBOOK_INFRA_CENSORED") for a in ARMS):continue
        log={a:math.log(row[a]["provider_input_tokens"]) for a in ARMS}
        factorial.append({"task":row["task"],"family":row["family"],"S_at_H0":log["C"]-log["A"],
                          "S_at_H1":log["D"]-log["B"],"H_at_S0":log["B"]-log["A"],
                          "H_at_S1":log["D"]-log["C"],
                          "interaction":(log["D"]-log["C"])-(log["B"]-log["A"])})
    def effect_stats(rows_in, key):
        vals=[x[key] for x in rows_in]
        if not vals:return {"n":0,"mean_log_effect":None,"bootstrap_95pct_ci_mean_log_effect":None}
        rng=random.Random(20260922)
        boot=sorted(stats.mean(rng.choice(vals) for _ in vals) for _ in range(10000))
        return {"n":len(vals),"mean_log_effect":stats.mean(vals),
                "multiplicative_ratio":math.exp(stats.mean(vals)),
                "bootstrap_95pct_ci_mean_log_effect":[boot[249],boot[9749]]}
    effect_keys=("S_at_H0","S_at_H1","H_at_S0","H_at_S1","interaction")
    put("factorial_effects.json",{"contrasts":contrasts,"task_level_log_effects":factorial,
                                   "overall_mean_log_effects":{k:stats.mean(x[k] for x in factorial) if factorial else None for k in effect_keys},
                                   "overall_effects_with_ci":{k:effect_stats(factorial,k) for k in effect_keys},
                                   "family_effects_with_ci":{f:{k:effect_stats([x for x in factorial if x["family"]==f],k) for k in effect_keys} for f in FAMILIES}})
    put("family_token_summary.json",{f:{a:{"input_tokens":sum(row[a]["provider_input_tokens"] for row in task_rows if row["family"]==f and row[a]),
                                           "valid":sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows if row["family"]==f)} for a in ARMS}
                                       for f in FAMILIES})
    put("completion_analysis.json",{"by_arm":{a:{"submitted":sum(bool(row[a] and row[a]["status"]=="SUBMITTED") for row in task_rows),
                                                   "valid":sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows),
                                                   "noncompletion":sum(bool(row[a] and row[a]["censoring"]=="MODEL_NONCOMPLETION") for row in task_rows)} for a in ARMS},
                                    "E1_E2":{k:{x:v[x] for x in ("E1_dual_valid","E2_all_uncensored")} for k,v in contrasts.items()}})
    put("token_to_success.json",{a:{"total_input_tokens":sum(row[a]["provider_input_tokens"] for row in task_rows if row[a]),
                                   "uncensored_input_tokens":sum(row[a]["provider_input_tokens"] for row in task_rows if row[a] and row[a]["censoring"] not in ("PROVIDER_CENSORED","RUNNER_CENSORED","WORKBOOK_INFRA_CENSORED")),
                                   "valid_submissions":sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows),
                                   "tokens_per_valid_submission":(sum(row[a]["provider_input_tokens"] for row in task_rows if row[a])/sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows)) if sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows) else None,
                                   "uncensored_tokens_per_valid_submission":(sum(row[a]["provider_input_tokens"] for row in task_rows if row[a] and row[a]["censoring"] not in ("PROVIDER_CENSORED","RUNNER_CENSORED","WORKBOOK_INFRA_CENSORED"))/sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows)) if sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows) else None,
                                   "score_floor_burden":"unavailable: no score floor was preregistered"} for a in ARMS})
    behavior={a:{k:sum(row[a][k] for row in task_rows if row[a]) for k in ("broad_views","view_calls","python_calls","whole_workbook_scans","targeted_range_inspections","helper_mention_calls","helper_output_bytes_proxy","formula_dump_calls","python_stdout_bytes","observation_bytes","observation_local_tokens","truncations")} for a in ARMS}
    put("inspection_behavior.json",behavior)
    put("helper_adoption.json",{"by_arm":{a:{"runs_with_helper_mention":sum(bool(row[a] and row[a]["helper_mention_calls"]) for row in task_rows),
                                              "helper_mention_calls":behavior[a]["helper_mention_calls"],
                                              "runs_with_invocation_syntax":sum(bool(row[a] and row[a]["helper_invocation_syntax"]) for row in task_rows),
                                              "invocation_syntax_by_type":dict(Counter(h for row in task_rows if row[a] for h in row[a]["helper_invocation_syntax"]))} for a in ARMS},
                                "limitation":"Command syntax plus return code requires transcript audit for actual execution and displacement; mention alone is not adoption."})
    put("trajectory_decomposition.json",{a:{"total_model_calls":sum(row[a]["calls"] for row in task_rows if row[a]),
                                            "mean_calls_per_task":stats.mean(row[a]["calls"] for row in task_rows if row[a]) if any(row[a] for row in task_rows) else None,
                                            "total_input_tokens":sum(row[a]["provider_input_tokens"] for row in task_rows if row[a]),
                                            "input_tokens_per_call":(sum(row[a]["provider_input_tokens"] for row in task_rows if row[a])/sum(row[a]["calls"] for row in task_rows if row[a])) if sum(row[a]["calls"] for row in task_rows if row[a]) else None,
                                            "tool_observation_bytes":behavior[a]["observation_bytes"],
                                            "tool_observation_local_tokens":behavior[a]["observation_local_tokens"],
                                            "tool_observation_bytes_per_call":(behavior[a]["observation_bytes"]/sum(row[a]["calls"] for row in task_rows if row[a])) if sum(row[a]["calls"] for row in task_rows if row[a]) else None,
                                            "tool_observation_local_tokens_per_call":(behavior[a]["observation_local_tokens"]/sum(row[a]["calls"] for row in task_rows if row[a])) if sum(row[a]["calls"] for row in task_rows if row[a]) else None,
                                            "broad_view_share_of_views":behavior[a]["broad_views"]/behavior[a]["view_calls"] if behavior[a]["view_calls"] else None,
                                            "python_inspection_share_of_calls":behavior[a]["python_calls"]/sum(row[a]["calls"] for row in task_rows if row[a]) if sum(row[a]["calls"] for row in task_rows if row[a]) else None,
                                            "helper_output_share_of_observation_bytes_proxy":behavior[a]["helper_output_bytes_proxy"]/behavior[a]["observation_bytes"] if behavior[a]["observation_bytes"] else None,
                                            "fixed_schema_bytes":sum(sum(x["exact_bytes_by_category"]["TOOL_SCHEMAS"] for x in decomp if x["arm"]==a) for _ in [0]),
                                            "cumulative_prior_observation_bytes":sum(x["exact_bytes_by_category"]["PRIOR_TOOL_OBSERVATIONS"] for x in decomp if x["arm"]==a),
                                            "mean_prior_observation_bytes_per_call":stats.mean([x["exact_bytes_by_category"]["PRIOR_TOOL_OBSERVATIONS"] for x in decomp if x["arm"]==a]) if any(x["arm"]==a for x in decomp) else None,
                                            "max_prior_observation_bytes_on_call":max([x["exact_bytes_by_category"]["PRIOR_TOOL_OBSERVATIONS"] for x in decomp if x["arm"]==a],default=None),
                                            "assistant_output_tokens":sum(row[a]["provider_output_tokens"] for row in task_rows if row[a])} for a in ARMS})
    mods={a:[row[a]["modification"] for row in task_rows if row[a] and row[a]["valid_submission"] and row[a]["modification"] is not None] for a in ARMS}
    regs={a:[row[a]["regression"] for row in task_rows if row[a] and row[a]["valid_submission"] and row[a]["regression"] is not None] for a in ARMS}
    paired_scores={}
    for label,tr,co in (("D_vs_A","D","A"),("C_vs_A","C","A"),("B_vs_A","B","A"),("D_vs_C","D","C")):
        pairs=[]
        for row in task_rows:
            t,c=row[tr],row[co]
            if not t or not c or not t["valid_submission"] or not c["valid_submission"]:continue
            pairs.append({"task":row["task"],"modification_delta":(t["modification"]-c["modification"]) if t["modification"] is not None and c["modification"] is not None else None,
                          "regression_delta":(t["regression"]-c["regression"]) if t["regression"] is not None and c["regression"] is not None else None})
        paired_scores[label]={"pairs":pairs,"n":len(pairs),
                              "mean_modification_delta":stats.mean(x["modification_delta"] for x in pairs if x["modification_delta"] is not None) if any(x["modification_delta"] is not None for x in pairs) else None,
                              "mean_regression_delta":stats.mean(x["regression_delta"] for x in pairs if x["regression_delta"] is not None) if any(x["regression_delta"] is not None for x in pairs) else None}
    cap={"submitted":{a:sum(bool(row[a] and row[a]["status"]=="SUBMITTED") for row in task_rows) for a in ARMS},
         "valid":{a:sum(bool(row[a] and row[a]["valid_submission"]) for row in task_rows) for a in ARMS},
         "mean_modification_valid_only":{a:stats.mean(mods[a]) if mods[a] else None for a in ARMS},
         "mean_regression_valid_only":{a:stats.mean(regs[a]) if regs[a] else None for a in ARMS},
         "paired_score_deltas":paired_scores,
         "completion_discordance_D_vs_A":[row["task"] for row in task_rows if row["A"] and row["D"] and bool(row["A"]["valid_submission"])!=bool(row["D"]["valid_submission"])],
         "formal_equivalence":"NOT_ESTABLISHED"}
    da=contrasts["D_vs_A"]["E2_all_uncensored"]
    favorable_fams=sum(1 for f,v in contrasts["D_vs_A"]["family"].items() if v.get("median_ratio") is not None and v["median_ratio"]<1)
    gate={"D_vs_A_median_reduction_ge_10pct":da.get("median_reduction_pct") is not None and da["median_reduction_pct"]>=10,
          "favorable_two_families":favorable_fams>=2,
          "not_one_or_two_pathological_tasks":None,"capability_guard_pass":None,
          "coherent_mechanism":None,"component_material":None,
          "discovered":False,"primary_verdict":"EXPERIMENT_INCONCLUSIVE",
          "reason":"Requires scored capability and trajectory review; no automatic favorable verdict from aggregate tokens."}
    put("capability_guard.json",cap);put("discovery_gate.json",gate)
    print("analyzed",len(records),"runs",len(usage),"calls","D/A",da,"cap",cap,flush=True)


if __name__=="__main__":main()
