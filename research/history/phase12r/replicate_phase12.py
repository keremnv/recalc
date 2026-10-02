"""Requested all-final-file Phase12 replication, outside submission prevalence."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
import replay as r
manifest=r.load(r.OUT/'PHASE12_REPLICATION_MANIFEST.json');expected=(r.OUT/'PHASE12_REPLICATION_MANIFEST.sha256').read_text().split()[0];assert r.sha(r.OUT/'PHASE12_REPLICATION_MANIFEST.json')==expected
base=[json.loads(l) for l in (r.OUT/'BASELINE_CORRECTION_LEDGER.jsonl').read_text().splitlines()];assert len(base)==len(r.load(r.OUT/'POPULATION_MANIFEST.json')['eligible'])
rows=[x for x in base if x['id'] in manifest['primary_phase12_ids']]
with (r.OUT/'PHASE12_REPLICATION_STDERR.log').open('a') as err:
 for row in manifest['supplement']:
  resultpath=r.OUT/'artifacts'/row['id']/'result.json';start=time.monotonic()
  if not resultpath.exists():
   p=subprocess.Popen([sys.executable,str(r.OUT/'bounded_resume.py'),'--row-id',row['id']],stdout=subprocess.DEVNULL,stderr=err,start_new_session=True,env={**os.environ,'LC_ALL':'C.UTF-8','LANG':'C.UTF-8','TZ':'UTC'})
   try:code=p.wait(timeout=900)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.wait();code=-15
   if not resultpath.exists():resultpath.parent.mkdir(exist_ok=True);resultpath.write_text(json.dumps({**row,'classification':'UNSCORABLE','formula_identity':'UNDETERMINED','replay_error':f'PHASE12_SUPPLEMENT_PROCESS_EXIT_{code}','recalc':{'status':'RECALC_FAILED'},'total_elapsed_seconds':time.monotonic()-start},indent=2))
  result=r.load(resultpath);result['prevalence_eligible']=False;rows.append(result);print(row['task'],row['status'],result['classification'],flush=True)
(r.OUT/'PHASE12_REPLICATION.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows));(r.OUT/'PHASE12_REPLICATION_IDENTITY.json').write_text(json.dumps({'requested_final_files':28,'replayed_final_files':len(rows),'eligible_submissions':23,'retained_nonsubmitted_candidates':5,'manifest_hash':expected,'replication_ledger_hash':r.sha(r.OUT/'PHASE12_REPLICATION.jsonl'),'independent_prevalence':False},indent=2))
print('Phase12 replication records',len(rows))
