#!/usr/bin/env python3
"""Normalize archived aggregate/cohort token observations without pooling rows."""
import glob
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"token_claim_discovery/historical_token_summary.json"
REG=ROOT/"product_hygiene/future_claim_evidence_registry.json"


def load(path):return json.loads((ROOT/path).read_text())


def run_stats(items,control="H0",treat="H1",effkey="efficiency"):
    result={}
    for arm in (control,treat):
        armrows=[x for x in items if x.get("arm")==arm]
        eff=[x.get(effkey,{}) or {} for x in armrows]
        result[arm]={"runs":len(armrows),"calls":sum(x.get("api_calls",x.get("model_calls",0)) for x in eff),
                     "prompt":sum(x.get("prompt_tokens",x.get("input_tokens",0)) for x in eff),
                     "output":sum(x.get("completion_tokens",x.get("output_tokens",0)) for x in eff),
                     "submitted":sum(x.get("status")=="SUBMITTED" for x in armrows),
                     "statuses":dict(Counter(x.get("status") for x in armrows))}
    return result


def main():
    reg=load("product_hygiene/future_claim_evidence_registry.json")
    rows=[]
    for r in reg["rows"]:
        if r.get("scope") not in ("aggregate","ALL","A-representative","B-exposure"):
            continue
        measure=r.get("token_measure") or ""
        c,t=r.get("control_tokens"),r.get("treatment_tokens")
        src=ROOT/r["source"]
        row={"experiment":r["experiment"],"population":r.get("scope"),"sample_size":r.get("sample_size"),
             "control_input_tokens":c if "input" in measure or "prompt" in measure else None,
             "treatment_input_tokens":t if "input" in measure or "prompt" in measure else None,
             "control_output_tokens":None,"treatment_output_tokens":None,
             "control_total_tokens":c if "total" in measure else None,
             "treatment_total_tokens":t if "total" in measure else None,
             "token_measure":measure,"calls":{"control":None,"treatment":None},
             "completion":{"control_submitted":None,"treatment_submitted":None},
             "censoring":r.get("censoring"),"model_facing_difference":r.get("model_facing_mechanism_differed"),
             "invisible_difference":r.get("invisible_mechanism_differed"),
             "helper_adoption":None,"known_attribution_problem":r.get("note"),
             "source":r["source"],"source_sha256":hashlib.sha256(src.read_bytes()).hexdigest() if src.is_file() else None,
             "interpretation":"DESCRIPTIVE_ASSOCIATION; no current RC causal attribution"}
        e=r["experiment"]
        if e.startswith("Thin architecture checkpoint"):
            data=load("thin_architecture_checkpoint/efficiency_metrics.json")
            cohort=r["scope"]
            a=data[f"{cohort}_H0"];b=data[f"{cohort}_H1"]
            row["calls"]={"control":a["api_calls"],"treatment":b["api_calls"]}
            row["completion"]={"control_submitted":a["submitted"],"treatment_submitted":b["submitted"],
                               "control_outputs":a["outputs"],"treatment_outputs":b["outputs"]}
            row["helper_adoption"]="A-representative/nonadopter and B-exposure cohorts split in source; not randomized helper uptake"
        elif e=="Inspection efficiency Stage B":
            d=load("inspection_efficiency_ab/efficiency_metrics.json")["inspection_work"]
            row["calls"]={"control":d["C0"]["api_calls"],"treatment":d["C1"]["api_calls"]}
            items=[load(str(Path(p).relative_to(ROOT))) for p in glob.glob(str(ROOT/"inspection_efficiency_ab/reps/*/run_record.json"))]
            stats=run_stats(items,"C0","C1")
            row["completion"]={"control_submitted":stats["C0"]["submitted"],"treatment_submitted":stats["C1"]["submitted"]}
            row["helper_adoption"]="Variable adoption; stage includes repeated discordant pairs"
        elif e=="Batch-write helpers":
            d=load("batch_write_helper_ab/efficiency_metrics.json")["arm_totals"]
            row["calls"]={"control":d["C0"]["api_calls"],"treatment":d["C1"]["api_calls"]}
            row["helper_adoption"]="0/13 treatment runs invoked rejected batch-write helper"
        elif e=="Default-harness deterministic execution":
            d=load("architecture_transfer_audit/control_efficiency_census.json")["deterministic_execution_glm"]
            row["calls"]={"control":d["C0"]["calls"],"treatment":d["C1"]["calls"]}
            row["helper_adoption"]="deterministic executor invoked zero times"
        elif e in ("candidate_a_live","candidate_a_a1_checkpoint_rerun_01"):
            d=load(r["source"])
            stats={}
            for arm in ("H0","H1"):
                xx=[x for x in d["runs"] if x.get("arm")==arm]
                stats[arm]={"calls":sum(x.get("model_calls",0) for x in xx),"input":sum(x.get("input_tokens",0) for x in xx),
                            "output":sum(x.get("output_tokens",0) for x in xx),"submitted":sum(x.get("status")=="SUBMITTED" for x in xx),
                            "statuses":dict(Counter(x.get("status") for x in xx))}
            row["calls"]={"control":stats["H0"]["calls"],"treatment":stats["H1"]["calls"]}
            row["completion"]={"control_submitted":stats["H0"]["submitted"],"treatment_submitted":stats["H1"]["submitted"]}
            row["control_input_tokens"]=stats["H0"]["input"]
            row["treatment_input_tokens"]=stats["H1"]["input"]
            row["control_output_tokens"]=stats["H0"]["output"]
            row["treatment_output_tokens"]=stats["H1"]["output"]
            row["status_counts"]={"control":stats["H0"]["statuses"],"treatment":stats["H1"]["statuses"]}
            row["helper_adoption"]="No model-facing helper-factor treatment; invisible Candidate A varies"
        elif e in ("representative_architecture_checkpoint","representative_architecture_checkpoint_replication"):
            folder="reps" if e=="representative_architecture_checkpoint" else "reps_replication"
            items=[load(str(Path(p).relative_to(ROOT))) for p in glob.glob(str(ROOT/f"representative_architecture_checkpoint/{folder}/*/run_record.json"))]
            stats=run_stats(items)
            row["calls"]={"control":stats["H0"]["calls"],"treatment":stats["H1"]["calls"]}
            row["completion"]={"control_submitted":stats["H0"]["submitted"],"treatment_submitted":stats["H1"]["submitted"]}
            row["control_input_tokens"]=stats["H0"]["prompt"];row["treatment_input_tokens"]=stats["H1"]["prompt"]
            row["control_output_tokens"]=stats["H0"]["output"];row["treatment_output_tokens"]=stats["H1"]["output"]
            row["status_counts"]={"control":stats["H0"]["statuses"],"treatment":stats["H1"]["statuses"]}
            row["helper_adoption"]="Helper surface fixed across arms; sparse use"
        elif e in ("live_transparent_runtime_ab","targeted_runtime_replication"):
            pattern="live_transparent_runtime_ab/runs/**/run_record.json" if e=="live_transparent_runtime_ab" else "targeted_runtime_replication/reps/**/run_record.json"
            items=[load(str(Path(p).relative_to(ROOT))) for p in glob.glob(str(ROOT/pattern),recursive=True)]
            stats=run_stats(items)
            row["calls"]={"control":stats["H0"]["calls"],"treatment":stats["H1"]["calls"]}
            row["completion"]={"control_submitted":stats["H0"]["submitted"],"treatment_submitted":stats["H1"]["submitted"]}
            row["status_counts"]={"control":stats["H0"]["statuses"],"treatment":stats["H1"]["statuses"]}
        rows.append(row)
    out={"unit":"aggregate experiment/cohort; overlapping cohorts explicitly nested; no pooling as independent experiments",
         "registry_rows_not_pooled":len(reg["rows"]),"aggregate_or_cohort_records":len(rows),
         "rows":rows,"warning":"Total tokens and input tokens are distinct. Missing splits remain null. No prior aggregate is a current RC causal token claim."}
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(len(rows),"aggregate/cohort records")


if __name__=="__main__":main()
