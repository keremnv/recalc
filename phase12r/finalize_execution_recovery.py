"""Add separately identified normalized execution results; preserve frozen history."""
import json,copy
from pathlib import Path
import replay as r
from analyze import group
import render_tables
OUT=r.OUT;DEST=OUT/'scoring_recovery'
def read(p):return [json.loads(l) for l in p.read_text().splitlines()]
def main():
 manifest=r.load(DEST/'MANIFEST.json');normalized=read(DEST/'RESULTS.jsonl');assert len(normalized)==manifest['count'] and {x['id'] for x in normalized}==set(manifest['ids']);by={x['id']:x for x in normalized};raw=read(OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl');enriched=read(OUT/'BASELINE_CORRECTION_LEDGER.jsonl');effective=[]
 assert all(x['stratum']=='P3' for x in normalized)
 for old in raw:
  new=by.get(old['id'],old)
  if old['id'] in by:
   assert new['V0_hash']==old['V0_hash'] and new.get('V1_hash')==old.get('V1_hash') and new['evaluator_hash']==old['evaluator_hash']
   for key in ['formula_identity','cache_summary','semantic_differences','package_diffs']:
    assert new.get(key)==old.get(key),(old['id'],key)
  effective.append(new)
 links={x['id']:x for x in read(OUT/'QUALIFIED_HISTORY_CLAIM_LINKS.jsonl')}
 for entry in enriched:
  if entry['id'] in links:entry['prior_failure_link_audit']=links[entry['id']]
  if entry['id'] in by:
   n=by[entry['id']];path=DEST/'artifacts'/entry['id']/'result.json'
   entry['NORMALIZED_EXECUTION_RECOVERY']={'artifact':str(path.relative_to(r.ROOT)),'hash':r.sha(path),'basis':n['normalization_basis'],'CURRENT_V0_SCORE':n.get('current_V0_score'),'RECALC_SCORE':n.get('V1_score'),'delta':n.get('delta'),'classification':n['classification'],'original_score_reproduced':n.get('original_score_reproduced'),'historical_cache_recovery_proven':n.get('historical_cache_recovery_proven',False),'formula_identity':n['formula_identity'],'cache_change_summary':n.get('cache_summary'),'interpretation_impact':'UNKNOWN' if n['classification']=='UNSCORABLE' else n['interpretation_impact']}
 (OUT/'BASELINE_CORRECTION_LEDGER.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in enriched))
 scores=read(OUT/'SCORE_REPLAY.jsonl');first=OUT/'SCORE_REPLAY_FIRST_PASS.jsonl'
 if not first.exists():first.write_bytes((OUT/'SCORE_REPLAY.jsonl').read_bytes())
 for x in scores:
  if x['id'] in by:
   n=by[x['id']];x['NORMALIZED_EXECUTION_RECOVERY']={k:n.get(k) for k in ['current_V0_score','V1_score','delta','classification','original_score_reproduced']}
 (OUT/'SCORE_REPLAY.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in scores))
 s=copy.deepcopy(r.load(OUT/'SUMMARY.json'));s['execution_basis']='same-byte separately normalized scoring execution; first-pass SUMMARY.json remains frozen';s['normalization_manifest_hash']=r.sha(DEST/'MANIFEST.json');s['normalization_execution']=r.load(DEST/'EXECUTION.json')
 s['strata']={p:group([x for x in effective if x['stratum']==p]) for p in ['P1','P2','P3']};s['categories']={p:{c:group([x for x in effective if x['stratum']==p and x['category']==c]) for c in ['Template','Financial_Model','Debugging']} for p in ['P1','P2','P3']}
 s['task_clustering']=[{'stratum':p,'task':t,**group([x for x in effective if x['stratum']==p and x['task']==t]),'runs':[x['id'] for x in effective if x['stratum']==p and x['task']==t]} for p,t in sorted({(x['stratum'],x['task']) for x in effective})]
 for p in ['P1','P2']:assert s['strata'][p]==r.load(OUT/'SUMMARY.json')['strata'][p]
 (DEST/'SUMMARY.json').write_text(json.dumps(s,indent=2));render_tables.OUT=DEST;render_tables.main()
 (DEST/'IDENTITY.json').write_text(json.dumps({'normalized_summary_hash':r.sha(DEST/'SUMMARY.json'),'results_hash':r.sha(DEST/'RESULTS.jsonl'),'authoritative_additive_ledger_hash':r.sha(OUT/'BASELINE_CORRECTION_LEDGER.jsonl'),'first_pass_ledger_hash':r.sha(OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl'),'scoring_replay_first_pass_hash':r.sha(first),'official_scorer_hash':r.sha(r.BENCH/'evaluation/evaluation.py')},indent=2))
 print(json.dumps(s['strata']['P3'],indent=2))
if __name__=='__main__':main()
