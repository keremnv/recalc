import copy,json,subprocess,sys,time,os,resource,gc,shutil,signal
from pathlib import Path
import replay as r
from bounded_resume import bounded_score,verify
from reference_parse_cache import candidate_loader
OUT=r.OUT;DEST=OUT/'scoring_recovery'
def score_existing(row,old,work):
 start=time.monotonic();result=copy.deepcopy(old);work.mkdir(parents=True,exist_ok=True)
 for key in ['V0_source','input','gold']:
  expected=row[{'V0_source':'V0_hash','input':'input_hash','gold':'gold_hash'}[key]];assert r.sha(r.ROOT/row[key])==expected
 assert r.sha(r.BENCH/'evaluation/evaluation.py')==old['evaluator_hash']
 v0=r.ROOT/old['V0_artifact'];assert r.sha(v0)==old['V0_hash']
 result['current_V0_score']=bounded_score(row,v0,work/'score/V0');result['original_score_reproduced']=all(result['current_V0_score']['official'][k]==row['original_score'][k] for k in r.KEYS)
 result['classification']='UNSCORABLE';result['interpretation_impact']='UNKNOWN'
 if old.get('V1_artifact'):
  v1=r.ROOT/old['V1_artifact'];assert r.sha(v1)==old['V1_hash'];result['V1_score']=bounded_score(row,v1,work/'score/V1');v0s=result['current_V0_score'];v1s=result['V1_score'];result['delta']={k:v1s['official'][k]-v0s['official'][k] for k in r.KEYS}
  if v0s['status']=='SCORE_PASS' and v1s['status']=='SCORE_PASS':
   delta=result['delta'];harm=delta['accuracy']<0 or any(delta[k]<=-.01+1e-12 for k in r.KEYS[1:]);gain=delta['accuracy']>0 or any(delta[k]>=.01-1e-12 for k in r.KEYS[1:]);result['mixed_gain_and_harm']=gain and harm;result['mixed_signed_changes']=any(v>0 for v in delta.values()) and any(v<0 for v in delta.values())
   if harm:result['classification']='RECALC_REGRESSION'
   elif not gain:result['classification']='RECALC_NO_MATERIAL_EFFECT';result['interpretation_impact']='UNAFFECTED'
   else:
    # Newly assessable gain: full frozen classifier/witness, without a new LO execution.
    result=r.replay(row,DEST/'artifacts')
 result['historical_cache_recovery_proven']=result['classification']=='CACHE_ONLY_SCORE_RECOVERY' and result['original_score_reproduced'] and row['historical_byte_linkage']=='ARCHIVED_SUBMISSION'
 result['total_elapsed_seconds']=time.monotonic()-start;result['scoring_recovery_execution_amendment_hash']=r.sha(OUT/'SCORING_RECOVERY_EXECUTION_AMENDMENT.md')
 return result

def main():
 verify();DEST.mkdir(exist_ok=True)
 if len(sys.argv)>1:
  resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));gc.set_threshold(400,5,2)
  m=r.load(DEST/'MANIFEST.json');amendment=r.load(DEST/'IMPLEMENTATION_AMENDMENT.json');assert r.sha(Path(__file__))==amendment['implementation_hash'];assert r.sha(OUT/'scoring_execution_recovery_initial.py')==m['implementation_hash']
  row=next(x for x in r.load(OUT/'POPULATION_MANIFEST.json')['eligible'] if x['id']==sys.argv[1]);work=DEST/'artifacts'/row['id'];events=[];native=r.openpyxl.load_workbook;r.openpyxl.load_workbook=candidate_loader(native,work,events);r.score=bounded_score
  old=r.load(OUT/'artifacts'/row['id']/'result.json');result=score_existing(row,old,work);assert result.get('V1_hash')==old.get('V1_hash');assert result['V0_hash']==old['V0_hash']
  result['normalization_basis']='lossless auxiliary pickle execution recovery; same source/derived bytes and official scorer';result['first_pass_result_hash']=r.sha(OUT/'artifacts'/row['id']/'result.json')
  (work/'result.json').write_text(json.dumps(result,indent=2));shutil.rmtree(work/'.parsed_objects',ignore_errors=True)
  for p in work.rglob('.scored_objects'):shutil.rmtree(p,ignore_errors=True)
  return
 raw=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl').read_text().splitlines()]
 ids=[x['id'] for x in raw if 'DimensionHolder' in json.dumps({k:x.get(k) for k in ['current_V0_score','V1_score','replay_error']})]
 manifest={'ids':ids,'count':len(ids),'spec_hash':r.sha(OUT/'SCORING_EXECUTION_RECOVERY_SPEC.md'),'raw_ledger_hash':r.sha(OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl'),'implementation_hash':r.sha(OUT/'scoring_execution_recovery_initial.py'),'serialization_hash':r.sha(OUT/'workbook_pickle_compat.py')}
 mp=DEST/'MANIFEST.json'
 if mp.exists():assert r.load(mp)==manifest
 else:mp.write_text(json.dumps(manifest,indent=2));(DEST/'MANIFEST.sha256').write_text(r.sha(mp))
 start=time.monotonic();results=[]
 with (DEST/'STDERR.log').open('a') as err:
  for i,rid in enumerate(ids,1):
   pth=DEST/'artifacts'/rid/'result.json'
   if not pth.exists():
    p=subprocess.Popen([sys.executable,str(Path(__file__)),rid],stderr=err,stdout=err,start_new_session=True,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
    try:code=p.wait(timeout=900)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.wait();code=-15
    if code:raise RuntimeError((rid,code))
   results.append(r.load(pth));(DEST/'RESULTS.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in results))
   if i%10==0:print(i,'/',len(ids),flush=True)
 (DEST/'EXECUTION.json').write_text(json.dumps({'rows':len(results),'wall_seconds':time.monotonic()-start,'new_recalculations':0,'results_hash':r.sha(DEST/'RESULTS.jsonl')},indent=2))
if __name__=='__main__':main()
