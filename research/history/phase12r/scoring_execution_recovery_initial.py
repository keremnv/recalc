import json,subprocess,sys,time,os,resource,gc,shutil,signal
from pathlib import Path
import replay as r
from bounded_resume import bounded_score,verify
from reference_parse_cache import candidate_loader
OUT=r.OUT;DEST=OUT/'scoring_recovery'
def main():
 verify();DEST.mkdir(exist_ok=True)
 if len(sys.argv)>1:
  resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));gc.set_threshold(400,5,2)
  m=r.load(DEST/'MANIFEST.json');assert r.sha(Path(__file__))==m['implementation_hash']
  row=next(x for x in r.load(OUT/'POPULATION_MANIFEST.json')['eligible'] if x['id']==sys.argv[1]);work=DEST/'artifacts'/row['id'];events=[];native=r.openpyxl.load_workbook;r.openpyxl.load_workbook=candidate_loader(native,work,events);r.score=bounded_score
  result=r.replay(row,DEST/'artifacts');old=r.load(OUT/'artifacts'/row['id']/'result.json');assert result.get('V1_hash')==old.get('V1_hash');assert result['V0_hash']==old['V0_hash']
  result['normalization_basis']='lossless auxiliary pickle execution recovery; same source/derived bytes and official scorer';result['first_pass_result_hash']=r.sha(OUT/'artifacts'/row['id']/'result.json')
  (work/'result.json').write_text(json.dumps(result,indent=2));shutil.rmtree(work/'.parsed_objects',ignore_errors=True)
  for p in work.rglob('.scored_objects'):shutil.rmtree(p,ignore_errors=True)
  return
 raw=[json.loads(l) for l in (OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl').read_text().splitlines()]
 ids=[x['id'] for x in raw if 'DimensionHolder' in json.dumps({k:x.get(k) for k in ['current_V0_score','V1_score','replay_error']})]
 manifest={'ids':ids,'count':len(ids),'spec_hash':r.sha(OUT/'SCORING_EXECUTION_RECOVERY_SPEC.md'),'raw_ledger_hash':r.sha(OUT/'BASELINE_CORRECTION_LEDGER_RAW.jsonl'),'implementation_hash':r.sha(Path(__file__)),'serialization_hash':r.sha(OUT/'workbook_pickle_compat.py')}
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
